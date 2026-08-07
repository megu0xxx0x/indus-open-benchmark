from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

from indusbench.io import encode_json
from indusbench.kp1979_sign_template_roster import (
    KP1979SignTemplateRosterError,
    build_sign_template_roster,
    template_ids,
    verify_sign_template_roster_bytes,
)
from indusbench.schema_validation import validate_schema_instance


def pbm(*rows: str) -> bytes:
    width = len(rows[0])
    row_bytes = (width + 7) // 8
    payload = bytearray()
    for row in rows:
        value = 0
        for symbol in row:
            value = (value << 1) | (symbol == "#")
        payload.extend((value << (row_bytes * 8 - width)).to_bytes(row_bytes, "big"))
    return f"P4\n{width} {len(rows)}\n".encode() + bytes(payload)


GLYPH = pbm("#.#", ".#.", "#.#")
# Deliberately impossible source coordinates keep public fixtures distinct from
# every private sign-list inventory item.
SYNTHETIC_LANE_INDEX = 99
OCCUPIED_ID = "KP1979:P20:L99:R98"
BLANK_ID = "KP1979:P20:L99:R99"


def geometry_item(
    *,
    cell_id: str,
    row_index: int,
    occupancy: str,
    glyph: bytes = GLYPH,
) -> dict[str, Any]:
    return {
        "catalog_rank": 1 if occupancy == "proposed_occupied" else None,
        "cell_bbox": [0, row_index * 10, 10, row_index * 10 + 8],
        "cell_crop_byte_size": 1,
        "cell_crop_sha256": f"sha256:{'0' * 64}",
        "cell_id": cell_id,
        "glyph_bbox": [2, row_index * 10 + 2, 5, row_index * 10 + 5],
        "glyph_crop_byte_size": len(glyph),
        "glyph_crop_sha256": f"sha256:{hashlib.sha256(glyph).hexdigest()}",
        "lane_index": SYNTHETIC_LANE_INDEX,
        "occupancy": occupancy,
        "page_index": 19,
        "pdf_page_number": 20,
        "row_index": row_index,
        "source_kp1982_cell_id": f"synthetic:{row_index}",
    }


def catalog_item(
    *,
    cell_id: str,
    row_index: int,
    occupied: bool,
) -> dict[str, Any]:
    return {
        "catalog_rank": 7 if occupied else None,
        "catalog_rank_candidates": [7] if occupied else [],
        "catalog_rank_status": (
            "machine_provisional_unique" if occupied else "not_applicable_proposed_blank"
        ),
        "cell_id": cell_id,
        "lane_index": SYNTHETIC_LANE_INDEX,
        "occupancy": ("machine_provisional_occupied" if occupied else "machine_provisional_blank"),
        "page_index": 19,
        "row_index": row_index,
        "template_digit_hamming_distances": [],
        "template_digits": None,
        "tesseract_upper_digits": None,
        "tesseract_upper_raw": None,
        "transferred_occupancy": "proposed_occupied" if occupied else "proposed_blank",
    }


def inputs() -> tuple[bytes, bytes, dict[str, bytes]]:
    geometry = {
        "record_id": "synthetic:geometry",
        "items": [
            geometry_item(
                cell_id=OCCUPIED_ID,
                row_index=98,
                occupancy="proposed_occupied",
            ),
            geometry_item(
                cell_id=BLANK_ID,
                row_index=99,
                occupancy="proposed_blank",
            ),
        ],
    }
    geometry_bytes = json.dumps(geometry, separators=(",", ":"), sort_keys=False).encode()
    catalog = {
        "schema_version": "synthetic",
        "record_id": "synthetic:catalog",
        "status": "synthetic",
        "scientific_scope": "synthetic",
        "inputs": {
            "signlist_manifest_sha256": hashlib.sha256(geometry_bytes).hexdigest(),
            "template_dp_sha256": "0" * 64,
            "ai_adjudication_sha256": "1" * 64,
        },
        "summary": {},
        "items": [
            catalog_item(cell_id=OCCUPIED_ID, row_index=98, occupied=True),
            catalog_item(cell_id=BLANK_ID, row_index=99, occupied=False),
        ],
        "assurances": {},
    }
    return encode_json(catalog), geometry_bytes, {OCCUPIED_ID: GLYPH}


class SignTemplateRosterTests(unittest.TestCase):
    def test_builds_catalog_geometry_bound_provisional_roster(self) -> None:
        catalog_bytes, geometry_bytes, glyphs = inputs()
        requested: list[str] = []

        def loader(variant_id: str) -> bytes:
            requested.append(variant_id)
            return glyphs[variant_id]

        roster = build_sign_template_roster(catalog_bytes, geometry_bytes, loader)
        self.assertEqual([OCCUPIED_ID], requested)
        self.assertEqual([OCCUPIED_ID], [item["variant_id"] for item in roster["templates"]])
        self.assertEqual(7, roster["templates"][0]["catalog_rank"])
        self.assertEqual(
            {"variant_id", "catalog_rank", "glyph"},
            set(roster["templates"][0]),
        )
        self.assertFalse(roster["assurances"]["signlist_source_pages_reverified"])
        self.assertFalse(roster["assurances"]["catalog_values_accepted"])
        self.assertFalse(roster["assurances"]["decipherment"])
        schema = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / ("kp1979-sign-template-roster.schema.json")
        )
        self.assertEqual([], validate_schema_instance(roster, schema))

    def test_verifier_requires_exact_canonical_recomputation(self) -> None:
        catalog_bytes, geometry_bytes, glyphs = inputs()
        roster = build_sign_template_roster(catalog_bytes, geometry_bytes, glyphs.__getitem__)
        roster_bytes = encode_json(roster)
        summary = verify_sign_template_roster_bytes(
            catalog_bytes,
            geometry_bytes,
            glyphs.__getitem__,
            roster_bytes,
        )
        self.assertTrue(summary["valid"])
        self.assertTrue(summary["roster_canonical_bytes_verified"])
        self.assertEqual((OCCUPIED_ID,), template_ids(roster_bytes))

        tampered = json.loads(roster_bytes)
        tampered["templates"][0]["catalog_rank"] = 8
        with self.assertRaisesRegex(
            KP1979SignTemplateRosterError,
            "canonical glyph recomputation",
        ):
            verify_sign_template_roster_bytes(
                catalog_bytes,
                geometry_bytes,
                glyphs.__getitem__,
                encode_json(tampered),
            )
        with self.assertRaisesRegex(KP1979SignTemplateRosterError, "not canonical"):
            template_ids(json.dumps(roster, separators=(",", ":")).encode())

    def test_geometry_digest_is_over_raw_bytes_not_reencoded_value(self) -> None:
        catalog_bytes, geometry_bytes, glyphs = inputs()
        roster = build_sign_template_roster(catalog_bytes, geometry_bytes, glyphs.__getitem__)
        self.assertEqual(
            f"sha256:{hashlib.sha256(geometry_bytes).hexdigest()}",
            roster["input_bindings"]["geometry_manifest"]["sha256"],
        )
        reencoded_geometry = encode_json(json.loads(geometry_bytes))
        self.assertNotEqual(geometry_bytes, reencoded_geometry)
        with self.assertRaisesRegex(KP1979SignTemplateRosterError, "exact geometry"):
            build_sign_template_roster(
                catalog_bytes,
                reencoded_geometry,
                glyphs.__getitem__,
            )

    def test_rejects_all_white_glyph_for_occupied_catalog_item(self) -> None:
        catalog_bytes, geometry_bytes, _glyphs = inputs()
        geometry = json.loads(geometry_bytes)
        blank_glyph = pbm("...", "...", "...")
        geometry["items"][0]["glyph_crop_byte_size"] = len(blank_glyph)
        geometry["items"][0]["glyph_crop_sha256"] = (
            f"sha256:{hashlib.sha256(blank_glyph).hexdigest()}"
        )
        changed_geometry_bytes = json.dumps(
            geometry,
            separators=(",", ":"),
            sort_keys=False,
        ).encode()
        catalog = json.loads(catalog_bytes)
        catalog["inputs"]["signlist_manifest_sha256"] = hashlib.sha256(
            changed_geometry_bytes
        ).hexdigest()

        with self.assertRaisesRegex(
            KP1979SignTemplateRosterError,
            "contains no ink",
        ):
            build_sign_template_roster(
                encode_json(catalog),
                changed_geometry_bytes,
                lambda _name: blank_glyph,
            )

    def test_join_rank_bbox_hash_and_source_page_fail_closed(self) -> None:
        catalog_bytes, geometry_bytes, glyphs = inputs()
        catalog = json.loads(catalog_bytes)
        catalog["items"][0]["catalog_rank_candidates"] = [8]
        with self.assertRaisesRegex(KP1979SignTemplateRosterError, "absent"):
            build_sign_template_roster(
                encode_json(catalog),
                geometry_bytes,
                glyphs.__getitem__,
            )

        geometry = json.loads(geometry_bytes)
        geometry["items"][0]["pdf_page_number"] = 78
        geometry["items"][0]["page_index"] = 77
        changed_geometry_bytes = json.dumps(geometry, separators=(",", ":")).encode()
        catalog = json.loads(catalog_bytes)
        catalog["inputs"]["signlist_manifest_sha256"] = hashlib.sha256(
            changed_geometry_bytes
        ).hexdigest()
        calls: list[str] = []
        with self.assertRaisesRegex(KP1979SignTemplateRosterError, "outside sign-list pages"):
            build_sign_template_roster(
                encode_json(catalog),
                changed_geometry_bytes,
                lambda name: calls.append(name) or GLYPH,
            )
        self.assertEqual([], calls)

        catalog_bytes, geometry_bytes, _ = inputs()
        with self.assertRaisesRegex(KP1979SignTemplateRosterError, "geometry commitment"):
            build_sign_template_roster(
                catalog_bytes,
                geometry_bytes,
                lambda _name: GLYPH + b"tamper",
            )

    def test_schema_is_closed_and_contains_no_interpretation_fields(self) -> None:
        catalog_bytes, geometry_bytes, glyphs = inputs()
        roster = build_sign_template_roster(catalog_bytes, geometry_bytes, glyphs.__getitem__)
        roster["translation"] = "forbidden"
        with self.assertRaisesRegex(KP1979SignTemplateRosterError, "answer field"):
            template_ids(encode_json(roster))


if __name__ == "__main__":
    unittest.main()
