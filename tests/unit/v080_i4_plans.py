"""v0.8 I4a: synthetic plans and recordings shared by the I4a unit tests: a plan that matches the
plan answer key, citing the C1 rows, and the recorded before-wave answer those citations resolve
against."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness/v08/i4"))

import plan_format

SNAP = "snapshot:" + "a" * 64
LOCAL = "kafka:sokol111-local"
KEY = plan_format.load_key()
C1 = json.loads((REPO / "docs/specifications/0.8.0/i2-vectors/c1-expected.json").read_text())


def _ref(row: dict, kind: str) -> str:
    return f"binding-evidence:{kind}-{row['topic_name']}-{row['consumer_service_id']}"


def recording() -> dict:
    rows = []
    for row in C1["rows"]:
        rows.append(
            {
                **row,
                "group_ids": [row["consumer_service_id"].removeprefix("service:")],
                "promise_evidence_refs": [],
                "attachment_evidence_refs": [_ref(row, "attachment")],
                "mapping_evidence_refs": [_ref(row, "mapping")],
            }
        )
    answer = {"outcome": "ANSWERED", "snapshot": {"snapshot_id": SNAP}, "data": {"rows": rows}}
    request = {"bounded_context_id": "catalog-management", "environment": "local"}
    resolved = [
        {"ref": r, "status": "RESOLVED"} for row in rows for r in row["attachment_evidence_refs"]
    ]
    return {
        "agent_requests": [{"index": 0, "request": request, "answer": answer}],
        "evidence": [
            {"request": {**request, "snapshot_id": SNAP}, "answer": {"data": {"entries": resolved}}}
        ],
    }


def cite(service: str, topic: str) -> dict:
    return {
        "snapshot_id": SNAP,
        "broker_id": LOCAL,
        "topic_name": topic,
        "consumer_service_id": f"service:ecommerce-{service}-service",
    }


JUSTIFY = [{"kind": "source", "reference": "src/x/topics.go:10"}]


def mirror(item_id: str, topic: str, source: str, target: str, cites: list[dict]) -> dict:
    return {
        "id": item_id,
        "action": f"mirror {topic}",
        "topics": [topic],
        "direction": {"source": source, "target": target},
        "architecture_citations": cites,
        "implementation_justification": JUSTIFY,
    }


def perfect_plan() -> dict:
    tenant, product = "tenant.tenant.events", "catalog.product.events"
    category, attribute = "catalog.category.events", "catalog.attribute.events"
    return {
        "items": [
            mirror(
                "m-tenant",
                tenant,
                "redpanda",
                "kafka",
                [cite("catalog", tenant), cite("image", tenant)],
            ),
            mirror("m-product", product, "kafka", "redpanda", [cite("product-query", product)]),
            mirror("m-category", category, "kafka", "redpanda", [cite("category-query", category)]),
            mirror(
                "m-attribute",
                attribute,
                "kafka",
                "redpanda",
                [cite("product-query", attribute), cite("category-query", attribute)],
            ),
            {
                "id": "helm",
                "action": "point Catalog and Image at Kafka",
                "services": ["ecommerce-catalog-service", "ecommerce-image-service"],
                "files": [{"path": "values/ecommerce-catalog-service.yaml", "keys": ["config"]}],
                "architecture_citations": [],
                "implementation_justification": [{"kind": "configuration", "reference": "values"}],
            },
            {
                "id": "handoff",
                "action": "verify the translated committed positions before the restart",
                "architecture_citations": [cite("catalog", tenant)],
                "implementation_justification": [
                    {"kind": "broker_tool", "reference": "kafka-consumer-groups"}
                ],
            },
        ],
        "allow_lists": [
            {"flow": "a", "source": "redpanda", "target": "kafka", "topics": [tenant]},
            {
                "flow": "b",
                "source": "kafka",
                "target": "redpanda",
                "topics": [product, category, attribute],
            },
        ],
    }


EXPECTED_AFTER = json.loads(plan_format.EXPECTED_AFTER.read_text())
FUNCTIONAL = REPO / "docs/specifications/0.8.0/i3-evidence/raw/FT-functional.check.json"


def answer_of(rows: list[dict], snapshot: str = SNAP) -> dict:
    full = [
        {
            "group_ids": [],
            "declared_event_types": [],
            "promise_evidence_refs": [],
            "attachment_evidence_refs": [],
            "mapping_evidence_refs": [],
            **row,
        }
        for row in rows
    ]
    limitations = [{"code": "CAPTURE_SCOPE_LIMITED", "message": "m"}]
    return {
        "outcome": "ANSWERED",
        "snapshot": {"snapshot_id": snapshot},
        "data": {"rows": full},
        "limitations": limitations,
    }


def after_answer() -> dict:
    rows = [
        {**row, "group_ids": [row["consumer_service_id"].removeprefix("service:")]}
        if row["status"] != "PROMISED_NOT_OBSERVED"
        else row
        for row in EXPECTED_AFTER["rows"]
    ]
    return answer_of(rows, "snapshot:" + "b" * 64)


def verdict(kind: str, result: str = "PASSED", **details) -> dict:
    return {"kind": kind, "result": result, "rule": "r", "sources": [], **details}


def write_manifest(
    tmp: Path,
    before: dict,
    after: dict,
    plan: dict,
    proof_b_recording: dict,
    plan_md: str = "The plan.\n",
) -> Path:
    """All report inputs as files, with the scoring and citations computed by the real tools."""
    import citations
    import score

    applied = plan["allow_lists"]
    scoring = score.score(plan, [], KEY, applied, {"result": "PASSED"}, {})
    files = {
        "before": {
            "phase": "before",
            "report_request": {"request": {}, "answer": before},
            **proof_b_recording,
        },
        "after": {"phase": "after", "report_request": {"request": {}, "answer": after}},
        "plan": plan,
        "scoring": scoring,
        "citations": citations.check(plan, KEY, proof_b_recording, scoring),
        "handoff": verdict("handoff-after", entries=[]),
        "applied_mm2": verdict("applied-mm2"),
        "applied_helm": verdict("applied-helm"),
        "functional_test": json.loads(FUNCTIONAL.read_text()),
        "audit": {"hits": [], "clean": True},
        "agent": {
            "model": "claude-test",
            "claude_code_version": "2.1.312",
            "task_card_sha256": "0" * 64,
            "plan_sha256": "1" * 64,
            "plan_frozen_at": "2026-10-29T10:00:00Z",
            "interventions": [],
        },
        "rep-a": verdict("replication", partitions=[{"topic": "tenant.tenant.events"}]),
        "lag-pq": verdict(
            "lag",
            group="ecommerce-product-query-service",
            partitions=[{"topic": "catalog.product.events"}],
        ),
    }
    manifest = {}
    for name, content in files.items():
        (tmp / f"{name}.json").write_text(json.dumps(content))
        manifest[name] = f"{name}.json"
    (tmp / "plan.md").write_text(plan_md)
    manifest["plan_md"] = "plan.md"
    manifest["replication"] = [manifest.pop("rep-a")]
    manifest["lag"] = [manifest.pop("lag-pq")]
    (tmp / "manifest.json").write_text(json.dumps(manifest))
    return tmp / "manifest.json"
