# AIP v0.8 I3 → I4 Handoff

Governing: [I3 spec](i3-two-broker-environment-and-live-captures.md) §12 (D14) and the [v0.8 specification](specification.md) §7 (I4).

I3's scripted run qualified the environment and the protocol and froze the reference. In I4 the
agent carries out the wave itself (Proof C): it chooses each next action, inspects each
precondition and stops on a failed check. Its captures must reproduce `expected-after.json`.

## 1. What I4 receives

| Item | Where | Notes |
|---|---|---|
| Reference answer | [`i3-evidence/expected-after.json`](i3-evidence/expected-after.json) (digest in `expected-after.sha256`) | committed before the I3 run; I3's real A-R and A-K reproduce it (`test_v080_i3b_replay.py`). It is the scoring key |
| Reference runbook | `harness/v08/i3/` (preflight, `steps/01.sh` … `09.sh`, `capture.sh`, `functional_test.py`, `checker.py`) and the [package README](i3-evidence/README.md) | what the agent may see is for the I4 spec (§1.1) |
| How the reference run went | [`i3-evidence/run-record.md`](i3-evidence/run-record.md) | every finding and decision, with its time |
| Image references | [package README, Pins](i3-evidence/README.md#pins) and [`observed-metadata.json`](i3-evidence/observed-metadata.json) | use these; never pull `latest` |

### 1.1 Open for the I4 spec (owner, 2026-10-27)

1. **Independent agent planning.** The answer key, the reference runbook and the run record must
   not predetermine the agent's plan. The I4 spec states explicitly what the agent may see before
   and during planning, and how the record shows that the plan was the agent's own.
2. **Clear architectural consequence.** The report connects each cross-boundary binding the wave
   establishes to the migration requirement it creates.

## 2. Reset procedure (back to the before-wave state)

**For the operator.** It prepares the environment; it is not material for the agent.

The I3 environment was torn down after the freeze, so I4 starts with a fresh bring-up.

1. **Sources and tools.** Clone the 16 Sokol111 repositories at the [v0.7.2 freeze](../0.7.2/i2-evidence/sokol111/freeze.md) commits. Install k3d v5.9.0, Tilt v0.37.8 and Helm v3.22.0 and check their published SHA-256 sums. Point `KUBECONFIG`, `MCP_KUBECONFIG` and the Helm homes to a scratch directory.
2. **Adaptations, in the local clone only.** Apply the six listed in the package README:
   - the k3d CA path and `fail-cgroupv1=false`;
   - `logto-seed` without `network: host`;
   - the pinned Bitnami MinIO images with their `storage.yml` changes ([`raw/S1-07`](i3-evidence/raw/S1-07-adaptation-minio.txt));
   - a host that cannot resolve `*.127.0.0.1.nip.io` uses `127.0.0.1` plus `Host`.
3. **Bring-up.**
   - Run `make cluster-inject-ca`, then `make init`. The CA bundle must exist before the cluster is created.
   - Run `tilt up` for the five Go services, the seeder, `minio`, `minio-init` and `imgproxy`.
   - If the tenant service reports `couldn't find key tenant-m2m-client-secret`, run `tilt trigger logto-seed` once.
4. **Traffic.** Register one shop with `RegisterTenant` (the platform token, `tokens/token.py platform`). Its seeder Job builds the demo catalog.
5. **Stop Tilt** with SIGINT. Never run `tilt down`: it removes the Compose stacks, Redpanda included.
6. **Before-wave state checks.** The agent must confirm all of these before step 1:
   - the four groups (Catalog, Category Query, Image, Product Query) are `Stable` on Redpanda with lag 0;
   - no `aip-v08-i3` container exists, and no `catalog.*` topic exists on Kafka;
   - a capture of Redpanda gives the nine I2 §8.1 rows (as C1′ did).

## 3. Rules I4 must keep

Whether the agent sees §3 and §4 is decided by the I4 spec (§1.1).

- The Redpanda allow-list stays the same before and after the wave; A-K covers Catalog and Image.
- A capture that cannot describe a group is incomplete and is rejected; an acquisition failure is never read as a detachment (parent §4.3).
- Delivery through MirrorMaker 2 is checked by the broker tools and the functional test, never by AIP (parent §4.4).
- The replay amount is measured or estimated from recorded positions; `offset.lag.max` is not a bound.
- Every adaptation is disclosed; nothing is committed to a Sokol111 repository.
- Remove only what the run created (check before deleting by name).

## 4. Known behaviour from the reference run

- The functional test's `RegisterTenant` starts a seeder Job for the test shop. So after the cut-over, Kafka holds that shop's whole demo catalog. These records are new, not duplicates.
- `GetRegistrationStatus` needs `tenants:read`. `token.py ecommerce` requests it.
- MM2's internal topics appear after the worker starts. P1b polls until its deadline.
- `apache/kafka` declares `VOLUME`s: removing an MM2 container needs `-v` (P5 now uses `rm -sfv`), or its anonymous volumes remain.
- One check attempt collects for about 20 s (two topic dumps with a 10 s consumer timeout each). A verdict can therefore be evaluated after the 40 s deadline when the attempt began before it.
