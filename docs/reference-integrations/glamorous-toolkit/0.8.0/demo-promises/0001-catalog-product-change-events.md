# DEMO-ADR-001 — Catalog offers product-change events

**Status:** `DEMO_ASSUMED_CONFIRMED` — fictional decision of modeled Catalog owner, **not** confirmation by Sokol111 maintainers  
**Modeled promiser:** Catalog service role  
**Audience:** existing shop product-projection consumers; any new marketplace consumer requires separate applicability review  
**Scope:** simulated local e-commerce environment; demo fixture v1

## Context

The existing shop needs a current projection of catalog data across autonomous components. Source code shows Catalog building `ProductUpdatedEvent` with `ProductId`, `Enabled`, product attributes and other fields, plus `ProductDeletedEvent`; its application code uses a transactional outbox. This evidence suggests a plausible external capability but does **not** establish a real owner commitment.

## Decision and offered promise (+)

**For this fictional scenario only**, the modeled Catalog owner offers product-change events to the modeled existing shop projection consumers after successfully committed product updates/deletions, using the published event representation.

**Applicability:** relevant product changes that commit successfully; asynchronous publication and broker operations are distinct from state commit. Audience expansion to an independent marketplace connector is **not assumed**.

**Not promised by this ADR:** a specific end-to-end delivery deadline, perpetual recoverability, full historical replay/initial snapshot, third-party reuse authorization, or external marketplace withdrawal. These are **outside this fictional offer**, not assertions that the real Sokol111 owner explicitly declined them.

## Rationale and consequences

Event-based propagation lets downstream projections maintain state without synchronously calling Catalog on every read. A new consumer must investigate bootstrap, actual event meaning, permissions, recovery and timing before relying on this offer. The 15-minute marketplace withdrawal target does **not** follow from this ADR.

## Evidence / limitations

- [Catalog product event factory](https://github.com/Sokol111/ecommerce-catalog-service/blob/master/internal/infrastructure/outbound/kafka/product_event_factory.go)
- [Catalog application overview](https://github.com/Sokol111/ecommerce-catalog-service/blob/master/AGENTS.md)
- AIP's hosted C1 broker attachments are **separate evidence** and do not qualify this behavioral ADR promise.
- Source commit SHAs and AIP snapshot identity are to be frozen in evaluation increment 1; these links are discovery references, not qualified evidence identifiers.

**Evolution:** demo status changes only by explicitly revising this ADR as a fictional decision; no actual Sokol111 decision is implied.
