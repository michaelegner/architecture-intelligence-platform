# AIP v0.7.1 I3 — Public Destination-Consumer Answer

**Status:** Proposed  
**Depends on:** [v0.7.1 product spec](specification.md), [I0 decisions](i0-semantic-decision.md), and the completed [I2 → I3 handoff](i2-i3-handoff.md).

## 1. Product question

> For Kafka Topic D in environment E, which Services can AIP **evidence-qualify** as consumers?

I3 makes I2 attribution useful to a caller. It does **not** create new consumer relationships or reinterpret broker evidence.

A resolved row means: *in this snapshot, mapping evidence relates Service S to group G, and broker evidence observed G attached to Topic D at time T.* It does **not** prove message processing, continuing/current consumption, or that all consumers have been found.

## 2. One exact query

Public operation: `get_destination_consumers`.

Required input:

- `destination_id`: exact canonical Kafka Topic id (no name/substring search);
- `broker_id`: source-qualified Kafka broker identity used to derive the Topic id;
- `environment`: exact environment.

Optional: `snapshot_id` (exact snapshot fence), `limit` (default 100, maximum 200), and an opaque `cursor`. Continuation requires the original snapshot and query context.

**Scoping:**

- The Topic id contains broker identity but **no environment**. Verify the Topic is declared, is Kafka, and belongs to the requested broker (using canonical Topic identity/ownership, not name resemblance). Unknown destination, non-Kafka destination, or broker mismatch is an explicit `NOT_ANSWERED` refusal.
- Filter attachments by `broker_id` and `environment` on their I1 consumer group / Kafka capture evidence, **not** on the Topic. Mapping entries are already broker/environment-qualified by I2. A Topic used in two environments yields only rows for E.
- A known Topic with **no accepted capture for that broker/environment** returns `NOT_ANSWERED / NO_ACCEPTED_CAPTURE`, not an empty authoritative consumer list. A stale/unavailable `snapshot_id` is `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE`. Never silently substitute a different context.

v0.7.1 is **Kafka Topic only**, not a cross-broker topology query.

## 3. Public answer

Use the existing Architecture Intelligence envelope conventions (`outcome`, `snapshot_id`, `model_revision`, `limitations`). Data contains the exact request context, sorted `rows[]`, and `capture_sources[]`: **each accepted I1 source in the requested broker/environment**, with its own `source_instance_id`, `captured_at`, `source_revision` and scope digest. Never collapse multiple captures into one invented T.

One row **per I1 attachment on the queried Topic**, sorted by `consumer_id` then attachment id:

```text
consumer_id, group_id                  # Kafka-native group; not Service/Subscription
outcome                                # RESOLVED | UNRESOLVED | AMBIGUOUS | CONFLICT
service_id?                            # RESOLVED only
reason?, limitations[]                 # I2 reasons/limitations, unchanged
captured_at                            # attachment capture time T, not "now"
attachment_evidence_refs[]
mapping_evidence_refs[]                # every contributing mapping source; may be empty
```

When `kafka_consumer_attribution_v1` exists, use its rows **without re-running reconciliation**. If I1 has attachments but no I2 block (no mapping carrier), call the **existing pure I2 `attribution_block`** with empty mapping sources/entries and the same-snapshot I1 rows; filter the derived rows as usual. This yields `UNRESOLVED / NO_MAPPING` through **the same I2 rule**, not a second public implementation. Nothing is persisted. A mapping alone never creates an attribution row.

**Closed top-level limitation/refusal codes (distinct from I2 row reasons):**

| Code | Meaning |
|---|---|
| `UNKNOWN_DESTINATION`, `DESTINATION_NOT_KAFKA_TOPIC`, `BROKER_MISMATCH` | Refuse invalid exact destination/broker selection (`NOT_ANSWERED`) |
| `SNAPSHOT_NOT_AVAILABLE`, `CURSOR_QUERY_MISMATCH` | Refuse stale snapshot or invalid continuation context |
| `NO_ACCEPTED_CAPTURE` | No accepted I1 capture for broker/E; `NOT_ANSWERED`, even if mapping exists |
| `CAPTURE_SCOPE_LIMITED` | **Always** expose for accepted captures: they cover configured group allow-lists at their respective T, never all possible groups |
| `NO_MAPPING_SOURCE` | No accepted mapping source for broker/E; distinguish this from a present mapping source with no entry for G (row reason `NO_MAPPING` in both cases) |
| `MORE_ROWS_AVAILABLE`, `EVIDENCE_REF_NOT_RESOLVED` | Pagination or evidence-mode limitation |

A capture with no matching attachment may yield `rows: []`, **with `CAPTURE_SCOPE_LIMITED`**, never a negative assertion. Multiple accepted capture sources keep their separate scopes and timestamps. No inferred Service, no "not consuming" and no global completeness claim.

**Declared Subscriptions are excluded from this answer.** They remain independently queryable architecture declarations; do not combine them with Kafka group evidence or count them as observed consumers.

## 4. Evidence drill-down

Each public evidence ref is opaque, deterministic and bound to the **exact snapshot and query context** (destination, broker, environment); raw internal carrier ids are not public evidence handles.

The same capability provides an `evidence` mode: require `snapshot_id`, the same query context and 1–20 refs. Resolve only refs minted by that context to bounded, sanitized provenance:

- **broker path:** accepted Kafka capture source/revision, group→Topic attachment and T;
- **mapping path:** accepted mapping source/revision and associated Service-mapping evidence.

Unknown, forged, stale or cross-context refs are explicitly unresolved. Do not expose credentials, member/client/host strings, raw capture files or arbitrary graph properties. Existing `get_evidence` semantics stay unchanged.

## 5. Service, REST and MCP

**One semantic implementation** in `ArchitectureIntelligenceService`. REST and MCP only validate/dispatch and return the same answer; semantic refusals remain typed answers.

| Surface | Query | Evidence |
|---|---|---|
| Service | `get_destination_consumers` | `get_destination_consumer_evidence` |
| REST | `POST /api/destination-consumers` | `POST /api/destination-consumers/evidence` |
| Negotiated MCP | `get_destination_consumers`, `mode: query` | same tool, `mode: evidence` |

**MCP decision:** a narrowly scoped **sixth tool** is warranted. None of the five existing tools takes a broker destination as its subject; extending a Service/API/evidence tool would change its meaning. One new tool with two modes is sufficient.

The public schema is closed, deterministic and read-only. Paging is stable within one snapshot; changed query context/stale continuation is refused rather than silently restarted.

## 6. Acceptance cases

Author expected public outputs independently of the new projection:

- attachment + declared mapping → `RESOLVED`, both evidence paths and T; no mapping source → same I2 `NO_MAPPING` rule **plus** `NO_MAPPING_SOURCE`; source present but group unmapped → `NO_MAPPING` without `NO_MAPPING_SOURCE`;
- runtime-only/placeholder, ambiguous, conflicting and mixed mapping sources → exact I2 outcomes and limitations, without invented Service ids;
- mapping without attachment → no attribution; multiple members → one group/Topic row; one group on two Topics → only requested Topic; **same Topic in two environments → only E's attachments**;
- known Kafka Topic without accepted capture for E → `NO_ACCEPTED_CAPTURE`; accepted empty/limited capture → no negative claim, each capture's own T and `CAPTURE_SCOPE_LIMITED`;
- wrong broker, non-Kafka Topic and unknown destination → typed refusals; declared Subscriptions excluded;
- removal/replacement and alias changes → same-snapshot results; deterministic ordering/paging and stale cursor; valid vs forged/cross-snapshot evidence refs;
- equivalent Service/REST/MCP payloads, no sensitive exposure, and unchanged existing MCP tools.

## 7. Done / I4 handoff

I3 is done when a caller can query a Topic, see **who is attributable, who remains unresolved, why, and which evidence supports each reading**, then drill down through REST or MCP. Time and limited scope must remain visible; no positive or negative claim may exceed I1/I2 evidence.

Hand I4 the public schema, REST/MCP names, deterministic fixture, resolved/unresolved example answers, and limitations. Include the new sixth tool in MCP documentation, plugin docs, tool-list/golden tests, and release/pilot compatibility checks; do **not** rewrite older historical records merely to change their original tool count. Real-system A/B, RabbitMQ contrast and product-value assessment belong to **I4**, not I3.
