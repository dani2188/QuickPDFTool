"""Lightweight content/SEO audit for QuickTools templates.

No new dependencies, no framework -- plain stdlib. Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\content_audit.py

Checks each template in templates/ (skipping partials, error pages, and
generated result screens, which aren't indexable content pages) for:

  - missing <h1> / block title / block description
  - very low visible word count (a thin-content signal)
  - missing internal "More Tools" style links
  - internal href="/..." links that don't match any known app.py route
    (a broken-link signal; best-effort, string-based, not a live crawl)
  - leftover "QuickPDFTools" text (should be fully renamed to "QuickTools")

Also reports duplicate <title>/description text across pages, since two
pages targeting the same title is itself a low-value-content signal.

This is a diagnostic aid, not a build-blocking test -- it prints a report
and exits 0 regardless of findings.
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(BASE, "templates")
APP_PY = os.path.join(BASE, "app.py")

# Templates that are not standalone indexable pages -- skip them.
SKIP_DIRS = {"components"}
SKIP_FILES = {
    "404.html", "413.html", "500.html",
    "result.html", "processing.html",
    "extract_images_result.html", "pdf_to_jpg_result.html",
    "pdf_to_png_result.html", "compress_jpg_result.html",
    "ads.txt",
}
SKIP_SUFFIXES = ("_result.html",)


def iter_templates():
    for root, dirs, files in os.walk(TPL):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".html"):
                continue
            if f in SKIP_FILES or f.endswith(SKIP_SUFFIXES):
                continue
            yield os.path.relpath(os.path.join(root, f), TPL)


def visible_word_count(html):
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", " ", text)
    return len(text.split())


def extract_block(html, name):
    m = re.search(r"\{%-?\s*block\s+" + name + r"\s*-?%\}(.*?)\{%-?\s*endblock\s*-?%\}", html, re.S)
    return m.group(1).strip() if m else None


def get_known_routes():
    if not os.path.exists(APP_PY):
        return set()
    content = open(APP_PY, encoding="utf-8").read()
    routes = set(re.findall(r'@app\.route\("([^"<]+)"', content))
    # normalize dynamic segments like <filename> -> treat as a prefix match later
    return routes


def main():
    known_routes = get_known_routes()
    known_static = {r for r in known_routes if "<" not in r}
    dynamic_prefixes = tuple(r.split("<")[0] for r in known_routes if "<" in r)

    rows = []
    titles = {}
    descriptions = {}
    issues = []

    for rel in sorted(iter_templates()):
        path = os.path.join(TPL, rel)
        html = open(path, encoding="utf-8").read()

        if "{% extends" not in html:
            continue  # partial, not a full page

        h1_count = len(re.findall(r"<h1[ >]", html))
        title = extract_block(html, "title")
        desc = extract_block(html, "description")
        words = visible_word_count(html)
        has_related = "tools-mini-grid" in html or ("tools-grid" in html and "guide" in rel)
        has_qpt = "QuickPDFTools" in html

        row = {
            "file": rel, "h1": h1_count, "title": title, "desc": desc,
            "words": words, "has_related": has_related, "has_qpt": has_qpt,
        }
        rows.append(row)

        if h1_count == 0:
            issues.append(f"[H1] {rel}: no <h1>")
        elif h1_count > 1:
            issues.append(f"[H1] {rel}: {h1_count} <h1> tags (should be exactly 1)")
        if not title:
            issues.append(f"[TITLE] {rel}: no {{% block title %}}")
        if not desc:
            issues.append(f"[DESC] {rel}: no {{% block description %}}")
        if words < 150:
            issues.append(f"[THIN] {rel}: only {words} visible words")
        if has_qpt:
            issues.append(f"[BRAND] {rel}: still contains 'QuickPDFTools'")

        if title:
            titles.setdefault(title.strip(), []).append(rel)
        if desc:
            descriptions.setdefault(desc.strip(), []).append(rel)

        # internal link check (best-effort)
        for href in re.findall(r'href="(/[^"#?]*)', html):
            if href in ("/",):
                continue
            if href in known_static:
                continue
            if any(href.startswith(p) for p in dynamic_prefixes):
                continue
            if href.startswith("/static/") or href.startswith("/uploads/"):
                continue
            issues.append(f"[LINK] {rel}: links to {href}, no matching app.py route found")

    print(f"Scanned {len(rows)} page templates.\n")

    print("=== Word count distribution ===")
    thin = [r for r in rows if r["words"] < 150]
    low = [r for r in rows if 150 <= r["words"] < 300]
    ok = [r for r in rows if r["words"] >= 300]
    print(f"  < 150 words:  {len(thin)}")
    print(f"  150-299:      {len(low)}")
    print(f"  >= 300:       {len(ok)}")
    print()

    dup_titles = {t: fs for t, fs in titles.items() if len(fs) > 1}
    dup_descs = {d: fs for d, fs in descriptions.items() if len(fs) > 1}

    print(f"=== Duplicate titles: {len(dup_titles)} ===")
    for t, fs in dup_titles.items():
        print(f"  {t!r} used by: {', '.join(fs)}")
    print()

    print(f"=== Duplicate descriptions: {len(dup_descs)} ===")
    for d, fs in dup_descs.items():
        short = d[:70] + ("..." if len(d) > 70 else "")
        print(f"  {short!r} used by: {', '.join(fs)}")
    print()

    print(f"=== All issues ({len(issues)}) ===")
    for i in issues:
        print(" ", i)
    print()

    print("=== Notes ===")
    print("  - Canonical URLs are handled globally in base.html for every page, not checked per-file.")
    print("  - [LINK] entries can include false positives for query-string-only anchors or hrefs")
    print("    built dynamically with Jinja ({{ ... }}) that this regex can't resolve statically.")
    print("  - [THIN] threshold (150 words) is a floor, not a target -- see docs/CONTENT_AUDIT.md")
    print("    for the fuller quality rubric (FAQ, use cases, considerations, related tools).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
