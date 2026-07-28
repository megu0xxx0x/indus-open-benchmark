"""Network-free, no-replace CLI for the final MTAAC V5 development run."""

from __future__ import annotations

import argparse
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from indusbench.schema_validation import validate_schema_instance
from indusbench.v3dev.contracts import V3StructuralState
from indusbench.v3dev.metrics import add_confusion_matrices, metrics_from_confusion
from indusbench.v4dev_cli import (
    V4DevelopmentCLIError as _V4DevelopmentCLIError,
)
from indusbench.v4dev_cli import (
    _output_exists as _v4_output_exists,
)
from indusbench.v4dev_cli import (
    _read_regular_bytes as _v4_read_regular_bytes,
)
from indusbench.v4dev_cli import (
    _validate_public_value as _v4_validate_public_value,
)
from indusbench.v4dev_cli import (
    _write_no_replace as _v4_write_no_replace,
)
from indusbench.v5dev.plan import (
    MAX_V5_DEVELOPMENT_PLAN_BYTES,
    V5_DEVELOPMENT_PLAN_SHA256,
    V5DevelopmentPlanError,
    validate_v5_development_plan,
)
from indusbench.v5dev.sequence import V5_CRF_MODEL_VERSION

MAX_MTAAC_V5_ARCHIVE_BYTES: Final = 256 * 1024 * 1024
MAX_MTAAC_V5_REPORT_BYTES: Final = 2 * 1024 * 1024
MTAAC_V5_REPORT_VERSION: Final = "mtaac-v5-development-report-v1"
MTAAC_V5_REPORT_SCHEMA: Final = "mtaac-v5-development-report.schema.json"

_COMPARISON_TOLERANCE: Final = 1e-12
_MILD_MACRO_F1_MINIMUM: Final = 0.3977588813953674
_MILD_RECALL_FLOORS: Final = {
    "context_only": 0.520654531441017,
    "quantity": 0.1765055025096581,
    "unit": 0.3767836311289388,
    "person_name": 0.4988092152820551,
    "settlement_name": 0.15,
}
_MILD_PRECISION_FLOORS: Final = {
    "unit": 0.3512887014608468,
    "settlement_name": 0.20747537967348736,
}
_CLEAN_MACRO_F1_MINIMUM: Final = 0.4680972874281771
_CLEAN_SETTLEMENT_RECALL_MINIMUM: Final = 0.10
_POSITIVE_DELTA_FOLD_MINIMUM: Final = 4
_SETTLEMENT_POSITIVE_RECALL_FOLD_MINIMUM: Final = 5
_UNIT_WORST_FOLD_RECALL_MINIMUM: Final = 0.18225197064754597

_V4_MILD_MACRO_F1: Final = 0.3877588813953674
_V4_MILD_UNIT_RECALL: Final = 0.30521567409297784
_V4_MILD_SETTLEMENT_RECALL: Final = 0.042941913609110954
_V4_MILD_MACRO_F1_BY_OUTER_FOLD: Final = (
    0.3756051787768944,
    0.3998966341462856,
    0.3615261061386301,
    0.39294354710818963,
    0.39901832092281697,
)
_V4_MILD_UNIT_RECALL_BY_OUTER_FOLD: Final = (
    0.18225197064754597,
    0.2892249319203195,
    0.2772641078805165,
    0.39686535349113794,
    0.35585102688488385,
)
_V4_MILD_SETTLEMENT_RECALL_BY_OUTER_FOLD: Final = (
    0.0,
    0.09932569269976571,
    0.003780194718492515,
    0.06366234989790896,
    0.05568829861391914,
)
_EXPECTED_VALIDATION_FAMILY_COUNTS: Final = (52, 54, 55, 53, 57)
_EXPECTED_TRAIN_FAMILY_COUNTS: Final = (219, 217, 216, 218, 214)
_STATES: Final = (
    "context_only",
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
)

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_TAGGED_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_PUBLIC_REPORT_KEYS: Final = frozenset(
    {
        "analysis",
        "report_version",
        "terminal_status",
        "development_only",
        "model_executed",
        "scientific_metrics_emitted",
        "mtaac_retired",
        "plan_sha256",
        "implementation_commit",
        "parent_commitments",
        "data_boundary",
        "profile_contract",
        "model_contract",
        "outer_development",
        "gate_decision",
        "final_development_model",
        "claim_scope",
    }
)
_V5_FORBIDDEN_PUBLIC_KEYS: Final = frozenset(
    {
        "account",
        "account_id",
        "account_name",
        "deployment_identifier",
        "host",
        "host_name",
        "hostname",
        "identifier",
        "identifiers",
        "ip_address",
        "item_id",
        "item_ids",
        "network_address",
        "server",
        "user_name",
        "username",
    }
)
_EXPECTED_PARENT_COMMITMENTS: Final = {
    "gateway_version": "mtaac-v2-training-gateway-v1",
    "mtaac_source_commit": "66e0643efd230401210e27db353ebb6d7228b1bb",
    "v2_freeze_commit": "37157f1411a55ffd91b7327afaca8fc1080fa708",
    "source_archive_sha256": (
        "sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091"
    ),
    "selected_manifest_sha256": (
        "sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e"
    ),
    "evaluation_corpus_sha256": (
        "sha256:e7d6f8c9a8c090bb33ef4ba3703c1b36fe0519086efa75ff70d1ba53a8bf9312"
    ),
    "v2_protocol_sha256": (
        "sha256:25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892"
    ),
    "v2_split_manifest_sha256": (
        "sha256:7249c8fe1d3efc95b42cc9e0a9378550addb64f5b992f89af99dd852b83c5c30"
    ),
    "v3_freeze_commit": "5b39c8ba358ea66e46183cbf02eb07fbc91861e2",
    "v3_result_commit": "9f70679d0c0138d67d000e65ac71e258bcf439e0",
    "v3_plan_sha256": ("sha256:b2100318fa0e958d741fd25d7b9263ae1574967f4585f4609c118b1bd16880dd"),
    "v3_result_sha256": ("sha256:e40d4802906dbe05b19a8625949f8c9154711a28a687c930d3e31cec2bf124d2"),
    "v4_freeze_commit": "304f8b36a32083330b8af02d21a58382c29d8915",
    "v4_result_commit": "68332353a86f88e99e46df71fcdd2a4974dba31c",
    "v4_plan_sha256": ("sha256:604725a5929b63f578ade07b65ca784eefefce9b827e1686d4836f668c123b"),
    "v4_result_sha256": ("sha256:4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897"),
}
_EXPECTED_DATA_BOUNDARY: Final = {
    "model_training_family_count": 271,
    "v2_holdout_family_count_excluded": 90,
    "v2_holdout_exposed_to_model": False,
    "v2_holdout_scored": False,
    "reserved_validation_source_loaded": False,
    "regimes_used": ["clean", "mild"],
    "replica_index_used": 0,
    "mtaac_final_attempt": True,
}
_LOCAL_FEATURES: Final = [
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
]
_PROFILE_FEATURES: Final = [
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
]
_EXPECTED_PROFILE_CONTRACT: Final = {
    "version": "v4-truth-free-lofo-profile-v1",
    "inference_mode": "target_batch_partition_regime_local_document_leave_one_family_out",
    "local_features": _LOCAL_FEATURES,
    "profile_features": _PROFILE_FEATURES,
    "feature_value_types": {
        "local": "fixed_categorical",
        "type_support": "fixed_categorical",
        "profile_numeric": "direct_float64_in_closed_unit_interval",
        "missing_or_boundary": "fixed_categorical_marker",
    },
    "line_template_used": False,
    "gold_used": False,
    "identity_serialized": False,
    "train_validation_shared": False,
    "clean_mild_shared": False,
    "leave_one_family_out": True,
}
_EXPECTED_OPTIMIZER: Final = {
    "numeric_type": "float64",
    "batch": "full",
    "stable_logsumexp": "maximum_shift",
    "summation": "sorted_math_fsum",
    "history_size": 10,
    "maximum_accepted_iterations": 100,
    "direction": "deterministic_lbfgs_two_loop_recursion",
    "non_descent_policy": ("clear_history_once_then_use_negative_gradient_repeat_is_hard_error"),
    "curvature_pair_acceptance": ("s_dot_y_strictly_greater_than_1e-12_times_norm_s_times_norm_y"),
    "armijo": {
        "initial_step": 1.0,
        "c1": 0.0001,
        "contraction_factor": 0.5,
        "maximum_trials": 31,
        "minimum_step": 9.313225746154785e-10,
    },
    "convergence": {
        "gradient_infinity_norm": 1e-5,
        "relative_objective": 1e-9,
        "consecutive_relative_objective_iterations": 5,
        "secondary_gradient_infinity_norm": 1e-3,
    },
    "fallback": False,
}
_EXPECTED_MODEL_CONTRACT: Final = {
    "version": V5_CRF_MODEL_VERSION,
    "states": [
        "context_only",
        "quantity",
        "unit",
        "person_name",
        "settlement_name",
    ],
    "candidate_count": 1,
    "candidate_selection": "none_fixed_method",
    "l2_rho": 0.01,
    "class_adjustment_gamma": 0.5,
    "class_prior_smoothing": "family_weighted_jeffreys_alpha_0.5",
    "optimizer": _EXPECTED_OPTIMIZER,
    "family_weighting": "inverse_total_clean_mild_family_tokens",
    "likelihood": (
        "exact_v4_family_weighted_first_order_linear_chain_crf_conditional_log_likelihood"
    ),
    "parameter_count": (
        "exactly_the_v4_parameter_count_with_no_shared_or_residual_parameters_added"
    ),
    "regularizer": {
        "version": "v5-fixed-orthogonal-pair-group-contrast-v1",
        "group_pairs": [
            ["quantity", "unit"],
            ["person_name", "settlement_name"],
        ],
        "coordinate_scope": ("every_corresponding_emission_feature_coefficient_and_emission_bias"),
        "group_contrast_formula": (
            "for_each_pair_and_coordinate_mu_equals_a_plus_b_over_2_"
            "kappa_equals_a_minus_b_over_2_penalty_equals_rho_times_"
            "mu_squared_plus_2_times_kappa_squared"
        ),
        "group_contrast_gradient": (
            "gradient_a_equals_rho_times_(mu_plus_2_times_kappa)_and_"
            "gradient_b_equals_rho_times_(mu_minus_2_times_kappa)"
        ),
        "fixed_contrast_multiplier": 2.0,
        "context_emission_and_bias": "rho_over_2_times_sum_of_squares",
        "start_and_transition": "rho_over_2_times_sum_of_squares",
        "pooling_weight_grid": False,
        "alternate_groupings": False,
        "runtime_tunable_contrast_parameter": False,
        "naive_shared_plus_residual_parameterization": False,
    },
    "v4_refit": False,
    "v5_diagnostics": "none_primary_model_only",
}
_EXPECTED_CLAIM_SCOPE: Final = {
    "class": "development_only",
    "eligible_as_reserved_validation_result": False,
    "eligible_as_v2_holdout_result": False,
    "eligible_as_binding_confirmation": False,
    "eligible_as_decipherment": False,
    "individual_predictions_published": False,
    "prospective_execution_requires_separate_public_freeze": True,
}


class V5DevelopmentCLIError(ValueError):
    """Raised when V5 CLI data cannot cross the public output boundary."""


def _report_schema_path() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / MTAAC_V5_REPORT_SCHEMA
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        f"schemas/{MTAAC_V5_REPORT_SCHEMA}"
    )
    if not package_candidate.is_file():
        raise V5DevelopmentCLIError("the closed V5 report schema is unavailable")
    return Path(str(package_candidate))


def _validate_closed_schema(report: object) -> None:
    try:
        issues = validate_schema_instance(report, _report_schema_path())
    except V5DevelopmentCLIError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise V5DevelopmentCLIError("the closed V5 report schema could not be applied") from error
    if issues:
        raise V5DevelopmentCLIError("V5 report does not match the closed schema")


def _canonical_json(value: object) -> bytes:
    try:
        raw = (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise V5DevelopmentCLIError("V5 report is not canonical JSON data") from error
    if len(raw) > MAX_MTAAC_V5_REPORT_BYTES:
        raise V5DevelopmentCLIError("V5 report exceeds the public byte limit")
    return raw


def _validate_public_value(value: object) -> None:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            for key, nested in current.items():
                if not isinstance(key, str):
                    raise V5DevelopmentCLIError("V5 report keys must be strings")
                normalized = key.casefold().replace("-", "_")
                if (
                    normalized in _V5_FORBIDDEN_PUBLIC_KEYS
                    or normalized.endswith("_account")
                    or normalized.endswith("_hostname")
                    or normalized.endswith("_identifier")
                    or normalized.endswith("_identifiers")
                ):
                    raise V5DevelopmentCLIError(
                        "V5 report contains deployment or item identity data"
                    )
                pending.append(nested)
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    try:
        _v4_validate_public_value(value, budget=[0])
    except _V4DevelopmentCLIError as error:
        raise V5DevelopmentCLIError("V5 report failed the recursive public boundary") from error


def _mapping(value: object, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V5DevelopmentCLIError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _list(value: object, *, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise V5DevelopmentCLIError(f"{field_name} must be an array")
    return value


def _metric_confusion(
    metrics: Mapping[str, Any],
) -> Mapping[V3StructuralState, Mapping[V3StructuralState, float]]:
    confusion = metrics.get("weighted_confusion_matrix")
    if not isinstance(confusion, Mapping):
        raise V5DevelopmentCLIError("scientific metric lacks a confusion matrix")
    return cast(
        Mapping[V3StructuralState, Mapping[V3StructuralState, float]],
        confusion,
    )


def _recompute_metric_report(value: object) -> dict[str, Any]:
    metrics = _mapping(value, field_name="scientific metric")
    recomputed = metrics_from_confusion(_metric_confusion(metrics))
    if metrics != recomputed:
        raise V5DevelopmentCLIError("scientific metrics do not match their confusion matrix")
    return recomputed


def _per_state(metrics: Mapping[str, Any]) -> Mapping[str, Mapping[str, float]]:
    value = metrics.get("per_state")
    if not isinstance(value, Mapping):
        raise V5DevelopmentCLIError("metric report lacks per-state metrics")
    return cast(Mapping[str, Mapping[str, float]], value)


def _minimum_check(observed: float | int, minimum: float | int) -> dict[str, Any]:
    return {
        "observed": observed,
        "minimum": minimum,
        "passed": observed >= minimum - _COMPARISON_TOLERANCE,
    }


def _validate_optimizer_summary(value: object, *, field_name: str) -> None:
    optimizer = _mapping(value, field_name=field_name)
    iterations = optimizer.get("accepted_iterations")
    gradient = optimizer.get("final_gradient_infinity_norm")
    objective = optimizer.get("final_objective")
    termination = optimizer.get("termination_reason")
    if (
        optimizer.get("converged") is not True
        or type(iterations) is not int
        or iterations < 0
        or iterations > 100
        or not isinstance(gradient, (int, float))
        or isinstance(gradient, bool)
        or not math.isfinite(float(gradient))
        or float(gradient) < 0.0
        or not isinstance(objective, (int, float))
        or isinstance(objective, bool)
        or not math.isfinite(float(objective))
    ):
        raise V5DevelopmentCLIError("optimizer summary is malformed")
    if termination == "gradient_infinity_norm":
        if float(gradient) > 1e-5:
            raise V5DevelopmentCLIError("gradient termination does not meet the frozen tolerance")
    elif termination == "relative_objective_stability":
        if iterations < 5 or float(gradient) > 1e-3:
            raise V5DevelopmentCLIError(
                "relative-objective termination does not meet the frozen contract"
            )
    else:
        raise V5DevelopmentCLIError("optimizer termination reason is unsupported")


def _recomputed_gate(
    *,
    clean: Mapping[str, Any],
    mild: Mapping[str, Any],
    paired: Mapping[str, Any],
) -> dict[str, Any]:
    clean_per_state = _per_state(clean)
    mild_per_state = _per_state(mild)
    settlement_by_fold = cast(
        list[float],
        paired["v5_mild_settlement_name_recall_by_outer_fold"],
    )
    unit_by_fold = cast(list[float], paired["v5_mild_unit_recall_by_outer_fold"])
    settlement_positive_count = sum(value > _COMPARISON_TOLERANCE for value in settlement_by_fold)
    checks: dict[str, Any] = {
        "mild_macro_f1": _minimum_check(
            float(mild["macro_f1"]),
            _MILD_MACRO_F1_MINIMUM,
        ),
        "mild_recall_floors": {
            state: _minimum_check(
                float(mild_per_state[state]["recall"]),
                minimum,
            )
            for state, minimum in _MILD_RECALL_FLOORS.items()
        },
        "mild_precision_floors": {
            state: _minimum_check(
                float(mild_per_state[state]["precision"]),
                minimum,
            )
            for state, minimum in _MILD_PRECISION_FLOORS.items()
        },
        "clean_macro_f1": _minimum_check(
            float(clean["macro_f1"]),
            _CLEAN_MACRO_F1_MINIMUM,
        ),
        "clean_settlement_name_recall": _minimum_check(
            float(clean_per_state["settlement_name"]["recall"]),
            _CLEAN_SETTLEMENT_RECALL_MINIMUM,
        ),
        "positive_mild_macro_f1_delta_outer_fold_count": _minimum_check(
            int(paired["positive_mild_macro_f1_delta_fold_count"]),
            _POSITIVE_DELTA_FOLD_MINIMUM,
        ),
        "positive_mild_unit_recall_delta_outer_fold_count": _minimum_check(
            int(paired["positive_mild_unit_recall_delta_fold_count"]),
            _POSITIVE_DELTA_FOLD_MINIMUM,
        ),
        "positive_mild_settlement_name_recall_delta_outer_fold_count": (
            _minimum_check(
                int(paired["positive_mild_settlement_name_recall_delta_fold_count"]),
                _POSITIVE_DELTA_FOLD_MINIMUM,
            )
        ),
        "settlement_name_positive_recall_outer_fold_count": _minimum_check(
            settlement_positive_count,
            _SETTLEMENT_POSITIVE_RECALL_FOLD_MINIMUM,
        ),
        "unit_worst_outer_fold_recall": _minimum_check(
            min(unit_by_fold),
            _UNIT_WORST_FOLD_RECALL_MINIMUM,
        ),
    }
    all_passed = all(
        (
            checks["mild_macro_f1"]["passed"],
            *(check["passed"] for check in checks["mild_recall_floors"].values()),
            *(check["passed"] for check in checks["mild_precision_floors"].values()),
            checks["clean_macro_f1"]["passed"],
            checks["clean_settlement_name_recall"]["passed"],
            checks["positive_mild_macro_f1_delta_outer_fold_count"]["passed"],
            checks["positive_mild_unit_recall_delta_outer_fold_count"]["passed"],
            checks["positive_mild_settlement_name_recall_delta_outer_fold_count"]["passed"],
            checks["settlement_name_positive_recall_outer_fold_count"]["passed"],
            checks["unit_worst_outer_fold_recall"]["passed"],
        )
    )
    return {
        "terminal_status": ("advance_to_prospective_freeze" if all_passed else "mtaac_retired"),
        "all_passed": all_passed,
        "mtaac_retired": True,
        "comparison_tolerance": _COMPARISON_TOLERANCE,
        "minimum_gate_rule": ("observed_greater_than_or_equal_to_minimum_minus_tolerance"),
        "positive_delta_rule": "delta_strictly_greater_than_tolerance",
        "strict_positive_recall_rule": ("recall_strictly_greater_than_tolerance"),
        "checks": checks,
    }


def _validate_scientific_consistency(report: Mapping[str, Any]) -> None:
    """Recompute every V5 aggregate, paired delta, gate, and terminal state."""

    try:
        outer = _mapping(report["outer_development"], field_name="outer development")
        folds = _list(outer["outer_folds"], field_name="outer folds")
        if len(folds) != 5:
            raise V5DevelopmentCLIError("outer development must contain five folds")

        clean_confusions: list[Mapping[V3StructuralState, Mapping[V3StructuralState, float]]] = []
        mild_confusions: list[Mapping[V3StructuralState, Mapping[V3StructuralState, float]]] = []
        macro_by_fold: list[float] = []
        unit_by_fold: list[float] = []
        settlement_by_fold: list[float] = []
        validation_family_counts: list[int] = []
        state_totals_by_fold: dict[str, list[int]] = {state: [] for state in _STATES}
        validation_state_sums: dict[str, int] = {state: 0 for state in _STATES}

        for fold_index, fold_value in enumerate(folds):
            fold = _mapping(fold_value, field_name="outer fold")
            if fold.get("outer_fold_index") != fold_index:
                raise V5DevelopmentCLIError("outer fold indexes are not canonical")
            _validate_optimizer_summary(
                fold.get("optimizer"),
                field_name="outer-fold optimizer",
            )
            support = _mapping(fold["support"], field_name="outer-fold support")
            train_count = support.get("train_family_count")
            validation_count = support.get("validation_family_count")
            if (
                type(train_count) is not int
                or type(validation_count) is not int
                or train_count != _EXPECTED_TRAIN_FAMILY_COUNTS[fold_index]
                or validation_count != _EXPECTED_VALIDATION_FAMILY_COUNTS[fold_index]
                or train_count + validation_count != 271
            ):
                raise V5DevelopmentCLIError(
                    "outer-fold support does not match the fixed assignment"
                )
            validation_family_counts.append(validation_count)
            train_state_support = _mapping(
                support.get("train_state_support"),
                field_name="training state support",
            )
            validation_state_support = _mapping(
                support.get("validation_state_support"),
                field_name="validation state support",
            )
            if set(train_state_support) != set(_STATES) or set(validation_state_support) != set(
                _STATES
            ):
                raise V5DevelopmentCLIError(
                    "outer-fold state support does not cover the five states"
                )
            for state in _STATES:
                train_state_count = train_state_support[state]
                validation_state_count = validation_state_support[state]
                if (
                    type(train_state_count) is not int
                    or type(validation_state_count) is not int
                    or train_state_count <= 0
                    or validation_state_count <= 0
                ):
                    raise V5DevelopmentCLIError(
                        "outer-fold state support must be positive integer counts"
                    )
                state_totals_by_fold[state].append(train_state_count + validation_state_count)
                validation_state_sums[state] += validation_state_count
            metrics = _mapping(fold["metrics"], field_name="outer-fold metrics")
            clean = _recompute_metric_report(metrics["clean"])
            mild = _recompute_metric_report(metrics["mild"])
            for regime_metrics in (clean, mild):
                if not math.isclose(
                    float(regime_metrics["total_family_mass"]),
                    float(validation_count),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                ):
                    raise V5DevelopmentCLIError(
                        "outer-fold metric mass does not match validation support"
                    )
            clean_confusions.append(_metric_confusion(clean))
            mild_confusions.append(_metric_confusion(mild))
            mild_per_state = _per_state(mild)
            macro_by_fold.append(float(mild["macro_f1"]))
            unit_by_fold.append(float(mild_per_state["unit"]["recall"]))
            settlement_by_fold.append(float(mild_per_state["settlement_name"]["recall"]))

        recomputed_clean = metrics_from_confusion(add_confusion_matrices(clean_confusions))
        recomputed_mild = metrics_from_confusion(add_confusion_matrices(mild_confusions))
        support_partition_invalid = any(
            len(set(state_totals_by_fold[state])) != 1
            or validation_state_sums[state] != state_totals_by_fold[state][0]
            for state in _STATES
        )
        if (
            sum(validation_family_counts) != 271
            or support_partition_invalid
            or not math.isclose(
                float(recomputed_clean["total_family_mass"]),
                271.0,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
            or not math.isclose(
                float(recomputed_mild["total_family_mass"]),
                271.0,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        ):
            raise V5DevelopmentCLIError("out-of-fold metric mass does not cover 271 families")
        if outer["out_of_fold_metrics"] != {
            "clean": recomputed_clean,
            "mild": recomputed_mild,
        }:
            raise V5DevelopmentCLIError(
                "out-of-fold metrics do not match summed fold confusion matrices"
            )

        macro_deltas = [
            current - baseline
            for current, baseline in zip(
                macro_by_fold,
                _V4_MILD_MACRO_F1_BY_OUTER_FOLD,
                strict=True,
            )
        ]
        unit_deltas = [
            current - baseline
            for current, baseline in zip(
                unit_by_fold,
                _V4_MILD_UNIT_RECALL_BY_OUTER_FOLD,
                strict=True,
            )
        ]
        settlement_deltas = [
            current - baseline
            for current, baseline in zip(
                settlement_by_fold,
                _V4_MILD_SETTLEMENT_RECALL_BY_OUTER_FOLD,
                strict=True,
            )
        ]
        expected_paired = {
            "v4_mild_macro_f1": _V4_MILD_MACRO_F1,
            "v4_mild_unit_recall": _V4_MILD_UNIT_RECALL,
            "v4_mild_settlement_name_recall": _V4_MILD_SETTLEMENT_RECALL,
            "v4_mild_macro_f1_by_outer_fold": list(_V4_MILD_MACRO_F1_BY_OUTER_FOLD),
            "v4_mild_unit_recall_by_outer_fold": list(_V4_MILD_UNIT_RECALL_BY_OUTER_FOLD),
            "v4_mild_settlement_name_recall_by_outer_fold": list(
                _V4_MILD_SETTLEMENT_RECALL_BY_OUTER_FOLD
            ),
            "v5_mild_macro_f1_by_outer_fold": macro_by_fold,
            "v5_mild_unit_recall_by_outer_fold": unit_by_fold,
            "v5_mild_settlement_name_recall_by_outer_fold": settlement_by_fold,
            "mild_macro_f1_delta_by_outer_fold": macro_deltas,
            "mild_unit_recall_delta_by_outer_fold": unit_deltas,
            "mild_settlement_name_recall_delta_by_outer_fold": settlement_deltas,
            "positive_mild_macro_f1_delta_fold_count": sum(
                delta > _COMPARISON_TOLERANCE for delta in macro_deltas
            ),
            "positive_mild_unit_recall_delta_fold_count": sum(
                delta > _COMPARISON_TOLERANCE for delta in unit_deltas
            ),
            "positive_mild_settlement_name_recall_delta_fold_count": sum(
                delta > _COMPARISON_TOLERANCE for delta in settlement_deltas
            ),
        }
        paired = _mapping(outer["paired_v4"], field_name="paired V4 comparison")
        if paired != expected_paired:
            raise V5DevelopmentCLIError("paired V4 comparison does not recompute")

        expected_gate = _recomputed_gate(
            clean=recomputed_clean,
            mild=recomputed_mild,
            paired=expected_paired,
        )
        if report["gate_decision"] != expected_gate:
            raise V5DevelopmentCLIError("V5 gates do not recompute")
        if report["terminal_status"] != expected_gate["terminal_status"]:
            raise V5DevelopmentCLIError("V5 terminal status does not recompute")
    except V5DevelopmentCLIError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise V5DevelopmentCLIError("V5 scientific aggregates are malformed") from error


def _validate_terminal_consistency(report: Mapping[str, Any]) -> None:
    terminal_status = report["terminal_status"]
    gate = _mapping(report["gate_decision"], field_name="gate decision")
    final_model = _mapping(
        report["final_development_model"],
        field_name="final development model",
    )
    if gate.get("terminal_status") != terminal_status:
        raise V5DevelopmentCLIError("gate and report terminal states disagree")
    if gate.get("mtaac_retired") is not True or report["mtaac_retired"] is not True:
        raise V5DevelopmentCLIError("V5 report does not retire MTAAC")
    if terminal_status == "advance_to_prospective_freeze":
        commitment = final_model.get("model_state_commitment")
        if (
            gate.get("all_passed") is not True
            or final_model.get("fitted") is not True
            or not isinstance(commitment, str)
            or _TAGGED_SHA256.fullmatch(commitment) is None
            or not isinstance(final_model.get("optimizer"), Mapping)
        ):
            raise V5DevelopmentCLIError("advance report does not satisfy the closed gate")
        _validate_optimizer_summary(
            final_model.get("optimizer"),
            field_name="final-model optimizer",
        )
    elif terminal_status == "mtaac_retired":
        if (
            gate.get("all_passed") is not False
            or final_model.get("fitted") is not False
            or final_model.get("model_state_commitment") is not None
            or final_model.get("optimizer") is not None
        ):
            raise V5DevelopmentCLIError("retired report does not satisfy the closed gate")
    else:
        raise V5DevelopmentCLIError("V5 terminal status is unsupported")


def validate_public_development_report(
    report: object,
    *,
    expected_implementation_commit: str | None = None,
) -> dict[str, Any]:
    """Enforce the aggregate-only V5 report boundary before publication."""

    if not isinstance(report, dict) or set(report) != _PUBLIC_REPORT_KEYS:
        raise V5DevelopmentCLIError("V5 report root does not match the closed contract")
    if (
        report["analysis"] != "mtaac_v5_group_contrast_crf_development"
        or report["report_version"] != MTAAC_V5_REPORT_VERSION
        or report["terminal_status"] not in {"advance_to_prospective_freeze", "mtaac_retired"}
        or report["development_only"] is not True
        or report["model_executed"] is not True
        or report["scientific_metrics_emitted"] is not True
        or report["mtaac_retired"] is not True
        or report["plan_sha256"] != V5_DEVELOPMENT_PLAN_SHA256
        or not isinstance(report["implementation_commit"], str)
        or _COMMIT.fullmatch(report["implementation_commit"]) is None
        or (
            expected_implementation_commit is not None
            and report["implementation_commit"] != expected_implementation_commit
        )
    ):
        raise V5DevelopmentCLIError("V5 report assertions do not match the plan")
    for field_name in (
        "parent_commitments",
        "data_boundary",
        "profile_contract",
        "model_contract",
        "outer_development",
        "gate_decision",
        "final_development_model",
        "claim_scope",
    ):
        if not isinstance(report[field_name], dict):
            raise V5DevelopmentCLIError("V5 report aggregate sections must be objects")
    if report["parent_commitments"] != _EXPECTED_PARENT_COMMITMENTS:
        raise V5DevelopmentCLIError("V5 parent commitments disagree")
    if report["data_boundary"] != _EXPECTED_DATA_BOUNDARY:
        raise V5DevelopmentCLIError("V5 data boundary assertions disagree")
    if report["profile_contract"] != _EXPECTED_PROFILE_CONTRACT:
        raise V5DevelopmentCLIError("V5 profile contract disagrees")
    if report["model_contract"] != _EXPECTED_MODEL_CONTRACT:
        raise V5DevelopmentCLIError("V5 model contract disagrees")
    if report["claim_scope"] != _EXPECTED_CLAIM_SCOPE:
        raise V5DevelopmentCLIError("V5 claim scope disagrees")
    _validate_terminal_consistency(report)
    _validate_closed_schema(report)
    _validate_scientific_consistency(report)
    _validate_public_value(report)
    _canonical_json(report)
    return report


def _read_regular_bytes(path: Path, *, max_bytes: int) -> bytes:
    try:
        return _v4_read_regular_bytes(path, max_bytes=max_bytes)
    except _V4DevelopmentCLIError as error:
        raise V5DevelopmentCLIError("input could not be read safely") from error


def _output_exists(path: Path) -> bool:
    return _v4_output_exists(path)


def _write_no_replace(path: Path, raw: bytes) -> None:
    _v4_write_no_replace(path, raw)


def _build_training_bundle(archive_bytes: bytes) -> Any:
    from indusbench.v3dev.mtaac_training import build_mtaac_v2_training_bundle

    return build_mtaac_v2_training_bundle(archive_bytes)


def _run_v5_development(
    bundle: Any,
    *,
    plan_bytes: bytes,
    implementation_commit: str,
) -> dict[str, Any]:
    from indusbench.v5dev.runner import run_v5_development

    return run_v5_development(
        bundle,
        plan_bytes=plan_bytes,
        implementation_commit=implementation_commit,
    )


def _print_json(value: object) -> None:
    sys.stdout.write(_canonical_json(value).decode("utf-8"))


def _fail(error_code: str, message: str, *, status: int = 2) -> int:
    _print_json(
        {
            "analysis": "mtaac_v5_group_contrast_crf_development",
            "development_only": True,
            "error": message,
            "error_code": error_code,
            "model_executed": False,
            "mtaac_retired": True,
            "scientific_metrics_emitted": False,
            "terminal_status": "error",
        }
    )
    return status


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="indusbench-v5dev-mtaac",
        description="Run the exact final development-only MTAAC V5 plan.",
    )
    parser.add_argument("archive", type=Path, help="local exact pinned MTAAC archive")
    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
        help="local exact frozen MTAAC V5 development plan",
    )
    parser.add_argument(
        "--implementation-commit",
        required=True,
        help="published lowercase 40-hex implementation commit",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new aggregate JSON report path; existing paths are never replaced",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the one-purpose V5 CLI with path-redacted failures."""

    args = _parser().parse_args(list(argv) if argv is not None else None)
    if _COMMIT.fullmatch(args.implementation_commit) is None:
        return _fail(
            "implementation_commit_invalid",
            "the implementation commit must be lowercase 40-hex",
        )
    try:
        if _output_exists(args.output):
            return _fail(
                "output_exists",
                "the aggregate output target already exists",
                status=1,
            )
    except (OSError, ValueError):
        return _fail(
            "output_uninspectable",
            "the aggregate output target could not be inspected safely",
        )

    try:
        plan_bytes = _read_regular_bytes(
            args.plan,
            max_bytes=MAX_V5_DEVELOPMENT_PLAN_BYTES,
        )
    except (OSError, ValueError):
        return _fail("plan_unreadable", "the V5 plan could not be read safely")
    try:
        validate_v5_development_plan(plan_bytes)
    except V5DevelopmentPlanError:
        return _fail("plan_rejected", "the V5 plan does not match the exact freeze")

    try:
        archive_bytes = _read_regular_bytes(
            args.archive,
            max_bytes=MAX_MTAAC_V5_ARCHIVE_BYTES,
        )
    except (OSError, ValueError):
        return _fail("archive_unreadable", "the MTAAC archive could not be read safely")

    try:
        if _output_exists(args.output):
            return _fail(
                "output_exists",
                "the aggregate output target already exists",
                status=1,
            )
    except (OSError, ValueError):
        return _fail(
            "output_uninspectable",
            "the aggregate output target could not be inspected safely",
        )

    try:
        bundle = _build_training_bundle(archive_bytes)
    except Exception:
        return _fail(
            "archive_rejected",
            "the MTAAC archive failed the exact V5 training boundary",
        )
    try:
        report = _run_v5_development(
            bundle,
            plan_bytes=plan_bytes,
            implementation_commit=args.implementation_commit,
        )
    except Exception:
        return _fail(
            "development_rejected",
            "the fixed V5 development run failed closed",
        )
    try:
        validate_public_development_report(
            report,
            expected_implementation_commit=args.implementation_commit,
        )
        raw_report = _canonical_json(report)
    except (TypeError, ValueError):
        return _fail(
            "report_rejected",
            "the V5 report failed the aggregate public boundary",
        )

    try:
        _write_no_replace(args.output, raw_report)
    except FileExistsError:
        return _fail(
            "output_exists",
            "the aggregate output target already exists",
            status=1,
        )
    except (OSError, ValueError):
        return _fail(
            "output_write_failed",
            "the aggregate output could not be written safely",
        )
    sys.stdout.write(raw_report.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
