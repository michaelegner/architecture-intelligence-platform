I've built the artifact at `binding-picture/index.html` (self-contained HTML) with a verification record in `binding-picture/VERIFICATION.md`. I could not open it in a browser: shell access was denied and no browser was available, so selection, filters and evidence links are reviewed by reading the code only, never clicked.

**Question and boundary.** I used the question you supplied. Catalog Management = `ecommerce-catalog-service` + `ecommerce-image-service`, as your task defines it. No ownership or architecture record in the repos defines it. Environment is local (k3d/Tilt Helm values). Inspected 2026-11-01. There is no runtime capture and no architecture-knowledge provider, so nothing here says a message was actually delivered.

**Sources and revisions** (read from `.git/HEAD`; `git status` not checked):

| Repo | Revision |
|---|---|
| catalog-service | `e9f14748` |
| image-service | `f1b97e84` |
| catalog-service-api | `7cecb3e1` |
| image-service-api | `21679485` |
| tenant-service-api | `d9b90972` |
| commons | `d54bf55e` |
| product-query-service | `b8f5137b` |
| category-query-service | `6cb5373d` |
| tenant-service | `dbeacdbf` |
| infrastructure | `07c05990` |

**Bindings (14):**
- **Outbound:**
  - B1: catalog → product-query on `catalog.product.events` (product updated/deleted).
  - B2: image → product-query, `ProductImagePromotedEvent` on the same topic.
  - B3: catalog → category-query on `catalog.category.events`.
  - B4: catalog → both query services on `catalog.attribute.events`.
- **Inbound:** B5 and B6: tenant-service → catalog and image on `tenant.tenant.events`.
- **Inside the boundary:**
  - B7: catalog → image on `catalog.product.events`, which drives image promote and cleanup.
  - B8: image reads its own promoted events back and skips them.
- **Shared/platform:**
  - B9: broker `redpanda:29092`, Redpanda v24.3.1.
  - B10: topic provisioning (unresolved).
  - B11: dead-letter (DLQ) topics (unresolved).
  - B12: consumer groups and offsets.
  - B13: message headers (unresolved).
  - B14: standalone broker addresses that disagree (unresolved).

**Main insight** (the facts are in the sources; the consequence is my interpretation). Each service has a single `kafka.brokers` setting, used by its producer and all of its consumers (`commons/pkg/kafka/config/types.go:7` and both client constructors). A service can't be split across two clusters by config. Catalog Management can't move to Apache Kafka alone unless it gets `tenant.tenant.events` there (B5/B6), and product-query and category-query either move too or have `catalog.*` mirrored back (B1–B4). Catalog and image also share `catalog.product.events`, so they have to move together.

**Also found:**
- **No retry or DLQ settings on image's `catalog-events` consumer** (B7). It is the only consumer in the local values without them. Defaults then apply: 2 retries, no DLQ. The message is committed whatever the outcome, so promotions that fail during migration could be lost. This is my interpretation from the defaults code.
- **Topics may rely on auto-creation** (B10). The shared producer enables `AllowAutoTopicCreation` (`producer/fxconfig/module.go:35`), and I found no topic definitions. On Apache Kafka that depends on the broker's `auto.create.topics.enable` setting.
- **Standalone configs disagree** (B14). Catalog uses `localhost:9092`, image uses `localhost:29092`, and compose only publishes 9092.

**Not established:**
- Any runtime delivery.
- Who creates topics, and with what partitions and retention.
- The tenant header key name (I didn't find the file that implements it).
- What the no-op DLQ handler actually does.
- Who reads the DLQ topics.
- Production config.
- Kafka use in the UIs and the seeder.
- Whether the target cluster needs TLS/SASL. The shared client shows no such options.

**Checks performed:**
- I checked B1, B5, B7, B10 (unresolved) and B14 (ambiguous) line by line against the sources, including direction.
- Every statement cites a file and line range with a quoted excerpt. A built-in integrity check flags any statement without a reference, but it hasn't been run.
- No provider was used, so there are no provider findings to compare or remove.

To finish the browser checks, follow the steps at the end of `VERIFICATION.md`.
