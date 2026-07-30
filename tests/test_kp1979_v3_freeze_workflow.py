from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/kp1979-v3-freeze.yml"
CORE_COMMIT = "6eebc904a1bee3eaa05be619796cc6336bb2d10e"
CORE_USES = (
    f"megu0xxx0x/indus-open-benchmark/.github/workflows/kp1979-v3-freeze-core.yml@{CORE_COMMIT}"
)


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


class KP1979V3FreezeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.on_block = _block(cls.text, "on:")
        cls.dispatch_block = _block(cls.text, "  workflow_dispatch:")
        cls.jobs_block = _block(cls.text, "jobs:")
        cls.freeze_block = _block(cls.text, "  freeze:")

    def test_root_keys_and_only_manual_dispatch_are_exact(self) -> None:
        self.assertEqual(
            ["name", "on", "permissions", "jobs"],
            re.findall(r"(?m)^([a-z][a-z0-9_-]*):(?: .*)?$", self.text),
        )
        self.assertEqual(
            """on:
  workflow_dispatch:
    inputs:
      freeze_kind:
        description: Closed V3 artifact class
        required: true
        type: choice
        options:
          - control
          - detector
          - integration
      expected_sha256:
        description: Expected lowercase SHA-256 of the deterministic subject
        required: true
        type: string
""",
            self.on_block,
        )
        self.assertNotRegex(
            self.text,
            r"(?m)^\s*(?:push|pull_request|pull_request_target|schedule|workflow_call):",
        )
        self.assertNotIn("secrets:", self.text)
        self.assertNotIn("default:", self.dispatch_block)

    def test_dispatch_input_schema_is_closed_and_ordered(self) -> None:
        self.assertEqual(
            ["freeze_kind", "expected_sha256"],
            re.findall(r"(?m)^      ([a-z0-9_]+):$", self.dispatch_block),
        )
        freeze_kind = _block(self.text, "      freeze_kind:")
        expected_sha256 = _block(self.text, "      expected_sha256:")
        self.assertEqual(
            """      freeze_kind:
        description: Closed V3 artifact class
        required: true
        type: choice
        options:
          - control
          - detector
          - integration""",
            freeze_kind,
        )
        self.assertEqual(
            """      expected_sha256:
        description: Expected lowercase SHA-256 of the deterministic subject
        required: true
        type: string
""",
            expected_sha256,
        )

    def test_permission_ceiling_and_single_job_are_exact(self) -> None:
        self.assertEqual(
            ["freeze"],
            re.findall(r"(?m)^  ([a-z][a-z0-9_-]*):$", self.jobs_block),
        )
        self.assertEqual(2, len(re.findall(r"(?m)^\s*permissions:", self.text)))
        self.assertRegex(self.text, r"(?m)^permissions: \{\}$")
        self.assertEqual(
            """    permissions:
      contents: read
      id-token: write
      attestations: write""",
            _block(self.text, "    permissions:"),
        )
        self.assertEqual(
            ["name", "permissions", "uses", "with"],
            re.findall(r"(?m)^    ([a-z][a-z0-9_-]*):(?: .*)?$", self.freeze_block),
        )
        for forbidden in (
            "steps:",
            "run:",
            "runs-on:",
            "container:",
            "services:",
            "strategy:",
            "checkout@",
            "id-token: read",
            "contents: write",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_reusable_core_and_forwarded_inputs_are_exact(self) -> None:
        self.assertEqual(
            [CORE_USES],
            re.findall(r"(?m)^\s+uses: ([^\s]+)$", self.text),
        )
        self.assertRegex(CORE_COMMIT, r"\A[0-9a-f]{40}\Z")
        self.assertNotRegex(
            self.text,
            r"(?m)^\s+uses: [^\n]+@(?:main|master|HEAD|v[0-9]|refs/)",
        )
        self.assertEqual(
            """    with:
      freeze_kind: ${{ inputs.freeze_kind }}
      source_commit: ${{ github.sha }}
      expected_sha256: ${{ inputs.expected_sha256 }}""",
            _block(self.text, "    with:"),
        )
        self.assertEqual(
            [
                ("freeze_kind", "${{ inputs.freeze_kind }}"),
                ("source_commit", "${{ github.sha }}"),
                ("expected_sha256", "${{ inputs.expected_sha256 }}"),
            ],
            re.findall(r"(?m)^      ([a-z0-9_]+): (\$\{\{ [^}]+ \}\})$", self.freeze_block),
        )
        self.assertNotIn("github.event.inputs", self.text)

    def test_workflow_bytes_are_frozen(self) -> None:
        self.assertEqual(
            "aca066fc5df3565af831669b28ab661482dc0a21f319f6759fd912365c3f3442",
            hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
