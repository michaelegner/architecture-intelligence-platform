# AIP × Glamorous Toolkit — v0.8 contract reference experiment

**Status:** lightweight **pre-v0.9** experiment; Draft 0.12, demonstration only, GT implementation/evaluation pending  
**GT baseline:** official v1.1.657, bundled gt4llm v0.7.341  
**AIP source:** public read-only Sokol111 MCP `https://mcp.daip.io/mcp` (frozen pre-wave-1 C1 evidence)

**Sokol111 is a sample e-commerce codebase, not a production customer.** We do **not** need approval from its real maintainers or upstream Sokol111 code changes to demonstrate AIP's promise-inspection concepts. Fictional service roles make explicit demo decisions, clearly labeled as `DEMO_ASSUMED_CONFIRMED`; the proposed new consumer is `DEMO_PROPOSED`. These are **not genuine owner-confirmed promises or AIP status enums**.

**Scenario:** A merchant wants to reuse its shop catalog to maintain product listings on an additional marketplace. Most requirements—product details, prices, availability, images, updates—are similar. **One small difference:** a disabled or deleted shop product must be withdrawn from the marketplace **within 15 minutes**. That is a hypothetical merchant requirement, **not** a current Sokol111 guarantee or real marketplace policy. Orders, checkout and fulfillment are excluded. The Marketplace Connector does not yet exist as an observed binding.

**Promise-bearing ADRs:** The [demo ADRs](demo-promises/README.md) capture **why** modeled autonomous services offer capabilities, **what external behavior** they promise, **to whom**, and **under which conditions**. Two fictional provider offers (Catalog and Image) and one proposed consumer acceptance/merchant-facing commitment are provided. An **ADR is a decision record; the externally offered/accepted commitment inside it is the promise.** In a real organization, the corresponding team would own and approve its ADR; this reference overlay simulates that locality without misattribution.

**Central question:** Can an architect inspect these local offers and their limitations and determine what additional agreements or independently assumed responsibilities are necessary for the marketplace consumer's slightly stronger requirement?

**[Read the specification](specification.md)** — three increments: (1) prepare source-grounded demonstration ADRs and evidence, (2) one lightweight promise-first GT/Lepiter investigation, (3) fair comparison and findings. Incomplete AIP v0.8 qualification is **not a blocker**. GT may display the demo ADRs separately from v0.8 qualified broker evidence; never present the ADRs as native AIP-qualified behavioral Intent.

**Article lens:** Adapted from [Daniel Kocot, *Integration Beyond the Interface*](https://adorsys.com/en/techradar/integration-beyond-the-interface%20/): Why and for whom is each capability offered? What may the consumer rely on? Is use permitted? Who promises what independently? Can the commitments remain compatible as things change?

**Evaluation:** Compare source/ADR-only agent, GT without AIP, GT+AIP, and direct agent+AIP on the same ADRs and pinned raw evidence. Score correct promise scope/authority, missing or incompatible reliance, justified **proceed / conditional proceed / defer** decisions, unsupported assertions, unexpected independently substantiated insight and maintenance cost. **E1** is incremental AIP qualification; **E2** is fictional promise-navigation feasibility. Doctrine H1 (real decision value) / H2 (sustainable owner effort) still require real customers.

Historical [v0.4.2](../0.4.2/README.md) and [v0.5.1](../0.5.1/README.md) remain unchanged. No real owner approval, production marketplace connector, GT implementation, or measured product value is claimed.
