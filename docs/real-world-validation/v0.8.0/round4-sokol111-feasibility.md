# Round 4 — Sokol111 evidence capture and AIP feasibility

**Spec:** [spec-round4-finalist-technical-spike.md](spec-round4-finalist-technical-spike.md) §6–§8  
**Frozen revisions:** [round4-sokol111-freeze.md](round4-sokol111-freeze.md)  
**Evidence:** [`round4-evidence/sokol111/`](round4-evidence/sokol111/) (checksums in `SHA256SUMS`)

## 1. Live runtime exercise — attempted, stopped (setup cost: high)

Per the §7 live-first preference, a minimal live slice was attempted on 2026-10-13: Kafka
(`apache/kafka-native:4.2.0`), single-node replica-set MongoDB (`mongo:8.3.8`), an OTel Collector
file exporter, and the three **unmodified** services built from the frozen checkouts in a
`golang:1.26` container (`go build ./cmd/main.go`; all three built, commands in
`live-attempt/`). Services use their pinned `ecommerce-commons v0.8.16`, which equals the frozen
`ecommerce-commons` `VERSION`, so the source read for span attributes matches the built binaries.

All three services exit at start-up with the same error, after progressively supplying the missing
configuration (`CONFIG_FILE`, `tenant-events` consumer, `tenant.grpc.address`; Mongo/Kafka/OTLP
endpoints; security disabled):

```
tenant.Lifecycle is nil: ensure multi-tenancy is enabled to handle tenant events
```

The services unconditionally wire a tenant-events consumer that requires multi-tenancy, which in
turn requires the tenant service (gRPC) and, for client-credentials tokens, Logto; the Image
service additionally requires S3/MinIO and imgproxy configuration. Their `config.standalone.yaml`
is therefore not actually a standalone path. Running the slice would need at least tenant
service + Logto + Postgres + MinIO, which exceeds the "Kafka + three services" bound set for
this round, so the live run was **stopped** (stop condition of the owner's Round 4 decision) and
no live telemetry was captured. Setup cost for a live, reproducible Sokol111 slice: **high**
(realistically the k3d + Tilt environment the repository documents).

No application change was made to force a run (§6).

## 2. Replay evidence — source-derived, not live-captured

Because no live telemetry exists, the evidence below is **authored from the instrumentation
source**, not captured from the running system. It is weaker for system selection and is labelled
as such. Spans reproduce exactly the attributes emitted by `ecommerce-commons` v0.8.16
(`pkg/kafka/outbox/trace_propagator.go`, `pkg/kafka/consumer/tracing.go`) with resource
`service.name`, `service.version`, `deployment.environment.name` as set by
`pkg/observability/fxconfig/resource.go`:

| Span | Kind | Emitted attributes |
|---|---|---|
| `kafka.produce` (Catalog) | PRODUCER | `messaging.system=kafka`, `messaging.destination=<topic>`, `messaging.message.id` |
| `kafka.consume` (Product Query, Image) | CONSUMER | `messaging.system=kafka`, `messaging.destination=<topic>`, `messaging.partition`, `messaging.offset`, `messaging.message.key` |

W3C trace context is propagated through Kafka headers (producer injects, consumer extracts), so
producer→consumer parentage is real in the system; the probe reproduces it with a parent span id.
Consumer-group identity appears only in infra/service config (`default-group-id`), not on spans.

## 3. AIP feasibility (real decoder + adapter, no AIP code changes)

`round4-evidence/sokol111/aip_probe.py` builds an OTLP `ExportTraceServiceRequest`, decodes it with
`app.telemetry.otlp_receiver.decode_export_request`, and runs `app.telemetry.adapter.adapt` against
declared Service candidates and a declared Topic `catalog.product.events`. Output:
`aip_probe_output.txt`. Four variants separate the causes:

| Variant | Result |
|---|---|
| A. Spans exactly as emitted | no facts, no unresolved diagnostics — spans carry no `messaging.operation.type`, so they are not recognised as messaging spans at all |
| B. A + `messaging.destination.name` | same as A |
| C. A + `messaging.operation.type` | all three spans `no_destination_name` (legacy `messaging.destination` key is not read) |
| D. Fully conformant keys (`messaging.destination.name` + `messaging.operation.type`) | Catalog `PUBLISHES_TO` Topic **OBSERVED**; both consumers `unresolved_destination_semantics` |

Variant D is the best case and it matches AIP's own qualified Kafka boundary
(`tests/fixtures/pubsub/kafka`, `docs/opentelemetry.md` "Pub/Sub observations": a consumer group
never becomes a Subscription).

## 4. Gap classification (spec §8)

| Gap | Class | Detail |
|---|---|---|
| Emitted spans use legacy `messaging.destination` and omit `messaging.operation.type` | **ingestion gap** | Evidence fits the semantics but no current ingestion path reads these keys; fixing it means either changing the system's instrumentation (prohibited, §6) or adding an AIP attribute mapping (a small adapter change, §8 allows only if within existing semantics) |
| Product Query and Image consume the topic as separate Kafka consumer groups; AIP cannot attribute a consumer to a Topic | **semantic gap** | Even with conformant keys, variant D leaves both consumers unresolved. Group membership exists only in config (`default-group-id`) |
| No AsyncAPI/Topic declaration exists (contract is protobuf) | **ingestion gap** | A declared Topic would need a manifest/overlay source authored for this evaluation |
| Observed consumption (running consumers, deployed versions, other consumers) | **no relevant evidence** | no live telemetry captured |

Per spec §8 "a semantic gap weighs strongly against selection".

## 5. Comparison record (spec §9)

| Field | Content |
|---|---|
| Candidate | Sokol111 ecommerce workspace, revisions in the freeze doc |
| Change | Add a field to `ProductUpdatedEvent` |
| Expected boundary | Catalog (producer), Product Query + Image (consumers), api contract, infra config |
| Coding-agent/source result | Complete: producer, both consumers, groups, environments, per-consumer field use, rollout order ([baseline](round4-sokol111-baseline.md)) |
| Unresolved source question | Whether consumers actually run/consume per environment; other consumers outside the checkout; deployed versions |
| Distributed evidence | Kafka spans with trace propagation exist in source, but none captured live; consumer groups only in config |
| AIP feasibility | Producer→Topic OBSERVED only with conformant keys; consumers not attributable |
| AIP gap | Ingestion (attribute keys, declaration source) **and semantic** (consumer group) |
| Plausible investigation difference? | **No** with current AIP: the questions the baseline leaves open are exactly the consumer-side ones AIP cannot represent |
| Setup cost | High (live slice needs tenant service, Logto, MinIO) |
| Reproducibility | Poor for a live run; acceptable only as source-derived replay |
| Public-demo value | Medium |
| Verdict | **Reject** (fall through to sminerport per spec §3) |
