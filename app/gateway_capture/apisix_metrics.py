"""v0.7.0 I2.2: the separate APISIX measurement capture tool (I2 spec §4.2-§4.3, contract §2).

Scrapes the `prometheus` plugin's text endpoint at two boundaries of an observation window, waits at
each boundary until two consecutive normalized scrapes are identical (bounded by a timeout), and writes
the three fixture files: `apisix-metrics-start.txt`, `apisix-metrics-end.txt` and
`apisix-measurement-manifest.json` (`aip-apisix-measurement/1`). It never contacts the Admin API and
needs no credential. It never emits a source value in a log line or error: every failure is a fixed
`MetricsCaptureError` code.

Environment, route coverage, disabled labels and the no-restart assertion are operator-asserted
capture context (I2 spec §2): a single scrape cannot prove them, so they are arguments, and
`--no-restart` defaults to *not asserted*, which makes the window unestablished rather than guessed.

    python -m app.gateway_capture.apisix_metrics \\
        --metrics-url http://127.0.0.1:9091/apisix/prometheus/metrics \\
        --gateway-instance-id gw-prod-1 --environment prod --apisix-version 3.19.0 \\
        --route-coverage orders-route=true --no-restart --window-seconds 600 --out ./measurement
"""

import argparse
import http.client
import json
import re
import sys
import time
import urllib.parse
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.sources.apisix_measurement_contract import (
    END_FILE,
    MANIFEST_FILE,
    MANIFEST_SCHEMA,
    METRIC_NAME,
    START_FILE,
    MeasurementRejection,
    extract_sha256,
    render_extract,
    validate_fixture,
)

_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_SAMPLE = re.compile(rf"^{METRIC_NAME}\{{(.*)\}} (\S+)$")
_LABEL = re.compile(r'([a-z_][a-z0-9_]*)="((?:[^"\\]|\\.)*)"')


class MetricsCaptureError(Exception):
    """A fixed, value-free failure code; the exception carries nothing from the source."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class MetricsSource(Protocol):
    def scrape(self) -> str: ...


def normalize_scrape(text: str) -> bytes:
    """Keep only `apisix_http_status`, drop the runtime `node` label, give labels alphabetical order,
    sum series that become identical once `node` is gone (one series per APISIX node), and render the
    canonical extract bytes. A sample that cannot be read exactly is a fixed error, never a guess."""
    totals: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)
    for line in text.splitlines():
        if not line.startswith(f"{METRIC_NAME}{{"):
            continue
        match = _SAMPLE.match(line)
        if not match or not match.group(2).isdigit():
            raise MetricsCaptureError("GWM_CAPTURE_MALFORMED_SCRAPE")
        body = match.group(1)
        pairs = _LABEL.findall(body)
        if ",".join(f'{name}="{value}"' for name, value in pairs) != body:
            raise MetricsCaptureError("GWM_CAPTURE_MALFORMED_SCRAPE")
        labels = tuple(sorted((name, value) for name, value in pairs if name != "node"))
        if len({name for name, _ in labels}) != len(labels):
            raise MetricsCaptureError("GWM_CAPTURE_MALFORMED_SCRAPE")
        totals[labels] += int(match.group(2))
    return render_extract([(dict(labels), value) for labels, value in totals.items()])


@dataclass(frozen=True)
class Boundary:
    extract: bytes
    settled: bool
    scrape_count: int
    at: datetime  # when the boundary was captured (UTC)
    stable_seconds: int  # whole seconds the final extract was observed unchanged


DEFAULT_QUIET_SECONDS = 20.0
DEFAULT_SETTLE_TIMEOUT = 120.0
DEFAULT_POLL_INTERVAL = 2.0


def settle(
    source: MetricsSource,
    *,
    timeout: float,
    poll_interval: float,
    quiet_seconds: float = DEFAULT_QUIET_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Boundary:
    """Counters lag behind traffic (I0 F4): wait for two consecutive identical normalized scrapes
    that are at least `quiet_seconds` apart. On timeout the last extract is kept with
    `settled=False`; failing to settle never manufactures zero.

    The quiet period is the I2.2 finding behind the default: against real APISIX 3.19.0 in etcd mode
    the series for traffic appeared ~14 s after the requests, and scrapes taken seconds apart were
    identical (and empty) throughout the lag, so "two identical scrapes" alone settled on the wrong
    extract. `quiet_seconds=0` is the bare contract rule."""
    deadline = monotonic() + timeout
    previous: bytes | None = None
    stable_since = monotonic()
    count = 0
    while True:
        current = normalize_scrape(source.scrape())
        count += 1
        at = monotonic()
        if current != previous:
            previous, stable_since = current, at
        elif at - stable_since >= quiet_seconds:
            return Boundary(current, True, count, now(), int(at - stable_since))
        if at >= deadline:
            return Boundary(current, False, count, now(), int(at - stable_since))
        sleep(poll_interval)


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Fixture:
    start: bytes
    end: bytes
    manifest: bytes


def build_fixture(
    start: Boundary,
    end: Boundary,
    *,
    gateway_instance_id: str,
    environment: str,
    apisix_version: str,
    route_coverage: Mapping[str, bool],
    disabled_labels: Sequence[str],
    no_restart: bool,
) -> Fixture:
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "gateway_instance_id": gateway_instance_id,
        "environment": environment,
        "apisix_version": apisix_version,
        "window_start": _timestamp(start.at),
        "window_end": _timestamp(end.at),
        "start_settled": start.settled,
        "end_settled": end.settled,
        "start_scrape_count": start.scrape_count,
        "end_scrape_count": end.scrape_count,
        "start_stable_seconds": start.stable_seconds,
        "end_stable_seconds": end.stable_seconds,
        "no_restart": no_restart,
        "disabled_labels": sorted(set(disabled_labels)),
        "route_coverage": dict(sorted(route_coverage.items())),
        "start_sha256": extract_sha256(start.extract),
        "end_sha256": extract_sha256(end.extract),
    }
    manifest_bytes = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()
    try:  # the tool never writes a fixture the production validator would refuse
        validate_fixture(
            manifest_bytes,
            start.extract,
            end.extract,
            gateway_instance_id=gateway_instance_id,
            environment=environment,
        )
    except MeasurementRejection as exc:
        raise MetricsCaptureError(exc.code) from None
    return Fixture(start=start.extract, end=end.extract, manifest=manifest_bytes)


def capture_window(
    source: MetricsSource,
    *,
    gateway_instance_id: str,
    environment: str,
    apisix_version: str,
    route_coverage: Mapping[str, bool],
    disabled_labels: Sequence[str],
    no_restart: bool,
    window_seconds: float,
    settle_timeout: float = DEFAULT_SETTLE_TIMEOUT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    quiet_seconds: float = DEFAULT_QUIET_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Fixture:
    start = settle(
        source, timeout=settle_timeout, poll_interval=poll_interval, quiet_seconds=quiet_seconds,
        monotonic=monotonic, sleep=sleep, now=now,
    )  # fmt: skip
    sleep(window_seconds)
    end = settle(
        source, timeout=settle_timeout, poll_interval=poll_interval, quiet_seconds=quiet_seconds,
        monotonic=monotonic, sleep=sleep, now=now,
    )  # fmt: skip
    return build_fixture(
        start,
        end,
        gateway_instance_id=gateway_instance_id,
        environment=environment,
        apisix_version=apisix_version,
        route_coverage=route_coverage,
        disabled_labels=disabled_labels,
        no_restart=no_restart,
    )


# --------------------------------------------------------------------------------------------
# Real Prometheus endpoint client (stdlib only - no runtime HTTP dependency)
# --------------------------------------------------------------------------------------------


class UrllibMetricsSource:
    """Built on `http.client` with an explicit http/https scheme check (a configured URL can never
    name `file://` or another scheme)."""

    def __init__(self, *, metrics_url: str, timeout: float = 15.0):
        parts = urllib.parse.urlsplit(metrics_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise MetricsCaptureError("GWM_CAPTURE_URL_UNSUPPORTED")
        self._scheme, self._host, self._port = parts.scheme, parts.hostname, parts.port
        self._target = parts.path or "/"
        if parts.query:
            self._target += f"?{parts.query}"
        self._timeout = timeout

    def scrape(self) -> str:
        connection_class = (
            http.client.HTTPSConnection if self._scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_class(self._host, self._port, timeout=self._timeout)
        try:
            connection.request("GET", self._target, headers={"Accept": "text/plain"})
            response = connection.getresponse()
            data = response.read(_MAX_RESPONSE_BYTES + 1)
            status = response.status
        except (OSError, http.client.HTTPException):
            raise MetricsCaptureError("GWM_CAPTURE_UNREACHABLE") from None
        finally:
            connection.close()
        if len(data) > _MAX_RESPONSE_BYTES:
            raise MetricsCaptureError("GWM_CAPTURE_MALFORMED_SCRAPE")
        if status != 200:
            raise MetricsCaptureError("GWM_CAPTURE_SCRAPE_FAILED")
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise MetricsCaptureError("GWM_CAPTURE_MALFORMED_SCRAPE") from None


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------


def _route_coverage(values: Sequence[str]) -> dict[str, bool]:
    coverage: dict[str, bool] = {}
    for item in values:
        route, separator, flag = item.rpartition("=")
        if not separator or not route or flag not in ("true", "false"):
            raise MetricsCaptureError("GWM_CAPTURE_ARGUMENT_INVALID")
        coverage[route] = flag == "true"
    return coverage


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.gateway_capture.apisix_metrics",
        description="Capture an APISIX measurement fixture (aip-apisix-measurement/1) over one "
        "observation window from the Prometheus plugin's text endpoint.",
    )
    parser.add_argument("--metrics-url", required=True)
    parser.add_argument("--gateway-instance-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--apisix-version", required=True)
    parser.add_argument(
        "--route-coverage", action="append", default=[], metavar="ROUTE=true|false",
        help="operator assertion: the prometheus plugin was enabled (true) or not (false) on this "
        "Route for the whole window; repeatable",
    )  # fmt: skip
    parser.add_argument("--disabled-label", action="append", default=[], metavar="LABEL")
    parser.add_argument(
        "--no-restart", action="store_true",
        help="operator assertion that the gateway did not restart during the window",
    )  # fmt: skip
    parser.add_argument("--window-seconds", required=True, type=float)
    parser.add_argument("--settle-timeout", type=float, default=DEFAULT_SETTLE_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--quiet-seconds", type=float, default=DEFAULT_QUIET_SECONDS)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if (
            args.window_seconds <= 0
            or args.settle_timeout <= 0
            or args.poll_interval <= 0
            or args.quiet_seconds < 0
        ):
            raise MetricsCaptureError("GWM_CAPTURE_ARGUMENT_INVALID")
        fixture = capture_window(
            UrllibMetricsSource(metrics_url=args.metrics_url),
            gateway_instance_id=args.gateway_instance_id,
            environment=args.environment,
            apisix_version=args.apisix_version,
            route_coverage=_route_coverage(args.route_coverage),
            disabled_labels=args.disabled_label,
            no_restart=args.no_restart,
            window_seconds=args.window_seconds,
            settle_timeout=args.settle_timeout,
            poll_interval=args.poll_interval,
            quiet_seconds=args.quiet_seconds,
        )
    except MetricsCaptureError as exc:
        print(f"refused: {exc.code}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / START_FILE).write_bytes(fixture.start)
    (args.out / END_FILE).write_bytes(fixture.end)
    (args.out / MANIFEST_FILE).write_bytes(fixture.manifest)
    print(f"captured: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
