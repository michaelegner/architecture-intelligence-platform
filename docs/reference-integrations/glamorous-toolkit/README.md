# AIP × Glamorous Toolkit Reference Integration

**Status:** validated reference integration  
**Date:** 2026-09-21  
**AIP baseline:** v0.4.2 MCP contract  
**Consumer:** Glamorous Toolkit / gt4llm

This reference integration demonstrates that AIP can serve as an **evidence-qualified architecture knowledge layer** for an independent agentic and moldable development environment.

The integration validates more than transport compatibility. It exercises a complete consumer pattern:

```text
Architecture question
        ↓
Agent chooses AIP capabilities
        ↓
AIP MCP tools
        ↓
Evidence-qualified, snapshot-bound architecture knowledge
        ↓
Agent follows provenance where needed
        ↓
Glamorous Toolkit makes the result inspectable and moldable
        ↓
Agent may derive an ephemeral micro-tool
        ↓
Developer controls what becomes permanent
```

AIP remains the source of architecture facts. GT provides exploration, presentation, contextual micro-tools, and agent interaction on top of those facts.

## Results

| PoC | Scope | Result |
|---|---|---|
| [PoC 1](poc-1-moldable-runtime-profile.md) | Runtime-profile integration, live GT objects, MCP interoperability | PASS |
| [PoC 2](poc-2-evidence-exploration.md) | Moldable exploration of evidence and provenance | PASS |
| [PoC 3](poc-3-agentic-architecture-exploration.md) | Agent-selected AIP questions and chained MCP calls | PASS |
| [PoC 4](poc-4-dynamic-moldable-tools.md) | Agent-derived ephemeral GT micro-tools with human-controlled promotion | PASS |

A separate [gt4llm MCP interoperability note](gt4llm-mcp-interoperability.md) records a client-side adapter issue discovered during the integration and the generic patch direction validated locally.

## Architectural boundary

The integration preserves the separation:

```text
AIP
  establishes evidence-qualified architecture knowledge

GT
  makes that knowledge inspectable and moldable

Agent
  chooses questions and reasons over returned knowledge

Developer
  controls permanent tooling and code changes
```

The integration does **not** make GT or the agent an architecture authority.

## Key validated properties

- AIP MCP negotiation and tool discovery from GT.
- Full MCP input-schema preservation through the local GT adapter.
- Structured `ArchitectureAnswer` consumption.
- Snapshot-bound evidence drill-down.
- Claim evidence and destination-resolution evidence kept distinct.
- `DECLARED` and `OBSERVED` evidence kept distinct.
- Agent-selected capability use across dependency, evidence, and drift questions.
- Multi-step `get_service_dependencies → get_evidence` chaining.
- Explicit stopping at the AIP contract boundary when qualification derivation is not exposed.
- Ephemeral GT micro-tools derived from AIP context.
- AIP snapshot/tool/claim lineage retained by generated micro-tools.
- Human-controlled promotion of useful lenses into permanent GT tooling.

## Scope relative to v0.5

This reference integration is **not a new v0.5 feature stream**.

AIP v0.5 remains focused on **Broader Architecture Discovery**. The GT work is an independent reference integration and external validation of the existing agent-facing contract. Findings should enter AIP release scope only when they reveal an AIP correctness or contract defect.

See also:

- [MCP documentation](../../mcp.md)
- [Product doctrine and strategic direction](../../product-doctrine-and-strategic-direction.md)
- [Roadmap](../../../ROADMAP.md)
