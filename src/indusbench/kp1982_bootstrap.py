"""Proposal-value-stripped assignment manifests for KP1982 Batch 0 review."""

from __future__ import annotations

import hashlib
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .io import decode_json, encode_json
from .kp1982_layout import (
    EXPECTED_LAYOUT_PROPOSAL_BYTE_SIZE,
    EXPECTED_LAYOUT_PROPOSAL_SHA256,
    MAX_PROPOSAL_BYTES,
    verify_layout_proposal_bytes,
)
from .schema_validation import validate_schema_instance

ASSIGNMENT_SCHEMA = "kp1982-bootstrap-assignment.schema.json"
MAX_ASSIGNMENT_BYTES = 16 * 1024 * 1024
MANIFEST_ID = "KP1982:BATCH0:BOOTSTRAP-ASSIGNMENT:V1"
EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256 = (
    "sha256:0f927340763084329be3c25c25f9bfd51e2b03e6c3177a66780e9320c8bf3761"
)
EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE = 415621
STATUS = (
    "private_proposal_value_stripped_bootstrap_assignment_only_requires_independent_human_review"
)
SCIENTIFIC_SCOPE = (
    "proposal-value-stripped sign-inventory bootstrap assignment only; proposed crop "
    "rectangles are review aids, machine occupancy/OCR/identifier values are withheld, "
    "and no accepted observation, sign identity, phonetic, language, semantic, "
    "translation, or decipherment inference is present"
)
WITHHELD_FIELDS = [
    "layout_proposal.cells[].occupancy_proposal",
    "layout_proposal.cells[].accepted_occupancy",
    "all_ocr_output",
    "all_machine_identifier_proposals",
    "all_accepted_observation_fields",
]
_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "accepted_occupancy",
        "accepted_observation",
        "canonical_digits",
        "identifier_proposal",
        "lower_primary_identifier",
        "machine_identifier_proposal",
        "occupancy",
        "occupancy_proposal",
        "ocr_output",
        "raw_text",
        "upper_catalog_rank",
    }
)


class KP1982BootstrapError(ValueError):
    """Raised when a bootstrap assignment fails closed."""


def _default_schema_path() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / ASSIGNMENT_SCHEMA
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        f"schemas/{ASSIGNMENT_SCHEMA}"
    )
    return Path(str(package_candidate))


def build_bootstrap_assignment(
    source_contract_bytes: bytes,
    layout_seed_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
    layout_proposal_bytes: bytes,
) -> dict[str, Any]:
    """Build the deterministic reviewer roster without machine answer values."""

    if len(page_pbm_bytes) != 2:
        raise KP1982BootstrapError("bootstrap assignment requires exactly two page images")
    if (
        len(layout_proposal_bytes) != EXPECTED_LAYOUT_PROPOSAL_BYTE_SIZE
        or _tagged_sha256(layout_proposal_bytes) != EXPECTED_LAYOUT_PROPOSAL_SHA256
    ):
        raise KP1982BootstrapError("layout proposal does not match the fixed V1 bytes")
    try:
        verify_layout_proposal_bytes(
            source_contract_bytes,
            layout_seed_bytes,
            page_pbm_bytes,
            layout_proposal_bytes,
        )
    except ValueError as error:
        raise KP1982BootstrapError("layout proposal pixel verification failed") from error

    proposal = _decode_object(
        layout_proposal_bytes,
        label="layout proposal",
        max_bytes=MAX_PROPOSAL_BYTES,
    )
    proposal_cells = _list(proposal.get("cells"), "layout proposal cells")
    if len(proposal_cells) != 700:
        raise KP1982BootstrapError("layout proposal roster is incomplete")

    assignment_cells: list[dict[str, Any]] = []
    for index, cell_value in enumerate(proposal_cells):
        cell = _mapping(cell_value, f"layout proposal cell {index}")
        assignment_cells.append(
            {
                "cell_id": cell.get("cell_id"),
                "page_index": cell.get("page_index"),
                "lane_index": cell.get("lane_index"),
                "row_index": cell.get("row_index"),
                "proposed_cell_bbox": cell.get("cell_bbox"),
                "proposed_context_bbox": cell.get("context_bbox"),
                "cell_crop_sha256": cell.get("cell_crop_sha256"),
                "cell_crop_byte_size": cell.get("cell_crop_byte_size"),
                "context_crop_sha256": cell.get("context_crop_sha256"),
                "context_crop_byte_size": cell.get("context_crop_byte_size"),
            }
        )

    source_commitment = _mapping(proposal.get("source_contract"), "source commitment")
    seed_commitment = _mapping(proposal.get("layout_seed"), "layout seed commitment")
    proposal_page_bitmaps = _list(proposal.get("page_bitmaps"), "page bitmaps")
    if len(proposal_page_bitmaps) != 2:
        raise KP1982BootstrapError("layout proposal page roster is incomplete")
    page_bitmaps: list[dict[str, Any]] = []
    for index, (page_value, page_bytes) in enumerate(
        zip(proposal_page_bitmaps, page_pbm_bytes, strict=True)
    ):
        page = _mapping(page_value, f"page bitmap {index}")
        page_bitmaps.append(
            {
                "page_index": page.get("page_index"),
                "canonical_pbm_sha256": page.get("canonical_pbm_sha256"),
                "byte_size": len(page_bytes),
            }
        )

    assignment: dict[str, Any] = {
        "schema_version": "0.1.0",
        "manifest_id": MANIFEST_ID,
        "status": STATUS,
        "scientific_scope": SCIENTIFIC_SCOPE,
        "source_contract": dict(source_commitment),
        "layout_seed": dict(seed_commitment),
        "layout_proposal": {
            "id": proposal.get("manifest_id"),
            "sha256": _tagged_sha256(layout_proposal_bytes),
            "byte_size": len(layout_proposal_bytes),
        },
        "page_bitmaps": page_bitmaps,
        "crop_policy": {
            "algorithm": proposal.get("crop_algorithm"),
            "coordinate_space": "decoded_embedded_page_image_pixels",
            "origin": "top_left",
            "rectangle_encoding": "half_open_xyxy_integer",
            "canonical_crop_encoding": (
                "P4 with exact dimensions; row-major top-to-bottom, left-to-right, "
                "black=1, MSB-first, zero unused low bits"
            ),
            "cell_crop_role": proposal.get("cell_crop_role"),
            "context_crop_role": proposal.get("context_crop_role"),
            "context_padding_pixels": proposal.get("context_padding_pixels"),
            "bbox_status": "proposal_only_requires_independent_visual_acceptance",
        },
        "withheld_fields": list(WITHHELD_FIELDS),
        "cells": assignment_cells,
        "assurances": {
            "source_contract_exact_bytes_verified": True,
            "layout_seed_exact_bytes_verified": True,
            "layout_proposal_exact_bytes_verified": True,
            "canonical_page_bitmaps_verified": True,
            "cell_geometry_accepted": False,
            "occupancy_accepted": False,
            "human_review_complete": False,
            "reviewer_independence_verified": False,
            "reviewer_blinding_verified": False,
            "identifiers_transcribed": False,
            "private_storage_verified": False,
            "public_release_authorized": False,
            "evaluation_admissible": False,
            "decipherment": False,
        },
    }
    _reject_machine_answer_keys(assignment)
    issues = validate_schema_instance(assignment, _default_schema_path())
    if issues:
        first = issues[0]
        raise KP1982BootstrapError(f"generated bootstrap assignment invalid at {first.path}")
    canonical_assignment = encode_json(assignment)
    if (
        len(canonical_assignment) != EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE
        or _tagged_sha256(canonical_assignment) != EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256
    ):
        raise KP1982BootstrapError(
            "bootstrap assignment implementation drift requires a new manifest version"
        )
    return assignment


def verify_bootstrap_assignment_bytes(
    source_contract_bytes: bytes,
    layout_seed_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
    layout_proposal_bytes: bytes,
    assignment_bytes: bytes,
) -> dict[str, bool | str]:
    """Rebuild and exact-byte-check one untrusted assignment manifest."""

    assignment = _decode_object(
        assignment_bytes,
        label="bootstrap assignment",
        max_bytes=MAX_ASSIGNMENT_BYTES,
    )
    issues = validate_schema_instance(assignment, _default_schema_path())
    if issues:
        first = issues[0]
        raise KP1982BootstrapError(f"bootstrap assignment schema invalid at {first.path}")
    _reject_machine_answer_keys(assignment)
    expected = build_bootstrap_assignment(
        source_contract_bytes,
        layout_seed_bytes,
        page_pbm_bytes,
        layout_proposal_bytes,
    )
    if assignment != expected or assignment_bytes != encode_json(expected):
        raise KP1982BootstrapError(
            "bootstrap assignment bytes differ from canonical pixel recomputation"
        )
    return {
        "valid": True,
        "claim_class": "private_bootstrap_assignment_only",
        "source_page_pixels_verified": True,
        "layout_proposal_canonical_bytes_verified": True,
        "assignment_canonical_bytes_verified": True,
        "machine_answer_values_withheld": True,
        "cell_geometry_accepted": False,
        "human_review_complete": False,
        "reviewer_independence_verified": False,
        "reviewer_blinding_verified": False,
        "identifiers_transcribed": False,
        "private_storage_verified": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
    }


def _decode_object(raw_bytes: bytes, *, label: str, max_bytes: int) -> dict[str, Any]:
    if not isinstance(raw_bytes, bytes) or not raw_bytes or len(raw_bytes) > max_bytes:
        raise KP1982BootstrapError(f"{label} has an invalid byte length")
    try:
        value = decode_json(raw_bytes, source=label)
    except ValueError as error:
        raise KP1982BootstrapError(f"{label} is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1982BootstrapError(f"{label} must decode to an object")
    return value


def _reject_machine_answer_keys(value: object) -> None:
    if isinstance(value, Mapping):
        forbidden = _FORBIDDEN_OUTPUT_KEYS.intersection(value)
        if forbidden:
            raise KP1982BootstrapError("bootstrap assignment contains a machine answer field")
        for child in value.values():
            _reject_machine_answer_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_machine_answer_keys(child)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1982BootstrapError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise KP1982BootstrapError(f"{label} must be an array")
    return value


def _tagged_sha256(raw_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
