"""v0.5.0 I6 Slice 1a: the frozen release golden-path profile (I6 §7, Draft 0.3).

Guards `examples/release-golden-path/`:
- its content digests;
- that every `expected.json` citation resolves to real lines;
- that it never changes the bundled-examples discovery (§7.4);
- that every transcribed input is equivalent to its component test's own input through production
  code (§7.2).

The OTLP and mapping checks call the component tests' own builders and constants, so a
transcription cannot drift from its source silently.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml
from google.protobuf import json_format
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

import tests.integration.test_i3_cross_source_qualification as i3
import tests.integration.test_i4_pubsub_qualification as i4
import tests.integration.test_i5_qualification_tooling as i5_tooling
from app.canonical.model import Service
from app.ingestion.filesystem_discoverer import CANDIDATE_FILENAMES, FilesystemSourceDiscoverer
from app.ingestion.orchestrator import run_filesystem_discovery
from app.settings import load_config
from app.sources.model import FilesystemSourceConfig
from app.sources.service_workload_mapping import load_service_workload_mapping
from app.telemetry.otlp_receiver import decode_export_request

REPO = Path(__file__).resolve().parents[2]
PROFILE_DIR = REPO / "examples" / "release-golden-path"
PHASES = ("demo", "pubsub", "k8s-agree", "k8s-conflict", "k8s-unresolved")
K8S_PHASES = ("k8s-agree", "k8s-conflict", "k8s-unresolved")
DECLARED_SERVICES = {
    "k8s-agree": {"service:runtime-demo": "runtime-demo"},
    "k8s-conflict": {
        "service:runtime-demo": "runtime-demo",
        "service:runtime-demo-alt": "runtime-demo-alt",
    },
    "k8s-unresolved": {"service:runtime-demo": "runtime-demo"},
}
_CITATION = re.compile(r"^(?P<path>[\w./-]+?)(?::(?P<lines>[\d,-]+))?(?: .*)?$")
_OTLP_HEX_ID_FIELDS = ("traceId", "spanId", "parentSpanId")


def _mounted_files(source: Path) -> list[Path]:
    """Every file a mount exposes, minus interpreter caches and this directory's own top-level files
    (the `demo` phase mounts all of `examples/`, and SHA256SUMS cannot pin itself or the README)."""
    if source.is_file():
        return [source]
    return sorted(
        p
        for p in source.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and (PROFILE_DIR not in p.parents or PROFILE_DIR / "profile" in p.parents)
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sums() -> dict[str, str]:
    entries = {}
    for line in (PROFILE_DIR / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split("  ", 1)
        entries[path] = digest
    return entries


def _phase(phase: str) -> dict:
    return yaml.safe_load((PROFILE_DIR / "profile" / phase / "phase.yaml").read_text())


def _decode_otlp_json(path: Path):
    """OTLP/HTTP JSON (what the pinned collector accepts) -> protobuf bytes (what it forwards to
    AIP) -> the production decoder. OTLP JSON carries trace/span ids as hex, while protobuf's
    generic JSON mapping expects base64 for bytes fields, so the ids are converted first."""
    document = json.loads(path.read_text())
    for resource_spans in document["resourceSpans"]:
        for scope_spans in resource_spans["scopeSpans"]:
            for span in scope_spans["spans"]:
                for field in _OTLP_HEX_ID_FIELDS:
                    if field in span:
                        span[field] = base64.b64encode(bytes.fromhex(span[field])).decode()
    request = json_format.ParseDict(document, ExportTraceServiceRequest())
    return decode_export_request(request.SerializeToString())


# --- digests and citations ---------------------------------------------------------------------


def test_sha256sums_pins_the_profile_and_every_referenced_component_file():
    sums = _sums()
    for relative, digest in sums.items():
        assert _sha256(REPO / relative) == digest, relative
    profile_files = {
        p.relative_to(REPO).as_posix() for p in (PROFILE_DIR / "profile").rglob("*") if p.is_file()
    }
    assert profile_files | {"examples/release-golden-path/expected.json"} <= set(sums)
    for phase in PHASES:
        for mount in _phase(phase)["mounts"]:
            for file in _mounted_files(REPO / mount["from"]):
                assert file.relative_to(REPO).as_posix() in sums, file


def _citations(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "source":
                yield from value if isinstance(value, list) else [value]
            else:
                yield from _citations(value)
    elif isinstance(node, list):
        for item in node:
            yield from _citations(item)


def test_every_expected_check_cites_existing_lines():
    expected = json.loads((PROFILE_DIR / "expected.json").read_text())
    assert set(expected["phases"]) == set(PHASES)
    for phase in expected["phases"].values():
        for check in phase["checks"]:
            assert check["source"], check["id"]
    citations = list(_citations(expected))
    assert citations
    for citation in citations:
        match = _CITATION.match(citation)
        assert match, citation
        path = REPO / match["path"]
        assert path.is_file(), citation
        if match["lines"]:
            line_count = len(path.read_text().splitlines())
            for number in re.findall(r"\d+", match["lines"]):
                assert 1 <= int(number) <= line_count, citation


# --- §7.4: the bundled-examples discovery is unchanged ------------------------------------------


def test_no_discoverer_candidate_sits_directly_in_the_profile_directory():
    assert not [name for name in CANDIDATE_FILENAMES if (PROFILE_DIR / name).exists()]


def test_bundled_examples_discovery_is_unchanged_by_the_profile():
    [bundled] = load_config(REPO / "config.yaml").sources.directories
    outcome = FilesystemSourceDiscoverer(
        bundled.model_copy(update={"root": REPO / "examples"})
    ).discover()
    assert outcome.enumeration_complete is True
    locators = sorted(source.descriptor.locator for source in outcome.loaded_sources)
    # tests/integration/test_api.py:316 - the six bundled sources.
    assert len(locators) == 6
    assert not [locator for locator in locators if "release-golden-path" in locator]


def test_repinned_documentation_files_are_invisible_to_the_demo_import():
    """v0.5.0 I6 Slice 1b-iii re-pinned exactly the `examples/mcp-clients/*.md` digests after a
    documentation-only change: the v0.4.2 client matrix is marked as not re-qualified for v0.5.0.
    The `demo` phase mounts all of `examples/`, but the discoverer only enumerates candidate
    filenames. So these files can never change the demo import or `expected.json`."""
    repinned = [path for path in _sums() if path.startswith("examples/mcp-clients/")]
    assert repinned
    for path in repinned:
        assert path.endswith(".md"), path
        assert Path(path).name not in CANDIDATE_FILENAMES, path


# --- §7.2 transcription equivalence -------------------------------------------------------------


@pytest.mark.parametrize("phase", K8S_PHASES)
def test_declaration_transcriptions_emit_exactly_the_tests_in_memory_services(phase):
    root = PROFILE_DIR / "profile" / phase / "declarations"
    run = run_filesystem_discovery(FilesystemSourceConfig(id=f"golden-path-{phase}", root=root))
    assert run.inventory_status.value == "COMPLETE"
    assert {o.outcome.result.value for o in run.source_outcomes.values()} == {"ACCEPTED"}
    model = run.merged_model
    # tests/integration/test_i3_cross_source_qualification.py `_declare_service`
    assert model.services == [
        Service(id=service_id, name=name, version="1")
        for service_id, name in sorted(DECLARED_SERVICES[phase].items())
    ]
    assert model.operations == []
    assert model.schemas == []
    assert model.messages == []
    assert model.queues == []
    assert model.topics == []
    assert model.subscriptions == []
    assert model.relations == []


def test_k8s_agree_otlp_decodes_to_the_tests_runtime_span():
    decoded = _decode_otlp_json(PROFILE_DIR / "profile" / "k8s-agree" / "otlp.json")
    assert decoded == [i3._runtime_demo_span(service_name="runtime-demo")]


def test_pubsub_otlp_decodes_to_the_tests_runtime_spans_in_order():
    decoded = _decode_otlp_json(PROFILE_DIR / "profile" / "pubsub" / "otlp.json")
    environment, spans = i4._spans(i4.FIXTURES_ROOT / "google-pubsub")
    assert environment == _phase("pubsub")["observation_context"]["environment"]
    assert decoded == spans


def test_unresolved_mapping_is_byte_identical_to_the_tests_constant():
    mapping = PROFILE_DIR / "profile" / "k8s-unresolved" / "mapping.yaml"
    assert mapping.read_text() == i5_tooling._TWO_ABSENT_TARGET_MAPPINGS
    _, diagnostics = load_service_workload_mapping(mapping)
    assert diagnostics == ()


# --- phase configs mirror the component setups -------------------------------------------------


@pytest.mark.parametrize("phase", ("pubsub", *K8S_PHASES))
def test_phase_configs_load_and_match_their_component_setup(phase):
    config = load_config(PROFILE_DIR / "profile" / phase / "config.yaml")
    assert config.llm.enabled is False
    assert config.telemetry.service_aliases == {}
    assert config.telemetry.queue_aliases == {}
    assert config.telemetry.topic_aliases == {}
    assert config.telemetry.http_correlation.enabled is False
    assert (
        config.runtime_analysis.default_environment
        == (_phase(phase)["observation_context"]["environment"])
    )
    if phase == "pubsub":
        [directory] = config.sources.directories
        assert directory.id == "i4-qualification-google-pubsub"
        assert (
            directory.stable_target_identity
            == "urn:aip:logical-root:i4-qualification-google-pubsub"
        )
        assert config.sources.clusters == []
        assert config.sources.service_workload_mapping is None
        return
    [cluster] = config.sources.clusters
    reference = i3._kubernetes_config()
    assert cluster.model_dump(exclude={"root"}) == reference.model_dump(exclude={"root"})
    assert config.sources.service_workload_mapping is not None


@pytest.mark.parametrize("phase", PHASES)
def test_every_phase_mount_source_exists_and_targets_are_unique(phase):
    spec = _phase(phase)
    assert spec["phase"] == phase
    targets = [mount["to"] for mount in spec["mounts"]]
    assert len(targets) == len(set(targets))
    for mount in spec["mounts"]:
        assert (REPO / mount["from"]).exists(), mount
    config_mount = next(m for m in spec["mounts"] if m["to"] == f"/app/{spec['config_path']}")
    assert (REPO / config_mount["from"]).is_file()
