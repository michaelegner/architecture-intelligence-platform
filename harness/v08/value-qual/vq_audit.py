"""v0.8 value qualification (spec §6.4-§6.5): the audit of one session. It runs the v0.8 I4 audit
(`i4/audit.py`, session `planning`, with `answers.json` and `requests.json` allowed as outputs) and
adds:

- AIP_IN_NEGATIVE (`-` sessions): an AIP MCP tool call (`mcp__aip__*`, `mcp__plugin_aip_*`), or a command (not a v0.8 read-only one) that
  names the AIP or Neo4j ports (8000, 7474, 7687) or their containers;
- TEAM_SCOPE (T sessions): a `docker`, `kubectl`, `helm`, `rpk`, `k3d` or Kafka program, a command
  (not a v0.8 read-only one) that names a broker host or port (9092, 19092, 29092), or a tool input
  that names a kubeconfig;
- TEAM_LEAK (T sessions): a tool result with a string that exists only in an excluded repository,
  unless an R2 grant of a repository that holds it came earlier in the session;
- EXTERNAL_TOOL: a call to an MCP tool that is not AIP's (the account's claude.ai connectors reach
  every session, also with a new config dir);
- REQUEST_OUTSIDE_CATALOGUE (T sessions): an operator message after the first that is not a reply
  file of the session, or a recorded entry that differs from the mechanical match;
- FIRST_MESSAGE: the first operator message is not the card's first message;
- withheld output: the v0.8 canaries and the names of this experiment's frozen materials.

A denied call is still a hit. Every tool call is listed as attempted, and as received when its result
is not an error.

    vq_audit.py RUN_HOME SESSION TRANSCRIPT.jsonl [...]
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i4"))
sys.path.insert(0, str(HERE))

import audit
import vq_format
import vq_requests

FIRST_MESSAGE = (
    "Read TASK.md. Plan the move as TASK.md describes. Write plan.json, plan.md and answers.json "
    "in the workspace, then stop."
)
EXTRA_CANARIES = (
    "comprehension-key",
    "comprehension key",
    "claim-rules",
    "r2-list.json",
    "v08-value-qualification",
)
EXTRA_WITHHELD = ("v08-value-qualification-evidence",)
# Any MCP tool of AIP: `mcp__aip__...`, and plugin forms such as `mcp__plugin_aip_aip__...`.
AIP_TOOL = re.compile(r"^mcp__(?:.*_)?aip(?:_|$)", re.IGNORECASE)
AIP_PORTS = re.compile(r"(\b(8000|7474|7687)\b|\bneo4j\b|aip-v08-i4-aip)", re.IGNORECASE)
TEAM_PROGRAMS = {"docker", "kubectl", "helm", "rpk", "k3d", "kcat", "kafkacat"}
BROKER_PORTS = re.compile(r"\b(9092|19092|29092)\b")
NETWORK_PROGRAMS = audit.URL_CLIENTS | audit.REMOTE_TOOLS
BROKER_HOSTS = re.compile(r"\b(redpanda|kafka)\b(?![.-])")
KUBECONFIG = re.compile(r"(\.kube/|kubeconfig)", re.IGNORECASE)
# A string -> the excluded repositories that hold it (checked against the clones at the freeze
# commits: none is in a team repository or a card variant).
LEAK_CANARIES = {
    'brokers: "redpanda:29092"': ("ecommerce-infrastructure",),
    'default-group-id: "ecommerce-product-query-service"': (
        "ecommerce-infrastructure",
        "ecommerce-product-query-service",
    ),
    'default-group-id: "ecommerce-category-query-service"': (
        "ecommerce-infrastructure",
        "ecommerce-category-query-service",
    ),
    'database: "product-query"': ("ecommerce-infrastructure", "ecommerce-product-query-service"),
    'database: "category-query"': ("ecommerce-infrastructure", "ecommerce-category-query-service"),
    "catalog-attribute-events": ("ecommerce-infrastructure", "ecommerce-product-query-service"),
    "ecommerce-product-query-service/internal": ("ecommerce-product-query-service",),
    "ecommerce-category-query-service/internal": ("ecommerce-category-query-service",),
}
GRANT = re.compile(r"Added to src/([\w.-]+)\.")


def _text(content: object) -> str:
    return "\n".join(audit._strings(content))


def load(paths: list[Path]) -> list[dict]:
    """The entries of a session's transcript files in order, the file with the first message first.
    An entry that a later file repeats (same `uuid`, as a resumed session may copy the history) is
    kept once."""
    ordered = sorted(paths, key=lambda p: (FIRST_MESSAGE not in p.read_text(), str(p)))
    entries, seen = [], set()
    for path in ordered:
        for raw in path.read_text().splitlines():
            if not raw.strip():
                continue
            entry = json.loads(raw)
            uid = entry.get("uuid")
            if uid is not None and uid in seen:
                continue
            seen.add(uid)
            entries.append({**entry, "__file": path.name})
    return entries


def events_of(entries: list[dict]) -> list[dict]:
    """Operator messages (`prompt`) and tool calls with their results, in order. A subagent
    (sidechain) message is not an operator message; a tool call is listed once by its id."""
    found, results, calls = [], {}, set()
    for entry in entries:
        content = (entry.get("message") or {}).get("content")
        if entry.get("type") == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    results[block.get("tool_use_id")] = block
    for number, entry in enumerate(entries, start=1):
        content = (entry.get("message") or {}).get("content")
        if entry.get("type") == "user" and not entry.get("isSidechain"):
            text = content if isinstance(content, str) else None
            if isinstance(content, list):
                texts = [
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                text = "\n".join(texts) if texts and len(texts) == len(content) else None
            if text is not None and not entry.get("isMeta"):
                found.append({"kind": "prompt", "line": number, "text": text})
        elif entry.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                    continue
                if block.get("id") in calls:
                    continue
                calls.add(block.get("id"))
                result = results.get(block.get("id"))
                found.append(
                    {
                        "kind": "call",
                        "line": number,
                        "transcript": entry["__file"],
                        "id": block.get("id"),
                        "tool": block.get("name", ""),
                        "input": block.get("input"),
                        "result": result,
                        "received": result is not None and not result.get("is_error"),
                    }
                )
    return found


def events(path: Path) -> list[dict]:
    return events_of(load([path]))


def _hit(kind: str, line: int, tool: str, detail: str, denied: bool) -> dict:
    return audit._hit(kind, "planning", line, tool, detail, denied)


def _programs(command: str) -> set[str]:
    """The program of every simple command, before and after `docker exec` / `kubectl exec` are
    unwrapped (`docker exec redpanda rpk ...` runs both `docker` and `rpk`). Arguments are not
    programs: `grep -rn docker src/` runs grep only."""
    command = audit._without_heredocs(command)
    found = {Path(s.words[0]).name for s in audit.segments(command) if s.words}
    words: list[str] = []
    for token in [*audit._lex(command), ";"]:
        if token in audit.SEPARATORS or token == "\n":
            while words and ("=" in words[0] or Path(words[0]).name in audit.WRAPPERS):
                words = words[1:]
            if words:
                found.add(Path(words[0]).name)
            words = []
        elif token not in audit.REDIRECTS:
            words.append(token)
    return found


def _network_command(tool: str, data: object) -> str:
    """The command, unless every program in it is on the v0.8 read-only list: a port in a `grep`
    pattern is reading, not a connection."""
    if tool != "Bash" or not isinstance(data, dict):
        return ""
    command = audit._without_heredocs(str(data.get("command", "")))
    return "" if _programs(command) <= audit.READ_ONLY else command


def scope_hits(found: list[dict], card_type: str) -> list[dict]:
    hits = []
    for event in found:
        if event["kind"] != "call":
            continue
        tool, data, denied = event["tool"], event["input"], not event["received"]
        locators = "\n".join(audit._locators(tool, data))
        network = _network_command(tool, data)
        if tool.startswith("mcp__") and not AIP_TOOL.search(tool):
            hits.append(_hit("EXTERNAL_TOOL", event["line"], tool, locators[:200], denied))
        if card_type.endswith("-") and (AIP_TOOL.search(tool) or AIP_PORTS.search(network)):
            hits.append(_hit("AIP_IN_NEGATIVE", event["line"], tool, locators[:200], denied))
        if card_type.startswith("T"):
            command = str((data or {}).get("command", "")) if tool == "Bash" else ""
            programs = _programs(command) if command else set()
            kafka = {p for p in programs if p.startswith("kafka-") and p.endswith(".sh")}
            if (
                (programs & TEAM_PROGRAMS)
                or kafka
                or BROKER_PORTS.search(network)
                or (programs & NETWORK_PROGRAMS and BROKER_HOSTS.search(network))
                or KUBECONFIG.search(locators)
            ):
                hits.append(_hit("TEAM_SCOPE", event["line"], tool, locators[:200], denied))
    return hits


def leak_hits(found: list[dict]) -> list[dict]:
    hits, granted = [], set()
    for event in found:
        if event["kind"] == "prompt":
            granted |= set(GRANT.findall(event["text"]))
            continue
        if not event["received"]:
            continue
        output = _text((event["result"] or {}).get("content"))
        for canary, holders in LEAK_CANARIES.items():
            if canary in output and not granted & set(holders):
                hits.append(_hit("TEAM_LEAK", event["line"], event["tool"], canary, False))
    return hits


def request_hits(found: list[dict], session_dir: Path, task_card: Path) -> list[dict]:
    """Every operator message after the first is a reply file; every recorded entry is the
    mechanical match of its request."""
    hits = []
    replies_dir = session_dir / "replies"
    replies = (
        {p.read_text().strip() for p in replies_dir.iterdir()} if replies_dir.is_dir() else set()
    )
    prompts = [e for e in found if e["kind"] == "prompt" and e["text"].strip() != FIRST_MESSAGE]
    for prompt in prompts:
        if prompt["text"].strip() not in replies:
            hits.append(
                _hit("REQUEST_OUTSIDE_CATALOGUE", prompt["line"], "", prompt["text"][:200], False)
            )
    record_path = session_dir / "requests-record.json"
    record = json.loads(record_path.read_text()) if record_path.exists() else []
    r2 = json.loads(vq_requests.R2_LIST.read_text())["repositories"]
    item_schema = vq_format.schema("requests-schema", task_card)["items"]
    validator = vq_format.Draft202012Validator(item_schema)
    for entry in record:
        request = entry["request"]
        valid = isinstance(request, dict) and not any(True for _ in validator.iter_errors(request))
        expected = vq_requests.entry_for(request, r2) if valid else "R3"
        if entry["entry"] != expected or (entry.get("grant") and expected != "R2"):
            hits.append(_hit("REQUEST_OUTSIDE_CATALOGUE", 0, "", json.dumps(entry)[:200], False))
    return hits


def first_message_hits(found: list[dict]) -> list[dict]:
    prompts = [e for e in found if e["kind"] == "prompt"]
    if not prompts or prompts[0]["text"].strip() != FIRST_MESSAGE:
        line = prompts[0]["line"] if prompts else 0
        return [
            _hit("FIRST_MESSAGE", line, "", (prompts[0]["text"] if prompts else "")[:200], False)
        ]
    return []


def calls(found: list[dict]) -> list[dict]:
    return [
        {
            "transcript": e["transcript"],
            "line": e["line"],
            "tool": e["tool"],
            "attempted": True,
            "received": e["received"],
        }
        for e in found
        if e["kind"] == "call"
    ]


def audit_transcripts(
    paths: list[Path],
    card_type: str,
    session_dir: Path | None,
    withheld: list[str],
    config_dirs: list[str],
    requests: list[dict],
) -> list[dict]:
    """All hits of one session over its transcript files."""
    allowed = audit.PLAN_FILES | {"answers.json"}
    if card_type.startswith("T"):
        allowed |= {"requests.json"}
    hits = []
    for path in paths:
        hits += audit.audit_session(path, "planning", withheld, config_dirs, requests, allowed)
    found = events_of(load(paths))
    hits += scope_hits(found, card_type) + first_message_hits(found)
    for event in found:
        if event["kind"] == "call" and event["received"]:
            output = _text((event["result"] or {}).get("content"))
            if canary := next((c for c in EXTRA_CANARIES if c in output), None):
                hits.append(_hit("WITHHELD_OUTPUT", event["line"], event["tool"], canary, False))
    if card_type.startswith("T"):
        hits += leak_hits(found)
        if session_dir is not None:
            hits += request_hits(found, session_dir, vq_format.card(card_type))
    return hits


def withheld_locations(run_home: Path, session_dir: Path) -> list[str]:
    """Every AIP worktree, the operator state, the run home's denied directories and every other
    session (spec §6.1-§6.2)."""
    listed = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{HERE.parent / "i4/withheld.sh"}"; printf "%s\\n" "${{WITHHELD[@]}}" "${{OPERATOR_STATE[@]}}"',
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    found = [p for p in listed if p] + [
        str(run_home / n) for n in ("package", "src", "aip", "catalogue")
    ]
    sessions = run_home / "sessions"
    found += [str(p) for p in sessions.iterdir() if p != session_dir] if sessions.is_dir() else []
    return found


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    run_home = Path(args[0]).resolve()
    session_dir = run_home / "sessions" / args[1]
    transcripts = [Path(p) for p in args[2:]]
    card_type = json.loads((session_dir / "session.json").read_text())["type"]
    withheld = withheld_locations(run_home, session_dir) + list(EXTRA_WITHHELD)
    requests: list[dict] = []
    config = [str(session_dir / "claude")]
    hits = audit_transcripts(transcripts, card_type, session_dir, withheld, config, requests)
    listing = calls(events_of(load(transcripts)))
    result = {
        "session": args[1],
        "type": card_type,
        "clean": not hits,
        "hits": hits,
        "calls": listing,
    }
    (session_dir / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    (session_dir / "agent-requests.json").write_text(
        json.dumps(requests, indent=2, sort_keys=True) + "\n"
    )
    print(f"audit {args[1]}: {len(hits)} hit(s), {len(listing)} tool call(s)")
    return 0 if not hits else 2


if __name__ == "__main__":
    sys.exit(main())
