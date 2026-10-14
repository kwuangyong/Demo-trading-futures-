"""Fetch genuine VN30F1M candles in a killable subprocess; never invent fallback prices."""
import json
import math
import subprocess
import sys
import importlib.util
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from .diagnostics import safe_detail

ROOT = Path(__file__).resolve().parents[1]


def normalize(rows):
    out = {}
    for row in rows:
        stamp = datetime.fromisoformat(str(row['time']).replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            from zoneinfo import ZoneInfo
            stamp = stamp.replace(tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))
        prices = [float(row[k]) for k in ('open', 'high', 'low', 'close')]
        volume = float(row.get('volume', 0))
        if not all(math.isfinite(p) and p > 0 for p in prices) or not math.isfinite(volume) or volume < 0:
            raise ValueError('Invalid candle')
        o, h, l, c = prices
        if h < max(o, c) or l > min(o, c) or l > h:
            raise ValueError('Invalid OHLC bounds')
        ts = int(stamp.timestamp())
        out[ts] = dict(time=ts, open=o, high=h, low=l, close=c, volume=int(volume))
    values = sorted(out.values(), key=lambda r: r['time'])
    if len(values) < 40:
        raise ValueError('Nguồn trả quá ít nến; cần ít nhất 40 nến phút.')
    return values[-500:]


class Provider:
    def __init__(self):
        self.lock = threading.Lock()
        self.snapshot = None
        self.next_fetch = 0
        self.error = None

    def get(self):
        with self.lock:
            if time.monotonic() >= self.next_fetch:
                self.next_fetch = time.monotonic()+60
                try:
                    package = os.getenv('VNSTOCK_PACKAGE', 'vnstock')
                    if package not in ('vnstock', 'vnstock_data'):
                        raise RuntimeError('VNSTOCK_PACKAGE phải là vnstock hoặc vnstock_data.')
                    if importlib.util.find_spec(package) is None:
                        raise RuntimeError(f'Chưa cài {package}. Cài requirements.txt rồi khởi động lại server để dùng dữ liệu thật.')
                    result = subprocess.run([sys.executable, '-m', 'backend.vnstock_fetch'],
                                            cwd=ROOT, capture_output=True, text=True, timeout=35,
                                            encoding='utf-8', errors='replace',
                                            env={**os.environ, 'PYTHONIOENCODING':'utf-8', 'PYTHONUTF8':'1'})
                    # Library notices can precede JSON. Accept only our final marked line.
                    payload = next((line[12:] for line in reversed(result.stdout.splitlines())
                                    if line.startswith('ARENA_DATA: ')), None)
                    if result.returncode or payload is None:
                        detail = safe_detail(result.stderr)
                        raise RuntimeError('vnstock không trả dữ liệu. '+detail+' Chạy check-vnstock.bat để kiểm tra.')
                    raw = json.loads(payload)
                    rows = normalize(raw['candles'])
                    self.snapshot = dict(symbol='VN30F1M', source=raw['source'], interval='1m',
                                         contract=raw.get('contract'), candles=rows,
                                         fetched_at=datetime.now(timezone.utc).isoformat(),
                                         data_as_of=rows[-1]['time'], genuine=True)
                    self.error = None
                except (Exception, SystemExit) as exc:
                    self.error = 'Nguồn giá quá thời gian chờ.' if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
            if not self.snapshot:
                raise ValueError(self.error or 'Chưa tải được dữ liệu vnstock.')
            return {**self.snapshot, 'error': self.error, 'cached': bool(self.error)}


def fresh(snapshot):
    age = time.time()-snapshot['data_as_of']
    return snapshot.get('genuine') and not snapshot.get('error') and 0 <= age <= 120
