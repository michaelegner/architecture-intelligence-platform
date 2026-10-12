# I0 spike evidence — APISIX 3.19.0 and Tyk 5.13.0

**Status:** throwaway feasibility evidence for the v0.7.0 I0 survey ([`../i0-capability-survey-matrix.md`](../i0-capability-survey-matrix.md)). Not production code, not qualification evidence, not run in CI. Finalists were chosen by the owner on 2026-10-12 (APISIX and Tyk).
**Run date:** 2026-10-12 (UTC), Docker 29.8.1 / Compose 5.5.1 on WSL2. Everything here uses fake credentials (`SPIKE-FAKE-…`, `spike-admin-secret`) and no external accounts.

## Pinned images

| Role | Image digest |
|---|---|
| APISIX 3.19.0 | `apache/apisix@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141` (tag `3.19.0-debian`) |
| Tyk Gateway 5.13.0 | `tykio/tyk-gateway@sha256:ec0854f6f8d4f7282a5676cffac9dc179230e467718bac1d3f54afec00380b90` (tag `v5.13.0`) |
| Upstream | `traefik/whoami@sha256:43a68d10b9dfcfc3ffbfe4dd42100dc9aeaf29b3a5636c856337a5940f1b4f1c` (tag `v1.10.3`) |
| etcd (APISIX Admin-API mode) | `quay.io/coreos/etcd@sha256:d967d98a12dc220a1a290794711dba7eba04b8ce465e12b02383d1bfbb33e159` (tag `v3.5.16`) |
| Redis (Tyk) | `redis@sha256:c1e88455c85225310bbea54816e9c3f4b5295815e6dbf80c34d40afc6df28275` (tag `7.4.1-alpine`) |
| OTel Collector (Tyk) | `otel/opentelemetry-collector-contrib@sha256:d0ebf65280da2e1b1491d1b93648281afd353d4b9ea19160090303cec9a233bd` (tag `0.116.1`) |

## How to reproduce

```text
docker network create spike-net
docker run -d --name whoami --network spike-net traefik/whoami@sha256:43a68d10…   # upstream, both gateways
./apisix/run.sh   > out.txt      # compare with apisix/expected-capture.txt
./tyk/run.sh      > out.txt      # compare with tyk/expected-capture.txt
```

Each `run.sh` starts fresh containers, sends the same fixed traffic (alpha ×3, beta ×1, gamma ×1, one unauthenticated), and prints a **normalized** capture. Only the normalized capture is required to match; raw vendor output carries runtime values and is not compared.

**Normalization rules.** APISIX: keep `apisix_http_status` lines, drop the `node="…"` label (container IP), sort. Tyk: for configured access, list keys, read each by hash, keep only `alias`, `org_id` and `access_rights{api_id, versions}`, sorted by alias (drop `last_updated`, key material, key hashes); for measurement, keep `tyk_spike_*` lines, drop the `instance="…"` label (random gateway id), sort.

**Result.** Two consecutive runs of each script produced byte-identical normalized captures (`cmp` clean). The expected captures contain no key values.

## Scenario

One route (APISIX `orders-route` at `/orders`; Tyk API `orders-api` at `/orders/`) in front of `whoami`. Three consumers: **alpha** and **beta** are granted the route; **gamma** is not. Traffic: alpha ×3 → 200, beta ×1 → 200, gamma ×1 → 403, no credential ×1 → 401.

- Main scenario, APISIX standalone YAML: `key-auth` + `consumer-restriction` (whitelist alpha, beta) + `prometheus`, standalone YAML mode.
- Tyk: auth-token API, three keys created through the Gateway API with fixed key names and `access_rights` (gamma holds rights only to `other-api`); native OTLP metrics with one custom `api_metrics` instrument carrying `session.alias`, exported through an OTel Collector to a Prometheus endpoint.

## Findings

| # | Finding | Gateway | Bearing on the I0 gates |
|---|---|---|---|
| F1 | Consumer-attributed request counters work on the open-source path: `apisix_http_status{consumer="spike-alpha",code="200",route=…} 3`; Tyk `tyk_spike_requests_total{key_alias="spike-alpha",api_id=…,code="200"} 3`. | both | Gate 3 met on both, in the observed scenario. |
| F2 | **A denied request is attributed to its consumer.** gamma's 403 is counted under `consumer="spike-gamma"` (APISIX) and `key_alias="spike-gamma"` (Tyk). Consumer-attributed request count therefore includes rejected attempts; "observed usage" must be derived from the status code, not from the consumer label alone. | both | Semantic input for I2 qualification; not a gate failure. |
| F3 | An unauthenticated request is unattributed: APISIX `consumer=""`, Tyk `key_alias="unattributed"` (the `default` we configured; without it the dimension would be absent). | both | Supports "unattributed request ≠ request by a consumer". |
| F4 | **Counters lag.** APISIX metrics showed 2 of 5 alpha requests immediately after traffic and all 5 about 8 s later; in one etcd-mode run no `apisix_http_status` series was visible 8 s after traffic, and a 15 s wait showed it. | APISIX | Window derivation must allow a settle delay; capture must wait. |
| F5 | **Zero is absent.** A consumer with no traffic has no series on either gateway (beta/gamma had none before their first request). Measured zero and not-measured are indistinguishable from the metrics alone. | both | Gate 5 is not satisfied by the metrics; coverage must come from capture metadata (scrape time, gateway uptime/reload). |
| F6 | **Tyk alias is not unique.** A second key with alias `spike-alpha` merged into the same series (3 → 4). | Tyk | Alias cannot be the stable consumer identity without an externally enforced uniqueness rule. |
| F7 | Tyk custom `api_metrics` **replaces** the default instruments (`tyk.api.requests.total` was absent once a custom list was set). | Tyk | Matches the docs semantics; the capture must declare which instruments exist. |
| F8 | Tyk key listing is off by default (`enable_hashed_keys_listing` error); read by hash works. Generated keys are random, so replay needs fixed key names. | Tyk | Configured-access capture needs an explicit gateway setting and exposes key hashes; replay is deterministic only with controlled key names. |
| F9 | APISIX `consumer-restriction` ran after the `mocking` plugin short-circuited, so no restriction was enforced and no metrics were emitted; a real upstream fixed both. | APISIX | Plugin priority matters for what "configured" means at runtime; not a source defect. |
| F10 | Neither gateway reported an environment. APISIX `node` is a container IP; Tyk's resource attributes are `instance`/`job` (gateway id). Environment would be `OPERATOR_ASSERTED_CAPTURE_CONTEXT`. | both | Gate 4 can only be met by an operator-asserted, immutable capture context. |
| F11 | APISIX consumer usernames in YAML are plaintext-keyed (`key-auth.key`); Tyk keys are returned only as hashes in listing. | both | Redaction boundary needed in the APISIX configuration capture; Tyk listing already hashes. |
| F12 | **APISIX duplicate `username` (standalone YAML): last entry wins silently.** With two consumers named `spike-alpha` (keys `…ALPHA`, `…ALPHA2`), only `ALPHA2` authenticated (200); `ALPHA` returned 401 (`invalid api key`). Metrics showed one `spike-alpha` series. No load error or warning was logged. | APISIX | Within this mode the username behaves as a unique key, but a duplicate removes the earlier consumer without any signal, so a configuration capture cannot show it was ever declared. Admin API/etcd mode untested. |
| F13 | **APISIX Admin API enforces username uniqueness visibly.** The resource id is the username (`/apisix/consumers/spike-alpha`). A second `PUT` with the same username is an update (HTTP 200, `modifiedIndex` 15 → 16) and replaces the credential; `POST` on `/consumers` is rejected (405). The earlier key then fails (401). | APISIX | Gate 2 met in Admin-API mode: the username is a unique source key and a change is visible as an update. Standalone-YAML mode (F12) overwrites silently, so the capture surface matters. |
| F14 | **Credentials are a separate resource.** `PUT /consumers/{username}/credentials/{id}` creates a credential (`cred-1`) owned by the consumer; its key authenticates as the same consumer and is counted in the same series (`spike-alpha` 200 ×2 for the embedded key and the credential). | APISIX | Consumer identity ≠ credential identity is expressible; the docs page read earlier did not establish this (matrix "N-E" now INSPECTED). |
| F15 | **The Admin API returns key values in plaintext on read** (`GET /consumers/…`, `GET …/credentials`), while the write response and etcd store them encrypted. | APISIX | A configuration capture through the Admin API reads secrets; I1 must redact credential values and keep only non-secret identity (consumer username, credential id). |
| F16 | **Revision and inventory surface exists.** Each list item carries `createdIndex` / `modifiedIndex` (etcd revisions); etcd's header revision was 18 and the consumer's `mod_revision` 16; `update_time` / `create_time` are volatile. A list under `/apisix/consumers` is a complete inventory of that etcd prefix. | APISIX | Candidate source revision and authoritative-removal scope for I1 (to be frozen in I0.2); volatile timestamps must be normalized away. |

## Not tested

- APISIX with a multi-node etcd cluster or the Ingress Controller (`namespace_consumername` naming); Kong and Gravitee (not spiked, per owner choice).
- Route↔OpenAPI operation and upstream↔application Service mapping (I2 scope).
- Source revision identity and authoritative-removal scope for either gateway.

## Admin-API mode probe

[`apisix-etcd/probe.sh`](apisix-etcd/probe.sh) reproduces F13–F16 (output in `probe-output.txt`; it is not a normalized byte-identical capture, only a recorded run). APISIX runs with etcd (`config_provider: etcd`) and an Admin API key that is fake.
