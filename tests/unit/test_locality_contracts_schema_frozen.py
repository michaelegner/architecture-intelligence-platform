from app.architecture_intelligence.schema_export import (
    LOCALITY_ANSWER_SCHEMA_PATH,
    LOCALITY_REQUEST_SCHEMA_PATH,
    render_locality_answer_schema,
    render_locality_request_schema,
)

_REGENERATE = (
    "regenerate it with `uv run python -m app.architecture_intelligence.schema_export` after a "
    "deliberate change recorded in docs/specifications/0.6.0/i3-decision-record.md."
)


def test_committed_locality_request_schema_matches_generated_schema():
    assert LOCALITY_REQUEST_SCHEMA_PATH.read_text() == render_locality_request_schema(), (
        f"{LOCALITY_REQUEST_SCHEMA_PATH.name} is out of date - {_REGENERATE}"
    )


def test_committed_locality_answer_schema_matches_generated_schema():
    assert LOCALITY_ANSWER_SCHEMA_PATH.read_text() == render_locality_answer_schema(), (
        f"{LOCALITY_ANSWER_SCHEMA_PATH.name} is out of date - {_REGENERATE}"
    )


def test_locality_schemas_regenerate_deterministically():
    assert render_locality_request_schema() == render_locality_request_schema()
    assert render_locality_answer_schema() == render_locality_answer_schema()
