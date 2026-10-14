"""Small causal forecast desk: AR(2), lagged volume, and validated reversion.

No external feeds, stochastic simulation, or third-party numeric runtime.
Selection uses early walk-forward errors; reported errors use a later window.
"""
import math
from functools import lru_cache
from statistics import fmean

from .engine import FEE, SLIPPAGE, TICK_VALUE

MIN_TRAIN = 20
SELECTION = 12
MIN_AUDIT = 20
MAX_AUDIT = 40
TRAIN_WINDOW = 96
MAX_CANDLES = 180
COST_POINTS = (2*SLIPPAGE*TICK_VALUE+2*FEE)/(TICK_VALUE*10)
VERSION = 'quant-desk-1'


def _solve(matrix, values):
    a = [list(row)+[value] for row,value in zip(matrix, values)]
    for i in range(len(a)):
        pivot = max(range(i,len(a)), key=lambda j:abs(a[j][i]))
        a[i],a[pivot] = a[pivot],a[i]
        div = a[i][i]
        if abs(div) < 1e-12:
            raise ValueError('Singular regression')
        a[i] = [v/div for v in a[i]]
        for j in range(len(a)):
            if j != i:
                factor = a[j][i]
                a[j] = [v-factor*w for v,w in zip(a[j],a[i])]
    return [row[-1] for row in a]


def _features(row, model):
    price,d1,d2,volume = row['x']
    if model == 'mr':
        return [price]
    return [d1,d2,volume] if model == 'arx' else [d1,d2]


def _fit(rows, model):
    rows = rows[-TRAIN_WINDOW:]
    x = [_features(row,model) for row in rows]
    y = [row['y'] for row in rows]
    means = [fmean(col) for col in zip(*x)]
    scales = [max(math.sqrt(fmean((v-m)**2 for v in col)),1e-9) for col,m in zip(zip(*x),means)]
    ym = fmean(y)
    z = [[(v-m)/s for v,m,s in zip(row,means,scales)] for row in x]
    size = len(means)
    # A fixed, small ridge penalty stabilizes flat/correlated data.
    matrix = [[sum(row[i]*row[j] for row in z)+(1.0 if i==j else 0) for j in range(size)] for i in range(size)]
    target = [sum(row[i]*(value-ym) for row,value in zip(z,y)) for i in range(size)]
    weights = _solve(matrix,target)
    return dict(means=means,scales=scales,weights=weights,mean_y=ym,model=model)


def _predict(fit, row):
    return fit['mean_y']+sum(w*(v-m)/s for v,m,s,w in zip(_features(row,fit['model']),fit['means'],fit['scales'],fit['weights']))


def _rmse(errors):
    return math.sqrt(fmean(e*e for e in errors))


def _quantile(values, probability):
    values = sorted(values)
    position = probability*(len(values)-1)
    lo = math.floor(position)
    hi = math.ceil(position)
    return values[lo]+(values[hi]-values[lo])*(position-lo)


def _row(candles, i):
    p,d1,d2 = candles[i][1],candles[i-1][1],candles[i-2][1]
    return dict(x=(p,p-d1,d1-d2,math.log1p(candles[i][2])))


def analyze(candles):
    """Caller supplies only available closed candles, including past warmup."""
    key = tuple((int(c['time']),float(c['close']),float(c['volume'])) for c in candles[-MAX_CANDLES:])
    return _analyze(key)


def _decision(delta, rmse, baseline, audit):
    skill = 1-rmse/baseline if baseline>1e-9 else 0.0
    up_count = sum(1 if delta+error>0 else .5 if abs(delta+error)<1e-12 else 0 for error in audit)
    prob_up = (up_count+.5)/(len(audit)+1)
    expected_net = abs(delta)-COST_POINTS
    side_probability = prob_up if delta>0 else 1-prob_up
    reasons = []
    if baseline<=1e-9 or skill<.05:
        reasons.append('Sai số chưa tốt hơn dự báo giữ nguyên giá ít nhất 5%.')
    if expected_net<=0:
        reasons.append('Biên dự báo chưa vượt 0,24 điểm phí và trượt giá khứ hồi.')
    if abs(delta)<rmse*.5:
        reasons.append('Mức dự báo còn nhỏ so với sai số thường gặp.')
    if side_probability<.60:
        reasons.append('Phân bố sai số chưa nghiêng đủ về một chiều.')
    suggestion = 'wait' if reasons else 'long' if delta>0 else 'short'
    confidence = 'low' if suggestion=='wait' or len(audit)<30 else 'moderate'
    surprise = abs(audit[-1])/rmse if rmse>1e-9 else 0
    if surprise>2:
        confidence = 'low'
        reasons.append('Nến vừa rồi lệch dự báo hơn 2 lần RMSE; tín hiệu có thể kém ổn định.')
        suggestion = 'wait'
    return dict(probability_up=prob_up, expected_net_points=expected_net,suggestion=suggestion,
                confidence=confidence,surprise_ratio=surprise,
                reasons=reasons or ['Sai số vượt chuẩn kiểm định, biên dự báo vượt phí và phân bố sai số nghiêng về một chiều.'])


def at_quote(result, price):
    """Re-evaluate the forecast against the price at which a player can trade."""
    out = {k:v for k,v in result.items() if not k.startswith('_')}
    if result['status']=='ready':
        delta = result['forecast_price']-price
        out.update(_decision(delta,result['rmse_points'],result['baseline_rmse_points'],result['_audit_errors']))
        out.update(delta_points=delta,reference_price=price)
    return out


@lru_cache(maxsize=256)
def _analyze(candles):
    minimum = MIN_TRAIN+SELECTION+MIN_AUDIT
    meta = dict(version=VERSION, n_candles=len(candles), min_rows=minimum,
                round_trip_cost_points=COST_POINTS, horizon_bars=1)
    if not candles:
        return dict(meta,status='insufficient',reason='Chưa có nến để phân tích.',n_rows=0)
    if any(not math.isfinite(p) or p<=0 or not math.isfinite(v) or v<0 for _,p,v in candles):
        return dict(meta,status='insufficient',reason='Dữ liệu giá/khối lượng không hợp lệ.',n_rows=0)
    rows = []
    for i in range(2,len(candles)-1):
        # Do not learn lunch gaps, overnight jumps, duplicates or ATC as 1 minute.
        if all(candles[j][0]-candles[j-1][0]==60 for j in range(i-1,i+2)):
            row = _row(candles,i)
            row.update(y=candles[i+1][1]-candles[i][1],time=candles[i+1][0])
            rows.append(row)
    meta['n_rows'] = len(rows)
    meta['data_as_of'] = candles[-1][0]
    if len(rows)<minimum:
        return dict(meta,status='insufficient',reason=f'Cần thêm {minimum-len(rows)} mẫu nến liên tục để kiểm định; chưa đưa gợi ý.')
    if not all(candles[j][0]-candles[j-1][0]==60 for j in range(len(candles)-2,len(candles))):
        return dict(meta,status='insufficient',reason='Nến cuối có khoảng nghỉ/ATC. Chờ chuỗi nến phút liên tục mới.')
    audit_count = min(MAX_AUDIT,len(rows)-MIN_TRAIN-SELECTION)
    start = len(rows)-audit_count-SELECTION
    candidates = ('ar','arx','mr')
    errors = {model:[] for model in candidates}
    targets = []
    for i in range(start,len(rows)):
        train = rows[max(0,i-TRAIN_WINDOW):i]
        targets.append(rows[i]['y'])
        for model in candidates:
            errors[model].append(rows[i]['y']-_predict(_fit(train,model),rows[i]))
    selection = {model:_rmse(values[:SELECTION]) for model,values in errors.items()}
    chosen = 'ar'
    reason = 'AR dùng hai thay đổi giá gần nhất; giữ mô hình đơn giản khi biến thêm chưa giúp rõ rệt.'
    volume_values = [row['x'][3] for row in rows[:start+SELECTION]]
    if max(volume_values)-min(volume_values)>1e-9 and selection['arx']<selection['ar']*.95:
        chosen = 'arx'
        reason = 'Khối lượng trễ giúp giảm sai số ít nhất 5% trong cửa sổ chọn mô hình.'
    mr_fit = _fit(rows[:start+SELECTION],'mr')
    beta = mr_fit['weights'][0]/mr_fit['scales'][0]
    if -1<beta<0 and selection['mr']<selection[chosen]*.95:
        chosen = 'mr'
        reason = 'Quay về vùng giá giúp giảm sai số ít nhất 5% trong cửa sổ chọn mô hình.'
    audit = errors[chosen][SELECTION:]
    baseline = _rmse(targets[SELECTION:])  # next close == current close
    rmse = _rmse(audit)
    skill = 1-rmse/baseline if baseline>1e-9 else 0.0
    current = _row(candles,len(candles)-1)
    fit = _fit(rows,chosen)
    delta = _predict(fit,current)
    last = candles[-1][1]
    lo,hi = last+delta+_quantile(audit,.10),last+delta+_quantile(audit,.90)
    recent = [p for _,p,_ in candles[-40:]]
    center = fmean(recent)
    spread = math.sqrt(fmean((p-center)**2 for p in recent))
    z = (last-center)/spread if spread>1e-9 else None
    mr_audit = _rmse(errors['mr'][SELECTION:])
    mr_current = _fit(rows,'mr')
    slope = mr_current['weights'][0]/mr_current['scales'][0]
    mr_supported = -1<slope<0 and baseline>1e-9 and mr_audit<baseline*.95
    return dict(meta,**_decision(delta,rmse,baseline,audit),status='ready', model={'ar':'AR(2)','arx':'ARX(2) · volume trễ','mr':'Mean reversion'}[chosen],
                selected=chosen, selection_reason=reason, forecast_price=last+delta, delta_points=delta,
                interval80=[lo,hi], probability_label='Ước lượng từ sai số; chưa hiệu chỉnh xác suất',
                rmse_points=rmse, baseline_rmse_points=baseline, skill_pct=skill*100,
                n_selection=SELECTION,n_audit=len(audit), latest_error_points=audit[-1], _audit_errors=tuple(audit),
                z_score=z,z_window=len(recent),center_price=center,
                mean_reversion_supported=mr_supported, mean_reversion_rmse_points=mr_audit,
                mean_reversion_half_life_bars=math.log(.5)/math.log(1+slope) if mr_supported else None,
                evaluation_method='walk_forward_selection_then_later_audit',
                disclaimer='Gợi ý mô hình, không tự đặt lệnh. Khoảng 80% là ước lượng từ mẫu sai số gần đây.')
