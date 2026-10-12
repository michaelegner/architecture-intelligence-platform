# AIP v0.7.0 I0 — Source Selection Decision and Semantic Freeze

**Status:** Proposed decision record — owner review in PR B (I0.2); becomes frozen on merge.
**Governing specification:** [`i0-gateway-capability-survey-and-semantic-freeze.md`](i0-gateway-capability-survey-and-semantic-freeze.md) (Proposed, merged #507) §§12–14, 16, 18; parent [`specification.md`](specification.md) §§9–17, 29–31, 34–35.
**Evidence:** [`i0-capability-survey-matrix.md`](i0-capability-survey-matrix.md) and [`i0-spike/README.md`](i0-spike/README.md) (merged #508, `fbc8550`). Finding numbers (F1–F16) refer to the spike README.
**Owner decisions taken while preparing this record (2026-10-12):** select APISIX (O1); retain Tyk as the I4 cross-check; accept operator-asserted environment plus capture-metadata coverage.

This record contains the semantic decision record (artifact 2) and the source-selection decision (artifact 3). The acquisition plan, reconciliation dossier, handoff and completion record are separate files.

---

## 1. Selection (O1)

| | |
|---|---|
| Selected gateway | **Apache APISIX** |
| Selected product / version | APISIX **3.19.0** (`apache/apisix@sha256:9a7e45dc…1141`, spike evidence) |
| Configured-access source surface | Admin API over etcd (`config_provider: etcd`) |
| Measurement source | `prometheus` plugin, metric `apisix_http_status` |
| Cross-check gateway for I4 | **Tyk** (Gateway 5.13.0), see §6 |

## 2. Eligible set and §12.1 gates

Gate status uses the evidence classes of the survey matrix. "Not demonstrated" means the first-slice question could not be shown with the evidence gathered, not that the product is unsupported.

| Gate (§12.1) | APISIX | Tyk | Kong | Gravitee |
|---|---|---|---|---|
| 1 Real native configured consumer/API relationship | Met (INSPECTED: `consumer-restriction` enforced, F9, F13) | Met (INSPECTED: key `access_rights`) | Met (DOC) | Met (DOC) |
| 2 Stable non-secret consumer identity | **Met**: Consumer `username` is the Admin-API resource id; a duplicate is a visible update (F13); credentials are a separate resource (F14) | **Not demonstrated**: `alias` is not unique, two keys merged into one series (F6) | Not demonstrated (DOC suggests `id`/`username`/`custom_id`; not inspected) | Not demonstrated (identifiers N-E) |
| 3 Request-derived consumer-attributed usage | **Met** (INSPECTED, F1) | Met only through a custom `api_metrics` instrument (F1, F7) | Not demonstrated (`per_consumer` off by default; edition N-E) | Not demonstrated (DOC only; needs Elasticsearch or file reporter) |
| 4 Bounded environment / window | Met under the operator-asserted rule of §5.1 and the window rule of §5.3 | same rule would apply | Not demonstrated | Not demonstrated |
| 5 Explicit coverage limitation | Met under §5.4 (zero is an absent series, F5; the capture must assert closed-world coverage) | same | Not demonstrated | Not demonstrated |
| 6 Deterministic capture / replay | **Met** (byte-identical normalized captures, two runs; Admin-API revision surface, F16) | Met for the spike | Not demonstrated | Not demonstrated |
| §11 OSS / self-hosted | Met | Met | **Not established** (edition of the plugins and image) | Met for file/Elasticsearch reporter; subscription-model edition N-E |

**Eligible set for the first slice: {APISIX}.** Tyk fails gate 2 as demonstrated; Kong and Gravitee were not demonstrated on gates 2–6 because no spike was run (owner chose APISIX and Tyk as finalists from the matrix gate view). Because the eligible set has one member, the §12.2 tie-break is not exercised.

### 2.1 §12.2 per-criterion comparison

For the eligible candidate (APISIX), and for the others as information, in the order of §12.2:

| Criterion | APISIX | Tyk | Kong | Gravitee |
|---|---|---|---|---|
| Semantic fidelity to native configured access | Restriction allow/deny preserved with `type`, whitelist/blacklist and per-method rules as source-native fields | Key + `access_rights` + policy preserved | not compared | not compared |
| Quality and determinism of consumer-attributed request evidence | Default label; counters lag (F4); denied requests attributed (F2) | Custom instrument; same properties; alias merges (F6) | not compared | not compared |
| Replayability and source-revision clarity | etcd `createdIndex`/`modifiedIndex` and header revision (F16) | Key listing needs `enable_hashed_keys_listing`; random keys unless fixed (F8) | not compared | not compared |
| OSS / self-hosted minimum path | Yes | Yes (Redis + OTel Collector) | edition not established | Yes (Elasticsearch/file) |
| Mapping burden | Route/upstream mappings user-authored or explicit label (dossier) | similar | not compared | not compared |
| Setup / sync cost | etcd + APISIX | Redis + Collector + custom config | not compared | not compared |
| Positive and negative cases | Demonstrated (200, 403, 401 in one capture) | Demonstrated | not compared | not compared |

**Deciding criterion:** gate 2 (stable non-secret consumer identity) decided between the two spiked candidates; gates 3–6 and the OSS path were met by both. The remaining two candidates were not demonstrated.

### 2.2 Why each non-selected gateway was not selected for this first slice

- **Tyk:** alias is not unique (F6), the per-consumer metric needs a custom instrument that replaces the default ones (F7), and key listing is off by default (F8). It is retained as the I4 cross-check, not rejected.
- **Kong:** no spike; `per_consumer` is off by default and the open-source status of the Prometheus and ACL plugins and of a free image is not established. Not declared unsupported.
- **Gravitee:** no spike; analytics attribution is documented but requires Elasticsearch or the file reporter. Not declared unsupported.

## 3. Known limitations of the selected path

1. Environment is not reported by APISIX (F10); it is operator-asserted capture context (§5.1).
2. Counters are cumulative since gateway start and lag behind traffic (F4); windows depend on capture metadata (§5.3).
3. Zero is an absent series (F5); a negative usage statement requires the closed-world assertion of §5.4.
4. Denied requests are attributed to the consumer (F2); usage excludes them (§5.2).
5. The Admin API returns credential values in plaintext on read (F15); capture must redact before anything is stored.
6. Standalone-YAML mode overwrites a duplicate username silently (F12); it is not a supported capture surface for v0.7.
7. Only the first-slice subset of APISIX configuration is interpreted (§4.2); other plugin scopes are recorded as unsupported.

## 4. Source-native configured access (O3)

### 4.1 Native proposition

> In APISIX, a **Consumer** (identified by `username`) is **permitted by a `consumer-restriction` rule** (`type: consumer_name`, listed in `whitelist`) attached to a **Route**, in combination with an authentication plugin (e.g. `key-auth`) on that Route that resolves requests to Consumers.

This is a restriction rule, not a subscription, registration or entitlement. The relationship is *permitted by an allow-list on a route*; it does not mean the consumer holds a credential, nor that the route is otherwise open to authenticated consumers.

### 4.2 First-slice interpretation boundary

| Source fact | Treatment in v0.7 |
|---|---|
| `consumer-restriction` on a **Route**, `type: consumer_name`, name in `whitelist` | Maps to `ConfiguredAccess` (allow-list) |
| `blacklist` entries | Recorded as source-native evidence; **not** mapped to `ConfiguredAccess`. A denied consumer is not an access fact |
| `allowed_by_methods` (per-consumer method allowlist) | Recorded; scope narrowed to those methods on the route; the first slice maps only the unrestricted-method case and records the rest as `UNSUPPORTED` |
| `type`: `service_id`, `route_id`, `consumer_group_id` | Recorded as unsupported source fields |
| The plugin attached on a Service, Consumer, plugin_config or global rule | Recorded as unsupported scope |
| Route with an authentication plugin and **no** restriction | No `ConfiguredAccess` for any named consumer (open to all authenticated consumers is not enumerated) |
| Credentials (`key-auth.key`, credential resources) | Never stored (§4.3) |

Unsupported or discarded fields relevant to interpretation are preserved by name in the source evidence, as parent §12 requires.

### 4.3 Secret boundary

No `key-auth.key`, credential value, Admin API key or token is persisted as evidence or provenance. The credential **id** (e.g. `cred-1`) is a non-secret identifier and may be retained as a source attribute only where a mapping requires it; it is not exposed publicly by default.

## 5. Runtime measurement and coverage (O5)

### 5.1 Environment
Environment is **`OPERATOR_ASSERTED_CAPTURE_CONTEXT`**: an explicit, provenance-bearing value set in the capture manifest, immutable for the fixture, never inferred from labels or free text at query time. `SOURCE_REPORTED` is not available from APISIX (F10).

### 5.2 Observed interaction
`ObservedConsumerInteraction` is derived from `apisix_http_status` series with a non-empty `consumer` label. **Usage-qualifying requests are those with `response_source="upstream"`** (the request was proxied to the upstream), regardless of status code. Series with `response_source="apisix"` (e.g. the 403 for a denied consumer, the 401 for an unauthenticated request) are **rejected attempts**: they are retained as evidence but are not usage and do not establish access. `consumer=""` series are unattributed and never establish use by a consumer.

### 5.3 Window and granularity
Counters are cumulative per (`route`, `consumer`, `code`, `response_source`, …) since gateway start. The observation window is the interval between two captures of the same gateway process, and the contribution is the counter difference. The capture manifest SHALL record both capture instants, the APISIX version, and an operator-asserted statement that the gateway was not restarted in the interval. The first-slice fixtures use a freshly started gateway so that the window is [start, capture] and the baseline is zero; a restart-detection mechanism for longer windows is not frozen here and any window that cannot assert "no restart" is `UNKNOWN_COVERAGE`.

### 5.4 Coverage rule: when zero may be stated
A configured relationship with **no** matching series may be reported as *measured zero in the qualified window* only if the capture manifest asserts, for the exact route, environment and window, all of: the `prometheus` plugin was enabled for the route throughout; the `consumer` label was not blanked through `disabled_labels`; the scrape succeeded after the settle delay of the acquisition plan; no restart in the window. Otherwise the answer is *configured; usage unestablished*. "No metric" is never zero (parent §31).

## 6. Cross-check gateway (O11)

**Tyk**, chosen because its native configured-access relationship class (key + access policy / `access_rights`) is materially different from APISIX's (consumer + allow-list restriction), not because it ranked second. Kong shares APISIX's broad class and would not satisfy the cross-check. Gravitee (application + plan + subscription) is more different still but was not spiked; it remains a candidate for any later cross-check. Tyk's spiked evidence (F1, F6, F7, F8) is the starting input for I4.

## 7. Semantic freeze: vocabulary (O2)

Internal canonical names for v0.7; **public wire names and schema are I3 (O10)**. Parent §9's nine meanings are adopted without change.

| Parent meaning | Frozen as | Canonical entity/relation or source-only | Note |
|---|---|---|---|
| API Contract | the declared Service contract (existing `Service` from OpenAPI) | existing `Service` | no new contract entity |
| API Contract Version | `Service.version` | existing attribute | no new entity; applicability stays source evidence |
| API Operation | existing `Operation` | existing | keyed by method + path under its Service |
| Gateway Service | `GatewayService` | **new** canonical entity | APISIX Service object; kept distinct from application `Service` |
| Gateway Route | `GatewayRoute` | **new** canonical entity | APISIX Route; carries `uri`, `methods` as source attributes |
| Application Service | existing `Service` | existing | never inferred from a gateway object |
| Gateway Consumer / Consumer Application | `GatewayConsumer` | **new** canonical entity | identity per §8 |
| Configured Access Relationship | `ConfiguredAccess` (consumer → route, with source-native rule kind) | **new** relation/claim | allow-list semantics only (§4); polarity and rule kind are fields |
| Observed Consumer Interaction | `ObservedConsumerInteraction` | **new** observed fact | per §5.2; separate from `ConfiguredAccess` |

Source-only (not canonical in v0.7): the restriction `type`, `blacklist`, `allowed_by_methods`, credential id, plugin ordering, `labels`. Entities for API Product, Plan, Subscription, owner or authorization rule are **not** introduced (parent §9 admission rule: APISIX does not establish them).

## 8. Consumer identity and safe identifier policy (O4)

- Consumer identity = APISIX Consumer `username` within a **declared gateway instance** (an operator-declared stable `gateway_instance_id`). The same username on two instances is two identities.
- Canonical id: a deterministic, namespaced hash over (gateway instance id, username), following the repository's `…:owned:<sha256(length-delimited(…))>` convention; the exact encoding is an I1 deliverable and must not take any credential field as input.
- The username is retained as a display/source attribute. It is operational metadata and is exposed only through the I3 answer; whether to transform or withhold it publicly is decided in I3 under parent §29. Credential values are never retained; the credential id is retained only as in §4.3.
- Unattributed requests (`consumer=""`) have no consumer identity.

## 9. Association rules (O6, O7)

Frozen at rule level; the reconciliation pipeline is implemented and qualified in I2. Details and classes are in [`i0-identity-reconciliation-dossier.md`](i0-identity-reconciliation-dossier.md).

- **Route ↔ Operation:** `USER_AUTHORED_MAPPING_REQUIRED` unless a deterministic normalization yields exactly one candidate (equal method and path template after a documented base-path rule); zero or several candidates are `UNRESOLVED` or `AMBIGUOUS`. Similarity alone never resolves.
- **Gateway upstream/target ↔ application Service:** `USER_AUTHORED_MAPPING_REQUIRED`; host, port or name similarity never resolves. An explicit source reference (a route or service `labels` entry naming an AIP Service) is admitted as `EXPLICIT_SOURCE_REFERENCE`; the label key is an I2 decision.
- **Consumer ↔ runtime attribution:** `EXPLICIT_SOURCE_REFERENCE` (the `consumer` label is the Consumer `username`), valid only within the same gateway instance and environment context.

## 10. What this record does not freeze

Qualification vocabulary and truth table (O8, I2), enumeration limits (O9, I3), REST/MCP contract and public tool name (O10, I3), final real-source replay packaging (O11 remainder, I4), restart detection for multi-capture windows (I2, only if needed), the exact consumer id encoding (I1).

## 11. Stop-condition check (spec §16)

| Condition | Result |
|---|---|
| No source can support consumer-attributed request evidence | Not triggered (APISIX, Tyk, F1) |
| Only viable path is proprietary | Not triggered (open-source path, §11) |
| Configured access needs false equivalence | Not triggered (§4 keeps allow-list semantics) |
| Identity requires secrets | Not triggered (§4.3, §8) |
| Not deterministic enough for I4 | Not triggered (byte-identical normalized captures, F16 revision surface) |
| Required association inherently ambiguous with no bounded mechanism | Not triggered (§9, dossier) |
| Needs a broad API-product/catalog model | Not triggered (§7) |
| Forces a change to the parent question or Current-State/Intent boundary | Not triggered |

Proposed terminal outcome: **`READY_FOR_I1`**, recorded in [`i0-completion-record.md`](i0-completion-record.md).
