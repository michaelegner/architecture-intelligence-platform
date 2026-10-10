"""Kubernetes resource kinds and API-group parsing shared by the `app.sources.kubernetes_*`
modules (I2 Draft 0.2 §6)."""

NAMESPACE_KIND = "Namespace"
POD_KIND = "Pod"
SERVICE_KIND = "Service"
DEPLOYMENT_KIND = "Deployment"
STATEFULSET_KIND = "StatefulSet"
DAEMONSET_KIND = "DaemonSet"
REPLICASET_KIND = "ReplicaSet"
INGRESS_KIND = "Ingress"

WORKLOAD_KINDS = frozenset({DEPLOYMENT_KIND, STATEFULSET_KIND, DAEMONSET_KIND})


def api_group(api_version: str) -> str:
    """I2 Draft 0.2 §6: "The core API group is the empty string." `apiVersion` is always either a
    bare version (core group, e.g. "v1") or "group/version" (e.g. "apps/v1") - never more than one
    slash.
    """
    group, _, _version = api_version.rpartition("/")
    return group
