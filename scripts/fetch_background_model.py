"""Download the u2netp model used by Remove Background into the project folder.

Run from the repo root (render.yaml runs it in the build step):

    .venv\Scripts\python.exe scripts\fetch_background_model.py

Without this, rembg downloads the 4.6 MB model from GitHub during the first Remove Background
request after every deploy, which delays that visitor and fails if GitHub is unreachable. app.py
looks for the file in the same place (.u2net/ next to app.py, unless U2NET_HOME is set).
Exits 1 if the model can't be downloaded or doesn't load.
"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("U2NET_HOME", os.path.join(BASE, ".u2net"))
os.environ.setdefault("NUMBA_DISABLE_JIT", "1")  # rembg -> pymatting would otherwise JIT-compile on import

from rembg.sessions.u2netp import U2netpSession  # noqa: E402

try:
    path = U2netpSession.download_models()
    size = os.path.getsize(path)
    if size < 1_000_000:
        raise RuntimeError(f"{path} is only {size} bytes")
except Exception as e:  # noqa: BLE001
    print("Could not fetch the u2netp model:", e)
    sys.exit(1)
print(f"u2netp model ready: {path} ({size / 1_000_000:.1f} MB)")
