# RabbitMQ semantic contrast (v0.7.1 I4 §4)

**Outcome: SOURCE_SPECIFIC; no MODEL_GAP.** This confirms the [I0 decision](../../i0-semantic-decision.md) §3 (D8) and makes one point of D1 precise: the native RabbitMQ consumer id must include the **channel number**. RabbitMQ stays a semantic contrast case in v0.7.1, with no adapter, no carrier and no narrowing.

**Evidence:**

- The [I0 spike](../../i0-spike/README.md) shapes S1–S4, in `i0-spike/rabbitmq/raw/`.
- A supplementary capture of two shapes I0 did not show, in [`raw/`](raw/). It used the same pinned image as I0 (`rabbitmq@sha256:606d8c0d…`, RabbitMQ 3.13.7) on 2026-10-19 from 09:15:45Z to 09:16:08Z. The setup is [`shapes_i4.py`](shapes_i4.py), with fake credentials only and local loopback; the container was removed afterwards.
  - S5: one connection, two channels, both consuming `q.s5` with the same tag `worker`.
  - S6: a queue `q.s1` in vhost `/` and another in vhost `v2`, one consumer each with tag `s6`.

Each step has a `.txt`, a `.meta` (UTC, command, exit code) and, if stderr was non-empty, an `.err`. `raw/failed-start-1/` holds an earlier attempt, started before the I4.3 plan existed: the broker crashed at start-up (`.erlang.cookie: eacces`) before any shape ran.

## §4 checks

| §4 point | Observed | Evidence |
|---|---|---|
| Native identity is vhost + queue + consumer tag + connection/channel scope, with no group | Every consumer is reported as queue (with vhost), tag and channel (connection name plus channel number). No group field exists | I0 `01-consumers`; `raw/04-consumers`, `raw/07-channels` |
| The tag is channel-scoped; two channels on one connection can reuse it | S5: two live consumers `/ q.s5 worker` on the same connection differ **only** by channel number (1, 2). So vhost + queue + tag + connection is not unique, and the channel number is required | `raw/04-consumers`, `raw/05-queues` (`q.s5`: 2 consumers) |
| The Queue is vhost-qualified | S6: `q.s1` exists in `/` and in `v2`, each with a consumer tagged `s6` on its own connection | `raw/04-consumers`, `raw/05-queues`, `raw/06-connections` |
| Multiple consumers compete without implying multiple Services | S1: two consumers on `q.s1` from one connection `svc-a`; S5 likewise | I0 `01-consumers` |
| Bindings express fan-out | S2: fanout exchange `x.s2` bound to `q.s2a` and `q.s2b`, one consumer each | I0 `03-bindings` |
| `consumers: 0` means zero live attachments at T, not "no Service consumes" | S4: `q.s4` is bound to `x.s4` with `consumers: 0` | I0 `02-queues`, `03-bindings` |
| Broker-side hints are not Service-mapping authority | `connection_name` is a client property set by the client (`svc-a` … `svc-f`); the user and peer address are shared or ephemeral | I0 `04-connections`; `raw/06-connections` |
| Public boundary | A RabbitMQ Queue id gives `NOT_ANSWERED / DESTINATION_NOT_KAFKA_TOPIC` on service, REST and negotiated MCP, never an empty Kafka list | `tests/integration/test_v071_i4_kafka_replay.py::test_a_rabbitmq_queue_is_not_a_kafka_topic_on_every_surface`, green in the qualification tier on candidate `df3a9e4` ([execution record](../../i4-execution-record.md)) |

## Classification

- **SOURCE_SPECIFIC** for attachment and consumer identity. A live consumer on a Queue is a RabbitMQ attachment, not a Kafka consumer group and not an AIP Subscription.
- **D1 made precise.** I0 D1 already allows ordered native id parts and notes that "the channel number is unique only within a connection". S5 shows that the channel number is a **necessary** part, not only a scoping note. A future RabbitMQ carrier's native id is therefore vhost, queue, consumer tag, connection and channel number. This is representable in the D1 envelope, so it is not a MODEL_GAP and needs no scope decision before I5.
- **Not covered:** attribution to a Service. As with Kafka, that needs an accepted independent mapping source; no broker-side field qualifies.
