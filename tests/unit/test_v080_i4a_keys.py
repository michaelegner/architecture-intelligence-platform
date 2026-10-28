"""v0.8 I4a: the frozen plan answer key and task card (I4 spec §3, §4.3, E1).

The digests match; every expected row of the key is a C1 row with the stated crossing; the task card
gives no part of the answer (the leak guard, each rule proven by a violation); the plan format the
tools validate against is the one embedded in the card.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs/specifications/0.8.0"
EVIDENCE = SPEC / "i4-evidence"
sys.path.insert(0, str(REPO / "harness/v08/i4"))

import plan_format

TOPICS = (
    "tenant.tenant.events",
    "catalog.product.events",
    "catalog.category.events",
    "catalog.attribute.events",
)


def _digest_file(name: str) -> str:
    return (EVIDENCE / f"{name.rsplit('.', 1)[0]}.sha256").read_text().split()[0]


@pytest.mark.parametrize("name", ["plan-key.json", "task-card.md"])
def test_frozen_digests_match(name):
    assert hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest() == _digest_file(name)


def test_proof_c_reference_is_pinned():
    expected = SPEC / "i3-evidence/expected-after.json"
    pinned = (SPEC / "i3-evidence/expected-after.sha256").read_text().split()[0]
    assert plan_format.EXPECTED_AFTER_SHA256 == pinned
    assert hashlib.sha256(expected.read_bytes()).hexdigest() == pinned


def test_key_items_and_kinds():
    key = plan_format.load_key()
    kinds = {item["id"]: item["kind"] for item in key["items"]}
    assert kinds == {
        "K1": "binding",
        "K2": "binding",
        "K3": "binding",
        "K4": "binding",
        "K5": "mechanism",
        "K6": "mechanism",
        "K7": "mechanism",
        "K8": "mechanism",
    }
    k8 = next(item for item in key["items"] if item["id"] == "K8")
    assert [s["id"] for s in k8["sub_checks"]] == [f"K8.{n}" for n in range(1, 10)]


def test_expected_rows_are_c1_crossing_rows():
    c1 = json.loads((SPEC / "i2-vectors/c1-expected.json").read_text())
    rows = {plan_format.row_key(r): r for r in c1["rows"]}
    for item in plan_format.load_key()["items"]:
        for expected in item.get("expected_rows", []):
            row = rows[plan_format.row_key(expected)]
            assert row["crossing"] == expected["crossing"]
            assert expected["topic_name"] == item["topic"]


def test_undeclared_items_rest_on_undeclared_rows_only():
    """§3.1: K1, K3 and K4 rest on undeclared rows only; K2 on a promised row."""
    c1 = json.loads((SPEC / "i2-vectors/c1-expected.json").read_text())
    rows = {plan_format.row_key(r): r for r in c1["rows"]}
    key = {item["id"]: item for item in plan_format.load_key()["items"]}
    for item_id in ("K1", "K3", "K4"):
        assert all(
            rows[plan_format.row_key(r)].get("reason") == "PROMISE_COVERAGE_MISSING"
            for r in key[item_id]["expected_rows"]
        )
    assert (
        rows[plan_format.row_key(key["K2"]["expected_rows"][0])]["status"]
        == "PROMISED_AND_OBSERVED"
    )


# --- Task-card leak guard (§4.3: no topic list, no direction, no step list, no check kinds) ---------

LEAKS = {
    "topic name": re.compile("|".join(re.escape(t) for t in TOPICS)),
    "direction as a broker pair": re.compile(
        r"\b(redpanda|kafka)\s*(→|->|to)\s*(redpanda|kafka)\b", re.IGNORECASE
    ),
    "numbered step list": re.compile(r"^\s*(\d+[.)]|step\s+\d)", re.IGNORECASE | re.MULTILINE),
    "check kind": re.compile(
        r"\b(caught up|lag|checkpoints?|hand-?off|flow [AB]|offsets?|drain(ed)?)\b", re.IGNORECASE
    ),
}


def leaks(text: str) -> list[str]:
    return [name for name, pattern in LEAKS.items() if pattern.search(text)]


def test_task_card_gives_no_part_of_the_answer():
    assert leaks((EVIDENCE / "task-card.md").read_text()) == []


@pytest.mark.parametrize(
    ("violation", "rule"),
    [
        ("Mirror tenant.tenant.events.", "topic name"),
        ("Bridge redpanda -> kafka first.", "direction as a broker pair"),
        ("Bridge Redpanda to Kafka first.", "direction as a broker pair"),
        ("1. Start the mirror.", "numbered step list"),
        ("Wait until the consumer is caught up.", "check kind"),
        ("Check the lag.", "check kind"),
        ("Verify the offset hand-off.", "check kind"),
        ("Start flow A.", "check kind"),
    ],
)
def test_leak_guard_catches_each_rule(violation, rule):
    card = (EVIDENCE / "task-card.md").read_text()
    assert rule in leaks(card + "\n" + violation + "\n")


def test_plan_format_section_passes_the_guard():
    """The plan format must name `direction` and `allow_lists`: the guard is narrow enough for it."""
    card = (EVIDENCE / "task-card.md").read_text()
    section = card[card.index("## Plan format") :]
    assert "allow_lists" in section and '"direction"' in section
    assert leaks(section) == []


def test_embedded_schemas_are_what_the_tools_validate():
    schema = plan_format.schema("plan-schema")
    assert schema["required"] == ["items", "allow_lists"]
    assert set(schema["properties"]["items"]["items"]["properties"]) >= {
        "architecture_citations",
        "implementation_justification",
        "direction",
        "files",
    }
    assert plan_format.schema("amendment-schema")["required"] == [
        "utc",
        "item_id",
        "change",
        "reason",
    ]


def test_invalid_plan_is_rejected(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"items": [{"id": "x", "action": "y"}], "allow_lists": []}))
    with pytest.raises(plan_format.PlanFormatError):
        plan_format.load_plan(path)
