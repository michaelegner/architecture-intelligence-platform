# AIP v0.3.0 — Real-World Validation & Model Hardening

**Release:** `v0.3.0`  
**Status:** I1-I4 complete; `v0.3.0-rc.1` tagged at the qualified candidate; I5 (release
qualification) pending — see
[`docs/real-world-validation/cross-system/report.md`](../../real-world-validation/cross-system/report.md)  
**Project:** Architecture Intelligence Platform (AIP)

---

## Purpose

AIP `v0.3.0` validates the architecture-intelligence core against independently authored external
systems before that core is exposed through a broader public tool contract or expanded with
additional discovery adapters.

The release progression is:

```text
v0.1
Architecture intelligence exists

v0.2
Architecture intelligence is reproducibly verified

v0.3
Architecture intelligence survives real systems
```

The defining principle is:

> **Do not make external systems fit AIP. Make AIP prove that its supported semantics fit external
> systems, and explicitly admit where they do not.**

---

## Validation Systems

`v0.3.0` uses two complementary systems:

```text
Quarkus Super Heroes
    External Reference Architecture

Apache Airflow
    Real-World OSS Software
```

Quarkus Super Heroes provides a relatively controlled externally authored microservice architecture
with REST, OpenAPI, messaging, mixed synchronous/asynchronous flows, and OpenTelemetry.

Apache Airflow provides the stronger model stress test: a mature real-world architecture with API
server, scheduler, workers, broker/executor behavior, runtime process identities, and asynchronous
task execution.

---

## Release Structure

The implementation is divided into five iterations:

| Iteration | Title | Purpose | Planned tag | Status |
|---|---|---|---|---|
| I1 | Real-World Validation Contract | Freeze methodology, finding vocabulary, dossier structure, comparison semantics, and runbook contract | `v0.3.0-alpha.1` | ✓ complete (no separate tag cut) |
| I2 | Quarkus Super Heroes Validation | Validate the current model against an external reference architecture | `v0.3.0-alpha.2` | ✓ complete — tag cut |
| I3 | Apache Airflow Validation | Validate the current model against real-world OSS software | `v0.3.0-alpha.3` | ✓ complete (no separate tag cut) |
| I4 | Cross-System Model Hardening | Apply only general fixes justified by independent real-system evidence and revalidate both systems | `v0.3.0-rc.1` | ✓ complete — tag cut |
| I5 | Release Qualification | Qualify the exact candidate and publish `v0.3.0` | `v0.3.0` | pending |

---

## Documents

```text
docs/specifications/0.3.0/
├── README.md
├── specification.md
├── i1-real-world-validation-contract.md
├── i2-quarkus-validation.md
├── i3-airflow-validation.md
├── i4-cross-system-model-hardening.md
├── i5-release-qualification.md
└── git-workflow.md               (not yet created — see status below)
```

Current documents:

| Document | Status |
|---|---|
| [`specification.md`](specification.md) | Final |
| [`i1-real-world-validation-contract.md`](i1-real-world-validation-contract.md) | Final implementation specification |
| [`i2-quarkus-validation.md`](i2-quarkus-validation.md) | Final implementation specification |
| [`i3-airflow-validation.md`](i3-airflow-validation.md) | Final implementation specification |
| [`i4-cross-system-model-hardening.md`](i4-cross-system-model-hardening.md) | Final implementation specification |
| [`i5-release-qualification.md`](i5-release-qualification.md) | Draft implementation specification |
| `git-workflow.md` | To be added if release-specific workflow details are required |

---

## Core Methodological Invariant

The central validation rule is:

```text
AIP Input != AIP Expected Output
AIP Output MUST NOT define Ground Truth
```

Required order:

```text
upstream contracts/docs/config/source/runtime evidence
        |
        v
independent architecture dossier
        |
        v
freeze supported expected facts
        |
        v
run AIP
        |
        v
compare
```

Ground truth SHALL be frozen before the qualifying AIP comparison run.

---

## Finding Vocabulary

All real-world findings use the following fixed categories:

```text
CORRECT
MISSING_SUPPORTED
INCORRECT_SUPPORTED
UNSUPPORTED
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
```

The release prioritizes correctness over apparent completeness:

```text
correct but incomplete
    >
complete-looking but wrong
```

Unsupported architecture is acceptable when it is explicit.

Incorrectly represented supported architecture is not.

---

## Validation Evidence

Real-system evidence is stored separately from release specifications:

```text
docs/real-world-validation/
├── README.md
├── quarkus-super-heroes/
└── apache-airflow/
```

Each system dossier is expected to preserve the distinction between:

```text
upstream identity
validation profile
independent ground truth
AIP results
findings
```

The release specification defines the semantic contract.

The validation dossiers contain the actual evidence.

---

## Fundamental v0.3 Gate

Before AIP proceeds to `v0.4 — Architecture Intelligence Tools`:

> **No unresolved real-world finding may indicate that the Canonical Architecture Model requires a
> fundamental breaking redesign before AIP exposes it through a broader machine-consumable
> contract.**

If such a finding exists:

```text
v0.3 = NO-GO
```

until the model is corrected or the affected semantic claim is deliberately removed from supported
scope.

---

## Non-Goals

`v0.3.0` deliberately does not include:

```text
MCP
Architecture Intelligence Service public contract
Kubernetes discovery
Dapr discovery
gRPC/protobuf adapter
Kafka Connect adapter
GraphRAG
vector search
Architecture Copilot
policy engine
multi-agent behavior
performance benchmarking
1.0 contract freeze
```

Those belong to later releases.

---

## Expected Roadmap After v0.3

```text
v0.4
Architecture Intelligence Tools
    Goal: Trusted Architecture Context for Agents
    ArchitectureIntelligenceService
    structured evidence-backed result contracts
    snapshot and observation-context binding
    evidence and provenance linkage
    qualification of architectural claims
    read-only MCP tools
    deterministic tool evaluation

v0.5
Broader Architecture Discovery
    Kubernetes
    additional adapters
    deeper runtime discovery

v0.9
Contract Freeze / Production Qualification

v1.0
Stable Architecture Intelligence Platform
```
