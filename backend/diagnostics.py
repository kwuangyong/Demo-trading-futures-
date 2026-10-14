"""Local provider check. Never print the API key or unfiltered SDK output."""
import importlib.util
import json
import os
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def safe_detail(output):
    text = output or ''
    key = os.getenv('VNSTOCK_API_KEY', '').strip()
    if key:
        for value in (key, quote(key, safe='')):
            text = text.replace(value, '[REDACTED]')
    text = re.sub(r'(?i)(api[_-]?key|access[_-]?token|authorization|password)(["\s]*[:=]["\s]*)([^\s&"\'<>]+)',
                  r'\1\2[REDACTED]', text)
    text = re.sub(r'(?i)bearer\s+[^\s"\']+', 'Bearer [REDACTED]', text)
    # The last exception line is sufficient; don't dump traceback/local paths.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1][:500] if lines else 'No error detail returned by the library.'


def main():
    load_dotenv(ROOT / '.env')
    package = os.getenv('VNSTOCK_PACKAGE', 'vnstock')
    source = os.getenv('VNSTOCK_SOURCE', 'vci')
    print('Python:', sys.version.split()[0])
    print('Environment file:', 'FOUND' if (ROOT / '.env').is_file() else 'NOT FOUND')
    print('API key:', 'SET (hidden)' if os.getenv('VNSTOCK_API_KEY', '').strip() else 'NOT SET')
    print('Package / source:', package, '/', source)
    for name in ('vnstock', 'vnstock_data', 'vnai'):
        try:
            print(name+':', version(name))
        except PackageNotFoundError:
            print(name+': NOT INSTALLED')
    if package not in ('vnstock', 'vnstock_data') or source.lower() not in ('vci', 'kbs'):
        print('FAIL: Invalid package/source setting in .env.')
        return 1
    if importlib.util.find_spec(package) is None:
        print('FAIL: Install requirements.txt, then restart the server.')
        return 1
    print('Checking genuine VN30F1M 1-minute history (maximum 35 seconds)...', flush=True)
    try:
        result = subprocess.run([sys.executable, '-m', 'backend.vnstock_fetch'], cwd=ROOT,
                                capture_output=True, text=True, timeout=35, encoding='utf-8', errors='replace',
                                env={**os.environ, 'PYTHONIOENCODING':'utf-8', 'PYTHONUTF8':'1'})
    except subprocess.TimeoutExpired:
        print('FAIL: Provider timed out after 35 seconds.')
        return 1
    payload = next((line[12:] for line in reversed(result.stdout.splitlines())
                    if line.startswith('ARENA_DATA: ')), None)
    if result.returncode or payload is None:
        print('FAIL: vnstock fetch failed, exit code:', result.returncode)
        print('Error:', safe_detail(result.stderr))
        return 1
    try:
        from .provider import normalize
        raw = json.loads(payload)
        candles = normalize(raw['candles'])
    except Exception as exc:
        print('FAIL: Invalid provider data:', safe_detail(str(exc)))
        return 1
    from datetime import datetime
    from zoneinfo import ZoneInfo
    latest = datetime.fromtimestamp(candles[-1]['time'], ZoneInfo('Asia/Ho_Chi_Minh'))
    print('PASS: Genuine data fetched. Candles:', len(candles))
    print('Source:', raw['source'])
    print('Last candle (Vietnam):', latest.isoformat())
    print('Last close (points):', candles[-1]['close'])
    print('Replay can use this history outside trading hours. No synthetic fallback was used.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
