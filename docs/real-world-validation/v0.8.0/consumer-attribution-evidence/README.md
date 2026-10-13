# Consumer attribution evidence-capture — result

**Spec:** [spec-consumer-attribution-evidence-capture.md](../spec-consumer-attribution-evidence-capture.md)  
**Detail:** [commands.md](commands.md) · [mapping.md](mapping.md) · [raw captures](raw/) (checksums in `SHA256SUMS`)  
**Date:** 2026-10-13

## Outcome: SUPPORTED EVIDENCE PATH

Independent broker-held state established that named consumer groups are attached to named topics, with
active member state, in one run; separate source/config evidence plus a runtime container join maps each
group to a Service without relying on name equality. The check does not decide the canonical abstraction.

## Result record (spec §5)

| Field | Content |
|---|---|
| System | `hungCS22hcmiu/ecommerce-system` @ `cd65365838ea880185a02e6536fa347439bfa274` |
| Environment | Local Docker Compose project `hungcs-r6`, network `hungcs-r6_backend`; Kafka `cp-kafka:7.5.0` with ZooKeeper; slice = postgres, redis, zookeeper, kafka, payment-service, order-service; captured 2026-10-13 21:48 UTC (see `raw/*.meta`); no traffic generated |
| Destination | Topics `orders.created`, `payments.completed`, `payments.failed` (3 partitions each; `raw/08`, `raw/09`) |
| Consumer identity | Kafka consumer group `payment-service` (1 member, topic `orders.created`) and group `order-service` (2 members: one on `payments.completed`, one on `payments.failed`), both `Stable` (`raw/02`–`raw/07`) |
| Broker evidence | `kafka-consumer-groups --describe/--members/--state` and `kafka-topics`, stored unchanged with timestamp, command and exit code (`raw/01`–`raw/09`) |
| Service mapping | payment: configurable group (`docker-compose.yml:174`, `config.go:43`) used as `GroupID` (`consumer.go:81`), member id embeds container hostname and HOST = container IP (`raw/04`, `raw/11`, `raw/15`). order: `application.yaml:39` and `@KafkaListener(groupId="order-service")` (`PaymentEventConsumer.java:29,60`), member HOST = container IP (`raw/05`, `raw/12`). Detail in [mapping.md](mapping.md) |
| Attribution supported? | **Yes**, as the qualified combination of the two separate claims, for this run |
| Remaining ambiguity | The order-service join is by container IP only (consumer ids carry no hostname). IPs and member ids are ephemeral. Observation is a single point in time on a local Compose run, not a window or a production environment. No messages were processed, so participation in actual delivery is not shown. Kafka CLI output is human-formatted text (a structured admin API would be needed for ingestion) |
| Semantic implication | See below |

## Decisive question

> Does independent broker state plus separately attributable source/config evidence support a Service↔consumer↔destination relationship without equating the broker-native consumer identity with an AIP Subscription?

**Yes.** Both groups were attached to the stated topics, and the Service link came from configuration and
runtime container identity, never from the group string equalling a service name. The payment group is
configurable by environment, which is exactly why the string alone would have been a guess.

## Semantic implication (what AIP would have to preserve; no model proposed)

- The **consumer-group id as a distinct broker-native identity**, not coerced to a Subscription, and the
  **member** level (a group can have several members, here `order-service` has two, one per topic).
- **Broker claim and Service-mapping claim as separate, separately qualified evidence**; the combination is derived.
- The **run/environment identity** and **capture time** of broker state (point-in-time, not a window).
- Mapping can depend on **deployment-resolved configuration** (a configurable group id), so a code default is
  not sufficient evidence.
- The runtime join keys observed (container hostname in a member id, member host address) are **ephemeral and
  vary per client library** (kafka-go embeds a hostname; the Spring client does not).
- Group state (`Stable`, member count) and topic assignment are available per group; lag, offsets and
  rebalancing were captured by the CLI but are out of scope.

## Scope notes

- Optional RabbitMQ cross-check: **not performed** (spec §6 says only if cheap; it was not attempted).
- One system, one run. The check shows an evidence path exists for Kafka; it does not show the path for
  RabbitMQ queues or Service Bus subscriptions, and it does not choose the cross-broker abstraction
  (promotion condition 5 stays open).
- No application, instrumentation, AIP semantics or product code changed. `*.err`: only `raw/14` (my invalid
  `docker images` invocation, kept as a record).
