"""Near-duplicate content audit: tool pages vs. their how-to guides.

No new dependencies -- plain stdlib plus the app itself. Run from the repo
root:

    .venv\\Scripts\\python.exe scripts\\similarity_audit.py [--threshold 0.35]

Google tends to treat pairs of pages that walk through the same steps in
the same words as templated / doorway content. Each tool has a landing page
and a /how-to-* guide, so this checks that each pair (and every pair of
guides) says genuinely different things.

What it does:

1. Renders every tool page and every /how-to-* guide through Flask's test
   client, so it measures what a browser actually receives.
2. Keeps only the page's own content: the text inside <main>, minus
   scripts/styles, the breadcrumb trail, the byline, the upload widget, and
   the shared related-tool link grids (.tools-mini-grid / .more-tools /
   .tools-links / .browse-tools), which are navigation, not content.
3. Splits the text into lowercase word 5-grams (shingles) and computes the
   Jaccard similarity |A & B| / |A | B| for:
     - each tool page against its own guide, and
     - every pair of guides.
4. Prints every pair at or above the threshold (default 0.35), then the
   ten highest-scoring pairs of each kind for context.

Exits 1 if any pair is at or above the threshold, so it can gate a check
script; it changes no files.
"""

import itertools
import os
import re
import sys
from html import unescape

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import app as qt_app  # noqa: E402  (the actual hellobrivio Flask app)

SHINGLE = 5

# Guides whose slug isn't simply "how-to-" + the tool's path.
GUIDE_FOR_TOOL = {
    "/delete-pdf-pages": "/how-to-delete-pdf-pages",
    "/add-watermark": "/how-to-add-watermark-pdf",
    "/remove-watermark": "/how-to-remove-watermark-pdf",
    "/extract-images": "/how-to-extract-images-from-pdf",
    "/pdf-to-text": "/how-to-extract-text-from-pdf",
}

# Elements whose whole subtree is navigation/boilerplate, not page content.
STRIP_BLOCKS = [
    r'<nav class="breadcrumb".*?</nav>',
    r'<p class="byline">.*?</p>',
]
STRIP_CLASSES = ("tools-mini-grid", "more-tools", "tools-links", "browse-tools", "upload-box", "drop-area")


def strip_div_by_class(html, cls):
    """Remove every <div class="... cls ..."> element, including nested divs."""
    pattern = re.compile(r'<div[^>]*class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>')
    while True:
        m = pattern.search(html)
        if not m:
            return html
        depth, i = 1, m.end()
        tag = re.compile(r"<(/?)div\b[^>]*>")
        while depth and i < len(html):
            t = tag.search(html, i)
            if not t:
                i = len(html)
                break
            depth += -1 if t.group(1) else 1
            i = t.end()
        html = html[:m.start()] + " " + html[i:]


def page_text(client, path):
    html = client.get(path).get_data(as_text=True)
    main = re.search(r"<main\b.*?>(.*)</main>", html, re.S)
    html = main.group(1) if main else html
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    for block in STRIP_BLOCKS:
        html = re.sub(block, " ", html, flags=re.S)
    for cls in STRIP_CLASSES:
        html = strip_div_by_class(html, cls)
    text = unescape(re.sub(r"<[^>]+>", " ", html)).lower()
    return re.findall(r"[a-z0-9]+(?:['’][a-z]+)?", text)


def shingles(words):
    return {tuple(words[i:i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def main():
    threshold = 0.35
    if "--threshold" in sys.argv:
        threshold = float(sys.argv[sys.argv.index("--threshold") + 1])

    rules = {r.rule for r in qt_app.app.url_map.iter_rules() if "GET" in r.methods and not r.arguments}
    guides = sorted(r for r in rules if r.startswith("/how-to-"))
    pairs = []
    for guide in guides:
        tool = next((t for t, g in GUIDE_FOR_TOOL.items() if g == guide), "/" + guide[len("/how-to-"):])
        if tool in rules:
            pairs.append((tool, guide))
        else:
            print(f"  (no tool page found for {guide})")

    client = qt_app.app.test_client()
    sh = {p: shingles(page_text(client, p)) for p in rules if p in guides or any(p == t for t, _ in pairs)}

    tool_scores = sorted(((jaccard(sh[t], sh[g]), t, g) for t, g in pairs), reverse=True)
    guide_scores = sorted(((jaccard(sh[a], sh[b]), a, b) for a, b in itertools.combinations(guides, 2)), reverse=True)

    flagged = [s for s in tool_scores + guide_scores if s[0] >= threshold]
    print(f"Compared {len(pairs)} tool/guide pairs and {len(guide_scores)} guide/guide pairs "
          f"({SHINGLE}-word shingles, threshold {threshold}).\n")
    print(f"=== Pairs at or above {threshold}: {len(flagged)} ===")
    for score, a, b in flagged:
        print(f"  [SIMILAR] {score:.3f}  {a}  <->  {b}")

    print("\n=== Top 10 tool/guide pairs ===")
    for score, a, b in tool_scores[:10]:
        print(f"  {score:.3f}  {a}  <->  {b}")
    print("\n=== Top 10 guide/guide pairs ===")
    for score, a, b in guide_scores[:10]:
        print(f"  {score:.3f}  {a}  <->  {b}")

    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
