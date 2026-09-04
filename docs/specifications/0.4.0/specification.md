# AIP v0.4.0 Release Specification — Trusted Architecture Context for Agents

**Status:** Draft 1.2 — capability-first implementation contract  
**Target release:** `v0.4.0`  
**Release theme:** Architecture Intelligence Tools  
**Entry baseline:** Published and post-release-verified `v0.3.0`  
**Primary outcome:** An independent MCP client can obtain deterministic, evidence-backed,
qualified, and snapshot-bound architecture answers without knowing AIP's internal graph model.

---

## 1. Release Promise

`v0.3.0` established that AIP's architecture intelligence survives independently authored real
systems. `v0.4.0` makes that intelligence safely consumable by external tools and AI agents.

The release SHALL prove this single capability:

> **Given an architecture already known to AIP, an external MCP client can query selected
> architecture facts and receive reproducible answers that identify the supporting evidence,
> qualification, snapshot, observation context, and known limitations.**

The release is not complete merely because an MCP endpoint or tool wrapper exists. It is complete
when the capability works end to end through an independent client.

```text
v0.3
AIP knows architecture facts reliably

                 ↓

v0.4
External agents can safely consume those facts
```

The governing principle is:

> **AIP may help agents reason about architecture, but an agent must never become the source of
> architectural truth.**

---

## 2. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

Examples in this document illustrate semantics. Executable JSON Schemas and independently authored
evaluation fixtures SHALL become the authoritative wire-contract evidence during implementation.

---

## 3. Product Capability and Release Gate

The `v0.4.0` golden path is:

```text
Independent MCP client
        |
        | per-request metadata / tools/list / tools/call
        v
Read-only AIP MCP adapter
        |
        v
ArchitectureIntelligenceService
        |
        v
Canonical Model + Evidence + Snapshot Context
        |
        v
ArchitectureAnswer<T>
```

At minimum, the client SHALL be able to:

1. Query the direct dependencies of one known service.
2. Identify declared-versus-observed drift for one service in a named observation context.
3. Resolve the evidence and provenance referenced by an answer.
4. Detect when AIP cannot answer safely because identity, evidence, support, or snapshot context is
   insufficient.

The client SHALL NOT require:

```text
knowledge of Neo4j
knowledge of AIP node labels or relationship types
Cypher
an LLM API key
access to AIP internals
write access to the architecture model
```

---

## 4. Scope Budget

To prevent feature creep, `v0.4.0` has a fixed capability budget:

| Area | `v0.4.0` limit |
|---|---|
| Public MCP tools | Exactly 3 |
| MCP transport | Streamable HTTP only |
| Architecture service boundary | One `ArchitectureIntelligenceService` |
| Result envelope | One versioned `ArchitectureAnswer<T>` family |
| Dependency traversal | Direct dependencies only |
| Drift scope | One service and one observation context per call |
| Snapshot persistence | None; bind queries to a fingerprint of the current committed state |
| Observation-context persistence | None; derive an audit identity from explicit request fields |
| Mutations | None |
| LLM dependency | None for correctness or qualification |
| Real-system qualification | Reuse frozen v0.3 evidence; no default rerun of the source systems |

Adding a fourth tool, another transport, a new discovery source, or a new analysis algorithm
requires removal of an existing `v0.4.0` item or explicit rescoping to a later release.

---

## 5. In Scope

`v0.4.0` SHALL deliver:

1. `ArchitectureIntelligenceService` as the product-facing semantic boundary.
2. A structured and versioned `ArchitectureAnswer<T>` contract.
3. Snapshot and observation-context binding on every architecture answer.
4. Claim-level qualification using AIP's existing declared/observed semantics.
5. Stable evidence references and provenance drill-down.
6. Three read-only MCP tools.
7. Deterministic tool evaluation with independently authored expected answers.
8. Qualification through an independent MCP client.
9. One short, reproducible hero demo using bundled or frozen architecture evidence.
10. Release-candidate and published-artifact verification for the new capability.

---

## 6. Explicit Non-Goals

The following are outside `v0.4.0`:

```text
Kubernetes discovery
new source adapters
deeper runtime discovery
new Canonical Model relation families
new architecture-analysis algorithms
transitive blast-radius exposure through MCP
generic graph query or execute_cypher tools
graph writes or architecture mutations
agent orchestration or autonomous architecture agents
A2A integration
GraphRAG or vector databases
prompt libraries or sophisticated LLM prompting
MCP resources, prompts, tasks, or UI extensions
multiple MCP transports
multi-tenancy and enterprise authorization
consumer-platform control-plane functions such as user/workspace policy, complete activity audit,
human-decision records, or compute/token governance
large UI work
historical architecture trajectories or snapshot diffing
v1.0 contract freeze
production-scale performance qualification
```

Existing AIP capabilities remain available through their current interfaces. Their omission from
the initial MCP tool set does not remove them from AIP.

---

## 7. Architecture Boundary

`ArchitectureIntelligenceService` SHALL own the semantics visible to all new tools.

```text
MCP adapter ──┐
              ├──> ArchitectureIntelligenceService ──> model/evidence repositories
future API ───┘
```

The MCP adapter SHALL:

- validate protocol and tool input;
- call the service boundary;
- map the returned answer to MCP structured content;
- add no architectural claims of its own.

The MCP adapter MUST NOT:

- query Neo4j or repositories directly;
- contain Cypher;
- call analysis implementations except through `ArchitectureIntelligenceService`;
- infer, complete, summarize, or rewrite claims using an LLM;
- create or update canonical entities, relations, evidence, or snapshots;
- weaken qualifications or omit limitations returned by the service.

The same service result SHALL be usable by a future REST, CLI, or integration adapter without
changing its architectural meaning.

---

## 8. `ArchitectureAnswer<T>`

Every successful or safely refused architecture query SHALL return the same envelope family.

Conceptually:

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
    "snapshot_id": "aip:snapshot:...",
    "model_revision": "sha256:..."
  },
  "observation_context": {
    "context_id": "aip:observation-context:...",
    "environment": "demo",
    "window_start": "...",
    "window_end": "..."
  },
  "data": {},
  "claims": [],
  "evidence_refs": [],
  "limitations": []
}
```

### 8.1 Required Fields

| Field | Requirement |
|---|---|
| `schema_version` | MUST identify the answer-contract version. |
| `producer` | MUST identify the AIP implementation by stable product name, version, and immutable build revision. |
| `tool` | MUST identify the semantic operation that produced the answer. |
| `outcome` | MUST be `ANSWERED`, `PARTIAL`, or `NOT_ANSWERED`. |
| `snapshot` | MUST bind the answer to exactly one fingerprinted committed model state. |
| `observation_context` | MUST be explicit when runtime observation affects the answer; otherwise `null`. |
| `data` | MUST contain only data justified by the returned claims. |
| `claims` | MUST contain normalized, qualified architecture claims in deterministic order. |
| `evidence_refs` | MUST be the deduplicated union of evidence referenced by the claims. |
| `limitations` | MUST explain every known qualification gap affecting interpretation. |

`producer.name`, `producer.version`, and `producer.build_revision` SHALL be deterministic for one
deployed artifact. `build_revision` MUST identify the immutable source revision from which that
artifact was built. Together, `producer`, `schema_version`, and `snapshot` bind an answer to the
implementation, wire contract, and architecture state that produced it. They MUST NOT contain an
invocation identifier or request-time value.

### 8.2 Claim Shape

Each claim SHALL contain at least:

```text
claim_id
subject
predicate
object
qualification
evidence_refs
```

No human-readable text field may introduce a claim absent from the structured claim set.

### 8.3 Outcome Semantics

```text
ANSWERED
    The requested supported question was answered without a material unresolved part.

PARTIAL
    A safe subset was answered and one or more limitations identify what remains unresolved.

NOT_ANSWERED
    AIP cannot answer the requested question safely in the selected scope.
```

An empty `data` value without an explicit outcome and reason is invalid.

---

## 9. Claim Qualification

`v0.4.0` SHALL reuse existing AIP semantics rather than invent agent-specific confidence scores.

Supported claim qualifications are:

```text
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
DECLARED_ONLY          only if this is the existing canonical representation used by the source
```

If the current model represents declared-only state solely as `NOT_OBSERVED_IN_WINDOW`, the public
contract SHALL preserve that existing meaning and SHALL NOT introduce `DECLARED_ONLY` as a synonym.
The executable schema SHALL freeze exactly one representation before I1 exits.

The following are limitations or refusal reasons, not fabricated claims:

```text
UNSUPPORTED
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
UNKNOWN_ENTITY
OBSERVATION_CONTEXT_REQUIRED
SNAPSHOT_NOT_AVAILABLE
RESULT_LIMIT_EXCEEDED
```

Numeric confidence scores are out of scope. AIP SHALL report what is known and why, not assign
unvalidated probability to an architecture claim.

---

## 10. Snapshot and Observation Context

### 10.1 Snapshot Binding

A snapshot is the committed AIP model-and-evidence state against which a query is evaluated.

In `v0.4.0`, a snapshot is a **virtual current-state snapshot**, not a stored copy of the graph.
`model_revision` SHALL be a deterministic content fingerprint of the queryable canonical model and
evidence state, and `snapshot_id` SHALL be its opaque, versioned public identity. The implementation
MAY cache or maintain this fingerprint transactionally, but SHALL NOT introduce a historical
snapshot store merely to satisfy this release.

- Every answer MUST include `snapshot_id` and `model_revision`.
- The fingerprint and semantic answer MUST describe one consistent committed read state. A
  concurrent import or telemetry write MUST NOT produce an answer whose snapshot identity describes
  different graph contents.
- One answer MUST NOT combine claims from different snapshots.
- A caller MAY omit `snapshot_id` for an initial architecture query; the service then binds once to
  the current committed state and returns its exact identity.
- Repeating a call with the returned explicit `snapshot_id` and the same inputs MUST produce the
  same semantic answer while the live committed state still has that fingerprint.
- An explicit `snapshot_id` is available only when it matches the current committed state. If the
  model or evidence changed, the service MUST produce `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE`;
  silent fallback to the newer state is forbidden.

`v0.4.0` does not require persisted snapshots, arbitrary historical retention, snapshot diffing, or
architecture trajectories. It requires content-addressed current-state identity, consistent reads,
and honest failure after that state is no longer live.

The semantic answer SHALL NOT contain a request-time snapshot timestamp. Tool invocation timestamps
belong to transport or consumer audit logs, not to the deterministic snapshot identity.

### 10.2 Observation Context

`v0.4.0` SHALL NOT introduce a persisted `ObservationContext` entity. Runtime-sensitive requests
MUST carry this structured input:

```text
environment
window_start
window_end
```

The service SHALL normalize the environment and the inclusive time window to a canonical UTC
representation and derive:

```text
context_id = versioned deterministic fingerprint(environment, window_start, window_end)
```

`context_id` is returned for correlation and auditing. It is not a persisted entity or a historical
lookup key, and the client is not required to parse it. To repeat a context, the client resubmits the
normalized structured fields returned in the original answer.

Runtime-sensitive MCP tools SHALL require an explicit environment, `window_start`, and `window_end`.
They SHALL NOT use a moving clock-derived default because the same apparent request would then select
a different window on every call. Existing REST defaults may remain unchanged outside the new tool
contract.

AIP MUST NOT silently mix environments or windows. `NOT_OBSERVED_IN_WINDOW` is valid only when the
selected observation context and the relevant evidence/coverage basis are present.

---

## 11. Evidence and Provenance

Every supported claim MUST reference at least one resolvable evidence record. A claim requiring both
declared and observed support SHOULD reference both evidence classes.

An evidence response SHALL expose enough provenance to answer:

```text
What source produced this evidence?
Was it declared or observed?
When and in which environment was it captured?
Which canonical entity or relation does it support?
Which adapter, import, or telemetry mechanism processed it?
```

Evidence identifiers SHALL be opaque to clients. Clients MUST NOT need to parse an identifier to
derive meaning.

Evidence output MUST NOT expose credentials, authorization headers, secrets, or unsanitized payloads.
If raw evidence cannot be returned safely, metadata and a limitation SHALL be returned instead.

---

## 12. Public MCP Tool Set

The `v0.4.0` MCP server SHALL expose exactly these tools.

### 12.1 `get_service_dependencies`

Purpose: return direct outgoing architecture dependencies of one service.

Required input:

```text
service_id
observation_context:
    environment
    window_start
    window_end
```

Optional input:

```text
snapshot_id
```

Required behavior:

- return direct dependencies only;
- represent `destination` independently from `delivery` so identity is not encoded in transport
  semantics;
- identify the canonical destination by `id`, `type`, and display name;
- identify delivery separately by the existing canonical relation type and its operation or queue
  path where available;
- preserve every supported delivery path: the same destination reached synchronously and
  asynchronously MUST retain both delivery entries rather than being collapsed by traversal-level
  deduplication;
- use a safely resolved target `Service` as the destination when the existing canonical relations
  establish it; otherwise retain the directly identified `Operation` or `Queue` target and report
  any unresolved logical-service identity as a limitation rather than guessing;
- implement this as a service-layer projection over existing `CALLS`/`PROVIDES`, `SENDS`,
  `RECEIVES_FROM`, `sync_depends_on`, and `async_flow_to` semantics; it MUST NOT materialize a new
  Canonical Model relation merely for this tool;
- qualify every returned dependency;
- reference supporting evidence;
- distinguish an empty dependency set from an unknown service or unsupported query;
- sort results deterministically by canonical destination identity, delivery type/path, and claim
  identity.

### 12.2 `get_architecture_drift`

Purpose: return declared-versus-observed discrepancies affecting one service in one observation
context.

Required input:

```text
service_id
observation_context:
    environment
    window_start
    window_end
```

Optional input:

```text
snapshot_id
```

Required behavior:

- return `OBSERVED_ONLY` and `NOT_OBSERVED_IN_WINDOW` claims in the supported scope;
- preserve AIP's rule that non-observation is not absence;
- never label a relation obsolete, dead, unused, or incorrect solely because it was not observed;
- report unresolved or insufficient evidence explicitly;
- sort results deterministically.

### 12.3 `get_evidence`

Purpose: resolve evidence and provenance referenced by architecture answers.

Required input:

```text
evidence_refs[]   (1..20)
snapshot_id
```

Required behavior:

- resolve evidence only within the selected snapshot context;
- require the `snapshot_id` returned by the originating architecture answer so drill-down cannot
  silently resolve the same evidence reference against a newer live graph state; unlike an initial
  architecture query, evidence resolution MUST NOT default to the current snapshot;
- preserve the order requested or return one documented deterministic canonical order;
- identify missing, unavailable, or redacted evidence explicitly;
- perform no architecture analysis and create no new claim.

### 12.4 MCP Representation

- The server SHALL implement MCP specification version `2026-07-28`.
- Each JSON-RPC request SHALL carry the protocol and client metadata required by that version;
  `initialize` and protocol-level sessions are not part of this protocol baseline.
- `v0.4.0` SHALL support Streamable HTTP only.
- `tools/list` SHALL expose complete JSON Schemas and read-only behavior descriptions.
- `tools/call` SHALL return `ArchitectureAnswer<T>` as structured content.
- Optional text content MUST be deterministic and derived solely from the structured answer.
- Tool annotations are hints only and SHALL NOT substitute for server-side read-only enforcement.

---

## 13. Failure Semantics

Safe refusal is part of the product capability.

The evaluation suite SHALL include at least:

| Situation | Required result |
|---|---|
| Unknown service | `NOT_ANSWERED / UNKNOWN_ENTITY` |
| Ambiguous runtime identity | `PARTIAL` or `NOT_ANSWERED / UNRESOLVED_IDENTITY` |
| Unsupported mechanism | `NOT_ANSWERED / UNSUPPORTED` |
| Missing evidence needed for claim | `PARTIAL` or `NOT_ANSWERED / INSUFFICIENT_EVIDENCE` |
| Runtime-sensitive query without complete explicit context | `NOT_ANSWERED / OBSERVATION_CONTEXT_REQUIRED` |
| Explicit stale/unavailable snapshot | `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE` |
| Valid service with no direct dependencies | `ANSWERED` with an empty result and no false limitation |

Errors in transport, authentication, or malformed input SHALL remain protocol/input errors and SHALL
NOT be represented as architecture qualifications.

---

## 14. Determinism

For a fixed application version, snapshot, observation context, and input:

- the structured semantic response MUST be byte-identical after canonical serialization;
- arrays MUST use documented stable ordering;
- evidence references MUST be deduplicated deterministically;
- generated prose, timestamps, random IDs, or LLM output MUST NOT affect the answer;
- the MCP adapter and direct service call MUST produce semantically identical results.

Transport framing and MCP request IDs are excluded from semantic comparison. The canonical
`ArchitectureAnswer<T>` payload is the comparison unit.

---

## 15. Deterministic Tool Evaluation

The existing architecture-model evaluation remains in place. `v0.4.0` adds a tool-facing layer:

```text
architecture-model evaluation
              +
ArchitectureIntelligenceService evaluation
              +
MCP contract evaluation
```

Each scenario SHALL contain independently authored:

```text
input architecture and evidence
tool name and arguments
expected answer payload or semantic projection
expected claim qualifications
expected evidence references
expected snapshot and observation binding
expected limitations or refusal reason
```

Expected answers MUST NOT be generated from AIP output.

The suite SHALL verify:

1. JSON Schema conformance.
2. Result values and exact claim identities.
3. Qualifications and failure semantics.
4. Evidence-reference integrity and drill-down.
5. Virtual snapshot fingerprint and normalized observation-context binding.
6. Deterministic ordering and serialization.
7. Absence of unexpected claims.
8. Service/MCP semantic equivalence.
9. Two consecutive identical semantic runs.

Correctness evaluation MUST require no LLM provider or API key.

---

## 16. Real-System Evidence Qualification

The tool layer SHALL be exercised against frozen evidence from both v0.3 real-system profiles:

```text
Quarkus Super Heroes
    supported direct service dependencies
    declared/observed qualification

Apache Airflow
    supported REST dependencies
    unresolved identity and insufficient-evidence cases
```

The qualifying inputs SHALL name their source revisions and artifact hashes.

Because `v0.4.0` does not change discovery or canonical semantics, the default qualification path
SHALL reuse the frozen v0.3 captures or derived immutable fixtures. It SHALL NOT rebuild and run both
heavy external systems merely to prove a read-only query adapter.

A fresh real-system run becomes mandatory only if `v0.4.0` changes ingestion, identity resolution,
evidence reconciliation, Canonical Model semantics, or the comparator behavior relevant to the
answers.

---

## 17. Independent-Client Qualification

At least one client implementation not sharing the MCP server's internal call path SHALL execute:

```text
POST /mcp with required protocol and client metadata
tools/list
tools/call get_service_dependencies
tools/call get_architecture_drift
tools/call get_evidence
```

The qualification SHALL verify:

- protocol negotiation succeeds;
- exactly the three intended tools are exposed;
- tool schemas are accepted by the client;
- structured responses conform to the frozen answer schema;
- evidence references from the first two tools resolve through `get_evidence`;
- no internal graph knowledge is required;
- all operations remain read-only;
- the same calls repeated against the same snapshot produce identical semantic results.

An LLM-based host MAY be shown as an additional demonstration but MUST NOT be the correctness oracle.

---

## 18. Hero Demo

`v0.4.0` SHALL include one reproducible demonstration runnable in approximately five minutes after
the existing AIP prerequisites are available.

The demo question is:

> **Which direct dependencies of this service were observed but not declared, and what evidence
> supports that answer?**

The flow SHALL show:

```text
independent MCP client
    -> dependency or drift query
    -> qualified claim
    -> snapshot and observation window
    -> evidence drill-down
```

The demo SHALL use bundled or frozen data, require no LLM API key, and produce a deterministic
result. A separate optional agent/LLM walkthrough may consume the same tools but adds no release
claim.

The hero demo SHALL use the bundled runtime-demo architecture and query
`service:order-service` within its frozen `demo` observation context.

The expected primary finding is the direct
`OrderService -> LegacyPricingService` dependency, qualified as
`OBSERVED_ONLY` and linked to its OpenTelemetry evidence.

The frozen Quarkus and Airflow profiles remain separate real-system
qualification inputs under §16 and are not required to execute the
five-minute hero-demo path.

---

## 19. Read-Only and Safety Requirements

The MCP surface SHALL be read-only by construction.

- No tool may accept Cypher, SQL, shell commands, prompts, or executable expressions.
- No tool may import architecture sources or telemetry.
- No tool may mutate model, evidence, configuration, or snapshot state.
- Tool execution SHALL use a repository/service interface that exposes no write operation.
- Inputs SHALL be schema-validated and bounded.
- `get_evidence` SHALL accept at most 20 references per call.
- Responses SHALL not expose secrets or raw internal exceptions.
- Client-supplied text SHALL never alter query structure outside documented parameters.

Authentication and multi-tenant policy are deferred, but the server MUST NOT claim production-safe
public exposure without them. The release demo and documentation SHALL state the supported deployment
boundary.

AIP provides architecture claims, qualifications, evidence provenance, snapshot identity, and
observation context. The consuming platform remains responsible for user and workspace
authorization, tool-invocation audit logs, human-decision records, policy enforcement, and compute
or token governance. These consumer-platform control-plane capabilities are outside `v0.4.0` and
MUST NOT be added merely to demonstrate compatibility with a larger agent platform.

---

## 20. Compatibility and Versioning

`v0.4.0` remains pre-1.0.

- The answer contract SHALL carry `schema_version`.
- MCP tool names and schemas SHALL be frozen for the `0.4.x` line unless a correctness or security
  defect requires a breaking correction.
- Additive optional fields MAY be introduced in `0.4.x`; changing meaning or removing fields
  requires a new minor release.
- The MCP protocol version and SDK dependency SHALL be pinned in the dependency lock.
- MCP is an adapter over the service contract; protocol changes MUST NOT silently change
  architecture semantics.

This is not the final public-contract freeze. Full stability remains a `v0.9` goal.

---

## 21. Scope-Change Rule

The release baseline is the published `v0.3.0` semantic core.

Changes below `ArchitectureIntelligenceService` are presumed out of scope. If implementation finds
that a model, ingestion, identity, reconciliation, or evidence-semantic change is necessary:

1. Record the concrete capability blocker.
2. Stop the affected `v0.4` work package.
3. Specify the semantic change separately.
4. Re-run all affected synthetic and real-system validation gates from v0.3.
5. Resume only after the new baseline is qualified.

A tool must not compensate for a model gap by inventing an MCP-only interpretation.

Feature requests discovered during implementation SHALL go to `v0.4.x`, `v0.5`, or later unless
they block the golden path.

---

## 22. Delivery Split

The release is divided into four capability increments. Each increment exits with executable
behavior, not documentation alone.

### I1 — Service Contract and Dependency Vertical Slice

Deliver:

```text
ArchitectureIntelligenceService boundary
ArchitectureAnswer<T> schema
virtual current-state snapshot fingerprint
stateless observation-context normalization and audit identity
qualification and limitation vocabulary
destination/delivery dependency projection
get_service_dependencies service implementation
independently authored dependency scenarios
```

Exit capability:

> A direct service call returns a deterministic, qualified, evidence-linked, snapshot-bound
> dependency answer.

### I2 — MCP Vertical Slice and Evidence Drill-Down

Deliver:

```text
single Streamable HTTP MCP endpoint
get_service_dependencies MCP adapter
get_evidence service and MCP tool
per-request metadata / tools/list / tools/call integration tests
read-only enforcement tests
```

Exit capability:

> An independent MCP client obtains a dependency answer and resolves its evidence without graph
> knowledge.

### I3 — Drift Capability and Deterministic Qualification

Deliver:

```text
get_architecture_drift service and MCP tool
negative/failure-semantic scenarios
full deterministic tool evaluation
two identical repeated runs
frozen Quarkus and Airflow evidence qualification
hero demo
```

Exit capability:

> All three tools are useful, bounded, deterministic, evidence-qualified, and proven against
> synthetic plus real-system-derived inputs.

### I4 — Release Candidate, Publication, and Verification

Deliver:

```text
exact candidate freeze
clean-checkout test and evaluation
independent-client qualification
CI / CodeQL / dependency / container checks
release blocker assessment and GO / NO-GO
v0.4.0 tag and release
published source/image smoke test of the MCP golden path
public status closure
```

Exit capability:

> A new external user can run the published artifact and complete the documented MCP golden path.

---

## 23. Required Evidence and Documentation

The implementation SHALL prefer executable contracts and compact evidence over a large document set.

Required artifacts are limited to:

```text
one release specification and short index
versioned answer/tool JSON Schemas
independently authored evaluation fixtures
machine-readable evaluation report
one combined RC qualification and GO/NO-GO record
one concise MCP usage/demo guide
README / ROADMAP / CHANGELOG release updates
```

Separate design dossiers per tool, generated API prose, an architecture wiki, and duplicated test
reports are not required. Executable schemas and tests are the primary contract; prose explains
intent, semantics, boundaries, and limitations.

---

## 24. Release Blockers

Any of the following blocks `v0.4.0`:

### Semantic Integrity

```text
answer contains a claim absent from the deterministic service result
qualification or limitation is dropped or weakened
evidence reference is missing, broken, or points outside the selected snapshot
snapshot or observation context is ambiguous or silently substituted
unresolved identity is guessed
non-observation is represented as absence, dead code, or obsolescence
MCP and direct service answers differ semantically
```

### Scope and Safety

```text
MCP adapter directly accesses the graph or contains architecture logic
generic query or write path is exposed
tool call mutates architecture state
LLM output is required for correctness
fourth public tool or second transport added without explicit rescoping
unqualified new discovery/model semantics introduced
```

### Determinism and Usability

```text
evaluation expected answers derived from AIP output
tool evaluation has missing, unexpected, or wrongly qualified claims
repeat runs differ semantically for the same bound inputs
independent client cannot negotiate per request, list, or call every tool
evidence drill-down cannot reconstruct why a claim exists
hero demo cannot run from clean documented state
```

### Release Quality

```text
required tests, CI, CodeQL, or dependency audit fail
candidate changes after qualification
published artifact differs from the GO candidate without recorded provenance
published artifact fails the MCP golden-path smoke test
known critical security issue remains undispositioned
```

Targets:

```text
Incorrect supported architecture claims = 0
Unexpected tool claims = 0
Broken evidence references = 0
Write-capable MCP operations = 0
Release blockers = 0
```

---

## 25. Definition of Done

### Capability

- [ ] `ArchitectureIntelligenceService` is the only semantic entry point used by the MCP tools.
- [ ] Exactly three public tools exist with the names and scopes defined in §12.
- [ ] An independent client sends valid per-request metadata and completes `tools/list` and all
  required `tools/call`s.
- [ ] A client can obtain a dependency/drift claim and resolve why it exists.
- [ ] No client needs graph-schema or Cypher knowledge.

### Answer Contract

- [ ] Every answer conforms to the versioned `ArchitectureAnswer<T>` schema.
- [ ] Every answer identifies the AIP version and immutable build revision that produced it.
- [ ] Every claim has an accepted qualification and resolvable evidence.
- [ ] Every answer is bound to one fingerprint of the current committed model-and-evidence state.
- [ ] A stale explicit snapshot is rejected rather than silently redirected to current state.
- [ ] No persisted snapshot-history or `ObservationContext` entity was added for this release.
- [ ] Runtime-sensitive requests provide a complete explicit context and answers return its
      normalized fields plus deterministic audit identity.
- [ ] Limitations and safe refusals are explicit.
- [ ] No generated prose adds claims.
- [ ] No request-time timestamp or invocation identifier affects the deterministic semantic answer.

### Determinism and Evaluation

- [ ] Expected answers are independently authored.
- [ ] Positive, empty, partial, unresolved, insufficient, unsupported, and unknown cases are covered.
- [ ] Missing, unexpected, and wrongly qualified claims are detected.
- [ ] Evidence references and drill-down are validated.
- [ ] A destination reached through multiple delivery paths retains every path deterministically.
- [ ] Service and MCP semantic outputs agree.
- [ ] Two consecutive evaluation runs are semantically identical.
- [ ] No LLM API key is required.

### Real-System and Demo

- [ ] Frozen Quarkus evidence produces the expected supported answers.
- [ ] Frozen Airflow evidence preserves unresolved/insufficient cases without guessing.
- [ ] Source revisions and artifact hashes are recorded.
- [ ] The five-minute hero demo succeeds from clean documented state.

### Safety and Release

- [ ] All tools are read-only by interface and test.
- [ ] No generic graph query is exposed.
- [ ] Inputs are validated and bounded; evidence output is sanitized.
- [ ] CI, CodeQL, dependency, and container checks pass on the exact candidate.
- [ ] Explicit GO names the exact candidate.
- [ ] The published source and image complete the independent-client MCP smoke test.
- [ ] README, ROADMAP, CHANGELOG, and release notes state the bounded capability and limitations.
- [ ] Release blockers = `0`.

---

## 26. Exit Statement

The release decision SHALL be one of:

```text
GO — v0.4.0 proves that an independent MCP client can consume AIP as trusted,
snapshot-bound, evidence-qualified architecture context through the three frozen
read-only tools at <exact candidate SHA>.
```

or:

```text
NO-GO — the trusted-context golden path is not proven; return to <named iteration and blocker>.
```

“MCP implemented,” “tools available,” or a successful LLM demo is not a valid substitute for the
GO statement.

---

## 27. Roadmap Boundary After `v0.4.0`

Items intentionally deferred from this release remain sequenced as follows:

```text
v0.4.x
    additional architecture tools only when usage justifies them

v0.5
    Kubernetes and broader architecture discovery
    additional adapters and deeper runtime discovery

v0.9
    public contract freeze and production qualification

v1.0
    stable Architecture Intelligence Platform
```

Candidate follow-on tools include blast radius and broader claim lookup. They are not promised by
`v0.4.0` and require their own contract and deterministic evaluation before exposure.

The sequencing principle remains:

```text
validate the semantic core first
expose trusted context second
broaden discovery third
freeze and qualify public contracts last
```

---

## 28. Summary

`v0.4.0` is deliberately small in surface area and substantial in product effect:

```text
one semantic service boundary
one qualified answer contract
three read-only tools
one transport
one independent-client golden path
deterministic synthetic and frozen real-system evidence
zero agent-authored architecture truth
```

The release succeeds when AIP can be consumed as trusted architecture context, not when the largest
possible MCP feature list has been implemented.

---

## References

- AIP roadmap: `ROADMAP.md`
- v0.3 release qualification: `docs/specifications/0.3.0/i5-release-qualification.md`
- MCP specification and documentation: <https://modelcontextprotocol.io/specification/2026-07-28>
- MCP transports: <https://modelcontextprotocol.io/specification/2026-07-28/basic/transports>
