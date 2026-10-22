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
- **Status:** Done
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

**Resolved (2026-10-22):** `scripts/faq_schema_audit.py` renders every GET page through Flask and diffs visible FAQ pairs against the `FAQPage` JSON-LD; it reports 0 mismatches across all 80 pages that have an FAQ.

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
- **Status:** Done
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

**Resolved (2026-10-22, branch `fix/security-and-adsense-2026-10`):** rolled out sitewide. `base.html` now renders the visible trail and `BreadcrumbList` JSON-LD for any page that sets `breadcrumb_label` (85 tool, guide, blog and hub pages); `breadcrumb_trail()` in `app.py` derives the parent section from the URL. The 11 hand-written breadcrumb calls were migrated so no page emits two trails. `SEO_GUIDELINES.md` and `COMPONENT_LIBRARY.md` updated.

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
- **Status:** Done
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

**Resolved (2026-10-22):** every guide now emits `FAQPage`; the last gap found by `scripts/faq_schema_audit.py` was the `/rotate-pdf` tool page, fixed on the same branch. The audit reports 0 pages with a visible FAQ and no schema.

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
- **Status:** Done
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

**Resolved (2026-10-22, branch `fix/security-and-adsense-2026-10`, commit B1):** `compress_pdf()` now writes `<output>.error` with a user-safe message when Ghostscript fails ("temporarily unavailable" when the binary is missing), `/status/<file>` returns `{"ready": false, "error": ...}`, and `processing.html` stops polling and shows the message with a Try again link. It also gives up client-side after ~3 minutes, matching `--timeout 180`. The success path is unchanged.

---

## QT-011 — `/uploads/<filename>` has no auth or expiry check at serve time

- **Area:** Security
- **Priority:** P3
- **Status:** Done
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

**Resolved (2026-10-22, branch `fix/security-and-adsense-2026-10`, commit A6):** the route is kept for its only consumer (the sign-pdf signature preview) but now serves image extensions only (png/jpg/jpeg/webp/gif) and returns 404 for anything else, so PDFs, documents and ZIPs can't be fetched through it. It and `/download-file/<name>` send `X-Robots-Tag: noindex`. An expiry check at serve time was not added: every file is deleted within 10 minutes, so the window this would close is already short.

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

---

## QT-014 — Same-name uploads from two users could overwrite or leak each other's files

- **Area:** Security
- **Priority:** P0
- **Status:** Done
- **Discovered:** Fix spec review (2026-10-22)
- **Source:** `app.py`: 14 routes saved uploads under the bare `secure_filename()`

**Problem:** jpg-to-pdf, pdf-to-png/jpg/webp, extract-images, pdf-to-word, word-to-pdf, protect-pdf, unlock-pdf, add-page-numbers, add-watermark, pdf-to-excel, excel-to-pdf and pdf-to-text saved uploads (and several outputs) without a UUID prefix. Two people uploading `invoice.pdf` at the same time could overwrite each other's input or download each other's result.

**Proposed improvement:** N/A — already implemented.

**Notes:** Fixed on branch `fix/security-and-adsense-2026-10` (A1/A2/A3): new `save_upload()` helper (UUID-prefixed name + scheduled deletion), UUID-named outputs, and friendly names via `send_file(download_name=...)`. Verified with concurrent same-name uploads of different content: each user got their own result.

---

## QT-015 — Converter output names could overwrite the input (`.replace(".pdf", ...)`)

- **Area:** Technical
- **Priority:** P0
- **Status:** Done
- **Discovered:** Fix spec review (2026-10-22)
- **Source:** `app.py`: pdf-to-word, word-to-pdf, pdf-to-excel, excel-to-pdf, pdf-to-text

**Problem:** Output names were built with `filename.replace(".pdf", ".docx")` and similar. `SCAN.PDF` or an `.xls` input made the output path equal the input path, and word-to-pdf looked for the wrong LibreOffice output for `.doc`/`.odt`/`.DOCX`, reporting "Conversion failed" after a successful conversion.

**Proposed improvement:** N/A — already implemented.

**Notes:** Fixed on branch `fix/security-and-adsense-2026-10` (A3): outputs use `uuid + splitext stem`, extensions are checked case-insensitively, and word-to-pdf expects `splitext(input) + ".pdf"`. LibreOffice is now called as `soffice` on Windows (like `gswin64c`/`gs`) so the route can be tested locally. Verified: `SCAN.PDF` → `SCAN.docx`; `.doc`, `.docx`, `.DOCX` and `.odt` all convert.

---

## QT-016 — Path traversal in sign-pdf / add-text-to-pdf / redact-pdf step 2

- **Area:** Security
- **Priority:** P0
- **Status:** Done
- **Discovered:** Fix spec review (2026-10-22)
- **Source:** `app.py`: `existing_file` / `signature_file` form fields

**Problem:** The second step of the two-step tools joined a client-supplied form value onto `UPLOAD_FOLDER`, so `existing_file=../app.py` escaped `uploads/`.

**Proposed improvement:** N/A — already implemented.

**Notes:** Fixed on branch `fix/security-and-adsense-2026-10` (A4): `resolve_upload()` accepts only a plain filename that exists inside `uploads/`; anything else returns a 400 "File missing or expired" page. Verified with `../app.py` and `..\\app.py` on all three routes.

---

## QT-017 — Some uploads and outputs were never deleted

- **Area:** Security
- **Priority:** P1
- **Status:** Done
- **Discovered:** Fix spec review (2026-10-22)
- **Source:** `app.py`: extract-images, merge-pdf, jpg-to-pdf, sign-pdf

**Problem:** extract-images never deleted its input or extracted images; merge-pdf and jpg-to-pdf never deleted their outputs; sign-pdf only scheduled deletion in step 2, so abandoned sessions kept files forever. Several routes also left `fitz` documents open.

**Proposed improvement:** N/A — already implemented.

**Notes:** Fixed on branch `fix/security-and-adsense-2026-10` (A5). All retention periods are now listed per tool in the privacy policy; the longest is 10 minutes.

---

## QT-018 — Invalid input returned a 500 or a bare-text page

- **Area:** UX
- **Priority:** P1
- **Status:** Done
- **Discovered:** Fix spec review (2026-10-22)
- **Source:** `app.py`: numeric/form parsing in rotate, crop, sign, add-text, redact; protect/unlock passwords; image routes

**Problem:** Non-numeric or out-of-range form values raised and showed the 500 page; wrong unlock passwords produced a garbage PDF; jpg-to-pdf with no valid files called `send_file` on a path that didn't exist; many routes returned bare strings like "No file selected" with a 200 status on an unstyled white page.

**Proposed improvement:** N/A — already implemented.

**Notes:** Fixed on branch `fix/security-and-adsense-2026-10` (B2/B3): `error_page(message, status)` renders `templates/error.html` (noindex) with a 4xx status; a 400 handler covers missing form fields; corrupt/non-PDF uploads that make PyMuPDF/PyPDF2/pdfminer raise return 400 instead of 500. Each case in the spec's B2 table was exercised against a running server.

---

## QT-019 — PDF to WebP result page showed no download links

- **Area:** UX
- **Priority:** P0
- **Status:** Done
- **Discovered:** End-to-end verification of the fix spec (2026-10-22)
- **Source:** `templates/pdf_to_webp_result.html`

**Problem:** The template looped over `files`, but the route passes `images`, so every PDF to WebP conversion ended on a page with nothing to download.

**Proposed improvement:** N/A — already implemented.

**Notes:** Fixed on branch `fix/security-and-adsense-2026-10`: the template loops over `images` and labels each link "Download page N".

---

## QT-020 — Ad units on result/download screens; non-content pages indexable

- **Area:** Monetization
- **Priority:** P0
- **Status:** Done
- **Discovered:** AdSense "Low value content" rejection review (2026-10-22)
- **Source:** `result.html`, `compress_jpg_result.html`, `extract_images_result.html`

**Problem:** Three result screens carried manual `<ins class="adsbygoogle">` units (with a placeholder slot id) on pages with no publisher content, which AdSense policy disallows; result, processing and error pages were also indexable.

**Proposed improvement:** N/A — already implemented.

**Notes:** Fixed on branch `fix/security-and-adsense-2026-10` (C1): ad units removed (the loader stays in `base.html`), and a `{% block robots %}` sets noindex on processing, every result page, 404/413/500 and `error.html`. Do not add ad units until the site is approved.

---

## QT-021 — Remove Watermark doesn't recognise its own watermark on A4 (non-Letter) pages

- **Area:** Technical
- **Priority:** P1
- **Status:** Open
- **Discovered:** End-to-end verification of the fix spec (2026-10-22)
- **Source:** `app.py` `add_watermark()` / `_is_own_watermark_span()`

**Problem:** `add_watermark()` draws its overlay on a Letter-size canvas, so on an A4 page the watermark lands 50pt higher than on Letter (span bbox y≈410.7 instead of ≈360.7). `_is_own_watermark_span()` requires y≈360.7, so watermarks added by QuickTools to A4 PDFs are not removed. Verified: removal works on a 612×792 page and fails on 595×842.

**Proposed improvement:** Match the watermark position relative to the page height (or record the y used when adding it), then re-run the near-miss checks from QT-013 on Letter, A4 and a landscape page.

**Notes:** Not fixed on this branch: it changes file-processing logic, which the fix spec didn't cover.

---

## QT-022 — JPG/PNG to PDF re-encode every image as lossy JPEG

- **Area:** Technical
- **Priority:** P2
- **Status:** Open
- **Discovered:** Real-results measurements (C3, 2026-10-22)
- **Source:** `app.py` `jpg_to_pdf()` / `png_to_pdf()` → Pillow `Image.save(..., save_all=True)` on RGB images

**Problem:** Pillow's PDF writer stores RGB images as DCTDecode (JPEG) at its default quality, so every image is re-compressed: a 682 KB JPG became a 387 KB PDF, and lossless PNG screenshots pick up JPEG artifacts. The pages claimed images were embedded "at original quality" with "no compression"; that copy has been corrected.

**Proposed improvement:** Embed JPEGs without re-encoding (e.g. PyMuPDF `insert_image` with the original bytes) and embed PNGs losslessly (Flate), then update the copy and re-run `scripts/measure_examples.py`.

**Notes:** Copy corrected on the fix branch so the pages describe current behaviour; the conversion code is unchanged.

---

## QT-023 — Transparent PNG areas turn black in PNG/JPG to PDF

- **Area:** Technical
- **Priority:** P2
- **Status:** Open
- **Discovered:** Real-results measurements (C3, 2026-10-22)
- **Source:** `app.py` `open_upload_images()` → `Image.convert("RGB")`

**Problem:** `convert("RGB")` drops alpha without compositing, so transparent pixels keep their stored colour — black for most PNGs. A logo on a transparent background comes out on a black box. The PNG guide said transparent areas render white; corrected.

**Proposed improvement:** Composite RGBA/LA/P-with-transparency images onto white before converting (the same approach `_letterbox_resize()` already uses).

**Notes:** Copy corrected on the fix branch; conversion code unchanged.

---

## QT-024 — Remove Background has no measured "Real Results" section

- **Area:** Content
- **Priority:** P2
- **Status:** Open
- **Discovered:** C3 (2026-10-22)
- **Source:** `scripts/measure_examples.py`

**Problem:** The other seven top tools show measured results generated from `static/examples/`. Remove Background can only be measured with a remove.bg API key, which isn't available locally, and numbers must not be invented.

**Proposed improvement:** With `REMOVE_BG_API_KEY` set, add a `measure_remove_background()` step (e.g. a portrait and a product photo with fine edges) to the script, include its partial on `remove_background.html`, and re-run.

**Notes:** Each call uses a paid remove.bg credit; see QT-008 for the licensing check.

---

## QT-025 — Cookie banner is not a Google-certified CMP

- **Area:** Monetization
- **Priority:** P1
- **Status:** Open
- **Discovered:** C4 privacy review (2026-10-22)
- **Source:** `templates/base.html` cookie banner

**Problem:** The banner now records consent and, until a visitor accepts, asks AdSense for non-personalised ads (`requestNonPersonalizedAds`). Google requires a Google-certified CMP (IAB TCF) to serve ads to users in the EEA, UK and Switzerland; a custom banner doesn't meet that requirement.

**Proposed improvement:** In AdSense → Privacy & messaging, enable Google's own consent message (or another certified CMP) for EEA/UK/CH, then remove or reduce the custom banner so visitors aren't asked twice, and update the privacy policy's banner section.

**Notes:** Owner/account task, not a code change.

---

## QT-026 — About page names the company but not the person behind it

- **Area:** Content
- **Priority:** P2
- **Status:** Open
- **Discovered:** C4 trust review (2026-10-22)
- **Source:** `templates/about.html`

**Problem:** The About page now says QuickTools is run by HelloBrivio and gives a direct email, but no person's name or registered company details. Readers and reviewers weigh a named owner as a trust signal.

**Proposed improvement:** Add the owner's name (and registered business details if HelloBrivio is a registered company) to the "Who Runs QuickTools" section, and consider a matching `Person` author in the BlogPosting JSON-LD.

**Notes:** Needs the owner's input; nothing was invented.
