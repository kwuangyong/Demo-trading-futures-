"""Fetch genuine candles with an explicit recent window; stdout SDK output stays captured."""
import json
import os
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def history_query(source, today=None):
    # v4.0.9's bar-to-date helper treats 1m like 1D. Explicit dates bypass it.
    today = today or datetime.now(timezone(timedelta(hours=7))).date()
    return dict(start=(today-timedelta(days=14)).isoformat(), end=today.isoformat(),
                length=500, interval='1m', source=source)


def authenticate(library, key):
    if not key:
        return
    # v5 authenticates through vnstock.login; v4 uses vnai. Do not mix them.
    if callable(getattr(library, 'login', None)):
        library.login(key)
    else:
        from vnai import setup_api_key
        if setup_api_key(key) is False:
            raise ValueError('API key registration failed. Check the key/account on vnstocks.com.')


def main():
    load_dotenv(ROOT / '.env')
    package = os.getenv('VNSTOCK_PACKAGE', 'vnstock').strip()
    source = os.getenv('VNSTOCK_SOURCE', 'vci').strip().lower()
    if package not in ('vnstock', 'vnstock_data') or source not in ('vci', 'kbs'):
        raise ValueError('Use vnstock/vnstock_data and vci/kbs only.')
    print('ARENA_STAGE: import', flush=True)
    library = importlib.import_module(package)
    print('ARENA_STAGE: authenticate', flush=True)
    authenticate(library, os.getenv('VNSTOCK_API_KEY', '').strip())
    params = history_query(source)
    print('ARENA_STAGE: history', flush=True)
    print('ARENA_QUERY: '+json.dumps(params), flush=True)
    frame = library.Market().futures('VN30F1M').ohlcv(**params)
    print('ARENA_STAGE: serialize', flush=True)
    contract = frame.attrs.get('symbol') or getattr(frame, 'name', None)
    frame = frame.sort_values('time').tail(500)
    rows = []
    for _, row in frame.iterrows():
        rows.append({**{k:float(row[k]) for k in ('open','high','low','close','volume')},
                     'time':row['time'].isoformat()})
    print('ARENA_DATA: '+json.dumps(dict(candles=rows,
          source=package+' / '+str(frame.attrs.get('source', source)),
          contract=contract), allow_nan=False))


if __name__ == '__main__':
    main()
