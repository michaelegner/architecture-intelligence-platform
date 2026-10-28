"""v0.8 I4 §6, §8, §9: records AIP's answers through the REST interface while the right snapshot is
current. AIP answers only for the current snapshot (`SNAPSHOT_NOT_AVAILABLE` otherwise), so:

- `before` runs in S4 before the after-wave import, with B-R current. It replays every frozen
  `get_binding_picture` request of the agent (extracted by `audit.py`), checks that each answer equals
  the one in the agent's transcript, resolves every cited evidence ref through evidence mode with the
  context of the request that returned it, and records the report's before-wave request;
- `after` runs after the after-wave import and records the report's after-wave request.

Evidence refs do not depend on the surface: MCP and REST derive them with the same tool name.
"""

import argparse
import json
import sys
from pathlib import Path

import httpx
from plan_format import load_plan

BOUNDED_CONTEXT, ENVIRONMENT = "catalog-management", "local"
REDPANDA, KAFKA = "kafka:sokol111-local", "kafka:sokol111-kafka"
REPORT_REQUESTS = {
    "before": {"broker_ids": [REDPANDA]},
    "after": {"broker_ids": [KAFKA, REDPANDA]},
}
MAX_REFS = 20
CONTEXT_KEYS = ("bounded_context_id", "environment", "broker_ids")


class Stop(SystemExit):
    def __init__(self, message: str):
        super().__init__(f"STOP: {message}")


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def report_request(phase: str) -> dict:
    return {
        "bounded_context_id": BOUNDED_CONTEXT,
        "environment": ENVIRONMENT,
        "limit": 200,
        **REPORT_REQUESTS[phase],
    }


def evidence_requests(plan: dict, exchanges: list[dict]) -> list[dict]:
    """One evidence request per (agent request, snapshot) for the refs the plan cites, in groups of
    at most 20. A cited ref that no recorded answer returned is left out; the citation checker reads
    it as unresolved."""
    owner: dict[str, dict] = {}
    for exchange in exchanges:
        answer = exchange["answer"]
        if not answer.get("snapshot") or not answer.get("data"):
            continue
        for row in answer["data"]["rows"]:
            for field in (
                "promise_evidence_refs",
                "attachment_evidence_refs",
                "mapping_evidence_refs",
            ):
                for ref in row[field]:
                    owner.setdefault(ref, exchange)
    groups: dict[str, tuple[dict, list[str]]] = {}
    for item in plan["items"]:
        for citation in item["architecture_citations"]:
            for ref in citation.get("evidence_refs", []):
                exchange = owner.get(ref)
                if exchange is None:
                    continue
                context = {
                    k: exchange["request"][k] for k in CONTEXT_KEYS if k in exchange["request"]
                }
                context["snapshot_id"] = exchange["answer"]["snapshot"]["snapshot_id"]
                refs = groups.setdefault(canonical(context), (context, []))[1]
                if ref not in refs:
                    refs.append(ref)
    requests = []
    for _, (context, refs) in sorted(groups.items()):
        for start in range(0, len(refs), MAX_REFS):
            requests.append({**context, "evidence_refs": sorted(refs[start : start + MAX_REFS])})
    return requests


def record(client: httpx.Client, phase: str, agent_requests: list[dict], plan: dict | None) -> dict:
    def post(path: str, body: dict) -> dict:
        response = client.post(path, json=body)
        if response.status_code != 200:
            raise Stop(f"{path} answered HTTP {response.status_code}")
        return response.json()

    recording: dict = {"phase": phase}
    report = post("/api/binding-picture", report_request(phase))
    if report["data"] and report["data"]["page"].get("next_cursor"):
        raise Stop("the report request needs more than one page")
    recording["report_request"] = {"request": report_request(phase), "answer": report}
    if phase == "after":
        return recording
    cites = any(item["architecture_citations"] for item in (plan or {"items": []})["items"])
    if cites and not agent_requests:
        raise Stop(
            "the plan cites AIP, but no binding-picture request was read from the transcript"
        )
    exchanges = []
    for entry in agent_requests:
        request = {k: v for k, v in entry["request"].items() if k != "mode"}
        answer = post("/api/binding-picture", request)
        seen = entry.get("transcript_answer")
        if seen is None:  # the only proof that the agent saw this snapshot: never skipped
            raise Stop(
                f"request {entry['index']}: the agent's answer was not read from the transcript"
            )
        if canonical(seen) != canonical(answer):
            raise Stop(f"the replayed answer differs from the agent's (request {entry['index']})")
        exchanges.append({"index": entry["index"], "request": request, "answer": answer})
    recording["agent_requests"] = exchanges
    recording["evidence"] = [
        {"request": body, "answer": post("/api/binding-picture/evidence", body)}
        for body in evidence_requests(plan or {"items": []}, exchanges)
    ]
    return recording


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phase", choices=("before", "after"))
    parser.add_argument("--aip", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=Path, help="audit.py's extracted agent requests")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.phase == "before" and (args.requests is None or args.plan is None):
        parser.error("before needs --requests and --plan")
    agent_requests = json.loads(args.requests.read_text()) if args.requests else []
    plan = load_plan(args.plan) if args.plan else None
    with httpx.Client(base_url=args.aip, timeout=30) as client:
        recording = record(client, args.phase, agent_requests, plan)
    args.out.write_text(json.dumps(recording, indent=2, sort_keys=True) + "\n")
    print(f"recorded the {args.phase}-wave answers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
