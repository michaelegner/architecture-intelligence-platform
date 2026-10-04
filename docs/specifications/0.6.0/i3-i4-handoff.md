# AIP v0.6.0 I3 → I4 Handoff: the locality answer to qualify

**Status:** I3.4b deliverable (I3 spec §16, "Handoff to I4"). It lists what I3 built and froze, the independent truth tables I4 qualifies against, and how to run them. It claims no final-candidate qualification: an I3 run is not I4 evidence, and I4 reruns everything on the exact final candidate.
**Governing:** [I3 specification](i3-bounded-current-state-projection-and-public-answers.md) revision 0.2, the [decision record](i3-decision-record.md) D1–D17, the [expected-answer matrix](i3-expected-answer-matrix.md), and the [I3 completion record](i3-completion-record.md).

## 1. Public contract (frozen)

| Item | Value |
|---|---|
| Schema version | `0.6` locality envelope (`LocalityAnswer`), separate from the closed 0.5 `ArchitectureAnswer` (D2). Producer build version and schema version are separate. |
| Published schemas | `schemas/architecture_intelligence/v0.6/service-dependencies-by-locality-request.schema.json` (the MCP `request` argument, discriminated on `mode`) and `…-answer.schema.json`. Both are pinned byte for byte by `tests/unit/test_locality_contracts_schema_frozen.py`. |
| Contract models | `app/architecture_intelligence/locality_contracts.py` |
| v0.5 | `schemas/architecture_intelligence/v0.5/*` are unchanged; the three v0.5 tools and routes keep their meanings |

### Route and tool map (D1, D14)

| Mode | Service (sole semantic owner) | REST | MCP |
|---|---|---|---|
| `query` | `ArchitectureIntelligenceService.get_service_dependencies_by_locality(LocalityQueryRequest)` | `POST /api/services/{service_id}/dependencies/by-locality` | tool `get_service_dependencies_by_locality`, `request.mode = "query"` |
| `evidence` | `ArchitectureIntelligenceService.resolve_scoped_locality_evidence(LocalityEvidenceRequest)` | `POST /api/services/{service_id}/dependencies/by-locality/evidence` | the same tool, `request.mode = "evidence"` |

- **Tool count:** **four** read-only tools, in lexicographic `tools/list` order. `contracts.TOOL_NAMES` stays the three v0.5 names.
- **REST body:** closed. It is the published request minus `subject_service_id` (from the path) and `mode` (from the route).
- **REST status:** a malformed body is `422`; every evaluated or refused answer is `200` (D9).
- **MCP:** the tool rejects an unexpected top-level argument before dispatch (D12); the three v0.5 tools keep the SDK's ignore behaviour.

## 2. The independent truth tables

I4's expected answers are the I3.1c oracle, unchanged: [`i3-vectors/expected-answers.json`](i3-vectors/expected-answers.json).
- **Written independently:** it is produced by a stdlib-only author script that imports nothing from `app`.
- **Read-only:** an implementation that disagrees is fixed, or the disagreement goes back to the specification. The expectation is never edited (I3 §17 stop condition).

| Group | Cases |
|---|---|
| Two caller Workloads, the C1/C2 rehearsal (REHEARSAL – NOT I5) | X01, X02, X03, P08 |
| Unique owner and mixed-Operation truth table | X04 (one provider, two Operations, both qualifications), X05 (owner missing), X06 (owner ambiguous), X18 (provider filter, D16.4) |
| No v2, wrong day, wrong environment | X07, X08, X09 |
| Source selection and fan-out | X10 (unrelated capture, missing-Pod limitation), X11/X12 (explicit and stale selector), X13 (no cover), X14 (conflicting source), X25 (`S > 2,000` refused) |
| Complete versus partial enumeration | P01 (`k = 400`), P02 (I2 page boundary), P03 (Workload cap without I2 truncation), P04 (cursor misuse) |
| Selected-scope comparison and stale-snapshot negatives | X02, X14–X16, X19, P09; X24, X28, P04, P08 |
| Unsupported requests | X20–X23 |
| Scoped resolver: access and lineage | X26, X27, P05, P06 |
| Replay and permutation | P07 |
| Request validation | Q01–Q08 |

**Matching:** matrix §2 is normative. It covers literals, symbols bound once and injectively, spreads, the wildcard, pre-bound `SOURCE`/`REF` symbols, set matching for symbol-ordered lists, and the snapshot/model-revision digest rule. The reference implementation is `tests/integration/locality_oracle/matcher.py`, which has its own positive and negative tests in `tests/unit/test_locality_oracle_matcher.py`.

**Worlds:** `tests/integration/locality_oracle/world.py` builds each case's graph through the real importer and per-POST persistence. Matrix §6 discloses its deviations:
- the X05/X06 owner adjustments;
- the X25 capture clones, validated against real imports;
- the P08 predecessor-set copy of the recorded C2 envelope.

**Rehearsal identities:** `tests/fixtures/locality/rehearsal/identities.env` and the recorded C1/C2 envelopes (`SHA256SUMS` in the fixture).

## 3. Snapshot pins I4 must hold

- With no v2 records, the canonical snapshot has no conditional v2 keys, and every no-v2 pin, including the golden-path `expected_snapshot_id`, is unchanged (I2 D15).
- The locality answer, `assess_local_calls` and every v0.5 answer carry the **same** `SnapshotRef` for one graph. This holds with a configured Path B mapping artifact too: `test_with_a_mapping_artifact_every_read_still_shares_one_snapshot` (G2 in the completion record).
- The snapshot ID does not depend on database return order or on import order: `test_a_pod_captured_by_two_sources_projects_in_one_order_whatever_the_read_order` and oracle P07 (G1).

## 4. Cross-surface normalization procedure

For one graph and one request, all three surfaces must return the same answer:
- the service answer is `LocalityAnswer.model_dump(mode="json")`;
- the REST response body must **equal** it;
- the MCP `tools/call` `structuredContent` must **equal** it.

The only differences allowed are transport ones: the HTTP status and the MCP result wrapper (`isError: false`). Each surface's answer also validates against the published answer schema, and the advertised MCP `inputSchema.request` and `outputSchema` equal the published request and answer schemas after `$ref` resolution.

The I3 implementations of these checks are:
- `tests/integration/test_locality_surface_parity.py` (all 28 answer cases);
- `tests/unit/test_mcp_locality_contract_parity.py`;
- `test_independent_client_discovers_four_tools_and_drills_a_locality_answer_down` (httpx-only client over real HTTP, both modes, a reconnect).

## 5. Measured cost (baseline, not an SLO)

[`i3-locality-cost.json`](i3-locality-cost.json), summarized in the completion record.
- At the 2,000-pair bound (covering fan-out), one page takes about 1.9–2.4 s end to end on the recorded host, almost all of it in the fenced read.
- Pod churn of 1,000 caller Pods, with I2 truncation, takes about 0.6 s per page.

Re-measure with `uv run python -m benchmarks.locality_cost --profile i3` on the candidate host. Any threshold is I6's decision, not a value implied here.

## 6. What I4 must do

1. Rerun the frozen oracle (every answer and property case), the cross-surface parity and the independent-client checks on **two clean complete states**, on the **exact final candidate** commit, with the identity threaded explicitly as the release process requires. Do not reuse an I3 run.
2. Compare the two runs' normalized answers for repeatability, and the surfaces for parity, by the procedure in §4.
3. Hold the §3 pins.
4. Record the failures, skips and exact SHAs.

## 7. Deferred requirements (not I3, not I4)

- **I5:** the real controlled two-Workload capture, `NOT_RUN`. The rehearsal is not I5 evidence.
- **I6:** the D16 default flip of `telemetry.scoped-evidence.enabled`, with the demo oracle's handling of `ScopedEvidence*` nodes; the golden-path re-freeze to **four** tools in `examples/release-golden-path/golden_path.py` and the pinned `cursor.md`, `vscode.md` and `hero-demo.md` (completion record F6); the ROADMAP reconciliation.
- **Open findings:** I2's F1–F5 (including #323) and F7, as recorded in the completion record.
- **ADR 0012:** retention and compaction stay unenacted.
