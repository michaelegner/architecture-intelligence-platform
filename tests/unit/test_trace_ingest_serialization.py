"""v0.6.3 I1 (spec §3.3): `POST /v1/traces` ingests off the event loop, one batch at a time.

The ingestion function is replaced by a recorder, so these tests cover the route's concurrency
contract only; the real ingestion path is exercised by `tests/integration/test_trace_ingest_responsiveness.py`.
"""

import asyncio
import threading
import time

import httpx
import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

import app.api.telemetry as telemetry_route
from app.deps import get_trace_ingest_lock
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings

_CONTENT_TYPE = "application/x-protobuf"
_BATCHES = 3


def _payload() -> bytes:
    span = Span(
        trace_id=bytes.fromhex("4bf92f3577b34da6a3ce929d0e0e4736"),
        span_id=bytes.fromhex("b7ad6b7169203331"),
        name="GET /products/{id}",
        kind=Span.SPAN_KIND_CLIENT,
        start_time_unix_nano=1_700_000_000_000_000_000,
        end_time_unix_nano=1_700_000_000_100_000_000,
    )
    resource = Resource(
        attributes=[KeyValue(key="service.name", value=AnyValue(string_value="OrderService"))]
    )
    return ExportTraceServiceRequest(
        resource_spans=[ResourceSpans(resource=resource, scope_spans=[ScopeSpans(spans=[span])])]
    ).SerializeToString()


def _app():
    app = create_app()
    app.state.driver = None
    app.state.settings = Settings(
        config=AppConfig(), secrets=Secrets(neo4j_user="unused", neo4j_password="unused")
    )
    return app


class _Recorder:
    """Stands in for `ingest_trace_spans`: counts how many calls overlap, and which thread ran them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.threads: set[int] = set()

    def __call__(self, spans, **_kwargs) -> None:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.threads.add(threading.get_ident())
        time.sleep(0.1)
        with self._lock:
            self.active -= 1


async def _post_concurrently(app) -> list[int]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(
            *(
                client.post(
                    "/v1/traces", content=_payload(), headers={"content-type": _CONTENT_TYPE}
                )
                for _ in range(_BATCHES)
            )
        )
    return [response.status_code for response in responses]


@pytest.mark.asyncio
async def test_concurrent_batches_are_ingested_one_at_a_time_off_the_event_loop(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(telemetry_route, "ingest_trace_spans", recorder)

    statuses = await _post_concurrently(_app())

    assert statuses == [200] * _BATCHES
    assert recorder.max_active == 1
    assert threading.get_ident() not in recorder.threads


@pytest.mark.asyncio
async def test_without_the_ingest_lock_batches_overlap(monkeypatch):
    """The guard proof for the test above: with the lock replaced by a no-op, the same requests
    overlap, so the serialization test fails when the guard is removed."""
    recorder = _Recorder()
    monkeypatch.setattr(telemetry_route, "ingest_trace_spans", recorder)
    app = _app()

    class _NoLock:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_exc) -> None:
            return None

    app.dependency_overrides[get_trace_ingest_lock] = lambda: _NoLock()

    statuses = await _post_concurrently(app)

    assert statuses == [200] * _BATCHES
    assert recorder.max_active > 1
