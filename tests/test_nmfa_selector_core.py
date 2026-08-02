from __future__ import annotations

import copy
import hashlib
import unittest
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from indusbench import nmfa_selector_core as selector
from indusbench.io import encode_json, read_json
from indusbench.nmfa_preregistration import (
    NMFAGatePlanSnapshot,
)
from indusbench.nmfa_preregistration import (
    _Component as GateComponent,
)
from indusbench.nmfa_preregistration import (
    _tuple_search as gate_tuple_search,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark/nmfa-selector-core-plan-v1.json"
BUNDLE_PATH = ROOT / "benchmark/nmfa-selector-core-evaluator-bundle-v1.json"
PLAN_SCHEMA_PATH = ROOT / "schemas/nmfa-selector-core-plan.schema.json"
INVENTORY_SCHEMA_PATH = ROOT / "schemas/nmfa-selector-inventory.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas/nmfa-selector-receipt.schema.json"
PARENT_PATH = ROOT / "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
GATE_PLAN_PATH = ROOT / "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"

PARENT_SHA256 = "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"
GATE_PLAN_SHA256 = "dfea30b6cc0635e98d6fc1c0125e428df454bfbb4f22ba464923801db01273af"
NONCE_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
AXES = ("site", "period", "medium", "object_type")


def resource_bytes(relative: str) -> bytes:
    if relative in {"io.py", "nmfa_selector_core.py"}:
        return (ROOT / "src" / "indusbench" / relative).read_bytes()
    return (ROOT / relative).read_bytes()


@contextmanager
def local_resources():
    with patch.object(selector, "_resource_bytes", side_effect=resource_bytes):
        yield


def domain_digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + encode_json(value)).hexdigest()


def opaque(label: str) -> str:
    return "hmac-sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()


def registry_id(label: str) -> str:
    return "registry-id:" + hashlib.sha256(label.encode("ascii")).hexdigest()


def f_id_for(index: int) -> str:
    return "hmac-sha256:" + f"{index:064x}"


def g_id(member_f_ids: list[str]) -> str:
    return domain_digest(
        b"indusbench:nmfa:executor-g:v1\x00",
        {"member_f_ids": member_f_ids},
    )


def context_for(index: int, *, unique_nuisance: bool = False) -> dict[str, Any]:
    pair = index // 2
    if index < 20:
        labels = (
            "selected-site",
            f"period-{pair:03d}",
            f"medium-{pair:03d}",
            f"object-{pair:03d}",
        )
    elif index < 40:
        labels = (
            f"site-{pair:03d}",
            "selected-period",
            f"medium-{pair:03d}",
            f"object-{pair:03d}",
        )
    elif index < 60:
        labels = (
            f"site-{pair:03d}",
            f"period-{pair:03d}",
            "selected-medium",
            f"object-{pair:03d}",
        )
    elif index < 80:
        labels = (
            f"site-{pair:03d}",
            f"period-{pair:03d}",
            f"medium-{pair:03d}",
            "selected-object",
        )
    else:
        labels = (
            f"site-{pair:03d}",
            f"period-{pair:03d}",
            f"medium-{pair:03d}",
            f"object-{pair:03d}",
        )
    values = tuple(opaque(label) for label in labels)
    nuisance_label = f"nuisance-{index:03d}" if unique_nuisance else f"nuisance-{pair:03d}"
    return {axis: value for axis, value in zip(AXES, values, strict=True)} | {
        "nuisance": [opaque(nuisance_label)]
    }


def closure_tables(components: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for axis in AXES:
        values = sorted(
            {row["context"][axis] for component in components for row in component["members"]}
        )
        tables[axis] = [{"group_id": value, "member_value_ids": [value]} for value in values]
    return tables


def inventory(*, count: int = 160, unique_nuisance: bool = False) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    for index in range(count):
        f_id = f_id_for(index)
        components.append(
            {
                "complete_c": True,
                "m_g_member_ids": [f_id],
                "members": [
                    {
                        "context": context_for(index, unique_nuisance=unique_nuisance),
                        "e_eligible": True,
                        "f_id": f_id,
                        "split_eligible": True,
                    }
                ],
                "split_eligible_g": True,
            }
        )
    nuisance_values = sorted(
        {row["context"]["nuisance"][0] for component in components for row in component["members"]}
    )
    return {
        "claim_binding": {
            "claim_family_id": registry_id("synthetic-claim-family"),
            "claim_slot_id": registry_id("synthetic-claim-slot"),
            "experiment_instance_id": registry_id("synthetic-experiment"),
            "predecessor_chain_head_sha256": "sha256:" + "9" * 64,
        },
        "eligible_split_inventory": {
            "axis_order": list(AXES),
            "closure_tables": closure_tables(components),
            "components": components,
            "nuisance_semantics": {
                "nuisance_field_ids": [opaque("nuisance-field")],
                "nuisance_vocabularies": [
                    {
                        "canonical_value_ids": nuisance_values,
                        "field_id": opaque("nuisance-field"),
                    }
                ],
                "provenance_policy": "complete_canonical_nuisance_tuple",
            },
        },
        "format_version": "1.0.0",
        "gate_plan_sha256": "sha256:" + GATE_PLAN_SHA256,
        "parent_protocol_sha256": "sha256:" + PARENT_SHA256,
        "record_kind": "nmfa_selector_inventory",
        "selector_plan_sha256": "sha256:" + hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),
    }


def raw_and_expected(value: dict[str, Any]) -> tuple[bytes, str]:
    eligible_digest = domain_digest(
        b"indusbench:nmfa:eligible-split-inventory:v1\x00",
        value["eligible_split_inventory"],
    )
    return encode_json(value), eligible_digest


def validate(value: dict[str, Any]):
    raw, eligible_digest = raw_and_expected(value)
    with local_resources():
        return selector.validate_nmfa_selector_inventory(raw, eligible_digest)


def evaluate(value: dict[str, Any]):
    raw, eligible_digest = raw_and_expected(value)
    with local_resources():
        return selector.evaluate_nmfa_selector_inventory(raw, eligible_digest)


class NMFASelectorCoreTests(unittest.TestCase):
    maxDiff = None

    def test_plan_and_all_schemas_are_valid_canonical_draft_2020_12(self) -> None:
        plan = read_json(PLAN_PATH)
        plan_schema = read_json(PLAN_SCHEMA_PATH)
        Draft202012Validator.check_schema(plan_schema)
        self.assertEqual(
            [],
            list(
                Draft202012Validator(plan_schema, format_checker=FormatChecker()).iter_errors(plan)
            ),
        )
        for path in (INVENTORY_SCHEMA_PATH, RECEIPT_SCHEMA_PATH):
            schema = read_json(path)
            Draft202012Validator.check_schema(schema)
            self.assertEqual(encode_json(schema), path.read_bytes())
        self.assertEqual(encode_json(plan), PLAN_PATH.read_bytes())

    def test_plan_schema_rejects_every_nested_semantic_mutation(self) -> None:
        plan = read_json(PLAN_PATH)
        schema = read_json(PLAN_SCHEMA_PATH)
        mutations = []
        extra_algorithm = copy.deepcopy(plan)
        extra_algorithm["algorithms"]["split_enumeration"]["unbound"] = True
        mutations.append(extra_algorithm)
        empty_decision = copy.deepcopy(plan)
        empty_decision["decision"] = {}
        mutations.append(empty_decision)
        changed_limit = copy.deepcopy(plan)
        changed_limit["limits"]["max_units"] += 1
        mutations.append(changed_limit)
        changed_assurance = copy.deepcopy(plan)
        changed_assurance["assurance_boundary"] = {"replacement": False}
        mutations.append(changed_assurance)
        erased_blocker = copy.deepcopy(plan)
        erased_blocker["compiled_blockers"].pop()
        mutations.append(erased_blocker)
        for mutated in mutations:
            with self.subTest(mutation=hashlib.sha256(encode_json(mutated)).hexdigest()[:8]):
                self.assertIsNotNone(next(Draft202012Validator(schema).iter_errors(mutated), None))

    def test_evaluator_bundle_closes_every_runtime_resource(self) -> None:
        bundle = read_json(BUNDLE_PATH)
        self.assertEqual(encode_json(bundle), BUNDLE_PATH.read_bytes())
        self.assertEqual("nmfa-selector-core-evaluator-bundle-v1", bundle["bundle_id"])
        self.assertEqual("2026-08-02T15:50:25Z", bundle["created_at"])
        self.assertEqual(selector._EXPECTED_RUNTIME_PROFILE, bundle["runtime_profile"])
        self.assertEqual(selector._EXPECTED_SECURITY_BOUNDARY, bundle["security_boundary"])
        self.assertTrue(all(value is False for value in bundle["security_boundary"].values()))
        expected_paths = {
            "benchmark/nmfa-selector-core-plan-v1.json",
            "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json",
            "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json",
            "benchmark/numeral-metrology-functional-anchor-protocol-v1.json",
            "schemas/nmfa-selector-core-plan.schema.json",
            "schemas/nmfa-selector-inventory.schema.json",
            "schemas/nmfa-selector-receipt.schema.json",
            "src/indusbench/io.py",
            "src/indusbench/nmfa_selector_core.py",
        }
        self.assertEqual(expected_paths, {row["path"] for row in bundle["files"]})
        for row in bundle["files"]:
            raw = (ROOT / row["path"]).read_bytes()
            self.assertEqual(row["bytes"], len(raw))
            self.assertEqual(row["sha256"], "sha256:" + hashlib.sha256(raw).hexdigest())
            self.assertEqual("runtime_and_ci", row["verification"])

    def test_bundle_rejects_unknown_path_before_any_member_read(self) -> None:
        bundle = read_json(BUNDLE_PATH)
        bundle["files"][0]["path"] = "../outside"
        tampered = encode_json(bundle)
        calls: list[str] = []

        def guarded_resource(path: str) -> bytes:
            calls.append(path)
            if path == selector._BUNDLE_PATH:
                return tampered
            raise AssertionError("bundle validator read a path before allowlist validation")

        with (
            patch.object(selector, "_resource_bytes", side_effect=guarded_resource),
            self.assertRaisesRegex(
                selector.NMFASelectorError,
                "^PACKAGE_RESOURCE_INVALID$",
            ),
        ):
            selector._validate_installed_bundle()
        self.assertEqual([selector._BUNDLE_PATH], calls)

    def test_module_resource_locks_match_exact_plan_and_schemas(self) -> None:
        expected = {
            selector._PLAN_PATH: (selector._PLAN_SIZE, selector._PLAN_SHA256),
            selector._PLAN_SCHEMA_PATH: (
                selector._PLAN_SCHEMA_SIZE,
                selector._PLAN_SCHEMA_SHA256,
            ),
            selector._INVENTORY_SCHEMA_PATH: (
                selector._INVENTORY_SCHEMA_SIZE,
                selector._INVENTORY_SCHEMA_SHA256,
            ),
            selector._RECEIPT_SCHEMA_PATH: (
                selector._RECEIPT_SCHEMA_SIZE,
                selector._RECEIPT_SCHEMA_SHA256,
            ),
        }
        self.assertEqual(expected, selector._RESOURCE_LOCKS)
        for relative, (size, digest) in expected.items():
            raw = (ROOT / relative).read_bytes()
            self.assertEqual(size, len(raw))
            self.assertEqual(digest, hashlib.sha256(raw).hexdigest())

    def test_plan_is_explicitly_not_complete_E_or_authority(self) -> None:
        plan = read_json(PLAN_PATH)
        self.assertEqual("development_component_not_complete_E", plan["scope"]["status"])
        self.assertTrue(all(value is False for value in plan["assurance_boundary"].values()))
        self.assertIn("COMPLETE_EXECUTION_BUNDLE_UNBOUND", plan["compiled_blockers"])
        self.assertIn("NONCE_EVENT_TRUST_UNBOUND", plan["compiled_blockers"])
        self.assertIn("Y_parser_unit_conversion_and_values", plan["scope"]["omitted"])

    def test_installed_plan_loader_rechecks_predecessors(self) -> None:
        with local_resources():
            loaded = selector.load_installed_nmfa_selector_plan()
        self.assertEqual("nmfa-selector-core-plan-v1", loaded["plan_id"])
        self.assertEqual("sha256:" + PARENT_SHA256, loaded["bindings"]["parent_protocol_sha256"])
        self.assertEqual("sha256:" + GATE_PLAN_SHA256, loaded["bindings"]["gate_plan_sha256"])
        self.assertEqual(PARENT_SHA256, hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest())
        self.assertEqual(GATE_PLAN_SHA256, hashlib.sha256(GATE_PLAN_PATH.read_bytes()).hexdigest())

    def test_frozen_component_nonce_primary_and_ticket_vectors(self) -> None:
        plan = read_json(PLAN_PATH)
        component = plan["fixed_vectors"]["component_identity"]
        self.assertEqual(component["expected_g_id"], g_id(component["member_f_ids"]))

        nonce = selector.normalize_nmfa_split_nonce(NONCE_HEX)
        self.assertEqual(bytes(range(32)), nonce)

        primary = plan["fixed_vectors"]["primary_f_rank"]
        primary_rank = hashlib.sha256(
            b"indusbench:nmfa:preregistration-primary-f:v1\x00"
            + primary["gate_plan_sha256"].encode("ascii")
            + b"\x00"
            + primary["candidate_f_id"].encode("ascii")
        ).digest()
        self.assertEqual(primary["expected_rank_sha256"], "sha256:" + primary_rank.hex())

        ticket = plan["fixed_vectors"]["split_ticket"]
        actual_ticket = selector._ticket(
            bytes.fromhex(ticket["nonce_hex"]),
            ticket["eligible_split_inventory_sha256"],
            tuple(ticket["canonical_tuple"]),
        )
        self.assertEqual(ticket["expected_ticket_sha256"], "sha256:" + actual_ticket.hex())

    def test_nonce_rejects_alternate_representations_with_fixed_error(self) -> None:
        invalid = (
            NONCE_HEX.upper(),
            "0x" + NONCE_HEX,
            NONCE_HEX + "\n",
            NONCE_HEX[:-2],
            b"\x00" * 32,
        )
        for value in invalid:
            with (
                self.subTest(value=type(value).__name__),
                self.assertRaisesRegex(selector.NMFASelectorError, "^NONCE_CONTRACT_INVALID$"),
            ):
                selector.normalize_nmfa_split_nonce(value)  # type: ignore[arg-type]

    def test_closed_inventory_validation_and_protected_repr(self) -> None:
        value = inventory()
        validated = validate(value)
        self.assertEqual("<ValidatedNMFASelectorInventory protected>", repr(validated))
        expected = domain_digest(b"indusbench:nmfa:selector-inventory:v1\x00", value)
        self.assertEqual(expected, validated.selector_inventory_sha256)
        self.assertEqual(raw_and_expected(value)[1], validated.eligible_split_inventory_sha256)
        self.assertEqual(encode_json(value), validated.canonical_bytes)

    def test_inventory_rejects_noncanonical_float_extra_and_identity_errors(self) -> None:
        base = inventory()
        _, base_expected = raw_and_expected(base)
        cases: list[tuple[bytes, str]] = [(encode_json(base).rstrip(b"\n"), base_expected)]
        floating = copy.deepcopy(base)
        floating["eligible_split_inventory"]["components"][0]["members"][0]["context"][
            "nuisance"
        ] = [1.0]
        cases.append(raw_and_expected(floating))
        extra = copy.deepcopy(base)
        extra["private_path"] = "sensitive"
        cases.append(raw_and_expected(extra))
        wrong_membership = copy.deepcopy(base)
        wrong_membership["eligible_split_inventory"]["components"][0]["m_g_member_ids"] = []
        cases.append(raw_and_expected(wrong_membership))
        unsorted = copy.deepcopy(base)
        components = unsorted["eligible_split_inventory"]["components"]
        components[0], components[1] = (
            components[1],
            components[0],
        )
        cases.append(raw_and_expected(unsorted))
        for raw, expected_digest in cases:
            with (
                self.subTest(case=hashlib.sha256(raw).hexdigest()[:8]),
                local_resources(),
                self.assertRaisesRegex(
                    selector.NMFASelectorError,
                    "^INVENTORY_CONTRACT_INVALID$",
                ) as caught,
            ):
                selector.validate_nmfa_selector_inventory(raw, expected_digest)
            self.assertEqual(
                selector.NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID,
                caught.exception.code,
            )
            self.assertNotIn("sensitive", str(caught.exception))

    def test_external_digest_is_required_again_and_public_handle_is_not_consumed(self) -> None:
        value = inventory()
        raw, expected = raw_and_expected(value)
        validated = validate(value)
        forged = selector.ValidatedNMFASelectorInventory(
            canonical_bytes=validated.canonical_bytes,
            selector_inventory_sha256="sha256:" + "e" * 64,
            eligible_split_inventory_sha256="sha256:" + "f" * 64,
            selector_bundle_sha256="sha256:" + "d" * 64,
        )
        with local_resources():
            for operation in (
                lambda: selector.validate_nmfa_selector_inventory(raw, "sha256:" + "f" * 64),
                lambda: selector.evaluate_nmfa_selector_inventory(cast(Any, forged), expected),
                lambda: selector.derive_nmfa_selector_assignment(
                    cast(Any, forged),
                    expected,
                    NONCE_HEX,
                ),
            ):
                with self.assertRaisesRegex(
                    selector.NMFASelectorError,
                    "^INVENTORY_CONTRACT_INVALID$",
                ):
                    operation()

    def test_huge_integer_has_a_fixed_contract_error(self) -> None:
        raw = b'{"huge":' + b"9" * 5000 + b"}\n"
        with (
            local_resources(),
            self.assertRaisesRegex(
                selector.NMFASelectorError,
                "^INVENTORY_CONTRACT_INVALID$",
            ),
        ):
            selector.validate_nmfa_selector_inventory(raw, "sha256:" + "0" * 64)

    def test_structural_search_is_exhaustive_and_n2_safe(self) -> None:
        analysis = evaluate(inventory())
        self.assertEqual(
            selector.NMFASelectorOutcome.READY_FOR_DECLARED_NONCE_ANALYSIS,
            analysis.outcome,
        )
        self.assertEqual(1, analysis.tuple_evaluations)
        self.assertEqual(1, analysis.split_eligible_tuple_count)
        self.assertEqual(1, analysis.n2_tuple_evaluations)
        self.assertEqual(80, analysis.n2_primary_assignments)
        self.assertEqual(1, analysis.n2_supported_tuple_count)
        self.assertIsNotNone(analysis.tuple_roster_sha256)
        self.assertEqual("<NMFASelectorAnalysis protected>", repr(analysis))

    def test_insufficient_no_tuple_and_universal_n2_block_are_distinct(self) -> None:
        insufficient_result = evaluate(inventory(count=159))
        unsafe_result = evaluate(inventory(unique_nuisance=True))
        no_tuple_value = inventory()
        no_tuple_components = no_tuple_value["eligible_split_inventory"]["components"]
        no_tuple_components[79]["members"][0]["context"]["object_type"] = opaque("other-object")
        no_tuple_value["eligible_split_inventory"]["closure_tables"] = closure_tables(
            no_tuple_components
        )
        no_tuple_result = evaluate(no_tuple_value)
        self.assertEqual(
            selector.NMFASelectorOutcome.INSUFFICIENT_ELIGIBLE_G,
            insufficient_result.outcome,
        )
        self.assertEqual(
            selector.NMFASelectorOutcome.N2_UNIVERSAL_SUPPORT_BLOCKED,
            unsafe_result.outcome,
        )
        self.assertEqual(1, unsafe_result.split_eligible_tuple_count)
        self.assertEqual(0, unsafe_result.n2_supported_tuple_count)
        self.assertEqual(
            selector.NMFASelectorOutcome.NO_FEASIBLE_DOMAIN_TUPLE,
            no_tuple_result.outcome,
        )

    def test_declared_assignment_is_exact_private_and_independently_reexecuted(self) -> None:
        value = inventory()
        raw, expected = raw_and_expected(value)
        with local_resources():
            result = selector.derive_nmfa_selector_assignment(raw, expected, NONCE_HEX)
            receipt = result.receipt()
        self.assertEqual("<ProtectedNMFASelectorAssignment protected>", repr(result))
        self.assertEqual("DECLARED_SELECTOR_ASSIGNMENT_ONLY", receipt["terminal_state"])
        self.assertEqual(
            [
                opaque("selected-site"),
                opaque("selected-period"),
                opaque("selected-medium"),
                opaque("selected-object"),
            ],
            receipt["selected_tuple"],
        )
        self.assertEqual(80, receipt["n2_movable_g"])
        self.assertEqual(160, len(receipt["assignments"]))
        partitions = Counter(row["partition"] for row in receipt["assignments"])
        self.assertEqual(
            {"development": 54, "holdout": 80, "validation": 26},
            dict(partitions),
        )
        complement_g_ids = sorted(
            (
                g_id([component["members"][0]["f_id"]])
                for component in value["eligible_split_inventory"]["components"][80:]
            ),
            key=lambda item: (bytes.fromhex(item[7:]), item),
        )
        expected_complement = {
            component_g: ("development", "development", "validation")[index % 3]
            for index, component_g in enumerate(complement_g_ids)
        }
        observed_complement = {
            row["g_id"]: row["partition"]
            for row in receipt["assignments"]
            if row["partition"] != "holdout"
        }
        self.assertEqual(expected_complement, observed_complement)
        self.assertEqual(
            sorted(
                (row["g_id"] for row in receipt["assignments"]),
                key=lambda item: (bytes.fromhex(item[7:]), item),
            ),
            [row["g_id"] for row in receipt["assignments"]],
        )
        self.assertEqual(80, sum(row["cell"] is not None for row in receipt["assignments"]))
        self.assertTrue(all(value is False for value in receipt["assurance_boundary"].values()))
        self.assertIn("CLAIM_BINDING_ORIGIN_UNBOUND", receipt["compiled_blockers"])
        self.assertIn(
            "EXTERNAL_ELIGIBLE_INVENTORY_DIGEST_ORIGIN_UNBOUND",
            receipt["compiled_blockers"],
        )
        self.assertNotIn(NONCE_HEX.encode("ascii"), result.receipt_bytes)
        self.assertEqual(
            result.receipt_sha256,
            domain_digest(b"indusbench:nmfa:selector-assignment:v1\x00", receipt),
        )
        schema = read_json(RECEIPT_SCHEMA_PATH)
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(receipt)))
        with local_resources():
            verified = selector.verify_nmfa_selector_assignment(
                raw,
                expected,
                NONCE_HEX,
                result.receipt_bytes,
            )
        self.assertEqual(result, verified)
        with (
            local_resources(),
            self.assertRaisesRegex(
                selector.NMFASelectorError,
                "^ASSIGNMENT_CONTRACT_INVALID$",
            ),
        ):
            selector.verify_nmfa_selector_assignment(
                raw,
                expected,
                NONCE_HEX,
                result.receipt_bytes[:-1] + b" ",
            )
        forged = selector.ProtectedNMFASelectorAssignment(
            receipt_bytes=result.receipt_bytes,
            receipt_sha256="sha256:" + "f" * 64,
        )
        with (
            local_resources(),
            self.assertRaisesRegex(
                selector.NMFASelectorError,
                "^ASSIGNMENT_CONTRACT_INVALID$",
            ),
        ):
            forged.receipt()

    def test_selection_refuses_nonready_inventory(self) -> None:
        raw, expected = raw_and_expected(inventory(unique_nuisance=True))
        with (
            local_resources(),
            self.assertRaisesRegex(selector.NMFASelectorError, "^SELECTOR_NOT_READY$"),
        ):
            selector.derive_nmfa_selector_assignment(raw, expected, NONCE_HEX)

    def test_multiple_tuple_ticket_minimum_is_nonce_bound_and_not_deduplicated(self) -> None:
        value = inventory(count=164)
        payload = value["eligible_split_inventory"]
        parent = opaque("site-parent")
        payload["closure_tables"]["site"].append(
            {
                "group_id": parent,
                "member_value_ids": sorted([parent, opaque("selected-site"), opaque("site-040")]),
            }
        )
        payload["closure_tables"]["site"].sort(key=lambda row: row["group_id"])
        analysis = evaluate(value)
        self.assertEqual(2, analysis.split_eligible_tuple_count)
        self.assertEqual(2, analysis.n2_supported_tuple_count)

        raw, expected = raw_and_expected(value)
        with local_resources():
            result = selector.derive_nmfa_selector_assignment(raw, expected, NONCE_HEX)
            receipt = result.receipt()
        suffix = (
            opaque("selected-period"),
            opaque("selected-medium"),
            opaque("selected-object"),
        )
        candidates = [
            (opaque("selected-site"), *suffix),
            (parent, *suffix),
        ]
        nonce = bytes.fromhex(NONCE_HEX)

        def independent_ticket(candidate: tuple[str, ...]) -> tuple[bytes, bytes]:
            canonical_tuple = encode_json(list(candidate))
            return (
                hashlib.sha256(
                    nonce + b"\x00" + expected.encode("ascii") + b"\x00" + canonical_tuple
                ).digest(),
                canonical_tuple,
            )

        self.assertEqual(list(min(candidates, key=independent_ticket)), receipt["selected_tuple"])

    def test_multi_member_component_binds_full_roster_but_uses_only_split_members(self) -> None:
        value = inventory()
        components = value["eligible_split_inventory"]["components"]
        target = components[0]
        original_member = target["members"][0]
        original_singleton_g = g_id([original_member["f_id"]])
        ineligible_member = {
            "context": copy.deepcopy(original_member["context"]),
            "e_eligible": False,
            "f_id": opaque("ineligible-component-member"),
            "split_eligible": False,
        }
        target["members"].append(ineligible_member)
        target["members"].sort(key=lambda row: row["f_id"])
        components.sort(key=lambda row: tuple(member["f_id"] for member in row["members"]))
        raw, expected = raw_and_expected(value)
        with local_resources():
            result = selector.derive_nmfa_selector_assignment(raw, expected, NONCE_HEX)
            receipt = result.receipt()
        expected_g = g_id(sorted([original_member["f_id"], ineligible_member["f_id"]]))
        assignment = next(row for row in receipt["assignments"] if row["g_id"] == expected_g)
        self.assertNotEqual(original_singleton_g, expected_g)
        self.assertEqual(original_member["f_id"], assignment["primary_f_id"])

    def test_each_computation_limit_has_exact_fail_closed_counters(self) -> None:
        raw, expected = raw_and_expected(inventory())
        cases = (
            ("_MAX_TUPLE_EVALUATIONS", 0, (0, 0, 0)),
            ("_MAX_N2_TUPLE_EVALUATIONS", 0, (1, 0, 0)),
            ("_MAX_N2_PRIMARY_ASSIGNMENTS", 79, (1, 0, 0)),
            ("_MAX_PRIMARY_CACHE_ENTRIES", 79, (1, 1, 80)),
        )
        for name, limit, expected_counters in cases:
            with (
                self.subTest(limit=name),
                patch.object(selector, name, limit),
                local_resources(),
            ):
                analysis = selector.evaluate_nmfa_selector_inventory(raw, expected)
            self.assertEqual(
                selector.NMFASelectorOutcome.COMPUTATION_LIMIT_BLOCKED,
                analysis.outcome,
            )
            self.assertEqual(
                expected_counters,
                (
                    analysis.tuple_evaluations,
                    analysis.n2_tuple_evaluations,
                    analysis.n2_primary_assignments,
                ),
            )
            self.assertEqual(0, analysis.split_eligible_tuple_count)
            self.assertIsNone(analysis.tuple_roster_sha256)

    def test_analysis_rejects_bundle_change_between_validation_and_return(self) -> None:
        raw, expected = raw_and_expected(inventory())
        installed_validator = selector._validate_installed_bundle
        calls = 0

        def changing_bundle() -> tuple[str, str]:
            nonlocal calls
            calls += 1
            digest, created_at = installed_validator()
            if calls >= 3:
                return "sha256:" + "f" * 64, created_at
            return digest, created_at

        with (
            local_resources(),
            patch.object(selector, "_validate_installed_bundle", side_effect=changing_bundle),
            self.assertRaisesRegex(
                selector.NMFASelectorError,
                "^PACKAGE_RESOURCE_INVALID$",
            ),
        ):
            selector.evaluate_nmfa_selector_inventory(raw, expected)
        self.assertEqual(3, calls)

    def test_structural_result_matches_immutable_gate_oracle(self) -> None:
        value = inventory()
        actual = evaluate(value)

        units_by_id: dict[str, dict[str, Any]] = {}
        gate_components: list[GateComponent] = []
        for raw_component in value["eligible_split_inventory"]["components"]:
            raw_members = raw_component["members"]
            member_ids = tuple(row["f_id"] for row in raw_members)
            for row in raw_members:
                units_by_id[row["f_id"]] = {"context": row["context"]}
            contexts = {
                axis: frozenset(row["context"][axis] for row in raw_members) for axis in AXES
            }
            triggers = {
                axis: frozenset(
                    row["context"][axis] for row in raw_members if row["split_eligible"]
                )
                for axis in AXES
            }
            m_g_members = tuple(row["f_id"] for row in raw_members if row["e_eligible"])
            eligible = tuple(row["f_id"] for row in raw_members if row["split_eligible"])
            gate_components.append(
                GateComponent(
                    member_ids=member_ids,
                    m_g_member_ids=m_g_members,
                    eligible_member_ids=eligible,
                    contexts=contexts,
                    trigger_contexts=triggers,
                    complete=raw_component["complete_c"],
                )
            )
        closures = {
            axis: {group["group_id"]: frozenset(group["member_value_ids"]) for group in groups}
            for axis, groups in value["eligible_split_inventory"]["closure_tables"].items()
        }
        snapshot = NMFAGatePlanSnapshot(
            gate_id="synthetic",
            gate_plan_sha256="sha256:" + GATE_PLAN_SHA256,
            parent_protocol_sha256="sha256:" + PARENT_SHA256,
            eligible_g_minimum=160,
            cell_minimum_g=20,
            holdout_minimum_g=80,
            complement_minimum_g=80,
            n2_minimum_movable_g=64,
            n2_minimum_movable_percent=80,
            max_tuple_evaluations=200000,
            max_n2_tuple_evaluations=10000,
            max_n2_primary_assignments=2000000,
            max_primary_cache_entries=200000,
            evaluator_bundle_sha256="sha256:" + "0" * 64,
        )
        expected = gate_tuple_search(
            tuple(gate_components),
            units_by_id,
            closures,
            "sha256:" + GATE_PLAN_SHA256,
            snapshot,
        )
        self.assertEqual("EXHAUSTED_SPLIT_ROSTER_N2_SAFE", expected.outcome)
        self.assertEqual(expected.split_eligible_tuple_count, actual.split_eligible_tuple_count)
        self.assertEqual(expected.n2_supported_tuple_count, actual.n2_supported_tuple_count)
        self.assertEqual(expected.split_eligible_tuple_roster_sha256, actual.tuple_roster_sha256)
        self.assertEqual(expected.tuple_evaluations, actual.tuple_evaluations)
        self.assertEqual(expected.n2_tuple_evaluations, actual.n2_tuple_evaluations)
        self.assertEqual(expected.n2_primary_assignments, actual.n2_primary_assignments)


if __name__ == "__main__":
    unittest.main()
