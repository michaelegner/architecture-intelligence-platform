"""v0.7.0 I1.4: the pure interpretation of a validated `aip-apisix-capture/1` envelope into the
internal gateway carriers (I1.1 contract §3-§4). No I/O. The expected results are the independent
vectors `configured-access.json` C01-C15 and `ids.json`; nothing here reads a source value into a
message - limitation subjects are route/service/plugin_config/global_rule ids and inventory
usernames only.
"""

from dataclasses import dataclass

from app.canonical.gateway import (
    CONSUMER_RESTRICTION_ALLOW_LIST,
    GatewayConfiguredAccess,
    GatewayConsumer,
    GatewayLimitation,
    GatewayRoute,
    GatewayService,
    GatewaySourceEvidence,
    configured_access_id,
    gateway_consumer_id,
    gateway_limitation_id,
    gateway_route_id,
    gateway_service_id,
    gateway_source_evidence_id,
)
from app.common.jcs import canonical_json_bytes
from app.sources.apisix_contract import (
    RECOGNIZED_UNSUPPORTED_AUTH_PLUGINS,
    RESTRICTION_PLUGIN,
    SUPPORTED_AUTH_PLUGINS,
    ApisixCaptureEnvelope,
    CapturePluginBundle,
    CaptureRoute,
)

# Limitation codes (contract §4 table).
UNSUPPORTED_TYPE = "GW_RESTRICTION_UNSUPPORTED_TYPE"
NO_AUTH_PLUGIN = "GW_RESTRICTION_NO_AUTH_PLUGIN"
AUTH_PLUGIN_UNSUPPORTED = "GW_AUTH_PLUGIN_UNSUPPORTED"
DANGLING_CONSUMER = "GW_WHITELIST_DANGLING_CONSUMER"
WHITELIST_BLACKLIST_CONFLICT = "GW_WHITELIST_BLACKLIST_CONFLICT"
BLACKLIST_RECORDED = "GW_BLACKLIST_RECORDED"
METHOD_SCOPED = "GW_RESTRICTION_METHOD_SCOPED"
UNSUPPORTED_SCOPE = "GW_RESTRICTION_UNSUPPORTED_SCOPE"


@dataclass(frozen=True)
class GatewayMapping:
    source_evidence: GatewaySourceEvidence
    consumers: list[GatewayConsumer]
    routes: list[GatewayRoute]
    services: list[GatewayService]
    accesses: list[GatewayConfiguredAccess]
    limitations: list[GatewayLimitation]


def _labels_json(labels: dict[str, str]) -> str:
    return canonical_json_bytes(dict(sorted(labels.items()))).decode("utf-8")


def _scope_limitations(kind: str, bundles: list[CapturePluginBundle]) -> list[tuple[str, str]]:
    return [
        (UNSUPPORTED_SCOPE, f"{kind}:{bundle.id}")
        for bundle in bundles
        if RESTRICTION_PLUGIN in bundle.plugins
    ]


def _route_access(
    route: CaptureRoute, consumer_names: set[str]
) -> tuple[list[str], list[tuple[str, str]]]:
    """(whitelisted usernames that qualify, limitation (code, subject) pairs) for one route."""
    config = route.plugins.get(RESTRICTION_PLUGIN)
    if config is None:
        return [], []
    if config.get("type", "consumer_name") != "consumer_name":
        return [], [(UNSUPPORTED_TYPE, route.id)]
    if "allowed_by_methods" in config:
        return [], [(METHOD_SCOPED, route.id)]
    plugins = set(route.plugins)
    if not SUPPORTED_AUTH_PLUGINS & plugins:
        unsupported = sorted(RECOGNIZED_UNSUPPORTED_AUTH_PLUGINS & plugins)
        if unsupported:
            return [], [(AUTH_PLUGIN_UNSUPPORTED, f"{route.id}:{name}") for name in unsupported]
        return [], [(NO_AUTH_PLUGIN, route.id)]
    whitelist, blacklist = config.get("whitelist") or [], config.get("blacklist") or []
    if not whitelist:
        return [], ([(BLACKLIST_RECORDED, route.id)] if blacklist else [])
    allowed: list[str] = []
    limitations: list[tuple[str, str]] = []
    for name in whitelist:
        if name in blacklist:
            limitations.append((WHITELIST_BLACKLIST_CONFLICT, f"{route.id}:{name}"))
        elif name not in consumer_names:
            limitations.append((DANGLING_CONSUMER, f"{route.id}:{name}"))
        else:
            allowed.append(name)
    return allowed, limitations


def map_capture(envelope: ApisixCaptureEnvelope) -> GatewayMapping:
    instance = envelope.gateway_instance_id
    environment = envelope.environment
    revision = envelope.source_revision
    evidence = GatewaySourceEvidence(
        id=gateway_source_evidence_id(instance, revision),
        gateway_instance_id=instance,
        environment=environment,
        apisix_version=envelope.apisix_version,
        source_revision=revision,
    )

    consumers = [
        GatewayConsumer(
            id=gateway_consumer_id(instance, consumer.username),
            gateway_instance_id=instance,
            environment=environment,
            username=consumer.username,
            credential_ids=sorted(consumer.credential_ids),
            created_index=consumer.created_index,
            modified_index=consumer.modified_index,
        )
        for consumer in envelope.consumers
    ]
    routes = [
        GatewayRoute(
            id=gateway_route_id(instance, route.id),
            gateway_instance_id=instance,
            environment=environment,
            route_id=route.id,
            uri=route.uri,
            uris=sorted(route.uris),
            methods=sorted(route.methods),
            service_id=route.service_id,
            plugin_config_id=route.plugin_config_id,
            upstream_id=route.upstream_id,
            upstream_nodes=sorted(route.upstream_nodes),
            labels_json=_labels_json(route.labels),
            auth_plugins=sorted(
                (SUPPORTED_AUTH_PLUGINS | RECOGNIZED_UNSUPPORTED_AUTH_PLUGINS) & set(route.plugins)
            ),
            plugin_names=sorted(route.plugins),
            created_index=route.created_index,
            modified_index=route.modified_index,
        )
        for route in envelope.routes
    ]
    services = [
        GatewayService(
            id=gateway_service_id(instance, service.id),
            gateway_instance_id=instance,
            environment=environment,
            service_id=service.id,
            upstream_id=service.upstream_id,
            upstream_nodes=sorted(service.upstream_nodes),
            labels_json=_labels_json(service.labels),
            plugin_names=sorted(service.plugins),
            created_index=service.created_index,
            modified_index=service.modified_index,
        )
        for service in envelope.services
    ]

    consumer_names = {consumer.username for consumer in envelope.consumers}
    limitation_pairs: set[tuple[str, str]] = set()
    limitation_pairs.update(
        _scope_limitations(
            "service", [CapturePluginBundle(id=s.id, plugins=s.plugins) for s in envelope.services]
        )
    )
    limitation_pairs.update(_scope_limitations("plugin_config", envelope.plugin_configs))
    limitation_pairs.update(_scope_limitations("global_rule", envelope.global_rules))

    accesses: dict[str, GatewayConfiguredAccess] = {}
    for route in envelope.routes:
        allowed, limitations = _route_access(route, consumer_names)
        limitation_pairs.update(limitations)
        route_id = gateway_route_id(instance, route.id)
        for name in allowed:
            consumer_id = gateway_consumer_id(instance, name)
            access_id = configured_access_id(consumer_id, route_id, CONSUMER_RESTRICTION_ALLOW_LIST)
            accesses[access_id] = GatewayConfiguredAccess(
                id=access_id,
                consumer_id=consumer_id,
                route_id=route_id,
                evidence_ids=[evidence.id],
                source_revision=revision,
            )
    return GatewayMapping(
        source_evidence=evidence,
        consumers=sorted(consumers, key=lambda item: item.id),
        routes=sorted(routes, key=lambda item: item.id),
        services=sorted(services, key=lambda item: item.id),
        accesses=sorted(accesses.values(), key=lambda item: item.id),
        limitations=sorted(
            (
                GatewayLimitation(
                    id=gateway_limitation_id(instance, code, subject),
                    gateway_instance_id=instance,
                    code=code,
                    subject=subject,
                )
                for code, subject in limitation_pairs
            ),
            key=lambda item: item.id,
        ),
    )
