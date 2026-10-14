# v0.8.0 Candidate Comparison — Round 3

**Status:** Round 3 complete  
**Date:** 2026-10-13  
**Input:** [Round 2 candidate evaluation](candidate-evaluation-round2.md)  
**Purpose:** Compare the remaining candidates with one concrete bounded change each and identify the best systems for the final v0.8 technical spike.

Round 3 deliberately excludes Teamscale. The question is narrower:

> **With all relevant repositories and existing agent-readable context available, does independent distributed-system evidence plausibly change what a coding agent needs to inspect before making a bounded change?**

A candidate is not retained merely because it has good observability. If source, configuration, `CLAUDE.md` / `AGENTS.md`, ADRs, or repository documentation already expose the same investigation boundary, runtime evidence may increase confidence without materially changing the next action.

## Comparison

| Candidate | Concrete change | Expected investigation boundary | Coding-agent/source baseline | Independent distributed evidence | Material difference? | PoC effort | Verdict |
|---|---|---|---|---|---|---|---|
| **Sokol111 ecommerce workspace** | Add or change a field in `ProductUpdatedEvent` from `ecommerce-catalog-service-api` | Catalog producer; Product Query consumer; Image consumer; shared contract; environment-specific topic/config | Strong baseline. Separate repos and `AGENTS.md` explicitly describe the contract and consumer behavior. A determined agent can find both consumers, but must join contract, topic, consumer registration, and deployment/configuration across multiple repos. | Strong. Kafka producer/consumer tracing propagates W3C context and records `messaging.system=kafka` plus destination; local and production infra independently configure both consumers on `catalog.product.events`. | **Unclear, but plausible.** The likely value is not discovering an undocumented consumer; it is establishing which cross-repo relationship is actually configured/observed in the selected environment and qualifying that relation independently of repository guidance. | Medium | **Finalist** |
| **sminerport/eCommerceMicroservices** | Change the `product.update` message payload/header semantics | Products repo producer; RabbitMQ `products.exchange`; Orders repo `orders.product.update.queue` consumer; deployment config | Moderate baseline. All source can be provided, but there is no direct repo dependency between Products and Orders. A cross-repo text search can match the `product.update` header and exchange names and infer the relation. | RabbitMQ topology can independently establish exchange → queue binding and active consumer; Docker/Kubernetes configs provide environment-specific broker/exchange configuration. | **Unclear, but plausible.** This is a clean test of whether independent broker topology adds anything beyond a strong cross-repo search. | Low | **Finalist** |
| **daonhan/Microservices-in-.NET** | Change `OrderCreatedEvent` used by the order saga | Order; Saga; Inventory; Payment; Shipping; broker provider | Very strong baseline. The repository contains the event contracts, saga matrix, provider abstraction, `CLAUDE.md`, ADRs and detailed architecture docs. The complete business investigation boundary is already explicit. | Excellent runtime evidence: RabbitMQ or Azure Service Bus selected through `Messaging__Provider`, OTel messaging spans, DLQ/operator data, Kubernetes/Azure configuration. | **No for this task.** Runtime evidence identifies the active transport/environment, but does not materially add services that the coding agent needs to inspect for an `OrderCreatedEvent` change. | Low/medium | **Reject for selection** |
| **mehdihadeli/food-delivery-microservices** | Change an order-domain integration event | Publishing service; RabbitMQ/Wolverine consumers; durable outbox/inbox; relevant downstream services | Very strong baseline. Repository docs and EventCatalog explicitly describe services, messages, channels, routing keys and ownership. | Strong OTel/RabbitMQ/Aspire evidence and durable messaging state. | **No.** Independent evidence can confirm execution, but the repository already provides the event/channel investigation boundary explicitly. | Medium | **Reject for selection** |
| **JYC11/koupang** | Change `OrderCreated` on `orders.events` | Order producer; Catalog inventory consumer; Payment path; reply events back to Order | Extremely strong agent-native baseline. Root/per-service `CLAUDE.md`, Kafka guide and saga docs explicitly describe the producer, consumers, topics and event flow. | Kafka plus OpenTelemetry support and testcontainers can independently observe the flow. | **No.** This is an excellent coding-agent control precisely because the agent-readable context already supplies the boundary AIP would otherwise need to contribute. | Low | **Reject; retain as negative control** |
| **dotnet/eShop** | Change `OrderStatusChangedToPaidIntegrationEvent` | Ordering publisher; Catalog, Webhooks and WebApp subscribers | Very strong source baseline. Subscription registration and handlers are explicit and colocated in the monorepo; direct search identifies the consumers. | RabbitMQ OTel instrumentation and Aspire runtime topology are strong. | **No.** Runtime evidence confirms a relation already obvious from source and does not change the inspection boundary. | Low | **Reject; retain as recognizable control** |
| **hungCS22hcmiu/ecommerce-system** | Change `orders.created` | Order producer; Payment consumer; `payments.completed/failed` return path to Order | Extremely strong Claude Code baseline. Root `CLAUDE.md`, README, ADRs and service docs explicitly state the Kafka saga and payloads. | Kafka runtime and E2E scripts can verify the flow; no stronger independent messaging telemetry was established in this pass. | **No.** The project is valuable as an agent-native control, but AIP is unlikely to change where the agent looks. | Low | **Reject; retain as agent-native control** |

## Finalists

Round 3 leaves **two finalists** for a technical spike:

### 1. Sokol111 ecommerce workspace

This is the strongest candidate because the architecture question genuinely crosses repository boundaries:

- the event contract lives in its own API repository;
- the producer is a separate service repository;
- Product Query and Image are separate consumer repositories;
- deployment and environment-specific Kafka configuration live in a separate infrastructure repository;
- OpenTelemetry independently captures Kafka producer/consumer relationships;
- rich `AGENTS.md` context gives the coding-agent baseline a fair advantage.

The uncertainty is important: the agent context is already good enough that AIP may still fail to change the investigation boundary. That makes it a useful product test rather than a constructed AIP win.

### 2. sminerport/eCommerceMicroservices

This is the simpler counterpoint:

- Products and Orders are genuinely separate repositories;
- Products publishes a `product.update` message to `products.exchange`;
- Orders binds `orders.product.update.queue` using the same message-header semantics;
- no direct source dependency connects the producer repo to the consumer repo;
- RabbitMQ can independently expose the active exchange/queue/consumer topology.

It is less production-like and less agent-native than Sokol111, but substantially cheaper to spike. It therefore provides a useful test of the same hypothesis with much less setup.

## Round 3 conclusion

Round 3 is more selective than Round 2. Several technically impressive systems were rejected because **good observability is not enough**. If the repository already tells a coding agent exactly which services consume an event, observing the same relation at runtime may improve confidence without changing the next action.

The two remaining systems test the harder question:

> **When producer and consumer live in different repositories and are connected through broker/configuration semantics rather than a direct source dependency, does independent distributed evidence materially improve the coding agent's investigation boundary?**

The technical spike should run this test first on **Sokol111** and use **sminerport** as the lower-cost comparison. Teamscale belongs in that spike, not in Round 3.
