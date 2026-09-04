import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    Coverage,
    DeliveryKind,
    DeliveryRef,
    DeliveryRelationType,
    DependencyClaim,
    DependencyPredicate,
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
)

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "architecture_intelligence" / "i1"
)
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.4"
    / "architecture-answer.schema.json"
)

EVIDENCE_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.4"
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
    assert answer.schema_version == "0.4"


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_fixture_conforms_to_frozen_schema(name):
    payload = load_fixture(name)
    jsonschema.validate(instance=payload, schema=load_schema())


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
        name="architecture-intelligence-platform", version="0.4.0", build_revision="a" * 40
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
        "schema_version": "0.4",
        "producer": _valid_producer().model_dump(),
        "tool": "get_service_dependencies",
        "outcome": "ANSWERED",
        "snapshot": _valid_snapshot().model_dump(),
        "observation_context": _valid_context(),
        "data": {"service": _valid_service_entity().model_dump(), "dependency_claim_ids": []},
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
        "schema_version": "0.4",
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
