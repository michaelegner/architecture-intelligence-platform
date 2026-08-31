"""Guards the frozen Quarkus Architecture Manifest against drifting from I2.1's independently
established CALLS ground truth (I2.2).

runtime/declarations/rest-fights/architecture.yaml is a pre-run input (I2 spec §28) - it must keep
transcribing exactly the three CALLS relations expected.yaml already asserts, never more or fewer.
"""

from pathlib import Path

import yaml

from real_world_validation.loader import load_expected

DOSSIER_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "real-world-validation"
    / "quarkus-super-heroes"
)
MANIFEST_PATH = DOSSIER_DIR / "runtime" / "declarations" / "rest-fights" / "architecture.yaml"


def test_manifest_declares_service_rest_fights():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())

    assert manifest["service"] == "rest-fights"


def test_manifest_calls_match_expected_call_count_and_target_services():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    doc = load_expected(DOSSIER_DIR / "expected.yaml")
    expected_calls = [r for r in doc.expected_relations if r.fact.type == "CALLS"]

    assert len(manifest["calls"]) == len(expected_calls)

    manifest_targets = {entry["service"] for entry in manifest["calls"]}
    expected_targets = {r.fact.target.split(":")[2] for r in expected_calls}
    assert (
        manifest_targets == expected_targets == {"rest-heroes", "rest-villains", "rest-narration"}
    )


def test_manifest_operation_ids_match_the_pinned_openapi_operations():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    manifest_by_service = {entry["service"]: entry["operationId"] for entry in manifest["calls"]}

    # Independently established in ground-truth.md / evidence/rest-and-grpc.md from rest-fights'
    # own client source code - not re-derived from AIP output.
    assert manifest_by_service == {
        "rest-heroes": "getRandomHero",
        "rest-villains": "getRandomVillain",
        "rest-narration": "narrate",
    }


def test_manifest_operation_ids_exist_in_the_pinned_openapi_documents():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())

    for entry in manifest["calls"]:
        openapi_path = DOSSIER_DIR / "runtime" / "declarations" / entry["service"] / "openapi.yml"
        openapi = yaml.safe_load(openapi_path.read_text())
        operation_ids = {
            op.get("operationId")
            for path_item in openapi.get("paths", {}).values()
            if isinstance(path_item, dict)
            for op in path_item.values()
            if isinstance(op, dict)
        }
        assert entry["operationId"] in operation_ids
