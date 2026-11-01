I've built the binding picture at `binding-picture/index.html` (self-contained), with the provider's raw answers saved next to it in `binding-picture/provider-responses.json`. **I could not open it in a browser**: Bash was denied and no browser tool was available, so row selection, the filters and evidence navigation are untested.

**Question:** When moving Catalog Management (`ecommerce-catalog-service` + `ecommerce-image-service`) to Apache Kafka, which bindings are configured across the boundary and what is not established? The boundary comes from your task definition. The provider's `catalog-management` context lists exactly those two services. Scope is Kafka bindings in the local environment only.

**Premise check:** the services already talk Kafka (Go client `franz-go`). The local broker is Redpanda v24.3.1, and the docs say production also runs Redpanda. So "moving to Apache Kafka" means swapping the broker.

**Inspected sources (revision from `.git/HEAD`):**
- catalog-service `e9f1474`, image-service `f1b97e8`
- catalog-service-api `7cecb3e`, image-service-api `2167948`, tenant-service-api `d9b9097`
- product-query `b8f5137`, category-query `6cb5373`, tenant-service `dbeacdb` (docs only)
- infrastructure `07c0599` (local values, Tiltfile, `compose/kafka.yml`), commons `d54bf55` (`go.mod` and docs)
- Provider: `get_binding_picture` query and evidence modes, snapshot `aip:snapshot:v1:7f171aea…`, outcome `PARTIAL`, 9 rows. Kafka capture from 2026-10-21T17:53:57Z; all 16 evidence refs resolved.

**Bindings:**

| ID | Direction | Topic or resource | Counterpart | Provider status (verbatim) |
|---|---|---|---|---|
| R1 | ⇒ out | `catalog.product.events` (catalog and image both produce) | product-query | `PROMISED_AND_OBSERVED` |
| R2 | ⟲ inside | `catalog.product.events` | image consumes it | `PROMISED_AND_OBSERVED` |
| R3 | ⇒ out | `catalog.category.events` | category-query | `UNRESOLVED / PROMISE_COVERAGE_MISSING` |
| R4, R5 | ⇒ out | `catalog.attribute.events` | category-query, product-query | `UNRESOLVED / PROMISE_COVERAGE_MISSING` |
| R6, R7 | ⇐ in | `tenant.tenant.events` | tenant-service produces; catalog and image consume | `UNRESOLVED / PROMISE_COVERAGE_MISSING` |
| R10 | ? unresolved | dead-letter topics (`enable-dlq: true` on the tenant consumers) | unknown | no provider row |
| R11 | ◇ shared | broker `redpanda:29092` | all five services | no provider row |

R8 and R9 (the query services' own tenant consumers) don't cross the boundary and are hidden by default.

**Decision-relevant insight:** the facts are that all five services have the same broker address in their local config, and that `catalog.product.events` has two Catalog Management producers and an outside consumer. My interpretation, not a finding: moving only Catalog Management to a separate Kafka cluster would cut off R1 and R3–R7 unless the counterparts switch with it or replication is added. Nothing inspected shows delivery between clusters. So the first decision is whether this is a broker swap for all services or a Catalog-only cluster.

**Unresolved:**
- `ProductDeletedEvent` is produced and handled in code but has no promise; the promises cover only `ProductUpdated` and `ProductImagePromoted`.
- The provider's producer record for `catalog.attribute.events` lists no event types, although code produces `AttributeUpdatedEvent` there.
- Dead-letter topic names and their readers are unknown; the shared library's consumer code wasn't found.
- No source maps the provider's broker id `kafka:sokol111-local` to `redpanda:29092`.
- Topic partition counts and consumer offsets were not captured. Every group starts from the earliest offset if it has none, so a new cluster that receives the topic data without the consumer offsets could replay history into the image service's cleanup handlers, which delete S3 objects. That replay risk is interpretation.
- The tenant-service producer code and production values were not read.
- Without Bash I found files by following known paths, so other references may exist, and I couldn't check for uncommitted changes.

**Checks performed:**
- **Re-read against sources:**
  - R6 (inbound, unresolved)
  - R1 (outbound; source shows the ProductDeleted gap the provider status doesn't)
  - R2 (inside)
  - R4/R5 (unresolved producer declaration)
- **Direction:** re-derived from the task boundary for every row; it matches the provider's classification everywhere.
- **Provider revisions:** its contract lookup commits are the same commits as the API repos in `./src`.
- **Provider findings:** shown verbatim from the embedded response, never re-assessed.
- **Provider toggle:** the "Use provider input" switch, or `?provider=off`, removes all provider statuses, refs and provider-only gaps. Every binding still has its own source facts.
- **In-page checks:** the page also runs integrity checks for refs and leaks when opened. These haven't been run, because I couldn't open the page.
