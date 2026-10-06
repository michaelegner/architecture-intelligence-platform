"""v0.5.1 I1: the Quarkus Super Heroes demo's own inputs (spec §4).

Guards `examples/quarkus-super-heroes-demo/` through production code:
- the operator-authored AsyncAPI overlay is enumerated by the real discoverer and adapted under the
  unchanged v0.5.0 I4 rules (a declared Topic, no Subscription for the consumer group side);
- `otlp.json` decodes to exactly the three CLIENT/SERVER pairs transcribed from the frozen
  final-candidate observed evidence, inside the frozen window;
- the demo config keeps the source and cluster ids the frozen dossier bindings and mapping use;
- the demo never changes the bundled-examples discovery the minimal demo relies on.

The end-to-end answer shape is checked by the demo's own `check_ready.py` against a running AIP.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.ingestion.filesystem_discoverer import CANDIDATE_FILENAMES, FilesystemSourceDiscoverer
from app.ingestion.orchestrator import run_filesystem_discovery
from app.settings import load_config
from app.sources.model import FilesystemSourceConfig
from tests.unit.test_release_golden_path_profile import _decode_otlp_json

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO / "examples" / "quarkus-super-heroes-demo"
DOSSIER = REPO / "docs" / "real-world-validation" / "v0.5.0"
FINAL_EVIDENCE = (
    DOSSIER
    / "final-candidate/quarkus-super-heroes/artifacts/public-surfaces"
    / "evidence_service_rest-fights_batch_0.rest.json"
)


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.strip()).astimezone(UTC)


def test_overlay_is_discovered_and_adapted_under_the_i4_rules():
    run = run_filesystem_discovery(
        FilesystemSourceConfig(id="qsh-demo-overlay", root=DEMO_DIR / "overlay")
    )
    assert run.inventory_status.value == "COMPLETE"
    overlay = DEMO_DIR / "overlay"
    outcomes = {
        Path(o.descriptor_locator).relative_to(overlay).as_posix(): o.outcome
        for o in run.source_outcomes.values()
    }
    assert {locator: o.result.value for locator, o in outcomes.items()} == {
        "rest-fights/asyncapi.yaml": "ACCEPTED",
        "event-statistics/asyncapi.yaml": "ACCEPTED_WITH_LIMITATIONS",
    }
    assert [d.code for d in outcomes["event-statistics/asyncapi.yaml"].diagnostics] == [
        "SUBSCRIPTION_IDENTITY_MISSING"
    ]

    model = run.merged_model
    assert [topic.name for topic in model.topics] == ["fights"]
    assert model.subscriptions == []
    assert model.queues == []
    [topic] = model.topics
    # Each source owns its own `Fight` Message (and Schema), as in tests/fixtures/pubsub/kafka,
    # whose expected facts also list CARRIES twice. The consumer side adds no relation of its own.
    assert Counter(r.type for r in model.relations) == Counter(
        {"PUBLISHES_TO": 1, "CARRIES": 2, "CONFORMS_TO": 2, "USES_BROKER": 2}
    )
    # v0.6.1 I1: both Services declare the same explicit `x-aip-broker-id: kafka:fights-kafka`, so
    # they share one Broker; the unresolved Subscription stays unresolved.
    [broker] = model.brokers
    assert broker.stable_broker_id == "kafka:fights-kafka"
    assert {(r.source_id, r.target_id) for r in model.relations if r.type == "USES_BROKER"} == {
        ("service:rest-fights", broker.id),
        ("service:event-statistics", broker.id),
    }
    [publish] = [r for r in model.relations if r.type == "PUBLISHES_TO"]
    assert (publish.source_id, publish.target_id) == ("service:rest-fights", topic.id)
    message_ids = {m.id for m in model.messages}
    assert {r.target_id for r in model.relations if r.type == "CARRIES"} == message_ids
    assert {r.source_id for r in model.relations if r.type == "CARRIES"} == {topic.id}
    assert [message.name for message in model.messages] == ["Fight", "Fight"]
    # The overlay must not rename the Services the upstream declarations already name.
    assert {s.id: s.name for s in model.services} == {
        "service:event-statistics": "event-statistics",
        "service:rest-fights": "Fights API",
    }


def test_otlp_transcribes_exactly_the_final_candidate_observations():
    records = [
        r
        for r in json.loads(FINAL_EVIDENCE.read_text())["data"]["records"]
        if r["evidence_type"] == "OBSERVED"
    ]
    expected = {
        (r["supports"][0]["target_id"], _utc(r["observation"]["first_seen"])) for r in records
    }
    assert len(expected) == 3

    spans = _decode_otlp_json(DEMO_DIR / "otlp.json")
    clients = {s.span_id: s for s in spans if s.span_kind == "CLIENT"}
    servers = [s for s in spans if s.span_kind == "SERVER"]
    assert len(clients) == len(servers) == 3 == len(spans) // 2
    window = (
        _utc((DOSSIER / "final-candidate/quarkus-super-heroes/artifacts/window-start").read_text()),
        _utc((DOSSIER / "final-candidate/quarkus-super-heroes/artifacts/window-end").read_text()),
    )
    transcribed = set()
    for server in servers:
        client = clients[server.parent_span_id]
        assert client.trace_id == server.trace_id
        assert client.service_name == "rest-fights"
        for span in (client, server):
            assert span.environment == "quarkus-i5"
            assert span.service_version == "1.0"
            assert window[0] <= span.start_time <= span.end_time <= window[1]
        method = server.attributes["http.request.method"]
        route = server.attributes["http.route"]
        assert (client.attributes["http.request.method"], client.attributes["http.route"]) == (
            method,
            route,
        )
        target = f"operation:service:{server.service_name}:{method}:{route}"
        transcribed.add((target, server.end_time))
    assert transcribed == expected


def test_config_keeps_the_ids_the_frozen_bindings_and_mapping_depend_on():
    demo = load_config(DEMO_DIR / "config.yaml")
    frozen = load_config(DOSSIER / "quarkus-super-heroes/runtime/config.quarkus-i5.yaml")
    assert [d.id for d in demo.sources.directories] == ["qsh-v0.5-declarations", "qsh-demo-overlay"]
    [cluster] = demo.sources.clusters
    [frozen_cluster] = [c for c in frozen.sources.clusters if c.id == cluster.id]
    ignore = {"root"}
    assert cluster.model_dump(exclude=ignore) == frozen_cluster.model_dump(exclude=ignore)
    assert demo.runtime_analysis.default_environment == "quarkus-i5"


def test_demo_never_changes_the_bundled_examples_discovery():
    assert not [name for name in CANDIDATE_FILENAMES if (DEMO_DIR / name).exists()]
    [bundled] = load_config(REPO / "config.yaml").sources.directories
    outcome = FilesystemSourceDiscoverer(
        bundled.model_copy(update={"root": REPO / "examples"})
    ).discover()
    locators = [source.descriptor.locator for source in outcome.loaded_sources]
    assert len(locators) == 6
    assert not [locator for locator in locators if "quarkus-super-heroes-demo" in locator]
