# Try the hosted demo (Sokol111)

Since v0.7.2 I2 (2026-10-21), the public read-only AIP instance serves a **frozen Sokol111 dataset**.
Before that it served Pitstop, which you can still [run locally](TRY_IT_LOCALLY.md).
[Sokol111](https://github.com/Sokol111/ecommerce-workspace) is a multi-repository Go e-commerce
system that communicates over Kafka. The dataset is one real capture of its local environment
([package](../../docs/specifications/0.7.2/i2-evidence/sokol111/README.md)). It answers which Services
were attached as consumers of the Kafka topic `catalog.product.events` at capture time T. It is not
a view of live Sokol111 traffic.

You need:

- an MCP client that speaks streamable HTTP. Claude Code 2.1.292 or later works.
- the public MCP URL: `https://mcp.daip.io/mcp`. No credentials are required.

## 1. Connect

```bash
claude mcp add --transport http aip-hosted https://mcp.daip.io/mcp
```

Run `/mcp`. `aip-hosted` should be connected with six read-only tools. Ingestion, imports and
other AIP routes are not public.

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

The Pitstop `aip` plugin and its skill target the Pitstop demo; use them with the
[local Pitstop demo](TRY_IT_LOCALLY.md).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/mcp` cannot connect | check the URL is `https://mcp.daip.io/mcp` exactly |
| `421 Invalid Host header` | use `https://mcp.daip.io/mcp` exactly |
| `429 Too Many Requests` | the public rate limit was reached; wait briefly and retry |
| `UNKNOWN_DESTINATION` | use the Topic id above, not the topic name |
