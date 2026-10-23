# AIP — v0.8 Entry Boundary-Gap Screen, Round 7

**Status:** Completed — see [round7-result.md](round7-result.md)
**Input:** Rounds 1–6, the v0.7.2 I3 comparison and the I4 DEFER ([record](../../specifications/0.7.2/i3-comparison-record.md#owner-checkpoint-i4-defer))
**Purpose:** Before any v0.8 scope or code, find out whether one real change-impact question exists where independently established System/Component membership plus AIP-qualified evidence beats source analysis.

Round 7 is a **desk screen**. It does not:
- change any AIP code, schema or semantics;
- run captures, environments or coding-agent arms;
- run a comparison.

A negative result is valid. If the result is negative, the question is not to be rebuilt around a favourable scenario.

## 1. Question

Round 7 SHALL answer:

> **On a real system, is there a bounded change whose impact includes a relationship that crosses an independently established System/Component boundary, where a fair source-only investigation misses or misstates that relationship, and current AIP can represent and qualify it from independent evidence?**

## 2. Starting position

- **Strong baselines.** Rounds 3–6 and v0.7.2 I3 found the source/agent baseline strong in every system. The questions it left open were runtime-only: whether consumers are attached, which versions are deployed, and whether undeclared consumers exist ([Round 4](round4-result.md)).
- **No AIP history.** AIP replaces a source's capture in place, so it keeps no history. A retained-observation advantage therefore needs new semantics and is out of scope here. The v0.7.2 Sokol111 C1/C2 check (2026-10-23) found this.
- **Membership is open to both sides.** A fair baseline can read a membership source too: a Backstage catalog, an EventCatalog, an architecture spec or ownership files. Once the relationships are known, classifying them against a boundary is trivial. Any advantage must therefore come from the **relationship**: a cross-boundary relationship that is runtime-only, or that source states misleadingly. Membership makes such a relationship matter; it does not create the advantage.

## 3. Current AIP sources (live `main` `f864625`, [ingestion](../../ingestion.md))

- **Declared sources:** OpenAPI, AsyncAPI 2.x, the architecture manifest.
- **Offline sources:**
  - Kubernetes and the Service↔Workload mapping;
  - APISIX configuration and measurement;
  - Kafka consumer-group state plus Kafka service mapping.
- **OpenTelemetry traces:** HTTP and messaging spans with the attribute keys AIP reads ([allow-list](../../opentelemetry.md#attribute-allowlist)), plus Pub/Sub observations.

AIP has no RabbitMQ topology source, no routing-predicate semantics and no System/Component concept. Membership is an input to the screen, not an AIP fact.

## 4. Pool

1. **Known systems.** Each keeps the bounded change from [Round 3](candidate-comparison-round3.md) or its own record:
   - Sokol111
   - sminerport
   - daonhan
   - food-delivery
   - koupang
   - eShop
   - hungCS22hcmiu
   - [quarkus-super-heroes](../quarkus-super-heroes/)
   - [apache-airflow](../apache-airflow/)

   Pitstop is excluded, because it is authored.
2. **One search, time-boxed to about 2 hours.**
   - Find public multi-service systems with an explicit membership declaration: a Backstage `catalog-info.yaml` with `kind: System` or `Component`, an EventCatalog, or an architecture/conformance spec.
   - The system must also have evidence for a source in §3.
   - Screen at most three new systems.

## 5. Gates

A candidate passes only if every gate passes. Screening of a system stops at its first failed gate.

| Gate | Pass condition |
|---|---|
| G1 Membership | A membership source exists that is independent of connectivity, naming and repository structure. It is named in the result **before** that system's relationship evidence is assessed. Authored membership counts only if it is derived from a cited non-connectivity source (ownership, deployable unit, organisation), and it must be disclosed |
| G2 Crossing | A relationship that the bounded change touches crosses that boundary |
| G3 Source fails | There is a concrete reason why a fair, complete source investigation misses or misstates the relationship. Examples: the endpoint or destination is supplied only at deploy time from outside the repositories, the consumer sits outside what the change author's organisation can read, or the dispatch is dynamic. "Hard to join across repositories" does not pass |
| G4 Representable | Independent evidence for the relationship exists, and a §3 source can carry it with current semantics |
| G5 Decision | A named decision differs: the consumer set, the change list, the inspection list or a rollout gate |
| G6 Not ops-equivalent | Ordinary operational inspection (broker CLI, `kubectl`, gateway admin), with the access the baseline has, does not give an equally qualified answer with comparable effort |

Each system gets one classification. The first failed gate decides it:

| Classification | Assigned when |
|---|---|
| `NO_MEMBERSHIP_SOURCE` | G1 fails |
| `NO_CROSSING` | G2 fails |
| `SOURCE_SUFFICIENT` | G3 fails |
| `RUNTIME_ONLY_UNREPRESENTABLE` | G4 fails |
| `NO_DECISION_CHANGE` | G5 fails |
| `OPS_EQUIVALENT` | G6 fails |
| `PASS` | every gate passes |

## 6. Fairness

- **Full baseline access.** The baseline gets everything the change author's organisation could realistically read: repositories, configuration, contracts, the membership source and ordinary operational tooling.
- **Nothing withheld.** No evidence is withheld to create a gap.
- **Real access boundaries.** A claim that something lies outside the organisation's repositories must reflect a real organisational access boundary.
- **Cited verdicts.** Every gate verdict cites a file, revision or upstream path. Prior round records are used first, and upstream source is read only where a gate depends on it.

## 7. Confirmation

This step runs only for a `PASS`. It is one fair source-only investigation of the candidate question, time-boxed to about 1 hour, to test G3 honestly. AIP is not run. The one exception is a genuinely uncertain G4, and then only as a local import of material that already exists.

## 8. Output and stop

[`round7-result.md`](round7-result.md) records one outcome:

- **FOUND:** the question, the evidence path and the affected decision. This is the v0.8 entry input.
- **NOT FOUND:** the near misses by classification. This is the input for the v0.8 checkpoint (stop/defer).
- **INCONCLUSIVE:** the single missing piece of evidence and what it would cost to obtain.

Time box: about one working day. If the known pool and the one search produce no `PASS`, Round 7 stops with NOT FOUND, and the search is not widened.

## 9. Addendum A — CDC-fed projections (owner, 2026-10-23)

This addendum was added after the main screen and written before its own screening. It narrows the round to one shape.

**Shape.** Service A owns a database. A change-data-capture connector publishes A's raw table changes to Kafka, for example Debezium with topic `<server>.<schema>.<table>`. Another service B builds a projection from that topic.

**Bounded change.** A schema migration on table T in A's database.

**Why it is screened.** Through the connector, B depends on A's internal schema, not on an event contract. A's repository has no publishing code. The connector configuration may live elsewhere, or be registered at runtime through the Kafka Connect REST API.

**Excluded.** Debezium's outbox event router. It publishes an event contract, which reduces the case to the event-fed projection already classified for Sokol111.

**Gates.** The §5 gates apply, with one disclosed change to G4:

| Gate | Change |
|---|---|
| G4′ | Passes if two conditions hold: the Kafka consumer side is carried by the current Kafka consumer-state source; and the table→topic derivation is evidenced by capturable connector configuration. The derivation relationship is **new semantics**. A `PASS` under G4′ therefore means "candidate for a small semantic extension", not "representable today" |

**Pool.** One search, time-boxed to about 2 hours. Its targets are public multi-service systems with:
- Kafka Connect/Debezium connector configuration that captures tables (not the outbox router);
- a consumer of those topics in another service;
- if possible, a membership source.

At most five systems are screened. Examples and tutorials with a single owner count as `NO_CROSSING`, unless they declare separate Systems.

**Stop.** If no hit passes, the addendum records NOT FOUND, and the search is not widened.
