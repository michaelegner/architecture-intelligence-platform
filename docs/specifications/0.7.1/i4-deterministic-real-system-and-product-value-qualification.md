# AIP v0.7.1 I4 — Qualification and Product Value

**Status:** Proposed  
**Depends on:** merged [I3](i3-i4-handoff.md), [v0.7.1 release spec](specification.md) §4/§7, and [I0 semantic decisions](i0-semantic-decision.md).

## 1. What I4 must answer

> Does broker-held consumer attachment, combined with independent Service mapping, produce a **correct and useful** answer to “which Services consume this Kafka Topic?” that repository/configuration analysis alone cannot establish?

I4 **qualifies the I3 product**, not another architecture model. Do not change I1/I2 attribution rules or the public REST/MCP contract just to make a test pass.

## 2. Deterministic qualification

Use **one exact candidate commit SHA** and independently written expected results. Execute the same frozen inputs twice from clean state (**run A and B**), through the production import path. For unchanged inputs, assert identical canonical snapshot id, sorted public answers, evidence refs and resolved evidence payloads. Record the SHA and input digests; if a fix changes production behavior or qualification inputs, rerun the affected checks on a new candidate.

Minimum coverage:

| Case | Required result |
|---|---|
| Live Kafka group attachment + reviewed mapping to a declared Service | `RESOLVED`; group, Topic, T and **both independent evidence paths** |
| Attachment without mapping; runtime-only/unknown Service | `UNRESOLVED`, no invented Service; `NO_MAPPING_SOURCE` when appropriate |
| Ambiguous/conflicting mappings | Exact frozen I2 outcome and explanation; no chosen Service |
| Accepted capture with no matching attachment or incomplete group coverage | No negative “not consuming” claim; `CAPTURE_SCOPE_LIMITED` remains visible |
| Multiple members, multiple Topics, two environments | One row per group/Topic attachment; correct destination/environment selection |
| Accepted update, authoritative removal, rejected update, identical replay | No stale attribution; rejected input preserves accepted state; deterministic replay |
| Wrong broker, unknown Topic, stale snapshot or forged evidence ref | Correct typed refusal/`NOT_RESOLVED`; no cross-snapshot evidence |
| No new Kafka source configured | Existing v0.7.0 tool *semantics* unchanged (the sixth tool still exists) |

Verify public parity on the candidate: **semantic service = REST response body = negotiated MCP `structuredContent`** for query, evidence, partial result and refusal; include a paged query. Keep the five pre-existing MCP tools' contracts unchanged and check the advertised six-tool list. Reuse existing I1–I3 tests and evaluation infrastructure; no new general-purpose framework or duplicated oracle.

## 3. Real Kafka check

Run a **controlled, reproducible Kafka instance** and capture its actual broker-held group/member assignments through the structured capture path accepted by I1. Import that capture alongside already-declared Topics/Services and a separate, operator-reviewed group → Service mapping artifact through the real I1/I2 adapters.

Prove at least one **resolved** and one **unresolved or insufficient** public answer, including same-snapshot evidence drill-down over REST and MCP. Record Kafka version, fixture/config revision, capture T, scope, source revisions, artifact hashes and the actual answer. A second accepted capture or a labelled deterministic variation should exercise update/removal.

The [October 2026 Kafka capture](../../real-world-validation/v0.8.0/consumer-attribution-evidence/README.md) establishes a **prior evidence path**, but is CLI text with an ephemeral-IP Service join. It does **not** by itself qualify the production structured-ingestion path. Name equality, container IP and member/client/host text must never become attribution authority. Explicitly distinguish real captures from derived replay variants.

## 4. RabbitMQ semantic contrast

Reuse the [I0 RabbitMQ captures and shapes](i0-spike/README.md) as an **independent semantic check**, not a second adapter.

Verify: RabbitMQ consumer identity is **connection-scoped consumer tag on a Queue**, not a Kafka consumer group; multiple consumers can compete without implying multiple Services; bindings express fan-out; `consumers: 0` means zero live attachments **at T**, not “no Service consumes”; broker-side hints are insufficient Service-mapping authority.

Record **SOURCE_SPECIFIC / MODEL_GAP** and explain any gap. Do not force RabbitMQ concepts into a Kafka group or AIP Subscription. A material unrepresentable distinction needs an explicit scope decision before I5, not a silent normalization.

## 5. Small product-value check

Use **one realistic coding-agent investigation**: an engineer is changing a Kafka-published event or Topic and wants to know which Services may be affected.

Compare the same question **without** broker evidence (repository/configuration view) and **with** the qualified I3 public answer and evidence drill-down. Record briefly:

- what the agent could and could not conclude in each case;
- whether broker evidence changed the investigation or next action;
- source setup/refresh effort, mapping effort and unresolved/ambiguous cases;
- whether that value outweighs the work needed to keep the evidence useful.

Finish with **one owner-reviewed decision: `CONTINUE | NARROW | DEFER | STOP`**, based on both semantic correctness and product usefulness. One investigation is evidence, not a general adoption claim.

## 6. Done / I5 handoff

I4 is complete when:

1. The independently expected cases and **two clean runs on one SHA** pass, with no unexplained mismatch.
2. Real Kafka ingestion produces a resolved and an unresolved/insufficient end-to-end answer, with public evidence and T.
3. RabbitMQ distinctions remain explicit; any model gap has a reviewed scope decision.
4. REST/MCP parity, evidence safety, source lifecycle and existing-tool compatibility pass.
5. The product-value check ends with an explicit decision.

Produce **one concise I4 result record** containing the candidate SHA, test/replay commands, fixture/source hashes, A/B outcome, real Kafka evidence, RabbitMQ result, significant limitations and product decision. Hand the qualified SHA and remaining release work to I5. **I5**, not I4, owns release-facing tool-count/golden re-freeze, publication and post-publication verification.
