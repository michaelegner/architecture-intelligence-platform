# v0.8 I1 evidence package

These are the frozen declared inputs of the v0.8 showcase ([I1 spec](../i1-declared-side-and-inventory.md) §8). Digests are in [`SHA256SUMS`](SHA256SUMS).

## Real versus authored

| Input | Origin |
|---|---|
| `c1/kafka-consumer-state.json` | **Real.** Byte copy of the v0.7.2 C1 capture ([v0.7.2 package](../../0.7.2/i2-evidence/sokol111/README.md), T `2026-10-21T17:53:57Z`); the replay test checks its digest against the v0.7.2 `SHA256SUMS` |
| `declarations/sokol111-local/` | **Authored** from each Service's `*-service-api` `pkg/events/topics.go` (I1 spec §4.2): the five Services, the pre-wave producers (`publish`) and their Topics on Redpanda. No declaration names a consumer |
| `declarations/sokol111-kafka/` | **Authored** inventory of the target broker: the four Topics without operations. The server `url` (`kafka:9092`) is a placeholder; only `x-aip-broker-id` is identity |
| `mapping/` | **Authored** from the environment configuration ([review](mapping-review.md)) |
| [`../i1-vectors/ids.json`](../i1-vectors/ids.json) | **Computed** by [`vector-hashes.py`](../i1-vectors/vector-hashes.py), hashlib only; next to the spec, as in earlier releases |

## Pins

The Sokol111 revisions are those of the [v0.7.2 freeze](../../0.7.2/i2-evidence/sokol111/freeze.md). Each declaration's `info.description` names the repository, commit and file it was authored from.

## Replay

- `tests/integration/test_v080_i1_declarations.py` (A6): both declaration sets in one snapshot, no Service or Topic conflict.
- `tests/integration/test_v080_i1_c1_replay.py` (A7, qualification tier): C1 with the Redpanda set and mapping persists and resolves all nine attachments of the parent specification §3.5.

[`config.yaml`](config.yaml) is the matching hosted profile.
