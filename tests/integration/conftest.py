import pytest
from testcontainers.community.neo4j import Neo4jContainer

# The Neo4j process is shared across the integration-test session. Each integration module/test
# remains responsible for resetting graph state before use - a fresh container does NOT imply an
# empty graph once other modules/tests have already run against it this session.


@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:5") as container:
        yield container


@pytest.fixture(scope="session")
def driver(neo4j_container):
    drv = neo4j_container.get_driver()
    yield drv
    drv.close()
