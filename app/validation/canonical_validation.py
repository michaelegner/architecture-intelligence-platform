from collections import defaultdict

from app.canonical.infrastructure import KUBERNETES_SOURCE_TYPE, UNARY_CLAIM_KINDS
from app.canonical.model import ArchitectureModel

SCHEMA_RELATION_TYPES = {"REQUEST_SCHEMA", "RESPONSE_SCHEMA", "CONFORMS_TO"}


class CanonicalValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _check_unique(entity_ids: list[str], label: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for entity_id in entity_ids:
        if entity_id in seen:
            errors.append(f"{label} id is not unique: {entity_id}")
        seen.add(entity_id)


def validate_canonical_model(model: ArchitectureModel) -> None:
    """Enforces V1-V8 (spec §10) against a fully merged ArchitectureModel."""
    errors: list[str] = []

    service_ids = {s.id for s in model.services}
    queue_ids = {q.id for q in model.queues}
    message_ids = {m.id for m in model.messages}
    schema_ids = {s.id for s in model.schemas}
    operation_ids = {o.id for o in model.operations}

    # V1 / V3 / V4: unique stable ids
    _check_unique([s.id for s in model.services], "Service", errors)
    _check_unique([q.id for q in model.queues], "Queue", errors)
    _check_unique([m.id for m in model.messages], "Message", errors)

    # V2: every operation has exactly one provider, matching its own service_id
    provides_sources_by_target: dict[str, list[str]] = defaultdict(list)
    for relation in model.relations:
        if relation.type == "PROVIDES":
            provides_sources_by_target[relation.target_id].append(relation.source_id)
    for operation in model.operations:
        providers = provides_sources_by_target.get(operation.id, [])
        if len(providers) != 1:
            errors.append(
                f"Operation {operation.id} must have exactly one PROVIDES relation, found {len(providers)}"
            )
        elif providers[0] != operation.service_id:
            errors.append(
                f"Operation {operation.id} is provided by {providers[0]} but declares "
                f"service_id {operation.service_id}"
            )

    # V5: every CALLS relation references an existing operation
    for relation in model.relations:
        if relation.type == "CALLS" and relation.target_id not in operation_ids:
            errors.append(
                f"CALLS {relation.source_id} -> {relation.target_id} references unknown operation"
            )

    # V6: schema references point to an existing schema
    for relation in model.relations:
        if relation.type in SCHEMA_RELATION_TYPES and relation.target_id not in schema_ids:
            errors.append(
                f"{relation.type} {relation.source_id} -> {relation.target_id} references unknown schema"
            )
    for operation in model.operations:
        for schema_id in (*operation.request_schema_ids, *operation.response_schema_ids):
            if schema_id not in schema_ids:
                errors.append(f"Operation {operation.id} references unknown schema {schema_id}")
    for message in model.messages:
        if message.schema_id and message.schema_id not in schema_ids:
            errors.append(f"Message {message.id} references unknown schema {message.schema_id}")

    # V7: a DLQ must not point to itself
    for relation in model.relations:
        if relation.type == "DEAD_LETTERS_TO" and relation.source_id == relation.target_id:
            errors.append(f"Queue {relation.source_id} cannot be its own DLQ")

    # V8: relations only reference existing source/target entities
    known_ids = service_ids | operation_ids | queue_ids | message_ids | schema_ids
    for relation in model.relations:
        if relation.source_id not in known_ids:
            errors.append(f"Relation {relation.type} has unknown source {relation.source_id}")
        if relation.target_id not in known_ids:
            errors.append(f"Relation {relation.type} has unknown target {relation.target_id}")

    # Evidence: every relation's evidence_ids must reference a Provenance record in this model
    evidence_ids = {p.id for p in model.provenance}
    for relation in model.relations:
        for evidence_id in relation.evidence_ids:
            if evidence_id not in evidence_ids:
                errors.append(
                    f"Relation {relation.type} {relation.source_id} -> {relation.target_id} "
                    f"references unknown evidence {evidence_id}"
                )

    provenance_by_id = {p.id: p for p in model.provenance}
    _validate_infrastructure(model, provenance_by_id=provenance_by_id, errors=errors)

    if errors:
        raise CanonicalValidationError(errors)


def _check_infrastructure_evidence_ref(
    evidence_ref: str, *, provenance_by_id: dict, owner_description: str, errors: list[str]
) -> None:
    """§7.2: "resolve within the selected snapshot." §9 (as amended): a Kubernetes source's
    evidence is internal-only, exactly like the facts it supports - if it were ever stamped with a
    public `source_type`, the exposure filters in `app.architecture_intelligence.repository`/
    `app.api.evidence` (which key on `source_type`, not on what references the evidence) would not
    know to hide it. Checked here so a mis-stamped adapter fails loudly in validation rather than
    silently leaking through a query filter no code path re-derives this from.
    """
    provenance = provenance_by_id.get(evidence_ref)
    if provenance is None:
        errors.append(f"{owner_description} references unknown evidence {evidence_ref}")
    elif provenance.source_type != KUBERNETES_SOURCE_TYPE:
        errors.append(
            f"{owner_description} references evidence {evidence_ref} stamped source_type "
            f"{provenance.source_type!r}, expected {KUBERNETES_SOURCE_TYPE!r} (§9: infrastructure "
            "evidence must be internal-only)"
        )


def _validate_infrastructure(
    model: ArchitectureModel, *, provenance_by_id: dict, errors: list[str]
) -> None:
    """I2 Draft 0.2 §3 item 6: infrastructure facts pass through the same *validation* path as every
    other canonical fact. The per-object §7 invariants (arity, sortedness, kind-specific fields) are
    already enforced by `app.canonical.infrastructure`'s own Pydantic validators; what only a whole
    merged model can check is whether the ids those objects reference actually resolve - §7.2's
    "resolve within the selected snapshot" and "both referenced entity IDs must resolve in the
    canonical model" - and, per §9, that the evidence they resolve to is genuinely internal-only.
    """
    entity_ids = {entity.id for entity in model.infrastructure_entities}
    _check_unique(
        [entity.id for entity in model.infrastructure_entities], "Infrastructure entity", errors
    )

    for contribution in model.infrastructure_contributions:
        if contribution.entity_id not in entity_ids:
            errors.append(
                f"Infrastructure contribution from {contribution.source_instance_id} references "
                f"unknown entity {contribution.entity_id}"
            )
        for evidence_ref in contribution.evidence_refs:
            _check_infrastructure_evidence_ref(
                evidence_ref,
                provenance_by_id=provenance_by_id,
                owner_description=f"Infrastructure contribution for {contribution.entity_id}",
                errors=errors,
            )

    for claim in model.infrastructure_claims:
        if claim.subject_id not in entity_ids:
            errors.append(
                f"Infrastructure claim {claim.kind.value} references unknown subject "
                f"{claim.subject_id}"
            )
        # A unary claim's absent object is validated by the model itself; only a binary claim's
        # object has to resolve here (§7.2: "the other three claim kinds are binary and both
        # referenced entity IDs must resolve in the canonical model").
        if claim.kind not in UNARY_CLAIM_KINDS and claim.object_id not in entity_ids:
            errors.append(
                f"Infrastructure claim {claim.kind.value} references unknown object "
                f"{claim.object_id}"
            )
        for evidence_ref in claim.evidence_refs:
            _check_infrastructure_evidence_ref(
                evidence_ref,
                provenance_by_id=provenance_by_id,
                owner_description=(
                    f"Infrastructure claim {claim.kind.value} on {claim.subject_id}"
                ),
                errors=errors,
            )
