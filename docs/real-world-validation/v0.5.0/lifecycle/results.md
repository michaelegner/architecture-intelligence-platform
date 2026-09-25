# Results: I5 §10 Lifecycle Scenarios (v0.5.0, I5 Slice 5)

These steps ran against **candidate `174a17c5d0f8be35291032c677585291c330cc0a`** on 2026-09-24,
using `runbook.md` as written. The AIP image was built once with `--no-cache` (id
`sha256:653255971a00a0a8943751d686df43194054f09ddbad70b320ce5de96b31dd6f`) and checked on every
restart. The raw records per target and step are in `artifacts/<target>/<step>/`:
- `workdir-digest`;
- `import.json`;
- `aip.log`, with noise filtered as marked in its first line;
- the six state queries;
- the `without_x` expected, diff and `diffs.txt` files.

The procedure is `artifacts/run.sh`, generated from the runbook blocks. It has one disclosed
deviation: block 5's diffs are recorded instead of aborting, so a mismatch becomes a finding and
the other target still runs.

Every step's `workdir-digest` equals its pinned digest in `tests/unit/test_i5_lifecycle_freeze.py`.

## Verdicts

"= State(P)" means all six state queries are byte-identical to step P's.

### apache-airflow: all nine steps match the frozen ledger

| Step | Observed | Verdict |
| --- | --- | --- |
| S0 | `committed:true`, the OpenAPI source `ACCEPTED_WITH_LIMITATIONS` (F3) | match |
| L1 | `graph_revision_advanced:false`, 0 expirations; = State(S0) | match |
| L4a | `committed:false`, `sources:{}`; = State(L1) | match |
| L4b | `committed:false`, `sources:{}`; = State(L1), so X is still owned | match |
| L6 | `committed:false`, `sources:{}`; = State(L1) | match |
| L2 | `committed:true`. The `Removed` log line names X only. Q-SRC and the owned graph are empty, and X owned all of them, so this is exactly State(L1) minus X and `Without_X(L1)`. | match (see F6) |
| R | = State(L1) | match |
| L5 | `committed:true`, no `Removed` line. X's Q-SRC and Q-SRC-SEM rows and the owned graph all = State(R). Q-INV has the same `discovery_scope_id` and a new `scope_definition_digest`. | match |
| L3 | `committed:true`. The `Removed` log line names X only. Q-SRC and the owned graph are empty, which is `Without_X(L5)`. | match (see F6) |

**F6.** The L2 and L3 `without_x` diffs report exit 1 **only** because `without_x.py` keeps the
header line when every row is dropped. `cypher-shell` prints nothing at all for an empty result.
The row sets are identical: both are empty.

### quarkus-super-heroes: six steps match; the three X-omission steps are not qualifiable (F7, F1)

| Step | Observed | Verdict |
| --- | --- | --- |
| S0 | `committed:true`, 5 sources `ACCEPTED` | match |
| L1 | `graph_revision_advanced:false`, 0 expirations; = State(S0) | match |
| L4a | `committed:false`, `sources:{}`; = State(L1) | match |
| L4b | `committed:false`, `sources:{}`; = State(L1), so X is still owned | match |
| L6 | `committed:false`, `sources:{}`; = State(L1) | match |
| L2 | **`POST /api/import` → HTTP 500.** `CanonicalValidationError: Relation CALLS has unknown source service:rest-fights` (×7) is raised by `validate_canonical_model` in `import_discovery_run` (`artifacts/quarkus-super-heroes/L2/aip.log`). Nothing committed, and the state stayed = State(L1). | **mismatch (F7, F1)** |
| R | = State(L1) | match |
| L5 | HTTP 500, same cause | **mismatch (F7, F1)** |
| L3 | HTTP 500, same cause | **mismatch (F7, F1)** |

**The cause.** Omitting X (`rest-fights/openapi.yml`) leaves no remaining source that mints the
`service:rest-fights` entity. The rest-fights architecture manifest still resolves its caller from
its own `x-aip-service-id` and emits 7 CALLS from that Service. The merged model fails canonical
validation, and the exception escapes as an unhandled 500.

The frozen ledger chose X on the assumption that "no other declaration depends on it". That
assumption was wrong: the manifest depends on X's Service entity. This is a qualification-input
defect (**F7**). Under the current contract, the manifest deliberately emits only `CALLS` and does
not mint its caller Service, so a rejected run would be correct for this input. The frozen
expectation needs an I5 §6 correction and re-freeze. Separately, AIP crashes on the input instead
of rejecting it (**F1**). So the real-declaration
omission, changed-scope and tombstone outcomes for Quarkus are **not qualified at this candidate**.
The same three semantics are qualified on Airflow's real declarations, and by the I1 regression
tests.

The non-committing Quarkus steps behaved correctly. Where the API gave no reason, the step's own
`aip.log` shows the 500 traceback.
