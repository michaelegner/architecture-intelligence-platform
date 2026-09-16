# AIP v0.5.0 I2 — Kubernetes Discovery Vertical Slice

**Status:** Draft 0.2 — post-I1 integration amendment; pending acceptance<br>
**Release:** `v0.5.0`<br>
**Increment:** I2<br>
**Parent:** [v0.5.0 release specification](specification.md), especially §§7–8, 14, 28–29<br>
**Dependency:** [I1 Source Ingestion Foundation, Draft 0.3](i1-source-ingestion-foundation.md)<br>
**Reviewed I1 implementation baseline:** `ecc598a5ae57c614172cb1cfe4e76198f4b4a5e6`<br>
**Draft scope disposition:** `OFFLINE_ONLY`

## 1. Purpose and boundaries

I2 adds Kubernetes as the single new discovery-source family in v0.5. It maps bounded frozen
Kubernetes inputs through the I1 seam into deterministic infrastructure entities, claims, and
evidence. It prepares guarded Pod/Workload evidence for I3 without resolving application Service
identity or inferring communication.

The key words MUST, SHALL, REQUIRED, SHOULD, and MAY are normative within this proposed contract.
Draft status does not mean implementation or qualification has passed.

```text
AIP Service != Kubernetes Service != Workload != Pod
WHERE something is != HOW it interacts
selector match != application dependency
declared resource != captured resource
resource presence != running or healthy workload
non-observation != absence
source disappearance != authorized source removal
observed behavior != intent
```

The positive exit capability is:

> Given an explicitly scoped, attributable frozen Kubernetes inventory, AIP establishes bounded
> infrastructure structure with deterministic identities and evidence, preserves unresolved cases,
> and reconciles only the ownership that a complete authorized inventory may change.

## 2. Scope decision

This draft selects `OFFLINE_ONLY` to keep the increment bounded. Acceptance of the specification
records that decision before implementation and qualification fixture authoring.

Required:
- one registered Kubernetes adapter using I1 discovery, validation, mapping, and reconciliation;
- frozen YAML/JSON resource bundles with a versioned inventory envelope;
- explicit cluster/source identity, resource identity, and incarnation handling;
- four infrastructure claim kinds defined in §7;
- deterministic offline qualification and I3 evidence handoff.

Excluded:
- a live Kubernetes client, kubeconfig loading, watches, polling, or cluster writes;
- Helm rendering, Kustomize execution, template evaluation, or remote reference fetching;
- ConfigMaps, Secrets, environment extraction, logs, exec, network probes, and credentials;
- new source families, broker discovery, Pub/Sub semantics, and additional MCP tools;
- application Service creation from Kubernetes metadata, `DEPLOYED_AS`, or OTel correlation;
- locality-qualified projections, health/readiness, reachability, causal flows, and Intent.

Frozen captures can originate from an independently operated exporter; building or operating that
exporter is not an I2 runtime requirement. Qualification must document capture origin and bounds.

A change to `LIVE_INCLUDED` requires a reviewed specification amendment before implementation:
exact capture/completeness rules, limits, failure handling, frozen/live equivalence, and the parent
RBAC gates must be added. In particular, Deployment owner-chain capture needs ReplicaSet read
access; the parent's live permission table would need an explicit corresponding amendment.
Offline qualification SHALL NOT be advertised as live discovery or RBAC qualification.

## 3. Dependency on I1 and implementation entry gate

I2 reuses I1's source descriptors, result taxonomy, inventory authority, tombstones, mapping-context
fingerprint, atomic discovery-run transaction, and deterministic report comparison. It does not
create a parallel lifecycle pipeline or write directly to the graph.

The Draft 0.2 integration review was performed against I1 Draft 0.3 at merge revision
`ecc598a5ae57c614172cb1cfe4e76198f4b4a5e6`. It found that I1's source/adapter protocols and
lifecycle calculation primitives exist, but three contracts I2 depends on are not complete in the
production path:

- the production discovery runner and graph importer are filesystem-specific even though the
  discoverer and adapter protocols are generic;
- discovery does not construct or return a real `SourceInventorySnapshot`, and the commit path does
  not persist or transactionally compare the committed inventory revision;
- the current Canonical Model has neither infrastructure entities nor a first-class unary-claim
  representation.

The resulting integration disposition is:

| Dependency | Draft 0.2 integration finding | Required closure before Kubernetes mapping |
|---|---|---|
| Registration | `SourceDiscoverer` and `SourceAdapterRegistry` are generic; production orchestration constructs filesystem discovery directly. | A source-neutral orchestration path accepts a configured discoverer and registered adapters without a source-kind branch. |
| Identity/replay | Common mapping-context and semantic-digest primitives exist. | Kubernetes registration semantics and adapter/rule versions participate in those existing digests. |
| Inventory | Snapshot/revision/tombstone models and calculations exist, but the production run and commit paths do not carry or persist them end to end. | Every run produces a snapshot; current inventory state and capture audit identity are persisted; predecessor and tombstone checks execute in the atomic commit. |
| Merge | Existing source ownership and conflict primitives are reusable. | Infrastructure entity/claim contributions use those primitives and the Draft 0.2 conflict rules in §7. |
| Evidence | Existing provenance can retain source pointers, but infrastructure entity and unary-claim shapes are absent. | The logical schemas in §7 are implemented without widening a public response. |
| Qualification | Initial-state fixtures exist, while the semantic/audit inventory report path remains incomplete. | Qualification includes committed inventory state and distinct semantic versus capture-specific projections. |

Before any Kubernetes mapping slice begins, the implementation SHALL complete one shared I1
integration slice with these properties:

1. Source-neutral orchestration consumes a configured discoverer plus the adapter registry and
   returns the common discovery-run result. Existing filesystem entry points MAY remain as
   compatibility wrappers.
2. The common commit path consumes that result and MUST NOT instantiate filesystem discovery or
   branch on source kind.
3. Every discovery attempt constructs a real `SourceInventorySnapshot`. The result carries that
   snapshot through planning/reporting, and a successful `COMPLETE` run persists its current
   semantic inventory revision together with its capture/audit identity in the same transaction as
   source reconciliation and authorized removals.
4. The transaction compares any expected predecessor with the currently committed inventory before
   mutation. A mismatch, including null-versus-existing and value-versus-missing, rejects the run
   and preserves the last committed state.
5. Explicit source/scope-transition tombstones are validated against committed inventory and wired
   into production removal authorization. Ordinary same-scope resource withdrawal remains a
   source-owned reconciliation and does not require one tombstone per Kubernetes resource.
6. The canonical layer can carry the logical infrastructure entities, contributions, and unary or
   binary claims frozen in §7 through the same merge, validation, ownership, and reconciliation
   path as other canonical facts.

Package names, Python interfaces, persistence labels, CLI wiring, and diagnostic envelope integration
remain implementation decisions. The requirements above constrain behavior and transaction
boundaries, not function names or graph labels. They must be recorded before executable fixtures
are frozen. A further mismatch with I1 requires an explicit specification correction, not a hidden
adapter workaround or a second reconciliation engine.

## 4. Frozen input and authority contract

### 4.1 Two evidence modes

Each configured Kubernetes source has exactly one immutable evidence mode:

| Mode | Meaning | Allowed qualification |
|---|---|---|
| `DECLARED_MANIFEST` | Attributable resource declarations targeted at an explicitly identified cluster. | Declared infrastructure only; no claim of API presence or execution. |
| `CAPTURED_RESOURCE` | Resource representations captured from an identified Kubernetes API scope. | Presence in that bounded capture, not current liveness or an atomic cluster-wide instant. |

Separate modes use separate configured source IDs. Switching modes under an existing ID is rejected.
Captured UIDs MUST NOT be fabricated for declaration-only resources. Synthetic fixture captures
must be marked synthetic in their provenance and cannot count as independent live-system evidence.

### 4.2 Versioned envelope

The implementation SHALL provide a strict envelope schema equivalent to this shape:

```yaml
apiVersion: aip.dev/v1
kind: KubernetesSourceSnapshot
metadata:
  id: snapshot-example
  revision: snapshot-revision
  producer: attributable-producer
  capturedAt: "2026-09-15T10:00:00Z"
source:
  configuredSourceId: configured-kubernetes-source
  configuredScopeId: configured-kubernetes-scope
  clusterUid: independently-established-cluster-identity
  clusterIdentityEvidenceRef: retained-identity-evidence
  mode: CAPTURED_RESOURCE
scope:
  namespaces: [example]
  resourceTypes:
    - v1/Namespace
    - v1/Pod
    - v1/Service
    - apps/v1/Deployment
    - apps/v1/StatefulSet
    - apps/v1/DaemonSet
    - apps/v1/ReplicaSet
    - networking.k8s.io/v1/Ingress
completeness:
  status: COMPLETE
  authorityRef: configured-authority-record
  expectedPriorInventoryRevision: null
files:
  - path: resources.yaml
    sha256: lowercase-sha256-of-exact-file-bytes
```

All displayed fields are required. `expectedPriorInventoryRevision` is null only for a first import;
successor bundles bind the currently committed inventory revision. The comparison occurs inside the
atomic commit transaction: null is accepted only when no inventory is committed for the configured
scope, and a non-null value is accepted only when it equals the current committed revision. A stale
or racing predecessor is `K8S_STALE_INVENTORY` and commits nothing.

After registration binding and validation of every listed file, one snapshot envelope and all of its
listed resource files become exactly one `LoadedSource` with one `SourceInstanceId`. The envelope is
the source locator and its normalized resource projection is the adapter input. Listed files are
subordinate snapshot artifacts: they retain pointers and byte digests but are never registered,
owned, reconciled, or removed as independent sources.

IDs and attribution fields are non-empty strings. Namespace lists are non-empty, sorted,
duplicate-free explicit names: no wildcard or implicit default namespace. The resourceTypes list is
the exact eight-entry set above. No label filter is supported in Draft 0.2. File paths are unique
normalized relative POSIX paths. Unknown envelope fields and duplicate YAML/JSON keys are rejected.
Wire schema validation precedes mapping.

The configured source registration binds the source/scope IDs, cluster UID, evidence mode,
authorized snapshot producer, and authority record. Envelope values must match it. The authority
record identifies who may declare a complete inventory for this source; an arbitrary file containing
`COMPLETE` is insufficient. Attribution is an explicit configured trust boundary, not cryptographic
verification or a claim that AIP independently observed the cluster.

Cluster identity must be supplied with attributable evidence. Cluster context names, API URLs,
namespace names, or checkout names are insufficient. This contract does not assume Kubernetes has a
universal Cluster object UID. The registration defines and retains the independently established
cluster-identity convention; changing the cluster identity creates a new logical source.

### 4.3 Completeness and ingestion bounds

`COMPLETE` means the authorized bundle exhaustively represents its configured artifact scope.
For captured resources, the producer also attests that every selected resource type/namespace was
successfully enumerated, including empty results, without hidden permission or pagination failure.
It does not mean all resources existed simultaneously or remain present now.

Every listed file must exist and match its digest. All resources must belong to the registered
cluster and selected namespaces; Namespace objects themselves are cluster-scoped and restricted to
those selected names. Out-of-scope resources reject the bundle rather than silently changing scope.
A bundle with no resources can be complete only through an explicit empty file list and the same
authority and predecessor checks. A missing bundle never means an empty bundle.

Limits: at most 256 files, 32 MiB total input bytes including envelope, and 10,000 resource objects.
Files may contain YAML document streams or JSON objects; `v1/List` is a container whose items are
validated individually, not an architecture entity. Nested List containers are rejected. YAML alias
expansion is unsupported, custom tags are rejected, and parser nesting is bounded to 64 levels.
Limit violations are `REJECTED_UNSUPPORTED`; malformed inputs are `REJECTED_INVALID`.

Files are local regular files inside the configured root after normalization and symlink resolution.
Absolute paths, traversal escapes, URL fetches, shell execution, and missing files are prohibited.
Completeness is checked even on a mapping replay no-op.

`PARTIAL` or `FAILED` inputs commit no canonical change and preserve the last successful inventory.
Their sanitized failure reports remain available through I1's audit mechanism.

## 5. Admitted resources and retained fields

| API version / kind | Role |
|---|---|
| `v1/Namespace` | Namespace identity/context; no locality claim. |
| `apps/v1/Deployment` | Workload declaration or captured resource. |
| `apps/v1/StatefulSet` | Workload declaration or captured resource. |
| `apps/v1/DaemonSet` | Workload declaration or captured resource. |
| `v1/Pod` | Pod resource and captured UID evidence. |
| `apps/v1/ReplicaSet` | Internal bridge for the parent's bounded Pod owner-chain requirement only. |
| `v1/Service` | Kubernetes network-service resource, distinct from AIP Service. |
| `networking.k8s.io/v1/Ingress` | Declared routing configuration to Kubernetes Services. |

ReplicaSet is not a fourth supported Workload kind or a new public claim family. Its only mapped
purpose is the Pod → ReplicaSet → Deployment controller chain. Other controller kinds and API
versions require an amendment; unsupported objects are omitted with pointer diagnostics and
`ACCEPTED_WITH_LIMITATIONS`. They cannot authorize a guessed replacement relation.

Allowlisted evidence:
- API version/kind; metadata name/namespace; UID and resourceVersion when present;
- controller owner references: API version, kind, name, UID, and controller flag;
- labels needed by an admitted Service selector, and the exact selector keys/values;
- `architecture-intelligence.io/service-id` on supported Workloads, retained for I3 only;
- Service type and declared ports; Ingress service backend references, host/path/pathType;
- source identity, evidence mode, scope, producer/capture attribution, and source pointers.

Status, managedFields, timestamps embedded in resources, arbitrary annotations, container commands,
environment values, volumes, credentials, and Secret contents are not architecture evidence.
Resource labels/addresses that are retained must be covered by the fixture data-handling review.
Opaque source bytes may be hashed for provenance but are not stored or echoed as evidence.
The adapter emits only allowlisted fragments. Diagnostics never dump rejected resource payloads.

Missing name, missing namespace for a namespaced kind, malformed used fields, or conflicting
duplicate resources reject the source. Identical duplicates merge their source pointers
deterministically. A captured resource requires UID and resourceVersion; absence rejects the
capture. Declarations may omit them and never gain fabricated values.

## 6. Identity, normalization, and replay

Use I1's unambiguous tuple encoding and lowercase SHA-256:

```text
source_kind = kubernetes
SourceInstanceId
  = urn:aip:source:kubernetes:<sha256(configured Kubernetes-source id, cluster UID)>

logical resource key
  = (cluster UID, API group, kind, namespace-or-empty, resource name)

logical resource id
  = urn:aip:k8s-resource:<sha256(logical resource key)>

resource incarnation
  = (logical resource id, captured resource UID)
```

The core API group is the empty string. Namespace objects have an empty namespace component.
API version is retained and validated but does not split identity for the same group/kind.
Names are exact validated Kubernetes names; no case folding, slug conversion, or name equivalence
with application Services is permitted.

Workload IDs are the logical IDs of the three supported controller kinds. Pod/Service/Ingress IDs
use the same typed key. A replacement resource with the same name and a new UID preserves logical
identity while changing incarnation evidence. Old UID links must not resolve against the replacement.

Normalize the allowlisted resource projection, ordering resources by logical key. Map ordering,
file ordering, YAML/JSON choice, and identical duplicates do not affect semantic output. Source
pointers remain provenance and are sorted when multiple files represent one object.

UID and resourceVersion values are capture provenance, not logical identity. Nevertheless, any
changed UID or controller-reference UID MUST trigger owner-chain reevaluation. The Kubernetes
semantic projection includes the resolved incarnation bindings and owner-chain outcomes needed for
that decision; it may not erase identity-relevant UID changes as volatile metadata.
A resourceVersion-only change with identical semantic structure/incarnations is an audit capture
change, not a graph-revision change. Use a deterministic sorted digest of captured UID/resourceVersion
pairs as provider capture revision; do not compare resourceVersion numerically across objects.

The common I1 mapping context includes the active Kubernetes adapter/rule versions and registration
semantics. Document and mapping changes trigger reevaluation. Comparison after reevaluation follows
I1: changed canonical facts, ownership, or answer-visible evidence require reconciliation; audit-only
changes do not. Replay never skips inventory, predecessor, or removal checks.

## 7. Canonical infrastructure contracts

### 7.1 Entity and contribution schema

I2 adds exactly four internal canonical infrastructure entity kinds. They are distinct from all
existing application entities:

| Entity kind | Admitted Kubernetes resource | Additional semantic fields |
|---|---|---|
| `KUBERNETES_WORKLOAD` | Deployment, StatefulSet, or DaemonSet | none beyond the common fields; `resource_kind` distinguishes the three kinds |
| `KUBERNETES_POD` | Pod | none beyond the common fields |
| `KUBERNETES_NETWORK_SERVICE` | Service | `service_type` and a sorted list of ports `(name-or-null, protocol, port)` |
| `KUBERNETES_INGRESS` | Ingress | none beyond the common fields; backend semantics are represented by claims |

Each entity's common logical fields are exactly:

```text
id
entity_kind
cluster_uid
api_group
resource_kind
namespace
name
```

`id` is the §6 logical resource ID. `namespace` is the empty string only for a cluster-scoped
resource. Namespace and ReplicaSet resources remain in the snapshot-bound resource/incarnation
index for validation, context, and owner-chain evidence; I2 does not promote them to additional
canonical entity kinds.

Every source-owned entity contribution carries:

```text
entity_id
source_instance_id
evidence_mode
resource_semantic_digest
evidence_refs
mapping_rule_id
mapping_rule_version
```

`resource_semantic_digest` is the deterministic digest of the resource's allowlisted normalized
semantic projection. It includes every allowlisted value that can affect an entity, claim, identity
handoff, or limitation, including selectors, owner references, ports, Ingress backends, and the
retained explicit Service-ID annotation. It excludes source pointers and capture-only UID,
resourceVersion, capture time, and file-format differences. Those excluded values remain in
evidence, provenance, or the snapshot-bound incarnation index as applicable.

For one logical entity ID, equal semantic digests merge contributions and union evidence
deterministically. Different evidence modes coexist as distinct contributions and never promote a
declaration into an observation. Different semantic digests from simultaneously current sources are
incompatible and reject the affected discovery run as `K8S_RESOURCE_CONFLICT`; no source wins by
precedence. Two current captured contributions that bind the same logical resource to different UIDs
are likewise incompatible incarnations. A resourceVersion-only difference for the same UID and
semantic projection is capture/audit variation, not a semantic conflict.

The exact Python classes, package layout, graph labels, and persistence encoding are implementation
decisions. They MUST preserve these logical fields, contribution boundaries, and conflict outcomes.

### 7.2 Claim schema

All claims carry `kind`, `subject_id`, optional `object_id`, `evidence_refs`, and
`mapping_rule_id/version`. Their internal logical schema version is `kubernetes-infrastructure/1`.
Evidence references are non-empty, sorted, duplicate-free, and resolve within the selected snapshot.
Claim identity is the hash of kind, subject, and object (empty for a unary claim). Evidence mode is
retained per contribution; merging declarations and captures never turns all support into observation.

`WORKLOAD_EXISTS` is a first-class unary claim whose `object_id` is null. Implementations MUST NOT
invent a sentinel entity or self-edge to force it through a binary-relation representation. The
other three claim kinds are binary and both referenced entity IDs must resolve in the canonical
model. Claim contributions use the same source ownership, evidence-mode retention, deterministic
evidence union, and incompatible-current-contribution rejection rules as entity contributions.

| Kind | Subject → object | Exact bounded meaning |
|---|---|---|
| `WORKLOAD_EXISTS` | Workload → none | A supported Workload resource is represented in this source, with declared/captured mode explicit; no assertion of running replicas. |
| `WORKLOAD_OWNS_POD` | Workload → Pod | A captured Pod's unique supported controller chain resolves through matching UIDs to this Workload. |
| `NETWORK_SERVICE_SELECTS_WORKLOAD` | Kubernetes Service → Workload | The Service selector matches at least one captured Pod whose qualified controller chain resolves to this Workload. |
| `INGRESS_ROUTES_TO_NETWORK_SERVICE` | Ingress → Kubernetes Service | An admitted Ingress backend explicitly references this Service and one of its declared ports; configuration only. |

### 7.3 Workload owner chain

Accepted captured chains:
- Pod → StatefulSet;
- Pod → DaemonSet;
- Pod → ReplicaSet → Deployment.

Every hop requires exactly one controller owner reference with `controller: true`, matching
group/kind/name/UID, in the same namespace and the same bundle. Non-controller owner references do
not select the Workload. No suffix stripping or label fallback is allowed.

Missing owner, missing UID match, unsupported chain, or declaration-only input emits no ownership
claim and a limitation diagnostic. Multiple controller owners, cyclic references, or internally
conflicting UID assignments reject the source. A captured standalone Pod can remain as an internal
resource with unresolved Workload; it does not imply a new Workload kind.

### 7.4 Service selection

For a non-empty `spec.selector` string map, all key/value pairs must match a captured Pod's labels
in the Service's namespace. A matching Pod contributes only if §7.3 resolves its owner. The relation
contains evidence for the selector, matched Pod incarnation, and every owner-chain hop.

Multiple Pods in one Workload yield one relation with unioned evidence; multiple resolved Workloads
yield distinct relations. No unique target is guessed. Unresolved matching Pods remain explicit
limitations without suppressing separately proven matches.

Empty/absent selectors and ExternalName Services emit no selection relation. Declaration-only Pod
templates are not substituted for captured Pods. No matching Pod means no relation with a
`NO_QUALIFIED_POD_MATCH` limitation, not evidence that the Service has no backend.
EndpointSlices, ready endpoints, actual traffic, and connectivity are outside this claim.

### 7.5 Ingress backends

Process service backends under defaultBackend and rules/http/paths. Resolve the exact backend
service name within the Ingress namespace; the referenced numeric or named port must match exactly
one declared Service port. Evidence retains the backend pointer and the matching Service port.

Missing Service/port produces an unresolved diagnostic and no relation for that backend. Resource
backends are unsupported. Other resolved backends may still emit claims. Multiple routes to one
Service merge evidence; rule order does not choose an authoritative route.
Ingress annotations, controller implementation, TLS Secrets, and externally observed reachability
are not interpreted. This predicate states routing configuration, never verified packet delivery.

## 8. Source lifecycle and safe removal

I2 has one logical Kubernetes source per registered source ID/cluster, not one source per file or
resource. Resource reconciliation is owned by that source; whole-source removal follows I1.

Every attempt, including failed acquisition, produces an inventory snapshot for reporting and audit.
The current committed inventory state is keyed by discovery scope and retains at least the semantic
inventory revision, scope-definition digest, and a reference to the last successful inventory
capture. Capture identity and optional event-chain identity remain audit data and do not participate
in semantic equality. Failed or partial snapshots may be retained as audit attempts but MUST NOT
replace the current committed inventory.

For a `COMPLETE` run, predecessor comparison, canonical reconciliation, current-inventory update,
and authorized whole-source tombstones execute in one transaction. The predecessor is compared
again inside that transaction even if it was checked during planning. Any change since planning
rejects or retries the entire run without mutation.

A verified COMPLETE successor with the same scope digest may remove that source's contribution for
resources/claims it no longer emits. For declared manifests this withdraws a declaration; it does
not prove API deletion. For captures it withdraws support from that bounded capture; it does not
assert global nonexistence. Other source contributions and evidence remain intact.

Changing namespace filters changes the scope digest. Claims absent from the narrowed scope remain
until an explicit versioned transition/tombstone authorizes removal. A missing file, missing bundle,
permission failure, unknown cluster identity, stale predecessor, or producer mismatch never authorizes
expiration. Stale predecessors reject before commit, including retries racing a newer import.

I1 source tombstones retain their expected inventory revision and attributable reason. An identical
replay without a tombstone is allowed only when its resource semantic digest, mapping context,
scope, and mode also equal the last committed source state; an equal inventory revision alone
does not establish resource equality. A stale destructive transition is not allowed. Explicit
tombstones authorize whole-source removal or a reviewed scope transition; they do not replace the
same-scope source-owned diff for resources omitted by a verified complete successor. All source
contributions in the discovery run commit atomically.

Changing capture incarnation invalidates old Pod-UID resolution. I3 must consume a snapshot-bound
owner index and must not retain an association justified only by a removed incarnation.

## 9. Public exposure and I3 handoff

This draft freezes the following deliberately bounded exposure decision:

| Claim/data | Internal schema/location | REST architecture response | MCP tool/result |
|---|---|---|---|
| Four §7 claim kinds | Canonical infrastructure claims, `kubernetes-infrastructure/1` | Not exposed by I2 | Not exposed by I2 |
| Resource and incarnation index | Snapshot-bound evidence/index | No new endpoint | No new tool |
| Scope/ingestion diagnostics | Existing I1 ingestion report envelope | Follow I1 ingestion reporting where present; no architecture claim payload | Not added to MCP |
| `DEPLOYED_AS` | Not emitted by I2 | I3 owns its schema/exposure | I3 owns its existing-tool integration |
| Locality-qualified relations | Not created | Not exposed | Not exposed |

The internal logical claim fields are fixed by §7. No public ArchitectureAnswer schema version
change is required solely for these internal-only claims. Their inclusion in any future public
payload requires an explicit versioned schema and exposure amendment before implementation.
They MUST NOT leak through generic serialization, existing dependency answers, or a graph tool.

The I3 handoff includes:
- logical Workload/Pod IDs and exact captured UID bindings;
- namespace/cluster and evidence mode;
- owner-chain hop evidence and unresolved/conflicting outcomes;
- retained explicit Service-ID annotation as unqualified input;
- source, inventory, mapping context/rule, and graph snapshot references;
- bundle capture provenance and completeness limitations.

I2 never evaluates the annotation into an AIP Service identity. I3 applies parent §§15–17 and
defines temporal compatibility with its chosen OTel observation. No cross-capture UID join or
freshness assumption is authorized implicitly by this handoff.

## 10. Diagnostics and failure taxonomy

I1 source result statuses remain unchanged. Required diagnostic codes are:

| Code | Outcome |
|---|---|
| `K8S_CLUSTER_IDENTITY_UNRESOLVED` | REJECTED_UNSUPPORTED; preserve state. |
| `K8S_SNAPSHOT_INVALID` | REJECTED_INVALID for shape, digest, or scope mismatch. |
| `K8S_SNAPSHOT_INCOMPLETE` | PARTIAL/FAILED run; no canonical commit. |
| `K8S_STALE_INVENTORY` | REJECTED_CONFLICT; no commit. |
| `K8S_RESOURCE_CONFLICT` | REJECTED_CONFLICT for incompatible duplicate identity/incarnation. |
| `K8S_RESOURCE_UNSUPPORTED` | Omit object; ACCEPTED_WITH_LIMITATIONS. |
| `K8S_OWNER_UNRESOLVED` | Omit ownership; ACCEPTED_WITH_LIMITATIONS. |
| `K8S_OWNER_INVALID` | REJECTED_INVALID for cycle/multiple controllers. |
| `NO_QUALIFIED_POD_MATCH` | Omit selector relation; ACCEPTED_WITH_LIMITATIONS. |
| `K8S_BACKEND_UNRESOLVED` | Omit affected backend relation; ACCEPTED_WITH_LIMITATIONS. |
| `K8S_LIMIT_EXCEEDED` | REJECTED_UNSUPPORTED; no commit. |

Diagnostics contain source/resource IDs where safely known, source pointers, affected claim kind,
and sanitized reasons. They expose no raw Secret/environment contents. Incomplete acquisition is
a run status, not a sixth source acceptance status. Source status for a rejected incomplete envelope
is REJECTED_INVALID; acquisition failure before a source can be loaded is reported at run level.

The exact source/run distinction is:

| Situation | Source result | Run inventory status |
|---|---|---|
| A loaded envelope declares an incomplete capture | `REJECTED_INVALID` | `PARTIAL` |
| A required listed file is missing, has the wrong digest, or cannot be parsed | `REJECTED_INVALID` | `PARTIAL` |
| Acquisition fails before a stable source can be loaded and identified | no source result | `FAILED` |
| An authorized, predecessor-valid complete envelope contains an explicit empty file list | no rejection | `COMPLETE` |

If a run contains multiple configured sources, any source rejection prevents the whole run from
committing, as required by I1; the table does not authorize partial canonical writes.

## 11. Deterministic qualification

Freeze independently authored fixtures and expected claims before target execution. Each fixture
records mode, registration, bundle hashes, initial graph/inventory state, rule versions, expected
claims/limitations, and expected mutations. Require at least:

| Family | Mandatory positive and negative cases |
|---|---|
| Resource identity | Same name across namespaces/clusters/kinds; missing identity; UID replacement; API-version rejection. |
| Workloads | All three supported kinds, declaration-only and captured presence, zero running replicas making no health claim. |
| Owner chains | All three supported paths; ReplicaSet bridge; absent/stale UID; cross-namespace owner; multiple controllers; cycles; unsupported controller. |
| Selectors | One/many Pods, one/many Workloads, partial unresolved matches, absent/empty selector, ExternalName, no matches, declaration-only template. |
| Ingress | Named/numeric ports, default backend, multiple routes, missing Service/port, unsupported resource backend. |
| Normalization | YAML/JSON, map/file/resource ordering, identical duplicates, resourceVersion-only changes, changed UID. |
| Replay | Unchanged bundle and mapping context; changed rules/context; first import versus sequential no-op. |
| Inventory | Complete empty successor, missing bundle/file, digest mismatch, PARTIAL/FAILED, scope narrowing, stale transition, explicit source removal. |
| Ownership | Two sources support one claim; one removed; incompatible current contributions; recreated Pod cannot resolve an old UID. |
| Atomicity | Failure in one Kubernetes object/source preserves all prior contributions and inventories in the run. |
| Bounds/security | Limit and limit+1, nesting, aliases/tags, traversal/symlink escape, unknown producer, secret/environment sentinels absent from outputs. |
| Surface | Internal claims absent from REST/MCP answers; no CALLS/SENDS/RECEIVES_FROM/DEPLOYED_AS/locality claim from Kubernetes alone. |
| Regression | Qualified I1 OpenAPI/AsyncAPI/Manifest ingestion and existing OTel/direct/negotiated MCP behavior preserved. |

Two clean runs with identical initial state and rules must produce byte-identical semantic reports.
A sequential replay instead proves unchanged canonical results, zero semantic mutations, and no
graph-revision advance. Audit captures may differ. Compare sources' evidence modes explicitly.

No live cluster access is needed for the deterministic suite. At least one independently captured,
frozen resource bundle must qualify the owner-chain handoff; authored fixtures alone do not justify
a claim of captured-resource interoperability. Record the upstream system/revision, capture procedure,
and whether the capture is temporally non-atomic. I5 still owns the two-system release qualification.

## 12. Suggested implementation slices

1. Prerequisite I1 seam completion: source-neutral orchestration and commit entry, real inventory
   snapshot production, committed inventory/predecessor persistence, atomic predecessor comparison,
   and production tombstone authorization.
2. Envelope validation, source registration, bounded sanitized loading, and identity.
3. Canonical entity/contribution projection, incarnation index, and unary Workload existence.
4. Owner-chain, selector, and Ingress mapping with evidence.
5. Shared lifecycle replay, conflict, scope/removal, and semantic/audit report qualification.
6. Independent frozen-capture qualification, surface regression, and I3 handoff.

These slices do not authorize new source families or live discovery. Package layout and exact
commands are recorded after the I1 integration gate; no second reconciliation engine is permitted.
No Kubernetes mapping slice starts until slice 1 has executable acceptance evidence against the
shared filesystem path as well as the new source-neutral path.

## 13. Definition of Done and release relationship

I2 is complete only when:
- this draft's scope, claim, and exposure decisions have been reviewed and accepted;
- the I1 implementation integration check is committed with its tested revision;
- the internal versioned schemas and registration/envelope validation are executable;
- all mandatory §11 cases pass with zero guessed identities, unsupported positive claims, or
  unauthorized expirations;
- evidence mode, snapshot continuity, and sanitized provenance survive persistence and handoff;
- regressions pass and no new public MCP tool or architecture claim exposure is introduced;
- limitations and OFFLINE_ONLY support wording are published in repository documentation;
- candidate, rule/schema, fixture, report, and evidence revisions are recorded.

I2 completion is not release publication or SHIPPED_VERIFIED. I3/I4 disposition, I5 independent
qualification, and I6 exact-artifact release/post-release gates remain required by the parent.

## 14. References and review record

Parent and I1 contracts take precedence over implementation convenience. This draft was prepared
against parent blob `96df1cbef2f096f016369b129e93d69fae41362a` and I1 blob
`3f3651353354c360952ab85dfc01d3ab4b17bea6`. These identify drafting inputs, not implementation
candidates or qualification evidence.

**Draft 0.2 integration amendment:** I1 was reviewed after merge at
`ecc598a5ae57c614172cb1cfe4e76198f4b4a5e6` (PR #187), governed by I1 Draft 0.3. The review retained
the original OFFLINE_ONLY, authority, identity, claim-meaning, exposure, and qualification decisions.
It added the §3 prerequisite slice because production orchestration remained filesystem-specific and
the normative I1 inventory snapshot/predecessor lifecycle was present only as disconnected models,
calculations, and unit-level evidence. It also froze §7's logical infrastructure entity,
contribution, unary-claim, and conflict contracts because the implemented Canonical Model could not
yet represent them. Exact Python APIs and graph labels remain implementation decisions.

Kubernetes reference semantics:
- [Object names and IDs](https://kubernetes.io/docs/concepts/overview/working-with-objects/names/):
  distinguish resource names from object incarnations.
- [Owners and dependents](https://kubernetes.io/docs/concepts/overview/working-with-objects/owners-dependents/):
  owner references and namespace constraints.
- [Services](https://kubernetes.io/docs/concepts/services-networking/service/):
  selectors target Pods; selectorless Services require separate handling.
- [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/):
  service backend references are routing configuration.

Review must explicitly confirm OFFLINE_ONLY, the internal-only exposure boundary, the bounded
ReplicaSet bridge, and the envelope's configured authority model. Implementation-specific wiring
must satisfy the Draft 0.2 integration gate; further semantic changes require a reviewed amendment.
