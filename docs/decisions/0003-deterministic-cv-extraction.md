# ADR 0003: CV Extraction Is Deterministic, Not LLM-Based

- Status: accepted
- Date: 2026-09-02
- Owners: backend maintainers
- Supersedes: the original LLM-based extraction path for `classification == "cv"`
  documents in `sync_processor.py` and `document_service.py`

## Context

CV extraction originally sent every uploaded CV through Ollama (`qwen2.5:14b`)
for structured field extraction, the same as every other document
classification (certificates, identity, project, compliance, performance).
That call runs on the Celery `gpu` queue.

Two facts changed the calculus:

1. All CVs in this system come from **one fixed template**. A deterministic
   PDF-table/text parser (`app/services/cv_table_extractor.py`) already
   existed and, per its own tests against the real template, recovered *more*
   training rows with exact dates than the LLM did, with zero invented
   fields.
2. The `celery_gpu_worker`/`ollama` containers depend on an NVIDIA GPU device
   (`/dev/nvidia0`) that is not reliably present on this host — confirmed
   during this work: `ollama` failed to start on every attempt while the
   device was unavailable, which in turn blocked `backend` and `frontend`
   (both `depends_on: ollama: condition: service_healthy`). A batch of CV
   uploads meant a batch of blocked or GPU-contending LLM calls on a critical
   path that didn't need to be there.

## Decision

CV extraction (`classification == "cv"`) never calls an LLM. A deterministic
parser pulls every field the fixed template makes available:

- `full_name`, `nationality`, `country_of_residence`, `date_of_birth`,
  `gender`, `flying_point`, `education`, `languages` — from the PERSONAL
  INFORMATION table.
- `expertise`, `geographical_experience`, `systems`,
  `training_qualifications` (+ structured per-row dates), `certifications`
  (short-token match), `work_history` — from their respective tables.
- `professional_summary` and `skills` — the two genuinely free-text sections
  (PROFESSIONAL SUMMARY paragraph, "Skills & Competencies" bullet list) —
  captured **verbatim, uninterpreted**. No attempt is made to force-structure
  or summarize this text at ingestion time.

If a CV doesn't fit the template — wrong file type, or the parser finds
neither personal info nor work history — it is **not** sent to the LLM as a
fallback. It is flagged for manual review (`extraction_status = "needs_review"`)
via a deliberately low confidence signal, reusing the existing
`determine_review_status` mechanism rather than adding a parallel one.

AI's role for CV-derived data moves entirely to *read* time: search,
summaries, and future agent queries operate on the structured rows and the
stored free text (see `backend/docs/consultant-knowledge-core.md`,
`ConsultantKnowledgeService`). Non-CV classifications are unaffected — they
still go through Ollama; this decision does not touch them.

## Alternatives considered

- **Keep the LLM as a fallback for non-template CVs**: the deterministic
  parser as primary, Ollama only for what it can't handle. Rejected for now
  because it reintroduces the exact GPU-availability fragility this decision
  removes, for a case (non-PDF or malformed CV) that's rare given the
  single-template constraint. If that assumption stops holding, revisit with
  a new ADR rather than silently reintroducing the dependency.
- **Force-structure the free-text sections too** (via AI or a hand-maintained
  keyword dictionary): rejected — a dictionary only ever catches known terms
  and drifts from reality, and running AI at ingestion time for two
  paragraphs reintroduces the same GPU dependency for marginal gain over
  storing the text as-is and letting read-time AI interpret it.
- **Keep the LLM call and just fix the GPU scheduling**: doesn't address that
  the LLM was already measurably less accurate than the deterministic parser
  on this template, independent of GPU availability.

## Consequences

- CV processing dropped from tens of seconds (LLM round trip) to under one
  second, and no longer depends on GPU/Ollama availability at all.
- Accuracy improved on the fields the template exposes as tables (more
  training rows recovered, exact dates, no invented values) — proven by
  existing tests against the real fixture PDF before this decision was made.
- `email`/`phone`/`address` are not recoverable from CVs at all under either
  approach — the template never carries them — so this decision has no effect
  on that pre-existing gap; they're populated by manual entry.
- A CV that doesn't match the template gets no structured data and sits in
  `needs_review` until a human handles it, rather than a lower-confidence
  AI-guessed result. This is an explicit accuracy-over-coverage trade-off.
- If the CV template population changes (e.g. a second recruiting agency with
  a different layout), this decision should be revisited — likely via the
  "keep LLM as fallback" alternative above, formalized as a new ADR.

## Migration and rollback

- Forward: `CVProcessingService.extract_cv_deterministically`
  (`app/services/cv_processing.py`) replaced the `extraction_service.extract_document_sync`
  call in both `sync_processor.py` and `document_service.py`'s CV branches,
  and in the pre-crew-creation preview path (`POST /api/documents/preview-cv`).
  No schema change; `Document.extracted_data`/`extracted_text` keep the same
  shape, now populated deterministically. `CrewMember.professional_summary`
  is a new column (migration `012_add_professional_summary`).
- Rollback: revert the three call sites to call `extraction_service.extract_document_sync`/`extract_document`
  directly, as before. No data migration required — deterministically-written
  rows are ordinary `CrewMember`/`Certification`/`WorkHistory` data.

## Validation

- `pytest backend/tests/test_cv_extraction.py backend/tests/test_documents.py -q`
  — includes a test asserting `extract_document_sync`/`extract_document` are
  never called for a `classification="cv"` PDF, and a test asserting a
  non-template CV routes to `needs_review`.
- Live-verified against the real fixture CV through the actual upload API:
  `extraction_method: "deterministic"` in the persisted `extracted_data`,
  zero Ollama HTTP calls in the container logs, sub-second processing time,
  three sequential uploads to the same long-lived Celery worker all
  succeeded (see `backend/docs/consultant-knowledge-core.md` Phase 1 status
  for the related event-loop fix this also depended on).
