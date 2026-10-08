"""Controlled traffic generator for the Pitstop live demo (v0.6.2 spec §4.2).

Drives a running Pitstop through the application's own HTTP API only, at a steady, documented rate, so that
every observation window holds messaging traffic on the exchange `Pitstop`. One cycle is:

    1. register a customer          POST /api/customers                                   (CustomerManagementAPI)
    2. register a vehicle           POST /api/vehicles                                    (VehicleManagementAPI)
    3. plan a maintenance job       POST /api/workshopplanning/{date}/jobs                (WorkshopManagementAPI)
    4. finish that job              PUT  /api/workshopplanning/{date}/jobs/{jobId}/finish (WorkshopManagementAPI)

which publishes CustomerRegistered, VehicleRegistered, WorkshopPlanningCreated, MaintenanceJobPlanned and
MaintenanceJobFinished to every consumer queue (about thirty messaging spans per cycle).

Rules the generator keeps (the reasons are Pitstop's own constraints):
- Every cycle uses a fresh customer id, licence number, job id and message ids (the customer id and licence number
  are primary keys: a duplicate is a 500).
- Every cycle plans on its own synthetic date (`PLANNING_BASE_DATE` plus the interval counter), so no planning date
  accumulates events (a plan or finish replays all events of its date) and the "at most three overlapping jobs per
  date" rule is never reached. The counter is derived from the wall clock, so a restart never reuses a date.
- A job is finished at most once, and only if planning it succeeded (finishing twice, or an unknown job, is a 500).
- Nothing is retried: a failed step is logged and counted, and the next step or cycle still runs. Pitstop's messaging
  library can fail the first publish of a request (its broker connect is not awaited), so an occasional 500 is
  expected and does not stop the loop.
- Startup waits until the three APIs answer HTTP at all. It deliberately does not wait for a healthy `/hc` of the
  workshop API: that stays 503 until its first request creates the event-store database.

Standard library only. Configuration comes from environment variables (see `Settings`).
"""

from __future__ import annotations

import json
import os
import random
import signal
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

# Pitstop's licence-number format is ((\d{1,3}|[a-z]{1,3})-){2}(\d{1,3}|[a-z]{1,3}); these are the letters its own UI
# tests draw from.
LICENSE_LETTERS = "DFGHJKLNPRSTXYZ"
MAX_PLANNING_DAYS = (
    2_000_000  # from 2031-01-01 this stays below the year 7600, inside .NET's DateTime range
)


@dataclass(frozen=True)
class Settings:
    customer_api: str = "http://customermanagementapi:5100"
    vehicle_api: str = "http://vehiclemanagementapi:5000"
    workshop_api: str = "http://workshopmanagementapi:5200"
    interval_seconds: int = 600
    planning_base_date: date = date(2031, 1, 1)
    event_settle_seconds: float = 2.0
    startup_timeout_seconds: int = 900

    @staticmethod
    def from_env(env: dict[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        defaults = Settings()
        return Settings(
            customer_api=env.get("CUSTOMER_API", defaults.customer_api).rstrip("/"),
            vehicle_api=env.get("VEHICLE_API", defaults.vehicle_api).rstrip("/"),
            workshop_api=env.get("WORKSHOP_API", defaults.workshop_api).rstrip("/"),
            interval_seconds=int(env.get("TRAFFIC_INTERVAL_SECONDS", defaults.interval_seconds)),
            planning_base_date=date.fromisoformat(
                env.get("PLANNING_BASE_DATE", defaults.planning_base_date.isoformat())
            ),
            event_settle_seconds=float(
                env.get("EVENT_SETTLE_SECONDS", defaults.event_settle_seconds)
            ),
            startup_timeout_seconds=int(
                env.get("STARTUP_TIMEOUT_SECONDS", defaults.startup_timeout_seconds)
            ),
        )


@dataclass
class CycleResult:
    cycle: int
    planning_date: date
    statuses: dict[str, int | None] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(status is not None and 200 <= status < 300 for status in self.statuses.values())


def planning_date(settings: Settings, cycle_index: int) -> date:
    return settings.planning_base_date + timedelta(days=cycle_index % MAX_PLANNING_DAYS)


def licence_number(rng: random.Random) -> str:
    """Letters-digits-letters, e.g. `XN-482-ZT`: valid for Pitstop's pattern, 15^4 * 1000 combinations."""
    letters = "".join(rng.choice(LICENSE_LETTERS) for _ in range(4))
    return f"{letters[:2]}-{rng.randrange(1000):03d}-{letters[2:]}".lower()


def request(method: str, url: str, body: dict | None = None, timeout: float = 30) -> int | None:
    """Returns the HTTP status, or None when the server could not be reached. Never raises on HTTP errors."""
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=data, method=method, headers=headers), timeout=timeout
        ) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return None


def run_cycle(
    settings: Settings,
    cycle_index: int,
    *,
    http: Callable[..., int | None] = request,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> CycleResult:
    rng = rng or random.SystemRandom()
    day = planning_date(settings, cycle_index)
    customer_id = uuid.uuid4().hex
    license_number = licence_number(rng)
    job_id = str(uuid.uuid4())
    result = CycleResult(cycle=cycle_index, planning_date=day)

    result.statuses["customer"] = http(
        "POST",
        f"{settings.customer_api}/api/customers",
        {
            "messageId": str(uuid.uuid4()),
            "customerId": customer_id,
            "name": f"Demo customer {customer_id[:8]}",
            "address": "Demo street 1",
            "postalCode": "1234AB",
            "city": "Utrecht",
            "telephoneNumber": "0612345678",
            "emailAddress": f"{customer_id[:8]}@example.org",
        },
    )
    result.statuses["vehicle"] = http(
        "POST",
        f"{settings.vehicle_api}/api/vehicles",
        {
            "messageId": str(uuid.uuid4()),
            "licenseNumber": license_number,
            "brand": "Volvo",
            "type": "V70",
            "ownerId": customer_id,
        },
    )
    sleep(
        settings.event_settle_seconds
    )  # let the event handler cache the customer and vehicle (UITest does too)
    result.statuses["plan"] = http(
        "POST",
        f"{settings.workshop_api}/api/workshopplanning/{day.isoformat()}/jobs",
        {
            "messageId": str(uuid.uuid4()),
            "jobId": job_id,
            "startTime": f"{day.isoformat()}T08:00:00",
            "endTime": f"{day.isoformat()}T12:00:00",
            # System.ValueTuple serialises as Item1..Item3
            "customerInfo": {
                "Item1": customer_id,
                "Item2": f"Demo customer {customer_id[:8]}",
                "Item3": "0612345678",
            },
            "vehicleInfo": {"Item1": license_number, "Item2": "Volvo", "Item3": "V70"},
            "description": "Controlled demo traffic",
        },
    )
    if result.statuses["plan"] is not None and 200 <= result.statuses["plan"] < 300:
        sleep(1)
        result.statuses["finish"] = http(
            "PUT",
            f"{settings.workshop_api}/api/workshopplanning/{day.isoformat()}/jobs/{job_id}/finish",
            {
                "messageId": str(uuid.uuid4()),
                "jobId": job_id,
                "startTime": f"{day.isoformat()}T08:00:00",
                "endTime": f"{day.isoformat()}T11:00:00",
                "notes": "Controlled demo traffic",
            },
        )
    return result


def wait_until_up(
    settings: Settings,
    *,
    http: Callable[..., int | None] = request,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """True once all three APIs answer HTTP with any status (connection refused means: not up yet)."""
    urls = [
        f"{settings.customer_api}/hc",
        f"{settings.vehicle_api}/hc",
        f"{settings.workshop_api}/hc",
    ]
    deadline = clock() + settings.startup_timeout_seconds
    pending = list(urls)
    while pending:
        pending = [url for url in pending if http("GET", url, timeout=5) is None]
        if not pending:
            return True
        if clock() >= deadline:
            return False
        sleep(3)
    return True


def cycle_index_now(settings: Settings, now: float | None = None) -> int:
    """Wall-clock based, so a restarted generator never reuses a planning date."""
    return int((time.time() if now is None else now) // max(settings.interval_seconds, 1))


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_env()
    stop = False

    def request_stop(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    print(
        f"traffic generator: one cycle every {settings.interval_seconds}s "
        f"(customer {settings.customer_api}, vehicle {settings.vehicle_api}, workshop {settings.workshop_api})",
        flush=True,
    )
    if not wait_until_up(settings):
        print("error: the Pitstop APIs did not answer in time", file=sys.stderr, flush=True)
        return 1

    completed = failed = 0
    last_index = -1
    while not stop:
        index = cycle_index_now(settings)
        if index != last_index:
            last_index = index
            result = run_cycle(settings, index)
            completed += result.ok
            failed += not result.ok
            print(
                f"cycle {index} ({result.planning_date}): "
                + " ".join(f"{step}={status}" for step, status in result.statuses.items())
                + f" | ok={completed} failed={failed}",
                flush=True,
            )
        # sleep in short steps so a stop request is honoured promptly
        for _ in range(max(1, min(settings.interval_seconds, 10))):
            if stop:
                break
            time.sleep(1)
    print("traffic generator stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
