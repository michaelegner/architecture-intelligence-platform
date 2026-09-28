import json

import pytest

from app.api.openapi_export import (
    OPENAPI_SNAPSHOT_PATH,
    SNAPSHOT_VERSION,
    generate_openapi,
    render_openapi,
)


def test_committed_openapi_snapshot_matches_generated_openapi():
    committed = OPENAPI_SNAPSHOT_PATH.read_text()
    generated = render_openapi()
    assert committed == generated, (
        "tests/snapshots/openapi.json is out of date - the REST API changed. If the change is "
        "deliberate, regenerate it with `uv run python -m app.api.openapi_export` and commit it "
        "with the change so the surface diff is reviewed."
    )


def test_openapi_snapshot_regenerates_deterministically():
    assert render_openapi() == render_openapi()


@pytest.mark.parametrize(
    "document",
    [generate_openapi(), json.loads(OPENAPI_SNAPSHOT_PATH.read_text())],
    ids=["generated", "committed"],
)
def test_openapi_document_has_the_fields_openapi_requires(document):
    """OpenAPI 3.1 requires `openapi`, an Info Object with `title` and `version` strings, and (for
    this API) `paths` - the snapshot normalizes `info.version`, it must never drop it."""
    assert isinstance(document["openapi"], str) and document["openapi"].startswith("3.")
    assert isinstance(document["info"]["title"], str) and document["info"]["title"]
    assert document["info"]["version"] == SNAPSHOT_VERSION
    assert isinstance(document["paths"], dict) and document["paths"]
