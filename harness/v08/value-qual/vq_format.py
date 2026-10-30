"""v0.8 value qualification (spec §4.4): the session outputs, read and validated against the schemas
of the session's frozen card variant (```json plan-schema / answers-schema / requests-schema blocks).

An invalid `plan.json` or `answers.json` is never scored. An invalid request is answered with R3
(spec §4.3), so `load_requests` returns the valid and the invalid entries separately.
"""

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i4"))

import plan_format

REPO = HERE.parents[2]
EVIDENCE = REPO / "docs/specifications/evaluation/v08-value-qualification-evidence"
CARDS = EVIDENCE / "cards"
TYPES = ("F+", "F-", "T+", "T-")
FILE_KINDS = ("source", "configuration", "documentation")
LOCATION = re.compile(r"^(?P<path>[^\s:]+):(?P<start>\d+)(?:-(?P<end>\d+))?$")

PlanFormatError = plan_format.PlanFormatError


def card(card_type: str) -> Path:
    if card_type not in TYPES:
        raise PlanFormatError(f"unknown type {card_type}")
    return CARDS / f"task-card.{card_type}.md"


def schema(name: str, task_card: Path | str) -> dict:
    return plan_format.schema(name, Path(task_card))


def _errors(document: object, name: str, task_card: Path) -> list[str]:
    validator = Draft202012Validator(schema(name, task_card))
    return sorted(error.message for error in validator.iter_errors(document))


def load_plan(path: Path, task_card: Path) -> dict:
    plan = json.loads(path.read_text())
    if errors := _errors(plan, "plan-schema", task_card):
        raise PlanFormatError(f"{path.name} is not valid: {errors[0]}")
    ids = [item["id"] for item in plan["items"]]
    if len(ids) != len(set(ids)):
        raise PlanFormatError(f"{path.name}: item ids are not unique")
    return plan


def load_answers(path: Path, task_card: Path) -> dict:
    answers = json.loads(path.read_text())
    if errors := _errors(answers, "answers-schema", task_card):
        raise PlanFormatError(f"{path.name} is not valid: {errors[0]}")
    return answers


def load_requests(text: str, task_card: Path) -> tuple[list[dict], list[object]]:
    """(valid requests, invalid entries). A file that is not a JSON list is one invalid entry."""
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return [], [text]
    if not isinstance(document, list):
        return [], [document]
    item_schema = schema("requests-schema", task_card)["items"]
    validator = Draft202012Validator(item_schema)
    valid, invalid, seen = [], [], set()
    for entry in document:
        if any(True for _ in validator.iter_errors(entry)) or entry["id"] in seen:
            invalid.append(entry)
        else:
            seen.add(entry["id"])
            valid.append(entry)
    return valid, invalid


def location(reference: str) -> tuple[str, int, int] | None:
    """A file reference `<path>:<line>[-<line>]` as (path below src/, start, end); None when the
    reference does not parse. The path may start with `src/`, `./src/` or an absolute workspace
    path ending in `/workspace/src/`."""
    match = LOCATION.match(reference.strip().strip("`"))
    if match is None:
        return None
    path = match["path"]
    if "/workspace/src/" in path:
        path = path.split("/workspace/src/", 1)[1]
    path = path.removeprefix("./").removeprefix("src/")
    start = int(match["start"])
    end = int(match["end"]) if match["end"] else start
    if end < start:
        return None
    return path, start, end
