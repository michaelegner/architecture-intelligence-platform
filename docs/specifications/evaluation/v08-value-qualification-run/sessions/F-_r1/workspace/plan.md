# Plan: move Catalog Management from Redpanda to Apache Kafka

## What moves and what crosses the boundary

`ecommerce-catalog-service` and `ecommerce-image-service` move to Kafka (`kafka:29092`). Tenant,
product-query and category-query services stay on Redpanda (`redpanda:29092`).

Topic map (source + live config + `rpk group describe`):

| Topic | Producers | Consumers (groups) |
|---|---|---|
| `catalog.product.events` | catalog (ProductUpdated/Deleted), **image** (ProductImagePromoted) | image, product-query |
| `catalog.category.events` | catalog | category-query |
| `catalog.attribute.events` | catalog | product-query, category-query |
| `tenant.tenant.events` | tenant | catalog, image, product-query, category-query |

Note: image-service also produces to `catalog.product.events`
(`ecommerce-image-service-api/pkg/events/topics.go:11-16`). Because both producers of that topic
move together, the topic's producers all end up on Kafka.

Bindings that cross the boundary (six):

- **Outbound** (Kafka → Redpanda consumers): product-query × `catalog.product.events`,
  product-query × `catalog.attribute.events`, category-query × `catalog.category.events`,
  category-query × `catalog.attribute.events`.
- **Inbound** (Redpanda → Kafka consumers): catalog × `tenant.tenant.events`,
  image × `tenant.tenant.events`.

image × `catalog.product.events` stays inside the boundary. product-query/category-query ×
`tenant.tenant.events` stay outside it. Neither needs mirroring.

All six bindings were observed (live groups on Redpanda). Only product-query × product events
(product-update-flow.md) and category-query × category events (platform-overview.md, diagram
level) are documented. The attribute bindings and the tenant-consumer bindings are not
documented.

## MirrorMaker 2 design

One MM2 process (container `mm2-catalog-move`, the on-host `apache/kafka:4.1.2@sha256:5cc2…`
image, `shared-network`) runs two flows with **disjoint** allow-lists:

- `redpanda->kafka`: `tenant.tenant.events`
- `kafka->redpanda`: `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events`

No topic is mirrored in both directions. Settings:

- `IdentityReplicationPolicy` keeps topic names unchanged, so no consumer subscription changes.
- Heartbeats are off on both flows. MM2 replicates heartbeat topics regardless of the allow-list,
  and with identity naming that would create a two-way loop. A gate checks that no heartbeats
  topic exists.
- Topic-config and ACL sync are off, so MM2 does not alter Redpanda topics.
- Checkpoints and group-offset sync are on only for `redpanda->kafka`, groups
  `ecommerce-catalog-service` and `ecommerce-image-service`. They carry those groups' tenant-topic
  positions over to Kafka.
- Kafka's `catalog.*` topics are pre-created empty (1 partition). They hold only what the moved
  producers write. The image group starts there from `earliest`, which is correct for a fresh topic.

## Cutover order and why

1. Preflight on both brokers. Kafka, Helm and the network could not be queried in planning, so
   these checks come first.
2. Create the Kafka topics, write the MM2 config, start MM2, verify the gates (tenant topic copied,
   Redpanda catalog offsets unchanged, no heartbeats topic).
3. **Stop catalog-service first.** Its outbox keeps unsent events in MongoDB, so nothing is lost
   while it is down.
4. **Drain image-service on Redpanda** (lag 0 on `catalog.product.events`) before stopping it.
   Product events written directly to Redpanda are never mirrored to Kafka, so image-service must
   consume them before it switches.
5. Verify the tenant offsets synced to Kafka for both groups.
6. Switch image-service, then catalog-service (`kafka.brokers: kafka:29092` in the values files
   and in the live ConfigMaps, which were backed up first), and scale them back up.
7. Verify group membership on both brokers, ask the operator for the functional test, then verify
   offsets and lag moved as expected.

Each gate is a stop point: on failure, stop and report, rolling back only items recorded in
`cutover/created-resources.txt` (each name checked before deletion).

## What this plan does not claim

The move is not claimed to be lossless or exactly-once. MM2 delivers at-least-once, and offset
translation is approximate. The checks compare counts and lags. They do not prove that every
record was delivered exactly once. Open points are listed in `answers.json` q5:

- Kafka state not queried during planning
- producers inferred, not observed
- MM2 heartbeat behaviour and Redpanda compatibility
- DLQ topics split across the two brokers
- local environment only
