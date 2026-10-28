# v0.8 I4 operator tooling

**Governs:** [I4 specification](../../../docs/specifications/0.8.0/i4-agent-run-report-and-release.md)
Draft 0.3. This is material for the operator. The agent never sees it.

The run home is a directory **outside every AIP worktree**, for example `~/aip-v08-i4-run`. It holds
`src/` (the Sokol111 clones), `kafka/`, `aip/`, `workspace/`, one `claude-<session>/` config dir per
session, and `package/` (the run package, frozen into `i4-evidence/` in S5).

```bash
export I4_RUN_HOME=~/aip-v08-i4-run   # used by capture.sh
I4=<AIP checkout>/harness/v08/i4
```

## Agent isolation: what is enforced and what is audited

Checked on Claude Code 2.1.312 with a scratch config dir (I4a):
- `dontAsk` mode refuses every tool call that no allow rule covers.
- A `Read` deny rule on the AIP checkout also stops Bash commands that name a path under it.
- `Edit(...)` rules cover every file-writing tool. `Write(...)` rules are ignored.
- **Live seam check (I4a, scratch run home, C1 as B-R, AIP image from this branch):**
  - the project MCP server is approved under `dontAsk` (`enableAllProjectMcpServers`);
  - the agent calls `mcp__aip__get_binding_picture` with its arguments wrapped
    (`{"request": {...}}`), and the transcript stores the answer inline as JSON text;
  - the REST replay equals that answer after canonicalisation, and cited refs resolve;
  - `docker-compose.aip.yml`, `config.before.yaml` and `setup_run_home.sh before` give the nine C1
    rows.
- **The Bash sandbox is not available on this host** (`bubblewrap` and `socat` are missing), and
  `curl` to the internet goes through an allowed Bash. Network access is therefore not blocked:
  `audit.py` is the control, and it fails closed (§4.4).

## S1: bring-up and the before-wave state (operator)

1. Reset and bring up Sokol111 as in [handoff §2](../../../docs/specifications/0.8.0/i3-i4-handoff.md#2-reset-procedure-back-to-the-before-wave-state).
   Clone the repositories into `$I4_RUN_HOME/src/`. Do the before-state checks yourself.
2. **Nothing may need a fetch later:**
   - pull every pinned image now, including `apache/kafka:4.1.2@sha256:5cc2a2fd…`;
   - run `helm dependency build` in each chart of `src/ecommerce-infrastructure` that has
     dependencies.
3. Check how `rpk group list` and `rpk group describe` show an `Empty` group (handoff §4). Record
   what you find in `run-record.md`.
4. Start Kafka:
   - `$I4/setup_run_home.sh $I4_RUN_HOME kafka`;
   - `docker compose -p aip-v08-i4 --project-directory $I4_RUN_HOME/kafka -f $I4_RUN_HOME/kafka/docker-compose.kafka.yml --env-file /dev/null up -d`;
   - check that no topic exists on it.
5. Record the configuration of the moved services: `$I4/capture.sh helm before`.
6. Capture B-R: `$I4/capture.sh b-r`.
7. Start AIP with the before-wave profile:
   - build the image from the I4a merge commit: `export AIP_IMAGE=$(docker build -q <AIP checkout>)`,
     and record the ID in `observed-metadata.json`;
   - `$I4/setup_run_home.sh $I4_RUN_HOME before`;
   - `cd $I4_RUN_HOME && AIP_NEO4J_PASSWORD=… docker compose -f docker-compose.aip.yml up -d`
     (with `AIP_IMAGE` set);
   - `curl -X POST localhost:8000/api/import`.

   Check that the binding picture for `catalog-management` on `kafka:sokol111-local` gives the nine
   I2 §8.1 rows.

## S2: planning session (agent)

1. Run `$I4/setup_workspace.sh $I4_RUN_HOME planning`, then start the session as it prints.
2. Record the model id and `claude --version` in `package/agent-record.json`.
3. Give the first message from the task card. Do not intervene in the agent's work.
4. **Freeze the plan.** When the session ends:
   - `sha256sum workspace/plan.json workspace/plan.md` and `date -u +%FT%TZ` go to
     `$I4_RUN_HOME/plan-freeze.txt`;
   - copy `claude-planning/projects/` **recursively** (every `*.jsonl`, including subagent and
     tool-output files) to `package/transcripts/planning/`, and add the digests.

## S3: execution session (agent)

1. Run `$I4/setup_workspace.sh $I4_RUN_HOME execution`, then start the session with the task card's
   second message.
2. When the agent asks for the functional test, run the I3 driver
   (`harness/v08/i3/functional_test.py`) and give the agent its result.
3. Log every intervention (UTC, cause, action). Intervene for environment faults only.
4. At the end:
   - copy `claude-execution/projects/` recursively to `package/transcripts/execution/`;
   - check that `plan.json` and `plan.md` still have the frozen digests.

## S4: after-wave reads and scoring (operator)

Run the steps in this order. AIP answers only for the current snapshot.

1. **Audit:**
   `python3 $I4/audit.py --planning $(find package/transcripts/planning -name '*.jsonl') --execution $(find package/transcripts/execution -name '*.jsonl') --withheld <each AIP worktree> --config-dir $I4_RUN_HOME/claude-planning --config-dir $I4_RUN_HOME/claude-execution --out package/audit.json --requests-out package/agent-requests.json`.
   A hit invalidates the run (§4.4). Zero extracted requests while the plan cites AIP stops the
   next step.
2. **Before-wave answers**, with B-R still current:
   `python3 $I4/record_answers.py before --requests package/agent-requests.json --plan workspace/plan.json --out package/answers-before.json`.
3. **Configuration and ground truth:**
   - `$I4/capture.sh mm2-config`;
   - `$I4/capture.sh helm after`;
   - transcribe the agent-reported installed offsets into `package/agent-reported-handoff.json`, with
     the format in `ground_truth.py`;
   - `$I4/capture.sh ground-truth`.
4. **After-wave captures:** `$I4/capture.sh a-r` and `$I4/capture.sh a-k`.
5. **After-wave answers:**
   - `docker compose -f docker-compose.aip.yml down -v` (a clean graph);
   - `$I4/setup_run_home.sh $I4_RUN_HOME after`;
   - `up -d`, then the import;
   - `python3 $I4/record_answers.py after --out package/answers-after.json`;
   - Proof C: `python3 $I4/proof_c.py --recording package/answers-after.json --out package/proof-c.json`.
6. **Scoring:**
   - `python3 $I4/score.py --plan workspace/plan.json --amendments workspace/amendments.json --applied package/applied-mm2.json --helm-check package/applied-helm.json --verdicts package/owner-verdicts.json --out package/scoring.json`;
   - `python3 $I4/citations.py --plan workspace/plan.json --recording package/answers-before.json --scoring package/scoring.json --out package/citations.json`.

   The owner writes `owner-verdicts.json`: the K6/K8 sub-check verdicts, and a reason for each
   `DIFFERENT` or `MISSING`.

## S5: report, freeze, replay

1. Write `package/report-inputs.json` (the manifest in `report.py`), then run
   `python3 $I4/report.py package/report-inputs.json --out package/report.html`.
2. Freeze as in I3: sanitize → secret scan → `SHA256SUMS` → verify → commit.
3. Add the replay test (I4b).
