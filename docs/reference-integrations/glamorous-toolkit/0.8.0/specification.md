# AIP × Glamorous Toolkit — v0.8 Contract Reference Experiment

**Status:** Draft 0.5 — specification only; not implemented or qualified  
**Date:** 2026-11-03  
**Experiment scope:** lightweight **pre-v0.9** investigation; its results may inform a future AIP release, but do not define or qualify one  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 pre-wave-1 dataset

The `0.8.0/` directory identifies the **AIP contract consumed**. Historical GT integrations remain unchanged.

## 1. One architect question

**Can AIP + GT increase the likelihood that an architect discovers a *new, evidence-supported, change-relevant insight* while exploring a distributed system, compared with simpler representations or direct AIP access?**

**Promise-aware insight hypothesis:** Contextually and dynamically inspecting the **local promises (Intent)** of selected services, together with their observed/configured bindings and AIP's qualified assessments, helps architects notice reliance, missing agreements and uncertainty that they might otherwise overlook. This is a hypothesis to test, **not** an assertion that every available declaration is an owner-confirmed promise.

An *insight* is a finding or question that is **new to the investigating architect**, relevant to the proposed decision and grounded in traceable evidence. Mere additional nodes, clicks, attractive visualizations or unsupported interpretations do not count. The experiment may reveal unexpected questions rather than just confirm the predefined answer key.

**Preferred Sokol111 scenario:** follow the accepted [Sokol111 demo specification](../../../specifications/evaluation/sokol111-v08-demo.md), especially its **optional next-wave question (§5B): “Who relies on Store Provisioning?”** Explore Store Provisioning's tenant-event dependents and the questions a subsequent broker change would raise. This reuses an established architectural decision context without reproducing historical migration failures.

The accepted demo distinguishes **hosted pre-wave-1 C1** from **recorded after-wave-1** evidence. Its after-wave-1 `answers-after.json` was queried for **Catalog Management**, *not* for Store Provisioning. GT must not present those answers as a Store Provisioning-scoped AIP projection or pretend that the hosted endpoint serves the after-wave-1 captures. Use the hosted C1 data for the initial connection and what it actually establishes; if interactive investigation of the next wave needs after-wave-1 or Store Provisioning-scoped answers, explicitly supply a separate reproducible dataset/query route (see §2).

Choose a different Sokol111 change question only if this one cannot support useful interactive exploration; record the reason **before implementing the views**.

The user workflow is one short investigation:
1. **Orient:** start with Store Provisioning or a proposed change, and navigate the relevant services, topics, brokers, contexts and evidence.
2. **Explore:** select any relevant service or intermediary and inspect its *local* provider/consumer/runtime promises where available, their sources and confirmation status, and the relationships they may concern; distinguish established boundaries from candidate groupings and unknowns.
3. **Investigate:** navigate from a promise (or missing promise coverage) to qualified Current State and Assessment, then identify a newly recognized dependency, assumption, gap or owner/technical question relevant to the decision.

A fixed nine-row table, re-running previous agent/migration failures and building a generic architecture visualization product are all out of scope.

## 2. Approach and evidence discipline

**Use existing tooling first.** Connect with GT's bundled `GtLMcpClient` / `GtLMcpHttpTransport`. Invoke AIP's existing read-only MCP tools and preserve complete `structuredContent`, outcome, source scope, limitations and snapshot. AIP `get_binding_picture` is the starting point; other existing queries may be composed only within their documented scope.

**Dataset is flexible, provenance is not.** Inventory what the hosted C1 answer, [accepted Sokol111 story](../../../specifications/evaluation/sokol111-v08-demo.md) and pinned Sokol111 sources support. The after-wave-1 evidence in the accepted demo is **recorded, not hosted or an existing Store Provisioning-scoped answer**. If the next-wave question needs a runnable cross-broker picture, build a separately identified, reproducible *read-only* Sokol111 package or local replay from traceable recorded captures/documents. Pin source revisions, broker IDs, capture times, mapping authorship, assumptions and snapshot IDs. Clearly identify whether evidence is observed, authored, recorded, illustrative or newly queried. No invented architectural facts, mixed snapshot-scoped refs or silent replacement of the public hosted dataset. Do **not** re-run historical migration failure experiments merely to prepare the dataset.

**Promise Theory lens.** Promises are **local, voluntary commitments of autonomous participants**, not obligations deduced from a dependency. When an architect selects a service, GT should expose the promises *available from the chosen sources*: typed promiser (provider, consumer or intermediary), promised behavior, scope/counterparty, conditions and validity, source/carrier, confirmation status and corresponding Current State/Assessment **where these fields actually exist**. Keep confirmed promises, candidate declarations, assumed-confirmed demo catalog entries and missing coverage clearly distinct. Do not invent a promise, infer acceptance by the other party or imply a live promise feed merely because a view refreshes dynamically. If the hosted demo cannot support meaningful promise inspection, record that gap and use an explicitly labeled, source-grounded dataset where feasible.

**Keep authority visible.** AIP owns qualified Current State, attributable promises, assessments and provenance. GT owns contextual navigation and investigator interpretations. An exploratory grouping is a **candidate boundary**, never automatically an established Bounded Context. Do not recalculate authoritative AIP `crossing` or `status` from a candidate grouping; do not reinterpret `NONE` relative to Catalog Management as a Store Provisioning boundary classification.

**Preserve uncertainty.** Resolve v0.8 `binding-evidence:` references through `get_binding_picture` in `mode: "evidence"`, not `get_evidence`. Reuse the exact original snapshot, bounded context, environment and broker IDs; keep promise/attachment/mapping ref roles distinct; deduplicate and sort the 1–20 requested refs. Show unresolved refs and errors. Broker attachment ≠ event handling or delivery; authored mappings and producer declarations ≠ observed traffic; missing catalog coverage ≠ absence of an agreement.

**Keep GT small.** Prefer basic Phlow inspectors, linked objects and one executable Lepiter investigation. Add a graph only if a concrete task requires it. Never import historical customized GT images or local gt4llm adapters.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Scenario, evidence + connection** | Select the Store Provisioning question; check which *local promises* and qualifications are genuinely available; pin sources/snapshots and connect GT v1.1.657 to AIP. **Freeze source-grounded task answer keys and an insight-assessment rubric before increment 2.** | One relevant decision, independently checkable premises, a GT→AIP query and a documented dataset choice/limitations. |
| **2 — One interactive investigation** | Build the smallest context-sensitive GT exploration: selected service → available local promises → relevant bindings and assessments → evidence/limitations → follow-up questions, plus one executable Lepiter page. | Architect can navigate promises and relationships, discover potential insights and distinguish facts, candidates and unknowns without upgraded claims. |
| **3 — Evaluate + publish** | Compare against a simple evidence-linked table/report, GT without AIP and direct AIP access where feasible; reproduce in a clean GT image. | Short report records *supported new insights*, missed/false claims, decision relevance, investigation and maintenance effort, and positive, negative or inconclusive findings. **If a comparison is not run, state why in one line.** |

These are three thin steps, not separate feature workstreams. Add no infrastructure unless the selected architectural question requires it.

## 4. Fair evaluation

Before increment 2, write one or two **source-grounded answer keys**, pinned to the chosen evidence state and observation time, plus an **insight rubric**. Include known bindings, locally attributable promises (and confirmation gaps), boundary scope, qualified assertions and unknowns. Do not adjust the answer key to fit GT's implementation; a different dataset needs a separately pinned key. **Do not limit discoveries to the predefined answers:** separately record unanticipated insights and check them against independent evidence using the same prewritten rubric.

Use the same bounded question across available conditions:

| Condition | What it tests |
|---|---|
| Existing documentation / a simple evidence-linked table or report | Whether a simpler representation already suffices |
| GT without AIP | Incremental value from contextual exploration itself |
| GT + AIP | Incremental value from qualified AIP context inside GT |
| Coding agent + AIP directly | Whether GT contributes beyond direct AIP use |

Evaluate the **proportion of investigations yielding at least one new, independently supported, decision-relevant insight** (without claiming statistical significance from a small demonstration), alongside correctness, missed relationships or promises, unsupported claims, decision quality, navigation/time cost and promise/source upkeep effort. Record differences in access and assistance. **Do not assert product value from a public demo.** A comparison may be infeasible; explicitly log the reason instead of treating it as a pass.

## 5. Small deliverables

- `specification.md` — this draft and its three-step plan.
- `README.md` — scoped setup, baseline and status.
- GT source export + one executable Lepiter story **after implementation**.
- Compact evidence/answer-key and evaluation/reproduction report **when available**.

Work under `docs/reference-integrations/glamorous-toolkit/0.8.0/`; leave `0.4.2/` and `0.5.1/` unchanged.

## 6. Non-goals and release boundary

No re-running old migration/agent failures; no artificial proof of boundary ownership from graph clusters; no authoritative reinterpretation of bounded AIP answers; no new GT/AIP core capability, MCP tool, generalized graph engine or autonomous code mutation without an observed need.

This is an **independent reference experiment**, not a release qualification. If the existing AIP contract suffices, publish the result without creating AIP-side work to justify a new release.

## References

- [Accepted Sokol111 evaluation/demo specification](../../../specifications/evaluation/sokol111-v08-demo.md)
- [Hosted Sokol111 walkthrough (pre-wave-1)](../../../../examples/sokol111-demo/TRY_IT_HOSTED.md)
- [AIP product doctrine](../../../product-doctrine-and-strategic-direction.md)
- [v0.8 binding-picture request schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-request.schema.json)
- [v0.8 binding-picture answer schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-answer.schema.json)
- [Historical GT reference integration](../0.5.1/README.md)
- [GT v1.1.657 release](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.657)
