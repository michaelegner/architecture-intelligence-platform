# AIP × Glamorous Toolkit — v0.8 contract reference experiment

**Status:** lightweight **pre-v0.9** experiment; specification draft only, not implemented or qualified  
**GT baseline:** official v1.1.657, bundled gt4llm v0.7.341  
**Initial AIP source:** public read-only Sokol111 MCP endpoint, `https://mcp.daip.io/mcp` (frozen pre-wave-1 evidence)

**Core question:** Under which conditions can autonomous services successfully cooperate, and how might a proposed change endanger those conditions? Test whether AIP's attributable Intent and qualified Current State/Assessment materially improve an architect's investigation beyond access to the same underlying service sources without AIP. The binding picture is the entry point, not the conclusion.

**Preferred Sokol111 scenario:** propose reducing shared outbox record retention from five days to 24 hours. Investigate the Catalog → outbox → broker → Product Query cooperation and whether pending records could expire before successful publication. This is a **hypothetical change and source-supported risk**, not a verified failure or confirmed promise violation; the existing five-day TTL already limits recovery.

**Local promises:** declarations and their lifecycle belong to the autonomous service owners, usually in service or provider-owned `*-service-api` repositories. Consumer acceptance/reliance is independent and belongs to consumers. An optional minimal, service-local `architecture/promises.yaml` may carry candidate declarations if existing artifacts are insufficient. AIP/GT are read-only consumers, not authoritative authoring or approval systems. Existing v0.8 EventCatalog entries have **demo-assumed** confirmation; the hosted interface does not establish outbox behavioral promises.

**[Read the draft specification](specification.md)** — three increments: freeze scenario/evidence/baselines → one situated GT/Lepiter investigation → compare and publish findings.

**Evidence discipline:** retain the hosted C1 snapshot's original scope and limitations; pin revisions for independent Sokol111 code/config evidence; distinguish confirmed promises, candidate declarations, inferred cooperation conditions, assessed relationships, and unresolved assumptions. No invented live promise feed, inferred end-to-end guarantee, or silent mixing of recorded after-wave-1 evidence with hosted C1.

**Evaluation:** freeze answer keys and a scoring rubric before building the views. Give source-only agents and GT baselines equivalent access to the underlying repositories and declarations, and measure verified change-relevant conditions/risks separately from interesting questions. Include direct AIP/agent access and record unsupported claims, missed effects, effort and negative/inconclusive outcomes. AIP gets credit only for incremental value beyond those baselines.

Historical [v0.4.2](../0.4.2/README.md) and [v0.5.1](../0.5.1/README.md) integrations remain unchanged. This reference experiment does not justify a new AIP release on its own.
