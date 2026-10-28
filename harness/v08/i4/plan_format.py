"""v0.8 I4 §4.3: the agent's plan format, read from the frozen task card.

The two JSON Schemas are code blocks in `task-card.md` (```json plan-schema / ```json
amendment-schema), so that the task card's one digest covers them. Every tool that reads `plan.json`
or `amendments.json` validates it here first; an invalid plan is never scored.
"""

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = REPO / "docs/specifications/0.8.0/i4-evidence"
TASK_CARD = EVIDENCE / "task-card.md"
PLAN_KEY = EVIDENCE / "plan-key.json"
EXPECTED_AFTER = REPO / "docs/specifications/0.8.0/i3-evidence/expected-after.json"
# I4 §3: the Proof C reference, pinned by digest; checked before any scoring.
EXPECTED_AFTER_SHA256 = "969cf66e6bae4ad7a67d28d7b723d190328ecb3e11afc248d92312dece50364f"

BROKERS = ("redpanda", "kafka")


class PlanFormatError(ValueError):
    pass


def schema(name: str, task_card: Path = TASK_CARD) -> dict:
    """The ```json <name> code block of the task card."""
    match = re.search(rf"```json {re.escape(name)}\n(.*?)\n```", task_card.read_text(), re.DOTALL)
    if match is None:
        raise PlanFormatError(f"the task card has no {name} block")
    return json.loads(match[1])


def _validate(document: object, name: str, what: str) -> None:
    errors = sorted(Draft202012Validator(schema(name)).iter_errors(document), key=str)
    if errors:
        raise PlanFormatError(f"{what} is not valid: {errors[0].message}")


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text())
    _validate(plan, "plan-schema", path.name)
    ids = [item["id"] for item in plan["items"]]
    if len(ids) != len(set(ids)):
        raise PlanFormatError(f"{path.name}: item ids are not unique")
    return plan


def load_amendments(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    amendments = json.loads(path.read_text())
    if not isinstance(amendments, list):
        raise PlanFormatError(f"{path.name} must be a list")
    for entry in amendments:
        _validate(entry, "amendment-schema", path.name)
    return amendments


def load_key(path: Path = PLAN_KEY) -> dict:
    return json.loads(path.read_text())


def row_key(row: dict) -> tuple[str, str, str]:
    return (row["broker_id"], row["topic_name"], row.get("consumer_service_id") or "")


def short_service(name: str) -> str:
    """`service:ecommerce-catalog-service` and `ecommerce-catalog-service` compare equal."""
    return name.removeprefix("service:")
