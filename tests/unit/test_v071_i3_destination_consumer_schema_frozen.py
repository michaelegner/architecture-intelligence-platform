from app.architecture_intelligence.schema_export import (
    DESTINATION_ANSWER_SCHEMA_PATH,
    DESTINATION_REQUEST_SCHEMA_PATH,
    render_destination_answer_schema,
    render_destination_request_schema,
)

_REGENERATE = (
    "regenerate it with `uv run python -m app.architecture_intelligence.schema_export` after a "
    "deliberate change to docs/specifications/0.7.1/i3-destination-consumer-public-answer.md."
)


def test_committed_destination_request_schema_matches_generated_schema():
    assert DESTINATION_REQUEST_SCHEMA_PATH.read_text() == render_destination_request_schema(), (
        f"{DESTINATION_REQUEST_SCHEMA_PATH.name} is out of date - {_REGENERATE}"
    )


def test_committed_destination_answer_schema_matches_generated_schema():
    assert DESTINATION_ANSWER_SCHEMA_PATH.read_text() == render_destination_answer_schema(), (
        f"{DESTINATION_ANSWER_SCHEMA_PATH.name} is out of date - {_REGENERATE}"
    )
