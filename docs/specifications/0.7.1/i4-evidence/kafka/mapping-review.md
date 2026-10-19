# Service-mapping review (I4 §3)

The mapping artifact [`mapping/kafka-service-mapping.json`](mapping/kafka-service-mapping.json) is
operator-reviewed evidence, separate from the broker capture. Its schema is closed, so the review
citations live here. All references are at
`hungCS22hcmiu/ecommerce-system@cd65365838ea880185a02e6536fa347439bfa274`, re-read for this check;
they match the October 2026 [mapping record](../../../../real-world-validation/v0.8.0/consumer-attribution-evidence/mapping.md).

| Group | Service | Configuration chain |
|---|---|---|
| `payment-service` | `payment-service` | `docker-compose.yml:174` `KAFKA_CONSUMER_GROUP: ${KAFKA_CONSUMER_GROUP:-payment-service}` (unset in this run, so the default applies) → `payment-service/config/config.go:43` → `payment-service/internal/kafka/consumer.go:81` `GroupID: cfg.KafkaConsumerGroup`, topic `consumer.go:80` `orders.created` |
| `order-service` | `order-service` | `order-service/src/main/resources/application.yaml:39` `group-id: order-service`; `PaymentEventConsumer.java:29` `@KafkaListener(topics = "payments.completed", groupId = "order-service")` and `:60` (`payments.failed`) |

Not mapped, on purpose:

- `ops-tail` is a stock `kafka-console-consumer` started by the operator ([`raw/00a`](raw/00a-start-ops-tail.meta)). No application configuration names it, so it has no Service.
- `analytics-tap` is outside the capture allow-list ([`raw/00b`](raw/00b-start-analytics-tap.meta)).

The mapping never uses group-name equality, container IPs, member ids, client ids or host text as
authority. The payment group is configurable, so the name alone would be a guess; the
configuration chain above is the authority.
