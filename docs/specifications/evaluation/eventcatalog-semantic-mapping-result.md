# Result: EventCatalog semantic mapping

**Experiment:** [`eventcatalog-semantic-mapping-experiment.md`](eventcatalog-semantic-mapping-experiment.md)
**AIP commit:** `ab3222f67dbdfbe3c4e2ce87cbae3289bf367d52`
**EventCatalog commit:** `d042e3092b44bbcd68f45b63ed5c25c2ff56da13` (`event-catalog/eventcatalog`, `main`, `examples/default`)
**Status:** Paper comparison. No AIP code, schema, graph or adapter was changed or run.

All quotes below are from the pinned EventCatalog commit. Paths are relative to
`examples/default/`; `PCS` abbreviates `domains/Catalog/systems/product-catalog-system`. Line numbers
are file lines (front matter included). AIP claims cite [`canonical-model.md`](../../canonical-model.md),
[`graph-model.md`](../../graph-model.md), [`evidence.md`](../../evidence.md),
[`app/canonical/model.py`](../../../app/canonical/model.py), [`app/canonical/merge.py`](../../../app/canonical/merge.py)
and [ADR 0017](../../adr/0017-source-independent-pubsub-semantics.md). They were read from the docs and
code, not exercised against a running graph.

## 1. Extracted assertions

Extracted independently, not normalized. `FM` = front matter, `P` = prose.

| # | Source (file:line) | Kind | Assertion (verbatim) |
|---|---|---|---|
| A1 | `PCS/services/ProductAPI/index.mdx:11-19` | FM | `receives:` create-product, update-product, delete-product, get-product |
| A2 | `…/ProductAPI/index.mdx:20-23` | FM | `writesTo: product-database`; `readsFrom: product-database` |
| A3 | `…/ProductAPI/index.mdx:37` | P | "records every change to the outbox. The [[service\|product-search-publisher]] then turns those changes into the domain events" |
| A4 | `…/ProductSearchPublisher/index.mdx:11-12` | FM | `readsFrom: product-database` |
| A5 | `…/ProductSearchPublisher/index.mdx:13-18` | FM | `sends: product-created … to: catalog.product-events` (likewise product-updated, product-deleted, lines 19-28) |
| A6 | `…/ProductCreated/index.mdx:21` | P | "`ProductCreated` is published by the [[service\|product-search-publisher]]" |
| A7 | `…/ProductCreated/index.mdx:10` | FM | badge `Broker:Kafka` |
| A8 | `…/CreateProduct/index.mdx:22` | P | "`CreateProduct` is handled by the [[service\|product-api]]. It validates the incoming product, writes it to the [[container\|product-database]], and on success publishes a [[event\|product-created]] event." |
| A9 | `…/CreateProduct/index.mdx:10-13` | FM | `operation: method: POST, path: /products` |
| A10 | `PCS/index.mdx:6` | FM | "Owns the product database and publishes product change events" |
| A11 | `PCS/index.mdx:9-14` | FM | system `services:` product-api, product-worker, product-search-publisher; `containers:` product-database |
| A12 | `PCS/index.mdx:59-63` | P | "Messages this system publishes … [[event\|product-created]]" |
| A13 | `PCS/index.mdx:66` | P | lists `[[adr\|adr-001-use-transactional-outbox]]` under "Messages this system publishes", with the product-deleted description |
| A14 | `PCS/containers/product-database/index.mdx:10` | FM | `authoritative: true` (also `container_type: database`, `access_mode: readWrite`) |
| A15 | `…/product-database/index.mdx:41-42` | P | API "is the only writer to the `products` table"; publisher "is a read-only consumer of the `outbox` table" |
| A16 | `PCS/adrs/adr-001-…/index.mdx:14-20` | FM | `appliesTo:` system product-catalog-system, service product-search-publisher, container product-database |
| A17 | `…/adr-001-…/index.mdx:32` | P | "Publishing to the broker directly from the [[service\|product-api]] request path creates a dual-write problem" |
| A18 | `…/adr-001-…/index.mdx:38` | P | "A separate relay, the [[service\|product-search-publisher]], reads unpublished outbox rows in order and publishes them to the broker" |
| A19 | `channels/catalog.product-events/index.mdx:6,9-12` | FM | "Kafka topic"; `address: catalog.product-events`; `protocols: kafka`; `deliveryGuarantee: at-least-once` |
| A20 | `channels/catalog.product-events/index.mdx:13-15,20` | FM+P | `routes:` to `catalog.product-events.search`; "[[service\|product-search-publisher]] publishes product lifecycle events to this topic" |
| A21 | `domains/Catalog/index.mdx:9-13` | FM | domain `systems:` product-catalog-system, search-system |
| A22 | all slice files | FM | `owners: product-platform` |

Not extracted into a distinct row because they restate A2/A5: the `[[container]]` prose links in
ProductAPI lines 37, 50-51 and the Publisher lines 38, 50.

## 2. Mapping

| EventCatalog concept / assertion | AIP concept | Class | Semantic loss or reason |
|---|---|---|---|
| Service (`product-api`, `product-search-publisher`) | `Service` | **EXACT** | Name, version, identity. EventCatalog's `repository`, language and icon have no AIP field and don't matter. |
| Command `create-product` with `operation: POST /products` (A9) | `Operation` (`PROVIDES`) | **PARTIAL** | The HTTP operation maps. The "command" message-kind and `statusCodes` do not. In practice the authoritative source for the operation would be the OpenAPI document that ProductAPI references (`specifications: openapi.yml`, line 27-30), not this catalog entry. |
| `receives` (A1) | `Service -[PROVIDES]-> Operation` | **PARTIAL** | `receives` is message-direction-neutral across protocols. `PROVIDES` is specifically a REST provider. For a non-HTTP message AIP would need `RECEIVES_FROM` a Queue/Subscription, which A1 doesn't name. |
| Event `product-created` (A6, A7) | `Message` (+ `Schema` via `CONFORMS_TO`) | **PARTIAL** | Name, version and schema map. EventCatalog's Event is also a catalog entry with an owner and a folder location under a producing service (`PCS/services/ProductAPI/events/ProductCreated/`). That location implies ownership or producer, which `Message` does not carry. |
| Channel `catalog.product-events` (A19) | `Topic` | **PARTIAL** | A Kafka channel with an address maps to `Topic` (protocol and name), consistent with ADR 0017. Lost: `deliveryGuarantee`; `routes` to another channel (A20), which AIP has no channel-to-channel route for; and the fact that "Channel" is a single EventCatalog type covering both queue and topic semantics, so each use must be classified, never assumed. |
| `sends … to: channel` (A5) | `Service -[PUBLISHES_TO]-> Topic` + `Topic -[CARRIES]-> Message` | **PARTIAL** | **Message-level attribution is lost.** The edge stores Service→Topic only. Which message a given service sends is not on the edge; it is recoverable only by joining with `CARRIES` on the topic. See §3. |
| `readsFrom` / `writesTo` product-database (A2, A4) | none (no database or data-access relation) | **NO_MAPPING** | Matches the *Database connectivity* candidate in [`semantic-gaps.md`](../../semantic-gaps.md) §1 (Medium). The `Evidence`-based declared/observed distinction could apply, but there is no entity or relation to attach it to. |
| Container `product-database` (A14) | none | **NO_MAPPING** | Same candidate. `authoritative: true` is a single-author claim; AIP has no concept of a data authority. |
| System `product-catalog-system`, Domain `catalog` (A11, A21) | none | **NO_MAPPING** | Matches *Logical composition* (Candidate gap, High). The system also appears as an actor in prose ("this system publishes", A10, A12), which is composition-as-subject and has no AIP counterpart. |
| System→system `relationships` (`search-system`, "notifies of product changes") | none | **NO_MAPPING** | A generic, label-only connection. Matches *Generic declared connectivity* (High). Mapping it to a typed relation would invent semantics. |
| ADR `appliesTo` (A16) | none as a Current-State fact; closest is the Intent side of [`semantic-gaps.md`](../../semantic-gaps.md) §3 | **NO_MAPPING** | AIP's `Evidence` types are `DECLARED` and `OBSERVED`. An ADR's `status: accepted` is attributable *intent*, not a statement of what is deployed. Treating it as `DECLARED` evidence for a relation would turn intent into Current State. |
| `owners` (A22) | none (`Provenance` looks similar but is a different concept) | **NO_MAPPING** | See §4 group 3. Owner is who is *responsible* for an entity; provenance is where a *claim* came from. No useful mapping exists: mapping one to the other would manufacture a claim source. AIP has no ownership concept; this is not a gap unless an ownership question is shown to need one. |
| Actors, Teams, Users, Flows, Entities, runbooks, badges, styles | none | **NOT_RELEVANT** | None changes an answer about declared or observed service, operation, messaging or deployment structure. Revisit only if a concrete question needs them. |

## 3. The ambiguous publisher case: who publishes `ProductCreated`?

| Statement | Says | Names |
|---|---|---|
| A6 `ProductCreated:21` | "published by the product-search-publisher" | Publisher |
| A5 `Publisher` front matter | `sends product-created to catalog.product-events` | Publisher |
| A18 ADR `:38` | the relay "reads unpublished outbox rows … and publishes them to the broker" | Publisher |
| A20 channel `:20` | "[Publisher] publishes product lifecycle events to this topic" | Publisher |
| A3 ProductAPI `:37` | API "records … to the outbox. The Publisher then turns those changes into the domain events" | API does **not** publish |
| A17 ADR `:32` | direct publish "from the API request path creates a dual-write problem" | rejects API publishing |
| A8 CreateProduct `:22` | handled by API; "on success publishes a product-created event" | **grammatically the API** (subject is the command/handler) |
| A10/A12 System | "the system … publishes product change events" | the System, not a Service |

**What the statements actually say.** Only A8 reads as "the API publishes", and A3 and A17 contradict
that reading. The most defensible reading is that A8 describes the end-to-end causal chain loosely,
while A5, A6, A18 and A20 describe the mechanical publisher. A10/A12 attribute at system level.
The experiment therefore doesn't expose a hard factual contradiction in this slice. It exposes a
**granularity difference** ("publishes" meaning causes-to-be-published vs. performs the publish)
that a flattening mapper could turn into a false conflict or a false agreement.

**Can AIP preserve it?**

- *At the relation level, yes.* AIP's relation key is `(type, source_id, target_id)`
  (`app/canonical/merge.py`, `relation_key` in `app/canonical/model.py`). `API -[PUBLISHES_TO]-> Topic`
  and `Publisher -[PUBLISHES_TO]-> Topic` are two distinct relations, each with its own
  `evidence_ids`, so neither silently overwrites the other. Each `Evidence` carries its own
  source, locator and `DECLARED` type.
- *A8's ambiguity is not expressible.* AIP has no way to state "causes-to-be-published". An adapter
  would have to choose `PUBLISHES_TO` (an over-claim, since A3/A17 say the API does not publish) or
  drop the statement. That is the correct, evidence-honest choice (drop it or record a limitation),
  not a model defect.
- *System-level attribution (A10/A12) has no target.* There is no System entity, so it cannot be
  expressed. See group 1.
- *Prose is out of reach regardless of the model.* AIP ingests structured sources (OpenAPI,
  AsyncAPI, manifest, OTel, Kubernetes). A6, A8, A18 and A20 are prose; only A5 is machine-readable.
  This is a source limitation, not a Canonical Model gap.

**The one real structural observation.** Because `PUBLISHES_TO` is Service→Topic and `CARRIES` is
Topic→Message, "who publishes `ProductCreated`" is answered only by joining them. That join is
correct when a topic has one publisher or when every publisher sends every message on it. If two
Services publish *different* messages to the same Topic, the join attributes both Services to both
Messages. **This slice does not demonstrate that failure:** A5 declares one publisher for all three
events. So it is recorded as a candidate observation only. It does not meet the promotion rule in
[`semantic-gaps.md`](../../semantic-gaps.md) §6 (a recurring question, independent real-system
evidence, and a demonstrated wrong answer). It also has not been confirmed against an actual
AsyncAPI-derived graph, where the source may already bind the message to the publishing operation
before the canonical model drops it.

## 4. Semantic gaps

**Group 1 — EventCatalog concepts absent from AIP.** Domain, System, Container/database,
`readsFrom`/`writesTo`, ADR, Actor, Team, Flow, label-only system relationships, channel `routes`.
Of these, only three coincide with existing register entries (logical composition, database
connectivity, generic connectivity). They are not new findings, and one single-vendor example is not
independent evidence for promoting them. No wrong answer to an evidence-qualified question was
demonstrated for any of them. The ADR case is deliberately not a gap; see the Intent vs Current
State boundary.

**Group 2 — AIP richer than the evaluated EventCatalog slice.** This group describes only what the
pinned Product Catalog slice expresses, not EventCatalog's wider capabilities, which were not
evaluated. No declared/observed distinction, observation context, per-claim provenance or
qualification state was found in this slice's front matter or prose. Within it, A5 and A6 appear as
two statements of equal standing, with nothing marking one as machine-readable front matter and the
other as prose. `authoritative: true` appears as a bare assertion with no source. No way was found
in this slice to say "declared but not observed in this window", which AIP treats as distinct from
absent.

**Group 3 — similar-looking, different meaning (highest value).**

1. **Owner ≠ provenance.** `owners` says who is accountable for an entity. `Provenance` says which
   source produced a claim and when. Mapping owner to provenance would manufacture a source for
   claims that have none.
2. **ADR `appliesTo` ≠ declared evidence.** It looks like a relation to the three targets but is
   intent. See §2.
3. **`sends` ≠ `PUBLISHES_TO`.** Same direction, but the message is part of the EventCatalog edge and
   only inferable in AIP (§3).
4. **Channel ≠ Topic in general.** Here the channel is explicitly a Kafka topic, so the mapping is
   safe for this slice. The same EventCatalog type can also name queues, so it must be classified
   per use, consistent with the retained destination guard in ADR 0017.
5. **"publishes" at three levels** (handler, relay, system) is one verb with three meanings (A8,
   A5, A10).
6. **`authoritative`** is a property claim by one author, not a relation. It is not the same thing
   as a `DECLARED` relation with evidence.
7. **Catalog content is not self-consistent.** A13 lists an ADR under "Messages this system
   publishes" with the product-deleted description, which looks like a copy-paste error in the
   example. Any ingestion of such content would carry it, a reminder that declared documentation
   needs qualification, not trust.

## 5. Decisions

- **Safe mappings:** Service → `Service`; Kafka channel → `Topic` (this slice, protocol and address
  explicit); the schema'd Event → `Message` + `Schema`; command with an HTTP `operation` → `Operation`.
- **Lossy mappings (loss stated in §2):** `receives`, `sends`, Event, Channel, Command. `owners` is NO_MAPPING, not lossy: no useful mapping exists.
- **Intentionally ignored:** Actors, Teams, Users, Flows, Entities, runbooks, presentation metadata.
- **Does any current AIP concept conflate meanings that should stay distinct?** No conflation
  demonstrated. The only candidate is the message-level attribution of `PUBLISHES_TO` + `CARRIES`
  (§3), which this slice does not exercise.
- **Does the publisher case reveal a genuine model gap?** No. AIP can hold the conflicting
  assertions as separate relations with separate evidence. Prose extraction and system-level
  attribution are source and boundary limits, not Canonical Model defects.
- **Is an AIP change justified?** **No AIP change.** Everything that EventCatalog models and AIP
  doesn't either matches an existing register entry (without new independent evidence) or does not
  affect evidence-qualified answers.
- **Follow-up (optional, bounded):** if the message-level attribution question matters, test it on
  an independently authored multi-publisher AsyncAPI topic and check whether the graph already keeps
  the per-operation message binding. Run it only if a concrete question needs it, not for parity.

## 6. Limits of this result

- Single vendor-authored example; the Product Catalog slice only.
- AIP behavior was read from docs and code, not run. The `PUBLISHES_TO`+`CARRIES` join claim in
  particular should be confirmed on a real graph before anyone relies on it.
- Assertion extraction and classification are one reviewer's judgment and should be challenged.
