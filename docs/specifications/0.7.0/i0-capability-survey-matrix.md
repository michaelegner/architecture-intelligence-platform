# AIP v0.7.0 I0 — Capability Survey Matrix

**Status:** Draft 0.2 — I0.1 (docs survey plus finalist spikes on APISIX and Tyk, chosen by the owner 2026-10-12); the selection decision follows in I0.2.
**Governing specification:** [`i0-gateway-capability-survey-and-semantic-freeze.md`](i0-gateway-capability-survey-and-semantic-freeze.md) (Proposed, merged #507, `9009ab9`) §§4–6, 8, 11; parent [`specification.md`](specification.md) §6.
**Retrieval date for every first-party source below:** 2026-10-12 (UTC). Pages are mutable; the exact claim relied on is quoted or paraphrased per row so drift is visible.

This document records what first-party documentation establishes. It does **not** select a gateway (that is the I0 selection decision) and does not normalize the four products into one model.

## 1. Evidence record convention

Each claim carries an evidence status:

| Status | Meaning |
|---|---|
| **DOC** | Stated by a first-party documentation page named in §8. |
| **INSPECTED** | Observed on a pinned, digest-pinned running instance; see [`i0-spike/README.md`](i0-spike/README.md). |
| **UNRESOLVED-NOT-INVESTIGATED** | Not looked at yet. |
| **NOT-ESTABLISHED** | Looked for in the cited pages; the pages do not say. Not the same as unsupported. |
| **UNSUPPORTED** | The source states the capability does not exist. (None recorded so far.) |

Version bounds: APISIX claims are from the 3.19 documentation; Kong from the developer.konghq.com pages whose install examples reference 3.16.0.0 (the page does not label that "current"); Tyk native OTLP metrics from Gateway 5.13.0+; Gravitee from the current documentation.gravitee.io APIM pages (version not stated on the pages read). APISIX 3.19.0 and Tyk Gateway 5.13.0 were run (§7); Kong and Gravitee were not.

## 2. Source-native configured access (spec §6)

Written in each product's own terms, before any AIP mapping.

| Gateway | Native configuration fact | Subject | Scope | Native meaning | Status |
|---|---|---|---|---|---|
| **APISIX** | `consumer-restriction` plugin: `type` ∈ {`consumer_name`, `service_id`, `route_id`, `consumer_group_id`}; `whitelist` / `blacklist` / `allowed_by_methods` (`user`, `methods`); `rejected_code` default 403. Requires an authentication plugin (`key-auth`, `jwt-auth`). | Consumer by **name** | Route or Service (examples also attach it to a Consumer); per-consumer HTTP-method allowlist | **Allowed / denied** (a restriction rule), not registered or subscribed | DOC |
| **Kong** | `acl` plugin: allow/deny list of Consumers or Consumer Groups; from v3.16 CEL `allow_when` / `deny_when` (mutually exclusive with `allow`/`deny`). Requires an authentication plugin on the same Service/Route. | Consumer or Consumer Group | Gateway Service or Route | **Allowed / denied** by group membership or expression | DOC. The `acls` membership object is NOT-ESTABLISHED on the page read. |
| **Gravitee** | Subscription = the binding between an **Application** and a published **Plan** on an **API** or **API Product**; lifecycle: created, approved, suspended, revoked. | Application | API / API Product via Plan | **Subscribed** (a formal product relationship), with plan-level access criteria and limits | DOC. Full status list NOT-ESTABLISHED. |
| **Tyk** | A **Session/key** carries `access_rights` (per `api_id`: `versions`, `allowed_urls`); a **Policy** is a reusable access-rights template applied to many sessions (`apply_policies`). OSS policies live in `policies.json` or the Gateway API. | Key (session); consumer alias is a Dashboard concept | API id / version / URL | **Granted access rights** via key and policy | DOC for fields in OSS examples. Key→consumer/alias mapping in OSS NOT-ESTABLISHED. |

Differences that must stay visible: APISIX and Kong express an *allow/deny restriction on a route/service* (APISIX also per consumer, per method); Gravitee expresses a *product subscription* with an approval lifecycle; Tyk expresses *rights held by a key*, grouped by policy. None is a generic "subscription".

## 3. Capability matrix (spec §5)

Legend: **Y** = DOC says yes; **N-E** = NOT-ESTABLISHED on the pages read; **U** = UNRESOLVED-NOT-INVESTIGATED.

| Area | APISIX (3.19 docs) | Kong (docs, 3.16 examples) | Gravitee APIM | Tyk |
|---|---|---|---|---|
| API exposure object | Route, Service (Y) | Gateway Service, Route (Y) | API, API Product (Y) | API definition (`api_id`) (Y) |
| Consumer identity | Consumer `username` (Y); `id` is "the unique identifier" (Y). `username` uniqueness N-E | Consumer `id` (UUID), `username`, `custom_id`, all documented unique (Y) | Application (Y); identifier fields N-E | Key / session; alias only seen in Dashboard UI (N-E in OSS) |
| Credential separate from identity | INSPECTED: a separate `credentials` resource exists (F14); the page's example embeds the key in plaintext in the Consumer's `key-auth` config; the Admin API reads keys back in plaintext (F15) | Y: credentials authenticate a Consumer, one Consumer can have several | Y: application credentials, API-key management | N-E |
| Configured access relation | consumer-restriction (§2) | acl (§2) | Subscription (§2) | access_rights + policy (§2) |
| Target scope bound | Route, Service; method per consumer | Service, Route | API / API Product via Plan | `api_id` + versions + `allowed_urls` |
| Runtime attribution to same consumer | Y: `consumer` label = "Name of the Consumer associated with a request" on `apisix_http_status`, `apisix_bandwidth`, `apisix_http_latency`; empty when none. Absent from `apisix_http_requests_total`, `apisix_upstream_status`, stream metrics. | Partly: `consumer` label on `kong_http_requests_total`, `kong_http_consumer_status`, `kong_bandwidth_bytes`; `kong_http_requests_total` / bandwidth label filled only when `per_consumer: true` (default `false`) and `status_code_metrics` / `bandwidth_metrics` enabled | Y in analytics: v4 metrics `applicationId`, `planId`, `subscriptionId`, `apiId`; v2 `application`, `plan`, `subscription`, `api`. Keyless plan: `applicationId` is "1". Logs carry no application/plan fields. | Not default: native OTLP counter `tyk.api.requests.total` documented (via search summary) with `tyk_api_id`, method, status; consumer key only possible through custom `api_metrics`, whose schema and dimensions are N-E |
| Runtime target in same measurement | Y: `route`, `service`, `matched_uri`, `matched_host` labels | Y: `service`, `route` labels | Y: `apiId` | Y: `tyk_api_id` |
| Environment identity | N-E. `node` label only; no environment label. Capture context would be operator-asserted | N-E (`node_id` on core metrics) | N-E on pages read | N-E |
| Observation window | Prometheus counters scraped at capture time; window = scrape-to-scrape delta (derived, not source-reported) | Same | Per-request records in Elasticsearch/file (timestamp field N-E on page read) | OTLP counters, same class as Prometheus |
| Coverage: zero vs missing | N-E. A counter that has not been incremented is absent; `consumer=""` marks unattributed requests (Y) | N-E; label empty when consumer not available ("when available") | N-E | N-E. Overflow bucket `otel.metric.overflow=true` exists on cardinality limit (Y) |
| Replayability | Metrics text endpoint `127.0.0.1:9091/apisix/prometheus/metrics`; config via Admin API / etcd (config export path U) | `/metrics` on Status API; config via Admin API / decK (U) | Config via Management API (U); analytics from Elasticsearch or File reporter | Config via `policies.json` / Gateway API; metrics via OTel Collector → Prometheus (U) |
| Revision identity | U | U (`kong_data_plane_config_hash` metric exists on data planes, Y) | U | U |
| Removal / authoritative inventory | U | U | U | U |
| Secrets in evidence | Keys can sit in plaintext in Consumer plugin config: a redaction boundary is required (Y) | Credentials are separate entities (Y) | Application credentials separate (Y); not investigated | Keys are secrets; `hash`/alias form N-E |
| OSS / self-hosted path | Apache project; all cited pages are the open-source docs | **NOT-ESTABLISHED**: the pages read do not mark the Prometheus or ACL plugin OSS vs Enterprise or name a free image. Consumer Groups appear Enterprise-oriented (search summary only) | Elasticsearch and File reporters are Community; TCP and Datadog Enterprise only (Y). Community vs Enterprise for the subscription model N-E | Native OTLP metrics are in Community and Enterprise since 5.13.0 (Y); OSS policies in `policies.json` (Y) |
| Mapping burden | Route↔Operation, Service↔application Service: user-authored or ambiguous until inspected | same | API↔contract: possibly explicit if API is imported from OpenAPI (U) | `api_id`↔contract (U) |
| Native distinctions a generic model would lose | allow/deny and per-method restriction vs. grant; consumer *name* is the join key | group/expression restriction (v3.16 CEL); Consumer Groups | approval lifecycle, Plan, keyless special case, API Product | key + policy, version and URL-level rights, alias vs key |
| Operational cost | U | U | Heavier: Elasticsearch required for analytics views (Y) | Needs OTel Collector for Prometheus (Y); version ≥ 5.13 for native metrics |

## 4. Gate view (spec §12.1), documentation evidence only

This is a *first reading from documentation*, not the selection. "Open" means a spike or further reading must settle it.

| Gate | APISIX | Kong | Gravitee | Tyk |
|---|---|---|---|---|
| 1 Real native configured consumer/API relationship | Met (DOC) | Met (DOC) | Met (DOC) | Met (DOC) |
| 2 Stable non-secret consumer identity | Partial: name is the join key; uniqueness N-E | Met (UUID, username, custom_id) | Open: identifier fields N-E | Open: alias OSS N-E |
| 3 Request-derived consumer-attributed usage | Met on paper: consumer label on request counters; independence to settle at inspection | Met on paper but only with `per_consumer` and optional metrics enabled | Met on paper (Elasticsearch/File reporter fields) | Open: needs custom `api_metrics`, schema N-E |
| 4 Bounded environment / window | Open: environment must be operator-asserted; window derived | Open | Open | Open |
| 5 Explicit coverage limitation | Open | Open | Open | Open (overflow bucket only) |
| 6 Deterministic capture / replay | Open until spike | Open | Open | Open |
| OSS path (§11) | Met | **Open (edition not established)** | Met for File/ES reporter path | Met for native metrics |

Candidate for further inspection ranked by documented evidence only (not a decision): APISIX is the only one with consumer-attributed request counters, a documented unauthenticated metrics endpoint and an unambiguous OSS path, all on the pages read. Kong and Gravitee each have an open gate that docs alone cannot close; Tyk's gate 3 is blocked on an undocumented custom-metric schema.

**Eligible set.** The matrix does not derive a formal §12.1 eligible set: several gates are open for every candidate after the documentation pass, so none is eliminated on documentation alone. The owner chose APISIX and Tyk as spike finalists from this gate view; the spikes are feasibility evidence. The eligible set, per-criterion comparison and deciding criterion are recorded in the I0.2 selection decision (spec §12.2-12.3).

## 5. Open items that the next slice must close or carry forward

1. Kong: OSS-vs-Enterprise status of `acl`, Consumer Groups, Prometheus `per_consumer`, and image availability.
2. Tyk: `api_metrics` schema and whether a hashed key or alias can be a dimension; OSS key→alias mapping; default metric names.
3. Gravitee: Application identifier, metric timestamp field, Community availability of the subscription model, file-reporter record shape.
4. All: configuration export surface, revision identity, authoritative-removal scope, environment identity.

## 6. Non-claims

Nothing here selects a gateway, defines an AIP vocabulary or canonical type, or asserts that any product is unsupported. A blank or N-E cell means the cited pages did not establish it.

## 7. Inspected findings (APISIX 3.19.0, Tyk 5.13.0)

Detail, pins and reproduction are in [`i0-spike/README.md`](i0-spike/README.md) (findings F1–F16). Effects on the §4 gate view, for these two candidates only:

| Gate | APISIX | Tyk |
|---|---|---|
| 2 Stable non-secret consumer identity | **Met in Admin-API mode (INSPECTED)**: the username is the resource id; a duplicate is an update (F13). In standalone YAML a duplicate silently replaces the earlier consumer (F12), so the capture surface must be the Admin API | **Weakened**: `alias` is not unique (F6); a uniqueness rule would have to be enforced outside Tyk |
| 3 Request-derived consumer-attributed usage | **Met (INSPECTED)** by default labels | **Met (INSPECTED)** only with a custom `api_metrics` instrument on `session.alias`; replaces default instruments (F7) |
| 4 Bounded environment / window | Not source-reported; operator-asserted context; window from scrape deltas after a settle delay (F4, F10) | Not source-reported; operator-asserted context (F10) |
| 5 Explicit coverage limitation | Zero = absent series (F5) | Zero = absent series (F5); cardinality overflow bucket documented |
| 6 Deterministic capture / replay | **Met for the spike**: normalized capture byte-identical across two runs; Admin API gives revision indexes (F16); credential values are returned in plaintext on read and need redaction (F15) | **Met for the spike** with fixed key names and explicit listing setting (F8) |
| OSS path | Met | Met (Community 5.13.0; Redis and OTel Collector required) |

Both candidates count denied requests under their consumer (F2) and treat unauthenticated requests as unattributed (F3). The unresolved points that need an owner-level semantic or selection decision are F5 (coverage cannot come from the metrics alone) and F6 (identity).

## 8. Sources (first-party, retrieved 2026-10-12)

- APISIX consumer-restriction: <https://apisix.apache.org/docs/apisix/plugins/consumer-restriction/>
- APISIX prometheus plugin: <https://apisix.apache.org/docs/apisix/plugins/prometheus/>
- APISIX Consumer terminology: <https://apisix.apache.org/docs/apisix/terminology/consumer/>
- Kong Prometheus plugin and reference: <https://developer.konghq.com/plugins/prometheus/>, <https://developer.konghq.com/plugins/prometheus/reference/>
- Kong ACL plugin: <https://developer.konghq.com/plugins/acl/>
- Kong Consumer entity: <https://developer.konghq.com/gateway/entities/consumer/>
- Kong install page (edition question): <https://developer.konghq.com/gateway/install/>
- Gravitee subscriptions: <https://documentation.gravitee.io/apim/secure-and-expose-apis/subscriptions>
- Gravitee reporters: <https://documentation.gravitee.io/apim/analyze-and-monitor-apis/reporters.md>
- Tyk policies: <https://tyk.io/docs/api-management/policies>
- Tyk key/session fields: <https://tyk.io/docs/api-management/gateway-config-managing-classic>
- Tyk logs and metrics: <https://tyk.io/docs/api-management/logs-metrics> (the `tyk.api.requests.total` name and dimensions come from a search summary, not a page read in full; treat as NOT-ESTABLISHED until the Default Metrics page is read)
