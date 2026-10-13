# AIP v0.8.0 — Finalist Technical Spike, Round 4

**Status:** Completed — neither finalist suitable; see [round4-result.md](round4-result.md)  
**Input:** Round 3 finalists  
**Purpose:** Select the system and bounded-change scenario for the v0.8 product-boundary validation.

Round 4 is **pre-v0.8 selection work**. It selects a system that can fairly test the product hypothesis. It does not run the final v0.8 comparison.

## 1. Goal

Round 4 SHALL answer:

> **Does this finalist provide a realistic, reproducible bounded-change scenario where independent distributed-system evidence exists, fits current AIP semantics, and could plausibly add investigation context beyond all available repository/source context?**

The spike must keep the baseline fair: all relevant repositories, configuration, documentation, `AGENTS.md`, `CLAUDE.md`, ADRs and contracts remain available.

## 2. Out of scope

Round 4 SHALL NOT:

- make the final v0.8 continue / narrow / integrate / defer / stop decision;
- add new AIP semantics solely to make a candidate work;
- hide source or repository-native context;
- perform the final v0.8 product-boundary validation.

## 3. Finalists and fixed changes

Evaluate in this order:

1. **Sokol111 ecommerce workspace** — change `ProductUpdatedEvent`.
2. **sminerport/eCommerceMicroservices** — change the `product.update` RabbitMQ message contract/header semantics.

Start with Sokol111. Evaluate sminerport only if Sokol111 is inconclusive, impractical, unsupported by current AIP semantics, or otherwise unsuitable.

Freeze and record exact repository commits before evaluation.

## 4. Sokol111 source scope

The baseline SHALL include at least:

- `ecommerce-catalog-service-api`
- `ecommerce-catalog-service`
- `ecommerce-product-query-service`
- `ecommerce-image-service`
- `ecommerce-commons`
- `ecommerce-infrastructure`

If another repository becomes relevant, add it rather than withholding it.

## 5. Coding-agent/source baseline

Use a fresh checkout/session with all relevant repository context.

Record:

- which services/repositories the agent chooses to inspect;
- why;
- which distributed relationships it considers established;
- which relationships remain inferred or uncertain;
- what source/configuration evidence supports the conclusion.

One coding agent is sufficient. Claude Code is the preferred initial baseline because the finalists already contain agent-readable context.

Round 4 is not successful merely because the agent overlooks information that was available in source.

## 6. Independent distributed evidence

The candidate must provide evidence independent of ordinary source dependency analysis.

For **Sokol111**, prefer existing Kafka/OpenTelemetry and deployment evidence: producer/consumer spans, runtime service identity, `messaging.system=kafka`, topic/destination attributes, trace propagation, and environment-specific topic/consumer configuration. The fixed scenario centers on Catalog producing `ProductUpdatedEvent` and Product Query plus Image consuming `catalog.product.events`.

For **sminerport**, prefer RabbitMQ/deployment evidence: `products.exchange`, exchange-to-queue bindings, `orders.product.update.queue`, active consumer identity, `product.update` header semantics, and environment-specific Docker/Kubernetes configuration.

Do not modify the application merely to manufacture a stronger AIP case.

## 7. Evidence capture

Round 4 SHOULD perform one minimal live runtime exercise for the leading candidate where setup cost remains reasonable. The resulting evidence SHOULD then be captured with provenance and reused as a deterministic replay fixture. Existing/documented traces may be used instead if running the relevant slice proves disproportionately expensive or fragile.

For Sokol111 the minimal live slice is Kafka plus Catalog, Product Query and Image. The complete environment (Kubernetes, Helm, frontend, databases unrelated to this event flow) is not required.

Prefer captured OTLP/broker/deployment evidence and replayable fixtures where current AIP already supports them. Record the commands and environment assumptions needed to reproduce the evidence.

Synthetic/replayed evidence is acceptable only when it faithfully represents evidence from the real system and preserves provenance.

## 8. AIP feasibility

Use existing AIP Current-State semantics and qualification.

Record:

- what evidence current AIP can ingest;
- what relationship it can establish;
- qualification and provenance;
- what remains unsupported or unresolved;
- whether the result is available through the existing Architecture Intelligence surface.

Classify limitations as:

- **ingestion gap** — evidence fits current semantics but no current ingestion path exists;
- **semantic gap** — current semantics cannot represent the relationship correctly;
- **qualification gap** — evidence is available but cannot be qualified correctly;
- **no relevant evidence**.

A small ingestion adapter or fixture may be acceptable if it stays within existing semantics. A semantic gap weighs strongly against selection.

## 9. Comparison record

| Field | Content |
|---|---|
| Candidate | System + frozen commits |
| Change | Fixed bounded task |
| Expected boundary | Relevant services/components |
| Coding-agent/source result | What repository/context establishes |
| Unresolved source question | What remains uncertain |
| Distributed evidence | Independent observed/configured relation |
| AIP feasibility | What current AIP can establish |
| AIP gap | None / ingestion / semantics / qualification / no evidence |
| Plausible investigation difference? | Yes / unclear / no |
| Setup cost | Low / medium / high |
| Reproducibility | Good / acceptable / poor |
| Public-demo value | Strong / medium / weak |
| Verdict | Select / fallback / reject |

The decisive field is **Plausible investigation difference?**:

> **Is there a credible distributed-architecture question that source/context does not safely settle, while independent evidence can answer it and current AIP semantics can represent that answer?**

This does not prove the final v0.8 product hypothesis. Round 4 only selects a system capable of testing it fairly.

## 10. Selection rule

Select the v0.8 validation system when:

1. the bounded change is realistic and understandable;
2. the source/agent baseline is fair and complete;
3. a meaningful cross-boundary question remains beyond direct source dependencies;
4. independent evidence genuinely exists;
5. current AIP semantics can represent and qualify that evidence, or need only a small ingestion path;
6. the scenario is reproducible;
7. the scenario would make a credible public demonstration if v0.8 succeeds.

Do not require Round 4 to prove the final product-boundary result.

## 11. Execution order

Round 4 SHOULD proceed:

**freeze Sokol111 → coding-agent/source baseline → capture Kafka/OTel evidence → test AIP ingestion/qualification → assess selection fitness**

Only if required:

**freeze sminerport → coding-agent/source baseline → capture RabbitMQ evidence → test AIP ingestion/qualification → assess selection fitness**

## 12. Handoff to v0.8

After selection, Round 4 hands over:

- the selected system and frozen revisions;
- the fixed bounded-change scenario;
- the fair coding-agent/source baseline;
- the independent distributed evidence;
- the reproducible evidence-capture path;
- AIP feasibility and any identified gaps.

The actual product-boundary validation belongs to v0.8 proper.

> **Round 4 selects a system that can fairly test the product hypothesis. v0.8 tests the hypothesis.**

## 13. Exit criteria

Round 4 ends with:

- one selected v0.8 validation system, or an explicit result that neither finalist is suitable;
- one frozen bounded-change scenario;
- exact repository revisions;
- documented coding-agent/source investigation boundary;
- identified independent distributed evidence;
- a reproducible evidence-capture path;
- an explicit statement of what current AIP can and cannot establish;
- any ingestion, semantic, or qualification gap;
- a short **select / fallback / reject** rationale.

If neither candidate is fair and technically viable, record that result rather than weakening the baseline or changing AIP semantics to force a selection.
