# Round 4 — Sokol111 frozen revisions

**Status:** Frozen for Round 4 evaluation  
**Spec:** [spec-round4-finalist-technical-spike.md](spec-round4-finalist-technical-spike.md) §3–§4  
**Frozen:** 2026-10-13 (default branch `master` of each repository, shallow clone, `git rev-parse HEAD`)

| Repository | Role | Commit | Commit date |
|---|---|---|---|
| `Sokol111/ecommerce-catalog-service-api` | `ProductUpdatedEvent` contract | `7cecb3e1131dbd5199ce25e9cf101d75d3365171` | 2026-08-05 |
| `Sokol111/ecommerce-catalog-service` | producer | `e9f147483e6e33ec512851d478169d2985614b09` | 2026-08-05 |
| `Sokol111/ecommerce-product-query-service` | consumer | `b8f5137b9e6fae3bacbe0319e0c23edfd0d25f19` | 2026-08-05 |
| `Sokol111/ecommerce-image-service` | consumer | `f1b97e8402e8183b131847f8a4db8bb00dddb33a` | 2026-08-05 |
| `Sokol111/ecommerce-commons` | shared Kafka/OTel libraries | `d54bf55eba79566286b57b630f5d5b0d68b64302` | 2026-08-05 |
| `Sokol111/ecommerce-infrastructure` | environment topic/consumer config | `07c059908b99e08448cf1c2c7dad6a865fe5ccf0` | 2026-08-06 |
| `Sokol111/ecommerce-workspace` | workspace `AGENTS.md`, `go.work`, `Makefile` (added: baseline context, not in spec §4 list) | `f6b4c1ce723cb3be83eda73d74b2bacb9c584f17` | 2026-08-06 |

The workspace repository is added per spec §4 ("if another repository becomes relevant, add it
rather than withholding it"): its `AGENTS.md` is repository-native agent context.

## Pre-evaluation observations (source reading only; not yet confirmed live)

Recorded before any AIP run so they cannot be shaped by AIP output. They are hypotheses for the
live capture and AIP feasibility steps.

- Topic `catalog.product.events` is consumed by both Product Query (`default-group-id:
  ecommerce-product-query-service`) and Image (`ecommerce-image-service`), in
  `ecommerce-infrastructure/environments/{local,production}/values/*.yaml` and each service's
  `configs/config.standalone.yaml`.
- Hand-written Kafka spans in `ecommerce-commons/pkg/kafka/{consumer/tracing.go,outbox/trace_propagator.go}`
  set `messaging.system=kafka` and the **legacy** `messaging.destination` key, not
  `messaging.destination.name`; they set no consumer-group attribute. If confirmed live, current AIP
  would classify these spans as `no_destination_name` — an **ingestion/attribute-mapping** question
  to classify per spec §8, without changing AIP.
- The documented consumer-group semantics in AIP (`docs/opentelemetry.md`, "Pub/Sub observations")
  leave Kafka consumer attribution unresolved by design — a likely **semantic gap** for the
  Product Query / Image consumer relations.
- The contract is protobuf (`catalog/events/v1/product_events.proto`), not AsyncAPI, so a declared
  Topic would need a declaration source within existing semantics.
- Local live run: the repository's documented dev path is `make run` per service
  (`APP_ENV=standalone`) with Mongo, Kafka and an OIDC/JWKS endpoint; the full environment is
  k3d + Tilt. This host has Docker but no Go toolchain (services require Go 1.26.x), so a minimal
  live slice would build via a Go container image.
