# Upstream Identity: `apache-airflow` (v0.5.0)

I5 spec §5 (Draft 0.3) requires these fields. They were reconfirmed on 2026-09-24 against a fresh
fetch of the pinned commit and the GitHub tag API. A changed pin requires a documented reason, a
fresh ground-truth review, and a new freeze.

```text
system:                      apache-airflow
repository:                  https://github.com/apache/airflow
release / tag:               3.3.1, annotated tag object 8d7af742565409cf8857c92c1cec98568dae4296
                             (tagged 2026-08-12T08:47:45Z)
commit:                      3adbbe1c58e4532df1964cb7794805e763816ee8
                             "Update 3.3.1 release notes and date for rc2"
validation profile revision: this dossier's merge commit (the freeze)
validation date:             2026-09-24 (freeze drafted; no qualifying run yet)
```

## Upstream sources used as inputs or evidence

| Source at the pin | Identity | Use |
| --- | --- | --- |
| `airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml` | git blob `34068eab85b936036b3304fae1985e86230c7fb0`, sha256 `2c57114da43a131f68772f1660ed52ca7116089a20893ac5e5f6225ffde3abd9` ("Airflow API 2", 88 paths, 128 operations) | Copied verbatim to `runtime/declarations/airflow-apiserver/openapi.yml` (upstream-supplied) |
| `airflow-core/docs/howto/docker-compose/docker-compose.yaml` | git blob `6a8891f3f58cc5e37e27ac02c16604d0f1e90b88`, sha256 `eb35701a5e74a8578755b3b544105769fb2c6703b15e47864138a7711a2480a9` | The official Compose. The profile in `runtime/docker-compose.yml` derives from it; the differences are listed in its header. It is evidence for the component inventory. |
| `airflow-core/src/airflow/config_templates/config.yml` | at the pin | Configuration defaults (`[operators] default_queue`, `[traces]`) |
| `airflow-core/src/airflow/api_fastapi/app.py`, `.../execution_api/` | at the pin | The Execution API boundary |
| `shared/observability/src/airflow_shared/observability/traces/__init__.py` | at the pin | OTel resource identity |

The OpenAPI copy is byte-identical to the file v0.3 used (the same blob). The Airflow OpenAPI and
Compose did not change between the v0.3 freeze and this one, because the pin is the same.

## Image and runtime identities

Airflow ships prebuilt release images, so nothing is built from upstream source. Every image the
profile runs is pinned by digest in `runtime/docker-compose.yml`, and Docker refuses other bytes.
The one exception is the AIP candidate image, which every run rebuilds from the verified candidate
checkout (`runbook.md` step 4).

| Image | Role | Digest |
| --- | --- | --- |
| `apache/airflow:3.3.1` | apiserver, scheduler, dag-processor, worker ×2, triggerer, init | `sha256:0c4bcc0370e526de1b7892a3bf4343d260c6c82359c66f77155b53cd773d6339` (unchanged since v0.3) |
| `postgres:16.15` | metadata database and Celery result backend | `sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6` (resolved 2026-09-24; v0.3 pinned only the tag) |
| `redis:7.2-bookworm` | Celery broker | `sha256:74566c6910d13ae61e7ce73ebd3127438a1fe805b309b097c323142719ec8a5b` (the v0.3-pinned digest, kept and still resolvable. The tag itself now resolves to `sha256:0637954999d0…`, a later rebuild that this profile does not use.) |
| `neo4j:5.26.0` | AIP graph | `sha256:5a015e53de1895e7eee1574ae0325cf8c4b89587222778108c594bdd45a474b5` |
| `otel/opentelemetry-collector:0.159.0` | OTLP routing | `sha256:7725a7a10c87d8853208bdd4bb3439ad3c0d7b32b4292b9300ac07c8daba14a2` |

The digests are multi-arch index digests (`docker buildx imagetools inspect`). Changing one is a
profile change that needs a new freeze (I5 §6). The official Compose lets `AIRFLOW_IMAGE_NAME`
override the image. The profile removes that override, so a run cannot substitute another image.

## License

```text
upstream license: Apache License 2.0 (LICENSE at the pin)
```

AIP does not vendor the upstream repository. This dossier commits only the verbatim public REST
OpenAPI document (Apache-2.0), which the profile needs as an exact input.

## Notes

A validation result applies only to the pinned identities above. v0.3 results for this system are
research input only, never v0.5 qualification results (I5 §5). v0.3 used the same pin.
