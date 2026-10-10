# AIP v0.6.0 I3 — Completion Record

**Status:** **COMPLETE.** Closed by PR #408, merge `2f57b660c5a03cdd09c7fba8277670fb1d4b49c4` (2026-10-02T19:30:47Z). The closure SHA was written into this record by a follow-up PR, because a PR cannot record its own merge commit (the two-step closure pattern used for I1 and I2).
**Release / increment:** `v0.6.0` — Locality-Aware Current State / I3.
**Governing specification:** [I3 specification](i3-bounded-current-state-projection-and-public-answers.md) revision 0.2 (Accepted), merged in #382 (`82652f44b0f35f4349f94c5b5c62598a3d03bbd4`), with the tool-name proposal of #385 (`22782529ba3f6f8ba95e825283a0339ed91dd69a`). This record covers the whole of I3, slices I3.1–I3.4: the specification and tool-name PRs, 10 merged slice PRs, and this record.
**Not claimed:** I3 is not qualified as a final candidate, not released and not published. There is no final-candidate repeatability or two-clean-state qualification; that is I4. The real controlled I5 capture is **`NOT_RUN`**: the I2.6a recording replayed through I3 is a labelled **rehearsal**, not I5 evidence. Release qualification is I6.

## Run identity

Merge commits and times were read with `gh pr view --json mergeCommit,mergedAt` in the same command that listed them; none is typed. "Planning started" is the PR-body marker (`aip-agent-metadata:v1`).

| Slice | PR | Merge commit | Merged (UTC) | Planning started |
|---|---|---|---|---|
| I3 spec (rev. 0.2) | #382 | `82652f44b0f35f4349f94c5b5c62598a3d03bbd4` | 2026-10-01T08:00:07Z | — |
| Tool-name proposal | #385 | `22782529ba3f6f8ba95e825283a0339ed91dd69a` | 2026-10-01T08:37:50Z | — |
| I3.1a decision record D1–D15 | #386 | `c0672e39bd5f29783b6f69602e47422b6b5b6eb2` | 2026-10-01T09:57:22Z | 2026-10-01T08:00:42Z |
| I3.1b 0.6 contract models and schemas, D16 | #387 | `7578cbbfe1ca0036fe617369e2eea6f04bba8a6c` | 2026-10-01T15:19:08Z | 2026-10-01T08:00:42Z |
| I3.1c independent oracle and matrix | #388 | `2fa068e1e396fd1282f115624f915e8e86bdbc64` | 2026-10-01T17:44:03Z | 2026-10-01T08:00:42Z |
| I3.2a I2 read hooks, D17 | #393 | `db5589066d06b4280e75fef37b0fac3e9afb0190` | 2026-10-02T08:06:16Z | 2026-10-02T06:50:56Z |
| I3.2b projection and service method | #394 | `e4ee79a2c867d44754c917ec4841aa498d40e977` | 2026-10-02T08:45:02Z | 2026-10-02T06:50:56Z |
| I3.2c oracle on real Neo4j; snapshot row-order fix | #396 | `c13348937dcad524700e929a24ce6b8e1019d6f7` | 2026-10-02T11:47:37Z | 2026-10-02T06:50:56Z |
| I3.3a same-snapshot fix; scoped resolver | #398 | `8b2d87993841a50d890cf9f8428dbf6a6c5482a8` | 2026-10-02T12:58:13Z | 2026-10-02T12:00:31Z |
| I3.3b REST routes; fourth MCP tool | #403 | `601c4ad9f3192506a941b8a6602081c92048a304` | 2026-10-02T14:01:39Z | 2026-10-02T12:00:31Z |
| I3.3c cross-surface parity; independent client | #406 | `04bfd65e5b65a04d1abb198b062997c1c522297c` | 2026-10-02T14:47:42Z | 2026-10-02T12:00:31Z |
| I3.4a locality cost benchmark and recorded run | #407 | `40ccc29acb89d4d95228499fc97dd8b17f6d24de` | 2026-10-02T16:12:04Z | 2026-10-02T14:48:35Z |
| I3.4b this record and the I4 handoff | #408 | `2f57b660c5a03cdd09c7fba8277670fb1d4b49c4` | 2026-10-02T19:30:47Z | 2026-10-02T14:48:35Z |

Merged during I3 but outside its scope:
- #349 (UTC-day telemetry buckets) and #384 (landscape references);
- the Dependabot bumps #389–#392;
- the CI changes #395 (core integration sharding; rehearsal replays reused per state) and #397 (a separate `oracle` shard for `test_locality_oracle.py`), both from another session.

## Decisions frozen during I3

All are in the [decision record](i3-decision-record.md). Each settles an item that the accepted specification marked **[I3 proposal]**, and none reopens a parent, I1 or I2 semantic.

| Decision | Subject | Slice |
|---|---|---|
| D1–D2 | One new read-only tool, `get_service_dependencies_by_locality`, with `query` and `evidence` modes, and two POST routes. A new `0.6` locality envelope, not a widening of the closed 0.5 `ArchitectureAnswer`. | I3.1a |
| D3 | Query vocabulary. `caller_localities` is a post-evaluation filter, and `compare` must be a subset of it. `WorkloadIdentity` requires the captured UID. | I3.1a |
| D4–D7 | Bounds. A same-fence fan-out preflight with `k = min(500, ⌊2000/S⌋)`; fail closed at `S > 2,000` (D6); the D5 cursor; page-local, provisional groups (D7). | I3.1a |
| D8 | Operation → provider owner by the v0.5 evidenced-`PROVIDES` rule. No group qualification label. | I3.1a |
| D9–D10 | Outcome and limitation mapping (no positive is `NOT_ANSWERED` with data); the payload; selected-scope status (`EVALUATED_NO_POSITIVE` only through an `APPLICABLE` pair); the comparison | I3.1a |
| D11–D12 | The same-snapshot scoped resolver and its capture authority (owner decision). MCP top-level argument closure for the new tool only. | I3.1a |
| D13–D15 | Unchanged and deferred items; the parent §18 exposure table; the review cases R1–R8 | I3.1a |
| D16.1–D16.11 | Representation details of the published schemas. D16.4 (the provider filter narrows localities) and D16.11 (a continuation page is always `PARTIAL`) are owner decisions. | I3.1b, I3.1c |
| D17.1–D17.4 | Refusal precedence; caps count the presented projection (monotone `assess` prefix); lineage on a continuation page; the I2 read-hook shape | I3.2a |

## I3 Definition of Done (I3 §16)

| # | Requirement | Evidence |
|---|---|---|
| 1 | A client asks **where** a caller Service's direct HTTP CALLS are positively established, for an explicit environment and whole-day window, without giving Workload identities first | Oracle X01 (rehearsal C1: two caller Workloads, O1 `CONFIRMED`, O2 `OBSERVED_ONLY`) through `test_the_rehearsal_answer_matches_the_oracle` (#396). Over real HTTP against the production app: `test_independent_client_discovers_four_tools_and_drills_a_locality_answer_down` (#406). |
| 2 | The answer enumerates the bounded candidate/source inventory, all admitted pairs, positive Workloads and reasoned nonpositive candidates; unscanned or unrelated captures never become "no Pod" or "no dependency" | Oracle X10 (an unrelated capture is not a pair; a covering source's missing Pod stays a pair limitation), X13 (no cover) and X07 (no v2 is `NOT_ANSWERED` / `INSUFFICIENT_EVIDENCE`, not absence). P01–P03 walks: every candidate exactly once. All via `test_the_answer_matches_the_oracle` and the P tests (#396). |
| 3 | Exact source/revision and Workload-UID selection respects the I2 phase, temporal, no-cover and conflict rules; C1 and C2 are never interchanged | X08/X09 (phase-3 `INAPPLICABLE`, not prefiltered); X11/X12 (explicit and stale selector, D13.3); X14 (conflicting source not preferred); X03 and P08 (after C2, P1's record is `UNRESOLVED` and a C1 snapshot is refused). The disclosed P08 realization is below. |
| 4 | Each Operation keeps its I2 assertion/assessment identity, qualification, v2/declaration/capture refs, `UNKNOWN` target placement and `LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE` | Literal assertion IDs and every assessment field in the oracle answers X01–X19, matched exactly (#396). The projection copies I2 values unchanged (D16.3). |
| 5 | Unique provider ownership proved under the same snapshot; distinct Operations of one provider grouped without pooled qualification; missing or ambiguous owners stay explicit | X04 (one group, two members, `member_qualifications` both), X05/X06 (`PROVIDER_OWNER_MISSING`/`_AMBIGUOUS`, no provider, `PARTIAL`) and X18 (D16.4 filter). Unit: `test_one_provider_with_two_operations_is_one_group_without_a_pooled_label`, `test_an_unresolved_owner_keeps_the_operation_and_mints_no_provider` (#394). The `PROVIDES` rows are read in the same fence (D8, #393). |
| 6 | The schema defines explicit scopes, caps, truncation, lineage completeness and ordering; I2 truncation and I3 caps both mark lineage incomplete; the over-limit fan-out has the D6 disposition | P01 (`S = 5`, `k = 400`), P02 (I2 page boundary, two pages, one snapshot), P03 (Workload cap with `i2_truncated = false`) and X25 (`S > 2,000` refused before any candidate is read). Unit: cap prefix, monotonicity (`test_assess_is_monotone_in_the_candidate_prefix`), continuation lineage (D17.3). The published schemas pass both validators for every answer. |
| 7 | Two exact selected localities compared under one snapshot; targets within `caller_localities` or within the unfiltered inventory; a target beyond a cap gives an incomplete or refused comparison | X02, X14 (R5: `EVALUATED_NO_POSITIVE`), X15 (R4: invented identity `UNKNOWN`), X16 (R6b), X19 (`in_both`), P09 (R6: a `PARTIAL` inventory gives `UNKNOWN`); Q03/Q04 rejected requests |
| 8 | A same-snapshot, bounded, sanitized resolver for scoped refs; legacy readers stay isolated from v2, with negative tests | `resolve_scoped_locality_evidence` (#398). X26 (own v2 resolves; another caller's is `NOT_FOUND`), X27 (R8: declared, v1 and another caller's capture refs `NOT_FOUND`), X28 (stale snapshot), P05 (R7: capture refs resolve here, legacy `get_evidence` reports them missing), P06 (legacy `get_evidence`, `/api/evidence*` and the NL path return no v2). `test_an_owner_capture_ref_resolves_only_for_its_own_caller`; unit `test_every_not_found_entry_is_identical_but_for_its_ref`. |
| 9 | One reviewed, versioned contract through the service, REST and negotiated MCP; tool count and routes frozen; independent schema and client checks agree; old schemas and the three tools' meanings stay compatible | **4 tools; 2 routes** (`POST /api/services/{id}/dependencies/by-locality[/evidence]`), #403. `test_service_rest_and_mcp_return_the_same_answer` (X01–X28: REST body and MCP `structuredContent` equal the service answer, #406). `test_the_advertised_request_argument_is_the_published_request_schema` / `…output…` (#406). D12 is checked over the negotiated transport (`test_mcp_discovery.py`). The v0.5 frozen-schema tests and the v0.5 equivalence and golden-path suites pass; only their tool lists changed to four. |
| 10 | No-v2 snapshot and golden pins, legacy relations and dependency/drift/deployment/Pub/Sub, v1 counts and capture qualification unchanged; D16 not flipped | `test_one_snapshot_is_shared_with_the_v0_5_answers_and_no_v2_adds_no_state`, `test_the_locality_query_writes_nothing_and_leaves_v0_5_answers_unchanged` (#396), `test_with_a_mapping_artifact_every_read_still_shares_one_snapshot` (#398). The existing golden-pin and I2 vector tests pass unmodified. `telemetry.scoped-evidence.enabled` still defaults to `false`. |
| 11 | Bounded high-Pod-churn reads and cap/refusal behaviour measured with no invented SLOs; the exact HEAD's results recorded | [`i3-locality-cost.json`](i3-locality-cost.json) (#407, below), including covering fan-out at the 2,000-pair bound. Gate results below and in each PR body. |
| 12 | A completion record reconciling proposals, decisions and implementation, with limitations, deferrals, commands, SHAs and the I4 handoff; I5 stays `NOT_RUN` | This document and [`i3-i4-handoff.md`](i3-i4-handoff.md) |

## Check status

Each slice's PR body records its exact gate. This PR's gate, on the head it merges from:

| Check | Result |
|---|---|
| `uv run ruff format --check .` / `uv run ruff check .` | Clean (on `40ccc29` + this record) |
| `uv run pyright` | 0 errors |
| `uv run lint-imports` | 8 contracts kept |
| `uv run pytest tests/unit` | 3380 passed |
| `uv run pytest tests/integration` | 777 passed, 1 skipped (the QSH demo smoke test leaves an already-running local Compose project alone; CI runs it) |

CI runs the same checks plus CodeQL, Semgrep, `pip-audit` and the demo E2E job. The integration tests run in three shards: `heavy`, `oracle` and `rest` (#395, #397, I3.3c). Every I3 slice PR's CI check-runs succeeded at the head it merged from. This was read with `gh api …/commits/<head>/check-runs` for the exact head SHAs (`79152d8`, `07c8b0a`, `53b4dd3`, `3da7a83`, `d9ccebf`, `46b96b1`, `97c1496`, `21a4a53`, `49a6713`, `557c2de`); the only exception is the Copilot reviewer, which errored without reviewing.

## Measurements (I3 §14; [`i3-locality-cost.json`](i3-locality-cost.json))

One clean run of `benchmarks/locality_cost.py --profile i3` at `5f35843` in a fresh worktree (`dirty_worktree: false`). WSL2, 14 logical CPUs, 16 GB, Neo4j 5.26.31, Python 3.13.14. Medians of 5, in ms. Observed values only; no threshold is implied.

| Point | First page (candidates / admitted pairs / localities / memberships; k; caps) | Outcome | End to end | Fenced read | Owner lookup | Projection | Serialization | Evidence lookup | Cursor walk |
|---|---|---|---|---|---|---|---|---|---|
| churn, 2 Workloads, N = 0 | 0 / 0 / 0 / 0; k = 500; none | NOT_ANSWERED | 176.736 | 165.257 | 0.001 | 0.082 | 0.013 | 93.804 | 1 page(s), 0 candidates once each; 0 capped, 0 I2-truncated, 0 refusals |
| churn, 2 Workloads, N = 100 | 100 / 100 / 2 / 2; k = 500; none | ANSWERED | 141.229 | 130.748 | 4.493 | 3.168 | 1.234 | 168.493 | 1 page(s), 100 candidates once each; 0 capped, 0 I2-truncated, 0 refusals |
| churn, 2 Workloads, N = 1,000 | 500 / 500 / 2 / 2; k = 500; none | PARTIAL | 628.146 | 611.313 | 2.792 | 18.859 | 4.173 | 282.119 | 2 page(s), 1000 candidates once each; 0 capped, 1 I2-truncated, 0 refusals |
| Workload cap, 60 Deployments | 50 / 50 / 50 / 50; k = 500; WORKLOADS | PARTIAL | 119.44 | 68.659 | 2.469 | 39.911 | 0.71 | 48.3 | 2 page(s), 60 candidates once each; 1 capped, 0 I2-truncated, 0 refusals |
| membership cap, 201 Operations | 200 / 200 / 1 / 200; k = 500; MEMBERSHIPS | PARTIAL | 365.071 | 234.863 | 21.694 | 139.554 | 2.784 | 168.868 | 2 page(s), 201 candidates once each; 1 capped, 0 I2-truncated, 0 refusals |
| fan-out (non-pairing), S = 1, 500 Pods | 500 / 500 / 1 / 1; k = 500; none | ANSWERED | 519.612 | 608.632 | 1.92 | 14.769 | 5.348 | 155.616 | 1 page(s), 500 candidates once each; 0 capped, 0 I2-truncated, 0 refusals |
| fan-out (non-pairing), S = 5, 500 Pods | 400 / 400 / 1 / 1; k = 400; none | PARTIAL | 342.153 | 327.241 | 3.883 | 17.506 | 3.458 | 228.523 | 2 page(s), 500 candidates once each; 0 capped, 1 I2-truncated, 0 refusals |
| fan-out (non-pairing), S = 50, 500 Pods | 40 / 40 / 1 / 1; k = 40; none | PARTIAL | 172.168 | 155.68 | 2.134 | 1.39 | 0.241 | 1004.506 | 13 page(s), 500 candidates once each; 0 capped, 12 I2-truncated, 0 refusals |
| covering fan-out, S = 5, 400 Pods | 400 / 2000 / 1 / 1; k = 400; none | ANSWERED | 2426.41 | 2463.516 | 2.232 | 44.691 | 13.623 | 705.152 | 1 page(s), 400 candidates once each; 0 capped, 0 I2-truncated, 0 refusals |
| covering fan-out, S = 50, 40 Pods | 40 / 2000 / 1 / 1; k = 40; none | ANSWERED | 1894.318 | 1995.203 | 2.701 | 41.035 | 9.759 | 119.605 | 1 page(s), 40 candidates once each; 0 capped, 0 I2-truncated, 0 refusals |

- **Measured, not logged.** By owner decision, the per-phase costs are measured by calling each real function on its own; production code does not log them. The spec's "log" is read as "record", per D4.
- **The fenced read dominates.** It includes the full canonical snapshot state, and at the 2,000-pair bound it is almost all of the end-to-end time.
- **What the two fan-out families measure.** The non-pairing points measure the page-size reduction only. The covering points carry D4's real candidate × source work at its bound; they were added after the PR #407 review.
- **Not measured:** the `S > 2,000` refusal. 2,001 real imports take about 13 minutes, and oracle X25 executes that refusal with a disclosed clone of the generated captures.

## Reconciliation against the retained plans

Each slice's approved plan is kept verbatim in its first PR body: #386 (I3.1), #393 (I3.2), #398 (I3.3) and #407 (I3.4).

| Slice | Completed as planned | Deviations (disclosed in the PR, and why) |
|---|---|---|
| I3.1 | Decision record, draft schemas, independent oracle | Review rounds rebuilt D4/D6 as a pre-materialization preflight and defined D10's `EVALUATED_NO_POSITIVE` on `APPLICABLE` pairs (#386). D16.10 and D16.11 were added in review (#387, #388). |
| I3.2 | Hooks with D17; projection and service; the oracle on real Neo4j | **X25:** 3 of the 2,000 generated captures are imported for real and the rest cloned as `SourceState` capture properties; a test asserts the clone writer reproduces the importer's properties (owner decision). **P08:** C2 is imported over C1 from a copy that sets only `expectedPriorInventoryRevision`; the recorded envelopes are both first imports (owner decision; the fixture is unchanged). The execution status is matrix §6, not a §4 column, because the frozen §4 table is machine-parsed. |
| I3.3 | Same-snapshot fix and resolver; REST and the fourth tool; parity and the independent client | `golden_path.py` and the golden-path-pinned example docs (`cursor.md`, `vscode.md`, `hero-demo.md`) still list three tools. They are frozen release content, left for the I6 re-freeze; edits to them were tried and reverted after the pin test flagged them. The stale guard docstrings in `app/mcp/server.py` and `tools.py` were corrected (D12). |
| I3.4 | Benchmark (owner decision: measured, not logged), this record and the handoff | Covering fan-out points added after the PR #407 review, and the run re-recorded at `5f35843`. |

## Findings fixed during I3

| # | Finding | Fix |
|---|---|---|
| G1 | **Snapshot row order.** One Pod captured by two sources gave `deployment_captured_pods` rows with the same id. They were sorted by id only, so `snapshot_id` followed Neo4j's return order. Found by oracle P07. | #396: sort by the whole row; `test_a_pod_captured_by_two_sources_projects_in_one_order_whatever_the_read_order` |
| G2 | **Mapping artifact missing from the locality snapshot.** The I2 and I3.2 reads omitted the configured Path B mapping document, so with an artifact configured their `snapshot_id` differed from every v0.5 answer's. Found while planning I3.3. | #398: the document is a required keyword on both reads; `test_with_a_mapping_artifact_every_read_still_shares_one_snapshot` |
| G3 | **Oracle matcher.** A list binding contradicted by a later field was never replaced by an alternative order, so a valid binding could be rejected. Found in the PR #396 review. | #396: every ordering is yielded; `test_a_list_binding_that_a_later_field_contradicts_is_replaced` |

## Open findings and specification questions

| # | Item | Status |
|---|---|---|
| F1–F5 | Carried from the [I2 record](i2-completion-record.md): #323 (NL can read Kubernetes `Evidence`, independent of v2, which stays unreachable; P06), cross-run Workload incarnations, the scope-definition root change, the deferred D16 flip, the Operation-ID convention | Open as recorded there |
| F6 | **Four tools in the release golden path.** `examples/release-golden-path/golden_path.py` (`TOOLS`) and the pinned `examples/mcp-clients/cursor.md`, `vscode.md` and `examples/runtime-demo/hero-demo.md` still list three tools; the hero demo tells readers to expect three. | Deferred to the I6 golden-path re-freeze, with D16 |
| F7 | **One unreproduced integration failure.** During I3.3b one integration test failed once and did not recur on rerun. Its name was lost to truncated output; every later full run passed. | Recorded; no evidence of a defect |

## Deferred work (explicit, with owner)

- **I4:** final-candidate repeatability on two clean complete states; permutation and surface qualification of the exact final candidate. See the [handoff](i3-i4-handoff.md).
- **I5:** the real controlled capture, which is `NOT_RUN`.
- **I6:** the D16 default flip with the demo oracle's handling of `ScopedEvidence*` nodes; the golden-path four-tool re-freeze (F6); the ROADMAP reconciliation before the candidate freeze.
- **ADR 0012:** scoped-evidence retention and compaction stay unenacted.

## Handoff

[`i3-i4-handoff.md`](i3-i4-handoff.md) gives I4 the route/tool map, the frozen truth tables and their matching procedure, the case groups, the normalization procedure across surfaces, the pins, the measured cost and the deferred items.

## I3 exit statement

I3 turns I2's internal caller-Workload-local assessment into one bounded, deterministic, versioned public answer:
- **Where:** an ordinary client asks where a caller Service's direct HTTP dependencies are positively established, without naming any Workload first.
- **What it gets back:** the evaluated inventory of every candidate and admitted capture pair, the positive Workload localities with each Operation's own qualification and provider group, and an optional same-snapshot comparison.
- **Honesty about bounds:** bounds, continuation and every unknown, unresolved or excluded item are explicit.
- **Drill-down:** the scoped evidence behind an answer resolves at the same snapshot without widening the legacy evidence readers.
- **One answer everywhere:** the service, REST and negotiated MCP return byte-identical answers, and the advertised contract equals the published v0.6 schemas.

This is **caller** locality only. It establishes no target placement, exclusivity, global dependency or local absence. Every item of I3 §16 is supported by the executed evidence above, and the open findings and deferrals are listed explicitly. I5 remains `NOT_RUN`.
