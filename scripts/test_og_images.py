"""Check the per-tool social preview images (og:image / twitter:image).

Run from the repo root:  .venv\Scripts\python.exe scripts\test_og_images.py

  - every tool page in scripts/make_og_images.py TOOLS gets its own og:image, and the same URL as
    twitter:image, pointing at a real 1200 x 630 PNG that the site serves;
  - no two tool pages share an image, and the image file is named after the page's route;
  - hubs, the home page, legal pages, guides and blog posts keep the shared icon and the small card;
  - the alt text names the page.

Exits 1 on any failure.
"""

import io
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from PIL import Image  # noqa: E402

import app as qt_app  # noqa: E402
import make_og_images  # noqa: E402

client = qt_app.app.test_client()
failures = []
SHARED = "https://hellobrivio.com/static/img/icon-512.png"


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


def meta(html, key):
    m = re.search(r'<meta (?:property|name)="' + re.escape(key) + r'" content="([^"]*)"', html)
    return m.group(1) if m else None


seen = {}
for slug in sorted(make_og_images.TOOLS):
    path = "/" + slug
    html = client.get(path).get_data(as_text=True)
    og, tw = meta(html, "og:image"), meta(html, "twitter:image")
    expected = f"https://hellobrivio.com/static/img/og/{slug}.png"
    check(f"{path}: og:image is its own image", og == expected, og)
    check(f"{path}: twitter:image matches og:image and the card is large", tw == og
          and meta(html, "twitter:card") == "summary_large_image", (tw, meta(html, "twitter:card")))
    r = client.get(og.replace("https://hellobrivio.com", ""))
    ok = r.status_code == 200
    if ok:
        with Image.open(io.BytesIO(r.data)) as im:
            ok = im.format == "PNG" and im.size == (1200, 630)
    check(f"{path}: the image is served and is a 1200 x 630 PNG", ok, r.status_code)
    check(f"{path}: size and alt are declared", meta(html, "og:image:width") == "1200" and meta(html, "og:image:height") == "630"
          and "hellobrivio" in (meta(html, "og:image:alt") or ""), meta(html, "og:image:alt"))
    seen.setdefault(og, []).append(path)
check("no two tool pages share an image", all(len(v) == 1 for v in seen.values()), seen)
check("every file in static/img/og belongs to a tool page",
      {f[:-4] for f in os.listdir(os.path.join(BASE, "static", "img", "og"))} == set(make_og_images.TOOLS))

for path in ("/", "/pdf-tools", "/image-tools", "/about", "/privacy-policy", "/how-to-compress-pdf",
             "/blog/pdf-file-size-explained"):
    html = client.get(path).get_data(as_text=True)
    check(f"{path}: keeps the shared icon and the small card",
          meta(html, "og:image") == SHARED and meta(html, "twitter:card") == "summary", meta(html, "og:image"))

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
