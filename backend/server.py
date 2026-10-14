import hashlib
import json
import os
import random
import secrets
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import account, flatten, metrics, risk_check, trade
from .provider import Provider, fresh
from .quant import analyze as analyze_quant, at_quote

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATA = Path(os.getenv('ARENA_DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(DATA / 'arena.sqlite', check_same_thread=False)
db.execute('PRAGMA journal_mode=WAL')
db.execute('CREATE TABLE IF NOT EXISTS games (id TEXT PRIMARY KEY, owner TEXT, body TEXT)')
db.execute('CREATE TABLE IF NOT EXISTS scores (game_id TEXT PRIMARY KEY, scenario TEXT, name TEXT, mode TEXT, pnl INTEGER, trades INTEGER, ended REAL)')
db.commit()
lock = threading.RLock()
provider = Provider()
app = FastAPI(title='QuanTik Futures Arena', docs_url='/api/docs')


class Start(BaseModel):
    name: str = Field(default='Trader', min_length=1, max_length=24)
    mode: Literal['replay', 'live', 'practice'] = 'replay'


class Order(BaseModel):
    side: Literal['long', 'short', 'close']
    qty: int = Field(default=1, ge=1, le=50, strict=True)
    action_id: str = Field(min_length=8, max_length=80)


def practice():
    rng = random.Random(3030)
    rows = []
    price = 1800.0
    for i in range(120):
        opening = price
        price = round(max(100, price+rng.uniform(-2.4, 2.4)+.35), 1)
        rows.append(dict(time=1760320800+i*60, open=opening, close=price,
                         high=round(max(opening, price)+rng.uniform(.1, 1), 1),
                         low=round(min(opening, price)-rng.uniform(.1, 1), 1),
                         volume=rng.randint(200, 2000)))
    return dict(symbol='VN30F1M', source='MẪU TỔNG HỢP · không phải dữ liệu thật',
                candles=rows, data_as_of=rows[-1]['time'], genuine=False,
                interval='1m', error=None, cached=False, contract=None)


def save(g):
    db.execute('INSERT OR REPLACE INTO games VALUES (?, ?, ?)', (g['id'], g['owner'], json.dumps(g)))
    if g['done'] and g['mode'] != 'live':
        db.execute('INSERT OR IGNORE INTO scores VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (g['id'], g['scenario'], g['name'], g['mode'],
                    g['account']['cash']-100_000_000, len(g['account']['trades']), time.time()))
    db.commit()


def load(gid, request):
    row = db.execute('SELECT owner, body FROM games WHERE id=?', (gid,)).fetchone()
    if not row or row[0] != request.cookies.get('arena_owner'):
        raise HTTPException(404, 'Không tìm thấy lượt chơi trong trình duyệt này.')
    return json.loads(row[1])


def finish(g, reason='finish'):
    candle = g['market']['candles'][g['cursor']]
    flatten(g['account'], round(candle['close']*10), str(candle['time']), reason)
    g['done'] = True
    g['end_reason'] = reason


def advance(g, live=None, now=None):
    if g['done']:
        return
    now = time.time() if now is None else now
    if g['mode'] == 'live':
        if live:
            g['market'] = live
        g['cursor'] = len(g['market']['candles'])-1
        c = g['market']['candles'][g['cursor']]
        risk_check(g['account'], round(c['close']*10), str(c['time']))
        return
    target = min(len(g['market']['candles'])-1, 29+int(max(0, now-g['started'])/3))
    for i in range(g['cursor']+1, target+1):
        c = g['market']['candles'][i]
        risk_check(g['account'], round(c['close']*10), str(c['time']))
    g['cursor'] = target
    if target == len(g['market']['candles'])-1:
        finish(g, 'time_up')


def public(g):
    market = g['market']
    candle = market['candles'][g['cursor']]
    mark = round(candle['close']*10)
    is_live = g['mode'] == 'live'
    active = not g['done'] and (not is_live or fresh(market))
    quant_history = g.get('quant_history', []) + market['candles'][:g['cursor']+1]
    if is_live:
        fetched = datetime.fromisoformat(market['fetched_at']).timestamp() if market.get('fetched_at') else time.time()
        quant_history = [c for c in quant_history if c['time']+60 <= fetched]
    quant = {**at_quote(analyze_quant(quant_history),mark/10), 'genuine':market.get('genuine',False),
             'scope':'live_closed_candles' if is_live else 'revealed_replay_candles'}
    return dict(id=g['id'], name=g['name'], mode=g['mode'], scenario=g['scenario'],
                done=g['done'], end_reason=g.get('end_reason'), can_trade=active,
                seconds_left=None if is_live else max(0, round(g['deadline']-time.time())),
                progress=(g['cursor']-29)/max(1, len(market['candles'])-30) if not is_live else 0,
                account={**g['account'], **metrics(g['account'], mark), 'entry_price':g['account']['entry']/10},
                market={k:v for k,v in market.items() if k != 'candles'},
                candles=market['candles'][:g['cursor']+1][-100:], price=mark/10,
                quant=quant,
                warning=market.get('error') or ('Giá nến đã cũ hoặc ngoài giờ giao dịch. Dùng chế độ chơi lại.' if is_live and not fresh(market) else None))


def live_snapshot(g):
    if g['mode'] != 'live' or g['done']:
        return None
    try:
        return provider.get()
    except ValueError as exc:
        return {**g['market'], 'error': str(exc), 'cached': True}


@app.get('/api/health')
def health():
    return dict(ok=True, symbol='VN30F1M')


@app.get('/api/market')
def market_status():
    try:
        snap = provider.get()
        return {k:v for k,v in snap.items() if k != 'candles'} | {'fresh':fresh(snap), 'count':len(snap['candles'])}
    except ValueError as exc:
        raise HTTPException(503, str(exc))


@app.post('/api/games')
def start(body: Start, request: Request, response: Response):
    try:
        snap = practice() if body.mode == 'practice' else provider.get()
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    if body.mode == 'live' and not fresh(snap):
        raise HTTPException(409, 'Chưa có nến phút mới trong 120 giây. Hãy chơi lại dữ liệu thật ngoài giờ giao dịch.')
    owner = request.cookies.get('arena_owner') or secrets.token_urlsafe(32)
    response.set_cookie('arena_owner', owner, httponly=True, samesite='strict', max_age=604800,
                        secure=request.url.scheme == 'https')
    quant_history = []
    if body.mode != 'live':
        fetched = datetime.fromisoformat(snap['fetched_at']).timestamp() if snap.get('fetched_at') else time.time()
        closed = [c for c in snap['candles'] if not snap.get('genuine') or c['time']+60 <= fetched]
        if len(closed)<40:
            raise HTTPException(409, 'Cần ít nhất 40 nến đã đóng để chơi lại.')
        # Warmup precedes the game. It contains no unrevealed future candles.
        quant_history = closed[:-90][-120:]
        snap = {**snap, 'candles':closed[-90:]}
    now = time.time()
    scenario = hashlib.sha256(json.dumps(snap['candles'], sort_keys=True).encode()).hexdigest()[:12]
    g = dict(id=secrets.token_urlsafe(20), owner=owner, name=body.name.strip() or 'Trader', mode=body.mode,
             market=snap, account=account(), started=now, deadline=now+3*(len(snap['candles'])-30),
             cursor=len(snap['candles'])-1 if body.mode == 'live' else 29, done=False,
             scenario=scenario, actions=[], quant_history=quant_history)
    with lock:
        # One active game per browser; changing a mode closes its previous account.
        for (raw,) in db.execute('SELECT body FROM games WHERE owner=?', (owner,)).fetchall():
            previous = json.loads(raw)
            if not previous['done']:
                advance(previous)
                finish(previous, 'new_game')
                save(previous)
        save(g)
    return public(g)


@app.get('/api/games/{gid}')
def get_game(gid: str, request: Request):
    with lock:
        initial = load(gid, request)
    live = live_snapshot(initial)
    with lock:
        g = load(gid, request)
        advance(g, live)
        save(g)
        return public(g)


@app.post('/api/games/{gid}/orders')
def order(gid: str, body: Order, request: Request):
    with lock:
        initial = load(gid, request)
    live = live_snapshot(initial)
    with lock:
        g = load(gid, request)
        advance(g, live)
        if body.action_id in g['actions']:
            save(g)
            return public(g)
        if not public(g)['can_trade']:
            save(g)
            raise HTTPException(409, 'Lượt chơi đã kết thúc hoặc dữ liệu đã cũ.')
        candle = g['market']['candles'][g['cursor']]
        try:
            if body.side == 'close':
                flatten(g['account'], round(candle['close']*10), str(candle['time']))
            else:
                trade(g['account'], 1 if body.side == 'long' else -1, body.qty,
                      round(candle['close']*10), str(candle['time']))
        except ValueError as exc:
            save(g)
            raise HTTPException(400, str(exc))
        g['actions'].append(body.action_id)
        save(g)
        return public(g)


@app.post('/api/games/{gid}/finish')
def end_game(gid: str, request: Request):
    with lock:
        g = load(gid, request)
        advance(g)
        if not g['done']:
            finish(g)
        save(g)
        return public(g)


@app.get('/api/leaderboard')
def leaderboard(scenario: str = ''):
    with lock:
        rows = db.execute('SELECT name, mode, pnl, trades, ended FROM scores WHERE scenario=? ORDER BY pnl DESC, ended ASC LIMIT 10', (scenario,)).fetchall()
    return [dict(name=r[0], mode=r[1], pnl=r[2], trades=r[3], ended=r[4]) for r in rows]


app.mount('/', StaticFiles(directory=ROOT / 'web', html=True), name='web')
