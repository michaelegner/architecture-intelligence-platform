"""v0.6.1 I3a §6.2: Apache Airflow 3.3.1, the negative Broker-attribution boundary.

The frozen v0.5.0 I5 dossier establishes `CeleryExecutor`, a Redis broker and the `default` task
queue at configuration level, and that scheduler/worker/task-runner process roles have no admitted
Service identity; only `service:airflow-apiserver` is admitted (via the dossier's identity binding of
its byte-identical upstream OpenAPI). An explicit, operator-authored manifest names a stable Redis
broker id for an unadmitted worker Service. AIP must reject it: no Broker, no `USES_BROKER`, no
attribution to `service:airflow-apiserver`, and no Service minted for the worker.

This is the real-system confirmation of the unresolved-manifest-Service guard that
`tests/unit/test_manifest_adapter_broker.py` exercises deterministically, not a separate semantic
rule. It runs the real discovery over the frozen inputs and needs no Neo4j.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import yaml

from app.ingestion.orchestrator import run_filesystem_discovery
from app.sources.model import DiagnosticCode, FilesystemSourceConfig, IngestionResult

ROOT = Path(__file__).resolve().parents[2]
DOSSIER = ROOT / "docs" / "real-world-validation" / "v0.5.0" / "apache-airflow" / "runtime"
NEGATIVE = ROOT / "tests" / "fixtures" / "broker-qualification" / "airflow-negative"
# Frozen in the dossier's profile.md / upstream.md (the same digest tests/unit/
# test_airflow_v05_dossier.py pins); re-asserted here because this test relies on it being untouched.
OPENAPI_SHA256 = "2c57114da43a131f68772f1660ed52ca7116089a20893ac5e5f6225ffde3abd9"
# The id the dossier's identity binding was computed for (config.airflow-i5.yaml's directory id).
CONFIGURED_SOURCE_ID = "airflow-v0.5-declarations"


def _discover(tmp_path: Path):
    root = tmp_path / "declarations"
    shutil.copytree(DOSSIER / "declarations", root)
    shutil.copytree(NEGATIVE / "declarations", root, dirs_exist_ok=True)
    return root, run_filesystem_discovery(
        FilesystemSourceConfig(id=CONFIGURED_SOURCE_ID, root=root)
    )


def test_the_frozen_airflow_inputs_are_the_unmodified_dossier_files():
    openapi = DOSSIER / "declarations" / "airflow-apiserver" / "openapi.yml"
    assert hashlib.sha256(openapi.read_bytes()).hexdigest() == OPENAPI_SHA256


def test_the_redis_broker_manifest_for_an_unadmitted_worker_is_rejected(tmp_path):
    expected = yaml.safe_load((NEGATIVE / "expected.yaml").read_text())
    _, run = _discover(tmp_path)

    outcomes = {
        Path(o.descriptor_locator).relative_to(tmp_path / "declarations").as_posix(): o.outcome
        for o in run.source_outcomes.values()
    }
    manifest = outcomes[expected["manifest"]["locator"]]
    assert manifest.result is IngestionResult.REJECTED_UNSUPPORTED
    assert [d.code for d in manifest.diagnostics] == [
        DiagnosticCode.MANIFEST_CALL_SOURCE_UNRESOLVED
    ]
    assert expected["manifest"]["diagnostic"] == "MANIFEST_CALL_SOURCE_UNRESOLVED"
    assert manifest.diagnostics[0].source_pointer == "/x-aip-service-id"
    # the manifest emits nothing at all
    assert manifest.model.brokers == [] and manifest.model.relations == []
    assert manifest.model.services == [] and manifest.model.operations == []


def test_no_broker_is_attributed_and_no_worker_service_is_minted(tmp_path):
    expected = yaml.safe_load((NEGATIVE / "expected.yaml").read_text())
    _, run = _discover(tmp_path)

    # the OpenAPI source (admitted through the dossier's identity binding) is unaffected
    openapi = next(
        o.outcome
        for o in run.source_outcomes.values()
        if o.descriptor_locator.endswith("airflow-apiserver/openapi.yml")
    )
    # (its payload-composition limitations are the unchanged v0.5.0 baseline, not a Broker matter)
    assert openapi.result in {
        IngestionResult.ACCEPTED,
        IngestionResult.ACCEPTED_WITH_LIMITATIONS,
    }
    assert [s.id for s in openapi.model.services] == ["service:airflow-apiserver"]

    merged = run.merged_model
    assert [b.stable_broker_id for b in merged.brokers] == expected["brokers"] == []
    assert [r for r in merged.relations if r.type == "USES_BROKER"] == []
    assert sorted(s.id for s in merged.services) == expected["services"]
    assert "service:airflow-worker" not in {s.id for s in merged.services}
    # existing messaging negatives unchanged: the Redis broker/`default` queue mint no destination
    assert merged.queues == [] and merged.topics == [] and merged.subscriptions == []
    # a rejected source makes the run non-committing, so nothing about Redis can reach the graph
    assert run.commit_eligible is False
