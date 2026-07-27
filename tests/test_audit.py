from __future__ import annotations

import unittest

from indusbench.audit import audit_leakage


def record(
    artifact_id: str,
    family: str | None,
    image_hash: str,
    signs: list[tuple[str, int]],
) -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "duplicate_family_id": family,
        "sides": [
            {
                "images": [{"sha256": image_hash}],
                "lines": [
                    {
                        "tokens": [
                            {"sign_id": sign, "reading_index": reading_index}
                            for sign, reading_index in signs
                        ]
                    }
                ],
            }
        ],
    }


class LeakageAuditTests(unittest.TestCase):
    def test_detects_family_image_and_normalized_sequence_leakage(self) -> None:
        train = [
            record(
                "TRAIN-1",
                "FAMILY-7",
                "SHA256:ABCDEF",
                [("M002", 1), ("M001", 0)],
            )
        ]
        test = [
            record(
                "TEST-1",
                "FAMILY-7",
                "abcdef",
                [("M001", 0), ("M002", 1)],
            )
        ]

        report = audit_leakage(train, test)

        self.assertTrue(report.has_leakage)
        self.assertFalse(report.is_clean)
        self.assertEqual(report.family_leakage[0].value, "family:FAMILY-7")
        self.assertEqual(report.image_hash_leakage[0].value, "abcdef")
        self.assertEqual(report.sequence_leakage[0].value, '["M001","M002"]')
        self.assertEqual(
            report.sequence_leakage[0].train_artifact_ids,
            ("TRAIN-1",),
        )
        self.assertEqual(
            report.sequence_leakage[0].test_artifact_ids,
            ("TEST-1",),
        )

    def test_artifact_id_is_a_singleton_family_fallback(self) -> None:
        shared = record("SAME-ID", None, "one", [("M001", 0)])
        report = audit_leakage([shared], [shared])
        self.assertEqual(report.family_leakage[0].value, "artifact:SAME-ID")

    def test_clean_partitions_have_empty_serializable_report(self) -> None:
        train = [record("A", "F1", "hash-a", [("M001", 0), ("M002", 1)])]
        test = [record("B", "F2", "hash-b", [("M002", 0), ("M003", 1)])]

        report = audit_leakage(train, test)

        self.assertTrue(report.is_clean)
        self.assertEqual(
            report.as_dict(),
            {
                "has_leakage": False,
                "family_leakage": [],
                "image_hash_leakage": [],
                "sequence_leakage": [],
                "catalog_crosswalk_leakage": [],
            },
        )

    def test_direct_image_hash_field_is_audited(self) -> None:
        train = {
            "artifact_id": "A",
            "image_hash": "HASH",
            "tokens": [{"sign_id": "M001", "reading_index": 0}],
        }
        test = {
            "artifact_id": "B",
            "image_hash": "hash",
            "tokens": [{"sign_id": "M002", "reading_index": 0}],
        }
        report = audit_leakage([train], [test])
        self.assertEqual(report.image_hash_leakage[0].value, "hash")

    def test_unreadable_positions_are_preserved_in_sequence_fingerprint(self) -> None:
        train = {
            "artifact_id": "A",
            "tokens": [
                {"sign_id": "M001", "reading_index": 0},
                {"sign_id": None, "reading_index": 1},
                {"sign_id": "M002", "reading_index": 2},
            ],
        }
        test = {
            "artifact_id": "B",
            "tokens": [
                {"sign_id": "M001", "reading_index": 0},
                {"sign_id": "M002", "reading_index": 1},
            ],
        }
        self.assertFalse(audit_leakage([train], [test]).sequence_leakage)

    def test_visual_order_uses_right_to_left_direction_as_fallback(self) -> None:
        train = {
            "artifact_id": "A",
            "lines": [
                {
                    "reading_direction": "right_to_left",
                    "tokens": [
                        {"sign_id": "M002", "visual_index": 0},
                        {"sign_id": "M001", "visual_index": 1},
                    ],
                }
            ],
        }
        test = {
            "artifact_id": "B",
            "tokens": [
                {"sign_id": "M001", "reading_index": 0},
                {"sign_id": "M002", "reading_index": 1},
            ],
        }
        self.assertTrue(audit_leakage([train], [test]).sequence_leakage)

    def test_catalog_crosswalk_alias_is_audited(self) -> None:
        train = {
            "artifact_id": "A",
            "catalog_crosswalk": [{"catalog": "M77", "identifier": "342"}],
        }
        test = {
            "artifact_id": "B",
            "catalog_crosswalk": [
                {"catalog": "Wells", "identifier": "740"},
                {"catalog": "M77", "identifier": "342"},
            ],
        }

        report = audit_leakage([train], [test])

        self.assertTrue(report.has_leakage)
        self.assertEqual(
            report.catalog_crosswalk_leakage[0].value,
            '["M77","342"]',
        )
        self.assertEqual(
            report.catalog_crosswalk_leakage[0].train_artifact_ids,
            ("A",),
        )
        self.assertEqual(
            report.catalog_crosswalk_leakage[0].test_artifact_ids,
            ("B",),
        )


if __name__ == "__main__":
    unittest.main()
