# SEO Guidelines — QuickTools

SEO standards for every QuickTools product. QuickPDFTools is heavily long-tail (one tool page + one "how-to" guide per feature); protecting that structure is the priority.

Legend: ✅ implemented · ◑ partial · ⬜ standard to adopt.

---

## 1. Per-page requirements

Every indexable page must have:

| Element | How | Status |
|---|---|---|
| Unique `<title>` | `{% block title %}` — keyword-first, brand suffix ` – QuickPDFTools` | ✅ per-page titles; ◑ brand suffix not uniform |
| Unique meta description | `{% block description %}` | ✅ |
| Canonical URL | `<link rel="canonical" href="https://hellobrivio.com{{ request.path }}">` in `base.html` head | ✅ |
| Open Graph | `og:site_name`, `og:type`, `og:url`, `og:title`, `og:description` | ✅ in `base.html` |
| Twitter Card | `twitter:card=summary`, `twitter:title`, `twitter:description` | ✅ in `base.html` |
| One `<h1>` | exactly one per page | ✅ |
| Structured headings | `h1 → h2 → h3`, no skips | ✅ |
| JSON-LD | `WebApplication` / `HowTo` / `FAQPage` / `BreadcrumbList` | ◑ site-wide `WebSite` in `base.html` `{% block jsonld %}`; per-page types **to add** |

> **Keyword rule:** when adding the brand suffix, keep the keywords first — `Compress PDF – QuickPDFTools`, never `QuickPDFTools – Home`.

---

## 2. `base.html` head (implemented)

```html
<link rel="canonical" href="https://hellobrivio.com{{ request.path }}" />

<meta property="og:url" content="https://hellobrivio.com{{ request.path }}" />

<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="{{ self.title() }}" />
<meta name="twitter:description" content="{{ self.description() }}" />
```

These reuse the existing `title` / `description` blocks, so every page that extends `base.html` gets them with no per-page work. The canonical/og:url host is fixed to `hellobrivio.com` (not derived from `request.host`) so signals consolidate regardless of which host served the page.

---

## 3. JSON-LD templates

**Tool page → `WebApplication`:**
```json
{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "Compress PDF",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Any",
  "offers": { "@type": "Offer", "price": "0" }
}
```

**Guide page → `HowTo`** (mirror the visible `.steps`).
**FAQ blocks → `FAQPage`** (mirror the visible Q&A).
**All pages → `BreadcrumbList`** once breadcrumbs ship.

Provide these via an optional `{% block jsonld %}` in `base.html` so only relevant pages emit them.

---

## 4. Site-level files

| File | Location | Status |
|---|---|---|
| `robots.txt` | project root, served at `/robots.txt` | ✅ allows all except `/uploads/`, points to sitemap |
| `sitemap.xml` | project root, served at `/sitemap.xml` | ✅ — **must list every public route** |
| `ads.txt` | `templates/ads.txt`, served at `/ads.txt` | ✅ AdSense pub id |
| Google verification | `<meta name="google-site-verification">` or GSC DNS/file | ⬜ confirm method |

**Sitemap discipline:** when you add a route, add its `<loc>`. Use absolute `https://` URLs on the canonical domain. Do not list redirecting or `noindex` URLs (see the "Page with redirect" note below).

---

## 5. Internal linking strategy
- **Every tool page** links to its guide (`/how-to-*`) and to 4–6 related tools via `.tools-mini-grid`.
- **Every guide** links back to its tool and to sibling guides.
- **Homepage** links to top tools + top guides.
- **Footer** provides a persistent link cluster (PDF Tools / Image Tools / Resources / Legal) on every page.
- Use descriptive anchor text containing the target keyword ("Compress PDF"), never "click here".

## 6. Blog / guide linking
- One `_guide.html` per tool, matching the `/how-to-<tool>` route.
- Guides interlink in clusters (compress ↔ compress-to-1mb ↔ compress-for-email).
- Keep guide content distinct from the tool page to avoid duplicate content.

## 7. Related-tools strategy
- Curate `.tools-mini-grid` links by relevance (rotate → crop → organize), not randomly.
- 4–6 links per cluster; keep them stable so link equity accumulates.

## 8. Cross-product (ecosystem) linking
- Link to sibling products with the ` ↗` external marker and `rel="noopener"` (e.g. **QuickImageTools**).
- Footer names the ecosystem: "Part of the HelloBrivio ecosystem."

## 9. Known issue — "Page with redirect"
Google may report `http://` URLs as *Page with redirect* because `http` 301-redirects to `https` (correct HTTPS enforcement). This is usually **benign**: Google indexes the `https` destination. To keep it clean:
- Only ever expose `https://` canonical URLs in the sitemap, internal links, and OG tags.
- Ensure the canonical tag always points to the `https` version.
- Don't submit `http://` URLs in Search Console.

## 10. Domain note
Primary host is **`hellobrivio.com`**. Canonical tags, `og:url`, `sitemap.xml`, and `robots.txt` all agree on it (aligned 2026-07). `quickpdftool.onrender.com` still resolves (Render default) but is non-canonical — do not link to it or list it in the sitemap. If the primary host ever changes, update all four in one pass.
