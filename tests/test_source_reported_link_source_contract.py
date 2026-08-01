from __future__ import annotations

import copy
import hashlib
import re
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from jsonschema import Draft202012Validator

from indusbench.io import CorpusFormatError, decode_json, encode_json

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "registry" / "source-reported-link-source-contract-v1.json"
SCHEMA_PATH = ROOT / "schemas" / "source-reported-link-source-contract.schema.json"
SOURCE_REGISTRY_PATH = ROOT / "registry" / "sources.json"
SOURCE_REGISTRY_SCHEMA_PATH = ROOT / "schemas" / "source-registry.schema.json"
POLICY_PATH = ROOT / "registry" / "source-reported-link-policy-v1.json"
POLICY_SCHEMA_PATH = ROOT / "schemas" / "source-reported-link-policy.schema.json"
PRESELECTION_PATH = ROOT / "registry" / "chanhu-daro-helsinki-gate-v1.json"
PRESELECTION_SCHEMA_PATH = ROOT / "schemas" / "context-source-link-gate.schema.json"

LINK_IDS = tuple(f"chanhu-daro-preselection-v1:{index:03d}" for index in range(6))
PENN_RECORD_IDS = ("83830", "83829", "149372", "238862", "329820")
PENN_RESOURCE_IDS = tuple(
    f"source-resource-v1:penn-object-{record_id}" for record_id in PENN_RECORD_IDS
)
PENN_ITEM_URIS = tuple(
    f"https://collections.penn.museum/collections/object/{record_id}"
    for record_id in PENN_RECORD_IDS
)
CANONICAL_JSON_PROFILE_ID = "indusbench-io-encode-json-v1"
PARENT_FILES = {
    "policy": POLICY_PATH,
    "policy_schema": POLICY_SCHEMA_PATH,
    "preselection_registry": PRESELECTION_PATH,
    "preselection_schema": PRESELECTION_SCHEMA_PATH,
    "source_registry": SOURCE_REGISTRY_PATH,
    "source_registry_schema": SOURCE_REGISTRY_SCHEMA_PATH,
}
PRIVATE_MARKERS = {
    "personal home path": re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+"),
    "literal IPv4": re.compile(
        r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
        r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)"
    ),
    "private key": re.compile(r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----"),
    "token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
}


def recursive_mutations(value: Any):
    if isinstance(value, dict):
        added = copy.deepcopy(value)
        added["unexpected"] = False
        yield added
        for key, child in value.items():
            removed = copy.deepcopy(value)
            del removed[key]
            yield removed
            for mutation in recursive_mutations(child):
                changed = copy.deepcopy(value)
                changed[key] = mutation
                yield changed
    elif isinstance(value, list):
        yield [*copy.deepcopy(value), None]
        if value:
            yield copy.deepcopy(value[:-1])
            reversed_value = list(reversed(copy.deepcopy(value)))
            if reversed_value != value:
                yield reversed_value
        for index, child in enumerate(value):
            for mutation in recursive_mutations(child):
                changed = copy.deepcopy(value)
                changed[index] = mutation
                yield changed
    elif isinstance(value, bool):
        yield not value
    elif isinstance(value, int):
        yield value + 1
    elif value is None:
        yield "unexpected"
    else:
        yield f"{value}-mutated"


def nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for child in value.values():
            keys.update(nested_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(nested_keys(child))
    return keys


def source_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["source_id"]: source for source in registry["sources"]}


def expected_tasks(parent_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = []
    for index, row in enumerate(parent_rows):
        mackay, official, accession = row["identifiers"]
        tasks.append(
            {
                "collision_group": row["collision_group"],
                "index": index,
                "link_id": row["link_id"],
                "mackay_locator": {
                    "identifier": mackay["identifier"],
                    "identifier_namespace": mackay["identifier_namespace"],
                    "resource_id": "source-resource-v1:mackay-report",
                },
                "penn_locators": [
                    {
                        "identifier": official["identifier"],
                        "identifier_namespace": official["identifier_namespace"],
                    },
                    {
                        "identifier": accession["identifier"],
                        "identifier_namespace": accession["identifier_namespace"],
                    },
                ],
                "penn_resource_id": (f"source-resource-v1:penn-object-{official['identifier']}"),
                "role": row["role"],
                "unresolved_axis": row["unresolved_axis"],
            }
        )
    return tasks


class SourceReportedLinkSourceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_bytes = CONTRACT_PATH.read_bytes()
        self.schema_bytes = SCHEMA_PATH.read_bytes()
        self.contract = decode_json(self.contract_bytes, source=str(CONTRACT_PATH))
        self.schema = decode_json(self.schema_bytes, source=str(SCHEMA_PATH))
        self.validator = Draft202012Validator(self.schema)

    def test_schema_const_contract_and_bytes_are_exact_and_canonical(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        self.validator.validate(self.contract)
        self.assertEqual(self.schema["const"], self.contract)
        self.assertEqual(encode_json(self.contract), self.contract_bytes)
        self.assertEqual(encode_json(self.schema), self.schema_bytes)
        self.assertEqual(
            "preregistered_contract_blocked_pending_revision_receipt",
            self.contract["contract_status"],
        )

        number_mutation = copy.deepcopy(self.contract)
        number_mutation["ordered_inspection_roster"]["ordered_source_roster_count"] = 6.0
        self.assertFalse(list(self.validator.iter_errors(number_mutation)))
        self.assertNotEqual(self.contract_bytes, encode_json(number_mutation))
        boundary = self.contract["execution_boundary"]
        self.assertIs(True, boundary["canonical_byte_identity_required"])
        self.assertEqual(
            "semantic_exact_const_with_json_number_equivalence",
            boundary["schema_validation_scope"],
        )
        profile = self.contract["canonical_json_profile"]
        self.assertEqual(CANONICAL_JSON_PROFILE_ID, profile["profile_id"])
        self.assertEqual("utf-8", profile["encoding"])
        self.assertEqual("single_lf", profile["document_end"])
        self.assertEqual(2, profile["indent_spaces_per_level"])
        self.assertIs(False, profile["ensure_ascii"])
        self.assertIs(False, profile["floats_permitted"])
        self.assertEqual("hard_reject", profile["noncanonical_raw_bytes_disposition"])

        duplicate = self.contract_bytes.replace(
            b'{\n  "canonical_json_profile":',
            b'{\n  "canonical_json_profile": {},\n  "canonical_json_profile":',
            1,
        )
        with self.assertRaises(CorpusFormatError):
            decode_json(duplicate, source="duplicate-contract")

    def test_exact_const_rejects_generated_recursive_mutations(self) -> None:
        checked = 0
        for mutation in recursive_mutations(self.contract):
            checked += 1
            self.assertTrue(list(self.validator.iter_errors(mutation)))
        self.assertGreater(checked, 500)

    def test_parent_commitments_bind_exact_current_files(self) -> None:
        commitments = self.contract["parent_commitments"]
        self.assertEqual(
            "45d946a462dd85aa3025ed9ad9c0465541bd85be",
            commitments["base_commit"],
        )
        for key, path in PARENT_FILES.items():
            with self.subTest(key=key):
                payload = path.read_bytes()
                expected = commitments[key]
                self.assertEqual(len(payload), expected["size"])
                self.assertEqual(
                    "sha256:" + hashlib.sha256(payload).hexdigest(),
                    expected["sha256"],
                )

    def test_source_registry_registration_is_distinct_and_fail_closed(self) -> None:
        registry = decode_json(SOURCE_REGISTRY_PATH.read_bytes(), source=str(SOURCE_REGISTRY_PATH))
        registry_schema = decode_json(
            SOURCE_REGISTRY_SCHEMA_PATH.read_bytes(), source=str(SOURCE_REGISTRY_SCHEMA_PATH)
        )
        Draft202012Validator(registry_schema).validate(registry)
        sources = registry["sources"]
        source_ids = [source["source_id"] for source in sources]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        by_id = source_map(registry)
        self.assertLessEqual(
            {
                "mackay-chanhu-daro-1943",
                "penn-museum-collections-data",
                "penn-museum-object-pages",
            },
            set(by_id),
        )

        item_source = by_id["penn-museum-object-pages"]
        self.assertEqual(
            list(PENN_ITEM_URIS),
            [value["value"] for value in item_source["citation"]["identifiers"]],
        )
        self.assertEqual(
            {
                "accessed_at": None,
                "access_method": "public_web",
                "landing_page": None,
                "snapshot_hash": None,
            },
            {
                key: item_source["access"][key]
                for key in ("accessed_at", "access_method", "landing_page", "snapshot_hash")
            },
        )
        self.assertEqual("unknown", item_source["rights"]["status"])
        self.assertIsNone(item_source["rights"]["license_id"])
        self.assertIsNone(item_source["rights"]["license_uri"])
        self.assertIsNone(item_source["rights"]["evidence_uri"])
        self.assertIsNone(item_source["rights"]["verified_at"])
        self.assertIsNone(item_source["rights"]["commercial_use"])
        self.assertIs(False, item_source["rights"]["redistribution"])
        self.assertIs(False, item_source["rights"]["derivatives"])
        self.assertEqual([], item_source["provenance"]["upstream_source_ids"])
        self.assertEqual("other", item_source["provenance"]["record_method"])
        self.assertNotIn("licence", item_source["rights"]["statement"].lower())

        bulk_source = by_id["penn-museum-collections-data"]
        self.assertEqual("CC-BY-4.0", bulk_source["rights"]["license_id"])
        self.assertNotEqual(bulk_source["source_id"], item_source["source_id"])
        transition = self.contract["registration_transition"]
        self.assertEqual("unregistered", transition["from_policy_registration_status"])
        self.assertIsNone(transition["from_policy_source_registry_binding"])
        self.assertEqual(item_source["source_id"], transition["item_source_id"])
        self.assertIs(False, transition["bulk_metadata_license_inherited"])
        self.assertIs(False, transition["transition_is_retroactive"])

        policy = decode_json(POLICY_PATH.read_bytes(), source=str(POLICY_PATH))
        frozen_item_state = policy["source_scope"][1]
        self.assertEqual("unregistered", frozen_item_state["registration_status"])
        self.assertIsNone(frozen_item_state["source_registry_binding"])
        self.assertEqual(item_source["source_id"], frozen_item_state["source_id"])

    def test_rights_layers_and_known_mackay_revision_do_not_overclaim(self) -> None:
        layers = {layer["source_id"]: layer for layer in self.contract["source_layers"]}
        mackay = layers["mackay-chanhu-daro-1943"]
        penn = layers["penn-museum-object-pages"]
        registry = source_map(decode_json(SOURCE_REGISTRY_PATH.read_bytes()))

        self.assertEqual(
            registry["mackay-chanhu-daro-1943"]["access"]["snapshot_hash"],
            mackay["revision"]["sha256"],
        )
        self.assertEqual(27802606, mackay["revision"]["byte_size"])
        self.assertEqual("exact_existing_registry_revision", mackay["revision"]["status"])
        self.assertEqual("unknown", mackay["rights_status"])
        self.assertEqual("unknown", penn["rights_status"])
        self.assertEqual("link_only", mackay["scope"])
        self.assertEqual("link_only", penn["scope"])
        self.assertIsNone(penn["license_id"])
        self.assertIsNone(penn["license_uri"])
        self.assertIsNone(penn["rights_evidence_uri"])
        self.assertIsNone(penn["rights_holder"])
        self.assertIsNone(penn["rights_verified_at"])
        self.assertIs(False, penn["bulk_metadata_license_inherited"])
        self.assertEqual("CC-BY-4.0", penn["noninherited_bulk_license_id"])

        for layer in layers.values():
            self.assertIs(False, layer["contract_content_included"])
            self.assertIs(False, layer["media_included"])
            self.assertIs(False, layer["redistribution_permitted"])
            self.assertIs(False, layer["derivatives_permitted"])
            self.assertIs(False, layer["handling_is_legal_conclusion"])
            self.assertIsNone(layer["commercial_use_permitted"])
        handling = self.contract["rights_handling"]
        self.assertIs(False, handling["item_page_bulk_license_inherited"])
        self.assertIs(False, handling["legal_determination_made"])
        self.assertIs(False, handling["rights_clearance_claimed"])

    def test_resources_roster_order_hash_conflict_and_collision_are_exact(self) -> None:
        resources = self.contract["retrieval_resources"]
        self.assertEqual(6, resources["count"])
        resource_rows = resources["resources"]
        resource_ids = [resource["resource_id"] for resource in resource_rows]
        self.assertEqual(len(resource_ids), len(set(resource_ids)))
        self.assertEqual("source-resource-v1:mackay-report", resource_ids[0])
        self.assertEqual(
            list(PENN_RESOURCE_IDS),
            resource_ids[1:],
        )
        self.assertEqual(
            list(zip(PENN_RESOURCE_IDS, PENN_ITEM_URIS, strict=True)),
            [(row["resource_id"], row["requested_uri"]) for row in resource_rows[1:]],
        )
        for resource, requested_uri in zip(resource_rows[1:], PENN_ITEM_URIS, strict=True):
            self.assertEqual("absent_pending_authorized_receipt", resource["revision_status"])
            self.assertEqual(requested_uri, resource["requested_uri"])
            self.assertTrue({"revision", "sha256", "byte_size"}.isdisjoint(resource))

        parent_rows = decode_json(PRESELECTION_PATH.read_bytes())["links"]
        roster = self.contract["ordered_inspection_roster"]
        tasks = roster["tasks"]
        self.assertEqual(6, roster["ordered_source_roster_count"])
        self.assertEqual(list(LINK_IDS), [task["link_id"] for task in tasks])
        self.assertEqual(expected_tasks(parent_rows), tasks)
        digest_payload = roster["hash_domain"].encode("ascii") + b"\x00" + encode_json(tasks)
        self.assertEqual(
            "sha256:" + hashlib.sha256(digest_payload).hexdigest(),
            roster["ordered_source_roster_sha256"],
        )
        self.assertIs(False, roster["post_hoc_row_substitution_permitted"])
        self.assertIs(False, roster["result_aggregation_permitted"])
        self.assertEqual(tasks[4]["penn_resource_id"], tasks[5]["penn_resource_id"])
        self.assertNotEqual(tasks[4]["link_id"], tasks[5]["link_id"])
        self.assertNotEqual(
            tasks[4]["mackay_locator"]["identifier"],
            tasks[5]["mackay_locator"]["identifier"],
        )
        self.assertEqual("excavation_location", tasks[1]["unresolved_axis"])

    def test_future_receipt_revision_set_and_attestation_interfaces_are_exact(self) -> None:
        requirement = self.contract["revision_receipt_requirement"]
        self.assertEqual(
            "separate_closed_schema_not_implemented",
            requirement["closed_receipt_schema_status"],
        )
        self.assertEqual("absent_not_created", requirement["receipt_status"])
        self.assertIs(False, requirement["receipt_creation_authorized"])
        self.assertEqual(5, requirement["penn_item_resource_count"])

        members = requirement["expected_members"]
        self.assertEqual(list(range(5)), [member["index"] for member in members])
        self.assertEqual(list(PENN_RESOURCE_IDS), [member["resource_id"] for member in members])
        self.assertEqual(list(PENN_ITEM_URIS), [member["requested_uri"] for member in members])
        self.assertEqual(5, len({member["resource_id"] for member in members}))
        self.assertEqual(5, len({member["requested_uri"] for member in members}))
        self.assertEqual([LINK_IDS[4], LINK_IDS[5]], members[4]["bound_link_ids"])
        self.assertIs(False, requirement["failure_handling"]["no_link_or_unresolved_permitted"])
        failure = requirement["failure_handling"]
        self.assertEqual("hard_reject", failure["invalid_input_disposition"])
        self.assertEqual("contract_blocked", failure["prerequisite_state_after_failure"])
        self.assertIs(False, failure["scientific_terminal_result_emitted"])
        self.assertLessEqual(
            {
                "non_200_http_status",
                "missing_receipt_member",
                "duplicate_resource_id",
                "receipt_member_order_mismatch",
                "resource_id_requested_uri_mapping_mismatch",
                "sha256_mismatch",
                "receipt_digest_mismatch",
                "revision_set_digest_mismatch",
                "tls_certificate_validation_error",
                "hostname_validation_error",
                "cached_response_reuse_detected",
            },
            set(failure["failure_codes"]),
        )

        top_level = requirement["future_receipt_top_level"]
        self.assertEqual(5, top_level["member_count"])
        self.assertEqual(self.contract["contract_id"], top_level["contract_id"])
        self.assertEqual(requirement["future_receipt_id"], top_level["receipt_id"])
        self.assertEqual("v1", top_level["receipt_schema_version"])
        self.assertEqual("complete", top_level["receipt_status"])
        self.assertNotIn("revision_receipt_sha256", top_level["required_fields"])
        self.assertEqual(
            "sha256_of_exact_finalized_contract_canonical_bytes_external_to_contract",
            top_level["contract_sha256_semantics"],
        )
        self.assertEqual(list(PENN_RESOURCE_IDS), top_level["ordered_resource_ids"])
        self.assertEqual(
            self.contract["parent_commitments"]["source_registry"]["sha256"],
            top_level["expected_source_registry_sha256"],
        )
        self.assertIn("contract_sha256", top_level["required_fields"])
        self.assertIn("source_registry_sha256", top_level["required_fields"])
        self.assertIn("members", top_level["required_fields"])

        self.assertEqual(
            [
                "resource_id",
                "requested_uri",
                "final_uri",
                "redirect_chain",
                "retrieved_at",
                "http_status",
                "content_type",
                "content_encoding",
                "response_representation",
                "byte_size",
                "sha256",
                "etag",
                "last_modified",
            ],
            requirement["required_member_fields"],
        )
        self.assertEqual(
            [
                "resource_id",
                "requested_uri",
                "final_uri",
                "redirect_chain",
                "retrieved_at",
                "http_status",
                "content_type",
                "content_encoding",
                "response_representation",
                "byte_size",
                "sha256",
            ],
            requirement["nonnullable_member_fields"],
        )
        self.assertEqual(["etag", "last_modified"], requirement["nullable_member_fields"])
        self.assertEqual(
            set(requirement["required_member_fields"]),
            set(requirement["nonnullable_member_fields"])
            | set(requirement["nullable_member_fields"]),
        )
        self.assertTrue(
            set(requirement["nonnullable_member_fields"]).isdisjoint(
                requirement["nullable_member_fields"]
            )
        )
        profile = requirement["fixed_request_profile"]
        self.assertEqual("GET", profile["http_method"])
        self.assertEqual("https", profile["uri_scheme"])
        self.assertEqual(
            [
                {"name": "Accept", "value": "text/html"},
                {"name": "Accept-Encoding", "value": "identity"},
            ],
            profile["request_headers"],
        )
        for key in (
            "additional_end_to_end_headers_permitted",
            "application_or_browser_cache_reuse_permitted",
            "authentication_permitted",
            "browser_execution_permitted",
            "cached_response_bytes_permitted",
            "client_certificates_permitted",
            "cookies_permitted",
            "environment_proxy_permitted",
            "netrc_or_credential_file_permitted",
            "proxy_permitted",
            "request_body_permitted",
            "script_execution_permitted",
        ):
            self.assertIs(False, profile[key])
        self.assertEqual(10, profile["connect_timeout_seconds"])
        self.assertEqual(10, profile["read_idle_timeout_seconds"])
        self.assertEqual(30, profile["request_overall_deadline_seconds"])
        self.assertIs(True, profile["fresh_network_response_required"])
        self.assertIs(True, profile["hostname_validation_required"])
        self.assertIs(True, profile["tls_certificate_validation_required"])

        response = requirement["response_requirements"]
        self.assertEqual(200, response["final_http_status"])
        self.assertEqual("text/html", response["normalized_content_type"])
        self.assertEqual(["identity"], response["content_encoding_allowed_values"])
        self.assertEqual(
            "missing_header_to_identity_ascii_casefold_identity_to_identity_other_rejected",
            response["content_encoding_normalization"],
        )
        self.assertIn("content_encoding", requirement["nonnullable_member_fields"])
        self.assertNotIn("content_encoding", requirement["nullable_member_fields"])
        self.assertIs(False, response["decompression_permitted"])
        self.assertIs(False, response["partial_or_truncated_body_permitted"])
        self.assertEqual(10485760, response["per_member_maximum_byte_size"])
        self.assertEqual(52428800, response["aggregate_maximum_byte_size"])
        self.assertEqual(
            {"revision_identity", "rights", "trusted_time"},
            set(response["metadata_cannot_substitute_for"]),
        )
        redirect = requirement["redirect_policy"]
        self.assertEqual(0, redirect["maximum_hops"])
        self.assertEqual("collections.penn.museum", redirect["host"])
        self.assertIs(True, redirect["full_ordered_chain_required"])
        self.assertIs(True, redirect["final_uri_equals_requested_uri"])
        self.assertEqual([], redirect["redirect_chain_required_value"])
        self.assertIs(False, redirect["redirects_permitted"])
        self.assertIs(False, redirect["source_substitution_permitted"])

        receipt_digest = requirement["future_receipt_digest"]
        self.assertEqual(CANONICAL_JSON_PROFILE_ID, receipt_digest["canonical_json_profile_id"])
        self.assertEqual(
            "indusbench:source-reported-link:source-revision-receipt:v1",
            receipt_digest["digest_domain"],
        )
        self.assertIs(False, receipt_digest["hashed_payload_contains_external_commitment"])
        self.assertEqual(
            "separate_receipt_commitment_envelope_not_receipt_payload",
            receipt_digest["external_commitment_location"],
        )
        self.assertIs(False, receipt_digest["receipt_payload_self_hash_field_permitted"])
        self.assertEqual("absent_not_computed", receipt_digest["status"])

        revision_set = requirement["source_revision_set_specification"]
        self.assertEqual(CANONICAL_JSON_PROFILE_ID, revision_set["canonical_json_profile_id"])
        self.assertEqual(6, revision_set["member_count"])
        self.assertEqual(
            ["source-resource-v1:mackay-report", *PENN_RESOURCE_IDS],
            revision_set["ordered_resource_ids"],
        )
        self.assertEqual(
            ["resource_id", "byte_size", "sha256"],
            revision_set["content_identity_fields"],
        )
        self.assertEqual(
            [
                "resource_id",
                "requested_uri",
                "final_uri",
                "response_representation",
                "byte_size",
                "sha256",
            ],
            revision_set["member_projection_fields"],
        )
        self.assertEqual(
            "exact_future_source_revision_sha256_from_this_domain_and_framing",
            revision_set["parent_policy_mapping"]["source_revision_sha256_exact"],
        )
        self.assertEqual(
            {"resource_count": 6, "revision_set_version": "v1"},
            revision_set["payload_constants"],
        )
        self.assertEqual("absent_not_computed", revision_set["status"])

        attestation = self.contract["inspection_procedure"]["future_completeness_attestation"]
        self.assertEqual(CANONICAL_JSON_PROFILE_ID, attestation["canonical_json_profile_id"])
        fixed = attestation["fixed_inputs"]
        self.assertEqual(list(LINK_IDS), fixed["processed_link_ids"])
        self.assertEqual(6, fixed["processed_count"])
        self.assertEqual(6, fixed["ordered_source_roster_count"])
        self.assertEqual(
            self.contract["ordered_inspection_roster"]["ordered_source_roster_sha256"],
            fixed["ordered_source_roster_sha256"],
        )
        for key in (
            "missing_count",
            "extra_count",
            "duplicate_count",
            "unreadable_count",
            "error_count",
            "ambiguous_count",
        ):
            self.assertEqual(0, fixed[key])
            self.assertIn(key, attestation["digest_input_fields"])
        self.assertIn("source_revision_sha256", attestation["digest_input_fields"])
        self.assertIn("revision_receipt_sha256", attestation["digest_input_fields"])
        self.assertIs(False, attestation["five_resource_coverage_substitution_permitted"])
        self.assertIs(False, attestation["shared_penn_resource_reuse_counts_as_duplicate"])
        self.assertIs(
            True,
            attestation["revision_receipt_sha256_cannot_substitute_for_source_revision_sha256"],
        )
        self.assertEqual(
            CANONICAL_JSON_PROFILE_ID,
            self.contract["ordered_inspection_roster"]["canonical_json_profile_id"],
        )
        self.assertEqual(5, len(members))
        self.assertEqual(6, revision_set["member_count"])
        self.assertEqual(6, fixed["ordered_source_roster_count"])
        self.assertNotEqual(len(members), revision_set["member_count"])
        self.assertEqual(revision_set["member_count"], fixed["ordered_source_roster_count"])
        self.assertEqual(6, len(fixed["processed_link_ids"]))

        retention = self.contract["inspection_procedure"]["content_retention_boundary"]
        self.assertIs(False, retention["public_or_repository_retention_permitted"])
        self.assertIs(False, retention["persistent_retention_permitted"])
        self.assertEqual(
            "required_but_not_authorized",
            retention["future_protected_ephemeral_retention_status"],
        )
        self.assertEqual("missing", retention["separate_custody_and_deletion_contract_status"])

    def test_future_interface_mutations_fail_closed_under_static_const(self) -> None:
        mutations: dict[str, tuple[str, Any]] = {}

        changed = copy.deepcopy(self.contract)
        changed["retrieval_resources"]["resources"][1]["requested_uri"] += "/wrong"
        mutations["retrieval URI"] = ("uri", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["expected_members"][0]["requested_uri"] = (
            PENN_ITEM_URIS[1]
        )
        mutations["mapping"] = ("mapping", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["nullable_member_fields"].reverse()
        mutations["nullable fields"] = ("nullability", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["expected_members"].reverse()
        mutations["member order"] = ("order", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["penn_item_resource_count"] = 4
        mutations["member count"] = ("count", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["expected_members"][1]["resource_id"] = (
            PENN_RESOURCE_IDS[0]
        )
        mutations["duplicate member"] = ("duplicate", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["response_requirements"]["final_http_status"] = 204
        mutations["HTTP status"] = ("status", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["redirect_policy"]["maximum_hops"] = 1
        mutations["redirect"] = ("redirect", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["fixed_request_profile"][
            "tls_certificate_validation_required"
        ] = False
        mutations["TLS validation"] = ("network", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["failure_handling"]["failure_codes"].remove(
            "sha256_mismatch"
        )
        mutations["hash error policy"] = ("hash", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["failure_handling"][
            "prerequisite_state_after_failure"
        ] = "unresolved"
        mutations["error disposition"] = ("error", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["future_receipt_digest"]["digest_framing"] += (
            "-mutated"
        )
        mutations["receipt digest framing"] = ("digest", changed)
        changed = copy.deepcopy(self.contract)
        changed["revision_receipt_requirement"]["source_revision_set_specification"][
            "digest_framing"
        ] += "-mutated"
        mutations["revision-set digest framing"] = ("digest", changed)
        changed = copy.deepcopy(self.contract)
        changed["inspection_procedure"]["future_completeness_attestation"]["digest_framing"] += (
            "-mutated"
        )
        mutations["attestation digest framing"] = ("digest", changed)
        changed = copy.deepcopy(self.contract)
        changed["inspection_procedure"]["future_completeness_attestation"]["fixed_inputs"][
            "processed_link_ids"
        ].reverse()
        mutations["link-slot coverage"] = ("coverage", changed)

        for name, (_, mutation) in mutations.items():
            with self.subTest(name=name):
                self.assertTrue(list(self.validator.iter_errors(mutation)))

    def test_blocked_boundary_has_no_receipt_digest_runtime_or_outcome(self) -> None:
        boundary = self.contract["execution_boundary"]
        self.assertEqual("not_authorized", boundary["authorization_status"])
        self.assertEqual("not_executed", boundary["execution_status"])
        for key in (
            "observations_present",
            "operational_parser_implemented",
            "pass_seals_present",
            "results_present",
            "revision_receipt_present",
            "runtime_evaluator_implemented",
            "source_access_performed_under_contract",
        ):
            self.assertIs(False, boundary[key])
        self.assertEqual({False}, set(self.contract["nonclaims"].values()))
        self.assertEqual(
            "absent_not_computed",
            self.contract["revision_receipt_requirement"]["revision_set_status"],
        )
        self.assertIs(
            False, self.contract["revision_receipt_requirement"]["receipt_creation_authorized"]
        )
        requirement = self.contract["revision_receipt_requirement"]
        self.assertEqual("absent_not_created", requirement["receipt_status"])
        self.assertEqual("absent_not_computed", requirement["future_receipt_digest"]["status"])
        self.assertEqual(
            "absent_not_computed", requirement["source_revision_set_specification"]["status"]
        )
        self.assertEqual(
            "separate_closed_schema_not_implemented",
            requirement["closed_receipt_schema_status"],
        )
        attestation = self.contract["inspection_procedure"]["future_completeness_attestation"]
        self.assertEqual("not_created_before_execution", attestation["status"])
        for artifact_key in (
            "revision_receipt",
            "revision_receipt_sha256",
            "source_revision_set",
            "source_revision_sha256",
            "completeness_attestation",
            "completeness_attestation_sha256",
        ):
            self.assertNotIn(artifact_key, self.contract)
        procedure = self.contract["inspection_procedure"]
        self.assertEqual("zero_or_one_else_unresolved", procedure["candidate_cardinality"])
        self.assertEqual(
            "unresolved",
            procedure["zero_candidate_without_complete_attestation"],
        )
        self.assertNotEqual("no_link", procedure["zero_candidate_without_complete_attestation"])
        keys = nested_keys(self.contract)
        self.assertNotIn("source_revision_set_sha256", keys)
        self.assertNotIn("completeness_attestation_sha256", keys)
        for key in ("observations", "results", "passes", "seal_sha256"):
            self.assertNotIn(key, self.contract)
        self.assertFalse(
            (ROOT / "src" / "indusbench" / "source_reported_link_source_contract.py").exists()
        )
        self.assertFalse((ROOT / "src" / "indusbench" / "source_reported_link.py").exists())
        receipt_schema_path = (
            ROOT / "schemas" / "source-reported-link-source-revision-receipt.schema.json"
        )
        self.assertTrue(receipt_schema_path.exists())
        receipt_schema = decode_json(receipt_schema_path.read_bytes())
        self.assertNotIn("revision_receipt_sha256", receipt_schema["properties"])

    def test_forbidden_channels_and_publication_markers_remain_absent(self) -> None:
        policy = decode_json(POLICY_PATH.read_bytes())
        self.assertEqual(policy["forbidden_channels"], self.contract["forbidden_channels"])
        forbidden = set(self.contract["forbidden_channels"])
        self.assertTrue(
            forbidden.isdisjoint(nested_keys(self.contract["ordered_inspection_roster"]["tasks"]))
        )
        candidate_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (CONTRACT_PATH, SCHEMA_PATH, SOURCE_REGISTRY_PATH)
        )
        self.assertNotIn("data/" + "raw/", candidate_text)
        self.assertNotIn("data/" + "derived/", candidate_text)
        for label, pattern in PRIVATE_MARKERS.items():
            with self.subTest(label=label):
                self.assertIsNone(pattern.search(candidate_text))

    def test_validation_is_repository_only_and_does_not_open_network(self) -> None:
        with (
            patch("socket.create_connection", side_effect=AssertionError("network forbidden")),
            patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")),
        ):
            contract = decode_json(CONTRACT_PATH.read_bytes())
            schema = decode_json(SCHEMA_PATH.read_bytes())
            Draft202012Validator(schema).validate(contract)
            registry = decode_json(SOURCE_REGISTRY_PATH.read_bytes())
            registry_schema = decode_json(SOURCE_REGISTRY_SCHEMA_PATH.read_bytes())
            Draft202012Validator(registry_schema).validate(registry)

    def test_static_packaging_boundary_makes_no_runtime_resource_claim(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"schemas" = "indusbench/schemas"', pyproject)
        for packaged_registry in (
            "chanhu-daro-helsinki-gate-v1.json",
            "sources.json",
            "source-reported-link-policy-v1.json",
            "source-reported-link-source-contract-v1.json",
            "source-reported-link-protected-ephemeral-custody-contract-v1.json",
        ):
            self.assertIn(
                f'"registry/{packaged_registry}" = "indusbench/registry/{packaged_registry}"',
                pyproject,
            )
        self.assertIn('"/registry"', pyproject)
        self.assertIn('"/tests"', pyproject)
        self.assertTrue((ROOT / "src" / "indusbench" / "source_reported_link_resource.py").exists())
        self.assertTrue((ROOT / "src" / "indusbench" / "source_reported_link_static.py").exists())
        for runtime_module in (
            "source_reported_link_acquisition.py",
            "source_reported_link_parser.py",
            "source_reported_link_evaluator.py",
            "source_reported_link_strict_verifier.py",
        ):
            self.assertFalse((ROOT / "src" / "indusbench" / runtime_module).exists())


if __name__ == "__main__":
    unittest.main()
