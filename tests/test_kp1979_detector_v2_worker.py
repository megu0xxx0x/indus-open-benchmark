from __future__ import annotations

import base64
import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from typing import Any

from indusbench.kp1979_detector_v2_worker import (
    INTERFACE_VERSION,
    MAX_REQUEST_BYTES,
)
from indusbench.kp1979_synthetic_control import (
    SYNTHETIC_PAGE_HEIGHT,
    SYNTHETIC_PAGE_WIDTH,
    SYNTHETIC_SCAN_BANDS,
    build_synthetic_fixture,
)
from indusbench.printed_concordance_layout_v2 import DETECTOR_ALGORITHM_ID

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RESPONSE_KEYS = {
    "algorithm_id",
    "interface_version",
    "status",
    "abstention_codes",
    "predictions",
}


def _request(pbm_bytes: bytes) -> bytes:
    return json.dumps(
        {
            "interface_version": INTERFACE_VERSION,
            "pbm_base64": base64.b64encode(pbm_bytes).decode("ascii"),
            "width": SYNTHETIC_PAGE_WIDTH,
            "height": SYNTHETIC_PAGE_HEIGHT,
            "scan_bands": SYNTHETIC_SCAN_BANDS,
        },
        separators=(",", ":"),
    ).encode("ascii")


def _run_worker(raw_request: bytes) -> tuple[int, bytes, bytes, dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, "-m", "indusbench.kp1979_detector_v2_worker"],
        cwd=ROOT,
        input=raw_request,
        capture_output=True,
        check=False,
        timeout=45,
    )
    response: dict[str, Any] = json.loads(completed.stdout)
    return completed.returncode, completed.stdout, completed.stderr, response


class KP1979DetectorV2WorkerTests(unittest.TestCase):
    def assertClosedAbstention(self, raw_request: bytes) -> None:
        return_code, _, standard_error, response = _run_worker(raw_request)
        self.assertEqual(0, return_code)
        self.assertEqual(b"", standard_error)
        self.assertEqual(EXPECTED_RESPONSE_KEYS, set(response))
        self.assertEqual(DETECTOR_ALGORITHM_ID, response["algorithm_id"])
        self.assertEqual(INTERFACE_VERSION, response["interface_version"])
        self.assertEqual("abstained", response["status"])
        self.assertEqual(["invalid_request"], response["abstention_codes"])
        self.assertEqual([], response["predictions"])

    def test_valid_positive_request_emits_only_closed_sorted_predictions(self) -> None:
        fixture = build_synthetic_fixture("positive_thin_strokes")
        return_code, standard_output, standard_error, response = _run_worker(
            _request(fixture.pbm_bytes)
        )
        self.assertEqual(0, return_code)
        self.assertEqual(b"", standard_error)
        self.assertTrue(standard_output.endswith(b"\n"))
        self.assertEqual(EXPECTED_RESPONSE_KEYS, set(response))
        self.assertEqual(DETECTOR_ALGORITHM_ID, response["algorithm_id"])
        self.assertEqual(INTERFACE_VERSION, response["interface_version"])
        self.assertEqual("proposed", response["status"])
        self.assertEqual([], response["abstention_codes"])
        predictions = response["predictions"]
        self.assertIsInstance(predictions, list)
        ordering = [
            (prediction["lane"], prediction["y0"], prediction["y1"]) for prediction in predictions
        ]
        self.assertEqual(ordering, sorted(set(ordering)))
        self.assertTrue(
            all(
                set(prediction) == {"lane", "y0", "y1"}
                and prediction["y1"] - prediction["y0"] == 96
                for prediction in predictions
            )
        )

    def test_detector_abstention_never_leaks_lane_candidates(self) -> None:
        fixture = build_synthetic_fixture("negative_periodic_non_label_bands")
        return_code, _, standard_error, response = _run_worker(_request(fixture.pbm_bytes))
        self.assertEqual(0, return_code)
        self.assertEqual(b"", standard_error)
        self.assertEqual("abstained", response["status"])
        self.assertEqual([], response["predictions"])
        codes = response["abstention_codes"]
        self.assertEqual(codes, sorted(set(codes)))

    def test_malformed_closed_contract_cases_fail_without_stderr(self) -> None:
        base_request = {
            "interface_version": INTERFACE_VERSION,
            "pbm_base64": "",
            "width": SYNTHETIC_PAGE_WIDTH,
            "height": SYNTHETIC_PAGE_HEIGHT,
            "scan_bands": SYNTHETIC_SCAN_BANDS,
        }
        malformed: list[bytes] = [
            b"{}",
            b'{"interface_version":"x","interface_version":"x"}',
            b"{}\n{}",
            json.dumps({**base_request, "unknown": 1}).encode("ascii"),
            json.dumps({**base_request, "width": True}).encode("ascii"),
            json.dumps(
                {
                    **base_request,
                    "scan_bands": [
                        SYNTHETIC_SCAN_BANDS[1],
                        SYNTHETIC_SCAN_BANDS[0],
                    ],
                }
            ).encode("ascii"),
            json.dumps(
                {
                    **base_request,
                    "scan_bands": [
                        (2056, 0, 2316, 6600),
                        SYNTHETIC_SCAN_BANDS[1],
                    ],
                }
            ).encode("ascii"),
            json.dumps({**base_request, "pbm_base64": "!!!!"}).encode("ascii"),
            json.dumps({"deep": [[[[[0]]]]]}).encode("ascii"),
        ]
        for raw_request in malformed:
            with self.subTest(raw_request=raw_request[:80]):
                self.assertClosedAbstention(raw_request)

    def test_canonical_size_invalid_encoding_and_range_fail_closed(self) -> None:
        fixture = build_synthetic_fixture("negative_blank")
        canonical: dict[str, Any] = json.loads(_request(fixture.pbm_bytes))
        encoded_pbm = canonical["pbm_base64"]
        self.assertIsInstance(encoded_pbm, str)
        self.assertClosedAbstention(
            json.dumps(
                {**canonical, "pbm_base64": "!" + encoded_pbm[1:]},
                separators=(",", ":"),
            ).encode("ascii")
        )
        self.assertClosedAbstention(
            json.dumps(
                {
                    **canonical,
                    "scan_bands": [
                        (2056, 0, 2316, 6600),
                        SYNTHETIC_SCAN_BANDS[1],
                    ],
                },
                separators=(",", ":"),
            ).encode("ascii")
        )

    def test_oversize_request_fails_closed_without_reading_another_request(self) -> None:
        self.assertClosedAbstention(b" " * (MAX_REQUEST_BYTES + 1))

    def test_console_entrypoint_is_packaged_by_the_detector_commit(self) -> None:
        configuration = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            "indusbench.kp1979_detector_v2_worker:main",
            configuration["project"]["scripts"]["indusbench-kp1979-label-detector-v2"],
        )


if __name__ == "__main__":
    unittest.main()
