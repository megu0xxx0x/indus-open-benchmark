from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from typing import Any

from indusbench.benchmark_lock import (
    BenchmarkLockError,
    benchmark_definition_digest,
    build_benchmark_definition,
    validate_benchmark_definition,
    verify_benchmark_definition,
)
from indusbench.io import read_json, write_json, write_jsonl
from indusbench.quarantine import quarantine_manifest_digest, registry_digest
from indusbench.schema_validation import validate_schema_instance
from indusbench.split_manifest import build_split_manifest
from tests.test_validation import valid_artifact

ROOT = Path(__file__).resolve().parents[1]


def distinct_records(count: int = 4) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index in range(count):
        record = valid_artifact(f"SYN:LOCK-{index:03d}")
        record["duplicate_family_id"] = f"SYN:LOCK-F{index:03d}"
        record["images"][0]["image_id"] = f"SYN:LOCK-I{index:03d}"
        record["images"][0]["image_hash"] = f"sha256:{index + 100:064x}"
        record["sides"][0]["image_ids"] = [record["images"][0]["image_id"]]
        record["sides"][0]["lines"][0]["tokens"][0]["sign_id"] = f"SYN:{index + 100:03d}"
        records.append(record)
    return records


class BenchmarkLockTests(unittest.TestCase):
    def prepare_definition(
        self,
        temporary: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        corpus_path = temporary / "corpus.jsonl"
        split_dir = temporary / "split"
        split_dir.mkdir()
        records = distinct_records()
        train = records[:2]
        development = records[2:]
        write_jsonl(corpus_path, records)
        corpus_raw = corpus_path.read_bytes()

        sources = read_json(ROOT / "registry/sources.json")
        quarantine = read_json(ROOT / "registry/quarantine.json")
        split_manifest = build_split_manifest(
            train,
            development,
            seed=7,
            corpus_file_sha256="sha256:" + hashlib.sha256(corpus_raw).hexdigest(),
            corpus_file_bytes=len(corpus_raw),
            source_registry_sha256=registry_digest(sources),
            quarantine_manifest_sha256=quarantine_manifest_digest(quarantine),
            test_fraction=0.5,
            created_at="2026-07-27T00:00:00Z",
        )
        write_jsonl(split_dir / "train.jsonl", train)
        write_jsonl(split_dir / "development.jsonl", development)
        from indusbench.audit import audit_leakage

        write_json(
            split_dir / "leakage-audit.json",
            audit_leakage(train, development).as_dict(),
        )
        write_json(split_dir / "split-manifest.json", split_manifest)

        evaluator_config = temporary / "evaluator.json"
        write_json(
            evaluator_config,
            {
                "schema_version": "0.1.0",
                "config_id": "development-structural-v0.1",
                "claim_class": "public_development",
                "entrypoint": "indusbench.cli:main",
                "commands": ["audit", "baseline"],
                "metrics": ["heldout_log_loss"],
                "random_seeds": [7],
                "network_access_required": False,
                "notes": "Synthetic public-development evaluator fixture.",
            },
        )
        evaluator_file = temporary / "evaluator.py"
        evaluator_file.write_text("def score():\n    return 0\n", encoding="utf-8")
        environment_lock = temporary / "environment.lock"
        environment_lock.write_text("lock-version = 1\n", encoding="utf-8")

        paths = {
            "corpus_path": corpus_path,
            "split_dir": split_dir,
            "evaluator_config_path": evaluator_config,
            "evaluator_files": [evaluator_file],
            "environment_lock_path": environment_lock,
            "project_manifest_path": ROOT / "pyproject.toml",
            "artifact_schema_path": ROOT / "schemas/artifact.schema.json",
            "source_registry_path": ROOT / "registry/sources.json",
            "source_schema_path": ROOT / "schemas/source-registry.schema.json",
            "quarantine_registry_path": ROOT / "registry/quarantine.json",
            "quarantine_schema_path": ROOT / "schemas/quarantine-manifest.schema.json",
            "split_schema_path": ROOT / "schemas/split-manifest.schema.json",
            "evaluator_schema_path": ROOT / "schemas/evaluator-config.schema.json",
            "benchmark_lock_schema_path": ROOT / "schemas/benchmark-lock.schema.json",
        }
        lock = build_benchmark_definition(
            **paths,
            created_by="unit-test",
            created_at="2026-07-27T01:02:03Z",
        )
        return lock, paths

    def test_builds_exact_unanchored_development_definition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock, paths = self.prepare_definition(Path(temporary_directory))
            validate_benchmark_definition(lock)
            self.assertEqual(lock["definition_sha256"], benchmark_definition_digest(lock))
            self.assertFalse(lock["assurance"]["blind_claim_allowed"])
            self.assertFalse(lock["assurance"]["final_evaluation_eligible"])
            self.assertEqual("unanchored_local", lock["external_anchor"]["status"])
            self.assertEqual(
                [],
                validate_schema_instance(
                    lock,
                    ROOT / "schemas/benchmark-lock.schema.json",
                ),
            )

            local_report = verify_benchmark_definition(lock, **paths)
            self.assertTrue(local_report.valid)
            self.assertTrue(local_report.self_consistent)
            self.assertTrue(local_report.inputs_match)
            self.assertFalse(local_report.externally_anchored)
            self.assertEqual(17, local_report.checked_file_count)

            anchored_report = verify_benchmark_definition(
                lock,
                **paths,
                expected_definition_sha256=lock["definition_sha256"],
            )
            self.assertTrue(anchored_report.valid)
            self.assertTrue(anchored_report.expected_digest_match)
            self.assertFalse(anchored_report.externally_anchored)

    def test_external_anchor_mismatch_and_evaluator_tamper_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock, paths = self.prepare_definition(Path(temporary_directory))
            mismatch = verify_benchmark_definition(
                lock,
                **paths,
                expected_definition_sha256=f"sha256:{'0' * 64}",
            )
            self.assertFalse(mismatch.valid)
            self.assertFalse(mismatch.externally_anchored)

            evaluator_path = paths["evaluator_files"][0]
            evaluator_path.write_text("def score():\n    return 1\n", encoding="utf-8")
            tampered = verify_benchmark_definition(lock, **paths)
            self.assertFalse(tampered.valid)
            self.assertFalse(tampered.inputs_match)

    def test_semantically_equal_corpus_bytes_do_not_bypass_raw_commitment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock, paths = self.prepare_definition(Path(temporary_directory))
            corpus_path = paths["corpus_path"]
            corpus_path.write_bytes(corpus_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(BenchmarkLockError, "exact corpus"):
                verify_benchmark_definition(lock, **paths)

    def test_recomputed_local_digest_cannot_enable_blind_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock, paths = self.prepare_definition(Path(temporary_directory))
            tampered = copy.deepcopy(lock)
            tampered["assurance"]["blind_claim_allowed"] = True
            digest = benchmark_definition_digest(tampered)
            tampered["definition_sha256"] = digest
            tampered["definition_id"] = f"benchmark-definition:{digest}"

            report = verify_benchmark_definition(
                tampered,
                **paths,
                expected_definition_sha256=digest,
            )
            self.assertFalse(report.valid)
            self.assertFalse(report.self_consistent)
            self.assertTrue(report.inputs_match)
            self.assertFalse(report.externally_anchored)
            self.assertIn("cannot claim blind", " ".join(report.mismatches))

            scope_tamper = copy.deepcopy(lock)
            scope_tamper["scientific_scope"] = "blind final decipherment proven"
            scope_tamper["created_at"] = "not-a-date"
            scope_tamper["created_by"] = ""
            scope_digest = benchmark_definition_digest(scope_tamper)
            scope_tamper["definition_sha256"] = scope_digest
            scope_tamper["definition_id"] = f"benchmark-definition:{scope_digest}"
            with self.assertRaisesRegex(BenchmarkLockError, "scientific_scope"):
                validate_benchmark_definition(scope_tamper)

    def test_duplicate_json_key_in_evaluator_config_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            _, paths = self.prepare_definition(Path(temporary_directory))
            config = paths["evaluator_config_path"]
            config.write_text('{"metric":"a","metric":"b"}\n', encoding="utf-8")
            with self.assertRaisesRegex(BenchmarkLockError, "duplicate JSON key"):
                build_benchmark_definition(
                    **paths,
                    created_by="unit-test",
                    created_at="2026-07-27T01:02:03Z",
                )

    def test_remote_schema_reference_is_rejected_without_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            _, paths = self.prepare_definition(temporary)
            schema = read_json(ROOT / "schemas/evaluator-config.schema.json")
            schema["properties"]["notes"]["$ref"] = "https://example.invalid/remote.json"
            hostile_schema = temporary / "hostile-evaluator.schema.json"
            write_json(hostile_schema, schema)
            paths["evaluator_schema_path"] = hostile_schema
            with self.assertRaisesRegex(BenchmarkLockError, "non-local"):
                build_benchmark_definition(
                    **paths,
                    created_by="unit-test",
                    created_at="2026-07-27T01:02:03Z",
                )


if __name__ == "__main__":
    unittest.main()
