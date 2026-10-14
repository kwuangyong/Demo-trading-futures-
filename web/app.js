(async () => {
const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat('vi-VN');
const num = (n) => fmt.format(Math.round(n));
const money = (n) => `${num(n)} ₫`;
const points = (n) => new Intl.NumberFormat('vi-VN', {minimumFractionDigits:1,maximumFractionDigits:1}).format(n);
const date = (ts, short=false) => new Intl.DateTimeFormat('vi-VN', {timeZone:'Asia/Ho_Chi_Minh', ...(short?{hour:'2-digit',minute:'2-digit'}:{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})}).format(new Date(ts*1000));
let game = null, busy = false, polling = false, page = 'terminal', lastError = '', toastTimer;
const safeGet = (key) => {try{return localStorage.getItem(key);}catch{return null;}};
const safeSet = (key,value) => {try{localStorage.setItem(key,value);}catch{}};
function toast(message) { $('toast').textContent=message; $('toast').classList.add('visible'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').classList.remove('visible'),4000); }
function notice(message, type='') { $('notice').textContent=message; $('notice').className=`notice ${type}`; }
async function api(path, options={}) {
  if(location.protocol==='file:') throw new Error('Chạy start-local.bat hoặc start-local.sh, rồi mở http://localhost:8080 để chơi.');
  const response = await fetch(`/api${path}`, {credentials:'same-origin', ...options, headers:{'Content-Type':'application/json', ...options.headers}});
  let data; try{data=await response.json();}catch{throw new Error('Không đọc được phản hồi máy chủ.');}
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'Yêu cầu không hợp lệ.');
  return data;
}
function choosePage(next) {
  page=next; for(const p of ['terminal','ranking','guide']) $(`page-${p}`).hidden=p!==next;
  document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===next));
  if(next==='ranking') loadRanking();
}
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>choosePage(b.dataset.page));
$('theme').onclick=()=>{const theme=document.documentElement.dataset.theme==='light'?'dark':'light';document.documentElement.dataset.theme=theme;safeSet('arena_theme',theme);drawChart(game?.candles||[]);};
document.documentElement.dataset.theme=safeGet('arena_theme')||'dark';
$('name').value=safeGet('arena_name')||'Trader';
function updateButtons(){const enabled=game?.can_trade && !busy && !lastError;for(const id of ['long','short']) $(id).disabled=!enabled;$('close').disabled=!enabled||!game?.account.qty;$('finish').disabled=busy||!game||game.done;$('start').disabled=busy;}
$('start').onclick=async()=>{
  if(busy)return;
  if(game&&!game.done&&!confirm('Bắt đầu lượt mới sẽ đóng vị thế và chốt lượt hiện tại. Tiếp tục?'))return;
  busy=true;updateButtons();$('start').textContent='Đang tải…';notice('Đang tải nguồn dữ liệu. Có thể cần tối đa 35 giây…');
  try{game=await api('/games',{method:'POST',body:JSON.stringify({name:$('name').value.trim()||'Trader',mode:$('mode').value})});safeSet('arena_game',game.id);safeSet('arena_name',game.name);lastError='';choosePage('terminal');render();toast('Lượt chơi bắt đầu. Chúc bạn giao dịch có kỷ luật!');}
  catch(e){notice(e.message+' Chọn Luyện tập để thử game bằng dữ liệu mẫu.', 'error');toast(e.message);}
  finally{busy=false;$('start').innerHTML='Vào sân <span>→</span>';updateButtons();}
};
function quantity(){return Number($('qty').value);}
$('minus').onclick=()=>{$('qty').value=Math.max(1,Math.min(50,(quantity()||1)-1));};
$('plus').onclick=()=>{$('qty').value=Math.max(1,Math.min(50,(quantity()||1)+1));};
async function order(side){
  if(busy||!game?.can_trade||lastError)return;
  const qty=quantity();if(!Number.isInteger(qty)||qty<1||qty>50){toast('Nhập số nguyên từ 1 đến 50 hợp đồng.');return;}
  busy=true;updateButtons();
  try{game=await api(`/games/${game.id}/orders`,{method:'POST',body:JSON.stringify({side,qty,action_id:crypto.randomUUID()})});lastError='';render();toast(side==='close'?'Đã đóng vị thế.':'Đã khớp lệnh mô phỏng.');}
  catch(e){toast(e.message);}
  finally{busy=false;updateButtons();}
}
$('long').onclick=()=>order('long');$('short').onclick=()=>order('short');$('close').onclick=()=>order('close');
$('finish').onclick=async()=>{if(busy||!game||game.done)return;busy=true;updateButtons();try{game=await api(`/games/${game.id}/finish`,{method:'POST'});render();choosePage('ranking');toast('Đã đóng vị thế và chốt điểm.');}catch(e){toast(e.message);}finally{busy=false;updateButtons();}};
function signed(n){return `${n>0?'+':''}${money(n)}`;}
function setPnl(id,n){$(id).textContent=signed(n);$(id).classList.toggle('up',n>=0);$(id).classList.toggle('down',n<0);}
function row(cells){const tr=document.createElement('tr');for(const cell of cells){const td=document.createElement('td');td.textContent=typeof cell==='object'?cell.text:cell;if(typeof cell==='object')td.className=cell.cls||'';tr.append(td);}return tr;}
function emptyRow(text,span){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=span;td.className='empty-cell';td.textContent=text;tr.append(td);return tr;}
function render(){
  if(!game)return;
  const a=game.account,c=game.candles.at(-1),first=game.candles[0],change=game.price-first.close;
  $('player-label').textContent=game.name;$('avatar').textContent=game.name.charAt(0).toUpperCase();
  $('equity').innerHTML=`${num(a.equity)} <em>₫</em>`;setPnl('pnl',a.net_pnl);$('pnl-percent').textContent=`${(a.net_pnl/1000000).toFixed(2)}% sau phí ${money(a.fees)}`;
  $('available').innerHTML=`${num(a.available)} <em>₫</em>`;$('margin').textContent=`Ký quỹ đang dùng: ${money(a.margin)}`;
  $('timer').textContent=game.done?'ĐÃ CHỐT':game.mode==='live'?'THEO DÕI':`${String(Math.floor(game.seconds_left/60)).padStart(2,'0')}:${String(game.seconds_left%60).padStart(2,'0')}`;
  $('round-caption').textContent=game.done?'Đã chốt điểm':game.mode==='live'?'Nguồn cập nhật mỗi 60 giây':'Mỗi 3 giây mở thêm 1 nến';$('progress').style.width=`${game.progress*100}%`;
  $('price').textContent=points(game.price);$('price-change').textContent=`${change>=0?'+':''}${points(change)} (${(change/first.close*100).toFixed(2)}%)`;$('price-change').className=change>=0?'up':'down';
  $('ohlc').textContent=`O ${points(c.open)}   H ${points(c.high)}   L ${points(c.low)}   C ${points(c.close)}`;
  $('source').textContent=game.market.source;$('data-time').textContent=`Nến hiển thị: ${date(c.time)}`;$('per-margin').textContent=money(game.price*100000*.17);
  $('session-label').textContent=game.done?'Lượt chơi hoàn tất':game.mode==='practice'?'Luyện tập · dữ liệu mẫu':game.mode==='replay'?'Chơi lại · dữ liệu thật':'Theo dõi · nến mới nhất';
  $('session-sub').textContent=`Bộ nến #${game.scenario}${game.market.contract?' · '+game.market.contract:''}`;
  const info=game.done?`Đã chốt lượt chơi: ${signed(a.net_pnl)}. ${a.liquidations?'Có '+a.liquidations+' lần tự đóng do thiếu ký quỹ.':''}`:game.mode==='practice'?'DỮ LIỆU MẪU TỔNG HỢP · Không phải giá thị trường. Điểm luyện tập có bảng riêng.':game.mode==='replay'?`Dữ liệu thật qua vnstock · Chơi lại lịch sử, không phải tick realtime. Bộ nến #${game.scenario}.`:'Giá nến phút gần nhất · nguồn cập nhật mỗi 60 giây · lệnh mô phỏng.';
  notice(lastError||game.warning||info,lastError||game.warning?'error':game.mode==='practice'?'sample':'');
  $('position-count').textContent=`${Math.abs(a.qty)} HĐ`;$('position').replaceChildren();
  if(a.qty)$('position').append(row(['VN30F1M',{text:`${a.qty>0?'LONG':'SHORT'} / ${Math.abs(a.qty)} HĐ`,cls:a.qty>0?'up':'down'},points(a.entry_price),points(game.price),{text:signed(a.unrealized),cls:a.unrealized>=0?'up':'down'},money(a.margin)]));else $('position').append(emptyRow('Chưa có vị thế. Hãy chọn Long hoặc Short để bắt đầu.',6));
  $('trade-count').textContent=`/ ${a.trades.length}`;$('trades').replaceChildren();
  for(const t of a.trades.toReversed())$('trades').append(row([date(Number(t.time),true),{text:`${t.side>0?'MUA':'BÁN'}${t.reason==='margin_call'?' · Ký quỹ':t.reason==='time_up'?' · Hết giờ':''}`,cls:t.side>0?'up':'down'},String(t.qty),points(t.price),{text:signed(t.realized-t.fee),cls:t.realized-t.fee>=0?'up':'down'}]));
  if(!a.trades.length)$('trades').append(emptyRow('Các quyết định của bạn sẽ xuất hiện ở đây.',5));
  renderQuant();drawChart(game.candles);updateButtons();
}
function renderQuant(){
  const q=game?.quant;
  const usable=q?.status==='ready';
  $('quant-scope').textContent=q?.genuine?'Nến đã đóng · dữ liệu thật':'Nến đã đóng · dữ liệu mẫu';
  $('quant-model').textContent=usable?q.model:'ĐANG KIỂM ĐỊNH';
  $('quant-call').className='';$('quant-confidence').className='';
  if(!usable){
    $('quant-call').textContent='Chờ dữ liệu';$('quant-reason').textContent=q?.reason||'Cần nến đã đóng để phân tích.';
    $('quant-confidence').textContent='Chưa đủ mẫu';$('quant-audit').textContent=`${q?.n_rows||0} / ${q?.min_rows||52} mẫu nến liên tục`;
    for(const id of ['quant-forecast','quant-rmse','quant-z'])$(id).textContent='—';
    $('quant-delta').textContent='Chưa đưa gợi ý khi thiếu dữ liệu';$('quant-range').textContent='Vùng sai số 80%: —';
    $('quant-probability').textContent='Ước lượng chiều tăng: —';$('quant-baseline').textContent='So với đoán giá giữ nguyên: —';
    $('quant-cost').textContent='Phí + trượt giá khứ hồi: 0,24 điểm / HĐ';$('quant-skill').textContent='Chưa có kiểm định';$('quant-center').textContent='Vùng giá gần đây: —';
    $('quant-mr').textContent='Mean reversion: chưa kiểm định';$('quant-selection').textContent='Mô hình không dùng nến chưa được mở trong replay.';
    return;
  }
  const disabled=game.done||!game.can_trade||lastError;
  $('quant-call').textContent=disabled?'Chờ · lượt đã dừng':q.suggestion==='long'?'Nghiêng Long':q.suggestion==='short'?'Nghiêng Short':'Chờ · chưa đủ lợi thế';
  $('quant-call').className=disabled||q.suggestion==='wait'?'':q.suggestion==='long'?'up':'down';
  $('quant-reason').textContent=disabled?'Lượt đã kết thúc hoặc dữ liệu giao dịch không sẵn sàng; các số dưới đây chỉ để xem lại.':q.reasons.join(' ');
  $('quant-confidence').textContent=q.confidence==='moderate'?'Vừa · trong mẫu gần đây':'Thấp';
  $('quant-audit').textContent=`${q.n_audit} dự báo kiểm định sau ${q.n_selection} dự báo chọn mô hình`;
  $('quant-forecast').textContent=points(q.forecast_price);
  $('quant-delta').textContent=`${q.delta_points>=0?'+':''}${q.delta_points.toFixed(2)} điểm so với giá đang giao dịch`;
  $('quant-range').textContent=`Vùng sai số 80%: ${points(q.interval80[0])} – ${points(q.interval80[1])}`;
  $('quant-probability').textContent=`Ước lượng tăng: ${(q.probability_up*100).toFixed(0)}% · chưa hiệu chỉnh`;
  $('quant-rmse').textContent=`${q.rmse_points.toFixed(2)} điểm`;
  $('quant-baseline').textContent=`Đoán giá giữ nguyên: ${q.baseline_rmse_points.toFixed(2)} điểm`;
  $('quant-skill').textContent=`Sai số ${q.skill_pct>=0?'giảm':'tăng'} ${Math.abs(q.skill_pct).toFixed(1)}% so với baseline`;
  $('quant-cost').textContent=`Biên còn sau phí: ${q.expected_net_points>=0?'+':''}${q.expected_net_points.toFixed(2)} điểm / HĐ (đã trừ 0,24 điểm)`;
  $('quant-z').textContent=q.z_score===null?'Không phân tán':`${q.z_score>=0?'+':''}${q.z_score.toFixed(2)} σ`;
  $('quant-center').textContent=`Trung bình ${q.z_window} nến: ${points(q.center_price)}`;
  $('quant-mr').textContent=q.mean_reversion_supported?'Quay về: sai số tốt hơn baseline trong mẫu':'Quay về: chưa vượt chuẩn kiểm định';
  $('quant-selection').textContent=`${q.selection_reason} Tính trên ${q.n_candles} nến đã biết, đến ${date(q.data_as_of)}. ${q.genuine?'':'Đang phân tích dữ liệu mẫu; không thể suy ra hiệu quả thị trường.'}`;
}
function drawChart(candles){
  const svg=$('chart').querySelector('svg');$('chart-empty').hidden=candles.length>0;
  const w=$('chart').clientWidth||900,h=Math.max(270,Math.min(370,w*.46)),left=15,right=73,top=12,bottom=43,priceBottom=h-85,volBottom=h-48;
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  const shown=candles.slice(-65);let low=shown.length?Math.min(...shown.map(c=>c.low)):1700,high=shown.length?Math.max(...shown.map(c=>c.high)):1750;
  const spread=Math.max(high-low,2);low-=spread*.1;high+=spread*.1;const y=p=>top+(high-p)/(high-low)*(priceBottom-top);
  const step=(w-left-right)/Math.max(shown.length,45),bar=Math.max(2,step*.55);let parts=[];
  for(let i=0;i<=5;i++){const p=high-(high-low)*i/5,yy=y(p);parts.push(`<line class="grid" x1="${left}" y1="${yy}" x2="${w-right}" y2="${yy}"/><text x="${w-right+13}" y="${yy+4}">${points(p)}</text>`);}
  const maxVol=Math.max(1,...shown.map(c=>c.volume));
  shown.forEach((c,i)=>{const x=left+step*(i+.5),color=c.close>=c.open?'var(--up)':'var(--down)',bodyY=Math.min(y(c.open),y(c.close)),bodyH=Math.max(1.2,Math.abs(y(c.open)-y(c.close)));parts.push(`<line x1="${x}" y1="${y(c.high)}" x2="${x}" y2="${y(c.low)}" stroke="${color}"/><rect x="${x-bar/2}" y="${bodyY}" width="${bar}" height="${bodyH}" fill="${color}"/><rect x="${x-bar/2}" y="${volBottom-c.volume/maxVol*24}" width="${bar}" height="${c.volume/maxVol*24}" fill="${color}" opacity=".22"/>`);if(i%Math.max(1,Math.floor(shown.length/5))===0)parts.push(`<text x="${x}" y="${h-17}" text-anchor="middle">${date(c.time,true)}</text>`);});
  if(shown.length){const c=shown.at(-1),yy=y(c.close),color=c.close>=c.open?'var(--up)':'var(--down)';parts.push(`<line x1="${left}" y1="${yy}" x2="${w-right}" y2="${yy}" stroke="${color}" stroke-width=".7" stroke-dasharray="4 4"/><rect x="${w-right+3}" y="${yy-10}" width="66" height="21" rx="3" fill="${color}"/><text x="${w-right+36}" y="${yy+4}" text-anchor="middle" style="fill:var(--bg)">${points(c.close)}</text>`);}
  parts.push(`<line class="axis" x1="${left}" y1="${h-bottom}" x2="${w-right}" y2="${h-bottom}"/><line class="axis" x1="${w-right}" y1="${top}" x2="${w-right}" y2="${h-bottom}"/>`);svg.innerHTML=parts.join('');
}
async function loadRanking(){try{const scores=await api(`/leaderboard?scenario=${encodeURIComponent(game?.scenario||'')}`);$('ranking').replaceChildren();$('rank-mode').textContent=game?.mode==='practice'?'DỮ LIỆU MẪU':game?.mode==='live'?'KHÔNG CHẤM ĐIỂM':'CÙNG BỘ NẾN';scores.forEach((s,i)=>$('ranking').append(row([String(i+1),s.name,{text:signed(s.pnl),cls:s.pnl>=0?'up':'down'},String(s.trades),date(s.ended)])));if(!scores.length)$('ranking').append(emptyRow('Chưa có điểm trong bộ nến này. Hoàn tất lượt chơi để ghi điểm.',5));}catch(e){toast(e.message);}}
$('refresh-rank').onclick=loadRanking;
$('export').onclick=()=>{if(!game?.account.trades.length){toast('Chưa có lệnh để xuất.');return;}const lines=['time,side,quantity,fill_points,realized_vnd,fee_vnd,reason'];game.account.trades.forEach(t=>lines.push([new Date(Number(t.time)*1000).toISOString(),t.side>0?'BUY':'SELL',t.qty,t.price,t.realized,t.fee,t.reason].join(',')));const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8;'}));const a=document.createElement('a');a.href=url;a.download=`quantik-${game.mode}-${game.scenario}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
async function poll(){if(polling||busy||!game||game.done)return;polling=true;const oldId=game.id;try{const next=await api(`/games/${oldId}`);if(game.id===oldId){const wasDone=game.done;game=next;lastError='';render();if(game.done&&!wasDone){toast(`Hết lượt. Điểm của bạn: ${signed(game.account.net_pnl)}`);loadRanking();}}}catch(e){lastError='Mất kết nối máy chủ: '+e.message;notice(lastError,'error');renderQuant();updateButtons();}finally{polling=false;}}
setInterval(poll,1000);setInterval(()=>{$('clock').textContent=date(Date.now()/1000);},1000);
drawChart([]);
window.addEventListener('resize',()=>drawChart(game?.candles||[]));
if(location.protocol==='file:'){notice('Bạn đang mở HTML trực tiếp. Để chơi: chạy start-local.bat (Windows) hoặc bash start-local.sh (macOS/Linux), rồi mở http://localhost:8080.', 'error');$('start').textContent='Cần chạy server local';$('start').onclick=()=>toast('Chạy start-local.bat trong thư mục gốc repo, rồi mở http://localhost:8080.');return;}
const saved=safeGet('arena_game');if(saved){try{game=await api(`/games/${saved}`);render();$('name').value=game.name;$('mode').value=game.mode;}catch{safeSet('arena_game','');}}

})();
