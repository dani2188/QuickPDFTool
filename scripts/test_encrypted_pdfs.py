"""Password-protected PDFs get a clear message on every PDF tool (QT-030).

Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\test_encrypted_pdfs.py

Uses Flask's test client with a temporary upload folder and no timers, so it
needs no server. For every route that takes a PDF it checks that:

  - a PDF that needs a password to open gets a styled 400 page that says it is
    password-protected and links to Unlock PDF (never a 500, and never the
    misleading "not a valid PDF");
  - a PDF with only an owner password (it opens freely, with restrictions)
    still works exactly as before;
  - Unlock PDF and Compress PDF are not blocked, and Unlock PDF still unlocks;
  - damaged "PDF" files are still reported the way each route did before.

Exits 1 on any failure.
"""

import io
import os
import re
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import fitz  # noqa: E402
from PIL import Image  # noqa: E402
from PyPDF2 import PdfReader, PdfWriter  # noqa: E402

import app as qt_app  # noqa: E402  (the actual hellobrivio Flask app)

qt_app.app.config["PROPAGATE_EXCEPTIONS"] = False
qt_app.app.logger.disabled = True
tmp = tempfile.mkdtemp(prefix="encrypted_")
qt_app.UPLOAD_FOLDER = os.path.join(tmp, "uploads")
os.makedirs(qt_app.UPLOAD_FOLDER)
qt_app.delete_file_later = lambda *a, **k: None
client = qt_app.app.test_client()
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


doc = fitz.open()
for i in range(3):
    doc.new_page().insert_text((72, 72), f"Page {i + 1}")
plain = doc.tobytes()


def encrypt(user, owner):
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(plain)).pages:
        writer.add_page(page)
    writer.encrypt(user_password=user, owner_password=owner)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


locked = encrypt("secret", "secret")
owner_only = encrypt("", "owner-secret")
signature = io.BytesIO()
Image.new("RGBA", (100, 40), (0, 0, 0, 255)).save(signature, "PNG")

# route, upload field, extra form fields. Every PDF-taking route except Unlock PDF and Compress PDF.
ROUTES = [
    ("/pdf-to-png", "pdf", {}), ("/pdf-to-jpg", "pdf", {}), ("/pdf-to-webp", "pdf", {}),
    ("/extract-images", "pdf", {}), ("/pdf-to-text", "pdf", {}), ("/pdf-to-word", "pdf", {}),
    ("/pdf-to-excel", "pdf", {}), ("/split-pdf", "pdf", {}), ("/rotate-pdf", "pdf", {"rotation": "90"}),
    ("/delete-pdf-pages", "pdf", {"pages": "1"}),
    ("/crop-pdf", "pdf", {"left": "10", "right": "10", "top": "10", "bottom": "10"}),
    ("/add-page-numbers", "pdf", {}), ("/add-watermark", "pdf", {"text": "DRAFT"}),
    ("/remove-watermark", "pdf", {}), ("/protect-pdf", "pdf", {"password": "x"}), ("/redact-pdf", "pdf", {}),
    ("/add-text-to-pdf", "pdf", {}), ("/merge-pdf", "pdfs", {}), ("/sign-pdf", "pdf", {"__signature": True}),
]


def post(route, field, extra, data, name="t.pdf"):
    form = dict(extra)
    files = {field: (io.BytesIO(data), name)}
    if form.pop("__signature", False):
        files["signature"] = (io.BytesIO(signature.getvalue()), "sig.png")
    return client.post(route, data={**form, **files}, content_type="multipart/form-data")


for route, field, extra in ROUTES:
    r = post(route, field, extra, locked, name="report.pdf")
    text = r.get_data(as_text=True)
    ok = (r.status_code == 400 and "password-protected" in text and 'href="/unlock-pdf"' in text
          and "valid PDF" not in text)
    check(f"{route}: locked PDF -> 400 with 'password-protected' and an Unlock PDF link", ok, r.status_code)
    r = post(route, field, extra, owner_only)
    # pdf-to-excel answers 400 "no table found" for this table-less sample, which is its normal behaviour.
    ok = r.status_code in (200, 302) or (route == "/pdf-to-excel" and r.status_code == 400
                                         and "password" not in r.get_data(as_text=True))
    check(f"{route}: owner-password-only PDF still works", ok, r.status_code)

r = post("/pdf-to-png", "pdf", {}, locked, name="my report (final).pdf")
check("message names the file", "my_report_final_.pdf" in r.get_data(as_text=True)
      or "my_report_final.pdf" in r.get_data(as_text=True), re.sub(r"\s+", " ", r.get_data(as_text=True))[-250:])

# Merge: one locked file among several is rejected, and says which.
r = client.post("/merge-pdf", data={"pdfs": [(io.BytesIO(plain), "fine.pdf"), (io.BytesIO(locked), "locked.pdf")]},
                content_type="multipart/form-data")
check("merge-pdf: one locked file among two is rejected and named",
      r.status_code == 400 and "locked.pdf" in r.get_data(as_text=True) and "fine.pdf" not in
      re.sub(r"<[^>]+>", " ", r.get_data(as_text=True).split("<main")[1]), r.status_code)

# Not blocked: Unlock PDF, which exists to open these, and Compress PDF.
r = post("/unlock-pdf", "pdf", {"password": "secret"}, locked)
check("unlock-pdf: correct password still unlocks it", r.status_code == 200 and r.data[:4] == b"%PDF", r.status_code)
unlocked = fitz.open(stream=r.data, filetype="pdf")
check("unlock-pdf: the result opens without a password", unlocked.needs_pass == 0 and len(unlocked) == 3)
r = post("/unlock-pdf", "pdf", {"password": "wrong"}, locked)
check("unlock-pdf: wrong password still says 'Incorrect password.'", r.status_code == 400 and "Incorrect password" in r.get_data(as_text=True), r.status_code)
r = post("/compress-pdf", "pdf", {"level": "medium"}, locked)
check("compress-pdf: not intercepted (still its own processing flow)", r.status_code == 200 and "password-protected, so we can't open" not in r.get_data(as_text=True), r.status_code)

# Damaged files keep their old behaviour, and the two-step tools' second step is untouched.
r = post("/pdf-to-png", "pdf", {}, b"this is not a pdf at all", name="broken.pdf")
check("a damaged .pdf still gets the 'valid PDF' message, not the password one",
      r.status_code == 400 and "valid PDF" in r.get_data(as_text=True) and "password" not in r.get_data(as_text=True), r.status_code)
r = client.post("/redact-pdf", data={"existing_file": "../app.py"}, content_type="multipart/form-data")
check("a step-2 post with no upload is not affected (still 'File missing or expired')",
      r.status_code == 400 and "File missing or expired" in r.get_data(as_text=True), r.status_code)

# An ordinary PDF is unaffected, and so are the page's normal buttons.
r = post("/pdf-to-png", "pdf", {}, plain)
check("an ordinary PDF converts as before", r.status_code == 200 and "page(s) converted" in r.get_data(as_text=True), r.status_code)
page = client.get("/pdf-to-png").get_data(as_text=True)
check("GET pages are unaffected", "Convert to PNG" in page)

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
