"""Check the memory guards added for QT-009.

Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\test_memory_guards.py

Uses Flask's test client with a temporary upload folder and no timers, so it
needs no server. Verifies that:

  - images over MAX_IMAGE_MEGAPIXELS are rejected with a clear 400 page by the
    tools that fully decode them (resize-image, compress-jpg, png-to-pdf),
    exactly at the limit is accepted, and just over it is rejected;
  - a JPEG in jpg-to-pdf is still embedded byte-for-byte whatever its size,
    and a truncated JPEG is still rejected;
  - ordinary PDF pages render at exactly the same size as before, while
    poster-sized pages are scaled down to the pixel budget instead of failing;
  - pdf-to-word rejects PDFs holding too many page-image pixels (a clear 400)
    but still converts an ordinary 2-page scan;
  - pdf-to-text output is unchanged by freeing pdfplumber pages.

For actual memory numbers use scripts/measure_memory.py. Exits 1 on failure.
"""

import io
import os
import re
import sys
import tempfile
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import fitz  # noqa: E402
import numpy as np  # noqa: E402
import pdfplumber  # noqa: E402
from PIL import Image  # noqa: E402

import app as qt_app  # noqa: E402  (the actual hellobrivio Flask app)

tmp = tempfile.mkdtemp(prefix="guards_")
qt_app.UPLOAD_FOLDER = os.path.join(tmp, "uploads")
os.makedirs(qt_app.UPLOAD_FOLDER)
qt_app.delete_file_later = lambda *a, **k: None
client = qt_app.app.test_client()
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


def post(route, field, name, data, **form):
    r = client.post(route, data={field: (io.BytesIO(data), name), **form}, content_type="multipart/form-data")
    return r


def jpeg(w, h):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (120, 160, 200)).save(b, "JPEG", quality=80)
    return b.getvalue()


def png(w, h):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (120, 160, 200)).save(b, "PNG")
    return b.getvalue()


def first_zip_image_size(pdf_bytes, route):
    r = post(route, "pdf", "a.pdf", pdf_bytes)
    assert r.status_code == 200, (route, r.status_code)
    name = re.search(rb'/download-file/([^"]+\.zip)"', r.data).group(1).decode()
    z = zipfile.ZipFile(os.path.join(qt_app.UPLOAD_FOLDER, name))
    return Image.open(io.BytesIO(z.read(z.namelist()[0]))).size


limit = qt_app.MAX_IMAGE_MEGAPIXELS
check("default image limit is 30 MP (unless overridden by the environment)",
      limit == 30 or "MAX_IMAGE_MEGAPIXELS" in os.environ, limit)

# --- images that are fully decoded -------------------------------------------------
huge = jpeg(9000, 9000)  # 81 MP, about 1 MB on disk
r = post("/resize-image", "image", "big.jpg", huge, width="1080", height="1080")
check("resize-image: 81 MP rejected with a clear 400", r.status_code == 400 and b"81 megapixels" in r.data and b"30-megapixel" in r.data, r.status_code)
r = post("/compress-jpg", "images", "big.jpg", huge, level="medium")
check("compress-jpg: 81 MP rejected", r.status_code == 400 and b"megapixels" in r.data, r.status_code)
r = post("/resize-image", "image", "at.jpg", jpeg(6000, 5000), width="1080", height="1080")
check("resize-image: exactly 30 MP accepted", r.status_code == 200, r.status_code)
r = post("/resize-image", "image", "over.jpg", jpeg(6001, 5000), width="1080", height="1080")
check("resize-image: just over 30 MP rejected", r.status_code == 400, r.status_code)
r = post("/png-to-pdf", "images", "big.png", png(7000, 6000))
check("png-to-pdf: 42 MP PNG rejected", r.status_code == 400 and b"megapixels" in r.data, r.status_code)
r = post("/png-to-pdf", "images", "ok.png", png(3000, 2000))
check("png-to-pdf: 6 MP PNG accepted", r.status_code == 200 and r.data[:4] == b"%PDF", r.status_code)

# --- JPEGs are embedded as-is, so size doesn't matter, but corruption still does ------
r = post("/jpg-to-pdf", "images", "big.jpg", huge)
doc = fitz.open(stream=r.data, filetype="pdf") if r.status_code == 200 else None
check("jpg-to-pdf: 81 MP JPEG still embedded byte-for-byte",
      doc is not None and doc.extract_image(doc[0].get_images()[0][0])["image"] == huge, r.status_code)
check("jpg-to-pdf: truncated 81 MP JPEG rejected", post("/jpg-to-pdf", "images", "t.jpg", huge[: len(huge) // 2]).status_code == 400)
small = jpeg(3000, 2000)
check("jpg-to-pdf: truncated 6 MP JPEG rejected", post("/jpg-to-pdf", "images", "t.jpg", small[: len(small) // 2]).status_code == 400)

# --- PDF page renders: unchanged for normal pages, scaled for posters ------------------
for label, size, expected in (("A4", (595, 842), (1190, 1684)), ("Letter", (612, 792), (1224, 1584))):
    d = fitz.open()
    d.new_page(width=size[0], height=size[1])
    got = first_zip_image_size(d.tobytes(), "/pdf-to-jpg")
    check(f"pdf-to-jpg: {label} page is still {expected[0]} x {expected[1]} px", got == expected, got)
budget = qt_app.MAX_PDF_RENDER_MEGAPIXELS * 1_000_000
for label, size in (("A0 poster 2384 x 3370 pt", (2384, 3370)), ("5000 x 5000 pt page", (5000, 5000))):
    d = fitz.open()
    d.new_page(width=size[0], height=size[1])
    for route in ("/pdf-to-jpg", "/pdf-to-png"):
        got = first_zip_image_size(d.tobytes(), route)
        check(f"{route}: {label} scaled to {got[0] * got[1] / 1e6:.1f} MP (budget {budget / 1e6:.0f} MP)",
              got[0] * got[1] <= budget * 1.01 and got[0] > 2000, got)

# --- pdf-to-word -------------------------------------------------------------------------
scan = open(os.path.join(BASE, "static", "examples", "scanned-letter.pdf"), "rb").read()
r = post("/pdf-to-word", "pdf", "scan.pdf", scan)
check("pdf-to-word: ordinary 2-page 200 DPI scan still converts", r.status_code == 200 and r.data[:2] == b"PK", r.status_code)
rng = np.random.default_rng(3)
doc = fitz.open()
for _ in range(9):
    b = io.BytesIO()
    Image.fromarray(rng.integers(0, 256, (2400, 1700, 3), dtype=np.uint8)).save(b, "JPEG", quality=70)
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=b.getvalue())
r = post("/pdf-to-word", "pdf", "big.pdf", doc.tobytes())
check("pdf-to-word: 9 pages x 4 MP of scans rejected with a clear 400",
      r.status_code == 400 and b"megapixels" in r.data and b"Compress PDF" in r.data, r.status_code)

# --- pdf-to-text unchanged by freeing pages ----------------------------------------------
src = fitz.open(os.path.join(BASE, "static", "examples", "text-report.pdf"))
doc = fitz.open()
for _ in range(5):
    doc.insert_pdf(src)
data = doc.tobytes()
expected = ""
with pdfplumber.open(io.BytesIO(data)) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        expected += (text + "\n\n") if text else ""
r = post("/pdf-to-text", "pdf", "t.pdf", data)
check("pdf-to-text: output identical to the plain pdfplumber loop (ignoring Windows CRLF)",
      r.status_code == 200 and r.data.decode("utf-8").replace("\r\n", "\n") == expected)

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
