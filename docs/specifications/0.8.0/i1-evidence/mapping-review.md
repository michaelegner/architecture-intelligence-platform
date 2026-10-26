# Service-mapping review (v0.8 I1)

The two mapping artifacts map each consumer group to its declared Service ([I1 spec §7](../i1-declared-side-and-inventory.md#7-mappings)). Their sources:
- **Groups:** `Sokol111/ecommerce-infrastructure@07c059908b99e08448cf1c2c7dad6a865fe5ccf0`, `environments/local/values/<service>.yaml`, `kafka.consumers-config.default-group-id`.
- **Group defaulting:** a consumer without its own `group-id` uses that default (`ecommerce-commons@d54bf55e…`, `pkg/kafka/config/types.go`). No consumer of the four services sets one.

| Group = Service | Values file line (`default-group-id`) | Consumers' topics in that file | Artifacts |
|---|---|---|---|
| `ecommerce-catalog-service` | `ecommerce-catalog-service.yaml:34` | `tenant.tenant.events` | local, kafka |
| `ecommerce-category-query-service` | `ecommerce-category-query-service.yaml:24` | `catalog.category.events`, `catalog.attribute.events`, `tenant.tenant.events` | local |
| `ecommerce-image-service` | `ecommerce-image-service.yaml:26` | `catalog.product.events`, `tenant.tenant.events` | local, kafka |
| `ecommerce-product-query-service` | `ecommerce-product-query-service.yaml:24` | `catalog.product.events`, `catalog.attribute.events`, `tenant.tenant.events` | local |

- The Kafka artifact names only Catalog and Image, the groups that move in wave 1 (parent §4.1). The Helm values that point them to Kafka are written in I3; the group ids do not change.
- Group names are never used as evidence of a Service. The mapping comes from configuration and is independent of the captures.
