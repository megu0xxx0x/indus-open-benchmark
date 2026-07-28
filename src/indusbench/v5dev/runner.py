"""Deterministic aggregate-only execution for the final MTAAC V5 attempt.

V5 reuses the immutable V4 truth-free profile, family weighting, outer-fold
assignment, metric, and optimizer machinery.  The only fitted candidate is the
fixed V5 group-contrast CRF.  No V4 model or nonselecting V4 diagnostic is
fitted, and no item or family identifier crosses the returned report boundary.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final, cast

from indusbench.v3dev.contracts import (
    V3_STRUCTURAL_STATES,
    MTAACTrainingBundle,
    V3StructuralState,
)
from indusbench.v3dev.folds import GroupedFold, build_grouped_folds
from indusbench.v3dev.metrics import add_confusion_matrices, metrics_from_confusion
from indusbench.v4dev.corpus_statistics import (
    LOCAL_FEATURE_NAMES,
    PROFILE_FEATURE_NAMES,
    V4_CORPUS_PROFILE_VERSION,
)
from indusbench.v4dev.runner import (
    V3_FREEZE_COMMIT,
    V3_PLAN_SHA256,
    V3_RESULT_COMMIT,
    V3_RESULT_SHA256,
    V4_OUTER_FOLD_COUNT,
    V4_OUTER_FOLD_DOMAIN,
    V4DevelopmentError,
    _evaluate_model,
    _family_support,
    _labeled_families,
    _optimizer_contract,
    _prepare_partition_variants,
    _prepare_training_families,
    _support_report,
    _validate_bundle_commitments,
)
from indusbench.v4dev.sequence import CLASS_ADJUSTMENT_GAMMA, CRF_L2_RHO
from indusbench.v5dev.plan import (
    V5_DEVELOPMENT_PLAN_SHA256,
    V5DevelopmentPlanError,
    validate_v5_development_plan,
)
from indusbench.v5dev.sequence import (
    V5_CRF_MODEL_VERSION,
    V5GroupContrastLinearChainCRF,
)

V5_DEVELOPMENT_REPORT_VERSION: Final = "mtaac-v5-development-report-v1"

V4_FREEZE_COMMIT: Final = "304f8b36a32083330b8af02d21a58382c29d8915"
V4_RESULT_COMMIT: Final = "68332353a86f88e99e46df71fcdd2a4974dba31c"
V4_PLAN_SHA256: Final = "sha256:604725a5929b63f578ade07b65ca784eefefce9b827e1686d4836f668c123b"
V4_RESULT_SHA256: Final = "sha256:4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897"

V4_MILD_MACRO_F1: Final = 0.3877588813953674
V4_MILD_UNIT_RECALL: Final = 0.30521567409297784
V4_MILD_SETTLEMENT_RECALL: Final = 0.042941913609110954
V4_MILD_MACRO_F1_BY_OUTER_FOLD: Final = (
    0.3756051787768944,
    0.3998966341462856,
    0.3615261061386301,
    0.39294354710818963,
    0.39901832092281697,
)
V4_MILD_UNIT_RECALL_BY_OUTER_FOLD: Final = (
    0.18225197064754597,
    0.2892249319203195,
    0.2772641078805165,
    0.39686535349113794,
    0.35585102688488385,
)
V4_MILD_SETTLEMENT_RECALL_BY_OUTER_FOLD: Final = (
    0.0,
    0.09932569269976571,
    0.003780194718492515,
    0.06366234989790896,
    0.05568829861391914,
)

COMPARISON_TOLERANCE: Final = 1e-12
MILD_MACRO_F1_MINIMUM: Final = 0.3977588813953674
MILD_RECALL_FLOORS: Final = {
    "context_only": 0.520654531441017,
    "quantity": 0.1765055025096581,
    "unit": 0.3767836311289388,
    "person_name": 0.4988092152820551,
    "settlement_name": 0.15,
}
MILD_PRECISION_FLOORS: Final = {
    "unit": 0.3512887014608468,
    "settlement_name": 0.20747537967348736,
}
CLEAN_MACRO_F1_MINIMUM: Final = 0.4680972874281771
CLEAN_SETTLEMENT_RECALL_MINIMUM: Final = 0.10
POSITIVE_DELTA_FOLD_MINIMUM: Final = 4
SETTLEMENT_POSITIVE_RECALL_FOLD_MINIMUM: Final = 5
UNIT_WORST_FOLD_RECALL_MINIMUM: Final = 0.18225197064754597

_IMPLEMENTATION_COMMIT = re.compile(r"[0-9a-f]{40}")


class V5DevelopmentError(ValueError):
    """Raised when fixed V5 development execution cannot complete safely."""


def run_v5_development(
    bundle: MTAACTrainingBundle,
    *,
    plan_bytes: bytes,
    implementation_commit: str,
) -> dict[str, Any]:
    """Run the closed, single-candidate final MTAAC development protocol."""

    try:
        validate_v5_development_plan(plan_bytes)
    except V5DevelopmentPlanError as error:
        raise V5DevelopmentError("development plan does not match the V5 freeze") from error
    try:
        _validate_bundle_commitments(bundle)
    except V4DevelopmentError as error:
        raise V5DevelopmentError("training bundle does not match the parent boundary") from error
    if (
        not isinstance(implementation_commit, str)
        or _IMPLEMENTATION_COMMIT.fullmatch(implementation_commit) is None
    ):
        raise V5DevelopmentError("implementation commit must be lowercase 40-hex")

    try:
        families = _family_support(bundle.clean)
        outer_folds = build_grouped_folds(
            families,
            fold_count=V4_OUTER_FOLD_COUNT,
            domain=V4_OUTER_FOLD_DOMAIN,
        )
    except ValueError as error:
        raise V5DevelopmentError("V5 outer-fold construction failed closed") from error
    outer_reports: list[dict[str, Any]] = []
    clean_confusions: list[Mapping[V3StructuralState, Mapping[V3StructuralState, float]]] = []
    mild_confusions: list[Mapping[V3StructuralState, Mapping[V3StructuralState, float]]] = []
    mild_macro_by_fold: list[float] = []
    mild_unit_recall_by_fold: list[float] = []
    mild_settlement_recall_by_fold: list[float] = []

    try:
        for fold in outer_folds:
            prepared = _prepare_primary_outer_fold(bundle, fold)
            model = V5GroupContrastLinearChainCRF.fit(
                prepared["full_train_families"],
            )
            clean = _evaluate_model(model, prepared["validation_clean"])
            mild = _evaluate_model(model, prepared["validation_mild"])
            clean_confusions.append(_metric_confusion(clean))
            mild_confusions.append(_metric_confusion(mild))

            mild_per_state = _per_state(mild)
            mild_macro_by_fold.append(float(mild["macro_f1"]))
            mild_unit_recall_by_fold.append(float(mild_per_state["unit"]["recall"]))
            mild_settlement_recall_by_fold.append(
                float(mild_per_state["settlement_name"]["recall"])
            )
            outer_reports.append(
                {
                    "outer_fold_index": fold.index,
                    "support": _support_report(fold.support_summary()),
                    "profile_batch_commitments": prepared["profile_commitments"],
                    "optimizer": model.optimization_summary(),
                    "metrics": {
                        "clean": clean,
                        "mild": mild,
                    },
                }
            )
    except V5DevelopmentError:
        raise
    except (V4DevelopmentError, ValueError) as error:
        raise V5DevelopmentError(
            "V5 profile, fit, or evaluation machinery failed closed"
        ) from error

    oof_clean = metrics_from_confusion(add_confusion_matrices(clean_confusions))
    oof_mild = metrics_from_confusion(add_confusion_matrices(mild_confusions))
    paired_v4 = _paired_v4(
        mild_macro_by_fold=mild_macro_by_fold,
        mild_unit_recall_by_fold=mild_unit_recall_by_fold,
        mild_settlement_recall_by_fold=mild_settlement_recall_by_fold,
    )
    gate_decision = _gate_decision(
        clean=oof_clean,
        mild=oof_mild,
        paired_v4=paired_v4,
    )

    all_family_ids = tuple(sorted(family.family_id for family in families))
    final_model: V5GroupContrastLinearChainCRF | None = None
    if gate_decision["all_passed"] is True:
        try:
            final_training = _prepare_training_families(bundle, all_family_ids)
            final_model = V5GroupContrastLinearChainCRF.fit(
                final_training["families"],
            )
        except (V4DevelopmentError, ValueError) as error:
            raise V5DevelopmentError("final V5 fit failed closed") from error

    return {
        "analysis": "mtaac_v5_group_contrast_crf_development",
        "report_version": V5_DEVELOPMENT_REPORT_VERSION,
        "terminal_status": gate_decision["terminal_status"],
        "development_only": True,
        "model_executed": True,
        "scientific_metrics_emitted": True,
        "mtaac_retired": True,
        "plan_sha256": V5_DEVELOPMENT_PLAN_SHA256,
        "implementation_commit": implementation_commit,
        "parent_commitments": {
            "gateway_version": bundle.gateway_version,
            "mtaac_source_commit": bundle.source_commit,
            "v2_freeze_commit": bundle.v2_freeze_commit,
            "source_archive_sha256": bundle.source_archive_sha256,
            "selected_manifest_sha256": bundle.selected_manifest_sha256,
            "evaluation_corpus_sha256": bundle.evaluation_corpus_sha256,
            "v2_protocol_sha256": bundle.v2_protocol_sha256,
            "v2_split_manifest_sha256": bundle.split_manifest_sha256,
            "v3_freeze_commit": V3_FREEZE_COMMIT,
            "v3_result_commit": V3_RESULT_COMMIT,
            "v3_plan_sha256": V3_PLAN_SHA256,
            "v3_result_sha256": V3_RESULT_SHA256,
            "v4_freeze_commit": V4_FREEZE_COMMIT,
            "v4_result_commit": V4_RESULT_COMMIT,
            "v4_plan_sha256": V4_PLAN_SHA256,
            "v4_result_sha256": V4_RESULT_SHA256,
        },
        "data_boundary": {
            "model_training_family_count": bundle.training_family_count,
            "v2_holdout_family_count_excluded": bundle.excluded_holdout_family_count,
            "v2_holdout_exposed_to_model": False,
            "v2_holdout_scored": False,
            "reserved_validation_source_loaded": False,
            "regimes_used": ["clean", "mild"],
            "replica_index_used": 0,
            "mtaac_final_attempt": True,
        },
        "profile_contract": {
            "version": V4_CORPUS_PROFILE_VERSION,
            "inference_mode": ("target_batch_partition_regime_local_document_leave_one_family_out"),
            "local_features": list(LOCAL_FEATURE_NAMES),
            "profile_features": list(PROFILE_FEATURE_NAMES),
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
        },
        "model_contract": {
            "version": V5_CRF_MODEL_VERSION,
            "states": list(V3_STRUCTURAL_STATES),
            "candidate_count": 1,
            "candidate_selection": "none_fixed_method",
            "l2_rho": CRF_L2_RHO,
            "class_adjustment_gamma": CLASS_ADJUSTMENT_GAMMA,
            "class_prior_smoothing": "family_weighted_jeffreys_alpha_0.5",
            "optimizer": _optimizer_contract(),
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
                "coordinate_scope": (
                    "every_corresponding_emission_feature_coefficient_and_emission_bias"
                ),
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
        },
        "outer_development": {
            "outer_fold_count": V4_OUTER_FOLD_COUNT,
            "fold_assignment_parent": ("exact_v3_and_v4_five_outer_fold_assignments"),
            "outer_folds": outer_reports,
            "out_of_fold_metrics": {
                "clean": oof_clean,
                "mild": oof_mild,
            },
            "paired_v4": paired_v4,
        },
        "gate_decision": gate_decision,
        "final_development_model": {
            "fitted": final_model is not None,
            "fit_rule": ("fit_all_271_families_only_after_advance_to_prospective_freeze"),
            "model_state_commitment": (
                None if final_model is None else final_model.model_state_commitment()
            ),
            "optimizer": (None if final_model is None else final_model.optimization_summary()),
        },
        "claim_scope": {
            "class": "development_only",
            "eligible_as_reserved_validation_result": False,
            "eligible_as_v2_holdout_result": False,
            "eligible_as_binding_confirmation": False,
            "eligible_as_decipherment": False,
            "individual_predictions_published": False,
            "prospective_execution_requires_separate_public_freeze": True,
        },
    }


def _prepare_primary_outer_fold(
    bundle: MTAACTrainingBundle,
    fold: GroupedFold,
) -> dict[str, Any]:
    """Prepare only the four V5 primary train/evaluation target batches."""

    train_clean = _prepare_partition_variants(
        bundle.clean,
        fold.train_family_ids,
    )
    train_mild = _prepare_partition_variants(
        bundle.mild,
        fold.train_family_ids,
    )
    validation_clean = _prepare_partition_variants(
        bundle.clean,
        fold.validation_family_ids,
    )
    validation_mild = _prepare_partition_variants(
        bundle.mild,
        fold.validation_family_ids,
    )
    return {
        "full_train_families": _labeled_families(
            train_clean["full"],
            train_mild["full"],
            fold.train_family_ids,
        ),
        "validation_clean": validation_clean["full"],
        "validation_mild": validation_mild["full"],
        "profile_commitments": {
            "train_clean": train_clean["full"].profile_commitment,
            "train_mild": train_mild["full"].profile_commitment,
            "validation_clean": validation_clean["full"].profile_commitment,
            "validation_mild": validation_mild["full"].profile_commitment,
        },
    }


def _metric_confusion(
    metrics: Mapping[str, Any],
) -> Mapping[V3StructuralState, Mapping[V3StructuralState, float]]:
    value = metrics.get("weighted_confusion_matrix")
    if not isinstance(value, Mapping):
        raise V5DevelopmentError("metric report lacks its aggregate confusion matrix")
    return cast(
        Mapping[V3StructuralState, Mapping[V3StructuralState, float]],
        value,
    )


def _per_state(metrics: Mapping[str, Any]) -> Mapping[str, Mapping[str, float]]:
    value = metrics.get("per_state")
    if not isinstance(value, Mapping):
        raise V5DevelopmentError("metric report lacks per-state metrics")
    return cast(Mapping[str, Mapping[str, float]], value)


def _paired_v4(
    *,
    mild_macro_by_fold: list[float],
    mild_unit_recall_by_fold: list[float],
    mild_settlement_recall_by_fold: list[float],
) -> dict[str, Any]:
    macro_deltas = _deltas(mild_macro_by_fold, V4_MILD_MACRO_F1_BY_OUTER_FOLD)
    unit_deltas = _deltas(
        mild_unit_recall_by_fold,
        V4_MILD_UNIT_RECALL_BY_OUTER_FOLD,
    )
    settlement_deltas = _deltas(
        mild_settlement_recall_by_fold,
        V4_MILD_SETTLEMENT_RECALL_BY_OUTER_FOLD,
    )
    return {
        "v4_mild_macro_f1": V4_MILD_MACRO_F1,
        "v4_mild_unit_recall": V4_MILD_UNIT_RECALL,
        "v4_mild_settlement_name_recall": V4_MILD_SETTLEMENT_RECALL,
        "v4_mild_macro_f1_by_outer_fold": list(V4_MILD_MACRO_F1_BY_OUTER_FOLD),
        "v4_mild_unit_recall_by_outer_fold": list(V4_MILD_UNIT_RECALL_BY_OUTER_FOLD),
        "v4_mild_settlement_name_recall_by_outer_fold": list(
            V4_MILD_SETTLEMENT_RECALL_BY_OUTER_FOLD
        ),
        "v5_mild_macro_f1_by_outer_fold": mild_macro_by_fold,
        "v5_mild_unit_recall_by_outer_fold": mild_unit_recall_by_fold,
        "v5_mild_settlement_name_recall_by_outer_fold": (mild_settlement_recall_by_fold),
        "mild_macro_f1_delta_by_outer_fold": macro_deltas,
        "mild_unit_recall_delta_by_outer_fold": unit_deltas,
        "mild_settlement_name_recall_delta_by_outer_fold": settlement_deltas,
        "positive_mild_macro_f1_delta_fold_count": _positive_count(macro_deltas),
        "positive_mild_unit_recall_delta_fold_count": _positive_count(unit_deltas),
        "positive_mild_settlement_name_recall_delta_fold_count": _positive_count(settlement_deltas),
    }


def _deltas(current: list[float], baseline: tuple[float, ...]) -> list[float]:
    if len(current) != V4_OUTER_FOLD_COUNT:
        raise V5DevelopmentError("paired comparison does not contain five folds")
    return [observed - reference for observed, reference in zip(current, baseline, strict=True)]


def _positive_count(deltas: list[float]) -> int:
    return sum(delta > COMPARISON_TOLERANCE for delta in deltas)


def _minimum_check(observed: float | int, minimum: float | int) -> dict[str, Any]:
    return {
        "observed": observed,
        "minimum": minimum,
        "passed": observed >= minimum - COMPARISON_TOLERANCE,
    }


def _gate_decision(
    *,
    clean: Mapping[str, Any],
    mild: Mapping[str, Any],
    paired_v4: Mapping[str, Any],
) -> dict[str, Any]:
    clean_per_state = _per_state(clean)
    mild_per_state = _per_state(mild)
    settlement_by_fold = cast(
        list[float],
        paired_v4["v5_mild_settlement_name_recall_by_outer_fold"],
    )
    unit_by_fold = cast(
        list[float],
        paired_v4["v5_mild_unit_recall_by_outer_fold"],
    )
    settlement_positive_count = sum(value > COMPARISON_TOLERANCE for value in settlement_by_fold)
    unit_worst_fold = min(unit_by_fold)

    checks: dict[str, Any] = {
        "mild_macro_f1": _minimum_check(
            float(mild["macro_f1"]),
            MILD_MACRO_F1_MINIMUM,
        ),
        "mild_recall_floors": {
            state: _minimum_check(
                float(mild_per_state[state]["recall"]),
                minimum,
            )
            for state, minimum in MILD_RECALL_FLOORS.items()
        },
        "mild_precision_floors": {
            state: _minimum_check(
                float(mild_per_state[state]["precision"]),
                minimum,
            )
            for state, minimum in MILD_PRECISION_FLOORS.items()
        },
        "clean_macro_f1": _minimum_check(
            float(clean["macro_f1"]),
            CLEAN_MACRO_F1_MINIMUM,
        ),
        "clean_settlement_name_recall": _minimum_check(
            float(clean_per_state["settlement_name"]["recall"]),
            CLEAN_SETTLEMENT_RECALL_MINIMUM,
        ),
        "positive_mild_macro_f1_delta_outer_fold_count": _minimum_check(
            int(paired_v4["positive_mild_macro_f1_delta_fold_count"]),
            POSITIVE_DELTA_FOLD_MINIMUM,
        ),
        "positive_mild_unit_recall_delta_outer_fold_count": _minimum_check(
            int(paired_v4["positive_mild_unit_recall_delta_fold_count"]),
            POSITIVE_DELTA_FOLD_MINIMUM,
        ),
        "positive_mild_settlement_name_recall_delta_outer_fold_count": (
            _minimum_check(
                int(paired_v4["positive_mild_settlement_name_recall_delta_fold_count"]),
                POSITIVE_DELTA_FOLD_MINIMUM,
            )
        ),
        "settlement_name_positive_recall_outer_fold_count": _minimum_check(
            settlement_positive_count,
            SETTLEMENT_POSITIVE_RECALL_FOLD_MINIMUM,
        ),
        "unit_worst_outer_fold_recall": _minimum_check(
            unit_worst_fold,
            UNIT_WORST_FOLD_RECALL_MINIMUM,
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
    terminal_status = "advance_to_prospective_freeze" if all_passed else "mtaac_retired"
    return {
        "terminal_status": terminal_status,
        "all_passed": all_passed,
        "mtaac_retired": True,
        "comparison_tolerance": COMPARISON_TOLERANCE,
        "minimum_gate_rule": ("observed_greater_than_or_equal_to_minimum_minus_tolerance"),
        "positive_delta_rule": "delta_strictly_greater_than_tolerance",
        "strict_positive_recall_rule": ("recall_strictly_greater_than_tolerance"),
        "checks": checks,
    }


__all__ = [
    "CLEAN_MACRO_F1_MINIMUM",
    "CLEAN_SETTLEMENT_RECALL_MINIMUM",
    "COMPARISON_TOLERANCE",
    "MILD_MACRO_F1_MINIMUM",
    "MILD_PRECISION_FLOORS",
    "MILD_RECALL_FLOORS",
    "POSITIVE_DELTA_FOLD_MINIMUM",
    "SETTLEMENT_POSITIVE_RECALL_FOLD_MINIMUM",
    "UNIT_WORST_FOLD_RECALL_MINIMUM",
    "V4_MILD_MACRO_F1",
    "V4_MILD_MACRO_F1_BY_OUTER_FOLD",
    "V4_MILD_SETTLEMENT_RECALL",
    "V4_MILD_SETTLEMENT_RECALL_BY_OUTER_FOLD",
    "V4_MILD_UNIT_RECALL",
    "V4_MILD_UNIT_RECALL_BY_OUTER_FOLD",
    "V5_DEVELOPMENT_REPORT_VERSION",
    "V5DevelopmentError",
    "run_v5_development",
]
