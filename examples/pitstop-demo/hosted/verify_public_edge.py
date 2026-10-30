"""External acceptance check for the public read-only hosted demo (Pitstop, Sokol111 since v0.7.2 I2, or the
v0.8 Sokol111 binding picture).

Run from OUTSIDE the demo's network, with no credentials:

    python examples/pitstop-demo/hosted/verify_public_edge.py --url https://<host>/mcp \
        [--profile pitstop|sokol111|sokol111-v08] [--date YYYY-MM-DD] [--expect-429-within N] [--local-app]

AIP itself has no public-internet authentication; the safety of the anonymous deployment is owned by the
deployment edge. This script is the evidence that the edge does its job. Checks:

- anonymous `initialize` / `tools/list` succeed, and `tools/list` returns EXACTLY the profile's allowlist
  (`PUBLIC_TOOL_ALLOWLIST`, plus `get_binding_picture` for `sokol111-v08`; the edge only knows `POST /mcp`;
  it cannot tell a safe `tools/call` from a future mutating tool, so the tool inventory is a hard
  acceptance boundary - any extra or missing tool fails; no name heuristics);
- `--profile pitstop` (default): a `get_service_dependencies` call and a `get_evidence` drill-down on its
  own snapshot succeed;
- `--profile sokol111`: `get_destination_consumers` for the frozen Sokol111 Topic `catalog.product.events`
  answers `PARTIAL` with `CAPTURE_SCOPE_LIMITED`, exactly the frozen C1 `RESOLVED` Services, and every row
  at the C1 capture time T; the same-snapshot evidence drill-down returns exactly the requested refs, each
  `RESOLVED` with its `kind` and `evidence` (a frozen observation at T, not live use);
- `--profile sokol111-v08`: the `sokol111` check, and `get_binding_picture` for the Catalog Management
  boundary answers `PARTIAL` with exactly the four frozen limitations and the nine frozen C1 rows
  (docs/specifications/0.8.0/i2-vectors/c1-expected.json), one capture at T, and the same-snapshot
  evidence drill-down resolves every ref;
- `get_api_consumer_usage` (no gateway source on either demo) and `get_destination_consumers` for an
  unknown Topic answer with a typed refusal; any evaluated answer there would be invented;
- the import, ingest, query and unrelated routes are not reachable (any non-2xx, or a connection
  failure, counts as closed - the exact code is the edge's business);
- an invalid `Host` is not served an MCP result (an empty 200 from the edge counts) and an oversized body is rejected;
- the rate limit is checked only when `--expect-429-within N` is given (the deployed threshold):
  without it the check is SKIPPED, never inferred.

`--local-app` is for a rehearsal against AIP itself, without the edge: the four edge checks (routes,
Host, body size, rate limit) are SKIPPED, and every other check still runs. It never accepts a public
deployment.

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
        "get_api_consumer_usage",
        "get_architecture_drift",
        "get_destination_consumers",
        "get_evidence",
        "get_service_dependencies",
        "get_service_dependencies_by_locality",
    }
)
# v0.8 D11: the hosted v0.8 profile enables `experimental.binding-picture`, which adds one tool.
PROFILE_TOOL_ALLOWLISTS = {
    "pitstop": PUBLIC_TOOL_ALLOWLIST,
    "sokol111": PUBLIC_TOOL_ALLOWLIST,
    "sokol111-v08": PUBLIC_TOOL_ALLOWLIST | {"get_binding_picture"},
}
# The closed refusal codes of the two source-dependent tools' query mode (a refusal has `data: null` and
# exactly one of these). Copied so the script stays stdlib-only; the unit test pins them to the contracts.
API_USAGE_REFUSAL_CODES = frozenset(
    {
        "CURSOR_QUERY_MISMATCH",
        "MEASUREMENT_WINDOW_NOT_AVAILABLE",
        "SNAPSHOT_NOT_AVAILABLE",
        "TARGET_NOT_IN_WINDOW_SCOPE",
        "UNKNOWN_TARGET",
    }
)
DESTINATION_REFUSAL_CODES = frozenset(
    {
        "BROKER_MISMATCH",
        "CURSOR_QUERY_MISMATCH",
        "DESTINATION_NOT_KAFKA_TOPIC",
        "NO_ACCEPTED_CAPTURE",
        "SNAPSHOT_NOT_AVAILABLE",
        "UNKNOWN_DESTINATION",
    }
)
SERVICE_ID = "service:workshop-management-api"
# The frozen Sokol111 package (docs/specifications/0.7.2/i2-evidence/sokol111/): `topic:owned:` id of
# `catalog.product.events` on broker `kafka:sokol111-local` (app.sources.owner_ids.topic_owned_id).
SOKOL111_TOPIC_ID = "topic:owned:5534005a20357fa91c86e22e83f557c20a0be39302067e509fa59c85eb034539"
SOKOL111_BROKER = "kafka:sokol111-local"
SOKOL111_ENVIRONMENT = "local"
# Its C1 answer (expected.json `c1`): the two RESOLVED consumers, all captured at T.
SOKOL111_RESOLVED = frozenset(
    {"service:ecommerce-image-service", "service:ecommerce-product-query-service"}
)
SOKOL111_CAPTURED_AT = "2026-10-21T17:53:57Z"
# get_destination_consumers and get_binding_picture take at most this many refs per evidence request.
MAX_EVIDENCE_REFS = 20
# The v0.8 C1 binding picture (docs/specifications/0.8.0/i2-vectors/c1-expected.json, in answer order:
# broker, topic, consumer): the compared fields of tests/integration/binding_picture_support.essentials.
BINDING_PICTURE_CONTEXT = {
    "bounded_context_id": "catalog-management",
    "environment": SOKOL111_ENVIRONMENT,
    "broker_ids": [SOKOL111_BROKER],
}
BINDING_PICTURE_LIMITATIONS = (
    "CAPTURE_SCOPE_LIMITED",
    "EVENT_HANDLING_NOT_ESTABLISHED",
    "PRODUCER_SIDE_DECLARED_ONLY",
    "PROMISES_ASSUMED_CONFIRMED",
)
BINDING_PICTURE_PAGE_LIMIT = 200
_ROW_FIELDS = (
    "broker_id",
    "topic_name",
    "consumer_service_id",
    "crossing",
    "status",
    "reason",
    "cross_broker_producers",
)
_ROW_REF_FIELDS = ("promise_evidence_refs", "attachment_evidence_refs", "mapping_evidence_refs")


def _binding_row(topic: str, consumer: str, crossing: str, status: str, reason: str | None) -> dict:
    row = {
        "broker_id": SOKOL111_BROKER,
        "topic_name": topic,
        "consumer_service_id": f"service:ecommerce-{consumer}",
        "crossing": crossing,
        "status": status,
        "cross_broker_producers": False,
    }
    return row if reason is None else {**row, "reason": reason}


_MISSING = "PROMISE_COVERAGE_MISSING"
BINDING_PICTURE_ROWS = (
    _binding_row(
        "catalog.attribute.events", "category-query-service", "OUTBOUND", "UNRESOLVED", _MISSING
    ),
    _binding_row(
        "catalog.attribute.events", "product-query-service", "OUTBOUND", "UNRESOLVED", _MISSING
    ),
    _binding_row(
        "catalog.category.events", "category-query-service", "OUTBOUND", "UNRESOLVED", _MISSING
    ),
    _binding_row(
        "catalog.product.events", "image-service", "INSIDE", "PROMISED_AND_OBSERVED", None
    ),
    _binding_row(
        "catalog.product.events", "product-query-service", "OUTBOUND", "PROMISED_AND_OBSERVED", None
    ),
    _binding_row("tenant.tenant.events", "catalog-service", "INBOUND", "UNRESOLVED", _MISSING),
    _binding_row("tenant.tenant.events", "category-query-service", "NONE", "UNRESOLVED", _MISSING),
    _binding_row("tenant.tenant.events", "image-service", "INBOUND", "UNRESOLVED", _MISSING),
    _binding_row("tenant.tenant.events", "product-query-service", "NONE", "UNRESOLVED", _MISSING),
)
ENVIRONMENT = "pitstop-demo"
PROTOCOL_VERSION = "2025-11-25"
CLOSED_PATHS = (
    ("POST", "/api/import"),
    ("POST", "/api/import/anything"),
    ("POST", "/v1/traces"),
    ("POST", "/api/query"),
    ("POST", "/api/binding-picture"),
    ("POST", "/api/binding-picture/evidence"),
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


def check_tool_inventory(url: str, allowlist: frozenset[str]) -> tuple[str, str]:
    status, message = _rpc(url, 2, "tools/list", {})
    if status != 200 or not message or "result" not in message:
        return FAIL, f"tools/list: HTTP {status}"
    names = {tool["name"] for tool in message["result"].get("tools", [])}
    extra, missing = sorted(names - allowlist), sorted(allowlist - names)
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


def _refusal_code(answer: dict, allowed: frozenset[str]) -> str | None:
    """The single refusal code of a typed non-answer, or None if the answer is anything else."""
    codes = [item.get("code") for item in answer.get("limitations") or []]
    if answer.get("outcome") == "NOT_ANSWERED" and answer.get("data") is None and len(codes) == 1:
        return codes[0] if codes[0] in allowed else None
    return None


def check_source_dependent_tools_refuse(url: str, date: str) -> tuple[str, str]:
    """Pitstop has no gateway or Kafka source: both tools must refuse, never evaluate."""
    calls = (
        (
            "get_api_consumer_usage",
            {
                "mode": "query",
                "target": {"kind": "APPLICATION_SERVICE", "id": SERVICE_ID},
                "gateway_instance_id": "pitstop-demo-gateway",
                "environment": ENVIRONMENT,
                "window_start": f"{date}T00:00:00Z",
                "window_end": f"{date}T23:59:59Z",
            },
            API_USAGE_REFUSAL_CODES,
        ),
        (
            "get_destination_consumers",
            {
                "mode": "query",
                "destination_id": "topic:owned:" + "0" * 64,
                "broker_id": "kafka:pitstop-demo",
                "environment": ENVIRONMENT,
            },
            DESTINATION_REFUSAL_CODES,
        ),
    )
    seen = []
    for request_id, (name, request, allowed) in enumerate(calls, start=8):
        ok, answer = _tool_call(url, request_id, name, {"request": request})
        if not ok:
            return FAIL, str(answer)
        code = _refusal_code(answer, allowed)
        if code is None:
            return FAIL, f"{name}: not a typed refusal (outcome {answer.get('outcome')})"
        seen.append(f"{name} {code}")
    return PASS, "; ".join(seen)


def check_sokol111_consumers_and_drilldown(url: str) -> tuple[str, str]:
    context = {
        "destination_id": SOKOL111_TOPIC_ID,
        "broker_id": SOKOL111_BROKER,
        "environment": SOKOL111_ENVIRONMENT,
    }
    ok, answer = _tool_call(
        url, 10, "get_destination_consumers", {"request": {"mode": "query", **context}}
    )
    if not ok:
        return FAIL, str(answer)
    codes = [item.get("code") for item in answer.get("limitations") or []]
    rows = (answer.get("data") or {}).get("rows") or []
    resolved = sorted(row["service_id"] for row in rows if row.get("outcome") == "RESOLVED")
    if (
        answer.get("outcome") != "PARTIAL"
        or "CAPTURE_SCOPE_LIMITED" not in codes
        or resolved != sorted(SOKOL111_RESOLVED)
    ):
        return (
            FAIL,
            f"outcome {answer.get('outcome')}, limitations {codes}, RESOLVED {resolved}",
        )
    times = sorted({str(row.get("captured_at")) for row in rows})
    if times != [SOKOL111_CAPTURED_AT]:
        return FAIL, f"capture times {times}, expected {SOKOL111_CAPTURED_AT}"
    refs = sorted(
        {
            r
            for row in rows
            for r in [*row["attachment_evidence_refs"], *row["mapping_evidence_refs"]]
        }
    )
    if not refs:
        return FAIL, "no evidence refs to drill down"
    snapshot_id = (answer.get("snapshot") or {}).get("snapshot_id")
    for start in range(0, len(refs), MAX_EVIDENCE_REFS):
        batch = refs[start : start + MAX_EVIDENCE_REFS]
        request = {
            "mode": "evidence",
            "snapshot_id": snapshot_id,
            "evidence_refs": batch,
            **context,
        }
        ok, evidence = _tool_call(
            url, 11 + start // MAX_EVIDENCE_REFS, "get_destination_consumers", {"request": request}
        )
        if not ok:
            return FAIL, str(evidence)
        entries = (evidence.get("data") or {}).get("entries") or []
        if (
            evidence.get("outcome") != "ANSWERED"
            or [e.get("ref") for e in entries] != batch
            or {e.get("status") for e in entries} != {"RESOLVED"}
            or not all(e.get("kind") and e.get("evidence") for e in entries)
        ):
            return (
                FAIL,
                f"evidence drill-down: outcome {evidence.get('outcome')}, {len(entries)}/{len(batch)} entries",
            )
    return PASS, (
        f"T {SOKOL111_CAPTURED_AT}; RESOLVED {', '.join(resolved)}; {len(rows) - len(resolved)} other rows; "
        f"{len(refs)} refs resolved on its snapshot"
    )


def check_binding_picture_and_drilldown(url: str) -> tuple[str, str]:
    request = {"mode": "query", "limit": BINDING_PICTURE_PAGE_LIMIT, **BINDING_PICTURE_CONTEXT}
    ok, answer = _tool_call(url, 40, "get_binding_picture", {"request": request})
    if not ok:
        return FAIL, str(answer)
    codes = tuple(item.get("code") for item in answer.get("limitations") or [])
    data = answer.get("data") or {}
    rows = data.get("rows") or []
    compared = [{k: row[k] for k in _ROW_FIELDS if k in row} for row in rows]
    if (
        answer.get("outcome") != "PARTIAL"
        or codes != BINDING_PICTURE_LIMITATIONS
        or (data.get("page") or {}).get("next_cursor") is not None
        or compared != list(BINDING_PICTURE_ROWS)
    ):
        return (
            FAIL,
            f"outcome {answer.get('outcome')}, limitations {list(codes)}, {len(rows)} rows, "
            + f"cursor {(data.get('page') or {}).get('next_cursor')} (expected the frozen C1 page)",
        )
    captures = [
        (c.get("broker_id"), c.get("captured_at")) for c in data.get("capture_sources") or []
    ]
    times = {row["captured_at"] for row in rows if row.get("captured_at") is not None}
    if captures != [(SOKOL111_BROKER, SOKOL111_CAPTURED_AT)] or times != {SOKOL111_CAPTURED_AT}:
        return FAIL, f"captures {captures}, row capture times {sorted(times)}"
    refs = sorted({r for row in rows for key in _ROW_REF_FIELDS for r in row.get(key) or []})
    snapshot_id = (answer.get("snapshot") or {}).get("snapshot_id")
    if not refs or not snapshot_id:
        return FAIL, f"{len(refs)} evidence refs, snapshot {snapshot_id}"
    for start in range(0, len(refs), MAX_EVIDENCE_REFS):
        batch = refs[start : start + MAX_EVIDENCE_REFS]
        request = {
            "mode": "evidence",
            "snapshot_id": snapshot_id,
            "evidence_refs": batch,
            **BINDING_PICTURE_CONTEXT,
        }
        ok, evidence = _tool_call(
            url, 41 + start // MAX_EVIDENCE_REFS, "get_binding_picture", {"request": request}
        )
        if not ok:
            return FAIL, str(evidence)
        entries = (evidence.get("data") or {}).get("entries") or []
        if (
            evidence.get("outcome") != "ANSWERED"
            or [e.get("ref") for e in entries] != batch
            or {e.get("status") for e in entries} != {"RESOLVED"}
            or not all(e.get("kind") and e.get("evidence") for e in entries)
        ):
            return (
                FAIL,
                f"evidence drill-down: outcome {evidence.get('outcome')}, {len(entries)}/{len(batch)} entries",
            )
    observed = sum(row["status"] == "PROMISED_AND_OBSERVED" for row in rows)
    return PASS, (
        f"T {SOKOL111_CAPTURED_AT}; {len(rows)} frozen rows ({observed} PROMISED_AND_OBSERVED); "
        f"{len(refs)} refs resolved on its snapshot"
    )


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
    """Rejected means no MCP result was served. Caddy answers a Host that matches no site with an empty
    `200`; that reaches nothing behind the edge, so a non-2xx status is not required."""
    body = json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {}}).encode()
    status, raw = _request("POST", url, body, _HEADERS, host="not-the-demo.invalid")
    try:
        served = "result" in json.loads(raw)
    except (ValueError, TypeError):
        served = False
    if served:
        return FAIL, f"invalid Host reached the MCP server (HTTP {status})"
    return PASS, f"invalid Host not served ({'connection refused' if status is None else status})"


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


EDGE_CHECKS = frozenset(
    {
        "non-MCP routes closed",
        "invalid Host rejected",
        "oversized body rejected",
        "rate limit enforced",
    }
)


def run(args: argparse.Namespace) -> list[tuple[str, str, str]]:
    allowlist = PROFILE_TOOL_ALLOWLISTS[args.profile]
    checks = [
        ("anonymous initialize", lambda: check_initialize(args.url)),
        ("tool inventory (frozen allowlist)", lambda: check_tool_inventory(args.url, allowlist)),
    ]
    if args.profile == "pitstop":
        checks.append(
            (
                "Pitstop answer + evidence drill-down",
                lambda: check_pitstop_answer_and_drilldown(args.url, args.date),
            )
        )
    else:
        checks.append(
            (
                "Sokol111 consumers + evidence drill-down",
                lambda: check_sokol111_consumers_and_drilldown(args.url),
            )
        )
    if args.profile == "sokol111-v08":
        checks.append(
            (
                "binding picture + evidence drill-down",
                lambda: check_binding_picture_and_drilldown(args.url),
            )
        )
    checks += [
        (
            "source-dependent tools refuse",
            lambda: check_source_dependent_tools_refuse(args.url, args.date),
        ),
        ("non-MCP routes closed", lambda: check_closed_routes(args.url)),
        ("invalid Host rejected", lambda: check_invalid_host(args.url)),
        ("oversized body rejected", lambda: check_oversized_body(args.url, args.oversize_bytes)),
        # last: it may exhaust the budget the checks above need
        ("rate limit enforced", lambda: check_rate_limit(args.url, args.expect_429_within)),
    ]
    return [
        (name, SKIPPED, "--local-app: no edge in front of AIP")
        if args.local_app and name in EDGE_CHECKS
        else (name, *check())
        for name, check in checks
    ]


def build_parser() -> argparse.ArgumentParser:
    yesterday = datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="the public MCP URL, e.g. https://host/mcp")
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILE_TOOL_ALLOWLISTS),
        default="pitstop",
        help="which hosted dataset the supported-answer check expects",
    )
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
    parser.add_argument(
        "--local-app",
        action="store_true",
        help="rehearsal against AIP without the edge: skip the four edge checks",
    )
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
