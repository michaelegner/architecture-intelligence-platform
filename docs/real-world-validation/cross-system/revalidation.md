# I4.4 — Final-Candidate Real-System Revalidation

Spec §27's I4.4 scope: "Deliver clean Quarkus and Airflow runs against the same final candidate,
actual-facts/report hashes, comparison reports, final dispositions, and known limitations." Spec §19
("no substitution") requires this real-system execution regardless of I4.1/I4.2's `NO_CHANGE`
outcome — a source diff or content-equivalence argument does not satisfy it.

Both profiles were executed twice each, back-to-back, from clean state, against the identical pinned
AIP candidate image — never rebuilt between runs — per spec §20's repeatability requirement.

## Candidate identity (spec §3 / §20)

```text
AIP candidate SHA:        9f95d48046ab1942bb1a77c9a3a887a542120b98
Dependency lock (uv.lock) SHA-256:
                           7945b63c47391d7bd81a9c7025dc2004907c33db6147cb169795357a27381a6a
AIP candidate image:       aip-candidate-9f95d48 (local build, not pushed to a registry)
AIP image ID:              sha256:67a27be2ec4ea370f24ad6b3e0129d58400b27fbdd2cf20ac3128482365d5aa2
```

The same image ID was verified (`docker inspect ... --format='{{.Image}}'`) as the running
`architecture-intelligence` container in every one of the four runs below — the image was built
once, before any run, and reused unmodified throughout, so no run could have been comparing against
a different candidate build.

```text
Environment:  Linux 5.15.153.1-microsoft-standard-WSL2 x86_64
Docker:       29.7.2
Compose:      v5.3.1 (Compose v2 spec)
```

## Quarkus Super Heroes

```text
Upstream commit:            8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
Profile revision:           docs/real-world-validation/quarkus-super-heroes/runtime/ @ 9f95d48
Ground-truth revision:      docs/real-world-validation/quarkus-super-heroes/expected.yaml @ 9f95d48
Comparison-tool revision:   real_world_validation/ @ 9f95d48
Base image (all 6 services): registry.access.redhat.com/ubi10/openjdk-25-runtime:1.24
                             @sha256:68525bc239f93a62070625354e3b863be0963f61f1338794011665d5b8a946f5
```

Service images (all six built fresh from the pinned upstream commit, containerized
`maven:3.9.16-eclipse-temurin-25`, immediately before run 1 and reused unmodified for run 2):

```text
rest-fights:8ea0337         sha256:e2d3a3bfb61878342c1922dbe223bb18b521b0d6c21dd655a61d979b15b0823c
rest-heroes:8ea0337         sha256:2d1aca9454dec5b4cd508b6b61d72c5411efbe79458826fd92ec04753e215c67
rest-villains:8ea0337       sha256:ac7ca03053fd09aebb4a8d8bf851f6eddce181175023ec6f42c3073f9bb37e99
rest-narration:8ea0337      sha256:da43f7def254c5fa536c884d1949f1b0a878bffb06266d34d2e1a14f5ca38fbd
event-statistics:8ea0337    sha256:64b35d4a668c4dca7e8dcf196273cff5b9fdf3503f52c17549c774fd5f3a9cdc
grpc-locations:8ea0337      sha256:d11439741f5ae923565e974db79a66a2492d86790fdc93ccdfe3be11882f3da2
otel-collector               otel/opentelemetry-collector:0.159.0
                             @sha256:7725a7a10c87d8853208bdd4bb3439ad3c0d7b32b4292b9300ac07c8daba14a2
```

Provider/instrumentation: Quarkus's own built-in OpenTelemetry extension, unmodified from the pinned
upstream commit — no source-code instrumentation change (I2 spec §16, still true here).

### Run 1

```text
window_start:                2026-09-02T06:08:02Z
window_end (drain-widened):  2026-09-02T06:08:15Z
```

Bounded readiness gate passed for every service on the first pass. `POST /api/import` returned
`nodes_written`/`relations_written` of 22/23, 14/16, 8/6, 14/16 for
fights/heroes/narration/villains — identical to the I2.3/I2.4 baseline. `traffic.sh` ran once. The
raw phase-9 drain check (bound to the raw `window_end`, `06:08:04Z`) initially observed only 2 of 3
`CALLS` relations; the third (`rest-fights -> rest-narration`) landed at `06:08:09.24Z`, ~5s after
the raw traffic completion — the same narration-fallback OTLP lag the I2.4 dossier documents
(`quarkus-super-heroes/results.md`'s "Revalidation (I2.4)"). Per that same precedent this is an
operator choice about how generously to draw the capture window, not a change to the comparison
contract: the capture's `--until` was widened to `06:08:15Z` to include the already-landed span
before treating the window as closed, and comparator invocation happened only after that widened
capture confirmed all three `CALLS` relations `CONFIRMED`.

```text
Expected supported facts:      38
Correct:                       38
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         2
Unresolved identities:          0
Insufficient evidence:           0
Critical semantic errors:        0
```

Identical to the frozen I2.3/I2.4 summary in every classification.

Artifacts: [`artifacts/quarkus-actual.yaml`](artifacts/quarkus-actual.yaml)
(SHA-256 `8baff3a9a9f0480f5f0d2c144008ee4f075d3eda538ed4ac5f171df51b209b1a`),
[`artifacts/quarkus-compare.txt`](artifacts/quarkus-compare.txt)
(SHA-256 `4c34ae89d32209ab178dfc5b72bfd903ce47580c389b6e6381282303b7627309`).

### Run 2 (repeatability)

Full teardown (`docker compose down -v`) after run 1, fresh `NEO4J_PASSWORD`, same unmodified
service images and same pinned AIP image (verified by image ID again before traffic). Import
returned identical counts. `traffic.sh` ran once; this time the drain check's own window
(`since`=window_start, `until`=window_start+14s) already included all 3 `CALLS` relations by the
time it first polled, so no widening was needed for capture.

```text
window_start:  2026-09-02T06:12:06Z
window_end:    2026-09-02T06:12:20Z
```

```text
Expected supported facts:      38
Correct:                       38
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         2
Unresolved identities:          0
Insufficient evidence:           0
Critical semantic errors:        0
```

Artifacts: [`artifacts/quarkus-actual-revalidation.yaml`](artifacts/quarkus-actual-revalidation.yaml),
[`artifacts/quarkus-compare-revalidation.txt`](artifacts/quarkus-compare-revalidation.txt).

### Repeatability result

```text
diff quarkus-actual.yaml quarkus-actual-revalidation.yaml         -> byte-identical
diff quarkus-compare.txt quarkus-compare-revalidation.txt         -> byte-identical
SHA-256 (both actual.yaml files):  8baff3a9a9f0480f5f0d2c144008ee4f075d3eda538ed4ac5f171df51b209b1a
SHA-256 (both compare.txt files):  4c34ae89d32209ab178dfc5b72bfd903ce47580c389b6e6381282303b7627309
```

Two independent runs against the literal `9f95d48` candidate: same images, same profile, same
frozen `expected.yaml`, byte-identical captures, byte-identical comparator output. Spec §20's
repeatability requirement is met in full (stronger than "SHOULD have identical semantic results" —
these are byte-identical, not merely semantically equivalent).

## Apache Airflow

```text
Upstream image:              apache/airflow:3.3.1
                             @sha256:0c4bcc0370e526de1b7892a3bf4343d260c6c82359c66f77155b53cd773d6339
Profile revision:            docs/real-world-validation/apache-airflow/runtime/ @ 9f95d48
Ground-truth revision:       docs/real-world-validation/apache-airflow/expected.yaml @ 9f95d48
Comparison-tool revision:    real_world_validation/ @ 9f95d48
Postgres:                    postgres:16.15@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94
Redis:                       redis:7.2-bookworm@sha256:74566c6910d13ae61e7ce73ebd3127438a1fe805b309b097c323142719ec8a5b
otel-collector:               otel/opentelemetry-collector:0.159.0
                             @sha256:7725a7a10c87d8853208bdd4bb3439ad3c0d7b32b4292b9300ac07c8daba14a2
Workers:                     AIRFLOW_WORKERS=2 (both runs — matches I3 spec §9's preferred
                             multiple-runtime-instance configuration)
```

Provider/instrumentation: Airflow's native tracing, unmodified from the pinned release image — no
diagnostic Celery instrumentation was added (I4.1's `runtime-role-identity` and
`airflow-celery-messaging-runtime-status` decisions remain `DEFER`/`DOCUMENT_UNSUPPORTED`; this
revalidation does not reopen either).

### Run 1

```text
window_start:  2026-09-02T06:17:52Z
window_end:    2026-09-02T06:18:26Z
```

Bounded readiness gate (apiserver, scheduler, dag-processor, triggerer, both workers, DAG
registration) passed on the first pass. `POST /api/import` returned `nodes_written: 223,
relations_written: 512` — identical to the frozen I3 baseline. `traffic.sh` triggered
`i3_validation` (`dag_run_id=aip-i3-validation`); both tasks reached `success` on `queue=default`,
running on two distinct worker container hostnames (`ddcdfb8f538a`, `c9de510752a7`), directly
exercising the multiple-runtime-instance configuration. The AIP-access-log drain barrier (I3's valid
system-shape-independent drain signal, since `/api/runtime/relations` legitimately stays empty for
Airflow's native task/dagrun spans) confirmed ingestion before capture.

```text
Expected supported facts:      9
Correct:                       9
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         3
Unresolved identities:          2
Insufficient evidence:           1
Critical semantic errors:        0
```

Identical to the frozen I3.3/I3.4 summary in every classification.

Artifacts: [`artifacts/airflow-actual.yaml`](artifacts/airflow-actual.yaml)
(SHA-256 `1d8a0db7741b0f108f4a23c78113e6cfb3466c01a975eac660b5ab2d7c026419`),
[`artifacts/airflow-compare.txt`](artifacts/airflow-compare.txt)
(SHA-256 `bc05e5cbb22a22175e3fdeb3112c40875f61907708a07fbcf35da316c0274d36`).

### Run 2 (repeatability)

Full teardown (`docker compose down -v` — Postgres, Redis, Neo4j, and the named
`airflow-i3-logs`/`-config`/`-plugins` volumes all removed) after run 1, fresh
`NEO4J_PASSWORD`/`FERNET_KEY`, same pinned AIP image (verified again), same unmodified
`apache/airflow:3.3.1` digest. Import returned identical counts. `traffic.sh` ran once; both tasks
succeeded on `queue=default` on worker hostname `d24726a67b91`.

```text
window_start:  2026-09-02T06:21:54Z
window_end:    2026-09-02T06:22:27Z
```

```text
Expected supported facts:      9
Correct:                       9
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         3
Unresolved identities:          2
Insufficient evidence:           1
Critical semantic errors:        0
```

Artifacts: [`artifacts/airflow-actual-revalidation.yaml`](artifacts/airflow-actual-revalidation.yaml),
[`artifacts/airflow-compare-revalidation.txt`](artifacts/airflow-compare-revalidation.txt).

### Repeatability result

```text
diff airflow-actual.yaml airflow-actual-revalidation.yaml         -> byte-identical
diff airflow-compare.txt airflow-compare-revalidation.txt         -> byte-identical
SHA-256 (both actual.yaml files):  1d8a0db7741b0f108f4a23c78113e6cfb3466c01a975eac660b5ab2d7c026419
SHA-256 (both compare.txt files):  bc05e5cbb22a22175e3fdeb3112c40875f61907708a07fbcf35da316c0274d36
```

Byte-identical captures and comparator output despite the two runs using different worker container
hostnames — expected and correct: the captured scope (`PROVIDES`, `SENDS`, `RECEIVES_FROM`) contains
no fact derived from worker hostname, since Celery sender/consumer identity remains
`INSUFFICIENT_EVIDENCE`/unresolved by design (I4.1's `runtime-role-identity` decision). Spec §20's
repeatability requirement is met in full.

## Final dispositions

No new finding was discovered during this revalidation. Every finding in
[`finding-ledger.md`](finding-ledger.md) keeps the disposition I4.1 assigned; nothing here reopens
`hardening.md`'s `NO_CHANGE` record or any decision in `decisions/`. Both systems reproduce, against
the literal `v0.3.0-rc.1` candidate, the exact classification counts their own frozen dossiers
recorded:

```text
Quarkus:  CORRECT 38, UNSUPPORTED 2, all other classifications 0
Airflow:  CORRECT 9, UNSUPPORTED 3, UNRESOLVED_IDENTITY 2, INSUFFICIENT_EVIDENCE 1, all others 0
```

Material `INCORRECT_SUPPORTED` findings = 0. Critical semantic errors = 0.

## Known limitations (carried forward, unchanged)

```text
gRPC/protobuf calls (Quarkus)                      — unsupported, DOCUMENT_UNSUPPORTED
Kafka topic/subscription semantics (Quarkus)       — unsupported, DOCUMENT_UNSUPPORTED
PostgreSQL/database dependencies (Airflow)         — unsupported, DOCUMENT_UNSUPPORTED
Airflow Execution API caller identity              — unresolved, DEFER
Airflow runtime-role/Celery messaging identity     — unresolved, DEFER
```

None of these is a material `INCORRECT_SUPPORTED` claim; each is an explicit, bounded limitation
per spec §24's non-blocking outcomes.

## Method note

No production code, `expected.yaml`, `docker-compose.yml`, `runbook.md`, or `traffic.sh` changed
between or during any of the four runs. The only per-run inputs that changed were secrets
(`NEO4J_PASSWORD`, `FERNET_KEY`) generated fresh per spec's clean-state requirement (I1 §29). Both
compose profiles were pointed at the single pre-built `aip-candidate-9f95d48` image via a local,
untracked `docker-compose.override.yml` (`image:` key layered onto the committed `build:` key so
Compose reused the existing tagged image instead of rebuilding) — this override is gitignored
(`.gitignore` already lists `docker-compose.override.yml`) and is not part of this commit; it exists
only to guarantee, per spec §20's identity requirement, that all four runs measured the exact same
candidate image rather than four separately built (and potentially non-identical) images from the
same source.
