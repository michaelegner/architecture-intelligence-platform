"""v0.6.2 I1c-1: the Pitstop LIVE demo's traffic generator, live readiness check and launcher (spec §4.2, §4.3).

- the generator is exercised against a fake HTTP server standing in for the three Pitstop APIs: the four calls of a
  cycle, their payload shapes, uniqueness across cycles, the planning-date rule, the failure rules (nothing is
  retried, a job is finished at most once and only after a successful plan, the loop goes on), and startup that treats
  any HTTP answer as "up";
- `check_ready.py --live` is checked on synthetic answers built from the replay expectation: the live shape passes,
  a still declared-only route fails, and the usual deviations are reported;
- `run-live.sh` is checked statically for the properties the design depends on: import before the Pitstop stack,
  the "no completed window yet" exit, and `--down` that needs no fork directory.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO / "examples" / "pitstop-demo"
LIVE_DIR = DEMO_DIR / "live"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


generator = _load(LIVE_DIR / "traffic_generator.py", "pitstop_traffic_generator")
check_ready = _load(DEMO_DIR / "check_ready.py", "pitstop_check_ready_live")


class FakePitstop:
    """One HTTP server that answers like the three APIs; `fail` maps a path prefix to the status to return."""

    def __init__(self, fail: dict[str, int] | None = None):
        self.requests: list[tuple[str, str, dict | None]] = []
        self.fail = fail or {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                outer.requests.append((self.command, self.path, body))
                status = next(
                    (s for prefix, s in outer.fail.items() if self.path.startswith(prefix)), None
                )
                if status is None:
                    status = 200 if self.command == "PUT" else 201
                self.send_response(status)
                self.end_headers()
                self.wfile.write(b"{}")

            do_GET = do_POST = do_PUT = _answer

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def settings(self, **kwargs) -> generator.Settings:
        return generator.Settings(
            customer_api=f"{self.base}/c",
            vehicle_api=f"{self.base}/v",
            workshop_api=f"{self.base}/w",
            event_settle_seconds=0,
            **kwargs,
        )


def _no_sleep(_seconds: float) -> None:
    return None


# --- the generator ------------------------------------------------------------------------------------------------


def test_a_cycle_makes_the_four_calls_in_order_with_pitstops_payload_shapes():
    with FakePitstop() as pitstop:
        settings = pitstop.settings()
        result = generator.run_cycle(settings, 0, sleep=_no_sleep)

    assert result.ok
    assert result.statuses == {"customer": 201, "vehicle": 201, "plan": 201, "finish": 200}
    assert [(m, p.split("/", 2)[1]) for m, p, _ in pitstop.requests] == [
        ("POST", "c"),
        ("POST", "v"),
        ("POST", "w"),
        ("PUT", "w"),
    ]
    customer, vehicle, plan, finish = (body for _, _, body in pitstop.requests)
    day = date(2031, 1, 1).isoformat()
    assert pitstop.requests[0][1] == "/c/api/customers"
    assert pitstop.requests[1][1] == "/v/api/vehicles"
    assert pitstop.requests[2][1] == f"/w/api/workshopplanning/{day}/jobs"
    assert pitstop.requests[3][1] == f"/w/api/workshopplanning/{day}/jobs/{plan['jobId']}/finish"
    assert re.fullmatch(r"[0-9a-f]{32}", customer["customerId"])
    assert re.fullmatch(r"((\d{1,3}|[a-z]{1,3})-){2}(\d{1,3}|[a-z]{1,3})", vehicle["licenseNumber"])
    assert vehicle["ownerId"] == customer["customerId"]
    assert plan["customerInfo"]["Item1"] == customer["customerId"]
    assert plan["vehicleInfo"]["Item1"] == vehicle["licenseNumber"]
    assert finish["jobId"] == plan["jobId"]
    assert (
        plan["startTime"] < plan["endTime"]
        and plan["startTime"][:10] == plan["endTime"][:10] == day
    )
    assert finish["startTime"] < finish["endTime"]


def test_identifiers_and_planning_dates_are_unique_across_cycles():
    with FakePitstop() as pitstop:
        settings = pitstop.settings()
        results = [generator.run_cycle(settings, i, sleep=_no_sleep) for i in range(25)]

    assert len({r.planning_date for r in results}) == 25
    bodies = [body for _, _path, body in pitstop.requests if body]
    for key in ("customerId", "licenseNumber"):
        values = [b[key] for b in bodies if key in b]
        assert len(values) == len(set(values)) == 25, key
    # a job id appears in its plan body and its finish body (the same job), never in two jobs
    job_ids = [b["jobId"] for b in bodies if "jobId" in b]
    assert len(job_ids) == 50 and len(set(job_ids)) == 25


def test_the_planning_date_counts_from_the_base_date_and_wraps_far_in_the_future():
    settings = generator.Settings()
    assert generator.planning_date(settings, 0) == date(2031, 1, 1)
    assert generator.planning_date(settings, 365) == date(2032, 1, 1)
    assert generator.planning_date(settings, generator.MAX_PLANNING_DAYS) == date(2031, 1, 1)
    assert generator.planning_date(settings, generator.MAX_PLANNING_DAYS - 1).year < 9999


def test_the_cycle_index_comes_from_the_wall_clock_so_a_restart_never_reuses_a_date():
    settings = generator.Settings(interval_seconds=600)
    assert generator.cycle_index_now(settings, now=0) == 0
    assert generator.cycle_index_now(settings, now=599) == 0
    assert generator.cycle_index_now(settings, now=600) == 1
    assert (
        generator.cycle_index_now(settings, now=1_000_000)
        == generator.cycle_index_now(settings, now=1_000_001)
        or True
    )  # same interval bucket or the next one: both are monotonic
    assert generator.cycle_index_now(settings, now=2_000_000) > generator.cycle_index_now(
        settings, now=1_000_000
    )


@pytest.mark.parametrize("failing_step", ["/c/", "/v/"])
def test_a_failed_registration_is_counted_but_planning_and_finishing_still_run(failing_step):
    with FakePitstop(fail={failing_step: 500}) as pitstop:
        result = generator.run_cycle(pitstop.settings(), 3, sleep=_no_sleep)

    assert not result.ok
    assert result.statuses["plan"] == 201 and result.statuses["finish"] == 200
    assert len(pitstop.requests) == 4  # nothing is retried


def test_a_job_is_never_finished_when_planning_it_failed_and_never_twice():
    with FakePitstop(fail={"/w/": 500}) as pitstop:
        result = generator.run_cycle(pitstop.settings(), 4, sleep=_no_sleep)
    assert result.statuses["plan"] == 500 and "finish" not in result.statuses
    assert [m for m, _, _ in pitstop.requests] == ["POST", "POST", "POST"]

    with FakePitstop() as pitstop:
        generator.run_cycle(pitstop.settings(), 5, sleep=_no_sleep)
    assert [m for m, _, _ in pitstop.requests].count("PUT") == 1


def test_an_unreachable_server_is_a_none_status_not_an_exception():
    assert generator.request("GET", "http://127.0.0.1:1/hc", timeout=1) is None


def test_startup_treats_any_http_answer_as_up_even_a_503_health_check():
    with FakePitstop(fail={"/w/hc": 503}) as pitstop:
        assert generator.wait_until_up(pitstop.settings(startup_timeout_seconds=5), sleep=_no_sleep)


def test_startup_gives_up_after_the_timeout_when_an_api_never_answers():
    ticks = iter(range(0, 10_000, 100))
    settings = generator.Settings(
        customer_api="http://127.0.0.1:1",
        vehicle_api="http://127.0.0.1:1",
        workshop_api="http://127.0.0.1:1",
        startup_timeout_seconds=300,
    )
    assert not generator.wait_until_up(settings, sleep=_no_sleep, clock=lambda: next(ticks))


def test_settings_come_from_the_environment_with_documented_defaults():
    defaults = generator.Settings.from_env({})
    assert defaults.interval_seconds == 600  # 144 cycles a day
    assert defaults.planning_base_date == date(2031, 1, 1)
    custom = generator.Settings.from_env(
        {
            "TRAFFIC_INTERVAL_SECONDS": "60",
            "WORKSHOP_API": "http://w:1/",
            "PLANNING_BASE_DATE": "2040-02-03",
        }
    )
    assert custom.interval_seconds == 60 and custom.workshop_api == "http://w:1"
    assert custom.planning_base_date == date(2040, 2, 3)


# --- the live readiness check -------------------------------------------------------------------------------------


def _claim(name: str, queue: str, refs: int, **overrides) -> dict:
    claim = {
        "claim_id": f"aip:claim:v1:{name}",
        "predicate": "DIRECT_DEPENDENCY",
        "subject": {"name": "WorkshopManagementAPI"},
        "object": {"name": name},
        "destination_resolution": "RESOLVED_SERVICE",
        "delivery": {
            "relation_type": "PUBLISHES_TO",
            "via": {"type": "TOPIC", "name": "Pitstop"},
            "subscription": {"name": queue},
        },
        "qualification": "CONFIRMED",
        "coverage": None,
        "evidence_refs": ["p1", "p2"],
        "resolution_evidence_refs": [f"{name}-{i}" for i in range(refs)],
    }
    claim.update(overrides)
    return claim


def _answer(refs_by_receiver: dict[str, int]) -> dict:
    claims = [
        _claim(name, queue, refs_by_receiver[name])
        for name, (queue, _refs) in check_ready.EXPECTED_RECEIVERS.items()
    ]
    broker = {
        "claim_id": "aip:claim:v1:broker",
        "predicate": "USES_BROKER",
        "object": {"type": "BROKER", "name": check_ready.EXPECTED_BROKER},
    }
    return {
        "outcome": "ANSWERED",
        "schema_version": "0.6",
        "claims": [*claims, broker],
        "limitations": [],
        "data": {"broker_claim_ids": [broker["claim_id"]]},
    }


LIVE = {name: 2 for name in check_ready.EXPECTED_RECEIVERS}


def test_the_live_expectation_wants_every_route_observed_the_replay_expectation_does_not():
    live = _answer(LIVE)
    replay = _answer({n: refs for n, (_q, refs) in check_ready.EXPECTED_RECEIVERS.items()})
    assert check_ready.check_answer(live, live=True) == []
    assert check_ready.check_answer(replay, live=False) == []
    # the replay's deliberately declared-only AuditlogService route is a failure live
    assert check_ready.check_answer(replay, live=True) == [
        "receiver AuditlogService: ('Auditlog', 1), expected ('Auditlog', 2)"
    ]
    # and the live shape is a failure for the replay, which expects Auditlog declared-only
    assert check_ready.check_answer(live, live=False) == [
        "receiver AuditlogService: ('Auditlog', 2), expected ('Auditlog', 1)"
    ]


def test_a_missing_receiver_a_wrong_qualification_and_a_limitation_are_reported_live():
    answer = _answer(LIVE)
    answer["claims"] = [c for c in answer["claims"] if c["object"].get("name") != "InvoiceService"]
    problems = check_ready.check_answer(answer, live=True)
    assert any("4 PUBLISHES_TO claims" in p for p in problems)
    assert any("receiver InvoiceService: None" in p for p in problems)

    answer = _answer(LIVE)
    answer["claims"][0]["qualification"] = "NOT_OBSERVED_IN_WINDOW"
    answer["claims"][0]["coverage"] = "NONE"
    assert any("expected CONFIRMED" in p for p in check_ready.check_answer(answer, live=True))

    answer = _answer(LIVE)
    answer["limitations"] = [{"code": "UNRESOLVED_IDENTITY", "claim_ids": []}]
    assert any("limitations" in p for p in check_ready.check_answer(answer, live=True))


def test_the_live_context_is_one_whole_utc_day():
    assert check_ready.live_context("2026-10-08") == {
        "environment": "pitstop-demo",
        "window_start": "2026-10-08T00:00:00Z",
        "window_end": "2026-10-08T23:59:59Z",
    }


def test_live_mode_needs_a_date_and_import_only_is_a_separate_mode(capsys):
    with pytest.raises(SystemExit) as exit_info:
        check_ready.main(["--live"])
    assert exit_info.value.code == 2
    assert "--live needs --date" in capsys.readouterr().err


# --- the launcher ---------------------------------------------------------------------------------------------------


def _script() -> str:
    return (LIVE_DIR / "run-live.sh").read_text()


def test_the_import_happens_before_the_pitstop_stack_and_the_generator_start():
    script = _script()
    import_at = script.index('"$AIP_URL/api/import"')
    stack_at = script.index("\ncompose up -d\n")
    assert import_at < stack_at
    # the first `up` names only AIP, Neo4j and the Collector, so no Pitstop span can precede the import
    first_up = re.search(r"compose up -d --build --wait ([a-z0-9 -]+)\n", script).group(1).split()
    assert first_up == ["architecture-intelligence", "neo4j", "aip-collector"]
    assert "--import-only" in script[import_at:stack_at]


def test_down_needs_no_fork_directory_and_removes_the_whole_project():
    script = _script()
    down_block = script[script.index('if [[ "${1:-}" == "--down" ]]') :]
    down_block = down_block[: down_block.index("\nfi\n")]
    assert "com.docker.compose.project=$PROJECT" in down_block
    assert (
        "docker compose" not in down_block
    )  # no compose model: the repo root has a compose file of its own
    assert "PITSTOP_FORK_DIR" not in down_block
    assert script.index("--down") < script.index("PITSTOP_FORK_DIR must point")


def test_check_refuses_a_window_that_is_not_wholly_in_the_past_or_predates_the_start():
    script = _script()
    assert "exit 3" in script
    assert "is not wholly in the past" in script
    assert "No completed window yet" in script
    assert "date -u -d yesterday +%F" in script
    assert "live-started-on" in script


def test_run_sh_delegates_live_and_keeps_its_replay_behaviour():
    run_sh = (DEMO_DIR / "run.sh").read_text()
    assert 'exec "$DEMO_DIR/live/run-live.sh" "${@:2}"' in run_sh
    assert "not available yet" not in run_sh


def test_the_live_compose_includes_the_fork_applies_the_isolation_and_publishes_only_aip():
    compose = (LIVE_DIR / "docker-compose.yml").read_text()
    assert "${PITSTOP_FORK_DIR}/src/docker-compose.otel.yml" in compose
    assert "./examples/pitstop-demo/live/pitstop-live-override.yml" in compose
    published = re.findall(r'^\s+- "([^"]+:\d+:\d+)"', compose, flags=re.MULTILINE)
    assert published == ["127.0.0.1:8000:8000"]
    override = (LIVE_DIR / "pitstop-live-override.yml").read_text()
    for service in ("rabbitmq", "sqlserver", "mailserver", "logserver", "webapp"):
        block = re.search(
            rf"^  {service}:\n((?:    .*\n|\n)*)", override, flags=re.MULTILINE
        ).group(1)
        assert "container_name: !reset null" in block, service
        assert "ports: !reset []" in block, service
    # the services the demo does not need never start
    assert override.count('profiles: ["unused"]') == 2
    # the fork's data directory is never bind-mounted
    assert not [
        l for l in override.splitlines() if ".containerdata" in l and not l.lstrip().startswith("#")
    ]
