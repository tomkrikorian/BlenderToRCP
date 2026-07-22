"""Regression coverage for the protected Apple runner trust boundary."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIRECTORY = ROOT / ".github/workflows"
APPLE_WORKFLOW = ROOT / ".github/workflows/apple-platform-validation.yml"
RELEASE_WORKFLOW = ROOT / ".github/workflows/build-archive.yml"
EXPECTED_REPOSITORY = "tomkrikorian/BlenderToRCP"
STABLE_SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
)


def _job_block(workflow: str, job_id: str) -> str:
    lines = workflow.splitlines()
    marker = f"  {job_id}:"
    start = lines.index(marker)
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.fullmatch(r"  [a-zA-Z0-9_-]+:", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def _trigger_block(workflow: str) -> str:
    return workflow.split("\npermissions:", maxsplit=1)[0].split("\non:\n", maxsplit=1)[1]


def _simulate_apple_policy(
    *,
    repository: str = EXPECTED_REPOSITORY,
    event: str,
    ref: str,
    ref_type: str,
    manifest_version: str = "2.0.0",
    is_dev_ancestor: bool = True,
    tag_resolves_to_sha: bool = True,
) -> bool:
    """Model the allow-list enforced inline by the GitHub-hosted policy job."""

    if repository != EXPECTED_REPOSITORY or event not in {"push", "workflow_dispatch"}:
        return False

    if ref == "refs/heads/dev":
        if ref_type != "branch":
            return False
    else:
        match = re.fullmatch(r"refs/tags/(.+)", ref)
        if match is None or ref_type != "tag":
            return False
        tag = match.group(1)
        if STABLE_SEMVER.fullmatch(tag) is None or tag != manifest_version:
            return False
        if not tag_resolves_to_sha:
            return False

    return is_dev_ancestor


def test_apple_workflow_has_no_direct_manual_or_pull_request_entrypoint() -> None:
    triggers = _trigger_block(APPLE_WORKFLOW.read_text(encoding="utf-8"))

    assert re.search(r"^  workflow_call:$", triggers, re.MULTILINE)
    assert re.search(r"^  push:$", triggers, re.MULTILINE)
    assert not re.search(r"^  workflow_dispatch:$", triggers, re.MULTILINE)
    assert not re.search(r"^  pull_request(?:_target)?:$", triggers, re.MULTILINE)


def test_self_hosted_job_consumes_only_authorized_immutable_sha() -> None:
    workflow = APPLE_WORKFLOW.read_text(encoding="utf-8")
    authorization = _job_block(workflow, "authorize-apple-revision")
    protected = _job_block(workflow, "apple-27")

    assert "runs-on: ubuntu-24.04" in authorization
    assert "EXPECTED_REPOSITORY: tomkrikorian/BlenderToRCP" in authorization
    assert '"refs/heads/dev"' in authorization
    assert "^refs/tags/" in authorization
    assert "manifest_version" in authorization
    assert "git merge-base --is-ancestor" in authorization
    assert "refs/remotes/origin/dev" in authorization
    assert "authorized_sha=$requested_commit" in authorization

    assert "needs: authorize-apple-revision" in protected
    assert "if: needs.authorize-apple-revision.outputs.authorized == 'true'" in protected
    assert "- self-hosted" in protected
    assert "persist-credentials: false" in protected
    assert "ref: ${{ needs.authorize-apple-revision.outputs.authorized_sha }}" in protected


def test_release_workflow_is_the_only_manual_entry_and_calls_canonical_dev_policy() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    triggers = _trigger_block(workflow)
    metadata = _job_block(workflow, "validate-release-metadata")
    apple_call = _job_block(workflow, "apple-27-quality-gate")

    assert re.search(r"^  workflow_dispatch:$", triggers, re.MULTILINE)
    assert '"refs/heads/dev"' in metadata
    assert '"refs/tags/$RELEASE_TAG"' in metadata
    assert "git merge-base --is-ancestor" in metadata
    assert "refs/remotes/origin/dev" in metadata
    assert "needs: validate-release-metadata" in apple_call
    assert (
        "uses: tomkrikorian/BlenderToRCP/"
        ".github/workflows/apple-platform-validation.yml@dev"
    ) in apple_call
    assert "uses: ./.github/workflows/apple-platform-validation.yml" not in apple_call


def test_manual_dispatch_from_arbitrary_branch_is_rejected() -> None:
    assert not _simulate_apple_policy(
        event="workflow_dispatch",
        ref="refs/heads/feature/untrusted-runner-code",
        ref_type="branch",
    )


def test_reusable_call_inherits_and_rejects_unvalidated_caller_ref() -> None:
    # Reusable workflows see the caller's original event/ref. This models a
    # workflow_call reached from an otherwise valid push event on an untrusted
    # branch; the branch must not be allowed to allocate the Apple runner.
    assert not _simulate_apple_policy(
        event="push",
        ref="refs/heads/feature/unvalidated-caller",
        ref_type="branch",
    )


def test_trusted_dev_and_exact_release_revisions_are_allowed() -> None:
    assert _simulate_apple_policy(
        event="push",
        ref="refs/heads/dev",
        ref_type="branch",
    )
    assert _simulate_apple_policy(
        event="workflow_dispatch",
        ref="refs/heads/dev",
        ref_type="branch",
    )
    assert _simulate_apple_policy(
        event="push",
        ref="refs/tags/2.0.0",
        ref_type="tag",
    )


def test_release_policy_fails_closed_on_identity_version_and_ancestry() -> None:
    base = {
        "event": "push",
        "ref": "refs/tags/2.0.0",
        "ref_type": "tag",
    }

    assert not _simulate_apple_policy(repository="someone/fork", **base)
    assert not _simulate_apple_policy(manifest_version="2.0.1", **base)
    assert not _simulate_apple_policy(is_dev_ancestor=False, **base)
    assert not _simulate_apple_policy(tag_resolves_to_sha=False, **base)
    assert not _simulate_apple_policy(
        event="push",
        ref="refs/tags/v2.0.0",
        ref_type="tag",
    )
    assert not _simulate_apple_policy(
        event="push",
        ref="refs/tags/02.0.0",
        ref_type="tag",
        manifest_version="02.0.0",
    )


def test_privileged_jobs_pin_third_party_actions_to_full_commit_shas() -> None:
    """A mutable action tag must never receive release-write authority."""

    full_commit = re.compile(r"[^\s@]+@[0-9a-f]{40}$")
    privileged_jobs = 0

    for workflow_path in sorted(WORKFLOW_DIRECTORY.glob("*.yml")):
        workflow = workflow_path.read_text(encoding="utf-8")
        job_ids = re.findall(r"^  ([a-zA-Z0-9_-]+):$", workflow, re.MULTILINE)
        for job_id in job_ids:
            block = _job_block(workflow, job_id)
            if not re.search(r"^      contents: write$", block, re.MULTILINE):
                continue
            privileged_jobs += 1
            action_refs = re.findall(
                r"^\s+-?\s*uses:\s*([^\s#]+)", block, re.MULTILINE
            )
            for action_ref in action_refs:
                if action_ref.startswith(("actions/", "./")):
                    continue
                assert full_commit.fullmatch(action_ref), (
                    f"{workflow_path.name}:{job_id} grants contents:write to "
                    f"mutable third-party action {action_ref}"
                )

    assert privileged_jobs > 0

    release_workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert (
        "softprops/action-gh-release@"
        "3bb12739c298aeb8a4eeaf626c5b8d85266b0e65 # v2.6.2"
    ) in release_workflow


def test_release_tag_is_revalidated_immediately_before_publication() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    publish_job = _job_block(workflow, "publish-release")

    revalidate = publish_job.index(
        "- name: Revalidate release tag immediately before publication"
    )
    publish = publish_job.index("- name: Publish release and assets")
    assert revalidate < publish
    assert '"+refs/tags/${release_tag}:refs/tags/${release_tag}"' in publish_job
    assert 'git rev-parse "refs/tags/${release_tag}^{commit}"' in publish_job
    assert '[[ "$tag_commit" != "$GITHUB_SHA" ]]' in publish_job
    assert "target_commitish: ${{ github.sha }}" in publish_job


def test_apple_workflow_keeps_meshy_as_a_portable_expected_rejection() -> None:
    workflow = APPLE_WORKFLOW.read_text(encoding="utf-8")

    assert 'error.get("code") == "UNSUPPORTED_MATERIAL_NODES"' in workflow
    assert 'if [[ "$meshy_status" -eq 0 ]]' in workflow
    assert '"Specular Tint" in detail.get("message", "")' in workflow
    assert '"RealityKit Portable" in detail.get("message", "")' in workflow
    assert (
        'test ! -e "$APPLE_VALIDATION_DIR/exports/'
        'MeshyRiggedCharacter/MeshyRiggedCharacter.usdc"'
    ) in workflow

    compile_step = workflow.split(
        "      - name: Compile fresh export for every Apple 27 platform\n",
        maxsplit=1,
    )[1].split("\n      - name:", maxsplit=1)[0]
    runtime_step = workflow.split(
        "      - name: Load fresh and compiled assets with RealityKit 27\n",
        maxsplit=1,
    )[1].split("\n      - name:", maxsplit=1)[0]
    assert "MeshyRiggedCharacter" not in compile_step
    assert "MeshyRiggedCharacter" not in runtime_step

    assert "for asset_name in RedCube CubeWith4Animations Robot" in compile_step
    assert "exports/Robot/Robot.usdc" in runtime_step
    assert "compiled/macosx/Robot/Robot-macosx-27.0.reality" in runtime_step
    assert runtime_step.count("--expect-animation-key Animation") == 2
    assert runtime_step.count("--expect-animation-name Animation") == 2
    assert runtime_step.count("--expect-component MeshDeformerComponent") == 2
    assert runtime_step.count("--expect-component SkeletalPosesComponent") == 2
