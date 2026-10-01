# Controlled two-Workload capture: RUN RECORD (REHEARSAL - NOT I5 evidence)

**Label (I1 capture runbook §8/§9):** this is the v0.6.0 **I2.6a rehearsal** of the runbook §4
procedure. It is **not** the I5 controlled reference, not a production observation and not a
pilot. The I5 acquisition remains `NOT_RUN`. Everything in this directory was produced by
`harness/locality-capture/rehearse.sh` (acquisition) and `harness/locality-capture/replay/run-replay.sh`
(clean offline replay), from the harness committed with it.

- **Executor:** the I2 implementer (Claude Code), with the acquisition owner (Michael Egner) reviewing (runbook §1).
- **Run day:** 2026-09-30, entirely between 14:31Z and 14:42Z. That is inside the runbook's
  01:00Z-22:00Z margin, on one UTC day.
- **Pre-evaluation commit:** `expected.md` was committed and pushed in `33dba17` **before** any AIP
  evaluation of this recording (runbook §7).

## Pins (runbook §4 step 0; `run-log.txt`)

| Item | Value |
|---|---|
| kind | `v0.33.0 go1.26.7 linux/amd64` |
| kubectl client | `v1.36.1` |
| docker server | `29.8.0` |
| Node image | `kindest/node:v1.31.2@sha256:18fbefc20a7113353c7b75b5c869d7145a6abd6269154825872dc59c1329912e` (API server `v1.31.2`) |
| Recording Collector | `otel/opentelemetry-collector-contrib:0.161.0@sha256:fd328de2552466ad78385e1b1289c3f2402b1c45f265b252aab1955b42845ac1` |
| Replay Collector | `otel/opentelemetry-collector:0.161.0@sha256:b6d2b9a85b1029d05b5ad913150c1f014eed4ae99be81a1813ca5ade4a191913` (the demo's) |
| Neo4j (replay) | `neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93` |
| App image | `aip-locality-harness:rehearsal`, id `sha256:987eb5b64c96ce773af75d73e03fa6ead806a6963551b824873592d099dff0d3`, built from `harness/locality-capture/app` (base `python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b`; OTel SDK 1.45.0, instrumentations 0.66b0, hash-pinned) |
| AIP (replay) | Built from this repository at the harness commit |

## Identities (`identities.env`)

| Item | Value |
|---|---|
| `CLUSTER_UID` (`kubectl get namespace kube-system -o jsonpath='{.metadata.uid}'`) | `3c9b3e0f-1239-404a-8a45-c1195a7918f5` |
| P1, Deployment `orders` (W1) | `orders-66686679bb-cvd46`, Pod UID `1cda6fde-9aa4-409d-baff-8b0604b0f63b`, Deployment UID `9b85fa34-e343-4bb6-ad52-3c55381408d7` |
| P2, Deployment `orders-canary` (W2) | `orders-canary-67975b66fd-xmv8q`, Pod UID `d005b4f6-5377-410d-aad7-15233aed7bac`, Deployment UID `87a6fe2b-eb3b-424f-affb-6028679fd607` |
| Traffic window | 2026-09-30T14:32:39Z - 2026-09-30T14:41:33Z |
| C1 (overlap) | `capturedAt` 2026-09-30T14:38:11Z, revision `rehearsal-c1-2026-09-30T14-38-11Z` |
| Promotion | Deployment `orders` deleted; P1 gone at 14:38:41Z; 2 more minutes of canary traffic |
| C2 (post-promotion) | `capturedAt` 2026-09-30T14:40:42Z, revision `rehearsal-c2-2026-09-30T14-40-42Z` |
| Recording | `otlp.jsonl`, 52 lines, sha256 `2683f37fe77fb886993db23e5837287b277c37b290371c21288b06387ea4d4c6` |
| Accepted Operation ids (`import-report-c1.json`, `accepted-operations.txt`) | O1 `operation:service:pricing:GET:/prices`, O2 `operation:service:legacy-pricing:GET:/prices` |

**Temporal atomicity:** each capture is two sequential `kubectl get` calls (the Namespace, then the
namespaced kinds), kept verbatim as `c1/ns.yaml`/`c1/rest.yaml` (and `c2/`). It is not atomic, as
in the v0.5 precedent. `resources.yaml` is exactly those two documents joined by a `---` separator.
Authority is self-declared (`aip-locality-rehearsal-self-declared-authority`).

## Stop-condition checklist (runbook §4; checked in `rehearse.sh`)

| Condition | Result |
|---|---|
| P1 and P2 both `Running` at C1 | Pass |
| Neither Pod replaced during the traffic window (UID unchanged) | Pass (P1 through C1, P2 through C2) |
| Every CLIENT Resource carries `k8s.pod.uid`, `k8s.cluster.uid` and the environment | Pass (`analysis.json`: 0 violations over 867 CLIENT spans) |
| Every CLIENT `k8s.cluster.uid` equals `CLUSTER_UID` | Pass |
| Captures and traffic on one UTC day | Pass (2026-09-30) |
| No recorded artifact edited | Pass (the recording, C1/C2 and the raw `kubectl` outputs are as written) |

## Rehearsal gates (runbook §9)

| Gate | Result | Evidence |
|---|---|---|
| 1. Authentic CLIENT identity | **Pass** | `analysis.json`: every CLIENT span's Resource carries P1's or P2's API Pod UID (Downward API), `k8s.cluster.uid` byte-equal to `CLUSTER_UID` and `deployment.environment.name=locality-capture`. The 2 distinct CLIENT Resources are listed there, and no `k8s.*` value came from the Collector. |
| 2. Pinned wire path | **Pass** | In all three clean replays (`evaluation/wire-*.json`), each of the 52 lines was accepted by the replay Collector (HTTP 200) and AIP answered exactly 52 `POST /v1/traces` with HTTP 200: nothing merged, split or retried. The persisted v2 records' `k8s_pod_name`, `k8s_deployment_name`, `k8s_namespace_name`, Pod UID, cluster UID and environment equal the recorded Resource values (`evaluation/state-on-c1.json` against `analysis.json`). C1 and C2 validate as `KubernetesSourceSnapshot` envelopes with matching `files[]` digests (both import `committed`). Raw `otlp.jsonl` is never decoded by AIP's protobuf decoder. |
| 3. Owner chain | **Pass** | The unmodified owner-chain module resolves P1 to Deployment `orders` (`9b85fa34-…`) and P2 to Deployment `orders-canary` (`87a6fe2b-…`): two distinct Deployment UIDs (`evaluation/state-on-c1.json` `inventories`). |
| 4. CLIENT identity retained in every arrival order | **Pass, over two recordings** | This recording: 820 in-batch and 47 SERVER-first pairs (plus 5 SERVER-only traces, which mint nothing). The v2 counts, 359 (P1 -> O1) and 508 (P2 -> O2), equal the recorded CLIENT span counts exactly. The CLIENT-first order comes from attempt 1's unmodified recording (`attempt1/`: 644 CLIENT-first, 224 SERVER-first, 0 in-batch); `tests/integration/test_locality_rehearsal_replay.py` replays it and requires the same equality. |
| 5. Stop conditions checked and recorded | **Pass** | The checklist above. |

## Expected answers (`expected.md`, committed in `33dba17` before evaluation) and results

| # | Result | Evidence |
|---|---|---|
| E1 | **Match:** (P1 -> O1) `APPLICABLE` at Deployment `orders`, `CONFIRMED`; v2 id `…3d179044…` as expected | `evaluation/state-on-c1.json` |
| E2 | **Match:** (P2 -> O2) `APPLICABLE` at Deployment `orders-canary`, `OBSERVED_ONLY`; v2 id `…df6b26b5…` as expected | same |
| E3 | **Match:** exactly those two assertions, two distinct Workload UIDs, target runtime scope `UNKNOWN`, no candidate limitation | same |
| E4 | **Match:** with C2 selected, P1's v2 record is retained and still P1's, as candidate limitation `UNRESOLVED` [`LOCALITY_CAPTURE_MISSING_POD`]; no assertion for `orders` | `evaluation/state-on-c2.json` |
| E5 | **Match:** with C2 selected, (P2 -> O2) is still `APPLICABLE` at `orders-canary`, `OBSERVED_ONLY` | same |
| E6 | **Match:** one v1 OBSERVED bucket per Operation, 359 and 508, identical in the flag-off replay and equal to the v2 counts | `evaluation/state-off-c1.json`, `state-on-c1.json` |
| E7 | **Match:** C1-selected `aip:snapshot:v1:…b94382691520` differs from C2-selected `…84294bd48454`; both states carry v2 (so the conditional keys) | `evaluation/state-on-c1.json`, `state-on-c2.json` |

## Attempts and deviations (disclosed)

| Attempt | Outcome | Kept |
|---|---|---|
| 1 (14:13Z, recording Collector `batch` 1 s) | The recording had no in-batch CLIENT/SERVER pair. C1/C2 were also invalid: `resources.yaml` joined the two `kubectl` documents without `---` (the precedent's PROVENANCE command omits it; its committed file has it), which the importer rejects as `K8S_SNAPSHOT_INCOMPLETE` (duplicate mapping key). | Only the unmodified `otlp.jsonl`, `identities.env`, `analysis.json` and `run-log.txt`, under `attempt1/`, for the gate 4 CLIENT-first order (owner decision). C1/C2 are discarded. |
| 2 (14:29Z) | Stopped before C1: the same `resources.yaml` defect. | Nothing. |
| 3 (14:31Z, `batch` 10 s, separator fixed) | Clean. This recording. | Everything here. |

Harness choices that are configuration, not synthesis:
- **Semantic conventions.** `OTEL_SEMCONV_STABILITY_OPT_IN=http` makes the instrumentations emit the stable HTTP conventions AIP reads (`http.request.method`, `http.route`).
- **`peer.service`.** It is set by the requests instrumentation's `request_hook` from the configured target service name (`TARGET_PEER_SERVICE`). It is never inferred from an address.
- **Recording Collector as root.** It runs as root only to write its `hostPath`, which `rehearse.sh` copies out with `docker cp`; the contrib image has no `tar`, so `kubectl cp` is impossible.
- **Two clean replays, not a C2 reimport.** Both envelopes declare `expectedPriorInventoryRevision: null` (a first import), so C1 and C2 are each replayed into their own clean state. C2 is not reimported over C1, and nothing recorded is edited. Runbook §6 step 2 allows either.
- **Evaluation path.** Answers are read with the internal `ArchitectureIntelligenceService.assess_local_calls` (`replay/evaluate.py`, run in the AIP container with the app's own configuration). There is no public route until I3.
