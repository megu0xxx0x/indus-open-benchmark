from __future__ import annotations

import unittest

from indusbench.audit import audit_leakage
from indusbench.splits import (
    MISSING_GROUP,
    deterministic_family_split,
    deterministic_leakage_safe_split,
    leave_one_object_type_out,
    leave_one_period_out,
    leave_one_site_out,
)


def artifact(
    artifact_id: str,
    family: str | None,
    site: str | None,
    period: str,
    object_type: str,
) -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "duplicate_family_id": family,
        "site": site,
        "period": period,
        "object_type": object_type,
    }


class DeterministicFamilySplitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            artifact("A1", "F1", "Mohenjo-daro", "Mature", "seal"),
            artifact("A2", "F1", "Mohenjo-daro", "Mature", "impression"),
            artifact("B1", "F2", "Harappa", "Mature", "seal"),
            artifact("C1", None, "Dholavira", "Late", "tablet"),
            artifact("D1", None, None, "Early", "pottery"),
        ]

    def test_is_deterministic_and_never_splits_duplicate_families(self) -> None:
        train, test = deterministic_family_split(
            self.records,
            test_fraction=0.5,
            seed=2026,
        )
        reversed_train, reversed_test = deterministic_family_split(
            reversed(self.records),
            test_fraction=0.5,
            seed=2026,
        )

        self.assertEqual(
            {record["artifact_id"] for record in train},
            {record["artifact_id"] for record in reversed_train},
        )
        self.assertEqual(
            {record["artifact_id"] for record in test},
            {record["artifact_id"] for record in reversed_test},
        )
        train_families = {
            record["duplicate_family_id"]
            for record in train
            if record["duplicate_family_id"] is not None
        }
        test_families = {
            record["duplicate_family_id"]
            for record in test
            if record["duplicate_family_id"] is not None
        }
        self.assertTrue(train)
        self.assertTrue(test)
        self.assertTrue(train_families.isdisjoint(test_families))

    def test_boundary_fractions_and_invalid_inputs(self) -> None:
        train, test = deterministic_family_split(self.records, test_fraction=0.0)
        self.assertEqual(len(train), len(self.records))
        self.assertEqual(test, [])

        train, test = deterministic_family_split(self.records, test_fraction=1.0)
        self.assertEqual(train, [])
        self.assertEqual(len(test), len(self.records))

        with self.assertRaises(ValueError):
            deterministic_family_split(self.records, test_fraction=float("nan"))
        with self.assertRaises(ValueError):
            deterministic_family_split(
                [artifact("A1", "F1", "Harappa", "Mature", "seal")],
                test_fraction=0.2,
            )

    def test_missing_artifact_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "artifact_id"):
            deterministic_family_split([{"duplicate_family_id": None}])


class LeakageSafeSplitTests(unittest.TestCase):
    @staticmethod
    def _linked_record(
        artifact_id: str,
        family: str | None,
        image_hash: str,
        signs: list[str],
        catalog_aliases: list[tuple[str, str]] | None = None,
    ) -> dict[str, object]:
        return {
            "artifact_id": artifact_id,
            "duplicate_family_id": family,
            "catalog_crosswalk": [
                {"catalog": catalog, "identifier": identifier}
                for catalog, identifier in (catalog_aliases or [])
            ],
            "images": [{"image_hash": f"sha256:{image_hash}"}],
            "tokens": [
                {"sign_id": sign, "reading_index": index} for index, sign in enumerate(signs)
            ],
        }

    def test_transitive_family_image_sequence_catalog_component_stays_together(
        self,
    ) -> None:
        chain = [
            self._linked_record("A", "F1", "a" * 64, ["S1"]),
            self._linked_record("B", "F1", "b" * 64, ["S2"]),
            self._linked_record("C", "F3", "b" * 64, ["S3"]),
            self._linked_record(
                "D",
                "F4",
                "d" * 64,
                ["S3"],
                [("M77", "342")],
            ),
            self._linked_record(
                "E",
                "F5",
                "e" * 64,
                ["S5"],
                [("M77", "342")],
            ),
        ]
        independent = [
            self._linked_record("F", "F6", "f" * 64, ["S6"]),
            self._linked_record("G", "F7", "0" * 64, ["S7"]),
        ]

        train, test = deterministic_leakage_safe_split(
            chain + independent,
            test_fraction=0.5,
            seed=17,
        )

        train_ids = {record["artifact_id"] for record in train}
        test_ids = {record["artifact_id"] for record in test}
        chain_ids = {"A", "B", "C", "D", "E"}
        self.assertTrue(chain_ids <= train_ids or chain_ids <= test_ids)
        self.assertTrue(train)
        self.assertTrue(test)

        self.assertTrue(audit_leakage(train, test).is_clean)

    def test_assignment_is_independent_of_input_order(self) -> None:
        records = [
            self._linked_record("A", "F1", "a" * 64, ["S1"]),
            self._linked_record("B", "F2", "b" * 64, ["S2"]),
            self._linked_record("C", "F3", "c" * 64, ["S3"]),
        ]
        train, test = deterministic_leakage_safe_split(records, seed="stable")
        reversed_train, reversed_test = deterministic_leakage_safe_split(
            reversed(records),
            seed="stable",
        )
        self.assertEqual(
            {record["artifact_id"] for record in train},
            {record["artifact_id"] for record in reversed_train},
        )
        self.assertEqual(
            {record["artifact_id"] for record in test},
            {record["artifact_id"] for record in reversed_test},
        )


class LeaveOneGroupOutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            artifact("A", None, "Harappa", "Mature", "seal"),
            artifact("B", None, "Harappa", "Late", "tablet"),
            artifact("C", None, "Dholavira", "Mature", "seal"),
            artifact("D", None, None, "Early", "pottery"),
        ]

    def test_leave_one_site_out(self) -> None:
        splits = leave_one_site_out(self.records)
        self.assertEqual(set(splits), {"Dholavira", "Harappa", MISSING_GROUP})
        train, test = splits["Harappa"]
        self.assertEqual({record["artifact_id"] for record in test}, {"A", "B"})
        self.assertEqual({record["artifact_id"] for record in train}, {"C", "D"})

    def test_leave_one_period_and_object_type_out(self) -> None:
        period_splits = leave_one_period_out(self.records)
        self.assertEqual(
            {record["artifact_id"] for record in period_splits["Mature"][1]},
            {"A", "C"},
        )

        object_splits = leave_one_object_type_out(self.records)
        self.assertEqual(
            {record["artifact_id"] for record in object_splits["seal"][1]},
            {"A", "C"},
        )

    def test_object_mapping_is_normalized(self) -> None:
        records = [
            {
                "artifact_id": "A",
                "site": {"site_id": "SITE-A", "name": "A"},
                "period": {"label": "Mature", "phase": "III"},
                "object": {"object_type": "seal"},
            },
            {
                "artifact_id": "B",
                "site": {"site_id": "SITE-B", "name": "B"},
                "period": {"label": None, "phase": "Late"},
                "object": {"object_type": "tablet"},
            },
        ]
        self.assertEqual(set(leave_one_object_type_out(records)), {"seal", "tablet"})
        self.assertEqual(set(leave_one_site_out(records)), {"SITE-A", "SITE-B"})
        self.assertEqual(set(leave_one_period_out(records)), {"Late", "Mature"})

    def test_group_holdout_closes_over_duplicate_families(self) -> None:
        records = [
            artifact("A", "F1", "Harappa", "Mature", "seal"),
            artifact("B", "F1", "Dholavira", "Late", "tablet"),
            artifact("C", "F2", "Dholavira", "Late", "tablet"),
        ]
        train, test = leave_one_site_out(records)["Harappa"]
        self.assertEqual({record["artifact_id"] for record in test}, {"A", "B"})
        self.assertEqual({record["artifact_id"] for record in train}, {"C"})


if __name__ == "__main__":
    unittest.main()
