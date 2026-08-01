from __future__ import annotations

import copy
import hashlib
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

import indusbench.source_reported_link_static as static_module
from indusbench.io import decode_json, encode_json
from indusbench.source_reported_link_resource import (
    RawArtifactRole,
    SourceLinkResourceError,
    SourceLinkResourceErrorCode,
    preflight_canonical_resource,
)

ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = (
    ROOT / "registry" / "source-reported-link-protected-ephemeral-custody-contract-v2.json"
)
WRAPPER_SCHEMA_PATH = (
    ROOT / "schemas" / "source-reported-link-protected-ephemeral-custody-contract-v2.schema.json"
)

EXPECTED_V2_RESOURCES = {
    "registry/source-reported-link-protected-ephemeral-custody-contract-v2.json": (
        16981,
        "a064331361057947e8b4079dcc114e3d7918459a538107039199f7074bc4c86c",
    ),
    "schemas/source-reported-link-protected-ephemeral-custody-contract-v2.schema.json": (
        17694,
        "1523534dabf734c2381d454f4c7a387f271fd4088f81c3d15a4d0e4915fed671",
    ),
}

EXPECTED_INCORPORATED_ARTIFACTS = {
    "custody_contract_v1": (
        "registry/source-reported-link-protected-ephemeral-custody-contract-v1.json",
        426824,
        "917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914",
    ),
    "custody_contract_v1_const_schema": (
        "schemas/source-reported-link-protected-ephemeral-custody-contract.schema.json",
        440116,
        "5c4b88acb41676b49139242944f28cc3da1202b1e1193edb6e35481aeabaae3b",
    ),
    "source_contract_v1": (
        "registry/source-reported-link-source-contract-v1.json",
        29059,
        "e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f",
    ),
    "source_contract_v1_const_schema": (
        "schemas/source-reported-link-source-contract.schema.json",
        30752,
        "e73a90c12b25c40d134f5ac58d1fceb793f2cd14168e77c7035eef9dd41c3e78",
    ),
    "source_registry_legacy_raw": (
        "registry/sources.json",
        43235,
        "e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584",
    ),
    "source_registry_schema_legacy_raw": (
        "schemas/source-registry.schema.json",
        8295,
        "6272a824cd09fb7a3b50225006ffedd4191c707545ad3f98c7d971438906beb3",
    ),
}

EXPECTED_LEGACY_PROJECTIONS = (
    (
        "registry/sources.json",
        43235,
        "e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584",
        43239,
        "da9254e6a8cd4d6cbe7a465119bd1a1be7b6583586b8b1cb0cb8af02e9f83b1b",
    ),
    (
        "schemas/source-registry.schema.json",
        8295,
        "6272a824cd09fb7a3b50225006ffedd4191c707545ad3f98c7d971438906beb3",
        8295,
        "b118345e10446f92446114b3a1773bb0927a6b808e253268088d953776218073",
    ),
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _walk(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for child in value.values():
            values.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk(child))
    return values


def _resolve_json_pointer(value: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise AssertionError("absolute JSON Pointer required")
    current = value
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


class SourceReportedLinkCustodyV2WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wrapper_raw = WRAPPER_PATH.read_bytes()
        cls.schema_raw = WRAPPER_SCHEMA_PATH.read_bytes()
        cls.wrapper = decode_json(cls.wrapper_raw)
        cls.schema = decode_json(cls.schema_raw)
        cls.validator = Draft202012Validator(cls.schema)

    def test_exact_v2_wrapper_and_const_schema_are_canonical_and_frozen(self) -> None:
        observed = {}
        for relative_path in EXPECTED_V2_RESOURCES:
            raw = (ROOT / relative_path).read_bytes()
            observed[relative_path] = (len(raw), _sha256(raw))
            self.assertEqual(raw, encode_json(decode_json(raw)))
        self.assertEqual(EXPECTED_V2_RESOURCES, observed)

        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            self.schema["$schema"],
        )
        self.assertEqual(
            "source-reported-link-protected-ephemeral-custody-contract-v2.schema.json",
            self.schema["$id"],
        )
        self.assertEqual({"$id", "$schema", "const"}, set(self.schema))
        self.assertEqual(self.wrapper, self.schema["const"])
        Draft202012Validator.check_schema(self.schema)
        self.validator.validate(self.wrapper)
        schema_keys = {
            key for value in _walk(self.schema) if isinstance(value, dict) for key in value
        }
        self.assertNotIn("$ref", schema_keys)

    def test_canonical_profile_remains_exact_v1_and_compatibility_id_is_separate(self) -> None:
        source_contract = decode_json(
            (ROOT / "registry" / "source-reported-link-source-contract-v1.json").read_bytes()
        )
        custody_contract = decode_json(
            (
                ROOT
                / "registry"
                / "source-reported-link-protected-ephemeral-custody-contract-v1.json"
            ).read_bytes()
        )
        self.assertEqual(
            source_contract["canonical_json_profile"],
            custody_contract["canonical_json_profile"],
        )
        self.assertEqual(
            custody_contract["canonical_json_profile"],
            self.wrapper["canonical_json_profile"],
        )
        self.assertEqual(
            "hard_reject",
            self.wrapper["canonical_json_profile"]["noncanonical_raw_bytes_disposition"],
        )
        self.assertEqual(
            "source-reported-link-exact-two-static-byte-compatibility-v2",
            self.wrapper["resolver_successor"]["compatibility_profile_id"],
        )
        self.assertNotEqual(
            self.wrapper["canonical_json_profile"]["profile_id"],
            self.wrapper["resolver_successor"]["compatibility_profile_id"],
        )

    def test_v1_resolver_order_is_preserved_with_one_exact_canonical_check_splice(
        self,
    ) -> None:
        custody_contract = decode_json(
            (
                ROOT
                / "registry"
                / "source-reported-link-protected-ephemeral-custody-contract-v1.json"
            ).read_bytes()
        )
        base_order = custody_contract["cross_artifact_verifier_contract"][
            "static_file_binding_resolver"
        ]["resolver_exact_order"]
        splice = self.wrapper["resolver_successor"]["canonical_byte_check_splice"]
        self.assertEqual(base_order, splice["v1_resolver_exact_order_incorporated"])
        self.assertEqual(
            splice["base_token_occurrence_count_exact"],
            base_order.count(splice["base_token_exact"]),
        )
        self.assertEqual(
            splice["composed_resolver_exact_order_after_activation"],
            base_order.replace(splice["base_token_exact"], splice["replacement_token_exact"]),
        )
        composed = splice["composed_resolver_exact_order_after_activation"]
        for required_fragment in (
            "require_signed_expected_digest",
            "separately_open_hash_and_bound_the_runtime_distribution",
            "distinct_validated_immutable_manifest_and_distribution_handles",
            "already_loaded_exact_contract_bytes_and_never_embedded_inside_it",
        ):
            self.assertIn(required_fragment, composed)
        composed_rules = self.wrapper["historical_parent_incorporation"][
            "composed_parent_rules_exact"
        ]
        self.assertEqual(1, len(composed_rules))
        self.assertEqual(
            "/cross_artifact_verifier_contract/static_file_binding_resolver/resolver_exact_order",
            composed_rules[0]["base_json_pointer"],
        )

    def test_all_raw_sha256_incorporated_v1_parents_are_exact(self) -> None:
        incorporated = self.wrapper["historical_parent_incorporation"]["incorporated_artifacts"]
        self.assertEqual(set(EXPECTED_INCORPORATED_ARTIFACTS), set(incorporated))
        for key, (
            relative_path,
            expected_size,
            expected_sha256,
        ) in EXPECTED_INCORPORATED_ARTIFACTS.items():
            raw = (ROOT / relative_path).read_bytes()
            self.assertEqual(relative_path, incorporated[key]["path"])
            self.assertEqual(expected_size, incorporated[key]["size"])
            self.assertEqual(f"sha256:{expected_sha256}", incorporated[key]["sha256"])
            self.assertEqual(expected_size, len(raw))
            self.assertEqual(expected_sha256, _sha256(raw))

    def test_exact_two_legacy_raw_identities_and_canonical_canaries_are_closed(self) -> None:
        successor = self.wrapper["resolver_successor"]
        exceptions = successor["legacy_noncanonical_static_resources_exact"]
        self.assertEqual(2, successor["exact_legacy_noncanonical_static_resource_count"])
        self.assertEqual(2, len(exceptions))
        self.assertEqual([0, 1], [entry["exception_index"] for entry in exceptions])

        observed = []
        for entry in exceptions:
            raw = (ROOT / entry["path"]).read_bytes()
            canonical = encode_json(decode_json(raw))
            self.assertNotEqual(raw, canonical)
            self.assertIs(entry["normalized_bytes_are_identity"], False)
            self.assertIs(entry["normalized_bytes_may_be_persisted"], False)
            observed.append(
                (
                    entry["path"],
                    len(raw),
                    _sha256(raw),
                    len(canonical),
                    _sha256(canonical),
                )
            )
        self.assertEqual(EXPECTED_LEGACY_PROJECTIONS, tuple(observed))

    def test_exact_sixteen_order_and_distinct_validation_modes_are_closed(self) -> None:
        successor = self.wrapper["resolver_successor"]
        selected = successor["selected_static_resources_after_implementation_exact"]
        expected_exact_fourteen = [spec.package_path for spec in static_module._RESOURCE_SPECS]
        self.assertEqual(
            [
                *expected_exact_fourteen,
                "registry/source-reported-link-protected-ephemeral-custody-contract-v2.json",
                "schemas/source-reported-link-protected-ephemeral-custody-contract-v2.schema.json",
            ],
            selected,
        )
        self.assertEqual(successor["selected_static_resource_count_after_implementation"], 16)
        self.assertEqual(16, len(selected))

        exceptions = successor["legacy_noncanonical_static_resources_exact"]
        self.assertEqual(
            ("instance_against_exact_schema", "draft202012_check_schema"),
            tuple(entry["validation_mode"] for entry in exceptions),
        )
        for entry in exceptions:
            self.assertEqual(entry["path"], selected[entry["resource_index"]])
            self.assertEqual(
                entry["validation_schema_path"],
                selected[entry["validation_schema_resource_index"]],
            )

        source_registry = decode_json((ROOT / "registry" / "sources.json").read_bytes())
        source_registry_schema = decode_json(
            (ROOT / "schemas" / "source-registry.schema.json").read_bytes()
        )
        Draft202012Validator.check_schema(source_registry_schema)
        Draft202012Validator(source_registry_schema).validate(source_registry)

    def test_exact_two_binding_sources_resolve_to_the_frozen_raw_identities(self) -> None:
        loaded_artifacts: dict[str, Any] = {}
        exceptions = self.wrapper["resolver_successor"][
            "legacy_noncanonical_static_resources_exact"
        ]
        for entry in exceptions:
            for binding in entry["binding_sources"]:
                relative_path, pointer = binding.split("#", 1)
                artifact = loaded_artifacts.setdefault(
                    relative_path,
                    decode_json((ROOT / relative_path).read_bytes()),
                )
                resolved = _resolve_json_pointer(artifact, pointer)
                if isinstance(resolved, dict):
                    self.assertEqual(entry["raw_sha256"], resolved["sha256"])
                    if "size" in resolved:
                        self.assertEqual(entry["raw_size"], resolved["size"])
                    if "path" in resolved:
                        self.assertEqual(entry["path"], resolved["path"])
                else:
                    self.assertEqual(entry["raw_sha256"], resolved)

    def test_all_parent_composition_and_supersession_pointers_resolve_exactly(self) -> None:
        incorporation = self.wrapper["historical_parent_incorporation"]
        incorporated_paths = {
            entry["path"] for entry in incorporation["incorporated_artifacts"].values()
        }
        rule_groups = (
            (incorporation["composed_parent_rules_exact"], "base_json_pointer"),
            (incorporation["superseded_parent_rules_exact"], "json_pointer"),
        )
        self.assertEqual((1, 4), tuple(len(rules) for rules, _ in rule_groups))
        for rules, parent_pointer_key in rule_groups:
            for rule in rules:
                self.assertIn(rule["artifact_path"], incorporated_paths)
                parent = decode_json((ROOT / rule["artifact_path"]).read_bytes())
                self.assertEqual(rule["artifact_id"], parent["contract_id"])
                parent_value = _resolve_json_pointer(parent, rule[parent_pointer_key])
                replacement_value = _resolve_json_pointer(
                    self.wrapper,
                    rule["replacement_json_pointer"],
                )
                self.assertIsNotNone(parent_value)
                self.assertIsNotNone(replacement_value)
                if parent_pointer_key == "base_json_pointer":
                    self.assertEqual(
                        parent_value,
                        self.wrapper["resolver_successor"]["canonical_byte_check_splice"][
                            "v1_resolver_exact_order_incorporated"
                        ],
                    )

    def test_exact_eight_crosswalk_and_additive_self_cycle_exclusion_match_v1(self) -> None:
        custody_contract = decode_json(
            (
                ROOT
                / "registry"
                / "source-reported-link-protected-ephemeral-custody-contract-v1.json"
            ).read_bytes()
        )
        required_bindings = custody_contract["future_protocol_prerequisite_blueprints"][
            "authority_proof_bundle"
        ]["signed_authority_payload"]["required_bindings"]
        first_static_binding = required_bindings.index("source_contract_sha256")
        expected_exact_eight = required_bindings[first_static_binding : first_static_binding + 8]
        self.assertEqual(
            expected_exact_eight,
            self.wrapper["future_external_binding"]["existing_exact_eight_field_names_unchanged"],
        )

        v1_self_cycle = custody_contract["cross_artifact_verifier_contract"][
            "static_file_binding_resolver"
        ]["schema_set_self_cycle_exclusion_exact"]
        successor_self_cycle = self.wrapper["future_external_binding"]["self_cycle_exclusion"]
        expected_ids = [
            v1_self_cycle["custody_const_schema_id_forbidden_from_exact_four_schema_set"],
            "source-reported-link-protected-ephemeral-custody-contract-v2.schema.json",
        ]
        expected_paths = [
            v1_self_cycle["custody_const_schema_path_forbidden_from_exact_four_schema_set"],
            "schemas/source-reported-link-protected-ephemeral-custody-contract-v2.schema.json",
        ]
        self.assertEqual(
            expected_ids,
            successor_self_cycle[
                "custody_const_schema_ids_forbidden_from_exact_four_schema_set_exact"
            ],
        )
        self.assertEqual(
            expected_paths,
            successor_self_cycle[
                "custody_const_schema_paths_forbidden_from_exact_four_schema_set_exact"
            ],
        )
        self.assertEqual(
            len(expected_ids),
            successor_self_cycle["custody_const_schema_forbidden_count_exact"],
        )
        exact_four = custody_contract["artifact_schema_commitments"]["schemas"]
        self.assertTrue(set(expected_ids).isdisjoint(entry["id"] for entry in exact_four))
        self.assertTrue(set(expected_paths).isdisjoint(entry["path"] for entry in exact_four))

    def test_v1_canonical_preflight_still_rejects_both_legacy_resources(self) -> None:
        for relative_path, *_ in EXPECTED_LEGACY_PROJECTIONS:
            with self.subTest(relative_path=relative_path):
                with self.assertRaises(SourceLinkResourceError) as caught:
                    preflight_canonical_resource(
                        (ROOT / relative_path).read_bytes(),
                        role=RawArtifactRole.TRANSITIVE_RUNTIME_INPUT_MANIFEST,
                    )
                self.assertIs(
                    SourceLinkResourceErrorCode.CANONICAL_BYTES_MISMATCH,
                    caught.exception.code,
                )

    def test_wrapper_never_activates_authority_runtime_source_access_or_result(self) -> None:
        boundary = self.wrapper["authorization_boundary"]
        self.assertEqual("not_authorized", boundary["status"])
        self.assertEqual("not_executed", boundary["execution_status"])
        for key, value in boundary.items():
            if isinstance(value, bool):
                self.assertIs(value, False, key)

        nonclaims = self.wrapper["nonclaims"]
        self.assertTrue(nonclaims)
        self.assertTrue(all(value is False for value in nonclaims.values()))

        successor = self.wrapper["resolver_successor"]
        self.assertEqual("not_implemented", successor["resolver_implementation_status"])
        self.assertIs(successor["strict_v1_resolver_eligible"], False)
        self.assertIs(successor["successor_static_profile_conformant"], False)
        self.assertIs(
            successor["caller_may_select_path_profile_exception_digest_or_schema"],
            False,
        )
        self.assertIs(
            self.wrapper["future_external_binding"]["adding_only_runtime_bindings_is_sufficient"],
            False,
        )

    def test_const_schema_rejects_scope_identity_order_or_status_mutation(self) -> None:
        mutations: list[tuple[str, Any]] = []

        changed = copy.deepcopy(self.wrapper)
        changed["resolver_successor"]["strict_v1_resolver_eligible"] = True
        mutations.append(("v1 eligibility", changed))

        changed = copy.deepcopy(self.wrapper)
        changed["authorization_boundary"]["source_access_performed"] = True
        mutations.append(("source access", changed))

        changed = copy.deepcopy(self.wrapper)
        changed["resolver_successor"]["legacy_noncanonical_static_resources_exact"].reverse()
        mutations.append(("exception order", changed))

        changed = copy.deepcopy(self.wrapper)
        del changed["resolver_successor"]["legacy_noncanonical_static_resources_exact"][1]
        mutations.append(("missing exception", changed))

        changed = copy.deepcopy(self.wrapper)
        changed["resolver_successor"]["legacy_noncanonical_static_resources_exact"].append(
            copy.deepcopy(
                changed["resolver_successor"]["legacy_noncanonical_static_resources_exact"][0]
            )
        )
        mutations.append(("extra exception", changed))

        changed = copy.deepcopy(self.wrapper)
        changed["resolver_successor"]["legacy_noncanonical_static_resources_exact"][0][
            "raw_sha256"
        ] = "sha256:" + "0" * 64
        mutations.append(("raw digest", changed))

        changed = copy.deepcopy(self.wrapper)
        changed["resolver_successor"]["legacy_noncanonical_static_resources_exact"][1][
            "canonical_reencoding_sha256"
        ] = "sha256:" + "0" * 64
        mutations.append(("canonical digest", changed))

        changed = copy.deepcopy(self.wrapper)
        changed["historical_parent_incorporation"]["superseded_parent_rules_exact"][0]["scope"] = (
            "caller_selected"
        )
        mutations.append(("supersession scope", changed))

        changed = copy.deepcopy(self.wrapper)
        changed["contract_id"] = "source-reported-link-protected-ephemeral-custody-contract-v1"
        mutations.append(("contract id", changed))

        for label, value in mutations:
            with self.subTest(label=label), self.assertRaises(ValidationError):
                self.validator.validate(value)


if __name__ == "__main__":
    unittest.main()
