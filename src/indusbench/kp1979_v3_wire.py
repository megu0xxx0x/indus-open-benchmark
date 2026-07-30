"""Canonical answer-free JSONL wire contract for the KP1979 V3 worker.

The parent-to-worker envelope contains only raster bytes, public geometry, and
scan bands.  It deliberately carries no case identity, expected outcome,
generator metadata, random material, or source commitment.  Semantically
invalid synthetic inputs remain representable because the closed C3 roster
must exercise the worker's four public input-error codes inside the sandbox.

The trusted valid-case builder may validate against ``WorkerRequest`` before
encoding.  Out-of-contract fixtures use ``encode_worker_request`` directly;
the worker then calls ``decode_worker_request`` and returns a closed rejection.
"""

from __future__ import annotations

import base64
import binascii
import itertools
import json
from dataclasses import dataclass
from typing import Final

from .kp1979_v3_protocol import (
    MAXIMUM_PREDICTION_HEIGHT,
    MAXIMUM_PREDICTIONS_PER_INVOCATION,
    RAW_P4_CONTRACT,
    SYNTHETIC_PAGE_HEIGHT,
    TARGET_ALGORITHM_ID,
    WORKER_ID,
    InputErrorCode,
    WorkerStatus,
)

WORKER_INTERFACE_VERSION: Final = WORKER_ID
MAX_WORKER_REQUEST_BYTES: Final = 6_000_000
MAX_WORKER_RESPONSE_BYTES: Final = 131_072
MAX_ENVELOPE_PBM_BYTES: Final = (MAX_WORKER_REQUEST_BYTES * 3) // 4

REQUEST_KEYS: Final = frozenset(
    {"interface_version", "pbm_base64", "width", "height", "scan_bands"}
)
RESPONSE_KEYS: Final = frozenset(
    {"algorithm_id", "interface_version", "status", "error_code", "predictions"}
)
PREDICTION_KEYS: Final = frozenset({"lane", "y0", "y1"})


class KP1979V3WireError(ValueError):
    """A redacted outer-envelope or response-contract failure."""

    def __init__(self) -> None:
        super().__init__("kp1979-v3 wire contract rejected")


class KP1979V3WorkerInputError(ValueError):
    """A closed semantic input rejection without path or diagnostic detail."""

    __slots__ = ("error_code",)

    error_code: InputErrorCode

    def __init__(self, error_code: InputErrorCode) -> None:
        if type(error_code) is not InputErrorCode:
            raise KP1979V3WireError
        self.error_code = error_code
        super().__init__("kp1979-v3 worker input rejected")


class _JSONContractFailure(ValueError):
    pass


ScanBands = tuple[tuple[int, int, int, int], ...]


@dataclass(frozen=True, slots=True)
class WorkerRequestEnvelope:
    """A syntactically valid answer-free envelope, including C3 error cases."""

    pbm: bytes
    width: int
    height: int
    scan_bands: ScanBands

    def __post_init__(self) -> None:
        _validate_generic_request_values(
            pbm=self.pbm,
            width=self.width,
            height=self.height,
            scan_bands=self.scan_bands,
        )


@dataclass(frozen=True, slots=True)
class WorkerRequest:
    """A semantically valid request under the exact frozen raw-P4 contract."""

    pbm: bytes
    width: int
    height: int
    scan_bands: ScanBands

    def __post_init__(self) -> None:
        _validate_generic_request_values(
            pbm=self.pbm,
            width=self.width,
            height=self.height,
            scan_bands=self.scan_bands,
        )
        _validate_request_semantics(
            pbm=self.pbm,
            width=self.width,
            height=self.height,
            scan_bands=self.scan_bands,
        )


@dataclass(frozen=True, slots=True)
class Prediction:
    """One bounded, answer-free worker proposal."""

    lane: int
    y0: int
    y1: int

    def __post_init__(self) -> None:
        _validate_prediction(self)


@dataclass(frozen=True, slots=True)
class WorkerResponse:
    """One closed raw worker response before evaluator interpretation."""

    status: WorkerStatus
    error_code: InputErrorCode | None
    predictions: tuple[Prediction, ...]

    def __post_init__(self) -> None:
        _validate_worker_response(self)


def _canonical_json_line(value: object) -> bytes:
    try:
        encoded = (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (OverflowError, RecursionError, TypeError, ValueError):
        raise KP1979V3WireError from None
    return encoded


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _JSONContractFailure
        result[key] = value
    return result


def _reject_json_constant(_: str) -> object:
    raise _JSONContractFailure


def _decode_canonical_json_line(line: bytes, *, maximum_bytes: int) -> dict[str, object]:
    if type(line) is not bytes or not line or len(line) > maximum_bytes:
        raise KP1979V3WireError
    try:
        parsed = json.loads(
            line.decode("ascii"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _JSONContractFailure,
        RecursionError,
        ValueError,
    ):
        raise KP1979V3WireError from None
    if type(parsed) is not dict or _canonical_json_line(parsed) != line:
        raise KP1979V3WireError
    return parsed


def _strict_int(value: object, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise KP1979V3WireError
    return value


def _validate_generic_request_values(
    *,
    pbm: object,
    width: object,
    height: object,
    scan_bands: object,
) -> None:
    if type(pbm) is not bytes or not pbm or len(pbm) > MAX_ENVELOPE_PBM_BYTES:
        raise KP1979V3WireError
    _strict_int(width, minimum=1, maximum=10_000)
    _strict_int(height, minimum=1, maximum=10_000)
    if type(scan_bands) is not tuple or not 1 <= len(scan_bands) <= 8:
        raise KP1979V3WireError
    for band in scan_bands:
        if type(band) is not tuple or len(band) != 4:
            raise KP1979V3WireError
        for coordinate in band:
            _strict_int(coordinate, minimum=0, maximum=10_000)


def _validate_request_semantics(
    *,
    pbm: bytes,
    width: int,
    height: int,
    scan_bands: ScanBands,
) -> None:
    if not pbm.startswith(RAW_P4_CONTRACT.header):
        raise KP1979V3WorkerInputError(InputErrorCode.INVALID_PBM_HEADER)
    if (width, height) != (RAW_P4_CONTRACT.width, RAW_P4_CONTRACT.height):
        raise KP1979V3WorkerInputError(InputErrorCode.INVALID_DIMENSIONS)
    if len(pbm) != RAW_P4_CONTRACT.pbm_byte_size:
        raise KP1979V3WorkerInputError(InputErrorCode.INVALID_PBM_PAYLOAD_SIZE)
    if scan_bands != RAW_P4_CONTRACT.scan_bands:
        raise KP1979V3WorkerInputError(InputErrorCode.INVALID_SCAN_BANDS)


def encode_worker_request(
    *,
    pbm: bytes,
    width: int,
    height: int,
    scan_bands: ScanBands,
) -> bytes:
    """Encode one answer-free envelope, including a trusted C3 error fixture."""

    _validate_generic_request_values(
        pbm=pbm,
        width=width,
        height=height,
        scan_bands=scan_bands,
    )
    line = _canonical_json_line(
        {
            "interface_version": WORKER_INTERFACE_VERSION,
            "pbm_base64": base64.b64encode(pbm).decode("ascii"),
            "width": width,
            "height": height,
            "scan_bands": [list(band) for band in scan_bands],
        }
    )
    if len(line) > MAX_WORKER_REQUEST_BYTES:
        raise KP1979V3WireError
    return line


def decode_worker_request_envelope(line: bytes) -> WorkerRequestEnvelope:
    """Decode only the bounded outer envelope without preempting C3 errors."""

    parsed = _decode_canonical_json_line(line, maximum_bytes=MAX_WORKER_REQUEST_BYTES)
    if frozenset(parsed) != REQUEST_KEYS:
        raise KP1979V3WireError
    if (
        type(parsed["interface_version"]) is not str
        or parsed["interface_version"] != WORKER_INTERFACE_VERSION
        or type(parsed["pbm_base64"]) is not str
        or not parsed["pbm_base64"]
        or not parsed["pbm_base64"].isascii()
    ):
        raise KP1979V3WireError

    width = _strict_int(parsed["width"], minimum=1, maximum=10_000)
    height = _strict_int(parsed["height"], minimum=1, maximum=10_000)
    raw_bands = parsed["scan_bands"]
    if type(raw_bands) is not list or not 1 <= len(raw_bands) <= 8:
        raise KP1979V3WireError
    bands: list[tuple[int, int, int, int]] = []
    for raw_band in raw_bands:
        if type(raw_band) is not list or len(raw_band) != 4:
            raise KP1979V3WireError
        coordinates = tuple(
            _strict_int(coordinate, minimum=0, maximum=10_000) for coordinate in raw_band
        )
        bands.append((coordinates[0], coordinates[1], coordinates[2], coordinates[3]))

    encoded_pbm = parsed["pbm_base64"]
    assert isinstance(encoded_pbm, str)
    try:
        pbm = base64.b64decode(encoded_pbm.encode("ascii"), validate=True)
    except (ValueError, binascii.Error):
        raise KP1979V3WireError from None
    if (
        not pbm
        or len(pbm) > MAX_ENVELOPE_PBM_BYTES
        or base64.b64encode(pbm).decode("ascii") != encoded_pbm
    ):
        raise KP1979V3WireError
    return WorkerRequestEnvelope(
        pbm=pbm,
        width=width,
        height=height,
        scan_bands=tuple(bands),
    )


def decode_worker_request(line: bytes) -> WorkerRequest:
    """Decode and apply the worker-owned semantic raw-P4 checks."""

    envelope = decode_worker_request_envelope(line)
    return WorkerRequest(
        pbm=envelope.pbm,
        width=envelope.width,
        height=envelope.height,
        scan_bands=envelope.scan_bands,
    )


def _validate_prediction(prediction: Prediction) -> None:
    if type(prediction) is not Prediction:
        raise KP1979V3WireError
    lane = _strict_int(prediction.lane, minimum=0, maximum=1)
    y0 = _strict_int(prediction.y0, minimum=0, maximum=SYNTHETIC_PAGE_HEIGHT)
    y1 = _strict_int(prediction.y1, minimum=0, maximum=SYNTHETIC_PAGE_HEIGHT)
    if y0 >= y1 or y1 - y0 > MAXIMUM_PREDICTION_HEIGHT or lane not in (0, 1):
        raise KP1979V3WireError


def _validate_worker_response(response: WorkerResponse) -> None:
    if type(response) is not WorkerResponse:
        raise KP1979V3WireError
    if type(response.status) is not WorkerStatus:
        raise KP1979V3WireError
    if type(response.predictions) is not tuple or any(
        type(prediction) is not Prediction for prediction in response.predictions
    ):
        raise KP1979V3WireError
    if len(response.predictions) > MAXIMUM_PREDICTIONS_PER_INVOCATION:
        raise KP1979V3WireError
    for prediction in response.predictions:
        _validate_prediction(prediction)
    keys = tuple(
        (prediction.lane, prediction.y0, prediction.y1) for prediction in response.predictions
    )
    if any(current <= previous for previous, current in itertools.pairwise(keys)):
        raise KP1979V3WireError

    if response.status is WorkerStatus.PROPOSED:
        if not response.predictions or response.error_code is not None:
            raise KP1979V3WireError
    elif response.status is WorkerStatus.ABSTAINED:
        if response.predictions or response.error_code is not None:
            raise KP1979V3WireError
    elif response.status is WorkerStatus.REJECTED:
        if response.predictions or type(response.error_code) is not InputErrorCode:
            raise KP1979V3WireError
    else:
        raise KP1979V3WireError


def encode_worker_response(response: WorkerResponse) -> bytes:
    """Encode one closed raw worker response as canonical ASCII JSONL."""

    _validate_worker_response(response)
    line = _canonical_json_line(
        {
            "algorithm_id": TARGET_ALGORITHM_ID,
            "interface_version": WORKER_INTERFACE_VERSION,
            "status": response.status.value,
            "error_code": (response.error_code.value if response.error_code is not None else None),
            "predictions": [
                {"lane": prediction.lane, "y0": prediction.y0, "y1": prediction.y1}
                for prediction in response.predictions
            ],
        }
    )
    if len(line) > MAX_WORKER_RESPONSE_BYTES:
        raise KP1979V3WireError
    return line


def decode_worker_response(line: bytes) -> WorkerResponse:
    """Decode and validate one closed raw worker response."""

    parsed = _decode_canonical_json_line(line, maximum_bytes=MAX_WORKER_RESPONSE_BYTES)
    if frozenset(parsed) != RESPONSE_KEYS:
        raise KP1979V3WireError
    if (
        type(parsed["algorithm_id"]) is not str
        or parsed["algorithm_id"] != TARGET_ALGORITHM_ID
        or type(parsed["interface_version"]) is not str
        or parsed["interface_version"] != WORKER_INTERFACE_VERSION
        or type(parsed["status"]) is not str
    ):
        raise KP1979V3WireError
    try:
        status = WorkerStatus(parsed["status"])
    except ValueError:
        raise KP1979V3WireError from None

    raw_error_code = parsed["error_code"]
    if raw_error_code is None:
        error_code = None
    elif type(raw_error_code) is str:
        try:
            error_code = InputErrorCode(raw_error_code)
        except ValueError:
            raise KP1979V3WireError from None
    else:
        raise KP1979V3WireError

    raw_predictions = parsed["predictions"]
    if (
        type(raw_predictions) is not list
        or len(raw_predictions) > MAXIMUM_PREDICTIONS_PER_INVOCATION
    ):
        raise KP1979V3WireError
    predictions: list[Prediction] = []
    for raw_prediction in raw_predictions:
        if type(raw_prediction) is not dict or frozenset(raw_prediction) != PREDICTION_KEYS:
            raise KP1979V3WireError
        predictions.append(
            Prediction(
                lane=_strict_int(raw_prediction["lane"], minimum=0, maximum=1),
                y0=_strict_int(
                    raw_prediction["y0"],
                    minimum=0,
                    maximum=SYNTHETIC_PAGE_HEIGHT,
                ),
                y1=_strict_int(
                    raw_prediction["y1"],
                    minimum=0,
                    maximum=SYNTHETIC_PAGE_HEIGHT,
                ),
            )
        )
    return WorkerResponse(
        status=status,
        error_code=error_code,
        predictions=tuple(predictions),
    )
