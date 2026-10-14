"""Opt-in real-data check. Fails explicitly if genuine data cannot be fetched."""
import json
from backend.provider import Provider

snap = Provider().get()
assert snap['genuine'] is True
assert snap['symbol'] == 'VN30F1M'
assert len(snap['candles']) >= 40
print(json.dumps({k:v for k,v in snap.items() if k != 'candles'}, ensure_ascii=False))
print('Genuine VN30F1M candles:', len(snap['candles']))
