# Quarkus Super Heroes — Runtime Profile Artifacts (I2.2)

Supporting mechanics for `../runbook.md`. See `../upstream.md`/`../profile.md`/`../ground-truth.md`
for the pinned identity and the ground truth these artifacts exercise.

## Contents

```text
docker-compose.yml          the bounded I2 profile: infra + the 6 pinned-SHA-built service images
                             + AIP + Neo4j + an OTel Collector
otel-collector-config.yaml  OTLP receiver -> AIP /v1/traces exporter, adapted from
                             examples/runtime-demo/otel-collector-config.yaml
traffic.sh                  deterministic curl traffic script (I2 spec §19)
declarations/               AIP import-ready declared-source tree (app/ingestion/scanner.py
                             conventions: one subdirectory per service slug)
```

## Provenance of captured upstream files

`declarations/{rest-fights,rest-heroes,rest-villains,rest-narration}/openapi.yml` are **verbatim,
byte-identical copies** of the pinned upstream contracts (Apache-2.0 licensed, same license as this
repository — see `../upstream.md`):

```text
rest-fights/openapi.yml    <- rest-fights/src/main/resources/openapi/openapi.yml
                               @ 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
rest-heroes/openapi.yml    <- rest-heroes/src/main/resources/openapi/openapi.yml
                               @ 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
rest-villains/openapi.yml  <- rest-villains/src/main/resources/openapi/openapi.yml
                               @ 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
rest-narration/openapi.yml <- rest-narration/src/main/resources/openapi/openapi.yml
                               @ 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
```

Full permalinks: `../evidence/rest-and-grpc.md`. No content was edited (not even a provenance
comment inserted) — provenance lives here instead, per I2 spec §21's upstream-modification policy
(a source modification, even a comment, is avoided when it isn't needed).

`declarations/rest-fights/architecture.yaml` is **new**, authored by this dossier, not copied from
upstream. It transcribes the `CALLS` ground truth already independently established in
`../ground-truth.md` from `rest-fights`' own client source code (`HeroRestClient`/`VillainClient`/
`NarrationClient`) — it is not derived from any AIP output (I2 spec §28). `test_quarkus_runtime_manifest.py`
guards it against drifting from that ground truth.

## Why the compose file builds images instead of pulling `:java25-latest`

The official upstream `deploy/docker-compose/java25.yml` (CI-generated) pulls
`quay.io/quarkus-super-heroes/<service>:java25-latest`. That tag is a rolling build, not pinned to
our exact commit — at research time it predated our pinned commit by six days (which itself bumps
the Quarkus platform version), so it does not reliably represent
`8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce`. I2 spec §4 requires the qualifying run to apply to the
exact pinned commit, not a moving tag, so `docker-compose.yml` here builds each of the six required
services' images from source at the pinned SHA instead of pulling the floating tag (see
`../runbook.md` phase 3). Environment wiring for datasource URLs/Stork discovery/Kafka
bootstrap/Apicurio registry is carried over unchanged from the official upstream compose, since
none of that is affected by which exact commit is built.

## Why every infra image is pinned to an exact version (PR #40 review F1)

A "reproducible runtime profile" means every image the profile controls resolves to the same
version on every run, not only the Quarkus application images. The official upstream compose's
`neo4j:5`/`mongo:8`/`postgres:18`/`mariadb:11.5` and a plain `otel/opentelemetry-collector:latest`
are all moving major-only or `latest` tags that can silently resolve to a different image between
two runs of this same frozen profile. `docker-compose.yml` therefore pins each ordinary
infrastructure image to an exact version that existed at research time (`neo4j:5.26.0`,
`mongo:8.3.8`, `postgres:18.6`, `mariadb:11.5.2`) — registry tags are not technically immutable,
but this closes off the moving-tag failure mode the official compose had. The OTel Collector gets
the stronger byte-level guarantee: because it sits directly on the OTLP evidence path (Quarkus
spans → Collector → AIP `/v1/traces`), it is additionally pinned by digest
(`otel/opentelemetry-collector:0.159.0@sha256:...`). The containerized Maven build image
(`runbook.md` phase 3) is likewise pinned to `maven:3.9.16-eclipse-temurin-25`, not a
`3.9`/`latest` floating tag.
