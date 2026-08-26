# Architecture Guidelines — QuickTools

The architecture every HelloBrivio product follows. QuickTools (renamed from QuickPDFTools on 2026-08-26) is the reference. For the concrete, current-state description of this app see [`../ARCHITECTURE.md`](../ARCHITECTURE.md); this document is the **prescriptive standard** for the family.

---

## 1. Philosophy
- **Boring on purpose.** A Flask monolith with server-rendered templates and one stylesheet. No SPA, no build pipeline, no database.
- **Fast to ship a tool.** Adding a feature = one route + one template (+ one guide template). No infrastructure changes.
- **SEO-native.** Real URLs, real HTML, real content on first byte.
- **Portable standards.** Design system + components are copy-paste reusable across products.
- **Do no harm.** UI/architecture work never alters tool behavior.

## 2. Folder structure
```
app.py                 # routes + processing (monolith)
templates/
  base.html            # global layout + shared JS blocks
  components/          # reusable Jinja partials
  *.html               # tool pages, guides, result screens, error pages
static/style.css       # design system
uploads/               # transient user files (gitignored, auto-deleted)
docs/                  # family standards
render.yaml · Procfile # deploy
robots.txt · sitemap.xml · templates/ads.txt
```

## 3. Component hierarchy
```
base.html  (html, head, chrome, blocks: head, adsense, title, description, content)
└── page template  {% extends "base.html" %}
    ├── {% include "components/upload.html" %}      # shared partial
    ├── design-system classes from style.css
    └── page-specific markup + optional inline <script>
```
Every page extends `base.html`. There are **no standalone `<html>` pages** — even result/processing/error screens extend base so chrome and branding stay consistent.

## 4. Static assets
- One stylesheet: `static/style.css`. No CSS splitting, no preprocessor.
- Icons are emoji; favicon is an inline SVG data-URI (no file).
- No web fonts. Images: `max-width:100%`, `loading="lazy"` below the fold.
- Anything served to users from `uploads/` is UUID-named and time-deleted.

## 5. JavaScript organization
- Vanilla, minimal, inlined. Two shared behaviors in `base.html`:
  1. **Responsive navigation** (hamburger/drawer/overlay).
  2. **Upload** (click, drag-drop, filename display, optional auto-submit; the auto-submit path keys on `#dropArea`/`#fileInput`).
- Page-specific JS (preview drag, polling) lives in that page's template and is guarded against missing elements.
- No bundler; scripts are small enough to inline.

## 6. CSS organization
- Mobile-first, token-driven, sectioned (see PROJECT_STANDARDS §4).
- One source of truth; document changes in DESIGN_SYSTEM.

## 7. Request / processing model
- Tools process **synchronously in the request** using libraries (PyMuPDF, PyPDF2, Pillow, pdf2docx, reportlab, pdfplumber) or by shelling out to system binaries (Ghostscript, LibreOffice).
- Long jobs (compression, rasterization) run in a background thread and the browser polls `/status/<file>` → `/download/<file>` (see `processing.html`).
- Cleanup: `delete_file_later()` schedules deletion via a daemon thread. Upload cap: `MAX_CONTENT_LENGTH` (currently 20 MB).
- **Known scaling caveats** (documented in `../ARCHITECTURE.md`): single Gunicorn worker; `pdf2docx`/`pandas` permanently inflate worker memory; thread-based cleanup is lost on restart. New products should weigh `--max-requests` recycling and per-tool memory before raising limits.

## 8. Deployment
- **Render.com** web service via `render.yaml`: `apt-get` installs `ghostscript`, `libreoffice`, `poppler-utils`, then `pip install -r requirements.txt`.
- **Start:** `gunicorn app:app --workers 1 --timeout 180` (`Procfile` mirrors this).
- Local dev: `python app.py` (reads `PORT`, defaults per file).

## 9. Build process
There is none — that's the point. Deploy = push to the default branch; Render rebuilds. No compile/transpile/minify step. Keep it that way unless a product genuinely needs it.

## 10. Development environment
- Use a project-local virtualenv (`python -m venv .venv`) so dependencies are isolated from the machine's global Python.
- System binaries (Ghostscript, LibreOffice) must be installed separately for the tools that shell out; they are **not** pip-installable.
- Pin dependency versions over time so local and Render installs match.

## 11. Future migration strategy
- If a product outgrows the monolith, split `app.py` by blueprint **without changing URLs** (routes are the public contract).
- Extract shared chrome/CSS into a small internal package or git submodule so all HelloBrivio products consume one design system.
- Introduce a job queue (RQ/Celery) only when synchronous processing becomes the bottleneck; keep the poll-based UX so templates don't change.

## 12. Cross-product integration
- All products share this design system, component library, and standards.
- Cross-link in the nav/footer with the ` ↗` marker (QuickTools ↔ future QuickVideoTools ↔ …). QuickImageTools was merged into QuickTools as native routes (2026-08-25), not cross-linked externally.
- Present a unified identity: each product shows its own name in the header and "Part of the HelloBrivio ecosystem" in the footer.
- When these standards evolve, update the reference implementation (QuickTools) first, then propagate.
