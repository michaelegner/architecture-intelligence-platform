import copy
from pathlib import Path

import pytest
import yaml

from real_world_validation.loader import load_actual, load_expected
from real_world_validation.model import ExpectedValidationError

_VALID = {
    "system": "quarkus-super-heroes",
    "upstream_revision": "abc123",
    "scope": {
        "entities": ["service:rest-fights"],
        "relation_types": ["CALLS"],
    },
    "expected": {
        "relations": [
            {
                "id": "qsh-rest-fights-calls-heroes",
                "type": "CALLS",
                "source": "service:rest-fights",
                "target": "operation:service:rest-heroes:GET:/api/heroes",
                "status": "CONFIRMED",
                "evidence": {"declared": True, "observed": True},
            }
        ]
    },
    "unsupported": [
        {"id": "qsh-grpc", "mechanism": "grpc", "description": "Outside current scope."}
    ],
    "unresolved_identity": [{"id": "qsh-worker-01", "description": "Cannot resolve safely."}],
    "insufficient_evidence": [{"id": "qsh-unclear", "description": "Evidence too weak."}],
}

_DELETE = object()


def _key(raw: str):
    return int(raw) if raw.isdigit() else raw


def _mutated(**overrides) -> dict:
    data = copy.deepcopy(_VALID)
    for path, value in overrides.items():
        keys = [_key(k) for k in path.split(".")]
        target = data
        for key in keys[:-1]:
            target = target[key]
        if value is _DELETE:
            del target[keys[-1]]
        else:
            target[keys[-1]] = value
    return data


def _write(tmp_path: Path, data: dict, *, name: str = "expected.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data))
    return path


# --- valid document --------------------------------------------------------------------------


def test_load_expected_parses_a_valid_document(tmp_path):
    doc = load_expected(_write(tmp_path, _VALID))

    assert doc.system == "quarkus-super-heroes"
    assert doc.upstream_revision == "abc123"
    assert doc.scope.entities == ("service:rest-fights",)
    assert doc.scope.relation_types == ("CALLS",)
    assert len(doc.expected_relations) == 1
    relation = doc.expected_relations[0]
    assert relation.id == "qsh-rest-fights-calls-heroes"
    assert relation.fact.type == "CALLS"
    assert relation.fact.status == "CONFIRMED"
    assert relation.fact.declared_evidence is True
    assert relation.fact.observed_evidence is True
    assert [u.id for u in doc.unsupported] == ["qsh-grpc"]
    assert [u.id for u in doc.unresolved_identity] == ["qsh-worker-01"]
    assert [u.id for u in doc.insufficient_evidence] == ["qsh-unclear"]


def test_load_expected_allows_omitted_optional_sections(tmp_path):
    data = _mutated(unsupported=_DELETE, unresolved_identity=_DELETE)
    del data["insufficient_evidence"]

    doc = load_expected(_write(tmp_path, data))

    assert doc.unsupported == ()
    assert doc.unresolved_identity == ()
    assert doc.insufficient_evidence == ()


# --- strictness -------------------------------------------------------------------------------


def test_load_expected_rejects_unknown_top_level_field(tmp_path):
    data = _mutated()
    data["typo_field"] = "x"

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


def test_load_expected_rejects_unknown_relation_field(tmp_path):
    data = _mutated()
    data["expected"]["relations"][0]["typo"] = "x"

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


def test_load_expected_rejects_duplicate_finding_id_across_sections(tmp_path):
    data = _mutated()
    data["unsupported"][0]["id"] = "qsh-rest-fights-calls-heroes"  # collides with expected relation

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


def test_load_expected_rejects_duplicate_expected_relation_identity(tmp_path):
    # PR #38 review F1: distinct finding ids don't excuse two expected.relations entries that
    # assert the same (type, source, target) - one actual fact could otherwise satisfy both.
    data = _mutated()
    duplicate = copy.deepcopy(data["expected"]["relations"][0])
    duplicate["id"] = "qsh-rest-fights-calls-heroes-again"
    data["expected"]["relations"].append(duplicate)

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


def test_load_expected_rejects_scope_excluded_relation(tmp_path):
    # PR #38 review F2: the declared scope is normative - an expected relation whose source and
    # target the dossier itself placed outside scope.entities can never be a qualifying
    # expectation, even though its type is in scope.relation_types.
    data = _mutated(
        **{
            "expected.relations.0.source": "service:rest-villains",
            "expected.relations.0.target": "operation:service:rest-heroes:GET:/api/villains",
        }
    )

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


@pytest.mark.parametrize(
    ("relation_type", "source", "target"),
    [
        ("PROVIDES", "service:x", "operation:service:x:GET:/y"),
        ("CALLS", "service:x", "operation:service:x:GET:/y"),
        ("REQUEST_SCHEMA", "operation:service:x:GET:/y", "schema:Foo:v1"),
        ("RESPONSE_SCHEMA", "operation:service:x:GET:/y", "schema:Foo:v1"),
        ("SENDS", "service:x", "queue:y"),
        ("RECEIVES_FROM", "service:x", "queue:y"),
        ("CARRIES", "queue:y", "message:Foo:v1"),
        ("CONFORMS_TO", "message:Foo:v1", "schema:Foo:v1"),
        ("DEAD_LETTERS_TO", "queue:y", "queue:z"),
    ],
)
def test_load_expected_accepts_every_canonical_relation_type(
    tmp_path, relation_type, source, target
):
    # PR #38 review F3: KNOWN_RELATION_TYPES must cover AIP's complete current canonical relation
    # vocabulary (CLAUDE.md's graph model table), not only the four dependency-analysis edges.
    data = _mutated(
        **{
            "scope.entities": [source, target],
            "scope.relation_types": _DELETE,
            "expected.relations.0.type": relation_type,
            "expected.relations.0.source": source,
            "expected.relations.0.target": target,
            "expected.relations.0.status": _DELETE,
            "expected.relations.0.evidence": _DELETE,
        }
    )

    doc = load_expected(_write(tmp_path, data))

    assert doc.expected_relations[0].fact.type == relation_type


def test_load_expected_rejects_unknown_relation_type(tmp_path):
    data = _mutated(**{"expected.relations.0.type": "SUBSCRIBES"})

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


def test_load_expected_rejects_malformed_canonical_id(tmp_path):
    data = _mutated(**{"expected.relations.0.source": "rest-fights"})

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


def test_load_expected_rejects_missing_required_field(tmp_path):
    data = _mutated(system=_DELETE)

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


def test_load_expected_rejects_empty_scope_entities(tmp_path):
    data = _mutated(**{"scope.entities": []})

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


def test_load_expected_rejects_non_boolean_evidence(tmp_path):
    data = _mutated(**{"expected.relations.0.evidence": {"declared": "yes"}})

    with pytest.raises(ExpectedValidationError):
        load_expected(_write(tmp_path, data))


# --- actual-facts capture ----------------------------------------------------------------------


def test_load_actual_parses_a_valid_capture(tmp_path):
    data = {
        "relations": [
            {
                "type": "CALLS",
                "source": "service:rest-fights",
                "target": "operation:service:rest-heroes:GET:/api/heroes",
                "status": "CONFIRMED",
                "evidence": {"declared": True, "observed": True},
            }
        ]
    }
    facts = load_actual(_write(tmp_path, data, name="actual.yaml"))

    assert len(facts) == 1
    assert facts[0].type == "CALLS"
    assert facts[0].status == "CONFIRMED"


def test_load_actual_rejects_unknown_field(tmp_path):
    data = {
        "relations": [
            {
                "type": "CALLS",
                "source": "service:rest-fights",
                "target": "operation:service:rest-heroes:GET:/api/heroes",
                "id": "should-not-be-here",
            }
        ]
    }

    with pytest.raises(ExpectedValidationError):
        load_actual(_write(tmp_path, data, name="actual.yaml"))


def test_load_actual_defaults_to_empty_list_when_relations_omitted(tmp_path):
    facts = load_actual(_write(tmp_path, {}, name="actual.yaml"))

    assert facts == []
