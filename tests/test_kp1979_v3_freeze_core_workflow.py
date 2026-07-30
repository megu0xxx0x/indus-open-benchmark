from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/kp1979-v3-freeze-core.yml"


def _block(text: str, marker: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index(marker)
    except ValueError as exc:
        raise AssertionError(f"missing workflow marker: {marker}") from exc
    indent = len(marker) - len(marker.lstrip())
    collected = [marker]
    for line in lines[start + 1 :]:
        if line and len(line) - len(line.lstrip()) <= indent:
            break
        collected.append(line)
    return "\n".join(collected)


class KP1979V3FreezeCoreWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.on_block = _block(cls.text, "on:")
        cls.jobs_block = _block(cls.text, "jobs:")
        cls.validate_block = _block(cls.text, "  validate:")
        cls.build_block = _block(cls.text, "  build:")
        cls.attest_block = _block(cls.text, "  attest:")

    def test_only_workflow_call_with_closed_required_string_inputs(self) -> None:
        self.assertIn("  workflow_call:", self.on_block)
        self.assertNotIn("workflow_dispatch:", self.text)
        self.assertNotRegex(self.text, r"(?m)^\s*(?:push|pull_request|schedule):")
        self.assertNotIn("    secrets:", self.on_block)
        self.assertNotIn("    outputs:", self.on_block)
        self.assertNotRegex(self.text, r"(?m)^\s+(?:continue-on-error|if):")
        self.assertEqual(
            ["freeze_kind", "source_commit", "expected_sha256"],
            re.findall(r"(?m)^      ([a-z0-9_]+):$", self.on_block),
        )
        for input_name in ("freeze_kind", "source_commit", "expected_sha256"):
            input_block = _block(self.text, f"      {input_name}:")
            self.assertRegex(input_block, r"(?m)^        required: true$")
            self.assertRegex(input_block, r"(?m)^        type: string$")
        self.assertRegex(self.text, r"(?m)^permissions: \{\}$")
        self.assertEqual(1, len(re.findall(r"(?m)^permissions:", self.text)))

    def test_global_environment_and_job_dag_are_exact(self) -> None:
        env_block = _block(self.text, "env:")
        expected_env = {
            "EXPECTED_SHA256": "${{ inputs.expected_sha256 }}",
            "FREEZE_KIND": "${{ inputs.freeze_kind }}",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONHASHSEED": '"0"',
            "SOURCE_COMMIT": "${{ inputs.source_commit }}",
            "SOURCE_DATE_EPOCH": '"0"',
            "TZ": "UTC",
        }
        observed_env = dict(re.findall(r"(?m)^  ([A-Z0-9_]+): (.+)$", env_block))
        self.assertEqual(expected_env, observed_env)
        self.assertEqual(
            ["validate", "build", "attest"],
            re.findall(r"(?m)^  ([^:\s][^:]*):$", self.jobs_block),
        )
        self.assertNotIn("needs:", self.validate_block)
        self.assertRegex(self.build_block, r"(?m)^    needs: validate$")
        self.assertRegex(self.attest_block, r"(?m)^    needs: build$")

    def test_validation_is_permissionless_and_precedes_every_build(self) -> None:
        self.assertRegex(self.validate_block, r"(?m)^    runs-on: ubuntu-24\.04$")
        self.assertRegex(self.validate_block, r"(?m)^    timeout-minutes: 5$")
        self.assertRegex(self.validate_block, r"(?m)^    permissions: \{\}$")
        self.assertNotIn("uses:", self.validate_block)
        self.assertIn("CALLER_SHA: ${{ github.sha }}", self.validate_block)
        self.assertIn("CALLER_EVENT_NAME: ${{ github.event_name }}", self.validate_block)
        self.assertIn("CALLER_REF: ${{ github.ref }}", self.validate_block)
        self.assertIn("CALLER_REPOSITORY: ${{ github.repository }}", self.validate_block)
        self.assertIn(
            "CALLER_WORKFLOW_REF: ${{ github.workflow_ref }}",
            self.validate_block,
        )
        self.assertIn(
            "CALLER_WORKFLOW_SHA: ${{ github.workflow_sha }}",
            self.validate_block,
        )
        self.assertIn("control|detector|integration", self.validate_block)
        self.assertIn('case "$SOURCE_COMMIT" in', self.validate_block)
        self.assertIn('*[!0-9a-f]*|"")', self.validate_block)
        self.assertIn('test "${#SOURCE_COMMIT}" -eq 40', self.validate_block)
        self.assertIn('case "$EXPECTED_SHA256" in', self.validate_block)
        self.assertIn('test "${#EXPECTED_SHA256}" -eq 64', self.validate_block)
        self.assertIn('test "$SOURCE_COMMIT" = "$CALLER_SHA"', self.validate_block)
        self.assertIn(
            'test "$CALLER_REPOSITORY" = "megu0xxx0x/indus-open-benchmark"',
            self.validate_block,
        )
        self.assertIn(
            'test "$CALLER_EVENT_NAME" = "workflow_dispatch"',
            self.validate_block,
        )
        self.assertIn(
            'test "$CALLER_WORKFLOW_SHA" = "$CALLER_SHA"',
            self.validate_block,
        )
        self.assertIn(
            "$CALLER_REPOSITORY/.github/workflows/kp1979-v3-freeze.yml@$CALLER_REF",
            self.validate_block,
        )
        self.assertIn(
            'expected_ref_prefix="refs/heads/freeze/kp1979-v3-$FREEZE_KIND-"',
            self.validate_block,
        )
        self.assertIn('"$expected_ref_prefix"?*)', self.validate_block)
        self.assertLess(self.text.index("  validate:"), self.text.index("  build:"))
        self.assertEqual(
            ["Validate inputs and caller identity"],
            re.findall(r"(?m)^      - name: (.+)$", self.validate_block),
        )
        self.assertEqual(1, len(re.findall(r"(?m)^      - ", self.validate_block)))

    def test_build_replicas_have_only_read_access_and_exact_tools(self) -> None:
        self.assertRegex(self.build_block, r"(?m)^    runs-on: ubuntu-24\.04$")
        self.assertRegex(self.build_block, r"(?m)^    timeout-minutes: 30$")
        self.assertRegex(
            self.build_block,
            r"(?m)^    permissions:\n      contents: read\n    strategy:$",
        )
        self.assertNotIn("id-token:", self.build_block)
        self.assertNotIn("attestations:", self.build_block)
        self.assertIn("fail-fast: false", self.build_block)
        self.assertEqual(
            "      matrix:\n        replica: [a, b]",
            _block(self.text, "      matrix:"),
        )
        self.assertIn("persist-credentials: false", self.build_block)
        self.assertIn("ref: ${{ inputs.source_commit }}", self.build_block)
        self.assertIn('test "$(git rev-parse HEAD)" = "$SOURCE_COMMIT"', self.build_block)
        self.assertIn('python-version: "3.12.11"', self.build_block)
        self.assertIn('version: "0.11.7"', self.build_block)
        self.assertIn("uv sync --locked --extra dev", self.build_block)
        self.assertEqual(
            2,
            self.build_block.count("UV_PROJECT_ENVIRONMENT: ${{ runner.temp }}/kp1979-v3-venv"),
        )
        self.assertEqual(
            [
                "Check out the exact source commit",
                "Verify the checked-out identity",
                "Set up exact Python",
                "Set up exact uv",
                "Install the locked development environment",
                "Build and verify the deterministic subject twice",
                "Retain this source replica",
            ],
            re.findall(r"(?m)^      - name: (.+)$", self.build_block),
        )
        self.assertEqual(7, len(re.findall(r"(?m)^      - ", self.build_block)))

    def test_actions_are_full_sha_pins_in_exact_order_with_duplicates(self) -> None:
        expected = [
            (
                "actions/checkout",
                "3d3c42e5aac5ba805825da76410c181273ba90b1",
                "v7.0.1",
            ),
            (
                "actions/setup-python",
                "5fda3b95a4ea91299a34e894583c3862153e4b97",
                "v7.0.0",
            ),
            (
                "astral-sh/setup-uv",
                "08807647e7069bb48b6ef5acd8ec9567f424441b",
                "v8.1.0",
            ),
            (
                "actions/upload-artifact",
                "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
                "v7.0.1",
            ),
            (
                "actions/download-artifact",
                "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
                "v8.0.1",
            ),
            (
                "actions/download-artifact",
                "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
                "v8.0.1",
            ),
            (
                "actions/attest",
                "508db95dd578ae2727ebd6217d5ba78e4fbda05d",
                "v4.2.1",
            ),
            (
                "actions/upload-artifact",
                "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
                "v7.0.1",
            ),
        ]
        observed = re.findall(
            r"(?m)^\s+uses: ([a-z0-9-]+/[a-z0-9-]+)@([0-9a-f]{40}) # (v[0-9.]+)$",
            self.text,
        )
        self.assertEqual(expected, observed)
        self.assertEqual(len(expected), len(re.findall(r"(?m)^\s+uses:", self.text)))

    def test_builder_mapping_reproducibility_tree_and_digest_are_closed(self) -> None:
        expected_pairs = [
            (
                "kp1979-v3-control-bundle.tar.gz",
                "indusbench.kp1979_v3_control_freeze",
            ),
            (
                "kp1979-v3-detector.pyz",
                "indusbench.kp1979_v3_detector_freeze",
            ),
            (
                "kp1979-v3-integration-binding.json",
                "indusbench.kp1979_v3_integration_freeze",
            ),
        ]
        observed_pairs = re.findall(
            r"subject_name=([a-z0-9.-]+)\n\s+module=([a-z0-9_.]+)",
            self.build_block,
        )
        self.assertEqual(expected_pairs, observed_pairs)
        self.assertEqual(
            ["16777216", "8388608", "65536"],
            re.findall(r"(?m)^\s+max_bytes=([0-9]+)$", self.build_block),
        )
        self.assertEqual(
            2,
            self.build_block.count('"$UV_PROJECT_ENVIRONMENT/bin/python" -s -B -m "$module"'),
        )
        self.assertEqual(2, self.build_block.count("env -i LANG=C.UTF-8"))
        for allowed_environment in (
            "LC_ALL=C.UTF-8",
            'PATH="$UV_PROJECT_ENVIRONMENT/bin:/usr/bin:/bin"',
            "PYTHONHASHSEED=0",
            "PYTHONNOUSERSITE=1",
            'SOURCE_COMMIT="$SOURCE_COMMIT"',
            "SOURCE_DATE_EPOCH=0",
            "TZ=UTC",
        ):
            self.assertEqual(2, self.build_block.count(allowed_environment))
        for excluded_environment in (
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
            "ACTIONS_ID_TOKEN_REQUEST_URL",
            "GITHUB_ENV",
            "GITHUB_PATH",
            "GITHUB_STEP_SUMMARY",
            "GITHUB_TOKEN",
        ):
            self.assertNotIn(excluded_environment, self.build_block)
        self.assertNotIn('HOME="$HOME"', self.build_block)
        self.assertNotIn(" -I ", self.build_block)
        self.assertIn(
            "'import sys; print(\".\".join(map(str, sys.version_info[:3])))'",
            self.build_block,
        )
        self.assertIn('build_root="$RUNNER_TEMP/kp1979-v3-build"', self.build_block)
        self.assertIn(
            'cmp -- "$build_one/$subject_name" "$build_two/$subject_name"',
            self.build_block,
        )
        self.assertIn(
            'test -z "$(git status --porcelain)"',
            self.build_block,
        )
        self.assertIn("git diff --quiet --", self.build_block)
        self.assertIn("git diff --cached --quiet --", self.build_block)
        digest_check = 'test "$actual_sha256" = "$EXPECTED_SHA256"'
        self.assertIn(digest_check, self.build_block)
        self.assertLess(
            self.build_block.index(digest_check),
            self.build_block.index("Retain this source replica"),
        )
        self.assertIn(
            "name: kp1979-v3-${{ inputs.freeze_kind }}-"
            "${{ inputs.source_commit }}-${{ matrix.replica }}",
            self.build_block,
        )
        self.assertIn(
            "path: ${{ steps.build_subject.outputs.subject_path }}",
            self.build_block,
        )

    def test_attest_job_is_fresh_code_free_and_has_only_attestation_permissions(self) -> None:
        self.assertRegex(self.attest_block, r"(?m)^    runs-on: ubuntu-24\.04$")
        self.assertRegex(self.attest_block, r"(?m)^    timeout-minutes: 30$")
        self.assertRegex(
            self.attest_block,
            (
                r"(?m)^    permissions:\n"
                r"      contents: read\n"
                r"      id-token: write\n"
                r"      attestations: write\n"
                r"    steps:$"
            ),
        )
        for forbidden in (
            "actions/checkout@",
            "actions/setup-python@",
            "astral-sh/setup-uv@",
            "uv sync",
            "uv run",
            "indusbench.",
            "git ",
            "python ",
            "bash ",
            "sh ",
            "chmod ",
            "eval ",
            "source ",
            "tar ",
            "unzip ",
            "gunzip ",
            "node ",
            "perl ",
            "ruby ",
            "curl ",
            "wget ",
            "./",
        ):
            self.assertNotIn(forbidden, self.attest_block)
        self.assertNotIn("secrets.", self.text)
        self.assertEqual(1, self.build_block.count("actions/upload-artifact@"))
        self.assertEqual(2, self.attest_block.count("actions/download-artifact@"))
        self.assertEqual(1, self.attest_block.count("actions/attest@"))
        self.assertEqual(1, self.attest_block.count("actions/upload-artifact@"))
        self.assertEqual(
            [
                "Download replica A",
                "Download replica B",
                "Verify and stage the identical subject",
                "Generate the subject attestation",
                "Verify and stage the attestation bundle",
                "Retain the attestation bundle",
            ],
            re.findall(r"(?m)^      - name: (.+)$", self.attest_block),
        )
        self.assertEqual(6, len(re.findall(r"(?m)^      - ", self.attest_block)))
        self.assertRegex(
            self.attest_block,
            (
                r"(?s)      - name: Verify and stage the identical subject\n"
                r".*?\n      - name: Generate the subject attestation\n"
            ),
        )

    def test_attestation_checks_precede_signing_and_bundle_is_retained(self) -> None:
        self.assertIn(
            "name: kp1979-v3-${{ inputs.freeze_kind }}-${{ inputs.source_commit }}-a",
            self.attest_block,
        )
        self.assertIn(
            "name: kp1979-v3-${{ inputs.freeze_kind }}-${{ inputs.source_commit }}-b",
            self.attest_block,
        )
        self.assertEqual(
            [
                "kp1979-v3-control-bundle.tar.gz",
                "kp1979-v3-detector.pyz",
                "kp1979-v3-integration-binding.json",
            ],
            re.findall(r"(?m)^\s+subject_name=([a-z0-9.-]+)$", self.attest_block),
        )
        self.assertIn("path: replicas/a", self.attest_block)
        self.assertIn("path: replicas/b", self.attest_block)
        self.assertEqual(
            ["16777216", "8388608", "65536"],
            re.findall(r"(?m)^\s+max_bytes=([0-9]+)$", self.attest_block),
        )
        self.assertEqual(
            [("2", "1f8b"), ("4", "504b0304"), ("1", "7b")],
            re.findall(
                r"magic_bytes=([0-9]+)\n\s+expected_magic=([0-9a-f]+)",
                self.attest_block,
            ),
        )
        for required in (
            'test "$(find "$replica_dir" -mindepth 1 -maxdepth 1 -printf x | wc -c)" -eq 1',
            'test -f "$candidate"',
            'test ! -L "$candidate"',
            'test "$(stat -c %F -- "$candidate")" = "regular file"',
            'cmp -- "replicas/a/$subject_name" "replicas/b/$subject_name"',
            'test "$observed_magic" = "$expected_magic"',
            'test "$actual_sha256" = "$EXPECTED_SHA256"',
            'subject_path="attestation-subject/$subject_name"',
        ):
            self.assertIn(required, self.attest_block)
        signing = self.attest_block.index("Generate the subject attestation")
        self.assertLess(
            self.attest_block.index('cmp -- "replicas/a/$subject_name" "replicas/b/$subject_name"'),
            signing,
        )
        self.assertLess(
            self.attest_block.index('test "$observed_magic" = "$expected_magic"'),
            signing,
        )
        self.assertLess(
            self.attest_block.index('test "$actual_sha256" = "$EXPECTED_SHA256"'),
            signing,
        )
        self.assertIn("id: attestation", self.attest_block)
        self.assertIn(
            "subject-path: ${{ steps.verify_subject.outputs.subject_path }}",
            self.attest_block,
        )
        for output in ("bundle-path", "attestation-id", "attestation-url"):
            self.assertIn(f"${{{{ steps.attestation.outputs.{output} }}}}", self.attest_block)
        for variable in (
            "ATTESTATION_BUNDLE_PATH",
            "ATTESTATION_ID",
            "ATTESTATION_URL",
        ):
            self.assertIn(f'test -n "${variable}"', self.attest_block)
        self.assertIn(
            '"https://github.com/$GITHUB_REPOSITORY/attestations/$ATTESTATION_ID"',
            self.attest_block,
        )
        self.assertIn(
            'sha256sum "$ATTESTED_SUBJECT_PATH"',
            self.attest_block,
        )
        self.assertIn('test -f "$ATTESTATION_BUNDLE_PATH"', self.attest_block)
        self.assertIn('test ! -L "$ATTESTATION_BUNDLE_PATH"', self.attest_block)
        self.assertIn(
            'test "$(stat -c %F -- "$ATTESTATION_BUNDLE_PATH")" = "regular file"',
            self.attest_block,
        )
        self.assertIn('test "$bundle_size" -le 16777216', self.attest_block)
        self.assertIn(
            "jq -e -s 'length >= 1 and all(.[]; type == \"object\")'",
            self.attest_block,
        )
        self.assertLess(
            signing,
            self.attest_block.index("Verify and stage the attestation bundle"),
        )
        self.assertIn(
            "name: kp1979-v3-attestation-${{ inputs.freeze_kind }}-${{ inputs.source_commit }}",
            self.attest_block,
        )
        self.assertIn(
            "path: ${{ steps.verify_attestation.outputs.bundle_path }}",
            self.attest_block,
        )
        self.assertEqual(2, self.text.count("retention-days: 90"))
        self.assertEqual(2, self.text.count("compression-level: 0"))
        self.assertEqual(2, self.text.count("if-no-files-found: error"))

    def test_workflow_bytes_are_frozen(self) -> None:
        self.assertEqual(
            "9bd93bed5359bd8cb396a0f6be063b5bc6f76ad1b84e1d6338e1edc14ae0300a",
            hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
