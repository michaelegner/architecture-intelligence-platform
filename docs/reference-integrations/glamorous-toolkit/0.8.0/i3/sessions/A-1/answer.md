# Marketplace listing connector: withdrawal within 15 minutes

## 1. First impression (written before the investigation, unchanged)

> Provisional recommendation: **conditional proceed**. The catalog sync itself looks feasible, but the 15-minute withdrawal guarantee likely depends on commitments from the product service (timely, reliable disable/delete events) and from the external marketplace (withdrawal processing time) that the new connector cannot promise alone, so it should only proceed once those commitments are secured.

(Also in `out/first-impression.md`.)

## 2. Findings

All paths are relative to the work directory. Every Promise Contract is fictional and has the status `DEMO_ASSUMED_CONFIRMED` / `DEMO_CONTRACT_ASSUMED`.

### A. What the Promise Contracts offer, and to whom

**F1. Catalog sends product-change events, but only to the existing shop consumers, and promises no delivery or latency.**
`contracts/catalog/product-change-events.yaml` (CAT-OFFER-01) offers messages for committed product updates and deletions. Its audience is "Existing shop projection consumers". Its limitations say: "No delivery or latency guarantee is offered" and "New consumers or changed purposes need their own applicability and acceptance assessment." It also separates commit, outbox recording, publication and downstream processing as different stages. A marketplace connector is a new consumer with a new purpose, so this offer does not cover it today.

**F2. Product Query reads are open only to clients that have been provisioned separately, and they are not guaranteed fresh.**
`contracts/product-query/product-reads.yaml` (PQ-READ-01) says the client must be "separately provisioned and authorized for its tenant and purpose". The offer itself grants no credentials. It gives "No guarantee of freshness relative to the latest Catalog commit."

**F3. Product Query's acceptance contract is not something a connector can use.**
`contracts/product-query/catalog-change-acceptance.yaml` (PQ-ACCEPT-01) is an acceptance aimed at Catalog for the existing projection. It explicitly "Does not authorize a new consumer". It also does not prove delivery latency, read freshness or complete projections.

**F4. Image events are limited to the existing shop audience.**
`contracts/image/image-promotion-information.yaml` (IMG-OFFER-01) has the audience "Existing shop image-read and projection consumers" and "Does not authorize additional consumers".

**F5. The marketplace processes valid withdrawals but promises no time limit.**
`contracts/marketplace-withdrawal-contract.md` (DEMO-CONTRACT-001):
- An accepted, valid request ends as either *completed* (the listing is no longer visible) or *failed* (further action may be needed). Both outcomes can be queried.
- It "does not promise a fixed time from request acceptance to completed withdrawal".
- An acknowledgement or a pending status does not count as withdrawal.
- Rejected requests, an unavailable endpoint, or a request that never arrived create no commitment at all.

**Result of A:** none of the parties in the chain (Catalog → broker → connector → marketplace) offers any time bound today. Of the parties whose offers would matter, only the marketplace's offer is open to a new third-party publisher at all, and that offer has no time limit. No combination of the existing contracts adds up to "withdrawn within 15 minutes".

### B. What the code shows (fixed revisions in `sokol111/`)

**F6. Deleting a product sends its own event.**
`ecommerce-catalog-service/internal/application/product/delete_product.go:42-65` writes `ProductDeletedEvent` to the outbox in the same transaction as the delete. The event is built in `internal/infrastructure/outbound/kafka/product_event_factory.go:76-85` and carries only `ProductId`: no version and no timestamp. It is declared on `catalog.product.events` in `inputs/declarations/sokol111-local/ecommerce-catalog-service/asyncapi.yaml:30-37`.

**F7. Disabling a product sends no dedicated event.**
Disabling is a normal update with `Enabled=false`: `update_product.go:27,77,159`. It shows up as `ProductUpdatedEvent.Enabled` (`product_event_factory.go:57`). A connector has to read the `enabled` field on every update and treat the change to false as "withdraw".

**F8. The outbox guarantees the event is recorded, not that it is sent quickly.**
Each handler tries one immediate send and ignores the result (`_ = send(ctx)`, "best-effort send", `update_product.go:177`, `delete_product.go:63`). After that, a relay retries:
- The first retry comes no earlier than 10 s (`ecommerce-commons/pkg/kafka/outbox/repository.go:100-101`).
- Retries back off at `30s · 2^attempts`, capped at `MaxBackoff`, which defaults to **10 hours** (`repository.go:56-75`, `config.go:13-16`).
- The fetcher polls every 5 s when the outbox is empty and every 10 s after an error (`fetcher.go:36-48`).

If the first send fails, the delays grow like 30 s, 1 m, 2 m, 4 m, 8 m, 16 m and so on. After a few failures, the next retry alone is later than 15 minutes. This matches the "no latency guarantee" in CAT-OFFER-01. `inputs/upstream/product-update-flow.md` claims the outbox "prevents a database update from being committed without its corresponding domain event". That is true for recording the event, not for timely publication.

**F9. Product Query's public API cannot reliably show that a product was disabled.**
- The `Product` message in `ecommerce-product-query-service-api/proto/product_query/v1/product_query.proto:45-56` has no `enabled` field.
- The list endpoints filter on `enabled: true` (`ecommerce-product-query-service/internal/infrastructure/outbound/mongo/product_view_repository.go:111,154`).
- `GetProductById` does not filter on it (`internal/infrastructure/inbound/connect/product_handler.go:41-56`). It still returns disabled products, without saying they are disabled.

So a connector polling PQ could only find disabled or deleted products by scanning the whole list and noticing what is missing. It would also inherit the projection lag that PQ does not bound (F2). Using PQ reads to detect withdrawals is not a sound basis.

**F10. In the projection, a delete has no version, so a late update can bring the product back.**
PQ deletes the view unconditionally (`internal/application/productview/delete_product.go:24-26`). Upserts insert whenever no newer version is stored (`product_view_repository.go:34-37,68`). An old `ProductUpdated` that is redelivered after a delete would re-create the deleted product. A connector that copies this pattern could re-publish a withdrawn listing. It needs tombstones (records of deleted IDs) and must order events per product (the outbox key is the product ID, `product_event_factory.go:71,82`).

**F11. Image events share the product topic.**
`inputs/event-topic-lookup.json` maps `ProductImagePromoted` (from the image-service API) to `catalog.product.events`, the same topic as the Catalog events. A connector subscribed to that topic would also receive Image events, which IMG-OFFER-01 does not authorize for new consumers (F4). Two separate owner agreements are needed, not one.

### C. Architecture documents, event catalog and broker capture

**F12. The generated event catalog does not list the delete event.**
`inputs/catalog/events/` contains `ProductEvents`, `ProductUpdated`, `ProductImagePromoted`, `CategoryEvents` and `TenantUpdated`, but no `ProductDeleted`. The catalog was generated from the architecture documents, and those mention only `ProductUpdated`. Anyone planning from the catalog alone would miss the delete event that the code and the AsyncAPI declaration show (F6). The deletion part of the requirement must be planned from code and declarations, not from the catalog.

**F13. The broker capture shows only the existing consumers.**
`inputs/c1/kafka-consumer-state.json` (local environment, captured 2026-10-21T17:53:57Z, `complete: true`), mapped through `inputs/mapping/sokol111-local/kafka-service-mapping.json`:
- Only `ecommerce-product-query-service` and `ecommerce-image-service` consume `catalog.product.events`.
- Every topic has a single partition (0).
- No connector group exists, as expected.
- The capture reports membership and assignments only. It contains no lag, offsets or throughput, so it says nothing about how fast events arrive.
- It is one local snapshot, not production.

**F14. The documents describe the design as eventually consistent.**
`inputs/upstream/product-update-flow.md`: "The storefront is eventually consistent after a write." `inputs/upstream/platform-overview.md` likewise describes asynchronous projections. Neither document gives any timing figure.

## 3. Recommendation: **conditional proceed**

**Short version:**
- Building the catalog-sync connector can go ahead once the access agreements below are signed.
- Do **not** promise the merchant "withdrawn within 15 minutes" yet. No party currently offers any time bound (F1, F2, F5, F8). The connector cannot make the outcome true by itself, because two of the three stages are outside its control.
- The 15-minute outcome becomes credible only if all the commitments below exist together. Until then, the merchant should get a weaker, honest commitment (C3 and C5).

**A credible set of commitments: who makes each one, and under which conditions.**

| # | Who commits | What they commit to | Conditions / notes |
|---|---|---|---|
| C1 | **Catalog owner** (revision of CAT-OFFER-01 or a new offer) | Adds the marketplace connector as an authorized audience for `ProductUpdatedEvent` and `ProductDeletedEvent` on `catalog.product.events`. Commits to a **publication bound**: a committed delete or disable is published within *T₁* (for example 3 min) while the broker is reachable. Commits to alerting when outbox entries are older than *T₁*. | This requires a change to the code or configuration, not just a contract. Today's backoff can reach 10 h (F8). `MaxBackoff` would need to be about 1 min, and old outbox entries would need monitoring. The bound does not hold during a broker outage. Who gets told, and how, must be defined. Catalog also states the `enabled=false` semantics (F7) and whether it will add a version to `ProductDeletedEvent` (F10). |
| C2 | **Image owner** | Adds the connector to the audience of IMG-OFFER-01 for `ProductImagePromoted` (F4, F11). | Image only matters for keeping images aligned. Withdrawal does not depend on it. |
| C3 | **Connector owner** (the new party) | Consumes with its own group. Turns `enabled=false` or `ProductDeleted` into a withdrawal request within *T₂* (for example 2 min) of receiving the event. Keeps tombstones and orders events per product (F10). Polls the marketplace outcome; only "completed" counts as withdrawn (F5). Retries rejected or failed requests, then escalates. Runs a periodic reconciliation against Catalog's authoritative state as a safety net. Reports the measured time from Catalog commit to completed withdrawal. | This is valid only while C1 and C4 hold. The connector promises its own stage only, never the end-to-end result. It must not depend on PQ reads to detect withdrawals (F9). If it reconciles through PQ, it needs provisioning under PQ-READ-01 (F2). Reconciling against Catalog's admin API would need a separate Catalog authorization. |
| C4 | **Marketplace operator** (revision of DEMO-CONTRACT-001, or a separate SLA for this publisher) | For valid, accepted withdrawal requests: completion (no longer publicly visible) within *T₃* (for example 8 min). Includes some availability commitment for the endpoint. | This is the critical gap: today there is no time bound at all (F5). Rejected, unreceived or failed requests stay excluded, so C3 must cover those cases. |
| C5 | **Merchant, with the connector operator** | Agrees that the 15-minute goal is a target that holds only while C1, C3 and C4 hold, with *T₁ + T₂ + T₃ ≤ 15 min* and a safety margin. Agrees on what happens when it is missed: alert the merchant and give a manual withdrawal path in the marketplace. | Should the merchant insist on an unconditional guarantee, the honest answer is **defer**: no party can credibly give one. |

**Launch gates (all must be met before the 15-minute promise is made):**
1. C1, C2 (if images are synced), C3 and C4 have all been agreed.
2. PQ provisioning, if used, has been granted.
3. An end-to-end test of disable and delete, including broker outage and marketplace rejection scenarios, shows the time budget is met.

If C4 cannot be obtained, run the connector for catalog sync only and present withdrawal as "best effort, monitored". Do not present it as a 15-minute guarantee.

## 4. What remains uncertain

- **Marketplace timing:** whether the marketplace operator will commit to any completion time at all. Without that, the requirement cannot be met credibly (F5).
- **Catalog's willingness and timing:** whether the Catalog owner will add the new audience and change outbox retry and monitoring. Also, what real publication latency looks like: the capture has no lag or offset data, and it is a single local snapshot (F8, F13).
- **Real-world latency:** broker, consumer lag and Catalog transaction behaviour in production are unknown. There are only single-partition local topics and no throughput figures (F13).
- **Disable semantics:** whether `enabled=false` covers every "disable" path the merchant uses. I found only the update path (F7). Whether other kinds of unpublishing, such as tenant-level suspension through `TenantUpdated`, should also trigger withdrawal is unknown.
- **Delete event details:** the delete event carries no tenant field. I assume the tenant travels in message headers or context, but I did not verify this in the commons consumer code. The delete event also has no version (F10).
- **PQ access:** whether PQ provisioning (PQ-READ-01) would be granted for a marketplace purpose, and whether the API would ever expose `enabled` (F9).
- **Contract status:** all contracts are fictional and "assumed confirmed". None reflects real Sokol111 maintainers or a real marketplace.
- **Failure cases:** how to handle marketplace "failed" outcomes or a rejection that persists (for example, a listing ID that no longer maps to a listing). The marketplace contract says only that "further action may be necessary".

## 5. Did the recommendation change?

The label did not change: it is still **conditional proceed**. But two parts of my first impression were wrong and have been corrected:

- **The sync is not freely "feasible".** My first impression assumed the connector could simply consume existing events and reads. CAT-OFFER-01, PQ-READ-01, PQ-ACCEPT-01 and IMG-OFFER-01 all limit their audience to existing consumers or provisioned clients (F1–F4). Even plain catalog sync therefore needs new agreements with the owners.
- **The 15-minute outcome has no backing anywhere today.**
  - The marketplace contract explicitly refuses a fixed time (F5). This finding made the marketplace commitment (C4) a hard gate rather than a nice-to-have.
  - The outbox backoff can reach 10 hours (F8). This turned the Catalog commitment from a contract signature into a required code or configuration change.
  - PQ cannot show disabled products (F9). This ruled out a PQ-polling design for withdrawals.

Together these mean the 15-minute promise should be withheld (in effect, deferred) until C1 and C4 exist. Connector development and catalog sync can proceed in the meantime.
