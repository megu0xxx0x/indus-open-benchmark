from __future__ import annotations

import copy
import errno
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

import indusbench.cli as cli_module
from indusbench.cli import main
from indusbench.io import write_json, write_jsonl
from indusbench.museum_intake import (
    MET_SOURCE_ID,
    POLICY_EVIDENCE_SPECS,
    JsonDocument,
    PolicyDocument,
    build_met_intake,
)
from indusbench.schema_validation import validate_schema_instance
from indusbench.smithsonian_metadata import (
    validate_smithsonian_metadata_semantics,
)
from tests.test_museum_review import valid_review
from tests.test_penn_metadata import csv_bytes, penn_row
from tests.test_smithsonian_metadata import (
    SCHEMA as SMITHSONIAN_SCHEMA,
)
from tests.test_smithsonian_metadata import (
    SOURCE_URL as SMITHSONIAN_SOURCE_URL,
)
from tests.test_smithsonian_metadata import json_record_bytes, synthetic_record
from tests.test_validation import valid_artifact

ROOT = Path(__file__).resolve().parents[1]


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(argv)
    return result, stdout.getvalue(), stderr.getvalue()


def distinct_records(count: int = 6) -> list[dict]:
    records = []
    for index in range(count):
        record = valid_artifact(f"SYN:A{index:03d}")
        record["duplicate_family_id"] = f"SYN:F{index:03d}"
        record["images"][0]["image_id"] = f"SYN:IMG{index:03d}"
        record["images"][0]["image_hash"] = f"sha256:{index + 10:064x}"
        record["sides"][0]["image_ids"] = [record["images"][0]["image_id"]]
        record["sides"][0]["lines"][0]["tokens"][0]["sign_id"] = f"SYN:{index + 10:03d}"
        records.append(record)
    return records


class CliTests(unittest.TestCase):
    def test_parse_penn_metadata_is_local_metadata_only_and_no_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "penn.csv"
            output = temporary / "penn-snapshot.json"
            source_bytes = csv_bytes([penn_row()])
            source.write_bytes(source_bytes)
            source_sha256 = "sha256:" + hashlib.sha256(source_bytes).hexdigest()

            result, stdout, error = run_cli(
                [
                    "parse-penn-metadata",
                    str(source),
                    str(output),
                    "--retrieved-at",
                    "2026-07-27T04:05:06Z",
                    "--source-last-updated",
                    "2026-07-01",
                    "--etag",
                    '"synthetic-etag"',
                    "--last-modified",
                    "Thu, 02 Jul 2026 03:54:37 GMT",
                    "--expected-sha256",
                    source_sha256,
                ]
            )
            self.assertEqual(0, result, error)
            summary = json.loads(stdout)
            self.assertTrue(summary["written"])
            self.assertEqual(1, summary["primary_script_candidate_count"])
            self.assertFalse(summary["images_included"])
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(32, len(snapshot["csv_header"]))
            self.assertFalse(snapshot["source"]["images_included"])
            self.assertNotIn("media", snapshot)

            repeated_result, _, repeated_error = run_cli(
                [
                    "parse-penn-metadata",
                    str(source),
                    str(output),
                    "--retrieved-at",
                    "2026-07-27T04:05:06Z",
                ]
            )
            self.assertEqual(1, repeated_result)
            self.assertIn("refusing to overwrite", repeated_error)

            mismatch_output = temporary / "mismatch.json"
            mismatch_result, mismatch_stdout, mismatch_error = run_cli(
                [
                    "parse-penn-metadata",
                    str(source),
                    str(mismatch_output),
                    "--retrieved-at",
                    "2026-07-27T04:05:06Z",
                    "--expected-sha256",
                    "sha256:" + "0" * 64,
                ]
            )
            self.assertEqual(2, mismatch_result, mismatch_error)
            self.assertFalse(json.loads(mismatch_stdout)["valid"])
            self.assertFalse(mismatch_output.exists())

            durability_output = temporary / "penn-durability-unknown.json"
            real_rename = cli_module._rename_regular_file_no_replace

            def rename_then_report_unknown(source_path: Path, destination: Path) -> None:
                real_rename(source_path, destination)
                raise cli_module._CommittedDurabilityUnknown(
                    errno.ENOTSUP,
                    "synthetic directory durability failure",
                    str(destination),
                    content_verified=True,
                )

            with patch(
                "indusbench.cli._rename_regular_file_no_replace",
                side_effect=rename_then_report_unknown,
            ):
                durability_result, durability_stdout, durability_error = run_cli(
                    [
                        "parse-penn-metadata",
                        str(source),
                        str(durability_output),
                        "--retrieved-at",
                        "2026-07-27T04:05:06Z",
                    ]
                )
            self.assertEqual(1, durability_result)
            self.assertEqual("", durability_error)
            durability_payload = json.loads(durability_stdout)
            self.assertTrue(durability_payload["written"])
            self.assertTrue(durability_payload["output_content_verified"])
            self.assertEqual(
                "committed_durability_unknown",
                durability_payload["postcondition"],
            )
            self.assertTrue(durability_output.is_file())

    def test_parse_smithsonian_metadata_is_local_raw_bound_and_no_replace(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "smithsonian-01.txt"
            output = temporary / "smithsonian-record.json"
            first = synthetic_record(identifier="first")
            target = synthetic_record(
                identifier="target",
                title="Mohenjo-Daro Square Seal Cast",
                notes="Cast/replica.",
            )
            raw_bytes = json_record_bytes(first) + b"\n" + json_record_bytes(target) + b"\n"
            source.write_bytes(raw_bytes)
            source_sha256 = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()

            result, stdout, error = run_cli(
                [
                    "parse-smithsonian-metadata",
                    str(source),
                    str(output),
                    "--source-url",
                    SMITHSONIAN_SOURCE_URL,
                    "--retrieved-at",
                    "2026-07-27T04:05:06Z",
                    "--line-number",
                    "2",
                    "--expected-sha256",
                    source_sha256,
                ]
            )
            self.assertEqual(0, result, error)
            payload = json.loads(stdout)
            self.assertTrue(payload["valid"])
            self.assertTrue(payload["written"])
            self.assertEqual(2, payload["line_number"])
            self.assertEqual(
                "nmnhanthropology_target",
                payload["record_ID"],
            )
            self.assertTrue(payload["external_digest_checked"])
            self.assertFalse(payload["publication_or_training_release_allowed"])

            record = json.loads(output.read_text(encoding="utf-8"))
            validate_smithsonian_metadata_semantics(
                record,
                raw_jsonl_bytes=raw_bytes,
            )
            self.assertEqual(
                [],
                validate_schema_instance(record, SMITHSONIAN_SCHEMA),
            )
            self.assertEqual(
                source_sha256,
                record["source_acquisition"]["container"]["sha256"],
            )

            repeated_result, _, repeated_error = run_cli(
                [
                    "parse-smithsonian-metadata",
                    str(source),
                    str(output),
                    "--source-url",
                    SMITHSONIAN_SOURCE_URL,
                    "--retrieved-at",
                    "2026-07-27T04:05:06Z",
                    "--line-number",
                    "2",
                ]
            )
            self.assertEqual(1, repeated_result)
            self.assertIn("refusing to overwrite", repeated_error)

            mismatch_output = temporary / "mismatch.json"
            mismatch_result, mismatch_stdout, mismatch_error = run_cli(
                [
                    "parse-smithsonian-metadata",
                    str(source),
                    str(mismatch_output),
                    "--source-url",
                    SMITHSONIAN_SOURCE_URL,
                    "--retrieved-at",
                    "2026-07-27T04:05:06Z",
                    "--line-number",
                    "2",
                    "--expected-sha256",
                    "sha256:" + "0" * 64,
                ]
            )
            self.assertEqual(2, mismatch_result, mismatch_error)
            self.assertFalse(json.loads(mismatch_stdout)["written"])
            self.assertFalse(mismatch_output.exists())

            durability_output = temporary / "smithsonian-durability-unknown.json"
            real_rename = cli_module._rename_regular_file_no_replace

            def rename_then_report_unknown(source_path: Path, destination: Path) -> None:
                real_rename(source_path, destination)
                raise cli_module._CommittedDurabilityUnknown(
                    errno.ENOTSUP,
                    "synthetic directory durability failure",
                    str(destination),
                    content_verified=True,
                )

            with patch(
                "indusbench.cli._rename_regular_file_no_replace",
                side_effect=rename_then_report_unknown,
            ):
                durability_result, durability_stdout, durability_error = run_cli(
                    [
                        "parse-smithsonian-metadata",
                        str(source),
                        str(durability_output),
                        "--source-url",
                        SMITHSONIAN_SOURCE_URL,
                        "--retrieved-at",
                        "2026-07-27T04:05:06Z",
                        "--line-number",
                        "2",
                    ]
                )
            self.assertEqual(1, durability_result)
            self.assertEqual("", durability_error)
            durability_payload = json.loads(durability_stdout)
            self.assertTrue(durability_payload["written"])
            self.assertTrue(durability_payload["output_content_verified"])
            self.assertEqual(
                "committed_durability_unknown",
                durability_payload["postcondition"],
            )
            self.assertTrue(durability_output.is_file())

    def test_validate_normative_fixture(self) -> None:
        result, output, error = run_cli(
            [
                "validate",
                str(ROOT / "examples/synthetic_corpus.jsonl"),
            ]
        )
        self.assertEqual(0, result, error)
        self.assertTrue(json.loads(output)["valid"])

    def test_split_audit_baseline_manifest_and_control(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            corpus = temporary / "corpus.jsonl"
            split_dir = temporary / "split"
            write_jsonl(corpus, distinct_records())

            split_result, split_output, split_error = run_cli(
                [
                    "split",
                    str(corpus),
                    str(split_dir),
                    "--test-fraction",
                    "0.34",
                    "--seed",
                    "9",
                ]
            )
            self.assertEqual(0, split_result, split_error)
            self.assertTrue(json.loads(split_output)["written"])

            audit_result, audit_output, audit_error = run_cli(
                [
                    "audit",
                    str(split_dir / "train.jsonl"),
                    str(split_dir / "development.jsonl"),
                ]
            )
            self.assertEqual(0, audit_result, audit_error)
            self.assertFalse(json.loads(audit_output)["has_leakage"])

            baseline_result, baseline_output, baseline_error = run_cli(
                [
                    "baseline",
                    str(split_dir / "train.jsonl"),
                    str(split_dir / "development.jsonl"),
                ]
            )
            self.assertEqual(0, baseline_result, baseline_error)
            self.assertEqual(
                "structural baseline only; no phonetic or semantic inference",
                json.loads(baseline_output)["scientific_scope"],
            )

            evaluator_config = temporary / "evaluator-config.json"
            write_json(
                evaluator_config,
                {
                    "schema_version": "0.1.0",
                    "config_id": "cli-development-v0.1",
                    "claim_class": "public_development",
                    "entrypoint": "indusbench.cli:main",
                    "commands": ["audit", "baseline"],
                    "metrics": ["heldout_log_loss"],
                    "random_seeds": [9],
                    "network_access_required": False,
                    "notes": "CLI test for an explicitly public development evaluator.",
                },
            )
            lock_path = temporary / "benchmark-lock.json"
            evaluator_file = ROOT / "src/indusbench/baseline.py"
            lock_result, lock_output, lock_error = run_cli(
                [
                    "lock-benchmark",
                    str(corpus),
                    str(split_dir),
                    str(evaluator_config),
                    str(lock_path),
                    "--evaluator-file",
                    str(evaluator_file),
                    "--created-by",
                    "cli-test",
                    "--created-at",
                    "2026-07-27T00:00:00Z",
                ]
            )
            self.assertEqual(0, lock_result, lock_error)
            lock_payload = json.loads(lock_output)
            self.assertTrue(lock_payload["written"])
            self.assertFalse(lock_payload["blind_claim_allowed"])
            self.assertFalse(lock_payload["externally_anchored"])

            verify_result, verify_output, verify_error = run_cli(
                [
                    "verify-benchmark-lock",
                    str(lock_path),
                    str(corpus),
                    str(split_dir),
                    str(evaluator_config),
                    "--evaluator-file",
                    str(evaluator_file),
                    "--expected-definition-sha256",
                    lock_payload["definition_sha256"],
                ]
            )
            self.assertEqual(0, verify_result, verify_error)
            verify_payload = json.loads(verify_output)
            self.assertTrue(verify_payload["valid"])
            self.assertTrue(verify_payload["expected_digest_match"])
            self.assertFalse(verify_payload["externally_anchored"])
            self.assertFalse(verify_payload["blind_claim_allowed"])

            manifest_result, manifest_output, manifest_error = run_cli(["manifest", str(corpus)])
            self.assertEqual(0, manifest_result, manifest_error)
            self.assertEqual(6, json.loads(manifest_output)["counts"]["artifacts"])

            control_path = temporary / "control.jsonl"
            control_result, control_output, control_error = run_cli(
                ["control-shuffle", str(corpus), str(control_path), "--seed", "3"]
            )
            self.assertEqual(0, control_result, control_error)
            self.assertTrue(json.loads(control_output)["written"])
            self.assertTrue(control_path.is_file())

    def test_quarantine_blocks_normal_paths_and_requires_explicit_audit_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            train_path = temporary / "blocked-train.jsonl"
            test_path = temporary / "clean-test.jsonl"
            blocked, clean = distinct_records(2)
            blocked["source_records"][0]["source_id"] = "external-indusbench"
            blocked["images"][0]["source_id"] = "external-indusbench"
            blocked["source_records"][0]["locator"] = (
                "https://github.com/prabhatchanchal/IndusBench/test.json"
            )
            write_jsonl(train_path, [blocked])
            write_jsonl(test_path, [clean])

            blocked_commands = [
                ["validate", str(train_path)],
                ["split", str(train_path), str(temporary / "split")],
                ["audit", str(train_path), str(test_path)],
                ["baseline", str(train_path), str(test_path)],
                [
                    "control-shuffle",
                    str(train_path),
                    str(temporary / "control.jsonl"),
                    "--seed",
                    "1",
                ],
                [
                    "null-evaluate",
                    str(train_path),
                    str(test_path),
                    "--runs",
                    "1",
                ],
                ["treewidth-audit", str(train_path), "--runs", "1"],
                ["manifest", str(train_path)],
            ]
            for command in blocked_commands:
                with self.subTest(command=command[0]):
                    result, output, error = run_cli(command)
                    self.assertEqual(2, result, error)
                    payload = json.loads(output)
                    self.assertFalse(payload.get("valid", True))
                    quarantine = payload["quarantine"]
                    self.assertGreater(quarantine["finding_count"], 0)

            self.assertFalse((temporary / "split").exists())
            self.assertFalse((temporary / "control.jsonl").exists())

            audit_result, audit_output, audit_error = run_cli(
                [
                    "audit",
                    str(train_path),
                    str(test_path),
                    "--allow-quarantined-for-audit",
                ]
            )
            self.assertEqual(0, audit_result, audit_error)
            audit_payload = json.loads(audit_output)
            self.assertFalse(audit_payload["has_leakage"])
            self.assertTrue(audit_payload["quarantine"]["audit_only_override"])
            self.assertGreater(audit_payload["quarantine"]["finding_count"], 0)

    def test_refuses_to_overwrite_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            corpus = temporary / "corpus.jsonl"
            output = temporary / "control.jsonl"
            write_jsonl(corpus, distinct_records())
            output.write_text("preserve me\n", encoding="utf-8")

            result, _, error = run_cli(["control-shuffle", str(corpus), str(output), "--seed", "3"])

            self.assertEqual(1, result)
            self.assertIn("refusing to overwrite", error)
            self.assertEqual("preserve me\n", output.read_text(encoding="utf-8"))

    def test_museum_output_refuses_dangling_symlink_and_atomic_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            dangling_output = temporary / "dangling-output"
            dangling_output.symlink_to(temporary / "missing-target", target_is_directory=True)

            result, _, error = run_cli(
                [
                    "intake-museum",
                    str(dangling_output),
                    "--met-object",
                    "324062",
                ]
            )

            self.assertEqual(1, result)
            self.assertIn("refusing to overwrite", error)
            self.assertTrue(dangling_output.is_symlink())

            staging = temporary / "staging"
            destination = temporary / "destination"
            staging.mkdir()
            destination.mkdir()
            (staging / "new.txt").write_text("new\n", encoding="utf-8")
            (destination / "keep.txt").write_text("keep\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                cli_module._rename_directory_no_replace(staging, destination)

            self.assertEqual("new\n", (staging / "new.txt").read_text(encoding="utf-8"))
            self.assertEqual("keep\n", (destination / "keep.txt").read_text(encoding="utf-8"))

    @unittest.skipIf(os.name == "nt", "directory fsync is not used on Windows")
    def test_directory_fsync_failure_is_not_silenced(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch(
                "indusbench.cli.os.fsync",
                side_effect=OSError(errno.ENOTSUP, "directory fsync unavailable"),
            ),
            self.assertRaises(OSError) as raised,
        ):
            cli_module._fsync_directory(Path(temporary_directory))
        self.assertEqual(errno.ENOTSUP, raised.exception.errno)

    @unittest.skipIf(os.name == "nt", "this injection targets the POSIX dirfd path")
    def test_post_rename_stat_failure_reports_committed_unknown_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "staged.json"
            destination = temporary / "published.json"
            source.write_bytes(b'{"valid":true}\n')
            real_stat = cli_module.os.stat

            def fail_published_stat(
                path: Any,
                *args: Any,
                **kwargs: Any,
            ) -> os.stat_result:
                if (
                    path == destination.name
                    and kwargs.get("dir_fd") is not None
                    and kwargs.get("follow_symlinks") is False
                ):
                    raise OSError(errno.EIO, "synthetic post-rename stat failure")
                return real_stat(path, *args, **kwargs)

            with (
                patch("indusbench.cli.os.stat", side_effect=fail_published_stat),
                self.assertRaises(cli_module._CommittedDurabilityUnknown) as raised,
            ):
                cli_module._rename_regular_file_no_replace(source, destination)

            self.assertFalse(raised.exception.content_verified)
            self.assertTrue(destination.is_file())
            self.assertFalse(source.exists())

    @unittest.skipIf(os.name == "nt", "this injection targets POSIX descriptors")
    def test_post_rename_close_failure_reports_committed_unknown_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "staged.json"
            destination = temporary / "published.json"
            source.write_bytes(b'{"valid":true}\n')
            real_close = cli_module.os.close
            close_count = 0

            def close_then_fail_once(descriptor: int) -> None:
                nonlocal close_count
                real_close(descriptor)
                close_count += 1
                if close_count == 1:
                    raise OSError(errno.EIO, "synthetic post-rename close failure")

            with (
                patch("indusbench.cli.os.close", side_effect=close_then_fail_once),
                self.assertRaises(cli_module._CommittedDurabilityUnknown) as raised,
            ):
                cli_module._rename_regular_file_no_replace(source, destination)

            self.assertTrue(raised.exception.content_verified)
            self.assertTrue(destination.is_file())
            self.assertFalse(source.exists())

    def test_research_filters_machine_readable_evidence_ledger(self) -> None:
        result, output, error = run_cli(
            [
                "research",
                "--tier",
                "A",
                "--type",
                "policy_or_prize",
                "--status",
                "verified",
            ]
        )

        self.assertEqual(0, result, error)
        payload = json.loads(output)
        self.assertEqual(1, payload["entry_count"])
        self.assertEqual("policy-tamil-nadu-prize-2025", payload["entries"][0]["entry_id"])
        self.assertEqual(["A"], payload["filters"]["evidence_tiers"])
        self.assertEqual(["policy_or_prize"], payload["filters"]["entity_types"])

        due_result, due_output, due_error = run_cli(["research", "--review-due", "2026-08-26"])
        self.assertEqual(0, due_result, due_error)
        due_payload = json.loads(due_output)
        self.assertGreater(due_payload["entry_count"], 0)
        self.assertTrue(
            all(
                entry["dates"]["next_review_on"] <= "2026-08-26" for entry in due_payload["entries"]
            )
        )

    def test_museum_candidates_filters_fail_closed_rights_ledger(self) -> None:
        result, output, error = run_cli(
            [
                "museum-candidates",
                "--automation-class",
                "metadata_only",
                "--with-verified-candidates",
            ]
        )
        self.assertEqual(0, result, error)
        payload = json.loads(output)
        self.assertEqual(2, payload["institution_count"])
        self.assertEqual(
            {"penn-museum", "smithsonian-institution"},
            {institution["institution_id"] for institution in payload["institutions"]},
        )
        self.assertTrue(
            all(
                not institution["media_rights"]["redistribution"]
                and not institution["media_rights"]["automated_retrieval"]
                for institution in payload["institutions"]
            )
        )

    def test_treewidth_audit_reports_boundary_policy_and_null_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            corpus = temporary / "corpus.jsonl"
            output = temporary / "treewidth.json"
            write_jsonl(corpus, distinct_records())

            result, stdout, error = run_cli(
                [
                    "treewidth-audit",
                    str(corpus),
                    "--runs",
                    "3",
                    "--seed",
                    "7",
                    "--sequence-unit",
                    "canonical_line",
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(0, result, error)
            payload = json.loads(stdout)
            self.assertEqual("treewidth_null_audit", payload["analysis"])
            self.assertEqual("canonical_line", payload["sequence_policy"]["sequence_unit"])
            self.assertEqual(3, payload["runs"])
            self.assertEqual(6, payload["input"]["artifact_count"])
            self.assertRegex(payload["input"]["corpus_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(output.is_file())
            self.assertEqual(payload, json.loads(output.read_text(encoding="utf-8")))

    def test_museum_intake_writes_atomic_untranscribed_bundle(self) -> None:
        payload = {
            "objectID": 324062,
            "isPublicDomain": True,
            "accessionNumber": "49.40.1",
            "title": "Synthetic Met response",
            "objectURL": "https://www.metmuseum.org/art/collection/search/324062",
            "primaryImage": "https://images.metmuseum.org/example/primary.jpg",
            "additionalImages": [],
        }
        raw_bytes = json.dumps(payload, separators=(",", ":")).encode()
        document = JsonDocument(
            url=("https://collectionapi.metmuseum.org/public/collection/v1/objects/324062"),
            status=200,
            content_type="application/json",
            headers={"content-type": "application/json"},
            raw_bytes=raw_bytes,
            value=payload,
        )
        record = build_met_intake(
            document,
            expected_object_id=324062,
            retrieved_at="2026-07-26T08:00:00Z",
        )
        image_bytes = b"\xff\xd8\xff\xe0synthetic-private-review-image"

        def download_synthetic_media(
            intake_record: dict,
            *,
            root: Path,
            downloaded_at: str,
            **_: object,
        ) -> dict:
            updated = copy.deepcopy(intake_record)
            relative_path = "images/museum_met_324062/met_324062_primary_original.jpg"
            destination = root / relative_path
            destination.parent.mkdir(parents=True)
            destination.write_bytes(image_bytes)
            updated["media"][0]["download"] = {
                "status": "downloaded",
                "sha256": "sha256:" + hashlib.sha256(image_bytes).hexdigest(),
                "bytes": len(image_bytes),
                "content_type": "image/jpeg",
                "local_relative_path": relative_path,
                "downloaded_at": downloaded_at,
            }
            return updated

        policy_documents = [
            PolicyDocument(
                evidence_id=specification.evidence_id,
                source_id=specification.source_id,
                url=specification.uri,
                status=200,
                content_type=next(iter(specification.allowed_content_types)),
                raw_relative_path=specification.raw_relative_path,
                raw_bytes=b" ".join(specification.required_markers),
            )
            for specification in POLICY_EVIDENCE_SPECS
            if specification.source_id == MET_SOURCE_ID
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "museum-bundle"
            with (
                patch(
                    "indusbench.cli.fetch_met_intake",
                    return_value=(record, document),
                ),
                patch(
                    "indusbench.cli.fetch_policy_documents",
                    return_value=policy_documents,
                ),
                patch(
                    "indusbench.cli.download_intake_media",
                    side_effect=download_synthetic_media,
                ),
                patch(
                    "indusbench.cli._utc_timestamp",
                    return_value="2026-07-26T08:00:00Z",
                ),
            ):
                result, stdout, error = run_cli(
                    [
                        "intake-museum",
                        str(output_dir),
                        "--met-object",
                        "324062",
                        "--download-media",
                    ]
                )

            self.assertEqual(0, result, error)
            summary = json.loads(stdout)
            self.assertTrue(summary["written"])
            self.assertEqual(1, summary["record_count"])
            self.assertEqual(1, summary["media_count"])
            self.assertEqual(1, summary["downloaded_media_count"])
            self.assertEqual(len(image_bytes), summary["downloaded_media_bytes"])
            self.assertTrue((output_dir / "intake.jsonl").is_file())
            self.assertTrue((output_dir / "bundle-manifest.json").is_file())
            self.assertTrue((output_dir / "raw/met/324062/api-response.json").is_file())

            verify_result, verify_stdout, verify_error = run_cli(
                ["verify-museum-intake", str(output_dir)]
            )
            self.assertEqual(0, verify_result, verify_error)
            self.assertTrue(json.loads(verify_stdout)["valid"])

            review_dir = Path(temporary_directory) / "private-review"
            with patch(
                "indusbench.cli._utc_timestamp",
                return_value="2026-07-26T09:00:00Z",
            ):
                review_result, review_stdout, review_error = run_cli(
                    [
                        "prepare-museum-review",
                        str(output_dir),
                        str(review_dir),
                    ]
                )
            self.assertEqual(0, review_result, review_error)
            review_summary = json.loads(review_stdout)["review_packet"]
            self.assertEqual(1, review_summary["subject_count"])
            self.assertEqual(1, review_summary["view_group_count"])
            self.assertEqual(1, review_summary["evidence_image_count"])
            self.assertEqual(len(image_bytes), review_summary["evidence_bytes"])
            self.assertFalse(review_summary["source_externally_anchored"])
            self.assertEqual(
                "blocked_missing_external_source_anchor",
                review_summary["publication_gate"],
            )
            self.assertEqual(
                "passed",
                review_summary["catalog_blind_text_leak_check"],
            )

            reviewer_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (
                    review_dir / "reviewer/subjects.jsonl",
                    review_dir / "reviewer/manifest.json",
                    review_dir / "reviewer/REVIEW_INSTRUCTIONS.md",
                )
            )
            for forbidden in (
                "Metropolitan Museum of Art",
                "49.40.1",
                "museum:met:324062",
                "https://www.metmuseum.org/",
                "met:324062:primary:original",
            ):
                self.assertNotIn(forbidden, reviewer_text)
            custody = json.loads(
                (review_dir / "custody/identity-map.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                "museum:met:324062",
                custody["subjects"][0]["intake_id"],
            )
            evidence_entry = json.loads(
                (review_dir / "reviewer/manifest.json").read_text(encoding="utf-8")
            )["evidence"][0]
            copied_image = review_dir / "reviewer" / evidence_entry["relative_path"]
            source_image = output_dir / "images/museum_met_324062/met_324062_primary_original.jpg"
            self.assertEqual(image_bytes, copied_image.read_bytes())
            self.assertFalse(source_image.samefile(copied_image))
            self.assertEqual(1, source_image.stat().st_nlink)
            self.assertEqual(1, copied_image.stat().st_nlink)

            packet_verify_result, packet_verify_stdout, packet_verify_error = run_cli(
                ["verify-museum-review", str(review_dir)]
            )
            self.assertEqual(0, packet_verify_result, packet_verify_error)
            packet_verify = json.loads(packet_verify_stdout)
            self.assertTrue(packet_verify["valid"])
            self.assertEqual([], packet_verify["mismatches"])

            subject = json.loads(
                (review_dir / "reviewer/subjects.jsonl").read_text(encoding="utf-8").splitlines()[0]
            )
            draft = valid_review(subject)
            reviewer_manifest_bytes = (review_dir / "reviewer/manifest.json").read_bytes()
            draft["source_commitment"]["reviewer_manifest_sha256"] = (
                "sha256:" + hashlib.sha256(reviewer_manifest_bytes).hexdigest()
            )
            draft_path = Path(temporary_directory) / "review-draft.json"
            write_json(draft_path, draft)
            ledger_dir = Path(temporary_directory) / "private-review-ledger"

            invalid_draft = copy.deepcopy(draft)
            invalid_draft["subject_id"] = "subject:unknown"
            invalid_draft_path = Path(temporary_directory) / "invalid-review-draft.json"
            write_json(invalid_draft_path, invalid_draft)
            invalid_ledger_dir = Path(temporary_directory) / "invalid-review-ledger"
            invalid_seal_result, invalid_seal_stdout, _ = run_cli(
                [
                    "seal-museum-review",
                    str(review_dir),
                    str(invalid_ledger_dir),
                    str(invalid_draft_path),
                ]
            )
            self.assertEqual(2, invalid_seal_result)
            self.assertFalse(json.loads(invalid_seal_stdout)["sealed"])
            self.assertFalse(invalid_ledger_dir.exists())

            durability_ledger_dir = Path(temporary_directory) / "durability-review-ledger"
            real_directory_rename = cli_module._rename_directory_no_replace

            def rename_then_report_io_failure(source: Path, destination: Path) -> None:
                real_directory_rename(source, destination)
                raise OSError(errno.EIO, "synthetic post-rename durability failure")

            with patch(
                "indusbench.cli._rename_directory_no_replace",
                side_effect=rename_then_report_io_failure,
            ):
                durability_result, durability_stdout, durability_error = run_cli(
                    [
                        "seal-museum-review",
                        str(review_dir),
                        str(durability_ledger_dir),
                        str(draft_path),
                    ]
                )
            self.assertEqual(1, durability_result)
            self.assertEqual("", durability_error)
            durability_payload = json.loads(durability_stdout)
            self.assertTrue(durability_payload["sealed"])
            self.assertEqual(
                "committed_durability_unknown",
                durability_payload["postcondition"],
            )
            self.assertTrue(
                (durability_ledger_dir / Path(durability_payload["relative_path"])).is_file()
            )

            with patch(
                "indusbench.cli._utc_timestamp",
                return_value="2026-07-26T09:30:00Z",
            ):
                seal_result, seal_stdout, seal_error = run_cli(
                    [
                        "seal-museum-review",
                        str(review_dir),
                        str(ledger_dir),
                        str(draft_path),
                        "--expected-packet-manifest-sha256",
                        packet_verify["packet_manifest_sha256"],
                    ]
                )
            self.assertEqual(0, seal_result, seal_error)
            seal_payload = json.loads(seal_stdout)
            self.assertTrue(seal_payload["sealed"])
            self.assertFalse(seal_payload["publication_or_training_release_allowed"])
            sealed_path = ledger_dir / seal_payload["relative_path"]
            self.assertTrue(sealed_path.is_file())
            self.assertEqual(0o600, stat.S_IMODE(sealed_path.stat().st_mode))

            ledger_result, ledger_stdout, ledger_error = run_cli(
                [
                    "verify-museum-review-ledger",
                    str(review_dir),
                    str(ledger_dir),
                    "--expected-packet-manifest-sha256",
                    packet_verify["packet_manifest_sha256"],
                ]
            )
            self.assertEqual(0, ledger_result, ledger_error)
            ledger_payload = json.loads(ledger_stdout)
            self.assertTrue(ledger_payload["valid"])
            self.assertEqual(1, ledger_payload["sealed_review_count"])
            self.assertEqual(1, ledger_payload["unresolved_subjects"])
            self.assertFalse(ledger_payload["publication_or_training_release_allowed"])
            self.assertIn(
                "rights_review_not_approved",
                ledger_payload["publication_blocks"],
            )
            self.assertIn(
                "cultural_heritage_review_not_approved",
                ledger_payload["publication_blocks"],
            )

            second_draft = valid_review(subject)
            second_draft["review_id"] = "review:synthetic:two"
            second_draft["assignment_id"] = "assignment:synthetic:two"
            second_draft["actor"]["actor_id"] = "reviewer:pseudonymous-two"
            second_draft["actor"]["reviewed_at"] = "2026-07-26T10:05:00Z"
            second_draft["source_commitment"]["reviewer_manifest_sha256"] = draft[
                "source_commitment"
            ]["reviewer_manifest_sha256"]
            second_draft_path = Path(temporary_directory) / "review-draft-two.json"
            write_json(second_draft_path, second_draft)
            second_seal_result, second_seal_stdout, second_seal_error = run_cli(
                [
                    "seal-museum-review",
                    str(review_dir),
                    str(ledger_dir),
                    str(second_draft_path),
                ]
            )
            self.assertEqual(0, second_seal_result, second_seal_error)
            self.assertTrue(json.loads(second_seal_stdout)["sealed"])

            max_count_draft = copy.deepcopy(second_draft)
            max_count_draft["review_id"] = "review:synthetic:three"
            max_count_draft["assignment_id"] = "assignment:synthetic:three"
            max_count_draft["actor"]["actor_id"] = "reviewer:pseudonymous-three"
            max_count_draft["actor"]["reviewed_at"] = "2026-07-26T10:10:00Z"
            max_count_draft_path = Path(temporary_directory) / "review-draft-three.json"
            write_json(max_count_draft_path, max_count_draft)
            max_count_result, max_count_stdout, _ = run_cli(
                [
                    "seal-museum-review",
                    str(review_dir),
                    str(ledger_dir),
                    str(max_count_draft_path),
                    "--max-review-count",
                    "2",
                ]
            )
            self.assertEqual(2, max_count_result)
            self.assertFalse(json.loads(max_count_stdout)["sealed"])

            two_review_result, two_review_stdout, two_review_error = run_cli(
                [
                    "verify-museum-review-ledger",
                    str(review_dir),
                    str(ledger_dir),
                ]
            )
            self.assertEqual(0, two_review_result, two_review_error)
            self.assertEqual(
                2,
                json.loads(two_review_stdout)["sealed_review_count"],
            )

            ledger_manifest_path = ledger_dir / "ledger-manifest.json"
            ledger_manifest_bytes = ledger_manifest_path.read_bytes()
            ledger_manifest_path.write_bytes(b"{")
            malformed_result, malformed_stdout, malformed_error = run_cli(
                [
                    "verify-museum-review-ledger",
                    str(review_dir),
                    str(ledger_dir),
                ]
            )
            self.assertEqual(2, malformed_result, malformed_error)
            self.assertFalse(json.loads(malformed_stdout)["valid"])
            ledger_manifest_path.write_bytes(ledger_manifest_bytes)
            os.chmod(ledger_manifest_path, 0o600)

            noncanonical_bytes = sealed_path.read_bytes() + b"\n"
            noncanonical_digest = hashlib.sha256(noncanonical_bytes).hexdigest()
            noncanonical_path = ledger_dir / "submissions" / f"sha256-{noncanonical_digest}.json"
            noncanonical_path.write_bytes(noncanonical_bytes)
            os.chmod(noncanonical_path, 0o600)
            noncanonical_result, noncanonical_stdout, _ = run_cli(
                [
                    "verify-museum-review-ledger",
                    str(review_dir),
                    str(ledger_dir),
                ]
            )
            self.assertEqual(2, noncanonical_result)
            self.assertTrue(
                any(
                    "canonical serialization" in mismatch
                    for mismatch in json.loads(noncanonical_stdout)["mismatches"]
                )
            )
            noncanonical_path.unlink()

            os.chmod(sealed_path, 0o640)
            ledger_permission_result, ledger_permission_stdout, _ = run_cli(
                [
                    "verify-museum-review-ledger",
                    str(review_dir),
                    str(ledger_dir),
                ]
            )
            self.assertEqual(2, ledger_permission_result)
            self.assertTrue(
                any(
                    "accessible to group/other" in mismatch
                    for mismatch in json.loads(ledger_permission_stdout)["mismatches"]
                )
            )
            os.chmod(sealed_path, 0o600)

            if sys.platform == "darwin":
                subprocess.run(
                    ["chmod", "+a", "everyone allow read", str(sealed_path)],
                    check=True,
                )
                acl_result, acl_stdout, acl_error = run_cli(
                    [
                        "verify-museum-review-ledger",
                        str(review_dir),
                        str(ledger_dir),
                    ]
                )
                self.assertEqual(2, acl_result, acl_error)
                self.assertTrue(
                    any(
                        "extended ACL" in mismatch
                        for mismatch in json.loads(acl_stdout)["mismatches"]
                    )
                )
                subprocess.run(
                    ["chmod", "-a#", "0", str(sealed_path)],
                    check=True,
                )

            repeated_seal_result, repeated_seal_stdout, repeated_seal_error = run_cli(
                [
                    "seal-museum-review",
                    str(review_dir),
                    str(ledger_dir),
                    str(draft_path),
                ]
            )
            self.assertEqual(0, repeated_seal_result)
            self.assertEqual("", repeated_seal_error)
            repeated_seal_payload = json.loads(repeated_seal_stdout)
            self.assertTrue(repeated_seal_payload["sealed"])
            self.assertTrue(repeated_seal_payload["valid"])
            self.assertTrue(repeated_seal_payload["already_sealed"])
            self.assertEqual(
                "already_sealed_and_verified",
                repeated_seal_payload["postcondition"],
            )

            unexpected_review_file = review_dir / "unexpected.txt"
            unexpected_review_file.write_text("not declared\n", encoding="utf-8")
            unexpected_review_result, unexpected_review_stdout, _ = run_cli(
                ["verify-museum-review", str(review_dir)]
            )
            self.assertEqual(2, unexpected_review_result)
            self.assertIn(
                "unexpected review packet file: unexpected.txt",
                json.loads(unexpected_review_stdout)["mismatches"],
            )
            unexpected_review_file.unlink()

            tampered_image = bytearray(image_bytes)
            tampered_image[-1] ^= 1
            copied_image.write_bytes(tampered_image)
            tampered_review_result, tampered_review_stdout, _ = run_cli(
                ["verify-museum-review", str(review_dir)]
            )
            self.assertEqual(2, tampered_review_result)
            self.assertIn(
                f"{evidence_entry['image_id']}: evidence hash mismatch",
                json.loads(tampered_review_stdout)["mismatches"],
            )
            copied_image.write_bytes(image_bytes)
            os.chmod(copied_image, 0o600)

            os.chmod(copied_image, 0o640)
            permission_result, permission_stdout, _ = run_cli(
                ["verify-museum-review", str(review_dir)]
            )
            self.assertEqual(2, permission_result)
            self.assertTrue(
                any(
                    "accessible to group/other" in mismatch
                    for mismatch in json.loads(permission_stdout)["mismatches"]
                )
            )
            os.chmod(copied_image, 0o600)

            repeated_result, _, repeated_error = run_cli(
                [
                    "prepare-museum-review",
                    str(output_dir),
                    str(review_dir),
                ]
            )
            self.assertEqual(1, repeated_result)
            self.assertIn("refusing to overwrite", repeated_error)

            nested_result, _, nested_error = run_cli(
                [
                    "prepare-museum-review",
                    str(output_dir),
                    str(output_dir / "nested-review"),
                ]
            )
            self.assertEqual(1, nested_result)
            self.assertIn("must be disjoint", nested_error)

            manifest_reads: list[Path] = []
            original_read_regular_bytes = cli_module._read_regular_bytes

            def observe_index_reads(path: Path, *, max_bytes: int) -> bytes:
                if path.name == "bundle-manifest.json":
                    manifest_reads.append(path)
                return original_read_regular_bytes(path, max_bytes=max_bytes)

            with patch(
                "indusbench.cli._read_regular_bytes",
                side_effect=observe_index_reads,
            ):
                anchored_result, anchored_stdout, anchored_error = run_cli(
                    ["verify-museum-intake", str(output_dir)]
                )
            self.assertEqual(0, anchored_result, anchored_error)
            self.assertTrue(json.loads(anchored_stdout)["self_consistent"])
            self.assertEqual([output_dir / "bundle-manifest.json"], manifest_reads)

            unexpected = output_dir / "unexpected.txt"
            unexpected.write_text("not part of the bundle\n", encoding="utf-8")
            unexpected_result, unexpected_stdout, unexpected_error = run_cli(
                ["verify-museum-intake", str(output_dir)]
            )
            self.assertEqual(2, unexpected_result, unexpected_error)
            self.assertIn(
                "unexpected bundle file: unexpected.txt",
                json.loads(unexpected_stdout)["manifest_mismatches"],
            )
            unexpected.unlink()

            unexpected_directory = output_dir / "unexpected-empty-directory"
            unexpected_directory.mkdir()
            directory_result, directory_stdout, directory_error = run_cli(
                ["verify-museum-intake", str(output_dir)]
            )
            self.assertEqual(2, directory_result, directory_error)
            self.assertIn(
                "unexpected bundle directory: unexpected-empty-directory",
                json.loads(directory_stdout)["manifest_mismatches"],
            )
            unexpected_directory.rmdir()

            deepest = output_dir
            for depth in range(cli_module.MUSEUM_MAX_BUNDLE_DEPTH + 1):
                deepest = deepest / f"depth-{depth}"
                deepest.mkdir()
            depth_result, _, depth_error = run_cli(["verify-museum-intake", str(output_dir)])
            self.assertEqual(1, depth_result)
            self.assertIn("directory depth exceeds limit", depth_error)
            shutil.rmtree(output_dir / "depth-0")

            fifo_path = output_dir / "blocking-fifo"
            os.mkfifo(fifo_path)
            fifo_result, _, fifo_error = run_cli(["verify-museum-intake", str(output_dir)])
            self.assertEqual(1, fifo_result)
            self.assertIn("non-regular file", fifo_error)
            fifo_path.unlink()

            manifest_path = output_dir / "bundle-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered_manifest = dict(manifest)
            tampered_manifest["bundle_version"] = "999.0"
            tampered_manifest["created_at"] = "1900-01-01T00:00:00Z"
            tampered_manifest["scientific_scope"] = "claims a completed translation"
            tampered_manifest["unknown"] = True
            manifest_path.write_text(
                json.dumps(tampered_manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            tampered_result, tampered_stdout, tampered_error = run_cli(
                ["verify-museum-intake", str(output_dir)]
            )
            self.assertEqual(2, tampered_result, tampered_error)
            tampered_mismatches = json.loads(tampered_stdout)["manifest_mismatches"]
            self.assertIn("manifest contains unknown field: unknown", tampered_mismatches)
            self.assertIn(
                "manifest scientific_scope does not match the intake-only boundary",
                tampered_mismatches,
            )

            manifest["records"].append(dict(manifest["records"][0]))
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            duplicate_result, duplicate_stdout, duplicate_error = run_cli(
                ["verify-museum-intake", str(output_dir)]
            )
            self.assertEqual(2, duplicate_result, duplicate_error)
            self.assertIn(
                "manifest.records contains duplicate intake_id values",
                json.loads(duplicate_stdout)["manifest_mismatches"],
            )

            second_result, _, second_error = run_cli(
                [
                    "intake-museum",
                    str(output_dir),
                    "--met-object",
                    "324062",
                ]
            )
            self.assertEqual(1, second_result)
            self.assertIn("refusing to overwrite", second_error)


if __name__ == "__main__":
    unittest.main()
