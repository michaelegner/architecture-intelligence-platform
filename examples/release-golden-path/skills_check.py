"""v0.8.1 I2: the release-artifact check of the MCP skills (spec
`docs/specifications/0.8.1/specification.md` §5).

Starts one AIP image with `experimental.binding-picture` on and reads both `SKILL.md` files through
its MCP endpoint only:

    RELEASE_CANDIDATE_SHA=<40-hex> python examples/release-golden-path/skills_check.py <IMAGE_REF> <OUT_DIR>

`golden_path.py` runs the same phase after `destination-consumers`. The image must already be
present locally and is never rebuilt. It proves that the skills are in the image, not only in the
source tree: each served file must equal, byte for byte, `app/mcp/skills/<name>/SKILL.md` in the
checkout that runs this harness (for a published image, the tagged-source clone). The phase imports
nothing; a fresh Compose project and a fresh Neo4j volume are used, as in every other phase.

The requests reproduce the modern (`2026-07-28`) shape that Claude Code 2.1.332 sends, plus the
`mcp-method` and `mcp-name` headers that the pinned SDK requires (see
`tests/support/modern_mcp_client.py`)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import golden_path as gp

PHASE = "skills"
MODERN = "2026-07-28"
SKILLS_EXTENSION = "io.modelcontextprotocol/skills"
SKILL_NAMES = ("aip-reading-answers", "aip-binding-picture")
SKILLS_DIR = gp.REPO / "app" / "mcp" / "skills"
METHOD_NOT_FOUND = -32601
_META = {
    "io.modelcontextprotocol/protocolVersion": MODERN,
    "io.modelcontextprotocol/clientInfo": {"name": "aip-release-golden-path", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


def skill_uri(name: str) -> str:
    return f"skill://aip/{name}/SKILL.md"


def source_frontmatter(text: str) -> Any:
    lines = text.split("\n")
    if lines[0] != "---":
        return None
    return yaml.safe_load("\n".join(lines[1 : lines.index("---", 1)]))


def modern(method: str, params: dict | None = None, name: str | None = None) -> tuple[int, Any]:
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": MODERN,
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {**(params or {}), "_meta": _META},
    }
    return gp.http("POST", f"{gp.AIP_URL}/mcp", body, headers)


def discover_problems(result: dict[str, Any], version: str) -> list[str]:
    capabilities = result.get("capabilities") or {}
    problems = []
    if (capabilities.get("extensions") or {}).get(SKILLS_EXTENSION) != {}:
        problems.append(f"extensions {capabilities.get('extensions')!r}")
    if capabilities.get("resources") != {"listChanged": False, "subscribe": False}:
        problems.append(f"resources {capabilities.get('resources')!r}")
    server_info = (result.get("_meta") or {}).get("io.modelcontextprotocol/serverInfo") or {}
    if server_info.get("version") != version:
        problems.append(f"serverInfo.version {server_info.get('version')!r}")
    return problems


def skill_problems(
    name: str, entry: dict[str, Any], served: bytes, source: bytes, got: dict[str, Any]
) -> list[str]:
    """One listed skill against the checkout's file. `served` is what `resources/read` returned;
    `got` is the `skills/get` result."""
    uri = skill_uri(name)
    problems = []
    if entry.get("uri") != uri:
        problems.append(f"{name}: uri {entry.get('uri')!r}")
    if served != source:
        problems.append(f"{name}: served bytes differ from {SKILLS_DIR.name}/{name}/SKILL.md")
    if entry.get("frontmatter") != source_frontmatter(source.decode("utf-8")):
        problems.append(f"{name}: frontmatter differs from the file")
    manifest = {
        "uri": uri,
        "digest": "sha256:" + hashlib.sha256(served).hexdigest(),
        "size": len(served),
    }
    if entry.get("resources") != [manifest]:
        problems.append(f"{name}: manifest {entry.get('resources')!r}, served {manifest!r}")
    if got.get("skill") != entry or got.get("resultType") != "complete":
        problems.append(f"{name}: skills/get differs from skills/list")
    return problems


def list_problems(result: dict[str, Any]) -> list[str]:
    uris = [entry.get("uri") for entry in result.get("skills", [])]
    problems = [] if uris == [skill_uri(n) for n in SKILL_NAMES] else [f"skills {uris!r}"]
    cache = (result.get("resultType"), result.get("ttlMs"), result.get("cacheScope"))
    if cache != ("complete", 0, "public"):
        problems.append(f"resultType/ttlMs/cacheScope {cache!r}")
    return problems


def _error_code(body: Any) -> Any:
    return (body or {}).get("error", {}).get("code") if isinstance(body, dict) else None


def _drive(checks: dict[str, Any], output: Path) -> None:
    def record(check: str, problems: list[str]) -> None:
        checks[check] = {"passed": not problems, "detail": problems}

    def result_of(label: str, status: int, body: Any) -> dict[str, Any]:
        (output / f"{label}.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
        if status != 200 or not isinstance(body, dict) or "result" not in body:
            raise gp.HarnessError(f"{label} failed: {status} {body}")
        return body["result"]

    record(
        "discover",
        discover_problems(result_of("discover", *modern("server/discover")), gp.package_version()),
    )
    listed = result_of("skills-list", *modern("skills/list"))
    record("skills-list", list_problems(listed))

    problems = []
    for name, entry in zip(SKILL_NAMES, listed.get("skills", []), strict=False):
        uri = skill_uri(name)
        read = result_of(f"read-{name}", *modern("resources/read", {"uri": uri}, name=uri))
        [content] = read["contents"]
        got = result_of(f"get-{name}", *modern("skills/get", {"uri": uri}))
        source = (SKILLS_DIR / name / "SKILL.md").read_bytes()
        problems += skill_problems(name, entry, content["text"].encode("utf-8"), source, got)
    record("skills-content", problems)

    status, body = modern("subscriptions/listen", {"notifications": {}})
    record(
        "listen-declined",
        [] if _error_code(body) == METHOD_NOT_FOUND else [f"listen: {status} {body}"],
    )

    client = gp.McpClient()
    status, resources = client._post({"method": "resources/list", "params": {}})
    status_skills, skills = client._post({"method": "skills/list", "params": {}})
    legacy = []
    listed_uris = [
        r.get("uri", "") for r in ((resources or {}).get("result") or {}).get("resources", [])
    ]
    if status != 200 or any(uri.startswith("skill://") for uri in listed_uris):
        legacy.append(f"legacy resources/list: {status} {listed_uris}")
    if _error_code(skills) != METHOD_NOT_FOUND:
        legacy.append(f"legacy skills/list: {status_skills} {skills}")
    record("legacy-unchanged", legacy)


def run_skills_phase(*, image_ref: str, sha: str, out_dir: Path) -> dict[str, Any]:
    output = out_dir / PHASE
    output.mkdir(parents=True, exist_ok=True)
    stack = gp.Stack(
        PHASE,
        image_ref=image_ref,
        config_path="golden-path/config.yaml",
        password=secrets.token_hex(16),
    )
    checks: dict[str, Any] = {}
    error = None
    stack.compose("down", "-v", "--remove-orphans", check=False)
    try:
        stack.compose("up", "-d", "--force-recreate", timeout=600)
        gp._wait(
            "AIP /health", lambda: gp.http("GET", f"{gp.AIP_URL}/health")[0] == 200, timeout=180
        )
        identity = gp._run_identity(stack, image_ref, sha)
        checks["run-identity"] = {
            "passed": identity["running_image_id"] == identity["image_ref_id"]
            and identity["aip_build_revision"] == sha
            and identity["user"] == "app",
            "detail": identity,
        }
        _drive(checks, output)
    except (gp.HarnessError, subprocess.TimeoutExpired, KeyError, ValueError) as exc:
        error = repr(exc)
        (output / "compose-logs.txt").write_text(stack.compose("logs", "--no-color", check=False))
    finally:
        stack.compose("down", "-v", "--remove-orphans", check=False)
    expected = [
        "run-identity",
        "discover",
        "skills-list",
        "skills-content",
        "listen-declined",
        "legacy-unchanged",
    ]
    result = {
        "phase": PHASE,
        "image_ref": image_ref,
        "release_candidate_sha": sha,
        "checks": checks,
        "not_run": sorted(set(expected) - set(checks)),
        "error": error,
        "passed": error is None
        and not set(expected) - set(checks)
        and all(c["passed"] for c in checks.values()),
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: skills_check.py <IMAGE_REF> <OUT_DIR>", file=sys.stderr)
        return 2
    image_ref, out_dir = argv[0], Path(argv[1]).resolve()
    sha = os.environ.get("RELEASE_CANDIDATE_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        print("RELEASE_CANDIDATE_SHA must be a full 40-character lowercase SHA", file=sys.stderr)
        return 2
    busy = [port for port in gp.HOST_PORTS if gp._port_open(port)]
    if busy:
        print(f"host ports already in use: {busy}", file=sys.stderr)
        return 2
    if out_dir.exists() and any(out_dir.iterdir()):
        print(f"OUT_DIR is not empty: {out_dir}", file=sys.stderr)
        return 2
    result = run_skills_phase(image_ref=image_ref, sha=sha, out_dir=out_dir)
    print(json.dumps({k: result[k] for k in ("phase", "passed", "error", "not_run")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
