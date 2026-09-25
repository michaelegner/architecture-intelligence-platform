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
- **Omit X.** Delete X's file. If X has an entry in `bindings/architecture-identity-bindings.yaml`,
  drop it from the copy. That file is AIP operator configuration, and without this edit it would
  reference an absent source, which is a separate phase-1 failure. An X without an entry leaves the
  copy byte-identical.
- **Unbound copy.** Add a byte-identical copy of one declaration under a new path, with no binding.
- **Inject.** Insert one root line, `x-aip-service-id: <id>`, before `info:` in the copy of the
  step's `inject` file.
- **Relocate.** Materialize the copy under the root `declarations-relocated` instead of
  `declarations`.
- **Tombstone X.** Add an I1 §6 tombstone for X. The frozen fields are in `tombstone.template.yaml`.
  The committed-state fields are bound at run time from Q-INV after L5.

**X, the source every removal scenario acts on:**

| Target | X | Why |
| --- | --- | --- |
| quarkus-super-heroes | `rest-fights/architecture.yaml` (corrected; see "Revision history") | No other declaration depends on it: it emits only CALLS, nothing refers to it, and it has no binding (its own `x-aip-service-id` resolves it). |
| apache-airflow | `airflow-apiserver/openapi.yml` | Airflow's only OpenAPI. Omitting it leaves a valid bindings document with an empty list. |

For the L4b unbound copy and the L6 injected identity:
- **quarkus-super-heroes:** the copy is of `rest-heroes/openapi.yml`. The injected id is
  `service:rest-villains`, injected into `rest-fights/openapi.yml`, where it disagrees with that
  file's binding `service:rest-fights`. This is the #244 L6 input, byte for byte.
- **apache-airflow:** the copy is of `airflow-apiserver/openapi.yml`. The injected id is
  `service:airflow-scheduler`, injected into X, where it disagrees with X's binding
  `service:airflow-apiserver`.

## Scenario sequence and expected outcomes

The steps run in this order, per target, on one clean state.
- **State(P)** means the outputs of the frozen queries (`../queries/`: Q-INV, Q-SRC, Q-SRC-SEM,
  Q-OWN, Q-SVC, Q-REL) recorded after step P. "Equals" means byte-identical outputs.
- **Owned graph** means Q-SVC (owned node ids with their sorted owners) together with Q-REL (owned
  relationship type, endpoints and key, with sorted owners).
- **Without_X(P)** is State(P)'s owned graph with X removed from every owner list, and every row
  whose owner list is then empty dropped. This is I1 §6's rule that a claim expires only when no
  other source owns it. For a removal step, it is the **exact** expected owned graph. So a
  relationship that is replaced, re-keyed or re-owned is caught even when the counts match.
  `without_x.py` computes it deterministically from the predecessor's Q-SVC and Q-REL outputs.
- **Q-SRC-SEM** holds each source's `semantic_input_digest`. That digest binds the common mapping
  context, including the identity-bindings index (I1 §5.3). When a step changes the bindings
  document, the remaining sources' values may legitimately change. The ledger asserts them only
  where the inputs and the bindings are unchanged (PR #244 review).

| Step | I5 §10 scenario | Mutation | Expected outcome | Basis |
| --- | --- | --- | --- | --- |
| S0 | baseline | none (root `declarations`) | `committed:true`. Every source is `ACCEPTED`/`ACCEPTED_WITH_LIMITATIONS`. This establishes State(S0). | I1 §6 |
| L1 | Reimport | none | No-op. Every `sources[*].graph_revision_advanced` is `false`, and all `nodes_expired`/`relations_expired` are `0`. **All** of State(L1) equals State(S0), including `inventory_revision` and Q-SRC-SEM. The dependencies `snapshot_id` of one declared Service equals its S0 value. | I1 §10 replay (identical inputs and mapping context) |
| L4a | Failed discovery | root → `declarations-missing` (absent) | `committed:false`, `sources:{}`. All of State(L4a) equals State(L1). No `Removed` log line. | I1 §6: missing roots preserve the prior inventory |
| L4b | Incomplete discovery | omit X, and add an unbound copy | `committed:false`, `sources:{}`. All of State(L4b) equals State(L1), so **X is still owned**, and no `Removed` line appears. | I1 §6: a run with a source failing validation is PARTIAL, nothing commits, and absence never removes ownership |
| L6 | Conflicting source | inject a disagreeing `x-aip-service-id` into the step's `inject` file (see above) | `committed:false`, `sources:{}`. All of State(L6) equals State(L1). | I1 §4.1 (disagreeing identities → `REJECTED_CONFLICT`) and §6 (nothing commits) |
| L2 | Complete same-scope inventory without one source | omit X | `committed:true`. The `Removed` log line names X only. Q-SRC equals State(L1) minus X's row. The owned graph equals **Without_X(L1)**. X appears in no Q-OWN row. X has no Q-SRC-SEM row; the other rows are not asserted (on Airflow the bindings change). | I1 §6 removal path 2 |
| R | (restore) | none | `committed:true`. Q-SRC, Q-SRC-SEM, Q-OWN and the owned graph all equal State(L1), so X is owned again. The inputs and bindings are identical to L1. | setup for L5/L3 |
| L5 | Changed scope | relocate, and omit X | `committed:true`. No `Removed` line. **X is not removed:** X's Q-SRC and Q-SRC-SEM rows equal State(R), and the owned graph equals State(R). Q-INV has the same `discovery_scope_id` and a new `scope_definition_digest`, and the other sources' Q-SRC rows carry that new digest. | I1 §6: changed scopes preserve claims of undiscovered sources; the scope id excludes roots |
| L3 | Explicit tombstone | relocate, omit X, and tombstone X (bound to State(L5) Q-INV) | `committed:true`. The `Removed` log line names X only. Q-SRC equals State(L5) minus X's row. The owned graph equals **Without_X(L5)**. X appears in no Q-OWN row. | I1 §6: removal authorized by an explicit tombstone matching the committed inventory |

Every non-committing step (L4a, L4b, L6) is compared with State(L1), which equals State(S0). After
L2, R and L5, each comparison is relative to the step's own predecessor. So nothing depends on
absolute AIP values that could only be learned by running AIP.

## Result labels for the non-committing steps (pre-Slice-7 amendment, 2026-09-25)

Following finding F2 (#254), the inventory status and the per-source results that I1 §10 requires
are publicly observable in the import report's `runs[]`. Before Slice 7 runs, the previously
unasserted L4a, L4b and L6 result expectations are therefore frozen here. They are derived from the
existing I1 contracts and the already-frozen scenario inputs. No observed Slice 7 result was used
to derive them. (#256 disclosed an offline discovery smoke over these inputs, which runs no import;
every label below follows from the cited rule on its own.)

The freeze is deliberately narrow. It covers the run's status and the source results that follow
directly from the induced mutation. It does not cover messages, diagnostic ordering beyond the
report's own deterministic order, counts of repeated diagnostics, or results unrelated to the
scenario. These are **in addition to** the outcomes in the table above, which are unchanged.

| Step | Target | Frozen expectation (in the step's `import.json` `runs[]` entry for the declarations source) | Basis |
| --- | --- | --- | --- |
| L4a | both | `inventory_status: FAILED`, `committed: false`, no `source_results`, and the run's `diagnostics` include `SOURCE_ROOT_UNAVAILABLE` | I1 §6: a missing root is a failed enumeration and preserves the prior inventory |
| L4b | quarkus-super-heroes | `inventory_status: PARTIAL`, `committed: false`. The added `lifecycle-unbound-copy/openapi.yml` is `REJECTED_UNSUPPORTED` with `SERVICE_IDENTITY_UNRESOLVED`. The four remaining OpenAPI sources are `ACCEPTED` or `ACCEPTED_WITH_LIMITATIONS`. | I1 §4.1: an unresolved Service identity emits no owner-scoped entities; §6: one rejected source makes the run PARTIAL, and nothing commits |
| L4b | apache-airflow | `inventory_status: PARTIAL`, `committed: false`. The added `lifecycle-unbound-copy/openapi.yml` is `REJECTED_UNSUPPORTED` with `SERVICE_IDENTITY_UNRESOLVED`. It is the only source, because X is Airflow's only OpenAPI. | same |
| L6 | apache-airflow | `inventory_status: PARTIAL`, `committed: false`. `airflow-apiserver/openapi.yml` is `REJECTED_CONFLICT` with `SERVICE_IDENTITY_CONFLICT`. | I1 §4.1: an extension that disagrees with a binding is a conflict, and no source wins |
| L6 | quarkus-super-heroes | `inventory_status: PARTIAL`, `committed: false`. `rest-fights/openapi.yml` is `REJECTED_CONFLICT` with `SERVICE_IDENTITY_CONFLICT`. Because that source no longer establishes `service:rest-fights`, `rest-fights/architecture.yaml` is also `REJECTED_UNSUPPORTED` with `MANIFEST_CALL_SOURCE_UNRESOLVED`. | I1 §4.1 as above; the manifest rule (#255, `docs/ingestion.md`): CALLS may reference a caller Service, but the manifest never mints it, so with the conflicting OpenAPI rejected the caller is absent from the phase-0 model |

Each expectation is checked on the public import report only (`runs[].inventory_status`,
`runs[].committed`, `runs[].source_results[].locator`, `.result` and `.diagnostics[].code`, and
`runs[].diagnostics[].code`).

## Verification method (owner decision, 2026-09-24)

Each step's outcome is checked through three things only:
1. **Public reads.** The `POST /api/import` response (`committed`, per-source `result`,
   `graph_revision_advanced`, and the written and expired counts), and the dependencies
   `snapshot_id` in L1. Since #254 this includes the import report's `runs[]` entry, which carries
   the result labels frozen for L4a, L4b and L6.
2. **The AIP log.** The `Removed import_id=… sources=…` line (`app/api/import_api.py`).
3. **Frozen read-only Cypher** (`../queries/`), run with `cypher-shell --access-mode read` in the
   lifecycle Neo4j:
   - **Q-INV** reads `CurrentInventory`;
   - **Q-SRC** reads the `SourceState` identity and scope fields;
   - **Q-SRC-SEM** reads each `SourceState`'s semantic input digest;
   - **Q-OWN** gives owned node and relation counts per owner;
   - **Q-SVC** gives owned node ids with their sorted owners;
   - **Q-REL** gives owned relationship identities (type, endpoints, key) with their sorted
     owners.

   These read AIP's internal state, the same way the comparator's capture reads the graph. They are
   verification, never ground truth.

## Pre-identified observability limitation (for Slice 5 to record as a finding)

*Superseded for Slice 7: since #254 the labels below are observable, and L4a, L4b and L6 carry the
frozen result expectations in "Result labels for the non-committing steps". This section is kept as
the Slice 4 record.*

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

## Revision history

**2026-09-25: I5 §6 correction of the Quarkus X (finding F7, #253).** Slice 5 showed that the #244
choice of X = `rest-fights/openapi.yml` rested on a false premise, "no other declaration depends on
it". The rest-fights manifest emits CALLS from `service:rest-fights`, and only that OpenAPI declares
the Service. So L2, L5 and L3 were inputs the contract rejects, while this ledger expected them to
commit. The correction changes the **input design only**; every expected outcome above is the same
I1 §6 / §10 rule, applied to the corrected X:
- X is now `rest-fights/architecture.yaml`, which no declaration depends on.
- L6's disagreeing identity names its own `inject` file. Its input is unchanged (same digest), and so
  is Airflow's whole scenario (every digest is unchanged).
- `mutate.py` drops X's binding only when X has one.
- The re-pinned digests are Quarkus L4b, L2, L5 and L3 (`tests/unit/test_i5_lifecycle_freeze.py`).
  A new test runs AIP's discovery over every step of both targets and requires each committing
  step's input to be commit-eligible and each non-committing step's not to be, so an input like
  F7's is caught before any run.

The failed Slice 5 comparison stays on record unchanged (`results.md`, `artifacts/`): a correction
cannot replace a failed comparison. The owner's merge of this correction is the re-freeze, and
Slice 7 reruns the Quarkus lifecycle on the corrected input.

**Same date: `without_x.py` (finding F6, #253).** When every row is removed, it now prints nothing,
exactly as `cypher-shell` prints an empty result, instead of a lone header line. No expected outcome
changes.

The observability limitation above predates finding F2. Since #254, the import report exposes each
step's result labels and diagnostics. This correction adds no expectations for them; the amendment
below does.

**2026-09-25: pre-Slice-7 result labels (owner decision).** The L4a, L4b and L6 result expectations
were frozen before Slice 7 ran, from the I1 contracts and the frozen inputs (see "Result labels for
the non-committing steps"). No scenario input and no earlier expectation changed, and the Slice 5
evidence is untouched.
