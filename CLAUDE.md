# CLAUDE.md — Rules to check FIRST, before any action

This is **QuickTools**, a product in the **HelloBrivio** ecosystem: a Flask monolith of ~38 browser-based PDF/image tools (server-rendered Jinja templates + one hand-written stylesheet). Read this before making changes.

---

## 1. Read the relevant reference doc BEFORE editing

Do not guess conventions — the standards are written down. Consult the matching doc first:

| Before you touch… | Read first |
|---|---|
| Colors, spacing, typography, buttons, breakpoints | [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) |
| A UI component (navbar, upload, cards, footer, spinner…) | [docs/COMPONENT_LIBRARY.md](docs/COMPONENT_LIBRARY.md) |
| Naming, folders, CSS/JS structure, code style | [docs/PROJECT_STANDARDS.md](docs/PROJECT_STANDARDS.md) |
| Titles, meta, canonical, sitemap, JSON-LD, links | [docs/SEO_GUIDELINES.md](docs/SEO_GUIDELINES.md) |
| Routes, processing, deployment, project layout | [docs/ARCHITECTURE_GUIDELINES.md](docs/ARCHITECTURE_GUIDELINES.md) |
| Current concrete state, memory/scaling caveats | [ARCHITECTURE.md](ARCHITECTURE.md) |

**Single source of truth for design:** [static/style.css](static/style.css) (tokens + all components). If a doc and the stylesheet disagree, the stylesheet wins — then update the doc.

**Global layout:** [templates/base.html](templates/base.html). Every page extends it; there are no standalone `<html>` pages.

---

## 2. Hard constraints — do NOT change (unless that IS the explicit task)

- **Routes / URLs** — kebab-case, frozen. URLs are an SEO asset; never rename an existing route.
- **Form field `name`s, input `id`s** (e.g. `pdf`, `target_size`, `email_opt`, `fileInput`) and `<form>` actions — the backend depends on them.
- **File-processing logic**, the background-thread + `/status/<file>` → `/download/<file>` polling flow, and `delete_file_later()` cleanup.
- **Deployment**: `render.yaml`, `Procfile`, Gunicorn config (`--workers 1 --timeout 180`).
- No new frontend/CSS framework, no build step, no npm, no database, no auth.

The standing rule for UI/docs/architecture work: **preserve all existing tool functionality exactly.**

---

## 3. Branding model (get names right)

- **HelloBrivio** = the ecosystem/company. **QuickTools** = this product (renamed from QuickPDFTools on 2026-08-26, since it now covers image tools too, not just PDFs).
- Header shows the product name (**QuickTools**). Footer says **"Part of the HelloBrivio ecosystem"** with sibling cross-links (future QuickVideoTools / QuickAITools).
- **Image tools are first-party, not a sibling product.** The former standalone QuickImageTools site was merged in (2026-08-25): Resize Image, Remove Background, and Compress JPG are native routes here, not external links. Its content (blog guides) was ported into `/blog`. Do not re-add an external `quickimagetools.onrender.com` link to the nav/footer.
- The 2026-08-26 rename was propagated everywhere in one pass — page titles, meta descriptions, JSON-LD, and body copy across every page — unlike the previous QuickPDFTool → QuickPDFTools rename, which was chrome-only. There should be no live "QuickPDFTools" text left; if you find one, fix it.

---

## 4. Environment & how to run

- Use the project-local venv: `.venv\Scripts\Activate.ps1` (Windows) then `python app.py` → http://localhost:10000.
- Deps: `pip install -r requirements.txt` (unpinned). Python 3.8 currently.
- **System binaries required and NOT pip-installable:** Ghostscript (`gswin64c`/`gs`, all `compress-*` tools) and LibreOffice (`soffice`, `word-to-pdf`). If a compress/convert route "does nothing", check these are installed.

---

## 5. Verify before committing

- Start the app and exercise the affected route end-to-end (upload → process → download), not just a page load. The compress flow is: POST `/compress-pdf` → `processing.html` polls `/status/<file>` → `/download/<file>` → `result.html`.
- Responsive check at 320 / 480 / 768 / 1024 / 1440px; no horizontal scroll; touch targets ≥ 44px.
- Put temp/test files in the scratchpad, not the repo. Clean `uploads/` after testing.
- Commit only when asked. Branch off `master` if the task warrants it. **Push only when the user asks.**

---

## 6. When you add a tool (the standard pattern)

1. Add the route in [app.py](app.py) (kebab-case), reusing helpers (`secure_filename` + UUID naming, `delete_file_later`).
2. Create `templates/<tool>.html` extending `base.html`; use `{% include "components/upload.html" %}` for the upload UI.
3. Add a matching `/how-to-<tool>` guide template.
4. Add the new URL(s) to [sitemap.xml](sitemap.xml).
5. Add related-tool links (`.tools-mini-grid`) and keep icons consistent with DESIGN_SYSTEM §9.
