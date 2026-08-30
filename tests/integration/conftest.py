import pytest
from testcontainers.community.neo4j import Neo4jContainer


@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:5") as container:
        yield container


@pytest.fixture(scope="session")
def driver(neo4j_container):
    drv = neo4j_container.get_driver()
    yield drv
    drv.close()
