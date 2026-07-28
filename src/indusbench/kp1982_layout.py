"""Deterministic private crop proposals for KP1982 Batch 0 layout review."""

from __future__ import annotations

import hashlib
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .io import decode_json, encode_json
from .kp1982 import verify_canonical_pbm
from .schema_validation import validate_schema_instance

SOURCE_SCHEMA = "kp1982-batch0-source.schema.json"
SEED_SCHEMA = "kp1982-layout-seed.schema.json"
PROPOSAL_SCHEMA = "kp1982-layout-proposal.schema.json"
MAX_SEED_BYTES = 1024 * 1024
MAX_PROPOSAL_BYTES = 16 * 1024 * 1024
CONTEXT_PADDING_PIXELS = 32
EXPECTED_LAYOUT_SEED_SHA256 = (
    "sha256:1254226d13781b67e7c0c52bdeeb01b5327afb9f8b07acadb3e4a4333e72f820"
)
EXPECTED_LAYOUT_SEED_BYTE_SIZE = 6922
EXPECTED_LAYOUT_PROPOSAL_SHA256 = (
    "sha256:85dfa34210380ca6f92fa2847d50050642bc221910a05eb2fed33855f3894a78"
)
EXPECTED_LAYOUT_PROPOSAL_BYTE_SIZE = 460008


class KP1982LayoutError(ValueError):
    """Raised when layout source, geometry, or crop commitments fail closed."""


def _default_schema_path(filename: str) -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / filename
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(f"schemas/{filename}")
    return Path(str(package_candidate))


def crop_canonical_pbm(
    page_pbm: bytes,
    *,
    page_width: int,
    page_height: int,
    bbox: Sequence[int],
) -> bytes:
    """Return one exact raw PBM crop with unused low bits fixed to zero."""

    if len(bbox) != 4 or any(
        not isinstance(value, int) or isinstance(value, bool) for value in bbox
    ):
        raise KP1982LayoutError("crop bbox must contain four integers")
    x0, y0, x1, y1 = bbox
    if not 0 <= x0 < x1 <= page_width or not 0 <= y0 < y1 <= page_height:
        raise KP1982LayoutError("crop bbox is outside the page bitmap")
    page_header = f"P4\n{page_width} {page_height}\n".encode("ascii")
    if not page_pbm.startswith(page_header):
        raise KP1982LayoutError("page image does not use the expected PBM header")
    source = memoryview(page_pbm)[len(page_header) :]
    source_row_bytes = (page_width + 7) // 8
    if len(source) != source_row_bytes * page_height:
        raise KP1982LayoutError("page image pixel payload has an invalid byte size")

    crop_width = x1 - x0
    crop_height = y1 - y0
    crop_row_bytes = (crop_width + 7) // 8
    crop_payload = bytearray(crop_row_bytes * crop_height)
    source_byte_start = x0 // 8
    source_byte_end = (x1 + 7) // 8
    source_segment_bytes = source_byte_end - source_byte_start
    source_segment_bits = source_segment_bytes * 8
    trailing_source_bits = source_segment_bits - (x0 % 8) - crop_width
    trailing_crop_bits = crop_row_bytes * 8 - crop_width
    crop_mask = (1 << crop_width) - 1
    for crop_y, source_y in enumerate(range(y0, y1)):
        source_row_offset = source_y * source_row_bytes + source_byte_start
        crop_row_offset = crop_y * crop_row_bytes
        segment = int.from_bytes(
            source[source_row_offset : source_row_offset + source_segment_bytes]
        )
        packed_crop = ((segment >> trailing_source_bits) & crop_mask) << trailing_crop_bits
        crop_payload[crop_row_offset : crop_row_offset + crop_row_bytes] = packed_crop.to_bytes(
            crop_row_bytes,
            "big",
        )
    return f"P4\n{crop_width} {crop_height}\n".encode("ascii") + bytes(crop_payload)


def build_layout_proposal(
    source_contract_bytes: bytes,
    layout_seed_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
) -> dict[str, Any]:
    """Build a deterministic crop-hash proposal from fixed public page pixels."""

    source_contract = _decode_schema_object(
        source_contract_bytes,
        label="source contract",
        schema_filename=SOURCE_SCHEMA,
    )
    if (
        len(layout_seed_bytes) != EXPECTED_LAYOUT_SEED_BYTE_SIZE
        or _tagged_sha256(layout_seed_bytes) != EXPECTED_LAYOUT_SEED_SHA256
    ):
        raise KP1982LayoutError("layout seed does not match the fixed snapshot")
    layout_seed = _decode_schema_object(
        layout_seed_bytes,
        label="layout seed",
        schema_filename=SEED_SCHEMA,
    )
    source_commitment = _mapping(
        layout_seed.get("source_contract"),
        "layout source commitment",
    )
    _require_exact_commitment(
        source_contract_bytes,
        expected_id=_string(source_contract.get("contract_id"), "contract_id"),
        actual=source_commitment,
    )

    source_pages = _list(source_contract.get("target_pages"), "source target_pages")
    seed_pages = _list(layout_seed.get("pages"), "layout pages")
    if len(source_pages) != 2 or len(seed_pages) != 2 or len(page_pbm_bytes) != 2:
        raise KP1982LayoutError("layout proposal requires exactly two target pages")
    coordinate_space = _mapping(
        layout_seed.get("coordinate_space"),
        "coordinate_space",
    )
    page_width = _integer(coordinate_space.get("width"), "page width")
    page_height = _integer(coordinate_space.get("height"), "page height")

    cells: list[dict[str, Any]] = []
    page_bitmap_commitments: list[dict[str, Any]] = []
    for source_page_value, seed_page_value, page_pbm in zip(
        source_pages,
        seed_pages,
        page_pbm_bytes,
        strict=True,
    ):
        source_page = _mapping(source_page_value, "source page")
        seed_page = _mapping(seed_page_value, "seed page")
        if (
            source_page.get("page_index") != seed_page.get("page_index")
            or source_page.get("pdf_page_number") != seed_page.get("pdf_page_number")
            or source_page.get("printed_page_label") != seed_page.get("printed_page_label")
        ):
            raise KP1982LayoutError("source and layout page identities differ")
        image = _mapping(source_page.get("embedded_image"), "embedded image")
        verify_canonical_pbm(
            page_pbm,
            width=page_width,
            height=page_height,
            expected_pbm_sha256=_string(
                image.get("canonical_pbm_sha256"),
                "canonical PBM sha256",
            ),
            expected_pixel_sha256=_string(
                image.get("pixel_payload_sha256"),
                "pixel payload sha256",
            ),
        )
        page_index = _integer(seed_page.get("page_index"), "page_index")
        pdf_page_number = _integer(
            seed_page.get("pdf_page_number"),
            "pdf_page_number",
        )
        page_bitmap_commitments.append(
            {
                "page_index": page_index,
                "canonical_pbm_sha256": _tagged_sha256(page_pbm),
            }
        )
        lane_edges = [
            _integer(value, "lane edge")
            for value in _list(seed_page.get("lane_edges_x"), "lane_edges_x")
        ]
        lanes = [_mapping(value, "lane") for value in _list(seed_page.get("lanes"), "lanes")]
        if len(lane_edges) != 11 or len(lanes) != 10:
            raise KP1982LayoutError("layout needs ten lanes and eleven boundaries")
        if lane_edges != sorted(set(lane_edges)):
            raise KP1982LayoutError("lane boundaries must be strictly increasing")
        row_slot_count = _integer(
            seed_page.get("row_slot_count_per_lane"),
            "row_slot_count_per_lane",
        )
        if row_slot_count != 35:
            raise KP1982LayoutError("layout v0.1 requires 35 row slots per lane")
        for expected_lane_index, lane in enumerate(lanes):
            lane_index = _integer(lane.get("lane_index"), "lane_index")
            if lane_index != expected_lane_index:
                raise KP1982LayoutError("lane indices must be contiguous from zero")
            model = _mapping(lane.get("row_center_model"), "row center model")
            intercept = _finite_number(model.get("intercept_y"), "row intercept")
            pitch = _finite_number(model.get("pitch_y"), "row pitch")
            if pitch <= 0:
                raise KP1982LayoutError("row pitch must be positive")
            boundaries = [
                _round_half_up(intercept + pitch * (boundary_index - 0.5))
                for boundary_index in range(row_slot_count + 1)
            ]
            boundaries = [min(page_height, max(0, value)) for value in boundaries]
            if boundaries != sorted(set(boundaries)):
                raise KP1982LayoutError("derived row boundaries are not strictly increasing")
            occupied_rows = _integer(
                lane.get("provisional_occupied_row_slots"),
                "provisional occupied rows",
            )
            if not 0 <= occupied_rows <= row_slot_count:
                raise KP1982LayoutError("provisional occupancy is outside the row slots")
            for row_index in range(row_slot_count):
                cell_bbox = [
                    lane_edges[lane_index],
                    boundaries[row_index],
                    lane_edges[lane_index + 1],
                    boundaries[row_index + 1],
                ]
                context_bbox = [
                    max(0, cell_bbox[0] - CONTEXT_PADDING_PIXELS),
                    max(0, cell_bbox[1] - CONTEXT_PADDING_PIXELS),
                    min(page_width, cell_bbox[2] + CONTEXT_PADDING_PIXELS),
                    min(page_height, cell_bbox[3] + CONTEXT_PADDING_PIXELS),
                ]
                crop_bytes = crop_canonical_pbm(
                    page_pbm,
                    page_width=page_width,
                    page_height=page_height,
                    bbox=cell_bbox,
                )
                context_crop_bytes = crop_canonical_pbm(
                    page_pbm,
                    page_width=page_width,
                    page_height=page_height,
                    bbox=context_bbox,
                )
                cells.append(
                    {
                        "cell_id": (
                            f"KP1982:P{pdf_page_number}:L{lane_index:02d}:R{row_index:02d}"
                        ),
                        "page_index": page_index,
                        "lane_index": lane_index,
                        "row_index": row_index,
                        "occupancy_proposal": (
                            "proposed_occupied" if row_index < occupied_rows else "proposed_blank"
                        ),
                        "cell_bbox": cell_bbox,
                        "context_bbox": context_bbox,
                        "cell_crop_sha256": _tagged_sha256(crop_bytes),
                        "cell_crop_byte_size": len(crop_bytes),
                        "context_crop_sha256": _tagged_sha256(context_crop_bytes),
                        "context_crop_byte_size": len(context_crop_bytes),
                        "accepted_occupancy": None,
                    }
                )

    proposal: dict[str, Any] = {
        "schema_version": "0.1.0",
        "manifest_id": "KP1982:BATCH0:LAYOUT-PROPOSAL:V1",
        "status": "private_proposal_only_requires_visual_double_review",
        "scientific_scope": (
            "deterministic crop proposal only; no accepted occupancy, identifier, "
            "sign, phonetic, language, semantic, translation, or decipherment inference"
        ),
        "source_contract": _commitment(
            source_contract_bytes,
            _string(source_contract.get("contract_id"), "contract_id"),
        ),
        "layout_seed": _commitment(
            layout_seed_bytes,
            _string(layout_seed.get("seed_id"), "seed_id"),
        ),
        "page_bitmaps": page_bitmap_commitments,
        "crop_algorithm": "kp1982-half-pitch-cells-v1",
        "cell_crop_role": "locator_only_may_split_foreground",
        "context_crop_role": "review_view_not_accepted_glyph_evidence",
        "context_padding_basis": (
            "proposal-only 8-connected black=1 component audit with maximum-overlap "
            "owner and manifest-order ties; disconnected-mark ownership remains unresolved"
        ),
        "context_padding_pixels": CONTEXT_PADDING_PIXELS,
        "cells": cells,
        "assurances": {
            "source_page_pixels_verified": True,
            "crop_bytes_recomputed": True,
            "context_component_coverage_recomputed": False,
            "lane_edges_accepted": False,
            "row_boundaries_accepted": False,
            "occupancy_accepted": False,
            "human_double_review_complete": False,
            "identifiers_transcribed": False,
            "decipherment": False,
        },
    }
    issues = validate_schema_instance(
        proposal,
        _default_schema_path(PROPOSAL_SCHEMA),
    )
    if issues:
        first = issues[0]
        raise KP1982LayoutError(f"generated layout proposal invalid at {first.path}")
    canonical_proposal = encode_json(proposal)
    if (
        len(canonical_proposal) != EXPECTED_LAYOUT_PROPOSAL_BYTE_SIZE
        or _tagged_sha256(canonical_proposal) != EXPECTED_LAYOUT_PROPOSAL_SHA256
    ):
        raise KP1982LayoutError(
            "layout proposal implementation drift requires a new manifest version"
        )
    return proposal


def verify_layout_proposal_bytes(
    source_contract_bytes: bytes,
    layout_seed_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
    proposal_bytes: bytes,
) -> dict[str, bool | str]:
    """Rebuild and compare an untrusted layout proposal against source pixels."""

    proposal = _decode_schema_object(
        proposal_bytes,
        label="layout proposal",
        schema_filename=PROPOSAL_SCHEMA,
        max_bytes=MAX_PROPOSAL_BYTES,
    )
    expected = build_layout_proposal(
        source_contract_bytes,
        layout_seed_bytes,
        page_pbm_bytes,
    )
    if proposal != expected or proposal_bytes != encode_json(expected):
        raise KP1982LayoutError("layout proposal bytes differ from canonical pixel recomputation")
    return {
        "valid": True,
        "claim_class": "private_layout_proposal_only",
        "source_page_pixels_verified": True,
        "crop_bytes_recomputed": True,
        "canonical_manifest_bytes_verified": True,
        "context_component_coverage_recomputed": False,
        "layout_accepted": False,
        "human_double_review_complete": False,
        "identifiers_transcribed": False,
        "private_storage_verified": False,
        "decipherment": False,
    }


def _decode_schema_object(
    raw_bytes: bytes,
    *,
    label: str,
    schema_filename: str,
    max_bytes: int = MAX_SEED_BYTES,
) -> dict[str, Any]:
    if not isinstance(raw_bytes, bytes) or not raw_bytes or len(raw_bytes) > max_bytes:
        raise KP1982LayoutError(f"{label} has an invalid byte length")
    try:
        value = decode_json(raw_bytes, source=label)
    except ValueError as error:
        raise KP1982LayoutError(f"{label} is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1982LayoutError(f"{label} must decode to an object")
    issues = validate_schema_instance(value, _default_schema_path(schema_filename))
    if issues:
        first = issues[0]
        raise KP1982LayoutError(f"{label} schema invalid at {first.path}")
    return value


def _require_exact_commitment(
    raw_bytes: bytes,
    *,
    expected_id: str,
    actual: Mapping[str, Any],
) -> None:
    expected = _commitment(raw_bytes, expected_id)
    normalized = {
        "id": actual.get("contract_id"),
        "sha256": actual.get("sha256"),
        "byte_size": actual.get("byte_size"),
    }
    if normalized != expected:
        raise KP1982LayoutError("layout seed cites different source-contract bytes")


def _commitment(raw_bytes: bytes, identifier: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "sha256": _tagged_sha256(raw_bytes),
        "byte_size": len(raw_bytes),
    }


def _tagged_sha256(raw_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


def _round_half_up(value: float) -> int:
    if not math.isfinite(value):
        raise KP1982LayoutError("derived boundary is not finite")
    return math.floor(value + 0.5)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1982LayoutError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise KP1982LayoutError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise KP1982LayoutError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise KP1982LayoutError(f"{label} must be an integer")
    return value


def _finite_number(value: object, label: str) -> float:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise KP1982LayoutError(f"{label} must be finite")
    return float(value)
