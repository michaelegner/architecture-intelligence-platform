# Runtime inputs: `apache-airflow` (v0.5.0)

| Path | What it is | I5 §6 kind |
| --- | --- | --- |
| `declarations/airflow-apiserver/openapi.yml` | The upstream public REST OpenAPI, byte-identical to the pin | upstream-supplied |
| `declarations/bindings/architecture-identity-bindings.yaml` | The I1 §4.1 path 3 Service binding for the OpenAPI source | AIP operator configuration |
| `config.airflow-i5.yaml` | The AIP configuration: one declarations source, with no Kubernetes and no mapping | AIP operator configuration |
| `dags/i3_validation.py` | The validation workload, carried over unchanged from v0.3 | AIP operator configuration |
| `traffic.sh` | The frozen traffic, carried over unchanged from v0.3 | AIP operator configuration |
| `docker-compose.yml` | The profile derived from the official Compose. Every third-party image is pinned by digest, and AIP is rebuilt per run. | AIP operator configuration |
| `otel-collector-config.yaml` | The Collector routing, carried over unchanged from v0.3 | AIP operator configuration |
