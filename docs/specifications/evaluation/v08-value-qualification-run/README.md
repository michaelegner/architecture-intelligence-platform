# v0.8 value qualification: run evidence

The evidence of the 12 sessions of the [experiment](../v08-showcase-value-qualification-experiment.md).
The [result record](../v08-showcase-value-qualification-result.md) interprets it. `SHA256SUMS`
covers every file here except this README.

| Path | Content |
|---|---|
| `sessions/<type>_r<round>/` | `session.json`, `preflight.json` (and `broker-check.json` in F), `workspace/` (the agent's `plan.json`, `plan.md`, `answers.json` and, in T, `requests.json`), `requests-record.json` and `replies/` (T), `agent-requests.json`, `audit.json`, `scoring.json` (final, with the owner verdicts), `superseded/` (earlier outputs), `transcripts/` (sanitized) with `transcripts.sha256` and `transcripts.pre-sanitize.sha256` |
| `owner-verdicts/` | the verdict file given to the scorer for each session |
| `owner-review/` | the proposals with their reasons, the owner decisions and the basis of each verdict |
| `waivers.json` | the audit waivers, with the exact command and denial of each occurrence |
| `compare-final.json` | the criteria results (spec §5.4) with the owner verdicts |
| `compare-mechanical.json` | the same, before the owner verdicts |
| `sensitivity-row5.json` | the row 5 sensitivity analysis (not the official score) |
| `preflight-failed/` | the four preflight stops (two attempts) before an agent started |
| `raw/`, `images/`, `adaptations.diff` | the bring-up records (S1), the image inventory before and after, the recorded adaptation diff |
| `environment/` | the session log, the ledger of created resources, the snapshot id, the operator scripts |

The session dirs do not include the clones, the config dirs or the raw `claude -p` streams.
