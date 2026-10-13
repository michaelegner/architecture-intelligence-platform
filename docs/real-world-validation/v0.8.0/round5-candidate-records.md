# Round 5 — Candidate records

**Spec:** [spec-round5-broker-semantic-gap-validation.md](spec-round5-broker-semantic-gap-validation.md) §3, §4, §6  
**Method:** lightweight static inspection of shallow clones (2026-10-13) plus one AIP probe of the
hand-emitted RabbitMQ span profiles ([`round5-evidence/`](round5-evidence/)). No live runs, no agent
baselines (spec §4 asks only for inspection). Source-known relationships were recorded from the
code **before** the probe was run. Round 4 cases are carried over as evidence, not rerun.

Frozen revisions (default branch HEAD, read with `git rev-parse HEAD` at clone time):

| Repository | Commit | Commit date |
|---|---|---|
| `JYC11/koupang` | `0cd5cea289c94652f8138a8f11cdd4273a80f0e8` | 2026-04-03 |
| `hungCS22hcmiu/ecommerce-system` | `cd65365838ea880185a02e6536fa347439bfa274` | 2026-05-26 |
| `daonhan/Microservices-in-.NET` | `2194f5f99b8879cead48b7f734b6780f1774a1cf` | 2026-06-24 |
| `dotnet/eShop` | `dc7ea499cd356924fb6689b3702964a5869dbae9` | 2026-10-01 |
| `mehdihadeli/food-delivery-microservices` | `dbcb5a22dbc6715a57bd2191f7c3de56c39d328b` | 2026-10-11 |

## Records

### JYC11/koupang (Rust)

| Field | Content |
|---|---|
| Broker model | Kafka |
| Bounded change | `OrderCreated` on `orders.events` (Round 3) |
| Source-known relationship | Each service registers one consumer with a literal `group_id` (`catalog-service`, `order-service`, `payment-service`) in `*/src/main.rs`; topics are documented in `docs/`; `CLAUDE.md` per service. One consumer group = one service |
| Independent evidence | OTel layer exists (`shared/src/observability.rs`, tracing-opentelemetry) but no `messaging.*` attribute is set anywhere in `*.rs`. Broker-held group state is capturable (Kafka in `docker-compose.infra.yml`) but was not captured |
| Missing AIP distinction | Consumer attribution: group → Service (same as Sokol111) |
| Classification | **SEMANTIC_GAP** (consumer attribution, Kafka) with **INSUFFICIENT_EVIDENCE** for runtime participation (no messaging spans captured or emitted) |
| Recurs Round 4 finding? | Kafka attribution |
| Product relevance | Which services consume an event is the core change-impact question; here source already answers it (strong agent docs) |
| Follow-up | Qualify further (live describe-groups capture) |

### hungCS22hcmiu/ecommerce-system (Go/Java/Python)

| Field | Content |
|---|---|
| Broker model | Kafka |
| Bounded change | `orders.created` (Round 3) |
| Source-known relationship | `order-service` group `order-service` (`application.yaml:39`, `@KafkaListener(groupId="order-service")` on `payments.completed/failed`); `payment-service` group from `cfg.KafkaConsumerGroup` (`internal/kafka/consumer.go:81`) |
| Independent evidence | No OpenTelemetry instrumentation of messaging (only indirect `otelhttp` in `go.mod`). Broker group state is already queried by the repository's own script (`script/test/phase1_run.sh`: `kafka-consumer-groups --describe`), so it is cheaply capturable |
| Missing AIP distinction | Consumer attribution: group → Service |
| Classification | **SEMANTIC_GAP** (consumer attribution, Kafka); runtime spans **INSUFFICIENT_EVIDENCE** |
| Recurs Round 4 finding? | Kafka attribution |
| Product relevance | As koupang |
| Follow-up | Qualify further |

### dotnet/eShop (RabbitMQ)

| Field | Content |
|---|---|
| Broker model | RabbitMQ, one **direct** exchange `eshop_event_bus`, routing key = event type name, one durable **queue per service** (`SubscriptionClientName`: `Catalog`, `Basket`, `Webhooks`, `OrderProcessor`, …) bound once per subscribed event (`src/EventBusRabbitMQ/RabbitMQEventBus.cs`) |
| Bounded change | `OrderStatusChangedToPaidIntegrationEvent` (Round 3) |
| Source-known relationship | Publisher, subscribers and their queues are explicit in code and `appsettings.json`; queue name is the service's subscription client name |
| Independent evidence | Hand-instrumented spans (both `ActivityKind.Client`): `messaging.system=rabbitmq`, `messaging.destination_kind=queue`, `messaging.operation=publish|receive`, `messaging.destination.name=<routing key>` and `messaging.rabbitmq.routing_key`. **The destination name is the routing key (event type), not the queue** |
| AIP probe | Spans are ignored as emitted (`messaging.operation` is not read; only `messaging.operation.type` send/receive/process). With that one key added, AIP records `SENDS` and `RECEIVES_FROM` an **observed-only Queue named after the event type** shared by publisher and consumer, i.e. a point-to-point queue that does not exist |
| Missing AIP distinction | Destination identity (exchange + routing key) distinct from the consumer endpoint (per-service queue) and the binding between them |
| Classification | **SEMANTIC_GAP** (destination identity / route-binding) plus **INGESTION_GAP** (operation key) |
| Recurs Round 4 finding? | Routing/binding (simple routing key rather than header predicate) and consumer attribution via queue |
| Product relevance | High: the consumer set of an event is exactly "queues bound with that routing key" |
| Follow-up | Candidate semantic completion; also record the observed-only-Queue hazard (§ synthesis) |

### daonhan/Microservices-in-.NET (RabbitMQ or Azure Service Bus)

| Field | Content |
|---|---|
| Broker model | RabbitMQ (**fanout** exchange, per-service queue bound with routing key = event name, which a fanout exchange ignores) and Azure Service Bus (one topic `ecommerce-topic`, one Subscription per service) |
| Bounded change | `OrderCreatedEvent` (Round 3) |
| Source-known relationship | Explicit in `shared-libs/ECommerce.Shared.RabbitMq/Impl/RabbitMqHostedService.cs`, `…AzureServiceBus/Impl/AzureServiceBusHostedService.cs` (`CreateProcessor(topic, subscriptionName)`), plus `AGENTS.md`/`CLAUDE.md`/ADRs |
| Independent evidence | RabbitMQ spans: `messaging.system=rabbitmq`, `messaging.operation.name=publish|receive`, `messaging.destination.name=<event name>`; no `messaging.operation.type`. Service Bus mode relies on the Azure SDK's own instrumentation (not inspected) |
| AIP probe | As emitted: ignored. With `operation.type` added and a declared Topic named after the event: producer `PUBLISHES_TO` Topic is OBSERVED; consumer stays `unresolved_destination_semantics` (no Subscription identity on the span). The fanout shape itself matches the supported Pitstop topology (declared Topic + named Subscription overlays) |
| Missing AIP distinction | Service Bus mode: none (**SUPPORTED** shape). RabbitMQ mode: consumer attribution from the queue the consumer owns; the binding key is irrelevant on fanout |
| Classification | ASB mode **SUPPORTED**; RabbitMQ mode **INGESTION_GAP** (operation key) + **SEMANTIC_GAP** (consumer attribution at runtime); binding key **BROKER_SPECIFIC_DETAIL** |
| Recurs Round 4 finding? | Kafka-style consumer attribution (queue instead of group); routing predicate: no |
| Product relevance | High for the consumer-set question; the provider switch shows the same question has different identity per broker |
| Follow-up | Candidate qualifier (has a SUPPORTED control and an unsupported sibling in one codebase) |

### mehdihadeli/food-delivery-microservices (RabbitMQ via Wolverine)

| Field | Content |
|---|---|
| Broker model | RabbitMQ through Wolverine conventions (`PublishToPrimaryExchange<T>`, `ListenToPrimaryExchange<T>`) |
| Bounded change | An order/product integration event (Round 3) |
| Source-known relationship | Per-service topology declared in `*/WolverineExtensions.cs` (e.g. Catalogs publishes `ProductCreatedV1`; Customers listens); EventCatalog under `docs/eventcatalog` documents events and channels |
| Independent evidence | Wolverine/Aspire instrumentation not inspected; queue and exchange names are generated by convention, not written in source |
| Missing AIP distinction | Not determinable without running Wolverine or reading its conventions: exchange/queue identity is produced by the framework |
| Classification | **INSUFFICIENT_EVIDENCE** |
| Recurs Round 4 finding? | Not decidable |
| Product relevance | Shows the "destination identity is framework-generated" variant |
| Follow-up | None in this round |

## Round 4 carry-over

| Case | Broker model | Classification |
|---|---|---|
| Sokol111 | Kafka, separate consumer groups, legacy `messaging.destination` keys | **SEMANTIC_GAP** (consumer attribution) + **INGESTION_GAP** (keys) |
| sminerport | RabbitMQ headers exchange, queue bound with `x-match`/header arguments | **SEMANTIC_GAP** (binding predicate) + **INGESTION_GAP** (no topology source) |
