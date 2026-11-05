# AIP × Glamorous Toolkit — v0.8 Contract Reference Experiment

**Status:** Draft 0.15 — demonstration design, not implemented or qualified  
**Date:** 2026-11-05  
**Experiment scope:** lightweight **pre-v0.9** investigation of Sokol111 as a **sample e-commerce system**, not a production customer; does not qualify an AIP release  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 pre-wave-1 dataset

The `0.8.0/` directory names the **AIP contract consumed**, not a proposed new release. The existing hosted Sokol111 evidence is a starting point, not a complete answer to the scenario. Historical GT integrations remain unchanged.

## 1. Customer decision — introduce a new consumer

**Central question:** **Which locally modeled service promises can a new consumer legitimately rely on, under which conditions, and what commitments—if any—should that consumer decide to make after investigating its requirements? Can AIP + GT improve this decision compared with equivalent ADR/source access without AIP?**

**Business scenario — deliberately small capability difference:** A merchant already uses Sokol111 to present its catalog in an online shop. The merchant wants to reuse the same product data, prices, availability and images on an external marketplace, with initial listing creation and subsequent updates. **The one additional business requirement is that a product disabled or deleted in the shop must be withdrawn from the external marketplace within 15 minutes of that change.** The 15-minute target is a **hypothetical merchant requirement chosen for this experiment**, not a stated policy of a real marketplace and **not** an existing Sokol111 guarantee. Tenant isolation remains necessary. **Orders, checkout and fulfillment are out of scope.** The Marketplace Connector is a **business proposal only**, not an existing Sokol111 service, observed binding, or pre-approved design. The merchant's 15-minute target is **an input requirement; an acceptance promise, solution, and externally offered guarantee are outcomes to investigate**, not scenario inputs.

**Requirement-to-promise investigation (not a predetermined failure or solution):**

| Existing capability / possible offers | New business requirement | Question to investigate |
|---|---|---|
| Catalog publishes product-change events, while Product Query builds a separate product read model and offers reads to its own audience; their **distinct fictional commitments and applicability conditions** live in separate ADRs. | Republish the shop catalog in another channel. | Which local offers permit the new purpose under their own conditions, and which existing acceptance does the available evidence actually support? |
| Product lifecycle changes and marketplace withdrawal have **different owners and delivery stages**. | Withdraw an external listing **within 15 minutes** when a shop product is disabled or deleted. | Which locally offered conditions cover change discovery, submitting a withdrawal and actual visibility removal? What would need to be agreed or verified before anyone promises the end-to-end result? |

**Design constraint:** keep the difference **small but meaningful**; do not expand into inventory reservation, order execution, payment, global consistency or an assumed complete historical event log. The 15-minute deadline is an **end-to-end business outcome**, not a promise automatically assigned to Catalog, Product Query, the connector or the marketplace. An architect must distinguish **(a) source change known, (b) connector detects it and requests withdrawal, (c) marketplace accepts the request, and (d) the listing ceases to be visible**. These stages belong to potentially independent promisers; one stage's guarantee does not manufacture the next.

**Participant-facing task (keep separate from the researcher key):**

> A merchant wants to reuse the product catalog from its existing online shop to maintain listings on a new marketplace. Product information, price, availability and images should stay aligned. **The merchant requires the external listing to be withdrawn within 15 minutes when a shop product is disabled or deleted.** Investigate the promises offered by the existing modeled services and what a new consumer may legitimately rely on. Determine **whether any credible set of commitments can satisfy the requirement, which parties would need to make them, and what remains uncertain**. Do not assume the new connector must or can promise the 15-minute outcome. Recommend **proceed / conditional proceed / defer** and explain any proposed commitments or agreements as your conclusion.

The participant needs ordinary e-commerce knowledge, not a prior mental model of Sokol111. The 15-minute withdrawal condition is a **business requirement only**. **The consumer's responsibilities, acceptance promises, eventual outward offer and any ADR recording that decision are investigation outputs, not provided fixtures.** Provide a brief business/platform orientation but **no answer key, dependency diagram, invented real-world owner approval, presumed failure mechanism or predetermined route**.

### Investigation questions — derived from *Integration Beyond the Interface*

Use the **five consumer-journey questions** from the article as a framework for revealing, understanding and validating **local promises**. Do **not** make discovery of dependencies the main outcome.

| Article-derived question | Promise-centered investigation |
|---|---|
| **1. Why does this capability exist, and for whom?** | Which autonomous owner offers it, what business meaning and audience does its *fictional ADR decision* specify, and which parts are merely documented or inferred? |
| **2. Can a consumer discover and understand what is offered?** | What do the distinct local offers cover: Catalog changes, Product Query projection/read semantics, image lifecycle, and marketplace acceptance/withdrawal? Which claims are promised, evidenced or unknown? |
| **3. Is the consumer permitted to rely on it?** | Compare the **different** locally modeled audiences and conditions: Catalog's projection-event consumers, Product Query's separately scoped read clients, Image's media consumers and the marketplace's authenticated publishers. Which of these conditions could the new consumer satisfy, and what authorization remains to be established? |
| **4. Where does each party's responsibility begin and end?** | How do the **existing** Catalog, Product Query and external-marketplace offers constrain possible connector acceptance and merchant-facing guarantees? Which unowned gap, division of responsibility or new agreement remains? Do not assign the deadline to the connector in advance. |
| **5. What allows cooperation to survive change?** | Which modeled ADR commitments cover compatibility, delivery/recovery, change notification or limits? What conditions must remain compatible, and which changes require a new agreement? |

Framing: [Daniel Kocot, *Integration Beyond the Interface* (adorsys TechRadar, 5 Nov 2026)](https://adorsys.com/en/techradar/integration-beyond-the-interface%20/). These are **questions adapted from the article**, not verbatim questionnaire items.

**Investigation output:** a compact, evidence-linked **promise/reliance picture** and **a decision on whether to introduce consumer commitments**: existing fictional independent service offers **and Product Query's existing acceptance**, the separately modeled marketplace contract, and any **newly proposed** consumer acceptance or merchant-facing offer with conditions, scope, source-derived support and unresolved agreements. Existing bindings are supporting evidence for finding relevant promisers, not the product being evaluated. An unresolved modeled-owner decision is not an assumed promise and a list of necessary conditions is not proof of sufficient end-to-end correctness.

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

**Furnish three existing-service ADRs before investigation:** Catalog's product-change offer, Product Query's independent **acceptance of Catalog changes plus its own read-model offer**, and Image's media offer. A **fourth, separately attributed fictional external-marketplace contract** describes acceptance, eventual application and completion reporting for valid withdrawal requests, **without supplying a numeric completion deadline**; it is an independent business counterparty, not a Sokol111 service or AIP-observed binding. Do not provide a Marketplace Connector ADR, responsibility split, accepted reliance or merchant-facing promise. ADRs document local offers **without being tailored to announce the 15-minute gap**; keep genuine applicability limits, rationale and provenance but remove preemptive conclusions. **An optional new-consumer ADR may be written only after investigation**, containing a justified conditional decision, agreements, evidence and limits. An explicit decision not to promise anything is equally valid.

**Independent promises:** Catalog's offered capability (+), Product Query's **separately identifiable** acceptance `PQ-ACCEPT-01` (−) and read offer `PQ-READ-01` (+), Image's offer (+), and the external marketplace's distinct conditional offer (+) are **separate fictional decisions by modeled autonomous roles**. The two Product Query commitments have **different audiences and applicability**; one cannot extend the other. The marketplace contract supports reasoning about an independent last stage, but **does not set the time needed to make a listing invisible**. It does not prove that the connector can fulfill prerequisites or that the merchant's deadline is attainable. Do not turn its eventual-completion promise into an SLA or present this as an arithmetic time-budget exercise. The connector has **no furnished ADR, observed binding or confirmed acceptance**. A business requirement never creates a provider obligation or consumer commitment; an architect may formulate or decline one after investigation. Implementation facts never become Intent automatically.

**Source and AIP limits:** [Sokol111 workspace](https://github.com/Sokol111/ecommerce-workspace), [Catalog](https://github.com/Sokol111/ecommerce-catalog-service), [Product Query](https://github.com/Sokol111/ecommerce-product-query-service), [Image](https://github.com/Sokol111/ecommerce-image-service) and provider-owned API repositories provide **source evidence**, not real owner commitments. The independently modeled external marketplace has **no Sokol111 code evidence**. AIP's frozen v0.8 `get_binding_picture` qualifies *existing, scoped* broker attachments with demo-assumed `sends`/`receives`; it does **not** ingest these ADRs, qualify event-type processing or read freshness, establish withdrawal timing or permissions, or observe the future connector/marketplace. **Incomplete v0.8 coverage is not a blocker**. GT may juxtapose separately pinned ADR/contract fixtures and AIP evidence, but must **not** call their semantic promises AIP-qualified Intent or fabricate an AIP Assessment.

**One AIP-sensitive promise–evidence check (research protocol, not a participant hint):** Product Query's ADR separately identifies its acceptance of Catalog product changes (`PQ-ACCEPT-01`) and its read offer (`PQ-READ-01`). The existing C1 binding picture includes the Product Query attachment to `catalog.product.events` crossing Catalog Management's boundary; its `PROMISED_AND_OBSERVED` label comes from **C1's own demo EventCatalog assumption**, **not** either ADR promise. Ask whether this **qualified broker attachment** changes what an architect may conclude about the scope or applicability of `PQ-ACCEPT-01`, and distinguish that conclusion from what is established about `PQ-READ-01`. Attachment **does not establish** event-type handling, complete projections, read freshness, a delivery deadline or acceptance of a new marketplace consumer. Compare the architect's **initial belief, discovered evidence, revised conclusion and resulting consumer decision** against the no-AIP condition. If AIP contributes no independently justified revision, E1 is negative or inconclusive. Do not make GT lead participants along this predetermined example.

**Keep the provenance visible:** (1) fictional assumed existing-provider promise, (2) any **post-investigation, investigator-proposed** consumer commitment, (3) source-derived observation or declaration, (4) existing AIP-qualified result, (5) investigator hypothesis. None automatically promotes to another. Lack of promise coverage means **unresolved**, not proof of no agreement. A list of necessary conditions is not a sufficient end-to-end guarantee.

**Freeze and parity:** Record the hosted AIP **package ID, complete snapshot ID, capture time and exact query scope**, plus pinned source/API revisions, raw broker captures, authored consumer-group mappings, context/boundary membership inputs, EventCatalog assumptions and applicable qualification rules. Freeze **each independently modeled ADR and the external-marketplace contract** plus the researcher key before evaluation. All comparison conditions receive **the same ADRs, external contract and raw underlying sources**; only AIP's qualified projections vary. Never blend pre-wave-1 hosted C1 with separate post-migration recordings.

**Evidence drill-down:** Resolve `binding-evidence:` refs using `get_binding_picture` in `mode: "evidence"` with the original snapshot/context/environment/broker IDs, preserving evidence roles, limitations and ref bounds. Do not infer ownership/context membership from topology.

**GT is a promise-first exploration:** navigate **business requirement → existing service ADR and rationale → offered promise and applicability → underlying evidence / AIP qualified context → investigate feasible responsibility options → decide whether to propose any consumer acceptance or outward promise**. A binding picture can locate a promiser, but counting nodes or drawing a graph is not the aim. Use one lightweight Phlow/Lepiter story; no new AIP APIs, registry or hosted data mutation.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Freeze independent offers and evidence** | Freeze **three** existing-service demo ADRs (Catalog, Product Query acceptance + read offer, Image), **one separately modeled marketplace withdrawal contract**, source/evidence identities, merchant task and independent researcher key. No Marketplace Connector ADR is shown or prepared. | Different autonomous commitments and their scope are inspectable, while the **15-minute consumer responsibility and outcome remain open**. ADRs do not preannounce the expected mismatch. No real owner approval or complete v0.8 qualification is required. |
| **2 — Investigate and formulate a decision with GT** | One small Phlow/Lepiter exploration of **locally distinct offers, existing acceptance and external-marketplace conditions**, with bounded AIP evidence where relevant. **Only after investigation** may the architect propose a conditional connector commitment/ADR or decline to make one. | A person unfamiliar with Sokol111 can distinguish **change detection, withdrawal request, acceptance and actual listing visibility**, explain which commitments might be compatible, and **record a conclusion revised (or upheld) by attributable evidence**. |
| **3 — Compare and publish** | Compare with source/ADR-only agent, GT without AIP, GT+AIP and direct AIP agent; collect independently derived decisions and **belief → finding → revised recommendation** records, including their cited authority and evidence. | Honest E1/E2 **demo feasibility** findings, including cases where ADR navigation helps but AIP does **not** change a decision. No real-owner-adoption or customer-value claim. |

## 4. Evaluation — follow the consumer journey

**E1 — Qualified cooperation knowledge:** Does AIP's scoped Current State/Assessment **materially revise or strengthen a particular promise-related architectural conclusion** beyond equivalent ADR/source-only investigation? Record the before/after conclusion and specific AIP-qualified premise. Merely displaying another service/topic, locating an ADR or reproducing the same recommendation does not demonstrate incremental decision value.

**E2 — Inspectable local promises (demo):** Do the fictional **existing-provider** promises and their ADR rationale help the architect determine **what a new consumer could credibly commit to after investigation**, what requires negotiation or verification, or why no commitment is justified? This tests the workflow, **not the value of actual organizational owner confirmation**.

Freeze the participant-facing task and an independent researcher key; do not hardwire an answer, pre-highlight a missing guarantee, or give the investigators an expected service route. Score findings across the article-derived questions from §1:

| Question | What counts as a useful promise-related result? |
|---|---|
| **Purpose / audience** | Discovers which fictional service role decided to offer the capability, why, to whom, with what limitations. |
| **Meaning / reliance** | Distinguishes Product Query's **`PQ-ACCEPT-01` versus `PQ-READ-01`** audience and conditions, Catalog's events, Image's media offer and the external marketplace contract from independently qualified evidence. It does not conflate stage completion with end-to-end withdrawal. |
| **Permitted use** | Identifies whether the modeled offer covers this consumer, tenant and purpose, or where the premise remains unconfirmed. |
| **Independent commitments** | Derives or declines connector commitments **after** examining all autonomous offers, including the marketplace's independently scoped obligations; separates accepted withdrawal requests from actual removal. |
| **Change / compatibility** | Identifies changing conditions, evidence and owner-level decisions required to keep the new cooperation viable. |

Compare four conditions **with identical initial ADRs, external marketplace contract, source revisions, raw captures and task**:

| Condition | Isolates |
|---|---|
| Coding agent + raw sources and demo ADRs, no AIP | Whether normal architecture/source investigation is enough |
| GT + identical inputs, no AIP | Value of ADR-centered interactive navigation |
| GT + identical inputs + AIP | Incremental benefit of AIP-qualified existing bindings and evidence |
| Coding agent + direct AIP | Whether GT adds value beyond direct agent use of AIP; necessary before claiming GT-specific advantage |

**Carryover control:** Prefer separate investigators or fresh, independent agent sessions per condition; record prior familiarity and what each investigator knew before starting. Where people repeat conditions, counterbalance the order and **exclude discoveries already learned in earlier conditions from incremental scores**. If independence is impractical, report the comparison as exploratory and make no causal tool-benefit claim.

**Insight and attribution criterion (primary):** Record the architect's **starting belief or provisional recommendation**, the **specific promise-related discovery**, its cited evidence and authority, the **revised or reaffirmed understanding and decision**, and whether the same result arose without AIP. Rank **a justified, previously unrecognized change to a consumer-onboarding decision** above locating ADRs or accurately restating their contents. An unchanged decision can still show improved justification, but do not score it as a decision change. For every consequential finding, distinguish (a) fictional ADR/marketplace-contract premises, (b) source-derived behavior, (c) independently qualified AIP C1 attachment/Assessment, and (d) architect inference. In particular, **do not count C1's broker attachment as qualification of Product Query's modeled event-type acceptance**, nor the marketplace contract as evidence of actual external behavior. Score **correctly scoped offers and acceptance, justified new-consumer promises or refusal, stage-specific conditions, unsupported reliance, and expected versus independently verified unexpected insights**; separately report **document discovery, promise comprehension and decision-changing insight**. Never equate a polished GT traversal with an AIP-supported architectural insight. Unsupported acceptance or a copied 15-minute guarantee without supporting conditions is a failure, not an output. Record ADR/GT fixture and investigation maintenance effort. A justified **conditional proceed** or **defer** can outperform unsupported certainty. Do not reward dependency count or a merely attractive visualization. Any promising E2 result demonstrates the *interaction design* only, not real decision value/sustainable owner effort; product doctrine H1/H2 require target customer validation.

## 5. Minimal deliverables

- This `specification.md` and aligned READMEs / integration index.
- **Three pre-existing service-local demo ADRs** (Catalog, Product Query, Image), plus an **independently modeled external marketplace contract**; clearly fictional, independently versioned, scoped and source-attributed where applicable. **No seeded new-consumer ADR.** An optional investigator-authored Marketplace Connector ADR or explicit no-commitment decision is an **output**, not an initial input. No Sokol111 upstream edits.
- After implementation: GT source export + one executable Lepiter investigation; compact frozen evidence/task/key and evaluation report.

Keep historical `0.4.2/` and `0.5.1/` integrations unchanged.

## 6. Non-goals and release boundary

No real Sokol111 or marketplace owner approval, upstream Sokol111 repository mutation, production marketplace connector, fabricated signatures or actual marketplace policy, universal promise/ADR registry, AIP schema/host mutation, inferred authorization or provider guarantee, implementation refactoring or GT graph platform. **Sokol111 is a sample**; ADR `DEMO_ASSUMED_CONFIRMED` is explicitly fictional and does not qualify as customer-confirmed Intent.

The experiment illustrates how autonomous local promises might be captured in ADRs and investigated against a new consumer's slightly different requirement. AIP provides bounded architectural premises; GT helps inspect and challenge them. **Partial v0.8 qualification is not a blocker**, and the showcase alone cannot establish product doctrine H1 (decision value) or H2 (sustainable owner effort).

## References

- [Integration Beyond the Interface — Daniel Kocot, adorsys TechRadar](https://adorsys.com/en/techradar/integration-beyond-the-interface%20/)
- [AIP product doctrine](../../../product-doctrine-and-strategic-direction.md)
- [v0.9 roadmap evaluation requirements](../../../../ROADMAP.md)
- [Sokol111 workspace and architecture](https://github.com/Sokol111/ecommerce-workspace)
- [Product Query source and API context](https://github.com/Sokol111/ecommerce-product-query-service)
- [Demo promise fixtures](demo-promises/README.md)
- [Accepted Sokol111 v0.8 demonstration and hosted C1 limits](../../../specifications/evaluation/sokol111-v08-demo.md)
- [Hosted Sokol111 walkthrough](../../../../examples/sokol111-demo/TRY_IT_HOSTED.md)
- [v0.8 binding-picture request schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-request.schema.json)
- [v0.8 binding-picture answer schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-answer.schema.json)
- [Historical GT reference integration](../0.5.1/README.md)
- [GT baseline release](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.657)
