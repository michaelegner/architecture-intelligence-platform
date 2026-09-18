import hashlib
from datetime import datetime


def service_id(slug: str, namespace: str | None = None) -> str:
    if namespace:
        return f"service:{namespace}:{slug}"
    return f"service:{slug}"


def operation_id(service_slug: str, method: str, path: str) -> str:
    return f"operation:{service_slug}:{method.upper()}:{path}"


def queue_id(name: str, namespace: str | None = None) -> str:
    if namespace:
        return f"queue:{namespace}:{name}"
    return f"queue:{name}"


def message_id(name: str, version: str | None = None) -> str:
    if version:
        return f"message:{name}:{version}"
    return f"message:{name}"


def schema_id(name: str, version: str | None = None) -> str:
    if version:
        return f"schema:{name}:{version}"
    return f"schema:{name}"


def evidence_id(source_type: str, service_slug: str, revision: str | None = None) -> str:
    if revision:
        return f"evidence:{source_type.lower()}:{service_slug}:{revision}"
    return f"evidence:{source_type.lower()}:{service_slug}"


def observed_evidence_id(
    environment: str, bucket_start: datetime, subject_id: str, relation_type: str, object_id: str
) -> str:
    """Deterministic id for an OTel-observed evidence bucket (spec §17). Has no trace/span-specific
    component - every seed for the same (fact, day, environment) gets the identical id, so a later
    Aggregator can MERGE into it rather than searching for a match."""
    fact_hash = hashlib.sha256(f"{subject_id}|{relation_type}|{object_id}".encode()).hexdigest()[
        :12
    ]
    return f"evidence:otel:{environment}:{bucket_start:%Y-%m-%d}:{fact_hash}"


def runtime_identity_observation_id(
    *,
    environment: str,
    bucket_start: datetime,
    service_name: str,
    service_namespace: str | None,
    k8s_pod_uid: str,
) -> str:
    """Deterministic id for an I3 §9.4 bounded runtime identity observation - an "equivalently
    deterministic bounded identity" to observed_evidence_id() above, since this record has no
    subject/relation_type/object triple to hash. Keyed on (environment, day, service_name,
    service_namespace, k8s_pod_uid), not k8s_pod_uid alone: spec §10.5 allows one Pod UID to
    legitimately produce multiple distinct service.name observations (e.g. separately-instrumented
    sidecar containers) as an AMBIGUOUS case, not an error, so service identity must be part of the
    key or that case would silently collapse into one merged record. service_version and the
    optional §9.3 consistency attributes are excluded, mirroring observed_evidence_id()'s own
    exclusion of non-identity fields; trace/span ids are excluded per §9.4's explicit instruction.

    Prefixed "runtime-identity:otel:...", not "evidence:...": this record is never persisted under
    the :Evidence label (see app.telemetry.aggregator), so an evidence:-prefixed id would misleadingly
    imply :Evidence-resolvability it doesn't have.
    """
    identity_hash = hashlib.sha256(
        f"{service_name}|{service_namespace or ''}|{k8s_pod_uid}".encode()
    ).hexdigest()[:12]
    return f"runtime-identity:otel:{environment}:{bucket_start:%Y-%m-%d}:{identity_hash}"
