"""Titles and descriptions of the SEO T-2 pages must be honest, unique and fact-based.

Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\test_seo_metadata.py

For each tool page listed below it checks that:

  - the title names the task and contains "Free" and "Online", is on one line and is at most 60 characters;
  - the description is 70-155 characters;
  - every fact the description cites (a figure, a limit, a claim) appears in the description AND in the
    page's own visible text, so a snippet can never promise something the page doesn't say. The measured
    figures come from scripts/measure_examples.py, so if that is re-run and a number changes, this fails
    and the description needs updating;
  - a description never claims "no signup / no account / no watermark" unless the page says so;
  - no title or description is shared with any other page on the site.

Exits 1 on any failure.
"""

import os
import re
import sys
from collections import Counter
from html import unescape

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import app as qt_app  # noqa: E402  (the actual hellobrivio Flask app)

# path -> (facts that must be in BOTH the description and the page text,
#          facts that must be in the page text, backing a claim the description makes in other words)
PAGES = {
    "/rotate-pdf": (["90°", "180°", "270°", "all pages", "20MB", "within a few minutes"], []),
    "/jpg-to-pdf": (["JPG", "PNG", "in the order you select them", "exactly as you uploaded"], ["not re-compressed"]),
    "/resize-image": (["Instagram", "TikTok", "YouTube", "Facebook", "never crop", "30 megapixels", "within minutes"], []),
    "/compress-jpg": (["ZIP", "EXIF", "GPS location"], ["Low –", "Medium –", "High –", "Extreme –"]),
    "/extract-images": (["50 images", "20MB", "original embedded quality", "no re-compression"], []),
    "/compress-pdf": (["1.15 MB", "194.4 KB", "Medium", "target size", "20 MB"], ["Scanned letter (2 pages"]),
    "/pdf-to-word": (["5,051", "OCR", "DOCX"], ["Text-only report (6 pages", "1 table"]),
    "/merge-pdf": (["in the order", "re-compress", "11"], ["Three input files", "three sample PDFs"]),
}
UNBACKED = ("no signup", "no sign-up", "no account", "no watermark", "without signing up")

client = qt_app.app.test_client()
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


def snippet_and_text(path):
    html = client.get(path, headers={"Host": "hellobrivio.com"}).get_data(as_text=True)
    raw_title = unescape(re.search(r"<title>(.*?)</title>", html, re.S).group(1))
    title = raw_title.strip()
    description = " ".join(unescape(re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.S).group(1)).split())
    main = re.sub(r"<script.*?</script>|<style.*?</style>", " ", re.search(r"<main.*?</main>", html, re.S).group(0), flags=re.S)
    text = " ".join(unescape(re.sub(r"<[^>]+>", " ", main)).split())
    return title, description, text


for path, (shared, body_only) in PAGES.items():
    title, description, text = snippet_and_text(path)
    low_title, low_desc, low_text = title.lower(), description.lower(), text.lower()
    check(f"{path}: title has 'Free' and 'Online', one line, <= 60 chars ({len(title)})",
          "free" in low_title and "online" in low_title and "\n" not in title and len(title) <= 60, title)
    check(f"{path}: description is 70-155 chars ({len(description)})", 70 <= len(description) <= 155, description)
    missing = [f for f in shared if f.lower() not in low_desc or f.lower() not in low_text]
    check(f"{path}: every cited fact is in the description and on the page", not missing, missing)
    missing = [f for f in body_only if f.lower() not in low_text]
    check(f"{path}: supporting text is on the page", not missing, missing)
    claimed = [c for c in UNBACKED if c in low_desc and c not in low_text]
    check(f"{path}: no 'no signup/account/watermark' claim the page doesn't make", not claimed, claimed)

# uniqueness across the whole site
titles, descriptions, owners = Counter(), Counter(), {}
for rule in qt_app.app.url_map.iter_rules():
    if "GET" not in rule.methods or rule.arguments or rule.rule.startswith("/static"):
        continue
    if rule.rule in ("/sitemap.xml", "/robots.txt", "/ads.txt"):
        continue
    title, description, _ = snippet_and_text(rule.rule)
    titles[" ".join(title.split())] += 1
    descriptions[description] += 1
    owners.setdefault(" ".join(title.split()), []).append(rule.rule)
check("every page title on the site is unique", all(n == 1 for n in titles.values()),
      [owners[t] for t, n in titles.items() if n > 1])
check("every page description on the site is unique", all(n == 1 for n in descriptions.values()),
      [d[:60] for d, n in descriptions.items() if n > 1])

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
