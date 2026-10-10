"""Controlled two-Workload capture harness app (v0.6.0 I2.6a; I1 capture runbook §§2-3).

One image, two roles, selected by `ROLE`:

- `provider` (`pricing`, `legacy-pricing`): a Flask service with `GET /prices`, instrumented by the
  standard OpenTelemetry Flask (HTTP SERVER) instrumentation.
- `caller` (`orders`, `orders-canary`): a loop making real `GET http://$TARGET/prices` calls with
  `requests`, instrumented by the standard OpenTelemetry requests (HTTP CLIENT) instrumentation.

Nothing here builds a span by hand: every span comes from the SDK instrumentation of a real HTTP
call. The Resource is exactly `OTEL_SERVICE_NAME` plus `OTEL_RESOURCE_ATTRIBUTES`, which the
manifests fill from the Kubernetes Downward API (`k8s.pod.uid`, namespace, Pod name) and literals
(`k8s.deployment.name`, `k8s.cluster.uid`, `deployment.environment.name`) - never from a Collector
processor. `OTEL_SEMCONV_STABILITY_OPT_IN=http` makes the instrumentations emit the stable HTTP
conventions AIP reads (`http.request.method`, `http.route`).
"""

import logging
import os
import time

import requests
from flask import Flask, jsonify
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("locality-harness")


def _tracing() -> None:
    # Resource.create() reads OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES; nothing is added.
    provider = TracerProvider(resource=Resource.create())
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # OTEL_EXPORTER_OTLP_*
    trace.set_tracer_provider(provider)


def provider() -> None:
    app = Flask(__name__)
    FlaskInstrumentor().instrument_app(app)

    @app.get("/prices")
    def prices():  # pyright: ignore[reportUnusedFunction]
        return jsonify(service=os.environ["OTEL_SERVICE_NAME"], prices=[{"sku": "a", "eur": 1}])

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


def caller() -> None:
    target = os.environ["TARGET"]  # the provider's Kubernetes Service name
    peer_service = os.environ["TARGET_PEER_SERVICE"]  # its configured service.name

    def request_hook(span, _request) -> None:
        # peer.service is the configured name of the called service (OTel semantic conventions);
        # v0.5 needs it to identify a CLIENT_ONLY target. It is configuration, not inference.
        if span.is_recording():
            span.set_attribute("peer.service", peer_service)

    RequestsInstrumentor().instrument(request_hook=request_hook)
    interval = float(os.environ.get("CALL_INTERVAL_SECONDS", "1"))
    while True:
        try:
            response = requests.get(f"http://{target}/prices", timeout=5)
            LOG.info("GET %s/prices -> %s", target, response.status_code)
        except requests.RequestException as error:  # keep calling; the run record checks totals
            LOG.warning("GET %s/prices failed: %s", target, error)
        time.sleep(interval)


if __name__ == "__main__":
    _tracing()
    {"provider": provider, "caller": caller}[os.environ["ROLE"]]()
