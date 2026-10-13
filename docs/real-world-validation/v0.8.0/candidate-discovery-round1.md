# v0.8.0 Candidate Discovery — Round 1

**Status:** Round 1 complete  
**Date:** 2026-10-13  
**Purpose:** Build a broad longlist for the v0.8 product-boundary PoC before deeper filtering.

Round 1 prefers realistic e-commerce/retail systems with several meaningful services, synchronous APIs,
and asynchronous messaging. Kafka is not required. Kubernetes, multi-repository structure,
OpenTelemetry and public recognition are useful signals, not gates.

The scan is intentionally lightweight: repository metadata, README/architecture documentation,
service layout, deployment files and obvious messaging/runtime support. Static-analysis blind spots,
exact bounded-change scenarios, Teamscale behavior and AIP evidence feasibility are deferred to the
next round.

## Longlist

| Candidate | Domain / shape | Sync communication | Async messaging | Repository / deployment | Activity / recognition | Why potentially interesting for v0.8 |
|---|---|---|---|---|---|---|
| [dotnet/eShop](https://github.com/dotnet/eShop) | Microsoft e-commerce reference application; several commerce services | HTTP + gRPC | RabbitMQ integration events | Monorepo; .NET Aspire/containerized | Active; **high** recognition (~10k stars) | Strong, recognizable baseline combining direct calls and broker-mediated integration events; source analysis gets a fair chance. |
| [aspnetrun/run-aspnetcore-microservices](https://github.com/aspnetrun/run-aspnetcore-microservices) | Catalog, Basket, Discount, Ordering, gateway and web UI | REST + gRPC | RabbitMQ / MassTransit | Monorepo; Docker Compose | Active; **high** recognition (~3.2k stars) | Well-known e-commerce sample with both explicit gRPC and asynchronous checkout flow; useful strong-source baseline. |
| [tokonoma-ai/microservices-demo](https://github.com/tokonoma-ai/microservices-demo) | Maintained Sock Shop lineage; 8 polyglot app services | HTTP | RabbitMQ for shipping/queue flow | Monorepo; Kubernetes/Kustomize | Active; **high lineage recognition** | Polyglot, Kubernetes-based commerce system where broker topology may add relationships not represented as direct code dependencies. |
| [redis-developer/redis-microservices-ecommerce-solutions](https://github.com/redis-developer/redis-microservices-ecommerce-solutions) | Redis-maintained fashion/e-commerce microservices | HTTP via API gateway | Redis Streams | Monorepo; Docker Compose | Older activity; **medium** recognition / vendor-owned | Useful non-Kafka broker case and a different eventing model from RabbitMQ/Kafka candidates. |
| [Noname2812/ecommerce-microservices-demo](https://github.com/Noname2812/ecommerce-microservices-demo) | UrbanX multi-merchant commerce platform; catalog, order, inventory, payment, promotion, identity, etc. | REST through YARP/BFF | RabbitMQ / MassTransit saga + outbox | Monorepo; Aspire, Docker, Kubernetes | Active; low recognition | Rich order saga, OpenTelemetry and independently meaningful services make runtime-vs-source comparison promising. |
| [daonhan/Microservices-in-.NET](https://github.com/daonhan/Microservices-in-.NET) | Production-shaped .NET e-commerce platform | REST | RabbitMQ or Azure Service Bus | Multi-project repo; Kubernetes support | Active; low/medium recognition | Provider-aware messaging, outbox/saga, DLQ/replay and OpenTelemetry create several independent evidence surfaces. |
| [VaninBuuKun/Ecommerce_Microservices](https://github.com/VaninBuuKun/Ecommerce_Microservices) | Broad commerce ecosystem including catalog, identity, notifications, recommendations and analytics | REST + gRPC | RabbitMQ / MassTransit, saga + outbox | Monorepo | Active; low recognition | Many autonomous components plus mixed gRPC and broker communication could produce a realistic cross-boundary investigation. |
| [biswojit65/e-commerce_application](https://github.com/biswojit65/e-commerce_application) | 11 Spring Boot services behind an API gateway | REST | Kafka choreography | Monorepo; Docker Compose | Active; low recognition | Large service set, order/inventory/payment events, DLTs and OpenTelemetry provide a strong production-like topology. |
| [Sagar1051/ecommerce-microservices-platform](https://github.com/Sagar1051/ecommerce-microservices-platform) | 8 Spring Boot services | REST / service discovery | Kafka | Monorepo; Docker | Active; low recognition | Order processing crosses synchronous service calls and Kafka-driven recommendation/notification paths. |
| [nashinnov8/microservices-ecommerce](https://github.com/nashinnov8/microservices-ecommerce) | Auth, Product, Inventory and Order services behind a gateway | REST | Kafka saga | Monorepo; Docker Compose | Active; low recognition | Clear order/inventory saga with gateway and service boundaries; compact enough to run while still distributed. |
| [karanpraja902/ecommerce-microservices](https://github.com/karanpraja902/ecommerce-microservices) | Spring e-commerce blueprint with database-per-service | REST via gateway + Eureka | RabbitMQ | Monorepo; Docker, Kubernetes/EKS, Terraform, Skaffold | Active; low recognition | Combines broker events, service discovery, deployment topology and tracing; several evidence sources beyond source dependencies. |
| [berkesayin/ecommerce-app-microservices](https://github.com/berkesayin/ecommerce-app-microservices) | Spring Boot commerce system with real payment integration | REST | Kafka | Monorepo; Docker; Kubernetes work present | Active; low recognition | Kafka plus Elasticsearch/APM/OpenTelemetry and payment flow could support a realistic change-impact scenario. |
| [sumeetwt/kafka-commerce-platform](https://github.com/sumeetwt/kafka-commerce-platform) | Order, Inventory, Payment and Notification services | HTTP order API | Kafka with outbox, retry and DLT | Monorepo; Docker Compose | Active; low recognition | Very clear order-fulfilment flow where publisher/consumer relationships are central and easy to explain publicly. |
| [Revazashvili/ECommerce](https://github.com/Revazashvili/ECommerce) | Basket, Products, Ordering, Reports, Payment and Identity | REST APIs | Kafka + NATS; Debezium/outbox | Monorepo; Docker Compose | Maintained/older; low recognition | Reporting and payment consumers plus two messaging systems make cross-boundary discovery potentially interesting. |
| [buemura/mini-commerce](https://github.com/buemura/mini-commerce) | Customer, Product, Order, Payment and gateway | External REST gateway; internal gRPC | RabbitMQ payment flow | Monorepo; Docker Compose | Active; low recognition | Clean mixed-protocol flow: REST → gRPC → RabbitMQ → consumer, directly matching the desired v0.8 shape. |
| [emirbaycan/event-driven-microservice-ecommerce-platform](https://github.com/emirbaycan/event-driven-microservice-ecommerce-platform) | Go/Next.js commerce services | gRPC / API endpoints | RabbitMQ | Monorepo; Docker | Maintained; low recognition | Realistic language/runtime mix with broker-mediated business flow and independently deployable services. |
| [abgdnv/gocommerce](https://github.com/abgdnv/gocommerce) | Users, Products, Orders, Notifications and gateway | REST externally + gRPC internally | NATS JetStream | Monorepo; Kubernetes | Maintained; low recognition | Strong non-Rabbit/Kafka candidate with production-oriented Kubernetes, observability and distinct sync/async paths. |
| [kayamuhammet/microservice-ecommerce](https://github.com/kayamuhammet/microservice-ecommerce) | Identity, Product, Order, Stock and API Gateway | HTTP/REST | RabbitMQ / MassTransit | Monorepo; Docker Compose | Maintained; low recognition | OpenTelemetry/Jaeger is already present, reducing effort to obtain independent runtime evidence. |
| [mmdhossein/microservices-ecommerce](https://github.com/mmdhossein/microservices-ecommerce) | Product, Inventory, Order and Payment services | Service APIs | Kafka | Monorepo; Docker Compose | Active; low recognition | Payment failures/timeouts and inventory compensation provide plausible bounded changes with distributed effects. |
| [mostafasharaby/E-Commerce-Microservices](https://github.com/mostafasharaby/E-Commerce-Microservices) | Scalable .NET commerce microservices | REST/API-style services | RabbitMQ | Monorepo; Docker Compose | Maintained/older; **medium-low** recognition (~47 stars) | Conventional commerce workflow and broker communication; worth retaining until deeper architecture filtering. |
| [sminerport/eCommerceMicroservices](https://github.com/sminerport/eCommerceMicroservices) | Angular storefront with multiple backend services and gateway | HTTP through Ocelot gateway | RabbitMQ | Services referenced as submodules; Docker Compose + Kubernetes | Maintained; low recognition | Submodule/service separation may provide a naturally stronger repository-boundary test than a normal monorepo. |
| [mehdihadeli/food-delivery-microservices](https://github.com/mehdihadeli/food-delivery-microservices) | Adjacent commerce domain: production-shaped food delivery microservices | APIs / service calls | RabbitMQ via Wolverine | Monorepo; .NET Aspire + containers | Very active; **high** recognition (~1k stars) | Strong fallback if pure e-commerce candidates are weaker: mature event-driven design, OpenTelemetry and active development. |
| [jadofils/food-delivery-platform-microservices](https://github.com/jadofils/food-delivery-platform-microservices) | 8 Spring Boot delivery services | OpenFeign through gateway/service discovery | RabbitMQ | Monorepo; Docker Compose | Very active; low recognition | Particularly good mixed flow: synchronous customer/restaurant validation followed by asynchronous delivery/notification, with broker spans visible in Zipkin. |
| [Itssanthoshhere/Feasto](https://github.com/Itssanthoshhere/Feasto) | Multi-role food delivery platform | REST/WebSocket-facing services | RabbitMQ | Monorepo; Docker | Active; low recognition | Payment, restaurant and rider services communicate asynchronously; realistic operational workflow despite adjacent domain. |
| [Bruce-the-dev/food-delivery-platform](https://github.com/Bruce-the-dev/food-delivery-platform) | Spring food-delivery microservices | OpenFeign + gateway/Eureka | RabbitMQ | Monorepo; Docker Compose | Active; low recognition | Straightforward mixed sync/async order flow and service discovery make it a practical fallback candidate. |

## Notable systems screened out in Round 1

- [dotnet-architecture/eShopOnContainers](https://github.com/dotnet-architecture/eShopOnContainers) —
  highly recognizable and architecturally relevant, but archived and replaced by `dotnet/eShop`.
- [GoogleCloudPlatform/microservices-demo](https://github.com/GoogleCloudPlatform/microservices-demo)
  (Online Boutique) — highly recognizable and realistic, but its services primarily communicate through
  gRPC; it lacks the meaningful asynchronous inter-service messaging preferred for this PoC.
- [aws-samples/retail-demo-store](https://github.com/aws-samples/retail-demo-store) — recognizable
  retail reference system, but archived and its event streaming is not a strong core inter-service
  messaging case for this evaluation.
- [instana/robot-shop](https://github.com/instana/robot-shop) — useful RabbitMQ-based commerce
  topology, but archived in 2026.
- [Azure/reddog-solutions](https://github.com/Azure/reddog-solutions) — strong retail/event-driven
  Azure example, but archived in 2026.

## Round 1 result

The longlist contains **25 candidates**: **21 e-commerce/retail systems** and **4 adjacent
food-delivery systems** retained as fallback because they have unusually strong mixed synchronous /
asynchronous flows.

The most immediately promising systems for the next filtering round are not selected yet, but several
stand out for different reasons: `dotnet/eShop` and `aspnetrun/run-aspnetcore-microservices` for
recognition and strong source-analysis baselines; `biswojit65/e-commerce_application`,
`Noname2812/ecommerce-microservices-demo`, and `daonhan/Microservices-in-.NET` for production-like
messaging/observability depth; and `jadofils/food-delivery-platform-microservices` as a strong
non-commerce fallback with an especially clear mixed REST/RabbitMQ flow.

Round 2 should now inspect architecture fitness rather than search for more systems: identify the
important distributed relationship in each candidate, verify that it is not merely a direct source
dependency, and reduce the list to systems worth a concrete Teamscale/AIP comparison.
