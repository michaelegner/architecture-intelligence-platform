# Answer: Marketplace listing connector, 15-minute withdrawal requirement

## 1. First impression (written before investigating, unchanged; see `first-impression.md`)

Provisional recommendation: **conditional proceed**. I expect a connector can keep catalog data aligned on a best-effort basis. The 15-minute withdrawal is an end-to-end outcome, so it can only be met if the product service promises timely disable/delete events, the broker/platform promises delivery, and the marketplace promises to process withdrawals within a bounded time. Without those commitments, the connector should not promise the 15 minutes itself.

## 2. Findings

All file paths are under the corpus `sokol111/` tree, at the revisions in `REPOS.txt` (catalog-service `e9f1474`, commons `d54bf55`, product-query-service `b8f5137`, image-service-api `2167948`). Promise Contracts were read through the gt `gtContractsFor:` view.

### Promise Contracts

- **F1. Catalog offers change events to existing shop projections only, with no delivery or latency guarantee.** CAT-OFFER-01 (`contracts/catalog/product-change-events.yaml`, fixture v2) has audience "Existing shop projection consumers". Its limitations say: "No delivery or latency guarantee is offered" and "New consumers or changed purposes need their own applicability and acceptance assessment". It also states that commit, outbox recording, publication and downstream processing are separate stages. **A new marketplace connector is outside this audience, so today it has no legitimate basis to rely on these events.**
- **F2. Product Query reads are offered only to separately provisioned clients, without freshness.** PQ-READ-01 (`contracts/product-query/product-reads.yaml`, v3) has audience "Separately provisioned tenant-scoped product-display clients". It grants no credentials, says "No guarantee of freshness relative to the latest Catalog commit", and has the purpose "product-display", not marketplace syndication.
- **F3. PQ-ACCEPT-01 covers only Product Query's own projection input.** It explicitly "Does not prove … delivery latency or read freshness" and "Does not authorize a new consumer". It cannot be borrowed as a promise to the connector (`contracts/product-query/catalog-change-acceptance.yaml`).
- **F4. Image offers promotion events only to the existing shop audience.** IMG-OFFER-01 says it "Does not authorize additional consumers" (`contracts/image/image-promotion-information.yaml`). Keeping images aligned therefore also needs a new agreement.
- **F5. The marketplace promises a processing outcome but no deadline.** DEMO-CONTRACT-001 (`contracts/marketplace-withdrawal-contract.md`, fixture v3): for accepted, valid, authenticated, correctly scoped requests it offers processing and a queryable outcome (completed = no longer publicly visible, or failed). It "**does not promise a fixed time from request acceptance to completed withdrawal**". Acceptance or a pending status is not withdrawal. A rejected, unreceived or unavailable request creates no commitment.

### Source code and inputs

- **F6. "Disable" has no event of its own.** It is `Enabled=false` inside an ordinary `ProductUpdatedEvent` (`ecommerce-catalog-service/internal/application/product/product.go`, `update_product.go`, `internal/infrastructure/outbound/kafka/product_event_factory.go`). The declarations list only `ProductUpdatedEvent` and `ProductDeletedEvent` on `catalog.product.events` (`inputs/declarations/sokol111-local/ecommerce-catalog-service/asyncapi.yaml`). The connector would have to read every update and detect the enabled→disabled transition itself.
- **F7. The delete event carries only `ProductId`, with no version or timestamp** (`product_event_factory.go`, `NewProductDeletedOutboxMessage`). Product Query deletes unconditionally (`ecommerce-product-query-service/internal/application/productview/delete_product.go`), and its upsert is guarded only by `version < event.Version` (product-query `AGENTS.md`). A late or redelivered older `ProductUpdated` arriving after a delete could therefore plausibly re-create a deleted product in the read model or in a connector built the same way. I inferred this from the design and did not test it.
- **F8. The transactional outbox makes publication durable, but not timely.**
  - The state change and the outbox record commit in one Mongo transaction. The immediate Kafka send after commit is "best-effort", and its error is ignored (`update_product.go`, `delete_product.go`; catalog `AGENTS.md`).
  - Retries use exponential backoff of `30s × 2^attempts`, capped by `MaxBackoff`, which **defaults to 10 hours** (`ecommerce-commons/pkg/kafka/outbox/repository.go`, `config.go`). The fetcher polls every 5 s, or 10 s after an error (`fetcher.go`).
  - Cumulative retry delays are 30 + 60 + 120 + 240 + 480 s ≈ 15.5 min, so a broker or producer outage of a few minutes can push publication past 15 minutes. Nothing in the code bounds latency.
- **F9. The documentation claims more than the contracts do.** `inputs/upstream/product-update-flow.md` says a product change "reliably reaches the storefront", but then states that the storefront is "eventually consistent". The architecture documents are context, not owner commitments, and the contracts themselves deny any latency guarantee (F1).
- **F10. Product Query's read RPCs are public in code, but that is not permission.** All four query RPCs require no auth (product-query `AGENTS.md`, `connect/module.go`). PQ-READ-01 still requires separate provisioning, so the fact that the endpoint is reachable gives the connector no legitimate basis to rely on it.
- **F11. The broker capture shows no marketplace consumer, and nothing about lag.** `inputs/c1/kafka-consumer-state.json` (captured 2026-10-21, `complete: true`) has four groups. `ecommerce-product-query-service` and `ecommerce-image-service` consume `catalog.product.events`, each on a single partition 0. There is no marketplace or connector group. The capture holds no offsets or lag, so it says nothing about current propagation latency. The group-to-service mapping is 1:1 (`inputs/mapping/sokol111-local/kafka-service-mapping.json`).
- **F12. Image events share the product topic.** `ProductImagePromotedEvent` is published to `catalog.product.events` (`ecommerce-image-service-api/pkg/events/topics.go`; `inputs/event-topic-lookup.json`). A connector on that topic would receive Catalog and Image events together, but under two different offers, neither of which covers it (F1, F4).
- **F13. The generated event catalog adds nothing about guarantees.** Its entries are stubs, e.g. `inputs/catalog/events/ProductEvents/index.mdx` says "Generated … Do not edit". It is not a source of promises.

### Summary of the gap

The chain from shop disable/delete to a withdrawn external listing has four stages:

1. Catalog commit → publication: durable, no latency bound.
2. Publication → connector: no offer exists for this consumer.
3. Connector → marketplace acceptance: the connector's own behaviour.
4. Marketplace acceptance → listing not visible: no time bound.

**No party currently promises a bound on any stage**, and two stages have no applicable offer at all. A 15-minute end-to-end guarantee cannot be built from today's commitments.

## 3. Recommendation and proposed commitments

**Recommendation: conditional proceed.**

- **Proceed now** with the alignment part (product information, price, availability, images) as best-effort, eventually consistent syndication.
- **Do not promise the 15-minute withdrawal to the merchant** until the agreements below exist.
- If the merchant treats the 15-minute withdrawal as a hard precondition for going live, the decision is **defer** until agreements A and D are in place.

### Proposed commitments (who makes each one, under which conditions)

**A. Catalog owner (Catalog service role): a new or extended offer for the marketplace connector.**
- **Content:**
  - Add the connector to the audience of product-change events, with "external marketplace syndication" as a stated purpose.
  - Commit to a publication-latency objective, e.g. p99 commit→publish ≤ X min (X well under 15) under normal operation.
  - Commit to an outage signal: an alert or status when the outbox backlog is older than a threshold.
- **Conditions:** broker available; tenant and product commit succeeded. This needs `MaxBackoff` and the base delay tuned for this purpose, because the 10 h default is incompatible.
- **Also wanted:** a version on `ProductDeletedEvent` (or a tombstone carrying a version) so that consumers can order a delete against late updates (F7). An explicit "disabled" signal would also help (F6).

**B. Image owner: an extension of IMG-OFFER-01 to the connector, for image alignment only.**
- Not needed for withdrawal; no latency bound needed.

**C. Product Query owner (optional): provisioning of the connector under PQ-READ-01, or a new syndication read offer.**
- Purpose: periodic reconciliation, i.e. detecting disabled or missing products as a safety net if events are lost or delayed.
- Without a freshness promise this cannot carry the 15-minute bound. It reduces the risk of a listing staying visible indefinitely.

**D. External marketplace platform: a bilateral agreement beyond DEMO-CONTRACT-001.**
- **Content:** a time bound from accepted withdrawal request to completed (not visible), e.g. ≤ Y min, plus failure notification.
- **Conditions:** valid, authenticated, correctly scoped requests; marketplace endpoint available.
- Only the marketplace can make this promise. The connector cannot make it for them.

**E. Connector owner (the new service): promises only about its own behaviour.**
- **What it promises:**
  - Consume disable transitions and deletes and submit a withdrawal request within Z min of receiving the event (Z small).
  - Retry rejections and unavailability, then poll the marketplace outcome until "completed" (not "accepted"/"pending").
  - Reconcile against Product Query (if C is agreed).
  - Escalate to the merchant when an outcome is "failed" or not completed within the budget.
- **What it does not promise:** the 15-minute end-to-end outcome. It can promise detection and escalation.

**F. Merchant (and whoever sells the integration): accept a composed, conditional statement instead of an unconditional one.**
- The statement would read: "withdrawn within X + Z + Y ≤ 15 min while all parties operate normally; otherwise alert within N min plus manual fallback."
- An operational fallback is the merchant manually withdrawing listings in the marketplace UI when alerted.

The 15-minute requirement is only credibly satisfiable as the **sum of A + E + D, with budgets X + Z + Y ≤ 15 min, under normal operating conditions**, plus an agreed alert and fallback path for outages. Without A and D it is not satisfiable.

## 4. What remains uncertain

- Whether the Catalog owner is willing to admit a new external-purpose consumer and to commit to a latency objective. The offers can be revised only by their owners.
- Whether the marketplace will agree to any time bound at all. DEMO-CONTRACT-001 explicitly offers none.
- **Actual propagation latency today.** The consumer-group capture has no offsets or lag and is a single local snapshot from 2026-10-21. No production or load evidence exists.
- Whether `outbox.max-backoff` is overridden in the deployed configuration (I did not inspect `ecommerce-infrastructure` values). The code default is 10 h.
- Behaviour on delete versus late update (F7). This is inferred from the design; I did not read the Product Query repository's upsert implementation or test it.
- How tenant identity is carried on events (probably in headers; the delete payload has only `ProductId`). Tenant scoping for a multi-tenant connector is unverified.
- Single partition (partition 0) on `catalog.product.events`: throughput under bulk changes is unknown.
- How disable is represented end to end: whether Product Query's list or detail reads filter out `enabled=false` products is not established (I did not see a filter in `get_list.go`'s query object). This matters if reconciliation relies on Product Query reads.
- What happens to listings during a marketplace outage beyond the agreed budget, i.e. liability and escalation terms with the merchant.

## 5. Did the recommendation change?

**No. It stayed conditional proceed**, but the investigation made it sharper and stricter:

- **The broker hop is worse than I assumed.** The first impression assumed the main gap was latency on that hop. F1 (CAT-OFFER-01's audience excludes new consumers) and F4 showed that today the connector has **no legitimate basis to consume the events at all**, so a new Catalog agreement (A) is a precondition, not just a latency add-on.
- **The latency gap is concrete.** F8 (exponential outbox backoff with a 10 h default cap) showed that an outage of a few minutes already exceeds 15 minutes.
- **The marketplace offers no time bound.** F5 (DEMO-CONTRACT-001 offers no time bound) confirmed that a separate marketplace agreement (D) is required.
- **A hard requirement means defer.** Together these findings add the explicit rule that if the merchant treats the 15-minute withdrawal as hard, the answer is defer until A and D are in place.
