from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import indusbench.v4dev.plan as plan_module
from indusbench.v4dev.plan import (
    MAX_V4_DEVELOPMENT_PLAN_BYTES,
    V4_DEVELOPMENT_PLAN_ID,
    V4_DEVELOPMENT_PLAN_SHA256,
    V4_DEVELOPMENT_PLAN_VERSION,
    V4DevelopmentPlanError,
    validate_v4_development_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark" / "mtaac-v4-development-v1.json"


def _tagged_sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


class V4DevelopmentPlanTests(unittest.TestCase):
    def test_checked_in_plan_is_the_exact_closed_contract(self) -> None:
        raw = PLAN_PATH.read_bytes()
        self.assertLessEqual(len(raw), MAX_V4_DEVELOPMENT_PLAN_BYTES)
        self.assertEqual(V4_DEVELOPMENT_PLAN_SHA256, _tagged_sha256(raw))

        value = validate_v4_development_plan(raw)
        self.assertEqual(V4_DEVELOPMENT_PLAN_ID, value["protocol_id"])
        self.assertEqual(V4_DEVELOPMENT_PLAN_VERSION, value["protocol_version"])
        self.assertEqual(
            "development_only_post_v3_result_before_reserved_source_execution",
            value["protocol_status"],
        )
        self.assertEqual("exact_v3_five_outer_fold_assignments", value["folds"]["outer_assignment"])
        self.assertEqual(5, value["folds"]["outer_fold_count"])
        self.assertFalse(value["folds"]["inner_cross_validation"])
        self.assertFalse(value["folds"]["candidate_grid"])
        self.assertEqual(1, value["model"]["candidate_count"])
        self.assertEqual(0.01, value["model"]["l2_rho"])
        self.assertEqual(0.5, value["model"]["class_adjustment"]["decode_only_gamma"])
        self.assertEqual(10, value["optimizer"]["history_size"])
        self.assertEqual(100, value["optimizer"]["maximum_accepted_iterations"])
        self.assertEqual(
            ["advance", "development_killed"],
            value["report_contract"]["terminal_statuses"],
        )
        self.assertNotIn("oracc", raw.decode("utf-8").casefold())

    def test_byte_change_is_rejected_even_if_primary_digest_is_substituted(self) -> None:
        raw = PLAN_PATH.read_bytes()
        changed = raw + b" "
        with self.assertRaisesRegex(V4DevelopmentPlanError, "SHA-256"):
            validate_v4_development_plan(changed)

        with (
            patch.object(plan_module, "V4_DEVELOPMENT_PLAN_SHA256", _tagged_sha256(changed)),
            self.assertRaisesRegex(V4DevelopmentPlanError, "byte layout"),
        ):
            validate_v4_development_plan(changed)

    def test_dual_digest_substitution_cannot_rewrite_a_closed_field(self) -> None:
        raw = PLAN_PATH.read_bytes()
        changed = raw.replace(b'"candidate_count": 1', b'"candidate_count": 2', 1)
        self.assertNotEqual(raw, changed)
        with (
            patch.object(plan_module, "V4_DEVELOPMENT_PLAN_SHA256", _tagged_sha256(changed)),
            patch.object(
                plan_module,
                "_EXPECTED_PLAN_BLAKE2B",
                hashlib.blake2b(changed).hexdigest(),
            ),
            self.assertRaisesRegex(V4DevelopmentPlanError, "closed contract"),
        ):
            validate_v4_development_plan(changed)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(self) -> None:
        cases = (
            b'{"protocol_id":"first","protocol_id":"second"}',
            b'{"protocol_id":NaN}',
        )
        for raw in cases:
            with (
                self.subTest(raw=raw),
                patch.object(plan_module, "V4_DEVELOPMENT_PLAN_SHA256", _tagged_sha256(raw)),
                patch.object(
                    plan_module,
                    "_EXPECTED_PLAN_BLAKE2B",
                    hashlib.blake2b(raw).hexdigest(),
                ),
                self.assertRaisesRegex(V4DevelopmentPlanError, "strict UTF-8 JSON"),
            ):
                validate_v4_development_plan(raw)

    def test_plan_shape_profile_and_gate_are_closed(self) -> None:
        value = json.loads(PLAN_PATH.read_bytes())
        self.assertEqual(
            {
                "data_boundary",
                "decision",
                "diagnostics",
                "features",
                "folds",
                "implementation",
                "model",
                "nonclaims",
                "optimizer",
                "parent_boundary",
                "profiles",
                "protocol_id",
                "protocol_status",
                "protocol_version",
                "report_contract",
                "task",
                "weighting",
            },
            set(value),
        )
        self.assertEqual(
            "target_batch_partition_regime_local_document_leave_one_family_out",
            value["profiles"]["inference_mode"],
        )
        self.assertFalse(value["profiles"]["gold_used"])
        self.assertFalse(value["profiles"]["train_validation_shared"])
        self.assertFalse(value["profiles"]["clean_mild_shared"])
        self.assertEqual(
            0.36432759235715436,
            value["decision"]["checks"]["mild_macro_f1_minimum"],
        )
        self.assertEqual(
            0.05,
            value["decision"]["checks"]["self_inclusive_minus_lofo_mild_macro_f1_maximum"],
        )
        assertions = value["report_contract"]["required_assertions"]
        self.assertTrue(assertions["development_only"])
        self.assertFalse(assertions["reserved_validation_source_loaded"])
        self.assertFalse(assertions["v2_holdout_scored"])


if __name__ == "__main__":
    unittest.main()
