# Project Standards — QuickTools

Development rules shared by every product in the **HelloBrivio / QuickTools** family. QuickPDFTools is the reference implementation; new products (QuickImageTools, QuickVideoTools, QuickAITools) start from these conventions.

Companion docs: [DESIGN_SYSTEM](./DESIGN_SYSTEM.md) · [COMPONENT_LIBRARY](./COMPONENT_LIBRARY.md) · [SEO_GUIDELINES](./SEO_GUIDELINES.md) · [ARCHITECTURE_GUIDELINES](./ARCHITECTURE_GUIDELINES.md).

---

## 1. Tech baseline (non-negotiable)
- **Backend:** Flask (WSGI) monolith, served by Gunicorn.
- **Frontend:** server-rendered Jinja2 templates + one hand-written `static/style.css`.
- **No** frontend framework, **no** npm/webpack build, **no** CSS framework, **no** database, **no** auth.
- Keep it installable with `pip install -r requirements.txt` and runnable with `python app.py`.

## 2. Folder structure
```
app.py                     # all routes + processing logic (monolith by design)
templates/                 # one Jinja template per page
  base.html                # global layout (chrome, blocks, shared JS)
  components/              # reusable partials (e.g. upload.html)
  <tool>.html              # tool page
  <tool>_guide.html        # matching SEO "how-to" page
  <result screens>.html    # processing.html, result.html, split_result.html
static/style.css           # the entire design system
uploads/                   # scratch space for user files (gitignored)
docs/                      # these standards
robots.txt · sitemap.xml · templates/ads.txt
render.yaml · Procfile     # deployment
```

## 3. Naming conventions
- **Routes/URLs:** kebab-case, verb-or-noun-first, stable forever (`/compress-pdf`, `/how-to-compress-pdf`). URLs are an SEO asset — **never rename an existing route.**
- **Templates:** snake_case matching the tool (`compress_pdf.html`, `compress_pdf_guide.html`).
- **View functions:** snake_case describing the action (`compress_pdf_page`).
- **CSS classes:** kebab-case, semantic not presentational (`.tool-card`, `.upload-area`, not `.red-box`).
- **CSS variables:** `--brand`, `--s1`…`--s6`, `--radius`, etc. (see DESIGN_SYSTEM).
- **Files:** lowercase, hyphen/underscore per the tables above; no spaces.

## 4. CSS structure
- One file, organized into the commented sections already in `style.css`: **Tokens → Base → Utilities → Layout → Navigation → Typography → Buttons → Cards → Upload → Forms → SEO content → Preview → Feedback → Result → Footer → Responsive → Reduced-motion.**
- **Mobile-first:** base rules target the smallest screen; scale up with `min-width` queries only.
- Use design tokens (`var(--…)`) instead of literals for color, spacing, radius, shadow.
- No inline styles for anything reusable. (Legacy inline styles — cookie banner, some result markup — are being migrated to classes.)
- Keep specificity low; prefer a single class selector.

## 5. JavaScript structure
- Vanilla JS only, inlined in `base.html` (global behaviors) or in the page that needs it.
- Two shared behaviors live in `base.html`: **responsive-nav** and **upload/drag-drop/auto-submit**. Reuse them; don't fork.
- Guard every handler (`if (!el) return;`) so pages without a given element don't error.
- Progressive enhancement: forms must still submit if JS fails; drag-drop is an enhancement over the native file input.
- Respect `prefers-reduced-motion` (CSS handles the global case).

## 6. Accessibility (must-pass)
- Semantic HTML: `<header> <nav> <main> <footer>`, one `<h1>`, no skipped heading levels.
- All interactive controls reachable and operable by keyboard; visible `:focus-visible` ring.
- Touch targets **≥ 44×44px**.
- `aria-label` / `aria-expanded` / `aria-controls` on custom controls (see the nav).
- `alt` on meaningful images; empty `alt` on decorative ones.
- Never signal state with color alone; pair with text/icon.
- Contrast ≥ WCAG AA.

## 7. SEO (must-pass)
Every indexable page: unique `<title>`, unique meta description, canonical, Open Graph, Twitter Card, one `<h1>`, structured headings, and (where applicable) JSON-LD. Full rules in [SEO_GUIDELINES](./SEO_GUIDELINES.md). Keep `robots.txt`, `sitemap.xml`, `ads.txt` current.

## 8. Responsive design
- Verify at **320 / 480 / 768 / 1024 / 1440px**.
- No horizontal scrolling; wide elements (tables, previews, code) scroll inside their own container.
- Fluid units + `max-width`; avoid fixed pixel widths on containers.

## 9. Performance
- No web fonts (system font stack). No JS frameworks. Keep `style.css` lean and deduplicated.
- `loading="lazy"` on below-the-fold images.
- Avoid layout shift (reserve space for media; the fake progress bar has fixed height).
- Target green Lighthouse across Performance / Accessibility / Best-Practices / SEO.

## 10. Code formatting & comments
- HTML/CSS/JS: 2-space indentation.
- Comment **why**, not what; use the section banners in `style.css`.
- Keep comment density consistent with surrounding code.
- Python: follow the existing style in `app.py`; small focused view functions.

## 11. The one hard constraint
**Never change existing business functionality.** Routes, form field `name`s, file-processing logic, polling endpoints, and deployment config are frozen unless a change is the explicit goal. UI/UX/docs work must preserve every existing tool exactly.
