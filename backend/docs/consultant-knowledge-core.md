# Consultant Knowledge Core

Living architecture doc for how consultant/crew data flows through this backend, and the
plan to give any future AI feature (search, summaries, agent tool-calling) one shared
way to read that data instead of each feature reinventing its own path. Update this file
in the same commit as the code change it describes — it should never go stale.

This doc covers the *read* side (search, summaries). For the *write* side — how a CV
actually becomes structured data in the first place — see
[`cv-ingestion-pipeline.md`](./cv-ingestion-pipeline.md).

## Why this exists

Ingestion (uploading a document and turning it into structured data) was already a single,
well-defined pipeline. Retrieval was not: three independent, disconnected mechanisms had
grown up around it, and the natural next step — "let an AI agent answer questions about a
consultant" — would have meant a fourth one-off integration on top. This doc, and the
`app/domain/` + `app/services/consultant_knowledge.py` modules it describes, exist to stop
that pattern before it compounds.

### The fragmentation that existed before this work

- **`crew_query.py`** — a working GraphQL `queryCrew` natural-language query engine (Ollama
  intent classification → direct SQLAlchemy filters → Ollama-generated summary). The only
  retrieval path the frontend actually used.
- **Meilisearch** — indexing was half-wired: `deleteCrewMember` synced the index, but
  `createCrewMember`/`updateCrewMember` never did, so the index silently went stale after
  every edit.
- **Qdrant** — a fully coded vector-search client and a fully written Celery embedding task
  that was never dispatched from anywhere. Dead code with a live entry point.
- **Duplicated vocabulary** — `cv_processing.py::CV_CERT_MAPPINGS` and
  `crew_query.py::CERT_NAME_MAP`/`CERTIFICATION_FAMILIES` were two independently maintained
  certification-alias dictionaries that had already diverged (e.g. "huet" and "harbour
  porpoise" were only recognized on the search side, not the CV-ingestion side — meaning a
  consultant's CV-mentioned HUET training never became a Certification row, even though
  searching for "HUET" worked).

## The retrieval-consolidation decision

Three retrieval mechanisms exist. Rather than force one winner, each was judged on its own
evidence:

- **Meilisearch: fix, don't remove.** The fix was two missing method calls mirroring the
  existing delete-sync pattern. It buys real typo-tolerant/autocomplete UX that plain SQL
  `ILIKE` can't match cheaply.
- **Direct-SQL + intent-LLM (`crew_query.py`): keep as the backbone**, refactored to sit
  *behind* the shared service rather than rewritten — it's the one retrieval path proven in
  production.
- **Qdrant: keep the code, don't wire it into the default path yet.** It's the only
  mechanism that could do semantic recall over free text (education, work-history prose, CV
  text) — something structured filters and keyword search can't do — but nothing today
  validates it's worth the added write-path cost (embedding latency, a third copy of the
  truth to keep in sync, an Ollama call that already swallows failures in
  `qdrant.py::_generate_embedding`). It's gated behind `settings.ENABLE_SEMANTIC_SEARCH`
  (default `False`) until a real validation pass (Phase 3) earns it a default-on switch.
  Decommissioning stays cheap as long as nothing else takes a hard dependency on it.

## The core

### `app/domain/` — shared vocabulary

- **`certifications.py`** — `CERT_ALIASES` (the merged union of the two former dicts, no
  conflicting values existed between them), `CERT_FAMILIES`, `normalize_cert_name()`,
  `cert_family_for()`. Both `cv_processing.py` (CV ingestion → Certification rows) and
  `crew_query.py` (search-query parsing) import from here — one dictionary, not two.
- **`fields.py`** — canonical value lists for status fields (`AVAILABILITY_STATUS_VALUES`,
  `CERT_STATUS_VALUES`, `CERT_VERIFICATION_STATUS_VALUES`, `DOCUMENT_CLASSIFICATIONS`).
  Introduced as available shared vocabulary for future call sites (Phase 2/3, or any new
  feature); not yet force-substituted into the LLM prompt bodies in `extraction.py` /
  `crew_query.py` / `reports.py`, since those prompts are tuned free text and rewriting them
  without evidence risked changing model behavior for no measured benefit. If a future
  change touches those prompts anyway, build them from this module rather than another
  independent literal list.

### `app/services/consultant_knowledge.py` — the one door (Phase 2, not yet built)

The single access-layer service any future feature should call instead of reaching into
Postgres/Meilisearch/Qdrant/Ollama directly:

```python
class ConsultantKnowledgeService:
    async def get_profile(self, crew_id: str, *, db_session) -> ConsultantProfile: ...
    async def search(self, query: str, *, db_session, mode="auto") -> SearchResult: ...
    async def summarize(self, crew_id: str, *, db_session) -> str: ...
    async def similar_documents(self, document_id: str, *, limit=10) -> list[SimilarDoc]: ...
    async def index_crew_member(self, crew: CrewMember) -> None: ...
```

`search(mode="structured"/"auto")` will delegate to the existing, unmodified
`CrewQueryService.process_query`. `similar_documents`/`search(mode="semantic")` stay stubbed
until Phase 3 wires Qdrant in behind the feature flag. **How to extend this**: a new
AI-agent feature should call this service, not add a fourth retrieval path.

## Phase status

| Phase | Status | Date | Notes |
|---|---|---|---|
| 1 — shared vocabulary + Meilisearch sync fix | Shipped | 2026-09-02 | `app/domain/certifications.py` and `app/domain/fields.py` added; `cv_processing.py`/`crew_query.py` now import `CERT_ALIASES` instead of keeping local dicts (verified: this widens CV-ingestion cert auto-creation to the aliases that were previously search-only, e.g. HUET, FOET, Harbour Porpoise Detection — a real behavior improvement, covered by a new regression test). `createCrewMember`/`updateCrewMember` now call `meilisearch_client.index_crew_member(...)`, mirroring the existing delete-sync pattern. `OLLAMA_EMBEDDING_MODEL` and `ENABLE_SEMANTIC_SEARCH` settings added to `app/config.py` (the latter unused until Phase 3). `qdrant.py` reads the embedding model from settings instead of a hardcoded literal. Tests: `tests/test_meilisearch_sync.py` (new), `tests/test_cv_extraction.py::test_cv_processing_and_crew_query_resolve_aliases_identically` (new). |
| 2 — `ConsultantKnowledgeService` | Shipped | 2026-09-02 | Added `app/services/consultant_knowledge.py`: `get_profile` (crew + certifications + work_history + linked documents in one call), `search` (mode `structured`/`auto` delegates unchanged to `CrewQueryService.process_query`; `keyword` delegates to Meilisearch; `semantic` raises `NotImplementedError` until Phase 3), `summarize` (reuses `CrewQueryService._handle_summarize`), `index_crew_member`/`remove_from_index` (now the only callers of `meilisearch_client` from the write path). `schema.py`'s `queryCrew` resolver and the three crew mutations now call this service instead of `crew_query_service`/`meilisearch_client` directly; `crew_query.py`'s internal logic is untouched. Verified against the live stack (not just mocked tests): `queryCrew` returns correct real-Ollama/real-Postgres results through the new service, `createCrewMember` now actually lands a document in Meilisearch (confirmed via direct Meilisearch API check), and `deleteCrewMember` removes it (confirmed 404 after). Tests: `tests/test_consultant_knowledge.py` (new, 5 tests). |
| 3 — validate & decide on semantic search | Wired, checkpoint recommends staying off | 2026-09-02 | `process_document_extraction`/`process_dropbox_document` now dispatch `index_document_embeddings` via a new `_maybe_queue_embeddings()` helper, gated behind `settings.ENABLE_SEMANTIC_SEARCH` (default `False`) — confirmed by test to be a true no-op when off. `ConsultantKnowledgeService.search(mode="semantic")` and `similar_documents()` are fully implemented against `qdrant_service.search_similar`, also gated behind the same flag; `similar_documents` excludes the source document from its own results. The document-text-to-embed logic was de-duplicated into `qdrant_service.document_indexable_text()`, shared by the Celery task and the new service (previously only existed inline in the task). **Validation run against the live stack, bypassing the flag directly** (not by turning it on in the deployment): (1) embedding generation currently **fails outright** — the `all-minilm` model configured via `OLLAMA_EMBEDDING_MODEL` is not pulled into this environment's Ollama instance (`ollama list` shows qwen2.5:14b, qwen2.5:7b/3b, llama3.2-vision, llava, moondream — no `all-minilm`); (2) of the 7 `Document` rows in this environment, only 1 (Helena Lindqvist's CV) has real `extracted_data`/`extracted_text` — the other 6 are seed/demo crew records with `extraction_status="extracted"` but no actual extracted content, so there isn't enough real data here yet for a meaningful semantic-vs-keyword comparison even once embeddings work. No side effects were left from this check (indexing failed before writing anything; the `documents` Qdrant collection doesn't exist). **Recommendation: leave `ENABLE_SEMANTIC_SEARCH=False`.** Before revisiting: pull `all-minilm` (or pick and configure a different embedding model) into Ollama, and get more real documents through extraction so there's enough data to compare against Meilisearch/SQL recall meaningfully. Tests: `tests/test_documents.py::test_embedding_indexing_dispatches_only_when_semantic_search_is_enabled` (new), `tests/test_consultant_knowledge.py` extended with semantic-mode on/off and `similar_documents` self-exclusion tests. Separately noted (pre-existing, unrelated to this work): the `celery_gpu_worker` **and** `ollama` containers both request an NVIDIA CDI device (`/dev/nvidia0`) and fail to start when it's absent — corrected from an earlier note in this doc that claimed Ollama falls back to CPU gracefully; live testing on 2026-09-02 showed it does not, at least under podman with CDI on this host: `ollama` failed hard on every start/create attempt while the GPU was unavailable, and once its container got torn down mid-deploy, `backend`/`frontend` (both transitively `depends_on: ollama: condition: service_healthy`) went down too until the GPU was available again. Not a code fix — host/scheduler dependent. |
| 4 — AI summary shown on profile open | Shipped | 2026-09-02 | See `backend/docs/cv-ingestion-pipeline.md` for the full design. Surfaces `ConsultantKnowledgeService.summarize()` automatically when a consultant's profile opens (previously only reachable by typing "Summarize X" into search), cached per crew member (`cache.py::SUMMARY_TTL`, invalidated on `updateCrewMember` and CV re-processing). Found and fixed two real, previously-undiscovered bugs along the way: (1) `summarize_response`'s prompt template used `{crew_data}` but `_generate_response` only ever passed a `results` kwarg — every summarize call hit a `KeyError`, silently caught, and fell back to returning the raw input JSON instead of a generated summary; (2) `OllamaClient.extract()` hardcodes `format: "json"` on every call, which constrains the model's decoding regardless of prompt wording — a narrative-prose prompt still got valid JSON back, just prose wrapped in `{"profile": "..."}`. Fixed via a new `json_format`/`prose` opt-out (`ollama.py::extract(json_format=...)`, `crew_query.py::_generate_response(prose=...)`) used only by the summarize path — the other three response types (`search_response`/`compliance_response`/`matching_response`) are untouched, since they weren't verified broken and forcing a global change would have been unjustified risk. Also fixed the redundant double DB lookup in the original `summarize()` (fetch by ID just to get `full_name`, then fuzzy `ILIKE` re-lookup by that name) by extracting `crew_query.py::generate_crew_summary(crew)`, shared by both the by-ID path and the NL fuzzy-name path. Live-verified: real Ollama call ~4-8s, cache hit ~0.03s (127x), cache correctly invalidated on profile edit (verified via timing + content diff), rendered correctly in the browser with no JSON/field-name leakage. Tests: `tests/test_crew_summary.py` (new, 5 tests, including a direct regression test for the template `KeyError`). |
| 5 — reviewed publication boundary | Shipped | 2026-09-05 | Deterministic CV extraction writes only to `CVReview.proposed_data`. SQL, Meilisearch, natural search, summaries, and compliance accept only `publication_status="approved"`; approval applies administrator-corrected facts before indexing. Rejected, failed, processing, and awaiting-review records remain excluded. Offline rules cover the first-release search examples; Qdrant remains disabled and postponed. See `cv-ingestion-pipeline.md`. |

## Explicitly out of scope

- Converting `document_ref` string fields on `Certification`/`WorkHistory`/`Project` into
  real FKs to `Document.id`.
- Unifying `sync_processor.py`'s separate synchronous SQLAlchemy engine with the app's async
  engine (`app/database.py`).
- Any new agent-facing endpoint/feature built on top of the core — this work is
  foundation-only.
