import pytest

from app.architecture_intelligence import repository as repo
from app.architecture_intelligence.contracts import SnapshotRef


class FakeSession:
    """Stands in for `neo4j.Session.run(query)` - looks up canned rows by the exact query text, so
    tests stay robust to internal query-text edits as long as the module-level constant names
    don't change."""

    def __init__(self, rows_by_query: dict[str, list[dict]]):
        self._rows_by_query = rows_by_query

    def run(self, query: str, **_params):
        return list(self._rows_by_query.get(query, []))


def test_project_row_drops_null_and_absent_values():
    assert repo._project_row({"id": "a", "version": None, "name": "A"}) == {"id": "a", "name": "A"}


def test_project_row_sorts_and_deduplicates_list_fields():
    row = repo._project_row({"id": "a", "evidence_ids": ["e2", "e1", "e1"]})
    assert row["evidence_ids"] == ["e1", "e2"]


def test_project_nodes_sorts_by_id():
    session = FakeSession({"Q": [{"id": "b"}, {"id": "a"}]})
    assert [row["id"] for row in repo._project_nodes(session, "Q")] == ["a", "b"]


def test_project_relations_sorts_by_type_source_target():
    session = FakeSession(
        {
            repo._RELATION_QUERY: [
                {"type": "SENDS", "source_id": "a", "target_id": "b", "evidence_ids": []},
                {"type": "CALLS", "source_id": "z", "target_id": "y", "evidence_ids": []},
                {"type": "CALLS", "source_id": "a", "target_id": "b", "evidence_ids": []},
            ]
        }
    )
    ordered = repo._project_relations(session)
    assert [(r["type"], r["source_id"], r["target_id"]) for r in ordered] == [
        ("CALLS", "a", "b"),
        ("CALLS", "z", "y"),
        ("SENDS", "a", "b"),
    ]


def test_canonical_snapshot_state_assembles_expected_shape():
    session = FakeSession(
        {
            repo._SERVICE_QUERY: [
                {"id": "service:b", "name": "B", "version": None},
                {"id": "service:a", "name": "A", "version": "1"},
            ],
            repo._RELATION_QUERY: [
                {
                    "type": "CALLS",
                    "source_id": "x",
                    "target_id": "y",
                    "evidence_ids": ["e2", "e1", "e1"],
                }
            ],
        }
    )
    state = repo.canonical_snapshot_state(session, coverage_qualification_enabled=True)
    assert state["version"] == 1
    assert [s["id"] for s in state["services"]] == ["service:a", "service:b"]
    assert "version" not in state["services"][1]  # service:b's None version was dropped
    assert state["relations"][0]["evidence_ids"] == ["e1", "e2"]
    assert state["semantic_config"] == {"coverage_qualification_enabled": True}
    for key in ("operations", "queues", "messages", "schemas", "evidence"):
        assert state[key] == []


def test_snapshot_fingerprint_produces_a_valid_matching_snapshot_ref():
    snapshot_id, model_revision = repo.snapshot_fingerprint({"a": 1})
    ref = SnapshotRef(snapshot_id=snapshot_id, model_revision=model_revision)  # must not raise
    assert ref.snapshot_id == snapshot_id


def test_snapshot_fingerprint_is_order_independent():
    state_a = {"b": 1, "a": {"z": 1, "y": 2}}
    state_b = {"a": {"y": 2, "z": 1}, "b": 1}
    assert repo.snapshot_fingerprint(state_a) == repo.snapshot_fingerprint(state_b)


def test_snapshot_fingerprint_changes_with_state():
    assert repo.snapshot_fingerprint({"a": 1}) != repo.snapshot_fingerprint({"a": 2})


def _sequence(values):
    iterator = iter(values)
    return lambda: next(iterator)


def test_read_stable_snapshot_happy_path():
    result = repo.read_stable_snapshot(
        read_revision_fn=_sequence([1, 1]),
        read_state=lambda: {"a": 1},
        read_extra=lambda: "x",
    )
    assert result.extra == "x"
    assert result.snapshot_id.startswith("aip:snapshot:v1:")
    assert result.model_revision.startswith("sha256:")


def test_read_stable_snapshot_discards_a_mismatched_attempt_and_retries():
    calls = []

    def read_state():
        calls.append("state")
        return {"a": len(calls)}

    result = repo.read_stable_snapshot(
        read_revision_fn=_sequence([1, 2, 5, 5]),  # attempt 1 mismatches, attempt 2 matches
        read_state=read_state,
        read_extra=lambda: "x",
    )
    assert len(calls) == 2  # both attempts actually read state...
    assert result.extra == "x"
    # ...but the fingerprint reflects only the accepted (second) attempt's state, not a mix.
    expected_id, expected_revision = repo.snapshot_fingerprint({"a": 2})
    assert (result.snapshot_id, result.model_revision) == (expected_id, expected_revision)


def test_read_stable_snapshot_raises_after_repeated_instability():
    with pytest.raises(repo.SnapshotUnstable):
        repo.read_stable_snapshot(
            read_revision_fn=_sequence([1, 2, 3, 4, 5, 6]),  # 3 attempts, all mismatched
            read_state=lambda: {"a": 1},
            read_extra=lambda: "x",
            max_attempts=3,
        )
