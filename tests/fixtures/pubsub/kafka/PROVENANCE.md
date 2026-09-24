# Kafka fixture: provenance and disclosure (negative boundary)

**Spec:** v0.5.0 I4 §13.3 fixture 3. **Role:** a negative normalization fixture (§4.1).
**Sources:** S5 (the OTel messaging attribute registry, where the consumer group and the destination subscription are distinct attributes) and S7 (Kafka 4.3 Design, where a group is partition and offset assignment), from
[`i4-decision-evidence.md`](../../../../docs/specifications/0.5.0/i4-decision-evidence.md) §1.
**Retrieval date:** 2026-09-23.

## Authored scenario data

Everything here is authored. Nothing is captured from a live cluster.

- **Broker:** one cluster, declared as `x-aip-broker-id: kafka:cluster-a` with `protocol: kafka`.
- **Topic `inventory`:**
  - `warehouse` publishes to it.
  - `stock-projector` subscribes with `x-aip-consumer-group: stock-projector` and **no** `x-aip-subscription-name`.
- **Spans** (`spans.yaml`, `messaging.system=kafka`):
  - `warehouse` sends.
  - Two `stock-projector` members, one doing `receive` and one doing `process`, carry `messaging.consumer.group.name=stock-projector`. Neither carries a subscription name.

## Expected facts
- The Topic is still modelled, because the declared evidence is sufficient (§13.3). The facts are `PUBLISHES_TO warehouse→inventory` and `CARRIES`, one per declaring document.
- OBSERVED evidence on `PUBLISHES_TO`.
- The `stock-projector` source is `ACCEPTED_WITH_LIMITATIONS`, with `SUBSCRIPTION_IDENTITY_MISSING` at `/channels/inventory/subscribe` (§8.3).
- Both consumer spans are unresolved.
- The answer for `warehouse` has one Topic `DIRECT_TARGET_FALLBACK` claim, which is CONFIRMED and has `UNRESOLVED_IDENTITY`.

## Forbidden facts
Everything not listed in `expected.yaml` is forbidden. In particular:
- **any** `Subscription` node, whether declared or from runtime;
- any `RECEIVES_FROM` involving `stock-projector`;
- the consumer group used as a Subscription name or as an alias;
- any claim resolved to `stock-projector`.

## Unsupported / deferred (§3.2)
These are not modelled, and none of them appear in the fixture:
- partitions and partition assignment;
- offsets and lag;
- consumer rebalancing;
- transactions;
- share groups (KIP-932, named from general knowledge in the decision evidence and not independently retrieved).
