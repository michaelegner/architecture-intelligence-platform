# AIP v0.7.1 I2.1 — Kafka Service-Mapping Contract and Reconciliation Vectors

**Status:** Frozen on merge of the I2.1 PR. I2.2–I2.3 SHALL NOT reinterpret it.
**Governs:** [`i2-service-mapping-and-attribution.md`](i2-service-mapping-and-attribution.md) §§3–7, under the I0 [decisions](i0-semantic-decision.md) and the [I1 → I2 handoff](i1-i2-handoff.md).
**Vectors:** [`i2-vectors/`](i2-vectors/) — hand-authored, independent of any production code. `ids.json` is produced by [`vector-hashes.py`](i2-vectors/vector-hashes.py) (hashlib only). The guard expectations in `reconciliation.json` and the join key M07 were cross-checked once against `decide_service_identity` and `kafka_consumer_id`.
**Precedent:** the I1.1 contract (registration, one offline file, internal carriers) and v0.7.0 I2 (mapping artifact, reconciliation as a pure function derived in the snapshot projection with a rule id and version). `ld` is the I1 length-delimited encoding.

## 1. Source kind and registration

- `SourceKind.KAFKA_SERVICE_MAPPING = "kafka_service_mapping"`. Settings gain `kafka_service_mappings: list[...]`, empty by default.
- Registration: `id`, `root`, `artifact_relative_path` (default `kafka-service-mapping.json`), `broker_id`, `environment`.
- Several registrations for one broker and environment are allowed; each is a separate evidence authority (I2 §3). Two registrations with the same `id` are both rejected `KSM_DUPLICATE_SOURCE` (Q09).
- Discovery is by registration; `supports()` checks the schema string, never the filename.
- A dropped registration retires its carriers at request level, as I1 does.

## 2. Identities (vectors M01–M09)

| Entity | Id |
|---|---|
| `SourceInstanceId` | `urn:aip:source:kafka-service-mapping:<sha256(ld(source id, broker id, environment))>` (M01–M03) |
| Mapping entry | `kafka-service-mapping:owned:<sha256(ld(source instance id, group id))>` (M04, M05) |
| Mapping evidence | `kafka-service-mapping-evidence:owned:<sha256(ld(source instance id))>` (M06) |
| Join key | the I1 consumer id `consumer:<sha256(ld("kafka_consumer_state", broker id, environment, group id))>`, stored on each entry (M07 equals I1 K05; M08: case is exact). Joining is id equality; no `KafkaConsumerGroup` is created from a mapping. |
| Source revision | `artifact-sha256:<sha256 of the artifact bytes>` (M09 shape); the artifact has no observation time |

## 3. Artifact `aip-kafka-consumer-service-mapping/1`

Example: [`kafka-service-mapping.example.json`](i2-vectors/kafka-service-mapping.example.json).

`schema`, `broker_id`, `environment`, `mappings[] = {group_id, service_name, service_namespace?}`. All values are non-empty strings, kept exactly (no normalization). The schema is closed: an unknown field anywhere is rejected, so no member id, client id, host or credential can be carried. Duplicate `group_id` rejects the artifact. Bounds: ≤ 1 MiB, ≤ 10,000 entries, nesting ≤ 64; the path must stay inside the root.

## 4. Rejections ([`mapping-rejections.json`](i2-vectors/mapping-rejections.json))

| Code | Result | Vector |
|---|---|---|
| `KSM_UNSUPPORTED_SCHEMA` | `REJECTED_UNSUPPORTED` | Q01 |
| `KSM_BROKER_MISMATCH`, `KSM_ENVIRONMENT_MISMATCH` | `REJECTED_INVALID` | Q02, Q03 |
| `KSM_DUPLICATE_GROUP` | `REJECTED_INVALID` | Q04 |
| `KSM_ARTIFACT_INVALID` | `REJECTED_INVALID` | Q05–Q07 |
| `KSM_LIMIT_EXCEEDED` | `REJECTED_UNSUPPORTED` | Q08 |
| `KSM_DUPLICATE_SOURCE` | `REJECTED_CONFLICT` | Q09 |

Messages are fixed text; a pointer is a JSON index path, never a value or key name. A rejected artifact commits nothing and keeps the previous accepted entries. A byte-identical artifact is a no-op. A later valid artifact replaces that source's entries through the generic same-source reconciliation.

## 5. Carriers

Internal, source-owned, no relationships, outside `NODE_LABELS`:

- `KafkaServiceMappingEntry`: `id`, `source_instance_id`, `broker_id`, `environment`, `group_id`, `consumer_id` (join key), `service_name`, `service_namespace` (or null), `evidence_ids`.
- `KafkaServiceMappingEvidence`: `id`, `source_instance_id`, `configured_source_id`, `broker_id`, `environment`, `artifact_sha256`, `source_revision`.

## 6. Service resolution per entry

Each entry calls `decide_service_identity(candidates, service_name, service_namespace, aliases)`:

- **Candidates** are the Service nodes of the same snapshot that are owned by at least one declared source (non-empty `owner_source_ids`). A runtime-only stub Service is never a candidate (`reconciliation.json` `runtime_stub`).
- **Aliases** are `telemetry.service_aliases`.

| Guard result | Entry reading |
|---|---|
| `DECLARED` | resolves Service S |
| `OBSERVED_ONLY` | `SERVICE_NOT_DECLARED` (nothing minted) |
| placeholder refusal | `SERVICE_IDENTITY_PLACEHOLDER` |
| ambiguous refusal (including an alias to a non-candidate) | `SERVICE_IDENTITY_AMBIGUOUS` |
| conflicting refusal | `SERVICE_IDENTITY_CONFLICT` |

## 7. Group reconciliation (rule `kafka-consumer-attribution` / `1`)

Per join key, over every accepted entry of every mapping source (I2 §4, in this order):

1. any `SERVICE_IDENTITY_CONFLICT` → `CONFLICT` / `SERVICE_IDENTITY_CONFLICT`;
2. resolving entries name more than one Service → `CONFLICT` / `MAPPING_SOURCE_DISAGREEMENT`;
3. exactly one Service → `RESOLVED`; each non-resolving entry is listed as a limitation with its entry reason;
4. none resolves, at least one ambiguous → `AMBIGUOUS` / `SERVICE_IDENTITY_AMBIGUOUS`;
5. otherwise → `UNRESOLVED` with `SERVICE_NOT_DECLARED` or `SERVICE_IDENTITY_PLACEHOLDER`, or `NO_MAPPING` when an attachment has no entry at all.

When several entries are unresolved for different reasons, the reason is the first in the order `SERVICE_NOT_DECLARED`, `SERVICE_IDENTITY_PLACEHOLDER`, and every entry keeps its own reason in the row.

## 8. Attribution rows (one per I1 attachment)

Attachment id, consumer id, topic id, `captured_at` (T), outcome, reason, `service_id` only when `RESOLVED`, the attachment's evidence ids, the id and evidence id of every contributing mapping entry, and limitations. A mapping without an attachment produces a group row and no attribution row; nothing is ever a negative claim.

## 9. Snapshot block `kafka_consumer_attribution_v1`

Derived in the projection; only the mapping carriers are persisted. Sections, each sorted by id:

- `rule`;
- `mapping_sources`;
- `mapping_entries`;
- `aliases_applied`: only the alias entries whose key is a mapping `service_name`, so the result can be reproduced from the snapshot alone;
- `groups`;
- `attributions`.

The block is present **only when at least one mapping carrier exists**. A graph with Kafka attachments and no mapping source keeps its exact I1 bytes (L05), and removing the last mapping source removes the block (L03).

## 10. Cases and slice ownership

| I2 §7 case | Vector | Slice |
|---|---|---|
| attachment + one mapping; attachment + no mapping; mapping + no attachment | C01, C02, C03 | I2.2 (groups), I2.3 (rows) |
| OBSERVED_ONLY target; placeholder; ambiguous; conflicting | C04, C05, C06–C07, C08 | I2.2 |
| two sources same / different Service; mixed outcomes | C09, C10, C11–C13 | I2.2 |
| broker/environment mismatch; exact group id | C14, C15 | I2.2 |
| several members; one group on two Topics | C16, C17 | I2.3 |
| alias to a declared Service | C18 | I2.2 |
| attachment disappears; mapping disappears; last source removed | L01, L02, L03 | I2.3 |
| rejected update; replay; replacement | L04, L07, L08 | I2.2 |
| no mapping source; no Kafka and no mapping source | L05, L06 | I2.3 |
| artifact rejections and duplicate registrations | Q01–Q09 | I2.2 |
| identities | M01–M09 | I2.2 |
