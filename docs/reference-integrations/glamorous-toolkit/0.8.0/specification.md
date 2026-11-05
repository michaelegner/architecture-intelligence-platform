# AIP × Glamorous Toolkit — v0.8 Contract Reference Experiment

**Status:** Draft 0.13 — demonstration design, not implemented or qualified  
**Date:** 2026-11-05  
**Experiment scope:** lightweight **pre-v0.9** investigation of Sokol111 as a **sample e-commerce system**, not a production customer; does not qualify an AIP release  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 pre-wave-1 dataset

The `0.8.0/` directory names the **AIP contract consumed**, not a proposed new release. The existing hosted Sokol111 evidence is a starting point, not a complete answer to the scenario. Historical GT integrations remain unchanged.

## 1. Customer decision — introduce a new consumer

**Central question:** **Which locally modeled service promises can a new consumer legitimately rely on, under which conditions, and what commitments—if any—should that consumer decide to make after investigating its requirements? Can AIP + GT improve this decision compared with equivalent ADR/source access without AIP?**

**Business scenario — deliberately small capability difference:** A merchant already uses Sokol111 to present its catalog in an online shop. The merchant wants to reuse the same product data, prices, availability and images on an external marketplace, with initial listing creation and subsequent updates. **The one additional business requirement is that a product disabled or deleted in the shop must be withdrawn from the external marketplace within 15 minutes of that change.** The 15-minute target is a **hypothetical merchant requirement chosen for this experiment**, not a stated policy of a real marketplace and **not** an existing Sokol111 guarantee. Tenant isolation remains necessary. **Orders, checkout and fulfillment are out of scope.** The Marketplace Connector is a **business proposal only**, not an existing Sokol111 service, observed binding, or pre-approved design. The merchant's 15-minute target is **an input requirement; an acceptance promise, solution, and externally offered guarantee are outcomes to investigate**, not scenario inputs.

**Requirement-to-promise investigation (not a predetermined failure or solution):**

| Source-supported existing capability and modeled demo offer | New business requirement | Question for independent promises |
|---|---|---|
| Display-oriented catalog reads and product-change events are available as **implementation/contract evidence**, with externally offered scope defined only by the fictional demo ADR (not by real Sokol111 owners). | Republish the same product information and updates through a new channel. | Which provider offers and consumer-use permissions actually extend to this different audience/purpose? |
| Product state contains enabled/deleted lifecycle information in relevant implementation/events; **no 15-minute delivery guarantee is established by this fact**. | Withdraw an external listing **within 15 minutes** when the merchant disables or deletes the product. | Does any owner offer sufficient delivery, freshness or query guarantees? If not, can the connector undertake the additional responsibility independently, or is a new agreement/provider change necessary? |

**Design constraint:** keep the required difference **small but meaningful**; do not silently expand the marketplace scenario into inventory reservation, order execution, payment, global consistency or an assumed complete historical event log. A missing upstream 15-minute promise is not itself proof that the use case is impossible: the architect must investigate which participant could credibly make and fulfill the merchant-facing commitment.

**Participant-facing task (keep separate from the researcher key):**

> A merchant wants to reuse the product catalog from its existing online shop to maintain listings on a new marketplace. Product information, price, availability and images should stay aligned. **The merchant requires the external listing to be withdrawn within 15 minutes when a shop product is disabled or deleted.** Investigate the promises offered by the existing modeled services and what a new consumer may legitimately rely on. Determine **whether any credible set of commitments can satisfy the requirement, which parties would need to make them, and what remains uncertain**. Do not assume the new connector must or can promise the 15-minute outcome. Recommend **proceed / conditional proceed / defer** and explain any proposed commitments or agreements as your conclusion.

The participant needs ordinary e-commerce knowledge, not a prior mental model of Sokol111. The 15-minute withdrawal condition is a **business requirement only**. **The consumer's responsibilities, acceptance promises, eventual outward offer and any ADR recording that decision are investigation outputs, not provided fixtures.** Provide a brief business/platform orientation but **no answer key, dependency diagram, invented real-world owner approval, presumed failure mechanism or predetermined route**.

### Investigation questions — derived from *Integration Beyond the Interface*

Use the **five consumer-journey questions** from the article as a framework for revealing, understanding and validating **local promises**. Do **not** make discovery of dependencies the main outcome.

| Article-derived question | Promise-centered investigation |
|---|---|
| **1. Why does this capability exist, and for whom?** | Which autonomous owner offers it, what business meaning and audience does its *fictional ADR decision* specify, and which parts are merely documented or inferred? |
| **2. Can a consumer discover and understand what is offered?** | Which demo-accepted or proposed local promises cover product data, initial state, updates, removals and media? Do any offer a relevant freshness or publication bound, or merely a technical change event? What scope and limitations are explicit versus unknown? |
| **3. Is the consumer permitted to rely on it?** | What does the modeled provider's ADR actually offer about tenant, identity, purpose, permissions and delegated access? Is marketplace use within the fictional offered scope, a proposed agreement, or unknown? |
| **4. Where does each party's responsibility begin and end?** | What (if anything) could the new consumer legitimately accept or promise **after** investigating provider and intermediary offers? Could responsibility be divided, require a new agreement, or leave the 15-minute requirement unsupported? Distinguish proposed decisions from assumed commitments. |
| **5. What allows cooperation to survive change?** | Which modeled ADR commitments cover compatibility, delivery/recovery, change notification or limits? What conditions must remain compatible, and which changes require a new agreement? |

Framing: [Daniel Kocot, *Integration Beyond the Interface* (adorsys TechRadar, 5 Nov 2026)](https://adorsys.com/en/techradar/integration-beyond-the-interface%20/). These are **questions adapted from the article**, not verbatim questionnaire items.

**Investigation output:** a compact, evidence-linked **promise/reliance picture** and **a decision on whether to introduce consumer commitments**: existing fictional provider offers, any **newly proposed** consumer acceptance or merchant-facing offer with conditions, applicability limits, source-derived support and unresolved agreements. Existing bindings are supporting evidence for finding relevant promisers, not the product being evaluated. An unresolved modeled-owner decision is not an assumed promise and a list of necessary conditions is not proof of sufficient end-to-end correctness.

**Demonstration objective:** Make a small set of **fictional but source-informed local service promises** explicit as **promise-bearing ADRs**. These model decisions by autonomous service roles for the purposes of this AIP showcase. **Sokol111 is sample code; real Sokol111-maintainer approval or repository changes are not required.** The demonstration must label assumptions as such and never imply an actual maintainer accepted them. The resulting ADRs live with this reference integration, not in upstream Sokol111.

### Experimental questions, independent of the product doctrine

- **E1 — Qualified cooperation knowledge:** does AIP's qualified view of existing cooperation help an architect **find, distinguish and interpret the modeled local promises, their provenance and missing agreements**, compared with source-only investigation? More discovered bindings alone are not a success.
- **E2 — Inspectable local promises (demo):** given fictional **existing-provider** offers recorded in demo ADRs, does navigating their decisions, conditions and qualified context help the architect **formulate or reject a justified new-consumer commitment as an output**? This tests interaction/design feasibility, not actual owner adoption.

These are not the product doctrine's **H1 (customer decision value)** and **H2 (sustainable owner effort)**, which require real customers. An ADR labeled **demo-assumed confirmed** is valid as a *fictional premise* for testing E2's navigation but must never be presented as owner-confirmed in Sokol111. Partial AIP v0.8 coverage remains acceptable.

## 2. Promise-bearing ADRs and evidence discipline

### ADRs as a local promise carrier, not a central authority

An **ADR documents a decision**: why a modeled autonomous service offers a capability, to which audience, with what conditions and trade-offs. The **external promise inside the ADR** is a distinct part of that decision. An ADR about implementation internals is not automatically an external promise.

Create a small versioned **demo-only** ADR set under `docs/reference-integrations/glamorous-toolkit/0.8.0/demo-promises/`. Model separate fictional service owners; do **not** modify the Sokol111 upstream repositories, invent actual approvals or describe AIP as the production source of authoritative promises. In a real customer organization, the promiser's own team/repository would own the ADR and its lifecycle.

Use ordinary ADR structure, with just enough dedicated promise metadata to inspect it:
- **Status and decider:** `DEMO_ASSUMED_CONFIRMED` for a consciously assumed fictional **existing-service** decision. A future consumer's decision may use `DEMO_PROPOSED` **only in an investigator-produced result after exploration**. These are demo labels, not AIP status enums or real owner confirmation.
- **Context / decision / rationale:** why the modeled owner offers this capability; alternatives considered and consequences.
- **Promise (+ or −):** who offers or accepts what, to whom, with explicitly stated behavior, audience, scope, applicability, limitations and effective version.
- **Evidence and qualification:** pinned source/code/API references, separately stated AIP-qualified Current State if applicable, and explicit gaps.
- **Evolution:** who would need to revisit or supersede this commitment if its applicability or conditions change.

**Only two provider ADRs are furnished before investigation:** Catalog product-change capability and Image promotion/media capability. No prewritten Marketplace Connector ADR, acceptance, responsibility split or 15-minute merchant-facing promise belongs in the participant-accessible fixtures. They should be short, readable and source-consistent. Do not manufacture an upstream 15-minute guarantee or construct a puzzle with a prescribed answer. **An optional new-consumer ADR may be written after the investigation**, containing the architect's conditional decision, proposed provider/consumer agreements, rationale, unanswered questions and any realistic limits. A conclusion that no credible offer can yet be made is equally valid; do not force a consumer ADR asserting a promise.

**Independent promises:** Existing provider offers (+), possible consumer acceptance/use (−) and intermediary promises are autonomous; a business requirement never creates a provider obligation or a consumer commitment. The future connector has **no provided ADR, observed binding or confirmed acceptance**. Its possible acceptance and outward offer may **emerge as an architect-authored decision** or remain unresolved. Implementation/code evidence must not silently become a promise, even in the demo.

**Source and AIP limits:** [Sokol111 workspace](https://github.com/Sokol111/ecommerce-workspace), [Catalog](https://github.com/Sokol111/ecommerce-catalog-service), [Image](https://github.com/Sokol111/ecommerce-image-service) and their API repositories offer evidence of existing system behavior. AIP's frozen v0.8 `get_binding_picture` supports scoped *existing* broker attachments and demo-assumed `sends`/`receives`; it does **not** ingest these new ADRs or establish publication deadlines, permission, application-level correctness or a binding for the proposed connector. **Incomplete v0.8 coverage is not a blocker**: GT may present independently pinned demo ADRs beside AIP's qualified evidence, but cannot call the ADRs AIP-qualified Intent or fabricate AIP assessments.

**Keep the provenance visible:** (1) fictional assumed existing-provider promise, (2) any **post-investigation, investigator-proposed** consumer commitment, (3) source-derived observation or declaration, (4) existing AIP-qualified result, (5) investigator hypothesis. None automatically promotes to another. Lack of promise coverage means **unresolved**, not proof of no agreement. A list of necessary conditions is not a sufficient end-to-end guarantee.

**Freeze and parity:** Record the hosted AIP **package ID, complete snapshot ID, capture time and exact query scope**, plus pinned source/API revisions, raw broker captures, authored consumer-group mappings, context/boundary membership inputs, EventCatalog assumptions and applicable qualification rules. Freeze ADR versions and the researcher key before evaluation. All comparison conditions receive **the same ADRs and raw underlying sources**; only AIP's qualified projections vary. Never blend pre-wave-1 hosted C1 with separate post-migration recordings.

**Evidence drill-down:** Resolve `binding-evidence:` refs using `get_binding_picture` in `mode: "evidence"` with the original snapshot/context/environment/broker IDs, preserving evidence roles, limitations and ref bounds. Do not infer ownership/context membership from topology.

**GT is a promise-first exploration:** navigate **business requirement → existing service ADR and rationale → offered promise and applicability → underlying evidence / AIP qualified context → investigate feasible responsibility options → decide whether to propose any consumer acceptance or outward promise**. A binding picture can locate a promiser, but counting nodes or drawing a graph is not the aim. Use one lightweight Phlow/Lepiter story; no new AIP APIs, registry or hosted data mutation.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Prepare existing-provider ADRs** | Freeze **only two** fictional provider promise ADRs, source evidence, the merchant's business requirement and the independent researcher key. No proposed Marketplace Connector ADR or promise is prepared or shown. | The **existing-shop offers versus the new 15-minute requirement** are available for open investigation, without an assigned consumer responsibility or accepted promise. No real Sokol111 approval is required. |
| **2 — Investigate and formulate a decision with GT** | One small Phlow/Lepiter exploration of existing offers and limits, using bounded AIP-qualified context when relevant. **Only after investigation**, the architect may formulate a conditional consumer commitment/ADR or decline to make one. | A person unfamiliar with Sokol111 can justify **which commitments, if any, should be proposed and by whom**, including unsupported/unknown conditions, without a supplied consumer promise. |
| **3 — Compare and publish** | Compare with source/ADR-only agent, GT without AIP, GT+AIP and direct AIP agent; **collect each independently derived consumer decision/ADR as an output**, evaluate promise attribution, justified responsibility, false guarantees, unexpected insights and maintenance effort. | Honest E1/E2 **demo feasibility** findings, including valid outcomes that make **no new promise**. No real-owner-adoption or customer-value claim. |

## 4. Evaluation — follow the consumer journey

**E1 — Qualified cooperation knowledge:** Does AIP's scoped Current State/Assessment improve a *promise-related* architectural decision beyond equivalent ADR/source-only investigation? Do not award AIP credit just for displaying an extra service/topic.

**E2 — Inspectable local promises (demo):** Do the fictional **existing-provider** promises and their ADR rationale help the architect determine **what a new consumer could credibly commit to after investigation**, what requires negotiation or verification, or why no commitment is justified? This tests the workflow, **not the value of actual organizational owner confirmation**.

Freeze the participant-facing task and an independent researcher key; do not hardwire an answer, pre-highlight a missing guarantee, or give the investigators an expected service route. Score findings across the article-derived questions from §1:

| Question | What counts as a useful promise-related result? |
|---|---|
| **Purpose / audience** | Discovers which fictional service role decided to offer the capability, why, to whom, with what limitations. |
| **Meaning / reliance** | Separates ADR promise semantics and conditions from source-derived behavior; avoids treating a change event as a 15-minute withdrawal guarantee. |
| **Permitted use** | Identifies whether the modeled offer covers this consumer, tenant and purpose, or where the premise remains unconfirmed. |
| **Independent commitments** | **Derives** potential consumer acceptance and merchant-facing promises **after exploring** the provider offers; may conclude no promise is justified. Identifies responsibility and agreements without adopting the business target as an automatic guarantee. |
| **Change / compatibility** | Identifies changing conditions, evidence and owner-level decisions required to keep the new cooperation viable. |

Compare four conditions **with identical underlying ADRs, source revisions, raw captures and task**:

| Condition | Isolates |
|---|---|
| Coding agent + raw sources and demo ADRs, no AIP | Whether normal architecture/source investigation is enough |
| GT + identical inputs, no AIP | Value of ADR-centered interactive navigation |
| GT + identical inputs + AIP | Incremental benefit of AIP-qualified existing bindings and evidence |
| Coding agent + direct AIP | Whether GT adds value beyond direct agent use of AIP; necessary before claiming GT-specific advantage |

Score **correctly classified existing fictional offers, scope/limitations, unsupported reliance, warranted or declined new-consumer promises, viable decisions, and expected vs independently verified unexpected insights**. Treat unsupported acceptance or a copied 15-minute commitment without evidence as a failure, not a completed artifact. Record ADR/GT maintenance effort. A justified **conditional proceed** or **defer** can outperform unsupported certainty. Do not reward dependency count or a merely attractive visualization. Any promising E2 result demonstrates the *interaction design* only, not real decision value/sustainable owner effort; product doctrine H1/H2 require target customer validation.

## 5. Minimal deliverables

- This `specification.md` and aligned READMEs / integration index.
- **Two pre-existing provider demo ADRs** with fictional promisers, offers, conditions and provenance; **no seeded new-consumer ADR**. An optional architect-authored Marketplace Connector ADR or explicit no-commitment decision is an **output of the investigation**, not part of the initial participant inputs. No Sokol111 upstream edits.
- After implementation: GT source export + one executable Lepiter investigation; compact frozen evidence/task/key and evaluation report.

Keep historical `0.4.2/` and `0.5.1/` integrations unchanged.

## 6. Non-goals and release boundary

No real Sokol111 owner approval, upstream Sokol111 repository mutation, production marketplace connector, fabricated signing by real people, universal promise/ADR registry, AIP schema/host mutation, inferred authorization or provider guarantee, implementation refactoring or GT graph platform. **Sokol111 is a sample**; ADR `DEMO_ASSUMED_CONFIRMED` is explicitly fictional and does not qualify as customer-confirmed Intent.

The experiment illustrates how autonomous local promises might be captured in ADRs and investigated against a new consumer's slightly different requirement. AIP provides bounded architectural premises; GT helps inspect and challenge them. **Partial v0.8 qualification is not a blocker**, and the showcase alone cannot establish product doctrine H1 (decision value) or H2 (sustainable owner effort).

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
