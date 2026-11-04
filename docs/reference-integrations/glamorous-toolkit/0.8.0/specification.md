# AIP × Glamorous Toolkit — v0.8 Contract Reference Experiment

**Status:** Draft 0.6 — specification only; not implemented or qualified  
**Date:** 2026-11-04  
**Experiment scope:** lightweight **pre-v0.9** investigation; its results may inform a future AIP release, but do not define or qualify one  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 pre-wave-1 dataset

The `0.8.0/` directory identifies the **AIP contract consumed**. Historical GT integrations remain unchanged.

## 1. One architect question

**Can AIP-supported, promise-aware investigation help an architect identify the conditions necessary for successful cooperation across autonomous services, and determine how a proposed change may endanger those conditions—better than the same source access without AIP?**

**Hypothesis:** AIP's attributable local Intent, qualified Current State and Assessment, combined with independent contextual tools and source analysis, improve understanding of *why* distributed cooperation works, which conditions it relies upon, and what remains unresolved. The binding picture is the entry point, not the result. The investigation may establish necessary conditions, but must never infer a complete or sufficient end-to-end guarantee from a collection of local claims.

**Preferred Sokol111 change scenario — outbox retention:** Catalog persists product state and its corresponding event atomically using the shared `ecommerce-commons` outbox. That outbox currently has a MongoDB TTL index of five days on `createdAt` (including pending records), and a separate retry/confirmation flow. Propose reducing the retention setting to **24 hours**. Investigate whether a prolonged broker failure could cause a pending event to expire before publication, leaving Product Query's projection stale. The proposed 24-hour setting is hypothetical; MongoDB TTL removal is asynchronous; the existing five-day setting already limits recovery. No failure or promise violation is asserted without independent verification.

Sources to pin before the experiment: [Catalog write and outbox transaction](https://github.com/Sokol111/ecommerce-catalog-service/blob/master/internal/application/product/update_product.go), [outbox TTL index](https://github.com/Sokol111/ecommerce-commons/blob/master/pkg/kafka/outbox/schema.go), [retry repository](https://github.com/Sokol111/ecommerce-commons/blob/master/pkg/kafka/outbox/repository.go), [sender and confirmation](https://github.com/Sokol111/ecommerce-commons/tree/master/pkg/kafka/outbox), and [Product Query's event projection](https://github.com/Sokol111/ecommerce-product-query-service/blob/master/AGENTS.md). Freeze actual commit revisions before evaluation; these links merely identify starting files.

**Investigation target:** trace the cooperation Catalog → outbox → broker → Product Query (and relevant other consumers if independently established). Distinguish the provider's offered behavior, consumers' own acceptance/reliance, intermediary capabilities, operational constraints and assumptions nobody explicitly promised. Ask what conditions make progress possible, how the proposed change affects them, and which evidence or owner decisions are still needed.

**What counts as an outcome:** (a) independently supported, decision-relevant conditions and risks; (b) explicitly unresolved assumptions or gaps that change the verification/coordination plan; (c) proposed checks or decisions traceable to those findings. A merely interesting question, added node, attractive visualization or generic outbox explanation does **not** count as a verified risk. New-to-investigator questions are recorded separately from validated findings.

**Scope discipline:** the hosted pre-wave-1 C1 Sokol111 dataset establishes only its declared/observed broker attachments and bounded assessments. Its v0.8 EventCatalog covers `sends`/`receives`, **not** outbox durability, TTL or end-to-end delivery promises. These behavioral facts come from separate pinned source/configuration and, where possible, tests. AIP must not receive credit for them unless it contributes qualified knowledge unavailable from the same sources alone. The recorded after-wave-1 evidence is not hosted and is not required for this non-migration scenario.

The workflow is one bounded, agent-assisted architect investigation:
1. **Orient:** start from the proposed outbox change, discover which established bindings and autonomous participants may be relevant.
2. **Explain cooperation:** inspect locally attributable provider/consumer promises and independently supported constraints, then build a *provisional* map of necessary conditions and unknowns.
3. **Challenge with change:** assess which conditions the retention change may threaten, inspect counter-evidence or alternatives, and define a justified verification or owner-coordination plan.

Do not re-run prior broker-migration agent failures, manufacture promises to make the scenario work, or build a general-purpose architecture browser.

## 2. Approach and evidence discipline

**Use the v0.8 contract first.** Connect through GT's bundled `GtLMcpClient` / `GtLMcpHttpTransport`; call existing read-only MCP tools and retain complete `structuredContent`, outcome, scope, limitations and snapshot. Begin with `get_binding_picture` to orient to independently established relationships; other AIP tools and repository/source tools supply distinct premises within their actual documented scopes. Do not invent an AIP outbox or behavioral-promise capability.

**Treat cooperation conditions as investigation results, not new canonical facts.** For each material condition, retain: (i) the specific cooperation/outcome at issue; (ii) relevant participants and binding; (iii) locally offered provider promise or candidate and separately stated consumer acceptance/reliance, if any; (iv) operational/intermediary constraints and preconditions; (v) supporting evidence and its scope; (vi) how the proposed change affects it; (vii) unresolved assumptions, required checks and possible mitigations. Label each item as `confirmed promise`, `candidate declaration`, `demo-assumed promise`, `observed/configured behavior`, `hypothesized condition`, or `unknown` as appropriate. This is an **investigator-owned working record**, not an AIP status enum or proof that the enumerated conditions are jointly sufficient.

**Promise Theory lens.** Promises are autonomous, local commitments: a provider's offer and a consumer's acceptance/use are independent; a technical dependency does not imply either. Service-owned or interface-owned declarations may be captured from code, contracts, catalogs or other carriers, but code alone is not an authoritative promise. Record who actually confirmed a commitment; keep missing confirmation, declined commitments, and unpromised reliance explicit. The outbox library is a local implementation mechanism of a service, not automatically an independent promiser. Do not invent provider promises from consumer expectations or infer global correctness from local intentions.

**Preserve AIP's authority boundary.** AIP supplies evidence-qualified Current State, locally attributable Intent when available, and its own bounded Assessment; GT/agents own navigation, composite reasoning, hypotheses and proposed decisions. An observed attachment does not establish event handling, successful delivery, offsets, retries or a promise about delivery timing. Existing v0.8 `sends`/`receives` are showcase-assumed confirmed **by assumption**, not by real Sokol111 owners. Do not silently upgrade source-derived behavior into accepted service promises or relabel inferred cooperation conditions as AIP-confirmed.

**Where local promises live.** A promise's source of authority belongs to the autonomous promiser, not to AIP or GT. Reuse provider-owned `*-service-api` contracts for published event/interface meaning and service-owned repositories for behavioral promises; separately capture consumer-owned acceptance/usage promises in consumer repositories. A minimal versioned, service-local `architecture/promises.yaml` is an optional demonstration carrier only when existing artifacts cannot express a candidate. Record the source revision and actual confirmation (or its absence); a Git commit is not itself confirmation. `ecommerce-commons` describes an outbox *implementation mechanism*, not an automatically owner-confirmed external promise for every service that uses it. AIP may ingest or index declarations with provenance while remaining non-authoritative for authoring and lifecycle. Do not add a central registry as a prerequisite.

**Pin and separate sources.** Inventory the hosted pre-wave-1 C1 snapshot, service and commons repository revisions, and any tests/configuration used. Preserve each source's authority, locality, effective time, capture scope and limitations; identify proposed changes separately from observed/current behavior. If richer read-only data is essential, create a separately identified reproducible package rather than silently alter the hosted frozen dataset or blend before/after captures. Do not claim the public endpoint serves recorded post-migration evidence.

**Respect evidence drill-down.** Resolve v0.8 `binding-evidence:` refs using `get_binding_picture` in `mode: "evidence"` with the exact original snapshot, bounded context, environment and broker IDs; deduplicate/sort the supported 1–20 refs and retain evidence roles and errors. Candidate GT groupings are not authoritative Bounded Contexts. Never recompute AIP `crossing`/`status` from hypothesized boundaries or treat `NONE` relative to Catalog Management as a Store Provisioning classification.

**Keep implementation small.** Prefer basic Phlow inspectors, linked objects and one executable Lepiter investigation. A graph is optional only if it helps investigate a concrete condition. Use existing code/test infrastructure where possible; do not introduce Oracle/sessionless transactions, new distributed runtime services, customized GT images, AIP tools or a general promise registry for the showcase.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Freeze scenario, evidence and controls** | Pin the proposed 5-day → 24-hour retention change, relevant Sokol111 commits, hosted AIP snapshot and actual service/broker relationships. Record the cooperation conditions supported by each source and the unknowns; connect GT to AIP. **Freeze independent answer keys, change consequences to test and a scoring rubric before implementing the view.** | One repeatable change task, source-grounded decision premises, explicit non-promises, a GT→AIP query and fair baseline inputs. |
| **2 — One situated investigation** | Small GT/Lepiter flow: proposed change → AIP-established relevant bindings → independently sourced local promises/conditions → evidence and limitations → hypotheses and next checks. | An investigator can identify how the change might affect cooperation, distinguish risks from questions, and explain which participants/evidence are relevant without upgrading claims. |
| **3 — Evaluate and publish** | Compare with matched baseline tools, test the asserted risk where feasible using controlled means, reproduce in a clean GT image, and record engineering/owner effort. | Compact report of verified conditions/risks, independently checked unresolved questions, misses, unsupported claims, decisions and costs; outcome can be positive, negative or inconclusive. State any omitted comparison or unverified failure explicitly. |

Keep the three increments thin. Add only the smallest reproducible fixtures/tests required to assess the chosen scenario; do not create a production reliability feature as a prerequisite.

## 4. Fair evaluation

**Pre-register a task and source-grounded answer key before increment 2.** The key includes known service/broker relationships, an accurate statement of the outbox's existing five-day TTL and retry mechanism, the proposed 24-hour change, which actors' promises are actually confirmed or merely inferred, and the plausible failure mechanism with its limits. Pin source revisions and observation windows. Do not rewrite the answer key to reward findings GT happens to surface. Accept unanticipated findings only after independent review under the original rubric.

**Do not leak the answer through the test materials.** Supply the proposed change and business goal, not a walkthrough that names the expected failure. Any additional promise declarations must be source-grounded, independently prepared and available equally to the relevant baselines. A meticulously written new promise catalog must not be created solely to tell the AIP condition the answer.

Compare the same task with the same source repositories and change description, recording actual tool access:

| Condition | What it tests |
|---|---|
| Existing source/documentation + simple evidence-linked report | Whether the problem is already clear without contextual tooling |
| Coding agent + source repositories **without AIP** | Whether normal cross-repository source analysis is sufficient (critical baseline) |
| GT + identical sources **without AIP** | Whether the contextual interface itself adds value |
| GT + identical sources **with AIP** | The incremental value of AIP's qualified relationship/Intent/Assessment context in GT |
| Coding agent + source repositories **with AIP directly** | Whether GT contributes beyond the same AIP access in an ordinary agent workflow |

Assess (1) **correct identification of necessary cooperation conditions**, with their evidence and provenance; (2) **verified change-relevant risks**, separately from merely raised questions or unconfirmed hypotheses; (3) missed affected services, unjustified claims, decision/test quality and ability to state unknowns; (4) investigation time, navigation cost and ongoing promise/source maintenance. Never count inferred sufficient end-to-end guarantees as established. Compare unsupported claims and total human/agent effort, not just number of insights or clicks.

A test that reproduces pending-event expiration and downstream staleness would support the specific failure mechanism, not establish every production-outage outcome; MongoDB TTL timing and actual relay behavior remain relevant. If no test is run, report the risk as a source-supported hypothesis and the missing evidence. Record changes in access, model/agent settings and assistance. A small demonstration carries no statistical inference and cannot by itself establish improved **collective** human–AI situational awareness or customer value.

**Decision gate:** if source-only agents uncover the same conditions at comparable cost, report no demonstrated AIP advantage; if AIP v0.8 cannot express the relevant behavioral promises, report that semantic gap rather than compensating by attributing adjacent tools' findings to AIP. Only independently supported improvement in decision quality or efficiency, net of integration and owner burden, motivates subsequent AIP work. As specified in the roadmap, a v0.9 release requires material AIP-side work rather than an integration alone.

## 5. Small deliverables

- `specification.md` — this draft and its three-step plan.
- `README.md` — scoped setup, baseline and status.
- GT source export + one executable Lepiter story **after implementation**.
- Compact evidence/answer-key and evaluation/reproduction report **when available**.

Work under `docs/reference-integrations/glamorous-toolkit/0.8.0/`; leave `0.4.2/` and `0.5.1/` unchanged.

## 6. Non-goals and release boundary

No re-running old broker-migration failures, invented promise confirmations, automatic extraction of authoritative Intent from code, inference that local promises jointly guarantee end-to-end success, attribution of source-only discoveries to AIP, artificial proof of boundary ownership from graph clusters, authoritative reinterpretation of bounded AIP answers, new generalized GT/AIP capability, promise approval workflow, or autonomous code mutation without an observed need.

This is an **independent pre-v0.9 reference experiment**, not a release qualification or a validated customer-value claim. It tests a necessary precondition for shared human–AI understanding—whether an investigator can form a more justified account of cooperation conditions and change risks—not collective understanding itself. If existing AIP interfaces suffice, publish findings without manufacturing a new AIP release.

## References

- [Accepted Sokol111 evaluation/demo specification](../../../specifications/evaluation/sokol111-v08-demo.md)
- [Hosted Sokol111 walkthrough (pre-wave-1)](../../../../examples/sokol111-demo/TRY_IT_HOSTED.md)
- [AIP product doctrine](../../../product-doctrine-and-strategic-direction.md)
- [v0.8 binding-picture request schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-request.schema.json)
- [v0.8 binding-picture answer schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-answer.schema.json)
- [Historical GT reference integration](../0.5.1/README.md)
- [GT v1.1.657 release](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.657)
