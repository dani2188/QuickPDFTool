"""Check the canonical-host redirect in app.py.

Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\test_canonical_redirect.py

Uses Flask's test client with fake Host / X-Forwarded-Host headers, so it
needs no server and makes no network calls. Verifies that onrender.com and
www.hellobrivio.com requests get a permanent redirect to
https://hellobrivio.com with the path and query string kept, that form
posts keep their method (308), that the canonical host, localhost and
look-alike hostnames are served normally, and that the optional
HEALTH_CHECK_PATH is exempt. It then confirms every page, sitemap.xml and
robots.txt use https://hellobrivio.com and never mention onrender. Exits 1
on any failure.
"""

import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import app as qt_app  # noqa: E402  (the actual hellobrivio Flask app)

client = qt_app.app.test_client()
ORIGIN = "https://hellobrivio.com"
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


def redirects(name, method, path, host, expect_code, expect_location, **kw):
    headers = {"Host": host, **kw.pop("headers", {})}
    r = getattr(client, method)(path, headers=headers, **kw)
    check(name, r.status_code == expect_code and r.headers.get("Location") == expect_location,
          f"{r.status_code} {r.headers.get('Location')}")


def served(name, host, path="/about", expect=200, method="get", **kw):
    r = getattr(client, method)(path, headers={"Host": host}, **kw)
    check(name, r.status_code == expect and "Location" not in r.headers, f"{r.status_code} {r.headers.get('Location')}")


# --- redirected requests -----------------------------------------------------
redirects("onrender root", "get", "/", "quickpdftool.onrender.com", 301, ORIGIN + "/")
redirects("path and query string kept", "get", "/pdf-to-word?a=1&b=x%20y", "quickpdftool.onrender.com", 301,
          ORIGIN + "/pdf-to-word?a=1&b=x%20y")
redirects("any *.onrender.com host", "get", "/about", "other-app.onrender.com", 301, ORIGIN + "/about")
redirects("host with a port", "get", "/about", "quickpdftool.onrender.com:443", 301, ORIGIN + "/about")
redirects("upper-case host", "get", "/about", "QuickPDFTool.OnRender.com", 301, ORIGIN + "/about")
redirects("trailing-dot host", "get", "/about", "quickpdftool.onrender.com.", 301, ORIGIN + "/about")
redirects("www.hellobrivio.com", "get", "/blog", "www.hellobrivio.com", 301, ORIGIN + "/blog")
redirects("X-Forwarded-Host (as Render's proxy sends it)", "get", "/about", "hellobrivio.com", 301, ORIGIN + "/about",
          headers={"X-Forwarded-Host": "quickpdftool.onrender.com", "X-Forwarded-Proto": "https"})
redirects("X-Forwarded-Host list", "get", "/about", "internal.local", 301, ORIGIN + "/about",
          headers={"X-Forwarded-Host": "quickpdftool.onrender.com, 10.0.0.1"})
redirects("a forged forwarded host can't dodge it", "get", "/about", "quickpdftool.onrender.com", 301, ORIGIN + "/about",
          headers={"X-Forwarded-Host": "hellobrivio.com"})
redirects("HEAD", "head", "/about", "quickpdftool.onrender.com", 301, ORIGIN + "/about")
redirects("static files", "get", "/static/style.css", "quickpdftool.onrender.com", 301, ORIGIN + "/static/style.css")
redirects("unicode path is percent-encoded", "get", "/café", "quickpdftool.onrender.com", 301, ORIGIN + "/caf%C3%A9")
r = client.get("/a%0d%0aSet-Cookie:x=1", headers={"Host": "quickpdftool.onrender.com"})
check("CR/LF in the path can't split the header", "\r" not in r.headers["Location"] and "\n" not in r.headers["Location"])

# --- form posts keep their method (a 301 would turn them into GETs) ----------
for method in ("post", "put", "delete"):
    redirects(f"{method.upper()} -> 308", method, "/compress-pdf", "quickpdftool.onrender.com", 308, ORIGIN + "/compress-pdf")
redirects("multipart upload -> 308 with query", "post", "/pdf-to-text?x=1", "quickpdftool.onrender.com", 308,
          ORIGIN + "/pdf-to-text?x=1", data={"pdf": (io.BytesIO(b"%PDF"), "a.pdf")}, content_type="multipart/form-data")

# --- served normally ------------------------------------------------------------
for label, host in (("canonical host", "hellobrivio.com"), ("localhost:port", "localhost:10000"),
                    ("127.0.0.1:port", "127.0.0.1:10000"), ("IPv6 literal", "[::1]:10000"),
                    ("look-alike notonrender.com", "notonrender.com"),
                    ("look-alike onrender.com.evil.io", "onrender.com.evil.io"),
                    ("look-alike www.hellobrivio.com.evil.io", "www.hellobrivio.com.evil.io")):
    served("served, not redirected: " + label, host)
served("canonical POST reaches the route (400 = missing file)", "hellobrivio.com", "/pdf-to-text", 400, "post")

# --- optional health-check exemption ----------------------------------------------
qt_app.HEALTH_CHECK_PATH = "/healthz"
served("HEALTH_CHECK_PATH is exempt (404 = not redirected)", "quickpdftool.onrender.com", "/healthz", 404)
redirects("the exemption is an exact match", "get", "/healthz2", "quickpdftool.onrender.com", 301, ORIGIN + "/healthz2")
qt_app.HEALTH_CHECK_PATH = None

# --- everything we emit names the canonical origin -------------------------------
canonical_host = {"Host": "hellobrivio.com"}
rules = sorted(r.rule for r in qt_app.app.url_map.iter_rules()
               if "GET" in r.methods and not r.arguments and not r.rule.startswith("/static"))
for path in rules:
    html = client.get(path, headers=canonical_host).get_data(as_text=True)
    problems = []
    if re.search(r"onrender|quickpdftool", html, re.I):
        problems.append("mentions onrender/quickpdftool")
    if path not in ("/sitemap.xml", "/robots.txt", "/ads.txt"):
        if re.findall(r'<link rel="canonical" href="([^"]+)"', html) != [ORIGIN + path]:
            problems.append("canonical")
        if re.findall(r'property="og:url" content="([^"]+)"', html) != [ORIGIN + path]:
            problems.append("og:url")
        if re.search(r'(?:href|src|content)="(?:http://hellobrivio|https?://www\.hellobrivio)', html):
            problems.append("non-canonical own-domain URL")
    if problems:
        check(f"{path}: domain", False, ", ".join(problems))
check(f"all {len(rules)} pages + sitemap/robots/ads.txt use {ORIGIN}", not any(f.endswith(": domain") for f in failures))

sitemap = client.get("/sitemap.xml", headers=canonical_host).get_data(as_text=True)
check("every sitemap <loc> starts with " + ORIGIN + "/",
      all(u.startswith(ORIGIN + "/") for u in re.findall(r"<loc>(.*?)</loc>", sitemap)))
check("robots.txt Sitemap line is canonical",
      ("Sitemap: " + ORIGIN + "/sitemap.xml") in client.get("/robots.txt", headers=canonical_host).get_data(as_text=True))

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
