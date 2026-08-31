# Independent Ground Truth — Quarkus Super Heroes

Authored from primary upstream evidence at commit `8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce` —
**before** any AIP run against this system (I1 §5/§36). No fact below was derived from AIP output.

## Evidence sources used, strongest first (I1 §6-7)

1. Official machine-readable contracts — each service's own `openapi.yml`
   ([`evidence/rest-and-grpc.md`](evidence/rest-and-grpc.md)).
2. Official architecture documentation — root `README.md`, each service's own `README.md`.
3. Official deployment/runtime configuration — each service's `application.properties`/`.yml`
   (`quarkus.application.name`, `quarkus.http.port`, `mp.messaging.*`, `quarkus.grpc.clients.*`,
   `quarkus.stork.*`).
4. Upstream source code — `rest-fights`' three REST client classes
   (`HeroRestClient`/`VillainClient`/`NarrationClient`), plus its gRPC `locations` client config and
   `locationservice-v1.proto`.

No runtime/OTLP evidence is used in I2.1 — I2.1 is declaration-only ground truth. Runtime-observed
evidence is established in I2.2/I2.3 once traffic is exercised.

## Logical service inventory

```text
rest-fights        REST API, orchestrates fights           IN SCOPE
rest-heroes        REST API, provides random hero           IN SCOPE
rest-villains       REST API, provides random villain        IN SCOPE
rest-narration      REST API, provides fight narration        IN SCOPE
event-statistics    Kafka consumer only, no REST provider under test   IN SCOPE (messaging boundary only)
grpc-locations      gRPC API                                  OUT OF AIP-SUPPORTED SCOPE (I2 spec §12)
ui-super-heroes     React UI                                  OUT OF SCOPE (not an architecture entity under validation)
```

## REST provider inventory

Four OpenAPI contracts are captured (I2 spec §46's "at least four REST provider contracts" gate):
`rest-heroes`, `rest-villains`, `rest-narration`, `rest-fights` — see
[`evidence/rest-and-grpc.md`](evidence/rest-and-grpc.md) for the exact path/method/operationId of
every operation in each contract.

`expected.yaml`'s `PROVIDES` set is the **complete** provider inventory of all four contracts (35
operations total: 10 rest-heroes + 10 rest-villains + 3 rest-narration + 12 rest-fights), not only
the four operations `rest-fights` happens to call. This is a scope-safety requirement, not
over-collection: the qualifying I2.3 profile imports each service's complete pinned OpenAPI
document, and under the I1 comparator's scope contract (`ScopeDeclaration.contains`: in scope iff
the relation type is allowed and the source or target is a scoped entity), *every* `PROVIDES` fact
for a scoped service becomes part of the qualifying comparison, whether or not `expected.yaml`
asserts it. A partial expected set would make every legitimate, unlisted provider operation surface
as a false `INCORRECT_SUPPORTED` finding once AIP actually ingests the real documents.

## Qualifying REST dependencies

Independently established from `rest-fights`' own client source code (not from OpenAPI, and not
from AIP output — I2 spec §11/§31: `PROVIDES != CALLS`, caller ground truth must come from
independent caller-side evidence):

```text
rest-fights -> GET  /api/heroes/random     (rest-heroes)     HeroRestClient.findRandomHero()
rest-fights -> GET  /api/villains/random   (rest-villains)   VillainClient.findRandomVillain()
rest-fights -> POST /api/narration         (rest-narration)  NarrationClient.narrate(...)
```

This satisfies I2 spec §11/§46's "at least three REST caller dependencies investigated" gate.

## gRPC unsupported dependency

`rest-fights` also calls `grpc-locations` via gRPC (`locationservice-v1.proto`,
`quarkus.grpc.clients.locations.*`). This is **not** a REST/HTTP call and has no OpenAPI contract.
Per I2 spec §12, it is classified `UNSUPPORTED` (mechanism `grpc`) and must never be represented as
an HTTP `CALLS` relation, a Queue relation, or any other supported fact.

## Kafka topic producer/consumer ground truth

```text
destination kind:  Kafka topic
name:              fights
producer:          rest-fights   (mp.messaging.outgoing.fights.topic=fights)
consumer:          event-statistics (mp.messaging.incoming.fights.topic=fights)
```

Per I2 spec §13-14, this is classified `UNSUPPORTED` (mechanism `kafka-topic`) with respect to
AIP's Queue semantics for the qualifying comparison — see
[`evidence/messaging.md`](evidence/messaging.md) for the full rationale and citations.

**Making the boundary observable.** Classifying the topic `UNSUPPORTED` in the dossier is not by
itself enough to *test* the boundary: the I1 comparator only surfaces an unexpected actual fact
when `expected.scope.contains(fact)` is true, so a scope that omits `service:event-statistics` and
`SENDS`/`RECEIVES_FROM` would let AIP silently emit `service:rest-fights -[:SENDS]->
queue:fights` / `service:event-statistics -[:RECEIVES_FROM]-> queue:fights` without the qualifying
comparison ever seeing it — exactly the false mapping I2 exists to catch. `expected.yaml`'s scope
therefore includes `service:event-statistics` and `SENDS`/`RECEIVES_FROM`, deliberately with **no**
expected `SENDS`/`RECEIVES_FROM` facts: if AIP ever emits one, it becomes an unexpected in-scope
fact and is reported as `INCORRECT_SUPPORTED`, which is the correct outcome for a Kafka topic
incorrectly coerced into Queue semantics.

## Identity normalization rationale

AIP's OpenAPI adapter derives a service's canonical id from the declaration directory name
supplied to the importer (`app/ingestion/openapi_adapter.py`'s `service_id` parameter), not from
the OpenAPI `info.title`. For this dossier, that directory name is chosen to equal each service's
own `quarkus.application.name` (`rest-fights`, `rest-heroes`, `rest-villains`, `rest-narration`) —
the same identity Quarkus itself uses for its container image name, Kubernetes labels, and the
`app` OpenTelemetry resource attribute (`quarkus.otel.resource.attributes=app=${quarkus.application.name},...`).
This mapping is independently corroborated three ways per service: the OpenAPI-declaration
directory name chosen by this dossier, `quarkus.application.name` in the service's own config, and
the Stork static discovery ports in `rest-fights`' own config (`8083`/`8084`/`8087`), which match
each target's own `quarkus.http.port` exactly (see [`evidence/rest-and-grpc.md`](evidence/rest-and-grpc.md)).

Resulting canonical identities (per `app/canonical/ids.py`'s `service_id`/`operation_id` format):

```text
service:rest-fights
service:rest-heroes
service:rest-villains
service:rest-narration

operation:service:rest-heroes:GET:/api/heroes/random
operation:service:rest-villains:GET:/api/villains/random
operation:service:rest-narration:POST:/api/narration
operation:service:rest-fights:GET:/api/fights/randomfighters
```

## Known ambiguities

**Runtime status/evidence is deferred for all three `CALLS` relations, not assumed.** I2.1 freezes
no Architecture Manifest and runs no traffic — its frozen inputs are only OpenAPI contracts and
source code. In current AIP, a declared `CALLS` fact requires an Architecture Manifest (the
`manifest_adapter`, which attaches `MANIFEST` provenance) and an `observed` fact requires captured
OTLP traffic; neither exists yet in this iteration's frozen profile. Asserting `status: CONFIRMED`
or `evidence: {declared: true, observed: true}` now would therefore describe an outcome this
iteration's own frozen inputs cannot reproduce (PR #39 review F3) — pre-authoring a runtime result
is only valid when the causal input that produces it is *also* frozen, and the manifest/traffic
inputs are deliberately I2.2's job, not I2.1's.

`expected.yaml` therefore asserts all three `rest-fights -> {rest-heroes,rest-villains,
rest-narration}` `CALLS` relations by identity only (`type`/`source`/`target`), with no
`status`/`evidence` fields — the relations' *existence* is independently certain from
`rest-fights`' own client source code regardless of what each callee does internally, and the I1
comparator treats an unset expected field as not part of the assertion, so this is a `CORRECT`
match against any of `CONFIRMED`/`OBSERVED_ONLY`/`NOT_OBSERVED_IN_WINDOW` once a real run exists.
I2.2 is expected to freeze a second, explicit pre-run commit — an Architecture Manifest derived
directly from this dossier's already-independent caller evidence, plus the minimum qualifying
traffic intent — and I2.3 then asserts the resulting runtime status from those frozen inputs. What
must not happen is choosing I2.2's manifest/traffic inputs *after* seeing what makes a particular
status pass.

For `rest-narration` specifically, there is an additional reason this is the right call:
`rest-narration/src/main/resources/application.properties` sets
`quarkus.langchain4j.openai.enable-integration=false` by default (real OpenAI calls only happen
under the `%dev,test,openai` profile), so whether `POST /api/narration` returns a clean,
deterministic HTTP response end-to-end under the default profile is itself an open question for
I2.2's traffic-script design — another reason not to pre-assert its runtime status now.

No `INSUFFICIENT_EVIDENCE` or `UNRESOLVED_IDENTITY` items are needed for I2.1 — every fact used
above is corroborated by at least two independent evidence sources.
