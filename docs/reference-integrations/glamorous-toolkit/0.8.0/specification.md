# AIP × Glamorous Toolkit — v0.8 Contract Reference Experiment

**Status:** Draft 0.9 — specification only; not implemented or qualified  
**Date:** 2026-11-05  
**Experiment scope:** lightweight **pre-v0.9** investigation; does not define or qualify an AIP release  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 pre-wave-1 dataset

The `0.8.0/` directory names the **AIP contract consumed**, not a proposed new release. The existing hosted Sokol111 evidence is a starting point, not a complete answer to the scenario. Historical GT integrations remain unchanged.

## 1. Customer decision — introduce a new consumer

**Central question:** **What must a new consumer understand, obtain and independently promise before it can safely cooperate with existing autonomous services—and does AIP + GT make that decision better supported than the same source evidence without AIP?**

**Business scenario:** An e-commerce merchant wants to offer products from the existing shop on an external marketplace, without maintaining a separate product catalog. A new team proposes a **Marketplace Connector** that reuses existing platform capabilities. The connector and external marketplace are *proposed*, not existing Sokol111 services or observed AIP bindings. Do not pick a particular marketplace or fabricate its requirements.

**Participant-facing task (keep separate from the researcher key):**

> A merchant wants to publish products from their online shop to an additional marketplace and keep listings accurate as products change. A new team plans to reuse the platform's existing interfaces and events. As the architect, investigate whether and under which conditions this new consumer can cooperate with existing services. Identify what the new team can rely upon, what it must promise to its own users, what is not established, and what needs to be agreed or checked before proceeding. Make a justified **proceed / conditional proceed / defer** recommendation.

The participant should need only ordinary e-commerce familiarity. Provide a short orientation to the platform's role and the business goal, **not** a pre-drawn service dependency graph, an expected answer, or a list of Sokol111 internals.

### Investigation questions — derived from *Integration Beyond the Interface*

Use the article's **consumer journey and architectural responsibility** questions to structure **both the investigation and its evaluation**, rather than treating this as an event-stream integration exercise:

| Article question / decision lens | What the architect must investigate |
|---|---|
| **1. Why does the capability/interface exist, and for whom?** | Which existing business capability could serve the new channel? Which requirements, owning context, intended consumers and business semantics are evidenced, promised, candidate-only or unknown? |
| **2. Can a new consumer discover and understand it?** | Are suitable APIs, events and interaction patterns available? What do product updates, deletions, enablement, image handling and current-state reads actually mean? Can initial state, subsequent changes and recovery be supported—under stated conditions? |
| **3. Can this consumer legitimately use it?** | What tenant scope, authorization, delegated authority, intended purpose and execution constraints apply? Distinguish endpoint accessibility from permitted marketplace reuse; do not infer policy from connectivity or public RPCs. |
| **4. Where do product and operational responsibilities begin and end?** | What does each autonomous provider offer, what does the proposed consumer need and commit to accept, and what can it credibly promise its merchants? Identify intermediary guarantees, consumer-specific agreements and missing owner confirmation. |
| **5. How will cooperation survive change?** | Which relevant semantics, dependencies, compatibility expectations and operational conditions could change? What must be verified or coordinated before onboarding and later evolution? Consider recovery, freshness, ordering and deletion only to the extent the evidence and business requirement justify them. |

Source and framing: [Daniel Kocot, *Integration Beyond the Interface* (adorsys TechRadar, 5 Nov 2026)](https://adorsys.com/en/techradar/integration-beyond-the-interface%20/). These are experiment questions *adapted from* the article's themes, not purported verbatim questionnaire items. The article's measure of integration maturity is whether a new consumer can be introduced without repeatedly reconstructing responsibilities and dependencies.

**Decision outcome:** a bounded, evidence-linked account of what existing participants offer and what the proposed connector needs, a short list of unsupported assumptions/owner questions, and a justified integration-readiness recommendation. The investigation is **not** tasked with implementing the connector, designing a data lake, selecting marketplace technology, or proving end-to-end consistency.

### Experimental questions, independent of the product doctrine

- **E1 — Qualified cooperation knowledge:** does AIP's evidence-qualified view of *existing* autonomous bindings help discover relevant participants and conditions and reduce unsupported claims compared with source-only investigation?
- **E2 — Inspectable local promises:** *if genuine owner-attributable promises are available*, does contextual navigation of provider offers and independent consumer acceptances make relevant agreements and gaps clearer?

These are not the product doctrine's **H1 (customer decision value)** and **H2 (sustainable owner effort)**, which require target-customer validation. E2 can remain **untested** if owner-confirmed promises are not available; E1 and the exploratory GT workflow can still be investigated.

## 2. Investigation and evidence discipline

**Use existing AIP and Sokol111 capabilities first.** GT's bundled `GtLMcpClient` / `GtLMcpHttpTransport` can query AIP's read-only MCP; use `get_binding_picture` as a *qualified orientation to existing relations*, then inspect relevant source/configuration, API contracts and evidence. Source investigation may be broader than the existing AIP v0.8 query scope. Preserve the difference between qualified AIP claims and independent investigator interpretation.

**Source-grounded starting points, not an answer key:** Sokol111's [workspace overview](https://github.com/Sokol111/ecommerce-workspace) describes a multi-tenant e-commerce system; [Catalog](https://github.com/Sokol111/ecommerce-catalog-service) owns product writes and emits events; [Product Query](https://github.com/Sokol111/ecommerce-product-query-service) maintains a separate query projection; [Image](https://github.com/Sokol111/ecommerce-image-service) handles product images. The provider-owned `*-service-api` repositories contain contracts. Relevant possibilities include full-state product event semantics, separate image-promotion information, existing query endpoints, tenant propagation, and outbox/transport constraints. **These are researcher starting points to verify at pinned commits; do not preselect a traversal or present any behavior as an owner-confirmed promise.**

**Critical temporal boundary:** The Marketplace Connector is a *proposed* consumer: it has no observed topic attachment, no demonstrated authorization, and no owner-confirmed acceptance promise. Never invent a new binding row, treat a proposal as Current State or claim its future conformance. AIP can qualify existing bindings among present participants; an architect can use those premises to assess *possible future* cooperation, with uncertainty explicit.

**Local promises and conditions:** Provider offers (+), consumer acceptance/use (−), platform/intermediary capabilities and the new connector's prospective outward commitments are **distinct**. Code, Protobuf, config, an event catalog or a sample integration may supply **candidate declarations and behavior**, never real owner confirmation by themselves. AIP's v0.8 showcase treats catalog entries as confirmed only under an openly stated **demo assumption**. A consumer's need does not create a provider promise. Missing coverage is **unresolved**, not proof that no one promised or authorized an action. Locally owned promise declarations remain in service/API/team-controlled carriers; a GT view or AIP projection must not become the owner.

**Cooperation conditions are investigator-owned hypotheses**, not new authoritative AIP assertions. For each decision-relevant condition, record the affected capability/consumer journey, relevant independently established participants, local offer/acceptance if any, factual constraints, evidence provenance/scope, whether it is necessary or only conjectured, and the required owner/technical verification. A list of necessary conditions does not prove sufficient end-to-end correctness. In particular, broker attachment ≠ event processing/delivery; an available endpoint ≠ legitimate marketplace access; `ImageId` ≠ a promised usable image URL; present state ≠ historical completeness.

**Partial qualification is explicitly allowed.** The hosted Sokol111 v0.8 C1 binding picture establishes bounded broker attachments and demo-assumed `sends`/`receives`, not every application contract, identity, authorization rule, marketplace-specific promise, bootstrap guarantee or event-handling behavior. **This is not a blocker for this experiment.** Combine AIP-qualified premises with other pinned sources, label which question each source can and cannot answer, and log any AIP semantic/coverage gap as a result. Do not patch the AIP result, silently extend its snapshot, invent a positive assessment, or demand a new AIP tool/release as a prerequisite.

**Evidence freeze and parity:** Before the exploratory run, preserve the **hosted package ID, complete snapshot ID, capture time and exact AIP request/response scope** from the real endpoint; pin service/API/commons commit SHAs, raw broker captures, authored consumer-group mappings, context/boundary membership sources, EventCatalog and assumed-confirmation inputs, and applicable qualification rules. Supply the underlying sources to all baseline conditions. Keep recorded after-wave-1 captures separate from the hosted pre-wave-1 C1 evidence; any additional package needs its own identity and qualification. AIP projections may add deterministic qualification and provenance—not privileged access to undisclosed source facts.

**Evidence drill-down:** Resolve `binding-evidence:` refs through `get_binding_picture` in `mode: "evidence"` with the original snapshot, bounded context, environment and broker IDs; keep ref roles, 1–20-ref limits, unresolved refs and errors intact. Do not reinterpret `crossing` or `status` against an inferred context boundary, infer context membership from connectivity, or confuse a projection over existing services with the proposed consumer's future binding.

**GT remains small and exploratory:** implement one contextual Phlow/Lepiter investigation. An architect should be able to follow an available capability → an evidenced relationship → its local provider/consumer evidence or promise candidate → a missing condition or unexpected participant → a sharper decision or owner question. Navigation must remain open-ended; no hardcoded solution path, pre-highlighted Image dependency, fabricated promise feed, generalized graph browser or code mutations.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Business task, evidence fitness and controls** | Freeze the participant-facing marketplace task, researcher-only baseline/answer key and insight rubric; pin all source and hosted snapshot identities. Map the five article-derived questions to available evidence and its known limits. | **GO** when the case offers an intelligible consumer decision and at least one source-grounded autonomous relationship to examine. Partial AIP qualification, missing promises or unresolved authorization **do not block GO**. Record coverage gaps; no prior demonstration of AIP superiority is required. |
| **2 — One exploratory GT investigation** | Make the five questions navigable through existing AIP context plus independently sourced service/API/contract evidence; one small Phlow/Lepiter flow, no new AIP capability. | An e-commerce architect unfamiliar with Sokol111 can follow at least one evidence chain, distinguish what is promised/observed/assumed and form a justified question or integration decision. Unanswerable questions stay explicitly open. |
| **3 — Compare and publish** | Evaluate the same marketplace onboarding task across matched baselines, check findings independently, document false claims, unexpected insights, decision quality and owner/engineering effort. | A reproducible positive, negative or inconclusive assessment for E1 and (if promise coverage permits) E2, including whether GT adds value over direct AIP; no product-value claim from the public demonstration alone. |

## 4. Evaluation — follow the consumer journey

**Separate task from key.** Give investigators only the business brief and reasonable platform access. Freeze an independent **researcher key** from pinned Sokol111 sources, AIP scope and known unknowns before developing GT views. Do not supply a catalog of expected services, hidden obstacles or preferred solutions inside the task or UI. Unexpected findings must be independently verified and recorded separately from anticipated key items; assess how they change the question or integration recommendation.

Score each investigation against the **same five article-derived questions from `1**, not against a preordained implementation:

| Evaluation question | Decision-relevant evidence of progress |
|---|---|
| **1. Why this capability?** | Finds the suitable existing owners/interfaces and distinguishes published purpose/semantics from an inference about intended consumers. |
| **2. Can it be understood?** | Establishes what APIs/events actually allow, what a new consumer still needs to learn, and which initial-sync/updates/recovery conditions require confirmation. |
| **3. May it be used?** | Separates technical reachability from tenant-scoped authorization, external-use permissions and approval gaps; avoids invented security guarantees. |
| **4. Who promises what?** | Separates locally attributable provider offers, prospective consumer acceptance and downstream commitments from candidate declarations and unpromised reliance. |
| **5. Can it change safely?** | Identifies consequential existing dependents, evolution constraints and verification/coordination required to onboard the consumer without unsupported assurances. |

**Evaluation outcome, not completeness theater:** Count evidenced, decision-changing cooperation conditions and owner questions, missed relevant dependencies, false claims, inappropriate promise/qualification upgrades, and **unanticipated independently verified discoveries** versus expected key findings. Record investigation effort and new consumer/owner maintenance burden. A justified **conditional proceed** or **defer** with specific missing evidence can outperform an unjustified **proceed**. An unanswered governance question is not an AIP failure unless the tool misleadingly claims it answered it.

**Fair comparison with identical underlying facts:**

| Condition | Purpose |
|---|---|
| Coding agent + pinned source/config/contracts/raw captures, **without AIP** | Whether ordinary engineering analysis already supports the consumer decision |
| GT + the same sources, **without AIP** | Whether interactive exploration itself helps |
| GT + the same sources **with AIP** | Incremental value of AIP's qualified existing bindings and evidence |
| Coding agent + those same sources **with direct AIP access** | Needed **before claiming GT adds value beyond direct AIP**; if omitted, GT-specific benefit is undetermined |

An optional evidence-linked report is a low-cost cross-check. Keep task, sources, model/assistance, and investigation budget as comparable as feasible. Qualifying evidence is a potential AIP contribution; withholding the raw inputs that produced that evidence is not.

**Interpretation gates:** E1 can succeed, fail or remain inconclusive even if AIP covers only part of the journey. E2 is **untested** without genuinely owner-attributable promises; demonstrative `sends`/`receives`, consumer needs or agent-authored proposals do not count as confirmation. A GT-only navigation advantage is not proof of AIP's product value. AIP's semantic gaps, unresolved owner questions and a finding that a direct agent suffices are valid outcomes. Product doctrine H1 (decision value) and H2 (sustainable owner effort) still require real multi-team customer validation.

## 5. Minimal deliverables

- This `specification.md` and aligned `README.md` / integration index.
- After implementation only: small GT source export and one executable Lepiter investigation.
- A compact frozen task/key and evidence manifest; after evaluation, a brief comparison/outcome report with provenance and costs.

Work in `docs/reference-integrations/glamorous-toolkit/0.8.0/`. Retain the historical `0.4.2/` and `0.5.1/` integrations unchanged.

## 6. Non-goals and release boundary

No actual marketplace integration, simulated authoritative promise, central approval/registry workflow, cross-system business-state verification, generic event/marketplace adapter, inferred authorization, product-ownership claim from a topic, GT graph platform, agent-driven code mutation or new AIP tool simply to make the experiment look complete. AIP supports qualified architectural premises; the architect and contextual tooling interpret and decide.

This is a **reference experiment**, not proof of production readiness, improved consumer onboarding across organizations or the doctrine's H1/H2. If v0.8 evidence cannot answer a question, show the limit and continue with the available independently grounded context. Only demonstrated AIP-side semantic/interoperability need justifies considering a future release.

## References

- [Integration Beyond the Interface — Daniel Kocot, adorsys TechRadar](https://adorsys.com/en/techradar/integration-beyond-the-interface%20/)
- [AIP product doctrine](../../../product-doctrine-and-strategic-direction.md)
- [v0.9 roadmap evaluation requirements](../../../../ROADMAP.md)
- [Sokol111 workspace and architecture](https://github.com/Sokol111/ecommerce-workspace)
- [Accepted Sokol111 v0.8 demonstration and hosted C1 limits](../../../specifications/evaluation/sokol111-v08-demo.md)
- [Hosted Sokol111 walkthrough](../../../../examples/sokol111-demo/TRY_IT_HOSTED.md)
- [v0.8 binding-picture request schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-request.schema.json)
- [v0.8 binding-picture answer schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-answer.schema.json)
- [Historical GT reference integration](../0.5.1/README.md)
- [GT baseline release](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.657)
