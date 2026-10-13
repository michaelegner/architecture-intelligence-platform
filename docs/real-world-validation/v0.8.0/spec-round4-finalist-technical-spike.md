# AIP v0.8.0 — Finalist Technical Spike, Round 4

**Status:** Planned  
**Input:** Round 3 finalists  
**Purpose:** Select the system and bounded-change scenario for the v0.8 product-boundary PoC through a concrete technical spike.

## 1. Goal

Round 4 SHALL answer:

> **For a realistic bounded change, does AIP provide distributed-system context that materially changes the coding agent's investigation boundary beyond a fair source/agent baseline and Teamscale?**

The spike must not hide relevant repositories, documentation, configuration, `AGENTS.md`, or `CLAUDE.md` from the baseline.

## 2. Finalists and fixed changes

Evaluate in this order:

1. **Sokol111 ecommerce workspace**  
   Change: modify the `ProductUpdatedEvent` contract.

2. **sminerport/eCommerceMicroservices**  
   Change: modify the `product.update` RabbitMQ message contract/header semantics.

Start with Sokol111. Evaluate sminerport only if Sokol111 is inconclusive, impractical, or fails the product-boundary test.

Exact repository commits used for the spike SHALL be recorded before evaluation.

## 3. Sokol111 source scope

The Sokol111 baseline SHALL include at least:

- `ecommerce-catalog-service-api`
- `ecommerce-catalog-service`
- `ecommerce-product-query-service`
- `ecommerce-image-service`
- `ecommerce-commons`
- `ecommerce-infrastructure`

All existing repository-native agent guidance and architecture documentation remain available.

## 4. Coding-agent baseline

Use a fresh checkout/session and give the coding agent all relevant repositories and repository context.

For the fixed change, record:

- which services/repositories it decides must be inspected;
- why it includes each one;
- which relationships it considers established versus inferred.

One coding agent is sufficient for the spike. Claude Code is the preferred initial baseline because the selected systems already contain agent-readable project context.

## 5. Teamscale baseline

Use **Teamscale 2026.7.1**.

Import all relevant repositories for the candidate and give Teamscale the same source scope as the coding agent.

Record only what Teamscale can establish from source analysis that is relevant to the bounded change.

Do not restrict repositories to create an artificial advantage for AIP.

## 6. Independent distributed evidence

### Sokol111

Prefer existing Kafka/OpenTelemetry evidence:

- producer and consumer spans;
- runtime service identity;
- `messaging.system=kafka`;
- topic/destination attributes;
- trace propagation;
- environment-specific consumer/topic configuration.

### sminerport

Prefer existing RabbitMQ evidence:

- exchange;
- bindings;
- queue;
- active consumer;
- environment-specific deployment/configuration.

Existing evidence SHOULD be used rather than modifying the application to manufacture a stronger AIP case.

## 7. AIP feasibility

Use existing AIP Current-State semantics and evidence qualification wherever possible.

Prefer replayable evidence fixtures/snapshots over implementing a new production adapter.

AIP SHALL NOT gain new broker semantics solely to make the spike succeed.

For each relationship record:

- what evidence AIP can ingest;
- what relationship it can establish;
- qualification and provenance;
- anything that remains unresolved or unsupported.

If existing AIP semantics cannot correctly represent the available evidence, record that as a spike result.

## 8. Comparison

| Field | Content |
|---|---|
| Candidate | System + frozen commits |
| Change | Fixed bounded task |
| Expected boundary | Services/components that actually matter |
| Coding-agent result | Investigation boundary from all source/context |
| Teamscale result | Relevant boundary established from source |
| Distributed evidence | Independently observed/configured relationship |
| AIP result | Evidence-qualified relationship AIP can establish |
| Changed next action? | Yes / no / unclear |
| AIP gap | None / ingestion / semantics / qualification |
| Setup cost | Low / medium / high |
| Reproducibility | Good / acceptable / poor |
| Public-demo value | Strong / medium / weak |
| Verdict | Select / reject |

The decisive field is **Changed next action?**

## 9. Selection rule

Select a system only if:

> **AIP causes the coding agent to inspect something materially relevant that the fair source/agent/Teamscale baseline did not safely establish.**

Runtime confirmation alone is insufficient if the same services would already have been inspected.

The preferred system should also be reproducible, understandable publicly, and maintainable as the v0.8 demo.

## 10. Execution order

Round 4 SHOULD proceed sequentially:

**freeze Sokol111 → coding-agent baseline → Teamscale baseline → capture Kafka/OTel evidence → replay through AIP → compare**

Only then, if required:

**freeze sminerport → coding-agent baseline → Teamscale baseline → capture RabbitMQ evidence → replay through AIP → compare**

This avoids doing two full environment setups before knowing whether the leading candidate already answers the product question.

## 11. Exit criteria

Round 4 ends with:

- one selected v0.8 PoC system, or an explicit result that neither finalist demonstrates sufficient value;
- one frozen bounded-change scenario;
- exact repository revisions;
- documented coding-agent, Teamscale and AIP investigation boundaries;
- identified independent evidence;
- any AIP ingestion/semantic limitation discovered;
- a short **select / narrow / stop** rationale.

If neither candidate demonstrates material value beyond the fair baseline, the result SHALL be recorded rather than constructing a scenario to force an AIP win.
