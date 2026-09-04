# I1 Completion Record — v0.4.0 Service Contract and Dependency Vertical Slice

One concise record per spec §26 ("I1 SHALL produce only ... one concise I1 completion record");
this is not a release-level dossier. See
[`i1-service-contract-and-dependency-vertical-slice.md`](i1-service-contract-and-dependency-vertical-slice.md)
for the full spec this record qualifies against.

## Run identity

- **Candidate commit:** `8031f640daac3067ba9e709b19464d8246959fe2` (branch
  `v0.4.0/i1.4-qualification`, PR #74).
- **Verified CI, on this exact SHA** (via `gh api repos/.../commits/8031f640.../check-runs`, not
  just the PR's current-head view, per PR review round 2's finding that an earlier candidate had no
  check-runs of its own attached): `lint + test` ×2, `CodeQL`, `analyze (actions)`,
  `analyze (python)`, `dependency security scan (pip-audit, spec §29)` ×2 — all `completed`/`success`.
- **Candidate identity is explicitly pinned, not ambient.** PR review round 2 found that deriving
  `producer.build_revision` from `git rev-parse HEAD` independently in the runner and the comparator
  left the "qualified" SHA undocumented and free to drift. `evaluation/architecture_answers/
  candidate.py`'s `resolve_candidate_sha()` is now called exactly once per run
  (`evaluation/architecture_answers/runner.py::run_suite`) and threaded through the `Producer`
  injected into every live service call, the comparator's `producer.build_revision` check, and the
  recorded result artifact - never re-derived independently. This record's evidence was produced by
  running `uv run python -m evaluation answers --candidate-sha
  8031f640daac3067ba9e709b19464d8246959fe2` explicitly (not the ambient-HEAD default), so the
  artifact is self-describing: its own `"candidate_sha"` field is the same value cited here, not a
  claim that only exists in this record's prose.
- **Environment / window used throughout local qualification:** `test`,
  `2026-08-26T00:00:00Z`–`2026-08-27T00:00:00Z`
- **Result artifact:** `evaluation/architecture_answers/results/i1-evaluation-result.json` (sha256
  `06a3e6d0b38069cd0975b974fc52721aac2426e7d47c96d6aadb6e8cc945be80`), recording
  `"candidate_sha": "8031f640daac3067ba9e709b19464d8246959fe2"` internally — cross-check this file
  directly rather than trusting this record's transcription of it. Produced from, and committed
  after, the candidate commit above (the evidence commit necessarily follows the code it evaluates;
  it changes no code the candidate's own CI needed to re-validate).

## Review history on this candidate

Two review rounds on PR #74 preceded this record, both addressed on the candidate commit above:

- **Round 1** (4 blocking): full-envelope comparison was missing `schema_version`/`producer`/`tool`;
  a targeted single-scenario run could overwrite the committed 8-scenario artifact; the concurrent-
  write integration test only bumped the revision singleton without mutating a real canonical field;
  producer identity used a placeholder (`"0" * 40`) build revision.
- **Round 2** (2 blocking, 1 non-blocking): the placeholder fix still derived `build_revision` from
  an unpinned, independently-called `git rev-parse HEAD` rather than one explicit, threaded run
  identity (fixed as described above); the completion record itself was stale/unbound to a verified
  candidate (this rewrite); the loader accepted non-string `description`/`environment`/`snapshot_id`
  values, relying on later Pydantic errors instead of a precise `ScenarioValidationError`.

## Regression suite

| Suite | Result |
|---|---|
| `uv run pytest tests/unit` | 688 passed |
| `uv run pytest tests/integration` | 191 passed |
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run python -m evaluation run` (relation-facts, unchanged) | 10/10 PASS |
| `uv run python -m evaluation answers --candidate-sha 8031f640...` (architecture-answers, I1.4) | 8/8 PASS, `semantic_outputs_identical: true` |

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
the live comparator) — not generated from a run of AIP itself. `producer.build_revision` is the one
field deliberately *not* frozen per-scenario (see "Candidate identity" above) — it's checked against
the run's own explicit `candidate_sha` instead. Outcome branches already exhaustively covered by
unit tests (`PARTIAL`-via-mixed-resolution, `OBSERVATION_CONTEXT_REQUIRED`,
`SNAPSHOT_NOT_AVAILABLE`, `RESULT_LIMIT_EXCEEDED`) are not duplicated as separate scenarios here.

## Definition of Done (spec §28)

### Boundary and Contract
- [x] `ArchitectureIntelligenceService` is the only new semantic entry point (`app/architecture_intelligence/service.py`).
- [x] Only `get_service_dependencies` is implemented.
- [x] The versioned schema freezes every required envelope and dependency field (I1.1,
      `schemas/architecture_intelligence/v0.4/architecture-answer.schema.json`).
- [x] Every answer identifies the AIP version and immutable build revision — `producer.name`/
      `.version` are frozen literals; `.build_revision` is the run's explicitly pinned candidate SHA
      (`evaluation/architecture_answers/candidate.py`), never a placeholder, per this iteration's
      review findings. Production build-provenance wiring for the real deployed service (as opposed
      to the evaluator) remains I4's job (spec §10).
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
      service path, mutating a real canonical field (not just the excluded revision singleton) in
      the same injected transaction as the bump
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
      suite's own two-full-pass proof — `semantic_outputs_identical: true` in the committed artifact).
- [x] Existing tests and deterministic architecture evaluation remain green — full regression above;
      the v0.2.0 relation-facts suite is untouched in behavior and still 10/10.
- [x] CI, lint, CodeQL and dependency checks pass on the exact I1 candidate — verified via the
      GitHub API directly against candidate commit `8031f640daac3067ba9e709b19464d8246959fe2` (see
      "Run identity" above), not inferred from the PR's current-head view.

## Exit Statement (spec §29)

```text
GO — At 8031f640daac3067ba9e709b19464d8246959fe2, a direct ArchitectureIntelligenceService call
returns a deterministic, evidence-qualified, snapshot-bound answer for one service's bounded direct
dependencies, with destination separated from delivery and zero graph writes.
```
