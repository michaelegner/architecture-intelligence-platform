# AIP v0.7.0 I3 — API-Aware Current-State Projection and Public Answer

**Status:** Proposed.  
**Governing:** [v0.7.0 parent specification](specification.md), [I1 → I2 handoff](i1-i2-handoff.md), [I2 specification](i2-consumer-attribution-and-configured-vs-observed-qualification.md), and the reviewed I2 → I3 handoff once I2 closes.  
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

## 2. Entry gate and authority

I3 implementation SHALL start only after I2 freezes an I2 → I3 handoff naming the exact internal state and snapshot fields I3 may read.

The handoff must provide, at minimum:

- the accepted measurement window identity, environment and exact window;
- qualified consumer/Route rows with configured-access status, usage status, coverage, counts and limitations;
- Route -> Operation/contract reconciliation outcome;
- gateway-target -> application-Service reconciliation outcome;
- source revision/evidence references required to substantiate the row;
- deterministic ordering and lifecycle semantics under `api_usage_v1`.

Until that handoff exists, this specification freezes the **public meaning**, not an assumed internal carrier layout.

I3 SHALL NOT re-run I2 reconciliation or qualification in REST, MCP, serialization code, or a second semantic engine.

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
environment
window_start
window_end
~~~

The environment/window MUST exactly identify an accepted current I2 measurement window. I3 does not silently substitute the newest window.

Optional:

~~~text
consumer_id
limit
cursor
snapshot_id
~~~

`consumer_id` is an exact `GatewayConsumer.id` filter. It is not a username search.

`snapshot_id` is optional on the first page and REQUIRED by continuation and evidence drill-down. Supplying a stale snapshot yields a typed `SNAPSHOT_NOT_AVAILABLE` / stale-snapshot refusal; I3 never restarts transparently against latest state.

## 5. Target selection semantics

I3 selects rows only through I2-established associations.

### 5.1 GATEWAY_ROUTE

Select the exact Route directly. Its API/application associations may be resolved, unresolved, ambiguous or conflicting and remain visible as such.

### 5.2 API_OPERATION

Select only Routes whose I2 Route -> Operation reconciliation is `RESOLVED` to the requested Operation.

Unresolved, ambiguous or conflicting Routes are not silently attached to that Operation. The answer SHALL state that target selection is relative to resolved associations and SHALL report aggregate unresolved-association counts for the same evaluated gateway/window where available from the I2 handoff.

### 5.3 APPLICATION_SERVICE

Select only Routes whose independent gateway-target -> application-Service reconciliation is `RESOLVED` to the requested Service.

The API chain is independent. A Route may therefore be selected for the Service while its Operation/contract association remains unresolved, ambiguous or conflicting.

Resolving either chain never strengthens the other.

## 6. Public answer contract

I3 introduces a versioned `0.7` answer payload under the existing Architecture Intelligence envelope conventions.

Each answer SHALL contain:

~~~text
snapshot_id
model_revision
environment
window_start
window_end
target
configuration_sources[]
measurement_sources[]
rows[]
limitations[]
page
~~~

### 6.1 Row

One row represents one I2 qualified `GatewayConsumer / GatewayRoute` pair.

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

They are null when I2 could not establish a valid count. Null is not zero.

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
- environment/window;
- optional consumer filter;
- last fully emitted row key.

A cursor used with different inputs or a different snapshot is rejected. No row may silently disappear because of a page boundary.

I3 does not create a Cartesian product. It projects I2's already bounded row universe only.

## 9. Evidence drill-down

The answer SHALL return opaque public evidence refs sufficient to explain:

- configured-access establishment;
- measurement/window evidence;
- reconciliation statements used in the row;
- limitations that materially affect qualification.

Raw I1/I2 internal carrier ids are not automatically public evidence.

The same new public capability SHALL support a second exact mode:

~~~text
get_api_consumer_usage(mode = "evidence", snapshot_id, evidence_refs[])
~~~

with **1–20** refs.

REST exposes the equivalent at:

~~~text
POST /api/api-consumer-usage/evidence
~~~

The resolver SHALL:

- require the exact answer `snapshot_id`;
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

This adds one new MCP tool. Existing tools retain their existing meanings.

REST and MCP adapters perform parsing, validation and transport mapping only. For the same request/snapshot their normalized semantic payload SHALL be identical to the service result.

Malformed request shape is a transport validation error. Semantic refusals such as unknown target, unavailable exact window or stale snapshot remain typed Architecture Intelligence answers rather than transport-specific invented meanings.

## 11. Source and snapshot context

Every answer SHALL identify the source context actually used:

- applicable APISIX configuration source revision;
- measurement source/window identity;
- gateway instance and environment;
- snapshot id/model revision.

If configuration and measurement state cannot be related under the I2 handoff's rules, I3 returns no strengthened row and exposes the limitation.

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
| page boundary | stable cursor; no duplicate/lost row |
| stale snapshot | explicit refusal |
| evidence drill-down | same-snapshot sanitized evidence |
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

Implement the same-snapshot bounded projection behind ArchitectureIntelligenceService using the exact I2 handoff.

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

- the exact I2 handoff is frozen and consumed without duplicate qualification logic;
- an ordinary client can query by Operation, application Service or gateway Route;
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
- exact environment/window matching;
- exposure of the source-qualified consumer name;
- configured-access or usage vocabulary/meaning;
- reconciliation meaning;
- measured-zero meaning;
- the rule that target selection uses only resolved I2 associations;
- page ordering or cursor snapshot binding;
- public evidence safety boundary;
- REST path or MCP tool/mode contract after I3.1 freeze;
- the rule that I3 projects I2 truth rather than recomputing it.
