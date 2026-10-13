"""v0.7.0 I2.2a: the measurement capture tool against real, digest-pinned APISIX 3.19.0 and etcd 3.5.16
containers (the images used by the I0 spike): the real Prometheus plugin endpoint, real counters that
lag behind traffic, and a real upstream (etcd's own /health, reachable inside the shared network
namespace). Fake credentials only."""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer

from app.gateway_capture.apisix_metrics import UrllibMetricsSource, build_fixture, settle
from app.sources.apisix_measurement_contract import validate_fixture

CONFIG = Path(__file__).resolve().parent.parent / "fixtures" / "apisix" / "config-etcd.yaml"
ADMIN_KEY = "spike-admin-key-fake"
ALICE_KEY = "CANARY-REAL-MEASUREMENT-ALICE-KEY-71c2"
GATEWAY, ENVIRONMENT = "gw-real-1", "test"


def _put(admin_url: str, path: str, body: dict) -> None:
    request = urllib.request.Request(
        f"{admin_url}/apisix/admin/{path}",
        data=json.dumps(body).encode(),
        method="PUT",
        headers={"X-API-KEY": ADMIN_KEY},
    )
    with urllib.request.urlopen(request, timeout=15):
        pass


def _wait(url: str, *, headers: dict[str, str] | None = None, seconds: int = 120) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(request, timeout=3):
                return
        except urllib.error.HTTPError:
            return  # it answered
        except Exception:  # noqa: BLE001 - polling until the endpoint answers
            time.sleep(1)
    raise TimeoutError(url)


@pytest.fixture(scope="module")
def stack():
    etcd = (
        DockerContainer(
            "quay.io/coreos/etcd:v3.5.16@sha256:d967d98a12dc220a1a290794711dba7eba04b8ce465e12b02383d1bfbb33e159"
        )
        .with_env("ETCD_ADVERTISE_CLIENT_URLS", "http://127.0.0.1:2379")
        .with_env("ETCD_LISTEN_CLIENT_URLS", "http://0.0.0.0:2379")
        .with_command("/usr/local/bin/etcd")
        .with_exposed_ports(2379, 9180, 9080, 9091)
    )
    with etcd:
        host = etcd.get_container_host_ip()
        _wait(f"http://{host}:{etcd.get_exposed_port(2379)}/health", seconds=60)
        apisix = (
            DockerContainer(
                "apache/apisix:3.19.0-debian@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141"
            )
            .with_kwargs(network_mode=f"container:{etcd.get_wrapped_container().id}")
            .with_volume_mapping(str(CONFIG), "/usr/local/apisix/conf/config.yaml", "ro")
        )
        with apisix:
            admin = f"http://{host}:{etcd.get_exposed_port(9180)}"
            _wait(f"{admin}/apisix/admin/consumers", headers={"X-API-KEY": ADMIN_KEY})
            _put(
                admin,
                "consumers",
                {"username": "alice", "plugins": {"key-auth": {"key": ALICE_KEY}}},
            )
            _put(
                admin,
                "routes/health-route",
                {
                    "uri": "/health",
                    "plugins": {"key-auth": {}, "prometheus": {}},
                    "upstream": {"type": "roundrobin", "nodes": {"127.0.0.1:2379": 1}},
                },
            )
            gateway = f"http://{host}:{etcd.get_exposed_port(9080)}"
            deadline = time.monotonic() + 60  # the route reaches the data plane asynchronously
            while time.monotonic() < deadline:
                try:
                    _get(gateway, ALICE_KEY)
                    break
                except Exception:  # noqa: BLE001 - polling until the route is live
                    time.sleep(1)
            yield gateway, f"http://{host}:{etcd.get_exposed_port(9091)}/apisix/prometheus/metrics"


def _get(gateway: str, key: str | None) -> int:
    request = urllib.request.Request(f"{gateway}/health", headers={"apikey": key} if key else {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def _boundary(metrics_url: str):
    # defaults: quiet period 20 s > the ~14 s series lag measured against this stack in I2.2
    return settle(UrllibMetricsSource(metrics_url=metrics_url), timeout=120, poll_interval=2)


@pytest.fixture(scope="module")
def window(stack):
    gateway, metrics_url = stack
    start = _boundary(metrics_url)
    assert [_get(gateway, ALICE_KEY) for _ in range(3)] == [200, 200, 200]
    assert _get(gateway, None) == 401
    end = _boundary(metrics_url)
    fixture = build_fixture(
        start,
        end,
        gateway_instance_id=GATEWAY,
        environment=ENVIRONMENT,
        apisix_version="3.19.0",
        route_coverage={"health-route": True},
        disabled_labels=[],
        no_restart=True,
    )
    return start, end, fixture


def test_real_counters_settle_and_the_window_yields_attributed_and_unattributed_deltas(
    window,
) -> None:
    start, end, fixture = window
    assert start.settled and end.settled and start.scrape_count >= 2 and end.scrape_count >= 2
    validated = validate_fixture(
        fixture.manifest,
        fixture.start,
        fixture.end,
        gateway_instance_id=GATEWAY,
        environment=ENVIRONMENT,
    )
    assert validated.window_reasons == []
    assert validated.manifest.start_stable_seconds >= 20  # the evidence the 0-start reading needs
    deltas = {
        (
            d.series.labels["consumer"],
            d.series.labels["code"],
            d.series.labels["response_source"],
        ): d
        for d in validated.series_deltas()
    }
    upstream = deltas[("alice", "200", "upstream")]
    assert (upstream.status, upstream.delta) == (
        "DELTA",
        3,
    )  # I0: usage is response_source=upstream
    # The 401 series was first created inside the window, so it exists at the end boundary only. The
    # window is valid and the Route covered, so the amended contract §3 reads its start as 0 (review
    # of #524): a consumer's first-ever traffic in a window is measurable.
    rejected = deltas[("", "401", "apisix")]
    assert (rejected.status, rejected.delta) == ("DELTA_FIRST_IN_WINDOW", 1)
    assert all(b"node=" not in part for part in (fixture.start, fixture.end))


def test_the_fixture_never_carries_a_credential(window) -> None:
    _, _, fixture = window
    blob = fixture.start + fixture.end + fixture.manifest
    for canary in (ALICE_KEY, ADMIN_KEY):
        assert canary.encode() not in blob
