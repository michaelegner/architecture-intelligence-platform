from __future__ import annotations

import json

import pytest
from mcp_types.jsonrpc import INVALID_REQUEST
from starlette.types import Message, Receive, Scope, Send

import app.mcp.guard as guard_module
from app.mcp.guard import MCP_PATH, ModernProtocolGuard


@pytest.mark.asyncio
async def test_oversized_body_is_rejected_before_remaining_chunks_are_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guard_module, "_MAX_REQUEST_BODY_BYTES", 8)

    downstream_called = False
    receive_calls = 0
    chunks: list[Message] = [
        {"type": "http.request", "body": b'{"id":1,', "more_body": True},
        {"type": "http.request", "body": b'"x":', "more_body": True},
        {"type": "http.request", "body": b'"ignored"}', "more_body": False},
    ]
    sent: list[Message] = []

    async def downstream_app(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal downstream_called
        downstream_called = True

    async def receive() -> Message:
        nonlocal receive_calls
        message = chunks[receive_calls]
        receive_calls += 1
        return message

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": MCP_PATH,
        "raw_path": MCP_PATH.encode(),
        "query_string": b"",
        "headers": [],
        "client": None,
        "server": None,
        "root_path": "",
    }

    await ModernProtocolGuard(downstream_app)(scope, receive, send)

    assert receive_calls == 2
    assert downstream_called is False
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413
    assert sent[1]["type"] == "http.response.body"

    payload = json.loads(sent[1]["body"])
    assert payload == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {
            "code": INVALID_REQUEST,
            "message": "Request body exceeds the maximum allowed size",
        },
    }
