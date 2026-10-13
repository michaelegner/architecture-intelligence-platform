"""v0.7.0 I1.3: the separate APISIX capture tool (I1 spec §3.2, I0 acquisition plan §2).

Reads the Admin API over etcd, fences the read with the etcd header revision before and after,
asserts every required list was read completely, redacts and normalizes in acquisition code, and
writes the `aip-apisix-capture/1` fixture. It never emits a source value in a log line, error or
diagnostic: the Admin API key is read from the environment and is never echoed, and every failure
is a fixed `CaptureError` code (I1.1 contract §2, §7).

`--etcd-url` MUST point at the etcd that backs the APISIX instance being captured: the etcd header
revision is the capture's fence and revision identity, and the Admin API exposes none.

    APISIX_ADMIN_KEY=... python -m app.gateway_capture.apisix \\
        --admin-url http://127.0.0.1:9180 --etcd-url http://127.0.0.1:2379 \\
        --gateway-instance-id gw-prod-1 --environment prod --apisix-version 3.19.0 \\
        --out apisix-capture.json
"""

import argparse
import base64
import http.client
import json
import os
import re
import sys
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.sources.apisix_contract import (
    ADMIN_SURFACE,
    LIST_KINDS,
    RESTRICTION_CONFIG_KEYS,
    RESTRICTION_PLUGIN,
    SCHEMA_ID,
    validate_capture_document,
)

ADMIN_KEY_ENV = "APISIX_ADMIN_KEY"
_ADMIN_PATHS = {
    "consumers": "consumers",
    "routes": "routes",
    "services": "services",
    "upstreams": "upstreams",
    "plugin_configs": "plugin_configs",
    "consumer_groups": "consumer_groups",
    "global_rules": "global_rules",
}
_VERSION_PATTERN = re.compile(r"APISIX/(\d+\.\d+\.\d+)")


def _split(url: str) -> tuple[str, str, int | None, str]:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise CaptureError("GW_CAPTURE_URL_UNSUPPORTED")
    return parts.scheme, parts.hostname, parts.port, parts.path.rstrip("/")


class CaptureError(Exception):
    """A capture refusal. `str(error)` is the fixed code only - never a source value, a URL with
    credentials, a response body or the Admin API key."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AdminList:
    items: list[dict[str, Any]]
    total: int | None


class AdminApi(Protocol):
    def etcd_revision(self) -> int: ...

    def list_resources(self, kind: str) -> AdminList: ...

    def list_credentials(self, username: str) -> AdminList: ...

    def server_version(self) -> str | None: ...


# --------------------------------------------------------------------------------------------
# Normalization and redaction (pure)
# --------------------------------------------------------------------------------------------


def _value(item: Mapping[str, Any]) -> Mapping[str, Any]:
    value = item.get("value")
    return value if isinstance(value, Mapping) else {}


def _resource_id(item: Mapping[str, Any]) -> str:
    value = _value(item)
    if isinstance(value.get("id"), str | int) and str(value["id"]):
        return str(value["id"])
    key = item.get("key")
    if isinstance(key, str) and key.rsplit("/", 1)[-1]:
        return key.rsplit("/", 1)[-1]
    raise CaptureError("GW_CAPTURE_MALFORMED_RESOURCE")


def _indices(item: Mapping[str, Any]) -> dict[str, int | None]:
    """The object's etcd `createdIndex` / `modifiedIndex` (I0 acquisition plan §2.3)."""
    created, modified = item.get("createdIndex"), item.get("modifiedIndex")
    return {
        "created_index": created
        if isinstance(created, int) and not isinstance(created, bool)
        else None,
        "modified_index": modified
        if isinstance(modified, int) and not isinstance(modified, bool)
        else None,
    }


def normalize_plugins(plugins: object) -> dict[str, dict[str, Any]]:
    """Contract §2: every plugin by name with an empty config, except `consumer-restriction`, which
    keeps only its allow-listed access-rule fields."""
    if not isinstance(plugins, Mapping):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for name in sorted(plugins):
        config = plugins[name]
        if name == RESTRICTION_PLUGIN and isinstance(config, Mapping):
            normalized[name] = {
                field: _sorted_rule_value(config[field])
                for field in RESTRICTION_CONFIG_KEYS
                if field in config
            }
        else:
            normalized[str(name)] = {}
    return normalized


def _sorted_rule_value(value: Any) -> Any:
    # whitelist/blacklist are unordered sets; allowed_by_methods keeps its source order shape but
    # sorted by user so the fixture is deterministic.
    if isinstance(value, list) and all(isinstance(entry, str) for entry in value):
        return sorted(value)
    if isinstance(value, list) and all(isinstance(entry, Mapping) for entry in value):
        return sorted(
            (
                {key: (sorted(v) if isinstance(v, list) else v) for key, v in sorted(entry.items())}
                for entry in value
            ),
            key=lambda entry: json.dumps(entry, sort_keys=True),
        )
    return value


def _upstream_nodes(value: Mapping[str, Any]) -> list[str]:
    upstream = value.get("upstream")
    nodes = upstream.get("nodes") if isinstance(upstream, Mapping) else value.get("nodes")
    if isinstance(nodes, Mapping):
        return sorted(str(node) for node in nodes)
    if isinstance(nodes, list):
        return sorted(
            f"{node.get('host')}:{node.get('port')}" for node in nodes if isinstance(node, Mapping)
        )
    return []


def _labels(value: Mapping[str, Any]) -> dict[str, str]:
    labels = value.get("labels")
    if not isinstance(labels, Mapping):
        return {}
    return {str(k): str(v) for k, v in sorted(labels.items())}


def _optional_id(value: Mapping[str, Any], field: str) -> str | None:
    found = value.get(field)
    return str(found) if found not in (None, "") else None


def normalize_route(item: Mapping[str, Any]) -> dict[str, Any]:
    value = _value(item)
    uris = value.get("uris")
    methods = value.get("methods")
    return {
        **_indices(item),
        "id": _resource_id(item),
        "uri": value.get("uri") if isinstance(value.get("uri"), str) else None,
        "uris": sorted(str(u) for u in uris) if isinstance(uris, list) else [],
        "methods": sorted(str(m) for m in methods) if isinstance(methods, list) else [],
        "service_id": _optional_id(value, "service_id"),
        "plugin_config_id": _optional_id(value, "plugin_config_id"),
        "upstream_id": _optional_id(value, "upstream_id"),
        "upstream_nodes": _upstream_nodes(value),
        "labels": _labels(value),
        "plugins": normalize_plugins(value.get("plugins")),
    }


def normalize_service(item: Mapping[str, Any]) -> dict[str, Any]:
    value = _value(item)
    return {
        **_indices(item),
        "id": _resource_id(item),
        "upstream_id": _optional_id(value, "upstream_id"),
        "upstream_nodes": _upstream_nodes(value),
        "labels": _labels(value),
        "plugins": normalize_plugins(value.get("plugins")),
    }


def normalize_upstream(item: Mapping[str, Any]) -> dict[str, Any]:
    return {**_indices(item), "id": _resource_id(item), "nodes": _upstream_nodes(_value(item))}


def normalize_bundle(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_indices(item),
        "id": _resource_id(item),
        "plugins": normalize_plugins(_value(item).get("plugins")),
    }


def _consumer_username(item: Mapping[str, Any]) -> str:
    username = _value(item).get("username")
    if not isinstance(username, str) or not username:
        raise CaptureError("GW_CAPTURE_MALFORMED_RESOURCE")
    return username


# --------------------------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------------------------


def _complete(listing: AdminList) -> bool:
    return listing.total is not None and listing.total == len(listing.items)


def capture(
    api: AdminApi, *, gateway_instance_id: str, environment: str, apisix_version: str
) -> dict[str, Any]:
    """One fenced capture. Raises `CaptureError` (a fixed code) rather than writing a fixture that
    the replay adapter would reject; the returned document is self-validated."""
    served_version = api.server_version()
    if served_version is not None and served_version != apisix_version:
        raise CaptureError("GW_CAPTURE_VERSION_MISMATCH")

    revision_before = api.etcd_revision()
    lists_complete: dict[str, bool] = {}
    listings: dict[str, AdminList] = {}
    for kind, path in _ADMIN_PATHS.items():
        listings[kind] = api.list_resources(path)
        lists_complete[kind] = _complete(listings[kind])

    consumers = sorted(
        (_consumer_username(item) for item in listings["consumers"].items),
    )
    credential_ids: dict[str, list[str]] = {}
    credentials_complete = True
    by_username = {_consumer_username(item): item for item in listings["consumers"].items}
    for username in consumers:
        credentials = api.list_credentials(username)
        credentials_complete = credentials_complete and _complete(credentials)
        credential_ids[username] = sorted(_resource_id(item) for item in credentials.items)
    lists_complete["credentials"] = credentials_complete
    revision_after = api.etcd_revision()

    document: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "gateway_instance_id": gateway_instance_id,
        "environment": environment,
        "apisix_version": apisix_version,
        "admin_surface": ADMIN_SURFACE,
        "etcd_revision_before": revision_before,
        "etcd_revision_after": revision_after,
        "lists_complete": {kind: lists_complete[kind] for kind in LIST_KINDS},
        "consumers": [
            {
                **_indices(by_username[name]),
                "username": name,
                "credential_ids": credential_ids[name],
            }
            for name in sorted(by_username)
        ],
        "routes": sorted(
            (normalize_route(i) for i in listings["routes"].items), key=lambda r: r["id"]
        ),
        "services": sorted(
            (normalize_service(i) for i in listings["services"].items), key=lambda s: s["id"]
        ),
        "upstreams": sorted(
            (normalize_upstream(i) for i in listings["upstreams"].items), key=lambda u: u["id"]
        ),
        "plugin_configs": sorted(
            (normalize_bundle(i) for i in listings["plugin_configs"].items), key=lambda b: b["id"]
        ),
        "consumer_groups": sorted(
            (normalize_bundle(i) for i in listings["consumer_groups"].items), key=lambda b: b["id"]
        ),
        "global_rules": sorted(
            (normalize_bundle(i) for i in listings["global_rules"].items), key=lambda b: b["id"]
        ),
    }
    problem = validate_capture_document(document)
    if problem is not None:
        raise CaptureError(problem.code)
    return document


def serialize(document: Mapping[str, Any]) -> bytes:
    """Deterministic bytes: sorted keys, two-space indent, trailing newline."""
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


# --------------------------------------------------------------------------------------------
# Real Admin API / etcd client (stdlib only - no runtime HTTP dependency)
# --------------------------------------------------------------------------------------------


def _is_key_not_found(body: bytes) -> bool:
    try:
        payload = json.loads(body)
    except ValueError:
        return False
    return isinstance(payload, dict) and payload.get("message") == "Key not found"


_MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class UrllibAdminApi:
    """The real Admin API / etcd client. Built on `http.client` with an explicit http/https scheme
    check (a configured URL can never name `file://` or another scheme)."""

    def __init__(self, *, admin_url: str, admin_key: str, etcd_url: str, timeout: float = 15.0):
        self._admin = _split(admin_url)
        self._etcd = _split(etcd_url)
        self._admin_key = admin_key
        self._timeout = timeout
        self._served: str | None = None

    def _request(
        self,
        target: tuple[str, str, int | None, str],
        path: str,
        *,
        body: bytes | None = None,
        admin: bool,
        empty_on_key_not_found: bool = False,
    ) -> tuple[bytes, str | None]:
        scheme, host, port, prefix = target
        headers = {"Accept": "application/json"}
        if admin:
            headers["X-API-KEY"] = self._admin_key
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection_class = (
            http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_class(host, port, timeout=self._timeout)
        try:
            connection.request("POST" if body is not None else "GET", prefix + path, body, headers)
            response = connection.getresponse()
            data = response.read(_MAX_RESPONSE_BYTES + 1)
            server = response.getheader("Server")
            status = response.status
        except (OSError, http.client.HTTPException):
            raise CaptureError("GW_CAPTURE_UNREACHABLE") from None
        finally:
            connection.close()
        if len(data) > _MAX_RESPONSE_BYTES:
            raise CaptureError("GW_CAPTURE_MALFORMED_RESPONSE")
        if status == 404:
            if empty_on_key_not_found and _is_key_not_found(data):
                return b'{"total":0,"list":[]}', None
            raise CaptureError("GW_CAPTURE_SURFACE_UNAVAILABLE")
        if status in (401, 403):
            raise CaptureError("GW_CAPTURE_ADMIN_AUTH_FAILED")
        if not 200 <= status < 300:
            raise CaptureError("GW_CAPTURE_ADMIN_REQUEST_FAILED")
        return data, server

    def etcd_revision(self) -> int:
        body = json.dumps({"key": base64.b64encode(b"\0").decode(), "limit": 1}).encode()
        raw, _ = self._request(self._etcd, "/v3/kv/range", body=body, admin=False)
        try:
            return int(json.loads(raw)["header"]["revision"])
        except (ValueError, KeyError, TypeError):
            raise CaptureError("GW_CAPTURE_ETCD_REVISION_UNAVAILABLE") from None

    def _list(self, path: str, *, empty_on_key_not_found: bool = False) -> AdminList:
        raw, server = self._request(
            self._admin,
            f"/apisix/admin/{path}",
            admin=True,
            empty_on_key_not_found=empty_on_key_not_found,
        )
        self._served = server
        try:
            payload = json.loads(raw)
            items = payload.get("list", [])
            total = payload.get("total")
            if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
                raise ValueError
            return AdminList(items=items, total=int(total) if total is not None else None)
        except (ValueError, KeyError, TypeError):
            raise CaptureError("GW_CAPTURE_MALFORMED_RESPONSE") from None

    def list_resources(self, kind: str) -> AdminList:
        return self._list(kind)

    def list_credentials(self, username: str) -> AdminList:
        # APISIX 3.19 answers 404 {"message": "Key not found"} - not an empty list - for a consumer
        # with no credentials (I1.3 finding). The consumer was just listed, and the etcd revision
        # fence catches one that vanished meanwhile, so that exact reply means "none".
        return self._list(
            f"consumers/{urllib.parse.quote(username, safe='')}/credentials",
            empty_on_key_not_found=True,
        )

    def server_version(self) -> str | None:
        match = _VERSION_PATTERN.search(self._served) if self._served else None
        return match.group(1) if match else None


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.gateway_capture.apisix",
        description="Capture a redacted, normalized APISIX configuration fixture "
        "(aip-apisix-capture/1). The Admin API key is read from $APISIX_ADMIN_KEY.",
    )
    parser.add_argument("--admin-url", required=True)
    parser.add_argument("--etcd-url", required=True)
    parser.add_argument("--gateway-instance-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--apisix-version", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    admin_key = os.environ.get(ADMIN_KEY_ENV)
    if not admin_key:
        print(f"refused: {ADMIN_KEY_ENV} is not set", file=sys.stderr)
        return 2
    api = UrllibAdminApi(admin_url=args.admin_url, admin_key=admin_key, etcd_url=args.etcd_url)
    try:
        document = capture(
            api,
            gateway_instance_id=args.gateway_instance_id,
            environment=args.environment,
            apisix_version=args.apisix_version,
        )
    except CaptureError as exc:
        print(f"refused: {exc.code}", file=sys.stderr)
        return 1
    args.out.write_bytes(serialize(document))
    print(
        f"captured: {args.out} ({document['apisix_version']}, etcd {document['etcd_revision_after']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
