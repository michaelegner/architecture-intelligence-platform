"""v0.8 I4a: Proof A (score.py) and Proof B (citations.py) on synthetic plans (I4 spec §6, §7).

A plan that matches the key scores MATCHED and COVERED. Each departure gives its own verdict: a
missing or reversed mirror, a citation of only part of the expected rows, no citations, a mechanism
item without a justification, a row the answer does not hold, an applied allow-list that overlaps
or differs from the plan, an applied ConfigMap check that failed, and plan items no key item claims.
"""

import copy
import hashlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness/v08/i4"))

import citations
import score

from .v080_i4_plans import C1, KEY, LOCAL, SNAP, _ref, cite, perfect_plan, recording

PASSED_HELM = {"result": "PASSED"}


def run(plan: dict, applied=None, helm=PASSED_HELM, verdicts=None) -> tuple[dict, dict]:
    applied = plan["allow_lists"] if applied is None else applied
    result = score.score(plan, [], KEY, applied, helm, verdicts or {})
    return result, citations.check(plan, KEY, recording(), result)


def verdicts_of(result: dict) -> dict:
    return {r["id"]: r["verdict"] for r in result["key_items"]}


def coverage_of(proof_b: dict) -> dict:
    return {c["id"]: c["verdict"] for c in proof_b["coverage"]}


def test_perfect_plan():
    proof_a, proof_b = run(perfect_plan())
    assert set(verdicts_of(proof_a).values()) == {"MATCHED"}
    assert set(coverage_of(proof_b).values()) == {"COVERED"}
    assert proof_b["passed"] is True
    assert proof_a["extra"] == ["handoff"]  # until the owner's K6/K8 verdicts claim it
    assert proof_a["pending_owner"] == [f"K6.{n}" for n in (1, 2)] + [
        f"K8.{n}" for n in range(1, 10)
    ]


def test_missing_mirror():
    plan = perfect_plan()
    plan["items"] = [i for i in plan["items"] if i["id"] != "m-category"]
    plan["allow_lists"][1]["topics"].remove("catalog.category.events")
    proof_a, proof_b = run(plan)
    assert verdicts_of(proof_a)["K3"] == "MISSING"
    assert coverage_of(proof_b)["K3"] == "NOT_CITED"
    assert "K3" in proof_a["missing_reasons"]
    assert proof_b["passed"] is False


def test_reversed_mirror_is_different():
    plan = perfect_plan()
    plan["items"][0]["direction"] = {"source": "kafka", "target": "redpanda"}
    proof_a, _ = run(plan)
    assert verdicts_of(proof_a)["K1"] == "DIFFERENT"


def test_partial_citation_is_incomplete():
    """The owner's #650 example: K1 cites Catalog but not Image."""
    plan = perfect_plan()
    plan["items"][0]["architecture_citations"] = [cite("catalog", "tenant.tenant.events")]
    _, proof_b = run(plan)
    k1 = next(c for c in proof_b["coverage"] if c["id"] == "K1")
    assert k1["verdict"] == "INCOMPLETE"
    assert k1["missing_rows"] == [
        [LOCAL, "tenant.tenant.events", "service:ecommerce-image-service"]
    ]
    assert proof_b["passed"] is False


def test_no_citations_is_not_cited():
    plan = perfect_plan()
    plan["items"][3]["architecture_citations"] = []
    _, proof_b = run(plan)
    assert coverage_of(proof_b)["K4"] == "NOT_CITED"


def test_cited_row_not_in_answer_does_not_support():
    plan = perfect_plan()
    plan["items"][2]["architecture_citations"].append(cite("image", "catalog.category.events"))
    _, proof_b = run(plan)
    assert coverage_of(proof_b)["K3"] == "DOES_NOT_SUPPORT"
    assert "m-category" in proof_b["unresolved"]


def test_wrong_topic_row_does_not_support():
    plan = perfect_plan()
    plan["items"][2]["architecture_citations"].append(
        cite("product-query", "catalog.product.events")
    )
    _, proof_b = run(plan)
    assert coverage_of(proof_b)["K3"] == "DOES_NOT_SUPPORT"


def test_ref_citation_resolves_and_supports():
    plan = perfect_plan()
    row = next(r for r in C1["rows"] if r["topic_name"] == "catalog.category.events")
    plan["items"][2]["architecture_citations"] = [
        {"snapshot_id": SNAP, "evidence_refs": [_ref(row, "attachment")]}
    ]
    _, proof_b = run(plan)
    assert coverage_of(proof_b)["K3"] == "COVERED"


def test_unresolved_ref_is_unresolved():
    plan = perfect_plan()
    row = next(r for r in C1["rows"] if r["topic_name"] == "catalog.category.events")
    plan["items"][2]["architecture_citations"] = [
        {
            "snapshot_id": SNAP,
            "evidence_refs": [_ref(row, "mapping")],
        }  # in the answer, not resolved
    ]
    _, proof_b = run(plan)
    assert coverage_of(proof_b)["K3"] == "DOES_NOT_SUPPORT"


def test_mechanism_item_without_justification_is_unjustified():
    """Citing AIP rows does not justify a mechanism (D16)."""
    plan = perfect_plan()
    plan["items"][5]["implementation_justification"] = []
    _, proof_b = run(plan)
    assert proof_b["unjustified"] == ["handoff"]
    assert proof_b["passed"] is False


@pytest.mark.parametrize(
    "applied",
    [
        # Overlapping: the tenant topic also flows back.
        [
            {
                "flow": "a",
                "source": "redpanda",
                "target": "kafka",
                "topics": ["tenant.tenant.events"],
            },
            {
                "flow": "b",
                "source": "kafka",
                "target": "redpanda",
                "topics": ["tenant.tenant.events"],
            },
        ],
        # Disjoint, but not what the plan says.
        [
            {
                "flow": "a",
                "source": "redpanda",
                "target": "kafka",
                "topics": ["tenant.tenant.events"],
            }
        ],
    ],
)
def test_applied_allow_lists_must_match_the_plan_and_be_disjoint(applied):
    proof_a, _ = run(perfect_plan(), applied=applied)
    assert verdicts_of(proof_a)["K5"] == "DIFFERENT"


def test_amended_allow_lists_count():
    plan = perfect_plan()
    amended = copy.deepcopy(plan["allow_lists"])
    amended[1]["topics"].remove("catalog.attribute.events")
    result = score.score(
        plan,
        [
            {
                "utc": "2026-10-29T10:00:00Z",
                "item_id": "m",
                "change": "changed",
                "reason": "r",
                "allow_lists": amended,
            }
        ],
        KEY,
        amended,
        PASSED_HELM,
        {},
    )
    assert verdicts_of(result)["K5"] == "MATCHED"


def test_k7_needs_the_applied_configmap_check():
    proof_a, _ = run(perfect_plan(), helm={"result": "FAILED"})
    assert verdicts_of(proof_a)["K7"] == "DIFFERENT"


def test_k7_other_service_is_different():
    plan = perfect_plan()
    plan["items"][4]["services"].append("ecommerce-product-query-service")
    proof_a, _ = run(plan)
    assert verdicts_of(proof_a)["K7"] == "DIFFERENT"


def test_owner_verdicts_and_extra_items():
    plan = perfect_plan()
    plan["items"].append(
        {
            "id": "notes",
            "action": "write a summary",
            "architecture_citations": [],
            "implementation_justification": [{"kind": "reasoning", "reference": "-"}],
        }
    )
    verdicts = {
        f"K{k}.{n}": {"verdict": "MATCHED", "plan_items": ["handoff"], "reason": "ok"}
        for k, count in ((6, 2), (8, 9))
        for n in range(1, count + 1)
    }
    proof_a, _ = run(plan, verdicts=verdicts)
    assert proof_a["pending_owner"] == []
    assert proof_a["missing_reasons"] == []
    assert proof_a["extra"] == ["notes"]


def test_reference_digest_is_checked(tmp_path):
    changed = tmp_path / "expected-after.json"
    changed.write_text("{}")
    with pytest.raises(SystemExit, match="pinned digest"):
        score.check_reference_digest(changed)
    score.check_reference_digest()


def test_a_shared_ref_is_narrowed_by_the_other_refs():
    """Found on a live answer: a group -> Service mapping ref belongs to every row of that consumer.
    Cited with the row's attachment ref it names that row; cited alone it names all of them."""
    rec = recording()
    rows = rec["agent_requests"][0]["answer"]["data"]["rows"]
    shared = "binding-evidence:mapping-category-query"
    for row in rows:
        if row["consumer_service_id"] == "service:ecommerce-category-query-service":
            row["mapping_evidence_refs"] = [shared]
    rec["evidence"][0]["answer"]["data"]["entries"].append({"ref": shared, "status": "RESOLVED"})
    category = next(r for r in C1["rows"] if r["topic_name"] == "catalog.category.events")
    plan = perfect_plan()
    plan["items"][2]["architecture_citations"] = [
        {"snapshot_id": SNAP, "evidence_refs": [_ref(category, "attachment"), shared]}
    ]
    scoring = score.score(plan, [], KEY, plan["allow_lists"], {"result": "PASSED"}, {})
    assert {c["id"]: c["verdict"] for c in citations.check(plan, KEY, rec, scoring)["coverage"]}[
        "K3"
    ] == "COVERED"
    plan["items"][2]["architecture_citations"] = [{"snapshot_id": SNAP, "evidence_refs": [shared]}]
    assert {c["id"]: c["verdict"] for c in citations.check(plan, KEY, rec, scoring)["coverage"]}[
        "K3"
    ] == "DOES_NOT_SUPPORT"


def test_the_scored_plan_must_be_the_frozen_one(tmp_path):
    plan, plan_md = tmp_path / "plan.json", tmp_path / "plan.md"
    plan.write_text("{}")
    plan_md.write_text("rationale")
    freeze = tmp_path / "plan-freeze.txt"
    digests = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (plan, plan_md)]
    freeze.write_text(
        f"{digests[0]}  workspace/plan.json\n{digests[1]}  workspace/plan.md\n2026-10-29T10:00:00Z\n"
    )
    score.check_plan_freeze(freeze, plan, plan_md)
    plan_md.write_text("rationale, edited after the freeze")
    with pytest.raises(SystemExit, match="not the frozen plan"):
        score.check_plan_freeze(freeze, plan, plan_md)
