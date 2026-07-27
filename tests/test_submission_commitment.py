from __future__ import annotations

import copy
import errno
import io
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, TypedDict
from unittest.mock import patch

import indusbench.cli as cli_module
import indusbench.submission_commitment as commitment_module
from indusbench.cli import main
from indusbench.schema_validation import validate_schema_instance
from indusbench.submission_commitment import (
    SubmissionCommitmentError,
    build_submission_commitment,
    normalize_logical_path,
    read_submission_commitment,
    submission_commitment_digest,
    submission_tree_digest,
    validate_submission_commitment,
    verify_submission_commitment,
)

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SHA256 = "sha256:" + "1" * 64


class SubmissionInputs(TypedDict):
    root: Path
    benchmark_definition_sha256: str
    entrypoint: str
    source_files: list[str]
    config_files: list[str]
    model_weight_files: list[str]
    dependency_files: list[str]
    static_arguments: list[str]


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(argv)
    return result, stdout.getvalue(), stderr.getvalue()


def prepare_tree(root: Path, *, reverse: bool = False) -> SubmissionInputs:
    files = [
        ("src/run.py", b"def main():\n    return 0\n"),
        ("src/helper.py", b"VALUE = 7\n"),
        ("config/model.json", b'{"seed":7}\n'),
        ("weights/model.bin", b"\x00\x01\x02\x03"),
        ("uv.lock", b"version = 1\n"),
        ("assets/empty.bin", b""),
        ("README.md", b"synthetic submission fixture\n"),
    ]
    if reverse:
        files.reverse()
    root.mkdir()
    (root / "empty-directory").mkdir()
    for relative_path, raw in files:
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    (root / "src/run.py").chmod(0o755)
    return {
        "root": root,
        "benchmark_definition_sha256": BENCHMARK_SHA256,
        "entrypoint": "src/run.py",
        "source_files": ["src/helper.py"],
        "config_files": ["config/model.json"],
        "model_weight_files": ["weights/model.bin"],
        "dependency_files": ["uv.lock"],
        "static_arguments": ["--mode", "predict"],
    }


def submission_cli_args(root: Path, output: Path) -> list[str]:
    return [
        "build-submission-commitment",
        str(root),
        str(output),
        "--benchmark-definition-sha256",
        BENCHMARK_SHA256,
        "--entrypoint",
        "src/run.py",
        "--source-file",
        "src/helper.py",
        "--config-file",
        "config/model.json",
        "--model-weight-file",
        "weights/model.bin",
        "--dependency-file",
        "uv.lock",
        "--static-argument=--mode",
        "--static-argument",
        "predict",
    ]


class SubmissionCommitmentTests(unittest.TestCase):
    maxDiff = None

    def test_build_verify_schema_roles_and_fixed_assurance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = prepare_tree(Path(temporary_directory) / "submission")
            commitment = build_submission_commitment(**paths)

            self.assertEqual(
                commitment["commitment_sha256"],
                submission_commitment_digest(commitment),
            )
            self.assertEqual(
                commitment["tree"]["tree_sha256"],
                submission_tree_digest(commitment["tree"]),
            )
            self.assertEqual(
                [],
                validate_schema_instance(
                    commitment,
                    ROOT / "schemas/submission-commitment.schema.json",
                ),
            )
            validate_submission_commitment(commitment)
            self.assertNotIn("created_at", commitment)
            self.assertNotIn("created_by", commitment)
            self.assertFalse(commitment["assurance"]["confidentiality_attested"])
            self.assertEqual(BENCHMARK_SHA256, commitment["target"]["benchmark_definition_sha256"])

            file_entries = {
                entry["path"]: entry
                for entry in commitment["tree"]["entries"]
                if entry["type"] == "file"
            }
            self.assertEqual(["entrypoint", "source"], file_entries["src/run.py"]["roles"])
            self.assertEqual(["source"], file_entries["src/helper.py"]["roles"])
            self.assertEqual(["configuration"], file_entries["config/model.json"]["roles"])
            self.assertEqual(["model_weight"], file_entries["weights/model.bin"]["roles"])
            self.assertEqual(["dependency"], file_entries["uv.lock"]["roles"])
            self.assertEqual(["runtime_input"], file_entries["README.md"]["roles"])
            self.assertEqual(0, file_entries["assets/empty.bin"]["bytes"])
            self.assertTrue(file_entries["src/run.py"]["executable"])
            self.assertIn(
                {"path": "empty-directory", "type": "directory"},
                commitment["tree"]["entries"],
            )

            report = verify_submission_commitment(
                commitment,
                root=paths["root"],
                expected_commitment_sha256=commitment["commitment_sha256"],
            )
            self.assertTrue(report.valid)
            self.assertTrue(report.self_consistent)
            self.assertTrue(report.tree_matches)
            self.assertTrue(report.entrypoint_bound)
            self.assertTrue(report.expected_digest_match)
            payload = report.as_dict()
            self.assertFalse(payload["blind_claim_allowed"])
            self.assertFalse(payload["externally_anchored"])
            self.assertFalse(payload["custody_attested"])
            self.assertFalse(payload["trusted_timestamp_attested"])
            self.assertFalse(payload["confidentiality_attested"])
            self.assertFalse(payload["runtime_isolation_attested"])
            self.assertFalse(payload["postconditions_atomic"])
            self.assertFalse(payload["future_immutability_attested"])
            self.assertEqual(
                "point_in_time_non_atomic_filesystem_checks",
                payload["verification_scope"],
            )

            deeply_nested_schema: dict[str, Any] = {}
            for _ in range(200):
                deeply_nested_schema = {"child": deeply_nested_schema}
            with self.assertRaisesRegex(SubmissionCommitmentError, "depth"):
                validate_submission_commitment(
                    commitment,
                    schema=deeply_nested_schema,
                )

    def test_commitment_is_deterministic_across_creation_order_location_and_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            first_paths = prepare_tree(temporary / "first")
            second_paths = prepare_tree(temporary / "second", reverse=True)
            for path in (temporary / "second").rglob("*"):
                if path.is_file():
                    os.utime(path, (1_000_000_000, 1_000_000_000))

            first = build_submission_commitment(**first_paths)
            second = build_submission_commitment(**second_paths)
            self.assertEqual(first, second)

            (temporary / "second" / "empty-directory-2").mkdir()
            with_extra_directory = build_submission_commitment(**second_paths)
            self.assertNotEqual(
                first["tree"]["tree_sha256"],
                with_extra_directory["tree"]["tree_sha256"],
            )

            (temporary / "second" / "empty-directory-2").rmdir()
            (temporary / "second" / "src/run.py").chmod(0o644)
            without_executable_bit = build_submission_commitment(**second_paths)
            self.assertNotEqual(
                first["tree"]["tree_sha256"],
                without_executable_bit["tree"]["tree_sha256"],
            )

    def test_v0_1_digest_golden_vector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "tree"
            (root / "empty").mkdir(parents=True)
            (root / "run.py").write_bytes(b"print('ok')\n")
            (root / "run.py").chmod(0o755)
            (root / "config.json").write_bytes(b"{}\n")
            (root / "zero.bin").write_bytes(b"")
            commitment = build_submission_commitment(
                root=root,
                benchmark_definition_sha256=BENCHMARK_SHA256,
                entrypoint="run.py",
                config_files=["config.json"],
                static_arguments=["--fixed"],
            )
            self.assertEqual(
                "sha256:72eca6974faf753e852832d7ec630b3f62ceb70503b74a790c028eeb88bd38b3",
                commitment["tree"]["tree_sha256"],
            )
            self.assertEqual(
                "sha256:3ee9eed5ec6d8ea2c28dba8cc304772c64e9c929a9a070b57c6b114f3e9a3811",
                commitment["commitment_sha256"],
            )

    def test_content_addition_removal_and_rename_fail_verification(self) -> None:
        mutations = ("one_byte", "add", "remove", "rename")
        for mutation in mutations:
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory) / "submission"
                paths = prepare_tree(root)
                commitment = build_submission_commitment(**paths)
                if mutation == "one_byte":
                    (root / "weights/model.bin").write_bytes(b"\x00\x01\x02\x04")
                elif mutation == "add":
                    (root / "added.txt").write_text("added\n", encoding="utf-8")
                elif mutation == "remove":
                    (root / "README.md").unlink()
                else:
                    (root / "README.md").rename(root / "RENAMED.md")

                report = verify_submission_commitment(commitment, root=root)
                self.assertFalse(report.valid)
                self.assertFalse(report.tree_matches)
                self.assertFalse(report.as_dict()["blind_claim_allowed"])

    def test_path_profile_rejects_traversal_unicode_controls_and_reserved_names(self) -> None:
        unsafe = (
            "/absolute.py",
            "../outside.py",
            "a/../outside.py",
            "a//b.py",
            "a/./b.py",
            r"a\b.py",
            "C:drive.py",
            "control\n.py",
            "CON",
            "name.",
            "café.py",
        )
        for value in unsafe:
            with self.subTest(value=value), self.assertRaises(SubmissionCommitmentError):
                normalize_logical_path(value)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "submission"
            paths = prepare_tree(root)
            paths["entrypoint"] = "../outside.py"
            with self.assertRaises(SubmissionCommitmentError):
                build_submission_commitment(**paths)

            unicode_file = root / "café.txt"
            unicode_file.write_text("unsafe path profile\n", encoding="utf-8")
            paths["entrypoint"] = "src/run.py"
            with self.assertRaisesRegex(SubmissionCommitmentError, "ASCII"):
                build_submission_commitment(**paths)

    def test_case_collision_and_recomputed_claim_injection_still_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = prepare_tree(Path(temporary_directory) / "submission")
            commitment = build_submission_commitment(**paths)

            collision = copy.deepcopy(commitment)
            for entry in collision["tree"]["entries"]:
                if entry["path"] == "README.md":
                    entry["path"] = "A.txt"
                elif entry["path"] == "uv.lock":
                    entry["path"] = "a.txt"
            collision["tree"]["entries"].sort(key=lambda entry: entry["path"].encode("utf-8"))
            with self.assertRaisesRegex(SubmissionCommitmentError, "collision"):
                validate_submission_commitment(collision)

            injected = copy.deepcopy(commitment)
            injected["assurance"]["blind_claim_allowed"] = True
            digest = submission_commitment_digest(injected)
            injected["commitment_sha256"] = digest
            injected["commitment_id"] = f"submission-commitment:{digest}"
            with self.assertRaisesRegex(SubmissionCommitmentError, "cannot claim"):
                validate_submission_commitment(injected)

            report = verify_submission_commitment(injected, root=paths["root"])
            self.assertFalse(report.valid)
            self.assertFalse(report.self_consistent)
            self.assertFalse(report.as_dict()["blind_claim_allowed"])

    def test_claim_like_tree_content_cannot_change_output_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "submission"
            paths = prepare_tree(root)
            (root / "claim.json").write_text(
                '{"blind_claim_allowed":true,"externally_anchored":true}\n',
                encoding="utf-8",
            )
            commitment = build_submission_commitment(**paths)
            self.assertFalse(commitment["assurance"]["blind_claim_allowed"])
            report = verify_submission_commitment(commitment, root=root).as_dict()
            self.assertTrue(report["valid"])
            self.assertFalse(report["blind_claim_allowed"])
            self.assertFalse(report["externally_anchored"])

    def test_symlink_hardlink_fifo_socket_and_root_symlink_fail_closed(self) -> None:
        cases = ("file_symlink", "directory_symlink", "hardlink", "fifo", "socket")
        for case in cases:
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                temporary = Path(temporary_directory)
                root = temporary / "submission"
                paths = prepare_tree(root)
                outside_file = temporary / "outside.txt"
                outside_file.write_text("outside\n", encoding="utf-8")
                if case == "file_symlink":
                    (root / "linked.txt").symlink_to(outside_file)
                elif case == "directory_symlink":
                    outside_directory = temporary / "outside-directory"
                    outside_directory.mkdir()
                    (root / "linked-directory").symlink_to(
                        outside_directory,
                        target_is_directory=True,
                    )
                elif case == "hardlink":
                    os.link(outside_file, root / "hardlinked.txt")
                elif case == "fifo":
                    os.mkfifo(root / "pipe")
                else:
                    unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.addCleanup(unix_socket.close)
                    unix_socket.bind(str(root / "socket"))
                with self.assertRaises(SubmissionCommitmentError):
                    build_submission_commitment(**paths)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            real_root = temporary / "real"
            paths = prepare_tree(real_root)
            linked_root = temporary / "linked"
            linked_root.symlink_to(real_root, target_is_directory=True)
            paths["root"] = linked_root
            with self.assertRaisesRegex(SubmissionCommitmentError, "real directory"):
                build_submission_commitment(**paths)

    def test_same_size_mutation_during_read_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "submission"
            root.mkdir()
            target = root / "run.py"
            target.write_bytes(b"A" * (2 * 1024 * 1024))
            real_read = commitment_module.os.read
            mutated = False

            def racing_read(descriptor: int, byte_count: int) -> bytes:
                nonlocal mutated
                chunk = real_read(descriptor, byte_count)
                if chunk and not mutated:
                    target.write_bytes(b"B" * (2 * 1024 * 1024))
                    mutated = True
                return chunk

            with (
                patch.object(commitment_module.os, "read", side_effect=racing_read),
                self.assertRaisesRegex(SubmissionCommitmentError, "changed while"),
            ):
                build_submission_commitment(
                    root=root,
                    benchmark_definition_sha256=BENCHMARK_SHA256,
                    entrypoint="run.py",
                )
            self.assertTrue(mutated)

    def test_namespace_change_between_complete_inventories_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "submission"
            root.mkdir()
            (root / "run.py").write_text("pass\n", encoding="utf-8")
            real_scan = commitment_module._scan_tree_once
            call_count = 0

            def mutate_after_scan(scan_root: Path) -> Any:
                nonlocal call_count
                snapshot = real_scan(scan_root)
                call_count += 1
                if call_count == 1:
                    (root / "added-after-first-scan.txt").write_text(
                        "race\n",
                        encoding="utf-8",
                    )
                return snapshot

            with (
                patch.object(
                    commitment_module,
                    "_scan_tree_once",
                    side_effect=mutate_after_scan,
                ),
                self.assertRaisesRegex(
                    SubmissionCommitmentError,
                    "changed between",
                ),
            ):
                build_submission_commitment(
                    root=root,
                    benchmark_definition_sha256=BENCHMARK_SHA256,
                    entrypoint="run.py",
                )
            self.assertEqual(2, call_count)

    def test_limits_and_static_argument_controls_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "submission"
            paths = prepare_tree(root)
            with (
                patch.object(commitment_module, "MAX_FILE_BYTES", 3),
                self.assertRaisesRegex(SubmissionCommitmentError, "file exceeds"),
            ):
                build_submission_commitment(**paths)

            with (
                patch.object(commitment_module, "MAX_ENTRIES", 3),
                self.assertRaisesRegex(SubmissionCommitmentError, "exceeds 3 entries"),
            ):
                build_submission_commitment(**paths)

            with (
                patch.object(commitment_module, "MAX_DIRECTORIES", 0),
                self.assertRaisesRegex(SubmissionCommitmentError, "exceeds 0 directories"),
            ):
                build_submission_commitment(**paths)

            with (
                patch.object(commitment_module, "MAX_TOTAL_BYTES", 3),
                self.assertRaisesRegex(SubmissionCommitmentError, "aggregate limit"),
            ):
                build_submission_commitment(**paths)

            with (
                patch.object(commitment_module, "MAX_STATIC_ARGUMENTS", 1),
                self.assertRaisesRegex(SubmissionCommitmentError, "more than 1"),
            ):
                build_submission_commitment(**paths)

            with (
                patch.object(commitment_module, "MAX_STATIC_ARGUMENT_TOTAL_BYTES", 3),
                self.assertRaisesRegex(SubmissionCommitmentError, "aggregate byte limit"),
            ):
                build_submission_commitment(**paths)

            paths["static_arguments"] = ["unsafe\nargument"]
            with self.assertRaisesRegex(SubmissionCommitmentError, "control"):
                build_submission_commitment(**paths)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "submission"
            deep_parent = root.joinpath(*(["a"] * commitment_module.MAX_DEPTH))
            deep_parent.mkdir(parents=True)
            (root / "run.py").write_text("pass\n", encoding="utf-8")
            (deep_parent / "too-deep.txt").write_text("deep\n", encoding="utf-8")
            with self.assertRaisesRegex(SubmissionCommitmentError, "exceeds depth"):
                build_submission_commitment(
                    root=root,
                    benchmark_definition_sha256=BENCHMARK_SHA256,
                    entrypoint="run.py",
                )

    def test_entry_limit_counts_parent_siblings_before_recursion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "submission"
            (root / "a").mkdir(parents=True)
            (root / "b").mkdir()
            (root / "c").mkdir()
            (root / "a" / "x").write_text("x\n", encoding="utf-8")
            (root / "a" / "y").write_text("y\n", encoding="utf-8")
            real_scandir = os.scandir
            stat_calls = 0

            class CountingEntry:
                def __init__(self, entry: Any) -> None:
                    self._entry = entry
                    self.name = entry.name

                def stat(self, *, follow_symlinks: bool) -> os.stat_result:
                    nonlocal stat_calls
                    stat_calls += 1
                    return self._entry.stat(follow_symlinks=follow_symlinks)

            class CountingScandir:
                def __init__(self, path: Any) -> None:
                    self._iterator = real_scandir(path)

                def __enter__(self) -> Any:
                    return (CountingEntry(entry) for entry in self._iterator)

                def __exit__(self, *_args: Any) -> None:
                    self._iterator.close()

            with (
                patch.object(
                    commitment_module.os,
                    "scandir",
                    side_effect=CountingScandir,
                ),
                patch.object(
                    commitment_module,
                    "_require_secure_tree_platform",
                ),
                patch.object(commitment_module, "MAX_ENTRIES", 3),
                self.assertRaisesRegex(SubmissionCommitmentError, "exceeds 3 entries"),
            ):
                build_submission_commitment(
                    root=root,
                    benchmark_definition_sha256=BENCHMARK_SHA256,
                    entrypoint="a/x",
                )
            self.assertEqual(3, stat_calls)

    def test_strict_bounded_manifest_reader(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            duplicate = temporary / "duplicate.json"
            duplicate.write_text('{"schema_version":"0.1.0","schema_version":"0.1.0"}\n')
            with self.assertRaisesRegex(SubmissionCommitmentError, "duplicate JSON key"):
                read_submission_commitment(duplicate)

            floating = temporary / "floating.json"
            floating.write_text('{"value":1.0}\n')
            with self.assertRaisesRegex(SubmissionCommitmentError, "floats"):
                read_submission_commitment(floating)

            invalid_utf8 = temporary / "invalid.json"
            invalid_utf8.write_bytes(b"\xff")
            with self.assertRaisesRegex(SubmissionCommitmentError, "UTF-8"):
                read_submission_commitment(invalid_utf8)

            oversized = temporary / "oversized.json"
            oversized.write_bytes(b"{}")
            with (
                patch.object(commitment_module, "MAX_MANIFEST_BYTES", 1),
                self.assertRaisesRegex(SubmissionCommitmentError, "at most"),
            ):
                read_submission_commitment(oversized)

            deeply_nested = temporary / "deep.json"
            deeply_nested.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
            with self.assertRaisesRegex(SubmissionCommitmentError, "invalid JSON|depth"):
                read_submission_commitment(deeply_nested)
            result, stdout, stderr = run_cli(
                [
                    "verify-submission-commitment",
                    str(deeply_nested),
                    str(temporary),
                ]
            )
            self.assertEqual(2, result, stderr)
            self.assertFalse(json.loads(stdout)["valid"])

            deeply_nested_value: dict[str, Any] = {}
            for _ in range(200):
                deeply_nested_value = {"child": deeply_nested_value}
            with self.assertRaisesRegex(SubmissionCommitmentError, "depth"):
                validate_submission_commitment(deeply_nested_value)

    def test_cli_build_verify_output_boundary_and_no_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            output = temporary / "commitment.json"
            build_args = submission_cli_args(root, output)
            build_result, build_stdout, build_stderr = run_cli(build_args)
            self.assertEqual(0, build_result, build_stderr)
            build_payload = json.loads(build_stdout)
            self.assertTrue(build_payload["written"])
            self.assertFalse(build_payload["blind_claim_allowed"])
            self.assertTrue(build_payload["output_boundary_preserved"])
            self.assertTrue(build_payload["requested_path_verified"])
            self.assertTrue(build_payload["post_write_tree_verified"])
            self.assertTrue(build_payload["final_output_matches"])
            self.assertEqual(
                "committed_and_verified_at_check",
                build_payload["postcondition"],
            )
            self.assertFalse(build_payload["postconditions_atomic"])
            self.assertFalse(build_payload["future_immutability_attested"])
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))

            verify_result, verify_stdout, verify_stderr = run_cli(
                [
                    "verify-submission-commitment",
                    str(output),
                    str(root),
                    "--expected-commitment-sha256",
                    build_payload["commitment_sha256"],
                ]
            )
            self.assertEqual(0, verify_result, verify_stderr)
            verify_payload = json.loads(verify_stdout)
            self.assertTrue(verify_payload["valid"])
            self.assertTrue(verify_payload["expected_digest_match"])
            self.assertFalse(verify_payload["externally_anchored"])

            repeated_result, _, repeated_error = run_cli(build_args)
            self.assertEqual(1, repeated_result)
            self.assertIn("refusing to overwrite", repeated_error)

            inside_output = root / "commitment.json"
            inside_args = build_args.copy()
            inside_args[2] = str(inside_output)
            inside_result, inside_stdout, inside_error = run_cli(inside_args)
            self.assertEqual(2, inside_result, inside_error)
            inside_payload = json.loads(inside_stdout)
            self.assertFalse(inside_payload["written"])
            self.assertFalse(inside_payload["blind_claim_allowed"])
            self.assertFalse(inside_output.exists())

            malformed = temporary / "malformed.json"
            malformed.write_text('{"x":1,"x":2}\n', encoding="utf-8")
            malformed_result, malformed_stdout, _ = run_cli(
                ["verify-submission-commitment", str(malformed), str(root)]
            )
            self.assertEqual(2, malformed_result)
            malformed_payload = json.loads(malformed_stdout)
            self.assertFalse(malformed_payload["valid"])
            self.assertFalse(malformed_payload["blind_claim_allowed"])

            dangling_output = temporary / "dangling.json"
            dangling_output.symlink_to(temporary / "missing.json")
            dangling_args = build_args.copy()
            dangling_args[2] = str(dangling_output)
            dangling_result, _, dangling_error = run_cli(dangling_args)
            self.assertEqual(1, dangling_result)
            self.assertIn("refusing to overwrite", dangling_error)
            self.assertTrue(dangling_output.is_symlink())

    def test_case_variant_output_parent_is_rejected_by_inode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "RootCase"
            prepare_tree(root)
            case_variant_parent = temporary / "rootcase"
            if not case_variant_parent.exists():
                return
            self.assertTrue(os.path.samefile(root, case_variant_parent))
            output = case_variant_parent / "commitment.json"
            result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertFalse(payload["written"])
            self.assertFalse(output.exists())

    def test_output_parent_symlink_swap_cannot_redirect_into_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            outside_parent = temporary / "outside"
            outside_parent.mkdir()
            output_parent = temporary / "output-link"
            output_parent.symlink_to(outside_parent, target_is_directory=True)
            output = output_parent / "commitment.json"
            real_builder = cli_module.build_submission_commitment

            def swap_parent(**kwargs: Any) -> dict[str, Any]:
                output_parent.unlink()
                output_parent.symlink_to(root, target_is_directory=True)
                return real_builder(**kwargs)

            with patch.object(
                cli_module,
                "build_submission_commitment",
                side_effect=swap_parent,
            ):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertFalse(payload["requested_path_verified"])
            self.assertFalse((root / "commitment.json").exists())
            self.assertTrue((outside_parent / "commitment.json").is_file())

    def test_staging_tamper_is_published_only_as_failed_postcondition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            output = temporary / "commitment.json"
            real_link = cli_module.os.link

            def tampering_link(
                source: str,
                destination: str,
                *,
                src_dir_fd: int,
                dst_dir_fd: int,
                follow_symlinks: bool,
            ) -> None:
                descriptor = os.open(
                    source,
                    os.O_WRONLY | os.O_TRUNC,
                    dir_fd=src_dir_fd,
                )
                try:
                    os.write(descriptor, b'{"tampered":true}\n')
                finally:
                    os.close(descriptor)
                real_link(
                    source,
                    destination,
                    src_dir_fd=src_dir_fd,
                    dst_dir_fd=dst_dir_fd,
                    follow_symlinks=follow_symlinks,
                )

            with patch.object(cli_module.os, "link", side_effect=tampering_link):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertFalse(payload["output_content_verified"])
            self.assertEqual(b'{"tampered":true}\n', output.read_bytes())

    def test_directory_fsync_failure_is_not_reported_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            output = temporary / "commitment.json"
            real_fsync = cli_module.os.fsync

            def fail_directory_fsync(descriptor: int) -> None:
                if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    raise OSError(errno.ENOTSUP, "synthetic directory fsync failure")
                real_fsync(descriptor)

            with patch.object(cli_module.os, "fsync", side_effect=fail_directory_fsync):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertTrue(payload["output_content_verified"])
            self.assertFalse(payload["durability_confirmed"])
            self.assertEqual(
                "published_but_not_fully_verified",
                payload["postcondition"],
            )
            self.assertTrue(output.is_file())

    def test_extended_acl_is_rejected_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            output = temporary / "commitment.json"
            with patch.object(
                cli_module,
                "_descriptor_has_extended_acl",
                return_value=True,
            ):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertFalse(payload["written"])
            self.assertFalse(output.exists())

        if sys.platform == "darwin":
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary = Path(temporary_directory)
                root = temporary / "submission"
                prepare_tree(root)
                output_parent = temporary / "inherited-acl"
                output_parent.mkdir()
                output = output_parent / "commitment.json"
                subprocess.run(
                    [
                        "chmod",
                        "+a",
                        "everyone allow read,write,file_inherit",
                        str(output_parent),
                    ],
                    check=True,
                )
                try:
                    result, stdout, stderr = run_cli(submission_cli_args(root, output))
                    self.assertEqual(2, result, stderr)
                    payload = json.loads(stdout)
                    self.assertFalse(payload["valid"])
                    self.assertFalse(payload["written"])
                    self.assertFalse(output.exists())
                finally:
                    subprocess.run(
                        ["chmod", "-a#", "0", str(output_parent)],
                        check=True,
                    )

    def test_final_acl_recheck_is_required_for_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            output = temporary / "commitment.json"
            acl_checks = 0

            def appear_after_publication(_descriptor: int) -> bool:
                nonlocal acl_checks
                acl_checks += 1
                return acl_checks >= 5

            with patch.object(
                cli_module,
                "_descriptor_has_extended_acl",
                side_effect=appear_after_publication,
            ):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertFalse(payload["final_output_matches"])
            self.assertGreaterEqual(acl_checks, 5)

    def test_final_mode_change_is_not_reported_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            output = temporary / "commitment.json"
            real_verify = cli_module.verify_submission_commitment

            def change_mode_then_verify(*args: Any, **kwargs: Any) -> Any:
                output.chmod(0o644)
                return real_verify(*args, **kwargs)

            with patch.object(
                cli_module,
                "verify_submission_commitment",
                side_effect=change_mode_then_verify,
            ):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertFalse(payload["final_output_matches"])
            self.assertEqual(0o644, stat.S_IMODE(output.stat().st_mode))

    def test_final_exact_bytes_reject_bool_integer_equivalence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            output = temporary / "commitment.json"
            real_verify = cli_module.verify_submission_commitment

            def tamper_then_verify(*args: Any, **kwargs: Any) -> Any:
                raw = output.read_bytes()
                tampered = raw.replace(
                    b'"blind_claim_allowed": false',
                    b'"blind_claim_allowed": 0',
                    1,
                )
                self.assertNotEqual(raw, tampered)
                output.write_bytes(tampered)
                return real_verify(*args, **kwargs)

            with patch.object(
                cli_module,
                "verify_submission_commitment",
                side_effect=tamper_then_verify,
            ):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertFalse(payload["final_output_matches"])
            self.assertIn(b'"blind_claim_allowed": 0', output.read_bytes())

    def test_final_requested_parent_swap_is_not_reported_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            outside_parent = temporary / "outside"
            outside_parent.mkdir()
            output_parent = temporary / "output-link"
            output_parent.symlink_to(outside_parent, target_is_directory=True)
            output = output_parent / "commitment.json"
            pinned_output = outside_parent / "commitment.json"
            real_verify = cli_module.verify_submission_commitment

            def swap_after_verify(*args: Any, **kwargs: Any) -> Any:
                report = real_verify(*args, **kwargs)
                output_parent.unlink()
                output_parent.symlink_to(root, target_is_directory=True)
                (root / "commitment.json").write_bytes(pinned_output.read_bytes())
                return report

            with patch.object(
                cli_module,
                "verify_submission_commitment",
                side_effect=swap_after_verify,
            ):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertFalse(payload["final_output_matches"])
            self.assertTrue(pinned_output.is_file())
            self.assertTrue((root / "commitment.json").is_file())

    def test_post_publication_cleanup_failure_preserves_written_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            root = temporary / "submission"
            prepare_tree(root)
            output = temporary / "commitment.json"
            real_cleanup = cli_module._unlink_submission_staging_if_same
            cleanup_calls = 0

            def fail_second_cleanup(*args: Any, **kwargs: Any) -> None:
                nonlocal cleanup_calls
                cleanup_calls += 1
                if cleanup_calls == 1:
                    real_cleanup(*args, **kwargs)
                    return
                raise OSError(errno.EIO, "synthetic final cleanup failure")

            with patch.object(
                cli_module,
                "_unlink_submission_staging_if_same",
                side_effect=fail_second_cleanup,
            ):
                result, stdout, stderr = run_cli(submission_cli_args(root, output))
            self.assertEqual(2, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertFalse(payload["durability_confirmed"])
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
