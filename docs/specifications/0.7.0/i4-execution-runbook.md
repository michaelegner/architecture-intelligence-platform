# v0.7.0 I4.2 execution

Governing method: [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) revision 0.2, §§3–5, 7–8 and 10. Expectations are those frozen in I4.1 ([register](i4-coverage-register.md), [decision record](i4-decision-record.md), `i4-vectors/`, `i4-replay/`). This runbook introduces no semantic contract.

## Candidate

`I4_CANDIDATE_SHA` is a full 40-hex commit on `main` after I4.1a, I4.1b, I4.1c and the I4.2a close-out have merged (D1). Read it from git in the same command that uses it, never typed from memory:

```sh
SHA=$(git rev-parse HEAD)   # in a clean checkout of the candidate
```

Before running, read the check-runs of that exact SHA through the API (not `gh pr checks`) and confirm that every required name of D1 is `completed/success` and that no CI job is still running. A candidate whose CI has not finished is not run.

Create a clean detached worktree of the candidate. `git status --porcelain --untracked-files=all` must be empty; the coordinator refuses a dirty tree.

## Run

```sh
uv run python -m evaluation.i4 --profile v0.7 --candidate-sha "$SHA" --out <new directory>
uv run python -m evaluation.i4.api_usage_cost_run --candidate-sha "$SHA" --out <cost.json>
```

The output directory must not exist. The coordinator exports the same identity (`I4_CANDIDATE_SHA`, `AIP_BUILD_REVISION`) to two separate pytest processes, each with its own session-scoped, digest-pinned Neo4j testcontainer. Each worker verifies `HEAD`, the producer build revision and the v0.6 baseline ancestry, then executes every register anchor plus the runner steps: the 57 frozen I3 cases, the bridge vector `B07a`–`B07c`, the real-import questions, the APISIX replay (`P1`…`W-NONE`, `EV`, `REVd`, `REVe`) and the independent HTTP/MCP client.

Each run writes `ledger.json` (schema `i4-ledger/1`, profile `v0.7`) and the complete canonical bytes of every answer under `bytes/`. The coordinator compares raw bytes (A against B, and service against REST against negotiated MCP), checks the required case and surface inventories and the result labels against the frozen classifications, reads the check-runs of the candidate SHA, and writes `ci-check-runs.json` and `report.json`. A failed or skipped required test, an absent record, an oracle failure, a byte difference, a mislabelled row or an incomplete CI inventory produces `BLOCKED`, never a pass. The report is an I4.2 result, not all-I4 completion and not release readiness.

The full unit and integration tiers run once on the same clean checkout (spec §4.3), together with `ruff`, `pyright`, `lint-imports` and `deptry`. The qualification tier already ran in CI on the candidate.

## Development mode

`--i4-development` with `--i4-candidate-sha`, `--i4-run` and `--i4-out` exercises the tooling on an uncommitted tree. Its ledger has `qualification_eligible: false` and the comparator refuses to qualify it. It is unavailable through the coordinator.

## If a run is BLOCKED

Stop and report (spec §13). Do not edit a result, a ledger, an oracle or an expectation after seeing an AIP output, and do not rerun until green. A fix is a reviewed change followed by a new candidate and a rerun of every affected gate.

## Evidence

Passing evidence is kept under `docs/release-validation/v0.7.0-i4.2/`: `report.json`, `ci-check-runs.json`, the cost artifact and a raw bundle (both ledgers, all canonical bytes, digests, input pins, pytest logs) with its SHA-256, so the comparison can be repeated from the bundle with `compare_runs(Path(...), V07)`. The execution record is added as a later documentation-only commit and is not claimed to be separately A/B-qualified. The Tyk dossier, the product-value pilot, the completion record and the I4 → I5 handoff are I4.3.
