from __future__ import annotations

import copy
import unittest
from pathlib import Path
from typing import Any

from indusbench.schema_validation import validate_schema_instance
from indusbench.v3dev.metrics import add_confusion_matrices, metrics_from_confusion
from indusbench.v5dev.plan import V5_DEVELOPMENT_PLAN_SHA256

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "mtaac-v5-development-report.schema.json"
STATES = [
    "context_only",
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
]
V4_MACRO_BY_FOLD = [
    0.3756051787768944,
    0.3998966341462856,
    0.3615261061386301,
    0.39294354710818963,
    0.39901832092281697,
]
V4_UNIT_RECALL_BY_FOLD = [
    0.18225197064754597,
    0.2892249319203195,
    0.2772641078805165,
    0.39686535349113794,
    0.35585102688488385,
]
V4_SETTLEMENT_RECALL_BY_FOLD = [
    0.0,
    0.09932569269976571,
    0.003780194718492515,
    0.06366234989790896,
    0.05568829861391914,
]
COMPARISON_TOLERANCE = 1e-12


def _optimizer_run() -> dict[str, Any]:
    return {
        "accepted_iterations": 12,
        "converged": True,
        "final_gradient_infinity_norm": 0.00001,
        "final_objective": 1.25,
        "termination_reason": "gradient_infinity_norm",
    }


def _optimizer_settings() -> dict[str, Any]:
    return {
        "armijo": {
            "c1": 0.0001,
            "contraction_factor": 0.5,
            "initial_step": 1.0,
            "maximum_trials": 31,
            "minimum_step": 9.313225746154785e-10,
        },
        "batch": "full",
        "convergence": {
            "consecutive_relative_objective_iterations": 5,
            "gradient_infinity_norm": 1e-05,
            "relative_objective": 1e-09,
            "secondary_gradient_infinity_norm": 0.001,
        },
        "curvature_pair_acceptance": (
            "s_dot_y_strictly_greater_than_1e-12_times_norm_s_times_norm_y"
        ),
        "direction": "deterministic_lbfgs_two_loop_recursion",
        "fallback": False,
        "history_size": 10,
        "maximum_accepted_iterations": 100,
        "non_descent_policy": (
            "clear_history_once_then_use_negative_gradient_repeat_is_hard_error"
        ),
        "numeric_type": "float64",
        "stable_logsumexp": "maximum_shift",
        "summation": "sorted_math_fsum",
    }


def _metrics(score: float) -> dict[str, Any]:
    confusion: dict[str, dict[str, float]] = {
        truth: {predicted: 0.0 for predicted in STATES} for truth in STATES
    }
    for state_index, truth in enumerate(STATES):
        confusion[truth][truth] = score
        confusion[truth][STATES[(state_index + 1) % len(STATES)]] = 1.0 - score
    return metrics_from_confusion(confusion)  # type: ignore[arg-type]


def _aggregate_metric_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    matrices = [report["weighted_confusion_matrix"] for report in reports]
    return metrics_from_confusion(add_confusion_matrices(matrices))  # type: ignore[arg-type]


def _minimum_check(observed: float, minimum: float) -> dict[str, Any]:
    return {
        "minimum": minimum,
        "observed": observed,
        "passed": observed >= minimum - COMPARISON_TOLERANCE,
    }


def _fold_count_check(observed: int, minimum: int = 4) -> dict[str, Any]:
    return {
        "minimum": minimum,
        "observed": observed,
        "passed": observed >= minimum,
    }


def _report(
    *,
    terminal_status: str = "advance_to_prospective_freeze",
) -> dict[str, Any]:
    advanced = terminal_status == "advance_to_prospective_freeze"
    score = 0.6 if advanced else 0.3
    folds = []
    for fold_index in range(5):
        folds.append(
            {
                "outer_fold_index": fold_index,
                "support": {
                    "train_family_count": 216,
                    "validation_family_count": 55,
                    "train_state_support": {state: 10 for state in STATES},
                    "validation_state_support": {state: 2 for state in STATES},
                },
                "profile_batch_commitments": {
                    "train_clean": "sha256:" + f"{fold_index + 1:x}" * 64,
                    "train_mild": "sha256:" + f"{fold_index + 2:x}" * 64,
                    "validation_clean": "sha256:" + f"{fold_index + 3:x}" * 64,
                    "validation_mild": "sha256:" + f"{fold_index + 4:x}" * 64,
                },
                "optimizer": _optimizer_run(),
                "metrics": {
                    "clean": _metrics(score),
                    "mild": _metrics(score),
                },
            }
        )

    out_of_fold = {
        regime: _aggregate_metric_reports(
            [fold["metrics"][regime] for fold in folds],
        )
        for regime in ("clean", "mild")
    }
    v5_macro = [float(fold["metrics"]["mild"]["macro_f1"]) for fold in folds]
    v5_unit = [float(fold["metrics"]["mild"]["per_state"]["unit"]["recall"]) for fold in folds]
    v5_settlement = [
        float(fold["metrics"]["mild"]["per_state"]["settlement_name"]["recall"]) for fold in folds
    ]
    macro_deltas = [
        current - baseline for current, baseline in zip(v5_macro, V4_MACRO_BY_FOLD, strict=True)
    ]
    unit_deltas = [
        current - baseline
        for current, baseline in zip(v5_unit, V4_UNIT_RECALL_BY_FOLD, strict=True)
    ]
    settlement_deltas = [
        current - baseline
        for current, baseline in zip(
            v5_settlement,
            V4_SETTLEMENT_RECALL_BY_FOLD,
            strict=True,
        )
    ]
    positive_macro = sum(delta > COMPARISON_TOLERANCE for delta in macro_deltas)
    positive_unit = sum(delta > COMPARISON_TOLERANCE for delta in unit_deltas)
    positive_settlement = sum(delta > COMPARISON_TOLERANCE for delta in settlement_deltas)
    positive_settlement_recall = sum(recall > COMPARISON_TOLERANCE for recall in v5_settlement)

    mild = out_of_fold["mild"]
    clean = out_of_fold["clean"]
    mild_per_state = mild["per_state"]
    clean_per_state = clean["per_state"]
    checks = {
        "clean_macro_f1": _minimum_check(
            float(clean["macro_f1"]),
            0.4680972874281771,
        ),
        "clean_settlement_name_recall": _minimum_check(
            float(clean_per_state["settlement_name"]["recall"]),
            0.1,
        ),
        "mild_macro_f1": _minimum_check(
            float(mild["macro_f1"]),
            0.3977588813953674,
        ),
        "mild_recall_floors": {
            "context_only": _minimum_check(
                float(mild_per_state["context_only"]["recall"]),
                0.520654531441017,
            ),
            "quantity": _minimum_check(
                float(mild_per_state["quantity"]["recall"]),
                0.1765055025096581,
            ),
            "unit": _minimum_check(
                float(mild_per_state["unit"]["recall"]),
                0.3767836311289388,
            ),
            "person_name": _minimum_check(
                float(mild_per_state["person_name"]["recall"]),
                0.4988092152820551,
            ),
            "settlement_name": _minimum_check(
                float(mild_per_state["settlement_name"]["recall"]),
                0.15,
            ),
        },
        "mild_precision_floors": {
            "unit": _minimum_check(
                float(mild_per_state["unit"]["precision"]),
                0.3512887014608468,
            ),
            "settlement_name": _minimum_check(
                float(mild_per_state["settlement_name"]["precision"]),
                0.20747537967348736,
            ),
        },
        "positive_mild_macro_f1_delta_outer_fold_count": _fold_count_check(
            positive_macro,
        ),
        "positive_mild_unit_recall_delta_outer_fold_count": _fold_count_check(
            positive_unit,
        ),
        "positive_mild_settlement_name_recall_delta_outer_fold_count": (
            _fold_count_check(positive_settlement)
        ),
        "settlement_name_positive_recall_outer_fold_count": _fold_count_check(
            positive_settlement_recall,
            minimum=5,
        ),
        "unit_worst_outer_fold_recall": _minimum_check(
            min(v5_unit),
            0.18225197064754597,
        ),
    }
    passed_values = [
        checks["clean_macro_f1"]["passed"],
        checks["clean_settlement_name_recall"]["passed"],
        checks["mild_macro_f1"]["passed"],
        *(check["passed"] for check in checks["mild_recall_floors"].values()),
        *(check["passed"] for check in checks["mild_precision_floors"].values()),
        checks["positive_mild_macro_f1_delta_outer_fold_count"]["passed"],
        checks["positive_mild_unit_recall_delta_outer_fold_count"]["passed"],
        checks["positive_mild_settlement_name_recall_delta_outer_fold_count"]["passed"],
        checks["settlement_name_positive_recall_outer_fold_count"]["passed"],
        checks["unit_worst_outer_fold_recall"]["passed"],
    ]
    all_passed = all(passed_values)
    expected_terminal = "advance_to_prospective_freeze" if all_passed else "mtaac_retired"
    if terminal_status != expected_terminal:
        raise AssertionError("test report terminal status does not match its gates")

    regularizer = {
        "alternate_groupings": False,
        "context_emission_and_bias": "rho_over_2_times_sum_of_squares",
        "coordinate_scope": ("every_corresponding_emission_feature_coefficient_and_emission_bias"),
        "fixed_contrast_multiplier": 2.0,
        "group_contrast_formula": (
            "for_each_pair_and_coordinate_mu_equals_a_plus_b_over_2_"
            "kappa_equals_a_minus_b_over_2_penalty_equals_rho_times_"
            "mu_squared_plus_2_times_kappa_squared"
        ),
        "group_contrast_gradient": (
            "gradient_a_equals_rho_times_(mu_plus_2_times_kappa)_and_"
            "gradient_b_equals_rho_times_(mu_minus_2_times_kappa)"
        ),
        "group_pairs": [["quantity", "unit"], ["person_name", "settlement_name"]],
        "naive_shared_plus_residual_parameterization": False,
        "pooling_weight_grid": False,
        "runtime_tunable_contrast_parameter": False,
        "start_and_transition": "rho_over_2_times_sum_of_squares",
        "version": "v5-fixed-orthogonal-pair-group-contrast-v1",
    }
    return {
        "analysis": "mtaac_v5_group_contrast_crf_development",
        "report_version": "mtaac-v5-development-report-v1",
        "terminal_status": terminal_status,
        "development_only": True,
        "model_executed": True,
        "scientific_metrics_emitted": True,
        "mtaac_retired": True,
        "plan_sha256": V5_DEVELOPMENT_PLAN_SHA256,
        "implementation_commit": "a" * 40,
        "parent_commitments": {
            "evaluation_corpus_sha256": (
                "sha256:e7d6f8c9a8c090bb33ef4ba3703c1b36fe0519086efa75ff70d1ba53a8bf9312"
            ),
            "gateway_version": "mtaac-v2-training-gateway-v1",
            "mtaac_source_commit": "66e0643efd230401210e27db353ebb6d7228b1bb",
            "selected_manifest_sha256": (
                "sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e"
            ),
            "source_archive_sha256": (
                "sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091"
            ),
            "v2_freeze_commit": "37157f1411a55ffd91b7327afaca8fc1080fa708",
            "v2_protocol_sha256": (
                "sha256:25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892"
            ),
            "v2_split_manifest_sha256": (
                "sha256:7249c8fe1d3efc95b42cc9e0a9378550addb64f5b992f89af99dd852b83c5c30"
            ),
            "v3_freeze_commit": "5b39c8ba358ea66e46183cbf02eb07fbc91861e2",
            "v3_plan_sha256": (
                "sha256:b2100318fa0e958d741fd25d7b9263ae1574967f4585f4609c118b1bd16880dd"
            ),
            "v3_result_commit": "9f70679d0c0138d67d000e65ac71e258bcf439e0",
            "v3_result_sha256": (
                "sha256:e40d4802906dbe05b19a8625949f8c9154711a28a687c930d3e31cec2bf124d2"
            ),
            "v4_freeze_commit": "304f8b36a32083330b8af02d21a58382c29d8915",
            "v4_plan_sha256": (
                "sha256:604725a5929b63f578ade07b65ca784eefefce9b827e1686d4836f668c123b"
            ),
            "v4_result_commit": "68332353a86f88e99e46df71fcdd2a4974dba31c",
            "v4_result_sha256": (
                "sha256:4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897"
            ),
        },
        "data_boundary": {
            "model_training_family_count": 271,
            "mtaac_final_attempt": True,
            "regimes_used": ["clean", "mild"],
            "replica_index_used": 0,
            "reserved_validation_source_loaded": False,
            "v2_holdout_exposed_to_model": False,
            "v2_holdout_family_count_excluded": 90,
            "v2_holdout_scored": False,
        },
        "profile_contract": {
            "clean_mild_shared": False,
            "feature_value_types": {
                "local": "fixed_categorical",
                "missing_or_boundary": "fixed_categorical_marker",
                "profile_numeric": "direct_float64_in_closed_unit_interval",
                "type_support": "fixed_categorical",
            },
            "gold_used": False,
            "identity_serialized": False,
            "inference_mode": ("target_batch_partition_regime_local_document_leave_one_family_out"),
            "leave_one_family_out": True,
            "line_template_used": False,
            "local_features": [
                "position_bucket",
                "line_length_bucket",
                "reported_direction",
                "damage",
                "observation_status",
                "previous_equality",
                "next_equality",
                "line_frequency_bucket",
                "seen_before",
                "seen_after",
            ],
            "profile_features": [
                "type_support",
                "type_frequency",
                "family_dispersion",
                "line_dispersion",
                "family_entropy",
                "type_initial_tendency",
                "type_final_tendency",
                "type_mean_position",
                "type_position_variance",
                "left_context_excess_diversity",
                "left_context_entropy",
                "right_context_excess_diversity",
                "right_context_entropy",
                "type_repeat_in_line_rate",
                "type_same_left_rate",
                "type_same_right_rate",
                "left_neighbor_commonness",
                "right_neighbor_commonness",
                "type_evidence",
                "type_diversity_evidence",
                "initial_tendency_interaction",
                "final_tendency_interaction",
                "position_agreement",
                "neighbor_equality_repetition_interaction",
            ],
            "train_validation_shared": False,
            "version": "v4-truth-free-lofo-profile-v1",
        },
        "model_contract": {
            "candidate_count": 1,
            "candidate_selection": "none_fixed_method",
            "class_adjustment_gamma": 0.5,
            "class_prior_smoothing": "family_weighted_jeffreys_alpha_0.5",
            "family_weighting": "inverse_total_clean_mild_family_tokens",
            "l2_rho": 0.01,
            "likelihood": (
                "exact_v4_family_weighted_first_order_linear_chain_crf_conditional_log_likelihood"
            ),
            "optimizer": _optimizer_settings(),
            "parameter_count": (
                "exactly_the_v4_parameter_count_with_no_shared_or_residual_parameters_added"
            ),
            "regularizer": regularizer,
            "states": STATES,
            "v4_refit": False,
            "v5_diagnostics": "none_primary_model_only",
            "version": "v5-fixed-group-contrast-linear-chain-crf-v1",
        },
        "outer_development": {
            "outer_fold_count": 5,
            "fold_assignment_parent": ("exact_v3_and_v4_five_outer_fold_assignments"),
            "outer_folds": folds,
            "out_of_fold_metrics": out_of_fold,
            "paired_v4": {
                "v4_mild_macro_f1": 0.3877588813953674,
                "v4_mild_macro_f1_by_outer_fold": V4_MACRO_BY_FOLD,
                "v5_mild_macro_f1_by_outer_fold": v5_macro,
                "mild_macro_f1_delta_by_outer_fold": macro_deltas,
                "positive_mild_macro_f1_delta_fold_count": positive_macro,
                "v4_mild_unit_recall": 0.30521567409297784,
                "v4_mild_unit_recall_by_outer_fold": V4_UNIT_RECALL_BY_FOLD,
                "v5_mild_unit_recall_by_outer_fold": v5_unit,
                "mild_unit_recall_delta_by_outer_fold": unit_deltas,
                "positive_mild_unit_recall_delta_fold_count": positive_unit,
                "v4_mild_settlement_name_recall": 0.042941913609110954,
                "v4_mild_settlement_name_recall_by_outer_fold": (V4_SETTLEMENT_RECALL_BY_FOLD),
                "v5_mild_settlement_name_recall_by_outer_fold": v5_settlement,
                "mild_settlement_name_recall_delta_by_outer_fold": (settlement_deltas),
                "positive_mild_settlement_name_recall_delta_fold_count": (positive_settlement),
            },
        },
        "gate_decision": {
            "terminal_status": terminal_status,
            "all_passed": all_passed,
            "comparison_tolerance": COMPARISON_TOLERANCE,
            "minimum_gate_rule": ("observed_greater_than_or_equal_to_minimum_minus_tolerance"),
            "mtaac_retired": True,
            "positive_delta_rule": "delta_strictly_greater_than_tolerance",
            "strict_positive_recall_rule": ("recall_strictly_greater_than_tolerance"),
            "checks": checks,
        },
        "final_development_model": {
            "fitted": advanced,
            "fit_rule": ("fit_all_271_families_only_after_advance_to_prospective_freeze"),
            "model_state_commitment": "sha256:" + "e" * 64 if advanced else None,
            "optimizer": _optimizer_run() if advanced else None,
        },
        "claim_scope": {
            "class": "development_only",
            "eligible_as_binding_confirmation": False,
            "eligible_as_decipherment": False,
            "eligible_as_reserved_validation_result": False,
            "eligible_as_v2_holdout_result": False,
            "individual_predictions_published": False,
            "prospective_execution_requires_separate_public_freeze": True,
        },
    }


class V5DevelopmentReportSchemaTests(unittest.TestCase):
    def test_advance_and_retired_reports_match_the_closed_schema(self) -> None:
        for terminal_status in (
            "advance_to_prospective_freeze",
            "mtaac_retired",
        ):
            with self.subTest(terminal_status=terminal_status):
                self.assertEqual(
                    [],
                    validate_schema_instance(
                        _report(terminal_status=terminal_status),
                        SCHEMA,
                    ),
                )

    def test_schema_rejects_unknown_identifier_path_and_nested_fields(self) -> None:
        cases = []

        identifier = _report()
        identifier["document_id"] = "forbidden"
        cases.append(identifier)

        local_path = _report()
        local_path["outer_development"]["outer_folds"][0]["support"]["local_path"] = (
            "/private/source"
        )
        cases.append(local_path)

        host = _report()
        host["outer_development"]["outer_folds"][0]["optimizer"]["host"] = "internal-host"
        cases.append(host)

        unknown_nested = _report()
        unknown_nested["gate_decision"]["checks"]["mild_precision_floors"]["note"] = "aggregate"
        cases.append(unknown_nested)

        for changed in cases:
            with self.subTest(changed=changed):
                self.assertTrue(validate_schema_instance(changed, SCHEMA))

    def test_schema_enforces_terminal_model_and_gate_consistency(self) -> None:
        advance_without_model = _report()
        advance_without_model["final_development_model"] = {
            "fitted": False,
            "fit_rule": ("fit_all_271_families_only_after_advance_to_prospective_freeze"),
            "model_state_commitment": None,
            "optimizer": None,
        }
        self.assertTrue(validate_schema_instance(advance_without_model, SCHEMA))

        retired_with_model = _report(terminal_status="mtaac_retired")
        retired_with_model["final_development_model"] = copy.deepcopy(
            _report()["final_development_model"],
        )
        self.assertTrue(validate_schema_instance(retired_with_model, SCHEMA))

        mismatched_gate = _report()
        mismatched_gate["gate_decision"]["terminal_status"] = "mtaac_retired"
        self.assertTrue(validate_schema_instance(mismatched_gate, SCHEMA))

    def test_schema_requires_fold_and_oof_aggregate_confusion(self) -> None:
        missing_fold_confusion = _report()
        del missing_fold_confusion["outer_development"]["outer_folds"][0]["metrics"]["mild"][
            "weighted_confusion_matrix"
        ]
        self.assertTrue(validate_schema_instance(missing_fold_confusion, SCHEMA))

        missing_oof_confusion = _report()
        del missing_oof_confusion["outer_development"]["out_of_fold_metrics"]["clean"][
            "weighted_confusion_matrix"
        ]
        self.assertTrue(validate_schema_instance(missing_oof_confusion, SCHEMA))

    def test_schema_binds_v4_result_and_plan_commitments(self) -> None:
        changed_result = _report()
        changed_result["parent_commitments"]["v4_result_sha256"] = "sha256:" + "f" * 64
        self.assertTrue(validate_schema_instance(changed_result, SCHEMA))

        changed_plan = _report()
        changed_plan["plan_sha256"] = "sha256:" + "f" * 64
        self.assertTrue(validate_schema_instance(changed_plan, SCHEMA))

        changed_regularizer = _report()
        changed_regularizer["model_contract"]["regularizer"]["fixed_contrast_multiplier"] = 1.5
        self.assertTrue(validate_schema_instance(changed_regularizer, SCHEMA))


if __name__ == "__main__":
    unittest.main()
