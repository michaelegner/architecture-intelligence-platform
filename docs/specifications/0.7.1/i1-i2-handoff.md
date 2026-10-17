# AIP v0.7.1 I1 → I2 Handoff

Governing: [I1 spec](i1-kafka-consumer-state-source.md) §11, [I1.1 contract](i1-kafka-source-contract.md), [I0 decisions](i0-semantic-decision.md) and [I0 handoff](i0-i1-i2-handoff.md).

I1 delivers broker evidence only: which consumer group is attached to which already-declared Topic at capture time T. It joins nothing to a Service.

## 1. What I2 receives (internal state, snapshot-visible, nothing public)

| State | Fields | Notes |
|---|---|---|
| `KafkaConsumerGroup` | consumer id, `group_id`, `broker_id`, `environment` | one per allow-listed group, any state; id = contract §2 (K05) |
| `KafkaConsumerAttachment` | consumer id, declared `topic_id`, `captured_at`, `evidence_ids`, `support_json` (`member_count`, `member_partitions`) | only for live `Stable` assignments to a declared Topic; id = K10, T is not an id input; no member id, client id or host is stored |
| `KafkaCaptureEvidence` | `captured_at`, capture content digest, scope digest, source revision, `group_states_json`, `configured_source_id` | one per source instance: the last accepted capture |
| snapshot key | `kafka_consumer_state_v1` (`groups`, `attachments`, `evidence`) | present only when Kafka carriers exist |
| diagnostics | `KAFKA_*` codes, fixed text | `KAFKA_TOPIC_NOT_DECLARED` is a diagnostic only, never state |

## 2. Canonical, source-qualified, unresolved

- **Canonical (I1-owned):** the carriers, their ids and the lifecycle (a complete accepted capture is authoritative for its source; a rejected one does not commit and removes nothing; ordering R14/R15 holds at commit time).
- **Source-qualified:** member count and partitions in `support_json`; group states; undeclared-Topic diagnostics.
- **Unresolved for I2:** consumer identity → Service. I1 emits no such association and infers none from group names. Member ids, client ids and hosts are not in AIP state, so I2 cannot use a runtime host join even as corroboration unless it brings its own source for it.

## 3. Facts I2 must respect

- Attachment is point-in-time at T, never "currently" (I0 D4).
- `Empty` and `Dead` mean zero live attachment at T, not that no Service consumes the Topic.
- Combine an attachment with a mapping only for the same environment and snapshot generation (I0 D4).
- Service resolution is DECLARED-only through `decide_service_identity`; its `OBSERVED_ONLY` outcome is rejected (I0 D3).
- If I2 writes state that depends on other sources' graph state, use the `commit_guard` hook of `import_discovery_run` rather than checks before the transaction.

## 4. I2 owns

The mapping artifact format and its accepted sources, `RESOLVED` / `UNRESOLVED` / `AMBIGUOUS` / `CONFLICT`, derived Service-level attribution, and the I0 §8 cases on the Service side.
