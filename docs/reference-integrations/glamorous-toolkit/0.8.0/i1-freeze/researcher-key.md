# Researcher key: GT 0.8.0 experiment

**Researcher only. Never part of the participant corpus.** The key author (Claude, for the owner) has read the GT 0.8.0 specification. The owner reviewed and approved the key before the freeze (2026-11-09).

The key does not name a correct decision. It has three parts:

1. established facts: what the frozen inputs actually say;
2. invalid inferences: conclusions that the inputs do not support;
3. open design decisions: where participants must reason for themselves.

Score against the five article questions of spec §4. A participant can find a better-supported solution than this key anticipates. Record that solution in [Unexpected insights](#unexpected-insights). E1 and E2 can legitimately be negative.

Source revisions: catalog `e9f147483e6e33ec512851d478169d2985614b09` (`CS`), product-query `b8f5137b9e6fae3bacbe0319e0c23edfd0d25f19` (`PQ`).

## 1. Established facts

### Promise Contracts (fictional premises)

| Ref | Fact |
|---|---|
| F1 | `CAT-OFFER-01` offers product-change messages for committed product updates and deletions to **existing shop projection consumers**. It offers no delivery or latency guarantee. New consumers or changed purposes need their own assessment. |
| F2 | `PQ-ACCEPT-01` is an **acceptance** by Product Query of Catalog's product-change events for its **existing configured projection**. It does not offer reads, does not authorize a new consumer, and does not prove processing, completeness, latency or freshness. |
| F3 | `PQ-READ-01` is a separate **offer** of tenant-scoped reads to **separately provisioned and authorized** display clients. It reflects the projection state at query time and offers no freshness relative to the latest Catalog commit. The offer itself grants no credentials. |
| F4 | `IMG-OFFER-01` offers promoted-image information to existing shop consumers. It offers no delivery guarantee and does not authorize additional consumers. |
| F5 | `DEMO-CONTRACT-001` covers only valid, authenticated, correctly scoped requests that the marketplace **accepts**. It then offers processing and a queryable outcome, completed (listing no longer visible) or failed. It promises **no fixed time** from acceptance to completion. |
| F6 | No contract names the new marketplace consumer as audience or counterparty. No Promise Contract exists for the connector. |

### Source (implementation facts, not promises)

| Ref | Fact | Source |
|---|---|---|
| S1 | A **disabled** product is not a separate event. It is a `ProductUpdatedEvent` that carries `Enabled`. | [CS `product_event_factory.go` L50-L65](https://github.com/Sokol111/ecommerce-catalog-service/blob/e9f147483e6e33ec512851d478169d2985614b09/internal/infrastructure/outbound/kafka/product_event_factory.go#L50-L65) |
| S2 | A **deleted** product produces a `ProductDeletedEvent` that carries only the product ID. | [CS `product_event_factory.go` L76-L85](https://github.com/Sokol111/ecommerce-catalog-service/blob/e9f147483e6e33ec512851d478169d2985614b09/internal/infrastructure/outbound/kafka/product_event_factory.go#L76-L85) |
| S3 | Update and delete write the event to an outbox in the same transaction. The immediate send after commit is best-effort. Redelivery is in the shared outbox library (`ecommerce-commons`); the key author did not establish its behavior or timing. | [CS `update_product.go` L150-L177](https://github.com/Sokol111/ecommerce-catalog-service/blob/e9f147483e6e33ec512851d478169d2985614b09/internal/application/product/update_product.go#L150-L177); [CS `delete_product.go` L45-L63](https://github.com/Sokol111/ecommerce-catalog-service/blob/e9f147483e6e33ec512851d478169d2985614b09/internal/application/product/delete_product.go#L45-L63) |
| S4 | Product Query registers handlers for `ProductUpdated`, `ProductDeleted` and `ProductImagePromoted`. | [PQ `fxconfig/module.go` L14-L24](https://github.com/Sokol111/ecommerce-product-query-service/blob/b8f5137b9e6fae3bacbe0319e0c23edfd0d25f19/internal/infrastructure/inbound/kafka/fxconfig/module.go#L14-L24) |
| S5 | Product Query copies `Enabled` into its view on update and deletes the view on `ProductDeleted`. The key author did not establish whether the read API filters disabled products. | [PQ `product_handler.go` L32-L57, L118-L119](https://github.com/Sokol111/ecommerce-product-query-service/blob/b8f5137b9e6fae3bacbe0319e0c23edfd0d25f19/internal/infrastructure/inbound/kafka/product_handler.go#L32-L57), [L118-L119](https://github.com/Sokol111/ecommerce-product-query-service/blob/b8f5137b9e6fae3bacbe0319e0c23edfd0d25f19/internal/infrastructure/inbound/kafka/product_handler.go#L118-L119) |

### AIP (frozen C1 snapshot; AIP conditions only)

| Ref | Fact |
|---|---|
| A1 | Product Query × `catalog.product.events` is `OUTBOUND` from Catalog Management and `PROMISED_AND_OBSERVED`. Evidence mode resolves four refs: one `KAFKA_ATTACHMENT` (consumer group attached at T `2026-10-21T17:53:57Z`), one `KAFKA_SERVICE_MAPPING` (authored group → Service) and two `CATALOG_PROMISE` (the generated demo EventCatalog). See [`aip/`](aip/). |
| A2 | The answer has 9 rows. Product Query × and Image × `catalog.product.events` are `PROMISED_AND_OBSERVED`. The other 7 are `UNRESOLVED`, including the Product Query and Category Query attachments to `catalog.attribute.events` and `tenant.tenant.events`. |

**Research-only check (spec §2).** A1 is independent evidence that Product Query's consumer group was attached to the product topic at T. It is consistent with the existing projection path that `PQ-ACCEPT-01` describes. A1 does **not** establish:

- event-type handling;
- complete projections;
- read freshness;
- delivery timing;
- `PQ-ACCEPT-01` itself, because its `PROMISED` part comes from the demo EventCatalog, not from that contract;
- anything about a new consumer.

Record whether a participant's conclusion about `PQ-ACCEPT-01` or `PQ-READ-01` changed because of A1. Record also whether a no-AIP participant reached the same conclusion from S4, or from the C1 capture and mapping in the common corpus. AIP's incremental contribution is the qualification, not access to the attachment.

## 2. Invalid inferences

| Ref | Invalid inference |
|---|---|
| X1 | Promising the merchant's 15-minute withdrawal, as a connector or anyone else, without naming the conditions and the other parties' commitments it depends on. |
| X2 | Treating marketplace **acceptance** of a request, or a pending status, as the listing being withdrawn (F5). |
| X3 | Treating the 15 minutes as a time budget derived from a marketplace SLA. There is no such SLA (F5). |
| X4 | Treating `PQ-ACCEPT-01` as covering the new consumer, or as offering reads (F2). |
| X5 | Treating `PQ-READ-01` reads as fresh relative to Catalog commits, or as already authorized for the connector (F3). |
| X6 | Treating a broker attachment (A1) or the source registrations (S4) as a confirmed acceptance, as proof of processing, or as a delivery time. |
| X7 | Treating `CAT-OFFER-01` as already offered to the new consumer, or as having a delivery or latency guarantee (F1, F6). |
| X8 | Presenting a fictional contract as real Sokol111 or marketplace commitment, or a source fact as a promise. |
| X9 | Treating disabled as needing no handling because it is "not a delete" (S1), or assuming that the delete event carries product data (S2). |

## 3. Open design decisions

There is no reference answer. The scorer judges whether each decision is justified by cited facts and keeps the provenance apart.

- **Stages:**
  - (a) the source change is known (Catalog commit, S3);
  - (b) the connector detects the change and requests withdrawal;
  - (c) the marketplace accepts the request;
  - (d) the listing is no longer visible.

  Which party could promise each stage, under which conditions? No stage's promise implies the next one.
- **Where the connector gets changes:** through a new agreement with Catalog that extends `CAT-OFFER-01` to the new audience; through provisioned `PQ-READ-01` reads, by polling or on demand; or through something else. Each option needs a different agreement and has its own freshness consequences.
- **What the connector could commit to:** for example, a bounded time for (b) under stated input conditions, monitoring of the marketplace outcome, and escalation on a failed outcome. The connector could also decline to commit.
- **What remains unowned:** the time from (c) to (d), the tenant authorization for the connector, the credentials on the marketplace, and the change notification when an offer evolves.
- **Decision class:** proceed, conditional proceed or defer can each be defensible if the reasoning is cited. A recommendation that carries the 15-minute guarantee without conditions is X1.

## Unexpected insights

Record here, per condition, any insight that the key did not anticipate. Give its citation and say whether it was verified independently.

| Condition | Insight | Evidence | Verified? |
|---|---|---|---|
| | | | |
