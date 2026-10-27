"""v0.8 I3a: static guards on the authored I3 environment, the scripts, the committed reference and
the functional-test driver (I3 spec §3, §6, §8; memory rule "compose run identity").

Nothing here runs Docker, Kafka or a Sokol111 service.
"""

import base64
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "docs/specifications/0.8.0/i3-evidence"
ENV = PKG / "environment"
HARNESS = REPO / "harness/v08/i3"
I2_FIXTURE = REPO / "docs/specifications/0.8.0/i2-vectors/two-broker"
SCRIPTS = sorted(HARNESS.rglob("*.sh"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load("i3_checker_env", HARNESS / "checker.py")
functional = _load("i3_functional", HARNESS / "functional_test.py")
FLOWS = {flow: checker.read_properties(ENV / f"{flow}.properties") for flow in checker.WORKER_STATE}


# --- Compose -----------------------------------------------------------------------------------------


def test_compose_uses_only_required_interpolation_digest_pins_and_the_external_network() -> None:
    text = (ENV / "docker-compose.i3.yml").read_text()
    for match in re.finditer(r"\$\{[^}]*\}", text):
        assert re.fullmatch(r"\$\{[A-Z0-9_]+:\?[^}]*\}", match[0]), match[0]
    compose = yaml.safe_load(text)
    assert compose["name"] == "aip-v08-i3"
    assert set(compose["services"]) == {"kafka", "mm2-flow-a", "mm2-flow-b", "mm2-probe"}
    for name, service in compose["services"].items():
        assert re.fullmatch(r"apache/kafka:4\.1\.2@sha256:[0-9a-f]{64}", service["image"]), name
        assert service["networks"] == ["shared-network"], name
        if name != "kafka":
            assert service["profiles"] == [name]
            assert service["volumes"] == [f"./{name}.properties:/etc/mm2/mm2.properties:ro"]
    assert compose["networks"] == {"shared-network": {"name": "shared-network", "external": True}}
    assert not (ENV / ".env").exists()
    kafka_env = compose["services"]["kafka"]["environment"]
    assert (
        kafka_env["KAFKA_ADVERTISED_LISTENERS"] == "PLAINTEXT://kafka:29092,HOST://localhost:19092"
    )
    assert kafka_env["KAFKA_AUTO_CREATE_TOPICS_ENABLE"] == "false"


def test_compose_is_called_only_through_the_pinned_frozen_helper() -> None:
    lib = (HARNESS / "lib.sh").read_text()
    assert (
        "frozen_compose() {\n"
        '  docker compose -p aip-v08-i3 --project-directory "$ENV_DIR" \\\n'
        '    -f "$ENV_DIR/docker-compose.i3.yml" --env-file /dev/null "$@"\n'
        "}\n"
    ) in lib
    assert lib.count("docker compose") == 1
    for script in SCRIPTS:
        if script.name != "lib.sh":
            assert "docker compose" not in script.read_text(), script
            assert not re.search(r"\bdocker-compose\s", script.read_text()), script  # v1 binary


def test_every_script_sources_the_library_and_parses() -> None:
    assert len(SCRIPTS) == 1 + 4 + 9 + 1  # lib, preflight, steps, capture
    for script in SCRIPTS:
        if script.name != "lib.sh":
            assert 'source "$(dirname "$0")/' in script.read_text(), script
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_each_step_checks_its_precondition_before_acting() -> None:
    for number in range(1, 10):
        lines = (HARNESS / f"steps/{number:02d}.sh").read_text().splitlines()
        body = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
        first_require = body.index("require ")
        acting = [body.find(word) for word in ("record ", "check ", "frozen_compose ", "scale ")]
        assert first_require < min(i for i in acting if i >= 0), number


# --- MirrorMaker 2 workers (I3 §3; plan corrections 1 and 2) -------------------------------------------


def test_the_flows_pass_p1a_and_p3() -> None:
    paths = [ENV / f"{flow}.properties" for flow in checker.WORKER_STATE]
    assert checker.check_p1a(paths)["result"] == "PASSED"
    assert (
        checker.check_p3(ENV / "mm2-flow-a.properties", ENV / "mm2-flow-b.properties")["result"]
        == "PASSED"
    )


@pytest.mark.parametrize("flow", sorted(checker.WORKER_STATE))
def test_replication_factor_one_everywhere_and_short_explicit_intervals(flow: str) -> None:
    props = FLOWS[flow]
    assert props["replication.factor"] == "1"  # mirrored data topics (the 4.1 default is 2)
    for key in checker.RF_KEYS:
        assert props[key] == "1", key
    for key in checker.INTERVAL_KEYS:
        assert props[key] == "10", key
    assert props["offset.lag.max"] == "1"
    # The worker commits the replicated source offsets at this cadence (default 60 s > the deadline).
    # Only the target-prefixed key reaches the dedicated MM2 worker; a bare key is ignored.
    target = checker.WORKER_STATE[flow][1]
    assert int(props[f"{target}.offset.flush.interval.ms"]) < 1000 * 40
    assert "offset.flush.interval.ms" not in props


def test_the_wait_deadline_derives_from_the_committed_intervals() -> None:
    lib = (HARNESS / "lib.sh").read_text()
    interval = int(re.search(r"^MM2_INTERVAL_SECONDS=(\d+)$", lib, re.MULTILINE)[1])
    for props in FLOWS.values():
        assert int(props["sync.group.offsets.interval.seconds"]) == interval
        assert int(props["refresh.groups.interval.seconds"]) == interval
    assert (
        "MM2_DEADLINE_SECONDS=$((3 * MM2_INTERVAL_SECONDS + MM2_INTERVAL_SECONDS))" in lib
    )  # 3 x sync.group.offsets + refresh.groups


def test_the_worker_state_is_pairwise_distinct() -> None:
    for key in ("config.storage.topic", "offset.storage.topic", "status.storage.topic"):
        values = [props[key] for props in FLOWS.values()]
        assert len(set(values)) == len(values), key
    group_ids = [
        props[f"{checker.WORKER_STATE[flow][1]}.group.id"] for flow, props in FLOWS.items()
    ]
    assert sorted(group_ids) == sorted(checker.WORKER_STATE)


def test_the_flow_allow_lists_are_disjoint_and_the_probe_is_alone() -> None:
    def topics(flow: str) -> set[str]:
        source, target = checker.WORKER_STATE[flow]
        return set(checker.topic_list(FLOWS[flow][f"{source}->{target}.topics"]))

    assert topics("mm2-flow-a") == {"tenant.tenant.events"}
    assert topics("mm2-flow-b") == {
        "catalog.attribute.events",
        "catalog.category.events",
        "catalog.product.events",
    }
    assert topics("mm2-probe") == {"aip-probe.events"}
    assert FLOWS["mm2-probe"]["rpprobe->kprobe.groups"] == "aip-probe-group"
    assert FLOWS["mm2-flow-b"]["kafka->redpanda.groups"] == "^$"


# --- P5 ownership and the Tilt guard ------------------------------------------------------------------


def _bash_array(text: str, name: str) -> list[str]:
    line = re.search(rf"^{name}=\((.*)\)$", text, re.MULTILINE)[1]
    return [item.strip('"').replace("$TOPIC", "aip-probe.events") for item in line.split()]


def test_p5_proves_absence_of_every_name_it_may_delete_before_arming_the_teardown() -> None:
    text = (HARNESS / "preflight/p5.sh").read_text()
    topics = checker.internal_topics("mm2-probe")
    assert sorted(_bash_array(text, "KAFKA_TOPICS")) == sorted(
        ["aip-probe.events", *topics["target"]]
    )
    assert _bash_array(text, "REDPANDA_TOPICS") == ["aip-probe.events", *topics["source"]]
    trap = text.index("trap teardown EXIT")
    before, teardown = text[:trap], text[text.index("teardown() {") : trap]
    for guard in (
        'for topic in "${REDPANDA_TOPICS[@]}"; do\n  require "Redpanda has no topic $topic yet" -- absent redpanda-topic "$topic"',
        'for topic in "${KAFKA_TOPICS[@]}"; do\n  require "Kafka has no topic $topic yet" -- absent kafka-topic "$topic"',
        'absent redpanda-group "$GROUP"\n',
        'absent kafka-group "$GROUP"\n',
    ):
        assert guard in before[: before.index("teardown() {")], guard
    # The teardown deletes only the guarded names: no literal topic or group name of its own.
    deletes = "\n".join(
        line
        for line in teardown.splitlines()
        if "probe-stop" not in line and "container" not in line
    )
    assert "aip-probe" not in deletes and "mm2-" not in deletes
    assert text.index("record P5 create-topic") > trap
    # The teardown removes the probe container, so none may exist before, not even a stopped one.
    assert (
        'require "no probe container exists, running or stopped" -- absent container mm2-probe'
        in before
    )


# A fake `docker` on PATH answers the listings P5 makes (empty unless told otherwise), logs every
# call, and fails the one named by FAKE_FAIL. "after-create": `rpk topic create` fails, and every
# listing after it fails too (the broker went away). "create-then-listed": `rpk topic create` fails,
# but Redpanda then lists the probe topic (it was created after all).
FAKE_DOCKER = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
a="$*"
created="$FAKE_LOG.created"
fail() { [[ "${FAKE_FAIL:-}" == "$1" ]] && exit 1; return 0; }
listing() {
  fail "$1"
  [[ -e "$created" && "${FAKE_FAIL:-}" == after-create ]] && exit 1
  return 0
}
case "$a" in
  *"rpk topic create"*) touch "$created"; exit 1 ;;
  *" ps "*) listing compose-ps; exit 0 ;;
  *"rpk topic list"*)
    listing rp-topic-list; echo "NAME  PARTITIONS  REPLICAS"
    [[ -e "$created" && "${FAKE_FAIL:-}" == create-then-listed ]] && echo "aip-probe.events  1  1"
    exit 0 ;;
  *"rpk group list"*) listing rp-group-list; echo "BROKER  GROUP  STATE"; exit 0 ;;
  *"kafka-topics.sh"*"--list"*) listing kafka-topic-list; echo "${FAKE_KAFKA_TOPIC:-}"; exit 0 ;;
  *"kafka-consumer-groups.sh"*"--list"*) listing kafka-group-list; exit 0 ;;
  *) exit 0 ;;
esac
"""


def _run_p5(tmp_path: Path, **env: str) -> tuple[int, list[str], Path]:
    bin_dir, raw = tmp_path / "bin", tmp_path / "raw"
    bin_dir.mkdir()
    fake = bin_dir / "docker"
    fake.write_text(FAKE_DOCKER)
    fake.chmod(0o755)
    log = tmp_path / "docker.log"
    run_env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "I3_RAW_DIR": str(raw),
        "FAKE_LOG": str(log),
        **env,
    }
    done = subprocess.run(
        ["bash", str(HARNESS / "preflight/p5.sh")], env=run_env, capture_output=True, check=False
    )
    return done.returncode, (log.read_text().splitlines() if log.exists() else []), raw


DELETES = ("delete", " rm ")


@pytest.mark.parametrize(
    "failure",
    ["compose-ps", "rp-topic-list", "kafka-topic-list", "rp-group-list", "kafka-group-list"],
)
def test_p5_stops_before_arming_the_teardown_when_a_listing_fails(tmp_path, failure: str) -> None:
    rc, calls, raw = _run_p5(tmp_path, FAKE_FAIL=failure)
    assert rc == 2
    assert not any(word in call for call in calls for word in DELETES), calls
    assert not any("topic create" in call for call in calls)
    assert not (raw / "P5-probe-stop.meta").exists()


def test_p5_stops_when_a_probe_name_already_exists(tmp_path) -> None:
    rc, calls, _ = _run_p5(tmp_path, FAKE_KAFKA_TOPIC="mm2-probe-configs")
    assert rc == 2
    assert not any(word in call for call in calls for word in DELETES), calls


def test_the_teardown_deletes_nothing_when_its_presence_checks_fail(tmp_path) -> None:
    rc, calls, _ = _run_p5(tmp_path, FAKE_FAIL="after-create")
    assert rc != 0 and any("rpk topic create" in call for call in calls)
    assert not any(word in call for call in calls for word in DELETES), calls


def test_the_teardown_deletes_exactly_what_it_confirms_present(tmp_path) -> None:
    rc, calls, _ = _run_p5(tmp_path, FAKE_FAIL="create-then-listed")
    assert rc != 0
    deleted = [call for call in calls if any(word in call for word in DELETES)]
    assert deleted == ["exec redpanda rpk topic delete aip-probe.events"]


def test_the_tilt_guard_never_matches_itself_and_sees_a_running_tilt(tmp_path) -> None:
    if subprocess.run(["pgrep", "-x", "tilt"], check=False, capture_output=True).returncode == 0:
        pytest.skip("a real Tilt runs on this machine")
    # The check's own shell carries the text "tilt up"; it must not count as a running Tilt.
    shell = f'I3_RAW_DIR="{tmp_path}" source "{HARNESS / "lib.sh"}"; : tilt up; tilt_stopped'
    assert subprocess.run(["bash", "-c", shell], check=False).returncode == 0
    # A process named tilt (a copy of sleep) counts.
    fake_tilt = tmp_path / "tilt"
    fake_tilt.symlink_to(shutil.which("sleep") or "/bin/sleep")
    fake = subprocess.Popen([str(fake_tilt), "30"])
    try:
        for _ in range(50):
            found = subprocess.run(["pgrep", "-x", "tilt"], check=False, capture_output=True)
            if found.returncode == 0:
                break
            time.sleep(0.05)
        assert subprocess.run(["bash", "-c", shell], check=False).returncode == 1
    finally:
        fake.kill()
        fake.wait()


# --- Helm overlays (D13) -------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["catalog", "image"])
def test_the_overlay_changes_only_the_broker_address(name: str) -> None:
    upstream = yaml.safe_load((ENV / f"upstream-values/ecommerce-{name}-service.yaml").read_text())
    overlay = yaml.safe_load((ENV / f"values-i3-{name}.yaml").read_text())
    assert set(overlay) == {"config"}
    before, after = upstream["config"].splitlines(), overlay["config"].splitlines()
    changed = [(b, a) for b, a in zip(before, after, strict=True) if b != a]
    assert changed == [('  brokers: "redpanda:29092"', '  brokers: "kafka:29092"')]


# --- Committed reference (C7) and declarations -------------------------------------------------------


def test_the_reference_digest_is_committed_and_matches() -> None:
    digest = hashlib.sha256((PKG / "expected-after.json").read_bytes()).hexdigest()
    assert (PKG / "expected-after.sha256").read_text() == f"{digest}  expected-after.json\n"


def test_the_reference_rows_equal_the_i2_two_broker_rows() -> None:
    expected = json.loads((PKG / "expected-after.json").read_text())
    i2 = json.loads((I2_FIXTURE / "expected.json").read_text())
    assert expected["rows"] == i2["rows"]
    assert expected["request"] == i2["request"]
    assert expected["limitations"] == i2["limitations"]


def test_the_after_wave_declarations_are_byte_copies_of_the_i2_fixture() -> None:
    ours = {
        p.relative_to(PKG / "declarations"): p
        for p in (PKG / "declarations").rglob("*")
        if p.is_file()
    }
    i2 = {
        p.relative_to(I2_FIXTURE / "declarations"): p
        for p in (I2_FIXTURE / "declarations").rglob("*")
        if p.is_file()
    }
    assert ours and set(ours) == set(i2)
    for rel, path in ours.items():
        assert path.read_bytes() == i2[rel].read_bytes(), rel


# --- Functional test (D15) -----------------------------------------------------------------------------


def test_the_dry_run_plans_the_three_steps_with_run_unique_names(capsys) -> None:
    assert functional.main(["--run-id", "r42x", "--dry-run"]) == 0
    planned = json.loads(capsys.readouterr().out)["planned"]
    methods = [call["method"] for call in planned]
    assert methods[0] == "tenant.v1.TenantRegistrationService/RegisterTenant"
    for method in (
        "catalog.v1.ProductService/CreateProduct",
        "image.v1.ImageService/ConfirmUpload",
        "catalog.v1.CategoryService/UpdateCategory",
        "catalog.v1.AttributeService/UpdateAttribute",
    ):
        assert method in methods
    polls = [call["poll_until"] for call in planned if "poll_until" in call]
    assert polls == [
        "the registration is COMPLETED",
        "Product Query returns the product with both image URLs",
        "Category Query returns the new category name",
        "Product Query returns the new attribute name",
        "Category Query returns the new attribute name",
    ]
    for call in planned:
        request = call.get("request", {})
        named = {k: v for k, v in request.items() if k in ("name", "slug", "filename", "alt")}
        assert all("r42x" in value for value in named.values()), call
        assert "token" not in json.dumps(call).lower().replace("upload_token", "")


def test_a_live_run_without_tokens_or_endpoints_is_refused() -> None:
    with pytest.raises(SystemExit):
        functional.main(["--run-id", "r42x"])
    with pytest.raises(SystemExit):
        functional.main(["--run-id", "R 42", "--dry-run"])


class _FakeServices:
    """The seven Connect-RPC services and the presigned upload, answering like protojson (camelCase,
    zero values omitted). `drop` removes one response field to exercise a missing value."""

    def __init__(self, drop: tuple[str, str] | None = None) -> None:
        self.drop = drop
        self.sent: list = []
        self.bodies: dict[str, dict] = {}
        self.names = {"attribute": "AIP I3 attribute r1", "category": "AIP I3 category r1"}

    def __call__(self, req, timeout):
        self.sent.append(req)
        method = req.full_url.rsplit("/", 1)[-1] if req.get_method() == "POST" else "PUT"
        body = json.loads(req.data) if req.get_method() == "POST" else {}
        self.bodies[method] = body
        if method == "UpdateCategory":
            self.names["category"] = body["name"]
        if method == "UpdateAttribute":
            self.names["attribute"] = body["name"]
        attrs = [{"name": self.names["attribute"]}]
        response = {
            "RegisterTenant": {"slug": "i3-r1", "status": "REGISTRATION_STATUS_PROVISIONING"},
            "GetRegistrationStatus": {"slug": "i3-r1", "status": "REGISTRATION_STATUS_COMPLETED"},
            "CreateAttribute": {"attribute": {"id": "a1"}},
            "CreateCategory": {"category": {"id": "c1"}},
            "CreatePresign": {"uploadUrl": "http://minio/up?X-Sig=SECRET-URL", "uploadToken": "t"},
            "PUT": {},
            "ConfirmUpload": {"image": {"id": "i1"}},
            "CreateProduct": {"product": {"id": "p1"}},
            "GetProductById": {
                "product": {"smallImageUrl": "s", "largeImageUrl": "l", "attributes": attrs}
            },
            "UpdateCategory": {"category": {"id": "c1", "version": "1"}},
            "GetCategoryById": {"category": {"name": self.names["category"], "attributes": attrs}},
            "GetAttributeById": {"attribute": {"id": "a1"}},
            "UpdateAttribute": {"attribute": {"id": "a1", "version": "1"}},
        }[method]
        if self.drop and self.drop[0] == method:
            response = {key: {} for key in response} if self.drop[1] == "id" else response
        return _Response(json.dumps(response).encode() if method != "PUT" else b"")


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def _live_driver(monkeypatch, fake: _FakeServices):
    monkeypatch.setattr(functional.urllib.request, "urlopen", fake)
    endpoints = dict.fromkeys(set(functional.ENDPOINT_OF.values()), "http://svc")
    token_commands = {
        "s2s": "echo SECRET-S2S",
        "user": "echo SECRET-USER",
    }
    return functional.Driver("r1", endpoints, token_commands, False)


def test_a_live_run_enters_the_shop_after_registration_and_records_no_secret(monkeypatch) -> None:
    fake = _FakeServices()
    driver = _live_driver(monkeypatch, fake)
    steps = functional.run(driver, timeout=5)
    assert [step["result"] for step in steps] == ["PASSED"] * 3
    rpc = [req for req in fake.sent if req.get_method() == "POST"]
    tenant = [req for req in rpc if "/tenant.v1." in req.full_url]
    others = [req for req in rpc if "/tenant.v1." not in req.full_url]
    # The tenant calls (RegisterTenant, then GetRegistrationStatus until COMPLETED) come first and
    # carry the platform token and no shop header.
    assert rpc[: len(tenant)] == tenant
    for req in tenant:
        assert req.get_header("Authorization") == "Bearer SECRET-S2S"
        assert req.get_header("X-tenant-slug") is None
    # Every catalog, image and query call carries the service token and the new shop's slug,
    # as the environment's own seeder does.
    for req in others:
        assert req.get_header("Authorization") == "Bearer SECRET-USER", req.full_url
        assert req.get_header("X-tenant-slug") == "i3-r1", req.full_url
    password = fake.bodies["RegisterTenant"]["password"]
    record = json.dumps(steps)
    for secret in ("SECRET", password, "Bearer", "X-Sig", "upload_token", "uploadToken"):
        assert secret not in record, secret
    # protojson omits a zero version: the updates send 0, never a placeholder.
    assert fake.bodies["UpdateCategory"]["version"] == 0
    assert fake.bodies["UpdateAttribute"]["version"] == 0
    assert "<" not in json.dumps(fake.bodies)


def test_a_missing_id_fails_the_step_with_a_clear_reason(monkeypatch) -> None:
    fake = _FakeServices(drop=("CreateAttribute", "id"))
    steps = functional.run(_live_driver(monkeypatch, fake), timeout=5)
    assert len(steps) == 1 and steps[0]["result"] == "FAILED"
    assert steps[0]["reason"] == "the response carries no attribute.id"
    assert "CreateCategory" not in fake.bodies


# --- Token command (I3b) -------------------------------------------------------------------------------

token_cmd = _load("i3_token", HARNESS / "tokens/token.py")
_SECRET_JSON = json.dumps(
    {
        "data": {
            "platform-client-id": base64.b64encode(b"pid").decode(),
            "platform-client-secret": base64.b64encode(b"TOP-SECRET-P").decode(),
            "ecommerce-m2m-client-id": base64.b64encode(b"eid").decode(),
            "ecommerce-m2m-client-secret": base64.b64encode(b"TOP-SECRET-E").decode(),
        }
    }
)


def _token_run(monkeypatch, capsys, *, kubectl_ok=True, response=b'{"access_token": "TKN"}'):
    posted = []

    def fake_run(cmd, **kwargs):
        if not kubectl_ok:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=_SECRET_JSON, stderr="")

    def fake_urlopen(req, timeout):
        posted.append(req)
        if response is None:
            raise OSError("connection refused, request was client_secret=TOP-SECRET-E")
        return _Response(response)

    monkeypatch.setattr(token_cmd.subprocess, "run", fake_run)
    monkeypatch.setattr(token_cmd.urllib.request, "urlopen", fake_urlopen)
    rc = token_cmd.main(["ecommerce"])
    out = capsys.readouterr()
    return rc, out.out, out.err, posted


def test_the_token_command_prints_only_the_token(monkeypatch, capsys) -> None:
    rc, out, err, posted = _token_run(monkeypatch, capsys)
    assert rc == 0 and out == "TKN\n" and err == ""
    form = dict(item.split("=", 1) for item in posted[0].data.decode().split("&"))
    assert form["grant_type"] == "client_credentials" and form["client_id"] == "eid"
    assert "cross-tenant" in form["scope"].replace("+", " ")
    assert posted[0].full_url == "http://localhost:3001/oidc/token"


@pytest.mark.parametrize(
    "kwargs",
    [{"kubectl_ok": False}, {"response": None}, {"response": b"{}"}, {"response": b"not json"}],
)
def test_the_token_command_fails_closed_and_never_prints_the_secret(
    monkeypatch, capsys, kwargs
) -> None:
    rc, out, err, _ = _token_run(monkeypatch, capsys, **kwargs)
    assert rc == 1 and out == ""
    assert "TOP-SECRET" not in err and "client_secret" not in err
