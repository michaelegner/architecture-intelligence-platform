# I5 §10 Lifecycle Scenarios on Real Declarations (frozen, Slice 4)

This ledger freezes the exact input mutation, expected outcome and verification method for every
I5 §10 scenario. It covers both targets, before any scenario runs (I5 §10, §14 Slice 4). The owner's
merge of this PR is the freeze.

- **Inputs.** Each step runs on a scratch copy of a frozen dossier's declarations (Quarkus #240,
  Airflow #242). `mutate.py` builds the copy from `scenarios/<target>.yaml`. The upstream pin and
  the dossiers are never modified.
- **Procedure.** `runbook.md`.
- **Expected outcomes.** Each comes from I1 §6 (inventory and removal authority) and §10 (results
  and replay), applied to the stated mutation. No AIP output was run or inspected to author them.

## Mutations

Only the following edits are permitted, and each is applied to the copy:
- **Omit X.** Delete X's file, and drop X's entry from the copy of `identity-bindings.yaml`. That
  file is AIP operator configuration. Without this edit, it would reference an absent source, which
  is a separate phase-1 failure.
- **Unbound copy.** Add a byte-identical copy of one declaration under a new path, with no binding.
- **Inject.** Insert one root line, `x-aip-service-id: <id>`, before `info:` in X's copy.
- **Relocate.** Materialize the copy under the root `declarations-relocated` instead of
  `declarations`.
- **Tombstone X.** Add an I1 §6 tombstone for X. The frozen fields are in `tombstone.template.yaml`.
  The committed-state fields are bound at run time from Q-INV after L5.

**X, the source every removal scenario acts on:**

| Target | X | Why |
| --- | --- | --- |
| quarkus-super-heroes | `rest-fights/openapi.yml` | No other declaration depends on it. The rest-fights manifest calls only heroes, villains and narration operations. |
| apache-airflow | `airflow-apiserver/openapi.yml` | Airflow's only OpenAPI. Omitting it leaves a valid bindings document with an empty list. |

For the L4b unbound copy and the L6 injected identity:
- **quarkus-super-heroes:** the copy is of `rest-heroes/openapi.yml`, and the injected id is
  `service:rest-villains`, which disagrees with X's binding `service:rest-fights`.
- **apache-airflow:** the copy is of `airflow-apiserver/openapi.yml`, and the injected id is
  `service:airflow-scheduler`, which disagrees with X's binding `service:airflow-apiserver`.

## Scenario sequence and expected outcomes

The steps run in this order, per target, on one clean state. "State(P)" means the Q-INV, Q-SRC,
Q-OWN and Q-SVC outputs recorded after step P. "Unchanged" means byte-identical query outputs.

| Step | I5 §10 scenario | Mutation | Expected outcome | Basis |
| --- | --- | --- | --- | --- |
| S0 | baseline | none (root `declarations`) | `committed:true`. Every source is `ACCEPTED`/`ACCEPTED_WITH_LIMITATIONS`. This establishes State(S0). | I1 §6 |
| L1 | Reimport | none | No-op. Every `sources[*].graph_revision_advanced` is `false`, and all `nodes_expired`/`relations_expired` are `0`. State(L1) equals State(S0), including `inventory_revision`. The dependencies `snapshot_id` of one declared Service equals its S0 value. | I1 §10 replay |
| L4a | Failed discovery | root → `declarations-missing` (absent) | `committed:false`, `sources:{}`. State(L4a) equals State(L1). No `Removed` log line. | I1 §6: missing roots preserve the prior inventory |
| L4b | Incomplete discovery | omit X, and add an unbound copy | `committed:false`, `sources:{}`. State(L4b) equals State(L1), so **X is still owned**, and no `Removed` line appears. | I1 §6: a run with a source failing validation is PARTIAL, nothing commits, and absence never removes ownership |
| L6 | Conflicting source | inject a disagreeing `x-aip-service-id` into X | `committed:false`, `sources:{}`. State(L6) equals State(L1). | I1 §4.1 (disagreeing identities → `REJECTED_CONFLICT`) and §6 (nothing commits) |
| L2 | Complete same-scope inventory without one source | omit X | `committed:true`. The `Removed` log line names X only. Q-SRC is State(L1) minus X's row. In Q-OWN and Q-SVC, X appears nowhere, and every other source's owned counts and ids are unchanged. | I1 §6 removal path 2 |
| R | (restore) | none | `committed:true`. Q-SRC and Q-OWN equal State(L1), so X is owned again. | setup for L5/L3 |
| L5 | Changed scope | relocate, and omit X | `committed:true`. No `Removed` line. X's Q-SRC row and its Q-OWN counts are unchanged from State(R), so **X is not removed**. Q-INV has the same `discovery_scope_id` and a new `scope_definition_digest`. | I1 §6: changed scopes preserve claims of undiscovered sources; the scope id excludes roots |
| L3 | Explicit tombstone | relocate, omit X, and tombstone X (bound to State(L5) Q-INV) | `committed:true`. The `Removed` log line names X only. Q-SRC is State(L5) minus X. X appears in no Q-OWN or Q-SVC owner list, and every other source is unchanged from State(L5). | I1 §6: removal authorized by an explicit tombstone matching the committed inventory |

Every non-committing step (L4a, L4b, L6) is compared with State(L1), which equals State(S0). After
L2, R and L5, the comparisons stay relative to each step's own predecessor. So nothing depends on
absolute AIP values that could only be learned by running AIP.

## Verification method (owner decision, 2026-09-24)

Each step's outcome is checked through three things only:
1. **Public reads.** The `POST /api/import` response (`committed`, per-source `result`,
   `graph_revision_advanced`, and the written and expired counts), and the dependencies
   `snapshot_id` in L1.
2. **The AIP log.** The `Removed import_id=… sources=…` line (`app/api/import_api.py`).
3. **Frozen read-only Cypher** (`../queries/`), run with `cypher-shell --access-mode read` in the
   lifecycle Neo4j:
   - **Q-INV** reads `CurrentInventory`;
   - **Q-SRC** reads `SourceState`;
   - **Q-OWN** gives owned node and relation counts per owner;
   - **Q-SVC** gives owned ids with their owners.

   These read AIP's internal state, the same way the comparator's capture reads the graph. They are
   verification, never ground truth.

## Pre-identified observability limitation (for Slice 5 to record as a finding)

I1 §10 requires the import report to include inventory status, conflicts, planned expirations,
tombstones and final commit status. `POST /api/import` returns only `import_id`, `committed` and
per-source stats. Those stats are `{}` for a run that does not commit, and the diagnostics are
never persisted. As a result:
- **L4a, L4b and L6 look identical through every surface.** The result labels (FAILED, PARTIAL,
  `REJECTED_CONFLICT`) and their diagnostics are **not observable**. What is verified is the part
  I5 §10 requires: nothing commits, and prior state is preserved.
- **Removals appear only in the log**, and ownership only in the internal graph.

Slice 5 SHALL record this as a finding with exactly one disposition (I5 §11). It is recorded here
before any run so that it cannot be mistaken for a surprise result.

## Relationship to existing I1 tests

The same semantics are covered by existing I1 regression tests, which are reused as regression
evidence only (I5 §9):
- `tests/integration/test_importer.py`: idempotent reimport; source-removed-when-no-longer-discovered;
  scope-change preservation; tombstone-authorized removal after a scope mismatch; stale-tombstone
  denial;
- `tests/unit/test_orchestrator.py`: a missing root is FAILED; a malformed document fails the whole
  run; one rejected source blocks the commit;
- `tests/unit/test_sources_tombstones.py`, `test_sources_removal_authority.py` and
  `test_sources_replay.py`.

These are fixtures, and they never stand in for the real-declaration runs above.
