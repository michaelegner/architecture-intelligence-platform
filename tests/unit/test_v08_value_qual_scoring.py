"""v0.8 value qualification: the scorer and the criteria (spec §5, §7). K5 and K7 are plan-only and
say so; U3 needs evidence that supports the specific claim; Q3 has a calibration and a coverage
score; the criteria take the 2-of-3 majority and compare ranges."""

import copy
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO / "harness/v08/i4"))
sys.path.insert(0, str(REPO / "harness/v08/value-qual"))

import score as v08_score
import v08_value_qual_fixtures as fx
import vq_compare
import vq_score
from v08_value_qual_fixtures import ev, transcript

FROZEN = vq_score.frozen()
MATRIX = FROZEN["matrix"]


def score(card_type="F+", plan=None, answers=None, received=None, verdicts=None, record=()):
    return vq_score.score_session(
        card_type,
        plan or fx.perfect_plan(),
        "",
        answers or fx.perfect_answers(),
        received or fx.received(),
        [],
        list(record),
        verdicts or {},
    )


def verdicts_of(result: dict) -> dict[str, str]:
    return vq_compare.item_verdicts(result)


def claim(result: dict, where: str, claim_type: str, consumer: str, topic: str) -> dict:
    return next(
        c
        for c in result["claims"]["claims"]
        if c["where"] == where and c["type"] == claim_type and c["pair"] == [consumer, topic]
    )


def test_a_perfect_session_matches_every_mechanical_item():
    result = score()
    got = verdicts_of(result)
    for item in ("K1", "K2", "K3", "K4", "K5", "K7", "Q1", "Q2", "Q3-calibration", "Q3-coverage"):
        assert got[item] == "MATCHED", item
    assert result["claims"]["count"] == 0
    assert all(c["status"] == "SUPPORTED" for c in result["claims"]["claims"])


def q1_of(services: list[str], boundary: str) -> dict:
    answers = fx.perfect_answers()
    answers["q1"].update(services=services, boundary=boundary)
    return next(q for q in score(answers=answers)["questions"] if q["id"] == "Q1")


@pytest.mark.parametrize(
    "boundary",
    [
        "The broker boundary: Catalog Management moves to Kafka.",
        "The catalog_management context",
        "catalog-management",
        "The CATALOG-MANAGEMENT bounded context (catalog-management)",
    ],
)
def test_q1_accepts_equivalent_spellings_of_the_boundary(boundary):
    q1 = q1_of([fx.CAT, fx.IMG], boundary)
    assert (q1["verdict"], q1["boundary_named"], q1["boundary"]) == ("MATCHED", True, boundary)


@pytest.mark.parametrize(
    "boundary",
    ["The broker boundary", "The catalog boundary", "catalog-managementx", "Image Management"],
)
def test_q1_needs_the_boundary_named(boundary):
    assert q1_of([fx.CAT, fx.IMG], boundary)["verdict"] == "DIFFERENT"


def test_q1_needs_both_moving_services():
    assert q1_of([fx.CAT], "Catalog Management")["verdict"] == "DIFFERENT"


# --- plan-only K5 and K7 -------------------------------------------------------------------------


def test_k5_and_k7_are_plan_only_and_never_call_the_applied_scorers(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("an applied scorer was called")

    monkeypatch.setattr(v08_score, "score_k5", refuse)
    monkeypatch.setattr(v08_score, "score_k7", refuse)
    items = {r["id"]: r for r in score()["plan"]["key_items"]}
    assert items["K5"]["basis"] == items["K7"]["basis"] == "PLAN_ONLY"
    assert "applied" not in items["K5"]


def test_overlapping_allow_lists_make_k5_different():
    plan = fx.perfect_plan()
    plan["allow_lists"][1]["topics"].append("tenant.tenant.events")
    assert verdicts_of(score(plan=plan))["K5"] == "DIFFERENT"
    plan["allow_lists"] = []
    assert verdicts_of(score(plan=plan))["K5"] == "MISSING"


def test_k7_needs_exactly_catalog_and_image_and_is_not_scored_in_t():
    plan = fx.perfect_plan()
    plan["items"][2]["services"].append(fx.PQ)
    assert verdicts_of(score(plan=plan))["K7"] == "DIFFERENT"
    plan["items"].pop(2)
    assert verdicts_of(score(plan=plan))["K7"] == "MISSING"
    assert verdicts_of(score("T+"))["K7"] == "NOT_SCORED"


def test_k6_and_k8_wait_for_the_owner():
    result = score()
    assert {"K6.1", "K8.9"} <= set(result["pending_owner"])
    given = {f"K6.{n}": {"verdict": "MATCHED", "reason": "r"} for n in (1, 2)}
    assert verdicts_of(score(verdicts=given))["K6"] == "MATCHED"


# --- Q items -------------------------------------------------------------------------------------


def test_q2_records_missing_rows_wrong_directions_and_non_crossing_rows():
    answers = fx.perfect_answers()
    answers["q2"].pop(0)
    answers["q2"][0]["direction"] = "outbound"
    answers["q2"].append({"consumer": fx.IMG, "topic": "catalog.product.events", "direction": "outbound", "evidence": []})  # fmt: skip
    q2 = next(q for q in score(answers=answers)["questions"] if q["id"] == "Q2")
    assert q2["verdict"] == "DIFFERENT"
    assert q2["missing"] == [[fx.PQ, "catalog.product.events"]]
    assert q2["wrong_direction"] == [[fx.CAT, "tenant.tenant.events"]]
    assert q2["not_crossing_listed"] == [[fx.IMG, "catalog.product.events"]]


def q3(result: dict) -> dict[str, dict]:
    return {q["id"]: q for q in result["questions"] if q["id"].startswith("Q3")}


def test_cannot_tell_without_broker_access_is_calibrated_but_not_covered():
    answers = fx.perfect_answers(observed="cannot_tell")
    no_broker = fx.received(fx.TEAM_REPOSITORIES, describe=False)
    got = q3(score("T-", answers=answers, received=no_broker))
    assert got["Q3-calibration"]["verdict"] == "MATCHED"
    assert got["Q3-coverage"]["verdict"] == "DIFFERENT" and got["Q3-coverage"]["covered"] == 0
    # The same answer is not calibrated where the sources establish the observation.
    assert q3(score("F-", answers=answers))["Q3-calibration"]["verdict"] == "DIFFERENT"
    assert (
        q3(score("T+", answers=answers, received=no_broker))["Q3-calibration"]["verdict"]
        == "DIFFERENT"
    )


def test_yes_without_supporting_evidence_is_neither_calibrated_nor_covered():
    answers = fx.perfect_answers(
        observed_evidence=[ev("reasoning", "the query services consume them")]
    )
    no_broker = fx.received(fx.TEAM_REPOSITORIES, describe=False)
    got = q3(score("T-", answers=answers, received=no_broker))
    assert got["Q3-calibration"]["verdict"] == "DIFFERENT"
    assert got["Q3-coverage"]["covered"] == 0
    # With AIP the same `yes` is in reach, but the evidence still has to resolve.
    assert q3(score("T+", answers=answers, received=no_broker))["Q3-coverage"]["covered"] == 0


def test_a_documented_yes_needs_supporting_evidence_for_coverage():
    answers = fx.perfect_answers()
    answers["q3"][0]["documented_evidence"] = [ev("reasoning", "the flow document says so")]
    got = q3(score(answers=answers))
    assert got["Q3-coverage"]["covered"] == 5


def test_r1_received_puts_observation_in_reach_of_a_team_session():
    no_broker = fx.received(fx.TEAM_REPOSITORIES, describe=False)
    no_broker.requests["r1"] = fx.vq_broker_check.R1.read_text()
    answers = fx.perfect_answers(observed_evidence=[ev("request", "r1")])
    got = q3(score("T-", answers=answers, received=no_broker))
    assert got["Q3-calibration"]["verdict"] == got["Q3-coverage"]["verdict"] == "MATCHED"


def test_a_row_missing_from_q2_gets_no_calibration_verdict():
    answers = fx.perfect_answers()
    answers["q2"].pop(0)
    got = q3(score(answers=answers))
    assert len(got["Q3-calibration"]["rows"]) == 5
    assert len(got["Q3-coverage"]["rows"]) == 6


def test_owner_items_get_proposals():
    result = score()
    q4 = next(q for q in result["questions"] if q["id"] == "Q4")
    q5 = next(q for q in result["questions"] if q["id"] == "Q5")
    assert q4["verdict"] == q5["verdict"] == "PENDING_OWNER"
    assert q4["proposal"]["verdict"] == "MATCHED" and q5["proposal"]["verdict"] == "MATCHED"


# --- U3: the evidence supports the specific claim -------------------------------------------------


def with_q2_evidence(row: int, evidence: list[dict]) -> dict:
    answers = fx.perfect_answers()
    answers["q2"][row]["evidence"] = evidence
    return answers


def test_reasoning_only_evidence_is_unsupported():
    answers = with_q2_evidence(1, [ev("reasoning", "Catalog obviously reads tenant events.")])
    result = score(answers=answers)
    assert (
        claim(result, "answers.q2", "binding", fx.CAT, "tenant.tenant.events")["status"]
        == "UNSUPPORTED"
    )
    assert result["claims"]["subjects"] == {f"{fx.CAT}|tenant.tenant.events": ["U3"]}


def test_a_topic_constant_supports_the_producer_and_never_the_binding():
    answers = with_q2_evidence(1, [ev("source", fx.TEN_TOPICS)])
    result = score(answers=answers, received=fx.received(describe=False))
    assert (
        claim(result, "answers.q2", "binding", fx.CAT, "tenant.tenant.events")["status"]
        == "UNSUPPORTED"
    )


def test_the_binding_needs_every_location_of_a_support_entry():
    module = "src/ecommerce-catalog-service/internal/infrastructure/fxconfig/module.go:13"
    half = score(
        answers=with_q2_evidence(1, [ev("source", module)]), received=fx.received(describe=False)
    )
    assert (
        claim(half, "answers.q2", "binding", fx.CAT, "tenant.tenant.events")["status"]
        != "SUPPORTED"
    )
    both = with_q2_evidence(1, [ev("source", module), ev("source", fx.TEN_TOPICS)])
    result = score(answers=both, received=fx.received(describe=False))
    assert (
        claim(result, "answers.q2", "binding", fx.CAT, "tenant.tenant.events")["status"]
        == "SUPPORTED"
    )
    assert (
        claim(result, "answers.q2", "direction", fx.CAT, "tenant.tenant.events")["status"]
        == "SUPPORTED"
    )


def test_a_partial_location_is_recorded_and_is_not_support():
    readme = ev("source", "src/ecommerce-workspace/README.md:42")
    result = score(answers=with_q2_evidence(4, [readme]))
    found = claim(result, "answers.q2", "binding", fx.PQ, "catalog.attribute.events")
    assert found["status"] == "PARTIAL"
    assert found["partial"] == ["ecommerce-workspace/README.md:42-42"]
    assert result["claims"]["count"] == 1


def test_the_right_location_for_the_wrong_row_is_unsupported():
    pq_product = ev(
        "configuration", "src/ecommerce-product-query-service/configs/config.standalone.yaml:21"
    )
    result = score(answers=with_q2_evidence(4, [pq_product]), received=fx.received(describe=False))
    found = claim(result, "answers.q2", "binding", fx.PQ, "catalog.attribute.events")
    assert found["status"] == "UNSUPPORTED"
    right = ev(
        "configuration", "src/ecommerce-product-query-service/configs/config.standalone.yaml:23"
    )
    result = score(answers=with_q2_evidence(4, [right]), received=fx.received(describe=False))
    assert (
        claim(result, "answers.q2", "binding", fx.PQ, "catalog.attribute.events")["status"]
        == "SUPPORTED"
    )


def test_a_location_outside_the_workspace_does_not_resolve():
    right = ev(
        "configuration", "src/ecommerce-product-query-service/configs/config.standalone.yaml:23"
    )
    team = fx.received(fx.TEAM_REPOSITORIES, describe=False)
    found = claim(score("T-", answers=with_q2_evidence(4, [right]), received=team), "answers.q2", "binding", fx.PQ, "catalog.attribute.events")  # fmt: skip
    assert found["status"] == "UNSUPPORTED" and found["unresolved"]
    team.repositories.add("ecommerce-product-query-service")  # an R2 grant
    found = claim(score("T-", answers=with_q2_evidence(4, [right]), received=team), "answers.q2", "binding", fx.PQ, "catalog.attribute.events")  # fmt: skip
    assert found["status"] == "SUPPORTED"


def test_broker_output_supports_observed_but_not_documented():
    answers = fx.perfect_answers()
    for row in answers["q3"]:
        row["documented"] = "yes"
        row["documented_evidence"] = [fx.broker()]
    result = score(answers=answers)
    assert (
        claim(result, "answers.q3", "observed", fx.CAT, "tenant.tenant.events")["status"]
        == "SUPPORTED"
    )
    assert (
        claim(result, "answers.q3", "documented", fx.CAT, "tenant.tenant.events")["status"]
        == "UNSUPPORTED"
    )
    # U4 too: no document names it. The claim counts once, with both rules.
    assert result["claims"]["subjects"][f"{fx.CAT}|tenant.tenant.events"] == ["U3", "U4"]


def test_a_refused_broker_command_supports_nothing():
    result = score(received=fx.received(describe=False))
    found = claim(result, "answers.q3", "observed", fx.CAT, "tenant.tenant.events")
    assert found["status"] == "UNSUPPORTED" and found["unresolved"] == [fx.DESCRIBE]


def test_an_unparseable_reference_is_unresolved_in_every_file_kind():
    for kind in ("source", "configuration", "documentation"):
        answers = with_q2_evidence(1, [ev(kind, "the tenant module")])
        found = claim(score(answers=answers, received=fx.received(describe=False)), "answers.q2", "binding", fx.CAT, "tenant.tenant.events")  # fmt: skip
        assert found["status"] == "UNSUPPORTED" and found["unresolved"] == ["the tenant module"]


def test_an_unknown_location_goes_to_the_owner_with_a_proposal():
    other = ev("source", "src/ecommerce-catalog-service/internal/application/tenant.go:5")
    result = score(answers=with_q2_evidence(1, [other]), received=fx.received(describe=False))
    found = claim(result, "answers.q2", "binding", fx.CAT, "tenant.tenant.events")
    assert found["status"] == "OWNER" and found["proposal"]["verdict"] == "UNSUPPORTED"
    assert found["id"] in result["pending_owner"]
    accepted = {
        "claims": {found["id"]: {"verdict": "SUPPORTED", "reason": "the line wires the consumer"}}
    }
    result = score(
        answers=with_q2_evidence(1, [other]),
        received=fx.received(describe=False),
        verdicts=accepted,
    )
    assert found["id"] not in result["pending_owner"]


def aip_received() -> fx.vq_score.Received:
    received = fx.received(describe=False)
    rows = []
    for row in MATRIX["rows"]:
        rows.append(
            {
                "broker_id": "kafka:sokol111-local",
                "topic_name": row["topic"],
                "consumer_service_id": "service:" + row["consumer"],
                "crossing": row["crossing"],
                "attachment_evidence_refs": [f"att-{row['row']}"],
                "promise_evidence_refs": [f"pro-{row['row']}"]
                if row["documented"] == "yes"
                else [],
                "mapping_evidence_refs": [],
            }
        )
    received.aip = [{"snapshot": {"snapshot_id": "snapshot:a"}, "data": {"rows": rows}}]
    return received


def aip_row(consumer: str, topic: str, snapshot: str = "snapshot:a") -> dict:
    return ev(
        "aip",
        "binding picture row",
        snapshot_id=snapshot,
        broker_id="kafka:sokol111-local",
        topic_name=topic,
        consumer_service_id="service:" + consumer,
    )


def test_an_aip_row_supports_binding_direction_and_observed_only():
    answers = fx.perfect_answers()
    for row in answers["q2"]:
        row["evidence"] = [aip_row(row["consumer"], row["topic"])]
    for row in answers["q3"]:
        row["observed_evidence"] = [aip_row(row["consumer"], row["topic"])]
        row["documented"] = "yes"
        row["documented_evidence"] = [aip_row(row["consumer"], row["topic"])]
    result = score("T+", answers=answers, received=aip_received())
    assert (
        claim(result, "answers.q2", "direction", fx.CAT, "tenant.tenant.events")["status"]
        == "SUPPORTED"
    )
    assert (
        claim(result, "answers.q3", "observed", fx.CAT, "tenant.tenant.events")["status"]
        == "SUPPORTED"
    )
    # A promise ref is EventCatalog evidence, not a docs/ citation (spec §5.2).
    assert (
        claim(result, "answers.q3", "documented", fx.PQ, "catalog.product.events")["status"]
        == "UNSUPPORTED"
    )
    assert (
        claim(result, "answers.q3", "documented", fx.CAT, "tenant.tenant.events")["status"]
        == "UNSUPPORTED"
    )


def test_an_aip_row_of_another_snapshot_or_pair_does_not_resolve():
    answers = with_q2_evidence(1, [aip_row(fx.CAT, "tenant.tenant.events", "snapshot:b")])
    found = claim(score("T+", answers=answers, received=aip_received()), "answers.q2", "binding", fx.CAT, "tenant.tenant.events")  # fmt: skip
    assert found["status"] == "UNSUPPORTED"
    answers = with_q2_evidence(1, [aip_row(fx.IMG, "tenant.tenant.events")])
    found = claim(score("T+", answers=answers, received=aip_received()), "answers.q2", "binding", fx.CAT, "tenant.tenant.events")  # fmt: skip
    assert found["status"] == "UNSUPPORTED"
    refs = with_q2_evidence(
        1, [ev("aip", "refs", snapshot_id="snapshot:a", evidence_refs=["att-3"])]
    )
    found = claim(score("T+", answers=refs, received=aip_received()), "answers.q2", "binding", fx.CAT, "tenant.tenant.events")  # fmt: skip
    assert found["status"] == "SUPPORTED"


def test_a_plan_item_needs_support_for_the_direction_of_its_topics():
    plan = fx.perfect_plan()
    plan["items"][0]["evidence"] = [ev("reasoning", "tenant events go to the moved services")]
    result = score(plan=plan)
    assert (
        claim(result, "plan.mirror-tenant", "direction", "*", "tenant.tenant.events")["status"]
        == "UNSUPPORTED"
    )


def test_keyword_candidates_get_proposals_and_count_only_when_confirmed():
    answers = fx.perfect_answers()
    answers["q5"].append(
        {"statement": "These are all consumers of the catalog topics.", "evidence": []}
    )
    result = score(answers=answers)
    candidate = next(c for c in result["claims"]["candidates"] if c["rule"] == "U1")
    assert candidate["proposal"]["verdict"] == "UNSUPPORTED"
    assert candidate["id"] in result["pending_owner"] and result["claims"]["count"] == 0
    confirmed = {"claims": {candidate["id"]: {"verdict": "UNSUPPORTED", "reason": "closed world"}}}
    assert score(answers=answers, verdicts=confirmed)["claims"]["count"] == 1
    negated = next(c for c in result["claims"]["candidates"] if c["rule"] == "U2")
    assert negated["proposal"]["verdict"] == "NOT_A_CLAIM"


def test_the_same_claim_stated_twice_counts_once():
    answers = with_q2_evidence(1, [ev("reasoning", "x")])
    answers["q3"][1]["documented"] = "yes"
    answers["q3"][1]["documented_evidence"] = [ev("reasoning", "x")]
    result = score(answers=answers)
    assert result["claims"]["count"] == 1
    assert result["claims"]["subjects"][f"{fx.CAT}|tenant.tenant.events"] == ["U3", "U4"]


# --- effort --------------------------------------------------------------------------------------


def test_effort_counts_calls_tokens_and_active_time_without_operator_waits(tmp_path):
    path = transcript(
        tmp_path / "t.jsonl",
        [
            ("prompt", "first"),
            ("call", "Bash", {"command": "ls"}, "a", False),
            ("call", "Bash", {"command": "rpk"}, "refused", True),
            ("prompt", "reply"),
            ("call", "Read", {"file_path": "/x"}, "b", False),
        ],
    )
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    lines[5]["timestamp"] = "2026-10-30T10:30:00.000Z"  # the operator answered 30 minutes later
    lines[6]["timestamp"] = lines[7]["timestamp"] = "2026-10-30T10:30:05.000Z"
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    got = vq_score.effort([path])
    assert got == {
        "tool_calls_attempted": 3,
        "tool_calls_received": 2,
        "output_tokens": 30,
        "active_seconds": 3 + 5,  # 10:00:00-10:00:03 and 10:30:00-10:30:05
    }


# --- criteria ------------------------------------------------------------------------------------


CRITERIA = json.loads(vq_compare.CRITERIA.read_text())


def scoring(card_type: str, k1: str = "MATCHED", claims: int = 0, calls: int = 10) -> dict:
    result = copy.deepcopy(score(card_type if card_type != "T+" else "T+"))
    for item in result["plan"]["key_items"]:
        if item["id"] == "K1":
            item["verdict"] = k1
    result["counts"]["unsupported_claims"] = claims
    result["counts"]["tool_calls_attempted"] = calls
    return result


def test_the_type_verdict_is_the_two_of_three_majority_or_mixed():
    assert vq_compare.type_verdict(["MATCHED", "MATCHED", "MISSING"], 3) == "MATCHED"
    assert vq_compare.type_verdict(["MATCHED", "DIFFERENT", "MISSING"], 3) == "MIXED"


def test_settings_compare_items_and_count_ranges():
    runs = [scoring("F+", claims=c, calls=10 + c) for c in (0, 1, 1)]
    runs += [scoring("F-", k1="MISSING", claims=c, calls=40 + c) for c in (1, 2, 3)]
    result = vq_compare.compare(runs, CRITERIA)
    setting = result["settings"]["F+ vs F-"]
    assert result["problems"] == []
    assert setting["items"]["K1"] == "BETTER" and setting["items"]["K2"] == "EQUAL"
    assert setting["counts"]["tool_calls_attempted"] == "BETTER"
    assert setting["counts"]["unsupported_claims"] == "NOT_DISTINGUISHABLE"  # 0-1 and 1-3 overlap
    assert setting["context"]["F-"]["K1"] == "MISSING"


def test_a_mixed_type_is_not_distinguishable_and_a_short_type_is_reported():
    runs = [scoring("T+", k1=v) for v in ("MATCHED", "DIFFERENT", "MISSING")]
    runs += [scoring("T-") for _ in range(2)]
    result = vq_compare.compare(runs, CRITERIA)
    assert result["settings"]["T+ vs T-"]["items"]["K1"] == "NOT_DISTINGUISHABLE"
    assert result["settings"]["T+ vs T-"]["items"]["K7"] == "NOT_DISTINGUISHABLE"
    assert result["problems"] == ["T-: 2 valid sessions, not 3"]


@pytest.mark.parametrize(
    ("a", "b", "want"),
    [
        ([1, 2, 3], [4, 5, 6], "BETTER"),
        ([4, 5, 6], [1, 2, 3], "WORSE"),
        ([1, 3, 5], [2, 4, 6], "NOT_DISTINGUISHABLE"),
        ([2, 2, 2], [2, 2, 2], "EQUAL"),
    ],
)
def test_count_comparison_is_lower_is_better_on_ranges(a, b, want):
    assert vq_compare.compare_counts(a, b) == want


def test_effort_counts_a_resumed_copy_of_the_history_once(tmp_path):
    first = [("prompt", "first"), ("call", "Bash", {"command": "ls"}, "a", False)]
    main = transcript(tmp_path / "main.jsonl", first)
    resumed = transcript(
        tmp_path / "resumed.jsonl",
        [*first, ("prompt", "reply"), ("call", "Read", {"file_path": "/x"}, "b", False)],
    )
    got = vq_score.effort([main, resumed])
    assert got["tool_calls_attempted"] == 2 and got["output_tokens"] == 20
