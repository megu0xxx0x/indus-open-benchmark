"""Standard-library checks for the normative schemas and synthetic fixture."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any

from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
FIXTURE = ROOT / "examples" / "synthetic_corpus.jsonl"
SOURCE_REGISTRY = ROOT / "registry" / "sources.json"
EVALUATOR_CONFIG = ROOT / "benchmark" / "development-evaluator.json"
SCHEMA_FILES = (
    "source-registry.schema.json",
    "artifact.schema.json",
    "benchmark-lock.schema.json",
    "evaluator-config.schema.json",
    "hypothesis.schema.json",
    "kp1982-batch0-source.schema.json",
    "kp1982-layout-seed.schema.json",
    "kp1982-layout-proposal.schema.json",
    "research-entry.schema.json",
    "museum-intake.schema.json",
    "museum-review-subject.schema.json",
    "museum-review.schema.json",
    "museum-review-ledger.schema.json",
    "penn-metadata-snapshot.schema.json",
    "private-corpus-policy.schema.json",
    "private-corpus-readiness.schema.json",
    "private-review-bundle.schema.json",
    "private-structural-quarantine.schema.json",
    "quarantine-manifest.schema.json",
    "sign-inventory.schema.json",
    "smithsonian-metadata-record.schema.json",
    "split-manifest.schema.json",
    "submission-commitment.schema.json",
    "transcription-review.schema.json",
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
EXTENSION_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]*:[A-Za-z0-9_.:/-]+$")


def walk_json(value: Any):
    """Yield all values in a decoded JSON tree."""
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


class SchemaContractTests(unittest.TestCase):
    maxDiff = None

    def test_schemas_are_json_and_use_draft_2020_12(self) -> None:
        for filename in SCHEMA_FILES:
            with self.subTest(filename=filename):
                schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
                self.assertEqual(
                    schema["$schema"],
                    "https://json-schema.org/draft/2020-12/schema",
                )
                self.assertFalse(schema["additionalProperties"])
                expected_version = (
                    "0.2.0"
                    if filename
                    in {
                        "museum-review.schema.json",
                        "private-corpus-policy.schema.json",
                        "private-corpus-readiness.schema.json",
                        "smithsonian-metadata-record.schema.json",
                        "split-manifest.schema.json",
                    }
                    else "0.1.0"
                )
                self.assertEqual(
                    schema["properties"]["schema_version"]["const"],
                    expected_version,
                )

    def test_local_schema_refs_resolve(self) -> None:
        for filename in SCHEMA_FILES:
            with self.subTest(filename=filename):
                schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
                definitions = schema.get("$defs", {})
                local_refs = {
                    value["$ref"]
                    for value in walk_json(schema)
                    if isinstance(value, dict)
                    and isinstance(value.get("$ref"), str)
                    and value["$ref"].startswith("#/$defs/")
                }
                missing = {
                    ref for ref in local_refs if ref.removeprefix("#/$defs/") not in definitions
                }
                self.assertEqual(missing, set())

    def test_synthetic_jsonl_obeys_cross_record_invariants(self) -> None:
        records = [
            json.loads(line)
            for line in FIXTURE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertGreaterEqual(len(records), 2)
        self.assertEqual(len({record["artifact_id"] for record in records}), len(records))

        for record in records:
            self.assertEqual(record["schema_version"], "0.1.0")
            source_record_ids = {
                source_record["source_record_id"] for source_record in record["source_records"]
            }
            self.assertEqual(len(source_record_ids), len(record["source_records"]))

            image_ids = {image["image_id"] for image in record["images"]}
            self.assertEqual(len(image_ids), len(record["images"]))
            for image in record["images"]:
                self.assertRegex(image["image_hash"], SHA256_RE)

            for side in record["sides"]:
                self.assertLessEqual(set(side["image_ids"]), image_ids)
                for line in side["lines"]:
                    tokens = line["tokens"]
                    self.assertEqual(
                        sorted(token["visual_index"] for token in tokens),
                        list(range(len(tokens))),
                    )
                    reading_indexes = [token["reading_index"] for token in tokens]
                    if line["reading_direction"] == "unknown":
                        self.assertTrue(all(index is None for index in reading_indexes))
                    elif all(index is not None for index in reading_indexes):
                        self.assertEqual(sorted(reading_indexes), list(range(len(tokens))))

                    for token in tokens:
                        self.assertLessEqual(set(token["source_record_ids"]), source_record_ids)
                        self.assertGreaterEqual(token["confidence"], 0)
                        self.assertLessEqual(token["confidence"], 1)
                        geometry = token["geometry"]
                        if geometry is not None:
                            self.assertIn(geometry["image_id"], image_ids)
            self.assertTrue(
                all(EXTENSION_KEY_RE.fullmatch(key) for key in record.get("extensions", {}))
            )

    def test_checked_in_source_registry_ids_resolve(self) -> None:
        registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["schema_version"], "0.1.0")
        source_ids = {source["source_id"] for source in registry["sources"]}
        self.assertEqual(len(source_ids), len(registry["sources"]))
        upstream_ids = {
            upstream_id
            for source in registry["sources"]
            for upstream_id in source["provenance"]["upstream_source_ids"]
        }
        self.assertLessEqual(upstream_ids, source_ids)

    def test_checked_in_development_evaluator_is_closed_and_nonblind(self) -> None:
        config = json.loads(EVALUATOR_CONFIG.read_text(encoding="utf-8"))
        issues = validate_schema_instance(
            config,
            SCHEMA_DIR / "evaluator-config.schema.json",
        )
        self.assertEqual([], issues)
        self.assertEqual("public_development", config["claim_class"])
        self.assertFalse(config["network_access_required"])

    def test_fixture_keeps_hypotheses_out_of_observations(self) -> None:
        forbidden = {
            "decipherment",
            "gloss",
            "language_assignment",
            "phonetic_value",
            "translation",
        }
        for line in FIXTURE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            artifact = json.loads(line)
            self.assertTrue(forbidden.isdisjoint(artifact))
            for side in artifact["sides"]:
                for inscription_line in side["lines"]:
                    for token in inscription_line["tokens"]:
                        self.assertTrue(forbidden.isdisjoint(token))


if __name__ == "__main__":
    unittest.main()
