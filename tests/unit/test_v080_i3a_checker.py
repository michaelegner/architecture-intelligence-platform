"""v0.8 I3a: the I3 checker on hand-made broker-tool outputs (I3 spec §4-§5).

Every pass case and every stop case, multi-partition results, missing data, mismatched group, topic
or partition identities, and PENDING before the deadline versus FAILED after it.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("i3_checker", REPO / "harness/v08/i3/checker.py")
assert _spec is not None and _spec.loader is not None
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

ENV = REPO / "docs/specifications/0.8.0/i3-evidence/environment"
FLOWS = [ENV / f"{name}.properties" for name in ("mm2-flow-a", "mm2-flow-b", "mm2-probe")]
TENANT = "tenant.tenant.events"


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def rpk_group(group: str, state: str, rows: list[tuple[str, int, int | None, int]]) -> str:
    lines = [f"GROUP        {group}", "COORDINATOR  0", f"STATE        {state}", ""]
    lines.append(
        "TOPIC  PARTITION  CURRENT-OFFSET  LOG-START-OFFSET  LOG-END-OFFSET  LAG  MEMBER-ID"
    )
    for topic, partition, current, end in rows:
        cur = "-" if current is None else str(current)
        lag = "-" if current is None else str(end - current)
        lines.append(f"{topic}  {partition}  {cur}  0  {end}  {lag}  m-1")
    return "\n".join(lines) + "\n"


def kafka_groups(rows: list[tuple[str, str, int, int | None, int]]) -> str:
    lines = [
        "GROUP  TOPIC  PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG  CONSUMER-ID  HOST  CLIENT-ID"
    ]
    for group, topic, partition, current, end in rows:
        cur = "-" if current is None else str(current)
        lag = "-" if current is None else str(end - current)
        lines.append(f"{group}  {topic}  {partition}  {cur}  {end}  {lag}  -  -  -")
    return "\n".join(lines) + "\n"


def offsets_dump(entries: list[tuple[str, int, int]]) -> str:
    key = '["MirrorSourceConnector",{{"cluster":"redpanda","partition":{p},"topic":"{t}"}}]'
    return "".join(f'{key.format(p=p, t=t)}\t{{"offset":{o}}}\n' for t, p, o in entries)


def rpk_end(topic: str, ends: list[int]) -> str:
    lines = [
        f"# topic: {topic}",
        "PARTITION  LEADER  EPOCH  REPLICAS  LOG-START-OFFSET  HIGH-WATERMARK",
    ]
    lines += [f"{p}  0  1  [0]  0  {end}" for p, end in enumerate(ends)]
    return "\n".join(lines) + "\n"


def checkpoint(group: str, topic: str, partition: int, up: int, down: int) -> str:
    return (
        f"Checkpoint{{consumerGroupId={group}, topicPartition={topic}-{partition}, "
        f"upstreamOffset={up}, downstreamOffset={down}, metadata=}}\n"
    )


def sync(topic: str, partition: int, up: int, down: int) -> str:
    return f"OffsetSync{{topicPartition={topic}-{partition}, upstreamOffset={up}, downstreamOffset={down}}}\n"


# --- Preflight -------------------------------------------------------------------------------------


def test_p1a_passes_on_the_committed_flow_files() -> None:
    result = checker.check_p1a(FLOWS)
    assert result["result"] == "PASSED", result["problems"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("replication.factor", "2"),  # the Kafka 4.1 default would fail on a single node
        ("offset.storage.topic", "mm2-offsets.redpanda.internal"),
        ("sync.group.offsets.interval.seconds", "60"),
        ("emit.heartbeats.enabled", "true"),
    ],
)
def test_p1a_fails_when_a_required_setting_differs(tmp_path, key, value) -> None:
    lines = [
        f"{key} = {value}" if line.split("=")[0].strip() == key else line
        for line in FLOWS[0].read_text().splitlines()
    ]
    path = write(tmp_path, "mm2-flow-a.properties", "\n".join(lines) + "\n")
    result = checker.check_p1a([path])
    assert result["result"] == "FAILED" and any(key in p for p in result["problems"])


def test_p3_detects_an_overlap(tmp_path) -> None:
    assert checker.check_p3(FLOWS[0], FLOWS[1])["result"] == "PASSED"
    b = (
        FLOWS[1]
        .read_text()
        .replace(
            r"catalog\\.attribute\\.events",
            r"catalog\\.attribute\\.events, tenant\\.tenant\\.events",
        )
    )
    result = checker.check_p3(FLOWS[0], write(tmp_path, "mm2-flow-b.properties", b))
    assert result["result"] == "FAILED" and result["overlap"] == [TENANT]


def test_p1b_finds_missing_and_wrong_rf_topics(tmp_path) -> None:
    target = write(
        tmp_path,
        "t.txt",
        "".join(
            f"Topic: {name}\tTopicId: x\tPartitionCount: 1\tReplicationFactor: {rf}\tConfigs:\n"
            for name, rf in (
                ("mm2-flow-a-configs", 1),
                ("mm2-flow-a-offsets", 1),
                ("mm2-flow-a-status", 3),
            )
        ),
    )
    source = write(
        tmp_path, "s.txt", "NAME  PARTITIONS  REPLICAS\nmm2-offset-syncs.kafka.internal  1  1\n"
    )
    result = checker.check_p1b("mm2-flow-a", target, source, "kafka", 0, 40)
    assert result["result"] == "FAILED"  # a wrong RF fails at once, even before the deadline
    assert any("mm2-flow-a-status" in p and "RF 3" in p for p in result["problems"])
    assert any("redpanda.checkpoints.internal" in p and "missing" in p for p in result["problems"])


def test_p1b_missing_topics_are_pending_until_the_deadline(tmp_path) -> None:
    def kafka_listing(names: list[str]) -> str:
        return "".join(
            f"Topic: {n}\tTopicId: x\tPartitionCount: 1\tReplicationFactor: 1\tConfigs:\n"
            for n in names
        )

    some = ["mm2-flow-a-configs", "mm2-flow-a-offsets"]
    target = write(tmp_path, "t.txt", kafka_listing(some))
    source = write(tmp_path, "s.txt", "NAME  PARTITIONS  REPLICAS\n")
    assert checker.check_p1b("mm2-flow-a", target, source, "kafka", 10, 40)["result"] == "PENDING"
    assert checker.check_p1b("mm2-flow-a", target, source, "kafka", 40, 40)["result"] == "FAILED"
    full = [*some, "mm2-flow-a-status", "redpanda.checkpoints.internal"]
    target = write(tmp_path, "t2.txt", kafka_listing(full))
    source = write(
        tmp_path, "s2.txt", "NAME  PARTITIONS  REPLICAS\nmm2-offset-syncs.kafka.internal  1  1\n"
    )
    assert checker.check_p1b("mm2-flow-a", target, source, "kafka", 10, 40)["result"] == "PASSED"


# --- Replication and lag ------------------------------------------------------------------------------


def test_replication_multi_partition_pass_pending_and_failed(tmp_path) -> None:
    end = write(tmp_path, "end.txt", rpk_end(TENANT, [5, 0, 3]))
    behind = write(tmp_path, "o1.txt", offsets_dump([(TENANT, 0, 4), (TENANT, 2, 1)]))
    caught = write(
        tmp_path, "o2.txt", offsets_dump([(TENANT, 0, 1), (TENANT, 0, 4), (TENANT, 2, 2)])
    )

    assert checker.check_replication(caught, end, "rpk", [TENANT], 0, 40)["result"] == "PASSED"
    pending = checker.check_replication(behind, end, "rpk", [TENANT], 5, 40)
    assert pending["result"] == "PENDING"
    assert [p["caught_up"] for p in pending["partitions"]] == [True, True, False]
    assert checker.check_replication(behind, end, "rpk", [TENANT], 40, 40)["result"] == "FAILED"


def test_replication_missing_topic_is_a_failure(tmp_path) -> None:
    end = write(tmp_path, "end.txt", "catalog.product.events:0:7\n")
    offsets = write(tmp_path, "o.txt", offsets_dump([("catalog.product.events", 0, 6)]))
    result = checker.check_replication(
        offsets, end, "kafka", ["catalog.product.events", "catalog.category.events"], 0, 40
    )
    assert result["result"] == "FAILED" and result["missing_topics"] == ["catalog.category.events"]


def test_lag_is_per_group_and_topic(tmp_path) -> None:
    text = rpk_group("g1", "Stable", [(TENANT, 0, 5, 5), (TENANT, 1, 2, 3)]) + rpk_group(
        "g2", "Stable", [(TENANT, 0, 5, 5)]
    )
    describe = write(tmp_path, "d.txt", text)
    assert checker.check_lag(describe, "rpk", "g2", [TENANT], 0, 40)["result"] == "PASSED"
    assert checker.check_lag(describe, "rpk", "g1", [TENANT], 0, 40)["result"] == "PENDING"
    assert checker.check_lag(describe, "rpk", "g1", [TENANT], 40, 40)["result"] == "FAILED"
    # Another group's caught-up rows never satisfy the named group.
    assert checker.check_lag(describe, "rpk", "g3", [TENANT], 40, 40)["result"] == "FAILED"


def test_state_accepts_only_the_allowed_readings(tmp_path) -> None:
    text = (
        rpk_group("catalog", "Empty", [])
        + rpk_group("image", "Dead", [])
        + rpk_group("query", "Stable", [])
    )
    describe = write(tmp_path, "d.txt", text)
    assert (
        checker.check_state(describe, "rpk", ["catalog", "image"], ["Empty", "Dead"])["result"]
        == "PASSED"
    )
    result = checker.check_state(describe, "rpk", ["catalog", "query"], ["Empty", "Dead"])
    assert result["result"] == "FAILED" and result["not_allowed"] == ["query"]


def test_state_is_pending_before_the_deadline_and_missing_groups_fail_at_once(tmp_path) -> None:
    describe = write(tmp_path, "d.txt", rpk_group("catalog", "Stable", []))
    pending = checker.check_state(describe, "rpk", ["catalog"], ["Empty", "Dead"], 10, 40)
    assert pending["result"] == "PENDING"
    late = checker.check_state(describe, "rpk", ["catalog"], ["Empty", "Dead"], 40, 40)
    assert late["result"] == "FAILED"
    missing = checker.check_state(describe, "rpk", ["image"], ["Empty", "Dead"], 10, 40)
    assert missing["result"] == "FAILED"


# --- Hand-off and replay amount ------------------------------------------------------------------------


def _handoff(tmp_path, *, source, cps, target, syncs, elapsed=0, deadline=40, groups=("g",)):
    return checker.check_handoff(
        write(tmp_path, "src.txt", source),
        write(tmp_path, "cp.txt", cps),
        write(tmp_path, "tgt.txt", target),
        write(tmp_path, "sync.txt", syncs),
        list(groups),
        TENANT,
        elapsed,
        deadline,
    )


def test_handoff_passes_with_a_measured_replay_amount(tmp_path) -> None:
    result = _handoff(
        tmp_path,
        source=rpk_group("g", "Empty", [(TENANT, 0, 10, 10), (TENANT, 1, 4, 4)]),
        cps=checkpoint("g", TENANT, 0, 10, 8) + checkpoint("g", TENANT, 1, 4, 4),
        target=kafka_groups([("g", TENANT, 0, 8, 10), ("g", TENANT, 1, 4, 4)]),
        syncs=sync(TENANT, 0, 10, 9) + sync(TENANT, 1, 4, 4),
    )
    assert result["result"] == "PASSED"
    replays = [e["replay"] for e in result["entries"]]
    assert replays == [{"kind": "MEASURED", "records": 1}, {"kind": "MEASURED", "records": 0}]


def test_replay_upper_estimate_and_no_bound(tmp_path) -> None:
    assert checker.replay_amount(10, 7, [(5, 5), (12, 12)]) == {
        "kind": "UPPER_ESTIMATE",
        "records": 5,
    }
    assert checker.replay_amount(10, 7, [(5, 5)])["kind"] == "NO_BOUND"
    assert checker.replay_amount(10, None, [(10, 10)])["kind"] == "NO_BOUND"


def test_a_checkpoint_for_another_group_or_partition_never_satisfies_the_rule(tmp_path) -> None:
    result = _handoff(
        tmp_path,
        source=rpk_group("g", "Empty", [(TENANT, 0, 10, 10)]),
        cps=checkpoint("other", TENANT, 0, 10, 10) + checkpoint("g", TENANT, 1, 10, 10),
        target=kafka_groups([("g", TENANT, 0, 10, 10)]),
        syncs=sync(TENANT, 0, 10, 10),
        elapsed=40,
    )
    assert result["result"] == "FAILED" and result["entries"][0]["checkpoint"] is None


def test_handoff_is_pending_then_failed_while_the_offset_is_not_installed(tmp_path) -> None:
    kwargs = {
        "source": rpk_group("g", "Empty", [(TENANT, 0, 10, 10)]),
        "cps": checkpoint("g", TENANT, 0, 10, 10),
        "target": kafka_groups([]),
        "syncs": sync(TENANT, 0, 10, 10),
    }
    assert _handoff(tmp_path, elapsed=5, **kwargs)["result"] == "PENDING"
    assert _handoff(tmp_path, elapsed=40, **kwargs)["result"] == "FAILED"


def test_an_installed_offset_that_differs_from_the_checkpoint_fails_at_once(tmp_path) -> None:
    result = _handoff(
        tmp_path,
        source=rpk_group("g", "Empty", [(TENANT, 0, 10, 10)]),
        cps=checkpoint("g", TENANT, 0, 10, 10),
        target=kafka_groups([("g", TENANT, 0, 12, 12)]),
        syncs=sync(TENANT, 0, 10, 10),
        elapsed=0,
    )
    assert result["result"] == "FAILED"


def test_a_group_without_a_source_offset_fails(tmp_path) -> None:
    result = _handoff(
        tmp_path,
        source=rpk_group("g", "Empty", [(TENANT, 0, 10, 10)]),
        cps=checkpoint("g", TENANT, 0, 10, 10),
        target=kafka_groups([("g", TENANT, 0, 10, 10)]),
        syncs="",
        groups=("g", "missing"),
    )
    assert result["result"] == "FAILED"


def test_collect_is_deterministic(tmp_path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in ("06-handoff", "02-replication"):
        (raw / f"{name}.check.json").write_text(json.dumps({"kind": name, "result": "PASSED"}))
    first = checker.collect(raw)
    assert [c["id"] for c in first["checks"]] == ["02-replication", "06-handoff"]
    assert first == checker.collect(raw)


def test_the_cli_exit_codes_follow_the_verdict(tmp_path) -> None:
    end = write(tmp_path, "end.txt", rpk_end(TENANT, [5]))
    offsets = write(tmp_path, "o.txt", offsets_dump([(TENANT, 0, 1)]))
    base = [
        "replication",
        "--offsets",
        str(offsets),
        "--source-end",
        str(end),
        "--format",
        "rpk",
        "--topic",
        TENANT,
        "--deadline",
        "40",
        "--out",
        str(tmp_path / "v.json"),
    ]
    assert checker.main([*base, "--elapsed", "0"]) == 3
    assert checker.main([*base, "--elapsed", "40"]) == 2


def test_kafka_state_of_an_empty_group_with_a_blank_strategy_is_pending(tmp_path) -> None:
    text = (
        "GROUP                     COORDINATOR (ID)       ASSIGNMENT-STRATEGY  STATE   #MEMBERS\n"
        "ecommerce-catalog-service kafka:29092 (1)                             Empty   0\n"
        "ecommerce-image-service   kafka:29092 (1)        cooperative-sticky   Stable  1\n"
    )
    describe = write(tmp_path, "k.txt", text)
    groups = ["ecommerce-catalog-service", "ecommerce-image-service"]
    pending = checker.check_state(describe, "kafka", groups, ["Stable"], 10, 120)
    assert pending["result"] == "PENDING"
    assert pending["states"]["ecommerce-catalog-service"] == "Empty"


def test_kafka_state_describe_is_parsed(tmp_path) -> None:
    text = (
        "GROUP                     COORDINATOR (ID)       ASSIGNMENT-STRATEGY  STATE   #MEMBERS\n"
        "ecommerce-catalog-service kafka:29092 (1)        cooperative-sticky   Stable  1\n"
        "ecommerce-image-service   kafka:29092 (1)        cooperative-sticky   Stable  1\n"
    )
    describe = write(tmp_path, "k.txt", text)
    result = checker.check_state(
        describe, "kafka", ["ecommerce-catalog-service", "ecommerce-image-service"], ["Stable"]
    )
    assert result["result"] == "PASSED"


# --- Step 8 ConfigMap identity -------------------------------------------------------------------------


def _cm(name: str, config: str) -> str:
    return json.dumps(
        {"metadata": {"name": name, "namespace": "dev"}, "data": {"config.yaml": config}}
    )


CONFIG = 'app:\n  kafka:\n    brokers: "redpanda:29092"\n    group: x\n'


def test_configmap_passes_only_for_the_broker_line_on_the_same_configmap(tmp_path) -> None:
    live = write(tmp_path, "live.json", _cm("ecommerce-catalog-service", CONFIG))
    ok = write(
        tmp_path, "ok.json", _cm("ecommerce-catalog-service", CONFIG.replace("redpanda", "kafka"))
    )
    assert checker.check_configmap(live, ok)["result"] == "PASSED"
    extra = CONFIG.replace("redpanda", "kafka").replace("group: x", "group: y")
    assert (
        checker.check_configmap(
            live, write(tmp_path, "x.json", _cm("ecommerce-catalog-service", extra))
        )["result"]
        == "FAILED"
    )
    other = write(tmp_path, "o.json", _cm("other", CONFIG.replace("redpanda", "kafka")))
    assert checker.check_configmap(live, other)["result"] == "FAILED"
    unchanged = write(tmp_path, "u.json", _cm("ecommerce-catalog-service", CONFIG))
    assert checker.check_configmap(live, unchanged)["result"] == "FAILED"
    assert (
        checker.check_configmap(live, write(tmp_path, "bad.json", "not json"))["result"] == "FAILED"
    )


def test_p1a_rejects_a_bare_flush_interval_that_never_reaches_the_worker(tmp_path) -> None:
    for flow in ("mm2-flow-a", "mm2-flow-b", "mm2-probe"):
        target = checker.WORKER_STATE[flow][1]
        text = (ENV / f"{flow}.properties").read_text()
        bare = text.replace(f"{target}.offset.flush.interval.ms", "offset.flush.interval.ms")
        path = tmp_path / f"{flow}.properties"
        path.write_text(bare)
        result = checker.check_p1a([path])
        assert result["result"] == "FAILED"
        assert any("bare offset.flush.interval.ms" in p for p in result["problems"])
