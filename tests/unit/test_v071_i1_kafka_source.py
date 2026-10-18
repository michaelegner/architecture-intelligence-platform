"""v0.7.1 I1.3: the Kafka consumer-state discoverer and adapter, with the graph replaced by an
injected declared-Topic resolver and a prior capture. Expected results come from the hand-authored
I1.1 vectors (`docs/specifications/0.7.1/i1-vectors/`), not from the production formulas."""

import copy
import json
from pathlib import Path

import pytest

from app.canonical.kafka_consumer_state import kafka_capture_evidence_id
from app.ingestion.kafka_consumer_state_adapter import KafkaConsumerStateSourceAdapter
from app.ingestion.kafka_consumer_state_discoverer import (
    KafkaConsumerStateSourceDiscoverer,
    PriorKafkaCapture,
)
from app.ingestion.orchestrator import run_kafka_consumer_state_discovery
from app.sources.kafka_consumer_state_loader import load_capture
from app.sources.model import DiagnosticCode, IngestionResult, KafkaConsumerStateSourceConfig
from app.sources.owner_ids import topic_owned_id

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.1/i1-vectors"
EXAMPLE = json.loads((VECTORS / "kafka-consumer-state-capture.example.json").read_text())
ATTACHMENTS = json.loads((VECTORS / "attachments.json").read_text())
REJECTIONS = {
    c["id"]: c for c in json.loads((VECTORS / "capture-rejections.json").read_text())["cases"]
}
IDS = json.loads((VECTORS / "ids.json").read_text())
BROKER, ENV = IDS["inputs"]["broker_id"], IDS["inputs"]["environment"]
DECLARED = ATTACHMENTS["declared_topics"]["topics"]
CANARY = "CANARY-KAFKA-NAME-77aa"


def _topic_id(name: str, broker: str = BROKER) -> str:
    return topic_owned_id(
        stable_broker_id=broker, normalized_namespace_or_empty="", exact_topic_address=name
    )


def _resolver(declared=DECLARED, broker: str = BROKER):
    ids = {_topic_id(name, broker) for name in declared}
    return lambda candidates: frozenset(set(candidates) & ids)


def _member(member_id: str, topic: str, host: str = "/10.0.0.7", client: str = "c1") -> dict:
    return {
        "member_id": member_id,
        "client_id": client,
        "host": host,
        "assignments": [{"topic": topic, "partitions": [0, 1, 2]}],
    }


def _capture(
    payment=("Empty", []), order=("Empty", []), *, environment: str = ENV, **extra
) -> dict:
    document = copy.deepcopy(EXAMPLE)
    document["environment"] = environment
    document["groups"] = [
        {"group_id": "order-service", "state": order[0], "members": order[1]},
        {"group_id": "payment-service", "state": payment[0], "members": payment[1]},
    ]
    document.update(extra)
    return document


def _config(root: Path, *, environment: str = ENV, source_id: str = "kafka-prod"):
    return KafkaConsumerStateSourceConfig(
        id=source_id,
        root=root,
        broker_id=BROKER,
        environment=environment,
        consumer_groups=["payment-service", "order-service"],
    )


def _run(tmp_path: Path, document: dict, **kwargs):
    environment = kwargs.pop("environment", ENV)
    root = tmp_path / f"root-{abs(hash(json.dumps(document, sort_keys=True)))}"
    root.mkdir(exist_ok=True)
    (root / "kafka-consumer-state.json").write_text(json.dumps(document))
    kwargs.setdefault("declared_topic_resolver", _resolver())
    return run_kafka_consumer_state_discovery(_config(root, environment=environment), **kwargs)


def _outcome(run):
    [source] = run.source_outcomes.values()
    return source.outcome


def _attachments(run) -> set[tuple[str, str]]:
    model = run.merged_model
    groups = {g.id: g.group_id for g in model.kafka_consumer_groups}
    names = {_topic_id(name): name for name in [*DECLARED, "payments.failed"]}
    return {(groups[a.consumer_id], names[a.topic_id]) for a in model.kafka_consumer_attachments}


def _case(case_id: str) -> dict:
    return next(c for c in ATTACHMENTS["capture_cases"] if c["id"] == case_id)


def _expected(case_id: str) -> set[tuple[str, str]]:
    return {(a["group"], a["topic"]) for a in _case(case_id)["expected_attachments"]}


# ---- attachment cases A01-A08 ---------------------------------------------------------------


def test_a01_live_member_on_declared_topic(tmp_path: Path) -> None:
    run = _run(tmp_path, _capture(payment=("Stable", [_member("m1", "orders.created")])))
    assert _outcome(run).result is IngestionResult.ACCEPTED
    assert run.commit_eligible
    assert _attachments(run) == _expected("A01")


def test_a02_several_members_one_group_one_topic_one_identity(tmp_path: Path) -> None:
    members = [_member("m1", "payments.completed"), _member("m2", "payments.completed")]
    run = _run(tmp_path, _capture(order=("Stable", members)))
    assert _attachments(run) == _expected("A02")
    [attachment] = run.merged_model.kafka_consumer_attachments
    assert json.loads(attachment.support_json) == {
        "member_count": 2, "member_partitions": [[0, 1, 2], [0, 1, 2]],
    }  # fmt: skip
    assert len(run.merged_model.kafka_consumer_groups) == 2  # still one per allow-listed group


def test_a03_one_group_on_several_topics(tmp_path: Path) -> None:
    members = [_member("m1", "orders.created"), _member("m2", "payments.completed")]
    run = _run(tmp_path, _capture(order=("Stable", members)))
    assert _attachments(run) == _expected("A03")


@pytest.mark.parametrize("case_id,state", [("A04", "Empty"), ("A05", "Dead")])
def test_a04_a05_empty_and_dead_groups_have_zero_attachment_but_a_group_row(
    tmp_path: Path, case_id: str, state: str
) -> None:
    run = _run(tmp_path, _capture(payment=(state, [])))
    assert _attachments(run) == _expected(case_id) == set()
    states = json.loads(run.merged_model.kafka_capture_evidence[0].group_states_json)
    assert states["payment-service"] == state  # explicit zero live attachment, not an absence


def test_a06_undeclared_topic_is_a_diagnostic_and_never_minted(tmp_path: Path) -> None:
    run = _run(tmp_path, _capture(payment=("Stable", [_member("m1", "payments.failed")])))
    outcome = _outcome(run)
    assert outcome.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.KAFKA_TOPIC_NOT_DECLARED]
    assert "payments.failed" not in repr(outcome.diagnostics)
    assert _attachments(run) == _expected("A06") == set()
    assert not run.merged_model.topics and not run.merged_model.subscriptions


def test_a07_member_client_and_host_changes_keep_identities(tmp_path: Path) -> None:
    first = _run(tmp_path, _capture(payment=("Stable", [_member("m1", "orders.created")])))
    second = _run(
        tmp_path,
        _capture(payment=("Stable", [_member("m9", "orders.created", "/10.9.9.9", "other")])),
    )
    assert _attachments(first) == _attachments(second) == _expected("A07")
    assert [a.id for a in first.merged_model.kafka_consumer_attachments] == [
        a.id for a in second.merged_model.kafka_consumer_attachments
    ]


def test_a08_same_group_id_in_another_environment_is_a_distinct_identity(tmp_path: Path) -> None:
    members = [_member("m1", "orders.created")]
    prod = _run(tmp_path, _capture(payment=("Stable", members)))
    staging = _run(
        tmp_path,
        _capture(payment=("Stable", members), environment="staging"),
        environment="staging",
    )
    assert _attachments(staging) == _expected("A08")
    assert {g.id for g in prod.merged_model.kafka_consumer_groups}.isdisjoint(
        {g.id for g in staging.merged_model.kafka_consumer_groups}
    )


def test_every_attachment_case_is_covered() -> None:
    assert {c["id"] for c in ATTACHMENTS["capture_cases"]} == {f"A0{n}" for n in range(1, 9)}


# ---- ordering and duplicates (R12, R14, R15) and lifecycle at source level ------------------


def _prior(run) -> PriorKafkaCapture:
    evidence = run.merged_model.kafka_capture_evidence[0]
    return PriorKafkaCapture(evidence.captured_at, evidence.capture_content_sha256)


def test_identical_replay_has_an_identical_digest_l01(tmp_path: Path) -> None:
    document = _capture(payment=("Stable", [_member("m1", "orders.created")]))
    first = _run(tmp_path, document)
    again = _run(tmp_path, document, prior_capture=_prior(first))
    assert _outcome(again).result is IngestionResult.ACCEPTED
    assert _outcome(first).semantic_input_digest == _outcome(again).semantic_input_digest


def test_a_later_capture_with_the_same_attachments_refreshes_t_only_l02(tmp_path: Path) -> None:
    members = [_member("m1", "orders.created")]
    first = _run(tmp_path, _capture(payment=("Stable", members)))
    later = _run(
        tmp_path,
        _capture(payment=("Stable", members), captured_at="2026-10-16T10:00:00Z"),
        prior_capture=_prior(first),
    )
    assert _outcome(later).result is IngestionResult.ACCEPTED
    assert [a.id for a in first.merged_model.kafka_consumer_attachments] == [
        a.id for a in later.merged_model.kafka_consumer_attachments
    ]
    assert later.merged_model.kafka_capture_evidence[0].captured_at == "2026-10-16T10:00:00Z"
    assert _outcome(first).semantic_input_digest != _outcome(later).semantic_input_digest


def test_r14_an_older_capture_is_rejected_stale(tmp_path: Path) -> None:
    first = _run(tmp_path, _capture(captured_at="2026-10-16T10:00:00Z"))
    older = _run(tmp_path, _capture(), prior_capture=_prior(first))
    outcome = _outcome(older)
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert outcome.diagnostics[0].code.value == REJECTIONS["R14"]["reason"]
    assert not older.commit_eligible


def test_r15_same_instant_different_content_is_rejected_conflict(tmp_path: Path) -> None:
    first = _run(tmp_path, _capture())
    changed = _capture(payment=("Stable", [_member("m1", "orders.created")]))
    run = _run(tmp_path, changed, prior_capture=_prior(first))
    assert _outcome(run).result is IngestionResult.REJECTED_CONFLICT
    assert _outcome(run).diagnostics[0].code.value == REJECTIONS["R15"]["reason"]


def test_r12_duplicate_registration_is_rejected_conflict(tmp_path: Path) -> None:
    run = _run(tmp_path, _capture(), duplicate_registration=True)
    outcome = _outcome(run)
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert outcome.diagnostics[0].code.value == REJECTIONS["R12"]["reason"]
    assert not run.commit_eligible


# ---- rejections reach the per-source result with fixed text ---------------------------------


@pytest.mark.parametrize(
    "mutation,code,result",
    [
        (lambda d: d.update(broker_id="kafka:other"), "KAFKA_BROKER_MISMATCH", "REJECTED_INVALID"),
        (lambda d: d.update(complete=False), "KAFKA_CAPTURE_INCOMPLETE", "REJECTED_INVALID"),
        (lambda d: d.update(schema="x/2"), "KAFKA_UNSUPPORTED_SCHEMA", "REJECTED_UNSUPPORTED"),
        (
            lambda d: d["groups"][1].update(state="PreparingRebalance"),
            "KAFKA_STATE_NOT_STABLE",
            "REJECTED_INVALID",
        ),
        (lambda d: d["groups"].pop(), "KAFKA_GROUP_NOT_DESCRIBED", "REJECTED_INVALID"),
        (lambda d: d.update(tool_version=None), "KAFKA_CAPTURE_INVALID", "REJECTED_INVALID"),
    ],
)
def test_rejected_captures_map_to_their_result_and_commit_nothing(
    tmp_path: Path, mutation, code: str, result: str
) -> None:
    document = _capture()
    mutation(document)
    run = _run(tmp_path, document)
    outcome = _outcome(run)
    assert outcome.result.value == result
    assert outcome.diagnostics[0].code.value == code
    assert not run.commit_eligible
    assert outcome.model.kafka_consumer_groups == []


def test_diagnostics_never_echo_a_name_or_value(tmp_path: Path) -> None:
    document = _capture()
    document["groups"][1][f"password-{CANARY}"] = "x"
    document["groups"][0]["members"] = [_member(f"m-{CANARY}", "orders.created")]
    run = _run(tmp_path, document)
    assert CANARY not in repr(_outcome(run))
    assert CANARY not in repr(run.diagnostics)
    undeclared = _capture(payment=("Stable", [_member(f"m-{CANARY}", f"topic-{CANARY}")]))
    assert CANARY not in repr(_outcome(_run(tmp_path, undeclared)))


def test_an_unconfigured_root_is_not_a_source(tmp_path: Path) -> None:
    run = run_kafka_consumer_state_discovery(_config(tmp_path / "missing"))
    assert run.source_outcomes == {}
    assert not run.commit_eligible


def test_the_resolver_sees_only_candidate_topic_ids(tmp_path: Path) -> None:
    seen: list[frozenset[str]] = []

    def resolver(candidates):
        seen.append(frozenset(candidates))
        return frozenset()

    members = [_member("m1", "orders.created"), _member("m2", "payments.completed")]
    _run(tmp_path, _capture(order=("Stable", members)), declared_topic_resolver=resolver)
    assert seen == [frozenset({_topic_id("orders.created"), _topic_id("payments.completed")})]


def test_loader_and_discoverer_agree_on_the_example_capture(tmp_path: Path) -> None:
    document = copy.deepcopy(EXAMPLE)
    run = _run(
        tmp_path,
        document,
        declared_topic_resolver=_resolver([*DECLARED, "payments.failed"]),
    )
    assert _outcome(run).result is IngestionResult.ACCEPTED
    evidence = run.merged_model.kafka_capture_evidence[0]
    root = next(p for p in tmp_path.iterdir())
    loaded = load_capture(_config(root))
    assert evidence.capture_content_sha256 == loaded.content_sha256  # type: ignore[union-attr]
    assert evidence.id == kafka_capture_evidence_id(next(iter(run.source_outcomes)))


def test_client_supplied_member_text_never_enters_aip_state(tmp_path: Path) -> None:
    """Review of #583 (I1 §4, §12): member ids, client ids and hosts are client-supplied text that
    may carry a secret no shape check can recognize, so the carriers keep only the member count and
    partitions."""
    secret = "CANARY-UNKNOWN-SECRET-3f9c"
    member = _member(f"m-{secret}", "orders.created", host=f"/{secret}", client=f"c-{secret}")
    run = _run(tmp_path, _capture(payment=("Stable", [member])))
    assert _outcome(run).result is IngestionResult.ACCEPTED
    assert secret not in run.merged_model.model_dump_json()
    [attachment] = run.merged_model.kafka_consumer_attachments
    assert json.loads(attachment.support_json) == {
        "member_count": 1, "member_partitions": [[0, 1, 2]],
    }  # fmt: skip


def test_the_adapter_supports_by_schema_string_not_by_filename(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "kafka-consumer-state.json").write_text(json.dumps(_capture()))
    discoverer = KafkaConsumerStateSourceDiscoverer(
        _config(root), declared_topic_resolver=_resolver()
    )
    [loaded] = discoverer.discover().loaded_sources
    adapter = KafkaConsumerStateSourceAdapter()
    assert adapter.supports(loaded)
    other_schema = copy.deepcopy(loaded.document)
    other_schema["capture"]["schema"] = "aip-kafka-consumer-state/2"
    assert not adapter.supports(loaded.model_copy(update={"document": other_schema}))
