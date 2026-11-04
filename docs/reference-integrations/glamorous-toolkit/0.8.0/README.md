# AIP × Glamorous Toolkit — v0.8 contract reference experiment

**Status:** lightweight **pre-v0.9** experiment; specification draft only, not implemented or qualified  
**GT baseline:** official v1.1.657, bundled gt4llm v0.7.341  
**Initial AIP source:** public read-only Sokol111 MCP endpoint, `https://mcp.daip.io/mcp` (frozen pre-wave-1 evidence)

**Core question:** Under which conditions can autonomous services successfully cooperate, and how might a proposed change endanger those conditions? Test whether AIP's attributable Intent and qualified Current State/Assessment materially improve an architect's investigation beyond access to the same underlying service sources without AIP. The binding picture is the entry point, not the conclusion.

**Preferred Sokol111 change setting:** evaluate a proposal to reduce Catalog's outgoing-event retention costs (candidate target: 24 hours). Investigate which autonomous participants rely on related event flows and what conditions enable their cooperation. **Do not tell investigators the expected TTL failure or preselect a consumer.** The five-day TTL and possible pending-event expiry are researcher-only answer-key candidates, not an established incident or promise violation. Updating an existing MongoDB TTL index also requires `collMod`.

**Local promises:** declarations and their lifecycle belong to the autonomous service owners, usually in service or provider-owned `*-service-api` repositories. Consumer acceptance/reliance is independent and belongs to consumers. An optional minimal, service-local `architecture/promises.yaml` may carry candidate declarations if existing artifacts are insufficient. AIP/GT are read-only consumers, not authoritative authoring or approval systems. Existing v0.8 EventCatalog entries have **demo-assumed** confirmation; the hosted interface does not establish outbox behavioral promises.

**[Read the draft specification](specification.md)** — three increments: **neutral dataset-fitness GO/DEFER** → one open-ended GT/Lepiter investigation → parity-controlled evaluation. Proceed when AIP can qualify relevant source-grounded distributed relationships, without pre-requiring a demonstrated advantage over source-only tools. Without owner-confirmed promises, E2 remains untested; E1 can still proceed.

**Evidence discipline:** freeze the **hosted package ID, complete snapshot ID and capture time from an actual AIP response**, plus source revisions and the mappings/catalog/rules used for qualification. Keep the C1 snapshot's original scope and limitations; distinguish confirmed promises, candidates, inferred conditions, assessed relationships and unknowns. No invented live promise feed, end-to-end guarantee, or silent mixing of recorded after-wave-1 evidence with hosted C1.

**Evaluation:** keep the task card separate from a frozen answer key, and score **unanticipated independently verified insights** separately from expected answers. Give baselines equivalent repositories, declarations, raw broker captures, **authored consumer-group mappings, context membership, catalog sources and qualification rules**. Minimum controls: source-only agent, GT without AIP, GT with AIP. Compare with **direct agent + AIP before claiming GT itself adds value beyond direct AIP use**. Report **E1** (qualified cooperation knowledge) and **E2** (inspectable owner-attributable promises) separately, reserving product doctrine **H1/H2** for customer decision-value and owner-effort validation. AIP gets credit only for verified incremental value.

Historical [v0.4.2](../0.4.2/README.md) and [v0.5.1](../0.5.1/README.md) integrations remain unchanged. This reference experiment does not justify a new AIP release on its own.
