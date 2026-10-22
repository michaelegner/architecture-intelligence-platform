# v0.7.2 I3 comparison kit

This kit runs the controlled comparison of [spec](../specification.md) §5 on the bounded Sokol111 change, a new field in `ProductUpdatedEvent`:
- **Arm A:** Unblocked only.
- **Arm B:** the same Unblocked setup, plus the hosted AIP MCP at `https://mcp.daip.io/mcp`. It serves the frozen Sokol111 C1 ([I2 record](../i2-hosted-record.md)).

AIP is the only added capability. The result is the comparison record, `../i3-comparison-record.md`, which is written after the run. [`scoring.md`](scoring.md) holds the ground truth and the rubric, and it was committed before either arm ran.

## Files

| File | Purpose |
|---|---|
| [`simulator.patch`](simulator.patch) | The adaptation of [`unblocked/context-engine-simulator`](https://github.com/unblocked/context-engine-simulator) at `837eb0a3bc217e594ac87b821881573957f70a9b` (MIT, no tags) |
| [`fixture.yaml`](fixture.yaml) | The task, the evaluator criteria, the models, and both arms |
| [`arm-unblocked.mcp.json`](arm-unblocked.mcp.json), [`arm-unblocked-aip.mcp.json`](arm-unblocked-aip.mcp.json) | The exact MCP servers of each arm. The Unblocked token comes from `UNBLOCKED_API_TOKEN` and is never written to a file here |
| [`settings.json`](settings.json) | In every invocation, turns off the local `aip` and `aip-mod` plugins and auto-memory. Without it, every worktree of the synthetic repository resolves to the same memory directory, so one arm could load what the other saved (probed with Claude Code 2.1.308) |
| [`build-synthetic-repo.sh`](build-synthetic-repo.sh) | Builds the repository both arms work in |
| [`scoring.md`](scoring.md) | Ground truth and rubric |

## The adaptation

By default the simulator does not compare arms with different tools. Its baseline runs plan → review → implement. Its enhanced arm adds a context-gathering pass and a plan-context pass. `--disable-mcp` applies to **both** arms and only detects calls; it hides nothing. Its detector parses Cursor's stream format, not Claude Code's.

The patch adds a same-chain mode (`arms:` in the fixture, Claude only):
- **Same chain.** Both arms run the same six-step context chain, with the same prompts, models, effort and budgets. They differ only in `--strict-mcp-config --mcp-config <arm file>`.
- **Isolated tool-less steps.** Pattern extraction, eval and attribution run with no MCP servers.
- **Init check.** Every invocation records its stream-json `system`/`init` event in `result.json` and checks it before the agent acts. The check requires:
  - exactly the arm's servers, all `connected` and each exposing tools;
  - no plugin except Claude Code's own `@builtin` ones;
  - in arm A, no server, tool or skill containing `aip`.
  A failure aborts the arm.
- **Call guard.** A Claude-format guard aborts arm A on any `mcp__*aip*` call.
- **Worktrees.** Each arm works in its own worktree, under its own new temp directory, not side by side.
- **`--check-arms` gate.** It runs one minimal invocation per arm. With `--swap-arms`, both must fail.
- **Reports.** The terminal, HTML and JSON reports show six steps and attribution for both arms, under the arm names.
- **Lock file.** It carries a regenerated `package-lock.json`, because upstream's lock file is out of sync with its `package.json` (`npm ci` fails: `Missing: eslint@9.39.5`).

The same tools are closed in both arms (`fixture.yaml` `disallowedTools`): web access, `gh`, `curl` and `wget`. The public AIP repository contains the I2 answer key, and the simulator's context pass otherwise runs `gh search`.

## Synthetic repository

The simulator needs one git repository, but Sokol111 spans many. `build-synthetic-repo.sh ~/code/sokol111-i3` builds one commit that holds:
- the `ecommerce-workspace` tree, with these 7 repositories nested in it at the [I2 freeze](../i2-evidence/sokol111/freeze.md) commits: `-infrastructure`, `-commons`, `-catalog-service`, `-catalog-service-api`, `-product-query-service`, `-image-service`, `-category-query-service`;
- `ops-evidence/kafka-local-2026-10-21T17-53Z/`, which contains only the stock `rpk` steps 01–08 and 11–14 of the I2 capture (G1, the Topic describe, versions and G1'). It excludes AIP's own capture (step 10), `expected.json` and the mapping.

The build is deterministic: commit `3d6a311a90a4eb4adf4d3f152ecc7cd74c88744f`.

Disclosed differences from the real workspace:
- the workspace `.gitignore` lines for the nested repositories are removed, because ignored paths would be hidden from the agents' search;
- `go.work` names six workspace repositories that are not included;
- there is no upstream git history.

Unblocked indexes the owner's forks of the same 8 repositories at the same commits. Forks do not carry upstream pull requests or issues.

## Steps

**Owner, once:**
1. Create an Unblocked account.
2. Fork the 8 repositories into your account.
3. In Unblocked, go to Team Settings → Data Sources → GitHub and select **only those forks**. Connect no other data source.
4. Create a Personal API token limited to that source and save it in `~/.config/unblocked-i3.token` (mode 600).

**Me:**

```sh
KIT=$PWD/docs/specifications/0.7.2/i3-evidence
SIM=$(mktemp -d) && git clone -q https://github.com/unblocked/context-engine-simulator.git "$SIM"
git -C "$SIM" checkout -q 837eb0a3bc217e594ac87b821881573957f70a9b && git -C "$SIM" apply "$KIT/simulator.patch"
(cd "$SIM" && npm ci --silent)
"$KIT/build-synthetic-repo.sh" ~/code/sokol111-i3        # prints 3d6a311a…
export UNBLOCKED_API_TOKEN=$(cat ~/.config/unblocked-i3.token)
RUN="$SIM/node_modules/.bin/tsx $SIM/src/index.ts --fixture $KIT/fixture.yaml --repo $HOME/code/sokol111-i3"
cd "$(mktemp -d)"                                          # results/ lands outside every arm's reach
$RUN --check-arms              # G3: both PASS
$RUN --check-arms --swap-arms  # G3 negative: both FAIL, exit 1
$RUN                           # the experiment
```

**G2 comes before G3.** Run one Unblocked-only `claude -p` with the arm A config, asking where `ProductUpdatedEvent` is defined and who consumes it. It must:
- connect `unblocked`;
- return citations into the forks;
- show whether `context_research` and `context_get_urls` are exposed.

**After the run, before anything is committed:**
1. Grep `result.json`, `report.html` and every transcript for the literal value of `UNBLOCKED_API_TOKEN`. The agents' shells inherit it. Rotate the token afterwards either way.
2. Scan the transcripts:
   - no `gh`, `curl` or `wget`;
   - no path outside the arm's own worktree;
   - no other arm's `ces-*` branch in `git worktree list`, `git branch -a` or `git log --all` output;
   - no AIP repository content;
   - no AIP in arm A.
3. List every `context_get_urls` argument in both arms. A URL of the AIP repository or of `daip.io` is contamination.
4. List arm B's AIP errors and HTTP 429s. The edge has a rate limit, and a limited call is an environmental difference, not an AIP answer.
5. Run `git log main..HEAD` in each kept worktree. The simulator's diff misses committed work.
6. Score both arms against `scoring.md`.
