# v0.8 value qualification: harness

The harness of the [experiment](../../../docs/specifications/evaluation/v08-showcase-value-qualification-experiment.md).
It reuses the v0.8 I4 harness (`../i4/`) by path. The only change there is the `allowed_files`
parameter of `audit.audit_session` (default unchanged).

| Script | Step |
|---|---|
| `make_cards.py` | builds the card variants and settings templates (frozen; kept for provenance) |
| `vq_setup_session.sh RUN_HOME TYPE ROUND` | a new session dir `RUN_HOME/sessions/<TYPE>_r<ROUND>/` with its workspace and config dir |
| `vq_preflight.py RUN_HOME SESSION` | the checks before each session (fails closed) |
| `vq_aip.sh RUN_HOME up\|down\|check` | AIP started with the recorded snapshot, or removed |
| `vq_broker_check.py` | the broker state check against `catalogue/R1.txt` |
| `vq_requests.py answer RUN_HOME SESSION` | the reply to `requests.json` (T only) |
| `vq_audit.py RUN_HOME SESSION TRANSCRIPT...` | the audit |
| `vq_score.py RUN_HOME SESSION TRANSCRIPT... [--verdicts FILE]` | the scores of one session |
| `vq_compare.py --out FILE SCORING...` | the criteria over all valid sessions |

## Run (stage B)

The run home is outside every AIP worktree. It holds `src/` (the 16 clones at the freeze commits),
the v0.8 environment (`../i4/README.md`, S1), and `sessions/`.

1. Remove `/tmp/pytest-of-*` (unit-test trees that the host scan finds), then bring up as in v0.8
   S1, with the same pins. `vq_aip.sh RUN_HOME up` records the snapshot id.
   `vq_broker_check.py --out RUN_HOME/package/broker-check.json` must pass (inside `package/`, which
   every session is denied). Copy the recorded adaptation diff (`git diff` of the clone after S1) to
   `RUN_HOME/package/adaptations.diff`: the preflight accepts those changes and no other.
2. Each round runs T−, T+, F−, F+. Per session:
   - `-`: `vq_aip.sh RUN_HOME down`; `+`: `vq_aip.sh RUN_HOME up`;
   - `vq_setup_session.sh RUN_HOME TYPE ROUND`, then `vq_preflight.py RUN_HOME SESSION`;
   - start the session in the workspace, in the same form every time:
     `env -i "HOME=$HOME" "PATH=$PATH" "CLAUDE_CONFIG_DIR=<session>/claude" CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 claude -p --model <model id> --output-format json "<first message>"`
     (quoted: `PATH` can hold spaces);
   - T: when the agent ends with `OPERATOR: please answer requests.json`, run `vq_requests.py`
     and send the reply file unchanged with `claude -p --resume <session id> "$(cat <reply file>)"`
     in the same form;
   - copy `<session>/claude/projects/` recursively to `<session>/transcripts/`; give `vq_audit.py`
     and `vq_score.py` every `*.jsonl` of the session. A resumed run appends to the same file
     (checked with Claude Code 2.1.312); a repeated entry is read once.
3. `vq_audit.py`, then `vq_score.py`. The owner writes the verdicts file: K6/K8 sub-checks, Q4, Q5,
   and the claims in `pending_owner`, each with a reason.
4. `vq_compare.py` over the 12 valid scorings.
