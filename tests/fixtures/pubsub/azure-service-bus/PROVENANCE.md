# Azure Service Bus fixture: provenance and disclosure

**Spec:** v0.5.0 I4 §13.3 fixture 1. **Role:** positive broker.
**Sources:** S1 (queues, topics and subscriptions, `ms.date` 2026-01-31) and S2 (dead-letter queues,
`ms.date` 2026-07-16), from
[`i4-decision-evidence.md`](../../../../docs/specifications/0.5.0/i4-decision-evidence.md) §1.
**Retrieval date:** 2026-09-23.

## Authored scenario data

Everything here is authored. Nothing is captured from a live namespace.

- **Broker:** one namespace, declared as `x-aip-broker-id: azure-sb:commerce` with `protocol: amqp`. There are no AMQP bindings, so every entity has namespace `null`.
- **Queue `payments`:**
  - `orders` sends to it.
  - `payment-worker-a` and `payment-worker-b` both receive from it. These are competing consumers (S1, "only one message consumer receives and processes each message").
- **Topic `order-events`:**
  - `orders` publishes to it.
  - Subscription `billing` is consumed by `billing`, and Subscription `audit` is consumed by `audit`. Each published message is copied to each subscription (S1).
- **Dead-letter configuration:** `billing` declares `x-aip-subscription-dead-letter`.
  - The target is the per-subscription sub-queue token `order-events/Subscriptions/billing/$deadletterqueue` (S2).
  - The target kind is `queue`.
- **Spans** (`spans.yaml`, `messaging.system=servicebus`):
  - `orders` sends to `payments` and to `order-events`.
  - Two `payment-worker-a` instances receive from `payments`.
  - Two `billing` instances process from `order-events` with `messaging.destination.subscription.name=billing`. That attribute placement is the OTel shape for Service Bus (S5).

## Expected facts
- `SENDS orders→payments`.
- `RECEIVES_FROM payment-worker-a→payments` and `RECEIVES_FROM payment-worker-b→payments`. These are competing consumers.
- `PUBLISHES_TO orders→order-events`.
- `SUBSCRIPTION_OF` for both `billing` and `audit` onto `order-events`. These two Subscriptions are the only expression of fan-out.
- `RECEIVES_FROM billing→Subscription billing` and `RECEIVES_FROM audit→Subscription audit`.
- `CARRIES`, one per declaring document.
- OBSERVED evidence on `SENDS`, `PUBLISHES_TO`, `RECEIVES_FROM payment-worker-a` and `RECEIVES_FROM billing→billing`.
- The two `billing` instances collapse into one logical consumer.
- The dependency answer for `orders` has four resolved claims. There are two Queue claims, which carry no route and are not fan-out. There are two routed Subscription claims, which are fan-out.
- The Queue claim ids equal the pre-I4 five-field formula.
- Exactly one `SubscriptionDeadLetterConfiguration` exists, and it is scoped to `billing`.

## Forbidden facts
Everything not listed in `expected.yaml` is forbidden. In particular:
- `DEAD_LETTERS_TO`.
- Any Queue, Topic or Subscription minted for the dead-letter token.
- A dead-letter carrier on `audit`.
- `RECEIVES_FROM` pointing at a Topic.
- A claim that treats the Queue's competing consumers as fan-out.
- A third claim for the second `billing` instance.

## Unsupported / deferred (§3.2)
These are not modelled, and none of them appear in the fixture:
- subscription filters, rules and actions (S1);
- auto-forwarding and transfer dead-letter queues (S2);
- JMS shared and durable subscriptions, and express entities (S1).

The dead-letter token is carried as an opaque token and is never resolved (spec §10).
