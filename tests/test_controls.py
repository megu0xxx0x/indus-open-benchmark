from __future__ import annotations

import unittest

from indusbench.controls import global_sign_shuffle
from tests.test_validation import valid_artifact


def signs(records: list[dict]) -> list[str]:
    return [
        token["sign_id"]
        for record in records
        for side in record["sides"]
        for line in side["lines"]
        for token in line["tokens"]
    ]


class ControlTests(unittest.TestCase):
    def test_shuffle_is_deterministic_and_preserves_counts(self) -> None:
        records = [valid_artifact("SYN:A001"), valid_artifact("SYN:A002")]
        records[1]["sides"][0]["lines"][0]["tokens"][0]["sign_id"] = "SYN:003"

        first = global_sign_shuffle(records, seed=7)
        second = global_sign_shuffle(records, seed=7)

        self.assertEqual(first, second)
        self.assertCountEqual(signs(records), signs(first))
        self.assertEqual(
            [
                len(line["tokens"])
                for record in records
                for side in record["sides"]
                for line in side["lines"]
            ],
            [
                len(line["tokens"])
                for record in first
                for side in record["sides"]
                for line in side["lines"]
            ],
        )
        self.assertNotIn("extensions", records[0])
        self.assertEqual(
            "global_sign_shuffle",
            first[0]["extensions"]["indusbench:control"]["kind"],
        )


if __name__ == "__main__":
    unittest.main()
