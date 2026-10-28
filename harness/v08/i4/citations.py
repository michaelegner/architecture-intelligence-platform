"""v0.8 I4 §6: Proof B. Checks the citations of the frozen plan against the recorded before-wave
AIP answers (`record_answers.py`), never against a live query.

Per citation:
- RESOLVED: a row citation names a row of the recorded answer to one of the agent's requests at the
  cited snapshot; a ref citation names refs that appear in such an answer and that evidence mode
  resolved (`RESOLVED`) for that request;
- SUPPORTS: for an item that a binding key item (K1-K4) matched, the cited row's topic is one of the
  item's topics and its crossing is INBOUND or OUTBOUND. For other items AIP citations are optional
  and this rule does not apply.

Per binding key item (the coverage rule): COVERED when the matched plan items cite every expected
row and every cited row resolves and supports; DOES_NOT_SUPPORT when a cited row does not; else
INCOMPLETE (with the missing rows) or NOT_CITED. Per mechanism item: JUSTIFIED when it has at least
one implementation justification, else UNJUSTIFIED, whatever it cites.

A pass means "the binding behind this item is evidenced", never "this action is correct".
"""

import argparse
import json
import sys
from pathlib import Path

from plan_format import load_key, load_plan, row_key

RESOLVED, UNRESOLVED = "RESOLVED", "UNRESOLVED"
SUPPORTS, DOES_NOT_SUPPORT = "SUPPORTS", "DOES_NOT_SUPPORT"
COVERED, INCOMPLETE, NOT_CITED = "COVERED", "INCOMPLETE", "NOT_CITED"
JUSTIFIED, UNJUSTIFIED = "JUSTIFIED", "UNJUSTIFIED"
CROSSING = {"INBOUND", "OUTBOUND"}
REF_FIELDS = ("promise_evidence_refs", "attachment_evidence_refs", "mapping_evidence_refs")


class Recorded:
    """The recorded before-wave answers: rows and resolved refs, per snapshot id."""

    def __init__(self, recording: dict):
        self.rows: dict[str, dict[tuple, dict]] = {}
        self.ref_rows: dict[str, dict[str, tuple]] = {}
        self.resolved: dict[str, set[str]] = {}
        for exchange in recording["agent_requests"]:
            answer = exchange["answer"]
            if answer.get("outcome") == "NOT_ANSWERED" or not answer.get("snapshot"):
                continue
            snapshot = answer["snapshot"]["snapshot_id"]
            for row in answer["data"]["rows"]:
                self.rows.setdefault(snapshot, {})[row_key(row)] = row
                for field in REF_FIELDS:
                    for ref in row[field]:
                        self.ref_rows.setdefault(snapshot, {})[ref] = row_key(row)
        for exchange in recording.get("evidence", []):
            answer = exchange["answer"]
            snapshot = exchange["request"]["snapshot_id"]
            for entry in (answer.get("data") or {}).get("entries", []):
                if entry["status"] == "RESOLVED":
                    self.resolved.setdefault(snapshot, set()).add(entry["ref"])

    def cited_rows(self, citation: dict) -> tuple[str, list[tuple]]:
        """(RESOLVED or UNRESOLVED, the row keys the citation names)."""
        snapshot = citation["snapshot_id"]
        if "evidence_refs" in citation:
            refs = citation["evidence_refs"]
            known = self.ref_rows.get(snapshot, {})
            ok = bool(refs) and all(
                r in known and r in self.resolved.get(snapshot, set()) for r in refs
            )
            return (RESOLVED if ok else UNRESOLVED), sorted({known[r] for r in refs if r in known})
        if not all(citation.get(k) for k in ("broker_id", "topic_name", "consumer_service_id")):
            return UNRESOLVED, []
        key = row_key(citation)
        return (RESOLVED if key in self.rows.get(snapshot, {}) else UNRESOLVED), [key]

    def row(self, snapshot: str, key: tuple) -> dict | None:
        return self.rows.get(snapshot, {}).get(key)


def check_item(item: dict, recorded: Recorded, binding: bool) -> dict:
    citations = []
    for citation in item["architecture_citations"]:
        status, keys = recorded.cited_rows(citation)
        support = None
        if binding:
            rows = [recorded.row(citation["snapshot_id"], k) for k in keys]
            support = (
                SUPPORTS
                if status == RESOLVED
                and rows
                and all(
                    r is not None
                    and r["topic_name"] in item.get("topics", [])
                    and r["crossing"] in CROSSING
                    for r in rows
                )
                else DOES_NOT_SUPPORT
            )
        citations.append(
            {"citation": citation, "resolution": status, "rows": [list(k) for k in keys]}
            | ({"support": support} if binding else {})
        )
    justified = JUSTIFIED if item["implementation_justification"] else UNJUSTIFIED
    return {
        "id": item["id"],
        "binding": binding,
        "citations": citations,
        "justification": justified,
    }


def coverage(key_item: dict, plan_ids: list[str], checked: dict[str, dict]) -> dict:
    expected = {row_key(r) for r in key_item["expected_rows"]}
    entries = [c for pid in plan_ids for c in checked[pid]["citations"]]
    cited = {tuple(k) for c in entries for k in c["rows"] if c["resolution"] == RESOLVED}
    if not plan_ids or not entries:
        verdict = NOT_CITED
    elif any(c.get("support") != SUPPORTS for c in entries):
        verdict = DOES_NOT_SUPPORT
    elif expected <= cited:
        verdict = COVERED
    else:
        verdict = INCOMPLETE
    return {
        "id": key_item["id"],
        "verdict": verdict,
        "plan_items": plan_ids,
        "missing_rows": [list(k) for k in sorted(expected - cited)],
    }


def check(plan: dict, key: dict, recording: dict, scoring: dict) -> dict:
    recorded = Recorded(recording)
    matched = {
        r["id"]: r["plan_items"] if r["verdict"] == "MATCHED" else []
        for r in scoring["key_items"]
        if r["id"] in ("K1", "K2", "K3", "K4")
    }
    binding_ids = {pid for ids in matched.values() for pid in ids}
    checked = {
        item["id"]: check_item(item, recorded, item["id"] in binding_ids) for item in plan["items"]
    }
    key_items = {k["id"]: k for k in key["items"]}
    covered = [coverage(key_items[k], ids, checked) for k, ids in sorted(matched.items())]
    mechanism = [c for c in checked.values() if not c["binding"]]
    return {
        "items": [checked[item["id"]] for item in plan["items"]],
        "coverage": covered,
        "unresolved": sorted(
            c["id"]
            for c in checked.values()
            if any(x["resolution"] != RESOLVED for x in c["citations"])
        ),
        "unjustified": sorted(c["id"] for c in mechanism if c["justification"] == UNJUSTIFIED),
        "passed": all(c["verdict"] == COVERED for c in covered)
        and not any(c["justification"] == UNJUSTIFIED for c in mechanism)
        and all(x["resolution"] == RESOLVED for c in checked.values() for x in c["citations"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--recording", type=Path, required=True, help="before-wave answers")
    parser.add_argument("--scoring", type=Path, required=True, help="score.py output")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = check(
        load_plan(args.plan),
        load_key(),
        json.loads(args.recording.read_text()),
        json.loads(args.scoring.read_text()),
    )
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"Proof B {'passed' if result['passed'] else 'did not pass'}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
