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
from typing import NamedTuple

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
INSIDE_SUFFIXES = (".127.0.0.1.nip.io", ".svc", ".cluster.local", ".local")
URL_CLIENTS = {"curl", "wget", "http", "https", "grpcurl", "nc", "telnet"}  # fmt: skip
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
SEPARATORS = {"|", "||", "&&", ";", "&", "(", ")", "|&", ";;"}
REDIRECTS = {">", ">>", "<", ">&", "&>", "&>>", ">|", "<&", "<>", "<<<"}
WRITE_REDIRECTS = {">", ">>", "&>", "&>>", ">|"}
WRAPPERS = {"sudo", "env", "timeout", "nohup", "time", "nice", "stdbuf", "watch", "xargs"}
SHELLS = {"sh", "bash", "zsh"}

READ_ONLY = {
    "ls", "cat", "head", "tail", "grep", "rg", "find", "wc", "sort", "uniq", "jq", "yq", "echo",
    "pwd", "cd", "tree", "file", "stat", "diff", "cut", "less", "date", "basename", "dirname",
    "realpath", "true", "test", "[", "printf", "column", "tr", "sleep",
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


class Segment(NamedTuple):
    """One simple command: its words (wrappers and assignments removed) and the files it writes
    through a redirection (`>`, `>>`, `&>`; never /dev/null or a file descriptor)."""

    words: list[str]
    writes: list[str]


def _lex(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""  # `#` inside a URL is not a comment; a leading `#` word is handled below
    try:
        return list(lexer)
    except ValueError:  # an unbalanced quote: fall back to whitespace words
        return line.split()


def _unwrap(words: list[str]) -> list[str]:
    """Drop leading VAR=value assignments and wrapper programs, so that the program that runs is
    first: `env X=1 timeout 5 curl ...`, `docker exec -it kafka curl ...`, `kubectl exec pod -- ...`."""
    while words:
        head = Path(words[0]).name
        if "=" in words[0] and not words[0].startswith("-"):
            words = words[1:]
        elif head in WRAPPERS:
            words = words[1:]
            while words and (words[0].startswith("-") or words[0][:1].isdigit()):
                words = words[1:]
        elif head == "docker" and len(words) > 1 and words[1] == "exec":
            rest = [w for w in words[2:] if not w.startswith("-")]
            options = [w for w in words[2:] if w.startswith("-")]
            # `-e VAR=...`, `-w DIR`, `-u USER` take a value: drop it with the option.
            for option in options:
                if option in ("-e", "--env", "-w", "--workdir", "-u", "--user") and rest:
                    rest = rest[1:]
            return _unwrap(rest[1:]) if rest else []
        elif head == "kubectl" and "exec" in words[1:3] and "--" in words:
            words = words[words.index("--") + 1 :]
        else:
            return words
    return words


def segments(command: str) -> list[Segment]:
    """Split a shell command into simple commands. Quotes are respected (`grep 'a|b'` is one word);
    `|`, `||`, `&&`, `;`, `&`, newlines and `$( )` separate commands; heredoc bodies are skipped; a
    `bash -c STRING` is split again."""
    found: list[Segment] = []
    heredoc: str | None = None
    for line in command.splitlines():
        if heredoc is not None:
            if line.strip() == heredoc:
                heredoc = None
            continue
        words: list[str] = []
        writes: list[str] = []
        tokens = _lex(line)
        at = 0
        while at <= len(tokens):
            token = tokens[at] if at < len(tokens) else ";"
            at += 1
            if token in SEPARATORS or (token.startswith("#") and not words):
                if token.startswith("#"):
                    at = len(tokens)
                words = _unwrap(words)
                if words and Path(words[0]).name in SHELLS and "-c" in words:
                    script_at = words.index("-c") + 1
                    if script_at < len(words):
                        found += segments(words[script_at])
                elif words or writes:
                    found.append(Segment(words, writes))
                words, writes = [], []
            elif token in ("<<", "<<-"):
                if at < len(tokens):
                    heredoc = tokens[at].strip("'\"")
                    at += 1
            elif token in REDIRECTS:
                target = tokens[at] if at < len(tokens) else ""
                at += 1
                if words and words[-1].isdigit():
                    words.pop()  # the file descriptor of `2>`
                if token in WRITE_REDIRECTS and target != "/dev/null" and not target.isdigit():
                    writes.append(target)
            elif token == "$":
                continue
            else:
                words.append(token)
    return found


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


def network_problem(words: list[str]) -> str | None:
    """Why this command reaches outside the environment, or None. `words` is unwrapped, so the
    program that runs is first (`docker exec kafka curl ...` is a curl)."""
    if not words:
        return None
    program, rest = Path(words[0]).name, words[1:]
    if program in ALWAYS_OUTSIDE:
        subs = ALWAYS_OUTSIDE[program]
        verbs = _subcommand_words(rest)
        if subs is None or (verbs and verbs[0] in subs):
            return f"{program} {' '.join(verbs[:1])}".strip()
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


def _without_heredocs(command: str) -> str:
    kept, heredoc = [], None
    for line in command.splitlines():
        if heredoc is not None:
            if line.strip() == heredoc:
                heredoc = None
            continue
        kept.append(line)
        match = re.search(r"<<-?\s*['\"]?([A-Za-z_][\w]*)", line)
        if match:
            heredoc = match[1]
    return "\n".join(kept)


def _locators(tool: str, data: object) -> list[str]:
    """The parts of a tool input that say where it reads, writes or connects: paths, patterns,
    URLs and commands (without heredoc bodies). File content is not a locator: a plan may quote
    AIP's own producer name."""
    if not isinstance(data, dict):
        return _strings(data)
    if tool in FILE_WRITE_TOOLS or tool == "Read":
        return [str(data.get(k, "")) for k in ("file_path", "notebook_path")]
    if tool == "Bash":
        return [_without_heredocs(str(data.get("command", "")))]
    return _strings(data)


def _withheld(text: str, withheld: list[str]) -> str | None:
    """The first withheld path (at a path boundary, so `aip-v08-i4a` does not match
    `aip-v08-i4a-run`) or withheld name in the text."""
    for path in withheld:
        if path and re.search(re.escape(path.rstrip("/")) + r"(?![\w.-])", text):
            return path
    for marker in WITHHELD_MARKERS:
        if re.search(r"(?<![\w-])" + re.escape(marker) + r"(?![\w-])", text):
            return marker
    return None


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
        joined = "\n".join(_locators(tool, data))
        if marker := _withheld(joined, withheld):
            hits.append(_hit("WITHHELD_PATH", session, number, tool, marker, denied))
        if tool in WEB_TOOLS:
            hits.append(_hit("WEB_TOOL", session, number, tool, joined[:200], denied))
        if ".claude/" in joined or any(d and d in joined for d in config_dirs):
            hits.append(_hit("SETTINGS_WRITE", session, number, tool, joined[:200], denied))
        if tool == "Bash":
            command = (data or {}).get("command", "")
            for segment in segments(command):
                problem = network_problem(segment.words)
                if problem:
                    hits.append(_hit("NETWORK_OUTSIDE", session, number, tool, problem, denied))
                change = planning_change(segment.words) if segment.words else None
                if segment.writes:
                    change = f"writes {segment.writes}"
                if session == "planning" and change:
                    hits.append(_hit("PLANNING_CHANGE", session, number, tool, change, denied))
        if session == "planning" and tool in FILE_WRITE_TOOLS:
            name = Path(str((data or {}).get("file_path", ""))).name
            if name not in PLAN_FILES:
                hits.append(_hit("PLANNING_CHANGE", session, number, tool, name, denied))
        # The MCP tool takes its arguments wrapped: {"request": {"mode": "query", ...}} (checked on
        # a real transcript, Claude Code 2.1.312).
        request = data.get("request", data) if isinstance(data, dict) else None
        if tool == BINDING_TOOL and isinstance(request, dict) and request.get("mode") == "query":
            requests.append(
                {
                    "index": len(requests),
                    "session": session,
                    "line": number,
                    "request": request,
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
