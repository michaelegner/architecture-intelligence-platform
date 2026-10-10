# Experiment: EventCatalog semantic mapping

## Purpose

Use the EventCatalog default example as an external architecture model and test whether its semantics can be mapped to AIP without silently changing their meaning.

This is a **model-validation experiment**, not an integration experiment.

The intended outcome is a clearer boundary for AIP:

- which EventCatalog concepts map cleanly to existing AIP concepts,
- which only map with semantic loss,
- which have no AIP equivalent but do not matter for AIP's purpose,
- and which expose a real gap worth considering in AIP.

The experiment must not create an EventCatalog adapter or ingest EventCatalog data into AIP.

## Question

> Can the architectural knowledge in a representative EventCatalog slice be expressed using AIP's current model without collapsing distinctions that matter for evidence-qualified reasoning?

A secondary question is:

> Where EventCatalog and AIP use similar-looking concepts, do they actually mean the same thing?

## Scope

Use the Product Catalog slice from EventCatalog's `examples/default`:

- Catalog domain
- Product Catalog System
- Product API
- Create Product command
- Product Created event
- Product Search Publisher
- Product Database
- transactional-outbox ADR
- `catalog.product-events` channel

Repository:

- https://github.com/event-catalog/eventcatalog/tree/main/examples/default

The experiment should use a pinned EventCatalog commit and the AIP commit on which the comparison is performed.

Do not broaden the first experiment to the complete EventCatalog example.

## Method

### 1. Extract the architectural assertions

Read both structured front matter and explanatory prose.

Capture the relevant assertions independently, for example:

- Product API receives `CreateProduct`.
- Product API writes to Product Database.
- Product Search Publisher reads Product Database.
- Product Search Publisher sends `ProductCreated`.
- `ProductCreated` is sent to `catalog.product-events`.
- the Product Database is authoritative.
- the transactional-outbox ADR applies to the system, publisher and database.

Do not normalize disagreements away during extraction.

In particular, retain statements that may disagree about who publishes `ProductCreated`.

### 2. Map semantics, not syntax

For each EventCatalog concept or assertion, compare it with the current AIP model.

Relevant AIP concepts include:

- Service
- Operation
- Message
- Schema
- Queue / Topic / Subscription
- Relation
- Provenance
- declared vs observed evidence
- evidence-supported claims and qualification

Classify each mapping as:

- **EXACT** — meaning is preserved.
- **PARTIAL** — useful mapping exists, but a material distinction is lost.
- **NO_MAPPING** — AIP has no corresponding concept.
- **NOT_RELEVANT** — AIP has no corresponding concept and does not need one for its current purpose.

For every PARTIAL mapping, state the semantic loss explicitly.

Examples to challenge rather than assume:

- EventCatalog Event → AIP Message
- EventCatalog Channel → AIP Topic
- EventCatalog `sends` → AIP relation
- EventCatalog ADR → AIP evidence
- EventCatalog owner → AIP provenance
- EventCatalog database/container → an AIP entity

### 3. Test the ambiguous publisher case

Use this concrete question:

> Who publishes `ProductCreated`?

Compare all relevant EventCatalog statements, including:

- Product API documentation,
- Create Product documentation,
- Product Created documentation,
- Product Search Publisher documentation,
- Product Catalog System documentation,
- transactional-outbox ADR.

The goal is not merely to produce the expected answer.

The experiment should determine whether AIP's current concepts can preserve the individual assertions and their provenance long enough to support a qualified conclusion instead of flattening them prematurely into one relation.

### 4. Identify semantic gaps

Separate findings into three groups:

1. **EventCatalog concepts absent from AIP**  
   Example candidates: Domain, System, Container, Team, ADR, Actor, Flow.

2. **AIP semantics richer than the EventCatalog representation**  
   Examples: declared vs observed evidence, observation context, evidence qualification and source-specific provenance.

3. **Similar-looking concepts with different semantics**  
   These are the highest-value findings because an apparently easy mapping may be wrong.

A missing EventCatalog concept in AIP is not automatically a gap. It is a gap only if its absence prevents AIP from answering evidence-qualified architecture questions correctly.

## Expected outcome

The experiment should end with a small set of decisions, not a large artifact set.

For the Product Catalog slice, we should be able to say:

- which mappings are safe,
- which mappings are lossy and why,
- which EventCatalog concepts AIP can intentionally ignore,
- whether any current AIP concept conflates meanings that should remain distinct,
- whether the ambiguous `ProductCreated` publisher case reveals a genuine model gap,
- and whether any follow-up experiment or AIP change is justified.

A valid result may be **no AIP change**.

## Non-goals

This experiment does **not** include:

- EventCatalog ingestion,
- an EventCatalog adapter,
- a new `SourceKind`,
- Neo4j changes,
- MCP changes,
- new canonical entities,
- schema changes,
- implementation work based only on feature parity.

No production-model change should be proposed merely because EventCatalog models something AIP does not.

## Completion criteria

The experiment is complete when the comparison supports a defensible statement of this form:

> These EventCatalog concepts map to AIP without semantic loss; these map only with explicit loss; these do not belong in AIP's current model; and these expose genuine gaps in AIP's evidence-qualified reasoning model.

Any proposed AIP change must point to a concrete reasoning failure demonstrated by the experiment, not to a missing EventCatalog feature.
