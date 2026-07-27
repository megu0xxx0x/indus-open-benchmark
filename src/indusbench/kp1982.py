"""Network-free verification of the fixed KP1982 Batch 0 PDF snapshot."""

from __future__ import annotations

import hashlib
import importlib.resources
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .io import decode_json
from .schema_validation import validate_schema_instance

CONTRACT_SCHEMA_FILENAME = "kp1982-batch0-source.schema.json"
MAX_CONTRACT_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_PAGE_PBM_BYTES = 5 * 1024 * 1024


class KP1982SourceError(ValueError):
    """Raised when the fixed public-source contract or bytes do not verify."""


def _default_schema_path() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / CONTRACT_SCHEMA_FILENAME
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        f"schemas/{CONTRACT_SCHEMA_FILENAME}"
    )
    return Path(str(package_candidate))


def verify_snapshot_identity(
    source_bytes: bytes,
    *,
    expected_sha256: str,
    expected_byte_size: int,
) -> None:
    """Verify exact bytes against an independently supplied size and digest."""

    if not isinstance(source_bytes, bytes):
        raise KP1982SourceError("source snapshot must be supplied as exact bytes")
    if (
        not isinstance(expected_byte_size, int)
        or isinstance(expected_byte_size, bool)
        or expected_byte_size < 1
    ):
        raise KP1982SourceError("expected source byte size is invalid")
    if len(source_bytes) != expected_byte_size:
        raise KP1982SourceError("source snapshot byte size does not match the contract")
    observed_sha256 = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    if observed_sha256 != expected_sha256:
        raise KP1982SourceError("source snapshot digest does not match the contract")


def verify_canonical_pbm(
    pbm_bytes: bytes,
    *,
    width: int,
    height: int,
    expected_pbm_sha256: str,
    expected_pixel_sha256: str,
) -> None:
    """Verify canonical raw PBM bytes and their packed pixel payload."""

    if not isinstance(pbm_bytes, bytes):
        raise KP1982SourceError("page image must be supplied as exact PBM bytes")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or width < 1
        or height < 1
    ):
        raise KP1982SourceError("page image dimensions are invalid")
    header = f"P4\n{width} {height}\n".encode("ascii")
    if not pbm_bytes.startswith(header):
        raise KP1982SourceError("page image does not use the canonical PBM header")
    payload = pbm_bytes[len(header) :]
    expected_payload_size = ((width + 7) // 8) * height
    if len(payload) != expected_payload_size:
        raise KP1982SourceError("page image pixel payload has an invalid byte size")
    observed_pbm_sha256 = "sha256:" + hashlib.sha256(pbm_bytes).hexdigest()
    if observed_pbm_sha256 != expected_pbm_sha256:
        raise KP1982SourceError("canonical PBM digest does not match the contract")
    observed_pixel_sha256 = "sha256:" + hashlib.sha256(payload).hexdigest()
    if observed_pixel_sha256 != expected_pixel_sha256:
        raise KP1982SourceError("page pixel digest does not match the contract")


def verify_kp1982_source(
    contract_bytes: bytes,
    source_bytes: bytes,
    *,
    page_pbm_bytes: Sequence[bytes] | None = None,
) -> dict[str, Any]:
    """Verify the exact official PDF bytes against the closed Batch 0 contract."""

    if not isinstance(contract_bytes, bytes):
        raise KP1982SourceError("source contract must be supplied as exact bytes")
    if not contract_bytes or len(contract_bytes) > MAX_CONTRACT_BYTES:
        raise KP1982SourceError("source contract has an invalid byte length")
    if not isinstance(source_bytes, bytes):
        raise KP1982SourceError("source snapshot must be supplied as exact bytes")
    if not source_bytes or len(source_bytes) > MAX_SOURCE_BYTES:
        raise KP1982SourceError("source snapshot has an invalid byte length")
    try:
        contract_value = decode_json(contract_bytes, source="KP1982 source contract")
    except ValueError as error:
        raise KP1982SourceError("source contract is not strict finite JSON") from error
    if not isinstance(contract_value, dict):
        raise KP1982SourceError("source contract must decode to an object")
    issues = validate_schema_instance(
        contract_value,
        _default_schema_path(),
    )
    if issues:
        first = issues[0]
        raise KP1982SourceError(f"source contract schema invalid at {first.path}")

    source = _mapping(contract_value.get("source"), "source")
    expected_sha256 = _string(source.get("sha256"), "source sha256")
    expected_byte_size = source.get("byte_size")
    if not isinstance(expected_byte_size, int) or isinstance(expected_byte_size, bool):
        raise KP1982SourceError("source byte_size must be an integer")
    verify_snapshot_identity(
        source_bytes,
        expected_sha256=expected_sha256,
        expected_byte_size=expected_byte_size,
    )
    if not source_bytes.startswith(b"%PDF-"):
        raise KP1982SourceError("source snapshot lacks a PDF signature")
    if b"%%EOF" not in source_bytes[-1024:]:
        raise KP1982SourceError("source snapshot lacks a terminal PDF marker")

    target_page_pixels_verified = False
    if page_pbm_bytes is not None:
        pages = contract_value.get("target_pages")
        if not isinstance(pages, list) or len(pages) != 2 or len(page_pbm_bytes) != len(pages):
            raise KP1982SourceError("exactly two page images are required in contract order")
        for page_value, pbm_bytes in zip(pages, page_pbm_bytes, strict=True):
            page = _mapping(page_value, "target page")
            image = _mapping(page.get("embedded_image"), "embedded image")
            width = _integer(image.get("width"), "embedded image width")
            height = _integer(image.get("height"), "embedded image height")
            verify_canonical_pbm(
                pbm_bytes,
                width=width,
                height=height,
                expected_pbm_sha256=_string(
                    image.get("canonical_pbm_sha256"),
                    "canonical PBM sha256",
                ),
                expected_pixel_sha256=_string(
                    image.get("pixel_payload_sha256"),
                    "pixel payload sha256",
                ),
            )
        target_page_pixels_verified = True

    return {
        "schema_version": "0.1.0",
        "contract_id": contract_value.get("contract_id"),
        "source_id": source.get("source_id"),
        "valid": True,
        "source_snapshot_match": True,
        "exact_byte_size_match": True,
        "exact_sha256_match": True,
        "pdf_signature_present": True,
        "target_page_identity_bound_by_snapshot": True,
        "target_page_pixels_verified": target_page_pixels_verified,
        "page_structure_reparsed": False,
        "crop_coordinates_verified": False,
        "human_double_transcription_complete": False,
        "rights_evidence_externally_verified": False,
        "decipherment": False,
    }


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1982SourceError(f"{label} must be an object")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise KP1982SourceError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise KP1982SourceError(f"{label} must be an integer")
    return value
