# AIP × Glamorous Toolkit — v0.5.1 Quarkus integration

**AIP release:** v0.5.1 (public schema `"0.5"`)  
**GT baseline:** fresh official [GT 1.1.601](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.601), bundling gt4llm v0.7.304  
**Status:** runbook and two-class GT source export supplied; end-to-end results must be recorded after execution. Historical v0.4.2 PoC PASS results do not qualify the v0.5.1 integration.

## Deliverables

- [Step-by-step runbook, v1.8](AIP_GT_Quarkus_Demo_Runbook_v1_8.md): start with official GT 1.1.601, replay AIP v0.5.1, verify MCP and snapshot-bound evidence, inspect the Quarkus object, and optionally open a GT chat.
- [AIP-GToolkit-Quarkus.st](AIP-GToolkit-Quarkus.st): user-exported Smalltalk package containing `GtAipMcpClient`, `GtAipArchitectureAnswer` and four Inspector views. This is an alternative to entering the two classes method-by-method in runbook §6; inspect before loading and do not overwrite bundled gt4llm classes.

Both files are reference integration artifacts, not a claim of an independently re-executed acceptance gate. The archived [0.4.2 PoCs](../0.4.2/README.md) remain separate.

## Starting point

The reproducible evidence source is the published [Quarkus Super Heroes replay](../../../../examples/quarkus-super-heroes-demo/README.md) and its [Q1–Q8 walkthrough](../../../../examples/quarkus-super-heroes-demo/walkthrough.md). It starts no live Quarkus system. AIP exposes exactly three read-only [MCP tools](../../../mcp.md) at `http://127.0.0.1:8000/mcp`.

Query `service:rest-fights` with environment `quarkus-i5` and window `2026-09-25T13:06:47Z` to `2026-09-25T13:06:54Z`. The clean replay contains seven operation-level HTTP claims (three confirmed, four not observed in this window), a configured `DEPLOYED_AS`, and an operator-authored AsyncAPI `PUBLISHES_TO` Topic `fights` claim with unresolved subscription identity. Preserve the complete answer, limitations, both evidence-ref roles and its returned snapshot.

## Implementation approach

Use the official GT 1.1.601 image and bundled upstream gt4llm (including feenkcom/gt4llm PR #12). The two AIP-specific classes are provided in the source export and documented method-by-method in the runbook. Retain each full `ArchitectureAnswer`, claim evidence and destination-resolution evidence in separate roles, and resolve references using the answer's own snapshot.

The agent chat is optional and uses upstream `mcpClient llmFunctionTools` together with GT's existing object-exploration tools. No historical `GtAipMcpStructuredFunctionTool` adapter, bulk-import of the GT 1.1.590 image or ephemeral micro-tool migration is needed.

## Verification gates

- **MCP:** initialize and discover the three tools with full nested input schemas and `structuredContent`.
- **Object/Inspectors:** preserve all nine claims (seven HTTP / one messaging / one deployment), `PARTIAL` and `UNRESOLVED_IDENTITY`; four working views.
- **Evidence:** resolve at the originating snapshot with no missing refs; do not infer absent activity, deployment identity or consumer identity from names.
- **Optional agent:** demonstrate the chat/object workflow separately if a model provider is configured.

Record observed v0.5.1 gate results only after running them in the target GT image.
