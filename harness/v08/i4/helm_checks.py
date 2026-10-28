"""v0.8 I4 §7 (K7, owner review on the I4a plan): the applied configuration of Catalog and Image.

The operator records, in S1 (before) and S4 (after), each deployment (`kubectl get deployment -o
json`) and every ConfigMap it references (`kubectl get configmap -o json`):

    <dir>/<phase>/<deployment>.deployment.json
    <dir>/<phase>/configmap-<name>.json

The check passes when, for each deployment, the pod spec is unchanged (the replica count and the
rollout annotation are outside it), the referenced ConfigMaps are the same, exactly one of them changed, and that change is the I3 rule (`checker.check_configmap`): same name and
namespace, and the only changed line is kafka.brokers redpanda:29092 -> kafka:29092.
"""

import argparse
import json
import sys
from pathlib import Path

from _i3 import checker

DEPLOYMENTS = ("ecommerce-catalog-service", "ecommerce-image-service")


def configmap_refs(deployment: dict) -> list[str]:
    spec = deployment.get("spec", {}).get("template", {}).get("spec", {})
    names = {v["configMap"]["name"] for v in spec.get("volumes", []) if "configMap" in v}
    for container in spec.get("containers", []) + spec.get("initContainers", []):
        for source in container.get("envFrom", []):
            if "configMapRef" in source:
                names.add(source["configMapRef"]["name"])
        for env in container.get("env", []):
            ref = env.get("valueFrom", {}).get("configMapKeyRef")
            if ref:
                names.add(ref["name"])
    return sorted(names)


def check_deployment(root: Path, deployment: str) -> dict:
    problems: list[str] = []
    try:
        specs = {
            phase: json.loads((root / phase / f"{deployment}.deployment.json").read_text())
            for phase in ("before", "after")
        }
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "deployment": deployment,
            "problems": [f"unreadable deployment: {type(exc).__name__}"],
        }
    refs = {phase: configmap_refs(spec) for phase, spec in specs.items()}
    # "Only the bootstrap address": the pod spec itself (image, env, args, volumes) is unchanged.
    # The replica count and the restartedAt annotation of a rollout sit outside it.
    pods = {p: s.get("spec", {}).get("template", {}).get("spec", {}) for p, s in specs.items()}
    if pods["before"] != pods["after"]:
        problems.append("the pod spec changed (image, env, args or volumes)")
    if refs["before"] != refs["after"]:
        problems.append(f"the referenced ConfigMaps changed: {refs['before']} -> {refs['after']}")
    changed = []
    for name in refs["before"]:
        before = root / "before" / f"configmap-{name}.json"
        after = root / "after" / f"configmap-{name}.json"
        try:
            old, new = json.loads(before.read_text()), json.loads(after.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{name}: unreadable ConfigMap ({type(exc).__name__})")
            continue
        if old.get("data") == new.get("data"):
            continue
        verdict = checker.check_configmap(before, after)
        changed.append(name)
        problems += [f"{name}: {p}" for p in verdict["problems"]]
    if len(changed) != 1:
        problems.append(f"expected exactly one changed ConfigMap, found {changed}")
    return {
        "deployment": deployment,
        "configmaps": refs["before"],
        "changed": changed,
        "problems": problems,
    }


def check(root: Path) -> dict:
    results = [check_deployment(root, d) for d in DEPLOYMENTS]
    problems = [f"{r['deployment']}: {p}" for r in results for p in r["problems"]]
    return checker.verdict(
        "applied-helm",
        "per moved service: same ConfigMaps; the only change is kafka.brokers -> kafka:29092",
        checker.FAILED if problems else checker.PASSED,
        [str(root)],
        deployments=results,
        problems=problems,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = check(args.root)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"applied-helm: {result['result']}")
    return checker.EXIT[result["result"]]


if __name__ == "__main__":
    sys.exit(main())
