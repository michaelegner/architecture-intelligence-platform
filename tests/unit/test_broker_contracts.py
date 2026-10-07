"""v0.6.1 I2a: the Broker-aware contract (spec §5). Every invariant the JSON Schema format can
express is asserted twice - pydantic and the committed v0.6 schema must both reject the same shape
(the frozen-contract / schema parity rule) - and the v0.5 models must stay unable to carry Broker
data."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from app.architecture_intelligence.broker_contracts import (
    BROKER_SCHEMA_VERSION,
    ArchitectureAnswerV06,
    BrokerClaim,
    BrokerRef,
    EvidenceDataV06,
    EvidenceRelationTypeV06,
    ServiceDependenciesDataV06,
)
from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    ArchitectureDriftData,
    EvidenceData,
    EvidenceRelationType,
    ServiceDependenciesData,
)
from app.sources.owner_ids import broker_owned_id

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "architecture_intelligence"
V05_DIR = ROOT / "schemas" / "architecture_intelligence" / "v0.5"
V06_DIR = ROOT / "schemas" / "architecture_intelligence" / "v0.6"
V06_DEPENDENCIES_SCHEMA = json.loads((V06_DIR / "architecture-answer.schema.json").read_text())
V06_EVIDENCE_SCHEMA = json.loads((V06_DIR / "evidence-answer.schema.json").read_text())
V05_DEPENDENCIES_SCHEMA = json.loads((V05_DIR / "architecture-answer.schema.json").read_text())
V05_EVIDENCE_SCHEMA = json.loads((V05_DIR / "evidence-answer.schema.json").read_text())

DEPENDENCIES_V06 = ArchitectureAnswerV06[ServiceDependenciesDataV06]
EVIDENCE_V06 = ArchitectureAnswerV06[EvidenceDataV06]

SERVICE_ID = "service:invoice-service"
BROKER_ID = broker_owned_id(stable_broker_id="kafka:cluster-a")
CLAIM_ID = "aip:claim:v1:" + "a" * 64
EVIDENCE_ID = "evidence:asyncapi:urn:aip:source:filesystem:" + "b" * 64


def _broker_claim(**overrides) -> dict:
    claim = {
        "claim_id": CLAIM_ID,
        "subject": {"id": SERVICE_ID, "type": "SERVICE", "name": "InvoiceService"},
        "predicate": "USES_BROKER",
        "object": {"id": BROKER_ID, "type": "BROKER", "name": "kafka:cluster-a"},
        "evidence_refs": [EVIDENCE_ID],
    }
    claim.update(overrides)
    return claim


def dependencies_payload() -> dict:
    payload = json.loads((FIXTURES / "i1" / "answered_empty.json").read_text())
    payload["schema_version"] = "0.6"
    payload["claims"] = [_broker_claim()]
    payload["data"]["broker_claim_ids"] = [CLAIM_ID]
    payload["evidence_refs"] = [EVIDENCE_ID]
    return payload


def evidence_payload() -> dict:
    payload = json.loads((FIXTURES / "i2" / "answered_full.json").read_text())
    payload["schema_version"] = "0.6"
    data = payload["data"]
    for record in data["records"]:
        for fact in record["supports"]:
            fact["broker"] = None
    data["records"].append(
        {
            "id": EVIDENCE_ID,
            "evidence_type": "DECLARED",
            "source_type": "ASYNCAPI",
            "source_locator": "invoice-service/asyncapi.yaml",
            "source_revision": None,
            "observation": None,
            "supports": [
                {
                    "relation_type": "USES_BROKER",
                    "source_id": SERVICE_ID,
                    "target_id": BROKER_ID,
                    "broker": {"id": BROKER_ID, "type": "BROKER", "name": "kafka:cluster-a"},
                }
            ],
        }
    )
    data["records"].sort(key=lambda r: r["id"])
    data["requested_evidence_refs"] = sorted({*data["requested_evidence_refs"], EVIDENCE_ID})
    return payload


def _uses_broker_fact(payload: dict) -> dict:
    [fact] = [
        fact
        for record in payload["data"]["records"]
        for fact in record["supports"]
        if fact["relation_type"] == "USES_BROKER"
    ]
    return fact


def _other_fact(payload: dict) -> dict:
    return next(
        fact
        for record in payload["data"]["records"]
        for fact in record["supports"]
        if fact["relation_type"] != "USES_BROKER"
    )


def _rejected_by_both(model, schema: dict, payload: dict) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def _accepted_by_both(model, schema: dict, payload: dict):
    answer = model.model_validate(payload)
    jsonschema.validate(instance=payload, schema=schema)
    return answer


def _mutated(payload: dict, mutate) -> dict:
    copied = copy.deepcopy(payload)
    mutate(copied)
    return copied


# --- the valid shapes ------------------------------------------------------------------------


def test_a_broker_aware_dependency_answer_round_trips_and_validates_against_the_schema():
    answer = _accepted_by_both(DEPENDENCIES_V06, V06_DEPENDENCIES_SCHEMA, dependencies_payload())
    assert answer.schema_version == BROKER_SCHEMA_VERSION == "0.6"
    [claim] = answer.claims
    assert isinstance(claim, BrokerClaim)
    assert (claim.object.id, claim.object.type.value, claim.object.name) == (
        BROKER_ID,
        "BROKER",
        "kafka:cluster-a",
    )
    dumped = json.loads(answer.model_dump_json())
    assert dumped["claims"][0]["object"] == dependencies_payload()["claims"][0]["object"]
    assert dumped["data"]["broker_claim_ids"] == [CLAIM_ID]
    assert DEPENDENCIES_V06.model_validate_json(answer.model_dump_json()) == answer


def test_a_broker_aware_evidence_answer_round_trips_and_validates_against_the_schema():
    answer = _accepted_by_both(EVIDENCE_V06, V06_EVIDENCE_SCHEMA, evidence_payload())
    facts = [fact for record in answer.data.records for fact in record.supports]  # type: ignore[union-attr]
    [uses] = [f for f in facts if f.relation_type is EvidenceRelationTypeV06.USES_BROKER]
    assert uses.broker is not None
    assert (uses.broker.id, uses.broker.type.value, uses.broker.name) == (
        BROKER_ID,
        "BROKER",
        "kafka:cluster-a",
    )
    assert EVIDENCE_V06.model_validate_json(answer.model_dump_json()) == answer


def test_a_dependency_answer_may_mix_broker_and_other_claims_in_the_documented_order():
    payload = dependencies_payload()
    other_id = "aip:claim:v1:" + "0" * 64
    other = _broker_claim(
        claim_id=other_id,
        object={"id": BROKER_ID, "type": "BROKER", "name": "kafka:cluster-a"},
    )
    # same object id: claim_id breaks the tie, so the lower id sorts first
    payload["claims"] = [other, _broker_claim()]
    payload["data"]["broker_claim_ids"] = [other_id, CLAIM_ID]
    _accepted_by_both(DEPENDENCIES_V06, V06_DEPENDENCIES_SCHEMA, payload)


# --- BrokerClaim / BrokerRef invariants: pydantic and schema agree ---------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda p: p["claims"][0].pop("predicate"), id="predicate-omitted"),
        pytest.param(
            lambda p: p["claims"][0].update(predicate="DIRECT_DEPENDENCY"), id="predicate"
        ),
        pytest.param(
            lambda p: p["claims"][0]["subject"].update(
                id="operation:x", type="OPERATION", name="x"
            ),
            id="subject-not-a-service",
        ),
        pytest.param(lambda p: p["claims"][0]["object"].update(type="SERVICE"), id="object-type"),
        pytest.param(lambda p: p["claims"][0]["object"].pop("type"), id="object-type-omitted"),
        pytest.param(lambda p: p["claims"][0]["object"].update(id="broker:x"), id="broker-id"),
        pytest.param(lambda p: p["claims"][0]["object"].update(name=""), id="empty-name"),
        pytest.param(lambda p: p["claims"][0]["object"].update(host="h"), id="object-extra-field"),
        pytest.param(lambda p: p["claims"][0].update(evidence_refs=[]), id="no-evidence"),
        pytest.param(
            lambda p: p["claims"][0].update(evidence_refs=[EVIDENCE_ID, EVIDENCE_ID]),
            id="duplicate-evidence",
        ),
        pytest.param(lambda p: p["claims"][0].update(claim_id="claim-1"), id="malformed-claim-id"),
        pytest.param(lambda p: p["claims"][0].update(delivery={}), id="delivery-field"),
        pytest.param(
            lambda p: p["claims"][0].update(qualification="CONFIRMED"), id="qualification"
        ),
    ],
)
def test_broker_claim_invariants_are_rejected_by_pydantic_and_the_schema(mutate):
    _rejected_by_both(
        DEPENDENCIES_V06, V06_DEPENDENCIES_SCHEMA, _mutated(dependencies_payload(), mutate)
    )


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda p: p["data"].update(broker_claim_ids=[]), id="empty-broker-ids"),
        pytest.param(lambda p: p["data"].pop("broker_claim_ids"), id="broker-ids-omitted"),
        pytest.param(lambda p: p.update(outcome="NOT_ANSWERED", data=None), id="not-answered"),
        pytest.param(lambda p: p.update(tool="get_evidence"), id="wrong-tool"),
        pytest.param(lambda p: p.update(schema_version="0.5"), id="v05-label"),
        pytest.param(
            lambda p: p["data"]["service"].update(type="OPERATION"), id="data-service-not-service"
        ),
    ],
)
def test_v06_dependency_answer_invariants_are_rejected_by_pydantic_and_the_schema(mutate):
    _rejected_by_both(
        DEPENDENCIES_V06, V06_DEPENDENCIES_SCHEMA, _mutated(dependencies_payload(), mutate)
    )


def test_a_broker_claim_interleaves_with_dependency_claims_in_claim_sort_order():
    payload = json.loads((FIXTURES / "i1" / "answered_full.json").read_text())
    payload["schema_version"] = "0.6"
    payload["outcome"] = "ANSWERED"
    payload["claims"] = sorted(
        [*payload["claims"], _broker_claim()],
        key=lambda c: (c["object"]["id"], c["predicate"]),
    )
    # the Broker object id sorts before the operation object ids ("broker:" < "operation:")
    assert payload["claims"][0]["predicate"] == "USES_BROKER"
    payload["data"]["broker_claim_ids"] = [CLAIM_ID]
    payload["data"]["dependency_claim_ids"] = [
        c["claim_id"] for c in payload["claims"] if c["predicate"] == "DIRECT_DEPENDENCY"
    ]
    payload["evidence_refs"] = sorted(
        {ref for c in payload["claims"] for ref in c["evidence_refs"]}
        | {ref for c in payload["claims"] for ref in c.get("resolution_evidence_refs", [])}
    )
    _accepted_by_both(DEPENDENCIES_V06, V06_DEPENDENCIES_SCHEMA, payload)

    def reverse_claims(p: dict) -> None:
        # keep the id projections consistent with the reversed order so only the sort rule fails
        p["claims"].reverse()
        p["data"]["dependency_claim_ids"].reverse()

    out_of_order = _mutated(payload, reverse_claims)
    with pytest.raises(ValidationError, match="claims must be sorted"):
        DEPENDENCIES_V06.model_validate(out_of_order)


def test_the_v06_envelope_is_only_defined_for_its_two_data_types():
    drift = json.loads((FIXTURES / "i1" / "answered_empty.json").read_text())
    drift.update(schema_version="0.6", tool="get_architecture_drift")
    drift["data"] = {"service": drift["data"]["service"], "drift_claim_ids": []}
    with pytest.raises(ValidationError, match="only defined for"):
        ArchitectureAnswerV06[ArchitectureDriftData].model_validate(drift)

    plain = json.loads((FIXTURES / "i1" / "answered_empty.json").read_text())
    plain["schema_version"] = "0.6"
    with pytest.raises(ValidationError, match="only defined for"):
        ArchitectureAnswerV06[ServiceDependenciesData].model_validate(plain)


def test_a_v06_dependency_answer_without_a_broker_claim_is_rejected_by_both():
    def drop_broker(payload: dict) -> None:
        payload["claims"] = []
        payload["data"]["broker_claim_ids"] = [CLAIM_ID]
        payload["evidence_refs"] = []

    _rejected_by_both(
        DEPENDENCIES_V06, V06_DEPENDENCIES_SCHEMA, _mutated(dependencies_payload(), drop_broker)
    )


# --- checks only pydantic can enforce (no JSON Schema expression) ----------------------------------


def test_broker_claim_ids_must_equal_the_broker_claims_in_order():
    payload = _mutated(
        dependencies_payload(),
        lambda p: p["data"].update(broker_claim_ids=["aip:claim:v1:" + "f" * 64]),
    )
    with pytest.raises(ValidationError, match="broker_claim_ids"):
        DEPENDENCIES_V06.model_validate(payload)


def test_a_dependency_claim_id_list_that_disagrees_with_claims_is_still_rejected():
    """Proves the shared dependency/deployment partition check actually runs for v0.6 data."""
    payload = _mutated(
        dependencies_payload(),
        lambda p: p["data"].update(dependency_claim_ids=["aip:claim:v1:" + "e" * 64]),
    )
    with pytest.raises(ValidationError, match="dependency_claim_ids"):
        DEPENDENCIES_V06.model_validate(payload)


def test_broker_claim_evidence_must_be_sorted():
    other = "evidence:asyncapi:urn:aip:source:filesystem:" + "a" * 64
    payload = _mutated(
        dependencies_payload(), lambda p: p["claims"][0].update(evidence_refs=[EVIDENCE_ID, other])
    )
    with pytest.raises(ValidationError, match="sorted"):
        DEPENDENCIES_V06.model_validate(payload)


def test_top_level_evidence_refs_must_be_the_union_of_claim_evidence():
    payload = _mutated(dependencies_payload(), lambda p: p.update(evidence_refs=[]))
    with pytest.raises(ValidationError, match="evidence_refs"):
        DEPENDENCIES_V06.model_validate(payload)


def test_a_v06_envelope_locks_the_tool_to_its_specialization():
    payload = _mutated(dependencies_payload(), lambda p: p.update(tool="get_architecture_drift"))
    with pytest.raises(ValidationError, match="tool must be 'get_service_dependencies'"):
        DEPENDENCIES_V06.model_validate(payload)


def test_the_generated_v06_schemas_lock_the_tool_const():
    def tool_consts(schema: dict) -> list[str]:
        return [
            item["properties"]["tool"]["const"]
            for item in schema["allOf"]
            if "tool" in item.get("properties", {}) and "const" in item["properties"]["tool"]
        ]

    assert tool_consts(V06_DEPENDENCIES_SCHEMA) == ["get_service_dependencies"]
    assert tool_consts(V06_EVIDENCE_SCHEMA) == ["get_evidence"]


# --- the evidence answer ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda p: _uses_broker_fact(p).update(broker=None),
            id="uses-broker-without-broker",
        ),
        pytest.param(
            lambda p: _other_fact(p).update(
                broker={"id": BROKER_ID, "type": "BROKER", "name": "kafka:cluster-a"}
            ),
            id="broker-on-another-relation",
        ),
        pytest.param(
            lambda p: _uses_broker_fact(p)["broker"].update(type="SERVICE"),
            id="broker-type",
        ),
        pytest.param(lambda p: _other_fact(p).pop("broker"), id="broker-omitted"),
        pytest.param(lambda p: p.update(claims=[_broker_claim()]), id="claims-not-empty"),
        pytest.param(lambda p: p.update(tool="get_service_dependencies"), id="wrong-tool"),
        pytest.param(lambda p: p.update(schema_version="0.5"), id="v05-label"),
    ],
)
def test_v06_evidence_invariants_are_rejected_by_pydantic_and_the_schema(mutate):
    _rejected_by_both(EVIDENCE_V06, V06_EVIDENCE_SCHEMA, _mutated(evidence_payload(), mutate))


def test_a_v06_evidence_answer_without_a_uses_broker_fact_is_rejected_by_both():
    def drop_uses_broker(payload: dict) -> None:
        data = payload["data"]
        data["records"] = [r for r in data["records"] if r["id"] != EVIDENCE_ID]
        data["requested_evidence_refs"] = [r["id"] for r in data["records"]]

    _rejected_by_both(
        EVIDENCE_V06, V06_EVIDENCE_SCHEMA, _mutated(evidence_payload(), drop_uses_broker)
    )


def test_a_uses_broker_broker_ref_must_name_the_fact_target():
    payload = _mutated(
        evidence_payload(),
        lambda p: _uses_broker_fact(p)["broker"].update(
            id=broker_owned_id(stable_broker_id="kafka:other")
        ),
    )
    with pytest.raises(ValidationError, match=r"broker\.id must equal target_id"):
        EVIDENCE_V06.model_validate(payload)


def test_v06_evidence_relation_enum_is_the_v05_set_plus_exactly_uses_broker():
    v05 = {member.value for member in EvidenceRelationType}
    v06 = {member.value for member in EvidenceRelationTypeV06}
    assert v06 - v05 == {"USES_BROKER"}
    assert v05 <= v06


# --- the v0.5 contract cannot carry Broker data -------------------------------------------------------


def test_the_v05_dependency_model_and_schema_reject_a_broker_claim_and_field():
    v05_model = ArchitectureAnswer[ServiceDependenciesData]
    # the Broker-aware payload relabelled 0.5 still carries a BrokerClaim and `broker_claim_ids`
    relabelled = _mutated(dependencies_payload(), lambda p: p.update(schema_version="0.5"))
    _rejected_by_both(v05_model, V05_DEPENDENCIES_SCHEMA, relabelled)

    # a Broker-free v0.5 answer carrying only the extra field is rejected too
    only_field = json.loads((FIXTURES / "i1" / "answered_empty.json").read_text())
    only_field["data"]["broker_claim_ids"] = []
    _rejected_by_both(v05_model, V05_DEPENDENCIES_SCHEMA, only_field)


def test_the_v05_evidence_model_and_schema_reject_a_uses_broker_fact():
    relabelled = _mutated(evidence_payload(), lambda p: p.update(schema_version="0.5"))
    _rejected_by_both(ArchitectureAnswer[EvidenceData], V05_EVIDENCE_SCHEMA, relabelled)


def test_the_v05_drift_model_rejects_a_broker_claim():
    drift = json.loads((FIXTURES / "i1" / "answered_empty.json").read_text())
    drift["tool"] = "get_architecture_drift"
    drift["data"] = {"service": drift["data"]["service"], "drift_claim_ids": [CLAIM_ID]}
    drift["claims"] = [_broker_claim()]
    drift["evidence_refs"] = [EVIDENCE_ID]
    with pytest.raises(ValidationError):
        ArchitectureAnswer[ArchitectureDriftData].model_validate(drift)


def test_a_v05_answer_is_never_valid_as_v06_and_vice_versa():
    broker_free = json.loads((FIXTURES / "i1" / "answered_empty.json").read_text())
    _rejected_by_both(DEPENDENCIES_V06, V06_DEPENDENCIES_SCHEMA, broker_free)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=dependencies_payload(), schema=V05_DEPENDENCIES_SCHEMA)


def test_broker_ref_and_claim_models_are_frozen_standalone_and_unrelated_to_v05_models():
    assert not issubclass(BrokerClaim, ServiceDependenciesData)
    assert not issubclass(ServiceDependenciesDataV06, ServiceDependenciesData)
    assert not issubclass(EvidenceDataV06, EvidenceData)
    ref = BrokerRef.model_validate({"id": BROKER_ID, "type": "BROKER", "name": "kafka:cluster-a"})
    with pytest.raises(ValidationError):
        ref.name = "other"  # type: ignore[misc]
