from app.architecture_intelligence.schema_export import SCHEMA_PATH, render_schema


def test_committed_schema_matches_generated_schema():
    committed = SCHEMA_PATH.read_text()
    generated = render_schema()
    assert committed == generated, (
        "schemas/architecture_intelligence/v0.4/architecture-answer.schema.json is out of date - "
        "regenerate it with `uv run python -m app.architecture_intelligence.schema_export` after a "
        "deliberate, recorded contract change."
    )
