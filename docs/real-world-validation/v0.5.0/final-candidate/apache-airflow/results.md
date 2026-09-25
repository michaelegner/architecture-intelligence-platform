# Final-candidate results: `apache-airflow` (v0.5.0, I5 Slice 7)

This is the I5 §12 revalidation of the frozen dossier (#242; post-freeze corrections #243 and #246)
against **candidate `aa04a150965924bd23ecf0125bcf7095a3cf72d9`**, the #257 merge. It ran on
2026-09-25 from the frozen checkout location, with the runbook executed as written. Every raw record
is in `artifacts/`. The Slice 5 run (`../../apache-airflow/results.md`) is left unchanged.

## Run identity

| Item | Value | Record |
| --- | --- | --- |
| Candidate SHA | `aa04a150965924bd23ecf0125bcf7095a3cf72d9`. It was a clean checkout at the frozen location, checked in steps 2 and 5. | `artifacts/candidate-sha` |
| AIP image | `aip-i5-candidate:aa04a15…`, id `sha256:b8975d29964e1aa414e8e62fa0a74c655b150cf5dc4b6b2b12993d9956a40fcf`, built with `--no-cache`. The running container's `AIP_BUILD_REVISION` equals the candidate. | `artifacts/aip-image` |
| All other images | Digest-pinned in `../../apache-airflow/runtime/docker-compose.yml`, with no environment override | `artifacts/compose-images.json` |
| Dag mount and workers | The resolved Compose config mounted exactly `../../apache-airflow/runtime/dags`, and there were exactly 2 healthy `airflow-worker` containers (runbook checks) | `artifacts/run.log` |
| Observation window | `2026-09-25T13:18:45Z` to `2026-09-25T13:19:14Z` | `artifacts/window-start`, `artifacts/window-end` |
| Procedure | The frozen runbook blocks 1-10. The runbook is unchanged since Slice 5, so the Slice 5 `run.sh` was reused with only its record directory changed. It carries the same disclosed deviations, including the v0.3 readiness helpers routed through `frozen_compose`. | `artifacts/run.sh`, `artifacts/run.log` |

The fetched upstream OpenAPI is byte-identical to the frozen copy.

## Import (`artifacts/import.json`, report `aip-import-report/1`)

`committed: true`. The `airflow-v0.5-declarations` run is `COMPLETE`. `airflow-apiserver/openapi.yml`
is **`ACCEPTED_WITH_LIMITATIONS`** (232 nodes, 521 relations), with dialect `3.1.0`, Service
`service:airflow-apiserver`, and the code `SCHEMA_COMPOSITION_UNINTERPRETED`. That code is now
publicly observable, where Slice 5 needed an offline run to see it. Finding F3 remains
`DOCUMENT_UNSUPPORTED`.

## Comparison (`artifacts/actual.yaml`, `artifacts/compare.txt`)

```text
Expected supported facts:      9         (the selected PROVIDES)
Correct:                       9
Missing supported:             0
Incorrect supported:           0
Unsupported constructs:        3         (Postgres ×3)
Unresolved identities:         2         (process roles, Execution API)
Insufficient evidence:         1         (Celery messaging)
Forbidden facts proven absent: 2         (queue:default)
Forbidden facts present:       0
Critical semantic errors:      0
```

This is identical to Slice 5. No unexpected in-scope fact exists.

## Manual checks (`artifacts/manual-checks/`)

All four read-only checks were re-run with the Slice 5 queries, and all four outputs are
**byte-identical to Slice 5's**:
- only `service:airflow-apiserver` exists;
- there are no messaging entities and no infrastructure entities;
- the relations are 128 PROVIDES plus request and response schema edges, and no CALLS.

## Public surfaces (`../../public-surfaces.md`; `artifacts/public-surfaces/`)

| Check | Result |
| --- | --- |
| `tools/list` | Exactly the three frozen tools |
| Dependencies and drift of `service:airflow-apiserver` (empty-claims answers) | Service = REST = negotiated MCP (`all_equal: true`, 3 reads). One snapshot: `aip:snapshot:v1:622470bb…`, the same value as in Slice 5. |
| Evidence drill-down | Nothing to resolve: the answers carry no evidence refs, as frozen |
| Zero writes | `Q-GRAPH` sha256 before and after = `0c92730b…a947` |

## Lifecycle

The results are in `../lifecycle/results.md`. All nine steps for this target match the frozen
ledger, including the frozen L4a/L4b/L6 result labels (#257). The L2 and L3 `without_x` diffs now
exit 0 (F6 is fixed).
