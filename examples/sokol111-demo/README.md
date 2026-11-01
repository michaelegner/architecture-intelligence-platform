# Sokol111 demo — Redpanda to Kafka migration

[Sokol111](https://github.com/Sokol111/ecommerce-workspace) is an open-source, event-driven e-commerce system.

**Scenario:** Catalog Management (Catalog and Image services) moves from Redpanda to Apache Kafka. Which cross-boundary consumer attachments and promises must the team investigate before changing brokers?

## Try it

- **[Try the hosted MCP walkthrough](TRY_IT_HOSTED.md)** — connect a coding agent anonymously to AIP's read-only, frozen **pre-migration** Sokol111 dataset; inspect the binding picture and plan the change. No migration runs on the hosted endpoint.
- **[Read the recorded v0.8 migration showcase](../../docs/release-validation/v0.8.0-release-notes.md)** — a coding agent planned and executed the broker move in a separate controlled run. The evidence records both passing checks and unmet acceptance checks.

AIP distinguishes documented promises, observed broker attachments, and unresolved claims. A captured topic attachment does not by itself establish message delivery, event handling, or the current live state.

## Hosted configuration and verification

The [v0.8 hosted configuration](hosted/config.sokol111-v08.yaml) and
[public-edge acceptance checker](hosted/verify_public_edge.py) belong to Sokol111.
To check the anonymous, read-only hosted MCP endpoint from outside the deployment:

```bash
python examples/sokol111-demo/hosted/verify_public_edge.py --url https://mcp.daip.io/mcp --profile sokol111-v08
```

The default profile is `sokol111-v08`, the current hosted dataset. The checker keeps the
`pitstop` and `sokol111` profiles to reproduce historical acceptance checks.

## Other demo

For the independently runnable .NET/RabbitMQ example, see the [Pitstop demo](../pitstop-demo/README.md).
