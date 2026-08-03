from __future__ import annotations

import ast
import copy
import hashlib
import random
import unittest
from contextlib import contextmanager
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from indusbench import nmfa_measurement_common as common
from indusbench import nmfa_rank_statistics_core as statistics
from indusbench import nmfa_x_model_core as x_core
from indusbench import nmfa_y_rational_core as y_core
from indusbench.io import encode_json, read_json

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark/nmfa-measurement-core-plan-v1.json"
BUNDLE_PATH = ROOT / "benchmark/nmfa-measurement-core-evaluator-bundle-v1.json"
SCHEMA_PATHS = tuple(
    ROOT / "schemas" / name
    for name in (
        "nmfa-gf-roster.schema.json",
        "nmfa-measurement-core-plan.schema.json",
        "nmfa-metric-receipt.schema.json",
        "nmfa-metric-roster.schema.json",
        "nmfa-score-receipt.schema.json",
        "nmfa-target-receipt.schema.json",
        "nmfa-x-batch.schema.json",
        "nmfa-y-batch.schema.json",
    )
)


def resource_bytes(relative: str) -> bytes:
    if relative in {
        "io.py",
        "nmfa_measurement_common.py",
        "nmfa_rank_statistics_core.py",
        "nmfa_x_model_core.py",
        "nmfa_y_rational_core.py",
    }:
        return (ROOT / "src" / "indusbench" / relative).read_bytes()
    return (ROOT / relative).read_bytes()


@contextmanager
def local_resources():
    with patch.object(common, "_resource_bytes", side_effect=resource_bytes):
        yield


def sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def domain_digest(domain: bytes, value: Any) -> str:
    return sha256(domain + encode_json(value))


def opaque(label: str) -> str:
    return "hmac-sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()


def registry_id(label: str) -> str:
    return "registry-id:" + hashlib.sha256(label.encode("ascii")).hexdigest()


def checksum(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()


def claim_binding() -> dict[str, str]:
    return {
        "claim_family_id": registry_id("synthetic-family"),
        "claim_slot_id": registry_id("synthetic-slot"),
        "experiment_instance_id": registry_id("synthetic-instance"),
        "predecessor_chain_head_sha256": checksum("synthetic-chain"),
    }


def gf_rows(count: int = 160) -> list[dict[str, str]]:
    return [
        {
            "g_id": "sha256:" + f"{index + 1:064x}",
            "primary_f_id": "hmac-sha256:" + f"{index + 1:064x}",
        }
        for index in range(count)
    ]


def roster(count: int = 160) -> dict[str, Any]:
    return {
        "claim_binding": claim_binding(),
        "format_version": "1.0.0",
        "gate_plan_sha256": "sha256:" + common._GATE_PLAN_SHA256,
        "measurement_plan_sha256": "sha256:" + common._PLAN_SHA256,
        "parent_protocol_sha256": "sha256:" + common._PARENT_PROTOCOL_SHA256,
        "record_kind": "nmfa_gf_roster",
        "rows": gf_rows(count),
        "selector_assignment_raw_sha256": checksum("synthetic-selector-assignment"),
        "selector_plan_sha256": "sha256:" + common._SELECTOR_PLAN_SHA256,
    }


def roster_raw_and_digests(value: dict[str, Any]) -> tuple[bytes, str, str]:
    raw = encode_json(value)
    roster_digest = domain_digest(common._ROSTER_DOMAIN, {"rows": value["rows"]})
    return raw, sha256(raw), roster_digest


def metric_roster(full: dict[str, Any], rows: list[dict[str, str]] | None = None) -> dict[str, Any]:
    full_raw, full_raw_digest, full_digest = roster_raw_and_digests(full)
    del full_raw
    return {
        "assignment_roster_raw_sha256": full_raw_digest,
        "assignment_roster_sha256": full_digest,
        "claim_binding": full["claim_binding"],
        "format_version": "1.0.0",
        "measurement_plan_sha256": "sha256:" + common._PLAN_SHA256,
        "record_kind": "nmfa_metric_roster",
        "rows": copy.deepcopy(rows if rows is not None else full["rows"]),
        "selector_assignment_raw_sha256": full["selector_assignment_raw_sha256"],
    }


def model_and_tokens() -> tuple[dict[str, Any], dict[str, str]]:
    tokens = {name: opaque(name) for name in ("a1", "a2", "b", "c")}
    classes = [
        {
            "class_id": domain_digest(
                x_core._CLASS_DOMAIN,
                {"member_token_ids": sorted([tokens["a1"], tokens["a2"]])},
            ),
            "member_token_ids": sorted([tokens["a1"], tokens["a2"]]),
            "weight": 2,
        },
        {
            "class_id": domain_digest(
                x_core._CLASS_DOMAIN,
                {"member_token_ids": [tokens["b"]]},
            ),
            "member_token_ids": [tokens["b"]],
            "weight": 1,
        },
    ]
    classes.sort(key=lambda row: row["class_id"])
    model = {
        "classes": classes,
        "policy_commitments": {
            "allograph_policy_sha256": checksum("allograph-policy"),
            "damage_policy_sha256": checksum("damage-policy"),
            "direction_policy_sha256": checksum("direction-policy"),
            "length_identity_policy_sha256": checksum("length-policy"),
            "segmentation_policy_sha256": checksum("segmentation-policy"),
            "surface_order_policy_sha256": checksum("surface-order-policy"),
        },
    }
    return model, tokens


def x_batch(full: dict[str, Any]) -> tuple[dict[str, Any], str]:
    _, _, full_digest = roster_raw_and_digests(full)
    model, tokens = model_and_tokens()
    token_vectors = [
        [tokens["c"]],
        [tokens["c"], tokens["c"]],
        [tokens["b"]],
        [tokens["a1"]],
    ] + [[tokens["c"]] for _ in full["rows"][4:]]
    units = []
    for index, (row, identities) in enumerate(zip(full["rows"], token_vectors, strict=True)):
        units.append(
            {
                "all_sides_complete_declared": True,
                "g_id": row["g_id"],
                "primary_f_id": row["primary_f_id"],
                "sides": [
                    {
                        "lines": [
                            {
                                "line_id": opaque(f"line-{index}"),
                                "line_index": 0,
                                "tokens": [
                                    {
                                        "disposition": "included",
                                        "length_identity_id": (
                                            tokens["c"] if identity == tokens["c"] else identity
                                        ),
                                        "scoring_identity_id": identity,
                                        "token_index": token_index,
                                    }
                                    for token_index, identity in enumerate(identities)
                                ],
                            }
                        ],
                        "side_id": opaque(f"side-{index}"),
                        "side_index": 0,
                    }
                ],
                "source_binding_sha256": checksum(f"x-source-{index}"),
            }
        )
    value = {
        "assignment_roster_sha256": full_digest,
        "claim_binding": full["claim_binding"],
        "format_version": "1.0.0",
        "gate_plan_sha256": "sha256:" + common._GATE_PLAN_SHA256,
        "measurement_plan_sha256": "sha256:" + common._PLAN_SHA256,
        "model": model,
        "parent_protocol_sha256": "sha256:" + common._PARENT_PROTOCOL_SHA256,
        "record_kind": "nmfa_x_model_batch",
        "selector_assignment_raw_sha256": full["selector_assignment_raw_sha256"],
        "selector_plan_sha256": "sha256:" + common._SELECTOR_PLAN_SHA256,
        "units": units,
    }
    return value, domain_digest(x_core._MODEL_DOMAIN, model)


def y_batch(
    full: dict[str, Any],
    *,
    family: str = "direct_count",
    values: tuple[int, ...] = (0, 1, 1, 2),
) -> tuple[dict[str, Any], str]:
    _, _, full_digest = roster_raw_and_digests(full)
    canonical_unit = opaque("canonical-unit")
    contract = {
        "canonical_unit_id": canonical_unit,
        "conversions": [
            {
                "multiplier": {"denominator": 1, "numerator": 1},
                "source_unit_id": canonical_unit,
            }
        ],
        "policy_commitments": {
            "canonical_unit_conversion_policy_sha256": checksum("conversion-policy"),
            "measurement_policy_sha256": checksum("measurement-policy"),
            "repeated_measurement_resolution_policy_sha256": checksum("repeat-policy"),
        },
        "target_family": family,
    }
    fill_value = 0 if family == "direct_count" else 1
    targets = values + (fill_value,) * (len(full["rows"]) - len(values))
    units = [
        {
            "g_id": row["g_id"],
            "primary_f_id": row["primary_f_id"],
            "source_binding_sha256": checksum(f"y-source-{index}"),
            "source_unit_id": canonical_unit,
            "source_value": {"denominator": 1, "numerator": target},
        }
        for index, (row, target) in enumerate(zip(full["rows"], targets, strict=True))
    ]
    value = {
        "assignment_roster_sha256": full_digest,
        "claim_binding": full["claim_binding"],
        "format_version": "1.0.0",
        "gate_plan_sha256": "sha256:" + common._GATE_PLAN_SHA256,
        "measurement_plan_sha256": "sha256:" + common._PLAN_SHA256,
        "parent_protocol_sha256": "sha256:" + common._PARENT_PROTOCOL_SHA256,
        "record_kind": "nmfa_y_target_batch",
        "selector_assignment_raw_sha256": full["selector_assignment_raw_sha256"],
        "selector_plan_sha256": "sha256:" + common._SELECTOR_PLAN_SHA256,
        "target_contract": contract,
        "units": units,
    }
    return value, domain_digest(y_core._TARGET_CONTRACT_DOMAIN, contract)


def run_score(full: dict[str, Any], x_value: dict[str, Any], model_digest: str):
    roster_raw, roster_digest, _ = roster_raw_and_digests(full)
    x_raw = encode_json(x_value)
    with local_resources():
        return x_core.score_nmfa_x_batch(
            roster_raw,
            roster_digest,
            x_raw,
            sha256(x_raw),
            model_digest,
        )


def run_target(full: dict[str, Any], y_value: dict[str, Any], contract_digest: str):
    roster_raw, roster_digest, _ = roster_raw_and_digests(full)
    y_raw = encode_json(y_value)
    with local_resources():
        return y_core.normalize_nmfa_y_batch(
            roster_raw,
            roster_digest,
            y_raw,
            sha256(y_raw),
            contract_digest,
        )


def integer_midranks(values: tuple[int, ...]) -> tuple[int, ...]:
    with local_resources():
        return statistics.doubled_midranks_integers(values)


def exact_threshold(
    covariance: int,
    variance_left: int,
    variance_target: int,
    threshold_numerator: int,
    threshold_denominator: int,
) -> bool:
    with local_resources():
        return statistics.exact_nmfa_spearman_at_least(
            covariance,
            variance_left,
            variance_target,
            threshold_numerator,
            threshold_denominator,
        )


class NMFAMeasurementCoreTests(unittest.TestCase):
    maxDiff = None

    def test_plan_and_all_schemas_are_canonical_closed_draft_2020_12(self) -> None:
        plan = read_json(PLAN_PATH)
        for path in SCHEMA_PATHS:
            schema = read_json(path)
            self.assertEqual(encode_json(schema), path.read_bytes())
            Draft202012Validator.check_schema(schema)
        plan_schema = read_json(ROOT / "schemas/nmfa-measurement-core-plan.schema.json")
        validator = Draft202012Validator(plan_schema, format_checker=FormatChecker())
        self.assertEqual([], list(validator.iter_errors(plan)))
        self.assertEqual(encode_json(plan), PLAN_PATH.read_bytes())
        self.assertEqual(
            "display_only_not_decision_bearing_future_gate_delta_bootstrap_and_control_ordering_require_separately_frozen_exact_algorithms",
            plan["algorithms"]["fixed_point_display"]["decision_use"],
        )
        self.assertEqual(
            "sha256:99f8f35e63cb5d719fbdce42131cf6cf0d1b2b68f2ac97c474a393e971b37d58",
            x_core._class_id(plan["fixed_vectors"]["class_identity"]["member_token_ids"]),
        )
        runtime_domains = {
            "assignment_roster": common._ROSTER_DOMAIN,
            "doubled_ranks": statistics._RANK_DOMAIN,
            "metric_receipt": statistics._METRIC_RECEIPT_DOMAIN,
            "metric_roster": common._METRIC_ROSTER_DOMAIN,
            "model": x_core._MODEL_DOMAIN,
            "model_class": x_core._CLASS_DOMAIN,
            "score_receipt": x_core._SCORE_RECEIPT_DOMAIN,
            "target_contract": y_core._TARGET_CONTRACT_DOMAIN,
            "target_receipt": y_core._TARGET_RECEIPT_DOMAIN,
            "x_batch": x_core._X_BATCH_DOMAIN,
            "y_batch": y_core._Y_BATCH_DOMAIN,
        }
        self.assertEqual(
            plan["algorithms"]["digest_framing"]["domains"],
            {
                name: domain.removesuffix(b"\x00").decode("ascii")
                for name, domain in runtime_domains.items()
            },
        )
        self.assertTrue(all(domain.endswith(b"\x00") for domain in runtime_domains.values()))
        metric_schema = read_json(ROOT / "schemas/nmfa-metric-receipt.schema.json")
        self.assertEqual(
            plan["algorithms"]["undefined_precedence"][:-1],
            metric_schema["$defs"]["undefined_metric"]["properties"]["status"]["enum"],
        )

        mutated = copy.deepcopy(plan)
        mutated["algorithms"]["model"]["weight_range"][1] = 17
        self.assertIsNotNone(next(validator.iter_errors(mutated), None))
        extra = copy.deepcopy(plan)
        extra["limits"]["unbound"] = 1
        self.assertIsNotNone(next(validator.iter_errors(extra), None))

    def test_bundle_closes_runtime_and_three_module_information_boundary(self) -> None:
        bundle = read_json(BUNDLE_PATH)
        self.assertEqual(encode_json(bundle), BUNDLE_PATH.read_bytes())
        self.assertEqual("nmfa-measurement-core-evaluator-bundle-v1", bundle["bundle_id"])
        self.assertEqual(common._EXPECTED_RUNTIME_PROFILE, bundle["runtime_profile"])
        self.assertEqual(common._EXPECTED_SECURITY_BOUNDARY, bundle["security_boundary"])
        self.assertEqual(common._BUNDLE_FILE_PATHS, {row["path"] for row in bundle["files"]})
        for row in bundle["files"]:
            raw = (ROOT / row["path"]).read_bytes()
            self.assertEqual(row["bytes"], len(raw))
            self.assertEqual(row["sha256"], sha256(raw))

        imports: dict[str, set[str]] = {}
        for module in ("nmfa_x_model_core.py", "nmfa_y_rational_core.py"):
            tree = ast.parse((ROOT / "src/indusbench" / module).read_text())
            imports[module] = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertNotIn("indusbench.nmfa_y_rational_core", imports["nmfa_x_model_core.py"])
        self.assertNotIn("indusbench.nmfa_x_model_core", imports["nmfa_y_rational_core.py"])

        for public_primitive in (
            lambda: statistics.doubled_midranks_integers((1, 2)),
            lambda: statistics.exact_nmfa_spearman_at_least(1, 1, 1, 0, 1),
        ):
            with (
                self.subTest(public_primitive=public_primitive.__code__.co_firstlineno),
                patch.object(
                    statistics,
                    "_validate_installed_bundle",
                    side_effect=common.NMFAMeasurementError(
                        common.NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID
                    ),
                ),
                self.assertRaisesRegex(
                    common.NMFAMeasurementError,
                    "^PACKAGE_RESOURCE_INVALID$",
                ),
            ):
                public_primitive()

        for public_primitive in (
            lambda: statistics.doubled_midranks_integers((1, 2)),
            lambda: statistics.exact_nmfa_spearman_at_least(1, 1, 1, 0, 1),
        ):
            with (
                self.subTest(public_primitive_end=public_primitive.__code__.co_firstlineno),
                patch.object(
                    statistics,
                    "_validate_installed_bundle",
                    return_value=checksum("stable-bundle"),
                ),
                patch.object(
                    common,
                    "_validate_installed_bundle",
                    return_value=checksum("changed-bundle"),
                ),
                self.assertRaisesRegex(
                    common.NMFAMeasurementError,
                    "^PACKAGE_RESOURCE_INVALID$",
                ),
            ):
                public_primitive()

    def test_installed_plan_and_resource_locks(self) -> None:
        with local_resources():
            plan = common.load_installed_nmfa_measurement_plan()
        self.assertEqual("nmfa-measurement-core-plan-v1", plan["plan_id"])
        for relative, (size, digest) in common._RESOURCE_LOCKS.items():
            raw = (ROOT / relative).read_bytes()
            self.assertEqual((size, digest), (len(raw), hashlib.sha256(raw).hexdigest()))

    def test_end_to_end_separated_score_target_and_exact_statistics(self) -> None:
        full = roster()
        full_raw, full_raw_digest, _ = roster_raw_and_digests(full)
        metric_value = metric_roster(full, full["rows"][:4])
        metric_raw = encode_json(metric_value)
        x_value, model_digest = x_batch(full)
        y_value, contract_digest = y_batch(full)
        with local_resources():
            score = x_core.score_nmfa_x_batch(
                full_raw,
                full_raw_digest,
                encode_json(x_value),
                sha256(encode_json(x_value)),
                model_digest,
            )
            target = y_core.normalize_nmfa_y_batch(
                full_raw,
                full_raw_digest,
                encode_json(y_value),
                sha256(encode_json(y_value)),
                contract_digest,
            )
            metric = statistics.evaluate_nmfa_rank_metrics(
                full_raw,
                full_raw_digest,
                metric_raw,
                sha256(metric_raw),
                score.receipt_bytes,
                score.receipt_raw_sha256,
                target.receipt_bytes,
                target.receipt_raw_sha256,
            )
            score_value = score.receipt()
            target_value = target.receipt()
            metric_value_out = metric.receipt()
            x_core.verify_nmfa_score_receipt(
                full_raw,
                full_raw_digest,
                encode_json(x_value),
                sha256(encode_json(x_value)),
                model_digest,
                score.receipt_bytes,
            )
            y_core.verify_nmfa_target_receipt(
                full_raw,
                full_raw_digest,
                encode_json(y_value),
                sha256(encode_json(y_value)),
                contract_digest,
                target.receipt_bytes,
            )
            statistics.verify_nmfa_metric_receipt(
                full_raw,
                full_raw_digest,
                metric_raw,
                sha256(metric_raw),
                score.receipt_bytes,
                score.receipt_raw_sha256,
                target.receipt_bytes,
                target.receipt_raw_sha256,
                metric.receipt_bytes,
            )

        self.assertEqual([0, 0, 1, 2], [row["score"] for row in score_value["rows"][:4]])
        self.assertEqual([1, 2, 1, 1], [row["l_total"] for row in score_value["rows"][:4]])
        self.assertEqual([1, 1, 1, 1], [row["l_distinct"] for row in score_value["rows"][:4]])
        self.assertEqual(
            ["0", "1", "1", "2"],
            [row["canonical_value"]["numerator"] for row in target_value["rows"][:4]],
        )
        primary = metric_value_out["metrics"]["score_vs_target"]
        self.assertEqual("60", primary["covariance_c"])
        self.assertEqual("72", primary["variance_left"])
        self.assertEqual("72", primary["variance_target"])
        self.assertEqual(833_333_333_333, primary["rho_scaled_1e12"])
        self.assertEqual("0.833333333333", primary["rho_decimal_12"])
        self.assertEqual(
            "undefined_zero_variance_left",
            metric_value_out["metrics"]["l_distinct_vs_target"]["status"],
        )
        self.assertNotIn(opaque("a1"), score.receipt_bytes.decode())
        self.assertNotIn(opaque("canonical-unit"), metric.receipt_bytes.decode())
        self.assertEqual("<ProtectedNMFAScoreState protected>", repr(score))
        self.assertEqual("<ProtectedNMFATargetState protected>", repr(target))
        self.assertEqual("<ProtectedNMFAMetricState protected>", repr(metric))
        self.assertFalse(
            metric_value_out["assurance_boundary"]["score_receipt_digest_origin_verified"]
        )
        self.assertFalse(
            metric_value_out["assurance_boundary"]["target_receipt_digest_origin_verified"]
        )
        self.assertIn(
            "PROCESS_CUSTODY_INFORMATION_SEPARATION_UNBOUND", metric_value_out["compiled_blockers"]
        )

        for decoder, receipt_value, error_name in (
            (x_core._decode_score_receipt, score_value, "SCORE_RECEIPT_INVALID"),
            (y_core._decode_target_receipt, target_value, "TARGET_RECEIPT_INVALID"),
        ):
            reordered = copy.deepcopy(receipt_value)
            reordered["rows"][0], reordered["rows"][1] = (
                reordered["rows"][1],
                reordered["rows"][0],
            )
            duplicate_f = copy.deepcopy(receipt_value)
            duplicate_f["rows"][1]["primary_f_id"] = duplicate_f["rows"][0]["primary_f_id"]
            for impossible in (reordered, duplicate_f):
                impossible_raw = encode_json(impossible)
                with (
                    self.subTest(decoder=decoder.__name__, impossible=sha256(impossible_raw)[:16]),
                    local_resources(),
                    self.assertRaisesRegex(common.NMFAMeasurementError, f"^{error_name}$"),
                ):
                    decoder(impossible_raw, sha256(impossible_raw))

        shared_target_mutations = {
            "distinct_target_levels": 2,
            "n": 5,
            "target_doubled_ranks_sha256": checksum("different-target-ranks"),
        }
        for field, replacement in shared_target_mutations.items():
            inconsistent_metric = copy.deepcopy(metric_value_out)
            inconsistent_metric["metrics"]["l_total_vs_target"][field] = replacement
            inconsistent_raw = encode_json(inconsistent_metric)
            with (
                self.subTest(inconsistent_shared_target_field=field),
                local_resources(),
                self.assertRaisesRegex(common.NMFAMeasurementError, "^METRIC_RECEIPT_INVALID$"),
            ):
                statistics._decode_metric_receipt(inconsistent_raw, sha256(inconsistent_raw))

        contradictory_target_variance = copy.deepcopy(metric_value_out)
        contradictory = contradictory_target_variance["metrics"]["score_vs_target"]
        contradictory["variance_target"] = "73"
        contradictory["denominator_radicand"] = str(int(contradictory["variance_left"]) * 73)
        contradictory["rho_scaled_1e12"] = statistics._round_ratio_sqrt(
            int(contradictory["covariance_c"]),
            int(contradictory["denominator_radicand"]),
        )
        contradictory["rho_decimal_12"] = statistics._format_scaled(
            contradictory["rho_scaled_1e12"]
        )
        contradictory_raw = encode_json(contradictory_target_variance)
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^METRIC_RECEIPT_INVALID$"),
        ):
            statistics._decode_metric_receipt(contradictory_raw, sha256(contradictory_raw))

        impossible_variance = copy.deepcopy(metric_value_out)
        impossible = impossible_variance["metrics"]["score_vs_target"]
        impossible["variance_left"] = "81"
        impossible["denominator_radicand"] = str(81 * int(impossible["variance_target"]))
        impossible["rho_scaled_1e12"] = statistics._round_ratio_sqrt(
            int(impossible["covariance_c"]),
            int(impossible["denominator_radicand"]),
        )
        impossible["rho_decimal_12"] = statistics._format_scaled(impossible["rho_scaled_1e12"])
        impossible_raw = encode_json(impossible_variance)
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^METRIC_RECEIPT_INVALID$"),
        ):
            statistics._decode_metric_receipt(impossible_raw, sha256(impossible_raw))

        below_minimum_variance = copy.deepcopy(metric_value_out)
        below_minimum = below_minimum_variance["metrics"]["score_vs_target"]
        below_minimum["covariance_c"] = "0"
        below_minimum["variance_left"] = "1"
        below_minimum["denominator_radicand"] = below_minimum["variance_target"]
        below_minimum["rho_scaled_1e12"] = 0
        below_minimum["rho_decimal_12"] = "0.000000000000"
        below_minimum_raw = encode_json(below_minimum_variance)
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^METRIC_RECEIPT_INVALID$"),
        ):
            statistics._decode_metric_receipt(below_minimum_raw, sha256(below_minimum_raw))

    def test_model_score_order_exclusion_and_length_contracts(self) -> None:
        full = roster()
        x_value, model_digest = x_batch(full)
        excluded = x_value["units"][0]["sides"][0]["lines"][0]["tokens"][0]
        excluded["disposition"] = "excluded_damage_policy"
        with local_resources():
            score = run_score(full, x_value, model_digest).receipt()
        self.assertEqual(
            (0, 0, 0), tuple(score["rows"][0][key] for key in ("score", "l_total", "l_distinct"))
        )

        invalid_cases: list[dict[str, Any]] = []
        overlap = copy.deepcopy(x_value)
        member = overlap["model"]["classes"][0]["member_token_ids"][0]
        overlap["model"]["classes"][1]["member_token_ids"].append(member)
        overlap["model"]["classes"][1]["member_token_ids"].sort()
        overlap["model"]["classes"][1]["class_id"] = domain_digest(
            x_core._CLASS_DOMAIN,
            {"member_token_ids": overlap["model"]["classes"][1]["member_token_ids"]},
        )
        overlap["model"]["classes"].sort(key=lambda row: row["class_id"])
        invalid_cases.append(overlap)
        nonprimitive_weights = copy.deepcopy(x_value)
        for class_row in nonprimitive_weights["model"]["classes"]:
            class_row["weight"] *= 2
        invalid_cases.append(nonprimitive_weights)
        gap = copy.deepcopy(x_value)
        gap["units"][1]["sides"][0]["lines"][0]["tokens"][1]["token_index"] = 2
        invalid_cases.append(gap)
        duplicate_side = copy.deepcopy(x_value)
        duplicate_side["units"][1]["sides"][0]["side_id"] = duplicate_side["units"][0]["sides"][0][
            "side_id"
        ]
        invalid_cases.append(duplicate_side)
        duplicate_line = copy.deepcopy(x_value)
        duplicate_line["units"][1]["sides"][0]["lines"][0]["line_id"] = duplicate_line["units"][0][
            "sides"
        ][0]["lines"][0]["line_id"]
        invalid_cases.append(duplicate_line)
        forbidden_y = copy.deepcopy(x_value)
        forbidden_y["units"][0]["target_y"] = 7
        invalid_cases.append(forbidden_y)
        for invalid in invalid_cases:
            digest = domain_digest(x_core._MODEL_DOMAIN, invalid["model"])
            with (
                self.subTest(case=hashlib.sha256(encode_json(invalid)).hexdigest()[:8]),
                self.assertRaises(common.NMFAMeasurementError),
            ):
                run_score(full, invalid, digest)

        full_raw, full_raw_digest, _ = roster_raw_and_digests(full)
        x_raw = encode_json(x_value)
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^X_CONTRACT_INVALID$"),
        ):
            x_core.score_nmfa_x_batch(
                full_raw,
                full_raw_digest,
                x_raw,
                checksum("wrong-x-raw"),
                model_digest,
            )

    def test_rational_conversion_zero_and_family_boundaries(self) -> None:
        full = roster()
        value, _ = y_batch(full, family="mass", values=(1, 2, 3, 4))
        canonical = value["target_contract"]["canonical_unit_id"]
        source_unit = opaque("grams")
        conversions: list[dict[str, Any]] = [
            {
                "multiplier": {"denominator": 1, "numerator": 1},
                "source_unit_id": canonical,
            },
            {
                "multiplier": {"denominator": 1000, "numerator": 1},
                "source_unit_id": source_unit,
            },
        ]
        value["target_contract"]["conversions"] = sorted(
            conversions,
            key=lambda row: str(row["source_unit_id"]),
        )
        value["units"][0]["source_unit_id"] = source_unit
        value["units"][0]["source_value"] = {"denominator": 1, "numerator": 1500}
        digest = domain_digest(y_core._TARGET_CONTRACT_DOMAIN, value["target_contract"])
        with local_resources():
            receipt = run_target(full, value, digest).receipt()
        self.assertEqual(
            {"denominator": "2", "numerator": "3"},
            receipt["rows"][0]["canonical_value"],
        )

        maximum = (1 << 63) - 1
        boundary, _ = y_batch(full, family="mass", values=(maximum, 1, 1, 1))
        boundary_unit = opaque("boundary-unit")
        boundary["target_contract"]["conversions"].append(
            {
                "multiplier": {"denominator": 1, "numerator": maximum},
                "source_unit_id": boundary_unit,
            }
        )
        boundary["target_contract"]["conversions"].sort(key=lambda row: row["source_unit_id"])
        boundary["units"][0]["source_unit_id"] = boundary_unit
        boundary_digest = domain_digest(y_core._TARGET_CONTRACT_DOMAIN, boundary["target_contract"])
        with local_resources():
            boundary_receipt = run_target(full, boundary, boundary_digest).receipt()
        self.assertEqual(
            str(maximum * maximum),
            boundary_receipt["rows"][0]["canonical_value"]["numerator"],
        )

        cancellation, _ = y_batch(full, family="mass", values=(1, 1, 1, 1))
        cancellation_unit = opaque("cancellation-unit")
        cancellation["target_contract"]["conversions"].append(
            {
                "multiplier": {
                    "denominator": maximum,
                    "numerator": maximum - 1,
                },
                "source_unit_id": cancellation_unit,
            }
        )
        cancellation["target_contract"]["conversions"].sort(key=lambda row: row["source_unit_id"])
        cancellation["units"][0]["source_unit_id"] = cancellation_unit
        cancellation["units"][0]["source_value"] = {
            "denominator": maximum - 1,
            "numerator": maximum,
        }
        cancellation_digest = domain_digest(
            y_core._TARGET_CONTRACT_DOMAIN, cancellation["target_contract"]
        )
        with local_resources():
            cancellation_receipt = run_target(full, cancellation, cancellation_digest).receipt()
        self.assertEqual(
            {"denominator": "1", "numerator": "1"},
            cancellation_receipt["rows"][0]["canonical_value"],
        )

        above_maximum, above_digest = y_batch(full)
        above_maximum["units"][0]["source_value"]["numerator"] = maximum + 1
        with self.assertRaisesRegex(common.NMFAMeasurementError, "^Y_CONTRACT_INVALID$"):
            run_target(full, above_maximum, above_digest)

        count_value, count_digest = y_batch(full)
        with local_resources():
            zero_numerator = run_target(full, count_value, count_digest).receipt()["rows"][0][
                "canonical_value"
            ]["numerator"]
        self.assertEqual("0", zero_numerator)
        invalid_mass, invalid_digest = y_batch(full, family="mass", values=(0, 1, 1, 2))
        with self.assertRaisesRegex(common.NMFAMeasurementError, "^Y_CONTRACT_INVALID$"):
            run_target(full, invalid_mass, invalid_digest)
        nonreduced, _ = y_batch(full)
        nonreduced["target_contract"]["conversions"][0]["multiplier"] = {
            "denominator": 2,
            "numerator": 2,
        }
        digest = domain_digest(y_core._TARGET_CONTRACT_DOMAIN, nonreduced["target_contract"])
        with self.assertRaisesRegex(common.NMFAMeasurementError, "^TARGET_CONTRACT_INVALID$"):
            run_target(full, nonreduced, digest)
        forbidden = copy.deepcopy(count_value)
        forbidden["units"][0]["score"] = 1
        with self.assertRaisesRegex(common.NMFAMeasurementError, "^Y_CONTRACT_INVALID$"):
            run_target(full, forbidden, count_digest)

        full_raw, full_raw_digest, _ = roster_raw_and_digests(full)
        count_raw = encode_json(count_value)
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^Y_CONTRACT_INVALID$"),
        ):
            y_core.normalize_nmfa_y_batch(
                full_raw,
                full_raw_digest,
                count_raw,
                checksum("wrong-y-raw"),
                count_digest,
            )

    def test_full_and_metric_rosters_are_distinct_and_fail_closed(self) -> None:
        full = roster()
        full_raw, full_raw_digest, _ = roster_raw_and_digests(full)
        subset = metric_roster(full, full["rows"][1:3])
        subset_raw = encode_json(subset)
        with local_resources():
            accepted = common.validate_nmfa_metric_roster(
                full_raw,
                full_raw_digest,
                subset_raw,
                sha256(subset_raw),
            )
        self.assertEqual(2, len(accepted.rows))

        outside = copy.deepcopy(subset)
        outside["rows"].append(
            {"g_id": "sha256:" + "f" * 64, "primary_f_id": "hmac-sha256:" + "f" * 64}
        )
        outside["rows"].sort(key=lambda row: (row["g_id"], row["primary_f_id"]))
        outside_raw = encode_json(outside)
        with (
            local_resources(),
            self.assertRaisesRegex(
                common.NMFAMeasurementError,
                "^METRIC_ROSTER_CONTRACT_INVALID$",
            ),
        ):
            common.validate_nmfa_metric_roster(
                full_raw,
                full_raw_digest,
                outside_raw,
                sha256(outside_raw),
            )

        for duplicate_field in ("g_id", "primary_f_id"):
            duplicate = roster()
            duplicate["rows"][1][duplicate_field] = duplicate["rows"][0][duplicate_field]
            duplicate["rows"].sort(key=lambda row: (row["g_id"], row["primary_f_id"]))
            duplicate_raw = encode_json(duplicate)
            with (
                self.subTest(duplicate_field=duplicate_field),
                local_resources(),
                self.assertRaisesRegex(common.NMFAMeasurementError, "^ROSTER_CONTRACT_INVALID$"),
            ):
                common.validate_nmfa_gf_roster(duplicate_raw, sha256(duplicate_raw))

        short = roster(159)
        short_raw = encode_json(short)
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^ROSTER_CONTRACT_INVALID$"),
        ):
            common.validate_nmfa_gf_roster(short_raw, sha256(short_raw))

    def test_midrank_exact_state_rounding_and_threshold_vectors(self) -> None:
        plan = read_json(PLAN_PATH)
        vector = plan["fixed_vectors"]["doubled_midranks"]
        self.assertEqual(
            tuple(vector["expected"]),
            integer_midranks(tuple(vector["values"])),
        )
        tied = plan["fixed_vectors"]["spearman_tied"]
        state = statistics._metric_state(
            [0, 0, 1, 2],
            [y_core.CanonicalRational(value, 1) for value in (0, 1, 1, 2)],
        )
        self.assertEqual(tied["covariance_numerator"], state["covariance_c"])
        self.assertEqual(tied["expected_scaled_integer"], state["rho_scaled_1e12"])
        for row in plan["fixed_vectors"]["half_even"]:
            self.assertEqual(
                row["expected"],
                statistics._round_ratio_sqrt(
                    row["numerator"],
                    row["denominator_radicand"],
                    row["scale"],
                ),
            )
        self.assertTrue(exact_threshold(2, 5, 5, 2, 5))
        self.assertFalse(exact_threshold(-1, 2, 2, 0, 1))
        self.assertTrue(exact_threshold(4, 4, 4, 1, 1))
        exact_limit = 1 << 255
        self.assertTrue(
            exact_threshold(
                exact_limit,
                exact_limit,
                exact_limit,
                1,
                1,
            )
        )
        self.assertFalse(exact_threshold(-1, 2, 2, 1, 10))
        self.assertFalse(exact_threshold(799_999_999_999, 1, 4 * 10**24, 2, 5))
        self.assertEqual(
            (2, 4, -2, -4, 1, -1),
            tuple(
                statistics._round_ratio_sqrt(numerator, radicand, scale)
                for numerator, radicand, scale in (
                    (1, 16, 10),
                    (7, 400, 10),
                    (-1, 16, 10),
                    (-7, 400, 10),
                    (1, 1, 1),
                    (-1, 1, 1),
                )
            ),
        )
        with self.assertRaisesRegex(common.NMFAMeasurementError, "^INVALID_ARGUMENT$"):
            exact_threshold(2, 1, 1, 1, 1)
        with self.assertRaisesRegex(common.NMFAMeasurementError, "^INVALID_ARGUMENT$"):
            exact_threshold(-2, 1, 1, 0, 1)
        with self.assertRaisesRegex(common.NMFAMeasurementError, "^INVALID_ARGUMENT$"):
            exact_threshold(1 << 256, 1, 1 << 512, 0, 1)

    def test_midrank_differential_oracle(self) -> None:
        generator = random.Random(20260803)
        for n in range(1, 31):
            values = tuple(generator.randrange(7) for _ in range(n))
            expected = tuple(
                2 * sum(other < value for other in values)
                + sum(other == value for other in values)
                + 1
                for value in values
            )
            self.assertEqual(expected, integer_midranks(values))

            self.assertEqual(n * (n + 1), sum(expected))

        rationals = [
            y_core.CanonicalRational(1, 2),
            y_core.CanonicalRational(2, 3),
            y_core.CanonicalRational(3, 4),
            y_core.CanonicalRational(1, 2),
        ]
        fractions = [Fraction(value.numerator, value.denominator) for value in rationals]
        rational_oracle = [
            2 * sum(other < value for other in fractions)
            + sum(other == value for other in fractions)
            + 1
            for value in fractions
        ]
        self.assertEqual(
            rational_oracle,
            statistics._doubled_midranks(rationals, statistics._compare_rational),
        )

        with localcontext() as context:
            context.prec = 100
            for _ in range(500):
                numerator = generator.randrange(-1_000_000, 1_000_001)
                radicand = generator.randrange(1, 1_000_001)
                expected_scaled = int(
                    (
                        Decimal(numerator) * Decimal(statistics._SCALE) / Decimal(radicand).sqrt()
                    ).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
                )
                self.assertEqual(
                    expected_scaled,
                    statistics._round_ratio_sqrt(numerator, radicand),
                )

    def test_undefined_states_and_receipt_tamper(self) -> None:
        one = statistics._metric_state([1], [y_core.CanonicalRational(2, 1)])
        self.assertEqual("undefined_insufficient_observations", one["status"])
        target = [y_core.CanonicalRational(value, 1) for value in (0, 1, 2)]
        state = statistics._metric_state([1, 1, 1], target)
        self.assertEqual("undefined_zero_variance_left", state["status"])
        self.assertNotIn("rho_scaled_1e12", state)
        both = statistics._metric_state(
            [1, 1, 1],
            [y_core.CanonicalRational(2, 1)] * 3,
        )
        self.assertEqual("undefined_zero_variance_both", both["status"])
        target_constant = statistics._metric_state(
            [0, 1, 2],
            [y_core.CanonicalRational(2, 1)] * 3,
        )
        self.assertEqual("undefined_zero_variance_target", target_constant["status"])
        perfect = statistics._metric_state(
            [0, 1, 2, 3],
            [y_core.CanonicalRational(value, 1) for value in (0, 1, 2, 3)],
        )
        reverse = statistics._metric_state(
            [0, 1, 2, 3],
            [y_core.CanonicalRational(value, 1) for value in (3, 2, 1, 0)],
        )
        self.assertEqual(statistics._SCALE, perfect["rho_scaled_1e12"])
        self.assertEqual(-statistics._SCALE, reverse["rho_scaled_1e12"])

        full = roster()
        x_value, model_digest = x_batch(full)
        score = run_score(full, x_value, model_digest)
        tampered = bytearray(score.receipt_bytes)
        tampered[-2] = ord(" ")
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^SCORE_RECEIPT_INVALID$"),
        ):
            tampered_raw = bytes(tampered)
            x_core._decode_score_receipt(tampered_raw, sha256(tampered_raw))

        with local_resources():
            score_value = score.receipt()
        for impossible_row in (
            {"l_distinct": 0, "l_total": 1, "score": 1},
            {"l_distinct": 1, "l_total": 1, "score": 17},
        ):
            impossible = copy.deepcopy(score_value)
            impossible["rows"][0].update(impossible_row)
            impossible_raw = encode_json(impossible)
            with (
                self.subTest(impossible_row=impossible_row),
                local_resources(),
                self.assertRaisesRegex(common.NMFAMeasurementError, "^SCORE_RECEIPT_INVALID$"),
            ):
                x_core._decode_score_receipt(impossible_raw, sha256(impossible_raw))

    def test_bundle_change_during_each_component_fails_closed(self) -> None:
        full = roster()
        full_raw, full_raw_digest, _ = roster_raw_and_digests(full)
        x_value, model_digest = x_batch(full)
        x_raw = encode_json(x_value)
        y_value, contract_digest = y_batch(full)
        y_raw = encode_json(y_value)
        metric_value = metric_roster(full, full["rows"][:4])
        metric_raw = encode_json(metric_value)
        with local_resources():
            stable_bundle = common._validate_installed_bundle()
            score = run_score(full, x_value, model_digest)
            target = run_target(full, y_value, contract_digest)
            metric = statistics.evaluate_nmfa_rank_metrics(
                full_raw,
                full_raw_digest,
                metric_raw,
                sha256(metric_raw),
                score.receipt_bytes,
                score.receipt_raw_sha256,
                target.receipt_bytes,
                target.receipt_raw_sha256,
            )
            score_value = score.receipt()
            target_value = target.receipt()
            metric_value_out = metric.receipt()
        changed_bundle = checksum("changed-bundle")

        def drift_after_two_calls():
            calls = 0

            def drift() -> str:
                nonlocal calls
                calls += 1
                return stable_bundle if calls <= 2 else changed_bundle

            return drift

        with (
            local_resources(),
            patch.object(common, "_validate_installed_bundle", side_effect=drift_after_two_calls()),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^PACKAGE_RESOURCE_INVALID$"),
        ):
            x_core.score_nmfa_x_batch(
                full_raw,
                full_raw_digest,
                x_raw,
                sha256(x_raw),
                model_digest,
            )
        with (
            local_resources(),
            patch.object(common, "_validate_installed_bundle", side_effect=drift_after_two_calls()),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^PACKAGE_RESOURCE_INVALID$"),
        ):
            y_core.normalize_nmfa_y_batch(
                full_raw,
                full_raw_digest,
                y_raw,
                sha256(y_raw),
                contract_digest,
            )
        with (
            local_resources(),
            patch.object(common, "_validate_installed_bundle", side_effect=drift_after_two_calls()),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^PACKAGE_RESOURCE_INVALID$"),
        ):
            statistics.evaluate_nmfa_rank_metrics(
                full_raw,
                full_raw_digest,
                metric_raw,
                sha256(metric_raw),
                score.receipt_bytes,
                score.receipt_raw_sha256,
                target.receipt_bytes,
                target.receipt_raw_sha256,
            )

        for module, decoder_name, raw, raw_sha256 in (
            (x_core, "_decode_score_receipt", score.receipt_bytes, score.receipt_raw_sha256),
            (y_core, "_decode_target_receipt", target.receipt_bytes, target.receipt_raw_sha256),
            (
                statistics,
                "_decode_metric_receipt",
                metric.receipt_bytes,
                metric.receipt_raw_sha256,
            ),
        ):
            with (
                self.subTest(decoder_end_guard=decoder_name),
                local_resources(),
                patch.object(module, "_validate_installed_bundle", return_value=stable_bundle),
                patch.object(
                    common,
                    "_validate_installed_bundle",
                    return_value=changed_bundle,
                ),
                self.assertRaisesRegex(common.NMFAMeasurementError, "^PACKAGE_RESOURCE_INVALID$"),
            ):
                getattr(module, decoder_name)(raw, raw_sha256, stable_bundle)

        for module, decoder_name, protected_state, decoded_value in (
            (x_core, "_decode_score_receipt", score, score_value),
            (y_core, "_decode_target_receipt", target, target_value),
            (statistics, "_decode_metric_receipt", metric, metric_value_out),
        ):
            with (
                self.subTest(protected_receipt_end_guard=decoder_name),
                patch.object(module, decoder_name, return_value=decoded_value),
                patch.object(
                    common,
                    "_validate_installed_bundle",
                    return_value=changed_bundle,
                ),
                self.assertRaisesRegex(common.NMFAMeasurementError, "^PACKAGE_RESOURCE_INVALID$"),
            ):
                protected_state.receipt()

    def test_noncanonical_huge_integer_and_bundle_change_are_fixed_errors(self) -> None:
        full = roster()
        raw, digest, _ = roster_raw_and_digests(full)
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^ROSTER_CONTRACT_INVALID$"),
        ):
            noncanonical = raw.rstrip(b"\n")
            common.validate_nmfa_gf_roster(noncanonical, sha256(noncanonical))
        huge = raw.replace(b'"format_version": "1.0.0"', b'"format_version": ' + b"9" * 5000)
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^ROSTER_CONTRACT_INVALID$"),
        ):
            common.validate_nmfa_gf_roster(huge, sha256(huge))
        lone_surrogate = b'{"value":"\\ud800"}\n'
        with self.assertRaisesRegex(common.NMFAMeasurementError, "^ROSTER_CONTRACT_INVALID$"):
            common._decode_canonical_json(
                lone_surrogate,
                common.NMFAMeasurementErrorCode.ROSTER_CONTRACT_INVALID,
            )
        with (
            patch.object(common, "_resource_bytes", return_value=lone_surrogate),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^PACKAGE_RESOURCE_INVALID$"),
        ):
            common._validate_installed_bundle()
        with (
            local_resources(),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^ROSTER_CONTRACT_INVALID$"),
        ):
            common.validate_nmfa_gf_roster(cast(bytes, "not-bytes"), digest)
        with (
            patch.object(common, "_validate_installed_bundle", return_value=checksum("changed")),
            self.assertRaisesRegex(common.NMFAMeasurementError, "^PACKAGE_RESOURCE_INVALID$"),
        ):
            common._require_unchanged_bundle(checksum("expected"))


if __name__ == "__main__":
    unittest.main()
