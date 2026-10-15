"""The one-time capture session of the I4 APISIX replay package (v0.7.0 I4.1c; I4 spec §5).

It starts the pinned APISIX 3.19.0, etcd 3.5.16 and traefik/whoami images (the images of the I0
spike; replay plan §1), applies revision R1 of the plan in `expected-replay.json`, sends exactly the
traffic of window W1, applies revision R2, restarts the gateway (so the counters start from nothing)
and sends the traffic of window W2. The configuration and the measurements are taken with the
repository's own capture tools (`app.gateway_capture`), which fence, redact and normalize in
acquisition code. Fake credentials only; nothing leaves the host.

    python docs/specifications/0.7.0/i4-replay/capture_session.py --out <empty directory>

writes `r1/` and `r2/` (each a `gateway/` configuration capture and a `metrics/` measurement fixture),
`EXPECTED.sha256` (the digest of the readings this session executed) and `SHA256SUMS`. The committed bytes are the frozen replay inputs: re-running this session does not
reproduce them (etcd revisions, instants, ports), and nothing replays by re-running it. It exists so
the procedure is inspectable. It refuses to run into a directory that already holds a capture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from testcontainers.core.container import DockerContainer

from app.gateway_capture.apisix import UrllibAdminApi, capture, serialize
from app.gateway_capture.apisix_metrics import UrllibMetricsSource, build_fixture, settle
from app.sources.apisix_contract import validate_capture_document
from app.sources.apisix_measurement_contract import END_FILE, MANIFEST_FILE, START_FILE

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / "expected-replay.json").read_text(encoding="utf-8"))
ROOT = HERE.parents[3]
CONFIG = ROOT / "tests/fixtures/apisix/config-etcd.yaml"
ADMIN_KEY = "spike-admin-key-fake"
GATEWAY, ENVIRONMENT = PLAN["gateway_instance_id"], PLAN["environment"]
APISIX_VERSION = "3.19.0"
UPSTREAM = "127.0.0.1:8081"


def key_of(consumer: str) -> str:
    return f"I4-REPLAY-FAKE-KEY-{consumer}"


def admin(method: str, base: str, path: str, body: dict[str, Any] | None = None) -> None:
    request = urllib.request.Request(
        f"{base}/apisix/admin/{path}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"X-API-KEY": ADMIN_KEY},
    )
    with urllib.request.urlopen(request, timeout=15):
        pass


def wait(url: str, *, headers: dict[str, str] | None = None, seconds: int = 120) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers or {}), timeout=3
            ):
                return
        except urllib.error.HTTPError:
            return  # it answered
        except Exception:  # noqa: BLE001 - polling until the endpoint answers
            time.sleep(1)
    raise TimeoutError(url)


def call(gateway: str, route: str, consumer: str) -> int:
    headers = {"apikey": key_of(consumer)} if consumer else {}
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"{gateway}/{route}", headers=headers), timeout=10
        ) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def route_body(route: str, spec: dict[str, Any]) -> dict[str, Any]:
    plugins: dict[str, Any] = {}
    if spec["auth"]:
        plugins["key-auth"] = {}
    if spec["allow"] is not None:
        plugins["consumer-restriction"] = {"type": "consumer_name", "whitelist": spec["allow"]}
    if spec["prometheus"]:
        plugins["prometheus"] = {}
    return {
        "uri": f"/{route}",
        "plugins": plugins,
        "upstream": {"type": "roundrobin", "nodes": {UPSTREAM: 1}},
    }


def apply_revision(base: str, revision: dict[str, Any], previous: dict[str, Any] | None) -> None:
    for route, spec in revision.items():
        admin("PUT", base, f"routes/{route}", route_body(route, spec))
    for route in (previous or {}).keys() - revision.keys():
        admin("DELETE", base, f"routes/{route}")


def send(gateway: str, traffic: list[dict[str, Any]]) -> None:
    for item in traffic:
        for _ in range(item["count"]):
            status = call(gateway, item["route"], item["consumer"])
            expected = item.get("code", 200)
            assert status == expected, f"{item}: answered {status}, expected {expected}"


def window(metrics_url: str, gateway: str, traffic: list[dict[str, Any]], revision: dict[str, Any]):
    source = UrllibMetricsSource(metrics_url=metrics_url)
    start = settle(source, timeout=180, poll_interval=2)
    send(gateway, traffic)
    end = settle(source, timeout=180, poll_interval=2)
    assert start.settled and end.settled, "a window boundary did not settle"
    assert start.stable_seconds >= 20, "the start boundary was not observed stable for 20 s"
    return build_fixture(
        start,
        end,
        gateway_instance_id=GATEWAY,
        environment=ENVIRONMENT,
        apisix_version=APISIX_VERSION,
        route_coverage={route: spec["prometheus"] for route, spec in revision.items()},
        disabled_labels=[],
        no_restart=True,
    )


def write_revision(out: Path, name: str, document: dict[str, Any], fixture: Any) -> None:
    (out / name / "gateway").mkdir(parents=True)
    (out / name / "metrics").mkdir(parents=True)
    assert validate_capture_document(document) is None
    (out / name / "gateway" / "apisix-capture.json").write_bytes(serialize(document))
    (out / name / "metrics" / START_FILE).write_bytes(fixture.start)
    (out / name / "metrics" / END_FILE).write_bytes(fixture.end)
    (out / name / "metrics" / MANIFEST_FILE).write_bytes(fixture.manifest)


def start_apisix(etcd: DockerContainer) -> DockerContainer:
    gateway = (
        DockerContainer(
            "apache/apisix:3.19.0-debian@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141"
        )
        .with_kwargs(network_mode=f"container:{etcd.get_wrapped_container().id}")
        .with_volume_mapping(str(CONFIG), "/usr/local/apisix/conf/config.yaml", "ro")
    )
    return gateway.start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    out: Path = args.out
    if (out / "r1").exists() or (out / "r2").exists():
        raise SystemExit("refusing to overwrite an existing capture")
    out.mkdir(parents=True, exist_ok=True)
    r1, r2 = PLAN["revisions"]["R1"], PLAN["revisions"]["R2"]

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
        etcd_url = f"http://{host}:{etcd.get_exposed_port(2379)}"
        admin_url = f"http://{host}:{etcd.get_exposed_port(9180)}"
        gateway_url = f"http://{host}:{etcd.get_exposed_port(9080)}"
        metrics_url = f"http://{host}:{etcd.get_exposed_port(9091)}/apisix/prometheus/metrics"
        wait(f"{etcd_url}/health", seconds=60)
        upstream = (
            DockerContainer(
                "traefik/whoami:v1.10.3@sha256:43a68d10b9dfcfc3ffbfe4dd42100dc9aeaf29b3a5636c856337a5940f1b4f1c"
            )
            .with_kwargs(network_mode=f"container:{etcd.get_wrapped_container().id}")
            .with_command("--port 8081")
        )
        with upstream:
            apisix = start_apisix(etcd)
            try:
                wait(f"{admin_url}/apisix/admin/consumers", headers={"X-API-KEY": ADMIN_KEY})
                for consumer in PLAN["consumers"]:
                    admin("PUT", admin_url, "consumers",
                          {"username": consumer, "plugins": {"key-auth": {"key": key_of(consumer)}}})  # fmt: skip
                apply_revision(admin_url, r1, None)
                time.sleep(3)
                api = UrllibAdminApi(admin_url=admin_url, admin_key=ADMIN_KEY, etcd_url=etcd_url)
                # No readiness probe goes through the gateway: a probe request would create a series
                # before the window and add rows the traffic plan does not contain. Propagation takes
                # seconds, the start boundary then waits 20 s more, and `send` asserts every status.
                time.sleep(10)
                fixture_1 = window(metrics_url, gateway_url, PLAN["traffic"]["W1"], r1)
                document_1 = capture(api, gateway_instance_id=GATEWAY, environment=ENVIRONMENT,
                                     apisix_version=APISIX_VERSION)  # fmt: skip
                write_revision(out, "r1", document_1, fixture_1)

                apply_revision(admin_url, r2, r1)
                time.sleep(3)
                document_2 = capture(api, gateway_instance_id=GATEWAY, environment=ENVIRONMENT,
                                     apisix_version=APISIX_VERSION)  # fmt: skip
                assert document_2["etcd_revision_after"] > document_1["etcd_revision_after"]
                apisix.stop()  # a rolling restart: the counters start from nothing
                apisix = start_apisix(etcd)
                wait(f"{admin_url}/apisix/admin/consumers", headers={"X-API-KEY": ADMIN_KEY})
                time.sleep(10)
                fixture_2 = window(metrics_url, gateway_url, PLAN["traffic"]["W2"], r2)
                write_revision(out, "r2", document_2, fixture_2)
            finally:
                apisix.stop()

    # The readings were written before this session; the digest proves they did not change after it.
    (out / "EXPECTED.sha256").write_text(
        hashlib.sha256((HERE / "expected-replay.json").read_bytes()).hexdigest() + "\n"
    )
    blob = b"".join(path.read_bytes() for path in sorted(out.rglob("*")) if path.is_file())
    secrets = [ADMIN_KEY, *(key_of(c) for c in PLAN["consumers"])]
    assert not any(secret.encode() in blob for secret in secrets), "a credential reached a capture"
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(out)}"
        for path in sorted(out.rglob("*"))
        if path.is_file() and path.name not in {"SHA256SUMS", "EXPECTED.sha256"}
    ]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
