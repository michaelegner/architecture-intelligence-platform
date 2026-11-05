# DEMO-ADR-001 — Catalog offers product-change events

**Status:** `DEMO_ASSUMED_CONFIRMED` — fictional decision of the modeled Catalog owner; **not** Sokol111 maintainer confirmation  
**Modeled decision owner:** Catalog service role  
**Audience:** existing shop projection consumers  
**Scope and version:** simulated local e-commerce environment, fixture v1

## Context

The existing shop needs product changes to reach independently maintained read projections. Sokol111's Catalog code builds versioned `ProductUpdatedEvent` and `ProductDeletedEvent` messages and uses a transactional outbox for updates and deletes. These are **source facts**, not real owner confirmation.

## Decision and local offer (+)

**In this fictional experiment**, Catalog offers product-change event messages for successfully committed product updates and deletions to the modeled existing shop projection consumers through its asynchronous outgoing-event mechanism.

**Conditions and scope:** The offer concerns the published event representation and existing shop projection use. Catalog transaction completion, event queuing and downstream processing are different stages. Additional consumers and changed purposes need their own applicability and acceptance examination.

## Rationale and consequences

A change-event interface lets separately owned projections evolve without requiring every read to call Catalog synchronously. This ADR describes the modeled provider's local offer; it does **not** decide what another service will consume, how a future connector will work or what an external marketplace will do. Any other externally relevant semantics must be established from an independently attributable commitment and appropriately scoped evidence.

## Evidence and limitations

- [Catalog product event factory](https://github.com/Sokol111/ecommerce-catalog-service/blob/master/internal/infrastructure/outbound/kafka/product_event_factory.go)
- [Catalog application overview](https://github.com/Sokol111/ecommerce-catalog-service/blob/master/AGENTS.md)
- [Catalog update transaction/outbox use](https://github.com/Sokol111/ecommerce-catalog-service/blob/master/internal/application/product/update_product.go)

Implementation supports the **plausibility** of the fictional decision but does not establish service-wide delivery behavior, owner approval or any AIP-qualified semantic promise. The frozen AIP C1 bindings are separate, bounded evidence. Pin exact source SHAs and the AIP package/snapshot before evaluating.

**Evolution:** Only the modeled Catalog owner can revise this fictional offer; other participants' acceptance remains independent.
