from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from collections.abc import Iterable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import indusbench.cli as cli_module
from indusbench.cli import main
from indusbench.io import encode_json
from indusbench.kp1979_row_assignment import KP1979RowAssignmentError


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


class KP1979RowAssignmentCLITests(unittest.TestCase):
    def _inputs(
        self,
        root: Path,
    ) -> tuple[Path, Path, Path, Path, Path]:
        contract = root / "contract.json"
        page_map = root / "page-map.json"
        pdf = root / "source.pdf"
        page_directory = root / "pages"
        private_directory = root / "private"
        contract.write_bytes(b"synthetic contract")
        page_map.write_bytes(b"synthetic page map")
        pdf.write_bytes(b"synthetic source")
        page_directory.mkdir()
        for page_number in range(2, 181):
            (page_directory / f"page-{page_number:03d}.pbm").write_bytes(
                f"synthetic page {page_number}".encode()
            )
        private_directory.mkdir()
        private_directory.chmod(0o700)
        return contract, page_map, pdf, page_directory, private_directory

    @staticmethod
    def _prepare_arguments(
        *,
        contract: Path,
        page_map: Path,
        pdf: Path,
        page_directory: Path,
        output: Path,
    ) -> list[str]:
        return [
            "prepare-kp1979-row-assignment",
            str(pdf),
            str(page_directory),
            str(output),
            "--contract",
            str(contract),
            "--page-map",
            str(page_map),
        ]

    @staticmethod
    def _verify_arguments(
        *,
        contract: Path,
        page_map: Path,
        pdf: Path,
        page_directory: Path,
        assignment: Path,
    ) -> list[str]:
        return [
            "verify-kp1979-row-assignment",
            str(pdf),
            str(page_directory),
            str(assignment),
            "--contract",
            str(contract),
            "--page-map",
            str(page_map),
        ]

    def test_prepare_uses_distinct_closed_page_iterators_and_private_no_replace(
        self,
    ) -> None:
        assignment_value = {
            "schema_version": "synthetic",
            "manifest_id": "synthetic:kp1979:row-assignment",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            contract, page_map, pdf, page_directory, private_directory = self._inputs(root)
            output = private_directory / "assignment.json"

            def build(
                contract_bytes: bytes,
                page_map_bytes: bytes,
                source_bytes: bytes,
                audit_pages: Iterable[tuple[int, bytes]],
                base_pages: Iterable[tuple[int, bytes]],
            ) -> dict[str, str]:
                self.assertEqual(contract.read_bytes(), contract_bytes)
                self.assertEqual(page_map.read_bytes(), page_map_bytes)
                self.assertEqual(pdf.read_bytes(), source_bytes)
                audited = list(audit_pages)
                base = list(base_pages)
                self.assertEqual(list(range(2, 181)), [page for page, _ in audited])
                self.assertEqual(list(range(22, 79)), [page for page, _ in base])
                self.assertEqual(b"synthetic page 2", audited[0][1])
                self.assertEqual(b"synthetic page 180", audited[-1][1])
                self.assertEqual(b"synthetic page 22", base[0][1])
                self.assertEqual(b"synthetic page 78", base[-1][1])
                return assignment_value

            arguments = self._prepare_arguments(
                contract=contract,
                page_map=page_map,
                pdf=pdf,
                page_directory=page_directory,
                output=output,
            )
            with patch.object(cli_module, "build_row_assignment", side_effect=build) as mocked:
                result, stdout, stderr = run_cli(arguments)
            self.assertEqual(0, result, stderr)
            self.assertEqual(1, mocked.call_count)
            summary = json.loads(stdout)
            self.assertTrue(summary["valid"])
            self.assertTrue(summary["written"])
            self.assertTrue(summary["private_storage_verified"])
            self.assertTrue(summary["assignment_canonical_bytes_verified"])
            self.assertTrue(summary["proposal_geometry_only"])
            self.assertTrue(summary["machine_answer_values_withheld"])
            self.assertNotIn("proposal_values_only", summary)
            self.assertFalse(summary["counts_disclosed"])
            self.assertFalse(summary["private_values_disclosed"])
            for field in (
                "label_geometry_accepted",
                "row_geometry_accepted",
                "human_review_complete",
                "reviewer_independence_verified",
                "identifiers_transcribed",
                "codes_transcribed",
                "sign_sequences_transcribed",
                "reading_direction_assigned",
                "public_release_authorized",
                "evaluation_admissible",
                "decipherment",
            ):
                self.assertFalse(summary[field])
            self.assertEqual(assignment_value, json.loads(output.read_text(encoding="utf-8")))
            self.assertEqual(0o600, output.stat().st_mode & 0o777)

            original = output.read_bytes()
            with patch.object(
                cli_module,
                "build_row_assignment",
                return_value={"replacement": True},
            ):
                second_result, second_stdout, second_stderr = run_cli(arguments)
            self.assertEqual(1, second_result)
            self.assertEqual("", second_stdout)
            self.assertEqual(
                "indusbench: private KP1979 row assignment could not be created safely\n",
                second_stderr,
            )
            self.assertNotIn(output.name, second_stderr)
            self.assertEqual(original, output.read_bytes())

    def test_verify_reads_private_assignment_and_recomputes_both_page_ranges(
        self,
    ) -> None:
        assignment_value = {
            "schema_version": "synthetic",
            "manifest_id": "synthetic:kp1979:row-assignment",
        }
        assignment_bytes = encode_json(assignment_value)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            contract, page_map, pdf, page_directory, private_directory = self._inputs(root)
            assignment = private_directory / "assignment.json"
            assignment.write_bytes(assignment_bytes)
            assignment.chmod(0o600)

            def verify(
                contract_bytes: bytes,
                page_map_bytes: bytes,
                source_bytes: bytes,
                audit_pages: Iterable[tuple[int, bytes]],
                base_pages: Iterable[tuple[int, bytes]],
                supplied_assignment_bytes: bytes,
            ) -> dict[str, bool | str]:
                self.assertEqual(contract.read_bytes(), contract_bytes)
                self.assertEqual(page_map.read_bytes(), page_map_bytes)
                self.assertEqual(pdf.read_bytes(), source_bytes)
                self.assertEqual(assignment_bytes, supplied_assignment_bytes)
                audited = list(audit_pages)
                base = list(base_pages)
                self.assertEqual(list(range(2, 181)), [page for page, _ in audited])
                self.assertEqual(list(range(22, 79)), [page for page, _ in base])
                return {
                    "valid": True,
                    "claim_class": "private_kp1979_row_assignment_only",
                    "assignment_canonical_bytes_verified": True,
                    "proposal_geometry_only": True,
                    "machine_answer_values_withheld": True,
                    "decipherment": False,
                }

            arguments = self._verify_arguments(
                contract=contract,
                page_map=page_map,
                pdf=pdf,
                page_directory=page_directory,
                assignment=assignment,
            )
            with patch.object(
                cli_module,
                "verify_row_assignment_bytes",
                side_effect=verify,
            ) as mocked:
                result, stdout, stderr = run_cli(arguments)
            self.assertEqual(0, result, stderr)
            self.assertEqual(1, mocked.call_count)
            summary = json.loads(stdout)
            self.assertTrue(summary["valid"])
            self.assertTrue(summary["private_storage_verified"])
            self.assertTrue(summary["assignment_canonical_bytes_verified"])
            self.assertTrue(summary["proposal_geometry_only"])
            self.assertTrue(summary["machine_answer_values_withheld"])
            self.assertNotIn("proposal_values_only", summary)
            self.assertFalse(summary["counts_disclosed"])
            self.assertFalse(summary["label_geometry_accepted"])
            self.assertFalse(summary["identifiers_transcribed"])
            self.assertFalse(summary["sign_sequences_transcribed"])
            self.assertFalse(summary["decipherment"])
            self.assertNotIn("written", summary)

    def test_summary_extension_cannot_replace_fixed_assurances(self) -> None:
        with self.assertRaisesRegex(
            KP1979RowAssignmentError,
            "cannot replace a fixed assurance",
        ):
            cli_module._kp1979_row_assignment_summary(
                valid=True,
                private_storage_verified=True,
                assignment_canonical_bytes_verified=True,
                decipherment=True,
            )

    def test_physical_directory_and_private_input_failures_are_sanitized(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            contract, page_map, pdf, page_directory, private_directory = self._inputs(root)
            linked_directory = root / "PRIVATE-LINKED-PAGES"
            linked_directory.symlink_to(page_directory, target_is_directory=True)
            output = private_directory / "PRIVATE-ASSIGNMENT.json"
            prepare_arguments = self._prepare_arguments(
                contract=contract,
                page_map=page_map,
                pdf=pdf,
                page_directory=linked_directory,
                output=output,
            )
            with patch.object(cli_module, "build_row_assignment") as mocked:
                result, stdout, stderr = run_cli(prepare_arguments)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 row assignment preparation failed\n",
                stderr,
            )
            self.assertNotIn(linked_directory.name, stderr)
            mocked.assert_not_called()
            self.assertFalse(output.exists())

            assignment = private_directory / "PRIVATE-INPUT.json"
            assignment.write_bytes(encode_json({"synthetic": True}))
            assignment.chmod(0o644)
            verify_arguments = self._verify_arguments(
                contract=contract,
                page_map=page_map,
                pdf=pdf,
                page_directory=page_directory,
                assignment=assignment,
            )
            with patch.object(cli_module, "verify_row_assignment_bytes") as mocked:
                result, stdout, stderr = run_cli(verify_arguments)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 row assignment verification failed\n",
                stderr,
            )
            self.assertNotIn(assignment.name, stderr)
            mocked.assert_not_called()

    def test_prepare_rejects_nonprivate_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            contract, page_map, pdf, page_directory, _ = self._inputs(root)
            nonprivate_directory = root / "NONPRIVATE-OUTPUT"
            nonprivate_directory.mkdir()
            nonprivate_directory.chmod(0o755)
            output = nonprivate_directory / "PRIVATE-ASSIGNMENT.json"
            arguments = self._prepare_arguments(
                contract=contract,
                page_map=page_map,
                pdf=pdf,
                page_directory=page_directory,
                output=output,
            )
            with patch.object(
                cli_module,
                "build_row_assignment",
                return_value={"synthetic": True},
            ):
                result, stdout, stderr = run_cli(arguments)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: private KP1979 row assignment could not be created safely\n",
                stderr,
            )
            self.assertNotIn(nonprivate_directory.name, stderr)
            self.assertFalse(output.exists())

    def test_core_rejection_and_unknown_durability_never_upgrade_assurances(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            contract, page_map, pdf, page_directory, private_directory = self._inputs(root)
            output = private_directory / "assignment.json"
            arguments = self._prepare_arguments(
                contract=contract,
                page_map=page_map,
                pdf=pdf,
                page_directory=page_directory,
                output=output,
            )
            with patch.object(
                cli_module,
                "build_row_assignment",
                side_effect=KP1979RowAssignmentError("forbidden field detected"),
            ):
                result, stdout, stderr = run_cli(arguments)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 row assignment preparation failed\n",
                stderr,
            )
            self.assertNotIn("forbidden", stderr)
            self.assertFalse(output.exists())

            with (
                patch.object(
                    cli_module,
                    "build_row_assignment",
                    return_value={"synthetic": True},
                ),
                patch.object(
                    cli_module,
                    "_write_private_json_no_replace",
                    return_value=(False, True),
                ),
            ):
                result, stdout, stderr = run_cli(arguments)
            self.assertEqual(1, result, stderr)
            summary = json.loads(stdout)
            self.assertFalse(summary["valid"])
            self.assertFalse(summary["written"])
            self.assertFalse(summary["private_storage_verified"])
            self.assertTrue(summary["assignment_canonical_bytes_verified"])
            self.assertTrue(summary["destination_may_exist"])
            self.assertFalse(summary["counts_disclosed"])
            self.assertFalse(summary["label_geometry_accepted"])
            self.assertFalse(summary["row_geometry_accepted"])
            self.assertFalse(summary["identifiers_transcribed"])
            self.assertFalse(summary["sign_sequences_transcribed"])
            self.assertFalse(summary["evaluation_admissible"])
            self.assertFalse(summary["decipherment"])


if __name__ == "__main__":
    unittest.main()
