# Service mapping evidence (separate from the broker evidence)

All source references are at `hungCS22hcmiu/ecommerce-system@cd65365838ea880185a02e6536fa347439bfa274`.
The mapping never relies on the group string equalling the service name.

## payment-service ↔ group `payment-service` ↔ `orders.created`

| Link | Evidence |
|---|---|
| Group is **configurable**, so equality alone would be a guess | `docker-compose.yml:174` `KAFKA_CONSUMER_GROUP: ${KAFKA_CONSUMER_GROUP:-payment-service}`; `payment-service/config/config.go:43` `getEnv("KAFKA_CONSUMER_GROUP", "payment-service")` |
| The service's consumer uses that config value as the Kafka group | `payment-service/internal/kafka/consumer.go:81` `GroupID: cfg.KafkaConsumerGroup`; topic `consumer.go:80` `Topic: "orders.created"` |
| Runtime statement of the same fact | payment-service startup log: `kafka.consumer: started … "group":"payment-service","topic":"orders.created"` (container log, not captured as a raw file) |
| Broker member ↔ container, independent of any name | Member `CONSUMER-ID` `server@352697958a99 (github.com/segmentio/kafka-go)-…` (`raw/04`) embeds hostname `352697958a99`, which is container `ecommerce-payment-service`'s hostname and id prefix (`raw/15`); member `HOST /172.19.0.7` equals that container's IP on `hungcs-r6_backend` (`raw/11`) |

## order-service ↔ group `order-service` ↔ `payments.completed`, `payments.failed`

| Link | Evidence |
|---|---|
| Group declared in service config | `order-service/src/main/resources/application.yaml:39` `group-id: order-service` |
| Group and topics declared on the listeners | `order-service/src/main/java/com/ecommerce/order_service/kafka/PaymentEventConsumer.java:29` `@KafkaListener(topics = "payments.completed", groupId = "order-service")` and `:60` `… "payments.failed" …` |
| Broker member ↔ container | Members `consumer-order-service-1-…` (completed) and `consumer-order-service-2-…` (failed) both have `HOST /172.19.0.6` (`raw/05`), equal to `ecommerce-order-service`'s IP (`raw/12`). The consumer ids carry no hostname, so this link is by IP only |

## What the mapping does not establish

- Member HOST is a container IP at capture time; IPs are not stable identities across runs.
- For order-service the broker evidence names a client id derived from the group id, not the service. The Service link there is the config chain plus the IP join.
- Nothing here shows the services' behaviour (messages processed); no traffic was generated.
- A group id is not treated as a Service identity, and not as an AIP Subscription.
