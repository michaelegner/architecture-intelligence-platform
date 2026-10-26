# AIP v0.8 I2: Assessment, Projection and Tool

**Status:** Draft 0.2 (2026-10-26; review on #641: candidate enumeration, R3 before R7, optional `topic_id`, delivery limitation from the evidence chain)  
**Governs:** [v0.8 specification](specification.md) §3.2–§3.6, §4.3, §5 and §7 I2, as amended by D9–D12 (§11).  
**Baseline:** `main` at `08da0b7` (I1 complete: [completion record](i1-completion-record.md), [handoff](i1-i2-handoff.md)).  
**Hands off to:** I3 (two-broker environment and live captures).

## 1. Purpose

I2 turns I1's declared inputs and the qualified broker evidence into one answer:

> For a selected Bounded Context, which bindings cross its boundary, what does each binding's
> promise say, and what does the evidence on each broker establish?

**Primary result:** on C1, I2 gives exactly the nine rows of §8.1, with status, reason and crossing
class. Everything else in this spec supports that result.

I2 delivers:
- the promise record;
- the per-binding assessment;
- the crossing-binding projection;
- one experimental tool with a REST twin;
- the two field descriptions on `get_destination_consumers`.

**Non-goals:**
- the environment, MirrorMaker 2 and live captures (I3);
- the report and the agent (I4);
- the before/after comparison, which is report-level only (parent D6);
- any claim of cross-broker delivery or of event handling (§3).

## 2. Promise record

**Import wiring.** The `event_catalogs` registration (I1 §5.5) joins `run_all_configured_sources`
as a new source kind, following the Kafka mapping pattern:
- it is registration-bound;
- it loads through `load_event_catalog`;
- it writes internal carriers that are outside `NODE_LABELS` and have no relationship to a public
  entity.

**Carriers:**

| Carrier | Fields |
|---|---|
| `CatalogPromise` | `id`, `service_name` (catalog service id), `direction` (`SENDS` or `RECEIVES`), `event_id`, `event_version`, `file`, `environment`, `evidence_ids` |
| `CatalogMembership` | `id`, `bounded_context_id` (catalog domain id), `bounded_context_name`, `owners[]`, `service_name`, `file`, `environment`, `evidence_ids` |
| `CatalogEventTopic` | `id`, `event_id`, `topic`, `repository`, `commit`, `path`, `environment`, `evidence_ids` |
| `CatalogEvidence` | `id`, `source_instance_id`, `configured_source_id`, `environment`, `catalog_digest`, `lookup_digest`, `source_revision` |

**Ids.** Every id is `<carrier prefix>:owned:<sha256(ld(source instance id, natural key))>`, using
the I1 length-delimited encoding. The natural keys are:
- promise: service, direction, event id;
- membership: bounded context id, service;
- event topic: event id.

The implementation writes known-answer vectors before the code (`i2-vectors/`).

**Rules:**
- Promises are environment-scoped, never broker-scoped (parent §3.2). The loader output is the only
  input. A promise is never written as Current State, and Current State never writes a promise
  (doctrine §4.3).
- Each catalog entry counts as a confirmed promise by the disclosed demonstration assumption
  (parent §2).

**Lifecycle:**
- A replay of the same catalog and lookup bytes is a no-op.
- A later accepted catalog replaces this source's carriers through the generic same-source
  reconciliation.
- A rejected catalog commits nothing and keeps the prior state.
- Dropping the registration retires the carriers.

**Effective revision (D12).** The revision is
`catalog-sha256:<catalog digest>+lookup-sha256:<lookup digest>`, where the lookup digest is SHA-256
over the exact bytes of the lookup file. The source's semantic input digest covers both, so a
lookup-only change is a content change, not a replay no-op. This amends I1 §5.5.

**Loader rules.** The seven loader rules in the I1 completion record ("Specification questions
discovered") are adopted as normative.

## 3. Three separate claims

I2 keeps these claims apart. No field and no wording joins them:

| Claim | Established by | In the answer |
|---|---|---|
| **Crossing classification**: the binding crosses the selected Bounded Context | declared producers (`PUBLISHES_TO`) and catalog Bounded Context membership, under D9 (§5) | `crossing` |
| **Observed attachment**: a consumer group of this Service is attached to this Topic on this broker at T | the accepted capture plus the attribution of the mapping (v0.7.1) | `status`, `captured_at`, evidence refs |
| **Cross-broker delivery**: records written on one broker reach another | **not established by AIP**. MirrorMaker 2 is not ingested. The report uses MM2 configuration and runtime checks (parent §4.4) | never; the limitation `CROSS_BROKER_DELIVERY_NOT_ESTABLISHED` |

An attachment never proves that an event type was handled (parent §3.4). The producer side is
declared evidence only.

## 4. Assessment

**Unit:** one row per consumer Service × Topic × broker, in the environment of the request.

**Candidates.** The rows come from the union of two inputs, for each broker B in the request that
has an accepted complete capture:
- **promise candidates:** each `RECEIVES` promise of Service S for event E, resolved along the
  chain below;
- **attachment candidates:** each live attachment on B (the v0.7.1 attribution rows of that
  capture), whether or not a promise exists. R4 and R6 rows come from these.

A promise candidate and an attachment candidate for the same S × Topic × B are one row.

**Resolution chain** (parent §3.4), for a promise candidate:
1. **Scope first.** If B has no accepted complete capture, or S is not in scope on B (below), the
   candidate gives no row (R3). The remaining steps do not run, so a missing Topic never creates an
   assessed row on an unobserved broker.
2. Look up E's topic in the lookup.
3. Find the inventory Topic id of that topic on B (I1 §6). If none exists, the row is R7.
4. Resolve S to a declared Service with `decide_service_identity`, using the same candidate rule as
   the v0.7.1 mapping guard. If that fails, the row is `UNRESOLVED` / the guard's reason.
5. Match the attachment on B: the v0.7.1 attribution row for that Topic whose `service_id` is S.

**Capture scope.** S is in scope on B when an accepted complete capture of B allow-lists a group
whose accepted mapping entry for B resolves to S (v0.7.1 I2 §6, per entry). Scope uses the mapping
entries, not the attribution rows, because a group with no live attachment (`Empty`, `Dead`) has no
attribution row.

**Status rule.** The closed status enum is D10. The rules apply in this order; R3 comes before R7.

| # | Promise (`RECEIVES`, resolved to this topic) | Evidence on B | Row |
|---|---|---|---|
| R3 | yes | no accepted complete capture of B, or S not in scope on B | no row |
| R7 | yes | S in scope; the inventory has no Topic for that topic on B | `UNRESOLVED` / `TOPIC_NOT_DECLARED`, with no `topic_id` (§6) |
| R1 | yes | live attachment, attribution `RESOLVED` to S | `PROMISED_AND_OBSERVED` |
| R2 | yes | S in scope; its group has no live attachment to this Topic (`Empty`, broker-reported `Dead`, or `Stable` without this Topic) | `PROMISED_NOT_OBSERVED` |
| R4 | no | live attachment, attribution `RESOLVED` to S | `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` ("observed, undeclared") |
| R5 | no | no live attachment | no row |
| R6 | any | live attachment whose attribution is not `RESOLVED` | `UNRESOLVED` / the attribution reason (`NO_MAPPING`, `SERVICE_NOT_DECLARED`, …). The row names the group, not a Service, and its crossing is `UNRESOLVED` |

**Notes:**
- `PROMISED_NOT_OBSERVED` needs an accepted complete capture of B. An absent, rejected or
  incomplete capture never yields it (R3). An incomplete capture is rejected at import
  (`KAFKA_CAPTURE_INCOMPLETE`, v0.7.1 I1 §4) and keeps the prior state.
- The v0.8 rules never emit `CONTRADICTED` (there is no closed-world rule) or
  `OBSERVED_NOT_PROMISED` (there is no promise coverage, parent §3.2).
- A binding that had a live attachment before the wave and has none after it, with no promise, is
  R5 (no row). Parent §3.6's "no live attachment here" is the report's comparison of two snapshots,
  never a sixth status.

**Per row:**
- `declared_event_types`: the event ids of S's `RECEIVES` promises that resolve to this topic.
  The list is empty for R4 and R6, and it is labelled declared-only.
- `producers[]`: the declared producers of the topic (§5), each with its Bounded Context and the
  event ids of its `SENDS` promises for this topic.

## 5. Crossing classification (D9)

**Producers** of a topic are the declared Services with `PUBLISHES_TO` to a Topic of that **name**
on any broker of the request's environment. Topic ids are never merged; the name only selects
producers.

**Bounded Context** of a Service: its catalog membership. In the catalog, a Service is in exactly
one domain (I1 §5.1).

For the selected Bounded Context X, consumer context c and producer contexts P:

| Condition | `crossing` |
|---|---|
| c = X, and P contains a context ≠ X | `INBOUND` |
| c = X, and P = {X} | `INSIDE` |
| c ≠ X, and X ∈ P | `OUTBOUND` |
| c ≠ X, and X ∉ P | `NONE` |
| no declared producer, a producer without membership, a consumer without membership, or an R6 row | `UNRESOLVED` |

## 6. Projection and answer

**Query.**
- Required: `bounded_context_id` (the catalog domain id, e.g. `catalog-management`) and
  `environment`.
- Optional:
  - `broker_ids` (1–8 declared broker ids; the default is every broker with an accepted capture
    in the environment);
  - `snapshot_id`;
  - `limit` (default 100, maximum 200) and `cursor`, as in v0.7.1.

**Envelope.** The v0.7.1 conventions apply: `outcome`, `snapshot`, `model_revision`, `limitations`.
`data` holds:
- the exact request context;
- `catalog_source` (source instance id, catalog digest, lookup digest, revision);
- `capture_sources[]`, one per accepted capture in scope, each with its own `broker_id`,
  `captured_at` and `source_revision`;
- the sorted `rows[]`.

Several captures are never collapsed into one T.

**Row:**

```text
broker_id, topic_name                     # the topic name; for R7 the only topic field
topic_id?                                 # broker-scoped Topic id; never merged; absent only for R7
consumer_service_id?                      # absent for R6
group_id?                                 # the attributed group (R1, R4, R6)
crossing                                  # INBOUND | INSIDE | OUTBOUND | NONE | UNRESOLVED
status, reason?                           # D10 enum + reason
declared_event_types[]                    # declared only
producers[]                               # {service_id, bounded_context_id, broker_ids[], declared_event_types[]}
cross_broker_producers                    # true when a producer used for `crossing` publishes on no Topic of this row's broker
captured_at?                              # T of the capture of this broker (R1, R2, R4, R6)
promise_evidence_refs[], attachment_evidence_refs[], mapping_evidence_refs[]
```

Rows are sorted by `broker_id`, `topic_name`, `consumer_service_id` (or `group_id`).

**Top-level codes:**

| Code | Kind | When |
|---|---|---|
| `UNKNOWN_BOUNDED_CONTEXT`, `NO_ACCEPTED_CATALOG` | refusal, `NOT_ANSWERED` | no such catalog domain, or no accepted catalog in the environment |
| `NO_ACCEPTED_CAPTURE` | refusal if no requested broker has a capture; otherwise a limitation that names the broker | a requested broker has no accepted capture |
| `SNAPSHOT_NOT_AVAILABLE`, `CURSOR_QUERY_MISMATCH` | refusal | as v0.7.1 |
| `CAPTURE_SCOPE_LIMITED` | limitation, always present | captures cover their allow-lists at their T only |
| `PROMISES_ASSUMED_CONFIRMED` | limitation, always present | parent §2 disclosure |
| `PRODUCER_SIDE_DECLARED_ONLY`, `EVENT_HANDLING_NOT_ESTABLISHED` | limitation, always present | §3 |
| `CROSS_BROKER_DELIVERY_NOT_ESTABLISHED` | limitation, present when any row has `cross_broker_producers: true`, whatever brokers were requested | §3 |
| `MORE_ROWS_AVAILABLE`, `EVIDENCE_REF_NOT_RESOLVED` | limitation | as v0.7.1 |

**Evidence mode.** As v0.7.1 I3 §4: opaque refs bound to the snapshot and the query context, 1–20
per call. The promise path resolves to the catalog file, catalog digest and lookup entry. The broker
and mapping paths are unchanged. No member id, client id or host is ever returned.

## 7. Tool and surfaces (D11)

| Surface | Query | Evidence |
|---|---|---|
| Service | `get_binding_picture` | `get_binding_picture_evidence` |
| REST | `POST /api/binding-picture` | `POST /api/binding-picture/evidence` |
| MCP | `get_binding_picture`, `mode: query` | same tool, `mode: evidence` |

- **One semantic implementation** in `ArchitectureIntelligenceService`. REST and MCP only validate
  and dispatch.
- The schema is closed and frozen in `schemas/`. Every field has a description that names the
  identifier it expects, for example "catalog domain id, such as `catalog-management`" or
  "declared broker id (`x-aip-broker-id`), not a bootstrap address".
- **Flag.** A new setting, `experimental.binding_picture` (default `false`), controls the tool:
  - The MCP tool and the REST routes exist only when it is `true`.
  - With `false`, `tools/list` and every existing answer are byte-identical to `08da0b7`, apart from
    the next item.
  - The hosted profile (mcp.daip.io) and the showcase profile set it to `true`.
- **Field descriptions** on `get_destination_consumers`:
  - `destination_id`: "Exact canonical Kafka Topic id (`topic:owned:…`), not a topic name."
  - `broker_id`: "Declared broker id (`x-aip-broker-id`, e.g. `kafka:cluster-a`), not a bootstrap
    address."

  These two strings are the only change to the six existing tools. Their schema and the golden
  files change for exactly these strings.

## 8. Expected answers

### 8.1 C1 (primary acceptance)

**Request:** `bounded_context_id = catalog-management`, `environment = local`,
`broker_ids = [kafka:sokol111-local]`.
**Inputs:** the I1 package: the Redpanda declarations, the Redpanda mapping, C1 and the catalog.

| Consumer Service × Topic | Crossing | Status / reason | Rule |
|---|---|---|---|
| `ecommerce-product-query-service` × `catalog.product.events` | `OUTBOUND` | `PROMISED_AND_OBSERVED` | R1 |
| `ecommerce-image-service` × `catalog.product.events` | `INSIDE` | `PROMISED_AND_OBSERVED` | R1 |
| `ecommerce-catalog-service` × `tenant.tenant.events` | `INBOUND` | `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | R4 |
| `ecommerce-image-service` × `tenant.tenant.events` | `INBOUND` | `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | R4 |
| `ecommerce-category-query-service` × `catalog.category.events` | `OUTBOUND` | `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | R4 |
| `ecommerce-product-query-service` × `catalog.attribute.events` | `OUTBOUND` | `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | R4 |
| `ecommerce-category-query-service` × `catalog.attribute.events` | `OUTBOUND` | `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | R4 |
| `ecommerce-product-query-service` × `tenant.tenant.events` | `NONE` | `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | R4 |
| `ecommerce-category-query-service` × `tenant.tenant.events` | `NONE` | `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | R4 |

The answer has exactly these nine rows. Its limitations are `CAPTURE_SCOPE_LIMITED`,
`PROMISES_ASSUMED_CONFIRMED`, `PRODUCER_SIDE_DECLARED_ONLY` and `EVENT_HANDLING_NOT_ESTABLISHED`.

**Derivation:**
- **Producers (I1 §4.3):**
  - `tenant.tenant.events`: Tenant (`store-provisioning`);
  - `catalog.product.events`: Catalog and Image (`catalog-management`);
  - `catalog.category.events` and `catalog.attribute.events`: Catalog.
- **Promises:** Image and Product Query receive `ProductUpdated`, and Product Query also receives
  `ProductImagePromoted`. Both events map to `catalog.product.events`.

### 8.2 Two-broker fixture (parent §3.6 and §4.3)

The fixture is hand-authored in `i2-vectors/` before any implementation (I2b):
- after-wave declarations (I1 §4.1 rules: Catalog and Image `publish` on Kafka; the `catalog.*`
  topics topic-only on Redpanda; `tenant.tenant.events` topic-only on Kafka);
- a Redpanda capture with the same allow-list as C1: Catalog `Empty`, Image broker-reported `Dead`,
  Product Query and Category Query as in C1;
- a Kafka capture with the allow-list {Catalog, Image}: Catalog on `tenant.tenant.events`, Image on
  `tenant.tenant.events` and `catalog.product.events`;
- both mappings of I1 §7.

**Request:** `catalog-management`, `local`, both brokers.

| Consumer × Topic | Redpanda | Kafka |
|---|---|---|
| Image × `catalog.product.events` | `INSIDE`, `PROMISED_NOT_OBSERVED` (R2) | `INSIDE`, `PROMISED_AND_OBSERVED` (R1) |
| Product Query × `catalog.product.events` | `OUTBOUND`, `PROMISED_AND_OBSERVED` (R1) | no row: outside scope (R3) |
| Catalog × `tenant.tenant.events` | no row (R5) | `INBOUND`, `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` (R4) |
| Image × `tenant.tenant.events` | no row (R5) | `INBOUND`, `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` (R4) |
| Category Query × `catalog.category.events` | `OUTBOUND`, `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | no row |
| Product Query × `catalog.attribute.events` | `OUTBOUND`, `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | no row |
| Category Query × `catalog.attribute.events` | `OUTBOUND`, `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | no row |
| Product Query × `tenant.tenant.events` | `NONE`, `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | no row |
| Category Query × `tenant.tenant.events` | `NONE`, `UNRESOLVED` / `PROMISE_COVERAGE_MISSING` | no row |

- The Redpanda Product Query row stays `OUTBOUND` after the wave because the producers of
  `catalog.product.events` (now on Kafka) are in `catalog-management` (D9). The row says nothing
  about delivery: it has `cross_broker_producers: true`, and `CROSS_BROKER_DELIVERY_NOT_ESTABLISHED` is
  present. A request for Redpanda alone gives the same row and the same limitation.
- The same topic name on the two brokers gives two Topic ids, and the rows never merge them.

**Fixture variants:**
- A Redpanda capture with `complete: false` is rejected at import. The prior state stays, and no
  `PROMISED_NOT_OBSERVED` comes from it.
- **R7:** the Kafka inventory without `catalog.product.events`, with the same Kafka capture, gives
  the Image row on Kafka as `UNRESOLVED` / `TOPIC_NOT_DECLARED` with no `topic_id`. The same change
  with no accepted Kafka capture gives no Kafka row (R3 before R7).
- A request for both brokers when only Redpanda has an accepted capture gives the Redpanda rows and
  the limitation `NO_ACCEPTED_CAPTURE` for Kafka.

## 9. Acceptance

| # | Check | Tier |
|---|---|---|
| **B1** | **C1 gives exactly the nine rows of §8.1** (status, reason, crossing) and the listed limitations, through the production import of the I1 package plus the catalog | qualification |
| B2 | The two-broker fixture gives exactly the §8.2 table and its variants | integration |
| B3 | Parent §4.3: separate Topic ids per broker; `Empty` and `Dead` as zero live attachment; an incomplete capture rejected; no merged Topics | integration (with B2) |
| B4 | `CONTRADICTED` and `OBSERVED_NOT_PROMISED` are never emitted. R5 gives no row. R6 names no Service and has crossing `UNRESOLVED` | unit |
| B5 | Promise-record lifecycle: replay no-op, replacement, rejection keeps state, retirement. The ids equal `i2-vectors/` | unit + integration |
| B6 | D12: changing one lookup mapping changes the effective revision and the semantic input digest, and the persisted promise chain is re-evaluated (a row changes topic) | integration |
| B7 | Flag `false`: `tools/list` and all six tools' answers are byte-identical, apart from the B8 strings. Flag `true`: seven tools, over the real negotiated MCP transport, with the advertised schema validating every answer | integration |
| B8 | `get_destination_consumers` differs only by the two descriptions | unit (schema) |
| B9 | Evidence mode: minted refs resolve, forged and cross-context refs do not, and no member text is returned | integration |
| B10 | No field states delivery. `CROSS_BROKER_DELIVERY_NOT_ESTABLISHED` is present exactly when a row has `cross_broker_producers: true`, including a single-broker request | unit |

**Stop rule** (parent §7): if a check cannot pass as specified, record the attempt and ask.

## 10. Delivery

| PR | Content | Acceptance |
|---|---|---|
| I2a | Promise record: carriers, ids and vectors, import wiring, lifecycle, D12 | B5, B6 |
| I2b | Assessment and projection in the service; the C1 and two-broker expected answers (fixture first) | B1–B4, B10 |
| I2c | Tool, REST, schema, flag, field descriptions, evidence mode | B7–B9 |

## 11. Decisions

| # | Decision | Source |
|---|---|---|
| D9 | Crossing classification uses declared producers by topic **name** across the environment's brokers and catalog membership (§5). It is separate from observed attachment and from cross-broker delivery, which AIP does not establish (§3) | owner, 2026-10-26 |
| D10 | Statuses are the closed doctrine enum of five plus a reason; "observed, undeclared" is `UNRESOLVED` / `PROMISE_COVERAGE_MISSING`; `CONTRADICTED` and `OBSERVED_NOT_PROMISED` are not emitted in v0.8 | owner, 2026-10-26 |
| D11 | The tool exists only with `experimental.binding_picture: true`. The default `tools/list` stays six; the hosted and showcase profiles enable it | owner, 2026-10-26 |
| D12 | The EventCatalog revision covers the exact lookup bytes: `catalog-sha256:<catalog digest>+lookup-sha256:<lookup digest>`. Amends I1 §5.5 | owner review on #640, 2026-10-26 |

## 12. Handoff to I3

I3 needs from I2:
- the projection (§6) with `broker_ids` for both brokers;
- the after-wave declaration rules (I1 §4.1), which the §8.2 fixture already exercises;
- the Kafka capture registration for `kafka:sokol111-kafka` with the allow-list {Catalog, Image} and
  the I1 §7 mapping.

I3 reproduces §8.2 from live captures (parent §3.6).
