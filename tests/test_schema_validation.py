from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from indusbench.io import read_json, read_jsonl
from indusbench.schema_validation import (
    SchemaDependencyMissing,
    validate_artifact_rows,
    validate_schema_instance,
)
from tests.test_validation import valid_artifact

ROOT = Path(__file__).resolve().parents[1]
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


class SchemaValidationTests(unittest.TestCase):
    def test_missing_dependency_has_actionable_message(self) -> None:
        if HAS_JSONSCHEMA:
            self.skipTest("jsonschema is installed")
        with self.assertRaisesRegex(SchemaDependencyMissing, "reinstall the package"):
            validate_schema_instance({}, ROOT / "schemas/artifact.schema.json")

    @unittest.skipUnless(HAS_JSONSCHEMA, "declared jsonschema dependency is unavailable")
    def test_normative_fixture_matches_artifact_schema(self) -> None:
        rows = read_jsonl(ROOT / "examples/synthetic_corpus.jsonl")
        issues = validate_artifact_rows(rows, ROOT / "schemas/artifact.schema.json")
        self.assertEqual([], issues)

    @unittest.skipUnless(HAS_JSONSCHEMA, "declared jsonschema dependency is unavailable")
    def test_hypothesis_template_matches_hypothesis_schema(self) -> None:
        hypothesis = read_json(ROOT / "examples/hypothesis_template.json")
        issues = validate_schema_instance(
            hypothesis,
            ROOT / "schemas/hypothesis.schema.json",
        )
        self.assertEqual([], issues)

    @unittest.skipUnless(HAS_JSONSCHEMA, "declared jsonschema dependency is unavailable")
    def test_source_registry_matches_source_registry_schema(self) -> None:
        registry = read_json(ROOT / "registry/sources.json")
        issues = validate_schema_instance(
            registry,
            ROOT / "schemas/source-registry.schema.json",
        )
        self.assertEqual([], issues)

    @unittest.skipUnless(HAS_JSONSCHEMA, "declared jsonschema dependency is unavailable")
    def test_rejects_unregistered_observation_property(self) -> None:
        record = valid_artifact()
        record["translation"] = "forbidden"
        issues = validate_schema_instance(record, ROOT / "schemas/artifact.schema.json")
        self.assertIn("json_schema", {issue.code for issue in issues})


if __name__ == "__main__":
    unittest.main()
