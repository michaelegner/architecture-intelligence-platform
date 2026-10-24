# Service-mapping review (v0.7.2 I2.1)

[`mapping/kafka-service-mapping.json`](mapping/kafka-service-mapping.json) maps the two consumer groups that the configuration names on `catalog.product.events` to their declared Services. Its sources:
- **Groups:** `ecommerce-infrastructure@07c059908b99e08448cf1c2c7dad6a865fe5ccf0`, `environments/local/values/ecommerce-image-service.yaml` and `ecommerce-product-query-service.yaml`, `kafka.consumers-config.default-group-id`.
- **Group defaulting:** a consumer without its own `group-id` uses that default (`ecommerce-commons@d54bf55e…`, `pkg/kafka/config/types.go`). Neither `catalog-events` consumer sets one.

| Group | Service | Evidence |
|---|---|---|
| `ecommerce-image-service` | `ecommerce-image-service` | `values/ecommerce-image-service.yaml` `default-group-id`, consumer `catalog-events` on `catalog.product.events` |
| `ecommerce-product-query-service` | `ecommerce-product-query-service` | `values/ecommerce-product-query-service.yaml` `default-group-id`, consumer `catalog-events` on `catalog.product.events` |

Out of scope:
- The catalog and category-query groups are allow-listed in the capture but consume other topics. They are not mapped, because no declared Topic of this package is attached to them.
- Group names are never used as evidence of a Service. The mapping comes from configuration and is independent of the captures.
