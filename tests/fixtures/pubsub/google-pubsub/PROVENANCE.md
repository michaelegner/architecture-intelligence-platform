# Google Cloud Pub/Sub fixture: provenance and disclosure

**Spec:** v0.5.0 I4 §13.3 fixture 2. **Role:** positive broker.
**Sources:** S3 (Pub/Sub basics) and S4 (handle message failures), from
[`i4-decision-evidence.md`](../../../../docs/specifications/0.5.0/i4-decision-evidence.md) §1.
**Retrieval date:** 2026-09-23.

## Authored scenario data

Everything here is authored. Nothing is captured from a live project.

- **Broker:** one project, declared as `x-aip-broker-id: gcp-pubsub:projects/shop` with `protocol: googlepubsub`. Every entity has namespace `null`.
- **Topic `orders`:**
  - `checkout` publishes to it.
  - Subscriptions `fulfillment` (consumed by `fulfillment`) and `analytics` (consumed by `analytics`). "a single topic is attached to multiple subscriptions" is fan-out (S3).
- **Dead-letter configuration:** `fulfillment` declares a dead-letter topic token `orders-dead-letter` with target kind `topic`. The dead-letter topic is a subscription property (S4).
- **Spans** (`spans.yaml`, `messaging.system=gcp_pubsub`):
  - Three `fulfillment` instances receive on Subscription `fulfillment`. Multiple subscriber applications on one subscription load-balance it (S3).
  - One `analytics` span names an undeclared Subscription, `ghost`.
  - The publisher is deliberately left unobserved, so the declared routes surface as drift.

## Expected facts
- `PUBLISHES_TO checkout→orders`.
- `SUBSCRIPTION_OF` for both `fulfillment` and `analytics` onto `orders`.
- `RECEIVES_FROM fulfillment→Subscription fulfillment` and `RECEIVES_FROM analytics→Subscription analytics`.
- `CARRIES`, one per declaring document.
- OBSERVED evidence only on `RECEIVES_FROM fulfillment→fulfillment`.
- The three `fulfillment` instances collapse into one logical consumer.
- The `ghost` span is the only unresolved span.
- The answer for `checkout` has two routed resolved claims. Both are `NOT_OBSERVED_IN_WINDOW`. Qualification comes from the publisher, the same as for Queue, and the publisher is unobserved.
- The drift answer for `checkout` carries exactly those two claims.
- Exactly one dead-letter carrier exists: `[fulfillment, orders-dead-letter, topic]`.

## Forbidden facts
Everything not listed in `expected.yaml` is forbidden. In particular:
- a `Topic orders-dead-letter` node;
- `DEAD_LETTERS_TO`;
- a `ghost` Subscription or any fact from the `ghost` span;
- one claim per subscriber instance;
- consumer evidence from `fulfillment` appearing on the `analytics` route.

## Unsupported / deferred (§3.2)
These are not modelled, and none of them appear in the fixture:
- subscription filters;
- exactly-once delivery and ordering keys;
- push/pull delivery type;
- the dead-letter retry policy and maximum delivery attempts.

The dead-letter token stays opaque (spec §10). Only the dead-letter topic comes from S4. The other
items in this list are named from general knowledge and were not independently retrieved.
