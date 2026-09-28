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
