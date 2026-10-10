"""v0.5.1 I1 readiness check for the Quarkus Super Heroes demo (spec §4 step 5).

Runs inside the `architecture-intelligence` container (stdlib only), after run.sh has imported the
inputs and replayed otlp.json:

    docker compose ... exec -T architecture-intelligence python qsh/check_ready.py < import.json

It reads the import report from stdin, then reads the real `rest-fights` dependencies answer once
over REST. It never writes. It exits 1 with a readable list of problems, rather than letting a
misleading demo start, when either differs from what the frozen evidence and the overlay require.
On success it prints the answer's claims as JSON, so run.sh can record them.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

AIP_URL = "http://localhost:8000"
SERVICE_ID = "service:rest-fights"
# The frozen v0.5.0 I5 final-candidate observation window, which otlp.json's timestamps fall in.
CONTEXT = {
    "environment": "quarkus-i5",
    "window_start": "2026-09-25T13:06:47Z",
    "window_end": "2026-09-25T13:06:54Z",
}
EXPECTED_RUNS = {
    # configured source id -> {locator: (result, required diagnostic codes)}
    "qsh-v0.5-declarations": {
        "rest-fights/architecture.yaml": ("ACCEPTED", set()),
        "rest-fights/openapi.yml": ("ACCEPTED", set()),
        "rest-heroes/openapi.yml": ("ACCEPTED", set()),
        "rest-narration/openapi.yml": ("ACCEPTED", set()),
        "rest-villains/openapi.yml": ("ACCEPTED", set()),
    },
    "qsh-demo-overlay": {
        "rest-fights/asyncapi.yaml": ("ACCEPTED", set()),
        "event-statistics/asyncapi.yaml": (
            "ACCEPTED_WITH_LIMITATIONS",
            {"SUBSCRIPTION_IDENTITY_MISSING"},
        ),
    },
    "qsh-k8s-namespaced": {"envelope.yaml": ("ACCEPTED_WITH_LIMITATIONS", set())},
}
# The seven per-operation CALLS of the frozen v0.5.0 answer: operation -> qualification.
EXPECTED_CALLS = {
    "operation:service:rest-heroes:GET:/api/heroes/hello": "NOT_OBSERVED_IN_WINDOW",
    "operation:service:rest-heroes:GET:/api/heroes/random": "CONFIRMED",
    "operation:service:rest-narration:GET:/api/narration/hello": "NOT_OBSERVED_IN_WINDOW",
    "operation:service:rest-narration:POST:/api/narration": "CONFIRMED",
    "operation:service:rest-narration:POST:/api/narration/image": "NOT_OBSERVED_IN_WINDOW",
    "operation:service:rest-villains:GET:/api/villains/hello": "NOT_OBSERVED_IN_WINDOW",
    "operation:service:rest-villains:GET:/api/villains/random": "CONFIRMED",
}
# The overlay's answer shape, recorded on the first real run (spec §4 step 5) and consistent with
# the v0.5.0 I4 rules: the declared Topic has no evidenced Subscription, so the claim keeps the Topic
# as its direct target, and the whole answer is PARTIAL with one UNRESOLVED_IDENTITY limitation.
# The frozen v0.5.0 answer, without the overlay, was ANSWERED with no limitations.
EXPECTED_PUBLISH = {
    "qualification": "NOT_OBSERVED_IN_WINDOW",
    "coverage": "PARTIAL",
    "destination_resolution": "DIRECT_TARGET_FALLBACK",
}
SERVICE_NAME = "Fights API"  # the upstream OpenAPI title; the overlay must not rename the Service
# v0.6.1 I2 (spec §5): the overlay declares `x-aip-broker-id: kafka:fights-kafka` for rest-fights, so
# the answer is the Broker-aware v0.6 shape and carries exactly one BrokerClaim for it. Knowing the
# Broker does not resolve the missing Subscription: the PARTIAL/UNRESOLVED_IDENTITY shape above is
# unchanged.
EXPECTED_BROKER = "kafka:fights-kafka"


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
            if got["result"] != result or not codes <= got_codes:
                problems.append(
                    f"{source_id}/{locator}: {got['result']} {sorted(got_codes)}, "
                    f"expected {result} with {sorted(codes)}"
                )
    return problems


def dependencies() -> dict:
    query = urllib.parse.urlencode(
        {
            "environment": CONTEXT["environment"],
            "from": CONTEXT["window_start"],
            "to": CONTEXT["window_end"],
        }
    )
    url = f"{AIP_URL}/api/services/{urllib.parse.quote(SERVICE_ID)}/dependencies?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def relation(claim: dict) -> str | None:
    return (claim.get("delivery") or {}).get("relation_type")


def check_answer(answer: dict) -> list[str]:
    problems = []
    if answer.get("outcome") != "PARTIAL":
        problems.append(f"dependencies outcome {answer.get('outcome')}, expected PARTIAL")
    claims = answer.get("claims", [])
    names = {c["subject"]["name"] for c in claims}
    if names != {SERVICE_NAME}:
        problems.append(f"rest-fights display names {sorted(names)}, expected {SERVICE_NAME!r}")
    call_claims = [c for c in claims if relation(c) == "CALLS"]
    calls = {c["delivery"]["via"]["id"]: c.get("qualification") for c in call_claims}
    if len(call_claims) != len(calls) or calls != EXPECTED_CALLS:
        for operation in sorted(set(calls) | set(EXPECTED_CALLS)):
            if calls.get(operation) != EXPECTED_CALLS.get(operation):
                problems.append(
                    f"CALLS {operation}: {calls.get(operation)}, "
                    f"expected {EXPECTED_CALLS.get(operation)}"
                )
        if len(call_claims) != len(calls):
            problems.append(f"{len(call_claims)} CALLS claims for {len(calls)} operations")

    deployed = [c for c in claims if c["predicate"] == "DEPLOYED_AS"]
    if [c.get("resolution_method") for c in deployed] != ["RESOLVED_CONFIGURED"]:
        problems.append(
            f"DEPLOYED_AS {[c.get('resolution_method') for c in deployed]}, "
            "expected exactly one RESOLVED_CONFIGURED"
        )

    published = [c for c in claims if relation(c) == "PUBLISHES_TO"]
    if len(published) != 1:
        problems.append(
            f"{len(published)} PUBLISHES_TO claims, expected exactly one (Topic fights)"
        )
    for claim in published:
        target = claim["delivery"].get("via") or claim["object"]
        if target.get("type") != "TOPIC" or target.get("name") != "fights":
            problems.append(f"PUBLISHES_TO target {target}, expected the Topic fights")
        shape = {key: claim.get(key) for key in EXPECTED_PUBLISH}
        if shape != EXPECTED_PUBLISH or claim["delivery"].get("subscription") is not None:
            problems.append(
                f"PUBLISHES_TO {shape}, subscription {claim['delivery'].get('subscription')}; "
                f"expected {EXPECTED_PUBLISH} and no subscription"
            )
    limitations = [(lim.get("code"), lim.get("claim_ids")) for lim in answer.get("limitations", [])]
    expected_limitations = [("UNRESOLVED_IDENTITY", [c["claim_id"] for c in published])]
    if limitations != expected_limitations:
        problems.append(f"limitations {limitations}, expected {expected_limitations}")

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
        c
        for c in claims
        if c["predicate"] not in ("DEPLOYED_AS", "USES_BROKER")
        and relation(c) not in ("CALLS", "PUBLISHES_TO")
    ]
    if unexpected:
        problems.append(f"unexpected claims: {[c.get('claim_id') for c in unexpected]}")
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
        problems.append(f"could not read the rest-fights dependencies answer: {exc}")
    if answer is not None:
        problems += check_answer(answer)
    if problems:
        print("The demo is NOT ready - the result differs from what the frozen evidence requires:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(json.dumps(answer, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
