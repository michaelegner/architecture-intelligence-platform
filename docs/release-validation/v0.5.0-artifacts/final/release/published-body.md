## Release story

**v0.5.0 broadens what AIP can safely know about a distributed system's Current State.**

It adds Kubernetes as the one new discovery source family, and it associates declared Services
with Kubernetes Workloads (`DEPLOYED_AS`) only through explicit, evidence-backed identity paths. It
distinguishes Topics and Subscriptions from Queues, independently of the broker. It also rebuilds
source ingestion around explicit source identity and authoritative inventories.

Every supported answer stays deterministic, evidence-backed and read-only. Unresolved, conflicting
and unsupported cases are reported as such, never guessed. Knowing *where* something runs does not
establish *how* it interacts: Kubernetes and deployment evidence never create a dependency claim.

Two real systems were qualified against independently frozen ground truth:
- **Quarkus Super Heroes:** 45 of 45 supported facts correct;
- **Apache Airflow 3.3.1:** 9 of 9 correct;
- zero incorrect supported facts on either system.

## What's new

- **Source ingestion foundation.** One adapter/discoverer seam serves OpenAPI, AsyncAPI, the
  architecture manifest and filesystem discovery.
  - **Accepted dialects:** exactly OpenAPI `3.0.3`, `3.1.0` and `3.1.2`, and AsyncAPI `2.6.0`. Any
    other version is rejected as `REJECTED_UNSUPPORTED`.
  - **Identity:** local multi-file `$ref`s are bounded. Identities are owner-scoped.
  - **Removal is explicit.** A source that disappears is not removed: a source's facts expire only
    after a complete inventory of the same scope, or an explicit versioned tombstone. A failed or
    incomplete discovery keeps the last committed state.
  - **Import report.** `POST /api/import` now also returns a versioned import report
    (`aip-import-report/1`). It gives per-source results, inventory status, removals and
    diagnostics. See [`docs/ingestion.md`](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/ingestion.md).
- **Kubernetes discovery (offline).** AIP reads frozen Kubernetes resource bundles.
  - It covers the Workloads `Deployment`, `StatefulSet` and `DaemonSet`, with their Pods, owner
    chains, Kubernetes Services and Ingress routing.
  - It works offline only: there is no live Kubernetes client, no kubeconfig, and no cluster
    access or writes.
  - Infrastructure facts never become application dependencies.
- **Deployment identity (`DEPLOYED_AS`).** A declared Service is associated with a Workload only
  through:
  - an explicit Workload annotation (`architecture-intelligence.io/service-id`);
  - a configured, versioned identity mapping;
  - qualified OpenTelemetry Pod-UID and owner-chain evidence.

  Every outcome is explicit: `RESOLVED_EXPLICIT`, `RESOLVED_CONFIGURED`, `RESOLVED_OBSERVED`,
  `CONFLICT`, `AMBIGUOUS` or `UNRESOLVED`. Disagreeing paths stay a conflict and are never settled by
  precedence. Name similarity never resolves an identity. Deployment answers are part of
  `get_service_dependencies`, and REST serves them at `GET /api/services/{id}/deployments`.
- **Source-independent Pub/Sub.** Topics and Subscriptions are distinct from Queues, as declared by
  AsyncAPI. The behavior was qualified across Google Pub/Sub, Azure Service Bus and a Kafka
  boundary case. Runtime spans can qualify declared Topics and Subscriptions but never create them.
  A Kafka consumer group is never treated as a Subscription.
- **Cross-system qualification.** Both real systems were frozen before they were run. Validation
  found two general defects and fixed them:
  - canonical-validation failures are now reported as per-source results instead of an HTTP 500;
  - the import report now carries the complete source-lifecycle outcome.

  Neither fix is specific to either system.

## What changed for integrators

- **The direct MCP envelope is retired.** `POST /mcp` now serves standard negotiated MCP only. The
  v0.4.x AIP-specific direct envelope (`mcp-method`/`mcp-name` headers, `params._meta` markers) is
  gone. See [ADR 0016](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/adr/0016-public-architecture-knowledge-adapters.md) and
  [`docs/mcp.md`](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/mcp.md). This is an intentional pre-1.0 breaking change.
- **Still exactly three read-only MCP tools:** `get_architecture_drift`, `get_evidence` and
  `get_service_dependencies`.
- **`schema_version` is `"0.5"`.** The answer schemas are under
  [`schemas/architecture_intelligence/v0.5/`](https://github.com/michaelegner/architecture-intelligence-platform/tree/v0.5.0/schemas/architecture_intelligence/v0.5) and
  the import-report schemas under [`schemas/import/v0.5/`](https://github.com/michaelegner/architecture-intelligence-platform/tree/v0.5.0/schemas/import/v0.5).
- **New REST routes over the same service as MCP:**
  - `GET /api/services/{id}/dependencies`
  - `GET /api/services/{id}/drift`
  - `GET /api/services/{id}/deployments`
  - `POST /api/evidence/resolve`
- **Evidence reads are snapshot-bound.** `GET /api/evidence` and `GET /api/evidence/{id}` now
  require `snapshot_id`. They return `409` for a stale snapshot and `503` when no stable snapshot
  can be read.
- **The `POST /api/import` response is extended additively.** The existing `sources` map is
  unchanged, and `report_version` and `runs` are added alongside it.

## Known limitations

- **Kubernetes is `OFFLINE_ONLY`.** There is no live discovery, and no live RBAC, denied-verb or
  denied-scope qualification. Helm, Kustomize, ConfigMaps, Secrets and environment values are never
  read.
- **Deployment identity.** One Service per Workload only; several same-path candidates are
  `AMBIGUOUS`. No locality semantics: namespace and cluster are identity context only.
- **Pub/Sub.** Excluded:
  - live broker discovery;
  - Kafka Connect;
  - partitions, offsets and lag;
  - delivery guarantees;
  - filters and routing rules;
  - schema-registry lifecycle;
  - AsyncAPI 3.x.

  The queue-only analyses (A1-A5, O1-O4) do not traverse Pub/Sub. Pub/Sub is answered by the
  Architecture Intelligence tools.
- **Ingestion.**
  - No remote `$ref` resolution.
  - OpenAPI schema composition (`allOf`/`oneOf`/`anyOf`) is preserved but not interpreted, and is
    reported as a limitation.
  - A present but un-enumerated declaration file produces no diagnostic.
  - An unsupported Kubernetes resource diagnostic names the file and kind, not the object.
- **Snapshot identity depends on the configured source-root path.** The same inputs at a different
  path give a different `snapshot_id`, with the same claims and evidence.
- **Real-system coverage.**
  - gRPC, Kafka event streaming and Postgres are unsupported on the qualified targets.
  - Some real identities remain unresolved (Airflow roles and the Execution API) or have
    insufficient evidence (Celery).
  - Annotation-based deployment identity and messaging parity are covered by supporting fixtures,
    not by the real targets.
- **The MCP client matrix is from v0.4.2.** Codex CLI, Claude Code, Cursor and VS Code + GitHub
  Copilot Chat were qualified against v0.4.2, and that qualification has not been repeated for
  v0.5.0. See the
  [v0.4.2 client matrix](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/release-validation/v0.4.2-client-qualification.md).
- **The evaluation report in the tagged source is older.** The architecture-answers evaluation
  report committed in the tagged source still identifies an earlier candidate (`a906a58`). The
  report refreshed for this release candidate is the release evidence.
- **Not in v0.5:**
  - gRPC/protobuf, and other new source families;
  - locality-qualified Current State (planned for v0.6);
  - explicit Architecture Intent (v0.7).

## Links

- [v0.5.0 specification](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/specifications/0.5.0/specification.md) and its increment completion
  records: [I1](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/specifications/0.5.0/i1-completion-record.md),
  [I2](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/specifications/0.5.0/i2-completion-record.md),
  [I3](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/specifications/0.5.0/i3-completion-record.md),
  [I4](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/specifications/0.5.0/i4-completion-record.md) and
  [I5](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/docs/specifications/0.5.0/i5-completion-record.md)
- Real-system qualification: [`docs/real-world-validation/v0.5.0/`](https://github.com/michaelegner/architecture-intelligence-platform/tree/v0.5.0/docs/real-world-validation/v0.5.0)
- Release golden path: [`examples/release-golden-path/`](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/examples/release-golden-path/README.md)
- [`CHANGELOG.md`](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.0/CHANGELOG.md)
