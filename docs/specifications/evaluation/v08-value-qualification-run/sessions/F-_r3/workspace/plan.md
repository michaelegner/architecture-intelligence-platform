# Plan: move Catalog Management from Redpanda to Apache Kafka

## Scope

The services that move are `ecommerce-catalog-service` and `ecommerce-image-service`. The services
that stay on Redpanda are `ecommerce-tenant-service`, `ecommerce-product-query-service` and
`ecommerce-category-query-service`. The brokers are bridged by one MirrorMaker 2 process
(container `mm2-catalog-move`, image `apache/kafka@sha256:5cc2a2fd…`, `--pull never`).

## What crosses the boundary

The planning session found the following:

- Producers come from the source topic registries and event factories. `catalog-service` writes
  `catalog.product.events`, `catalog.category.events` and `catalog.attribute.events`.
  `image-service` writes `ProductImagePromotedEvent` to `catalog.product.events`, so that topic has
  two producers and both move. `tenant-service` writes `tenant.tenant.events`, and it stays.
- Consumers come from the Helm values. The deployed ConfigMaps are identical to the values files.
- The runtime picture comes from `rpk group describe`. All four groups are Stable with lag 0, and
  every configured binding has a live member.

| Consumer | Topic | Direction | Documented | Observed |
|---|---|---|---|---|
| product-query | catalog.product.events | outbound | yes (product-update-flow.md) | yes |
| product-query | catalog.attribute.events | outbound | no | yes |
| category-query | catalog.category.events | outbound | no (overview mentions it only vaguely) | yes |
| category-query | catalog.attribute.events | outbound | no | yes |
| catalog-service | tenant.tenant.events | inbound | no (only the producer is drawn) | yes |
| image-service | tenant.tenant.events | inbound | no | yes |

`image-service` consuming `catalog.product.events` is internal to the boundary. Both ends move, so
it needs no mirror. It does need care at cutover, because image-service must never sit on a
different broker from catalog-service. That is why both services move in one step.

Three of the six crossing bindings appear in no document: the two attribute bindings and the
category binding. A docs-only plan would lose them. The allow-lists below are built from source,
config and broker evidence.

## Mirror design

Each topic is mirrored in exactly one direction, and the two allow-lists are disjoint.

| Flow | Topics |
|---|---|
| redpanda → kafka | `tenant.tenant.events` |
| kafka → redpanda | `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events` |

- **IdentityReplicationPolicy.** Consumers keep their topic names, and mirrored records are
  appended to the existing Redpanda topics, so the query services' committed offsets stay valid.
  Identity naming cannot detect replication loops, which is another reason for disjoint
  allow-lists.
- **Same partition count (1) on Kafka.** The four topics are pre-created so partition mapping is
  1:1 and per-key order is kept.
- **Group-offset sync only on redpanda→kafka, only for the two moving groups.** Their consumers
  use `auto-offset-reset: earliest`. Without translated offsets they would replay tenant events
  on Kafka. After cutover, sync is turned off (S06) so stale Redpanda offsets cannot overwrite the
  live Kafka groups.
- **Things turned off on both flows:** heartbeats, topic-config sync and ACL sync. MM2 must not
  alter the existing Redpanda topics. Offset-syncs for redpanda→kafka are kept on the Kafka side.

`mm2/mm2-catalog-move.properties`:

```properties
clusters = redpanda, kafka
redpanda.bootstrap.servers = redpanda:29092
kafka.bootstrap.servers = kafka:29092

replication.policy.class = org.apache.kafka.connect.mirror.IdentityReplicationPolicy
replication.factor = 1
offset-syncs.topic.replication.factor = 1
checkpoints.topic.replication.factor = 1
heartbeats.topic.replication.factor = 1
config.storage.replication.factor = 1
offset.storage.replication.factor = 1
status.storage.replication.factor = 1
emit.heartbeats.enabled = false
sync.topic.configs.enabled = false
sync.topic.acls.enabled = false
refresh.topics.interval.seconds = 10
refresh.groups.interval.seconds = 10

redpanda->kafka.enabled = true
redpanda->kafka.topics = tenant\.tenant\.events
redpanda->kafka.groups = ecommerce-catalog-service, ecommerce-image-service
redpanda->kafka.emit.checkpoints.enabled = true
redpanda->kafka.emit.checkpoints.interval.seconds = 10
redpanda->kafka.sync.group.offsets.enabled = true
redpanda->kafka.sync.group.offsets.interval.seconds = 10
redpanda->kafka.offset-syncs.topic.location = target

kafka->redpanda.enabled = true
kafka->redpanda.topics = catalog\.product\.events, catalog\.category\.events, catalog\.attribute\.events
kafka->redpanda.emit.checkpoints.enabled = false
kafka->redpanda.sync.group.offsets.enabled = false
```

## Sequence

All steps are in `plan.json`. Each verification step stops the run on failure.

1. **Pre-flight (P01–P04).**
   - Redpanda still matches the snapshot.
   - Kafka is empty and reachable as `kafka:29092` on shared-network.
   - The moving pods can resolve `kafka`.
   - The names `mm2-catalog-move` and `mm2/` are free.
2. **Bridge first (S01–S05, V01).**
   - Create the four Kafka topics and start MM2.
   - Verify the tenant topic is copied and the two groups' offsets are translated on Kafka.
   - Verify nothing changed on the Redpanda catalog topics.
3. **Cutover (C01–C06).**
   - Record baseline offsets and edit `config.kafka.brokers` in the two values files.
   - Scale both moving services to 0. The outbox holds any unpublished events.
   - Check that both Redpanda groups are drained (image-service lag 0 on `catalog.product.events`)
     and that the tenant offsets on Kafka match.
   - Patch both ConfigMaps to `kafka:29092`, scale back to 1, and confirm the groups are Stable on
     Kafka.
4. **Test (T01).** `OPERATOR: please run the functional test`, then wait for the result.
5. **Verify (V02).**
   - Each outbound consumer group on Redpanda has advanced from the baseline with lag 0.
   - Redpanda end-offset growth matches Kafka growth.
   - Keys and headers survive the mirror.
6. **Settle (S06).** Turn off group-offset sync on redpanda→kafka and restart MM2.
7. **Rollback (R01)** only if a check after the stop fails.

The bridge stays in place: tenant-service and the query services remain on Redpanda.

## What this plan does not claim

- The move is **not** lossless or exactly-once. MM2 is at-least-once and adds delay.
  - The product projection is versioned, which the doc says tolerates duplicates and reordering.
    This was not verified for category-query or image-service.
  - The drain check reduces the risk of image-service missing events but does not prove it.
- Kafka reachability and its advertised listener were not verified in planning. P02 and P03 cover
  this.
- The DLQ topic `tenant.tenant.events.dlq` has no consumer and is not mirrored. After the move,
  DLQ records from catalog-service and image-service go to Kafka.
- Production values are out of scope.

## Created resources (for any later cleanup)

- The container `mm2-catalog-move`.
- The workspace files `mm2/` and `cutover/`.
- The Kafka topics `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events`
  and `tenant.tenant.events`.
- The MM2 internal topics recorded in V01.

Delete only names from this list, after checking that each one exists. Never delete the
pre-existing Redpanda topics or the four Redpanda consumer groups.
