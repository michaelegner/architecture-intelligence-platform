# Plan: move Catalog Management from Redpanda to Apache Kafka

## Scope

The services `ecommerce-catalog-service` and `ecommerce-image-service` move to Kafka
(`kafka:29092`). The tenant, product-query and category-query services stay on Redpanda.
MirrorMaker 2 bridges the two brokers.

## What the evidence shows

**Producers (from source):**
- The catalog service produces `catalog.product.events`, `catalog.category.events` and
  `catalog.attribute.events` (`src/ecommerce-catalog-service-api/pkg/events/topics.go:11-21`).
- The image service produces `ProductImagePromotedEvent` to `catalog.product.events`
  (`src/ecommerce-image-service-api/pkg/events/topics.go:11-16`).
- The tenant service produces `tenant.tenant.events`
  (`src/ecommerce-tenant-service/internal/infrastructure/outbound/kafka/event_factory.go:19-42`).

**Consumers (source, plus the runtime group descriptions from R1):**

| Group (= service) | Topics on Redpanda |
|---|---|
| ecommerce-catalog-service | tenant.tenant.events |
| ecommerce-image-service | catalog.product.events, tenant.tenant.events |
| ecommerce-product-query-service | catalog.product.events, catalog.attribute.events, tenant.tenant.events |
| ecommerce-category-query-service | catalog.category.events, catalog.attribute.events, tenant.tenant.events |

All lags were 0 when R1 was taken. End offsets: product 120, category 4, attribute 20, tenant 1.

**Bindings that cross the boundary (q2):**
- Inbound (Redpanda → Kafka): catalog-service and image-service × `tenant.tenant.events`.
- Outbound (Kafka → Redpanda): product-query × `catalog.product.events` and
  `catalog.attribute.events`; category-query × `catalog.category.events` and
  `catalog.attribute.events`.

**Bindings that do not cross:**
- The image service on `catalog.product.events`: both producers of that topic move, so this
  stays inside Kafka.
- The query services on `tenant.tenant.events`: these stay on Redpanda.

## Design

Two MM2 flows run in one dedicated-mode MM2 process, in a new container `mm2-catalog`. It uses the
already-present `apache/kafka:4.1.2@sha256:5cc2a2fd…` image and runs
`/opt/kafka/bin/connect-mirror-maker.sh`.

| Flow | Topics |
|---|---|
| redpanda → kafka | `tenant.tenant.events` |
| kafka → redpanda | `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events` |

The allow-lists are disjoint, so no topic is mirrored in both directions. Each topic has exactly
one "home" broker after the cutover:
- `catalog.*` lives on Kafka: all of their producers move.
- `tenant.*` lives on Redpanda: its producer stays.

**IdentityReplicationPolicy.** Services subscribe by exact topic name, and the default policy
would prefix topics (`redpanda.tenant.tenant.events`). The identity policy keeps the names, but it
removes MM2's own cycle protection, so the disjointness above is what keeps loops out. For the
same reason:
- Heartbeats are disabled on both flows. MM2 always replicates heartbeats topics, which under
  the identity policy would be a two-way mirror.
- The preflight checks that no `heartbeats` topic exists.

**Offsets:**
- On Kafka, the `catalog.*` topics are new and empty. The image service starts on them from
  offset 0 and sees only post-move events. No replay is needed.
- On Redpanda, mirrored `catalog.*` records are appended after the current end offsets, so the
  query groups continue where they are.
- For `tenant.tenant.events`, the moved groups would otherwise start from the beginning
  (`default-auto-offset-reset: earliest`) and re-run tenant migrations and cleanup. MM2
  checkpoints with `sync.group.offsets.enabled` are therefore turned on for redpanda→kafka only,
  limited to `ecommerce-catalog-service` and `ecommerce-image-service`.
- The plan checks the synced offsets before the services start. If they are wrong, it stops
  instead of resetting by hand.
- Checkpoints and offset sync are off for kafka→redpanda, so no Redpanda group is ever written.

**Topic config and ACL sync** are disabled, so MM2 doesn't change the existing Redpanda topics.

**Cutover order:**
1. Stop the catalog service first.
2. Let the image service drain its Redpanda backlog on `catalog.product.events`, then stop it.
3. Switch both services to `kafka:29092` and start them again.

Outbox rows that were not yet sent stay in MongoDB, and the relay sends them to Kafka after the
restart. The broker switch is a Helm-values change (`kafka.brokers`, or env `KAFKA__BROKERS`, see
`src/ecommerce-commons/pkg/core/config/koanf.go:19-24`). It is outside the workspace, so the
platform team makes it and applies it with helm, not Tilt.

## Steps (see plan.json)

| Step | What it does |
|---|---|
| P00 | Preflight gate: Kafka empty, topic configs, no heartbeats/mm2 topics, container name free, image present. Stop on any failure. |
| P01 | Create the four topics on Kafka with partitions and cleanup policy matching Redpanda. |
| P02 | Write `mm2/mm2-catalog.properties` (flows F1 and F2). |
| P03 | Start `mm2-catalog`; record the MM2 internal topics it creates. |
| P04 | Verify the inbound copy and the synced tenant offsets for the two moved groups. |
| P05 | Record replicas, stop the catalog service, drain the image service, stop it, record end offsets. |
| P06 | Platform team switches the brokers and scales both services back up. |
| P07 | Verify the groups are attached on the correct brokers. |
| P08 | `OPERATOR: please run the functional test`, plus checks that events flow end to end in both directions. Stop on failure. |
| P09 | Rollback path. |
| P10 | Cleanup scope: only what this plan created, checked by name first. |

## Things not established

The details are in answers.json q5. In short:
- Redpanda topic configs and Kafka emptiness were not available (R6).
- The Helm values were not available (R5): deployed group ids, DLQ settings and the broker key are
  unknown.
- R1 is a snapshot, so the seeder job, any stopped services and the UIs are not covered.
- Redpanda/MM2 behaviour and offset translation are not tested.

Nothing here claims the move is lossless or exactly-once. MM2 is at-least-once, and the
downstream projections tolerate duplicates only because they are version-guarded
(`product-update-flow.md:43-45`).
