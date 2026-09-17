"""I2 Draft 0.2 §5 ("Admitted resources and retained fields"), §6 ("Identity, normalization, and
replay"), and §7.1 ("Entity and contribution schema") - v0.5.0 I2 §12 slices 3a/3b: resource
classification, validation, and allowlisted-projection building. Pure logic, no Neo4j and no
`Provenance`/evidence-id construction - mirrors `app.sources.kubernetes_envelope`'s own "sources
layer = pure" discipline. `app.ingestion.kubernetes_adapter` is the caller: it turns this module's
`MappedResource` results into `InfrastructureContribution`/`Provenance`/`WORKLOAD_EXISTS` claims
(all of which need evidence ids and are therefore that layer's job, not this one's).

Every admitted resource kind is classified, validated, and projected here, regardless of whether
its kind is promoted to a canonical entity. §6's normalization/replay rule ("Normalize the
allowlisted resource projection, ordering resources by logical key") and §5's "malformed used
fields[...] or conflicting duplicate resources reject the source" both apply to every admitted
resource - slice 3a's own review found that deferring Namespace/ReplicaSet/Service/Ingress coverage
left the overall `semantic_input_digest` blind to their content and let a conflicting duplicate
Service or Ingress silently pass unchecked, so this pipeline was generalized to all eight admitted
kinds from slice 3a onward. `MappedResource.entity` is `None` only for `Namespace`/`ReplicaSet`
(§7.1: "remain in the snapshot-bound resource/incarnation index... I2 does not promote them to
additional canonical entity kinds", permanently for this increment) - slice 3b promotes
`KUBERNETES_NETWORK_SERVICE`/`KUBERNETES_INGRESS` here too, reusing the same already-validated
projections without touching the classification/validation/projection pipeline itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.canonical.infrastructure import (
    InfrastructureEntity,
    InfrastructureEntityKind,
    InfrastructurePort,
)
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
_INGRESS_RESOURCE_KIND = "Ingress"

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
class MappedResource:
    """Every admitted, validated, logically-unique resource in the bundle - not only the ones this
    slice promotes to a canonical entity. `app.ingestion.kubernetes_adapter` uses `entity` (when not
    `None`) to build the `InfrastructureContribution`/`Provenance`/`WORKLOAD_EXISTS` claim around
    it, and uses `projection` from *every* `MappedResource` (regardless of `entity`) to compute the
    overall `semantic_input_digest` - §6's normalization/replay rule covers all admitted resources,
    not only promoted ones.
    """

    logical_id: str
    resource_kind: str
    entity: InfrastructureEntity | None
    """`None` for a resource kind this slice does not promote (Namespace, ReplicaSet, Service,
    Ingress) - still participates in digest/duplicate-conflict handling."""
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
    captured_uid: str | None
    """§6: "resource incarnation = (logical resource id, captured resource UID)." Set only when
    the source's evidence mode is `CAPTURED_RESOURCE`; `None` for `DECLARED_MANIFEST` (§5:
    "Declarations may omit them and never gain fabricated values"). Kept separate from `projection`
    - §7.1 explicitly excludes capture-only UID from the semantic digest - so
    `app.ingestion.kubernetes_adapter` can carry it into `InfrastructureContribution.
    captured_resource_uid` for §7.1's own independent incarnation-conflict rule."""


@dataclass(frozen=True)
class KubernetesMappingResult:
    result: IngestionResult
    resources: tuple[MappedResource, ...]
    """Every admitted, deduplicated resource in the bundle, ordered by logical resource id (§6) -
    empty whenever `result` is not `ACCEPTED` or `ACCEPTED_WITH_LIMITATIONS`, matching this
    codebase's "a source either fully succeeds or is entirely discarded" discipline for a hard
    rejection."""
    diagnostics: tuple[IngestionDiagnostic, ...]

    @property
    def entities(self) -> tuple[MappedResource, ...]:
        """The subset of `resources` this slice promotes to a canonical entity - a convenience view
        for `app.ingestion.kubernetes_adapter`'s own entity/contribution/claim construction, which
        never needs to see the non-promoted resources individually."""
        return tuple(resource for resource in self.resources if resource.entity is not None)


def _entity_kind_for(resource_kind: str) -> InfrastructureEntityKind | None:
    """§7.1's four admitted-to-entity-kind mappings. `None` for `Namespace`/`ReplicaSet`, which
    §7.1 keeps permanently in the snapshot-bound resource/incarnation index only.
    """
    if resource_kind in _WORKLOAD_RESOURCE_KINDS:
        return InfrastructureEntityKind.KUBERNETES_WORKLOAD
    if resource_kind == _POD_RESOURCE_KIND:
        return InfrastructureEntityKind.KUBERNETES_POD
    if resource_kind == _SERVICE_RESOURCE_KIND:
        return InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE
    if resource_kind == _INGRESS_RESOURCE_KIND:
        return InfrastructureEntityKind.KUBERNETES_INGRESS
    return None


def _owner_references_or_error(raw: object) -> tuple[list[dict], str | None]:
    """I2 Draft 0.2 §5's allowlisted "controller owner references: API version, kind, name, UID,
    and controller flag." §5 also requires "malformed used fields[...] reject the source" - so an
    owner reference with a non-dict entry, a missing/wrongly-typed identifying field, or a
    non-boolean `controller` flag rejects rather than silently coercing (a prior version used
    `bool(...)`, which treats any truthy non-bool - e.g. the string `"false"` - as `True`).
    """
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return [], "metadata.ownerReferences must be a list"
    refs = []
    for ref in raw:
        if not isinstance(ref, dict):
            return [], "metadata.ownerReferences entries must be objects"
        api_version, kind, name, uid = (
            ref.get("apiVersion"),
            ref.get("kind"),
            ref.get("name"),
            ref.get("uid"),
        )
        if not all(isinstance(value, str) and value for value in (api_version, kind, name, uid)):
            message = (
                "metadata.ownerReferences entries require non-empty string apiVersion/kind/name/uid"
            )
            return [], message
        controller = ref.get("controller", False)
        if not isinstance(controller, bool):
            return [], "metadata.ownerReferences[].controller must be a boolean"
        refs.append(
            {
                "apiVersion": api_version,
                "kind": kind,
                "name": name,
                "uid": uid,
                "controller": controller,
            }
        )
    return sorted(
        refs, key=lambda ref: (ref["apiVersion"], ref["kind"], ref["name"], ref["uid"])
    ), None


def _string_map_or_error(raw: object, *, field: str) -> tuple[dict[str, str], str | None]:
    if raw is None:
        return {}, None
    if not isinstance(raw, dict):
        return {}, f"{field} must be a mapping"
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return {}, f"{field} keys/values must be strings"
    return dict(raw), None


def _service_ports_or_error(raw: object) -> tuple[list[dict], str | None]:
    """§5: "Service type and declared ports" - §7.1's `(name-or-null, protocol, port)` shape,
    validated and sorted the same way `InfrastructurePort.sort_key` orders them.
    """
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return [], "spec.ports must be a list"
    ports = []
    for entry in raw:
        if not isinstance(entry, dict):
            return [], "spec.ports entries must be objects"
        name = entry.get("name")
        if name is not None and not isinstance(name, str):
            return [], "spec.ports[].name must be a string"
        protocol = entry.get("protocol", "TCP")
        if not isinstance(protocol, str) or not protocol:
            return [], "spec.ports[].protocol must be a non-empty string"
        port = entry.get("port")
        if not isinstance(port, int) or isinstance(port, bool):
            return [], "spec.ports[].port must be an integer"
        ports.append({"name": name, "protocol": protocol, "port": port})
    ports.sort(key=lambda p: (p["name"] or "", p["protocol"], p["port"]))
    return ports, None


def _ingress_backend_or_error(raw: object) -> tuple[dict | None, str | None]:
    """§5: "Ingress service backend references." A backend always names a target Service and one
    of a port name or number - both absent is malformed, not merely incomplete.
    """
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, "ingress backend must be an object"
    service = raw.get("service")
    if not isinstance(service, dict):
        return None, "ingress backend.service must be an object"
    name = service.get("name")
    if not isinstance(name, str) or not name:
        return None, "ingress backend.service.name must be a non-empty string"
    port = service.get("port")
    if not isinstance(port, dict):
        return None, "ingress backend.service.port must be an object"
    port_name = port.get("name")
    port_number = port.get("number")
    if port_name is not None and not isinstance(port_name, str):
        return None, "ingress backend.service.port.name must be a string"
    if port_number is not None and (
        not isinstance(port_number, int) or isinstance(port_number, bool)
    ):
        return None, "ingress backend.service.port.number must be an integer"
    if port_name is None and port_number is None:
        return None, "ingress backend.service.port must set name or number"
    return {
        "serviceName": name,
        "servicePortName": port_name,
        "servicePortNumber": port_number,
    }, None


def _ingress_rules_or_error(raw: object) -> tuple[list[dict], str | None]:
    """§5: "host/path/pathType" alongside each rule's own backend reference."""
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return [], "spec.rules must be a list"
    rules = []
    for rule in raw:
        if not isinstance(rule, dict):
            return [], "spec.rules entries must be objects"
        host = rule.get("host")
        if host is not None and not isinstance(host, str):
            return [], "spec.rules[].host must be a string"
        http = rule.get("http")
        paths: list[dict] = []
        if http is not None:
            if not isinstance(http, dict):
                return [], "spec.rules[].http must be an object"
            raw_paths = http.get("paths")
            if raw_paths is not None:
                if not isinstance(raw_paths, list):
                    return [], "spec.rules[].http.paths must be a list"
                for path_entry in raw_paths:
                    if not isinstance(path_entry, dict):
                        return [], "spec.rules[].http.paths entries must be objects"
                    path = path_entry.get("path")
                    if path is not None and not isinstance(path, str):
                        return [], "spec.rules[].http.paths[].path must be a string"
                    path_type = path_entry.get("pathType")
                    if path_type is not None and not isinstance(path_type, str):
                        return [], "spec.rules[].http.paths[].pathType must be a string"
                    backend, error = _ingress_backend_or_error(path_entry.get("backend"))
                    if error is not None:
                        return [], error
                    paths.append({"path": path, "pathType": path_type, "backend": backend})
        paths.sort(key=lambda p: (p["path"] or "", p["pathType"] or ""))
        rules.append({"host": host, "paths": paths})
    rules.sort(key=lambda r: (r["host"] or "", canonical_json_bytes(r["paths"])))
    return rules, None


def _needed_pod_label_keys(resources: tuple[KubernetesResourceEntry, ...]) -> frozenset[str]:
    """I2 Draft 0.2 §5: "labels needed by an admitted Service selector" - a data-minimization rule
    over what a Pod's labels retain, not a selector-*match* (slice 4's job). Reads every admitted
    `v1/Service`'s own `spec.selector` keys without promoting any Service to an entity - deferring
    this to slice 3b (when `KUBERNETES_NETWORK_SERVICE` entities are added) would silently change
    every existing Pod's `resource_semantic_digest` the moment that slice ships, a real and
    avoidable revision-churn regression. A malformed selector is caught by `_project_or_error`
    (rejects the whole source), not here - this best-effort pass only needs the well-typed keys.
    """
    keys: set[str] = set()
    for entry in resources:
        document = entry.document
        if _resource_type_key(document) != f"v1/{_SERVICE_RESOURCE_KIND}":
            continue
        # Review round (PR #200): this prepass runs before `_project_or_error` validates `spec`'s
        # own shape, so a malformed `spec` (e.g. a list instead of a mapping) must not raise here -
        # it still rejects the source once `_project_or_error` reaches this resource.
        spec = document.get("spec")
        selector = spec.get("selector") if isinstance(spec, dict) else None
        if isinstance(selector, dict):
            keys.update(k for k in selector if isinstance(k, str))
    return frozenset(keys)


def _validation_error(
    entry: KubernetesResourceEntry, *, code: DiagnosticCode, message: str
) -> IngestionDiagnostic:
    document = entry.document
    # Review round (PR #200): called from the branch that rejects a resource whose `metadata`
    # itself is not a mapping - re-reading it with a bare `.get()` would raise on exactly that
    # input (e.g. `metadata: []`), so this falls back to an empty mapping instead of trusting the
    # shape being reported as invalid.
    metadata = document.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    pointer = (
        f"{entry.source_pointer}:{document.get('apiVersion')}/{document.get('kind')}"
        f"/{metadata.get('namespace', '')}"
        f"/{metadata.get('name', '<missing>')}"
    )
    return IngestionDiagnostic(code=code, message=message, source_pointer=pointer)


def _validate_resource(
    entry: KubernetesResourceEntry,
    *,
    scope_namespaces: frozenset[str],
    requires_capture_identity: bool,
) -> IngestionDiagnostic | None:
    """I2 Draft 0.2 §5/§4.3's per-resource shape/scope validation rules, checked uniformly for
    every admitted resource. Field-shape ("malformed used fields") validation for the fields this
    module actually consumes for projection is `_project_or_error`'s job, run per logical-resource
    group once duplicates are known - kept separate so a within-group projection difference is
    still comparable even when one copy is well-formed and the shape check hasn't run on it yet.
    Returns the single diagnostic that rejects the whole source, or `None` if this resource is
    valid.
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


def _project_or_error(
    document: dict, *, needed_label_keys: frozenset[str]
) -> tuple[dict | None, str | None]:
    """§7.1: "includes every allowlisted value that can affect an entity, claim, identity handoff,
    or limitation... excludes... capture-only UID, resourceVersion." Resource UID/resourceVersion
    are the resource's *own* capture identity (excluded, tracked separately as `MappedResource.
    captured_uid`); an owner *reference*'s UID is relationship-defining, not this object's own
    identity, and is retained (§6: "any changed UID or controller-reference UID MUST trigger
    owner-chain reevaluation").

    §5: "malformed used fields[...] reject the source" - every field this function reads is
    type-checked before use; returns `(None, error_message)` instead of silently coercing or
    dropping malformed data (a prior version's `bool(ref.get("controller", False))` masked this).
    """
    metadata = document.get("metadata", {})
    kind = document["kind"]

    owner_refs, error = _owner_references_or_error(metadata.get("ownerReferences"))
    if error is not None:
        return None, error

    projection: dict = {
        "apiVersion": document["apiVersion"],
        "kind": kind,
        "namespace": metadata.get("namespace") or "",
        "name": metadata["name"],
        "ownerReferences": owner_refs,
    }

    if kind in _WORKLOAD_RESOURCE_KINDS:
        annotations = metadata.get("annotations")
        if annotations is not None and not isinstance(annotations, dict):
            return None, "metadata.annotations must be a mapping"
        service_id = (
            annotations.get(SERVICE_ID_ANNOTATION) if isinstance(annotations, dict) else None
        )
        if service_id is not None and not isinstance(service_id, str):
            return None, f"{SERVICE_ID_ANNOTATION} annotation must be a string"
        projection["serviceIdAnnotation"] = service_id

    elif kind == _POD_RESOURCE_KIND:
        labels, error = _string_map_or_error(metadata.get("labels"), field="metadata.labels")
        if error is not None:
            return None, error
        retained_labels = {k: v for k, v in labels.items() if k in needed_label_keys}
        projection["labels"] = dict(sorted(retained_labels.items()))

    elif kind == _SERVICE_RESOURCE_KIND:
        spec = document.get("spec")
        if spec is not None and not isinstance(spec, dict):
            return None, "spec must be a mapping"
        spec = spec or {}
        selector, error = _string_map_or_error(spec.get("selector"), field="spec.selector")
        if error is not None:
            return None, error
        projection["selector"] = dict(sorted(selector.items()))
        service_type = spec.get("type")
        if service_type is not None and not isinstance(service_type, str):
            return None, "spec.type must be a string"
        projection["serviceType"] = service_type
        ports, error = _service_ports_or_error(spec.get("ports"))
        if error is not None:
            return None, error
        projection["ports"] = ports

    elif kind == _INGRESS_RESOURCE_KIND:
        spec = document.get("spec")
        if spec is not None and not isinstance(spec, dict):
            return None, "spec must be a mapping"
        spec = spec or {}
        default_backend, error = _ingress_backend_or_error(spec.get("defaultBackend"))
        if error is not None:
            return None, error
        rules, error = _ingress_rules_or_error(spec.get("rules"))
        if error is not None:
            return None, error
        projection["defaultBackend"] = default_backend
        projection["rules"] = rules

    return projection, None


def _captured_uid(document: dict, *, requires_capture_identity: bool) -> str | None:
    """§6: "resource incarnation = (logical resource id, captured resource UID)." Only meaningful
    under `CAPTURED_RESOURCE` evidence mode - `_validate_resource` already guarantees a non-empty
    string `metadata.uid` on that path, so this is a plain lookup, not a re-validation.
    """
    if not requires_capture_identity:
        return None
    return document["metadata"]["uid"]


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
                result=IngestionResult.REJECTED_INVALID, resources=(), diagnostics=(error,)
            )

    needed_label_keys = _needed_pod_label_keys(resources)

    # Group EVERY admitted resource (not only entity-promoted kinds) by its §6 logical resource id
    # - §6's normalization/replay rule and §5's duplicate-conflict rule both apply uniformly.
    groups: dict[str, list[KubernetesResourceEntry]] = {}
    for entry in resources:
        document = entry.document
        if not is_admitted(document):
            continue
        resource_kind = document["kind"]
        metadata = document.get("metadata", {})
        logical_id = kubernetes_logical_resource_id(
            cluster_uid=cluster_uid,
            api_group=_api_group(document["apiVersion"]),
            kind=resource_kind,
            namespace=metadata.get("namespace") or "",
            name=metadata["name"],
        )
        groups.setdefault(logical_id, []).append(entry)

    mapped_resources: list[MappedResource] = []
    for logical_id in sorted(groups):
        group = groups[logical_id]
        projections = []
        for entry in group:
            projection, error = _project_or_error(
                entry.document, needed_label_keys=needed_label_keys
            )
            if error is not None:
                return KubernetesMappingResult(
                    result=IngestionResult.REJECTED_INVALID,
                    resources=(),
                    diagnostics=(
                        _validation_error(
                            entry, code=DiagnosticCode.K8S_RESOURCE_INVALID, message=error
                        ),
                    ),
                )
            projections.append(projection)

        first_projection = projections[0]
        if any(projection != first_projection for projection in projections[1:]):
            return KubernetesMappingResult(
                result=IngestionResult.REJECTED_CONFLICT,
                resources=(),
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.K8S_RESOURCE_CONFLICT,
                        message="conflicting duplicate resources under one logical resource id",
                        source_pointer=logical_id,
                    ),
                ),
            )

        captured_uids = {
            uid
            for entry in group
            if (
                uid := _captured_uid(
                    entry.document, requires_capture_identity=requires_capture_identity
                )
            )
            is not None
        }
        if len(captured_uids) > 1:
            # §7.1: "Two current captured contributions that bind the same logical resource to
            # different UIDs are likewise incompatible incarnations" - checked within-bundle here;
            # app.sources.claim_conflicts.detect_infrastructure_entity_content_conflicts checks the
            # cross-source case via InfrastructureContribution.captured_resource_uid.
            return KubernetesMappingResult(
                result=IngestionResult.REJECTED_CONFLICT,
                resources=(),
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.K8S_RESOURCE_CONFLICT,
                        message="conflicting captured UIDs under one logical resource id",
                        source_pointer=logical_id,
                    ),
                ),
            )

        document = group[0].document
        resource_kind = document["kind"]
        metadata = document.get("metadata", {})
        entity_kind = _entity_kind_for(resource_kind)
        # §7.1: "Additional semantic fields" apply only to KUBERNETES_NETWORK_SERVICE. Sourced
        # directly from `first_projection` (already validated/sorted by `_project_or_error`) rather
        # than re-derived from the raw document, so the entity's own persisted fields and the
        # hashed digest input can never disagree.
        service_fields = (
            {
                "service_type": first_projection["serviceType"],
                "ports": [InfrastructurePort(**port) for port in first_projection["ports"]],
            }
            if entity_kind is InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE
            else {}
        )
        entity = (
            InfrastructureEntity(
                id=logical_id,
                entity_kind=entity_kind,
                cluster_uid=cluster_uid,
                api_group=_api_group(document["apiVersion"]),
                resource_kind=resource_kind,
                namespace=metadata.get("namespace") or "",
                name=metadata["name"],
                **service_fields,
            )
            if entity_kind is not None
            else None
        )
        digest = sha256_hex(canonical_json_bytes(first_projection))
        source_pointers = tuple(sorted({entry.source_pointer for entry in group}))
        captured_uid = next(iter(captured_uids), None)
        mapped_resources.append(
            MappedResource(
                logical_id=logical_id,
                resource_kind=resource_kind,
                entity=entity,
                resource_semantic_digest=digest,
                source_pointers=source_pointers,
                projection=first_projection,
                captured_uid=captured_uid,
            )
        )

    result = (
        IngestionResult.ACCEPTED_WITH_LIMITATIONS if has_limitation else IngestionResult.ACCEPTED
    )
    return KubernetesMappingResult(
        result=result, resources=tuple(mapped_resources), diagnostics=tuple(diagnostics)
    )
