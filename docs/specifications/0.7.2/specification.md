# AIP v0.7.2 — Hosted Interoperability and Product Checkpoint

**Status:** Proposed  
**Baseline:** released v0.7.1 plus merged image-security fix [#617](https://github.com/michaelegner/architecture-intelligence-platform/pull/617) (`f71e1a0`), scheduled to ship in v0.7.2. Governing: ROADMAP.md v0.7.2.

## Product question

Does AIP add material distributed-architecture value to a coding-agent investigation beyond a mature context engine with comparable source, execution and raw-evidence access?

Use **Sokol111** as the realistic distributed system and **Unblocked** as the initial comparator, not a normative dependency.

## Increments

| Increment | Goal | Exit |
|---|---|---|
| **I1 — Hosted six tools** | Expose the complete read-only v0.7.1 MCP surface through the hosted edge | External client sees all six tools, obtains a scoped answer and drills into evidence; public-edge checks pass |
| **I2 — Sokol111 evidence** | Prepare a realistic, reproducible Sokol111 dataset for AIP | The selected questions have evidence-backed answers, including explicit partial, unresolved and insufficient results where appropriate |
| **I3 — Agent comparison** | Run one bounded Sokol111 coding task with **Unblocked alone** and **Unblocked + AIP** | Short records show relevant external components found or missed, unsupported claims, provenance, changes to next action, and mapping/refresh effort |
| **I4 — Decision and release** | Interpret results and ship v0.7.2 | Owner records **CONTINUE / NARROW / INTEGRATE / DEFER / STOP**, implications for v0.8, and verifies the published image and hosted endpoint |

## Ground rules

- Give both comparison arms comparable access to repositories, direct execution and raw distributed evidence. Do not make the baseline artificially weak.
- Prioritize architectural correctness and material investigation impact; measure time, tokens and cost only secondarily.
- Do not manufacture positive evidence to exercise every tool. Preserve capture time, incomplete coverage, uncertain Service mapping and provenance.
- Record whether the agent can reach relevant AIP query contexts naturally. A new discovery/search tool is **not** pre-authorized; treat navigation difficulty as an experiment finding.
- The six existing tools remain independent qualified views. Agent-side synthesis may be observed; AIP-owned cross-capability composition belongs to a later scope decision, not this release.

## Verification and release

Reuse v0.7.1 qualification where behavior is unchanged. I1 needs an external six-tool smoke test, same-snapshot evidence resolution and public-edge restrictions. I2 freezes only the data/config required for the chosen task. I3 needs one credible controlled comparison, not a benchmark framework.

I4 follows the **lightweight v0.7.1 release path**: normal CI/security checks, relevant image and hosted verification, owner go, publication and one short record. Requalify affected behavior if it changes; avoid repeating established campaigns for docs or unrelated dependency updates.

The v0.7.1 image-security follow-up is **already implemented on `main`** by #617: system pip is removed and the pinned Python base updated, resolving the recorded bundled-pip and OS-certificate findings in its scan. Treat this as part of the v0.7.2 baseline, not new I1–I4 work. Normal release security/image checks verify the final candidate; do not repeat the remediation unless a finding recurs.

## Out of scope

No new broker adapter, generic broker topology, architecture-question class, cross-capability AIP semantics, Intent, Assessment, or generic context-engine integration framework.

**Exit capability:** a mature context engine can use AIP's hosted six-tool evidence in one realistic workflow, and the comparison establishes whether the additional distributed Current State justifies its operational and mapping cost before v0.8.
