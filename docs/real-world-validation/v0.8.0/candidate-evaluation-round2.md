# v0.8.0 Candidate Evaluation — Round 2

**Status:** Round 2 complete  
**Date:** 2026-10-13  
**Input:** [Round 1 candidate discovery](candidate-discovery-round1.md)  
**Purpose:** Reduce the broad candidate pool to systems worth a concrete Teamscale × AIP comparison.

Round 2 asks one question:

> **Is there a realistic bounded change where an important distributed relationship matters, but that relationship is not simply equivalent to a direct source-code dependency?**

All relevant source and existing repository-native agent context remain available to the baseline. A candidate is not interesting if AIP only wins because source or documentation is withheld.

## Candidate evaluation

| Candidate | Bounded change | Relevant distributed relationship | Source visibility | Independent evidence | Agent context | PoC practicality | Verdict |
|---|---|---|---|---|---|---|---|
| [dotnet/eShop](https://github.com/dotnet/eShop) | Change `OrderStatusChangedToPaidIntegrationEvent` | Ordering publishes; Catalog, Webhooks and WebApp subscribe through RabbitMQ | **Direct/explicit**: subscriptions and handlers are registered in source | Strong: custom RabbitMQ OpenTelemetry spans + Aspire topology | GitHub skills, strong repo docs | Excellent | **Maybe** — valuable high-recognition control, but source already exposes most of the investigation boundary |
| [aspnetrun/run-aspnetcore-microservices](https://github.com/aspnetrun/run-aspnetcore-microservices) | Change `BasketCheckoutEvent` | Basket publishes; Ordering consumes via RabbitMQ/MassTransit | **Direct/explicit** shared event type, publisher and handler | RabbitMQ available; little independent telemetry found | Normal repo docs | Excellent | **Reject** — source gives the key relationship directly |
| [tokonoma-ai/microservices-demo](https://github.com/tokonoma-ai/microservices-demo) | Any checkout contract change | Sock Shop services | **Direct REST** | Logs/OTel platform exists, but upstream design states all app services communicate via REST/HTTP | Demo-oriented | Good | **Reject** — Round 2 corrected the Round 1 RabbitMQ assumption; no meaningful async inter-service relation |
| [redis-developer/redis-microservices-ecommerce-solutions](https://github.com/redis-developer/redis-microservices-ecommerce-solutions) | Change an order stream message | Redis Streams consumers | Mostly explicit teaching example | Redis runtime possible | Tutorial docs | Good | **Reject** — vendor tutorial optimized to explain the relation rather than hide it |
| [Noname2812/ecommerce-microservices-demo](https://github.com/Noname2812/ecommerce-microservices-demo) | Change `OrderCreated` saga event | Order → Inventory → Payment through RabbitMQ/MassTransit | **Explicit** in README and saga code | Strong OpenTelemetry + RabbitMQ + Aspire/K8s | Strong docs | Good | **Reject** — excellent runtime evidence, but the distributed boundary is already spelled out in repository context |
| [daonhan/Microservices-in-.NET](https://github.com/daonhan/Microservices-in-.NET) | Change `OrderCreatedEvent` / order saga contract | Order → Saga → Inventory/Payment/Shipping over selected broker | **Indirect enough to test**: shared messaging abstraction and runtime-selectable RabbitMQ vs Azure Service Bus | Strong: OTLP traces/logs, broker provider, DLQ, K8s, gateway | Extensive project context; agent/automation material present | Excellent | **Keep** — environment/provider-specific Current State can differ while source remains the same |
| [VaninBuuKun/Ecommerce_Microservices](https://github.com/VaninBuuKun/Ecommerce_Microservices) | Change order/payment integration event | Order/payment/analytics via MassTransit | Likely explicit in shared contracts and handlers | RabbitMQ available | Limited | Possible | **Reject** — no clear advantage over stronger .NET candidates |
| [biswojit65/e-commerce_application](https://github.com/biswojit65/e-commerce_application) | Change order/payment/inventory event | Kafka choreography across order, inventory, payment, notification/search | **Mostly explicit** in architecture docs and service code | Strong: OpenTelemetry → Zipkin, Kafka, Eureka | Extensive README/docs | Good | **Maybe** — rich production-like topology, but repository docs already disclose most edges |
| [Sagar1051/ecommerce-microservices-platform](https://github.com/Sagar1051/ecommerce-microservices-platform) | Change `OrderPlacedEvent` | Order/Payment/Product → Recommendation via Kafka | **Explicit** in README architecture | Kafka runtime | Portfolio docs | Good | **Reject** — event edges are intentionally documented |
| [nashinnov8/microservices-ecommerce](https://github.com/nashinnov8/microservices-ecommerce) | Change order/inventory saga event | Order ↔ Inventory via Kafka | **Explicit** in README and saga documentation | Kafka runtime | Strong docs | Good | **Reject** — source/docs already define the relevant boundary |
| [karanpraja902/ecommerce-microservices](https://github.com/karanpraja902/ecommerce-microservices) | Change an order/inventory event | Spring services via RabbitMQ + Eureka | Mixed source/config, but deliberately tutorialized | Zipkin, RabbitMQ, Kubernetes/EKS | Extensive guide | Medium | **Reject** — technical teaching system; relation discovery is part of the documentation |
| [berkesayin/ecommerce-app-microservices](https://github.com/berkesayin/ecommerce-app-microservices) | Change `OrderCreated` / payment event | Order, payment, notification/search through Kafka | Explicit event list and diagrams | OpenTelemetry / Elastic APM + Kafka | Extensive docs | Medium | **Reject** — strong evidence, but the repo already advertises the event graph |
| [sumeetwt/kafka-commerce-platform](https://github.com/sumeetwt/kafka-commerce-platform) | Change order event | Order → Inventory/Payment/Notification through Kafka | Direct Kafka-focused source | Kafka + DLT | Limited | Good | **Reject** — intentionally Kafka-centric and low external credibility |
| [Revazashvili/ECommerce](https://github.com/Revazashvili/ECommerce) | Change an ordering outbox event consumed by Payment/Reports | Ordering DB outbox → Debezium/Kafka Connect → Kafka → consumers | **Interesting indirect source path** across application + connector configuration | Strong broker/config potential, but no usable OTel messaging evidence found | Normal docs | Medium | **Reject for v0.8** — excellent semantic case, but proving it would depend on Kafka Connect/broker evidence that AIP does not currently ingest; Kafka Connect is explicitly deferred |
| [buemura/mini-commerce](https://github.com/buemura/mini-commerce) | Change order-payment message | Order → RabbitMQ → Payment → completion → Order | **Explicit** in README and compact source | OpenTelemetry + RabbitMQ | Normal docs | Excellent | **Reject** — easy PoC, but too little uncertainty in the investigation boundary |
| [emirbaycan/event-driven-microservice-ecommerce-platform](https://github.com/emirbaycan/event-driven-microservice-ecommerce-platform) | Change order/payment event | Go services via RabbitMQ/gRPC | Mostly explicit | RabbitMQ runtime | Limited | Good | **Reject** — lower recognition and no stronger blind spot than better candidates |
| [abgdnv/gocommerce](https://github.com/abgdnv/gocommerce) | Change order notification event | Order → NATS JetStream → Notification | **Explicit** in architecture diagram | Strong: OpenTelemetry, NATS, Kubernetes/Helm | Good docs | Good | **Reject** — strong implementation, but README already gives the exact edge |
| [kayamuhammet/microservice-ecommerce](https://github.com/kayamuhammet/microservice-ecommerce) | Change stock/order event | Order ↔ Stock via RabbitMQ/MassTransit | Direct/explicit | OpenTelemetry/Jaeger + RabbitMQ | Normal docs | Excellent | **Reject** — smaller and less credible than equivalent candidates |
| [mmdhossein/microservices-ecommerce](https://github.com/mmdhossein/microservices-ecommerce) | Change reservation/payment event | Order ↔ Inventory ↔ Payment via Kafka request/reply + pub/sub | Explicit architecture narrative | Kafka runtime | Normal docs | Good | **Reject** — relation is already described directly |
| [mostafasharaby/E-Commerce-Microservices](https://github.com/mostafasharaby/E-Commerce-Microservices) | Change payment confirmation / inventory update | RabbitMQ between Product/Inventory/Order/Payment | Explicit service responsibilities | RabbitMQ runtime | Normal docs | Good | **Reject** — no stronger source/runtime distinction than other .NET candidates |
| [sminerport/eCommerceMicroservices](https://github.com/sminerport/eCommerceMicroservices) | Change product-update event used by order-side cache | **Products repo → RabbitMQ → Orders repo** | **No direct source dependency across repos**; producer and consumers match only through RabbitMQ exchange/header semantics | RabbitMQ + environment-specific Kubernetes/Compose config | Separate repos/submodules; little agent guidance | Excellent | **Keep** — naturally cross-repository and broker-mediated without hiding source |
| [mehdihadeli/food-delivery-microservices](https://github.com/mehdihadeli/food-delivery-microservices) | Change an order/payment/delivery message | Independent services via Wolverine/RabbitMQ, mixed with REST/gRPC | Messaging framework abstracts direct source edges | Strong: OpenTelemetry Collector, RabbitMQ, Aspire; EventCatalog also available | Rich docs | Good | **Keep** — recognized, realistic fallback; source baseline is strong, but runtime messaging remains independently observable |
| [jadofils/food-delivery-platform-microservices](https://github.com/jadofils/food-delivery-platform-microservices) | Change `OrderPlacedEvent` | Order → Delivery + Notification via RabbitMQ | **Explicit** in README and service docs | Zipkin/RabbitMQ | Very strong docs | Good | **Reject** — excellent system explanation leaves little boundary uncertainty |
| [Itssanthoshhere/Feasto](https://github.com/Itssanthoshhere/Feasto) | Change order/payment/rider event | Services through RabbitMQ | Likely direct/explicit | RabbitMQ | Limited | Possible | **Reject** — weaker evidence and recognition than retained candidates |
| [Bruce-the-dev/food-delivery-platform](https://github.com/Bruce-the-dev/food-delivery-platform) | Change order event | Spring services through RabbitMQ + Eureka | Direct/explicit | RabbitMQ/service discovery | Limited | Possible | **Reject** — no distinctive v0.8 advantage |
| [Sokol111 ecommerce workspace](https://github.com/Sokol111/ecommerce-catalog-service) | Change a catalog product event schema | **Catalog repo → Kafka topic → Product Query + Image service repos** | **No direct source dependency between producer and consumers**; relation is assembled from separate API/config/service repos | **Very strong:** explicit OTel Kafka producer/consumer spans with `messaging.system=kafka`, topic attributes, trace propagation; k3d/k3s deployment config | Detailed per-repo `AGENTS.md`, workspace rules, OpenCode integration | Excellent | **Keep — strongest positive candidate** |
| [hungCS22hcmiu/ecommerce-system](https://github.com/hungCS22hcmiu/ecommerce-system) | Change `orders.created` | Order → Kafka → Payment → Kafka → Order | **Extremely explicit** in `CLAUDE.md`, README, ADRs and service docs | Kafka runtime; no comparable OTel messaging evidence established in this pass | Built with Claude Code; root `CLAUDE.md`, `.claude/` | Excellent | **Maybe** — ideal agent-native control, but AIP is unlikely to change the investigation boundary |
| [JYC11/koupang](https://github.com/JYC11/koupang) | Change `OrderCreated` | Order → Kafka → Catalog inventory + Payment; replies back to Order | **Explicit in agent context**, but no direct producer→consumer source dependency | Strong: Kafka + OpenTelemetry support + testcontainers | Built with Claude assistance; root/per-service `CLAUDE.md`, `.claude/skills`, plans/ADRs | Excellent | **Keep** — deliberately hard agent-native baseline with real broker/runtime evidence |
| [Ngoc-Giang/Ecommerce-MVP](https://github.com/Ngoc-Giang/Ecommerce-MVP) | Change `order-created` | Order → Kafka → Shipment | Explicit in `CLAUDE.md` | Kafka; limited independent runtime evidence found | Strong Claude Code agent setup | Good | **Reject** — agent-native but too small and too explicit |
| [eoghks/ecommerce-msa](https://github.com/eoghks/ecommerce-msa) | Change order saga event | Order/Product through Kafka choreography | Explicit in README/`CLAUDE.md` | Kafka | Project `CLAUDE.md` | Good | **Reject** — portfolio system and agent context already exposes the relation |
| [daoductam/ecomerce-platform-quarkus](https://github.com/daoductam/ecomerce-platform-quarkus) | Change order/payment/inventory message | Five Quarkus services via RabbitMQ | Agent guidance explicitly describes the topology | RabbitMQ, Docker/Kubernetes | `AGENTS.md` | Possible | **Reject** — useful agent-native example, but weak recognition and no stronger blind spot |
  
## Survivors

Round 2 leaves **7 candidates** worth deeper comparison:

1. **Sokol111 ecommerce workspace — KEEP.** Best positive candidate: real multi-repo boundaries, Kafka relations without direct source dependencies, strong OTel messaging semantics, deployment context, and rich agent-readable repository guidance.
2. **daonhan/Microservices-in-.NET — KEEP.** Strong runtime/config distinction because the same source can use different messaging providers by environment; full telemetry and failure paths are already present.
3. **sminerport/eCommerceMicroservices — KEEP.** Natural separate-repository producer/consumer relationship joined through RabbitMQ semantics rather than code dependency.
4. **mehdihadeli/food-delivery-microservices — KEEP.** Recognized, mature event-driven fallback with RabbitMQ/Wolverine and OpenTelemetry; not e-commerce but close enough for a credible comparison.
5. **JYC11/koupang — KEEP.** Agent-native hard baseline: Kafka + OTel + rich Claude context. If AIP still changes the next action here, that is strong evidence.
6. **dotnet/eShop — MAYBE.** High-recognition control. Its source already exposes subscriptions clearly, so it may demonstrate the point at which AIP adds little.
7. **hungCS22hcmiu/ecommerce-system — MAYBE.** Explicitly built with Claude Code and unusually rich `CLAUDE.md`; useful agent-native control, but likely too explicit to become the final PoC system.

## Round 2 conclusion

The strongest direction changed during Round 2.

The best candidates are **not** simply the systems with the most services, the most observability, or the most recognizable names. The key discriminator is whether the distributed relationship survives this fairness test:

> **Give the coding agent and source-analysis baseline all relevant repositories and all existing agent-readable context. Is the producer→consumer or runtime relationship still something that source dependencies alone cannot safely establish?**

On that basis, the **Sokol111 ecommerce workspace currently leads**. It combines the properties v0.8 needs unusually well:

- genuinely separate repositories;
- Kafka producer/consumer relationships with no direct producer→consumer code dependency;
- environment-specific deployment/configuration in a separate infrastructure repo;
- explicit OpenTelemetry producer/consumer spans using messaging semantic attributes;
- realistic local and production deployment;
- detailed `AGENTS.md` guidance that strengthens rather than weakens the baseline.

Round 3 should therefore be a **small concrete comparison of these seven survivors**, not another broad search. For each, use one bounded change and determine what a strong source/agent baseline can actually establish before introducing AIP.
