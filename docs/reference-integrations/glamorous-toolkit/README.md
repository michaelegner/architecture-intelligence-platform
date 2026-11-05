# AIP × Glamorous Toolkit reference integrations

The versions below name the **AIP architecture-knowledge contract/release**, not the Glamorous Toolkit application version. The historical and current integrations are maintained separately.

| AIP version | GT baseline | Integration |
|---|---|---|
| [0.4.2](0.4.2/README.md) | GT 1.1.590, local gt4llm compatibility adapter | Validated PoCs 1–4: runtime objects, provenance, agent-selected MCP tools and bounded ephemeral micro-tools. The original documentation and installer are retained as historical evidence. |
| [0.5.1](0.5.1/README.md) | Clean official GT 1.1.601 with gt4llm v0.7.304 | Quarkus Super Heroes integration: migrate the validated patterns, use upstream `mcpClient llmFunctionTools`, preserve operation/deployment/messaging distinctions. Agentic migration qualification is recorded separately from the earlier PoC PASS results. |
| [0.8.0](0.8.0/README.md) | Clean official GT 1.1.657 with gt4llm v0.7.341 (planned) | **Pre-v0.9 reference experiment (draft):** inspect **fictional local promises from Catalog, Image and Product Query**, plus a separate external marketplace contract, against a new consumer's **15-minute listing-withdrawal business requirement**. Explore independently scoped offers (including Product Query's separate event acceptance and read promise) using GT + AIP, then **derive whether any new consumer commitment is justified**. Score evidence-supported decision changes beyond simply finding ADRs; partial v0.8 coverage is acceptable. **Sample-system demo**, not real owner confirmation or a finished implementation. |

The upstream [gt4llm PR #12](https://github.com/feenkcom/gt4llm/pull/12) incorporated the generic client fix identified by the [0.4.2 interoperability work](0.4.2/gt4llm-mcp-interoperability.md). Do not load that historical local adapter into the current GT image.

See [AIP MCP](../../mcp.md) and the [published Quarkus demonstration](../../../examples/quarkus-super-heroes-demo/README.md).
