# AIP v0.8.0 — Candidate Discovery, Round 1

**Status:** Completed  
**Target:** v0.8.0 product-boundary PoC preparation  
**Scope authority:** ROADMAP.md — v0.8 product-boundary validation

## 1. Purpose

Round 1 SHALL build a broad longlist of credible distributed systems for the v0.8 product-boundary PoC.

The scan is intentionally lightweight. Its purpose is to find plausible systems, not to prove the AIP product boundary yet.

## 2. Candidate profile

Prefer realistic e-commerce or retail systems with:

- several meaningful autonomous services/components;
- synchronous APIs plus meaningful asynchronous messaging;
- runnable open-source code;
- realistic deployment/configuration;
- recent enough activity to support a reproducible PoC.

Kafka is **not required**. RabbitMQ, NATS, Redis Streams, Service Bus and similar messaging technologies are equally valid.

Kubernetes, multi-repository structure, OpenTelemetry, public recognition and coding-agent-native context are useful signals, not gates.

## 3. Discovery

Search primarily through:

- GitHub repository and topic searches around e-commerce, retail, order processing, event-driven systems and microservices;
- established open-source commerce/reference systems;
- vendor/reference repositories;
- CNCF/OpenTelemetry/cloud-native examples.

A secondary search track SHOULD look for systems that already contain coding-agent context such as:

- `CLAUDE.md`;
- `AGENTS.md`;
- Claude Code configuration/skills;
- Codex/Cursor/Copilot-oriented repository guidance.

Coding-agent-native context is a bonus because it strengthens the later baseline.

## 4. Lightweight scan

Spend only enough time on each candidate to inspect:

- README and architecture overview;
- service/repository structure;
- synchronous communication;
- asynchronous messaging;
- deployment files;
- recent meaningful activity.

Do not yet configure Teamscale, validate AIP evidence, deeply inspect source-analysis blind spots, or design detailed change scenarios.

## 5. Candidate record

Record:

| Field | Content |
|---|---|
| Project | Candidate name |
| Repository | Repository URL |
| Domain | E-commerce/retail or adjacent domain |
| Services | Main autonomous components |
| Synchronous communication | REST/gRPC/etc. |
| Asynchronous messaging | Broker/event mechanism |
| Repository structure | Mono/multi-repo/submodules |
| Deployment | Compose/Kubernetes/etc. |
| Activity | Maintenance signal |
| Recognition | Rough public recognition |
| v0.8 interest | One sentence only |

## 6. Filtering

Reject obvious cases that are:

- toy or trivial;
- not meaningfully distributed;
- missing meaningful asynchronous messaging;
- impractical to run;
- clearly abandoned;
- dependent on unavailable/proprietary components that prevent realistic evaluation.

Keep plausible candidates even if the eventual source-analysis blind spot is not yet clear.

## 7. Exit criteria

Round 1 is complete when approximately **20–30 credible candidates** have been identified and documented.

The output becomes the input for Round 2 architecture-fitness evaluation.
