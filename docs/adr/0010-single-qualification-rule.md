# 10. The declared-vs-observed rule has one owner and one executable cross-check

Status: Accepted — implemented v0.4.1 I1 (`docs/specifications/0.4.1/i1-qualification-consistency.md`); see [`architecture-review-0.4.0.md`](../architecture-review-0.4.0.md#f2--the-declared-vs-observed-rule-is-stated-twice-and-never-cross-checked)

## Context

[ADR 0006](0006-declared-vs-observed.md) defines the qualification semantics
(`CONFIRMED`/`OBSERVED_ONLY`/`NOT_OBSERVED_IN_WINDOW`). Two implementations of it exist:

| | Cypher | Python |
|---|---|---|
| Evidence-window match | `app/analysis/runtime.py:28` — `_OBSERVED_EXISTS`, `_NOT_OBSERVED_EXISTS`, `_DECLARED_EXISTS` | `app/architecture_intelligence/dependency_projection.py:52` — `_matches_declared`, `_matches_observed` |
| Coverage classification | `app/analysis/runtime.py:364` `_classify_coverage` | `dependency_projection.py:82` `_classify_coverage` |
| Consumers | O1–O5, REST, the UI | `get_service_dependencies`, `get_architecture_drift` |

Some of that duplication is deliberate and worth keeping: `contracts.py` states that its enums
"mirror `app.analysis.runtime`'s literal values by value, not by import, so this public contract
doesn't couple to internal analysis module churn", and the coverage *rule* is genuinely shared —
`repository.py:296` calls `telemetry_coverage` rather than reimplementing it.

`get_evidence` is out of scope for this ADR: it is snapshot-bound provenance resolution for
already-identified references, with no observation context and no qualified claims of its own.

What is missing is any executable statement that the two paths agree. Both are covered by frozen
evaluation (`evaluation/projector.py` for the Cypher path, `evaluation/architecture_answers/` for the
Python path), but against independently authored scenario sets: a divergence between them fails
neither suite. Two surfaces answering the same question differently is precisely the failure mode
this project's evaluation culture exists to prevent.

## Decision

Keep both implementations. Add the guarantee that is missing:

1. **One named owner for the evidence-matching predicate.** The rule "an evidence id counts as
   observed for (environment, window)" is defined in one place and referenced from both
   implementations — as a shared Cypher fragment and predicate, not two independently maintained
   spellings of the same sentence.
2. **A differential test.** Over shared graph fixtures, for every relation in the fixture, the Cypher
   path and the projection path must produce the same qualification and the same coverage
   classification. It runs in `tests/integration`, against a real Neo4j, in both directions
   (declared-only, observed-only, both, neither).
3. **The window-default asymmetry is documented, not removed.** REST answers against an implicit
   clock-relative window (`default_since`, and an open-ended `$until`); MCP requires an explicit
   `observation_context`. That difference is legitimate, but it must be stated in both contracts, so
   two surfaces giving different answers for the same fact is explainable rather than alarming.

A deliberate divergence, if one is ever wanted, is recorded as its own ADR and encoded as an expected
difference in the differential test — never left implicit.

## Consequences

- A new integration test that can fail for a real reason: any future change to window semantics,
  evidence typing, or coverage classification made on one side only.
- The shared predicate becomes a contract of its own; changing it changes both surfaces at once,
  which is the intent.
- The REST/UI layer still reaches Neo4j directly (`app/api/services.py`, `queues.py`, `messages.py`,
  `evidence.py`, `ui.py` embed Cypher) while the MCP layer goes through a repository. This ADR does
  not converge them — it only removes the risk that they disagree. Convergence, if ever wanted,
  belongs to `v0.9`'s REST contract stabilization.
- Cost is one test plus a small refactor, not a redesign; the public contracts are unchanged.

## Implementation record (v0.4.1 I1)

Implemented in three PRs: I1.1 added the shared owner, `app/qualification/declared_observed.py`
(pure, dependency-free — no Neo4j/FastAPI/MCP import); I1.2 migrated both
`app/analysis/runtime.py` and `app/architecture_intelligence/dependency_projection.py` to consume
it, removing their independent evidence-matching/coverage-classification code; I1.3 added the
differential test (`tests/integration/test_qualification_consistency.py`), covering the Q1–Q15
boundary matrix from the I1 spec against a hand-built, `PROVIDES`-free fixture.

The differential test found a real pre-existing bug, not merely duplicated code: `app/analysis/
runtime.py`'s `declared_only_relations` (O4) computed its coverage annotation via an internal
`telemetry_coverage` call that omitted the `until` bound entirely, so a service's coverage always
used an open-ended upper bound regardless of what window the caller actually requested — an
observed relation from *after* the requested window silently counted as coverage. The Python/MCP
path's equivalent computation (`repository.read_service_dependency_rows`) already bounded coverage
by `until` correctly. Per this project's standing rule for exactly this situation, the divergent
case was recorded, the correct side was identified from the two paths' behavior rather than assumed,
and only the incorrect side (`declared_only_relations`) was changed — with its own regression test
(`tests/integration/test_runtime_analysis.py::test_o4_coverage_respects_an_explicit_until_bound`,
confirmed to fail without the fix before being kept as a permanent regression).

`coverage_row_exists=False` (the shared kernel's "no coverage row for this subject" branch) remains
supported and unit-tested but is not reachable by either production caller today — both
`app.analysis.runtime.telemetry_coverage` and `app.architecture_intelligence.repository.
read_service_dependency_rows` always synthesize exactly one coverage row per requested `service_id`.
Widening `telemetry_coverage`/O5 to validate service existence (which would make this branch live)
was deliberately left out of I1's scope — a real behavior change to a query several other callers
depend on, not required by the Q1–Q15 matrix or this ADR's decision.
