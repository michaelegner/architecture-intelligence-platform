# Runtime inputs: `quarkus-super-heroes` (v0.5.0)

| Path | What it is | I5 §6 kind |
| --- | --- | --- |
| `declarations/rest-*/openapi.yml` | The four upstream OpenAPI documents, byte-identical to the pin | upstream-supplied |
| `declarations/rest-fights/architecture.yaml` | The seven rest-fights `CALLS`, transcribed from `../ground-truth.md` | AIP operator configuration |
| `declarations/bindings/architecture-identity-bindings.yaml` | The I1 §4.1 path 3 Service bindings for the four OpenAPI sources | AIP operator configuration |
| `k8s/unmodified/` | The upstream `deploy/k8s/java25-kubernetes.yml`, byte-identical to the pin, with its I2 envelope. It is the negative case (I5 §5 item 1). | upstream-supplied |
| `k8s/namespaced/` | The namespace-derived copy, with its I2 envelope. It is the positive I2/I3 input (I5 §5 item 2). | upstream-derived |
| `k8s/derive_namespaced.py` | The one permitted transform. It is deterministic and self-verifying. | AIP operator configuration |
| `mapping.yaml` | The Path B mapping artifact: rest-fights, rest-heroes and rest-villains. rest-narration is deliberately unmapped. | AIP operator configuration |
| `config.quarkus-i5.yaml` | The AIP configuration: one declarations source, two Kubernetes sources and the mapping | AIP operator configuration |
| `docker-compose.yml`, `otel-collector-config.yaml`, `traffic.sh` | The runtime profile carried over from v0.3. Only the environment name, the AIP build context and the mounts changed. | profile |

The upstream Kubernetes files begin with an upstream banner: "ANY LOCAL CHANGES YOU MAKE SHOULD NOT
BE COMMITTED TO SOURCE CONTROL." That banner refers to the upstream repository. Here the unmodified
file is a verbatim frozen input. The derived copy is disclosed as upstream-derived and is never
presented as upstream-supplied.
