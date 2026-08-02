from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEXT_FILES = (
    ROOT / "AGENTS.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "DATA_POLICY.md",
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "benchmark" / "numeral-metrology-functional-anchor-protocol-v1.json",
    ROOT / "benchmark" / "nmfa-value-blind-preregistration-evaluator-bundle-v1.json",
    ROOT / "benchmark" / "nmfa-value-blind-preregistration-gate-plan-v1.json",
    ROOT / "benchmark" / "nmfa-selector-core-evaluator-bundle-v1.json",
    ROOT / "benchmark" / "nmfa-selector-core-plan-v1.json",
)
PUBLIC_CODE_FILES = (
    ROOT / "src" / "indusbench" / "nmfa_preregistration.py",
    ROOT / "src" / "indusbench" / "nmfa_selector_core.py",
    ROOT / "src" / "indusbench" / "source_reported_link_static_v2.py",
    ROOT / "tests" / "test_numeral_metrology_functional_anchor_protocol.py",
    ROOT / "tests" / "test_nmfa_preregistration.py",
    ROOT / "tests" / "test_nmfa_selector_core.py",
    ROOT / "tests" / "test_source_reported_link_static_v2.py",
    ROOT / "tests" / "verify_nmfa_preregistration_installed_distribution.py",
    ROOT / "tests" / "verify_nmfa_selector_installed_distribution.py",
    ROOT / "tests" / "verify_source_reported_link_installed_distribution.py",
)
PUBLIC_TEXT_ROOTS = (ROOT / ".github", ROOT / "docs", ROOT / "registry", ROOT / "schemas")
TEXT_SUFFIXES = {".json", ".md", ".toml", ".yaml", ".yml"}

FORBIDDEN_PUBLIC_PATTERNS = {
    "absolute personal home path": re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+"),
    "SSH key path": re.compile(r"(?:\$HOME|~)?/\.ssh/"),
    "repository-specific Actions run URL": re.compile(
        r"https://github\.com/[^/\s]+/indus-open-benchmark/actions/runs/\d+"
    ),
    "machine topology": re.compile(r"\b(?:VPS|Navi)\b|iCloud|File Provider"),
    "local scan directory": re.compile(r"/tmp/indusbench[A-Za-z0-9._-]*"),
    "dated private data path": re.compile(
        r"data/(?:raw|derived)/[^\s`\"']*20\d{2}-\d{2}-\d{2}[^\s`\"']*"
    ),
    "literal IPv4 address": re.compile(
        r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
        r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)"
    ),
    "private key material": re.compile(r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
}

OPERATIONAL_PUBLIC_DOCS = (
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "DEVELOPMENT_PLAN_AND_LOG.md",
    ROOT / "docs" / "MUSEUM_INTAKE.md",
    ROOT / "docs" / "MUSEUM_REVIEW.md",
    ROOT / "docs" / "PUBLICATION_PRECHECK_2026-07-27.md",
    ROOT / "docs" / "ROADMAP.md",
    ROOT / "docs" / "SOURCES.md",
)


def public_text_paths() -> list[Path]:
    paths = [path for path in (*PUBLIC_TEXT_FILES, *PUBLIC_CODE_FILES) if path.exists()]
    for directory in PUBLIC_TEXT_ROOTS:
        paths.extend(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
        )
    return sorted(set(paths))


class PublicationBoundaryTests(unittest.TestCase):
    def test_public_text_has_no_machine_or_credential_metadata(self) -> None:
        findings: list[str] = []
        for path in public_text_paths():
            text = path.read_text(encoding="utf-8")
            for label, pattern in FORBIDDEN_PUBLIC_PATTERNS.items():
                if pattern.search(text):
                    findings.append(f"{path.relative_to(ROOT)}: {label}")
        self.assertEqual([], findings)

    def test_operational_docs_have_no_literal_sha256_commitment(self) -> None:
        literal_digest = re.compile(r"\bsha256:[0-9a-f]{64}\b")
        findings = [
            str(path.relative_to(ROOT))
            for path in OPERATIONAL_PUBLIC_DOCS
            if literal_digest.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual([], findings)

    def test_private_run_report_is_not_public(self) -> None:
        retired_name = "MUSEUM_PILOT_REPORT_2026-07-26.md"
        self.assertFalse((ROOT / "docs" / retired_name).exists())
        references = [
            str(path.relative_to(ROOT))
            for path in public_text_paths()
            if retired_name in path.read_text(encoding="utf-8")
        ]
        self.assertEqual([], references)

    def test_ai_only_checkpoint_has_no_private_execution_metadata(self) -> None:
        marker = "## KP1979 AI-only provisional extraction checkpoint"
        development_log = (ROOT / "docs" / "DEVELOPMENT_PLAN_AND_LOG.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(marker, development_log)
        checkpoint = development_log.split(marker, 1)[1]
        synthetic_result = (
            ROOT / "docs" / "KP1979_LABEL_LATTICE_SYNTHETIC_CONTROL_V1_RESULT_2026-07-29.md"
        ).read_text(encoding="utf-8")
        new_public_text = checkpoint + synthetic_result
        self.assertIsNone(
            re.search(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}|"
                r"private (?:source-pixel|aggregate) audit",
                new_public_text,
                flags=re.IGNORECASE,
            )
        )


if __name__ == "__main__":
    unittest.main()
