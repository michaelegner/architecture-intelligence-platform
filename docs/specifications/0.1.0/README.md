# AIP v0.1.0 — Design History

AIP `v0.1.0` did not originate from a single release specification. It emerged incrementally from a
sequence of design, hardening, runtime-observation, and open-source-readiness specifications.

This directory therefore acts as a release-oriented index for the design history that led to
`v0.1.0`. The original specification files remain in their existing locations under
`docs/specifications/` so that historical links and their chronological meaning are preserved.

## Design Sequence

1. [Proof of Concept](../poc.md)  
   Defines the initial Canonical Model, OpenAPI/AsyncAPI/manifest ingestion, Neo4j graph model,
   deterministic analyses, and the read-only LLM query subsystem.

2. [H1–H3 Hardening](../h1-h3-hardening.md)  
   Introduces persisted Evidence/Provenance, semantic query validation, and the deterministic intent
   router.

3. [H4 — OpenTelemetry](../h4-opentelemetry.md)  
   Adds runtime observation through OpenTelemetry and the declared-vs-observed architecture model.

4. [11H — Runtime Correctness & Robustness](../11h-runtime-correctness-robustness.md)  
   Hardens runtime semantics, evidence reconciliation, HTTP correlation, partial instrumentation,
   observed `PROVIDES`, coverage qualification, and the Collector-based demo.

5. [H5 — Open Source Readiness](../h5-open-source-readiness.md)  
   Covers licensing, documentation, runtime demo, CI/CD, community files, and release preparation.

6. [12G — Public Repository Activation](../12g-public-repository-activation.md)  
   Covers activation of the public GitHub repository, CI verification, security features, and release
   infrastructure.

## Relationship to v0.1.0

The sequence can be viewed as:

```text
PoC
  ↓
H1–H3 Hardening
  ↓
H4 OpenTelemetry
  ↓
11H Runtime Correctness & Robustness
  ↓
H5 Open Source Readiness
  ↓
12G Public Repository Activation
  ↓
v0.1.0
```

The files above are intentionally **not** moved into this directory because they document the
chronological design evolution of AIP, not a single unified `v0.1.0` release contract.

For the current system documentation, see:

- [Architecture](../../architecture.md)
- [Canonical Model](../../canonical-model.md)
- [Evidence](../../evidence.md)
- [OpenTelemetry](../../opentelemetry.md)
- [Roadmap](../../../ROADMAP.md)
