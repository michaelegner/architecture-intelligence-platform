# AIP × Glamorous Toolkit — v0.8 Contract Reference Experiment

**Status:** Draft 0.7 — specification only; not implemented or qualified  
**Date:** 2026-11-04  
**Experiment scope:** lightweight **pre-v0.9** investigation; its results may inform a future AIP release, but do not define or qualify one  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 pre-wave-1 dataset

The `0.8.0/` directory identifies the **AIP contract consumed**. Historical GT integrations remain unchanged.

## 1. One architect question

**Can AIP-supported, promise-aware investigation help an architect identify the conditions necessary for successful cooperation across autonomous services, and determine how a proposed change may endanger those conditions—better than the same source access without AIP?**

**Hypothesis:** AIP's attributable local Intent, qualified Current State and Assessment, combined with independent contextual tools and source analysis, improve understanding of *why* distributed cooperation works, which conditions it relies upon, and what remains unresolved. The binding picture is the entry point, not the result. The investigation may establish necessary conditions, but must never infer a complete or sufficient end-to-end guarantee from a collection of local claims.

**Preferred Sokol111 scenario — outgoing-event retention:** A Catalog service owner proposes reducing storage costs by shortening retention of persisted outgoing event records (candidate target: 24 hours). The architect investigates *which autonomous participants rely on the resulting event flows*, which conditions enable successful cooperation, and which changes would affect those conditions. Start with Catalog, shared `ecommerce-commons`, independently evidenced consumers and relevant broker bindings; do not presuppose Product Query as the only affected consumer.

**Participant-facing task card:** > Catalog proposes shortening retention of stored outgoing event records to reduce costs. Determine which autonomous participants and cooperation conditions must be investigated before accepting the change. Distinguish attributable promises, independently supported behavior, unpromised assumptions, and needed verification. This task card must not disclose the expected failure mechanism or a route to a specific consumer.

**Researcher-only candidate finding (exclude from participant materials and navigation):** the current shared outbox has a five-day `createdAt` TTL index not restricted to sent records; publication, retry and confirmation follow separately after transactional recording. Pending records may therefore expire during extended outages, reducing opportunities to update downstream projections. The five-day configuration already imposes this limit; reducing it to 24 hours changes that risk. This is an independently testable *hypothesis*, not a verified incident or an owner-confirmed delivery promise.

**Deployment qualification:** merely editing the TTL constant does **not** update an existing MongoDB index. An existing index requires `collMod`; new instances may create the new index directly. Shortening TTL makes older records eligible for asynchronous deletion; verify actual index options and effects before interpreting a test ([MongoDB documentation](https://www.mongodb.com/docs/manual/core/index-ttl/)). Separate code change, database migration and runtime observations.

**Scenario fitness gate:** before building any GT views, establish at least one material cross-boundary question for which AIP supplies qualified knowledge beyond the initiating repository; inventory actual owner-confirmed promises versus candidate/assumed declarations. If the case reduces to local TTL code review without AIP-consequential knowledge, report a negative feasibility result or choose another pinned Sokol111 change. Do not manufacture a promise or force a successful scenario.

**What counts as an outcome:** (a) independently supported, decision-relevant conditions and risks; (b) explicitly unresolved assumptions or gaps that change the verification/coordination plan; (c) proposed checks or decisions traceable to those findings. A merely interesting question, added node, attractive visualization or generic outbox explanation does **not** count as a verified risk. New-to-investigator questions are recorded separately from validated findings.

**Scope discipline and two hypotheses:** H1: qualified AIP cross-boundary knowledge helps discover necessary cooperation conditions beyond source-only analysis. H2: genuinely owner-attributable, inspectable local provider/consumer promises improve investigation of those conditions or missing agreements. The hosted v0.8 C1 dataset only qualifies bounded topic attachments and `sends`/`receives`; it cannot establish outbox durability, delivery timing, event processing or behavioral promises. Its assumed-confirmed catalog entries are **not** owner confirmation. If no relevant owner-confirmed promises exist, H2 cannot be positively validated; evaluate H1 separately and report the limitation. The recorded after-wave-1 evidence is not hosted or needed.

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

**Evidence access parity.** Source-only baselines receive the same pinned repositories, contracts/candidate promise declarations, and raw broker captures from which AIP qualified its bindings. AIP access may add normalized claims, provenance and qualification—not privileged access to otherwise unavailable facts. Record gaps in parity and do not attribute information asymmetry to AIP insight.

**Pin and separate sources.** Inventory the hosted pre-wave-1 C1 snapshot, service and commons repository revisions, and any tests/configuration used. Preserve each source's authority, locality, effective time, capture scope and limitations; identify proposed changes separately from observed/current behavior. If richer read-only data is essential, create a separately identified reproducible package rather than silently alter the hosted frozen dataset or blend before/after captures. Do not claim the public endpoint serves recorded post-migration evidence.

**Respect evidence drill-down.** Resolve v0.8 `binding-evidence:` refs using `get_binding_picture` in `mode: "evidence"` with the exact original snapshot, bounded context, environment and broker IDs; deduplicate/sort the supported 1–20 refs and retain evidence roles and errors. Candidate GT groupings are not authoritative Bounded Contexts. Never recompute AIP `crossing`/`status` from hypothesized boundaries or treat `NONE` relative to Catalog Management as a Store Provisioning classification.

**Keep implementation small.** Prefer basic Phlow inspectors, linked objects and one executable Lepiter investigation. A graph is optional only if it helps investigate a concrete condition. Use existing code/test infrastructure where possible; do not introduce Oracle/sessionless transactions, new distributed runtime services, customized GT images, AIP tools or a general promise registry for the showcase.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Evidence fitness and frozen controls** | Pin repository revisions, hosted snapshot and raw evidence; check whether the proposed change has an AIP-relevant cross-boundary question; inventory **real owner-confirmed** versus candidate/assumed promises. Freeze a separate participant task card, independent answer key and rubric before building views. | Explicit **GO / DEFER**. Without demonstrable AIP-relevant knowledge, defer the GT implementation. Without genuine attributable promises, H2 remains untestable; do not treat demo assumptions as owner adoption. |
| **2 — One open-ended investigation** | Minimal GT/Lepiter flow: change → relevant participants/bindings → available local promises, conditions and uncertainty → possible consequences, tests or owner questions. No prewired route to TTL expiry or a designated downstream consumer. | An architect can identify independently supported conditions and distinguish tested risks from unresolved assumptions without upgraded claims. |
| **3 — Evaluate and publish** | Run fair baseline comparisons and independently check findings; reproduce in clean GT; report H1/H2 separately and maintenance/owner effort. | Short report records validated new architectural insights, false claims, missed participants, decision quality, cost and negative/inconclusive outcomes. |

Keep this lightweight. No generic promise registry, runtime service, AIP tool, or new release merely to make the experiment succeed.

## 4. Fair evaluation

**Pre-register a source-grounded answer key and a separate unspoiled task card** before increment 2. The researcher key may identify the five-day `createdAt` TTL, retry mechanism, possible 24-hour change, potentially impacted consumers, promise-coverage gaps and MongoDB `collMod` requirement. The investigator is asked about cooperation conditions **without** being given the TTL failure mechanism. GT views must not encode the answer or guide users toward a single prediction. Unexpected results are welcome if independently checked using the original rubric.

**Same evidence, different qualification:** Supply equivalent repository revisions, service documents, published contracts, candidate promise carriers, raw broker captures, task description and comparable agent assistance to every condition. AIP-enabled tools alone may expose AIP's *qualified interpretation* of that evidence. Record any unavoidable asymmetry and do not confuse extra information with better interpretation.

The minimum comparison set is:

| Condition | What it isolates |
|---|---|
| Source-only coding agent using the same raw evidence, **no AIP** | Whether ordinary source and broker analysis already find the change risk |
| **GT without AIP**, same raw evidence | Whether contextual exploration alone helps |
| **GT + AIP**, same raw evidence | Whether AIP's qualified relationships/attributed promises improve the GT investigation |

If feasible, also run the agent **with direct AIP access** to isolate whether GT adds value beyond AIP. A simple evidence-linked report is optional, not a mandatory fifth condition. Report any omitted comparisons.

**Score separately:** (1) independently supported and decision-relevant cooperation conditions, including cross-boundary relationships; (2) genuinely attributable promises versus candidate declarations and *unpromised assumptions*; (3) risks **verified** by separate evidence versus plausible but untested hypotheses or merely asked questions; (4) missed consumers, unsupported claims and incorrect evidence qualification; (5) justified owner coordination, decision/test quality, investigation and maintenance effort. An outbox implementation finding alone is not credited to AIP. Do not treat necessary conditions as a proved sufficient end-to-end guarantee.

**Execution/test constraints:** Verify the *effective MongoDB TTL index*, retry/sender behavior and downstream state in any failure injection; updating an existing index requires `collMod` and TTL expiration is asynchronous. An observed failure supports only the bounded mechanism tested. If untested, retain a hypothesis and say why.

**Independent outcome gates:** If no owner-attributable promises exist, record H2 as **not validated**, not a promise-centric success. If AIP adds no material verified advantage over raw-source baselines, report H1 **not supported** even if GT is pleasant. A GT-only improvement is a GT finding; if direct AIP already suffices, evaluate whether GT's extra cost is worthwhile. This demo does not establish team-level collective understanding or justify v0.9 AIP-side work without a demonstrated need.

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
