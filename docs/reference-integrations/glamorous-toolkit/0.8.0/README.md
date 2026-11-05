# AIP × Glamorous Toolkit — v0.8 contract reference experiment

**Status:** lightweight **pre-v0.9** experiment; Draft 0.9 specification only, not implemented or qualified  
**GT baseline:** official v1.1.657, bundled gt4llm v0.7.341  
**Initial AIP source:** public read-only Sokol111 MCP endpoint, `https://mcp.daip.io/mcp` (frozen pre-wave-1 C1 evidence)

**Business scenario:** An e-commerce merchant wants to sell products on an additional marketplace without separately maintaining the catalog. A **new, proposed Marketplace Connector** would consume existing platform capabilities; it is **not** an observed Sokol111 service or an already-established AIP binding.

**Core question:** What must a new consumer understand, obtain and independently promise before it can safely cooperate with existing autonomous participants? Can AIP + GT make that decision more evidence-grounded than source access alone?

**Investigation and evaluation follow the questions in [Daniel Kocot's *Integration Beyond the Interface*](https://adorsys.com/en/techradar/integration-beyond-the-interface%20/):** Why does the capability exist and for whom? Can the consumer discover and understand it? Is its proposed use permitted? Where do provider, intermediary and consumer responsibilities begin and end? How can the cooperation evolve safely? Use these to assess a **proceed / conditional proceed / defer** onboarding decision, not connector implementation.

**[Read the specification](specification.md)** — three increments: freeze business task and evidence → one open-ended GT/Lepiter investigation → source-parity comparison and findings. The old outbox-retention proposal is **no longer the primary experiment**; outbox behavior can be a relevant condition if discovered.

**Promise discipline:** Service/API owners retain authority for local promises; a prospective consumer's acceptance and downstream commitments are independent. Code/config/catalog entries may be candidates or behavior evidence, not owner confirmation. Sokol111 v0.8's `sends`/`receives` entries have **demo-assumed confirmation**, not actual owner sign-off. E1 tests qualified cooperation knowledge; E2 tests inspectable real promises **only if available**.

**Partial AIP qualification is not a blocker:** Existing C1 results need not establish marketplace permissions, image lifecycle or all event/recovery semantics. Preserve their snapshot/scope limits and use separately pinned source evidence for broader investigation; report unknowns and coverage gaps without inventing AIP claims. The proposed connector never becomes observed Current State. A fair baseline receives the same underlying source material, including raw captures, authored mappings, context membership, catalog inputs and rules.

**Evaluation:** Freeze an unspoiled participant task and independent key; score the article-derived consumer questions, justified decisions, unsupported claims, effort, and **unexpected independently verified discoveries** separately from expected findings. Compare source-only agent, GT without AIP, and GT+AIP; include direct agent+AIP before claiming GT adds incremental value over AIP alone. Neither E1 nor E2 validates product doctrine H1/H2 without customers.

Historical [v0.4.2](../0.4.2/README.md) and [v0.5.1](../0.5.1/README.md) remain unchanged. No marketplace integration, GT implementation, owner-confirmed promise, or evidence of product value is claimed.
