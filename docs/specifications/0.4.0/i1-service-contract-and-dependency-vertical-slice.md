# AIP v0.4.0 — I1 Service Contract and Dependency Vertical Slice

**Status:** Draft 1  
**Target release:** `v0.4.0`  
**Release increment:** I1  
**Target repository path:** `docs/specifications/0.4.0/i1-service-contract-and-dependency-vertical-slice.md`  
**Entry baseline:** `main` at `eeab319b0cea2d761cad395419e707d53ba33285`  
**Governing specification:** `docs/specifications/0.4.0/specification.md`, Draft 1.2 semantics  
**Primary outcome:** A direct call to `ArchitectureIntelligenceService` returns a deterministic,
qualified, evidence-linked and snapshot-bound answer for one service's direct dependencies.

---

## 1. Purpose

I1 establishes the semantic product boundary on which every `v0.4.0` tool will depend.

I1 SHALL prove this capability:

> **Given one known service and one explicit observation context, a caller can obtain its direct
> outgoing dependencies as structured claims whose destination, delivery path, qualification,
> evidence, producer build, snapshot and limitations are explicit and reproducible.**

I1 is not complete merely because data classes or JSON Schemas exist. The capability MUST execute
against the real Neo4j-backed AIP model through `ArchitectureIntelligenceService`, and its result
MUST be verified against independently authored expectations.

```text
direct caller
    -> ArchitectureIntelligenceService
    -> read-only repository
    -> existing canonical model and evidence
    -> ArchitectureAnswer<ServiceDependenciesData>
```

The service SHALL add no architectural fact that cannot be derived from the existing model and its
evidence.

---

## 2. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

The release specification governs whenever this document is silent. If the two specifications
conflict, implementation SHALL stop and resolve the conflict explicitly rather than silently
selecting one interpretation.

Executable JSON Schemas and independently authored I1 fixtures become the authoritative wire and
behavioral evidence when I1 exits.

---

## 3. Entry Conditions

I1 starts from the published and post-release-verified `v0.3.0` semantic core.

The following existing behavior is treated as frozen input:

- `CALLS` targets an `Operation`; a provider `Service` may be resolved through `PROVIDES`.
- `SENDS` targets a `Queue`; consumer services may be resolved through `RECEIVES_FROM`.
- `sync_depends_on` and `async_flow_to` are computed views and are not materialized relations.
- `CONFIRMED`, `OBSERVED_ONLY`, and `NOT_OBSERVED_IN_WINDOW` retain their existing runtime meaning.
- non-observation is never absence, obsolescence, dead code, or proof of non-use.
- unresolved identity is retained and reported rather than guessed.
- evidence is attached to canonical relations through `evidence_ids`.
- analysis sessions can already be opened with Neo4j `READ_ACCESS`.

I1 MUST NOT change these semantics merely to make the public service contract simpler.

---

## 4. Scope Budget

I1 has the following fixed budget:

| Area | I1 limit |
|---|---|
| Semantic entry point | One `ArchitectureIntelligenceService` |
| Implemented operation | `get_service_dependencies` only |
| Result family | One `ArchitectureAnswer<T>` family |
| Dependency depth | Exactly one hop |
| Public claim predicate | `DIRECT_DEPENDENCY` only |
| Delivery kinds | `SYNC_HTTP`, `ASYNC_MESSAGE` |
| Observation context | One explicit environment and inclusive time window |
| Snapshot model | Virtual current-state snapshot only |
| Historical persistence | None |
| Maximum dependency claims | 500 |
| Graph mutations by service call | Zero |
| LLM usage | Zero |
| MCP surface | None in I1 |

Any additional service operation, transport, analysis, discovery source or stored public model
relation requires explicit movement to a later increment.

---

## 5. In Scope

I1 SHALL deliver:

1. The `ArchitectureIntelligenceService` boundary.
2. Versioned executable schemas for `ArchitectureAnswer<T>` and dependency-specific payloads.
3. Stable producer identity including AIP version and immutable build revision.
4. Deterministic observation-context normalization and identity.
5. A content-addressed virtual current-state snapshot identity.
6. A read-only consistency fence protecting answers against concurrent graph writes.
7. Direct synchronous and asynchronous dependency projection.
8. Independent representation of destination and delivery path.
9. Existing declared/observed qualification on every returned dependency claim.
10. Evidence references for both dependency qualification and destination resolution.
11. Explicit partial, empty and safe-refusal behavior.
12. Deterministic service-level evaluation and Neo4j integration tests.

---

## 6. Explicit Non-Goals

I1 SHALL NOT implement:

```text
MCP server, MCP transport, tools/list or tools/call
get_evidence
get_architecture_drift
hero demo
fresh Quarkus or Airflow execution
new ingestion or discovery sources
new Canonical Model nodes or public relation families
materialized DEPENDS_ON relations
transitive dependency or blast-radius traversal
historical snapshots or snapshot diffing
persisted ObservationContext entities
generic graph or Cypher access
architecture mutation through the service
authentication, tenancy, workspace policy or audit platform
agent orchestration, prompting or LLM output
performance qualification for production-scale graphs
```

I1 MAY add narrowly scoped internal metadata needed to detect concurrent writes. Such metadata is
not a canonical architecture entity, not a public snapshot, and not queryable through the service.

---

## 7. Architecture Boundary

`ArchitectureIntelligenceService` SHALL be the only semantic entry point introduced by I1.

```text
future MCP adapter ──┐
future REST adapter ─┼──> ArchitectureIntelligenceService
I1 evaluator ────────┘                 |
                                      v
                         ArchitectureReadRepository
                                      |
                                      v
                                   Neo4j
```

The service SHALL own:

- request semantics;
- context and snapshot binding;
- dependency projection;
- claim construction;
- qualification and limitations;
- deterministic ordering;
- answer-envelope construction.

The repository SHALL own only read mechanics and raw graph projection. It MUST NOT return a public
`ArchitectureAnswer` or decide public outcome semantics.

No adapter or evaluator may bypass the service and query Neo4j directly for an architecture answer.

The service call MUST run through a session opened with Neo4j `READ_ACCESS`. It MUST NOT acquire a
write lock, mutate a temporary property, create metadata, or execute any write query.

---

## 8. Service Operation

The semantic operation is conceptually:

```python
ArchitectureIntelligenceService.get_service_dependencies(
    request: ServiceDependenciesRequest,
) -> ArchitectureAnswer[ServiceDependenciesData]
```

The public service method MUST NOT expose a Neo4j session, transaction, record, label, relationship
object or Cypher expression.

### 8.1 Request

```json
{
  "service_id": "service:order-service",
  "observation_context": {
    "environment": "demo",
    "window_start": "2026-08-26T00:00:00.000000Z",
    "window_end": "2026-08-27T00:00:00.000000Z"
  },
  "snapshot_id": null
}
```

Semantically required:

```text
service_id
observation_context.environment
observation_context.window_start
observation_context.window_end
```

Optional:

```text
snapshot_id
```

`service_id` MUST be a syntactically valid canonical service id, MUST start with `service:`, and
MUST contain at most 512 Unicode code points. A malformed id is input validation failure. A
well-formed id absent from the selected snapshot is `NOT_ANSWERED / UNKNOWN_ENTITY`.

The service request type MAY represent an absent or incomplete `observation_context` solely so the
semantic boundary can return the required `NOT_ANSWERED / OBSERVATION_CONTEXT_REQUIRED` result.
Malformed values inside a supplied context remain input-schema errors.

---

## 9. Answer Envelope

Every semantic result, including a safe refusal, SHALL use the same envelope:

```json
{
  "schema_version": "0.4",
  "producer": {
    "name": "architecture-intelligence-platform",
    "version": "0.4.0",
    "build_revision": "<immutable-source-revision>"
  },
  "tool": "get_service_dependencies",
  "outcome": "ANSWERED",
  "snapshot": {
    "snapshot_id": "aip:snapshot:v1:<sha256>",
    "model_revision": "sha256:<sha256>"
  },
  "observation_context": {
    "context_id": "aip:observation-context:v1:<sha256>",
    "environment": "demo",
    "window_start": "2026-08-26T00:00:00.000000Z",
    "window_end": "2026-08-27T00:00:00.000000Z"
  },
  "data": {
    "service": {
      "id": "service:order-service",
      "type": "SERVICE",
      "name": "OrderService"
    },
    "dependency_claim_ids": []
  },
  "claims": [],
  "evidence_refs": [],
  "limitations": []
}
```

Rules:

- all fields shown above are required, although `data` may be `null` for `NOT_ANSWERED` and
  `observation_context` is `null` only for `OBSERVATION_CONTEXT_REQUIRED`;
- `tool` SHALL be the stable semantic operation name even before an MCP adapter exists;
- `producer`, `snapshot` and normalized `observation_context` MUST also be present on safe refusals
  whenever a consistent current snapshot could be acquired;
- `evidence_refs` SHALL be the sorted, deduplicated union of every qualification and resolution
  evidence reference in `claims`;
- `limitations` SHALL contain only machine-classifiable limitations with deterministic text;
- no request id, invocation time, random value or generated prose may appear in the semantic answer.

---

## 10. Producer Identity

`producer` SHALL contain:

| Field | Rule |
|---|---|
| `name` | Fixed literal `architecture-intelligence-platform`. |
| `version` | Exact application/package version for the deployed artifact. |
| `build_revision` | Full immutable source revision used to build the artifact. |

All three values MUST remain identical for the lifetime of one deployed artifact. The I1 evaluator
MUST inject or otherwise freeze them explicitly; it MUST NOT derive them from the current time,
branch name or a mutable tag.

The production build mechanism MAY be finalized in I4, but I1 tests SHALL prove that missing or
placeholder build provenance cannot qualify a release artifact.

---

## 11. Entity and Delivery References

### 11.1 Entity Reference

```json
{
  "id": "service:product-service",
  "type": "SERVICE",
  "name": "ProductService"
}
```

Allowed `type` values in I1 are:

```text
SERVICE
OPERATION
QUEUE
```

An operation reference SHALL additionally carry `method` and `path` when those values exist in the
model. A queue reference SHALL additionally carry `protocol` and `namespace` when available.
Missing optional display metadata MUST NOT be guessed.

### 11.2 Delivery Reference

```json
{
  "kind": "SYNC_HTTP",
  "relation_type": "CALLS",
  "via": {
    "id": "operation:service:product-service:GET:/products/{id}",
    "type": "OPERATION",
    "name": "GET /products/{id}",
    "method": "GET",
    "path": "/products/{id}"
  }
}
```

Allowed pairs are fixed:

| `kind` | `relation_type` | `via.type` |
|---|---|---|
| `SYNC_HTTP` | `CALLS` | `OPERATION` |
| `ASYNC_MESSAGE` | `SENDS` | `QUEUE` |

`destination` and `delivery` are independent. A client MUST NOT parse an operation id, queue name,
protocol or path to infer the logical destination.

---

## 12. Dependency Claim

I1 adds one public result-claim predicate, not a stored graph relation:

```text
DIRECT_DEPENDENCY
```

A dependency claim SHALL have this shape:

```json
{
  "claim_id": "aip:claim:v1:<sha256>",
  "subject": {
    "id": "service:order-service",
    "type": "SERVICE",
    "name": "OrderService"
  },
  "predicate": "DIRECT_DEPENDENCY",
  "object": {
    "id": "service:product-service",
    "type": "SERVICE",
    "name": "ProductService"
  },
  "destination_resolution": "RESOLVED_SERVICE",
  "delivery": {
    "kind": "SYNC_HTTP",
    "relation_type": "CALLS",
    "via": {
      "id": "operation:service:product-service:GET:/products/{id}",
      "type": "OPERATION",
      "name": "GET /products/{id}",
      "method": "GET",
      "path": "/products/{id}"
    }
  },
  "qualification": "CONFIRMED",
  "coverage": null,
  "evidence_refs": ["evidence:declared:...", "evidence:observed:..."],
  "resolution_evidence_refs": ["evidence:provider:..."]
}
```

Allowed destination-resolution values are:

```text
RESOLVED_SERVICE
DIRECT_TARGET_FALLBACK
```

`evidence_refs` support the outgoing `CALLS` or `SENDS` fact and determine its qualification.
`resolution_evidence_refs` support only the mapping from the delivery target to the destination.
Resolution evidence MUST NOT silently upgrade the qualification of the outgoing fact.

### 12.1 Claim Identity

`claim_id` SHALL be:

```text
aip:claim:v1:sha256(canonical-json({
    subject_id,
    predicate,
    object_id,
    delivery_kind,
    delivery_via_id
}))
```

Qualification, evidence ids, snapshot id, display names and observation times MUST NOT be part of
claim identity. A material change to subject, destination or delivery path MUST produce a different
claim id.

---

## 13. Destination and Delivery Projection

### 13.1 Synchronous Path

Input pattern:

```text
(source:Service)-[calls:CALLS]->(operation:Operation)
(provider:Service)-[provides:PROVIDES]->(operation)
```

Rules:

1. The delivery target is always the directly identified `Operation`.
2. Exactly one provider supported by at least one evidence record resolves the destination to that
   `Service`.
3. No supported provider resolves the destination to the `Operation` itself with
   `DIRECT_TARGET_FALLBACK` and an `UNRESOLVED_IDENTITY` limitation.
4. More than one supported provider is ambiguous; the service MUST NOT choose one. It SHALL retain
   the `Operation` fallback and report `UNRESOLVED_IDENTITY`.
5. The implementation MUST NOT parse the operation id to manufacture a provider service.

### 13.2 Asynchronous Path

Input pattern:

```text
(source:Service)-[sends:SENDS]->(queue:Queue)
(consumer:Service)-[receives:RECEIVES_FROM]->(queue)
```

Rules:

1. The delivery target is always the directly identified `Queue`.
2. Every distinct consumer supported by evidence produces one dependency claim to that consumer.
3. Multiple consumers are valid fan-out and MUST NOT be treated as ambiguous identity.
4. No supported consumer resolves the destination to the `Queue` itself with
   `DIRECT_TARGET_FALLBACK` and an `UNRESOLVED_IDENTITY` limitation.
5. Queue name, namespace or protocol MUST NOT be interpreted as a service identity.

### 13.3 Path Preservation

The same destination reached through different operations or queues SHALL produce distinct claims.
The same destination reached through both synchronous and asynchronous delivery SHALL retain both
claims.

Deduplication is allowed only for rows with the same deterministic `claim_id`. When exact duplicate
rows carry different valid evidence references, their references SHALL be unioned and sorted.

This projection does not create or persist a `DIRECT_DEPENDENCY`, `SYNC_DEPENDS_ON`,
`ASYNC_FLOW_TO`, or `DEPENDS_ON` relationship.

---

## 14. Qualification

Qualification SHALL reuse the existing runtime evidence rules on the outgoing `CALLS` or `SENDS`
relation.

| Declared evidence | Matching observed evidence | Qualification |
|---|---|---|
| yes | yes | `CONFIRMED` |
| no | yes | `OBSERVED_ONLY` |
| yes | no | `NOT_OBSERVED_IN_WINDOW` |
| no | no | no supported dependency claim |

Matching observed evidence SHALL use the existing AIP environment/window semantics with the
normalized inclusive context. I1 MUST NOT redefine bucket or correlation semantics.

Additional rules:

- `CONFIRMED` claims MUST reference both declared and matching observed evidence.
- `OBSERVED_ONLY` claims MUST reference matching observed evidence.
- `NOT_OBSERVED_IN_WINDOW` claims MUST reference declared evidence and carry the existing coverage
  classification: `SUFFICIENT`, `PARTIAL`, `NONE`, or `UNKNOWN`.
- observed evidence outside the selected environment/window MUST NOT qualify or support the claim.
- resolution evidence is recorded separately and does not affect this table.
- an outgoing relation without any qualifying evidence MUST NOT become a claim.
- a missing required evidence record SHALL produce `INSUFFICIENT_EVIDENCE`, never an invented
  qualification.

The only accepted declared-only public literal in I1 is `NOT_OBSERVED_IN_WINDOW`.
`DECLARED_ONLY` MUST NOT appear as a second public synonym.

---

## 15. Evidence Requirements

Every returned claim MUST have at least one resolvable `evidence_refs` entry.

For a service-resolved destination, `resolution_evidence_refs` MUST contain the evidence supporting
the relevant `PROVIDES` or `RECEIVES_FROM` relation. If that evidence is unavailable, the logical
service destination is not safely established and the direct operation/queue fallback SHALL be
used.

Evidence references SHALL:

- use the existing opaque evidence ids unchanged;
- be deduplicated and sorted lexicographically;
- point to Evidence nodes included in the returned snapshot fingerprint;
- exclude observed evidence from another environment or outside the selected window when used for
  qualification;
- never expose raw secrets, authorization values or unsanitized payloads.

I1 does not implement evidence drill-down. I1 SHALL nevertheless prove that every emitted evidence
reference exists and is within the same stable snapshot. I2 will expose those records through
`get_evidence` without changing I1 claim semantics.

---

## 16. Observation Context

I1 SHALL introduce no persisted `ObservationContext` entity.

### 16.1 Validation

- `environment` is required, case-sensitive, 1..128 Unicode code points, contains no control
  characters, and MUST NOT contain leading or trailing whitespace.
- both timestamps are required RFC 3339 values with explicit offsets;
- timestamps are normalized to UTC;
- `window_start` MUST be less than or equal to `window_end`;
- the inclusive window MUST NOT exceed 31 days.

Equivalent offset representations of the same instants MUST normalize to the same context.

### 16.2 Canonical Representation

Returned timestamps SHALL use UTC with `Z` and exactly six fractional-second digits.

`context_id` SHALL be:

```text
aip:observation-context:v1:sha256(canonical-json({
    version: 1,
    environment,
    window_start_utc,
    window_end_utc
}))
```

The hash input SHALL use normalized values, sorted object keys and UTF-8 encoding.

There are no clock-derived defaults. Repeating a context means resubmitting the normalized fields,
not looking up `context_id` as a stored entity.

---

## 17. Virtual Snapshot Identity

A virtual snapshot identifies the complete current queryable canonical model-and-evidence state.
It is not a stored graph copy.

```text
model_revision = "sha256:" + sha256(canonical_state_bytes)
snapshot_id    = "aip:snapshot:v1:" + sha256(canonical_state_bytes)
```

The two fields intentionally carry the same digest with different public type prefixes.

The fingerprint SHALL be global, not scoped to the requested service. A change elsewhere in the
queryable architecture therefore produces a new current snapshot.

An omitted `snapshot_id` binds the answer to the stable current fingerprint. An explicit
`snapshot_id` MUST match that fingerprint. A mismatch returns
`NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE`; silent fallback is forbidden.

No invocation timestamp belongs to the snapshot or semantic answer.

---

## 18. Canonical Snapshot Projection

I1 SHALL define one explicit, versioned allowlist of fingerprint inputs. At minimum it includes all
fields that can affect any frozen `v0.4.0` answer:

```text
Service:   id, name, version
Operation: id, name where present, service_id, operation_id, method, path,
           request_schema_ids, response_schema_ids, discovery_status where present
Queue:     id, name, protocol, namespace, queue_type, discovery_status where present
Message:   id, name, version, schema_id
Schema:    id, name, version, format, canonical_hash
Evidence:  id, source_type, source_file, source_revision, evidence_type,
           environment, bucket_start, bucket_end, first_seen, last_seen,
           observation_count, sample_trace_ids, service_version, correlation_mode
Relation:  type, source_id, target_id, evidence_ids
Semantic configuration used by the answer: coverage qualification enabled/disabled
```

The projection MUST exclude:

```text
Neo4j element ids
record or insertion order
relationship key when derivable from type/source/target
reconciliation-only sources arrays
the internal consistency-fence revision
request ids and invocation timestamps
secrets and connection configuration
```

Canonicalization rules:

- JSON UTF-8 encoding;
- sorted object keys;
- no insignificant whitespace;
- node arrays sorted by `(type, id)`;
- relation arrays sorted by `(type, source_id, target_id)`;
- set-valued arrays sorted and deduplicated;
- timestamps normalized to the same UTC representation as §16;
- null and absent optional values normalized according to one executable schema rule;
- semantically identical state inserted in a different order produces identical bytes.

Changing the fingerprint allowlist or canonicalization version is a contract change and MUST be
recorded explicitly.

---

## 19. Concurrent-Write Consistency Fence

Neo4j's default read-committed isolation permits non-repeatable reads. A sequence of ordinary read
queries alone therefore does not prove that the fingerprint and dependency answer describe one
state.

I1 SHALL add one internal singleton, conceptually:

```text
(:AipInternalState {id: "architecture", revision: <monotonic integer>})
```

This node:

- is internal metadata, not part of the Canonical Model;
- is excluded from the snapshot fingerprint;
- stores no historical state or architecture fact;
- is never exposed in an answer;
- MUST be incremented atomically inside every transaction that mutates queryable canonical or
  evidence state.

The existing schema-initialization path SHALL create the singleton with revision `0` before the
new service is available. If the singleton is missing or invalid, a service read MUST fail safely;
it MUST NOT initialize or repair metadata through its read-only session.

The current write paths that MUST participate are:

1. declared import/pre-merge transactions in `app/graph/importer.py`;
2. service reconciliation/import transactions in `app/graph/importer.py`;
3. observation-batch persistence in `app/telemetry/aggregator.py`.

A rolled-back write MUST NOT advance the committed revision. A future graph writer MUST use the
same helper; adding a writer without the fence is a release blocker.

### 19.1 Stable Read Algorithm

For at most three attempts, the read repository SHALL:

1. read `revision_before`;
2. read the canonical snapshot projection;
3. read the raw dependency/evidence projection for the request;
4. read `revision_after`;
5. accept the read only when both revisions are equal;
6. otherwise discard every intermediate value and retry from step 1.

If three attempts cannot obtain a stable state, return
`NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE` with a deterministic limitation explaining that a
consistent current snapshot could not be acquired.

The dependency answer and snapshot hash MUST be constructed only from one accepted attempt.

This fence is deliberately narrower than serializable locking: reads remain read-only and writers
are not blocked for the duration of answer construction.

---

## 20. Deterministic Ordering and Serialization

Claims SHALL be ordered by:

```text
object.id
delivery.kind
delivery.via.id
claim_id
```

`data.dependency_claim_ids` SHALL contain the claim ids in exactly the same order as `claims`.

Evidence references and claim-targeted limitation ids SHALL be sorted and deduplicated.

For a fixed producer build, stable snapshot, normalized observation context and request, canonical
serialization of the entire answer MUST be byte-identical across repeated calls.

Pydantic/model construction order, Neo4j record order and Python set iteration MUST NOT influence
the result.

---

## 21. Outcomes, Limitations and Bounds

Allowed outcomes:

```text
ANSWERED
PARTIAL
NOT_ANSWERED
```

Allowed I1 limitation/refusal codes:

```text
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
UNKNOWN_ENTITY
OBSERVATION_CONTEXT_REQUIRED
SNAPSHOT_NOT_AVAILABLE
RESULT_LIMIT_EXCEEDED
```

Required behavior:

| Situation | Result |
|---|---|
| Known service, all returned destinations safely resolved | `ANSWERED` |
| Known service with zero applicable direct dependencies | `ANSWERED`, empty claims |
| At least one safe claim plus unresolved/insufficient paths | `PARTIAL` |
| All candidate paths lack required evidence | `NOT_ANSWERED / INSUFFICIENT_EVIDENCE` |
| Well-formed unknown service id | `NOT_ANSWERED / UNKNOWN_ENTITY` |
| Missing/incomplete context | `NOT_ANSWERED / OBSERVATION_CONTEXT_REQUIRED`; `observation_context` is `null` |
| Explicit snapshot differs from stable current state | `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE` |
| Stable current state cannot be acquired after three attempts | `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE` |
| More than 500 unique claims would be returned | `NOT_ANSWERED / RESULT_LIMIT_EXCEEDED` |

The result limit MUST NOT silently truncate claims. The count may be reported, but no partial
architecture answer may masquerade as complete.

Malformed ids, timestamps and supplied context values are input-schema errors, not architecture
limitations. Absence of the semantically required context is the deliberate safe-refusal case above.

---

## 22. Reference Processing Flow

```text
validate request
    -> normalize observation context
    -> acquire stable raw read using revision fence
    -> canonicalize and hash full queryable state
    -> reject mismatching explicit snapshot
    -> verify source service exists
    -> project CALLS and SENDS delivery paths
    -> resolve service destinations without parsing ids
    -> qualify outgoing facts from existing evidence semantics
    -> attach qualification and resolution evidence separately
    -> create deterministic claim ids
    -> apply result bound
    -> sort and deduplicate
    -> construct ArchitectureAnswer
    -> validate against executable schema
    -> canonical serialize for evaluation
```

No step may call an LLM or generate an additional architecture assertion.

---

## 23. Required Evaluation Scenarios

Expected answers SHALL be independently authored before comparing them with implementation output.

At minimum, the I1 suite SHALL include:

### Contract and Context

1. valid answer conforms to the versioned schema;
2. all safe-refusal answers conform to the same envelope family;
3. producer version/build revision are present and stable;
4. equivalent timestamp offsets yield one normalized context and identical `context_id`;
5. environment remains case-sensitive;
6. missing timezone, reversed window, excessive window and whitespace-invalid environment fail;
7. no request-time field affects semantic bytes.

### Snapshot

8. identical state inserted in different orders yields the same fingerprint;
9. a queryable node property change changes the fingerprint;
10. relation or evidence change changes the fingerprint;
11. reconciliation-only/internal metadata changes do not change the fingerprint;
12. an omitted snapshot binds successfully;
13. a matching explicit snapshot repeats the answer;
14. a stale explicit snapshot is refused without fallback;
15. importer and telemetry writes increment the internal revision in the same transaction;
16. rollback does not expose a committed increment;
17. an injected concurrent write forces retry and discards the mixed attempt;
18. repeated instability fails safely after the fixed retry count.

### Synchronous Dependencies

19. one `CALLS` plus one evidenced `PROVIDES` resolves a service destination;
20. an operation without a provider remains an operation with `UNRESOLVED_IDENTITY`;
21. multiple providers are not guessed;
22. two operations to one service remain two delivery claims;
23. destination resolution evidence is separate from qualification evidence.

### Asynchronous Dependencies

24. one sender/one consumer resolves a service destination through a queue;
25. one queue with two consumers yields two claims;
26. a queue without a consumer remains a queue with `UNRESOLVED_IDENTITY`;
27. queue name, namespace and protocol are never parsed into service identity;
28. sync and async paths to the same service both survive.

### Qualification and Evidence

29. declared plus matching observed yields `CONFIRMED` with both evidence classes;
30. matching observed only yields `OBSERVED_ONLY`;
31. declared without matching observation yields `NOT_OBSERVED_IN_WINDOW` with coverage;
32. observation from another environment/window does not qualify the claim;
33. missing evidence cannot create a claim;
34. every returned evidence id exists in the accepted snapshot;
35. evidence unions and ordering are deterministic.

### Outcome and Bounds

36. unknown service is distinguished from a valid empty service;
37. mixed resolved and unresolved paths produce `PARTIAL`;
38. more than 500 claims fails without truncation;
39. canonical output from two consecutive identical calls is byte-identical.

The bundled examples SHALL include at least the following semantic anchors:

```text
order-service -> product-service via HTTP
order-service -> payment-q via messaging
one observed-only HTTP operation
one unresolved operation or queue destination
one destination reached through more than one delivery path
```

---

## 24. Test Levels

### Unit

- schema models and enums;
- context validation/normalization/hash;
- claim-id construction;
- canonical state serialization and hashing;
- projection, qualification, sorting, deduplication and outcome rules;
- producer identity validation.

### Neo4j Integration

- real canonical/evidence graph reads;
- sync and async destination resolution;
- read-session enforcement;
- importer and telemetry revision-fence participation;
- stale snapshot and concurrent-write retry behavior;
- existing example topology.

### Deterministic Evaluation

- independently authored request and expected semantic answer;
- exact claims, qualifications, evidence references, snapshot/context identity and limitations;
- two identical consecutive runs;
- missing and unexpected claims fail the evaluation.

All existing unit, integration, evaluation, lint and security checks MUST remain green.

---

## 25. Delivery Sequence

### I1.1 — Contract Freeze

Deliver:

```text
ArchitectureAnswer<T> models and JSON Schema
producer/snapshot/context/entity/delivery/claim/limitation types
canonical serialization rules
independently authored contract fixtures
```

Exit:

> The dependency answer and safe-refusal shapes are executable, versioned and unambiguous.

### I1.2 — Stable Context and Snapshot

Deliver:

```text
observation-context normalization and context_id
canonical state projection and fingerprint
internal monotonic revision fence
write-path participation
bounded stable-read retry
```

Exit:

> A read-only caller obtains one content-addressed state or fails honestly under concurrent change.

### I1.3 — Dependency Projection

Deliver:

```text
ArchitectureIntelligenceService
read repository
sync and async destination/delivery projection
qualification and evidence linkage
safe outcomes, bounds and deterministic ordering
```

Exit:

> A direct service call returns the complete bounded direct-dependency answer without graph knowledge.

### I1.4 — Qualification

Deliver:

```text
Neo4j integration coverage
independently authored deterministic evaluation
two identical runs
full regression suite
I1 result record
```

Exit:

> I1's complete capability is proven and ready for the I2 MCP adapter.

---

## 26. Required Artifacts

I1 SHALL produce only:

```text
this I1 specification
versioned answer/dependency JSON Schemas
service and repository implementation
independently authored fixtures
unit and integration tests
machine-readable deterministic evaluation result
one concise I1 completion record
```

I1 SHALL NOT produce separate design dossiers, an MCP guide, hero-demo documentation, duplicated
test reports, or release notes.

---

## 27. Release Blockers

Any of the following blocks I1 completion:

### Contract

```text
producer build revision is missing or mutable
answer does not conform to the executable schema
qualification or limitation can be omitted
request-time values affect deterministic semantic output
public answer leaks Neo4j labels, records, element ids or Cypher
```

### Semantic Integrity

```text
destination is inferred by parsing an operation id or queue name
multiple delivery paths are collapsed
unresolved identity is guessed
resolution evidence changes outgoing-fact qualification
claim lacks resolvable qualification evidence
non-observation is represented as absence or obsolescence
new canonical dependency relation is persisted
```

### Snapshot Integrity

```text
fingerprint omits a field that can change a v0.4 answer
fingerprint depends on insertion or query order
snapshot and answer can observe different committed states
one current graph writer does not participate in the revision fence
explicit stale snapshot silently receives current data
read-only service performs any graph write or lock mutation
```

### Evaluation and Scope

```text
expected output is generated from AIP output
missing or unexpected claim is not detected
two identical calls differ semantically
existing CI, tests, CodeQL or dependency checks fail
MCP, drift, hero demo, new discovery or transitive analysis enters I1
```

Targets:

```text
Incorrect supported dependency claims = 0
Unexpected dependency claims = 0
Broken evidence references = 0
Mixed-state accepted answers = 0
Write operations from service calls = 0
I1 blockers = 0
```

---

## 28. Definition of Done

### Boundary and Contract

- [ ] `ArchitectureIntelligenceService` is the only new semantic entry point.
- [ ] Only `get_service_dependencies` is implemented.
- [ ] The versioned schema freezes every required envelope and dependency field.
- [ ] Every answer identifies the AIP version and immutable build revision.
- [ ] No graph-specific internal type crosses the service boundary.

### Context and Snapshot

- [ ] Observation context is explicit, bounded, normalized and deterministically identified.
- [ ] Snapshot identity is a deterministic content hash of the allowlisted queryable state.
- [ ] The internal revision fence is updated by every current graph writer.
- [ ] Concurrent writes cannot produce an accepted mixed-state answer.
- [ ] Matching explicit snapshots repeat; stale snapshots fail without fallback.
- [ ] No snapshot history or persisted ObservationContext was added.

### Dependency Semantics

- [ ] Only direct outgoing dependencies are returned.
- [ ] Destination and delivery are independent fields.
- [ ] Sync and async service destinations are resolved only from canonical evidenced relations.
- [ ] Unresolved operations/queues are retained without guessing.
- [ ] Multiple operations, queues, consumers and delivery kinds are preserved deterministically.
- [ ] No derived dependency relation is materialized.

### Qualification and Evidence

- [ ] Every claim uses exactly one accepted qualification.
- [ ] `NOT_OBSERVED_IN_WINDOW` remains distinct from absence.
- [ ] Qualification evidence and destination-resolution evidence are separate.
- [ ] Every referenced evidence id exists in the accepted snapshot.
- [ ] Missing evidence produces a limitation or safe refusal, never a fabricated claim.

### Determinism and Quality

- [ ] Result bounds fail explicitly and never silently truncate.
- [ ] Independently authored positive, empty, partial, unresolved, insufficient, unknown and stale
      scenarios pass.
- [ ] Two consecutive canonical answers for fixed inputs are byte-identical.
- [ ] Existing tests and deterministic architecture evaluation remain green.
- [ ] CI, lint, CodeQL and dependency checks pass on the exact I1 candidate.
- [ ] I1 blockers equal zero.

---

## 29. Exit Statement

I1 SHALL exit with exactly one of:

```text
GO — At <exact candidate SHA>, a direct ArchitectureIntelligenceService call returns
a deterministic, evidence-qualified, snapshot-bound answer for one service's bounded
direct dependencies, with destination separated from delivery and zero graph writes.
```

or:

```text
NO-GO — The dependency vertical slice is not proven because <named blocker>;
return to <I1 subsection>.
```

“Models added,” “schema generated,” or “query works” is not a valid GO statement.

---

## 30. Handoff to I2

I2 may begin only after I1 GO.

I2 SHALL reuse without semantic reinterpretation:

```text
ArchitectureIntelligenceService.get_service_dependencies
ArchitectureAnswer<T>
producer identity
snapshot identity and stale-snapshot behavior
observation-context normalization
dependency claim and limitation vocabulary
canonical serialization
```

I2 will add the Streamable HTTP MCP adapter and `get_evidence`. It MUST NOT duplicate I1 graph
queries, qualification logic or claim construction inside the adapter.

---

## References

- AIP `v0.4.0` release specification: `docs/specifications/0.4.0/specification.md`
- AIP dependency computed views: `app/analysis/dependencies.py`
- AIP runtime qualification: `app/analysis/runtime.py`
- AIP canonical model: `app/canonical/model.py`
- AIP evidence model: `app/provenance/model.py`
- AIP graph write paths: `app/graph/importer.py`, `app/telemetry/aggregator.py`
- AIP read-session boundary: `app/graph/repository.py`, `app/deps.py`
- Neo4j concurrent data access and read-committed isolation:
  <https://neo4j.com/docs/operations-manual/current/database-internals/concurrent-data-access/>
