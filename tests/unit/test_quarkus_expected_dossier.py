"""Protects the frozen Quarkus Super Heroes expected.yaml against schema drift (PR #39 review N1).

This is not a qualifying I2.3 comparison - it only proves the committed dossier still loads under
the current real_world_validation schema, independent of any AIP run.
"""

from pathlib import Path

from real_world_validation.loader import load_expected

EXPECTED_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "real-world-validation"
    / "quarkus-super-heroes"
    / "expected.yaml"
)


def test_quarkus_expected_dossier_loads():
    doc = load_expected(EXPECTED_PATH)

    assert doc.system == "quarkus-super-heroes"
    assert doc.upstream_revision == "8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce"
    assert doc.scope.entities == (
        "service:rest-fights",
        "service:rest-heroes",
        "service:rest-villains",
        "service:rest-narration",
        "service:event-statistics",
    )
    assert doc.scope.relation_types == ("PROVIDES", "CALLS", "SENDS", "RECEIVES_FROM")

    provides = [r for r in doc.expected_relations if r.fact.type == "PROVIDES"]
    calls = [r for r in doc.expected_relations if r.fact.type == "CALLS"]
    assert len(provides) == 35
    assert len(calls) == 3

    # I2.2 froze runtime/declarations/rest-fights/architecture.yaml, a pre-run Architecture
    # Manifest transcribing this exact CALLS ground truth - declared evidence is now reproducible.
    # status/observed remain unset until I2.3 runs the frozen traffic (runbook.md phase 8-9).
    for relation in calls:
        assert relation.fact.status is None
        assert relation.fact.declared_evidence is True
        assert relation.fact.observed_evidence is None

    assert {u.id for u in doc.unsupported} == {"qsh-grpc-locations", "qsh-kafka-fights-topic"}
