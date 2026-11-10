"""GT 0.8.0 I3: audit one session's transcript. Deviation detection, not a sandbox.

    audit.py SESSION [PROBE]   (for example A-1, or G-1 probe-1 for a dry run)

A violation voids the session; a note is reported only. Violations:

- a tool outside the arm's set was offered or used, or an MCP server other than the arm's;
- a file tool reached a path outside the workspace and the output directory;
- a write other than the two output files;
- the first-impression rule, the same in every arm: before the single write of
  `first-impression.md`, only the task read (A, AA: `task.md`; G, GA: the session's Lepiter page)
  and `ToolSearch`;
- an output file is missing;
- a scored AIP answer names a snapshot other than the frozen one (AA: the transcript; GA: the
  exported client log `aip-log.json`, which must exist);
- the transcript contains the session's credentials.

Refused tool calls are notes: they did not reach anything.
Writes `record/audit.json`. Exit 0 when clean, 3 when void.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from session import FROZEN_SNAPSHOT, OUTPUTS, Session, tokens

# The path arguments of the file tools; an absolute Glob pattern or Grep glob also names a place.
FILE_TOOLS = {
    "Read": ("file_path",),
    "Glob": ("path", "pattern"),
    "Grep": ("path", "glob"),
    "Write": ("file_path",),
}


def allowed_tools(session: Session) -> set[str]:
    return set(session.spec["tools"].split(","))


def snapshot_ids(value: object) -> list[str]:
    """Every `snapshot_id` value in a parsed JSON value."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "snapshot_id" and isinstance(item, str):
                found.append(item)
            else:
                found += snapshot_ids(item)
    elif isinstance(value, list):
        for item in value:
            found += snapshot_ids(item)
    return found


def result_text(result: dict) -> str:
    content = result.get("content")
    if isinstance(content, str):
        return content
    return "\n".join(part.get("text", "") for part in content or [] if isinstance(part, dict))


def load(session: Session) -> tuple[list[dict], dict[str, dict], dict]:
    """(tool uses in order, results by tool-use id, init event)."""
    uses, results, init = [], {}, {}
    for line in (session.record / "transcript.jsonl").read_text().splitlines():
        event = json.loads(line)
        if event.get("type") == "system" and event.get("subtype") == "init":
            init = event
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "tool_use":
                uses.append(part)
            elif part.get("type") == "tool_result":
                results[part["tool_use_id"]] = part
    return uses, results, init


def inside(path: str, roots: list[Path], cwd: Path) -> bool:
    resolved = (cwd / path).resolve() if path else cwd.resolve()
    return any(resolved == root.resolve() or root.resolve() in resolved.parents for root in roots)


def paths(name: str, arguments: dict) -> list[str]:
    """The places a file-tool call names. Patterns count only when absolute; their fixed prefix
    before the first wildcard is the place."""
    found = []
    for key in FILE_TOOLS[name]:
        value = arguments.get(key) or ""
        if key in ("pattern", "glob"):
            if not value.startswith(("/", "~")):
                continue
            value = value.split("*")[0].split("?")[0].split("{")[0].split("[")[0] or "/"
        found.append(value)
    return found


def audit(session: Session) -> dict:
    violations: list[str] = []
    notes: list[str] = []
    uses, results, init = load(session)
    allowed = allowed_tools(session)
    mcp = session.spec["mcp"]

    def permitted(name: str) -> bool:
        return name in allowed or (mcp is not None and name.startswith(f"mcp__{mcp}__"))

    for name in init.get("tools") or []:
        if not permitted(name):
            violations.append(f"tool offered outside the arm's set: {name}")
    servers = sorted(server.get("name") for server in init.get("mcp_servers") or [])
    if servers != ([mcp] if mcp else []):
        violations.append(f"MCP servers {servers}")

    page = session.page_ids()[0] if session.is_gt else None
    roots = [session.cwd, session.out]
    first_write = None
    seen: set[str] = set()
    for index, use in enumerate(uses):
        name, arguments = use["name"], use.get("input") or {}
        result = results.get(use["id"], {})
        refused = bool(result.get("is_error"))
        label = f"#{index + 1} {name} {json.dumps(arguments)[:160]}"
        if not permitted(name):
            (notes if refused else violations).append(f"tool outside the arm's set: {label}")
            continue
        if name in FILE_TOOLS and not all(
            inside(p, roots, session.cwd) for p in paths(name, arguments)
        ):
            (notes if refused else violations).append(f"path outside the workspace: {label}")
        if name == "Write":
            target = Path(arguments.get("file_path") or "")
            if target.parent.resolve() != session.out.resolve() or target.name not in OUTPUTS:
                (notes if refused else violations).append(f"write other than an output: {label}")
            elif target.name == "first-impression.md" and not refused:
                if first_write is None:
                    first_write = index
                else:
                    violations.append(f"first-impression.md written again: {label}")
        if name == "mcp__gt__getLepiterPageContents" and arguments.get("pageUid") != page:
            violations.append(f"another Lepiter page: {label}")
        if refused:
            notes.append(f"refused: {label}")
        if name.startswith("mcp__aip__") and not refused:
            seen |= check_snapshots(result_text(result), label, violations, notes)

    if first_write is None:
        violations.append("first-impression.md was never written")
    else:
        for use in uses[:first_write]:
            if not before_first_impression(session, use, page):
                violations.append(
                    f"before the first impression: {use['name']} {json.dumps(use.get('input'))[:160]}"
                )
    for name in OUTPUTS:
        if not (session.record / name).exists():
            violations.append(f"{name} is missing")

    if session.arm == "GA":
        log = session.win / "aip-log.json"
        if not log.exists():
            violations.append(f"{log} has not been exported")
        else:
            shutil.copy(log, session.record / "aip-log.json")
            seen |= check_snapshots(log.read_text(), "GA client log", violations, notes)

    record = json.loads((session.record / "session.json").read_text())
    transcript = (session.record / "transcript.jsonl").read_text()
    leaked = any(token in transcript for token in tokens(Path.home() / ".claude/.credentials.json"))
    if record.get("secret_scan") != "clean" or leaked or "sk-ant-" in transcript:
        violations.append("the transcript may contain credentials: do not publish it")

    return {
        "session": session.name,
        "verdict": "VOID" if violations else "CLEAN",
        "snapshots_seen": sorted(seen),
        "violations": violations,
        "notes": notes,
    }


def before_first_impression(session: Session, use: dict, page: str | None) -> bool:
    name, arguments = use["name"], use.get("input") or {}
    if name == "ToolSearch":
        return True
    if session.is_gt:
        return name == "mcp__gt__getLepiterPageContents" and arguments.get("pageUid") == page
    if name == "Read":
        return (session.cwd / arguments.get("file_path", "")).resolve() == (
            session.work / "task.md"
        ).resolve()
    return False


def check_snapshots(text: str, label: str, violations: list[str], notes: list[str]) -> set[str]:
    """The snapshot ids in one AIP answer; a non-frozen one is a violation."""
    try:
        value = json.loads(text)
    except ValueError:
        notes.append(f"AIP answer is not JSON: {label}")
        return set()
    ids = snapshot_ids(value)
    if not ids:
        notes.append(f"AIP answer without a snapshot (not scorable): {label}")
    for snapshot in sorted(set(ids)):
        if snapshot != FROZEN_SNAPSHOT:
            violations.append(f"snapshot {snapshot}: {label}")
    return set(ids)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    arm, attempt = args[0].rsplit("-", 1)
    session = Session(arm, int(attempt))
    if len(args) > 1:
        # A dry run: audit a probe record.
        session.record = session.dir / args[1]
    report = audit(session)
    (session.record / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{session.name}: {report['verdict']}")
    for violation in report["violations"]:
        print(f"  VIOLATION {violation}")
    print(f"  {len(report['notes'])} notes")
    return 0 if report["verdict"] == "CLEAN" else 3


if __name__ == "__main__":
    sys.exit(main())
