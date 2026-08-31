from real_world_validation.model import (
    CLASSIFICATION_RANK,
    CLASSIFICATIONS,
    DEFAULT_SEVERITY,
    SEVERITIES,
    SEVERITY_RANK,
    RelationFact,
    ScopeDeclaration,
    is_canonical_id,
)


def test_is_canonical_id_accepts_known_prefixes():
    assert is_canonical_id("service:order-service")
    assert is_canonical_id("operation:service:product-service:GET:/products/{id}")
    assert is_canonical_id("queue:payment-q")
    assert is_canonical_id("message:PaymentRequested:v2")
    assert is_canonical_id("schema:PaymentRequested:v2")


def test_is_canonical_id_rejects_unknown_prefix_and_non_string():
    assert not is_canonical_id("order-service")
    assert not is_canonical_id("evidence:openapi:order-service")
    assert not is_canonical_id(123)
    assert not is_canonical_id(None)


def test_default_severity_covers_every_classification():
    assert set(DEFAULT_SEVERITY) == CLASSIFICATIONS
    assert set(DEFAULT_SEVERITY.values()) <= SEVERITIES


def test_rank_tables_cover_every_value():
    assert set(CLASSIFICATION_RANK) == CLASSIFICATIONS
    assert set(SEVERITY_RANK) == SEVERITIES


def test_scope_contains_filters_by_relation_type_and_entity():
    scope = ScopeDeclaration(entities=("service:order-service",), relation_types=("CALLS",))
    matching = RelationFact(
        type="CALLS", source="service:order-service", target="operation:service:x:GET:/y"
    )
    wrong_type = RelationFact(
        type="SENDS", source="service:order-service", target="queue:payment-q"
    )
    wrong_entity = RelationFact(
        type="CALLS", source="service:unrelated", target="operation:service:x:GET:/y"
    )

    assert scope.contains(matching)
    assert not scope.contains(wrong_type)
    assert not scope.contains(wrong_entity)


def test_scope_contains_allows_any_relation_type_when_unrestricted():
    scope = ScopeDeclaration(entities=("service:order-service",), relation_types=None)
    fact = RelationFact(type="SENDS", source="service:order-service", target="queue:payment-q")

    assert scope.contains(fact)
