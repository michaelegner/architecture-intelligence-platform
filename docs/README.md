# Documentation index

Start with the product scope and current architecture, then follow the relevant topic.
These documents describe different boundaries; research notes are not release commitments.

## Orientation

- [Product doctrine and strategic direction](product-doctrine-and-strategic-direction.md) — Product positioning, governing principles, and strategic direction.
- [Architecture](architecture.md) — System components, staged ingestion and the public API surface.
- [Research landscape](landscape.md) — Curated adjacent concepts and standards; research, not endorsed dependencies or roadmap commitments.

## Architecture model and semantics

- [Canonical model](canonical-model.md) — Shared entities and relations mapped from declared and observed sources before persistence.
- [Graph model](graph-model.md) — Neo4j node and relation shapes, including public and internal graph boundaries.
- [Evidence and provenance](evidence.md) — How architecture facts carry source identity and traceable evidence.
- [Ingestion and source adapters](ingestion.md) — Declared-document and Kubernetes discovery mapping into the canonical model.
- [Semantic gaps and boundaries](semantic-gaps.md) — Working register of observed or candidate semantic limitations, separate from release commitments.
- [Natural-language query and semantic validation](semantic-validation.md) — Deterministic analysis routing, guarded Cypher generation, and read-only execution.

## Use and operate AIP

- [Configuration](configuration.md) — YAML and environment-based settings, with secrets restricted to the environment.
- [Analyses](analyses.md) — Fixed, parameterized Cypher architecture analyses.
- [MCP tools](mcp.md) — Public, read-only tools for agent clients and the standard MCP adapter boundary.
- [OpenTelemetry](opentelemetry.md) — Runtime observation ingestion and its failure-isolation contract.

## Develop and extend

- [Development](development.md) — Local setup, test commands, linting and contributor workflows.
- [Adapter development](adapter-development.md) — Interfaces and evidence rules for new declared sources and runtime observation adapters.

## Security

- [Security model](security-model.md) — Trust boundaries for queries, graph reachability and runtime ingestion.

## Decisions and release specifications

- [Architecture decision records](adr/) — Recorded architecture decisions, rationale and change history.
- [Specification index](specifications/README.md) — Release-specific specifications and historical design inputs; consult [the roadmap](../ROADMAP.md) for shipped versus planned work.
