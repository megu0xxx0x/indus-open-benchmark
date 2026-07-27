from __future__ import annotations

import json
import os
import unittest
from collections import Counter
from pathlib import Path
from typing import ClassVar

from indusbench.importers.mayig import import_mayig_corpus
from indusbench.treewidth_audit import (
    build_undirected_adjacency_graph,
    empirical_frequency_iid,
    evaluate_treewidth_nulls,
    extract_treewidth_sequences,
    global_frequency_preserving_shuffle,
    min_degree_treewidth_upper_bound,
    within_sequence_order_shuffle,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "mayig"
MAYIG_REVISION = "ad2f1e218a34b8c33c57de0d6cb8d99272765bbb"
MAYIG_INTEGRATION_ROOT = os.environ.get("INDUSBENCH_MAYIG_REVISION_ROOT")


class TreewidthGraphTests(unittest.TestCase):
    def test_adjacency_is_undirected_and_excludes_self_loops(self) -> None:
        graph = build_undirected_adjacency_graph(
            [
                ("A", "A", "B"),
                ("C", "B"),
                ("D",),
            ]
        )

        self.assertEqual(
            {
                "A": {"B"},
                "B": {"A", "C"},
                "C": {"B"},
                "D": set(),
            },
            graph,
        )

    def test_minimum_degree_upper_bound_on_known_graphs(self) -> None:
        path = {"A": {"B"}, "B": {"A", "C"}, "C": {"B", "D"}, "D": {"C"}}
        cycle = {
            "A": {"B", "D"},
            "B": {"A", "C"},
            "C": {"B", "D"},
            "D": {"A", "C"},
        }
        clique = {
            "A": {"B", "C", "D"},
            "B": {"A", "C", "D"},
            "C": {"A", "B", "D"},
            "D": {"A", "B", "C"},
        }

        self.assertEqual(1, min_degree_treewidth_upper_bound(path))
        self.assertEqual(2, min_degree_treewidth_upper_bound(cycle))
        self.assertEqual(3, min_degree_treewidth_upper_bound(clique))
        self.assertEqual(0, min_degree_treewidth_upper_bound({"A": {"A"}}))


class TreewidthNullTests(unittest.TestCase):
    sequences: ClassVar[list[tuple[str, ...]]] = [
        ("A", "B", "C", "D"),
        ("A", "C", "E"),
        ("D", "E", "B"),
        ("E", "A", "D", "B"),
    ]

    def test_null_generators_are_deterministic_and_preserve_declared_units(self) -> None:
        global_first = global_frequency_preserving_shuffle(self.sequences, 17)
        global_second = global_frequency_preserving_shuffle(self.sequences, 17)
        within = within_sequence_order_shuffle(self.sequences, 17)
        iid_first = empirical_frequency_iid(self.sequences, 17)
        iid_second = empirical_frequency_iid(self.sequences, 17)

        self.assertEqual(global_first, global_second)
        self.assertEqual(iid_first, iid_second)
        expected_lengths = [len(sequence) for sequence in self.sequences]
        self.assertEqual(expected_lengths, [len(sequence) for sequence in global_first])
        self.assertEqual(
            Counter(sign for sequence in self.sequences for sign in sequence),
            Counter(sign for sequence in global_first for sign in sequence),
        )
        for observed, shuffled in zip(self.sequences, within, strict=True):
            self.assertEqual(Counter(observed), Counter(shuffled))
        self.assertEqual(expected_lengths, [len(sequence) for sequence in iid_first])
        self.assertLessEqual(
            {sign for sequence in iid_first for sign in sequence},
            {sign for sequence in self.sequences for sign in sequence},
        )

    def test_evaluation_is_deterministic_and_json_compatible(self) -> None:
        first = evaluate_treewidth_nulls(self.sequences, runs=9, seed=23)
        second = evaluate_treewidth_nulls(self.sequences, runs=9, seed=23)
        explicitly_flat = evaluate_treewidth_nulls(
            self.sequences,
            runs=1,
            seed=23,
            sequence_unit="artifact_flat",
        )

        self.assertEqual(first, second)
        self.assertEqual(first, json.loads(json.dumps(first)))
        self.assertEqual(9, first["runs"])
        self.assertEqual(4, first["sequence_count"])
        self.assertEqual(14, first["token_count"])
        self.assertEqual(
            {
                "global_frequency_preserving_shuffle",
                "within_sequence_order_shuffle",
                "empirical_frequency_iid",
            },
            set(first["null_models"]),
        )
        observed = first["observed"]["treewidth_upper_bound"]
        for result in first["null_models"].values():
            self.assertEqual(observed, result["observed"])
            self.assertEqual(9, len(result["run_values"]))
            self.assertLessEqual(result["min"], result["mean"])
            self.assertLessEqual(result["mean"], result["max"])
            self.assertLessEqual(result["min"], result["median"])
            self.assertLessEqual(result["median"], result["max"])
            for rate in result["empirical_rate"].values():
                self.assertGreaterEqual(rate, 0.0)
                self.assertLessEqual(rate, 1.0)
        self.assertEqual(
            {"explicit_input_sequences": 4},
            explicitly_flat["sequence_policy"]["order_basis_counts"],
        )
        self.assertEqual("artifact_flat", explicitly_flat["sequence_policy"]["sequence_unit"])

    def test_mayig_fixture_keeps_canonical_lines_and_artifact_flat_distinct(self) -> None:
        records = import_mayig_corpus(
            FIXTURE_ROOT,
            source_revision="a" * 40,
            retrieved_at="2026-07-26T12:00:00+09:00",
        )

        canonical = evaluate_treewidth_nulls(records, runs=3, seed=5)
        artifact_flat = evaluate_treewidth_nulls(
            records,
            runs=3,
            seed=5,
            sequence_unit="artifact_flat",
        )
        artifact_flat_min_two = evaluate_treewidth_nulls(
            records,
            runs=3,
            seed=5,
            sequence_unit="artifact_flat",
            min_length=2,
        )

        self.assertEqual(
            (4, 5, 1),
            (
                canonical["sequence_count"],
                canonical["token_count"],
                canonical["observed"]["edge_count"],
            ),
        )
        self.assertEqual(
            (2, 5, 3),
            (
                artifact_flat["sequence_count"],
                artifact_flat["token_count"],
                artifact_flat["observed"]["edge_count"],
            ),
        )
        self.assertEqual(
            (1, 4, 4, 3, 1),
            (
                artifact_flat_min_two["sequence_count"],
                artifact_flat_min_two["token_count"],
                artifact_flat_min_two["observed"]["node_count"],
                artifact_flat_min_two["observed"]["edge_count"],
                artifact_flat_min_two["observed"]["treewidth_upper_bound"],
            ),
        )
        self.assertEqual(
            {"mayig_upstream_grapheme_index": 2},
            artifact_flat["sequence_policy"]["order_basis_counts"],
        )
        self.assertEqual(
            {"sequence_count": 1, "token_count": 1},
            artifact_flat_min_two["sequence_policy"]["excluded"],
        )
        self.assertEqual(
            3,
            len(artifact_flat["null_models"]["empirical_frequency_iid"]["run_values"]),
        )

    def test_extraction_policy_is_available_without_running_nulls(self) -> None:
        sequences, policy = extract_treewidth_sequences(
            self.sequences,
            sequence_unit="canonical_line",
            min_length=4,
        )

        self.assertEqual([self.sequences[0], self.sequences[3]], sequences)
        self.assertEqual({"sequence_count": 2, "token_count": 6}, policy["excluded"])
        self.assertEqual({"sequence_count": 2, "token_count": 8}, policy["after_filter"])

    def test_rejects_invalid_run_count_and_empty_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            evaluate_treewidth_nulls(self.sequences, runs=0)
        with self.assertRaisesRegex(ValueError, "after min_length"):
            evaluate_treewidth_nulls([], runs=1)
        with self.assertRaisesRegex(ValueError, "min_length must be at least 1"):
            evaluate_treewidth_nulls(self.sequences, runs=1, min_length=0)


@unittest.skipUnless(
    MAYIG_INTEGRATION_ROOT,
    "set INDUSBENCH_MAYIG_REVISION_ROOT to the fixed mayig checkout",
)
class RossMayigRevisionIntegrationTests(unittest.TestCase):
    def test_artifact_flat_reproduces_fixed_revision_graph_counts(self) -> None:
        records = import_mayig_corpus(
            Path(MAYIG_INTEGRATION_ROOT or ""),
            source_revision=MAYIG_REVISION,
            retrieved_at="2026-07-26T00:00:00Z",
        )

        full = evaluate_treewidth_nulls(
            records,
            runs=1,
            seed=20260726,
            sequence_unit="artifact_flat",
        )
        minimum_two = evaluate_treewidth_nulls(
            records,
            runs=1,
            seed=20260726,
            sequence_unit="artifact_flat",
            min_length=2,
        )

        self.assertEqual((179, 1003), (full["sequence_count"], full["token_count"]))
        self.assertEqual(
            {"treewidth_upper_bound": 26, "node_count": 182, "edge_count": 521},
            full["observed"],
        )
        self.assertEqual(
            (178, 1002),
            (minimum_two["sequence_count"], minimum_two["token_count"]),
        )
        self.assertEqual(
            {"treewidth_upper_bound": 26, "node_count": 181, "edge_count": 521},
            minimum_two["observed"],
        )


if __name__ == "__main__":
    unittest.main()
