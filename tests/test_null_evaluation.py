from __future__ import annotations

import unittest

from indusbench.null_evaluation import evaluate_shuffle_null
from tests.test_cli import distinct_records


class NullEvaluationTests(unittest.TestCase):
    def test_repeated_null_is_deterministic_and_scoped(self) -> None:
        records = distinct_records(8)
        train = records[:6]
        test = records[6:]

        first = evaluate_shuffle_null(train, test, order=2, runs=5, seed=11)
        second = evaluate_shuffle_null(train, test, order=2, runs=5, seed=11)

        self.assertEqual(first, second)
        self.assertEqual(5, first["runs"])
        self.assertEqual(5, len(first["run_values"]))
        self.assertIn("does not identify language", first["scientific_scope"])
        for value in first["empirical_p_values"].values():
            self.assertGreater(value, 0)
            self.assertLessEqual(value, 1)

    def test_requires_at_least_one_run(self) -> None:
        records = distinct_records(4)
        with self.assertRaisesRegex(ValueError, "at least 1"):
            evaluate_shuffle_null(records[:3], records[3:], runs=0)


if __name__ == "__main__":
    unittest.main()
