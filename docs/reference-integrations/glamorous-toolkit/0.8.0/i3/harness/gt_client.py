"""GT 0.8.0 I3: a minimal client for the GT MCP server, for the operator's preflight only."""

from __future__ import annotations

import json
import urllib.request


class GtClient:
    def __init__(self, url: str) -> None:
        self.url = url

    def rpc(self, method: str, params: dict) -> dict:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        request = urllib.request.Request(
            self.url,
            body.encode(),
            {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)["result"]

    def tool_names(self) -> list[str]:
        return [tool["name"] for tool in self.rpc("tools/list", {})["tools"]]

    def text(self, tool: str, **arguments: str) -> str:
        """The text parts of a tool result; a JSON string is decoded."""
        result = self.rpc("tools/call", {"name": tool, "arguments": arguments})
        parts = []
        for part in result.get("content", []):
            if part.get("type") != "text":
                continue
            text = part["text"]
            try:
                decoded = json.loads(text)
            except ValueError:
                decoded = None
            parts.append(decoded if isinstance(decoded, str) else text)
        return "\n".join(parts)

    def stored(self) -> dict[str, str]:
        """The object storage as reason → object id."""
        items = json.loads(self.text("listObjectStorage"))["items"]
        return {item["reasonString"]: item["objectId"] for item in items}
