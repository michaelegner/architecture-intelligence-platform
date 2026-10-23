# Round 7 — Result: NOT FOUND

**Spec:** [spec-round7-boundary-gap-screen.md](spec-round7-boundary-gap-screen.md)
**Date:** 2026-10-23
**Outcome:** **NOT FOUND.** No system in the known pool, the one search or Addendum A (§5) passes every gate. Following the spec (§8), the search was not widened.

## 1. Known pool

Upstream trees were read at their default-branch HEAD on 2026-10-23. The membership source is named first, and screening of a system stopped at its first failed gate.

The spec was written before any screening, in the same session. Both files were committed together afterwards, so git history does not show that order.

| System | Membership source (G1) | Crossing (G2) | First failed gate | Classification |
|---|---|---|---|---|
| Sokol111 | `ecommerce-workspace/docs/architecture/platform-overview.md`: lifecycle groups "Manage products" (Catalog, Image) and "Shop" (Product/Category Query). These groups are informal, but they are drawn from user capability, not connectivity | Catalog → `catalog.product.events` → Product Query crosses the groups; Catalog → Image does not | G3: `docs/architecture/product-update-flow.md` names both consumers and what each does with `ProductUpdated`; the [Round 4 baseline](round4-sokol111-baseline.md) found them from source; the [v0.7.2 I3](../../specifications/0.7.2/i3-comparison-record.md) answers matched | `SOURCE_SUFFICIENT` |
| food-delivery | `docs/eventcatalog/domains/FoodDelivery/subdomains/*`: one EventCatalog subdomain per service, one team (`teams/platform.mdx`) | Yes, but the subdomain boundary equals the service boundary | G3: the EventCatalog itself lists the events, channels and services ([Round 3](candidate-comparison-round3.md)) | `SOURCE_SUFFICIENT` |
| sminerport | None in the tree: no catalog, ownership or architecture document | — | G1 | `NO_MEMBERSHIP_SOURCE` |
| daonhan | None: the ADRs (`docs/adr/0001–0009`) describe patterns, not membership | — | G1 | `NO_MEMBERSHIP_SOURCE` |
| koupang | None: the ADRs describe patterns and `docs/KAFKA_GUIDE.md` describes flows | — | G1 | `NO_MEMBERSHIP_SOURCE` |
| eShop | None in the tree | — | G1 | `NO_MEMBERSHIP_SOURCE` |
| hungCS22hcmiu | None: `docs/adrs/*` and `docs/planning/*` cover design and plans | — | G1 | `NO_MEMBERSHIP_SOURCE` |
| quarkus-super-heroes | None: the docs describe each service | — | G1 | `NO_MEMBERSHIP_SOURCE` |
| apache-airflow | Not applicable: a single application, not a multi-service system | — | G1 | `NO_MEMBERSHIP_SOURCE` |

**Degenerate membership changes nothing.** If membership were taken as "one Component per deployable service", every `NO_MEMBERSHIP_SOURCE` row would reduce to v0.7.2's "which services consume D". Rounds 3–5 already classified that as answered from source for each of these systems.

## 2. Search

The search was one GitHub code search, `"kind: System" filename:catalog-info.yaml`, run on 2026-10-23. It returned about 50 repositories. It took about 30 minutes of the 2-hour box. Three hits were selected for screening:
- `navikt/dagpenger` and `crizstian/cinema-microservice-in-GO` were the only multi-service hits with a messaging or runtime side.
- `wellcomecollection/catalogue-pipeline` does **not** meet §4's eligibility rule, because its messaging is SNS/SQS. It was screened anyway as a real-organisation control and does not count towards the pool.

The other hits were platform templates, workshops, libraries or single services.

| System | Membership source (G1) | Crossing (G2) | First failed gate | Classification |
|---|---|---|---|---|
| `navikt/dagpenger` | `catalog-info.yaml`: Backstage `Domain` `dagpenger` and `System` `dp-soknadsdialog`, owner `teamdagpenger` | Plausible: services in several Systems share one Kafka "rapid" topic (`.github/kafka.agent.md`) | G3: each consumer is a Rapids & Rivers `River` that declares the event types it accepts in its own public `navikt` repository. For example, `navikt/dp-varsel@a4b24f9` `src/main/kotlin/no/nav/dagpenger/behov/brukernotifikasjon/tjenester/rivers/OppgaveSynligFramTilUtløptRiver.kt` declares `demandValue("@event_name", "inaktivert")`. Finding them is a cross-repository search, which §5 excludes as a pass. G4 would fail as well: on a rapid, every app consumes the topic, so broker group state cannot say who handles a given event type. The NAV Aiven broker state is also not available to us | `SOURCE_SUFFICIENT` |
| `wellcomecollection/catalogue-pipeline` | `catalog-info.yaml`: `System` `catalogue-pipeline`, owner `digital-platform`, with per-unit Locations | Plausible, to `catalogue-api` (a separate System) through the pipeline's output | G4: the relationships run over SNS/SQS (`calm_adapter/terraform/topics.tf`, `common/lambda/.../SQS*`) and shared indexes, and none of those is a §3 source. G3 was not fully assessed, because G4 already excludes the system | `RUNTIME_ONLY_UNREPRESENTABLE` |
| `crizstian/cinema-microservice-in-GO` | Root `catalog-info.yaml`: one `System` `cinema-platform`, owner `team-cinema`; every `services/*/catalog-info.yaml` Component sets `system: cinema-platform` | No: everything is in one System with one owner | G2 | `NO_CROSSING` |

## 3. What recurs

- **Demo and portfolio systems lack a boundary.** Either there is no membership source (the known pool), or there is one System with one owner (cinema).
- **Real organisations have a boundary, but nothing AIP can add.** NAV and Wellcome both have Backstage Systems with distinct owners and real cross-System relationships. In both, the relationship is either declared in public source (NAV Rivers, Wellcome Terraform) or carried by a medium AIP does not read (SNS/SQS, shared indexes).
  - **Message-type routing is the closest miss.** NAV's rapid is the closest near miss: the change-relevant fact is which consumer handles which event type, and broker group state cannot carry that by construction.
- **Runtime-only Kafka liveness was not decision-relevant in any system screened.** It is the one runtime-only fact AIP can currently qualify, and it is ops-equivalent with `rpk` or `kafka-consumer-groups` (v0.7.2 C1/C2 check).

## 4. Consequence for v0.8

This result is input to the v0.8 entry decision; it does not decide v0.8 by itself.

- **No v0.8 question on existing evidence.** No real change-impact question was found where membership plus AIP-qualified evidence beats source analysis on current AIP semantics. A v0.8 built around a bounded cross-boundary view would therefore have no demonstrated question to answer.
- **Any viable direction needs new semantics.** The near misses point at:
  - message-type routing on shared topics;
  - SNS/SQS sources;
  - non-messaging shared-data relationships.

  Each of these is new semantics or a new source. The roadmap's own rule makes them a scope decision for the owner, not something this round promotes.

## 5. Addendum A — CDC-fed projections: NOT FOUND

**Spec:** [§9](spec-round7-boundary-gap-screen.md#9-addendum-a--cdc-fed-projections-owner-2026-10-23). The addendum was written before this screening, in the same session.

**Search.** Four GitHub code searches on 2026-10-23:
- Debezium Postgres and MySQL connector classes with `table.include.list`, in JSON and YAML;
- Strimzi `KafkaConnector` resources with `table.include.list`.

They returned about 70 repositories. Most are tutorials, single-owner examples or data-engineering pipelines. Four multi-service hits were screened: three from real organisations, and Kessel, which is out of shape. Revisions are default-branch HEAD on 2026-10-23.

| System | What is captured | First failed gate | Classification |
|---|---|---|---|
| `project-kessel/insights-rbac@b4081c1` | `deploy/debezium-connector.yml` uses `io.debezium.transforms.outbox.EventRouter` on `public.management_outbox` | Outside the §9 shape: outbox router, so an event contract | Excluded |
| `RedHatInsights/playbook-dispatcher@e5687a8` | `deploy/connect.yaml`: `public.runs` and `public.run_hosts`, mapped by the owner's own transforms (`RunEventTransform`, `RunHostEventTransform`) to `platform.playbook-dispatcher.runs` and `.run-hosts` | Outside the §9 shape: the owner-side transform defines the published contract, and the table coupling sits in the owner's own repository | Excluded |
| `RedHatInsights/config-manager@d06a312` with `insights-host-inventory` | `scripts/xjoin-config/debezium.json`: raw `public.hosts` of the inventory database, server `xjoin.inventory`, `ExtractNewRecordState` | G1: neither repository has a CODEOWNERS or catalog file. G3 would fail as well: the owner's README names the xjoin pipeline (`README.md:663`) | `NO_MEMBERSHIP_SOURCE` |
| PagoPA: `pagopa-debt-position@37f6d0d` (owner of schema `apd`), `pagopa-infra@33700d8` (connector), consumers `pagopa-gpd-ingestion-manager@ba4a749` and `pagopa-gpd-rtp@26ce610` | `src/domains/gps-app/yaml/postgres-connector.yaml`: raw `apd.payment_option`, `apd.payment_position` and `apd.transfer` to `cdc-raw-auto.apd.*` (Azure Event Hubs, Kafka endpoint). Both consumers bind those topics in `application.properties` and keep entity classes that mirror the table columns | G3 (detail below) | `SOURCE_SUFFICIENT` |

**PagoPA, gate by gate.**

| Gate | Verdict | Evidence |
|---|---|---|
| G1 | Pass | CODEOWNERS ownership: `pagopa-debt-position` `@pagopa/pagopa-team-core`, `pagopa-gpd-rtp` `@pagopa/pagopa-team-core` (plus associates), `pagopa-gpd-ingestion-manager` `@pagopa/pagopa-tech` |
| G2 | Pass for ingestion-manager only | A migration on `apd.payment_position` crosses from team-core to pagopa-tech. RTP has the same owner, so it does not cross |
| G3 | **Fail** | The owner's repository does not mention the CDC at all: a search for `debezium OR cdc` returns 0 hits. But a fair search across the organisation's source finds the connector's table list, both consumers' topic bindings, and the consumer set itself, declared as Terraform resources (`src/domains/observability/03_eventhub_msg_gdp.tf:118–134`: `rtp-consumer-group`, `gpd-ingestion-manager-{po,pp,tr}`). That is a cross-repository join, which §5 excludes as a pass |
| G4′ | Not assessed | Plausibly also blocking: these are Event Hubs consumer groups, AIP's Kafka capture was never qualified against Event Hubs, and we have no access to the environment |

**What recurs.**
- **Real raw-table CDC across teams exists.** PagoPA's `apd` tables feed another team's service, and that service mirrors the owner's columns. A schema migration in `pagopa-debt-position` can break it, and nothing in the owner's repository says so.
- **The gap is search scope, not missing evidence.** Even in the case where the dependency is invisible from the owner's repository, the organisation's infrastructure-as-code declares the full consumer set. Organisation-wide code search (Unblocked) closes it; runtime evidence would only confirm it.
- **The shape tends to remove its own gap.** It only stays hidden when connectors or consumer groups are created outside version control. None of the four hits did that.

**Consequence.** Addendum A does not change the Round 7 outcome: NOT FOUND, with no real change-impact question where independent evidence beats a fair source investigation. CDC-fed projections are no exception on the systems reachable here.
