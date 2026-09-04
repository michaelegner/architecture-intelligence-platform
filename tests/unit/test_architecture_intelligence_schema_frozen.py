from app.architecture_intelligence.schema_export import (
    DEPENDENCIES_SCHEMA_PATH,
    EVIDENCE_SCHEMA_PATH,
    render_dependencies_schema,
    render_evidence_schema,
)


def test_committed_dependencies_schema_matches_generated_schema():
    committed = DEPENDENCIES_SCHEMA_PATH.read_text()
    generated = render_dependencies_schema()
    assert committed == generated, (
        "schemas/architecture_intelligence/v0.4/architecture-answer.schema.json is out of date - "
        "regenerate it with `uv run python -m app.architecture_intelligence.schema_export` after a "
        "deliberate, recorded contract change."
    )


def test_committed_evidence_schema_matches_generated_schema():
    committed = EVIDENCE_SCHEMA_PATH.read_text()
    generated = render_evidence_schema()
    assert committed == generated, (
        "schemas/architecture_intelligence/v0.4/evidence-answer.schema.json is out of date - "
        "regenerate it with `uv run python -m app.architecture_intelligence.schema_export` after a "
        "deliberate, recorded contract change."
    )
