from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import indusbench.v5dev.plan as plan_module
from indusbench.v5dev.plan import (
    MAX_V5_DEVELOPMENT_PLAN_BYTES,
    V5_DEVELOPMENT_PLAN_ID,
    V5_DEVELOPMENT_PLAN_SHA256,
    V5_DEVELOPMENT_PLAN_VERSION,
    V5DevelopmentPlanError,
    validate_v5_development_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark" / "mtaac-v5-development-v1.json"


def _tagged_sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


class V5DevelopmentPlanTests(unittest.TestCase):
    def test_checked_in_plan_is_the_exact_closed_contract(self) -> None:
        raw = PLAN_PATH.read_bytes()
        self.assertLessEqual(len(raw), MAX_V5_DEVELOPMENT_PLAN_BYTES)
        self.assertEqual(V5_DEVELOPMENT_PLAN_SHA256, _tagged_sha256(raw))

        value = validate_v5_development_plan(raw)
        self.assertEqual(V5_DEVELOPMENT_PLAN_ID, value["protocol_id"])
        self.assertEqual(V5_DEVELOPMENT_PLAN_VERSION, value["protocol_version"])
        self.assertEqual(
            "development_only_post_v4_result_final_mtaac_attempt_before_reserved_source_execution",
            value["protocol_status"],
        )
        self.assertEqual(
            [
                "advance_to_prospective_freeze",
                "mtaac_retired",
            ],
            value["report_contract"]["terminal_statuses"],
        )
        self.assertTrue(value["report_contract"]["required_assertions"]["mtaac_retired"])
        self.assertNotIn("oracc", raw.decode("utf-8").casefold())
        self.assertNotIn("tau", raw.decode("utf-8").casefold())

    def test_only_fixed_group_contrast_model_change_is_declared(self) -> None:
        value = json.loads(PLAN_PATH.read_bytes())
        model = value["model"]
        regularizer = model["regularizer"]

        self.assertEqual(1, model["candidate_count"])
        self.assertEqual(0.01, model["l2_rho"])
        self.assertEqual(0.5, model["class_adjustment"]["decode_only_gamma"])
        self.assertEqual(0.5, model["class_adjustment"]["family_weighted_jeffreys_alpha"])
        self.assertEqual(
            "exactly_the_v4_parameter_count_with_no_shared_or_residual_parameters_added",
            model["parameter_count"],
        )
        self.assertFalse(model["v4_parameter_layout_changed"])
        self.assertFalse(model["v4_refit"])
        self.assertEqual("none_primary_model_only", model["v5_diagnostics"])
        self.assertEqual(
            "v5-fixed-group-contrast-linear-chain-crf-v1",
            model["version"],
        )
        self.assertEqual(
            [["quantity", "unit"], ["person_name", "settlement_name"]],
            regularizer["group_pairs"],
        )
        self.assertEqual(2.0, regularizer["fixed_contrast_multiplier"])
        self.assertEqual(
            "for_each_pair_and_coordinate_mu_equals_a_plus_b_over_2_kappa_equals_a_minus_b_over_2_penalty_equals_rho_times_mu_squared_plus_2_times_kappa_squared",
            regularizer["group_contrast_formula"],
        )
        self.assertEqual(
            "gradient_a_equals_rho_times_(mu_plus_2_times_kappa)_and_gradient_b_equals_rho_times_(mu_minus_2_times_kappa)",
            regularizer["group_contrast_gradient"],
        )
        self.assertEqual(
            "every_corresponding_emission_feature_coefficient_and_emission_bias",
            regularizer["coordinate_scope"],
        )
        self.assertEqual(
            "rho_over_2_times_sum_of_squares",
            regularizer["context_emission_and_bias"],
        )
        self.assertEqual(
            "rho_over_2_times_sum_of_squares",
            regularizer["start_and_transition"],
        )
        self.assertFalse(regularizer["runtime_tunable_contrast_parameter"])
        self.assertFalse(regularizer["pooling_weight_grid"])
        self.assertFalse(regularizer["alternate_groupings"])
        self.assertFalse(regularizer["naive_shared_plus_residual_parameterization"])

    def test_v4_parent_result_and_paired_baseline_are_exact(self) -> None:
        value = json.loads(PLAN_PATH.read_bytes())
        parent = value["parent_boundary"]
        baseline = value["paired_v4_baseline"]

        self.assertEqual(
            "304f8b36a32083330b8af02d21a58382c29d8915",
            parent["v4_freeze_commit"],
        )
        self.assertEqual(
            "68332353a86f88e99e46df71fcdd2a4974dba31c",
            parent["v4_result_commit"],
        )
        self.assertEqual(
            "sha256:4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897",
            parent["v4_result_sha256"],
        )
        self.assertEqual([0, 1, 2, 3, 4], baseline["outer_fold_order"])
        self.assertEqual(0.3877588813953674, baseline["aggregate_mild_macro_f1"])
        self.assertEqual(0.30521567409297784, baseline["aggregate_mild_unit_recall"])
        self.assertEqual(
            0.042941913609110954,
            baseline["aggregate_mild_settlement_name_recall"],
        )
        self.assertEqual(0.3512887014608468, baseline["aggregate_mild_unit_precision"])
        self.assertEqual(
            0.20747537967348736,
            baseline["aggregate_mild_settlement_name_precision"],
        )
        self.assertEqual(
            [
                0.3756051787768944,
                0.3998966341462856,
                0.3615261061386301,
                0.39294354710818963,
                0.39901832092281697,
            ],
            baseline["mild_macro_f1_by_outer_fold"],
        )
        self.assertEqual(
            [
                0.18225197064754597,
                0.2892249319203195,
                0.2772641078805165,
                0.39686535349113794,
                0.35585102688488385,
            ],
            baseline["mild_unit_recall_by_outer_fold"],
        )
        self.assertEqual(
            [
                0.0,
                0.09932569269976571,
                0.003780194718492515,
                0.06366234989790896,
                0.05568829861391914,
            ],
            baseline["mild_settlement_name_recall_by_outer_fold"],
        )
        self.assertEqual(
            "immutable_v4_aggregate_result_without_v4_refit",
            baseline["source"],
        )

    def test_gates_and_tolerance_semantics_are_exact(self) -> None:
        value = json.loads(PLAN_PATH.read_bytes())
        decision = value["decision"]
        checks = decision["checks"]
        self.assertEqual(1e-12, decision["comparison_semantics"]["comparison_tolerance"])
        self.assertEqual(
            "passed_iff_observed_is_greater_than_or_equal_to_minimum_minus_comparison_tolerance",
            decision["comparison_semantics"]["minimum_gate"],
        )
        self.assertEqual(
            "counted_iff_delta_is_strictly_greater_than_comparison_tolerance",
            decision["comparison_semantics"]["positive_delta"],
        )
        self.assertEqual(
            "counted_iff_recall_is_strictly_greater_than_comparison_tolerance",
            decision["comparison_semantics"]["strict_positive_recall"],
        )
        self.assertEqual(0.3977588813953674, checks["mild_macro_f1_minimum"])
        self.assertEqual(0.3767836311289388, checks["mild_unit_recall_minimum"])
        self.assertEqual(0.15, checks["mild_settlement_name_recall_minimum"])
        self.assertEqual(0.3512887014608468, checks["mild_unit_precision_minimum"])
        self.assertEqual(
            0.20747537967348736,
            checks["mild_settlement_name_precision_minimum"],
        )
        self.assertEqual(
            0.18225197064754597,
            checks["unit_worst_outer_fold_recall_minimum"],
        )
        self.assertEqual(
            5,
            checks["settlement_name_positive_recall_outer_fold_count_minimum"],
        )
        self.assertEqual("mtaac_retired", decision["failure_terminal_status"])
        self.assertEqual(
            "advance_to_prospective_freeze",
            decision["success_terminal_status"],
        )
        self.assertEqual(
            "hard_error_without_result_and_without_rerun_under_changed_conditions",
            decision["invalid_execution_policy"],
        )
        attempts = value["attempt_semantics"]
        self.assertEqual(
            "only_a_complete_runtime_consistency_valid_and_closed_schema_valid_aggregate_report_counts_as_the_single_valid_v5_result",
            attempts["single_valid_result"],
        )
        self.assertEqual(
            [
                "no_complete_aggregate_report_exists",
                "no_scientific_metric_was_emitted_or_exposed",
                "implementation_commit_is_exactly_identical",
                "plan_bytes_are_exactly_identical",
                "source_archive_bytes_are_exactly_identical",
                "all_cli_arguments_are_exactly_identical",
            ],
            attempts["pre_report_retry"]["all_conditions_required"],
        )
        self.assertEqual(
            ["environmental", "io"],
            attempts["pre_report_retry"]["allowed_failure_classes"],
        )
        self.assertEqual(
            [
                "any_code_or_implementation_commit_changes",
                "any_plan_byte_changes",
                "any_source_archive_or_data_byte_changes",
                "any_cli_argument_changes",
                "any_partial_scientific_metric_is_emitted_or_exposed",
            ],
            attempts["retire_without_another_mtaac_attempt_if"],
        )

    def test_byte_change_is_rejected_even_if_primary_digest_is_substituted(self) -> None:
        raw = PLAN_PATH.read_bytes()
        changed = raw + b" "
        with self.assertRaisesRegex(V5DevelopmentPlanError, "SHA-256"):
            validate_v5_development_plan(changed)

        with (
            patch.object(plan_module, "V5_DEVELOPMENT_PLAN_SHA256", _tagged_sha256(changed)),
            self.assertRaisesRegex(V5DevelopmentPlanError, "byte layout"),
        ):
            validate_v5_development_plan(changed)

    def test_dual_digest_substitution_cannot_rewrite_a_closed_field(self) -> None:
        raw = PLAN_PATH.read_bytes()
        changed = raw.replace(b'"candidate_count": 1', b'"candidate_count": 2', 1)
        self.assertNotEqual(raw, changed)
        with (
            patch.object(plan_module, "V5_DEVELOPMENT_PLAN_SHA256", _tagged_sha256(changed)),
            patch.object(
                plan_module,
                "_EXPECTED_PLAN_BLAKE2B",
                hashlib.blake2b(changed).hexdigest(),
            ),
            self.assertRaisesRegex(V5DevelopmentPlanError, "closed contract"),
        ):
            validate_v5_development_plan(changed)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(self) -> None:
        cases = (
            b'{"protocol_id":"first","protocol_id":"second"}',
            b'{"protocol_id":NaN}',
        )
        for raw in cases:
            with (
                self.subTest(raw=raw),
                patch.object(plan_module, "V5_DEVELOPMENT_PLAN_SHA256", _tagged_sha256(raw)),
                patch.object(
                    plan_module,
                    "_EXPECTED_PLAN_BLAKE2B",
                    hashlib.blake2b(raw).hexdigest(),
                ),
                self.assertRaisesRegex(V5DevelopmentPlanError, "strict UTF-8 JSON"),
            ):
                validate_v5_development_plan(raw)


if __name__ == "__main__":
    unittest.main()
