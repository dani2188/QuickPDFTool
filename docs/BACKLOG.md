# QuickTools Backlog

A lightweight, human-readable backlog of concrete future work discovered
during development, technical investigations, SEO/content audits, and
editorial QA. This is not a roadmap and carries no dates, sprints, or
commitments — it exists so the project can be picked back up months later
with a clear record of what needs attention, why, where it came from, and
what we intended to do about it.

## How to use this backlog

- Tasks must be concrete and actionable — not goals like "improve SEO" or
  "add more content."
- Every task records where it was discovered, so the reasoning behind it
  isn't lost.
- Completed tasks may be retained (marked **Done**) for historical
  traceability rather than deleted — they are not open work.
- When starting a task, update its **Status**. When finishing one, set it to
  **Done** and leave it in place rather than removing it.
- Add new tasks in the same format, with the next sequential `QT-XXX` ID.

**Statuses:** Open · Planned · In Progress · Done · Won't Do

**Priorities:**
- **P0** — Critical / blocking
- **P1** — Important
- **P2** — Useful improvement
- **P3** — Nice to have

**Task format:**

```
## QT-XXX — Short task title

- **Area:** UX / SEO / Content / Technical / Performance / Security / Infrastructure / Monetization
- **Priority:** P0/P1/P2/P3
- **Status:** Open
- **Discovered:** date or milestone
- **Source:** where the issue was discovered
- **Problem:** concise description
- **Proposed improvement:** concrete future action
- **Notes:** relevant implementation details, dependencies, or caveats
```

---

## QT-001 — Show effective 12 MB limit for Remove Background

- **Area:** UX
- **Priority:** P1
- **Status:** Open
- **Discovered:** Article #4 technical research (2026-09-16)
- **Source:** Remove Background implementation inspection (`app.py`, `/remove-background` route)

**Problem:** QuickTools has a general upload limit of 20 MB
(`MAX_CONTENT_LENGTH` in `app.py`), while the remove.bg API used by the
Remove Background tool has a documented 12 MB request limit. An uploaded
file between 12 MB and 20 MB therefore passes QuickTools' own upload
validation but subsequently fails at the external provider, returning only
a generic "could not remove the background" error.

**Proposed improvement:** Show the effective Remove Background file-size
limit (12 MB, not 20 MB) in the tool's UI, and validate against that limit
before sending the file to remove.bg. Improve the resulting error message so
users understand the file was too large for this specific tool, rather than
receiving only a generic provider-failure message.

**Notes:** Do not change the implementation as part of logging this
backlog item. Do not expose API credentials in any UI copy or error
message.

---

## QT-002 — Fix remaining FAQPage JSON-LD dash mismatches

- **Area:** SEO / Technical
- **Priority:** P2
- **Status:** Open
- **Discovered:** Article #2/#3/#4 editorial QA (2026-09-11 through 2026-09-16)
- **Source:** Automated FAQ visible-content vs. JSON-LD comparison

**Problem:** During article QA, FAQPage JSON-LD answers were found to
differ from their visible FAQ answers because the visible HTML used em
dashes (—) while the inline JSON-LD data used double hyphens (--). The
issue was caught and fixed in the newer articles (Article #3, Article #4)
during their respective milestones. Article #2
(`templates/blog/why_pdf_to_word_conversion_looks_wrong.html`) still
contains the previously identified remaining mismatches (confirmed: 3 of 7
FAQ entries).

**Proposed improvement:** Perform a dedicated audit of every FAQPage
JSON-LD block sitewide and confirm each question and answer exactly
matches its corresponding visible FAQ text, character for character. Fix
any mismatch found.

**Notes:** Do this as a separate cleanup task rather than reopening
completed article milestones. A short script that extracts visible
`<h3>`/`<p>` FAQ pairs and diffs them against the rendered `FAQPage`
JSON-LD (the same method used ad hoc during Article #3/#4 QA) would cover
the whole site in one pass.

---

## QT-003 — Correct PDF-to-Word scanned-PDF OCR documentation

- **Area:** Content
- **Priority:** P1
- **Status:** Done
- **Discovered:** Article #2 technical research
- **Source:** `templates/pdf_to_word_guide.html`, verified against the real `/pdf-to-word` route

**Problem:** The PDF-to-Word guide's FAQ answer implied scanned PDFs could
be converted via OCR with reduced accuracy ("may not be perfectly
accurate"), when the actual tool performs no OCR at all — a scanned PDF
converts to a Word document with the page embedded as an image and zero
selectable text.

**Proposed improvement:** N/A — already implemented.

**Notes:** Corrected during the Article #2 milestone (commit `004453f`).
Retained here only for historical traceability; not open work.

---

## QT-004 — Breadcrumb navigation and BreadcrumbList JSON-LD are only on 4 of ~96 pages

- **Area:** SEO
- **Priority:** P2
- **Status:** Open
- **Discovered:** Backlog creation pass (2026-09-17)
- **Source:** `grep -rl "components/breadcrumb" templates/` (4 matches out of 96 page templates); `docs/SEO_GUIDELINES.md` §1 ("BreadcrumbList **to add**"); `docs/COMPONENT_LIBRARY.md` Breadcrumb entry ("Status: not yet implemented")

**Problem:** The `breadcrumb`/`breadcrumb_jsonld` component
(`templates/components/breadcrumb.html`) exists and is used by the four
newest blog articles (Articles #2–#4 plus `scanned_documents_to_pdf.html`),
but none of the ~31 tool pages, ~29 how-to guides, or the other 9 blog
articles have visible breadcrumb navigation or `BreadcrumbList` JSON-LD.
`SEO_GUIDELINES.md` and `COMPONENT_LIBRARY.md` both still describe this as
sitewide work not yet done.

**Proposed improvement:** Decide whether breadcrumbs should roll out
sitewide (tool pages, guides, remaining blog articles) or stay scoped to
new editorial content going forward, and update `SEO_GUIDELINES.md` /
`COMPONENT_LIBRARY.md` to reflect whichever is decided so the docs stop
describing it as entirely unimplemented.

**Notes:** The component itself needs no new work — this is purely about
applying it more broadly (or explicitly deciding not to) and correcting
two now-stale doc statements.

---

## QT-005 — `/blog` nav label doesn't match the page's own section names

- **Area:** Content
- **Priority:** P3
- **Status:** Open
- **Discovered:** `docs/EDITORIAL_AUDIT.md` §1 (2026-09-09), confirmed still true 2026-09-17
- **Source:** `templates/base.html` (3 nav/footer links labeled "Guides") vs. `templates/blog.html` (sections titled "Latest Articles" and "How-To Guides")

**Problem:** The top nav and footer both link to `/blog` labeled "Guides,"
but the page itself never calls its content "Guides" as a whole — it splits
into a "Latest Articles" section and a separate "How-To Guides" section.
Three different names for overlapping content is a minor but real naming
inconsistency.

**Proposed improvement:** Pick one consistent name for the `/blog`
destination across nav, footer, and on-page headings (e.g. rename the nav
link to "Guides & Articles," or rename the on-page sections to align with
"Guides"), and apply it in all three places.

**Notes:** Purely a naming/labeling fix — no routing or content changes
required.

---

## QT-006 — 25 of 29 how-to guides have an on-page FAQ but no FAQPage JSON-LD

- **Area:** SEO
- **Priority:** P2
- **Status:** Open
- **Discovered:** `docs/EDITORIAL_AUDIT.md` §3 (2026-09-09), confirmed still true 2026-09-17
- **Source:** `grep -l "faqpage(" templates/*_guide.html` (4 of 29 matches)

**Problem:** All 29 `*_guide.html` how-to pages have a genuine, on-page FAQ
section (4–5 questions each), but only 4
(`remove_background_guide.html`, `resize_image_guide.html`,
`compress_jpg_guide.html`, `redact_pdf_guide.html`) emit `FAQPage` JSON-LD
alongside their `HowTo` schema. The other 25 guides' FAQ content isn't
represented in structured data at all.

**Proposed improvement:** Add `faqpage()` (alongside the existing
`howto()` call, not replacing it) to the remaining 25 guide templates,
using their existing on-page FAQ text verbatim so visible content and
JSON-LD match exactly from the start (see QT-002 for why that matters).

**Notes:** Mechanical, low-risk, high-volume task — the FAQ content
already exists on every page; this is only about also emitting it as
structured data.

---

## QT-007 — `requirements.txt` remains unpinned beyond the one `reportlab` exception

- **Area:** Infrastructure
- **Priority:** P2
- **Status:** Open
- **Discovered:** `ARCHITECTURE.md` §8–9 (documented, unresolved as of 2026-09-17)
- **Source:** `requirements.txt`; the `reportlab<4.4.3` incident (commit `bad3845`)

**Problem:** Every dependency except `reportlab` has no version pin, so a
future `pip install -r requirements.txt` on Render can silently resolve a
newer major version than what's installed and tested locally
(`.venv` currently has Flask 3.0.3, Pillow 10.4.0, PyMuPDF 1.24.11,
PyPDF2 3.0.1, reportlab 4.4.2, requests 2.32.4). The `reportlab` incident —
where 4.4.3+ broke `add-page-numbers`/`add-watermark`/`excel-to-pdf` on
Python 3.8 until pinned back — is a concrete example of what this can
silently break.

**Proposed improvement:** Pin exact versions for the remaining
dependencies in `requirements.txt` (or generate a lockfile), matching what
is actually installed and verified in the local `.venv`.

**Notes:** Low risk, mechanical change, but should be tested against a
full local run of every tool before deploying, since it's touching the
dependency set for the whole app at once.

---

## QT-008 — Confirm remove.bg plan is licensed for commercial, ad-monetized use

- **Area:** Monetization
- **Priority:** P1
- **Status:** Open
- **Discovered:** `ARCHITECTURE.md` §6 (documented, unresolved as of 2026-09-17)
- **Source:** `ARCHITECTURE.md`: "remove.bg's free tier is non-commercial-use-only, so a paid/commercial plan is required for this to run legitimately on an ad-monetized site."

**Problem:** QuickTools is an AdSense-monetized site, and the Remove
Background tool proxies every request to remove.bg. remove.bg's free tier
is documented as non-commercial use only. Whether the API key currently
configured via `REMOVE_BG_API_KEY` is on a plan that actually permits this
usage hasn't been confirmed as part of any reviewed milestone.

**Proposed improvement:** Confirm the remove.bg account/plan backing the
production `REMOVE_BG_API_KEY` is licensed for commercial use on an
ad-monetized site, and upgrade it if it isn't.

**Notes:** This is an account/billing check, not a code change — nothing
in `app.py` needs to change regardless of the plan tier, since the key is
read from the environment either way.

---

## QT-009 — `pdf-to-word` (and similar) permanently bloat worker memory; OOM risk on Render

- **Area:** Performance
- **Priority:** P1
- **Status:** Open
- **Discovered:** `ARCHITECTURE.md` §8 (documented, unresolved as of 2026-09-17)
- **Source:** Local measurement recorded in `ARCHITECTURE.md`: server process ~93 MB working set at cold start, rising to ~394 MB working set / ~598 MB private memory after the first `pdf-to-word` request, and never dropping back down

**Problem:** `pdf-to-word` pulls in `opencv-python-headless` and `numpy`
via `pdf2docx`, imported lazily on first use; `pdf-to-excel`/`excel-to-pdf`
do the same via `pandas`/`openpyxl`. Once any of these routes is hit once,
the Gunicorn worker's memory footprint permanently jumps by roughly
300 MB+ and never returns, regardless of the size of any individual
upload. With `render.yaml` running a single worker on Render's
default/free-tier RAM, this is a real, unquantified OOM risk that
compounds with the existing 20 MB upload cap.

**Proposed improvement:** Measure actual memory headroom on the real
Render plan in use (not just locally), and decide whether to: increase the
Render plan's RAM, isolate the heavy-import routes into a separate worker
process, or accept the current risk with monitoring/alerting for OOM
kills.

**Notes:** Not something to fix by changing `app.py`'s processing logic —
this is a deployment-sizing and monitoring question, not a code defect.

---

## QT-010 — Ghostscript compression failures are swallowed instead of surfaced

- **Area:** Technical
- **Priority:** P2
- **Status:** Open
- **Discovered:** `ARCHITECTURE.md` §6/§8 (documented, unresolved as of 2026-09-17)
- **Source:** `app.py` `compress_pdf()`, line ~297: `print("Compression ERROR:", e)`

**Problem:** `compress_pdf()` catches every exception from the Ghostscript
subprocess call and only prints it to the server log. If Ghostscript isn't
installed or the call fails for any other reason, the user gets no output
file and no error message explaining why — the request just silently
produces nothing.

**Proposed improvement:** Surface a clear user-facing error (e.g. via the
existing `/status/<file>` polling flow) when compression fails, instead of
leaving the user watching a processing page that never completes.

**Notes:** Must preserve the existing background-thread + polling flow
exactly, per the project's hard constraints — this is about adding an
error signal to that flow, not changing how it works.

---

## QT-011 — `/uploads/<filename>` has no auth or expiry check at serve time

- **Area:** Security
- **Priority:** P3
- **Status:** Open
- **Discovered:** `ARCHITECTURE.md` §8 (documented, unresolved as of 2026-09-17)
- **Source:** `app.py` route `/uploads/<filename>` (line ~2415)

**Problem:** Any file in `uploads/` is servable directly by filename with
no authentication and no check on whether it's already past its scheduled
deletion time. Filenames are UUID-prefixed and therefore not guessable,
which is the primary mitigation already in place, but a file is
technically downloadable by anyone who obtains its exact URL for as long
as it exists on disk before `delete_file_later` removes it.

**Proposed improvement:** Consider adding an expiry check at serve time
(return 404 if the file is past its intended lifetime, independent of
whether the deletion thread has actually run yet) as defense in depth.

**Notes:** Low urgency given UUID-based unguessability already in place;
this is a hardening improvement, not a known exploited vulnerability.

---

## QT-013 — "Remove Watermark" did not remove watermarks, contradicting its own FAQ

- **Area:** Technical / Content
- **Priority:** P0
- **Status:** Done
- **Discovered:** post-Article-#6 editorial audit (2026-09-18), confirmed via empirical testing
- **Source:** `app.py` `remove_watermark()` (previously only called `page.clean_contents()`), tested against the live `/add-watermark` → `/remove-watermark` round trip

**Problem:** `remove_watermark()` only ran PyMuPDF's generic content-stream
sanitizer (`clean_contents()`), which has no concept of "watermark" and
removed nothing. Empirical testing confirmed QuickTools' own watermark
text, a genuine PDF annotation, and vector graphics all survived the
"removal" unchanged. This directly contradicted claims on
`remove_watermark.html`, `remove_watermark_guide.html`,
`add_watermark.html`, and `blog/pdf_security_basics.html` that the tool
removed watermarks added by QuickTools' own Add Watermark tool.

**Proposed improvement:** N/A — already implemented.

**Notes:** Fixed in commit `8371c7a` ("Fix QuickTools watermark
removal"). `remove_watermark()` now matches text spans against Add
Watermark's exact signature (font `Helvetica`, size `40`, opacity `≈0.3`,
gray `≈0.572`, position `x≈150, y≈360.7` — all hardcoded in
`add_watermark()`) via `page.get_texttrace()`, then removes matches with
`add_redact_annot()`/`apply_redactions()` (the same API already used by
`redact_pdf()` elsewhere in this codebase) before the existing
`clean_contents()` pass runs. Verified against the real routes: removal
confirmed on 1-page and 3-page PDFs and with varying watermark text;
several deliberate near-miss cases (legitimate text at a different
position, plain text containing the watermark's exact string, the
closest near-miss at the same x but a different y) all correctly survived
with no false positives; unrelated content on a watermarked page (title,
body text, lines, rectangles, an embedded image) was left untouched.
Documentation corrected on the three pages that overstated the tool's
scope; `add_watermark.html`'s existing claim was already accurate and
left unchanged. General/third-party watermark removal remains explicitly
out of scope — this fix only recognizes QuickTools' own watermark format.
