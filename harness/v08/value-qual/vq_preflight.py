"""v0.8 value qualification (spec §6.1-§6.2, §6.5): the operator checks before each session. It fails
closed: any problem stops the session.

- the workspace holds only the setup output, and the config dir only the settings and the login;
- every clone in the workspace is at its freeze commit and clean;
- `-`: no AIP entry in `.mcp.json`, no AIP MCP allow rule, and no AIP or Neo4j container
  (`docker ps -a`); `+`: AIP answers with the recorded snapshot id (`vq_aip.sh check`);
- F: the broker state check (`vq_broker_check.py`);
- host scan: no copy of an excluded repository (T) or of AIP's inputs or the frozen keys (all types)
  exists outside the denied locations.

    vq_preflight.py RUN_HOME SESSION
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import vq_audit

FREEZE = REPO / "docs/specifications/0.7.2/i2-evidence/sokol111/freeze.md"
SETUP_FILES = {"src", "TASK.md", "plan.schema.json", "answers.schema.json", "requests.schema.json", ".mcp.json"}  # fmt: skip
CONFIG_FILES = {"settings.json", ".credentials.json"}
EXCLUDED_REPOSITORIES = re.compile(
    r"^(ecommerce-infrastructure|ecommerce-product-query-service.*|ecommerce-category-query-service.*)$"
)
# AIP's inputs, the v0.8 keys and captures, and the frozen materials of this experiment.
WITHHELD_NAMES = re.compile(
    r"^(event-topic-lookup\.json|kafka-consumer-state\.json|plan-key\.json|expected-after\.json"
    r"|comprehension-key\.json|claim-rules\.json|r2-list\.json"
    r"|S1-13-groups-describe\.txt|v08-value-qualification-evidence|i[1-4]-evidence|!sokol111)$"
)
SCAN_ROOTS = ("~", "/tmp", "/var/tmp", "/opt", "/srv")
PRUNE = {"node_modules", ".git", "snap", ".cache", ".npm", ".rustup", ".cargo"}
CONTAINER_NAMES = re.compile(r"(aip|neo4j)", re.IGNORECASE)


def freeze_commits(text: str) -> dict[str, str]:
    return dict(re.findall(r"`Sokol111/([\w.-]+)` \| `([0-9a-f]{40})`", text))


def _inside(path: str, roots: list[str]) -> bool:
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


def host_scan(roots: list[Path], denied: list[str], team: bool) -> list[str]:
    """Every path outside the denied locations whose name is an excluded repository (T only) or a
    withheld name. Symlinks are not followed."""
    denied = [os.path.realpath(d) for d in denied]
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for top, dirs, files in os.walk(root, followlinks=False):
            if _inside(os.path.realpath(top), denied):
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in PRUNE]
            for name in dirs + files:
                path = os.path.join(top, name)
                if _inside(os.path.realpath(path), denied):
                    continue
                if WITHHELD_NAMES.match(name) or (team and EXCLUDED_REPOSITORIES.match(name)):
                    found.append(path)
    return sorted(found)


def workspace_problems(session_dir: Path, card_type: str) -> list[str]:
    problems = []
    workspace, config = session_dir / "workspace", session_dir / "claude"
    extra = sorted(set(os.listdir(workspace)) - SETUP_FILES)
    if extra:
        problems.append(f"the workspace has more than the setup output: {extra}")
    extra = sorted(set(os.listdir(config)) - CONFIG_FILES)
    if extra:
        problems.append(f"the config dir is not new: {extra}")
    has_mcp = (workspace / ".mcp.json").exists()
    settings = json.loads((config / "settings.json").read_text())
    allows_aip = any(vq_audit.AIP_TOOL.search(r) for r in settings["permissions"]["allow"])
    if card_type.endswith("-") and (
        has_mcp or allows_aip or settings.get("enableAllProjectMcpServers")
    ):
        problems.append("a session without AIP has AIP registered")
    if card_type.endswith("+") and not (has_mcp and allows_aip):
        problems.append("a session with AIP does not register it")
    commits = freeze_commits(FREEZE.read_text())
    for repository in sorted(os.listdir(workspace / "src")):
        clone = workspace / "src" / repository
        head = _git(clone, "rev-parse", "HEAD")
        if head != commits.get(repository):
            problems.append(f"{repository} is at {head}, not at its freeze commit")
        if _git(clone, "status", "--porcelain"):
            problems.append(f"{repository} has local changes")
    return problems


def _git(clone: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(clone), *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def container_problems(listing: str) -> list[str]:
    """`docker ps -a --format '{{.Names}} {{.Image}}'`: no AIP or Neo4j container in a `-` session."""
    return [
        f"container present: {line}"
        for line in listing.splitlines()
        if CONTAINER_NAMES.search(line)
    ]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    run_home = Path(args[0]).resolve()
    session_dir = run_home / "sessions" / args[1]
    record = json.loads((session_dir / "session.json").read_text())
    card_type = record["type"]
    problems = workspace_problems(session_dir, card_type)

    def run(*command: str) -> subprocess.CompletedProcess:
        return subprocess.run(command, capture_output=True, text=True, check=False)

    if card_type.endswith("-"):
        listing = run("docker", "ps", "-a", "--format", "{{.Names}} {{.Image}}")
        problems += container_problems(listing.stdout)
    else:
        aip = run(str(HERE / "vq_aip.sh"), str(run_home), "check")
        if aip.returncode != 0:
            problems.append(f"AIP check failed: {aip.stderr.strip()}")
    if card_type.startswith("F"):
        out = session_dir / "broker-check.json"
        broker = run(sys.executable, str(HERE / "vq_broker_check.py"), "--out", str(out))
        if broker.returncode != 0:
            detail = (broker.stdout.strip() or broker.stderr.strip()).splitlines()[-1:]
            problems.append(f"broker state check failed: {' '.join(detail)}")

    denied = vq_audit.withheld_locations(run_home, session_dir)
    if card_type.startswith("F"):
        denied.append(str(session_dir / "workspace/src"))
    roots = [Path(os.path.expanduser(r)) for r in SCAN_ROOTS]
    problems += [
        f"reachable copy: {p}" for p in host_scan(roots, denied, card_type.startswith("T"))
    ]

    result = {"session": args[1], "type": card_type, "problems": problems}
    (session_dir / "preflight.json").write_text(json.dumps(result, indent=2) + "\n")
    for problem in problems:
        print(f"STOP: {problem}", file=sys.stderr)
    if not problems:
        print(f"preflight {args[1]}: clean")
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
