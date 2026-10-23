# AIP v0.7.2 — Hosted Interoperability and Product-Boundary Qualification

**Status:** Proposed  
**Target:** `v0.7.2`  
**Baseline:** published and verified `v0.7.1`, plus the merged runtime-image security fix [#617](https://github.com/michaelegner/architecture-intelligence-platform/pull/617).  
**Scope authority:** [ROADMAP.md — v0.7.2](../../../ROADMAP.md)

## 1. Promise

v0.7.2 **qualifies the existing product**, rather than adding another architecture model or MCP tool.

**Product question:**

> With equivalent access to repositories, execution and distributed-system evidence, does adding AIP materially improve what a coding agent can establish, needs to inspect, or changes beyond a mature context engine alone?

The hosted product-validation system moves from **Pitstop to Sokol111**. Pitstop remains historical and regression material. **Unblocked is the fixed context-engine comparator for v0.7.2.** Use Unblocked's open-source [`context-engine-simulator`](https://github.com/unblocked/context-engine-simulator) as the **preferred I3 evaluation harness**, with a small adaptation of its default A/B workflow. It complements, rather than replaces, the real Unblocked setup.

**Release promise:**

> A coding agent can consume AIP's complete hosted six-tool, evidence-qualified Current State on Sokol111, and a controlled investigation shows where AIP adds distributed-architecture value—or does not—before v0.8 scope is finalized.

## 2. Constraints

- Preserve all six v0.7.1 read-only MCP contracts, REST parity, snapshot/context/evidence rules and honest `PARTIAL` / `NOT_ANSWERED` behavior.
- No new architecture-question class, seventh/discovery tool, new adapter, generic broker topology or AIP-owned cross-capability composition.
- The hosted edge stays anonymous/read-only only on allowed routes, with existing Host, method, payload-size and write restrictions. Hosted data and credentials must not be exposed by mistake.
- **Historical context is not established Current State.** A retrieved document, old runtime event, configuration hint or past capture cannot silently become a current observed relationship. Preserve evidence time, scope, provenance and uncertainty.
- No forced positive answer for each tool. Mapping and observation gaps are product facts, not fixtures to conceal.
- Use one meaningful coding task and a short record, not a benchmark framework or increment-specific spec collection.

## 3. I1 — Hosted six-tool deployment

### 3.1 Problem

The published v0.7.1 image exposes six tools, but the existing hosted Pitstop environment and its public-edge verification still reflect the earlier surface. In particular, `examples/pitstop-demo/hosted/verify_public_edge.py` has a **four-tool `PUBLIC_TOOL_ALLOWLIST`**; tool-count consistency must be updated rather than merely assumed.

### 3.2 Required outcome

Make all six v0.7.1 tools callable via the hosted read-only MCP edge. **I1 may run against the existing Pitstop dataset as an infrastructure step**: on that dataset, `get_api_consumer_usage` and `get_destination_consumers` have no accepted source and must return the appropriate typed non-answer, **not** invented positive evidence.

The actual **Sokol111 hosted switch belongs to I2**. I1's acceptance requires a working external answer and evidence drill-down for an already-supported Pitstop question; Sokol111-specific product claims are not made before I2.

### 3.3 Acceptance

- External MCP initialization and `tools/list` return exactly six tools; client calls traverse the public edge, not an internal shortcut.
- Update the public-edge allowlist and verification script to the six-tool contract; test permitted operations and rejection of disallowed route/method/Host/oversized requests.
- At least one supported hosted query and same-snapshot evidence lookup succeed. The two newly exposed tools may demonstrate correct typed refusal on Pitstop if no source exists.
- No graph writes, privileged administration or broader unauthenticated surface are exposed. Record deployment image digest/config revision and concise external smoke results.

## 4. I2 — Hosted Sokol111 evidence

### 4.1 Problem

Pitstop does not exercise the target distributed workflow. An agent comparison needs a realistic, reproducible Sokol111 world; repository assertions and inferred identities alone cannot qualify runtime or broker Current State.

### 4.2 Required outcome

Prepare and serve **one bounded Sokol111 dataset on the hosted instance**. Include only the declarations, runtime/deployment/broker/gateway observations and independent mappings relevant to the chosen task. Identify repository/configured facts separately from observed attachments/communications and from unresolved attribution.

Freeze the relevant source revisions, evidence context, capture times/windows, coverage and mapping decisions for repeatable interpretation. A replayed frozen capture establishes **what was true at its observation time**, not live present-tense behavior.

### 4.3 Acceptance

- A short scenario brief identifies the Sokol111 revision/repositories, one concrete change, relevant environment and architectural question.
- The **hosted** endpoint is switched to the reproducible Sokol111 inputs and verified after loading them; it is not only a local fixture.
- At least one relevant external relationship is supported by qualified evidence and drill-down; missing or conflicting support remains explicit rather than silently removed.
- A reload/replay of the chosen frozen inputs preserves the semantic answers, with documented location-bound snapshot-id effects. Record practical setup and refresh effort.
- No secrets enter the committed evidence, published responses or anonymous edge; no need to make all six tools return positive results.

## 5. I3 — Controlled context-engine comparison

### 5.1 Problem

A functional AIP connection is not evidence of distinct product value. A mature context engine may already retrieve useful architecture context from code, documentation, and execution.

### 5.2 Unblocked setup (required before the experiment)

- Create a usable **Unblocked account/workspace** and connect the **GitHub repositories relevant to the chosen Sokol111 change** through Unblocked's GitHub integration (Team Settings → Data Sources → GitHub). Obtain authorization for the selected repositories; avoid indexing unrelated/private data just to increase coverage. Confirm indexing/sync has finished sufficiently for the selected repository revisions.
- Install/configure the **Unblocked remote MCP server** in the chosen coding agent and authenticate it. For Claude Code, the documented command is `claude mcp add -s user --transport http unblocked https://getunblocked.com/api/mcpsse`, followed by OAuth login through `/mcp`. Verify the actual Unblocked tools connect and return a cited result grounded in the selected repositories. Do not commit OAuth tokens or personal credentials.
- Fix the **same Unblocked workspace, indexed sources, account permissions, agent model/settings and prompt** for both experiment arms. Record the source list, repository revision(s), indexing state/time and any additional organizational sources enabled. Do not let extra Slack/docs/issues access appear in only one arm.
- Configure the hosted **AIP MCP** separately. Verify its six tools and evidence drill-down on the frozen Sokol111 dataset. Enable AIP **only in the combined arm**; Unblocked remains enabled and unchanged in both. Ensure the baseline agent has no implicit access to AIP via shared MCP settings, prepared context bundles or previous chat history.
- Run one small **Unblocked-only smoke query** asking about the selected change and check the citations. If Unblocked cannot access the relevant indexed data, fix setup before comparing rather than interpreting missing setup as an AIP benefit.
- Record the exact tool versions/configuration and connections used, including whether Unblocked exposes `context_research`/`context_get_urls`.
- **Preferred harness: `context-engine-simulator`.** Reuse its isolated Git worktrees, task fixture, acceptance criteria, evaluation, attribution and HTML/JSON reporting. Its default baseline (no pre-gathering) versus enhanced (pre-gathering plus extra planning passes) measures the value of context preparation—not AIP. **Adapt both arms to perform the same Unblocked context-gathering and agent workflow**, with the same steps, prompts and budgets; make the **AIP MCP connection available only in the combined arm**. AIP use must be attributable to the additional tool access, not extra prework or a different planning path.
- Scope the adaptation to per-arm MCP availability and equivalent workflow, with a small regression check that the baseline cannot invoke AIP and both arms can invoke Unblocked. Avoid building a new benchmarking framework. If the simulator cannot support a fair comparison without disproportionate changes, document that constraint and use two isolated manual sessions with the same fixed inputs.

**Setup references:** [Unblocked GitHub integration](https://getunblocked.com/integrations/github/), [Unblocked MCP instructions](https://getunblocked.com/download/), [context-engine-simulator](https://github.com/unblocked/context-engine-simulator).

### 5.3 Required experiment

Run the **same bounded Sokol111 change** in two fresh coding-agent sessions:

1. **Baseline:** Unblocked connected and usable, **without AIP**.
2. **Combined:** the **same Unblocked setup** with AIP's qualified hosted MCP surface additionally enabled.

**Hold constant:** agent model/version/configuration, initial prompt/context card, repository commits, Sokol111 dataset/configuration and frozen evidence snapshot, execution permissions, tools other than AIP, context-gathering/planning workflow, and access to raw distributed evidence. **AIP is the only added capability.** Record unavoidable environmental differences and their effect; do not call an unfair run a controlled comparison.

Allow both sessions realistic source browsing and direct execution, including raw broker/runtime checks where available. Independent evidence, not either agent's story, is the ground truth.

### 5.4 Acceptance

Produce **one short comparison record** with:
- verified Unblocked account/MCP/GitHub indexing setup, fixed source scope and relevant raw-evidence access; simulator version/fixture (or documented manual fallback) and proof of equivalent arm workflows;
- external Services/components found or missed, evidence-qualified confidence and unsupported claims;
- **whether historical documents, old captures or retrieved organizational context were confused with established Current State**, and whether evidence time/coverage was preserved;
- what was left unresolved versus asserted; provenance and evidence drill-down actually used;
- concrete change in the next investigation, proposed implementation or rollout gate, including a possible **no additional value** result;
- source setup/mapping/refresh effort; tokens, time and cost only as secondary observations;
- whether the task's ordinary vocabulary naturally reached the right AIP query context.

Do not pre-authorize a new search/discovery capability. If natural navigation proves a serious blocker, record it for the owner checkpoint.

## 6. I4 — Product decision and lightweight release

### 6.1 Decision

The owner records exactly one of **CONTINUE / NARROW / INTEGRATE / DEFER / STOP**, based on supported architecture facts, useful investigation changes, preserved uncertainty and maintenance cost. The conclusion explicitly informs v0.8: keep safe cross-view synthesis in the context-engine/agent layer, and introduce AIP-owned composition only if the experiment shows a concrete semantic distinction that layer cannot safely preserve.

### 6.2 Release acceptance

- I1 external-edge verification, I2 hosted Sokol111 evidence, and I3 comparative record are complete enough to support the decision.
- Use the **lightweight v0.7.1 release path**: normal CI, security/dependency checks, applicable image/hosted smoke tests, version/changelog/release notes, owner GO, tag/publish and one concise verification record. Repeat affected qualification only if relevant behavior changes.
- Bind the record to the **exact merged release SHA and published image digest**; externally verify the hosted six-tool endpoint against **that same published artifact**, not a different local image.
- The already merged #617 update removes the base image's system pip and refreshes its pinned base. Verify pip absence and base/security results on the final release image. Any new or residual material security exposure requires an explicit **owner** acceptance or remediation before publication; do not recreate the fixed issue as a separate increment.
- The release record includes the owner product disposition, SHA/tag/digest, hosted revision, checks and major limits. No additional RC series or separate decision documents are required.

## 7. Exit criteria

v0.7.2 is complete when:

1. an external client reaches six read-only hosted tools under the verified public-edge restrictions;
2. the same hosted service serves defensible Sokol111 Current-State evidence for the bounded task, with faithful partial/unsupported outcomes;
3. a fair comparison establishes whether AIP actually changes the engineering investigation, **without confusing historical context with observed Current State**;
4. the owner records the product-boundary decision and resulting v0.8 scope guidance;
5. the verified published image, exact merge SHA, digest and hosted deployment correspond.

No seventh tool or new canonical semantics are required for success.

## 8. Decision register

| ID | Decision | Status |
|---|---|---|
| D1 | v0.7.2 is a six-tool interoperability and product-boundary checkpoint, not another architecture-question release. | Roadmap accepted |
| D2 | I1 may qualify six-tool hosting on Pitstop, including typed absence for the two newer source-dependent tools; I2 moves the hosted system to Sokol111. | Proposed clarification |
| D3 | Sokol111 is the forward demo; Pitstop remains regression/history. | Roadmap accepted |
| D4 | Unblocked is the **required** comparator. `context-engine-simulator` is the **preferred I3 harness**, adapted for identical Unblocked-based workflows with AIP enabled only in the second arm; a documented manual fallback is allowed. | v0.7.2 decision |
| D5 | No seventh search tool or AIP-owned cross-view composition is pre-authorized. | Roadmap accepted |
| D6 | #617 image-security remediation is baseline; the exact published digest is checked before hosted release. | Implemented / release verification pending |
| D7 | One owner product checkpoint decides what, if anything, AIP should own in v0.8. | Decided 2026-10-23: **DEFER** ([record](i3-comparison-record.md#owner-checkpoint-i4-defer)) |

## 9. Baseline carry-forward

Later versions may reuse v0.7.2's **verified hosted read-only access**, the reproducible Sokol111 evidence package and the bounded comparison result. They may **not** treat a past capture as ongoing Current State or infer that one successful task proves generic product superiority.

v0.8 may own only the smallest distributed boundary/composition semantics that this experiment shows the agent/context layer cannot preserve reliably; otherwise it should build on the existing qualified six-tool evidence.
