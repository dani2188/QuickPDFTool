# Content Audit — QuickTools (2026-09-09)

Produced as Step 1 of the AdSense low-value-content remediation. Numbers are
measured directly from the current templates (visible word count after
stripping tags/Jinja; FAQ/related-tools/use-case/considerations detected by
heading and section patterns), not estimated. Re-run
`scripts/content_audit.py` to refresh this table after further edits.

**Key finding**: the site's `*_guide.html` pages are already substantial —
every single one is 599–1163 words. The actual gap is the **tool landing
pages themselves** (the page with the upload form, which is what most
search traffic and an AdSense crawl actually lands on): 13 of 31 score LOW,
mostly 95–130 words of pure boilerplate ("Upload your file → click the
button → download") with no FAQ, no use cases, no considerations, sitting
right next to an already-good guide it doesn't link readers into deeply
enough.

## Tool pages

| Route | Words | Unique intro | How it works | Use cases | Considerations | FAQ | Related tools | Guide exists | Quality |
|---|---|---|---|---|---|---|---|---|---|
| /add-text-to-pdf | 34 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | **LOW** |
| /add-page-numbers | 108 | ◑ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /add-watermark | 95 | ◑ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | MEDIUM |
| /delete-pdf-pages | 117 | ◑ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /excel-to-pdf | 111 | ◑ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | MEDIUM |
| /extract-images | 107 | ◑ | ✗ | ✓ | ✗ | ✗ | ✓ | ✓ | MEDIUM |
| /jpg-to-pdf | 125 | ◑ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /pdf-to-excel | 118 | ◑ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /pdf-to-png | 101 | ◑ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /pdf-to-text | 128 | ◑ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | **LOW** |
| /pdf-to-webp | 128 | ◑ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | **LOW** |
| /png-to-pdf | 121 | ◑ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | MEDIUM |
| /protect-pdf | 112 | ◑ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /remove-watermark | 115 | ◑ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /sign-pdf | 125 | ◑ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | **LOW** |
| /unlock-pdf | 104 | ◑ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /word-to-pdf | 124 | ◑ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | **LOW** |
| /crop-pdf | 159 | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | MEDIUM |
| /svg-to-pdf | 276 | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | MEDIUM |
| /redact-pdf | 350 | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | MEDIUM |
| /rotate-pdf | 372 | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | MEDIUM |
| /split-pdf | 372 | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | MEDIUM |
| /pdf-to-jpg | 374 | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | MEDIUM |
| /compress-jpg | 524 | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | MEDIUM |
| /compress-pdf | 585 | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | MEDIUM |
| /compress-pdf-for-email | 638 | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | (own content, no separate guide) | MEDIUM |
| /organize-pdf | 624 | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | (hub, no guide) | MEDIUM |
| /compress-pdf-to-1mb | 699 | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | (own content, no separate guide) | MEDIUM |
| /merge-pdf | 474 | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | **HIGH** |
| /pdf-to-word | 461 | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | **HIGH** |
| /remove-background | 330 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **HIGH** |
| /resize-image | 503 | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | **HIGH** |

**13 LOW, 15 MEDIUM, 4 HIGH.** The `✗` in "Considerations" across almost every
MEDIUM page is the single most common gap even among the "good" pages — most
have an intro, steps, and FAQ, but few explain real tradeoffs (image-heavy vs
text-heavy compression, scanned vs digital PDFs, layout fidelity limits, etc.).

## Guide pages (`/how-to-*`)

All 29 existing guides are already substantial: **599–1163 words**, every one
with numbered steps, a tips section, and an FAQ. This is the opposite problem
from the tool pages — no guide needs a word-count fix. `compress-pdf-for-email`,
`compress-pdf-to-1mb`, and `organize-pdf` don't have a separate guide, but
each already carries its own How-To + FAQ content directly on the tool page,
which is an intentional, documented pattern (SEO_GUIDELINES.md §6: "keep
guide content distinct from the tool page to avoid duplicate content" — these
three fold both into one page instead of duplicating).

## Hub pages

| Route | Words | Notes |
|---|---|---|
| /image-tools | 59 | Pure button grid, no intro, no explanation of the 3 tools, no FAQ. **LOW.** |
| /pdf-tools | 156 | One-line subtitle + category headers + grid. No explanation of what each category is for, no FAQ. **LOW.** |
| /organize-pdf | 624 | Already a real landing page (intro, use cases, tip, FAQ). Doubles as both a hub and a tool-ish page. **HIGH.** |
| /edit-pdf | 672 | Already a real landing page. **HIGH.** |
| /convert-pdf | 762 | Already a real landing page. **HIGH.** |

`/pdf-tools` and `/image-tools` are the two that actually need work — they're
pure navigation, not landing pages.

## Trust / transparency pages

| Route | Words | Notes |
|---|---|---|
| /terms | 108 | Generic boilerplate ("QuickTools provides free online tools...", "not responsible for any loss"). No specifics about file handling, upload limits, or account-free operation. **LOW.** |
| /contact | 290 | Categorized reasons to write in, privacy/GDPR routing, response-time expectations. Solid. |
| /about | 553 | Explains what the product is, how tools actually process files (server-side, Ghostscript/PyMuPDF), editorial approach, HelloBrivio family. Solid. |
| /privacy-policy | 878 | Detailed, covers uploads/cookies/AdSense/GDPR. Solid. |

`/terms` is the one weak trust page.

## Blog articles

9 articles exist (4 PDF-focused: file size, security basics, resume prep,
email-size decision tree; 5 image-focused, ported from the former
QuickImageTools site: resize-for-social, Instagram sizes, PNG vs JPG,
web-image optimization, background removal). All are 700–1900 words with
real, specific, non-templated content and links back to the relevant tools.
**No blog work needed** — this is already the strongest content on the site.

## Tier classification for remediation

**Tier 1** (spec's named high-search-intent list, cross-checked against the
real route inventory — all 13 exist):

`compress-pdf`, `merge-pdf`, `split-pdf`, `pdf-to-word`, `pdf-to-jpg`,
`pdf-to-png`, `jpg-to-pdf`, `png-to-pdf`, `pdf-to-text`, `redact-pdf`,
`resize-image`, `compress-jpg`, `remove-background`.

Of these, already HIGH and left alone: `merge-pdf`, `pdf-to-word`,
`resize-image`, `remove-background`. Needing work, worst-first:
`pdf-to-png` (101w, LOW) → `jpg-to-pdf` (125w, LOW) → `pdf-to-text` (128w,
LOW) → `compress-pdf` / `split-pdf` / `pdf-to-jpg` / `redact-pdf` /
`png-to-pdf` (MEDIUM, missing considerations/use-cases sections).

**Tier 1.5** (not in the spec's example list, but LOW-quality *and* clearly
high search-intent — core PDF tools anyone would search for by name):
`sign-pdf`, `protect-pdf`, `unlock-pdf`, `add-page-numbers`, `word-to-pdf`.

**Tier 2**: the remaining LOW/MEDIUM tools — `add-text-to-pdf`,
`delete-pdf-pages`, `excel-to-pdf`, `pdf-to-excel`, `extract-images`,
`add-watermark`, `remove-watermark`, `pdf-to-webp`, `svg-to-pdf`, `crop-pdf`,
`compress-pdf-for-email`, `compress-pdf-to-1mb`, `organize-pdf`.

**Tier 3**: none — every route is already at least a real, working tool with
some content; there's no page with literally zero explanatory text.

Given the explicit instruction not to mass-rewrite 31 pages in one blind
pass, this remediation pass targets **Tier 1 + Tier 1.5** (18 tool pages)
plus both thin hub pages, the home page, and `/terms`. Tier 2 is left for a
follow-up pass — see the final report for exactly what's done vs. not.
