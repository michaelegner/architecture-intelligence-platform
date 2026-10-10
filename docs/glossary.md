# Architecture glossary

These are short pointers to AIP's existing documented contracts, not new definitions or a
substitute for the governing product doctrine, roadmap or release specifications.

- **Architecture Knowledge Graph** — The Neo4j representation built from declared
  architecture and optional qualified runtime observations. It answers bounded
  architectural questions with traceable evidence rather than invented links.
  See [Architecture](architecture.md).
- **Canonical Model** — The source-neutral collection of services, operations,
  messaging entities, schemas, relations and provenance that adapters produce
  before graph persistence. See [Canonical Model](canonical-model.md).
- **Declared evidence** — Evidence from OpenAPI, AsyncAPI or an Architecture
  Manifest describing what the architecture intends to provide, not proof
  that a runtime interaction happened. See [Evidence and provenance](evidence.md).
- **DEPLOYED_AS** — A Service-to-Kubernetes-Workload claim computed at query
  time when independent reconciliation paths agree; it is **not** a stored
  Neo4j edge or a general inference from matching names.
  See [Graph model](graph-model.md).
- **Deterministic analysis** — A fixed, parameterized Cypher query for a
  defined architecture question (for example, queue senders or blast radius);
  no LLM determines the analysis outcome. See [Analyses](analyses.md).
- **Drift** — A dependency surfaced as a declared-versus-observed
  discrepancy such as `OBSERVED_ONLY` or `NOT_OBSERVED_IN_WINDOW`, scoped to
  the evidence and observation window; it is not proof of complete runtime
  visibility. See [MCP tools](mcp.md).
- **Evidence** — The source-backed support for an architecture fact, identified
  by references on relations and resolvable to provenance within allowed
  exposure boundaries. See [Evidence and provenance](evidence.md).
- **Infrastructure entity** — A Kubernetes-derived internal-only workload,
  pod, network service or ingress identity; its internal representation is
  not an ordinary public architecture entity.
  See [Canonical Model](canonical-model.md).
- **Observed evidence** — Bounded runtime facts derived from OpenTelemetry
  traces, with context such as environment, observation window and counts.
  Observed does not mean a business outcome was achieved.
  See [OpenTelemetry](opentelemetry.md).
- **Provenance** — The attributable source information carried with a fact,
  including source type and file, optional revision, and declared/observed
  evidence type. See [Evidence and provenance](evidence.md).
- **Qualification** — The evidence-aware classification of an architecture
  answer in its declared/observed and observation-context boundaries;
  unsupported facts remain limitations rather than being silently promoted.
  See [MCP tools](mcp.md).
- **Service** — A canonical architecture entity with a deterministic ID,
  name and version; it is distinct from Kubernetes Workload identity.
  See [Canonical Model](canonical-model.md).
- **Snapshot** — The stable graph-state identity binding a bounded answer
  and follow-on evidence resolution, so both are evaluated against the
  same state. See [MCP tools](mcp.md).
- **Source adapter** — A mapping boundary that converts source-specific
  documents or observations into canonical facts; it does not write
  directly to the public graph. See [Ingestion](ingestion.md).
- **Subscription** — A named logical delivery entity associated with one
  Topic in the canonical Pub/Sub model, not a consumer instance, offset
  or delivery-guarantee claim. See [Canonical Model](canonical-model.md).
