# ruff: noqa: E501
"""Exact-byte verifier for the development-only MTAAC V3 plan."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Final

V3_DEVELOPMENT_PLAN_ID: Final = "mtaac-v3-development-v1"
V3_DEVELOPMENT_PLAN_VERSION: Final = "mtaac-v3-development-v1"
V3_DEVELOPMENT_PLAN_SHA256: Final = (
    "sha256:b2100318fa0e958d741fd25d7b9263ae1574967f4585f4609c118b1bd16880dd"
)
MAX_V3_DEVELOPMENT_PLAN_BYTES: Final = 16 * 1024

_EXPECTED_PLAN_BYTES: Final = b"""{
  "data_boundary": {
    "accepted_training_regimes": [
      "clean",
      "mild"
    ],
    "clean_role": "guard_and_diagnostic_only_not_candidate_selection",
    "mild_role": "only_candidate_selection_and_primary_development_evaluation",
    "reserved_validation_source": "not_loaded_or_used_for_fitting_selection_tuning_debugging_or_feature_design",
    "v2_holdout": "membership_verified_by_gateway_then_not_exposed_to_model_and_not_scored"
  },
  "features": {
    "exact_feature_order": [
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
      "line_template"
    ],
    "lexical_identity_policy": "opaque_observation_ids_used_only_to_derive_within_line_equality_then_discarded",
    "unknown_feature_value": "neutral_evidence"
  },
  "folds": {
    "coverage_gate": "all_five_states_positive_in_every_training_and_validation_partition",
    "fallback": false,
    "family_grouping": "complete_sequence_family_never_split",
    "final_selection": {
      "domain": "indusbench-v3dev:full-selection:v1",
      "family_count": 271,
      "fold_count": 4,
      "selection_regime": "mild"
    },
    "nested_development": {
      "inner_fold_count": 4,
      "outer_fold_count": 5,
      "selection_regime": "mild"
    },
    "seed_search": false
  },
  "implementation": {
    "entry_point": "indusbench-v3dev-mtaac",
    "gateway_module": "indusbench.v3dev.mtaac_training",
    "model_module": "indusbench.v3dev.sequence",
    "normative_module": "indusbench.v3dev.runner",
    "plan_module": "indusbench.v3dev.plan"
  },
  "model": {
    "class_balance_gamma_candidates": [
      0.0,
      0.5,
      1.0
    ],
    "emissions": "weighted_categorical_naive_bayes",
    "laplace_alpha": 1.0,
    "sequence_decoder": "first_order_viterbi",
    "transition_counts": "unadjusted_family_weights",
    "transition_strength_candidates": [
      0.0,
      0.5,
      1.0
    ]
  },
  "nonclaims": [
    "development_metrics_are_not_binding_confirmation",
    "reserved_validation_source_is_not_loaded",
    "v2_holdout_is_not_scored",
    "no_indus_reading_translation_decipherment_or_prize_claim"
  ],
  "parent_boundary": {
    "evaluation_corpus_sha256": "sha256:e7d6f8c9a8c090bb33ef4ba3703c1b36fe0519086efa75ff70d1ba53a8bf9312",
    "excluded_v2_holdout_family_count": 90,
    "gateway_version": "mtaac-v2-training-gateway-v1",
    "selected_manifest_sha256": "sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e",
    "source_archive_sha256": "sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091",
    "source_commit": "66e0643efd230401210e27db353ebb6d7228b1bb",
    "training_family_count": 271,
    "v2_freeze_commit": "37157f1411a55ffd91b7327afaca8fc1080fa708",
    "v2_protocol_sha256": "sha256:25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892",
    "v2_split_manifest_sha256": "sha256:7249c8fe1d3efc95b42cc9e0a9378550addb64f5b992f89af99dd852b83c5c30",
    "v2_split_seed": 0,
    "v2_split_test_fraction": 0.25
  },
  "protocol_id": "mtaac-v3-development-v1",
  "protocol_status": "development_only_post_v2_result_before_reserved_source_execution",
  "protocol_version": "mtaac-v3-development-v1",
  "report_contract": {
    "granularity": "aggregate_only",
    "prohibited_content": [
      "source_document_or_token_identifiers",
      "archive_member_or_local_paths",
      "raw_annotation_values",
      "per_document_or_per_family_metrics",
      "family_or_fold_membership",
      "reserved_validation_source_results_or_counts"
    ],
    "required_assertions": {
      "development_only": true,
      "model_executed": true,
      "reserved_validation_source_loaded": false,
      "scientific_metrics_emitted": true,
      "v2_holdout_scored": false
    },
    "success_terminal_status": "development_complete"
  },
  "selection": {
    "candidate_count": 9,
    "complexity_order": [
      "lower_class_balance_gamma",
      "lower_transition_strength"
    ],
    "metric": "family_weighted_mild_macro_f1",
    "rule": "one_standard_error_simplest_eligible_candidate"
  },
  "task": {
    "damaged_retained_tokens": "predicted_and_scored",
    "empty_gold_projection": "context_only",
    "prediction_unit": "every_retained_token",
    "states": [
      "context_only",
      "quantity",
      "unit",
      "person_name",
      "settlement_name"
    ]
  },
  "weighting": {
    "evaluation": "each_validation_family_has_total_mass_one_per_regime",
    "training": "each_training_family_has_base_mass_one_distributed_across_clean_and_mild_occurrences"
  }
}
"""


class V3DevelopmentPlanError(ValueError):
    """Raised when supplied plan bytes do not match the frozen V3 contract."""


class _StrictJsonError(ValueError):
    """Internal marker for JSON values rejected by the strict decoder."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _StrictJsonError("duplicate object key")
        result[key] = value
    return result


def _reject_nonfinite_constant(_value: str) -> None:
    raise _StrictJsonError("non-finite number")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _StrictJsonError("non-finite number")
    return parsed


def _strict_json(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
            parse_float=_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _StrictJsonError) as error:
        raise V3DevelopmentPlanError("development plan is not strict UTF-8 JSON") from error


_EXPECTED_PLAN: Final = _strict_json(_EXPECTED_PLAN_BYTES)


def validate_v3_development_plan(plan_bytes: bytes) -> dict[str, Any]:
    """Verify exact frozen bytes and every closed semantic field."""

    if not isinstance(plan_bytes, bytes):
        raise V3DevelopmentPlanError("development plan must be supplied as exact bytes")
    if not plan_bytes:
        raise V3DevelopmentPlanError("development plan is empty")
    if len(plan_bytes) > MAX_V3_DEVELOPMENT_PLAN_BYTES:
        raise V3DevelopmentPlanError("development plan exceeds the byte limit")
    actual_sha256 = f"sha256:{hashlib.sha256(plan_bytes).hexdigest()}"
    if actual_sha256 != V3_DEVELOPMENT_PLAN_SHA256:
        raise V3DevelopmentPlanError("development plan SHA-256 does not match the freeze")

    value = _strict_json(plan_bytes)
    if not isinstance(value, dict):
        raise V3DevelopmentPlanError("development plan JSON root must be an object")
    if value != _EXPECTED_PLAN:
        raise V3DevelopmentPlanError("development plan fields do not match the closed contract")
    if plan_bytes != _EXPECTED_PLAN_BYTES:
        raise V3DevelopmentPlanError("development plan byte layout does not match the freeze")
    return value


__all__ = [
    "MAX_V3_DEVELOPMENT_PLAN_BYTES",
    "V3_DEVELOPMENT_PLAN_ID",
    "V3_DEVELOPMENT_PLAN_SHA256",
    "V3_DEVELOPMENT_PLAN_VERSION",
    "V3DevelopmentPlanError",
    "validate_v3_development_plan",
]
