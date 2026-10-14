from app.architecture_intelligence.schema_export import (
    API_USAGE_ANSWER_SCHEMA_PATH,
    API_USAGE_REQUEST_SCHEMA_PATH,
    render_api_usage_answer_schema,
    render_api_usage_request_schema,
)

_REGENERATE = (
    "regenerate it with `uv run python -m app.architecture_intelligence.schema_export` after a "
    "deliberate change recorded in docs/specifications/0.7.0/i3-decision-record.md."
)


def test_committed_api_usage_request_schema_matches_generated_schema():
    assert API_USAGE_REQUEST_SCHEMA_PATH.read_text() == render_api_usage_request_schema(), (
        f"{API_USAGE_REQUEST_SCHEMA_PATH.name} is out of date - {_REGENERATE}"
    )


def test_committed_api_usage_answer_schema_matches_generated_schema():
    assert API_USAGE_ANSWER_SCHEMA_PATH.read_text() == render_api_usage_answer_schema(), (
        f"{API_USAGE_ANSWER_SCHEMA_PATH.name} is out of date - {_REGENERATE}"
    )


def test_api_usage_schemas_regenerate_deterministically():
    assert render_api_usage_request_schema() == render_api_usage_request_schema()
    assert render_api_usage_answer_schema() == render_api_usage_answer_schema()
