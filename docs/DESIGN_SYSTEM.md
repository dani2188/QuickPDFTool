# Design System — hellobrivio

The visual language for **hellobrivio** (always lowercase, matching the logo; previously QuickPDFTools, then QuickTools; renamed on 2026-10-25). hellobrivio is both the brand and the product. QuickImageTools (Resize Image, Remove Background, Compress JPG) was merged in as native tools on 2026-08-25 rather than remaining a separate site.

The single source of truth is [`static/style.css`](../static/style.css) — this document describes what lives there. When a value here and in the stylesheet disagree, the stylesheet wins and this doc should be updated.

---

## 1. Branding

| | |
|---|---|
| **Brand and product name** | `hellobrivio` — always lowercase, even at the start of a sentence or heading |
| **Header shows** | the hellobrivio image logo (`static/img/logo.png`) |
| **Footer shows** | the logo, a short description, and "© 2026 hellobrivio · Free online tools to compress, merge, convert and edit your PDF files." — no "ecosystem" line |
| **Accent color** | `#e5322d` (brand red) |

**Logo usage:** the official hellobrivio logo is an image, never typed text.

| File (`static/img/`) | Use |
|---|---|
| `logo.png` (612 × 160, transparent) | Header (displayed 153 × 40) and footer (122 × 32). `alt="hellobrivio"`, explicit `width`/`height` to prevent layout shift, links to `/`. |
| `icon-512.png` (512 × 512) | Organization `logo` in JSON-LD and the default `og:image` / `twitter:image` (hubs, home, legal pages, guides, blog). |
| `og/<route-slug>.png` (1200 × 630) | One social preview image per tool page, made from the logo, the icon and the brand red by `scripts/make_og_images.py`. `app.py` serves it as that page's `og:image` / `twitter:image` when the file exists. Add a tool to the script's `TOOLS`, re-run it and commit the PNG. |
| `favicon-32.png`, `favicon-192.png` | `<link rel="icon">` in `base.html`. |
| `apple-touch-icon.png` (180 × 180, opaque) | `<link rel="apple-touch-icon">`; corners are filled with brand red because iOS paints transparency black. |

Keep the proportions (scale with `width`/`height` only, never stretch or crop), keep the link area at least 44px tall, and don't recolor it or put it on a busy background. The logo's reds match the brand red `#e5322d` below; the palette is unchanged.

---

## 2. Color palette

All colors are declared as CSS custom properties on `:root`.

### Brand
| Token | Value | Use |
|---|---|---|
| `--brand` | `#e5322d` | Primary actions, accents, links, focus ring |
| `--brand-dark` | `#c62823` | Hover state for brand elements |

### Text & ink
| Token | Value | Use |
|---|---|---|
| `--ink` | `#222` | Headings |
| `--text` | `#333` | Body text |
| `--muted` | `#777` | Subtitles, secondary text |
| `--muted-2` | `#888` | Fine print / file-info |

### Surfaces & lines
| Token | Value | Use |
|---|---|---|
| `--bg` | `#fafafa` | Page background |
| `--surface` | `#ffffff` | Cards, upload areas, header |
| `--surface-2` | `#f4f5f7` | Feature chips, secondary buttons, hover fills |
| `--line` | `#e6e6e6` | Borders, dividers |

### Semantic / status
| Token | Value | Use |
|---|---|---|
| `--success` | `#2e7d32` (bg `#e8f5e9`) | Success messages, "target reached" |
| Warning | text `#8a6100` on bg `#fff8e1` | Soft warnings ("target missed") |
| `--danger` | `#c0392b` | Destructive actions |

> **Contrast:** body text `#333` on `#fafafa` and brand `#e5322d` on white both exceed WCAG AA. Do not put brand red text on `--surface-2` for long copy.

---

## 3. Typography

- **Primary font:** `Arial, Helvetica, sans-serif` (system-safe, zero network cost — no web fonts by design).
- **Base line-height:** `1.5`.

Fluid sizing with `clamp()` (mobile-min, viewport-scaled, desktop-max):

| Element | Size |
|---|---|
| `h1` | `clamp(26px, 6vw, 40px)`, line-height 1.15 |
| `h2` | `clamp(20px, 4vw, 28px)` |
| `h3` | `clamp(18px, 3vw, 22px)` |
| `.subtitle` | `clamp(15px, 2.5vw, 18px)`, color `--muted` |
| Body | `16px` |
| Button text | `16px`, weight 600 |
| Fine print (`.file-info`) | `13px`, color `--muted-2` |

> Inputs use `font-size: 16px` minimum to prevent iOS Safari zoom-on-focus.

---

## 4. Spacing scale (8px)

| Token | px |
|---|---|
| `--s1` | 8 |
| `--s2` | 16 |
| `--s3` | 24 |
| `--s4` | 32 |
| `--s5` | 40 |
| `--s6` | 60 |

Use tokens instead of raw pixel values for margins/padding/gaps. Section rhythm: `--s5`/`--s6` between major blocks, `--s2`/`--s3` inside components.

---

## 5. Radius, shadow, sizing

| Token | Value | Use |
|---|---|---|
| `--radius` | `12px` | Cards, upload areas, options box |
| `--radius-sm` | `8px` | Buttons, inputs, chips |
| `--shadow` | `0 4px 12px rgba(0,0,0,.06)` | Resting cards |
| `--shadow-lg` | `0 8px 22px rgba(0,0,0,.12)` | Hovered cards |
| `--tap` | `44px` | Minimum touch-target height/width |
| `--maxw` | `1100px` | Global content container width |

---

## 6. Responsive breakpoints

Mobile-first. Base styles target the smallest screen; `min-width` queries scale up.

| Breakpoint | Applies |
|---|---|
| `< 640px` | 1-column tool grid, single-column footer, hamburger nav |
| `≥ 640px` | 2-column tool grid, 2-column footer |
| `≥ 768px` | Desktop horizontal nav (hamburger hidden), 3-column footer, larger container padding |
| `≥ 1024px` | 4-column tool grid, 5-column footer, wider nav spacing |

Verify layouts at **320 / 480 / 768 / 1024 / 1440px**. Never allow horizontal scrolling (`body { overflow-x: hidden }` is a safety net, not a license to overflow).

---

## 7. Buttons

Base class `.main-btn` (alias `.btn`), min-height `--tap`, radius `--radius-sm`, weight 600, `inline-flex` centered.

| Variant | Class | Look |
|---|---|---|
| Primary | `.main-btn` / `.btn` | Brand red, white text; hover → `--brand-dark` |
| Secondary | `.btn-secondary` | `--surface-2` fill, `--line` border, dark text |
| Success | `.btn-success` | `--success` green |
| Danger | `.btn-danger` | `--danger` red |
| Disabled | `disabled` attr | Reduced affordance; never rely on color alone |
| Hover | — | Darken background; no layout shift |
| Focus | `:focus-visible` | 3px `--brand` outline, 2px offset |
| Loading | `.spinner` next to/again in button context | Use the shared spinner |

`:active` nudges 1px down for tactile feedback.

---

## 8. Cards

All cards sit on `--surface`, radius `--radius`, `--shadow` at rest, `--shadow-lg` on hover.

| Card | Class | Notes |
|---|---|---|
| Tool card | `.tool-card` | Icon + title + description, centered; hover lifts `-4px` + brand underline grows; `:active` scales 0.98 for touch feedback |
| Feature chip | `.feature` | Small `--surface-2` pill in `.features` row |
| Advertisement | `.ad-container` | Wraps AdSense `<ins>`; `overflow-x: hidden`, centered |
| Result card | `.result-box` | Compression/download result summary |
| Guide / FAQ / Blog card | reuse `.tool-card` or `.seo-content` blocks | Standardize on the tool-card shell where a clickable card is needed |

---

## 9. Icons

Icons are **emoji glyphs** (no icon font, no SVG sprite) for zero-cost, universal rendering. Keep them consistent across the family:

| Concept | Glyph |
|---|---|
| Compress | 📦 |
| Merge | 📑 |
| Split | ✂️ |
| PDF → image | 🖼 |
| Rotate | 🔄 |
| Convert | 🔀 |
| Sign | ✍️ |
| Edit | ✏️ |
| Organize | 📂 |
| Security (protect/unlock) | 🔒 |
| Redact | ⬛ |
| Resize | 📐 |
| Remove background | 🪄 |
| Performance / fast | ⚡ |
| Installation-free | 💻 |
| Upload | ⬆ (via `.upload-area::before`) |
| Download | ⬇ (via `.download-list a::before`) |
| External link | ↗ (appended to sibling-product links) |

When a tool needs a new icon, pick one emoji and record it here so sibling products reuse the same symbol.
