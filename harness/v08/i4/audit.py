"""v0.8 I4 §4.4: the independence audit of both agent sessions. It fails closed.

It reads the Claude Code session transcripts (JSONL) and checks every tool call the agent made,
whatever its result: a call that the settings denied still counts. A hit is:

- WITHHELD_PATH: a withheld path or name in any tool input (the AIP checkout, the AIP repository
  name, `harness/v08`, the I3/I4 evidence, the keys);
- WEB_TOOL: WebFetch or WebSearch;
- NETWORK_OUTSIDE: a network command whose target is outside the environment, or cannot be
  classified. Inside are localhost, the Docker network names and the cluster's own hosts. Fetching
  tools (git, gh, package managers, helm repositories, docker pull) are always outside;
- SETTINGS_WRITE: any tool input that names `.claude/` or a session config dir;
- PLANNING_CHANGE: in the planning session, a command that is not on the read-only list, or a file
  write other than plan.json / plan.md;
- UNPARSEABLE: a transcript line that is not JSON.

It also extracts the agent's `get_binding_picture` query requests, with the answer the agent saw,
for `record_answers.py`.
"""

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

WITHHELD_MARKERS = (
    "architecture-intelligence-platform",
    "ArchitectureIntelligencePlatform",
    "harness/v08",
    "i3-evidence",
    "i4-evidence",
    "expected-after",
    "plan-key",
)
WEB_TOOLS = {"WebFetch", "WebSearch"}
BINDING_TOOL = "mcp__aip__get_binding_picture"
FILE_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PLAN_FILES = {"plan.json", "plan.md"}

INSIDE_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "kafka",
    "redpanda",
    "host.k3d.internal",
}
INSIDE_SUFFIXES = (".nip.io", ".svc", ".cluster.local", ".local")
URL_CLIENTS = {"curl", "wget", "http", "https", "grpcurl", "nc", "telnet"}
# Options of the URL clients that take a value, which is not a target.
VALUE_OPTIONS = {
    "-H", "--header", "-d", "--data", "--data-raw", "--data-binary", "-o", "--output", "-X",
    "--request", "-u", "--user", "-F", "--form", "-w", "--write-out", "-m", "--max-time", "-A",
    "--user-agent", "-e", "--referer", "-b", "--cookie", "-c", "--cookie-jar", "-T",
    "--upload-file", "-O", "--output-document", "--header-file", "-import-path", "-proto", "-d@",
    "-max-time", "-H@", "-rpc-header", "-authority", "-w@",
}  # fmt: skip
ADDRESS_OPTIONS = {"--connect-to", "--resolve"}
ALWAYS_OUTSIDE = {
    "git": {"clone", "fetch", "pull", "ls-remote", "submodule", "push"},
    "gh": None,
    "pip": None,
    "pip3": None,
    "uv": {"pip", "add", "sync", "tool", "run"},
    "npm": None,
    "npx": None,
    "go": {"get", "install", "mod"},
    "helm": {"repo", "pull", "dependency", "dep", "search"},
    "docker": {"pull", "login", "search"},
    "apt": None,
    "apt-get": None,
}
SEGMENT_SPLIT = re.compile(r"\|\||&&|[|;&\n]|\$\(|`")

READ_ONLY = {
    "ls", "cat", "head", "tail", "grep", "rg", "find", "wc", "sort", "uniq", "jq", "yq", "echo",
    "pwd", "cd", "tree", "file", "stat", "diff", "cut", "less", "date", "basename", "dirname",
    "realpath", "true", "test", "[", "printf", "column", "tr", "xargs",
}  # fmt: skip
READ_ONLY_SUB = {
    "git": {"log", "show", "status", "diff", "ls-files", "rev-parse", "branch", "blame", "grep"},
    "kubectl": {"get", "describe", "logs", "version", "explain", "api-resources", "top"},
    "helm": {"template", "show", "list", "get", "version", "lint", "history"},
    "rpk": {"topic", "group", "cluster", "version"},
}
RPK_READ = {"list", "describe", "info", "health", "consume"}
DOCKER_READ = {"ps", "inspect", "logs", "images", "image", "network", "version", "info", "compose"}
DOCKER_COMPOSE_READ = {"ps", "ls", "config", "logs", "images"}
KAFKA_READ_FLAGS = {"--list", "--describe"}
KAFKA_WRITE_FLAGS = {"--create", "--delete", "--alter", "--reset-offsets"}
GLOBAL_VALUE_OPTIONS = {
    "-n",
    "--namespace",
    "--context",
    "--kubeconfig",
    "-C",
    "--kube-context",
    "-X",
}


def _hit(kind: str, session: str, line: int, tool: str, detail: str, denied: bool) -> dict:
    return {
        "kind": kind,
        "session": session,
        "line": line,
        "tool": tool,
        "detail": detail,
        "denied": denied,
    }


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def segments(command: str) -> list[list[str]]:
    words = []
    for part in SEGMENT_SPLIT.split(command):
        try:
            tokens = shlex.split(part, comments=True)
        except ValueError:
            tokens = part.split()
        while tokens and ("=" in tokens[0] and not tokens[0].startswith("-")):
            tokens = tokens[1:]  # leading VAR=value assignments
        for prefix in ("sudo", "env", "timeout", "nohup", "time"):
            while tokens and tokens[0] == prefix:
                tokens = tokens[1:]
                while tokens and (tokens[0].startswith("-") or tokens[0][:1].isdigit()):
                    tokens = tokens[1:]
        if tokens:
            words.append(tokens)
    return words


def _host(token: str) -> str | None:
    match = re.match(r"^(?:[a-z][a-z0-9+.-]*://)?(?:[^@/\s]+@)?(\[[^\]]+\]|[^:/\s]+)", token)
    return match[1].strip("[]").lower() if match else None


def _inside(host: str) -> bool:
    return host in INSIDE_HOSTS or host.endswith(INSIDE_SUFFIXES) or host.startswith("k3d-")


def _positional(args: list[str]) -> list[str]:
    """The non-option arguments of a URL client: its targets. Option values are skipped; a
    `--connect-to`/`--resolve` value names an address, so it is a target too."""
    found, skip = [], False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg in ADDRESS_OPTIONS:
            skip = True
            continue
        if arg.startswith("-"):
            skip = arg in VALUE_OPTIONS
            continue
        found.append(arg)
    for at, arg in enumerate(args[:-1]):
        if arg in ADDRESS_OPTIONS:
            found += [part for part in args[at + 1].split(":") if part and not part.isdigit()]
    return found


def network_problem(tokens: list[str]) -> str | None:
    """Why this command segment reaches outside the environment, or None. The program may be
    wrapped (`docker exec kafka curl ...`), so every token is a candidate program."""
    for at, word in enumerate(tokens):
        program = Path(word).name
        rest = tokens[at + 1 :]
        if program in ALWAYS_OUTSIDE:
            subs = ALWAYS_OUTSIDE[program]
            if subs is None or (rest and rest[0] in subs):
                return f"{program} {' '.join(rest[:1])}".strip()
        if program in URL_CLIENTS:
            targets = [t for t in _positional(rest) if not t.isdigit()]  # nc HOST PORT
            if program == "grpcurl":  # grpcurl [opts] HOST:PORT SERVICE/METHOD
                targets = [t for t in targets if "/" not in t]
            hosts = [_host(t) for t in targets]
            if not hosts or any(h is None or not _inside(h) for h in hosts):
                return f"{program} target {targets or '(none found)'}"
    return None


def _subcommand_words(args: list[str]) -> list[str]:
    """The words after the global options (`kubectl -n dev get ...`, `git -C dir log ...`)."""
    words, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg.startswith("-"):
            skip = arg in GLOBAL_VALUE_OPTIONS
        else:
            words.append(arg)
    return words


def planning_change(tokens: list[str]) -> str | None:
    """None when the segment is on the read-only list."""
    program = Path(tokens[0]).name
    rest = tokens[1:]
    if program in READ_ONLY:
        return None
    if program == "sed" and not any(t.startswith("-i") for t in rest):
        return None
    words = _subcommand_words(rest)
    if program in READ_ONLY_SUB and words and words[0] in READ_ONLY_SUB[program]:
        if program == "rpk" and not (len(words) > 1 and words[1] in RPK_READ):
            return " ".join(tokens[:3])
        return None
    if program == "docker" and rest:
        if rest[0] == "exec":
            inner = [t for t in rest[1:] if not t.startswith("-")][1:]
            return planning_change(inner) if inner else "docker exec"
        if rest[0] == "compose":
            subs = [t for t in rest[1:] if not t.startswith("-")]
            return None if subs and subs[-1] in DOCKER_COMPOSE_READ else "docker compose"
        if rest[0] in DOCKER_READ:
            return None
    if (
        program.startswith("kafka-")
        and program.endswith(".sh")
        and KAFKA_READ_FLAGS & set(rest)
        and not KAFKA_WRITE_FLAGS & set(rest)
    ):
        return None
    return " ".join(tokens[:3])


def _tool_calls(path: Path, session: str, hits: list[dict]):
    """(line number, tool name, input, result) for every tool call, in order."""
    calls, results = [], {}
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            hits.append(_hit("UNPARSEABLE", session, number, "", path.name, False))
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if entry.get("type") == "assistant" and block.get("type") == "tool_use":
                calls.append((number, block.get("id"), block.get("name", ""), block.get("input")))
            elif entry.get("type") == "user" and block.get("type") == "tool_result":
                results[block.get("tool_use_id")] = block
    return [(n, name, data, results.get(tool_id)) for n, tool_id, name, data in calls]


def _answer(result: dict | None) -> dict | None:
    if result is None or result.get("is_error"):
        return None
    content = result.get("content")
    text = (
        content
        if isinstance(content, str)
        else "".join(b.get("text", "") for b in content or [] if isinstance(b, dict))
    )
    try:
        answer = json.loads(text)
    except json.JSONDecodeError:
        return None
    return answer if isinstance(answer, dict) else None


def audit_session(
    path: Path, session: str, withheld: list[str], config_dirs: list[str], requests: list[dict]
) -> list[dict]:
    hits: list[dict] = []
    for number, tool, data, result in _tool_calls(path, session, hits):
        denied = bool(result and result.get("is_error"))
        texts = _strings(data)
        joined = "\n".join(texts)
        for marker in (*withheld, *WITHHELD_MARKERS):
            if marker and marker in joined:
                hits.append(_hit("WITHHELD_PATH", session, number, tool, marker, denied))
                break
        if tool in WEB_TOOLS:
            hits.append(_hit("WEB_TOOL", session, number, tool, joined[:200], denied))
        if ".claude/" in joined or any(d and d in joined for d in config_dirs):
            hits.append(_hit("SETTINGS_WRITE", session, number, tool, joined[:200], denied))
        if tool == "Bash":
            command = (data or {}).get("command", "")
            for tokens in segments(command):
                problem = network_problem(tokens)
                if problem:
                    hits.append(_hit("NETWORK_OUTSIDE", session, number, tool, problem, denied))
                if session == "planning" and (change := planning_change(tokens)):
                    hits.append(_hit("PLANNING_CHANGE", session, number, tool, change, denied))
        if session == "planning" and tool in FILE_WRITE_TOOLS:
            name = Path(str((data or {}).get("file_path", ""))).name
            if name not in PLAN_FILES:
                hits.append(_hit("PLANNING_CHANGE", session, number, tool, name, denied))
        if tool == BINDING_TOOL and isinstance(data, dict) and data.get("mode") == "query":
            requests.append(
                {
                    "index": len(requests),
                    "session": session,
                    "line": number,
                    "request": data,
                    "transcript_answer": _answer(result),
                }
            )
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--planning", type=Path, nargs="+", required=True)
    parser.add_argument("--execution", type=Path, nargs="*", default=[])
    parser.add_argument("--withheld", action="append", default=[], help="a withheld path")
    parser.add_argument("--config-dir", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--requests-out", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.withheld:
        parser.error("name the AIP checkout with --withheld")
    requests: list[dict] = []
    hits = []
    for session, paths in (("planning", args.planning), ("execution", args.execution)):
        for path in paths:
            hits += audit_session(path, session, args.withheld, args.config_dir, requests)
    args.out.write_text(json.dumps({"hits": hits, "clean": not hits}, indent=2) + "\n")
    args.requests_out.write_text(json.dumps(requests, indent=2, sort_keys=True) + "\n")
    print(f"audit: {len(hits)} hit(s); {len(requests)} binding-picture request(s)")
    return 0 if not hits else 2


if __name__ == "__main__":
    sys.exit(main())
