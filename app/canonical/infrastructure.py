"""I2 Draft 0.2 §7.1/§7.2's frozen infrastructure entity/contribution/claim schemas - the Canonical
Model's *capacity* to carry Kubernetes infrastructure facts (v0.5.0 I2's §3 prerequisite slice, item
6). No adapter populates these yet: that begins at I2 §12 slice 2 (envelope/identity) and slice 3
(the first real Kubernetes adapter). A separate module from `app.canonical.model`, mirroring how
`app.provenance.model` is already its own module - these are a distinct fact category
(infrastructure, not application) from Service/Operation/Queue/Message/Schema/Relation.

Field names and shapes here are this PR's own choice where the spec gives only a prose bullet list,
not a schema - the same discipline `SourceDescriptor`/`SourceInventorySnapshot` used in I1/I2's
prerequisite slice.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class InfrastructureEntityKind(StrEnum):
    """I2 Draft 0.2 §7.1: "I2 adds exactly four internal canonical infrastructure entity kinds.
    They are distinct from all existing application entities." No fifth kind may be added without a
    reviewed specification amendment.
    """

    KUBERNETES_WORKLOAD = "KUBERNETES_WORKLOAD"
    KUBERNETES_POD = "KUBERNETES_POD"
    KUBERNETES_NETWORK_SERVICE = "KUBERNETES_NETWORK_SERVICE"
    KUBERNETES_INGRESS = "KUBERNETES_INGRESS"


class InfrastructureClaimKind(StrEnum):
    """I2 Draft 0.2 §7.2's four canonical infrastructure claim kinds. `WORKLOAD_EXISTS` is unary
    (its `InfrastructureClaim.object_id` is always `None`); the other three are binary.
    """

    WORKLOAD_EXISTS = "WORKLOAD_EXISTS"
    WORKLOAD_OWNS_POD = "WORKLOAD_OWNS_POD"
    NETWORK_SERVICE_SELECTS_WORKLOAD = "NETWORK_SERVICE_SELECTS_WORKLOAD"
    INGRESS_ROUTES_TO_NETWORK_SERVICE = "INGRESS_ROUTES_TO_NETWORK_SERVICE"


class KubernetesEvidenceMode(StrEnum):
    """I2 Draft 0.2 §4.1: "Each configured Kubernetes source has exactly one immutable evidence
    mode." Distinct from `app.provenance.model.EvidenceType`'s generic `DECLARED`/`OBSERVED` split -
    both Kubernetes modes are declared-or-captured *infrastructure* evidence, never `OBSERVED` in
    the OTel runtime-observation sense (§4.1: "no claim of API presence or execution" /
    "presence in that bounded capture, not current liveness").
    """

    DECLARED_MANIFEST = "DECLARED_MANIFEST"
    CAPTURED_RESOURCE = "CAPTURED_RESOURCE"


class InfrastructurePort(BaseModel):
    """I2 Draft 0.2 §7.1: `KUBERNETES_NETWORK_SERVICE`'s "sorted list of ports
    (name-or-null, protocol, port)"."""

    name: str | None = None
    protocol: str
    port: int


class InfrastructureEntity(BaseModel):
    """I2 Draft 0.2 §7.1: "Each entity's common logical fields are exactly: id, entity_kind,
    cluster_uid, api_group, resource_kind, namespace, name." `namespace` is the empty string only
    for a cluster-scoped resource (§6). `service_type`/`ports` are meaningful only when `entity_kind`
    is `KUBERNETES_NETWORK_SERVICE` ("Additional semantic fields" in §7.1's own table) - left unset
    (`None`/empty) for every other kind, mirroring how e.g. `Message.schema_id` is optional and only
    meaningful for certain message shapes elsewhere in the Canonical Model.
    """

    id: str
    entity_kind: InfrastructureEntityKind
    cluster_uid: str
    api_group: str
    resource_kind: str
    namespace: str
    name: str
    service_type: str | None = None
    ports: list[InfrastructurePort] = Field(default_factory=list)


class InfrastructureContribution(BaseModel):
    """I2 Draft 0.2 §7.1: "Every source-owned entity contribution carries: entity_id,
    source_instance_id, evidence_mode, resource_semantic_digest, evidence_refs, mapping_rule_id,
    mapping_rule_version." `resource_semantic_digest` is an opaque, already-computed digest string
    here - computing it from real Kubernetes resource content is the adapter's job (I2 §12 slice 3),
    not this Canonical Model layer's.
    """

    entity_id: str
    source_instance_id: str
    evidence_mode: KubernetesEvidenceMode
    resource_semantic_digest: str
    evidence_refs: list[str] = Field(default_factory=list)
    mapping_rule_id: str
    mapping_rule_version: str


class InfrastructureClaim(BaseModel):
    """I2 Draft 0.2 §7.2: "All claims carry kind, subject_id, optional object_id, evidence_refs, and
    mapping_rule_id/version." `WORKLOAD_EXISTS` MUST NOT invent a sentinel entity or self-edge to
    force it through a binary-relation representation - `object_id=None` represents it directly.
    """

    kind: InfrastructureClaimKind
    subject_id: str
    object_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    mapping_rule_id: str
    mapping_rule_version: str
