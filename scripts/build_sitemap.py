"""Generate sitemap.xml from the app's public routes, with <lastmod> dates.

No new dependencies -- plain stdlib plus the app itself and git. Run from
the repo root:

    .venv\\Scripts\\python.exe scripts\\build_sitemap.py          # rewrite sitemap.xml
    .venv\\Scripts\\python.exe scripts\\build_sitemap.py --check  # verify only

What it does:

1. Discovers every public page from Flask's own `app.url_map`: GET routes
   with no URL parameters, minus the non-page endpoints in NON_PAGE_PATHS
   (sitemap/robots/ads.txt). Download, status and upload routes all take a
   <filename> parameter, so they are excluded automatically.
2. Renders each page through the test client to learn which template it
   uses, and takes the last git commit date of that template (plus any
   page-specific components/examples/* partial it includes) as <lastmod>;
   shared chrome such as base.html never moves it. A template with no
   commit yet falls back to today.
3. Writes sitemap.xml with the homepage first and the rest sorted by path.

With --check it rewrites nothing: it compares the routes against the
existing sitemap.xml, reports pages missing from the sitemap, sitemap
entries with no matching route, and entries without <lastmod>, and exits 1
if any are found. Run it after adding or removing a route.
"""

import datetime
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import app as qt_app  # noqa: E402  (the actual hellobrivio Flask app)

SITE = "https://hellobrivio.com"
SITEMAP = os.path.join(BASE, "sitemap.xml")
NON_PAGE_PATHS = {"/sitemap.xml", "/robots.txt", "/ads.txt"}


def public_paths():
    paths = set()
    for rule in qt_app.app.url_map.iter_rules():
        if "GET" not in rule.methods or rule.arguments:
            continue
        if rule.rule in NON_PAGE_PATHS:
            continue
        paths.add(rule.rule)
    return sorted(paths, key=lambda p: (p != "/", p))


def template_for(client, path):
    """Return the template name a GET of `path` renders."""
    rendered = []
    original = qt_app.render_template

    def capture(name, **context):
        rendered.append(name)
        return original(name, **context)

    qt_app.render_template = capture
    try:
        response = client.get(path)
    finally:
        qt_app.render_template = original

    if response.status_code != 200 or not rendered:
        raise SystemExit(f"{path}: expected a rendered page, got HTTP {response.status_code}")
    return rendered[0]


def last_commit_date(rel_path):
    """Date of the last commit that touched `rel_path` (author date, so a rebase
    or merge that rewrites committer dates cannot move it)."""
    out = subprocess.run(
        ["git", "log", "-1", "--format=%as", "--", rel_path],
        cwd=BASE, capture_output=True, text=True, check=True,
    ).stdout.strip()
    return out or datetime.date.today().isoformat()


EXAMPLE_INCLUDE = re.compile(r'\{%-?\s*include\s+"(components/examples/[^"]+)"')


def content_files(template):
    """The files whose edits change this page's content: its own template plus
    the page-specific components/examples/* partials it includes. Shared chrome
    (base.html, jsonld, byline, breadcrumb, open_tool, upload) is excluded on
    purpose: editing it must not move every page's lastmod."""
    rel = f"templates/{template}"
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        partials = EXAMPLE_INCLUDE.findall(f.read())
    return [rel] + [f"templates/{p}" for p in partials]


def build():
    client = qt_app.app.test_client()
    entries = []
    for path in public_paths():
        template = template_for(client, path)
        lastmod = max(last_commit_date(f) for f in content_files(template))
        entries.append((path, lastmod))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "",
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', ""]
    for path, lastmod in entries:
        lines += ["<url>", f"<loc>{SITE}{path}</loc>", f"<lastmod>{lastmod}</lastmod>", "</url>", ""]
    lines.append("</urlset>")

    with open(SITEMAP, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {len(entries)} URLs to sitemap.xml")


def check():
    xml = open(SITEMAP, encoding="utf-8").read()
    urls = re.findall(r"<url>(.*?)</url>", xml, re.S)
    listed = {}
    for block in urls:
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block).group(1)
        listed[loc.replace(SITE, "", 1)] = "<lastmod>" in block

    routes = set(public_paths())
    missing = sorted(routes - set(listed))
    extra = sorted(set(listed) - routes)
    no_lastmod = sorted(p for p, has in listed.items() if not has)

    print(f"Public GET routes: {len(routes)}    sitemap entries: {len(listed)}")
    for label, items in (("Routes missing from sitemap", missing),
                         ("Sitemap entries with no route", extra),
                         ("Entries without <lastmod>", no_lastmod)):
        print(f"{label}: {len(items)}")
        for item in items:
            print(f"  {item}")

    return 1 if (missing or extra or no_lastmod) else 0


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        sys.exit(check())
    build()
