# AIP v0.4.0 — I2 MCP Vertical Slice and Evidence Drill-Down

**Status:** Draft 1 — for review  
**Target release:** `v0.4.0`  
**Release increment:** I2  
**Target repository path:** `docs/specifications/0.4.0/i2-mcp-vertical-slice-and-evidence-drill-down.md`  
**Entry baseline:** `main` at `5232e3b3b83c1df87f326d47eb65da1170b14034`  
**Qualified I1 candidate:** `8031f640daac3067ba9e709b19464d8246959fe2`  
**Governing specification:** `docs/specifications/0.4.0/specification.md`, Draft 1.2 semantics  
**Primary outcome:** An independent MCP client obtains an I1 dependency answer and resolves every
referenced evidence record through one read-only, snapshot-bound HTTP tool surface.

---

## 1. Purpose

I1 proved the semantic core of the first `v0.4.0` vertical slice. I2 exposes that qualified
capability through MCP and adds only the evidence drill-down needed to answer why a dependency claim
exists.

I2 SHALL prove:

> **Given one known service and one explicit observation context, an independent MCP client can
> obtain the same deterministic dependency answer qualified in I1, carry its returned snapshot id
> into a second tool call, and resolve the answer's evidence and provenance without graph knowledge
> or write access.**

The complete capability is:

```text
independent MCP client
    -> get_service_dependencies
    -> ArchitectureAnswer<ServiceDependenciesData>
    -> collect evidence references and snapshot_id
    -> get_evidence using the same snapshot_id
    -> ArchitectureAnswer<EvidenceData>
```

The MCP layer SHALL expose I1 semantics. It SHALL NOT reinterpret, summarize, repair, enrich, or
replace them.

---

## 2. Normative Language and Precedence

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

The release specification governs whenever this document is silent. This I2 specification makes
one explicit protocol correction in §4 because MCP `2026-07-28` and the release specification's
older `initialize` wording cannot both be implemented literally.

The I1 service and answer semantics remain authoritative for `get_service_dependencies`. If I2
cannot expose them without changing their meaning, implementation SHALL stop and record the
blocker rather than introduce MCP-only semantics.

Executable JSON Schemas and protocol integration tests become the authoritative wire evidence when
I2 exits.

---

## 3. Entry Conditions and Frozen I1 Results

I2 begins only after I1 qualification and merge. The following I1 results are frozen input:

- `ArchitectureIntelligenceService` is the sole semantic entry point.
- `get_service_dependencies` returns one-hop dependency claims only.
- destination identity is independent from delivery semantics.
- claims retain `CONFIRMED`, `OBSERVED_ONLY`, or `NOT_OBSERVED_IN_WINDOW` qualification.
- unresolved operation or queue destinations are retained rather than guessed.
- qualification and destination-resolution evidence references remain separate.
- answers are bound to a virtual current-state snapshot and explicit observation context.
- stale explicit snapshots fail with `SNAPSHOT_NOT_AVAILABLE`; they do not fall forward.
- service reads use Neo4j `READ_ACCESS`, the revision fence, and zero graph mutations.
- the independently authored I1 suite passes `8/8`, with two byte-identical semantic runs.

I2 MUST NOT reopen dependency projection, claim identity, qualification, context hashing, snapshot
fingerprinting, or retry semantics merely to simplify the MCP adapter.

The I1 contract has two narrow extension points for I2:

1. `ArchitectureAnswer<T>` must support a non-runtime-sensitive `get_evidence` answer whose
   `observation_context` is `null` without falsely reporting `OBSERVATION_CONTEXT_REQUIRED`.
2. The generic envelope must support `EvidenceData` while retaining the exact I1 dependency-answer
   schema and invariants.

These are contract generalizations required by the planned second tool. They are not new
architecture semantics.

---

## 4. MCP Protocol Baseline

I2 SHALL implement MCP revision `2026-07-28` over Streamable HTTP.

This revision is stateless:

- there is no `initialize` request or `notifications/initialized` handshake;
- every request carries the required protocol version and client-capability metadata;
- the server identifies itself in result metadata;
- `tools/list` and `tools/call` are independent requests;
- no behavior depends on a connection-scoped MCP session.

The release specification currently combines MCP `2026-07-28` with older `initialize` language in
§3, §17, §22, and §25. The I2 documentation PR SHALL make the smallest corresponding correction:
replace the `initialize` requirement with a stateless protocol-metadata compatibility check. This is
a protocol-consistency correction, not release rescoping.

Each client message SHALL use HTTP `POST` to one endpoint. I2 requires and qualifies non-streaming
JSON responses only. Persistent subscriptions and server-initiated notifications are out of scope.

The MCP SDK dependency, if used, SHALL be pinned exactly in `uv.lock`. Adopting an older protocol
revision because of SDK convenience requires an explicit specification change.

---

## 5. Scope Budget

| Area | I2 limit |
|---|---|
| MCP endpoints | One Streamable HTTP endpoint |
| Public tools after I2 | Exactly two |
| Tools | `get_service_dependencies`, `get_evidence` |
| New service operations | `get_evidence` only |
| MCP protocol | `2026-07-28` only |
| Evidence references per call | `1..20`, unique |
| Dependency depth | I1's one hop, unchanged |
| Snapshot model | I1 virtual current-state snapshot, unchanged |
| Observation-context persistence | None |
| MCP/session state | None |
| Graph mutations | Zero |
| LLM usage | Zero |
| New evaluation framework | None; full tool evaluation remains I3 |
| New real-system runs | None |

I2 does not pre-implement `get_architecture_drift`; that third release tool remains I3.

---

## 6. In Scope

I2 SHALL deliver:

1. One stateless Streamable HTTP MCP endpoint.
2. Deterministic `tools/list` exposure of exactly two tools.
3. A thin MCP adapter for I1's `get_service_dependencies` operation.
4. `ArchitectureIntelligenceService.get_evidence` as the only new semantic operation.
5. Versioned `EvidenceData` and evidence-record wire contracts.
6. Snapshot-bound resolution of `1..20` opaque evidence references.
7. Deterministic provenance and supported-fact projection.
8. Explicit partial and safe-refusal behavior for unavailable evidence.
9. Output sanitization and a documented local/trusted-network deployment boundary.
10. Service/MCP equivalence, independent-client, determinism, and read-only tests.

---

## 7. Explicit Non-Goals

I2 SHALL NOT implement:

```text
get_architecture_drift or any third tool
MCP resources, prompts, elicitation, sampling, tasks, or subscriptions
stdio or a second transport
connection-scoped sessions or server-side client state
authentication, authorization, tenancy, or a general audit platform
public-internet production exposure
generic evidence search or list-all-evidence
raw evidence payload or OpenTelemetry trace retrieval
generic graph, Cypher, node, or relationship access
new architecture claims, predicates, qualifications, or confidence scores
new discovery sources, adapters, or model relations
transitive traversal or blast radius
LLM-generated summaries
fresh Quarkus or Airflow execution
the full I3 deterministic tool-evaluation matrix
the hero demo
release-candidate qualification or publication
```

---

## 8. Architecture Boundary

```text
independent MCP client
        |
        | Streamable HTTP / JSON-RPC
        v
MCP protocol and input adapter
        |
        v
ArchitectureIntelligenceService
        |
        v
read-only architecture/evidence repository
        |
        v
Neo4j
```

The MCP adapter owns protocol framing, tool-argument validation, service dispatch, conversion of the
returned answer to MCP `structuredContent`, and sanitized execution-error mapping.

The adapter MUST NOT open Neo4j, import graph repositories, contain Cypher, construct or rewrite
claims, resolve evidence directly, replace limitations with prose, or expose a write-capable
interface.

The `ArchitectureIntelligenceService` SHALL remain independently callable without MCP.

---

## 9. Endpoint and Tool Discovery

The default endpoint SHALL be `POST /mcp`. The path MAY be configurable, but one process SHALL
expose only one MCP endpoint.

For MCP `2026-07-28`:

- required per-request protocol/client metadata MUST be validated;
- required Streamable HTTP method/name headers MUST agree with the JSON-RPC body;
- unsupported protocol versions MUST fail explicitly;
- request ids MUST NOT enter semantic answers;
- the server MUST NOT emit an MCP session id;
- `GET` subscriptions and `DELETE` session termination are not required.

`tools/list` SHALL return exactly these names, in lexicographic order:

```text
get_evidence
get_service_dependencies
```

Each definition SHALL provide a bounded read-only description, a closed `inputSchema`, a complete
`outputSchema`, and read-only/non-destructive/idempotent annotations where supported. The static
tool list and its required cache metadata SHALL be deterministic.

---

## 10. `get_service_dependencies` MCP Tool

The MCP input SHALL be isomorphic to I1's `ServiceDependenciesRequest`.

Rules:

1. The adapter validates the closed tool schema and constructs the existing I1 request type.
2. It calls `ArchitectureIntelligenceService.get_service_dependencies` exactly once.
3. `structuredContent` is the complete returned `ArchitectureAnswer` JSON object.
4. No claim, evidence reference, qualification, limitation, snapshot, context value, or semantic
   ordering may be added, omitted, translated, or rewritten.
5. `ANSWERED`, `PARTIAL`, and `NOT_ANSWERED` are successful tool executions with `isError: false`.
6. Malformed arguments are tool-execution errors, not architecture limitations.
7. If compatibility text is emitted, it is the canonical JSON serialization, not narration.

For identical bound inputs, direct-service and MCP structured answers MUST be semantically
identical.

---

## 11. `get_evidence` Service and Tool

The service operation is conceptually:

```python
ArchitectureIntelligenceService.get_evidence(
    request: EvidenceRequest,
) -> ArchitectureAnswer[EvidenceData]
```

### 11.1 Request

```json
{
  "evidence_refs": [
    "evidence:manifest:order-service",
    "evidence:openapi:product-service"
  ],
  "snapshot_id": "aip:snapshot:v1:<sha256>"
}
```

Rules:

- `evidence_refs` contains `1..20` unique opaque ids;
- `snapshot_id` is required and matches the I1 snapshot-id format;
- duplicates, empty/oversized lists, malformed values, and unknown fields are input errors;
- there is no observation-context input;
- requested ids are sorted lexicographically for processing and output;
- the service never defaults to the current snapshot when the requested id is stale.

### 11.2 Evidence Data

```json
{
  "requested_evidence_refs": ["evidence:manifest:order-service"],
  "records": [
    {
      "id": "evidence:manifest:order-service",
      "evidence_type": "DECLARED",
      "source_type": "MANIFEST",
      "source_locator": "architecture.yaml",
      "source_revision": null,
      "observation": null,
      "supports": [
        {
          "relation_type": "CALLS",
          "source_id": "service:order-service",
          "target_id": "operation:service:product-service:GET:/products/{id}"
        }
      ]
    }
  ],
  "missing_evidence_refs": []
}
```

`EvidenceRecord` contains only stable, bounded public metadata:

| Field | Rule |
|---|---|
| `id` | Exact opaque evidence id. |
| `evidence_type` | Existing `DECLARED` or `OBSERVED` value. |
| `source_type` | Existing source type; no new adapter classification. |
| `source_locator` | Sanitized stable locator, or `null` when unsafe/unavailable. |
| `source_revision` | Existing immutable source revision when available, otherwise `null`. |
| `observation` | Existing bounded observation metadata for observed evidence, otherwise `null`. |
| `supports` | Existing relation facts supported by this evidence. |

`source_locator` SHALL be derived without interpretation:

- return the existing `source_file` unchanged only when it is the literal `opentelemetry` or a
  relative POSIX-style path containing no empty, `.` or `..` segment;
- otherwise return `null`;
- do not rewrite an absolute path into a plausible public path and do not return URI user-info,
  query parameters, or fragments.

Observed metadata is limited to `environment`, bucket and first/last-seen timestamps,
`observation_count`, `service_version`, and `correlation_mode`. Raw payloads, authorization values,
full spans, baggage, resource attributes, and sample trace ids are outside the I2 contract.

Each `supports` entry contains only `relation_type`, `source_id`, and `target_id`. It describes an
existing canonical fact; it is not a generic graph record or a new architecture claim.

Ordering is deterministic: requested and missing refs lexicographically, records by `id`, and
supported facts by `(relation_type, source_id, target_id)`. Set-valued lists are deduplicated.

---

## 12. Evidence Outcomes

| Situation | Required result |
|---|---|
| Every requested record resolves | `ANSWERED`; all records returned |
| Some records resolve | `PARTIAL / INSUFFICIENT_EVIDENCE`; resolved records plus missing refs |
| No record resolves | `NOT_ANSWERED / INSUFFICIENT_EVIDENCE`; empty records plus missing refs |
| Requested snapshot is not current | `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE`; no newer-state lookup |
| Stable read cannot be acquired | `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE` |

For `get_evidence`, `claims` and top-level `evidence_refs` are empty because lookup creates no claim;
resolved ids live in `data.records`. `observation_context` is `null` because the tool is not
runtime-context-sensitive. `snapshot` identifies the stable state used for the decision when one
could be acquired.

Missing refs appear in `data.missing_evidence_refs` and one deterministic
`INSUFFICIENT_EVIDENCE` limitation; silent omission is forbidden. I2 SHALL NOT add a new limitation
code solely for lookup.

---

## 13. Snapshot Consistency

`get_evidence` SHALL reuse I1's virtual snapshot and revision fence. Each attempt reads the revision,
full fingerprint projection, requested evidence and supported relations, and the revision again.
Only an unchanged attempt is accepted; mixed values are discarded and retried up to I1's fixed
limit.

After a stable attempt, the required request `snapshot_id` is compared with that fingerprint. A
mismatch is rejected before returning evidence. The connection, request id, client metadata, and
input ordering MUST NOT influence the snapshot or semantic response.

---

## 14. Contract Generalization

I2 retains one `ArchitectureAnswer<T>` family with two closed specializations:

```text
ArchitectureAnswer<ServiceDependenciesData>
ArchitectureAnswer<EvidenceData>
```

I1 invariants remain unchanged for `get_service_dependencies`. For `get_evidence`, null observation
context, empty claims/top-level evidence refs, `EvidenceData`, and a required request snapshot are
valid.

The executable schemas MAY be separate roots sharing common definitions. They MUST NOT use an
unconstrained `data: object` or weaken the qualified dependency schema.

---

## 15. Read-Only and Output Safety

- Every service call uses Neo4j `READ_ACCESS`.
- The MCP package has no graph-session or write-repository dependency.
- No tool accepts Cypher, SQL, shell, prompts, URI fetches, paths, or executable expressions.
- No tool imports architecture declarations or telemetry.
- Success, refusal, input error, cancellation, and internal error leave the revision fence and
  canonical fingerprint unchanged.
- Internal exceptions, credentials, connection strings, server paths, and raw graph values outside
  the public contract are never returned.

I2 does not implement authorization. The server binds to loopback by default and documentation SHALL
describe it as local or explicitly trusted-network evaluation only. It MUST NOT claim production-safe
public exposure.

---

## 16. Determinism and Failure Mapping

For fixed producer, snapshot, request, and context where applicable, direct-service and MCP answers
are semantically identical and canonical structured content is byte-identical across calls. Tool
definitions, evidence records, and supported facts use documented stable ordering. Generated prose,
request time, request id, client identity, and connection state do not affect semantic output.

| Failure class | MCP representation |
|---|---|
| Malformed JSON-RPC, unknown method/tool | JSON-RPC protocol error |
| Invalid tool arguments | Tool execution error with `isError: true` |
| Supported question cannot be answered safely | Valid `ArchitectureAnswer`, `isError: false` |
| Unexpected internal/driver failure | Sanitized tool execution error with `isError: true` |

Every successful call provides `structuredContent` conforming to the advertised output schema.
The MCP tool result SHALL use `resultType: "complete"`; multi-round-trip `input_required` results
are outside I2. If compatibility text is emitted, it SHALL contain the same canonical JSON and no
additional claim-bearing prose.

---

## 17. Required Test Scenarios

I2 adds focused tests rather than duplicating I1's semantic matrix.

### Protocol and Discovery

1. MCP `2026-07-28` request metadata is accepted; missing/unsupported metadata fails.
2. No `initialize` handshake or session id is required.
3. `tools/list` returns exactly two tools in deterministic order with closed schemas.
4. Unknown tools and extra arguments fail without calling the service.

### Dependency Adapter

5. A confirmed I1 dependency answer survives MCP without semantic change.
6. Valid empty and safe-refusal answers retain their exact I1 meaning.
7. Direct service and MCP output validate against the same dependency schema.
8. Two identical calls produce identical canonical structured content.

### Evidence Drill-Down

9. All qualification and resolution evidence from a dependency answer resolves using its snapshot.
10. Declared evidence returns source provenance and supported facts.
11. Observed evidence returns bounded environment/time/count/correlation metadata.
12. Mixed existing/missing refs produce deterministic `PARTIAL / INSUFFICIENT_EVIDENCE`.
13. All-missing refs produce deterministic `NOT_ANSWERED / INSUFFICIENT_EVIDENCE`.
14. A stale snapshot returns `SNAPSHOT_NOT_AVAILABLE` and no newer-state records.
15. Empty, duplicate, oversized, malformed, and extra inputs fail validation.
16. Repeated evidence calls produce identical canonical structured content.

### Read-Only and Independent Client

17. The MCP adapter imports no graph repository and opens no Neo4j session.
18. Both service operations request `READ_ACCESS` and leave revision/fingerprint unchanged.
19. Concurrent evidence writes force retry or safe refusal, never a mixed response.
20. Failure paths also leave graph state unchanged.
21. A separately instantiated HTTP client performs `tools/list`, calls dependencies, extracts the
    snapshot/evidence refs, calls evidence, and validates both advertised output schemas.
22. The client imports no AIP internal module and requires no LLM key.

---

## 18. Qualification Boundary

I2 qualification includes unit, Neo4j integration, service/MCP equivalence, one real HTTP
independent-client golden path, read-only state assertions, all existing regression suites, lint,
format, CI, CodeQL, and dependency audit.

It reuses a small subset of independently authored I1 fixtures, including one confirmed dependency
with declared, observed, and destination-resolution evidence. Expected I1 answers MUST NOT be
regenerated from MCP output.

I2 does not create the final machine-readable multi-tool evaluation report, qualify frozen Quarkus
and Airflow inputs, or execute two release-level passes. Those remain I3 responsibilities.

No I2 dossier is required. Executable schemas, tests, the PR verification record, and a short
`0.4.0/README.md` status update are sufficient.

---

## 19. Delivery Split

### I2.1 — Protocol and Contract Skeleton

Freeze MCP `2026-07-28`, correct the parent `initialize` wording, add evidence schemas, generalize
the envelope without weakening I1, and expose deterministic two-tool discovery.

### I2.2 — Dependency MCP Adapter

Map MCP input to the I1 request, call the service only, return exact structured content, and prove
service/MCP equivalence plus read-only behavior.

### I2.3 — Evidence Service and Tool

Implement snapshot-bound evidence resolution, bounded sanitized provenance, explicit missing/stale
behavior, and the thin MCP adapter.

### I2.4 — Independent-Client Qualification

Run the real HTTP golden path, validate schemas and deterministic outputs, prove zero graph writes,
run all checks on one exact candidate, and update the `0.4.0` status index.

---

## 20. Release Blockers

Any of the following blocks I2:

```text
MCP dependency output differs semantically from the direct I1 service answer
adapter adds, drops, rewrites, or weakens a claim or limitation
evidence is resolved outside the required snapshot
stale snapshot silently falls forward
missing evidence is silently omitted or provenance/support is guessed
I1 dependency contract is weakened for the evidence tool
implementation requires initialize while claiming MCP 2026-07-28
connection state or session id affects behavior
tools/list exposes anything other than the two I2 tools
adapter accesses Neo4j or repositories directly
any success or failure path mutates graph state
raw secrets, paths, payloads, or sample trace ids are exposed
structured output violates its advertised schema or is nondeterministic
independent client cannot complete the dependency-to-evidence path
required checks fail or a blocking review finding remains open
```

Targets:

```text
MCP/direct semantic differences = 0
broken evidence references in the golden path = 0
write-capable MCP operations = 0
unexpected public tools = 0
I2 blockers = 0
```

---

## 21. Definition of Done

- [ ] One Streamable HTTP endpoint implements MCP `2026-07-28` without `initialize` or sessions.
- [ ] Exactly `get_service_dependencies` and `get_evidence` are listed.
- [ ] An independent client completes the dependency-to-evidence golden path.
- [ ] The I1 dependency answer is unchanged through MCP.
- [ ] `EvidenceRequest`, `EvidenceData`, and both output schemas are executable and closed.
- [ ] Evidence lookup requires and preserves one explicit snapshot.
- [ ] Missing evidence and stale snapshots are explicit and deterministic.
- [ ] `get_evidence` creates no architecture claim.
- [ ] Null observation context for evidence does not weaken the I1 context requirement.
- [ ] MCP adapters depend only on the service boundary.
- [ ] Both tools and all failure paths are proven read-only.
- [ ] Inputs are bounded and output contains no raw payload or sample trace id.
- [ ] Tool discovery and repeated semantic outputs are deterministic.
- [ ] Focused I2 and all existing regression tests pass.
- [ ] CI, CodeQL, and dependency audit pass on the exact I2 candidate.
- [ ] I2 blockers equal `0`.

---

## 22. Exit Statement

```text
GO — At <exact candidate SHA>, an independent MCP 2026-07-28 client can obtain AIP's qualified,
snapshot-bound direct-dependency answer and resolve its evidence and provenance through two
read-only tools, with semantic differences from direct service calls = 0 and graph writes = 0.
```

or:

```text
NO-GO — the MCP dependency-to-evidence vertical slice is not proven; return to
<named I2 sub-increment and blocker>.
```

“MCP server starts,” “tool appears in a client,” or a successful LLM narration is not a substitute.

---

## 23. Boundary to I3

I2 hands I3 one endpoint, two read-only tools, the unchanged I1 dependency contract, one
snapshot-bound evidence drill-down contract, and one independent-client golden path.

I3 owns `get_architecture_drift`, the complete three-tool deterministic evaluation, frozen Quarkus
and Airflow evidence qualification, two complete repeated runs, and the five-minute hero demo.

---

## References

- `docs/specifications/0.4.0/specification.md`
- `docs/specifications/0.4.0/i1-service-contract-and-dependency-vertical-slice.md`
- `docs/specifications/0.4.0/i1-completion-record.md`
- <https://modelcontextprotocol.io/specification/2026-07-28>
- <https://modelcontextprotocol.io/specification/2026-07-28/server/tools>
- <https://modelcontextprotocol.io/specification/2026-07-28/basic/transports>
- <https://modelcontextprotocol.io/specification/2026-07-28/changelog>
