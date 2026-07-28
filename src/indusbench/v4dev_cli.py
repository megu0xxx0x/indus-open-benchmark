"""Network-free, no-replace CLI for the development-only MTAAC V4 run."""

from __future__ import annotations

import argparse
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
import json
import math
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from indusbench.schema_validation import validate_schema_instance
from indusbench.v3dev.contracts import V3StructuralState
from indusbench.v3dev.metrics import add_confusion_matrices, metrics_from_confusion
from indusbench.v4dev.plan import (
    MAX_V4_DEVELOPMENT_PLAN_BYTES,
    V4_DEVELOPMENT_PLAN_SHA256,
    V4DevelopmentPlanError,
    validate_v4_development_plan,
)

MAX_MTAAC_V4_ARCHIVE_BYTES: Final = 256 * 1024 * 1024
MAX_MTAAC_V4_REPORT_BYTES: Final = 4 * 1024 * 1024
MTAAC_V4_REPORT_VERSION: Final = "mtaac-v4-development-report-v1"
MTAAC_V4_REPORT_SCHEMA: Final = "mtaac-v4-development-report.schema.json"

_V3_MILD_MACRO_F1: Final = 0.32432759235715436
_V3_MILD_MACRO_F1_BY_OUTER_FOLD: Final = (
    0.31683351626900313,
    0.32138764286827887,
    0.3088289319784221,
    0.30447569487308923,
    0.33797633693780393,
)
_MILD_MACRO_F1_MINIMUM: Final = 0.36432759235715436
_MILD_SETTLEMENT_RECALL_MINIMUM: Final = 0.15
_PAIRED_POSITIVE_FOLD_MINIMUM: Final = 4
_FULL_MINUS_LOCAL_MINIMUM: Final = 0.02
_MILD_RECALL_FLOORS: Final = {
    "context_only": 0.520654531441017,
    "quantity": 0.1765055025096581,
    "unit": 0.3767836311289388,
    "person_name": 0.4988092152820551,
}
_CLEAN_MACRO_F1_MINIMUM: Final = 0.36
_CLEAN_SETTLEMENT_RECALL_MINIMUM: Final = 0.10
_SELF_INFORMATION_DELTA_MAXIMUM: Final = 0.05
_DIAGNOSTIC_NAMES: Final = (
    "no_corpus_profile",
    "transition_zero",
    "logistic_emission",
    "self_inclusive_target_profile",
    "strict_single_family_profile",
)

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_TAGGED_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_UNTAGGED_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_P_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])P[0-9]{6}(?![0-9])")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_RAW_IDENTIFIER_PREFIX = re.compile(
    r"mtaac-(?:document-source-id|token-source-order|word-form|artificial-word-form)-sha256-v1:"
)
_RAW_ANNOTATION_WORD = re.compile(r"\b(?:FORM|SEGM|XPOSTAG)\b", re.IGNORECASE)

_PUBLIC_REPORT_KEYS: Final = frozenset(
    {
        "analysis",
        "report_version",
        "terminal_status",
        "development_only",
        "model_executed",
        "scientific_metrics_emitted",
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
    "v3_model_state_commitment": (
        "sha256:d2b332f6d9b2b6acae206f7f0b8db07d7e2431b5995168f7228a374e4f134158"
    ),
}
_EXPECTED_DATA_BOUNDARY: Final = {
    "model_training_family_count": 271,
    "v2_holdout_family_count_excluded": 90,
    "v2_holdout_exposed_to_model": False,
    "v2_holdout_scored": False,
    "reserved_validation_source_loaded": False,
    "regimes_used": ["clean", "mild"],
    "replica_index_used": 0,
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
    "version": "v4-distributional-linear-chain-crf-v1",
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
    "diagnostics": [
        "no_corpus_profile",
        "transition_zero",
        "logistic_emission",
        "self_inclusive_target_profile",
        "strict_single_family_profile",
    ],
}
_EXPECTED_CLAIM_SCOPE: Final = {
    "class": "development_only",
    "eligible_as_reserved_validation_result": False,
    "eligible_as_v2_holdout_result": False,
    "eligible_as_binding_confirmation": False,
    "eligible_as_decipherment": False,
    "individual_predictions_published": False,
}
_FORBIDDEN_REPORT_KEYS: Final = frozenset(
    {
        "archive_member",
        "archive_members",
        "archive_member_path",
        "cache_key",
        "cache_keys",
        "document",
        "documents",
        "document_id",
        "document_ids",
        "document_identifier",
        "document_identifiers",
        "document_key",
        "document_keys",
        "families",
        "family_id",
        "family_ids",
        "family_membership",
        "feature_row",
        "feature_rows",
        "file_path",
        "fold_family_ids",
        "fold_members",
        "fold_membership",
        "form",
        "identity_commitment",
        "identity_map",
        "input_path",
        "local_path",
        "member",
        "members",
        "member_name",
        "member_names",
        "member_path",
        "member_paths",
        "observed_form_id",
        "observation_id",
        "output_path",
        "p_id",
        "per_document",
        "per_document_metrics",
        "per_family",
        "per_family_metrics",
        "per_member",
        "per_token",
        "pid",
        "profile_entries",
        "raw_form",
        "raw_value",
        "segm",
        "source_document_identifier",
        "source_identifier",
        "source_path",
        "token",
        "tokens",
        "token_id",
        "token_ids",
        "token_key",
        "token_keys",
        "xpostag",
    }
)


class V4DevelopmentCLIError(ValueError):
    """Raised when local CLI data cannot cross the public output boundary."""


def _report_schema_path() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / MTAAC_V4_REPORT_SCHEMA
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        f"schemas/{MTAAC_V4_REPORT_SCHEMA}"
    )
    if not package_candidate.is_file():
        raise V4DevelopmentCLIError("the closed development report schema is unavailable")
    return Path(str(package_candidate))


def _validate_closed_schema(report: object) -> None:
    try:
        issues = validate_schema_instance(report, _report_schema_path())
    except V4DevelopmentCLIError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise V4DevelopmentCLIError(
            "the closed development report schema could not be applied"
        ) from error
    if issues:
        raise V4DevelopmentCLIError("development report does not match the closed schema")


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
        raise V4DevelopmentCLIError("development report is not canonical JSON data") from error
    if len(raw) > MAX_MTAAC_V4_REPORT_BYTES:
        raise V4DevelopmentCLIError("development report exceeds the public byte limit")
    return raw


def _validate_public_scalar(value: object, *, key: str | None) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise V4DevelopmentCLIError("public report contains a non-finite number")
    if not isinstance(value, str):
        raise V4DevelopmentCLIError("public report contains a non-JSON value")
    if len(value) > 10_000:
        raise V4DevelopmentCLIError("public report contains an oversized string")
    folded = value.casefold()
    if "oracc" in folded:
        raise V4DevelopmentCLIError("public report names the reserved validation source")
    if (
        _P_IDENTIFIER.search(value) is not None
        or _RAW_IDENTIFIER_PREFIX.search(folded) is not None
        or _RAW_ANNOTATION_WORD.search(value) is not None
        or value.startswith(("/", "~"))
        or _WINDOWS_ABSOLUTE_PATH.match(value) is not None
        or "file://" in folded
    ):
        raise V4DevelopmentCLIError("public report contains item-level or local source data")
    if _UNTAGGED_SHA256.fullmatch(value) is not None:
        raise V4DevelopmentCLIError("public report contains an unlabelled item fingerprint")
    if key is not None and key.endswith("_sha256") and not value.startswith("sha256:"):
        raise V4DevelopmentCLIError("public report contains an untagged SHA-256 commitment")


def _validate_public_value(
    value: object,
    *,
    key: str | None = None,
    depth: int = 0,
    budget: list[int],
) -> None:
    if depth > 32:
        raise V4DevelopmentCLIError("public report nesting exceeds the fixed limit")
    budget[0] += 1
    if budget[0] > 100_000:
        raise V4DevelopmentCLIError("public report structure exceeds the fixed limit")
    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str) or not nested_key:
                raise V4DevelopmentCLIError("public report keys must be non-empty strings")
            normalized_key = nested_key.casefold().replace("-", "_")
            if (
                normalized_key in _FORBIDDEN_REPORT_KEYS
                or normalized_key.startswith("raw_")
                or normalized_key.endswith("_path")
                or "oracc" in normalized_key
            ):
                raise V4DevelopmentCLIError("public report contains a forbidden field")
            _validate_public_value(
                nested_value,
                key=normalized_key,
                depth=depth + 1,
                budget=budget,
            )
        return
    if isinstance(value, (list, tuple)):
        for nested_value in value:
            _validate_public_value(
                nested_value,
                key=key,
                depth=depth + 1,
                budget=budget,
            )
        return
    _validate_public_scalar(value, key=key)


def _mapping(value: object, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V4DevelopmentCLIError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _list(value: object, *, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise V4DevelopmentCLIError(f"{field_name} must be an array")
    return value


def _metric_confusion(
    metrics: Mapping[str, Any],
) -> Mapping[V3StructuralState, Mapping[V3StructuralState, float]]:
    confusion = metrics.get("weighted_confusion_matrix")
    if not isinstance(confusion, Mapping):
        raise V4DevelopmentCLIError("scientific metric lacks a confusion matrix")
    return cast(
        Mapping[V3StructuralState, Mapping[V3StructuralState, float]],
        confusion,
    )


def _recompute_metric_report(value: object) -> dict[str, Any]:
    metrics = _mapping(value, field_name="scientific metric")
    recomputed = metrics_from_confusion(_metric_confusion(metrics))
    if metrics != recomputed:
        raise V4DevelopmentCLIError("scientific metrics do not match their confusion matrix")
    return recomputed


def _minimum_check(observed: float | int, minimum: float | int) -> dict[str, Any]:
    return {
        "observed": observed,
        "minimum": minimum,
        "passed": observed >= minimum,
    }


def _maximum_check(observed: float, maximum: float) -> dict[str, Any]:
    return {
        "observed": observed,
        "maximum": maximum,
        "passed": observed <= maximum,
    }


def _recomputed_gate(
    *,
    primary_clean: Mapping[str, Any],
    primary_mild: Mapping[str, Any],
    no_profile: Mapping[str, Any],
    self_inclusive: Mapping[str, Any],
    positive_delta_fold_count: int,
) -> dict[str, Any]:
    mild_macro = float(primary_mild["macro_f1"])
    clean_macro = float(primary_clean["macro_f1"])
    mild_per_state = _mapping(primary_mild["per_state"], field_name="mild per-state metrics")
    clean_per_state = _mapping(
        primary_clean["per_state"],
        field_name="clean per-state metrics",
    )
    local_macro = float(no_profile["macro_f1"])
    self_inclusive_delta = float(self_inclusive["macro_f1"]) - mild_macro

    checks: dict[str, Any] = {
        "mild_macro_f1": _minimum_check(mild_macro, _MILD_MACRO_F1_MINIMUM),
        "mild_settlement_name_recall": _minimum_check(
            float(
                _mapping(
                    mild_per_state["settlement_name"],
                    field_name="mild settlement-name metrics",
                )["recall"]
            ),
            _MILD_SETTLEMENT_RECALL_MINIMUM,
        ),
        "positive_paired_delta_outer_fold_count": _minimum_check(
            positive_delta_fold_count,
            _PAIRED_POSITIVE_FOLD_MINIMUM,
        ),
        "profile_increment_mild_macro_f1": _minimum_check(
            mild_macro - local_macro,
            _FULL_MINUS_LOCAL_MINIMUM,
        ),
        "mild_recall_floors": {
            state: _minimum_check(
                float(
                    _mapping(
                        mild_per_state[state],
                        field_name=f"mild {state} metrics",
                    )["recall"]
                ),
                minimum,
            )
            for state, minimum in _MILD_RECALL_FLOORS.items()
        },
        "clean_macro_f1": _minimum_check(clean_macro, _CLEAN_MACRO_F1_MINIMUM),
        "clean_settlement_name_recall": _minimum_check(
            float(
                _mapping(
                    clean_per_state["settlement_name"],
                    field_name="clean settlement-name metrics",
                )["recall"]
            ),
            _CLEAN_SETTLEMENT_RECALL_MINIMUM,
        ),
        "self_inclusive_minus_lofo_mild_macro_f1": _maximum_check(
            self_inclusive_delta,
            _SELF_INFORMATION_DELTA_MAXIMUM,
        ),
    }
    flat_passes = [
        checks["mild_macro_f1"]["passed"],
        checks["mild_settlement_name_recall"]["passed"],
        checks["positive_paired_delta_outer_fold_count"]["passed"],
        checks["profile_increment_mild_macro_f1"]["passed"],
        *(value["passed"] for value in checks["mild_recall_floors"].values()),
        checks["clean_macro_f1"]["passed"],
        checks["clean_settlement_name_recall"]["passed"],
        checks["self_inclusive_minus_lofo_mild_macro_f1"]["passed"],
    ]
    all_passed = all(flat_passes)
    return {
        "terminal_status": "advance" if all_passed else "development_killed",
        "all_passed": all_passed,
        "self_information_sensitive": not checks["self_inclusive_minus_lofo_mild_macro_f1"][
            "passed"
        ],
        "checks": checks,
    }


def _validate_scientific_consistency(report: Mapping[str, Any]) -> None:
    """Recompute every public aggregate and the complete frozen decision."""

    try:
        outer = _mapping(report["outer_development"], field_name="outer development")
        folds = _list(outer["outer_folds"], field_name="outer folds")
        if len(folds) != 5:
            raise V4DevelopmentCLIError("outer development must contain five folds")

        metric_names = ("primary_clean", "primary_mild", *_DIAGNOSTIC_NAMES)
        fold_confusions: dict[
            str,
            list[Mapping[V3StructuralState, Mapping[V3StructuralState, float]]],
        ] = {name: [] for name in metric_names}
        v4_mild_by_outer_fold: list[float] = []

        for fold_index, fold_value in enumerate(folds):
            fold = _mapping(fold_value, field_name="outer fold")
            if fold.get("outer_fold_index") != fold_index:
                raise V4DevelopmentCLIError("outer fold indexes are not canonical")
            metrics = _mapping(fold["metrics"], field_name="outer-fold metrics")
            primary = _mapping(metrics["primary"], field_name="primary metrics")
            diagnostics = _mapping(
                metrics["diagnostics"],
                field_name="diagnostic metrics",
            )
            reports = {
                "primary_clean": primary["clean"],
                "primary_mild": primary["mild"],
                **{name: diagnostics[name] for name in _DIAGNOSTIC_NAMES},
            }
            for name, metric_report in reports.items():
                recomputed = _recompute_metric_report(metric_report)
                fold_confusions[name].append(_metric_confusion(recomputed))
                if name == "primary_mild":
                    v4_mild_by_outer_fold.append(float(recomputed["macro_f1"]))

        recomputed_oof = {
            name: metrics_from_confusion(add_confusion_matrices(matrices))
            for name, matrices in fold_confusions.items()
        }
        expected_oof = {
            "primary": {
                "clean": recomputed_oof["primary_clean"],
                "mild": recomputed_oof["primary_mild"],
            },
            "diagnostics": {name: recomputed_oof[name] for name in _DIAGNOSTIC_NAMES},
        }
        if outer["out_of_fold_metrics"] != expected_oof:
            raise V4DevelopmentCLIError(
                "out-of-fold metrics do not match the sum of fold confusion matrices"
            )

        delta_by_outer_fold = [
            current - baseline
            for current, baseline in zip(
                v4_mild_by_outer_fold,
                _V3_MILD_MACRO_F1_BY_OUTER_FOLD,
                strict=True,
            )
        ]
        positive_delta_fold_count = sum(delta > 0.0 for delta in delta_by_outer_fold)
        expected_paired = {
            "v3_mild_macro_f1": _V3_MILD_MACRO_F1,
            "v3_mild_macro_f1_by_outer_fold": list(_V3_MILD_MACRO_F1_BY_OUTER_FOLD),
            "v4_mild_macro_f1_by_outer_fold": v4_mild_by_outer_fold,
            "delta_by_outer_fold": delta_by_outer_fold,
            "positive_delta_fold_count": positive_delta_fold_count,
        }
        if outer["paired_v3"] != expected_paired:
            raise V4DevelopmentCLIError("paired V3 comparison does not recompute")

        expected_gate = _recomputed_gate(
            primary_clean=recomputed_oof["primary_clean"],
            primary_mild=recomputed_oof["primary_mild"],
            no_profile=recomputed_oof["no_corpus_profile"],
            self_inclusive=recomputed_oof["self_inclusive_target_profile"],
            positive_delta_fold_count=positive_delta_fold_count,
        )
        if report["gate_decision"] != expected_gate:
            raise V4DevelopmentCLIError("development gate or terminal decision does not recompute")
        if report["terminal_status"] != expected_gate["terminal_status"]:
            raise V4DevelopmentCLIError("report terminal status does not match recomputed gates")
    except V4DevelopmentCLIError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise V4DevelopmentCLIError(
            "development report scientific aggregates are malformed"
        ) from error


def _validate_terminal_consistency(report: Mapping[str, Any]) -> None:
    terminal_status = report["terminal_status"]
    gate = report["gate_decision"]
    final_model = report["final_development_model"]
    if not isinstance(gate, Mapping) or not isinstance(final_model, Mapping):
        raise V4DevelopmentCLIError("development decision sections must be objects")
    if gate.get("terminal_status") != terminal_status:
        raise V4DevelopmentCLIError("gate and report terminal states disagree")
    if terminal_status == "advance":
        if (
            gate.get("all_passed") is not True
            or gate.get("self_information_sensitive") is not False
            or final_model.get("fitted") is not True
            or not isinstance(final_model.get("model_state_commitment"), str)
            or _TAGGED_SHA256.fullmatch(final_model["model_state_commitment"]) is None
            or not isinstance(final_model.get("optimizer"), Mapping)
        ):
            raise V4DevelopmentCLIError("advance report does not satisfy the closed gate")
    elif terminal_status == "development_killed":
        if (
            final_model.get("fitted") is not False
            or final_model.get("model_state_commitment") is not None
            or final_model.get("optimizer") is not None
            or (gate.get("all_passed") is True and gate.get("self_information_sensitive") is False)
        ):
            raise V4DevelopmentCLIError("killed report does not satisfy the closed gate")
    else:
        raise V4DevelopmentCLIError("development report terminal state is unsupported")


def validate_public_development_report(
    report: object,
    *,
    expected_implementation_commit: str | None = None,
) -> dict[str, Any]:
    """Enforce the aggregate-only V4 report boundary before publication."""

    if not isinstance(report, dict) or set(report) != _PUBLIC_REPORT_KEYS:
        raise V4DevelopmentCLIError("development report root does not match the closed contract")
    if (
        report["analysis"] != "mtaac_v4_distributional_crf_development"
        or report["report_version"] != MTAAC_V4_REPORT_VERSION
        or report["terminal_status"] not in {"advance", "development_killed"}
        or report["development_only"] is not True
        or report["model_executed"] is not True
        or report["scientific_metrics_emitted"] is not True
        or report["plan_sha256"] != V4_DEVELOPMENT_PLAN_SHA256
        or not isinstance(report["implementation_commit"], str)
        or _COMMIT.fullmatch(report["implementation_commit"]) is None
        or (
            expected_implementation_commit is not None
            and report["implementation_commit"] != expected_implementation_commit
        )
    ):
        raise V4DevelopmentCLIError("development report assertions do not match the plan")
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
            raise V4DevelopmentCLIError("development report aggregate sections must be objects")
    if report["parent_commitments"] != _EXPECTED_PARENT_COMMITMENTS:
        raise V4DevelopmentCLIError("development report parent commitments disagree")
    if report["data_boundary"] != _EXPECTED_DATA_BOUNDARY:
        raise V4DevelopmentCLIError("development report data boundary assertions disagree")
    if report["profile_contract"] != _EXPECTED_PROFILE_CONTRACT:
        raise V4DevelopmentCLIError("development report profile contract disagrees")
    if report["model_contract"] != _EXPECTED_MODEL_CONTRACT:
        raise V4DevelopmentCLIError("development report model contract disagrees")
    if report["claim_scope"] != _EXPECTED_CLAIM_SCOPE:
        raise V4DevelopmentCLIError("development report claim scope disagrees")
    _validate_terminal_consistency(report)
    _validate_closed_schema(report)
    _validate_scientific_consistency(report)
    _validate_public_value(report, budget=[0])
    _canonical_json(report)
    return report


def _read_regular_bytes(path: Path, *, max_bytes: int) -> bytes:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise V4DevelopmentCLIError("input is not a single-link regular file")
        if before.st_size > max_bytes:
            raise V4DevelopmentCLIError("input exceeds the byte limit")
        chunks: list[bytes] = []
        byte_count = 0
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            while True:
                chunk = handle.read(min(1024 * 1024, max_bytes + 1 - byte_count))
                if not chunk:
                    after = os.fstat(handle.fileno())
                    break
                chunks.append(chunk)
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise V4DevelopmentCLIError("input exceeds the byte limit")
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise V4DevelopmentCLIError("input changed while it was read")
        return b"".join(chunks)
    except OSError as error:
        raise V4DevelopmentCLIError("input could not be read safely") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _output_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _write_no_replace(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _build_training_bundle(archive_bytes: bytes) -> Any:
    from indusbench.v3dev.mtaac_training import build_mtaac_v2_training_bundle

    return build_mtaac_v2_training_bundle(archive_bytes)


def _run_v4_development(
    bundle: Any,
    *,
    plan_bytes: bytes,
    implementation_commit: str,
) -> dict[str, Any]:
    from indusbench.v4dev.runner import run_v4_development

    return run_v4_development(
        bundle,
        plan_bytes=plan_bytes,
        implementation_commit=implementation_commit,
    )


def _print_json(value: object) -> None:
    sys.stdout.write(_canonical_json(value).decode("utf-8"))


def _fail(error_code: str, message: str, *, status: int = 2) -> int:
    _print_json(
        {
            "analysis": "mtaac_v4_distributional_crf_development",
            "development_only": True,
            "error": message,
            "error_code": error_code,
            "model_executed": False,
            "scientific_metrics_emitted": False,
            "terminal_status": "error",
        }
    )
    return status


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="indusbench-v4dev-mtaac",
        description="Run the exact development-only MTAAC V4 plan without network access.",
    )
    parser.add_argument("archive", type=Path, help="local exact pinned MTAAC archive")
    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
        help="local exact frozen MTAAC V4 development plan",
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
    """Execute the one-purpose V4 CLI with path-redacted failures."""

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
            max_bytes=MAX_V4_DEVELOPMENT_PLAN_BYTES,
        )
    except (OSError, ValueError):
        return _fail("plan_unreadable", "the development plan could not be read safely")
    try:
        validate_v4_development_plan(plan_bytes)
    except V4DevelopmentPlanError:
        return _fail("plan_rejected", "the development plan does not match the exact freeze")

    try:
        archive_bytes = _read_regular_bytes(
            args.archive,
            max_bytes=MAX_MTAAC_V4_ARCHIVE_BYTES,
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
            "the MTAAC archive failed the exact V4 training boundary",
        )
    try:
        report = _run_v4_development(
            bundle,
            plan_bytes=plan_bytes,
            implementation_commit=args.implementation_commit,
        )
    except Exception:
        return _fail(
            "development_rejected",
            "the fixed V4 development run failed closed",
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
            "the development report failed the aggregate public boundary",
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
