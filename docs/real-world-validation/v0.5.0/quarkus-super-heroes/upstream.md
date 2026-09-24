# Upstream Identity: `quarkus-super-heroes` (v0.5.0)

I5 spec §5 (Draft 0.3) requires these fields. They were reconfirmed on 2026-09-24 against a fresh
fetch of the pinned commit. A changed pin requires a documented reason, a fresh ground-truth review,
and a new freeze.

```text
system:                      quarkus-super-heroes
repository:                  https://github.com/quarkusio/quarkus-super-heroes
project version/tag:         none (main-branch commit)
commit:                      8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
                             "Bump quarkus.platform.version from 3.38.3 to 3.39.1 (#2262)",
                             committed 2026-08-31T11:49:10Z
validation profile revision: this dossier's merge commit (the freeze)
validation date:             2026-09-24 (freeze drafted; no qualifying run yet)
```

## Image and runtime identities

| Image | Role | Identity |
| --- | --- | --- |
| `quarkus-super-heroes/{rest-fights,rest-heroes,rest-villains,rest-narration,event-statistics,grpc-locations}:8ea0337` | The six services, built locally from the pin | Build recipe: `runbook.md` step 3. Each is built with `maven:3.9.16-eclipse-temurin-25` and the service's own `src/main/docker/Dockerfile.jvm`. The built image digests are recorded at run time in `results.md` and disclosed as run-time identities (see below). |
| `maven:3.9.16-eclipse-temurin-25` | Build container | `sha256:dd8e01b3be719853578c07b57ff8d9bbbbfe746f802226f05b19689420815221` |
| `registry.access.redhat.com/ubi10/openjdk-25-runtime:1.24` | Base image of every upstream `src/main/docker/Dockerfile.jvm` | `sha256:c49d36c03d0a9472935b9f318f709c4cf158afa2dc204099f1f463cfbf9d4626` |
| `neo4j:5.26.0` | AIP graph | `sha256:5a015e53de1895e7eee1574ae0325cf8c4b89587222778108c594bdd45a474b5` |
| `otel/opentelemetry-collector:0.159.0` | OTLP routing | Pinned by digest in `runtime/docker-compose.yml`: `sha256:7725a7a10c87d8853208bdd4bb3439ad3c0d7b32b4292b9300ac07c8daba14a2` |
| `mongo:8.3.8` | fights-db | `sha256:5211c51171f57ae60842b11664bb244628971b3d35325762a97888337b9bb0db` |
| `quay.io/apicurio/apicurio-registry:3.1.7` | Schema registry | `sha256:3ff121c9f744d535ef770b80ff95693bc95063295316a5864b56312b6edfb4e2` |
| `apache/kafka-native:4.2.0` | Kafka | `sha256:777f2dddec6970003f1f27922a8c317d87140567b0537e801d35669ad9a81faf` |
| `postgres:18.6` | heroes-db, villains-db | `sha256:5a5a84b19854a9ffaa54082c166ff4ec27473a361e496e5ea167f298f2da9722` |
| `mariadb:11.5.2` | locations-db | `sha256:2d50fe0f77dac919396091e527e5e148a9de690e58f32875f113bef6506a17f5` |

The third-party digests are the multi-arch index digests that the tags resolved to on 2026-09-24
(`docker buildx imagetools inspect <tag>`). They are enforced, not only recorded (PR #240 review):
- `runtime/docker-compose.yml` references every third-party runtime image as `<tag>@<digest>`, so
  Docker cannot run other bytes;
- `runbook.md` step 3 pulls the Maven builder and the `Dockerfile.jvm` base by digest, and builds
  the unmodified upstream Dockerfiles on exactly that base.

Changing any of these digests is a profile change that needs a new freeze (I5 §6).

The six service images cannot carry a pre-run digest. They are built locally from the pin, and a
local build is not byte-reproducible. Their identity for the freeze is therefore the pinned commit,
the frozen builder and base digests, and the build recipe. Every run rebuilds them from scratch
(`--no-cache`, fresh clone) and records their image ids. It then checks that the running containers
use exactly those ids before any import or traffic (`runbook.md` steps 2-5).

**Framework identity.** The pin's `quarkus.platform.version` is 3.39.1 (the commit title). The
REST services use the Quarkus REST client with Stork static discovery. Messaging uses SmallRye
Reactive Messaging Kafka with Apicurio Avro. See `ground-truth.md` for the citations.

## Upstream Kubernetes manifests (I5 §5)

```text
present at the pinned commit: yes
selected variant:             deploy/k8s/java25-kubernetes.yml   (owner decision, 2026-09-24)
upstream git blob:            4cdda1965c5552b17af951d771475ad8678d1032
sha256 (unmodified):          a1cd818385b3bbb582be12d5e43960f3f1ce85a619e5a974bc5c3b03c94d2c25
                              copied verbatim to runtime/k8s/unmodified/java25-kubernetes.yml
namespace transform (I5 §5):  runtime/k8s/derive_namespaced.py, namespace "quarkus-super-heroes"
sha256 (namespace-derived):   4ba52254b4a331590f1f7b1a43ae9f89a813dc7885938769bcdac8cd907d1cd2
                              runtime/k8s/namespaced/java25-kubernetes.namespaced.yml
service-id annotations:       absent on every Workload (see the table below)
```

**What upstream says about these files.** `deploy/k8s/README.md` at the pin says the files are
generated during CI/CD (`scripts/generate-k8s-helm-resources.sh`). The upstream deployment guide
(`docs/src/main/resources/content/deploying.md:26`) applies a variant with `kubectl apply -f`, and
it names no namespace. No resource in the file sets `metadata.namespace`. So the namespace is
operator deployment context, and that is why I5 §5 freezes the negative case and the derived copy
both.

**Generation provenance.** The file carries upstream build annotations such as
`app.quarkus.io/commit-id: fa5a29db43200a0cf0ca0fe1f10e1218687a4062` and
`app.quarkus.io/quarkus-version: 3.38.3` (for example on the Ingress, `java25-kubernetes.yml:2151-2152`).
CI therefore generated it from an earlier upstream commit than the pin, and it references rolling
`java25-latest` images. It is still the file present at the pin, and I5 §5 names that file. It is
declared deployment configuration, not a description of the locally built Compose images.

**Other variants, not used.** At the pin, `deploy/k8s/` also contains `native-kubernetes.yml`,
`{java25,native}-{minikube,knative,openshift}.yml` and `monitoring-*.yml`. Each service also has
its own `<service>/deploy/k8s/*-kubernetes.yml`.

### Per-Workload Path A annotation record (I5 §8.1)

Every `apps/v1` Deployment in the file is listed. The annotation checked is
`architecture-intelligence.io/service-id`, on both the Deployment and its Pod template.

| Deployment | Upstream line | Path A annotation | In I5 §8.1 scope |
| --- | --- | --- | --- |
| `rest-fights` | 1465 | absent | yes |
| `rest-heroes` | 925 | absent | yes |
| `rest-villains` | 636 | absent | yes |
| `rest-narration` | 346 | absent | yes |
| `event-statistics` | 1869 | absent | yes (messaging boundary) |
| `grpc-locations` | 181 | absent | no (excluded) |
| `ui-super-heroes` | 2023 | absent | no (excluded) |
| `fights-db`, `fights-kafka`, `apicurio` | 1282, 1345 (and 1749), 1403 (and 1807) | absent | no (infrastructure) |
| `heroes-db`, `villains-db`, `locations-db` | 862, 574, 112 | absent | no (infrastructure) |

No Workload is Path A-evaluable. Under I5 §8.1, both real-target cases that need an unannotated
Workload are therefore available: the configured-only positive and the name-only negative.

## License

```text
upstream license: Apache License 2.0 (LICENSE at the pin)
```

AIP does not vendor the upstream repository. This dossier commits only four verbatim OpenAPI
documents, one verbatim Kubernetes manifest, and its namespace-derived copy. All are
Apache-2.0-licensed upstream content that the I5 profile needs as exact inputs. The Kubernetes
manifest contains upstream demo Secrets with default credentials (for example `locations`). I2
omits Secret objects as unsupported and never stores their contents (I2 §5).

## Notes

A validation result applies only to the pinned identities above. v0.3 results for this system are
research input only, never v0.5 qualification results (I5 §5). v0.3 used the same pin.
