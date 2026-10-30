# Architecture Intelligence Platform

[![CI](https://github.com/michaelegner/architecture-intelligence-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/michaelegner/architecture-intelligence-platform/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Understand the relationships across your system's boundaries before changing them.**

In a distributed system, a service's dependencies are spread across API contracts, event
declarations, configuration, runtime evidence, and other teams' knowledge. No single repository
or diagram necessarily shows the complete picture.

**AIP** combines attributable architectural promises with independently qualified evidence to
show **who relies on what, across which boundary, what is established, and what remains unresolved**.
Architects, engineering teams, and coding agents can inspect the same snapshot-bound answers.

**[Try the hosted MCP demo](#try-aip) · [See the binding picture](#the-binding-picture) ·
[Explore the technical documentation](#documentation)**

## What is AIP?

AIP addresses a practical question before a team changes or moves a capability:

> Which relationships cross this boundary, what do the participating services promise,
> and what does the available evidence actually establish?

AIP separates three things that architecture descriptions often blur:

- **Current State:** relationships supported by observations and other applicable evidence,
  qualified by environment, capture scope, identity, and time.
- **Intent:** attributable promises made by participating systems or their owners.
- **Assessment:** a bounded comparison of relevant promises with what the evidence establishes,
  including explicit uncertainty.

It does not infer service ownership from traffic, turn missing observations into proof of absence,
or make an agent's plausible explanation authoritative. Its purpose is to supply defensible
architectural premises for a concrete question—not to own a complete enterprise architecture
model or perform the change itself.

## The binding picture

The [v0.8.0 showcase](docs/release-validation/v0.8.0-release-notes.md) uses
[Sokol111](https://github.com/Sokol111/ecommerce-workspace), a distributed e-commerce system.
The proposed change moves **Catalog Management** from Redpanda to Apache Kafka.
Before planning that move, which consumers and event dependencies must be examined?

The documented architecture describes some of the relationships. A frozen broker capture also
establishes consumer-group attachments that the documents do not describe. AIP evaluates the
attachments against the defined Catalog Management boundary and a generated EventCatalog.

| Frozen v0.8 C1 result | What it means |
|---|---|
| **2 `PROMISED_AND_OBSERVED`** bindings on `catalog.product.events` | The demo's assumed-confirmed promises and captured consumer attachments agree. |
| **7 `UNRESOLVED`** bindings | Consumer attachments are evidenced, but promise coverage is missing (`PROMISE_COVERAGE_MISSING`). |
| **Boundary classifications** | The nine rows distinguish `INBOUND`, `OUTBOUND`, `INSIDE`, and `NONE` relative to the selected context. |

The answer is **`PARTIAL`**, not a claim that the whole system has been discovered.
Each row is connected to evidence that can be retrieved against the same snapshot.

The [showcase report](docs/specifications/0.8.0/i4-evidence/report.html) follows the
migration through the before/after broker captures. The [frozen evidence package](docs/specifications/0.8.0/i1-evidence/README.md)
shows which inputs are captured, authored, or generated.

**Important:** The EventCatalog is generated from the project's documents; treating its entries
as confirmed owner promises is an explicit *demonstration assumption*. Consumer attachment is not
event handling or end-to-end delivery. This is a technical demonstration, not proof that AIP
improves migration-planning quality.

## Try AIP

### Hosted MCP demo — no installation or credentials

The public, read-only endpoint serves the frozen **v0.8.0 Sokol111 C1** dataset, not live
monitoring. It exposes seven tools, including the experimental `get_binding_picture`:

```bash
claude mcp add --transport http aip-hosted https://mcp.daip.io/mcp
```

In Claude Code, check `/mcp` and ask:

> Which bindings cross the Catalog Management boundary in environment `local` on
> broker `kafka:sokol111-local`? Show which are promised and observed, which remain
> unresolved, and resolve the relevant evidence at the same snapshot.

Use `get_binding_picture` with `bounded_context_id: catalog-management` and
`broker_ids: [kafka:sokol111-local]`. See the [hosted walkthrough](examples/pitstop-demo/TRY_IT_HOSTED.md)
for the exact request, expected findings, limitations, and troubleshooting.

### Quick Start — run a local example

For an introductory, deterministic declared-versus-observed demo, install Docker with Compose,
plus `curl` and `jq`. No LLM API key is needed:

```bash
git clone https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform
cp .env.example .env
examples/runtime-demo/mcp-demo.sh
```

This separate example demonstrates `get_architecture_drift` and `get_evidence`.
Clean up with `examples/runtime-demo/mcp-demo.sh --down`.
For the full platform, see the [development guide](docs/development.md).

Other real-system examples: [Pitstop (.NET/RabbitMQ)](examples/pitstop-demo/README.md) and
[Quarkus Super Heroes](examples/quarkus-super-heroes-demo/README.md).
The [MCP client setup guide](examples/mcp-clients/README.md) covers Codex, Claude Code,
Cursor, and VS Code; previous end-to-end client qualification was performed against v0.4.2,
not re-qualified for v0.8.0.

## How AIP works

AIP makes *bounded, evidence-qualified answers* from distinct sources, rather than collapsing
every input into one unquestionable architecture description.

```text
OpenAPI / AsyncAPI / mappings ───┐
Runtime traces / broker capture ─┼──> qualified Current State ─┐
                                 │                             │
EventCatalog / owner promises ───┴──> attributable Intent ─────┼──> bounded Assessment
Declared context membership ───────────────────────────────────┘      │
                                                                        v
                                                           read-only MCP / REST
                                                           + snapshot-bound evidence
```

The core is a deterministic architecture service backed by Neo4j. The MCP tools and REST APIs
provide read-only access to its qualified results. **Six MCP tools are enabled by default**;
`get_binding_picture` is an **experimental seventh tool** behind
`architecture_intelligence.experimental.binding-picture: true` (enabled on the hosted demo).
No model or LLM key is needed to produce these answers.

### Declared vs observed

For direct dependency/drift answers, AIP retains these distinctions:

| Qualification | Meaning |
|---|---|
| `CONFIRMED` | Declared and observed in the relevant context. |
| `OBSERVED_ONLY` | Observed but not declared in the ingested sources. |
| `NOT_OBSERVED_IN_WINDOW` | Declared but not observed in the specified window—not proof it is absent or unused. |

These older dependency qualifications are **not** the same as the experimental v0.8
binding-picture assessment statuses.

**Boundaries matter:** A frozen broker capture establishes a group's topic attachment at capture
time, not the event types a service handles; producer declarations are not observed production;
an absent promise is not a proven violation; and the two-broker picture does not establish
cross-broker delivery. AIP keeps these limits explicit in its answers.

The public hosted endpoint is a **constrained demo** behind an HTTP edge; the AIP MCP server itself
is not a general authenticated, multi-tenant public service. Keep self-hosted MCP access local or
on a trusted network. See the [security model](docs/security-model.md).

## Documentation

| Explore | Reference |
|---|---|
| MCP tools, schemas, and evidence drill-down | [MCP reference](docs/mcp.md) |
| Architecture, ingestion, configuration, and local development | [Architecture](docs/architecture.md) · [Configuration](docs/configuration.md) · [Development](docs/development.md) |
| v0.8 release, showcase, and hosted deployment | [Release notes](docs/release-validation/v0.8.0-release-notes.md) · [Showcase evidence](docs/specifications/0.8.0/i4-evidence/README.md) · [Hosted record](docs/release-validation/v0.8.0-hosted-record.md) |
| Product thinking and next steps | [Product doctrine](docs/product-doctrine-and-strategic-direction.md) · [Roadmap](ROADMAP.md) |
| Source, evaluation, and independent findings | [Evaluation](evaluation/README.md) · [v0.8 comparison](docs/specifications/evaluation/v08-showcase-value-qualification-result.md) |
| Contribute or report an issue | [Contributing](CONTRIBUTING.md) · [Discussions](https://github.com/michaelegner/architecture-intelligence-platform/discussions) · [Security reports](SECURITY.md) |

**Current status:** [v0.8.0](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.8.0)
is a shipped **demonstration release**. The binding-picture contract remains experimental.
In a controlled 12-session comparison, AIP reduced information requests in the team-scoped
setting, but did not show a robust improvement in migration-planning quality. Real customer value
and the effort of maintaining attributable promises remain to be validated.

Apache-2.0 licensed. See [LICENSE](LICENSE) and [third-party licenses](THIRD_PARTY_LICENSES.md).
