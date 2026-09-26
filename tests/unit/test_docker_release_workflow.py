"""v0.5.0 I6 §8/§19: the release workflow binds every post-push step to the pushed digest.

The workflow runs only on `release: published`, from the tagged commit. So nothing can execute it
before publication, and its content has to be right in the release candidate itself. These
tests pin each §8 element statically.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "docker.yml"
DIGEST_REF = "${{ steps.pushed.outputs.ref }}"
TRIVY = "aquasecurity/trivy-action@"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps() -> list[dict]:
    return _workflow()["jobs"]["build-and-push"]["steps"]


def _step(name: str) -> dict:
    [step] = [s for s in _steps() if s.get("name") == name]
    return step


def _trivy_steps() -> list[dict]:
    return [s for s in _steps() if s.get("uses", "").startswith(TRIVY)]


def test_trigger_and_permissions_are_unchanged():
    workflow = _workflow()
    # PyYAML reads the bare `on:` key as boolean True.
    assert workflow[True] == {"release": {"types": ["published"]}}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["build-and-push"]["permissions"] == {
        "contents": "read",
        "packages": "write",
        "security-events": "write",
    }


def test_the_pushed_digest_is_captured_and_recorded_in_the_job_summary():
    assert _step("Build and push")["id"] == "build"
    pushed = _step("Record pushed digest")
    assert pushed["id"] == "pushed"
    assert pushed["env"]["DIGEST"] == "${{ steps.build.outputs.digest }}"
    assert pushed["env"]["RUN_ID"] == "${{ github.run_id }}"
    assert pushed["env"]["RUN_ATTEMPT"] == "${{ github.run_attempt }}"
    script = pushed["run"]
    assert 'echo "ref=${IMAGE_NAME}@${DIGEST}"' in script
    assert "GITHUB_STEP_SUMMARY" in script
    for field in ("${IMAGE_NAME}@${DIGEST}", "${RUN_ID}", "${RUN_ATTEMPT}"):
        assert field in script
    # A malformed digest must stop the job rather than scan something else.
    assert "^sha256:[0-9a-f]{64}$" in script


def test_every_scan_uses_the_digest_and_one_pinned_trivy_version():
    trivy = _trivy_steps()
    assert len(trivy) == 3
    assert {s["uses"] for s in trivy} == {"aquasecurity/trivy-action@v0.36.0"}
    for step in trivy:
        assert step["with"]["image-ref"] == DIGEST_REF, step["name"]
        assert step["with"]["version"] == "v0.70.0", step["name"]
        assert step["with"]["scan-type"] == "image", step["name"]
    # No step may reference the mutable tag as a scan target.
    assert all(":${{ github.ref_name }}" not in s["with"]["image-ref"] for s in trivy)


def test_full_report_includes_unfixed_high_and_critical_findings():
    full = _step("Full HIGH/CRITICAL report with Trivy")["with"]
    assert full["format"] == "json"
    assert full["output"] == "trivy-full-report.json"
    assert full["severity"] == "CRITICAL,HIGH"
    assert full["ignore-unfixed"] is False


def test_sbom_is_cyclonedx_for_the_pushed_digest():
    sbom = _step("Generate SBOM with Trivy")["with"]
    assert sbom["format"] == "cyclonedx"
    assert sbom["output"] == "sbom.cdx.json"


def test_sarif_upload_is_kept_and_non_blocking():
    sarif = _step("Scan image with Trivy (SARIF)")["with"]
    assert sarif["format"] == "sarif"
    assert sarif["exit-code"] == "0"
    upload = _step("Upload Trivy scan results")
    assert upload["with"]["sarif_file"] == "trivy-results.sarif"


def test_report_and_sbom_are_retained_as_digest_named_artifacts():
    retain = _step("Retain release security evidence")
    assert retain["uses"] == "actions/upload-artifact@v7.0.1"
    assert retain["with"]["name"] == "release-security-${{ steps.pushed.outputs.slug }}"
    assert retain["with"]["path"].split() == ["trivy-full-report.json", "sbom.cdx.json"]
    assert retain["with"]["if-no-files-found"] == "error"
    names = [s.get("name") for s in _steps()]
    assert names.index("Retain release security evidence") > names.index("Generate SBOM with Trivy")


def test_every_action_is_version_pinned():
    for step in _steps():
        if "uses" in step:
            assert "@" in step["uses"] and not step["uses"].endswith("@main"), step["uses"]
