# AIP v0.7.1 I3 — Public Destination-Consumer Answer

**Status:** Proposed  
**Depends on:** [v0.7.1 product spec](specification.md), [I0 decisions](i0-semantic-decision.md), and the completed [I2 → I3 handoff](i2-i3-handoff.md).

## 1. Product question

> For Kafka Topic D in environment E, which Services can AIP **evidence-qualify** as consumers?

I3 makes the existing I2 attribution useful to a caller. It does **not** create new consumer relationships or reinterpret broker evidence.

The answer means: *in this snapshot, mapping evidence relates Service S to group G, and broker evidence observed G attached to Topic D at time T.* It does **not** establish message processing, continuous/current consumption, or that all consumers have been found.

## 2. One exact query

Public operation: `get_destination_consumers`.

Required input:

- `destination_id`: exact existing canonical Topic id (no name/substring search);
- `broker_id`: the source-qualified Kafka broker identity;
- `environment`: exact environment.

Optional: `snapshot_id` (exact snapshot fence), `limit` (default 100, maximum 200) and opaque `cursor` for continuation. A cursor requires its original snapshot and query context. v0.7.1 supports **Kafka Topics only**; no generic cross-broker equivalence is implied.

Unknown destination or unavailable exact snapshot is an explicit `NOT_ANSWERED` refusal. The request never silently selects a different broker, environment or snapshot.

## 3. Public answer

The answer uses the existing Architecture Intelligence conventions (`outcome`, `snapshot_id`, `model_revision`, `limitations`). Its data contains:

- queried `destination_id`, `broker_id`, `environment`;
- `rows[]`, sorted by `consumer_id` then attachment id, **one row per I1 Topic attachment**;
- capture/source context sufficient to distinguish evidence at T from lack of available evidence;
- snapshot-bound evidence references and continuation, when applicable.

Each row contains:

```text
consumer_id, group_id                  # Kafka-native group identity, not a Service/Subscription
outcome                                # RESOLVED | UNRESOLVED | AMBIGUOUS | CONFLICT
service_id?                            # only when RESOLVED
reason?, limitations[]                 # unchanged I2 qualifications
captured_at                            # broker capture time T, not "now"
attachment_evidence_refs[]
mapping_evidence_refs[]                # every contributing mapping source; may be empty
```

Use `kafka_consumer_attribution_v1` as the authority for reconciliation. **Do not recompute** Service resolution, conflict precedence or mapping joins in REST/MCP.

When I1 has attachments but no mapping source (hence no I2 block), expose those attachments as `UNRESOLVED / NO_MAPPING` with broker evidence only. Mapping without attachment does **not** create a consumer row.

An empty result or an absent accepted capture is **not** "there are no consumers". State the actual limitation, including when broker evidence is unavailable or the configured capture scope does not establish completeness. An accepted capture describes only its scoped observation at T. Declared Subscriptions remain separate; do not silently merge or elevate them into broker-attributed Services.

## 4. Evidence drill-down

Each public evidence ref is opaque, deterministic and bound to the **exact snapshot and query context** (destination, broker, environment); raw internal carrier ids are not public evidence handles.

The same capability provides an `evidence` mode: require `snapshot_id`, the same query context and 1–20 refs. Resolve only refs minted by that context into bounded, sanitized provenance:

- **broker path:** accepted Kafka capture source/revision, group→Topic attachment and T;
- **mapping path:** accepted mapping source/revision and the associated Service-mapping evidence.

Unknown, forged, stale or cross-context refs are explicitly unresolved. Do not return credentials, member/client/host strings, raw capture files or arbitrary graph properties. Existing `get_evidence` semantics stay unchanged.

## 5. Service, REST and MCP

**One semantic implementation** in `ArchitectureIntelligenceService`. REST and MCP only validate/dispatch and return the same answer; semantic refusals remain typed answers, not transport-specific assertions.

| Surface | Query | Evidence |
|---|---|---|
| Service | `get_destination_consumers` | `get_destination_consumer_evidence` |
| REST | `POST /api/destination-consumers` | `POST /api/destination-consumers/evidence` |
| Negotiated MCP | `get_destination_consumers`, `mode: query` | same tool, `mode: evidence` |

**MCP decision:** a narrowly scoped **sixth tool** is warranted. None of the five existing tools accepts a broker destination as its subject; extending a Service/API/evidence tool would misrepresent its meaning. This does not change any existing tool's contract. One new tool with two modes is sufficient.

The public schema is closed, deterministic and read-only. Paging is stable within a snapshot; stale continuation is refused, never silently restarted.

## 6. Acceptance cases

Test against independently expected public results, not output generated from the new projection:

- attached group + declared Service mapping → `RESOLVED`, both evidence paths, T;
- attached group + no mapping → `UNRESOLVED / NO_MAPPING`; runtime-only/placeholder target → unresolved, no Service id;
- ambiguous, conflicting and mixed mapping sources → I2 outcome, reasons and limitations unchanged;
- mapping without attachment → no attribution; multiple members → one row per group/Topic; one group on two Topics → correctly filtered rows;
- no configured/accepted capture, empty scoped observation, or no mapping source → no invented negative or Service claim;
- environment/broker mismatch → no cross-join; removal/replacement and alias changes → snapshot-consistent results;
- deterministic order/page boundary and stale cursor; valid vs forged/cross-snapshot evidence ref;
- equivalent Service/REST/MCP payloads and no sensitive data exposure; all five existing MCP tools remain unchanged.

## 7. Done / I4 handoff

I3 is done when a caller can query one Topic, see **who is attributable, who remains unresolved, why, and what evidence supports each reading**, then drill into that evidence through REST or MCP. Capture time and limited scope must remain visible, and no positive or negative claim may exceed I1/I2 evidence.

Hand I4 the public schema, exact REST/MCP names, deterministic test fixture, example resolved and unresolved answers, and known limitations. Real-system A/B, RabbitMQ semantic contrast and product-value assessment belong to **I4**, not I3.
