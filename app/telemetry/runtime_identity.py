from app.canonical import ids
from app.provenance.model import RuntimeIdentityObservation
from app.telemetry.model import RuntimeSpan, day_bucket


def extract_runtime_identity_observations(
    spans: list[RuntimeSpan],
) -> list[RuntimeIdentityObservation]:
    """Builds bounded runtime identity observations from a decoded OTLP batch (I3 spec §9.4,
    §23 slice 2). Deliberately independent of correlate_http_call_observations/
    correlate_queue_observations: reads only RuntimeSpan's own resource-identity fields, never
    couples to service/operation/queue resolution, and never infers an interaction.

    A span produces an observation only when service_name, k8s_pod_uid, and environment are all
    present (spec §9.1: "service.name alone is insufficient", "k8s.pod.name without k8s.pod.uid is
    insufficient") - a span missing any of these silently produces no observation. This is evidence
    collection, not a refused claim, so no UnresolvedObservation is recorded either.
    """
    seeds: list[RuntimeIdentityObservation] = []
    for span in spans:
        if not (span.service_name and span.k8s_pod_uid and span.environment):
            continue

        bucket_start, _bucket_end = day_bucket(span.end_time)
        seeds.append(
            RuntimeIdentityObservation(
                id=ids.runtime_identity_observation_id(
                    environment=span.environment,
                    bucket_start=bucket_start,
                    service_name=span.service_name,
                    service_namespace=span.service_namespace,
                    k8s_pod_uid=span.k8s_pod_uid,
                ),
                service_name=span.service_name,
                service_namespace=span.service_namespace,
                service_version=span.service_version,
                environment=span.environment,
                k8s_pod_uid=span.k8s_pod_uid,
                k8s_pod_name=span.k8s_pod_name,
                k8s_namespace_name=span.k8s_namespace_name,
                k8s_cluster_uid=span.k8s_cluster_uid,
                k8s_deployment_name=span.k8s_deployment_name,
                k8s_statefulset_name=span.k8s_statefulset_name,
                k8s_daemonset_name=span.k8s_daemonset_name,
                first_seen=span.end_time,
                last_seen=span.end_time,
                observation_count=1,
            )
        )
    return seeds
