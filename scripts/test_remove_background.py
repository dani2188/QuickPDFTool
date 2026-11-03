"""Remove Background runs locally (rembg + u2netp): no API key, no external service, no toggle.

Run from the repo root:

    .venv\Scripts\python.exe scripts\test_remove_background.py

Drives the real /remove-background route and checks that:

  - with no API key of any kind, it returns a transparent PNG: the background of a simple subject
    is transparent, the subject stays opaque, and the picture keeps its size;
  - an EXIF-rotated photo comes out upright;
  - a file that is not an image, and a picture over the pixel limit, get a clear 400, not a 500;
  - the model segments a copy capped at BACKGROUND_SEGMENTATION_MAX_DIM, while the PNG keeps the
    photo's own size; and the heavy-job lock makes background removal, Word to PDF and Ghostscript
    take turns (a request that waits too long gets a 503 'busy' page);
  - nothing of the old remove.bg path is left: no toggle, no key lookup, no call to any outside
    service (a network call here would fail the test).

Needs the u2netp model file (downloaded by rembg on first use to ~/.u2net). Exits 1 on any failure.
"""

import io
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from PIL import Image, ImageDraw  # noqa: E402

import app as qt_app  # noqa: E402

qt_app.delete_file_later = lambda *a, **k: None
client = qt_app.app.test_client()
failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


def subject_photo(size=(640, 480), exif_orientation=None):
    """A red apple-like disc on a plain light wall: the easy case every engine should get."""
    img = Image.new("RGB", size, (232, 232, 228))
    d = ImageDraw.Draw(img)
    cx, cy, r = size[0] // 2, size[1] // 2, min(size) // 3
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(200, 30, 30))
    d.ellipse((cx - r // 2, cy - r // 2, cx, cy), fill=(235, 90, 70))
    buf = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        img.save(buf, "JPEG", quality=92, exif=exif)
    else:
        img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


PNG_MAGIC = bytes([0x89]) + b"PNG"


def post(data, name="photo.jpg"):
    return client.post("/remove-background", data={"image": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


# ---- default engine, no API key anywhere
r = post(subject_photo())
check("works with no API key", r.status_code == 200 and r.data.startswith(b"\x89PNG"))
if r.status_code == 200:
    out = Image.open(io.BytesIO(r.data))
    check("output is an RGBA PNG of the same size", out.mode == "RGBA" and out.size == (640, 480))
    a = out.split()[-1]
    check("background corner is transparent", a.getpixel((8, 8)) < 40 and a.getpixel((630, 470)) < 40)
    check("subject centre is opaque", a.getpixel((320, 240)) > 215)
    check("subject colour is kept", out.getpixel((320, 240))[:3][0] > 150)

# EXIF orientation 6 = rotate 90 degrees clockwise to display: a 640x480 file shows as 480x640.
r = post(subject_photo(exif_orientation=6))
check("rotated photo comes out upright", r.status_code == 200 and Image.open(io.BytesIO(r.data)).size == (480, 640))

# ---- bad input
r = post(b"this is not an image")
check("non-image gets a 400 with a message", r.status_code == 400 and "valid image" in r.get_data(as_text=True))
r = client.post("/remove-background", data={}, content_type="multipart/form-data")
check("no file gets a 400", r.status_code == 400)

check("local limit is tighter than the shared one", qt_app.MAX_BACKGROUND_MEGAPIXELS < qt_app.MAX_IMAGE_MEGAPIXELS)
r = post(subject_photo(size=(3000, 2200)))  # 6.6 MP, over the default 6 MP limit
check("picture over the local pixel limit gets a 400 naming it, not a 500",
      r.status_code == 400 and "6-megapixel" in r.get_data(as_text=True))
r = post(subject_photo(size=(2400, 2400)))  # 5.76 MP, just under it
check("picture just under the limit is processed", r.status_code == 200 and r.data.startswith(PNG_MAGIC))

# ---- segmentation runs on a capped copy, the result keeps the photo's own size
seen = []
session = qt_app._background_model()
real_predict = session.predict
session.predict = lambda img, *a, **k: (seen.append(img.size), real_predict(img, *a, **k))[1]
old_dim = qt_app.BACKGROUND_SEGMENTATION_MAX_DIM
qt_app.BACKGROUND_SEGMENTATION_MAX_DIM = 320
r = post(subject_photo(size=(1200, 900)))
qt_app.BACKGROUND_SEGMENTATION_MAX_DIM = old_dim
check("the model is given a copy capped at BACKGROUND_SEGMENTATION_MAX_DIM", seen == [(320, 240)])
out = Image.open(io.BytesIO(r.data))
check("...but the PNG has the original's full size", r.status_code == 200 and out.size == (1200, 900))
check("...and the full-size mask still cuts the subject out",
      out.split()[-1].getpixel((10, 10)) < 40 and out.split()[-1].getpixel((600, 450)) > 215)
seen.clear()
post(subject_photo(size=(640, 480)))
check("a picture already under the cap is not resized", seen == [(640, 480)])
session.predict = real_predict

# ---- heavy jobs take turns (Ghostscript, LibreOffice, the model)
import threading  # noqa: E402

qt_app.HEAVY_JOB_WAIT = 0.3
qt_app.HEAVY_JOB_LOCK.acquire()
try:
    r = post(subject_photo())
    check("background removal waits for the lock, then says the server is busy",
          r.status_code == 503 and "busy" in r.get_data(as_text=True))
    r = client.post("/word-to-pdf", data={"docx": (io.BytesIO(b"x"), "a.docx")}, content_type="multipart/form-data")
    check("Word to PDF also waits for the lock and says the server is busy",
          r.status_code == 503 and "busy" in r.get_data(as_text=True))
finally:
    qt_app.HEAVY_JOB_LOCK.release()

held = []
real_run = qt_app.subprocess.run
qt_app.subprocess.run = lambda *a, **k: held.append(qt_app.HEAVY_JOB_LOCK.locked())
qt_app._run_ghostscript([], "in.pdf", "out.pdf")
qt_app.subprocess.run = real_run
check("Compress PDF's Ghostscript run holds the lock", held == [True])
check("the lock is released afterwards", not qt_app.HEAVY_JOB_LOCK.locked())

started = []
t = threading.Thread(target=lambda: (qt_app.HEAVY_JOB_LOCK.acquire(), started.append(1), qt_app.HEAVY_JOB_LOCK.release()))
qt_app.HEAVY_JOB_LOCK.acquire()
t.start()
t.join(0.2)
check("a second heavy job really waits while one is running", started == [] and t.is_alive())
qt_app.HEAVY_JOB_LOCK.release()
t.join(2)
check("...and runs once the first has finished", started == [1])

# ---- the remove.bg path is really gone
source = open(os.path.join(BASE, "app.py"), encoding="utf-8").read()
check("app.py no longer mentions remove.bg, its key or a toggle",
      not any(w in source.lower() for w in ("remove.bg", "removebg", "remove_bg", "background_remover")))
check("app.py no longer imports requests", "import requests" not in source)
check("no BACKGROUND_REMOVER attribute is left", not hasattr(qt_app, "BACKGROUND_REMOVER"))

import socket  # noqa: E402

real_connect = socket.socket.connect
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network call attempted"))
os.environ["REMOVE_BG_API_KEY"] = "ignored-if-set"
try:
    r = post(subject_photo())
finally:
    socket.socket.connect = real_connect
    del os.environ["REMOVE_BG_API_KEY"]
check("a set REMOVE_BG_API_KEY is ignored and no network connection is made", r.status_code == 200)

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
