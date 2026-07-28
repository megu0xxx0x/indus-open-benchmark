"""Exact-source and pixel-only layout audit for the Helsinki 1979 corpus."""

from __future__ import annotations

import hashlib
import importlib.resources
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import decode_json
from .printed_concordance_layout import (
    ROW_WINDOW_HEIGHT,
    TwoColumnLayoutProposal,
    detect_two_column_label_lattice,
)
from .schema_validation import validate_schema_instance

SOURCE_SCHEMA = "kp1979-corpus-source.schema.json"
PAGE_MAP_SCHEMA = "kp1979-page-map.schema.json"
MAX_CONTRACT_BYTES = 1024 * 1024
MAX_PAGE_MAP_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_PAGE_PBM_BYTES = 5 * 1024 * 1024
EXPECTED_SOURCE_CONTRACT_BYTE_SIZE = 3319
EXPECTED_SOURCE_CONTRACT_SHA256 = (
    "sha256:489d7f4cee1de7211b6bd098d1b8fb5f2bf1a44d6ce78249ac90c1be4dfbd40b"
)
EXPECTED_PAGE_MAP_BYTE_SIZE = 154016
EXPECTED_PAGE_MAP_SHA256 = "sha256:ecd3054909928dddcb087ffdefe1b786c1f6464bd448b008c9ec476ccadc3793"
FIRST_MAPPED_PDF_PAGE = 2
LAST_MAPPED_PDF_PAGE = 180
PAGE_WIDTH = 4880
PAGE_HEIGHT = 7010


class KP1979SourceError(ValueError):
    """Raised when the fixed source, page map, or layout audit fails closed."""


@dataclass(frozen=True)
class KP1979PageLayoutResult:
    """Label-lattice-only result for one mapped page."""

    pdf_page_number: int
    page_role: str
    layout_class: str
    detection_status: str
    abstention_codes: tuple[str, ...]
    label_slot_lanes: tuple[tuple[tuple[int, int, int, int], ...], ...]


def _default_schema_path(filename: str) -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / filename
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(f"schemas/{filename}")
    return Path(str(package_candidate))


def verify_kp1979_source(
    source_contract_bytes: bytes,
    page_map_bytes: bytes,
    source_bytes: bytes,
    *,
    page_pbm_bytes: Iterable[tuple[int, bytes]] | None = None,
) -> dict[str, bool | str]:
    """Verify the exact official PDF and, optionally, all 179 native page images."""

    source_contract, page_map = _verify_public_contracts(
        source_contract_bytes,
        page_map_bytes,
    )
    _verify_source_snapshot(source_contract, source_bytes)
    pixels_verified = False
    if page_pbm_bytes is not None:
        _consume_verified_pages(page_map, page_pbm_bytes)
        pixels_verified = True
    return {
        "valid": True,
        "claim_class": "fixed_public_source_and_page_map_only",
        "source_snapshot_match": True,
        "page_map_snapshot_match": True,
        "all_mapped_page_pixels_verified": pixels_verified,
        "page_classes_accepted": False,
        "layout_candidates_accepted": False,
        "identifiers_transcribed": False,
        "sign_sequences_transcribed": False,
        "three_way_reconciliation_complete": False,
        "decipherment": False,
    }


def audit_kp1979_layout(
    source_contract_bytes: bytes,
    page_map_bytes: bytes,
    source_bytes: bytes,
    page_pbm_bytes: Iterable[tuple[int, bytes]],
) -> dict[str, bool | str]:
    """Verify all page pixels and apply the abstaining V1 detector page by page."""

    source_contract, page_map = _verify_public_contracts(
        source_contract_bytes,
        page_map_bytes,
    )
    _verify_source_snapshot(source_contract, source_bytes)
    pages = _page_entries(page_map)
    supplied = iter(page_pbm_bytes)
    for page in pages:
        pdf_page_number, page_bytes = _next_page(supplied)
        expected_page_number = _integer(page.get("pdf_page_number"), "pdf_page_number")
        if pdf_page_number != expected_page_number:
            raise KP1979SourceError("page bitmap order differs from the fixed page map")
        _verify_page_bitmap(page, page_bytes)
        result = detect_kp1979_page_layout(page, page_bytes)
        _verify_expected_layout_gate(result)
    try:
        next(supplied)
    except StopIteration:
        pass
    else:
        raise KP1979SourceError("page bitmap iterator contains an unexpected extra page")

    return {
        "valid": True,
        "claim_class": "public_source_bound_layout_audit_only",
        "source_snapshot_match": True,
        "page_map_snapshot_match": True,
        "all_mapped_page_pixels_verified": True,
        "selected_page_layout_status_gates_passed": True,
        "normal_page_detector_gates_passed": True,
        "candidate_counts_disclosed": False,
        "layout_candidates_accepted": False,
        "identifiers_transcribed": False,
        "sign_sequences_transcribed": False,
        "three_way_reconciliation_complete": False,
        "decipherment": False,
    }


def detect_kp1979_page_layout(
    page: Mapping[str, Any],
    page_pbm: bytes,
) -> KP1979PageLayoutResult:
    """Apply the same detector to data, negative-control, and auxiliary pages."""

    page_number = _integer(page.get("pdf_page_number"), "pdf_page_number")
    page_role = _string(page.get("page_role"), "page_role")
    layout_class = _string(page.get("layout_class"), "layout_class")
    scan_values = page.get("proposal_scan_bands")
    if not isinstance(scan_values, list):
        raise KP1979SourceError("proposal_scan_bands must be an array")
    if not scan_values:
        return KP1979PageLayoutResult(
            pdf_page_number=page_number,
            page_role=page_role,
            layout_class=layout_class,
            detection_status="not_applicable",
            abstention_codes=(),
            label_slot_lanes=(),
        )
    if len(scan_values) != 2:
        raise KP1979SourceError("a detector page must contain exactly two scan bands")
    scan_bands = tuple(_bbox(value, "proposal scan band") for value in scan_values)
    proposal = detect_two_column_label_lattice(
        page_pbm,
        width=PAGE_WIDTH,
        height=PAGE_HEIGHT,
        scan_bands=(scan_bands[0], scan_bands[1]),
    )
    exclusions_value = page.get("proposal_exclusion_bboxes")
    if not isinstance(exclusions_value, list):
        raise KP1979SourceError("proposal_exclusion_bboxes must be an array")
    exclusions = tuple(_bbox(value, "proposal exclusion bbox") for value in exclusions_value)
    label_slot_lanes = _label_slot_bboxes(proposal, exclusions=exclusions)
    return KP1979PageLayoutResult(
        pdf_page_number=page_number,
        page_role=page_role,
        layout_class=layout_class,
        detection_status=proposal.detection_status,
        abstention_codes=proposal.abstention_codes,
        label_slot_lanes=label_slot_lanes,
    )


def _verify_public_contracts(
    source_contract_bytes: bytes,
    page_map_bytes: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_fixed_bytes(
        source_contract_bytes,
        label="source contract",
        expected_size=EXPECTED_SOURCE_CONTRACT_BYTE_SIZE,
        expected_sha256=EXPECTED_SOURCE_CONTRACT_SHA256,
        max_bytes=MAX_CONTRACT_BYTES,
    )
    _require_fixed_bytes(
        page_map_bytes,
        label="page map",
        expected_size=EXPECTED_PAGE_MAP_BYTE_SIZE,
        expected_sha256=EXPECTED_PAGE_MAP_SHA256,
        max_bytes=MAX_PAGE_MAP_BYTES,
    )
    source_contract = _decode_schema_object(
        source_contract_bytes,
        label="source contract",
        schema_filename=SOURCE_SCHEMA,
    )
    page_map = _decode_schema_object(
        page_map_bytes,
        label="page map",
        schema_filename=PAGE_MAP_SCHEMA,
    )
    commitment = _mapping(page_map.get("source_contract"), "source contract commitment")
    expected_commitment = {
        "contract_id": source_contract.get("contract_id"),
        "sha256": _tagged_sha256(source_contract_bytes),
        "byte_size": len(source_contract_bytes),
    }
    if dict(commitment) != expected_commitment:
        raise KP1979SourceError("page map cites different source-contract bytes")
    _verify_page_map_semantics(page_map)
    return source_contract, page_map


def _verify_source_snapshot(source_contract: Mapping[str, Any], source_bytes: bytes) -> None:
    if (
        not isinstance(source_bytes, bytes)
        or not source_bytes
        or len(source_bytes) > MAX_SOURCE_BYTES
    ):
        raise KP1979SourceError("source snapshot has an invalid byte length")
    source = _mapping(source_contract.get("source"), "source")
    expected_size = _integer(source.get("byte_size"), "source byte_size")
    if len(source_bytes) != expected_size:
        raise KP1979SourceError("source snapshot byte size does not match the contract")
    if _tagged_sha256(source_bytes) != _string(source.get("sha256"), "source sha256"):
        raise KP1979SourceError("source snapshot digest does not match the contract")
    if not source_bytes.startswith(b"%PDF-"):
        raise KP1979SourceError("source snapshot lacks a PDF signature")
    if b"%%EOF" not in source_bytes[-1024:]:
        raise KP1979SourceError("source snapshot lacks a terminal PDF marker")


def _consume_verified_pages(
    page_map: Mapping[str, Any],
    supplied_pages: Iterable[tuple[int, bytes]],
) -> None:
    supplied = iter(supplied_pages)
    for page in _page_entries(page_map):
        page_number, page_bytes = _next_page(supplied)
        expected_page_number = _integer(page.get("pdf_page_number"), "pdf_page_number")
        if page_number != expected_page_number:
            raise KP1979SourceError("page bitmap order differs from the fixed page map")
        _verify_page_bitmap(page, page_bytes)
    try:
        next(supplied)
    except StopIteration:
        return
    raise KP1979SourceError("page bitmap iterator contains an unexpected extra page")


def _next_page(supplied: Iterator[tuple[int, bytes]]) -> tuple[int, bytes]:
    try:
        value = next(supplied)
    except StopIteration as error:
        raise KP1979SourceError("page bitmap iterator ended before the fixed page map") from error
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not isinstance(value[0], int)
        or isinstance(value[0], bool)
        or not isinstance(value[1], bytes)
    ):
        raise KP1979SourceError("page bitmap iterator yielded an invalid item")
    return value


def _verify_page_bitmap(page: Mapping[str, Any], page_bytes: bytes) -> None:
    if not page_bytes or len(page_bytes) > MAX_PAGE_PBM_BYTES:
        raise KP1979SourceError("page bitmap has an invalid byte length")
    header = f"P4\n{PAGE_WIDTH} {PAGE_HEIGHT}\n".encode("ascii")
    if not page_bytes.startswith(header):
        raise KP1979SourceError("page bitmap lacks the canonical raw PBM header")
    payload = page_bytes[len(header) :]
    if len(payload) != ((PAGE_WIDTH + 7) // 8) * PAGE_HEIGHT:
        raise KP1979SourceError("page bitmap payload has an invalid byte size")
    if _tagged_sha256(page_bytes) != _string(
        page.get("canonical_pbm_sha256"),
        "canonical PBM sha256",
    ):
        raise KP1979SourceError("page bitmap digest does not match the fixed page map")
    if _tagged_sha256(payload) != _string(
        page.get("pixel_payload_sha256"),
        "pixel payload sha256",
    ):
        raise KP1979SourceError("page pixel digest does not match the fixed page map")


def _verify_page_map_semantics(page_map: Mapping[str, Any]) -> None:
    pages = _page_entries(page_map)
    if len(pages) != LAST_MAPPED_PDF_PAGE - FIRST_MAPPED_PDF_PAGE + 1:
        raise KP1979SourceError("page map does not contain the complete fixed range")
    for expected_page, page in zip(
        range(FIRST_MAPPED_PDF_PAGE, LAST_MAPPED_PDF_PAGE + 1),
        pages,
        strict=True,
    ):
        if (
            page.get("pdf_page_number") != expected_page
            or page.get("page_index") != expected_page - 1
            or page.get("printed_page_label") != str(expected_page - 1)
            or page.get("canonical_pbm_filename") != f"page-{expected_page:03d}.pbm"
            or page.get("pdf_image_object_number")
            != (4961 if expected_page == 2 else 3 * expected_page + 1)
        ):
            raise KP1979SourceError("page map identity sequence is invalid")
        expected = _expected_page_semantics(expected_page)
        observed = (
            page.get("page_role"),
            page.get("layout_class"),
            page.get("corpus_sequence_role"),
            page.get("label_side"),
            page.get("contains_linguistic_sequence_candidates"),
        )
        if observed != expected:
            raise KP1979SourceError("page map section semantics are invalid")


def _expected_page_semantics(page: int) -> tuple[str, str, str, str | None, bool]:
    if 2 <= page <= 19:
        return ("non_corpus_negative", "non_corpus", "none", None, False)
    if 20 <= page <= 21:
        return ("sign_list_negative", "sign_list_10_column", "none", None, False)
    if 22 <= page <= 78:
        return (
            "corpus_data",
            "identifier_order_2_column_labels_right",
            "base_rendering",
            "right",
            True,
        )
    if 79 <= page <= 128:
        return (
            "corpus_data",
            "sorted_end_2_column_labels_left",
            "internal_crosscheck",
            "left",
            True,
        )
    if page == 129:
        return (
            "auxiliary_catalog_only",
            "sorted_end_auxiliary_grid_8",
            "catalog_metadata_only",
            None,
            False,
        )
    if page == 130:
        return (
            "auxiliary_catalog_only",
            "sorted_end_auxiliary_grid_6",
            "catalog_metadata_only",
            None,
            False,
        )
    return (
        "corpus_data",
        "sorted_beginning_2_column_labels_right",
        "internal_crosscheck",
        "right",
        True,
    )


def _verify_expected_layout_gate(result: KP1979PageLayoutResult) -> None:
    if result.page_role == "corpus_data":
        if result.detection_status != "proposed" or len(result.label_slot_lanes) != 2:
            raise KP1979SourceError("normal corpus page failed the fixed layout detector")
        if result.pdf_page_number == 180:
            forbidden = (3000, 5000, 4550, 5850)
            if any(
                _rectangles_intersect(candidate, forbidden)
                for lane in result.label_slot_lanes
                for candidate in lane
            ):
                raise KP1979SourceError("page 180 prose mask retained a label-slot candidate")
        return
    if result.pdf_page_number in {8, 20, 21, 129, 130} and (
        result.detection_status != "abstained" or any(result.label_slot_lanes)
    ):
        raise KP1979SourceError("hard-negative or auxiliary page produced label-slot candidates")


def _label_slot_bboxes(
    proposal: TwoColumnLayoutProposal,
    *,
    exclusions: tuple[tuple[int, int, int, int], ...],
) -> tuple[tuple[tuple[int, int, int, int], ...], ...]:
    if proposal.detection_status != "proposed":
        return ()
    lanes: list[tuple[tuple[int, int, int, int], ...]] = []
    for lane in proposal.lanes:
        x0, _, x1, _ = lane.scan_bbox
        boxes: list[tuple[int, int, int, int]] = []
        for y in lane.candidate_y:
            bbox = (x0, y, x1, min(PAGE_HEIGHT, y + ROW_WINDOW_HEIGHT))
            if not any(_rectangles_intersect(bbox, exclusion) for exclusion in exclusions):
                boxes.append(bbox)
        lanes.append(tuple(boxes))
    return tuple(lanes)


def _rectangles_intersect(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    return (
        first[0] < second[2]
        and first[2] > second[0]
        and first[1] < second[3]
        and first[3] > second[1]
    )


def _page_entries(page_map: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = page_map.get("pages")
    if not isinstance(value, list):
        raise KP1979SourceError("page map pages must be an array")
    return [_mapping(page, "page map entry") for page in value]


def _decode_schema_object(
    raw_bytes: bytes,
    *,
    label: str,
    schema_filename: str,
) -> dict[str, Any]:
    try:
        value = decode_json(raw_bytes, source=label)
    except ValueError as error:
        raise KP1979SourceError(f"{label} is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1979SourceError(f"{label} must decode to an object")
    issues = validate_schema_instance(value, _default_schema_path(schema_filename))
    if issues:
        first = issues[0]
        raise KP1979SourceError(f"{label} schema invalid at {first.path}")
    return value


def _require_fixed_bytes(
    raw_bytes: bytes,
    *,
    label: str,
    expected_size: int,
    expected_sha256: str,
    max_bytes: int,
) -> None:
    if (
        not isinstance(raw_bytes, bytes)
        or not raw_bytes
        or len(raw_bytes) > max_bytes
        or len(raw_bytes) != expected_size
        or _tagged_sha256(raw_bytes) != expected_sha256
    ):
        raise KP1979SourceError(f"{label} does not match the fixed V1 snapshot")


def _tagged_sha256(raw_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1979SourceError(f"{label} must be an object")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise KP1979SourceError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise KP1979SourceError(f"{label} must be an integer")
    return value


def _bbox(value: object, label: str) -> tuple[int, int, int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        raise KP1979SourceError(f"{label} must contain four integers")
    return (value[0], value[1], value[2], value[3])
