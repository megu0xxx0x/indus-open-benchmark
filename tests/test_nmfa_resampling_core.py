from __future__ import annotations

import copy
import hashlib
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from indusbench import nmfa_bootstrap_core as bootstrap_core
from indusbench import nmfa_resampling_common as common
from indusbench import nmfa_x_model_core as x_core
from indusbench import nmfa_y_rational_core as y_core
from indusbench.io import encode_json, read_json
from tests import test_nmfa_measurement_core as measurement_fixture

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark/nmfa-resampling-core-plan-v1.json"
BUNDLE_PATH = ROOT / "benchmark/nmfa-resampling-core-evaluator-bundle-v1.json"
PLAN_SCHEMA_PATH = ROOT / "schemas/nmfa-resampling-core-plan.schema.json"
BOOTSTRAP_SCHEMA_PATH = ROOT / "schemas/nmfa-bootstrap-receipt.schema.json"
SELECTOR_SCHEMA_PATH = ROOT / "schemas/nmfa-selector-receipt.schema.json"


def sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def resource_bytes(relative: str) -> bytes:
    if relative.startswith("src/indusbench/"):
        relative = relative.removeprefix("src/indusbench/")
    module = ROOT / "src" / "indusbench" / relative
    if "/" not in relative and module.is_file():
        return module.read_bytes()
    return (ROOT / relative).read_bytes()


@contextmanager
def local_resampling_resources():
    with patch.object(common, "_resource_bytes", side_effect=resource_bytes):
        yield


def selector_assignment(full: dict[str, Any]) -> dict[str, Any]:
    selector_schema = read_json(SELECTOR_SCHEMA_PATH)
    assignments: list[dict[str, Any]] = []
    for index, row in enumerate(full["rows"]):
        if index < 80:
            cell = common._AXES[index // 20]
            partition = "holdout"
        else:
            cell = None
            partition = ("development", "development", "validation")[(index - 80) % 3]
        assignments.append(
            {
                "cell": cell,
                "g_id": row["g_id"],
                "partition": partition,
                "primary_f_id": row["primary_f_id"],
            }
        )
    return {
        "assignments": assignments,
        "assurance_boundary": {
            "claim_binding_origin_verified": False,
            "eligible_inventory_digest_origin_verified": False,
            "external_nonce_provenance_verified": False,
            "one_use_consumption_verified": False,
            "realized_split": False,
            "relation_evidence_origin_verified": False,
            "scientific_result": False,
            "value_free_identifier_origin_verified": False,
        },
        "bindings": {
            "eligible_split_inventory_sha256": measurement_fixture.checksum("selector-inventory"),
            "gate_evaluator_bundle_sha256": "sha256:" + common._GATE_BUNDLE_SHA256,
            "gate_plan_sha256": "sha256:" + common._GATE_PLAN_SHA256,
            "parent_protocol_sha256": "sha256:" + common._PARENT_PROTOCOL_SHA256,
            "selector_bundle_sha256": "sha256:" + common._SELECTOR_BUNDLE_SHA256,
            "selector_inventory_sha256": measurement_fixture.checksum("selector-typed-inventory"),
            "selector_plan_sha256": "sha256:" + common._SELECTOR_PLAN_SHA256,
            "tuple_roster_sha256": measurement_fixture.checksum("tuple-roster"),
        },
        "claim_binding": full["claim_binding"],
        "compiled_blockers": selector_schema["properties"]["compiled_blockers"]["const"],
        "format_version": "1.0.0",
        "n2_movable_g": 80,
        "nonce_sha256": measurement_fixture.checksum("declared-nonce"),
        "record_kind": "nmfa_protected_selector_assignment",
        "selected_ticket_sha256": measurement_fixture.checksum("selected-ticket"),
        "selected_tuple": [
            measurement_fixture.opaque(f"selected-tuple-{index}") for index in range(4)
        ],
        "split_eligible_tuple_count": 1,
        "terminal_state": "DECLARED_SELECTOR_ASSIGNMENT_ONLY",
    }


class NMFAResamplingCoreTests(unittest.TestCase):
    maxDiff = None

    def test_plan_and_schemas_are_canonical_exact_and_closed(self) -> None:
        plan = read_json(PLAN_PATH)
        for path in (PLAN_SCHEMA_PATH, BOOTSTRAP_SCHEMA_PATH):
            raw = path.read_bytes()
            schema = read_json(path)
            self.assertEqual(encode_json(schema), raw)
            Draft202012Validator.check_schema(schema)
            self.assertFalse(schema.get("additionalProperties", False))
        plan_schema = read_json(PLAN_SCHEMA_PATH)
        validator = Draft202012Validator(plan_schema, format_checker=FormatChecker())
        self.assertEqual([], list(validator.iter_errors(plan)))
        self.assertEqual(encode_json(plan), PLAN_PATH.read_bytes())
        mutated = copy.deepcopy(plan)
        mutated["assurance_boundary"]["scientific_result"] = True
        self.assertIsNotNone(next(validator.iter_errors(mutated), None))
        self.assertEqual(10_000, plan["limits"]["bootstrap_runs"])
        self.assertEqual(249, plan["algorithms"]["endpoint"]["index_zero_based"])

    def test_bundle_closes_exact_runtime_inventory(self) -> None:
        bundle = read_json(BUNDLE_PATH)
        self.assertEqual(encode_json(bundle), BUNDLE_PATH.read_bytes())
        self.assertEqual("nmfa-resampling-core-evaluator-bundle-v1", bundle["bundle_id"])
        self.assertEqual(common._EXPECTED_RUNTIME_PROFILE, bundle["runtime_profile"])
        self.assertEqual(common._EXPECTED_SECURITY_BOUNDARY, bundle["security_boundary"])
        self.assertEqual(common._BUNDLE_FILE_PATHS, {row["path"] for row in bundle["files"]})
        for row in bundle["files"]:
            raw = (ROOT / row["path"]).read_bytes()
            self.assertEqual((row["bytes"], row["sha256"]), (len(raw), sha256(raw)))

    def test_installed_plan_and_resource_locks(self) -> None:
        with local_resampling_resources():
            plan = common.load_installed_nmfa_resampling_plan()
        self.assertEqual("nmfa-resampling-core-plan-v1", plan["plan_id"])
        for relative, (size, digest) in common._RESOURCE_LOCKS.items():
            raw = (ROOT / relative).read_bytes()
            self.assertEqual((size, digest), (len(raw), hashlib.sha256(raw).hexdigest()))

    def test_complete_public_synthetic_bootstrap_reexecution(self) -> None:
        full = measurement_fixture.roster()
        selector_value = selector_assignment(full)
        selector_raw = encode_json(selector_value)
        selector_raw_sha256 = sha256(selector_raw)
        full["selector_assignment_raw_sha256"] = selector_raw_sha256
        full_raw, full_raw_sha256, _ = measurement_fixture.roster_raw_and_digests(full)
        metric_value = measurement_fixture.metric_roster(full, full["rows"][:80])
        metric_raw = encode_json(metric_value)
        x_value, model_sha256 = measurement_fixture.x_batch(full)
        x_raw = encode_json(x_value)
        y_value, target_contract_sha256 = measurement_fixture.y_batch(full)
        y_raw = encode_json(y_value)
        stable_bundle = measurement_fixture.checksum("resampling-test-bundle")

        with measurement_fixture.local_resources():
            score = x_core.score_nmfa_x_batch(
                full_raw,
                full_raw_sha256,
                x_raw,
                sha256(x_raw),
                model_sha256,
            )
            target = y_core.normalize_nmfa_y_batch(
                full_raw,
                full_raw_sha256,
                y_raw,
                sha256(y_raw),
                target_contract_sha256,
            )
            with (
                local_resampling_resources(),
                patch.object(
                    bootstrap_core,
                    "_validate_installed_bundle",
                    return_value=stable_bundle,
                ),
                patch.object(bootstrap_core, "_validate_predecessors", return_value=None),
                patch.object(
                    bootstrap_core,
                    "_require_unchanged_bundle",
                    return_value=None,
                ),
            ):
                result = bootstrap_core.evaluate_nmfa_paired_bootstrap(
                    full_raw,
                    full_raw_sha256,
                    metric_raw,
                    sha256(metric_raw),
                    selector_raw,
                    selector_raw_sha256,
                    score.receipt_bytes,
                    score.receipt_raw_sha256,
                    target.receipt_bytes,
                    target.receipt_raw_sha256,
                    measurement_fixture.checksum("frozen-protocol-chain-head"),
                )
                receipt = result.receipt()
                bootstrap_core.verify_nmfa_bootstrap_receipt(
                    full_raw,
                    full_raw_sha256,
                    metric_raw,
                    sha256(metric_raw),
                    selector_raw,
                    selector_raw_sha256,
                    score.receipt_bytes,
                    score.receipt_raw_sha256,
                    target.receipt_bytes,
                    target.receipt_raw_sha256,
                    measurement_fixture.checksum("frozen-protocol-chain-head"),
                    result.receipt_bytes,
                )

                impossible_sentinel = copy.deepcopy(receipt)
                impossible_sentinel["endpoints"]["candidate_rho_lower"]["rho"] = {
                    "covariance_c": "1",
                    "denominator_radicand": "1",
                    "kind": "sentinel",
                }
                impossible_raw = encode_json(impossible_sentinel)
                with self.assertRaises(common.NMFAResamplingError) as caught:
                    bootstrap_core._decode_bootstrap_receipt(
                        impossible_raw,
                        sha256(impossible_raw),
                        stable_bundle,
                    )
                self.assertIs(
                    caught.exception.code,
                    common.NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
                )

                impossible_counter = copy.deepcopy(receipt)
                impossible_counter["bootstrap"]["counter"].update(
                    {
                        "maximum_blocks_generated_per_run": 96,
                        "total_blocks_generated": 800_001,
                        "total_rejected_blocks": 1,
                    }
                )
                impossible_raw = encode_json(impossible_counter)
                with self.assertRaises(common.NMFAResamplingError) as caught:
                    bootstrap_core._decode_bootstrap_receipt(
                        impossible_raw,
                        sha256(impossible_raw),
                        stable_bundle,
                    )
                self.assertIs(
                    caught.exception.code,
                    common.NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
                )

                impossible_counter = copy.deepcopy(receipt)
                impossible_counter["bootstrap"]["counter"].update(
                    {
                        "maximum_blocks_generated_per_run": 81,
                        "total_blocks_generated": 810_001,
                        "total_rejected_blocks": 10_001,
                    }
                )
                impossible_raw = encode_json(impossible_counter)
                with self.assertRaises(common.NMFAResamplingError) as caught:
                    bootstrap_core._decode_bootstrap_receipt(
                        impossible_raw,
                        sha256(impossible_raw),
                        stable_bundle,
                    )
                self.assertIs(
                    caught.exception.code,
                    common.NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
                )

                impossible_counter = copy.deepcopy(receipt)
                impossible_counter["bootstrap"]["counter"]["maximum_blocks_generated_per_run"] += 1
                impossible_raw = encode_json(impossible_counter)
                with self.assertRaises(common.NMFAResamplingError) as caught:
                    bootstrap_core._decode_bootstrap_receipt(
                        impossible_raw,
                        sha256(impossible_raw),
                        stable_bundle,
                    )
                self.assertIs(
                    caught.exception.code,
                    common.NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
                )

        self.assertEqual(10_000, receipt["bootstrap"]["run_count"])
        self.assertEqual(800_000, receipt["bootstrap"]["counter"]["total_draws"])
        self.assertEqual(0, receipt["bootstrap"]["discarded_runs"])
        self.assertEqual(0, receipt["bootstrap"]["redrawn_runs"])
        self.assertFalse(receipt["assurance_boundary"]["scientific_result"])
        self.assertNotIn("rows", receipt)
        self.assertEqual("<ProtectedNMFABootstrapState protected>", repr(result))


if __name__ == "__main__":
    unittest.main()
