"""GT 0.8.0 I3: set up and run one agent session of one arm.

    session.py setup ARM [--attempt N]
    session.py run ARM [--attempt N]

Arms: A (files), G (GT), GA (GT + AIP through the I2 client), AA (files + hosted AIP).

`setup` builds the session directory under the run home (default `~/aip-gt-i3-runs`, outside every
repository): a fresh Claude config with the arm's settings, the MCP config, the workspace, the
output directory and `record/`. For A and AA it materializes the corpus as the workspace. For G and
GA it prepares the Windows side instead: a fresh GT extraction, the `--gt` corpus and the arm's
`.st` files. The owner then loads GT and starts the server.

`run` checks the arm's preconditions, runs `claude -p` once and writes `record/session.json`.
A voided session is re-run with the next `--attempt`; every attempt is kept.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
I3 = HERE.parent
GT080 = I3.parent
REPO = GT080.parents[3]
MATERIALIZE = GT080 / "gt/materialize_corpus.py"
PROMPTS = HERE / "prompts"

RUN_HOME = Path(os.environ.get("AIP_GT_I3_RUNS", Path.home() / "aip-gt-i3-runs"))
WIN_ROOT = Path("/mnt/c/Users/megne/aip-gt-i3")
WIN_ROOT_WINDOWS = r"C:\Users\megne\aip-gt-i3"
GT_ZIP = "GlamorousToolkit-Windows-x86_64-v1.1.657.zip"
GT_ZIP_SHA256 = "19ae8ba3edd80a786a56d44d35f52b7d4796312da676d1104fcef7b4fecfd4da"
GT_PORT = 7790
AIP_URL = "https://mcp.daip.io/mcp"
FROZEN_SNAPSHOT = "aip:snapshot:v1:7f171aea2d3c5070e6be3dd9c6b53a234ad75934be5724681b95cd3e1705c413"
MODEL = "claude-opus-5-5"
# The pinned Claude Code build: called by path, so an update of the `claude` symlink cannot reach it.
CLAUDE_VERSION = "2.1.322"
CLAUDE_BIN = Path.home() / ".local/share/claude/versions" / CLAUDE_VERSION
OUTPUTS = ("first-impression.md", "answer.md")
GT_TOOLS = ["getLepiterPageContents", "getViewText", "listObjectStorage", "selectViewItem"]

ARMS = {
    # built-in tools, MCP server, .st files loaded in GT (None: no GT)
    "A": {"tools": "Read,Glob,Grep,Write,ToolSearch", "mcp": None, "st": None},
    "AA": {"tools": "Read,Glob,Grep,Write,ToolSearch", "mcp": "aip", "st": None},
    "G": {
        "tools": "Read,Write,ToolSearch",
        "mcp": "gt",
        "st": [GT080 / "gt/AIP-GT-Promises.st", HERE / "AIP-GT-Promises-MCP.st"],
    },
    "GA": {
        "tools": "Read,Write,ToolSearch",
        "mcp": "gt",
        "st": [
            GT080 / "gt/AIP-GT-Promises.st",
            GT080 / "gt/AIP-GT-Promises-AIP.st",
            HERE / "AIP-GT-Promises-MCP.st",
            HERE / "AIP-GT-Promises-MCP-AIP.st",
        ],
    },
}


def stop(message: str) -> None:
    print(f"STOP: {message}", file=sys.stderr)
    sys.exit(2)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def wsl_host() -> str:
    """The Windows host as WSL sees it: the default gateway."""
    route = subprocess.run(
        ["ip", "route", "show", "default"], check=True, capture_output=True, text=True
    )
    return route.stdout.split()[2]


class Session:
    def __init__(self, arm: str, attempt: int) -> None:
        self.arm = arm
        self.spec = ARMS[arm]
        self.name = f"{arm}-{attempt}"
        self.dir = RUN_HOME / self.name
        self.home = self.dir / "home"
        self.config = self.dir / "config"
        self.work = self.dir / "work"
        self.out = self.dir / "out"
        self.record = self.dir / "record"
        self.win = WIN_ROOT / "sessions" / self.name
        self.is_gt = self.spec["st"] is not None
        # GT arms work in the output directory: Read reaches only their own outputs.
        self.cwd = self.out if self.is_gt else self.work

    def other_sessions(self) -> list[Path]:
        if not RUN_HOME.exists():
            return []
        return sorted(p for p in RUN_HOME.iterdir() if p.is_dir() and p != self.dir)

    def settings(self) -> dict:
        allow = [f"Edit(/{self.out}/{name})" for name in OUTPUTS] + [f"Read(/{self.out}/**)"]
        if self.spec["mcp"]:
            allow.append(f"mcp__{self.spec['mcp']}")
        deny = [
            "Read(//mnt/**)",
            f"Read(/{REPO.parent}/**)",
            f"Read(/{Path.home()}/.claude/**)",
            f"Read(/{self.config}/**)",
            f"Read(/{self.record}/**)",
            *(f"Read(/{p}/**)" for p in self.other_sessions()),
            "WebFetch",
            "WebSearch",
            "Bash",
            "Agent",
            "Task",
        ]
        return {"permissions": {"allow": allow, "deny": deny, "defaultMode": "dontAsk"}}

    def mcp_config(self) -> dict:
        if self.spec["mcp"] == "gt":
            return {
                "mcpServers": {"gt": {"type": "http", "url": f"http://{wsl_host()}:{GT_PORT}/"}}
            }
        if self.spec["mcp"] == "aip":
            return {"mcpServers": {"aip": {"type": "http", "url": AIP_URL}}}
        return {"mcpServers": {}}

    def page_ids(self) -> tuple[str, str]:
        lines = (self.win / "page-ids.txt").read_text().split()
        return lines[0], lines[1]

    def prompt(self, probe: bool = False) -> str:
        """The first message: `gt.md` or `files.md`; a dry run uses `probe-gt.md` or `probe-files.md`."""
        name = ("probe-" if probe else "") + ("gt.md" if self.is_gt else "files.md")
        text = (PROMPTS / name).read_text()
        if self.is_gt:
            page, database = self.page_ids()
            text = text.replace("{PAGE_UID}", page).replace("{DATABASE_ID}", database)
        return text.replace("{OUT}", str(self.out))

    # setup

    def setup(self) -> None:
        if self.dir.exists():
            stop(f"{self.dir} exists; use the next --attempt")
        for path in (self.home, self.config, self.out, self.record):
            path.mkdir(parents=True)
        credentials = Path.home() / ".claude/.credentials.json"
        if credentials.exists():
            shutil.copy(credentials, self.config / ".credentials.json")
            (self.config / ".credentials.json").chmod(0o600)
        (self.config / "settings.json").write_text(json.dumps(self.settings(), indent=2) + "\n")
        (self.dir / "mcp.json").write_text(json.dumps(self.mcp_config(), indent=2) + "\n")
        record: dict = {"session": self.name, "arm": self.arm, "created_utc": now(), "model": MODEL}
        if self.is_gt:
            self.work.mkdir()
            corpus = self.setup_windows()
            record["gt_zip_sha256"] = GT_ZIP_SHA256
        else:
            corpus = self.work
            self.materialize(corpus, gt=False)
        record["corpus_sha256sums_sha256"] = sha256(corpus / "SHA256SUMS")
        (self.record / "session.json").write_text(json.dumps(record, indent=2) + "\n")
        print(f"session {self.name} ready in {self.dir}")
        if self.is_gt:
            print(f"GT side: {self.win_path(self.win)}")

    def materialize(self, out: Path, gt: bool) -> None:
        command = [sys.executable, str(MATERIALIZE), "--repo", str(REPO), "--out", str(out)]
        if gt:
            command.append("--gt")
        subprocess.run(command, check=True)

    def setup_windows(self) -> Path:
        zip_path = WIN_ROOT / GT_ZIP
        if sha256(zip_path) != GT_ZIP_SHA256:
            stop(f"{zip_path} does not match the recorded sha256")
        if self.win.exists():
            stop(f"{self.win} exists")
        self.win.mkdir(parents=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(self.win / "gt")
        corpus = self.win / "corpus"
        self.materialize(corpus, gt=True)
        for source in self.spec["st"]:
            shutil.copy(source, self.win / source.name)
        return corpus

    @staticmethod
    def win_path(path: Path) -> str:
        return WIN_ROOT_WINDOWS + "\\" + str(path.relative_to(WIN_ROOT)).replace("/", "\\")

    # run

    def preflight(self) -> None:
        if not (self.record / "session.json").exists():
            stop(f"no setup for {self.name}")
        if (self.record / "transcript.jsonl").exists():
            stop(f"{self.name} has already run; use the next --attempt")
        if any(self.out.iterdir()):
            stop(f"{self.out} is not empty")
        if not (self.config / ".credentials.json").exists():
            stop("no credentials in the session config")
        version = subprocess.run(
            [str(CLAUDE_BIN), "--version"], check=True, capture_output=True, text=True
        ).stdout
        if not version.startswith(CLAUDE_VERSION + " "):
            stop(f"{CLAUDE_BIN} reports {version.strip()}, expected {CLAUDE_VERSION}")
        if self.spec["mcp"] == "aip" or self.arm == "GA":
            subprocess.run([sys.executable, str(HERE / "check_hosted.py")], check=True)
        if self.is_gt:
            self.check_gt()

    def check_gt(self) -> None:
        """The GT server offers exactly the four tools, holds the arm's starting objects, and
        answers a refusal with text."""
        sys.path.insert(0, str(HERE))
        from gt_client import GtClient

        client = GtClient(f"http://{wsl_host()}:{GT_PORT}/")
        if sorted(client.tool_names()) != GT_TOOLS:
            stop(f"GT tools differ: {client.tool_names()}")
        stored = client.stored()
        expected = ["corpus", "aip"] if self.arm == "GA" else ["corpus"]
        if sorted(stored) != sorted(expected):
            stop(f"GT object storage holds {sorted(stored)}, expected {expected}")
        corpus = stored["corpus"]
        refusal = client.text(
            "selectViewItem", objectId=corpus, viewSelector="gtFilesFor:", itemIndex="999"
        )
        if "Not selectable" not in refusal:
            stop(f"selectViewItem refusal is not text: {refusal!r}")
        if "corpus root" not in client.text(
            "getViewText", objectId=corpus, viewSelector="gtFilesFor:"
        ):
            stop("the Files view does not show the corpus root")
        page, database = self.page_ids()
        if "# Task:" not in client.text(
            "getLepiterPageContents", pageUid=page, databaseId=database
        ):
            stop("the investigation page has no task")
        print("GT server: four tools, starting objects, refusal text and page OK")

    def run(self, probe: bool = False) -> int:
        self.preflight()
        if probe:
            # A dry run keeps its own record and leaves the output directory empty.
            probe_record = self.dir / f"probe-{len(list(self.dir.glob('probe-*'))) + 1}"
            probe_record.mkdir()
            shutil.copy(self.record / "session.json", probe_record / "session.json")
            self.record = probe_record
        prompt = self.prompt(probe)
        (self.record / "prompt.md").write_text(prompt)
        command = [
            str(CLAUDE_BIN), "-p", prompt,
            "--model", MODEL,
            "--tools", self.spec["tools"],
            "--permission-mode", "dontAsk",
            "--setting-sources", "user",
            "--strict-mcp-config", "--mcp-config", str(self.dir / "mcp.json"),
            "--disallowedTools", "WebFetch", "WebSearch", "Bash", "mcp__claude_ai_*",
            "--output-format", "stream-json", "--verbose",
        ]  # fmt: skip
        env = {
            "HOME": str(self.home),
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "TERM": "dumb",
            "LANG": "C.UTF-8",
            "CLAUDE_CONFIG_DIR": str(self.config),
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "DISABLE_AUTOUPDATER": "1",
        }
        started, start = now(), time.monotonic()
        transcript = self.record / "transcript.jsonl"
        stderr = self.record / "stderr.txt"
        with transcript.open("w") as out, stderr.open("w") as err, open(os.devnull) as stdin:
            completed = subprocess.run(
                command, check=False, cwd=self.cwd, env=env, stdin=stdin, stdout=out, stderr=err,
                timeout=4 * 3600,
            )  # fmt: skip
        ended, duration = now(), round(time.monotonic() - start)
        self.write_record(started, ended, duration, completed.returncode)
        self.scan_secrets()
        if probe:
            for path in self.out.iterdir():
                path.unlink()
        else:
            (self.config / ".credentials.json").unlink()
        print(f"session {self.name}: exit {completed.returncode}, {duration} s")
        return completed.returncode

    def scan_secrets(self) -> None:
        """Record whether the transcript holds a token of the session's credentials (which the
        session may have refreshed) or of the operator's."""
        transcript = (self.record / "transcript.jsonl").read_text()
        secrets = tokens(self.config / ".credentials.json") + tokens(
            Path.home() / ".claude/.credentials.json"
        )
        found = "sk-ant-" in transcript or any(secret in transcript for secret in secrets)
        path = self.record / "session.json"
        record = json.loads(path.read_text())
        record["secret_scan"] = "FOUND" if found else "clean"
        path.write_text(json.dumps(record, indent=2) + "\n")

    def write_record(self, started: str, ended: str, duration: int, exit_code: int) -> None:
        path = self.record / "session.json"
        record = json.loads(path.read_text())
        record.update(
            started_utc=started, ended_utc=ended, duration_s=duration, exit_code=exit_code
        )
        if self.spec["mcp"] == "aip" or self.arm == "GA":
            record["expected_snapshot"] = FROZEN_SNAPSHOT
        tool_calls: dict[str, int] = {}
        for line in (self.record / "transcript.jsonl").read_text().splitlines():
            event = json.loads(line)
            if event.get("type") == "system" and event.get("subtype") == "init":
                record["claude_code_version"] = event.get("claude_code_version")
                record["model_reported"] = event.get("model")
                record["tools_offered"] = event.get("tools")
                record["mcp_servers"] = event.get("mcp_servers")
            elif event.get("type") == "assistant":
                for part in event["message"]["content"]:
                    if part.get("type") == "tool_use":
                        tool_calls[part["name"]] = tool_calls.get(part["name"], 0) + 1
            elif event.get("type") == "result":
                record["usage"] = {
                    "num_turns": event.get("num_turns"),
                    "duration_ms": event.get("duration_ms"),
                    "total_cost_usd": event.get("total_cost_usd"),
                    "tokens": event.get("usage"),
                    "permission_denials": len(event.get("permission_denials") or []),
                    "is_error": event.get("is_error"),
                }
        record["tool_calls"] = dict(sorted(tool_calls.items()))
        path.write_text(json.dumps(record, indent=2) + "\n")
        for name in OUTPUTS:
            if (self.out / name).exists():
                shutil.copy(self.out / name, self.record / name)


def tokens(path: Path) -> list[str]:
    """Every token string in a Claude credentials file."""
    found = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower().endswith("token") and isinstance(item, str) and len(item) > 20:
                    found.append(item)
                walk(item)

    if path.exists():
        walk(json.loads(path.read_text()))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("action", choices=["setup", "run"])
    parser.add_argument("arm", choices=sorted(ARMS))
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument(
        "--probe", action="store_true", help="dry run: the capability-check prompt, not the task"
    )
    args = parser.parse_args(argv)
    session = Session(args.arm, args.attempt)
    if args.action == "setup":
        session.setup()
        return 0
    return session.run(args.probe)


if __name__ == "__main__":
    sys.exit(main())
