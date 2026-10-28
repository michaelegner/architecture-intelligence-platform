"""v0.8 I4 §8: the showcase report, one static HTML page.

It is built only from frozen inputs, named in a manifest (JSON, paths relative to it):

    before, after          record_answers.py recordings (the AIP answers, via REST)
    plan, plan_md          the agent's frozen plan; amendments (optional)
    scoring, citations     score.py and citations.py results
    replication, lag       lists of I3 checker verdicts (broker tools)
    handoff                ground_truth.py result; applied_mm2, applied_helm: the configuration checks
    proof_c                proof_c.py result
    functional_test        the functional test verdict
    audit, agent           audit.py result; the agent record (model, digests, freeze time,
                           interventions)

The same inputs give the same bytes: no clock, no randomness, sorted iteration. The agent's own
words are quoted in elements with class "agent"; the wording rules (§8.4) apply to everything else.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from plan_format import load_amendments, load_key, load_plan, short_service

HERE = Path(__file__).resolve().parent
FUNCTIONAL_STEP = {
    "tenant.tenant.events": "1-shop-product-image",
    "catalog.product.events": "1-shop-product-image",
    "catalog.category.events": "2-category-update",
    "catalog.attribute.events": "3-attribute-update",
}
BROKER_NAMES = {"kafka:sokol111-local": "Redpanda", "kafka:sokol111-kafka": "Apache Kafka"}
CROSSING = ("INBOUND", "OUTBOUND")
# §8.4: words the report's own text never uses. The agent's quoted words (class "agent") are exempt.
FORBIDDEN = re.compile(r"\b(control\w*|dependenc\w*|during|superagent)\b", re.IGNORECASE)
AGENT_QUOTE = re.compile(r'<(\w+) class="agent">.*?</\1>', re.DOTALL)


def wording_problems(html: str) -> list[str]:
    return sorted({m[0].lower() for m in FORBIDDEN.finditer(AGENT_QUOTE.sub("", html))})


def _load(base: Path, value: str | None):
    return json.loads((base / value).read_text()) if value else None


def _rows(recording: dict) -> list[dict]:
    answer = recording["report_request"]["answer"]
    return answer["data"]["rows"] if answer.get("data") else []


def _limitations(recording: dict) -> list[str]:
    return sorted(item["code"] for item in recording["report_request"]["answer"]["limitations"])


def _verification(topic: str, groups: list[str], inputs: dict) -> dict:
    replication = [
        v
        for v in inputs["replication"]
        if any(p["topic"] == topic for p in v.get("partitions", []))
    ]
    lag = [
        v
        for v in inputs["lag"]
        if v.get("group") in groups and any(p["topic"] == topic for p in v.get("partitions", []))
    ]
    step = next(
        (s for s in inputs["functional_test"]["steps"] if s["step"] == FUNCTIONAL_STEP.get(topic)),
        None,
    )
    return {
        "replication": [v["result"] for v in replication] or ["NOT RECORDED"],
        "lag": [f"{v['group']}: {v['result']}" for v in lag] or ["NOT RECORDED"],
        "functional": f"{step['step']}: {step['result']}" if step else "NOT RECORDED",
    }


def chains(inputs: dict, key: dict, plan: dict) -> list[dict]:
    """One requirement chain per INBOUND/OUTBOUND row after the wave (§8.2)."""
    by_topic = {k["topic"]: k for k in key["items"] if k["kind"] == "binding"}
    scored = {r["id"]: r for r in inputs["scoring"]["key_items"]}
    covered = {c["id"]: c for c in inputs["citations"]["coverage"]}
    items = {item["id"]: item for item in plan["items"]}
    before = {(r["topic_name"], r.get("consumer_service_id")): r for r in _rows(inputs["before"])}
    found = []
    for row in _rows(inputs["after"]):
        if row["crossing"] not in CROSSING:
            continue
        key_item = by_topic.get(row["topic_name"])
        result = scored.get(key_item["id"]) if key_item else None
        plan_items = [items[pid] for pid in (result or {}).get("plan_items", []) if pid in items]
        found.append(
            {
                "row": row,
                "broker": BROKER_NAMES.get(row["broker_id"], row["broker_id"]),
                "consumer": short_service(row.get("consumer_service_id") or "-"),
                "continues": before.get((row["topic_name"], row.get("consumer_service_id"))),
                "key": key_item,
                "proof_a": result["verdict"] if result else "NO KEY ITEM",
                "proof_b": covered[key_item["id"]]["verdict"] if key_item else "-",
                "plan_items": plan_items,
                "verification": _verification(row["topic_name"], row["group_ids"], inputs),
            }
        )
    return found


def no_live_attachment(inputs: dict) -> list[dict]:
    """Report-level comparison (parent §3.6): a Redpanda row with a live attachment before that has
    no row after. It is not a detachment claim beyond the captures."""
    after = {
        (r["broker_id"], r["topic_name"], r.get("consumer_service_id"))
        for r in _rows(inputs["after"])
    }
    return [
        r
        for r in _rows(inputs["before"])
        if r["group_ids"]
        and (r["broker_id"], r["topic_name"], r.get("consumer_service_id")) not in after
    ]


def render(manifest: Path) -> str:
    base = manifest.parent
    paths = json.loads(manifest.read_text())
    inputs = {
        name: _load(base, paths.get(name))
        for name in (
            "before",
            "after",
            "scoring",
            "citations",
            "handoff",
            "proof_c",
            "applied_mm2",
            "applied_helm",
            "functional_test",
            "audit",
            "agent",
        )
    }
    inputs["replication"] = [_load(base, p) for p in paths.get("replication", [])]
    inputs["lag"] = [_load(base, p) for p in paths.get("lag", [])]
    plan = load_plan(base / paths["plan"])
    amendments = load_amendments(base / paths["amendments"] if paths.get("amendments") else None)
    key = load_key()
    env = Environment(
        loader=FileSystemLoader(HERE),
        autoescape=True,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["service"] = short_service
    env.filters["broker"] = lambda broker_id: BROKER_NAMES.get(broker_id, broker_id)
    return env.get_template("report.html.j2").render(
        before_rows=_rows(inputs["before"]),
        after_rows=_rows(inputs["after"]),
        before_limitations=_limitations(inputs["before"]),
        after_limitations=_limitations(inputs["after"]),
        chains=chains(inputs, key, plan),
        gone=no_live_attachment(inputs),
        plan=plan,
        plan_items_by_id={item["id"]: item for item in plan["items"]},
        plan_md=(base / paths["plan_md"]).read_text(),
        amendments=amendments,
        key=key,
        **{name: inputs[name] for name in inputs},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    html = render(args.manifest)
    if problems := wording_problems(html):
        raise SystemExit(f"STOP: the report's own text uses {problems} (I4 §8.4)")
    args.out.write_text(html)
    print(f"report written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
