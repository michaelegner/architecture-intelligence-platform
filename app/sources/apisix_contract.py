"""v0.7.0 I1.3: the APISIX capture envelope (`aip-apisix-capture/1`) shared by the separate capture
tool (`app.gateway_capture.apisix`, which writes it) and - from I1.4 - the replay adapter (which
validates it). Pure and dependency-free: no HTTP, no graph, no adapter. The shape and every rule
below are frozen by the I1.1 contract (`docs/specifications/0.7.0/i1-gateway-source-contract.md`
§2, §7) and the independent vectors in `i1-vectors/capture-rejections.json`.

Nothing here ever returns, logs or raises a source *value*: validation reports a stable code and,
at most, the JSON path of an offending field.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA_ID = "aip-apisix-capture/1"
ADMIN_SURFACE = "admin-api-etcd"
STANDALONE_SURFACE = "standalone-yaml"

# The eight resource kinds the I0 acquisition plan §2 reads. `credentials` are folded into
# `consumers[].credential_ids`; every other kind has its own array.
LIST_KINDS = (
    "consumers",
    "credentials",
    "routes",
    "services",
    "upstreams",
    "plugin_configs",
    "consumer_groups",
    "global_rules",
)

# Contract §4 / §4.1.
SUPPORTED_AUTH_PLUGINS = frozenset({"key-auth", "basic-auth", "jwt-auth", "hmac-auth", "ldap-auth"})
RECOGNIZED_UNSUPPORTED_AUTH_PLUGINS = frozenset(
    {
        "multi-auth",
        "openid-connect",
        "saml-auth",
        "wolf-rbac",
        "jwe-decrypt",
        "cas-auth",
        "dingtalk-auth",
        "feishu-auth",
        "ldap-auth-advanced",
    }
)

RESTRICTION_PLUGIN = "consumer-restriction"
# The only plugin configuration the fixture keeps (it is an access rule, not a secret); every other
# plugin is kept by name with an empty config (contract §2 redaction invariants).
RESTRICTION_CONFIG_KEYS = (
    "type",
    "whitelist",
    "blacklist",
    "allowed_by_methods",
    "rejected_code",
    "rejected_msg",
)

# Field names that may never appear in a redacted capture. Matched case-insensitively against every
# object key outside the free-form `labels` maps.
SECRET_KEY_NAMES = frozenset(
    {
        "key",
        "secret",
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "apikey",
        "api_key",
        "private_key",
        "client_secret",
        "hmac_secret",
        "secret_key",
        "authorization",
    }
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Plugins = dict[str, dict[str, Any]]


class _Provenanced(_Strict):
    """Per-object etcd revision provenance (I0 acquisition plan §2.3): the object's `createdIndex` /
    `modifiedIndex` as the Admin API reports them. Deterministic for unchanged state, unlike the
    volatile `create_time` / `update_time`, which are dropped. `None` only if the source omitted
    them; the capture tool always records what the Admin API returns."""

    created_index: int | None = Field(default=None, ge=0)
    modified_index: int | None = Field(default=None, ge=0)


class CaptureConsumer(_Provenanced):
    username: str = Field(min_length=1)
    credential_ids: list[str]


class CaptureRoute(_Provenanced):
    id: str = Field(min_length=1)
    uri: str | None = None
    uris: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    service_id: str | None = None
    plugin_config_id: str | None = None
    upstream_id: str | None = None
    upstream_nodes: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    plugins: Plugins


class CaptureService(_Provenanced):
    id: str = Field(min_length=1)
    upstream_id: str | None = None
    upstream_nodes: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    plugins: Plugins


class CaptureUpstream(_Provenanced):
    id: str = Field(min_length=1)
    nodes: list[str] = Field(default_factory=list)


class CapturePluginBundle(_Provenanced):
    """A `plugin_configs`, `consumer_groups` or `global_rules` entry: only its id and plugins."""

    id: str = Field(min_length=1)
    plugins: Plugins


class ApisixCaptureEnvelope(_Strict):
    schema_: str = Field(alias="schema")
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    apisix_version: str = Field(min_length=1)
    admin_surface: str
    etcd_revision_before: int = Field(ge=0)
    etcd_revision_after: int = Field(ge=0)
    lists_complete: dict[str, bool]
    consumers: list[CaptureConsumer]
    routes: list[CaptureRoute]
    services: list[CaptureService]
    upstreams: list[CaptureUpstream]
    plugin_configs: list[CapturePluginBundle]
    consumer_groups: list[CapturePluginBundle]
    global_rules: list[CapturePluginBundle]

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @property
    def source_revision(self) -> str:
        """Contract §2: `apisix:<apisix_version>+etcd:<etcd_revision_after>`."""
        return source_revision(self.apisix_version, self.etcd_revision_after)


def source_revision(apisix_version: str, etcd_revision: int) -> str:
    return f"apisix:{apisix_version}+etcd:{etcd_revision}"


@dataclass(frozen=True)
class CaptureProblem:
    """A stable rejection: the code and I1.1 contract §7 result, never a source value."""

    code: str
    result: str  # REJECTED_INVALID | REJECTED_UNSUPPORTED
    subject: str | None = None  # a JSON path, never a value


def unredacted_secret_paths(document: object) -> list[str]:
    """JSON paths (never values) of anything a redacted capture must not contain: a secret-named
    field, or a plugin configuration other than the `consumer-restriction` allow-list."""
    found: list[str] = []

    def walk(node: object, path: str, *, in_plugins: bool) -> None:
        if isinstance(node, Mapping):
            for name, child in node.items():
                child_path = f"{path}/{name}"
                if str(name).lower() in SECRET_KEY_NAMES:
                    found.append(child_path)
                    continue
                if name == "labels":
                    continue  # free-form operator metadata, not credential material
                if in_plugins:
                    if child and name != RESTRICTION_PLUGIN:
                        found.append(child_path)  # a retained plugin config other than the rule
                    elif name == RESTRICTION_PLUGIN:
                        walk(child, child_path, in_plugins=False)
                    continue
                walk(child, child_path, in_plugins=(name == "plugins"))
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}/{index}", in_plugins=False)

    walk(document, "", in_plugins=False)
    return sorted(set(found))


def validate_capture_document(document: object) -> CaptureProblem | None:
    """The contract §2/§7 checks, in the order the I1.1 vectors R01-R08 require: schema, surface,
    unredacted secrets, structure, revision fence, list completeness. `None` means acceptable."""
    if not isinstance(document, Mapping):
        return CaptureProblem("GW_CAPTURE_INVALID", "REJECTED_INVALID")
    if document.get("schema") != SCHEMA_ID:
        if "schema" not in document:
            return CaptureProblem("GW_CAPTURE_INVALID", "REJECTED_INVALID", "/schema")
        return CaptureProblem("GW_CAPTURE_SCHEMA_UNSUPPORTED", "REJECTED_UNSUPPORTED", "/schema")
    if document.get("admin_surface") != ADMIN_SURFACE:
        return CaptureProblem(
            "GW_CAPTURE_SURFACE_UNSUPPORTED", "REJECTED_UNSUPPORTED", "/admin_surface"
        )
    secret_paths = unredacted_secret_paths(document)
    if secret_paths:
        return CaptureProblem("GW_CAPTURE_UNREDACTED", "REJECTED_INVALID", secret_paths[0])
    try:
        envelope = ApisixCaptureEnvelope.model_validate(document)
    except ValidationError as exc:
        first = exc.errors(include_input=False, include_url=False)[0]
        pointer = "/" + "/".join(str(part) for part in first["loc"])
        return CaptureProblem("GW_CAPTURE_INVALID", "REJECTED_INVALID", pointer)
    if envelope.etcd_revision_before != envelope.etcd_revision_after:
        return CaptureProblem("GW_CAPTURE_INCONSISTENT", "REJECTED_INVALID", "/etcd_revision_after")
    if set(envelope.lists_complete) != set(LIST_KINDS):
        return CaptureProblem("GW_CAPTURE_INVALID", "REJECTED_INVALID", "/lists_complete")
    for kind in LIST_KINDS:
        if envelope.lists_complete[kind] is not True:
            return CaptureProblem(
                "GW_CAPTURE_INCOMPLETE", "REJECTED_INVALID", f"/lists_complete/{kind}"
            )
    return None
