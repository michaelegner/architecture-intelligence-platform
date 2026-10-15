# v0.7.0 I4.2 — Execution record

**Status: I4.2 execution PASS.** Governing: the [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) revision 0.2, §§3–5, 7–8 and 10; the [execution runbook](i4-execution-runbook.md).
Exact tested candidate, read from `git rev-parse HEAD` in the clean candidate checkout:
`c662f3c440733a7b75252ba2466fee14c1c88f4a` (#554, the I4.2a close-out, on top of I4.1c #553 `d3cea3a`). This record does not declare I4 complete or release readiness: the Tyk dossier, the product-value pilot, the completion record and the I4 → I5 handoff are I4.3.

## Execution

No production code, schema, oracle, expectation or qualification code was changed for this run. The candidate's CI had finished before the run: all 13 required checks (D1) are `completed/success` on the candidate SHA, read through the check-runs API. The checkout was a detached, clean worktree of the candidate (`git status --porcelain --untracked-files=all` empty before the local gates, before the qualification and before the cost run). No rerun, repair or normalization took place; the single qualification run reported below is the only one.

```sh
uv run python -m evaluation.i4 --profile v0.7 --candidate-sha c662f3c440733a7b75252ba2466fee14c1c88f4a --out <new directory>
uv run python -m evaluation.i4.api_usage_cost_run --candidate-sha c662f3c440733a7b75252ba2466fee14c1c88f4a --out api-usage-cost.json
```

## Qualification result

| Run | Process ID | Fresh Neo4j container ID | Recorded resets | Records | Cases | Canonical byte files | Tests |
|---|---|---|---|---|---|---|---|
| A | 41064 | `286064112b1c355d957fa49bc29756dc318ef5468681ebd51b9c96028426a830` | 2 (real import, replay) | 215 | 80 | 215 | 532 passed |
| B | 42142 | `329d7eed88e391967839faabf2e9151fcfe33d31f0f4fc7ff76a2c5f9e5b0752` | 2 (real import, replay) | 215 | 80 | 215 | 532 passed |

| Check | Result |
|---|---|
| Required cases (V07 profile, 76) and the real-import questions (`RT01a`–`RT01d`) | all present in both runs; 80 distinct case ids |
| Oracle checks | every record `oracle_match: true` in both runs |
| Result labels | 84 `I4_CORRECT` and 131 `I4_EXPECTED_NEGATIVE` records in each run, each equal to the independently frozen classification; no other label |
| Raw canonical A/B comparison | zero differences; no normalization |
| Service / REST / negotiated MCP | zero byte differences |
| Independent HTTP client | query, evidence and reconnect agree |
| Exact-candidate CI | 13 recorded checks, all required names present, all `success`, all on the candidate SHA |
| Report | `status: PASS`, `blockers: []` |

Cases by family (distinct case ids; the register's positive-versus-abstaining counts, §10), identical in A and B:

| Family | Positive / resolved (`I4_CORRECT`) | Expected-negative / abstaining (`I4_EXPECTED_NEGATIVE`) |
|---|---|---|
| Frozen I3 answers and properties (`A*`) | 13 | 15 |
| Frozen I3 evidence (`E*`) | 3 | 3 |
| Frozen I3 request validation (`V01`–`V22`, REST and MCP) | 0 | 22 |
| Frozen I3 property `C01` | 1 | 0 |
| Bridge vector `B07a`–`B07c` | 1 | 2 (`B07a`, `B07b`: `AMBIGUOUS` Route→Operation, no `operation_id`) |
| APISIX real replay | 8 (`P1`, `P2`, `N4`, `N4b`, `OBS`, `REVa`, `REVc`, `EV`) | 8 (`N1`, `N2`, `N3`, `REVb`, `REVd`, `REVe`, `W-INVALID`, `W-NONE`) |
| Real-import questions (`RT*`) | 3 | 1 |

No scenario class passed solely because everything abstained: every class with answers has both a positive and an abstaining case, and the request-validation class consists of rejections by definition.

## Local gates on the candidate checkout

| Gate | Result |
|---|---|
| `ruff format --check`, `ruff check` | clean |
| `pyright` | 0 errors |
| `lint-imports`, `deptry` | 10 contracts kept; no dependency issues |
| `tests/unit` | 4,668 passed |
| `tests/integration -m "not qualification"` | 837 passed, 1 skipped |

The one skip is `tests/integration/test_pitstop_demo_live_smoke.py`, which needs `PITSTOP_FORK_DIR` (the private instrumented Pitstop fork). It is not a register anchor, not a worker test and not a mandatory qualification case. The qualification tier ran in CI on the candidate (three `integration-qualification` jobs, all `success`), and both workers executed every register anchor without a skip.

## Cost evidence (spec §8; evidence, not an SLO)

[`api-usage-cost.json`](../../release-validation/v0.7.0-i4.2/api-usage-cost.json) was produced through the I4 wrapper: it carries the candidate SHA, the verified `HEAD`, the producer build revision, the Neo4j version (5.26.31, digest-pinned), the input pins and the exact-SHA check-runs (no CI blockers). Median of five repeats, this machine (14 logical CPUs, 16 GB, WSL2):

| Point | Rows | Pages | Import (s) | End to end (ms) | State read (ms) | Fingerprint (ms) | Projection (ms) | Evidence lookup (ms) |
|---|---|---|---|---|---|---|---|---|
| service, 100 rows | 100 | 1 | 8.1 | 174 | 132 | 2.7 | 4.6 | 121 |
| service, 1,000 rows | 1,000 | 5 | 7.8 | 198 | 117 | 18.6 | 38.6 | 147 |
| service, 5,000 rows | 5,000 | 25 | 37.3 | 519 | 226 | 74.7 | 196.9 | 340 |
| service, 10,000 rows | 10,000 | 50 | 142.8 | 1,065 | 498 | 167.0 | 365.4 | 711 |
| Route target, 110 rows | 110 | 1 | 8.2 | 163 | 116 | 30.7 | 3.8 | 165 |
| invalid window, 800 rows | 800 | 4 | 2.7 | 105 | 62 | 10.1 | 26.1 | 79 |

Every complete cursor walk saw exactly its row count, with no refusal. The I3 findings are carried, unchanged and still open: **F1** (the projection builds the whole selection before paging; deferred past the candidate, D2), **F2** (every request reads the whole canonical state) and **F3** (evidence mode rebuilds the ref map for the whole selection). The measurements are consistent with them: end-to-end cost grows with the whole selection, not the page.

### Selected-source (APISIX) import/replay cost and association rates (spec §8)

The I3 benchmark above is the synthetic-scale tool run through the I4 identity wrapper; it does not report the selected-source replay. These items were measured afterwards on the same clean candidate checkout (`HEAD` equals the candidate, `git status` empty) with [`replay_measurement.py`](../../release-validation/v0.7.0-i4.2/replay_measurement.py), which uses only the frozen replay path (`evaluation.i4.apisix_replay`, the committed real captures, `run_all_configured_sources`), changes no qualification code, expectation or fixture, and asserts nothing about answers. Output: [`replay-measurement.json`](../../release-validation/v0.7.0-i4.2/replay-measurement.json). Five repetitions, each into an emptied disposable Neo4j 5.26.31 (digest-pinned); the association counts were identical in every repetition (the script asserts it). The committed script was formatted by `ruff format` after the run; the formatting is the only difference. Evidence, not an SLO.

**Import/replay cost** (seconds; each import runs the examples directory and the APISIX configuration and measurement sources of the revision through the production path):

| Import | Median | Min | Max | All five |
|---|---|---|---|---|
| R1 into an empty graph | 0.86 | 0.74 | 7.68 | 7.68, 1.56, 0.86, 0.83, 0.74 |
| R2 over R1 (authoritative update) | 0.87 | 0.63 | 4.40 | 4.40, 1.17, 0.87, 0.71, 0.63 |

The first repetition of each is a cold start; the spread is stated, not trimmed.

**Unresolved and ambiguous rates in the imported replay state.** There are no `AMBIGUOUS` outcomes anywhere in the replay state. The unresolved rates are high, by construction of the replay world and not a defect: the replay gateway's Routes expose no contract Operation of the examples, and **no mapping entry was supplied** (`mapping_entries` = 0), so no manual mapping was needed to obtain any answer and none could have resolved an association.

| Measure | R1 (window W1) | R2 (window W2) |
|---|---|---|
| Routes | 5 | 5 |
| Route → Operation | 5 `UNRESOLVED` (5 / 5) | 5 `UNRESOLVED` (5 / 5) |
| Route → application Service target | 5 `UNRESOLVED` (5 / 5) | 5 `UNRESOLVED` (5 / 5) |
| Measurement attribution: consumer | 4 `RESOLVED`, 1 `UNRESOLVED` (the unattributed `consumer=""` series, `N3`) | 1 `RESOLVED` |
| Measurement attribution: Route | 5 `RESOLVED` | 1 `RESOLVED` |
| Route coverage | 3 `SUFFICIENT_FOR_ZERO`, 2 `UNKNOWN_COVERAGE` | 4 `SUFFICIENT_FOR_ZERO`, 1 `UNKNOWN_COVERAGE` |
| Qualification rows | 9: configured access 7 established, 2 with no matching configured access (`OBS`) | 4: 4 established |
| Usage status of the rows | 3 `OBSERVED_USAGE`, 4 `MEASURED_ZERO`, 2 `USAGE_UNESTABLISHED` | 2 `MEASURED_ZERO`, 1 `OBSERVED_USAGE`, 1 `USAGE_UNESTABLISHED` |

The product-relevant reading is that, from a gateway capture alone, APISIX Routes are not associated to API contract Operations or application Services without a contract match or an operator mapping. That is the frozen v0.7 behaviour (parent §§10 and 15: association is not entity equivalence and is never invented), it is not a qualification failure, and it is the identity-mapping effort the I4.3 pilot has to weigh.

## Auditable artifacts

Under [`docs/release-validation/v0.7.0-i4.2/`](../../release-validation/v0.7.0-i4.2/):
[`report.json`](../../release-validation/v0.7.0-i4.2/report.json) (PASS, zero mismatches, the 13-check CI inventory);
[`ci-check-runs.json`](../../release-validation/v0.7.0-i4.2/ci-check-runs.json) (each check's id, candidate identity, conclusion and details URL);
[`api-usage-cost.json`](../../release-validation/v0.7.0-i4.2/api-usage-cost.json);
[`replay-measurement.json`](../../release-validation/v0.7.0-i4.2/replay-measurement.json) and its script;
[`raw-evidence-c662f3c.tar.gz`](../../release-validation/v0.7.0-i4.2/raw-evidence-c662f3c.tar.gz) (both ledgers, all 430 canonical byte files, the test outcomes and the pytest logs; SHA-256 `8ef9163b4b239c5b271aa0d2296ad0d0e27dcbb897d5ffac846f4047143a1ff3`).

Extract the bundle and call `compare_runs(Path("aip-i4.2-qualification-c662f3c"), V07)` from `evaluation.i4.__main__` (with `V07` from `evaluation.i4.profiles`) to repeat the comparison independently; the evidence was re-compared from the extracted bundle before it was committed and returned no blocker. The `/tmp` paths in the report identify the execution location; relative contents are retained beneath the archive's top-level directory. The replay fixtures and their digests are the committed `i4-replay/` package at the candidate; none of its readings was edited after any run (`EXPECTED.sha256`). A scan of the bundle for the replay package's fake credential values found none.

## Remaining

No semantic mismatch, unexplained skip or unexecuted mandatory case remains in I4.2. This evidence-only commit is a later documentation-only commit and is not claimed to be separately A/B-qualified; production code, qualification code, expectations, schemas and configuration are unchanged after the tested candidate. Known debt carried: F1–F3 (above) and #323. Remaining I4 work, all I4.3: the Tyk semantic cross-check dossier, the coding-agent pilot and its disposition, the I4 completion record and the I4 → I5 handoff. I5 owns release candidate freeze, release-content re-freeze, publication and verification, and must rerun the mandatory qualification on its own exact final candidate.
