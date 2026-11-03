"""Every tool that takes a PDF must refuse a file that isn't one (QT-033).

Run from the repo root:

    .venv\Scripts\python.exe scripts\test_non_pdf_uploads.py

PyMuPDF opens images and text files as one-page documents, so PDF to PNG, PDF to JPG, PDF to WebP,
Extract Images, Redact PDF, Sign PDF, Add Text and Compress PDF returned a normal result for a JPG,
and Remove Watermark crashed with a 500. The check now lives in one place (a before_request hook in
app.py), so this test finds every POST route that reads a "pdf" or "pdfs" upload by itself, which
means a tool added later is covered too, and checks that each of them:

  - answers a JPG, a text file and a JPG renamed to .pdf with a styled 400 page, never a result
    page, a download or a 500;
  - still accepts a real PDF, including one saved without an extension, one whose name is in capitals,
    one named .jpg, and one with a few bytes before the "%PDF-" header;
  - rejects a whole Merge PDF upload if any one file in it is not a PDF.

Uses Flask's test client with the timers switched off. Exits 1 on any failure.
"""

import inspect
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import fitz  # noqa: E402
from PIL import Image  # noqa: E402

import app as qt_app  # noqa: E402

qt_app.app.config["PROPAGATE_EXCEPTIONS"] = False
qt_app.app.logger.disabled = True
qt_app.delete_file_later = lambda *a, **k: None
client = qt_app.app.test_client()
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{detail}]"))
    if not cond:
        failures.append(name)


buf = io.BytesIO()
Image.new("RGB", (200, 150), (200, 30, 30)).save(buf, "JPEG")
JPG = buf.getvalue()
TXT = b"just some text, not a pdf at all\n" * 20
doc = fitz.open()
doc.new_page().insert_text((72, 72), "Real PDF", fontsize=14)
PDF = doc.tobytes()
doc.close()

# Other form fields some tools need to get past their own checks; irrelevant to the upload check.
EXTRA = {"pages": "1", "rotation": "90", "text": "x", "level": "medium", "target_size": "", "password": "abc123",
         "x": "10", "y": "10", "width": "50", "height": "50", "current_page": "1",
         "left": "10", "right": "10", "top": "10", "bottom": "10"}


def pdf_routes():
    """(route, field) for every POST route that reads a 'pdf' or 'pdfs' upload."""
    found = []
    for rule in sorted(qt_app.app.url_map.iter_rules(), key=lambda r: r.rule):
        if "POST" not in rule.methods or rule.rule.startswith("/static"):
            continue
        code = inspect.getsource(qt_app.app.view_functions[rule.endpoint])
        for field in dict.fromkeys(re.findall(r'request\.files(?:\[|\.get\(|\.getlist\()"(\w+)"', code)):
            if field in ("pdf", "pdfs"):
                found.append((rule.rule, field))
    return found


def post(route, field, data, name):
    return client.post(route, data={field: (io.BytesIO(data), name), **EXTRA}, content_type="multipart/form-data")


routes = pdf_routes()
check("found the PDF-input routes", len(routes) >= 20, len(routes))
named = {r for r, _ in routes}
for must in ("/pdf-to-png", "/pdf-to-jpg", "/pdf-to-webp", "/extract-images", "/redact-pdf", "/sign-pdf",
             "/add-text-to-pdf", "/compress-pdf", "/remove-watermark", "/rotate-pdf", "/merge-pdf"):
    check(f"{must} is among them", must in named)

for route, field in routes:
    for label, data, name in (("a JPG", JPG, "photo.jpg"), ("a text file", TXT, "notes.txt"),
                              ("a JPG renamed to .pdf", JPG, "photo.pdf")):
        r = post(route, field, data, name)
        page = r.get_data(as_text=True) if r.mimetype == "text/html" else ""
        ok = r.status_code == 400 and ("not a PDF" in page or "valid PDF" in page)
        check(f"{route}: {label} gets the 400 'not a PDF' page", ok, f"{r.status_code} {r.mimetype}")

# Real PDFs must still get through the check (they may still fail a route's own rules, but never this one).
for label, name, data in (("a PDF with no extension", "scan", PDF), ("a PDF named in capitals", "SCAN.PDF", PDF),
                          ("a PDF named .jpg", "scan.jpg", PDF),
                          ("a PDF with bytes before the header", "scan.pdf", b"\n\n junk \n" + PDF)):
    r = post("/pdf-to-png", "pdf", data, name)
    check(f"/pdf-to-png accepts {label}", r.status_code == 200 and "converted" in r.get_data(as_text=True), r.status_code)
r = post("/rotate-pdf", "pdf", PDF, "scan.pdf")
check("/rotate-pdf still rotates a real PDF", r.status_code == 200 and r.data.startswith(b"%PDF"))

# Merge PDF: one bad file spoils the upload, with a message naming it.
r = client.post("/merge-pdf", data={"pdfs": [(io.BytesIO(PDF), "a.pdf"), (io.BytesIO(JPG), "b.jpg")]},
                content_type="multipart/form-data")
check("Merge PDF refuses an upload with one non-PDF in it",
      r.status_code == 400 and "b.jpg" in r.get_data(as_text=True))
r = client.post("/merge-pdf", data={"pdfs": [(io.BytesIO(PDF), "a.pdf"), (io.BytesIO(PDF), "b.pdf")]},
                content_type="multipart/form-data")
check("Merge PDF still merges two real PDFs", r.status_code == 200 and r.data.startswith(b"%PDF"))

# The non-PDF tools are untouched.
r = client.post("/jpg-to-pdf", data={"images": (io.BytesIO(JPG), "photo.jpg")}, content_type="multipart/form-data")
check("JPG to PDF still takes a JPG", r.status_code == 200 and r.data.startswith(b"%PDF"), r.status_code)

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
