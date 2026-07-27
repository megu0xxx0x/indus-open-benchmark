from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from indusbench.schema_validation import validate_schema_instance
from indusbench.split_manifest import (
    SplitManifestError,
    build_split_manifest,
    split_manifest_digest,
    validate_split_manifest,
)
from tests.test_validation import valid_artifact

ROOT = Path(__file__).resolve().parents[1]
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


class SplitManifestTests(unittest.TestCase):
    def test_builds_frozen_public_development_manifest(self) -> None:
        train_record = valid_artifact("SYN:A001")
        test_record = valid_artifact("SYN:A002")
        test_record["duplicate_family_id"] = "SYN:F002"
        test_record["images"][0]["image_hash"] = f"sha256:{'2' * 64}"
        test_record["sides"][0]["lines"][0]["tokens"][0]["sign_id"] = "SYN:003"

        manifest = build_split_manifest(
            [train_record],
            [test_record],
            seed=17,
            corpus_file_sha256=f"sha256:{'a' * 64}",
            corpus_file_bytes=1234,
            source_registry_sha256=f"sha256:{'b' * 64}",
            quarantine_manifest_sha256=f"sha256:{'c' * 64}",
            test_fraction=0.25,
            created_at="2026-07-26T00:00:00Z",
        )

        self.assertEqual("0.2.0", manifest["schema_version"])
        self.assertTrue(manifest["membership_frozen"])
        self.assertFalse(manifest["benchmark_locked"])
        self.assertEqual(2, len(manifest["partitions"]))
        self.assertEqual(1, manifest["partitions"][0]["artifact_count"])
        self.assertEqual([], manifest["leakage_policy"]["violations"])
        self.assertEqual(
            "public_development",
            manifest["evaluation_assurance"]["claim_class"],
        )
        self.assertFalse(manifest["evaluation_assurance"]["blind_claim_allowed"])
        self.assertFalse(
            manifest["evaluation_assurance"]["final_evaluation_eligible"],
        )
        self.assertIsNone(manifest["evaluation_assurance"]["test_partition_id"])
        self.assertEqual(
            manifest["manifest_sha256"],
            split_manifest_digest(manifest),
        )
        validate_split_manifest(manifest)

        if HAS_JSONSCHEMA:
            issues = validate_schema_instance(
                manifest,
                ROOT / "schemas/split-manifest.schema.json",
            )
            self.assertEqual([], issues)

    def test_materializes_holdout_generator_once_and_rejects_tampering(self) -> None:
        train_record = valid_artifact("SYN:A001")
        development_record = valid_artifact("SYN:A002")
        development_record["duplicate_family_id"] = "SYN:F002"
        development_record["images"][0]["image_hash"] = f"sha256:{'2' * 64}"
        development_record["sides"][0]["lines"][0]["tokens"][0]["sign_id"] = "SYN:003"

        manifest = build_split_manifest(
            [train_record],
            [development_record],
            seed=17,
            corpus_file_sha256=f"sha256:{'a' * 64}",
            corpus_file_bytes=1234,
            source_registry_sha256=f"sha256:{'b' * 64}",
            quarantine_manifest_sha256=f"sha256:{'c' * 64}",
            holdout_values=(value for value in ["site-b", "site-a", "site-a"]),
        )
        self.assertEqual(
            ["site-a", "site-b"],
            manifest["strategy"]["holdout_values"],
        )

        manifest["partitions"][0]["artifact_count"] = 999
        manifest["manifest_sha256"] = split_manifest_digest(manifest)
        with self.assertRaisesRegex(SplitManifestError, "artifact_count"):
            validate_split_manifest(manifest)

    def test_public_manifest_cannot_claim_blind_or_locked(self) -> None:
        train_record = valid_artifact("SYN:A001")
        development_record = valid_artifact("SYN:A002")
        development_record["duplicate_family_id"] = "SYN:F002"
        development_record["images"][0]["image_hash"] = f"sha256:{'2' * 64}"
        development_record["sides"][0]["lines"][0]["tokens"][0]["sign_id"] = "SYN:003"
        manifest = build_split_manifest(
            [train_record],
            [development_record],
            seed=17,
            corpus_file_sha256=f"sha256:{'a' * 64}",
            corpus_file_bytes=1234,
            source_registry_sha256=f"sha256:{'b' * 64}",
            quarantine_manifest_sha256=f"sha256:{'c' * 64}",
        )

        manifest["evaluation_assurance"]["blind_claim_allowed"] = True
        manifest["benchmark_locked"] = True
        manifest["manifest_sha256"] = split_manifest_digest(manifest)
        with self.assertRaisesRegex(SplitManifestError, "blind_claim_allowed"):
            validate_split_manifest(manifest)

    def test_refuses_exact_sequence_leakage(self) -> None:
        train_record = valid_artifact("SYN:A001")
        test_record = valid_artifact("SYN:A002")
        test_record["duplicate_family_id"] = "SYN:F002"
        test_record["images"][0]["image_hash"] = f"sha256:{'2' * 64}"

        with self.assertRaisesRegex(ValueError, "leaking split"):
            build_split_manifest(
                [train_record],
                [test_record],
                seed=17,
                corpus_file_sha256=f"sha256:{'a' * 64}",
                corpus_file_bytes=1234,
                source_registry_sha256=f"sha256:{'b' * 64}",
                quarantine_manifest_sha256=f"sha256:{'c' * 64}",
            )


if __name__ == "__main__":
    unittest.main()
