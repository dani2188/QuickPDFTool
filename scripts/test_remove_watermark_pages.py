"""Remove Watermark must find QuickTools' own watermark on any page shape.

Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\test_remove_watermark_pages.py

Adds a watermark with the real /add-watermark route to pages of many sizes,
orientations, rotations and crop boxes, removes it with the real
/remove-watermark route, and checks that the watermark span is gone while
the page's own content survives. It also checks near-misses (same style at
the wrong position, opaque, bigger, coloured) are left alone. Exits 1 on any
failure.
"""

import io
import os
import sys

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


def post(route, pdf, **data):
    fields = {"pdf": (io.BytesIO(pdf), "test.pdf"), **data}
    r = client.post(route, data=fields, content_type="multipart/form-data")
    assert r.status_code == 200, (route, r.status_code)
    return r.data


def body(page):
    page.insert_text((72, 72), "Body text stays", fontsize=14)
    page.draw_rect(fitz.Rect(72, 100, 200, 140))
    page.insert_text((72, 300), "DRAFT", fontsize=11)  # same word, ordinary text


def big_spans(pdf, page_no=0):
    """Text spans at the watermark's 40pt size (the watermark, if still present)."""
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        return [s for s in doc[page_no].get_texttrace() if s["size"] > 30]


def page_words(pdf, page_no=0):
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        return doc[page_no].get_text().split()


SHAPES = {
    "Letter": (612, 792, 0, None), "A4": (595, 842, 0, None), "A5": (420, 595, 0, None),
    "A3": (842, 1191, 0, None), "Legal": (612, 1008, 0, None),
    "landscape Letter": (792, 612, 0, None), "landscape A4": (842, 595, 0, None),
    "A4 rotated 90": (595, 842, 90, None), "A4 rotated 180": (595, 842, 180, None),
    "A4 rotated 270": (595, 842, 270, None), "A4 with crop box": (595, 842, 0, fitz.Rect(20, 30, 500, 800)),
}

for name, (w, h, rotation, crop) in SHAPES.items():
    doc = fitz.open()
    page = doc.new_page(width=w, height=h)
    body(page)
    if crop:
        page.set_cropbox(crop)
    if rotation:
        page.set_rotation(rotation)
    marked = post("/add-watermark", doc.tobytes(), text="CONFIDENTIAL")
    cleaned = post("/remove-watermark", marked)
    words = page_words(cleaned)
    check(f"{name}: watermark present before, gone after",
          len(big_spans(marked)) == 1 and not big_spans(cleaned))
    check(f"{name}: page content survives", "Body" in words and words.count("DRAFT") == 1)

doc = fitz.open()
for w, h in ((612, 792), (595, 842), (842, 595)):
    body(doc.new_page(width=w, height=h))
cleaned = post("/remove-watermark", post("/add-watermark", doc.tobytes(), text="CONFIDENTIAL"))
check("mixed page sizes in one file: removed on every page",
      all(not big_spans(cleaned, i) and "Body" in page_words(cleaned, i) for i in range(3)))

# Near-misses on an A4 page: each must survive removal.
H = 842
cases = {
    "opaque": dict(origin=(150, H - 400), opacity=1.0),
    "bigger": dict(origin=(150, H - 400), size=44),
    "coloured": dict(origin=(150, H - 400), color=(0.9, 0.2, 0.2)),
    "moved 25pt": dict(origin=(150, H - 400 + 25)),
    "moved sideways": dict(origin=(190, H - 400)),
}
doc = fitz.open()
for label, kw in cases.items():
    page = doc.new_page(width=595, height=H)
    page.insert_text(kw["origin"], label.upper().replace(" ", "_"), fontsize=kw.get("size", 40),
                     fontname="helv", fill_opacity=kw.get("opacity", 0.3), color=kw.get("color", (0.572,) * 3))
cleaned = post("/remove-watermark", doc.tobytes())
for i, label in enumerate(cases):
    check(f"near-miss survives: {label}", label.upper().replace(" ", "_") in page_words(cleaned, i))

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
