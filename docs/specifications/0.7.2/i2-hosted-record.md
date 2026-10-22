# v0.7.2 I2 — Hosted Sokol111 record

Governing: the [v0.7.2 specification](specification.md) §4. The public read-only AIP instance now serves the frozen
Sokol111 dataset from [I2.1](i2-evidence/sokol111/README.md) (#620) instead of Pitstop. This is a **frozen local Kafka
observation at its capture time**, not live consumption and not a complete view of Sokol111.

## Scenario

- **Brief:** [package README](i2-evidence/sokol111/README.md), "Scenario". A new field in `ProductUpdatedEvent` on
  `catalog.product.events`. The question is which Services consume it, and how sure we can be.
- **Revisions:** [`freeze.md`](i2-evidence/sokol111/freeze.md).
- **Served capture:** **C1** (`2026-10-21T17:53:57Z`, SHA-256 `b46d4ae2…30d8`), with both configured consumers
  attached (owner's decision). C2 stays in the package.

## Hosted switch (owner, 2026-10-21)

The image is unchanged: v0.7.1, `sha256:2f6f2a21…850a47`. The answers report version `0.7.1` and build revision
`b0d7448…`.

| Change | Detail |
|---|---|
| Package | The package was copied to the deployment's `sokol111/` directory: `declarations/`, `mapping/` and `config.yaml`, plus C1 as `kafka/kafka-consumer-state.json`. AIP mounts it read-only at `/app/sokol111` |
| AIP config | `CONFIG_PATH: sokol111/config.yaml`. The first external run was refused with `421` because the new config lacked the public host. The deployment's `mcp:` allow-list block (`mcp.daip.io`) was appended, and the same block is now in the committed [`config.yaml`](i2-evidence/sokol111/config.yaml) |
| Graph | Neo4j uses a new volume, `neo4j_sokol111_data`. The Pitstop graph volume is kept untouched for rollback |
| Pitstop | The Pitstop services, the traffic generator and the Collector are stopped, not removed |
| Edge | Caddy and its configuration are unchanged |
| Import | One `POST /api/import` from inside the deployment, `committed: true`. A second import was also `committed: true` and left the answer byte-identical (snapshot `aip:snapshot:v1:a08b1bad…`) |

The compose change is four lines: `CONFIG_PATH`, the `./sokol111` mount, the Neo4j volume line, and the new volume
declaration. A backup of the previous compose file is kept on the server.

## External check

The check was run with `verify_public_edge.py --url https://mcp.daip.io/mcp --profile sokol111`, from outside the
deployment, without credentials. The rate-limit check was not enforced (no threshold given).

| Check | Before (18:37:17Z, Pitstop) | After (18:50:44Z, Sokol111) |
|---|---|---|
| anonymous initialize | PASS | PASS |
| tool inventory | PASS (6 tools) | PASS (6 tools) |
| Sokol111 consumers + evidence drill-down | **FAIL** (`UNKNOWN_DESTINATION`) | PASS: T `2026-10-21T17:53:57Z`; `RESOLVED` `service:ecommerce-image-service` and `service:ecommerce-product-query-service`; 4 refs resolved on the same snapshot |
| source-dependent tools refuse | PASS | PASS: `get_api_consumer_usage` `MEASUREMENT_WINDOW_NOT_AVAILABLE` (no gateway source); unknown Topic `UNKNOWN_DESTINATION` |
| non-MCP routes closed, invalid Host, oversized body | PASS | PASS (10 routes; empty 200; 413) |
| rate limit | SKIPPED | SKIPPED |

The full hosted query answer matches the frozen [`expected.json`](i2-evidence/sokol111/expected.json) for C1:
- **Rows:** the same two rows and outcomes.
- **Limitations:** only `CAPTURE_SCOPE_LIMITED`.
- **Leaks:** the catalog and category-query groups are not named, and neither are any member ids or hosts.
- **`capture_sources`:** the one capture, at T.

## Effort

| Step | Effort |
|---|---|
| Setup | About 40 minutes for the I2.1 capture, including three host adaptations ([README](i2-evidence/sokol111/README.md)) |
| Hosted switch | About 15 minutes of owner commands, including the one `421` fix |
| Refresh | Copy another frozen capture over `kafka/kafka-consumer-state.json`, then import once. Nothing else changes |

## Docs

`examples/pitstop-demo/TRY_IT_HOSTED.md` now describes the hosted Sokol111 dataset:
- how to connect;
- the exact Topic id;
- what the answer says, and what it does not.

The Pitstop demo, its Claude Code plugin and the mod are the local path (`TRY_IT_LOCALLY.md`). The README, the
Pitstop README, `docs/mcp.md` and `docs/security-model.md` no longer call the hosted instance Pitstop.
