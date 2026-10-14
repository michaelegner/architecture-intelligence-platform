"""Wiring of the `/v1/traces` stall benchmark (`benchmarks/traces_stall.py`): the payload has the
requested number of resolvable span pairs and one measurement returns its structure, with the POST
accepted and probes answered. It asserts no timing."""

import os
import tempfile
from pathlib import Path

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

import app.main
from benchmarks.traces_stall import build_payload, measure_once
from tests.integration.support.live_server import free_loopback_port, serve_over_real_http


def test_payload_has_two_spans_per_pair():
    request = ExportTraceServiceRequest.FromString(build_payload(7))
    spans = [s for rs in request.resource_spans for ss in rs.scope_spans for s in ss.spans]
    assert len(spans) == 14
    assert len({s.span_id for s in spans}) == 14


def test_measure_once_posts_the_batch_and_answers_probes(neo4j_container, monkeypatch):
    monkeypatch.setenv("NEO4J_URI", neo4j_container.get_connection_url())
    monkeypatch.setenv("NEO4J_USER", neo4j_container.username)
    monkeypatch.setenv("NEO4J_PASSWORD", neo4j_container.password)
    monkeypatch.setenv("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    port = free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "config.yaml"
        config_path.write_text(
            "architecture_intelligence:\n"
            "  mcp:\n"
            f'    allowed-origins: ["{base_url}"]\n'
            f'    allowed-hosts: ["127.0.0.1:{port}"]\n'
        )
        monkeypatch.setattr(app.main, "CONFIG_PATH", config_path)
        with serve_over_real_http(app.main.create_app(), port=port):
            result = measure_once(base_url, "/health", build_payload(3))

    assert result["post_status"] == 200
    assert result["ingest_s"] > 0
    assert result["probes_during_ingest"] >= 0
    assert result["idle_max_s"] >= result["idle_p50_s"] > 0
