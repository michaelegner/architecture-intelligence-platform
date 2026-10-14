# AIP v0.7.0 I3 — API-Aware Current-State Projection and Public Answer

**Status:** Proposed.  
**Governing:** [v0.7.0 parent specification](specification.md), [I1 → I2 handoff](i1-i2-handoff.md), [I2 specification](i2-consumer-attribution-and-configured-vs-observed-qualification.md), and the frozen [I2 → I3 handoff](i2-i3-handoff.md).  
**Purpose:** expose the v0.7 configured-consumer / observed-usage question as one deterministic Architecture Intelligence answer without changing I2 truth.

## 1. Exit outcome

I3 answers one bounded developer question:

> **For this API exposure or application Service, which consumers have configured access, which have independently observed usage in the selected environment/window, and what remains unresolved or unsupported?**

I3 is a **projection** increment. It does not ingest gateway data, recompute measurement deltas, reinterpret configured access, or introduce Intent/policy semantics.

The semantic path is:

~~~text
I2 qualified Current State
  -> bounded target selection
  -> question-specific projection
  -> ArchitectureIntelligenceService
  -> REST + negotiated MCP
  -> same-snapshot evidence drill-down
~~~

## 2. Frozen I2 input and authority

I2 is complete and the [I2 → I3 handoff](i2-i3-handoff.md) is the authority for the internal state I3 may project.

I3 reads the current stable snapshot only. Its primary input is the conditional `api_usage_v1` block:

| I2 section | I3 use |
|---|---|
| `windows` | exact gateway/environment/window identity, source identity and window validity context |
| `evidence` | internal measurement evidence available for sanitized public projection |
| `reconciliation_rule` | binds the reconciliation semantics used by the snapshot |
| `attributions` | resolved/unresolved consumer and Route attribution context |
| `route_operation` | Route → Operation → contract-version reconciliation |
| `target_service` | independent gateway-target → application-Service reconciliation |
| `qualification_rule` | binds the qualification semantics used by the snapshot |
| `coverage` | Route-level `SUFFICIENT_FOR_ZERO` / `UNKNOWN_COVERAGE` and limitation codes |
| `interactions` | attributed window-local upstream/rejected counts and internal evidence refs |
| `qualification_rows` | **primary public-row source**: bounded configured/observed consumer–Route pairs with both proposition states |

I3 also reads:

- `gateway_configuration_v1` for source-qualified consumer/Route data, configured-source evidence and configuration source revision;
- `api_contracts_v1` for contract/version context already associated by I2;
- the ordinary canonical `Operation` and application `Service` state already bound into the same snapshot.

The following I2 facts are frozen inputs, not I3 decisions:

- `CONFIGURED_ACCESS_ESTABLISHED` / `NO_MATCHING_CONFIGURED_ACCESS_FACT`;
- `OBSERVED_USAGE` / `MEASURED_ZERO` / `USAGE_UNESTABLISHED`;
- `SUFFICIENT_FOR_ZERO` / `UNKNOWN_COVERAGE`;
- `RESOLVED` / `UNRESOLVED` / `AMBIGUOUS` / `CONFLICT`;
- one current window per configured measurement source and at most one source per `(gateway_instance_id, environment)`;
- counts are omitted, not zero, when the window is invalid;
- reconciliation, coverage, interactions and qualification rows are derived snapshot state whose rule ids/versions are fingerprint-bound.

I3 SHALL project these results. It SHALL NOT recompute measurement deltas, consumer/Route joins, reconciliation, coverage or qualification in REST, MCP, serialization code or a second semantic engine.

## 3. Scope and non-goals

In scope:

- one public API-consumer-usage request/result contract;
- exact target selection;
- bounded deterministic row enumeration;
- resolved API/application associations where I2 established them;
- explicit unresolved/ambiguous/conflicting association state;
- configured-access and observed-usage propositions kept separate;
- same-snapshot sanitized evidence drill-down;
- ArchitectureIntelligenceService as the semantic owner;
- REST and negotiated MCP parity;
- independent public expected-answer vectors and I4 handoff.

Out of scope:

- API products, plans or subscriptions;
- authorization, compliance or approval judgments;
- API/business owner inference;
- business capability/domain inference;
- payload-field dependency inference;
- generic gateway analytics;
- generic graph/Cypher queries;
- historical usage trajectories;
- changing I2 coverage, identity or qualification rules;
- Intent or Current-State ↔ Intent assessment.

## 4. Public target and request

The public semantic operation is:

~~~text
get_api_consumer_usage
~~~

The request SHALL use a discriminated exact target:

~~~text
target.kind =
  APPLICATION_SERVICE
  | API_OPERATION
  | GATEWAY_ROUTE

target.id = exact canonical/source-qualified id
~~~

Exactly one target is required.

Why these three:

- `API_OPERATION` supports the primary coding-agent task: "I am changing this operation; who is related to it?"
- `APPLICATION_SERVICE` supports investigation from an application boundary.
- `GATEWAY_ROUTE` remains the source-native exposure anchor when API/application reconciliation is unresolved.

No display-name, path-similarity or host-name lookup is introduced.

Required context:

~~~text
gateway_instance_id
environment
window_start
window_end
~~~

The four values MUST exactly match one row in `api_usage_v1.windows`. This makes the request deliberately single-gateway and single-window: two gateway instances may legitimately use the same environment and window bounds, so environment/window alone is not a unique observation identity.

I3 does not silently substitute another gateway or window. I2 keeps no historical window series, so this selects current snapshot state rather than providing a time-travel query.

If no exact `api_usage_v1.windows` row exists, the semantic answer is `NOT_ANSWERED` with the new v0.7 public limitation code `MEASUREMENT_WINDOW_NOT_AVAILABLE`. This includes a configured gateway that currently has no accepted measurement source. I3 does **not** synthesize configured-only rows outside I2's qualified row universe.

Optional:

~~~text
consumer_id
limit
cursor
snapshot_id
~~~

`consumer_id` is an exact `GatewayConsumer.id` filter. It is not a username search.

`snapshot_id` is optional on the first page and REQUIRED by continuation and evidence drill-down. Supplying a stale or unavailable snapshot yields `NOT_ANSWERED` with the existing `SNAPSHOT_NOT_AVAILABLE` limitation; I3 never restarts transparently against latest state.

## 5. Target selection semantics

I3 selects rows only through I2-established associations.

### 5.1 GATEWAY_ROUTE

Select the exact Route directly. Its API/application associations may be resolved, unresolved, ambiguous or conflicting and remain visible as such.

### 5.2 API_OPERATION

Select only Routes whose I2 Route -> Operation reconciliation is `RESOLVED` to the requested Operation.

Unresolved, ambiguous or conflicting Routes are not silently attached to that Operation. The answer SHALL state that target selection is relative to resolved associations.

For an `API_OPERATION` target, `association_summary` SHALL count **all GatewayRoutes in the selected gateway/window scope** by their I2 Route → Operation outcome before target filtering:

~~~text
route_operation:
  resolved_to_target
  resolved_elsewhere
  unresolved
  ambiguous
  conflict
~~~

This summary is informational context only; non-resolved Routes are never attached to the requested Operation.

### 5.3 APPLICATION_SERVICE

Select only Routes whose independent gateway-target -> application-Service reconciliation is `RESOLVED` to the requested Service.

The API chain is independent. A Route may therefore be selected for the Service while its Operation/contract association remains unresolved, ambiguous or conflicting.

For an `APPLICATION_SERVICE` target, `association_summary.target_service` SHALL count all GatewayRoutes in the selected gateway/window scope as `resolved_to_target`, `resolved_elsewhere`, `unresolved`, `ambiguous` or `conflict` using the independent I2 target-Service outcome.

Resolving either chain never strengthens the other.

## 6. Public answer contract

I3 introduces a versioned `0.7` answer payload under the existing Architecture Intelligence envelope conventions.

Each answer SHALL contain:

~~~text
snapshot_id
model_revision
gateway_instance_id
environment
window:
  window_start
  window_end
  source_instance_id
  valid
  reasons[]
target
association_summary
selected_routes[]
configuration_sources[]
measurement_sources[]
rows[]
limitations[]
page
~~~

`window.valid` is true iff the matching I2 window has no `window_reasons`; `window.reasons` is the exact public-safe projection of those reasons.

`selected_routes[]` is emitted independently of `rows[]`. For every Route selected by the target it contains at least the Route id plus its I2 `coverage` and coverage limitations. Therefore `rows: []` never hides whether the window was invalid or whether a selected Route had `UNKNOWN_COVERAGE`.

### 6.1 Row

One row represents one entry from I2 `api_usage_v1.qualification_rows`, enriched only with same-snapshot reconciliation and source context.

It contains at least:

~~~text
consumer:
  id
  source_name

gateway_route:
  id
  gateway_instance_id

api:
  operation_id?
  contract_version_id?
  contract_id?
  reconciliation

application_service:
  service_id?
  reconciliation

configured_access:
  status

usage:
  status
  coverage
  upstream_request_count?
  rejected_attempt_count?
  interaction_id?

evidence_refs[]
limitations[]
~~~

The frozen status meanings come from I2 unchanged:

Configured access:

~~~text
CONFIGURED_ACCESS_ESTABLISHED
NO_MATCHING_CONFIGURED_ACCESS_FACT
~~~

Usage:

~~~text
OBSERVED_USAGE
MEASURED_ZERO
USAGE_UNESTABLISHED
~~~

Association reconciliation is presented using the I2 meanings:

~~~text
RESOLVED
UNRESOLVED
AMBIGUOUS
CONFLICT
~~~

I3 may rename those values only if the public mapping is one-to-one and independently tested. It MUST NOT collapse them to a boolean such as `mapped`.

### 6.2 Consumer exposure

APISIX Consumer `username` is a stable non-secret source identity under the frozen I0/I1 contract. I3 SHALL expose it as `consumer.source_name` because the product question is otherwise not usable.

It remains explicitly **source-qualified**, not a global application/person identity.

Credential ids, credential values, keys, tokens and authentication-plugin secrets are never public answer fields or evidence fields.

### 6.3 Counts

`upstream_request_count` and `rejected_attempt_count` are window-local I2 results, not analytics time series.

They are omitted when I2 could not establish a valid count, including an invalid window. Absence is not zero.

A rejected-attempt count never changes configured access or establishes usage.

## 7. Answer meaning and limitations

A public row means only what its fields state.

In particular:

~~~text
CONFIGURED_ACCESS_ESTABLISHED
  != approved
  != intended
  != subscription

OBSERVED_USAGE
  != approved usage
  != payload-field dependency

MEASURED_ZERO
  = measured zero only under I2 SUFFICIENT_FOR_ZERO coverage

USAGE_UNESTABLISHED
  != zero
  != non-use
~~~

`NO_MATCHING_CONFIGURED_ACCESS_FACT` is not denial or misconfiguration.

A resolved Route -> Operation association does not make the Route and Operation the same entity.

A resolved target Service association does not establish API ownership, business ownership or authorization boundary.

## 8. Bounded enumeration and continuation

Rows are ordered deterministically by:

~~~text
consumer.id
gateway_route.id
~~~

Default page size: **100** rows. Maximum: **200**.

If more rows exist, the answer is `PARTIAL` and contains an opaque cursor. The cursor SHALL bind to:

- schema/rule version;
- snapshot id;
- normalized target;
- gateway instance + environment/window;
- optional consumer filter;
- last fully emitted row key.

A cursor used with different inputs or a different snapshot is rejected. No row may silently disappear because of a page boundary.

Because the cursor is bound to the whole AIP snapshot, **any import that changes the snapshot — even an unrelated source — invalidates an in-flight cursor**. Continuation then returns `SNAPSHOT_NOT_AVAILABLE`; the client must restart the query explicitly. This is an accepted v0.7 limitation, not a promise of source-local pagination stability.

I3 does not create a Cartesian product. It projects I2's already bounded row universe only.

## 9. Evidence drill-down

The answer SHALL mint/return opaque public evidence refs from the same-snapshot I1/I2 internal evidence necessary to explain:

- configured-access establishment;
- measurement/window evidence;
- reconciliation statements used in the row;
- limitations that materially affect qualification.

Raw I1/I2 internal carrier ids are not automatically public evidence.

Public evidence refs SHALL be deterministic, opaque, snapshot-bound handles:

~~~text
api-evidence:<sha256(ld(
  snapshot_id,
  normalized_query_context_digest,
  evidence_kind,
  sorted internal supporting ids
))>
~~~

The public answer returns only the handle. It never exposes the internal supporting ids used to mint it.

For a query answer, the semantic projection builds the finite mapping `public_ref -> sanitized evidence projection` from the same snapshot inputs and normalized query context that produced the answer. The query-context digest binds target, gateway instance, environment, window and consumer filter, but not pagination position.

For evidence mode, the caller resubmits that same bounded query context. The service reacquires the requested exact snapshot, deterministically rebuilds the mapping for that context, and resolves only refs present in it. A forged ref, a ref from another snapshot, or a ref from another target/gateway/window/filter context is refused. No server-side ref history or direct graph-id lookup is introduced.

The same new public capability SHALL support a second exact mode:

~~~text
get_api_consumer_usage(
  mode = "evidence",
  snapshot_id,
  target,
  gateway_instance_id,
  environment,
  window_start,
  window_end,
  consumer_id?,
  evidence_refs[]
)
~~~

with **1–20** refs.

REST exposes the equivalent at:

~~~text
POST /api/api-consumer-usage/evidence
~~~

The resolver SHALL:

- require the exact answer `snapshot_id` and the same normalized query context used to mint the refs;
- return sanitized typed evidence only;
- preserve configuration vs measurement evidence distinction;
- expose source/product revision and bounded relevant facts;
- never return credentials, raw gateway plugin configs, arbitrary metric labels, raw graph records or Cypher;
- refuse refs not belonging to the supplied snapshot.

The existing generic `get_evidence` behavior remains unchanged in v0.7.

## 10. Semantic service, REST and MCP

ArchitectureIntelligenceService remains the sole public semantic owner.

Recommended internal shape:

~~~text
ArchitectureIntelligenceService.get_api_consumer_usage(request)
ArchitectureIntelligenceService.get_api_consumer_usage_evidence(request)
~~~

A dedicated API-aware projection/repository module MAY be introduced behind the service to avoid turning the service into a large inline branch. It remains read-only and is not a second semantic authority.

Public adapters:

| Surface | Contract |
|---|---|
| Service | `get_api_consumer_usage` + exact evidence resolver |
| REST | `POST /api/api-consumer-usage` |
| REST evidence | `POST /api/api-consumer-usage/evidence` |
| negotiated MCP | new read-only tool `get_api_consumer_usage` with discriminated `query` / `evidence` modes |

The REST endpoint is intentionally top-level rather than `/api/services/{id}/...` because the operation has three peer target kinds (`APPLICATION_SERVICE`, `API_OPERATION`, `GATEWAY_ROUTE`). Making Service the URL parent would incorrectly privilege one target kind and force artificial routes for the other two. The body carries the discriminated target; the sibling `/evidence` path follows the existing scoped-evidence pattern.

This adds one new MCP tool. Existing tools retain their existing meanings.

REST and MCP adapters perform parsing, validation and transport mapping only. For the same request/snapshot their normalized semantic payload SHALL be identical to the service result.

Malformed request shape is a transport validation error. Semantic refusals such as unknown target, unavailable exact window or stale snapshot remain typed Architecture Intelligence answers rather than transport-specific invented meanings.

## 11. Source and snapshot context

Every answer SHALL identify the source context actually used:

- applicable APISIX configuration source revision from `gateway_configuration_v1.source_evidence`;
- measurement `source_instance_id` and window identity from `api_usage_v1.windows`;
- measurement evidence identity from `api_usage_v1.evidence` / row evidence refs;
- reconciliation and qualification rule id/version;
- exact selected gateway instance and operator-asserted environment;
- snapshot id/model revision.

If configuration and measurement state cannot be related under the I2 handoff's rules, I3 returns no strengthened row and exposes the limitation.

A gateway/environment/window with no accepted I2 measurement window is `NOT_ANSWERED / MEASUREMENT_WINDOW_NOT_AVAILABLE`; configured-only projection is explicitly out of scope for v0.7.

I3 does not query historical snapshots. `snapshot_id` is a consistency fence, not a time-travel API.

## 12. Independent public expected answers

Before semantic implementation, I3 SHALL author public expected outputs independently of the new projection code.

At minimum:

| Case | Public expectation |
|---|---|
| configured + observed | configured established + observed usage |
| configured + measured zero | configured established + measured zero with sufficient coverage |
| configured + insufficient measurement | configured established + usage unestablished |
| observed-only | no matching configured fact + observed usage |
| rejected attempt only | no usage established from rejection |
| unresolved Route -> Operation | Route row remains; API association unresolved |
| conflicting target Service | application association conflict; no Service claim |
| exact Operation target | only Routes resolved to that Operation included |
| exact Service target | only Routes resolved independently to that Service included |
| unattributed traffic | no consumer row invented |
| empty rows + invalid window | rows empty, but top-level window reasons remain visible |
| selected Route + no pair rows | rows empty, but selected Route coverage remains visible |
| gateway with no measurement source | NOT_ANSWERED / MEASUREMENT_WINDOW_NOT_AVAILABLE |
| same env/window on two gateways | required gateway_instance_id selects exactly one |
| page boundary | stable cursor; no duplicate/lost row |
| unrelated import during paging | old cursor refused with SNAPSHOT_NOT_AVAILABLE |
| stale snapshot | SNAPSHOT_NOT_AVAILABLE refusal |
| evidence drill-down | deterministic same-snapshot public ref resolves to sanitized evidence |
| forged/cross-snapshot evidence ref | refused |
| credential canary | absent from every service/REST/MCP/evidence payload |

Expected outputs SHALL not be generated from AIP execution.

## 13. Implementation slices

Keep I3 small.

### I3.1 — Public contract freeze

Freeze:

- request/target schema;
- `0.7` response schema;
- consumer exposure decision;
- row/evidence shape;
- page/cursor rules;
- service/REST/MCP names;
- independently authored expected-answer vectors.

No semantic implementation required.

### I3.2 — Internal projection

Implement the same-snapshot bounded projection behind ArchitectureIntelligenceService directly from the frozen I2 handoff sections named in §2. `qualification_rows` is the row authority; I3 only performs target selection, bounded enumeration and public enrichment.

No public adapter reasoning.

### I3.3 — REST, MCP and evidence

Implement:

- REST query;
- negotiated MCP tool;
- exact same-snapshot evidence mode;
- schema/client parity;
- compatibility tests for existing tools/routes.

### I3.4 — Qualification and I4 handoff

Record:

- cross-surface deterministic results;
- bounds and observed read cost;
- known limitations;
- exact tested HEAD;
- I3 completion record;
- I3 -> I4 handoff with frozen public vectors.

## 14. Definition of Done

I3 is complete when:

- the frozen I2 handoff is consumed exactly as §2 states, with `qualification_rows` as the row authority and without duplicate I2 reasoning;
- an ordinary client can query by Operation, application Service or gateway Route for one exact gateway/window;
- an absent measurement window produces the typed `MEASUREMENT_WINDOW_NOT_AVAILABLE` refusal rather than configured-only synthesis;
- window validity and selected-Route coverage remain visible even when no qualification rows are returned;
- configured access and usage remain independent public propositions;
- unresolved/ambiguous/conflicting associations stay explicit;
- measured zero appears only when I2 established it;
- no unattributed traffic becomes a consumer row;
- consumer source names are exposed without any credentials;
- pagination is deterministic and snapshot-bound;
- every returned evidence ref resolves under the same snapshot or refuses explicitly;
- service, REST and negotiated MCP return equivalent semantic payloads;
- existing Architecture Intelligence tools retain their meanings;
- independent positive/negative expected outputs pass;
- no public write, generic graph query, Intent or policy judgment is introduced;
- the I4 handoff contains the exact schemas, vectors, routes/tool names, source/window fixture identity and known limitations.

## 15. Needs a reviewed amendment if it changes

A reviewed amendment is required before changing:

- the public question;
- the exact target kinds;
- exact gateway/environment/window matching and the no-measurement refusal;
- exposure of the source-qualified consumer name;
- configured-access or usage vocabulary/meaning;
- reconciliation meaning;
- measured-zero meaning;
- the rule that target selection uses only resolved I2 associations;
- page ordering or cursor snapshot binding;
- public evidence safety boundary and snapshot-bound evidence-ref derivation;
- REST path or MCP tool/mode contract after I3.1 freeze;
- the exact I2 section-to-I3 responsibility boundary in §2;
- the rule that I3 projects I2 truth rather than recomputing it.
