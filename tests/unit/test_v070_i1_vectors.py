"""v0.7.0 I1.1: the hand-authored vectors in docs/specifications/0.7.0/i1-vectors/ are internally
consistent with the frozen contract (docs/specifications/0.7.0/i1-gateway-source-contract.md).

Deliberately imports nothing from `app`: the id formulas and the ConfiguredAccess interpretation are
re-implemented here from the contract text, so a later production adapter is checked against vectors
that did not come from it (I1 spec §5: "expected results should be authored independently").
"""

import hashlib
import json
from pathlib import Path

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i1-vectors"

AUTH_PLUGINS = {"key-auth", "basic-auth", "jwt-auth", "hmac-auth", "ldap-auth"}
RULE_KIND = "CONSUMER_RESTRICTION_ALLOW_LIST"


def _ld(*parts: str) -> bytes:
    out = b""
    for part in parts:
        raw = part.encode("utf-8")
        out += len(raw).to_bytes(8, "big") + raw
    return out


def _h(*parts: str) -> str:
    return hashlib.sha256(_ld(*parts)).hexdigest()


def _load(name: str) -> dict:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def test_id_vectors_match_the_frozen_formulas() -> None:
    by_id = {v["id"]: v for v in _load("ids.json")["vectors"]}
    inst = "gw-prod-1"
    i = by_id["V01"]["inputs"]
    assert by_id["V01"]["expected"] == "gateway-consumer:owned:" + _h(
        i["gateway_instance_id"], i["username"]
    )
    assert by_id["V02"]["expected"] != by_id["V01"]["expected"]
    assert by_id["V03"]["expected"] == "gateway-route:owned:" + _h(inst, "orders-route")
    assert by_id["V04"]["expected"] == "gateway-service:owned:" + _h(inst, "orders")
    v5 = by_id["V05"]["expected"]
    assert v5["route"] != v5["service"]
    assert by_id["V07"]["expected"] == "urn:aip:source:apisix:" + _h("apisix-prod", inst)
    contract = "api-contract:owned:" + _h("urn:aip:source:filesystem:abc123")
    assert by_id["V08"]["expected"] == contract
    assert by_id["V09"]["expected"] == "api-contract-version:owned:" + _h(contract, "1.4.0")
    assert (
        by_id["V10"]["expected"]
        == by_id["V11"]["expected"]
        == "api-contract-version:owned:" + _h(contract, "")
    )
    assert by_id["V12"]["expected"]["a"] != by_id["V12"]["expected"]["b"]
    for vector in by_id.values():
        assert vector["formula"]


def _interpret(capture: dict) -> dict:
    """Reference reading of contract §4, applied to one case's capture fragment."""
    consumers = {c["username"] for c in capture["consumers"]}
    access: list[dict] = []
    limitations: list[dict] = []

    def limit(code: str, subject: str) -> None:
        limitations.append({"code": code, "subject": subject})

    for scope, kind in (
        ("services", "service"),
        ("plugin_configs", "plugin_config"),
        ("global_rules", "global_rule"),
    ):
        for obj in capture.get(scope, []):
            if "consumer-restriction" in obj["plugins"]:
                limit("GW_RESTRICTION_UNSUPPORTED_SCOPE", f"{kind}:{obj['id']}")
    for route in capture["routes"]:
        cfg = route["plugins"].get("consumer-restriction")
        if cfg is None:
            continue
        rid = route["id"]
        if cfg.get("type", "consumer_name") != "consumer_name":
            limit("GW_RESTRICTION_UNSUPPORTED_TYPE", rid)
            continue
        if "allowed_by_methods" in cfg:
            limit("GW_RESTRICTION_METHOD_SCOPED", rid)
            continue
        if not AUTH_PLUGINS & set(route["plugins"]):
            limit("GW_RESTRICTION_NO_AUTH_PLUGIN", rid)
            continue
        whitelist, blacklist = cfg.get("whitelist", []), cfg.get("blacklist", [])
        if not whitelist:
            if blacklist:
                limit("GW_BLACKLIST_RECORDED", rid)
            continue
        for name in whitelist:
            if name in blacklist:
                limit("GW_WHITELIST_BLACKLIST_CONFLICT", f"{rid}:{name}")
            elif name not in consumers:
                limit("GW_WHITELIST_DANGLING_CONSUMER", f"{rid}:{name}")
            else:
                access.append({"consumer": name, "route": rid, "rule_kind": RULE_KIND})
    key = lambda d: sorted(d.items())
    return {
        "configured_access": sorted(access, key=key),
        "limitations": sorted(limitations, key=key),
    }


def test_configured_access_cases_agree_with_the_reference_reading() -> None:
    doc = _load("configured-access.json")
    assert set(doc["frozen_auth_plugins"]) == AUTH_PLUGINS
    assert doc["base_capture"]["schema"] == "aip-apisix-capture/1"
    assert doc["base_capture"]["admin_surface"] == "admin-api-etcd"
    ids = [c["id"] for c in doc["cases"]]
    assert ids == sorted(set(ids)) == [f"C{n:02d}" for n in range(1, len(ids) + 1)]
    for case in doc["cases"]:
        got = _interpret(case["capture"])
        key = lambda d: sorted(d.items())
        expected = {
            "configured_access": sorted(case["expected"]["configured_access"], key=key),
            "limitations": sorted(case["expected"]["limitations"], key=key),
        }
        assert got == expected, case["id"]


def test_every_i1_section5_case_is_covered_by_a_vector() -> None:
    access_tags = {c["spec_case"] for c in _load("configured-access.json")["cases"]}
    assert access_tags >= {
        "whitelisted-consumer-positive", "type-default", "no-auth-plugin", "dangling-whitelist",
        "whitelist-blacklist-conflict", "blacklist-only", "method-restriction", "unsupported-scope",
        "no-enumerating-restriction", "unsupported-auth-plugin", "multi-consumer-multi-route",
    }  # fmt: skip
    rejections = _load("capture-rejections.json")["cases"]
    assert {c["spec_case"] for c in rejections} >= {
        "revision-change", "incomplete-list", "standalone-yaml", "schema-version",
        "instance-binding", "duplicate-instance", "unredacted-secret", "malformed",
    }  # fmt: skip
    results = {"REJECTED_INVALID", "REJECTED_UNSUPPORTED", "REJECTED_CONFLICT"}
    for case in rejections:
        assert case["expected"]["result"] in results
        assert case["expected"]["code"].startswith("GW_")
    canary = next(c for c in rejections if c["spec_case"] == "unredacted-secret")
    assert canary["expected"]["diagnostic_must_not_contain"] == ["CANARY-SECRET-VALUE"]
