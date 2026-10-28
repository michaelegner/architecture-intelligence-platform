"""v0.8 I4a: the operator's checks of what the agent applied (I4 spec §5, §6, §7 K7).

- config_checks.py: the I3 flow files (known good) pass P1a/P2/P3 and give their allow-lists and
  the I3 internal-topic names; each departure fails (an unset replication factor, a renaming policy,
  a topic mirrored both ways, a pattern allow-list, a file that is not dedicated-mode properties).
- helm_checks.py (K7 against the applied ConfigMaps): only kafka.brokers changes, nothing else.
- ground_truth.py: the hand-off read after the wave, on the I3 run's real broker-tool output, with
  the installed offset labelled agent-reported.
- e6_gate.py (I4b): every expected verdict says PASSED; a FAILED or a missing verdict fails it.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness/v08/i4"))

import config_checks
import e6_gate
import ground_truth
import helm_checks
from _i3 import checker

I3_ENV = REPO / "docs/specifications/0.8.0/i3-evidence/environment"
I3_RAW = REPO / "docs/specifications/0.8.0/i3-evidence/raw"
FLOWS = [I3_ENV / "mm2-flow-a.properties", I3_ENV / "mm2-flow-b.properties"]


def edited(tmp_path: Path, source: Path, drop: str = "", add: str = "") -> Path:
    lines = [
        line for line in source.read_text().splitlines() if not (drop and line.startswith(drop))
    ]
    path = tmp_path / source.name
    path.write_text("\n".join(lines + ([add] if add else [])) + "\n")
    return path


def test_i3_flows_pass_and_give_their_allow_lists():
    result = config_checks.check_static(FLOWS)
    assert result["result"] == "PASSED", result["problems"]
    assert {(f["source"], f["target"]): f["topics"] for f in result["allow_lists"]} == {
        ("redpanda", "kafka"): ["tenant.tenant.events"],
        ("kafka", "redpanda"): [
            "catalog.attribute.events",
            "catalog.category.events",
            "catalog.product.events",
        ],
    }


def test_derived_internal_topics_equal_the_i3_names():
    result = config_checks.check_static(FLOWS)
    for flow, pair in (("mm2-flow-a", "redpanda->kafka"), ("mm2-flow-b", "kafka->redpanda")):
        assert result["internal_topics"][pair] == {
            role: sorted(names) for role, names in checker.internal_topics(flow).items()
        }


def test_offset_syncs_on_the_target_are_named_after_the_source(tmp_path):
    """MirrorMaker 2 names the offset-syncs topic after the cluster that does not hold it; the I4b
    run's flows used `offset-syncs.topic.location = target` (S4, both broker listings)."""
    flow_a = edited(tmp_path, FLOWS[0], add="redpanda->kafka.offset-syncs.topic.location = target")
    topics = config_checks.check_static([flow_a, FLOWS[1]])["internal_topics"]["redpanda->kafka"]
    assert "mm2-offset-syncs.redpanda.internal" in topics["target"] and topics["source"] == []


@pytest.mark.parametrize(
    ("drop", "add", "problem"),
    [
        ("checkpoints.topic.replication.factor", "", "P1a"),
        ("replication.policy.class", "", "P2"),
        ("emit.checkpoints.enabled", "emit.checkpoints.enabled = false", "P2"),
        (
            "redpanda->kafka.topics",
            "redpanda->kafka.topics = tenant\\\\.tenant\\\\.events, catalog\\\\.product\\\\.events",
            "P3",
        ),
        ("redpanda->kafka.topics", "", "P3"),  # unset: MirrorMaker 2 mirrors every topic
    ],
)
def test_each_departure_fails(tmp_path, drop, add, problem):
    flow_a = edited(tmp_path, FLOWS[0], drop, add)
    result = config_checks.check_static([flow_a, FLOWS[1]])
    assert result["result"] == "FAILED"
    assert any(p.startswith(problem) for p in result["problems"]), result["problems"]


def test_not_dedicated_mode_stops(tmp_path):
    path = tmp_path / "connector.json"
    path.write_text('{"name": "x"}\n')
    with pytest.raises(SystemExit, match="record the verdicts by hand"):
        config_checks.check_static([path])


def test_p1b_on_listings(tmp_path):
    static = config_checks.check_static(FLOWS)
    topics = static["internal_topics"]["redpanda->kafka"]
    kafka = tmp_path / "kafka.txt"
    kafka.write_text(
        "".join(
            f"Topic: {t}\tTopicId: x\tPartitionCount: 1\tReplicationFactor: 1\n"
            for t in topics["target"]
        )
    )
    redpanda = tmp_path / "redpanda.txt"
    redpanda.write_text(
        "NAME PARTITIONS REPLICAS\n" + "".join(f"{t} 1 1\n" for t in topics["source"])
    )
    assert config_checks.check_p1b(static, "redpanda->kafka", kafka, redpanda)["result"] == "PASSED"
    redpanda.write_text("NAME PARTITIONS REPLICAS\n")
    assert config_checks.check_p1b(static, "redpanda->kafka", kafka, redpanda)["result"] == "FAILED"


# --- K7: the applied ConfigMaps --------------------------------------------------------------------

CONFIG = 'kafka:\n  brokers: "{brokers}"\n  group: x\nlog: info\n'


def write_state(root: Path, phase: str, brokers: str, extra: str = "", refs=("cm",)) -> None:
    for deployment in helm_checks.DEPLOYMENTS:
        directory = root / phase
        directory.mkdir(parents=True, exist_ok=True)
        names = [f"{deployment}-{ref}" for ref in refs]
        spec = {
            "spec": {
                "template": {
                    "spec": {"volumes": [{"name": n, "configMap": {"name": n}} for n in names]}
                }
            }
        }
        (directory / f"{deployment}.deployment.json").write_text(json.dumps(spec))
        for name in names:
            data = {"config.yaml": CONFIG.format(brokers=brokers) + extra}
            cm = {"metadata": {"name": name, "namespace": "dev"}, "data": data}
            (directory / f"configmap-{name}.json").write_text(json.dumps(cm))


def test_helm_only_the_broker_changes(tmp_path):
    write_state(tmp_path, "before", "redpanda:29092")
    write_state(tmp_path, "after", "kafka:29092")
    assert helm_checks.check(tmp_path)["result"] == "PASSED"


def test_helm_extra_env_var_fails(tmp_path):
    write_state(tmp_path, "before", "redpanda:29092")
    write_state(tmp_path, "after", "kafka:29092")
    path = tmp_path / "after" / f"{helm_checks.DEPLOYMENTS[0]}.deployment.json"
    spec = json.loads(path.read_text())
    spec["spec"]["template"]["spec"]["containers"] = [
        {"name": "app", "env": [{"name": "X", "value": "1"}]}
    ]
    path.write_text(json.dumps(spec))
    result = helm_checks.check(tmp_path)
    assert result["result"] == "FAILED" and any("pod spec" in p for p in result["problems"])


def test_helm_replicas_and_rollout_annotation_are_ignored(tmp_path):
    write_state(tmp_path, "before", "redpanda:29092")
    write_state(tmp_path, "after", "kafka:29092")
    path = tmp_path / "after" / f"{helm_checks.DEPLOYMENTS[1]}.deployment.json"
    spec = json.loads(path.read_text())
    spec["spec"]["replicas"] = 0
    spec["spec"]["template"]["metadata"] = {
        "annotations": {"kubectl.kubernetes.io/restartedAt": "t"}
    }
    path.write_text(json.dumps(spec))
    assert helm_checks.check(tmp_path)["result"] == "PASSED"


@pytest.mark.parametrize(
    ("after_brokers", "extra", "refs"),
    [
        ("kafka:29092", "debug: true\n", ("cm",)),  # an unrelated change too
        ("redpanda:29092", "", ("cm",)),  # the broker did not change
        ("kafka:29092", "", ("cm", "other")),  # the deployment references another ConfigMap
    ],
)
def test_helm_departures_fail(tmp_path, after_brokers, extra, refs):
    write_state(tmp_path, "before", "redpanda:29092")
    write_state(tmp_path, "after", after_brokers, extra, refs)
    assert helm_checks.check(tmp_path)["result"] == "FAILED"


# --- The hand-off after the wave -------------------------------------------------------------------


MOVED = ("ecommerce-catalog-service", "ecommerce-image-service")


def agent_reported(tmp_path: Path, c: int, groups=MOVED) -> Path:
    path = tmp_path / "agent.json"
    path.write_text(
        json.dumps(
            [
                {
                    "group": g,
                    "topic": "tenant.tenant.events",
                    "partition": 0,
                    "c": c,
                    "transcript": "execution line 1",
                }
                for g in groups
            ]
        )
    )
    return path


def handoff(tmp_path: Path, c: int, groups=MOVED) -> dict:
    return ground_truth.check_handoff_after(
        agent_reported(tmp_path, c, groups),
        I3_RAW / "06-source-groups.txt",
        I3_RAW / "06-checkpoints.txt",
        I3_RAW / "06-target-groups.txt",
        I3_RAW / "06-offset-syncs.txt",
    )


def test_handoff_on_the_i3_run(tmp_path):
    result = handoff(tmp_path, 1)
    assert result["result"] == "PASSED", result["entries"]
    entry = result["entries"][0]
    assert entry["c"]["source"].startswith("agent-reported")
    assert entry["a"]["value"] == 1 and entry["kafka_position_now"]["value"] == 1


def test_handoff_with_a_reported_offset_no_checkpoint_has(tmp_path):
    assert handoff(tmp_path, 0)["result"] == "FAILED"


def test_mm2_processes_in_both_shapes():
    """The flow as a container's command, through `docker exec`, and as the exec'd Java process."""
    top = (
        "COMMAND\n"
        "/bin/bash /opt/kafka/bin/connect-mirror-maker.sh /etc/mm2/flow-a.properties\n"
        "java -cp /opt/kafka/libs/* org.apache.kafka.connect.mirror.MirrorMaker /work/b.properties"
        " --clusters kafka\n"
        "/opt/kafka/bin/kafka-server-start.sh /opt/kafka/config/server.properties\n"
    )
    assert config_checks.mm2_properties(top) == ["/etc/mm2/flow-a.properties", "/work/b.properties"]
    assert config_checks.mm2_properties("COMMAND\n/etc/kafka/docker/run\n") == []
    # Docker 29 refuses `-eo args` without a PID column (I4b S4): `-eo pid,args`.
    with_pid = "PID   COMMAND\n92653 java -cp x org.apache.kafka.connect.mirror.MirrorMaker /mm2/mm2.properties\n"
    assert config_checks.mm2_properties(with_pid) == ["/mm2/mm2.properties"]


# --- Proof C ---------------------------------------------------------------------------------------


def test_proof_c_on_the_reference_and_a_departure():
    import proof_c

    expected = json.loads(proof_c.EXPECTED_AFTER.read_text())
    answer = {
        "data": {"rows": [{**r, "group_ids": [], "topic_id": "t"} for r in expected["rows"]]},
        "limitations": [{"code": c, "message": "m"} for c in expected["limitations"]],
    }
    recording = {"report_request": {"answer": answer}}
    assert proof_c.check(recording, expected)["result"] == "PASSED"
    answer["data"]["rows"][0]["status"] = "PROMISED_AND_OBSERVED"
    result = proof_c.check(recording, expected)
    assert result["result"] == "FAILED" and len(result["unexpected"]) == 1


@pytest.mark.parametrize(
    ("groups", "problem"),
    [
        (("ecommerce-catalog-service",), "missing"),  # Image omitted
        (
            ("ecommerce-catalog-service", "ecommerce-image-service", "ecommerce-image-service"),
            "duplicated",
        ),
    ],
)
def test_handoff_must_cover_both_moved_groups_exactly(tmp_path, groups, problem):
    """#651 owner review: a report that omits Image (or repeats a key) cannot pass."""
    result = handoff(tmp_path, 1, groups)
    assert result["result"] == "FAILED"
    assert result["coverage"][problem]


def e6_package(tmp_path: Path) -> tuple[Path, Path]:
    """A package with every verdict the gate expects, all PASSED."""
    pairs = [{"pair": "redpanda->kafka"}, {"pair": "kafka->redpanda"}]
    (tmp_path / "raw").mkdir()
    (tmp_path / "applied-mm2.json").write_text(json.dumps({"result": "PASSED", "pairs": pairs}))
    functional = tmp_path / "raw" / "FT.check.json"
    for path in e6_gate.expected(tmp_path, functional)[1:]:
        path.write_text('{"result": "PASSED"}')
    return tmp_path, functional


def test_e6_gate_passes_only_on_every_expected_verdict(tmp_path):
    package, functional = e6_package(tmp_path)
    assert e6_gate.gate(package, functional)["result"] == "PASSED"
    assert len(e6_gate.expected(package, functional)) == 12


def test_e6_gate_fails_on_a_failed_verdict(tmp_path):
    package, functional = e6_package(tmp_path)
    (package / "p1b-kafka-to-redpanda.json").write_text('{"result": "FAILED"}')
    result = e6_gate.gate(package, functional)
    assert result["result"] == "FAILED"
    assert result["problems"] == [f"{package}/p1b-kafka-to-redpanda.json: FAILED"]


def test_e6_gate_fails_on_a_missing_verdict(tmp_path):
    """I4b S4: a pair whose replication was never evaluated must not pass by absence."""
    package, functional = e6_package(tmp_path)
    (package / "raw" / "GT-kafka->redpanda-replication.check.json").unlink()
    result = e6_gate.gate(package, functional)
    assert result["result"] == "FAILED"
    assert result["problems"] == [
        f"{package}/raw/GT-kafka->redpanda-replication.check.json: MISSING"
    ]
