# Promise-bearing ADRs — Sokol111 demonstration only

Sokol111 is an **illustrative e-commerce codebase**, not a real customer whose service owners have accepted these commitments. These short Architecture Decision Records document **fictional decisions by modeled autonomous service roles**, with links to real source evidence where available.

| ADR | Modeled promiser | Demonstration status |
|---|---|---|
| [0001 — Product-change events](0001-catalog-product-change-events.md) | Catalog | `DEMO_ASSUMED_CONFIRMED` |
| [0002 — Image-promotion information](0002-image-promotion-information.md) | Image | `DEMO_ASSUMED_CONFIRMED` |

**An ADR is a decision record, not automatically a promise.** Each ADR's *offered/accepted external behavior and its conditions* is the demo promise, and its rationale explains why the modeled owner chose it.

**Status rules:** `DEMO_ASSUMED_CONFIRMED` means accepted **within the fictional experiment only**, not by real Sokol111 maintainers. `DEMO_PROPOSED` may be assigned to an investigator-authored decision **after** exploration, never to a consumer promise furnished as an input. These are **not AIP qualification enums**. Neither status is evidence that the real code works as described or that any real user is authorized. The existing AIP v0.8 C1 `sends`/`receives` assumptions remain separate from these ADRs.

**Authority boundary:** In an actual organization, each autonomous promiser would author, approve, change and retire its own ADR or other promise carrier. Here, the AIP reference integration holds a transparent **demo overlay**; it does not own a real Sokol111 promise or alter upstream repositories.

**Input versus output:** The two provider ADRs above are available **before** investigation. The merchant's **hypothetical 15-minute listing-withdrawal requirement** is also an input, but **no Marketplace Connector ADR, consumer acceptance, responsibility assignment or outward promise is supplied**. Each architect must independently decide whether compatible commitments can be proposed, by whom, and under which conditions—or explain why none is justified. An optional `DEMO_PROPOSED` consumer ADR is an **investigation output** to collect after completion, not a fixture to publish in this directory beforehand.

**Evaluation:** provide the same provider ADRs, business task and source/evidence to source-only, GT-only and AIP-enabled baselines. Compare the **independently produced** consumer decisions, including defensible decisions not to offer a guarantee. Do not pre-mark a failure as established or guarantee any solution. Pin source revisions and the AIP snapshot in the evidence manifest before interpreting results.

See the [reference experiment specification](../specification.md).
