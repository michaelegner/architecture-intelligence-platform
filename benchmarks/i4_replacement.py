"""Measure the existing frozen B01 bridge, without duplicating its inputs or assertions."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.locality_contracts import LocalityQueryRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from benchmarks.i4_metadata import input_pins
from benchmarks.locality_cost import measure_reads
from tests.integration import test_locality_oracle as oracle
from tests.integration import test_scoped_applicability as applicability
from tests.integration import test_v060_i4_bridges as bridge
from tests.integration.locality_oracle import world


def measure_replacements(driver, root: Path, configured_producer: Producer) -> list[dict]:
    return [
        _measure_replacement(driver, root / case, configured_producer, case)
        for case in ("B01a", "B01b")
    ]


def _measure_replacement(
    driver, directory: Path, configured_producer: Producer, case_id: str
) -> dict:
    states = []
    answers = []
    imports = []
    posts = []
    service = ArchitectureIntelligenceService(
        driver, database=world.DATABASE, producer=configured_producer
    )
    original_ask = bridge._ask
    original_import = bridge._import
    source_calls = []
    original_import_source = applicability.import_kubernetes_source
    original_persist_batch = world.persist_observation_batch

    def capture(*args, **kwargs):
        started = time.perf_counter()
        result = original_import(*args, **kwargs)
        imports.append(
            {
                **source_calls[-1],
                "capture_total_including_fixture_ms": (time.perf_counter() - started) * 1000,
                "source_instance_id": result.source_instance_id,
                "revision": kwargs["revision"],
                "generated_inputs": input_pins(directory),
            }
        )
        return result

    def import_source(*args, **kwargs):
        started = time.perf_counter()
        result = original_import_source(*args, **kwargs)
        source_calls.append(
            {
                "capture_import_ms": (time.perf_counter() - started) * 1000,
                "committed": result.committed,
                "source_configuration": kwargs["source_config"].model_dump(mode="json"),
            }
        )
        return result

    def persist_batch(*args, **kwargs):
        started = time.perf_counter()
        original_persist_batch(*args, **kwargs)
        posts.append(
            {
                "persist_ms": (time.perf_counter() - started) * 1000,
                "accepted_facts": len(args[2].facts),
                "scoped_configuration": kwargs["scoped"].model_dump(mode="json"),
            }
        )

    def ask(graph, request):
        answer = original_ask(graph, request)
        assert answer["producer"] == configured_producer.model_dump(mode="json")
        answers.append({"request": request, "answer": answer})
        if request["mode"] == "query" and len(states) < len(imports):
            states.append(
                {
                    "state": "C1" if len(imports) == 1 else "C2",
                    "capture": imports[-1],
                    "post": posts[-1],
                    **measure_reads(
                        graph,
                        service,
                        LocalityQueryRequest.model_validate(request),
                        configured_producer,
                    ),
                }
            )
        return answer

    with (
        patch.object(oracle, "PRODUCER", configured_producer),
        patch.object(bridge, "_import", capture),
        patch.object(applicability, "import_kubernetes_source", import_source),
        patch.object(world, "persist_observation_batch", persist_batch),
        patch.object(bridge, "_ask", ask),
    ):
        bridge.test_p3_bridge(driver, directory, case_id)
    assert [s["state"] for s in states] == ["C1", "C2"]
    return {
        "case_id": case_id,
        "source_mode": "synthetic frozen B01 inputs through real import/persistence",
        "oracle_match": True,
        "states": states,
        "semantic_answers": answers,
    }
