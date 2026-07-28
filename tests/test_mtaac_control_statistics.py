# pyright: reportPrivateUsage=false

from __future__ import annotations

import math
import unittest
from collections import Counter, defaultdict
from typing import Any, Literal
from unittest.mock import patch

import indusbench.mtaac_control as control
from indusbench.mtaac import (
    MTAAC_COLUMNS,
    MTAAC_GOLD_CLASSES,
    GoldClass,
    parse_mtaac_directory,
)


def _features(opaque_form_id: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            feature_name,
            opaque_form_id if feature_name == "opaque_form_id" else f"fixture:{feature_name}",
        )
        for feature_name in control.FULL_FEATURES
    )


def _example(
    gold_class: GoldClass,
    *,
    index: int,
    weight: float = 1.0,
    opaque_form_id: str = "fixture:shared-form",
) -> control._Example:
    return control._Example(
        document_key=f"fixture-document-{index}",
        observation_key=f"fixture-observation-{index}",
        replica_index=0,
        line_ordinal=0,
        model_order=index,
        token_key=f"fixture-token-{index}",
        features=_features(opaque_form_id),
        true_class=gold_class,
        weight=weight,
    )


def _observed_document(
    document_key: str,
    *,
    partition: Literal["train", "test"],
    replica_index: int,
) -> control.MTAACObservedDocument:
    tokens = tuple(
        control.MTAACObservedToken(
            token_key=f"{document_key}-token-{index}",
            observed_form_id=f"fixture-form-{index}",
            source_order=index,
            visual_index=index,
            pseudo_variant_applied=False,
            damaged=False,
        )
        for index in range(2)
    )
    return control.MTAACObservedDocument(
        observation_key=f"{document_key}-replica-{replica_index}",
        document_key=document_key,
        partition=partition,
        replica_index=replica_index,
        lines=(
            control.MTAACObservedLine(
                line_ordinal=0,
                reported_direction="known_source_order",
                visual_reversed=False,
                tokens=tokens,
            ),
        ),
    )


def _degraded_family_weight_fixture(
    partition: Literal["train", "test"],
) -> tuple[
    control.MTAACDegradedCorpus,
    dict[str, GoldClass | None],
    set[tuple[str, int]],
]:
    observations = (
        _observed_document("family-one-replica", partition=partition, replica_index=0),
        _observed_document("family-two-replicas", partition=partition, replica_index=0),
        _observed_document("family-two-replicas", partition=partition, replica_index=1),
    )
    truth: dict[str, GoldClass | None] = {}
    for document_key in ("family-one-replica", "family-two-replicas"):
        truth[f"{document_key}-token-0"] = "quantity"
        truth[f"{document_key}-token-1"] = "unit"
    return (
        control.MTAACDegradedCorpus(
            protocol_version=control.MTAAC_CONTROL_PROTOCOL_VERSION,
            seed=0,
            regime=control.CLEAN_REGIME,
            split_manifest_sha256="sha256:" + "0" * 64,
            observations=observations,
        ),
        truth,
        {
            ("family-one-replica", 0),
            ("family-two-replicas", 0),
        },
    )


def _conll_document(
    p_identifier: str,
    rows: tuple[tuple[str, str, str, str], ...],
) -> bytes:
    token_rows = [
        "\t".join((position, form, segm, xpostag, "_", "_", "_"))
        for position, form, segm, xpostag in rows
    ]
    return (
        "\n".join(
            (
                f"#new_text={p_identifier}",
                "# " + "\t".join(MTAAC_COLUMNS),
                *token_rows,
                "",
            )
        )
    ).encode()


def _permutation_family_examples(
    document_key: str,
    labels: tuple[GoldClass, ...],
    *,
    replica_count: int,
) -> list[control._Example]:
    weight = 1.0 / (len(labels) * replica_count)
    return [
        control._Example(
            document_key=document_key,
            observation_key=f"{document_key}-replica-{replica_index}",
            replica_index=replica_index,
            line_ordinal=0,
            model_order=model_order,
            token_key=f"{document_key}-token-{model_order}",
            features=_features(f"{document_key}-form-{model_order}"),
            true_class=gold_class,
            weight=weight,
        )
        for replica_index in range(replica_count)
        for model_order, gold_class in enumerate(labels)
    ]


def _decision_regime(
    *,
    macro_f1: float,
    delta: float,
    recall: float,
    coverage: float,
    permutation_p: float | None = None,
    movable_fraction: float | None = None,
) -> dict[str, Any]:
    regime: dict[str, Any] = {
        "observed": {
            "macro_f1": macro_f1,
            "per_class": {
                gold_class: {
                    "recall": recall,
                    "family_mean_readable_coverage": coverage,
                }
                for gold_class in MTAAC_GOLD_CLASSES
            },
        },
        "observed_minus_decision_reference": delta,
    }
    if permutation_p is not None and movable_fraction is not None:
        regime["permutation_null"] = {
            "add_one_empirical_p_greater_or_equal": permutation_p,
            "movable_family_weight_fraction": movable_fraction,
        }
    return regime


class FamilyWeightingTests(unittest.TestCase):
    def test_each_family_has_total_weight_one_regardless_of_replica_count(self) -> None:
        for partition in ("train", "test"):
            with self.subTest(partition=partition):
                degraded, truth, primary_lines = _degraded_family_weight_fixture(partition)
                examples, support = control._examples_for_partition(
                    degraded,
                    truth,
                    primary_lines,
                    partition=partition,
                )
                totals: dict[str, float] = defaultdict(float)
                weights: dict[str, set[float]] = defaultdict(set)
                for example in examples:
                    totals[example.document_key] += example.weight
                    weights[example.document_key].add(example.weight)

                self.assertEqual(set(totals), {"family-one-replica", "family-two-replicas"})
                self.assertTrue(
                    all(
                        math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12)
                        for total in totals.values()
                    )
                )
                self.assertEqual(weights["family-one-replica"], {0.5})
                self.assertEqual(weights["family-two-replicas"], {0.25})
                self.assertEqual(support["quantity"], 2)
                self.assertEqual(support["unit"], 2)


class PrimaryStratumAndCoverageTests(unittest.TestCase):
    def test_primary_lines_exclude_only_exact_train_sequences(self) -> None:
        train_identifier = "P910001"
        test_identifier = "P910002"
        corpus = parse_mtaac_directory(
            {
                f"fixture/morph/to_dict/{train_identifier}.conll": _conll_document(
                    train_identifier,
                    (
                        ("o.1.1", "FORM_A", "context", "N"),
                        ("o.1.2", "FORM_B", "context", "N"),
                    ),
                ),
                f"fixture/morph/to_dict/{test_identifier}.conll": _conll_document(
                    test_identifier,
                    (
                        ("o.1.1", "FORM_A", "context", "N"),
                        ("o.1.2", "FORM_B", "context", "N"),
                        ("o.2.1", "FORM_B", "context", "N"),
                        ("o.2.2", "FORM_A", "context", "N"),
                        ("o.3.1", "FORM_A", "context", "N"),
                        ("o.3.2", "FORM_B", "context", "N"),
                        ("o.3.3", "FORM_C", "context", "N"),
                    ),
                ),
            }
        )
        document_key_by_identifier = {
            document.p_identifier: document.document_key for document in corpus.gold_documents
        }
        split = control.MTAACSplitManifest(
            seed=0,
            test_fraction=0.5,
            entries=(
                control.MTAACSplitEntry(
                    document_key=document_key_by_identifier[train_identifier],
                    cluster_identifier="fixture-train-cluster",
                    partition="train",
                ),
                control.MTAACSplitEntry(
                    document_key=document_key_by_identifier[test_identifier],
                    cluster_identifier="fixture-test-cluster",
                    partition="test",
                ),
            ),
            manifest_sha256="sha256:" + "0" * 64,
        )

        primary_lines = control._primary_line_membership(corpus, split)
        test_key = document_key_by_identifier[test_identifier]
        self.assertNotIn((test_key, 0), primary_lines)
        self.assertEqual(primary_lines, {(test_key, 1), (test_key, 2)})

    def test_coverage_uses_predegradation_denominator_and_ignores_replicas(self) -> None:
        p_identifier = "P920001"
        corpus = parse_mtaac_directory(
            {
                f"fixture/morph/to_dict/{p_identifier}.conll": _conll_document(
                    p_identifier,
                    tuple(
                        (f"o.1.{index + 1}", f"QUANTITY_{index}", "one", "NU") for index in range(4)
                    ),
                )
            }
        )
        model_document = corpus.model_documents[0]
        document_key = model_document.document_key
        retained_tokens = (
            control.MTAACObservedToken(
                token_key=model_document.tokens[0].token_key,
                observed_form_id=model_document.tokens[0].sign_id,
                source_order=0,
                visual_index=0,
                pseudo_variant_applied=False,
                damaged=False,
            ),
            control.MTAACObservedToken(
                token_key=model_document.tokens[1].token_key,
                observed_form_id=None,
                source_order=1,
                visual_index=1,
                pseudo_variant_applied=False,
                damaged=True,
            ),
        )
        line = control.MTAACObservedLine(
            line_ordinal=0,
            reported_direction="known_source_order",
            visual_reversed=False,
            tokens=retained_tokens,
        )
        truth = control._truth_by_token(corpus)
        primary_lines = {(document_key, 0)}

        coverage_values = []
        for replica_count in (1, 2):
            degraded = control.MTAACDegradedCorpus(
                protocol_version=control.MTAAC_CONTROL_PROTOCOL_VERSION,
                seed=0,
                regime=control.MILD_REGIME,
                split_manifest_sha256="sha256:" + "0" * 64,
                observations=tuple(
                    control.MTAACObservedDocument(
                        observation_key=f"coverage-replica-{replica_index}",
                        document_key=document_key,
                        partition="test",
                        replica_index=replica_index,
                        lines=(line,),
                    )
                    for replica_index in range(replica_count)
                ),
            )
            coverage = control._coverage(
                corpus,
                degraded,
                primary_lines,
                truth,
            )
            coverage_values.append(coverage["quantity"])
            self.assertIsNone(coverage["unit"])
            self.assertIsNone(coverage["person_name"])
            self.assertIsNone(coverage["settlement_name"])

        self.assertEqual(coverage_values, [0.25, 0.25])


class NaiveBayesContractTests(unittest.TestCase):
    def test_prior_likelihood_and_reserved_unseen_bucket_are_exact(self) -> None:
        model = control._CategoricalNaiveBayes(("opaque_form_id",)).fit(
            (
                _example(
                    "quantity",
                    index=0,
                    weight=2.0,
                    opaque_form_id="fixture:q",
                ),
                _example(
                    "unit",
                    index=1,
                    weight=1.0,
                    opaque_form_id="fixture:u",
                ),
            )
        )
        real_log = math.log
        expected_unseen_arguments = [
            3.0 / 7.0,
            1.0 / 5.0,
            2.0 / 7.0,
            1.0 / 4.0,
            1.0 / 7.0,
            1.0 / 3.0,
            1.0 / 7.0,
            1.0 / 3.0,
        ]
        with patch(
            "indusbench.mtaac_control.math.log",
            side_effect=real_log,
        ) as log_mock:
            prediction = model.predict(_features("fixture:unseen"))
        self.assertEqual(prediction, "quantity")
        self.assertEqual(
            [call.args[0] for call in log_mock.call_args_list],
            expected_unseen_arguments,
        )

        with patch(
            "indusbench.mtaac_control.math.log",
            side_effect=real_log,
        ) as log_mock:
            model.predict(_features("fixture:q"))
        self.assertEqual(log_mock.call_args_list[1].args[0], 3.0 / 5.0)

    def test_exact_score_tie_uses_fixed_first_class(self) -> None:
        model = control._CategoricalNaiveBayes(("opaque_form_id",)).fit(
            tuple(
                _example(
                    gold_class,
                    index=index,
                    opaque_form_id="fixture:shared",
                )
                for index, gold_class in enumerate(MTAAC_GOLD_CLASSES)
            )
        )
        self.assertEqual(model.predict(_features("fixture:shared")), "quantity")


class NullDistributionTests(unittest.TestCase):
    def test_p95_uses_linear_interpolation(self) -> None:
        self.assertAlmostEqual(
            control._percentile_95((0.1, 0.2, 0.9), required_runs=3),
            0.83,
        )

    def test_add_one_p_counts_values_equal_to_observed(self) -> None:
        train = [_example("quantity", index=0)]
        test = [_example("quantity", index=1)]
        metrics = (
            {"macro_f1": 0.5},
            {"macro_f1": 0.6},
            {"macro_f1": 0.7},
        )
        with (
            patch.object(
                control,
                "_permuted_training_labels",
                return_value=(["quantity"], 0, 1.0),
            ),
            patch.object(control, "_model_metrics", side_effect=metrics),
        ):
            null = control._permutation_null(
                train,
                test,
                effective_families={gold_class: 1 for gold_class in MTAAC_GOLD_CLASSES},
                coverage={gold_class: 1.0 for gold_class in MTAAC_GOLD_CLASSES},
                observed_macro_f1=0.6,
                runs=3,
                seed_start=0,
            )
        self.assertEqual(null["add_one_empirical_p_greater_or_equal"], 0.75)
        self.assertAlmostEqual(null["macro_f1"]["p95"], 0.69)


class DocumentVectorPermutationTests(unittest.TestCase):
    def test_vectors_move_only_within_equal_r_and_are_identical_across_replicas(
        self,
    ) -> None:
        family_contract = {
            "r2-two-replicas": (("quantity", "unit"), 2),
            "r2-one-replica": (("person_name", "settlement_name"), 1),
            "r3-two-replicas": (("quantity", "quantity", "unit"), 2),
            "r3-one-replica": (
                ("person_name", "settlement_name", "settlement_name"),
                1,
            ),
        }
        examples: list[control._Example] = []
        replica_counts: dict[str, int] = {}
        for document_key, (labels, replica_count) in family_contract.items():
            examples.extend(
                _permutation_family_examples(
                    document_key,
                    labels,
                    replica_count=replica_count,
                )
            )
            replica_counts[document_key] = replica_count

        permuted_labels, fixed_points, movable_fraction = control._permuted_training_labels(
            examples, run_seed=0
        )
        self.assertEqual(movable_fraction, 1.0)
        self.assertGreaterEqual(fixed_points, 0)
        self.assertLessEqual(fixed_points, len(family_contract))

        original_vectors = {
            document_key: tuple(
                example.true_class
                for example in sorted(
                    (
                        row
                        for row in examples
                        if row.document_key == document_key and row.replica_index == 0
                    ),
                    key=lambda row: row.model_order,
                )
            )
            for document_key in family_contract
        }
        assigned_by_replica: dict[tuple[str, int], list[tuple[int, GoldClass]]] = defaultdict(list)
        for example, permuted_label in zip(examples, permuted_labels, strict=True):
            assigned_by_replica[(example.document_key, example.replica_index)].append(
                (example.model_order, permuted_label)
            )
        assigned_vectors = {
            key: tuple(label for _, label in sorted(indexed_labels, key=lambda item: item[0]))
            for key, indexed_labels in assigned_by_replica.items()
        }

        for document_key, replica_count in replica_counts.items():
            representative = assigned_vectors[(document_key, 0)]
            self.assertIn(
                representative,
                {
                    vector
                    for vector in original_vectors.values()
                    if len(vector) == len(original_vectors[document_key])
                },
            )
            for replica_index in range(1, replica_count):
                self.assertEqual(
                    assigned_vectors[(document_key, replica_index)],
                    representative,
                )

        for readable_count in (2, 3):
            original_in_stratum = Counter(
                vector for vector in original_vectors.values() if len(vector) == readable_count
            )
            assigned_in_stratum = Counter(
                assigned_vectors[(document_key, 0)]
                for document_key, vector in original_vectors.items()
                if len(vector) == readable_count
            )
            self.assertEqual(assigned_in_stratum, original_in_stratum)


class SupportAndDecisionBoundaryTests(unittest.TestCase):
    def test_support_minima_are_inclusive(self) -> None:
        supports: dict[str, dict[GoldClass, int]] = {
            "mild_train": {gold_class: 40 for gold_class in MTAAC_GOLD_CLASSES},
            "mild_test_primary": {gold_class: 20 for gold_class in MTAAC_GOLD_CLASSES},
        }
        coverage: dict[str, dict[GoldClass, float | None]] = {
            regime: {gold_class: 0.0 for gold_class in MTAAC_GOLD_CLASSES}
            for regime in ("clean", "mild")
        }
        truth_rows = [
            _example(gold_class, index=index) for index, gold_class in enumerate(MTAAC_GOLD_CLASSES)
        ]
        examples = {
            "clean": ([], truth_rows),
            "mild": ([], truth_rows),
        }

        passed, criteria = control._decision_support_passes(
            supports,
            coverage,
            examples,
        )
        self.assertTrue(passed)
        self.assertTrue(all(criteria.values()))

        supports["mild_train"]["quantity"] = 39
        passed, criteria = control._decision_support_passes(
            supports,
            coverage,
            examples,
        )
        self.assertFalse(passed)
        self.assertFalse(criteria["mild_train_effective_families"])

    def test_decision_thresholds_are_inclusive_and_support_integrity_are_binding(
        self,
    ) -> None:
        clean = _decision_regime(
            macro_f1=0.60,
            delta=0.10,
            recall=0.35,
            coverage=0.95,
        )
        mild = _decision_regime(
            macro_f1=0.60,
            delta=0.10,
            recall=0.35,
            coverage=0.75,
            permutation_p=0.05,
            movable_fraction=0.80,
        )
        decision = control.apply_mtaac_control_decision(
            clean,
            mild,
            support_passed=True,
            integrity_passed=True,
        )
        self.assertTrue(decision["all_thresholds_passed"])
        self.assertTrue(all(decision["clean_criteria"].values()))
        self.assertTrue(all(decision["mild_criteria"].values()))

        for support_passed, integrity_passed, failed_criterion in (
            (False, True, "decision_bearing_support"),
            (True, False, "all_integrity_and_leakage_checks"),
        ):
            with self.subTest(failed_criterion=failed_criterion):
                decision = control.apply_mtaac_control_decision(
                    clean,
                    mild,
                    support_passed=support_passed,
                    integrity_passed=integrity_passed,
                )
                self.assertFalse(decision["all_thresholds_passed"])
                self.assertFalse(decision["mild_criteria"][failed_criterion])


class DiagnosticNonbindingTests(unittest.TestCase):
    def test_empty_harsh_training_is_unavailable_and_nonbinding(self) -> None:
        test_examples = [
            _example(gold_class, index=index) for index, gold_class in enumerate(MTAAC_GOLD_CLASSES)
        ]
        diagnostic = control._diagnostic_regime_score(
            [],
            test_examples,
            test_support={gold_class: 1 for gold_class in MTAAC_GOLD_CLASSES},
            coverage={gold_class: 1.0 for gold_class in MTAAC_GOLD_CLASSES},
        )
        self.assertFalse(diagnostic["aggregate_available"])
        self.assertFalse(diagnostic["can_change_overall_outcome"])
        self.assertNotIn("observed", diagnostic)


if __name__ == "__main__":
    unittest.main()
