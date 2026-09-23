# AIP v0.5.0 I4 — Decision Evidence Record

**Governing specification:** [`i4-source-independent-pubsub-semantics.md`](i4-source-independent-pubsub-semantics.md)
Draft 0.3, as merged at `f98e48b` (#226, #227 residuals)<br>
**Slice:** I4 Slice 1 — Decision and canonical foundation (spec §15)<br>
**Decision:** `GO` — recorded in [ADR 0017](../../adr/0017-source-independent-pubsub-semantics.md)<br>
**Evidence retrieval date:** 2026-09-23

This record is the §15 Slice 1 "independent evidence record". It is evidence, not qualification.
It shows that the §4 semantic distinctions are supported by independent public broker and
OpenTelemetry documentation. The deterministic broker-semantic fixtures in §13.3 remain slice 5
work.

---

## 1. Sources

Quoted passages are short excerpts as retrieved on 2026-09-23. The URLs are the canonical public
documentation pages the spec cites in §4.1, plus two dead-letter pages cited for §10.

| # | Source | URL |
|---|---|---|
| S1 | Azure Service Bus — Queues, topics, and subscriptions (`ms.date` 2026-01-31) | https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-queues-topics-subscriptions |
| S2 | Azure Service Bus — Dead-letter queues (`ms.date` 2026-07-16) | https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-dead-letter-queues |
| S3 | Google Cloud Pub/Sub — Pub/Sub basics (was `cloud.google.com/pubsub/docs/pubsub-basics`, now 301 → `docs.cloud.google.com`) | https://docs.cloud.google.com/pubsub/docs/pubsub-basics |
| S4 | Google Cloud Pub/Sub — Handle message failures | https://docs.cloud.google.com/pubsub/docs/handling-failures |
| S5 | OpenTelemetry semantic conventions — Messaging attribute registry | https://opentelemetry.io/docs/specs/semconv/registry/attributes/messaging/ |
| S6 | OpenTelemetry semantic conventions — Messaging spans | https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/ |
| S7 | Apache Kafka 4.3 documentation — Design (the spec's `documentation/#design` anchor now resolves to a navigation hub; this is the current Design page) | https://kafka.apache.org/43/design/design/ |

### Quoted evidence

- **S1, Queues:** "Queues offer First In, First Out (FIFO) message delivery to one or more competing
  consumers. ... only one message consumer receives and processes each message."
- **S1, Topics and subscriptions:** "Each published message is made available to each subscription
  registered with the topic. Publisher sends a message to a topic and one or more subscribers
  receive a copy of the message." Also: "consumers don't receive messages directly from the topic.
  Instead, consumers receive messages from subscriptions of the topic. ... subscriptions support the
  same patterns described earlier in this section regarding queues: competing consumer, temporal
  decoupling, load leveling, and load balancing."
- **S2:** "Each queue and each subscription has its own dead-letter sub-queue." It is addressed as
  `<topic path>/Subscriptions/<subscription path>/$deadletterqueue`.
- **S3, Fan-out:** "a single topic is attached to multiple subscriptions. ... Each of the subscriber
  applications gets the same set of published messages from the topic."
- **S3, Load balancing:** "a single topic is attached to a single subscription that is, in turn,
  connected to multiple subscriber applications. Each of the subscriber applications gets a subset
  of the published messages, and no two subscriber applications get the same subset."
- **S4:** "You configure a dead-letter topic on a subscription, not on the topic it pulls from.
  This is because it's a subscription property."
- **S5:** `messaging.destination.subscription.name` is "The name of the destination subscription
  from which a message is consumed." `messaging.consumer.group.name` is "The name of the consumer
  group with which a consumer is associated", and it carries the note that "Semantic conventions
  for individual messaging systems SHOULD document whether `messaging.consumer.group.name` is
  applicable and what it means in the context of that system." Both are *Development* stability,
  and they are two distinct registry attributes.
- **S7:** "each partition is consumed by exactly one consumer within each subscribing consumer
  group at any given time." The position of a consumer is tracked per partition as an offset. Group
  semantics are therefore expressed through partition assignment and offsets, the constructs spec
  §3.2/§6.2 exclude from the generic model.
- **S6:** `messaging.destination.name` "SHOULD uniquely identify a specific queue, topic or other
  entity within the broker". No destination-kind attribute is defined in the current conventions.

---

## 2. §4 distinctions → evidence

| §4 distinction | Supported by | Disposition |
|---|---|---|
| `Queue != Topic` | S1: queue = single consumer per message; topic = copies per subscription | Supported |
| `Topic != Subscription` | S1: consumers receive from subscriptions, not the topic. S3: topic attached to subscriptions | Supported |
| `AsyncAPI Channel != broker destination` | Unchanged I1 §9 rule (Channel is a source-language construct). No broker source says otherwise | Retained |
| `consumer instance != Subscription` | S1: consumers compete within a subscription. S3: multiple subscriber applications share one subscription's messages | Supported |
| `consumer group != automatically Subscription` | S5: distinct attributes, with group meaning left to each system. S7: group semantics are partition/offset-based | Supported (Kafka negative boundary) |
| Queue + multiple consumers → competing consumers, no fan-out | S1 | Supported |
| Topic + multiple Subscriptions → fan-out | S1, S3 | Supported |
| one Subscription + multiple consumer instances → load balancing, not fan-out | S1, S3 | Supported |
| same destination name → no identity equivalence across kind/broker/namespace | S1 (queues and topics are separate entity kinds in one namespace). Spec §7 identity is broker/namespace scoped with type-distinct prefixes | Retained by identity formula |
| runtime destination name alone → insufficient kind evidence | S6: `messaging.destination.name` "SHOULD uniquely identify a specific queue, topic or other entity within the broker", and the current conventions define no generic destination-kind attribute (AIP's recognized `messaging.destination_kind` is a legacy key) | Supported |
| runtime consumer-group name alone → insufficient Subscription identity | S5 | Supported |

## 3. §4.2 GO condition

The abstraction in §4.2 is supported by two materially different positive brokers:

- **Azure Service Bus (S1/S2):** a Subscription is a broker-held named entity under a Topic, and
  consumers compete within it. **Google Cloud Pub/Sub (S3/S4):** a Subscription is a named entity
  attached to one Topic, and subscribers load-balance within it. Both map to
  `Topic ← SUBSCRIPTION_OF ← Subscription ← RECEIVES_FROM ← Service` with no product-specific
  entity.
- **Kafka (S7)** has no broker-held named Subscription. A consumer group is a distinct
  partition/offset construct, and is modeled only as the §4 negative boundary.

**No broker-specific production exception is required** for either positive broker. The one place
the two differ materially is dead-letter handling: ASB has a per-subscription dead-letter subqueue
(S2), and Google has a dead-letter *topic* configured as a subscription property (S4). The spec
already handles this difference generically through §10's internal, Subscription-scoped
`SubscriptionDeadLetterConfiguration` carrier, which forces no target kind. That difference is the
reason the spec forbids a generic `Subscription -[DEAD_LETTERS_TO]-> Queue`. It is not an exception
to it.

**Outcome: `GO`.** The §4.2 condition "If either positive broker fixture requires a broker-specific
production exception, the outcome SHALL be `DEFER`" does not trigger on this evidence. The slice 5
fixtures (§13.3) remain the executable re-check. If a fixture later needs an exception, that is
stop condition §16 #11, and the decision returns to review.

### Disclosed, out-of-scope constructs

These remain unsupported and deferred, per §3.2:

- ASB subscription filters/rules and actions (S1);
- ASB transfer dead-letter queues and auto-forwarding (S2);
- ASB JMS shared/unshared durable subscriptions and express entities (S1);
- Kafka partitions, offsets, and consumer rebalancing (S7);
- Kafka share groups (KIP-932; named here from general knowledge, not independently retrieved
  for this record).

None of these constructs becomes Subscription or Queue semantics in I4.

---

## 4. §19 entry-gate checklist dispositions

| Checklist item | Disposition |
|---|---|
| I4 decision is explicit GO or DEFER | **GO**, recorded here and in ADR 0017 (Status `Proposed` until the I4 work lands, per the ADR index convention) |
| Azure Service Bus and Google Pub/Sub independently support the abstraction | Satisfied, §3 above. Executable fixtures: slice 5 |
| Kafka consumer group is not normalized to Subscription | Satisfied by spec §4/§7.2/§9. Slice 1's `subscription_owned_id` has no consumer-group input (pinned by test). Runtime guard: slice 3. Fixture: slice 5 |
| Queue remains competing-consumer semantics | Satisfied. Queue model, identity and claim ids are unchanged in slice 1 |
| Queue and Subscription each preserve one resolved claim per distinct evidenced logical consumer without calling it fan-out | Specified in §6.3/§12.3. Projection: slice 4 |
| Topic fan-out is represented by distinct Subscriptions | Specified in §6.3. Slice 1 `Subscription` carries no consumer fields. Projection: slice 4 |
| Multiple instances on one Subscription are not fan-out | Specified in §6.3/§12.3. Slice 4/5 |
| AsyncAPI Channel is not automatically Queue/Topic | Specified in §8. Slice 2 |
| `x-aip-destination-kind` is bounded to `queue\|topic` | Specified in §8.1. Slice 2 |
| Topic identity requires stable broker/namespace evidence | Slice 1 `topic_owned_id` takes the broker id and namespace as required inputs. Evidence sourcing: slice 2 |
| Subscription identity includes Topic id | Slice 1 `subscription_owned_id` binds the canonical Topic id (pinned by test) |
| `subscribe` direction alone cannot mint Subscription | Specified in §8.3. Slice 2 |
| Runtime cannot mint Topic/Subscription | Specified in §9. Slice 3 |
| Consumer-group name cannot resolve Subscription | Specified in §9. Slice 3 |
| Existing v0.4.1 destination/service guards remain active | Unchanged in slice 1. ADR 0017 retains both |
| I3 `DEPLOYED_AS` and Kubernetes placement are not Pub/Sub evidence | Specified in §2. No slice 1 code reads them |
| Exactly three MCP tools remain | Unchanged in slice 1 (existing tool-count tests) |
| `ArchitectureIntelligenceService` remains semantic owner | Unchanged in slice 1 |
| Queue claim ids remain unchanged | Slice 1 leaves the claim-id payload unchanged. The optional `subscription_id` lands in slice 4 |
| Canonicalization version bumps to 3, with Topic/Subscription node queries, in the first slice that persists new public state | Slice 2. Slice 1 pins `_CANONICALIZATION_VERSION == 2` and a closed persistence path |
| Schema version remains `0.5` | Satisfied. The slice 1 schema widening stays at `0.5` |
| No live broker adapter is added | Satisfied |
| No broker-specific production branch is required | Satisfied on this evidence (§3). Slice 5 re-checks it executably |
