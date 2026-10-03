# AIP v0.6.0 I4 — Ledger and Comparator Design

**Status:** I4.1 design (decision D3). It is implemented in I4.2/I4.3; nothing here has been run.
**Governing:** [I4 specification](i4-deterministic-semantic-qualification.md) §4–§7.

## 1. Candidate identity

- `I4_CANDIDATE_SHA` is one 40-hex value passed explicitly to every component: the runner, both run workers, the evaluators, both benchmarks and the ledger writer.
- Each component calls `benchmarks.snapshot_read_cost.resolve_candidate_sha(explicit)`. It validates the 40-hex form and fails when the value differs from the checkout `HEAD`. A worker also asserts the producer build revision equals it.
- `benchmarks/scoped_churn_cost.py` and `benchmarks/locality_cost.py` gain a `--candidate-sha` argument in I4.3. Their ambient `git rev-parse HEAD` (`commit` key) is replaced by the validated value.
- CI is read from `gh api repos/<owner>/<repo>/commits/<sha>/check-runs`, never `gh pr checks`. The ledger stores run/check IDs, status and conclusion, in the TSV shape of `docs/real-world-validation/v0.5.0/final-candidate/suites/ci-check-runs.tsv`.

## 2. Two clean runs

- A coordinator starts run A and run B as separate `python -m pytest` subprocesses. Each starts its own session-scoped Neo4j testcontainer (`tests/integration/conftest.py::neo4j_container`), so the container ID differs.
- The in-process caches `locality_oracle/world.py::_REPLAYED` and `test_locality_rehearsal_replay.py::_RESULTS` may speed a run but never cross A and B.
- Each run replays C1 then C2 (including both `B01` variants), resets state between scenarios or declared sequences, and writes raw artifacts to a directory named by `AIP_I4_OUT_DIR`.
- The ledger records per run: process ID, container ID, the clean-state proof (node count `0` after reset, schema re-applied), the candidate SHA, and fixture, oracle, schema and config digests.

## 3. Canonical bytes and comparison

- Serialization is `app/architecture_intelligence/canonical_json.py::canonical_json_bytes` (sorted keys, compact separators, UTF-8, UTC timestamps). The digest is its SHA-256.
- **A versus B:** the raw canonical bytes of each case, state and surface are compared exactly. No placeholder substitution, ID remapping, field removal or masking. `snapshot_id`, assessment and assertion IDs, source and capture IDs, Workload UIDs, provenance, limitations and producer identity stay in. A stable refusal is compared the same way.
- **Service versus REST versus MCP (within one run):** only the HTTP status and the MCP result wrapper are removed (`response.json()` body, `structuredContent`). The remaining bytes must equal the service's `LocalityAnswer.model_dump(mode="json")` canonicalized.
- **Oracle conformance only:** symbol binding and set matching (`locality_oracle/matcher.py`) apply to the comparison against the frozen expected JSON and never to A/B or adapter parity.
- Cursor and `snapshot_id` binding: the runner records each continuation's cursor and snapshot and asserts it stays bound to the first call.

## 4. Ledger schema (`i4-ledger/1`)

One JSON document per run plus a merged result. Per case/state/surface record:

| Field | Meaning |
|---|---|
| `case_id`, `register_key` | oracle or `B` case; `S20-NN` or `G-NN` |
| `state` | `C1`, `C2`, … or the declared sequence step |
| `surface` | `service`, `rest`, `mcp`, `mcp-independent-client` |
| `candidate_sha`, `head`, `producer_build_revision` | verified equal |
| `run`, `process_id`, `container_id` | `A` or `B`, distinct per run |
| `input_digest`, `oracle_digest`, `schema_digest`, `config_digest` | pins |
| `canonical_digest` | SHA-256 of the raw canonical semantic bytes; `bytes_ref` points at the artifact |
| `oracle_match` | `true`/`false`, with `mismatch_excerpt` on failure |
| `original_disposition` | the payload's own disposition/limitation code, recorded separately |
| `classification` | `I4_CORRECT`, `I4_MISSING_SUPPORTED`, `I4_UNSUPPORTED_EXPECTED`, `I4_UNRESOLVED_EXPECTED`, `I4_INSUFFICIENT_EVIDENCE_EXPECTED`, `I4_SEMANTIC_DEFECT` |
| `skipped`, `skip_reason` | an unexecuted required case is a blocker |

The merged result adds `ab_equal`, `cross_surface_equal`, the CI check-run table, and separately: harness/environment failures, known debt (#323), unsupported scope and product/performance findings.

The `I4_…_EXPECTED` classifications mean a *correctly expected* abstention. They are ledger vocabulary only and change no public enum or I2 disposition value.

## 5. Acceptance (I4 §4)

Zero A/B byte differences, zero oracle mismatches on supported and forbidden facts, zero cross-surface byte differences, zero false positive locality or negative-dependency claims. An unexecuted required case, unexplained nondeterminism, or a fixture changed after seeing output blocks the result.

## 6. Out of scope here

The runner and comparator code (I4.2), the benchmark changes and the capacity disposition (I4.3), and the I5/I6 items listed in the I4 specification §2.
