"""v0.7.0 I1.3: the capture tool against real, digest-pinned APISIX 3.19.0 and etcd 3.5.16
containers (the images used by the I0 spike; the upstream host is never contacted, only configured) - the real Admin API, the real etcd JSON gateway, and
real plaintext-on-read credentials. Fake credentials only."""

import json
import time
import urllib.request
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer

from app.gateway_capture.apisix import CaptureError, UrllibAdminApi, capture, serialize
from app.sources.apisix_contract import validate_capture_document

CONFIG = Path(__file__).resolve().parent.parent / "fixtures" / "apisix" / "config-etcd.yaml"
ADMIN_KEY = "spike-admin-key-fake"
CONSUMER_KEY_CANARY = "CANARY-REAL-CONSUMER-KEY-3c9e"
CREDENTIAL_KEY_CANARY = "CANARY-REAL-CREDENTIAL-KEY-8d2f"


def _put(admin_url: str, path: str, body: dict) -> None:
    request = urllib.request.Request(
        f"{admin_url}/apisix/admin/{path}",
        data=json.dumps(body).encode(),
        method="PUT",
        headers={"X-API-KEY": ADMIN_KEY},
    )
    with urllib.request.urlopen(request, timeout=15):
        pass


def _get_raw(admin_url: str, path: str) -> str:
    request = urllib.request.Request(
        f"{admin_url}/apisix/admin/{path}", headers={"X-API-KEY": ADMIN_KEY}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode()


@pytest.fixture(scope="module")
def stack():
    """etcd and APISIX in one network namespace (APISIX joins etcd's), so the config reaches etcd at
    127.0.0.1 and only etcd needs published ports. The images are literal and digest-pinned: the
    repository's image-pin guard reads them from these calls."""
    etcd = (
        DockerContainer(
            "quay.io/coreos/etcd:v3.5.16@sha256:d967d98a12dc220a1a290794711dba7eba04b8ce465e12b02383d1bfbb33e159"
        )
        .with_env("ETCD_ADVERTISE_CLIENT_URLS", "http://127.0.0.1:2379")
        .with_env("ETCD_LISTEN_CLIENT_URLS", "http://0.0.0.0:2379")
        .with_command("/usr/local/bin/etcd")
        .with_exposed_ports(2379, 9180)
    )
    with etcd:
        host = etcd.get_container_host_ip()
        etcd_url = f"http://{host}:{etcd.get_exposed_port(2379)}"
        _wait_for_etcd(etcd_url)
        apisix = (
            DockerContainer(
                "apache/apisix:3.19.0-debian@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141"
            )
            .with_kwargs(network_mode=f"container:{etcd.get_wrapped_container().id}")
            .with_volume_mapping(str(CONFIG), "/usr/local/apisix/conf/config.yaml", "ro")
        )
        with apisix:
            admin_url = f"http://{host}:{etcd.get_exposed_port(9180)}"
            _wait_for_admin(admin_url)
            _seed(admin_url)
            yield admin_url, etcd_url


def _wait_for_etcd(etcd_url: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{etcd_url}/health", timeout=3):
                return
        except Exception:  # noqa: BLE001 - polling until etcd answers
            time.sleep(1)
    raise TimeoutError("etcd did not become ready")


def _wait_for_admin(admin_url: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            _get_raw(admin_url, "consumers")
            return
        except Exception:  # noqa: BLE001 - polling until the Admin API answers
            time.sleep(1)
    raise TimeoutError("APISIX Admin API did not become ready")


def _seed(admin_url: str) -> None:
    _put(
        admin_url,
        "consumers",
        {"username": "alice", "plugins": {"key-auth": {"key": CONSUMER_KEY_CANARY}}},
    )
    _put(
        admin_url,
        "consumers",
        {"username": "bob", "plugins": {"key-auth": {"key": "CANARY-REAL-BOB-KEY-1a1a"}}},
    )
    _put(
        admin_url,
        "consumers/alice/credentials/cred-1",
        {"plugins": {"key-auth": {"key": CREDENTIAL_KEY_CANARY}}},
    )
    _put(
        admin_url,
        "routes/orders-route",
        {
            "uri": "/orders",
            "labels": {"aip/service": "orders"},
            "plugins": {
                "key-auth": {},
                "consumer-restriction": {"whitelist": ["alice", "bob"]},
                "prometheus": {},
            },
            "upstream": {"type": "roundrobin", "nodes": {"orders.internal:80": 1}},
        },
    )


def _api(stack) -> UrllibAdminApi:
    admin_url, etcd_url = stack
    return UrllibAdminApi(admin_url=admin_url, admin_key=ADMIN_KEY, etcd_url=etcd_url)


def test_the_real_admin_api_returns_credentials_in_plaintext_and_the_capture_redacts_them(
    stack,
) -> None:
    admin_url, _ = stack
    # I0 finding F15: the Admin API itself returns key values on read...
    assert CONSUMER_KEY_CANARY in _get_raw(admin_url, "consumers")
    assert CREDENTIAL_KEY_CANARY in _get_raw(admin_url, "consumers/alice/credentials")

    document = capture(
        _api(stack), gateway_instance_id="gw-real-1", environment="test", apisix_version="3.19.0"
    )
    assert validate_capture_document(document) is None
    raw = serialize(document).decode()
    # ...so the redaction in acquisition is what keeps them out of the fixture.
    for canary in (
        CONSUMER_KEY_CANARY,
        CREDENTIAL_KEY_CANARY,
        "CANARY-REAL-BOB-KEY-1a1a",
        ADMIN_KEY,
    ):
        assert canary not in raw
    assert [c["username"] for c in document["consumers"]] == ["alice", "bob"]
    assert document["consumers"][0]["credential_ids"] == ["cred-1"]
    [route] = document["routes"]
    assert route["id"] == "orders-route"
    assert route["plugins"]["consumer-restriction"] == {"whitelist": ["alice", "bob"]}
    assert route["plugins"]["key-auth"] == {}
    assert route["upstream_nodes"] == ["orders.internal:80"]
    assert document["etcd_revision_before"] == document["etcd_revision_after"] > 0
    # I0 acquisition plan §2.3: per-object etcd revisions are retained as provenance and never
    # exceed the capture's own revision.
    objects = [*document["consumers"], *document["routes"]]
    for obj in objects:
        assert isinstance(obj["created_index"], int) and isinstance(obj["modified_index"], int)
        assert 0 < obj["created_index"] <= obj["modified_index"] <= document["etcd_revision_after"]


def test_two_captures_of_unchanged_state_are_byte_identical(stack) -> None:
    def once() -> bytes:
        return serialize(
            capture(
                _api(stack),
                gateway_instance_id="gw-real-1",
                environment="test",
                apisix_version="3.19.0",
            )
        )

    assert once() == once()


def test_a_write_during_the_read_changes_the_real_etcd_revision_and_refuses_the_capture(
    stack,
) -> None:
    admin_url, _ = stack
    real = _api(stack)

    class WritingApi:
        """Delegates to the real API but performs a real write after the first list."""

        def __init__(self) -> None:
            self.wrote = False

        def etcd_revision(self) -> int:
            return real.etcd_revision()

        def list_resources(self, kind: str):
            listing = real.list_resources(kind)
            if not self.wrote:
                self.wrote = True
                _put(
                    admin_url,
                    "consumers",
                    {"username": "carol", "plugins": {"key-auth": {"key": "CANARY-CAROL-1b1b"}}},
                )
            return listing

        def list_credentials(self, username: str):
            return real.list_credentials(username)

        def server_version(self):
            return real.server_version()

    with pytest.raises(CaptureError) as excinfo:
        capture(
            WritingApi(),
            gateway_instance_id="gw-real-1",
            environment="test",
            apisix_version="3.19.0",
        )
    assert excinfo.value.code == "GW_CAPTURE_INCONSISTENT"
    # the refusal leaves the earlier state unchanged for the next (consistent) capture
    document = capture(
        _api(stack), gateway_instance_id="gw-real-1", environment="test", apisix_version="3.19.0"
    )
    assert "carol" in [c["username"] for c in document["consumers"]]


def test_the_real_client_refuses_a_wrong_admin_key_without_echoing_it(stack) -> None:
    admin_url, etcd_url = stack
    api = UrllibAdminApi(
        admin_url=admin_url, admin_key="CANARY-WRONG-ADMIN-KEY-77", etcd_url=etcd_url
    )
    with pytest.raises(CaptureError) as excinfo:
        capture(api, gateway_instance_id="gw-real-1", environment="test", apisix_version="3.19.0")
    assert excinfo.value.code == "GW_CAPTURE_ADMIN_AUTH_FAILED"
    assert "CANARY-WRONG-ADMIN-KEY-77" not in str(excinfo.value)


def test_updating_one_object_changes_only_its_own_modified_index(stack) -> None:
    admin_url, _ = stack

    def indices() -> dict[str, tuple[int, int]]:
        document = capture(
            _api(stack),
            gateway_instance_id="gw-real-1",
            environment="test",
            apisix_version="3.19.0",
        )
        return {
            c["username"]: (c["created_index"], c["modified_index"]) for c in document["consumers"]
        }

    before = indices()
    _put(
        admin_url,
        "consumers",
        {"username": "bob", "plugins": {"key-auth": {"key": "CANARY-REAL-BOB-KEY-2c2c"}}},
    )
    after = indices()
    assert after["alice"] == before["alice"]
    assert after["bob"][0] == before["bob"][0]  # createdIndex is stable
    assert after["bob"][1] > before["bob"][1]  # modifiedIndex advanced
