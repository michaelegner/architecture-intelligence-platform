# AIP v0.7.0 I4 — Tyk Semantic Cross-Check Dossier

**Status:** I4.3a deliverable (I4 spec §6, §11 artifact 3; parent [§24](specification.md)). A documentation and capture-based mapping dossier. It is **not** a second adapter, runs no Tyk, adds no code, fixture or contract, and claims no adapter qualification.
**Question (spec §6):** can the frozen AIP vocabulary represent the Tyk source without pretending its native access concept means the same thing as APISIX consumer restriction?
**Structure:** the eight sections frozen in the [decision record D6](i4-decision-record.md). Section 8 states the one outcome.

## Evidence base and how each claim is marked

Only these sources are used. No claim goes beyond them.

| Tag | Source |
|---|---|
| `[SPIKE]` | The real Tyk Gateway 5.13.0 assets under [`i0-spike/tyk/`](i0-spike/tyk/): `tyk.conf`, `apps/orders.json`, `run.sh`, `otel.yaml`, `expected-capture.txt`, `dup-alias-probe.sh`, `dup-alias-output.txt`, run with the pinned images in [`i0-spike/README.md`](i0-spike/README.md) |
| `[F#]` | The numbered finding of the [I0 spike README](i0-spike/README.md) |
| `[DOC]` | The documentation recorded in the [I0 capability matrix](i0-capability-survey-matrix.md), not inspected on a running Tyk |
| `[FROZEN]` | The frozen AIP contracts: parent [`specification.md`](specification.md), [`i1-gateway-source-contract.md`](i1-gateway-source-contract.md), [`i2-measurement-contract.md`](i2-measurement-contract.md), and the published v0.7 schemas |
| `[NOT-ESTABLISHED]` | Neither inspected nor documented well enough to claim. Listed so it is not mistaken for a finding |

The spike scenario: one API definition `orders-api` (listen path `/orders/`, auth-token) in front of `traefik/whoami`; three keys created with fixed names through the Gateway API (alpha and beta hold `orders-api`, gamma holds only `other-api`); fixed traffic alpha ×3, beta ×1, gamma ×1, one unauthenticated `[SPIKE: run.sh, apps/orders.json]`. Policies, `allowed_urls`, several API versions and several organizations were **not** exercised.

## 1. The native configured-access relationship

- **Tyk:** a **key** (a Session) holds `access_rights`, a map keyed by `api_id`, each entry carrying `versions` (and, per the documentation, `allowed_urls`). In the capture the relationship is exactly `{alias, org_id, access_rights{api_id, versions}}` `[SPIKE: expected-capture.txt]`. A **Policy** is a reusable template of access rights applied to sessions through `apply_policies` `[DOC]`; the spike applied none.
- **APISIX (frozen):** a Route carries a `consumer-restriction` plugin whose `whitelist` names Consumers by `username`; AIP creates a `ConfiguredAccess` per `(consumer, route)` with `rule_kind = CONSUMER_RESTRICTION_ALLOW_LIST`, `polarity = ALLOW`, `scope = ROUTE` `[FROZEN: i1 §3, §4]`.

The two are not the same concept. APISIX states *a restriction on a Route naming the consumers it admits*. Tyk states *rights held by a key, per API definition and version, optionally grouped by policy*. The direction of the statement is different (restriction held by the target versus rights held by the subject), the scope is different (a Route versus an API definition and version), and Tyk has no consumer entity in the evidenced path, only a key `[DOC: "Differences that must stay visible"]`. Neither is a "subscription": there is no plan, approval or product in either `[DOC]`. A Tyk relationship therefore must not be recorded under `CONSUMER_RESTRICTION_ALLOW_LIST`.

## 2. Identity: key, alias, application, policy

| Concept | Tyk | Stable? | Secret? | Evidence |
|---|---|---|---|---|
| Key (session id) | the token the client presents; with `hash_keys: true` the stored id is a hash of it | the id is stable while the key exists | the token **is a secret**; the stored hash is derived from it | `[SPIKE: tyk.conf]`, `[F8]`, `[F11]` |
| Alias | a free-text field on the key | stable per key, but **not unique** | no | `[F6]` |
| Application | a Dashboard concept; absent from the open-source path | n/a | n/a | `[DOC]`, `[NOT-ESTABLISHED]` for OSS |
| Policy | a named rights template referenced by `apply_policies` | by policy id | no | `[DOC]`; not exercised in the spike |
| Organization | `org_id` on the key | by value | no | `[SPIKE: expected-capture.txt]` |

Key listing is off by default and returns hashes (`enable_hashed_keys_listing`), and generated keys are random, so replay needed fixed key names `[F8]`. The spike normalization dropped the key hashes and all key material; whether a **stable, non-secret** key identifier exists (for example whether the stored hash may be retained under parent §29) is `[NOT-ESTABLISHED]`. Hash and alias forms are `N-E` in the matrix `[DOC]`.

By contrast APISIX gives the frozen pipeline a unique, non-secret consumer identity, the `username`, which is also the Admin API resource id `[F13]`, and keeps credentials as a separate resource `[F14]`.

## 3. F6: the alias is not unique

Two distinct keys with the same alias `spike-alpha` were counted in **one** request series: the series went from 3 to 4 after one request with the second key, and two keys shared the alias `[F6; SPIKE: dup-alias-output.txt]`. The only per-subject label the evidenced instrument carries is `key_alias` `[SPIKE: tyk.conf]`.

Consequences, stated against the frozen rules:

- The frozen runtime join resolves a `consumer` label **iff** it equals a `GatewayConsumer.username` of the same gateway instance and environment, exactly `[FROZEN: i2 §6 J01–J06]`; the consumer id is a function of `(gateway_instance_id, username)` `[FROZEN: i1 §3]`. If a Tyk adapter minted a `GatewayConsumer` per **alias**, two distinct keys would receive one identity and the merged series would be read as one subject. That is a collapse and is not permitted (parent §10: credential/key identity and consumer identity stay distinct; association is not equivalence).
- If it mints one per **key**, the metric label (the alias) cannot be joined to it: the label names no unique key.
- Therefore alias alone cannot license one resolved canonical consumer. Two honest representations exist, and neither collapses: (a) an operator-asserted uniqueness rule that the capture can **verify** (more than one key per alias in the capture is detected and no `GatewayConsumer` is minted for that alias, with a limitation), or (b) a key-derived identifier, if and only if its non-secret status is established (section 2). Under either, a duplicated alias leaves the label unresolved.
- In the frozen pipeline an unresolved label is not a new outcome. The series stays source evidence and the Route carries the route-wide unattributed limitation already qualified as `A10` and `N3`, with no consumer row `[FROZEN: i2 §6; register S22-06, A10]`. The frozen pipeline has no `AMBIGUOUS` consumer outcome, so I4 invents no executable case (register S22-06 `DOSSIER_ONLY`). What is **lost** is the ability to attribute that alias's usage to either key; what is **kept** is that no usage is attributed to the wrong one.

## 4. How request usage is attributed

- Per-consumer counters need a **custom** `api_metrics` instrument; defining one **replaces** the default instruments `[F7; SPIKE: tyk.conf]`. The evidenced instrument is the counter `tyk.spike.requests.total` with labels `api_id`, `code` and `key_alias`, exported over OTLP (5 s interval) through an OpenTelemetry Collector to a Prometheus endpoint `[SPIKE: tyk.conf, otel.yaml]`.
- An unauthenticated request carries `key_alias="unattributed"`, **only because the spike configured that default**; without it the dimension would be absent `[F3; SPIKE: tyk.conf]`. APISIX marks the same condition with `consumer=""` `[F3]`.
- A denied request is counted under the key's alias: gamma's `403` is `key_alias="spike-gamma"`, `code="403"` `[F2; SPIKE: expected-capture.txt]`. The same holds for APISIX `[F2]`.
- The evidenced Tyk instrument has **no response-origin label**. The frozen APISIX measurement distinguishes a response produced by the upstream from one produced by the gateway through the required `response_source` label, which is what separates `upstream_request_count` from `rejected_attempt_count` `[FROZEN: i2 §2.1, §4]`. In the Tyk capture the only available separator is the status code, and F2 states that observed usage "must be derived from the status code, not from the consumer label alone" `[F2]`. A `403` from the upstream and a `403` from the gateway are not distinguishable from these labels. [NOT-ESTABLISHED] whether another dimension can carry the origin.

## 5. Environment, window and coverage

- **Environment** is not source-reported by Tyk (its resource attributes are `instance` and `job`) and is operator-asserted capture context, exactly as for APISIX `[F10]`.
- **Window:** OTLP counters are cumulative counters of the same class as Prometheus counters; a window would be the delta between two boundary reads `[DOC]`. The spike read the endpoint once, after a 12 s wait, with a 5 s export interval `[SPIKE: run.sh, tyk.conf]`; it did not exercise boundary deltas, counter reset on restart, or a settle rule. Those are `[NOT-ESTABLISHED]` for Tyk. APISIX counters lag and needed a settle rule `[F4]`; a Tyk analogue (export interval plus collector scrape) is plausible but unmeasured.
- **Coverage:** a consumer with no traffic has **no series**; zero and not-measured are indistinguishable from the metrics `[F5]`. Coverage therefore cannot come from the metrics. For APISIX the frozen source takes it from capture metadata (a per-Route flag that the Prometheus plugin was enabled for the whole window, and disabled labels) `[FROZEN: i2 §2]`. Tyk has no per-Route plugin toggle in the evidence; what would attest "the instrument was defined and exported for the whole window" is operator-asserted, and the documented cardinality overflow bucket (`otel.metric.overflow=true`) is a source-specific coverage limitation `[DOC]`. None of this was inspected.
- **Revision identity and authoritative removal** for a Tyk configuration inventory were not investigated (`U` in the matrix) `[DOC]`, and are listed "Not tested" in the spike README. The frozen lifecycle (a complete, revision-bearing inventory that removes what is gone) cannot be assumed for Tyk `[NOT-ESTABLISHED]`.

## 6. Source-specific concepts that do not map to APISIX consumer restriction

1. **Rights held by a key, not a restriction on the target** (section 1).
2. **API definition as the exposure object.** A Tyk API definition carries the listen path, the target URL and the version table together `[SPIKE: apps/orders.json]`, whereas APISIX splits Route, Service and Upstream. It is neither cleanly a Gateway Route nor a Gateway Service.
3. **Version-scoped rights** (`versions` per `api_id`) and, per the documentation, **URL-scoped rights** (`allowed_urls`) `[DOC]`. The spike exercised `versions: ["Default"]` only.
4. **Policies** that grant rights to many keys through `apply_policies` `[DOC]`. A key's effective rights would depend on policy resolution that the capture did not perform.
5. **Alias versus key**, and the hashed key listing (sections 2 and 3).
6. **A custom instrument that replaces the defaults, with an operator-chosen label set** (section 4), so the capture must declare which instruments and labels exist `[F7]`.
7. **Rights vary in kind, not only in extent.** Gamma holds no rights to `orders-api` yet its request is counted `403` under its own alias `[SPIKE: expected-capture.txt]`: usage evidence exists for a subject with no configured access to that API, the same shape as the frozen `NO_MATCHING_CONFIGURED_ACCESS_FACT`.

## 7. The frozen vocabulary, term by term

"Frozen contracts" below are the APISIX-source contracts (I1, I2) and the published v0.7 schemas. The parent vocabulary (§9) fixes meanings; the I1/I2 contracts fix the APISIX realization of them.

| Frozen term | For Tyk | Reading |
|---|---|---|
| Gateway Consumer / Consumer Application | the subject of the rights is a **key**; no stable, non-secret, unique consumer identifier is established (sections 2, 3) | Represented only under a verifiable uniqueness rule or an established non-secret key id; never by alias alone. Source-specific distinction kept explicit |
| Configured Access Relationship | key `access_rights` per `api_id` and version | The meaning (a configured fact, not authorization, approval or intent: parent §30) is preserved. The carrier fixes `rule_kind = CONSUMER_RESTRICTION_ALLOW_LIST`, `polarity = ALLOW`, `scope = ROUTE` `[FROZEN: i1 §3]`; a Tyk fact needs its own `rule_kind` and a scope that is not `ROUTE`. The published answer types `rule_kind`, `polarity` and `scope` as opaque non-whitespace strings, not enumerations, so the wire carries a different value without a new field `[FROZEN: published answer schema]`. `allowed_urls` and policy-derived rights have no field and are `[NOT-ESTABLISHED]` |
| Gateway Route | the API definition's exposure (listen path and versions) | Not a Route by identity. Representable as a Route only with an explicit statement that the exposure object is a Tyk API definition; otherwise it would pretend an API definition is an APISIX Route |
| Gateway Service | the API definition's target | Same caution; `GatewayService` is an APISIX Service id `[FROZEN: i1 §3]` |
| API Operation, API Contract, Application Service | unchanged | Association stays explicit (route/target to Operation or Service by statement or exact match, never by name or similarity) `[FROZEN: i2 §6]`; unaffected by the gateway |
| Observed Consumer Interaction | counts per `(alias, api_id, code)` | The upstream and rejected split needs a response-origin attribute that the evidenced instrument lacks (section 4); without it the neutral meaning is preserved only by reporting usage as unestablished, never by guessing from the code |
| Measurement window, coverage, limitations | operator-asserted environment; deltas and coverage not exercised | Neutral meaning kept; the evidence for a valid window and for `SUFFICIENT_FOR_ZERO` is `[NOT-ESTABLISHED]`, and the answer abstains rather than treating absent series as zero (parent §31) |
| Source revision, authoritative removal | not investigated | `[NOT-ESTABLISHED]` |
| Public naming | `apisix_version` is a field of the window evidence and `RowConsumer.source_name` is documented as the "APISIX Consumer username" `[FROZEN: published answer schema, api_usage_contracts.py]` | The names, not the meanings, are APISIX-specific. A second adapter needs a reviewed additive generalization; no v0.7 behavior depends on it |

No native Tyk concept is renamed into a generic "subscription", "plan" or "consumer".

## 8. Outcome

**`REPRESENTABLE_WITH_SOURCE_SPECIFIC_DISTINCTION`**, within the evidence listed above.

Reading under parent §24: the frozen vocabulary's *meanings* (distinct consumer, key and credential identities; a configured access relationship that is a fact and not a judgment; an observed interaction separate from configured access; explicit coverage; explicit association) can represent the evidenced Tyk path **without collapse**, provided the Tyk-native distinctions stay explicit and unnormalized:

1. the subject is a key, not an APISIX-style named consumer, and the alias, which is the only attributable label, is not an identity (F6);
2. the access is rights held per API definition and version, carried under its own `rule_kind` and a non-`ROUTE` scope, not under `CONSUMER_RESTRICTION_ALLOW_LIST`;
3. the exposure object is an API definition, not an APISIX Route or Service;
4. rejected attempts and upstream requests are separable only with a response-origin attribute the evidenced instrument lacks.

This is not `REPRESENTABLE`, because the carriers, the join and the measurement contract are shaped by APISIX and cannot take a Tyk fact unchanged. It is not `MODEL_GAP`, because every distinction above has a safe representation inside the frozen vocabulary: an opaque `rule_kind` and `scope`, a consumer left unresolved rather than collapsed, usage left unestablished rather than guessed, and association left explicit. F6 in particular produces the already-qualified unresolved-label behavior, not a wrong attribution.

What this does **not** establish, and the conclusion must not be read to include: URL-scoped rights, policy-derived effective rights, a stable non-secret key identifier, response-origin attribution, boundary deltas and counter resets, a coverage attestation, a Tyk configuration revision or authoritative-removal scope, and any Tyk adapter behavior. A future Tyk adapter would have to establish each of them from real captures and would extend the carriers and the measurement contract through a reviewed amendment. Release scope is unchanged: Tyk remains a cross-check, not a v0.7 source, and this outcome is not a blocker for v0.7.
