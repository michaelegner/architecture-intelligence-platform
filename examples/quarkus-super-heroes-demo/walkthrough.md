# Walkthrough: before changing image narration in `rest-fights`

> **Task:** We need to change the image-narration behavior in `rest-fights`. Before touching the
> code, establish its dependencies, deployment context, observed behavior, supporting evidence and
> unresolved integration boundaries.

This walks through the eight questions of the [v0.5.1 spec](../../docs/specifications/0.5.1/specification.md)
§5 (Q1-Q8) and, since v0.6.1, a ninth, the Broker question (Q9; [v0.6.1 spec](../../docs/specifications/0.6.1/specification.md)
§6.3), against the running demo. Every **AIP result** below is an excerpt of a real answer from a clean
`run.sh`. The snapshot is deterministic, so you get the same ids. Each answer is kept visibly apart
from the other two kinds of information:

| Block | What it is |
|---|---|
| **AIP result** | What AIP returned: claims, qualifications, evidence and limitations |
| **Dossier context** | What the independently authored v0.5.0 dossier records but AIP's answer does not contain |
| **Agent suggestion** | A next step for the developer. Not an architecture fact. |

## Setup

```bash
examples/quarkus-super-heroes-demo/run.sh
claude mcp add --transport http --scope local aip http://localhost:8000/mcp   # or see ../mcp-clients/
```

Then paste the prompt that `run.sh` printed (also in `.aip-qsh-demo/prompt.txt`) into your agent.
AIP needs no model API key. Your agent client may need its own account. A recorded example is in
[`conversation-claude-code.md`](conversation-claude-code.md).

All questions use this observation context, which the prompt already contains:

```json
{"environment": "quarkus-i5", "window_start": "2026-09-25T13:06:47Z", "window_end": "2026-09-25T13:06:54Z"}
```

Over REST, the same context is `?environment=quarkus-i5&from=2026-09-25T13:06:47Z&to=2026-09-25T13:06:54Z`
(written `$CTX` below). Evidence is snapshot-bound. If the graph changes (another import, say),
query again or rerun `run.sh --down && run.sh`.

---

## Q1 — What does `rest-fights` depend on?

MCP `get_service_dependencies` `{"service_id": "service:rest-fights", "observation_context": …}`, or
`curl -s "http://localhost:8000/api/services/service:rest-fights/dependencies?$CTX"`.

**AIP result:** `outcome: PARTIAL`, snapshot
`aip:snapshot:v1:5fc44f0a7742b37eb0cb3aa1bb960eb08bb87dd459fa0d7f6e8e76f927fb9246`. There are seven
`CALLS`, grouped by target and operation. The same target appears more than once because each
operation is its own claim:

| Target | Operation (`delivery.via`) | Qualification |
|---|---|---|
| `service:rest-heroes` | `GET /api/heroes/random` | `CONFIRMED` |
| | `GET /api/heroes/hello` | `NOT_OBSERVED_IN_WINDOW` |
| `service:rest-villains` | `GET /api/villains/random` | `CONFIRMED` |
| | `GET /api/villains/hello` | `NOT_OBSERVED_IN_WINDOW` |
| `service:rest-narration` | `POST /api/narration` | `CONFIRMED` |
| | `POST /api/narration/image` | `NOT_OBSERVED_IN_WINDOW` |
| | `GET /api/narration/hello` | `NOT_OBSERVED_IN_WINDOW` |

The same answer also contains one `PUBLISHES_TO` claim (Q7), one `DEPLOYED_AS` claim (Q4) and, since
v0.6.1, one `USES_BROKER` claim (Q9), so it is the Broker-aware `schema_version: "0.6"` shape. It has
exactly one limitation, `UNRESOLVED_IDENTITY`, on the topic claim.

**Dossier context (not AIP's answer):** `rest-fights` also calls `grpc-locations` over gRPC
(`LocationClient.java:34`, `@GrpcClient("locations")`; dossier
[`ground-truth.md`](../../docs/real-world-validation/v0.5.0/quarkus-super-heroes/ground-truth.md) lines
133-138). v0.5 has no gRPC semantics, so this call is neither a claim nor a limitation. **The
limitations list does not cover every unknown dependency.**

## Q2 — What actually ran?

Same answer, `qualification` per claim.

**AIP result:** three `CONFIRMED` claims, meaning declared and observed in the window: `GET /api/heroes/random`,
`GET /api/villains/random` and `POST /api/narration`. Four are `NOT_OBSERVED_IN_WINDOW`, meaning
declared but not exercised between `13:06:47Z` and `13:06:54Z`. The window covers one replayed fight.

Not observed means *not exercised in this window*. It does not mean unused or dead.

## Q3 — Why do you believe it calls `GET /api/heroes/random`?

Take that claim's `evidence_refs` and `resolution_evidence_refs`, plus the answer's `snapshot_id`, and
call MCP `get_evidence`, or
`curl -s -X POST localhost:8000/api/evidence/resolve -H 'content-type: application/json' -d '{"evidence_refs": […], "snapshot_id": "…"}'`.

**AIP result:** claim `aip:claim:v1:a669b8dd1dd4a8d7c17c45759e3137520b6462d803f9afadc51ec9222126fa4f`
(`CONFIRMED`). All three refs resolve at the same snapshot, and none is missing:

| Evidence | Type | Source |
|---|---|---|
| `evidence:manifest:urn:aip:source:filesystem:3f01cbac…` | `DECLARED` `MANIFEST` | `qsh/declarations/rest-fights/architecture.yaml`: the declared call |
| `evidence:openapi:urn:aip:source:filesystem:9e809db0…` | `DECLARED` `OPENAPI` | `qsh/declarations/rest-heroes/openapi.yml`: resolves the target operation |
| `evidence:otel:quarkus-i5:2026-09-25:4878531641e8` | `OBSERVED` `OPENTELEMETRY` | One `CLIENT_SERVER` call, first seen `2026-09-25T13:06:48.899936Z` |

## Q4 — Where does it run?

The `DEPLOYED_AS` claim in the same MCP dependencies answer. Its evidence goes through `get_evidence`, as in Q3.

**AIP result:** `rest-fights` is `DEPLOYED_AS` the Deployment `rest-fights` in namespace
`quarkus-super-heroes`, with `resolution_method: RESOLVED_CONFIGURED` and
`supporting_methods: [RESOLVED_CONFIGURED]`. The only evidence is
`evidence:mapping:v1:5abcfb14a391738519af257da06c7752a5f336d970f4a9a4584f9bcf2fd4d507`
(`DECLARED` `CONFIGURATION`, `mapping.yaml`).

**Dossier context:** the Kubernetes input is an offline declared manifest. The replayed services
never ran in a cluster. Knowing *where* something runs creates no dependency.

## Q5 — And `rest-narration`? There is a Deployment with the same name.

MCP `get_service_dependencies` for `service:rest-narration`, or its REST equivalent
`curl -s "http://localhost:8000/api/services/service:rest-narration/dependencies?$CTX"`. The
deployment-only view is an additional REST route:
`curl -s "http://localhost:8000/api/services/service:rest-narration/deployments?$CTX"`.

**AIP result:** `outcome: ANSWERED` with `claims: []` and `limitations: []`. The deployment-only view
returns `deployment_claims: []` and `deployment_resolutions: []`. AIP makes no deployment claim at
all. That is neither a resolution nor an explicit `UNRESOLVED` result. The same-named `rest-narration`
Deployment exists in the manifest, but a matching name never resolves an identity, and no annotation,
mapping entry or observed evidence links them.

## Q6 — What is declared but was not exercised?

MCP `get_architecture_drift`, or `curl -s "http://localhost:8000/api/services/service:rest-fights/drift?$CTX"`.

**AIP result:** `outcome: PARTIAL`, five claims, all `NOT_OBSERVED_IN_WINDOW`: `GET /api/heroes/hello`,
`GET /api/villains/hello`, `GET /api/narration/hello`, **`POST /api/narration/image`**, and the
`fights` topic. There is no observed-but-undeclared call.

The image call exists: it is declared, and the dossier traces it to `NarrationClient.java:39-44`. The
replayed traffic simply did not exercise it.

## Q7 — Does it publish events, and who consumes them?

The `PUBLISHES_TO` claim in the dependencies answer, its evidence, and the import report
(`.aip-qsh-demo/import.json`).

**AIP result:** claim `aip:claim:v1:001e05d24d100a7cb0a8507047e51a2453c08b3650896ec43f8f8c12d3af8da3`:
`rest-fights` `PUBLISHES_TO` Topic `fights`, with `NOT_OBSERVED_IN_WINDOW`, `coverage: PARTIAL`,
`destination_resolution: DIRECT_TARGET_FALLBACK` and `subscription: null`. Its only evidence is
`DECLARED` `ASYNCAPI` from `qsh/overlay/rest-fights/asyncapi.yaml`, the **operator-authored overlay**
([PROVENANCE.md](PROVENANCE.md)). The answer's limitation:

> `UNRESOLVED_IDENTITY` — topic:owned:496c9bff… has no single evidenced subscription; retained as
> the direct topic target rather than guessed.

The overlay does declare `event-statistics` as a consumer. But it has no Subscription identity, so
the import report records `SUBSCRIPTION_IDENTITY_MISSING` at `/channels/fights/subscribe`, and AIP
names **no** consumer.

**Dossier context:** upstream, `event-statistics` consumes `fights` as a Kafka consumer group
(`SuperStats.java:59`; `ground-truth.md` "Kafka `fights`"). A consumer group is never a Subscription,
and the real producer spans carry only a legacy key AIP does not read. That is why nothing confirms
the publish at runtime.

## Q8 — What should I watch out for before changing image narration?

**AIP result, taken together:**
- `POST /api/narration/image` is declared but was not exercised in the window (Q2, Q6).
- `rest-narration` has no qualified deployment identity (Q5).
- The `fights` topic's consumers are unresolved (Q7). Knowing its Broker (Q9) does not change that.

**Dossier context:** the gRPC `grpc-locations` call is outside AIP's answer (Q1).

**Agent suggestion (not AIP output):**
- Read the existing code path and contract before changing it: the dossier traces the call to
  `NarrationClient.java:39-44` via `FightService.java:294-296`, and `rest-narration` provides it as
  `generateImageFromNarration`.
- Getting a `CONFIRMED` runtime baseline for the image call needs live traffic in a running system.
  That is a separate validation activity: this replay demo starts no Quarkus services and stops its
  Collector after the fixed replay, so it cannot observe new calls.
- Coordinate any contract change with `rest-narration`, which provides the operation.
- Treat consumers of the published fight message as unknown until they are confirmed outside AIP.

AIP doesn't say the change is safe, and neither should your agent.

## Q9 — Which broker does `rest-fights` use, and what does that tell me about the messaging topology?

*(Added in v0.6.1.)* The `USES_BROKER` claim in the same dependencies answer as Q1, and its evidence:
MCP `get_evidence` (or `curl -s -X POST http://localhost:8000/api/evidence/resolve …`) on the
claim's `evidence_refs` at the answer's own `snapshot_id`.

**AIP result:** because `rest-fights` declares a Broker, the answer is the Broker-aware v0.6 shape
(`schema_version: "0.6"`; the evidence answer is v0.6 too). One claim,
`aip:claim:v1:a1d173f77375c8af38d4a0f473aae99d82f63c7646fe99ec00c41cb9ea70d6e0`: `rest-fights`
`USES_BROKER` the Broker `kafka:fights-kafka` (`object.type: BROKER`, id
`broker:owned:41c2cee978012556efd6d7da196e07c0d58dde2bc925c8ebd6b4719065a0d5a7`), listed in
`data.broker_claim_ids`. Its only evidence is `DECLARED` `ASYNCAPI` from
`qsh/overlay/rest-fights/asyncapi.yaml`, the **operator-authored overlay**
([PROVENANCE.md](PROVENANCE.md)), the same record that supports the `PUBLISHES_TO` claim (Q7). Resolving it at
the answer's snapshot returns that record with the exact fact
`USES_BROKER service:rest-fights → broker:owned:41c2…` and a `broker` object (`id`, `type: BROKER`,
`name: kafka:fights-kafka`). `event-statistics` declares the same `x-aip-broker-id` in its own overlay file,
so its answer names the same Broker. Both ids reproduce from the spec's formulas with the
independent reference
(`uv run python -m evaluation.architecture_answers.reference broker-id kafka:fights-kafka` and
`… broker-claim-id service:rest-fights kafka:fights-kafka`).

A Broker claim has no `delivery`, runtime qualification or coverage: it says the declaration names
this Broker, not that any traffic was observed.

**What this tells you about the messaging topology:** the Kafka cluster `kafka:fights-kafka` is the
infrastructure `rest-fights` is declared to use, and nothing more. It does **not** resolve the
consumers of Topic `fights`: the answer is still `PARTIAL` with the same single `UNRESOLVED_IDENTITY`
limitation on the `PUBLISHES_TO` claim (Q7), and there is no Subscription claim or entity. A Broker
claim never creates or implies a Queue, Topic, Subscription, Message, producer or consumer.

**Dossier context:** upstream, `event-statistics` consumes `fights` as a Kafka consumer group, and a
consumer group is never a Subscription (Q7). The dossier does not model the Kafka cluster either: the
Broker id comes only from the operator-authored overlay.

**Agent suggestion (not AIP output):** treat the Broker as a declared infrastructure fact, not as
confirmation of who consumes the topic. To learn the consumers, confirm them outside AIP.
