# AIP v0.5.0 I1 — Source Ingestion Foundation

**Status:** Draft 0.2  
**Release:** `v0.5.0`  
**Increment:** I1  
**Parent specification:** [`specification.md`](specification.md)

## 1. Purpose

I1 introduces the source-adapter seam and migrates the existing OpenAPI, AsyncAPI, Architecture
Manifest, and filesystem ingestion paths to it. It expands OpenAPI/AsyncAPI fidelity while
preserving canonical meaning, provenance, deterministic replay, atomicity, and source-owned
expiration.

The governing invariant is:

> **A source may change what is observed, but no import may guess what the evidence does not support.**

I1 does not add Kubernetes or Pub/Sub semantics; it provides the ingestion foundation consumed by
those later increments.

## 2. Baseline and invariants

The baseline is the published and post-release-verified `v0.4.2` ingestion behavior. Existing
qualified fixtures retain their canonical meaning through explicit, versioned migration mappings.
Unchanged legacy inputs with authoritative Service identity but without legacy entity/destination
mappings may become `ACCEPTED_WITH_LIMITATIONS` where v0.4.2 derived shared identity or Queue
identity from names alone. An AsyncAPI source with channels but no supported Queue relation is
`REJECTED_UNSUPPORTED`, as specified in §9.1. Without authoritative Service identity, sources are
also `REJECTED_UNSUPPORTED`.
These safety corrections SHALL be recorded and qualified as intentional migration, never hidden as
backward-compatible parsing.

The following remain mandatory:

```text
non-observation != absence
unresolved identity > guessed identity
unsupported > falsely supported
one source != one service
one service != one source
```

## 3. Scope

I1 delivers:

- `SourceDescriptor`, `SourceInstanceId`, `DiscoveryScopeId`, and source inventory records;
- a registry-based adapter/discoverer seam;
- source-scoped atomic reconciliation and lifecycle diagnostics;
- deterministic source identity, revision, capture, and semantic-input hashing;
- OpenAPI 3.0/3.1 validation and bounded local reference expansion;
- bounded AsyncAPI validation and local reference expansion;
- migration of existing adapters without a parallel hard-coded path;
- deterministic qualification and evidence for all behavior above.

I1 does not deliver Kubernetes resource mapping, live broker discovery, Topic/Subscription
semantics, gRPC/protobuf, Kafka Connect, remote references, third-party adapter loading, or new
MCP/public tools.

## 4. Source model

The implementation SHALL provide concepts equivalent to:

```text
SourceDescriptor
SourceInstanceId
DiscoveryScopeId
SourceInventorySnapshot
LoadedSource
SourceAdapter
SourceAdapterRegistry
SourceDiscoverer
IngestionResult
IngestionDiagnostic
ReconciliationPlan
```

`SourceDescriptor` SHALL include:

```text
source_instance_id
source_kind
locator
discovery_scope_id
scope_definition_digest
source_inventory_snapshot_ref
declared/provider revision, where available
content_sha256
dependency_closure_digest, where applicable
semantic_input_digest
mapping_context_digest
declared/configured service identity, where available
document dialect/version
adapter identity
mapping-rule identity and version
```

Adapters return normalized claims, evidence, diagnostics, and lifecycle inputs. Adapters MUST NOT
write directly to the graph or call another adapter's mapping logic.

### 4.1 Canonical Service identity

Every OpenAPI or AsyncAPI claim SHALL resolve to exactly one authoritative canonical Service ID
before any Service-owned Operation, Schema, Message, Queue relation, or owner key is emitted.

The accepted Service-ID grammar is:

```text
service:<service-segment>
service:<namespace-segment>:<service-segment>

segment = [a-z0-9][a-z0-9._-]*
```

No whitespace, empty segment, additional colon, case folding, or implicit slug conversion is
allowed. I1 accepts exactly these resolution paths:

```text
1. root or construct extension
   x-aip-service-id = <full canonical Service ID>

2. versioned configured source-to-Service mapping
   (SourceInstanceId, exact source pointer or pointer prefix) -> <full canonical Service ID>

3. authoritative Architecture Manifest source binding
   (SourceInstanceId, exact source pointer or pointer prefix) -> <full canonical Service ID>
```

A root binding applies to the complete document. A construct binding applies only below its decoded
RFC 6901 pointer prefix. When multiple bindings apply to one construct, all MUST resolve to the same
Service ID; no precedence suppresses disagreement. Every configured or manifest binding carries
attribution, revision, content digest, and mapping-rule version.

```text
all applicable paths agree
  -> RESOLVED; union identity evidence

missing identity for any emitted construct
  -> REJECTED_UNSUPPORTED + SERVICE_IDENTITY_UNRESOLVED
  -> emit no canonical entity/relation from that source

multiple applicable identities disagree
  -> REJECTED_CONFLICT + SERVICE_IDENTITY_CONFLICT
  -> emit nothing from the discovery run

malformed x-aip-service-id or mapping target
  -> REJECTED_INVALID + SERVICE_IDENTITY_INVALID
```

`info.title`, service name, `operationId`, directory name, filename, source path, and content
similarity are display/discovery evidence only and MUST NOT establish Service identity.

### 4.2 Architecture Manifest binding format and evaluation order

The authoritative Architecture Manifest binding format is a YAML/JSON document with this exact
shape (additional fields are rejected):

```yaml
apiVersion: aip.dev/v1
kind: ArchitectureIdentityBindings
metadata:
  id: <non-empty stable manifest id>
  revision: <non-empty manifest revision>
bindings:
  - sourceInstanceId: <full SourceInstanceId>
    pointerPrefix: <RFC 6901 JSON Pointer, empty string means document root>
    serviceId: <full canonical Service ID>
```

`sourceInstanceId` MUST refer to a source present in the same completed inventory. `pointerPrefix`
is parsed into decoded RFC 6901 tokens; matching compares complete token sequences, not raw string
prefixes. Thus `/paths/~1foo` matches a descendant of the `/paths/~1foo` node but never
`/paths/~1foobar`. Duplicate bindings for the same source and token prefix are invalid unless their
Service IDs are identical; overlapping prefixes with different Service IDs are
`SERVICE_IDENTITY_CONFLICT`.

Identity evaluation is two-phase:

```text
phase 1: discover every source and binding manifest
  -> validate manifest shape, revision, IDs, pointers, and target SourceInstanceIds
  -> collect and canonicalize one binding index
  -> reject unresolved/duplicate/conflicting bindings

phase 2: map OpenAPI/AsyncAPI documents
  -> resolve each construct from the complete binding index plus extensions/configured mappings
  -> map in canonical SourceInstanceId order
```

No OpenAPI/AsyncAPI adapter may map a document before phase 1 completes. Binding manifests,
documents, and their source inventory are sorted by canonical IDs before evaluation. Permuting source
discovery order MUST produce the same binding index, diagnostics, semantic report, and graph result.
The manifest itself is evidence with its locator, revision, content digest, and mapping-rule version.

## 5. Stable identity and replay

### 5.1 Source identity

`SourceInstanceId` is the stable logical owner of claims. It MUST remain stable across content
changes, revisions, checkout locations, and equivalent replays. It MUST NOT derive from content
hash, service identity, absolute path, temporary checkout, or Kubernetes `resourceVersion`.

```text
source_instance_id = urn:aip:source:<source-kind>:<sha256(stable-source-key)>

filesystem stable-source-key
  = configured filesystem-source id
    + source kind
    + normalized POSIX root-document path relative to configured source root

Kubernetes stable-source-key (reserved for I2)
  = configured Kubernetes-source id + immutable cluster UID
```

The concatenation used for every identity hash SHALL be length-delimited or otherwise
unambiguously encoded, and SHA-256 output SHALL be lowercase hexadecimal.

### 5.1.1 Portable bundled-example identities

The v0.5.0 migration configuration for repository-owned examples SHALL use these fixed logical
identities:

```text
configured filesystem-source id = aip-bundled-examples-v0.5
configured discovery-scope id    = aip-bundled-examples-v0.5
stable target identity           = urn:aip:logical-root:bundled-examples
configured physical source root  = examples/
migration mapping artifact id    = aip-v0.5.0-bundled-example-identities-v1
required repository path         = config/migrations/v0.5.0-bundled-example-identities.yaml
```

Only the physical `examples/` root participates in `scope_definition_digest`; it does not
participate in `DiscoveryScopeId`. Each bundled source's `SourceInstanceId` is derived from the fixed
filesystem-source ID, source kind, and normalized root-document path relative to `examples/`.

The migration artifact SHALL bind those portable SourceInstanceIds and exact source pointers to the
authoritative Service IDs and prior qualified Schema, Message, and Queue IDs. A clean checkout in a
different absolute directory MUST derive the same scope/source identities and apply the same
mappings. Missing or modified migration configuration is diagnosed and MUST NOT fall back to a
directory slug or name-derived identity.

### 5.2 Revision and capture identity

Every successful load SHALL record:

```text
source_revision_id
source_capture_id
declared/provider revision, where available
semantic_input_digest
mapping_context_digest
content_sha256
dependency_closure_digest, where applicable
capture time
```

```text
source_revision_id
  = urn:aip:source-revision:<sha256(length-delimited(
      SourceInstanceId, mapping-rule version, semantic_input_digest))>

source_capture_id
  = urn:aip:source-capture:<sha256(length-delimited(
      source_revision_id, normalized declared/provider revision))>
```

Without an independent provider revision, `source_capture_id` equals `source_revision_id`. A
provider revision MUST NOT create a new semantic graph revision when normalized input is unchanged.

### 5.3 Semantic normalization

The semantic input digest SHALL hash a versioned source-kind projection:

- YAML/JSON object keys are canonically ordered;
- comments, formatting, and absolute paths are excluded;
- OpenAPI/AsyncAPI roots and bounded local reference closures are ordered by normalized relative
  path;
- volatile metadata excluded by the adapter contract is removed;
- normalization-rule changes are mapping-rule changes and require new golden tests.

Equivalent documents under the same mapping context MUST produce equivalent semantic input digests
and canonical results.

The normalized document/reference projection alone is insufficient for replay. I1 SHALL compute
one common `mapping_context_digest` per discovery run after phase 1 validation. Its input is the
complete canonical index of configured and manifest Service bindings, shared Schema/Message
mappings, Queue/destination and broker/server/namespace mappings, bundled migration mappings, and
all active adapter, normalization, and mapping-rule identities/versions. Each mapping entry retains
its stable artifact identity, revision, content digest, attribution, normalized source pointers,
targets, and semantic options. Capture times and physical checkout paths are excluded.

Canonicalize the context as RFC 8785 JSON; sort unordered entry arrays by their complete canonical
JSON bytes before hashing. Explicit empty arrays represent absent mapping categories. The context
digest is lowercase hexadecimal SHA-256 of those bytes. No fine-grained dependency index is required.

```text
semantic_input_digest
  = sha256(length-delimited(
      normalized document/reference projection, mapping_context_digest))
```

Mapping additions, modifications, removals, or active rule-version changes therefore invalidate
replay even when document bytes are unchanged. A changed common context may conservatively cause
all sources in the run to be reevaluated. Missing required mapping artifacts or invalid bindings
remain failures under §§4–6; they MUST NOT be silently treated as an empty context. A valid explicit
mapping removal is reevaluated and may still cause unresolved identity and rejection.

`content_sha256` is the SHA-256 of the exact bytes received for the root document. It is retained
for provenance and is allowed to differ across semantically equivalent captures. For OpenAPI and
AsyncAPI, each referenced-file closure entry is encoded as a length-delimited tuple:

```text
UTF-8 byte length of normalized POSIX path
UTF-8 bytes of normalized POSIX path relative to the approved source root
exact file byte length
exact file bytes
```

Entries are concatenated in normalized-path byte order and SHA-256 hashed to produce
`dependency_closure_digest`. The root document is excluded because its exact bytes are represented
by `content_sha256`. The empty closure digest is SHA-256 of the zero-length byte string
(`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
`semantic_input_digest` binds the normalized document projection and mapping context above and is
used to decide semantic replay no-op.

### 5.4 Replay behavior

```text
same SourceInstanceId + same semantic_input_digest
  -> mapping replay no-op; no duplicate ownership/evidence; no graph-revision advance
  -> inventory validation and scope/removal checks still execute

same SourceInstanceId + changed semantic_input_digest
  + same completed scope_definition_digest
  -> deterministic source-owned diff; expire claims no longer emitted

same SourceInstanceId + changed scope digest
  -> preserve claims absent from the new scope
  -> expire them only through an explicit inventory transition/tombstone

invalid or incomplete load or reevaluation
  -> commit nothing; preserve last successful source state
```

A changed mapping context requires reevaluation, not an unconditional graph-revision increment.
After reevaluation, compare canonical claims, ownership, and answer-visible evidence with committed
state. Only an identical result is a semantic no-op; changed identity or evidence is reconciled
atomically under the same scope/removal guards. Audit capture changes alone do not advance the graph.
If mapping removal leaves Service identity unresolved, the run fails and preserves prior claims;
it does not authorize their deletion.

## 6. Inventory and removal authority

Every discovery run SHALL produce a `SourceInventorySnapshot` containing an inventory revision and
capture identity, `DiscoveryScopeId`, scope digest, discoverer/adapter and mapping-rule identities,
status (`COMPLETE`, `PARTIAL`, or `FAILED`), discovered source IDs, explicit tombstones, provider
revision where available, capture time, and diagnostic references.

Canonical inventory identities use length-delimited UTF-8 fields and lowercase hexadecimal SHA-256:

```text
DiscoveryScopeId
  = urn:aip:discovery-scope:<sha256(configured scope id, stable target identity)>

scope_definition_digest
  = sha256(DiscoveryScopeId, normalized roots, filters, inclusion rules)

inventory_revision
  = urn:aip:inventory-revision:<sha256(DiscoveryScopeId, scope_definition_digest,
      ordered source ids, ordered tombstones, completion status)>

inventory_capture_id
  = urn:aip:inventory-capture:<sha256(inventory_revision,
      normalized provider revision, capture time)>

inventory_event_id, optional audit-chain identity
  = urn:aip:inventory-event:<sha256(previous event id, inventory_capture_id)>
```

`configured scope id` is the operator-assigned stable identity for the discovery boundary. `stable
target identity` is a configured logical repository/root identity, cluster UID, or equivalent
endpoint identity without mutable filters or credentials. For filesystem discovery it MUST NOT be
an absolute checkout path, resolved physical directory, mount point, or other mutable root location.
Physical roots, filters, and inclusion rules belong only to `scope_definition_digest`; changing
them MUST NOT change `DiscoveryScopeId`.

`inventory_revision` is semantic and idempotent: identical enumerations produce the same revision.
`inventory_capture_id` distinguishes repeated captures without affecting semantic replay. The
optional event ID may provide chronology but MUST NOT participate in semantic equality, removal
authority, or graph-revision decisions.

An explicit tombstone SHALL contain the target `SourceInstanceId`, the `DiscoveryScopeId`, the
expected prior committed `inventory_revision`, the scope digest, an attributable actor/reason, and
the tombstone revision. A tombstone whose expected prior revision does not match the committed
inventory is stale and MUST be rejected without expiration.

Whole-source expiration is authorized only by either:

1. a versioned desired-source inventory explicitly tombstoning the source; or
2. a `COMPLETE` authoritative enumeration with the same scope ID and scope digest that confirms the
   source is absent.

Missing roots, incomplete checkouts, authentication/authorization failures, timeouts, truncation,
pagination errors, unavailable endpoints, and changed/unverified scopes MUST preserve the prior
inventory and all claims owned by undiscovered sources. Permission denial MUST NOT be interpreted as
an empty result.

The transaction unit is one complete discovery run: inventory update, all source reconciliations,
and authorized tombstones commit atomically. If any discovered source fails validation/load, the
run is `PARTIAL` or `FAILED`; no source reconciliation, `COMPLETE` inventory, or tombstone from that
run may commit. The prior inventory and all source claims remain intact. A later clean run may
commit valid sources and removals together.

Inventory update, per-source reconciliation, and authorized tombstones SHALL commit atomically.
A claim expires only when its latest successful same-scope import no longer emits it (or the source
has an authoritative removal decision), no other source owns it, and the complete reconciliation
commits.

## 7. Adapter pipeline

The orchestrator SHALL execute:

```text
discover -> inventory -> classify -> load -> validate -> normalize -> map
  -> merge -> canonical validation -> reconciliation plan -> atomic commit
```

The orchestrator MUST NOT contain a hard-coded branch per source kind. I1 SHALL register:

```text
OpenAPI adapter
AsyncAPI adapter
Architecture Manifest adapter
filesystem source discoverer
```

The existing filesystem layouts and canonical filenames remain supported. A source may emit claims
for multiple services, and a service may be supported by multiple sources.

## 8. OpenAPI contract

The OpenAPI adapter SHALL:

- accept exactly OpenAPI `3.0.3` and `3.1.0`; any other version is
  `REJECTED_UNSUPPORTED` unless a reviewed amendment adds that exact version and its conformance
  fixtures;
- map schemas through the normalization and identity contract in §8.1;
- resolve local multi-file `$ref` only within an approved source root;
- enforce a maximum reference depth of 16, 128 distinct referenced files, and 8 MiB total bytes
  across the root and closure; exceeding any limit is `REJECTED_UNSUPPORTED` with diagnostic code
  `REFERENCE_LIMIT_EXCEEDED`;
- hash the bounded transitive reference closure;
- map supported inline, array, and nested schemas;
- preserve relevant path parameters and server/base-path metadata;
- provide stable operation identities and deterministic duplicate-`operationId` diagnostics;
- produce equivalent results for YAML/JSON and irrelevant key-order changes.

### 8.1 Canonical schema normalization and identity

Every admitted schema is converted to a JSON-compatible value, all local references are expanded,
and the result is serialized with RFC 8785 JSON Canonicalization Scheme. The schema
`canonical_hash` is the lowercase hexadecimal SHA-256 of those UTF-8 bytes.

The canonical projection excludes only `description`, `summary`, `example`, `examples`, and
`externalDocs`. All validation/serialization keywords and every extension key are retained. Object
keys are canonicalized by RFC 8785. The branch arrays of `allOf`, `oneOf`, and `anyOf` are sorted by
the full canonical hash of each normalized branch because their order has no architectural meaning;
all other arrays retain source order.

Composition is represented structurally in the canonical hash and is not flattened or interpreted
as an effective object shape in I1:

```text
valid allOf / oneOf / anyOf
  -> Schema emitted
  -> canonical hash includes the normalized composition
  -> ACCEPTED_WITH_LIMITATIONS + SCHEMA_COMPOSITION_UNINTERPRETED

composition containing a cycle
  -> REJECTED_UNSUPPORTED + REFERENCE_CYCLE_UNSUPPORTED

composition branch with invalid/dangling reference
  -> REJECTED_INVALID
```

Conflicting constraints within a syntactically valid composition remain preserved in its hash and
are not resolved by AIP. A definition at the same owner pointer may evolve between successful
source revisions: the current revision deterministically updates the entity's canonical hash/content
while preserving its owner-scoped Schema ID. Two
incompatible definitions for the same owner-scoped ID in one run are `REJECTED_CONFLICT`. Two
current owners explicitly mapped to one shared Schema ID with different canonical hashes are also
`REJECTED_CONFLICT`; identical hashes may merge only under that explicit mapping.

Schema IDs are owner-scoped and independent of unscoped names and content:

```text
schema_owner_key
  = length-delimited(canonical Service id, SourceInstanceId, normalized definition source pointer)

default schema id
  = schema:owned:<sha256(schema_owner_key)>

explicit shared schema id
  = full canonical id supplied by a versioned configured shared-identity mapping
```

The normalized definition source pointer is the normalized relative document path plus decoded RFC
6901 pointer. A referenced schema uses the resolved definition's pointer. An inline schema uses its
own stable request/response/media-type pointer. Component name, display name, title, structural
hash, and matching content elsewhere are labels/comparison evidence only and MUST NOT establish
identity.

An explicit shared-identity mapping SHALL bind one or more exact `(SourceInstanceId, source
pointer)` pairs to one full canonical Schema ID and carry attribution, content digest, revision, and
mapping-rule version. Cross-source schema merging is permitted only when both sources resolve
through such mappings to the same ID. Different hashes under an explicitly shared ID are
`REJECTED_CONFLICT`; otherwise identical cross-source hashes remain distinct owner-scoped schemas.
I1 SHALL provide versioned migration mappings from each qualified v0.4.2 schema source pointer to
its prior canonical Schema ID; the adapter MUST NOT preserve those unscoped IDs through name-based
fallback.

An array is one schema: its normalized `items` schema participates recursively in the array's
canonical hash. Anonymous nested object/array schemas do not create separate Schema entities unless
they are directly referenced by an operation or message; when materialized, the same rules above
determine their owner-scoped IDs. Adding, removing, or renaming another equal schema cannot change
an inline schema's ID. Equivalent inline and referenced schemas may share `canonical_hash` for
comparison but remain different logical identities unless an explicit shared-identity mapping binds
them.

Fragment-only references such as `#/components/schemas/X` are allowed and resolve within the
containing document. A relative reference in any document resolves against that containing
document's directory, not directly against the source root. Resolution SHALL occur in this order:

```text
parse reference URI
  -> reject non-empty URI schemes and authorities
  -> percent-decode the path exactly once; reject invalid encoding
  -> reject an absolute decoded path
  -> resolve the decoded relative path against the containing document directory
  -> normalize dot segments
  -> resolve symlinks to the real filesystem path
  -> require the real path to be a regular file inside the approved source root real path
  -> decode and resolve the fragment as an RFC 6901 JSON Pointer
```

Containment is checked only after decoding, normalization, and symlink resolution. Encoded traversal,
`..` escape, symlink escape, directory targets, missing files, malformed encoding, and invalid or
dangling JSON Pointers are `REJECTED_INVALID`. A detected reference cycle is
`REJECTED_UNSUPPORTED` with diagnostic code `REFERENCE_CYCLE_UNSUPPORTED`. Equivalent URI
percent-encoding and JSON Pointer escaping normalize to one target identity.

Construct outcomes are frozen as follows:

```text
remote/non-local reference
  -> REJECTED_UNSUPPORTED for the whole source

callback or webhook in an otherwise valid document
  -> ACCEPTED_WITH_LIMITATIONS
  -> omit only that construct and emit a source-pointer diagnostic

security declaration whose presence does not affect a supported operation mapping
  -> ACCEPTED_WITH_LIMITATIONS
  -> retain provenance; perform no security-policy inference

full API-catalog-only metadata
  -> ACCEPTED_WITH_LIMITATIONS
  -> omit fields outside the canonical Service/Operation/Schema mapping and list each omitted
     construct by source pointer
```

An OpenAPI source is accepted when its Service and every syntactically valid HTTP operation can be
identified by method/path, even if a callback, webhook, documentation-only field, or schema relation
is omitted under a rule above. An operation with an unsupported schema still emits the Operation but
omits only the affected `REQUEST_SCHEMA`/`RESPONSE_SCHEMA` relation and produces
`ACCEPTED_WITH_LIMITATIONS`. Whole-source rejection occurs only for an unsupported dialect, remote
reference, reference cycle/limit, invalid structure/reference, duplicate canonical identity with
conflicting content, or inability to determine a Service or HTTP operation identity. No unsupported
construct may silently disappear from the report.

## 9. AsyncAPI contract

The AsyncAPI adapter SHALL:

- accept exactly AsyncAPI `2.6.0`; all other versions, including every AsyncAPI 3.x document, are
  `REJECTED_UNSUPPORTED` in I1;
- resolve local multi-file `$ref` and transitive message/payload schemas using the complete OpenAPI
  containment, URI/pointer normalization, cycle handling, and maximum depth 16 / file count 128 /
  total size 8 MiB contract from §8;
- provide deterministic message identities and collision diagnostics;
- support multiple messages per supported operation;
- preserve relevant server, protocol, address, and binding metadata;
- keep an AsyncAPI Channel distinct from any canonical broker destination;
- emit an explicit diagnostic for operation keys other than `publish`/`subscribe` and whenever none
  of the three Queue-evidence paths below succeeds.

Queue mapping requires both qualified destination kind and qualified destination identity.

Destination kind is `Queue` only when at least one of these paths succeeds and all successful paths
agree:

```text
channel extension x-aip-destination-kind = "queue"
supported AMQP channel binding has is = "queue"
versioned configured destination mapping declares kind = "queue"
```

Queue identity is established only by:

```text
versioned configured destination mapping supplies a full canonical Queue id

OR

derived queue id
  = queue:owned:<sha256(length-delimited(
      stable broker id, normalized namespace-or-empty, exact channel address))>
```

`stable broker id` must come from an explicit `x-aip-broker-id` on the single selected AsyncAPI
server or a versioned configured server-identity mapping. Server name, URL, hostname, protocol, and
TLS identity are not sufficient. Namespace is the configured destination namespace when present,
otherwise the AMQP server binding `virtualHost`, otherwise the explicit empty string. Channel
address is the channel key normalized to Unicode NFC without trimming or case folding. When a
channel selects multiple servers, all must resolve to the same broker ID and namespace or the result
is `AMBIGUOUS` and no Queue is emitted.

Multiple agreeing kind/identity paths union evidence. Conflicting kinds, configured Queue IDs, or a
configured Queue ID that disagrees with the derived ID are `REJECTED_CONFLICT`. Missing kind or
identity evidence leaves the channel unsupported. Channel name, `-q` suffix, operation direction,
protocol name, URL, or content coincidence never establishes Queue identity.

The unchanged v0.4.2 AsyncAPI document with its authoritative Service mapping but without a Queue
mapping is `REJECTED_UNSUPPORTED` when none of its channels can emit a supported Queue relation.
No Queue is guessed and the failed discovery run preserves its previously committed state. I1 SHALL ship an
explicit, versioned migration mapping for each qualified v0.4.2 fixture, binding its channel pointer
to the prior full canonical Queue ID; input plus that mapping preserves the prior canonical meaning.
The adapter MUST NOT grandfather legacy inputs through hidden filename or naming rules.

### 9.1 Canonical message and payload identity

Each message is normalized with the same RFC 8785 projection used for schemas. The complete
normalized document projection has a `message_document_digest` (lowercase hexadecimal SHA-256) and
is retained as provenance. Unscoped names and content do not establish identity; the normalized
owner pointer is intentional identity scope. The default identity is:

```text
message_owner_key
  = length-delimited(canonical Service id, SourceInstanceId,
      normalized resolved message-definition source pointer, normalized x-version-or-empty)

default message id
  = message:owned:<sha256(message_owner_key)>

referenced payload schema id
  = the §8.1 owner-scoped or explicitly shared ID of the resolved schema definition pointer

inline payload schema id
  = schema:owned:<sha256(length-delimited(message id, normalized inline payload source pointer))>

explicit shared message/schema id
  = full canonical id supplied by a versioned configured shared-identity mapping
```

The resolved pointer is the normalized relative document path plus decoded RFC 6901 pointer. A
component reference uses the component definition pointer; an inline message uses its operation
message pointer. A payload `$ref` always uses the resolved definition's §8.1 Schema ID; only a payload
defined inline uses the message-owned inline payload ID above. `name`, `title`, component key, and
`message_document_digest` is retained as provenance only. `x-version`
participates in the owner key only when it is a non-empty string; another type is
`REJECTED_INVALID`. Payload canonical hashes use §8.1, including array, nested, and composition
handling.

The complete normalized message document is retained as `message_document_digest` provenance. A
separate `message_contract_digest` is used for semantic comparison and conflict detection. It is
computed from the canonical message projection after excluding presentation and identity metadata:

```text
excluded from message_contract_digest:
  name, title, description, summary, example, examples, externalDocs
  x-version, x-aip-* identity/mapping extensions
  component key and source pointer (never part of the message object itself)

retained:
  payload, headers, contentType, correlationId, traits, bindings,
  and all other non-documentation, non-identity fields and extensions
```

The contract digest is the lowercase hexadecimal SHA-256 of the RFC 8785 bytes after those
exclusions. Two explicitly shared Messages with different local labels but equal contract digests
merge; different contract digests under the same explicit shared ID conflict.

Shared message/schema mappings use the same attributable, versioned contract as §8.1 and bind exact
source pointers, never names or hashes. Cross-source Message or payload-Schema merging is prohibited
without an explicit mapping to the same full canonical ID.

I1 SHALL provide versioned migration mappings from every qualified v0.4.2 message and payload source
pointer to its prior canonical Message and Schema IDs. Without that mapping the unchanged source uses
safe owner-scoped IDs; no legacy name-based ID is inferred.

Messages are visited in canonical channel-name, operation (`publish` before `subscribe`), then
source-pointer order. Repeated references to the same owner-scoped message merge and union evidence.
Different owner-scoped messages remain distinct even when their labels and contract digests match.
A message at the same owner pointer may evolve between source revisions and deterministically updates
its canonical content/digest while preserving its owner-scoped ID. Two definitions for that owner ID
in one run with different contract digests, or two current
owners explicitly sharing an ID with different contract digests, are `REJECTED_CONFLICT`. The same
applies to payload Schema IDs with different canonical hashes.

Unsupported versions MUST NOT pass through an older mapping. AsyncAPI 3 is entirely outside I1 and
requires a reviewed amendment or later increment. Topic/Subscription meaning belongs to I4.

For an otherwise valid AsyncAPI 2.6.0 document, an operation other than `publish`/`subscribe`, or a
channel without at least one successful, non-conflicting Queue-evidence result, is omitted with a source-pointer
diagnostic and produces `ACCEPTED_WITH_LIMITATIONS`; other supported operations may still be emitted. The source is
`REJECTED_UNSUPPORTED` when it contains channels but none has both (a) a supported `publish` or
`subscribe` operation and (b) sufficient evidence under the versioned I1 destination rule to emit
the existing Queue relation. This source-level rejection takes precedence over channel-level
limitations. A document with no channels is accepted as a Service-only source.

For an otherwise valid source with authoritative Service identity and no other rejection:
- no channels: `ACCEPTED` as Service-only;
- channels present, zero supported Queue relations: `REJECTED_UNSUPPORTED`;
- some supported Queue relations and some omitted constructs: `ACCEPTED_WITH_LIMITATIONS`;
- all constructs supported without limitations: `ACCEPTED`.

Any `REJECTED_*` result prevents the discovery run from committing, as required by §6.
Missing message `name`/`title` is not itself unsupported because §9.1 defines deterministic
fallbacks. Invalid structure and dangling/invalid local references produce `REJECTED_INVALID`. Cycles produce
`REJECTED_UNSUPPORTED` with `REFERENCE_CYCLE_UNSUPPORTED`; exceeded reference limits produce
`REJECTED_UNSUPPORTED` with `REFERENCE_LIMIT_EXCEEDED`. Remote references produce
`REJECTED_UNSUPPORTED` for the whole source.

## 10. Evidence, merge, and results

Every emitted claim SHALL trace to:

```text
source locator
source revision and capture
content_sha256
dependency_closure_digest, where applicable
semantic input digest and mapping context digest
source pointer / JSON Pointer
adapter identity
mapping-rule identity and version
inventory and scope identity
```

Merge behavior is:

```text
identical entity/relation
  -> deterministic merge and evidence/ownership union

compatible enrichment
  -> deterministic merge under a versioned rule

conflicting identity or property
  -> deterministic conflict diagnostic
  -> affected import rejected; no arbitrary winner
```

Each source receives exactly one result:

```text
ACCEPTED
ACCEPTED_WITH_LIMITATIONS
REJECTED_INVALID
REJECTED_UNSUPPORTED
REJECTED_CONFLICT
```

The import report SHALL include discovered sources and inventories, dialects, identities, emitted
counts, unsupported constructs, unresolved references, conflicts, planned mutations/expirations,
tombstones, and final commit status. A dry-run SHOULD return the same plan without mutation.

The persisted audit record retains capture-specific fields, including capture time,
`source_capture_id`, `inventory_capture_id`, provider revision, and optional event-chain identity.
The deterministic semantic report is a separately defined projection and SHALL exclude those
capture-specific fields. It includes only semantic source/inventory revisions, scope definitions,
ordered diagnostics, canonical planned/committed effects, result statuses, and stable identities.
Two runs over semantically identical inputs and mapping contexts, with the same initial committed
graph (including ownership and answer-visible evidence) and inventory state and the same active
rules, MUST produce byte-identical canonical JSON for this projection even when audit captures
differ. Qualification SHALL record the initial-state fixture identity and revision.

An initial import and its subsequent replay have different initial states and need not have
byte-identical effect reports. Sequential replay qualification instead requires unchanged canonical
results, zero canonical mutations, no duplicate ownership/evidence, and an unchanged graph revision.
Capture-specific audit records may still be appended.

## 11. Qualification and Definition of Done

I1 is complete only when deterministic tests prove that:

- all existing adapters use the registry seam and preserve qualified meaning;
- multiple sources per service and multiple services per source work;
- explicit extension, configured mapping, and Architecture Manifest Service-resolution paths agree
  deterministically; missing, malformed, ambiguous, and conflicting Service identities emit no
  owner-scoped canonical entities;
- Architecture Manifest bindings conform to the frozen schema, are validated/collected before
  document mapping, and source-discovery permutations produce identical binding indexes and results;
- pointer-prefix matching uses decoded RFC 6901 tokens, including a non-match for `/paths/~1foo`
  versus `/paths/~1foobar`;
- equivalent YAML/JSON and key-order forms produce equal normalized hashes and canonical meaning;
- content-equivalent inline and referenced schemas produce equal normalized hashes and equivalent
  operation-contract roles, while retaining distinct owner-scoped IDs unless explicitly mapped;
- named-component, inline, anonymous nested, and array schemas produce stable owner-scoped IDs and
  the exact RFC 8785 hashes specified in §8.1;
- adding/removing an unrelated content-equivalent schema does not change an inline schema ID;
- equal schema names/hashes across owners remain distinct unless an explicit shared-identity mapping
  binds them; shared-ID/different-hash conflicts reject the run;
- reordered composition branches are equivalent, while same-owner canonical-ID/hash conflicts reject
  the run;
- referenced and inline AsyncAPI messages produce stable pointer-based owner-scoped IDs, equal
  cross-source names/content remain distinct, and shared-ID/different-content conflicts reject;
- message presentation/AIP identity metadata may differ under an explicit shared ID without changing
  `message_contract_digest`, while contract-field differences conflict;
- same-owner revisions update deterministically, whereas same-run duplicate definitions or
  cross-owner explicit shared-ID content conflicts reject;
- referenced AsyncAPI payloads use the resolved §8.1 Schema ID, while inline payloads use the stable
  message-owned pointer identity;
- every Queue kind and identity evidence path, missing broker identity, multi-server ambiguity, and
  conflicting path has positive and negative coverage;
- unchanged v0.4.2 fixtures with only authoritative Service mappings produce owner-scoped
  schema/message identities where accepted; partial Queue support yields limitations, while zero
  supported Queue relations rejects the source and preserves the entire committed run state;
  without Service mappings they are rejected unresolved; full versioned mappings restore previous
  Schema/Message/Queue IDs and meaning;
- empty, entirely unsupported, partially supported, and fully supported AsyncAPI channel sets have
  the exact source-level outcomes in §9.1, including atomic preservation on rejection;
- two clean checkouts at different absolute paths derive the fixed bundled-example scope/source IDs
  and apply the same Service/Schema/Message/Queue migration mappings;
- cycles, duplicate identities, conflicts, and invalid inputs fail without partial writes;
- reference depth/file-count/byte limits pass at the boundary and fail at boundary +1;
- fragment-only and nested-file-relative references resolve from the containing document;
- absolute, percent-encoded traversal, symlink-escape, unsupported-URI, malformed fragment, and
  pointer-alias references are handled exactly as specified;
- reimport with unchanged mapping context is idempotent and a semantic no-op does not advance
  graph revision;
- unchanged documents with added, changed, or explicitly removed Service, shared Schema/Message,
  Queue, broker, namespace, or manifest mappings are reevaluated using a changed context digest;
- active adapter/normalization/mapping-rule version changes invalidate replay;
- mapping removal causing unresolved identity rejects the run without expiring prior claims;
- an unrelated context change may trigger reevaluation but identical canonical claims, ownership,
  and answer-visible evidence produce no graph-revision advance;
- context entry ordering and physical checkout paths do not affect the context digest;
- checkout paths do not affect source identity;
- changing roots/filters preserves `DiscoveryScopeId` and changes only `scope_definition_digest`;
- identical inventories retain `inventory_revision` across captures while distinct capture times or
  provider revisions produce distinct `inventory_capture_id` values;
- a tombstone bound to a stale prior inventory revision is rejected without expiration;
- explicit tombstones and complete same-scope inventories retire only intended ownership;
- failed/partial discovery, missing roots, permission denial, and incomplete checkouts preserve state;
- changed scopes cannot expire prior ownership without an explicit transition;
- shared claims survive removal of one source;
- a failed source prevents the entire discovery run from committing a `COMPLETE` inventory or
  tombstone, while a subsequent clean run commits all valid reconciliations atomically;
- byte-different but semantically equivalent inputs retain distinct `content_sha256` and closure
  provenance while sharing `semantic_input_digest` and producing no semantic duplicate;
- dependency-closure tuple encoding, path ordering, byte lengths, and the empty-closure digest match
  the fixed vectors in §5.3;
- exact accepted and rejected OpenAPI/AsyncAPI versions and every construct-level result are covered;
- equivalent runs from the same recorded initial graph/ownership/evidence and inventory state,
  with identical mapping contexts and rules, produce byte-identical semantic reports despite
  capture-specific audit differences;
- an initial import followed by replay yields unchanged canonical results, zero replay mutations,
  no duplicate ownership/evidence, and unchanged graph revision, without requiring identical
  first-import and replay effect reports;
- two clean runs from the same initial-state fixture produce byte-identical semantic reports.

Qualification evidence SHALL include independent fixtures for source identity, lifecycle transitions,
reference limits, merge outcomes, diagnostics, and the existing regression corpus.

## 12. Public compatibility and decisions

I1 MUST NOT add MCP tools or change existing Architecture Answer semantics. Any new canonical entity,
predicate, or payload crossing a public schema boundary requires an explicit versioned schema update
before qualification; silent enum widening or undocumented payload drift is prohibited.

The I1 implementation specification may decide package-level interfaces and diagnostic wire details,
but it MUST NOT change the source identity, inventory authority, atomicity, replay, evidence, or
result rules in this document without a reviewed parent-specification amendment.

## 13. Required evidence and handoff

The I1 completion record SHALL identify the candidate revision, adapter/mapping-rule versions,
fixture identities, source inventory/replay evidence, regression results, and any limitations or
unsupported constructs. It SHALL state that I2 may rely on the seam and lifecycle contract without
reintroducing directory-based ownership or name-based identity.
