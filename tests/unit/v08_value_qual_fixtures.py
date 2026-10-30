"""v0.8 value qualification: synthetic plans, answers and transcripts shared by the unit tests. The
perfect plan matches the plan key, and the perfect answers match the comprehension key, with evidence
that resolves against the frozen `matrix.json`."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness/v08/i4"))
sys.path.insert(0, str(REPO / "harness/v08/value-qual"))

import vq_broker_check
import vq_score

DESCRIBE = "docker exec redpanda rpk group describe " + " ".join(vq_broker_check.GROUPS)
ALL_REPOSITORIES = {
    "ecommerce-admin-ui", "ecommerce-catalog-service", "ecommerce-catalog-service-api",
    "ecommerce-category-query-service", "ecommerce-category-query-service-api", "ecommerce-commons",
    "ecommerce-image-service", "ecommerce-image-service-api", "ecommerce-infrastructure",
    "ecommerce-platform-ui", "ecommerce-product-query-service", "ecommerce-product-query-service-api",
    "ecommerce-tenant-service", "ecommerce-tenant-service-api", "ecommerce-ui", "ecommerce-workspace",
}  # fmt: skip
TEAM_REPOSITORIES = {
    "ecommerce-catalog-service", "ecommerce-catalog-service-api", "ecommerce-commons",
    "ecommerce-image-service", "ecommerce-image-service-api", "ecommerce-tenant-service-api",
    "ecommerce-workspace",
}  # fmt: skip
PQ, CQ = "ecommerce-product-query-service", "ecommerce-category-query-service"
CAT, IMG = "ecommerce-catalog-service", "ecommerce-image-service"
CAT_TOPICS = "src/ecommerce-catalog-service-api/pkg/events/topics.go"
TEN_TOPICS = "src/ecommerce-tenant-service-api/pkg/events/topics.go:11"


def ev(kind: str, reference: str, **extra) -> dict:
    return {"kind": kind, "reference": reference, **extra}


def broker() -> dict:
    return ev("broker_tool", DESCRIBE)


PRODUCER = {
    "tenant.tenant.events": ev("source", TEN_TOPICS),
    "catalog.product.events": ev("source", f"{CAT_TOPICS}:11"),
    "catalog.category.events": ev("source", f"{CAT_TOPICS}:12"),
    "catalog.attribute.events": ev("source", f"{CAT_TOPICS}:13"),
}
# The six crossing rows: (consumer, topic, direction).
CROSSING = [
    (PQ, "catalog.product.events", "outbound"),
    (CAT, "tenant.tenant.events", "inbound"),
    (IMG, "tenant.tenant.events", "inbound"),
    (CQ, "catalog.category.events", "outbound"),
    (PQ, "catalog.attribute.events", "outbound"),
    (CQ, "catalog.attribute.events", "outbound"),
]
DOCUMENTED = {
    (PQ, "catalog.product.events"): "yes",
    (CQ, "catalog.category.events"): "cannot_tell",
}


def item(item_id: str, topics: list[str], source: str, target: str, evidence=None, **extra) -> dict:
    return {
        "id": item_id,
        "action": f"Mirror {', '.join(topics)} from {source} to {target}.",
        "topics": topics,
        "direction": {"source": source, "target": target},
        "evidence": evidence
        if evidence is not None
        else [broker()] + [PRODUCER[t] for t in topics],
        **extra,
    }


def perfect_plan() -> dict:
    catalog = ["catalog.product.events", "catalog.category.events", "catalog.attribute.events"]
    return {
        "items": [
            item("mirror-tenant", ["tenant.tenant.events"], "redpanda", "kafka"),
            item("mirror-catalog", catalog, "kafka", "redpanda"),
            {
                "id": "switch-brokers",
                "action": "Change the Kafka bootstrap address of Catalog and Image to kafka:29092.",
                "services": [CAT, IMG],
                "files": [
                    {
                        "path": "src/ecommerce-infrastructure/environments/local/values/ecommerce-catalog-service.yaml",
                        "keys": ["kafka.brokers"],
                    },
                    {
                        "path": "src/ecommerce-infrastructure/environments/local/values/ecommerce-image-service.yaml",
                        "keys": ["kafka.brokers"],
                    },
                ],
                "evidence": [ev("reasoning", "The services move.")],
            },
        ],
        "allow_lists": [
            {
                "flow": "a",
                "source": "redpanda",
                "target": "kafka",
                "topics": ["tenant.tenant.events"],
            },
            {"flow": "b", "source": "kafka", "target": "redpanda", "topics": catalog},
        ],
    }


def perfect_answers(observed: str = "yes", observed_evidence=None) -> dict:
    observed_evidence = [broker()] if observed_evidence is None else observed_evidence
    q3 = []
    for consumer, topic, _ in CROSSING:
        documented = DOCUMENTED.get((consumer, topic), "no")
        q3.append(
            {
                "consumer": consumer,
                "topic": topic,
                "documented": documented,
                "observed": observed,
                "documented_evidence": [
                    ev(
                        "documentation",
                        "src/ecommerce-workspace/docs/architecture/product-update-flow.md:28",
                    )
                ]
                if documented == "yes"
                else [],
                "observed_evidence": observed_evidence if observed == "yes" else [],
            }
        )
    return {
        "q1": {
            "services": [CAT, IMG],
            "boundary": "Catalog Management",
            "evidence": [ev("documentation", "TASK.md:8")],
        },
        "q2": [
            {"consumer": c, "topic": t, "direction": d, "evidence": [broker(), PRODUCER[t]]}
            for c, t, d in CROSSING
        ],
        "q3": q3,
        "q4": [
            {
                "consumer": c,
                "topic": t,
                "must_preserve": f"delivery of {t} to {c}",
                "evidence": [broker()],
            }
            for c, t, _ in CROSSING
        ],
        "q5": [
            {"statement": s, "evidence": [ev("reasoning", "limits of the capture")]}
            for s in (
                "Attachment does not show that the service handles the events.",
                "The capture is one point in time.",
                "The producer is known from the source only.",
                "A binding that is not documented can still exist.",
            )
        ],
    }


def received(repositories=ALL_REPOSITORIES, describe: bool = True) -> vq_score.Received:
    result = vq_score.Received(set(repositories), None)
    if describe:
        result.commands[DESCRIBE] = [vq_broker_check.R1.read_text()]
    return result


def transcript(path: Path, events: list[tuple], start: int = 0) -> Path:
    """Claude Code JSONL: ("prompt", text), ("sidechain", text) or ("call", tool, input, output,
    is_error). Entries carry a `uuid` from their position, counted from `start`."""
    lines, n = [], start
    for event in events:
        stamp = f"2026-10-30T10:00:{len(lines):02d}.000Z"
        if event[0] in ("prompt", "sidechain"):
            lines.append(
                {
                    "type": "user",
                    "uuid": f"u{start + len(lines)}",
                    "isSidechain": event[0] == "sidechain",
                    "timestamp": stamp,
                    "message": {"role": "user", "content": event[1]},
                }
            )
            continue
        _, tool, data, output, is_error = event
        n += 1
        lines.append(
            {
                "type": "assistant",
                "uuid": f"u{start + len(lines)}",
                "timestamp": stamp,
                "message": {
                    "id": f"m{n}",
                    "usage": {"output_tokens": 10},
                    "content": [{"type": "tool_use", "id": f"t{n}", "name": tool, "input": data}],
                },
            }
        )
        lines.append(
            {
                "type": "user",
                "uuid": f"u{start + len(lines)}",
                "timestamp": stamp,
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": f"t{n}",
                            "content": output,
                            "is_error": is_error,
                        }
                    ]
                },
            }
        )
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return path
