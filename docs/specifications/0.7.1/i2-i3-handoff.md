# AIP v0.7.1 I2 → I3 Handoff

Governing: [I2 spec](i2-service-mapping-and-attribution.md) §9, [I2.1 contract](i2-kafka-service-mapping-contract.md), [I1 → I2 handoff](i1-i2-handoff.md) and [I0 decisions](i0-semantic-decision.md).

I2 delivers a derived, snapshot-bound attribution: in one snapshot, mapping evidence attributes Service S to consumer group G, and broker evidence observed G attached to Topic D at T. It does not mean S processed a message or still consumes D after T.

## 1. What I3 receives (internal, snapshot-visible, nothing public)

Snapshot key `kafka_consumer_attribution_v1`, present only when a mapping carrier exists; every section is sorted and has no null values.

| I2 §9 item | Block field |
|---|---|
| consumer group identity | `attributions[].consumer_id` (= I1 consumer id); `groups[].id`, `groups[].group_id` |
| destination | `attributions[].topic_id` (an already-declared Topic) |
| capture time T | `attributions[].captured_at` |
| reconciliation / attribution outcome | `groups[].outcome`, `attributions[].outcome` (`RESOLVED`, `UNRESOLVED`, `AMBIGUOUS`, `CONFLICT`) |
| Service id when resolved | `service_id`, present only when `RESOLVED` |
| conflict / limitation reason | `reason`; `limitations[]` (`entry_id`, `reason`) for non-resolving entries of a resolved group; each entry's own reading in `groups[].entries[]` |
| evidence for the attachment | `attributions[].attachment_evidence_ids` → `KafkaCaptureEvidence` in `kafka_consumer_state_v1.evidence` |
| evidence for every contributing mapping entry | `attributions[].mapping_entries[]` (`id`, `evidence_ids`) → `mapping_entries`, `mapping_sources` |
| reproducibility | `rule` (`kafka-consumer-attribution` / `1`) and `aliases_applied` |

Rows: one per I1 attachment (several members of one group on one Topic are one row; one group on two Topics is two rows). A mapping without an attachment is a group row and no attribution row.

## 2. Facts I3 must respect

- The outcome is derived per snapshot; nothing is persisted beyond the mapping carriers. A changed Service declaration or alias configuration changes the outcome at the next snapshot.
- Only a `RESOLVED` row names a Service. `UNRESOLVED`, `AMBIGUOUS` and `CONFLICT` are explicit and must not be presented as "no consumer" or as a negative claim.
- T is the broker capture time; the mapping has no observation time and must not be described as observed at T.
- The configured `telemetry.service_aliases` are part of the snapshot state; any new snapshot reader must pass them (`canonical_snapshot_state(..., service_aliases=...)`).
- No `RECEIVES_FROM`, Service→Topic relationship or Subscription exists for an attribution; I3 must not create one.

## 3. I3 decides

- The public question and answer shape, and whether non-resolved outcomes are listed.
- How the internal evidence carriers (`KafkaCaptureEvidence`, `KafkaServiceMappingEvidence`) are exposed through evidence resolution: neither is an `:Evidence` node today.
- How attribution relates to declared consumers (declared Subscriptions) in an answer.
