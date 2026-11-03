# AIP × Glamorous Toolkit — v0.8 Contract Reference Integration

**Status:** Draft 0.3 — lightweight experiment, not implemented or qualified  
**Date:** 2026-11-03  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** `https://mcp.daip.io/mcp` — read-only, frozen Sokol111 v0.8 dataset  
**Purpose:** prepare the proposed AIP v0.9 contextual-tooling evaluation

This folder is named `0.8.0` for the **AIP contract consumed**. It does not promise an AIP v0.9 release. Previous GT reference integrations remain untouched.

## 1. One question, one investigation

**Can GT help an architect gain situational awareness of a distributed system, interactively explore its established and candidate boundaries, and understand which relationships matter to a proposed change—beyond what the same engineer could achieve without AIP or using AIP directly?**

Start with a concrete Sokol111 architecture/change question (for example, moving Catalog Management between brokers), **not** a replay of the v0.7/v0.8 agent/migration failures.

The intended experience is one continuous exploratory workflow:

1. **Orient:** start with a service or proposed change; navigate relevant services, topics, brokers, neighboring contexts and available evidence.
2. **Explore boundaries:** follow relationships in either direction; distinguish established context membership from *candidate* groupings and unknowns.
3. **Investigate implications:** identify relationships that may be affected, the actual documents/assumptions they challenge, evidence supporting each claim and outstanding owner/technical questions.

The goal is not another static nine-row binding table, a system-wide architecture database, or a new GT visualization framework.

## 2. Approach and evidence rules

**Use what exists first.** Start with GT's bundled `GtLMcpClient` / `GtLMcpHttpTransport` and the hosted v0.8 `get_binding_picture` query/evidence interface. Preserve `structuredContent`, the complete AIP answer, source scope, outcome, limitations and snapshot. Other existing AIP capabilities or accessible Sokol111 documents may be used where they are relevant and independently attributable.

**The dataset is not fixed.** Inspect whether the hosted C1 dataset supports a meaningful exploration of more than one established context and a real architectural question. If not, assemble a *separately identified*, reproducible Sokol111 dataset using traceable documentation/configuration and appropriately labeled observations. Capture source revisions and provenance. Do not invent source facts or mix snapshot-specific references; do not silently replace the public hosted data.

**Keep authority visible.** AIP owns qualified Current State, attributable promises, assessments and provenance. GT owns contextual views and investigator interpretation. A GT-selected group of services is a **candidate boundary**, not automatically a supported Bounded Context. AIP's `crossing` and `status` retain their original scope; never recompute an authoritative assessment for a speculative grouping.

**Preserve uncertainty.** For v0.8 `binding-evidence:` references, resolve with `get_binding_picture` in `mode: "evidence"` using the same snapshot, bounded context, environment and brokers. Keep promise, attachment and mapping references distinct; sort/deduplicate references and respect the 1–20-ref limit. Show unresolved refs/errors explicitly. Attachment does not prove event handling or delivery; authored mappings/producer declarations are not runtime observations; missing catalog coverage is not proof of absence.

**Stay small.** Build only the contextual Phlow views, simple domain objects and optional graph/list navigation that the chosen question needs. A single executable Lepiter story is sufficient. Do not import old customized GT images or local compatibility adapters.

## 3. Three increments

| Increment | Deliverable | Done when |
|---|---|---|
| **1 — Scenario + connection** | Pick one architect decision; list the evidence available in Sokol111; verify GT v1.1.657 can query the selected AIP MCP endpoint with full results. Decide whether a separately sourced dataset is actually needed. | A relevant investigation question, traceable sources and one working GT→AIP query exist. Any gap is explicit. |
| **2 — Interactive investigation** | Build the smallest GT exploration connecting selected service/change → neighbors → established/candidate boundaries → source-qualified evidence → change questions. Add one executable Lepiter narrative. | An architect can explore at least one nontrivial change question, follow its evidence and identify uncertainties without interpreting guesses as AIP facts. |
| **3 — Evaluate + publish** | Try the same bounded question using existing tools, GT without AIP, GT+AIP and (where practical) an agent using AIP directly. Re-run the GT slice in a clean image and summarize findings. | A short report records what GT+AIP actually adds, unsupported claims, missing evidence, setup/owner effort and whether the result is useful, inconclusive or negative. |

The increments are **thin, end-to-end steps**, not six separately qualified workstreams. Avoid further decomposition unless an observed blocker makes it necessary.

## 4. Evaluation

Use one or two specific architecture tasks with source-grounded answer keys: discover relevant relationships/boundaries, follow the evidence and explain implications/unknowns for the change.

Compare, where feasible:

| Approach | What it isolates |
|---|---|
| Existing docs / engineering tools | Current investigation capability |
| GT without AIP | Value of moldable exploration itself |
| GT + AIP | Incremental value of qualified distributed architecture context |
| Coding agent + AIP | Whether an additional GT layer is needed |

Record correctness, missed dependencies, confusion between established/candidate boundaries, unsupported conclusions, time/navigation effort and the effort to prepare/maintain the data. Keep comparisons fair about available source material and assistance; report negative or inconclusive results. **A public Sokol111 case study prepares a customer evaluation; it cannot prove AIP product value or real owner coordination savings.**

## 5. Minimal deliverables

- `specification.md` — this draft.
- `README.md` — brief setup, scenario/dataset choice, and status.
- GT source export plus an executable Lepiter investigation **when implemented**.
- A compact evaluation/reproduction note **when tested**.

Keep artifacts in `docs/reference-integrations/glamorous-toolkit/0.8.0/`. Do not change `0.4.2/` or `0.5.1/`.

## 6. Explicit exclusions and release decision

No rerun of previous migration/agent failure studies; no hardcoded architecture inference from a nine-row table; no automatic promotion of candidate boundaries; no new AIP/GT core capability, MCP tool, custom graph engine or autonomous permanent code mutation without evidence of need.

The proposed AIP v0.9 release remains **conditional**. If the existing v0.8 interface meets the experiment's needs, publish the reference integration independently rather than creating AIP-side work to justify a release.

## References

- [Proposed v0.9 roadmap](../../../../ROADMAP.md#v09--contextual-architecture-intelligence-integration-proposed)
- [AIP product doctrine](../../../product-doctrine-and-strategic-direction.md)
- [Hosted Sokol111 demonstration](../../../../examples/sokol111-demo/TRY_IT_HOSTED.md)
- [v0.8 binding-picture request schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-request.schema.json)
- [v0.8 binding-picture answer schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-answer.schema.json)
- [Prior GT reference integration](../0.5.1/README.md)
- [GT v1.1.657 release](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.657)
