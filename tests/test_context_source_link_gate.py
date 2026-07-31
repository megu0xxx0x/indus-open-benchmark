from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from indusbench.io import encode_json

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "context-source-link-gate.schema.json"
REGISTRY_PATH = ROOT / "registry" / "chanhu-daro-helsinki-gate-v1.json"
CONTEXT_ANCHOR_SCHEMA_PATH = ROOT / "schemas" / "context-anchor-registry.schema.json"
SOURCE_REGISTRY_PATH = ROOT / "registry" / "sources.json"


def identifier(source_id: str, namespace: str, value: str) -> dict[str, str]:
    return {
        "identifier": value,
        "identifier_namespace": namespace,
        "source_id": source_id,
    }


def link(
    index: int,
    field_number: str,
    official_record_id: str,
    accession_number: str,
    role: str,
    *,
    unresolved_axis: str | None = None,
    collision_group: str | None = None,
) -> dict[str, Any]:
    return {
        "collision_group": collision_group,
        "preselection_status": "source_locator_only",
        "identifiers": [
            identifier("mackay-chanhu-daro-1943", "field_number", field_number),
            identifier(
                "penn-museum-collections-data",
                "official_record_id",
                official_record_id,
            ),
            identifier(
                "penn-museum-collections-data",
                "accession_number",
                accession_number,
            ),
        ],
        "future_join_status": "not_joined_requires_separate_contract",
        "link_id": f"chanhu-daro-preselection-v1:{index:03d}",
        "role": role,
        "unresolved_axis": unresolved_axis,
    }


COLLISION_GROUP = "chanhu-daro-penn-329820-collision"
EXPECTED_LINKS = [
    link(
        0,
        "SF 2000",
        "83830",
        "L-141-160",
        "lead_no_listed_material_conflict",
    ),
    link(
        1,
        "SF 3495",
        "83829",
        "L-141-159",
        "excavation_location_axis_conflict",
        unresolved_axis="excavation_location",
    ),
    link(
        2,
        "SF 3493",
        "149372",
        "L-141-92",
        "lead_no_listed_material_conflict",
    ),
    link(
        3,
        "SF 2428",
        "238862",
        "L-141-176",
        "lead_no_listed_material_conflict",
    ),
    link(
        4,
        "SF 3051",
        "329820",
        "L-141-177",
        "shared_penn_target_identity_collision",
        collision_group=COLLISION_GROUP,
    ),
    link(
        5,
        "SF 2558",
        "329820",
        "L-141-177",
        "shared_penn_target_identity_collision",
        collision_group=COLLISION_GROUP,
    ),
]
EXPECTED_RIGHTS_LAYERS = [
    {
        "layer": "penn_bulk_metadata",
        "license_id": "CC-BY-4.0",
        "media_included": False,
        "redistribution_permitted": True,
        "rights_status": "open_licensed",
        "scope": "metadata_only",
        "source_registry_id": "penn-museum-collections-data",
    },
    {
        "layer": "penn_item_page_association",
        "license_id": None,
        "media_included": False,
        "redistribution_permitted": False,
        "rights_status": "unknown",
        "scope": "link_only",
        "source_binding_status": "extra_bulk_item_page_not_registered",
        "source_layer_id": "penn-museum-object-pages",
        "source_registry_binding": None,
    },
    {
        "layer": "mackay_report_locator",
        "license_id": None,
        "media_included": False,
        "redistribution_permitted": False,
        "rights_status": "unknown",
        "scope": "link_only",
        "source_registry_id": "mackay-chanhu-daro-1943",
    },
]
EXPECTED_REGISTRY: dict[str, Any] = {
    "counts": {
        "admitted_join_count": 0,
        "distinct_penn_catalog_records": 5,
        "links": 6,
    },
    "links": EXPECTED_LINKS,
    "nonclaims": {
        "context_correctness_verified": False,
        "decipherment_evidence": False,
        "evaluation_admitted": False,
        "evaluation_nonexposure_verified": False,
        "field_number_truth_verified": False,
        "future_join_rights_verified": False,
        "object_authenticity_verified": False,
        "physical_identity_verified": False,
        "selection_representativeness_verified": False,
        "source_independence_verified": False,
        "transcription_approved": False,
    },
    "ordering_semantics": "source_table_order_only_not_rank",
    "record_state": "preselection_only_no_source_join",
    "registry_id": "chanhu-daro-helsinki-gate-v1",
    "rights_layers": EXPECTED_RIGHTS_LAYERS,
    "role_counts": {
        "excavation_location_axis_conflict": 1,
        "lead_no_listed_material_conflict": 3,
        "shared_penn_target_identity_collision": 2,
    },
    "schema_version": "0.1.0",
    "selection_basis_id": "chanhu-daro-context-crosswalk-audit:2026-07-28",
}
EXPECTED_REQUIRED = [
    "counts",
    "links",
    "nonclaims",
    "ordering_semantics",
    "record_state",
    "registry_id",
    "rights_layers",
    "role_counts",
    "schema_version",
    "selection_basis_id",
]
EXPECTED_SCHEMA: dict[str, Any] = {
    "$id": "context-source-link-gate.schema.json",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "additionalProperties": False,
    "properties": {
        "counts": {"const": EXPECTED_REGISTRY["counts"]},
        "links": {
            "items": False,
            "maxItems": 6,
            "minItems": 6,
            "prefixItems": [{"const": value} for value in EXPECTED_LINKS],
            "type": "array",
        },
        "nonclaims": {"const": EXPECTED_REGISTRY["nonclaims"]},
        "ordering_semantics": {"const": EXPECTED_REGISTRY["ordering_semantics"]},
        "record_state": {"const": EXPECTED_REGISTRY["record_state"]},
        "registry_id": {"const": EXPECTED_REGISTRY["registry_id"]},
        "rights_layers": {
            "items": False,
            "maxItems": 3,
            "minItems": 3,
            "prefixItems": [{"const": value} for value in EXPECTED_RIGHTS_LAYERS],
            "type": "array",
        },
        "role_counts": {"const": EXPECTED_REGISTRY["role_counts"]},
        "schema_version": {"const": EXPECTED_REGISTRY["schema_version"]},
        "selection_basis_id": {"const": EXPECTED_REGISTRY["selection_basis_id"]},
    },
    "required": EXPECTED_REQUIRED,
    "type": "object",
}
FORBIDDEN_LINK_KEY_FRAGMENTS = (
    "sign",
    "glyph",
    "token",
    "sequence",
    "transcription",
    "reading",
    "direction",
    "count",
    "image",
    "media",
    "scan",
    "ocr",
    "meaning",
    "language",
    "translation",
    "phonetic",
    "source_text",
    "quote",
    "hash",
    "bytes",
    "path",
)


def walk_objects(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_objects(child)


class ContextSourceLinkGateTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema)

    def assert_rejected(self, candidate: dict[str, Any]) -> None:
        self.assertTrue(list(self.validator.iter_errors(candidate)))

    def test_schema_and_registry_are_exact_and_canonical(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        self.validator.validate(self.registry)
        self.assertEqual(EXPECTED_SCHEMA, self.schema)
        self.assertEqual(EXPECTED_REGISTRY, self.registry)
        self.assertEqual(encode_json(EXPECTED_SCHEMA), SCHEMA_PATH.read_bytes())
        self.assertEqual(encode_json(EXPECTED_REGISTRY), REGISTRY_PATH.read_bytes())

    def test_schema_fixes_six_ordered_rows_and_three_rights_layers(self) -> None:
        properties = self.schema["properties"]
        self.assertEqual(
            "source_table_order_only_not_rank",
            properties["ordering_semantics"]["const"],
        )
        self.assertEqual(
            "preselection_only_no_source_join",
            properties["record_state"]["const"],
        )
        links = properties["links"]
        self.assertEqual(6, links["minItems"])
        self.assertEqual(6, links["maxItems"])
        self.assertIs(False, links["items"])
        self.assertEqual([{"const": value} for value in EXPECTED_LINKS], links["prefixItems"])

        rights = properties["rights_layers"]
        self.assertEqual(3, rights["minItems"])
        self.assertEqual(3, rights["maxItems"])
        self.assertIs(False, rights["items"])
        self.assertEqual(
            [{"const": value} for value in EXPECTED_RIGHTS_LAYERS],
            rights["prefixItems"],
        )

    def test_existing_context_anchor_gates_remain_unavailable_and_unapproved(self) -> None:
        context_anchor_schema = json.loads(CONTEXT_ANCHOR_SCHEMA_PATH.read_text(encoding="utf-8"))
        field_numbers = context_anchor_schema["$defs"]["field_numbers"]["properties"]
        self.assertEqual(
            "not_available_in_bulk_snapshot",
            field_numbers["status"]["const"],
        )
        self.assertEqual([], field_numbers["values"]["const"])

        admission = context_anchor_schema["$defs"]["admission"]["properties"]
        self.assertIs(True, admission["human_review_required"]["const"])
        for field in (
            "transcription_approved",
            "meaning_approved",
            "originality_approved",
            "field_number_approved",
        ):
            self.assertIs(False, admission[field]["const"])

    def test_rights_layers_match_the_tracked_public_source_registry(self) -> None:
        source_registry = json.loads(SOURCE_REGISTRY_PATH.read_text(encoding="utf-8"))
        sources = {value["source_id"]: value for value in source_registry["sources"]}
        registered_layer_source_ids = {
            value["source_registry_id"]
            for value in self.registry["rights_layers"]
            if value.get("source_registry_id") is not None
        }
        referenced_source_ids = {
            identifier_value["source_id"]
            for link_value in self.registry["links"]
            for identifier_value in link_value["identifiers"]
        } | registered_layer_source_ids
        self.assertLessEqual(referenced_source_ids, sources.keys())

        layers = {value["layer"]: value for value in self.registry["rights_layers"]}
        for source_id, layer_id in (
            ("penn-museum-collections-data", "penn_bulk_metadata"),
            ("mackay-chanhu-daro-1943", "mackay_report_locator"),
        ):
            source_rights = sources[source_id]["rights"]
            layer = layers[layer_id]
            self.assertEqual(source_rights["status"], layer["rights_status"])
            self.assertEqual(source_rights["license_id"], layer["license_id"])
            self.assertEqual(source_rights["redistribution"], layer["redistribution_permitted"])

        item_page_layer = layers["penn_item_page_association"]
        self.assertEqual(
            "extra_bulk_item_page_not_registered",
            item_page_layer["source_binding_status"],
        )
        self.assertEqual("penn-museum-object-pages", item_page_layer["source_layer_id"])
        self.assertIsNone(item_page_layer["source_registry_binding"])
        self.assertNotIn("source_registry_id", item_page_layer)
        self.assertEqual("unknown", item_page_layer["rights_status"])
        self.assertIsNone(item_page_layer["license_id"])
        self.assertIs(False, item_page_layer["redistribution_permitted"])

    def test_registry_is_locator_only_and_keeps_all_gates_closed(self) -> None:
        links = self.registry["links"]
        counts = self.registry["counts"]
        official_record_ids = {value["identifiers"][1]["identifier"] for value in links}
        computed_role_counts = {
            role: sum(value["role"] == role for value in links)
            for role in {value["role"] for value in links}
        }
        self.assertEqual(len(links), counts["links"])
        self.assertEqual(
            len(official_record_ids),
            counts["distinct_penn_catalog_records"],
        )
        self.assertEqual(0, counts["admitted_join_count"])
        self.assertEqual(computed_role_counts, self.registry["role_counts"])
        for value in links:
            self.assertEqual(
                [
                    "mackay-chanhu-daro-1943",
                    "penn-museum-collections-data",
                    "penn-museum-collections-data",
                ],
                [item["source_id"] for item in value["identifiers"]],
            )
        self.assertEqual(
            ["SF 2000", "SF 3495", "SF 3493", "SF 2428", "SF 3051", "SF 2558"],
            [value["identifiers"][0]["identifier"] for value in self.registry["links"]],
        )
        self.assertEqual(
            {
                "excavation_location_axis_conflict": 1,
                "lead_no_listed_material_conflict": 3,
                "shared_penn_target_identity_collision": 2,
            },
            self.registry["role_counts"],
        )
        for value in self.registry["links"]:
            self.assertEqual("source_locator_only", value["preselection_status"])
            self.assertEqual(
                "not_joined_requires_separate_contract",
                value["future_join_status"],
            )
            for object_value in walk_objects(value):
                for key in object_value:
                    self.assertFalse(
                        any(fragment in key.lower() for fragment in FORBIDDEN_LINK_KEY_FRAGMENTS),
                        key,
                    )

        string_values = {
            value
            for object_value in walk_objects(self.registry)
            for value in object_value.values()
            if isinstance(value, str)
        }
        self.assertTrue(
            {"positive", "probable", "exact", "joined", "admitted"}.isdisjoint(string_values)
        )
        self.assertEqual({False}, set(self.registry["nonclaims"].values()))

    def test_rejects_reorder_drop_and_add(self) -> None:
        reordered = copy.deepcopy(self.registry)
        reordered["links"][0], reordered["links"][1] = (
            reordered["links"][1],
            reordered["links"][0],
        )
        dropped = copy.deepcopy(self.registry)
        dropped["links"].pop()
        added = copy.deepcopy(self.registry)
        added["links"].append({})
        for label, candidate in (
            ("reordered", reordered),
            ("dropped", dropped),
            ("added", added),
        ):
            with self.subTest(label=label):
                self.assert_rejected(candidate)

    def test_rejects_role_status_and_rights_mutations(self) -> None:
        role = copy.deepcopy(self.registry)
        role["links"][0]["role"], role["links"][1]["role"] = (
            role["links"][1]["role"],
            role["links"][0]["role"],
        )
        preselection_status = copy.deepcopy(self.registry)
        preselection_status["links"][0]["preselection_status"] = "probable"
        future_join_status = copy.deepcopy(self.registry)
        future_join_status["links"][0]["future_join_status"] = "joined"
        rights = copy.deepcopy(self.registry)
        rights["rights_layers"][1]["rights_status"] = "open_licensed"
        rights["rights_layers"][1]["license_id"] = "CC-BY-4.0"
        rights["rights_layers"][1]["redistribution_permitted"] = True
        for candidate in (role, preselection_status, future_join_status, rights):
            self.assert_rejected(candidate)

    def test_rejects_namespace_bare_identifier_and_forbidden_nested_field(self) -> None:
        namespace = copy.deepcopy(self.registry)
        namespace["links"][0]["identifiers"][1]["identifier_namespace"] = "field_number"
        bare = copy.deepcopy(self.registry)
        bare["links"][0]["identifiers"][0] = "SF 2000"
        nested = copy.deepcopy(self.registry)
        nested["links"][0]["identifiers"][0]["transcription"] = "forbidden"
        for candidate in (namespace, bare, nested):
            self.assert_rejected(candidate)

    def test_rejects_conflict_collision_and_third_duplicate_tampering(self) -> None:
        conflict = copy.deepcopy(self.registry)
        conflict["links"][1]["unresolved_axis"] = None
        conflict_promotion = copy.deepcopy(self.registry)
        conflict_promotion["links"][1]["role"] = "lead_no_listed_material_conflict"
        conflict_promotion["links"][1]["unresolved_axis"] = None
        collision = copy.deepcopy(self.registry)
        collision["links"][4]["collision_group"] = None
        collision_endpoint = copy.deepcopy(self.registry)
        collision_endpoint["links"][5]["identifiers"][1]["identifier"] = "329821"
        third_duplicate = copy.deepcopy(self.registry)
        duplicate = copy.deepcopy(third_duplicate["links"][5])
        duplicate["link_id"] = "chanhu-daro-preselection-v1:006"
        duplicate["identifiers"][0]["identifier"] = "SF 9999"
        third_duplicate["links"].append(duplicate)
        self.assertEqual(
            3,
            sum(
                value["identifiers"][1]["identifier"] == "329820"
                for value in third_duplicate["links"]
            ),
        )
        for candidate in (
            conflict,
            conflict_promotion,
            collision,
            collision_endpoint,
            third_duplicate,
        ):
            self.assert_rejected(candidate)


if __name__ == "__main__":
    unittest.main()
