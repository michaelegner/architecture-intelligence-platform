# Round 4 — Sokol111 coding-agent/source baseline

**Spec:** [spec-round4-finalist-technical-spike.md](spec-round4-finalist-technical-spike.md) §5  
**Frozen revisions:** [round4-sokol111-freeze.md](round4-sokol111-freeze.md)  
**Run:** 2026-10-13, one fresh non-interactive Claude Code session (`claude -p`, tools restricted to
`Read,Grep,Glob`, working directory containing only the seven frozen checkouts, no files modified).

## Prompt (verbatim)

> You are working in a multi-repo workspace (all repositories are checked out in this directory). Task: a developer wants to add a new field to ProductUpdatedEvent (defined in ecommerce-catalog-service-api). Before any change is made, investigate and report: (1) which services/repositories you chose to inspect and why; (2) which distributed relationships (who produces, who consumes, over which topic/consumer group, in which environments) you consider ESTABLISHED, and the exact source/config evidence (file paths) for each; (3) which relationships remain INFERRED or UNCERTAIN and why; (4) what you would change or check in each affected repository. Do not modify any files. Be concise and structured.

## Fairness notes

- All six §4 repositories plus the workspace repository, with their `AGENTS.md`, configs, infra values and contracts, were available. Nothing was withheld.
- **Contamination disclosure:** the session inherited the owner's user-level Claude Code configuration, so an AIP plugin skill and the AIP `get_service_dependencies` tool were visible to it. The skill errored and the tool call was denied, so **no AIP evidence entered the result**. The agent also mentioned a Redpanda MCP config in the workspace and did not use it. A rerun with plugins disabled is not needed for this conclusion but would be required if the baseline were ever used as a qualifying v0.8 control.
- One agent, one run. Not repeated.

## Result (agent output, verbatim)

Nothing was modified. One caveat on method: the `aip:architecture-aware-development` skill errored, and the AIP `get_service_dependencies` call was denied for lack of permission. Everything below comes from reading source and config, not from runtime or observed evidence.

## 1. Repositories inspected and why
- **`ecommerce-catalog-service-api`** defines the event: `proto/catalog/events/v1/product_events.proto`, the generated code under `gen/go`, and `pkg/events/topics.go`.
- **`ecommerce-catalog-service`** is the producer. I found it by grepping for `ProductUpdatedEvent` and `TopicFor`.
- **`ecommerce-product-query-service`** and **`ecommerce-image-service`** each import the event type and register a `HandleProductUpdated` handler.
- **`ecommerce-infrastructure`** holds the per-environment deployment configs (`environments/local`, `environments/production`). These are the only source for topics, groups and environments in deployment.
- **`ecommerce-commons`** holds the Kafka consumer and outbox plumbing, which explains how the group ID is defaulted.
- **`ecommerce-workspace`** holds architecture docs. I treated them as a secondary source only.

I did not inspect the UIs or `ecommerce-category-query-service`. The category-query service is not checked out here, and the grep for `ProductUpdatedEvent` and the topic name found no consumer in `ecommerce-infrastructure/environments/*/values/ecommerce-category-query-service.yaml`.

## 2. Established relationships

| Relationship | Evidence |
|---|---|
| Schema owner and topic: `ProductUpdatedEvent` goes to `catalog.product.events` (shared with `ProductDeletedEvent`) | `ecommerce-catalog-service-api/proto/catalog/events/v1/product_events.proto` (message with fields 1–12); `ecommerce-catalog-service-api/pkg/events/topics.go` (`topicMap`) |
| **Producer: `ecommerce-catalog-service`**, via the transactional outbox in `create_product.go:76` and `update_product.go:159`. The topic comes from `apiEvents.TopicFor(event)`. | `ecommerce-catalog-service/internal/infrastructure/outbound/kafka/product_event_factory.go` (lines 50–72); `ecommerce-commons/pkg/kafka/outbox/sender.go` |
| **Consumer: `ecommerce-product-query-service`**. Group `ecommerce-product-query-service`, consumer name `catalog-events`, topic `catalog.product.events`. Retries and DLQ are enabled in production. | Local: `ecommerce-infrastructure/environments/local/values/ecommerce-product-query-service.yaml`. Production: `ecommerce-infrastructure/environments/production/values/ecommerce-product-query-service.yaml`. Also `ecommerce-product-query-service/configs/config.standalone.yaml`. Handler: `ecommerce-product-query-service/internal/infrastructure/inbound/kafka/product_handler.go` and `.../fxconfig/module.go`. |
| **Consumer: `ecommerce-image-service`**. Group `ecommerce-image-service`, topic `catalog.product.events`. | `ecommerce-infrastructure/environments/{local,production}/values/ecommerce-image-service.yaml`; `ecommerce-image-service/configs/config.standalone.yaml`; handler `ecommerce-image-service/internal/infrastructure/inbound/kafka/product_handler.go` |
| Environments: local (k3d), production, and standalone dev configs | The `environments/` tree above |
| Group ID defaulting: a consumer with no `group-id` gets `default-group-id` | `ecommerce-commons/pkg/kafka/config/defaults.go:55`. Each consumer's actual group is therefore its service's `default-group-id`, since neither service's `catalog-events` consumer sets its own. |
| Which fields each consumer reads: `product-query` reads all fields (id, version, name, description, price, quantity, image_id, category_id, enabled, timestamps, attributes). `image-service` reads only `ProductId` and `ImageId`. | The two handler files above |
| Version pins: `catalog-service` pins api v1.3.8. `product-query` and `image-service` pin v1.3.6. `ecommerce-infrastructure/cmd/seeder` pins v1.3.4, but it only uses the RPC types. | The `go.mod` files |

## 3. Inferred or uncertain
- **Runtime reality is not verified.** Whether consumers are running, their lag, and whether the production brokers actually carry the traffic are unchecked. The AIP query was denied, and the workspace has Redpanda MCP configs (`ecommerce-workspace/.opencode/opencode.json`) that I did not use.
- **Other consumers outside this checkout.** The grep found none in what is checked out. Candidates are `ecommerce-category-query-service` (its config subscribes to the category, attribute and tenant topics, not the product topic), the storefront and admin UIs, and the Grafana and k8s manifests. I cannot rule out a consumer elsewhere, such as an analytics job, a search indexer, or a direct subscriber to the topic.
- **Production "published" status.** The producer side of production is inferred from code. There is no producer config for it. The catalog-service values files contain only a tenant consumer. Redpanda has `auto_create_topics_enabled`.
- **`image-service` is also a producer** of `ProductImagePromoted`, which `product-query` consumes (this comes from the workspace doc `ecommerce-workspace/docs/architecture/product-update-flow.md`, which I did not cross-check in code). It is downstream, so a new field does not break it directly.
- **Deployed versions.** I don't know which version of each service runs in each environment. I only know the `go.mod` pins. In local dev, `ecommerce-workspace/go.work` resolves the api repo directly, so a change shows up in consumers immediately without a release.
- **Schema registry or buf breaking checks.** I found no registry. The CI breaking check is described only in `ecommerce-catalog-service-api/AGENTS.md`, not verified.

## 4. What I would change or check, per repo
- **`ecommerce-catalog-service-api`**:
  - Add the field to `ProductUpdatedEvent` with the next free number, 13, as an additive change (use `optional` if "absent" must differ from the zero value). Never renumber or reuse numbers.
  - Run `make generate`, then `make connect-breaking`. `make lint` runs as part of generate.
  - Do not edit `gen/` by hand.
  - `topicMap` needs no change, since the message already exists.
  - Read the `AGENTS.md` rule that events carry immutable references and values, not mutable display data. Check that the new field complies.
  - Releasing means bumping `VERSION`, which triggers the release workflow and tags the module.
- **`ecommerce-catalog-service`**:
  - Populate the field in `newProductUpdatedEvent` (`product_event_factory.go`), which implies a domain-model field on `product.Product` and probably persistence and RPC changes.
  - Both create and update go through this factory.
  - Extend the factory tests.
  - Bump the api dependency.
  - Decide how events behave for existing products.
- **`ecommerce-product-query-service`**:
  - Optional, but needed if the read model should store or expose the field. That means `NewProductView` and the upsert (including the Mongo projection), and possibly the query API and its DTOs.
  - Bump the api dependency to the released version.
  - Old events still decode fine, so the handler must tolerate the field being absent (version-based upserts handle replays).
  - Check what a replay or the `earliest` offset does.
- **`ecommerce-image-service`**: no change is needed because it only reads `ImageId` and `ProductId`. Bump the api dependency only if you want it current, and confirm its tests still pass against the new generated code.
- **`ecommerce-infrastructure`**: no config change is needed for an additive field. The topic and groups stay the same. Optionally bump the seeder's api pin (v1.3.4, RPC only). Check that no environment pins an old image of a consumer that would fail on the field (proto3 ignores unknown fields, so it should not).
- **`ecommerce-commons`**: no change.
- **Rollout order**: release the api first, then deploy the consumers (they tolerate absence), and deploy the producer last. Run a final check with Redpanda MCP or AIP to confirm there are no other consumers before changing semantics.

## Assessment

The baseline is **strong**. From source and infra values alone it established: the event and topic
(`catalog.product.events`), the producer (Catalog, via outbox), both consumers (Product Query,
Image), their consumer groups, the environments (local, production, standalone), and which fields
each consumer reads. It correctly bounded the change (Image needs no change; Product Query only if
the read model should expose the field).

What it explicitly could **not** settle (candidate questions for independent evidence):
1. whether consumers are actually running/consuming in an environment, and whether other consumers exist outside the checkout;
2. which service versions are deployed per environment (only `go.mod` pins are known);
3. the producer side in production (no producer config in infra values).

Whether independent evidence can answer these *and* current AIP can represent the answer is assessed
in the feasibility step.
