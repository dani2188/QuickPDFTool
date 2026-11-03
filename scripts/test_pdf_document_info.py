"""Rotate PDF and Add Watermark must keep bookmarks and document info, like Compress PDF does.

Run from the repo root:

    .venv\Scripts\python.exe scripts\test_pdf_document_info.py

Both tools rebuilt the PDF with PyPDF2 and dropped the title, author, subject, keywords and the
whole bookmark tree. Drives the real /rotate-pdf and /add-watermark routes with a PDF that has nested bookmarks and
metadata, and checks that the rotated and watermarked files keep them (the same bookmark titles,
nesting and target pages), that the tools still do their own job,
and that PDFs with no bookmarks, no metadata or a broken bookmark still work. Exits 1 on any
failure.
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

import fitz  # noqa: E402
from PyPDF2 import PdfReader, PdfWriter  # noqa: E402

import app as qt_app  # noqa: E402

client = qt_app.app.test_client()
failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


TOC = [[1, "Introduction", 1], [2, "Background", 2], [2, "Scope", 2], [1, "Résumé 摘要", 3], [2, "Details", 4], [1, "Appendix", 5]]
META = {"title": "Quarterly Report", "author": "Ana Silva", "subject": "Finance", "keywords": "q3, revenue"}


def make_pdf(toc=True, meta=True):
    d = fitz.open()
    for i in range(5):
        d.new_page(width=612, height=792).insert_text((72, 72), f"Page {i + 1}", fontsize=14)
    if toc:
        d.set_toc(TOC)
    if meta:
        d.set_metadata(META)
    data = d.tobytes()
    d.close()
    return data


def post(route, pdf, **data):
    return client.post(route, data={"pdf": (io.BytesIO(pdf), "report.pdf"), **data}, content_type="multipart/form-data")


def info(pdf):
    with fitz.open(stream=pdf, filetype="pdf") as d:
        return {k: d.metadata.get(k) for k in META}, d.get_toc(), [p.rotation for p in d], d.page_count


def keeps(label, pdf):
    meta, toc, _, pages = info(pdf)
    check(f"{label}: title, author, subject and keywords kept", meta == META)
    check(f"{label}: bookmarks kept with titles, nesting and pages", toc == TOC)
    check(f"{label}: no pages lost", pages == 5)


SOURCE = make_pdf()

r = post("/rotate-pdf", SOURCE, rotation="90")
check("rotate: accepted", r.status_code == 200)
keeps("rotate", r.data)
check("rotate: every page is rotated", info(r.data)[2] == [90] * 5)

r = post("/add-watermark", SOURCE, text="CONFIDENTIAL")
check("watermark: accepted", r.status_code == 200)
keeps("watermark", r.data)
with fitz.open(stream=r.data, filetype="pdf") as d:
    check("watermark: still drawn on every page", all(any(s["size"] > 30 for s in p.get_texttrace()) for p in d))

r = post("/add-watermark", SOURCE, text="机密")
keeps("watermark (Chinese text)", r.data)

# Nothing to carry over: must not break or invent anything.
plain = make_pdf(toc=False, meta=False)
for route, data in (("/rotate-pdf", {"rotation": "180"}), ("/add-watermark", {"text": "DRAFT"})):
    r = post(route, plain, **data)
    meta, toc, _, pages = info(r.data)
    check(f"{route}: PDF without bookmarks or metadata still works", r.status_code == 200 and toc == [] and pages == 5)
    check(f"{route}: ...and gets no invented title or author", not meta["title"] and not meta["author"])

# Bookmarks only / metadata only.
r = post("/rotate-pdf", make_pdf(meta=False), rotation="270")
check("rotate: bookmarks-only PDF keeps its bookmarks", info(r.data)[1] == TOC)
r = post("/add-watermark", make_pdf(toc=False), text="DRAFT")
check("watermark: metadata-only PDF keeps its metadata", info(r.data)[0] == META)

# A bookmark that points nowhere is skipped, not a failed request.
reader = PdfReader(io.BytesIO(SOURCE))
writer = PdfWriter()
writer.clone_document_from_reader(reader)
buf = io.BytesIO()
writer.write(buf)
broken = fitz.open(stream=buf.getvalue(), filetype="pdf")
broken.set_toc([[1, "Good", 1], [1, "Also good", 3]])
raw = broken.tobytes()
raw = raw.replace(b"/Count 2", b"/Count 3", 1)  # outline claims an entry that does not exist
for route, data in (("/rotate-pdf", {"rotation": "90"}), ("/add-watermark", {"text": "DRAFT"})):
    r = post(route, raw, **data)
    toc = info(r.data)[1] if r.status_code == 200 else None
    check(f"{route}: damaged bookmark tree does not fail the request",
          r.status_code == 200 and toc is not None and [t[1] for t in toc][:2] == ["Good", "Also good"])

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
