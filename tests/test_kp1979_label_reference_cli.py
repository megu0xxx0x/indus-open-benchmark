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

PARTITION_PAGES = {
    "development": (20, 22, 79, 129, 131, 180),
    "future_evaluation": (8, 78, 99, 128, 130, 175),
}


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


def write_private(path: Path, raw_bytes: bytes) -> None:
    path.write_bytes(raw_bytes)
    path.chmod(0o600)


def assignment_summary(**overrides: bool | str) -> dict[str, bool | str]:
    summary: dict[str, bool | str] = {
        "valid": True,
        "claim_class": "private_label_reference_assignment_only",
        "source_snapshot_match": True,
        "page_map_snapshot_match": True,
        "selected_page_pixels_verified": True,
        "assignment_canonical_bytes_verified": True,
        "answer_values_withheld": True,
        "detector_output_absent": True,
        "proposal_geometry_absent": True,
        "human_review_started_verified": False,
        "human_review_complete_verified": False,
        "human_authorship_verified": False,
        "real_world_independence_verified": False,
        "reviewer_blinding_verified": False,
        "label_geometry_accepted": False,
        "row_geometry_accepted": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
        "reference_custody_verified": False,
        "detector_freeze_verified": False,
        "scorer_freeze_verified": False,
        "runtime_isolation_verified": False,
    }
    summary.update(overrides)
    return summary


def review_summary(**overrides: bool | str) -> dict[str, bool | str]:
    summary: dict[str, bool | str] = {
        "valid": True,
        "claim_class": "private_label_reference_review_only",
        "assignment_canonical_bytes_verified": True,
        "assignment_commitment_verified": True,
        "selected_page_pixels_verified": True,
        "review_canonical_bytes_verified": True,
        "review_roster_verified": True,
        "submitted_crop_bytes_recomputed": True,
        "opaque_record_ids_structurally_distinct": True,
        "authorship_declaration_recorded": True,
        "access_declaration_recorded": True,
        "actor_identity_verified": False,
        "authorship_declaration_verified": False,
        "access_declaration_verified": False,
        "human_review_started_verified": False,
        "human_review_complete_verified": False,
        "human_authorship_verified": False,
        "real_world_independence_verified": False,
        "reviewer_blinding_verified": False,
        "reviewer_nonexposure_verified": False,
        "label_geometry_accepted": False,
        "row_geometry_accepted": False,
        "identifiers_transcribed": False,
        "codes_transcribed": False,
        "sign_sequences_transcribed": False,
        "reading_direction_assigned": False,
        "source_custody_verified": False,
        "source_rights_verified": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
        "reference_custody_verified": False,
        "detector_freeze_verified": False,
        "scorer_freeze_verified": False,
        "runtime_isolation_verified": False,
    }
    summary.update(overrides)
    return summary


class KP1979LabelReferenceCliTests(unittest.TestCase):
    def make_inputs(self, root: Path) -> dict[str, Path]:
        paths = {
            "contract": root / "contract.json",
            "page_map": root / "page-map.json",
            "pdf": root / "source.pdf",
            "pages": root / "pages",
            "private": root / "private",
        }
        paths["contract"].write_bytes(b"synthetic contract")
        paths["page_map"].write_bytes(b"synthetic page map")
        paths["pdf"].write_bytes(b"synthetic source")
        paths["pages"].mkdir()
        for page_number in sorted({page for pages in PARTITION_PAGES.values() for page in pages}):
            (paths["pages"] / f"page-{page_number:03d}.pbm").write_bytes(
                f"synthetic page {page_number}".encode()
            )
        paths["private"].mkdir()
        paths["private"].chmod(0o700)
        return paths

    @staticmethod
    def prepare_arguments(
        paths: dict[str, Path],
        output: Path,
        *,
        partition: str,
    ) -> list[str]:
        return [
            "prepare-kp1979-label-reference-assignment",
            str(paths["pdf"]),
            str(paths["pages"]),
            str(output),
            "--partition",
            partition,
            "--contract",
            str(paths["contract"]),
            "--page-map",
            str(paths["page_map"]),
        ]

    @staticmethod
    def verify_arguments(
        paths: dict[str, Path],
        assignment: Path,
        *,
        partition: str,
    ) -> list[str]:
        return [
            "verify-kp1979-label-reference-assignment",
            str(paths["pdf"]),
            str(paths["pages"]),
            str(assignment),
            "--partition",
            partition,
            "--contract",
            str(paths["contract"]),
            "--page-map",
            str(paths["page_map"]),
        ]

    @staticmethod
    def review_arguments(
        paths: dict[str, Path],
        assignment: Path,
        review: Path,
        *,
        partition: str,
    ) -> list[str]:
        return [
            "verify-kp1979-label-reference-review",
            str(paths["pdf"]),
            str(paths["pages"]),
            str(assignment),
            str(review),
            "--partition",
            partition,
            "--contract",
            str(paths["contract"]),
            "--page-map",
            str(paths["page_map"]),
        ]

    def test_prepare_uses_only_the_fixed_partition_and_private_no_replace(self) -> None:
        assignment_value = {
            "schema_version": "synthetic",
            "manifest_id": "synthetic:kp1979:label-reference-assignment",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)

            for partition_name, expected_pages in PARTITION_PAGES.items():
                with self.subTest(partition=partition_name):
                    output = paths["private"] / f"{partition_name}.json"

                    def build(
                        contract_bytes: bytes,
                        page_map_bytes: bytes,
                        source_bytes: bytes,
                        page_bytes: Iterable[tuple[int, bytes]],
                        *,
                        partition: str,
                        expected_partition: str = partition_name,
                        expected_page_roster: tuple[int, ...] = expected_pages,
                    ) -> dict[str, str]:
                        self.assertEqual(paths["contract"].read_bytes(), contract_bytes)
                        self.assertEqual(paths["page_map"].read_bytes(), page_map_bytes)
                        self.assertEqual(paths["pdf"].read_bytes(), source_bytes)
                        self.assertEqual(expected_partition, partition)
                        observed = list(page_bytes)
                        self.assertEqual(
                            list(expected_page_roster),
                            [page for page, _ in observed],
                        )
                        self.assertEqual(
                            [f"synthetic page {page}".encode() for page in expected_page_roster],
                            [raw_bytes for _, raw_bytes in observed],
                        )
                        return assignment_value

                    arguments = self.prepare_arguments(
                        paths,
                        output,
                        partition=partition_name,
                    )
                    with patch.object(
                        cli_module,
                        "build_label_reference_assignment",
                        side_effect=build,
                    ) as builder:
                        result, stdout, stderr = run_cli(arguments)

                    self.assertEqual(0, result, stderr)
                    self.assertEqual("", stderr)
                    self.assertEqual(1, builder.call_count)
                    summary = json.loads(stdout)
                    self.assertTrue(summary["valid"])
                    self.assertTrue(summary["written"])
                    self.assertTrue(summary["private_storage_verified"])
                    self.assertTrue(summary["assignment_canonical_bytes_verified"])
                    self.assertTrue(summary["partition_isolated"])
                    self.assertTrue(summary["detector_output_absent"])
                    self.assertTrue(summary["proposal_geometry_absent"])
                    self.assertFalse(summary["counts_disclosed"])
                    self.assertFalse(summary["private_values_disclosed"])
                    self.assertFalse(summary["record_ids_disclosed"])
                    self.assertFalse(summary["digests_disclosed"])
                    self.assertFalse(summary["paths_disclosed"])
                    self.assertFalse(summary["label_geometry_accepted"])
                    self.assertFalse(summary["reference_custody_verified"])
                    self.assertFalse(summary["detector_freeze_verified"])
                    self.assertFalse(summary["scorer_freeze_verified"])
                    self.assertFalse(summary["runtime_isolation_verified"])
                    self.assertFalse(summary["human_review_complete_verified"])
                    self.assertFalse(summary["real_world_independence_verified"])
                    self.assertFalse(summary["evaluation_admissible"])
                    self.assertFalse(summary["decipherment"])
                    self.assertFalse(summary["prize_submission_eligible"])
                    self.assertNotIn(str(paths["private"]), stdout)
                    self.assertEqual(encode_json(assignment_value), output.read_bytes())
                    self.assertEqual(0o600, output.stat().st_mode & 0o777)

                    original = output.read_bytes()
                    with patch.object(
                        cli_module,
                        "build_label_reference_assignment",
                        return_value={"private_replacement": "DO-NOT-REPLACE"},
                    ):
                        second_result, second_stdout, second_stderr = run_cli(arguments)
                    self.assertEqual(1, second_result)
                    self.assertEqual("", second_stdout)
                    self.assertEqual(
                        "indusbench: private KP1979 label-reference assignment "
                        "could not be created safely\n",
                        second_stderr,
                    )
                    self.assertNotIn("DO-NOT-REPLACE", second_stderr)
                    self.assertNotIn(output.name, second_stderr)
                    self.assertEqual(original, output.read_bytes())

    def test_verify_assignment_is_source_bound_and_count_free(self) -> None:
        assignment_bytes = encode_json({"private_assignment": "ASSIGNMENT-ID-SENTINEL"})
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            assignment = paths["private"] / "assignment.json"
            write_private(assignment, assignment_bytes)

            def verify(
                contract_bytes: bytes,
                page_map_bytes: bytes,
                source_bytes: bytes,
                page_bytes: Iterable[tuple[int, bytes]],
                supplied_assignment_bytes: bytes,
            ) -> dict[str, bool | str]:
                self.assertEqual(paths["contract"].read_bytes(), contract_bytes)
                self.assertEqual(paths["page_map"].read_bytes(), page_map_bytes)
                self.assertEqual(paths["pdf"].read_bytes(), source_bytes)
                self.assertEqual(assignment_bytes, supplied_assignment_bytes)
                self.assertEqual(
                    list(PARTITION_PAGES["development"]),
                    [page for page, _ in page_bytes],
                )
                return assignment_summary(
                    private_count="PRIVATE-COUNT-SENTINEL",
                    private_digest="sha256:" + ("f" * 64),
                )

            with patch.object(
                cli_module,
                "verify_label_reference_assignment_bytes",
                side_effect=verify,
            ) as verifier:
                result, stdout, stderr = run_cli(
                    self.verify_arguments(
                        paths,
                        assignment,
                        partition="development",
                    )
                )

        self.assertEqual(0, result, stderr)
        self.assertEqual("", stderr)
        self.assertEqual(1, verifier.call_count)
        summary = json.loads(stdout)
        self.assertTrue(summary["assignment_canonical_bytes_verified"])
        self.assertFalse(summary["record_ids_disclosed"])
        self.assertFalse(summary["digests_disclosed"])
        self.assertFalse(summary["human_review_started_verified"])
        self.assertFalse(summary["real_world_independence_verified"])
        self.assertFalse(summary["decipherment"])
        self.assertNotIn("ASSIGNMENT-ID-SENTINEL", stdout)
        self.assertNotIn("PRIVATE-COUNT-SENTINEL", stdout)
        self.assertNotIn("sha256:", stdout)

    def test_verify_review_rechecks_assignment_and_discards_private_core_values(
        self,
    ) -> None:
        assignment_bytes = encode_json({"private_assignment": "PRIVATE-ASSIGNMENT"})
        review_bytes = encode_json({"private_review": "PRIVATE-REVIEW-ID"})
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            assignment = paths["private"] / "assignment.json"
            review = paths["private"] / "review.json"
            write_private(assignment, assignment_bytes)
            write_private(review, review_bytes)
            expected_pages = list(PARTITION_PAGES["future_evaluation"])

            def verify_assignment(
                _contract_bytes: bytes,
                _page_map_bytes: bytes,
                _source_bytes: bytes,
                page_bytes: Iterable[tuple[int, bytes]],
                supplied_assignment_bytes: bytes,
            ) -> dict[str, bool | str]:
                self.assertEqual(assignment_bytes, supplied_assignment_bytes)
                self.assertEqual(expected_pages, [page for page, _ in page_bytes])
                return assignment_summary()

            def verify_review(
                supplied_assignment_bytes: bytes,
                page_bytes: Iterable[tuple[int, bytes]],
                supplied_review_bytes: bytes,
            ) -> dict[str, bool | str]:
                self.assertEqual(assignment_bytes, supplied_assignment_bytes)
                self.assertEqual(review_bytes, supplied_review_bytes)
                self.assertEqual(expected_pages, [page for page, _ in page_bytes])
                return review_summary(
                    private_observation_count="PRIVATE-OBSERVATION-COUNT",
                    private_record_id="PRIVATE-REVIEW-ID",
                    private_digest="sha256:" + ("a" * 64),
                )

            with (
                patch.object(
                    cli_module,
                    "verify_label_reference_assignment_bytes",
                    side_effect=verify_assignment,
                ) as assignment_verifier,
                patch.object(
                    cli_module,
                    "verify_independent_label_reference_review_bytes",
                    side_effect=verify_review,
                ) as review_verifier,
            ):
                result, stdout, stderr = run_cli(
                    self.review_arguments(
                        paths,
                        assignment,
                        review,
                        partition="future_evaluation",
                    )
                )

        self.assertEqual(0, result, stderr)
        self.assertEqual("", stderr)
        self.assertEqual(1, assignment_verifier.call_count)
        self.assertEqual(1, review_verifier.call_count)
        summary = json.loads(stdout)
        self.assertTrue(summary["review_canonical_bytes_verified"])
        self.assertTrue(summary["review_record_verified"])
        self.assertTrue(summary["submitted_crop_bytes_recomputed"])
        self.assertTrue(summary["authorship_declaration_recorded"])
        self.assertTrue(summary["access_declaration_recorded"])
        self.assertTrue(summary["review_actor_assignment_ids_structurally_pairwise_distinct"])
        self.assertFalse(summary["record_ids_disclosed"])
        self.assertFalse(summary["digests_disclosed"])
        self.assertFalse(summary["human_review_started_verified"])
        self.assertFalse(summary["human_review_complete_verified"])
        self.assertFalse(summary["human_authorship_verified"])
        self.assertFalse(summary["actor_identity_verified"])
        self.assertFalse(summary["authorship_declaration_verified"])
        self.assertFalse(summary["access_declaration_verified"])
        self.assertFalse(summary["real_world_independence_verified"])
        self.assertFalse(summary["reviewer_blinding_verified"])
        self.assertFalse(summary["reviewer_nonexposure_verified"])
        self.assertFalse(summary["label_geometry_accepted"])
        self.assertFalse(summary["row_geometry_accepted"])
        self.assertFalse(summary["source_custody_verified"])
        self.assertFalse(summary["source_rights_verified"])
        self.assertFalse(summary["reference_custody_verified"])
        self.assertFalse(summary["detector_freeze_verified"])
        self.assertFalse(summary["scorer_freeze_verified"])
        self.assertFalse(summary["runtime_isolation_verified"])
        self.assertFalse(summary["evaluation_admissible"])
        self.assertFalse(summary["decipherment"])
        self.assertFalse(summary["prize_submission_eligible"])
        for sentinel in (
            "PRIVATE-ASSIGNMENT",
            "PRIVATE-REVIEW-ID",
            "PRIVATE-OBSERVATION-COUNT",
            "sha256:",
        ):
            self.assertNotIn(sentinel, stdout)

    def test_only_the_two_named_partitions_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            output = paths["private"] / "assignment.json"
            invalid_arguments = self.prepare_arguments(
                paths,
                output,
                partition="all",
            )
            stderr = io.StringIO()
            with (
                patch.object(cli_module, "build_label_reference_assignment") as builder,
                redirect_stderr(stderr),
                self.assertRaises(SystemExit) as raised,
            ):
                main(invalid_arguments)

        self.assertEqual(2, raised.exception.code)
        builder.assert_not_called()
        self.assertIn("invalid choice", stderr.getvalue())
        self.assertNotIn("PRIVATE", stderr.getvalue())

    def test_private_modes_and_physical_page_directory_fail_closed(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            assignment = paths["private"] / "PRIVATE-ASSIGNMENT.json"
            review = paths["private"] / "PRIVATE-REVIEW.json"
            write_private(assignment, b"private assignment sentinel")
            write_private(review, b"private review sentinel")

            assignment.chmod(0o644)
            with patch.object(
                cli_module,
                "verify_label_reference_assignment_bytes",
            ) as verifier:
                result, stdout, stderr = run_cli(
                    self.verify_arguments(
                        paths,
                        assignment,
                        partition="development",
                    )
                )
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            verifier.assert_not_called()
            self.assertEqual(
                "indusbench: KP1979 label-reference assignment verification failed\n",
                stderr,
            )
            self.assertNotIn(assignment.name, stderr)

            assignment.chmod(0o600)
            review.chmod(0o644)
            with (
                patch.object(
                    cli_module,
                    "verify_label_reference_assignment_bytes",
                ) as assignment_verifier,
                patch.object(
                    cli_module,
                    "verify_independent_label_reference_review_bytes",
                ) as review_verifier,
            ):
                result, stdout, stderr = run_cli(
                    self.review_arguments(
                        paths,
                        assignment,
                        review,
                        partition="development",
                    )
                )
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            assignment_verifier.assert_not_called()
            review_verifier.assert_not_called()
            self.assertEqual(
                "indusbench: KP1979 label-reference review verification failed\n",
                stderr,
            )
            self.assertNotIn(review.name, stderr)
            self.assertNotIn("private review sentinel", stderr)

            linked_pages = root / "PRIVATE-LINKED-PAGES"
            linked_pages.symlink_to(paths["pages"], target_is_directory=True)
            linked_paths = dict(paths)
            linked_paths["pages"] = linked_pages
            output = paths["private"] / "linked-output.json"
            with patch.object(
                cli_module,
                "build_label_reference_assignment",
            ) as builder:
                result, stdout, stderr = run_cli(
                    self.prepare_arguments(
                        linked_paths,
                        output,
                        partition="development",
                    )
                )
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            builder.assert_not_called()
            self.assertEqual(
                "indusbench: KP1979 label-reference assignment preparation failed\n",
                stderr,
            )
            self.assertNotIn(linked_pages.name, stderr)
            self.assertFalse(output.exists())

    def test_page_directory_replacement_after_pinning_is_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links are unavailable")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            output = paths["private"] / "assignment.json"
            original_pages = root / "pages-original"
            replacement_pages = root / "pages-replacement"
            replacement_pages.mkdir()
            real_reader = cli_module._read_regular_bytes_at
            swapped = False

            def swap_then_read(
                parent_descriptor: int,
                name: str,
                *,
                max_bytes: int,
            ) -> bytes:
                nonlocal swapped
                if not swapped:
                    swapped = True
                    paths["pages"].rename(original_pages)
                    paths["pages"].symlink_to(
                        replacement_pages,
                        target_is_directory=True,
                    )
                return real_reader(
                    parent_descriptor,
                    name,
                    max_bytes=max_bytes,
                )

            with (
                patch.object(
                    cli_module,
                    "_read_regular_bytes_at",
                    side_effect=swap_then_read,
                ),
                patch.object(
                    cli_module,
                    "build_label_reference_assignment",
                ) as builder,
            ):
                result, stdout, stderr = run_cli(
                    self.prepare_arguments(
                        paths,
                        output,
                        partition="development",
                    )
                )

        self.assertTrue(swapped)
        self.assertEqual(1, result)
        self.assertEqual("", stdout)
        builder.assert_not_called()
        self.assertEqual(
            "indusbench: KP1979 label-reference assignment preparation failed\n",
            stderr,
        )
        self.assertNotIn("pages-original", stderr)
        self.assertNotIn("pages-replacement", stderr)

    def test_page_entries_reject_symlink_hardlink_and_fifo(self) -> None:
        cases = ["symlink", "hardlink"]
        if hasattr(os, "mkfifo"):
            cases.append("fifo")
        for case in cases:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory).resolve()
                    paths = self.make_inputs(root)
                    page = paths["pages"] / "page-020.pbm"
                    page.unlink()
                    outside = root / "outside-page.pbm"
                    outside.write_bytes(b"synthetic page 20")
                    if case == "symlink":
                        page.symlink_to(outside)
                    elif case == "hardlink":
                        os.link(outside, page)
                    else:
                        os.mkfifo(page)
                    output = paths["private"] / "assignment.json"
                    with patch.object(
                        cli_module,
                        "build_label_reference_assignment",
                    ) as builder:
                        result, stdout, stderr = run_cli(
                            self.prepare_arguments(
                                paths,
                                output,
                                partition="development",
                            )
                        )

                self.assertEqual(1, result)
                self.assertEqual("", stdout)
                builder.assert_not_called()
                self.assertEqual(
                    "indusbench: KP1979 label-reference assignment preparation failed\n",
                    stderr,
                )
                self.assertNotIn(page.name, stderr)
                self.assertNotIn(outside.name, stderr)

    def test_prepare_rejects_nonprivate_output_and_unknown_durability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            nonprivate = root / "NONPRIVATE"
            nonprivate.mkdir()
            nonprivate.chmod(0o755)
            unsafe_output = nonprivate / "PRIVATE-ASSIGNMENT.json"
            arguments = self.prepare_arguments(
                paths,
                unsafe_output,
                partition="development",
            )
            with patch.object(
                cli_module,
                "build_label_reference_assignment",
                return_value={"synthetic": True},
            ):
                result, stdout, stderr = run_cli(arguments)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: private KP1979 label-reference assignment "
                "could not be created safely\n",
                stderr,
            )
            self.assertNotIn(nonprivate.name, stderr)
            self.assertFalse(unsafe_output.exists())

            private_output = paths["private"] / "unknown-durability.json"
            arguments = self.prepare_arguments(
                paths,
                private_output,
                partition="development",
            )
            with (
                patch.object(
                    cli_module,
                    "build_label_reference_assignment",
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
            self.assertEqual("", stderr)
            summary = json.loads(stdout)
            self.assertFalse(summary["valid"])
            self.assertFalse(summary["written"])
            self.assertFalse(summary["private_storage_verified"])
            self.assertTrue(summary["assignment_canonical_bytes_verified"])
            self.assertTrue(summary["destination_may_exist"])
            self.assertTrue(summary["output_content_verified"])
            self.assertFalse(summary["durability_confirmed"])
            self.assertFalse(summary["evaluation_admissible"])
            self.assertFalse(summary["decipherment"])
            self.assertFalse(summary["prize_submission_eligible"])

    def test_core_failures_and_incomplete_assurances_are_sanitized(self) -> None:
        private_error = "page 128 record PRIVATE-REVIEW-ID contains y=1234 and sha256:" + ("b" * 64)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            assignment = paths["private"] / "assignment.json"
            write_private(assignment, b"private assignment")
            with patch.object(
                cli_module,
                "verify_label_reference_assignment_bytes",
                side_effect=cli_module.KP1979LabelReferenceError(private_error),
            ):
                result, stdout, stderr = run_cli(
                    self.verify_arguments(
                        paths,
                        assignment,
                        partition="development",
                    )
                )
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 label-reference assignment verification failed\n",
                stderr,
            )
            self.assertNotIn("PRIVATE-REVIEW-ID", stderr)
            self.assertNotIn("1234", stderr)
            self.assertNotIn("sha256:", stderr)

            for field in (
                "valid",
                "source_snapshot_match",
                "page_map_snapshot_match",
                "selected_page_pixels_verified",
                "assignment_canonical_bytes_verified",
                "answer_values_withheld",
                "detector_output_absent",
                "proposal_geometry_absent",
            ):
                with (
                    self.subTest(assignment_true_assurance=field),
                    patch.object(
                        cli_module,
                        "verify_label_reference_assignment_bytes",
                        return_value=assignment_summary(**{field: False}),
                    ),
                ):
                    result, stdout, stderr = run_cli(
                        self.verify_arguments(
                            paths,
                            assignment,
                            partition="development",
                        )
                    )
                self.assertEqual(1, result)
                self.assertEqual("", stdout)
                self.assertEqual(
                    "indusbench: KP1979 label-reference assignment verification failed\n",
                    stderr,
                )

            for field in (
                "human_review_started_verified",
                "human_review_complete_verified",
                "human_authorship_verified",
                "real_world_independence_verified",
                "reviewer_blinding_verified",
                "label_geometry_accepted",
                "row_geometry_accepted",
                "public_release_authorized",
                "evaluation_admissible",
                "decipherment",
                "prize_submission_eligible",
                "reference_custody_verified",
                "detector_freeze_verified",
                "scorer_freeze_verified",
                "runtime_isolation_verified",
            ):
                with (
                    self.subTest(assignment_false_assurance=field),
                    patch.object(
                        cli_module,
                        "verify_label_reference_assignment_bytes",
                        return_value=assignment_summary(**{field: True}),
                    ),
                ):
                    result, stdout, stderr = run_cli(
                        self.verify_arguments(
                            paths,
                            assignment,
                            partition="development",
                        )
                    )
                self.assertEqual(1, result)
                self.assertEqual("", stdout)
                self.assertEqual(
                    "indusbench: KP1979 label-reference assignment verification failed\n",
                    stderr,
                )

            review = paths["private"] / "review.json"
            write_private(review, b"private review")
            for field in (
                "valid",
                "assignment_canonical_bytes_verified",
                "assignment_commitment_verified",
                "selected_page_pixels_verified",
                "review_canonical_bytes_verified",
                "review_roster_verified",
                "submitted_crop_bytes_recomputed",
                "opaque_record_ids_structurally_distinct",
                "authorship_declaration_recorded",
                "access_declaration_recorded",
            ):
                with (
                    self.subTest(review_true_assurance=field),
                    patch.object(
                        cli_module,
                        "verify_label_reference_assignment_bytes",
                        return_value=assignment_summary(),
                    ),
                    patch.object(
                        cli_module,
                        "verify_independent_label_reference_review_bytes",
                        return_value=review_summary(**{field: False}),
                    ),
                ):
                    result, stdout, stderr = run_cli(
                        self.review_arguments(
                            paths,
                            assignment,
                            review,
                            partition="development",
                        )
                    )
                self.assertEqual(1, result)
                self.assertEqual("", stdout)
                self.assertEqual(
                    "indusbench: KP1979 label-reference review verification failed\n",
                    stderr,
                )

            for field in (
                "actor_identity_verified",
                "authorship_declaration_verified",
                "access_declaration_verified",
                "human_review_started_verified",
                "human_review_complete_verified",
                "human_authorship_verified",
                "real_world_independence_verified",
                "reviewer_blinding_verified",
                "reviewer_nonexposure_verified",
                "label_geometry_accepted",
                "row_geometry_accepted",
                "identifiers_transcribed",
                "codes_transcribed",
                "sign_sequences_transcribed",
                "reading_direction_assigned",
                "source_custody_verified",
                "source_rights_verified",
                "public_release_authorized",
                "evaluation_admissible",
                "decipherment",
                "prize_submission_eligible",
                "reference_custody_verified",
                "detector_freeze_verified",
                "scorer_freeze_verified",
                "runtime_isolation_verified",
            ):
                with (
                    self.subTest(review_false_assurance=field),
                    patch.object(
                        cli_module,
                        "verify_label_reference_assignment_bytes",
                        return_value=assignment_summary(),
                    ),
                    patch.object(
                        cli_module,
                        "verify_independent_label_reference_review_bytes",
                        return_value=review_summary(**{field: True}),
                    ),
                ):
                    result, stdout, stderr = run_cli(
                        self.review_arguments(
                            paths,
                            assignment,
                            review,
                            partition="development",
                        )
                    )
                self.assertEqual(1, result)
                self.assertEqual("", stdout)
                self.assertEqual(
                    "indusbench: KP1979 label-reference review verification failed\n",
                    stderr,
                )

    def test_summary_extension_cannot_replace_fixed_assurances(self) -> None:
        with self.assertRaisesRegex(
            cli_module.KP1979LabelReferenceError,
            "cannot replace a fixed assurance",
        ):
            cli_module._kp1979_label_reference_summary(
                valid=True,
                claim_class="synthetic",
                private_storage_verified=True,
                assignment_canonical_bytes_verified=True,
                decipherment=True,
            )


if __name__ == "__main__":
    unittest.main()
