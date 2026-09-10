# Editorial Guidelines — QuickTools

Quality bar for new guides/articles under the `/blog` editorial layer.
Companion to [`docs/CONTENT_QUALITY_CHECKLIST.md`](./CONTENT_QUALITY_CHECKLIST.md)
(which governs the 31 *tool* pages) and [`docs/EDITORIAL_AUDIT.md`](./EDITORIAL_AUDIT.md)
(which inventories what already exists). This document governs new
standalone editorial content — comparisons, explainers, troubleshooting
pieces — going forward.

---

## 1. The one-sentence test

**An article must remain genuinely useful to someone who reads it and never
clicks a tool.** If a piece only makes sense as a funnel into a tool page —
if stripped of its links it says nothing — it's not an article, it's a
disguised ad, and it doesn't belong in this layer.

---

## 2. Required qualities

- **Genuinely useful information.** The article must answer the question a
  real person searching for that topic actually has, completely, not just
  enough to justify a tool link.
- **Original explanations.** Explain concepts in your own reasoning, with
  specifics ("a scanned page is stored as one image, not text" — not "PDFs
  can be large for various reasons"). If a sentence could appear verbatim on
  any competitor's site, it's too generic — rewrite it with something
  concrete: a number, a mechanism, a specific failure mode.
- **Complete paragraphs, not fragments.** FAQ answers and body content are
  full sentences that stand alone, never a one-line stub.
- **Practical examples where they help.** A concrete scenario ("a cover
  page, a report, and an appendix, uploaded in that order") beats an
  abstract description every time it's available.
- **Accurate technical claims**, checked against what the product actually
  does (see §4) — never against general assumptions about "how PDFs work."
- **No fabricated statistics.** No invented percentages, survey numbers, or
  "studies show" claims. Real, checkable numbers only (e.g. "72 points = 1
  inch" is checkable and correct; "94% of PDFs are too large" is not
  something this project can verify and must not appear).
- **No unsupported claims** — about the product ("military-grade
  encryption," "100% private," "instant" where it isn't) or about the world
  ("everyone struggles with X," "the #1 reason Y happens" without a source).
- **No keyword stuffing.** Write for the reader's actual question, not a
  target-keyword density.
- **No repetitive AI-generated filler.** No restating the title as the first
  sentence, no "In today's digital world...", no padding a thin idea into
  five paragraphs that all say the same thing with different words. If an
  article can be said accurately in 400 words, don't stretch it to 900.
- **Natural links to tools** — where a tool genuinely solves part of the
  problem being discussed, link it in context. Never force a tool mention
  into a sentence where it doesn't belong.
- **Useful headings** that describe what's actually in the section (a
  reader scanning only the headings should understand the article's shape).
- **FAQ only where genuinely useful** — a real FAQ answers questions a
  reader plausibly still has after the body content, not a rephrasing of
  the intro into question form to hit a count. It's fine for an article to
  have no FAQ section at all (see `png_vs_jpg_guide.html` — no FAQ, still
  excellent).
- **Accurate metadata** — title and description describe what the article
  actually contains, not a clickbait promise the body doesn't deliver on.

---

## 3. Explicitly forbidden

- Publishing an article whose only purpose is increasing page count or
  total site word count.
- Describing a QuickTools capability that doesn't exist (check against
  `ARCHITECTURE.md` §5 and the actual route in `app.py` before writing a
  single claim about what a tool does).
- Claiming a workflow QuickTools doesn't support end-to-end (e.g. don't
  write an article implying the site can composite a subject onto a new
  background after `remove-background` — it can't; stop the workflow
  explanation honestly at the point where the product's capability ends).
- Restating an existing tool page or guide's content under a new URL. Check
  `docs/EDITORIAL_AUDIT.md` and the relevant tool page before writing —
  if the question is already answered there, either skip the topic or make
  the new article's angle genuinely different (see the Instagram-sizing
  pair in the audit for a defensible example of two adjacent-but-distinct
  angles on one topic).
- Mass-producing near-identical articles by swapping one variable (e.g. a
  separate "resize image for Twitter," "resize image for LinkedIn,"
  "resize image for Pinterest" series) — this is exactly the doorway-page
  pattern that triggered the original AdSense rejection. One comprehensive
  piece with a table beats five thin variants (see
  `instagram_image_sizes_guide.html` for the right shape).

---

## 4. Verify before writing

Every technical claim about what QuickTools does must be checked against
the actual backend, the same discipline used for the tool-page remediation:

1. Read the real route in `app.py` for any tool the article references.
2. Read `ARCHITECTURE.md` §5–6 for the tool inventory and known
   limitations (no OCR, no true form-field filling, resize never crops,
   remove-background needs a paid remove.bg plan for commercial use, etc.).
3. If the article's premise requires a capability that doesn't exist,
   either drop that section or state the limitation honestly (this is what
   the tool-page remediation did throughout — e.g. `pdf_to_word.html`
   stating plainly that scanned PDFs don't convert well because there's no
   OCR).

---

## 5. Structural conventions (match the existing `/blog` pattern)

- Extends `base.html`; content wrapped in `<article class="guide-article">`.
- One `<h1>`, `<h2>` section headings, `<h3>` for FAQ questions if present.
- `{% block title %}` / `{% block description %}` — specific, not generic.
- `article()` JSON-LD macro (`self.title()`, `self.description()`,
  `request.path`, publish date) always. Add `faqpage()` **alongside** it
  (not replacing it — remember to keep both, the way the tool-page fix
  earlier this project had to add `{{ super() }}` to avoid losing the
  site-wide schema) whenever the article has a genuine on-page FAQ. This
  fixes a real, current gap: 0 of the 9 existing blog articles emit
  `FAQPage` JSON-LD today even though 4 of them have a real FAQ section —
  every new article should do this from day one.
- End with a "Related Tools" `.tools-mini-grid` (existing tool convention)
  and, where genuinely relevant, a short "Related Guides" list linking to
  1–2 existing articles — the current 9 articles almost never link to each
  other or to the 29 how-to guides; new articles should close that gap
  rather than repeat it.
- Add the new URL to `sitemap.xml` in the same pass that creates the page.

---

## 6. The AdSense angle — what this layer does and doesn't fix

This editorial layer is the site's answer to Google's specific "Low value
content" rejection reason: a directory of 31 near-identical utility pages,
however well each one is now written, still reads as a tools directory
first. Genuine, independently-useful articles — pieces a reader would bookmark
or share even if they never touch a QuickTools upload box — are evidence the
site is more than a wrapper around a handful of Python libraries. That's
the entire point of this milestone, and it's a real, structural gap the
prior tool-page remediation (commit `7baf1a6`) could not close on its own,
because it worked strictly within the "add content to each existing tool
page" constraint.

**This does not guarantee AdSense approval, and no one should claim it
does.** Concretely, what remains unaddressed even after this editorial
layer ships:

- **Volume and track record.** A handful of new articles doesn't establish
  the kind of publishing history/authority signal Google's reviewers often
  expect from an approved site — this is a multi-month effort, not a single
  milestone.
- **Traffic and engagement are unknown and unmeasured.** There's no
  analytics layer in this project (`ARCHITECTURE.md` confirms no database,
  no auth, no tracking beyond AdSense's own script) — there is no way to
  confirm whether any article actually gets read, ranks, or gets organic
  traffic before or after publishing it.
- **The core product is still a utility site.** Even a strong editorial
  layer sits alongside 31 tool pages whose primary function is "upload,
  process, download." Google's reviewers may still weigh that core
  identity heavily regardless of how good the surrounding content is.
- **Nothing here addresses AdSense policy concerns unrelated to content
  depth** (site ownership verification, ads.txt correctness, traffic
  quality/sourcing, prior account history) — those are outside this
  project's ability to audit from inside the codebase.

Treat this layer as a genuine, worthwhile investment in making the site
better for real users — and a plausible contributing factor to a future
AdSense re-review — not as a guaranteed fix.
