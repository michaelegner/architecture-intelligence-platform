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
4. Upstream source code — the four `rest-fights` client classes
   (`HeroRestClient`/`VillainClient`/`NarrationClient`, plus the gRPC `locations` client config and
   `locationservice-v1.proto`).

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
each contract used below.

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

**Narration runtime-status uncertainty.** `rest-narration/src/main/resources/application.properties`
sets `quarkus.langchain4j.openai.enable-integration=false` by default — real OpenAI calls only
happen under the `%dev,test,openai` profile. Whether `POST /api/narration` still returns a clean,
deterministic HTTP response end-to-end with the OpenAI integration disabled is a question for
I2.2's traffic-script design, not a ground-truth question: the `rest-fights -> rest-narration`
`CALLS` relation's *existence* is independently established from source code regardless of what
`rest-narration` does internally. `expected.yaml` therefore asserts this relation without a
`status`/`evidence` assertion, deferring that decision to I2.2/I2.3 once the actual traffic
behavior under the frozen profile is known. This is not an `INSUFFICIENT_EVIDENCE` item — the
relation itself is certain; only its eventual runtime *status* is left for a later iteration to
assert, which the I1 comparator semantics support natively (an unset expected field is not part of
the assertion).

No `INSUFFICIENT_EVIDENCE` or `UNRESOLVED_IDENTITY` items are needed for I2.1 — every fact used
above is corroborated by at least two independent evidence sources.
