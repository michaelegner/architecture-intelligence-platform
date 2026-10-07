"""v0.6.2 I1a readiness check for the Pitstop demo (spec §4.3, §4.4).

Runs inside the `architecture-intelligence` container (stdlib only), after run.sh has imported the
overlay and replayed fixtures/otlp.json:

    docker compose ... exec -T architecture-intelligence python pitstop/check_ready.py < import.json

It reads the import report from stdin, then reads the real `WorkshopManagementAPI` dependencies
answer once over REST. It never writes. It exits 1 with a readable list of problems, rather than
letting a misleading demo start, when either differs from what the overlay and the authored fixture
require. On success it prints the dependencies answer as JSON, so run.sh can record it.

The expectations are the §4.4 semantic ones, not byte-identical output: five `RESOLVED_SERVICE` claims
through the five named queues of the exchange `Pitstop`, every claim carrying the publisher's
qualification, one declared resolution ref per receiver plus one observed ref where a receive span lies
in the window, and one Broker claim.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

AIP_URL = "http://localhost:8000"
SERVICE_ID = "service:workshop-management-api"
SERVICE_NAME = "WorkshopManagementAPI"
# One whole UTC day wholly in the past, which fixtures/otlp.json's timestamps fall in.
CONTEXT = {
    "environment": "pitstop-demo",
    "window_start": "2026-10-06T00:00:00Z",
    "window_end": "2026-10-06T23:59:59Z",
}
EXPECTED_OVERLAY = {
    f"{directory}/asyncapi.yaml": ("ACCEPTED", set())
    for directory in (
        "workshop-management-api",
        "customer-management-api",
        "vehicle-management-api",
        "time-service",
        "invoice-service",
        "notification-service",
        "workshop-management-event-handler",
        "auditlog-service",
        "reporting-service",
    )
}
EXPECTED_RUNS = {"pitstop-demo-overlay": EXPECTED_OVERLAY}
TOPIC = "Pitstop"
# receiver service name -> (its queue, resolution refs: the declared route ref, plus one observed ref
# where the authored fixture holds a receive span; AuditlogService deliberately has none)
EXPECTED_RECEIVERS = {
    "InvoiceService": ("Invoicing", 2),
    "NotificationService": ("Notifications", 2),
    "WorkshopManagementEventHandler": ("WorkshopManagement", 2),
    "ReportingService": ("Reporting", 2),
    "AuditlogService": ("Auditlog", 1),
}
# Every claim carries the publisher's qualification: one send span lies in the window.
EXPECTED_QUALIFICATION = "CONFIRMED"
EXPECTED_BROKER = "rabbitmq:pitstop-rabbitmq"


def check_import(report: dict) -> list[str]:
    problems = []
    runs = {run["configured_source_id"]: run for run in report.get("runs", [])}
    if set(runs) != set(EXPECTED_RUNS):
        problems.append(f"import runs: expected {sorted(EXPECTED_RUNS)}, got {sorted(runs)}")
    for source_id, expected_results in EXPECTED_RUNS.items():
        run = runs.get(source_id)
        if run is None:
            continue
        if run["inventory_status"] != "COMPLETE" or not run["committed"]:
            problems.append(
                f"{source_id}: inventory {run['inventory_status']}, committed {run['committed']}"
            )
        actual = {r["locator"]: r for r in run["source_results"]}
        if set(actual) != set(expected_results):
            problems.append(
                f"{source_id}: sources {sorted(actual)}, expected {sorted(expected_results)}"
            )
        for locator, (result, codes) in expected_results.items():
            if locator not in actual:
                continue
            got = actual[locator]
            got_codes = {d.get("code") for d in got.get("diagnostics", [])}
            if got["result"] != result or got_codes != codes:
                problems.append(
                    f"{source_id}/{locator}: {got['result']} {sorted(got_codes)}, "
                    f"expected {result} with {sorted(codes)}"
                )
    return problems


def _get(view: str) -> dict:
    query = urllib.parse.urlencode(
        {
            "environment": CONTEXT["environment"],
            "from": CONTEXT["window_start"],
            "to": CONTEXT["window_end"],
        }
    )
    url = f"{AIP_URL}/api/services/{urllib.parse.quote(SERVICE_ID)}/{view}?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def dependencies() -> dict:
    return _get("dependencies")


def drift() -> dict:
    return _get("drift")


def relation(claim: dict) -> str | None:
    return (claim.get("delivery") or {}).get("relation_type")


def check_answer(answer: dict) -> list[str]:
    problems = []
    if answer.get("outcome") != "ANSWERED":
        problems.append(f"dependencies outcome {answer.get('outcome')}, expected ANSWERED")
    claims = answer.get("claims", [])
    published = [c for c in claims if relation(c) == "PUBLISHES_TO"]
    if len(published) != len(EXPECTED_RECEIVERS):
        problems.append(
            f"{len(published)} PUBLISHES_TO claims, expected {len(EXPECTED_RECEIVERS)} "
            "(one per receiver, through the Topic)"
        )
    names = {c["subject"]["name"] for c in published}
    if names != {SERVICE_NAME}:
        problems.append(f"publisher names {sorted(names)}, expected {SERVICE_NAME!r}")

    receivers = {}
    for claim in published:
        via = claim["delivery"].get("via") or {}
        if via.get("type") != "TOPIC" or via.get("name") != TOPIC:
            problems.append(f"{claim['claim_id']}: via {via}, expected the Topic {TOPIC!r}")
        if claim.get("destination_resolution") != "RESOLVED_SERVICE":
            problems.append(
                f"{claim['object'].get('name')}: {claim.get('destination_resolution')}, "
                "expected RESOLVED_SERVICE"
            )
        if (
            claim.get("qualification") != EXPECTED_QUALIFICATION
            or claim.get("coverage") is not None
        ):
            problems.append(
                f"{claim['object'].get('name')}: qualification {claim.get('qualification')} "
                f"coverage {claim.get('coverage')}, expected {EXPECTED_QUALIFICATION} without coverage"
            )
        queue = (claim["delivery"].get("subscription") or {}).get("name")
        receivers[claim["object"].get("name")] = (queue, len(claim["resolution_evidence_refs"]))
    if receivers != EXPECTED_RECEIVERS:
        for name in sorted(set(receivers) | set(EXPECTED_RECEIVERS)):
            if receivers.get(name) != EXPECTED_RECEIVERS.get(name):
                problems.append(
                    f"receiver {name}: {receivers.get(name)}, expected {EXPECTED_RECEIVERS.get(name)}"
                )

    limitations = [(lim.get("code"), lim.get("claim_ids")) for lim in answer.get("limitations", [])]
    if limitations:
        problems.append(f"limitations {limitations}, expected none")

    brokers = [c for c in claims if c["predicate"] == "USES_BROKER"]
    broker_shape = [(c["object"].get("type"), c["object"].get("name")) for c in brokers]
    if broker_shape != [("BROKER", EXPECTED_BROKER)]:
        problems.append(
            f"USES_BROKER {broker_shape}, expected exactly one BROKER {EXPECTED_BROKER!r}"
        )
    if answer.get("schema_version") != "0.6" or answer["data"].get("broker_claim_ids") != [
        c["claim_id"] for c in brokers
    ]:
        problems.append("the answer is not the Broker-aware v0.6 shape naming its Broker claim")

    unexpected = [
        c for c in claims if c["predicate"] != "USES_BROKER" and relation(c) != "PUBLISHES_TO"
    ]
    if unexpected:
        problems.append(f"unexpected claims: {[c.get('claim_id') for c in unexpected]}")
    return problems


def check_drift(answer: dict) -> list[str]:
    """§4.4: the drift answer is only what the existing rules produce. Recorded on the first real
    replay: `ANSWERED` with no claims and no limitations for the publisher in this context."""
    problems = []
    if answer.get("tool") != "get_architecture_drift":
        problems.append(f"drift tool {answer.get('tool')}, expected get_architecture_drift")
    if answer.get("outcome") != "ANSWERED":
        problems.append(f"drift outcome {answer.get('outcome')}, expected ANSWERED")
    if answer.get("claims"):
        problems.append(
            f"drift claims {[c.get('claim_id') for c in answer['claims']]}, expected none"
        )
    if answer.get("limitations"):
        problems.append(f"drift limitations {answer['limitations']}, expected none")
    return problems


def main() -> int:
    try:
        problems = check_import(json.load(sys.stdin))
    except json.JSONDecodeError as exc:
        problems = [f"the import report is not JSON: {exc}"]
    try:
        answer = dependencies()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        # HTTPError is a URLError: a non-2xx answer is reported with its status, not a traceback.
        answer = None
        problems.append(f"could not read the WorkshopManagementAPI dependencies answer: {exc}")
    if answer is not None:
        problems += check_answer(answer)
    try:
        problems += check_drift(drift())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        problems.append(f"could not read the WorkshopManagementAPI drift answer: {exc}")
    if problems:
        print(
            "The demo is NOT ready - the result differs from what the overlay and fixture require:"
        )
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(json.dumps(answer, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
