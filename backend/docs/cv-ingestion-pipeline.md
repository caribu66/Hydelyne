# CV Ingestion Pipeline

Living doc for how a CV goes from "uploaded" to "populating a consultant's profile" in this
system, and why it's built the way it is. Companion to
[`consultant-knowledge-core.md`](./consultant-knowledge-core.md), which covers the *read* side
(search, summaries); this doc covers the *write* side (extraction). Update this file in the
same commit as the code change it describes.

## Why this exists

Formalized as [`docs/decisions/0003-deterministic-cv-extraction.md`](../../docs/decisions/0003-deterministic-cv-extraction.md) —
this doc is the implementation detail, the ADR is the decision record.

CV extraction originally depended on an LLM call (`qwen2.5:14b` via Ollama) per document. That
call requires a GPU worker — a GPU worker that doesn't even start on this host (no NVIDIA
device present). Since every CV in this system comes from **one fixed template**, that AI
dependency was mostly unnecessary: a deterministic PDF-table/text parser already existed
(`app/services/cv_table_extractor.py`) and, per its own tests, already **outperformed** the LLM
on this template — more training rows recovered, exact dates, no invented fields.

**Design principle: CV extraction never calls AI.** A tool deterministically pulls structured
fields out of the PDF; the two genuinely free-text sections (professional summary, skills
prose) are stored as-is, uninterpreted. AI's role is entirely at *read* time — search,
summaries, agent queries (see `consultant-knowledge-core.md`) — never at ingestion. If a CV
doesn't fit the template (wrong file type, or the parser can't find the expected structure),
it is **not** sent to AI as a fallback — it's flagged for manual review instead.

## The full lifecycle: submission, review, and publication

1. **A staff-owned draft is created.** The CV-led `createCrewMember` call writes a
   `CrewMember` with `publication_status="draft"`. It is deliberately excluded from
   ordinary, keyword, and natural-language search.
2. **If a CV was attached, it's a separate upload right after.** The modal doesn't send the CV
   as part of crew creation — it creates the crew member first, then does a real multipart
   upload (`POST /api/documents/upload`, `app/api/documents.py`), which creates a `Document`
   row (`extraction_status="pending"`) and queues `process_document_extraction` on the Celery
   `gpu` queue.
3. **The frontend polls for the terminal status** (`AddCrewMemberModal.tsx`) every 2 seconds,
   up to 60 seconds, so the UI reflects the real outcome instead of just "uploaded". In
   practice this finishes in under a second now — no LLM round trip to wait on.
4. **What the worker does** (`SyncDocumentProcessor.process`, `app/services/sync_processor.py`):
   extract text → run `CVProcessingService.extract_cv_deterministically` → write the result
   onto `Document.extracted_data`/`extracted_text` and its `CVReview` proposal. It does not
   update canonical profile fields.
5. **Administrator review:** the admin opens the original CV beside the proposal, corrects
   or rejects values, then approves. Approval applies the reviewed proposal, changes the
   profile to `approved`, and adds it to Meilisearch. Only then can natural search return it.
6. **Possible outcomes:**
   - **Template recognized** → `extraction_status = "awaiting_review"` until approval.
   - **Template not recognized** (non-PDF, or the parser finds no personal info and no work
     history) → `extraction_status` routes to `"needs_review"` via a deliberately low
     confidence signal (`{"all": 0.0}`) — see "Failure path" below. No guessing, no AI
     fallback.

Exact name/email matches block a CV-led draft as a possible duplicate. An admin
may explicitly confirm that the person is distinct; the system never auto-merges.

## Where the deterministic extraction actually lives

**`CVProcessingService.extract_cv_deterministically`** (`app/services/cv_processing.py`) is the
single shared entry point — both Celery-based processing paths call it:

- `app/services/sync_processor.py` — the Celery/synchronous path (the one described above).
- `app/services/document_service.py` — an async/non-Celery variant of the same pipeline. Kept
  structurally parallel rather than merged with `sync_processor.py` (merging the two duplicate
  pipelines is a known, separate, larger refactor — not done here).

A **third** call site exists and is easy to miss: **`POST /api/documents/preview-cv`**
(`app/api/documents.py`) — used only by the "Add Specialist" modal to pre-fill
name/nationality *before* a crew record exists, from the CV the operator is about to attach.
This also uses the deterministic table extractor directly (`extract_cv_tables`), not
`extract_cv_deterministically` (it only needs `full_name` + `nationality`, not the full
profile-write-back shape) — same "no LLM" rule applies here too.

## What's deterministic vs. what genuinely isn't

Extracted by `cv_table_extractor.py` (PDF-table/text parsing, no AI):

| Field | Source |
|---|---|
| `full_name` | First non-empty line of page 1, validated to look name-like |
| `professional_summary` | Verbatim text of the PROFESSIONAL SUMMARY section |
| `skills` | The "Skills & Competencies" bullet list, split mechanically (bullet detection, wrapped-line merging) — not interpreted |
| `nationality`, `country_of_residence`, `date_of_birth`, `gender`, `flying_point`, `education`, `languages` | PERSONAL INFORMATION table |
| `expertise` | EXPERTISE table |
| `geographical_experience` | GEOGRAPHICAL EXPERIENCE table |
| `systems` | SYSTEMS EXPERIENCE table |
| `training_qualifications` (+ structured per-row place/completed/expiry dates) | TRAINING table |
| `certifications` | Short-token match against training row names (`_SHORT_CERT_TOKENS`) |
| `work_history` | RECENT PROJECTS table (client/country/survey type/role/year) |

**Genuinely absent from the template, not extracted by anything (deterministic or AI):**
`email`, `phone`, `address` — confirmed by inspecting the real fixture
(`tests/fixtures_helena_cv.txt`), this template never carries them. They're populated by
manual entry, not CV extraction. Don't add extraction logic for these — there's nothing there
to find.

**Known, accepted gaps** (documented, not bugs):
- `WorkHistory.location` is always `None` from CV-sourced rows — the template's RECENT
  PROJECTS table has a CONTRACTOR/VESSEL column, not a true location column, and vessel data
  has nowhere else to go without a schema change (out of scope).
- `WorkHistory.responsibilities` is always `None` from CV-sourced rows — the template doesn't
  carry per-project responsibility text.

## Failure path (needs_review, not AI fallback)

`extract_cv_deterministically` returns a minimal stub when the template isn't recognized:
`{"document_type": "cv", "extraction_method": "deterministic_failed", "confidence": {"all": 0.0}}`.
The `confidence` shape is deliberate — `extraction_service.determine_review_status` only
reasons about per-field confidence scores, so a single low score is what routes the document
to `"needs_review"` through the *existing* review mechanism, without adding a parallel
signaling path. This triggers for:
- Any CV that isn't a PDF (`cv_table_extractor.py` is PDF-only via `pdfplumber`).
- A PDF where the parser finds neither `personal_information` nor `work_history` — i.e. it
  doesn't look like this template at all.

## Phase status

| Item | Status | Date | Notes |
|---|---|---|---|
| Deterministic extraction (`full_name`, `professional_summary`, `skills`) | Shipped | 2026-09-02 | `cv_table_extractor.py` extended; `extraction_method`/`extraction_status` shipped end-to-end, live-verified with zero Ollama calls, sub-second processing. |
| LLM removed from `sync_processor.py` / `document_service.py` CV branches | Shipped | 2026-09-02 | No fallback to AI for non-template CVs — routes to `needs_review` instead. |
| `CrewMember.professional_summary` column | Shipped | 2026-09-02 | Migration `012_add_professional_summary`. Populated fill-if-empty, same pattern as `education`. |
| Frontend: re-enabled dead Overview-tab sections, real "Clients" list, real professional summary | Shipped | 2026-09-02 | Was dead code (`{false && ...}`) since before this work. |
| Frontend: real CV/document content viewer | Shipped | 2026-09-02 | Replaced the fake "certificate card" preview with structured fields + raw text toggle. |
| Celery "attached to a different loop" fix | Shipped | 2026-09-02 | `app/database.py::dispose_engine()`; a long-lived worker processing a second CV in the same process was failing outright before this. |
| Overview-tab certification badges (was regex over tags) | Shipped | 2026-09-02 | Now sourced from the real `certifications` table via `mappers.ts`. |
| Bullet-glyph leak in EXPERTISE table extraction | Shipped | 2026-09-02 | Template's Private-Use-Area bullet character now stripped in `_extract_expertise`, same fix already applied to the newer skills extraction. |
| `/api/documents/preview-cv` still called the LLM | Shipped | 2026-09-02 | Found while updating stale UI copy ("AI will extract...") — switched to `extract_cv_tables`, copy corrected to describe only what it actually does (name + nationality). |
| Duplicate pipeline (`sync_processor.py` vs `document_service.py`) | Not started | — | Known duplication, larger refactor, out of scope so far. |
| Sync vs. async DB engine duplication (`sync_processor.py`'s separate sync engine) | Not started | — | Noted in `consultant-knowledge-core.md` too; not addressed. |

## Critical files

- `app/services/cv_table_extractor.py` — the deterministic parser (tables + free-text sections).
- `app/services/cv_processing.py` — `extract_cv_deterministically` (the shared entry point),
  `process_cv_extraction` (profile write-back), `merge_table_extraction`.
- `app/services/sync_processor.py`, `app/services/document_service.py` — the two pipeline
  call sites.
- `app/api/documents.py` — real upload (`/upload`) and pre-fill preview (`/preview-cv`).
- `app/database.py` — `dispose_engine()`.
- `frontend/src/components/AddCrewMemberModal.tsx` — create → upload → poll flow.
- `frontend/src/components/SpecialistDossierPane.tsx`,
  `frontend/src/components/DocumentPreviewModal.tsx`,
  `frontend/src/lib/mappers.ts` — display.

## How to extend this

Adding a new deterministically-extractable field: add it to `CVTableExtraction` and
`as_extraction_payload()` in `cv_table_extractor.py`, then either let
`merge_table_extraction` pass it through (for a genuinely new key) or teach
`_update_crew_fields`/`_create_certifications`/`_create_work_history` in `cv_processing.py`
to consume it. Do not add an LLM call anywhere in this pipeline — if a field can't be
extracted deterministically, leave it `None`/absent rather than reaching for AI; AI belongs
on the read side (`consultant-knowledge-core.md`), not here.
