# Rehearsal expected answers (REHEARSAL - NOT I5 evidence)

**Label (runbook §8):** (b) independently authored expected answers, for the I2.6a **rehearsal**
recording in this directory. Authored with `harness/locality-capture/replay/expected.py` (stdlib
only, the frozen v2 key rule of I1 v2 contract §2) from `identities.env` and the accepted
Operation ids of the import report, **before** any AIP evaluation of the recording.

Query: caller `service:orders`, environment `locality-capture`, whole UTC day `2026-09-30`.

| Symbol | Value |
|---|---|
| Cluster UID | `3c9b3e0f-1239-404a-8a45-c1195a7918f5` |
| P1 (`orders`) | `orders-66686679bb-cvd46` / `1cda6fde-9aa4-409d-baff-8b0604b0f63b` |
| P2 (`orders-canary`) | `orders-canary-67975b66fd-xmv8q` / `d005b4f6-5377-410d-aad7-15233aed7bac` |
| O1 (accepted) | `operation:service:pricing:GET:/prices` |
| O2 (accepted) | `operation:service:legacy-pricing:GET:/prices` |
| v2 (P1 -> O1) | `evidence:otel:calls-scoped:v2:3d17904494047d4ce70edeb55f7083481071ed5bd26c9a3f19dbb4f332cc04e0` |
| v2 (P2 -> O2) | `evidence:otel:calls-scoped:v2:df6b26b5e885eb7a425d1799ed36a2afdbc6c1c269d67a651ee2876d89e28807` |

| # | Selected capture | Candidate | Expected |
|---|---|---|---|
| E1 | C1 | v2 (P1 -> O1) | `APPLICABLE` at Deployment `orders` (namespace `aip-locality`, cluster above); `CONFIRMED` (declared orders -> pricing plus scoped observed) |
| E2 | C1 | v2 (P2 -> O2) | `APPLICABLE` at Deployment `orders-canary`; `OBSERVED_ONLY` (no declaration for legacy-pricing) |
| E3 | C1 | all | Exactly two assertions, (orders, O1) and (orders-canary, O2), with two distinct Workload UIDs; no (orders, O2) or (orders-canary, O1); target runtime scope `UNKNOWN`; no candidate limitation |
| E4 | C2 | v2 (P1 -> O1) | Retained and still P1's; candidate limitation `UNRESOLVED` [`LOCALITY_CAPTURE_MISSING_POD`]; no assertion for Deployment `orders` |
| E5 | C2 | v2 (P2 -> O2) | Still `APPLICABLE` at Deployment `orders-canary`, `OBSERVED_ONLY` (C2 is captured on `2026-09-30`) |
| E6 | both | v1 | One v1 bucket per (orders, Operation, day); its observation count equals the flag-off replay's and the matching v2 record's count |
| E7 | both | snapshot | The C1-selected and C2-selected `snapshot_id`s differ; both states carry `scoped_observed_calls_v2` |

