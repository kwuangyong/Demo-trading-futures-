"""Run with the repository virtual environment; optional --open opens a local browser."""
import argparse
import os
import threading
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

load_dotenv(Path(__file__).parent / '.env')
parser = argparse.ArgumentParser()
parser.add_argument('--open', action='store_true')
parser.add_argument('--host', default=os.getenv('HOST', '127.0.0.1'))
parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '8080')))
args = parser.parse_args()
if args.open:
    threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{args.port}')).start()
uvicorn.run('backend.server:app', host=args.host, port=args.port, workers=1)
