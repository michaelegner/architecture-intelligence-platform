"""v0.6.1 I1a: the canonical Broker entity and `USES_BROKER` relation - id formula, merge, and
validation (spec §4.1, §4.4). No adapter emits Brokers yet; these tests build models directly."""

import hashlib

import pytest

from app.canonical.model import ArchitectureModel, Broker, Relation, Service
from app.graph.claim_planning import model_node_ids
from app.graph.labels import NODE_LABELS
from app.ingestion.orchestrator import merge_models
from app.sources.owner_ids import broker_owned_id, queue_owned_id, topic_owned_id
from app.validation.canonical_validation import CanonicalValidationError, validate_canonical_model

SERVICE = Service(id="service:svc", name="Svc")
STABLE = "kafka:cluster-a"
BROKER_ID = broker_owned_id(stable_broker_id=STABLE)
BROKER = Broker(id=BROKER_ID, stable_broker_id=STABLE)
USES = Relation(type="USES_BROKER", source_id=SERVICE.id, target_id=BROKER_ID)


def _model(**overrides) -> ArchitectureModel:
    fields = {"services": [SERVICE], "brokers": [BROKER], "relations": [USES]}
    fields.update(overrides)
    return ArchitectureModel(**fields)


def _errors(model: ArchitectureModel) -> str:
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    return str(exc.value)


def test_broker_owned_id_matches_the_independently_derived_formula():
    # Written from the spec §4.1 formula (8-byte big-endian length prefix per UTF-8 part), not by
    # calling app.common.encoding.
    key = len(STABLE.encode()).to_bytes(8, "big") + STABLE.encode()
    assert BROKER_ID == "broker:owned:" + hashlib.sha256(key).hexdigest()


def test_broker_owned_id_is_keyword_only_and_takes_only_the_stable_broker_id():
    import inspect

    assert list(inspect.signature(broker_owned_id).parameters) == ["stable_broker_id"]
    with pytest.raises(TypeError):
        broker_owned_id(STABLE)  # type: ignore[misc]


def test_broker_id_never_aliases_a_destination_id_for_the_same_input():
    queue = queue_owned_id(
        stable_broker_id=STABLE, normalized_namespace_or_empty="", exact_channel_address="x"
    )
    topic = topic_owned_id(
        stable_broker_id=STABLE, normalized_namespace_or_empty="", exact_topic_address="x"
    )
    assert len({BROKER_ID, queue, topic}) == 3


def test_distinct_stable_broker_ids_give_distinct_broker_ids():
    assert broker_owned_id(stable_broker_id="kafka:cluster-b") != BROKER_ID


def test_valid_broker_model_passes():
    validate_canonical_model(_model())


def test_duplicate_broker_ids_are_rejected():
    assert "Broker id is not unique" in _errors(_model(brokers=[BROKER, BROKER]))


def test_uses_broker_with_unknown_endpoints_is_rejected():
    assert "unknown target" in _errors(_model(brokers=[]))
    assert "unknown source" in _errors(_model(services=[]))


def test_uses_broker_endpoints_must_be_service_to_broker():
    other = Service(id="service:other", name="Other")
    reversed_relation = Relation(type="USES_BROKER", source_id=BROKER_ID, target_id=SERVICE.id)
    assert "is not a service" in _errors(_model(relations=[reversed_relation]))
    service_to_service = Relation(type="USES_BROKER", source_id=SERVICE.id, target_id=other.id)
    assert "is not a broker" in _errors(
        _model(services=[SERVICE, other], relations=[service_to_service])
    )


def test_merge_is_first_wins_by_id_and_dedupes_the_relation():
    duplicate = Broker(id=BROKER_ID, stable_broker_id=STABLE)
    merged = merge_models([_model(), _model(brokers=[duplicate])])
    assert merged.brokers == [BROKER]
    assert merged.relations == [USES]


def test_merge_keeps_brokers_with_different_ids_separate():
    other = Broker(
        id=broker_owned_id(stable_broker_id="kafka:cluster-b"), stable_broker_id="kafka:cluster-b"
    )
    merged = merge_models([_model(), ArchitectureModel(brokers=[other])])
    assert {b.id for b in merged.brokers} == {BROKER_ID, other.id}


def test_broker_participates_in_ownership_and_node_label_mapping():
    assert BROKER_ID in model_node_ids(_model(), source_instance_id="urn:aip:source:test:x")
    assert NODE_LABELS["brokers"] == "Broker"


def test_broker_persistence_path_is_bound_to_canonicalization_v4():
    """v0.6.1 I1a: persisting USES_BROKER (bound by the untyped relation query) requires the Broker
    node projection and the v4 bump in the same change, or a snapshot would carry a relation whose
    target node is absent."""
    from app.architecture_intelligence import repository

    assert repository._CANONICALIZATION_VERSION == 4
    assert "MATCH (n:Broker)" in repository._BROKER_QUERY
