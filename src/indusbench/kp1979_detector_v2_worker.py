"""Closed one-request worker for the generic KP1979 V2 detector interface."""

from __future__ import annotations

import base64
import json
import sys
from typing import Final

from indusbench.printed_concordance_layout_v2 import (
    DETECTOR_ALGORITHM_ID,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    ROW_WINDOW_HEIGHT,
    TwoColumnLayoutProposalV2,
    detect_two_column_label_lattice_v2,
)

INTERFACE_VERSION: Final = "kp1979-label-detector-v2-worker-v1"
MAX_PBM_BYTES: Final = 4_276_113
MAX_BASE64_CHARS: Final = ((MAX_PBM_BYTES + 2) // 3) * 4
MAX_REQUEST_BYTES: Final = 6_000_000
MAX_JSON_DEPTH: Final = 4

_REQUEST_KEYS: Final = frozenset(
    {
        "interface_version",
        "pbm_base64",
        "width",
        "height",
        "scan_bands",
    }
)
_RESPONSE_KEYS: Final = frozenset(
    {
        "algorithm_id",
        "interface_version",
        "status",
        "abstention_codes",
        "predictions",
    }
)
_PREDICTION_KEYS: Final = frozenset({"lane", "y0", "y1"})


class DetectorWorkerRequestError(ValueError):
    """Raised internally when a worker request or response is not closed."""


def main() -> int:
    """Read exactly one bounded request, emit one closed response, and exit."""

    try:
        raw_request = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        page_pbm, width, height, scan_bands = _decode_request(raw_request)
        proposal = detect_two_column_label_lattice_v2(
            page_pbm,
            width=width,
            height=height,
            scan_bands=scan_bands,
        )
        response = _proposal_response(proposal, height=height)
    except Exception:
        # The process boundary intentionally emits no exception detail.
        response = _abstention_response("invalid_request")

    try:
        encoded = (json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n").encode(
            "ascii"
        )
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    except Exception:
        return 1
    return 0


def _decode_request(
    raw_request: bytes,
) -> tuple[
    bytes,
    int,
    int,
    tuple[tuple[int, int, int, int], tuple[int, int, int, int]],
]:
    if not raw_request or len(raw_request) > MAX_REQUEST_BYTES:
        raise DetectorWorkerRequestError("request size is outside the worker bound")
    parsed = json.loads(
        raw_request.decode("utf-8"),
        object_pairs_hook=_closed_object,
        parse_constant=_reject_json_constant,
    )
    _require_bounded_depth(parsed)
    if not isinstance(parsed, dict) or frozenset(parsed) != _REQUEST_KEYS:
        raise DetectorWorkerRequestError("request object is not closed")

    if parsed["interface_version"] != INTERFACE_VERSION:
        raise DetectorWorkerRequestError("interface version is unsupported")
    width = _request_integer(parsed["width"])
    height = _request_integer(parsed["height"])
    if (width, height) != (PAGE_WIDTH, PAGE_HEIGHT):
        raise DetectorWorkerRequestError("page dimensions are outside the interface")
    scan_bands = _request_scan_bands(parsed["scan_bands"])

    encoded_pbm = parsed["pbm_base64"]
    if (
        not isinstance(encoded_pbm, str)
        or not encoded_pbm.isascii()
        or len(encoded_pbm) != MAX_BASE64_CHARS
    ):
        raise DetectorWorkerRequestError("PBM encoding has an invalid size")
    page_pbm = base64.b64decode(encoded_pbm.encode("ascii"), validate=True)
    if len(page_pbm) != MAX_PBM_BYTES or base64.b64encode(page_pbm).decode("ascii") != encoded_pbm:
        raise DetectorWorkerRequestError("PBM encoding is not canonical")
    return page_pbm, width, height, scan_bands


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DetectorWorkerRequestError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise DetectorWorkerRequestError(f"unsupported JSON constant: {value}")


def _require_bounded_depth(value: object, *, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise DetectorWorkerRequestError("request nesting exceeds the worker bound")
    if isinstance(value, dict):
        for nested in value.values():
            _require_bounded_depth(nested, depth=depth + 1)
    elif isinstance(value, list):
        for nested in value:
            _require_bounded_depth(nested, depth=depth + 1)


def _request_integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise DetectorWorkerRequestError("request integer is invalid")
    return value


def _request_scan_bands(
    value: object,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    if not isinstance(value, list) or len(value) != 2:
        raise DetectorWorkerRequestError("exactly two scan bands are required")
    converted: list[tuple[int, int, int, int]] = []
    for raw_band in value:
        if not isinstance(raw_band, list) or len(raw_band) != 4:
            raise DetectorWorkerRequestError("scan band shape is invalid")
        coordinates = tuple(_request_integer(coordinate) for coordinate in raw_band)
        converted.append(
            (
                coordinates[0],
                coordinates[1],
                coordinates[2],
                coordinates[3],
            )
        )
    if converted[0] >= converted[1] or converted[0][0] >= converted[1][0]:
        raise DetectorWorkerRequestError("scan bands are not in physical-lane order")
    return converted[0], converted[1]


def _proposal_response(
    proposal: TwoColumnLayoutProposalV2,
    *,
    height: int,
) -> dict[str, object]:
    predictions: list[dict[str, int]] = []
    abstention_codes = sorted(proposal.abstention_codes)
    if proposal.detection_status == "proposed":
        for lane in proposal.lanes:
            for y0 in lane.candidate_y:
                predictions.append(
                    {
                        "lane": lane.lane_index,
                        "y0": y0,
                        "y1": y0 + ROW_WINDOW_HEIGHT,
                    }
                )
    response: dict[str, object] = {
        "algorithm_id": proposal.algorithm_id,
        "interface_version": INTERFACE_VERSION,
        "status": proposal.detection_status,
        "abstention_codes": abstention_codes,
        "predictions": predictions,
    }
    _validate_response(response, height=height)
    return response


def _abstention_response(code: str) -> dict[str, object]:
    return {
        "algorithm_id": DETECTOR_ALGORITHM_ID,
        "interface_version": INTERFACE_VERSION,
        "status": "abstained",
        "abstention_codes": [code],
        "predictions": [],
    }


def _validate_response(response: dict[str, object], *, height: int) -> None:
    if frozenset(response) != _RESPONSE_KEYS:
        raise DetectorWorkerRequestError("response object is not closed")
    if (
        response["algorithm_id"] != DETECTOR_ALGORITHM_ID
        or response["interface_version"] != INTERFACE_VERSION
    ):
        raise DetectorWorkerRequestError("response identity is invalid")

    status = response["status"]
    codes = response["abstention_codes"]
    predictions = response["predictions"]
    if status not in {"proposed", "abstained"}:
        raise DetectorWorkerRequestError("response status is invalid")
    if (
        not isinstance(codes, list)
        or any(not isinstance(code, str) or not code for code in codes)
        or codes != sorted(set(codes))
    ):
        raise DetectorWorkerRequestError("response abstention codes are invalid")
    if not isinstance(predictions, list):
        raise DetectorWorkerRequestError("response predictions are invalid")

    ordering: list[tuple[int, int, int]] = []
    for prediction in predictions:
        if not isinstance(prediction, dict) or frozenset(prediction) != _PREDICTION_KEYS:
            raise DetectorWorkerRequestError("prediction object is not closed")
        lane = _request_integer(prediction["lane"])
        y0 = _request_integer(prediction["y0"])
        y1 = _request_integer(prediction["y1"])
        if lane not in {0, 1} or not 0 <= y0 < y1 <= height or y1 - y0 != ROW_WINDOW_HEIGHT:
            raise DetectorWorkerRequestError("prediction geometry is invalid")
        ordering.append((lane, y0, y1))
    if ordering != sorted(set(ordering)):
        raise DetectorWorkerRequestError("predictions are duplicate or unsorted")
    if status == "proposed" and (codes or not predictions):
        raise DetectorWorkerRequestError("proposed response is incomplete")
    if status == "abstained" and (not codes or predictions):
        raise DetectorWorkerRequestError("abstained response is not fail-closed")


__all__ = [
    "INTERFACE_VERSION",
    "MAX_REQUEST_BYTES",
    "DetectorWorkerRequestError",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
