# Plan: move Catalog Management from Redpanda to Apache Kafka

## What moves

`ecommerce-catalog-service` and `ecommerce-image-service` move to Kafka (`kafka:29092`). The topics
they produce move with them:

| Topic | Producers (source) |
|---|---|
| `catalog.product.events` | catalog-service (`ecommerce-catalog-service-api/pkg/events/topics.go:18-19`) and image-service (`ecommerce-image-service-api/pkg/events/topics.go:16`) |
| `catalog.category.events` | catalog-service (`topics.go:20`) |
| `catalog.attribute.events` | catalog-service (`topics.go:21`) |

Both producers of `catalog.product.events` move together, so this shared topic does not need to be
split. The image service consuming `catalog.product.events` stays inside the boundary.

## Bindings that cross the boundary

From the consumer groups on Redpanda (request R1) and from the source:

| Consumer | Topic | Direction | Documented | Observed |
|---|---|---|---|---|
| ecommerce-catalog-service | tenant.tenant.events | inbound | no | yes |
| ecommerce-image-service | tenant.tenant.events | inbound | no | yes |
| ecommerce-product-query-service | catalog.product.events | outbound | yes (product-update-flow.md:28,34) | yes |
| ecommerce-product-query-service | catalog.attribute.events | outbound | no | yes |
| ecommerce-category-query-service | catalog.category.events | outbound | yes (platform-overview.md:41-43,51) | yes |
| ecommerce-category-query-service | catalog.attribute.events | outbound | no | yes |

Four of the six bindings, including both tenant bindings and both attribute bindings, appear in no
document. Only the running broker shows them. The tenant consumer is wired in through
`fx_tenant_api.NewKafkaConsumerModule()` in both moved services. It drives per-tenant migrations,
and in the image service it also drives S3 cleanup on tenant delete.

## Bridge design: two one-way MirrorMaker 2 flows

* **redpanda → kafka:** `tenant.tenant.events` only. The groups `ecommerce-catalog-service` and
  `ecommerce-image-service` get their offsets synced, so they resume at their translated position.
* **kafka → redpanda:** `catalog.product.events`, `catalog.category.events` and
  `catalog.attribute.events`. MM2 appends to the existing Redpanda topics. The query-service groups
  keep their Redpanda offsets (120 / 4 / 20) and simply continue. No checkpoints or group sync in
  this direction.

The allow-lists are disjoint, so no topic is mirrored in both directions.
`IdentityReplicationPolicy` keeps topic names unchanged, which matters because every service
subscribes to the literal name. It also turns off MM2's cycle detection, so heartbeats are disabled
(the heartbeats topic would otherwise bounce between the brokers). The preflight also checks that no
`heartbeats` topic exists. Topic config and ACL sync are off: Redpanda does not accept every Kafka
topic config.

`mm2/mm2-catalog.properties` (written by the executor in the workspace and mounted read-only into
the MM2 container):

```properties
clusters = redpanda, kafka
redpanda.bootstrap.servers = redpanda:29092
kafka.bootstrap.servers = kafka:29092

replication.policy.class = org.apache.kafka.connect.mirror.IdentityReplicationPolicy
replication.factor = 1
checkpoints.topic.replication.factor = 1
heartbeats.topic.replication.factor = 1
offset-syncs.topic.replication.factor = 1
offset.storage.replication.factor = 1
status.storage.replication.factor = 1
config.storage.replication.factor = 1

emit.heartbeats.enabled = false
sync.topic.configs.enabled = false
sync.topic.acls.enabled = false

redpanda->kafka.enabled = true
redpanda->kafka.topics = tenant\\.tenant\\.events
redpanda->kafka.groups = ecommerce-catalog-service|ecommerce-image-service
redpanda->kafka.emit.checkpoints.enabled = true
redpanda->kafka.sync.group.offsets.enabled = true
redpanda->kafka.sync.group.offsets.interval.seconds = 10

kafka->redpanda.enabled = true
kafka->redpanda.topics = catalog\\.product\\.events|catalog\\.category\\.events|catalog\\.attribute\\.events
kafka->redpanda.groups.exclude = .*
kafka->redpanda.emit.checkpoints.enabled = false
kafka->redpanda.sync.group.offsets.enabled = false
```

The container runs
`/opt/kafka/bin/connect-mirror-maker.sh /config/mm2-catalog.properties` from
`apache/kafka:4.1.2@sha256:5cc2a2fd93fa2687b44015eee04fb2c3edd9e526bd64bf8bec5ff1e268772e0e`, named
`mm2-catalog`, on `shared-network`. Nothing is pulled.

## Order of steps (see plan.json for details)

1. **Inputs (P01).** Get partition counts, topic configs, DLQ topics and the real Helm `kafka`
   values. R2 was not available, so these are still unknown. If anything contradicts the plan,
   stop.
2. **Clean-state checks (P02) and baseline (P03).** Kafka is empty, the image is present, no
   `mm2-catalog` container exists and no MM2 internal topics exist. Record the offsets.
3. **Create the catalog topics on Kafka (P04)** with matching partition counts.
4. **Start MM2 (P05–P07).** Check that `tenant.tenant.events` is mirrored and that the two moved
   groups' translated offsets equal the Kafka end offset. Stop otherwise: a conservative
   translation would replay tenant lifecycle events, including deletes that wipe S3.
5. **Stop the moved producers (P08).** Scale both deployments to 0 and wait until all Redpanda
   consumers of `catalog.*` have lag 0. Writes in this window stay queued in the Mongo outbox.
   With no producer on Redpanda, no event gets there through both an old producer and MM2.
6. **Switch brokers (P09).** The platform team changes the Helm values (their repo, outside this
   workspace) and runs `helm upgrade`. Tilt stays off.
7. **Verify (P10).** Check lag and offsets on both brokers, then ask
   `OPERATOR: please run the functional test` and wait.
8. **Failure handling (P11).** Delete only what we created, after checking each name. Before the
   switch, roll back by stopping MM2 and deleting our Kafka topics. After the switch, stop and
   report rather than re-pointing automatically.

## What this plan doesn't guarantee

MirrorMaker 2 delivers at least once at best. This plan does not claim the move is lossless or
exactly-once: duplicates after an MM2 restart are possible. The query projections are
version-guarded, which tolerates duplicates and reordering but cannot recover a dropped event.
Open points are listed in answers.json q5:

* Runtime Helm config and DLQ topics are unknown (R2 not available).
* Partition counts are inferred from R1, not confirmed.
* Consumers that weren't running at the R1 snapshot can't be seen.
* Offset translation has to be checked before the switch.
