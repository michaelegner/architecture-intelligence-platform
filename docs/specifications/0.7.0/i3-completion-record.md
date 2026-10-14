# AIP v0.7.0 I3 — Completion Record

**Status:** **COMPLETE.** Closed by PR #545, merge `24ffc12514df8ea19954d9dddf30625ca4f24b90` (2026-10-14T21:52:53Z). The closure SHA was written into this record after that merge (the two-step closure pattern, as for I1 and I2).
**Release / increment:** `v0.7.0` — API-Aware Current State / I3.
**Governing specification:** [I3 specification](i3-api-aware-current-state-projection-and-public-answer.md), merged in #529 (`bd870fd48b24fb3d228ace4d5df284cb105b2b33`), under the accepted parent [`specification.md`](specification.md). This record covers the whole of I3, slices I3.1–I3.4: the specification PR, seven slice PRs (I3.1a–c, I3.2, I3.3, I3.4a, I3.4b) and this record.
**Not claimed:** I3 is not qualified as a final candidate, not released and not published. There is no final-candidate repeatability or two-clean-state qualification of the release candidate; that is I4. The Tyk cross-check capture and the product-value pilot are I4. The golden-path and pinned-example re-freeze to five tools is the release slice.

## Run identity

Merge commits and times were read with `gh pr view --json mergeCommit,mergedAt` in the same command that listed them; none is typed. "Planning started" is the PR-body marker (`aip-agent-metadata:v1`) of each slice PR.

| Slice | Deliverables | PR | Merge commit | Merged (UTC) | Planning started |
|---|---|---|---|---|---|
| spec | I3 specification | #529 | `bd870fd48b24fb3d228ace4d5df284cb105b2b33` | 2026-10-14T13:52:11Z | — |
| I3.1a | [decision record](i3-decision-record.md) D1–D11 | #539 | `da82bc4213cdaa1fd34f628df7d87fffb04d5462` | 2026-10-14T15:13:29Z | 2026-10-14T13:52:47Z |
| I3.1b | `0.7` contract models and published schemas, D12 | #540 | `1ff3f64659ae1460c84d1d4dd33be2e8f5944863` | 2026-10-14T17:06:14Z | 2026-10-14T15:14:45Z |
| I3.1c | independent oracle and [matrix](i3-expected-answer-matrix.md) | #541 | `a0b81d19af46be7b3c22ec19e51bfa35c0f48e5a` | 2026-10-14T19:05:53Z | 2026-10-14T17:07:10Z |
| I3.2 | same-snapshot projection and service method | #542 | `4d797cf860b48b36e7ef0f055493ceccc9e3b6bc` | 2026-10-14T19:40:10Z | 2026-10-14T19:06:37Z |
| I3.3 | evidence mode, REST routes, the fifth MCP tool | #543 | `f700b28275a567d64cf0e2adf3b65cf6b557a05c` | 2026-10-14T20:42:25Z | 2026-10-14T19:40:43Z |
| I3.4a | read-cost benchmark, [recorded run](i3-api-usage-cost.json), repeatability test | #544 | `2094347387ab1461b0bff1371f3450fd23006d26` | 2026-10-14T21:40:33Z | 2026-10-14T20:44:47Z |
| I3.4b | this record, the [handoff](i3-i4-handoff.md) | #545 | `24ffc12514df8ea19954d9dddf30625ca4f24b90` | 2026-10-14T21:52:53Z | 2026-10-14T20:44:47Z |

## Decisions settled during I3

| Decision | Subject | Slice |
|---|---|---|
| D1–D2 | One new read-only tool `get_api_consumer_usage` with `query` and `evidence` modes, the service methods and two POST routes. A new `0.7` envelope, not a widening of the 0.5 `ArchitectureAnswer` or the 0.6 `LocalityAnswer`. | I3.1a |
| D3–D5 | Request vocabulary (exact target, exact gateway/environment/window, no ordering check so a reversed window stays addressable); the answer payload; the public vocabulary equal to the I2 values, unrenamed. | I3.1a |
| D6 | Closed limitation codes; the envelope invariant (`data` is null if and only if the answer is a refusal) and the refusal order snapshot, window, target, cursor. | I3.1a |
| D7–D8 | Source-qualified consumer name, no credential field; the opaque position cursor bound to snapshot and query. | I3.1a |
| D9 | Snapshot-bound evidence refs, five kinds with closed allow-listed payloads, and the rebuild-the-map evidence mode with no ref history. | I3.1a |
| D12.1–D12.13 | Representation details of the published schemas, including D12.13 (every kind's supporting-id set contains the id that distinguishes its payload). | I3.1b |
| Owner, I3.3 | One PR for the evidence mode, REST and MCP. Absent optional fields are **omitted** on the wire, never `null` (reversing the planning choice of `null` after the real-transport test, below). | I3.3 |
| Owner, I3.4 | Two PRs (benchmark, then record) and a closure PR, as in v0.6; cost is measured by calling each real phase, not logged by production code. | I3.4 |

## I3 Definition of Done (I3 §14)

| # | Requirement | Evidence |
|---|---|---|
| 1 | The frozen I2 handoff is consumed exactly, with `qualification_rows` as the row authority and no duplicate I2 reasoning | The projection copies and enriches the window's `qualification_rows` and recomputes no status, coverage or count. The oracle worlds are the exact handoff state and `test_the_reconciliation_sections_equal_the_i2_rule_applied_to_the_raw_facts` and `test_the_qualification_sections_equal_the_i2_rule_applied_to_the_raw_facts` check them against `reconcile` and `qualify`; `test_the_answer_is_projected_from_the_fingerprinted_snapshot` compares the real answer's rows with the stored rows field by field |
| 2 | A client queries by Operation, application Service or gateway Route for one exact gateway/window | Oracle A08 (Operation), A09 (Service), A01–A07 (Route), A14/A14b (two gateways) |
| 3 | An absent window is the typed `MEASUREMENT_WINDOW_NOT_AVAILABLE` refusal, not configured-only synthesis | A13 (`data` null); `test_a_window_is_never_substituted` |
| 4 | Window validity and selected-Route coverage stay visible with no rows | A11 (unsettled end), A20 (reversed window), A12 (selected Route, no pair rows) |
| 5 | Configured access and usage stay independent propositions | A01–A05; the row validators of D12.6 |
| 6 | Unresolved, ambiguous and conflicting associations stay explicit | A06, A07, A08/A09 summaries (all five counts), A19 |
| 7 | Measured zero only when I2 established it | A02, A03 (unestablished, not zero), A05; D12.6 row guards |
| 8 | Unattributed traffic never becomes a consumer row | A10; the `unattributed` world carries the unattributed series and an `UNRESOLVED` attribution |
| 9 | Consumer source names are exposed without any credential | C01 (property); `test_the_credential_canary_never_reaches_an_answer`; `test_the_canary_is_in_no_rest_transcript` and the MCP transcript in `test_v070_i3_adapter_oracle.py`; V14/V15 reject a Cypher or credential field |
| 10 | Pagination is deterministic and snapshot-bound | A15a–e, A15, A16, A17; `test_a_page_never_exceeds_its_limit_and_the_pages_cover_the_selection_once`; the recorded cursor walks (below) |
| 11 | Every returned ref resolves under the same snapshot or refuses explicitly | E01a–c, E02a–c; `test_every_ref_a_query_emits_resolves_in_the_same_context`; `test_every_emitted_ref_resolves_on_every_surface_and_a_forged_one_does_not`; `test_independent_client_runs_an_api_usage_query_and_resolves_its_evidence` |
| 12 | Service, REST and negotiated MCP return equivalent semantic payloads | `test_api_usage_surface_parity.py` (service == REST == MCP on a real import, each valid under the published schema); `test_v070_i3_adapter_oracle.py` (every oracle case through both adapters); `test_two_clean_states_give_identical_answers_on_every_surface` |
| 13 | Existing Architecture Intelligence tools retain their meanings | The four existing tools, the `/api/services/*` and `/api/evidence/*` routes and the v0.5/v0.6 schemas are untouched; the OpenAPI snapshot changed by additions only; `test_mcp_discovery.py` and the independent-client and transport tests now list five tools in lexicographic order with the four unchanged |
| 14 | Independent positive and negative expected outputs pass | The 57-case oracle (32 answers, 3 properties, 22 request cases) is executed by `test_v070_i3_projection_oracle.py`, `test_v070_i3_adapter_oracle.py` and `test_v070_i3_expected_answers.py`; the author is stdlib-only and imports nothing from `app` |
| 15 | No public write, generic graph query, Intent or policy judgment | The tool is read-only; its argument and request models are closed; no Cypher-like or credential field exists (V14, V15); no authorization or policy field exists in the answer |
| 16 | The I4 handoff contains the exact schemas, vectors, routes and tool names, fixture identity and known limitations | [`i3-i4-handoff.md`](i3-i4-handoff.md) |

## Check status

Each slice's PR body records its exact gate. For the slice PRs the CI check-runs were read through the GitHub API against the exact head SHA each merged from (`commits/<sha>/check-runs`, not `gh pr checks`), on 2026-10-14. At those heads every non-skipped check-run succeeded: `lint + test`, both `integration-core` shards, `demo-e2e`, `quality`, CodeQL, Semgrep and `pip-audit`. The `integration-qualification` shards were skipped by the path filter on #539, #541 and #542 and ran, and succeeded, on #540, #543 and #544. The CI run on `main` for #544 was still in progress when this record was written and is not claimed.

| Check (head of #544, the last code change) | Result |
|---|---|
| `uv run ruff format --check .` / `uv run ruff check .` | Clean |
| `uv run pyright` | 0 errors |
| `uv run lint-imports` | 10 contracts kept |
| `uv run deptry .` | No issues |
| `uv run pytest tests/unit` | 4578 passed |
| `uv run pytest tests/integration -m "not qualification"` | 832 passed, 1 skipped, 114 deselected (run before the image-pin fix, which changed no test) |

The I3.4b PR (#545) changed documentation only; its own gate is recorded in its PR body.

## Measurements (I3 §13; [`i3-api-usage-cost.json`](i3-api-usage-cost.json))

One clean run of `benchmarks/api_usage_cost.py --profile i3` at `6281dd7`, the benchmark's own committed head in the I3.4a branch (`dirty_worktree: false`), in the same worktree that built it. WSL2, 14 logical CPUs, 16 GB, Neo4j 5.26.31, Python 3.13.14. Medians of 5, in ms. Observed values only; no threshold is implied. Every point has `rows_equal_the_bounded_union: true`, no stable-read retries, at most 200 rows per page and 20 refs per evidence request, all resolved.

| Point (consumers / Routes) | Qualification rows | `consumers × routes` | Pages walked | Outcome | End to end | State read | Fingerprint | Projection | Serialization | Evidence mode (20 refs) | Ref map |
|---|---|---|---|---|---|---|---|---|---|---|---|
| service target, 20 / 10 | 100 (configured 100, observed 20) | 200 | 1 | ANSWERED | 160.981 | 163.794 | 2.987 | 5.944 | 3.339 | 122.563 | 0.572 |
| service target, 100 / 20 | 1,000 (configured 800, observed 300) | 2,000 | 5 | PARTIAL | 221.039 | 127.976 | 19.52 | 52.784 | 3.159 | 166.883 | 4.66 |
| service target, 500 / 50 | 5,000 (configured 4,500, observed 1,000) | 25,000 | 25 | PARTIAL | 731.242 | 328.35 | 133.744 | 297.166 | 5.81 | 528.446 | 35.749 |
| service target, 1,000 / 100 | 10,000 (configured 9,000, observed 3,000) | 100,000 | 50 | PARTIAL | 1597.4 | 657.979 | 289.56 | 545.442 | 3.81 | 1003.4 | 50.954 |
| Route target, 200 / 20 | 110 of 2,200 in the window (configured 2,000, observed 400) | 4,000 | 1 | ANSWERED | 202.254 | 148.838 | 40.336 | 4.494 | 1.763 | 215.599 | 0.593 |
| invalid window, 100 / 20 | 800 (configured 800, observed 100) | 2,000 | 4 | PARTIAL | 153.441 | 86.324 | 22.15 | 37.986 | 3.295 | 113.004 | 3.418 |

- **Bounded, not Cartesian.** At 10,000 rows `consumers × routes` is 100,000; the rows are the union of the configured and the observed pairs at every point (observed pairs on consumers that are not allow-listed add rows beyond the configured ones). Every cursor walk saw each row exactly once.
- **Measured, not logged.** By owner decision, each phase is timed by calling the real function on its own; production code does not log timings.
- **The whole-state read is a floor.** The answer is projected from the canonical snapshot state that is fingerprinted, so every request pays that read (ADR 0011); at 10,000 rows it is about 0.66 s of 1.6 s.
- **Projection is not paged.** The projection builds the public form of every selected row and sorts them before it takes a page, so its cost follows the selection, not the page: about 0.55 s at 10,000 rows for a 200-row page, repeated on each page of a walk (F1).
- **Evidence mode** rebuilds the finite ref map for the whole selection on each call (about 51 ms at 10,000 rows), and pays the state read as well.
- **Not measured:** unrelated graph growth beyond the imported sources (the v0.4.1 snapshot read-cost benchmark covers that dimension), and multi-gateway scale.

## Reconciliation against the retained plans

Each slice's approved plan is kept verbatim in its PR body: #539, #540, #541, #542, #543 and #544.

| Slice | Completed as planned | Deviations (disclosed in the PR, and why) |
|---|---|---|
| I3.1 | Decision record D1–D11, `0.7` models and published schemas with D12, independent oracle and matrix | #541 needed two review rounds on the oracle's input boundary (G1, G2). The oracle gained case ids beyond D11's list (A14b/c, A15a–e, A18a/b, A20, E01a–c, E02a–c) and a reversed window is an accepted answer case (A20). |
| I3.2 | Pure projection, thin service method, oracle executed against it | None. All 26 query cases and the property cases passed on the first execution. |
| I3.3 | Evidence mode, REST routes, fifth tool, parity, five-tool test updates, docs | Absent fields omitted instead of `null` (G4, owner decision); the REST routes document their 200 by pointing at the published schema instead of a typed response model (G5); an adapter-level oracle test was added to honour matrix §7. |
| I3.4 | Benchmark, recorded run, repeatability test, this record, the handoff | The first recorded run was invalid and was redone at a new head (G6). |

## Findings fixed during I3

| # | Finding | Fix |
|---|---|---|
| G1 | **Oracle input boundary.** The case worlds were an author abstraction (`routes[]`, `pairs[]`), so I3.2 would have needed a translator that re-decides the semantics under test. Review of #541. | #541: each world serializes as the exact handoff snapshot state (`gateway_configuration_v1`, `api_usage_v1`, `api_contracts_v1`, `operations`, `services`); the test checks the raw columns against the repository queries. |
| G2 | **Route-wide codes without their series.** `GWM_COUNTER_DECREASED` and `GWM_UNATTRIBUTED_UPSTREAM` were stated in `coverage` without the raw series that produce them, and the test injected series to compensate. Second review of #541. | #541: the worlds carry a decreased upstream series and an unattributed upstream series with an `UNRESOLVED` attribution, and `reconcile`/`qualify` run on the world as serialized. The only answer change was `A03` gaining the pair's `interaction_id`. |
| G3 | **A world contradicting the I2 rule.** `other-route` was stated as target-resolved with no Route label or mapping. Found by the cross-check of G1. | #541: the label was added; no expected answer changed. |
| G4 | **`null` for an absent field is invalid under the published schema.** The planning choice was `null` on the wire; the independent client, validating against the advertised `outputSchema`, rejected `association_summary: null` (a presence rule). Found by the real-transport test in #543. | #543 (owner decision): the 0.7 models drop `None`-valued fields on serialization except the required nullable `data` and `snapshot`; the published schema files did not change. |
| G5 | **OpenAPI component-name collision.** The 0.7 answer models share class names with the 0.5/0.6 ones (`Coverage`, `RuleRef`, `EvidenceEntry`); declaring one as a FastAPI response model renamed existing components. | #543: the routes use `response_model=None` and document their 200 by the published schema; the OpenAPI snapshot diff is additions only. |
| G6 | **A guard that scans tracked files.** `tests/unit/test_image_pins.py` requires a literal image in every `Neo4jContainer(` call. The benchmark was untracked when the unit tier first ran, so the guard failed only after it was committed. | #544: the image became a literal and the recorded run was re-made at the new head. |

## Open findings and limitations

| # | Item | Status |
|---|---|---|
| F1 | **Each page projects the whole selection.** The projection builds and sorts every selected row's public form before paging, so a full walk of N rows costs about N/200 projections of N rows (about 0.55 s per page at 10,000 rows). Found by the I3.4a measurement. | Open; a behaviour-preserving change (page, then enrich) for a separate reviewed PR. Not a correctness defect |
| F2 | **Every request reads the whole canonical state.** The answer is projected from the fingerprinted state, which keeps the snapshot and the answer consistent and makes cost follow the whole graph (ADR 0011). | Recorded; no cache or optimisation is introduced |
| F3 | **Evidence mode rebuilds the ref map for the whole selection** per call (bounded by I2's qualification row universe) and reads the whole state. | Recorded; consistent with D9 (no ref history) |
| F4 | **Five tools in the release golden path.** `examples/release-golden-path/golden_path.py` (`TOOLS`), `expected.json` and the pinned `examples/mcp-clients/cursor.md`, `vscode.md`, `examples/runtime-demo/hero-demo.md`, the README, the CHANGELOG release text, `examples/pitstop-demo/TRY_IT_HOSTED.md` and the runnable-demo paragraph of `docs/mcp.md` still say four tools. They are frozen release content. | Deferred to the v0.7 release slice, with the re-freeze |
| F5 | **The REST routes have no typed response model in OpenAPI** (G5). The contract is the published JSON Schema and the MCP `outputSchema`. | Recorded; renaming the 0.7 models would be a reviewed schema amendment |
| F6 | **Any import that changes the snapshot invalidates an in-flight cursor** (spec §8). The client restarts explicitly. | Accepted v0.7 limitation |
| F7 | **`interaction_id` is a row-local opaque value** that no evidence mode resolves (D4). | By design |
| F8 | **Carried from I2:** the recorded stable seconds are the capture tool's attestation; there is no restart or counter-reset inference; the environment is operator-asserted; one window per `(gateway_instance_id, environment)` and no history. Consumer names are source-qualified APISIX identities, not application or person identities. | Recorded; see the [I2 record](i2-completion-record.md) |

## Deferred work (explicit, with owner)

- **I4:** the two-clean-state, exact-final-candidate rerun of the oracle, the cross-surface parity and the independent-client checks; the Tyk cross-check capture; packaging; the product-value pilot. See the [handoff](i3-i4-handoff.md).
- **I5:** the release candidate, publication and verification, including the F4 re-freeze (golden path to five tools and the pinned example text).
- **v0.7.1:** broker-mediated consumer attribution.
- **Separate reviewed change:** F1.

## Handoff

[`i3-i4-handoff.md`](i3-i4-handoff.md) gives I4 the route and tool map, the frozen schemas and vectors with their matching procedure, the fixture identity, the normalization procedure across surfaces, the pins, the measured cost and the deferred items.

## I3 exit statement

I3 turns I2's internal configured-vs-observed qualification into one bounded, deterministic, versioned public answer:
- **What:** an ordinary client asks which consumers have configured access to, and which have observed usage of, an API Operation, an application Service or a gateway Route, for one exact gateway instance, environment and measurement window.
- **What it gets back:** each consumer×Route row keeps configured access and usage as separate propositions with the I2 coverage, counts and limitations, with the Route's Operation and Service associations explicit and independent, and the window's validity and each selected Route's coverage visible even when no row is returned.
- **Honesty about absence:** an unknown window, an unknown target, a stale snapshot and a foreign cursor are typed refusals, never an empty success; unattributed traffic and rejected attempts never become consumers or usage.
- **Drill-down:** every returned ref resolves at the same snapshot to a closed, sanitized payload, and no other ref does.
- **One answer everywhere:** the service, REST and negotiated MCP return the same answer, the advertised contract equals the published `0.7` schemas, and the 57-case independent oracle passes through all three.

It establishes no authorization, approval, intent, policy compliance or application ownership, and adds no write, graph query or credential exposure. Every item of I3 §14 is supported by the executed evidence above; the open findings and deferrals are listed explicitly. The final-candidate qualification remains I4–I5.
