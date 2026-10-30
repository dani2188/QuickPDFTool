"""Add Watermark must draw non-Western text properly, or refuse it with a clear message.

Run from the repo root:

    .venv\Scripts\python.exe scripts\test_add_watermark_text.py

Helvetica (the only font the tool used) cannot draw Cyrillic, Greek or Chinese, so those watermarks
came out as solid boxes while the page looked processed. Drives the real /add-watermark and
/remove-watermark routes and checks that:

  - Cyrillic, Greek, Chinese, Japanese, Korean and mixed text is drawn with a real font (the text
    extracts back to what was typed, and different strings look different, which solid boxes
    would not);
  - Latin / Western European text still uses Helvetica, exactly as before;
  - text no font can draw is refused with a styled 400 page naming the characters, never a PDF;
  - Remove Watermark still strips the new watermarks and leaves the page's own text alone;
  - the output only grows by a few KB (the font is subset, not embedded whole).

Exits 1 on any failure.
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

import app as qt_app  # noqa: E402

client = qt_app.app.test_client()
failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


doc = fitz.open()
doc.new_page(width=612, height=792).insert_text((72, 72), "Body text stays", fontsize=14)
SOURCE = doc.tobytes()
doc.close()


def post(route, pdf, **data):
    fields = {"pdf": (io.BytesIO(pdf), "test.pdf"), **data}
    return client.post(route, data=fields, content_type="multipart/form-data")


def big_spans(pdf):
    with fitz.open(stream=pdf, filetype="pdf") as d:
        return [s for s in d[0].get_texttrace() if s["size"] > 30]


def watermark_text(pdf):
    """The text of the 40pt span(s), as extracted back out of the PDF."""
    with fitz.open(stream=pdf, filetype="pdf") as d:
        page = d[0]
        words = page.get_text("dict")
    return "".join(
        span["text"]
        for block in words["blocks"] for line in block.get("lines", []) for span in line["spans"]
        if span["size"] > 30
    )


def ink(pdf):
    """Pixels of the watermark area, to tell two different strings apart."""
    with fitz.open(stream=pdf, filetype="pdf") as d:
        return d[0].get_pixmap(clip=fitz.Rect(140, 340, 612, 410), dpi=72).samples


TEXTS = {
    "Cyrillic": "Конфиденциально",
    "Greek": "Εμπιστευτικό",
    "Chinese": "机密文件",
    "Japanese": "社外秘",
    "Korean": "기밀",
    "mixed Latin and Chinese": "Draft 草稿",
    "Latin with a letter Helvetica lacks": "Łódź",
}

outputs = {}
for label, text in TEXTS.items():
    r = post("/add-watermark", SOURCE, text=text)
    check(f"{label}: accepted", r.status_code == 200)
    if r.status_code != 200:
        continue
    pdf = r.data
    outputs[label] = pdf
    spans = big_spans(pdf)
    check(f"{label}: drawn with a real font, not Helvetica", bool(spans) and all(s["font"] != "Helvetica" for s in spans))
    check(f"{label}: the typed text extracts back out", watermark_text(pdf) == text)
    check(f"{label}: page text untouched", "Body text stays" in fitz.open(stream=pdf, filetype="pdf")[0].get_text())
    check(f"{label}: output grows by under 100 KB (font is subset)", len(pdf) - len(SOURCE) < 100_000)

check("different strings look different (boxes would be identical)",
      ink(outputs["Chinese"]) != ink(outputs["Japanese"]) and ink(outputs["Cyrillic"]) != ink(outputs["Greek"]))

# Western text is unchanged: still Helvetica.
for text in ("CONFIDENTIAL", "Café €5 – naïve"):
    r = post("/add-watermark", SOURCE, text=text)
    spans = big_spans(r.data)
    check(f"{text!r}: still Helvetica", r.status_code == 200 and bool(spans) and all(s["font"] == "Helvetica" for s in spans))

# Text no font can draw: refused, with the characters named.
for label, text, shown in (("emoji", "Draft 😀", "😀"), ("Arabic", "سري", "س")):
    r = post("/add-watermark", SOURCE, text=text)
    page = r.get_data(as_text=True)
    check(f"{label}: refused with a 400, not a PDF", r.status_code == 400 and not r.data.startswith(b"%PDF"))
    check(f"{label}: message names the character", "can't be drawn" in page.replace("&#39;", "'") and shown in page)
    check(f"{label}: message says what to use instead", "Latin, Cyrillic, Greek" in page)

for label, text in (("empty", ""), ("spaces only", "   ")):
    r = post("/add-watermark", SOURCE, text=text)
    check(f"{label} text: clear 400, not a crash", r.status_code == 400 and "watermark text" in r.get_data(as_text=True))

# Remove Watermark still recognises the new watermarks.
for label in ("Cyrillic", "Chinese", "mixed Latin and Chinese", "Latin with a letter Helvetica lacks"):
    r = post("/remove-watermark", outputs[label])
    check(f"{label}: Remove Watermark strips it", r.status_code == 200 and not big_spans(r.data))
    check(f"{label}: ...and keeps the page's own text",
          "Body text stays" in fitz.open(stream=r.data, filetype="pdf")[0].get_text())

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
