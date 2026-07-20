# Component Library — QuickPDFTools

Reusable UI building blocks. Everything here is plain server-rendered HTML + classes from [`static/style.css`](../static/style.css) — **no framework, no build step**. Most components live in [`templates/base.html`](../templates/base.html) (shared chrome) or are inlined into page templates; the upload card is a Jinja partial in [`templates/components/`](../templates/components/).

For each component: **Purpose · Structure · CSS classes · Responsive · Accessibility.**

---

## Navbar
- **Purpose:** primary site navigation; shows the product name and top-level links.
- **Structure:** `<header class="topbar">` → `.header-wrapper` → `.logo` + `.nav-desktop` + `.nav-toggle`.
- **CSS:** `.topbar` (sticky, white, shadow), `.nav-desktop` (flex, hidden `<768px`), `.logo a` (brand red).
- **Responsive:** desktop links appear `≥768px`; below that they are hidden and the hamburger takes over.
- **A11y:** `<nav aria-label="Primary">`; links are real `<a href>`; focus-visible outline.

## Mobile Navigation
- **Purpose:** off-canvas menu for small screens.
- **Structure:** `.nav-toggle` (hamburger, 3 `<span>`) + `.nav-overlay` + `.nav-drawer` (with `.nav-close`). Toggled by the script in `base.html` adding `.nav-open` to `<body>`.
- **CSS:** `.nav-drawer` slides via `transform: translateX(100%)` → `0`; `.nav-overlay` fades; `.nav-open` locks body scroll.
- **Responsive:** hamburger + drawer only `<768px` (hidden above).
- **A11y:** `aria-controls`, `aria-expanded` on the toggle; `aria-hidden` on the drawer; closes on Escape / overlay click / link click; focus moves to the close button on open and back to the toggle on close.

## Hero
- **Purpose:** page intro (title + subtitle + trust chips).
- **Structure:** `<h1>` + `.subtitle` + `.features` (chips).
- **CSS:** fluid `h1`, `.subtitle`, `.feature`.
- **Responsive:** chips wrap; `h1` scales with `clamp()`.
- **A11y:** exactly one `<h1>` per page.

## CTA Button
- **Purpose:** primary/secondary actions.
- **Structure:** `<a class="main-btn">` or `<button class="main-btn">`.
- **CSS:** `.main-btn` + variants `.btn-secondary` / `.btn-success` / `.btn-danger`.
- **Responsive:** min-height 44px; comfortable tap target everywhere.
- **A11y:** use `<button>` for actions, `<a>` for navigation; visible focus ring.

## Trust Badge
- **Purpose:** reassurance chips (fast / secure / no install).
- **Structure:** `.features` → `.feature` items.
- **CSS:** `.feature` (`--surface-2` pill).
- **Responsive:** flex-wrap, centered.
- **A11y:** decorative emoji; keep the text label meaningful.

## Tool Card
- **Purpose:** entry point to a tool on the homepage / listings.
- **Structure:** `<a href class="tool-card">` → `.tool-card-icon` + `.tool-card-title` + `.tool-card-desc`.
- **CSS:** `.tool-card`, `.tools-grid` (1/2/4 columns).
- **Responsive:** grid reflows at 640 / 1024px.
- **A11y:** whole card is one link; icon is emoji; hover **and** `:active` feedback.

## Upload Area
- **Purpose:** file selection + drag & drop.
- **Structure (shared partial):** [`templates/components/upload.html`](../templates/components/upload.html) — `<label class="upload-area" for="fileInput">` wrapping `<input type="file" id="fileInput" name="{{ input_name }}">` + `.upload-content` (`.upload-text`, `#fileName`). Configurable via `input_name`, `accept_types`, `multiple`.
- **Alt pattern:** pages needing drag-drop + auto-submit use `<div id="dropArea" class="upload-box">` with a `hidden` `#fileInput`, driven by the global upload script in `base.html`.
- **CSS:** `.upload-area` / `.upload-box` (dashed card, `⬆` via `::before`, 44px min). The file input is visually hidden but reachable via the label.
- **Responsive:** `max-width: 560px`, generous padding, large tap area.
- **A11y:** `<label for>` association; `aria-label="Upload file"`; `required` preserved.
- **⚠️ Do not** change the input `name`, `id`, or the surrounding `<form>` action — the backend depends on them.

## Preview Area
- **Purpose:** show a rendered page/image before an action (sign, add-text, results).
- **Structure:** `.relative-container` → `#pdfPreview` (or `.preview-image`), optional `#signatureWrapper` overlay.
- **CSS:** `#pdfPreview { max-width:100%; pointer-events:none }`, `.preview-image { max-width:100% }`.
- **Responsive:** images scale to container; aspect ratio preserved; never overflow.
- **A11y:** provide `alt` on preview images; interactive overlays get keyboard-reachable controls where feasible.

## Feature Grid
- **Purpose:** list tools or benefits in a responsive grid.
- **Structure:** `.tools-grid` of `.tool-card`s, or `.benefits` / `.steps` lists.
- **CSS:** `.tools-grid`, `.benefits`, `.steps` (+ `.step-number`).
- **Responsive:** 1 → 2 → 4 columns.
- **A11y:** ordered steps use `<ol>`-style numbering via `.step-number` on `<li>`.

## FAQ Accordion
- **Purpose:** collapsible Q&A (currently rendered as static `<h3>` + `<p>` inside `.seo-content`).
- **Recommended structure:** native `<details><summary>` for zero-JS accordions.
- **CSS:** style `summary` as a 44px tappable row; brand focus ring.
- **A11y:** `<details>` is keyboard- and screen-reader-native; prefer it over custom JS.

## Blog Card
- **Purpose:** link to a guide/blog post.
- **Structure:** reuse `.tool-card` shell (icon/title/desc) or a `.seo-content` link list.
- **A11y:** descriptive link text (not "read more").

## Footer
- **Purpose:** ecosystem branding, sitemap of tools, legal.
- **Structure:** `.footer` → `.footer-grid` (columns: Brand, PDF Tools, Image Tools, Resources, Legal) → `.footer-bottom`.
- **CSS:** `.footer-grid` (1/2/3/5 columns), `.footer-col`, `.footer-logo`, `.footer-ecosystem`, `.footer-social`.
- **Responsive:** single column on mobile, up to 5 on desktop.
- **A11y:** grouped links; social icons carry `aria-label`.

## Advertisement Placeholder
- **Purpose:** AdSense unit.
- **Structure:** `.ad-container` → `<ins class="adsbygoogle">` + push script. The loader is in `base.html`'s `{% block adsense %}`.
- **CSS:** `.ad-container` (centered, `overflow-x:hidden`).
- **Responsive:** `data-full-width-responsive="true"`.
- **Note:** the homepage suppresses ads by overriding `{% block adsense %}`.

## Related Tools
- **Purpose:** internal-linking cluster at the bottom of a tool page.
- **Structure:** `.more-tools` → `.tools-mini-grid` of `<a>` chips.
- **CSS:** `.tools-mini-grid a` (44px chips, brand hover).
- **A11y:** real links, descriptive labels.

## Breadcrumb
- **Purpose:** show page hierarchy (Home › PDF Tools › Compress).
- **Recommended structure:** `<nav aria-label="Breadcrumb"><ol>…</ol></nav>` with a JSON-LD `BreadcrumbList`.
- **Status:** not yet implemented — see [SEO_GUIDELINES.md](./SEO_GUIDELINES.md).

## Section Heading
- **Purpose:** consistent section titles inside content.
- **Structure:** `<h2>`/`<h3>` inside `.seo-content` (centered `h2`).
- **A11y:** don't skip heading levels.

## Loading Spinner
- **Purpose:** async feedback (compression, conversion).
- **Structure:** `<div class="spinner">` + optional `.progress-bar > .progress-fill`.
- **CSS:** `.spinner` (brand ring animation), `.progress-bar` / `.progress-fill`.
- **A11y:** honor `prefers-reduced-motion` (handled globally); pair with a text status.

## Error Message
- **Purpose:** communicate failures (413/404/500, invalid file).
- **Structure:** dedicated templates `413.html`, `404.html`, `500.html` (extend `base.html`).
- **A11y:** clear heading + recovery action (`Try Again`).

## Success Notification
- **Purpose:** confirm completion (compression done, target met).
- **Structure:** `.result-box .success`, `.target-met` / `.target-missed`.
- **CSS:** green success block, amber warning block.
- **A11y:** convey status with text + icon, never color alone.
