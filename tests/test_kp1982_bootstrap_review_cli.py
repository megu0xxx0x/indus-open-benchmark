from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from indusbench.cli import main
from indusbench.io import encode_json
from indusbench.kp1982_bootstrap_review import KP1982BootstrapReviewError


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


def write_private(path: Path, raw_bytes: bytes) -> None:
    path.write_bytes(raw_bytes)
    path.chmod(0o600)


class KP1982BootstrapReviewCliTests(unittest.TestCase):
    def make_inputs(self, root: Path) -> dict[str, Path]:
        paths = {
            "page20": root / "page-20.pbm",
            "page21": root / "page-21.pbm",
            "assignment": root / "assignment.json",
            "left": root / "pass-a.json",
            "right": root / "pass-b.json",
            "adjudication": root / "adjudication.json",
            "report": root / "audit.json",
        }
        paths["page20"].write_bytes(b"P4\n8 1\n\x80")
        paths["page21"].write_bytes(b"P4\n8 1\n\x00")
        write_private(paths["assignment"], b"private assignment sentinel")
        write_private(paths["left"], b"private left identifier sentinel")
        write_private(paths["right"], b"private right identifier sentinel")
        write_private(paths["adjudication"], b"private adjudication sentinel")
        return paths

    def test_reviewer_input_verification_uses_no_layout_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            root.chmod(0o700)
            paths = self.make_inputs(root)

            with patch(
                "indusbench.cli.verify_stripped_bootstrap_assignment_bytes",
                return_value={"valid": True, "cell_count": 700},
            ) as verifier:
                result, stdout, stderr = run_cli(
                    [
                        "verify-kp1982-bootstrap-review-input",
                        str(paths["page20"]),
                        str(paths["page21"]),
                        str(paths["assignment"]),
                    ]
                )

        self.assertEqual(0, result, stderr)
        self.assertEqual("", stderr)
        verifier.assert_called_once_with(
            b"private assignment sentinel",
            [b"P4\n8 1\n\x80", b"P4\n8 1\n\x00"],
        )
        summary = json.loads(stdout)
        self.assertTrue(summary["valid"])
        self.assertTrue(summary["layout_proposal_not_supplied"])
        self.assertTrue(summary["private_storage_verified"])
        self.assertFalse(summary["independent_review_record_verified"])
        self.assertFalse(summary["human_review_started_verified"])
        self.assertFalse(summary["human_review_complete_verified"])
        self.assertFalse(summary["human_adjudication_complete_verified"])
        self.assertFalse(summary["human_authorship_verified"])
        self.assertFalse(summary["real_world_independence_verified"])
        self.assertFalse(summary["reviewer_nonexposure_verified"])
        self.assertFalse(summary["prize_submission_eligible"])
        self.assertNotIn("700", stdout)

    def test_independent_review_verification_is_count_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            root.chmod(0o700)
            paths = self.make_inputs(root)

            with patch(
                "indusbench.cli.verify_independent_review_bytes",
                return_value={
                    "valid": True,
                    "cell_count": 700,
                    "private_identifier": "LOWER-ID-SENTINEL",
                },
            ) as verifier:
                result, stdout, stderr = run_cli(
                    [
                        "verify-kp1982-bootstrap-review",
                        str(paths["page20"]),
                        str(paths["page21"]),
                        str(paths["assignment"]),
                        str(paths["left"]),
                    ]
                )

        self.assertEqual(0, result, stderr)
        self.assertEqual("", stderr)
        verifier.assert_called_once_with(
            b"private assignment sentinel",
            [b"P4\n8 1\n\x80", b"P4\n8 1\n\x00"],
            b"private left identifier sentinel",
        )
        summary = json.loads(stdout)
        self.assertTrue(summary["independent_review_record_verified"])
        self.assertTrue(summary["submitted_crop_bytes_recomputed"])
        self.assertFalse(summary["two_review_audit_verified"])
        self.assertFalse(summary["human_authorship_verified"])
        self.assertFalse(summary["prize_submission_eligible"])
        self.assertNotIn("700", stdout)
        self.assertNotIn("LOWER-ID-SENTINEL", stdout)
        self.assertNotIn("private left identifier sentinel", stdout)

    def test_two_review_audit_writes_only_a_private_no_replace_report(self) -> None:
        first_private_report = {
            "valid": True,
            "cell_count": 700,
            "field_metrics": {"lower_identifier": {"exact_agreement_count": 699}},
            "comparison_sha256": "sha256:" + "a" * 64,
        }
        replacement_private_report = {
            "valid": True,
            "cell_count": 1,
            "private_sentinel": "DO-NOT-REPLACE",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            root.chmod(0o700)
            paths = self.make_inputs(root)
            arguments = [
                "audit-kp1982-bootstrap-reviews",
                str(paths["page20"]),
                str(paths["page21"]),
                str(paths["assignment"]),
                str(paths["left"]),
                str(paths["right"]),
                "--private-report",
                str(paths["report"]),
            ]

            with patch(
                "indusbench.cli.compare_independent_review_bytes",
                return_value=first_private_report,
            ) as comparator:
                result, stdout, stderr = run_cli(arguments)

            self.assertEqual(0, result, stderr)
            self.assertEqual("", stderr)
            comparator.assert_called_once_with(
                b"private assignment sentinel",
                [b"P4\n8 1\n\x80", b"P4\n8 1\n\x00"],
                [
                    b"private left identifier sentinel",
                    b"private right identifier sentinel",
                ],
            )
            summary = json.loads(stdout)
            self.assertTrue(summary["two_review_audit_verified"])
            self.assertTrue(summary["distinct_record_actor_assignment_ids_verified"])
            self.assertTrue(summary["submitted_crop_bytes_recomputed"])
            self.assertTrue(summary["private_report_written"])
            self.assertFalse(summary["agreement_result_disclosed"])
            self.assertFalse(summary["raw_identifier_values_disclosed"])
            self.assertFalse(summary["cell_ids_disclosed"])
            self.assertFalse(summary["record_ids_disclosed"])
            self.assertFalse(summary["real_world_independence_verified"])
            self.assertFalse(summary["prize_submission_eligible"])
            self.assertNotIn("700", stdout)
            self.assertNotIn("699", stdout)
            self.assertNotIn("lower_identifier", stdout)
            self.assertEqual(encode_json(first_private_report), paths["report"].read_bytes())
            self.assertEqual(0o600, paths["report"].stat().st_mode & 0o777)
            original = paths["report"].read_bytes()

            with patch(
                "indusbench.cli.compare_independent_review_bytes",
                return_value=replacement_private_report,
            ):
                second_result, second_stdout, second_stderr = run_cli(arguments)

            self.assertEqual(1, second_result)
            self.assertEqual("", second_stdout)
            self.assertEqual(
                "indusbench: private KP1982 bootstrap review audit could not be created safely\n",
                second_stderr,
            )
            self.assertNotIn(paths["report"].name, second_stderr)
            self.assertNotIn("DO-NOT-REPLACE", second_stderr)
            self.assertEqual(original, paths["report"].read_bytes())

    def test_adjudication_verification_reports_only_fixed_nonclaims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            root.chmod(0o700)
            paths = self.make_inputs(root)

            with patch(
                "indusbench.cli.verify_adjudication_bytes",
                return_value={
                    "valid": True,
                    "resolved_cell_count": 699,
                    "private_identifier": "ADJUDICATED-ID-SENTINEL",
                },
            ) as verifier:
                result, stdout, stderr = run_cli(
                    [
                        "verify-kp1982-bootstrap-adjudication",
                        str(paths["page20"]),
                        str(paths["page21"]),
                        str(paths["assignment"]),
                        str(paths["left"]),
                        str(paths["right"]),
                        str(paths["adjudication"]),
                    ]
                )

        self.assertEqual(0, result, stderr)
        self.assertEqual("", stderr)
        verifier.assert_called_once_with(
            b"private assignment sentinel",
            [b"P4\n8 1\n\x80", b"P4\n8 1\n\x00"],
            [
                b"private left identifier sentinel",
                b"private right identifier sentinel",
            ],
            b"private adjudication sentinel",
        )
        summary = json.loads(stdout)
        self.assertTrue(summary["adjudication_record_verified"])
        self.assertTrue(summary["distinct_record_actor_assignment_ids_verified"])
        self.assertTrue(summary["no_invention_rule_verified"])
        self.assertFalse(summary["human_authorship_verified"])
        self.assertFalse(summary["source_rights_verified"])
        self.assertFalse(summary["evaluation_admissible"])
        self.assertFalse(summary["decipherment"])
        self.assertFalse(summary["prize_submission_eligible"])
        self.assertNotIn("699", stdout)
        self.assertNotIn("ADJUDICATED-ID-SENTINEL", stdout)

    def test_audit_does_not_claim_a_report_when_durability_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            root.chmod(0o700)
            paths = self.make_inputs(root)
            with (
                patch(
                    "indusbench.cli.compare_independent_review_bytes",
                    return_value={"valid": True, "cell_count": 700},
                ),
                patch(
                    "indusbench.cli._write_private_json_no_replace",
                    return_value=(False, True),
                ),
            ):
                result, stdout, stderr = run_cli(
                    [
                        "audit-kp1982-bootstrap-reviews",
                        str(paths["page20"]),
                        str(paths["page21"]),
                        str(paths["assignment"]),
                        str(paths["left"]),
                        str(paths["right"]),
                        "--private-report",
                        str(paths["report"]),
                    ]
                )

        self.assertEqual(1, result)
        self.assertEqual("", stderr)
        summary = json.loads(stdout)
        self.assertFalse(summary["valid"])
        self.assertFalse(summary["private_report_written"])
        self.assertTrue(summary["destination_may_exist"])
        self.assertTrue(summary["output_content_verified"])
        self.assertFalse(summary["durability_confirmed"])
        self.assertFalse(summary["private_storage_verified"])
        self.assertFalse(summary["human_authorship_verified"])
        self.assertFalse(summary["prize_submission_eligible"])
        self.assertNotIn("700", stdout)

    def test_private_validation_error_does_not_echo_cell_or_identifier(self) -> None:
        private_error = "cell KP1982-P20-L01-R01 has lower identifier PRIVATE-ID-219-PRIME"
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            root.chmod(0o700)
            paths = self.make_inputs(root)
            with patch(
                "indusbench.cli.verify_independent_review_bytes",
                side_effect=KP1982BootstrapReviewError(private_error),
            ):
                result, stdout, stderr = run_cli(
                    [
                        "verify-kp1982-bootstrap-review",
                        str(paths["page20"]),
                        str(paths["page21"]),
                        str(paths["assignment"]),
                        str(paths["left"]),
                    ]
                )

        self.assertEqual(1, result)
        self.assertEqual("", stdout)
        self.assertEqual(
            "indusbench: KP1982 independent bootstrap review verification failed\n",
            stderr,
        )
        self.assertNotIn("KP1982-P20-L01-R01", stderr)
        self.assertNotIn("PRIVATE-ID-219-PRIME", stderr)
        self.assertNotIn(paths["left"].name, stderr)

    def test_all_non_pbm_inputs_require_0600_files_below_a_0700_parent(self) -> None:
        cases = (
            (
                "assignment",
                [
                    "verify-kp1982-bootstrap-review-input",
                    "{page20}",
                    "{page21}",
                    "{assignment}",
                ],
                "verify_stripped_bootstrap_assignment_bytes",
            ),
            (
                "left",
                [
                    "verify-kp1982-bootstrap-review",
                    "{page20}",
                    "{page21}",
                    "{assignment}",
                    "{left}",
                ],
                "verify_independent_review_bytes",
            ),
            (
                "right",
                [
                    "audit-kp1982-bootstrap-reviews",
                    "{page20}",
                    "{page21}",
                    "{assignment}",
                    "{left}",
                    "{right}",
                    "--private-report",
                    "{report}",
                ],
                "compare_independent_review_bytes",
            ),
            (
                "adjudication",
                [
                    "verify-kp1982-bootstrap-adjudication",
                    "{page20}",
                    "{page21}",
                    "{assignment}",
                    "{left}",
                    "{right}",
                    "{adjudication}",
                ],
                "verify_adjudication_bytes",
            ),
        )
        for unsafe_name, template, patched_name in cases:
            with self.subTest(unsafe_name=unsafe_name):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory).resolve()
                    root.chmod(0o700)
                    paths = self.make_inputs(root)
                    paths[unsafe_name].chmod(0o644)
                    arguments = [
                        part.format(**{name: str(path) for name, path in paths.items()})
                        for part in template
                    ]
                    with patch(f"indusbench.cli.{patched_name}") as operation:
                        result, stdout, stderr = run_cli(arguments)

                self.assertEqual(1, result)
                self.assertEqual("", stdout)
                self.assertFalse(operation.called)
                self.assertNotIn(paths[unsafe_name].name, stderr)
                self.assertNotIn("identifier sentinel", stderr)
                self.assertNotIn("adjudication sentinel", stderr)
                self.assertIn("indusbench: KP1982", stderr)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            root.chmod(0o755)
            paths = self.make_inputs(root)
            with patch("indusbench.cli.verify_stripped_bootstrap_assignment_bytes") as verifier:
                result, stdout, stderr = run_cli(
                    [
                        "verify-kp1982-bootstrap-review-input",
                        str(paths["page20"]),
                        str(paths["page21"]),
                        str(paths["assignment"]),
                    ]
                )
        self.assertEqual(1, result)
        self.assertEqual("", stdout)
        self.assertFalse(verifier.called)
        self.assertNotIn(paths["assignment"].name, stderr)


if __name__ == "__main__":
    unittest.main()
