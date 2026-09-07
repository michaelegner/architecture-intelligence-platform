# 10. The declared-vs-observed rule has one owner and one executable cross-check

Status: Proposed — see [`architecture-review-0.4.0.md`](../architecture-review-0.4.0.md#f2--the-declared-vs-observed-rule-is-stated-twice-and-never-cross-checked)

## Context

[ADR 0006](0006-declared-vs-observed.md) defines the qualification semantics
(`CONFIRMED`/`OBSERVED_ONLY`/`NOT_OBSERVED_IN_WINDOW`). Two implementations of it exist:

| | Cypher | Python |
|---|---|---|
| Evidence-window match | `app/analysis/runtime.py:28` — `_OBSERVED_EXISTS`, `_NOT_OBSERVED_EXISTS`, `_DECLARED_EXISTS` | `app/architecture_intelligence/dependency_projection.py:52` — `_matches_declared`, `_matches_observed` |
| Coverage classification | `app/analysis/runtime.py:364` `_classify_coverage` | `dependency_projection.py:82` `_classify_coverage` |
| Consumers | O1–O5, REST, the UI | the three MCP tools |

Some of that duplication is deliberate and worth keeping: `contracts.py` states that its enums
"mirror `app.analysis.runtime`'s literal values by value, not by import, so this public contract
doesn't couple to internal analysis module churn", and the coverage *rule* is genuinely shared —
`repository.py:296` calls `telemetry_coverage` rather than reimplementing it.

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
