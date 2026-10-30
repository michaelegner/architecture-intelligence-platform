# Plan: move Catalog Management from Redpanda to Apache Kafka

AIP snapshot: `aip:snapshot:v1:18d59102a7c451ae8e84d3acaf3d2c6b036ff105ec14a59f255c2be0ffda906e`
(binding picture for `catalog-management`, environment `local`, captured 2026-10-29T20:02:22Z).

This is a planning session. Nothing was changed. The execution session carries out `plan.json`
and asks the platform team to run the broker, Docker and Kubernetes commands.

## What moves

`ecommerce-catalog-service` and `ecommerce-image-service` move to Kafka. Everything else stays on
Redpanda. So the Catalog Management context boundary is now also the broker boundary.

Topics the moving services produce (from the `-api` topic maps):

| Topic | Producers (declared) |
|---|---|
| `catalog.product.events` | catalog-service (ProductUpdated/Deleted), image-service (ProductImagePromoted) |
| `catalog.category.events` | catalog-service |
| `catalog.attribute.events` | catalog-service |

Topics the moving services consume: `tenant.tenant.events` (both services; producer
tenant-service stays on Redpanda) and `catalog.product.events` (image-service; inside the context,
so it moves with it).

## Bindings that cross the boundary (AIP + source)

| Consumer | Topic | Direction | Documented | Observed |
|---|---|---|---|---|
| catalog-service | tenant.tenant.events | inbound | no | yes |
| image-service | tenant.tenant.events | inbound | no | yes |
| product-query-service | catalog.product.events | outbound | yes | yes |
| category-query-service | catalog.category.events | outbound | yes | yes |
| category-query-service | catalog.attribute.events | outbound | no | yes |
| product-query-service | catalog.attribute.events | outbound | no | yes |

Five of the six are not covered by any catalog promise (AIP: `PROMISE_COVERAGE_MISSING`), and four are
not named in any document.
The attribute-events bindings are the ones that a doc-driven plan would miss.

## MirrorMaker 2 flows (no topic in both directions)

- **mm2-catalog-inbound, redpanda → kafka:** `tenant.tenant.events`. Checkpoints and group offset
  sync for `ecommerce-catalog-service` and `ecommerce-image-service`, so the moved consumers resume
  near their Redpanda position instead of replaying from `earliest` or skipping.
- **mm2-catalog-outbound, kafka → redpanda:** `catalog.product.events`, `catalog.category.events`,
  `catalog.attribute.events`, into the existing same-named Redpanda topics.

Both use `IdentityReplicationPolicy`. The default policy would rename topics (`redpanda.tenant.tenant.events`)
and every consumer would miss them. Identity naming is only safe because no topic is in both
allow-lists. Each flow runs in its own container from the `apache/kafka:4.1.2@sha256:5cc2a2fd...`
image on `shared-network`. Heartbeats, checkpoints and topic-config sync are turned off for the outbound
flow, so it writes as little as possible into Redpanda.

## Order and why

1. **Baseline (P00).** Record the topics, partitions, groups and lag on Redpanda, check that Kafka is
   empty, and check the image digest. Compare the live group list with the table above, because the
   AIP capture covers only its configured groups. A group the table doesn't have means stop.
2. **Pre-create the catalog topics on Kafka (P01)** with Redpanda's partition counts. That stops
   auto-creation with a wrong count, and MM2 keeps partition = partition, so per-key order holds.
3. **Start the inbound flow (P02)** and wait until the Kafka copy of `tenant.tenant.events` catches up.
4. **Start the outbound flow (P03)** before anyone produces on Kafka.
5. **Stop the two services (P04)** and drain their groups on Redpanda to lag 0. This matters for
   image-service on `catalog.product.events`. That topic is mirrored only Kafka → Redpanda, so
   anything it hadn't read on Redpanda would never reach it on Kafka. A stopped group also lets MM2
   sync its offsets to Kafka.
6. **Check the translated offsets on Kafka (P05).** If they are missing, stop. Don't start on an empty
   group with `earliest`.
7. **Switch the broker address (P06).** The platform team sets `kafka.brokers` to `kafka:29092` in the
   catalog and image values under `ecommerce-infrastructure/environments/local/values/` and applies
   it with `helm upgrade`, not Tilt. I can't see those files, so the platform team confirms the file
   names and key.
8. **Start and verify (P07, P08).** The groups are Stable on Kafka. The product-query and
   category-query groups on Redpanda keep consuming new records on all three catalog topics. Mirrored
   records keep their key, partition and tenant header. Then
   `OPERATOR: please run the functional test` and wait for the result.

Any failed check means stop and report. Don't continue past it.

## Rollback and cleanup

Rollback means reverting the values, running the services on Redpanda again and stopping the MM2
containers. Expect duplicates, because the Redpanda groups resume from offsets before the cutover. For
cleanup, delete only the MM2 containers, the topics this plan created on Kafka, and the MM2 internal
topics and groups that are in the after-list but not in the P00 baseline. Check every name against
that baseline before deleting it. If the move succeeds, the flows stay running.

## What this does not establish

- The binding list may be incomplete, because the capture scope is limited.
- An attachment doesn't show that the events are handled.
- Producers are declared, not observed.
- Delivery between the brokers isn't shown by any evidence. MM2 is at-least-once, so the move is
  **not** claimed to be lossless or exactly-once.
- The local group ids and values keys still need confirming. For example, `config.e2e.yaml` uses the
  group `catalog-service-tenant-events`, but AIP observed `ecommerce-catalog-service`.

The details are in `answers.json` q5.
