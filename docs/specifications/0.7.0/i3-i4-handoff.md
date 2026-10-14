# AIP v0.7.0 I3 → I4 Handoff: the API-aware answer to qualify

**Status:** Frozen (merged #545). I3.4b deliverable (I3 spec §13, "I3 → I4 handoff with frozen public vectors"). It lists what I3 built and froze, the independent truth tables I4 qualifies against, and how to run them. It claims no final-candidate qualification: an I3 run is not I4 evidence, and I4 reruns everything on the exact final candidate.
**Governing:** the [I3 specification](i3-api-aware-current-state-projection-and-public-answer.md), the [decision record](i3-decision-record.md) D1–D12, the [expected-answer matrix](i3-expected-answer-matrix.md), the [I3 completion record](i3-completion-record.md), the parent [`specification.md`](specification.md) §5, and the frozen [I2 → I3 handoff](i2-i3-handoff.md).

## 1. Public contract (frozen)

| Item | Value |
|---|---|
| Schema version | `0.7` envelope (`ApiConsumerUsageAnswer`), separate from the closed 0.5 `ArchitectureAnswer` and the 0.6 `LocalityAnswer` (D2). Producer build version and schema version are separate. |
| Published schemas | `schemas/architecture_intelligence/v0.7/api-consumer-usage-request.schema.json` (the MCP `request` argument, discriminated on `mode`) and `…/api-consumer-usage-answer.schema.json`. Both are pinned byte for byte by `tests/unit/test_api_usage_contracts_schema_frozen.py`. |
| Contract models | `app/architecture_intelligence/api_usage_contracts.py` |
| Earlier versions | `schemas/architecture_intelligence/v0.5/*` and `v0.6/*` are unchanged; the four earlier tools and their routes keep their meanings |

### Route and tool map (D1)

| Mode | Service (sole semantic owner) | REST | MCP |
|---|---|---|---|
| `query` | `ArchitectureIntelligenceService.get_api_consumer_usage(ApiConsumerUsageQueryRequest)` | `POST /api/api-consumer-usage` | tool `get_api_consumer_usage`, `request.mode = "query"` |
| `evidence` | `ArchitectureIntelligenceService.get_api_consumer_usage_evidence(ApiConsumerUsageEvidenceRequest)` | `POST /api/api-consumer-usage/evidence` | the same tool, `request.mode = "evidence"` |

- **Tool count:** **five** read-only tools in lexicographic `tools/list` order: `get_api_consumer_usage`, `get_architecture_drift`, `get_evidence`, `get_service_dependencies`, `get_service_dependencies_by_locality`. `contracts.TOOL_NAMES` stays the three v0.5 names.
- **REST body:** closed. It is the published request minus `mode`, which the route supplies.
- **REST status:** a malformed body is `422`; every evaluated or refused answer is `200`. There is no 404 for an unknown target.
- **MCP:** the tool rejects an unexpected top-level argument before dispatch. Its `inputSchema.request` and `outputSchema` equal the published schemas after `$ref` resolution (`tests/unit/test_mcp_api_usage_contract_parity.py`).
- **Wire form:** an absent optional field is omitted, never `null`; only `data` and `snapshot` are required but nullable (D4).
- **Projection:** `app/architecture_intelligence/api_usage_projection.py` (query) and `api_usage_evidence.py` (evidence), both pure over the canonical snapshot state.

## 2. The independent truth tables

I4's expected answers are the I3.1c oracle, unchanged: [`i3-vectors/expected-answers.json`](i3-vectors/expected-answers.json).
- **Written independently:** it is produced by [`i3-vectors/author_expected_answers.py`](i3-vectors/author_expected_answers.py), a stdlib-only script that imports nothing from `app` (an AST test enforces it) and re-derives the I1/I2 identity formulas, the D9 digest, refs and the D8 cursor.
- **Read-only:** an implementation that disagrees is fixed, or the disagreement goes back to the specification. The expectation is never edited to fit a run (I3 stop condition).

57 cases: 32 answer cases (26 `query`, 6 `evidence`), 3 property cases and 22 request-validation cases.

| Group | Cases |
|---|---|
| Configured, observed, zero and unestablished rows | A01 (configured + observed), A02 (measured zero), A03 (insufficient measurement), A04 (observed only), A05 (rejected attempt only) |
| Explicit association outcomes | A06 (unresolved Operation), A07 (conflicting Service), A08/A09 (exact Operation and Service targets with the five-way summary), A19 (`NO_ROUTE_SELECTED` with data) |
| Traffic and windows | A10 (unattributed traffic), A11 (unsettled window), A12 (selected Route, no rows), A13 (no measurement source), A20 (reversed window) |
| Gateways | A14, A14b, A14c (same environment and window on two gateways) |
| Paging and snapshot fences | A15 (property), A15a–d (first page, continuation from the issued cursor, a substituted well-formed position, the unpaged selection), A16 (cursor after an unrelated import), A17 (stale snapshot) |
| Refusals | A13 (`MEASUREMENT_WINDOW_NOT_AVAILABLE`), A16/A17 (`SNAPSHOT_NOT_AVAILABLE`), A18a (`UNKNOWN_TARGET`), A18b (`TARGET_NOT_IN_WINDOW_SCOPE`), A15e (`CURSOR_QUERY_MISMATCH`) |
| Evidence | E01a–c (all five kinds resolve; a conflicting Service exposes only the raw statements; a resolved chain), E02a (some refs resolve; forged, cross-snapshot and cross-context refs do not), E02b (none resolves), E02c (an evidence snapshot that is no longer current) |
| Credential safety | C01 (canary absent from every answer and evidence payload) |
| Request validation | V01–V22 (V10, V11, V12, V17 are Pydantic-only; the schema cannot express them) |

**Matching:** matrix §2 is normative: exact equality, one wildcard `{{*}}` for any non-empty string (limitation messages and producer version/revision), and an absent optional field is omitted, so there is no null/omitted equivalence rule. The reference implementation is `tests/api_usage_oracle/matcher.py` and, for properties, `tests/api_usage_oracle/properties.py`.

**Worlds and fixture identity:** each world in the oracle is the exact frozen I2 handoff snapshot state (`snapshot_state`) plus harness-only inputs (`internal_only`, the credential canary). The base world is gateway `gw-prod-1`, environment `prod`, window 2026-10-13T10:00:00Z–2026-10-13T10:10:00Z with the I2 vector extract digests (`i2-vectors/ids.json` M04: start `37016ed92411f67d01e64485f1b41e391896bee09d5dfeb2484c71f5380cbb2e`, end `f753e83a206e90bd8b1ac0b4466b503f290b25dea2f34a1b42911dbd4734f97b`) and a second gateway `gw-prod-2`; the variants are `unattributed`, `not-settled`, `reversed`, `no-measurement` and `new-snapshot`. The snapshot ids are synthetic inputs of the cases (`snapshots.A`, `snapshots.B`). The real-import fixture is the I2.4 integration fixture (`tests/integration/test_v070_i2_qualification.py`: an APISIX configuration source, the bundled `examples/` OpenAPI and a measurement source).

## 3. Pins I4 must hold

- With no gateway source, the canonical snapshot has none of the conditional v0.7 keys, so every earlier snapshot pin, including the golden-path `expected_snapshot_id`, is unchanged (I2).
- The API usage answer and every v0.5/v0.6 answer for one graph carry the **same** `SnapshotRef`: the answer is projected from the very state that is fingerprinted (`_read_api_usage_snapshot`), with no further query.
- The oracle's refs and cursors are literal only under the injected synthetic snapshot ids. A run against a real snapshot must compare structure and rebind refs; it must not edit the expected literals.
- The published request and answer schemas, the I2 vectors, the I3 oracle and the matrix are read-only inputs.

## 4. Cross-surface normalization procedure

For one graph and one request, all three surfaces must return the same answer:
- the service answer is `ApiConsumerUsageAnswer.model_dump(mode="json")`;
- the REST response body must **equal** it;
- the MCP `tools/call` `structuredContent` must **equal** it.

The only differences allowed are transport ones: the HTTP status and the MCP result wrapper (`isError: false`). Each surface's answer also validates against the published answer schema, and the advertised MCP `inputSchema.request` and `outputSchema` equal the published request and answer schemas after `$ref` resolution.

The I3 implementations of these checks are:
- `tests/unit/test_v070_i3_projection_oracle.py` (every answer and property case through the projection);
- `tests/unit/test_v070_i3_adapter_oracle.py` (every case through the real REST router and MCP tool; request cases rejected by both; C01 on the transcripts);
- `tests/integration/test_api_usage_surface_parity.py` (service == REST == MCP on a real import, paging, evidence and the stale-snapshot refusal);
- `tests/integration/test_api_usage_repeatability.py` (two clean complete states give identical answers on every surface, snapshot id included);
- `tests/unit/test_mcp_api_usage_contract_parity.py`;
- `test_independent_client_runs_an_api_usage_query_and_resolves_its_evidence` (httpx-only client over real HTTP against the production app, both modes, a reconnect).

## 5. Measured cost (baseline, not an SLO)

[`i3-api-usage-cost.json`](i3-api-usage-cost.json), summarized in the completion record.
- At 10,000 qualification rows (100,000 for a Cartesian product), a 200-row page takes about 1.6 s end to end: the whole-state read about 0.66 s, the projection about 0.55 s.
- At 1,000 rows it takes about 0.2 s, and a Route target of 110 rows about 0.2 s.
- The projection builds the whole selection before paging (finding F1), so a full walk repeats that cost per page.

Re-measure with `uv run python -m benchmarks.api_usage_cost --profile i3 --candidate-sha <sha>` on the candidate host, from a clean checkout at that sha. Any threshold is a release decision, not a value implied here.

## 6. What I4 must do

1. Rerun the frozen oracle (every answer and property case), the cross-surface parity and the independent-client checks on **two clean complete states**, on the **exact final candidate** commit, with the identity threaded explicitly as the release process requires. Do not reuse an I3 run.
2. Compare the two runs' normalized answers for repeatability, and the surfaces for parity, by the procedure in §4.
3. Hold the §3 pins.
4. Capture the Tyk cross-check source and run the cross-source semantic check against the same question (parent §24), without changing the I3 contract.
5. Run the packaging and the product-value pilot (parent §25) against the five-tool surface.
6. Record the failures, skips and exact SHAs.

## 7. Deferred requirements (not I3, not I4)

- **Release slice:** the re-freeze to **five** tools in `examples/release-golden-path/golden_path.py` (`TOOLS`) and `expected.json`, the pinned `cursor.md`, `vscode.md`, `hero-demo.md`, `TRY_IT_HOSTED.md`, the README and CHANGELOG text and the runnable-demo paragraph of `docs/mcp.md` (completion record F4); the ROADMAP reconciliation.
- **Separate reviewed change:** page-before-enrich in the projection (F1).
- **v0.7.1:** broker-mediated consumer attribution.
- **Not in v0.7:** configured-only projection without a measurement window, historical windows, a username search, restart or counter-reset inference, authorization or policy judgments.
