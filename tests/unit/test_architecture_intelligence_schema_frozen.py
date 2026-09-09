from app.architecture_intelligence.schema_export import (
    DEPENDENCIES_SCHEMA_PATH,
    DRIFT_SCHEMA_PATH,
    EVIDENCE_SCHEMA_PATH,
    render_dependencies_schema,
    render_drift_schema,
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


def test_committed_drift_schema_matches_generated_schema():
    committed = DRIFT_SCHEMA_PATH.read_text()
    generated = render_drift_schema()
    assert committed == generated, (
        "schemas/architecture_intelligence/v0.4/drift-answer.schema.json is out of date - "
        "regenerate it with `uv run python -m app.architecture_intelligence.schema_export` after a "
        "deliberate, recorded contract change."
    )


def test_all_three_schemas_regenerate_deterministically():
    """I3 spec §48: regeneration is a pure function of the models, so a second render of each of the
    three answer schemas is byte-identical to the first - a schema file can never depend on
    iteration/`set` ordering or on which other schema was rendered before it."""
    assert render_dependencies_schema() == render_dependencies_schema()
    assert render_evidence_schema() == render_evidence_schema()
    assert render_drift_schema() == render_drift_schema()
