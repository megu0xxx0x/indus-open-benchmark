from __future__ import annotations

import math
import unittest

from indusbench.v3dev.contracts import V3_STRUCTURAL_STATES
from indusbench.v3dev.folds import (
    PRIMARY_INNER_FOLD_COUNT,
    PRIMARY_OUTER_FOLD_COUNT,
    V3_STATES,
    CandidateScore,
    FamilySupport,
    NestedFoldPlan,
    V3FoldError,
    build_grouped_folds,
    build_nested_grouped_folds,
    make_family_support,
    select_one_standard_error,
    summarize_scores,
)


def family(
    family_id: str,
    counts: tuple[int, ...],
) -> FamilySupport:
    return make_family_support(
        family_id,
        dict(zip(V3_STATES, counts, strict=True)),
    )


def sparse_primary_families() -> tuple[FamilySupport, ...]:
    result: list[FamilySupport] = []
    for state_index in range(len(V3_STATES)):
        for replicate in range(PRIMARY_OUTER_FOLD_COUNT):
            counts = [0] * len(V3_STATES)
            counts[state_index] = replicate + 1
            result.append(
                family(
                    f"opaque-family-{state_index}-{replicate}",
                    tuple(counts),
                )
            )
    return tuple(result)


def plan_membership(
    plan: NestedFoldPlan,
) -> tuple[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]], ...]:
    return tuple(
        (
            nested.outer.validation_family_ids,
            tuple(fold.validation_family_ids for fold in nested.inner_folds),
        )
        for nested in plan.outer_folds
    )


class FamilySupportTests(unittest.TestCase):
    def test_uses_the_contract_state_order(self) -> None:
        self.assertIs(V3_STATES, V3_STRUCTURAL_STATES)
        item = family("opaque-family", (1, 2, 3, 4, 5))
        self.assertEqual(1, item.count("context_only"))
        self.assertEqual(5, item.count("settlement_name"))

    def test_requires_exact_states_non_negative_counts_and_ascii_ids(self) -> None:
        with self.assertRaisesRegex(V3FoldError, "exactly V3_STRUCTURAL_STATES"):
            make_family_support("opaque", {"context_only": 1})
        with self.assertRaisesRegex(V3FoldError, "non-negative"):
            family("opaque", (1, 1, 1, 1, -1))
        with self.assertRaisesRegex(V3FoldError, "non-negative"):
            family("opaque", (1, 1, 1, 1, True))
        with self.assertRaisesRegex(V3FoldError, "at least one"):
            family("opaque", (0, 0, 0, 0, 0))
        with self.assertRaisesRegex(V3FoldError, "printable ASCII"):
            family("family-日本語", (1, 1, 1, 1, 1))

    def test_family_repr_omits_the_identifier(self) -> None:
        item = family("sensitive-looking-family-id", (1, 1, 1, 1, 1))
        self.assertNotIn("sensitive-looking-family-id", repr(item))


class GroupedFoldTests(unittest.TestCase):
    def test_is_order_independent_balanced_and_family_disjoint(self) -> None:
        families = tuple(
            family(
                f"opaque-{index:02d}",
                tuple(
                    ((index * (state_index + 2) + state_index) % 7) + 1
                    for state_index in range(len(V3_STATES))
                ),
            )
            for index in range(30)
        )
        first = build_grouped_folds(
            families,
            fold_count=PRIMARY_OUTER_FOLD_COUNT,
            domain="balance-test-v1",
        )
        reversed_result = build_grouped_folds(
            reversed(families),
            fold_count=PRIMARY_OUTER_FOLD_COUNT,
            domain="balance-test-v1",
        )

        self.assertEqual(
            [fold.validation_family_ids for fold in first],
            [fold.validation_family_ids for fold in reversed_result],
        )
        self.assertEqual([6, 6, 6, 6, 6], [len(fold.validation_family_ids) for fold in first])
        token_loads = [sum(fold.validation_state_support) for fold in first]
        self.assertLessEqual(max(token_loads) - min(token_loads), 8)

        all_family_ids = {item.family_id for item in families}
        validation_memberships: list[str] = []
        for fold in first:
            self.assertFalse(set(fold.train_family_ids) & set(fold.validation_family_ids))
            self.assertEqual(
                all_family_ids,
                set(fold.train_family_ids) | set(fold.validation_family_ids),
            )
            self.assertTrue(all(count > 0 for count in fold.train_state_support))
            self.assertTrue(all(count > 0 for count in fold.validation_state_support))
            validation_memberships.extend(fold.validation_family_ids)
        self.assertCountEqual(all_family_ids, validation_memberships)

    def test_domain_separator_changes_the_equal_support_ranking(self) -> None:
        families = tuple(family(f"opaque-{index:02d}", (1, 1, 1, 1, 1)) for index in range(10))
        first = build_grouped_folds(
            families,
            fold_count=PRIMARY_OUTER_FOLD_COUNT,
            domain="domain-a-v1",
        )
        second = build_grouped_folds(
            families,
            fold_count=PRIMARY_OUTER_FOLD_COUNT,
            domain="domain-b-v1",
        )
        self.assertNotEqual(
            [fold.validation_family_ids for fold in first],
            [fold.validation_family_ids for fold in second],
        )

    def test_fails_closed_when_any_state_has_too_few_supporting_families(self) -> None:
        families: list[FamilySupport] = []
        for state_index in range(len(V3_STATES)):
            support_count = 4 if state_index == len(V3_STATES) - 1 else 5
            for replicate in range(support_count):
                counts = [0] * len(V3_STATES)
                counts[state_index] = 1
                families.append(
                    family(
                        f"opaque-{state_index}-{replicate}",
                        tuple(counts),
                    )
                )
        with self.assertRaisesRegex(V3FoldError, "at least fold_count"):
            build_grouped_folds(
                families,
                fold_count=PRIMARY_OUTER_FOLD_COUNT,
                domain="support-failure-v1",
            )

    def test_rejects_duplicate_families_bad_fold_counts_and_bad_domains(self) -> None:
        item = family("opaque", (1, 1, 1, 1, 1))
        with self.assertRaisesRegex(V3FoldError, "unique"):
            build_grouped_folds(
                [item, item],
                fold_count=2,
                domain="duplicate-test-v1",
            )
        with self.assertRaisesRegex(V3FoldError, "at least two"):
            build_grouped_folds(
                [item],
                fold_count=1,
                domain="fold-count-test-v1",
            )
        with self.assertRaisesRegex(V3FoldError, "printable ASCII"):
            build_grouped_folds(
                [item],
                fold_count=2,
                domain="bad domain",
            )


class NestedGroupedFoldTests(unittest.TestCase):
    def test_builds_fixed_five_by_four_sparse_support_plan(self) -> None:
        families = sparse_primary_families()
        plan = build_nested_grouped_folds(families)
        reversed_plan = build_nested_grouped_folds(reversed(families))

        self.assertEqual(PRIMARY_OUTER_FOLD_COUNT, len(plan.outer_folds))
        self.assertEqual(plan_membership(plan), plan_membership(reversed_plan))
        all_family_ids = {item.family_id for item in families}
        outer_validation_memberships: list[str] = []
        for nested in plan.outer_folds:
            outer = nested.outer
            self.assertEqual(PRIMARY_INNER_FOLD_COUNT, len(nested.inner_folds))
            self.assertTrue(all(count > 0 for count in outer.train_state_support))
            self.assertTrue(all(count > 0 for count in outer.validation_state_support))
            outer_validation_memberships.extend(outer.validation_family_ids)

            inner_validation_memberships: list[str] = []
            outer_train_ids = set(outer.train_family_ids)
            outer_validation_ids = set(outer.validation_family_ids)
            for inner in nested.inner_folds:
                self.assertFalse(
                    outer_validation_ids
                    & (set(inner.train_family_ids) | set(inner.validation_family_ids))
                )
                self.assertEqual(
                    outer_train_ids,
                    set(inner.train_family_ids) | set(inner.validation_family_ids),
                )
                self.assertTrue(all(count > 0 for count in inner.train_state_support))
                self.assertTrue(all(count > 0 for count in inner.validation_state_support))
                inner_validation_memberships.extend(inner.validation_family_ids)
            self.assertCountEqual(outer_train_ids, inner_validation_memberships)
        self.assertCountEqual(all_family_ids, outer_validation_memberships)

    def test_report_facing_summaries_and_repr_omit_family_ids(self) -> None:
        plan = build_nested_grouped_folds(sparse_primary_families())
        rendered = repr(plan)
        summaries = plan.support_summaries()

        self.assertNotIn("opaque-family", rendered)
        self.assertNotIn("opaque-family", repr(summaries))
        self.assertEqual(PRIMARY_OUTER_FOLD_COUNT, len(summaries))
        for summary in summaries:
            self.assertEqual(5, summary.outer.validation_family_count)
            self.assertEqual(PRIMARY_INNER_FOLD_COUNT, len(summary.inner_folds))


class OneStandardErrorTests(unittest.TestCase):
    def test_summarizes_scores_and_selects_the_simplest_eligible_candidate(self) -> None:
        best = CandidateScore(
            candidate_id="crf",
            complexity_rank=2,
            fold_scores=(0.80, 0.82, 0.84, 0.82, 0.82),
        )
        simpler = CandidateScore(
            candidate_id="hmm",
            complexity_rank=0,
            fold_scores=(0.815, 0.815, 0.815, 0.815, 0.815),
        )
        ineligible = CandidateScore(
            candidate_id="majority",
            complexity_rank=0,
            fold_scores=(0.79, 0.80, 0.81, 0.80, 0.80),
        )

        summary = summarize_scores(best.fold_scores)
        self.assertAlmostEqual(0.82, summary.mean)
        self.assertGreater(summary.standard_error, 0.0)
        self.assertEqual(5, summary.fold_count)
        self.assertEqual(
            "hmm",
            select_one_standard_error([ineligible, best, simpler]).candidate_id,
        )

    def test_uses_ascii_candidate_id_as_the_final_tie_break(self) -> None:
        alpha = CandidateScore("alpha", 0, (0.8, 0.8))
        beta = CandidateScore("beta", 0, (0.8, 0.8))
        self.assertEqual("alpha", select_one_standard_error([beta, alpha]).candidate_id)

    def test_rejects_invalid_or_duplicate_candidate_scores(self) -> None:
        with self.assertRaisesRegex(V3FoldError, "at least two"):
            summarize_scores([0.5])
        with self.assertRaisesRegex(V3FoldError, "finite"):
            summarize_scores([0.5, math.nan])
        with self.assertRaisesRegex(V3FoldError, "immutable tuple"):
            CandidateScore("mutable", 0, [0.5, 0.6])  # type: ignore[arg-type]
        duplicate_a = CandidateScore("same", 0, (0.5, 0.6))
        duplicate_b = CandidateScore("same", 1, (0.6, 0.7))
        with self.assertRaisesRegex(V3FoldError, "unique"):
            select_one_standard_error([duplicate_a, duplicate_b])


if __name__ == "__main__":
    unittest.main()
