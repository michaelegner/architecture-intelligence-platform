# Real Kafka replay package (v0.7.1 I4.1)

Frozen inputs of the I4 real-system check ([I4 spec](../../i4-deterministic-real-system-and-product-value-qualification.md) §2, §3). The committed bytes are the inputs; re-running the session does not reproduce them (member ids, hosts, T). Commands: [commands.md](commands.md). Digests: [`SHA256SUMS`](SHA256SUMS), [`replay-metadata.json`](replay-metadata.json).

## Pins

| Item | Value |
|---|---|
| System | `hungCS22hcmiu/ecommerce-system@cd65365838ea880185a02e6536fa347439bfa274`, slice postgres, redis, zookeeper, kafka, payment-service, order-service |
| Kafka | `confluentinc/cp-kafka:7.5.0@sha256:fbbb6fa11b258a88b83f54d4f0bddfcffbf2279f99d66a843486e3da7bdfbf41`, version `7.5.0-ccs` |
| Capture | `harness/kafka-capture/capture.py`, `confluent-kafka==2.16.0`, broker id `kafka:ecommerce-local`, environment `local`, allow-list `order-service`, `payment-service`, `ops-tail` |
| C1 | T `2026-10-19T06:21:23Z`, all three groups `Stable` |
| C2 | T `2026-10-19T06:23:28Z`; `payment-service` and `ops-tail` `Empty` with committed offsets, `order-service` `Stable` |

## Real versus derived

| Input | Origin |
|---|---|
| C1, C2 | **real** broker-held state, captured once each |
| `raw/` | **real** stock `kafka-consumer-groups`/`kafka-topics` output (ground truth G1, G1', G2, G2') |
| `C1-incomplete` | **derived**: C1 with `complete: false`, built in a temporary copy by the replay test; not independently observed |
| declarations, mapping, `expected.json` | authored: AsyncAPI from the source, the mapping from the configuration ([review](mapping-review.md)), the expectations from G1/G2 and the configuration |

Two extra groups are the operator's stock console consumers: `ops-tail` on `orders.created` (allow-listed, no Service, so `UNRESOLVED`), and `analytics-tap` on `payments.completed` (outside the allow-list, so it must never appear).

## Ordering

The git history shows the order:

1. `expected.json` (C1 part) and `EXPECTED.sha256` were committed with G1 before C1 was captured.
2. The C2 part was committed with G2 before C2 was captured.

G1, C1 and G1' match exactly: the same members and assignments. The G2 states match C2 and G2'. Offsets were committed by real traffic: six `orders.created` events from the repository's own `script/test/gen_kafka_payloads.py`, processed by payment-service. That happened while the consumers were attached, and they were stopped only afterwards. `--reset-offsets` was not used.

## Replay

- `tests/integration/test_v071_i4_kafka_replay.py` (qualification tier) imports these files through `run_all_configured_sources`. It compares every answer with `expected.json` on service, REST and negotiated MCP.
- [`ab_replay.py`](ab_replay.py) runs it twice from clean state and byte-compares the full output.

## Finding

The `harness/kafka-capture/README.md` command failed from a fresh checkout with `ModuleNotFoundError: app` ([`raw/12a`](raw/12a-c1-capture-failed-readme-command.err)); it needs `PYTHONPATH=.`. The README is corrected in the same PR. No capture content was affected.
