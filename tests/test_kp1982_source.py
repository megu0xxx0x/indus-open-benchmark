from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from indusbench.cli import main
from indusbench.io import encode_json
from indusbench.kp1982 import (
    KP1982SourceError,
    verify_canonical_pbm,
    verify_kp1982_source,
    verify_snapshot_identity,
)
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "registry" / "kp1982_batch0.json"
SCHEMA = ROOT / "schemas" / "kp1982-batch0-source.schema.json"
LAYOUT_SEED = ROOT / "registry" / "kp1982_batch0_layout_seed.json"
LAYOUT_SCHEMA = ROOT / "schemas" / "kp1982-layout-seed.schema.json"


class KP1982SourceTests(unittest.TestCase):
    def test_checked_in_contract_matches_closed_schema(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual([], validate_schema_instance(contract, SCHEMA))

    def test_layout_seed_is_bound_bounded_and_explicitly_provisional(self) -> None:
        seed = json.loads(LAYOUT_SEED.read_text(encoding="utf-8"))
        self.assertEqual([], validate_schema_instance(seed, LAYOUT_SCHEMA))
        contract_bytes = CONTRACT.read_bytes()
        self.assertEqual(
            "sha256:" + hashlib.sha256(contract_bytes).hexdigest(),
            seed["source_contract"]["sha256"],
        )
        self.assertEqual(len(contract_bytes), seed["source_contract"]["byte_size"])
        self.assertEqual(
            [(20, 19, "20"), (21, 20, "21")],
            [
                (
                    page["pdf_page_number"],
                    page["page_index"],
                    page["printed_page_label"],
                )
                for page in seed["pages"]
            ],
        )
        for page in seed["pages"]:
            self.assertEqual(sorted(page["lane_edges_x"]), page["lane_edges_x"])
            self.assertEqual(list(range(10)), [lane["lane_index"] for lane in page["lanes"]])
            for lane_index, guide in enumerate(page["internal_guide_x"]):
                self.assertLess(page["lane_edges_x"][lane_index], guide)
                self.assertLess(guide, page["lane_edges_x"][lane_index + 1])
            for lane in page["lanes"]:
                model = lane["row_center_model"]
                last_center = model["intercept_y"] + model["pitch_y"] * 34
                self.assertGreater(last_center, 0)
                self.assertLess(last_center, 6705)
                self.assertLessEqual(lane["provisional_occupied_row_slots"], 35)
        self.assertTrue(all(value is False for value in seed["assurances"].values()))

    def test_generic_snapshot_identity_uses_exact_size_and_digest(self) -> None:
        source_bytes = b"%PDF-1.3\nsynthetic\n%%EOF\n"
        expected = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
        verify_snapshot_identity(
            source_bytes,
            expected_sha256=expected,
            expected_byte_size=len(source_bytes),
        )
        with self.assertRaisesRegex(KP1982SourceError, "byte size"):
            verify_snapshot_identity(
                source_bytes,
                expected_sha256=expected,
                expected_byte_size=len(source_bytes) + 1,
            )
        with self.assertRaisesRegex(KP1982SourceError, "digest"):
            verify_snapshot_identity(
                source_bytes,
                expected_sha256=f"sha256:{'0' * 64}",
                expected_byte_size=len(source_bytes),
            )

    def test_canonical_pbm_binds_header_payload_and_both_digests(self) -> None:
        pbm_bytes = b"P4\n8 1\n\x80"
        pbm_sha256 = "sha256:" + hashlib.sha256(pbm_bytes).hexdigest()
        pixel_sha256 = "sha256:" + hashlib.sha256(b"\x80").hexdigest()
        verify_canonical_pbm(
            pbm_bytes,
            width=8,
            height=1,
            expected_pbm_sha256=pbm_sha256,
            expected_pixel_sha256=pixel_sha256,
        )
        with self.assertRaisesRegex(KP1982SourceError, "canonical PBM digest"):
            verify_canonical_pbm(
                b"P4\n8 1\n\x40",
                width=8,
                height=1,
                expected_pbm_sha256=pbm_sha256,
                expected_pixel_sha256=pixel_sha256,
            )

    def test_contract_cannot_be_rewritten_to_authorize_other_bytes(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        synthetic = b"%PDF-1.3\nsynthetic\n%%EOF\n"
        contract["source"]["byte_size"] = len(synthetic)
        contract["source"]["sha256"] = "sha256:" + hashlib.sha256(synthetic).hexdigest()
        with self.assertRaisesRegex(KP1982SourceError, "schema invalid"):
            verify_kp1982_source(encode_json(contract), synthetic)

    def test_cli_mismatch_is_fixed_and_does_not_disclose_the_input_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "PRIVATE-SOURCE-NAME.pdf"
            source_path.write_bytes(b"%PDF-1.3\nsynthetic\n%%EOF\n")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main(["verify-kp1982-source", str(source_path)])
            self.assertEqual(1, result)
            self.assertEqual("", stdout.getvalue())
            self.assertEqual(
                "indusbench: KP1982 fixed source verification failed\n",
                stderr.getvalue(),
            )
            self.assertNotIn(source_path.name, stderr.getvalue())

    @unittest.skipUnless(
        os.environ.get("INDUSBENCH_KP1982_PDF"),
        "set INDUSBENCH_KP1982_PDF to the fixed official PDF",
    )
    def test_fixed_official_snapshot(self) -> None:
        source_path = Path(os.environ["INDUSBENCH_KP1982_PDF"])
        page_paths = [
            os.environ.get("INDUSBENCH_KP1982_PAGE20_PBM"),
            os.environ.get("INDUSBENCH_KP1982_PAGE21_PBM"),
        ]
        page_bytes = (
            [Path(path).read_bytes() for path in page_paths if path is not None]
            if all(page_paths)
            else None
        )
        summary = verify_kp1982_source(
            CONTRACT.read_bytes(),
            source_path.read_bytes(),
            page_pbm_bytes=page_bytes,
        )
        self.assertTrue(summary["source_snapshot_match"])
        self.assertEqual(all(page_paths), summary["target_page_pixels_verified"])
        self.assertFalse(summary["decipherment"])


if __name__ == "__main__":
    unittest.main()
