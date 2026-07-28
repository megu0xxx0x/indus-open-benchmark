from __future__ import annotations

import hashlib
import json
import math
import re
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from indusbench.schema_validation import validate_schema_instance
from indusbench.v5dev.plan import V5_DEVELOPMENT_PLAN_SHA256
from indusbench.v5dev_cli import validate_public_development_report

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmark/results/mtaac-v5-development-v1.json"
SCHEMA = ROOT / "schemas/mtaac-v5-development-report.schema.json"
RESULT_SHA256 = "9b60b9eb6006efc35cdca90e91fdb07c356a09becc2a1d300ef22ec16393e88f"
IMPLEMENTATION_COMMIT = "b0be18d7c317d276dfefd1237c17ec0be6886cd0"
COMPARISON_TOLERANCE = 1e-12
STATES = (
    "context_only",
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
)
V4_MILD_MACRO_F1_BY_FOLD = (
    0.3756051787768944,
    0.3998966341462856,
    0.3615261061386301,
    0.39294354710818963,
    0.39901832092281697,
)
V4_MILD_UNIT_RECALL_BY_FOLD = (
    0.18225197064754597,
    0.2892249319203195,
    0.2772641078805165,
    0.39686535349113794,
    0.35585102688488385,
)
V4_MILD_SETTLEMENT_RECALL_BY_FOLD = (
    0.0,
    0.09932569269976571,
    0.003780194718492515,
    0.06366234989790896,
    0.05568829861391914,
)


def _recompute_metrics(
    confusion: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    truth_mass = {
        truth: math.fsum(float(confusion[truth][predicted]) for predicted in STATES)
        for truth in STATES
    }
    predicted_mass = {
        predicted: math.fsum(float(confusion[truth][predicted]) for truth in STATES)
        for predicted in STATES
    }
    per_state: dict[str, dict[str, float]] = {}
    for state in STATES:
        true_positive = float(confusion[state][state])
        precision = true_positive / predicted_mass[state] if predicted_mass[state] > 0.0 else 0.0
        recall = true_positive / truth_mass[state] if truth_mass[state] > 0.0 else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall > 0.0 else 0.0
        per_state[state] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "truth_mass": truth_mass[state],
            "predicted_mass": predicted_mass[state],
        }

    total_mass = math.fsum(truth_mass.values())
    recalls = [per_state[state]["recall"] for state in STATES]
    f1_values = [per_state[state]["f1"] for state in STATES]
    return {
        "weighted_accuracy": (
            math.fsum(float(confusion[state][state]) for state in STATES) / total_mass
        ),
        "balanced_accuracy": math.fsum(recalls) / len(STATES),
        "macro_f1": math.fsum(f1_values) / len(STATES),
        "worst_state_recall": min(recalls),
        "total_family_mass": total_mass,
        "per_state": per_state,
    }


def _sum_confusions(
    confusions: Sequence[Mapping[str, Mapping[str, float]]],
) -> dict[str, dict[str, float]]:
    return {
        truth: {
            predicted: math.fsum(float(confusion[truth][predicted]) for confusion in confusions)
            for predicted in STATES
        }
        for truth in STATES
    }


def _all_mapping_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return set(value) | {
            nested for nested_value in value.values() for nested in _all_mapping_keys(nested_value)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {nested for nested_value in value for nested in _all_mapping_keys(nested_value)}
    return set()


class MTAACV5PublishedDevelopmentResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = RESULT.read_bytes()
        if hashlib.sha256(cls.raw).hexdigest() != RESULT_SHA256:
            raise AssertionError("published MTAAC V5 development result bytes changed")
        cls.report: dict[str, Any] = json.loads(cls.raw)

    def assertFloatEqual(self, expected: float, actual: object) -> None:
        if not isinstance(actual, int | float):
            self.fail(f"{actual!r} is not numeric")
        self.assertTrue(
            math.isclose(expected, float(actual), rel_tol=0.0, abs_tol=1e-12),
            f"{actual!r} != {expected!r}",
        )

    def assertMetricReportRecomputed(self, metrics: Mapping[str, Any]) -> dict[str, Any]:
        self.assertEqual(list(STATES), metrics["states"])
        confusion = metrics["weighted_confusion_matrix"]
        self.assertEqual(set(STATES), set(confusion))
        for truth in STATES:
            self.assertEqual(set(STATES), set(confusion[truth]))
            for predicted in STATES:
                self.assertGreaterEqual(float(confusion[truth][predicted]), 0.0)

        expected = _recompute_metrics(confusion)
        for name in (
            "weighted_accuracy",
            "balanced_accuracy",
            "macro_f1",
            "worst_state_recall",
            "total_family_mass",
        ):
            self.assertFloatEqual(expected[name], metrics[name])
        self.assertEqual(set(STATES), set(metrics["per_state"]))
        for state in STATES:
            for name in ("precision", "recall", "f1", "truth_mass", "predicted_mass"):
                self.assertFloatEqual(
                    expected["per_state"][state][name],
                    metrics["per_state"][state][name],
                )
        return expected

    def test_result_bytes_schema_plan_commit_and_runtime_boundary_are_fixed(self) -> None:
        self.assertEqual(59053, len(self.raw))
        self.assertEqual([], validate_schema_instance(self.report, SCHEMA))
        self.assertIs(
            self.report,
            validate_public_development_report(
                self.report,
                expected_implementation_commit=IMPLEMENTATION_COMMIT,
            ),
        )
        self.assertEqual(
            "sha256:3c4a7c733218fcd0c4e6e25fbd59e5b86c1fd589512e9a88bb243b1d036c10f1",
            V5_DEVELOPMENT_PLAN_SHA256,
        )
        self.assertEqual(V5_DEVELOPMENT_PLAN_SHA256, self.report["plan_sha256"])
        self.assertEqual(IMPLEMENTATION_COMMIT, self.report["implementation_commit"])
        self.assertEqual(
            "sha256:4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897",
            self.report["parent_commitments"]["v4_result_sha256"],
        )
        self.assertTrue(self.report["development_only"])
        self.assertTrue(self.report["model_executed"])
        self.assertTrue(self.report["scientific_metrics_emitted"])
        self.assertTrue(self.report["mtaac_retired"])
        boundary = self.report["data_boundary"]
        self.assertEqual(271, boundary["model_training_family_count"])
        self.assertEqual(90, boundary["v2_holdout_family_count_excluded"])
        self.assertTrue(boundary["mtaac_final_attempt"])
        self.assertFalse(boundary["v2_holdout_exposed_to_model"])
        self.assertFalse(boundary["v2_holdout_scored"])
        self.assertFalse(boundary["reserved_validation_source_loaded"])

    def test_every_fold_and_oof_metric_is_independently_recomputed(self) -> None:
        outer = self.report["outer_development"]
        folds = outer["outer_folds"]
        self.assertEqual(5, outer["outer_fold_count"])
        self.assertEqual(5, len(folds))
        self.assertEqual(list(range(5)), [fold["outer_fold_index"] for fold in folds])
        self.assertEqual(
            271,
            sum(int(fold["support"]["validation_family_count"]) for fold in folds),
        )

        by_regime: dict[str, list[Mapping[str, Mapping[str, float]]]] = {
            "clean": [],
            "mild": [],
        }
        for fold in folds:
            support = fold["support"]
            self.assertEqual(
                271,
                support["train_family_count"] + support["validation_family_count"],
            )
            self.assertTrue(fold["optimizer"]["converged"])
            self.assertLessEqual(fold["optimizer"]["accepted_iterations"], 100)
            for regime in ("clean", "mild"):
                metrics = fold["metrics"][regime]
                expected = self.assertMetricReportRecomputed(metrics)
                self.assertFloatEqual(
                    float(support["validation_family_count"]),
                    expected["total_family_mass"],
                )
                by_regime[regime].append(metrics["weighted_confusion_matrix"])

        for regime in ("clean", "mild"):
            reported_oof = outer["out_of_fold_metrics"][regime]
            summed = _sum_confusions(by_regime[regime])
            for truth in STATES:
                for predicted in STATES:
                    self.assertFloatEqual(
                        summed[truth][predicted],
                        reported_oof["weighted_confusion_matrix"][truth][predicted],
                    )
            expected_oof = self.assertMetricReportRecomputed(reported_oof)
            self.assertFloatEqual(271.0, expected_oof["total_family_mass"])

        mild = outer["out_of_fold_metrics"]["mild"]
        clean = outer["out_of_fold_metrics"]["clean"]
        self.assertFloatEqual(0.3845528260429222, mild["macro_f1"])
        self.assertFloatEqual(0.47849819036965213, clean["macro_f1"])
        self.assertFloatEqual(
            0.29369010585463745,
            mild["per_state"]["unit"]["recall"],
        )
        self.assertFloatEqual(
            0.05746555180505497,
            mild["per_state"]["settlement_name"]["recall"],
        )

    def test_paired_v4_vectors_deltas_and_strict_counts_are_recomputed(self) -> None:
        folds = self.report["outer_development"]["outer_folds"]
        paired = self.report["outer_development"]["paired_v4"]
        self.assertEqual(
            list(V4_MILD_MACRO_F1_BY_FOLD),
            paired["v4_mild_macro_f1_by_outer_fold"],
        )
        self.assertEqual(
            list(V4_MILD_UNIT_RECALL_BY_FOLD),
            paired["v4_mild_unit_recall_by_outer_fold"],
        )
        self.assertEqual(
            list(V4_MILD_SETTLEMENT_RECALL_BY_FOLD),
            paired["v4_mild_settlement_name_recall_by_outer_fold"],
        )

        v5_macro = [
            _recompute_metrics(fold["metrics"]["mild"]["weighted_confusion_matrix"])["macro_f1"]
            for fold in folds
        ]
        v5_unit = [
            _recompute_metrics(fold["metrics"]["mild"]["weighted_confusion_matrix"])["per_state"][
                "unit"
            ]["recall"]
            for fold in folds
        ]
        v5_settlement = [
            _recompute_metrics(fold["metrics"]["mild"]["weighted_confusion_matrix"])["per_state"][
                "settlement_name"
            ]["recall"]
            for fold in folds
        ]
        vector_specs = (
            (
                v5_macro,
                V4_MILD_MACRO_F1_BY_FOLD,
                "v5_mild_macro_f1_by_outer_fold",
                "mild_macro_f1_delta_by_outer_fold",
                "positive_mild_macro_f1_delta_fold_count",
            ),
            (
                v5_unit,
                V4_MILD_UNIT_RECALL_BY_FOLD,
                "v5_mild_unit_recall_by_outer_fold",
                "mild_unit_recall_delta_by_outer_fold",
                "positive_mild_unit_recall_delta_fold_count",
            ),
            (
                v5_settlement,
                V4_MILD_SETTLEMENT_RECALL_BY_FOLD,
                "v5_mild_settlement_name_recall_by_outer_fold",
                "mild_settlement_name_recall_delta_by_outer_fold",
                "positive_mild_settlement_name_recall_delta_fold_count",
            ),
        )
        expected_counts: dict[str, int] = {}
        for current, baseline, current_key, delta_key, count_key in vector_specs:
            deltas = [
                observed - reference for observed, reference in zip(current, baseline, strict=True)
            ]
            for expected, actual in zip(current, paired[current_key], strict=True):
                self.assertFloatEqual(expected, actual)
            for expected, actual in zip(deltas, paired[delta_key], strict=True):
                self.assertFloatEqual(expected, actual)
            expected_counts[count_key] = sum(delta > COMPARISON_TOLERANCE for delta in deltas)
            self.assertEqual(expected_counts[count_key], paired[count_key])

        self.assertEqual(
            {
                "positive_mild_macro_f1_delta_fold_count": 1,
                "positive_mild_unit_recall_delta_fold_count": 0,
                "positive_mild_settlement_name_recall_delta_fold_count": 3,
            },
            expected_counts,
        )

    def test_all_fifteen_gates_terminal_state_and_no_final_fit_are_recomputed(self) -> None:
        outer = self.report["outer_development"]
        folds = outer["outer_folds"]
        clean = _recompute_metrics(
            outer["out_of_fold_metrics"]["clean"]["weighted_confusion_matrix"]
        )
        mild = _recompute_metrics(outer["out_of_fold_metrics"]["mild"]["weighted_confusion_matrix"])
        paired = outer["paired_v4"]
        unit_by_fold = [
            _recompute_metrics(fold["metrics"]["mild"]["weighted_confusion_matrix"])["per_state"][
                "unit"
            ]["recall"]
            for fold in folds
        ]
        settlement_by_fold = [
            _recompute_metrics(fold["metrics"]["mild"]["weighted_confusion_matrix"])["per_state"][
                "settlement_name"
            ]["recall"]
            for fold in folds
        ]
        gate_specs: tuple[tuple[tuple[str, ...], float | int, float | int], ...] = (
            (("clean_macro_f1",), clean["macro_f1"], 0.4680972874281771),
            (
                ("clean_settlement_name_recall",),
                clean["per_state"]["settlement_name"]["recall"],
                0.1,
            ),
            (("mild_macro_f1",), mild["macro_f1"], 0.3977588813953674),
            (
                ("mild_recall_floors", "context_only"),
                mild["per_state"]["context_only"]["recall"],
                0.520654531441017,
            ),
            (
                ("mild_recall_floors", "quantity"),
                mild["per_state"]["quantity"]["recall"],
                0.1765055025096581,
            ),
            (
                ("mild_recall_floors", "unit"),
                mild["per_state"]["unit"]["recall"],
                0.3767836311289388,
            ),
            (
                ("mild_recall_floors", "person_name"),
                mild["per_state"]["person_name"]["recall"],
                0.4988092152820551,
            ),
            (
                ("mild_recall_floors", "settlement_name"),
                mild["per_state"]["settlement_name"]["recall"],
                0.15,
            ),
            (
                ("mild_precision_floors", "unit"),
                mild["per_state"]["unit"]["precision"],
                0.3512887014608468,
            ),
            (
                ("mild_precision_floors", "settlement_name"),
                mild["per_state"]["settlement_name"]["precision"],
                0.20747537967348736,
            ),
            (
                ("positive_mild_macro_f1_delta_outer_fold_count",),
                paired["positive_mild_macro_f1_delta_fold_count"],
                4,
            ),
            (
                ("positive_mild_unit_recall_delta_outer_fold_count",),
                paired["positive_mild_unit_recall_delta_fold_count"],
                4,
            ),
            (
                ("positive_mild_settlement_name_recall_delta_outer_fold_count",),
                paired["positive_mild_settlement_name_recall_delta_fold_count"],
                4,
            ),
            (
                ("settlement_name_positive_recall_outer_fold_count",),
                sum(value > COMPARISON_TOLERANCE for value in settlement_by_fold),
                5,
            ),
            (
                ("unit_worst_outer_fold_recall",),
                min(unit_by_fold),
                0.18225197064754597,
            ),
        )
        self.assertEqual(15, len(gate_specs))
        checks = self.report["gate_decision"]["checks"]
        passed_values: list[bool] = []
        failed: set[str] = set()
        for path, observed, minimum in gate_specs:
            check: Mapping[str, Any] = checks
            for component in path:
                check = check[component]
            self.assertFloatEqual(float(observed), check["observed"])
            self.assertEqual(minimum, check["minimum"])
            passed = float(observed) >= float(minimum) - COMPARISON_TOLERANCE
            self.assertIs(passed, check["passed"])
            passed_values.append(passed)
            if not passed:
                failed.add(".".join(path))

        self.assertEqual(
            {
                "mild_macro_f1",
                "mild_precision_floors.unit",
                "mild_recall_floors.settlement_name",
                "mild_recall_floors.unit",
                "positive_mild_macro_f1_delta_outer_fold_count",
                "positive_mild_settlement_name_recall_delta_outer_fold_count",
                "positive_mild_unit_recall_delta_outer_fold_count",
                "unit_worst_outer_fold_recall",
            },
            failed,
        )
        self.assertFalse(all(passed_values))
        decision = self.report["gate_decision"]
        self.assertFalse(decision["all_passed"])
        self.assertEqual(COMPARISON_TOLERANCE, decision["comparison_tolerance"])
        self.assertEqual("mtaac_retired", decision["terminal_status"])
        self.assertEqual("mtaac_retired", self.report["terminal_status"])
        self.assertTrue(decision["mtaac_retired"])

        final_model = self.report["final_development_model"]
        self.assertFalse(final_model["fitted"])
        self.assertIsNone(final_model["model_state_commitment"])
        self.assertIsNone(final_model["optimizer"])

    def test_result_contains_no_item_identity_private_path_or_prospective_result(self) -> None:
        forbidden_keys = {
            "account",
            "archive_member",
            "document_id",
            "document_key",
            "family_id",
            "family_ids",
            "feature_rows",
            "fold_membership",
            "host",
            "identity_map",
            "individual_predictions",
            "local_path",
            "member_path",
            "raw_annotation",
            "raw_form",
            "source_identifier",
            "token_key",
            "username",
        }
        self.assertFalse(forbidden_keys & _all_mapping_keys(self.report))
        claim = self.report["claim_scope"]
        self.assertFalse(claim["eligible_as_binding_confirmation"])
        self.assertFalse(claim["eligible_as_decipherment"])
        self.assertFalse(claim["eligible_as_reserved_validation_result"])
        self.assertFalse(claim["eligible_as_v2_holdout_result"])
        self.assertFalse(claim["individual_predictions_published"])
        self.assertTrue(claim["prospective_execution_requires_separate_public_freeze"])
        self.assertFalse(self.report["model_contract"]["v4_refit"])
        self.assertEqual(
            "none_primary_model_only",
            self.report["model_contract"]["v5_diagnostics"],
        )

        text = self.raw.decode("utf-8")
        forbidden_patterns = (
            r"\bP[0-9]{6}\b",
            r"(?<![0-9])(?:[0-9]{1,3}[.]){3}[0-9]{1,3}(?![0-9])",
            r"/(?:home|Users|private/tmp|tmp)/",
            r"\bssh://",
            r"\b(?:FORM|SEGM|XPOSTAG)\b",
            r"\boracc\b",
            r'"(?:host|account|username)"\s*:',
            r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY",
            r"\bgh[pousr]_[A-Za-z0-9_]{20,}",
        )
        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text, flags=re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
