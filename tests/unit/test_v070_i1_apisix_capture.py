"""v0.7.0 I1.3: the separate APISIX capture tool and the shared capture-envelope contract
(I1.1 contract §2, §7; I1 spec §3.2-3.3, §5). The Admin API is a stub or a local stdlib HTTP server;
no Docker. Secrets are *canaries*: known fake values that must appear in no output."""

import copy
import json
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.gateway_capture import apisix
from app.gateway_capture.apisix import AdminList, CaptureError, capture, serialize
from app.sources.apisix_contract import (
    ApisixCaptureEnvelope,
    unredacted_secret_paths,
    validate_capture_document,
)

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i1-vectors"
CONSUMER_KEY_CANARY = "CANARY-CONSUMER-KEY-7f3a"
CREDENTIAL_KEY_CANARY = "CANARY-CREDENTIAL-KEY-91bc"
JWT_SECRET_CANARY = "CANARY-JWT-SECRET-44de"
ADMIN_KEY_CANARY = "CANARY-ADMIN-KEY-0a1b"
CANARIES = (CONSUMER_KEY_CANARY, CREDENTIAL_KEY_CANARY, JWT_SECRET_CANARY, ADMIN_KEY_CANARY)


def _rec(kind: str, ident: str, value: dict) -> dict:
    return {
        "key": f"/apisix/{kind}/{ident}",
        "createdIndex": 15,
        "modifiedIndex": 16,
        "value": {"create_time": 1791789964, "update_time": 1791789964, **value},
    }


def _resources() -> dict[str, list[dict]]:
    return {
        "consumers": [
            _rec(
                "consumers",
                "bob",
                {"username": "bob", "plugins": {"basic-auth": {"password": JWT_SECRET_CANARY}}},
            ),
            _rec(
                "consumers",
                "alice",
                {"username": "alice", "plugins": {"key-auth": {"key": CONSUMER_KEY_CANARY}}},
            ),
        ],
        "routes": [
            _rec(
                "routes",
                "orders-route",
                {
                    "id": "orders-route",
                    "uri": "/orders",
                    "methods": ["POST", "GET"],
                    "labels": {"aip/service": "orders"},
                    "upstream": {"type": "roundrobin", "nodes": {"orders:80": 1}},
                    "plugins": {
                        "prometheus": {"prefer_name": False},
                        "key-auth": {"header": "apikey"},
                        "jwt-auth": {"secret": JWT_SECRET_CANARY},
                        "consumer-restriction": {
                            "type": "consumer_name",
                            "whitelist": ["bob", "alice"],
                            "unknown_field": CONSUMER_KEY_CANARY,
                        },
                    },
                },
            )
        ],
        "services": [
            _rec(
                "services",
                "s1",
                {"id": "s1", "plugins": {"key-auth": {"key": CONSUMER_KEY_CANARY}}},
            )
        ],
        "upstreams": [
            _rec(
                "upstreams",
                "u1",
                {"id": "u1", "nodes": [{"host": "10.0.0.2", "port": 80, "weight": 1}]},
            )
        ],
        "plugin_configs": [
            _rec("plugin_configs", "pc1", {"id": "pc1", "plugins": {"limit-count": {"count": 5}}})
        ],
        "consumer_groups": [],
        "global_rules": [_rec("global_rules", "g1", {"id": "g1", "plugins": {"prometheus": {}}})],
    }


def _credentials() -> dict[str, list[dict]]:
    return {
        "alice": [
            _rec(
                "consumers/alice/credentials",
                "cred-2",
                {"id": "cred-2", "plugins": {"key-auth": {"key": CREDENTIAL_KEY_CANARY}}},
            ),
            _rec(
                "consumers/alice/credentials",
                "cred-1",
                {"id": "cred-1", "plugins": {"key-auth": {"key": CREDENTIAL_KEY_CANARY}}},
            ),
        ],
        "bob": [],
    }


class StubApi:
    def __init__(self, *, revisions=(18, 18), version="3.19.0", shuffle: int | None = None):
        self.resources = _resources()
        self.credentials = _credentials()
        self.revisions = list(revisions)
        self.version = version
        self.total_override: dict[str, int] = {}
        if shuffle is not None:
            rng = random.Random(shuffle)
            for items in (*self.resources.values(), *self.credentials.values()):
                rng.shuffle(items)

    def etcd_revision(self) -> int:
        return self.revisions.pop(0)

    def list_resources(self, kind: str) -> AdminList:
        items = self.resources[kind]
        return AdminList(items=items, total=self.total_override.get(kind, len(items)))

    def list_credentials(self, username: str) -> AdminList:
        items = self.credentials[username]
        return AdminList(items=items, total=self.total_override.get(f"cred:{username}", len(items)))

    def server_version(self) -> str | None:
        return self.version


def _capture(api: StubApi) -> dict:
    return capture(
        api, gateway_instance_id="gw-prod-1", environment="prod", apisix_version="3.19.0"
    )


def test_capture_is_redacted_valid_and_normalized() -> None:
    document = _capture(StubApi())
    assert validate_capture_document(document) is None
    ApisixCaptureEnvelope.model_validate(document)
    raw = serialize(document).decode()
    for canary in CANARIES:
        assert canary not in raw
    assert unredacted_secret_paths(document) == []
    assert [c["username"] for c in document["consumers"]] == ["alice", "bob"]
    assert document["consumers"][0]["credential_ids"] == ["cred-1", "cred-2"]
    [route] = document["routes"]
    assert route["methods"] == ["GET", "POST"]
    assert route["upstream_nodes"] == ["orders:80"]
    assert route["labels"] == {"aip/service": "orders"}
    assert route["plugins"]["key-auth"] == {} and route["plugins"]["jwt-auth"] == {}
    assert route["plugins"]["consumer-restriction"] == {
        "type": "consumer_name",
        "whitelist": ["alice", "bob"],
    }  # unknown restriction fields are dropped, not carried
    assert document["upstreams"][0]["nodes"] == ["10.0.0.2:80"]
    assert document["etcd_revision_before"] == document["etcd_revision_after"] == 18
    assert "create_time" not in raw and "update_time" not in raw and "modifiedIndex" not in raw


def test_output_is_byte_identical_regardless_of_source_ordering() -> None:
    first = serialize(_capture(StubApi()))
    for seed in (1, 2, 3):
        assert serialize(_capture(StubApi(shuffle=seed))) == first


def test_a_changed_etcd_revision_refuses_the_capture() -> None:
    with pytest.raises(CaptureError) as excinfo:
        _capture(StubApi(revisions=(18, 19)))
    assert (
        excinfo.value.code == "GW_CAPTURE_INCONSISTENT" and str(excinfo.value) == excinfo.value.code
    )


@pytest.mark.parametrize("override", ["routes", "cred:alice", "consumers"])
def test_an_incomplete_list_refuses_the_capture(override: str) -> None:
    api = StubApi()
    api.total_override[override] = 99
    with pytest.raises(CaptureError) as excinfo:
        _capture(api)
    assert excinfo.value.code == "GW_CAPTURE_INCOMPLETE"


def test_a_missing_total_is_treated_as_incomplete() -> None:
    api = StubApi()
    api.resources["services"] = api.resources["services"]
    original = api.list_resources
    api.list_resources = lambda kind: (  # type: ignore[method-assign]
        AdminList(items=original(kind).items, total=None) if kind == "services" else original(kind)
    )
    with pytest.raises(CaptureError) as excinfo:
        _capture(api)
    assert excinfo.value.code == "GW_CAPTURE_INCOMPLETE"


def test_a_version_mismatch_refuses_the_capture() -> None:
    with pytest.raises(CaptureError) as excinfo:
        _capture(StubApi(version="3.20.0"))
    assert excinfo.value.code == "GW_CAPTURE_VERSION_MISMATCH"


# ------------------------------------------------------------------------------------------
# The real client and CLI against a local stdlib server (no Docker)
# ------------------------------------------------------------------------------------------


class _Server:
    """A minimal Admin API + etcd JSON gateway. `mode` selects a failure."""

    def __init__(self, *, mode: str = "ok"):
        outer = self
        self.mode = mode
        self.resources = _resources()
        self.credentials = _credentials()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def _send(self, code: int, body: object) -> None:
                raw = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Server", "APISIX/3.19.0")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):  # etcd /v3/kv/range
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self._send(200, {"header": {"revision": "18"}})

            def do_GET(self):
                if outer.mode == "no-admin":
                    return self._send(404, {"error_msg": "not found"})
                if self.headers.get("X-API-KEY") != ADMIN_KEY_CANARY:
                    return self._send(
                        401, {"error_msg": f"bad key {self.headers.get('X-API-KEY')}"}
                    )
                path = self.path.removeprefix("/apisix/admin/")
                if path.startswith("consumers/") and path.endswith("/credentials"):
                    items = outer.credentials[path.split("/")[1]]
                    if not items:  # APISIX 3.19: no credentials is a 404, not an empty list
                        return self._send(404, {"message": "Key not found"})
                else:
                    items = outer.resources[path]
                self._send(200, {"total": len(items), "list": items})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    started = []

    def make(**kwargs) -> _Server:
        started.append(_Server(**kwargs))
        return started[-1]

    yield make
    for s in started:
        s.close()


def _cli(server: _Server, out: Path, capsys, monkeypatch, *, key: str | None = ADMIN_KEY_CANARY):
    if key is None:
        monkeypatch.delenv(apisix.ADMIN_KEY_ENV, raising=False)
    else:
        monkeypatch.setenv(apisix.ADMIN_KEY_ENV, key)
    code = apisix.main(
        [
            "--admin-url", server.url, "--etcd-url", server.url,
            "--gateway-instance-id", "gw-prod-1", "--environment", "prod",
            "--apisix-version", "3.19.0", "--out", str(out),
        ]
    )  # fmt: skip
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_cli_writes_the_same_bytes_as_the_library_and_never_prints_a_secret(
    server, tmp_path, capsys, monkeypatch
) -> None:
    out = tmp_path / "apisix-capture.json"
    code, console = _cli(server(), out, capsys, monkeypatch)
    assert code == 0
    for canary in CANARIES:
        assert canary not in console and canary not in out.read_text()
    assert out.read_bytes() == serialize(_capture(StubApi()))


def test_cli_refuses_without_an_admin_key_and_wrong_keys_never_echo(
    server, tmp_path, capsys, monkeypatch
) -> None:
    out = tmp_path / "x.json"
    code, console = _cli(server(), out, capsys, monkeypatch, key=None)
    assert code == 2 and not out.exists()
    code, console = _cli(server(), out, capsys, monkeypatch, key="CANARY-WRONG-KEY-5e5e")
    assert code == 1 and not out.exists()
    assert "CANARY-WRONG-KEY-5e5e" not in console
    assert console.strip() == "refused: GW_CAPTURE_ADMIN_AUTH_FAILED"


def test_cli_refuses_when_there_is_no_admin_api_surface(
    server, tmp_path, capsys, monkeypatch
) -> None:
    out = tmp_path / "x.json"
    code, console = _cli(server(mode="no-admin"), out, capsys, monkeypatch)
    assert code == 1 and not out.exists()
    assert console.strip() == "refused: GW_CAPTURE_SURFACE_UNAVAILABLE"


def test_an_unreachable_gateway_is_a_fixed_code(tmp_path, capsys, monkeypatch) -> None:
    class Dead:
        url = "http://127.0.0.1:9"

    code, console = _cli(Dead(), tmp_path / "x.json", capsys, monkeypatch)  # type: ignore[arg-type]
    assert code == 1 and console.strip() == "refused: GW_CAPTURE_UNREACHABLE"


# ------------------------------------------------------------------------------------------
# The shared envelope against the independent I1.1 vectors
# ------------------------------------------------------------------------------------------


def _load(name: str) -> dict:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def _full_document(patch: dict | None = None, *, case_capture: dict | None = None) -> dict:
    base = _load("configured-access.json")["base_capture"]
    document: dict = copy.deepcopy(base)
    document.update(
        consumers=[], routes=[], services=[], upstreams=[], plugin_configs=[],
        consumer_groups=[], global_rules=[],
    )  # fmt: skip
    for name, value in (case_capture or {}).items():
        document[name] = copy.deepcopy(value)
    for name, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(document.get(name), dict):
            document[name].update(value)
        else:
            document[name] = value
    return document


def test_every_configured_access_vector_is_an_acceptable_fixture() -> None:
    for case in _load("configured-access.json")["cases"]:
        document = _full_document(case_capture=case["capture"])
        assert validate_capture_document(document) is None, case["id"]


@pytest.mark.parametrize("case", _load("capture-rejections.json")["cases"], ids=lambda c: c["id"])
def test_rejection_vectors(case: dict) -> None:
    expected = case["expected"]
    if "capture_patch" not in case:
        assert case["spec_case"] == "duplicate-instance"  # registration side (I1.4)
        return
    if case["spec_case"] == "instance-binding":
        # The envelope is well-formed; mismatching the registration is checked against the
        # registration in I1.4, so the shared validator accepts it.
        assert validate_capture_document(_full_document(case["capture_patch"])) is None
        return
    problem = validate_capture_document(_full_document(case["capture_patch"]))
    assert problem is not None, case["id"]
    assert problem.code == expected["code"] and problem.result == expected["result"]
    for forbidden in expected.get("diagnostic_must_not_contain", []):
        assert forbidden not in repr(problem)


def test_secret_scan_reports_paths_and_never_values() -> None:
    document = _full_document(
        {"consumers": [{"username": "alice", "credential_ids": [], "key": CONSUMER_KEY_CANARY}]}
    )
    document["routes"] = [
        {"id": "r1", "plugins": {"jwt-auth": {"secret": JWT_SECRET_CANARY}, "key-auth": {}}}
    ]
    paths = unredacted_secret_paths(document)
    assert paths == ["/consumers/0/key", "/routes/0/plugins/jwt-auth"]
    assert not any(c in " ".join(paths) for c in CANARIES)
    # free-form labels are operator metadata, not credential material
    labelled = _full_document()
    labelled["routes"] = [{"id": "r1", "labels": {"key": "x"}, "plugins": {}}]
    assert unredacted_secret_paths(labelled) == []
