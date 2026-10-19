# v0.7.1 I4 — Agent session record

This record is filled in by the owner after the session ([kit](../i4-session-kit.md); [I4 spec](../i4-deterministic-real-system-and-product-value-qualification.md) §5). It is one investigation: evidence, not a general adoption claim.

## Setup

| Field | Value |
|---|---|
| Date, operator | |
| AIP checkout (`git rev-parse HEAD`) | |
| Agent client, model and version | |
| ecommerce-system checkout | `cd65365838ea880185a02e6536fa347439bfa274` |
| Context card given (verbatim, plus anything extra) | |
| Setup effort (minutes, to `tools/list` showing six tools) | |

## Arms

Prompt (unchanged): *I'm changing the `OrderCreated` event that order-service publishes to the Kafka topic `orders.created` (renaming a field). Which Services may be affected, and how sure can we be?*

For each arm, record:

- **Agent conclusion:** which Services, and how certain.
- **What it could not conclude.**
- **Commands or tools it used:** for example source search, a local run, the Kafka CLI, AIP query or evidence.
- **Next action it proposed.**
- **Transcript excerpt (redacted).**

### 1. Without AIP

-

### 2. With AIP, C1

-

### 3. With AIP, C2 (after the refresh, continuing the arm-2 conversation)

-

## Assessment

| Question | Answer |
|---|---|
| Did the broker evidence change the investigation or the next action? Where? | |
| Configuration shows payment-service as a possible consumer. Did the agent keep "no attachment at T" (C2) apart from "does not consume"? | |
| Did the agent find or handle `ops-tail`, a consumer that no configuration names (C1)? | |
| Did the agent present an at-T observation as a complete change-impact assessment? | |
| Effort: refresh (C1 → C2), minutes | |
| Effort: Service mapping | Spent before the session: the reviewed mapping and its configuration chain ([review](kafka/mapping-review.md)) |
| Unresolved / ambiguous rows | C1: 1 of 4 rows unresolved (`ops-tail`), 0 ambiguous; C2: 0 of 2 |
| Does the value outweigh the work of keeping the evidence current? | |

## Decision

**`CONTINUE | NARROW | DEFER | STOP`:**

Reason (owner, one or two sentences):
