from __future__ import annotations

import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import indusbench.kp1979_row_assignment as row_assignment_module
from indusbench.io import encode_json
from indusbench.kp1979 import PAGE_HEIGHT, PAGE_WIDTH
from indusbench.kp1979_row_assignment import (
    KP1979RowAssignmentError,
    build_row_assignment,
    verify_row_assignment_bytes,
)
from indusbench.kp1982_layout import crop_canonical_pbm
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT = ROOT / "registry" / "kp1979_corpus.json"
PAGE_MAP = ROOT / "registry" / "kp1979_page_map.json"
ASSIGNMENT_SCHEMA = ROOT / "schemas" / "kp1979-row-assignment.schema.json"


def tagged_sha256(raw_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


def real_page_bytes(
    directory: Path,
    *,
    first_page: int,
    last_page: int,
):
    for page_number in range(first_page, last_page + 1):
        yield page_number, (directory / f"page-{page_number:03d}.pbm").read_bytes()


class KP1979RowAssignmentTests(unittest.TestCase):
    def test_checked_in_schema_is_closed_and_base_page_map_is_fixed(self) -> None:
        schema = json.loads(ASSIGNMENT_SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            "KP1979:BASE:ROW-ASSIGNMENT:V1",
            schema["properties"]["manifest_id"]["const"],
        )
        self.assertIn("Schema validation alone is non-attesting", schema["description"])
        self.assertIn("canonical pixel-recomputing verifier", schema["description"])
        selected_page_schema = schema["properties"]["selected_page_bitmaps"]
        self.assertEqual(57, selected_page_schema["minItems"])
        self.assertEqual(57, selected_page_schema["maxItems"])
        self.assertFalse(selected_page_schema["items"])
        self.assertEqual(57, len(selected_page_schema["prefixItems"]))
        self.assertEqual(5000, schema["properties"]["slots"]["maxItems"])
        checksum_schema = schema["$defs"]["checksum"]
        self.assertEqual(71, checksum_schema["minLength"])
        self.assertEqual(71, checksum_schema["maxLength"])
        slot_id_schema = schema["$defs"]["slot"]["properties"]["slot_id"]
        self.assertEqual(18, slot_id_schema["minLength"])
        self.assertEqual(18, slot_id_schema["maxLength"])
        self.assertEqual(
            [],
            validate_schema_instance("sha256:" + ("a" * 64), checksum_schema),
        )
        self.assertTrue(validate_schema_instance("sha256:" + ("a" * 64) + "\n", checksum_schema))
        self.assertEqual(
            [],
            validate_schema_instance("KP1979:P022:L0:V00", slot_id_schema),
        )
        self.assertTrue(validate_schema_instance("KP1979:P022:L0:V00\n", slot_id_schema))
        assurances = schema["properties"]["assurances"]["const"]
        self.assertTrue(assurances["proposal_geometry_only"])
        for field in (
            "label_geometry_accepted",
            "row_geometry_accepted",
            "occupancy_accepted",
            "human_review_complete",
            "reviewer_independence_verified",
            "identifiers_transcribed",
            "codes_transcribed",
            "sign_sequences_transcribed",
            "reading_direction_assigned",
            "language_assigned",
            "meaning_assigned",
            "private_storage_verified",
            "public_release_authorized",
            "evaluation_admissible",
            "decipherment",
        ):
            self.assertFalse(assurances[field])

        page_map = json.loads(PAGE_MAP.read_text(encoding="utf-8"))
        base_pages = row_assignment_module._base_page_entries(page_map)
        self.assertEqual(list(range(22, 79)), [page["pdf_page_number"] for page in base_pages])
        self.assertTrue(
            all(page["corpus_sequence_role"] == "base_rendering" for page in base_pages)
        )
        expected_pbm_size = page_map["canonicalization"]["canonical_pbm_byte_size"]
        expected_page_commitments = [
            {
                "page_index": page["page_index"],
                "pdf_page_number": page["pdf_page_number"],
                "canonical_pbm_sha256": page["canonical_pbm_sha256"],
                "byte_size": expected_pbm_size,
            }
            for page in base_pages
        ]
        self.assertEqual(
            expected_page_commitments,
            [entry["const"] for entry in selected_page_schema["prefixItems"]],
        )

    def test_slot_builder_binds_label_and_full_row_crops_without_answers(self) -> None:
        page_header = f"P4\n{PAGE_WIDTH} {PAGE_HEIGHT}\n".encode("ascii")
        page_bytes = page_header + bytes(((PAGE_WIDTH + 7) // 8) * PAGE_HEIGHT)
        page = {"page_index": 21, "pdf_page_number": 22}
        label_bbox = (2000, 100, 2100, 196)
        slot = row_assignment_module._build_slot(
            page=page,
            page_bytes=page_bytes,
            lane_index=0,
            visual_row_index=0,
            label_bbox=label_bbox,
        )
        self.assertEqual("KP1979:P022:L0:V00", slot["slot_id"])
        self.assertEqual([0, 64, 2100, 232], slot["proposed_row_bbox"])
        label_crop = crop_canonical_pbm(
            page_bytes,
            page_width=PAGE_WIDTH,
            page_height=PAGE_HEIGHT,
            bbox=label_bbox,
        )
        row_crop = crop_canonical_pbm(
            page_bytes,
            page_width=PAGE_WIDTH,
            page_height=PAGE_HEIGHT,
            bbox=(0, 64, 2100, 232),
        )
        self.assertEqual(tagged_sha256(label_crop), slot["label_crop_sha256"])
        self.assertEqual(len(label_crop), slot["label_crop_byte_size"])
        self.assertEqual(tagged_sha256(row_crop), slot["row_crop_sha256"])
        self.assertEqual(len(row_crop), slot["row_crop_byte_size"])
        row_assignment_module._reject_answer_keys(slot)

        with self.assertRaisesRegex(KP1979RowAssignmentError, "outside its page half"):
            row_assignment_module._build_slot(
                page=page,
                page_bytes=page_bytes,
                lane_index=1,
                visual_row_index=0,
                label_bbox=label_bbox,
            )

    def test_forbidden_answer_fields_are_rejected_recursively_before_rebuild(
        self,
    ) -> None:
        for field in (
            "identifier",
            "code",
            "sign_sequence",
            "reading_direction",
            "ocr_output",
            "accepted_observation",
            "translation",
        ):
            with self.subTest(field=field):
                value = {
                    "schema_version": "synthetic",
                    "nested": {"safe": [{field: "PRIVATE-VALUE"}]},
                }
                with (
                    patch.object(row_assignment_module, "build_row_assignment") as rebuild,
                    self.assertRaisesRegex(KP1979RowAssignmentError, "answer field"),
                ):
                    verify_row_assignment_bytes(
                        b"contract",
                        b"map",
                        b"pdf",
                        (),
                        (),
                        encode_json(value),
                    )
                rebuild.assert_not_called()

        row_assignment_module._reject_answer_keys(
            {
                "withheld_fields": [
                    "all_identifier_values",
                    "all_code_values",
                    "all_sign_values",
                ]
            }
        )

    def test_excessive_json_depth_is_a_fixed_error_before_rebuild(self) -> None:
        depth = 200
        assignment_bytes = b'{"nested":' + (b"[" * depth) + b"0" + (b"]" * depth) + b"}\n"
        with (
            patch.object(row_assignment_module, "build_row_assignment") as rebuild,
            self.assertRaisesRegex(KP1979RowAssignmentError, "nesting exceeds"),
        ):
            verify_row_assignment_bytes(
                b"contract",
                b"map",
                b"pdf",
                (),
                (),
                assignment_bytes,
            )
        rebuild.assert_not_called()

        with (
            patch.object(
                row_assignment_module,
                "decode_json",
                side_effect=RecursionError("synthetic decoder depth"),
            ),
            self.assertRaisesRegex(KP1979RowAssignmentError, "not strict finite JSON"),
        ):
            row_assignment_module._decode_object(
                b"{}",
                label="KP1979 row assignment",
                max_bytes=2,
            )

    def test_base_page_size_is_rejected_before_digest_work(self) -> None:
        page = {"page_index": 21, "pdf_page_number": 22}
        with (
            patch.object(row_assignment_module, "_tagged_sha256") as digest,
            patch.object(row_assignment_module, "detect_kp1979_page_layout") as detector,
            self.assertRaisesRegex(KP1979RowAssignmentError, "page-map commitment"),
        ):
            row_assignment_module._build_base_slots(
                [page],
                page_map={"canonicalization": {"canonical_pbm_byte_size": 4}},
                base_page_pbm_bytes=((22, b"oversized"),),
            )
        digest.assert_not_called()
        detector.assert_not_called()

    def test_schema_is_nonattesting_without_canonical_pixel_recomputation(self) -> None:
        schema = json.loads(ASSIGNMENT_SCHEMA.read_text(encoding="utf-8"))
        properties = schema["properties"]
        forged = {
            key: properties[key]["const"]
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
        forged["selected_page_bitmaps"] = [
            entry["const"] for entry in properties["selected_page_bitmaps"]["prefixItems"]
        ]
        forged["slots"] = [
            {
                "slot_id": "KP1979:P022:L0:V00",
                "page_index": 77,
                "pdf_page_number": 78,
                "lane_index": 1,
                "visual_row_index": 99,
                "proposed_label_bbox": [4000, 7000, 1, 1],
                "proposed_row_bbox": [4000, 7000, 1, 1],
                "label_crop_sha256": "sha256:" + ("f" * 64),
                "label_crop_byte_size": 1,
                "row_crop_sha256": "sha256:" + ("e" * 64),
                "row_crop_byte_size": 1,
            }
        ]
        self.assertEqual([], validate_schema_instance(forged, ASSIGNMENT_SCHEMA))

        with (
            patch.object(
                row_assignment_module,
                "build_row_assignment",
                return_value={"canonical_recomputation": "differs"},
            ) as rebuild,
            self.assertRaisesRegex(KP1979RowAssignmentError, "canonical pixel recomputation"),
        ):
            verify_row_assignment_bytes(
                b"contract",
                b"map",
                b"pdf",
                (),
                (),
                encode_json(forged),
            )
        rebuild.assert_called_once()

    def test_verifier_requires_canonical_exact_bytes_after_rebuild(self) -> None:
        assignment = {"schema_version": "synthetic", "proposal": True}
        canonical = encode_json(assignment)
        with (
            patch.object(
                row_assignment_module,
                "_decode_object",
                return_value=assignment,
            ),
            patch.object(
                row_assignment_module,
                "validate_schema_instance",
                return_value=[],
            ),
            patch.object(
                row_assignment_module,
                "build_row_assignment",
                return_value=assignment,
            ),
        ):
            summary = verify_row_assignment_bytes(
                b"contract",
                b"map",
                b"pdf",
                (),
                (),
                canonical,
            )
            self.assertTrue(summary["valid"])
            self.assertTrue(summary["assignment_canonical_bytes_verified"])
            self.assertTrue(summary["proposal_geometry_only"])
            self.assertTrue(summary["machine_answer_values_withheld"])
            self.assertNotIn("proposal_values_only", summary)
            self.assertFalse(summary["label_geometry_accepted"])
            self.assertFalse(summary["row_geometry_accepted"])
            self.assertFalse(summary["identifiers_transcribed"])
            self.assertFalse(summary["sign_sequences_transcribed"])
            self.assertFalse(summary["decipherment"])

            noncanonical = canonical.replace(b"{", b"{ ", 1)
            with self.assertRaisesRegex(KP1979RowAssignmentError, "canonical pixel recomputation"):
                verify_row_assignment_bytes(
                    b"contract",
                    b"map",
                    b"pdf",
                    (),
                    (),
                    noncanonical,
                )

    def test_full_layout_negative_gate_precedes_assignment_decoding(self) -> None:
        with (
            patch.object(
                row_assignment_module,
                "audit_kp1979_layout",
                side_effect=ValueError("negative page produced a row"),
            ),
            patch.object(row_assignment_module, "_decode_object") as decode,
            self.assertRaisesRegex(
                KP1979RowAssignmentError,
                "full-page source and negative-control audit failed",
            ),
        ):
            build_row_assignment(
                b"contract",
                b"map",
                b"pdf",
                ((2, b"page"),),
                ((22, b"base"),),
            )
        decode.assert_not_called()

    @unittest.skipUnless(
        os.environ.get("INDUSBENCH_KP1979_PDF") and os.environ.get("INDUSBENCH_KP1979_PBM_DIR"),
        "set INDUSBENCH_KP1979_PDF and INDUSBENCH_KP1979_PBM_DIR",
    )
    def test_fixed_official_build_and_exact_verification(self) -> None:
        source_bytes = Path(os.environ["INDUSBENCH_KP1979_PDF"]).read_bytes()
        page_directory = Path(os.environ["INDUSBENCH_KP1979_PBM_DIR"])
        assignment = build_row_assignment(
            SOURCE_CONTRACT.read_bytes(),
            PAGE_MAP.read_bytes(),
            source_bytes,
            real_page_bytes(page_directory, first_page=2, last_page=180),
            real_page_bytes(page_directory, first_page=22, last_page=78),
        )
        self.assertEqual([], validate_schema_instance(assignment, ASSIGNMENT_SCHEMA))
        self.assertTrue(assignment["slots"])
        self.assertTrue(assignment["assurances"]["proposal_geometry_only"])
        self.assertFalse(assignment["assurances"]["label_geometry_accepted"])
        self.assertFalse(assignment["assurances"]["row_geometry_accepted"])
        self.assertFalse(assignment["assurances"]["identifiers_transcribed"])
        self.assertFalse(assignment["assurances"]["sign_sequences_transcribed"])
        assignment_bytes = encode_json(assignment)
        summary = verify_row_assignment_bytes(
            SOURCE_CONTRACT.read_bytes(),
            PAGE_MAP.read_bytes(),
            source_bytes,
            real_page_bytes(page_directory, first_page=2, last_page=180),
            real_page_bytes(page_directory, first_page=22, last_page=78),
            assignment_bytes,
        )
        self.assertTrue(summary["assignment_canonical_bytes_verified"])
        self.assertFalse(summary["decipherment"])


if __name__ == "__main__":
    unittest.main()
