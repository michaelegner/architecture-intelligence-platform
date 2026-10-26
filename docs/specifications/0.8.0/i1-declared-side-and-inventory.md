# AIP v0.8 I1 — Declared Side and Inventory

**Status:** Draft 0.2 (2026-10-26; §5.5 revision and pipeline amended by I2 D12)  
**Governs:** [v0.8 specification](specification.md) §3.1–§3.3 and §7 I1, as amended by D7 and D8 (§10).  
**Baseline:** `main` at `00bd120`.  
**Hands off to:** I2 (promise record, assessment, projection, tool).

## 1. Purpose

I1 supplies every declared input that I2 needs to reproduce §3.5 of the parent specification:

- the generated EventCatalog (the promises);
- the event → Topic lookup;
- the declared Services, producers and Topic inventory for both brokers;
- the extended group → Service mappings;
- the EventCatalog loader.

I1 makes no assessment and adds no tool. The field descriptions on `get_destination_consumers`
belong to I2.

## 2. Risk resolution (parent §7 I1)

**Question:** does the AsyncAPI adapter accept a topic-only declaration (a channel without service
operations)?

**Answer: no.** A probe on `00bd120` gave these results:

| Document | Result |
|---|---|
| One qualified Topic channel, no operation | `REJECTED_UNSUPPORTED`, no diagnostic, no Topic |
| One channel with `publish`, one bare qualified Topic channel | `ACCEPTED`, both Topics emitted (accidental: the bare channel rides on the other channel's operation) |
| No `x-aip-service-id` | `REJECTED_UNSUPPORTED`, `SERVICE_IDENTITY_UNRESOLVED` |
| `x-aip-service-id`, empty `channels` | `ACCEPTED`, one Service |

**Cause:** `_AsyncApiMapping.finish()` (`app/ingestion/asyncapi_adapter.py:1249`) rejects a
document with channels when no operation set `any_channel_supported`. A resolved Topic alone never
sets it.

**Second gap:** no I1 input declared a producer for `catalog.attribute.events`. The catalog does not
name attribute events, and the capture establishes no producers. Without a producer, I2 cannot
decide that the attribute rows of §3.5 cross Catalog Management.

**Third gap:** Category Query was not a declared Service. The mapping guard resolves only to
Services that a declared source owns ([v0.7.1 I2 contract §6](../0.7.1/i2-kafka-service-mapping-contract.md)),
so its entry would read `SERVICE_NOT_DECLARED`.

The owner decided all three on 2026-10-26 (D7, D8).

## 3. AsyncAPI change: qualified Topic without operations (D7)

**Rule.** A channel that resolves to a qualified Topic (positive Topic-kind evidence and a qualified
identity, [v0.5.0 I4 §7.1/§8.1](../0.5.0/i4-source-independent-pubsub-semantics.md)) counts as a
supported channel, even with no `publish` or `subscribe` operation.

**Output for such a channel:**

- one `Topic` and one `TOPIC` `PubSubDeclaration`, exactly as today;
- no relation, no `Broker` and no `USES_BROKER`: a Topic declaration is not evidence that the
  document's Service uses the broker.

**Unchanged:**

- A Queue channel without operations stays unsupported.
- A channel without Topic evidence, or with an ambiguous or missing identity, is still omitted with
  its existing diagnostic.
- A document whose channels all fail this way is still `REJECTED_UNSUPPORTED`.
- The root `x-aip-service-id` is still required.
- All output for documents that the adapter accepts today is byte-identical.

**Version.** `AsyncApiSourceAdapter.mapping_rule_version` stays `v2`. A bump is not needed and would
break the byte-identical rule:

- Only documents that are rejected today change outcome. A rejected source commits nothing, so its
  next load is a first successful load (`app/sources/replay.py`), not a replay no-op.
- A document that is accepted today maps to the same output, including a bare Topic channel next to
  an operation (§2).
- The version is an input of `source_revision_id` (`app/sources/identity.py`). A bump would change
  the revision id of every imported AsyncAPI source.

**Status.** This is an ingestion change, not experimental promise semantics. It stays after v0.8.
`docs/ingestion.md` is updated in the same PR.

## 4. Declared Current State (D7, D8)

### 4.1 Rules

1. **Services.** Each of the five deployed Go services has one AsyncAPI document for each broker on
   which it declares a channel, or one service-only document if it declares no channel. `x-aip-service-id`
   is `service:<deployment name>`, for example `service:ecommerce-catalog-service`.
2. **Producers.** A Service declares `publish` on a Topic only when the Service's own
   `*-service-api` maps one of its event types to that topic in `pkg/events/topics.go`, and only on the
   broker that the Service writes to in the topology. The `publish` operation carries no message
   contract beyond the event type names; the upstream contract is protobuf.
3. **Topic-only channels.** A topic whose writer on a broker is not a Service (in the wave: a
   MirrorMaker 2 flow) is declared there as a Topic channel without operations. It goes in the
   document of the Service whose `*-service-api` defines the topic.
4. **No subscribe operations.** No declaration names a consumer. Consumers come only from the capture
   and the mapping. The v0.7.2 subscribe overlays are not reused.
5. **One broker per document.** Each document has one server with `x-aip-broker-id`. A channel name is
   unique in a document, so a Service with channels on two brokers has two documents. Both documents
   have the same `x-aip-service-id`, `info.title` and `info.version`.

### 4.2 Producer sources (verified 2026-10-26)

| `*-service-api` (commit, [freeze](../0.7.2/i2-evidence/sokol111/freeze.md)) | Event types → topic |
|---|---|
| `ecommerce-tenant-service-api` `d9b9097` | `TenantUpdatedEvent`, `TenantDeletedEvent` → `tenant.tenant.events` |
| `ecommerce-catalog-service-api` `7cecb3e` | `ProductUpdatedEvent`, `ProductDeletedEvent` → `catalog.product.events`; `CategoryUpdatedEvent` → `catalog.category.events`; `AttributeUpdatedEvent` → `catalog.attribute.events` |
| `ecommerce-image-service-api` `2167948` | `ProductImagePromotedEvent` → `catalog.product.events` |

Each document's `info.description` names the repository, commit and file it was authored from.

### 4.3 Declaration set before the wave (I1)

Redpanda, `kafka:sokol111-local`:

| Service | Channels |
|---|---|
| `ecommerce-tenant-service` | `tenant.tenant.events` (`publish`) |
| `ecommerce-catalog-service` | `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events` (all `publish`) |
| `ecommerce-image-service` | `catalog.product.events` (`publish`) |
| `ecommerce-product-query-service` | none (service-only) |
| `ecommerce-category-query-service` | none (service-only) |

Apache Kafka, `kafka:sokol111-kafka` (the inventory of the target broker; no Service writes to it
before the wave):

| Service | Channels |
|---|---|
| `ecommerce-tenant-service` | `tenant.tenant.events` (no operation) |
| `ecommerce-catalog-service` | the three `catalog.*` topics (no operation) |

The Kafka set is a separate directory source. The C1 replay does not register it, because no Kafka
broker exists at C1. I1 only checks that it loads and that its Topic ids match §6.

The declaration set after the wave follows the same rules: Catalog and Image `publish` on Kafka, the
`catalog.*` channels on Redpanda become topic-only, and `tenant.tenant.events` stays topic-only on
Kafka. I3 authors it (§9).

## 5. EventCatalog

### 5.1 Supported subset

AIP reads a closed subset of the EventCatalog file layout
([service frontmatter](https://eventcatalog.dev/docs/api/service-api)). The generated catalog uses
nothing else:

| Path | Fields read |
|---|---|
| `domains/<id>/index.mdx` | `id`, `name`, `version`, `owners[]`, `services[] = {id}` |
| `services/<id>/index.mdx` | `id`, `name`, `version`, `sends[] = {id, version}`, `receives[] = {id, version}` |
| `events/<id>/index.mdx` | `id`, `name`, `version`, `summary` |
| `teams/<id>.mdx` | `id`, `name` |

- The frontmatter is YAML between the first two `---` lines. The body is ignored.
- Every entry has `version: 1.0.0`. A `sends` or `receives` reference without `version`, or with a
  `version` that does not match the referenced event, is rejected. Domain `services[]` and `owners[]`
  reference by `id` only.
- A service listed in no domain, or in more than one domain, is rejected.
- A reference to an unknown event, service or team is rejected.
- An unknown file, or an unknown field on a read entry, is rejected. A non-generated catalog is out
  of scope for v0.8.

### 5.2 Generated content (parent §3.1)

| Domain (`id`) | Owner (`teams/<id>`) | Services |
|---|---|---|
| `store-provisioning` | `provisioning-team` | `ecommerce-tenant-service` |
| `catalog-management` | `catalog-team` | `ecommerce-catalog-service`, `ecommerce-image-service` |
| `storefront` | `storefront-team` | `ecommerce-product-query-service`, `ecommerce-category-query-service` |

Events: `TenantUpdated`, `ProductEvents`, `CategoryEvents`, `ProductUpdated`,
`ProductImagePromoted`.

- **Families.** EventCatalog has no family construct. "Product events" and "category events" are
  ordinary event entries, `ProductEvents` and `CategoryEvents`. Each `summary` says that the entry
  stands for a family of event types. AIP treats every event id as an opaque name.
- **Services.** Each service entry's `id` is the deployment name, so it equals the declared Service
  name of §4. `name` is the document label, for example "Catalog Service".
- **`sends` / `receives`.** These equal the result table of parent §3.1 exactly. Category Query has
  a service entry with neither.

### 5.3 Event → Topic lookup

The catalog carries no Topic (D3). The lookup is a separate authored artifact,
`event-topic-lookup.json`, with schema `aip-event-topic-lookup/1`:

```json
{"schema": "aip-event-topic-lookup/1",
 "entries": [{"event_id": "ProductEvents", "topic": "catalog.product.events",
              "source": {"repository": "Sokol111/ecommerce-catalog-service-api",
                         "commit": "7cecb3e1131dbd5199ce25e9cf101d75d3365171",
                         "path": "pkg/events/topics.go"}}]}
```

| `event_id` | `topic` | `source.repository` |
|---|---|---|
| `TenantUpdated` | `tenant.tenant.events` | `ecommerce-tenant-service-api` |
| `ProductEvents` | `catalog.product.events` | `ecommerce-catalog-service-api` |
| `CategoryEvents` | `catalog.category.events` | `ecommerce-catalog-service-api` |
| `ProductUpdated` | `catalog.product.events` | `ecommerce-catalog-service-api` |
| `ProductImagePromoted` | `catalog.product.events` | `ecommerce-image-service-api` |

- The schema is closed, and every catalog event has exactly one entry.
- The lookup names a topic, not a Topic id. I2 resolves the topic to the inventory Topic id of each
  broker in capture scope (parent §3.4).

### 5.4 Generation script

`harness/v08/generate_eventcatalog.py` (stdlib only) generates the catalog and the lookup.

**Input.** The two documents at workspace commit `f6b4c1c`, committed as bytes:

| File | SHA-256 |
|---|---|
| `docs/architecture/platform-overview.md` | `b0c88221781fe6b18295c4e78c7d9e684fd043e238d2eb9621dc5be27b4b226a` |
| `docs/architecture/product-update-flow.md` | `312910e8b917dffe43fe41455b5f312ffbdb8b62d4aa1f9283111f7807ada9b2` |

The script stops before it writes anything if a digest is different.

**Recognized diagram forms.** The script reads exactly these Mermaid arrow forms:

- flowchart `a -. label .-> b` and `a -->|label| b`;
- sequence `A->>B: label`.

A chained flowchart line (`a -->|x| b -->|y| c`) yields one arrow per hop. The script ignores every
other line.

**Fixed tables** in the script:

- **Node → Service:**
  - `tenant` → Tenant;
  - `catalog`, `Catalog` → Catalog;
  - `images`, `Image` → Image;
  - `readModels` → Product Query, Category Query;
  - `ProductQuery` → Product Query.
- **Broker nodes:** `broker`, `Events`.
- **Labels:** the label lookup of parent §3.1. In a sequence label, the script removes a leading
  `Publish ` or `Consume `.
- **Non-event labels:** `build projections`.

**Rule for an arrow between a broker node and a service node:**

1. If the label is a non-event label, the arrow yields no entry.
2. If the label is in the label lookup, the arrow yields a `sends` entry (service → broker) or a
   `receives` entry (broker → service) for every Service of the node.
3. Otherwise, the script stops with an error that names the file and line. It never skips the arrow.

Arrows that have no broker endpoint yield nothing.

**Output.**

- `catalog/`: the EventCatalog of §5.2.
- `event-topic-lookup.json`.
- `catalog.SHA256SUMS`: one line per file under `catalog/`, sorted by path, in `sha256sum` format.
- The **catalog digest**: the SHA-256 of the `catalog.SHA256SUMS` bytes.

All output is deterministic: sorted keys and lists, LF line endings, no timestamps. Two runs produce
byte-identical files.

### 5.5 EventCatalog loader

- New `SourceKind.EVENT_CATALOG = "event_catalog"`. Settings gain `event_catalogs: list[...]`,
  empty by default.
- **Registration:** `id`, `root`, `catalog_relative_path` (default `catalog`),
  `lookup_relative_path` (default `event-topic-lookup.json`), `environment`. Both paths must stay
  inside `root`.
- **Discovery** is by registration only.
- **Bounds:** ≤ 1,000 files, ≤ 256 KiB per file, YAML nesting ≤ 32, no YAML aliases or tags.
- **Loader output:** a typed, immutable declaration set:
  - domains with owners and member services;
  - service entries with `sends` and `receives`;
  - events;
  - the lookup.

  Each item carries its file path and the catalog digest as provenance. The source revision is
  `catalog-sha256:<catalog digest>+lookup-sha256:<lookup digest>`. The lookup digest is SHA-256
  over the exact bytes of the lookup file ([I2](i2-assessment-projection-and-tool.md) D12; Draft 0.1
  had the catalog digest only).
- **Persistence.** I1 persists nothing to the graph. The promise record, and how promises and
  Bounded Context membership are stored, belong to I2.
- **Pipeline.** I2 wires the registration into the import ([I2 §2](i2-assessment-projection-and-tool.md#2-promise-record)). In I1 the loader is a function, tested on its own. I1 does not wire the
  `event_catalogs` registration into `run_all_configured_sources`, and the C1 `config.yaml` does not
  register the catalog. I2 wires it together with the promise record.

**Reason codes** (fixed text; a pointer is a path and a field name, never a value):

| Code | Result |
|---|---|
| `EVENTCATALOG_INVALID` | malformed frontmatter or a missing required field |
| `EVENTCATALOG_UNSUPPORTED` | unknown file or field, alias, tag, or a bound exceeded |
| `EVENTCATALOG_REFERENCE_UNRESOLVED` | unknown or version-mismatched reference, or a missing lookup entry |
| `EVENTCATALOG_MEMBERSHIP_INVALID` | a service in no domain or in several domains |

## 6. Known-answer Topic ids

`topic:owned:<sha256(ld(broker id, "", topic))>`
([v0.7.1 I1 contract §2](../0.7.1/i1-kafka-source-contract.md), K09). The values were computed with
hashlib and cross-checked once against `app.sources.owner_ids.topic_owned_id`:

| Topic | `kafka:sokol111-local` | `kafka:sokol111-kafka` |
|---|---|---|
| `catalog.attribute.events` | `topic:owned:ef00b8a20df7bed4e26c809d03727b11fd83d1169cc8e425f88922d3b5973bd6` | `topic:owned:709cf2cb7051c1368f5f033bf2a57d397d1b5e68a3fdb7d127eaf2ce3deb6efd` |
| `catalog.category.events` | `topic:owned:53418bb503b87bfe0ea8cb1fbc2677d69d1d70dc81b86cb8520dcc03bcc1bfa0` | `topic:owned:975673b170c21ec30dd818af70fecef49f460bd532cee4512a52388402c7443e` |
| `catalog.product.events` | `topic:owned:5534005a20357fa91c86e22e83f557c20a0be39302067e509fa59c85eb034539` | `topic:owned:bfd791ccdd2d47889e5f66e325638655ebd52d6938ee74011f253726d58052de` |
| `tenant.tenant.events` | `topic:owned:80ac3adc89d6d4d0c21254e63f88920456c927900edbe9d78fa242ce57bdc592` | `topic:owned:811dcd9c6959730becbc357c2fa002e5a285298a632e465fe11481a6023bb7be` |

The hashlib script and `ids.json` are committed in `i1-vectors/`.

## 7. Mappings

Each broker has one `aip-kafka-consumer-service-mapping/1` artifact. Every entry is authored from
`kafka.consumers-config.default-group-id` in `ecommerce-infrastructure` `07c0599`
`environments/local/values/<service>.yaml`. The review file lists the source line of each entry.

| Artifact | `broker_id` | Entries (`group_id` = `service_name`) |
|---|---|---|
| `mapping/sokol111-local/kafka-service-mapping.json` | `kafka:sokol111-local` | catalog, category-query, image, product-query |
| `mapping/sokol111-kafka/kafka-service-mapping.json` | `kafka:sokol111-kafka` | catalog, image |

(Each name is `ecommerce-<name>-service`.)

## 8. Package

The new v0.8 evidence package is `docs/specifications/0.8.0/i1-evidence/`. The frozen v0.7.2 package
and its replay test stay unchanged.

```text
i1-evidence/
  README.md                 real vs authored, pins, commands
  upstream/                 the two documents of §5.4 (bytes as fetched)
  catalog/                  generated EventCatalog
  catalog.SHA256SUMS
  event-topic-lookup.json
  declarations/sokol111-local/<service>/asyncapi.yaml
  declarations/sokol111-kafka/<service>/asyncapi.yaml
  mapping/sokol111-local/kafka-service-mapping.json
  mapping/sokol111-kafka/kafka-service-mapping.json
  mapping-review.md
  c1/kafka-consumer-state.json   byte copy of the v0.7.2 C1 capture (digest checked)
  config.yaml               C1 replay profile: sokol111-local declarations, mapping, C1
  SHA256SUMS
```

`harness/v08/generate_eventcatalog.py` is the only generator. Everything else is hand-authored and
marked so in `README.md`. The disclosures of parent §2 apply.

## 9. Acceptance

All checks are tests in the existing tiers. The C1 replay runs in the qualification tier, through
`run_all_configured_sources` and the real discoverer, from `config.yaml`.

| # | Check |
|---|---|
| A1 | The generator reproduces `catalog/`, `event-topic-lookup.json` and `catalog.SHA256SUMS` byte for byte from `upstream/`. A changed upstream digest, or an unknown label on a broker↔service arrow, stops it before it writes anything. |
| A2 | The loaded catalog equals §5.2 and the result table of parent §3.1 exactly (domains, owners, membership, `sends`, `receives`). |
| A3 | Each loader rejection of §5.5 has a test, with the code and no echoed value. |
| A4 | The AsyncAPI change of §3: a topic-only channel is accepted with one Topic and no relation, Broker or `USES_BROKER`. A topic-only Queue channel and the existing rejection cases are unchanged. The test goes red when the change is reverted. |
| A5 | No regression: every existing AsyncAPI unit test and golden passes unchanged. The v0.7.2 Sokol111 replay passes unchanged. |
| A6 | Both declaration sets import together into one snapshot with no Service or Topic conflict. The Topic ids equal §6. The Kafka set emits no `USES_BROKER`. The sokol111-local set emits `PUBLISHES_TO` exactly as in §4.3. This is the first check to run: I3 needs both sets in one snapshot. |
| A7 | The C1 replay persists all nine attachments of parent §3.5, emits no `KAFKA_TOPIC_NOT_DECLARED`, and resolves every attachment to its Service (`RESOLVED`) through the extended mapping. |
| A8 | The six existing tools and REST are byte-identical on their existing goldens, with no allowed difference. |

**Stop rule** (parent §7): if a check cannot pass as specified, record the attempt and ask.

## 10. Decisions

| # | Decision | Source |
|---|---|---|
| D7 | AsyncAPI accepts a qualified Topic channel without operations (§3). Producers are declared as `publish` operations from each Service's own `topics.go`, on the broker that the Service writes to. Topics with a non-Service writer are topic-only (§4.1) | owner, 2026-10-26 |
| D8 | Services are declared by service-level AsyncAPI documents (service-only where a Service publishes nothing). The EventCatalog declares no Service | owner, 2026-10-26 |

D7 amends parent §3.3 ("topic-only AsyncAPI declarations"). The parent specification is amended in
the same PR.

## 11. Handoff to I2 and I3

- **I2** receives:
  - the typed catalog declaration set and the lookup (§5.5);
  - the declared Services and producers, from which it decides the crossings of parent §3.5;
  - resolved attachments on C1.
- **I3** authors the after-wave declaration set by the rules of §4.1, and commits it before the
  after-wave captures. It uses the Kafka mapping of §7 unchanged.
