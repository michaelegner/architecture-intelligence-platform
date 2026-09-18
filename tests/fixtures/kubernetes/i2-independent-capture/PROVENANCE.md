# Independent Capture Provenance

I2 Draft 0.2 §11: "At least one independently captured, frozen resource bundle must qualify the
owner-chain handoff; authored fixtures alone do not justify a claim of captured-resource
interoperability. Record the upstream system/revision, capture procedure, and whether the capture is
temporally non-atomic."

This bundle (`envelope.yaml` + `resources.yaml`) is a real, independent `kubectl get -o yaml` capture
from a real (throwaway) Kubernetes API server — not an authored fixture. No cluster access is needed
to run the qualification test against it (`tests/integration/test_kubernetes_independent_capture.py`)
— only these frozen files are read at test time.

## Upstream system/revision

- Kubernetes distribution: [`kind`](https://kind.sigs.k8s.io/) `v0.33.0` (`go1.26.7 linux/amd64`)
- Node image: `kindest/node:v1.31.2`
  (`kindest/node@sha256:18fbefc20a7113353c7b75b5c869d7145a6abd6269154825872dc59c1329912e`)
- API server version: `v1.31.2` (`kubectl get nodes` `VERSION` column)
- `kubectl` client: `v1.36.1`
- `docker` server: `29.7.2`
- Deployed application: `examples/runtime-demo/` (this repo's own real, pre-existing app — already
  used for I1/H4's OTel runtime qualification, not a new toy app built for this capture), built from
  its own checked-in `Dockerfile`, tagged `aip-runtime-demo:i2-capture`

This is a specific, versioned Kubernetes distribution running this repo's own real application, not
a pre-existing named production cluster — stated explicitly so this capture is not overclaimed as
validating interoperability with any particular commercial/managed Kubernetes distribution beyond
what a stock `kind`/upstream Kubernetes API server represents.

## Capture procedure (exact commands run)

```bash
# 1. Install kind, pinned to the latest stable tag at capture time
curl -Lo /tmp/kind https://kind.sigs.k8s.io/dl/v0.33.0/kind-linux-amd64
chmod +x /tmp/kind && mv /tmp/kind ~/.local/bin/kind

# 2. Create a throwaway single-node cluster, explicit pinned node image
kind create cluster --name aip-i2-capture --image kindest/node:v1.31.2
kubectl wait --for=condition=Ready node --all --timeout=120s

# 3. Build and load the existing real app image (no new Dockerfile)
docker build -t aip-runtime-demo:i2-capture examples/runtime-demo/
kind load docker-image aip-runtime-demo:i2-capture --name aip-i2-capture

# 4. Create namespace and apply the checked-in manifest set (apply-manifests.yaml, this directory)
kubectl create namespace aip-runtime-demo
kubectl apply -f tests/fixtures/kubernetes/i2-independent-capture/apply-manifests.yaml
kubectl -n aip-runtime-demo rollout status deployment/runtime-demo --timeout=120s

# 5. Capture (two separate kubectl get calls - Namespace is cluster-scoped, so it isn't returned by
#    a namespaced `get ... -n aip-runtime-demo` call)
kubectl get namespace aip-runtime-demo -o yaml > /tmp/ns.yaml            # captured 2026-09-18T07:38:45Z
kubectl get deployment,replicaset,pod,service,ingress \
  -n aip-runtime-demo -o yaml > /tmp/rest.yaml                          # captured 2026-09-18T07:38:45Z
kubectl get namespace kube-system -o jsonpath='{.metadata.uid}'         # -> clusterUid

cat /tmp/ns.yaml /tmp/rest.yaml > tests/fixtures/kubernetes/i2-independent-capture/resources.yaml

# 6. Tear down - no live cluster access is needed to run the resulting qualification test
kind delete cluster --name aip-i2-capture
```

## Temporal atomicity

**Not atomic, disclosed as such (§11 explicitly asks this be recorded, not that it be atomic).** The
Namespace and the five namespaced resource kinds were captured via two sequential `kubectl get`
calls, not one cluster-wide atomic snapshot mechanism (Kubernetes' API server offers no such
mechanism for an arbitrary multi-kind `get`). Both calls completed within the same second
(`2026-09-18T07:38:45Z`) against a freshly-rolled-out, otherwise-idle single-node cluster with no
concurrent external mutation source — a controlled *absence* of concurrency in this throwaway
environment, not a cryptographic or transactional atomicity guarantee. `resourceVersion` values
across the captured objects (`480`/`510`/`508`/`506`/`489`/`498`) are close but not identical,
consistent with ordinary Kubernetes control-loop activity (Deployment/ReplicaSet/Pod controllers
writing status) between the two `kubectl get` calls, not a sign of external interference.

## Captured resources and real identity evidence

| Kind | Name | UID | resourceVersion |
|---|---|---|---|
| Namespace | `aip-runtime-demo` | `d0a58885-572b-449f-93ad-4c96b0518752` | `480` |
| Deployment | `runtime-demo` | `947e8f54-9bc1-445d-8306-cf7266871ba4` | `510` |
| ReplicaSet | `runtime-demo-6dc89f5656` | `4b2e9d49-0c0b-4960-9856-b7ca3c4a63fb` | `508` |
| Pod | `runtime-demo-6dc89f5656-8xxrv` | `658bd464-c78f-4ca2-b7e4-2b04e158f4ee` | `506` |
| Service | `runtime-demo` | `45174155-c2f7-409c-8fdd-961466e1f537` | `489` |
| Ingress | `runtime-demo` | `b0af9c0e-fb8e-4d88-826a-5a2b91e5001c` | `498` |

Cluster identity: `clusterUid` is the real captured `kube-system` Namespace UID
(`599e90a5-7ab8-426f-807f-92a65dcc8822`), matching every other Kubernetes fixture in this repo's own
established `clusterIdentityEvidenceRef: kube-system-namespace-uid` convention.

These are genuine, real-API-server-assigned UUIDs (visibly distinct in shape from every hand-typed
identifier like `deploy-uid-1` used in this repo's author-fabricated fixtures/tests) and a genuine
controller-owner chain: the Pod's `ownerReferences` targets the ReplicaSet's own real UID, and the
ReplicaSet's `ownerReferences` targets the Deployment's own real UID — resolved correctly end to end
by the unmodified `app.sources.kubernetes_owner_chain` module against this real capture.

The real capture also includes several fields no author-fabricated I2 fixture in this repo has ever
exercised, all correctly outside the §5 allowlist and confirmed absent from persisted graph state by
`tests/integration/test_kubernetes_independent_capture.py`: the `pod-template-hash` label Kubernetes'
own Deployment controller injects onto the ReplicaSet/Pod, the `kubectl.kubernetes.io/
last-applied-configuration` and `deployment.kubernetes.io/revision`/`deployment.kubernetes.io/
desired-replicas`/`deployment.kubernetes.io/max-replicas` annotations `kubectl apply` and the
Deployment controller inject, and full `status` blocks (conditions, `containerStatuses`, `podIP`,
`hostIP`, etc.).

## Authority attribution

`completeness.authorityRef` (`aip-i2-independent-capture-self-declared-authority`) is a
self-declared authority for this one-time capture, disclosed as such here rather than implied to be
an independent third party. I2 Draft 0.2 §4.2: "Attribution is an explicit configured trust
boundary, not cryptographic verification or a claim that AIP independently observed the cluster" -
this capture's own authority record makes no stronger claim than that boundary already allows.
