"""Regression coverage for the protected Apple runner trust boundary.

Every assertion here runs against the real ``.github/workflows`` artifacts:
structural policy is checked on the PyYAML-parsed workflow documents, and the
authorization semantics are checked by executing the actual bash policy script
extracted from the parsed workflow against fixture git repositories. Editing a
workflow in a way that violates the trust policy therefore fails these tests.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIRECTORY = ROOT / ".github/workflows"
APPLE_WORKFLOW = ROOT / ".github/workflows/apple-platform-validation.yml"
RELEASE_WORKFLOW = ROOT / ".github/workflows/build-archive.yml"
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
EXPECTED_REPOSITORY = "tomkrikorian/BlenderToRCP"
FULL_COMMIT_ACTION_REF = re.compile(r"[^\s@]+@[0-9a-f]{40}")
ZERO_SHA = "0" * 40

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "trust-policy-test",
    "GIT_AUTHOR_EMAIL": "trust-policy-test@example.invalid",
    "GIT_COMMITTER_NAME": "trust-policy-test",
    "GIT_COMMITTER_EMAIL": "trust-policy-test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def _load_workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML implements YAML 1.1, where a bare `on` key parses as boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), "workflow triggers must be a mapping"
    return triggers


def _steps_by_name(job: dict) -> dict[str, dict]:
    return {step["name"]: step for step in job["steps"] if "name" in step}


def _run_scripts(workflow: dict) -> list[tuple[str, str]]:
    """Return every (job_id, run-script) pair defined by a workflow."""

    scripts = []
    for job_id, job in workflow.get("jobs", {}).items():
        for step in job.get("steps", []) or []:
            if isinstance(step.get("run"), str):
                scripts.append((job_id, step["run"]))
    return scripts


# ---------------------------------------------------------------------------
# Static policy checkers. Each returns human-readable violations so the same
# checker can be proven to catch tampered workflow fixtures.
# ---------------------------------------------------------------------------


def _apple_entrypoint_violations(workflow: dict) -> list[str]:
    triggers = _triggers(workflow)
    violations = []
    if "workflow_call" not in triggers:
        violations.append("missing workflow_call trigger")
    for forbidden in ("workflow_dispatch", "pull_request", "pull_request_target"):
        if forbidden in triggers:
            violations.append(f"forbidden direct entrypoint: {forbidden}")
    push = triggers.get("push")
    if not isinstance(push, dict) or push.get("branches") != ["dev"]:
        violations.append("push trigger must be restricted to the dev branch")
    return violations


def _privileged_action_pins(workflow: dict) -> tuple[list[str], list[str]]:
    """Return (privileged job ids, unpinned third-party refs they use)."""

    privileged_jobs = []
    violations = []
    for job_id, job in workflow.get("jobs", {}).items():
        permissions = job.get("permissions") or {}
        if permissions.get("contents") != "write":
            continue
        privileged_jobs.append(job_id)
        for step in job.get("steps", []) or []:
            action_ref = step.get("uses")
            if not action_ref or action_ref.startswith(("actions/", "./")):
                continue
            if not FULL_COMMIT_ACTION_REF.fullmatch(action_ref):
                violations.append(f"{job_id}: {action_ref}")
    return privileged_jobs, violations


def _inert_diff_check_lines(workflow: dict) -> list[str]:
    """Find bare `git diff --check` invocations, which can never fail in CI."""

    violations = []
    for job_id, script in _run_scripts(workflow):
        for line in script.splitlines():
            if re.fullmatch(r"\s*git diff --check\s*", line):
                violations.append(f"{job_id}: {line.strip()}")
    return violations


# ---------------------------------------------------------------------------
# Behavioral harness: execute the real authorization script from the workflow.
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **_GIT_ENV},
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _authorization_policy() -> tuple[dict, str]:
    """Extract (job env, policy script) from the real Apple workflow."""

    job = _load_workflow(APPLE_WORKFLOW)["jobs"]["authorize-apple-revision"]
    policy_step = next(
        step for step in job["steps"] if step.get("id") == "policy"
    )
    return job["env"], policy_step["run"]


def _build_policy_fixture(
    tmp_path: Path,
    *,
    ref: str,
    manifest_version: str,
    is_dev_ancestor: bool,
    tag_resolves_to_sha: bool,
) -> tuple[Path, str]:
    """Create origin + checkout repositories mirroring the runner state."""

    origin = tmp_path / "origin"
    origin.mkdir()
    _git("init", "-q", "-b", "dev", cwd=origin)
    manifest = origin / "Plugin/blender_manifest.toml"
    manifest.parent.mkdir()
    manifest.write_text(f'version = "{manifest_version}"\n', encoding="utf-8")
    _git("add", "-A", cwd=origin)
    _git("commit", "-q", "-m", "base", cwd=origin)
    base_sha = _git("rev-parse", "HEAD", cwd=origin)

    _git("switch", "-q", "-c", "candidate", cwd=origin)
    (origin / "candidate.txt").write_text("candidate change\n", encoding="utf-8")
    _git("add", "-A", cwd=origin)
    _git("commit", "-q", "-m", "candidate", cwd=origin)
    requested_sha = _git("rev-parse", "HEAD", cwd=origin)

    if is_dev_ancestor:
        _git("branch", "-f", "dev", "candidate", cwd=origin)

    if ref.startswith("refs/tags/"):
        tag_name = ref[len("refs/tags/"):]
        tag_target = requested_sha if tag_resolves_to_sha else base_sha
        _git("tag", tag_name, tag_target, cwd=origin)

    work = tmp_path / "work"
    _git("clone", "-q", str(origin), str(work), cwd=tmp_path)
    _git("checkout", "-q", requested_sha, cwd=work)
    return work, requested_sha


def _run_authorization_policy(
    tmp_path: Path,
    *,
    event: str,
    ref: str,
    ref_type: str,
    repository: str = EXPECTED_REPOSITORY,
    manifest_version: str = "2.0.0",
    is_dev_ancestor: bool = True,
    tag_resolves_to_sha: bool = True,
) -> bool:
    """Run the workflow's real policy script against a fixture repository."""

    tmp_path.mkdir(parents=True, exist_ok=True)
    job_env, script = _authorization_policy()
    work, requested_sha = _build_policy_fixture(
        tmp_path,
        ref=ref,
        manifest_version=manifest_version,
        is_dev_ancestor=is_dev_ancestor,
        tag_resolves_to_sha=tag_resolves_to_sha,
    )
    github_output = tmp_path / "github-output"
    github_output.touch()

    # The heredoc in the script calls `python3`, which must support tomllib;
    # pin it to the interpreter running this test suite via a PATH shim.
    shim_dir = tmp_path / "python-shim"
    shim_dir.mkdir()
    (shim_dir / "python3").symlink_to(sys.executable)
    env = {
        **os.environ,
        **_GIT_ENV,
        "PATH": os.pathsep.join([str(shim_dir), os.environ["PATH"]]),
        "EXPECTED_REPOSITORY": job_env["EXPECTED_REPOSITORY"],
        "REQUESTED_REPOSITORY": repository,
        "REQUESTED_EVENT": event,
        "REQUESTED_REF": ref,
        "REQUESTED_REF_TYPE": ref_type,
        "REQUESTED_SHA": requested_sha,
        "GITHUB_OUTPUT": str(github_output),
    }
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
    )
    outputs = dict(
        line.split("=", maxsplit=1)
        for line in github_output.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    authorized = result.returncode == 0 and outputs.get("authorized") == "true"
    if authorized:
        # An authorization must always hand the protected runner the exact
        # immutable commit that was validated.
        assert outputs.get("authorized_sha") == requested_sha, outputs
    else:
        assert result.returncode != 0, (result.stdout, result.stderr)
        assert "authorized=true" not in github_output.read_text(encoding="utf-8")
    return authorized


# ---------------------------------------------------------------------------
# Structural policy on the real workflow documents.
# ---------------------------------------------------------------------------


def test_apple_workflow_has_no_direct_manual_or_pull_request_entrypoint() -> None:
    assert _apple_entrypoint_violations(_load_workflow(APPLE_WORKFLOW)) == []


def test_policy_checker_catches_reintroduced_apple_entrypoints() -> None:
    """Prove the checker fails when a workflow copy violates the policy."""

    source = APPLE_WORKFLOW.read_text(encoding="utf-8")

    tampered_triggers = source.replace(
        "on:\n  workflow_call:\n",
        "on:\n  workflow_call:\n  workflow_dispatch:\n  pull_request_target:\n",
    )
    assert tampered_triggers != source
    violations = _apple_entrypoint_violations(yaml.safe_load(tampered_triggers))
    assert "forbidden direct entrypoint: workflow_dispatch" in violations
    assert "forbidden direct entrypoint: pull_request_target" in violations

    tampered_branches = source.replace(
        "    branches: [dev]\n",
        '    branches: [dev, "**"]\n',
    )
    assert tampered_branches != source
    assert _apple_entrypoint_violations(yaml.safe_load(tampered_branches)) == [
        "push trigger must be restricted to the dev branch"
    ]


def test_self_hosted_job_consumes_only_authorized_immutable_sha() -> None:
    workflow = _load_workflow(APPLE_WORKFLOW)
    authorization = workflow["jobs"]["authorize-apple-revision"]
    protected = workflow["jobs"]["apple-27"]

    # The policy job must run on an ephemeral GitHub-hosted runner and read
    # the caller identity exclusively from the GitHub context.
    assert authorization["runs-on"] == "ubuntu-24.04"
    assert authorization["env"]["EXPECTED_REPOSITORY"] == EXPECTED_REPOSITORY
    assert authorization["env"]["REQUESTED_REPOSITORY"] == "${{ github.repository }}"
    assert authorization["env"]["REQUESTED_EVENT"] == "${{ github.event_name }}"
    assert authorization["env"]["REQUESTED_REF"] == "${{ github.ref }}"
    assert authorization["env"]["REQUESTED_REF_TYPE"] == "${{ github.ref_type }}"
    assert authorization["env"]["REQUESTED_SHA"] == "${{ github.sha }}"

    _, script = _authorization_policy()
    assert '"refs/heads/dev"' in script
    assert "^refs/tags/" in script
    assert "manifest_version" in script
    assert "git merge-base --is-ancestor" in script
    assert "refs/remotes/origin/dev" in script
    assert "authorized_sha=$requested_commit" in script

    assert protected["needs"] == "authorize-apple-revision"
    assert protected["if"] == (
        "needs.authorize-apple-revision.outputs.authorized == 'true'"
    )
    assert "self-hosted" in protected["runs-on"]

    checkout = protected["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["ref"] == (
        "${{ needs.authorize-apple-revision.outputs.authorized_sha }}"
    )


def test_release_workflow_is_the_only_manual_entry_and_calls_canonical_dev_policy() -> None:
    workflow = _load_workflow(RELEASE_WORKFLOW)
    triggers = _triggers(workflow)
    metadata = workflow["jobs"]["validate-release-metadata"]
    apple_call = workflow["jobs"]["apple-27-quality-gate"]

    assert "workflow_dispatch" in triggers

    metadata_scripts = "\n".join(
        step["run"] for step in metadata["steps"] if isinstance(step.get("run"), str)
    )
    assert '"refs/heads/dev"' in metadata_scripts
    assert '"refs/tags/$RELEASE_TAG"' in metadata_scripts
    assert "git merge-base --is-ancestor" in metadata_scripts
    assert "refs/remotes/origin/dev" in metadata_scripts

    assert apple_call["needs"] == "validate-release-metadata"
    assert apple_call["uses"] == (
        "tomkrikorian/BlenderToRCP/"
        ".github/workflows/apple-platform-validation.yml@dev"
    )


# ---------------------------------------------------------------------------
# Behavioral policy: the real bash script, executed against fixture repos.
# ---------------------------------------------------------------------------


def test_manual_dispatch_from_arbitrary_branch_is_rejected(tmp_path: Path) -> None:
    assert not _run_authorization_policy(
        tmp_path,
        event="workflow_dispatch",
        ref="refs/heads/feature/untrusted-runner-code",
        ref_type="branch",
    )


def test_reusable_call_inherits_and_rejects_unvalidated_caller_ref(
    tmp_path: Path,
) -> None:
    # Reusable workflows see the caller's original event/ref. This models a
    # workflow_call reached from an otherwise valid push event on an untrusted
    # branch; the branch must not be allowed to allocate the Apple runner.
    assert not _run_authorization_policy(
        tmp_path,
        event="push",
        ref="refs/heads/feature/unvalidated-caller",
        ref_type="branch",
    )


def test_trusted_dev_and_exact_release_revisions_are_allowed(tmp_path: Path) -> None:
    assert _run_authorization_policy(
        tmp_path / "push-dev",
        event="push",
        ref="refs/heads/dev",
        ref_type="branch",
    )
    assert _run_authorization_policy(
        tmp_path / "dispatch-dev",
        event="workflow_dispatch",
        ref="refs/heads/dev",
        ref_type="branch",
    )
    assert _run_authorization_policy(
        tmp_path / "push-tag",
        event="push",
        ref="refs/tags/2.0.0",
        ref_type="tag",
    )


def test_release_policy_fails_closed_on_identity_version_and_ancestry(
    tmp_path: Path,
) -> None:
    base = {
        "event": "push",
        "ref": "refs/tags/2.0.0",
        "ref_type": "tag",
    }

    assert not _run_authorization_policy(
        tmp_path / "fork", repository="someone/fork", **base
    )
    assert not _run_authorization_policy(
        tmp_path / "manifest-mismatch", manifest_version="2.0.1", **base
    )
    assert not _run_authorization_policy(
        tmp_path / "not-ancestor", is_dev_ancestor=False, **base
    )
    assert not _run_authorization_policy(
        tmp_path / "moved-tag", tag_resolves_to_sha=False, **base
    )
    assert not _run_authorization_policy(
        tmp_path / "v-prefix",
        event="push",
        ref="refs/tags/v2.0.0",
        ref_type="tag",
    )
    assert not _run_authorization_policy(
        tmp_path / "zero-padded",
        event="push",
        ref="refs/tags/02.0.0",
        ref_type="tag",
        manifest_version="02.0.0",
    )


def test_ref_type_must_match_the_presented_ref(tmp_path: Path) -> None:
    assert not _run_authorization_policy(
        tmp_path / "dev-as-tag",
        event="push",
        ref="refs/heads/dev",
        ref_type="tag",
    )
    assert not _run_authorization_policy(
        tmp_path / "tag-as-branch",
        event="push",
        ref="refs/tags/2.0.0",
        ref_type="branch",
    )


# ---------------------------------------------------------------------------
# Release-write hygiene across every workflow document.
# ---------------------------------------------------------------------------


def test_privileged_jobs_pin_third_party_actions_to_full_commit_shas() -> None:
    """A mutable action tag must never receive release-write authority."""

    privileged_jobs: list[str] = []
    violations: list[str] = []
    for workflow_path in sorted(WORKFLOW_DIRECTORY.glob("*.yml")):
        workflow = _load_workflow(workflow_path)
        jobs, unpinned = _privileged_action_pins(workflow)
        privileged_jobs.extend(f"{workflow_path.name}:{job_id}" for job_id in jobs)
        violations.extend(f"{workflow_path.name}:{ref}" for ref in unpinned)

    assert privileged_jobs
    assert violations == []

    release_workflow = _load_workflow(RELEASE_WORKFLOW)
    publish_steps = _steps_by_name(release_workflow["jobs"]["publish-release"])
    assert publish_steps["Publish release and assets"]["uses"] == (
        "softprops/action-gh-release@3bb12739c298aeb8a4eeaf626c5b8d85266b0e65"
    )
    # Keep the human-readable version breadcrumb next to the pin.
    assert (
        "softprops/action-gh-release@"
        "3bb12739c298aeb8a4eeaf626c5b8d85266b0e65 # v2.6.2"
    ) in RELEASE_WORKFLOW.read_text(encoding="utf-8")


def test_policy_checker_catches_unpinned_privileged_action() -> None:
    """Prove the pin checker fails when a workflow copy drops the SHA pin."""

    source = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    _, violations = _privileged_action_pins(yaml.safe_load(source))
    assert violations == []

    tampered = source.replace(
        "softprops/action-gh-release@"
        "3bb12739c298aeb8a4eeaf626c5b8d85266b0e65 # v2.6.2",
        "softprops/action-gh-release@v2",
    )
    assert tampered != source
    _, violations = _privileged_action_pins(yaml.safe_load(tampered))
    assert violations == ["publish-release: softprops/action-gh-release@v2"]


def test_release_tag_is_revalidated_immediately_before_publication() -> None:
    workflow = _load_workflow(RELEASE_WORKFLOW)
    publish_job = workflow["jobs"]["publish-release"]
    step_names = [step["name"] for step in publish_job["steps"] if "name" in step]

    revalidate_name = "Revalidate release tag immediately before publication"
    publish_name = "Publish release and assets"
    assert step_names.index(revalidate_name) < step_names.index(publish_name)

    steps = _steps_by_name(publish_job)
    revalidate_script = steps[revalidate_name]["run"]
    assert '"+refs/tags/${release_tag}:refs/tags/${release_tag}"' in revalidate_script
    assert 'git rev-parse "refs/tags/${release_tag}^{commit}"' in revalidate_script
    assert '[[ "$tag_commit" != "$GITHUB_SHA" ]]' in revalidate_script
    assert steps[publish_name]["with"]["target_commitish"] == "${{ github.sha }}"


# ---------------------------------------------------------------------------
# CI whitespace gate: `git diff --check` must diff the change under test.
# ---------------------------------------------------------------------------


def test_no_workflow_runs_an_inert_bare_git_diff_check() -> None:
    for workflow_path in sorted(WORKFLOW_DIRECTORY.glob("*.yml")):
        assert _inert_diff_check_lines(_load_workflow(workflow_path)) == [], (
            f"{workflow_path.name} runs a bare `git diff --check`, which "
            "compares a pristine checkout to its index and can never fail"
        )


def test_policy_checker_catches_inert_bare_git_diff_check() -> None:
    tampered = yaml.safe_load(
        "jobs:\n"
        "  unit-tests:\n"
        "    steps:\n"
        "      - name: Check repository\n"
        "        run: |\n"
        "          git diff --check\n"
        "          echo done\n"
    )
    assert _inert_diff_check_lines(tampered) == ["unit-tests: git diff --check"]


def test_ci_whitespace_gate_diffs_the_revision_under_test() -> None:
    workflow = _load_workflow(CI_WORKFLOW)
    job = workflow["jobs"]["unit-tests"]

    checkout = job["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    # The gate needs history to resolve the PR base, the push predecessor,
    # and origin/dev; a depth-1 clone would make every base unreachable.
    assert checkout["with"]["fetch-depth"] == 0

    gate = _steps_by_name(job)["Check whitespace introduced by this revision"]
    assert gate["env"]["EVENT_NAME"] == "${{ github.event_name }}"
    assert gate["env"]["PR_BASE_REF"] == "${{ github.base_ref }}"
    assert gate["env"]["PUSH_BEFORE"] == "${{ github.event.before }}"

    script = gate["run"]
    assert 'git merge-base "refs/remotes/origin/${PR_BASE_REF}" HEAD' in script
    assert f'"$PUSH_BEFORE" != {ZERO_SHA}' in script
    assert "git merge-base refs/remotes/origin/dev HEAD" in script
    assert 'git diff --check "$base" HEAD' in script


# ---------------------------------------------------------------------------
# The portable Specular Tint rejection stays wired into the Apple lane.
# ---------------------------------------------------------------------------


def test_apple_workflow_keeps_a_portable_expected_rejection() -> None:
    workflow = _load_workflow(APPLE_WORKFLOW)
    steps = _steps_by_name(workflow["jobs"]["apple-27"])

    export_step = steps["Export portable fixtures and assert the Specular Tint rejection"]["run"]
    assert 'error.get("code") == "UNSUPPORTED_MATERIAL_NODES"' in export_step
    assert 'if [[ "$tint_status" -eq 0 ]]' in export_step
    assert '"Specular Tint" in detail.get("message", "")' in export_step
    assert '"RealityKit Portable" in detail.get("message", "")' in export_step
    # The refusal comes from the material, so the whole scene has to be exported.
    # Under --selected-only this scene yields NO_EXPORTABLE_OBJECTS instead - the
    # step's own assertion then fails while the workflow still looks reasonable.
    assert "--selected-only" not in export_step
    assert (
        'test ! -e "$APPLE_VALIDATION_DIR/exports/'
        'SpecularTint/SpecularTint.usdc"'
    ) in export_step

    compile_step = steps["Compile fresh export for every Apple 27 platform"]["run"]
    runtime_step = steps["Load fresh and compiled assets with RealityKit 27"]["run"]
    assert "SpecularTint" not in compile_step
    assert "SpecularTint" not in runtime_step

    assert "for asset_name in RedCube CubeWith4Animations SkinnedLimb" in compile_step
    assert "exports/SkinnedLimb/SkinnedLimb.usdc" in runtime_step
    assert "compiled/macosx/SkinnedLimb/SkinnedLimb-macosx-27.0.reality" in runtime_step
    assert runtime_step.count("--expect-animation-key Bend") == 2
    assert runtime_step.count("--expect-animation-name Bend") == 2
    assert runtime_step.count("--expect-component MeshDeformerComponent") == 2
    assert runtime_step.count("--expect-component SkeletalPosesComponent") == 2
