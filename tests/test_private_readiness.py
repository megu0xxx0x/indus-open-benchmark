from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from indusbench.private_readiness import (
    AuditLimits,
    audit_private_corpus,
    read_private_policy,
)
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = "2026-07-27T07:00:00Z"
INTENDED_USE = "local_nonpublic_normalization"
SAFE_SUMMARY_KEYS = {
    "schema_version",
    "claim_class",
    "intended_use",
    "ready",
    "scan_completed",
    "reason_codes",
    "assurance",
}
EXPECTED_PRIVACY = {
    "aggregate_only": True,
    "paths_disclosed": False,
    "filenames_disclosed": False,
    "content_digests_disclosed": False,
    "identifiers_disclosed": False,
    "private_values_disclosed": False,
    "publication_review_required": True,
}
EXPECTED_ASSURANCE = {
    "blind_claim_allowed": False,
    "final_evaluation_eligible": False,
    "independent_custody_attested": False,
    "external_custodian_attested": False,
    "trusted_timestamp_attested": False,
    "access_history_attested": False,
    "confidentiality_attested": False,
    "rights_ownership_attested": False,
    "provenance_authenticity_attested": False,
    "future_immutability_attested": False,
    "decipherment_claim_allowed": False,
    "prize_submission_eligible": False,
}


def walk_json(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for key, item in value.items():
            values.extend(walk_json(key))
            values.extend(walk_json(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(walk_json(item))
    return values


def make_private_directory(path: Path) -> None:
    path.mkdir()
    make_owner_only(path)


def make_owner_only(path: Path) -> None:
    # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    os.chmod(path, 0o700)


def write_private(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)
    os.chmod(path, 0o600)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_audit(root: Path):
    return audit_private_corpus(
        root.resolve(),
        intended_use=INTENDED_USE,
        created_at=CREATED_AT,
        policy=None,
        source_registry=None,
        quarantine_manifest=None,
        key=None,
    )


class PrivateReadinessTests(unittest.TestCase):
    maxDiff = None

    def assert_rejection_is_redacted(
        self,
        root: Path,
        *sentinels: str,
    ) -> None:
        with self.assertRaises(ValueError) as raised:
            run_audit(root)
        message = str(raised.exception)
        self.assertNotIn(str(root.resolve()), message)
        for sentinel in sentinels:
            self.assertNotIn(sentinel, message)

    def test_default_limits_are_available_without_external_configuration(self) -> None:
        self.assertIsInstance(AuditLimits(), AuditLimits)

    def test_no_policy_scans_aggregate_formats_and_duplicates_but_is_not_ready(
        self,
    ) -> None:
        filename_sentinel = "PRIVATE_FILENAME_SENTINEL.json"
        content_sentinel = "PRIVATE_CONTENT_SENTINEL"
        identifier_sentinel = "PRIVATE_IDENTIFIER_SENTINEL"
        record = json.dumps(
            {
                "artifact_id": identifier_sentinel,
                "private_value": content_sentinel,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        note = b"bounded private note\n"

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "corpus"
            make_private_directory(root)
            write_private(root / filename_sentinel, record)
            write_private(root / "duplicate.json", record)
            write_private(root / "note.txt", note)

            result = run_audit(root)

        summary = result.summary
        self.assertEqual(SAFE_SUMMARY_KEYS, set(summary))
        self.assertEqual("0.2.0", summary["schema_version"])
        self.assertEqual("private_working_corpus_readiness", summary["claim_class"])
        self.assertEqual(INTENDED_USE, summary["intended_use"])
        self.assertFalse(summary["ready"])
        self.assertTrue(summary["scan_completed"])
        self.assertIn(
            "rights_coverage_incomplete",
            {reason.casefold() for reason in summary["reason_codes"]},
        )
        self.assertEqual(EXPECTED_ASSURANCE, summary["assurance"])
        self.assertFalse(
            any(
                isinstance(value, int) and not isinstance(value, bool)
                for value in walk_json(summary)
            ),
            "the safe summary must not disclose private corpus counts",
        )

        report = result.report
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual("0.2.0", report["schema_version"])
        self.assertEqual(CREATED_AT, report["created_at"])
        self.assertEqual(INTENDED_USE, report["intended_use"])
        self.assertTrue(report["scan_completed"])
        self.assertFalse(report["ready"])
        self.assertEqual(EXPECTED_PRIVACY, report["privacy"])
        self.assertEqual(summary["assurance"], report["assurance"])
        self.assertEqual(
            [],
            validate_schema_instance(
                report,
                ROOT / "schemas/private-corpus-readiness.schema.json",
            ),
        )
        self.assertEqual(
            {
                "file_count": 3,
                "directory_count": 1,
                "total_bytes": (2 * len(record)) + len(note),
            },
            report["inventory"],
        )
        self.assertEqual(2, report["formats"]["json"])
        self.assertEqual(1, report["formats"]["plain_text"])
        self.assertEqual(3, report["formats"]["parseable"])
        self.assertEqual(1, report["duplicates"]["duplicate_groups"])
        self.assertEqual(2, report["duplicates"]["duplicate_files"])
        self.assertFalse(report["policy"]["provided"])
        self.assertEqual(0, report["policy"]["covered_files"])
        self.assertEqual(3, report["policy"]["uncovered_files"])

        report_text = json.dumps(report, ensure_ascii=False, sort_keys=True)
        summary_text = json.dumps(summary, ensure_ascii=False, sort_keys=True)
        for sentinel in (
            str(root.resolve()),
            filename_sentinel,
            content_sentinel,
            identifier_sentinel,
        ):
            self.assertNotIn(sentinel, report_text)
            self.assertNotIn(sentinel, summary_text)
        self.assertNotIn(CREATED_AT, summary_text)
        self.assertNotRegex(report_text, r"\b(?:sha256:)?[0-9a-f]{64}\b")
        forbidden_record_keys = {
            "absolute_path",
            "content",
            "content_sha256",
            "digest",
            "file_name",
            "filename",
            "identifier",
            "relative_path",
            "sample",
            "sha256",
            "source_id",
        }
        self.assertFalse(
            forbidden_record_keys & {value for value in walk_json(report) if isinstance(value, str)}
        )

    def test_fully_covered_known_source_is_ready_only_for_local_intended_use(
        self,
    ) -> None:
        relative_path = "synthetic-record.json"
        raw = b'{"records":[]}\n'
        policy = {
            "schema_version": "0.2.0",
            "policy_kind": "private_corpus_use_policy",
            "entries": [
                {
                    "relative_path": relative_path,
                    "content_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "curation_status": "reviewed",
                    "content_layer": "metadata",
                    "source_id": "met-open-access-indus",
                    "source_locator": "https://www.metmuseum.org/hubs/open-access",
                    "source_revision": None,
                    "provenance_status": "documented",
                    "rights_status": "public_domain",
                    "rights_evidence_status": "documented",
                    "permitted_uses": [INTENDED_USE],
                }
            ],
        }
        source_registry = load_json(ROOT / "registry/sources.json")
        quarantine_manifest = load_json(ROOT / "registry/quarantine.json")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "corpus"
            make_private_directory(root)
            write_private(root / relative_path, raw)

            result = audit_private_corpus(
                root.resolve(),
                intended_use=INTENDED_USE,
                created_at=CREATED_AT,
                policy=policy,
                source_registry=source_registry,
                quarantine_manifest=quarantine_manifest,
                key=None,
            )

        self.assertEqual(SAFE_SUMMARY_KEYS, set(result.summary))
        self.assertTrue(result.summary["ready"])
        self.assertTrue(result.summary["scan_completed"])
        self.assertEqual([], result.summary["reason_codes"])
        self.assertEqual(EXPECTED_ASSURANCE, result.summary["assurance"])
        self.assertIsNotNone(result.report)
        assert result.report is not None
        self.assertTrue(result.report["ready"])
        self.assertEqual(
            {
                "provided": True,
                "valid": True,
                "covered_files": 1,
                "uncovered_files": 0,
                "extra_entries": 0,
                "compatible_entries": 1,
                "blocking_entries": 0,
            },
            result.report["policy"],
        )
        self.assertEqual(
            [],
            validate_schema_instance(
                result.report,
                ROOT / "schemas/private-corpus-readiness.schema.json",
            ),
        )
        aggregate_text = json.dumps(result.report, ensure_ascii=False, sort_keys=True)
        for private_policy_value in (
            relative_path,
            "met-open-access-indus",
            "https://www.metmuseum.org/hubs/open-access",
        ):
            self.assertNotIn(private_policy_value, aggregate_text)

    def test_private_policy_cannot_override_unknown_registry_rights_or_inject_claims(
        self,
    ) -> None:
        relative_path = "record.json"
        source_registry = load_json(ROOT / "registry/sources.json")
        quarantine_manifest = load_json(ROOT / "registry/quarantine.json")
        raw = b'{"records":[]}\n'
        base_policy: dict[str, Any] = {
            "schema_version": "0.2.0",
            "policy_kind": "private_corpus_use_policy",
            "entries": [
                {
                    "relative_path": relative_path,
                    "content_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "curation_status": "reviewed",
                    "content_layer": "metadata",
                    "source_id": "cisi",
                    "source_locator": None,
                    "source_revision": None,
                    "provenance_status": "documented",
                    "rights_status": "public_domain",
                    "rights_evidence_status": "documented",
                    "permitted_uses": [INTENDED_USE],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "corpus"
            make_private_directory(root)
            write_private(root / relative_path, raw)

            conflict = audit_private_corpus(
                root.resolve(),
                intended_use=INTENDED_USE,
                created_at=CREATED_AT,
                policy=base_policy,
                source_registry=source_registry,
                quarantine_manifest=quarantine_manifest,
            )
            injected_policy = dict(base_policy)
            injected_policy["ready"] = True
            injected = audit_private_corpus(
                root.resolve(),
                intended_use=INTENDED_USE,
                created_at=CREATED_AT,
                policy=injected_policy,
                source_registry=source_registry,
                quarantine_manifest=quarantine_manifest,
            )

        self.assertFalse(conflict.summary["ready"])
        self.assertIn(
            "RIGHTS_AMBIGUOUS_OR_CONFLICTING",
            conflict.summary["reason_codes"],
        )
        self.assertFalse(injected.summary["ready"])
        self.assertIn("POLICY_DOCUMENT_INVALID", injected.summary["reason_codes"])
        self.assertEqual(EXPECTED_ASSURANCE, injected.summary["assurance"])

    def test_private_policy_reader_rejects_duplicate_keys_without_quoting_values(
        self,
    ) -> None:
        sentinel = "PRIVATE_POLICY_VALUE_SENTINEL"
        raw = (
            '{"schema_version":"0.1.0","schema_version":"'
            + sentinel
            + '","policy_kind":"private_corpus_use_policy","entries":[]}'
        ).encode()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            policy_path = temporary / "policy.json"
            write_private(policy_path, raw)
            with self.assertRaises(ValueError) as raised:
                read_private_policy(policy_path.resolve())
        self.assertNotIn(sentinel, str(raised.exception))
        self.assertNotIn(str(policy_path), str(raised.exception))

    def test_symlink_is_rejected_without_disclosing_its_name(self) -> None:
        sentinel = "PRIVATE_SYMLINK_SENTINEL"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "corpus"
            make_private_directory(root)
            write_private(root / "target.json", b"{}\n")
            (root / sentinel).symlink_to("target.json")

            self.assert_rejection_is_redacted(root, sentinel)

    def test_hardlink_is_rejected_without_disclosing_its_name(self) -> None:
        sentinel = "PRIVATE_HARDLINK_SENTINEL.json"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "corpus"
            make_private_directory(root)
            source = root / "record.json"
            write_private(source, b"{}\n")
            os.link(source, root / sentinel)

            self.assert_rejection_is_redacted(root, sentinel)

    def test_non_private_file_and_directory_modes_are_rejected(self) -> None:
        cases = ("file", "directory")
        for case in cases:
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                temporary = Path(temporary_directory)
                make_owner_only(temporary)
                root = temporary / "corpus"
                make_private_directory(root)
                if case == "file":
                    sentinel = "PRIVATE_MODE_FILE_SENTINEL.json"
                    source = root / sentinel
                    write_private(source, b"{}\n")
                    os.chmod(source, 0o640)
                else:
                    sentinel = "PRIVATE_MODE_DIRECTORY_SENTINEL"
                    child = root / sentinel
                    make_private_directory(child)
                    # Deliberately unsafe mode verifies fail-closed handling.
                    # nosemgrep
                    os.chmod(child, 0o750)

                self.assert_rejection_is_redacted(root, sentinel)

    def test_nonsticky_world_writable_ancestor_is_rejected(self) -> None:
        sentinel = "PRIVATE_UNSAFE_ANCESTOR_SENTINEL"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            unsafe_parent = temporary / sentinel
            unsafe_parent.mkdir()
            # Deliberately unsafe mode verifies ancestry replacement protection.
            # nosemgrep
            os.chmod(unsafe_parent, 0o777)
            root = unsafe_parent / "corpus"
            make_private_directory(root)
            write_private(root / "record.json", b"{}\n")

            self.assert_rejection_is_redacted(root, sentinel)

    def test_unicode_casefold_collision_is_rejected_when_filesystem_supports_it(
        self,
    ) -> None:
        first_name = "straße.json"
        second_name = "STRASSE.JSON"
        self.assertEqual(first_name.casefold(), second_name.casefold())
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "corpus"
            make_private_directory(root)
            write_private(root / first_name, b'{"record":1}\n')
            write_private(root / second_name, b'{"record":2}\n')
            if len(tuple(root.iterdir())) != 2:
                self.skipTest("filesystem does not preserve this casefold-collision pair")

            self.assert_rejection_is_redacted(root, first_name, second_name)

    def test_relative_root_is_rejected_before_private_data_is_read(self) -> None:
        relative = Path("PRIVATE_RELATIVE_ROOT_SENTINEL")
        with self.assertRaises(ValueError) as raised:
            audit_private_corpus(
                relative,
                intended_use=INTENDED_USE,
                created_at=CREATED_AT,
                policy=None,
                source_registry=None,
                quarantine_manifest=None,
                key=None,
            )
        self.assertNotIn(str(relative), str(raised.exception))
        self.assertIsNone(re.search(r"/(?:[^/\n]+/)+", str(raised.exception)))


if __name__ == "__main__":
    unittest.main()
