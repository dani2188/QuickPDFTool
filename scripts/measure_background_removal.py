"""Measure the local Remove Background engine (rembg + u2netp): peak memory and time per image size.

Run from the repo root, with a photo to scale up/down as the test subject:

    .venv\Scripts\python.exe scripts\measure_background_removal.py path\to\photo.jpg
    .venv\Scripts\python.exe scripts\measure_background_removal.py photo.jpg --runs 3 --threads 1

Every run happens in a FRESH child process that imports the real Flask app and posts the image to
the real /remove-background route, so the first request pays for importing rembg and loading the
model, exactly like the first visitor after a restart. The same child then repeats the request
with the model already loaded ("warm"), which is what every later visitor gets. Reported per
size: the app's memory before any request, peak memory (Windows: PeakWorkingSetSize, Linux:
VmHWM), seconds for the cold and the warm request, and the memory left afterwards.

Sizes: small 0.5 MP, medium 2 MP, cap 6 MP (the tool's limit), large 12 MP (a phone photo), limit 30 MP.
--threads N sets OMP_NUM_THREADS for the child, to imitate an instance with fewer CPUs.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
MB = 1024 * 1024

SIZES = {"small": (800, 600), "medium": (1600, 1200), "cap": (3000, 2000), "large": (4000, 3000), "limit": (6000, 5000)}


def child(path):
    """Runs inside the fresh process: one cold and one warm request, JSON on the last line."""
    sys.path.insert(0, BASE)
    from measure_memory import memory_now

    import app as qt_app

    qt_app.delete_file_later = lambda *a, **k: None
    qt_app.UPLOAD_FOLDER = tempfile.mkdtemp(prefix="bgbench_")
    client = qt_app.app.test_client()
    data = open(path, "rb").read()
    out = {"before_mb": memory_now()[0] / MB}
    for label in ("cold", "warm"):
        t = time.perf_counter()
        r = client.post("/remove-background", data={"image": (io.BytesIO(data), "photo.jpg")},
                        content_type="multipart/form-data")
        out[label + "_s"] = time.perf_counter() - t
        out[label + "_status"] = r.status_code
        out[label + "_bytes"] = len(r.data)
        rss, peak = memory_now()
        out[label + "_peak_mb"] = peak / MB
        out["after_" + label + "_mb"] = rss / MB
    print("RESULT " + json.dumps(out))


def main():
    args = sys.argv[1:]
    if args and args[0] == "--child":
        return child(args[1])
    if not args or args[0].startswith("--"):
        sys.exit(__doc__)
    source = args[0]
    runs = int(args[args.index("--runs") + 1]) if "--runs" in args else 3
    threads = args[args.index("--threads") + 1] if "--threads" in args else None
    only = [a for a in args[1:] if a in SIZES]

    from PIL import Image

    folder = tempfile.mkdtemp(prefix="bgbench_in_")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if threads:
        env["OMP_NUM_THREADS"] = threads
    print(f"source {source}; {runs} runs per size; threads={threads or 'all'}")
    for name, (w, h) in SIZES.items():
        if only and name not in only:
            continue
        sample = os.path.join(folder, f"{name}.jpg")
        with Image.open(source) as im:
            im.convert("RGB").resize((w, h), Image.LANCZOS).save(sample, quality=90)
        size_kb = os.path.getsize(sample) / 1024
        rows = []
        for _ in range(runs):
            p = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", sample],
                               capture_output=True, text=True, env=env, cwd=BASE)
            line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
            if not line:
                print(f"{name}: run failed\n{p.stderr[-600:]}")
                continue
            rows.append(json.loads(line[0][7:]))
        print(f"\n{name}  {w}x{h} ({w * h / 1e6:.1f} MP, {size_kb:.0f} KB JPEG)")
        print("  run  status  before   peak(cold)  cold s   peak(warm)  warm s   after")
        for i, r in enumerate(rows, 1):
            print(f"  {i:>3}  {r['cold_status']}/{r['warm_status']}  {r['before_mb']:6.0f}MB {r['cold_peak_mb']:8.0f}MB "
                  f"{r['cold_s']:7.1f} {r['warm_peak_mb']:10.0f}MB {r['warm_s']:7.1f}  {r['after_warm_mb']:6.0f}MB")
        if rows:
            print(f"  max peak {max(r['warm_peak_mb'] for r in rows):.0f} MB; "
                  f"median cold {sorted(r['cold_s'] for r in rows)[len(rows) // 2]:.1f} s; "
                  f"median warm {sorted(r['warm_s'] for r in rows)[len(rows) // 2]:.1f} s")


if __name__ == "__main__":
    main()
