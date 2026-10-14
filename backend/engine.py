"""Paper futures accounting. Prices are 0.1-point ticks; amounts are VND."""
from copy import deepcopy

INITIAL = 100_000_000
TICK_VALUE = 10_000
FEE = 2_000
MARGIN_PER_CONTRACT = 1_000_000  # Fixed mini-game stake, not a broker requirement.
SLIPPAGE = 1


def account():
    return dict(cash=INITIAL, qty=0, entry=0.0, fees=0, trades=[], liquidations=0)


def metrics(a, mark):
    pnl = round((mark - a['entry']) * a['qty'] * TICK_VALUE)
    equity = a['cash'] + pnl
    margin = abs(a['qty']) * MARGIN_PER_CONTRACT
    return dict(unrealized=pnl, equity=equity, margin=margin,
                available=equity-margin, net_pnl=equity-INITIAL)


def trade(a, side, qty, mark, stamp='', reason='market'):
    if side not in (-1, 1) or isinstance(qty, bool) or not isinstance(qty, int) or not 1 <= qty <= 50:
        raise ValueError('Khối lượng phải từ 1 đến 50 hợp đồng.')
    if not isinstance(mark, (int, float)) or mark <= 0:
        raise ValueError('Chưa có giá hợp lệ.')
    b = deepcopy(a)
    fill = mark + side * SLIPPAGE
    old = b['qty']
    delta = side * qty
    closing = min(abs(old), qty) if old * delta < 0 else 0
    realized = round((fill - b['entry']) * (1 if old > 0 else -1) * closing * TICK_VALUE)
    remaining = old + delta
    if abs(remaining) > 50:
        raise ValueError('Game giới hạn vị thế tối đa 50 hợp đồng.')
    if old * delta >= 0:
        entry = (abs(old)*b['entry'] + qty*fill)/abs(remaining)
    elif abs(delta) > abs(old):
        entry = fill
    else:
        entry = b['entry'] if remaining else 0
    b.update(qty=remaining, entry=entry, cash=b['cash']+realized-qty*FEE, fees=b['fees']+qty*FEE)
    # Closing and reducing exposure are always allowed, including a margin call.
    increasing = abs(remaining) > abs(old) or (remaining * old < 0)
    if increasing and metrics(b, mark)['available'] < 0:
        raise ValueError('Không đủ sức mua ký quỹ. Giảm số hợp đồng.')
    b['trades'].append(dict(side=side, qty=qty, price=fill/10, realized=realized,
                            fee=qty*FEE, time=stamp, reason=reason))
    a.clear()
    a.update(b)
    return a['trades'][-1]


def flatten(a, mark, stamp='', reason='close'):
    if a['qty']:
        return trade(a, -1 if a['qty'] > 0 else 1, abs(a['qty']), mark, stamp, reason)


def risk_check(a, mark, stamp=''):
    m = metrics(a, mark)
    if a['qty'] and m['equity'] < .8*m['margin']:
        flatten(a, mark, stamp, 'margin_call')
        a['liquidations'] += 1
        return True
    return False

