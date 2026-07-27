from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from indusbench.quarantine import (
    CorpusQuarantineError,
    inspect_corpus_quarantine,
    quarantine_manifest_digest,
    require_corpus_permitted,
    validate_quarantine_manifest,
)
from indusbench.schema_validation import validate_schema_instance
from tests.test_validation import valid_artifact

ROOT = Path(__file__).resolve().parents[1]
QUARANTINE_PATH = ROOT / "registry" / "quarantine.json"
SOURCE_REGISTRY_PATH = ROOT / "registry" / "sources.json"
RESEARCH_REGISTRY_PATH = ROOT / "registry" / "research_landscape.json"
SCHEMA_PATH = ROOT / "schemas" / "quarantine-manifest.schema.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class QuarantineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load(QUARANTINE_PATH)
        cls.sources = load(SOURCE_REGISTRY_PATH)

    def test_checked_in_manifest_is_closed_content_addressed_and_resolved(self) -> None:
        validate_quarantine_manifest(self.manifest)
        self.assertEqual(
            self.manifest["manifest_sha256"],
            quarantine_manifest_digest(self.manifest),
        )
        self.assertEqual([], validate_schema_instance(self.manifest, SCHEMA_PATH))

        research_ids = {entry["entry_id"] for entry in load(RESEARCH_REGISTRY_PATH)["entries"]}
        source_ids = {source["source_id"] for source in self.sources["sources"]}
        for rule in self.manifest["rules"]:
            with self.subTest(rule_id=rule["rule_id"]):
                self.assertIn(rule["evidence_entry_id"], research_ids)
                self.assertTrue(set(rule["entity_ids"]) & (research_ids | source_ids))

    def test_manifest_tamper_breaks_self_commitment(self) -> None:
        tampered = copy.deepcopy(self.manifest)
        tampered["rules"][0]["notes"] = "silently weakened"
        with self.assertRaisesRegex(ValueError, "manifest_sha256"):
            validate_quarantine_manifest(tampered)

    def test_registered_synthetic_fixture_passes_normal_evaluation(self) -> None:
        report = require_corpus_permitted(
            [valid_artifact()],
            source_registry=self.sources,
            quarantine_manifest=self.manifest,
            purpose="development_evaluation",
        )
        self.assertTrue(report.allowed)
        self.assertEqual(0, len(report.findings))

    def test_known_quarantined_source_and_locator_spoof_are_blocked(self) -> None:
        blocked = valid_artifact("SYN:BLOCKED")
        blocked["source_records"][0]["source_id"] = "yajnadevam-lipi"
        blocked["source_records"][0]["locator"] = (
            "https://github.com/yajnadevam/lipi/blob/main/data.csv"
        )
        blocked["images"][0]["source_id"] = "yajnadevam-lipi"
        with self.assertRaises(CorpusQuarantineError) as raised:
            require_corpus_permitted(
                [blocked],
                source_registry=self.sources,
                quarantine_manifest=self.manifest,
                purpose="training",
            )
        self.assertIn(
            "quarantine:yajnadevam-lipi",
            {finding.rule_id for finding in raised.exception.report.findings},
        )

        spoofed = valid_artifact("SYN:SPOOFED")
        spoofed["source_records"][0]["source_id"] = "mayig-indus-valley-script-corpus"
        spoofed["images"][0]["source_id"] = "mayig-indus-valley-script-corpus"
        spoofed["source_records"][0]["locator"] = (
            "https://github.com/prabhatchanchal/IndusBench/test.json"
        )
        report = inspect_corpus_quarantine(
            [spoofed],
            source_registry=self.sources,
            quarantine_manifest=self.manifest,
            purpose="development_evaluation",
        )
        self.assertFalse(report.allowed)
        self.assertIn(
            "quarantine:external-indusbench",
            {finding.rule_id for finding in report.findings},
        )

    def test_unknown_and_fake_internal_sources_fail_closed(self) -> None:
        unknown = valid_artifact("SYN:UNKNOWN")
        unknown["source_records"][0]["source_id"] = "unregistered-source"
        unknown["images"][0]["source_id"] = "unregistered-source"
        report = inspect_corpus_quarantine(
            [unknown],
            source_registry=self.sources,
            quarantine_manifest=self.manifest,
            purpose="schema_validation",
        )
        self.assertFalse(report.allowed)
        self.assertIn(
            "unknown_source_id",
            {finding.code for finding in report.findings},
        )

        fake_internal = valid_artifact("REAL:001")
        report = inspect_corpus_quarantine(
            [fake_internal],
            source_registry=self.sources,
            quarantine_manifest=self.manifest,
            purpose="schema_validation",
        )
        self.assertFalse(report.allowed)
        self.assertIn(
            "internal_source_attestation_failed",
            {finding.code for finding in report.findings},
        )

    def test_audit_only_is_explicit_and_never_promotes_material(self) -> None:
        blocked = valid_artifact("SYN:AUDIT")
        blocked["source_records"][0]["source_id"] = "external-indusbench"
        blocked["images"][0]["source_id"] = "external-indusbench"
        report = inspect_corpus_quarantine(
            [blocked],
            source_registry=self.sources,
            quarantine_manifest=self.manifest,
            purpose="audit_only",
        )
        self.assertTrue(report.allowed)
        self.assertTrue(report.findings)
        payload = report.as_dict()
        self.assertTrue(payload["audit_only_override"])
        self.assertGreater(payload["finding_count"], 0)

    def test_rights_gate_is_purpose_specific(self) -> None:
        metadata_only = valid_artifact("SYN:RIGHTS")
        metadata_only["rights"]["derivatives"] = False
        report = inspect_corpus_quarantine(
            [metadata_only],
            source_registry=self.sources,
            quarantine_manifest=self.manifest,
            purpose="training",
        )
        self.assertIn(
            "derivatives_not_permitted",
            {finding.code for finding in report.findings},
        )


if __name__ == "__main__":
    unittest.main()
