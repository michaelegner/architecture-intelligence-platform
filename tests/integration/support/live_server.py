"""v0.4.1 I3.1 - extracted from `tests/integration/test_mcp_independent_client_golden_path.py`
(v0.4.0 I2.4) so `benchmarks/snapshot_read_cost.py`'s CLI entrypoint can reuse the identical "serve
the real production app over real network HTTP" mechanism rather than duplicating it. No behavior
change from the original private helpers - only relocation.

Runs the given ASGI app under a real `uvicorn` server bound to a loopback TCP port - the same server
this project's `Dockerfile` runs - so a client reaches it over ordinary network HTTP rather than an
in-process ASGI shortcut (`fastapi.testclient.TestClient`/`httpx.ASGITransport`), which would prove
nothing about a real listener (see the golden-path test module's own docstring for the original
review finding this addresses).
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager

import uvicorn

_SERVER_STARTUP_TIMEOUT_SECONDS = 30.0
_SERVER_SHUTDOWN_TIMEOUT_SECONDS = 10.0


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def serve_over_real_http(served_app, *, port: int):
    """Runs `served_app` under a real `uvicorn` server bound to a loopback TCP port - the same
    server this project's `Dockerfile` uses - so a client reaches it over ordinary network HTTP.

    Deliberately NOT `fastapi.testclient.TestClient`/`httpx.ASGITransport` (PR #80 review finding):
    those dispatch straight into the ASGI callable, so a loopback-looking base_url proves nothing
    about a real listener."""
    config = uvicorn.Config(served_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + _SERVER_STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if time.monotonic() > deadline:
            server.should_exit = True
            thread.join(timeout=_SERVER_SHUTDOWN_TIMEOUT_SECONDS)
            raise TimeoutError("uvicorn did not report startup within the bounded wait")
        time.sleep(0.02)
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=_SERVER_SHUTDOWN_TIMEOUT_SECONDS)
