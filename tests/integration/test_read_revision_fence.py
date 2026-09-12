"""v0.4.2 I3 - Neo4j-integration coverage for `read_revision_fence.py`'s Neo4j-backed half (spec
`docs/specifications/0.4.2/i3-client-qualification-and-release-preparation.md` §6.3): the fence value
after a real import, and the "create no singleton" requirement against a virgin database."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.graph.revision_fence import read_revision

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "examples"
    / "runtime-demo"
    / "read_revision_fence.py"
)
_spec = importlib.util.spec_from_file_location("read_revision_fence", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
read_revision_fence_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(read_revision_fence_module)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _whole_database_node_count(driver) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run("MATCH (n) RETURN count(n) AS count").single()["count"]


def test_matches_read_revision_after_a_real_import(driver):
    from app.graph.importer import import_all_sources

    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    with driver.session(database=DATABASE) as session:
        expected = read_revision(session)

    result = read_revision_fence_module.read_revision_fence(driver, database=DATABASE)

    assert result == {"revision": expected}


def test_reports_null_and_creates_no_singleton_on_a_virgin_database(driver):
    assert _whole_database_node_count(driver) == 0

    result = read_revision_fence_module.read_revision_fence(driver, database=DATABASE)

    assert result == {"revision": None}
    assert _whole_database_node_count(driver) == 0  # "create no singleton" (spec §6.3)
