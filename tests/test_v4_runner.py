from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Self
from unittest.mock import patch

import indusbench.v4dev.runner as runner
from indusbench.schema_validation import validate_schema_instance
from indusbench.v3dev.contracts import V3_STRUCTURAL_STATES, V3StructuralState
from indusbench.v4dev.contracts import V4FeatureLine, V4LabeledFeatureFamily
from indusbench.v4dev_cli import validate_public_development_report
from tests.test_v3_runner import _bundle

ROOT = Path(__file__).resolve().parents[1]
PLAN_BYTES = (ROOT / "benchmark" / "mtaac-v4-development-v1.json").read_bytes()
SCHEMA = ROOT / "schemas" / "mtaac-v4-development-report.schema.json"
IMPLEMENTATION_COMMIT = "d" * 40
SYNTHETIC_FAMILY_COUNT = 25


class _PerfectModel:
    fit_calls = 0

    @classmethod
    def fit(cls, families: tuple[V4LabeledFeatureFamily, ...]) -> Self:
        if not families:
            raise AssertionError("synthetic fit received no families")
        cls.fit_calls += 1
        return cls()

    def decode(
        self,
        line: V4FeatureLine,
        *,
        transition_zero: bool = False,
    ) -> tuple[V3StructuralState, ...]:
        del transition_zero
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


class _PerfectLogisticModel(_PerfectModel):
    def decode(self, line: V4FeatureLine) -> tuple[V3StructuralState, ...]:
        return tuple(
            V3_STRUCTURAL_STATES[index % len(V3_STRUCTURAL_STATES)]
            for index in range(len(line.rows))
        )


def _run_synthetic() -> dict[str, Any]:
    bundle = _bundle(SYNTHETIC_FAMILY_COUNT)
    _PerfectModel.fit_calls = 0
    _PerfectLogisticModel.fit_calls = 0
    with (
        patch.object(
            runner,
            "MTAAC_V2_TRAINING_FAMILY_COUNT",
            SYNTHETIC_FAMILY_COUNT,
        ),
        patch.object(runner, "V4LinearChainCRF", _PerfectModel),
        patch.object(runner, "V4LogisticEmissionModel", _PerfectLogisticModel),
    ):
        return runner.run_v4_development(
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


class V4RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = _run_synthetic()

    def test_report_matches_closed_public_boundary(self) -> None:
        public_report = deepcopy(self.report)
        public_report["data_boundary"]["model_training_family_count"] = 271
        self.assertIs(
            public_report,
            validate_public_development_report(
                public_report,
                expected_implementation_commit=IMPLEMENTATION_COMMIT,
            ),
        )
        json.dumps(self.report, allow_nan=False)
        serialized = json.dumps(self.report, sort_keys=True)
        self.assertNotIn("mtaac-document-source-id", serialized)
        self.assertNotIn("mtaac-word-form-sha256", serialized)
        self.assertNotIn("observed_form_id", serialized)
        self.assertNotIn("cluster_identifier", serialized)
        self.assertFalse(
            _mapping_keys(self.report)
            & {
                "document_key",
                "family_id",
                "family_ids",
                "feature_rows",
                "token_key",
            }
        )
        self.assertEqual([], validate_schema_instance(public_report, SCHEMA))

    def test_fixed_single_candidate_outer_execution_and_boundaries(self) -> None:
        self.assertEqual(
            "mtaac_v4_distributional_crf_development",
            self.report["analysis"],
        )
        self.assertEqual(5, self.report["outer_development"]["outer_fold_count"])
        self.assertEqual(
            list(range(5)),
            [fold["outer_fold_index"] for fold in self.report["outer_development"]["outer_folds"]],
        )
        self.assertEqual(1, self.report["model_contract"]["candidate_count"])
        self.assertEqual(
            "none_fixed_method",
            self.report["model_contract"]["candidate_selection"],
        )
        self.assertFalse(self.report["data_boundary"]["v2_holdout_exposed_to_model"])
        self.assertFalse(self.report["data_boundary"]["v2_holdout_scored"])
        self.assertFalse(self.report["data_boundary"]["reserved_validation_source_loaded"])
        for fold in self.report["outer_development"]["outer_folds"]:
            commitments = fold["profile_batch_commitments"]
            self.assertEqual(
                {
                    "train_clean",
                    "train_mild",
                    "validation_clean",
                    "validation_mild",
                },
                set(commitments),
            )
            self.assertTrue(
                all(
                    value.startswith("sha256:") and len(value) == 71
                    for value in commitments.values()
                )
            )

    def test_diagnostics_cannot_rescue_a_failed_primary_gate(self) -> None:
        decision = self.report["gate_decision"]
        self.assertEqual("development_killed", decision["terminal_status"])
        self.assertFalse(decision["all_passed"])
        self.assertFalse(decision["checks"]["profile_increment_mild_macro_f1"]["passed"])
        self.assertFalse(self.report["final_development_model"]["fitted"])
        self.assertIsNone(self.report["final_development_model"]["model_state_commitment"])
        self.assertIsNone(self.report["final_development_model"]["optimizer"])

    def test_v3_paired_baseline_is_exact_and_not_selected(self) -> None:
        paired = self.report["outer_development"]["paired_v3"]
        self.assertEqual(runner.V3_MILD_MACRO_F1, paired["v3_mild_macro_f1"])
        self.assertEqual(
            list(runner.V3_MILD_MACRO_F1_BY_OUTER_FOLD),
            paired["v3_mild_macro_f1_by_outer_fold"],
        )
        self.assertEqual(5, len(paired["delta_by_outer_fold"]))
        self.assertEqual(
            sum(delta > 0.0 for delta in paired["delta_by_outer_fold"]),
            paired["positive_delta_fold_count"],
        )

    def test_invalid_plan_and_parent_boundary_fail_before_models(self) -> None:
        bundle = _bundle(SYNTHETIC_FAMILY_COUNT)
        with (
            patch.object(
                runner,
                "MTAAC_V2_TRAINING_FAMILY_COUNT",
                SYNTHETIC_FAMILY_COUNT,
            ),
            patch.object(runner, "V4LinearChainCRF", _PerfectModel),
            self.assertRaises(ValueError),
        ):
            runner.run_v4_development(
                bundle,
                plan_bytes=PLAN_BYTES + b" ",
                implementation_commit=IMPLEMENTATION_COMMIT,
            )


if __name__ == "__main__":
    unittest.main()
