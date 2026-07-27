from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import unittest
from pathlib import Path
from typing import Any

from indusbench.penn_metadata import (
    BROAD_ARCHAEOLOGICAL_CANDIDATE,
    PENN_CSV_HEADER,
    PENN_CSV_URL,
    PHYSICAL_STATUS_UNKNOWN,
    PRIMARY_SCRIPT_CANDIDATE,
    REPLICA_OR_MODERN,
    PennMetadataError,
    parse_penn_csv_snapshot,
    validate_penn_metadata_semantics,
)

ROOT = Path(__file__).resolve().parents[1]
RETRIEVED_AT = "2026-07-27T04:05:06Z"


def penn_row(**changes: str) -> dict[str, str]:
    row: dict[str, str] = dict.fromkeys(PENN_CSV_HEADER, "")
    row.update(
        {
            "Record URL": "https://collections.penn.museum/collections/object/490764",
            "identifier": "89-13-408.2",
            "objectName": "Seal impression",
            "title": "Preserved title",
            "description": "  原文, 改変なし\n二行目  ",
            "culture": "Harappan",
            "material": "Stone",
            "inscriptionMarkLanguage": "Indus Script",
            "dateMade": "ca. 2500 B.C.",
        }
    )
    row.update(changes)
    return row


def csv_bytes(
    rows: list[dict[str, str]],
    *,
    header: tuple[str, ...] = PENN_CSV_HEADER,
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(field, "") for field in header])
    return output.getvalue().encode("utf-8")


def parse(raw_bytes: bytes, **changes: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "source_url": PENN_CSV_URL,
        "retrieved_at": RETRIEVED_AT,
        "expected_bytes": len(raw_bytes),
        "expected_sha256": f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}",
        "etag": '"penn-snapshot-1"',
        "last_modified": "Mon, 27 Jul 2026 03:00:00 GMT",
        "source_last_updated": "2026-07-27",
    }
    arguments.update(changes)
    return parse_penn_csv_snapshot(raw_bytes, **arguments)


class PennMetadataParsingTests(unittest.TestCase):
    def test_primary_and_broad_candidates_are_deterministic_and_raw_preserving(self) -> None:
        primary = penn_row(
            culture=" Harappan ",
            inscriptionMarkLanguage="Sanskrit;  INDUS   SCRIPT | undeciphered",
        )
        broad = penn_row(
            **{
                "Record URL": "https://collections.penn.museum/collections/object/2",
                "identifier": "BROAD-2",
                "objectName": "Reproduction",
                "culture": " HARAPPAN ",
                "inscriptionMarkLanguage": "Proto-Indus Script",
            }
        )
        noncandidate = penn_row(
            **{
                "Record URL": "https://collections.penn.museum/collections/object/3",
                "identifier": "OTHER-3",
                "culture": "Harappan-like",
                "inscriptionMarkLanguage": "Proto-Indus Script",
            }
        )
        raw_bytes = csv_bytes([primary, broad, noncandidate])

        first = parse(raw_bytes)
        second = parse(raw_bytes)

        self.assertEqual(first, second)
        self.assertEqual(3, first["record_count"])
        self.assertEqual(2, first["candidate_count"])
        self.assertEqual(
            [PRIMARY_SCRIPT_CANDIDATE, BROAD_ARCHAEOLOGICAL_CANDIDATE],
            [candidate["classification"] for candidate in first["candidates"]],
        )
        self.assertEqual(
            [
                {
                    "field": "inscriptionMarkLanguage",
                    "normalized_token": "indus script",
                },
                {"field": "culture", "normalized_token": "harappan"},
            ],
            first["candidates"][0]["matches"],
        )
        self.assertEqual(primary, first["candidates"][0]["raw_fields"])
        self.assertEqual(
            "  原文, 改変なし\n二行目  ",
            first["candidates"][0]["raw_fields"]["description"],
        )
        self.assertEqual(REPLICA_OR_MODERN, first["candidates"][1]["physical_status"])
        self.assertIs(False, first["source"]["images_included"])
        self.assertNotIn("media", first)
        validate_penn_metadata_semantics(first, raw_bytes=raw_bytes)

    def test_exact_normalized_tokens_do_not_accept_substrings(self) -> None:
        raw_bytes = csv_bytes(
            [
                penn_row(
                    culture="Post-Harappan",
                    inscriptionMarkLanguage="Proto-Indus Script",
                )
            ]
        )

        snapshot = parse(raw_bytes)

        self.assertEqual(0, snapshot["candidate_count"])
        self.assertEqual([], snapshot["candidates"])

    def test_duplicate_candidate_record_urls_and_identifiers_are_rejected(self) -> None:
        first = penn_row()
        duplicate_url = penn_row(
            identifier="OTHER-ID",
            culture="",
            inscriptionMarkLanguage="Indus Script",
        )
        with self.assertRaisesRegex(PennMetadataError, "duplicate candidate Record URL"):
            parse(csv_bytes([first, duplicate_url]))

        duplicate_identifier = penn_row(
            **{
                "Record URL": "https://collections.penn.museum/collections/object/other",
                "culture": "Harappan",
                "inscriptionMarkLanguage": "",
            }
        )
        with self.assertRaisesRegex(PennMetadataError, "duplicate candidate identifier"):
            parse(csv_bytes([first, duplicate_identifier]))

    def test_exact_header_contract_rejects_additions_duplicates_and_reordering(self) -> None:
        row = penn_row()
        bad_headers = {
            "addition": (*PENN_CSV_HEADER, "imageURL"),
            "duplicate": (
                PENN_CSV_HEADER[0],
                PENN_CSV_HEADER[0],
                *PENN_CSV_HEADER[2:],
            ),
            "reordered": (
                PENN_CSV_HEADER[1],
                PENN_CSV_HEADER[0],
                *PENN_CSV_HEADER[2:],
            ),
            "removed": PENN_CSV_HEADER[:-1],
        }
        for label, header in bad_headers.items():
            with (
                self.subTest(label=label),
                self.assertRaisesRegex(PennMetadataError, "header"),
            ):
                parse(csv_bytes([row], header=header))

    def test_strict_bytes_and_well_formed_csv_are_required(self) -> None:
        valid = csv_bytes([penn_row()])
        invalid_inputs = {
            "invalid_utf8": valid + b"\xff",
            "nul": valid.replace(b"Stone", b"Sto\x00ne"),
            "unterminated_quote": (
                ",".join(PENN_CSV_HEADER).encode("utf-8") + b'\r\n"unterminated'
            ),
            "short_row": ",".join(PENN_CSV_HEADER).encode("utf-8") + b"\r\none,two\r\n",
        }
        for label, raw_bytes in invalid_inputs.items():
            with self.subTest(label=label), self.assertRaises(PennMetadataError):
                parse(raw_bytes)

    def test_every_row_requires_unpadded_record_url_and_identifier(self) -> None:
        missing_url = penn_row(**{"Record URL": ""})
        missing_identifier = penn_row(identifier=" ")
        padded_url = penn_row(**{"Record URL": " https://example.invalid/object "})
        for row in (missing_url, missing_identifier, padded_url):
            with (
                self.subTest(row=row),
                self.assertRaisesRegex(PennMetadataError, "non-empty|surrounding"),
            ):
                parse(csv_bytes([row]))

    def test_physical_status_is_conservative_and_never_original(self) -> None:
        cases = {
            "material_plaster": ({"material": "Stone; Plaster of Paris"}, REPLICA_OR_MODERN),
            "object_cast": ({"objectName": "Cast"}, REPLICA_OR_MODERN),
            "object_seal_cast": ({"objectName": "Seal Cast"}, REPLICA_OR_MODERN),
            "object_reproduction": ({"objectName": "Reproduction"}, REPLICA_OR_MODERN),
            "technique_cast": ({"technique": "Molded and cast"}, REPLICA_OR_MODERN),
            "modern_word": ({"dateMade": "Modern"}, REPLICA_OR_MODERN),
            "modern_century": ({"dateMade": "20th century"}, REPLICA_OR_MODERN),
            "modern_year": ({"dateMade": "ca. 1932"}, REPLICA_OR_MODERN),
            "ancient_bce": ({"dateMade": "ca. 2500 BCE"}, PHYSICAL_STATUS_UNKNOWN),
            "ancient_range_without_era": (
                {"dateMade": "2800-2000"},
                PHYSICAL_STATUS_UNKNOWN,
            ),
            "unresolved": ({"dateMade": ""}, PHYSICAL_STATUS_UNKNOWN),
        }
        for label, (changes, expected) in cases.items():
            with self.subTest(label=label):
                candidate = parse(csv_bytes([penn_row(**changes)]))["candidates"][0]
                self.assertEqual(expected, candidate["physical_status"])
                self.assertNotEqual("original", candidate["physical_status"])

    def test_acquisition_commitments_are_checked_before_output(self) -> None:
        raw_bytes = csv_bytes([penn_row()])
        checksum = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
        failures = {
            "source_url": {"source_url": "https://example.invalid/penn.csv"},
            "expected_bytes": {"expected_bytes": len(raw_bytes) + 1},
            "expected_sha256": {"expected_sha256": "sha256:" + "0" * 64},
            "retrieved_at": {"retrieved_at": "2026-07-27T04:05:06+00:00"},
            "etag": {"etag": "bad\nvalidator"},
            "source_last_updated": {"source_last_updated": "2026-7-27"},
        }
        for label, changes in failures.items():
            with self.subTest(label=label), self.assertRaises(PennMetadataError):
                parse(raw_bytes, **changes)

        without_validators = parse(
            raw_bytes,
            expected_sha256=checksum,
            etag=None,
            last_modified=None,
            source_last_updated=None,
        )
        self.assertIsNone(without_validators["source_acquisition"]["etag"])
        self.assertIsNone(without_validators["source_acquisition"]["last_modified"])


class PennMetadataSemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_bytes = csv_bytes([penn_row()])
        self.snapshot = parse(self.raw_bytes)

    def test_semantics_reject_media_or_image_fields_anywhere(self) -> None:
        for field in ("media", "image_url"):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.snapshot)
                mutated[field] = []
                with self.assertRaisesRegex(PennMetadataError, "forbidden media/image"):
                    validate_penn_metadata_semantics(mutated)

    def test_semantics_reject_rights_and_source_constant_mutations(self) -> None:
        mutations = [
            ("license_id", "CC0-1.0"),
            ("dataset_url", "https://example.invalid/data.csv"),
            ("images_included", True),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.snapshot)
                mutated["source"][field] = value
                with self.assertRaises(PennMetadataError):
                    validate_penn_metadata_semantics(mutated)

    def test_semantics_recompute_classification_physical_status_and_matches(self) -> None:
        mutations = [
            ("classification", BROAD_ARCHAEOLOGICAL_CANDIDATE),
            ("physical_status", "original"),
            ("matches", [{"field": "culture", "normalized_token": "harappan"}]),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.snapshot)
                mutated["candidates"][0][field] = value
                with self.assertRaises(PennMetadataError):
                    validate_penn_metadata_semantics(mutated)

    def test_semantics_can_rederive_every_candidate_from_committed_bytes(self) -> None:
        mutated = copy.deepcopy(self.snapshot)
        mutated["record_count"] = 2

        with self.assertRaisesRegex(PennMetadataError, "record_count"):
            validate_penn_metadata_semantics(mutated, raw_bytes=self.raw_bytes)


class PennMetadataSchemaTests(unittest.TestCase):
    def test_parser_output_matches_closed_normative_schema(self) -> None:
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ImportError:
            self.skipTest("jsonschema optional extra is not installed")

        schema = json.loads(
            (ROOT / "schemas/penn-metadata-snapshot.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        snapshot = parse(csv_bytes([penn_row()]))

        self.assertEqual([], list(validator.iter_errors(snapshot)))


if __name__ == "__main__":
    unittest.main()
