from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import unittest
from pathlib import Path
from typing import Any

from indusbench.context_anchor import (
    PENDING_ORIGINALITY_ROLE,
    REPLICA_NEGATIVE_CONTROL_ROLE,
    ContextAnchorError,
    derive_context_anchor_registry,
    validate_context_anchor_registry,
)
from indusbench.penn_metadata import PENN_CSV_HEADER, PENN_CSV_URL, parse_penn_csv_snapshot

ROOT = Path(__file__).resolve().parents[1]
RETRIEVED_AT = "2026-07-28T08:00:00Z"


def penn_row(index: int, **changes: str) -> dict[str, str]:
    row: dict[str, str] = dict.fromkeys(PENN_CSV_HEADER, "")
    row.update(
        {
            "Record URL": f"https://collections.penn.museum/collections/object/{80000 + index}",
            "identifier": f"L-141-{index}",
            "objectName": "Seal (Object)",
            "creditLine": "Synthetic fixture credit",
            "description": "Synthetic catalog description; not archaeological evidence.",
            "placeName": "India,Chanhu-Daro",
            "siteName": "Chanhu-Daro",
            "culture": "Harappan",
            "locus": "Synthetic locus",
            "period": "Synthetic period",
            "material": "Steatite",
            "technique": "Carved",
            "iconography": "Horned Animal",
            "inscriptionMarkLanguage": "Indus Script",
            "dateMade": "2800-2000 BCE",
            "earlyDate": "-2800",
            "lateDate": "-2000",
            "width": "2.5",
            "height": "2.4",
            "weight": "12.0",
            "measurementUnit": "Centimeters/Grams",
        }
    )
    row.update(changes)
    return row


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(PENN_CSV_HEADER)
    for row in rows:
        writer.writerow([row[field] for field in PENN_CSV_HEADER])
    return output.getvalue().encode()


def parse_snapshot(rows: list[dict[str, str]]) -> dict[str, Any]:
    raw_bytes = csv_bytes(rows)
    return parse_penn_csv_snapshot(
        raw_bytes,
        source_url=PENN_CSV_URL,
        retrieved_at=RETRIEVED_AT,
        expected_bytes=len(raw_bytes),
        expected_sha256=f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}",
        etag='"synthetic-penn-snapshot"',
        last_modified="Tue, 28 Jul 2026 08:00:00 GMT",
        source_last_updated="2026-07-28",
    )


def five_pending_twenty_nine_replica_snapshot() -> dict[str, Any]:
    pending = [penn_row(index) for index in range(1, 6)]
    replicas = [
        penn_row(
            index,
            objectName="Seal Impression, Cast, Reproduction",
            material="Plaster",
            technique="Cast",
            dateMade="1900-1966",
            earlyDate="1900",
            lateDate="1966",
            locus="",
            width="",
            height="",
            weight="",
            measurementUnit="",
        )
        for index in range(6, 35)
    ]
    broad_only = penn_row(
        35,
        objectName="Sherd",
        inscriptionMarkLanguage="",
    )
    return parse_snapshot([*pending, *replicas, broad_only])


class ContextAnchorDerivationTests(unittest.TestCase):
    def test_selects_script_candidates_and_preserves_conservative_roles(self) -> None:
        snapshot = five_pending_twenty_nine_replica_snapshot()

        first = derive_context_anchor_registry(snapshot)
        second = derive_context_anchor_registry(snapshot)

        self.assertEqual(first, second)
        self.assertEqual(35, first["source_candidate_count"])
        self.assertEqual(34, first["entry_count"])
        self.assertEqual(
            {
                PENDING_ORIGINALITY_ROLE: 5,
                REPLICA_NEGATIVE_CONTROL_ROLE: 29,
            },
            first["role_counts"],
        )
        self.assertEqual(
            [PENDING_ORIGINALITY_ROLE] * 5 + [REPLICA_NEGATIVE_CONTROL_ROLE] * 29,
            [entry["anchor_role"] for entry in first["entries"]],
        )
        self.assertNotIn("L-141-35", [entry["accession_number"] for entry in first["entries"]])

    def test_context_is_raw_source_bound_and_axes_are_explicit(self) -> None:
        registry = derive_context_anchor_registry(five_pending_twenty_nine_replica_snapshot())
        entry = registry["entries"][0]

        self.assertEqual("Synthetic locus", entry["source_fields"]["locus"])
        self.assertEqual("12.0", entry["source_fields"]["weight"])
        self.assertEqual("Centimeters/Grams", entry["source_fields"]["measurementUnit"])
        self.assertEqual(
            [
                "catalog_identity",
                "script_catalog_label",
                "site_context",
                "culture_context",
                "excavation_context",
                "chronology_context",
                "object_form",
                "material_technology",
                "motif_context",
                "measurement_context",
                "provenance_credit",
                "catalog_description",
            ],
            [axis["axis"] for axis in entry["anchor_axes"]],
        )
        measurement_axis = next(
            axis for axis in entry["anchor_axes"] if axis["axis"] == "measurement_context"
        )
        self.assertEqual(
            ["width", "height", "weight", "measurementUnit"],
            measurement_axis["source_fields"],
        )
        self.assertTrue(entry["provenance"]["raw_fields_sha256"].startswith("sha256:"))

    def test_all_interpretive_and_field_number_gates_remain_closed(self) -> None:
        registry = derive_context_anchor_registry(five_pending_twenty_nine_replica_snapshot())

        self.assertFalse(registry["rights"]["images_included"])
        self.assertEqual("metadata_only", registry["rights"]["scope"])
        for entry in registry["entries"]:
            self.assertEqual(
                {
                    "status": "not_available_in_bulk_snapshot",
                    "values": [],
                },
                entry["field_numbers"],
            )
            self.assertEqual(
                {
                    "human_review_required": True,
                    "transcription_approved": False,
                    "meaning_approved": False,
                    "originality_approved": False,
                    "field_number_approved": False,
                },
                entry["admission"],
            )

    def test_registry_is_exactly_rederived_from_the_supplied_snapshot(self) -> None:
        snapshot = five_pending_twenty_nine_replica_snapshot()
        registry = derive_context_anchor_registry(snapshot)
        changed_snapshot = copy.deepcopy(snapshot)
        changed_snapshot["candidates"][0]["raw_fields"]["description"] = "Changed catalog text"

        with self.assertRaisesRegex(ContextAnchorError, "exactly match"):
            validate_context_anchor_registry(registry, source_snapshot=changed_snapshot)


class ContextAnchorSemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = five_pending_twenty_nine_replica_snapshot()
        self.registry = derive_context_anchor_registry(self.snapshot)

    def test_rejects_role_axis_and_source_binding_tampering(self) -> None:
        mutations = []

        wrong_role = copy.deepcopy(self.registry)
        wrong_role["entries"][0]["anchor_role"] = REPLICA_NEGATIVE_CONTROL_ROLE
        mutations.append(wrong_role)

        missing_axis = copy.deepcopy(self.registry)
        missing_axis["entries"][0]["anchor_axes"].pop()
        mutations.append(missing_axis)

        wrong_digest = copy.deepcopy(self.registry)
        wrong_digest["entries"][0]["provenance"]["source_sha256"] = "sha256:" + "0" * 64
        mutations.append(wrong_digest)

        for mutated in mutations:
            with self.subTest(mutated=mutated["entries"][0]), self.assertRaises(ContextAnchorError):
                validate_context_anchor_registry(mutated)

    def test_rejects_any_approval_or_field_number_invention(self) -> None:
        approval = copy.deepcopy(self.registry)
        approval["entries"][0]["admission"]["originality_approved"] = True
        with self.assertRaisesRegex(ContextAnchorError, "approval gates"):
            validate_context_anchor_registry(approval)

        field_number = copy.deepcopy(self.registry)
        field_number["entries"][0]["field_numbers"] = {
            "status": "reviewed",
            "values": ["3495"],
        }
        with self.assertRaisesRegex(ContextAnchorError, "unavailable and empty"):
            validate_context_anchor_registry(field_number)

    def test_rejects_duplicates_even_if_counts_are_adjusted(self) -> None:
        duplicate = copy.deepcopy(self.registry)
        duplicate_entry = copy.deepcopy(duplicate["entries"][-1])
        duplicate_entry["csv_row_number"] += 1
        duplicate_entry["provenance"]["csv_row_number"] += 1
        duplicate["entries"].append(duplicate_entry)
        duplicate["entry_count"] += 1
        duplicate["source_candidate_count"] += 1
        duplicate["role_counts"][REPLICA_NEGATIVE_CONTROL_ROLE] += 1

        with self.assertRaisesRegex(ContextAnchorError, "duplicate anchor_id"):
            validate_context_anchor_registry(duplicate)


class ContextAnchorSchemaTests(unittest.TestCase):
    def test_output_matches_closed_normative_schema(self) -> None:
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ImportError:
            self.skipTest("jsonschema is not installed")

        schema = json.loads(
            (ROOT / "schemas/context-anchor-registry.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        registry = derive_context_anchor_registry(five_pending_twenty_nine_replica_snapshot())

        self.assertEqual([], list(validator.iter_errors(registry)))


if __name__ == "__main__":
    unittest.main()
