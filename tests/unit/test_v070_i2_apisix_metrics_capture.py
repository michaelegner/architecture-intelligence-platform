"""v0.7.0 I2.2a: the APISIX measurement capture tool - normalization, settling, fixture building and
the real stdlib transport (a local HTTP server stands in for the Prometheus plugin endpoint)."""

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from app.gateway_capture.apisix_metrics import (
    MetricsCaptureError,
    UrllibMetricsSource,
    capture_window,
    main,
    normalize_scrape,
    settle,
)
from app.sources.apisix_measurement_contract import (
    END_FILE,
    MANIFEST_FILE,
    START_FILE,
    first_in_window_allowed,
    parse_extract,
    validate_fixture,
)

SPIKE = (
    Path(__file__).resolve().parents[2]
    / "docs/specifications/0.7.0/i0-spike/apisix/expected-capture.txt"
)


def _line(consumer: str, code: str, source: str, value: int, *, node: str | None = None) -> str:
    labels = (
        f'code="{code}",route="orders-route",matched_uri="/orders",matched_host="",service="",'
        f'consumer="{consumer}",request_type="traditional_http",request_llm_model="",'
        f'llm_model="",response_source="{source}"'
    )
    if node is not None:
        labels += f',node="{node}"'
    return f"apisix_http_status{{{labels}}} {value}"


NOISE = '# HELP apisix_http_status x\n# TYPE apisix_http_status counter\napisix_bandwidth{type="egress"} 9\n'


class ScriptedSource:
    """Returns the scripted scrape texts in order, repeating the last one."""

    def __init__(self, *texts: str) -> None:
        self._texts = list(texts)
        self.calls = 0

    def scrape(self) -> str:
        text = self._texts[min(self.calls, len(self._texts) - 1)]
        self.calls += 1
        return text


class Clock:
    def __init__(self) -> None:
        self.t = 0.0
        self.moment = datetime(2026, 10, 13, 10, 0, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds
        self.moment += timedelta(seconds=seconds)

    def now(self) -> datetime:
        return self.moment


def test_normalization_keeps_only_http_status_drops_node_sorts_labels_and_sums_nodes() -> None:
    text = NOISE + "\n".join(
        [
            _line("b", "200", "upstream", 4, node="10.0.0.2"),
            _line("a", "200", "upstream", 3, node="10.0.0.1"),
            _line("a", "200", "upstream", 2, node="10.0.0.2"),
        ]
    )
    out = normalize_scrape(text)
    series = parse_extract(out)  # the production validator accepts it
    by_consumer = {s.labels["consumer"]: s.value for s in series.values()}
    assert by_consumer == {"a": 5, "b": 4}  # one series per node collapses to one, counters summed
    assert b"node=" not in out and b"apisix_bandwidth" not in out and b"# " not in out
    assert out.decode().splitlines() == sorted(out.decode().splitlines())
    assert out.endswith(b"\n") and b"\r" not in out


def test_normalization_matches_the_i0_spike_extract_up_to_label_order() -> None:
    raw = SPIKE.read_text()
    series = parse_extract(normalize_scrape(raw))
    assert {(s.labels["consumer"], s.labels["code"], s.labels["response_source"]): s.value
            for s in series.values()} == {
        ("spike-alpha", "200", "upstream"): 3,
        ("spike-beta", "200", "upstream"): 1,
        ("", "401", "apisix"): 1,
        ("spike-gamma", "403", "apisix"): 1,
    }  # fmt: skip


def test_normalization_is_independent_of_input_order() -> None:
    lines = [_line("a", "200", "upstream", 1), _line("b", "404", "apisix", 2)]
    assert normalize_scrape("\n".join(lines)) == normalize_scrape("\n".join(reversed(lines)))


@pytest.mark.parametrize(
    "bad",
    [
        'apisix_http_status{code="200"} 1.5',
        'apisix_http_status{code="200"} NaN',
        'apisix_http_status{code="200",code="201"} 1',
        'apisix_http_status{code="200" route="r"} 1',
    ],
)
def test_an_unreadable_sample_is_a_fixed_error_never_a_guess(bad: str) -> None:
    with pytest.raises(MetricsCaptureError) as raised:
        normalize_scrape(bad)
    assert raised.value.code == "GWM_CAPTURE_MALFORMED_SCRAPE"
    assert "1.5" not in str(raised.value)


def test_an_empty_scrape_is_an_empty_extract() -> None:
    assert normalize_scrape("# nothing here\n") == b""


def test_settle_waits_for_two_identical_consecutive_scrapes() -> None:
    clock = Clock()
    source = ScriptedSource(
        _line("a", "200", "upstream", 1),
        _line("a", "200", "upstream", 2),  # still lagging
        _line("a", "200", "upstream", 3),
        _line("a", "200", "upstream", 3),
    )
    boundary = settle(
        source,
        timeout=30,
        poll_interval=1,
        quiet_seconds=0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        now=clock.now,
    )
    assert boundary.settled and boundary.scrape_count == 4
    assert parse_extract(boundary.extract).popitem()[1].value == 3


def test_settle_times_out_unsettled_and_keeps_the_last_extract() -> None:
    clock = Clock()
    counter = iter(range(1, 1000))

    class Moving:
        def scrape(self) -> str:
            return _line("a", "200", "upstream", next(counter))

    boundary = settle(
        Moving(),
        timeout=5,
        poll_interval=1,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        now=clock.now,
    )
    assert not boundary.settled and boundary.scrape_count >= 2  # never fewer than the attempts made
    assert boundary.extract  # the evidence stays inspectable; it is not turned into zero


def test_a_quiet_period_outlasts_a_lag_plateau_that_two_identical_scrapes_would_accept() -> None:
    """Real APISIX in etcd mode showed an unchanged (empty) extract for ~14 s after traffic: two
    identical scrapes seconds apart settled on it. The quiet period keeps waiting."""
    clock = Clock()
    plateau, arrived = "", _line("a", "200", "upstream", 4)

    class Lagging:
        def scrape(self) -> str:
            return arrived if clock.t >= 14 else plateau

    kwargs = {
        "timeout": 120,
        "poll_interval": 2,
        "monotonic": clock.monotonic,
        "sleep": clock.sleep,
    }
    bare = settle(Lagging(), quiet_seconds=0, now=clock.now, **kwargs)
    assert (
        bare.settled and bare.extract == b""
    )  # the false settle the quiet period exists to prevent
    clock.t = 0.0
    quiet = settle(Lagging(), quiet_seconds=20, now=clock.now, **kwargs)
    assert quiet.settled and parse_extract(quiet.extract).popitem()[1].value == 4


def test_settle_with_a_quiet_period_times_out_unsettled_if_the_extract_keeps_changing() -> None:
    clock = Clock()
    counter = iter(range(1, 1000))

    class Moving:
        def scrape(self) -> str:
            return _line("a", "200", "upstream", next(counter))

    boundary = settle(
        Moving(), timeout=30, poll_interval=2, quiet_seconds=20,
        monotonic=clock.monotonic, sleep=clock.sleep, now=clock.now,
    )  # fmt: skip
    assert not boundary.settled


def _fixture(*, no_restart: bool = True, end_text: str | None = None):
    clock = Clock()
    start_text = _line("a", "200", "upstream", 2)
    source = ScriptedSource(start_text, start_text, end_text or _line("a", "200", "upstream", 5))
    return capture_window(
        source,
        gateway_instance_id="gw-prod-1",
        environment="prod",
        apisix_version="3.19.0",
        route_coverage={"orders-route": True},
        disabled_labels=["service", "consumer", "consumer"],
        no_restart=no_restart,
        window_seconds=600,
        settle_timeout=10,
        poll_interval=1,
        quiet_seconds=0,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=clock.now,
    )


def test_a_captured_window_is_a_fixture_the_production_validator_accepts() -> None:
    fixture = _fixture()
    validated = validate_fixture(
        fixture.manifest,
        fixture.start,
        fixture.end,
        gateway_instance_id="gw-prod-1",
        environment="prod",
    )
    manifest = json.loads(fixture.manifest)
    assert manifest["schema"] == "aip-apisix-measurement/1"
    assert manifest["window_start"] < manifest["window_end"]
    assert manifest["disabled_labels"] == ["consumer", "service"]  # sorted, unique
    assert manifest["route_coverage"] == {"orders-route": True}
    assert manifest["start_settled"] and manifest["end_settled"] and manifest["no_restart"]
    assert manifest["start_scrape_count"] >= 2 and manifest["end_scrape_count"] >= 2
    assert validated.window_reasons == []
    [delta] = validated.series_deltas()
    assert (delta.status, delta.delta) == ("DELTA", 3)


def test_the_manifest_records_how_long_each_boundary_was_stable() -> None:
    """Review of #525: the first-in-window reading must rest on evidence the fixture itself carries."""
    clock = Clock()
    text = _line("a", "200", "upstream", 2)
    fixture = capture_window(
        ScriptedSource(text),
        gateway_instance_id="gw-prod-1",
        environment="prod",
        apisix_version="3.19.0",
        route_coverage={"orders-route": True},
        disabled_labels=[],
        no_restart=True,
        window_seconds=60,
        settle_timeout=120,
        poll_interval=2,
        quiet_seconds=20,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=clock.now,
    )
    manifest = json.loads(fixture.manifest)
    assert manifest["start_stable_seconds"] >= 20 and manifest["end_stable_seconds"] >= 20
    validated = validate_fixture(
        fixture.manifest,
        fixture.start,
        fixture.end,
        gateway_instance_id="gw-prod-1",
        environment="prod",
    )
    assert first_in_window_allowed(validated.manifest, "orders-route")


def test_a_bare_contract_capture_does_not_license_the_first_in_window_reading() -> None:
    fixture = _fixture()  # quiet_seconds=0: two identical scrapes, no stability evidence
    manifest = json.loads(fixture.manifest)
    assert manifest["start_stable_seconds"] < 20
    validated = validate_fixture(
        fixture.manifest,
        fixture.start,
        fixture.end,
        gateway_instance_id="gw-prod-1",
        environment="prod",
    )
    assert not first_in_window_allowed(validated.manifest, "orders-route")


def test_no_restart_is_not_asserted_unless_the_operator_says_so() -> None:
    fixture = _fixture(no_restart=False)
    manifest = json.loads(fixture.manifest)
    assert manifest["no_restart"] is False
    validated = validate_fixture(
        fixture.manifest,
        fixture.start,
        fixture.end,
        gateway_instance_id="gw-prod-1",
        environment="prod",
    )
    assert validated.window_reasons == ["GWM_WINDOW_RESTART"]


def test_two_captures_of_the_same_state_are_byte_identical() -> None:
    first, second = _fixture(), _fixture()
    assert (first.start, first.end, first.manifest) == (second.start, second.end, second.manifest)


class _Handler(BaseHTTPRequestHandler):
    body = b""
    status = 200

    def do_GET(self) -> None:
        self.send_response(self.status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/apisix/prometheus/metrics"
    srv.shutdown()
    thread.join()


def test_the_real_transport_scrapes_text_and_maps_failures_to_fixed_codes(server) -> None:
    url = server
    _Handler.status, _Handler.body = 200, _line("a", "200", "upstream", 7).encode()
    assert "apisix_http_status" in UrllibMetricsSource(metrics_url=url).scrape()
    _Handler.status = 500
    with pytest.raises(MetricsCaptureError) as raised:
        UrllibMetricsSource(metrics_url=url).scrape()
    assert raised.value.code == "GWM_CAPTURE_SCRAPE_FAILED"
    with pytest.raises(MetricsCaptureError) as raised:
        UrllibMetricsSource(metrics_url="http://127.0.0.1:1/x", timeout=1).scrape()
    assert raised.value.code == "GWM_CAPTURE_UNREACHABLE"
    with pytest.raises(MetricsCaptureError) as raised:
        UrllibMetricsSource(metrics_url="file:///etc/passwd")
    assert raised.value.code == "GWM_CAPTURE_URL_UNSUPPORTED"


def test_the_cli_writes_the_three_fixture_files(server, tmp_path: Path) -> None:
    url = server
    _Handler.status, _Handler.body = 200, _line("a", "200", "upstream", 7).encode()
    out = tmp_path / "fixture"
    code = main(
        [
            "--metrics-url", url, "--gateway-instance-id", "gw-prod-1", "--environment", "prod",
            "--apisix-version", "3.19.0", "--route-coverage", "orders-route=true", "--no-restart",
            "--window-seconds", "0.01", "--settle-timeout", "5", "--poll-interval", "0.01", "--quiet-seconds", "0",
            "--out", str(out),
        ]
    )  # fmt: skip
    assert code == 0
    assert sorted(p.name for p in out.iterdir()) == sorted([START_FILE, END_FILE, MANIFEST_FILE])
    validate_fixture(
        (out / MANIFEST_FILE).read_bytes(), (out / START_FILE).read_bytes(),
        (out / END_FILE).read_bytes(), gateway_instance_id="gw-prod-1", environment="prod",
    )  # fmt: skip


def test_the_cli_refuses_bad_arguments_with_a_fixed_code(capsys, tmp_path: Path) -> None:
    code = main(
        [
            "--metrics-url", "http://127.0.0.1:1/m", "--gateway-instance-id", "g", "--environment", "e",
            "--apisix-version", "3.19.0", "--route-coverage", "broken", "--window-seconds", "1",
            "--out", str(tmp_path / "o"),
        ]
    )  # fmt: skip
    assert code == 1
    assert capsys.readouterr().err.strip() == "refused: GWM_CAPTURE_ARGUMENT_INVALID"
    assert not (tmp_path / "o").exists()
