"""v0.6.1 I2a: the Broker-aware schemas are frozen like the locality pair, and the released v0.5
schemas are pinned independently of the generator. `schema_export.main()` rewrites all of them, so a
regenerate-and-compare test alone cannot notice a v0.5 file that drifted and was regenerated: the
v0.5 files are therefore also pinned by sha256 to the digests recorded in the v0.6.0 I4 release
records."""

import hashlib
import json

from app.architecture_intelligence.schema_export import (
    BROKER_DEPENDENCIES_SCHEMA_PATH,
    BROKER_EVIDENCE_SCHEMA_PATH,
    DEPENDENCIES_SCHEMA_PATH,
    DRIFT_SCHEMA_PATH,
    EVIDENCE_SCHEMA_PATH,
    render_broker_dependencies_schema,
    render_broker_evidence_schema,
)
from tests.unit.test_broker_contracts import ROOT

_REGENERATE = (
    "regenerate it with `uv run python -m app.architecture_intelligence.schema_export` after a "
    "deliberate change recorded in docs/specifications/0.6.1/specification.md."
)

# The digests of the released v0.5 files, as recorded in docs/release-validation/v0.6.0-i4/*.json
# (the drift file's digest is pinned the same way here). They never change.
V05_SHA256 = {
    DEPENDENCIES_SCHEMA_PATH: "531ac7bc9940936171e75817542b7e1f681529347e3429a775a2b4e56533c053",
    EVIDENCE_SCHEMA_PATH: "36d18ade82c4d7994b40497d19e6934729e9dda0aa7173a778e11c37135ddfe4",
    DRIFT_SCHEMA_PATH: "b3762ad20a71e7d5dc3865c2b9602364a8a303f7fc8254a9ec9254ecf02cf879",
}


def test_committed_broker_dependencies_schema_matches_generated_schema():
    assert BROKER_DEPENDENCIES_SCHEMA_PATH.read_text() == render_broker_dependencies_schema(), (
        f"{BROKER_DEPENDENCIES_SCHEMA_PATH.name} is out of date - {_REGENERATE}"
    )


def test_committed_broker_evidence_schema_matches_generated_schema():
    assert BROKER_EVIDENCE_SCHEMA_PATH.read_text() == render_broker_evidence_schema(), (
        f"{BROKER_EVIDENCE_SCHEMA_PATH.name} is out of date - {_REGENERATE}"
    )


def test_broker_schemas_regenerate_deterministically():
    assert render_broker_dependencies_schema() == render_broker_dependencies_schema()
    assert render_broker_evidence_schema() == render_broker_evidence_schema()


def test_the_released_v05_schema_files_are_byte_identical_to_their_recorded_digests():
    for path, digest in V05_SHA256.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, (
            f"{path.name}: the released v0.5 schema changed. v0.5 is immutable; the Broker-aware "
            "contract lives in schemas/architecture_intelligence/v0.6/."
        )


def test_the_recorded_v05_digests_agree_with_the_release_records():
    record = json.loads((ROOT / "docs/release-validation/v0.6.0-i4/locality.json").read_text())
    pins = {
        key: value
        for key, value in record.items()
        if isinstance(value, dict)
        for key, value in value.items()
        if key.startswith("schemas/architecture_intelligence/v0.5/")
    }
    assert pins, "the v0.6.0 I4 record no longer lists the v0.5 schema digests"
    by_name = {path.name: digest for path, digest in V05_SHA256.items()}
    for key, digest in pins.items():
        assert by_name[key.rsplit("/", 1)[1]] == digest
