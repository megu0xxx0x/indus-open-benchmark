from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path

from indusbench.cli import main
from indusbench.io import encode_json
from indusbench.kp1979 import (
    EXPECTED_PAGE_MAP_BYTE_SIZE,
    EXPECTED_PAGE_MAP_SHA256,
    EXPECTED_SOURCE_CONTRACT_BYTE_SIZE,
    EXPECTED_SOURCE_CONTRACT_SHA256,
    KP1979SourceError,
    audit_kp1979_layout,
    detect_kp1979_page_layout,
    verify_kp1979_source,
)
from indusbench.printed_concordance_layout import detect_two_column_label_lattice
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT = ROOT / "registry" / "kp1979_corpus.json"
PAGE_MAP = ROOT / "registry" / "kp1979_page_map.json"
SOURCE_SCHEMA = ROOT / "schemas" / "kp1979-corpus-source.schema.json"
PAGE_MAP_SCHEMA = ROOT / "schemas" / "kp1979-page-map.schema.json"


def iter_real_page_bytes(directory: Path):
    for page in range(2, 181):
        yield page, (directory / f"page-{page:03d}.pbm").read_bytes()


class KP1979SourceTests(unittest.TestCase):
    def test_checked_in_contracts_match_closed_schemas_and_fixed_bytes(self) -> None:
        source_bytes = SOURCE_CONTRACT.read_bytes()
        page_map_bytes = PAGE_MAP.read_bytes()
        self.assertEqual(EXPECTED_SOURCE_CONTRACT_BYTE_SIZE, len(source_bytes))
        self.assertEqual(
            EXPECTED_SOURCE_CONTRACT_SHA256,
            "sha256:" + hashlib.sha256(source_bytes).hexdigest(),
        )
        self.assertEqual(EXPECTED_PAGE_MAP_BYTE_SIZE, len(page_map_bytes))
        self.assertEqual(
            EXPECTED_PAGE_MAP_SHA256,
            "sha256:" + hashlib.sha256(page_map_bytes).hexdigest(),
        )
        self.assertEqual(
            [],
            validate_schema_instance(json.loads(source_bytes), SOURCE_SCHEMA),
        )
        self.assertEqual(
            [],
            validate_schema_instance(json.loads(page_map_bytes), PAGE_MAP_SCHEMA),
        )

    def test_page_map_is_contiguous_and_keeps_auxiliary_pages_nonlinguistic(self) -> None:
        page_map = json.loads(PAGE_MAP.read_text(encoding="utf-8"))
        pages = page_map["pages"]
        self.assertEqual(list(range(2, 181)), [page["pdf_page_number"] for page in pages])
        by_number = {page["pdf_page_number"]: page for page in pages}
        self.assertEqual("sign_list_negative", by_number[20]["page_role"])
        self.assertEqual("base_rendering", by_number[22]["corpus_sequence_role"])
        self.assertEqual("internal_crosscheck", by_number[79]["corpus_sequence_role"])
        self.assertEqual("sorted_end_auxiliary_grid_8", by_number[129]["layout_class"])
        self.assertEqual("sorted_end_auxiliary_grid_6", by_number[130]["layout_class"])
        self.assertFalse(by_number[129]["contains_linguistic_sequence_candidates"])
        self.assertFalse(by_number[130]["contains_linguistic_sequence_candidates"])
        self.assertTrue(by_number[128]["contains_linguistic_sequence_candidates"])
        self.assertEqual([[3000, 5000, 4550, 5850]], by_number[180]["proposal_exclusion_bboxes"])

    def test_contract_or_page_map_rewrite_cannot_authorize_other_bytes(self) -> None:
        synthetic_pdf = b"%PDF-1.3\nsynthetic\n%%EOF\n"
        rewritten = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
        rewritten["source"]["byte_size"] = len(synthetic_pdf)
        rewritten["source"]["sha256"] = "sha256:" + hashlib.sha256(synthetic_pdf).hexdigest()
        with self.assertRaisesRegex(KP1979SourceError, "fixed V1 snapshot"):
            verify_kp1979_source(
                encode_json(rewritten),
                PAGE_MAP.read_bytes(),
                synthetic_pdf,
            )
        page_map = deepcopy(json.loads(PAGE_MAP.read_text(encoding="utf-8")))
        page_map["pages"][0]["page_role"] = "corpus_data"
        with self.assertRaisesRegex(KP1979SourceError, "fixed V1 snapshot"):
            verify_kp1979_source(
                SOURCE_CONTRACT.read_bytes(),
                encode_json(page_map),
                synthetic_pdf,
            )

    def test_cli_mismatch_is_fixed_and_hides_input_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "PRIVATE-KP1979-NAME.pdf"
            source_path.write_bytes(b"%PDF-1.3\nsynthetic\n%%EOF\n")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main(["verify-kp1979-source", str(source_path)])
            self.assertEqual(1, result)
            self.assertEqual("", stdout.getvalue())
            self.assertEqual(
                "indusbench: KP1979 fixed source verification failed\n",
                stderr.getvalue(),
            )
            self.assertNotIn(source_path.name, stderr.getvalue())

    def test_exclusion_mask_removes_label_slots_without_claiming_detection(self) -> None:
        page_map = json.loads(PAGE_MAP.read_text(encoding="utf-8"))
        page = next(page for page in page_map["pages"] if page["pdf_page_number"] == 180)
        # Synthetic data are not source-valid; this unit checks only the
        # geometry-only page detector and exclusion boundary.
        width = 4880
        height = 7010
        row_bytes = width // 8
        payload = bytearray(row_bytes * height)
        for x0, x1 in ((2020, 2250), (4210, 4440)):
            for y in range(620, 6500, 164):
                for line_y0, line_y1 in ((y, y + 34), (y + 48, y + 82)):
                    for row_y in range(line_y0, line_y1):
                        offset = row_y * row_bytes
                        for x in range(x0, x1):
                            payload[offset + x // 8] |= 128 >> (x % 8)
        pbm = f"P4\n{width} {height}\n".encode("ascii") + bytes(payload)
        raw_bands = page["proposal_scan_bands"]
        scan_bands = (
            (
                int(raw_bands[0][0]),
                int(raw_bands[0][1]),
                int(raw_bands[0][2]),
                int(raw_bands[0][3]),
            ),
            (
                int(raw_bands[1][0]),
                int(raw_bands[1][1]),
                int(raw_bands[1][2]),
                int(raw_bands[1][3]),
            ),
        )
        raw = detect_two_column_label_lattice(
            pbm,
            width=width,
            height=height,
            scan_bands=scan_bands,
        )
        self.assertTrue(any(y < 5850 and y + 96 > 5000 for y in raw.lanes[1].candidate_y))

        result = detect_kp1979_page_layout(page, pbm)
        self.assertEqual("proposed", result.detection_status)
        forbidden = (3000, 5000, 4550, 5850)
        for lane in result.label_slot_lanes:
            for x0, y0, x1, y1 in lane:
                self.assertFalse(
                    x0 < forbidden[2]
                    and x1 > forbidden[0]
                    and y0 < forbidden[3]
                    and y1 > forbidden[1]
                )

    @unittest.skipUnless(
        os.environ.get("INDUSBENCH_KP1979_PDF"),
        "set INDUSBENCH_KP1979_PDF to the fixed official PDF",
    )
    def test_fixed_official_snapshot(self) -> None:
        pdf = Path(os.environ["INDUSBENCH_KP1979_PDF"]).read_bytes()
        summary = verify_kp1979_source(
            SOURCE_CONTRACT.read_bytes(),
            PAGE_MAP.read_bytes(),
            pdf,
        )
        self.assertTrue(summary["source_snapshot_match"])
        self.assertFalse(summary["decipherment"])

    @unittest.skipUnless(
        os.environ.get("INDUSBENCH_KP1979_PDF") and os.environ.get("INDUSBENCH_KP1979_PBM_DIR"),
        "set INDUSBENCH_KP1979_PDF and INDUSBENCH_KP1979_PBM_DIR",
    )
    def test_fixed_official_full_page_layout_audit(self) -> None:
        pdf = Path(os.environ["INDUSBENCH_KP1979_PDF"]).read_bytes()
        page_directory = Path(os.environ["INDUSBENCH_KP1979_PBM_DIR"])
        summary = audit_kp1979_layout(
            SOURCE_CONTRACT.read_bytes(),
            PAGE_MAP.read_bytes(),
            pdf,
            iter_real_page_bytes(page_directory),
        )
        self.assertTrue(summary["all_mapped_page_pixels_verified"])
        self.assertTrue(summary["selected_page_layout_status_gates_passed"])
        self.assertFalse(summary["layout_candidates_accepted"])
        self.assertFalse(summary["decipherment"])


if __name__ == "__main__":
    unittest.main()
