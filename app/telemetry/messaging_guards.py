"""AIP v0.4.1 I2 - the messaging destination and service-identity safety guards
(docs/specifications/0.4.1/i2-messaging-semantic-guards.md, ADR 0013).

Pure, dependency-free - no `neo4j`/FastAPI/MCP/LLM imports (spec §7/§23). Both guard functions are
evaluated by `app.telemetry.adapter.correlate_queue_observations` before any entity, Evidence, or
`SENDS`/`RECEIVES_FROM` fact is recorded for a messaging span (spec §6/§18/§22). This module is
scoped to the messaging path only - `app.telemetry.service_resolver.resolve_service` (used by the
HTTP path) is untouched (spec §14).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.canonical import ids
from app.telemetry.model import DiscoveryStatus
from app.telemetry.queue_resolver import DeclaredQueueCandidate
from app.telemetry.service_resolver import DeclaredServiceCandidate, _slugify

UNSUPPORTED_DESTINATION_SEMANTICS = "unsupported_destination_semantics"
UNRESOLVED_DESTINATION_SEMANTICS = "unresolved_destination_semantics"
AMBIGUOUS_DESTINATION_IDENTITY = "ambiguous_destination_identity"

PLACEHOLDER_SERVICE_IDENTITY = "placeholder_service_identity"
AMBIGUOUS_SERVICE_IDENTITY = "ambiguous_service_identity"
CONFLICTING_SERVICE_IDENTITY = "conflicting_service_identity"

# Spec §9.4-9.6: the only destination-kind value that supplies positive Queue-compatible evidence,
# and the values that explicitly refuse it. Anything else (absent, empty, unrecognized) is neither.
_QUEUE_COMPATIBLE_KIND = "queue"
_UNSUPPORTED_KINDS = frozenset(
    {"topic", "subscription", "pubsub", "publish-subscribe", "fanout", "broadcast"}
)

# Spec §15: the reserved placeholder family, checked after normalization (strip, casefold, collapse
# whitespace/underscore runs to '-', collapse repeated hyphens). The prefix additionally closes the
# real OpenTelemetry SDK fallback format `unknown_service:<executable>` without an application-name
# denylist.
_RESERVED_SERVICE_IDENTITIES = frozenset({"unknown", "unknown-service", "unknownservice"})
_RESERVED_SERVICE_IDENTITY_PREFIX = "unknown-service:"
_WHITESPACE_OR_UNDERSCORE_RUN = re.compile(r"[ _]+")
_REPEATED_HYPHENS = re.compile(r"-+")


@dataclass(frozen=True)
class DestinationDecision:
    """Spec §7's guard outcome contract. `accepted=False` carries a stable `refusal_reason` and no
    usable `queue_id`; `accepted=True` carries `discovery_status` (DECLARED or OBSERVED_ONLY) and a
    deterministic `queue_id`."""

    accepted: bool
    discovery_status: DiscoveryStatus | None = None
    queue_id: str | None = None
    refusal_reason: str | None = None


@dataclass(frozen=True)
class ServiceDecision:
    """Spec §7's guard outcome contract, service-identity side."""

    accepted: bool
    discovery_status: DiscoveryStatus | None = None
    service_id: str | None = None
    refusal_reason: str | None = None


def _classify_destination_kind(raw: object) -> str:
    """Spec §9. Returns "queue", "unsupported", "malformed", or "absent". A present-but-empty or
    present-but-unrecognized value is "malformed" (spec §11 row 2: refused regardless of declared
    match), distinct from "absent" (spec §11 rows 6-8: refusal depends on declared-match outcome)."""
    if raw is None:
        return "absent"
    if not isinstance(raw, str):
        return "malformed"
    normalized = raw.strip().lower()
    if not normalized:
        return "malformed"
    if normalized == _QUEUE_COMPATIBLE_KIND:
        return "queue"
    if normalized in _UNSUPPORTED_KINDS:
        return "unsupported"
    return "malformed"


def _match_declared_queue(
    candidates: list[DeclaredQueueCandidate],
    *,
    messaging_system: str | None,
    destination_name: str,
    aliases: dict[str, str],
) -> tuple[str, str | None]:
    """Spec §10's 5-step precedence. Returns ("declared", id) | ("none", None) | ("ambiguous", None).
    A same-name declared candidate whose namespace conflicts with a present `messaging_system`
    (both non-null, unequal) is "ambiguous", not silently skipped - a bare-name fallback MUST NOT
    merge across that conflict (spec §10)."""
    name_matches = [c for c in candidates if c.name == destination_name]
    conflict_detected = False

    if messaging_system is not None:
        tier1 = [c for c in name_matches if c.namespace == messaging_system]
        if tier1:
            distinct_ids = {c.id for c in tier1}
            if len(distinct_ids) == 1:
                return "declared", tier1[0].id
            return "ambiguous", None
        conflicting = [
            c for c in name_matches if c.namespace is not None and c.namespace != messaging_system
        ]
        conflict_detected = bool(conflicting)
        eligible = [c for c in name_matches if c.namespace is None]
    else:
        eligible = [c for c in name_matches if c.namespace is None]

    if eligible:
        distinct_ids = {c.id for c in eligible}
        if len(distinct_ids) == 1 and not conflict_detected:
            return "declared", eligible[0].id
        return "ambiguous", None

    if destination_name in aliases:
        target = aliases[destination_name]
        if any(c.id == target for c in candidates):
            return "declared", target
        return "ambiguous", None

    return ("ambiguous", None) if conflict_detected else ("none", None)


def decide_destination_semantics(
    candidates: list[DeclaredQueueCandidate],
    *,
    messaging_system: str | None,
    destination_name: str,
    destination_kind: object,
    aliases: dict[str, str],
) -> DestinationDecision:
    """Spec §11's decision table, in order. The destination-kind classification is decided before
    any declared-candidate matching runs, since an unsupported or malformed kind refuses regardless
    of what would otherwise match (spec §11 rows 1-2)."""
    kind_state = _classify_destination_kind(destination_kind)
    if kind_state == "unsupported":
        return DestinationDecision(accepted=False, refusal_reason=UNSUPPORTED_DESTINATION_SEMANTICS)
    if kind_state == "malformed":
        return DestinationDecision(accepted=False, refusal_reason=UNRESOLVED_DESTINATION_SEMANTICS)

    match_kind, matched_id = _match_declared_queue(
        candidates,
        messaging_system=messaging_system,
        destination_name=destination_name,
        aliases=aliases,
    )
    if match_kind == "declared":
        return DestinationDecision(
            accepted=True, discovery_status=DiscoveryStatus.DECLARED, queue_id=matched_id
        )
    if match_kind == "ambiguous":
        return DestinationDecision(accepted=False, refusal_reason=AMBIGUOUS_DESTINATION_IDENTITY)

    # match_kind == "none": no declared candidate applies. Only explicit kind == "queue" evidence
    # may authorize a new observed-only Queue (spec §11 row 4); an absent kind never does (row 7).
    if kind_state == "queue":
        minted_id = ids.queue_id(destination_name, namespace=messaging_system)
        return DestinationDecision(
            accepted=True, discovery_status=DiscoveryStatus.OBSERVED_ONLY, queue_id=minted_id
        )
    return DestinationDecision(accepted=False, refusal_reason=UNRESOLVED_DESTINATION_SEMANTICS)


def _normalize_for_placeholder_check(name: str) -> str:
    """Spec §15: strip surrounding whitespace, case-fold, replace runs of spaces/underscores with
    '-', collapse repeated hyphens."""
    folded = name.strip().casefold()
    folded = _WHITESPACE_OR_UNDERSCORE_RUN.sub("-", folded)
    return _REPEATED_HYPHENS.sub("-", folded)


def _is_placeholder_identity(name: str) -> bool:
    normalized = _normalize_for_placeholder_check(name)
    return normalized in _RESERVED_SERVICE_IDENTITIES or normalized.startswith(
        _RESERVED_SERVICE_IDENTITY_PREFIX
    )


def _match_declared_service(
    candidates: list[DeclaredServiceCandidate],
    *,
    service_name: str,
    service_namespace: str | None,
    aliases: dict[str, str],
) -> tuple[str, str | None]:
    """Spec §14's precedence. Returns ("declared", id) | ("none", None) | ("ambiguous", None) |
    ("conflicting", None). A runtime namespace and a different non-null declared namespace conflict
    outright - the messaging path MUST NOT fall through to a namespace-agnostic name match in that
    case (spec §14)."""
    name_matches = [c for c in candidates if c.name == service_name]

    if service_namespace is not None:
        tier1 = [c for c in name_matches if c.namespace == service_namespace]
        if tier1:
            distinct_ids = {c.id for c in tier1}
            if len(distinct_ids) == 1:
                return "declared", tier1[0].id
            return "ambiguous", None
        conflicting = [
            c for c in name_matches if c.namespace is not None and c.namespace != service_namespace
        ]
        if conflicting:
            return "conflicting", None
        eligible = [c for c in name_matches if c.namespace is None]
    else:
        eligible = name_matches

    if eligible:
        distinct_ids = {c.id for c in eligible}
        if len(distinct_ids) == 1:
            return "declared", eligible[0].id
        return "ambiguous", None

    if service_name in aliases:
        target = aliases[service_name]
        if any(c.id == target for c in candidates):
            return "declared", target
        return "ambiguous", None

    return "none", None


def decide_service_identity(
    candidates: list[DeclaredServiceCandidate],
    *,
    service_name: str,
    service_namespace: str | None,
    aliases: dict[str, str],
) -> ServiceDecision:
    """Spec §14-§16 composed. `service.instance.id` is deliberately not a parameter here - it never
    participates in canonical Service identity (spec §13), matching the shared resolver's existing
    contract."""
    match_kind, matched_id = _match_declared_service(
        candidates,
        service_name=service_name,
        service_namespace=service_namespace,
        aliases=aliases,
    )
    if match_kind == "declared":
        return ServiceDecision(
            accepted=True, discovery_status=DiscoveryStatus.DECLARED, service_id=matched_id
        )
    if match_kind == "ambiguous":
        return ServiceDecision(accepted=False, refusal_reason=AMBIGUOUS_SERVICE_IDENTITY)
    if match_kind == "conflicting":
        return ServiceDecision(accepted=False, refusal_reason=CONFLICTING_SERVICE_IDENTITY)

    # match_kind == "none": no declared candidate applies. Spec §15's explicit observed-only
    # predicate decides whether the runtime identity is explicit enough to mint.
    stripped = service_name.strip()
    if not stripped:
        return ServiceDecision(accepted=False, refusal_reason=PLACEHOLDER_SERVICE_IDENTITY)
    slug = _slugify(stripped)
    if not slug:
        return ServiceDecision(accepted=False, refusal_reason=PLACEHOLDER_SERVICE_IDENTITY)
    if _is_placeholder_identity(stripped):
        return ServiceDecision(accepted=False, refusal_reason=PLACEHOLDER_SERVICE_IDENTITY)

    minted_id = ids.service_id(slug, namespace=service_namespace)
    return ServiceDecision(
        accepted=True, discovery_status=DiscoveryStatus.OBSERVED_ONLY, service_id=minted_id
    )
