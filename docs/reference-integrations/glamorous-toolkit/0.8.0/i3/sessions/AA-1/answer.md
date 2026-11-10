# Marketplace listing connector: withdrawal within 15 minutes

## 1. First impression (written before the investigation, unchanged)

Provisional recommendation: **conditional proceed**. A connector can likely consume the shop's product events to keep listings aligned. The 15-minute withdrawal outcome is only credible if three parties commit to time budgets that add up to less than 15 minutes: the catalog service (timely disable/delete events), the connector (bounded processing) and the marketplace (bounded withdrawal time).

(Also in `first-impression.md`.)

## 2. Findings

### A. What the existing promises cover, and what they don't

**F1. Catalog offers change events, but only to the existing shop consumers, and with no timing.** Source: `contracts/catalog/product-change-events.yaml` (CAT-OFFER-01).
- Catalog offers product-change messages for committed updates and deletions.
- The audience is "existing shop projection consumers" only. A marketplace connector is a new consumer with a new purpose. The contract says such consumers "need their own applicability and acceptance assessment".
- The contract also says: "No delivery or latency guarantee is offered". It treats commit, outbox recording, publication and downstream processing as separate stages.
- So today a new connector **cannot legitimately rely on** this offer, and no one can rely on its timing.

**F2. Product Query offers tenant-scoped reads, with no freshness guarantee and no automatic access.** Source: `contracts/product-query/product-reads.yaml` (PQ-READ-01).
- The reads reflect the projection at query time, with "No guarantee of freshness relative to the latest Catalog commit".
- The client must be separately provisioned and authorized for its tenant *and purpose*. The offer itself grants no credentials.
- A polling connector would therefore need a provisioning approval, and it would still inherit unbounded projection lag.

**F3. Product Query's acceptance is not a promise to anyone else.** Source: `contracts/product-query/catalog-change-acceptance.yaml` (PQ-ACCEPT-01).
- It is an acceptance addressed to Catalog only.
- It "Does not prove … delivery latency or read freshness" and "Does not authorize a new consumer".

**F4. Image promotion information is also limited to the existing shop.** Source: `contracts/image/image-promotion-information.yaml` (IMG-OFFER-01). The audience is the existing shop consumers, and it "Does not authorize additional consumers". Keeping marketplace images aligned therefore needs a separate agreement with the Image owner (or reads via Product Query under PQ-READ-01). This is not needed for withdrawal itself.

**F5. The marketplace promises to process a withdrawal, but not by any deadline.** Source: `contracts/marketplace-withdrawal-contract.md` (DEMO-CONTRACT-001).
- For an accepted, valid request, the marketplace offers processing and a queryable outcome: completed (listing no longer visible) or failed.
- It "does not promise a fixed time from request acceptance to completed withdrawal".
- A rejection, an unavailable endpoint or a request never received creates no commitment at all.
- An acknowledgement or a pending status is not a withdrawal.

**Conclusion of A:** none of the existing parties promises any time bound. The only promise about the actual outcome (the listing is not visible) comes from the marketplace, and it has no deadline.

### B. What the implementation shows (supporting evidence, not commitments)

**F6. Disable and delete are different signals on the same topic.**
- Disabling is not its own event. It arrives as a `ProductUpdatedEvent` with `enabled=false` (field 8).
- Deletion is a `ProductDeletedEvent` that carries only `product_id`: no version and no timestamp.
- Both go to `catalog.product.events`, keyed by product ID.
- Sources: `sokol111/ecommerce-catalog-service-api/proto/catalog/events/v1/product_events.proto`, `…/pkg/events/topics.go`, `sokol111/ecommerce-catalog-service/internal/infrastructure/outbound/kafka/product_event_factory.go`, and `internal/application/product/{update_product.go,delete_product.go}`.

**F7. The outbox guarantees an event is recorded, not that it is published quickly.**
- The product change and the outbox message are committed in one MongoDB transaction. After the commit there is one best-effort immediate send (`_ = send(ctx)`, errors ignored). Sources: `update_product.go:150-177` and `delete_product.go:45-63`.
- If that send fails, the retry schedule is: first retry about 10 s after creation; each later retry delay is 30 s × 2^attempts; the cap (`MaxBackoff`) defaults to **10 hours**; the fetcher polls every 5 s. Sources: `sokol111/ecommerce-commons/pkg/kafka/outbox/repository.go:56-75,100-101`, `config.go:13-16`, `fetcher.go:39`.
- After about five failed attempts, publication alone already exceeds 15 minutes.
- The retry queue is ordered by next-attempt time, not by creation time. A retried earlier update can therefore be published *after* a later delete.
- So there is no structural basis for a 15-minute bound unless the Catalog owner configures and commits to one.

**F8. Product Query's handling of disable and delete affects any read-based approach.**
- The list, random and facet queries filter on `enabled=true` (`product_view_repository.go:111,154,217`). A disabled product drops out of list results; a deleted one is hard-deleted (`Delete`).
- Upserts are guarded by version (`version $lt`, line 36). Deletes have no tombstone, so a late stale update could re-create a deleted view.
- A connector that consumes events directly needs the same care: keep a tombstone per deleted product ID and never re-list after one. The ordering risk in F7 makes this a real concern.

**F9. The architecture model only partly covers deletion.**
- The event catalog and declarations list Catalog as sending `ProductEvents` and `ProductUpdated` only (`inputs/catalog/services/ecommerce-catalog-service/index.mdx`).
- Product Query is listed as receiving only `ProductUpdated` and `ProductImagePromoted` (`inputs/catalog/services/ecommerce-product-query-service/index.mdx`).
- But the AsyncAPI declaration (`inputs/declarations/sokol111-local/ecommerce-catalog-service/asyncapi.yaml`) and the code (`fxconfig/module.go:21-23`) both include `ProductDeletedEvent`.
- In other words, deletion appears only under the generic "ProductEvents" family label. The withdrawal-relevant event type is not separately modeled as promised.

**F10. Today's broker shows only the existing shop services consuming product events.**
- `get_binding_picture` (bounded context catalog-management, env local, snapshot `aip:snapshot:v1:7f171aea…c413`) returned outcome PARTIAL.
- `catalog.product.events` → ecommerce-product-query-service and → ecommerce-image-service are `PROMISED_AND_OBSERVED`. The declared event types are ProductUpdated/ProductImagePromoted; ProductDeleted is not declared.
- Several other bindings are `UNRESOLVED / PROMISE_COVERAGE_MISSING`.
- The tool's limitations: an attachment does not establish which events a group handles; producers are declared, never observed; the promises are "assumed confirmed".
- The capture (`inputs/c1/kafka-consumer-state.json`, 2026-10-21, local, single partition) shows no marketplace group. This is expected, because the connector does not exist yet.
- `get_service_dependencies` returned NOT_ANSWERED because it requires an observation window. Nothing was concluded from it.

**F11. The architecture docs promise eventual consistency only.** `inputs/upstream/product-update-flow.md` states that the storefront "is eventually consistent after a write", and that the outbox prevents a commit without its event. It does not state any latency.

## 3. Recommendation: **conditional proceed**

Building the connector for alignment of product information, price and availability can proceed once the access agreements (C1, C4) are in place. The **15-minute withdrawal requirement can only be claimed** if a chain of separately owned commitments exists, or if the merchant accepts a redefined requirement. No single party, and certainly not the connector alone, can promise it. The chain:

| # | Commitment | Who | Conditions |
|---|---|---|---|
| C1 | Admit the marketplace connector as an audience of the product-change offer, explicitly including `ProductDeletedEvent` and the `enabled` flag (a new or revised CAT-OFFER). | Catalog owner | Tenant-scoped consumer group; agreed event format and version semantics; notice of format changes. |
| C2 | A publication budget: committed disable/delete reaches `catalog.product.events` within *T₁* (e.g. ≤ 3 min) in normal operation, and outbox messages stuck longer than *T₁* are alerted on. Today's default `MaxBackoff` = 10 h is incompatible with this. | Catalog owner, with whoever operates the Redpanda broker | Applies only while the broker is available. Excludes declared outages. |
| C3 | An acceptance and a processing budget: consume, map and submit an authenticated withdrawal within *T₂* (e.g. ≤ 2 min) of receipt. Treat `enabled=false` and deletion the same way. Keep deletion tombstones. Retry until the request is *accepted*, then poll until the outcome is *completed*. Escalate on failure, rejection or deadline risk. | Connector owner (new) | Requires C1 and valid marketplace credentials. The connector promises its own step, not the end-to-end outcome. |
| C4 | Provision connector credentials for the merchant's channel scope. If reads are used for reconciliation or images, add PQ-READ-01 provisioning for this purpose and an Image audience extension. | Marketplace (publisher permission); Product Query owner / Image owner | Per tenant and purpose. |
| C5 | A withdrawal-completion time: an accepted valid request reaches *completed* within *T₃* (e.g. ≤ 10 min), plus a bound on how long the endpoint can be unavailable. **Not offered by DEMO-CONTRACT-001.** It needs a negotiated addendum. | External marketplace | Only for valid, accepted, in-scope requests. |
| C6 | Agree how the requirement is measured and what happens when it can't be met: start the clock at the Catalog commit (the clock starts at the commit, not when the merchant clicks), measure "withdrawn" as the marketplace outcome *completed*, keep a fallback (manual withdrawal from the marketplace console, or alerts to the merchant), and accept that outage windows are excluded. | Merchant, with the connector operator | Without this, nobody can verify the requirement. |

*T₁ + T₂ + T₃ ≤ 15 min* is required, with margin for retries.

**Without C5 (marketplace) and C2 (Catalog), the recommendation becomes defer for the 15-minute guarantee.** In that case the connector may still be built for best-effort alignment, but it must not be presented as meeting the requirement.

## 4. What remains uncertain

- **Marketplace timing:** whether the marketplace will negotiate any completion bound (C5), and how often requests are rejected or the endpoint is unavailable. Nothing currently promises either.
- **Real latency of the existing chain:** none was measured. The capture comes from a local environment, single partition, at a single point in time (2026-10-21). Production broker lag, outbox failure rates and the `MaxBackoff` setting actually deployed are unknown.
- **Event ordering:** the outbox retry order (F7) could put a stale update after a delete, or an enable after a disable. The connector's behavior in these cases needs owner-confirmed semantics: a version on deletes, or a tombstone rule.
- **Tenant identification:** `ProductDeletedEvent` has no tenant field in its payload. I did not verify from source how tenant context travels (presumably in headers).
- **Status of the contracts:** all of them are fictional and "DEMO_ASSUMED_CONFIRMED", so the AIP binding status `PROMISED_AND_OBSERVED` rests on an assumption. Bindings marked PROMISE_COVERAGE_MISSING show the promise coverage is incomplete. An attachment does not show which events a consumer handles.
- **Merchant clock and outages:** whether the merchant measures 15 minutes from the click in the admin UI or from the commit, and whether outage periods are excluded.
- **Images:** keeping marketplace images aligned depends on an Image audience extension that is not offered today.

## 5. Did the recommendation change?

The label stayed **conditional proceed**, but its meaning got stricter in two places:
- **F5** (DEMO-CONTRACT-001 promises no withdrawal time) showed that the most important condition is outside Sokol111 entirely: it needs a marketplace addendum, not just internal budgets.
- **F1 together with F7** (no latency guarantee, audience limited to existing consumers, 10-hour maximum outbox backoff, retries that can reorder events) showed that the Catalog side also needs an explicit new audience admission *and* a publication budget.

My first impression assumed the parties merely had to sum their budgets. The evidence shows that two of the three budgets do not exist today and have to be newly negotiated. If they are not, the outcome for the 15-minute guarantee is defer.
