from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
import yaml

from real_world_validation.__main__ import EXIT_INVALID, EXIT_OK, main
from real_world_validation.model import RelationFact


@contextmanager
def _fake_session(*_args, **_kwargs):
    yield MagicMock()


def test_capture_writes_facts_and_exits_ok(tmp_path, monkeypatch):
    facts = [
        RelationFact(type="CALLS", source="service:a", target="operation:service:b:GET:/x"),
        RelationFact(
            type="PROVIDES",
            source="service:b",
            target="operation:service:b:GET:/x",
            declared_evidence=True,
        ),
    ]
    monkeypatch.setattr("real_world_validation.__main__.build_driver", lambda *a, **k: MagicMock())
    monkeypatch.setattr("real_world_validation.__main__.open_session", _fake_session)
    monkeypatch.setattr(
        "real_world_validation.__main__.capture_actual_facts", lambda *a, **k: facts
    )
    out = tmp_path / "actual.yaml"

    code = main(
        [
            "capture",
            "--neo4j-uri",
            "bolt://localhost:7687",
            "--neo4j-user",
            "neo4j",
            "--neo4j-password",
            "secret",
            "--environment",
            "quarkus-i2",
            "--since",
            "2026-08-01T00:00:00+00:00",
            "--scope-entities",
            "service:a,service:b",
            "--out",
            str(out),
        ]
    )

    assert code == EXIT_OK
    document = yaml.safe_load(out.read_text())
    assert len(document["relations"]) == 2
    assert document["relations"][0]["type"] == "CALLS"
    assert document["relations"][1]["evidence"] == {"declared": True}


def test_capture_exits_invalid_on_connection_failure(tmp_path, monkeypatch):
    import neo4j.exceptions

    monkeypatch.setattr("real_world_validation.__main__.build_driver", lambda *a, **k: MagicMock())

    @contextmanager
    def _raising_session(*_args, **_kwargs):
        raise neo4j.exceptions.ServiceUnavailable("no connection")
        yield  # pragma: no cover - unreachable, satisfies generator-based contextmanager shape

    monkeypatch.setattr("real_world_validation.__main__.open_session", _raising_session)

    code = main(
        [
            "capture",
            "--neo4j-uri",
            "bolt://localhost:7687",
            "--neo4j-user",
            "neo4j",
            "--neo4j-password",
            "secret",
            "--environment",
            "quarkus-i2",
            "--since",
            "2026-08-01T00:00:00+00:00",
            "--scope-entities",
            "service:a",
            "--out",
            str(tmp_path / "actual.yaml"),
        ]
    )

    assert code == EXIT_INVALID


@pytest.mark.parametrize(
    ("scope_relation_types", "expected"),
    [(None, None), ("CALLS,PROVIDES", ("CALLS", "PROVIDES"))],
)
def test_capture_parses_optional_scope_relation_types(
    tmp_path, monkeypatch, scope_relation_types, expected
):
    captured_scope = {}

    def _record_scope(_session, *, scope, **_kwargs):
        captured_scope["scope"] = scope
        return []

    monkeypatch.setattr("real_world_validation.__main__.build_driver", lambda *a, **k: MagicMock())
    monkeypatch.setattr("real_world_validation.__main__.open_session", _fake_session)
    monkeypatch.setattr("real_world_validation.__main__.capture_actual_facts", _record_scope)

    argv = [
        "capture",
        "--neo4j-uri",
        "bolt://localhost:7687",
        "--neo4j-user",
        "neo4j",
        "--neo4j-password",
        "secret",
        "--environment",
        "quarkus-i2",
        "--since",
        "2026-08-01T00:00:00+00:00",
        "--scope-entities",
        "service:a",
        "--out",
        str(tmp_path / "actual.yaml"),
    ]
    if scope_relation_types is not None:
        argv += ["--scope-relation-types", scope_relation_types]

    assert main(argv) == EXIT_OK
    assert captured_scope["scope"].relation_types == expected
