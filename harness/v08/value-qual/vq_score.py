"""v0.8 value qualification (spec §5, §7): scores one session.

- Plan key (spec §5.1): K1-K4 as in v0.8 (`i4/score.py` `score_binding`); K5 and K7 from the plan
  only, with `basis: PLAN_ONLY` (no applied configuration exists: nothing is presented as applied);
  K7 is not scored in T (D5); K6 and K8 sub-checks are owner verdicts.
- Q1, Q2: against `comprehension-key.json`. Q3: calibration against the sources of the session and
  coverage against the common reference, per crossing row, from `matrix.json`. Q4, Q5: owner verdicts,
  with a proposed verdict and its reason.
- Unsupported claims (spec §5.3): U3 and U4 are mechanical. U3 needs evidence that supports the
  specific claim: a frozen support entry of `matrix.json` for that row and claim type, a received
  broker-tool output or R1 answer with the consumer's group on the topic, or a received AIP answer
  with the row. A partial location never counts as support. Any other cited location gets a proposed
  verdict for the owner. U1, U2, U5 and U6 are keyword candidates with proposed verdicts.
- Effort: tool calls attempted and received, output tokens, active agent time (operator waits
  excluded).

    vq_score.py RUN_HOME SESSION TRANSCRIPT.jsonl [...] [--verdicts FILE]
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i4"))
sys.path.insert(0, str(HERE))

import score as v08
import vq_audit
import vq_broker_check
import vq_format
from plan_format import load_key, short_service

EVIDENCE = vq_format.EVIDENCE
MATCHED, DIFFERENT, MISSING = v08.MATCHED, v08.DIFFERENT, v08.MISSING
PENDING_OWNER, NOT_SCORED, PLAN_ONLY = v08.PENDING_OWNER, "NOT_SCORED", "PLAN_ONLY"
SUPPORTED, PARTIAL, UNSUPPORTED, OWNER = "SUPPORTED", "PARTIAL", "UNSUPPORTED", "OWNER"
CLAIM_VERDICTS = {SUPPORTED, UNSUPPORTED, "NOT_A_CLAIM"}
MOVED = {"ecommerce-catalog-service", "ecommerce-image-service"}
Q5_KEYWORDS = {
    "Q5.1": ("handl", "process"),
    "Q5.2": ("point in time", "snapshot", "one capture", "one broker", "moment"),
    "Q5.3": ("producer",),
    "Q5.4": ("not documented", "undocumented", "missing document", "no document"),
}
SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
NEGATED = re.compile(r"\b(not|no|never|cannot)\b|n't")


def frozen() -> dict:
    return {
        name: json.loads((EVIDENCE / f"{name}.json").read_text())
        for name in ("matrix", "comprehension-key", "claim-rules")
    }


def _pair(consumer: str, topic: str) -> tuple[str, str]:
    return short_service(consumer.strip()), topic.strip()


# --- plan key ---------------------------------------------------------------------------------


def score_k5_plan_only(plan: dict) -> dict:
    directions = v08.by_direction(plan["allow_lists"])
    overlap = v08._overlap(directions)
    verdict = MISSING if not directions else DIFFERENT if overlap else MATCHED
    return {
        "id": "K5",
        "verdict": verdict,
        "basis": PLAN_ONLY,
        "plan_items": [],
        "problems": [f"the plan mirrors {overlap} in both directions"] if overlap else [],
        "planned": {f"{s}->{t}": sorted(v) for (s, t), v in sorted(directions.items())},
    }


def score_k7_plan_only(key_item: dict, plan: dict, card_type: str) -> dict:
    if card_type.startswith("T"):
        return {
            "id": "K7",
            "verdict": NOT_SCORED,
            "basis": PLAN_ONLY,
            "plan_items": [],
            "problems": [],
        }
    wanted = set(key_item["services"])
    changing = [item for item in plan["items"] if v08._changes_brokers(item)]
    services = {short_service(s) for item in changing for s in item.get("services", [])}
    problems = []
    if not changing:
        verdict = MISSING
    elif services != wanted:
        verdict = DIFFERENT
        problems.append(f"the plan changes the broker setting of {sorted(services)}")
    else:
        verdict = MATCHED
    return {
        "id": "K7",
        "verdict": verdict,
        "basis": PLAN_ONLY,
        "plan_items": sorted(item["id"] for item in changing),
        "problems": problems,
    }


def score_plan(plan: dict, card_type: str, verdicts: dict) -> dict:
    key = load_key()
    items = {k["id"]: k for k in key["items"]}
    directions = v08.by_direction(plan["allow_lists"])
    results = [v08.score_binding(items[k], plan, directions) for k in ("K1", "K2", "K3", "K4")]
    results.append(score_k5_plan_only(plan))
    results.append(score_k7_plan_only(items["K7"], plan, card_type))
    claimed = {pid for r in results for pid in r.get("plan_items", [])}
    owner = [
        e for k in ("K6", "K8") for e in v08.score_owner_judged(items[k], plan, verdicts, claimed)
    ]
    claimed |= {pid for e in owner for pid in e["plan_items"]}
    return {
        "key_items": results,
        "owner_judged": owner,
        "extra": sorted(i["id"] for i in plan["items"] if i["id"] not in claimed),
    }


# --- sources the session received ---------------------------------------------------------------


class Received:
    """What the session could cite: its repositories, the broker-tool outputs and request answers
    it received, and the AIP answers it received."""

    def __init__(self, repositories: set[str], workspace: Path | None) -> None:
        self.repositories = repositories
        self.workspace = workspace
        self.commands: dict[str, list[str]] = {}
        self.requests: dict[str, str] = {}
        self.aip: list[dict] = []

    @classmethod
    def from_session(
        cls,
        found: list[dict],
        record: list[dict],
        agent_requests: list[dict],
        repositories: set[str],
        workspace: Path | None,
    ) -> "Received":
        received = cls(repositories | {e["grant"] for e in record if e.get("grant")}, workspace)
        for event in found:
            if event["kind"] == "call" and event["tool"] == "Bash" and event["received"]:
                command = str((event["input"] or {}).get("command", "")).strip()
                output = vq_audit._text((event["result"] or {}).get("content"))
                received.commands.setdefault(command, []).append(output)
        r1 = vq_broker_check.R1.read_text()
        for entry in record:
            if entry["entry"] == "R1" and isinstance(entry["request"], dict):
                received.requests[entry["request"]["id"]] = r1
        received.aip = [
            r["transcript_answer"] for r in agent_requests if r.get("transcript_answer")
        ]
        return received

    def broker_pairs(self, outputs: list[str]) -> set[tuple[str, str]]:
        pairs = set()
        for output in outputs:
            for group, entry in vq_broker_check.groups(output).items():
                pairs |= {(group, topic) for topic in entry["topics"]}
        return pairs

    def aip_rows(self, snapshot: str | None) -> list[dict]:
        return [
            row
            for answer in self.aip
            if (answer.get("snapshot") or {}).get("snapshot_id") == snapshot and answer.get("data")
            for row in answer["data"]["rows"]
        ]


# --- U3: claim support ---------------------------------------------------------------------------


def _covers(cited: tuple[str, int, int], location: str) -> bool:
    path, start, end = vq_format.location(location) or ("", 0, -1)
    return cited[0] == path and cited[1] <= end + 1 and cited[2] >= start - 1


def _groups_met(groups: list[list[str]], cited: list[tuple[str, int, int]]) -> bool:
    return any(all(any(_covers(c, loc) for c in cited) for loc in group) for group in groups)


def _row(matrix: dict, pair: tuple[str, str]) -> dict | None:
    return next((r for r in matrix["rows"] if (r["consumer"], r["topic"]) == pair), None)


def _cited_lines(workspace: Path | None, cited: tuple[str, int, int]) -> str | None:
    if workspace is None:
        return None
    path = workspace / "src" / cited[0]
    if not path.is_file():
        return None
    lines = path.read_text(errors="replace").splitlines()
    return "\n".join(lines[cited[1] - 1 : min(cited[2], cited[1] + 4)])


def support(
    claim_type: str,
    pair: tuple[str, str],
    evidence: list[dict],
    matrix: dict,
    received: Received,
) -> dict:
    """The U3 resolution of one claim: SUPPORTED, PARTIAL, UNSUPPORTED or OWNER (with a proposal)."""
    consumer, topic = pair
    row = _row(matrix, pair) if consumer != "*" else None
    cited, partial, other, unresolved = [], [], [], []
    by_kind: dict[str, bool] = {}
    for entry in evidence:
        kind, reference = entry["kind"], entry["reference"]
        if kind == "reasoning":
            continue
        if kind in vq_format.FILE_KINDS:
            location = vq_format.location(reference)
            reachable = (
                location is not None and location[0].split("/", 1)[0] in received.repositories
            )
            exists = reachable and (
                received.workspace is None or (received.workspace / "src" / location[0]).is_file()
            )
            if location is None or not exists:
                unresolved.append(reference)
            else:
                cited.append(location)
        elif kind in ("broker_tool", "request"):
            outputs = (
                received.commands.get(reference.strip(), [])
                if kind == "broker_tool"
                else [received.requests[reference.strip()]]
                if reference.strip() in received.requests
                else []
            )
            if not outputs:
                unresolved.append(reference)
            elif (consumer, topic) in received.broker_pairs(outputs) or (
                consumer == "*" and any(t == topic for _, t in received.broker_pairs(outputs))
            ):
                by_kind["binding"] = by_kind["observed"] = True
            else:
                unresolved.append(reference)
        elif kind == "aip":
            rows = received.aip_rows(entry.get("snapshot_id"))
            refs = set(entry.get("evidence_refs") or [])
            matches = [
                r
                for r in rows
                if (
                    _pair(r["consumer_service_id"], r["topic_name"]) == pair
                    or (consumer == "*" and r["topic_name"] == topic)
                )
                and (
                    (entry.get("topic_name"), short_service(entry.get("consumer_service_id") or ""))
                    == (r["topic_name"], short_service(r["consumer_service_id"]))
                    or refs & _refs(r)
                )
            ]
            if not matches:
                unresolved.append(reference)
            for r in matches:
                by_kind["binding"] = by_kind["direction"] = True
                if r.get("attachment_evidence_refs"):
                    by_kind["observed"] = True
                # A promise ref is EventCatalog evidence, not documentation (spec §5.2):
                # "documented" needs a cited docs/ location.
        else:
            unresolved.append(reference)

    def files(kind: str) -> bool:
        if kind == "producer":
            return _groups_met(matrix["producers"].get(topic, []), cited)
        if consumer == "*":
            return any(
                _groups_met(r["support"][kind], cited)
                for r in matrix["rows"]
                if r["topic"] == topic
            )
        return row is not None and _groups_met(row["support"].get(kind, []), cited)

    if claim_type == "direction":
        binding = by_kind.get("binding") or files("binding")
        ok = by_kind.get("direction") or (
            binding and (by_kind.get("producer") or files("producer"))
        )
    elif claim_type == "observed":
        ok = by_kind.get("observed", False)
    else:
        ok = by_kind.get(claim_type) or files(claim_type)
    for location in cited:
        rows = [row] if row else [r for r in matrix["rows"] if r["topic"] == topic]
        if any(_covers(location, p) for r in rows for p in r["partial"]):
            partial.append(location)
        elif not any(
            _covers(location, loc)
            for r in matrix["rows"]
            for groups in r["support"].values()
            for group in groups
            for loc in group
        ) and not any(
            _covers(location, loc) for g in matrix["producers"].values() for gr in g for loc in gr
        ):
            other.append(location)
    if ok:
        status, proposal = SUPPORTED, None
    elif other and claim_type != "observed":
        status = OWNER
        proposal = {
            "verdict": UNSUPPORTED,
            "reason": "the cited location is not a frozen support location; the owner checks the line",
            "lines": {
                f"{p}:{s}-{e}": _cited_lines(received.workspace, (p, s, e)) for p, s, e in other
            },
        }
    else:
        status, proposal = (PARTIAL if partial else UNSUPPORTED), None
    return {
        "status": status,
        "partial": [f"{p}:{s}-{e}" for p, s, e in partial],
        "unresolved": unresolved,
        "proposal": proposal,
    }


def _refs(row: dict) -> set[str]:
    return {
        ref
        for field in ("promise_evidence_refs", "attachment_evidence_refs", "mapping_evidence_refs")
        for ref in row.get(field) or []
    }


def claims(plan: dict, answers: dict) -> list[dict]:
    """The factual claims of a session, each with its evidence: q2 rows (binding, direction), q3
    statuses stated as `yes`, and plan items with topics and a direction (direction of each topic)."""
    found = []
    for row in answers["q2"]:
        pair = _pair(row["consumer"], row["topic"])
        found += [
            {"type": t, "pair": pair, "evidence": row["evidence"], "where": "answers.q2"}
            for t in ("binding", "direction")
        ]
    for row in answers["q3"]:
        pair = _pair(row["consumer"], row["topic"])
        for status in ("documented", "observed"):
            if row[status] == "yes":
                found.append(
                    {
                        "type": status,
                        "pair": pair,
                        "evidence": row[f"{status}_evidence"],
                        "where": "answers.q3",
                    }
                )
    for item in plan["items"]:
        if item.get("direction"):
            for topic in item.get("topics", []):
                found.append(
                    {
                        "type": "direction",
                        "pair": ("*", topic),
                        "evidence": item["evidence"],
                        "where": f"plan.{item['id']}",
                    }
                )
    return found


def u4(answers: dict, matrix: dict) -> list[dict]:
    hits = []
    for row in answers["q3"]:
        pair = _pair(row["consumer"], row["topic"])
        known = _row(matrix, pair)
        if known is None or known["documented"] == "partly":
            continue
        if (row["documented"] == "yes" and known["documented"] == "no") or (
            row["documented"] == "no" and known["documented"] == "yes"
        ):
            hits.append(
                {
                    "rule": "U4",
                    "pair": list(pair),
                    "stated": row["documented"],
                    "matrix": known["documented"],
                }
            )
    return hits


def _texts(plan: dict, plan_md: str, answers: dict) -> list[tuple[str, str, bool]]:
    """(where, text, has a source entry) for every free text of the session."""
    found = [("plan.md", plan_md, False)]
    for item in plan["items"]:
        has_source = any(e["kind"] in vq_format.FILE_KINDS for e in item["evidence"])
        found.append((f"plan.{item['id']}", item["action"], has_source))
    for key in ("q4", "q5"):
        for at, row in enumerate(answers[key]):
            text = row.get("must_preserve") or row.get("statement") or ""
            has_source = any(e["kind"] in vq_format.FILE_KINDS for e in row["evidence"])
            found.append((f"answers.{key}[{at}]", text, has_source))
    return found


def keyword_candidates(plan: dict, plan_md: str, answers: dict, rules: dict) -> list[dict]:
    """U1/U2/U5/U6 candidates: a sentence with a rule keyword, with a proposed verdict."""
    found = []
    for rule in rules["rules"]:
        if rule["mode"] != "owner":
            continue
        for where, text, has_source in _texts(plan, plan_md, answers):
            for sentence in SENTENCE.findall(text):
                lowered = sentence.lower()
                keyword = next((k for k in rule["keywords"] if k in lowered), None)
                if keyword is None:
                    continue
                if NEGATED.search(lowered.replace(keyword, "")):
                    proposal = {"verdict": "NOT_A_CLAIM", "reason": "a negated statement"}
                elif rule["id"] == "U2" and has_source:
                    proposal = {
                        "verdict": SUPPORTED,
                        "reason": "a source entry is on the same item",
                    }
                else:
                    proposal = {"verdict": UNSUPPORTED, "reason": f"`{keyword}`: {rule['test']}"}
                found.append(
                    {
                        "rule": rule["id"],
                        "where": where,
                        "statement": sentence.strip(),
                        "keyword": keyword,
                        "proposal": proposal,
                    }
                )
    return found


def unsupported(
    plan: dict, plan_md: str, answers: dict, received: Received, frozen_: dict, verdicts: dict
) -> dict:
    """Every claim with its resolution; one count per subject (spec §5.3)."""
    matrix, rules = frozen_["matrix"], frozen_["claim-rules"]
    owner = verdicts.get("claims", {})
    subjects: dict[str, set[str]] = {}
    pending, resolved = [], []
    for claim in claims(plan, answers):
        result = support(claim["type"], claim["pair"], claim["evidence"], matrix, received)
        claim_id = f"{claim['where']}:{claim['type']}:{'|'.join(claim['pair'])}"
        entry = {"id": claim_id, **{k: v for k, v in claim.items() if k != "evidence"}, **result}
        entry["pair"] = list(claim["pair"])
        broken = result["status"] in (UNSUPPORTED, PARTIAL)
        if result["status"] == OWNER:
            given = owner.get(claim_id, {}).get("verdict")
            if given is None:
                pending.append(claim_id)
            broken = given == UNSUPPORTED
        if broken:
            subjects.setdefault("|".join(claim["pair"]), set()).add("U3")
        resolved.append(entry)
    for hit in u4(answers, matrix):
        subjects.setdefault("|".join(hit["pair"]), set()).add("U4")
    candidates = keyword_candidates(plan, plan_md, answers, rules)
    for candidate in candidates:
        cid = f"{candidate['rule']}:{candidate['where']}:{candidate['statement']}"
        candidate["id"] = cid
        given = owner.get(cid, {}).get("verdict")
        if given is None:
            pending.append(cid)
        elif given == UNSUPPORTED:
            subjects.setdefault(f"statement:{candidate['statement']}", set()).add(candidate["rule"])
    for given in owner.values():
        if given.get("verdict") not in CLAIM_VERDICTS:
            raise SystemExit(f"STOP: unknown claim verdict {given.get('verdict')!r}")
    return {
        "claims": resolved,
        "u4": u4(answers, matrix),
        "candidates": candidates,
        "count": len(subjects),
        "subjects": {k: sorted(v) for k, v in sorted(subjects.items())},
        "pending_owner": sorted(pending),
    }


# --- comprehension ------------------------------------------------------------------------------


def names_boundary(text: str, boundary: str) -> bool:
    """The free-text answer names the boundary in an equivalent spelling: case, spaces, `_` and
    `-` are one separator (`Catalog Management`, `catalog_management`, `catalog-management`)."""
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.search(rf"(^|-){re.escape(boundary)}(-|$)", words) is not None


def score_q1(answers: dict, key: dict) -> dict:
    services = {short_service(s.strip()) for s in answers["q1"]["services"]}
    boundary = names_boundary(answers["q1"]["boundary"], key["q1"]["boundary"])
    ok = services == set(key["q1"]["services"]) and boundary
    return {
        "id": "Q1",
        "verdict": MATCHED if ok else DIFFERENT,
        "services": sorted(services),
        "boundary_named": boundary,
        "boundary": answers["q1"]["boundary"],
    }


def _crossing(matrix: dict, key: dict) -> dict[tuple[str, str], dict]:
    rows = {r["row"]: r for r in matrix["rows"]}
    return {(rows[n]["consumer"], rows[n]["topic"]): rows[n] for n in key["q2"]["crossing_rows"]}


def score_q2(answers: dict, matrix: dict, key: dict) -> dict:
    crossing = _crossing(matrix, key)
    given = {_pair(r["consumer"], r["topic"]): r["direction"] for r in answers["q2"]}
    missing = sorted(p for p in crossing if p not in given)
    wrong = sorted(
        p
        for p, d in given.items()
        if p in crossing and d != key["q2"]["direction"][crossing[p]["crossing"]]
    )
    extra = sorted(p for p in given if p not in crossing)
    verdict = MATCHED if not (missing or wrong or extra) else DIFFERENT if given else MISSING
    return {
        "id": "Q2",
        "verdict": verdict,
        "missing": [list(p) for p in missing],
        "wrong_direction": [list(p) for p in wrong],
        "not_crossing_listed": [list(p) for p in extra],
    }


def _expected_documented(row: dict) -> set[str]:
    return {"yes": {"yes"}, "no": {"no"}, "partly": {"yes", "cannot_tell"}}[row["documented"]]


def established(claims_result: dict, verdicts: dict) -> set[tuple[str, str, str]]:
    """(claim type, consumer, topic) of every q3 claim whose evidence resolved, or that the owner
    accepted: a status is established only with supporting evidence (spec §5.2)."""
    owner = verdicts.get("claims", {})
    return {
        (c["type"], *c["pair"])
        for c in claims_result["claims"]
        if c["where"] == "answers.q3"
        and (
            c["status"] == SUPPORTED
            or (c["status"] == OWNER and owner.get(c["id"], {}).get("verdict") == SUPPORTED)
        )
    }


def score_q3(
    answers: dict,
    matrix: dict,
    key: dict,
    card_type: str,
    received: Received,
    supported: set[tuple[str, str, str]],
) -> list[dict]:
    """Calibration (the sources of the session) and coverage (the common reference). Coverage
    counts a row only when the session established it: observed `yes` with supporting evidence, and
    the documented status as in the matrix (a `yes` with supporting evidence)."""
    crossing = _crossing(matrix, key)
    observed_reach = card_type.startswith("F") or card_type.endswith("+") or bool(received.requests)
    given = {_pair(r["consumer"], r["topic"]): r for r in answers["q3"]}
    in_q2 = {_pair(r["consumer"], r["topic"]) for r in answers["q2"]}
    calibration, coverage = [], []
    for pair, row in sorted(crossing.items()):
        answer = given.get(pair)
        documented_ok = answer is not None and answer["documented"] in _expected_documented(row)
        if answer is not None and pair in in_q2:
            want_observed = "yes" if observed_reach else "cannot_tell"
            ok = documented_ok and answer["observed"] == want_observed
            calibration.append({"pair": list(pair), "calibrated": ok})
        covered = (
            answer is not None
            and documented_ok
            and answer["observed"] == "yes"
            and ("observed", *pair) in supported
            and (answer["documented"] != "yes" or ("documented", *pair) in supported)
        )
        coverage.append({"pair": list(pair), "covered": covered})
    cal_verdict = (
        MISSING
        if not calibration
        else MATCHED
        if all(c["calibrated"] for c in calibration)
        else DIFFERENT
    )
    cov_verdict = MATCHED if all(c["covered"] for c in coverage) else DIFFERENT
    return [
        {
            "id": "Q3-calibration",
            "verdict": cal_verdict,
            "observed_reach": observed_reach,
            "rows": calibration,
        },
        {
            "id": "Q3-coverage",
            "verdict": cov_verdict,
            "covered": sum(c["covered"] for c in coverage),
            "of": len(coverage),
            "rows": coverage,
        },
    ]


def score_owner_q(answers: dict, matrix: dict, key: dict, verdicts: dict) -> list[dict]:
    crossing = _crossing(matrix, key)
    given = {_pair(r["consumer"], r["topic"]): r["must_preserve"] for r in answers["q4"]}
    missing_q4 = sorted(p for p in crossing if p not in given)
    texts = " ".join(s["statement"] for s in answers["q5"]).lower()
    found_q5 = sorted(k for k, words in Q5_KEYWORDS.items() if any(w in texts for w in words))
    proposals = {
        "Q4": {
            "verdict": MATCHED if not missing_q4 else DIFFERENT,
            "reason": "a reason is given for every crossing row"
            if not missing_q4
            else f"no reason for {missing_q4}",
            "candidates": {"|".join(p): t for p, t in sorted(given.items())},
        },
        "Q5": {
            "verdict": MATCHED if len(found_q5) == len(Q5_KEYWORDS) else DIFFERENT,
            "reason": f"keywords found for {found_q5}",
            "candidates": [s["statement"] for s in answers["q5"]],
        },
    }
    return [
        {
            "id": qid,
            "verdict": verdicts.get(qid, {}).get("verdict", PENDING_OWNER),
            "reason": verdicts.get(qid, {}).get("reason"),
            "proposal": proposal,
        }
        for qid, proposal in proposals.items()
    ]


# --- effort -------------------------------------------------------------------------------------


def _time(stamp: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(stamp)


def effort(paths: list[Path]) -> dict:
    """Over all transcript files of the session, each entry and each tool call once: tool calls
    attempted and received; output tokens (one count per assistant message id); active time: per
    operator turn, from the operator's message to the agent's last entry before the next operator
    message (the operator's wait is excluded)."""
    entries = vq_audit.load(paths)
    found = vq_audit.events_of(entries)
    calls = [e for e in found if e["kind"] == "call"]
    prompts = {e["line"] for e in found if e["kind"] == "prompt"}
    tokens, seconds, seen = 0, 0.0, set()
    start = last = None
    for number, entry in enumerate(entries, start=1):
        message = entry.get("message") or {}
        if entry.get("type") == "assistant" and message.get("id") not in seen:
            seen.add(message.get("id"))
            tokens += (message.get("usage") or {}).get("output_tokens", 0)
        stamp = entry.get("timestamp")
        if not stamp:
            continue
        if number in prompts:
            if start and last:
                seconds += (last - start).total_seconds()
            start = last = _time(stamp)
        elif start is not None and entry.get("type") in ("assistant", "user"):
            # Only the agent's messages and tool results: the bookkeeping entries of a resumed run
            # (`queue-operation`, ...) carry the time of the operator's reply.
            last = _time(stamp)
    if start and last:
        seconds += (last - start).total_seconds()
    return {
        "tool_calls_attempted": len(calls),
        "tool_calls_received": sum(1 for e in calls if e["received"]),
        "output_tokens": tokens,
        "active_seconds": round(seconds),
    }


# --- session ------------------------------------------------------------------------------------


def score_session(
    card_type: str,
    plan: dict,
    plan_md: str,
    answers: dict,
    received: Received,
    transcripts: list[Path],
    record: list[dict],
    verdicts: dict,
) -> dict:
    frozen_ = frozen()
    matrix, key = frozen_["matrix"], frozen_["comprehension-key"]
    plan_result = score_plan(plan, card_type, verdicts)
    claims_result = unsupported(plan, plan_md, answers, received, frozen_, verdicts)
    questions = [score_q1(answers, key), score_q2(answers, matrix, key)]
    supported = established(claims_result, verdicts)
    questions += score_q3(answers, matrix, key, card_type, received, supported)
    questions += score_owner_q(answers, matrix, key, verdicts)
    counts = {
        **effort(transcripts),
        "unsupported_claims": claims_result["count"],
        "requests": len(record) if card_type.startswith("T") else None,
    }
    pending = sorted(
        [e["id"] for e in plan_result["owner_judged"] if e["verdict"] == PENDING_OWNER]
        + [q["id"] for q in questions if q["verdict"] == PENDING_OWNER]
        + claims_result["pending_owner"]
    )
    return {
        "type": card_type,
        "plan": plan_result,
        "questions": questions,
        "claims": claims_result,
        "counts": counts,
        "requests": record,
        "pending_owner": pending,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_home", type=Path)
    parser.add_argument("session")
    parser.add_argument("transcripts", type=Path, nargs="+")
    parser.add_argument("--verdicts", type=Path, help="owner verdicts (JSON)")
    args = parser.parse_args(argv)
    session_dir = args.run_home.resolve() / "sessions" / args.session
    session = json.loads((session_dir / "session.json").read_text())
    card = vq_format.card(session["type"])
    workspace = session_dir / "workspace"
    plan = vq_format.load_plan(workspace / "plan.json", card)
    answers = vq_format.load_answers(workspace / "answers.json", card)
    record_path = session_dir / "requests-record.json"
    record = json.loads(record_path.read_text()) if record_path.exists() else []
    agent_requests = json.loads((session_dir / "agent-requests.json").read_text())
    found = vq_audit.events_of(vq_audit.load(args.transcripts))
    received = Received.from_session(
        found, record, agent_requests, set(session["repositories"]), workspace
    )
    verdicts = json.loads(args.verdicts.read_text()) if args.verdicts else {}
    result = score_session(
        session["type"],
        plan,
        (workspace / "plan.md").read_text(),
        answers,
        received,
        args.transcripts,
        record,
        verdicts,
    )
    (session_dir / "scoring.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"scored {args.session}; {len(result['pending_owner'])} owner item(s) pending")
    return 0 if not result["pending_owner"] else 3


if __name__ == "__main__":
    sys.exit(main())
