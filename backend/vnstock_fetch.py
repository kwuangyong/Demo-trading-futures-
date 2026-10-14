"""Invoked only by provider.py. No API keys or raw upstream errors in stdout."""
import json
import os
import importlib
from dotenv import load_dotenv

load_dotenv()
package = os.getenv('VNSTOCK_PACKAGE', 'vnstock')
source = os.getenv('VNSTOCK_SOURCE', 'vci').lower()
if package not in ('vnstock', 'vnstock_data') or source not in ('vci', 'kbs'):
    raise ValueError('Use vnstock/vnstock_data and vci/kbs only.')
Market = importlib.import_module(package).Market

key = os.getenv('VNSTOCK_API_KEY')
if key:
    from vnai import setup_api_key
    setup_api_key(key)

asset = Market().futures('VN30F1M')
frame = asset.ohlcv(length=500, interval='1m', source=source)
contract = frame.attrs.get('symbol') or getattr(frame, 'name', None)
rows = []
for _, row in frame.iterrows():
    rows.append({**{k:float(row[k]) for k in ('open','high','low','close','volume')},
                 'time':row['time'].isoformat()})
print('ARENA_DATA: '+json.dumps(dict(candles=rows, source=package+' / '+str(frame.attrs.get('source', source)),
                                    contract=contract), allow_nan=False))
