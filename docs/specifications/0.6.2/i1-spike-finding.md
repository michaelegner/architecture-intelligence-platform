# v0.6.2 I1 — G1–G5 spike finding

**Status:** Result of the spike specified in [`specification.md`](specification.md) §3.2 (Draft, 2026-10-07).
**Baseline:** v0.6.1 (`main` at `68ea59d`), real Neo4j, no `app/` change.
**Evidence:** [`tests/integration/test_v062_i1_gate_spike.py`](../../../tests/integration/test_v062_i1_gate_spike.py) (31 characterization tests; fixtures under
`tests/fixtures/pitstop_spike/overlay/`). Planning started 2026-10-07T09:15:52Z.

The tests freeze what v0.6.1 *actually does* for the Pitstop-shaped world (nine AsyncAPI 2.6.0 overlays: four publishers and
five subscribers of one fanout exchange `Pitstop` on `rabbitmq:pitstop-rabbitmq`, each subscriber naming its queue; runtime
evidence injected through the same adapter/aggregator the `/v1/traces` endpoint uses, plus one real-endpoint test). A gate that
ends with limits is a green test proving the limit, not a red suite. Verdicts:

| Gate | Verdict | One line |
|---|---|---|
| G1 | PASS-WITH-LIMITS | the topology declares as intended; one invalid overlay file rejects the whole import |
| G2 | PASS-WITH-LIMITS | receivers are answerable from a **publisher** only; no receiver-side question exists |
| G3 | PASS | no claim has an event dimension; "per Topic" holds by construction |
| G4 | PASS-WITH-LIMITS | publisher qualification works; no per-Subscription qualification; a cross-queue name re-routes a claim |
| G5 | PASS-WITH-LIMITS, **affects the Live promise** | caller-chosen windows work; claims of a completed window are not stable under later receiver traffic; `snapshot_id` moves with every span |

## G1 — Topic and named Subscriptions (PASS-WITH-LIMITS)

Confirmed: the nine overlays import with no diagnostics into one Topic `Pitstop`, one Broker, five Subscriptions
(`Auditlog`, `Invoicing`, `Notifications`, `Reporting`, `WorkshopManagement`), nine deduplicated `USES_BROKER`, four `PUBLISHES_TO`,
five `RECEIVES_FROM` (each through a `SUBSCRIPTION_OF` Subscription; none to the Topic directly). A document needs no payload or
message.

Limits (each a test):

- A publisher without `x-aip-broker-id` is `REJECTED_UNSUPPORTED` (`AMBIGUOUS`) **and the import commits nothing** (`committed=False`,
  zero nodes): all nine overlays are one source set. For a hosted demo, one bad overlay edit empties the declared topology.
- A subscriber without `x-aip-subscription-name` gets no Subscription (`SUBSCRIPTION_IDENTITY_MISSING`); its claim disappears.
- An AMQP `virtualHost` on one publisher's server splits the exchange into two Topics (namespace is part of Topic identity).

## G2 — Receivers in the existing answer (PASS-WITH-LIMITS)

Confirmed: `get_service_dependencies(WorkshopManagementAPI)` returns five `RESOLVED_SERVICE` claims, each with
`delivery.via = Pitstop` and `delivery.subscription` = its queue, plus one Broker claim; the answer validates against the v0.6
schema, and every `evidence_refs` entry resolves through `get_evidence` at the answer's own snapshot (no missing refs).
Qualification before runtime evidence: `NOT_OBSERVED_IN_WINDOW`.

Limits:

- **The spec's G2 fallback does not exist.** A consumer's own answer (e.g. `ReportingService`) has no receiver claim, only its
  Broker claim; there is no Topic- or Subscription-centric question. Receivers are reachable only by asking a *declared publisher*.
  With no publisher declared, none of the five receivers is reachable from any service.
- The demo question "which services receive from the destination this service publishes to" is therefore answerable only as
  "ask the publisher".

## G3 — Several event types on one Topic (PASS)

Two header-distinguished messages (`oneOf`) on the publisher's channel produce two `CARRIES` edges but change no claim: the claim
set is identical up to content-hash ids/refs, and no event name appears anywhere in the answer. Consumers are per Topic, not per
event type; that statement must come from demo text, since the answer does not say it.

## G4 — Runtime evidence (PASS-WITH-LIMITS)

**(A) Publisher qualification — works as the spec hopes, with conditions.** One `send` span from the declared publisher flips all
five claims to `CONFIRMED`. Required: `messaging.operation.type` (a legacy `messaging.operation` or an empty value is silently
ignored), `deployment.environment.name`, an exact `messaging.destination.name` (`pitstop` ≠ `Pitstop`), and the right
environment. Observed behaviors worth knowing:

- `service.name` must equal the overlay's `info.title`. A different string (`workshopmanagementapi`) is **not dropped**: it mints a
  second, observed-only Service (10 Services) and leaves the declared publisher's claims `NOT_OBSERVED_IN_WINDOW`.
- `messaging.system` is not a requirement here (compared only against a declared namespace; the overlay has none).
- The real `/v1/traces` endpoint applies the same rules to the fork-facing attribute set (send + process with subscription name).
- Runtime evidence never mints a Topic or Subscription (unknown destination/queue names are unresolved).

**(B) Receiver-route evidence — attaches, but is not qualification.** The declared overlay alone already resolves each consumer
(`SUBSCRIPTION_OF` + `RECEIVES_FROM`, one declared resolution ref). A matching `process` span (correct
`messaging.destination.subscription.name`) adds one `OBSERVED` ref to that route's `resolution_evidence_refs` (1 → 2), visible
through `get_evidence`, and changes no claim's qualification. A missing, mismatched (`reporting`) or consumer-group-only name adds
no evidence and leaves every claim as it was.

**Central finding:** v0.6.1 can observe an individual Subscription route but has **no per-Subscription qualification**. With a
publisher span and receive spans for four of five queues (Auditlog never observed), all five claims read `CONFIRMED`; only the
count of resolution refs differs. The spec's Q4 ("qualification per Subscription") is not what v0.6.1 returns.

**Defect-like limit:** a consumer span naming *another declared* queue is accepted. `ReportingService` receiving with
`subscription.name = Auditlog` creates an observed-only `RECEIVES_FROM` (Reporting → Auditlog queue) that was never declared, and
the Reporting claim is then **re-routed through Auditlog's Subscription** with its declared `Reporting` route gone from the claim
and no limitation raised. This needs a product decision; it is out of scope for the spike.

## G5 — Windows and a stable answer for a completed window (PASS-WITH-LIMITS, affects the Live promise)

Confirmed / corrects the spec:

- Windows are caller-chosen (explicit UTC offset, start ≤ end, ≤ 31 days). Messaging qualifies identically in a whole day and a
  two-minute window, and a window without traffic reads `NOT_OBSERVED_IN_WINDOW`. The spec's "whole UTC day" statement for
  messaging is not a v0.6.1 rule for `get_service_dependencies`.
- Re-importing and re-ingesting the same input reproduces the complete claim set **and** the `snapshot_id` exactly.
- Later *publisher* traffic (next day) leaves the completed window's complete claim set unchanged.

Limits:

- Later *receiver* traffic changes the completed window's claim: a `process` span on 2026-10-07 adds an
  `evidence:otel:pitstop-spike:2026-10-07:…` ref to the 2026-10-06 window's `resolution_evidence_refs` (route evidence is not
  window-scoped). Qualification does not change, but the claim does.
- `snapshot_id` fingerprints live evidence: any ingested span changes it, and `get_evidence` at the previous snapshot is refused.
  Claims cite refs that are only resolvable at the current snapshot, so an agent must call `get_evidence` immediately after
  `get_service_dependencies`; on a continuously ingesting instance that sequence is a race.
- "Completed window" is not an AIP concept; the caller supplies the window.

## Stop point (spec §3.2 stop rule) and owner decision

The rule stops the release here: G4(B) and G5 are PASS-WITH-LIMITS and affect the Live promise. **Owner decision
(2026-10-07): separate product fix first** — neither accept-and-disclose nor replay-only. The stop rule stays active until
G4/G5 are rerun against the fix; no Pitstop `run.sh`, hosted mode or §4.4 freeze before then.

- **G4 is a semantic-safety defect:** runtime evidence must not silently reassign a consumer to another declared
  Subscription. The fix establishes the guard for when an observed `RECEIVES_FROM` may support or create a
  Service → Subscription relation.
- **G5 is an observation-context defect:** a completed window's answer must not gain receiver evidence from a later window
  (`resolution_evidence_refs` are not filtered by the requested window).
- **Snapshot-id stability is not a required fix.** A snapshot changing when evidence is ingested, and stale-snapshot refusal,
  are intended. After the window leak is fixed, G5 is rerun and differing snapshot ids are re-judged as an expected provenance
  property; any residual question returns to the owner as a narrower decision.
- Accepted as spec corrections, not product blockers: G1 (atomic rejection of an invalid overlay set is desirable for controlled
  demo overlays), G2 (the question ladder is publisher-centric), G3, and the `service.name` mismatch (document and guard it in
  the demo instrumentation; widen the fix only if it causes a false answer in the Pitstop scenario).

Sequence: (1) this PR only (finding + characterization tests); (2) amend the v0.6.2 spec from these findings, esp. G2/G4/G5;
(3) a small separate product-hardening change for receiver/Subscription relation safety and window filtering of resolution
evidence; (4) rerun the G4/G5 tests against it; (5) only then the demo implementation.

## Proposed spec amendments (not applied)

1. §3.2 G2: remove the "consumer set shown through the other services' answers" fallback; state receivers are reachable only
   through a declared publisher.
2. §5 Q3/Q4: "qualification per Subscription" → publisher-driven qualification plus per-route evidence.
3. §2/§3.2/§4.3: "whole UTC day" → caller-chosen window (≤ 31 days); define what "last completed window" means operationally.
4. §4.1: overlay `info.title` must equal the OTel `service.name`; all nine overlays must carry the same `x-aip-broker-id` and
   channel name, no `virtualHost`, one `subscribe` with `x-aip-subscription-name` per consumer.
5. §4.2: required span attributes: `messaging.operation.type`, `messaging.destination.name`, `deployment.environment.name`,
   `service.name`, and (consumers) `messaging.destination.subscription.name`; the legacy `messaging.operation` is ignored.
6. §4.3: a single invalid overlay file rejects the whole import; the demo's import step must treat that as a hard failure.
7. §5/§6: the snapshot-stability and cross-queue findings above, per the owner's chosen option.

## For later increments (recorded, out of scope here)

`examples/pitstop-demo/` overlay files must stay at depth ≥ 5 and no top-level demo file may use a discoverer
(`CANDIDATE_FILENAMES`) name, as `tests/unit/test_release_golden_path_profile.py` enforces for Quarkus; `run.sh` joins the CI
shellcheck line in `.github/workflows/ci.yml`; a Pitstop smoke test needs its own Compose project name and cannot share
ports 8000/4318 with the Quarkus one; whether the new files are pinned in `examples/release-golden-path/SHA256SUMS` is open.
