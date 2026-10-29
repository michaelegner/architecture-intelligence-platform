"""v0.8 value qualification (spec §4.4): builds the four task-card variants from the v0.8 card,
and the settings template of each type (`vq_settings.py`) next to them.

The shared text is taken from the frozen v0.8 `task-card.md`; only the changes of spec §4.4 are made:
the planning session only, the AIP paragraph only in `+`, the access text of the setting and the
request channel in T, one `evidence[]` field in the plan schema, and `answers.json`. Every replaced
passage must exist in the v0.8 card, or the build stops. The generated cards are committed and frozen
with their digests; this script is kept for provenance.

    make_cards.py CARDS_DIR      (the settings go to CARDS_DIR/../settings)
"""

import json
import sys
import textwrap
from pathlib import Path

import vq_settings

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
V08_CARD = REPO / "docs/specifications/0.8.0/i4-evidence/task-card.md"
EVIDENCE = REPO / "docs/specifications/evaluation/v08-value-qualification-evidence"
R2_LIST = EVIDENCE / "catalogue/r2-list.json"
TYPES = ("F+", "F-", "T+", "T-")
TEAM_REPOSITORIES = (
    "ecommerce-catalog-service",
    "ecommerce-catalog-service-api",
    "ecommerce-image-service",
    "ecommerce-image-service-api",
    "ecommerce-commons",
    "ecommerce-tenant-service-api",
    "ecommerce-workspace",
)
EVIDENCE_KINDS = [
    "aip",
    "documentation",
    "source",
    "configuration",
    "broker_tool",
    "request",
    "reasoning",
]
STATUS = ["yes", "no", "cannot_tell"]
# The v0.8 card keeps a leaf object on one line up to about this width.
WIDTH = 170


PLAN_REQUIRED = (
    '"required": ["id", "action", "architecture_citations", "implementation_justification"],'
)
CITATIONS_START = '          "architecture_citations": {\n'
JUSTIFICATION_END = (
    '                "note": {"type": "string"}\n              }\n            }\n          }\n'
)


class CardError(ValueError):
    pass


def _section(text: str, heading: str) -> str:
    """The text of `## heading` up to the next `## ` heading (or the end)."""
    start = text.index(f"## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end + 1 if end != -1 else len(text)]


def _replace(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise CardError(f"the v0.8 card does not contain exactly one {old[:60]!r}")
    return text.replace(old, new)


def evidence_schema() -> dict:
    return {
        "type": "array",
        "description": (
            "What supports this item or answer. A factual claim (a binding, its direction, its "
            "status, a producer) needs at least one entry of a kind other than reasoning."
        ),
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "reference"],
            "properties": {
                "kind": {"enum": EVIDENCE_KINDS},
                "reference": {
                    "type": "string",
                    "description": (
                        "source, configuration, documentation: <path>:<line> or "
                        "<path>:<line>-<line>, the path relative to the workspace. broker_tool: "
                        "the exact command you ran. request: the request id. aip: what the "
                        "answer says. reasoning: a short statement."
                    ),
                },
                "snapshot_id": {
                    "type": "string",
                    "description": "aip only: the answer's snapshot id.",
                },
                "broker_id": {"type": "string", "description": "aip only: the row's broker."},
                "topic_name": {"type": "string", "description": "aip only: the row's topic."},
                "consumer_service_id": {
                    "type": "string",
                    "description": "aip only: the row's consumer Service.",
                },
                "evidence_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "aip only: evidence refs from that answer.",
                },
                "note": {"type": "string"},
            },
        },
    }


def plan_schema(v08: dict) -> dict:
    """The v0.8 plan schema with `architecture_citations` and `implementation_justification`
    replaced by one `evidence` array (spec §4.4)."""
    schema = json.loads(json.dumps(v08))
    item = schema["properties"]["items"]["items"]
    for name in ("architecture_citations", "implementation_justification"):
        if name not in item["properties"]:
            raise CardError(f"the v0.8 plan schema has no {name}")
        del item["properties"][name]
    item["properties"]["evidence"] = evidence_schema()
    item["required"] = ["id", "action", "evidence"]
    return schema


def answers_schema() -> dict:
    ev = {"$ref": "#/$defs/evidence"}

    def rows(extra: dict, required: list[str]) -> dict:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["consumer", "topic", *required],
                "properties": {
                    "consumer": {
                        "type": "string",
                        "description": "The consumer service, such as ecommerce-catalog-service.",
                    },
                    "topic": {"type": "string"},
                    **extra,
                },
            },
        }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["q1", "q2", "q3", "q4", "q5"],
        "$defs": {"evidence": evidence_schema()},
        "properties": {
            "q1": {
                "type": "object",
                "additionalProperties": False,
                "required": ["services", "boundary", "evidence"],
                "properties": {
                    "services": {"type": "array", "items": {"type": "string"}},
                    "boundary": {"type": "string"},
                    "evidence": ev,
                },
            },
            "q2": rows(
                {
                    "direction": {
                        "enum": ["inbound", "outbound"],
                        "description": "inbound: the producer is outside the boundary and the consumer inside; outbound: the reverse.",
                    },
                    "evidence": ev,
                },
                ["direction", "evidence"],
            ),
            "q3": rows(
                {
                    "documented": {"enum": STATUS},
                    "observed": {"enum": STATUS},
                    "documented_evidence": ev,
                    "observed_evidence": ev,
                },
                ["documented", "observed", "documented_evidence", "observed_evidence"],
            ),
            "q4": rows(
                {"must_preserve": {"type": "string", "minLength": 1}, "evidence": ev},
                ["must_preserve", "evidence"],
            ),
            "q5": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["statement", "evidence"],
                    "properties": {"statement": {"type": "string", "minLength": 1}, "evidence": ev},
                },
            },
        },
    }


def requests_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "kind", "reason"],
            "properties": {
                "id": {
                    "type": "string",
                    "pattern": "^[A-Za-z0-9._-]+$",
                    "description": "Your request id, unique in the session.",
                },
                "kind": {
                    "type": "string",
                    "description": "broker_consumer_groups, repository_access or other.",
                },
                "repository": {
                    "type": "string",
                    "description": "repository_access only: one repository from the list.",
                },
                "reason": {"type": "string", "minLength": 1},
            },
        },
    }


def _bullet(text: str) -> str:
    """One Markdown bullet, wrapped at 100 columns."""
    return (
        textwrap.fill(
            text, 100, subsequent_indent="  ", break_long_words=False, break_on_hyphens=False
        )
        + "\n"
    )


def _dump(value: object, indent: int = 0, lead: int = 0) -> str:
    """JSON in the style of the v0.8 card: a value that fits in WIDTH columns stays on one line.
    `lead` is the width of the key in front of the value on its line."""
    flat = json.dumps(value, ensure_ascii=False)
    if not isinstance(value, (dict, list)) or indent + lead + len(flat) <= WIDTH:
        return flat
    pad, inner = " " * indent, " " * (indent + 2)
    if isinstance(value, dict):
        body = [
            f"{inner}{json.dumps(k)}: {_dump(v, indent + 2, len(json.dumps(k)) + 2)}"
            for k, v in value.items()
        ]
        return "{\n" + ",\n".join(body) + f"\n{pad}}}"
    body = [inner + _dump(v, indent + 2) for v in value]
    return "[\n" + ",\n".join(body) + f"\n{pad}]"


def _schema_text(text: str, name: str) -> str:
    start = text.index(f"```json {name}\n") + len(f"```json {name}\n")
    return text[start : text.index("\n```", start)]


def _block(name: str, schema: dict) -> str:
    return f"```json {name}\n{_dump(schema)}\n```\n"


def build(card_type: str, v08_text: str, r2: list[str]) -> str:
    if card_type not in TYPES:
        raise CardError(f"unknown type {card_type}")
    team, with_aip = card_type[0] == "T", card_type[1] == "+"
    title_intro = v08_text[: v08_text.index("## Goal\n")]
    title_intro = _replace(
        title_intro,
        "The operator gives it to you unchanged in both\nsessions, as `TASK.md` in your workspace.",
        "The operator gives it to you unchanged, as\n`TASK.md` in your workspace.",
    )
    goal = _section(v08_text, "Goal")
    environment = _section(v08_text, "Environment")
    constraints = _section(v08_text, "Constraints")
    plan_format = _section(v08_text, "Plan format")

    aip_start = environment.index("- **AIP**")
    aip_paragraph = environment[aip_start:].rstrip("\n") + "\n"
    environment = environment[:aip_start]
    if team:
        environment = _replace(
            environment,
            "Its source repositories are in `src/` in your workspace, at the\n  revisions that run.",
            "The source repositories of your team are in `src/` in your\n"
            "  workspace, at the revisions that run.",
        )
        environment = _replace(
            environment,
            "- **Kubernetes:**",
            _bullet(
                "- **Your team** owns Catalog Management. Its repositories in `src/` are "
                + ", ".join(f"`{r}`" for r in TEAM_REPOSITORIES)
                + ". The repositories of the other teams are not in your workspace."
            )
            + "- **Kubernetes:**",
        )
        environment = _replace(
            environment,
            "The Helm values are in\n  `src/ecommerce-infrastructure/environments/local/values/`.",
            "The Helm values are in\n  `ecommerce-infrastructure/environments/local/values/`, the platform team's repository. It\n"
            "  is not in your workspace.",
        )
        environment += (
            "- **Your access:** in this session you have no cluster or broker access: no `docker`, "
            "`kubectl`,\n  `helm`, `rpk` or Kafka commands. The platform team has this access. "
            "See Requests.\n"
        )
    else:
        environment += "- **Commands:** run one command per Bash call.\n"
    if with_aip:
        environment += aip_paragraph
    environment += "\n"

    outputs = "`plan.json`, `plan.md` and `answers.json`"
    writable = outputs + (" (and `requests.json`)" if team else "")
    session = (
        "## Session\n\n"
        "This is a planning session. Another session carries out the plan later; it is not part of "
        "this task.\n\n"
        "First message: `Read TASK.md. Plan the move as TASK.md describes. Write plan.json, plan.md "
        "and\nanswers.json in the workspace, then stop.` In this session you can read and query, "
        f"but not change the\nenvironment. You can write only {writable}.\n\n"
    )

    plan_section = plan_format[: plan_format.index("`amendments.json` is a list.")]
    plan_section = _replace(
        plan_section,
        PLAN_REQUIRED,
        PLAN_REQUIRED.replace(
            '"architecture_citations", "implementation_justification"', '"evidence"'
        ),
    )
    start = plan_section.index(CITATIONS_START)
    end = plan_section.index(JUSTIFICATION_END, start) + len(JUSTIFICATION_END)
    evidence = _dump(evidence_schema(), 10, len('"evidence": '))
    plan_section = plan_section[:start] + f'          "evidence": {evidence}\n' + plan_section[end:]
    v08_block = _schema_text(plan_format, "plan-schema")
    if json.loads(_schema_text(plan_section, "plan-schema")) != plan_schema(json.loads(v08_block)):
        raise CardError("the edited plan schema differs from the structural change")

    answers = (
        "## Answers\n\n"
        "`answers.json` answers five questions about the move:\n\n"
        "- **q1:** Which services move, and which boundary changes?\n"
        "- **q2:** Which consumer × topic bindings cross that boundary? One row per binding, with its "  # noqa: RUF001
        "direction.\n"
        "- **q3:** For each binding of q2: is it documented, is it observed at runtime, or can you "
        "not tell?\n"
        "- **q4:** Why does each binding of q2 matter for this move? Per row: what the move must "
        "preserve.\n"
        "- **q5:** What does your evidence not establish, and what must be verified after the move?\n\n"
        "A binding is **documented** when a document in `src/ecommerce-workspace/docs/` names it. "
        "README and\n`AGENTS.md` files are source, not documents. A binding is **observed** when a "
        "consumer group of the\nservice is attached to the topic on the running broker. Use "
        "`cannot_tell` when your evidence does not\nshow it.\n\n"
        "Every claim has evidence entries in the form of the plan schema. `answers.json` must be "
        "valid against\nthis schema:\n\n" + _block("answers-schema", answers_schema()) + "\n"
    )

    requests = ""
    if team:
        requests = (
            "## Requests\n\n"
            "You can ask for information that you cannot reach. Write `requests.json` in the "
            "workspace and end\nyour turn with `OPERATOR: please answer requests.json`. The operator "
            "answers each new request once,\nby its id, and you continue in the next turn. Each "
            "request has one `kind`:\n\n"
            "- `broker_consumer_groups`: the platform team describes the consumer groups on Redpanda.\n"
            + _bullet(
                "- `repository_access`: read access to one other team's repository, named in "
                "`repository`. The repository is then added to `src/`. The repositories are: "
                + ", ".join(f"`{r}`" for r in r2)
                + "."
            )
            + "- `other`: anything else; say what you need in `reason`.\n\n"
            "`requests.json` must be valid against this schema:\n\n"
            + _block("requests-schema", requests_schema())
            + "\n"
        )

    card = (
        title_intro + goal + environment + constraints + session + plan_section + answers + requests
    )
    return card.rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    out = Path(args[0])
    out.mkdir(parents=True, exist_ok=True)
    v08_text = V08_CARD.read_text()
    r2 = json.loads(R2_LIST.read_text())["repositories"]
    settings_dir = out.parent / "settings"
    settings_dir.mkdir(exist_ok=True)
    for card_type in TYPES:
        (out / f"task-card.{card_type}.md").write_text(build(card_type, v08_text, r2))
        settings = json.dumps(vq_settings.template(card_type), indent=2) + "\n"
        (settings_dir / f"settings.{card_type}.json").write_text(settings)
    print(f"{len(TYPES)} cards written to {out}, their settings templates to {settings_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
