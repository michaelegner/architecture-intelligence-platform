# Participant corpus

This list is for the operator. It is the complete list of what a participant receives. The participant receives the members, not this list. Set up each comparison condition from this list only. Do not give the participant this repository, the specification, any README, the researcher key, the `aip/` captures, or unrestricted repository or web access.

## Common corpus: identical in all four conditions

| Member | Source | Kind |
|---|---|---|
| Task | [`task.md`](task.md) | task |
| `CAT-OFFER-01` | [`../../demo-promises/catalog/product-change-events.yaml`](../../demo-promises/catalog/product-change-events.yaml) | fictional Promise Contract |
| `IMG-OFFER-01` | [`../../demo-promises/image/image-promotion-information.yaml`](../../demo-promises/image/image-promotion-information.yaml) | fictional Promise Contract |
| `PQ-ACCEPT-01` | [`../../demo-promises/product-query/catalog-change-acceptance.yaml`](../../demo-promises/product-query/catalog-change-acceptance.yaml) | fictional Promise Contract |
| `PQ-READ-01` | [`../../demo-promises/product-query/product-reads.yaml`](../../demo-promises/product-query/product-reads.yaml) | fictional Promise Contract |
| `DEMO-CONTRACT-001` | [`../../demo-promises/marketplace-withdrawal-contract.md`](../../demo-promises/marketplace-withdrawal-contract.md) | fictional external marketplace contract |
| Sokol111 repositories | The 16 repositories at the commits in the [v0.7.2 freeze table](../../../../../specifications/0.7.2/i2-evidence/sokol111/freeze.md), as local clones without other refs or remotes | real source |

The source set that hosted AIP ingests comes from the [I1 evidence package](../../../../../specifications/0.8.0/i1-evidence/README.md), exported from tag `v0.8.0`. Its members differ in kind:

| Member | Kind |
|---|---|
| `c1/kafka-consumer-state.json` | **runtime capture**: the consumer groups on the local broker at T `2026-10-21T17:53:57Z` |
| `declarations/sokol111-local/` | **authored**: the Services, the Topics they produce, and their pre-wave-1 producers |
| `mapping/sokol111-local/kafka-service-mapping.json` | **authored**: consumer group → Service, from the environment configuration |
| `upstream/platform-overview.md`, `upstream/product-update-flow.md` | **real upstream documents**: the Sokol111 architecture documents at workspace commit `f6b4c1c` |
| `catalog/`, `event-topic-lookup.json` | **generated** from `upstream/`: a demo EventCatalog with illustrative owners. Its entries count as confirmed promises only by a disclosed demonstration assumption. It is not an owner-confirmed Promise Contract |

## Additions for the AIP conditions only

| Condition | Addition |
|---|---|
| Coding agent, no AIP | none |
| GT, no AIP | GT with the same corpus; no AIP access |
| GT + AIP | read-only access to `https://mcp.daip.io/mcp`, serving snapshot `aip:snapshot:v1:7f171aea2d3c5070e6be3dd9c6b53a234ad75934be5724681b95cd3e1705c413` |
| Coding agent + AIP | the same read-only access as GT + AIP |

**Scope of AIP access.** The hosted instance serves only the frozen v0.8 I1 package. No technical restriction limits which read-only tool or query a participant uses. To keep the AIP evidence inside the frozen scope, the operator:

- re-runs the frozen `query` request before the session and compares it with the [freeze record](../README.md);
- records every AIP request and answer of the session;
- treats any answer that names a snapshot other than the frozen one as invalid for scoring.

This is a procedural limit, not a technical one. Report it as a limitation.

## Never in the corpus

- `../aip/`, `../researcher-key.md` and `../README.md`;
- the GT 0.8.0 `specification.md` and all READMEs in this integration;
- the `sokol111-kafka` declarations and mapping, and all v0.8 i2/i3 material (post-wave-1 or target-broker state);
- any other repository revision, branch or web page.
