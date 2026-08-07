"""Catalog/geometry-bound provisional roster for KP1979 sign-list glyphs."""

from __future__ import annotations

import hashlib
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import decode_json, encode_json
from .kp1979_glyph_match import (
    MAX_TEMPLATE_DIMENSION,
    MAX_TEMPLATE_PBM_BYTES,
    parse_canonical_pbm,
)
from .schema_validation import validate_schema_instance

ROSTER_SCHEMA = "kp1979-sign-template-roster.schema.json"
MANIFEST_ID = "KP1979:SIGN-TEMPLATE-ROSTER:MACHINE-PROVISIONAL:V1"
STATUS = "private_machine_provisional_templates_require_independent_validation"
SCIENTIFIC_SCOPE = (
    "private machine-provisional KP1979 sign-list glyph roster for language-blind shape "
    "comparison only; no accepted sign identity, reading, language, meaning, translation, "
    "row transcription, evaluation result, or decipherment inference is present"
)
MAX_CATALOG_BYTES = 32 * 1024 * 1024
MAX_GEOMETRY_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_TEMPLATE_ROSTER_BYTES = 16 * 1024 * 1024
MAX_INPUT_ITEMS = 5_000
MAX_NESTING_DEPTH = 64
OCCUPIED = "machine_provisional_occupied"
BLANK = "machine_provisional_blank"
_TAGGED_SHA256 = re.compile(r"\Asha256:[0-9a-f]{64}\Z")
_UNTAGGED_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_CELL_ID = re.compile(r"\AKP1979:P(20|21):L([0-9]{2}):R([0-9]{2})\Z")
_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "accepted_sign",
        "accepted_sign_sequence",
        "code",
        "deciphered_text",
        "identifier",
        "language",
        "meaning",
        "ocr",
        "phonetic_value",
        "reading",
        "reading_direction",
        "sign_sequence",
        "transcription",
        "translation",
    }
)
WITHHELD_FIELDS = (
    "all_ocr_output",
    "all_reading_values",
    "all_language_values",
    "all_meaning_values",
    "all_translation_values",
    "all_row_transcriptions",
    "all_accepted_sign_identities",
    "all_evaluation_values",
)

JsonObject = dict[str, Any]
GlyphLoader = Callable[[str], bytes]


class KP1979SignTemplateRosterError(ValueError):
    """Raised when private catalog, geometry, glyph, or roster bytes fail closed."""


@dataclass(frozen=True, slots=True)
class TemplateBinding:
    """One validated private glyph commitment needed by the shape matcher."""

    variant_id: str
    catalog_rank: int
    sha256: str
    byte_size: int
    width: int
    height: int


def _default_schema_path() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / ROSTER_SCHEMA
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(f"schemas/{ROSTER_SCHEMA}")
    return Path(str(package_candidate))


def build_sign_template_roster(
    catalog_bytes: bytes,
    geometry_manifest_bytes: bytes,
    glyph_loader: GlyphLoader,
) -> JsonObject:
    """Build an exact private roster from provisional occupancy and committed glyph PBMs."""

    if not callable(glyph_loader):
        raise KP1979SignTemplateRosterError("glyph loader is not callable")
    catalog = _decode_object(
        catalog_bytes,
        label="resolved catalog",
        max_bytes=MAX_CATALOG_BYTES,
    )
    if catalog_bytes != encode_json(catalog):
        raise KP1979SignTemplateRosterError("resolved catalog bytes are not canonical")
    geometry = _decode_object(
        geometry_manifest_bytes,
        label="geometry manifest",
        max_bytes=MAX_GEOMETRY_MANIFEST_BYTES,
    )
    catalog_inputs = _mapping(catalog.get("inputs"), "resolved catalog inputs")
    expected_geometry_digest = _untagged_sha256(
        catalog_inputs.get("signlist_manifest_sha256"),
        "resolved catalog geometry digest",
    )
    if hashlib.sha256(geometry_manifest_bytes).hexdigest() != expected_geometry_digest:
        raise KP1979SignTemplateRosterError(
            "resolved catalog does not bind the exact geometry manifest bytes"
        )

    catalog_items = _list(catalog.get("items"), "resolved catalog items")
    geometry_items = _list(geometry.get("items"), "geometry manifest items")
    if (
        not catalog_items
        or len(catalog_items) != len(geometry_items)
        or len(catalog_items) > MAX_INPUT_ITEMS
    ):
        raise KP1979SignTemplateRosterError("catalog and geometry item coverage differs")

    templates: list[JsonObject] = []
    seen_cell_ids: set[str] = set()
    for position, (catalog_value, geometry_value) in enumerate(
        zip(catalog_items, geometry_items, strict=True)
    ):
        catalog_item = _mapping(catalog_value, f"resolved catalog item {position}")
        geometry_item = _mapping(geometry_value, f"geometry manifest item {position}")
        cell_id = _cell_id(geometry_item.get("cell_id"), "geometry cell ID")
        if cell_id in seen_cell_ids:
            raise KP1979SignTemplateRosterError("geometry manifest contains a duplicate cell ID")
        seen_cell_ids.add(cell_id)
        if catalog_item.get("cell_id") != cell_id:
            raise KP1979SignTemplateRosterError("catalog and geometry cell order differs")
        _verify_join_identity(catalog_item, geometry_item, cell_id=cell_id)

        occupancy = _string(catalog_item.get("occupancy"), "resolved occupancy")
        transferred = _string(
            catalog_item.get("transferred_occupancy"),
            "transferred occupancy",
        )
        if transferred != geometry_item.get("occupancy"):
            raise KP1979SignTemplateRosterError("transferred occupancy differs from geometry")
        if occupancy == BLANK:
            if catalog_item.get("catalog_rank") is not None:
                raise KP1979SignTemplateRosterError("blank catalog item contains a selected rank")
            continue
        if occupancy != OCCUPIED:
            raise KP1979SignTemplateRosterError("resolved occupancy state is invalid")

        catalog_rank = _positive_integer(catalog_item.get("catalog_rank"), "catalog rank")
        candidates = _integer_list(
            catalog_item.get("catalog_rank_candidates"),
            "catalog rank candidates",
        )
        if catalog_rank not in candidates:
            raise KP1979SignTemplateRosterError("selected rank is absent from its candidates")
        if catalog_item.get("catalog_rank_status") not in {
            "machine_provisional_unique",
            "ai_visual_provisional_from_contact_sheet",
        }:
            raise KP1979SignTemplateRosterError("occupied catalog-rank status is invalid")

        cell_bbox = _bbox(geometry_item.get("cell_bbox"), "cell bbox")
        glyph_bbox = _bbox(geometry_item.get("glyph_bbox"), "glyph bbox")
        if not (
            cell_bbox[0] <= glyph_bbox[0] < glyph_bbox[2] <= cell_bbox[2]
            and cell_bbox[1] <= glyph_bbox[1] < glyph_bbox[3] <= cell_bbox[3]
        ):
            raise KP1979SignTemplateRosterError("glyph bbox lies outside its source cell")
        expected_width = glyph_bbox[2] - glyph_bbox[0]
        expected_height = glyph_bbox[3] - glyph_bbox[1]
        if expected_width > MAX_TEMPLATE_DIMENSION or expected_height > MAX_TEMPLATE_DIMENSION:
            raise KP1979SignTemplateRosterError("glyph dimensions exceed their limit")
        expected_byte_size = _positive_integer(
            geometry_item.get("glyph_crop_byte_size"),
            "glyph byte size",
        )
        if expected_byte_size > MAX_TEMPLATE_PBM_BYTES:
            raise KP1979SignTemplateRosterError("glyph byte size exceeds its limit")
        expected_sha256 = _tagged_sha256(
            geometry_item.get("glyph_crop_sha256"),
            "glyph SHA-256",
        )
        try:
            glyph_bytes = glyph_loader(cell_id)
        except (OSError, ValueError) as error:
            raise KP1979SignTemplateRosterError("glyph loader failed") from error
        if not isinstance(glyph_bytes, bytes):
            raise KP1979SignTemplateRosterError("glyph loader did not return bytes")
        if len(glyph_bytes) != expected_byte_size or _tagged_digest(glyph_bytes) != expected_sha256:
            raise KP1979SignTemplateRosterError("glyph bytes differ from geometry commitment")
        try:
            mask = parse_canonical_pbm(glyph_bytes)
        except ValueError as error:
            raise KP1979SignTemplateRosterError("glyph PBM is not canonical") from error
        if mask.ink_count == 0:
            raise KP1979SignTemplateRosterError("occupied glyph PBM contains no ink")
        if mask.width != expected_width or mask.height != expected_height:
            raise KP1979SignTemplateRosterError("glyph dimensions differ from its bbox")
        templates.append(
            {
                "variant_id": cell_id,
                "catalog_rank": catalog_rank,
                "glyph": {
                    "sha256": expected_sha256,
                    "byte_size": expected_byte_size,
                    "width": expected_width,
                    "height": expected_height,
                },
            }
        )
    if not templates:
        raise KP1979SignTemplateRosterError("resolved catalog contains no template glyphs")

    roster: JsonObject = {
        "schema_version": "0.1.0",
        "manifest_id": MANIFEST_ID,
        "record_state": "machine_provisional_private",
        "status": STATUS,
        "scientific_scope": SCIENTIFIC_SCOPE,
        "input_bindings": {
            "resolved_catalog": {
                "id": _string(catalog.get("record_id"), "resolved catalog record ID"),
                "sha256": _tagged_digest(catalog_bytes),
                "byte_size": len(catalog_bytes),
            },
            "geometry_manifest": {
                "id": _string(geometry.get("record_id"), "geometry manifest record ID"),
                "sha256": _tagged_digest(geometry_manifest_bytes),
                "byte_size": len(geometry_manifest_bytes),
            },
        },
        "template_policy": {
            "membership_authority": "catalog_geometry_bound_machine_provisional_occupancy",
            "variant_identity": "catalog_geometry_bound_provisional_cell_id",
            "catalog_rank_role": (
                "machine_provisional_shape_class_only_not_accepted_sign_identity"
            ),
            "rank_scoring": "minimum_cost_variant_per_rank_without_variant_count_bonus",
            "glyph_encoding": "canonical_raw_P4_MSB_first_zero_unused_low_bits",
        },
        "withheld_fields": list(WITHHELD_FIELDS),
        "templates": templates,
        "assurances": {
            "catalog_geometry_raw_bytes_bound": True,
            "catalog_geometry_item_join_verified": True,
            "glyph_crop_commitments_verified": True,
            "catalog_resolution_inputs_reverified": False,
            "signlist_source_pages_reverified": False,
            "geometry_accepted": False,
            "catalog_values_accepted": False,
            "sign_identity_accepted": False,
            "human_review_complete": False,
            "public_release_authorized": False,
            "evaluation_admissible": False,
            "decipherment": False,
            "prize_submission_eligible": False,
        },
    }
    _validate_roster(roster)
    if len(encode_json(roster)) > MAX_TEMPLATE_ROSTER_BYTES:
        raise KP1979SignTemplateRosterError("generated template roster exceeds its byte limit")
    return roster


def verify_sign_template_roster_bytes(
    catalog_bytes: bytes,
    geometry_manifest_bytes: bytes,
    glyph_loader: GlyphLoader,
    roster_bytes: bytes,
) -> dict[str, bool | str]:
    """Rebuild and exact-byte-check one untrusted private template roster."""

    roster = _decode_object(
        roster_bytes,
        label="sign template roster",
        max_bytes=MAX_TEMPLATE_ROSTER_BYTES,
    )
    _validate_roster(roster)
    expected = build_sign_template_roster(
        catalog_bytes,
        geometry_manifest_bytes,
        glyph_loader,
    )
    if roster != expected or roster_bytes != encode_json(expected):
        raise KP1979SignTemplateRosterError(
            "sign template roster differs from canonical glyph recomputation"
        )
    return {
        "valid": True,
        "claim_class": "private_kp1979_sign_template_roster_only",
        "catalog_geometry_raw_bytes_bound": True,
        "catalog_geometry_item_join_verified": True,
        "glyph_crop_commitments_verified": True,
        "roster_canonical_bytes_verified": True,
        "catalog_values_accepted": False,
        "sign_identity_accepted": False,
        "human_review_complete": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
    }


def template_ids(roster_bytes: bytes) -> tuple[str, ...]:
    """Return only validated manifest IDs so a caller can build a closed loader allowlist."""

    roster = _decode_object(
        roster_bytes,
        label="sign template roster",
        max_bytes=MAX_TEMPLATE_ROSTER_BYTES,
    )
    _validate_roster(roster)
    if roster_bytes != encode_json(roster):
        raise KP1979SignTemplateRosterError("sign template roster bytes are not canonical")
    return tuple(
        _cell_id(_mapping(item, "template item").get("variant_id"), "template variant ID")
        for item in _list(roster.get("templates"), "templates")
    )


def template_bindings(roster_bytes: bytes) -> tuple[TemplateBinding, ...]:
    """Return exact matcher inputs from one canonical, schema-valid private roster."""

    roster = _decode_object(
        roster_bytes,
        label="sign template roster",
        max_bytes=MAX_TEMPLATE_ROSTER_BYTES,
    )
    _validate_roster(roster)
    if roster_bytes != encode_json(roster):
        raise KP1979SignTemplateRosterError("sign template roster bytes are not canonical")
    bindings: list[TemplateBinding] = []
    for item_value in _list(roster.get("templates"), "templates"):
        item = _mapping(item_value, "template item")
        glyph = _mapping(item.get("glyph"), "template glyph")
        bindings.append(
            TemplateBinding(
                variant_id=_cell_id(item.get("variant_id"), "template variant ID"),
                catalog_rank=_positive_integer(item.get("catalog_rank"), "template catalog rank"),
                sha256=_tagged_sha256(glyph.get("sha256"), "template glyph SHA-256"),
                byte_size=_positive_integer(glyph.get("byte_size"), "template glyph byte size"),
                width=_positive_integer(glyph.get("width"), "template glyph width"),
                height=_positive_integer(glyph.get("height"), "template glyph height"),
            )
        )
    return tuple(bindings)


def _validate_roster(roster: JsonObject) -> None:
    _reject_forbidden_keys(roster)
    issues = validate_schema_instance(roster, _default_schema_path())
    if issues:
        raise KP1979SignTemplateRosterError(
            f"sign template roster schema invalid at {issues[0].path}"
        )
    ids = template_ids_from_value(roster)
    if len(ids) != len(set(ids)):
        raise KP1979SignTemplateRosterError("sign template roster has duplicate variant IDs")


def template_ids_from_value(roster: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _cell_id(_mapping(item, "template item").get("variant_id"), "template variant ID")
        for item in _list(roster.get("templates"), "templates")
    )


def _verify_join_identity(
    catalog_item: Mapping[str, Any],
    geometry_item: Mapping[str, Any],
    *,
    cell_id: str,
) -> None:
    page_index = _nonnegative_integer(geometry_item.get("page_index"), "geometry page index")
    pdf_page_number = _positive_integer(
        geometry_item.get("pdf_page_number"),
        "geometry PDF page number",
    )
    lane_index = _nonnegative_integer(geometry_item.get("lane_index"), "geometry lane index")
    row_index = _nonnegative_integer(geometry_item.get("row_index"), "geometry row index")
    if pdf_page_number not in {20, 21} or page_index != pdf_page_number - 1:
        raise KP1979SignTemplateRosterError("geometry item is outside sign-list pages")
    expected_cell_id = f"KP1979:P{pdf_page_number}:L{lane_index:02d}:R{row_index:02d}"
    if cell_id != expected_cell_id:
        raise KP1979SignTemplateRosterError("geometry cell ID is not source-derived")
    for key, expected in (
        ("page_index", page_index),
        ("lane_index", lane_index),
        ("row_index", row_index),
    ):
        if catalog_item.get(key) != expected:
            raise KP1979SignTemplateRosterError("catalog and geometry identities differ")


def _decode_object(raw_bytes: bytes, *, label: str, max_bytes: int) -> JsonObject:
    if not isinstance(raw_bytes, bytes) or not raw_bytes or len(raw_bytes) > max_bytes:
        raise KP1979SignTemplateRosterError(f"{label} byte length is invalid")
    try:
        value = decode_json(raw_bytes, source=label)
    except (RecursionError, ValueError) as error:
        raise KP1979SignTemplateRosterError(f"{label} is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1979SignTemplateRosterError(f"{label} must decode to an object")
    _check_nesting(value)
    return value


def _check_nesting(value: object) -> None:
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > MAX_NESTING_DEPTH:
            raise KP1979SignTemplateRosterError("JSON nesting exceeds its limit")
        if isinstance(current, Mapping):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)


def _reject_forbidden_keys(value: object) -> None:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            if _FORBIDDEN_OUTPUT_KEYS.intersection(current):
                raise KP1979SignTemplateRosterError("template roster contains an answer field")
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1979SignTemplateRosterError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise KP1979SignTemplateRosterError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise KP1979SignTemplateRosterError(f"{label} must be a bounded string")
    return value


def _cell_id(value: object, label: str) -> str:
    result = _string(value, label)
    if _CELL_ID.fullmatch(result) is None:
        raise KP1979SignTemplateRosterError(f"{label} is invalid")
    return result


def _nonnegative_integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 1_000_000:
        raise KP1979SignTemplateRosterError(f"{label} must be a nonnegative integer")
    return value


def _positive_integer(value: object, label: str) -> int:
    result = _nonnegative_integer(value, label)
    if result == 0:
        raise KP1979SignTemplateRosterError(f"{label} must be positive")
    return result


def _integer_list(value: object, label: str) -> list[int]:
    values = _list(value, label)
    result = [_positive_integer(item, label) for item in values]
    if not result or len(result) != len(set(result)) or len(result) > MAX_INPUT_ITEMS:
        raise KP1979SignTemplateRosterError(f"{label} is invalid")
    return result


def _bbox(value: object, label: str) -> tuple[int, int, int, int]:
    values = _list(value, label)
    if len(values) != 4:
        raise KP1979SignTemplateRosterError(f"{label} must contain four integers")
    x0, y0, x1, y1 = (_nonnegative_integer(item, label) for item in values)
    if not x0 < x1 or not y0 < y1:
        raise KP1979SignTemplateRosterError(f"{label} is empty or inverted")
    return x0, y0, x1, y1


def _tagged_sha256(value: object, label: str) -> str:
    result = _string(value, label)
    if _TAGGED_SHA256.fullmatch(result) is None:
        raise KP1979SignTemplateRosterError(f"{label} is invalid")
    return result


def _untagged_sha256(value: object, label: str) -> str:
    result = _string(value, label)
    if _UNTAGGED_SHA256.fullmatch(result) is None:
        raise KP1979SignTemplateRosterError(f"{label} is invalid")
    return result


def _tagged_digest(raw_bytes: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
