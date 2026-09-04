# AIP v0.2.0 Specifications

This directory contains the release-level and iteration-specific specifications for AIP `v0.2.0`.

Unlike `v0.1.0`, which emerged from a sequence of historical design and hardening specifications,
`v0.2.0` is managed through an explicit release specification plus self-contained implementation
specifications for each delivery iteration.

## Specification Structure

```text
v0.2.0 release specification
        |
        +-- I1 — Evaluation Kernel
        +-- I2 — Topology and Directionality
        +-- I3 — Evidence and Runtime Semantics
        +-- I4 — Coverage and Hardening
        +-- I5 — Release Qualification
```

The release-level specification defines the final target state for `v0.2.0`.

Each iteration specification is self-contained for implementing that iteration and may intentionally
implement only a subset of the final release semantics. Any such staging must be stated explicitly in
the iteration specification.

## Documents

| Document | Purpose |
|---|---|
| [specification.md](specification.md) | Normative release contract for the final `v0.2.0` release. Defines goals, non-goals, canonical evaluation semantics, scenario model, ground-truth format, runner behavior, reporting, acceptance criteria, and delivery iterations. |
| [i1-evaluation-kernel.md](i1-evaluation-kernel.md) | Self-contained implementation contract for I1 / `v0.2.0-alpha.1` (shipped). Establishes the evaluation kernel with REST `CONFIRMED`, REST `OBSERVED_ONLY`, and async `CONFIRMED` scenarios. |
| [i2-topology-directionality.md](i2-topology-directionality.md) | Self-contained implementation contract for I2 / `v0.2.0-alpha.2`. Enforces `forbidden.relations` and exhaustive unexpected-fact detection, and adds orphan-messaging, mixed REST+async, and request/response queue-pair scenarios. |
| [i3-evidence-runtime-semantics.md](i3-evidence-runtime-semantics.md) | Self-contained implementation contract for I3 / `v0.2.0-alpha.3` (shipped). Adds `NOT_OBSERVED_IN_WINDOW` classification and an evidence-reconciliation scenario proving the `CONFIRMED -> OBSERVED_ONLY` transition when stale declared evidence is removed but observed evidence survives. |
| [i4-coverage-hardening.md](i4-coverage-hardening.md) | Self-contained implementation contract for I4 / `v0.2.0-rc.1` (shipped). Adds partial-observation and declared-only-REST scenarios to reach the ten-scenario core suite, hardens scenario-schema and reconciliation-fixture validation, and makes comparison/report ordering deterministic. |
| [i5-release-qualification.md](i5-release-qualification.md) | Self-contained implementation contract for I5 / `v0.2.0` (shipped). Qualifies the exact `v0.2.0-rc.1` candidate (no new architecture or evaluation semantics), brings public documentation and release metadata to the final `v0.2.0` state, and defines the GO/NO-GO, tag, and published-artifact verification procedure. |
| [git-workflow.md](git-workflow.md) | Branching, commit, push, pull-request, merge, and tagging strategy for the `v0.2.0` implementation. |

Iteration status:

| Iteration | Focus | Target | Status |
|---|---|---|---|
| I1 | Evaluation Kernel | `v0.2.0-alpha.1` | Shipped |
| I2 | Topology and Directionality | `v0.2.0-alpha.2` | Shipped |
| I3 | Evidence and Runtime Semantics | `v0.2.0-alpha.3` | Shipped |
| I4 | Coverage and Hardening | `v0.2.0-rc.1` | Shipped |
| I5 | Release Qualification | `v0.2.0` | Shipped |

I5 is the final `v0.2.0` iteration - it closes the release rather than defining the next
architecture dimension (see [i5-release-qualification.md](i5-release-qualification.md) §33).

## Release Goal

The central `v0.2.0` objective is:

> Make the architecture intelligence introduced in `v0.1` reproducibly testable against independently
> defined ground truth.

In simplified form:

```text
known declared input
        +
known observed input
        +
observation context
        |
        v
       AIP
        |
        v
canonical architecture facts
        |
        v
independent expected ground truth
        |
        v
deterministic PASS / FAIL
```

The release deliberately focuses on verification of existing architecture intelligence rather than
adding another architecture-intelligence dimension.

## Implementation Model

Development is performed through short-lived task branches and focused pull requests against `main`.

An iteration is a milestone and pre-release boundary, not a long-lived integration branch.

```text
task branch
    |
    v
focused PR
    |
    v
   main
    |
    v
iteration complete
    |
    v
pre-release tag
```

See [git-workflow.md](git-workflow.md) for the detailed workflow.

## Relationship to Other Documentation

These files are implementation and release contracts.

Current product and architecture documentation remains under [`docs/`](../..), including:

- [Architecture](../../architecture.md)
- [Canonical Model](../../canonical-model.md)
- [Evidence](../../evidence.md)
- [OpenTelemetry](../../opentelemetry.md)
- [Development](../../development.md)

For shipped versus planned capabilities, see the project [Roadmap](../../../ROADMAP.md).

For the design history that led to `v0.1.0`, see the parent
[Specifications index](../README.md) and the [`v0.1.0` design-history index](../v0.1.0/README.md).
