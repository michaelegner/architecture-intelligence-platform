# AIP v0.8 I4b: Completion Record

**Status:** COMPLETE on merge of the I4b PR. The closure SHA is added in a follow-up only if the owner asks.
**Outcome:** recorded by the owner on merging the I4b PR. The run is valid (every audit hit waived
with evidence); E4 and E6 are not met and are recorded as failures; E8 is qualified: the replay
passed, but strict E8 is not fully met (owner-accepted deviation 9, below).

This record covers I4b of the [I4 spec](i4-agent-run-report-and-release.md), Draft 0.3, under the
[v0.8 specification](specification.md). Each slice's approved plan is kept verbatim in its PR
description. I4c (the release, E9) follows.

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I4 spec | [`i4-agent-run-report-and-release.md`](i4-agent-run-report-and-release.md), D16–D19 | #650 | `debe76d6d69b14b08977fd6d12854774b8e2ff5c` | 2026-10-28T07:31:06Z |
| I4a | the plan key and the task card with their digests, the agent setup, the operator tooling, the scorer, the citation checker and the report generator | #651 | `b0c6f9dc4237d59b9aaf9bfd378ea0dfc112f9a4` | 2026-10-28T10:25:06Z |
| I4b | the live run S1–S5, the frozen [`i4-evidence/`](i4-evidence/) package, `test_v080_i4b_replay.py`, this record, [`i4-i4c-handoff.md`](i4-i4c-handoff.md) | this PR | read from `gh pr view --json mergeCommit` after merge | |

The merge commits above were read from `gh pr view --json mergeCommit,mergedAt`. AIP ran as the
image built from `b0c6f9d`; the harness revisions per stage are in
[`observed-metadata.json`](i4-evidence/observed-metadata.json). The agent was `claude-opus-5-5` in
Claude Code 2.1.312, headless.

## Acceptance (I4 §12)

| # | Status | Evidence |
|---|---|---|
| **E1** | Met | `plan-key.json` and `task-card.md` hash to their I4a digests and git shows them unchanged; `expected-after.json` hashes to the §3 digest (`proof_c.check_reference_digest`, the replay test) |
| **E2** | Met | Plan frozen at 2026-10-28T12:59:16Z ([`plan-freeze.txt`](i4-evidence/plan-freeze.txt)), before the execution session started (13:09:45Z); the digests still held at the end of S3. Both transcripts are kept, and planning attempt 1. [`audit.json`](i4-evidence/audit.json): 6 hits, all `PLANNING_CHANGE` from two planning commands refused before they ran; each waived by the owner with the refused result as evidence ([`agent-record.json`](i4-evidence/agent-record.json)). Attempt 1: 0 hits |
| **E3** | Met | [`scoring.json`](i4-evidence/scoring.json): K1–K5 and K7 `MATCHED`; K6/K8 sub-checks 4 `MATCHED`, 6 `DIFFERENT`, 1 `MISSING`, each with the owner's reason ([`owner-verdicts.json`](i4-evidence/owner-verdicts.json)) |
| **E4** | **Not met** | [`citations.json`](i4-evidence/citations.json): K1–K4 `COVERED`; no mechanism item without an implementation justification; one citation does not resolve: REPORT-01 cites a snapshot id only, with no row and no ref. Recorded as a Proof B failure |
| **E5** | Met | [`proof-c.json`](i4-evidence/proof-c.json) `PASSED` (A-R and A-K reproduce `expected-after.json`); B-R gives the nine I2 §8.1 rows and their four limitations (run record S1) |
| **E6** | **Not met** | [`e6-gate.json`](i4-evidence/e6-gate.json) `FAILED` on 2 of 12 verdicts: `applied-mm2.json` (P2: checkpoints off on the kafka→redpanda flow) and `p1b-kafka-to-redpanda.json` (its checkpoints topic is never created), the same choice of the agent. Passed: the functional test, P1a/P3, P1b redpanda→kafka, K7, replication for both pairs, lag for all four consumers, the hand-off. Recorded as FAILED by owner decision; all are recorded apart from AIP's claims |
| **E7** | Met | [`report.html`](i4-evidence/report.html): the four parts, the five questions, a requirement chain for each crossing row after the wave, the disclosures; the wording guard passes |
| **E8** | **Qualified: replay passed; strict E8 not fully met** (owner-accepted deviation 9) | `tests/integration/test_v080_i4b_replay.py` (qualification tier) passes: the nine binding rows, every answer field apart from the snapshot block and the evidence refs, Proof C, and the byte-identical report. Tampering with one recorded answer field and one capture field fails all four tests. **Not verified:** §9 phase 1's exact equality with the recorded answers (the snapshot ids and the evidence refs, which depend on the absolute input paths, are compared only as ref counts per kind), and fresh citation resolution against the replayed snapshot (`citations.check` runs on the frozen recording only) |

## Decisions and deviations

| # | What | Where |
|---|---|---|
| 1 | Agent model `claude-opus-5-5`; the operator drives both sessions headless (`claude -p`, `--resume` for each turn) with a clean `env -i` launch | owner, I4b plan |
| 2 | The I3b host adaptations again, plus Logto pinned by digest (handoff §2.2); `logto-seed` run a second time | run record S1 |
| 3 | `Empty` groups are listed by `rpk group list` on this Redpanda; absence reads as "not listed" or `describe` `Dead` | run record S1 |
| 4 | Planning attempt 1 wrote no plan: the relative `Edit(./plan.json)` rule followed the agent's Bash `cd` (H3). Rules made absolute; attempt 2 ran on a new workspace and config dir (owner decision) | run record S2 |
| 5 | Two owner decisions under the stop rule after the agent's CHK-01 failed (MirrorMaker 2 refused the reverse-flow connectors; then `heartbeats` mirrored both ways): the agent continued with its own fixes as amendments | run record S3, `interventions.txt` |
| 6 | The owner waived the 6 audit hits (refused planning commands, no content returned) | run record S4 |
| 7 | E6 recorded FAILED (owner decision); S4 and S5 continued | run record S4 |
| 8 | Harness fixes found during the run, each unit-tested: H1 untagged images in the inventory; H2 no canary in the run home; H3 absolute plan-file rules; H4 `docker top -eo pid,args`; H5 a container without MirrorMaker 2; H6 the offset-syncs topic name with `location=target`; H7 the ground-truth pair loop; the `capture.sh p1b` step and `e6_gate.py` (owner review). The report lists each intervention with its cause. Frozen file names use `-to-` in place of `->` | `b264dd3`, `12bb476`, `3cb9f5f`, this PR |
| 9 | AIP's snapshot id is a digest of the graph state, which holds each declaration's absolute `source_file`. The run read `/app/sokol111-v08/...`; a replay reads the checkout. The replay therefore compares the answers without the snapshot block and with the evidence refs reduced to their count per kind; every other field is equal. The citation check runs on the frozen recording. No AIP change in I4 | run record S5, the replay test |
| 10 | Environment torn down after the freeze (owner decision), removing only what the ledger lists, the agent's `catalog-move-mm2` and its volumes, the AIP image and the H3 probe directories included | owner, run record S5 |

## Follow-ups (not in I4b)

- The snapshot id depends on the absolute input paths (deviation 9). Whether AIP should fingerprint
  a path-independent locator is for the owner to decide.
- The report shows the applied MirrorMaker 2 verdict but not the E6 gate or P1b by name.
