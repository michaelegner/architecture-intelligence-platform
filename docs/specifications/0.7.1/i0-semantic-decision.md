# AIP v0.7.1 I0 — Semantic Decision Record

**Status:** Frozen on merge of the I0.2 PR.
**Governs:** the three records required by [I0 §10](i0-consumer-attribution-semantic-freeze.md). Evidence: [`i0-spike/`](i0-spike/README.md) (I0.1, #577) and the [Kafka capture](../../real-world-validation/v0.8.0/consumer-attribution-evidence/README.md).

## 1. Semantic decisions

| # | Decision | Basis |
|---|---|---|
| D1 | **Carrier.** One envelope with a source-specific native part: source kind, broker/source scope, environment, native id (verbatim, ordered parts), deterministic AIP id. Kafka native id = group id. RabbitMQ native id = vhost + queue + consumer tag + connection scope (the channel number is unique only within a connection). The envelope never merges kinds and is never a Subscription or a Service. Id = `consumer:` + sha256 of the length-delimited parts, as for `topic:owned:` and `subscription:owned:` in [`canonical-model.md`](../../canonical-model.md). | I0.1 §2 |
| D2 | **Attachment.** An edge from the consumer identity to an already-declared Topic, Queue or Subscription (ADR 0017 guards), stamped with capture time T. Kafka: live member assignment only. Members are evidence detail, not entities. Zero live consumers at T means "zero live attachment at T", never a negative about a Service. | I0 §3, §4, §8; I0.1 §1, §2 |
| D3 | **Service-mapping authority.** An accepted mapping source must be explicit, provenance-bearing, environment-compatible, and resolve to exactly one existing Service. A reviewed, operator-supplied mapping artifact is the first supported source, not the only possible authority; a deterministic deployment-resolved configuration source may qualify later under the same rule. The Service must resolve as DECLARED through `decide_service_identity`; its `OBSERVED_ONLY` (minted) outcome is rejected, so broker evidence never mints a Service. Name equality is rejected. A runtime container-IP or hostname join is corroboration only and never sufficient alone. | I0 §2; I0.1 §1 (order-service join is IP only) |
| D4 | **Time.** Attachment is "attached at T". It combines with a mapping only when the environment is identical and the mapping artifact belongs to the same snapshot generation. Answers report T and never claim "currently". No generic temporal model. | I0 §6 |
| D5 | **Reconciliation.** RESOLVED, UNRESOLVED, AMBIGUOUS, CONFLICT exactly as I0 §7. No precedence rule. Both evidence paths are retained in every outcome. | I0 §7 |
| D6 | **Lifecycle.** The owner is the broker source id. A complete accepted capture replaces that source's attachments. A failed or partial capture removes nothing. Identical replay is a no-op. An unconfigured source writes nothing. Snapshot rows are sorted by id. | I0 §9 |

## 2. Kafka evidence decision

**Reuse for semantics, fresh fixture for I1 (D7).** The v0.8 capture is accepted as semantic evidence: live assignment, group/member split, mapping separate from attachment. It is not an I1 input, because it is CLI text, its Topics are undeclared, and the order-service join is IP only. I1 builds its own replay fixture: a declared Topic, a structured (Admin-API-shaped) capture, and a mapping artifact. **Accepted mapping source for I1/I2:** the D3 operator mapping artifact (first supported source).

## 3. RabbitMQ contrast record

**SOURCE_SPECIFIC (D8)** for attachment and consumer identity: a live consumer on a Queue, no group concept, competing consumers are not several Services, fan-out lives in bindings, `consumers: 0` is zero live attachment at T. Full attribution still needs an accepted D3 mapping source, because the broker-side hints (`connection_name`, user, peer address) are client-asserted or ephemeral. No MODEL_GAP seen. v0.7.1 keeps RabbitMQ as a semantic contrast case in I4, with no adapter and no narrowing.
