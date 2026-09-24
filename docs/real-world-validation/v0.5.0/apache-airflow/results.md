# Results: `apache-airflow` (v0.5.0, I5 Slice 5)

This is the qualifying run of the frozen dossier (#242; post-freeze corrections #243 and #246)
against **candidate `174a17c5d0f8be35291032c677585291c330cc0a`**. It ran on 2026-09-24 from the
frozen checkout location, with the runbook executed as written. Every raw record is in
`artifacts/`.

## Run identity

| Item | Value | Record |
| --- | --- | --- |
| Candidate SHA | `174a17c5d0f8be35291032c677585291c330cc0a` (clean checkout at the frozen location; checked in steps 2 and 5) | `artifacts/candidate-sha` |
| AIP image | `aip-i5-candidate:174a17c…`, id `sha256:092468e77cd54318a57ba7bb4702a2da21e82481f0319187e426b83ba9133f60`, built with `--no-cache`. The running container's `AIP_BUILD_REVISION` equals the candidate. | `artifacts/aip-image` |
| All other images | Digest-pinned in `runtime/docker-compose.yml`, with no environment override. `apache/airflow:3.3.1@sha256:0c4bcc03…`, postgres, redis, neo4j and the collector all ran by their frozen digests. | `artifacts/compose-images.json` |
| Dag mount | The resolved Compose config mounted exactly `runtime/dags` (step 3 check) | `artifacts/run.log` |
| Workers | Exactly 2 `airflow-worker` containers, both healthy | `artifacts/run.log` |
| Observation window | `2026-09-24T21:50:27Z` to `2026-09-24T21:50:51Z` (closed after the drain barrier saw AIP's `/v1/traces` ingestion) | `artifacts/window-start`, `artifacts/window-end` |
| Procedure | The frozen runbook blocks 1-10, extracted verbatim into `artifacts/run.sh`. The v0.3 readiness helpers' bare `docker compose` calls are routed through `frozen_compose`, as disclosed in its header, because the frozen project name requires it. | `artifacts/run.sh`, `artifacts/run.log` |

The fetched upstream OpenAPI is byte-identical to the frozen copy.

## Import (`artifacts/import.json`)

`committed: true`. `declarations/airflow-apiserver/openapi.yml` is **`ACCEPTED_WITH_LIMITATIONS`**,
with 232 nodes and 521 relations. The limitation code is not in the response (F2). An offline
discovery run over the same declarations reports `SCHEMA_COMPOSITION_UNINTERPRETED`. The dossier did
not anticipate this limitation, so it is finding **F3**. The frozen check "the declarations source
is accepted" holds.

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

No unexpected in-scope fact exists: no CALLS into a selected operation, and no Queue fact over
`queue:default`.

## Manual checks (`artifacts/manual-checks/`, read-only Cypher)

| Check | Frozen expectation | Observed |
| --- | --- | --- |
| Import accepted | yes | `ACCEPTED_WITH_LIMITATIONS`, committed (see F3) |
| No role Services | only `service:airflow-apiserver` | only `service:airflow-apiserver` |
| No messaging entities | none | none |
| Relations | — | 128 PROVIDES (the whole imported document; 9 in scope), request and response schema edges, and no CALLS |

## Public surfaces (`../public-surfaces.md`; `artifacts/public-surfaces/`)

| Check | Result |
| --- | --- |
| `tools/list` | Exactly the three frozen tools |
| Dependencies and drift of `service:airflow-apiserver` (empty-claims answers) | Service = REST = negotiated MCP. One snapshot: `aip:snapshot:v1:622470bb…` |
| Evidence drill-down | Nothing to resolve: the answers carry no evidence refs, as frozen for an empty-claims answer |
| Zero writes | `Q-GRAPH` sha256 before and after = `f82fbc3c…e062` |

## Lifecycle

The results are in `../lifecycle/results.md`. All nine steps for this target match the frozen
ledger.
