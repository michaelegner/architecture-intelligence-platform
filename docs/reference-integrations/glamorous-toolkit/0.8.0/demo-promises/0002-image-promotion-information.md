# DEMO-ADR-002 — Image offers promoted-image information

**Status:** `DEMO_ASSUMED_CONFIRMED` — fictional decision of modeled Image owner, **not** confirmation by Sokol111 maintainers  
**Modeled promiser:** Image service role  
**Audience:** existing shop read-model consumers; no automatic promise to a proposed marketplace connector  
**Scope:** simulated local e-commerce environment; demo fixture v1

## Context

Catalog events carry product image identity, while the Image service manages promotion and delivery. The existing Product Query consumer handles `ProductImagePromotedEvent` to update stored image URLs. This supports a plausible external image-information capability, not real owner approval.

## Decision and offered promise (+)

**For this fictional scenario only**, the modeled Image owner offers an event with promoted product image information for the modeled existing projection consumers when image promotion succeeds.

**Applicability:** successful image promotion within the relevant tenant and event semantics; this offer does not imply that every product update produces an image event.

**Not promised by this ADR:** image URLs embedded in each Catalog product event, a fixed delivery or availability deadline, third-party marketplace usage rights, permanent URL stability, or an end-to-end listing update guarantee. These are **outside the fictional offer**, not a documented refusal by real maintainers.

## Rationale and consequences

Media lifecycle is managed separately from product attributes. A new consumer should check whether it needs Image's capability, whether the intended audience is covered and which additional conditions could support its own listing promises. This ADR deliberately does **not** settle the 15-minute withdrawal requirement.

## Evidence / limitations

- [Image service overview](https://github.com/Sokol111/ecommerce-image-service/blob/master/AGENTS.md)
- [Product Query handling of image promotion](https://github.com/Sokol111/ecommerce-product-query-service/blob/master/internal/infrastructure/inbound/kafka/product_handler.go)
- AIP's frozen broker evidence may help locate the existing participants but does **not** assess this fictional semantic promise.
- Source SHAs and AIP snapshot identity must be frozen during increment 1.

**Evolution:** this demonstration decision may be revised/superseded only in the demo overlay; no upstream owner commitment is implied.
