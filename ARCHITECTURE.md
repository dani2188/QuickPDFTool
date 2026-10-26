# Architecture Overview

This document describes the current architecture of the PDF/Image tools web app as of 2026-10-26. It reflects what exists in the repo today, not a target design.

## 1. Summary

A single-process **Flask** web application, branded **hellobrivio** (one lowercase brand name, also the product name), that offers ~31 browser-based PDF and image conversion/editing tools (compress, merge, split, convert, watermark, sign, redact, resize, remove background, etc.), similar in spirit to iLovePDF/Smallpdf. Image tools (Resize Image, Remove Background, Compress JPG) were merged in from a former separate static site on 2026-08-25 as native routes. There is no build step, no frontend framework, and no database — it's server-rendered HTML + a monolithic Python backend that shells out to external binaries (Ghostscript, LibreOffice), calls one external HTTP API (remove.bg), and uses Python libraries (PyMuPDF, PyPDF2, Pillow, pdf2docx) to do the actual file processing.

## 2. Tech stack

| Layer | Technology |
|---|---|
| Web framework | Flask 3.0.3 (WSGI), served by Gunicorn in production |
| Templates | Jinja2 server-rendered HTML (`templates/`), one `base.html` layout |
| Styling | Single static stylesheet `static/style.css`, no JS bundler, no CSS framework |
| PDF manipulation | `PyMuPDF` (fitz), `PyPDF2`, `pdf2docx`, `reportlab`, `pdfplumber` |
| Image handling | `Pillow` |
| Office conversion | `LibreOffice` (via `subprocess`, headless `--convert-to`) |
| PDF compression | `Ghostscript` (via `subprocess`, `gswin64c`/`gs`) |
| Spreadsheet conversion | `pandas`, `openpyxl` |
| External API | `requests` → remove.bg (background removal only; key via `REMOVE_BG_API_KEY` env var) |
| Deployment target | Render.com (`render.yaml`), Gunicorn (`Procfile`) |

## 3. Code layout

```
app.py                 # entire backend: ~2,718 lines, ~97 routes, all in one file
templates/             # one Jinja2 template per tool page, usually paired with a *_guide.html SEO page
templates/components/  # shared partials (e.g. upload.html)
static/style.css        # single global stylesheet
uploads/                 # scratch directory for user-uploaded and generated files (gitignored)
requirements.txt        # unpinned Python dependencies
Procfile                 # `gunicorn app:app --timeout 180`
render.yaml              # Render.com build: apt-get ghostscript, libreoffice, poppler-utils + pip install
```

There is no `routes/`, `services/`, or `models/` split — every tool (compress, merge, split, rotate, watermark, sign, etc.) is a standalone `@app.route` function directly in `app.py`, each duplicating its own upload/validate/process/cleanup logic.

## 4. Request lifecycle (typical tool)

Every tool follows the same pattern. Saving an upload is shared via `save_upload()`; the processing itself is still written per-route:

1. **GET** `/tool-name` → renders the upload form template.
2. **POST** `/tool-name` → Flask receives the file via `request.files`; `save_upload()` sanitizes the name with `secure_filename()`, prefixes it with `uuid.uuid4()` so concurrent users with the same filename never collide, saves it into `uploads/`, and schedules its deletion. Outputs also get UUID-prefixed internal names.
3. The file is processed **synchronously, in the request thread** — either with a Python library (PyMuPDF/PyPDF2/Pillow) or by shelling out to `gs`/`libreoffice` (`soffice` on Windows) via `subprocess.run(...)`.
4. The result is returned one of three ways:
   - **Single file** → `send_file(..., as_attachment=True, download_name=...)`, so the user gets a friendly name (`invoice.docx`, `protected_invoice.pdf`) rather than the internal UUID name.
   - **Multiple files** (split-pdf, pdf-to-jpg, pdf-to-png, pdf-to-webp, extract-images, compress-jpg) → a result page rendered **synchronously** in the same request, linking each output (and a ZIP where offered) through `/download-file/<filename>`.
   - **compress-pdf only** → the polling flow: a background thread runs Ghostscript, `processing.html` polls `/status/<filename>`, then `/download/<filename>` renders `result.html`. If Ghostscript fails, `compress_pdf()` writes `<output>.error`, `/status` returns `{"ready": false, "error": ...}`, and the processing page stops polling and shows the message (it also gives up client-side after ~3 minutes, matching `--timeout 180`).
5. **Cleanup**: `delete_file_later(path, delay)` spawns a **daemon `threading.Thread`** that sleeps for `delay` seconds (default 300s) then deletes the file. There is no job queue, no cron, and no guarantee cleanup runs if the process restarts before the timer fires.

Invalid input returns a styled 4xx page via `error_page(message, status)` (`templates/error.html`), not a bare string.

Some multi-step tools (`add-text-to-pdf`, `sign-pdf`, `redact-pdf`) render a preview image first, then apply the edit in a second POST referencing the previously uploaded file by its generated `uploads/` filename. That client-supplied name is always passed through `resolve_upload()`, which rejects anything that isn't a plain filename inside `uploads/`.

## 5. Tool inventory (by category)

- **Compression**: compress-pdf (levels: low/medium/extreme/default, via Ghostscript `-dPDFSETTINGS`), compress-pdf-to-1mb, compress-pdf-for-email, compress-jpg (Pillow re-encode, no Ghostscript involved)
- **Merge/Split/Organize**: merge-pdf, split-pdf, delete-pdf-pages, organize-pdf (hub page), rotate-pdf, crop-pdf
- **Conversion — PDF ⇄ image**: pdf-to-jpg, pdf-to-png, pdf-to-webp, jpg-to-pdf, png-to-pdf, svg-to-pdf (PyMuPDF native SVG import, with a custom marker-inlining pre-pass since MuPDF's SVG parser drops most `<marker>`-based arrowheads — see `_inline_svg_markers()`), extract-images
- **Conversion — PDF ⇄ Office**: pdf-to-word, word-to-pdf (LibreOffice), pdf-to-excel, excel-to-pdf (pandas/openpyxl)
- **Conversion — PDF ⇄ text**: pdf-to-text (pdfplumber)
- **Security**: protect-pdf (password), unlock-pdf, redact-pdf (PyMuPDF redaction annotations — permanently strips underlying content, not just a visual overlay; supports black/white/blur/pixelate)
- **Editing/annotation**: add-page-numbers, add-watermark, remove-watermark, add-text-to-pdf, sign-pdf
- **Image tools** (merged in from the former standalone QuickImageTools static site, 2026-08-25): resize-image (server-side Pillow letterbox fit — scales to fit within the target box and pads with white, never crops/stretches), compress-jpg, remove-background (proxies to the remove.bg HTTP API server-side — see §6)
- **Hub / listing pages**: pdf-tools, image-tools, convert-pdf, edit-pdf, organize-pdf (these three are thin hub pages, not processing routes)
- **Marketing/SEO shell**: each tool above has a paired `/how-to-*` guide page, plus `about`, `blog` (+ per-article pages under `/blog/<slug>`), `contact`, `privacy-policy`, `terms`, `sitemap.xml`, `robots.txt`, `ads.txt` (AdSense)

## 6. External process dependencies

Two tool families depend on binaries **not installed via pip** — they must exist on `PATH`:

- **Ghostscript** (`gswin64c` on Windows, `gs` on Linux/Render) — required for all `compress-pdf*` routes.
- **LibreOffice** (`soffice`/`libreoffice --headless`) — required for `word-to-pdf`.

`render.yaml` installs both (plus `poppler-utils`) via `apt-get` in the Render build step. **Locally there is no equivalent setup script** — these must be installed manually on the dev machine, or the compress/word-to-pdf routes will fail (a missing Ghostscript makes compress-pdf show "temporarily unavailable" on the processing page; a missing LibreOffice makes word-to-pdf return a 503 page).

**One route depends on a third-party HTTP API rather than a local binary**: `remove-background` proxies the upload to the remove.bg API server-side, reading the key from the `REMOVE_BG_API_KEY` environment variable (never exposed to the client — the previous standalone image-tools site had this key hardcoded in client-side JS, which is why it was rebuilt as a server-side proxy). If the env var isn't set, the route returns a `503` with a clear message rather than crashing. This is the only tool with a per-request cost and an external service dependency outside this deployment's control; remove.bg's free tier is non-commercial-use-only, so a paid/commercial plan is required for this to run legitimately on an ad-monetized site.

## 7. Deployment

- `Procfile`: `gunicorn app:app --timeout 180`
- `render.yaml`: single Render web service, installs `ghostscript`, `libreoffice`, `poppler-utils` at build time, then `pip install -r requirements.txt`, runs Gunicorn with `--workers 1`.
- `app.py`'s `if __name__ == "__main__"` block also supports running directly with `python app.py` (reads `PORT` env var, defaults to 10000) for local dev without Gunicorn.

### Environment variables

| Variable | Purpose |
|---|---|
| `PORT` | Port for `python app.py` (default 10000); Gunicorn gets its port from `--bind` |
| `REMOVE_BG_API_KEY` | remove.bg key for `/remove-background` (503 if missing) |
| `MAX_IMAGE_MEGAPIXELS` (30), `MAX_PDF_RENDER_MEGAPIXELS` (30), `MAX_WORD_IMAGE_MEGAPIXELS` (20) | Memory limits, see §8 |
| `HEALTH_CHECK_PATH` | Optional: a health-check path set in the Render dashboard, never redirected by the canonical-host hook |

### Canonical host redirect

The one official address is **`https://hellobrivio.com`**. Render also serves the app at its default hostname (`quickpdftool.onrender.com`), so a `before_request` hook in `app.py` (`redirect_to_canonical_host`) sends every request for a host ending in `onrender.com`, or for `www.hellobrivio.com`, to `https://hellobrivio.com` plus the same path and query string. It is not configured in `render.yaml`, `Procfile` or Gunicorn (all unchanged), so it also works when running `python app.py` locally.

- **Status codes:** `301` for GET/HEAD. Form posts and other methods get `308` (also permanent), because a `301` makes browsers turn a POST into a GET and drop the upload. In practice a page loaded on `hellobrivio.com` posts to `hellobrivio.com`, since every form action, the `/status/<file>` poll and the `/download…` links are relative; the `308` only matters for a page that was already open on the old host.
- **Proxy handling:** Render sits behind a proxy. The hook checks both `Host` and every value in `X-Forwarded-Host`, and redirects if any of them is an onrender or www host, so a forged forwarded header can't be used to skip the redirect. `X-Forwarded-Proto` isn't needed, because the target is always `https://hellobrivio.com`.
- **Not an open redirect:** the target origin is a constant (`CANONICAL_ORIGIN`); only the path and query string come from the request, and the path is percent-encoded (so CR/LF can't split the header).
- **Never redirected:** `hellobrivio.com`, `localhost`, IP addresses, and look-alike names such as `notonrender.com` or `onrender.com.evil.io` (the match is on the full domain suffix, not a substring).
- **Health check:** `render.yaml` has **no** `healthCheckPath`, so Render only checks that the port is open and there's nothing to exempt. If a health-check path is set in the Render dashboard, set the `HEALTH_CHECK_PATH` environment variable to the same value; that exact path is then never redirected.
- **Everything we emit already names the canonical origin:** `<link rel="canonical">` and `og:url` are built as `https://hellobrivio.com{{ request.path }}` in `base.html`, and `sitemap.xml`, `robots.txt`, `og:image` and all JSON-LD use the same origin, whichever host the request arrived on.
- **Test:** `scripts/test_canonical_redirect.py` (no server needed) checks the redirect rules, method preservation, look-alike hosts, the health-check exemption, and that every page, `sitemap.xml` and `robots.txt` use `https://hellobrivio.com` and never mention onrender.

## 8. Notable architectural characteristics / risks

- **Monolith file**: all routes live in one 2,718-line `app.py`. Adding a tool means copy-pasting the upload/process/cleanup boilerplate from a similar route.
- **No shared processing/service layer**: saving an upload (UUID name + scheduled deletion) is shared via `save_upload()`, but each tool's actual processing and its output-file handling are still written per-route.
- **Unpinned dependencies**: `requirements.txt` has no version pins (`flask`, `Pillow`, `PyMuPDF`, etc. with no `==`), so `pip install` on Render can silently pick up newer major versions than what's used/tested locally.
- **In-process, in-memory cleanup**: `delete_file_later` uses a sleeping daemon thread per file rather than a scheduled task/cron — cleanup is lost on process restart, and with `--workers 1` this is fine, but it wouldn't scale to multiple Gunicorn workers (each worker has its own thread pool and no shared knowledge of what's pending deletion).
- **Public uploads route**: `/uploads/<filename>` serves anything in `uploads/` directly by filename. Filenames are UUID-prefixed (not guessable), but there's no auth or expiry check at serve time — if the delete-timer hasn't fired yet, the file is downloadable by anyone with the URL.
- **Errors swallowed**: `compress_pdf()` catches all exceptions and just `print()`s them — a Ghostscript failure (e.g., binary not installed) fails silently rather than surfacing an error to the user.
- **20 MB upload cap**: `MAX_CONTENT_LENGTH = 20 * 1024 * 1024` is global across all tools. It bounds a file's *size*, not the *memory* a request needs, which is what matters for the Render instance (see the next bullet). `render.yaml` runs a single Gunicorn worker with no `plan:` set, so Render's default RAM applies (assume 512 MB until confirmed in the Render dashboard).
- **Memory is bounded by pixels and pages, not by file size** (QT-009). Measured with `scripts/measure_memory.py` (a fresh process per scenario, real routes, real files; Windows, Python 3.8, resident memory). The earlier claim that one `pdf-to-word` request permanently adds ~300 MB regardless of input was wrong: `pdf2docx` was imported at module level (so OpenCV/numpy were part of the boot cost) and an ordinary Word conversion adds only about 15-30 MB. What actually spikes memory is inputs that are small on disk but large once decoded:

  | Input (size on disk) | Before | After |
  |---|---|---|
  | boot (`import app`) | 101 MB, 2.1 s | 91 MB, 2.1 s (`pdf2docx` now imported only by `/pdf-to-word`) |
  | `pdf-to-text`, 300-page PDF (0.5 MB) | **793 MB** | 102 MB (pdfplumber pages are now released as they are read; output identical) |
  | `pdf-to-excel`, 300-page PDF (0.5 MB) | 857 MB | 131 MB |
  | resize-image / compress-jpg, 81-megapixel JPEG (1.2 MB) | **762 MB** | rejected with a 400 (limit 30 MP) |
  | `jpg-to-pdf`, same 81 MP JPEG | 762 MB | 101 MB (the JPEG is embedded as-is, so it is only checked, at 1/8 scale) |
  | `pdf-to-jpg`, A0 poster page (0 MB) | 409 MB | 378 MB (scaled to a 30 MP budget) |
  | `pdf-to-jpg`, one 5000 x 5000 pt page (0 MB) | **1057 MB** | 379 MB (scaled to the budget) |
  | `pdf-to-word`, 9-page scan (19 MB) | **583 MB peak** | rejected with a 400 (limit 20 MP of page images) |
  | `pdf-to-word`, ordinary text PDFs (6 / 20 / 100 pages) | 116 / 129 / 185 MB | unchanged |
  | every tool in one process, 5 cycles (heaviest allowed inputs) | peak 1451 MB | peak 809 MB; resident settles at about 515 MB |

  What the guards in `app.py` do (limits are environment variables; raise them if the Render plan has more RAM):
  - `MAX_IMAGE_MEGAPIXELS` (default 30): images that are fully decoded (resize-image, compress-jpg, and non-JPEG images in jpg-to-pdf / png-to-pdf) are rejected with a clear 400 above it. The check reads only the image header.
  - `MAX_PDF_RENDER_MEGAPIXELS` (default 30): PDF pages rendered to images (pdf-to-jpg/png/webp, the sign / add-text / redact previews) use zoom 2 as before and are scaled down only if a page would exceed the budget, so ordinary pages (A4 is about 2 MP) are byte-for-byte unaffected and posters get a slightly lower zoom instead of failing.
  - `MAX_WORD_IMAGE_MEGAPIXELS` (default 20): a PDF whose page images total more than this (about 5 pages scanned at 200 DPI) is rejected by `pdf-to-word`, with advice to split or compress. Peak memory there was about 13 bytes per image pixel.
  - Peak memory while decoding is roughly 9-13 bytes per pixel, so the defaults keep one request under about 400 MB.

  Findings that did **not** need a code change: there is no leak (resident memory is flat across repeated full cycles); Ghostscript peaked at only 19-25 MB on a 19 MB scan and runs as a separate process; and each `delete_file_later()` timer thread costs about 26 KB (1000 sleeping timers = +26 MB), though a 300-page split starts 301 of them.

  Caveats: these numbers are from Windows. Linux (Render) uses a different allocator, so absolute figures will differ; run `scripts/measure_memory.py` on a Linux machine for production-like numbers. The Render plan's real RAM and whether OOM kills have happened are not known from the repository; see QT-029 in `docs/BACKLOG.md` for the options that need a decision (plan size, worker recycling, isolating conversions), none of which are applied.

## 9. Development environment

A project-local virtual environment exists at `.venv/` (Python 3.8) and is what's actually used — `.venv/Scripts/python.exe` / `.venv/Scripts/pip.exe`, not the global interpreter. Activate it with `.venv\Scripts\Activate.ps1` before running `python app.py` or installing dependencies, per `CLAUDE.md` §4.

- `requirements.txt` is still almost entirely unpinned (`flask`, `Pillow`, `PyMuPDF`, etc. with no `==`), with one deliberate exception: `reportlab<4.4.3`, pinned because 4.4.3+ calls `hashlib.md5(usedforsecurity=...)`, which isn't implemented on Python 3.8 and made `add-page-numbers`/`add-watermark`/`excel-to-pdf` throw a 500 until it was pinned back.
- No lockfile (no `requirements-lock.txt`/`poetry.lock`/`Pipfile.lock`), so beyond that one pin, "works on my machine" still isn't fully reproducible — a future `pip install` on Render could pick up a newer major version of any other dependency than what's installed locally.
- Confirmed installed versions in `.venv` as of this writing: Flask 3.0.3, Pillow 10.4.0, PyMuPDF 1.24.11, PyPDF2 3.0.1, reportlab 4.4.2, requests 2.32.4.

Longer term, pin exact versions in `requirements.txt` (or generate a lockfile) so local, CI, and Render installs stay in sync — the reportlab incident is a concrete example of what an unpinned dependency can silently break.
