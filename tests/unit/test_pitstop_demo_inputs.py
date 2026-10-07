"""v0.6.2 I1a: the Pitstop demo's own inputs (spec §4.1, §4.2).

Guards `examples/pitstop-demo/` through production code:
- the nine operator-authored AsyncAPI overlays are enumerated by the real discoverer and adapted under
  the existing rules (one Topic `Pitstop`, five named Subscriptions, one Broker, no payload);
- `fixtures/otlp.json` decodes to the authored send/process spans inside the frozen UTC day, carrying
  exactly the attributes the runtime guards read, and `service.name` equals each overlay `info.title`;
- the demo config and provenance record what the demo claims;
- the demo never changes the bundled-examples discovery the minimal demo relies on.

The end-to-end answer shape is checked by the demo's own `check_ready.py` against a running AIP.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.ingestion.filesystem_discoverer import CANDIDATE_FILENAMES, FilesystemSourceDiscoverer
from app.ingestion.orchestrator import run_filesystem_discovery
from app.settings import load_config
from app.sources.model import FilesystemSourceConfig
from tests.unit.test_release_golden_path_profile import _decode_otlp_json, _sums

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO / "examples" / "pitstop-demo"
OVERLAY = DEMO_DIR / "overlay"
FIXTURE = DEMO_DIR / "fixtures" / "otlp.json"

BROKER = "rabbitmq:pitstop-rabbitmq"
ENVIRONMENT = "pitstop-demo"
DAY_START = datetime(2026, 10, 6, tzinfo=UTC)
DAY_END = datetime(2026, 10, 7, tzinfo=UTC)
PUBLISHERS = {
    "WorkshopManagementAPI",
    "CustomerManagementAPI",
    "VehicleManagementAPI",
    "TimeService",
}
QUEUES = {
    "InvoiceService": "Invoicing",
    "NotificationService": "Notifications",
    "WorkshopManagementEventHandler": "WorkshopManagement",
    "AuditlogService": "Auditlog",
    "ReportingService": "Reporting",
}
# the authored fixture deliberately omits AuditlogService's receive span (PROVENANCE.md)
OBSERVED_CONSUMERS = set(QUEUES) - {"AuditlogService"}


def _documents() -> dict[str, dict]:
    return {
        path.parent.name: yaml.safe_load(path.read_text())
        for path in sorted(OVERLAY.glob("*/asyncapi.yaml"))
    }


def test_overlay_is_discovered_and_adapted_under_the_existing_rules():
    run = run_filesystem_discovery(FilesystemSourceConfig(id="pitstop-demo-overlay", root=OVERLAY))
    assert run.inventory_status.value == "COMPLETE"
    outcomes = {
        Path(o.descriptor_locator).relative_to(OVERLAY).as_posix(): o.outcome
        for o in run.source_outcomes.values()
    }
    assert len(outcomes) == 9
    assert {o.result.value for o in outcomes.values()} == {"ACCEPTED"}
    assert all(o.diagnostics == () for o in outcomes.values())

    model = run.merged_model
    assert [topic.name for topic in model.topics] == ["Pitstop"]
    assert {s.name for s in model.subscriptions} == set(QUEUES.values())
    assert model.queues == []
    assert model.messages == []
    # nine services share one explicit Broker; four publish, five receive through a named Subscription
    [broker] = model.brokers
    assert broker.stable_broker_id == BROKER
    relations = Counter(r.type for r in model.relations)
    assert relations == Counter(
        {"PUBLISHES_TO": 4, "SUBSCRIPTION_OF": 5, "RECEIVES_FROM": 5, "USES_BROKER": 9}
    )
    assert {r.target_id for r in model.relations if r.type == "USES_BROKER"} == {broker.id}
    assert {s.name for s in model.services} == PUBLISHERS | set(QUEUES)


def test_overlay_follows_the_spike_rules_and_declares_no_payload():
    documents = _documents()
    assert len(documents) == 9
    for name, document in documents.items():
        assert document["asyncapi"] == "2.6.0", name
        assert document["x-aip-service-id"] == f"service:{name}", name
        assert set(document["channels"]) == {"Pitstop"}, name
        assert document["channels"]["Pitstop"]["x-aip-destination-kind"] == "topic", name
        [server] = document["servers"].values()
        assert server["x-aip-broker-id"] == BROKER, name
        assert "bindings" not in server, (
            name
        )  # a virtualHost would split the exchange in two Topics
        assert "components" not in document, name  # AIP holds no payload or field knowledge
        channel = document["channels"]["Pitstop"]
        assert "message" not in channel.get("publish", {}) | channel.get("subscribe", {}), name
    publishers = {
        d["info"]["title"] for d in documents.values() if "publish" in d["channels"]["Pitstop"]
    }
    assert publishers == PUBLISHERS
    consumers = {
        d["info"]["title"]: d["channels"]["Pitstop"]["subscribe"]["x-aip-subscription-name"]
        for d in documents.values()
        if "subscribe" in d["channels"]["Pitstop"]
    }
    assert consumers == QUEUES


def test_fixture_is_the_authored_replay_inside_the_frozen_utc_day():
    spans = _decode_otlp_json(FIXTURE)
    titles = {d["info"]["title"] for d in _documents().values()}
    assert len(spans) == len(PUBLISHERS) + len(OBSERVED_CONSUMERS)
    by_service = {s.service_name: s for s in spans}
    assert set(by_service) == PUBLISHERS | OBSERVED_CONSUMERS
    assert set(by_service) <= titles  # AIP matches the declared Service name, not the service id
    for service, span in by_service.items():
        assert span.environment == ENVIRONMENT
        assert DAY_START <= span.start_time <= span.end_time < DAY_END
        assert span.attributes["messaging.system"] == "rabbitmq"
        assert span.attributes["messaging.destination.name"] == "Pitstop"
        assert "messaging.operation" not in span.attributes  # the legacy key is ignored by AIP
        if service in PUBLISHERS:
            assert span.span_kind == "PRODUCER"
            assert span.attributes["messaging.operation.type"] == "send"
            assert "messaging.destination.subscription.name" not in span.attributes
        else:
            assert span.span_kind == "CONSUMER"
            assert span.attributes["messaging.operation.type"] == "process"
            assert span.attributes["messaging.destination.subscription.name"] == QUEUES[service]
    # deliberate: the unobserved-is-not-unused boundary (PROVENANCE.md)
    assert "AuditlogService" not in by_service


def test_config_reads_only_the_overlay_and_sets_the_demo_environment():
    demo = load_config(DEMO_DIR / "config.yaml")
    assert [(d.id, d.root) for d in demo.sources.directories] == [
        ("pitstop-demo-overlay", Path("pitstop/overlay"))
    ]
    assert demo.sources.clusters == []
    assert demo.runtime_analysis.default_environment == ENVIRONMENT
    assert demo.import_.asyncapi is True
    assert demo.llm.enabled is False
    assert demo.telemetry.coverage.qualification_enabled is True


def test_provenance_pins_both_revisions_and_states_the_boundaries():
    text = (DEMO_DIR / "PROVENANCE.md").read_text()
    assert "306b5fbd0febceb6b0d0706f152a0520ca1a993a" in text
    [fork_commit] = re.findall(r"Fork baseline commit \| `([0-9a-f]{40})`", text)
    assert fork_commit != "306b5fbd0febceb6b0d0706f152a0520ca1a993a"
    assert "not yet committed" not in text
    for sentence in (
        "**authored, not captured**",
        "**operator-declared**",
        "no message payload or field",
        "`AuditlogService` has no receive span, deliberately",
    ):
        assert sentence in text, sentence


def test_pitstop_demo_files_are_pinned_and_invisible_to_the_demo_import():
    """The `demo` phase mounts all of `examples/`, so every demo file is pinned in SHA256SUMS. The
    discoverer only enumerates `<root>/<subdir>/<candidate>`, so no candidate filename sits at that
    depth (the overlay's `asyncapi.yaml` files are two levels deeper)."""
    on_disk = {
        p.relative_to(REPO).as_posix()
        for p in DEMO_DIR.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    pinned = {path for path in _sums() if path.startswith("examples/pitstop-demo/")}
    assert pinned == on_disk
    for path in pinned:
        parts = Path(path).parts
        assert not (len(parts) == 3 and parts[2] in CANDIDATE_FILENAMES), path


def test_demo_never_changes_the_bundled_examples_discovery():
    assert not [name for name in CANDIDATE_FILENAMES if (DEMO_DIR / name).exists()]
    [bundled] = load_config(REPO / "config.yaml").sources.directories
    outcome = FilesystemSourceDiscoverer(
        bundled.model_copy(update={"root": REPO / "examples"})
    ).discover()
    locators = [source.descriptor.locator for source in outcome.loaded_sources]
    assert len(locators) == 6
    assert not [locator for locator in locators if "pitstop-demo" in locator]
