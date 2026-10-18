# AIP v0.7.1 I1.1 — Kafka Consumer-State Source Contract and Identities

**Status:** Frozen on merge of the I1.1 PR. I1.2–I1.4 SHALL NOT reinterpret it.
**Governs:** [`i1-kafka-consumer-state-source.md`](i1-kafka-consumer-state-source.md) §§3–9 and the I0 [decisions](i0-semantic-decision.md).
**Vectors:** [`i1-vectors/`](i1-vectors/) — hand-authored, independent of any adapter. `ids.json` was produced by [`vector-hashes.py`](i1-vectors/vector-hashes.py) (hashlib only); `K09` was cross-checked once against `app.sources.owner_ids.topic_owned_id`.
**Precedent:** the v0.7.0 gateway source (registration model, one offline file, discovery by registration, internal-only carrier nodes). `ld` below is the 8-byte big-endian length + UTF-8 bytes per part encoding of `app.common.encoding.length_delimited`.

## 1. Source kind and registration

- New `SourceKind.KAFKA_CONSUMER_STATE = "kafka_consumer_state"`. Settings gain `kafka_consumer_state: list[...]`, empty by default.
- Registration: `id`, `root`, `capture_relative_path` (default `kafka-consumer-state.json`), `broker_id`, `environment`, `consumer_groups` (non-empty allow-list of exact group ids), optional `configured_scope_id` / `stable_target_identity` defaulting like the APISIX registration.
- `broker_id` is the declared-Topic broker id (`x-aip-broker-id`, for example `kafka:cluster-a`), never a bootstrap address.
- Discovery is by registration. The adapter's `supports()` checks `schema == "aip-kafka-consumer-state/1"`, never the filename. Bounds: file ≤ 8 MiB, nesting ≤ 64.
- Two registrations with the same `broker_id`, `environment` and any common group are both rejected `KAFKA_DUPLICATE_SOURCE` (R12); neither commits.

## 2. Identities (vectors K01–K13)

| Entity | Id |
|---|---|
| Scope digest | `sha256(ld(sorted exact group ids))`, hex (K01; order independent, K02) |
| `SourceInstanceId` | `urn:aip:source:kafka-consumer-state:<sha256(ld(source id, broker id, environment, scope digest))>` (K03; a different scope gives a different id, K04) |
| Consumer identity | `consumer:<sha256(ld("kafka_consumer_state", broker id, environment, group id))>` — the I0 D1 / I1 §3 formula with the registered source kind as first part (K05); environment and broker both change it (K06, K07); the group id is verbatim, no case folding or normalization (K11) |
| Declared Topic (join key) | `topic:owned:<sha256(ld(broker id, "", NFC topic name))>`, the existing derivation; every assignment topic is NFC-normalized first, so composed and decomposed spellings give one id (K09, K12, K13) |
| Attachment | `kafka-attachment:owned:<sha256(ld(consumer id, topic id))>` (K10); capture time is never an id input |

## 3. Capture envelope (`aip-kafka-consumer-state/1`)

Example: [`kafka-consumer-state-capture.example.json`](i1-vectors/kafka-consumer-state-capture.example.json).

`schema`, `broker_id`, `environment`, `captured_at` (RFC 3339 UTC), `tool_version`, `kafka_version`, `complete`, `group_scope` (sorted), `groups[]` = `{group_id, state, members[]}` with `members[]` = `{member_id, client_id, host, assignments[]}` and `assignments[]` = `{topic, partitions[]}`. All arrays are sorted. Member id, client id, host and partitions are evidence detail only.

**Redaction.** The capture utility writes no credential or security property. The adapter rejects a capture with any such field name or a canary value as `KAFKA_CAPTURE_UNREDACTED` (R09) without echoing the value.

## 4. Completeness and group states

A capture is accepted only when all hold: broker id and environment equal the registration (R01, R02); `group_scope` equals the allow-list (R03); `groups[].group_id` equals the allow-list as a unique set: every allow-listed group is described exactly once (R04, R13) and no group outside the allow-list appears (R03); `complete` is true (R08); every state is one of the accepted readings below; fields are valid (R10, R11).

| State | Reading |
|---|---|
| `Stable` | live assignments of its members are the attachments |
| `Empty` | zero live attachment at T (committed offsets are not attachment) |
| `Dead` (reported by the broker) | zero live attachment at T. A deleted configured group is a terminal accepted reading, so its attachments can be removed (resolves the I1 review gap). Only an explicit broker-reported `Dead` counts. A lookup failure, permission error, not-found or any acquisition error is `KAFKA_CAPTURE_INCOMPLETE` (R08), unless the capture utility has converted it into a well-defined authoritative `Dead` reading |
| `PreparingRebalance`, `CompletingRebalance`, unknown or missing | whole capture rejected `KAFKA_STATE_NOT_STABLE` (R05–R07) |

Source revision = `kafka:<kafka_version>+capture:<captured_at>`. A rejected capture preserves all prior accepted state.

**Capture ordering.** `captured_at` is compared as an instant. A capture older than the latest accepted capture of the source is rejected `KAFKA_STALE_CAPTURE` (R14) and never overwrites newer state. A capture with the same instant and identical normalized content is a no-op (L01). A capture with the same instant and different content is rejected `KAFKA_CAPTURE_CONFLICT` (R15); prior state is kept.

## 5. Scope change

A changed allow-list changes the scope digest and therefore the `SourceInstanceId` (K03, K04). The old registration is no longer configured, so the existing unconfigured-source reconciliation retires its carriers through the source-removal transaction, as `retire_unconfigured_gateways` does for gateways. The new source is empty until its first complete capture. A scope change is therefore a configuration change and never evidence that a group detached (L06; resolves the second I1 review gap).

## 6. Canonical carriers and Topic join

Internal-only carrier nodes with their own labels and no relationships to public entities (the v0.7.0 gateway representation):

- `KafkaConsumerGroup`: `id`, `group_id`, `broker_id`, `environment`, source ownership.
- `KafkaConsumerAttachment`: `id`, `consumer_id`, `topic_id`, `captured_at`, `evidence_ids`.

For each live assignment the Topic id is derived with the broker id, the empty namespace and the exact topic name. If no declared Topic has that id, no state is written and a deterministic source diagnostic `KAFKA_TOPIC_NOT_DECLARED` is emitted (A06). It is not persisted as an architecture relation.

## 7. Lifecycle (L01–L06)

Same normalized capture including T is a no-op (L01). The same attachment set with a later T keeps all ids and refreshes `captured_at` and evidence (L02). A later complete capture without an assignment removes that attachment for this source (L03). A rejected capture preserves prior state (L04). An unconfigured source writes nothing (L05).

## 8. Reason codes

`KAFKA_BROKER_MISMATCH`, `KAFKA_ENVIRONMENT_MISMATCH`, `KAFKA_SCOPE_MISMATCH`, `KAFKA_GROUP_NOT_DESCRIBED`, `KAFKA_STATE_NOT_STABLE`, `KAFKA_CAPTURE_INCOMPLETE`, `KAFKA_CAPTURE_UNREDACTED`, `KAFKA_CAPTURE_INVALID`, `KAFKA_UNSUPPORTED_SCHEMA`, `KAFKA_DUPLICATE_SOURCE`, `KAFKA_STALE_CAPTURE`, `KAFKA_CAPTURE_CONFLICT` (rejections, [`capture-rejections.json`](i1-vectors/capture-rejections.json)); `KAFKA_TOPIC_NOT_DECLARED` (diagnostic).

## 9. I1 §9 cases to vectors, and slice ownership

| I1 §9 case | Vector | Slice |
|---|---|---|
| live member on declared Topic; several members; several Topics | A01, A02, A03 | I1.3 |
| Empty / committed offsets only; Dead | A04, A05 | I1.3 |
| rebalance and unknown states | R05–R07 | I1.2 |
| exact scope, duplicate groups, stale and conflicting captures | R03, R13–R15 | I1.2 |
| undeclared Topic | A06 | I1.3 |
| broker / environment / scope mismatch | R01–R03 | I1.2 |
| allow-list change | K03, K04, L06 | I1.3 |
| same group on another broker or environment | K06, K07, A08 | I1.2 |
| known-answer ids (including NFC) | K01–K13 | I1.2 |
| replay, later T, removal, rejection, unconfigured | L01–L05 | I1.3 |
| member / client / host change | A07 | I1.3 |
| secret canary | R09 | I1.2 |
| registration, discovery, capture schema, reason codes | sections 1, 3, 8 | I1.2 |
| I2 handoff | sections 2, 6 | I1.4 |
