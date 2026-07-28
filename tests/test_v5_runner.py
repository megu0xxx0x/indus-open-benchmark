from __future__ import annotations

import json
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, Self
from unittest.mock import patch

import indusbench.v5dev.runner as runner
from indusbench.schema_validation import validate_schema_instance
from indusbench.v3dev.contracts import V3_STRUCTURAL_STATES, V3StructuralState
from indusbench.v4dev.contracts import V4FeatureLine, V4LabeledFeatureFamily
from tests.test_v3_runner import _bundle

ROOT = Path(__file__).resolve().parents[1]
PLAN_BYTES = (ROOT / "benchmark" / "mtaac-v5-development-v1.json").read_bytes()
IMPLEMENTATION_COMMIT = "d" * 40
SYNTHETIC_FAMILY_COUNT = 25
SCHEMA = ROOT / "schemas" / "mtaac-v5-development-report.schema.json"


class _PerfectV5Model:
    fit_calls = 0

    @classmethod
    def fit(cls, families: tuple[V4LabeledFeatureFamily, ...]) -> Self:
        if not families:
            raise AssertionError("synthetic V5 fit received no families")
        cls.fit_calls += 1
        return cls()

    def decode(self, line: V4FeatureLine) -> tuple[V3StructuralState, ...]:
        return tuple(
            V3_STRUCTURAL_STATES[index % len(V3_STRUCTURAL_STATES)]
            for index in range(len(line.rows))
        )

    def optimization_summary(self) -> dict[str, Any]:
        return {
            "converged": True,
            "accepted_iterations": 1,
            "final_objective": 0.5,
            "final_gradient_infinity_norm": 1e-6,
            "termination_reason": "gradient_infinity_norm",
        }

    def model_state_commitment(self) -> str:
        return "sha256:" + ("a" * 64)


class _ContextOnlyV5Model(_PerfectV5Model):
    fit_calls = 0

    def decode(self, line: V4FeatureLine) -> tuple[V3StructuralState, ...]:
        return ("context_only",) * len(line.rows)


class _BrokenV5Model(_PerfectV5Model):
    @classmethod
    def fit(cls, families: tuple[V4LabeledFeatureFamily, ...]) -> Self:
        del families
        raise ValueError("optimizer exposed an internal detail")


def _run_synthetic(
    model: type[_PerfectV5Model],
) -> dict[str, Any]:
    bundle = _bundle(SYNTHETIC_FAMILY_COUNT)
    model.fit_calls = 0
    with (
        patch(
            "indusbench.v4dev.runner.MTAAC_V2_TRAINING_FAMILY_COUNT",
            SYNTHETIC_FAMILY_COUNT,
        ),
        patch.object(runner, "V5GroupContrastLinearChainCRF", model),
    ):
        return runner.run_v5_development(
            bundle,
            plan_bytes=PLAN_BYTES,
            implementation_commit=IMPLEMENTATION_COMMIT,
        )


def _mapping_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested_key
            for nested_value in value.values()
            for nested_key in _mapping_keys(nested_value)
        }
    if isinstance(value, list):
        return {nested_key for nested_value in value for nested_key in _mapping_keys(nested_value)}
    return set()


class V5RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.advance_report = _run_synthetic(_PerfectV5Model)
        cls.retired_report = _run_synthetic(_ContextOnlyV5Model)

    def test_one_primary_v5_fit_per_fold_and_conditional_final_fit(self) -> None:
        self.assertEqual(6, _PerfectV5Model.fit_calls)
        self.assertEqual(5, _ContextOnlyV5Model.fit_calls)
        self.assertEqual(
            list(range(5)),
            [
                fold["outer_fold_index"]
                for fold in self.advance_report["outer_development"]["outer_folds"]
            ],
        )
        for report in (self.advance_report, self.retired_report):
            for fold in report["outer_development"]["outer_folds"]:
                self.assertEqual({"clean", "mild"}, set(fold["metrics"]))
                self.assertNotIn("diagnostics", fold["metrics"])
                self.assertEqual(
                    {
                        "train_clean",
                        "train_mild",
                        "validation_clean",
                        "validation_mild",
                    },
                    set(fold["profile_batch_commitments"]),
                )
            self.assertFalse(report["model_contract"]["v4_refit"])
            self.assertEqual(
                "none_primary_model_only",
                report["model_contract"]["v5_diagnostics"],
            )

    def test_pass_fits_final_model_and_failure_retires_without_fit(self) -> None:
        self.assertEqual(
            "advance_to_prospective_freeze",
            self.advance_report["terminal_status"],
        )
        self.assertTrue(self.advance_report["gate_decision"]["all_passed"])
        self.assertTrue(self.advance_report["final_development_model"]["fitted"])
        self.assertRegex(
            self.advance_report["final_development_model"]["model_state_commitment"],
            r"^sha256:[0-9a-f]{64}$",
        )

        self.assertEqual("mtaac_retired", self.retired_report["terminal_status"])
        self.assertFalse(self.retired_report["gate_decision"]["all_passed"])
        self.assertTrue(self.retired_report["mtaac_retired"])
        self.assertFalse(self.retired_report["final_development_model"]["fitted"])
        self.assertIsNone(self.retired_report["final_development_model"]["model_state_commitment"])
        self.assertIsNone(self.retired_report["final_development_model"]["optimizer"])

    def test_exact_v4_paired_baselines_and_strict_counts_are_reported(self) -> None:
        paired = self.advance_report["outer_development"]["paired_v4"]
        self.assertEqual(
            list(runner.V4_MILD_MACRO_F1_BY_OUTER_FOLD),
            paired["v4_mild_macro_f1_by_outer_fold"],
        )
        self.assertEqual(
            list(runner.V4_MILD_UNIT_RECALL_BY_OUTER_FOLD),
            paired["v4_mild_unit_recall_by_outer_fold"],
        )
        self.assertEqual(
            list(runner.V4_MILD_SETTLEMENT_RECALL_BY_OUTER_FOLD),
            paired["v4_mild_settlement_name_recall_by_outer_fold"],
        )
        for metric in ("macro_f1", "unit_recall", "settlement_name_recall"):
            deltas = paired[f"mild_{metric}_delta_by_outer_fold"]
            self.assertEqual(
                sum(delta > runner.COMPARISON_TOLERANCE for delta in deltas),
                paired[f"positive_mild_{metric}_delta_fold_count"],
            )

    def test_report_boundary_contains_no_item_or_fold_membership(self) -> None:
        serialized = json.dumps(self.advance_report, sort_keys=True)
        for forbidden in (
            "mtaac-document-source-id",
            "mtaac-word-form-sha256",
            "observed_form_id",
            "cluster_identifier",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(
            _mapping_keys(self.advance_report)
            & {
                "document_key",
                "family_id",
                "family_ids",
                "feature_rows",
                "fold_family_ids",
                "token_key",
            }
        )
        schema_report = deepcopy(self.advance_report)
        schema_report["data_boundary"]["model_training_family_count"] = 271
        self.assertEqual([], validate_schema_instance(schema_report, SCHEMA))

    def test_invalid_plan_and_parent_boundary_fail_before_model_fit(self) -> None:
        bundle = _bundle(SYNTHETIC_FAMILY_COUNT)
        with (
            patch.object(runner, "V5GroupContrastLinearChainCRF") as model,
            self.assertRaises(runner.V5DevelopmentError),
        ):
            runner.run_v5_development(
                bundle,
                plan_bytes=PLAN_BYTES + b" ",
                implementation_commit=IMPLEMENTATION_COMMIT,
            )
        model.fit.assert_not_called()

        changed_bundle = replace(bundle, source_commit="f" * 40)
        with (
            patch.object(runner, "V5GroupContrastLinearChainCRF") as model,
            self.assertRaises(runner.V5DevelopmentError),
        ):
            runner.run_v5_development(
                changed_bundle,
                plan_bytes=PLAN_BYTES,
                implementation_commit=IMPLEMENTATION_COMMIT,
            )
        model.fit.assert_not_called()

    def test_v4_models_and_diagnostic_profiles_are_never_called(self) -> None:
        original_prepare = runner._prepare_partition_variants
        profile_calls: list[bool] = []

        def prepare_without_diagnostics(*args: Any, **kwargs: Any) -> Any:
            profile_calls.append(bool(kwargs.get("include_self_inclusive", False)))
            return original_prepare(*args, **kwargs)

        with (
            patch.object(
                runner,
                "_prepare_partition_variants",
                side_effect=prepare_without_diagnostics,
            ),
            patch(
                "indusbench.v4dev.sequence.V4LinearChainCRF.fit",
                side_effect=AssertionError("V4 refit is forbidden"),
            ) as v4_fit,
            patch.object(
                runner,
                "V5GroupContrastLinearChainCRF",
                _ContextOnlyV5Model,
            ),
            patch(
                "indusbench.v4dev.runner.MTAAC_V2_TRAINING_FAMILY_COUNT",
                SYNTHETIC_FAMILY_COUNT,
            ),
        ):
            runner.run_v5_development(
                _bundle(SYNTHETIC_FAMILY_COUNT),
                plan_bytes=PLAN_BYTES,
                implementation_commit=IMPLEMENTATION_COMMIT,
            )
        v4_fit.assert_not_called()
        self.assertTrue(profile_calls)
        self.assertFalse(any(profile_calls))

    def test_optimizer_failure_is_wrapped_by_the_v5_runner_contract(self) -> None:
        with (
            patch(
                "indusbench.v4dev.runner.MTAAC_V2_TRAINING_FAMILY_COUNT",
                SYNTHETIC_FAMILY_COUNT,
            ),
            patch.object(runner, "V5GroupContrastLinearChainCRF", _BrokenV5Model),
            self.assertRaisesRegex(
                runner.V5DevelopmentError,
                "V5 profile, fit, or evaluation machinery failed closed",
            ),
        ):
            runner.run_v5_development(
                _bundle(SYNTHETIC_FAMILY_COUNT),
                plan_bytes=PLAN_BYTES,
                implementation_commit=IMPLEMENTATION_COMMIT,
            )


if __name__ == "__main__":
    unittest.main()
