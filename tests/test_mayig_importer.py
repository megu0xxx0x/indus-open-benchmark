from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from indusbench.importers.mayig import (
    MayigImportError,
    import_mayig_artifact,
    import_mayig_corpus,
)
from indusbench.validation import has_errors, validate_corpus

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "mayig"
REVISION = "a" * 40
RETRIEVED_AT = "2026-07-26T12:00:00+09:00"


class MayigCorpusImporterTests(unittest.TestCase):
    def test_imported_records_pass_domain_validation(self) -> None:
        records = import_mayig_corpus(
            FIXTURE_ROOT,
            source_revision=REVISION,
            retrieved_at=RETRIEVED_AT,
        )

        issues = validate_corpus(records)
        self.assertFalse(has_errors(issues), issues)

    def test_corpus_order_ids_provenance_and_rights_are_stable(self) -> None:
        records = import_mayig_corpus(
            FIXTURE_ROOT,
            source_revision=REVISION,
            retrieved_at=RETRIEVED_AT,
        )

        self.assertEqual(["M-9001", "M-9002"], [record["artifact_id"] for record in records])
        source = records[0]["source_records"][0]
        self.assertEqual("M-9001", source["upstream_record_id"])
        self.assertEqual(REVISION, source["revision"])
        self.assertEqual("corpus/m9000_m9099/m9001.json", source["source_path"])
        self.assertRegex(source["record_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertIn(f"/blob/{REVISION}/", source["locator"])
        self.assertEqual("metadata_only", records[0]["rights"]["status"])
        self.assertEqual([], records[0]["images"])

    def test_visual_order_and_inferred_reading_order_remain_separate(self) -> None:
        record = import_mayig_corpus(
            FIXTURE_ROOT,
            source_revision=REVISION,
            retrieved_at=RETRIEVED_AT,
        )[0]

        side = record["sides"][0]
        self.assertEqual("M-9001A", side["side_id"])
        self.assertEqual("seal_impression", side["physical_form"])
        self.assertEqual(2, len(side["lines"]))
        first_line = side["lines"][0]
        self.assertEqual("right_to_left", first_line["reading_direction"])
        self.assertEqual(["P901", "P902"], [token["sign_id"] for token in first_line["tokens"]])
        self.assertEqual([0, 1], [token["visual_index"] for token in first_line["tokens"]])
        self.assertEqual([1, 0], [token["reading_index"] for token in first_line["tokens"]])
        self.assertAlmostEqual(0.8, first_line["tokens"][1]["confidence"])

    def test_raw_features_and_out_of_range_damage_are_not_silently_repaired(self) -> None:
        record = import_mayig_corpus(
            FIXTURE_ROOT,
            source_revision=REVISION,
            retrieved_at=RETRIEVED_AT,
        )[1]
        token = record["sides"][0]["lines"][0]["tokens"][0]
        extensions = record["extensions"]

        self.assertEqual("damaged", token["condition"])
        self.assertEqual(
            [125, 1, 10, 3], extensions["mayig:raw_feature_vectors"][token["token_id"]]
        )
        warnings = extensions["mayig:import_warnings"]
        self.assertEqual(["damage_out_of_documented_range"], [item["code"] for item in warnings])
        self.assertEqual(125, warnings[0]["raw_value"])

    def test_multiple_upstream_sides_and_line_numbers_are_preserved(self) -> None:
        record = import_mayig_corpus(
            FIXTURE_ROOT,
            source_revision=REVISION,
            retrieved_at=RETRIEVED_AT,
        )[0]

        self.assertEqual(["M-9001A", "M-9001B"], [side["side_id"] for side in record["sides"]])
        self.assertEqual(
            ["M-9001A:L1", "M-9001A:L2"],
            [line["line_id"] for line in record["sides"][0]["lines"]],
        )
        second_line_token = record["sides"][0]["lines"][1]["tokens"][0]
        self.assertEqual("M-9001A:L2:T3", second_line_token["token_id"])
        self.assertEqual(
            2,
            record["extensions"]["mayig:upstream_grapheme_indices"][second_line_token["token_id"]],
        )

    def test_invalid_uncertainty_is_rejected_instead_of_clamped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "m9999.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "M-9999A",
                            "description": "synthetic seal",
                            "graphemes": [{"id": "P999", "features": [0, 1, 101]}],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(MayigImportError, "outside documented range"):
                import_mayig_artifact(path, source_revision=REVISION)

    def test_non_json_or_empty_corpus_reports_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "m9998.json"
            path.write_text("{not-json", encoding="utf-8")

            with self.assertRaisesRegex(MayigImportError, "m9998.json"):
                import_mayig_artifact(path, source_revision=REVISION)


if __name__ == "__main__":
    unittest.main()
