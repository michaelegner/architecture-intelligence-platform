# AIP × Glamorous Toolkit — v0.8 Contract Reference Experiment

**Status:** Draft 0.4 — specification only; not implemented or qualified  
**Date:** 2026-11-03  
**Experiment scope:** lightweight **pre-v0.9** investigation; its results may inform a future AIP release, but do not define or qualify one  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 pre-wave-1 dataset

The `0.8.0/` directory identifies the **AIP contract consumed**. Historical GT integrations remain unchanged.

## 1. One architect question

**Can GT help an architect gain situational awareness of a distributed system, explore established and candidate boundaries, and understand which relationships matter to a proposed change—beyond what the architect can achieve without AIP or by using AIP directly?**

**Preferred Sokol111 scenario:** follow the accepted [Sokol111 demo specification](../../../specifications/evaluation/sokol111-v08-demo.md), especially its **optional next-wave question (`5B): “Who relies on Store Provisioning?”** Explore Store Provisioning's tenant-event dependents and the questions a subsequent broker change would raise. This reuses an established architectural decision context without reproducing historical migration failures.

The accepted demo distinguishes **hosted pre-wave-1 C1** from **recorded after-wave-1** evidence. Its after-wave-1 `answers-after.json` was queried for **Catalog Management**, *not* for Store Provisioning. GT must not present those answers as a Store Provisioning-scoped AIP projection or pretend that the hosted endpoint serves the after-wave-1 captures. Use the hosted C1 data for the initial connection and what it actually establishes; if interactive investigation of the next wave needs after-wave-1 or Store Provisioning-scoped answers, explicitly supply a separate reproducible dataset/query route (see `2).

Choose a different Sokol111 change question only if this one cannot support useful interactive exploration; record the reason **before implementing the views**.

The user workflow is one short investigation:
1. **Orient:** start with Store Provisioning or a proposed change, and navigate the relevant services, topics, brokers, contexts and evidence.
2. **Explore:** follow dependencies in either direction, distinguishing **established** bounded-context membership from **candidate** groupings and unknowns.
3. **Investigate:** determine which bindings matter to the change, what source assumptions they challenge, what supports each finding and which owner/technical questions remain.

A fixed nine-row table, re-running previous agent/migration failures and building a generic architecture visualization product are all out of scope.

## 2. Approach and evidence discipline

**Use existing tooling first.** Connect with GT's bundled `GtLMcpClient` / `GtLMcpHttpTransport`. Invoke AIP's existing read-only MCP tools and preserve complete `structuredContent`, outcome, source scope, limitations and snapshot. AIP `get_binding_picture` is the starting point; other existing queries may be composed only within their documented scope.

**Dataset is flexible, provenance is not.** Inventory what the hosted C1 answer, [accepted Sokol111 story](../../../specifications/evaluation/sokol111-v08-demo.md) and pinned Sokol111 sources support. The after-wave-1 evidence in the accepted demo is **recorded, not hosted or an existing Store Provisioning-scoped answer**. If the next-wave question needs a runnable cross-broker picture, build a separately identified, reproducible *read-only* Sokol111 package or local replay from traceable recorded captures/documents. Pin source revisions, broker IDs, capture times, mapping authorship, assumptions and snapshot IDs. Clearly identify whether evidence is observed, authored, recorded, illustrative or newly queried. No invented architectural facts, mixed snapshot-scoped refs or silent replacement of the public hosted dataset. Do **not** re-run historical migration failure experiments merely to prepare the dataset.

**Keep authority visible.** AIP owns qualified Current State, attributable promises, assessments and provenance. GT owns contextual navigation and investigator interpretations. An exploratory grouping is a **candidate boundary**, never automatically an established Bounded Context. Do not recalculate authoritative AIP `crossing` or `status` from a candidate grouping; do not reinterpret `NONE` relative to Catalog Management as a Store Provisioning boundary classification.

**Preserve uncertainty.** Resolve v0.8 `binding-evidence:` references through `get_binding_picture` in `mode: "evidence"`, not `get_evidence`. Reuse the exact original snapshot, bounded context, environment and broker IDs; keep promise/attachment/mapping ref roles distinct; deduplicate and sort the 1–20 requested refs. Show unresolved refs and errors. Broker attachment ≠ event handling or delivery; authored mappings and producer declarations ≠ observed traffic; missing catalog coverage ≠ absence of an agreement.

**Keep GT small.** Prefer basic Phlow inspectors, linked objects and one executable Lepiter investigation. Add a graph only if a concrete task requires it. Never import historical customized GT images or local gt4llm adapters.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Scenario, evidence + connection** | Select the Store Provisioning next-wave question (or document why not); inventory/pin sources, snapshots and dataset limitations; connect clean GT v1.1.657 to the applicable AIP MCP endpoint. **Freeze source-grounded task answer keys before increment 2.** | One concrete decision, independently checkable answer keys, a valid GT→AIP query and an explicit choice of hosted C1 versus separately identified data. |
| **2 — One interactive investigation** | Build the minimum GT navigation for selected service/change → dependents → established/candidate boundaries → qualified evidence → unanswered change questions, plus one executable Lepiter page. | Architect can explore the question, inspect evidence and distinguish facts, hypotheses and unknowns without upgraded claims. |
| **3 — Evaluate + publish** | Run feasible comparisons on the **prewritten** answer keys, reproduce the GT workflow in a fresh image and publish a short report. | Report records comparative findings, unsupported claims, setup/owner effort and a positive, negative or inconclusive result. **If a comparison is not run, state why in one line.** |

These are three thin steps, not separate feature workstreams. Add no infrastructure unless the selected architectural question requires it.

## 4. Fair evaluation

Before increment 2, write one or two **source-grounded answer keys**, pinned to the chosen evidence state and observation time. Include expected relationships, boundary membership and scope, which assertions are supported, and explicit unknowns. Base them on independently inspectable source records and the accepted Sokol111 demo where applicable; do not derive or change them to match GT's finished views. A different dataset requires its own pinned key.

Use the same bounded question across available conditions:

| Condition | What it tests |
|---|---|
| Existing documentation / engineering tools | What an architect can establish today |
| GT without AIP | Incremental value from contextual exploration itself |
| GT + AIP | Incremental value from qualified AIP context inside GT |
| Coding agent + AIP directly | Whether GT contributes beyond direct AIP use |

Assess correct relationships and boundary distinctions, omissions, unsupported claims, useful change questions, interaction/time cost and source/owner maintenance effort. Record differences in access and assistance. **Do not assert product value from a public demo.** A comparison may be infeasible; explicitly log the reason instead of treating it as a pass.

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
