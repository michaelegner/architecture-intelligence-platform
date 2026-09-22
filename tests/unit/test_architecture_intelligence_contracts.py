import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import (
    DEPLOYMENT_RECONCILIATION_RULE_ID,
    ArchitectureAnswer,
    ArchitectureDriftData,
    Coverage,
    DeliveryKind,
    DeliveryRef,
    DeliveryRelationType,
    DependencyClaim,
    DependencyPredicate,
    DeploymentClaim,
    DeploymentPredicate,
    DeploymentResolution,
    DeploymentResolutionMethod,
    DeploymentResolutionStatus,
    DestinationResolution,
    EntityRef,
    EntityType,
    EvidenceData,
    EvidenceRecord,
    Limitation,
    LimitationCode,
    ObservationContextRef,
    Outcome,
    Producer,
    Qualification,
    ServiceDependenciesData,
    SnapshotRef,
    WorkloadKind,
    WorkloadRef,
)
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "architecture_intelligence" / "i1"
)
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.5"
    / "architecture-answer.schema.json"
)

EVIDENCE_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.5"
    / "evidence-answer.schema.json"
)

FIXTURE_NAMES = sorted(path.name for path in FIXTURES_DIR.glob("*.json"))

ANSWER_TYPE = ArchitectureAnswer[ServiceDependenciesData]
EVIDENCE_ANSWER_TYPE = ArchitectureAnswer[EvidenceData]


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def load_evidence_schema() -> dict:
    return json.loads(EVIDENCE_SCHEMA_PATH.read_text())


def test_fixture_directory_is_not_empty():
    assert FIXTURE_NAMES


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_fixture_round_trips_through_model(name):
    payload = load_fixture(name)
    answer = ANSWER_TYPE.model_validate(payload)
    assert answer.schema_version == "0.5"


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_fixture_conforms_to_frozen_schema(name):
    payload = load_fixture(name)
    jsonschema.validate(instance=payload, schema=load_schema())


EVIDENCE_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "architecture_intelligence" / "i2"
)
EVIDENCE_FIXTURE_NAMES = sorted(path.name for path in EVIDENCE_FIXTURES_DIR.glob("*.json"))


def load_evidence_fixture(name: str) -> dict:
    return json.loads((EVIDENCE_FIXTURES_DIR / name).read_text())


def test_evidence_fixture_directory_is_not_empty():
    assert EVIDENCE_FIXTURE_NAMES


@pytest.mark.parametrize("name", EVIDENCE_FIXTURE_NAMES)
def test_evidence_fixture_round_trips_through_model(name):
    payload = load_evidence_fixture(name)
    answer = EVIDENCE_ANSWER_TYPE.model_validate(payload)
    assert answer.schema_version == "0.5"


@pytest.mark.parametrize("name", EVIDENCE_FIXTURE_NAMES)
def test_evidence_fixture_conforms_to_frozen_schema(name):
    payload = load_evidence_fixture(name)
    jsonschema.validate(instance=payload, schema=load_evidence_schema())


def test_answered_full_has_expected_outcome_and_claim_count():
    answer = ANSWER_TYPE.model_validate(load_fixture("answered_full.json"))
    assert answer.outcome == Outcome.PARTIAL
    assert len(answer.claims) == 5
    assert answer.data.dependency_claim_ids == [claim.claim_id for claim in answer.claims]


def test_not_answered_observation_context_required_has_null_context():
    answer = ANSWER_TYPE.model_validate(
        load_fixture("not_answered_observation_context_required.json")
    )
    assert answer.observation_context is None
    assert answer.data is None
    assert answer.limitations[0].code == LimitationCode.OBSERVATION_CONTEXT_REQUIRED


def _valid_producer() -> Producer:
    return Producer(
        name="architecture-intelligence-platform", version="0.4.1", build_revision="a" * 40
    )


def _valid_snapshot() -> SnapshotRef:
    return SnapshotRef(
        snapshot_id="aip:snapshot:v1:" + "b" * 64, model_revision="sha256:" + "b" * 64
    )


def _valid_context():
    return {
        "context_id": "aip:observation-context:v1:" + "c" * 64,
        "environment": "demo",
        "window_start": "2026-08-26T00:00:00.000000Z",
        "window_end": "2026-08-27T00:00:00.000000Z",
    }


def _valid_service_entity() -> EntityRef:
    return EntityRef(id="service:order-service", type=EntityType.SERVICE, name="OrderService")


def _valid_operation_entity() -> EntityRef:
    return EntityRef(
        id="operation:service:product-service:GET:/products/{id}",
        type=EntityType.OPERATION,
        name="GET /products/{id}",
        method="GET",
        path="/products/{id}",
    )


def _valid_delivery() -> DeliveryRef:
    return DeliveryRef(
        kind=DeliveryKind.SYNC_HTTP,
        relation_type=DeliveryRelationType.CALLS,
        via=_valid_operation_entity(),
    )


def _valid_claim(**overrides) -> DependencyClaim:
    fields = {
        "claim_id": "aip:claim:v1:" + "d" * 64,
        "subject": _valid_service_entity(),
        "predicate": DependencyPredicate.DIRECT_DEPENDENCY,
        "object": EntityRef(
            id="service:product-service", type=EntityType.SERVICE, name="ProductService"
        ),
        "destination_resolution": DestinationResolution.RESOLVED_SERVICE,
        "delivery": _valid_delivery(),
        "qualification": Qualification.CONFIRMED,
        "coverage": None,
        "evidence_refs": ["evidence:declared:" + "e" * 64],
        "resolution_evidence_refs": ["evidence:declared:" + "f" * 64],
    }
    fields.update(overrides)
    return DependencyClaim(**fields)


def _valid_workload(**overrides) -> WorkloadRef:
    fields = {
        "id": "urn:aip:k8s-resource:" + "1" * 64,
        "type": EntityType.WORKLOAD,
        "name": "checkout",
        "workload_kind": WorkloadKind.DEPLOYMENT,
        "namespace": "checkout",
    }
    fields.update(overrides)
    return WorkloadRef(**fields)


def _valid_deployment_claim(**overrides) -> DeploymentClaim:
    fields = {
        "claim_id": "aip:claim:v1:" + "9" * 64,
        "subject": _valid_service_entity(),
        "predicate": DeploymentPredicate.DEPLOYED_AS,
        "object": _valid_workload(),
        "resolution_method": DeploymentResolutionMethod.RESOLVED_EXPLICIT,
        "supporting_methods": [DeploymentResolutionMethod.RESOLVED_EXPLICIT],
        "reconciliation_rule_id": DEPLOYMENT_RECONCILIATION_RULE_ID,
        "reconciliation_rule_version": 1,
        "evidence_refs": ["evidence:kubernetes:" + "a" * 64],
    }
    fields.update(overrides)
    return DeploymentClaim(**fields)


def _valid_deployment_resolution(**overrides) -> DeploymentResolution:
    fields = {
        "resolution_id": "aip:deployment-resolution:v1:" + "2" * 64,
        "workload": _valid_workload(),
        "status": DeploymentResolutionStatus.RESOLVED_EXPLICIT,
        "service_id": "service:order-service",
        "candidate_service_ids": ["service:order-service"],
        "supporting_methods": [DeploymentResolutionMethod.RESOLVED_EXPLICIT],
        "supporting_evidence_refs": ["evidence:kubernetes:" + "a" * 64],
        "conflicting_evidence_refs": [],
        "limitation_codes": [],
        "claim_id": "aip:claim:v1:" + "9" * 64,
        "reconciliation_rule_id": DEPLOYMENT_RECONCILIATION_RULE_ID,
        "reconciliation_rule_version": 1,
    }
    fields.update(overrides)
    return DeploymentResolution(**fields)


def test_entity_ref_rejects_method_on_a_service():
    with pytest.raises(ValidationError):
        EntityRef(
            id="service:order-service", type=EntityType.SERVICE, name="OrderService", method="GET"
        )


def test_entity_ref_rejects_protocol_on_an_operation():
    with pytest.raises(ValidationError):
        EntityRef(
            id="operation:x:GET:/y",
            type=EntityType.OPERATION,
            name="GET /y",
            protocol="amqp",
        )


@pytest.mark.parametrize(
    ("kind", "relation_type", "entity_type"),
    [
        (DeliveryKind.SYNC_HTTP, DeliveryRelationType.SENDS, EntityType.OPERATION),
        (DeliveryKind.ASYNC_MESSAGE, DeliveryRelationType.CALLS, EntityType.QUEUE),
        (DeliveryKind.SYNC_HTTP, DeliveryRelationType.CALLS, EntityType.QUEUE),
        (DeliveryKind.ASYNC_MESSAGE, DeliveryRelationType.SENDS, EntityType.OPERATION),
    ],
)
def test_delivery_ref_rejects_combinations_outside_the_fixed_pairs_table(
    kind, relation_type, entity_type
):
    via = (
        _valid_operation_entity()
        if entity_type == EntityType.OPERATION
        else EntityRef(id="queue:x:y", type=EntityType.QUEUE, name="y")
    )
    with pytest.raises(ValidationError):
        DeliveryRef(kind=kind, relation_type=relation_type, via=via)


def test_dependency_claim_rejects_coverage_on_a_non_not_observed_qualification():
    with pytest.raises(ValidationError):
        _valid_claim(qualification=Qualification.CONFIRMED, coverage=Coverage.PARTIAL)


def test_dependency_claim_requires_at_least_one_evidence_ref():
    with pytest.raises(ValidationError):
        _valid_claim(evidence_refs=[])


@pytest.mark.parametrize(
    "claim_id",
    ["not-a-claim-id", "aip:claim:v1:", "aip:snapshot:v1:" + "a" * 64],
)
def test_dependency_claim_rejects_malformed_claim_id(claim_id):
    with pytest.raises(ValidationError):
        _valid_claim(claim_id=claim_id)


@pytest.mark.parametrize(
    "snapshot_id",
    ["not-a-snapshot-id", "aip:claim:v1:" + "a" * 64],
)
def test_snapshot_ref_rejects_malformed_snapshot_id(snapshot_id):
    with pytest.raises(ValidationError):
        SnapshotRef(snapshot_id=snapshot_id, model_revision="sha256:" + "a" * 64)


def test_snapshot_ref_rejects_malformed_model_revision():
    with pytest.raises(ValidationError):
        SnapshotRef(snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="not-a-sha256")


def test_observation_context_ref_rejects_malformed_context_id():
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(
            {
                "producer": _valid_producer().model_dump(),
                "tool": "get_service_dependencies",
                "outcome": "ANSWERED",
                "snapshot": _valid_snapshot().model_dump(),
                "observation_context": {**_valid_context(), "context_id": "not-a-context-id"},
                "data": {
                    "service": _valid_service_entity().model_dump(),
                    "dependency_claim_ids": [],
                },
                "claims": [],
                "evidence_refs": [],
                "limitations": [],
            }
        )


def test_answer_rejects_null_data_for_answered_outcome():
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(
            {
                "producer": _valid_producer().model_dump(),
                "tool": "get_service_dependencies",
                "outcome": "ANSWERED",
                "snapshot": _valid_snapshot().model_dump(),
                "observation_context": _valid_context(),
                "data": None,
                "claims": [],
                "evidence_refs": [],
                "limitations": [],
            }
        )


def test_answer_rejects_null_observation_context_without_matching_limitation():
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(
            {
                "producer": _valid_producer().model_dump(),
                "tool": "get_service_dependencies",
                "outcome": "NOT_ANSWERED",
                "snapshot": _valid_snapshot().model_dump(),
                "observation_context": None,
                "data": None,
                "claims": [],
                "evidence_refs": [],
                "limitations": [
                    Limitation(code=LimitationCode.UNKNOWN_ENTITY, message="x").model_dump()
                ],
            }
        )


def test_answer_rejects_evidence_refs_not_matching_claim_union():
    claim = _valid_claim()
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(
            {
                "producer": _valid_producer().model_dump(),
                "tool": "get_service_dependencies",
                "outcome": "ANSWERED",
                "snapshot": _valid_snapshot().model_dump(),
                "observation_context": _valid_context(),
                "data": {
                    "service": _valid_service_entity().model_dump(),
                    "dependency_claim_ids": [claim.claim_id],
                },
                "claims": [claim.model_dump()],
                "evidence_refs": [],
                "limitations": [],
            }
        )


def test_answer_rejects_dependency_claim_ids_order_mismatch():
    claim = _valid_claim()
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(
            {
                "producer": _valid_producer().model_dump(),
                "tool": "get_service_dependencies",
                "outcome": "ANSWERED",
                "snapshot": _valid_snapshot().model_dump(),
                "observation_context": _valid_context(),
                "data": {
                    "service": _valid_service_entity().model_dump(),
                    "dependency_claim_ids": [],
                },
                "claims": [claim.model_dump()],
                "evidence_refs": sorted(claim.evidence_refs + claim.resolution_evidence_refs),
                "limitations": [],
            }
        )


def test_canonical_json_bytes_ignores_dict_key_order():
    first = {"b": 1, "a": {"z": 2, "y": 3}}
    second = {"a": {"y": 3, "z": 2}, "b": 1}
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_canonical_json_bytes_is_stable_across_repeated_calls():
    answer = ANSWER_TYPE.model_validate(load_fixture("answered_empty.json"))
    assert canonical_json_bytes(answer) == canonical_json_bytes(answer)


def test_canonical_json_bytes_normalizes_timestamps():
    from datetime import UTC, datetime, timedelta, timezone

    offset_time = datetime(2026, 8, 26, 2, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    utc_time = datetime(2026, 8, 26, 0, 0, 0, tzinfo=UTC)
    assert canonical_json_bytes({"t": offset_time}) == canonical_json_bytes({"t": utc_time})
    assert canonical_json_bytes({"t": utc_time}) == b'{"t":"2026-08-26T00:00:00.000000Z"}'


# --- Stricter opaque-id format (exactly v1 + 64 lowercase hex digits, spec §12.1/§16.2/§17) ---


@pytest.mark.parametrize(
    "claim_id",
    [
        "aip:claim:v2:" + "a" * 64,  # wrong version
        "aip:claim:v1:" + "A" * 64,  # uppercase hex
        "aip:claim:v1:" + "a" * 63,  # too short
        "aip:claim:v1:" + "g" * 64,  # non-hex character
    ],
)
def test_dependency_claim_rejects_stricter_malformed_claim_ids(claim_id):
    with pytest.raises(ValidationError):
        _valid_claim(claim_id=claim_id)


@pytest.mark.parametrize(
    "snapshot_id",
    ["aip:snapshot:v2:" + "a" * 64, "aip:snapshot:v1:" + "a" * 63],
)
def test_snapshot_ref_rejects_stricter_malformed_snapshot_id(snapshot_id):
    with pytest.raises(ValidationError):
        SnapshotRef(snapshot_id=snapshot_id, model_revision="sha256:" + "a" * 64)


def test_observation_context_ref_rejects_stricter_malformed_context_id():
    with pytest.raises(ValidationError):
        ObservationContextRef(
            **{**_valid_context(), "context_id": "aip:observation-context:v2:" + "a" * 64}
        )


# --- ObservationContextRef shape rules (spec §16.1) ---


def test_observation_context_rejects_empty_environment():
    with pytest.raises(ValidationError):
        ObservationContextRef(**{**_valid_context(), "environment": ""})


def test_observation_context_rejects_environment_over_128_chars():
    with pytest.raises(ValidationError):
        ObservationContextRef(**{**_valid_context(), "environment": "x" * 129})


def test_observation_context_rejects_environment_with_control_character():
    with pytest.raises(ValidationError):
        ObservationContextRef(**{**_valid_context(), "environment": "demo\tstaging"})


def test_observation_context_rejects_environment_with_leading_or_trailing_whitespace():
    with pytest.raises(ValidationError):
        ObservationContextRef(**{**_valid_context(), "environment": " demo"})


def test_observation_context_rejects_naive_window_start():
    with pytest.raises(ValidationError):
        ObservationContextRef(**{**_valid_context(), "window_start": "2026-08-26T00:00:00.000000"})


def test_observation_context_rejects_reversed_window():
    context = _valid_context()
    with pytest.raises(ValidationError):
        ObservationContextRef(
            **{
                **context,
                "window_start": context["window_end"],
                "window_end": context["window_start"],
            }
        )


def test_observation_context_rejects_window_over_31_days():
    with pytest.raises(ValidationError):
        ObservationContextRef(**{**_valid_context(), "window_end": "2026-10-01T00:00:00.000000Z"})


# --- DependencyClaim coverage/resolution-evidence/evidence-ordering invariants (spec §14/§15/§20) ---


def test_dependency_claim_requires_coverage_for_not_observed_in_window():
    with pytest.raises(ValidationError):
        _valid_claim(qualification=Qualification.NOT_OBSERVED_IN_WINDOW, coverage=None)


def test_dependency_claim_requires_resolution_evidence_for_resolved_service():
    with pytest.raises(ValidationError):
        _valid_claim(
            destination_resolution=DestinationResolution.RESOLVED_SERVICE,
            resolution_evidence_refs=[],
        )


def test_dependency_claim_rejects_resolution_evidence_for_direct_target_fallback():
    with pytest.raises(ValidationError):
        _valid_claim(destination_resolution=DestinationResolution.DIRECT_TARGET_FALLBACK)


def test_dependency_claim_rejects_unsorted_evidence_refs():
    with pytest.raises(ValidationError):
        _valid_claim(
            evidence_refs=["evidence:declared:" + "f" * 64, "evidence:declared:" + "e" * 64]
        )


def test_dependency_claim_rejects_duplicate_evidence_refs():
    with pytest.raises(ValidationError):
        _valid_claim(
            evidence_refs=["evidence:declared:" + "e" * 64, "evidence:declared:" + "e" * 64]
        )


def test_dependency_claim_rejects_unsorted_resolution_evidence_refs():
    with pytest.raises(ValidationError):
        _valid_claim(
            resolution_evidence_refs=[
                "evidence:declared:" + "f" * 64,
                "evidence:declared:" + "e" * 64,
            ]
        )


# --- Envelope claims canonical ordering (spec §20) ---


def test_answer_rejects_claims_not_in_canonical_order():
    claim_a = _valid_claim(
        claim_id="aip:claim:v1:" + "1" * 64,
        object=EntityRef(id="service:aaa-service", type=EntityType.SERVICE, name="AaaService"),
    )
    claim_b = _valid_claim(
        claim_id="aip:claim:v1:" + "2" * 64,
        object=EntityRef(id="service:zzz-service", type=EntityType.SERVICE, name="ZzzService"),
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(
            {
                "schema_version": "0.4",
                "producer": _valid_producer().model_dump(),
                "tool": "get_service_dependencies",
                "outcome": "ANSWERED",
                "snapshot": _valid_snapshot().model_dump(),
                "observation_context": _valid_context(),
                "data": {
                    "service": _valid_service_entity().model_dump(),
                    "dependency_claim_ids": [claim_b.claim_id, claim_a.claim_id],
                },
                # deliberately out of canonical (object.id) order
                "claims": [claim_b.model_dump(), claim_a.model_dump()],
                "evidence_refs": sorted(
                    {
                        *claim_a.evidence_refs,
                        *claim_a.resolution_evidence_refs,
                        *claim_b.evidence_refs,
                        *claim_b.resolution_evidence_refs,
                    }
                ),
                "limitations": [],
            }
        )


# --- Required-field strictness: omitting a required key must fail both Pydantic and the ---
# --- committed JSON Schema (not just be silently defaulted) - spec §9/§12.                ---


def _valid_answer_dict(**overrides) -> dict:
    base = {
        "schema_version": "0.5",
        "producer": _valid_producer().model_dump(),
        "tool": "get_service_dependencies",
        "outcome": "ANSWERED",
        "snapshot": _valid_snapshot().model_dump(),
        "observation_context": _valid_context(),
        "data": {
            "service": _valid_service_entity().model_dump(),
            "dependency_claim_ids": [],
            "deployment_claim_ids": [],
            "deployment_resolutions": [],
        },
        "claims": [],
        "evidence_refs": [],
        "limitations": [],
    }
    base.update(overrides)
    return base


def test_schema_marks_all_envelope_fields_required():
    schema = load_schema()
    assert schema["required"] == [
        "schema_version",
        "producer",
        "tool",
        "outcome",
        "snapshot",
        "observation_context",
        "data",
        "claims",
        "evidence_refs",
        "limitations",
    ]


def test_schema_marks_producer_name_required():
    schema = load_schema()
    assert "name" in schema["$defs"]["Producer"]["required"]


def test_schema_marks_dependency_claim_fields_required():
    schema = load_schema()
    required = schema["$defs"]["DependencyClaim"]["required"]
    for field in ("coverage", "evidence_refs", "resolution_evidence_refs"):
        assert field in required


@pytest.mark.parametrize(
    "omit_key",
    ["snapshot", "observation_context", "data", "claims", "evidence_refs", "limitations"],
)
def test_answer_omitting_a_required_envelope_key_fails_both_pydantic_and_schema(omit_key):
    payload = _valid_answer_dict()
    del payload[omit_key]
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_producer_omitting_name_fails_both_pydantic_and_schema():
    payload = _valid_answer_dict()
    del payload["producer"]["name"]
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_claim_omitting_coverage_fails_both_pydantic_and_schema():
    claim = _valid_claim().model_dump()
    del claim["coverage"]
    payload = _valid_answer_dict(
        data={
            "service": _valid_service_entity().model_dump(),
            "dependency_claim_ids": [claim["claim_id"]],
        },
        claims=[claim],
        evidence_refs=sorted({*claim["evidence_refs"], *claim["resolution_evidence_refs"]}),
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


# --- Second review round: SnapshotRef digest consistency, JSON-Schema-encoded if/then       ---
# --- conditionals for delivery pairs / coverage / resolution evidence, and array uniqueness ---
# --- (spec §11.2/§13/§14/§15/§17/§20).                                                       ---


def test_snapshot_ref_rejects_mismatched_digests():
    with pytest.raises(ValidationError):
        SnapshotRef(snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "b" * 64)


def _answer_dict_with_claim_dict(claim: dict, **overrides) -> dict:
    base = {
        "data": {
            "service": _valid_service_entity().model_dump(),
            "dependency_claim_ids": [claim["claim_id"]],
        },
        "claims": [claim],
        "evidence_refs": sorted({*claim["evidence_refs"], *claim["resolution_evidence_refs"]}),
    }
    base.update(overrides)
    return _valid_answer_dict(**base)


def test_claim_with_invalid_delivery_pair_fails_both_pydantic_and_schema():
    claim = _valid_claim().model_dump()
    claim["delivery"] = {**claim["delivery"], "relation_type": "SENDS"}
    payload = _answer_dict_with_claim_dict(claim)
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_claim_missing_coverage_for_not_observed_in_window_fails_both_pydantic_and_schema():
    claim = _valid_claim(
        qualification=Qualification.NOT_OBSERVED_IN_WINDOW, coverage=Coverage.PARTIAL
    ).model_dump()
    claim["coverage"] = None
    payload = _answer_dict_with_claim_dict(claim)
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_claim_with_empty_resolution_evidence_for_resolved_service_fails_both_pydantic_and_schema():
    claim = _valid_claim().model_dump()
    claim["resolution_evidence_refs"] = []
    payload = _answer_dict_with_claim_dict(claim)
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_claim_with_duplicate_evidence_refs_fails_both_pydantic_and_schema():
    claim = _valid_claim().model_dump()
    duplicate = claim["evidence_refs"][0]
    claim["evidence_refs"] = [duplicate, duplicate]
    payload = _answer_dict_with_claim_dict(claim)
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_limitation_rejects_unsorted_claim_ids():
    with pytest.raises(ValidationError):
        Limitation(code=LimitationCode.UNRESOLVED_IDENTITY, message="x", claim_ids=["b", "a"])


def test_limitation_rejects_duplicate_claim_ids():
    with pytest.raises(ValidationError):
        Limitation(code=LimitationCode.UNRESOLVED_IDENTITY, message="x", claim_ids=["a", "a"])


def test_limitation_with_duplicate_claim_ids_fails_schema_too():
    payload = _valid_answer_dict(
        outcome="NOT_ANSWERED",
        observation_context=None,
        data=None,
        limitations=[
            {
                "code": "OBSERVATION_CONTEXT_REQUIRED",
                "message": "x",
                "claim_ids": ["a", "a"],
            }
        ],
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


# --- Third review round: minItems on evidence_refs, EntityRef type-specific fields, and the ---
# --- outcome/data and observation_context/limitation envelope conditionals, all now encoded ---
# --- in the schema itself (spec §8.3/§9/§11.1/§15).                                          ---


def test_claim_with_empty_evidence_refs_fails_both_pydantic_and_schema():
    claim = _valid_claim().model_dump()
    claim["evidence_refs"] = []
    payload = _answer_dict_with_claim_dict(
        claim, evidence_refs=list(claim["resolution_evidence_refs"])
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_service_entity_with_method_fails_both_pydantic_and_schema():
    payload = _valid_answer_dict(
        data={
            "service": {
                "id": "service:order-service",
                "type": "SERVICE",
                "name": "OrderService",
                "method": "GET",
            },
            "dependency_claim_ids": [],
        }
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_service_entity_with_namespace_fails_both_pydantic_and_schema():
    payload = _valid_answer_dict(
        data={
            "service": {
                "id": "service:order-service",
                "type": "SERVICE",
                "name": "OrderService",
                "namespace": "commerce",
            },
            "dependency_claim_ids": [],
        }
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_answered_with_null_data_fails_both_pydantic_and_schema():
    payload = _valid_answer_dict(data=None)
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_null_observation_context_without_required_limitation_fails_both_pydantic_and_schema():
    payload = _valid_answer_dict(
        outcome="NOT_ANSWERED",
        observation_context=None,
        data=None,
        limitations=[{"code": "UNKNOWN_ENTITY", "message": "x", "claim_ids": []}],
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


# --- Review round: `tool` must not just be a member of the Literal, but the one value valid for  ---
# --- the generic specialization actually in use (spec §14) - and each frozen schema file, being  ---
# --- generated from one concrete ArchitectureAnswer[T] class, encodes that as a `const` too.      ---


def _valid_evidence_answer_dict(**overrides) -> dict:
    base = {
        "schema_version": "0.5",
        "producer": _valid_producer().model_dump(),
        "tool": "get_evidence",
        "outcome": "ANSWERED",
        "snapshot": _valid_snapshot().model_dump(),
        "observation_context": None,
        "data": _valid_evidence_data(),
        "claims": [],
        "evidence_refs": [],
        "limitations": [],
    }
    base.update(overrides)
    return base


def _valid_observed_metadata(**overrides) -> dict:
    fields = {
        "environment": "production",
        "bucket_start": "2026-08-26T00:00:00.000000Z",
        "bucket_end": "2026-08-26T01:00:00.000000Z",
        "first_seen": "2026-08-26T00:05:00.000000Z",
        "last_seen": "2026-08-26T00:55:00.000000Z",
        "observation_count": 3,
        "service_version": None,
        "correlation_mode": None,
    }
    fields.update(overrides)
    return fields


def _valid_evidence_record(**overrides) -> dict:
    fields = {
        "id": "evidence:manifest:order-service",
        "evidence_type": "DECLARED",
        "source_type": "MANIFEST",
        "source_locator": "architecture.yaml",
        "source_revision": None,
        "observation": None,
        "supports": [],
    }
    fields.update(overrides)
    return fields


def _valid_evidence_data(**overrides) -> dict:
    fields = {
        "requested_evidence_refs": ["evidence:manifest:order-service"],
        "records": [_valid_evidence_record()],
        "missing_evidence_refs": [],
    }
    fields.update(overrides)
    return fields


def test_dependency_answer_rejects_get_evidence_as_tool_fails_both_pydantic_and_schema():
    payload = _valid_answer_dict(tool="get_evidence")
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_evidence_answer_rejects_get_service_dependencies_as_tool_fails_both_pydantic_and_schema():
    payload = _valid_evidence_answer_dict(tool="get_service_dependencies")
    with pytest.raises(ValidationError):
        EVIDENCE_ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_evidence_schema())


def test_evidence_answer_rejects_nonempty_claims_fails_both_pydantic_and_schema():
    claim = _valid_claim().model_dump()
    payload = _valid_evidence_answer_dict(claims=[claim])
    with pytest.raises(ValidationError):
        EVIDENCE_ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_evidence_schema())


def test_evidence_answer_rejects_nonempty_top_level_evidence_refs_fails_both_pydantic_and_schema():
    payload = _valid_evidence_answer_dict(evidence_refs=["evidence:manifest:order-service"])
    with pytest.raises(ValidationError):
        EVIDENCE_ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_evidence_schema())


def test_evidence_answer_rejects_nonnull_observation_context_fails_both_pydantic_and_schema():
    """Spec §12/§14: get_evidence is not runtime-context-sensitive - observation_context must be
    null for every get_evidence answer, not just for the OBSERVATION_CONTEXT_REQUIRED case."""
    payload = _valid_evidence_answer_dict(observation_context=_valid_context())
    with pytest.raises(ValidationError):
        EVIDENCE_ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_evidence_schema())


def test_evidence_answer_fixture_conforms_to_frozen_evidence_schema():
    """Sanity check that a genuinely valid EvidenceData answer validates against both - the four
    tests above only prove invalid ones are rejected."""
    payload = _valid_evidence_answer_dict()
    EVIDENCE_ANSWER_TYPE.model_validate(payload)
    jsonschema.validate(instance=payload, schema=load_evidence_schema())


def test_evidence_data_rejects_id_in_both_records_and_missing():
    with pytest.raises(ValidationError):
        EvidenceData.model_validate(
            _valid_evidence_data(missing_evidence_refs=["evidence:manifest:order-service"])
        )


def test_evidence_data_rejects_incomplete_partition_of_requested_refs():
    with pytest.raises(ValidationError):
        EvidenceData.model_validate(
            _valid_evidence_data(
                requested_evidence_refs=[
                    "evidence:manifest:order-service",
                    "evidence:openapi:product-service",
                ]
            )
        )


def test_evidence_record_requires_observation_for_observed_evidence_fails_both_pydantic_and_schema():
    record = _valid_evidence_record(evidence_type="OBSERVED", source_type="OPENTELEMETRY")
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(record)
    # $ref-based sub-schemas share one top-level $defs, so a record is validated in place inside a
    # full evidence answer (matching the rest of this file's "fails both" pattern) rather than as
    # an extracted $defs fragment, which would leave its own $ref targets unresolved.
    payload = _valid_evidence_answer_dict(data=_valid_evidence_data(records=[record]))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_evidence_schema())


def test_evidence_record_rejects_observation_for_declared_evidence_fails_both_pydantic_and_schema():
    record = _valid_evidence_record(observation=_valid_observed_metadata())
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(record)
    payload = _valid_evidence_answer_dict(data=_valid_evidence_data(records=[record]))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_evidence_schema())


@pytest.mark.parametrize(
    "supports",
    [
        # Out of (relation_type, source_id, target_id) order.
        [
            {"relation_type": "CALLS", "source_id": "service:zzz", "target_id": "operation:x"},
            {"relation_type": "CALLS", "source_id": "service:aaa", "target_id": "operation:x"},
        ],
        # Exact duplicate.
        [
            {"relation_type": "CALLS", "source_id": "service:a", "target_id": "operation:x"},
            {"relation_type": "CALLS", "source_id": "service:a", "target_id": "operation:x"},
        ],
    ],
)
def test_evidence_record_rejects_unsorted_or_duplicated_supports(supports):
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(_valid_evidence_record(supports=supports))


@pytest.mark.parametrize("field", ["requested_evidence_refs", "missing_evidence_refs"])
@pytest.mark.parametrize(
    "refs",
    [
        ["evidence:manifest:zzz-service", "evidence:manifest:aaa-service"],  # unsorted
        ["evidence:manifest:order-service", "evidence:manifest:order-service"],  # duplicate
    ],
)
def test_evidence_data_rejects_unsorted_or_duplicated_refs(field, refs):
    with pytest.raises(ValidationError):
        EvidenceData.model_validate(_valid_evidence_data(**{field: refs}))


def test_evidence_data_rejects_records_not_sorted_by_id():
    unsorted_records = [
        _valid_evidence_record(id="evidence:manifest:zzz-service"),
        _valid_evidence_record(id="evidence:manifest:aaa-service"),
    ]
    with pytest.raises(ValidationError):
        EvidenceData.model_validate(_valid_evidence_data(records=unsorted_records))


def test_evidence_data_rejects_duplicate_record_ids():
    record = _valid_evidence_record()
    with pytest.raises(ValidationError):
        EvidenceData.model_validate(_valid_evidence_data(records=[record, record]))


# --- v0.4.0 I3.1: drift contract compatibility (I3 spec §48) -------------------------------------

DRIFT_ANSWER_TYPE = ArchitectureAnswer[ArchitectureDriftData]

DRIFT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.5"
    / "drift-answer.schema.json"
)


def load_drift_schema() -> dict:
    return json.loads(DRIFT_SCHEMA_PATH.read_text())


def _valid_drift_answer_dict(**overrides) -> dict:
    claim = _valid_claim(qualification=Qualification.OBSERVED_ONLY)
    payload = {
        "schema_version": "0.5",
        "producer": _valid_producer().model_dump(mode="json"),
        "tool": "get_architecture_drift",
        "outcome": "ANSWERED",
        "snapshot": _valid_snapshot().model_dump(mode="json"),
        "observation_context": _valid_context(),
        "data": {
            "service": _valid_service_entity().model_dump(mode="json"),
            "drift_claim_ids": [claim.claim_id],
        },
        "claims": [claim.model_dump(mode="json")],
        "evidence_refs": sorted(set(claim.evidence_refs) | set(claim.resolution_evidence_refs)),
        "limitations": [],
    }
    payload.update(overrides)
    return payload


def test_valid_drift_answer_passes_both_pydantic_and_the_frozen_schema():
    payload = _valid_drift_answer_dict()
    DRIFT_ANSWER_TYPE.model_validate(payload)
    jsonschema.validate(instance=payload, schema=load_drift_schema())


def test_architecture_drift_data_is_closed():
    with pytest.raises(ValidationError):
        ArchitectureDriftData.model_validate(
            {
                "service": _valid_service_entity().model_dump(mode="json"),
                "drift_claim_ids": [],
                "severity": "HIGH",
            }
        )


def test_drift_answer_rejects_extra_top_level_fields_in_both_pydantic_and_schema():
    payload = _valid_drift_answer_dict(drift_score=0.5)
    with pytest.raises(ValidationError):
        DRIFT_ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_drift_schema())


def test_evidence_request_rejects_non_evidence_reference_items():
    with pytest.raises(ValidationError) as exc_info:
        EvidenceRequest.model_validate(
            {
                "evidence_refs": ["service:order-service"],
                "snapshot_id": "aip:snapshot:v1:" + "a" * 64,
            }
        )

    assert exc_info.value.errors()[0]["type"] == "string_pattern_mismatch"


def test_evidence_request_rejects_oversized_reference_items():
    with pytest.raises(ValidationError) as exc_info:
        EvidenceRequest.model_validate(
            {
                "evidence_refs": ["evidence:" + "a" * 504],
                "snapshot_id": "aip:snapshot:v1:" + "a" * 64,
            }
        )

    assert exc_info.value.errors()[0]["type"] == "string_too_long"


def test_drift_request_is_closed():
    with pytest.raises(ValidationError):
        ArchitectureDriftRequest.model_validate(
            {"service_id": "service:order-service", "include_confirmed": True}
        )


def test_drift_request_field_validation_equals_dependencies_request():
    """I3 spec §9: `ArchitectureDriftRequest`'s field validation SHALL be equivalent to
    `ServiceDependenciesRequest`'s, while §9.1 keeps them separate public contract types. The three
    field declarations are therefore deliberately restated rather than inherited, so that the frozen
    I1 model (and the MCP `inputSchema` derived from it) is left untouched - this test is what stops
    the restatement from silently drifting apart. Only the model's own identity may differ."""

    def _without_identity(schema: dict) -> dict:
        return {key: value for key, value in schema.items() if key not in {"title", "description"}}

    assert _without_identity(ArchitectureDriftRequest.model_json_schema()) == _without_identity(
        ServiceDependenciesRequest.model_json_schema()
    )


def test_drift_answer_tool_const_is_exact_in_the_frozen_schema():
    """The shared `tool` Literal admits all three names, so each specialization's schema has to lock
    its own - otherwise a drift answer carrying `tool: get_service_dependencies` would be
    structurally valid JSON against the drift schema."""
    payload = _valid_drift_answer_dict(tool="get_service_dependencies")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_drift_schema())


def test_drift_answer_rejects_a_mismatched_tool_at_runtime():
    with pytest.raises(ValidationError):
        DRIFT_ANSWER_TYPE.model_validate(_valid_drift_answer_dict(tool="get_service_dependencies"))


def test_dependency_and_evidence_answers_keep_their_own_tool_consts():
    """I3 spec §11/§70: widening the shared `tool` Literal for the third specialization must not
    loosen what the two already-qualified schemas mean."""
    for schema, expected in (
        (load_schema(), "get_service_dependencies"),
        (load_evidence_schema(), "get_evidence"),
        (load_drift_schema(), "get_architecture_drift"),
    ):
        consts = [
            block["properties"]["tool"]["const"]
            for block in schema["allOf"]
            if set(block) == {"properties"} and "tool" in block["properties"]
        ]
        assert consts == [expected]


def test_drift_answer_requires_observation_context_unless_refused_for_it():
    payload = _valid_drift_answer_dict(
        outcome="NOT_ANSWERED",
        observation_context=None,
        data=None,
        claims=[],
        evidence_refs=[],
        limitations=[Limitation(code=LimitationCode.UNKNOWN_ENTITY, message="x").model_dump()],
    )
    with pytest.raises(ValidationError):
        DRIFT_ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_drift_schema())


def test_drift_answer_accepts_null_observation_context_for_a_context_refusal():
    payload = _valid_drift_answer_dict(
        outcome="NOT_ANSWERED",
        observation_context=None,
        data=None,
        claims=[],
        evidence_refs=[],
        limitations=[
            Limitation(code=LimitationCode.OBSERVATION_CONTEXT_REQUIRED, message="x").model_dump()
        ],
    )
    DRIFT_ANSWER_TYPE.model_validate(payload)
    jsonschema.validate(instance=payload, schema=load_drift_schema())


def test_drift_answer_rejects_drift_claim_ids_that_do_not_match_claims():
    claim = _valid_claim(qualification=Qualification.OBSERVED_ONLY)
    with pytest.raises(ValidationError):
        DRIFT_ANSWER_TYPE.model_validate(
            _valid_drift_answer_dict(
                data={
                    "service": _valid_service_entity().model_dump(mode="json"),
                    "drift_claim_ids": [],
                },
                claims=[claim.model_dump(mode="json")],
            )
        )


def test_drift_answer_rejects_drift_claim_ids_in_a_different_order():
    first = _valid_claim(
        claim_id="aip:claim:v1:" + "1" * 64,
        qualification=Qualification.OBSERVED_ONLY,
        object=EntityRef(id="service:a-service", type=EntityType.SERVICE, name="A"),
    )
    second = _valid_claim(
        claim_id="aip:claim:v1:" + "2" * 64,
        qualification=Qualification.OBSERVED_ONLY,
        object=EntityRef(id="service:z-service", type=EntityType.SERVICE, name="Z"),
    )
    with pytest.raises(ValidationError):
        DRIFT_ANSWER_TYPE.model_validate(
            _valid_drift_answer_dict(
                data={
                    "service": _valid_service_entity().model_dump(mode="json"),
                    "drift_claim_ids": [second.claim_id, first.claim_id],
                },
                claims=[first.model_dump(mode="json"), second.model_dump(mode="json")],
                evidence_refs=sorted(
                    set(first.evidence_refs)
                    | set(first.resolution_evidence_refs)
                    | set(second.evidence_refs)
                    | set(second.resolution_evidence_refs)
                ),
            )
        )


def test_drift_answer_rejects_an_evidence_union_that_is_not_exact():
    claim = _valid_claim(qualification=Qualification.OBSERVED_ONLY)
    with pytest.raises(ValidationError):
        DRIFT_ANSWER_TYPE.model_validate(
            _valid_drift_answer_dict(evidence_refs=sorted(claim.evidence_refs))
        )


# --- v0.5.0 I3 slice 1: WorkloadRef / DeploymentClaim / DeploymentResolution contract freeze ---
# --- (spec §11/§12/§13) and the closed DependencyClaim | DeploymentClaim union (spec §14.2). ---


def test_workload_ref_round_trips():
    workload = _valid_workload()
    assert workload.type == EntityType.WORKLOAD
    assert WorkloadRef.model_validate(workload.model_dump()) == workload


def test_workload_ref_rejects_a_non_workload_type():
    with pytest.raises(ValidationError):
        WorkloadRef.model_validate({**_valid_workload().model_dump(), "type": "SERVICE"})


def test_workload_ref_exposes_exactly_its_frozen_field_allowlist():
    """§21.6/spec §11: `WorkloadRef` leaks no Pod/cluster internals beyond its own frozen fields -
    asserted here as an exact field-set match (not just `extra=forbid` rejecting one extra field
    on write), so a future field addition to the model is caught by this test too, not just by
    someone remembering to update it."""
    assert set(WorkloadRef.model_fields) == {"id", "type", "name", "workload_kind", "namespace"}
    dumped = set(_valid_workload().model_dump())
    assert dumped == {"id", "type", "name", "workload_kind", "namespace"}
    with pytest.raises(ValidationError):
        WorkloadRef.model_validate({**_valid_workload().model_dump(), "cluster_uid": "c1"})


def test_dependency_claim_rejects_a_workload_typed_object():
    # DependencyClaim.object is typed plain EntityRef, not WorkloadRef - the model_validator guard
    # (not just EntityRef's own type-specific-field rules) must reject a Workload-shaped value.
    with pytest.raises(ValidationError):
        _valid_claim(object=EntityRef(id="wl:x", type=EntityType.WORKLOAD, name="x"))


def test_dependency_claim_rejects_a_non_service_subject():
    with pytest.raises(ValidationError):
        _valid_claim(subject=_valid_operation_entity())


def test_deployment_claim_round_trips():
    claim = _valid_deployment_claim()
    assert claim.predicate == DeploymentPredicate.DEPLOYED_AS
    assert DeploymentClaim.model_validate(claim.model_dump()) == claim


def test_deployment_claim_rejects_a_non_service_subject():
    with pytest.raises(ValidationError):
        _valid_deployment_claim(subject=_valid_operation_entity())


def test_deployment_claim_requires_at_least_one_evidence_ref():
    with pytest.raises(ValidationError):
        _valid_deployment_claim(evidence_refs=[])


def test_deployment_claim_requires_at_least_one_supporting_method():
    with pytest.raises(ValidationError):
        _valid_deployment_claim(supporting_methods=[])


def test_deployment_claim_rejects_duplicate_supporting_methods():
    with pytest.raises(ValidationError):
        _valid_deployment_claim(
            supporting_methods=[
                DeploymentResolutionMethod.RESOLVED_EXPLICIT,
                DeploymentResolutionMethod.RESOLVED_EXPLICIT,
            ]
        )


def test_deployment_claim_rejects_supporting_methods_out_of_canonical_order():
    with pytest.raises(ValidationError):
        _valid_deployment_claim(
            resolution_method=DeploymentResolutionMethod.RESOLVED_CONFIGURED,
            supporting_methods=[
                DeploymentResolutionMethod.RESOLVED_CONFIGURED,
                DeploymentResolutionMethod.RESOLVED_EXPLICIT,
            ],
        )


def test_deployment_claim_rejects_a_resolution_method_that_is_not_the_strongest():
    with pytest.raises(ValidationError):
        _valid_deployment_claim(
            resolution_method=DeploymentResolutionMethod.RESOLVED_CONFIGURED,
            supporting_methods=[
                DeploymentResolutionMethod.RESOLVED_EXPLICIT,
                DeploymentResolutionMethod.RESOLVED_CONFIGURED,
            ],
        )


def test_deployment_claim_accepts_a_weaker_agreeing_method_as_the_strongest_when_alone():
    claim = _valid_deployment_claim(
        resolution_method=DeploymentResolutionMethod.RESOLVED_OBSERVED,
        supporting_methods=[DeploymentResolutionMethod.RESOLVED_OBSERVED],
    )
    assert claim.resolution_method == DeploymentResolutionMethod.RESOLVED_OBSERVED


def test_deployment_claim_rejects_a_non_default_reconciliation_rule_id():
    with pytest.raises(ValidationError):
        DeploymentClaim.model_validate(
            {**_valid_deployment_claim().model_dump(), "reconciliation_rule_id": "some-other-rule"}
        )


def test_deployment_claim_rejects_a_non_default_reconciliation_rule_version():
    with pytest.raises(ValidationError):
        DeploymentClaim.model_validate(
            {**_valid_deployment_claim().model_dump(), "reconciliation_rule_version": 2}
        )


@pytest.mark.parametrize(
    "claim_id",
    ["not-a-claim-id", "aip:deployment-resolution:v1:" + "a" * 64],
)
def test_deployment_claim_rejects_malformed_claim_id(claim_id):
    with pytest.raises(ValidationError):
        _valid_deployment_claim(claim_id=claim_id)


def test_deployment_resolution_round_trips_when_resolved():
    resolution = _valid_deployment_resolution()
    assert DeploymentResolution.model_validate(resolution.model_dump()) == resolution


def test_deployment_resolution_round_trips_when_unresolved():
    resolution = _valid_deployment_resolution(
        workload=None,
        status=DeploymentResolutionStatus.UNRESOLVED,
        service_id=None,
        candidate_service_ids=[],
        supporting_methods=[],
        claim_id=None,
        limitation_codes=[LimitationCode.DEPLOYMENT_IDENTITY_UNRESOLVED],
    )
    assert resolution.claim_id is None
    assert DeploymentResolution.model_validate(resolution.model_dump()) == resolution


@pytest.mark.parametrize("missing_field", ["workload", "service_id", "claim_id"])
def test_deployment_resolution_resolved_status_requires_the_resolved_fields(missing_field):
    with pytest.raises(ValidationError):
        _valid_deployment_resolution(**{missing_field: None})


def test_deployment_resolution_resolved_status_requires_matching_candidate_service_ids():
    with pytest.raises(ValidationError):
        _valid_deployment_resolution(candidate_service_ids=["service:a-different-service"])


def test_deployment_resolution_non_resolved_status_rejects_a_non_null_claim_id():
    with pytest.raises(ValidationError):
        _valid_deployment_resolution(
            workload=None,
            status=DeploymentResolutionStatus.CONFLICT,
            service_id=None,
            candidate_service_ids=[],
        )


@pytest.mark.parametrize(
    "resolution_id",
    ["not-a-resolution-id", "aip:claim:v1:" + "a" * 64],
)
def test_deployment_resolution_rejects_malformed_resolution_id(resolution_id):
    with pytest.raises(ValidationError):
        _valid_deployment_resolution(resolution_id=resolution_id)


def test_deployment_resolution_rejects_a_malformed_non_null_claim_id():
    with pytest.raises(ValidationError):
        _valid_deployment_resolution(claim_id="not-a-claim-id")


def test_deployment_resolution_rejects_unsorted_candidate_service_ids():
    with pytest.raises(ValidationError):
        _valid_deployment_resolution(
            service_id="service:a",
            candidate_service_ids=["service:b", "service:a"],
        )


def _service_dependencies_answer_dict(*, claims: list, data_overrides: dict | None = None) -> dict:
    dependency_ids = [c["claim_id"] for c in claims if c.get("predicate") == "DIRECT_DEPENDENCY"]
    deployment_ids = [c["claim_id"] for c in claims if c.get("predicate") == "DEPLOYED_AS"]
    evidence_refs = sorted(
        {
            ref
            for c in claims
            for ref in (*c["evidence_refs"], *c.get("resolution_evidence_refs", []))
        }
    )
    data = {
        "service": _valid_service_entity().model_dump(mode="json"),
        "dependency_claim_ids": dependency_ids,
        "deployment_claim_ids": deployment_ids,
        "deployment_resolutions": [],
    }
    if data_overrides:
        data.update(data_overrides)
    return _valid_answer_dict(data=data, claims=claims, evidence_refs=evidence_refs)


_SHARED_OBJECT_ID = "urn:aip:k8s-resource:" + "3" * 64


def _mixed_claim_pair() -> tuple[DependencyClaim, DeploymentClaim]:
    # Deliberately the SAME object.id on both claims (a Service and a Workload can never really
    # share an id in production, but this unit test isolates the predicate tiebreaker specifically -
    # with object.id tied, ordering must fall through to `predicate`: "DEPLOYED_AS" < "DIRECT_
    # DEPENDENCY" lexicographically, so the DeploymentClaim sorts first).
    dependency_claim = _valid_claim(
        object=EntityRef(id=_SHARED_OBJECT_ID, type=EntityType.SERVICE, name="Aaa")
    )
    deployment_claim = _valid_deployment_claim(object=_valid_workload(id=_SHARED_OBJECT_ID))
    return dependency_claim, deployment_claim


def test_answer_accepts_a_mixed_claims_list_sorted_by_object_id_then_predicate():
    dependency_claim, deployment_claim = _mixed_claim_pair()
    payload = _service_dependencies_answer_dict(
        claims=[
            deployment_claim.model_dump(mode="json"),
            dependency_claim.model_dump(mode="json"),
        ]
    )
    answer = ANSWER_TYPE.model_validate(payload)
    assert [type(c).__name__ for c in answer.claims] == ["DeploymentClaim", "DependencyClaim"]
    assert answer.data.dependency_claim_ids == [dependency_claim.claim_id]
    assert answer.data.deployment_claim_ids == [deployment_claim.claim_id]


def test_answer_rejects_a_mixed_claims_list_in_the_wrong_order():
    dependency_claim, deployment_claim = _mixed_claim_pair()
    payload = _service_dependencies_answer_dict(
        claims=[
            dependency_claim.model_dump(mode="json"),
            deployment_claim.model_dump(mode="json"),
        ]
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)


def test_answer_rejects_an_unrecognized_predicate_value():
    bad_claim = {**_valid_claim().model_dump(mode="json"), "predicate": "SOMETHING_ELSE"}
    payload = _valid_answer_dict(
        data={
            "service": _valid_service_entity().model_dump(mode="json"),
            "dependency_claim_ids": [],
            "deployment_claim_ids": [],
            "deployment_resolutions": [],
        },
        claims=[bad_claim],
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)


def test_drift_answer_rejects_a_deployment_claim_in_claims():
    deployment_claim = _valid_deployment_claim()
    payload = _valid_drift_answer_dict(
        data={
            "service": _valid_service_entity().model_dump(mode="json"),
            "drift_claim_ids": [deployment_claim.claim_id],
        },
        claims=[deployment_claim.model_dump(mode="json")],
        evidence_refs=deployment_claim.evidence_refs,
    )
    with pytest.raises(ValidationError):
        DRIFT_ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_drift_schema())


def test_service_dependencies_data_partitions_claims_by_type():
    dependency_claim = _valid_claim()
    deployment_claim = _valid_deployment_claim(
        object=_valid_workload(id="urn:aip:k8s-resource:" + "4" * 64)
    )
    payload = _service_dependencies_answer_dict(
        claims=sorted(
            [dependency_claim.model_dump(mode="json"), deployment_claim.model_dump(mode="json")],
            key=lambda c: (c["object"]["id"], c["predicate"]),
        )
    )
    answer = ANSWER_TYPE.model_validate(payload)
    assert answer.data.dependency_claim_ids == [dependency_claim.claim_id]
    assert answer.data.deployment_claim_ids == [deployment_claim.claim_id]


def test_service_dependencies_data_rejects_a_deployment_claim_id_not_in_deployment_claim_ids():
    deployment_claim = _valid_deployment_claim()
    payload = _service_dependencies_answer_dict(
        claims=[deployment_claim.model_dump(mode="json")],
        data_overrides={"deployment_claim_ids": []},
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)


def test_service_dependencies_data_rejects_a_resolution_claim_id_not_present_in_claims():
    deployment_claim = _valid_deployment_claim()
    resolution = _valid_deployment_resolution(claim_id=deployment_claim.claim_id)
    payload = _service_dependencies_answer_dict(
        claims=[deployment_claim.model_dump(mode="json")],
        data_overrides={
            # A different DeploymentClaim id than the one actually present in claims.
            "deployment_resolutions": [
                {**resolution.model_dump(mode="json"), "claim_id": "aip:claim:v1:" + "0" * 64}
            ]
        },
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)


def test_service_dependencies_data_accepts_a_resolution_claim_id_present_in_claims():
    deployment_claim = _valid_deployment_claim()
    resolution = _valid_deployment_resolution(claim_id=deployment_claim.claim_id)
    payload = _service_dependencies_answer_dict(
        claims=[deployment_claim.model_dump(mode="json")],
        data_overrides={"deployment_resolutions": [resolution.model_dump(mode="json")]},
    )
    answer = ANSWER_TYPE.model_validate(payload)
    assert answer.data.deployment_resolutions[0].claim_id == deployment_claim.claim_id


def test_deployment_resolutions_must_be_sorted_by_resolution_id():
    first = _valid_deployment_resolution(
        resolution_id="aip:deployment-resolution:v1:" + "1" * 64,
        claim_id=None,
        workload=None,
        status=DeploymentResolutionStatus.UNRESOLVED,
        service_id=None,
        candidate_service_ids=[],
        supporting_methods=[],
    )
    second = _valid_deployment_resolution(
        resolution_id="aip:deployment-resolution:v1:" + "2" * 64,
        claim_id=None,
        workload=None,
        status=DeploymentResolutionStatus.UNRESOLVED,
        service_id=None,
        candidate_service_ids=[],
        supporting_methods=[],
    )
    with pytest.raises(ValidationError):
        ServiceDependenciesData(
            service=_valid_service_entity(),
            dependency_claim_ids=[],
            deployment_claim_ids=[],
            # Deliberately out of resolution_id order.
            deployment_resolutions=[second, first],
        )


def test_service_dependencies_schema_marks_deployment_fields_required():
    schema = load_schema()
    data_schema = schema["$defs"]["ServiceDependenciesData"]
    for field in ("deployment_claim_ids", "deployment_resolutions"):
        assert field in data_schema["required"]


def test_deployment_claim_schema_marks_fields_required():
    schema = load_schema()
    required = schema["$defs"]["DeploymentClaim"]["required"]
    for field in ("evidence_refs", "supporting_methods", "resolution_method"):
        assert field in required


def test_architecture_answer_schema_defines_a_discriminated_claims_union():
    # PR #212 re-review finding: the original `or "$ref"` branch passed even for a single,
    # non-union `$ref` (a real regression - dropping one claim arm - would have gone undetected).
    # Assert the exact discriminator mapping and both oneOf arms instead.
    schema = load_schema()
    claims_schema = schema["properties"]["claims"]["items"]
    assert claims_schema["discriminator"]["propertyName"] == "predicate"
    assert claims_schema["discriminator"]["mapping"] == {
        "DIRECT_DEPENDENCY": "#/$defs/DependencyClaim",
        "DEPLOYED_AS": "#/$defs/DeploymentClaim",
    }
    assert {entry["$ref"] for entry in claims_schema["oneOf"]} == {
        "#/$defs/DependencyClaim",
        "#/$defs/DeploymentClaim",
    }


# --- PR #212 review round: a Pydantic field default is silently omitted from the generated JSON  --
# --- Schema's `required` list, so a defaulted discriminator/identity field was NOT actually       --
# --- required for a non-Pydantic client even though Pydantic itself always filled it in - fixed    --
# --- by removing every such default; these prove both layers now reject the omission (spec         --
# --- §11-§14.2), and that a WORKLOAD-typed `service` field can no longer slip past either layer.    --


def test_workload_ref_omitting_type_fails_both_pydantic_and_schema():
    deployment_claim = _valid_deployment_claim().model_dump(mode="json")
    payload = _service_dependencies_answer_dict(claims=[deployment_claim])
    del payload["claims"][0]["object"]["type"]
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_dependency_claim_omitting_predicate_fails_both_pydantic_and_schema():
    claim = _valid_claim().model_dump(mode="json")
    payload = _service_dependencies_answer_dict(claims=[claim])
    del payload["claims"][0]["predicate"]
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_deployment_claim_omitting_predicate_fails_both_pydantic_and_schema():
    claim = _valid_deployment_claim().model_dump(mode="json")
    payload = _service_dependencies_answer_dict(claims=[claim])
    del payload["claims"][0]["predicate"]
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


@pytest.mark.parametrize("field", ["reconciliation_rule_id", "reconciliation_rule_version"])
def test_deployment_claim_omitting_reconciliation_rule_field_fails_both_pydantic_and_schema(field):
    claim = _valid_deployment_claim().model_dump(mode="json")
    payload = _service_dependencies_answer_dict(claims=[claim])
    del payload["claims"][0][field]
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


@pytest.mark.parametrize("field", ["reconciliation_rule_id", "reconciliation_rule_version"])
def test_deployment_resolution_omitting_reconciliation_rule_field_fails_both_pydantic_and_schema(
    field,
):
    deployment_claim = _valid_deployment_claim()
    resolution = _valid_deployment_resolution(claim_id=deployment_claim.claim_id)
    resolution_dict = resolution.model_dump(mode="json")
    del resolution_dict[field]
    payload = _service_dependencies_answer_dict(
        claims=[deployment_claim.model_dump(mode="json")],
        data_overrides={"deployment_resolutions": [resolution_dict]},
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_deployment_claim_rejects_a_non_service_subject_both_pydantic_and_schema():
    # _valid_deployment_claim's own model_validator already rejects an invalid subject before it
    # can be constructed - build the invalid shape as a raw dict instead, mirroring every other
    # "_and_schema" test in this file.
    claim = _valid_deployment_claim().model_dump(mode="json")
    claim["subject"] = _valid_operation_entity().model_dump(mode="json")
    payload = _service_dependencies_answer_dict(
        claims=[claim], data_overrides={"deployment_claim_ids": [claim["claim_id"]]}
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_deployment_resolution_rejects_a_malformed_claim_id_both_pydantic_and_schema():
    deployment_claim = _valid_deployment_claim()
    resolution = _valid_deployment_resolution(claim_id=deployment_claim.claim_id)
    resolution_dict = resolution.model_dump(mode="json")
    resolution_dict["claim_id"] = "not-a-claim-id"
    payload = _service_dependencies_answer_dict(
        claims=[deployment_claim.model_dump(mode="json")],
        data_overrides={"deployment_resolutions": [resolution_dict]},
    )
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_service_dependencies_data_rejects_a_workload_typed_service_both_pydantic_and_schema():
    payload = _valid_answer_dict()
    payload["data"]["service"]["type"] = "WORKLOAD"
    with pytest.raises(ValidationError):
        ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_schema())


def test_drift_data_rejects_a_workload_typed_service_both_pydantic_and_schema():
    payload = _valid_drift_answer_dict()
    payload["data"]["service"]["type"] = "WORKLOAD"
    with pytest.raises(ValidationError):
        DRIFT_ANSWER_TYPE.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=load_drift_schema())


def test_workload_ref_schema_marks_type_required():
    schema = load_schema()
    assert "type" in schema["$defs"]["WorkloadRef"]["required"]


def test_dependency_claim_schema_marks_predicate_required():
    schema = load_schema()
    assert "predicate" in schema["$defs"]["DependencyClaim"]["required"]


def test_deployment_claim_schema_marks_predicate_and_rule_fields_required():
    schema = load_schema()
    required = schema["$defs"]["DeploymentClaim"]["required"]
    for field in ("predicate", "reconciliation_rule_id", "reconciliation_rule_version"):
        assert field in required


def test_deployment_resolution_schema_marks_rule_fields_required():
    schema = load_schema()
    required = schema["$defs"]["DeploymentResolution"]["required"]
    for field in ("reconciliation_rule_id", "reconciliation_rule_version"):
        assert field in required


def test_service_dependencies_data_schema_requires_service_typed_service():
    schema = load_schema()
    data_schema = schema["$defs"]["ServiceDependenciesData"]
    assert data_schema["allOf"][0]["properties"]["service"]["properties"]["type"]["const"] == (
        "SERVICE"
    )


def test_drift_data_schema_requires_service_typed_service():
    schema = load_drift_schema()
    data_schema = schema["$defs"]["ArchitectureDriftData"]
    assert data_schema["allOf"][0]["properties"]["service"]["properties"]["type"]["const"] == (
        "SERVICE"
    )
