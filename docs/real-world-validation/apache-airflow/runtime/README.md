# Apache Airflow — Runtime Profile Artifacts (I3.2)

Supporting mechanics for `../runbook.md`. See `../upstream.md`/`../profile.md`/`../ground-truth.md`
for the pinned identity and the ground truth these artifacts exercise.

## Contents

```text
docker-compose.yml          the bounded I3 profile: Airflow (CeleryExecutor + Redis + Postgres) +
                             AIP + Neo4j + an OTel Collector
config.airflow-i3.yaml      AIP configuration for this profile (sources.directories, environment)
otel-collector-config.yaml  OTLP receiver -> AIP /v1/traces exporter + debug/raw evidence exporter,
                             same shape as examples/runtime-demo/otel-collector-config.yaml
dags/i3_validation.py       the I3 spec §32 deterministic validation Dag
traffic.sh                  deterministic traffic script (I3 spec §33)
declarations/               AIP import-ready declared-source tree (app/ingestion conventions: one
                             subdirectory per service slug)
```

## Provenance of captured upstream files

`declarations/airflow-apiserver/openapi.yml` is a **verbatim, byte-identical copy** of the pinned
official generated contract (Apache-2.0 licensed, same license as this repository — see
`../upstream.md`):

```text
declarations/airflow-apiserver/openapi.yml
    <- airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml
       @ 3adbbe1c58e4532df1964cb7794805e763816ee8
```

No content was edited (not even a provenance comment inserted) — provenance lives here instead, per
I3 spec's upstream-modification policy (matching the same policy Quarkus's I2.2 `runtime/README.md`
followed). The complete 88-path document is imported; comparator scope stays bounded to the 9
selected operations frozen in `../expected.yaml` (I3 spec §16 — the full document MAY be imported
without widening comparison scope).

No `architecture.yaml` manifest exists in `declarations/` — I3.1 established no `CALLS` ground truth
for Airflow (`../ground-truth.md`'s "REST caller ground truth"), so there is nothing for a manifest
to transcribe.

`docker-compose.yml` itself is **not** a verbatim copy: it starts from the pinned official
`airflow-core/docs/howto/docker-compose/docker-compose.yaml` @ the same commit (fetched fresh, never
vendored — I1 §36/§39) and is then modified as documented in the file's own header comment (exact
image pins, standard OTel env vars, added AIP/Neo4j/Collector services).

## Why every image the profile controls is pinned, at least to an exact version (PR #40 review F1
## precedent; PR #45 re-review N2 corrected this section's own claims below)

A "reproducible runtime profile" means every image the profile controls resolves to a known, fixed
version on every run, not only the system under test. The official Compose file's own
`postgres:16`/`otel/opentelemetry-collector:latest`-style tags are moving major-only/rolling tags
that can silently resolve to a different image between two runs of this same frozen profile.
`docker-compose.yml` pins every controlled image to at least an exact version tag, and the two
images that sit directly on an evidence path (execution or OTLP) additionally to an exact digest:

```text
apache/airflow    exact version tag (3.3.1) AND exact digest - both the executor's evidence path
                  and the OTel trace-source path
postgres          16 (official file, major-only) tightened to the exact patch resolved at research
                  time, 16.15 - version tag only, not digest-pinned
redis             7.2-bookworm (official file, already an exact minor+distro tag, not major-only)
                  additionally pinned by the exact digest resolved at research time (PR #45 review
                  F5 - a Debian codename tag can still be rebuilt at the same tag)
neo4j             5.26.0 (this repo's own choice, exact patch tag) - version tag only, not
                  digest-pinned
otel-collector    0.159.0 tag AND exact digest, same image already pinned in
                  quarkus-super-heroes/runtime/docker-compose.yml, since it sits directly on the
                  OTLP evidence path (Airflow spans -> Collector -> AIP /v1/traces)
```

## Deliberate deviations from the official Compose file

- `AIRFLOW__CORE__LOAD_EXAMPLES` is set to `'false'` (official default: `'true'`) so `GET
  /api/v2/dags` in `traffic.sh` and any Phase B inspection only ever sees the one Dag this profile
  actually cares about (`i3_validation`) — a setup-correctness simplification (I3.2 spec: "No
  production semantic fix unless required for general setup correctness"), not a semantic change to
  what's being validated.
- The `airflow-init` one-shot command is simplified to just the required steps (directory creation,
  `airflow version`, config-file materialization, DB migration via env vars, ownership fix) — the
  official file's resource-warning preflight script (`echo` diagnostics for low CPU/memory/disk) is
  dropped as non-functional noise; it changes nothing about how the profile actually behaves.
- `env_file: .env` is dropped — this profile expects its few required variables (`NEO4J_PASSWORD`,
  `FERNET_KEY`) to be exported directly (`../runbook.md`), not sourced from an `.env` file.
- `airflow-cli` and `flower` are not started (both are opt-in diagnostic profiles, `--profile debug`
  / `--profile flower`, not required for qualifying traffic — same as Quarkus's `grpc-locations`
  exclusion reasoning where something is present upstream but outside scope).

## OTel wiring

Every `x-airflow-common`-derived service (api-server, scheduler, dag-processor, worker, triggerer)
gets the standard OTel environment variables — never the deprecated
`otel_host`/`otel_port`/`otel_service`/`otel_ssl_active` keys (`../ground-truth.md`'s central
identity finding, which only the backcompat path reads when the standard variables are absent):

```text
AIRFLOW__TRACES__OTEL_ON=True
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_TRACES_EXPORTER=otlp_proto_http
OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=airflow-i3
```

`deployment.environment.name` is not cosmetic: AIP's OTLP receiver
(`app/telemetry/adapter.py`/`app/telemetry/semconv/resources.py`) reads exactly this resource
attribute to tag a span's environment, and **drops** any span missing it rather than guessing one —
so every component must set it, and it must match `config.airflow-i3.yaml`'s
`runtime_analysis.default_environment: airflow-i3` or every runtime-facing AIP query silently
returns zero rows. No per-role `OTEL_SERVICE_NAME` is set, per the frozen Logical Service boundary
decision (`../profile.md`).

**`OTEL_TRACES_EXPORTER` is required, found only by actually running this profile:**
`OTEL_EXPORTER_OTLP_PROTOCOL` is *not* read by Airflow's own exporter selection —
`configure_otel()` (`shared/observability/src/airflow_shared/observability/traces/__init__.py` @ the
pinned commit) picks the exporter class via `_load_exporter_from_env()`, which reads
`OTEL_TRACES_EXPORTER` instead (`otlp` = gRPC, the default; `otlp_proto_http` = HTTP). Without it set
explicitly, every component's default gRPC exporter dialed the Collector's HTTP port and failed
outright (`Failed parsing HTTP/2 ... Trying to connect an http1.x server`) — zero traces reached the
Collector until this was corrected. Full finding: `../profile.md`'s "OTel configuration" section.

Native tracing (the above) exposes task/dagrun/execution-API spans only — no Celery/broker/queue
attributes. `../profile.md`'s "Standard Celery instrumentation decision" section records the I3
spec §29 diagnostic experiment that established this and why it wasn't kept in this frozen profile.
