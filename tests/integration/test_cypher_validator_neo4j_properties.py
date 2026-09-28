"""The row limit (spec §15.4) checked with Neo4j's own Cypher parser as the oracle: adversarial
queries (LIMIT text inside strings and comments, several LIMITs, trailing line comments) are run
through validate_cypher, and every query it accepts must run on real Neo4j and return at most
max_result_rows rows. The unit-level properties are in tests/unit/test_cypher_validator_properties.py.
"""

import neo4j
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.ai.cypher_validator import CypherValidationError, validate_cypher
from app.ai.question_service import ArchitectureQuestionService

DATABASE = "neo4j"
NODE_COUNT = 150
MAX_ROWS = 20


@pytest.fixture(scope="module", autouse=True)
def many_services(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        session.run(
            "UNWIND range(1, $count) AS i CREATE (:Service {id: 'service:s' + i, name: 'S' + i})",
            count=NODE_COUNT,
        )


tricky_text = st.lists(
    st.sampled_from(
        ["LIMIT 5", "LIMIT", "RETURN", "//", "/*", "*/", "x", " ", "SKIP 1", "'", "`", "\r"]
    ),
    max_size=5,
).map("".join)


@st.composite
def adversarial_queries(draw) -> str:
    parts = ["MATCH (a:Service)"]
    if draw(st.booleans()):
        parts.append(f"WITH a LIMIT {draw(st.integers(0, 10**6))}")
    note = draw(tricky_text).replace("'", "")
    alias = draw(tricky_text).replace("`", "``") or "note"
    parts.append(f"RETURN a.id AS id, '{note}' AS `{alias}`")
    if draw(st.booleans()):
        parts.append("ORDER BY id")
    if draw(st.booleans()):
        parts.append(f"SKIP {draw(st.integers(0, 10))}")
    if draw(st.booleans()):
        parts.append(f"LIMIT {draw(st.integers(0, 10**6))}")
    query = " ".join(parts)
    comment = draw(tricky_text)
    choice = draw(st.sampled_from(["none", "line", "block"]))
    if choice == "line":
        query += " // " + comment
    elif choice == "block":
        query += " /* " + comment.replace("*/", "") + " */"
    return query


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(adversarial_queries())
def test_every_accepted_query_returns_at_most_max_rows_on_neo4j(driver, query):
    try:
        cypher = validate_cypher(query, max_result_rows=MAX_ROWS)
    except CypherValidationError:
        return
    try:
        with driver.session(database=DATABASE, default_access_mode=neo4j.READ_ACCESS) as session:
            rows = session.run(cypher).data()  # pyright: ignore[reportArgumentType]
    except neo4j.exceptions.CypherSyntaxError:
        # Fail-safe: a query Neo4j can't parse returns nothing (e.g. text after a `*/` that a
        # nested `/*` in a comment left behind).
        return
    assert len(rows) <= MAX_ROWS, f"{len(rows)} rows from {cypher!r}"


@pytest.mark.parametrize("alias", ["`LIMIT 5 note`", "`LIMIT 999 note`", "`x`` LIMIT 5 y`"])
def test_limit_text_in_a_backtick_alias_still_gets_a_real_limit(driver, alias):
    """PR #304 review reproducer: before backtick names were lexed, this query came back unchanged
    and Neo4j returned all 150 rows."""
    cypher = validate_cypher(f"MATCH (a:Service) RETURN a.id AS {alias}", max_result_rows=MAX_ROWS)
    with driver.session(database=DATABASE, default_access_mode=neo4j.READ_ACCESS) as session:
        rows = session.run(cypher).data()  # pyright: ignore[reportArgumentType]
    assert len(rows) == MAX_ROWS


class _FakeProvider:
    def __init__(self, cypher: str):
        self.cypher = cypher

    def generate_cypher(self, *, question: str, schema_description: str) -> str:
        return self.cypher

    def compose_answer(self, *, question: str, cypher: str, rows: list[dict]) -> str:
        return f"{len(rows)} row(s)"


def test_question_service_caps_rows_even_if_the_validator_misses_a_limit(driver, monkeypatch):
    """Defense in depth: with validate_cypher replaced by a pass-through (a validator miss), the
    service still reads at most max_result_rows records."""
    monkeypatch.setattr("app.ai.question_service.validate_cypher", lambda cypher, **_kwargs: cypher)
    service = ArchitectureQuestionService(
        driver=driver,
        database=DATABASE,
        provider=_FakeProvider("MATCH (a:Service) RETURN a.id AS id"),
        max_result_rows=7,
    )
    result = service.ask("list every service")
    assert len(result.rows) == 7
