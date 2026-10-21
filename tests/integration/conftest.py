from pathlib import Path

import pytest
from testcontainers.community.neo4j import Neo4jContainer

# The Neo4j process is shared across the integration-test session. Each integration module/test
# remains responsible for resetting graph state before use - a fresh container does NOT imply an
# empty graph once other modules/tests have already run against it this session.


@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer(
        "neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93"
    ) as container:
        yield container


@pytest.fixture(scope="session")
def driver(neo4j_container):
    drv = neo4j_container.get_driver()
    yield drv
    drv.close()


# The qualification tier: frozen-reference, oracle and real-third-party-container suites. They are
# valuable release evidence but dominate the integration runtime (~55% of it), so CI runs them on
# main, tags, nightly and on pull requests that touch their inputs (`.github/workflows/ci.yml`),
# and everyone else deselects them with `-m "not qualification"`. A module belongs here only if it
# is both slow and a frozen-reference/oracle check; fast qualification-named modules stay in the
# per-PR tier. Selection is by module so a module's tier is decided in one place.
QUALIFICATION_MODULES = frozenset(
    {
        "test_locality_oracle.py",
        "test_locality_surface_parity.py",
        "test_locality_query.py",
        "test_locality_rehearsal_replay.py",
        "test_i4_pubsub_qualification.py",
        "test_broker_qualification.py",
        "test_evaluation_architecture_answers.py",
        "test_v070_i1_apisix_capture_real.py",
        "test_v070_i2_apisix_metrics_capture_real.py",
        "test_v071_i4_kafka_replay.py",
        "test_v072_i2_sokol111_replay.py",
    }
)


def pytest_collection_modifyitems(items):
    for item in items:
        if Path(str(item.fspath)).name in QUALIFICATION_MODULES:
            item.add_marker(pytest.mark.qualification)
