"""v0.8 I4 §7: Proof A. Scores the frozen plan against the frozen plan answer key.

- K1-K4 (binding items): a plan item with the key's topic and direction, and the same topic in an
  allow-list of that direction -> MATCHED; the topic with another direction -> DIFFERENT; else
  MISSING.
- K5: the plan's allow-lists (with amendments) and the applied MirrorMaker 2 allow-lists
  (`config_checks.py`) are each disjoint between the two directions, and equal per direction.
- K7: the plan changes the broker setting of exactly Catalog and Image, and the applied ConfigMap
  check (`helm_checks.py`) passed.
- K6 and K8 sub-checks: the owner's verdicts, read from a verdicts file. The scorer lists the
  candidate plan items for each.
- Plan items that no key item claims are EXTRA.

The owner records a reason for every DIFFERENT, MISSING and owner-judged verdict; the output says
whether each one has it (I4 E3). Before anything is scored, the Proof C reference must hash to its
pinned digest (I4 §3).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from plan_format import (
    EXPECTED_AFTER,
    EXPECTED_AFTER_SHA256,
    load_amendments,
    load_key,
    load_plan,
    short_service,
)

MATCHED, DIFFERENT, MISSING, PENDING_OWNER = "MATCHED", "DIFFERENT", "MISSING", "PENDING_OWNER"
OWNER_VERDICTS = {MATCHED, DIFFERENT, MISSING}


def check_reference_digest(path: Path = EXPECTED_AFTER) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_AFTER_SHA256:
        raise SystemExit(f"STOP: {path.name} hashes to {digest}, not the pinned digest (I4 §3)")


def check_plan_freeze(freeze: Path, *files: Path) -> None:
    """The scored plan is the frozen one: each file hashes to its line in the S2 freeze record
    (`sha256sum` output plus the UTC time)."""
    recorded = {}
    for line in freeze.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            recorded[Path(parts[1]).name] = parts[0]
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if recorded.get(path.name) != digest:
            raise SystemExit(f"STOP: {path.name} is not the frozen plan (I4 §4.4)")


def effective_allow_lists(plan: dict, amendments: list[dict]) -> list[dict]:
    """The plan's allow-lists, replaced by the latest amendment that carries allow-lists."""
    allow_lists = plan["allow_lists"]
    for entry in amendments:
        if "allow_lists" in entry:
            allow_lists = entry["allow_lists"]
    return allow_lists


def by_direction(allow_lists: list[dict]) -> dict[tuple[str, str], set[str]]:
    found: dict[tuple[str, str], set[str]] = {}
    for flow in allow_lists:
        found.setdefault((flow["source"], flow["target"]), set()).update(flow["topics"])
    return found


def _overlap(directions: dict[tuple[str, str], set[str]]) -> list[str]:
    there = directions.get(("redpanda", "kafka"), set())
    back = directions.get(("kafka", "redpanda"), set())
    return sorted(there & back)


def score_binding(key_item: dict, plan: dict, allow_lists: dict) -> dict:
    topic, want = key_item["topic"], key_item["direction"]
    on_topic = [item for item in plan["items"] if topic in item.get("topics", [])]
    matching = [item for item in on_topic if item.get("direction") == want]
    listed = topic in allow_lists.get((want["source"], want["target"]), set())
    if matching and listed:
        verdict = MATCHED
    elif on_topic or listed:
        verdict = DIFFERENT
    else:
        verdict = MISSING
    return {
        "id": key_item["id"],
        "verdict": verdict,
        "plan_items": sorted(item["id"] for item in matching) or sorted(i["id"] for i in on_topic),
        "in_allow_list": listed,
    }


def score_k5(planned: list[dict], applied: list[dict]) -> dict:
    plan_dirs, applied_dirs = by_direction(planned), by_direction(applied)
    problems = []
    if overlap := _overlap(plan_dirs):
        problems.append(f"the plan mirrors {overlap} in both directions")
    if overlap := _overlap(applied_dirs):
        problems.append(f"the applied configuration mirrors {overlap} in both directions")
    norm = {k: sorted(v) for k, v in plan_dirs.items()}
    applied_norm = {k: sorted(v) for k, v in applied_dirs.items()}
    if norm != applied_norm:
        problems.append("the applied allow-lists differ from the plan and its amendments")
    return {
        "id": "K5",
        "verdict": DIFFERENT if problems else MATCHED,
        "plan_items": [],
        "problems": problems,
        "planned": {f"{s}->{t}": v for (s, t), v in sorted(norm.items())},
        "applied": {f"{s}->{t}": v for (s, t), v in sorted(applied_norm.items())},
    }


def _changes_brokers(item: dict) -> bool:
    """A plan item that changes a broker key, or a Helm values file (whose broker setting may sit
    inside a `config` string). The applied ConfigMap check decides what was really changed."""
    return any(
        "values" in entry["path"] or any("brokers" in key for key in entry.get("keys", []))
        for entry in item.get("files", [])
    )


def score_k7(key_item: dict, plan: dict, helm_check: dict) -> dict:
    wanted = set(key_item["services"])
    changing = [item for item in plan["items"] if _changes_brokers(item)]
    services = {short_service(s) for item in changing for s in item.get("services", [])}
    problems = []
    if helm_check.get("result") != "PASSED":
        problems.append("the applied ConfigMap check did not pass")
    if not changing:
        verdict = MISSING
    elif services != wanted:
        verdict = DIFFERENT
        problems.append(f"the plan changes the broker setting of {sorted(services)}")
    else:
        verdict = DIFFERENT if problems else MATCHED
    return {
        "id": "K7",
        "verdict": verdict,
        "plan_items": sorted(item["id"] for item in changing),
        "problems": problems,
    }


def score_owner_judged(key_item: dict, plan: dict, verdicts: dict, claimed: set[str]) -> list[dict]:
    """K6/K8: one entry per sub-check, with the owner's verdict (or PENDING_OWNER)."""
    candidates = sorted(item["id"] for item in plan["items"] if item["id"] not in claimed)
    entries = []
    for sub in key_item["sub_checks"]:
        given = verdicts.get(sub["id"], {})
        verdict = given.get("verdict", PENDING_OWNER)
        if verdict not in OWNER_VERDICTS | {PENDING_OWNER}:
            raise SystemExit(f"STOP: {sub['id']}: unknown verdict {verdict!r}")
        entries.append(
            {
                "id": sub["id"],
                "check": sub["check"],
                "verdict": verdict,
                "plan_items": sorted(given.get("plan_items", [])),
                "candidates": candidates,
                "reason": given.get("reason"),
            }
        )
    return entries


def score(
    plan: dict,
    amendments: list[dict],
    key: dict,
    applied_allow_lists: list[dict],
    helm_check: dict,
    verdicts: dict,
) -> dict:
    planned = effective_allow_lists(plan, amendments)
    directions = by_direction(planned)
    items = {k["id"]: k for k in key["items"]}
    results = [score_binding(items[k], plan, directions) for k in ("K1", "K2", "K3", "K4")]
    results.append(score_k5(planned, applied_allow_lists))
    results.append(score_k7(items["K7"], plan, helm_check))
    claimed = {pid for r in results for pid in r.get("plan_items", [])}
    owner = [
        entry
        for k in ("K6", "K8")
        for entry in score_owner_judged(items[k], plan, verdicts, claimed)
    ]
    claimed |= {pid for entry in owner for pid in entry["plan_items"]}
    reasons = verdicts.get("reasons", {})
    for result in results:
        result["reason"] = reasons.get(result["id"])
    needs_reason = [r for r in results if r["verdict"] in (DIFFERENT, MISSING)] + owner
    return {
        "key_items": results,
        "owner_judged": owner,
        "extra": sorted(item["id"] for item in plan["items"] if item["id"] not in claimed),
        "pending_owner": sorted(e["id"] for e in owner if e["verdict"] == PENDING_OWNER),
        "missing_reasons": sorted(e["id"] for e in needs_reason if not e.get("reason")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-md", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True, help="the S2 plan-freeze record")
    parser.add_argument("--amendments", type=Path)
    parser.add_argument("--applied", type=Path, required=True, help="config_checks.py output")
    parser.add_argument("--helm-check", type=Path, required=True, help="helm_checks.py output")
    parser.add_argument("--verdicts", type=Path, help="owner verdicts and reasons (JSON)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    check_reference_digest()
    check_plan_freeze(args.freeze, args.plan, args.plan_md)
    applied = json.loads(args.applied.read_text())
    result = score(
        load_plan(args.plan),
        load_amendments(args.amendments),
        load_key(),
        applied["allow_lists"],
        json.loads(args.helm_check.read_text()),
        json.loads(args.verdicts.read_text()) if args.verdicts else {},
    )
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    complete = not result["pending_owner"] and not result["missing_reasons"]
    print(f"Proof A scored; {'complete' if complete else 'owner verdicts or reasons pending'}")
    return 0 if complete else 3


if __name__ == "__main__":
    sys.exit(main())
