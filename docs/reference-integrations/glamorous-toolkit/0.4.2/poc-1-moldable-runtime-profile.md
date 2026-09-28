# PoC 1 — Moldable Exploration of Qualified Architecture State

**Result:** PASS

## Purpose

PoC 1 established the basic integration boundary between AIP and Glamorous Toolkit.

The question was:

> Can GT consume AIP architecture state, wrap it in domain objects, expose contextual micro-tools, and later consume the same knowledge over MCP without changing AIP semantics?

## Phase 1 — REST-backed runtime profile

The initial integration deliberately used AIP's REST runtime-profile endpoint before introducing MCP.

```text
GT
  ↓
AIP REST runtime profile
  ↓
GtAipRuntimeProfile
  ├── GtAipService
  ├── GtAipObservationContext
  └── GtAipDependency*
```

The seeded `OrderService` profile exposed four direct interactions:

| Target | Relation | Qualification |
|---|---|---|
| ProductService | CALLS | CONFIRMED |
| LegacyPricingService | CALLS | OBSERVED_ONLY |
| unused-q | SENDS | NOT_OBSERVED_IN_WINDOW |
| payment-q | SENDS | NOT_OBSERVED_IN_WINDOW |

GT micro-tools exposed views such as:

- Confirmed
- Observed only
- Not observed
- Messaging

This established the basic Moldable Development pattern:

```text
AIP-qualified state
        ↓
GT domain object
        ↓
small contextual micro-tools
```

## Agent over an existing GT object

The next step gave a GT agent a live `GtAipRuntimeProfile` object and only the restricted GT object-execution tool set.

The agent correctly answered questions such as:

- service name,
- environment,
- dependency count.

A boundary test then revealed an important issue: correct field retrieval alone did not prevent the agent from inventing a causal explanation for `OBSERVED_ONLY`.

After adding an explicit grounding contract, the agent correctly distinguished:

1. facts represented by the GT object,
2. interpretation over those facts,
3. provenance or qualification derivation not present in that object.

Key finding:

> A qualified projection is not enough to explain its own qualification.

## MCP interoperability

PoC 1.4 introduced GT ↔ AIP MCP interoperability.

Validated gates:

| Gate | Result |
|---|---|
| negotiated MCP session and discovery | PASS |
| AIP tool schemas visible in GT | PASS |
| raw structured `ArchitectureAnswer` | PASS |
| GT convenience mapping | LOSSY |
| snapshot-bound `get_evidence` | PASS |
| actual MCP message sequence | PASS |

The initial GT agent bridge failed because the current provider path expected the current GT function-tool model while `GtLMcpClient>>llmFunctionTools` still created the legacy `GtLlmFunctionTool`.

A local current-model adapter fixed both issues:

- preserve the full MCP `inputSchema`,
- preserve `structuredContent`.

That adapter was then exercised successfully by PoCs 2–4.

## Result

PoC 1 established:

```text
AIP establishes qualified architecture knowledge.
GT can wrap and inspect it.
Agents can reason over it.
The agent must stop where AIP provenance or derivation is unavailable.
```

See [gt4llm MCP interoperability](gt4llm-mcp-interoperability.md) for the client-side compatibility finding.
