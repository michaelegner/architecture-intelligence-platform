# I5 Public-Surface Checks on the Real Runs (frozen, Slice 4)

This freezes how Slice 5 checks the §9 row "Public answers and provenance" and the §13 item
"Public surfaces" on each target's qualifying run. The checks run after the comparison capture
(target `runbook.md` step 10), against the same running stack and the same observation context.
Nothing here authors an expected fact. It checks that the three public surfaces agree with each
other and that reading them writes nothing.

## Representative reads

| Target | Read | Why it is representative |
| --- | --- | --- |
| quarkus-super-heroes | Dependencies of `service:rest-fights` | HTTP claims (3 `CONFIRMED` + 4 `NOT_OBSERVED_IN_WINDOW` CALLS in the frozen expectations) plus a `DEPLOYED_AS` deployment claim (`RESOLVED_CONFIGURED`) |
| quarkus-super-heroes | Drift of `service:rest-fights` | The declared-but-unobserved CALLS |
| quarkus-super-heroes | Evidence for every `evidence_refs` entry of the dependencies answer, in batches of at most 20 | Same-snapshot drill-down (I5 §13) |
| apache-airflow | Dependencies and drift of `service:airflow-apiserver` | A declared provider with no outgoing dependency: the empty-claims answer |

Neither target has a supported messaging claim; both are messaging negatives. So **messaging-claim
parity is a coverage gap on the real targets.** It is covered only by the supporting I4 fixture
evidence (`coverage-matrix.md`).

## The three surfaces and the comparison

For each read, obtain the answer at one snapshot with the same explicit observation context: the
target's environment and its `[WINDOW_START, WINDOW_END]`.
1. **Service.** `ArchitectureIntelligenceService`, built through
   `app.mcp.wiring.production_service_kwargs` from the target's AIP config, the same way the
   capture tool builds it. The answer is `model_dump(mode="json")`.
2. **REST.** `GET /api/services/{service_id}/dependencies` or `/drift`, and `GET /api/evidence` for
   drill-down. The answer is the JSON body.
3. **Negotiated MCP.** `POST /mcp` through `tests/integration/independent_mcp_client.py`
   (`tools_list`, `call_tool`). The answer is the tool result's `structuredContent`.

**Pass condition:** the three JSON values are equal for every read. This is the same projection as
`tests/integration/test_mcp_service_dependencies_equivalence.py`. The snapshot identity in the three
answers is also equal.

**MCP tool set:** `tools/list` returns exactly `get_architecture_drift`, `get_evidence` and
`get_service_dependencies`, in that order.

## Zero writes

1. Before the first public read, run `../queries/Q-GRAPH.cypher` with `cypher-shell --access-mode
   read` and record the sha256 of its output.
2. After the last public read, repeat it.
3. **Pass condition:** the two digests are equal.

The digest is compared within one run only, because element ids are database-local.

Record every result in the target's `results.md`. A mismatch is a finding (I5 §11).
