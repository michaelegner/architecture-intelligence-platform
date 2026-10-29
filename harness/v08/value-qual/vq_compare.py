"""v0.8 value qualification (spec §5.4): the criteria over the scored sessions.

Per type: a key item's verdict is the verdict of at least 2 of its 3 runs, else MIXED; a count keeps
its 3 values. Per setting (F+ vs F-, T+ vs T-): a key item differs when the verdicts differ and
neither is MIXED; a count differs only when the ranges do not overlap (lower is better). The result
per measure is BETTER, EQUAL, WORSE (with AIP) or NOT_DISTINGUISHABLE. Effort and requests are shown
next to K1-K4 and Q3 coverage of the same type.

    vq_compare.py --out RESULT.json SCORING.json [...]
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRITERIA = (
    HERE.parents[2]
    / "docs/specifications/evaluation/v08-value-qualification-evidence/criteria.json"
)
MIXED, NOT_SCORED, PENDING_OWNER = "MIXED", "NOT_SCORED", "PENDING_OWNER"
RANK = {"MATCHED": 2, "DIFFERENT": 1, "MISSING": 0}
CONTEXT = ("K1", "K2", "K3", "K4", "Q3-coverage")


def item_verdicts(scoring: dict) -> dict[str, str]:
    """K1-K8 and Q1-Q5 of one session. K6/K8: MATCHED when every sub-check is MATCHED."""
    verdicts = {r["id"]: r["verdict"] for r in scoring["plan"]["key_items"]}
    for key in ("K6", "K8"):
        subs = [
            e["verdict"] for e in scoring["plan"]["owner_judged"] if e["id"].startswith(key + ".")
        ]
        if PENDING_OWNER in subs:
            verdicts[key] = PENDING_OWNER
        else:
            verdicts[key] = "MATCHED" if subs and all(v == "MATCHED" for v in subs) else "DIFFERENT"
    verdicts |= {q["id"]: q["verdict"] for q in scoring["questions"]}
    return verdicts


def type_verdict(values: list[str], runs: int) -> str:
    verdict, count = Counter(values).most_common(1)[0] if values else (MIXED, 0)
    return verdict if count * 3 >= 2 * runs and count >= 2 else MIXED


def compare_items(with_aip: str, without: str) -> str:
    if MIXED in (with_aip, without) or {with_aip, without} & {NOT_SCORED, PENDING_OWNER}:
        return "NOT_DISTINGUISHABLE"
    if with_aip == without:
        return "EQUAL"
    return "BETTER" if RANK[with_aip] > RANK[without] else "WORSE"


def compare_counts(with_aip: list[int], without: list[int]) -> str:
    if None in with_aip + without or not with_aip or not without:
        return "NOT_DISTINGUISHABLE"
    if set(with_aip) == set(without) and len(set(with_aip)) == 1:
        return "EQUAL"
    if max(with_aip) < min(without):
        return "BETTER"
    if min(with_aip) > max(without):
        return "WORSE"
    return "NOT_DISTINGUISHABLE"


def compare(scorings: list[dict], criteria: dict) -> dict:
    runs = criteria["runs_per_type"]
    by_type: dict[str, list[dict]] = {}
    for scoring in scorings:
        by_type.setdefault(scoring["type"], []).append(scoring)
    problems = [
        f"{t}: {len(s)} valid sessions, not {runs}"
        for t, s in sorted(by_type.items())
        if len(s) != runs
    ]
    types = {}
    for card_type, sessions in sorted(by_type.items()):
        verdicts = [item_verdicts(s) for s in sessions]
        items = {
            item: type_verdict([v.get(item, MIXED) for v in verdicts], runs)
            for item in criteria["key_items"]
        }
        if card_type.startswith("T"):
            items |= {item: NOT_SCORED for item in criteria["not_scored"]["T"]}
        counts = {name: [s["counts"].get(name) for s in sessions] for name in criteria["counts"]}
        types[card_type] = {"items": items, "runs": verdicts, "counts": counts}
    settings = {}
    for with_aip, without in criteria["comparisons"]:
        if with_aip not in types or without not in types:
            continue
        a, b = types[with_aip], types[without]
        settings[f"{with_aip} vs {without}"] = {
            "items": {
                i: compare_items(a["items"][i], b["items"][i]) for i in criteria["key_items"]
            },
            "counts": {
                c: compare_counts(a["counts"][c], b["counts"][c]) for c in criteria["counts"]
            },
            "context": {t: {i: types[t]["items"][i] for i in CONTEXT} for t in (with_aip, without)},
        }
    return {"types": types, "settings": settings, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("scorings", type=Path, nargs="+")
    args = parser.parse_args(argv)
    result = compare(
        [json.loads(p.read_text()) for p in args.scorings], json.loads(CRITERIA.read_text())
    )
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for problem in result["problems"]:
        print(f"STOP: {problem}", file=sys.stderr)
    print(f"compared {len(args.scorings)} session(s)")
    return 2 if result["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
