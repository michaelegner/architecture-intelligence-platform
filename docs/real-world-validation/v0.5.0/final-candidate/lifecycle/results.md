# Final-candidate results: I5 §10 lifecycle scenarios (v0.5.0, I5 Slice 7)

These steps ran against **candidate `aa04a150965924bd23ecf0125bcf7095a3cf72d9`** on 2026-09-25. They
used the frozen `../../lifecycle/runbook.md` as written, against the ledger as re-frozen by #256
(the corrected Quarkus X) and #257 (the L4a/L4b/L6 result labels). The AIP image was built once with
`--no-cache` (id `sha256:1bf871c401e7d1f1eb25568c036831df937b61cc3466c278bcb8111d85cbd879`) and
checked on every restart.

The raw records per target and step are in `artifacts/<target>/<step>/`:
- `workdir-digest`;
- `import.json`, including the report's `runs[]`;
- `aip.log`, with noise filtered as marked in its first line;
- the six state queries;
- the `without_x` expected and diff files, and `diffs.txt`.

**The procedure** is `artifacts/run.sh`. The runbook is unchanged since Slice 5, so the Slice 5
script was reused with only its record directory changed. Its one disclosed deviation is kept:
block 5's diffs are recorded instead of aborting.

**The checks** are `artifacts/verify.py`, which checks every row of `../../lifecycle/README.md`
against the records, with 84 checks in all. Its output is `artifacts/verify.txt`. The committed
`verify.py` differs from the as-run file only in lint and formatting: its docstring records the
as-run sha256, and its output on the same records is byte-identical. The Slice 5
failure record (`../../lifecycle/results.md`) is left unchanged.

## Verdicts: all nine steps match on both targets

| Step | Checked (both targets unless noted) | Verdict |
| --- | --- | --- |
| all | Each `workdir-digest` equals its pinned digest in `tests/unit/test_i5_lifecycle_freeze.py` (Quarkus L4b, L2, L5 and L3 as re-pinned by #256) | match |
| S0 | `committed:true`, and every source is `ACCEPTED`/`ACCEPTED_WITH_LIMITATIONS` | match |
| L1 | No `graph_revision_advanced`, 0 expirations, and **all** of State(L1) = State(S0). The dependencies `snapshot_id` also equals S0's, per the supplementary check below. | match |
| L4a | `committed:false`, `sources:{}`, State = State(L1), and no `Removed` line. **Label (#257):** `FAILED`, no source results, and `SOURCE_ROOT_UNAVAILABLE`. | match |
| L4b | The same preservation checks. **Label:** `PARTIAL`. `lifecycle-unbound-copy/openapi.yml` is `REJECTED_UNSUPPORTED` with `SERVICE_IDENTITY_UNRESOLVED`. The 4 remaining Quarkus OpenAPIs are accepted; on Airflow, the copy is the only source. | match |
| L6 | The same preservation checks. **Label:** `PARTIAL`, and the inject file is `REJECTED_CONFLICT` with `SERVICE_IDENTITY_CONFLICT`. On Quarkus, `rest-fights/architecture.yaml` is also `REJECTED_UNSUPPORTED` with `MANIFEST_CALL_SOURCE_UNRESOLVED`. | match |
| L2 | `committed:true`, and the `Removed` log line names X only. Q-SRC = State(L1) minus X's row. The owned graph = **Without_X(L1)** (Q-SVC and Q-REL diffs exit 0). X is in no Q-OWN or Q-SRC-SEM row. | match |
| R | `committed:true`. Q-SRC, Q-SRC-SEM, Q-OWN and the owned graph = State(L1). | match |
| L5 | `committed:true`, and there is no `Removed` line. X's Q-SRC and Q-SRC-SEM rows and the owned graph = State(R). Q-INV has the same `discovery_scope_id` and a new `scope_definition_digest`. The other Quarkus sources' Q-SRC rows carry the new digest; Airflow has no other source. | match |
| L3 | `committed:true`, and the `Removed` log line names X only. Q-SRC = State(L5) minus X's row. The owned graph = **Without_X(L5)** (the diffs exit 0). X is in no Q-OWN row. | match |

**What this closes:**
- **F7:** Quarkus L2, L5 and L3 now commit and remove exactly X, the corrected
  `rest-fights/architecture.yaml`, as the ledger requires. The frozen #244 inputs failed in Slice 5.
- **F1:** no step returns HTTP 500.
- **F6:** every `without_x` diff exits 0, including Airflow's empty-result steps.

## Supplementary check: the L1 `snapshot_id` (disclosed)

The ledger's L1 row also requires that "the dependencies `snapshot_id` of one declared Service equals
its S0 value". The frozen runbook never captures that read, and Slice 5 did not record it either.

`artifacts/supplementary-l1-snapshot/` closes the gap:
- **Procedure:** its `run.sh` replays runbook block 4's S0 and L1 only, per target. It uses the
  same verified image (not rebuilt; its id is checked) and adds exactly one read-only
  `GET /api/services/{id}/dependencies` after each import. `service:rest-heroes` is used for
  Quarkus, and `service:airflow-apiserver` for Airflow.
- **Quarkus:** S0 and L1 are both `aip:snapshot:v1:01346017…d5f9`.
- **Airflow:** S0 and L1 are both `aip:snapshot:v1:5fe7db49…1318`.
- **In both replays**, all six state queries at L1 equal S0, and no revision advances. The answers
  themselves are `NOT_ANSWERED` (they have no observation context), but every answer carries its
  snapshot identity, which is what the ledger compares.
