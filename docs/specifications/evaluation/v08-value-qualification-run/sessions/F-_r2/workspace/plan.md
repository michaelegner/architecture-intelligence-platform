# Plan: move Catalog Management from Redpanda to Apache Kafka

## What moves and where the boundary is

`ecommerce-catalog-service` and `ecommerce-image-service` switch from `redpanda:29092` to
`kafka:29092`. `ecommerce-tenant-service`, `ecommerce-product-query-service` and
`ecommerce-category-query-service` stay on Redpanda. The boundary is the broker. A consumer ×
topic binding crosses it when its producer and its consumer end up on different brokers.

## What I found

| Topic | Producer(s) | Consumers (group = service name) |
|---|---|---|
| `catalog.product.events` | catalog-service (ProductUpdated/Deleted), **image-service** (ProductImagePromoted) | image-service, product-query |
| `catalog.category.events` | catalog-service | category-query |
| `catalog.attribute.events` | catalog-service | product-query, category-query |
| `tenant.tenant.events` | tenant-service | catalog, image, product-query, category-query |

Sources: the local Helm values (`environments/local/values/*.yaml`), the `topics.go` files of the
three `-api` repos, the outbound event factories, and the inbound `consumer.Register` calls.
`rpk group describe` showed all four groups Stable with lag 0, and they are attached to exactly
these topics. So runtime matches config.

Two findings shape the plan:

- **image-service is also a producer on `catalog.product.events`.** That binding is internal to the
  boundary, because both producers and the image-service consumer move together. product-query on
  the far side needs both producers' events.
- **The attribute bindings and the tenant bindings appear in no document.** The docs show only
  product events to product-query and, at a grouped level, "product and category events" to the
  query services. The plan relies on config and runtime evidence for the rest.

### Bindings that cross the boundary

Inbound (Redpanda → Kafka): catalog-service × `tenant.tenant.events`, image-service ×
`tenant.tenant.events`.

Outbound (Kafka → Redpanda): product-query × `catalog.product.events`, product-query ×
`catalog.attribute.events`, category-query × `catalog.category.events`, category-query ×
`catalog.attribute.events`.

These do not cross: image-service × `catalog.product.events` (both ends on Kafka), and the query
services × `tenant.tenant.events` (both ends on Redpanda).

## MirrorMaker 2 design

One dedicated MM2 process (`connect-mirror-maker.sh`) runs in a container `mm2` from the local
`apache/kafka:4.1.2@sha256:5cc2…` image on `shared-network`. It has two flows with disjoint
allow-lists:

- `redpanda->kafka`: `tenant.tenant.events`. Checkpoints and group-offset sync are on for groups
  `ecommerce-catalog-service|ecommerce-image-service`, so the moved consumers start on Kafka near
  their Redpanda position. Without that, `auto-offset-reset: earliest` replays tenant history.
- `kafka->redpanda`: `catalog.product.events|catalog.category.events|catalog.attribute.events`.
  The flow appends into the existing Redpanda topics, so product-query and category-query keep
  their groups and offsets and change nothing.

`IdentityReplicationPolicy` keeps topic names unchanged. That policy cannot detect cycles, so the
rule "no topic in both directions" is what prevents loops, and the plan checks it. Heartbeats,
topic-config sync and ACL sync are off. Redpanda-specific configs would not apply on Kafka, and
heartbeats would create a `heartbeats` topic on both sides.

Kafka runs with `KAFKA_AUTO_CREATE_TOPICS_ENABLE=false`. So the catalog topics and
`tenant.tenant.events.dlq`, which the tenant-event consumers write to on failure, are created on
Kafka before the cutover. Each gets 1 partition and the same retention as Redpanda. One partition
plus the product-id key keeps per-product order.

## Order of the cutover

1. Preflight: check that Kafka is empty and reachable, take a Redpanda baseline, confirm the
   names to be created are free, and check that a pod can reach `kafka:29092`. I could not query
   Kafka in this session, so these checks matter.
2. Create the Kafka topics, write `mm2/mm2.properties` in the workspace, and start `mm2`.
3. Check that `tenant.tenant.events` is mirrored to Kafka with the same end offset.
4. Scale **catalog-service to 0 first**. Then wait until image-service has drained Redpanda
   `catalog.product.events` (lag 0). The Kafka topic starts empty, so image-service must not
   leave unread ProductUpdated events behind on Redpanda.
5. Scale image-service to 0. Check that both Redpanda groups are Empty with lag 0.
6. Check that MM2 synced the two groups' offsets on Kafka. If it did not, stop.
7. Change only `config.kafka.brokers` in the two values files, apply the two ConfigMaps, and
   scale both services back to 1. Do not start Tilt and do not commit.
8. Check the Kafka groups, then the outbound mirror: for each catalog topic, the Redpanda end
   offset must equal the baseline plus the Kafka end offset, and the query groups must show lag 0.
9. `OPERATOR: please run the functional test`, then repeat the checks.
10. Leave `mm2` running. List everything the plan created, for any later cleanup.

Every check is a stop point: if it fails, the executing session stops and reports. The rollback
item covers the way back. Before step 7 it is easy. After step 7 it causes duplicates, not loss.

## What this plan does not claim

I do not claim the move is lossless or exactly-once. MM2 is at-least-once and offset translation
is approximate. The catalog write path is unavailable between steps 4 and 7. Outbox rows written
before the stop should be published to Kafka after the restart, but that is unverified. The
open points are listed in `answers.json` q5: Kafka state not queried, pod-to-Kafka reachability,
DLQ topic handling, idempotency of the tenant handlers, outbox behaviour, and the production
environment, which is out of scope.
