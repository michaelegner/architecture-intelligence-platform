# Try the hosted demo (Sokol111)

Since v0.7.2 I2 (2026-10-21), the public read-only AIP instance serves a **frozen Sokol111 dataset**.
Before that it served Pitstop, which you can still [run locally](TRY_IT_LOCALLY.md).
[Sokol111](https://github.com/Sokol111/ecommerce-workspace) is a multi-repository Go e-commerce
system that communicates over Kafka. Since v0.8.0, the instance serves the v0.8 package
([package](../../docs/specifications/0.8.0/i1-evidence/README.md)):
- one real capture of the local environment's consumer groups, at capture time T;
- authored declarations of the Services and the Topics they produce;
- a generated EventCatalog with the documented promises of each Service.

It answers two questions: which Services were attached as consumers of a Kafka topic at T, and which
bindings cross the Catalog Management boundary. It is not a view of live Sokol111 traffic.

You need:

- an MCP client that speaks streamable HTTP. Claude Code 2.1.292 or later works.
- the public MCP URL: `https://mcp.daip.io/mcp`. No credentials are required.

## 1. Connect

```bash
claude mcp add --transport http aip-hosted https://mcp.daip.io/mcp
```

Run `/mcp`. `aip-hosted` should be connected with seven read-only tools: the six default tools and
the experimental `get_binding_picture`. Ingestion, imports and other AIP routes are not public.

## 2. Ask about the Kafka topic

`get_destination_consumers` needs the exact Topic id; no tool looks it up by name:

```text
broker_id:   kafka:sokol111-local
environment: local
Topic id of catalog.product.events: topic:owned:5534005a20357fa91c86e22e83f557c20a0be39302067e509fa59c85eb034539
```

Ask, for example: *"Which Services consume `catalog.product.events`, and how sure can we be?"*

The answer is `PARTIAL` with `CAPTURE_SCOPE_LIMITED`. Two consumer groups are attached at
T `2026-10-21T17:53:57Z`, each `RESOLVED` to a declared Service through explicit mapping evidence:
`ecommerce-product-query-service` and `ecommerce-image-service`. The evidence mode of the same tool
resolves the answer's refs at its snapshot.

What the answer does not say:
- that these Services consume now;
- that they process every message;
- that no other consumer exists.

A capture covers only its configured groups at its own T. To plan a change against the source, clone the
revisions in the package's [`freeze.md`](../../docs/specifications/0.7.2/i2-evidence/sokol111/freeze.md).

## 3. Ask about the Catalog Management boundary

`get_binding_picture` compares the documented promises with the captured consumers for one bounded
context:

```text
bounded_context_id: catalog-management
environment:        local
broker_ids:         [kafka:sokol111-local]
```

Ask, for example: *"Which bindings cross the Catalog Management boundary, what is promised, what was
observed, and what is unresolved?"*

The answer is `PARTIAL` with nine rows, one for each consumer Service and Topic:
- **2 rows `PROMISED_AND_OBSERVED`** on `catalog.product.events`: `ecommerce-product-query-service`
  (`OUTBOUND`) and `ecommerce-image-service` (`INSIDE`). A promise documents the binding, and a
  consumer group attached at T resolves to the Service.
- **7 rows `UNRESOLVED` with `PROMISE_COVERAGE_MISSING`**: a consumer group attached at T resolves
  to the Service, but no promise documents the binding. They are on `tenant.tenant.events`, `catalog.category.events`
  and `catalog.attribute.events`.

The evidence mode of the same tool resolves the answer's refs at its snapshot.

The tool is **experimental** (`experimental.binding-picture`). The answer has four limitations,
and each one says what the answer does not establish:

| Limitation | Meaning |
|---|---|
| `PROMISES_ASSUMED_CONFIRMED` | The catalog entries count as confirmed promises by a demonstration assumption. The owners in the catalog are illustrative |
| `PRODUCER_SIDE_DECLARED_ONLY` | Producers come from the declarations. No producer traffic was observed |
| `EVENT_HANDLING_NOT_ESTABLISHED` | An attachment shows a consumer group's topic assignment, not which event types the Service handles |
| `CAPTURE_SCOPE_LIMITED` | The capture covers only its configured groups at its own T. It is not live monitoring |

The answer describes the boundary. It does not plan a migration, and it is not evidence that a
migration plan made with it is more correct.

The Pitstop `aip` plugin and its skill target the Pitstop demo; use them with the
[local Pitstop demo](TRY_IT_LOCALLY.md).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/mcp` cannot connect | check the URL is `https://mcp.daip.io/mcp` exactly |
| `421 Invalid Host header` | use `https://mcp.daip.io/mcp` exactly |
| `429 Too Many Requests` | the public rate limit was reached; wait briefly and retry |
| `UNKNOWN_DESTINATION` | use the Topic id above, not the topic name |
| `get_binding_picture` is missing | reconnect; the hosted instance lists it since v0.8.0 |
