"""Check the results-page page-count notice (QT-031) and the guides' "Open the tool" button (T-3).

Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\test_result_pages.py

Uses Flask's test client with a temporary upload folder and no timers, so it needs no server. Verifies that:

  - PDF to PNG / JPG / WebP results say "N page(s) converted" for PDFs of 20 pages or fewer, and
    "20 of N pages converted" plus how to convert the rest when pages were left out;
  - the files really produced still stop at 20;
  - the how-to guides for Remove Watermark and PDF to JPG show an "Open the tool" button right under
    the byline, before the first section, linking to the right tool, and other guides are unchanged.

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

import app as qt_app  # noqa: E402  (the actual hellobrivio Flask app)

tmp = tempfile.mkdtemp(prefix="results_")
qt_app.UPLOAD_FOLDER = os.path.join(tmp, "uploads")
os.makedirs(qt_app.UPLOAD_FOLDER)
qt_app.delete_file_later = lambda *a, **k: None
client = qt_app.app.test_client()
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


def pdf_with(pages):
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Page {i + 1}")
    return doc.tobytes()


def text_of(response):
    html = response.get_data(as_text=True).split("<main", 1)[1]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# --- results pages ----------------------------------------------------------------------
for route, kind in (("/pdf-to-png", "PNG"), ("/pdf-to-jpg", "JPG"), ("/pdf-to-webp", "WebP")):
    for pages in (1, 5, 20):
        r = client.post(route, data={"pdf": (io.BytesIO(pdf_with(pages)), "t.pdf")}, content_type="multipart/form-data")
        text = text_of(r)
        check(f"{kind}: {pages}-page PDF says '{pages} page(s) converted' and shows no warning",
              r.status_code == 200 and f"{pages} page(s) converted" in text and "of " + str(pages) not in text
              and "not included" not in text, text[:200])
    for pages in (21, 25, 45):
        r = client.post(route, data={"pdf": (io.BytesIO(pdf_with(pages)), "t.pdf")}, content_type="multipart/form-data")
        html = r.get_data(as_text=True)
        text = text_of(r)
        links = re.findall(r'href="/download-file/[^"]+"', html)
        expected_gap = "page 21 is not included" if pages == 21 else f"pages 21 to {pages} are not included"
        check(f"{kind}: {pages}-page PDF says '20 of {pages} pages converted' and explains the rest",
              r.status_code == 200 and f"20 of {pages} pages converted" in text and expected_gap in text
              and "Delete PDF Pages" in text and "1, 2, 3 and so on up to 20" in text, text[:260])
        expected_links = 20 + (1 if kind != "WebP" else 0)  # 20 pages, plus the ZIP for PNG and JPG
        check(f"{kind}: {pages}-page PDF still produces exactly 20 images", len(links) == expected_links, len(links))
    r = client.post(route, data={"pdf": (io.BytesIO(pdf_with(25)), "t.pdf")}, content_type="multipart/form-data")
    has_guide = "/how-to-pdf-to-png#long-pdfs" in r.get_data(as_text=True)
    check(f"{kind}: step-by-step guide link only on the PNG page", has_guide == (kind == "PNG"), has_guide)

# --- the guides' button -----------------------------------------------------------------------
for path, href, label in (("/how-to-remove-watermark-pdf", "/remove-watermark", "Open the Remove Watermark tool"),
                          ("/how-to-pdf-to-jpg", "/pdf-to-jpg", "Open the PDF to JPG tool")):
    html = client.get(path).get_data(as_text=True)
    button = re.search(r'<p class="open-tool"><a class="main-btn" href="([^"]+)">([^<]+)</a></p>', html)
    byline_at, button_at = html.find('class="byline"'), html.find('class="open-tool"')
    first_h2 = html.find("<h2", byline_at)
    check(f"{path}: one button -> {href} labelled '{label}'",
          bool(button) and button.group(1) == href and button.group(2) == label and html.count('class="open-tool"') == 1,
          button.groups() if button else None)
    check(f"{path}: button sits under the byline and before the first section", byline_at < button_at < first_h2,
          (byline_at, button_at, first_h2))
    check(f"{path}: still exactly one h1", len(re.findall(r"<h1[ >]", html)) == 1)

for path in ("/how-to-compress-pdf", "/how-to-merge-pdf", "/how-to-pdf-to-png"):
    check(f"{path}: other guides are unchanged (no button)",
          'class="open-tool"' not in client.get(path).get_data(as_text=True))

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
