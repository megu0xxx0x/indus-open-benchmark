from __future__ import annotations

import hashlib
import json
import re
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import indusbench.kp1979_v2_runner as runner
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmark/results/kp1979-label-lattice-v2-result-v1.json"
RESULT_SCHEMA = ROOT / "schemas/kp1979-label-lattice-synthetic-control-v2-result.schema.json"
RESULT_SHA256 = "cc1cfa1e639ac0054d93fe49be65a14937178e6ffa1ca7fdab2d941cb75db204"
BASE_COMMIT = "662b01c23d4d4e2336e248d79bc508c3b7ed5f66"
CONTROL_COMMIT = "e143a5ed5a8128d7b7e3626a3bf01607289ee7cc"
DETECTOR_COMMIT = "5f059032ed9ee1e790c4c668047510f8e1cd60d5"
INTEGRATION_COMMIT = "4362da843c8ed48068198779a1a11702df422f3b"
INTEGRATION_PARENTS = (CONTROL_COMMIT, DETECTOR_COMMIT)

EXPECTED_COMMITMENTS = {
    "base_commit": BASE_COMMIT,
    "control_commit": CONTROL_COMMIT,
    "control_manifest_sha256": ("ee368613138f2ccb89686872ff127504f0627b2df662edef3b5a0486583f870f"),
    "control_module_sha256": ("7674968043476cc366cf7f0a73daf588d4cea8695a3c6fd368bf1c3d730ebab9"),
    "detector_commit": DETECTOR_COMMIT,
    "detector_module_sha256": ("2540310dad612080034ab89f37cff96ce3341d1fc93d2fa44c0c86a78ccd66a4"),
    "detector_wheel_byte_size": 639_360,
    "detector_wheel_sha256": ("7861a7e435d8221ac9c95a12e232c988533bba9c803b30f470384d2e9476a5cb"),
    "execution_plan_sha256": ("3b4c7c740cda6f6e1d6b5cc05efded01b775f611c51a304dcf4a5ae3e6608593"),
    "execution_schema_sha256": ("bfd275c2a6ea3c4a927a3bb04bccf3349d66f888042214aa5782909f05d399d1"),
    "integration_commit": INTEGRATION_COMMIT,
    "result_schema_sha256": ("2905b8daf79b8857fadc1451a2f2f7fa380fe57be190491e72a349750951711d"),
    "scorer_module_sha256": ("56bdcfe869f96e043acadabe44d839bce97891b5c1eb81604e72874fce4b48ba"),
    "uv_lock_sha256": ("d916009109bb939157fe248d613398ddc21735871704117dfa1ea1e00b7c2443"),
    "worker_module_sha256": ("4405774a8c544da5d09eb313025b40757ddfe6acc12dfa5013406e3c3f5326c4"),
}

PUBLIC_COMMITMENT_PATHS = {
    "control_manifest_sha256": (ROOT / "benchmark/kp1979-label-lattice-synthetic-control-v2.json"),
    "control_module_sha256": ROOT / "src/indusbench/kp1979_synthetic_control_v2.py",
    "detector_module_sha256": ROOT / "src/indusbench/printed_concordance_layout_v2.py",
    "execution_plan_sha256": (
        ROOT / "benchmark/kp1979-label-lattice-synthetic-control-v2-execution-v1.json"
    ),
    "execution_schema_sha256": (
        ROOT / "schemas/kp1979-label-lattice-synthetic-control-v2-execution.schema.json"
    ),
    "result_schema_sha256": RESULT_SCHEMA,
    "scorer_module_sha256": ROOT / "src/indusbench/kp1979_label_scoring.py",
    "worker_module_sha256": ROOT / "src/indusbench/kp1979_detector_v2_worker.py",
}
# The published result binds its historical execution lock. Later project
# dependency updates must not reinterpret that immutable digest as the current
# repository lock identity.


def _all_mapping_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return {key for key in value if isinstance(key, str)} | {
            nested for nested_value in value.values() for nested in _all_mapping_keys(nested_value)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {nested for nested_value in value for nested in _all_mapping_keys(nested_value)}
    return set()


class KP1979V2PublishedResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = RESULT.read_bytes()
        if hashlib.sha256(cls.raw).hexdigest() != RESULT_SHA256:
            raise AssertionError("published KP1979 V2 result bytes changed")
        cls.result: dict[str, Any] = json.loads(cls.raw)

    def test_result_bytes_are_canonical_and_semantically_schema_valid(self) -> None:
        self.assertEqual(13_072, len(self.raw))
        self.assertEqual([], validate_schema_instance(self.result, RESULT_SCHEMA))
        self.assertIsNone(runner._validate_result_semantics(self.result))
        self.assertEqual(self.raw, runner._canonical_json_bytes(self.result))

    def test_integration_parents_and_public_commitments_are_exact(self) -> None:
        commitments = self.result["commitments"]
        self.assertEqual(EXPECTED_COMMITMENTS, commitments)
        self.assertEqual(INTEGRATION_COMMIT, commitments["integration_commit"])
        self.assertEqual(
            INTEGRATION_PARENTS,
            (commitments["control_commit"], commitments["detector_commit"]),
        )
        self.assertEqual(BASE_COMMIT, runner.BASE_COMMIT)
        self.assertEqual(INTEGRATION_PARENTS, (runner.CONTROL_COMMIT, runner.DETECTOR_COMMIT))
        for field, path in PUBLIC_COMMITMENT_PATHS.items():
            with self.subTest(field=field):
                self.assertEqual(
                    commitments[field],
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
        self.assertEqual(
            {
                "blob_identity_verified": True,
                "control_manifest_verified": True,
                "detector_wheel_verified": True,
                "git_ancestry_verified": True,
                "public_main_ref_matches_integration_commit": True,
                "public_remote_independently_attested": False,
                "wheel_excludes_v2_control": True,
            },
            self.result["freeze_integrity"],
        )

    def test_raw_control_has_only_the_declared_gapped_positive_failure(self) -> None:
        control = self.result["control_report"]
        cases = control["cases"]
        self.assertEqual(19, control["case_count"])
        self.assertEqual(18, control["passed_case_count"])
        self.assertEqual("not_qualified", control["status"])
        self.assertEqual(
            ["positive_bounded_jitter_with_gaps"],
            [case["case_id"] for case in cases if not case["passed"]],
        )
        failed = next(case for case in cases if not case["passed"])
        self.assertEqual("positive", failed["case_class"])
        self.assertEqual("abstained", failed["outcome_status"])
        self.assertEqual(0, failed["prediction_count"])
        self.assertEqual(68, failed["reference_count"])
        self.assertEqual(0.0, failed["micro_precision"])
        self.assertEqual(0.0, failed["micro_recall"])
        self.assertTrue(all(case["passed"] for case in cases if case is not failed))

        metamorphic = control["metamorphic_checks"]
        self.assertEqual(
            [
                "identical_input_reproducibility",
                "unread_margin_invariance",
                "vertical_translation_equivariance",
            ],
            [relation["relation_id"] for relation in metamorphic],
        )
        self.assertTrue(all(relation["passed"] for relation in metamorphic))

    def test_transport_process_and_terminal_decisions_are_fixed(self) -> None:
        self.assertEqual(
            {
                "accepted_count": 21,
                "expected_invocation_count": 25,
                "failure_codes": [],
                "invocation_count": 25,
                "out_of_contract_rejection_count": 4,
                "stderr_observed": False,
                "timeout_observed": False,
                "transport_failure_count": 0,
            },
            self.result["transport_summary"],
        )
        boundary = self.result["execution_boundary"]
        self.assertEqual(25, boundary["started_process_count"])
        self.assertTrue(boundary["fresh_process_per_invocation"])
        gates = self.result["mandatory_gates"]
        self.assertTrue(gates["fresh_process_count_verified"])
        self.assertTrue(gates["transport_boundary_passed"])
        self.assertFalse(gates["control_case_gates_passed"])
        self.assertFalse(gates["control_before_detector_freeze"])
        self.assertFalse(gates["postfreeze_adversarial_deployment_clear"])
        self.assertFalse(gates["all_mandatory_gates_passed"])

        self.assertEqual("not_qualified", self.result["terminal_status"])
        self.assertFalse(self.result["advance_to_provisional_extraction"])
        self.assertEqual(
            {
                "automatic_corpus_admission_allowed": False,
                "future_execution_allowed": False,
                "machine_development_candidate_generation_allowed": False,
                "reason_codes": [
                    "control_before_detector_freeze_order_not_satisfied",
                    "postfreeze_periodic_confound",
                ],
                "reference_promotion_allowed": False,
                "status": "blocked",
            },
            self.result["deployment_decision"],
        )

    def test_every_scientific_claim_remains_false(self) -> None:
        claims = self.result["claim_scope"]
        self.assertTrue(claims)
        self.assertTrue(all(type(value) is bool for value in claims.values()))
        self.assertFalse(any(claims.values()))

        control = self.result["control_report"]
        control_claims = (
            "decipherment",
            "full_row_segmentation_validated",
            "future_evaluation_opened",
            "identifier_transcription_validated",
            "prize_submission_eligible",
            "real_accuracy",
            "reference_accepted",
            "reserved_sources_read",
        )
        self.assertTrue(all(control[field] is False for field in control_claims))

    def test_result_contains_no_private_or_future_item_data(self) -> None:
        forbidden_keys = {
            "account",
            "document_id",
            "future_target",
            "future_targets",
            "future_value",
            "future_values",
            "host",
            "hostname",
            "identifier",
            "image_bytes",
            "item",
            "item_id",
            "item_identifier",
            "local_path",
            "lower_code",
            "page_id",
            "page_index",
            "page_number",
            "pbm_base64",
            "pixel_data",
            "predictions",
            "private_path",
            "row_id",
            "sign_sequence",
            "source_path",
            "username",
        }
        self.assertFalse(forbidden_keys & _all_mapping_keys(self.result))
        claims = self.result["claim_scope"]
        self.assertFalse(claims["future_evaluation_opened"])
        self.assertFalse(claims["future_pixels_loaded"])
        self.assertFalse(claims["future_pixels_opened"])
        self.assertFalse(claims["reserved_sources_read"])

        allowed_case_keys = {
            "case_class",
            "case_id",
            "micro_precision",
            "micro_recall",
            "negative_control_empty",
            "outcome_status",
            "passed",
            "prediction_count",
            "reference_count",
            "scorer_status",
        }
        for case in self.result["control_report"]["cases"]:
            self.assertEqual(allowed_case_keys, set(case))

        text = self.raw.decode("ascii")
        forbidden_patterns = (
            r"/(?:home|Users|private|private/tmp|tmp)/",
            r"[A-Za-z]:[\\/]",
            r"(?<![0-9])(?:25[0-5]|2[0-4][0-9]|1?[0-9]?[0-9])"
            r"(?:[.](?:25[0-5]|2[0-4][0-9]|1?[0-9]?[0-9])){3}(?![0-9])",
            r"\bssh://",
            r'"(?:account|host|hostname|username)"\s*:',
            r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY",
            r"\bgh[pousr]_[A-Za-z0-9_]{20,}",
        )
        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text, flags=re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
