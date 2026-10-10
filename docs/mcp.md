# MCP Tools

AIP exposes its validated architecture model to AI agents and other MCP clients as four
**read-only** tools, mounted at the single public path `/mcp`. As of `v0.5.0` I3 (ADR 0016),
`ArchitectureIntelligenceService` is the single semantic owner of this Architecture Knowledge, and
standard negotiated MCP is one of its two public adapters (the other is [REST](architecture.md#api-surface))
— the `v0.4.x` AIP-specific "direct mode" envelope is retired; `/mcp` now serves standard negotiated
MCP only. See
[`docs/adr/0016-public-architecture-knowledge-adapters.md`](adr/0016-public-architecture-knowledge-adapters.md)
for the decision record, and
[`docs/adr/0014-negotiated-mcp-client-interoperability.md`](adr/0014-negotiated-mcp-client-interoperability.md)
(superseded by 0016 for the active `v0.5+` architecture) for the historical `v0.4.2` dual-mode record.

A standard MCP client connects with a markerless `initialize` request followed by ordinary
`MCP-Protocol-Version`-headed traffic, handled by the pinned MCP SDK — see `## Connecting a
negotiated client` below.

`/mcp` supports `POST` only in this stateless release. Every other HTTP method — `GET`, `DELETE`,
`HEAD`, and everything else — returns `405 Method Not Allowed` with `Allow: POST` before dispatch
(and, for every method but `HEAD`, a small bounded JSON error body).

See [`docs/specifications/0.4.0/specification.md`](specifications/0.4.0/specification.md) for the
full normative tool contract (unchanged since `v0.4.0`),
[`docs/specifications/0.4.1/specification.md`](specifications/0.4.1/specification.md) for the
qualification/messaging semantic hardening layered on top in `v0.4.1`, and
[`docs/specifications/0.5.0/i3-runtime-identity-reconciliation.md`](specifications/0.5.0/i3-runtime-identity-reconciliation.md)
§14 for the `v0.5.0` public-adapter consolidation; this page is a short practical reference.

Every answer's `producer.version` reports the current package/producer version — this is
build/producer metadata, separate from the public `schema_version`. For `get_service_dependencies`
and `get_evidence` the public `schema_version` is `"0.5"` (as of `v0.5.0` I3) **unless the answer
carries Broker data**, in which case it is `"0.6"` (since `v0.6.1` I2; see
[Broker claims](#broker-claims-v061-i2) below). `get_architecture_drift` stays `"0.5"` and the
fourth tool has its own `"0.6"` contract.

> AIP may help agents reason about architecture, but an agent must never become the source of
> architectural truth. — [`ROADMAP.md`](../ROADMAP.md)'s v0.4 principle.

## The four tools

`tools/list` always returns exactly these four, in this fixed lexicographic order:

| Tool | Purpose |
|---|---|
| `get_architecture_drift` | Direct dependencies of a service whose current evidence qualification shows a declared-versus-observed discrepancy (`OBSERVED_ONLY` or `NOT_OBSERVED_IN_WINDOW`) — never `CONFIRMED` — bound to one stable snapshot. |
| `get_evidence` | Resolves 1-20 opaque evidence references to bounded, sanitized provenance for one explicit snapshot. |
| `get_service_dependencies` | One-hop direct dependencies of a service, qualified against declared and observed evidence and bound to a stable snapshot. Also returns the service's Service-Workload deployment claims and resolutions (explicit annotation, configured mapping, or observed OpenTelemetry/Kubernetes linkage), reconciled across all applicable methods. |
| `get_service_dependencies_by_locality` | Since v0.6.0 I3: where a service's direct HTTP dependencies are positively established, per evidenced caller-Workload locality, with an optional same-snapshot comparison; a second mode resolves the answer's scoped evidence refs. See [below](#get_service_dependencies_by_locality-v060-i3). |

All four:

- take one `request` argument matching their JSON Schema exactly (closed `inputSchema`; an
  unrecognized field inside `request` is rejected before dispatch). An unexpected *top-level*
  argument beside `request` is rejected before dispatch by `get_service_dependencies_by_locality`
  only; for the three v0.5 tools the pinned SDK silently ignores it, unchanged since v0.5.0;
- return `structuredContent` as an answer envelope (`ArchitectureAnswer` for the three v0.5 tools,
  `LocalityAnswer` for the fourth) (`schema_version`, `producer`,
  `snapshot`, `outcome`, plus the tool-specific data/claims) validated against the tool's
  advertised `outputSchema`. For `get_service_dependencies` and `get_evidence` that `outputSchema`
  is a `oneOf` discriminated by `schema_version`: the released v0.5 answer or the Broker-aware v0.6
  answer;
- perform zero graph writes and require no LLM API key;
- never invent, guess, or upgrade an unresolved fact — insufficient evidence is returned as a
  `limitations` entry, never silently treated as absence.

Schemas live at `schemas/architecture_intelligence/v0.5/`:
`architecture-answer.schema.json` (`get_service_dependencies`), `drift-answer.schema.json`
(`get_architecture_drift`), `evidence-answer.schema.json` (`get_evidence`), and at
`schemas/architecture_intelligence/v0.6/`: for the fourth tool,
`service-dependencies-by-locality-request.schema.json` (its `request` argument) and
`service-dependencies-by-locality-answer.schema.json` (its answer); and, since v0.6.1 I2, the
Broker-aware `architecture-answer.schema.json` and `evidence-answer.schema.json`. The v0.5 files
are immutable.

## Broker claims (v0.6.1 I2)

v0.6.1 I2 adds no tool, transport mode or REST endpoint. `Service -[USES_BROKER]-> Broker` (declared
by an AsyncAPI `x-aip-broker-id` or an Architecture Manifest `brokers[].brokerId`; see
[`ingestion.md`](ingestion.md)) surfaces through `get_service_dependencies` and `get_evidence`, and
through their REST equivalents `GET /api/services/{id}/dependencies` and
`POST /api/evidence/resolve`.

- **`BrokerClaim`.** A sibling kind in `claims`, beside `DependencyClaim` and `DeploymentClaim`:
  `subject` (the Service), `predicate` `USES_BROKER`, `object` a bounded `BrokerRef` (`id` = the
  canonical Broker id, `type` `BROKER`, `name` = the explicit stable broker id the source declared)
  and sorted, deduplicated, non-empty `evidence_refs`. It has no `delivery`, qualification or
  coverage, and never implies a Queue, Topic, Subscription, Message, producer or consumer.
  `data.broker_claim_ids` lists them, a sibling of `dependency_claim_ids` and
  `deployment_claim_ids`. The claim id is
  `aip:claim:v1:sha256(canonical-json({"predicate": "USES_BROKER", "service_id", "broker_id"}))`.
- **The version follows the data.** A `get_service_dependencies` answer with at least one
  BrokerClaim is the v0.6 shape (`schema_version` `"0.6"`); with none it is exactly the v0.5 shape,
  with no empty Broker field. A `get_evidence` answer that returns a record supporting a
  `USES_BROKER` fact is v0.6, and each such supported fact carries a `broker` object (`id`, `type`
  `BROKER`, `name`); otherwise it is v0.5. A refusal (`NOT_ANSWERED`) is always v0.5. After a
  Service gains its first qualified Broker claim, its dependency answer therefore changes from the
  v0.5 branch to the v0.6 branch; this is deterministic, not an opt-in mode. A client that validates
  against the advertised `oneOf` (or against the frozen file for the answer's own `schema_version`)
  handles both.
- **Unchanged.** `get_architecture_drift` never returns a BrokerClaim and stays `"0.5"`; the
  locality tool is unchanged (Broker use is not locality-qualified); the REST-only
  `GET /api/services/{id}/deployments` view carries no Broker data and keeps `schema_version`
  `"0.5"` even when the underlying dependency answer is v0.6. The tool count and order are
  unchanged.
- **Evidence.** Every `evidence_refs` entry of a BrokerClaim resolves through `get_evidence` at the
  same snapshot to a v0.6 record whose `supports` include exactly that `(USES_BROKER, Service,
  Broker)` fact. A Broker relation with no resolvable evidence yields no claim and one
  `INSUFFICIENT_EVIDENCE` limitation.

## Pub/Sub in dependency and drift answers (v0.5.0 I4)

I4 adds no MCP tool, transport mode or REST endpoint. Declared Topic/Subscription topology surfaces
inside the existing `get_service_dependencies`/`get_architecture_drift` claims (and the matching
`GET /api/services/{id}/dependencies`/`/drift`). `ArchitectureIntelligenceService` is the only
semantic owner, and REST and MCP never derive Pub/Sub topology on their own.

**The delivery.** A Pub/Sub dependency claim has `delivery.kind = ASYNC_MESSAGE`, `relation_type =
PUBLISHES_TO`, and `via` = the Topic. `DeliveryRef.subscription` is either `null` or the Subscription
the route runs through. That Subscription is always `SUBSCRIPTION_OF` the `via` Topic in the same
snapshot. HTTP and Queue deliveries always carry `subscription = null`. `EntityType` gains `TOPIC` and
`SUBSCRIPTION`.

**Projection** (`app/architecture_intelligence/dependency_projection.py`):

| Declared situation | Claim `object` | `destination_resolution` |
|---|---|---|
| Topic with no usable Subscription | the Topic | `DIRECT_TARGET_FALLBACK` + `UNRESOLVED_IDENTITY` |
| Subscription with no evidenced consumer | the Subscription (routed through it) | `DIRECT_TARGET_FALLBACK` + `UNRESOLVED_IDENTITY` |
| Subscription with consumer Service(s) | one claim per distinct consumer Service, each routed through that Subscription | `RESOLVED_SERVICE` |

Rules behind the table:
- **Instances collapse:** several instances of one Service collapse into one claim with unioned
  evidence.
- **Competing consumers:** several Services on one Subscription are competing consumers, not fan-out.
- **Fan-out:** fan-out appears only as distinct Subscription routes, meaning distinct claims.
- **Usable route:** a route is usable only when its `SUBSCRIPTION_OF` carries accepted evidence.
  That evidence joins `resolution_evidence_refs` on resolved claims only, because fallback claims
  keep empty resolution refs.
- **Qualification:** qualification comes only from the publisher's own `PUBLISHES_TO` evidence, the
  same as a Queue claim's `SENDS`. A consumer's evidence appears only in its own route's
  `resolution_evidence_refs`, so evidence for one Subscription never touches a sibling.
- **No Pub/Sub drift from unmatched spans:** runtime-only Topics and Subscriptions are never minted.
  So an unmatched consumer span creates no `OBSERVED_ONLY` Pub/Sub claim.

**Claim identity.** The claim-id payload gains an optional `subscription_id`. It is present only for a
Subscription route and omitted entirely otherwise, so every pre-I4 HTTP and Queue claim id is
byte-identical.

**Evidence and schema.** `get_evidence` reports `PUBLISHES_TO` and `SUBSCRIPTION_OF` (new
`EvidenceRelationType` members), plus the reused `RECEIVES_FROM`/`CARRIES`, as supported facts. The
internal dead-letter carrier is never publicly resolvable. `schema_version` stays `"0.5"`.

## `DEPLOYED_AS` deployment claims (v0.5.0 I3)

v0.5.0 I3 added zero new MCP tools — `tools/list` kept exactly the three v0.5 tools, in the same
fixed order (the fourth arrived only in v0.6.0 I3). `Service -[DEPLOYED_AS]-> Workload` identity is folded entirely into
`get_service_dependencies`'s existing `data.deployment_claim_ids` / `data.deployment_resolutions`
fields (siblings of, never merged into, `data.dependency_claim_ids`) and into the same answer's
`claims` union, which now closes over `DependencyClaim | DeploymentClaim`. A `DeploymentClaim`'s
`object` is a bounded `WorkloadRef` (`id`, `type`, `name`, `workload_kind`, `namespace`) — never a
`Workload`-typed `EntityRef`, and never any Pod/cluster-UID/owner-chain detail beyond those fields;
its `resolution_method` names the strongest agreeing identity path
(`RESOLVED_EXPLICIT`/`RESOLVED_CONFIGURED`/`RESOLVED_OBSERVED`). Every reconciliation outcome —
resolved or not — is also returned as its own `DeploymentResolution`, whose `status` is one of
`RESOLVED_EXPLICIT`/`RESOLVED_CONFIGURED`/`RESOLVED_OBSERVED`/`CONFLICT`/`AMBIGUOUS`/`UNRESOLVED`, so
a client can always see *why* a deployment didn't resolve, not just that it didn't. `get_evidence`
resolves every deployment evidence ref a resolved-or-not outcome cites, the same as any other
evidence — see [`evidence.md`](evidence.md) and
[`graph-model.md`](graph-model.md#deployed_as-v050-i3--computed-not-a-stored-graph-edge) for the full
contract. `get_architecture_drift` never returns a `DeploymentClaim` — drift stays deployment-
agnostic, unchanged in meaning by I3.

## Qualification consistency with the analysis/REST surface (v0.4.1 ADR 0010)

These MCP tools require the explicit observation context defined by the v0.4 contract above —
unlike the analysis/REST path (see [`analyses.md`](analyses.md)'s runtime analyses), which may use
an implicit clock-relative default window and may allow an open-ended upper bound.

> Equivalent effective observation contexts MUST produce equivalent qualification semantics.
> Different effective observation windows MAY legitimately produce different qualifications.

Both surfaces share one semantic owner for declared-vs-observed evidence matching and coverage
classification (`app/qualification/declared_observed.py`), proven equivalent by a real Neo4j
differential test (`tests/integration/test_qualification_consistency.py`) rather than by inspection
alone.

## `get_service_dependencies_by_locality` (v0.6.0 I3)

The fourth tool answers **where** a service's direct HTTP `CALLS` are positively established, per
evidenced caller-Workload locality (cluster, namespace and captured Workload), for an explicit
environment and whole-UTC-day window, without the caller naming any Workload first. Its contract is
the locality schema `0.6`
([decision record](specifications/0.6.0/i3-decision-record.md) D1–D17), not a widening of the v0.5
`ArchitectureAnswer`. The single `request` argument is discriminated on `mode`:

- `"query"`: a bounded, evaluated inventory of the caller's scoped observations and every
  admitted capture pair, the positive localities with their per-Operation qualification and
  provider-Service groups, and optionally the selection or a two-Workload comparison. Bounds,
  continuation (`next_cursor`) and every unknown, unresolved or excluded item stay explicit;
- `"evidence"`: resolves up to 20 exact refs from such an answer (scoped v2 records and their
  Pod/owner capture evidence) at the **same `snapshot_id`**. Legacy `get_evidence` does not
  resolve scoped records and does not change.

A positive result is never an exhaustive partition of the service's dependencies: a relationship
missing from one Workload is not evidence of its absence there. Workload-level coverage is
unavailable (`LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE`), and the target's runtime placement stays
`UNKNOWN`. Unlike the three v0.5 tools, this tool also rejects an unexpected top-level argument
beside `request` before dispatch.

The REST parity routes are `POST /api/services/{service_id}/dependencies/by-locality` and
`…/by-locality/evidence`. The Service comes from the path, and the closed JSON body carries every
other request field (no `subject_service_id`, no `mode`). A malformed body is `422`; every evaluated
or refused answer is `200` with the same envelope MCP returns.

## Connecting a negotiated client

A standard MCP client — the kind a mainstream coding-agent tool ships out of the box, or a hand-
rolled HTTP/JSON-RPC client — connects to `http://localhost:8000/mcp` and speaks ordinary negotiated
MCP: an `initialize` request followed by `tools/list`/`tools/call` requests. This project's mounted
MCP app runs the pinned SDK's session manager in stateless mode, so a standalone `tools/list`/
`tools/call` is answered statelessly with no prior `initialize` required on the same connection — no
session identifier is issued.

A minimal `get_service_dependencies` call, with no prior handshake:

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -H 'mcp-protocol-version: 2025-11-25' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_service_dependencies",
      "arguments": {
        "request": {
          "service_id": "service:order-service",
          "observation_context": {
            "environment": "demo",
            "window_start": "2026-08-26T00:00:00.000000Z",
            "window_end": "2026-08-27T00:00:00.000000Z"
          }
        }
      }
    }
  }'
```

`get_architecture_drift` takes the identical `request` shape (`service_id` +
`observation_context`); `get_evidence` instead takes `{"evidence_refs": [...], "snapshot_id":
"..."}`, both usually read from a prior answer's own `evidence_refs`/`snapshot.snapshot_id`. The
four tools, their schemas, and their `ArchitectureAnswer` semantics are identical whether reached
over MCP or over the equivalent [REST endpoint](architecture.md#api-surface) — only the transport
envelope differs (ADR 0016 decision #7).

Client-specific setup steps for particular coding-agent tools are out of scope for this page — see
[`examples/mcp-clients/`](../examples/mcp-clients/README.md) for candidate setup guides (Codex CLI,
Claude Code, Cursor, VS Code). Setup syntax is verified separately from interoperability
qualification; see the
[v0.4.2 client/platform qualification matrix](release-validation/v0.4.2-client-qualification.md) for
which specific client/version combinations have actually been qualified end to end. Those
combinations were qualified against `v0.4.2` and have not been re-qualified since.

## Local security boundary

`/mcp` is built for a local or trusted-network posture, as in every release so far: it
has no public-internet authentication, so do not expose it directly to an untrusted network. A
request whose `Origin` or `Host` header falls outside the configured `allowed_origins`/`allowed_hosts`
allowlists (`app/settings.py`, both passed to the SDK's `TransportSecuritySettings`) is rejected with
`403` before dispatch (confirmed by
`test_negotiated_origin_and_host_security_matches_direct_mode`, a name retained from the now-historical
`v0.4.2` dual-mode era). AIP itself needs no LLM API key for this deterministic tool-call path — the
coding-agent client on the other end may still need its own account or model access, independent of
AIP.

## Evidence drill-down

Every claim from `get_architecture_drift`/`get_service_dependencies` carries `evidence_refs` (and,
where applicable, `resolution_evidence_refs`) — opaque IDs, never raw span/trace payload. Resolve
them with `get_evidence`, passing the **same `snapshot_id`** the first answer returned, so both
calls read the same immutable graph state.

## Try it end to end

[`examples/runtime-demo/hero-demo.md`](../examples/runtime-demo/hero-demo.md) is a complete,
deterministic, ~5-minute walkthrough: bring up AIP, seed frozen evidence, discover all four tools
via `tools/list`, then exercise the drift → evidence path via plain `curl` and see a real
`OBSERVED_ONLY` finding (`OrderService -> LegacyPricingService`) plus its evidence — no AIP internal
module, no LLM.
