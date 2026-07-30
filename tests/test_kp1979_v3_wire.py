from __future__ import annotations

import ast
import base64
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import indusbench.kp1979_v3_sandbox as sandbox
from indusbench.kp1979_v3_protocol import (
    MAXIMUM_PREDICTION_HEIGHT,
    MAXIMUM_PREDICTIONS_PER_INVOCATION,
    RAW_P4_CONTRACT,
    SYNTHETIC_PAGE_HEIGHT,
    TARGET_ALGORITHM_ID,
    WORKER_ID,
    InputErrorCode,
    WorkerStatus,
)
from indusbench.kp1979_v3_wire import (
    MAX_WORKER_REQUEST_BYTES,
    MAX_WORKER_RESPONSE_BYTES,
    PREDICTION_KEYS,
    REQUEST_KEYS,
    RESPONSE_KEYS,
    KP1979V3WireError,
    KP1979V3WorkerInputError,
    Prediction,
    WorkerRequest,
    WorkerRequestEnvelope,
    WorkerResponse,
    decode_worker_request,
    decode_worker_request_envelope,
    decode_worker_response,
    encode_worker_request,
    encode_worker_response,
)

ROOT = Path(__file__).resolve().parents[1]
WIRE_PATH = ROOT / "src" / "indusbench" / "kp1979_v3_wire.py"
VALID_PBM = RAW_P4_CONTRACT.header + bytes(RAW_P4_CONTRACT.payload_byte_size)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _request(
    pbm: bytes = VALID_PBM,
    *,
    width: int = RAW_P4_CONTRACT.width,
    height: int = RAW_P4_CONTRACT.height,
    scan_bands: tuple[tuple[int, int, int, int], ...] = RAW_P4_CONTRACT.scan_bands,
) -> bytes:
    return encode_worker_request(
        pbm=pbm,
        width=width,
        height=height,
        scan_bands=scan_bands,
    )


def _response_value(
    *,
    status: object = "abstained",
    error_code: object = None,
    predictions: object = None,
) -> dict[str, object]:
    return {
        "algorithm_id": TARGET_ALGORITHM_ID,
        "error_code": error_code,
        "interface_version": WORKER_ID,
        "predictions": [] if predictions is None else predictions,
        "status": status,
    }


def _semantic_ooc_requests() -> tuple[tuple[bytes, InputErrorCode], ...]:
    wrong_extent = (
        (
            RAW_P4_CONTRACT.scan_bands[0][0],
            RAW_P4_CONTRACT.scan_bands[0][1],
            RAW_P4_CONTRACT.scan_bands[0][2] - 1,
            RAW_P4_CONTRACT.scan_bands[0][3],
        ),
        RAW_P4_CONTRACT.scan_bands[1],
    )
    overlapping = (
        RAW_P4_CONTRACT.scan_bands[0],
        (
            RAW_P4_CONTRACT.scan_bands[0][2] - 1,
            RAW_P4_CONTRACT.scan_bands[1][1],
            RAW_P4_CONTRACT.scan_bands[1][2],
            RAW_P4_CONTRACT.scan_bands[1][3],
        ),
    )
    return (
        (
            _request(VALID_PBM[:-1]),
            InputErrorCode.INVALID_PBM_PAYLOAD_SIZE,
        ),
        (
            _request(VALID_PBM + b"\x00"),
            InputErrorCode.INVALID_PBM_PAYLOAD_SIZE,
        ),
        (
            _request(b"P4 \n4880 7010\n" + bytes(RAW_P4_CONTRACT.payload_byte_size)),
            InputErrorCode.INVALID_PBM_HEADER,
        ),
        (
            _request(width=RAW_P4_CONTRACT.width - 1),
            InputErrorCode.INVALID_DIMENSIONS,
        ),
        (
            _request(scan_bands=wrong_extent),
            InputErrorCode.INVALID_SCAN_BANDS,
        ),
        (
            _request(scan_bands=overlapping),
            InputErrorCode.INVALID_SCAN_BANDS,
        ),
    )


class KP1979V3RequestWireTests(unittest.TestCase):
    def test_request_is_exact_answer_free_canonical_ascii_jsonl(self) -> None:
        line = _request()
        parsed = json.loads(line)
        self.assertEqual(REQUEST_KEYS, frozenset(parsed))
        self.assertEqual(WORKER_ID, parsed["interface_version"])
        self.assertEqual(_canonical(parsed), line)
        self.assertEqual(1, line.count(b"\n"))
        line.decode("ascii")
        sandbox._validate_answer_free_request(line)
        self.assertEqual(MAX_WORKER_REQUEST_BYTES, sandbox.MAX_REQUEST_BYTES)

    def test_request_round_trip_preserves_only_public_raster_geometry(self) -> None:
        line = _request()
        envelope = decode_worker_request_envelope(line)
        self.assertEqual(
            WorkerRequestEnvelope(
                pbm=VALID_PBM,
                width=RAW_P4_CONTRACT.width,
                height=RAW_P4_CONTRACT.height,
                scan_bands=RAW_P4_CONTRACT.scan_bands,
            ),
            envelope,
        )
        self.assertEqual(
            WorkerRequest(
                pbm=VALID_PBM,
                width=RAW_P4_CONTRACT.width,
                height=RAW_P4_CONTRACT.height,
                scan_bands=RAW_P4_CONTRACT.scan_bands,
            ),
            decode_worker_request(line),
        )

    def test_semantic_error_cases_reach_worker_and_map_to_closed_codes(self) -> None:
        for line, expected_code in _semantic_ooc_requests():
            with self.subTest(error_code=expected_code):
                sandbox._validate_answer_free_request(line)
                decode_worker_request_envelope(line)
                with self.assertRaises(KP1979V3WorkerInputError) as caught:
                    decode_worker_request(line)
                self.assertIs(expected_code, caught.exception.error_code)
                self.assertEqual("kp1979-v3 worker input rejected", str(caught.exception))
                self.assertFalse(hasattr(caught.exception, "path"))
                self.assertFalse(hasattr(caught.exception, "detail"))

    def test_each_semantic_error_request_reaches_sandbox_invoke_once(self) -> None:
        requests = tuple(line for line, _ in _semantic_ooc_requests())
        reached: list[bytes] = []
        sentinel = cast(Any, object())

        def record_invoke(request: bytes) -> object:
            reached.append(request)
            return sentinel

        invoker = object.__new__(sandbox.SandboxedWorkerInvoker)
        with (
            patch.object(
                sandbox.SandboxedWorkerInvoker,
                "_source_artifact_is_unchanged",
                return_value=True,
            ) as artifact_check,
            patch.object(
                sandbox.SandboxedWorkerInvoker,
                "_invoke",
                side_effect=record_invoke,
            ) as invoke,
        ):
            for request in requests:
                self.assertIs(sentinel, invoker(request))

        self.assertEqual(requests, tuple(reached))
        self.assertEqual(6, artifact_check.call_count)
        self.assertEqual(6, invoke.call_count)

    def test_worker_semantic_error_precedence_is_header_dimensions_size_bands(self) -> None:
        noncanonical_header = b"P4 \n4880 7010\n" + bytes(RAW_P4_CONTRACT.payload_byte_size)
        line = _request(
            noncanonical_header,
            width=RAW_P4_CONTRACT.width - 1,
            scan_bands=(RAW_P4_CONTRACT.scan_bands[0],),
        )
        sandbox._validate_answer_free_request(line)
        with self.assertRaises(KP1979V3WorkerInputError) as caught:
            decode_worker_request(line)
        self.assertIs(InputErrorCode.INVALID_PBM_HEADER, caught.exception.error_code)

    def test_outer_envelope_rejects_duplicate_extra_and_noncanonical_json(self) -> None:
        tiny = {
            "height": RAW_P4_CONTRACT.height,
            "interface_version": WORKER_ID,
            "pbm_base64": base64.b64encode(b"P4\n").decode("ascii"),
            "scan_bands": [list(band) for band in RAW_P4_CONTRACT.scan_bands],
            "width": RAW_P4_CONTRACT.width,
        }
        malformed = (
            b'{"height":1,"height":1}\n',
            _canonical({**tiny, "case_id": "answer-bearing"}),
            _canonical(tiny).replace(b'":', b'": ', 1),
            _canonical(tiny)[:-1],
            _canonical(tiny) + b"{}\n",
            b"\xff\n",
        )
        for line in malformed:
            with self.subTest(line_prefix=line[:24]):
                with self.assertRaises(KP1979V3WireError) as caught:
                    decode_worker_request_envelope(line)
                self.assertEqual("kp1979-v3 wire contract rejected", str(caught.exception))

    def test_deep_nested_json_never_leaks_a_recursion_error(self) -> None:
        depth = 2_000
        line = b'{"x":' + (b"[" * depth) + b"0" + (b"]" * depth) + b"}\n"
        self.assertLess(len(line), MAX_WORKER_REQUEST_BYTES)
        with self.assertRaises(KP1979V3WireError):
            decode_worker_request_envelope(line)

    def test_outer_envelope_rejects_noncanonical_base64_bool_and_malformed_bands(self) -> None:
        base = {
            "height": RAW_P4_CONTRACT.height,
            "interface_version": WORKER_ID,
            "pbm_base64": base64.b64encode(b"P4\n").decode("ascii"),
            "scan_bands": [list(band) for band in RAW_P4_CONTRACT.scan_bands],
            "width": RAW_P4_CONTRACT.width,
        }
        bad_values: tuple[dict[str, object], ...] = (
            {**base, "pbm_base64": "UDQK="},
            {**base, "pbm_base64": "not-base64"},
            {**base, "width": True},
            {**base, "height": False},
            {**base, "scan_bands": [[0, 0, 1, True]]},
            {**base, "scan_bands": [[0, 0, 1]]},
            {**base, "scan_bands": "not-a-list"},
            {**base, "scan_bands": []},
        )
        for value in bad_values:
            with self.subTest(value=value), self.assertRaises(KP1979V3WireError):
                decode_worker_request_envelope(_canonical(value))

    def test_encoder_rejects_nonexact_types_and_oversize_without_partial_output(self) -> None:
        bad_calls: tuple[dict[str, Any], ...] = (
            {
                "pbm": cast(Any, bytearray(b"P4\n")),
                "width": RAW_P4_CONTRACT.width,
                "height": RAW_P4_CONTRACT.height,
                "scan_bands": RAW_P4_CONTRACT.scan_bands,
            },
            {
                "pbm": b"P4\n",
                "width": cast(Any, True),
                "height": RAW_P4_CONTRACT.height,
                "scan_bands": RAW_P4_CONTRACT.scan_bands,
            },
            {
                "pbm": b"P4\n",
                "width": RAW_P4_CONTRACT.width,
                "height": RAW_P4_CONTRACT.height,
                "scan_bands": cast(Any, [list(RAW_P4_CONTRACT.scan_bands[0])]),
            },
            {
                "pbm": b"x" * (((MAX_WORKER_REQUEST_BYTES * 3) // 4) + 1),
                "width": RAW_P4_CONTRACT.width,
                "height": RAW_P4_CONTRACT.height,
                "scan_bands": RAW_P4_CONTRACT.scan_bands,
            },
        )
        for arguments in bad_calls:
            with (
                self.subTest(arguments=tuple(arguments)),
                self.assertRaises(KP1979V3WireError),
            ):
                encode_worker_request(**arguments)

    def test_request_dataclasses_are_frozen(self) -> None:
        envelope = decode_worker_request_envelope(_request())
        with self.assertRaises(FrozenInstanceError):
            envelope.width = 1  # type: ignore[misc]


class KP1979V3ResponseWireTests(unittest.TestCase):
    def test_worker_status_vocabulary_is_closed(self) -> None:
        self.assertEqual(
            ("proposed", "abstained", "rejected"),
            tuple(status.value for status in WorkerStatus),
        )

    def test_proposed_response_round_trip_allows_bounded_non96_heights(self) -> None:
        response = WorkerResponse(
            status=WorkerStatus.PROPOSED,
            error_code=None,
            predictions=(
                Prediction(lane=0, y0=0, y1=1),
                Prediction(
                    lane=1,
                    y0=SYNTHETIC_PAGE_HEIGHT - MAXIMUM_PREDICTION_HEIGHT,
                    y1=SYNTHETIC_PAGE_HEIGHT,
                ),
            ),
        )
        line = encode_worker_response(response)
        parsed = json.loads(line)
        self.assertEqual(RESPONSE_KEYS, frozenset(parsed))
        self.assertEqual(PREDICTION_KEYS, frozenset(parsed["predictions"][0]))
        self.assertEqual(TARGET_ALGORITHM_ID, parsed["algorithm_id"])
        self.assertEqual(WORKER_ID, parsed["interface_version"])
        self.assertEqual(_canonical(parsed), line)
        self.assertEqual(response, decode_worker_response(line))

    def test_abstained_and_each_closed_rejection_round_trip(self) -> None:
        abstained = WorkerResponse(
            status=WorkerStatus.ABSTAINED,
            error_code=None,
            predictions=(),
        )
        self.assertEqual(abstained, decode_worker_response(encode_worker_response(abstained)))
        for error_code in InputErrorCode:
            rejected = WorkerResponse(
                status=WorkerStatus.REJECTED,
                error_code=error_code,
                predictions=(),
            )
            with self.subTest(error_code=error_code):
                self.assertEqual(
                    rejected,
                    decode_worker_response(encode_worker_response(rejected)),
                )

    def test_status_payload_combinations_are_fail_closed(self) -> None:
        prediction = Prediction(lane=0, y0=100, y1=196)
        invalid = (
            (WorkerStatus.PROPOSED, None, ()),
            (WorkerStatus.PROPOSED, InputErrorCode.INVALID_DIMENSIONS, (prediction,)),
            (WorkerStatus.ABSTAINED, None, (prediction,)),
            (WorkerStatus.ABSTAINED, InputErrorCode.INVALID_DIMENSIONS, ()),
            (WorkerStatus.REJECTED, None, ()),
            (WorkerStatus.REJECTED, InputErrorCode.INVALID_DIMENSIONS, (prediction,)),
        )
        for status, error_code, predictions in invalid:
            with (
                self.subTest(status=status, error_code=error_code),
                self.assertRaises(KP1979V3WireError),
            ):
                WorkerResponse(
                    status=status,
                    error_code=error_code,
                    predictions=predictions,
                )

    def test_prediction_types_lanes_coordinates_and_heights_are_fail_closed(self) -> None:
        invalid = (
            (cast(Any, True), 0, 1),
            (-1, 0, 1),
            (2, 0, 1),
            (0, cast(Any, True), 1),
            (0, -1, 1),
            (0, 1, 1),
            (0, 2, 1),
            (0, 0, MAXIMUM_PREDICTION_HEIGHT + 1),
            (0, SYNTHETIC_PAGE_HEIGHT, SYNTHETIC_PAGE_HEIGHT + 1),
        )
        for lane, y0, y1 in invalid:
            with (
                self.subTest(lane=lane, y0=y0, y1=y1),
                self.assertRaises(KP1979V3WireError),
            ):
                Prediction(lane=lane, y0=y0, y1=y1)

    def test_prediction_count_sort_order_and_uniqueness_are_fail_closed(self) -> None:
        too_many = tuple(
            Prediction(lane=0, y0=index, y1=index + 1)
            for index in range(MAXIMUM_PREDICTIONS_PER_INVOCATION + 1)
        )
        with self.assertRaises(KP1979V3WireError):
            WorkerResponse(
                status=WorkerStatus.PROPOSED,
                error_code=None,
                predictions=too_many,
            )
        first = Prediction(lane=0, y0=10, y1=20)
        second = Prediction(lane=1, y0=10, y1=20)
        for predictions in ((second, first), (first, first)):
            with (
                self.subTest(predictions=predictions),
                self.assertRaises(KP1979V3WireError),
            ):
                WorkerResponse(
                    status=WorkerStatus.PROPOSED,
                    error_code=None,
                    predictions=predictions,
                )

    def test_response_rejects_duplicate_extra_multiline_and_noncanonical_json(self) -> None:
        base = _response_value()
        malformed = (
            b'{"status":"abstained","status":"abstained"}\n',
            _canonical({**base, "detail": "must-not-cross"}),
            _canonical(base).replace(b'":', b'": ', 1),
            _canonical(base)[:-1],
            _canonical(base) + b"{}\n",
            b"\xff\n",
            b"x" * (MAX_WORKER_RESPONSE_BYTES + 1),
        )
        for line in malformed:
            with (
                self.subTest(line_prefix=line[:24]),
                self.assertRaises(KP1979V3WireError),
            ):
                decode_worker_response(line)

    def test_response_rejects_identity_status_error_and_prediction_schema_drift(self) -> None:
        base = _response_value()
        invalid = (
            {**base, "algorithm_id": "different"},
            {**base, "interface_version": "different"},
            {**base, "status": "accepted"},
            {**base, "status": True},
            {**base, "error_code": "different"},
            {**base, "predictions": {}},
            {
                **base,
                "status": "proposed",
                "predictions": [{"lane": 0, "y0": 0, "y1": 1, "score": 1}],
            },
            {
                **base,
                "status": "proposed",
                "predictions": [{"lane": True, "y0": 0, "y1": 1}],
            },
            {
                **base,
                "status": "proposed",
                "predictions": [{"lane": 0, "y0": 0, "y1": 129}],
            },
            {
                **base,
                "status": "proposed",
                "predictions": [
                    {"lane": 1, "y0": 0, "y1": 1},
                    {"lane": 0, "y0": 0, "y1": 1},
                ],
            },
            {
                **base,
                "status": "proposed",
                "predictions": [
                    {"lane": 0, "y0": 0, "y1": 1},
                    {"lane": 0, "y0": 0, "y1": 1},
                ],
            },
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(KP1979V3WireError):
                decode_worker_response(_canonical(value))

    def test_nested_duplicate_prediction_key_is_rejected(self) -> None:
        line = (
            b'{"algorithm_id":"two-column-glyph-lattice-v3","error_code":null,'
            b'"interface_version":"kp1979-label-detector-v3-worker-v1",'
            b'"predictions":[{"lane":0,"lane":0,"y0":0,"y1":1}],'
            b'"status":"proposed"}\n'
        )
        with self.assertRaises(KP1979V3WireError):
            decode_worker_response(line)

    def test_response_dataclasses_require_exact_closed_types(self) -> None:
        with self.assertRaises(KP1979V3WireError):
            WorkerResponse(
                status=cast(Any, "abstained"),
                error_code=None,
                predictions=(),
            )
        with self.assertRaises(KP1979V3WireError):
            WorkerResponse(
                status=WorkerStatus.ABSTAINED,
                error_code=None,
                predictions=cast(Any, []),
            )


class KP1979V3WireBoundaryTests(unittest.TestCase):
    def test_wire_has_no_sandbox_dependency_and_only_closed_request_keys(self) -> None:
        source = WIRE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        self.assertNotIn("indusbench.kp1979_v3_sandbox", imported_modules)
        self.assertNotIn("kp1979_v3_sandbox", source)
        self.assertNotIn("v2", source.lower())
        self.assertEqual(
            {
                "interface_version",
                "pbm_base64",
                "width",
                "height",
                "scan_bands",
            },
            REQUEST_KEYS,
        )

    def test_wire_errors_are_path_and_detail_free(self) -> None:
        with self.assertRaises(KP1979V3WireError) as caught:
            decode_worker_response(b"")
        self.assertEqual("kp1979-v3 wire contract rejected", str(caught.exception))
        self.assertFalse(hasattr(caught.exception, "path"))
        self.assertFalse(hasattr(caught.exception, "detail"))


if __name__ == "__main__":
    unittest.main()
