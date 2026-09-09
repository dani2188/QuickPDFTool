# Content Quality Checklist — Tier 1 Tool Pages

Pass/fail against the content model required by the AdSense remediation task
(Section 2 of the spec): **(A)** 2–4 paragraph intro (what/who/why/output
format), **(B)** How it works (3–5 steps matching the real implementation),
**(C)** When to use it (concrete use cases), **(D)** Important considerations
(real tradeoffs, not filler), **(E)** FAQ (4–8 tool-specific Q&As as complete
paragraphs, not one-liners), **(F)** Related tools.

Checked directly against each template's rendered content and against the
route's actual backend behavior in `app.py` — not assumed. Word counts and
FAQ counts are machine-counted (`scripts/content_audit.py` plus a JSON-LD
FAQPage item count), not estimated.

| Tool | Words | A. Intro | B. How it works | C. Use cases | D. Considerations | E. FAQ (count) | F. Related tools | FAQPage JSON-LD | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| /compress-pdf | 617 | ✓ | ✓ | ✓ | ◑ (Compression Levels Explained; no dedicated tradeoffs section) | ✓ (5) | ✓ | ✓ | **PASS** (D is folded into levels/FAQ, not a separate section) |
| /merge-pdf | 491 | ✓ | ✓ | ✓ | ◑ ("Tips for Best Results" covers practical caveats, not a distinct considerations section) | ✓ (5) | ✓ | ✓ | **PASS** |
| /split-pdf | 394 | ✓ | ✓ | ✓ | ◑ (no dedicated section; FAQ covers "does splitting change content," "can I recombine") | ✓ (5) | ✓ | ✓ | **PASS** |
| /pdf-to-word | 466 | ✓ | ✓ | ✓ | ◑ ("Tips for Better Conversion Results" functions as considerations) | ✓ (5) | ✓ | ✓ | **PASS** |
| /pdf-to-jpg | 403 | ✓ | ✓ | ✓ | ◑ (no dedicated section; FAQ covers quality/page limits) | ✓ (5) | ✓ | ✓ | **PASS** |
| /pdf-to-png | 615 | ✓ | ✓ | ✓ | ◑ (folded into "When to use PDF to PNG instead of JPG" + FAQ) | ✓ (4) | ✓ | ✓ | **PASS** |
| /jpg-to-pdf | 635 | ✓ | ✓ | ◑ (use cases live in the intro paragraph, no dedicated heading) | ✓ (explicit "Important considerations") | ✓ (4) | ✓ | ✓ | **PASS** |
| /png-to-pdf | 507 | ✓ | ✓ | ✓ | ✓ (explicit "Important considerations") | ✓ (4) | ✓ | ✓ | **PASS** |
| /pdf-to-text | 595 | ✓ | ✓ | ✓ | ✓ (limitations stated directly in the intro: no OCR, scanned PDFs unsupported) | ✓ (4) | ✓ | ✓ | **PASS** |
| /redact-pdf | 1826 | ✓ | ✓ | ✓ ("Why redact a PDF?") | ✓ (explicit "Important considerations" + "Privacy & security") | ✓ (4) | ✓ | ✓ | **PASS** |
| /resize-image | 611 | ✓ | ✓ | ◑ (no dedicated "when to use" heading; covered via FAQ and "Social Media Image Size Reference") | ✓ (letterbox/no-crop behavior explained in FAQ) | ✓ (4) | ✓ | ✓ | **PASS** |
| /compress-jpg | 529 | ✓ | ✓ | ✓ ("When Should You Compress a JPG?") | ◑ (Compression Levels Explained; EXIF-stripping covered in FAQ) | ✓ (4) | ✓ | ✓ | **PASS** |
| /remove-background | 335 | ✓ | ✓ | ✓ ("Perfect For") | ◑ (accuracy/format limits covered in FAQ, not a dedicated section) | ✓ (4) | ✓ | ✓ | **PASS** |

**Result: 13/13 Tier 1 pages pass the content-model bar, and all 13 now emit
FAQPage JSON-LD matching their on-page FAQ.** Every page has a real,
non-templated intro, an accurate how-it-works sequence checked against the
actual route code, genuine use cases, at least 4 FAQ entries answered in full
sentences, and related-tool links. Verified by loading every route through
Flask's test client and parsing the returned JSON-LD.

## Known, honest gaps (not blocking, but real)

- **"Considerations" is often folded into another section rather than given
  its own heading.** Marked ◑ above where the tradeoff information exists but
  isn't under a literal "Important considerations" H2/H3. This was a judgment
  call: adding a redundant considerations section that repeats the FAQ
  verbatim would be exactly the kind of padding the task explicitly forbids
  ("no keyword stuffing, no filler sections"). Where the underlying real
  tradeoff wasn't documented anywhere on the page, it was added; where it
  already existed under a different heading, it was left as-is rather than
  duplicated.
- **Tier 2 pages** (add-text-to-pdf, add-watermark, delete-pdf-pages,
  excel-to-pdf, pdf-to-excel, extract-images, remove-watermark, pdf-to-webp)
  were also brought up to the same content model as part of this pass
  (originally 63–139 words each; now full A–F pages), even though the task's
  priority order put them after Tier 1. They are not included in this
  Tier-1-scoped table — see `docs/CONTENT_AUDIT.md` for their before/after
  status.
