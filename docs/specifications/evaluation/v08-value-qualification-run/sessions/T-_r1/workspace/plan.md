# Moving Catalog Management from Redpanda to Apache Kafka: plan rationale

## What moves, and the boundary

`ecommerce-catalog-service` and `ecommerce-image-service` move to Kafka (`kafka:29092`). Tenant,
product-query and category-query services stay on Redpanda. The boundary is the broker line. A
consumer × topic binding crosses it when its producer and its consumer end up on different brokers.

## Who produces what (source)

| Topic | Producers | Side after move |
|---|---|---|
| `catalog.product.events` | catalog-service (ProductUpdated/Deleted), image-service (ProductImagePromoted) | Kafka |
| `catalog.category.events` | catalog-service | Kafka |
| `catalog.attribute.events` | catalog-service | Kafka |
| `tenant.tenant.events` | tenant-service | Redpanda |

Sources: `ecommerce-catalog-service-api/pkg/events/topics.go:11-21`,
`ecommerce-image-service-api/pkg/events/topics.go:16`,
`ecommerce-tenant-service/internal/infrastructure/outbound/kafka/event_factory.go:30-40`.
The query services produce nothing in their source.

## Bindings that cross the boundary (source + R1 consumer groups)

| Consumer | Topic | Direction | Documented | Observed |
|---|---|---|---|---|
| product-query | catalog.product.events | outbound | yes (product-update-flow.md) | yes |
| product-query | catalog.attribute.events | outbound | no | yes |
| category-query | catalog.category.events | outbound | cannot tell (merged node in platform-overview.md) | yes |
| category-query | catalog.attribute.events | outbound | no | yes |
| catalog-service | tenant.tenant.events | inbound | no | yes |
| image-service | tenant.tenant.events | inbound | no | yes |

Not crossing:
- image-service on `catalog.product.events`: producer and consumer both move.
- The query services on `tenant.tenant.events`: both ends stay on Redpanda.

The attribute bindings and both tenant bindings are in no document. Planning from the docs alone would have missed four of the six bindings.

## Mirror flows

Two MirrorMaker 2 flows in one dedicated MM2 process, with disjoint allow-lists:

- **redpanda → kafka:** `tenant.tenant.events`
- **kafka → redpanda:** `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events`

No topic is mirrored both ways.

**Topic names stay the same.** `IdentityReplicationPolicy` keeps them, so no consumer config changes. This policy disables MM2's cycle detection, so the disjoint allow-lists are the only protection against loops. P03 checks them explicitly.

**MM2 settings and why:**
- Checkpoints, group-offset sync, heartbeats, and topic-config/ACL sync are off. MM2 then never writes consumer groups or changes configs on Redpanda.
- `offset-syncs.topic.location=target`, so MM2 creates no offset-syncs topic on the source of the redpanda→kafka flow.

## Ordering of the cutover, and why

1. **Baseline (P00–P01).**
   - Record topics and groups on both brokers, so that cleanup can later remove only what this plan created.
   - The Helm values were not available (R5). The execution session must read them first. It must stop if group IDs or topics differ from R1. Note that the repo's e2e config uses another group ID than the running service.
2. **Pre-create the four topics on Kafka (P02).**
   - Same partition counts and cleanup policy as on Redpanda, so MM2 keeps each record in the same partition and order.
   - Without this, the producers' `AllowAutoTopicCreation` would create topics with broker defaults.
3. **Start MM2 before the services switch (P03–P05).**
   - Verify that the Kafka `tenant.tenant.events` matches Redpanda: log start 0 and the same end offset.
   - The kafka→redpanda flow starts on empty topics. Kafka must hold nothing except what the moved services write. Otherwise MM2 would copy duplicates into the Redpanda topics that the query services read.
4. **Stop catalog-service, drain image-service, then stop it (P06–P07).**
   - Catalog-service produces into its own team's image-service, so it stops first. Image-service is stopped only once its Redpanda lag on `catalog.product.events` is 0.
   - Outbox entries that were not yet sent are relayed after restart, now to Kafka, and are mirrored back.
5. **Prove no one else writes catalog.\* on Redpanda (P08).**
   - Consumer groups do not show producers. So while both services are down, the Redpanda end offsets must not move.
6. **Seed the Kafka group offsets (P09).**
   - On `tenant.tenant.events`, both moved groups start at their Redpanda committed offset, which maps one-to-one only because both logs start at 0 and have the same end. If they don't match, stop. Replaying a `TenantDeleted` would trigger destructive cleanup, including the image tenant's S3 prefix.
   - Image-service starts at 0 on the new, empty Kafka `catalog.product.events`.
7. **Switch `kafka.brokers` for the two services only, via `helm upgrade` (P10).** Tilt is not used.
8. **Verify (P11–P13).**
   - Kafka-side groups are Stable with lag 0.
   - Redpanda catalog topics grow, and the query-service groups advance back to lag 0.
   - A tenant event crosses to Kafka.
   - Then the functional test: `OPERATOR: please run the functional test`. Any failed check means stop and report.

## Limits

- **No lossless or exactly-once claim.** MM2 delivers at least once: after a restart, records can arrive twice on Redpanda. The query services drop stale versions (`version < event.Version`), but this was not tested here. The mirror also adds latency, and two topics can lag differently.
- **R1 is one snapshot.** Idle consumers are not visible in it, and it shows no producers. P08 and the re-run in P00 cover this.
- **Helm values unseen (R5).** The values file paths and the `kafka.brokers` key in P01/P10 are assumptions that must be confirmed.
- **Rollback after P10 is not clean.** Mirrored records already sit in the Redpanda topics, so switching back would make image-service re-read them. The plan therefore stops and reports instead of improvising.
- **Cleanup.** Only the objects recorded as created get removed: the four Kafka topics, the two Kafka groups, the MM2 `mm2-*` internal topics and the `mm2-catalog` container. Each name is checked against the record first. The old Redpanda groups of the moved services were not created by this plan and are left alone.
