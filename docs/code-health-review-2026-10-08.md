# Code health and design review — 2026-10-08

**Reviewed:** `main` @ `7638afd17a01380592a590a8817fa6225766a357` (2026-10-08, after v0.6.2 I1c-1, #469)
**Method:** read-only review of `app/` (164 files, about 33k lines) and its tooling: ruff complexity,
function lengths, typing escape hatches, layering and Neo4j access, REST response typing. Unlike
[`architecture-review-0.4.0.md`](architecture-review-0.4.0.md), this is a code-health review.

**Verdict:** healthy. Nothing is structurally broken. Most findings are the normal weight of fast
feature growth, not design mistakes.

## Already good practice

- CI enforces pyright (standard mode, `include = ["app"]`), ruff with bugbear, bandit, timezone and
  blind-except rules, deptry, and 8 import-linter contracts. The contracts keep the layering: the
  qualification kernel has no dependencies, delivery adapters (REST, MCP, wiring) sit on top, the LLM
  layer stays out of the deterministic core, and ingestion never imports the graph layer.
- Few escape hatches: 22 `pyright: ignore` and 5 `noqa` in about 33k lines.
- Low complexity: only 11 functions exceed cyclomatic complexity 12.
- Domain contracts are frozen Pydantic models with validators and frozen-schema parity tests.
- Tests: about 74.6k lines (about 2.2x the app), including real-transport and frozen-schema guard
  tests.

## Main findings, ranked

### 1. `POST /v1/traces` blocks the event loop — DEFERRED

- `app/api/telemetry.py:17` `post_traces` is `async def` and calls the synchronous
  `ingest_trace_spans`, which does six Neo4j reads plus writes on the event loop. While a batch is
  ingested, every REST, MCP and UI request stalls.
- This is deliberate: the `app/telemetry/correlation_buffer.py:51` docstring relies on the
  serialization it gives.
- With live mode (#469) the Collector exports continuously, so the stalls now recur.
- Fix when picked up: run the ingest in a worker thread behind an explicit single-flight lock or a
  single-worker executor, so ingests stay serialized. A plain `def` route is not enough, because
  FastAPI's thread pool would then ingest concurrently. The database side already tolerates
  concurrent ingestion units (revision-singleton lock, `docs/specifications/0.6.0/i2-decision-record.md`),
  and the correlation buffer is thread-safe.
- Acceptance: a query is answered during a deliberately slow ingest; a test proves serialization by
  failing when the lock is removed; the `correlation_buffer.py` docstring is updated; the full unit
  and integration suites pass.

**Outcome (owner, 2026-10-08): defer.** Not part of v0.6.2. The v0.6.2 spec §2 allows exactly one
product change (I0). The default live traffic is about 30 messaging spans per 600 s cycle, so the
stalls are probably small for the demo. No latency was measured. List it as a known limitation in
the v0.6.2 release notes and schedule it for v0.7 or a v0.6.x patch, using the full spec-driven
workflow because it touches the runtime evidence write path.

### 2. `ArchitectureIntelligenceService` is turning into a hub

- `app/architecture_intelligence/service.py` is 1009 lines.
- The constructor keeps gaining optional parameters "so every pre-existing caller keeps working".
- `_project_direct_dependencies` (`:269`, 165 lines) is switched by `include_deployment` and
  `include_broker` flags.
- `get_service_dependencies` (`:459`, 146 lines) combines the dependency, deployment and broker
  projections inline.
- Each new sibling projection adds another flag and another merge block.

Dedicated design work when the next projection lands. The `fingerprint_holder` part is already on the
earlier `app/` refactoring work's list of touch-only items.

### 3. Very long functions that mix several jobs

30 of 984 functions are over 100 lines. The worst:

| Function | Lines | Note |
|---|---|---|
| `app/telemetry/adapter.py:271` `correlate_http_call_observations` | 326 | known touch-only item |
| `app/ingestion/kubernetes_adapter.py:54` `map` | 268 | complexity 15 |
| `app/graph/importer.py:134` `_import_source_tx` | 245 | 14 parameters, 5 of them optional "mode" parameters |
| `app/ingestion/openapi_adapter.py:53` `map` | 241 | complexity 25, the highest in `app/` |
| `app/graph/importer.py:453` `_import_all_sources_tx` | 217 | complexity 17 |
| `app/architecture_intelligence/deployment_projection.py:887` `resolve_path_c` | 177 | known touch-only item |
| `app/architecture_intelligence/deployment_projection.py:324` `resolve_path_b` | 173 | known touch-only item |

Cheap safeguard: enable ruff `C901` with a ceiling at today's maximum and lower it over time.

### 4. Database access is spread across layers with no boundary

- Cypher runs in 18 modules outside `app/graph/`: `telemetry/*_resolver.py`, `analysis/*`,
  `intent/entity_resolver.py`, `ai/question_service.py`, and three separate
  `architecture_intelligence/*repository.py` modules.
- Read layers return plain `dict` / `list[dict]` (63 functions), so projections reach into rows by
  string key and pyright can't check them.
- There are two read paths side by side: the older `graph/read_models` + `analysis/*` path and the
  newer typed service path.

An import-linter contract confining Cypher to repository modules would match this repo's habit of
enforcing rules in CI, but it can only land after those call sites move. Dedicated work.

### 5. Some REST routes have no response schema

10 JSON routes in `app/api/services.py`, `queues.py`, `messages.py`, `evidence.py`, `ui_context.py`
and `openapi_export.py` return bare `dict` / `list[dict]`, so the exported OpenAPI has no schema for
them. That's inconsistent with the schema-backed MCP and architecture-intelligence routes. Fix route
by route when touched.

## Smaller items (fix when touching the file)

- `app/architecture_intelligence/contracts.py:448`, `:676` and `:728` contain three copies of the
  sorted-and-deduplicated validator, while `locality_contracts.py:211` already has a generic
  `_check_sorted_unique`. Watch the error text if a frozen test pins it.
- About 328 lines in `app/` narrate release history, for example "v0.5.0 I3 slice 5b: … so every
  pre-existing caller keeps working". This goes stale; trim it when in a file. The roughly 1,160
  `spec §` references are deliberate traceability and should stay.
- Don't split `contracts.py` (1222 lines) or `locality_contracts.py` (1481) for size alone. Frozen
  Pydantic contract modules backed by schema tests are a reasonable place for that much code.

## Already known, not repeated here

These were identified in earlier, unpublished working reviews.

- Test-suite cleanup proposal (2026-09-29, on hold by owner decision): helpers repeated across files
  (`clean_database` in 23 files), the 3,148-line `tests/integration/test_importer.py`, weak
  assertions.
- Owner-decision items left over from the earlier `app/` refactoring work: YAML loader duplicate
  keys, Cypher lexer differences, silent span eviction in the correlation buffer, HTTP-vs-messaging
  identity minting, and others.

## Suggested order

1. The `/v1/traces` fix, after v0.6.2 (deferred, see finding 1).
2. The C901 ratchet: cheap and stops new long functions.
3. Findings 2 and 4 as design work when the next projection or source type lands.
4. Everything else when you're already editing that file, per the continuous-refactoring policy in
   `CLAUDE.md`.
