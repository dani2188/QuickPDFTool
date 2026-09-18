"""FAQ visible-content vs. FAQPage JSON-LD consistency validator.

No new dependencies -- plain stdlib plus the app itself. Run from the repo
root:

    .venv\\Scripts\\python.exe scripts\\faq_schema_audit.py

What it does:

1. Discovers every GET route with no URL parameters (via Flask's own
   `app.url_map`, not by guessing from template source), skipping a small
   blocklist of non-page endpoints (static assets, uploads, sitemap/robots,
   generated result screens).
2. Renders each page for real through Flask's test client -- the same
   Jinja environment and macros (`faqpage()`, `howto()`, etc.) the live
   site uses -- so this reflects what a user's browser actually receives,
   not the raw template source.
3. Extracts the visible FAQ: every <h3>/<following content> pair between
   an "<h2>...Frequently Asked Questions...</h2>" heading and the next
   <h2>.
4. Extracts every FAQPage JSON-LD block on the page (there should be at
   most one) and its mainEntity question/answer pairs.
5. Normalizes both sides (HTML-entity unescaping, tag stripping keeping
   inner text, whitespace collapsing) and compares them pair-by-pair, in
   order. Punctuation, dashes, quotes, and case are NOT normalized away --
   an em dash ("—") and a double hyphen ("--") are different text and
   must be reported as a mismatch, since that is exactly the class of bug
   this script exists to catch.
6. Reports, per page: PASS (all pairs match), FAIL (with the exact
   mismatching question/answer text from both sides), NO_FAQ (no visible
   FAQ section), or a flag for FAQPage JSON-LD present with no visible
   FAQ backing it (schema without content).

This is a diagnostic script, not a build-blocking test -- it prints a
report and exits 0 regardless of findings, matching the existing
`content_audit.py` convention.
"""

import json
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

import app as qt_app  # noqa: E402  (the actual QuickTools Flask app)

# Endpoints that are not real indexable content pages, or whose GET
# response isn't a static page render -- skip them.
SKIP_RULES_CONTAINING = (
    "/static/", "/uploads/", "/download/", "/status/",
)
SKIP_EXACT_PATHS = {
    "/sitemap.xml", "/robots.txt", "/ads.txt",
}


def discover_pages():
    """Every GET route with no URL parameters, via Flask's own routing
    table -- not a regex guess at app.py source."""
    pages = []
    for rule in qt_app.app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        if rule.arguments:  # dynamic segments like <filename>
            continue
        path = str(rule)
        if path in SKIP_EXACT_PATHS:
            continue
        if any(s in path for s in SKIP_RULES_CONTAINING):
            continue
        pages.append(path)
    return sorted(set(pages))


def extract_visible_faq(html):
    """Return [(question_text, answer_text), ...] for the FAQ section,
    or [] if there isn't one. The FAQ section heading is normally <h2>
    with individual questions as <h3> (the sitewide convention), but at
    least one page (redact_pdf.html) nests one level deeper (<h3> section
    heading, <h4> questions) -- so this detects whatever heading level
    the "Frequently Asked Questions" heading itself uses, then treats the
    next heading level down as the question markers, stopping at the next
    heading of the same level as the section heading (or higher)."""
    section_m = re.search(
        r"<h([1-6])[^>]*>\s*(?:[^<]*?)Frequently Asked Questions(?:[^<]*?)</h\1>",
        html, re.I,
    )
    if not section_m:
        return []
    section_level = int(section_m.group(1))
    question_level = section_level + 1
    start = section_m.end()

    # Section ends at the next heading of the same level or shallower, the
    # closing </article> tag, or the page's global <footer> -- whichever
    # comes first. Without this, a FAQ section that's the last thing in
    # the article (no trailing <h1>/<h2> to stop at) would otherwise
    # swallow the rest of the document -- footer, nav, inline scripts --
    # into the last answer's text.
    remainder = html[start:]
    candidates = []
    end_m = re.search(rf"<h[1-{section_level}][^>]*>", remainder, re.I)
    if end_m:
        candidates.append(end_m.start())
    article_m = re.search(r"</article>", remainder, re.I)
    if article_m:
        candidates.append(article_m.start())
    footer_m = re.search(r"<footer[ >]", remainder, re.I)
    if footer_m:
        candidates.append(footer_m.start())
    section = remainder[:min(candidates)] if candidates else remainder

    # Split into (question, answer_html) blocks on each question-level heading.
    parts = re.split(rf"<h{question_level}[^>]*>(.*?)</h{question_level}>", section, flags=re.S)
    pairs = []
    for i in range(1, len(parts) - 1, 2):
        question_html = parts[i]
        answer_html = parts[i + 1]
        # A genuine FAQ answer is prose in a <p>. Several pages follow the
        # FAQ block with a same-level "More Tools"/"Related PDF Tools"
        # heading pointing at a .tools-mini-grid link list instead of a
        # <p> -- that's not a question/answer pair, and its presence marks
        # the end of the real FAQ content within this section.
        if "<p" not in answer_html:
            break
        pairs.append((normalize(question_html), normalize(answer_html)))
    return pairs


def extract_faqpage_jsonld(html):
    """Return [(question_text, answer_text), ...] from every FAQPage
    JSON-LD block on the page (normally 0 or 1 blocks)."""
    blocks = re.findall(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        html, re.S,
    )
    pairs = []
    for b in blocks:
        try:
            obj = json.loads(b)
        except json.JSONDecodeError:
            continue
        if obj.get("@type") != "FAQPage":
            continue
        for item in obj.get("mainEntity", []):
            q = normalize(item.get("name", ""))
            a = normalize(item.get("acceptedAnswer", {}).get("text", ""))
            pairs.append((q, a))
    return pairs


def has_faqpage_block(html):
    for b in re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.S):
        try:
            if json.loads(b).get("@type") == "FAQPage":
                return True
        except json.JSONDecodeError:
            continue
    return False


def normalize(s):
    """Unescape HTML entities, strip tags (keeping inner text), collapse
    whitespace. Deliberately does NOT touch punctuation, dashes, quotes,
    or case -- those differences are exactly what this script must
    detect, not hide."""
    s = unescape(s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def audit_page(path, client):
    resp = client.get(path)
    if resp.status_code != 200:
        return {"path": path, "status": "HTTP_ERROR", "code": resp.status_code}

    html = resp.get_data(as_text=True)
    visible = extract_visible_faq(html)
    jsonld = extract_faqpage_jsonld(html)
    emits_faqpage = has_faqpage_block(html)

    if not visible and not emits_faqpage:
        return {"path": path, "status": "NO_FAQ"}

    if visible and not emits_faqpage:
        return {"path": path, "status": "MISSING_SCHEMA", "visible_count": len(visible), "visible": visible}

    if emits_faqpage and not visible:
        return {"path": path, "status": "SCHEMA_WITHOUT_CONTENT", "jsonld_count": len(jsonld)}

    # Both exist -- compare pair by pair, in order.
    mismatches = []
    max_len = max(len(visible), len(jsonld))
    for i in range(max_len):
        v = visible[i] if i < len(visible) else None
        j = jsonld[i] if i < len(jsonld) else None
        if v is None:
            mismatches.append({
                "index": i, "kind": "extra_jsonld_entry",
                "jsonld_q": j[0], "jsonld_a": j[1],
            })
        elif j is None:
            mismatches.append({
                "index": i, "kind": "missing_jsonld_entry",
                "visible_q": v[0], "visible_a": v[1],
            })
        else:
            vq, va = v
            jq, ja = j
            if vq != jq or va != ja:
                mismatches.append({
                    "index": i, "kind": "content_mismatch",
                    "visible_q": vq, "visible_a": va,
                    "jsonld_q": jq, "jsonld_a": ja,
                    "q_matches": vq == jq, "a_matches": va == ja,
                })

    if mismatches:
        return {"path": path, "status": "FAIL", "pair_count": len(visible), "mismatches": mismatches}
    return {"path": path, "status": "PASS", "pair_count": len(visible)}


def main():
    client = qt_app.app.test_client()
    pages = discover_pages()

    results = [audit_page(p, client) for p in pages]

    if "--json" in sys.argv:
        out_path = sys.argv[sys.argv.index("--json") + 1] if sys.argv.index("--json") + 1 < len(sys.argv) and not sys.argv[sys.argv.index("--json") + 1].startswith("-") else None
        payload = json.dumps(results, indent=2)
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(payload)
            print(f"Wrote machine-readable report to {out_path}")
        else:
            print(payload)
        return 0

    n_checked = len(results)
    n_http_error = sum(1 for r in results if r["status"] == "HTTP_ERROR")
    n_no_faq = sum(1 for r in results if r["status"] == "NO_FAQ")
    n_visible_faq = sum(1 for r in results if r["status"] not in ("NO_FAQ", "HTTP_ERROR"))
    n_missing_schema = sum(1 for r in results if r["status"] == "MISSING_SCHEMA")
    n_schema_without_content = sum(1 for r in results if r["status"] == "SCHEMA_WITHOUT_CONTENT")
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_emits_faqpage = n_pass + n_fail + n_schema_without_content

    print(f"Checked {n_checked} GET pages (no URL parameters, via app.url_map).")
    print(f"  HTTP errors:                 {n_http_error}")
    print(f"  No visible FAQ section:      {n_no_faq}")
    print(f"  Have a visible FAQ or FAQPage schema: {n_visible_faq}")
    print(f"  Emit FAQPage JSON-LD:        {n_emits_faqpage}")
    print(f"    PASS (exact match):        {n_pass}")
    print(f"    FAIL (mismatch):           {n_fail}")
    print(f"  Visible FAQ but NO schema (QT-006 candidates): {n_missing_schema}")
    print(f"  FAQPage schema but NO visible FAQ (orphan schema): {n_schema_without_content}")
    print()

    if n_http_error:
        print("=== HTTP ERRORS ===")
        for r in results:
            if r["status"] == "HTTP_ERROR":
                print(f"  {r['path']}: HTTP {r['code']}")
        print()

    if n_fail:
        print("=== FAILING PAGES (FAQ mismatch) ===")
        for r in results:
            if r["status"] != "FAIL":
                continue
            print(f"\nFAIL: {r['path']} -- {len(r['mismatches'])} mismatch(es) of {r['pair_count']} pairs")
            for m in r["mismatches"]:
                if m["kind"] == "content_mismatch":
                    print(f"  FAQ #{m['index']+1}:")
                    if not m["q_matches"]:
                        print(f"    question mismatch:")
                        print(f"      visible: {m['visible_q']!r}")
                        print(f"      jsonld : {m['jsonld_q']!r}")
                    if not m["a_matches"]:
                        print(f"    answer mismatch:")
                        print(f"      visible: {m['visible_a']!r}")
                        print(f"      jsonld : {m['jsonld_a']!r}")
                elif m["kind"] == "missing_jsonld_entry":
                    print(f"  FAQ #{m['index']+1}: visible question has NO matching JSON-LD entry")
                    print(f"    visible: {m['visible_q']!r}")
                elif m["kind"] == "extra_jsonld_entry":
                    print(f"  FAQ #{m['index']+1}: JSON-LD has an entry with NO visible question")
                    print(f"    jsonld: {m['jsonld_q']!r}")
        print()

    if n_missing_schema:
        print("=== VISIBLE FAQ BUT NO FAQPage SCHEMA (QT-006 candidates) ===")
        for r in results:
            if r["status"] == "MISSING_SCHEMA":
                print(f"  {r['path']}: {r['visible_count']} visible FAQ pairs, no schema")
        print()

    if n_schema_without_content:
        print("=== FAQPage SCHEMA WITH NO VISIBLE FAQ (orphan schema) ===")
        for r in results:
            if r["status"] == "SCHEMA_WITHOUT_CONTENT":
                print(f"  {r['path']}: {r['jsonld_count']} JSON-LD entries, no visible FAQ section found")
        print()

    if n_pass:
        print("=== PASSING PAGES ===")
        for r in results:
            if r["status"] == "PASS":
                print(f"  PASS: {r['path']} -- {r['pair_count']}/{r['pair_count']} FAQ pairs match")

    return 0


if __name__ == "__main__":
    sys.exit(main())
