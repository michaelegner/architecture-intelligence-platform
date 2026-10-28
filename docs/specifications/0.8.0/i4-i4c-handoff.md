# AIP v0.8 I4 → I4c Handoff

Governing: [I4 spec](i4-agent-run-report-and-release.md) §13 (I4c, E9) and the
[v0.8 specification](specification.md).

## 1. What I4c receives

| Item | Where | Notes |
|---|---|---|
| The showcase report | [`i4-evidence/report.html`](i4-evidence/report.html) | built only from frozen inputs; the replay test renders it byte for byte |
| The run package | [`i4-evidence/`](i4-evidence/) with `SHA256SUMS` | sanitized (`<run home>`, `<AIP checkout>`), secret-scanned before the digests |
| The outcome | [`i4-completion-record.md`](i4-completion-record.md) | E1–E3, E5, E7 met; **E4 and E6 not met**, recorded as failures; **E8 qualified**: replay passed, strict E8 not fully met (owner-accepted deviation 9) |
| The replay | `tests/integration/test_v080_i4b_replay.py` | qualification tier |

## 2. What I4c must keep in its release-facing text

- The run's results as recorded: Proof A with the owner's verdicts (6 `DIFFERENT`, 1 `MISSING`),
  Proof B failed on one unresolved citation, E6 failed on the reverse flow's checkpoints, two owner
  decisions under the stop rule. A release note must not describe the run as a full pass.
- Delivery across the brokers is established by the broker tools and the functional test, never by
  AIP; the agent and the report make no lossless or exactly-once claim.
- The snapshot ids in the package depend on the absolute paths AIP read (completion record,
  deviation 9). E8 is qualified: the replay does not verify exact equality of the snapshot ids and
  evidence refs, nor fresh citation resolution against the replayed snapshot. Release text keeps
  this qualification next to the E4 and E6 failures and must not claim byte-identical replay of
  AIP's answers.

## 3. Known behaviour

- MirrorMaker 2 4.1.2 refuses a flow with `emit.offset-syncs.enabled=false`, and adds `heartbeats`
  to every flow unless `heartbeats.replication.enabled=false` (the agent's findings, run record S3).
- With `offset-syncs.topic.location = target`, the offset-syncs topic is named after the source
  alias (H6).
- A relative permission rule in Claude Code follows the session's Bash working directory (H3).
