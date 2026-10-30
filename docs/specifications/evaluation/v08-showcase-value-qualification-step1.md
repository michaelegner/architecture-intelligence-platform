# v0.8 showcase value qualification: Step 1 matrix

**Spec:** [§3](v08-showcase-value-qualification-experiment.md#3-step-1-binding--source-matrix)
**Date:** 2026-10-29
**Inputs:** the 16 Sokol111 repositories, cloned from GitHub at the
[v0.7.2 freeze commits](../0.7.2/i2-evidence/sokol111/freeze.md) (each `HEAD` checked); the frozen
v0.8 capture [`S1-13-groups-describe.txt`](../0.8.0/i4-evidence/raw/S1-13-groups-describe.txt); the
[I2 §8.1 rows](../0.8.0/i2-assessment-projection-and-tool.md#81-c1-primary-acceptance).

Paths are relative to the repository root. `PQ` is `ecommerce-product-query-service`, `CQ` is
`ecommerce-category-query-service`. `local/values/` is
`ecommerce-infrastructure/environments/local/values/`.

## 1. Matrix

`Y` = the source establishes the consumer × topic pair. `P` = it names the consumer or the topic
family, but not the pair. `N` = it does not.

| # | Row (I2 §8.1) | Crossing | Documents | Team source | Infrastructure | All source | Broker tools | AIP |
|---|---|---|---|---|---|---|---|---|
| 1 | PQ × `catalog.product.events` | `OUTBOUND` | Y (a) | P (d) | Y | Y | Y | Y |
| 2 | Image × `catalog.product.events` | `INSIDE` | Y (a) | Y (e) | Y | Y | Y | Y |
| 3 | Catalog × `tenant.tenant.events` | `INBOUND` | N | Y (f) | Y | Y | Y | Y |
| 4 | Image × `tenant.tenant.events` | `INBOUND` | N | Y (f) | Y | Y | Y | Y |
| 5 | CQ × `catalog.category.events` | `OUTBOUND` | P (b) | P (d) | Y | Y | Y | Y |
| 6 | PQ × `catalog.attribute.events` | `OUTBOUND` | N | P (d) | Y | Y | Y | Y |
| 7 | CQ × `catalog.attribute.events` | `OUTBOUND` | N | P (d) | Y | Y | Y | Y |
| 8 | PQ × `tenant.tenant.events` | `NONE` | N (c) | P (g) | Y | Y | Y | Y |
| 9 | CQ × `tenant.tenant.events` | `NONE` | N (c) | P (g) | Y | Y | Y | Y |

**References:**

- (a) `ecommerce-workspace/docs/architecture/product-update-flow.md:28,34` (PQ consumes
  `ProductUpdated` and the image promotion event), `:31` (Image consumes `ProductUpdated`). The
  document names events, not topics. `catalog-service-api/pkg/events/topics.go:18` and
  `image-service-api/pkg/events/topics.go:16` map both events to `catalog.product.events`.
- (b) `platform-overview.md:43,51`: "Product and category events" go to the broker, and the broker
  builds the projections of the "Product and Category Query Services". No topic per service.
- (c) `platform-overview.md:50`: Tenant publishes `TenantUpdated`; no consumer is named.
- (d) `catalog-service-api/AGENTS.md:13` ("the query services (consume the events into their read
  models)"), `catalog-service/AGENTS.md:8`, `image-service-api/AGENTS.md:14-16`, and
  `ecommerce-workspace/README.md:42` (PQ "built from catalog Kafka events"). No topic per service.
- (e) `image-service/configs/config.standalone.yaml:21`, `image-service/AGENTS.md:57`,
  `image-service/internal/infrastructure/inbound/kafka/product_handler.go`.
- (f) `catalog-service/internal/infrastructure/fxconfig/module.go:13` and
  `image-service/internal/infrastructure/fxconfig/module.go:36` call
  `fx_tenant_api.NewKafkaConsumerModule()`; `tenant-service-api/pkg/fxconfig/consumer.go:25` wires the
  consumer and `tenant-service-api/pkg/events/topics.go:11` names the topic. Also
  `catalog-service/configs/config.e2e.yaml:17`.
- (g) `ecommerce-workspace/README.md:45` and `AGENTS.md:80`: Tenant is "consumed by every other service",
  without saying through Kafka; `tenant-service-api/AGENTS.md:33-36`: services add their own
  cleanup through the consumer module.
- **Infrastructure:** `local/values/ecommerce-product-query-service.yaml:28,34,40`,
  `ecommerce-category-query-service.yaml:28,34,40`, `ecommerce-catalog-service.yaml:38`,
  `ecommerce-image-service.yaml:30,32`. The production values show the same pairs.
- **All source:** in addition to the team source, `PQ/configs/config.standalone.yaml:21,23`,
  `CQ/configs/config.standalone.yaml:23,25`, and `fxconfig/module.go:13` in both query services.
- **Broker tools:** `S1-13-groups-describe.txt` lines 1–44. Each group name is the service name.

## 2. Direction and status

- **Crossing direction:** derivable wherever the pair is known. The producers are in the team source:
  `catalog-service-api/pkg/events/topics.go:11-13` (Catalog: the three `catalog.*` topics),
  `image-service-api/pkg/events/topics.go:11` (Image: `catalog.product.events`) and
  `tenant-service-api/pkg/events/topics.go:11` (`tenant.tenant.events`, produced outside Catalog
  Management). The task card names the services that move.
- **Documented:** only rows 1 and 2 are named by a document (a). AIP's `PROMISED` status for these two
  rows comes from the generated EventCatalog, which states the same two consumptions. No document
  names rows 3–9.
- **Observed:** only the broker tools and AIP establish runtime attachment. The source and the Helm
  values establish wiring and configuration, not attachment.

## 3. Leak check (team-scoped workspace)

| Content | Reveals K2–K4 (rows 1, 5, 6, 7)? |
|---|---|
| `ecommerce-infrastructure` (`local/values/`) | **Yes, every pair**, and rows 8–9 |
| `ecommerce-workspace/docs` | row 1 only (a); row 5 partly (b) |
| `ecommerce-workspace` README, `AGENTS.md`, `go.work` | partly: query services consume catalog events (d), (g); `go.work` names the other modules |
| Team repositories' `AGENTS.md` | partly (d) |
| Go module files of the team repositories | no: they require only `catalog-service-api`, `image-service-api`, `commons` and `tenant-service-api` |

## 4. Information baseline

- **Full access:** all source, the Helm values and the broker tools each establish all nine pairs.
  AIP adds no binding that F− cannot find. AIP adds the joined status (documented vs. observed per
  pair) and its provenance. The documented status for rows 1–2 is also in the documents.
- **Team-scoped without `ecommerce-infrastructure`:** the team source establishes rows 2–4. Rows 1
  and 5–9 are partial: the agent knows that query services consume catalog events, but not which
  service consumes which topic. AIP, R1 or R2 grants establish them.
- **Team-scoped with `ecommerce-infrastructure`:** all nine pairs are in the workspace. Only the
  observed status needs AIP or R1.

## 5. For checkpoint 1 (D5)

Per the spec §4.2 table:

- **Include `ecommerce-infrastructure`:** Step 1 shows that it reveals K2–K4. T then tests discovery
  without runtime access only, and K7 is scored.
- **Exclude it:** T tests discovery without other teams' repositories and without runtime access. K7
  is not scored in T.

**Decision (owner, 2026-10-29): exclude `ecommerce-infrastructure`.** T tests discovery without other
teams' repositories and without runtime access. K7 is not scored in T. Disclosure: many
organisations make such a platform repository readable to all teams.
