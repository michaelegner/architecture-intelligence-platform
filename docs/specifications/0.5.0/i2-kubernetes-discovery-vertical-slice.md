# AIP v0.5.0 I2 — Kubernetes Discovery Vertical Slice

**Status:** Draft 0.1 — proposed contracts; pending review and I1 integration check  
**Release:** `v0.5.0`  
**Increment:** I2  
**Parent:** [v0.5.0 release specification](specification.md), especially §§7–8, 14, 28–29  
**Dependency:** [I1 Source Ingestion Foundation, Draft 0.2](i1-source-ingestion-foundation.md)  
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

Before I2 implementation starts, record an integration check against the implemented I1 revision:

| Dependency | Required confirmation |
|---|---|
| Registration | A new source kind can register without a hard-coded orchestration branch. |
| Identity/replay | Kubernetes normalization can contribute to the common mapping context and semantic digest. |
| Inventory | Explicit complete snapshots, failure preservation, scope transitions, and stale tombstones work. |
| Merge | Ownership from multiple sources survives removal of one owner; incompatible current contributions conflict. |
| Evidence | Resource pointers, sanitized context, revision/capture identities, and limitations can be retained. |
| Qualification | Initial-state fixtures and semantic/audit report separation are available. |

Package names, Python interfaces, persistence labels, CLI wiring, and diagnostic envelope integration
remain implementation decisions. They must be recorded before executable fixtures are frozen.
A mismatch with I1 requires an explicit specification correction, not a hidden adapter workaround.

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
successor bundles bind the currently committed inventory revision. IDs and attribution fields are
non-empty strings. Namespace lists are non-empty, sorted, duplicate-free explicit names: no wildcard
or implicit default namespace. The resourceTypes list is the exact eight-entry set above. No label
filter is supported in Draft 0.1. File paths are unique normalized relative POSIX paths. Unknown
envelope fields and duplicate YAML/JSON keys are rejected. Wire schema validation precedes mapping.

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

## 7. Canonical claim contracts

All claims carry `kind`, `subject_id`, optional `object_id`, `evidence_refs`, and
`mapping_rule_id/version`. Their internal logical schema version is `kubernetes-infrastructure/1`.
Evidence references are non-empty, sorted, duplicate-free, and resolve within the selected snapshot.
Claim identity is the hash of kind, subject, and object (empty for a unary claim). Evidence mode is
retained per contribution; merging declarations and captures never turns all support into observation.

| Kind | Subject → object | Exact bounded meaning |
|---|---|---|
| `WORKLOAD_EXISTS` | Workload → none | A supported Workload resource is represented in this source, with declared/captured mode explicit; no assertion of running replicas. |
| `WORKLOAD_OWNS_POD` | Workload → Pod | A captured Pod's unique supported controller chain resolves through matching UIDs to this Workload. |
| `NETWORK_SERVICE_SELECTS_WORKLOAD` | Kubernetes Service → Workload | The Service selector matches at least one captured Pod whose qualified controller chain resolves to this Workload. |
| `INGRESS_ROUTES_TO_NETWORK_SERVICE` | Ingress → Kubernetes Service | An admitted Ingress backend explicitly references this Service and one of its declared ports; configuration only. |

### 7.1 Workload owner chain

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

### 7.2 Service selection

For a non-empty `spec.selector` string map, all key/value pairs must match a captured Pod's labels
in the Service's namespace. A matching Pod contributes only if §7.1 resolves its owner. The relation
contains evidence for the selector, matched Pod incarnation, and every owner-chain hop.

Multiple Pods in one Workload yield one relation with unioned evidence; multiple resolved Workloads
yield distinct relations. No unique target is guessed. Unresolved matching Pods remain explicit
limitations without suppressing separately proven matches.

Empty/absent selectors and ExternalName Services emit no selection relation. Declaration-only Pod
templates are not substituted for captured Pods. No matching Pod means no relation with a
`NO_QUALIFIED_POD_MATCH` limitation, not evidence that the Service has no backend.
EndpointSlices, ready endpoints, actual traffic, and connectivity are outside this claim.

### 7.3 Ingress backends

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
does not establish resource equality. A stale destructive transition is not allowed. Concurrent plans must compare their expected committed state at commit
and retry/reject if it changed. All source contributions in the discovery run commit atomically.

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

1. Envelope validation, source registration, bounded sanitized loading, and identity.
2. Canonical resource projection, incarnation index, and Workload existence.
3. Owner-chain, selector, and Ingress mapping with evidence.
4. I1 lifecycle integration, replay, conflict, and scope/removal qualification.
5. Independent frozen-capture qualification, surface regression, and I3 handoff.

These slices do not authorize new source families or live discovery. Package layout and exact
commands are recorded after the I1 integration gate; no second reconciliation engine is permitted.

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
remains provisional until I1 qualification; semantic changes require a reviewed amendment.
