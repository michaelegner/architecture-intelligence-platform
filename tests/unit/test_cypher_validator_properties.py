"""Property-based tests for the LLM Cypher validator (spec §15.2-§15.4), the boundary between
model-generated text and the graph. Queries are assembled from clause pieces with adversarial
string literals and comments; tests/integration/test_cypher_validator_neo4j_properties.py runs the
accepted ones against real Neo4j to check the row limit with Neo4j's own parser.
"""

import re

from hypothesis import given
from hypothesis import strategies as st

from app.ai.cypher_validator import (
    FORBIDDEN_KEYWORDS,
    KNOWN_NODE_LABELS,
    CypherValidationError,
    validate_cypher,
)
from app.graph.importer import KNOWN_RELATION_TYPES

MAX_DEPTH = 5
MAX_ROWS = 100

labels = st.sampled_from(sorted(KNOWN_NODE_LABELS))
relation_types = st.sampled_from(sorted(KNOWN_RELATION_TYPES))
forbidden = st.sampled_from(sorted(FORBIDDEN_KEYWORDS))
limits = st.integers(min_value=0, max_value=10**7)


def _random_case(draw, word: str) -> str:
    return "".join(char.upper() if draw(st.booleans()) else char.lower() for char in word)


# Text that looks like code but sits inside a string literal, comment or backtick-quoted name,
# where it must be inert.
tricky_text = st.lists(
    st.sampled_from(
        [
            "LIMIT 5",
            "LIMIT",
            "//",
            "/*",
            "*/",
            "RETURN",
            "x",
            " ",
            "\n",
            "\\'",
            '\\"',
            ";",
            "'",
            "`",
            *sorted(FORBIDDEN_KEYWORDS),
        ]
    ),
    max_size=6,
).map("".join)


@st.composite
def string_literals(draw) -> str:
    body = draw(tricky_text).replace("\n", " ")
    quote = draw(st.sampled_from(["'", '"']))
    body = body.replace("\\" + quote, "").replace(quote, "")
    body = body.removesuffix("\\")
    return f"{quote}{body}{quote}"


@st.composite
def backtick_names(draw) -> str:
    """A backtick-quoted name; a backtick inside it is escaped by doubling (PR #304 review)."""
    body = draw(tricky_text).replace("\n", " ").replace("`", "``")
    return f"`{body or 'n'}`"


@st.composite
def comments(draw) -> str:
    body = draw(tricky_text)
    if draw(st.booleans()):
        return "// " + body.replace("\n", " ").replace("\r", " ")
    return "/* " + body.replace("*/", "") + " */"


@st.composite
def read_queries(draw, *, extra_clause=None) -> str:
    """A read-only query the validator should accept: MATCH, optional WITH ... LIMIT, an optional
    WITH that introduces a backtick-quoted name, a RETURN with an adversarial string literal and
    backtick alias, optional ORDER BY/SKIP/LIMIT and a trailing comment."""

    def kw(word: str) -> str:
        return _random_case(draw, word)

    a, b = draw(labels), draw(labels)
    rel = draw(relation_types)
    parts = [f"{kw('MATCH')} (a:{a})-[:{rel}]->(b:{b})"]
    if draw(st.booleans()):
        parts.append(f"{kw('WITH')} a, b {kw('LIMIT')} {draw(limits)}")
    if draw(st.booleans()):
        # A name that opens with an apostrophe must not hide the clauses after it.
        parts.append(f"{kw('WITH')} a, b, 0 AS {draw(backtick_names())}")
    if extra_clause is not None:
        parts.append(extra_clause)
    parts.append(
        f"{kw('RETURN')} a.id AS id, {draw(string_literals())} AS {draw(backtick_names())}"
    )
    if draw(st.booleans()):
        parts.append(f"{kw('ORDER')} {kw('BY')} id")
    if draw(st.booleans()):
        parts.append(f"{kw('SKIP')} {draw(st.integers(0, 50))}")
    if draw(st.booleans()):
        parts.append(f"{kw('LIMIT')} {draw(limits)}")
    query = " ".join(parts)
    if draw(st.booleans()):
        query += " " + draw(comments())
    return query


@given(read_queries())
def test_generated_read_queries_are_accepted(query):
    validate_cypher(query, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS)


@given(read_queries())
def test_validation_is_idempotent(query):
    once = validate_cypher(query, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS)
    assert validate_cypher(once, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS) == once


@given(read_queries())
def test_no_limit_literal_in_the_output_exceeds_the_cap(query):
    """Every LIMIT clause the generator wrote is clamped, and the last line of the output (where the
    final RETURN's LIMIT or an appended one sits) carries a LIMIT within the cap."""
    result = validate_cypher(query, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS)
    code = re.sub(
        r"'[^']*'|\"[^\"]*\"|`(?:``|[^`])*`|//[^\n]*|/\*.*?\*/", " ", result, flags=re.DOTALL
    )
    values = [int(v) for v in re.findall(r"\bLIMIT\s+(\d+)", code, flags=re.IGNORECASE)]
    assert values and all(value <= MAX_ROWS for value in values)


@st.composite
def queries_with_forbidden_clause(draw):
    keyword = _random_case(draw, draw(forbidden))
    return draw(read_queries(extra_clause=f"{keyword} a")), keyword


@given(queries_with_forbidden_clause())
def test_a_forbidden_keyword_in_code_is_always_rejected(case):
    query, _keyword = case
    try:
        validate_cypher(query, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS)
    except CypherValidationError as error:
        assert "forbidden" in str(error)
    else:
        raise AssertionError(f"accepted a query with a forbidden clause: {query!r}")


@given(forbidden, tricky_text, st.sampled_from(["\n", "\r", "\r\n"]))
def test_a_line_comment_never_hides_the_next_line(keyword, body, line_end):
    """Neo4j ends a `//` comment at `\n` or `\r`, so a clause after either is code."""
    comment = "// " + body.replace("\n", " ").replace("\r", " ")
    query = f"MATCH (s:Service) {comment}{line_end}{keyword} s\nRETURN s.id AS id"
    try:
        validate_cypher(query, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS)
    except CypherValidationError as error:
        assert "forbidden" in str(error)
    else:
        raise AssertionError(f"a comment hid {keyword!r}: {query!r}")


@given(forbidden, st.booleans())
def test_a_forbidden_keyword_in_a_string_or_comment_is_inert(keyword, in_comment):
    wrapper = f"/* {keyword} */" if in_comment else f"'{keyword}' AS x,"
    query = f"MATCH (s:Service) RETURN {wrapper} s.id AS id"
    validate_cypher(query, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS)


@given(
    st.one_of(
        st.tuples(st.none(), st.none()),  # [*]
        st.tuples(st.integers(0, 12), st.none()),  # [*n]
        st.tuples(st.integers(0, 12), st.just("..")),  # [*n..]
        st.tuples(st.integers(0, 12), st.integers(0, 12)),  # [*n..m]
        st.tuples(st.just(""), st.integers(0, 12)),  # [*..m]
    ),
    relation_types,
)
def test_traversal_depth_is_accepted_only_when_bounded_within_max_depth(bounds, rel):
    low, high = bounds
    if low is None:
        star, bound = "*", None
    elif high is None:
        star, bound = f"*{low}", low
    elif high == "..":
        star, bound = f"*{low}..", None
    else:
        star, bound = f"*{low}..{high}", high
    query = f"MATCH (a:Service)-[:{rel}{star}]->(b:Service) RETURN a.id AS id"
    try:
        validate_cypher(query, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS)
    except CypherValidationError:
        assert bound is None or bound > MAX_DEPTH
    else:
        assert bound is not None and bound <= MAX_DEPTH


@given(
    st.sampled_from(["{n} + {m}", "$p", "toInteger('{n}')", "{n}e2", "({n})", "{n} * {m}", "-{n}"]),
    limits,
    limits,
)
def test_a_non_literal_limit_is_always_rejected(template, n, m):
    query = "MATCH (s:Service) RETURN s.id LIMIT " + template.format(n=n, m=m)
    try:
        validate_cypher(query, max_depth=MAX_DEPTH, max_result_rows=MAX_ROWS)
    except CypherValidationError as error:
        assert "single integer literal" in str(error)
    else:
        raise AssertionError(f"accepted a non-literal LIMIT: {query!r}")
