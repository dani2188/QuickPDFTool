"""Regression test for the Crop PDF FloatObject/Decimal arithmetic bug.

No new dependencies -- plain stdlib plus the app itself and libraries
already in requirements.txt. Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\test_crop_pdf_geometry.py

Background: PyPDF2's FloatObject subclasses decimal.Decimal, which does
not support direct arithmetic with a plain Python float. A page's
MediaBox corner is only a FloatObject when its value is non-integer --
true for ISO page sizes (A4, A3, A5, ...) and any non-zero fractional
origin, but not for US Letter, whose corners happen to be whole numbers.
This previously crashed /crop-pdf with an unhandled HTTP 500 for any of
those cases. The fix wraps each MediaBox accessor in float() before
arithmetic.

This script exercises the REAL /crop-pdf route (via Flask's test
client, not a reimplementation) across every page size in that
category, plus a synthetic fractional-origin case, plus a zero-margin
no-op case, and asserts both success and exact output geometry.

Exits 0 if every case passes, 1 otherwise.
"""

import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from reportlab.pdfgen import canvas  # noqa: E402
from reportlab.lib.pagesizes import A3, A4, A5, letter  # noqa: E402
from PyPDF2 import PdfReader, PdfWriter  # noqa: E402
from PyPDF2.generic import FloatObject  # noqa: E402

import app as qt_app  # noqa: E402  (the actual QuickTools Flask app)


def build_pdf(pagesize, landscape=False):
    w, h = pagesize
    if landscape:
        w, h = h, w
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.drawString(20, h - 30, "test")
    c.save()
    buf.seek(0)
    return buf.getvalue()


def build_fractional_origin_pdf():
    """A page whose MediaBox origin itself is fractional/non-zero --
    simulates a real-world PDF not produced starting at a clean (0, 0),
    which fails on the addition lines too, not just the subtraction
    lines A4/A3/A5 exercise."""
    base = build_pdf(letter)
    reader = PdfReader(io.BytesIO(base))
    writer = PdfWriter()
    page = reader.pages[0]
    page.mediabox.lower_left = (FloatObject(10.5), FloatObject(20.5))
    page.mediabox.upper_right = (FloatObject(622.5), FloatObject(812.5))
    writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def crop_via_real_route(client, pdf_bytes, left, right, top, bottom):
    resp = client.post(
        "/crop-pdf",
        data={
            "pdf": (io.BytesIO(pdf_bytes), "test.pdf"),
            "left": str(left),
            "right": str(right),
            "top": str(top),
            "bottom": str(bottom),
        },
        content_type="multipart/form-data",
    )
    return resp


def mediabox_tuple(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    mb = reader.pages[0].mediabox
    return (float(mb.left), float(mb.bottom), float(mb.right), float(mb.top))


MARGIN = 50.0


def main():
    client = qt_app.app.test_client()
    failures = []

    cases = [
        ("A4 portrait", build_pdf(A4)),
        ("A4 landscape", build_pdf(A4, landscape=True)),
        ("Letter portrait", build_pdf(letter)),
        ("Letter landscape", build_pdf(letter, landscape=True)),
        ("A3", build_pdf(A3)),
        ("A5", build_pdf(A5)),
        ("Fractional origin (synthetic)", build_fractional_origin_pdf()),
    ]

    print(f"{'Case':<32}{'HTTP':<8}{'Input MediaBox':<32}{'Output MediaBox':<32}{'Result'}")

    for label, pdf_bytes in cases:
        input_mb = mediabox_tuple(pdf_bytes)
        expected = (
            input_mb[0] + MARGIN,  # left + left-margin
            input_mb[1] + MARGIN,  # bottom + bottom-margin
            input_mb[2] - MARGIN,  # right - right-margin
            input_mb[3] - MARGIN,  # top - top-margin
        )

        resp = crop_via_real_route(client, pdf_bytes, MARGIN, MARGIN, MARGIN, MARGIN)
        status_ok = resp.status_code == 200

        if not status_ok:
            failures.append(f"{label}: expected HTTP 200, got {resp.status_code}")
            print(f"{label:<32}{resp.status_code:<8}{str(input_mb):<32}{'n/a':<32}FAIL")
            continue

        output_mb = mediabox_tuple(resp.data)
        geometry_ok = all(abs(a - b) < 0.01 for a, b in zip(output_mb, expected))

        if not geometry_ok:
            failures.append(
                f"{label}: expected MediaBox {expected}, got {output_mb}"
            )

        result = "PASS" if geometry_ok else "FAIL"
        print(f"{label:<32}{resp.status_code:<8}{str(input_mb):<32}{str(output_mb):<32}{result}")

    print()
    print("=" * 70)
    print("Zero-margin crop must leave the MediaBox unchanged")
    print("=" * 70)
    zero_case_pdf = build_pdf(A4)
    input_mb = mediabox_tuple(zero_case_pdf)
    resp = crop_via_real_route(client, zero_case_pdf, 0, 0, 0, 0)
    status_ok = resp.status_code == 200
    if not status_ok:
        failures.append(f"Zero-margin A4: expected HTTP 200, got {resp.status_code}")
        print(f"HTTP {resp.status_code}: FAIL")
    else:
        output_mb = mediabox_tuple(resp.data)
        unchanged = all(abs(a - b) < 0.01 for a, b in zip(output_mb, input_mb))
        if not unchanged:
            failures.append(
                f"Zero-margin A4: expected unchanged MediaBox {input_mb}, got {output_mb}"
            )
        print(f"input={input_mb} output={output_mb} -> {'PASS' if unchanged else 'FAIL'}")

    print()
    if failures:
        print(f"=== {len(failures)} FAILURE(S) ===")
        for f in failures:
            print("  -", f)
        return 1

    print("=== ALL CASES PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
