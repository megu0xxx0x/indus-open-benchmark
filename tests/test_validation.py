from __future__ import annotations

import unittest

from indusbench.validation import has_errors, validate_artifact, validate_corpus


def valid_artifact(artifact_id: str = "SYN:A001") -> dict:
    return {
        "schema_version": "0.1.0",
        "artifact_id": artifact_id,
        "source_records": [
            {
                "source_record_id": f"{artifact_id}:source",
                "source_id": "synthetic",
                "upstream_record_id": artifact_id,
                "role": "primary_record",
                "locator": "urn:synthetic:record",
                "retrieved_at": "2026-07-26T00:00:00Z",
                "revision": "fixture-v1",
                "source_path": None,
                "record_hash": f"sha256:{'1' * 64}",
            }
        ],
        "rights": {
            "status": "public_domain",
            "license_id": "CC0-1.0",
            "license_uri": "https://creativecommons.org/publicdomain/zero/1.0/",
            "rights_holder": None,
            "redistribution": True,
            "derivatives": True,
            "commercial_use": True,
            "statement": "Synthetic fixture; no external rights.",
            "evidence_uri": None,
            "verified_at": "2026-07-26T00:00:00Z",
        },
        "catalog_crosswalk": [],
        "site": {
            "site_id": "SYN:SITE-A",
            "name": "Synthetic Site A",
            "modern_country": None,
            "administrative_area": None,
            "findspot": None,
            "certainty": 1.0,
        },
        "period": {
            "label": "Synthetic Period 1",
            "phase": "SYN:P1",
            "earliest_year_bce": 2600,
            "latest_year_bce": 2500,
            "basis": "unknown",
            "certainty": 1.0,
        },
        "object": {
            "object_type": "seal",
            "material": "synthetic",
            "dimensions_mm": None,
            "condition": "complete",
            "collection": {"institution": None, "accession_number": None},
            "observed_motifs": [],
        },
        "duplicate_family_id": "SYN:F001",
        "images": [
            {
                "image_id": "SYN:IMG001",
                "source_id": "synthetic",
                "image_role": "impression",
                "uri": "urn:synthetic:image:001",
                "iiif_manifest": None,
                "image_hash": f"sha256:{'0' * 64}",
                "pixel_width": 100,
                "pixel_height": 100,
                "rights": {
                    "status": "public_domain",
                    "license_id": "CC0-1.0",
                    "license_uri": "https://creativecommons.org/publicdomain/zero/1.0/",
                    "rights_holder": None,
                    "redistribution": True,
                    "derivatives": True,
                    "commercial_use": True,
                    "statement": "Synthetic fixture.",
                    "evidence_uri": None,
                    "verified_at": "2026-07-26T00:00:00Z",
                },
            }
        ],
        "sides": [
            {
                "side_id": "SYN:A001:obverse",
                "physical_form": "seal_impression",
                "image_ids": ["SYN:IMG001"],
                "lines": [
                    {
                        "line_id": "SYN:A001:L1",
                        "visual_order_basis": "left_to_right_in_image",
                        "reading_direction": "right_to_left",
                        "direction_confidence": 1.0,
                        "tokens": [
                            {
                                "token_id": "SYN:A001:L1:T1",
                                "sign_id": "SYN:001",
                                "visual_index": 0,
                                "reading_index": 1,
                                "confidence": 1.0,
                                "condition": "clear",
                                "uncertainty": {
                                    "status": "certain",
                                    "alternatives": [],
                                    "notes": None,
                                },
                                "geometry": None,
                                "source_record_ids": [f"{artifact_id}:source"],
                            },
                            {
                                "token_id": "SYN:A001:L1:T2",
                                "sign_id": "SYN:002",
                                "visual_index": 1,
                                "reading_index": 0,
                                "confidence": 0.9,
                                "condition": "clear",
                                "uncertainty": {
                                    "status": "clear",
                                    "alternatives": [],
                                    "notes": None,
                                },
                                "geometry": None,
                                "source_record_ids": [f"{artifact_id}:source"],
                            },
                        ],
                    }
                ],
            }
        ],
    }


class ArtifactValidationTests(unittest.TestCase):
    def test_valid_record_has_no_errors(self) -> None:
        issues = validate_artifact(valid_artifact())
        self.assertFalse(has_errors(issues), issues)

    def test_duplicate_artifact_id_is_rejected(self) -> None:
        issues = validate_corpus([valid_artifact(), valid_artifact()])
        self.assertIn("duplicate_artifact_id", {issue.code for issue in issues})

    def test_unknown_direction_with_order_warns(self) -> None:
        record = valid_artifact()
        record["sides"][0]["lines"][0]["reading_direction"] = "unknown"
        issues = validate_artifact(record)
        conflicts = [issue for issue in issues if issue.code == "direction_order_conflict"]
        self.assertEqual(1, len(conflicts))
        self.assertEqual("warning", conflicts[0].severity)

    def test_allowed_images_require_explicit_license(self) -> None:
        record = valid_artifact()
        record["rights"]["status"] = "open_licensed"
        record["rights"]["license_id"] = None
        issues = validate_artifact(record)
        self.assertIn("missing_license", {issue.code for issue in issues})

    def test_visual_and_reading_indices_are_independent(self) -> None:
        record = valid_artifact()
        tokens = record["sides"][0]["lines"][0]["tokens"]
        tokens[1]["visual_index"] = 0
        issues = validate_artifact(record)
        self.assertIn("duplicate_visual_index", {issue.code for issue in issues})


if __name__ == "__main__":
    unittest.main()
