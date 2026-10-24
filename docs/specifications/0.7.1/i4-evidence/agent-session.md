# v0.7.1 I4 — Agent session record

This record is filled in by the owner after the session ([kit](../i4-session-kit.md); [I4 spec](../i4-deterministic-real-system-and-product-value-qualification.md) §5). It is one investigation: evidence, not a general adoption claim.

## Setup

| Field | Value |
|---|---|
| Date, operator | 2026-10-21, Michael Egner |
| AIP checkout (`git rev-parse HEAD`) | 108390f0d4d1baa7436f6de65030f1292c2aa455 |
| Agent client, model and version | Claude Code v2.1.306, Opus 5.5 with high effort |
| ecommerce-system checkout | `cd65365838ea880185a02e6536fa347439bfa274` |
| Context card given (verbatim, plus anything extra) | broker_id: kafka:ecommerce-local, environment: local, orders.created Topic id: topic:owned:d50263b3b6fb95e3e67b5ad7bc404874526fee87b3a9b333cc1c7fd1d87f413f |
| Setup effort (minutes, to `tools/list` showing six tools) | 30 min (start 08:42 CET, end 09:12 CET)  |
| Capture times T (from [`replay-metadata.json`](kafka/replay-metadata.json)) | C1 `2026-10-19T06:21:23Z` (arm 2), C2 `2026-10-19T06:23:28Z` (arm 3) |

## Arms

Prompt (unchanged): *I'm changing the `OrderCreated` event that order-service publishes to the Kafka topic `orders.created` (renaming a field). Which Services may be affected, and how sure can we be?*

For each arm, record:

- **Agent conclusion:** which Services, and how certain.
- **What it could not conclude.**
- **Commands or tools it used:** for example source search, a local run, the Kafka CLI, AIP query or evidence.
- **Next action it proposed.**
- **Transcript excerpt (redacted).**

### 1. Without AIP

Gate: `/mcp` showed no MCP servers.

- **Agent conclusion:** payment-service is the only consumer of `orders.created` in the repo. order-service is affected as the producer, because its outbox rows are read back into `OrderCreatedEvent`. Tests, the payload generator script and the docs also need updating. The impact depends on the field: renaming `totalAmount`, `orderId` or `userId` breaks payment-service silently, and renaming `items` has no runtime effect. Certainty: "fairly sure" within the repo.
- **What it could not conclude:** which consumer groups are attached on the broker, since the stack was not running and it did not start it, and whether anything outside the repo consumes the topic (there is no schema registry or contract test, and topic auto-create is on).
- **Commands or tools it used:** source search only (5 search patterns, 3 shell commands). No local run, no Kafka CLI.
- **Next action it proposed:** start the stack and run `kafka-consumer-groups --describe --all-groups | grep orders.created`, noting that this shows only groups that commit offsets. Then a three-step tolerant-reader rollout: payment-service accepts both names and rejects a nil `orderId` or an amount ≤ 0; order-service adds `@JsonAlias` for the old name and then publishes the new one; finally the fallbacks are removed.
- **Transcript excerpt (redacted):** "payment-service is the only consumer of orders.created in this repo." … "Not sure about anything outside the repo. There's no schema registry or contract test." … "A consumer elsewhere (an analytics job, a teammate's tool, kafka-console-consumer) wouldn't show up in a code search."

### 2. With AIP, C1

- **Agent conclusion:** payment-service is affected, with high confidence, because two separate sources agree. The capture shows the `payment-service` group attached to the topic at 2026-10-19 06:21Z, and the explicit mapping ties that group to `service:payment-service`. Its code decodes the event into a struct that hard-codes the field names. A second group, `ops-tail`, was also attached at capture time; it has no mapping and the repo never names it, so it is low confidence and unowned. The agent also named order-service itself: outbox rows written before the deploy go out with the renamed field set to null. The per-field impact on payment-service matches arm 1.
- **What it could not conclude:** who owns `ops-tail`, and whether it reads the messages at all ("Being attached to a topic doesn't prove a group processes its messages"). It also could not say the list is complete: the capture covers only the configured groups, "at one moment two days ago"; only the local environment on `kafka:ecommerce-local`; and readers without a consumer group never appear.
- **Commands or tools it used:** `get_destination_consumers` in query mode, then source search (`grep`, file reads). Then evidence mode for the mapping of `payment-service` and the attachment of `ops-tail`. The first evidence call failed with `evidence_refs must be sorted and duplicate-free`, and the agent retried with the refs sorted. No local run, no Kafka CLI.
- **Next action it proposed:** ask the ops team who owns `ops-tail`, or run `kafka-consumer-groups --describe --group ops-tail` to see whether it has active members and still commits offsets. Then a two-step rename: publish both names while payment-service reads the new one with a fallback, and stop publishing the old name once the outbox is empty and `ops-tail` is accounted for. It also suggested making payment-service reject a nil `orderId` or an amount ≤ 0.
- **Transcript excerpt (redacted):** "payment-service is the only service I can confirm is affected. A second consumer group, ops-tail, is also attached to the topic, and I can't tell who owns it. I'm sure about payment-service, less sure about ops-tail, and the list may not be complete."

### 3. With AIP, C2 (after the refresh, continuing the arm-2 conversation)

- **Agent conclusion:** the answer stands: payment-service is affected, `ops-tail` is unknown, and the list may not be complete. The agent noticed the newer capture (06:23:28Z, two minutes after C1, with the same watched groups) and that it shows no consumer on `orders.created`. It said: "An empty capture doesn't mean nobody reads the topic", and gave stopped consumers as the likeliest reason. payment-service stays "certain to break", with the code now the evidence instead of the capture. It lowered `ops-tail` to "lower confidence than before", because the group was attached at 06:21 and gone two minutes later, which fits a short console tail better than a dependent service. It still advised checking with ops before the old name is removed.
- **What it could not conclude:** "The two captures disagree, so the live data can't confirm or rule out any consumer." The other limits are the same as in arm 2: watched groups only, captures two days old, local on `kafka:ecommerce-local` only, and readers without a group never appear.
- **Commands or tools it used:** `get_destination_consumers` in query mode, once, which returned 0 rows with `CAPTURE_SCOPE_LIMITED`. No evidence call, no new source search, no local run.
- **Next action it proposed:** the arm-2 rollout, unchanged. For fresh live data, start the stack and run `kafka-consumer-groups --describe --all-groups`, filtered for `orders.created`.
- **Transcript excerpt (redacted):** "An empty capture doesn't mean nobody reads the topic. It only means none of the watched groups were attached to orders.created at 06:23:28Z." … "payment-service: still certain to break, but the evidence is now the code, not the live capture."

## Assessment

| Question | Answer |
|---|---|
| Did the broker evidence change the investigation or the next action? Where? | Yes, both. Arm 1 found payment-service by code search alone. It proposed listing the broker's groups but never did it. In arm 2 the agent called AIP first and then searched the code for what AIP returned, including `ops-tail`. The next action changed too: finding who owns `ops-tail` became a condition before the old field name is dropped. Arm 1's rollout had no such step. |
| Configuration shows payment-service as a possible consumer. Did the agent keep "no attachment at T" (C2) apart from "does not consume"? | Yes for payment-service: "An empty capture doesn't mean nobody reads the topic". It kept payment-service as affected, on the code evidence. Partly for `ops-tail`: it lowered the group's confidence because it was gone at 06:23. payment-service was gone too, and both had in fact only stopped (Empty, offsets committed; `expected.json` c2). It treated the absence of one group as weak negative evidence, but not the other's. |
| Did the agent find or handle `ops-tail`, a consumer that no configuration names (C1)? | Yes. It reported the group as UNRESOLVED / NO_MAPPING, searched the repo for the name (no hit), and called it unowned and low confidence. It made the group's owner a rollout condition and proposed `kafka-consumer-groups --describe --group ops-tail`. Arm 1 could not see the group. |
| Did the agent present an at-T observation as a complete change-impact assessment? | No. Each AIP answer gave the capture time and said the list may be incomplete: configured groups only, local only, readers without a group invisible. The scope caveat is real: `analytics-tap`, a group outside the allow-list on `payments.completed`, was attached at C1 and never appears in any answer. |
| Effort: refresh (C1 → C2), minutes | 1 |
| Effort: Service mapping | Spent before the session: the reviewed mapping and its configuration chain ([review](kafka/mapping-review.md)) |
| Unresolved / ambiguous rows | C1: 1 of 4 rows unresolved (`ops-tail`), 0 ambiguous; C2: 0 of 2 |
| Does the value outweigh the work of keeping the evidence current? | For this investigation, yes. The value: one consumer that code search could not find (`ops-tail`), a concrete gate in the rollout, and stated at-T limits. The work: 30 min setup, 1 min refresh, plus the mapping review before the session. Limits: one local system and one change; the allow-list needs upkeep, since a group outside it (`analytics-tap`, on `payments.completed`) is never seen; ownership of `ops-tail` stays a human question. Friction: an evidence call is rejected unless `evidence_refs` is sorted (arm 2, one retry). |

## Decision

**`CONTINUE`:**

Reason (owner, one or two sentences): The semantics hold against independent ground truth: real Kafka C1/C2, A/B identical, and RabbitMQ kept SOURCE_SPECIFIC. In the session, broker evidence surfaced a consumer that code search could not find (ops-tail) and turned it into a rollout gate, without the agent presenting the capture as complete. Carried limits: one local system, the allow-list needs upkeep, and the sorted-evidence_refs friction.
