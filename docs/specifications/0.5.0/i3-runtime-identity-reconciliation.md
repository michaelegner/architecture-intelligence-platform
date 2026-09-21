# AIP v0.5.0 I3 — Runtime Identity Reconciliation and `DEPLOYED_AS`

**Status:** Draft 0.4 — public Architecture Knowledge adapter consolidation  
**Target release:** `v0.5.0`  
**Release increment:** I3 — Deeper Runtime Discovery and Cross-Source Reconciliation  
**Target repository path:** `docs/specifications/0.5.0/i3-runtime-identity-reconciliation.md`  
**Governing specification:** [`specification.md`](specification.md), especially §§15–18 and §28  
**Preceding increment:** I2 — Kubernetes Discovery Vertical Slice, complete  
**I2 merge baseline:** `ae662b1255d71e35e59c8ca0d67b0bec3b4d99d6` (PR #209)  
**I2 qualified candidate:** `d82a0fa1190f485482ab2ce2262e124a1280049d`  
**I2 completion record:** [`i2-completion-record.md`](i2-completion-record.md)

---

## 1. Purpose

I1 established the evidence-preserving source/discovery lifecycle.

I2 established bounded Kubernetes infrastructure facts while deliberately refusing to infer an
application Service from Kubernetes names, labels, selectors, placement, or co-location. It also
retained the explicit `architecture-intelligence.io/service-id` workload annotation as **unqualified
input for I3**, rather than interpreting it itself.

I3 is the first increment allowed to reconcile those infrastructure facts with declared AIP Services
and OpenTelemetry runtime identity evidence.

The positive exit capability is:

> **Given an existing declared AIP Service, a current I2 Workload, and one or more of the three
> explicitly admitted identity paths, AIP can establish a deterministic, evidence-backed
> `Service -[DEPLOYED_AS]-> Workload` association, or report conflict/ambiguity/unresolved status
> without guessing.**

The governing distinction remains:

```text
Service != Kubernetes Service != Workload != Pod

WHERE something is != HOW it interacts

DEPLOYED_AS != CALLS
DEPLOYED_AS != SENDS
DEPLOYED_AS != RECEIVES_FROM

deployment association != entity equivalence
deployment association != ownership
deployment association != locality qualification
deployment association != health/readiness
deployment association != Intent
```

I3 does not turn Kubernetes into an application-dependency source. It adds one bounded
cross-source identity reconciliation capability.

---

## 2. Normative language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

The parent specification §§15–17 already freezes:

1. the three successful identity paths;
2. their ordering for reporting;
3. conflict-over-precedence behavior; and
4. the meaning of the public `DEPLOYED_AS` relation.

This increment specification SHALL NOT replace those decisions with a different identity strategy.

---

## 3. Entry baseline and integration gate

I3 starts from the merged I2 implementation at
`ae662b1255d71e35e59c8ca0d67b0bec3b4d99d6`.

The following I2 handoff is assumed executable and queryable:

```text
InfrastructureEntity.id
InfrastructureEntity.cluster_uid
InfrastructureEntity.namespace
InfrastructureEntity.resource_kind

InfrastructureContribution.source_instance_id
InfrastructureContribution.evidence_mode
InfrastructureContribution.captured_resource_uid
InfrastructureContribution.service_id_annotation
InfrastructureContribution.mapping_rule_id
InfrastructureContribution.mapping_rule_version

InfrastructureClaim(kind = WORKLOAD_OWNS_POD)
InfrastructureClaim.evidence_refs

CurrentInventory / inventory revision and capture identity
Kubernetes Evidence / Provenance
```

Before a positive `DEPLOYED_AS` implementation is merged, I3 SHALL prove that:

- the current I2 Workload/Pod/owner-chain state can be read without widening I2's internal exposure
  accidentally;
- the existing exact OTel Service resolver can distinguish a declared Service from an
  `OBSERVED_ONLY` minted Service;
- bounded Kubernetes resource identity attributes can be retained from OTLP without retaining the
  raw Resource, arbitrary labels/annotations, environment variables, baggage, or span payloads; and
- any configured Service↔Workload mapping that affects a public answer is bound to snapshot identity
  and evidence.

A discovered mismatch with those seams requires an explicit I3 correction. It MUST NOT be hidden in
one adapter as an ad-hoc workaround.

---

## 4. Scope and non-goals

### 4.1 In scope

I3 SHALL deliver:

1. exact Path A — explicit workload annotation;
2. exact Path B — versioned configured Service↔Workload mapping;
3. exact Path C — qualified OTel Pod-UID → I2 Pod → owner-chain Workload linkage;
4. deterministic cross-path agreement/conflict reduction;
5. a public `DEPLOYED_AS` claim projection;
6. bounded public Workload references required by that claim;
7. snapshot-bound evidence drill-down for every public deployment claim;
8. public-adapter consolidation around `ArchitectureIntelligenceService`: REST parity for the
   existing dependency, drift, and bounded evidence-resolution capabilities, standard negotiated
   MCP as the sole public MCP transport, and retirement of the v0.4.x direct MCP envelope;
9. the new deployment REST view plus deployment integration into the existing negotiated
   `get_service_dependencies` MCP tool without adding a fourth tool;
10. explicit schema versioning for the widened public contract;
11. deterministic qualification and an I3 completion record.

### 4.2 Non-goals

I3 SHALL NOT add:

```text
new discovery-source families
live Kubernetes discovery
new MCP tools
generic graph/Cypher access
service-mesh discovery
container identity as a new canonical entity
Node identity as a new canonical entity
Kubernetes Service == AIP Service equivalence
name/label/namespace/co-location inference
locality-qualified Current-State claims
health/readiness/availability semantics
causal runtime flow analysis
Intent
Current↔Intent assessment
historical architecture trajectories
policy enforcement
architecture mutation/remediation
LLM-based identity resolution
```

I4 still owns Pub/Sub semantic expansion. I5 still owns independent two-system release
qualification.

---

## 5. Architecture boundary: reconciliation is cross-source, not adapter-owned

No individual source adapter has enough authority to create `DEPLOYED_AS`.

Therefore:

> **`DEPLOYED_AS` SHALL be produced by one deterministic cross-source reconciliation projection over
> already-committed source evidence. Kubernetes and OTel adapters remain sources of evidence, never
> the sole owners of the cross-source conclusion.**

The conceptual flow is:

```text
Declared Services
        \
         \
I2 Kubernetes facts ----> Service/Workload Reconciliation ----> DEPLOYED_AS projection
         /
        /
OTel runtime identity observations

Configured mapping artifact -------------------------------^
```

I3 SHALL NOT introduce a second ingestion/reconciliation engine parallel to I1/I2.

The preferred implementation shape is a read-side projection using a stable snapshot, analogous to
the existing Architecture Intelligence dependency projection. A materialized Neo4j
`DEPLOYED_AS` relationship is **not required** by I3 and SHALL NOT be introduced merely for
convenience.

If implementation later demonstrates that materialization is necessary, that is a reviewed
specification amendment because it introduces ownership/expiry/write semantics not needed by this
contract.

---

## 6. Reconciliation identities and rule version

The I3 reconciliation rule identity is frozen as:

```text
service-workload-reconciliation@1
```

A successful public claim is identified by semantic pair, not evidence path:

```text
deployment_claim_id
  = aip:claim:v1:
    sha256(
      "DEPLOYED_AS",
      canonical Service id,
      logical Workload id
    )
```

Changing evidence method without changing the Service/Workload pair does not create a different
semantic claim id.

The reconciliation context SHALL bind at least:

```text
service-workload-reconciliation rule id/version
configured Service↔Workload mapping artifact identity + content digest
active OTel Kubernetes-resource normalization rule/version
active I2 Kubernetes mapping rule/version
public snapshot canonicalization version
```

A public answer MUST NOT depend on a configuration/rule value that is absent from its snapshot
identity.

---

## 7. Path A — explicit workload annotation

I3 evaluates I2's retained field:

```text
architecture-intelligence.io/service-id
```

Successful Path A requires:

```text
Workload is one of:
  Deployment
  StatefulSet
  DaemonSet

annotation value is a full canonical AIP Service id
annotation resolves by exact equality to exactly one existing declared Service
```

Result:

```text
RESOLVED_EXPLICIT
```

Rules:

- no trimming, slug conversion, case folding, suffix matching, namespace matching, or fuzzy matching;
- an annotation naming a missing Service is `UNRESOLVED`;
- multiple current contributions for the same logical Workload carrying the same annotation agree;
- multiple current contributions carrying different non-null annotations are `CONFLICT`;
- a contribution with no annotation does not contradict a contribution with one annotation;
- I3 never changes the Workload's logical identity based on the annotation;
- I3 never creates a new Service from the annotation.

Path A may use either I2 evidence mode:

```text
DECLARED_MANIFEST
CAPTURED_RESOURCE
```

The evidence mode remains visible in drill-down so consumers can distinguish a declaration from an
API capture.

---

## 8. Path B — configured identity mapping

### 8.1 Mapping artifact

Path B uses one local, versioned mapping artifact. The initial schema is equivalent to:

```yaml
apiVersion: aip.dev/v1
kind: ServiceWorkloadIdentityMappings
metadata:
  id: v0.5.0-service-workload-identities
  revision: <non-empty version/revision>
mappings:
  - mappingId: checkout-runtime
    serviceId: service:checkout
    kubernetesSourceId: checkout-cluster
    clusterUid: 599e90a5-7ab8-426f-807f-92a65dcc8822
    workload:
      apiGroup: apps
      kind: Deployment
      namespace: checkout
      name: checkout
```

Required properties:

```text
metadata.id
metadata.revision
mappingId
full canonical serviceId
configured Kubernetes source id
cluster UID
api group
workload kind
namespace
workload name
```

Supported workload kinds are exactly:

```text
Deployment
StatefulSet
DaemonSet
```

Unknown fields are rejected. Remote references, environment substitution, templating, shell
execution, and implicit aliases are prohibited.

### 8.2 Mapping semantics

A successful mapping requires:

- `serviceId` resolves to exactly one existing declared AIP Service;
- the configured Kubernetes source id and cluster UID identify the current I2 source;
- the exact `(apiGroup, kind, namespace, name)` identifies exactly one current I2 Workload.

Result:

```text
RESOLVED_CONFIGURED
```

A mapping to a missing Service or missing Workload is `UNRESOLVED`.

Two mapping entries that target the same Workload and different Services are `CONFLICT`; ordering in
the file never selects a winner.

Identical duplicate mappings are normalized deterministically.

### 8.3 Mapping evidence

The mapping artifact is evidence, not merely process configuration.

Each mapping entry SHALL have deterministic evidence identity bound to:

```text
mapping artifact id
mapping artifact revision
mapping artifact content digest
mappingId
```

The exact stored representation is an implementation choice, but the public evidence record SHALL
identify those four values and a sanitized relative source locator.

Changing the mapping artifact content SHALL change the I3 reconciliation context and public snapshot
identity even if no source document or Kubernetes bundle changes.

---

## 9. Path C — qualified OTel/Kubernetes linkage

Path C is deliberately stronger than `service.name` correlation alone.

All required conditions must hold.

### 9.1 Required OTel identity evidence

The OTel Resource must contain:

```text
service.name
k8s.pod.uid
deployment.environment.name
```

The Resource MAY additionally contain the bounded consistency attributes in §9.3.

`service.name` alone is insufficient.

`k8s.pod.name` without `k8s.pod.uid` is insufficient.

A Workload name without Pod UID + I2 owner-chain evidence is insufficient.

### 9.2 Exact Service resolution

`service.name` is passed through the existing exact Service resolver.

Path C succeeds only if the result is an existing **declared** AIP Service.

A resolver result that would mint or reuse an `OBSERVED_ONLY` Service is not a successful I3
identity path.

The existing exact resolver may use:

```text
exact service.namespace + service.name
unique exact service.name
explicitly configured alias
```

An alias is admissible only when its target is one existing declared Service and the alias
configuration identity/version is bound to the reconciliation context.

No fuzzy/case-folded/suffix/nearest-name matching is permitted.

### 9.3 OTel Kubernetes-resource allowlist

I3 widens the retained OTel **Resource identity** allowlist only by these attributes:

```text
k8s.pod.uid                 REQUIRED for Path C
k8s.pod.name                optional consistency evidence
k8s.namespace.name          optional consistency evidence
k8s.cluster.uid             optional consistency evidence

k8s.deployment.name         optional consistency evidence
k8s.statefulset.name        optional consistency evidence
k8s.daemonset.name          optional consistency evidence
```

The existing retained Service attributes remain:

```text
service.name
service.namespace
service.version
service.instance.id
deployment.environment.name
```

The Kubernetes attribute names above follow OpenTelemetry Kubernetes resource semantic conventions.
I3 does not adopt the broader OTel entity model; it admits only this bounded attribute set.

The following remain excluded:

```text
arbitrary k8s labels
arbitrary k8s annotations
container environment
container command/args
pod IP / host IP
Node metadata
volumes
Secrets
baggage
raw Resource payload
unbounded span attributes
```

### 9.4 Bounded runtime identity observation

The OTLP path SHALL persist a bounded runtime **resource identity observation** independently of
whether the same span produces a supported HTTP/messaging architecture interaction.

It contains only what I3 needs:

```text
service.name
service.namespace
service.version
environment  # normalized from deployment.environment.name

k8s.pod.uid
optional §9.3 consistency attributes

first_seen
last_seen
observation_count

conflicting_consistency_attributes  # names of §9.6 attributes that disagreed within this bucket

OTel source/evidence identity
normalization rule/version
```

It is not itself `DEPLOYED_AS`, `CALLS`, `SENDS`, or `RECEIVES_FROM`.

It SHALL use the existing deterministic daily evidence-bucket convention or an equivalently
deterministic bounded identity. Trace/span ids are not part of public semantic identity.

Merging two observations into the same bucket SHALL NOT silently erase or overwrite disagreeing
consistency-attribute evidence (§9.6 requires a directly contradictory value to surface as
`CONFLICT`, not be lost at persistence time):

```text
for each optional §9.3/§9.6 consistency attribute (service.version and the six k8s.* attributes -
service.namespace is excluded, since it is part of this bucket's own identity and so cannot differ
within one bucket by construction):

  existing non-null, seed null          -> keep the existing value (a missing attribute on one
                                            observation is not itself a limitation, per §9.6)
  existing null, seed non-null          -> adopt the seed's value
  existing non-null, seed non-null,
    equal                               -> keep the (shared) value
  existing non-null, seed non-null,
    different                           -> the merged value becomes null, and the attribute's name
                                            is added to conflicting_consistency_attributes
                                            (sorted, deduplicated, monotonic - once an attribute is
                                            flagged for a bucket, it stays flagged for that bucket,
                                            even if a later observation's value happens to agree
                                            with a subsequent reconciled value)
```

A later slice's Path C evaluation SHALL treat a non-empty `conflicting_consistency_attributes` the
same as a directly observed §9.6 contradiction (`CONFLICT`), not as a merely-missing attribute.

### 9.5 Pod and Workload resolution

Within the selected current I2 state:

```text
k8s.pod.uid
  -> exactly one current CAPTURED_RESOURCE Pod contribution
  -> exactly one WORKLOAD_OWNS_POD owner-chain claim
  -> exactly one supported Workload
```

Path C requires I2 evidence mode:

```text
CAPTURED_RESOURCE
```

`DECLARED_MANIFEST` cannot qualify Path C because the observed Pod incarnation must be bound through
a real captured UID.

If Pod UID resolves to zero Pods:

```text
UNRESOLVED
```

If it resolves to multiple current Pods or multiple supported Workloads:

```text
AMBIGUOUS
```

No name-based fallback is attempted.

### 9.6 Consistency attributes

When present, each optional attribute must agree with the already-resolved identities.

```text
service.namespace
  -> if the declared Service has a namespace, exact equality required

service.version
  -> if both observed and declared values are non-null, exact equality required

k8s.namespace.name
  -> exact equality with resolved Pod/Workload namespace

k8s.cluster.uid
  -> exact equality with selected I2 cluster UID

k8s.pod.name
  -> exact equality with resolved Pod name

k8s.deployment.name
  -> if resolved Workload kind = Deployment, exact equality with Workload name;
     otherwise contradictory

k8s.statefulset.name
  -> same rule for StatefulSet

k8s.daemonset.name
  -> same rule for DaemonSet
```

A directly contradictory consistency attribute makes the observed path `CONFLICT`; it is not silently
ignored.

A missing optional consistency attribute is not a limitation by itself.

### 9.7 Observation-context compatibility

Path C SHALL evaluate the persisted bounded runtime identity observation with the same exact
environment/window semantics on every implementation path. It SHALL NOT use an undefined synthetic
"observation timestamp" or treat the daily bucket as a continuous interval.

For one persisted runtime identity observation, Path C applicability is:

```text
environment is present
AND environment == observation_context.environment       # exact equality

AND last_seen is present
AND window_start <= last_seen <= window_end              # inclusive bounds

AND current I2 CAPTURED_RESOURCE envelope capturedAt is present
AND window_start <= capturedAt <= window_end             # inclusive bounds
```

The OTel receiver's retained `environment` value is the normalized
`deployment.environment.name` Resource attribute required by parent §15.3. No alternate
environment attribute, wildcard, case folding, or alias is admitted.

`last_seen` is the **decisive runtime timestamp** for I3 window applicability. This intentionally
matches AIP's existing declared-versus-observed qualification rule. `first_seen` and
`observation_count` remain evidence metadata but SHALL NOT independently make an observation match
a requested window.

The outcomes are frozen as:

```text
deployment.environment.name absent
  -> UNRESOLVED
  -> DEPLOYMENT_EVIDENCE_INCOMPLETE

environment != observation_context.environment
  -> UNRESOLVED
  -> DEPLOYMENT_ENVIRONMENT_MISMATCH

last_seen absent or outside [window_start, window_end]
  -> UNRESOLVED
  -> DEPLOYMENT_TEMPORAL_MISMATCH

capturedAt absent or outside [window_start, window_end]
  -> UNRESOLVED
  -> DEPLOYMENT_TEMPORAL_MISMATCH
```

An environment mismatch is not a contradictory Service↔Workload identity claim; it means that the
runtime observation is not applicable to the requested observation context.

Path A and Path B remain independently evaluable because they do not claim runtime observation.
However, the public deployment view still requires Observation Context so an applicable Path C can
agree with or contradict them.

This rule deliberately avoids an arbitrary "N hours of skew" constant. A future historical/locality
release may introduce richer temporal continuity. I3 does not.

---

## 10. Cross-path reduction, precedence, and conflict

The parent ordering is retained:

```text
RESOLVED_EXPLICIT
  > RESOLVED_CONFIGURED
  > RESOLVED_OBSERVED
  > similarity
```

Similarity is never a successful path.

Precedence chooses the **reported strongest method only after agreement has been established**.
It never chooses a winner between contradictory identities.

### 10.1 Agreement

```text
all applicable successful paths resolve the same (Service, Workload)
  -> one DEPLOYED_AS claim
  -> union evidence
  -> resolution_method = strongest successful method
  -> supporting_methods = every agreeing successful method
```

Canonical supporting-method order is:

```text
RESOLVED_EXPLICIT
RESOLVED_CONFIGURED
RESOLVED_OBSERVED
```

### 10.2 Conflict

Examples:

```text
annotation -> Service A
mapping    -> Service B

annotation -> Service A
observed   -> Service B

mapping    -> Service A
observed   -> Service B
```

Result:

```text
CONFLICT
no DEPLOYED_AS claim
retain both/all evidence chains
```

### 10.3 Ambiguity

Examples:

```text
one OTel service.name resolves to multiple declared Services
one Pod UID resolves to multiple current Pod incarnations
one Pod owner chain resolves to multiple supported Workloads
multiple successful observed identities for one current Workload disagree within the same window
```

Result:

```text
AMBIGUOUS
no DEPLOYED_AS claim
```

### 10.4 Unresolved

Examples:

```text
annotation names no declared Service
mapping target does not exist
service.name resolves only to OBSERVED_ONLY Service
Pod UID not found
only Workload/service name similarity exists
Path C capture/window is temporally incompatible
```

Result:

```text
UNRESOLVED
no DEPLOYED_AS claim
```

### 10.5 Same-path multiplicity and multi-Service Workloads

I3 does not introduce a container/sidecar submodel.

The outcome taxonomy is frozen:

```text
more than one Service or Workload satisfies one identity path
  -> AMBIGUOUS

two or more distinct successful identity paths resolve contradictory identities
  -> CONFLICT

one Path C consistency attribute directly contradicts the already-resolved Service/Workload
  -> CONFLICT
```

Therefore, multiple distinct declared Services satisfying one Path C runtime identity is always
`AMBIGUOUS`, never `CONFLICT`.

If one current logical Workload receives contradictory identities from distinct paths — for example
Path A resolves Service A while Path C resolves Service B — the cross-path result is `CONFLICT`.

No `DEPLOYED_AS` claim is emitted for either outcome.

Supporting multiple application Services intentionally sharing one Workload requires a later reviewed
model amendment.

---

## 11. Public Workload reference

I3 exposes a bounded Workload reference without making I2's full infrastructure graph public.

Public shape:

```text
WorkloadRef
  id
  type = WORKLOAD
  name
  workload_kind = DEPLOYMENT | STATEFULSET | DAEMONSET
  namespace
```

Rules:

- `id` is the existing I2 logical Workload id;
- `namespace` is identity context, not a locality qualification;
- cluster UID, Pod UID, source inventory, resource UID, and owner-chain details remain evidence
  drill-down, not fields of the relation target;
- Kubernetes Service, Pod, ReplicaSet, Ingress, and Namespace do not become new public entity types
  in I3.

---

## 12. Public deployment claim

A successful association is represented as:

```text
DeploymentClaim
  claim_id
  subject: EntityRef(type = SERVICE)
  predicate = DEPLOYED_AS
  object: WorkloadRef
  resolution_method
  supporting_methods[]
  reconciliation_rule_id
  reconciliation_rule_version
  evidence_refs[]
```

Invariants:

```text
subject.type == SERVICE
object.type == WORKLOAD
predicate == DEPLOYED_AS
evidence_refs is non-empty, sorted, deduplicated
supporting_methods is non-empty, sorted by §10.1 strength
resolution_method == first(strongest) supporting method
reconciliation_rule_id == service-workload-reconciliation
reconciliation_rule_version == 1
```

`DEPLOYED_AS` means only:

> Qualified evidence associates execution/deployment identity of the logical AIP Service with the
> identified Kubernetes Workload.

It does not mean:

```text
Service == Workload
Service owns Workload
Workload calls anything
same namespace implies dependency
same Workload implies same Bounded Context
healthy
available
ready
reachable
locality-qualified
Intent-compliant
```

---

## 13. Public resolution result

Resolved and non-resolved outcomes SHALL be inspectable without fabricating a claim.

### 13.1 Reconciliation candidate groups

I3 produces exactly one `DeploymentResolution` per canonical **reconciliation candidate group**.

The group key is chosen deterministically:

```text
existing Workload resolved by one or more applicable paths:
  group_key = "workload:" + Workload.id

configured mapping whose exact Workload target is absent:
  group_key =
    "mapping:"
    + canonical-json({
        "artifact_id": mapping artifact id,
        "artifact_revision": mapping artifact revision,
        "mapping_id": mappingId
      })

OTel runtime identity observation whose Pod UID cannot resolve to exactly one current Workload:
  group_key = "otel:" + OTel runtime-identity evidence id
```

If an OTel observation resolves to a current Workload, it joins that Workload's `workload:<id>`
group rather than creating a separate OTel group.

Annotation evidence always belongs to an existing Workload group because the annotation is retained
on an I2 Workload contribution.

The mapping form SHALL use AIP's existing deterministic canonical-JSON utility. Its structured
object encoding, not delimiter concatenation, is normative. Therefore delimiter-bearing values such
as `:`, `/`, `|`, or Unicode characters in any mapping identity field cannot change tuple
boundaries or collide with a different `(artifact_id, artifact_revision, mapping_id)` tuple.

No implementation may replace this with separator-based string concatenation unless a future reviewed
specification proves an injective escaping scheme.

Identical group keys are reduced exactly once. Input/source ordering cannot create additional public
resolutions.

### 13.2 Resolution identity

`resolution_id` identifies one exact snapshot-bound evaluation:

```text
resolution_id
  = aip:deployment-resolution:v1:
    sha256(
      canonical-json({
        snapshot_id,
        observation_context.context_id,
        group_key,
        reconciliation_rule_id,
        reconciliation_rule_version
      })
    )
```

The exact canonical-JSON rules SHALL reuse AIP's existing deterministic canonical-JSON utility.

A changed snapshot or Observation Context therefore produces a different resolution id. Reordering
the same inputs does not.

### 13.3 Public shape

Public shape equivalent to:

```text
DeploymentResolution
  resolution_id
  workload: WorkloadRef | null
  status:
    RESOLVED_EXPLICIT
    RESOLVED_CONFIGURED
    RESOLVED_OBSERVED
    CONFLICT
    AMBIGUOUS
    UNRESOLVED

  service_id: string | null
  candidate_service_ids[]
  supporting_methods[]
  supporting_evidence_refs[]
  conflicting_evidence_refs[]
  limitation_codes[]
  claim_id: string | null
  reconciliation_rule_id
  reconciliation_rule_version
```

`candidate_service_ids` contains the sorted, deduplicated canonical Service ids named or exactly
resolved by applicable paths in that group. It may contain an id that is not present as a current
declared Service when an explicit annotation/configured mapping names such an id; this does not make
that id resolved.

Resolved invariants:

```text
status starts with RESOLVED_
workload != null
service_id != null
candidate_service_ids == [service_id]
claim_id != null
claim_id names one returned DeploymentClaim
```

Non-resolved invariants:

```text
claim_id == null
no DEPLOYED_AS claim is emitted for that resolution
```

A mapping-target or unresolved-OTel group MAY have `workload = null`.

### 13.4 Service-scoped projection cardinality

For a request scoped to Service `S`, return a resolution if and only if at least one condition is
true:

```text
resolution.service_id == S
OR S is present in resolution.candidate_service_ids
```

Consequences:

- a conflict between Service A and Service B is visible from both A and B;
- a Workload resolution unrelated to the requested Service is not returned;
- an unresolved mapping explicitly naming the requested Service remains visible even if its Workload
  target is absent;
- an unresolved OTel observation that resolves to no declared Service is not injected into an
  unrelated Service response.

Exactly one public resolution is returned per included `group_key`.

### 13.5 Canonical ordering and evidence retention

`DeploymentResolution[]` is sorted lexicographically by `resolution_id`.

All list-valued fields are sorted and deduplicated.

For non-resolved outcomes, supporting/conflicting evidence is retained and publicly drillable under
§16 even though no `DEPLOYED_AS` claim exists.

No diagnostic message may contain raw OTLP Resource data, arbitrary Kubernetes annotations, Secrets,
or environment contents.

---

## 14. Public exposure, adapter ownership, and schema version

I3 freezes the parent-spec §28 public-adapter decision as follows.

> **`ArchitectureIntelligenceService` is the single semantic owner. REST and standard negotiated
> MCP are public adapters over that service. The architecture-answer evaluator invokes the service
> directly as the transport-independent qualification oracle.**

| Semantic item | Canonical/internal status | REST | Negotiated MCP | Public schema |
|---|---|---|---|---|
| I2 `InfrastructureEntity`/`Contribution`/`Claim` generally | internal-only | not exposed | not exposed | none |
| Existing dependency Architecture Knowledge | public | `GET /api/services/{service_id}/dependencies` | `get_service_dependencies` | `0.5` |
| Existing dependency-drift Architecture Knowledge | public | `GET /api/services/{service_id}/drift` | `get_architecture_drift` | `0.5` |
| `WorkloadRef` needed by `DEPLOYED_AS` | bounded public projection | `GET /api/services/{service_id}/deployments` | `get_service_dependencies` | `0.5` |
| `DeploymentClaim(DEPLOYED_AS)` | public | `GET /api/services/{service_id}/deployments` | `get_service_dependencies` | `0.5` |
| `DeploymentResolution` including conflict/ambiguity/unresolved | public | same endpoint | `get_service_dependencies.data.deployment_resolutions` | `0.5` |
| Bounded evidence resolution | public under the existing visibility rules, widened by §16.2 for deployment evidence | `POST /api/evidence/resolve`; single-record/list convenience remains under `/api/evidence` | `get_evidence` | `0.5` |
| `get_architecture_drift` deployment meaning | no deployment semantics | unchanged dependency-drift meaning | unchanged dependency-drift meaning | `0.5` |

### 14.1 Single semantic owner and public-adapter topology

The public topology in v0.5 is:

```text
                    ArchitectureIntelligenceService
                              |
              +---------------+---------------+
              |                               |
             REST                     standard negotiated MCP
```

The deterministic architecture-answer evaluator calls `ArchitectureIntelligenceService` directly.
It is a qualification path, not a public transport.

A REST adapter MUST NOT query Neo4j, invoke qualification helpers, or reconstruct an
`ArchitectureAnswer` independently when the corresponding service capability exists. It SHALL
construct the relevant request model, invoke the service, and preserve the returned semantics.
A REST-specific projection such as §15 MAY select a bounded subset of fields from that returned
answer, but it MUST NOT derive stronger or different Architecture Knowledge.

The AIP-specific direct MCP envelope shipped in v0.4.x is retired in v0.5. `POST /mcp` remains the
single MCP endpoint and serves standard negotiated MCP only. Direct-envelope markers and routing are
not part of the v0.5 public contract. Historical v0.4.x specifications and release evidence remain
unchanged.

### 14.2 MCP tool budget

The tool count remains exactly three:

```text
get_architecture_drift
get_evidence
get_service_dependencies
```

No fourth MCP tool is added. The three tools continue to dispatch through the same
`ArchitectureIntelligenceService` methods as the deterministic evaluator and REST adapters.

### 14.3 `get_service_dependencies` integration

The tool retains its existing dependency semantics and adds deployment as a **separate sibling
projection**, never as a dependency.

`ServiceDependenciesData` becomes equivalent to:

```text
service
dependency_claim_ids[]
deployment_claim_ids[]
deployment_resolutions[]
```

The top-level `claims[]` becomes a closed union of:

```text
DependencyClaim
DeploymentClaim
```

Rules:

- `dependency_claim_ids` names only `DependencyClaim`;
- `deployment_claim_ids` names only `DeploymentClaim`;
- a `DeploymentClaim` MUST NOT be counted or described as a direct dependency;
- `get_architecture_drift` returns only dependency-drift claims and never `DEPLOYED_AS`.

### 14.4 Schema version decision

I3 intentionally changes:

- the closed claim union;
- public entity type vocabulary (`WORKLOAD`);
- `ServiceDependenciesData`;
- evidence source/support vocabulary; and
- evidence metadata needed for deployment lineage.

Therefore silently retaining public `schema_version = "0.4"` would be incorrect.

I3 SHALL introduce:

```text
schema_version = "0.5"
schemas/architecture_intelligence/v0.5/
```

The three MCP tool names and request shapes remain stable. Existing `0.4` dependency/drift
semantics remain semantically compatible, but a client that validates the closed `0.4` response
schema must adopt the `0.5` schema.

No dual-schema negotiation is required in I3.

### 14.5 REST parity for existing Architecture Intelligence capabilities

The REST adapter SHALL expose the existing service-level Architecture Knowledge through:

```text
GET  /api/services/{service_id}/dependencies
GET  /api/services/{service_id}/drift
POST /api/evidence/resolve
```

For the dependency and drift endpoints, these query parameters map directly to the existing request
model:

```text
environment  -> observation_context.environment
from         -> observation_context.window_start
to           -> observation_context.window_end
snapshot_id  -> request.snapshot_id
```

`snapshot_id` remains optional exactly as it is in `ServiceDependenciesRequest` and
`ArchitectureDriftRequest`. Missing or incomplete observation context remains a semantic
`ArchitectureIntelligenceService` refusal/limitation rather than being invented by the REST layer.
Malformed supplied values that cannot form the request model are HTTP input errors.

Both endpoints return the complete corresponding `ArchitectureAnswer` JSON shape. They SHALL call
the matching `ArchitectureIntelligenceService` method exactly once and SHALL NOT run an
independent REST qualification/query path.

`POST /api/evidence/resolve` accepts the existing `EvidenceRequest` shape and returns the complete
`ArchitectureAnswer[EvidenceData]` produced by
`ArchitectureIntelligenceService.get_evidence`. This preserves the existing 1–20-ref bounded
resolution, missing-ref reporting, and same-snapshot semantics over REST.

The existing `GET /api/evidence` and `GET /api/evidence/{evidence_id}` forms remain REST
convenience surfaces. I3 makes them snapshot-aware under §16.3; they MUST use the same public
evidence-visibility rules and MUST NOT derive architecture claims.

## 15. REST deployment view

The new read-only endpoint is:

```text
GET /api/services/{service_id}/deployments
```

Required query parameters:

```text
environment
from
to
```

They map to the same bounded Observation Context used by Architecture Intelligence.

The response SHALL contain:

```text
schema_version = "0.5"
snapshot
observation_context
service
deployment_claims[]
deployment_resolutions[]
evidence_refs[]
limitations[]
```

It SHALL be a bounded REST projection over the deployment portion of one
`ArchitectureIntelligenceService.get_service_dependencies` answer for the equivalent request. It
MUST NOT invoke deployment reconciliation, Neo4j queries, or qualification logic independently.
The projected deployment claims, resolutions, evidence references, snapshot, observation context,
and limitations SHALL preserve the service answer semantics.

The endpoint creates no graph writes.

Unknown Service:

```text
404
```

Malformed observation context:

```text
422
```

A known Service with no resolved deployment is still a valid semantic response containing resolution
status/limitations rather than a guessed relation.

---

## 16. Evidence exposure and drill-down

I2 deliberately kept Kubernetes evidence off public surfaces because it supported only internal
infrastructure facts.

I3 changes that boundary narrowly:

> **An otherwise-internal Kubernetes/configuration/runtime-identity evidence record may become
> publicly resolvable only when the current snapshot makes it reachable from a public
> `DEPLOYED_AS` claim or from a public `DeploymentResolution`.**

This includes non-resolved `CONFLICT`, `AMBIGUOUS`, and `UNRESOLVED` resolutions: evidence refs
returned to a client MUST NOT become dead/non-drillable references merely because no claim was
established.

All other Kubernetes evidence remains hidden exactly as in I2.

### 16.1 Public evidence vocabulary

The `0.5` evidence schema SHALL admit:

```text
source_type:
  OPENAPI
  ASYNCAPI
  MANIFEST
  OPENTELEMETRY
  KUBERNETES
  CONFIGURATION

supports.relation_type:
  existing relation types
  DEPLOYED_AS
```

A public deployment-reconciliation evidence record SHALL preserve, where applicable:

```text
source locator
source revision
source instance id
I2 inventory revision / capture identity
I2 evidence mode
mapping rule id/version
configured mapping id/revision/digest
OTel observation context
bounded OTel Kubernetes resource identity attributes
```

Evidence reachable only from a non-resolved `DeploymentResolution` MUST NOT falsely advertise
`DEPLOYED_AS` in `supports`. `supports` continues to describe established facts only; public
reachability from a resolution is sufficient for drill-down.

### 16.2 Selective visibility

For a given snapshot, Kubernetes/configuration/runtime-identity evidence is public if and only if at
least one of these is true:

```text
its id occurs in evidence_refs of a public DeploymentClaim

OR

its id occurs in supporting_evidence_refs or conflicting_evidence_refs
of a public DeploymentResolution
```

"Public DeploymentResolution" means one that can be returned by §13.4 for at least one current
declared Service.

Existing pre-I3 public evidence remains public under its existing rules.

Every evidence ref emitted in a `DeploymentClaim` or `DeploymentResolution` SHALL resolve through
REST evidence resolution and negotiated MCP `get_evidence` at the exact same snapshot.

Evidence not reachable under these rules behaves as a missing **public** evidence id even if an
internal Evidence node exists.

### 16.3 Snapshot-aware REST evidence contract

I3 changes the REST evidence surface so evidence drill-down preserves the same snapshot continuity
as `ArchitectureIntelligenceService` and negotiated MCP.

The parity operation is:

```text
POST /api/evidence/resolve
```

Its body is the existing `EvidenceRequest`; its response is the complete
`ArchitectureAnswer[EvidenceData]` returned by `ArchitectureIntelligenceService.get_evidence`.

The existing REST convenience forms are:

```text
GET /api/evidence?snapshot_id=<aip:snapshot:v1:...>

GET /api/evidence/{evidence_id}?snapshot_id=<aip:snapshot:v1:...>
```

`snapshot_id` is REQUIRED for both listing and lookup.

Behavior is frozen:

```text
missing or malformed snapshot_id
  -> HTTP 422

stable current snapshot cannot be acquired under the revision fence
  -> HTTP 503
  -> code SNAPSHOT_NOT_AVAILABLE

supplied snapshot_id != current stable snapshot id
  -> HTTP 409
  -> code SNAPSHOT_NOT_AVAILABLE

valid current snapshot + evidence is publicly reachable at that snapshot
  -> HTTP 200

valid current snapshot + evidence is not publicly reachable / does not exist
  -> HTTP 404
```

The list endpoint SHALL compute public evidence visibility from the same stable snapshot used to
validate `snapshot_id`; it MUST NOT validate the snapshot and then run an unfenced second read.

`ArchitectureIntelligenceService.get_evidence` and negotiated MCP `get_evidence` already require
`snapshot_id`; those snapshot semantics remain unchanged.

The dependency, drift, and deployment public responses supply the snapshot id clients SHALL pass to
subsequent REST or MCP evidence drill-down.

No public evidence response exposes:

```text
raw Kubernetes YAML/JSON
arbitrary annotations
arbitrary labels
status
managedFields
container environment
Secrets
raw OTLP Resources
baggage
full spans
sample payloads
```

---

## 17. Snapshot binding and determinism

I2 intentionally excluded internal Kubernetes state from the public Architecture Intelligence
snapshot because it could not affect a public answer.

I3 changes that only for the bounded reconciliation projection.

The public snapshot fingerprint SHALL now bind the deterministic public-relevant state for:

```text
current supported Workload identity
current captured Pod UID bindings used by I3
current WORKLOAD_OWNS_POD links used by I3
retained explicit Service-ID annotation values
active configured mapping identity/content digest
bounded OTel runtime identity observations
service-workload-reconciliation rule/version
public deployment evidence projection
```

It SHALL NOT include unrelated Kubernetes internal facts merely because they exist:

```text
Kubernetes Network Service selector facts
Ingress routing facts
unreferenced Kubernetes evidence
arbitrary excluded resource metadata
```

The snapshot canonicalization version SHALL be incremented.

A mapping/configuration change that can change a deployment answer MUST change snapshot identity.

Equivalent input ordering MUST NOT change snapshot identity or semantic output.

All read-side reconciliation must execute under the existing revision-fence/stable-snapshot rules.

---

## 18. Observation-context semantics

I3 reuses the existing Architecture Intelligence Observation Context:

```text
environment
window_start
window_end
context_id
```

The existing maximum window remains unchanged.

I3 does not invent a second environment or time-window model.

For equivalent REST and negotiated-MCP requests routed through the same service semantics:

```text
same service id
same snapshot
same observation context
same reconciliation context
    -> equivalent deployment claims, resolutions, evidence, and limitations
```

Transport envelopes need not be byte-identical; the Architecture Knowledge semantics must be.

Path A/B may resolve without OTel evidence, but the public service deployment view still requires
Observation Context because an applicable Path C observation inside that context may establish
agreement or conflict.

This prevents a caller from suppressing contradictory runtime evidence merely by omitting runtime
context.

---

## 19. Reconciliation limitations and diagnostics

At minimum I3 SHALL define public limitation codes equivalent to:

```text
DEPLOYMENT_IDENTITY_UNRESOLVED
DEPLOYMENT_IDENTITY_AMBIGUOUS
DEPLOYMENT_IDENTITY_CONFLICT
DEPLOYMENT_ENVIRONMENT_MISMATCH
DEPLOYMENT_TEMPORAL_MISMATCH
DEPLOYMENT_EVIDENCE_INCOMPLETE
DEPLOYMENT_RESULT_LIMIT_EXCEEDED
```

Configured mapping syntax/schema errors are configuration errors and SHALL fail startup/load rather
than silently become an unresolved identity.

A mapping whose syntactically valid target is not present in the current snapshot is a semantic
`UNRESOLVED` result.

A direct contradiction is never downgraded to `UNRESOLVED`.

---

## 20. Result bounds

The public deployment projection SHALL be bounded.

Per requested Service:

```text
maximum DeploymentClaim count:      100
maximum DeploymentResolution count: 250
maximum evidence refs per claim:     64
```

Exceeding a bound returns a deterministic `DEPLOYMENT_RESULT_LIMIT_EXCEEDED` safe refusal/limitation;
it does not truncate silently.

These bounds are I3 contract constants and require a reviewed change if altered.

---

## 21. Required deterministic qualification matrix

Fixtures SHALL be frozen only after this specification is accepted.

### 21.1 Path A

Required cases:

```text
valid Deployment annotation
valid StatefulSet annotation
valid DaemonSet annotation
missing annotation
annotation -> missing Service
two contributions -> same annotation
two contributions -> different annotations
annotation exact-case requirement
annotation similarity-only negative
```

### 21.2 Path B

Required cases:

```text
valid configured mapping for each supported Workload kind
mapping -> missing Service
mapping -> missing Workload
wrong configured Kubernetes source id
wrong cluster UID
same names in different namespaces
same names in different clusters
identical duplicate mapping
two mappings -> same Workload, different Services
mapping file unknown field
mapping file duplicate key/id
delimiter-bearing artifact id/revision/mappingId values preserve distinct group keys
distinct tuples ("a", "b:c", "d") and ("a:b", "c", "d") produce distinct group keys
mapping-content change changes reconciliation context/snapshot
```

### 21.3 Path C

Required cases:

```text
service.name + k8s.pod.uid -> Deployment
service.name + k8s.pod.uid -> StatefulSet
service.name + k8s.pod.uid -> DaemonSet

missing k8s.pod.uid
unknown Pod UID
stale/recreated Pod UID
Pod UID resolves ambiguously
owner chain unresolved
owner chain ambiguous

exact service.namespace + service.name
unique exact service.name
configured exact alias
alias target missing
service resolves OBSERVED_ONLY -> unresolved

k8s.namespace.name agrees/disagrees
k8s.cluster.uid agrees/disagrees
k8s.pod.name agrees/disagrees
workload-name consistency attribute agrees/disagrees
service.version agrees/disagrees when both values exist

last_seen inside observation window
last_seen before observation window
last_seen after observation window
capturedAt inside observation window
capturedAt before observation window
capturedAt after observation window
deployment.environment.name absent
deployment.environment.name exact match
deployment.environment.name mismatch -> UNRESOLVED + DEPLOYMENT_ENVIRONMENT_MISMATCH
```

### 21.4 Cross-path reduction

Required cases:

```text
A only -> RESOLVED_EXPLICIT
B only -> RESOLVED_CONFIGURED
C only -> RESOLVED_OBSERVED

A+B agree -> one claim, explicit strongest, union evidence
A+C agree -> one claim, explicit strongest, union evidence
B+C agree -> one claim, configured strongest, union evidence
A+B+C agree -> one claim, explicit strongest, union all evidence

A vs B disagree -> CONFLICT, no claim
A vs C disagree -> CONFLICT, no claim
B vs C disagree -> CONFLICT, no claim
multiple Services satisfying Path C for one Workload -> AMBIGUOUS, no claim

similarity only -> UNRESOLVED
```

### 21.5 Pod replacement

Sequential current-state qualification SHALL prove:

```text
capture N:
  Pod UID P1 -> Workload W
  OTel P1 -> Service S
  result S DEPLOYED_AS W

capture N+1:
  P1 removed
  Pod UID P2 -> same Workload W
  OTel P2 -> same Service S
  result S DEPLOYED_AS W

claim id remains stable because (S, W) is unchanged
old P1 no longer resolves in the new current snapshot
```

### 21.6 Surface/evidence

Required cases:

```text
ArchitectureIntelligenceService/REST/negotiated-MCP dependency semantics agree
ArchitectureIntelligenceService/REST/negotiated-MCP drift semantics agree
REST/MCP same deployment claims and resolutions
POST /api/evidence/resolve and negotiated MCP get_evidence preserve service semantics
get_architecture_drift never returns DEPLOYED_AS
get_service_dependencies keeps dependency_claim_ids separate from deployment_claim_ids
public WorkloadRef leaks no Pod/cluster internals beyond its frozen fields
public evidence resolves every returned deployment evidence ref
unreferenced Kubernetes evidence remains hidden
Kubernetes-only infrastructure with no A/B/C resolution creates no DEPLOYED_AS
DEPLOYED_AS creates no CALLS/SENDS/RECEIVES_FROM
MCP tool count remains exactly 3
zero graph writes through REST and negotiated MCP public read paths
```

### 21.7 Determinism

Require:

```text
resource ordering has no effect
mapping ordering has no effect
OTel batch ordering has no effect
evidence-ref ordering is canonical
resolution ordering is canonical
two clean runs from identical state are byte-identical
same snapshot + same context returns identical deployment semantics

resolution_id is identical for reordered equivalent inputs
resolution_id changes when snapshot_id changes
resolution_id changes when observation_context.context_id changes
one resolution per canonical group_key
service-scoped filtering follows §13.4 exactly

REST evidence lookup/list require snapshot_id
stale REST snapshot -> 409 SNAPSHOT_NOT_AVAILABLE
non-resolved resolution evidence is drillable at the same snapshot
unreferenced internal Kubernetes evidence remains non-public
```

---

## 22. Cross-source fixture strategy

I3 qualification SHALL include one frozen cross-source fixture containing:

```text
declared AIP Service(s)
I2 Kubernetes bundle
I2 owner-chain facts
explicit workload annotation cases
configured mapping artifact
OTel resource identity observations
positive and contradictory identities
```

The Kubernetes side SHOULD reuse I2's independently captured bundle where practical, but I3 does not
claim independent real-system interoperability merely because one component of the fixture is real.

Authored OTel/resource-identity fixture data used to exercise specific conflict matrices SHALL be
identified as authored.

I5 remains responsible for independent two-system cross-source qualification.

---

## 23. Implementation slices

I3 SHOULD be delivered in six bounded slices.

### Slice 1 — contract and public schema foundation

```text
freeze public WorkloadRef / DeploymentClaim / DeploymentResolution
freeze schema_version 0.5
freeze REST/MCP exposure table
add no positive reconciliation yet
```

Exit: closed schemas and contract tests exist; all old dependency/drift semantics remain green.

### Slice 2 — OTel runtime identity evidence

```text
bounded §9.3 Resource allowlist
runtime identity observation model
deterministic persistence/aggregation
no DEPLOYED_AS yet
```

Exit: Pod UID/resource identity evidence survives OTLP → persistence deterministically without
interaction inference.

### Slice 3 — explicit and configured paths

```text
Path A
Path B
mapping artifact schema/validation
mapping evidence
snapshot binding of mapping digest
```

Exit: A/B positive, unresolved, and conflict cases are executable internally.

### Slice 4 — observed path

```text
Path C
Pod UID lookup
owner-chain linkage
exact Service resolver gate
consistency checks
temporal compatibility
```

Exit: observed positive/unresolved/ambiguous/conflict cases are executable internally.

### Slice 5 — public adapter consolidation and public exposure

Slice 5 is intentionally split into two reviewable parts. Slice 5a lands before 5b so the deployment
surface is built on the final v0.5 adapter topology rather than on a transport that v0.5 removes.

#### Slice 5a — public adapter consolidation and REST parity

```text
ArchitectureIntelligenceService remains the single semantic owner
GET /api/services/{service_id}/dependencies
GET /api/services/{service_id}/drift
POST /api/evidence/resolve
retire the v0.4.x direct MCP envelope
retain standard negotiated MCP on /mcp
ArchitectureAnswer evaluator continues direct in-process service invocation
REST/service semantic-equivalence tests
negotiated-MCP/service semantic-equivalence tests
```

Exit: existing dependency, drift, and evidence Architecture Knowledge is available through REST and
standard negotiated MCP without a second semantic implementation or a direct MCP compatibility path.

#### Slice 5b — deployment public exposure

```text
agreement/conflict reducer
get_service_dependencies deployment integration
GET /api/services/{service_id}/deployments
selective Kubernetes evidence exposure
snapshot canonicalization bump
REST/service/negotiated-MCP deployment equivalence
```

Exit: full public `DEPLOYED_AS` vertical slice works without dependency relabeling, and both public
adapters preserve the same service-owned deployment semantics.

### Slice 6 — deterministic qualification and completion

```text
full §21 matrix
frozen cross-source fixture
byte-repeatability
regression suite
documentation
I3 completion record
I4/I5 handoff
```

Exit: §25 Definition of Done is satisfied.

A slice MAY be split into smaller reviewed PRs. Splitting does not change the semantic contract.

---

## 24. Documentation requirements

Before I3 completion, update at least:

```text
docs/canonical-model.md
docs/evidence.md
docs/graph-model.md
docs/opentelemetry.md
docs/ingestion.md
docs/mcp.md
docs/architecture.md
ROADMAP.md only if implementation changes the already-planned I3 scope
```

Documentation SHALL state explicitly:

- which identity paths are supported;
- `DEPLOYED_AS` meaning and non-meaning;
- exact OTel Kubernetes Resource attribute allowlist;
- mapping artifact format;
- temporal compatibility;
- conflict/ambiguity behavior;
- public Workload projection;
- selective Kubernetes evidence exposure;
- schema-version bump to `0.5`;
- no fourth MCP tool;
- no locality semantics.

---

## 25. Definition of Done

I3 is complete only when:

- all three parent-spec identity paths are implemented exactly;
- Path C uses Pod UID + current I2 owner chain and never service/workload name similarity;
- the exact OTel Resource allowlist is executable;
- Path C uses persisted `last_seen` and exact environment equality under one executable
  Observation Context predicate;
- temporal compatibility is executable;
- same-path multiplicity produces `AMBIGUOUS` deterministically;
- observed-only Service minting cannot qualify `DEPLOYED_AS`;
- agreement unions evidence and reports the strongest agreed method;
- contradiction always wins over precedence;
- ambiguous/unresolved/conflicting cases emit no deployment claim;
- supported Pod replacement preserves logical Workload association;
- the mapping artifact is versioned, validated, evidence-backed, and snapshot-bound;
- `DEPLOYED_AS` is exposed as its own public claim and never relabeled as a dependency;
- REST and negotiated MCP semantics are equivalent to the corresponding
  `ArchitectureIntelligenceService` result;
- `get_architecture_drift` remains deployment-agnostic;
- every public deployment claim **and non-resolved resolution** evidence ref is drillable at the
  same snapshot;
- REST evidence listing and lookup require and enforce the same snapshot id;
- DeploymentResolution grouping/id/cardinality/filtering/ordering are executable and deterministic;
- unreferenced Kubernetes infrastructure/evidence remains internal;
- `schema_version = "0.5"` and committed v0.5 schemas validate all new/old answer cases;
- standard negotiated MCP exposes exactly three read-only tools and causes zero graph writes;
- the v0.4.x direct MCP envelope is absent from the v0.5 public contract;
- the deterministic architecture-answer evaluator invokes `ArchitectureIntelligenceService`
  directly rather than using a transport adapter;
- two clean qualification runs are byte-identical;
- all pre-I3 I1/I2/OTel/MCP regression suites remain green;
- limitations and unsupported cases are documented; and
- the I3 completion record pins:
  - implementation candidate revision;
  - reconciliation rule/schema revisions;
  - mapping artifact revision;
  - fixture digests;
  - qualification report/evidence revisions.

I3 completion is not release qualification. I5 and I6 remain required.

---

## 26. Handoff to I4 and I5

I3 provides I5 with:

```text
stable Service↔Workload claim semantics
positive and negative cross-source identity fixtures
public Workload projection
public evidence lineage
conflict/ambiguity taxonomy
temporal compatibility rule
exact reconciliation rule version
```

I3 provides no new Pub/Sub semantics to I4.

I4 SHALL NOT use `DEPLOYED_AS`, Kubernetes co-location, or Workload identity as evidence that a
Queue/Topic/Subscription relationship exists.

I5 may harden I3 only when independent cross-system evidence demonstrates a real model defect.
Target-specific identity exceptions are prohibited.

---

## 27. Relationship to later releases

I3 remains deliberately below the later semantic layers.

### v0.6 — Locality-aware Current State

I3 retains namespace/cluster context needed for identity/evidence, but does not turn it into a
locality-qualified claim.

### v0.7 — Explicit Intent

`DEPLOYED_AS` is Current-State identity reconciliation. It is never architectural Intent.

### v0.8 — Qualified assessment

Future Current↔Intent assessment may consume a qualified deployment association, but Intent must not
alter I3's Current-State reconciliation result.

---

## 28. Stop conditions

Implementation SHALL stop for specification review if any of these becomes necessary:

1. a fourth MCP tool;
2. name/label/fuzzy identity matching;
3. a new Kubernetes resource kind;
4. a new discovery-source family;
5. materializing `DEPLOYED_AS` requires a second ownership/expiry engine;
6. a live Kubernetes client;
7. locality-qualified output;
8. container/sidecar canonical entities to make a positive case work;
9. exposing arbitrary Kubernetes or OTLP payloads;
10. weakening conflict to precedence-based winner selection;
11. schema widening while continuing to claim public `schema_version = "0.4"`;
12. a REST or MCP adapter independently deriving or qualifying Architecture Knowledge instead of
    using `ArchitectureIntelligenceService`.

These are scope changes, not implementation details.

---

## 29. Review checklist before implementation

Review SHALL explicitly confirm:

- [ ] I2's internal infrastructure model remains the source of Workload/Pod truth.
- [ ] All three successful identity paths are mandatory and no fourth path exists.
- [ ] `service.name` alone is insufficient.
- [ ] `OBSERVED_ONLY` Services cannot qualify deployment identity.
- [ ] `k8s.pod.uid` is required for Path C.
- [ ] Path C requires `CAPTURED_RESOURCE`.
- [ ] Path C window applicability uses persisted `last_seen` with inclusive bounds.
- [ ] `deployment.environment.name` matches Observation Context environment by exact equality.
- [ ] Temporal compatibility uses the same explicit observation window; no arbitrary skew.
- [ ] Same-path multiplicity is always `AMBIGUOUS`.
- [ ] Contradiction between distinct paths or consistency evidence is `CONFLICT`.
- [ ] Contradiction wins over precedence.
- [ ] Multi-Service-per-Workload is not modeled in v0.5.
- [ ] `DEPLOYED_AS` is not a dependency or locality claim.
- [ ] `ArchitectureIntelligenceService` is the single semantic owner for REST and negotiated MCP.
- [ ] The deterministic evaluator invokes `ArchitectureIntelligenceService` directly.
- [ ] The v0.4.x direct MCP envelope is retired; `/mcp` serves standard negotiated MCP only.
- [ ] REST exposes dependencies, drift, and bounded evidence resolution through the §14.5 parity
      operations.
- [ ] `get_service_dependencies` exposes deployment as a separate sibling projection.
- [ ] `get_architecture_drift` remains unchanged in meaning.
- [ ] Evidence referenced by non-resolved public resolutions remains snapshot-drillable.
- [ ] REST evidence listing/lookup require `snapshot_id` and define stale-snapshot behavior.
- [ ] `DeploymentResolution` grouping, identity, service filtering, and ordering are deterministic.
- [ ] Selective Kubernetes evidence exposure is limited to public claim/resolution reachability.
- [ ] Public schema version changes to `0.5`.
- [ ] MCP tool count remains three.
- [ ] No agent/LLM becomes a source of identity truth.

Acceptance of this checklist is the implementation entry gate.

---

## 30. References

Repository contracts:

- `docs/specifications/0.5.0/specification.md` §§15–18, §28
- `docs/specifications/0.5.0/i2-kubernetes-discovery-vertical-slice.md`
- `docs/specifications/0.5.0/i2-completion-record.md`
- `app/canonical/infrastructure.py`
- `app/telemetry/service_resolver.py`
- `app/telemetry/model.py`
- `app/telemetry/semconv/resources.py`
- `app/architecture_intelligence/contracts.py`
- `app/architecture_intelligence/repository.py`

External semantic reference:

- OpenTelemetry Kubernetes resource semantic conventions:
  `https://opentelemetry.io/docs/specs/semconv/resource/k8s/`

The OpenTelemetry reference supplies attribute vocabulary only. AIP's admitted subset and
reconciliation semantics are frozen by this specification, not delegated to external convention
changes.
