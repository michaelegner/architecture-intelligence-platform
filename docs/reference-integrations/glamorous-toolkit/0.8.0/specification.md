# AIP × Glamorous Toolkit — v0.8 Contract Reference Experiment

**Status:** Draft 0.10 — specification only; owner confirmation and implementation pending  
**Date:** 2026-11-05  
**Experiment scope:** lightweight **pre-v0.9** investigation; does not define or qualify an AIP release  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 pre-wave-1 dataset

The `0.8.0/` directory names the **AIP contract consumed**, not a proposed new release. The existing hosted Sokol111 evidence is a starting point, not a complete answer to the scenario. Historical GT integrations remain unchanged.

## 1. Customer decision — introduce a new consumer

**Central question:** **What do existing autonomous service owners explicitly promise to a new consumer, under which conditions, and which further commitments must the consumer obtain or make before cooperation is viable? Can AIP + GT help an architect inspect and challenge those promises more effectively than source access alone?**

**Business scenario:** A merchant wants product listings on an external marketplace to reflect its shop catalog: initial product publication, product data, prices, availability, images, updates and withdrawals, with tenant isolation. **Orders, checkout and fulfillment are out of scope.** A new team proposes a **Marketplace Connector**. The connector and external marketplace are *proposed*, not existing Sokol111 services or observed bindings. No marketplace-specific policy or guarantee is assumed.

**Participant-facing task (keep separate from the researcher key):**

> A merchant wants to publish and maintain its shop's product listings on another marketplace without maintaining the catalog twice. A new consumer team needs to know **what the existing platform teams actually promise to provide**, under which conditions, what they explicitly do not promise, and what must be agreed before the new team can credibly offer listings to merchants. Investigate these commitments and their evidence. Recommend **proceed / conditional proceed / defer** and explain what each autonomous party must confirm or decide.

The participant needs ordinary e-commerce knowledge, not a prior mental model of Sokol111. Give a brief business/platform orientation but **no answer key, dependency diagram, owner-confirmation assumptions or predetermined route**.

### Investigation questions — derived from *Integration Beyond the Interface*

Use the **five consumer-journey questions** from the article as a framework for revealing, understanding and validating **local promises**. Do **not** make discovery of dependencies the main outcome.

| Article-derived question | Promise-centered investigation |
|---|---|
| **1. Why does this capability exist, and for whom?** | Which autonomous owner offers it, what business meaning and intended audience does that owner actually confirm, and which parts are merely documented or inferred? |
| **2. Can a consumer discover and understand what is offered?** | Which explicit promises cover product data, initial state, updates, removals and media? Under what scope, prerequisites, conditions and limitations are they offered? Which interface behavior is *not promised*? |
| **3. Is the consumer permitted to rely on it?** | What does the accountable owner actually allow about tenant, identity, purpose, permissions and delegated access? Is marketplace use within a confirmed promise, a proposed agreement, or unknown? |
| **4. Where does each party's responsibility begin and end?** | Which provider (+), consumer acceptance (−) and intermediary commitments apply? What can the proposed connector independently promise its merchants, and which needed provider promises remain absent, declined or unconfirmed? |
| **5. What allows cooperation to survive change?** | Which owners explicitly commit to compatibility, delivery/recovery, change notification or limits? What conditions must remain compatible, and which changes require a new agreement? |

Framing: [Daniel Kocot, *Integration Beyond the Interface* (adorsys TechRadar, 5 Nov 2026)](https://adorsys.com/en/techradar/integration-beyond-the-interface%20/). These are **questions adapted from the article**, not verbatim questionnaire items.

**Investigation output:** a compact, evidence-linked **promise/reliance picture**: established local provider offers, distinct prospective consumer acceptances and merchant-facing commitments, applicability limits, owner-confirmation status, observed/configured support and unresolved agreements. Existing bindings are supporting evidence for finding relevant promisers, not the product being evaluated. An unanswered owner question is not an assumed promise and a list of necessary conditions is not proof of sufficient end-to-end correctness.

**Experiment objective beyond writing the spec:** **update the relevant Sokol111 service-owned contract/documentation sources with capabilities expressed as locally attributable, owner-reviewed and explicitly confirmed promises.** The claims and their source of authority must remain in the corresponding Sokol111 repositories; AIP/GT read and qualify them, not authoritatively approve them. This requires the real Sokol111 owner's explicit review/acceptance (or documented decline), not an agent's inference or a Git commit alone. Because the connected account has read-only access to Sokol111, any actual owner-repository change and confirmation must be supplied via an owner-reviewed contribution route; this specification must not present that external step as already completed.

### Experimental questions, independent of the product doctrine

- **E1 — Qualified cooperation knowledge:** does AIP's qualified view of existing cooperation help an architect **find, distinguish and interpret the relevant owners' promises, their evidence and missing agreements**, compared with source-only investigation? More discovered bindings alone are not a success.
- **E2 — Inspectable local promises:** once actual Sokol111 owners have confirmed usable local promises, does contextual inspection of those offers, applicability conditions and independent consumer acceptances improve the integration decision? If the owner process is unfinished, E2 is **pending/untested**, never simulated as complete.

These are not the product doctrine's **H1 (customer decision value)** and **H2 (sustainable owner effort)**, which require target-customer validation. Obtaining genuine, local Sokol111-owner confirmation is an **explicit experiment deliverable**, but the owner may reject a proposed promise. E1 and exploratory GT work may proceed before E2 is ready; missing owner sign-off is a limitation for E2, **not** a reason to invent confirmation. Partial AIP v0.8 coverage is never a prerequisite for owner agreement.

## 2. Investigation and evidence discipline

**Start with local offers, then qualified evidence.** Ask what a prospective consumer needs each provider to promise before inspecting technical relationships. Owner-controlled Sokol111 sources establish the declaration and explicit confirmation; code, configuration and contracts may support or challenge the offered behavior. GT's bundled `GtLMcpClient` / `GtLMcpHttpTransport` uses AIP's read-only MCP; `get_binding_picture` can help locate established participants and assess existing scoped bindings, but **v0.8 must not be portrayed as a behavioral-promise registry**. AIP-qualified Current State, attributable Intent and investigator interpretation stay separate.

**Source-grounded candidate owners, not confirmed promises:** [Sokol111 workspace](https://github.com/Sokol111/ecommerce-workspace) describes a multi-tenant e-commerce platform with Catalog, Image and query services; contracts reside in provider-owned `*-service-api` repositories. Start with the **smallest set of owners relevant to listing publication and maintenance** (potentially Catalog, Image, Product Query and an applicable platform/broker owner); add more only if the investigation provides evidence. Do not predetermine which promises their owners will accept, infer a promise from the service name, or manufacture a platform owner.

**Prospective consumer boundary:** The Marketplace Connector has **no observed AIP binding or confirmed local acceptance**. Its candidate acceptance/use promises and potential merchant-facing commitments may be drafted for owner review, but are prospective. Provider owners can confirm, condition or decline offers independently; a consumer requirement cannot create a provider commitment. Never insert the proposed connector as observed Current State.

**Owner-confirmed promises are the key deliverable, not a source-code inference.** Document one minimal, versioned local carrier in the appropriate Sokol111 owner-controlled service/API repository, using existing documentation/contracts where sufficient. Only introduce an optional service-local `architecture/promises.yaml` if the owners find a separate carrier necessary. Do **not** require a centralized registry or impose a global template on autonomous owners. Each promise must identify its **promiser/owner; offered or accepted behavior; intended audience; scope and applicability conditions; material limits; effective version/interval; source; confirmation/decline status and review evidence** as applicable. Explicitly document non-offered guarantees only when the owner confirms those limits. A code commit or an agent-authored draft alone does **not** imply confirmation.

**A small two-stage owner workflow:** (a) investigate source and existing contracts to prepare **candidate** provider/consumer promises, with unresolved questions and possible evidence; (b) ask the **actual autonomous owner** to accept, revise or decline each promise and record that attributable decision in the owner-controlled repo or linked review/decision record. Publish only as **owner-confirmed** after this decision; keep remaining candidates labeled or out of the confirmed view. Recheck claims against qualified runtime/config evidence without treating agreement as proof the offered behavior currently holds. A refusal or absence of confirmation is a legitimate outcome, not a reason to force a promise.

**Investigate compatibility, not graph completeness.** The architect compares local provider offers (+), independent (possibly proposed) consumer acceptance (−), intermediary guarantees, and the connector's desired merchant-facing commitments. The useful findings are **incompatible conditions, unpromised reliance, missing scope/authority or necessary new agreements**. Source-only behavior (full-state product events, images, retries, tenant propagation, etc.) can motivate a candidate or a test, but must not silently become Intent.

**Promise qualification boundary:** Existing v0.8 EventCatalog `sends`/`receives` entries are **demo-assumed confirmed**, not owner decisions. Confirmed Sokol111 promises may be inspected from separately pinned service-owned sources even when current AIP does not ingest or assess them. Do not upgrade those sources to AIP-confirmed Intent, forge binding statuses or require new AIP capabilities merely to finish the scenario. Record the semantic coverage gap separately.

**Partial qualification is explicitly allowed.** The hosted Sokol111 v0.8 C1 binding picture establishes bounded broker attachments and demo-assumed `sends`/`receives`, not every application contract, identity, authorization rule, marketplace-specific promise, bootstrap guarantee or event-handling behavior. **This is not a blocker for this experiment.** Combine AIP-qualified premises with other pinned sources, label which question each source can and cannot answer, and log any AIP semantic/coverage gap as a result. Do not patch the AIP result, silently extend its snapshot, invent a positive assessment, or demand a new AIP tool/release as a prerequisite.

**Evidence freeze and parity:** Before the exploratory run, preserve the **hosted package ID, complete snapshot ID, capture time and exact AIP request/response scope** from the real endpoint; pin service/API/commons commit SHAs, raw broker captures, authored consumer-group mappings, context/boundary membership sources, EventCatalog and assumed-confirmation inputs, and applicable qualification rules. Supply the underlying sources to all baseline conditions. Keep recorded after-wave-1 captures separate from the hosted pre-wave-1 C1 evidence; any additional package needs its own identity and qualification. AIP projections may add deterministic qualification and provenance—not privileged access to undisclosed source facts.

**Evidence drill-down:** Resolve `binding-evidence:` refs through `get_binding_picture` in `mode: "evidence"` with the original snapshot, bounded context, environment and broker IDs; keep ref roles, 1–20-ref limits, unresolved refs and errors intact. Do not reinterpret `crossing` or `status` against an inferred context boundary, infer context membership from connectivity, or confuse a projection over existing services with the proposed consumer's future binding.

**GT remains small and promise-first:** implement one contextual Phlow/Lepiter investigation. Navigate **consumer need → possible promiser → locally confirmed offer or clearly labeled candidate → scope and conditions → evidence/qualified assessment → separate prospective acceptance → missing agreement or decision**. Existing AIP bindings can locate a potential owner or test an observation; topology is not the product. GT may link directly to a pinned Sokol111 promise source when v0.8 cannot represent it. Do not hardcode a solution path or fabricate a live promise feed.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Candidate promises and owner review** | Freeze the marketplace task, evidence manifest and independent rubric. Identify a minimal set of locally relevant Sokol111 capabilities; prepare candidate promises in service/API-owned sources and seek **actual owner confirmation, revision or documented decline**. | Candidate and owner-decision status are explicit; accepted promises have owner-attributable review evidence and pinned revisions. **Read-only access or pending owner review does not block E1**, but E2 stays pending/untested until confirmed sources exist. Incomplete AIP v0.8 qualification is not a blocker. |
| **2 — Inspect local commitments with GT** | One small Phlow/Lepiter investigation centered on confirmed local offers, conditions, prospective acceptance and unpromised reliance; use AIP-qualified existing bindings only where they add context. | An e-commerce architect unfamiliar with Sokol111 can inspect attributable service capabilities, distinguish promises from behavior and candidates, and identify a meaningful agreement or verification needed for the new consumer. |
| **3 — Compare and publish** | Compare with matched source-only / GT / direct-AIP baselines; independently verify promise attribution, findings, decision quality, unsupported commitments and effort. | An honest E1 result and E2 result **only if owner-confirmed promises exist**, with expected vs unexpected insights and owner-maintenance cost. Negative or inconclusive findings count; no customer-value claim. |

Do not substitute presumed authority for owner approval to keep a schedule. A service owner's decision (including decline) belongs to that service/team, not to AIP or the experiment author.

## 4. Evaluation — follow the consumer journey

**Separate task from key.** Give investigators only the business brief and reasonable platform access. Freeze an independent **researcher key** from pinned Sokol111 sources, AIP scope and known unknowns before developing GT views. Do not supply a catalog of expected services, hidden obstacles or preferred solutions inside the task or UI. Unexpected findings must be independently verified and recorded separately from anticipated key items; assess how they change the question or integration recommendation.

Score each investigation against the **same five article-derived questions from §1**, not against a preordained implementation:

| Article-derived question | Promise-related evidence of progress |
|---|---|
| **1. Why is it offered?** | Identifies the actual owner and **confirmed external capability/purpose/audience**, versus API existence and source-derived candidate intent. |
| **2. What may a consumer rely on?** | Correctly exposes the provider's stated behavior, limits, applicability and unknowns for listing creation, maintenance and withdrawal—never invents a completeness or delivery promise. |
| **3. May it legitimately be used?** | Finds attributable tenant, consumer, delegated-access and purpose conditions, or the **specific owner decision** still required. Reachability is not authorization. |
| **4. Who makes which commitments?** | Separates confirmed provider and intermediary offers, distinct prospective consumer acceptance, merchant-facing expectations and **material unpromised reliance**. |
| **5. Will promises remain compatible?** | Establishes owner-confirmed compatibility/change/recovery conditions where available; identifies necessary agreements and evidence to support the new consumer's proposed guarantees. |

**Evaluation outcome, not completeness theater:** Score **correctly attributed and scoped local promises, compatible/unsupported reliance, actionable missing agreements, material limits and evidence gaps, and the justified onboarding decision**. Count dependency findings only when they change a promise-related conclusion; do not reward topic/node counts. Separate false promise/permission claims, anticipated answer-key findings and **unanticipated independently verified promise-related insights**. Include owner-review and ongoing maintenance effort. A justified conditional proceed/defer may outperform an unsupported proceed.

**Fair comparison with identical underlying facts:**

| Condition | Purpose |
|---|---|
| Coding agent + pinned source/config/contracts/raw captures, **without AIP** | Whether ordinary engineering analysis already supports the consumer decision |
| GT + the same sources, **without AIP** | Whether interactive exploration itself helps |
| GT + the same sources **with AIP** | Whether AIP's qualified existing relationships and assessments materially improve discovery or interpretation of **local promises, their applicability and missing agreements** |
| Coding agent + those same sources **with direct AIP access** | Needed **before claiming GT adds value beyond direct AIP**; if omitted, GT-specific benefit is undetermined |

An optional evidence-linked report is a low-cost cross-check. Keep task, sources, model/assistance, and investigation budget as comparable as feasible. Qualifying evidence is a potential AIP contribution; withholding the raw inputs that produced that evidence is not.

**Interpretation gates:** E1 can succeed, fail or remain inconclusive with partial AIP coverage. **Only owner-reviewed, accepted Sokol111 declarations qualify as confirmed local promises for E2**; pending proposals, demo-assumed `sends`/`receives` and consumer wishes never do. E2 is pending/untested until enough genuine confirmations exist. AIP receives credit only when its qualified evidence materially improves promise interpretation or a decision beyond equivalent raw sources; source/GT-only gains are reported separately. A direct agent with AIP must be compared before claiming GT-specific value. Product doctrine H1 (customer decision value) and H2 (sustainable owner effort) still require target-customer validation.

## 5. Minimal deliverables

- This `specification.md` and aligned `README.md` / integration index.
- **Owner-controlled Sokol111 service/API changes:** minimal candidate local promise declarations, with real owner review/acceptance or decline and pinned commit/review references; report pending access/review honestly. No promise is pre-confirmed by this spec.
- After implementation only: small GT source export and one executable Lepiter investigation.
- A compact frozen task/key and evidence manifest; after evaluation, a brief comparison/outcome report with provenance and costs.

Work in `docs/reference-integrations/glamorous-toolkit/0.8.0/`. Retain the historical `0.4.2/` and `0.5.1/` integrations unchanged.

## 6. Non-goals and release boundary

No actual marketplace integration, synthetic owner confirmation, central approval/registry workflow, cross-system business-state verification, generic event/marketplace adapter, inferred authorization, product-ownership claim from a topic, dependency-map completeness exercise, GT graph platform, agent-driven code mutation or new AIP tool simply to make the experiment look complete. AIP supports qualified architectural premises; the architect and contextual tooling interpret and decide.

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
