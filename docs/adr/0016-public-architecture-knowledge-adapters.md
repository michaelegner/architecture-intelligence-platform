# 16. Use REST and standard negotiated MCP as the public Architecture Knowledge adapters

Status: Proposed — targeted for `v0.5.0` I3 Slice 5.

## Context

`v0.4.0` introduced a strict direct MCP envelope so AIP's first agent-facing architecture surface
could be deterministic, bounded, and independently qualified. `v0.4.2` then added standard
negotiated MCP alongside that direct mode and qualified real coding-agent clients without changing
Architecture Knowledge semantics. ADR 0014 records that dual-mode decision and remains the
historical record for `v0.4.2`.

The architecture has since acquired a clearer semantic boundary:

```text
ArchitectureIntelligenceService
        |
        +-- architecture-answer evaluator (direct in-process invocation)
        +-- MCP adapter
```

The deterministic evaluator already invokes `ArchitectureIntelligenceService` directly. It does not
need the direct MCP envelope to establish a transport-independent semantic oracle.

`v0.5.0` I3 also needs REST exposure for the same Architecture Knowledge. If direct MCP were kept,
the public/qualification topology would become:

```text
ArchitectureIntelligenceService
        |
        +-- evaluator
        +-- REST
        +-- direct MCP
        +-- negotiated MCP
```

That would preserve two MCP connection modes after REST has taken over the general deterministic HTTP
integration role. Every release would then continue to qualify REST, direct MCP, negotiated MCP, and
the service boundary even though direct MCP no longer has a distinct responsibility.

The desired responsibility split is instead:

```text
                    ArchitectureIntelligenceService
                              |
              +---------------+---------------+
              |                               |
             REST                     standard negotiated MCP
              |                               |
      general integrations                agent clients

architecture-answer evaluator
      |
direct in-process service invocation
      |
transport-independent qualification
```

The AIP × Glamorous Toolkit reference integration further validates standard negotiated MCP as a
real agent-facing path: a GT-hosted agent can select AIP tools, chain evidence requests, preserve
snapshot-bound Architecture Answers, and derive bounded ephemeral micro-tools without becoming an
architecture authority. That validation does not require preserving a bespoke direct MCP transport.

## Decision

1. **`ArchitectureIntelligenceService` is the single semantic owner for public Architecture
   Knowledge.** Public adapters may map transport inputs and outputs, but they do not independently
   derive, qualify, strengthen, suppress, or reinterpret architecture claims.

2. **`v0.5.0` has two public Architecture Knowledge adapters: REST and standard negotiated MCP.**
   They expose equivalent service-owned semantics for equivalent requests even when their transport
   envelopes or HTTP/JSON-RPC error mapping differ.

3. **The AIP-specific direct MCP envelope is retired in `v0.5.0`.** `POST /mcp` remains the sole
   MCP endpoint, but it serves standard negotiated MCP only. Direct-envelope marker detection,
   routing, and direct-mode compatibility are no longer part of the v0.5 public contract.

4. **The deterministic architecture-answer evaluator remains the transport-independent
   qualification oracle.** It invokes `ArchitectureIntelligenceService` directly, as it already
   does. No replacement "internal transport" or adapter framework is introduced.

5. **REST parity is completed in I3 before deployment public exposure is considered complete.**
   The v0.5 I3 contract freezes REST access for existing dependency, drift, and bounded evidence
   resolution semantics and the new deployment view. REST adapters call the corresponding
   `ArchitectureIntelligenceService` capability or project a bounded subset from its returned
   answer; they do not create a second graph/qualification path.

6. **Standard negotiated MCP retains exactly the existing three read-only tools:**

   ```text
   get_architecture_drift
   get_evidence
   get_service_dependencies
   ```

   Deployment semantics are added to `get_service_dependencies` as a separate sibling projection;
   no fourth MCP tool is introduced.

7. **Cross-surface qualification uses the service result as the reference point.** The release proves:

   ```text
   deterministic evaluator -> ArchitectureIntelligenceService
   REST                    == ArchitectureIntelligenceService semantics
   negotiated MCP          == ArchitectureIntelligenceService semantics
   REST                    == negotiated MCP semantics for equivalent requests
   ```

   Equality here means Architecture Knowledge semantics: outcome, claims and identities,
   qualifications, snapshot and observation context, evidence references and roles, deployment
   resolutions, limitations, ordering, and schema meaning where applicable. Transport envelopes
   need not be byte-identical.

8. **Historical release records are not rewritten.** `v0.4.0` through `v0.4.2` specifications,
   ADRs, release validation, examples, and qualification evidence remain accurate records of the
   direct and dual-mode contracts that those releases shipped.

9. **This is an intentional pre-`1.0` compatibility change.** The repository already states that
   REST/MCP contracts may change on a minor release before `1.0`. The removal is made in the same
   release that completes REST parity so v0.5 does not first qualify a redundant third public
   adapter and remove it later.

## Consequences

- I3 Slice 5 is split into public-adapter consolidation/REST parity followed by deployment public
  exposure.
- The v0.5 parent specification no longer requires direct/negotiated MCP equivalence. It requires
  deterministic service evaluation, REST/service equivalence, negotiated-MCP/service equivalence,
  and REST/MCP cross-surface consistency.
- The published-image golden path uses REST plus standard negotiated MCP rather than direct plus
  negotiated MCP.
- `app/mcp/guard.py` and its tests can drop direct-mode classification and direct-envelope-specific
  compatibility behavior while retaining whatever HTTP method, Host/Origin, sanitization, and
  negotiated-protocol protections remain required.
- Existing shell/demo workflows that used direct MCP move to REST when they need deterministic HTTP
  invocation; agent demonstrations use standard negotiated MCP.
- Future Architecture Knowledge capabilities have one semantic owner and two public adapter types,
  reducing qualification and maintenance multiplicity.
- The reference-integration strategy remains free to use negotiated MCP for agentic/moldable
  workflows and REST for general deterministic integrations; neither surface owns architecture
  semantics.

## Alternatives considered

### Keep REST, direct MCP, and negotiated MCP

Rejected. Once REST provides the general deterministic integration surface and the evaluator invokes
the service directly, direct MCP has no distinct architectural responsibility. Keeping it permanently
multiplies transport, security, documentation, and release-qualification work.

### Keep direct MCP and remove negotiated MCP

Rejected. Standard negotiated MCP is the interoperability path used by qualified coding-agent
clients and by the validated GT-hosted agent integration. A bespoke direct envelope is not a
substitute for standard client interoperability.

### Expose Architecture Knowledge only through MCP

Rejected. AIP also needs a deterministic, non-agent-specific integration surface. REST provides that
surface without requiring general engineering tools or scripts to implement MCP negotiation.

### Introduce a new internal deterministic adapter

Rejected. The existing architecture-answer evaluator already invokes
`ArchitectureIntelligenceService` directly. A new adapter abstraction would add machinery without
adding a semantic capability.

## Implementation and supersession

This ADR is **Proposed** until the v0.5 I3 public-adapter implementation lands.

When that implementation is accepted:

- this ADR moves to **Accepted**;
- ADR 0014 is marked **Superseded by 0016** for the active v0.5+ architecture;
- ADR 0014 remains unchanged otherwise as the historical rationale and implementation record for
  the v0.4.2 dual-mode MCP release.
