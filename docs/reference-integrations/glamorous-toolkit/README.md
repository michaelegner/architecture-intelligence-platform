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

## Architecture Explorer demo

The prepared Windows image is at `C:\opt\GlamorousToolkit\gt-1.1.590-architecture-explorer`. To start the demo:

1. From this repository in WSL, start AIP and leave its demo stack running:

   ```bash
   examples/runtime-demo/mcp-demo.sh --serve
   ```

2. In **Windows PowerShell**, launch GT with the image and a model choice:

   ```powershell
   & 'C:\opt\GlamorousToolkit\gt-1.1.590-architecture-explorer\bin\GlamorousToolkit-cli.exe' --interactive 'C:\opt\GlamorousToolkit\gt-1.1.590-architecture-explorer\GlamorousToolkit.image' eval --no-quit 'GtAipArchitectureExplorer openDemoWithModel: #luna'
   ```

   Use `#sol` instead of `#luna` for `gpt-5.6-sol`; `#luna` selects `gpt-6-luna`. Replace the entire expression after `eval --no-quit` when switching models: use `GtAipArchitectureExplorer openDemoWithModel: #sol`, without an extra `openDemo` before it. The parameterless `openDemo` remains an alias for `#luna`. Keep this process running for the demo. It opens a GT chat titled `a GtLChat (Chat)`. **Do not double-click `bin\GlamorousToolkit.exe`**: without the image and `openDemoWithModel:` arguments, it can leave a process running with only a tiny helper window and no usable chat.

The prepared image already has the launcher installed. If using a fresh PoC 4 image instead, evaluate the [Architecture Explorer installer](architecture-explorer-install.st) once in a setup Playground before running the PowerShell command. To apply updated standing instructions in an already-open GT, paste and evaluate the installer in a setup Playground, then evaluate `GtAipArchitectureExplorer openDemo` to open a new chat. The launcher keeps the MCP endpoint, demo service/window, and agent instructions out of the visible interaction; it does not change AIP.

For the video, ask a natural opening question such as “Which OrderService dependencies have incomplete evidence, and what should we inspect next?” The standing instruction now asks the agent to investigate with AIP first and create one `GtAipEphemeralMicroTool` from the returned claims after that first successful investigation. If AIP fails or yields no relevant claims, it should report that instead of manufacturing a tool. Verify that the trace shows an AIP call before `smalltalkCodeEvaluation`, then inspect the tool's Results and AIP provenance views. Later questions can reuse the same chat and context; permanent promotion remains a developer decision.

The chat answer uses headings and bullets, not Markdown pipe tables. Open the ephemeral micro-tool's **Results** view for the compact follow-up lens:

| Dependency | AIP qualification | Follow-up question |
|---|---|---|
| `unused-q` | `NOT_OBSERVED_IN_WINDOW` | Which service consumes this queue? |
| `payment-q` | `NOT_OBSERVED_IN_WINDOW` | Does a longer observation window show traffic on this queue? |
| `LegacyPricingService` | `OBSERVED_ONLY` | What declarations apply to this observed call? |

The rows illustrate the requested layout across GT investigations. They must appear only when AIP returns those exact dependency and qualification pairs. In the seeded runtime demo, `payment-q` is `CONFIRMED`; its qualification must remain `CONFIRMED` if included. The separate **AIP details** view retains each row's claim ID, complete claim and resolution evidence references, snapshot ID, applicable limitations, resolved evidence records in their respective roles, and missing references. Select a detail row in GT to inspect its full dictionary values. The agent resolves represented rows' evidence references through `get_evidence` at the originating snapshot before creating the tool. The **AIP provenance** view retains the overall snapshot, source tools, and source claim IDs. Any investigation priority in the chat is explicitly the agent's suggestion. If the answer interprets detailed evidence, it uses those same-snapshot records before answering. The chat's **Create page from Markdown** action copies the answer into a Lepiter text snippet, where pipe-table markup remains plain text in this GT version. Existing chats keep their original instructions.


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
