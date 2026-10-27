# AIP v0.8 I3: Completion Record

**Status:** COMPLETE on merge of the I3b PR. The closure SHA is added in a follow-up only if the owner asks.
**Outcome:** `READY_FOR_I4` if the owner records it on merging the I3b PR.

This record covers the [I3 spec](i3-two-broker-environment-and-live-captures.md), Draft 0.2, under the [v0.8 specification](specification.md). Each slice's approved plan is kept verbatim in its PR description.

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I3 spec | [`i3-two-broker-environment-and-live-captures.md`](i3-two-broker-environment-and-live-captures.md), D13–D15 | #646 | `d85686e80f0d6ab475156d89238b92fda0522a04` | 2026-10-27T10:58:25Z |
| I3a | environment, MirrorMaker 2 workers, Helm overlays, preflight and runbook scripts, `checker.py`, after-wave declarations, `expected-after.json` with its digest | #647 | `ac930ec169147628a63de797b47eeb1ea72f280d` | 2026-10-27T15:55:43Z |
| I3b | the live run S1–S3, the frozen [`i3-evidence/`](i3-evidence/) package, `test_v080_i3b_replay.py`, this record, [`i3-i4-handoff.md`](i3-i4-handoff.md) | this PR | read from `gh pr view --json mergeCommit` after merge | |

The merge commits above were read from `gh pr view --json mergeCommit,mergedAt`. The live run used harness revisions `9a1af65`, `836e5f9` and `7e45f3f` of the I3b branch; [`observed-metadata.json`](i3-evidence/observed-metadata.json) says which stage ran on which.

## Acceptance (I3 §11)

| # | Status | Evidence |
|---|---|---|
| **C1** | Met | P1a, P3 ([`raw/P1a-p1a`, `raw/P3-p3`](i3-evidence/raw/)), P4 attempt 2 (exit codes of [`raw/P4-*`](i3-evidence/raw/); attempt 1 failed on a harness race and is kept), P5 with its teardown ([`raw/P5-sync.check.json`](i3-evidence/raw/P5-sync.check.json)); P1b at each flow's first start (`02-`, `07-`, `P5-*-p1b.check.json`) |
| **C2** | Met | the §4.2 protocol ran end to end in steps 1–9; [`checks.json`](i3-evidence/checks.json) holds 22 verdicts, all `PASSED`, each with its inputs, rule and sources |
| **C3** | Met | replication per source partition (`02-replication`, `09-replication-b`); hand-off (a), checkpoint and (c) per group and partition (`06-handoff`: 1, 1 → 1, 1 for Catalog and Image). The replay amount is `NO_BOUND` by the committed rule (the only offset sync is 0 → 0); the end offsets of both brokers equal (a) and (c) (`06-*-tenant-end`), so no record lay after the installed offset |
| **C4** | Met | C1′, A-R and A-K in [`captures/`](i3-evidence/captures/), each with G and G′ in `raw/` that are byte-identical. The moved groups read `Empty` on Redpanda (`04-groups-state`, `AR-moved-state`). The Redpanda allow-list is unchanged |
| **C5** | Met | [`raw/FT-functional.check.json`](i3-evidence/raw/FT-functional.check.json): all three §6 steps passed through the services' Connect-RPC endpoints, recorded apart from AIP's claims; no token or password in any record |
| **C6** | Met | `tests/integration/test_v080_i3b_replay.py` (qualification tier): A-R and A-K give exactly the `expected-after.json` rows and limitations, and a second import is a no-op (no graph revision advance, the same answer). C1′ gives exactly the nine I2 §8.1 rows. Using C1′ in place of A-R fails the test |
| **C7** | Met | `expected-after.json` still hashes to `expected-after.sha256` from I3a; git shows both unchanged. The replay test checks the digest and `SHA256SUMS` |

## Decisions and deviations

| # | What | Where |
|---|---|---|
| 1 | Tokens from the environment's own Logto M2M apps, as its seeder gets them: `platform-service` for `RegisterTenant`, `ecommerce-service` (`cross-tenant`, `tenants:read`) with `X-Tenant-Slug` for everything else; no user login | I3b plan, `9a1af65`, `836e5f9` |
| 2 | MinIO from Bitnami's frozen builds, pinned by digest, because the upstream images and binaries are gone (owner decision, S1) | run record S1 |
| 3 | `logto-seed` run a second time: the first run stores no client secrets with Logto 1.45.0 | run record S1 |
| 4 | Host DNS: `127.0.0.1` plus the ingress `Host` header (`--connect-to`) | run record S1, `836e5f9` |
| 5 | P4 got a bounded broker wait after attempt 1 failed on a race (owner decision, S2) | run record S2, `7e45f3f` |
| 6 | The checker's hand-made inputs are inline in its unit test, not in a fixture directory | I3a README |
| 7 | The new catalog records after the cut-over are the functional test's shop (its seeder Job), not duplicates; the `event_id`s on Redpanda are unique | run record S3 |
| 8 | Environment torn down after the freeze, removing only what this run created (owner decision) | run record S4 |
| 9 | P5's teardown now removes the probe container's anonymous volumes (`rm -sfv`); found during the I3b teardown, after the run | run record S4 |
