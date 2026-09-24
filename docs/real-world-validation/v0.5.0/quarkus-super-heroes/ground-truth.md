# Independent Ground Truth: `quarkus-super-heroes` (v0.5.0)

This was drafted on 2026-09-24 from upstream evidence at commit
`8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce` only. No qualifying AIP output for this target existed
or was inspected. The owner reviews it, and merging the dossier PR freezes it (I5 §6, spec Draft 0.3).

## Rules

- Every fact cites its upstream source. Unless stated otherwise, a path is relative to the upstream
  repository root at the pin, and `path:N` is line N.
- AIP graph contents, API responses, comparator output, and generated prose never determine a fact.
- Where an expected outcome depends on AIP semantics, it is derived by applying the governing
  specification to the upstream input, never by running AIP. That applies to the I2 import results,
  the I2 claims and the I3 outcomes below. The specification section is cited next to the upstream
  line.
- v0.3 used the same pin. Its dossier (`../../quarkus-super-heroes/`) was research input only.
  Every fact below was re-derived from the upstream files.

## Evidence sources used, strongest first

1. **Official machine-readable contracts.** The four OpenAPI documents
   `rest-{fights,heroes,villains,narration}/src/main/resources/openapi/openapi.yml`, and the
   upstream Kubernetes manifest `deploy/k8s/java25-kubernetes.yml`. There is no AsyncAPI document
   anywhere in the repository at the pin.
2. **Official documentation.** `docs/src/main/resources/content/deploying.md` and
   `deploy/k8s/README.md`.
3. **Official configuration.** Each service's `src/main/resources/application.properties`, or
   `application.yml` for rest-heroes.
4. **Upstream source code.** The rest-fights REST, gRPC and messaging clients, and the
   event-statistics listener.
5. **Independently captured runtime evidence.** None is used for the freeze. OTel is captured
   during the qualifying run (Slice 5) and is compared, not used to author facts.

## Service identity

The canonical Service id of each service is `service:<quarkus.application.name>`:

| Service | `quarkus.application.name` | HTTP port |
| --- | --- | --- |
| `service:rest-fights` | `rest-fights/src/main/resources/application.properties:1` | `:10` (8082) |
| `service:rest-heroes` | `rest-heroes/src/main/resources/application.yml:2-3` | `:31` (8083) |
| `service:rest-villains` | `rest-villains/src/main/resources/application.properties:1` | `:5` (8084) |
| `service:rest-narration` | `rest-narration/src/main/resources/application.properties:1` | `:38` (8087) |
| `service:event-statistics` | `event-statistics/src/main/resources/application.properties:1` | `:4` (8085) |

The same names label each service's Deployment and Kubernetes Service in the upstream manifest
(for example `app: rest-fights`), and they appear as `app=${quarkus.application.name}` in each
service's OTel resource attributes (`rest-fights/src/main/resources/application.properties:95`).

The upstream OpenAPI documents carry no `x-aip-service-id`, and I1 §4.1 forbids deriving identity
from a directory name or `info.title`. So `runtime/declarations/identity-bindings.yaml` binds each
OpenAPI source to its Service (I1 §4.1 path 3). That file is disclosed AIP operator configuration,
not ground truth.

`event-statistics` has no OpenAPI and no REST contract. No declaration mints it as a Service. It is
in scope only as a messaging boundary. An expectation about it is always negative.

## REST: PROVIDES (35)

This is the complete operation inventory of the four upstream OpenAPI documents. The copies in
`runtime/declarations/` are byte-identical to upstream; their digests are in `profile.md`. The
citation is each operation's `operationId` line.

| Fact | Citation |
| --- | --- |
| `service:rest-heroes` PROVIDES `GET /api/heroes` (`getAllHeroes`) | `rest-heroes/src/main/resources/openapi/openapi.yml:19` |
| `service:rest-heroes` PROVIDES `PUT /api/heroes` (`replaceAllHeroes`) | `rest-heroes/src/main/resources/openapi/openapi.yml:48` |
| `service:rest-heroes` PROVIDES `POST /api/heroes` (`createHero`) | `rest-heroes/src/main/resources/openapi/openapi.yml:81` |
| `service:rest-heroes` PROVIDES `DELETE /api/heroes` (`deleteAllHeroes`) | `rest-heroes/src/main/resources/openapi/openapi.yml:111` |
| `service:rest-heroes` PROVIDES `GET /api/heroes/hello` (`hello`) | `rest-heroes/src/main/resources/openapi/openapi.yml:120` |
| `service:rest-heroes` PROVIDES `GET /api/heroes/random` (`getRandomHero`) | `rest-heroes/src/main/resources/openapi/openapi.yml:136` |
| `service:rest-heroes` PROVIDES `GET /api/heroes/{id}` (`getHero`) | `rest-heroes/src/main/resources/openapi/openapi.yml:160` |
| `service:rest-heroes` PROVIDES `PUT /api/heroes/{id}` (`fullyUpdateHero`) | `rest-heroes/src/main/resources/openapi/openapi.yml:191` |
| `service:rest-heroes` PROVIDES `DELETE /api/heroes/{id}` (`deleteHero`) | `rest-heroes/src/main/resources/openapi/openapi.yml:225` |
| `service:rest-heroes` PROVIDES `PATCH /api/heroes/{id}` (`partiallyUpdateHero`) | `rest-heroes/src/main/resources/openapi/openapi.yml:240` |
| `service:rest-villains` PROVIDES `GET /api/villains` (`getAllVillains`) | `rest-villains/src/main/resources/openapi/openapi.yml:19` |
| `service:rest-villains` PROVIDES `PUT /api/villains` (`replaceAllVillains`) | `rest-villains/src/main/resources/openapi/openapi.yml:48` |
| `service:rest-villains` PROVIDES `POST /api/villains` (`createVillain`) | `rest-villains/src/main/resources/openapi/openapi.yml:81` |
| `service:rest-villains` PROVIDES `DELETE /api/villains` (`deleteAllVillains`) | `rest-villains/src/main/resources/openapi/openapi.yml:111` |
| `service:rest-villains` PROVIDES `GET /api/villains/hello` (`hello`) | `rest-villains/src/main/resources/openapi/openapi.yml:120` |
| `service:rest-villains` PROVIDES `GET /api/villains/random` (`getRandomVillain`) | `rest-villains/src/main/resources/openapi/openapi.yml:136` |
| `service:rest-villains` PROVIDES `GET /api/villains/{id}` (`getVillain`) | `rest-villains/src/main/resources/openapi/openapi.yml:160` |
| `service:rest-villains` PROVIDES `PUT /api/villains/{id}` (`fullyUpdateVillain`) | `rest-villains/src/main/resources/openapi/openapi.yml:191` |
| `service:rest-villains` PROVIDES `DELETE /api/villains/{id}` (`deleteVillain`) | `rest-villains/src/main/resources/openapi/openapi.yml:225` |
| `service:rest-villains` PROVIDES `PATCH /api/villains/{id}` (`partiallyUpdateVillain`) | `rest-villains/src/main/resources/openapi/openapi.yml:240` |
| `service:rest-narration` PROVIDES `POST /api/narration` (`narrate`) | `rest-narration/src/main/resources/openapi/openapi.yml:19` |
| `service:rest-narration` PROVIDES `GET /api/narration/hello` (`hello`) | `rest-narration/src/main/resources/openapi/openapi.yml:65` |
| `service:rest-narration` PROVIDES `POST /api/narration/image` (`generateImageFromNarration`) | `rest-narration/src/main/resources/openapi/openapi.yml:81` |
| `service:rest-fights` PROVIDES `GET /api/fights` (`getAllFights`) | `rest-fights/src/main/resources/openapi/openapi.yml:19` |
| `service:rest-fights` PROVIDES `POST /api/fights` (`performFight`) | `rest-fights/src/main/resources/openapi/openapi.yml:88` |
| `service:rest-fights` PROVIDES `GET /api/fights/hello` (`hello`) | `rest-fights/src/main/resources/openapi/openapi.yml:145` |
| `service:rest-fights` PROVIDES `GET /api/fights/hello/heroes` (`helloHeroes`) | `rest-fights/src/main/resources/openapi/openapi.yml:161` |
| `service:rest-fights` PROVIDES `GET /api/fights/hello/locations` (`helloLocations`) | `rest-fights/src/main/resources/openapi/openapi.yml:177` |
| `service:rest-fights` PROVIDES `GET /api/fights/hello/narration` (`helloNarration`) | `rest-fights/src/main/resources/openapi/openapi.yml:193` |
| `service:rest-fights` PROVIDES `GET /api/fights/hello/villains` (`helloVillains`) | `rest-fights/src/main/resources/openapi/openapi.yml:209` |
| `service:rest-fights` PROVIDES `POST /api/fights/narrate` (`narrateFight`) | `rest-fights/src/main/resources/openapi/openapi.yml:225` |
| `service:rest-fights` PROVIDES `POST /api/fights/narrate/image` (`generateImageFromNarration`) | `rest-fights/src/main/resources/openapi/openapi.yml:268` |
| `service:rest-fights` PROVIDES `GET /api/fights/randomfighters` (`getRandomFighters`) | `rest-fights/src/main/resources/openapi/openapi.yml:300` |
| `service:rest-fights` PROVIDES `GET /api/fights/randomlocation` (`getRandomLocation`) | `rest-fights/src/main/resources/openapi/openapi.yml:326` |
| `service:rest-fights` PROVIDES `GET /api/fights/{id}` (`getFight`) | `rest-fights/src/main/resources/openapi/openapi.yml:345` |

## REST calls: CALLS (7)

rest-fights calls three REST services through two MicroProfile REST clients and one JAX-RS
`WebTarget` client (`rest-fights/src/main/java/io/quarkus/sample/superheroes/fight/client/`):

| Fact | Client citation | Target operation (`operationId`) | Exercised by `runtime/traffic.sh` |
| --- | --- | --- | --- |
| rest-fights CALLS `GET /api/heroes/random` | `HeroRestClient.java:20,30-32` (`findRandomHero`), reached via `FightService.java:119,141-143` | `rest-heroes/.../openapi.yml:136` (`getRandomHero`) | yes: `GET /api/fights/randomfighters` |
| rest-fights CALLS `GET /api/heroes/hello` | `HeroRestClient.java:20,38-41`, via `FightService.java:157-160` | `rest-heroes/.../openapi.yml:120` (`hello`) | no |
| rest-fights CALLS `GET /api/villains/random` | `VillainClient.java:39,50-59` (base `api/villains/`, path `random`) | `rest-villains/.../openapi.yml:136` (`getRandomVillain`) | yes: `GET /api/fights/randomfighters` |
| rest-fights CALLS `GET /api/villains/hello` | `VillainClient.java:39,69-76`, via `FightService.java:204-207` | `rest-villains/.../openapi.yml:120` (`hello`) | no |
| rest-fights CALLS `POST /api/narration` | `NarrationClient.java:24,35-37`, via `FightService.java:285` | `rest-narration/.../openapi.yml:19` (`narrate`) | yes: `POST /api/fights/narrate` |
| rest-fights CALLS `POST /api/narration/image` | `NarrationClient.java:24,39-44`, via `FightService.java:294-296` | `rest-narration/.../openapi.yml:81` (`generateImageFromNarration`) | no |
| rest-fights CALLS `GET /api/narration/hello` | `NarrationClient.java:24,50-53`, via `FightService.java:166-169` | `rest-narration/.../openapi.yml:65` (`hello`) | no |

**Target identity.** The clients resolve their targets through Stork static discovery:
- `rest-fights/src/main/resources/application.properties:29-32` names `hero-service`,
  `narration-service` and `villain-service`;
- `:49-56` resolves them to `localhost:8083`, `:8084` and `:8087`.

Those are exactly the HTTP ports of rest-heroes, rest-villains and rest-narration (see "Service
identity").

**Owner decision (2026-09-24).** v0.3 froze only the three exercised calls. Re-review found four
more real client calls. All seven are frozen, and all seven are declared through the disclosed
manifest `runtime/declarations/rest-fights/architecture.yaml`. The three calls that
`runtime/traffic.sh` exercises are expected `CONFIRMED`, with declared and observed evidence. The
other four are expected `NOT_OBSERVED_IN_WINDOW`, with declared evidence and no observed evidence.
The frozen traffic never calls the rest-fights `hello` endpoints or `POST /api/fights/narrate/image`,
and no other component in the profile does (the UI is excluded).

## gRPC: UNSUPPORTED

rest-fights calls grpc-locations over gRPC: `LocationClient.java:34`
(`@GrpcClient("locations")`), with the `locationservice-v1.proto` contract. v0.5 has no gRPC
semantics, so the mechanism is `UNSUPPORTED` and yields no CALLS, Queue or Pub/Sub fact
(`qsh-grpc-locations`). grpc-locations is outside the component scope (I5 §8.1).

## Kafka `fights`: negative, UNSUPPORTED

```text
producer: rest-fights       @Channel("fights") MutinyEmitter   FightService.java:64
                            mp.messaging.outgoing.fights.topic=fights
                            rest-fights/src/main/resources/application.properties:82-83
consumer: event-statistics  @Incoming(FIGHTS_CHANNEL_NAME)     statistics/listener/SuperStats.java:59
                            mp.messaging.incoming.fights.topic=fights, broadcast=true
                            event-statistics/src/main/resources/application.properties:11-14
contract: none; no AsyncAPI document exists in the repository at the pin
```

Under I4, v0.5 admits Topics and Subscriptions only from declarations, and runtime observation mints
none. A Kafka consumer group is never a Subscription (I5 §4.2, §8.1). With no AsyncAPI, the
expected facts are:
- there is **no** Queue, Topic or Subscription for `fights`;
- there is **no** `SENDS`, `PUBLISHES_TO` or `RECEIVES_FROM` involving rest-fights or
  event-statistics;
- the producer's legacy `messaging.operation` key stays unsupported (I4 §9) and creates no fact.

`expected.yaml` enforces this through scope closure and two named `queue:fights` forbidden facts.
Both mechanisms are recorded as `UNSUPPORTED` (`qsh-kafka-fights-topic`,
`qsh-kafka-legacy-operation-key`).

## Kubernetes (I2): expected import outcomes

The source is `deploy/k8s/java25-kubernetes.yml` at the pin: 56 YAML documents. Line numbers below
refer to that upstream file, which is byte-identical to `runtime/k8s/unmodified/java25-kubernetes.yml`.
The derived copy has one extra line per document, so the same object sits a few lines lower there.

### Unmodified upstream file (I5 §5 item 1)

No document sets `metadata.namespace`, and every admitted kind in the file is namespaced. I2 §5
rejects a namespaced resource with a missing namespace. So the expected outcome is:

```text
source qsh-k8s-upstream-unmodified: REJECTED_INVALID, diagnostic K8S_RESOURCE_INVALID
                                    nothing commits; no Workload, Kubernetes Service or Ingress
```

### Namespace-derived copy (I5 §5 item 2)

`runtime/k8s/derive_namespaced.py` adds `  namespace: quarkus-super-heroes` after each of the 56
top-level `metadata:` lines. It then verifies, by parsing, that removing that key restores every
document exactly. The two digests are recorded in `upstream.md`.

```text
source qsh-k8s-namespaced: ACCEPTED_WITH_LIMITATIONS, evidence mode DECLARED_MANIFEST
```

**Workloads (`WORKLOAD_EXISTS`, 13 unique `apps/v1` Deployments, namespace `quarkus-super-heroes`):**
`rest-fights` (1465), `rest-heroes` (925), `rest-villains` (636), `rest-narration` (346),
`event-statistics` (1869), `grpc-locations` (181), `ui-super-heroes` (2023), `fights-db` (1282),
`fights-kafka` (1345), `apicurio` (1403), `heroes-db` (862), `villains-db` (574) and
`locations-db` (112). There are no StatefulSets, DaemonSets, Pods or ReplicaSets.

**Kubernetes Services (13 unique `v1` Services, all `ClusterIP` with a non-empty selector):**

| Service | Line | Selector |
| --- | --- | --- |
| `locations-db` | 63 | `name=locations-db` |
| `grpc-locations` | 80 | `app.kubernetes.io/name=grpc-locations, app.kubernetes.io/part-of=locations-service, app.kubernetes.io/version=java25-latest` |
| `rest-narration` | 314 | `app.kubernetes.io/name=rest-narration, app.kubernetes.io/part-of=narration-service, app.kubernetes.io/version=java25-latest` |
| `villains-db` | 525 | `name=villains-db` |
| `rest-villains` | 542 | `app.kubernetes.io/name=rest-villains, app.kubernetes.io/part-of=villains-service, app.kubernetes.io/version=java25-latest` |
| `heroes-db` | 813 | `name=heroes-db` |
| `rest-heroes` | 830 | `app.kubernetes.io/name=rest-heroes, app.kubernetes.io/part-of=heroes-service, app.kubernetes.io/version=java25-latest` |
| `fights-db` | 1199 | `name=fights-db` |
| `fights-kafka` | 1216 | `name=fights-kafka` |
| `apicurio` | 1233 | `name=apicurio` |
| `rest-fights` | 1250 | `app.kubernetes.io/name=rest-fights, app.kubernetes.io/part-of=fights-service, app.kubernetes.io/version=java25-latest` |
| `event-statistics` | 1717 | `app.kubernetes.io/name=event-statistics, app.kubernetes.io/part-of=event-stats, app.kubernetes.io/version=java25-latest` |
| `ui-super-heroes` | 1991 | `app.kubernetes.io/name=ui-super-heroes, app.kubernetes.io/part-of=ui-super-heroes, app.kubernetes.io/version=java25-latest` |

**Ingress (1):** `ui-super-heroes` (2144). I2 §7.5 applies to its backends:

- `INGRESS_ROUTES_TO_NETWORK_SERVICE` Ingress `ui-super-heroes` → Service `rest-fights`. The
  rule's path is `/api/fights` (Prefix), and the backend port `name: http` matches the Service's
  single port `http`/80 (1250).
- `INGRESS_ROUTES_TO_NETWORK_SERVICE` Ingress `ui-super-heroes` → Service `ui-super-heroes`. Two
  rules have `path: /` (Prefix): one has no `host`, and the other has `host: ""` (2182). Port
  `http` matches the Service's single port `http`/80 (1991). Under I2 §7.5, multiple routes to
  one Service merge their evidence into one claim.

**No other claims.**
- **No `NETWORK_SERVICE_SELECTS_WORKLOAD`.** This is a declaration-only bundle with no captured
  Pods, and I2 §7.4 does not substitute a Pod template for a captured Pod.
- **No `WORKLOAD_OWNS_POD`.** There are no Pods (I2 §7.3).
- **No interaction fact.** Kubernetes creates no CALLS, SENDS, PUBLISHES_TO or RECEIVES_FROM
  (I2 §11 qualification matrix, "Surface" row; I5 §8.1).

**Frozen limitation list (I5 §5).** The derived copy's result is `ACCEPTED_WITH_LIMITATIONS` with
exactly these limitations.

*(a) `K8S_RESOURCE_UNSUPPORTED`: 25 objects whose kind is outside I2 §5's admitted set, one
limitation each:*

| # | API version | Kind | Name | Line |
| --- | --- | --- | --- | --- |
| 1 | `v1` | Secret | `grpc-locations-config-creds` | 7 |
| 2 | `v1` | Secret | `locations-db-config` | 20 |
| 3 | `v1` | ConfigMap | `grpc-locations-config` | 35 |
| 4 | `v1` | ConfigMap | `locations-db-init` | 49 |
| 5 | `v1` | ConfigMap | `rest-narration-config` | 303 |
| 6 | `v1` | Secret | `rest-villains-config-creds` | 470 |
| 7 | `v1` | Secret | `villains-db-config` | 483 |
| 8 | `v1` | ConfigMap | `rest-villains-config` | 497 |
| 9 | `v1` | ConfigMap | `villains-db-init` | 511 |
| 10 | `v1` | Secret | `rest-heroes-config-creds` | 758 |
| 11 | `v1` | Secret | `heroes-db-config` | 771 |
| 12 | `v1` | ConfigMap | `rest-heroes-config` | 785 |
| 13 | `v1` | ConfigMap | `heroes-db-init` | 799 |
| 14 | `v1` | ServiceAccount | `rest-fights` | 1047 |
| 15 | `v1` | Secret | `rest-fights-config-creds` | 1068 |
| 16 | `v1` | Secret | `fights-db-config` | 1081 |
| 17 | `v1` | ConfigMap | `rest-fights-config` | 1095 |
| 18 | `v1` | ConfigMap | `fights-db-init` | 1124 |
| 19 | `rbac.authorization.k8s.io/v1` | Role | `view-jobs` | 1138 |
| 20 | `rbac.authorization.k8s.io/v1` | RoleBinding | `default_view` | 1154 |
| 21 | `rbac.authorization.k8s.io/v1` | RoleBinding | `rest-fights-view-jobs` | 1166 |
| 22 | `rbac.authorization.k8s.io/v1` | RoleBinding | `rest-fights-view` | 1183 |
| 23 | `batch/v1` | Job | `rest-fights-liquibase-mongodb-init` | 1605 |
| 24 | `v1` | Secret | `event-statistics-config-creds` | 1660 |
| 25 | `v1` | ConfigMap | `event-statistics-config` | 1670 |

That is 9 Secrets, 10 ConfigMaps, 1 ServiceAccount, 1 Role, 3 RoleBindings and 1 Job.

*(b) `NO_QUALIFIED_POD_MATCH`: one per Kubernetes Service above (13).* Each has a non-empty
selector and no captured Pod to match (I2 §7.4 and the §10 diagnostic table).

*(c) Nothing else.* There is no `K8S_BACKEND_UNRESOLVED`, because both Ingress backends resolve.
There is no `K8S_OWNER_UNRESOLVED`, because there are no Pods. There is no
`K8S_RESOURCE_CONFLICT` (see the duplicate record).

Any limitation not on this list, or a listed one that is missing, is a finding (I5 §5).

**Duplicate record (I5 §5).** The file declares four objects twice, once in the rest-fights section
and once in the event-statistics section:

| Object | Lines | Bytes | Semantic content | Expected I2 handling |
| --- | --- | --- | --- | --- |
| Service `fights-kafka` | 1216, 1683 | identical | identical | merged (identical duplicate) |
| Service `apicurio` | 1233, 1700 | identical | identical | merged |
| Deployment `apicurio` | 1403, 1807 | identical | identical | merged |
| Deployment `fights-kafka` | 1345, 1749 | differ (label key order) | identical as parsed YAML | merged: same allowlisted projection, so same semantic digest (I2 §6, §7.1) |

## DEPLOYED_AS (I3): per-Workload outcomes (I5 §8.1)

No Workload carries a Path A annotation (`upstream.md`). Path C is not exercised (I5 §8.1). The
disclosed Path B artifact `runtime/mapping.yaml` is AIP operator configuration. It maps exactly
three Services to their same-named Deployments, taking the Workload identities from the
namespace-derived manifest. With no Path A evidence it cannot disagree with anything.

| Workload (Deployment, `quarkus-super-heroes`) | Path A | Path B | Expected public outcome | Basis |
| --- | --- | --- | --- | --- |
| `rest-fights` | absent | mapped (`qsh-rest-fights`) | `RESOLVED_CONFIGURED`, `supporting_methods = [RESOLVED_CONFIGURED]` | I5 §8.1 row 2; I3 §8.2 |
| `rest-heroes` | absent | mapped (`qsh-rest-heroes`) | `RESOLVED_CONFIGURED`, `[RESOLVED_CONFIGURED]` | I5 §8.1 row 2 |
| `rest-villains` | absent | mapped (`qsh-rest-villains`) | `RESOLVED_CONFIGURED`, `[RESOLVED_CONFIGURED]` | I5 §8.1 row 2 |
| `rest-narration` | absent | **deliberately none** | **No claim and no resolution.** This is the name-only negative: the Deployment name equals the declared Service name. With no applicable path, I3 §13.1 forms no candidate group. | I5 §8.1 row 1; I3 §13.1 |
| `event-statistics` | absent | none | No claim and no resolution. The Service is not declared. | I5 §8.1 row 1 |
| all other Deployments | absent | none | No claim and no resolution. | I3 §13.1 |

So the complete set of public deployment outcomes for the scoped Services is exactly the three
`RESOLVED_CONFIGURED` rows. Every claim's and resolution's evidence must drill down at the same
snapshot (I5 §13). That check runs in Slice 5.

## Checks the comparator cannot express

The comparator compares relation facts and public deployment outcomes. Slice 5 SHALL verify these
frozen expectations from public reads and the import response, and record the result in
`results.md`:

1. **Import results.** `qsh-k8s-upstream-unmodified` is `REJECTED_INVALID` with
   `K8S_RESOURCE_INVALID`. `qsh-k8s-namespaced` is `ACCEPTED_WITH_LIMITATIONS` with exactly the
   limitation list above. Every declaration source is accepted.
2. **Kubernetes inventory.** Exactly the 13 Workloads, 13 Kubernetes Services, 1 Ingress and 2
   Ingress routes above, all `DECLARED_MANIFEST`.
3. **Messaging entities.** No Queue, Topic or Subscription entity exists.

## Unknowns

None needs an `UNRESOLVED_IDENTITY` or `INSUFFICIENT_EVIDENCE` entry. One interpretation is flagged
for review instead:
- **Ingress rule with `host: ""`.** It is read with its Kubernetes meaning: an empty host is
  equivalent to an absent host. If AIP handles it differently, the difference is a Slice 5
  finding, never a post-freeze edit.

## Change log

- 2026-09-24: initial v0.5 freeze draft (I5 Slice 2).
