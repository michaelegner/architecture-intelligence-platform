# OTel resource attribute keys used to identify the reporting service (spec §11/§33). Centralized
# here so semantic-convention-version differences can be normalized in one place, not scattered
# across the receiver/resolvers.
SERVICE_NAME = "service.name"
SERVICE_NAMESPACE = "service.namespace"
SERVICE_VERSION = "service.version"
SERVICE_INSTANCE_ID = "service.instance.id"
DEPLOYMENT_ENVIRONMENT_NAME = "deployment.environment.name"

# I3 §9.3 bounded Kubernetes resource identity allowlist. k8s.pod.uid is the only one of these
# required for a runtime identity observation to be constructed at all (spec §9.1); the rest are
# optional consistency attributes. No other Kubernetes-shaped Resource attribute (labels,
# annotations, container env/command/args, pod/host IP, Node metadata, volumes, Secrets) is ever
# read - this list is exhaustive by design, not a starting point to extend ad hoc.
K8S_POD_UID = "k8s.pod.uid"
K8S_POD_NAME = "k8s.pod.name"
K8S_NAMESPACE_NAME = "k8s.namespace.name"
K8S_CLUSTER_UID = "k8s.cluster.uid"
K8S_DEPLOYMENT_NAME = "k8s.deployment.name"
K8S_STATEFULSET_NAME = "k8s.statefulset.name"
K8S_DAEMONSET_NAME = "k8s.daemonset.name"
