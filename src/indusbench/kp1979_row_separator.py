"""Pure, deterministic separation of KP1979 signs from printed row labels.

The assignment's proposed label rectangle is only a locator.  Its left edge is
not an observed separator and may cross foreground.  This adapter therefore
considers only maximal columns that are white for the complete row height,
lets the shape-only row matcher score every eligible separation, and keeps the
globally best paths with the observed separator attached as provenance.

No identifier text, language, reading direction, sign frequency, or page
partition is available to this module.  It accepts exact bytes and in-memory
objects only; source-boundary and private-file enforcement remain caller tasks.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

from indusbench.kp1979_glyph_match import (
    MAX_ROW_HEIGHT,
    MAX_ROW_PBM_BYTES,
    MAX_ROW_WIDTH,
    MatcherConfig,
    TemplateIndex,
    match_row_sequence,
    parse_canonical_pbm,
)

ROW_SEPARATOR_METHOD = "maximal-full-height-white-gap-locator-neighbours-shape-comparison-v2"
MAX_SEPARATOR_CANDIDATES = 64

_ROW_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9:._-]{0,159}\Z")


class KP1979RowSeparatorError(ValueError):
    """Raised when the row or label locator cannot be compared safely."""


def match_row_with_separator(
    *,
    row_id: str,
    row_pbm: bytes,
    proposed_label_bbox: Sequence[int],
    index: TemplateIndex,
    config: MatcherConfig,
) -> dict[str, Any]:
    """Match signs after comparing observed white-gap separator alternatives.

    Coordinates in ``proposed_label_bbox`` are relative to ``row_pbm``.  A cut
    is always the right edge of an observed, maximal, full-height white-column
    gap.  Eligible gaps contact or overlap the locator, or are the nearest
    observed gaps immediately to its left and right.  In particular, the
    proposed label rectangle's x0 coordinate is never copied as an unobserved
    cut.  A gap-derived right edge may legitimately have the same numeric
    coordinate.
    """

    if not isinstance(row_id, str) or _ROW_ID.fullmatch(row_id) is None:
        raise KP1979RowSeparatorError("row ID is invalid")
    if not isinstance(row_pbm, bytes) or len(row_pbm) > MAX_ROW_PBM_BYTES:
        raise KP1979RowSeparatorError("row PBM byte size exceeds its limit")
    if not isinstance(index, TemplateIndex):
        raise KP1979RowSeparatorError("template index has an invalid type")
    if not isinstance(config, MatcherConfig):
        raise KP1979RowSeparatorError("matcher configuration has an invalid type")

    row_mask = parse_canonical_pbm(row_pbm)
    if row_mask.width > MAX_ROW_WIDTH or row_mask.height > MAX_ROW_HEIGHT:
        raise KP1979RowSeparatorError("row PBM dimensions exceed their limit")
    locator = _validate_locator(
        proposed_label_bbox,
        row_width=row_mask.width,
        row_height=row_mask.height,
    )
    gaps = _separator_gap_candidates(row_mask.rows, row_mask.width, locator)
    if len(gaps) > MAX_SEPARATOR_CANDIDATES:
        raise KP1979RowSeparatorError("row has too many separator alternatives")

    base: dict[str, Any] = {
        "row_id": row_id,
        "visual_order": "left_to_right_coordinate_order_not_reading_direction",
        "proposed_label_bbox": list(locator),
        "separator_method": ROW_SEPARATOR_METHOD,
    }
    if not gaps:
        return {
            **base,
            "proposal_status": "no_match",
            "abstention_code": "no_full_height_white_gap_intersects_locator",
            "candidate_paths": [],
            "gates": {
                "separator_found": False,
                "separator_consensus_passed": False,
                "best_matcher_proposed": False,
            },
        }

    alternatives: list[dict[str, Any]] = []
    for candidate_index, (gap_x0, gap_x1, locator_relation) in enumerate(gaps):
        # The right edge includes at least one observed white column in the
        # matcher region, unlike cutting at the foreground-facing gap edge.
        cut_x = gap_x1
        matcher_result = match_row_sequence(
            row_id=row_id,
            row_pbm=row_pbm,
            sign_region_bbox=(0, 0, cut_x, row_mask.height),
            index=index,
            config=config,
        )
        locator_intersection = _locator_intersection_bbox(
            gap_x0,
            gap_x1,
            locator=locator,
            relation=locator_relation,
        )
        provenance = {
            "candidate_index": candidate_index,
            "full_height_white_gap_bbox": [gap_x0, 0, gap_x1, row_mask.height],
            "locator_relation": locator_relation,
            "locator_intersection_bbox": locator_intersection,
            "cut_x": cut_x,
        }
        matcher_paths = matcher_result.get("candidate_paths")
        if not isinstance(matcher_paths, list):
            raise KP1979RowSeparatorError("row matcher returned invalid candidate paths")
        for matcher_path in matcher_paths:
            alternatives.append(
                _candidate_from_matcher(
                    matcher_path,
                    provenance=provenance,
                    matcher_result=matcher_result,
                )
            )

    if not alternatives:
        return {
            **base,
            "proposal_status": "no_match",
            "abstention_code": "no_separator_candidate_path",
            "candidate_paths": [],
            "gates": {
                "separator_found": True,
                "separator_consensus_passed": False,
                "best_matcher_proposed": False,
            },
        }

    alternatives.sort(key=_global_path_sort_key)
    best = alternatives[0]
    separator_conflict = _has_competing_separator(
        best,
        alternatives,
    )
    best_matcher_proposed = best["matcher_proposal_status"] == "proposed"
    if separator_conflict:
        proposal_status = "segmentation_ambiguous"
        abstention_code = "competing_separator_alternatives"
    else:
        proposal_status = best["matcher_proposal_status"]
        abstention_code = best["matcher_abstention_code"]

    best_cost = _exact_int(best.get("total_cost"), "matcher path total cost")
    output_paths: list[dict[str, Any]] = []
    for path_index, alternative in enumerate(alternatives[: config.top_paths]):
        output_paths.append(
            {
                "path_index": path_index,
                "total_cost": alternative["total_cost"],
                "margin_from_best": alternative["total_cost"] - best_cost,
                "separator_provenance": alternative["separator_provenance"],
                "matcher_path_index": alternative["matcher_path_index"],
                "matcher_proposal_status": alternative["matcher_proposal_status"],
                "matcher_abstention_code": alternative["matcher_abstention_code"],
                "matcher_gates": alternative["matcher_gates"],
                "segments": alternative["segments"],
            }
        )
    return {
        **base,
        "proposal_status": proposal_status,
        "abstention_code": abstention_code,
        "candidate_paths": output_paths,
        "gates": {
            "separator_found": True,
            "separator_consensus_passed": not separator_conflict,
            "best_matcher_proposed": best_matcher_proposed,
        },
    }


def _validate_locator(
    value: Sequence[int],
    *,
    row_width: int,
    row_height: int,
) -> tuple[int, int, int, int]:
    if len(value) != 4 or any(
        not isinstance(item, int) or isinstance(item, bool) for item in value
    ):
        raise KP1979RowSeparatorError("proposed label bbox must contain four integers")
    x0, y0, x1, y1 = value
    if not 0 <= x0 < x1 <= row_width or not 0 <= y0 < y1 <= row_height:
        raise KP1979RowSeparatorError("proposed label bbox lies outside the row crop")
    return x0, y0, x1, y1


def _separator_gap_candidates(
    rows: Sequence[int],
    width: int,
    locator: tuple[int, int, int, int],
) -> list[tuple[int, int, str]]:
    ink_columns = 0
    for row in rows:
        ink_columns |= row
    all_gaps: list[tuple[int, int]] = []
    start: int | None = None
    for x in range(width):
        has_ink = bool(ink_columns & (1 << (width - 1 - x)))
        if not has_ink and start is None:
            start = x
        elif has_ink and start is not None:
            if start != 0:
                all_gaps.append((start, x))
            start = None
    # A separator must have foreground somewhere on both horizontal sides;
    # the possible trailing run intentionally is not appended.

    locator_x0, _locator_y0, locator_x1, _locator_y1 = locator
    selected: dict[tuple[int, int], str] = {}
    for gap_x0, gap_x1 in all_gaps:
        if gap_x1 == locator_x0:
            selected[(gap_x0, gap_x1)] = "left_edge_contact"
        elif gap_x0 < locator_x1 and locator_x0 < gap_x1:
            selected[(gap_x0, gap_x1)] = "positive_overlap"

    strictly_left = [gap for gap in all_gaps if gap[1] < locator_x0]
    if strictly_left:
        nearest_left = max(strictly_left, key=lambda gap: (gap[1], gap[0]))
        selected[nearest_left] = "nearest_left"
    on_or_right = [gap for gap in all_gaps if gap[0] >= locator_x1]
    if on_or_right:
        nearest_right = min(on_or_right, key=lambda gap: (gap[0], gap[1]))
        selected[nearest_right] = (
            "right_edge_contact" if nearest_right[0] == locator_x1 else "nearest_right"
        )
    return [(*gap, selected[gap]) for gap in sorted(selected)]


def _locator_intersection_bbox(
    gap_x0: int,
    gap_x1: int,
    *,
    locator: tuple[int, int, int, int],
    relation: str,
) -> list[int] | None:
    if relation in {"nearest_left", "nearest_right"}:
        return None
    intersection_x0 = max(gap_x0, locator[0])
    intersection_x1 = min(gap_x1, locator[2])
    return [intersection_x0, locator[1], intersection_x1, locator[3]]


def _candidate_from_matcher(
    path: Mapping[str, Any],
    *,
    provenance: Mapping[str, Any],
    matcher_result: Mapping[str, Any],
) -> dict[str, Any]:
    matcher_path_index = _exact_int(path.get("path_index"), "matcher path index")
    total_cost = _exact_int(path.get("total_cost"), "matcher path total cost")
    segments = path.get("segments")
    matcher_gates = matcher_result.get("gates")
    matcher_status = matcher_result.get("proposal_status")
    matcher_code = matcher_result.get("abstention_code")
    if not isinstance(segments, list) or not isinstance(matcher_gates, Mapping):
        raise KP1979RowSeparatorError("row matcher returned an invalid path")
    if not isinstance(matcher_status, str) or not isinstance(matcher_code, str):
        raise KP1979RowSeparatorError("row matcher returned an invalid status")
    return {
        "total_cost": total_cost,
        "separator_provenance": copy.deepcopy(dict(provenance)),
        "matcher_path_index": matcher_path_index,
        "matcher_proposal_status": matcher_status,
        "matcher_abstention_code": matcher_code,
        "matcher_gates": copy.deepcopy(dict(matcher_gates)),
        "segments": copy.deepcopy(segments),
    }


def _exact_int(value: object, description: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise KP1979RowSeparatorError(f"{description} is invalid")
    return value


def _global_path_sort_key(path: Mapping[str, Any]) -> tuple[object, ...]:
    segments = path["segments"]
    provenance = path["separator_provenance"]
    if not isinstance(segments, list) or not isinstance(provenance, Mapping):
        raise KP1979RowSeparatorError("separator candidate has an invalid shape")
    return (
        path["total_cost"],
        sum(
            1
            for segment in segments
            if isinstance(segment, Mapping) and segment.get("segment_kind") == "unmatched_ink"
        ),
        len(segments),
        _path_signature(path),
        tuple(provenance["full_height_white_gap_bbox"]),
        path["matcher_path_index"],
    )


def _path_signature(path: Mapping[str, Any]) -> tuple[object, ...]:
    segments = path.get("segments")
    if not isinstance(segments, list):
        raise KP1979RowSeparatorError("separator candidate segments are invalid")
    signature: list[tuple[object, ...]] = []
    for segment in segments:
        if not isinstance(segment, Mapping):
            raise KP1979RowSeparatorError("separator candidate segment is invalid")
        kind = segment.get("segment_kind")
        bbox = segment.get("segment_bbox")
        if not isinstance(kind, str) or not isinstance(bbox, list):
            raise KP1979RowSeparatorError("separator candidate segment fields are invalid")
        if kind == "rank_proposal":
            rank = _exact_int(segment.get("catalog_rank"), "catalog rank")
            variants = segment.get("best_variant_ids")
            if not isinstance(variants, list) or any(
                not isinstance(variant, str) for variant in variants
            ):
                raise KP1979RowSeparatorError("best variant IDs are invalid")
            signature.append((kind, rank, tuple(variants), tuple(bbox)))
        elif kind == "unmatched_ink":
            signature.append((kind, tuple(bbox)))
        else:
            raise KP1979RowSeparatorError("separator candidate segment kind is invalid")
    return tuple(signature)


def _has_competing_separator(
    best: Mapping[str, Any],
    alternatives: Sequence[Mapping[str, Any]],
) -> bool:
    best_signature = _path_signature(best)
    best_provenance = best.get("separator_provenance")
    if not isinstance(best_provenance, Mapping):
        raise KP1979RowSeparatorError("best separator provenance is invalid")
    best_candidate = _exact_int(
        best_provenance.get("candidate_index"),
        "best separator candidate index",
    )
    best_by_separator: dict[int, Mapping[str, Any]] = {}
    for alternative in alternatives:
        provenance = alternative.get("separator_provenance")
        if not isinstance(provenance, Mapping):
            raise KP1979RowSeparatorError("separator provenance is invalid")
        candidate_index = _exact_int(
            provenance.get("candidate_index"),
            "separator candidate index",
        )
        best_by_separator.setdefault(candidate_index, alternative)
    for candidate_index, alternative in best_by_separator.items():
        if candidate_index == best_candidate:
            continue
        if _path_signature(alternative) != best_signature:
            return True
    return False
