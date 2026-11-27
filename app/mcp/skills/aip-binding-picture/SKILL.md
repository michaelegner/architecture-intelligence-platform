---
name: aip-binding-picture
description: Use when you call the experimental AIP tool get_binding_picture or report its answer. States its two modes, how to read the crossing and status of each binding row, and the limits of what the answer establishes.
---

# Reading the AIP binding picture (experimental)

`get_binding_picture` is **experimental** (v0.8). Its semantics are not a v1.0 contract. Read its
answers with the rules in the `aip-reading-answers` skill, and with the rules below.

## The two modes

- **Query** (`request.mode` `"query"`): give `bounded_context_id` (a catalog domain id, such as
  `catalog-management`), `environment`, and optionally `broker_ids`. A broker id is a declared
  broker id (`x-aip-broker-id`, such as `kafka:...`), not a bootstrap address. Each row is one
  consumer Service x Topic x broker.
- **Evidence** (`request.mode` `"evidence"`): resolves the answer's `binding-evidence:` refs at the
  same snapshot. The promise path also shows the event to topic lookup entry. Use this mode, not
  `get_evidence`, for these refs.

## Reading a row

- **Crossing** classifies the binding against the selected Bounded Context: `INBOUND`, `INSIDE`,
  `OUTBOUND`, `NONE` or `UNRESOLVED`. A crossing never states delivery.
- **Status** says whether a catalog promise covers the binding and what the broker capture
  establishes:
  - `PROMISED_AND_OBSERVED`: a promise covers it, and the capture shows it;
  - `PROMISED_NOT_OBSERVED`: a promise covers it, and the capture does not show it;
  - `UNRESOLVED` with a reason, such as `PROMISE_COVERAGE_MISSING` for an observed binding that no
    promise covers.
- Each row also lists the declared producers and its evidence refs.

## Limits

- An attachment is not event handling.
- Producers are declared only. AIP does not observe them.
- Delivery between brokers is never established (`CROSS_BROKER_DELIVERY_NOT_ESTABLISHED`).
- Report each limitation of the answer as an unknown. Do not state more than the answer
  establishes.
