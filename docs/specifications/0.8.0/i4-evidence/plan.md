# Plan: move Catalog Management from Redpanda to Apache Kafka

AIP snapshot: `aip:snapshot:v1:4d8db6483e03a6564e593a3cbcf07bd1bcb7795c22bd975e95dd9e5ab11313a6`
(`get_binding_picture`, `catalog-management`, `local`, broker `kafka:sokol111-local` = the Redpanda
broker. Outcome **PARTIAL**, broker capture at 2026-10-28T11:55:58Z.)

## What AIP shows and what the source confirms

Event bindings that touch Catalog Management (rows of the binding picture):

| Topic | Producer (declared) | Consumer | Crossing | Status |
|---|---|---|---|---|
| catalog.product.events | catalog, image | ecommerce-image-service | INSIDE | PROMISED_AND_OBSERVED |
| catalog.product.events | catalog, image | ecommerce-product-query-service | OUTBOUND | PROMISED_AND_OBSERVED |
| catalog.category.events | catalog | ecommerce-category-query-service | OUTBOUND | UNRESOLVED (PROMISE_COVERAGE_MISSING) |
| catalog.attribute.events | catalog | ecommerce-category-query-service | OUTBOUND | UNRESOLVED (PROMISE_COVERAGE_MISSING) |
| catalog.attribute.events | catalog | ecommerce-product-query-service | OUTBOUND | UNRESOLVED (PROMISE_COVERAGE_MISSING) |
| tenant.tenant.events | tenant | ecommerce-catalog-service | INBOUND | UNRESOLVED (PROMISE_COVERAGE_MISSING) |
| tenant.tenant.events | tenant | ecommerce-image-service | INBOUND | UNRESOLVED (PROMISE_COVERAGE_MISSING) |
| tenant.tenant.events | tenant | product-query, category-query | NONE | (not affected) |

The three "UNRESOLVED / PROMISE_COVERAGE_MISSING" outbound rows are observed bindings that the
event catalog does not declare. They are real consumers and I treat them like the declared ones.
The local Helm values (`environments/local/values/*-query-service.yaml`) match them.

AIP's limits that shape the plan:
- **CAPTURE_SCOPE_LIMITED**: the capture covers only configured groups. So PRE-01 lists *all*
  groups on Redpanda before the move. If an unknown group reads a topic that this plan doesn't
  cover, I stop.
- **PRODUCER_SIDE_DECLARED_ONLY**: AIP only declares producers and never observes them. The
  source code confirms them: `ecommerce-catalog-service-api/pkg/events/topics.go` lists the three
  catalog topics, and `ecommerce-image-service-api/pkg/events/topics.go` shows the image service
  writes to `catalog.product.events`.
- AIP never establishes delivery between brokers. I check the bridge only with broker tools.

During planning I could not run `rpk`, `docker` or `kubectl` because those calls were denied. So
partition counts, the full group list, replica counts and the Kafka listener inside the container
are not known yet. PRE-01 reads them first.

## Topology after the move

- **Kafka** gets the producers of `catalog.product.events`, `catalog.category.events` and
  `catalog.attribute.events` (catalog, image) and the consumers of `tenant.tenant.events` (catalog,
  image) and `catalog.product.events` (image).
- **Redpanda** keeps `tenant.tenant.events` (producer: tenant service) and the consumers
  product-query and category-query.

So there are two MM2 flows, and they share no topics:

| Flow | Topics |
|---|---|
| redpanda -> kafka | `tenant.tenant.events` |
| kafka -> redpanda | `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events` |

No topic is mirrored both ways. `IdentityReplicationPolicy` keeps topic names, so the consumers
need no change. That policy cannot detect loops, which is why the disjoint allow-lists matter.
Heartbeats are also turned off, so MM2 creates no `heartbeats` topic for the two flows to copy back
and forth.

**Not mirrored:** `tenant.tenant.events.dlq`. Catalog and image write their DLQ messages for
tenant events to `<topic>.dlq` (`commons/pkg/kafka/config/defaults.go:61`), so after the move
their DLQ messages land on Kafka. AIP shows no consumer of this DLQ. PRE-01 checks Redpanda for
one, and if one exists I stop rather than add a flow without an amendment.

## Sequence and why

1. **PRE-01 / PRE-02.** Read-only checks, then back up the two ConfigMaps and the replica counts.
   Tilt deployed with `helm template` + `k8s_yaml`, so there is no Helm release to upgrade. The
   live ConfigMap `<name>-config` is what the pods read.
2. **KAFKA-01.** Create the three catalog topics on Kafka with the same partition counts as on
   Redpanda. The producers allow auto-creation, which would use broker defaults and could change
   which partition a key goes to.
3. **MM2-01 / MM2-02.** Run one dedicated MM2 process (`catalog-move-mm2`, host image by digest,
   on `shared-network`) with both flows. The redpanda->kafka flow also emits checkpoints and syncs
   group offsets, only for `ecommerce-catalog-service` and `ecommerce-image-service`, and with
   `offset-syncs.topic.location=target` so MM2 writes nothing to Redpanda for that flow. Checkpoints
   follow the flow's topic list, so the image group's Redpanda offsets on `catalog.product.events`
   are not copied onto Kafka's new, separate topic.
4. **CHK-01.** `tenant.tenant.events` on Kafka has caught up with Redpanda, and MM2 has tasks for
   the catalog topics.
5. **CUT-01.** Stop catalog first. Its outbox keeps unsent events in MongoDB, and they publish to
   Kafka after restart. Then let the image service drain `catalog.product.events` on Redpanda to lag
   0 and stop it. This step matters because the Kafka copy of that topic starts empty. Seeding it
   from Redpanda would mean mirroring the topic in both directions.
6. **CHK-02.** Both groups have translated offsets on Kafka `tenant.tenant.events`, so they
   continue where they stopped instead of replaying from `earliest`. Translation is conservative: it
   may point earlier, which means some events get delivered again. It never points past unread
   events.
7. **CUT-02.** Set `kafka.brokers: "kafka:29092"` in both ConfigMaps and scale back up. One
   setting covers the producer, the consumers and the DLQ producer.
8. **CHK-03, TEST-01, REPORT-01.** Check the consumers on both brokers and ask the operator for
   the functional test. The MM2 bridge stays running; it is part of the target state.

Any failed check stops the run and is reported.

## What this plan creates (and so may later remove)

- Kafka topics `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events`.
  `tenant.tenant.events` and `tenant.tenant.events.dlq` appear on Kafka through MM2 and the
  services.
- Container `catalog-move-mm2`.
- MM2 internal topics. On Kafka: `mm2-configs/offsets/status.redpanda.internal`,
  `redpanda.checkpoints.internal`, `mm2-offset-syncs.kafka.internal`. On Redpanda:
  `mm2-configs/offsets/status.kafka.internal`. PRE-01 checks that none of these exist before the
  move.
- Kafka consumer-group offsets for the two moved groups.
- Workspace files `mm2/`, `backup/`, `patched/`.
- Changed: the ConfigMaps `ecommerce-catalog-service-config` and `ecommerce-image-service-config`.
  The repo values files are not edited.

Nothing is deleted in this plan. Before anything created is removed later, I check it by name
against this list.

## Rollback (only if the operator asks; recorded as an amendment)

1. Scale both services to 0.
2. Apply the `backup/` ConfigMaps and scale back to the saved replica counts.

Events produced on Kafka in the meantime have already been mirrored to Redpanda. The image group's
old Redpanda offset on `catalog.product.events` is then behind, so those events are delivered
again.

## Delivery guarantees

The move gives at-least-once delivery at best. Some events may be delivered again: offset
translation is conservative and MM2 can redeliver on restart. Ordering is kept per partition
within each topic. The two brokers also stay mixed for a while, because catalog topics on Redpanda
hold pre-move records written directly and post-move records mirrored from Kafka. I make no claim
that the move is lossless or exactly-once. The query services' versioned projections
(product-update-flow.md) tolerate duplicates and out-of-order messages, but that is their design,
not something the move guarantees.
