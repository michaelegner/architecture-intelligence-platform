# Validation Profile: `quarkus-super-heroes` (v0.5.0)

This is the bounded, reproducible profile that I5 Slice 5 exercises (I5 §6 item 1, §8.1). It is
carried over from the v0.3 I2 profile (`../../quarkus-super-heroes/profile.md`), with the v0.5
additions below. The owner's merge of this dossier freezes it.

## Input classification (I5 §6, Draft 0.3)

Every input falls into exactly one of four kinds, and no input is presented as another kind.

| Input | Kind | Path | Content identity |
| --- | --- | --- | --- |
| OpenAPI `rest-fights` | upstream-supplied | `runtime/declarations/rest-fights/openapi.yml` | sha256 `6ddbcf5b750b156b0445227b3fb5a51a6b6492f8d10b8c4dac72f1fa40eb1275`, byte-identical to upstream `rest-fights/src/main/resources/openapi/openapi.yml` |
| OpenAPI `rest-heroes` | upstream-supplied | `runtime/declarations/rest-heroes/openapi.yml` | sha256 `6068d22ef8a4f16d48c48f5c650e6afaee98b54b2ec87dcd2760d920064fb980`, byte-identical to upstream |
| OpenAPI `rest-villains` | upstream-supplied | `runtime/declarations/rest-villains/openapi.yml` | sha256 `8c2fec17445d17990bf27bab024f22b31150c78c22cb349d904b79dc5e328473`, byte-identical to upstream |
| OpenAPI `rest-narration` | upstream-supplied | `runtime/declarations/rest-narration/openapi.yml` | sha256 `686351d7e0777c738696f0dc3a80dd0e5c49db2afd0426a3e4142f22aa2f0bef`, byte-identical to upstream |
| Kubernetes manifest, unmodified | upstream-supplied | `runtime/k8s/unmodified/java25-kubernetes.yml` | sha256 `a1cd818385b3bbb582be12d5e43960f3f1ce85a619e5a974bc5c3b03c94d2c25`, byte-identical to upstream `deploy/k8s/java25-kubernetes.yml` |
| Kubernetes manifest, namespace-derived | **upstream-derived** (I5 §5) | `runtime/k8s/namespaced/java25-kubernetes.namespaced.yml` | sha256 `4ba52254b4a331590f1f7b1a43ae9f89a813dc7885938769bcdac8cd907d1cd2`. Produced from the unmodified file by `runtime/k8s/derive_namespaced.py`, namespace `quarkus-super-heroes`. |
| OTLP traces from the running services | independently captured | via `runtime/otel-collector-config.yaml` | The observation window of the qualifying run |
| rest-fights Architecture Manifest (7 `CALLS`) | AIP operator configuration | `runtime/declarations/rest-fights/architecture.yaml` | Freeze commit |
| OpenAPI identity bindings (I1 §4.1 path 3) | AIP operator configuration | `runtime/declarations/identity-bindings.yaml` | Freeze commit |
| Path B mapping artifact (3 entries) | AIP operator configuration | `runtime/mapping.yaml` | Freeze commit |
| Kubernetes snapshot envelopes, cluster identity, producer, authority | AIP operator configuration | `runtime/k8s/{namespaced,unmodified}/envelope.yaml`, `runtime/config.quarkus-i5.yaml` | Freeze commit |
| Namespace name `quarkus-super-heroes` | AIP operator configuration | `runtime/k8s/derive_namespaced.py` | Freeze commit |
| AIP configuration | AIP operator configuration | `runtime/config.quarkus-i5.yaml` | Freeze commit |

The upstream-supplied and upstream-derived digests above are also asserted by
`tests/unit/test_quarkus_v05_dossier.py`. For operator configuration, "freeze commit" means the
content identity is the git blob at the dossier's merge commit. List the blobs with:
`git ls-tree -r <freeze-commit> docs/real-world-validation/v0.5.0/quarkus-super-heroes/runtime`.

**Declared cluster identity.** `qsh-i5-declared-deployment-target` is the operator's name for the
cluster these manifests are declared for. No real cluster exists in this profile (I5 §4.2), so the
identity is attributable only to this profile. `qsh-i5-profile-declared-cluster-identity` in both
envelopes refers to this paragraph. Both Kubernetes sources use the same declared cluster
identity. They are separate configured sources (`qsh-k8s-namespaced` and
`qsh-k8s-upstream-unmodified`), so they have separate SourceInstanceIds.

## Components/processes started

These are unchanged from v0.3:
- the services `rest-fights`, `rest-heroes`, `rest-villains`, `rest-narration` and
  `event-statistics`;
- `grpc-locations`, because rest-fights needs it to start, although it is outside the compared
  scope;
- the datastores, Kafka and Apicurio;
- Neo4j, the pinned OTel Collector, and AIP itself.

`ui-super-heroes` is not started. The Kubernetes manifests are **only declarations**: nothing is
deployed to Kubernetes (I5 §4.2).

## Runtime/deployment mode

The runtime is Docker Compose (`runtime/docker-compose.yml`), with images built locally from the pin
in JVM mode (`upstream.md`). The Kubernetes input is imported offline as `DECLARED_MANIFEST`. It
does not describe the Compose runtime, and the Compose runtime supplies no Pod UIDs, so Path C is
not exercised (I5 §8.1).

## Telemetry configuration

This is unchanged from v0.3, except for the environment name:
- each service exports OTLP to the pinned Collector;
- the Collector forwards to AIP's `/v1/traces`;
- `deployment.environment.name=quarkus-i5`;
- there is no source instrumentation change.

## Architecture flows exercised

`runtime/traffic.sh` is unchanged from v0.3, and its calls run in this order:
1. `GET /api/fights/randomfighters`, which calls rest-heroes random and rest-villains random;
2. `GET /api/fights/randomlocation`, which calls gRPC and is unsupported;
3. `POST /api/fights`, which persists the fight and publishes to Kafka `fights`;
4. `POST /api/fights/narrate`, which calls rest-narration `POST /api/narration`.

The four rest-fights calls to the `hello` endpoints and `POST /api/narration/image` are
deliberately not exercised (`ground-truth.md`, "REST calls").

## Supported AIP semantics in scope

| I5 §7 fact class | In this profile |
| --- | --- |
| `PROVIDES`, `CALLS` | yes: 35 and 7 |
| `SENDS`, `PUBLISHES_TO`, `RECEIVES_FROM` | in scope as negatives only (Kafka `fights`) |
| `SUBSCRIPTION_OF`, `CARRIES` | no service endpoint, so not comparable. No Topic, Queue or Subscription entity may exist (`ground-truth.md`, "Checks the comparator cannot express") |
| `DEPLOYED_AS` | yes: 3 `RESOLVED_CONFIGURED`, 2 forbidden name-only pairs |
| I2 discovery | yes, via the import-result and inventory checks in `ground-truth.md` |

## Known upstream mechanisms out of scope

These are:
- gRPC (`grpc-locations`);
- Kafka `fights` as Pub/Sub or Queue;
- the legacy OTel `messaging.operation` key;
- Apicurio schema registry semantics;
- datastore dependencies (MongoDB, PostgreSQL, MariaDB);
- Kubernetes kinds outside I2 §5 (the 25 frozen `K8S_RESOURCE_UNSUPPORTED` objects);
- the UI.

## Comparison projection, window, and determinism (I5 §6 item 4, §12)

```text
run identity:               The candidate SHA is the HEAD of the clean checkout at the frozen
                            location. The AIP image aip-i5-candidate:<SHA> and the six service
                            images are rebuilt with --no-cache for every run. Third-party, builder
                            and base images are pulled by their frozen digests. The running
                            containers are verified against these before any import or traffic
                            (runbook.md steps 2-5; PR #240 review).
observation environment:    quarkus-i5
observation window:         [WINDOW_START, WINDOW_END], derived by runbook.md step 9. WINDOW_END is
                            when the three exercised CALLS are first CONFIRMED, bounded by 60s.
comparison projection:      expected.yaml scope. 5 Services, and PROVIDES, CALLS, SENDS,
                            PUBLISHES_TO and RECEIVES_FROM, plus public DEPLOYED_AS outcomes for
                            the scoped Services.
absolute checkout location: /home/michael/code/ArchitectureIntelligencePlatform
                            Both §12 byte-identity evaluations run from this one path. The
                            target run's declared sources are mounted at the fixed container path
                            /app/declarations, so the target-run evidence paths do not depend on
                            the host checkout.
normalization policy:       - The comparator report is compared byte-for-byte between paired runs.
                            - In actual.yaml, only these run-bound fields may differ between runs:
                              the window bounds, captured_at-style timestamps, and each
                              resolution_id (it hashes the snapshot id, which includes observed
                              evidence).
                            - Nothing is normalized by location (I5 §12).
                            - The raw actual.yaml of every run is retained.
rerun criteria:             A comparison is rerun only after a documented clean-state reset, and
                            only for one of three reasons:
                            (a) a runbook readiness or window-close step failed and is documented;
                            (b) a new candidate (I5 §12);
                            (c) a §6 post-freeze correction.
                            A rerun never replaces a failed comparison.
```

## Startup, traffic, and shutdown procedures

See `runbook.md`. Clean state is `docker compose down -v` before startup. That removes the Neo4j,
datastore and Kafka volumes, so no run depends on data from an earlier run.
