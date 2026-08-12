# Architecture Overview

This document describes the current architecture of the PDF/Image tools web app as of 2026-08-12. It reflects what exists in the repo today, not a target design.

## 1. Summary

A single-process **Flask** web application that offers ~37 browser-based PDF/image conversion and editing tools (compress, merge, split, convert, watermark, sign, redact, etc.), similar in spirit to iLovePDF/Smallpdf. There is no build step, no frontend framework, and no database — it's server-rendered HTML + a monolithic Python backend that shells out to external binaries (Ghostscript, LibreOffice) and Python libraries (PyMuPDF, PyPDF2, Pillow, pdf2docx) to do the actual file processing.

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
| Deployment target | Render.com (`render.yaml`), Gunicorn (`Procfile`) |

## 3. Code layout

```
app.py                 # entire backend: ~1,956 lines, ~75 routes, all in one file
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

Every tool follows the same manual pattern, repeated per-route rather than shared via a helper:

1. **GET** `/tool-name` → renders the upload form template.
2. **POST** `/tool-name` → Flask receives the file via `request.files`, filename is sanitized with `secure_filename()` and prefixed with `uuid.uuid4()` to avoid collisions, saved into `uploads/`.
3. The file is processed **synchronously, in the request thread** — either with a Python library (PyMuPDF/PyPDF2/Pillow) or by shelling out to `gs`/`libreoffice` via `subprocess.run(...)`.
4. Result is returned via `send_file(..., as_attachment=True)`, or for some tools (compress, pdf-to-jpg/png/webp) via a polling flow: an async thread does the work, `/status/<filename>` is polled from the browser, then `/download/<filename>` streams the result.
5. **Cleanup**: `delete_file_later(path, delay)` spawns a **daemon `threading.Thread`** that sleeps for `delay` seconds (default 300s) then deletes the file. There is no job queue, no cron, and no guarantee cleanup runs if the process restarts before the timer fires.

Some multi-step tools (`add-text-to-pdf`, `sign-pdf`) render a preview image first, then apply the edit in a second POST referencing the previously uploaded file by its generated `uploads/` filename.

## 5. Tool inventory (by category)

- **Compression**: compress-pdf (levels: low/medium/extreme/default, via Ghostscript `-dPDFSETTINGS`), compress-pdf-to-1mb, compress-pdf-for-email
- **Merge/Split/Organize**: merge-pdf, split-pdf, delete-pdf-pages, organize-pdf, rotate-pdf, crop-pdf
- **Conversion — PDF ⇄ image**: pdf-to-jpg, pdf-to-png, pdf-to-webp, jpg-to-pdf, png-to-pdf, extract-images
- **Conversion — PDF ⇄ Office**: pdf-to-word, word-to-pdf (LibreOffice), pdf-to-excel, excel-to-pdf (pandas/openpyxl)
- **Conversion — PDF ⇄ text**: pdf-to-text (pdfplumber)
- **Security**: protect-pdf (password), unlock-pdf
- **Editing/annotation**: add-page-numbers, add-watermark, remove-watermark, add-text-to-pdf, sign-pdf
- **Marketing/SEO shell**: each tool above has a paired `/how-to-*` guide page, plus `about`, `blog`, `contact`, `privacy-policy`, `terms`, `sitemap.xml`, `robots.txt`, `ads.txt` (AdSense)

## 6. External process dependencies

Two tool families depend on binaries **not installed via pip** — they must exist on `PATH`:

- **Ghostscript** (`gswin64c` on Windows, `gs` on Linux/Render) — required for all `compress-pdf*` routes.
- **LibreOffice** (`soffice`/`libreoffice --headless`) — required for `word-to-pdf`.

`render.yaml` installs both (plus `poppler-utils`) via `apt-get` in the Render build step. **Locally there is no equivalent setup script** — these must be installed manually on the dev machine, or the compress/word-to-pdf routes will fail (the compress function currently swallows the error and just prints it, returning no output file rather than raising).

## 7. Deployment

- `Procfile`: `gunicorn app:app --timeout 180`
- `render.yaml`: single Render web service, installs `ghostscript`, `libreoffice`, `poppler-utils` at build time, then `pip install -r requirements.txt`, runs Gunicorn with `--workers 1`.
- `app.py`'s `if __name__ == "__main__"` block also supports running directly with `python app.py` (reads `PORT` env var, defaults to 10000) for local dev without Gunicorn.

## 8. Notable architectural characteristics / risks

- **Monolith file**: all routes live in one 1,956-line `app.py`. Adding a tool means copy-pasting the upload/process/cleanup boilerplate from a similar route.
- **No shared processing/service layer**: file-save, UUID-naming, and cleanup-scheduling logic is duplicated per-route instead of factored into helpers.
- **Unpinned dependencies**: `requirements.txt` has no version pins (`flask`, `Pillow`, `PyMuPDF`, etc. with no `==`), so `pip install` on Render can silently pick up newer major versions than what's used/tested locally.
- **In-process, in-memory cleanup**: `delete_file_later` uses a sleeping daemon thread per file rather than a scheduled task/cron — cleanup is lost on process restart, and with `--workers 1` this is fine, but it wouldn't scale to multiple Gunicorn workers (each worker has its own thread pool and no shared knowledge of what's pending deletion).
- **Public uploads route**: `/uploads/<filename>` serves anything in `uploads/` directly by filename. Filenames are UUID-prefixed (not guessable), but there's no auth or expiry check at serve time — if the delete-timer hasn't fired yet, the file is downloadable by anyone with the URL.
- **Errors swallowed**: `compress_pdf()` catches all exceptions and just `print()`s them — a Ghostscript failure (e.g., binary not installed) fails silently rather than surfacing an error to the user.
- **20 MB upload cap**: `MAX_CONTENT_LENGTH = 20 * 1024 * 1024` is global across all tools. Raised from 10 MB after local testing (below) showed comfortable headroom on processing time; `render.yaml` runs a single Gunicorn worker with no `plan:` set (Render's default/free tier RAM), so this should be re-verified against real Render metrics before pushing the cap any higher.
- **`pdf-to-word` permanently bloats worker memory, independent of file size**: `pdf2docx` pulls in `opencv-python-headless` + `numpy`, both imported lazily on first use. Local testing (Windows, `python3.8.exe`) showed the server process sitting at ~93 MB working set at cold start and staying there through `compress-pdf`/`pdf-to-jpg`/`extract-images` calls — but a single `pdf-to-word` request permanently pushed it to ~394 MB working set / ~598 MB private memory, and it never drops back down (Python doesn't unload C-extension modules). With `--workers 1` on Render, the first `pdf-to-word` (or `pdf-to-excel`/`excel-to-pdf`, which import `pandas`/`openpyxl` the same way) call of the process's lifetime permanently eats a large chunk of whatever RAM the plan has, for every request after it — regardless of upload size. Worth watching for OOM kills on Render independent of the upload-size question.

## 9. Development environment

**There is currently no isolated Python environment for this project.** Findings from inspecting the local machine:

- `python`/`pip` resolve to the **global Windows Store Python 3.8** install (`sys.prefix == sys.base_prefix`), not a virtualenv.
- Flask 3.0.3 and the other dependencies are installed **system-wide**, not scoped to this project.
- `.gitignore` already lists `.venv/`, `__pycache__/`, `*.pyc`, `uploads/`, `.vscode/` — meaning a virtual environment was *anticipated* but never actually created.
- `requirements.txt` has no lockfile (no `requirements-lock.txt`/`poetry.lock`/`Pipfile.lock`) and no version pins, so "works on my machine" isn't reproducible even if a venv is created today.

**Recommendation**: create a project-local virtual environment so dependency versions are isolated from other Python projects on the machine and match what's installed on Render:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Longer term, pin exact versions in `requirements.txt` (or generate a lockfile) so local, CI, and Render installs stay in sync.
