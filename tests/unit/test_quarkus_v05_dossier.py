"""Guards the frozen v0.5.0 I5 Quarkus dossier inputs (I5 §§5-6, spec Draft 0.3) against drift.

These tests check the dossier's own internal consistency and its fixed digests. They never run AIP
against the target, so they produce no qualifying output (I5 §6).
"""

import hashlib
import importlib.util
import re
from pathlib import Path

import yaml

from app.settings import load_config
from app.sources.identity import source_instance_id
from app.sources.kubernetes_envelope import KubernetesSourceSnapshot
from app.sources.manifest_bindings import parse_architecture_identity_bindings
from app.sources.model import SourceKind
from app.sources.service_workload_mapping import parse_service_workload_mappings
from real_world_validation.loader import load_expected

DOSSIER = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "real-world-validation"
    / "v0.5.0"
    / "quarkus-super-heroes"
)
RUNTIME = DOSSIER / "runtime"
DECLARATIONS = RUNTIME / "declarations"
SERVICES = ("rest-fights", "rest-heroes", "rest-villains", "rest-narration")

# Frozen in profile.md / upstream.md; independently re-checked against the pin by runbook.md step 2.
UPSTREAM_SHA256 = {
    "declarations/rest-fights/openapi.yml": (
        "6ddbcf5b750b156b0445227b3fb5a51a6b6492f8d10b8c4dac72f1fa40eb1275"
    ),
    "declarations/rest-heroes/openapi.yml": (
        "6068d22ef8a4f16d48c48f5c650e6afaee98b54b2ec87dcd2760d920064fb980"
    ),
    "declarations/rest-villains/openapi.yml": (
        "8c2fec17445d17990bf27bab024f22b31150c78c22cb349d904b79dc5e328473"
    ),
    "declarations/rest-narration/openapi.yml": (
        "686351d7e0777c738696f0dc3a80dd0e5c49db2afd0426a3e4142f22aa2f0bef"
    ),
    "k8s/unmodified/java25-kubernetes.yml": (
        "a1cd818385b3bbb582be12d5e43960f3f1ce85a619e5a974bc5c3b03c94d2c25"
    ),
}
DERIVED = "k8s/namespaced/java25-kubernetes.namespaced.yml"
DERIVED_SHA256 = "4ba52254b4a331590f1f7b1a43ae9f89a813dc7885938769bcdac8cd907d1cd2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _derive_module():
    spec = importlib.util.spec_from_file_location(
        "derive_namespaced", RUNTIME / "k8s" / "derive_namespaced.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upstream_supplied_inputs_match_their_frozen_digests():
    for relative, digest in UPSTREAM_SHA256.items():
        assert _sha256(RUNTIME / relative) == digest, relative


def test_derived_manifest_regenerates_byte_for_byte_and_only_adds_namespace_lines():
    module = _derive_module()
    source = (RUNTIME / "k8s" / "unmodified" / "java25-kubernetes.yml").read_text()
    derived = module.derive(source)
    module.verify(source, derived)

    assert derived.encode() == (RUNTIME / DERIVED).read_bytes()
    assert _sha256(RUNTIME / DERIVED) == DERIVED_SHA256
    added = [line for line in derived.split("\n") if line not in source.split("\n")]
    assert set(added) == {"  namespace: quarkus-super-heroes"}
    assert len(derived.split("\n")) - len(source.split("\n")) == 56


def test_envelopes_are_valid_and_bind_their_file_digests():
    for kind in ("namespaced", "unmodified"):
        envelope_path = RUNTIME / "k8s" / kind / "envelope.yaml"
        envelope = KubernetesSourceSnapshot.model_validate(
            yaml.safe_load(envelope_path.read_text())
        )

        assert envelope.source.mode == "DECLARED_MANIFEST"
        assert envelope.scope.namespaces == ["quarkus-super-heroes"]
        for entry in envelope.files:
            assert _sha256(envelope_path.parent / entry.path) == entry.sha256


def test_config_registrations_match_their_envelopes():
    config = load_config(RUNTIME / "config.quarkus-i5.yaml")
    for cluster in config.sources.clusters:
        envelope = yaml.safe_load(
            (RUNTIME / cluster.root / cluster.envelope_relative_path).read_text()
        )
        assert envelope["source"]["configuredSourceId"] == cluster.id
        assert envelope["source"]["configuredScopeId"] == cluster.resolved_scope_id
        assert envelope["source"]["clusterUid"] == cluster.cluster_uid
        assert envelope["metadata"]["producer"] == cluster.authorized_producer
        assert envelope["completeness"]["authorityRef"] == cluster.authority_record
    assert {c.id for c in config.sources.clusters} == {
        "qsh-k8s-namespaced",
        "qsh-k8s-upstream-unmodified",
    }


def test_identity_bindings_target_the_configured_openapi_sources():
    config = load_config(RUNTIME / "config.quarkus-i5.yaml")
    (directory,) = config.sources.directories
    document, diagnostics = parse_architecture_identity_bindings(
        yaml.safe_load((DECLARATIONS / "identity-bindings.yaml").read_text()),
        locator="identity-bindings.yaml",
    )

    assert diagnostics == []
    expected = {
        str(
            source_instance_id(
                configured_source_id=directory.id,
                source_kind=SourceKind.FILESYSTEM,
                normalized_root_document_path=f"{service}/openapi.yml",
            )
        ): f"service:{service}"
        for service in SERVICES
    }
    actual = {str(binding.source_instance_id): binding.service_id for binding in document.bindings}
    assert actual == expected


def test_manifest_calls_are_exactly_the_expected_calls():
    operations = {}
    for service in SERVICES:
        openapi = yaml.safe_load((DECLARATIONS / service / "openapi.yml").read_text())
        for path, item in openapi["paths"].items():
            for method, operation in item.items():
                if isinstance(operation, dict) and "operationId" in operation:
                    operations[(f"service:{service}", operation["operationId"])] = (
                        f"operation:service:{service}:{method.upper()}:{path}"
                    )
    manifest = yaml.safe_load((DECLARATIONS / "rest-fights" / "architecture.yaml").read_text())
    manifest_targets = {operations[(c["service"], c["operationId"])] for c in manifest["calls"]}

    doc = load_expected(DOSSIER / "expected.yaml")
    calls = [r for r in doc.expected_relations if r.fact.type == "CALLS"]
    provides = [r for r in doc.expected_relations if r.fact.type == "PROVIDES"]

    assert manifest["x-aip-service-id"] == "service:rest-fights"
    assert len(manifest["calls"]) == len(manifest_targets) == 7
    assert {r.fact.target for r in calls} == manifest_targets
    assert {r.fact.target for r in provides} == set(operations.values())
    assert len(provides) == 35


def test_mapping_binds_only_the_three_frozen_services():
    raw = yaml.safe_load((RUNTIME / "mapping.yaml").read_text())
    document, diagnostics = parse_service_workload_mappings(
        raw, locator="mapping.yaml", content_digest=_sha256(RUNTIME / "mapping.yaml")
    )
    doc = load_expected(DOSSIER / "expected.yaml")

    assert diagnostics == []
    assert document is not None
    mapped = {(m["serviceId"], m["workload"]["name"]) for m in raw["mappings"]}
    assert mapped == {
        ("service:rest-fights", "rest-fights"),
        ("service:rest-heroes", "rest-heroes"),
        ("service:rest-villains", "rest-villains"),
    }
    assert {(d.fact.service, d.fact.workload.name) for d in doc.expected_deployments} == mapped
    forbidden = {(d.service, d.workload.name) for d in doc.forbidden_deployments}
    assert forbidden == {
        ("service:rest-narration", "rest-narration"),
        ("service:event-statistics", "event-statistics"),
    }
    assert not forbidden & mapped


def test_compose_runs_only_digest_pinned_or_run_built_images():
    compose = yaml.safe_load((RUNTIME / "docker-compose.yml").read_text())
    for name, service in compose["services"].items():
        image = service["image"]
        if name == "architecture-intelligence":
            # Rebuilt from the verified candidate checkout each run (runbook.md step 4).
            assert image.startswith("aip-i5-candidate:${AIP_CANDIDATE_SHA")
            assert "AIP_BUILD_REVISION" in service["build"]["args"]
        elif image.startswith("quarkus-super-heroes/"):
            # Rebuilt from scratch at the pin each run and verified by id (runbook.md steps 3, 5).
            assert image.endswith(":8ea0337"), name
        else:
            assert "@sha256:" in image, name


def test_compose_interpolates_only_the_three_required_variables():
    # Post-freeze hardening (profile.md "Revision history"): any `${VAR:-default}` would let the
    # environment change the run's bytes without changing its reported identity.
    # Compose never interpolates comment lines, so only configuration lines are checked.
    text = "\n".join(
        line
        for line in (RUNTIME / "docker-compose.yml").read_text().splitlines()
        if not line.lstrip().startswith("#")
    )
    names = set(re.findall(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)", text))
    assert names == {"NEO4J_PASSWORD", "AIP_CANDIDATE_SHA", "QUARKUS_SUPERHEROES_CHECKOUT"}
    assert all(
        re.fullmatch(r"\$\{[A-Z0-9_]+:\?[^}]*\}", m)
        for m in re.findall(r"(?<!\$)\$\{[^}]*\}", text)
    ), "every interpolation must be a required (:?) variable, never a default (:-)"


def test_runbook_invokes_compose_only_through_the_frozen_helper():
    # PR #243 review: a bare `docker compose` would honor a gitignored .env (e.g. COMPOSE_FILE) or a
    # docker-compose.override.yml that the clean-checkout gate cannot see.
    runbook = (DOSSIER / "runbook.md").read_text()
    helper = re.search(r"^frozen_compose\(\) \{\n(.*?)\n\}", runbook, re.DOTALL | re.MULTILINE)

    assert helper is not None
    body = " ".join(helper.group(1).split())
    assert body == (
        'docker compose -p qsh-i5 --project-directory "$RUNTIME" '
        '-f "$RUNTIME/docker-compose.yml" \\ --env-file /dev/null "$@"'
    )
    assert runbook.count("docker compose") == 1  # only inside the helper
