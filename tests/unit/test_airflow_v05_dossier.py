"""Guards the frozen v0.5.0 I5 Airflow dossier inputs (I5 §§5-6, §8.2) against drift.

These tests check the dossier's own internal consistency and its fixed digests. They never run AIP
against the target, so they produce no qualifying output (I5 §6).
"""

import hashlib
import re
from pathlib import Path

import yaml

from app.settings import load_config
from app.sources.identity import source_instance_id
from app.sources.manifest_bindings import parse_architecture_identity_bindings
from app.sources.model import SourceKind
from real_world_validation.loader import load_expected

DOSSIER = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "real-world-validation"
    / "v0.5.0"
    / "apache-airflow"
)
RUNTIME = DOSSIER / "runtime"
OPENAPI = RUNTIME / "declarations" / "airflow-apiserver" / "openapi.yml"
# Frozen in profile.md / upstream.md; independently re-checked against the pin by runbook.md step 2.
OPENAPI_SHA256 = "2c57114da43a131f68772f1660ed52ca7116089a20893ac5e5f6225ffde3abd9"
SELECTED = {
    ("GET", "/api/v2/monitor/health"),
    ("GET", "/api/v2/dags"),
    ("GET", "/api/v2/dags/{dag_id}"),
    ("POST", "/api/v2/dags/{dag_id}/dagRuns"),
    ("GET", "/api/v2/dags/{dag_id}/dagRuns"),
    ("GET", "/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}"),
    ("GET", "/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances"),
    ("GET", "/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}"),
    ("GET", "/api/v2/variables"),
}


def test_openapi_matches_its_frozen_digest():
    assert hashlib.sha256(OPENAPI.read_bytes()).hexdigest() == OPENAPI_SHA256


def test_identity_binding_targets_the_configured_openapi_source():
    config = load_config(RUNTIME / "config.airflow-i5.yaml")
    (directory,) = config.sources.directories
    document, diagnostics = parse_architecture_identity_bindings(
        yaml.safe_load(
            (
                RUNTIME / "declarations" / "bindings" / "architecture-identity-bindings.yaml"
            ).read_text()
        ),
        locator="architecture-identity-bindings.yaml",
    )

    assert diagnostics == []
    assert config.sources.clusters == []
    assert config.sources.service_workload_mapping is None
    assert {str(b.source_instance_id): b.service_id for b in document.bindings} == {
        str(
            source_instance_id(
                configured_source_id=directory.id,
                source_kind=SourceKind.FILESYSTEM,
                normalized_root_document_path="airflow-apiserver/openapi.yml",
            )
        ): "service:airflow-apiserver"
    }


def test_expected_provides_are_exactly_the_selected_operations():
    openapi = yaml.safe_load(OPENAPI.read_text())
    for method, path in SELECTED:
        assert method.lower() in openapi["paths"][path], (method, path)
    selected_ids = {f"operation:service:airflow-apiserver:{m}:{p}" for m, p in SELECTED}

    doc = load_expected(DOSSIER / "expected.yaml")
    provides = [r for r in doc.expected_relations if r.fact.type == "PROVIDES"]

    assert {r.fact.target for r in provides} == selected_ids
    assert all(r.fact.source == "service:airflow-apiserver" for r in provides)
    assert [r for r in doc.expected_relations if r.fact.type != "PROVIDES"] == []
    assert doc.expected_deployments == ()
    assert set(doc.scope.entities) == selected_ids | {"queue:default"}


def test_compose_runs_only_digest_pinned_or_run_built_images():
    compose = yaml.safe_load((RUNTIME / "docker-compose.yml").read_text())
    images = {name: service.get("image") for name, service in compose["services"].items()}
    images["x-airflow-common"] = compose["x-airflow-common"]["image"]
    for name, image in images.items():
        if name == "architecture-intelligence":
            # Rebuilt from the verified candidate checkout each run (runbook.md step 4).
            assert image.startswith("aip-i5-candidate:${AIP_CANDIDATE_SHA")
            assert "AIP_BUILD_REVISION" in compose["services"][name]["build"]["args"]
        else:
            assert "@sha256:" in image, name
            assert "${" not in image, name  # no environment override (e.g. AIRFLOW_IMAGE_NAME)


def test_compose_interpolates_only_the_three_required_variables():
    # PR #242 review: any `${VAR:-default}` would let the environment change the run's bytes (for
    # example AIRFLOW_PROJ_DIR re-pointing the Dag mount) without changing its reported identity.
    text = (RUNTIME / "docker-compose.yml").read_text()
    names = set(re.findall(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)", text))
    assert names == {"FERNET_KEY", "NEO4J_PASSWORD", "AIP_CANDIDATE_SHA"}
    assert all(
        re.fullmatch(r"\$\{[A-Z0-9_]+:\?[^}]*\}", m)
        for m in re.findall(r"(?<!\$)\$\{[^}]*\}", text)
    ), "every interpolation must be a required (:?) variable, never a default (:-)"

    compose = yaml.safe_load(text)
    dag_mounts = {
        volume
        for service in compose["services"].values()
        for volume in service.get("volumes", [])
        if volume.endswith(":/opt/airflow/dags")
    }
    assert dag_mounts == {"./dags:/opt/airflow/dags"}


def test_runbook_invokes_compose_only_through_the_frozen_helper():
    # PR #243 review: a bare `docker compose` would honor a gitignored .env (e.g. COMPOSE_FILE) or a
    # docker-compose.override.yml that the clean-checkout gate cannot see.
    runbook = (DOSSIER / "runbook.md").read_text()
    helper = re.search(r"^frozen_compose\(\) \{\n(.*?)\n\}", runbook, re.DOTALL | re.MULTILINE)

    assert helper is not None
    body = " ".join(helper.group(1).split())
    assert body == (
        'docker compose -p airflow-i5 --project-directory "$RUNTIME" '
        '-f "$RUNTIME/docker-compose.yml" \\ --env-file /dev/null "$@"'
    )
    assert runbook.count("docker compose") == 1  # only inside the helper


def test_every_declaration_file_is_a_name_the_filesystem_discoverer_enumerates():
    # The first Slice 5 attempt at 34067b7 stopped because the bindings document had a name that
    # CANDIDATE_FILENAMES does not contain, at the root level the discoverer never scans. It was skipped silently, and every OpenAPI
    # source was SERVICE_IDENTITY_UNRESOLVED.
    from app.ingestion.filesystem_discoverer import CANDIDATE_FILENAMES

    declarations = RUNTIME / "declarations"
    files = [p for p in declarations.rglob("*") if p.is_file()]
    assert files
    assert {p.name for p in files} <= set(CANDIDATE_FILENAMES)
    # FilesystemSourceDiscoverer enumerates only <root>/<subdirectory>/<candidate name>.
    assert all(len(p.relative_to(declarations).parts) == 2 for p in files)
    assert (declarations / "bindings" / "architecture-identity-bindings.yaml").is_file()
