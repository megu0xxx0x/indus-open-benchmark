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
from indusbench.kp1982_layout import (
    EXPECTED_LAYOUT_PROPOSAL_BYTE_SIZE,
    EXPECTED_LAYOUT_PROPOSAL_SHA256,
    KP1982LayoutError,
    build_layout_proposal,
    crop_canonical_pbm,
    verify_layout_proposal_bytes,
)
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT = ROOT / "registry" / "kp1982_batch0.json"
LAYOUT_SEED = ROOT / "registry" / "kp1982_batch0_layout_seed.json"
PROPOSAL_SCHEMA = ROOT / "schemas" / "kp1982-layout-proposal.schema.json"


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


class KP1982LayoutTests(unittest.TestCase):
    def test_unaligned_crop_is_canonical_and_zero_padded(self) -> None:
        page = b"P4\n8 2\n" + bytes([0b10101010, 0b01010101])
        crop = crop_canonical_pbm(
            page,
            page_width=8,
            page_height=2,
            bbox=[2, 0, 6, 2],
        )
        self.assertEqual(b"P4\n4 2\n" + bytes([0b10100000, 0b01010000]), crop)

    def test_optimized_crop_matches_bit_reference(self) -> None:
        for width in range(1, 18):
            height = 4
            row_bytes = (width + 7) // 8
            payload = bytes(
                (width * 17 + index * 73 + 11) % 256 for index in range(row_bytes * height)
            )
            page = f"P4\n{width} {height}\n".encode("ascii") + payload
            for x0 in range(width):
                for x1 in range(x0 + 1, width + 1):
                    bbox = [x0, 1, x1, 4]
                    expected_width = x1 - x0
                    expected_row_bytes = (expected_width + 7) // 8
                    expected_payload = bytearray(expected_row_bytes * 3)
                    for crop_y, source_y in enumerate(range(1, 4)):
                        for crop_x, source_x in enumerate(range(x0, x1)):
                            source_byte = payload[source_y * row_bytes + source_x // 8]
                            if source_byte & (1 << (7 - source_x % 8)):
                                expected_payload[crop_y * expected_row_bytes + crop_x // 8] |= (
                                    1 << (7 - crop_x % 8)
                                )
                    expected = f"P4\n{expected_width} 3\n".encode("ascii") + bytes(expected_payload)
                    self.assertEqual(
                        expected,
                        crop_canonical_pbm(
                            page,
                            page_width=width,
                            page_height=height,
                            bbox=bbox,
                        ),
                    )

    @unittest.skipUnless(
        all(
            os.environ.get(name)
            for name in (
                "INDUSBENCH_KP1982_PAGE20_PBM",
                "INDUSBENCH_KP1982_PAGE21_PBM",
            )
        ),
        "set both INDUSBENCH_KP1982_PAGE*_PBM paths",
    )
    def test_fixed_pages_build_deterministic_proposal(self) -> None:
        page_bytes = [
            Path(os.environ["INDUSBENCH_KP1982_PAGE20_PBM"]).read_bytes(),
            Path(os.environ["INDUSBENCH_KP1982_PAGE21_PBM"]).read_bytes(),
        ]
        first = build_layout_proposal(
            SOURCE_CONTRACT.read_bytes(),
            LAYOUT_SEED.read_bytes(),
            page_bytes,
        )
        second = build_layout_proposal(
            SOURCE_CONTRACT.read_bytes(),
            LAYOUT_SEED.read_bytes(),
            page_bytes,
        )
        self.assertEqual(first, second)
        canonical = encode_json(first)
        self.assertEqual(EXPECTED_LAYOUT_PROPOSAL_BYTE_SIZE, len(canonical))
        self.assertEqual(
            EXPECTED_LAYOUT_PROPOSAL_SHA256,
            "sha256:" + hashlib.sha256(canonical).hexdigest(),
        )
        verification = verify_layout_proposal_bytes(
            SOURCE_CONTRACT.read_bytes(),
            LAYOUT_SEED.read_bytes(),
            page_bytes,
            encode_json(first),
        )
        self.assertTrue(verification["crop_bytes_recomputed"])
        self.assertTrue(verification["canonical_manifest_bytes_verified"])
        self.assertFalse(verification["private_storage_verified"])
        self.assertFalse(verification["human_double_review_complete"])
        mutations = []
        tampered_hash = deepcopy(first)
        tampered_hash["cells"][0]["cell_crop_sha256"] = f"sha256:{'0' * 64}"
        mutations.append(tampered_hash)
        tampered_id = deepcopy(first)
        tampered_id["cells"][0]["cell_id"] = tampered_id["cells"][1]["cell_id"]
        mutations.append(tampered_id)
        tampered_bbox = deepcopy(first)
        tampered_bbox["cells"][0]["cell_bbox"] = [4888, 6705, 0, 0]
        mutations.append(tampered_bbox)
        tampered_occupancy = deepcopy(first)
        tampered_occupancy["cells"][0]["occupancy_proposal"] = "proposed_blank"
        mutations.append(tampered_occupancy)
        for tampered in mutations:
            with self.assertRaisesRegex(KP1982LayoutError, "pixel recomputation"):
                verify_layout_proposal_bytes(
                    SOURCE_CONTRACT.read_bytes(),
                    LAYOUT_SEED.read_bytes(),
                    page_bytes,
                    encode_json(tampered),
                )
        noncanonical = encode_json(first).replace(b"{", b"{ ", 1)
        with self.assertRaisesRegex(KP1982LayoutError, "canonical pixel recomputation"):
            verify_layout_proposal_bytes(
                SOURCE_CONTRACT.read_bytes(),
                LAYOUT_SEED.read_bytes(),
                page_bytes,
                noncanonical,
            )
        self.assertEqual([], validate_schema_instance(first, PROPOSAL_SCHEMA))
        self.assertEqual(700, len(first["cells"]))
        self.assertRegex(first["cells"][0]["cell_crop_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(first["cells"][0]["context_crop_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(first["assurances"]["human_double_review_complete"])
        self.assertFalse(first["assurances"]["decipherment"])

    def test_cli_rejects_wrong_pixels_without_disclosing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            page20 = temporary / "PRIVATE-PAGE-20.pbm"
            page21 = temporary / "PRIVATE-PAGE-21.pbm"
            output = temporary / "PRIVATE-PROPOSAL.json"
            page20.write_bytes(b"P4\n8 1\n\x80")
            page21.write_bytes(b"P4\n8 1\n\x80")
            result, stdout, stderr = run_cli(
                [
                    "propose-kp1982-layout",
                    str(page20),
                    str(page21),
                    str(output),
                ]
            )
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1982 layout proposal generation failed\n",
                stderr,
            )
            self.assertNotIn(page20.name, stderr)
            self.assertNotIn(page21.name, stderr)
            self.assertNotIn(output.name, stderr)
            self.assertFalse(output.exists())

    def test_layout_seed_geometry_cannot_be_rewritten(self) -> None:
        seed = json.loads(LAYOUT_SEED.read_text(encoding="utf-8"))
        rewritten = deepcopy(seed)
        rewritten["pages"][0]["lane_edges_x"][0] += 1
        with self.assertRaisesRegex(KP1982LayoutError, "fixed snapshot"):
            build_layout_proposal(
                SOURCE_CONTRACT.read_bytes(),
                encode_json(rewritten),
                [b"", b""],
            )

    @unittest.skipUnless(
        all(
            os.environ.get(name)
            for name in (
                "INDUSBENCH_KP1982_PAGE20_PBM",
                "INDUSBENCH_KP1982_PAGE21_PBM",
            )
        ),
        "set both INDUSBENCH_KP1982_PAGE*_PBM paths",
    )
    def test_cli_writes_private_proposal_without_claiming_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            temporary.chmod(0o700)
            output = temporary / "proposal.json"
            result, stdout, stderr = run_cli(
                [
                    "propose-kp1982-layout",
                    os.environ["INDUSBENCH_KP1982_PAGE20_PBM"],
                    os.environ["INDUSBENCH_KP1982_PAGE21_PBM"],
                    str(output),
                ]
            )
            self.assertEqual(0, result, stderr)
            summary = json.loads(stdout)
            self.assertTrue(summary["written"])
            self.assertFalse(summary["counts_disclosed"])
            self.assertFalse(summary["layout_accepted"])
            self.assertFalse(summary["identifiers_transcribed"])
            self.assertFalse(summary["decipherment"])
            proposal = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual([], validate_schema_instance(proposal, PROPOSAL_SCHEMA))
            self.assertEqual(0o600, output.stat().st_mode & 0o777)
            result, stdout, stderr = run_cli(
                [
                    "verify-kp1982-layout",
                    os.environ["INDUSBENCH_KP1982_PAGE20_PBM"],
                    os.environ["INDUSBENCH_KP1982_PAGE21_PBM"],
                    str(output),
                ]
            )
            self.assertEqual(0, result, stderr)
            verification = json.loads(stdout)
            self.assertTrue(verification["crop_bytes_recomputed"])
            self.assertTrue(verification["private_storage_verified"])
            self.assertFalse(verification["layout_accepted"])
            output.chmod(0o644)
            result, stdout, stderr = run_cli(
                [
                    "verify-kp1982-layout",
                    os.environ["INDUSBENCH_KP1982_PAGE20_PBM"],
                    os.environ["INDUSBENCH_KP1982_PAGE21_PBM"],
                    str(output),
                ]
            )
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1982 layout proposal verification failed\n",
                stderr,
            )
            self.assertNotIn(output.name, stderr)


if __name__ == "__main__":
    unittest.main()
