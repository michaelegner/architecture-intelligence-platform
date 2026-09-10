# I3 Completion Record — v0.4.1 Hardening, Qualification and Release

One concise record covering all of I3's slices plus the release itself, matching this repository's
established precedent (`i1-completion-record.md`, `i2-completion-record.md`). See
[`i3-hardening-qualification-and-release.md`](i3-hardening-qualification-and-release.md) for the
full spec this record qualifies against.

## Run identity

- **I3.1 (Reproducible Benchmark Harness):** merged to `main` as `795653e6da419c0d04918dee4a45fa734d996a67`
  (PR #119, 2026-09-10) plus a same-PR review-round follow-up (`d815ad4`, squashed into `795653e`
  on merge) fixing four real findings: candidate-identity spoofing (an explicit `--candidate-sha`
  now must match the actual checkout or the measured `producer.build_revision`), two separate
  incomplete "did this run succeed" predicates centralized into one `scale_points_are_valid()`,
  the real Neo4j server version now queried live instead of guessed from the mutable image tag,
  and structural validation now checks the target subgraph against a frozen baseline plus a
  CALLS-specific relation count, not just a self-consistent aggregate delta.
- **I3.2 (Candidate Preparation):** merged as `bc03602f95557eb0450506a9f5c3a7f7c296b2da` (PR #120)
  plus a review-round follow-up (`6bbd8f7`, squashed in) fixing a real drift: the architecture-answers
  evaluator's own synthetic producer and all 23 `expected_answer.json` fixtures had independently
  drifted to a stale `0.4.0` — centralized through a new `app/version.py::package_version()` single
  source of truth. **This commit is `RELEASE_CANDIDATE_SHA`** — every subsequent slice's evidence
  is bound to it, never to a later `main` tip.
- **I3.2 qualification evidence (doc-only, PR #121):** merged as `bab0e45` — candidate-bound
  benchmark result, clean-checkout qualification record
  (`v0.4.1-rc.1-candidate-preparation.md`). Evidence-only per spec §21; does not move
  `RELEASE_CANDIDATE_SHA`.
- **I3.3 (RC/GO/Final Publication):** `v0.4.1-rc.1` tagged and published at `bc03602` (PR #122,
  merged `9edb03e`, one review round fixing an incomplete published-image golden path — the drift
  flow was missing, plus two Copilot findings). GO decision recorded by the repository owner,
  2026-09-10 (PR #123, merged `9464c65`). Final `v0.4.1` tag published at the same `bc03602`
  candidate; final publication identity recorded (PR #124, merged `d01d474`).
- **I3.4 (Post-Release Verification and Closure):** this record, plus
  `v0.4.1-post-release-verification.md` and the public status-closure edits (`ROADMAP.md`,
  `README.md`, `docs/specifications/0.4.1/README.md`, `docs/release-validation/README.md`).
- **CI, verified via the GitHub API against the exact candidate SHA** (not `gh pr checks`):
  `lint + test`, `CodeQL` (`analyze (actions)`, `analyze (python)`),
  `dependency security scan (pip-audit)` — all `completed`/`success` at `bc03602`, both at merge
  time and re-verified at RC/final publication time.

## Regression suite (candidate `bc03602`, clean-checkout run)

| Suite | Result |
|---|---|
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run pytest tests/unit` | 985 passed |
| `uv run pytest tests/integration` | 257 passed |
| `uv run python -m evaluation answers --candidate-sha bc03602...` | 23/23 PASS, two clean-state passes semantically identical |
| `uv run --with pip-audit pip-audit` | No known vulnerabilities found |

985 unit tests = the 930 v0.4.1-I2 baseline + 32 (I3.1 benchmark harness) + 18 (I3.1 review-round
regressions) + 3 (I3.2 version-consistency) + 2 (I3.2 review-round version-consistency extensions).
257 integration tests = the 254 v0.4.1-I2 baseline + 3 (I3.1 benchmark seed/cleanup/smoke).

## One declared-versus-observed semantic owner (spec §6.1, preserved from I1)

`app/qualification/declared_observed.py` remains the single semantic owner for both the
analysis/REST path and `ArchitectureIntelligenceService`/MCP. Qualification mismatches = 0,
coverage mismatches = 0, confirmed by `tests/integration/test_qualification_consistency.py` as
part of every clean-checkout run in I3.2/I3.3.

## Messaging semantic guards (spec §6.2, preserved from I2)

Both guards (`decide_destination_semantics`, `decide_service_identity` in
`app/telemetry/messaging_guards.py`) remain wired into `correlate_queue_observations`, refusal
still creates zero semantic artifacts, and the frozen Quarkus/Airflow exact-captured-shape
regressions still pass unmodified — confirmed by the full clean-checkout unit/integration run.

## Committed snapshot/read-cost benchmark (spec §7-18)

`benchmarks/snapshot_read_cost.py` + `benchmarks/__main__.py`
(`uv run python -m benchmarks --profile {smoke,review-comparable}`), a committed closed JSON
Schema (`benchmarks/snapshot_read_cost.schema.json`), seeding through real production write paths
(`app.graph.importer.import_all_sources`, `app.telemetry.aggregator.persist_observation_batch`),
timing the real `canonical_snapshot_state()`/`snapshot_fingerprint()` and one end-to-end
`get_service_dependencies` call through the real MCP boundary
(`tests/integration/independent_mcp_client.py`).

Candidate-bound `review-comparable` result (`bc03602`, `dirty_worktree=false`):

| Scale index | Total nodes | Snapshot fingerprint (min) | Dependency call (min) | Structural | Semantic |
|---:|---:|---:|---:|---|---|
| 0 | 120 | 0.0353s | 0.0900s | PASS | PASS |
| 1 | 4,980 | 0.3686s | 0.4099s | PASS | PASS |
| 2 | 19,980 | 1.3897s | 1.5170s | PASS | PASS |
| 3 | 99,030 | 7.3035s | 8.1093s | PASS | PASS |

Target answer semantically invariant across ~825× graph-size growth; observed cost increased with
total graph size in this environment (bounded conclusion, spec §16 — no SLO, no linear-law claim).
Full result: `docs/release-validation/v0.4.1-read-cost-benchmark.json`/`.md`
(`sha256:cd6dd9669af94850b51db503f75bd6ed03717dc4467196ecac26b6b697d0d389`).

**No cache, snapshot-identity change, or retention policy shipped.** ADR 0011 stays `Proposed`
(evidence note added, naming this benchmark as the baseline half of its acceptance condition — the
cache-effect half remains unsatisfied by design). ADR 0012 remains untouched/deferred.

## Public contract compatibility (spec §6.3)

Preserved throughout: exactly `get_architecture_drift`, `get_evidence`, `get_service_dependencies`;
read-only MCP, zero graph writes through any tool (confirmed against the actual published RC and
final GHCR images, not only the source suite); `ArchitectureAnswer<T>` envelope family;
`schema_version = "0.4"`; snapshot-bound answers; evidence/provenance drill-down; direct
dependencies only; no LLM requirement for deterministic correctness.

## Release publication

```text
RELEASE_CANDIDATE_SHA:        bc03602f95557eb0450506a9f5c3a7f7c296b2da
RC tag:                       v0.4.1-rc.1 -> bc03602 (published as prerelease)
Final tag:                    v0.4.1 -> bc03602 (published as the final release)
Final GHCR digest:            sha256:fdcd5957419b0c6c4e90536b529b08b88a49573e9bb9ea256fa090e2ed3c76fa
GO decision:                  decided by the repository owner, 2026-09-10
```

Full records: `docs/release-validation/v0.4.1-go-no-go.md`,
`docs/release-validation/v0.4.1-post-release-verification.md`.

## I3 exit statement (spec §39)

> GO — At `bc03602f95557eb0450506a9f5c3a7f7c296b2da`, AIP v0.4.1 preserves the shipped v0.4
> ArchitectureAnswer schema family and exactly three read-only MCP tools while completing its
> semantic hardening: the analysis and Architecture Intelligence paths remain governed by one
> declared-versus-observed rule with qualification mismatches = 0 and coverage mismatches = 0, and
> runtime messaging still requires both Queue-compatible destination semantics and safe service
> identity before producing any canonical artifact. A committed, disposable, deterministic
> benchmark reproduces and records the current relationship between total graph/evidence size and
> snapshot/dependency read cost without changing snapshot identity, retention, or public semantics.
> The exact source candidate, release-triggered RC image, final v0.4.1 tag, and final GHCR image
> have passed their required independent qualification, with producer.version=0.4.1 and
> producer.build_revision=bc03602f95557eb0450506a9f5c3a7f7c296b2da. Release blockers = 0.

`v0.4.1` is shipped — see [`ROADMAP.md`](../../../ROADMAP.md)'s `v0.4.1` section.
