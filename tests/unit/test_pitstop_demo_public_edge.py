"""Public read-only hosted demo: the external acceptance script (`hosted/verify_public_edge.py`).

The edge that makes anonymous `/mcp` safe lives outside the repository, so the checker is the evidence.
These tests run it against a local stub that plays the edge, once correctly gated and once with each
guard removed, and require the matching check (and only it) to FAIL - proving every check can fail.
"""

from __future__ import annotations

import importlib.util
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.architecture_intelligence.contracts import TOOL_NAMES
from app.architecture_intelligence.locality_contracts import LOCALITY_TOOL_NAME

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO / "examples" / "pitstop-demo"
_spec = importlib.util.spec_from_file_location(
    "verify_public_edge", DEMO_DIR / "hosted" / "verify_public_edge.py"
)
assert _spec and _spec.loader
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

HOST = "demo.example"
BODY_CAP = 64 * 1024
RATE_LIMIT = 5


class Guards:
    def __init__(self, **disabled: bool) -> None:
        self.extra_tool = disabled.get("extra_tool", False)
        self.open_import = disabled.get("open_import", False)
        self.any_host = disabled.get("any_host", False)
        self.no_body_cap = disabled.get("no_body_cap", False)
        self.no_rate_limit = disabled.get("no_rate_limit", False)
        self.empty_200_for_unknown_host = disabled.get("empty_200_for_unknown_host", False)
        self.mcp_requests = 0


def _edge(guards: Guards) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def _send(self, status: int, payload: object = None) -> None:
            data = json.dumps(payload).encode() if payload is not None else b"x"
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_empty_200(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _handle(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)
            if self.path.startswith("/api/import") and guards.open_import:
                return self._send(200, {"runs": []})
            if self.path != "/mcp" or self.command != "POST":
                return self._send(404)
            if not guards.any_host and self.headers.get("Host") != f"{HOST}":
                if guards.empty_200_for_unknown_host:
                    return self._send_empty_200()
                return self._send(421)
            if not guards.no_body_cap and length > BODY_CAP:
                return self._send(413)
            guards.mcp_requests += 1
            if not guards.no_rate_limit and guards.mcp_requests > RATE_LIMIT:
                return self._send(429)
            message = json.loads(raw)
            method, args = message["method"], message["params"].get("arguments", {})
            if method == "initialize":
                result: dict = {"protocolVersion": verify.PROTOCOL_VERSION}
            elif method == "tools/list":
                names = set(verify.PUBLIC_TOOL_ALLOWLIST) | (
                    {"import_graph"} if guards.extra_tool else set()
                )
                result = {"tools": [{"name": name} for name in sorted(names)]}
            elif message["params"]["name"] == "get_service_dependencies":
                result = {
                    "structuredContent": {
                        "outcome": "ANSWERED",
                        "evidence_refs": ["evidence:a"],
                        "snapshot": {"snapshot_id": "aip:snapshot:v1:" + "0" * 64},
                    }
                }
            else:
                assert args["request"]["evidence_refs"] == ["evidence:a"]
                result = {"structuredContent": {"outcome": "ANSWERED"}}
            self._send(200, {"jsonrpc": "2.0", "id": message["id"], "result": result})

        do_GET = do_POST = _handle

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def _run(guards: Guards, *, rate_limit: int | None = RATE_LIMIT + 1) -> dict[str, str]:
    server = _edge(guards)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        argv = ["--url", f"http://127.0.0.1:{port}/mcp", "--date", "2026-10-12"]
        if rate_limit is not None:
            argv += ["--expect-429-within", str(rate_limit)]
        args = verify.build_parser().parse_args(argv)
        # Host header: the stub only serves its own public name, as the real edge does.
        verify_host = HOST
        original = verify._request

        def with_host(method, url, body=None, headers=None, host=None):
            return original(method, url, body, headers, host=host or verify_host)

        verify._request = with_host
        try:
            return {name: status for name, status, _ in verify.run(args)}
        finally:
            verify._request = original
    finally:
        server.shutdown()


def test_frozen_allowlist_is_the_live_registry():
    assert verify.PUBLIC_TOOL_ALLOWLIST == {*TOOL_NAMES, LOCALITY_TOOL_NAME}
    source = (REPO / "app" / "mcp" / "tools.py").read_text()
    assert (
        set(re.findall(r'@server\.tool\(\s*name="(\w+)"', source)) <= verify.PUBLIC_TOOL_ALLOWLIST
    )


def test_correctly_gated_edge_passes_every_check():
    results = _run(Guards())
    assert set(results.values()) == {verify.PASS}, results


def test_an_empty_200_for_an_unknown_host_counts_as_not_served():
    """Caddy answers a Host that matches no site with an empty 200: nothing behind the edge is reached."""
    results = _run(Guards(empty_200_for_unknown_host=True))
    assert set(results.values()) == {verify.PASS}, results


def test_rate_limit_is_skipped_not_inferred_without_a_threshold():
    results = _run(Guards(), rate_limit=None)
    assert results["rate limit enforced"] == verify.SKIPPED
    assert {v for k, v in results.items() if k != "rate limit enforced"} == {verify.PASS}


@pytest.mark.parametrize(
    ("guard", "failing_check"),
    [
        ("extra_tool", "tool inventory (frozen allowlist)"),
        ("open_import", "non-MCP routes closed"),
        ("any_host", "invalid Host rejected"),
        ("no_body_cap", "oversized body rejected"),
        ("no_rate_limit", "rate limit enforced"),
    ],
)
def test_each_check_fails_when_its_guard_is_removed(guard, failing_check):
    results = _run(Guards(**{guard: True}))
    assert results[failing_check] == verify.FAIL, results
    assert {k for k, v in results.items() if v == verify.FAIL} == {failing_check}, results


def test_current_user_facing_docs_do_not_call_the_hosted_demo_token_gated():
    """Historical release records and the CHANGELOG's past entries keep their wording; these do not."""
    for path in (
        REPO / "README.md",
        DEMO_DIR / "README.md",
        DEMO_DIR / "TRY_IT_HOSTED.md",
        DEMO_DIR / "claude" / "plugin" / ".claude-plugin" / "plugin.json",
    ):
        assert not re.search(r"token[- ]gated", path.read_text(), re.IGNORECASE), path.name
