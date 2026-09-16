# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Architecture Intelligence Platform (AIP) is an evidence-qualified architecture knowledge layer:
it ingests declared architecture (OpenAPI, AsyncAPI, an architecture manifest) and, optionally,
runtime observation (OpenTelemetry traces), builds an Architecture Knowledge Graph in Neo4j, and
answers questions about it through fixed deterministic Cypher analyses and a read-only
natural-language query layer. Kubernetes discovery is in progress (`ROADMAP.md`'s v0.5 I2) — check
`ROADMAP.md` for exactly what's shipped vs. planned before assuming a source type is available. See
[`docs/product-doctrine-and-strategic-direction.md`](docs/product-doctrine-and-strategic-direction.md)
for the full product doctrine and [`docs/architecture.md`](docs/architecture.md) for the current
system design — this file does not restate either, since a restatement here is exactly what went
stale last time (see "Repository status" below).

## Governing sources and workflow

This repository is governed by, in authority order: product doctrine, then
[`ROADMAP.md`](ROADMAP.md) (authoritative for shipped-vs-planned release sequencing), then the
current release's own specification (`docs/specifications/<release>/specification.md` and its
`iN-*.md` increment specs — currently `docs/specifications/0.5.0/`). See
[`AGENTS.md`](AGENTS.md) for the full authority chain and the mandatory rules that follow from it.

For substantial specification-driven implementation work, follow `AGENTS.md`'s
reviewed-plan-then-implement-then-reconcile workflow via the
[specification-driven-implementation skill](.claude/skills/specification-driven-implementation/SKILL.md).
Small maintenance changes that don't touch public contracts, identity, evidence, qualification,
reconciliation, or release semantics don't need that full workflow — see `AGENTS.md`'s exemption.

## Repository status

`docs/specifications/poc.md` (and its siblings listed in
[`docs/specifications/README.md`](docs/specifications/README.md): `h1-h3-hardening.md`,
`h4-opentelemetry.md`, `h5-open-source-readiness.md`, `11h-runtime-correctness-robustness.md`,
`12g-public-repository-activation.md`) is the **original historical design input** this project was
built from — not the current governing specification. Every release since v0.2 has its own
versioned specification under `docs/specifications/<release>/`; the current release in progress is
`docs/specifications/0.5.0/`. Do not treat `poc.md`'s scope statements (e.g. what's "out of scope
for this PoC") as current — check `ROADMAP.md` instead, which is authoritative for what's actually
shipped vs. planned per release.

Build/lint/test commands: `uv sync`, `uv run pytest tests/unit`, `uv run pytest tests/integration`,
`uv run ruff check .`, `uv run ruff format .` — see [`docs/development.md`](docs/development.md) for
the full local-dev workflow, including running without Docker and the Collector-based runtime demo.

## Reference

- [`docs/architecture.md`](docs/architecture.md) — current system design: ingestion pipeline,
  runtime observation pipeline, graph write strategy.
- [`docs/canonical-model.md`](docs/canonical-model.md) — the shared Canonical Model every source
  adapter maps into.
- [`docs/graph-model.md`](docs/graph-model.md) — Neo4j node labels, relationship types, import
  strategy.
- [`docs/evidence.md`](docs/evidence.md) — the `Evidence`/`Provenance` model and declared-vs-observed
  semantics.
- [`docs/ingestion.md`](docs/ingestion.md) / [`docs/adapter-development.md`](docs/adapter-development.md)
  — the source-adapter seam and what a new adapter must produce.
- [`docs/analyses.md`](docs/analyses.md) — the deterministic Cypher analyses (A1-A5 and beyond).
- [`docs/mcp.md`](docs/mcp.md) — the MCP tool/transport layer.
- [`docs/opentelemetry.md`](docs/opentelemetry.md) — runtime trace ingestion and declared-vs-observed
  comparison.
- [`docs/adr/`](docs/adr/) — the numbered architecture decision log (design rationale that doesn't
  belong in a living reference doc).
- [`docs/specifications/README.md`](docs/specifications/README.md) — the historical spec index, and
  a pointer to the current versioned specifications.
