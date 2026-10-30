# Plan: move Catalog Management from Redpanda to Apache Kafka

AIP snapshot: `aip:snapshot:v1:18d59102a7c451ae8e84d3acaf3d2c6b036ff105ec14a59f255c2be0ffda906e`
(binding picture, `catalog-management` / `local`, capture 2026-10-29T20:02:22Z, outcome PARTIAL).
The full Redpanda consumer-group listing (request R1) matches the AIP rows exactly. R2 (Helm
values) was not available.

## 1. What moves

`ecommerce-catalog-service` and `ecommerce-image-service` move. They switch their whole Kafka client
(outbox producer and consumers) from `redpanda:29092` to `kafka:29092`. Every other service stays on
Redpanda. The broker boundary therefore matches the context boundary of Catalog Management.

## 2. Bindings and what crosses

| Consumer | Topic | Producer(s) | Crossing | Documented | Observed |
|---|---|---|---|---|---|
| product-query-service | catalog.product.events | catalog-service, image-service | outbound | yes (product-update-flow.md) | yes |
| product-query-service | catalog.attribute.events | catalog-service | outbound | **no** | yes |
| category-query-service | catalog.category.events | catalog-service | outbound | cannot tell (named only in aggregate) | yes |
| category-query-service | catalog.attribute.events | catalog-service | outbound | **no** | yes |
| catalog-service | tenant.tenant.events | tenant-service | inbound | no (producer side only) | yes |
| image-service | tenant.tenant.events | tenant-service | inbound | no | yes |
| image-service | catalog.product.events | catalog-service, image-service | inside (moves together) | yes | yes |
| category/product-query | tenant.tenant.events | tenant-service | none (both stay) | – | yes |

The two `catalog.attribute.events` bindings and both tenant bindings have no catalog promise in AIP
(`PROMISE_COVERAGE_MISSING`), and the docs don't name them. They show up only in the broker evidence.
A plan built from the documentation alone would drop `catalog.attribute.events` from the mirror and
stop the attribute projections of both query services.

## 3. Mirror design

Two one-way MM2 flows with disjoint allow-lists. No topic is mirrored in both directions.

| Flow | Topics |
|---|---|
| redpanda → kafka | `tenant.tenant.events` |
| kafka → redpanda | `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events` |

- **Topic names stay the same** (`IdentityReplicationPolicy`). The consumers subscribe to fixed names
  (`topics.go`), so the default `<alias>.` prefix would break them. Identity naming turns off MM2's
  loop detection, which is one more reason the allow-lists must stay disjoint.
- **The staying consumers keep their Redpanda groups.** Mirrored records are appended to the
  existing Redpanda topics after their committed offsets (product 120, category 4, attribute 20), so
  no offset translation is needed for them. Checkpoints and group sync are off for kafka→redpanda.
- **The moving consumers on `tenant.tenant.events`** get their Redpanda position carried over
  through MM2 checkpoints and `sync.group.offsets` for groups `ecommerce-catalog-service` and
  `ecommerce-image-service`. MM2 writes these only while the target group is inactive, which holds
  until P08.
- **`catalog.product.events` for the image service** cannot be offset-translated: that would need a
  redpanda→kafka flow for a topic that already flows kafka→redpanda. Instead, both producers are
  stopped before the switch (P07), so Redpanda has no events the image service still needs. Kafka
  `catalog.product.events` starts empty, and the image group's Kafka offset is pinned to 0 (P06).
  Redpanda history is **not** copied to Kafka.
- Heartbeats, topic-ACL sync and topic-config sync are off, so that MM2 creates as little as
  possible on Redpanda.

### mm2/mm2.properties (written by the execution session, in the workspace)

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
sync.topic.acls.enabled = false
sync.topic.configs.enabled = false
refresh.topics.interval.seconds = 10
refresh.groups.interval.seconds = 10

# Flow 1: inbound tenant events, with offset carry-over for the two moving groups
redpanda->kafka.enabled = true
redpanda->kafka.topics = tenant\.tenant\.events
redpanda->kafka.groups = ecommerce-catalog-service|ecommerce-image-service
redpanda->kafka.emit.checkpoints.enabled = true
redpanda->kafka.emit.checkpoints.interval.seconds = 10
redpanda->kafka.sync.group.offsets.enabled = true
redpanda->kafka.sync.group.offsets.interval.seconds = 10
redpanda->kafka.offset-syncs.topic.location = target
redpanda->kafka.consumer.auto.offset.reset = earliest

# Flow 2: outbound catalog events, no group translation
kafka->redpanda.enabled = true
kafka->redpanda.topics = catalog\.product\.events|catalog\.category\.events|catalog\.attribute\.events
kafka->redpanda.groups.exclude = .*
kafka->redpanda.emit.checkpoints.enabled = false
kafka->redpanda.sync.group.offsets.enabled = false
kafka->redpanda.offset-syncs.topic.location = source
kafka->redpanda.consumer.auto.offset.reset = earliest
```

Run (platform team), image `apache/kafka:4.1.2@sha256:5cc2a2fd93fa2687b44015eee04fb2c3edd9e526bd64bf8bec5ff1e268772e0e`,
container `mm2-catalog-move`, network `shared-network`, config mounted read-only,
`/opt/kafka/bin/connect-mirror-maker.sh /mm2/mm2.properties`.

MM2 will create internal topics: on Kafka the `mm2-{configs,offsets,status}.redpanda.internal`,
`redpanda.checkpoints.internal` and `mm2-offset-syncs.*.internal` topics; on Redpanda the
`mm2-{configs,offsets,status}.kafka.internal` topics. P04 records each name actually created
against the P01 baseline. Only those names may be removed later.

## 4. Sequence (see plan.json for checks and evidence)

1. **P01** Read-only baseline on both brokers (topics, partitions, groups, offsets). Stop if Kafka
   is not empty or the groups differ from R1.
2. **P02** Create the three catalog topics on Kafka with partition counts matching Redpanda.
3. **P03/P04** Write the MM2 config and start the MM2 container.
4. **P05 (check)** `tenant.tenant.events` is on Kafka with the same end offset, and both moving
   groups have translated offsets equal to their Redpanda offsets. If not, stop.
5. **P06** Pin `ecommerce-image-service` on Kafka `catalog.product.events` to offset 0 (the
   auto-offset-reset in Helm is unknown).
6. **P07** Scale down catalog-service. Wait until the image-service lag on Redpanda is 0. Scale down
   image-service.
7. **P08** Platform team changes only the broker address in both Helm values and runs `helm upgrade`
   (no Tilt), then scales back up. The catalog and image outboxes, which are persisted in Mongo,
   flush to Kafka.
8. **P09 (check)** Attachments on Kafka; Redpanda query groups still Stable; mirrored records appear
   on Redpanda.
9. **P10** `OPERATOR: please run the functional test`, then wait. Stop on failure.
10. **P11 (check)** Kafka and Redpanda offset growth match per topic; all lags are 0.
11. **P12** Only on stop or rollback: revert the broker address, then remove the MM2 container and
    only the names on the created list. Existing Redpanda topics and groups are never deleted. The
    old Redpanda groups of the moved services stay in place.

Catalog writes are unavailable for a short time between P07 and P08. That is the price of not
needing offset translation for `catalog.product.events`.

## 5. What this does not establish

- Cross-broker delivery is not established by any evidence. MM2 delivers at least once, so
  duplicates can occur. The cutover can also reorder events relative to each other (the product
  projections are versioned, per product-update-flow.md). **This plan claims no lossless and no
  exactly-once move.**
- Attachment is not event handling, and producers are only declared. A writer on Redpanda to the
  catalog topics that is not known today would not reach the image service after the move.
- The consumer picture is a single point in time. P01 re-checks it.
- R2 was unavailable. The Helm key and file names, the tenant consumer's topic and group config,
  auto-offset-reset and DLQ settings must be confirmed by the platform team before P08.
- MM2 offset translation can lag, which would redeliver a TenantUpdated or TenantDeleted. P05
  checks this. After the move, a newly created tenant must be checked for migrated catalog and
  image databases.
