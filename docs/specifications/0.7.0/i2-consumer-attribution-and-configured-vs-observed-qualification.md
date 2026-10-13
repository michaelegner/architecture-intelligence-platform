# AIP v0.7.0 I2 — Consumer Attribution and Configured-vs-Observed Qualification

**Status:** Proposed  
**Release / increment:** v0.7.0 / I2, API-Aware Current State  
**Governing:** [v0.7.0 parent](specification.md), [I0 source-selection decision](i0-source-selection-decision.md), [I0 acquisition/replay plan](i0-acquisition-replay-plan.md), [I0 identity/reconciliation dossier](i0-identity-reconciliation-dossier.md), and the frozen [I1 → I2 handoff](i1-i2-handoff.md).

## 1. Goal

I2 adds the **runtime half** of the first v0.7 question and joins it to the configuration state delivered by I1.

It shall establish, for one APISIX gateway instance, environment and observation window:

> **Which consumer/route relationships have a matching configured-access fact, which have independently observed upstream usage, which are measured zero under sufficient coverage, and which remain unestablished from the available evidence?**

I2 is still **Current State**. It does not decide whether access or usage is approved, intended, compliant, secure or desirable.

I2 produces internal, deterministic, snapshot-visible state for I3. It adds no REST/MCP/public schema.

## 2. Frozen inputs

I2 shall not reinterpret these decisions:

- selected gateway: APISIX 3.19.0;
- configured access: the I1 `GatewayConfiguredAccess` allow-list fact only;
- consumer identity: `(gateway_instance_id, Consumer.username)`;
- runtime source: APISIX Prometheus `apisix_http_status`;
- usage: only `response_source="upstream"`;
- `response_source="apisix"` is a rejected attempt, not usage;
- `consumer=""` is unattributed and never becomes use by a named consumer;
- environment is operator-asserted capture context;
- zero may be stated only under the I0 closed-world coverage rule;
- gateway Route, API Operation/Contract, Gateway Service and application `Service` remain distinct identity domains;
- name, host, path or graph similarity alone never establishes identity;
- the two reconciliation chains remain independent:

~~~text
Gateway Route -> Operation -> ApiContractVersion -> ApiContract

Gateway target/service -> application Service
~~~

Resolving one chain says nothing about the other.

## 3. Scope and non-goals

I2 shall implement four things only:

1. deterministic APISIX measurement capture/replay for one bounded window;
2. consumer- and route-attributed runtime observations;
3. the I0-frozen reconciliation rules for consumer, route/operation and gateway-target/application-Service associations;
4. one deterministic configured-vs-observed qualification record.

Out of scope:

- public REST/MCP/tool schemas, usernames in public answers or public evidence widening (I3);
- API product, plan, subscription, authorization or policy semantics;
- generic gateway analytics;
- payload-field dependency inference;
- automatic owner/domain/capability inference;
- multi-gateway joins;
- Tyk implementation (I4 cross-check only);
- historical trajectories;
- restart inference beyond the explicit window assertions frozen here.

## 4. Measurement source and replay

### 4.1 Separate source

Measurement is a separate configured source from the I1 APISIX configuration source.

This separation is required because configuration revision/lifecycle and runtime observation windows have different authority and update cadence. I2 shall reuse the normal source lifecycle, atomic import and replay path; it shall not introduce a parallel persistence mechanism.

The source declaration shall include at least:

- stable configured source id;
- `gateway_instance_id`;
- operator-asserted `environment`;
- fixture root.

A measurement source never owns or removes I1 gateway-configuration carriers.

### 4.2 Fixture

The deterministic replay fixture is:

~~~text
apisix-metrics-start.txt
apisix-metrics-end.txt
apisix-measurement-manifest.json
~~~

The two text files contain only normalized `apisix_http_status` samples:

- drop the `node` label;
- preserve the remaining source labels;
- sort labels deterministically;
- sort samples deterministically;
- no timestamps or scrape-local presentation data.

The manifest schema is `aip-apisix-measurement/1` and records at least:

~~~text
gateway_instance_id
environment
apisix_version
window_start
window_end
start_settled
end_settled
start_scrape_count
end_scrape_count
no_restart
disabled_labels
route_coverage
start_sha256
end_sha256
~~~

`route_coverage` records, by APISIX Route id, whether the Prometheus plugin was enabled for the whole window.

The hashes bind the manifest to the normalized extracts.

Replay reads these files only and never contacts APISIX.

### 4.3 Capture

The capture tool shall read APISIX's Prometheus endpoint and wait for **two consecutive identical normalized scrapes** at each boundary, with a bounded timeout.

Failure to settle does not manufacture zero. The fixture may still be retained with `*_settled = false`, but qualification becomes coverage-insufficient as defined below.

The capture tool must not require gateway credential secrets as architecture evidence.

## 5. Window and counter semantics

The observation window is `[window_start, window_end]`.

For an exact normalized metric series, contribution is:

~~~text
delta = end_counter - start_counter
~~~

A delta is usable for window qualification only when:

- start and end belong to the declared same gateway instance;
- APISIX version is compatible with the selected source contract;
- `window_start < window_end`;
- both boundaries settled;
- `no_restart = true`;
- the end counter is not lower than the start counter.

If these conditions do not hold, the source evidence remains inspectable but runtime usage for that affected window is **unestablished**.

I2 does not infer a restart or repair counter resets.

## 6. Runtime observation model

I2 shall preserve enough source detail to distinguish:

- attributed upstream usage;
- attributed APISIX-side rejected attempts;
- unattributed traffic.

A normalized source-series carrier shall preserve at least:

~~~text
gateway_instance_id
environment
window_start
window_end
route label
consumer label
code
response_source
request_count_delta
measurement evidence id
~~~

For a non-empty consumer label and a resolved Route/Consumer join, I2 may aggregate source series into one `ObservedConsumerInteraction` for:

~~~text
(gateway_instance_id, environment, window, GatewayRoute, GatewayConsumer)
~~~

with at least:

~~~text
upstream_request_count
rejected_attempt_count
evidence_ids
~~~

`upstream_request_count > 0` is the only fact that establishes observed usage.

A rejected attempt never creates configured access and never establishes usage.

Unattributed series are retained as source evidence but never attached to a `GatewayConsumer`.

## 7. Reconciliation outcomes

I2 freezes these internal reconciliation outcomes:

~~~text
RESOLVED
UNRESOLVED
AMBIGUOUS
CONFLICT
~~~

They are not public I3 wire vocabulary.

### 7.1 Runtime Consumer and Route

The APISIX metric `consumer` label resolves to a `GatewayConsumer` only when:

- it is non-empty;
- it equals the Consumer username;
- the gateway instance matches;
- the environment matches.

Otherwise the consumer join is `UNRESOLVED`.

The metric `route` label resolves to a `GatewayRoute` by exact APISIX Route id within the same gateway instance.

A source series whose Route or Consumer cannot be resolved remains source evidence and does not become an attributed interaction.

### 7.2 Gateway Route -> Operation

User-authored mapping is authoritative.

I2 shall admit a small mapping artifact that can explicitly bind a `GatewayRoute.id` to an existing `Operation.id`.

Without an explicit mapping, deterministic normalization is allowed only when there is **exactly one** candidate under this rule:

- the Route has one literal `uri` value;
- no wildcard/regex/path-pattern expansion is performed;
- Operation path equals that literal URI exactly;
- if Route methods are present, Operation method is one of them;
- if Route methods are absent, all Operations on the exact path are candidates.

Outcome:

- exactly one candidate -> `RESOLVED`;
- zero -> `UNRESOLVED`;
- more than one -> `AMBIGUOUS`.

There is no automatic base-path stripping in v0.7. A deployment needing one shall use explicit mapping.

Once an Operation resolves, its existing I1 `OPERATION_IN_CONTRACT_VERSION` association determines the contract version. Missing association is `UNRESOLVED`; multiple conflicting associations are `CONFLICT`.

### 7.3 Gateway target -> application Service

The exact source label key admitted for the first slice is:

~~~text
aip/service
~~~

Its value must equal an existing canonical `Service.id` exactly.

The label may appear on the APISIX Route or Gateway Service captured by I1. A user-authored mapping artifact may also bind a Gateway Route or Gateway Service id to a canonical `Service.id`.

Resolution precedence:

1. explicit user-authored mapping;
2. explicit `aip/service` source label;
3. otherwise unresolved.

A mapping and label that disagree produce `CONFLICT`.

Missing target Service produces `UNRESOLVED`.

Host/port, upstream-node, service-name, route-name and graph-neighbour similarity never resolve this join.

This target association remains independent of Route -> Operation/Contract reconciliation.

## 8. Coverage

Coverage for **zero usage** is evaluated per Route, environment and window.

It is `SUFFICIENT_FOR_ZERO` only when all are true:

- both boundary captures settled;
- `no_restart = true`;
- Prometheus was enabled for that Route throughout the window;
- the `consumer` label was not disabled;
- the metric extracts were successfully captured and bound by the manifest.

Otherwise coverage is:

~~~text
UNKNOWN_COVERAGE
~~~

Positive upstream usage still requires a valid window delta (§5), but does not require complete route coverage for the entire population.

No other coverage state is introduced in I2.

## 9. Configured-vs-observed qualification

### 9.1 Bounded row universe

I2 shall **not** generate a Cartesian product of consumers and routes.

The qualification universe is the union of:

1. every I1 `GatewayConfiguredAccess` pair; and
2. every successfully attributed runtime `GatewayConsumer` / `GatewayRoute` pair observed in the selected window.

This permits observed-only facts without inventing negative configuration claims.

### 9.2 Independent propositions

Each row has two independent fields.

Configured-access status:

~~~text
CONFIGURED_ACCESS_ESTABLISHED
NO_MATCHING_CONFIGURED_ACCESS_FACT
~~~

`NO_MATCHING_CONFIGURED_ACCESS_FACT` means only that the bounded I1 interpretation produced no matching positive access fact. It does **not** mean denied, unauthorized, misconfigured or forbidden.

Usage status:

~~~text
OBSERVED_USAGE
MEASURED_ZERO
USAGE_UNESTABLISHED
~~~

Rules:

| Configured fact | Runtime evidence | Coverage | Usage status |
|---|---|---|---|
| yes/no | matching attributed upstream delta > 0 | valid window | `OBSERVED_USAGE` |
| yes | no matching upstream delta | sufficient for zero | `MEASURED_ZERO` |
| yes | no matching upstream delta | unknown | `USAGE_UNESTABLISHED` |
| no | rejected-attempt evidence only | any | `USAGE_UNESTABLISHED` |
| any | unattributed evidence only | any | `USAGE_UNESTABLISHED` |

For an observed-only pair, configured status is `NO_MATCHING_CONFIGURED_ACCESS_FACT`; this is not a policy finding.

Rejected-attempt counts and relevant limitations are carried alongside the row but do not change the two proposition states.

### 9.3 Frozen qualification cases

I2 shall qualify at least the I0 cases:

| Case | Expected |
|---|---|
| P1 configured C->R + attributed upstream delta | configured established; observed usage |
| P2 configured C->R + no upstream delta + closed-world coverage | configured established; measured zero |
| N1 configured C->R + no upstream delta + insufficient coverage | configured established; usage unestablished |
| N2 consumer rejected by APISIX on R | no usage established from the rejected attempt; no access fact invented |
| N3 unattributed traffic | no consumer usage established |
| N4 configured C->R1 + observed usage on R2 | R1 is not marked used by R2 evidence; R2 remains its own row/fact |

Also required:

- same username on two gateway instances does not cross-join;
- environment mismatch does not cross-join;
- observation for unknown Route remains unresolved;
- conflicting route/operation mapping is explicit;
- conflicting target-Service mapping is explicit.

## 10. Snapshot and lifecycle

Accepted I2 state shall be deterministic and snapshot-visible under one conditional internal block:

~~~text
api_usage_v1
~~~

The block contains, in deterministic order:

- accepted measurement-window identity and coverage;
- attributed observed interactions;
- reconciliation outcomes needed by I3;
- configured-vs-observed qualification rows;
- evidence references and limitation codes.

It is absent when no accepted measurement source exists.

Measurement-source replay with byte-identical normalized inputs is a semantic no-op.

Removing a measurement-source registration removes only its I2-owned window/observation/qualification state. It does not remove I1 gateway configuration or API-contract carriers.

A rejected/partial measurement import removes nothing previously accepted.

## 11. Evidence and safety

Every observed/qualification claim shall remain evidence-resolvable internally.

I2 shall keep APISIX measurement evidence internal. It shall not widen public `SourceType`, evidence endpoints, NL/Cypher reachability or consumer-name exposure. I3 owns that decision.

Secrets and authorization headers are never Architecture Knowledge.

## 12. Implementation slices

Keep I2 small:

### I2.1 — Measurement contract and independent vectors
Freeze:

- measurement manifest and normalized fixture;
- observation ids/fields;
- mapping artifact shape;
- reconciliation outcome names;
- qualification truth table and independent expected vectors.

No production ingestion required.

### I2.2 — Measurement capture/replay
Implement:

- APISIX Prometheus capture;
- start/end settling and normalization;
- replay source/discoverer/adapter;
- measurement carriers and lifecycle;
- deterministic fixture/replay.

### I2.3 — Reconciliation
Implement:

- consumer/runtime and route/runtime joins;
- explicit route->Operation mapping plus exact unique fallback;
- `aip/service` / explicit target-Service mapping;
- `RESOLVED/UNRESOLVED/AMBIGUOUS/CONFLICT`;
- no similarity inference.

### I2.4 — Qualification and I3 handoff
Implement:

- bounded union row set;
- configured-access and usage statuses;
- coverage rule;
- `api_usage_v1`;
- P1/P2/N1-N4 and negative cases;
- I2 completion record and I2 -> I3 handoff.

## 13. Definition of Done

I2 is complete when:

- measurement capture/replay is deterministic and secret-safe;
- window/counter/coverage semantics match the I0 freeze;
- consumer and Route attribution are gateway/environment scoped;
- Route->Operation and gateway-target->Service reconciliation obey §7;
- ambiguous/conflicting/unresolved joins stay explicit;
- no similarity-only resolution exists;
- qualification uses the bounded union, not a Cartesian product;
- P1, P2 and N1-N4 pass against independently authored expected results;
- rejected and unattributed traffic cannot become usage;
- zero is emitted only under `SUFFICIENT_FOR_ZERO`;
- snapshot/replay/removal behavior is deterministic;
- I1 configuration behavior remains green;
- no I3 public API/schema decision is introduced;
- the I2 -> I3 handoff identifies the exact internal state I3 may project.

## 14. Needs a reviewed amendment if it changes

A reviewed amendment is required before changing:

- `apisix_http_status` as the measurement source;
- `response_source="upstream"` as the usage criterion;
- the operator-asserted environment rule;
- the no-restart/settled counter-delta window rule;
- the closed-world zero-coverage rule;
- consumer identity;
- the four reconciliation outcomes;
- the exact-only automatic Route->Operation fallback;
- the `aip/service` label key;
- the bounded qualification row universe;
- the configured/usage qualification vocabulary;
- the rule that observed-only usage is not a policy violation;
- the separation of the API-exposure chain from the application-Service target chain.
