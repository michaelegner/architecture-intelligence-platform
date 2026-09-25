"""Slice 7: checks every frozen lifecycle/README.md expectation against the recorded step outputs.

    uv run python verify.py <record directory>

Committed as run evidence. The as-run file had sha256
5344f5960f914b407080015df1986204ea96e112bd45e736b874428d1517abff. The committed copy differs only in lint and formatting, with no behavior change
(its output on the same records is byte-identical to `verify.txt`):
- this docstring;
- the imports split one per line, and one unused import removed;
- `ruff format`;
- a file-level B023 exemption. The per-target lambdas are defined and called within the same loop
  iteration, so the late binding B023 warns about cannot occur.
"""

# ruff: noqa: B023
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path("/home/michael/code/ArchitectureIntelligencePlatform")
LC = ROOT / "docs/real-world-validation/v0.5.0/lifecycle"
REC = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "tests/unit"))
spec = importlib.util.spec_from_file_location("m", LC / "mutate.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from test_i5_lifecycle_freeze import PINNED

Q = ["Q-INV", "Q-SRC", "Q-SRC-SEM", "Q-OWN", "Q-SVC", "Q-REL"]
fails = []


def check(target, step, cond, what):
    print(f"  {'ok  ' if cond else 'FAIL'} {step:4} {what}")
    if not cond:
        fails.append((target, step, what))


for target in ["apache-airflow", "quarkus-super-heroes"]:
    print(f"== {target}")
    sc = m.load_scenario(target)
    x = m.x_source_instance_id(sc)
    d = lambda st: REC / target / st
    txt = lambda st, q: (d(st) / f"{q}.txt").read_text()
    imp = lambda st: json.loads((d(st) / "import.json").read_text())
    state = lambda st: {q: txt(st, q) for q in Q}
    removed = lambda st: re.findall(
        r"Removed import_id=\S+ sources=(\S+)", (d(st) / "aip.log").read_text()
    )
    rows = lambda s: [l for l in s.splitlines()[1:] if l.strip()]

    def run(st):
        [r] = [
            r for r in imp(st)["runs"] if r["configured_source_id"] == sc["declarations_source_id"]
        ]
        return r

    for st in ["S0", "L1", "L4a", "L4b", "L6", "L2", "R", "L5", "L3"]:
        check(
            target,
            st,
            (d(st) / "workdir-digest").read_text().strip() == PINNED[target][st],
            "workdir-digest = pinned",
        )
    # S0
    check(
        target,
        "S0",
        imp("S0")["committed"]
        and all(s["result"].startswith("ACCEPTED") for s in imp("S0")["sources"].values()),
        "committed, every source ACCEPTED*",
    )
    # L1
    src = imp("L1")["sources"].values()
    check(
        target,
        "L1",
        all(
            not s["graph_revision_advanced"]
            and s["nodes_expired"] == 0
            and s["relations_expired"] == 0
            for s in src
        ),
        "no revision advance, 0 expirations",
    )
    check(target, "L1", state("L1") == state("S0"), "all of State(L1) = State(S0)")
    # non-committing
    for st in ["L4a", "L4b", "L6"]:
        check(
            target,
            st,
            imp(st)["committed"] is False and imp(st)["sources"] == {},
            "committed:false, sources:{}",
        )
        check(target, st, state(st) == state("L1"), "all of State = State(L1)")
        check(target, st, removed(st) == [], "no Removed line")
    # #257 frozen labels
    r = run("L4a")
    check(
        target,
        "L4a",
        r["inventory_status"] == "FAILED"
        and r["committed"] is False
        and r["source_results"] == []
        and "SOURCE_ROOT_UNAVAILABLE" in {x["code"] for x in r["diagnostics"]},
        "label: FAILED, no source results, SOURCE_ROOT_UNAVAILABLE",
    )
    r = run("L4b")
    res = {s["locator"]: s for s in r["source_results"]}
    copy = res.get("lifecycle-unbound-copy/openapi.yml")
    others = [s for k, s in res.items() if k != "lifecycle-unbound-copy/openapi.yml"]
    ok = (
        r["inventory_status"] == "PARTIAL"
        and r["committed"] is False
        and copy is not None
        and copy["result"] == "REJECTED_UNSUPPORTED"
        and "SERVICE_IDENTITY_UNRESOLVED" in {x["code"] for x in copy["diagnostics"]}
    )
    ok = ok and all(s["result"] in ("ACCEPTED", "ACCEPTED_WITH_LIMITATIONS") for s in others)
    ok = ok and (len(others) == (4 if target == "quarkus-super-heroes" else 0))
    check(
        target,
        "L4b",
        ok,
        f"label: PARTIAL; unbound copy REJECTED_UNSUPPORTED/SERVICE_IDENTITY_UNRESOLVED; {len(others)} others accepted",
    )
    r = run("L6")
    res = {s["locator"]: s for s in r["source_results"]}
    inj = sc["steps"][[s["id"] for s in sc["steps"]].index("L6")]["inject"]["file"]
    ok = (
        r["inventory_status"] == "PARTIAL"
        and r["committed"] is False
        and res[inj]["result"] == "REJECTED_CONFLICT"
        and "SERVICE_IDENTITY_CONFLICT" in {x["code"] for x in res[inj]["diagnostics"]}
    )
    if target == "quarkus-super-heroes":
        man = res["rest-fights/architecture.yaml"]
        ok = (
            ok
            and man["result"] == "REJECTED_UNSUPPORTED"
            and "MANIFEST_CALL_SOURCE_UNRESOLVED" in {x["code"] for x in man["diagnostics"]}
        )
    check(
        target,
        "L6",
        ok,
        f"label: PARTIAL; {inj} REJECTED_CONFLICT/SERVICE_IDENTITY_CONFLICT"
        + (
            "; manifest REJECTED_UNSUPPORTED/MANIFEST_CALL_SOURCE_UNRESOLVED"
            if target == "quarkus-super-heroes"
            else ""
        ),
    )
    # L2
    check(target, "L2", imp("L2")["committed"], "committed:true")
    check(target, "L2", removed("L2") == [x], "Removed line names X only")
    check(
        target,
        "L2",
        rows(txt("L2", "Q-SRC")) == [l for l in rows(txt("L1", "Q-SRC")) if x not in l],
        "Q-SRC = State(L1) minus X's row",
    )
    for q in ["Q-SVC", "Q-REL"]:
        check(
            target,
            "L2",
            (d("L2") / f"{q}.diff").read_text() == "",
            f"{q} = Without_X(L1) (empty diff)",
        )
    check(
        target,
        "L2",
        x not in txt("L2", "Q-OWN") and x not in txt("L2", "Q-SRC-SEM"),
        "X in no Q-OWN / Q-SRC-SEM row",
    )
    # R
    check(target, "R", imp("R")["committed"], "committed:true")
    check(
        target,
        "R",
        all(txt("R", q) == txt("L1", q) for q in ["Q-SRC", "Q-SRC-SEM", "Q-OWN", "Q-SVC", "Q-REL"]),
        "Q-SRC, Q-SRC-SEM, Q-OWN, owned graph = State(L1)",
    )
    # L5
    check(
        target,
        "L5",
        imp("L5")["committed"] and removed("L5") == [],
        "committed:true, no Removed line",
    )
    xrow = lambda st, q: [l for l in rows(txt(st, q)) if x in l]
    check(
        target,
        "L5",
        xrow("L5", "Q-SRC") == xrow("R", "Q-SRC")
        and xrow("R", "Q-SRC") != []
        and xrow("L5", "Q-SRC-SEM") == xrow("R", "Q-SRC-SEM"),
        "X's Q-SRC and Q-SRC-SEM rows = State(R)",
    )
    check(
        target,
        "L5",
        txt("L5", "Q-SVC") == txt("R", "Q-SVC") and txt("L5", "Q-REL") == txt("R", "Q-REL"),
        "owned graph = State(R)",
    )
    invR, inv5 = rows(txt("R", "Q-INV"))[0].split(", "), rows(txt("L5", "Q-INV"))[0].split(", ")
    check(
        target,
        "L5",
        invR[0] == inv5[0] and invR[1] != inv5[1],
        "Q-INV: same discovery_scope_id, new scope_definition_digest",
    )
    others5 = [l for l in rows(txt("L5", "Q-SRC")) if x not in l]
    check(
        target,
        "L5",
        others5 != [] and all(inv5[1] in l for l in others5)
        if target == "quarkus-super-heroes"
        else True,
        "other sources' Q-SRC rows carry the new digest"
        + ("" if target == "quarkus-super-heroes" else " (Airflow: no other source)"),
    )
    # L3
    check(
        target,
        "L3",
        imp("L3")["committed"] and removed("L3") == [x],
        "committed:true; Removed line names X only",
    )
    check(
        target,
        "L3",
        rows(txt("L3", "Q-SRC")) == [l for l in rows(txt("L5", "Q-SRC")) if x not in l],
        "Q-SRC = State(L5) minus X's row",
    )
    for q in ["Q-SVC", "Q-REL"]:
        check(
            target,
            "L3",
            (d("L3") / f"{q}.diff").read_text() == "",
            f"{q} = Without_X(L5) (empty diff)",
        )
    check(target, "L3", x not in txt("L3", "Q-OWN"), "X in no Q-OWN row")
print("FAILURES:", fails if fails else "none")
