from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import indusbench.v3dev.plan as plan_module
from indusbench.v3dev.plan import (
    MAX_V3_DEVELOPMENT_PLAN_BYTES,
    V3_DEVELOPMENT_PLAN_ID,
    V3_DEVELOPMENT_PLAN_SHA256,
    V3_DEVELOPMENT_PLAN_VERSION,
    V3DevelopmentPlanError,
    validate_v3_development_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark/mtaac-v3-development-v1.json"


def _tagged_sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


class V3DevelopmentPlanTests(unittest.TestCase):
    def test_checked_in_plan_is_the_exact_closed_contract(self) -> None:
        raw = PLAN_PATH.read_bytes()
        self.assertLessEqual(len(raw), MAX_V3_DEVELOPMENT_PLAN_BYTES)
        self.assertEqual(V3_DEVELOPMENT_PLAN_SHA256, _tagged_sha256(raw))

        value = validate_v3_development_plan(raw)
        self.assertEqual(V3_DEVELOPMENT_PLAN_ID, value["protocol_id"])
        self.assertEqual(V3_DEVELOPMENT_PLAN_VERSION, value["protocol_version"])
        self.assertEqual(
            "development_only_post_v2_result_before_reserved_source_execution",
            value["protocol_status"],
        )
        self.assertEqual(5, value["folds"]["nested_development"]["outer_fold_count"])
        self.assertEqual(4, value["folds"]["nested_development"]["inner_fold_count"])
        self.assertEqual(
            "indusbench-v3dev:full-selection:v1",
            value["folds"]["final_selection"]["domain"],
        )
        self.assertEqual(4, value["folds"]["final_selection"]["fold_count"])
        self.assertEqual(
            "family_weighted_mild_macro_f1",
            value["selection"]["metric"],
        )
        self.assertEqual(
            [
                "lower_class_balance_gamma",
                "lower_transition_strength",
            ],
            value["selection"]["complexity_order"],
        )
        self.assertEqual(
            "guard_and_diagnostic_only_not_candidate_selection",
            value["data_boundary"]["clean_role"],
        )
        self.assertEqual(
            "membership_verified_by_gateway_then_not_exposed_to_model_and_not_scored",
            value["data_boundary"]["v2_holdout"],
        )
        self.assertNotIn("oracc", raw.decode("utf-8").casefold())

    def test_byte_change_is_rejected_even_when_json_is_semantically_equal(self) -> None:
        raw = PLAN_PATH.read_bytes()
        changed = raw + b" "
        with self.assertRaisesRegex(V3DevelopmentPlanError, "SHA-256"):
            validate_v3_development_plan(changed)

        with (
            patch.object(
                plan_module,
                "V3_DEVELOPMENT_PLAN_SHA256",
                _tagged_sha256(changed),
            ),
            self.assertRaisesRegex(V3DevelopmentPlanError, "byte layout"),
        ):
            validate_v3_development_plan(changed)

    def test_digest_substitution_cannot_rewrite_a_closed_field(self) -> None:
        raw = PLAN_PATH.read_bytes()
        changed = raw.replace(b'"family_count": 271', b'"family_count": 272', 1)
        self.assertNotEqual(raw, changed)
        with (
            patch.object(
                plan_module,
                "V3_DEVELOPMENT_PLAN_SHA256",
                _tagged_sha256(changed),
            ),
            self.assertRaisesRegex(V3DevelopmentPlanError, "closed contract"),
        ):
            validate_v3_development_plan(changed)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(self) -> None:
        cases = (
            b'{"protocol_id":"first","protocol_id":"second"}',
            b'{"protocol_id":NaN}',
        )
        for raw in cases:
            with (
                self.subTest(raw=raw),
                patch.object(
                    plan_module,
                    "V3_DEVELOPMENT_PLAN_SHA256",
                    _tagged_sha256(raw),
                ),
                self.assertRaisesRegex(V3DevelopmentPlanError, "strict UTF-8 JSON"),
            ):
                validate_v3_development_plan(raw)

    def test_plan_shape_is_closed_and_development_only(self) -> None:
        value = json.loads(PLAN_PATH.read_bytes())
        self.assertEqual(
            {
                "data_boundary",
                "features",
                "folds",
                "implementation",
                "model",
                "nonclaims",
                "parent_boundary",
                "protocol_id",
                "protocol_status",
                "protocol_version",
                "report_contract",
                "selection",
                "task",
                "weighting",
            },
            set(value),
        )
        self.assertTrue(value["report_contract"]["required_assertions"]["development_only"])
        self.assertFalse(
            value["report_contract"]["required_assertions"]["reserved_validation_source_loaded"]
        )
        self.assertFalse(value["report_contract"]["required_assertions"]["v2_holdout_scored"])


if __name__ == "__main__":
    unittest.main()
