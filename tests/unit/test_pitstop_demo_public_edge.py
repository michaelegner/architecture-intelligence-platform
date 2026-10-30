"""Public read-only hosted demo: the external acceptance script (`hosted/verify_public_edge.py`).

The edge that makes anonymous `/mcp` safe lives outside the repository, so the checker is the evidence.
These tests run it against a local stub that plays the edge, once correctly gated and once with each
guard removed, and require the matching check (and only it) to FAIL - proving every check can fail.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.architecture_intelligence.api_usage_contracts import REFUSAL_CODES_QUERY
from app.architecture_intelligence.destination_consumer_contracts import REFUSAL_CODES
from app.mcp.server import build_mcp_server, mcp_server
from app.sources.owner_ids import topic_owned_id

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO / "examples" / "pitstop-demo"
C1_BINDING_PICTURE = REPO / "docs" / "specifications" / "0.8.0" / "i2-vectors" / "c1-expected.json"
_spec = importlib.util.spec_from_file_location(
    "verify_public_edge", DEMO_DIR / "hosted" / "verify_public_edge.py"
)
assert _spec and _spec.loader
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

HOST = "demo.example"
BODY_CAP = 64 * 1024
RATE_LIMIT = 12  # above the MCP requests the earlier checks make (ten for sokol111-v08)


class Guards:
    def __init__(self, **disabled: bool) -> None:
        self.extra_tool = disabled.get("extra_tool", False)
        self.open_import = disabled.get("open_import", False)
        self.any_host = disabled.get("any_host", False)
        self.no_body_cap = disabled.get("no_body_cap", False)
        self.no_rate_limit = disabled.get("no_rate_limit", False)
        self.empty_200_for_unknown_host = disabled.get("empty_200_for_unknown_host", False)
        self.invented_answer = disabled.get("invented_answer", False)
        self.no_sokol111_attachment = disabled.get("no_sokol111_attachment", False)
        self.only_image_row = disabled.get("only_image_row", False)
        self.later_capture = disabled.get("later_capture", False)
        self.missing_entry = disabled.get("missing_entry", False)
        self.empty_evidence = disabled.get("empty_evidence", False)
        self.many_refs = disabled.get("many_refs", False)
        self.no_binding_tool = disabled.get("no_binding_tool", False)
        self.open_binding_route = disabled.get("open_binding_route", False)
        self.wrong_crossing = disabled.get("wrong_crossing", False)
        self.missing_limitation = disabled.get("missing_limitation", False)
        self.second_page = disabled.get("second_page", False)
        self.binding_later_capture = disabled.get("binding_later_capture", False)
        self.binding_missing_entry = disabled.get("binding_missing_entry", False)
        self.row_without_mapping = disabled.get("row_without_mapping", False)
        self.row_without_time = disabled.get("row_without_time", False)
        self.promise_on_unresolved = disabled.get("promise_on_unresolved", False)
        self.tools: frozenset[str] = verify.PUBLIC_TOOL_ALLOWLIST
        self.evidence_batches: list[list[str]] = []
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
            if self.path.startswith("/api/binding-picture") and guards.open_binding_route:
                return self._send(200, {})
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
                names = set(guards.tools) | ({"import_graph"} if guards.extra_tool else set())
                if guards.no_binding_tool:
                    names.discard("get_binding_picture")
                result = {"tools": [{"name": name} for name in sorted(names)]}
            elif message["params"]["name"] == "get_binding_picture":
                result = {"structuredContent": _binding_picture_answer(args["request"], guards)}
            elif (
                message["params"]["name"] == "get_destination_consumers"
                and args["request"]["destination_id"] == verify.SOKOL111_TOPIC_ID
            ):
                result = {"structuredContent": _sokol111_answer(args["request"], guards)}
            elif message["params"]["name"] in (
                "get_api_consumer_usage",
                "get_destination_consumers",
            ):
                code = (
                    "MEASUREMENT_WINDOW_NOT_AVAILABLE"
                    if message["params"]["name"] == "get_api_consumer_usage"
                    else "UNKNOWN_DESTINATION"
                )
                answer = {"outcome": "NOT_ANSWERED", "data": None, "limitations": [{"code": code}]}
                if guards.invented_answer:
                    answer = {"outcome": "PARTIAL", "data": {"rows": []}, "limitations": []}
                result = {"structuredContent": answer}
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


def _sokol111_answer(request: dict, guards: Guards) -> dict:
    """The frozen Sokol111 C1 reading, as the hosted instance answers it."""
    if request["mode"] == "evidence":
        refs = request["evidence_refs"]
        assert len(refs) <= verify.MAX_EVIDENCE_REFS
        guards.evidence_batches.append(refs)
        content = (
            {}
            if guards.empty_evidence
            else {"kind": "ATTACHMENT", "evidence": {"kind": "ATTACHMENT"}}
        )
        entries = [{"ref": ref, "status": "RESOLVED", **content} for ref in refs]
        return {
            "outcome": "ANSWERED",
            "data": {"entries": entries[1:] if guards.missing_entry else entries},
        }
    extra = [f"destination-evidence:x{i:02d}" for i in range(25)] if guards.many_refs else []
    rows = [
        {
            "group_id": group,
            "outcome": "RESOLVED",
            "service_id": f"service:{group}",
            "captured_at": "2026-10-21T17:53:57Z",
            "attachment_evidence_refs": [f"destination-evidence:{group}-a", *extra],
            "mapping_evidence_refs": [f"destination-evidence:{group}-m"],
        }
        for group in ("ecommerce-image-service", "ecommerce-product-query-service")
    ]
    if guards.only_image_row:
        rows = rows[:1]
    if guards.later_capture:
        rows[1]["captured_at"] = "2026-10-21T17:56:03Z"
    return {
        "outcome": "PARTIAL",
        "snapshot": {"snapshot_id": "aip:snapshot:v1:" + "1" * 64},
        "data": {"rows": [] if guards.no_sokol111_attachment else rows},
        "limitations": [{"code": "CAPTURE_SCOPE_LIMITED"}],
    }


def _binding_picture_answer(request: dict, guards: Guards) -> dict:
    """The frozen v0.8 C1 binding picture, as the hosted v0.8 instance answers it."""
    if request["mode"] == "evidence":
        refs = request["evidence_refs"]
        assert len(refs) <= verify.MAX_EVIDENCE_REFS
        assert request["snapshot_id"] == "aip:snapshot:v1:" + "2" * 64
        entries = [
            {"ref": ref, "status": "RESOLVED", "kind": "ATTACHMENT", "evidence": {"kind": "A"}}
            for ref in refs
        ]
        return {
            "outcome": "ANSWERED",
            "data": {"entries": entries[1:] if guards.binding_missing_entry else entries},
        }
    # The real C1 shape: every row has one attachment and one mapping ref at T; only the two
    # PROMISED_AND_OBSERVED rows (3 and 4) carry promise refs.
    rows = [
        {
            **row,
            "captured_at": verify.SOKOL111_CAPTURED_AT,
            "promise_evidence_refs": (
                [f"binding-evidence:p{i}"] if row["status"] == "PROMISED_AND_OBSERVED" else []
            ),
            "attachment_evidence_refs": [f"binding-evidence:a{i}"],
            "mapping_evidence_refs": [f"binding-evidence:m{i}"],
        }
        for i, row in enumerate(verify.BINDING_PICTURE_ROWS)
    ]
    if guards.wrong_crossing:
        rows[0]["crossing"] = "INSIDE"
    if guards.binding_later_capture:
        rows[3]["captured_at"] = "2026-10-21T17:56:03Z"
    if guards.row_without_mapping:
        rows[5]["mapping_evidence_refs"] = []
    if guards.row_without_time:
        del rows[5]["captured_at"]
    if guards.promise_on_unresolved:
        rows[0]["promise_evidence_refs"] = ["binding-evidence:p0"]
    codes = list(verify.BINDING_PICTURE_LIMITATIONS)
    if guards.missing_limitation:
        codes.remove("PROMISES_ASSUMED_CONFIRMED")
    return {
        "outcome": "PARTIAL",
        "snapshot": {"snapshot_id": "aip:snapshot:v1:" + "2" * 64},
        "data": {
            "capture_sources": [
                {"broker_id": verify.SOKOL111_BROKER, "captured_at": verify.SOKOL111_CAPTURED_AT}
            ],
            "rows": rows,
            "page": {"next_cursor": "next" if guards.second_page else None},
        },
        "limitations": [{"code": code} for code in codes],
    }


def _run(
    guards: Guards,
    *,
    rate_limit: int | None = RATE_LIMIT + 1,
    profile: str = "pitstop",
    local_app: bool = False,
) -> dict[str, str]:
    guards.tools = verify.PROFILE_TOOL_ALLOWLISTS[profile]
    server = _edge(guards)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        argv = [
            "--url",
            f"http://127.0.0.1:{port}/mcp",
            "--date",
            "2026-10-12",
            "--profile",
            profile,
        ]
        if rate_limit is not None:
            argv += ["--expect-429-within", str(rate_limit)]
        if local_app:
            argv.append("--local-app")
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
    registered = {tool.name for tool in asyncio.run(mcp_server.list_tools())}
    assert verify.PUBLIC_TOOL_ALLOWLIST == registered


def test_the_v08_allowlist_is_the_registry_with_the_binding_picture_flag():
    flagged = build_mcp_server(binding_picture=True)
    registered = {tool.name for tool in asyncio.run(flagged.list_tools())}
    assert verify.PROFILE_TOOL_ALLOWLISTS["sokol111-v08"] == registered


def test_copied_refusal_codes_match_the_contracts():
    assert verify.API_USAGE_REFUSAL_CODES == {code.value for code in REFUSAL_CODES_QUERY}
    assert verify.DESTINATION_REFUSAL_CODES == {code.value for code in REFUSAL_CODES}


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
        ("invented_answer", "source-dependent tools refuse"),
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


def test_the_sokol111_topic_id_is_the_frozen_package_topic():
    assert verify.SOKOL111_TOPIC_ID == topic_owned_id(
        stable_broker_id=verify.SOKOL111_BROKER,
        normalized_namespace_or_empty="",
        exact_topic_address="catalog.product.events",
    )


def test_the_sokol111_profile_passes_on_a_correctly_gated_edge():
    results = _run(Guards(), profile="sokol111")
    assert "Pitstop answer + evidence drill-down" not in results
    assert set(results.values()) == {verify.PASS}, results


@pytest.mark.parametrize(
    "guard",
    # no attachment; one frozen consumer missing; a row at C2's T; one requested ref unanswered
    # ...; a RESOLVED entry without its kind and evidence content
    [
        "no_sokol111_attachment",
        "only_image_row",
        "later_capture",
        "missing_entry",
        "empty_evidence",
    ],
)
def test_the_sokol111_check_fails_when_the_answer_departs_from_c1(guard):
    results = _run(Guards(**{guard: True}), profile="sokol111")
    assert {k for k, v in results.items() if v == verify.FAIL} == {
        "Sokol111 consumers + evidence drill-down"
    }, results


def test_the_sokol111_drilldown_resolves_more_than_twenty_refs_in_batches():
    guards = Guards(many_refs=True)
    results = _run(guards, rate_limit=None, profile="sokol111")
    assert results["Sokol111 consumers + evidence drill-down"] == verify.PASS, results
    assert [len(batch) for batch in guards.evidence_batches] == [20, 9]


def test_the_binding_picture_constants_are_the_frozen_c1_vector():
    expected = json.loads(C1_BINDING_PICTURE.read_text())
    assert expected["request"] == verify.BINDING_PICTURE_CONTEXT
    assert list(verify.BINDING_PICTURE_LIMITATIONS) == sorted(expected["limitations"])
    rows = sorted(
        expected["rows"],
        key=lambda r: (r["broker_id"], r["topic_name"], r["consumer_service_id"]),
    )
    assert list(verify.BINDING_PICTURE_ROWS) == rows


def test_the_sokol111_v08_profile_passes_on_a_correctly_gated_edge():
    results = _run(Guards(), profile="sokol111-v08")
    assert "Sokol111 consumers + evidence drill-down" in results
    assert set(results.values()) == {verify.PASS}, results


@pytest.mark.parametrize(
    ("guard", "failing_check"),
    [
        # the v0.7.2 deployment: six tools, no binding picture (the before state)
        ("no_binding_tool", "tool inventory (frozen allowlist)"),
        ("extra_tool", "tool inventory (frozen allowlist)"),
        ("open_binding_route", "non-MCP routes closed"),
        ("wrong_crossing", "binding picture + evidence drill-down"),
        ("missing_limitation", "binding picture + evidence drill-down"),
        ("second_page", "binding picture + evidence drill-down"),
        ("binding_later_capture", "binding picture + evidence drill-down"),
        ("binding_missing_entry", "binding picture + evidence drill-down"),
        # per row, not as a union across rows (owner review of #668)
        ("row_without_mapping", "binding picture + evidence drill-down"),
        ("row_without_time", "binding picture + evidence drill-down"),
        ("promise_on_unresolved", "binding picture + evidence drill-down"),
    ],
)
def test_the_sokol111_v08_profile_fails_when_its_guard_is_removed(guard, failing_check):
    results = _run(Guards(**{guard: True}), profile="sokol111-v08")
    assert {k for k, v in results.items() if v == verify.FAIL} == {failing_check}, results


def test_local_app_skips_exactly_the_edge_checks():
    """Without an edge every edge guard is absent; only the edge checks are skipped, never passed."""
    guards = Guards(open_import=True, open_binding_route=True, any_host=True, no_body_cap=True)
    results = _run(guards, profile="sokol111-v08", local_app=True)
    assert {k for k, v in results.items() if v == verify.SKIPPED} == verify.EDGE_CHECKS
    assert {v for k, v in results.items() if k not in verify.EDGE_CHECKS} == {verify.PASS}


def test_local_app_still_runs_the_answer_checks():
    results = _run(Guards(wrong_crossing=True), profile="sokol111-v08", local_app=True)
    assert results["binding picture + evidence drill-down"] == verify.FAIL


@pytest.mark.parametrize("url", ["https://mcp.daip.io/mcp", "http://10.0.0.5:8000/mcp"])
def test_local_app_refuses_a_non_loopback_url(url):
    with pytest.raises(SystemExit) as raised:
        verify.main(["--url", url, "--profile", "sokol111-v08", "--local-app"])
    assert raised.value.code == 2
