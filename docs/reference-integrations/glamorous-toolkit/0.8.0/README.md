# AIP × Glamorous Toolkit — v0.8 contract reference experiment

**Status:** lightweight **pre-v0.9** experiment; specification draft only, not implemented or qualified  
**GT baseline:** official v1.1.657, bundled gt4llm v0.7.341  
**Initial AIP source:** public read-only Sokol111 MCP endpoint, `https://mcp.daip.io/mcp` (frozen pre-wave-1 evidence)

**Core question:** Under which conditions can autonomous services successfully cooperate, and how might a proposed change endanger those conditions? Test whether AIP's attributable Intent and qualified Current State/Assessment materially improve an architect's investigation beyond access to the same underlying service sources without AIP. The binding picture is the entry point, not the conclusion.

**Preferred Sokol111 change setting:** evaluate a proposal to reduce Catalog's outgoing-event retention costs (candidate target: 24 hours). Investigate which autonomous participants rely on related event flows and what conditions enable their cooperation. **Do not tell investigators the expected TTL failure or preselect a consumer.** The five-day TTL and possible pending-event expiry are researcher-only answer-key candidates, not an established incident or promise violation. Updating an existing MongoDB TTL index also requires `collMod`.

**Local promises:** declarations and their lifecycle belong to the autonomous service owners, usually in service or provider-owned `*-service-api` repositories. Consumer acceptance/reliance is independent and belongs to consumers. An optional minimal, service-local `architecture/promises.yaml` may carry candidate declarations if existing artifacts are insufficient. AIP/GT are read-only consumers, not authoritative authoring or approval systems. Existing v0.8 EventCatalog entries have **demo-assumed** confirmation; the hosted interface does not establish outbox behavioral promises.

**[Read the draft specification](specification.md)** — three increments: **evidence-fitness GO/DEFER** → one open-ended GT/Lepiter investigation → parity-controlled evaluation. Without attributable promises, the specific promise-value hypothesis cannot be positively tested; do not manufacture service-owner confirmation.

**Evidence discipline:** retain the hosted C1 snapshot's original scope and limitations; pin revisions for independent Sokol111 code/config evidence; distinguish confirmed promises, candidate declarations, inferred cooperation conditions, assessed relationships, and unresolved assumptions. No invented live promise feed, inferred end-to-end guarantee, or silent mixing of recorded after-wave-1 evidence with hosted C1.

**Evaluation:** keep the task card separate from a frozen answer key. Provide baselines with equivalent repositories, declarations **and raw broker captures**. Minimum controls: source-only agent, GT without AIP, GT with AIP; direct AIP/agent is useful if feasible. Measure independently supported cooperation conditions, verified risks separately from questions, missed participants, false claims and effort. Report H1 (qualified AIP relationships) and H2 (genuinely attributable promises) separately. AIP gets credit only for verified incremental value.

Historical [v0.4.2](../0.4.2/README.md) and [v0.5.1](../0.5.1/README.md) integrations remain unchanged. This reference experiment does not justify a new AIP release on its own.
