from __future__ import annotations

import copy
import hashlib
import json
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from indusbench.io import encode_json
from indusbench.kp1979_match_calibration import calibrate_matcher_plan
from indusbench.kp1979_row_matcher import (
    KP1979RowMatcherError,
    build_row_match_proposal,
    development_row_ids,
    verify_row_match_proposal_bytes,
)
from indusbench.kp1979_sign_template_roster import build_sign_template_roster
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_SCHEMA = ROOT / "schemas" / "kp1979-row-assignment.schema.json"
PROPOSAL_SCHEMA = ROOT / "schemas" / "kp1979-row-match-proposal.schema.json"
DEVELOPMENT_ROW_ID = "KP1979:P022:L1:V99"
RESERVED_ROW_ID = "KP1979:P078:L1:V99"


def tagged_sha256(raw_bytes: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


def pbm(*rows: str) -> bytes:
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise AssertionError("synthetic PBM rows must be rectangular")
    width = len(rows[0])
    row_bytes = (width + 7) // 8
    payload = bytearray()
    for row in rows:
        value = 0
        for symbol in row:
            value = (value << 1) | (1 if symbol == "#" else 0)
        value <<= row_bytes * 8 - width
        payload.extend(value.to_bytes(row_bytes, "big"))
    return f"P4\n{width} {len(rows)}\n".encode() + bytes(payload)


TEMPLATE_ROW_SETS = (
    (
        "#...#..#.##",
        ".........#.",
        ".#....##..#",
        "..#........",
        "..##.#...##",
        ".......#..#",
        "#....#.##..",
        "#...#......",
        "#...#..#.#.",
        "..##..##...",
        "..#..#.#..#",
    ),
    (
        "#..#.......",
        "....#.#...#",
        "...#......#",
        ".##.......#",
        "...#.#....#",
        "##..#.#....",
        "#..#...#...",
        "......#.#..",
        "#.#...#...#",
        ".##..##.#..",
        "..##....#.#",
    ),
    (
        "#..#....##.",
        ".#...#.....",
        ".##.##.##.#",
        "#....#...#.",
        ".##....##..",
        "....#....#.",
        ".....#....#",
        ".####.....#",
        "#...#.#....",
        "...##...#..",
        "....#.....#",
    ),
    (
        "#.....#.##.",
        ".#..#.....#",
        "..#....##.#",
        "....#.....#",
        "#..#.#..#..",
        "...#.....#.",
        "..........#",
        "..##.....#.",
        "#..#..###..",
        "....#.#.#.#",
        "##.#..#...#",
    ),
    (
        "###...#.##.",
        ".....#...#.",
        "...##....##",
        "..##.#.....",
        "..##...#...",
        "#.#..##....",
        "...........",
        "....##.####",
        ".#.#.......",
        "....#..#...",
        ".....#....#",
    ),
)
SYNTHETIC_TEMPLATES = tuple(
    (
        f"KP1979:P21:L01:R{99 - index:02d}",
        10 + index,
        pbm(*rows),
    )
    for index, rows in enumerate(TEMPLATE_ROW_SETS)
)
FIRST_TEMPLATE_ID, _FIRST_TEMPLATE_RANK, FIRST_GLYPH = SYNTHETIC_TEMPLATES[0]


def composed_row() -> bytes:
    width = 31
    height = 51
    rows = [["."] * width for _ in range(height)]
    for y, template_row in enumerate(TEMPLATE_ROW_SETS[0], start=3):
        for x, symbol in enumerate(template_row, start=2):
            rows[y][x] = symbol
    for y in range(2, 15):
        rows[y][28] = "#"
    return pbm(*(f"{''.join(row)}" for row in rows))


ROW_PBM = composed_row()
RESERVED_SENTINEL = b"reserved-row-must-never-be-opened"


def synthetic_roster() -> tuple[bytes, dict[str, bytes]]:
    geometry_items: list[dict[str, Any]] = []
    catalog_items: list[dict[str, Any]] = []
    glyphs: dict[str, bytes] = {}
    for position, (variant_id, catalog_rank, glyph) in enumerate(SYNTHETIC_TEMPLATES):
        row_index = 99 - position
        y0 = row_index * 20
        glyphs[variant_id] = glyph
        geometry_items.append(
            {
                "catalog_rank": catalog_rank,
                "cell_bbox": [2440, y0, 2460, y0 + 15],
                "cell_crop_byte_size": 1,
                "cell_crop_sha256": tagged_sha256(f"cell-{position}".encode()),
                "cell_id": variant_id,
                "glyph_bbox": [2442, y0 + 2, 2453, y0 + 13],
                "glyph_crop_byte_size": len(glyph),
                "glyph_crop_sha256": tagged_sha256(glyph),
                "lane_index": 1,
                "occupancy": "proposed_occupied",
                "page_index": 20,
                "pdf_page_number": 21,
                "row_index": row_index,
                "source_kp1982_cell_id": f"synthetic-sentinel-{position}",
            }
        )
        catalog_items.append(
            {
                "catalog_rank": catalog_rank,
                "catalog_rank_candidates": [catalog_rank],
                "catalog_rank_status": "machine_provisional_unique",
                "cell_id": variant_id,
                "lane_index": 1,
                "occupancy": "machine_provisional_occupied",
                "page_index": 20,
                "row_index": row_index,
                "template_digit_hamming_distances": [],
                "template_digits": None,
                "tesseract_upper_digits": None,
                "tesseract_upper_raw": None,
                "transferred_occupancy": "proposed_occupied",
            }
        )
    geometry_bytes = encode_json(
        {
            "record_id": "synthetic-sentinel-geometry",
            "items": geometry_items,
        }
    )
    catalog_bytes = encode_json(
        {
            "schema_version": "synthetic-sentinel",
            "record_id": "synthetic-sentinel-catalog",
            "status": "synthetic-sentinel",
            "scientific_scope": "synthetic-test-only",
            "inputs": {
                "signlist_manifest_sha256": hashlib.sha256(geometry_bytes).hexdigest(),
                "template_dp_sha256": "0" * 64,
                "ai_adjudication_sha256": "1" * 64,
            },
            "summary": {},
            "items": catalog_items,
            "assurances": {},
        }
    )
    roster = build_sign_template_roster(
        catalog_bytes,
        geometry_bytes,
        glyphs.__getitem__,
    )
    return encode_json(roster), glyphs


def slot(
    *,
    row_id: str,
    pdf_page_number: int,
    row_bytes: bytes,
) -> dict[str, Any]:
    return {
        "slot_id": row_id,
        "page_index": pdf_page_number - 1,
        "pdf_page_number": pdf_page_number,
        "lane_index": 1,
        "visual_row_index": 99,
        "proposed_label_bbox": [2466, 2, 2471, 15],
        "proposed_row_bbox": [2440, 0, 2471, 51],
        "label_crop_sha256": tagged_sha256(b"synthetic-label-locator"),
        "label_crop_byte_size": 1,
        "row_crop_sha256": tagged_sha256(row_bytes),
        "row_crop_byte_size": len(row_bytes),
    }


def assignment_bytes(*, include_development: bool = True) -> bytes:
    schema = json.loads(ASSIGNMENT_SCHEMA.read_text(encoding="utf-8"))
    properties = schema["properties"]
    assignment = {
        key: copy.deepcopy(properties[key]["const"])
        for key in (
            "schema_version",
            "manifest_id",
            "status",
            "scientific_scope",
            "source_contract",
            "page_map",
            "source_pdf",
            "layout_evaluation_page_protocol",
            "crop_policy",
            "withheld_fields",
            "assurances",
        )
    }
    assignment["selected_page_bitmaps"] = [
        copy.deepcopy(entry["const"])
        for entry in properties["selected_page_bitmaps"]["prefixItems"]
    ]
    assignment["slots"] = []
    if include_development:
        assignment["slots"].append(
            slot(
                row_id=DEVELOPMENT_ROW_ID,
                pdf_page_number=22,
                row_bytes=ROW_PBM,
            )
        )
    assignment["slots"].append(
        slot(
            row_id=RESERVED_ROW_ID,
            pdf_page_number=78,
            row_bytes=RESERVED_SENTINEL,
        )
    )
    self_issues = validate_schema_instance(assignment, ASSIGNMENT_SCHEMA)
    if self_issues:
        raise AssertionError(self_issues)
    return encode_json(assignment)


def recording_loader(calls: list[str], payload: bytes) -> Callable[[str], bytes]:
    def load(name: str) -> bytes:
        calls.append(name)
        return payload

    return load


def recording_mapping_loader(
    calls: list[str],
    payloads: dict[str, bytes],
) -> Callable[[str], bytes]:
    def load(name: str) -> bytes:
        calls.append(name)
        return payloads[name]

    return load


class KP1979RowMatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.roster_bytes, cls.glyphs = synthetic_roster()
        plan = calibrate_matcher_plan(SYNTHETIC_TEMPLATES)
        if plan["status"] != "frozen_closed_template_retrieval_only":
            raise AssertionError("synthetic matcher plan did not freeze")
        cls.plan_bytes = encode_json(plan)
        cls.assignment_bytes = assignment_bytes()

    def test_allowlist_and_build_never_load_reserved_future_row(self) -> None:
        self.assertEqual(
            (DEVELOPMENT_ROW_ID,),
            development_row_ids(self.assignment_bytes),
        )
        row_calls: list[str] = []

        def row_loader(row_id: str) -> bytes:
            row_calls.append(row_id)
            if row_id == RESERVED_ROW_ID:
                raise AssertionError("reserved future row was opened")
            return ROW_PBM

        with patch(
            "indusbench.kp1979_row_assignment.verify_row_assignment_bytes",
            side_effect=AssertionError("pixel-recomputing verifier was called"),
        ):
            proposal = build_row_match_proposal(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                row_loader,
            )

        self.assertEqual([DEVELOPMENT_ROW_ID], row_calls)
        self.assertEqual([], validate_schema_instance(proposal, PROPOSAL_SCHEMA))
        self.assertEqual([DEVELOPMENT_ROW_ID], [row["row_id"] for row in proposal["rows"]])
        self.assertFalse(proposal["partition_policy"]["reserved_future_rows_loaded"])
        self.assertFalse(proposal["assurances"]["row_assignment_source_pixels_recomputed"])
        self.assertFalse(proposal["assurances"]["template_roster_source_inputs_recomputed"])
        self.assertLessEqual(len(proposal["rows"][0]["proposal"]["candidate_paths"]), 3)
        self.assertEqual(
            [26, 2, 31, 15],
            proposal["rows"][0]["assignment_locator"]["relative_proposed_label_bbox"],
        )

    def test_exact_rebuild_binds_inputs_and_rejects_tampering(self) -> None:
        def row_loader(row_id: str) -> bytes:
            if row_id != DEVELOPMENT_ROW_ID:
                raise AssertionError("reserved future row was opened")
            return ROW_PBM

        first = build_row_match_proposal(
            self.assignment_bytes,
            self.roster_bytes,
            self.plan_bytes,
            self.glyphs.__getitem__,
            row_loader,
        )
        second = build_row_match_proposal(
            self.assignment_bytes,
            self.roster_bytes,
            self.plan_bytes,
            self.glyphs.__getitem__,
            row_loader,
        )
        self.assertEqual(first, second)
        proposal_bytes = encode_json(first)
        summary = verify_row_match_proposal_bytes(
            self.assignment_bytes,
            self.roster_bytes,
            self.plan_bytes,
            self.glyphs.__getitem__,
            row_loader,
            proposal_bytes,
        )
        self.assertTrue(summary["valid"])
        self.assertTrue(summary["raw_input_bytes_bound"])
        self.assertFalse(summary["reserved_future_rows_loaded"])
        self.assertFalse(summary["row_separator_calibration_claimed"])
        self.assertFalse(summary["open_set_allograph_generalization_claimed"])
        self.assertFalse(summary["sign_sequences_accepted"])
        self.assertFalse(summary["decipherment"])
        self.assertEqual(
            tagged_sha256(self.assignment_bytes),
            first["input_bindings"]["row_assignment"]["sha256"],
        )

        tampered = copy.deepcopy(first)
        tampered["rows"][0]["row_crop"]["sha256"] = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(KP1979RowMatcherError, "exact recomputation"):
            verify_row_match_proposal_bytes(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                row_loader,
                encode_json(tampered),
            )

        noncanonical = json.dumps(first, separators=(",", ":")).encode()
        with self.assertRaisesRegex(KP1979RowMatcherError, "not canonical"):
            verify_row_match_proposal_bytes(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                row_loader,
                noncanonical,
            )

    def test_row_hash_dimensions_and_relative_locator_fail_closed(self) -> None:
        with self.assertRaisesRegex(KP1979RowMatcherError, "assignment commitment"):
            build_row_match_proposal(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                lambda _row_id: ROW_PBM + b"tamper",
            )

        different_width = pbm(
            *(
                row[:-1]
                for row in (
                    ".......................",
                    ".......................",
                    "....................#..",
                    "....................#..",
                    "..#.#...............#..",
                    "...#................#..",
                    "..#.#...............#..",
                    "....................#..",
                    "....................#..",
                    "....................#..",
                    ".......................",
                    ".......................",
                )
            )
        )
        changed = json.loads(self.assignment_bytes)
        changed["slots"][0]["row_crop_sha256"] = tagged_sha256(different_width)
        changed["slots"][0]["row_crop_byte_size"] = len(different_width)
        with self.assertRaisesRegex(KP1979RowMatcherError, "dimensions differ"):
            build_row_match_proposal(
                encode_json(changed),
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                lambda row_id: (
                    different_width
                    if row_id == DEVELOPMENT_ROW_ID
                    else (_ for _ in ()).throw(AssertionError("reserved row opened"))
                ),
            )

        malformed_row = b"synthetic-not-a-canonical-pbm"
        malformed = json.loads(self.assignment_bytes)
        malformed["slots"][0]["row_crop_sha256"] = tagged_sha256(malformed_row)
        malformed["slots"][0]["row_crop_byte_size"] = len(malformed_row)
        with self.assertRaisesRegex(KP1979RowMatcherError, "PBM is not canonical"):
            build_row_match_proposal(
                encode_json(malformed),
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                lambda row_id: (
                    malformed_row
                    if row_id == DEVELOPMENT_ROW_ID
                    else (_ for _ in ()).throw(AssertionError("reserved row opened"))
                ),
            )

        outside = json.loads(self.assignment_bytes)
        outside["slots"][0]["proposed_label_bbox"] = [2466, 2, 2472, 15]
        row_calls: list[str] = []
        with self.assertRaisesRegex(KP1979RowMatcherError, "fixed crop policy"):
            build_row_match_proposal(
                encode_json(outside),
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                lambda row_id: row_calls.append(row_id) or ROW_PBM,
            )
        self.assertEqual([], row_calls)

    def test_exact_plan_recomputation_precedes_development_row_loader(self) -> None:
        base = json.loads(self.plan_bytes)
        tampered_plans: list[dict[str, Any]] = []
        no_go = copy.deepcopy(base)
        no_go["status"] = "no_go"
        tampered_plans.append(no_go)
        false_accept = copy.deepcopy(base)
        false_accept["closed_set_controls"]["validation"]["false_accepted"] = 1
        tampered_plans.append(false_accept)
        generalization = copy.deepcopy(base)
        generalization["open_set_lovo_negative_control"]["generalization_claimed"] = True
        tampered_plans.append(generalization)
        in_range_configuration_change = copy.deepcopy(base)
        in_range_configuration_change["configuration"]["max_token_cost"] = 5_000_000
        tampered_plans.append(in_range_configuration_change)

        for plan in tampered_plans:
            glyph_calls: list[str] = []
            row_calls: list[str] = []
            with (
                self.subTest(plan=plan["status"]),
                self.assertRaisesRegex(
                    KP1979RowMatcherError,
                    "exact template-only recomputation",
                ),
            ):
                build_row_match_proposal(
                    self.assignment_bytes,
                    self.roster_bytes,
                    encode_json(plan),
                    recording_mapping_loader(glyph_calls, self.glyphs),
                    recording_loader(row_calls, ROW_PBM),
                )
            self.assertEqual(list(self.glyphs), glyph_calls)
            self.assertEqual([], row_calls)

    def test_glyph_commitment_failure_precedes_development_row_loading(self) -> None:
        row_calls: list[str] = []
        with self.assertRaisesRegex(KP1979RowMatcherError, "roster commitment"):
            build_row_match_proposal(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                lambda _variant_id: FIRST_GLYPH + b"tamper",
                lambda row_id: row_calls.append(row_id) or ROW_PBM,
            )
        self.assertEqual([], row_calls)

    def test_reserved_only_or_inconsistent_identity_is_rejected_without_row_loading(self) -> None:
        with self.assertRaisesRegex(KP1979RowMatcherError, "no development rows"):
            development_row_ids(assignment_bytes(include_development=False))

        inconsistent = json.loads(self.assignment_bytes)
        inconsistent["slots"][0]["pdf_page_number"] = 78
        inconsistent["slots"][0]["page_index"] = 77
        row_calls: list[str] = []
        with self.assertRaisesRegex(KP1979RowMatcherError, "identity fields disagree"):
            build_row_match_proposal(
                encode_json(inconsistent),
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                lambda row_id: row_calls.append(row_id) or ROW_PBM,
            )
        self.assertEqual([], row_calls)

    def test_closed_schema_contains_no_interpretation_or_inventory_aggregate_fields(self) -> None:
        schema = json.loads(PROPOSAL_SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("private", schema["title"].lower())
        property_names: set[str] = set()
        pending: list[object] = [schema]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                properties = value.get("properties")
                if isinstance(properties, dict):
                    property_names.update(properties)
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        self.assertTrue(
            {
                "identifier",
                "code",
                "reading",
                "reading_direction",
                "language",
                "meaning",
                "translation",
                "sign_sequence",
                "accepted_sign",
            }.isdisjoint(property_names)
        )
        self.assertTrue(
            {
                "inventory",
                "summary",
                "row_count",
                "template_count",
                "catalog_count",
                "proposed_count",
                "abstained_count",
            }.isdisjoint(property_names)
        )
        assurances = schema["properties"]["assurances"]["const"]
        for field in (
            "row_geometry_accepted",
            "catalog_values_accepted",
            "sign_identity_accepted",
            "sign_sequences_accepted",
            "reading_direction_assigned",
            "language_assigned",
            "meaning_assigned",
            "translations_assigned",
            "human_review_complete",
            "independent_replication_complete",
            "public_release_authorized",
            "evaluation_admissible",
            "decipherment",
            "prize_submission_eligible",
        ):
            self.assertFalse(assurances[field])


if __name__ == "__main__":
    unittest.main()
