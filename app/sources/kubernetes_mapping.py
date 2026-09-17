"""I2 Draft 0.2 §5 ("Admitted resources and retained fields"), §6 ("Identity, normalization, and
replay"), and §7.1 ("Entity and contribution schema") - v0.5.0 I2 §12 slice 3a: resource
classification, validation, and allowlisted-projection building. Pure logic, no Neo4j and no
`Provenance`/evidence-id construction - mirrors `app.sources.kubernetes_envelope`'s own "sources
layer = pure" discipline. `app.ingestion.kubernetes_adapter` is the caller: it turns this module's
`MappedEntity` results into `InfrastructureContribution`/`Provenance`/`WORKLOAD_EXISTS` claims (all
of which need evidence ids and are therefore that layer's job, not this one's).

Shared by this slice (`KUBERNETES_WORKLOAD`/`KUBERNETES_POD`) and slice 3b
(`KUBERNETES_NETWORK_SERVICE`/`KUBERNETES_INGRESS`, not yet implemented) - the classification/
validation/needed-label-key pipeline below already sees every admitted resource kind, since §5's
validation rules apply uniformly regardless of which kinds a given slice promotes to entities.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.canonical.infrastructure import InfrastructureEntity, InfrastructureEntityKind
from app.sources.encoding import sha256_hex
from app.sources.identity import kubernetes_logical_resource_id
from app.sources.jcs import canonical_json_bytes
from app.sources.kubernetes_envelope import EXPECTED_RESOURCE_TYPES
from app.sources.model import (
    DiagnosticCode,
    IngestionDiagnostic,
    IngestionResult,
    KubernetesResourceEntry,
)

# I2 Draft 0.2 §5's table, restricted to the two kinds this slice promotes to entities.
_WORKLOAD_RESOURCE_KINDS = frozenset({"Deployment", "StatefulSet", "DaemonSet"})
_POD_RESOURCE_KIND = "Pod"
_SERVICE_RESOURCE_KIND = "Service"
_NAMESPACE_RESOURCE_KIND = "Namespace"

# I2 Draft 0.2 §5: "architecture-intelligence.io/service-id on supported Workloads, retained for I3
# only" - retained unqualified; I2 never evaluates it into an AIP Service identity (§9).
SERVICE_ID_ANNOTATION = "architecture-intelligence.io/service-id"


def _api_group(api_version: str) -> str:
    """I2 Draft 0.2 §6: "The core API group is the empty string." `apiVersion` is always either a
    bare version (core group, e.g. "v1") or "group/version" (e.g. "apps/v1") - never more than one
    slash.
    """
    group, _, _version = api_version.rpartition("/")
    return group


def _resource_type_key(document: dict) -> str:
    return f"{document.get('apiVersion')}/{document.get('kind')}"


def is_admitted(document: dict) -> bool:
    return _resource_type_key(document) in EXPECTED_RESOURCE_TYPES


def _is_namespaced(resource_kind: str) -> bool:
    return resource_kind != _NAMESPACE_RESOURCE_KIND


@dataclass(frozen=True)
class MappedEntity:
    """One admitted, validated, logically-unique resource this slice promotes to a canonical
    entity - everything `app.ingestion.kubernetes_adapter` needs to build the
    `InfrastructureContribution`/`Provenance`/`WORKLOAD_EXISTS` claim around it, without
    re-deriving any of this module's own classification/validation/projection logic.
    """

    entity: InfrastructureEntity
    resource_semantic_digest: str
    """§7.1: the deterministic digest of `projection` alone - used for cross-source/within-source
    equal-vs-conflicting-contribution comparison. Deliberately not folded with mapping_context_
    digest (that combination is `semantic_input_digest`'s own job, computed once for the whole
    adapter output, not per entity)."""
    source_pointers: tuple[str, ...]
    """Sorted, de-duplicated file pointers this logical resource was declared in - one pointer per
    contributing file (more than one only when §5's "identical duplicates merge their source
    pointers deterministically" applied)."""
    projection: dict
    """This resource's own normalized allowlisted projection - included verbatim in the ordered
    list `app.ingestion.kubernetes_adapter` canonicalizes into the adapter's overall
    `semantic_input_digest` (§6: "normalize the allowlisted resource projection, ordering resources
    by logical key")."""


@dataclass(frozen=True)
class KubernetesMappingResult:
    result: IngestionResult
    entities: tuple[MappedEntity, ...]
    """Ordered by logical resource id (§6) - empty whenever `result` is not `ACCEPTED` or
    `ACCEPTED_WITH_LIMITATIONS`, matching this codebase's "a source either fully succeeds or is
    entirely discarded" discipline for a hard rejection."""
    diagnostics: tuple[IngestionDiagnostic, ...]


def _owner_references(document: dict) -> list[dict]:
    """I2 Draft 0.2 §5's allowlisted "controller owner references: API version, kind, name, UID,
    and controller flag" - retained regardless of the `controller` flag's value here (owner-chain
    *interpretation*, which only cares about `controller: true` hops, is slice 4's job; this is
    only the allowlisted-projection extraction §7.1 requires for the digest). Sorted deterministically
    so map/list ordering in the source document never affects the projection.
    """
    raw = document.get("metadata", {}).get("ownerReferences")
    if not isinstance(raw, list):
        return []
    refs = [
        {
            "apiVersion": ref.get("apiVersion"),
            "kind": ref.get("kind"),
            "name": ref.get("name"),
            "uid": ref.get("uid"),
            "controller": bool(ref.get("controller", False)),
        }
        for ref in raw
        if isinstance(ref, dict)
    ]
    return sorted(
        refs,
        key=lambda ref: (
            ref["apiVersion"] or "",
            ref["kind"] or "",
            ref["name"] or "",
            ref["uid"] or "",
        ),
    )


def _needed_pod_label_keys(resources: tuple[KubernetesResourceEntry, ...]) -> frozenset[str]:
    """I2 Draft 0.2 §5: "labels needed by an admitted Service selector" - a data-minimization rule
    over what a Pod's labels retain, not a selector-*match* (slice 4's job). Reads every admitted
    `v1/Service`'s own `spec.selector` keys without promoting any Service to an entity - deferring
    this to slice 3b (when `KUBERNETES_NETWORK_SERVICE` entities are added) would silently change
    every existing Pod's `resource_semantic_digest` the moment that slice ships, a real and
    avoidable revision-churn regression.
    """
    keys: set[str] = set()
    for entry in resources:
        document = entry.document
        if _resource_type_key(document) != f"v1/{_SERVICE_RESOURCE_KIND}":
            continue
        selector = document.get("spec", {}).get("selector")
        if isinstance(selector, dict):
            keys.update(k for k in selector if isinstance(k, str))
    return frozenset(keys)


def _validation_error(
    entry: KubernetesResourceEntry, *, code: DiagnosticCode, message: str
) -> IngestionDiagnostic:
    document = entry.document
    pointer = (
        f"{entry.source_pointer}:{document.get('apiVersion')}/{document.get('kind')}"
        f"/{document.get('metadata', {}).get('namespace', '')}"
        f"/{document.get('metadata', {}).get('name', '<missing>')}"
    )
    return IngestionDiagnostic(code=code, message=message, source_pointer=pointer)


def _validate_resource(
    entry: KubernetesResourceEntry,
    *,
    scope_namespaces: frozenset[str],
    requires_capture_identity: bool,
) -> IngestionDiagnostic | None:
    """I2 Draft 0.2 §5/§4.3's per-resource validation rules, checked uniformly for every admitted
    resource regardless of whether this slice promotes its kind to an entity. Returns the single
    diagnostic that rejects the whole source, or `None` if this resource is valid.
    """
    document = entry.document
    kind = document.get("kind")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        return _validation_error(
            entry, code=DiagnosticCode.K8S_RESOURCE_INVALID, message="resource has no metadata"
        )

    name = metadata.get("name")
    if not isinstance(name, str) or not name:
        return _validation_error(
            entry,
            code=DiagnosticCode.K8S_RESOURCE_INVALID,
            message="resource is missing metadata.name",
        )

    namespace = metadata.get("namespace")
    if _is_namespaced(kind):
        if not isinstance(namespace, str) or not namespace:
            return _validation_error(
                entry,
                code=DiagnosticCode.K8S_RESOURCE_INVALID,
                message="namespaced resource is missing metadata.namespace",
            )
        # §4.3: "Out-of-scope resources reject the bundle rather than silently changing scope" -
        # K8S_SNAPSHOT_INVALID is reused here (not a new code): its own definition already names
        # "scope mismatch".
        if namespace not in scope_namespaces:
            return _validation_error(
                entry,
                code=DiagnosticCode.K8S_SNAPSHOT_INVALID,
                message="resource namespace is not in the declared scope",
            )
    else:
        # §4.3: "Namespace objects themselves are cluster-scoped and restricted to those selected
        # names" - the object's own name (not a namespace field) must be a declared namespace.
        if kind == _NAMESPACE_RESOURCE_KIND and name not in scope_namespaces:
            return _validation_error(
                entry,
                code=DiagnosticCode.K8S_SNAPSHOT_INVALID,
                message="Namespace object is not in the declared scope",
            )

    if requires_capture_identity:
        uid = metadata.get("uid")
        resource_version = metadata.get("resourceVersion")
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(resource_version, str)
            or not resource_version
        ):
            return _validation_error(
                entry,
                code=DiagnosticCode.K8S_RESOURCE_INVALID,
                message="captured resource requires metadata.uid and metadata.resourceVersion",
            )

    return None


def _build_projection(document: dict, *, needed_label_keys: frozenset[str]) -> dict:
    """§7.1: "includes every allowlisted value that can affect an entity, claim, identity handoff,
    or limitation... excludes... capture-only UID, resourceVersion." Resource UID/resourceVersion
    are the resource's *own* capture identity (excluded); an owner *reference*'s UID is
    relationship-defining, not this object's own identity, and is retained (§6: "any changed UID or
    controller-reference UID MUST trigger owner-chain reevaluation").
    """
    metadata = document.get("metadata", {})
    kind = document["kind"]
    projection: dict = {
        "apiVersion": document["apiVersion"],
        "kind": kind,
        "namespace": metadata.get("namespace") or "",
        "name": metadata["name"],
        "ownerReferences": _owner_references(document),
    }
    if kind in _WORKLOAD_RESOURCE_KINDS:
        annotations = metadata.get("annotations")
        service_id = (
            annotations.get(SERVICE_ID_ANNOTATION) if isinstance(annotations, dict) else None
        )
        projection["serviceIdAnnotation"] = service_id
    elif kind == _POD_RESOURCE_KIND:
        labels = metadata.get("labels")
        retained_labels = (
            {k: v for k, v in labels.items() if k in needed_label_keys}
            if isinstance(labels, dict)
            else {}
        )
        projection["labels"] = dict(sorted(retained_labels.items()))
    return projection


def _entity_kind_for(resource_kind: str) -> InfrastructureEntityKind | None:
    if resource_kind in _WORKLOAD_RESOURCE_KINDS:
        return InfrastructureEntityKind.KUBERNETES_WORKLOAD
    if resource_kind == _POD_RESOURCE_KIND:
        return InfrastructureEntityKind.KUBERNETES_POD
    return None


def map_kubernetes_resources(
    resources: tuple[KubernetesResourceEntry, ...],
    *,
    cluster_uid: str,
    requires_capture_identity: bool,
    scope_namespaces: tuple[str, ...],
) -> KubernetesMappingResult:
    """The one entry point `app.ingestion.kubernetes_adapter` needs. `requires_capture_identity`
    is `evidence_mode == CAPTURED_RESOURCE` - passed as a plain bool rather than the enum itself so
    this module stays independent of `app.canonical.infrastructure.KubernetesEvidenceMode`'s own
    import surface, mirroring `kubernetes_envelope.py`'s own "plain string, not the enum" choice for
    the same field.
    """
    scope = frozenset(scope_namespaces)
    diagnostics: list[IngestionDiagnostic] = []
    has_limitation = False

    for entry in resources:
        if not is_admitted(entry.document):
            document = entry.document
            pointer = f"{entry.source_pointer}:{document.get('apiVersion')}/{document.get('kind')}"
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.K8S_RESOURCE_UNSUPPORTED,
                    message="resource kind is not admitted by this increment",
                    source_pointer=pointer,
                )
            )
            has_limitation = True
            continue

        error = _validate_resource(
            entry, scope_namespaces=scope, requires_capture_identity=requires_capture_identity
        )
        if error is not None:
            # Both K8S_RESOURCE_INVALID (this module's own rejection reasons) and the reused
            # K8S_SNAPSHOT_INVALID (out-of-scope namespace) share the same REJECTED_INVALID outcome.
            return KubernetesMappingResult(
                result=IngestionResult.REJECTED_INVALID, entities=(), diagnostics=(error,)
            )

    needed_label_keys = _needed_pod_label_keys(resources)

    # Group admitted, mapped-kind resources by their §6 logical resource id.
    groups: dict[str, list[KubernetesResourceEntry]] = {}
    order: list[str] = []
    for entry in resources:
        document = entry.document
        if not is_admitted(document):
            continue
        resource_kind = document["kind"]
        if _entity_kind_for(resource_kind) is None:
            continue
        metadata = document.get("metadata", {})
        logical_id = kubernetes_logical_resource_id(
            cluster_uid=cluster_uid,
            api_group=_api_group(document["apiVersion"]),
            kind=resource_kind,
            namespace=metadata.get("namespace") or "",
            name=metadata["name"],
        )
        if logical_id not in groups:
            groups[logical_id] = []
            order.append(logical_id)
        groups[logical_id].append(entry)

    mapped_entities: list[MappedEntity] = []
    for logical_id in sorted(order):
        group = groups[logical_id]
        projections = [
            _build_projection(entry.document, needed_label_keys=needed_label_keys)
            for entry in group
        ]
        first_projection = projections[0]
        if any(projection != first_projection for projection in projections[1:]):
            return KubernetesMappingResult(
                result=IngestionResult.REJECTED_CONFLICT,
                entities=(),
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.K8S_RESOURCE_CONFLICT,
                        message="conflicting duplicate resources under one logical resource id",
                        source_pointer=logical_id,
                    ),
                ),
            )

        document = group[0].document
        metadata = document.get("metadata", {})
        entity = InfrastructureEntity(
            id=logical_id,
            entity_kind=_entity_kind_for(document["kind"]),
            cluster_uid=cluster_uid,
            api_group=_api_group(document["apiVersion"]),
            resource_kind=document["kind"],
            namespace=metadata.get("namespace") or "",
            name=metadata["name"],
        )
        digest = sha256_hex(canonical_json_bytes(first_projection))
        source_pointers = tuple(sorted({entry.source_pointer for entry in group}))
        mapped_entities.append(
            MappedEntity(
                entity=entity,
                resource_semantic_digest=digest,
                source_pointers=source_pointers,
                projection=first_projection,
            )
        )

    result = (
        IngestionResult.ACCEPTED_WITH_LIMITATIONS if has_limitation else IngestionResult.ACCEPTED
    )
    return KubernetesMappingResult(
        result=result, entities=tuple(mapped_entities), diagnostics=tuple(diagnostics)
    )
