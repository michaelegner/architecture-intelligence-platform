# Marketplace listing connector: what the existing promises support

## 1. First impression (written before the investigation, copied unchanged from `first-impression.md`)

Conditional proceed: syncing catalog data (info, price, availability, images) to the marketplace looks feasible from the shop's product events, but the 15-minute withdrawal guarantee is an end-to-end outcome that no single party controls, so I expect it to be achievable only if the product service, the broker/operations side, the new connector and the marketplace each make bounded commitments (event publication on disable/delete, delivery latency, connector processing, and marketplace withdrawal time) that together fit within 15 minutes — otherwise defer the hard guarantee.

## 2. Findings

Corpus root: `GtAipPromiseCorpus` (`contracts.json` and the files listed there). Repository revisions come from `REPOS.txt`.

### Promise Contracts

**F1. Catalog publishes change events, but only for the existing shop consumers, and with no delivery or latency guarantee.**
- Source: Promise Contract CAT-OFFER-01 (`contracts/catalog/product-change-events.yaml`).
- Catalog offers product-change messages for committed product updates and deletions.
- The audience is the "existing shop projection consumers" only. The contract says "New consumers or changed purposes need their own applicability and acceptance assessment."
- It also says "No delivery or latency guarantee is offered", and that commit, outbox recording, publication and downstream processing are separate stages.
- So a marketplace connector is **outside the audience**. It cannot currently rely on this offer at all, and certainly not for timing.

**F2. The marketplace promises to process withdrawals, but sets no time limit.**
- Source: DEMO-CONTRACT-001 (`contracts/marketplace-withdrawal-contract.md`).
- For a valid, authenticated, correctly scoped and **accepted** request, the marketplace offers processing and a queryable outcome: *completed* (the listing is no longer visible) or *failed*.
- It explicitly "does not promise a fixed time from request acceptance to completed withdrawal".
- An acknowledgement or a pending status is not a withdrawal.
- A rejected request, an unavailable endpoint or a request that never arrived creates no commitment.

**F3. Product Query's acceptance of Catalog events covers only Product Query itself.**
- Source: PQ-ACCEPT-01 (`contracts/product-query/catalog-change-acceptance.yaml`).
- Product Query accepts Catalog update and delete events for its own projection.
- It disclaims "delivery latency or read freshness" and "does not authorize a new consumer".
- This is a bilateral arrangement between Catalog and Product Query. A connector cannot inherit it.

**F4. Product Query reads require provisioning and are not guaranteed fresh.**
- Source: PQ-READ-01 (`contracts/product-query/product-reads.yaml`).
- Tenant-scoped list and detail reads are offered only to "separately provisioned" clients.
- It gives "No guarantee of freshness relative to the latest Catalog commit".
- Polling Product Query therefore adds another unbounded stage. It is not a shortcut to the 15 minutes.

**F5. Image promotion events also exclude new consumers.**
- Source: IMG-OFFER-01 (`contracts/image/image-promotion-information.yaml`).
- Image offers promoted-image information to existing shop consumers and "Does not authorize additional consumers."
- Keeping marketplace images in sync therefore also needs a new agreement, this time with the Image owner.

### Source code and declarations

**F6. "Disable" has no event of its own. It arrives as a `ProductUpdatedEvent` with `enabled=false`.**
- Sources:
  - `ecommerce-catalog-service@e9f1474…/internal/application/product/update_product.go`
  - `…/product.go` (`Update`, `validateEnabledState`: disabling needs no validation)
  - `…/internal/infrastructure/outbound/kafka/product_event_factory.go` (`Enabled: p.Enabled`)
- The connector has to detect the change from `enabled` = true to false. It must not treat every update as an upsert.

**F7. Deletion produces a `ProductDeletedEvent` that carries only `product_id`.**
- Sources: `…/delete_product.go` and `product_event_factory.go` (`NewProductDeletedOutboxMessage`).
- Both events go to `catalog.product.events`, keyed by product id. Source: `ecommerce-catalog-service-api@7cecb3e…/pkg/events/topics.go`.
- The delete event has no version number. That makes ordering against a late, stale update harder to handle.

**F8. Each event is stored in the same database transaction as the change, but sending it to the broker is best-effort.**
- Sources: `update_product.go` and `delete_product.go` (`mongo.WithTransaction` plus `outbox.Create`, then `_ = send(ctx) // best-effort`), and `ecommerce-catalog-service/AGENTS.md` ("the actual Kafka send … happens best-effort after commit and its error is intentionally ignored (already logged by the outbox relay)").
- What this guarantees: an event cannot be lost once the change commits.
- What it does not guarantee: how quickly the event is sent. If the immediate send fails, the event waits for the outbox relay, and I found no relay interval or bound that anyone commits to.
- The upstream architecture document `inputs/upstream/product-update-flow.md` agrees: the storefront "is eventually consistent after a write."

**F9. The authored AsyncAPI declaration matches the code. The generated event catalog does not.**
- Sources:
  - `inputs/declarations/sokol111-local/ecommerce-catalog-service/asyncapi.yaml`: `catalog.product.events` publishes `ProductUpdatedEvent` or `ProductDeletedEvent`.
  - `inputs/event-topic-lookup.json` (the event catalog generated from the architecture documents)
- The generated catalog has **no `ProductDeleted` entry** and no `catalog.attribute.events`.
- A connector designed from that catalog would miss deletions, which is exactly the case the merchant cares about. The code and the authored declaration must be the design basis.

**F10. Product Query handles both event types. A disabled product stays in its projection.**
- Sources: `ecommerce-product-query-service@b8f5137…/AGENTS.md` and `internal/infrastructure/inbound/kafka/product_handler.go` (`HandleProductUpdated`, `HandleProductDeleted`).
- Disabled products remain in the projection with `enabled=false`. `get_list.go` and `get_product.go` contain no filter on `enabled`, and I did not check the repository-level filter.
- `AGENTS.md` says all query RPCs are **public (no auth)**. Being technically reachable is not the same as being authorized: PQ-READ-01 still requires separate provisioning.

### Broker capture

**F11. No marketplace consumer exists yet, and the capture shows no lag or timing.**
- Sources: `inputs/c1/kafka-consumer-state.json` (captured 2026-10-21, local environment, `complete: true`, 4 groups in scope) and `inputs/mapping/sokol111-local/kafka-service-mapping.json`.
- Only `ecommerce-image-service` and `ecommerce-product-query-service` consume `catalog.product.events`, which has a single partition (0).
- There is no connector group. A new group would be a new, so far unauthorized consumer.
- The capture contains no offsets, lag or timing data, so it gives no evidence about delivery latency.

### Overall result

**F12. Today, no party has promised any time bound on any stage of the withdrawal chain.**

| Stage | Who owns it | Current time bound |
|---|---|---|
| Catalog commit → outbox → broker | Catalog | none (F1, F8) |
| Broker → connector | platform / operations | none (F11) |
| Connector processing and submitting the withdrawal | new connector | not yet defined |
| Marketplace accepts → listing no longer visible | marketplace | none (F2) |

So under the current commitments the 15-minute requirement **cannot** be met, and nobody can credibly promise it.

## 3. Recommendation: conditional proceed

- **Proceed now** with the parts that need no timing promise. That means building the connector against the authored event declaration and the code (F9), with explicit handling of `enabled=false` (F6) and of deletes (F7).
- **Do not promise the merchant the 15-minute withdrawal** until the agreements below are in place. If they cannot be obtained, tell the merchant plainly that withdrawal is best-effort and eventually consistent, and treat the hard requirement as deferred.

The connector cannot promise the 15-minute outcome on its own, because it controls only one stage. A credible set of commitments needs these parties:

1. **Catalog owner → connector: a new or extended offer.**
   - Admit the marketplace connector to the audience of CAT-OFFER-01 for this purpose, covering update events (including `enabled` changes) and delete events.
   - Commit to an outbox publication bound: committed change visible on `catalog.product.events` within *T1* (for example ≤ 2 min, p99), including the relay retry path.
   - Conditions: the commit succeeds, the broker is available, and the tenant is in scope.
   - Ideally, also add a version or timestamp to `ProductDeletedEvent`.
2. **Platform / operations (broker owner) → connector:**
   - Provision the consumer group.
   - Set retention long enough to replay after a connector outage.
   - Commit to broker availability, and monitor lag with alerting below *T2* (≤ 1 min).
3. **Connector owner (new) → merchant and Catalog:**
   - Accept the event formats and meanings explicitly, including disable detected as an `enabled` change and idempotent handling.
   - Consume the event and submit an authenticated withdrawal request within *T3* (≤ 2 min).
   - Retry rejected or failed outcomes, and poll the marketplace outcome until *completed* (F2).
   - Raise an alert and escalate to the merchant if the outcome is not *completed* by minute ~10.
   - Run a periodic reconciliation, for example comparing disabled or deleted products against active listings, as a safety net for lost or reordered events.
4. **Marketplace → merchant/publisher: an amendment to DEMO-CONTRACT-001.**
   - A time bound *T4* from an accepted, valid request to *completed* (≤ 8 min), plus availability of the withdrawal endpoint.
   - Without this, the end-to-end bound cannot exist: the slowest stage sits entirely with the marketplace.
5. **Image owner → connector:** extend IMG-OFFER-01's audience for image sync. This has no time bound, because images are not part of the 15-minute requirement.
6. **Merchant ↔ connector operator: a service-level agreement.**
   - It promises the end-to-end time only as the composition T1+T2+T3+T4 ≤ 15 min.
   - It applies under stated conditions: all four parties' commitments hold, the request is valid and accepted, and the product is in a provisioned tenant.
   - It names an explicit remedy or escalation path when any stage fails.
   - It is not a single party's unconditional guarantee.

If the Catalog or marketplace bound cannot be obtained, move to **defer** for the hard requirement. Optionally, the merchant could get manual withdrawal through the marketplace as a stopgap.

## 4. What remains uncertain

- **Outbox relay timing.** How often the relay polls, and its retry and backoff behaviour, were not established. I did not inspect `ecommerce-commons` (`pkg/kafka/outbox`). In any case that would be implementation evidence, not a commitment.
- **Real latencies.** The capture is a local, single-partition snapshot without lag data. Production topology, partitions and throughput are unknown.
- **Willingness of the parties.** It is unknown whether the Catalog, Image and platform owners will admit a new consumer and commit to bounds. It is also unknown whether the marketplace role will amend DEMO-CONTRACT-001 at all. Only those owners can revise their offers.
- **Delete ordering.** `ProductDeletedEvent` has no version, so how a delete interacts with a late, stale update is unresolved. That includes whether Product Query or the connector could recreate a deleted product.
- **Disabled products in Product Query.** Whether Product Query's list or detail reads filter out disabled products at the repository level is unverified.
- **How tenant context is carried.** The event payloads contain no tenant field, and the outbox collection is not tenant-scoped. How tenant context travels in message headers was not verified, and the connector depends on it.
- **The generated event catalog.** Its omissions (F9) raise the question of which other artefacts derived from the architecture documents are incomplete.
- **What "withdrawn" means to the merchant.** The marketplace defines completion as "no longer publicly visible". Whether that matches the merchant's meaning, for example caches or search indexes, is unclear.
- **Bad publisher states.** Outcomes when credentials or authorization are revoked, or when the marketplace rejects a request, fall outside any commitment (F2).

## 5. Did my recommendation change?

The label did not change: it is still **conditional proceed**. The evidence did make it stricter in three ways:

- **Stage-specific bounds are needed from the Catalog owner.** I had expected the existing services to offer at least some usable promise. CAT-OFFER-01 (F1) and PQ-ACCEPT-01 / PQ-READ-01 (F3, F4) instead exclude new consumers and disclaim latency, and the code shows the publish step is best-effort (F8).
- **The marketplace contract is a blocker, not just one more condition.** DEMO-CONTRACT-001 (F2) offers no time bound, so even a perfect internal pipeline cannot deliver 15 minutes without a marketplace amendment.
- **Two design obligations were added.** The generated event catalog omits `ProductDeleted` (F9), and disable is only an `enabled` flag on an update (F6). The connector must therefore be built from the code and the authored declaration, and it must include reconciliation.
