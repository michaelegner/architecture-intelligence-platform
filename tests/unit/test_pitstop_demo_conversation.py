"""v0.6.2 I1b-2: the recorded Claude Code conversation over the Pitstop demo (spec §5, §7.1).

The recording is a real, unedited model run, so its wording cannot be asserted. These static checks guard
what must hold of any version of the document: its structure, that it labels itself an example, that the
tool calls it lists stay inside the granted set, that it quotes one snapshot, that it records the two
earlier discarded attempts, and that its links resolve.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO / "examples" / "pitstop-demo"
DOC = DEMO_DIR / "conversation-claude-code.md"
SNAPSHOT = re.compile(r"aip:snapshot:v1:[0-9a-f]{64}")
AIP_TOOLS = {"get_service_dependencies", "get_evidence", "get_architecture_drift"}
FILE_TOOLS = {"Read", "Grep", "Glob"}
FORBIDDEN = ("Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "Task", "Agent")


def _text() -> str:
    return DOC.read_text()


def _sections(text: str) -> dict[str, str]:
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    return {part.splitlines()[0]: part for part in parts[1:]}


def _tool_call_lines(text: str) -> list[dict]:
    calls = []
    for block in re.findall(r"```json\n(.*?)\n```", text, flags=re.DOTALL):
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("{"):
                calls.append(json.loads(line))
    return calls


def test_the_document_has_three_turns_the_history_and_the_evaluation():
    sections = _sections(_text())
    assert [name for name in sections if name.startswith("Turn ")] == ["Turn 1", "Turn 2", "Turn 3"]
    assert any(name.startswith("Recording history") for name in sections)
    assert any(name.startswith("Evaluation against the spec §5 checks") for name in sections)
    for turn in ("Turn 1", "Turn 2", "Turn 3"):
        assert "**User:**" in sections[turn] and "**Claude Code:**" in sections[turn], turn
        assert "**Tool calls:**" in sections[turn], turn


def test_the_user_turns_are_the_demo_prompt_and_the_two_spec_questions_verbatim():
    sections = _sections(_text())
    run_sh = (DEMO_DIR / "run.sh").read_text()
    prompt_start = run_sh.index("In the Pitstop service WorkshopManagementAPI")
    first_sentence = " ".join(run_sh[prompt_start : prompt_start + 420].split()[:20])
    assert first_sentence in " ".join(sections["Turn 1"].replace("> ", "").split())
    assert "> Which of them read StartTime and EndTime?" in sections["Turn 2"]
    assert "> What should I inspect before replacing the two fields?" in sections["Turn 3"]


def test_the_header_labels_the_recording_an_example_and_names_its_boundaries():
    text = _text()
    assert "**example, not\nqualification evidence**" in text
    assert "re-qualification of the [v0.4.2 client matrix]" in text
    assert "`src/WorkshopManagementAPI/` and `docs/` only" in text
    assert "no shell, write, edit or web tools" in text
    assert "blockReadsOutsideWorkingDirectories" in text
    assert re.search(r"fork baseline commit `[0-9a-f]{40}`", text)
    assert "not publicly resolvable" in text
    assert "The agent left its checkout" in text and "The plugin skill never loaded" in text


def test_the_listed_tool_calls_stay_inside_the_granted_set():
    text = _text()
    calls = _tool_call_lines(text)
    assert calls
    tools = [c.get("tool") for c in calls if "tool" in c]
    # the optional drift step was not taken in this recording; the two answers the ladder needs were
    assert {"get_service_dependencies", "get_evidence"} <= set(tools)
    assert set(tools) <= AIP_TOOLS | FILE_TOOLS
    assert not [t for t in tools if t in FORBIDDEN]
    assert [c["skill"] for c in calls if "skill" in c] == ["aip:architecture-aware-development"]
    # no recorded call reads anywhere but the placeholder checkout
    for call in calls:
        for value in (call.get("input") or {}).values():
            assert not str(value).startswith("/"), call


def test_the_document_quotes_one_snapshot_and_no_local_paths_or_personal_data():
    text = _text()
    header = text.split("```bash")[0]
    [snapshot] = set(SNAPSHOT.findall(header))
    assert set(SNAPSHOT.findall(text)) == {snapshot}
    assert "<checkout>" in text
    for forbidden in ("/home/", "/tmp/", "/Users/", "sk-", "token"):
        assert forbidden not in text, forbidden
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)  # no e-mail address


def test_every_aip_request_is_for_the_publisher_in_the_demo_context():
    for call in _tool_call_lines(_text()):
        request = call.get("request")
        if not request:
            continue
        if "service_id" in request:
            assert request["service_id"] == "service:workshop-management-api"
            assert request["observation_context"] == {
                "environment": "pitstop-demo",
                "window_start": "2026-10-06T00:00:00Z",
                "window_end": "2026-10-06T23:59:59Z",
            }
        else:
            assert SNAPSHOT.fullmatch(request["snapshot_id"])


def test_the_evaluation_covers_q1_to_q6_and_the_sanity_criteria():
    evaluation = next(s for n, s in _sections(_text()).items() if n.startswith("Evaluation"))
    for row in ("| Q1 |", "| Q2 |", "| Q3 |", "| Q4 |", "| Q5 |", "| Q6 |"):
        assert row in evaluation, row
    for row in ("§7.1 (a)", "§7.1 (b)", "§7.1 (c)"):
        assert row in evaluation, row
    assert "What to read critically" in evaluation


def test_the_walkthrough_and_the_readme_link_to_the_recording():
    assert "conversation-claude-code.md" in (DEMO_DIR / "walkthrough.md").read_text()
    assert "conversation-claude-code.md" in (DEMO_DIR / "README.md").read_text()
    assert (
        "arrives with the Claude Code client assets in a\nlater increment"
        not in (DEMO_DIR / "walkthrough.md").read_text()
    )
