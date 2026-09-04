# I1 Completion Record — v0.4.0 Service Contract and Dependency Vertical Slice

One concise record per spec §26 ("I1 SHALL produce only ... one concise I1 completion record");
this is not a release-level dossier. See
[`i1-service-contract-and-dependency-vertical-slice.md`](i1-service-contract-and-dependency-vertical-slice.md)
for the full spec this record qualifies against.

## Run identity

- **Candidate commit:** `4297e0b457b86f9e982ed5852058f28ca8ea6a34` (branch
  `v0.4.0/i1.4-qualification`) — supersedes `817800e6522c0806ba3b7f373c16bd33b5d6aa00`, this PR's
  first pushed commit, which failed CI's own `lint + test` job: the frozen snapshot literals had
  been derived from an absolute, checkout-location-specific path
  (`Path(__file__).resolve()`-built scenario-path constants leaking into `Evidence.source_file`,
  spec §18's allowlist) and were not reproducible on the GitHub Actions runner's own checkout path.
  `4297e0b` fixes the path construction to be relative to the repo root everywhere and regenerates
  the affected literals — see that commit's message for the full root-cause account.
- **Environment / window used throughout local qualification:** `test`,
  `2026-08-26T00:00:00Z`–`2026-08-27T00:00:00Z`
- **Result artifact:** `evaluation/architecture_answers/results/i1-evaluation-result.json`
  (sha256 `2dbe271321bfbb2f15a800ea439c32012447269096a2a34c21d1d6fa07654965`), produced by and
  committed alongside the candidate commit above

## Regression suite

| Suite | Result |
|---|---|
| `uv run pytest tests/unit` | 683 passed |
| `uv run pytest tests/integration` | 187 passed |
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run python -m evaluation run` (relation-facts, unchanged) | 10/10 PASS |
| `uv run python -m evaluation answers` (architecture-answers, I1.4) | 8/8 PASS, `semantic_outputs_identical: true` |

The architecture-answers suite's own `run_output_sha256` pair (two complete
reset→ingest→telemetry→reconcile→call-service passes over all 8 scenarios) was identical across
every local invocation during this iteration, including separate container instances — the
committed result artifact reflects one such run.

## Deterministic-evaluation scenarios (spec §23 required semantic anchors)

| Scenario | Proves |
|---|---|
| `sync-confirmed` | declared `CALLS` + matching observed → `CONFIRMED`, resolved via `PROVIDES` |
| `async-confirmed` | declared `SENDS`/`RECEIVES_FROM` + matching observed → `CONFIRMED`, resolved via queue |
| `sync-not-observed-in-window` | declared only, no observation anywhere → `NOT_OBSERVED_IN_WINDOW` + `NONE` coverage |
| `observed-only-undeclared` | observed evidence with no declared relation → `OBSERVED_ONLY` |
| `unresolved-queue-destination` | sender with no evidenced consumer → `DIRECT_TARGET_FALLBACK` + `UNRESOLVED_IDENTITY`, outcome `PARTIAL` |
| `multiple-delivery-paths` | one destination reached via both `CALLS` and `SENDS`/`RECEIVES_FROM` → two distinct claims survive |
| `unknown-service` | well-formed but absent `service_id` → `NOT_ANSWERED`/`UNKNOWN_ENTITY` |
| `empty-service` | known service, zero outgoing dependencies → `ANSWERED`, empty claims |

Ground truth is frozen literal data (`expected_answer.json`, a full `ArchitectureAnswer` instance),
independently derived via `evaluation/architecture_answers/reference/` (a separate reimplementation
of the claim/context/snapshot/evidence-id formulas, transcribed from spec text, never imported by
the live comparator) — not generated from a run of AIP itself. Outcome branches already exhaustively
covered by unit tests (`PARTIAL`-via-mixed-resolution, `OBSERVATION_CONTEXT_REQUIRED`,
`SNAPSHOT_NOT_AVAILABLE`, `RESULT_LIMIT_EXCEEDED`) are not duplicated as separate scenarios here.

## Definition of Done (spec §28)

### Boundary and Contract
- [x] `ArchitectureIntelligenceService` is the only new semantic entry point (`app/architecture_intelligence/service.py`).
- [x] Only `get_service_dependencies` is implemented.
- [x] The versioned schema freezes every required envelope and dependency field (I1.1,
      `schemas/architecture_intelligence/v0.4/architecture-answer.schema.json`).
- [x] Every answer identifies the AIP version and immutable build revision (`Producer`, frozen literal
      pending I4's real build-provenance wiring per spec §10).
- [x] No graph-specific internal type crosses the service boundary — `read_service_dependency_rows`
      returns plain dicts; the service never exposes a session, transaction, or Cypher expression.

### Context and Snapshot
- [x] Observation context is explicit, bounded, normalized and deterministically identified (I1.2,
      `observation_context.py`).
- [x] Snapshot identity is a deterministic content hash of the allowlisted queryable state (I1.2,
      `repository.canonical_snapshot_state`/`snapshot_fingerprint`).
- [x] The internal revision fence is updated by every current graph writer (I1.2 `revision_fence.py`,
      exercised by `test_revision_fence.py`).
- [x] Concurrent writes cannot produce an accepted mixed-state answer — proven through the real
      service path this iteration
      (`test_a_concurrent_write_during_the_stable_read_forces_a_retry_through_the_real_service_path`).
- [x] Matching explicit snapshots repeat; stale snapshots fail without fallback
      (`test_matching_explicit_snapshot_repeats_the_answer`,
      `test_stale_explicit_snapshot_is_refused_without_fallback`).
- [x] No snapshot history or persisted `ObservationContext` was added — both remain computed, never
      stored, entities.

### Dependency Semantics
- [x] Only direct outgoing dependencies are returned (`dependency_projection.py` projects exactly
      the subject's own `CALLS`/`SENDS` relations).
- [x] Destination and delivery are independent fields (`DependencyClaim.object` vs. `.delivery`).
- [x] Sync and async service destinations are resolved only from canonical evidenced relations
      (`_resolve_sync_destination`/`_resolve_async_destinations`, never by parsing an id).
- [x] Unresolved operations/queues are retained without guessing (`DIRECT_TARGET_FALLBACK` +
      `UNRESOLVED_IDENTITY`, `unresolved-queue-destination` scenario).
- [x] Multiple operations, queues, consumers and delivery kinds are preserved deterministically
      (`multiple-delivery-paths` scenario; claim sort key `(object.id, delivery.kind, delivery.via.id,
      claim_id)`).
- [x] No derived dependency relation is materialized — `DIRECT_DEPENDENCY` is a result-claim
      predicate only, never written to the graph.

### Qualification and Evidence
- [x] Every claim uses exactly one accepted qualification (contract-enforced enum).
- [x] `NOT_OBSERVED_IN_WINDOW` remains distinct from absence (`sync-not-observed-in-window` scenario).
- [x] Qualification evidence and destination-resolution evidence are separate (`evidence_refs` vs.
      `resolution_evidence_refs`, both compared exactly in the I1.4 comparator).
- [x] Every referenced evidence id exists in the accepted snapshot — proven at the unit level (I1.3's
      dangling-evidence-id fix, PR #73) and independently at the integration level this iteration
      (`broken_evidence_refs` real-Neo4j check in every architecture-answers scenario run).
- [x] Missing evidence produces a limitation or safe refusal, never a fabricated claim
      (`INSUFFICIENT_EVIDENCE`, unit-tested in I1.3).

### Determinism and Quality
- [x] Result bounds fail explicitly and never silently truncate (`RESULT_LIMIT_EXCEEDED`, unit-tested
      in I1.3, `test_result_limit_exceeded_is_reported_without_truncation`).
- [x] Independently authored positive, empty, partial, unresolved, insufficient, unknown and stale
      scenarios pass (8 architecture-answers scenarios plus I1.2/I1.3 unit coverage for the branches
      not re-proven there).
- [x] Two consecutive canonical answers for fixed inputs are byte-identical
      (`test_two_consecutive_calls_are_canonically_byte_identical`, plus the architecture-answers
      suite's own two-full-pass proof).
- [x] Existing tests and deterministic architecture evaluation remain green — full regression above;
      the v0.2.0 relation-facts suite is untouched in behavior and still 10/10.
- [x] CI, lint, CodeQL and dependency checks pass on the exact I1 candidate — confirmed on PR #74 at
      candidate commit `4297e0b457b86f9e982ed5852058f28ca8ea6a34` (`lint + test`, `CodeQL`,
      `analyze (actions)`, `analyze (python)`, `dependency security scan (pip-audit, spec §29)` —
      all pass; verified at PR head `a70cd5d808fa610eefc532217cbda12806487492`, a documentation-only
      descendant of the candidate that changes no code CI needed to re-validate).

## Exit Statement (spec §29)

```text
GO — At 4297e0b457b86f9e982ed5852058f28ca8ea6a34, a direct ArchitectureIntelligenceService call
returns a deterministic, evidence-qualified, snapshot-bound answer for one service's bounded direct
dependencies, with destination separated from delivery and zero graph writes.
```
