# Service-local Promise Contracts — Sokol111 demo

Sokol111 is a **sample codebase**, not a real customer whose owners have approved these commitments. Each YAML file is a fictional, independently modeled local offer or acceptance. The contracts are **not** an AIP schema, OpenAPI/AsyncAPI format, operational guarantee or real maintainer approval.

| Promise | Modeled owner | Contract |
|---|---|---|
| `CAT-OFFER-01` — product-change offer (+) | Catalog | [catalog/product-change-events.yaml](catalog/product-change-events.yaml) |
| `IMG-OFFER-01` — image-promotion offer (+) | Image | [image/image-promotion-information.yaml](image/image-promotion-information.yaml) |
| `PQ-ACCEPT-01` — Catalog event acceptance (−) | Product Query | [product-query/catalog-change-acceptance.yaml](product-query/catalog-change-acceptance.yaml) |
| `PQ-READ-01` — read-model offer (+) | Product Query | [product-query/product-reads.yaml](product-query/product-reads.yaml) |

The [independent fictional marketplace withdrawal contract](marketplace-withdrawal-contract.md), `DEMO_CONTRACT_ASSUMED`, is **not** a Sokol111 service promise. It separates authenticated withdrawal requests, acceptance/rejection and eventual completed/failed outcomes, **without any numeric processing deadline**.

## Local fixture convention

Fields: `id`, `title`, `kind` (`offer`/`acceptance`), `status`, `promiser`, `audience`, `scope` (including `fixture_version`), `commitment`, `conditions`, `limitations`, `rationale`, `evidence` and `evolution`; acceptances also name the `counterparty`. The field vocabulary is **demo-only**, not a universal promise registry. Contract IDs and versions are scoped to their modeled service roles. Each contract can be inspected or evolved independently.

**`DEMO_ASSUMED_CONFIRMED`** means accepted **in the fictional exercise**, not by Sokol111 maintainers; it is **not** an AIP status. Source URLs establish possible implementation behavior, not owner confirmation. Freeze exact code and hosted AIP C1 evidence identities separately before evaluation. Existing AIP v0.8 does **not** ingest these contracts or qualify their promises as Intent.

**Input/output boundary:** the four existing-service contracts and the external-marketplace contract are furnished **before** investigation. The merchant's hypothetical **15-minute withdrawal target is a business requirement only**. The proposed Marketplace Connector has **no seeded Promise Contract, accepted reliance or externally offered guarantee**. An optional `DEMO_PROPOSED` consumer contract—or explicit refusal—is an **investigator-produced result** after exploring independent providers, conditions and missing agreements.

All comparison conditions receive the same frozen contracts, source/broker evidence and task; only AIP qualification differs. Evaluate decision-changing insights, unsupported promises and fixture/GT maintenance cost separately from merely discovering documents.

See the [experiment specification](../specification.md).
