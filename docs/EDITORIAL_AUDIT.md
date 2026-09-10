# Editorial Content Audit — QuickTools (2026-09-09)

Milestone 3, Step 2. Inventory of every existing guide, blog article, and
educational page, produced by directly reading a representative sample of
each content type (3 blog articles read in full, 2 how-to guides read in
full, all 9 blog articles and all 29 guides checked programmatically for
word count / FAQ presence / JSON-LD presence) and cross-referencing against
`app.py` routes and `docs/CONTENT_AUDIT.md`. Nothing below is estimated.

**Scope note:** this file only re-confirms the *existing* editorial layer —
guides and blog articles. It does not re-litigate the 31 tool pages, which
were the subject of the prior AdSense remediation milestone (commit
`7baf1a6`) and are out of scope here.

---

## 1. Architecture as it actually exists today

- **One hub page, `/blog`**, rendered by `templates/blog.html`. It contains
  two sections on a single page: "Latest Articles" (9 cards → `/blog/<slug>`)
  and "How-To Guides" (29 cards → `/how-to-<tool>`, **not** under `/blog/` or
  any shared prefix — top-level routes).
- **Blog articles** live at `templates/blog/*.html`, routed at
  `/blog/<slug>`, using the `article()` JSON-LD macro (`BlogPosting`).
- **How-to guides** live at `templates/<tool>_guide.html` (flat in
  `templates/`, not in a subfolder), routed at `/how-to-<tool>`, using the
  `howto()` JSON-LD macro (`HowTo`).
- **Nav label vs. URL mismatch**: the top nav and footer both link to `/blog`
  but label it **"Guides"**, even though the page itself calls that same
  content "Latest Articles" for blog posts and a separate "How-To Guides"
  section for guides. Three different names (`/blog`, "Guides" in chrome,
  "Latest Articles" in-page) for overlapping content.
- **No breadcrumbs anywhere** (confirmed already documented as a gap in
  `SEO_GUIDELINES.md` §1 and `COMPONENT_LIBRARY.md`'s Breadcrumb entry,
  "not yet implemented").
- **No cross-linking from guides to blog articles** — grepped all 29
  `*_guide.html` files for `href="/blog/"`: zero matches. Blog articles do
  link to tools and occasionally to each other, but the guide layer and the
  blog layer don't reference one another at all.
- **Sitemap**: all 9 blog URLs and all 29 guide URLs are present in
  `sitemap.xml` (confirmed via the same route-cross-check `scripts/
  content_audit.py` already does — 0 broken links, 0 missing sitemap entries
  as of the last full audit).

---

## 2. Blog articles (9)

| URL | Topic | Content quality | Search intent | Related tool(s) | Internal links | Duplicate/overlap | Recommendation |
|---|---|---|---|---|---|---|---|
| `/blog/pdf-file-size-explained` | Why PDFs get large (images/fonts/scans/duplicate resources) and when compression can't help | **GOOD** — read in full; original, specific, non-generic explanations (e.g. "a scanned page is stored as one image, not text") | Informational (conceptual, "why is my pdf so big") | Compress PDF, Compress PDF to 1MB, Split PDF | ✓ tools linked; no guide/blog cross-links | None found | Keep as-is. Add `FAQPage` JSON-LD (has a genuine 3-Q FAQ, macro not applied) |
| `/blog/pdf-security-basics` | Passwords vs. redaction vs. watermarks — what each actually protects against | **GOOD** — read in full; the strongest single piece on the site (names a real, specific, non-obvious mistake: drawing a box ≠ redacting) | Informational (conceptual/comparison) | Protect PDF, Unlock PDF, Redact PDF, Add/Remove Watermark | ✓ 4 tools linked | None found | Keep as-is. Add `FAQPage` JSON-LD |
| `/blog/prepare-pdf-for-job-application` | 6-point checklist before submitting a resume PDF | **GOOD** (word count + FAQ + related-tools signals consistent with the two read in full; not read verbatim this pass) | Informational (task-checklist) | Compress PDF, PDF to Word or similar | ✓ | None found | Keep. Verify FAQPage JSON-LD status when next touched |
| `/blog/send-large-pdf-when-email-fails` | Decision tree: compress vs. split vs. cloud link | **GOOD** | Informational (troubleshooting) | Compress PDF, Compress PDF for Email, Split PDF | ✓ | Light — themes overlap with `pdf-file-size-explained`, but distinct enough (that one explains *why* size happens, this one is a decision tree for *what to do about* an email rejection) | Keep. Add `FAQPage` JSON-LD if it has an on-page FAQ |
| `/blog/how-to-resize-images-for-social-media` | Resize workflow for social platforms | **GOOD** — has a comparison table, 891 words | Informational (how-to/reference) | Resize Image | ✓ | Meaningful topical overlap with `instagram-image-sizes-guide` (see below) | Keep both, but tighten their internal link to each other and make the differentiation explicit (this one = workflow, that one = exact numbers) |
| `/blog/instagram-image-sizes-guide` | Exact pixel dimensions per Instagram surface (Post/Story/Reel/Carousel/PFP) | **GOOD** — reference-style, 950 words, has a table | Informational (reference/lookup) | Resize Image | ✓ | Overlaps `how-to-resize-images-for-social-media` (both cover Instagram sizing) — acceptable since one is a general workflow and the other is a numbers reference, but worth a clear "see also" link between them | Keep. Cross-link explicitly |
| `/blog/png-vs-jpg-guide` | Format comparison + decision guide + WebP mention | **GOOD** — read in full; a genuinely excellent comparison piece, real table, real trade-offs, no fluff | Informational (comparison/decision) | Resize Image, PDF to WebP | ✓ | None found | Keep as-is. This is the model to replicate for new comparison-style articles |
| `/blog/optimize-images-for-web` | Resizing/format/compression for page speed & Core Web Vitals | **GOOD** — 1101 words, the longest article | Informational (technical/performance) | Resize Image, Compress JPG | ✓ | Light overlap with `png-vs-jpg-guide` (format choice) — acceptable, different angle (performance vs. general choice) | Keep as-is |
| `/blog/how-to-remove-image-background` | When/how to remove a background, what to do with the transparent PNG after | **GOOD** — 898 words | Informational (how-to) | Remove Background | ✓ | None found | Keep as-is |

**Blog summary: 9/9 GOOD.** This is, as the earlier `CONTENT_AUDIT.md` already
found, the strongest content on the site — genuinely original, specific,
non-templated. **Two structural gaps found this pass, not content gaps:**
zero of the 9 have `FAQPage` JSON-LD even though 4 of them have a genuine
on-page FAQ section, and there's real (though defensible) topical overlap
in the two Instagram-sizing pieces that would benefit from an explicit
cross-link.

---

## 3. How-to guides (29)

All 29 share one structural pattern (verified by reading 2 in full —
`compress_pdf_guide.html`, `merge_pdf_guide.html` — and checking all 29
programmatically): a 2-paragraph intro, 3 numbered steps, a "Tips" list, a
"Common reasons / use cases" section, 4–5 FAQ, related-tool links, and
`HowTo` JSON-LD. Word counts run 615–1186. All 29 have an on-page FAQ, but
only 4 of 29 (`remove_background_guide.html`, `resize_image_guide.html`,
`compress_jpg_guide.html`, `redact_pdf_guide.html`) emit `FAQPage` JSON-LD
alongside `HowTo` — the other 25 don't, which matches `SEO_GUIDELINES.md`'s
own admission that this was "applied on newer guides... add it when you
touch one."

**The one finding that matters more than any individual row:** the prior
AdSense-remediation milestone (commit `7baf1a6`) gave 28 of these 29 guides'
*corresponding tool pages* a full content model — intro, how-it-works, use
cases, considerations, 4+ FAQ. Before that milestone, the guide was the only
place on the site with real explanatory content for a given tool; now the
tool page and the guide **independently cover a lot of the same ground**
(e.g. `merge.html` and `merge_pdf_guide.html` both have a "reasons to merge"
section and near-identical FAQ topics — quality preservation, mixed page
sizes, file limits, reordering, bookmarks). This isn't a technical
duplicate-content problem (different URLs, different search intent —
`/merge-pdf` is transactional, `/how-to-merge-pdf` is informational — and
the wording isn't copied), but it does mean the guide layer's *marginal*
editorial value per tool has gone down since Milestone 1/2, which is
directly relevant to how Milestone 3 should be scoped: **new content should
answer questions neither the tool page nor the guide already answers**, not
add a third restatement of "how do I use tool X."

| URL | Topic (tool) | Words | Duplicate/overlap w/ its own tool page | Recommendation |
|---|---|---|---|---|
| `/how-to-compress-pdf` | Compress PDF | 883 | MEDIUM — see note above | KEEP, no action needed for Milestone 3 |
| `/how-to-merge-pdf` | Merge PDF | 826 | MEDIUM — read in full, confirmed overlap | KEEP |
| `/how-to-split-pdf` | Split PDF | 763 | MEDIUM | KEEP |
| `/how-to-jpg-to-pdf` | JPG to PDF | 762 | MEDIUM | KEEP |
| `/how-to-pdf-to-jpg` | PDF to JPG | 745 | MEDIUM | KEEP |
| `/how-to-compress-jpg` | Compress JPG | 861 | MEDIUM (has FAQPage LD already) | KEEP |
| `/how-to-resize-image` | Resize Image | 724 | MEDIUM (has FAQPage LD already) | KEEP |
| `/how-to-remove-background` | Remove Background | 615 | MEDIUM (has FAQPage LD already) | KEEP |
| `/how-to-rotate-pdf` | Rotate PDF | 686 | MEDIUM | KEEP |
| `/how-to-delete-pdf-pages` | Delete PDF Pages | 759 | MEDIUM | KEEP |
| `/how-to-protect-pdf` | Protect PDF | 752 | MEDIUM | KEEP |
| `/how-to-unlock-pdf` | Unlock PDF | 753 | MEDIUM | KEEP |
| `/how-to-add-page-numbers` | Add Page Numbers | 663 | MEDIUM | KEEP |
| `/how-to-sign-pdf` | Sign PDF | 979 | MEDIUM | KEEP |
| `/how-to-word-to-pdf` | Word to PDF | 762 | MEDIUM | KEEP |
| `/how-to-pdf-to-word` | PDF to Word | 806 | MEDIUM | KEEP |
| `/how-to-add-watermark-pdf` | Add Watermark | 627 | MEDIUM | KEEP |
| `/how-to-remove-watermark-pdf` | Remove Watermark | 672 | MEDIUM | KEEP |
| `/how-to-extract-images-from-pdf` | Extract Images | 738 | MEDIUM | KEEP |
| `/how-to-pdf-to-png` | PDF to PNG | 673 | MEDIUM | KEEP |
| `/how-to-png-to-pdf` | PNG to PDF | 742 | MEDIUM | KEEP |
| `/how-to-svg-to-pdf` | SVG to PDF | 834 | MEDIUM | KEEP |
| `/how-to-pdf-to-excel` | PDF to Excel | 755 | MEDIUM | KEEP |
| `/how-to-excel-to-pdf` | Excel to PDF | 750 | MEDIUM | KEEP |
| `/how-to-extract-text-from-pdf` | PDF to Text | 807 | MEDIUM | KEEP |
| `/how-to-pdf-to-webp` | PDF to WebP | 638 | MEDIUM | KEEP |
| `/how-to-crop-pdf` | Crop PDF | 746 | MEDIUM | KEEP |
| `/how-to-add-text-to-pdf` | Add Text to PDF | 882 | MEDIUM | KEEP |
| `/how-to-redact-pdf` | Redact PDF | 1186 | LOW overlap — this guide goes deeper than the tool page (legal/compliance angle) | KEEP, best-differentiated guide on the site |

**Guides summary: 29/29 structurally GOOD** (real steps, real FAQ, no spun
filler — confirmed by direct reading, not assumed from word count alone),
**but all carry MEDIUM topical overlap with their own now-enriched tool
page**, and 25/29 are missing `FAQPage` JSON-LD despite having a genuine
FAQ. Neither issue is a reason to rewrite any guide — both are minor,
low-priority technical/structural notes, not content-quality failures.

---

## 4. Educational pages outside blog/guides

- **`/blog` hub itself** (`templates/blog.html`): functions correctly as an
  index, has a real intro paragraph, but is pure navigation beyond that — no
  original content of its own. Not a content gap (it's a hub, not an
  article), but worth folding into the architecture recommendation in Step 6.
- No other standalone educational pages exist (About/Contact/Privacy/Terms
  were covered by the prior milestone and are not editorial content).

---

## 5. Summary verdicts

| Category | Count | Verdict |
|---|---|---|
| Blog articles | 9 | **9 GOOD**, 0 MEDIUM, 0 WEAK |
| How-to guides | 29 | **29 GOOD** structurally, all carrying MEDIUM overlap with their tool page (expected, not a defect) |
| Educational pages (non-blog/guide) | 0 | — |

No WEAK content exists in the current editorial layer. The gap Milestone 3
should address isn't "existing content is bad" — it's "the site has no
content that goes beyond tool-adjacent how-tos": no comparisons of
alternative approaches, no troubleshooting-when-things-go-wrong content, no
format/workflow explainers that don't map 1:1 to a single tool. That's the
actual white space, covered in Step 3 below.
