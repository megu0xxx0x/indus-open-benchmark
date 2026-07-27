from __future__ import annotations

import io
import json
import os
import re
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from indusbench.cli import main

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
SAFE_PREPARATION_KEYS = {
    "schema_version",
    "operation",
    "scan_completed",
    "write_state",
    "template_state",
    "curator_review_required",
    "corpus_use_permitted",
    "source_data_modified",
    "publication_review_required",
    "reason_codes",
    "assurance",
}


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(argv)
    return result, stdout.getvalue(), stderr.getvalue()


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


def make_owner_only(path: Path) -> None:
    # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    os.chmod(path, 0o700)


class PrivateReadinessCliTests(unittest.TestCase):
    def assert_safe_summary(
        self,
        *,
        result: int,
        stdout: str,
        stderr: str,
        forbidden: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        self.assertEqual("", stderr)
        payload = json.loads(stdout)
        self.assertIsInstance(payload, dict)
        self.assertEqual(SAFE_SUMMARY_KEYS, set(payload))
        self.assertEqual("0.2.0", payload["schema_version"])
        self.assertEqual(
            "private_working_corpus_readiness",
            payload["claim_class"],
        )
        self.assertEqual(INTENDED_USE, payload["intended_use"])
        self.assertIsInstance(payload["ready"], bool)
        self.assertIsInstance(payload["scan_completed"], bool)
        self.assertIsInstance(payload["reason_codes"], list)
        self.assertTrue(
            all(
                isinstance(reason, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", reason) is not None
                for reason in payload["reason_codes"]
            )
        )
        self.assertEqual(EXPECTED_ASSURANCE, payload["assurance"])
        self.assertEqual(result == 0, payload["ready"])
        self.assertIn(result, (0, 2))

        summary_values = walk_json(payload)
        self.assertFalse(
            any(isinstance(value, int) and not isinstance(value, bool) for value in summary_values),
            "the public summary must not disclose counts",
        )
        summary_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(CREATED_AT, summary_text)
        self.assertNotRegex(summary_text, r"\b[0-9a-f]{64}\b")
        for sentinel in forbidden:
            self.assertNotIn(sentinel, stdout)
            self.assertNotIn(sentinel, stderr)
        return payload

    def test_no_policy_is_blocked_after_scan_and_writes_aggregate_report(self) -> None:
        filename_sentinel = "SECRET_RECORD_NAME_SENTINEL.json"
        content_sentinel = "SECRET_PRIVATE_CONTENT_SENTINEL"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "private-corpus"
            root.mkdir(mode=0o700)
            source = root / filename_sentinel
            source.write_text(
                json.dumps(
                    {
                        "source_id": "unknown-private-source",
                        "private_value": content_sentinel,
                    }
                ),
                encoding="utf-8",
            )
            os.chmod(source, 0o600)
            report_parent = temporary / "private-reports"
            report_parent.mkdir(mode=0o700)
            report = report_parent / "readiness.json"

            result, stdout, stderr = run_cli(
                [
                    "audit-private-readiness",
                    str(root.resolve()),
                    "--intended-use",
                    INTENDED_USE,
                    "--created-at",
                    CREATED_AT,
                    "--private-report",
                    str(report.resolve()),
                ]
            )

            payload = self.assert_safe_summary(
                result=result,
                stdout=stdout,
                stderr=stderr,
                forbidden=(
                    str(root.resolve()),
                    str(report.resolve()),
                    filename_sentinel,
                    content_sentinel,
                    "unknown-private-source",
                ),
            )
            self.assertEqual(2, result)
            self.assertFalse(payload["ready"])
            self.assertTrue(payload["scan_completed"])
            self.assertTrue(payload["reason_codes"])
            self.assertTrue(report.is_file())
            self.assertEqual(0o600, stat.S_IMODE(report.stat().st_mode))

            aggregate = json.loads(report.read_text(encoding="utf-8"))
            aggregate_text = json.dumps(aggregate, ensure_ascii=False, sort_keys=True)
            for sentinel in (
                str(root.resolve()),
                str(report.resolve()),
                filename_sentinel,
                content_sentinel,
                "unknown-private-source",
            ):
                self.assertNotIn(sentinel, aggregate_text)
            disclosed_record_keys = {
                "absolute_path",
                "content",
                "digest",
                "file_name",
                "filename",
                "identifier",
                "relative_path",
                "sample",
                "sha256",
            }
            self.assertTrue(
                all(
                    not isinstance(value, str) or value not in disclosed_record_keys
                    for value in walk_json(aggregate)
                )
            )

    def test_prepare_bundle_is_redacted_deny_all_and_remains_blocked_when_audited(
        self,
    ) -> None:
        filename_sentinel = "PRIVATE_REVIEW_FILENAME_SENTINEL.json"
        value_sentinel = "PRIVATE_REVIEW_VALUE_SENTINEL"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "private-corpus"
            root.mkdir(mode=0o700)
            source = root / filename_sentinel
            source.write_text(
                json.dumps({"private_value": value_sentinel}),
                encoding="utf-8",
            )
            os.chmod(source, 0o600)
            output_parent = temporary / "private-review"
            output_parent.mkdir(mode=0o700)
            output = output_parent / "bundle.json"

            result, stdout, stderr = run_cli(
                [
                    "prepare-private-review",
                    str(root.resolve()),
                    str(output.resolve(strict=False)),
                    "--created-at",
                    CREATED_AT,
                ]
            )

            self.assertEqual(0, result)
            self.assertEqual("", stderr)
            payload = json.loads(stdout)
            self.assertEqual(SAFE_PREPARATION_KEYS, set(payload))
            self.assertEqual("0.1.0", payload["schema_version"])
            self.assertEqual("prepare_private_review", payload["operation"])
            self.assertTrue(payload["scan_completed"])
            self.assertEqual("committed_and_verified", payload["write_state"])
            self.assertTrue(payload["curator_review_required"])
            self.assertFalse(payload["corpus_use_permitted"])
            self.assertFalse(payload["source_data_modified"])
            self.assertTrue(payload["publication_review_required"])
            self.assertEqual(["CURATOR_REVIEW_REQUIRED"], payload["reason_codes"])
            self.assertEqual(EXPECTED_ASSURANCE, payload["assurance"])
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))
            public_text = stdout + stderr
            for sentinel in (
                str(root.resolve()),
                str(output.resolve()),
                filename_sentinel,
                value_sentinel,
                CREATED_AT,
            ):
                self.assertNotIn(sentinel, public_text)
            self.assertNotRegex(public_text, r"\b[0-9a-f]{64}\b")
            self.assertFalse(
                any(
                    isinstance(value, int) and not isinstance(value, bool)
                    for value in walk_json(payload)
                )
            )

            private_bundle = json.loads(output.read_text(encoding="utf-8"))
            private_text = json.dumps(private_bundle, ensure_ascii=False, sort_keys=True)
            self.assertIn(filename_sentinel, private_text)
            self.assertNotIn(value_sentinel, private_text)

            audit_result, audit_stdout, audit_stderr = run_cli(
                [
                    "audit-private-readiness",
                    str(root.resolve()),
                    "--intended-use",
                    INTENDED_USE,
                    "--created-at",
                    CREATED_AT,
                    "--policy-bundle",
                    str(output.resolve()),
                ]
            )
            audit_payload = self.assert_safe_summary(
                result=audit_result,
                stdout=audit_stdout,
                stderr=audit_stderr,
                forbidden=(
                    str(root.resolve()),
                    str(output.resolve()),
                    filename_sentinel,
                    value_sentinel,
                ),
            )
            self.assertEqual(2, audit_result)
            self.assertFalse(audit_payload["ready"])
            self.assertIn(
                "POLICY_REVIEW_INCOMPLETE",
                audit_payload["reason_codes"],
            )

            inside_bundle = root / "PRIVATE_POLICY_INSIDE_CORPUS_SENTINEL.json"
            inside_bundle.write_bytes(output.read_bytes())
            os.chmod(inside_bundle, 0o600)
            inside_result, inside_stdout, inside_stderr = run_cli(
                [
                    "audit-private-readiness",
                    str(root.resolve()),
                    "--intended-use",
                    INTENDED_USE,
                    "--created-at",
                    CREATED_AT,
                    "--policy-bundle",
                    str(inside_bundle.resolve()),
                ]
            )
            inside_payload = self.assert_safe_summary(
                result=inside_result,
                stdout=inside_stdout,
                stderr=inside_stderr,
                forbidden=(
                    str(inside_bundle.resolve()),
                    inside_bundle.name,
                    filename_sentinel,
                    value_sentinel,
                ),
            )
            self.assertEqual(2, inside_result)
            self.assertFalse(inside_payload["scan_completed"])
            self.assertIn("ROOT_BOUNDARY_INVALID", inside_payload["reason_codes"])

    def test_malformed_policy_bundle_maps_to_policy_document_invalid(self) -> None:
        filename_sentinel = "PRIVATE_MALFORMED_BUNDLE_SENTINEL.json"
        value_sentinel = "PRIVATE_MALFORMED_VALUE_SENTINEL"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "private-corpus"
            root.mkdir(mode=0o700)
            source = root / filename_sentinel
            source.write_text(
                json.dumps({"private_value": value_sentinel}),
                encoding="utf-8",
            )
            os.chmod(source, 0o600)
            output_parent = temporary / "private-review"
            output_parent.mkdir(mode=0o700)
            output = output_parent / "bundle.json"

            prepare_result, _, _ = run_cli(
                [
                    "prepare-private-review",
                    str(root.resolve()),
                    str(output.resolve(strict=False)),
                    "--created-at",
                    CREATED_AT,
                ]
            )
            self.assertEqual(0, prepare_result)
            malformed = json.loads(output.read_text(encoding="utf-8"))
            malformed["policy"]["entries"][0]["ready"] = True
            output.write_text(
                json.dumps(malformed, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.chmod(output, 0o600)

            result, stdout, stderr = run_cli(
                [
                    "audit-private-readiness",
                    str(root.resolve()),
                    "--intended-use",
                    INTENDED_USE,
                    "--created-at",
                    CREATED_AT,
                    "--policy-bundle",
                    str(output.resolve()),
                ]
            )
            payload = self.assert_safe_summary(
                result=result,
                stdout=stdout,
                stderr=stderr,
                forbidden=(
                    str(root.resolve()),
                    str(output.resolve()),
                    filename_sentinel,
                    value_sentinel,
                ),
            )
            self.assertEqual(2, result)
            self.assertFalse(payload["scan_completed"])
            self.assertEqual(
                ["POLICY_DOCUMENT_INVALID"],
                payload["reason_codes"],
            )

    def test_missing_root_oserror_is_sanitized(self) -> None:
        path_sentinel = "MISSING_PRIVATE_PATH_SENTINEL"
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory).resolve() / path_sentinel
            result, stdout, stderr = run_cli(
                [
                    "audit-private-readiness",
                    str(missing),
                    "--intended-use",
                    INTENDED_USE,
                    "--created-at",
                    CREATED_AT,
                ]
            )

            payload = self.assert_safe_summary(
                result=result,
                stdout=stdout,
                stderr=stderr,
                forbidden=(str(missing), path_sentinel),
            )
            self.assertEqual(2, result)
            self.assertFalse(payload["ready"])
            self.assertFalse(payload["scan_completed"])
            self.assertTrue(payload["reason_codes"])

    def test_existing_private_report_is_not_replaced_and_error_is_sanitized(
        self,
    ) -> None:
        report_content_sentinel = b"EXISTING_PRIVATE_REPORT_SENTINEL\n"
        report_name_sentinel = "EXISTING_PRIVATE_REPORT_NAME_SENTINEL.json"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            root = temporary / "private-corpus"
            root.mkdir(mode=0o700)
            source = root / "record.json"
            source.write_text("{}\n", encoding="utf-8")
            os.chmod(source, 0o600)
            report_parent = temporary / "private-reports"
            report_parent.mkdir(mode=0o700)
            report = report_parent / report_name_sentinel
            report.write_bytes(report_content_sentinel)
            os.chmod(report, 0o600)

            result, stdout, stderr = run_cli(
                [
                    "audit-private-readiness",
                    str(root.resolve()),
                    "--intended-use",
                    INTENDED_USE,
                    "--created-at",
                    CREATED_AT,
                    "--private-report",
                    str(report.resolve()),
                ]
            )

            payload = self.assert_safe_summary(
                result=result,
                stdout=stdout,
                stderr=stderr,
                forbidden=(
                    str(report.resolve()),
                    report_name_sentinel,
                    report_content_sentinel.decode().strip(),
                ),
            )
            self.assertEqual(2, result)
            self.assertFalse(payload["ready"])
            self.assertTrue(payload["reason_codes"])
            self.assertEqual(report_content_sentinel, report.read_bytes())
            self.assertEqual(0o600, stat.S_IMODE(report.stat().st_mode))


if __name__ == "__main__":
    unittest.main()
