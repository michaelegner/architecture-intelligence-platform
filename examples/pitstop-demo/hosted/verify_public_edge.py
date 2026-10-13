"""External acceptance check for the public read-only hosted Pitstop demo.

Run from OUTSIDE the demo's network, with no credentials:

    python examples/pitstop-demo/hosted/verify_public_edge.py --url https://<host>/mcp \
        [--date YYYY-MM-DD] [--expect-429-within N]

AIP itself has no public-internet authentication; the safety of the anonymous deployment is owned by the
deployment edge. This script is the evidence that the edge does its job. Checks:

- anonymous `initialize` / `tools/list` succeed, and `tools/list` returns EXACTLY `PUBLIC_TOOL_ALLOWLIST`
  (the edge only knows `POST /mcp`; it cannot tell a safe `tools/call` from a future mutating tool, so
  the tool inventory is a hard acceptance boundary - any extra or missing tool fails; no name heuristics);
- a `get_service_dependencies` call and a `get_evidence` drill-down on its own snapshot succeed;
- the import, ingest, query and unrelated routes are not reachable (any non-2xx, or a connection
  failure, counts as closed - the exact code is the edge's business);
- an invalid `Host` and an oversized body are rejected;
- the rate limit is checked only when `--expect-429-within N` is given (the deployed threshold):
  without it the check is SKIPPED, never inferred.

Exit code 0 only if no check FAILED. Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime
import http.client
import json
import ssl
import sys
import urllib.parse

# Frozen public-demo tool inventory. Changing the MCP surface must be a deliberate edit here
# (tests/unit/test_pitstop_demo_public_edge.py compares it with the registry).
PUBLIC_TOOL_ALLOWLIST = frozenset(
    {
        "get_architecture_drift",
        "get_evidence",
        "get_service_dependencies",
        "get_service_dependencies_by_locality",
    }
)
SERVICE_ID = "service:workshop-management-api"
ENVIRONMENT = "pitstop-demo"
PROTOCOL_VERSION = "2025-11-25"
CLOSED_PATHS = (
    ("POST", "/api/import"),
    ("POST", "/api/import/anything"),
    ("POST", "/v1/traces"),
    ("POST", "/api/query"),
    ("GET", "/api/services"),
    ("GET", "/api/evidence"),
    ("GET", "/health"),
    ("GET", "/docs"),
    ("GET", "/openapi.json"),
    ("GET", "/"),
)
PASS, FAIL, SKIPPED = "PASS", "FAIL", "SKIPPED"
TIMEOUT = 30
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": PROTOCOL_VERSION,
}


def _request(
    method: str,
    url: str,
    body: bytes | None = None,
    headers: dict | None = None,
    host: str | None = None,
) -> tuple[int | None, bytes]:
    """(status, body); status None when the connection itself was refused/reset/failed TLS.
    `host` sends that Host header (and no SNI change) to the same address."""
    parts = urllib.parse.urlsplit(url)
    connection_class = (
        http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    )
    kwargs = {"context": ssl.create_default_context()} if parts.scheme == "https" else {}
    connection = connection_class(parts.hostname, parts.port, timeout=TIMEOUT, **kwargs)
    send_headers = dict(headers or {})
    if host is not None:
        send_headers["Host"] = host
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    try:
        connection.request(method, path, body=body, headers=send_headers)
        response = connection.getresponse()
        return response.status, response.read()
    except (OSError, http.client.HTTPException):
        return None, b""
    finally:
        connection.close()


def _rpc(url: str, request_id: int, method: str, params: dict) -> tuple[int | None, dict | None]:
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
    status, raw = _request("POST", url, body.encode(), _HEADERS)
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, None


def _tool_call(url: str, request_id: int, name: str, arguments: dict) -> tuple[bool, dict | str]:
    status, message = _rpc(url, request_id, "tools/call", {"name": name, "arguments": arguments})
    if status != 200 or not message or "result" not in message:
        return False, f"{name}: HTTP {status}, {json.dumps(message)[:200]}"
    result = message["result"]
    if result.get("isError") or not isinstance(result.get("structuredContent"), dict):
        return False, f"{name}: tool error or no structuredContent"
    return True, result["structuredContent"]


def check_initialize(url: str) -> tuple[str, str]:
    status, message = _rpc(
        url,
        1,
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "verify-public-edge", "version": "1"},
        },
    )
    ok = status == 200 and bool(message) and "result" in message
    return (PASS, "anonymous initialize succeeded") if ok else (FAIL, f"HTTP {status}")


def check_tool_inventory(url: str) -> tuple[str, str]:
    status, message = _rpc(url, 2, "tools/list", {})
    if status != 200 or not message or "result" not in message:
        return FAIL, f"tools/list: HTTP {status}"
    names = {tool["name"] for tool in message["result"].get("tools", [])}
    extra, missing = sorted(names - PUBLIC_TOOL_ALLOWLIST), sorted(PUBLIC_TOOL_ALLOWLIST - names)
    if extra or missing:
        return (
            FAIL,
            f"tools/list differs from the frozen allowlist: extra {extra}, missing {missing}",
        )
    return PASS, f"exactly the {len(names)} allowlisted tools"


def check_pitstop_answer_and_drilldown(url: str, date: str) -> tuple[str, str]:
    context = {
        "environment": ENVIRONMENT,
        "window_start": f"{date}T00:00:00Z",
        "window_end": f"{date}T23:59:59Z",
    }
    ok, answer = _tool_call(
        url,
        3,
        "get_service_dependencies",
        {"request": {"service_id": SERVICE_ID, "observation_context": context}},
    )
    if not ok:
        return FAIL, str(answer)
    refs = answer.get("evidence_refs") or []
    snapshot_id = (answer.get("snapshot") or {}).get("snapshot_id")
    if answer.get("outcome") != "ANSWERED" or not refs or not snapshot_id:
        return FAIL, f"dependencies for {date}: outcome {answer.get('outcome')}, {len(refs)} refs"
    ok, evidence = _tool_call(
        url,
        4,
        "get_evidence",
        {"request": {"evidence_refs": refs[:20], "snapshot_id": snapshot_id}},
    )
    if not ok:
        return FAIL, str(evidence)
    return PASS, f"{date}: answered with {len(refs)} refs; get_evidence resolved on its snapshot"


def check_closed_routes(url: str) -> tuple[str, str]:
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    open_routes = []
    for method, path in CLOSED_PATHS:
        body = b"{}" if method == "POST" else None
        status, _ = _request(method, base + path, body, {"Content-Type": "application/json"})
        if status is not None and 200 <= status < 300:
            open_routes.append(f"{method} {path} -> {status}")
    if open_routes:
        return FAIL, "reachable: " + "; ".join(open_routes)
    return PASS, f"{len(CLOSED_PATHS)} non-MCP routes closed"


def check_invalid_host(url: str) -> tuple[str, str]:
    body = json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {}}).encode()
    status, _ = _request("POST", url, body, _HEADERS, host="not-the-demo.invalid")
    if status is not None and 200 <= status < 300:
        return FAIL, f"invalid Host accepted (HTTP {status})"
    return PASS, f"invalid Host rejected ({'connection refused' if status is None else status})"


def check_oversized_body(url: str, size: int) -> tuple[str, str]:
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {"pad": "x" * size}}
    )
    status, _ = _request("POST", url, body.encode(), _HEADERS)
    if status is not None and 200 <= status < 300:
        return FAIL, f"{size}-byte body accepted (HTTP {status})"
    return PASS, f"{size}-byte body rejected ({'connection refused' if status is None else status})"


def check_rate_limit(url: str, within: int | None) -> tuple[str, str]:
    if within is None:
        return SKIPPED, "pass --expect-429-within N (the deployed threshold) to enforce"
    body = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}).encode()
    for sent in range(1, within + 1):
        status, _ = _request("POST", url, body, _HEADERS)
        if status == 429:
            return PASS, f"429 after {sent} requests (limit {within})"
    return FAIL, f"no 429 within {within} requests"


def run(args: argparse.Namespace) -> list[tuple[str, str, str]]:
    checks = [
        ("anonymous initialize", lambda: check_initialize(args.url)),
        ("tool inventory (frozen allowlist)", lambda: check_tool_inventory(args.url)),
        (
            "Pitstop answer + evidence drill-down",
            lambda: check_pitstop_answer_and_drilldown(args.url, args.date),
        ),
        ("non-MCP routes closed", lambda: check_closed_routes(args.url)),
        ("invalid Host rejected", lambda: check_invalid_host(args.url)),
        ("oversized body rejected", lambda: check_oversized_body(args.url, args.oversize_bytes)),
        # last: it may exhaust the budget the checks above need
        ("rate limit enforced", lambda: check_rate_limit(args.url, args.expect_429_within)),
    ]
    return [(name, *check()) for name, check in checks]


def build_parser() -> argparse.ArgumentParser:
    yesterday = datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="the public MCP URL, e.g. https://host/mcp")
    parser.add_argument(
        "--date", default=yesterday.isoformat(), help="completed UTC day (default: yesterday)"
    )
    parser.add_argument(
        "--oversize-bytes",
        type=int,
        default=256 * 1024,
        help="body size that only the edge (not AIP's own 1 MiB limit) rejects; set above its cap",
    )
    parser.add_argument("--expect-429-within", type=int, default=None, metavar="N")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    results = run(args)
    for name, status, detail in results:
        print(f"{status:8} {name}: {detail}")
    failed = [name for name, status, _ in results if status == FAIL]
    print("FAILED: " + ", ".join(failed) if failed else "all executed checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
