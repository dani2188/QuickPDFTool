"""Generate the per-tool social preview images (og:image / twitter:image).

Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\make_og_images.py

Writes one 1200 x 630 PNG per tool page to static/img/og/<route-slug>.png, for example
static/img/og/compress-pdf.png for /compress-pdf. The images are built only from the brand
assets already in the repo (static/img/logo.png, static/img/icon-512.png, the brand red from
static/style.css) plus the tool's name, so there is nothing to keep in sync by hand: add a tool to
TOOLS below, re-run the script, and commit the new PNG. app.py serves it as the page's og:image
when static/img/og/<slug>.png exists, and falls back to the shared icon otherwise.

Hub pages, the home page, legal pages and blog posts keep the shared icon.
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "static", "img")
OUT = os.path.join(IMG, "og")

WIDTH, HEIGHT = 1200, 630
BRAND, BRAND_DARK = (229, 50, 45), (198, 40, 35)  # --brand / --brand-dark in static/style.css
BACKGROUND, INK, MUTED = (250, 250, 250), (34, 34, 34), (95, 95, 95)

# route slug -> name shown on the image. Image tools are listed in IMAGE_TOOLS; the rest are PDF tools.
TOOLS = {
    "add-page-numbers": "Add Page Numbers to PDF",
    "add-text-to-pdf": "Add Text to PDF",
    "add-watermark": "Add Watermark to PDF",
    "compress-jpg": "Compress JPG",
    "compress-pdf": "Compress PDF",
    "compress-pdf-for-email": "Compress PDF for Email",
    "compress-pdf-to-1mb": "Compress PDF to 1MB",
    "crop-pdf": "Crop PDF",
    "delete-pdf-pages": "Delete PDF Pages",
    "excel-to-pdf": "Excel to PDF",
    "extract-images": "Extract Images from PDF",
    "jpg-to-pdf": "JPG to PDF",
    "merge-pdf": "Merge PDF",
    "pdf-to-excel": "PDF to Excel",
    "pdf-to-jpg": "PDF to JPG",
    "pdf-to-png": "PDF to PNG",
    "pdf-to-text": "PDF to Text",
    "pdf-to-webp": "PDF to WebP",
    "pdf-to-word": "PDF to Word",
    "png-to-pdf": "PNG to PDF",
    "protect-pdf": "Protect PDF with a Password",
    "redact-pdf": "Redact PDF",
    "remove-background": "Remove Image Background",
    "remove-watermark": "Remove Watermark from PDF",
    "resize-image": "Resize Image",
    "rotate-pdf": "Rotate PDF",
    "sign-pdf": "Sign PDF",
    "split-pdf": "Split PDF",
    "svg-to-pdf": "SVG to PDF",
    "unlock-pdf": "Unlock PDF",
    "word-to-pdf": "Word to PDF",
}
IMAGE_TOOLS = {"compress-jpg", "remove-background", "resize-image"}

BOLD_FONTS = ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf")
REGULAR_FONTS = ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")


def font(candidates, size):
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise SystemExit("No TrueType font found (looked for: " + ", ".join(candidates) + ")")


def wrap(draw, text, fnt, max_width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def render(slug, name):
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 20, HEIGHT), fill=BRAND)

    logo = Image.open(os.path.join(IMG, "logo.png")).convert("RGBA")
    logo = logo.resize((330, round(330 * logo.height / logo.width)), Image.LANCZOS)
    image.paste(logo, (80, 56), logo)

    icon = Image.open(os.path.join(IMG, "icon-512.png")).convert("RGBA").resize((230, 230), Image.LANCZOS)
    image.paste(icon, (WIDTH - 230 - 80, HEIGHT - 230 - 80), icon)

    max_width = 760
    for size in (104, 96, 88, 80, 72, 64):
        title_font = font(BOLD_FONTS, size)
        lines = wrap(draw, name, title_font, max_width)
        if len(lines) <= 2 and all(draw.textlength(l, font=title_font) <= max_width for l in lines):
            break
    y = 215
    for line in lines:
        draw.text((80, y), line, font=title_font, fill=INK)
        y += round(size * 1.15)

    kind = "image" if slug in IMAGE_TOOLS else "PDF"
    draw.text((80, y + 14), f"Free online {kind} tool", font=font(REGULAR_FONTS, 38), fill=MUTED)
    draw.text((80, HEIGHT - 96), "hellobrivio.com", font=font(BOLD_FONTS, 36), fill=BRAND_DARK)

    path = os.path.join(OUT, f"{slug}.png")
    image.save(path, "PNG", optimize=True)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] or sorted(TOOLS)
    for slug in only:
        path = render(slug, TOOLS[slug])
        print(f"static/img/og/{slug}.png  {os.path.getsize(path) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
