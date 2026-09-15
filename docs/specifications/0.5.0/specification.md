# AIP v0.5.0 Release Specification — Broader Architecture Discovery

**Status:** Draft 0.1 — release capability and implementation contract (aligned with I1)  
**Target release:** `v0.5.0`  
**Release theme:** Broader Architecture Discovery  
**Entry baseline:** Published and post-release-verified `v0.4.2`  
**Primary outcome:** AIP can safely discover a broader distributed-system Current State from
expanded OpenAPI/AsyncAPI inputs, Kubernetes infrastructure, and qualified runtime evidence while
preserving deterministic identity, provenance, evidence, unsupported-case, and read-only
Architecture Intelligence guarantees.

---

## 1. Release Promise

`v0.4.x` made AIP's evidence-backed architecture intelligence safely consumable through direct and
negotiated MCP workflows. `v0.5.0` broadens what AIP can safely know.

The release SHALL prove this capability:

> **Given declared API/messaging documents, a bounded Kubernetes source, and qualified runtime
> evidence, AIP can discover and reconcile a broader distributed-system Current State, retain the
> source and evidence behind every supported claim, and leave ambiguous, conflicting,
> insufficiently observed, or unsupported cases explicit rather than guessing.**

The release is governed by these invariants:

```text
non-observation != absence
source disappearance != authorized source removal
unresolved identity > guessed identity
explicitly unsupported > incorrectly represented as supported
Queue != Topic
Topic != Subscription
Service != Kubernetes Service != Workload != Pod
WHERE something is != HOW it interacts
co-location != dependency
observed behavior != intent
```

> **WHERE something is does not establish HOW it interacts.**

The existing agent boundary remains:

> **AIP may help agents reason about architecture, but an agent must never become the source of
> architectural truth.**

## 2. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

Examples illustrate required semantics. Versioned schemas, mapping rules, deterministic fixtures,
and independently authored release evidence SHALL be authoritative implementation evidence.

## 3. Entry Conditions and Preserved Baseline

Implementation may be planned before `v0.4.2` publication, but final `v0.5.0` qualification SHALL
use a published and post-release-verified `v0.4.2` baseline.

The following baseline properties SHALL remain true:

- the Canonical Model is the single mapping target for all sources;
- adapters do not write directly to Neo4j;
- canonical identities remain deterministic and path-independent;
- claims retain evidence and provenance references;
- imports and reconciliations are atomic;
- declared-versus-observed qualification remains governed by one semantic rule;
- snapshot/revision fencing remains the basis for consistent reads;
- `ArchitectureAnswer<T>` remains evidence-backed and limitation-aware;
- direct and negotiated MCP paths remain semantically equivalent;
- the public MCP surface remains exactly three read-only tools unless a separately approved release
  amendment changes the scope budget;
- no LLM or agent assertion can create or qualify a canonical fact;
- the `v0.4.1` Queue/destination-kind and runtime-service-identity guards remain active unless an I4
  decision explicitly supersedes them with qualified semantics.

`v0.5.0` SHALL NOT weaken a baseline refusal merely because a new source provides a similar name,
namespace, label, selector, address, or co-location signal.

## 4. Fixed Scope Budget

### 4.1 In scope

`v0.5.0` SHALL deliver:

1. one evidence-preserving source-adapter seam;
2. expanded OpenAPI and AsyncAPI ingestion through the seam;
3. migration of Architecture Manifest ingestion and filesystem discovery to the seam;
4. deterministic source identity, inventory, replay, conflict, and expiration semantics;
5. Kubernetes as the single new discovery-source family;
6. bounded OpenTelemetry/Kubernetes/declared-source identity reconciliation;
7. conditional source-independent Pub/Sub semantics through a `GO` or `DEFER` gate;
8. independent cross-system qualification and evidence-justified hardening;
9. exact-candidate release preparation, optional owner-authorized publication, and published-
   artifact verification.

### 4.2 Explicitly out of scope

```text
gRPC/protobuf ingestion
Kafka Connect ingestion
live broker-topology adapters
service-mesh discovery
cloud-provider inventory adapters
repository or source-code mining
third-party adapter loading
distributed local-assessor deployment
qualified locality-aware Current-State projections
explicit Architecture Intent
Current-to-Intent assessment
historical architecture trajectories
architecture mutation or policy enforcement
new public MCP tools
generic graph-query tools
LLM-based identity, mapping, or qualification
```

Broker products MAY appear as independently authored I4 semantic fixtures. That does not introduce
a broker adapter or broker-specific canonical meaning.

Kubernetes is the only admitted new source family. OpenAPI and AsyncAPI are expansions of existing
source families. Other adapters require a separately approved later-release specification.

Placement evidence may be retained for identity, collision avoidance, replay, and future
qualification. `v0.5.0` SHALL NOT expose a locality-qualified claim or projection.

## 5. Increment Contract and Dependency Order

| Increment | Title | Required outcome |
|---|---|---|
| I1 | OpenAPI/AsyncAPI Ingestion Expansion and Source Adapter Seam | Existing sources use one evidence-preserving seam with deterministic lifecycle semantics. |
| I2 | Kubernetes Discovery Vertical Slice | Kubernetes infrastructure is discovered without name-based service equivalence or interaction inference. |
| I3 | Deeper Runtime Discovery and Cross-Source Reconciliation | Declared Service, Workload, and runtime identities are linked only through frozen guards. |
| I4 | Conditional Source-Independent Pub/Sub Semantics | A recorded `GO` or `DEFER`; implementation occurs only after the semantic gate passes. |
| I5 | Cross-System Qualification and Model Hardening | Independent real-system validation with evidence-justified fixes only. |
| I6 | Release Candidate, Publication, and Post-Release Verification | One exact candidate reaches an explicitly distinguished unpublished or published terminal outcome. |

```text
I1 -> I2 -> I3
I1 -> I4 decision
I2 + I3 + I4 disposition -> I5 -> I6
```

I4 may end in `DEFER` without blocking the release. Every other increment requires its stated
positive exit capability.

---

# Part I — Source Ingestion Foundation

The increment-level implementation contract is maintained in
[`i1-source-ingestion-foundation.md`](i1-source-ingestion-foundation.md). Its frozen identity,
normalization, inventory, construct-outcome, and migration rules are the detailed I1 contract;
the release-level summaries below do not broaden its accepted inputs or qualification claims.

## 6. Source Model

I1 SHALL introduce concepts equivalent to:

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

A `SourceDescriptor` SHALL carry at least:

```text
source_instance_id
source_kind
locator
discovery_scope_id
scope_definition_digest
source_inventory_snapshot_ref
declared/provider revision, where available
content SHA-256
declared/configured service identity, where available
document dialect/version
adapter identity
mapping-rule identity and version
```

The model SHALL NOT assume:

```text
source == local file
service identity == directory name
one source == one service
one service == one source
one fixed filename per source kind
```

Filesystem scanning remains one discoverer. Existing qualified layouts and canonical filenames
SHALL remain backward compatible.

## 7. Source Identity, Revision, and Replay

### 7.1 Stable source identity

`SourceInstanceId` identifies the stable logical source that owns imported claims. It SHALL remain
stable across content changes, revisions, checkout locations, and equivalent replays. It SHALL NOT
derive from content hash, service identity, an absolute path, Kubernetes `resourceVersion`, or a
temporary checkout.

```text
source_instance_id = urn:aip:source:<source-kind>:<sha256(stable-source-key)>

filesystem stable-source-key
  = configured filesystem-source id
    + source kind
    + normalized POSIX root-document path relative to configured source root

Kubernetes stable-source-key
  = configured Kubernetes-source id
    + immutable cluster UID
```

Two independently configured scopes against one cluster SHALL use different configured source ids.
A frozen Kubernetes snapshot is replay-equivalent to a live source only with the same configured
source id and independently captured cluster UID. Context name, URL, namespace, or filename alone
is insufficient.

### 7.2 Revision and capture identity

Every successful load SHALL record:

```text
source_revision_id
source_capture_id
declared/provider revision, where available
semantic_input_digest
raw/dependency-closure digest, where retained
capture time
```

```text
source_revision_id
  = urn:aip:source-revision:
    <sha256(SourceInstanceId + mapping-rule version + semantic_input_digest)>

source_capture_id
  = urn:aip:source-capture:
    <sha256(source_revision_id + normalized declared/provider revision)>
```

Without an independent provider revision, `source_capture_id = source_revision_id`. A Git-backed
source uses the full commit SHA when available. A live Kubernetes capture uses a deterministic
digest over retained sorted `resource UID + resourceVersion` pairs. A provider revision SHALL NOT
create a new semantic graph revision when normalized input is unchanged.

### 7.3 Semantic input normalization

`semantic_input_digest` SHALL hash a versioned deterministic source-kind projection:

- YAML/JSON keys are canonically ordered;
- comments, formatting, and absolute checkout paths are excluded;
- an OpenAPI/AsyncAPI root and its bounded local reference closure are hashed in normalized
  relative-path order;
- Kubernetes resources are sorted by cluster UID, GVK, namespace, and name;
- status, managed fields, timestamps, and specified volatile metadata are excluded;
- Kubernetes UID and `resourceVersion` remain capture provenance, not logical source identity.

Changing normalization is a mapping-rule version change and requires golden tests.

I1 Draft 0.2 amends this replay contract: its `semantic_input_digest` binds the normalized
document/reference projection and a common `mapping_context_digest` as specified in I1 §5.3.
The context includes the complete configured/manifest identity and migration mappings and active
adapter, normalization, and mapping-rule identities/versions. Changes or valid removals trigger
reevaluation even with unchanged documents; missing required artifacts remain errors. A changed
fingerprint alone does not mandate a graph-revision increment: identical canonical claims,
ownership, and answer-visible evidence after reevaluation remain a semantic no-op. Inventory,
scope, and removal checks cannot be skipped by a mapping replay no-op.

### 7.4 Replay behavior

```text
same SourceInstanceId + same semantic_input_digest
  -> semantic no-op
  -> no duplicate ownership/evidence
  -> no graph-revision advance

same SourceInstanceId + changed semantic_input_digest
  + same successfully completed scope_definition_digest
  -> deterministic source-owned diff
  -> add/update emitted claims
  -> expire claims no longer emitted by that source

same SourceInstanceId + changed scope_definition_digest
  -> add/update claims supported by the new observation
  -> preserve prior claims absent from the changed scope
  -> expire prior out-of-scope ownership only by explicit inventory transition/tombstone

different SourceInstanceId + identical claim
  -> preserve both ownership/evidence chains
  -> union evidence on the shared claim

invalid or incomplete load
  -> commit nothing
  -> preserve last successful source state
```

Kubernetes logical identity and resource incarnation are distinct:

```text
logical resource id
  = cluster UID + API group/kind + namespace + resource name

captured resource incarnation
  = logical resource id + Kubernetes resource UID
```

## 8. Source Inventory, Disappearance, and Removal

### 8.1 Removal authority

An undiscovered previously committed source is not evidence of removal. Whole-source expiration
requires one authoritative decision:

```text
REGISTERED inventory mode
  -> versioned desired-source inventory explicitly tombstones SourceInstanceId
     (including an explicit tombstone in a COMPLETE successor inventory)

AUTHORITATIVE enumeration mode
  -> identical DiscoveryScopeId
  -> identical scope_definition_digest
  -> adapter-qualified authoritative source-presence enumeration
  -> COMPLETE marker
  -> previously inventoried SourceInstanceId absent
```

No other absence authorizes whole-source expiration.

### 8.2 Inventory snapshot

Every discovery run SHALL produce a `SourceInventorySnapshot` containing:

```text
inventory_revision and inventory_capture_id
DiscoveryScopeId
scope_definition_digest
discoverer/adapter identity and mapping-rule version
status = COMPLETE | PARTIAL | FAILED
discovered SourceInstanceIds
explicit source tombstones, if any
capture time
diagnostic references
```

`DiscoveryScopeId` identifies the stable configured boundary. Its derivation and inventory
revision/capture identities follow I1 §6:
`DiscoveryScopeId` binds the configured scope id and stable logical target identity, never an
absolute checkout path or mutable physical root. The scope digest covers that ID, normalized roots,
namespace/resource filters, and inclusion rules. Physical root/filter changes preserve the scope ID
while changing its digest. Inventory revisions are semantic and idempotent; capture identities are
audit provenance, not semantic replay keys.

A changed scope digest SHALL NOT expire ownership last confirmed under a prior digest. Narrowing or
retiring the previous scope requires an explicit versioned transition/tombstone.

### 8.3 Completion authority

`COMPLETE` is valid only when the configured root/endpoint was reached, the full bounded scope and
pagination were enumerated, checkout integrity passed where applicable, and no authentication,
authorization, I/O, timeout, truncation, or adapter error could hide a source.

`PARTIAL`/`FAILED`, missing roots, incomplete checkouts, unavailable Kubernetes APIs, and unverified
scope changes SHALL preserve the last inventory and every claim owned by an undiscovered source.

An explicit tombstone SHALL bind its target source, scope ID/digest, expected prior committed
inventory revision, attributable actor/reason, and tombstone revision. A stale expected revision
rejects removal without expiration, as specified in I1 §6.

The transaction unit is one complete discovery run. Inventory update, all source reconciliations,
and authorized tombstones SHALL commit atomically. Any source load/validation failure makes the run
`PARTIAL` or `FAILED`: no reconciliation, COMPLETE inventory, or tombstone from that run commits.
Temporary non-observation MAY be diagnosed but MUST NOT be represented as removal.

### 8.4 Ownership and expiration

A claim may expire only when its latest successful same-scope import no longer emits it, or its
source has an authoritative removal decision; no other source still owns it; and the complete
reconciliation commits. Removing one source SHALL preserve every other source's ownership/evidence.

## 9. Adapter Seam and Atomic Ingestion

```text
discover
  -> inventory
  -> classify
  -> load
  -> validate
  -> normalize
  -> map
  -> merge
  -> canonical validation
  -> reconciliation plan
  -> atomic commit
```

The orchestrator SHALL NOT contain a hard-coded branch per source kind. Adapters return claims,
evidence, diagnostics, and lifecycle inputs; they SHALL NOT write directly to the graph.

I1 SHALL migrate:

```text
OpenAPI adapter
AsyncAPI adapter
Architecture Manifest adapter
filesystem source discoverer
```

Existing qualified fixtures retain canonical meaning through explicit, versioned migration mappings,
as specified in I1 §§2, 5.1.1, 8.1, and 9. Without authoritative Service identity, inputs are
`REJECTED_UNSUPPORTED`. Without shared Schema/Message mappings they use safe owner-scoped IDs;
Queue mapping requires independently qualified destination kind and identity, with limitation or
rejection outcomes exactly as specified in I1 §9. Legacy names are never identity fallbacks.

I1 SHALL ship the portable bundled-example Service/Schema/Message/Queue mappings at
`config/migrations/v0.5.0-bundled-example-identities.yaml`. These intentional safety migrations
SHALL be recorded and qualified, not described as unchanged legacy parsing.

## 10. OpenAPI Ingestion Expansion

I1 SHALL support:

- exactly OpenAPI `3.0.3` and `3.1.0`, with version-specific validation;
- safe local multi-file `$ref` within an approved source root;
- cycle, depth, file-count, and total-byte bounds;
- transitive reference-closure hashing;
- supported inline, array, and nested schemas under I1's owner-scoped identity rules;
- structural preservation of `allOf`, `oneOf`, and `anyOf` in canonical hashes, without flattening
  or effective-shape inference; valid composition reports `ACCEPTED_WITH_LIMITATIONS` and
  `SCHEMA_COMPOSITION_UNINTERPRETED`;
- relevant path-level parameters and server/base-path metadata;
- stable operation identity and duplicate-`operationId` diagnostics;
- equivalent semantics for YAML/JSON and irrelevant key ordering.

Other OpenAPI versions require a reviewed amendment with exact-version conformance fixtures.
Construct-level acceptance, omission, and rejection follow I1 §8.

Remote Internet `$ref`, security-policy analysis, complete API-catalog behavior, callbacks, and
webhooks are out of scope unless a reviewed bounded amendment admits them before implementation.

## 11. AsyncAPI Ingestion Expansion

I1 SHALL support:

- exactly AsyncAPI `2.6.0`, with explicit dialect detection and validation;
- safe bounded local multi-file `$ref`;
- transitive message/payload-schema resolution;
- deterministic message identity and collision diagnostics;
- multiple messages per supported operation;
- relevant server, protocol, address, and binding metadata;
- strict separation between AsyncAPI Channel and canonical broker destination;
- explicit diagnostics where kind or operation semantics cannot be mapped safely.

An unsupported version SHALL NOT pass through an older mapping. Every AsyncAPI 3.x document is
`REJECTED_UNSUPPORTED` in I1; admitting another version requires a reviewed amendment or later
increment with deterministic qualification. I4 `GO` does not itself expand dialect support.
Topic/Subscription meaning belongs to I4. Queue kind and Queue identity require separate evidence
under I1 §9; channel names, URLs, or operation direction cannot establish either by themselves.

## 12. Merge Results and Diagnostics

Every emitted claim SHALL trace to source locator, source revision/capture, semantic digest, source
pointer, adapter, mapping-rule version, and inventory/scope identity.

```text
identical entity/relation
  -> deterministic merge and evidence/ownership union

compatible enrichment
  -> deterministic merge under versioned rule

conflicting identity/property
  -> deterministic conflict diagnostic
  -> affected import rejected
  -> no arbitrary winner
```

Per-source result:

```text
ACCEPTED
ACCEPTED_WITH_LIMITATIONS
REJECTED_INVALID
REJECTED_UNSUPPORTED
REJECTED_CONFLICT
```

The report SHALL include sources, inventories/scopes, dialects, identities, emitted counts,
unsupported constructs, unresolved references, conflicts, planned mutations/expirations,
tombstones, and final commit status. A dry-run SHOULD return the same plan without mutation.

## 13. I1 Exit Gates

I1 requires deterministic proof that:

- all existing adapters use the seam and preserve qualified meaning through explicit migration mappings;
- multiple sources/service and services/source work;
- equivalent YAML/JSON and key-order forms preserve normalized hashes and canonical meaning;
- content-equivalent inline/reference schemas preserve normalized hashes and operation-contract
  roles while retaining distinct owner-scoped IDs unless explicitly mapped to a shared identity;
- cycles, duplicates, and conflicts fail deterministically without partial writes;
- reimport with unchanged mapping context is idempotent and semantic no-op does not advance graph revision;
- changed/removed mappings and active rule versions force reevaluation; unresolved identity rejects
  the run without expiration;
- AsyncAPI with channels but zero supported Queue relations is rejected; partial support yields
  limitations, and empty channel sets may be accepted as Service-only under I1 §9.1;
- checkout paths do not affect source identity;
- generic source identity, replay, and inventory rules pass I1 fixtures; Kubernetes mapping and
  any frozen/live replay qualification belong to I2;
- explicit tombstones and complete same-scope inventory retire exactly intended ownership;
- missing sources, incomplete checkouts, failed/partial discovery preserve committed state;
- changed filters/scopes cannot expire prior ownership without explicit transition;
- shared claims survive removal of one source;
- two clean runs with identical mapping contexts/rules and the same initial graph, ownership,
  evidence, and inventory state produce byte-identical semantic reports;
- sequential replay preserves canonical results with zero mutations and unchanged graph revision;
  first-import and replay effect reports need not be identical.

---

# Part II — Kubernetes and Runtime Reconciliation

## 14. Kubernetes Discovery Vertical Slice

### 14.1 Bounded resource scope

```text
Namespace
Deployment
StatefulSet
DaemonSet
Pod owner chain
Kubernetes Service
Ingress
```

ConfigMaps MAY provide selected non-secret identity metadata only after an I2 specification proves
need. Secrets and arbitrary environment values SHALL NOT become architecture content.

### 14.2 Canonical separation and locality boundary

```text
AIP Service
Kubernetes Service
Workload / Deployment Unit
Pod
network ingress/endpoint
```

Bounded positive infrastructure claim candidates:

```text
WORKLOAD_EXISTS
WORKLOAD_OWNS_POD
NETWORK_SERVICE_SELECTS_WORKLOAD
INGRESS_ROUTES_TO_NETWORK_SERVICE
```

I2 SHALL freeze exact names/shapes before fixtures. They describe infrastructure only.

Cluster, namespace, GVK, name, UID, `resourceVersion`, manifest revision, and resource placement are
source-context evidence, not a `v0.5` locality relation.

```text
placement != WORKLOAD_LOCALITY claim
selector match != application dependency
co-location != communication
```

### 14.3 Identity, provenance, and safe deletion

Kubernetes evidence includes source/inventory id, cluster UID, resource UID, GVK, namespace, name,
provider revision, source pointer, and mapping-rule version.

Names, labels, selectors, and co-location SHALL NOT establish an AIP Service identity.

I2 SHALL support deterministic offline frozen-manifest discovery. Bounded read-only live discovery
is optional. Before implementation and fixture authoring, I2 SHALL record `LIVE_INCLUDED` or
`OFFLINE_ONLY`. Live API, RBAC, pagination, and frozen/live-equivalence gates apply only to
`LIVE_INCLUDED`; offline identity, inventory, deletion, and incomplete-input safety remain mandatory.

A resource disappearance is actionable only after `COMPLETE` observation of the same
cluster and unchanged scope digest. Failure, timeout, truncation, pagination error, or partial
enumeration preserves state. Filter changes require explicit scope transition before expiration.

If `LIVE_INCLUDED`, live discovery SHALL use a least-privilege, read-only identity.
The normative minimum permission set is:

```text
get, list, watch:
  core/namespaces
  core/pods
  core/services
  apps/deployments
  apps/statefulsets
  apps/daemonsets
  networking.k8s.io/ingresses

no permission:
  create, update, patch, delete, deletecollection, or apply on any resource
  exec, attach, portforward, log, proxy, or arbitrary subresource access
  secrets, unless a separately approved I2 scope explicitly requires metadata-only access
```

The configured namespace/resource filters MUST be enforced in addition to RBAC. A denied required
resource, namespace, or list/watch operation makes the inventory `PARTIAL` (or `FAILED` when the
endpoint/authentication is unusable), records a sanitized diagnostic naming the denied scope, and
preserves the last successfully committed inventory and claims. Permission denial MUST NOT be
treated as an empty result or authorize source/claim expiration. The live adapter MUST NOT issue
write, exec, attach, port-forward, log, proxy, or secret-read requests as a fallback.

### 14.4 I2 exit gates

I2 requires:

- equivalent frozen inputs produce equivalent semantics;
- if `LIVE_INCLUDED`, equivalent frozen/live inputs preserve semantics and ownership with the
  same configured source id and independently captured cluster UID;
- ordering has no effect;
- namespace/cluster identity prevents collisions;
- selectors and owner chains resolve deterministically;
- deletion expires only source-owned facts after complete same-scope observation;
- failed/partial observation preserves state;
- ambiguous Service/Workload identity remains unresolved;
- Kubernetes-only evidence creates no `CALLS`, `SENDS`, or `RECEIVES_FROM`;
- no locality-qualified claim/projection is exposed;
- no secret/unrestricted environment content enters evidence;
- existing OpenAPI/AsyncAPI/OTel semantics remain unchanged.

## 15. Service-to-Workload Identity Contract

I3 SHALL implement exactly these successful paths. Another successful combination requires a
reviewed amendment before implementation or fixture authoring.

### 15.1 Path A — explicit workload annotation

```text
architecture-intelligence.io/service-id = <full canonical AIP Service id>
workload = cluster UID + GVK + namespace + workload name
annotation resolves to exactly one existing canonical Service

result = RESOLVED_EXPLICIT
```

### 15.2 Path B — configured identity mapping

```text
versioned mapping identity
full canonical AIP Service id
configured Kubernetes source id
cluster UID
workload GVK
namespace
workload name

result = RESOLVED_CONFIGURED
```

The mapping is evidence. Unversioned aliases, similarity, or implicit defaults do not qualify.

### 15.3 Path C — qualified OTel/Kubernetes linkage

All are required:

```text
OTel Resource contains k8s.pod.uid
Pod UID resolves to exactly one Pod in selected Kubernetes observation
owner chain resolves to exactly one supported Workload
OTel Resource contains service.name
service.name resolves through existing exact resolver to exactly one declared AIP Service
service.namespace, when present, is consistent
cluster/namespace attributes, when present, match Kubernetes evidence

result = RESOLVED_OBSERVED
```

The exact resolver may accept a canonical Service id or explicitly configured alias. It SHALL NOT
use fuzzy, case-folded, suffix, label, or nearest-name matching.

`service.name` without Pod UID linkage is insufficient. Workload name without UID/owner chain is
insufficient. `service.namespace`, `service.version`, `k8s.namespace.name`,
`k8s.deployment.name`, and similar attributes are consistency evidence only.

## 16. Identity Precedence and Conflicts

```text
explicit canonical identity annotation
  > configured versioned mapping
  > qualified OTel Pod-UID/owner-chain linkage
  > name/namespace/label similarity
```

Precedence applies only when other applicable paths agree or are absent. It never suppresses
contradiction.

```text
successful paths resolve same Service/Workload
  -> one association; union evidence; strongest method reported

annotation and configured mapping disagree
  -> CONFLICT; no association

explicit/configured and observed disagree
  -> CONFLICT; no association; retain both evidence chains

multiple Services or Workloads satisfy one path
  -> AMBIGUOUS; no association

only similarity exists
  -> UNRESOLVED; no association
```

Results expose status, method, mapping-rule identity/version, resolved ids where applicable,
supporting/conflicting evidence, and limitations.

## 17. Reconciliation Semantics

The successful public relation is frozen as:

```text
Service -[DEPLOYED_AS]-> Workload
```

It means qualified evidence associates execution of the logical Service with the Workload. It does
not assert entity equivalence, ownership, Bounded Context identity, communication, dependency,
health, availability, locality qualification, or Intent.

Agreeing paths union evidence. Conflicting, ambiguous, or insufficient paths emit no relation.
Infrastructure may establish workload existence. OTel may establish supported runtime interaction
and guarded Service/Workload association. Neither establishes Intent. Selectors, shared namespaces,
network reachability, sidecars, and common labels create no application dependency.

## 18. I3 Exit Gates

I3 requires:

- executable explicit/configured/observed/unresolved/ambiguous/conflict cases;
- exact accepted attribute combinations and consistency checks;
- evidence drill-down through Pod UID and owner chain;
- namespace/cluster collision safety and stable Workload identity across supported Pod replacement;
- service-name-only remains unresolved;
- conflicts/unsupported combinations emit no association artifact;
- Kubernetes-only evidence creates no interaction;
- equivalent exposed REST/MCP semantics preserve qualification under the §28 exposure contract;
- two runs produce byte-identical semantics.

---

# Part III — Conditional Pub/Sub Semantics

## 19. Mandatory I4 Decision Gate

I4 first decides whether generic source-independent Pub/Sub meaning is safe. `DEFER` is valid.

Before Canonical Model implementation, independent evidence SHALL prove:

- Queue, Topic, and Subscription have distinct identities/behavior;
- AsyncAPI Channel is not automatically a broker destination;
- competing consumers and subscription fan-out remain distinguishable;
- namespace/broker identity prevents collision;
- semantics survive two materially different broker models;
- runtime evidence cannot mint destination kind without sufficient evidence;
- existing Queue behavior is backward compatible.

```text
GO
  -> freeze model in ADR/I4 specification
  -> implement and qualify all scenarios

DEFER
  -> record evidence and unsupported cases
  -> create no speculative model extension
  -> continue v0.5.0 without Pub/Sub support
```

## 20. Candidate Model if I4 = GO

```text
Service -[SENDS]-> Queue
Service -[RECEIVES_FROM]-> Queue
Queue   -[CARRIES]-> Message

Service      -[PUBLISHES_TO]-> Topic
Subscription -[SUBSCRIPTION_OF]-> Topic
Service      -[RECEIVES_FROM]-> Subscription
Topic        -[CARRIES]-> Message
```

Pub/Sub names are candidates until I4 `GO` freezes them. Queue, Topic, Subscription, Channel, and a
broker-specific consumer construct SHALL NOT collapse into an unqualified destination.

I4 uses AsyncAPI, OTel, and deterministic broker-semantic fixtures. It adds no live Kafka, Azure
Service Bus, Google Pub/Sub, or Kafka Connect discovery.

## 21. I4 Qualification if GO

Required cases include Queue competing consumers; one/two Topic subscriptions; multiple instances
behind one Subscription; unresolved Topic/Subscription/consumer; subscription-specific dead-letter
handling; same names across namespaces/kinds; conflicting kinds; Kafka Consumer Group without
guessed Subscription equivalence; and runtime observation without declared destination kind.

Required distinctions:

```text
Topic + two subscriptions -> fan-out
Queue + two consumer instances -> no fan-out
same name -> no identity equivalence
insufficient kind evidence -> unresolved
```

`GO` requires zero Queue regression, complete evidence drill-down, preservation of Subscription
paths, no broker-specific false normalization, deterministic positive/negative evaluation, and
byte-identical reruns.

Partitions, lag, delivery guarantees, schema-registry lifecycle, broker administration, live
topology, choreography inference, and messaging Intent remain out of scope.

---

# Part IV — Independent Qualification and Release

## 22. I5 Cross-System Qualification

### 22.1 Frozen validation contract

Before target execution, I5 freezes source/system and upstream identities, independently authored
ground truth, expectation vocabulary, capture/evidence policy, comparison/rerun rules, finding
taxonomy, and the scope-change gate.

Coverage includes I1 source lifecycle, I2 Kubernetes, I3 reconciliation, I4 only if `GO`, and
evidence drill-down for representative claims. At least two materially different independently
authored systems plus deterministic negative fixtures are required.

### 22.2 Finding dispositions

```text
FIX
DEFER
DOCUMENT_UNSUPPORTED
NO_CHANGE
```

A production fix must correct a general defect justified by frozen evidence. Target-specific names,
aliases, heuristics, and fixture exceptions are prohibited. A new Canonical Model family, adapter,
or public tool after validation starts requires an amendment and explicit approval.

### 22.3 Final-candidate revalidation

After fixes, I5 SHALL rerun all scenarios from clean state, run deterministic evaluation twice,
require byte-identical output and zero unexplained facts/guessed identities/silent unsupported
cases, verify provenance, verify inventory/tombstone/failure/scope-change behavior, preserve the
`v0.4` Architecture Answer contract, and freeze one candidate.

```text
I5 exit = FINAL_CANDIDATE_QUALIFIED
```

## 23. Release Identity and Candidate Freeze

I6 keeps distinct:

```text
RELEASE_CANDIDATE_SHA
EVIDENCE_COMMIT_SHA
DECISION_COMMIT_SHA
UNPUBLISHED_CLOSURE_COMMIT_SHA, when applicable
POST_RELEASE_COMMIT_SHA, when applicable
final tag target
final image digest
```

The tag SHALL point to `RELEASE_CANDIDATE_SHA`, not an evidence commit. Every candidate/release
image SHALL inject the full SHA and expose:

```text
producer.build_revision = RELEASE_CANDIDATE_SHA
```

Freeze records candidate SHA, clean state, versions, returned build revision, lock hash,
adapter/mapping versions, Canonical Model version, fixture identities, and image digest where used.
Executable or qualification-relevant changes create a new candidate and reopen affected gates.

## 24. Pre-Publication Qualification

The exact clean-checkout candidate SHALL pass:

```text
lint/format/unit/integration
source-adapter conformance
OpenAPI/AsyncAPI corpus
inventory/scope/tombstone/discovery-failure lifecycle
reimport/conflict/atomicity
Kubernetes discovery
runtime reconciliation
Pub/Sub, only if I4 = GO
deterministic evaluation twice
direct and negotiated MCP regression/equivalence
read-only invariants
dependency/security checks
repository/documentation hygiene
```

```text
semantic mismatches = 0
unexpected canonical facts = 0
guessed identities = 0
unresolved release blockers = 0
repeatability = PASS
producer.build_revision = RELEASE_CANDIDATE_SHA
```

Passing produces `RELEASE_READY`; it does not authorize publication.

## 25. Publication Authority and Workflow

Publication requires separately recorded repository-owner authorization.

```text
mandatory gates fail -> NO_GO
mandatory gates pass -> RELEASE_READY

RELEASE_READY + not authorized for this cycle + unpublished closure
  -> RELEASE_READY_NOT_PUBLISHED

RELEASE_READY + authorization pending
  -> AWAITING_PUBLICATION_DECISION

RELEASE_READY + authorized
  -> publication and final-artifact verification
```

`RELEASE_READY_NOT_PUBLISHED` is a successful technical outcome but SHALL NOT be described as
shipped, released, published, generally available, or post-release verified.

After authorization, I6 SHALL verify tag/candidate identity, record every workflow attempt, verify
revision injection, record final digest, bind SBOM/security disposition to that digest and workflow,
require zero unresolved release-blocking findings, anonymously pull by digest, execute the golden
path, verify tagged source and GitHub Release, and commit post-release closure.

## 26. Published-Image Golden Path

The pulled digest is prepared from a frozen fixture covering OpenAPI, AsyncAPI Queue, Kubernetes,
OTel reconciliation, Pub/Sub only if `GO`, positive identities, negative unresolved/conflicting
identities, and source inventory with `COMPLETE` scope marker.

It SHALL prove:

```text
pulled digest = published digest
producer.build_revision = RELEASE_CANDIDATE_SHA
fixture classification = COMPLETE
expected declared/infrastructure/observed facts
unsupported/unresolved cases preserved
claim evidence and mapping provenance
same-snapshot continuity
direct MCP workflow
negotiated initialization/workflow
disconnect/reconnect
revision fence unchanged across read-only tools
post-run fixture remains COMPLETE
```

A local rebuild or RC image cannot substitute for the published digest.

## 27. Closure and Terminal Outcomes

Unpublished closure records candidate/evidence/decision identities, gates, publication disposition,
limitations, and that no release is claimed. Its commit is `UNPUBLISHED_CLOSURE_COMMIT_SHA`.

```text
RELEASE_READY + NOT_GRANTED + NOT_PUBLISHED + closure committed
  -> RELEASE_READY_NOT_PUBLISHED
```

Published closure records all identities, tag/release, workflow attempts, final digest, security
disposition, anonymous pull, build revision, golden path, tagged source, and limitations.

```text
published + final verification PASS + closure committed
  -> SHIPPED_VERIFIED

published + verification missing/failed
  -> POST_RELEASE_FAILED
```

`AWAITING_PUBLICATION_DECISION` is non-terminal. `NO_GO` and `POST_RELEASE_FAILED` are terminal
failures. A closure commit is not required to embed its own SHA.

---

# Part V — Compatibility, Evidence, and Completion

## 28. Public Surface and Compatibility

`v0.5.0` SHALL NOT add a fourth MCP tool. Existing direct and negotiated workflows remain
operational and equivalent.

New canonical entities, predicates, or variants that cross a public schema boundary SHALL be added
explicitly to the relevant versioned schema before qualification. The increment SHALL record
whether this is backward compatible or needs a schema-version change. Silent widening of a closed
enum or undocumented payload drift is prohibited.

Before implementation and fixture authoring, I2 and I3 SHALL freeze an exposure table for their
claims: exact canonical name/shape, internal-only or public status, REST response location, existing
MCP tool/result field where applicable, schema version, and evidence/limitation representation.
I3's public `DEPLOYED_AS` meaning remains frozen by §17; only its concrete exposure locations are
specified here. Infrastructure claims and `DEPLOYED_AS` MUST NOT be relabeled as application
dependencies to fit an existing response. If an additional MCP tool is necessary, it requires a
separately approved scope amendment. Equivalence gates apply to the same exposed semantics.

Evidence drill-down for every public new claim preserves source, inventory, mapping rule,
observation context, and snapshot continuity. Tool adapters do not infer or rewrite claims.

## 29. Security and Data Handling

The release SHALL preserve the least-privilege, read-only Kubernetes RBAC contract in §14.3;
bounded local document references; no remote Internet `$ref`; no credential, secret, or arbitrary
environment capture; sanitized evidence; zero MCP writes; and dependency/container/SBOM security
checks. If `LIVE_INCLUDED`, qualification SHALL include denied-verb and denied-scope cases and
verify that they produce `PARTIAL`/`FAILED` without state expiration or fallback writes.
`OFFLINE_ONLY` SHALL qualify failed/partial frozen-input and inventory scenarios; it does not
claim live API or RBAC qualification.

`SHIPPED_VERIFIED` requires zero unresolved release-blocking findings bound to the final workflow
and image digest. Candidate/local-image security evidence cannot substitute for this disposition.

## 30. Required Documentation and Evidence

Repository documentation SHALL cover adapter conformance; OpenAPI/AsyncAPI support matrices; source
identity/inventory/replay/tombstones; Kubernetes permissions; I3 identity combinations/conflicts;
I4 `GO`/`DEFER`; limitations; deterministic qualification; and release verification.

Documentation distinguishes supported, qualified, unresolved, unsupported, deferred, and
unverified behavior. Roadmap aspiration is not release evidence.

## 31. Release-Level Definition of Done

Common completion requires I1/I2/I3/I5 gates, a qualified I4 `GO` or defensible `DEFER`, deterministic
coverage of shipped capabilities, machine-visible unsupported/unresolved cases, authoritative
source-removal safety, exact-candidate qualification, and committed candidate/evidence/decision ids.

Successful terminal outcomes:

```text
RELEASE_READY_NOT_PUBLISHED
  = technical qualification + explicit no-publication disposition + unpublished closure

SHIPPED_VERIFIED
  = authorized publication + exact artifacts + final security disposition
    + published-image golden path + post-release closure
```

Permitted unpublished claim:

> **The AIP v0.5.0 candidate completed all mandatory technical qualification gates and is release
> ready, but publication was not authorized and no public v0.5.0 release is claimed.**

Permitted published claim:

> **AIP v0.5.0 expands OpenAPI and AsyncAPI ingestion, adds Kubernetes as the single new discovery
> source family, reconciles infrastructure and runtime evidence through explicit identity guards,
> and includes source-independent Pub/Sub semantics only if independently qualified. Every
> supported claim remains deterministic, evidence-backed, and explicit about unresolved,
> conflicting, or unsupported cases; final artifacts were verified against the exact candidate.**

## 32. Relationship to Later Releases

`v0.5.0` retains placement context but does not claim locality semantics. Locality-aware Current
State remains `v0.6`. OpenAPI, AsyncAPI, Kubernetes, and OTel evidence do not establish Intent.
Explicit Intent remains `v0.7`, followed by Current-to-Intent assessment in `v0.8`.

## 33. Draft 0.1 Decision Register

| Owner | Decision still to freeze | Constraint already fixed here |
|---|---|---|
| I1 | Package interfaces and diagnostic wire schema | Source identity, inventory authority, atomicity, result taxonomy, and behavior cannot change. |
| I2 | Exact infrastructure claim shapes and exposure table; `LIVE_INCLUDED` or `OFFLINE_ONLY` before implementation/fixtures | Offline discovery mandatory; no locality claim, interaction, or name-based AIP Service equivalence. |
| I3 | Concrete REST/existing-MCP exposure locations and schema versions | §§15–17 identity paths, precedence, conflicts, and public `DEPLOYED_AS` meaning remain frozen. |
| I4 | `GO`/`DEFER`; if `GO`, final Topic/Subscription schema | Queue/Topic/Subscription distinctions and multi-broker qualification are mandatory. |
| I5 | Real systems, revisions, expected facts | Two materially different systems plus negative fixtures; target-specific fixes prohibited. |
| I6 | Exact commands and evidence filenames | Candidate/revision/security/publication/terminal-state rules are fixed. |

I3 accepted combinations, precedence, conflict behavior, and `DEPLOYED_AS` are already frozen by
§§15–17 and SHALL NOT be deferred again.

## 34. Draft 0.1 Acceptance Criterion

This draft is ready to split into increment specifications when review confirms:

1. source lifecycle cannot confuse absence with removal;
2. I2 cannot expose locality or infer interaction;
3. I3 identity paths/conflicts are decision-complete;
4. I4 remains conditional and broker-independent;
5. I5 can author independent fixtures from this contract; and
6. I6 distinguishes release readiness from shipped verification.
