"""v0.8 I4a: the AIP answer recorder (I4 spec §6, §9) against a fake REST transport.

`before` replays the agent's requests without `mode`, stops when an answer differs from the one in
the agent's transcript, and resolves the cited refs with the context of the request that returned
them, at most 20 per call; `after` records only the report's request.
"""

import json
import sys
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness/v08/i4"))

import record_answers

from .v080_i4_plans import SNAP, perfect_plan, recording

ANSWER = recording()["agent_requests"][0]["answer"] | {"limitations": []}
ANSWER["data"] |= {"page": {"limit": 100, "returned": 9, "next_cursor": None}}


def client(calls: list) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        if request.url.path.endswith("/evidence"):
            entries = [{"ref": r, "status": "RESOLVED"} for r in body["evidence_refs"]]
            return httpx.Response(200, json={"data": {"entries": entries}})
        return httpx.Response(200, json=ANSWER)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://aip")


AGENT = [
    {
        "index": 0,
        "request": {
            "mode": "query",
            "bounded_context_id": "catalog-management",
            "environment": "local",
        },
        "transcript_answer": ANSWER,
    }
]


def plan_citing_refs() -> dict:
    plan = perfect_plan()
    refs = [r for row in ANSWER["data"]["rows"] for r in row["attachment_evidence_refs"]]
    plan["items"][0]["architecture_citations"].append({"snapshot_id": SNAP, "evidence_refs": refs})
    plan["items"][1]["architecture_citations"].append(
        {"snapshot_id": SNAP, "evidence_refs": refs[:2]}
    )
    return plan


def test_before_replays_and_resolves():
    calls: list = []
    result = record_answers.record(client(calls), "before", AGENT, plan_citing_refs())
    queries = [body for path, body in calls if path == "/api/binding-picture"]
    assert all("mode" not in body for body in queries)
    assert queries[0]["broker_ids"] == ["kafka:sokol111-local"]  # the report's before request
    evidence = [body for path, body in calls if path.endswith("/evidence")]
    assert [len(body["evidence_refs"]) for body in evidence] == [9]  # one context, de-duplicated
    assert evidence[0]["snapshot_id"] == SNAP
    assert evidence[0]["bounded_context_id"] == "catalog-management"
    assert len(result["agent_requests"]) == 1 and len(result["evidence"]) == 1


def test_before_stops_when_the_answer_differs():
    changed = [{**AGENT[0], "transcript_answer": {**ANSWER, "outcome": "NOT_ANSWERED"}}]
    with pytest.raises(SystemExit, match="differs"):
        record_answers.record(client([]), "before", changed, perfect_plan())


def test_refs_are_sent_in_groups_of_twenty():
    plan = perfect_plan()
    exchange = {
        "request": {"bounded_context_id": "c", "environment": "local"},
        "answer": json.loads(json.dumps(ANSWER)),
    }
    refs = [f"binding-evidence:{n:02d}" for n in range(25)]
    exchange["answer"]["data"]["rows"][0]["attachment_evidence_refs"] = refs
    plan["items"][0]["architecture_citations"] = [{"snapshot_id": SNAP, "evidence_refs": refs}]
    requests = record_answers.evidence_requests(plan, [exchange])
    assert [len(r["evidence_refs"]) for r in requests] == [20, 5]


def test_after_records_only_the_report_request():
    calls: list = []
    result = record_answers.record(client(calls), "after", [], None)
    assert [body["broker_ids"] for _, body in calls] == [
        ["kafka:sokol111-kafka", "kafka:sokol111-local"]
    ]
    assert set(result) == {"phase", "report_request"}
