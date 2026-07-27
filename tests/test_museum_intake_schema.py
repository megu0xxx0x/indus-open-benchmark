"""Contracts for rights-cleared, untranscribed museum API staging records."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import unittest
from pathlib import Path
from typing import Any

from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "museum-intake.schema.json"
FIXTURE_PATH = ROOT / "examples" / "synthetic_museum_intake.jsonl"
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
FORBIDDEN_INTERPRETIVE_KEYS = {
    "decipherment",
    "front",
    "gloss",
    "language_assignment",
    "phonetic_value",
    "reading_direction",
    "reverse",
    "sign_id",
    "tokens",
    "transcription",
    "translation",
}


def load_fixture() -> list[dict[str, Any]]:
    """Load the checked-in JSONL staging examples."""
    return [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def walk_json(value: Any):
    """Yield every value in a decoded JSON tree."""
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


class MuseumIntakeContractTests(unittest.TestCase):
    maxDiff = None

    def test_schema_is_closed_draft_2020_12(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["schema_version"]["const"], "0.1.0")
        self.assertEqual(schema["properties"]["record_state"]["const"], "untranscribed")

    def test_fixture_is_fail_closed_and_uninterpreted(self) -> None:
        records = load_fixture()
        self.assertGreaterEqual(len(records), 2)
        self.assertEqual(len({record["intake_id"] for record in records}), len(records))

        for record in records:
            self.assertEqual(record["record_state"], "untranscribed")
            self.assertTrue(record["item_rights"]["item_level_verified"])
            self.assertTrue(record["item_rights"]["redistribution"])
            self.assertTrue(record["item_rights"]["derivatives"])
            self.assertTrue(record["item_rights"]["commercial_use"])
            self.assertEqual(record["catalog_crosswalk"]["status"], "unresolved")
            self.assertEqual(
                record["retrieval"]["response_sha256"],
                record["item_rights"]["evidence"]["api_response_sha256"],
            )
            self.assertRegex(record["retrieval"]["response_sha256"], SHA256_RE)

            media_ids = {media["media_id"] for media in record["media"]}
            self.assertEqual(len(media_ids), len(record["media"]))
            for media in record["media"]:
                self.assertEqual(media["physical_side"], "unknown")
                self.assertEqual(media["rights_basis"], "item_rights")
                self.assertGreaterEqual(media["provider_view_index"], 0)
                download = media["download"]
                if download["status"] == "downloaded":
                    self.assertRegex(download["sha256"], SHA256_RE)
                    self.assertGreater(download["bytes"], 0)
                    self.assertTrue(download["content_type"].startswith("image/"))
                    self.assertFalse(Path(download["local_relative_path"]).is_absolute())
                    if media["api_declared_bytes"] is not None:
                        self.assertNotEqual(
                            media["api_declared_bytes"],
                            download["bytes"],
                            "the fixture must exercise API/HTTP byte-count disagreement",
                        )
                else:
                    self.assertEqual(download["status"], "not_downloaded")
                    self.assertTrue(
                        all(
                            download[field] is None
                            for field in (
                                "sha256",
                                "bytes",
                                "content_type",
                                "local_relative_path",
                                "downloaded_at",
                            )
                        )
                    )

            for value in walk_json(record):
                if isinstance(value, dict):
                    self.assertTrue(FORBIDDEN_INTERPRETIVE_KEYS.isdisjoint(value))

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema optional extra is not installed")
    def test_fixture_matches_schema(self) -> None:
        for record in load_fixture():
            with self.subTest(intake_id=record["intake_id"]):
                self.assertEqual([], validate_schema_instance(record, SCHEMA_PATH))

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema optional extra is not installed")
    def test_rejects_unverified_or_nonredistributable_rights(self) -> None:
        template = load_fixture()[0]
        mutations = (
            ("unknown status", ("status", "unknown")),
            ("unverified item", ("item_level_verified", False)),
            ("redistribution disabled", ("redistribution", False)),
            ("derivatives disabled", ("derivatives", False)),
            ("commercial use unresolved", ("commercial_use", None)),
        )
        for label, (field, value) in mutations:
            with self.subTest(label=label):
                record = copy.deepcopy(template)
                record["item_rights"][field] = value
                self.assertNotEqual([], validate_schema_instance(record, SCHEMA_PATH))

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema optional extra is not installed")
    def test_rejects_incomplete_download_evidence(self) -> None:
        template = load_fixture()[0]

        record = copy.deepcopy(template)
        record["media"][0]["download"]["sha256"] = None
        self.assertNotEqual([], validate_schema_instance(record, SCHEMA_PATH))

        record = copy.deepcopy(template)
        record["media"][1]["download"]["local_relative_path"] = "staging/media/untracked.jpg"
        self.assertNotEqual([], validate_schema_instance(record, SCHEMA_PATH))

        record = copy.deepcopy(template)
        record["media"][0]["download"]["local_relative_path"] = "../outside.jpg"
        self.assertNotEqual([], validate_schema_instance(record, SCHEMA_PATH))

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema optional extra is not installed")
    def test_rejects_side_crosswalk_or_interpretation_guesses(self) -> None:
        template = load_fixture()[0]

        record = copy.deepcopy(template)
        record["media"][0]["physical_side"] = "front"
        self.assertNotEqual([], validate_schema_instance(record, SCHEMA_PATH))

        record = copy.deepcopy(template)
        record["catalog_crosswalk"]["status"] = "proposed"
        self.assertNotEqual([], validate_schema_instance(record, SCHEMA_PATH))

        record = copy.deepcopy(template)
        record["translation"] = "forbidden"
        self.assertNotEqual([], validate_schema_instance(record, SCHEMA_PATH))


if __name__ == "__main__":
    unittest.main()
