"""Image-bound independent transcription and adjudication.

This module stops at visual segmentation and sign-inventory identification.  It
does not assign sounds, languages, meanings, translations, or decipherments.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import decode_json, encode_json
from .schema_validation import validate_schema_instance
from .validation import has_errors, validate_artifact

JsonObject = dict[str, Any]
SignKey = tuple[str, str, str]

SCHEMA_VERSION = "0.1.0"
SCIENTIFIC_SCOPE = (
    "visual sign segmentation and inventory identification only; no phonetic, "
    "language, semantic, translation, or decipherment inference"
)
INVENTORY_SCOPE = (
    "graphic sign identity only; no phonetic, language, semantic, translation, "
    "or decipherment assignment"
)
FORBIDDEN_INTERPRETIVE_KEYS = frozenset(
    {
        "decipherment",
        "gloss",
        "language",
        "language_assignment",
        "meaning",
        "phonetic",
        "phonetic_value",
        "semantic_assignment",
        "translation",
    }
)
_KNOWN_DIRECTIONS = frozenset(
    {
        "left_to_right",
        "right_to_left",
        "top_to_bottom",
        "bottom_to_top",
        "boustrophedon",
        "mixed",
    }
)
_EPSILON = 1e-9
_MAX_EVIDENCE_JSON_BYTES = 64 * 1024 * 1024


class TranscriptionReviewError(ValueError):
    """Raised when transcription evidence fails closed."""


@dataclass(frozen=True)
class TranscriptionPromotion:
    """One privately promoted artifact and its byte-level verification summary."""

    artifact: JsonObject
    verification: JsonObject


@dataclass(frozen=True)
class _VerifiedTranscriptionEvidence:
    inventory: JsonObject
    reviews: tuple[JsonObject, ...]
    adjudication: JsonObject
    inventory_sha256: str
    review_sha256: tuple[str, ...]
    adjudication_sha256: str
    summary: JsonObject


def sha256_bytes(raw_bytes: bytes) -> str:
    """Return the project's tagged SHA-256 representation."""

    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


def validate_sign_inventory(inventory_value: Mapping[str, Any]) -> None:
    """Validate semantic invariants not expressible in the JSON schema."""

    inventory = _require_mapping(inventory_value, "sign inventory")
    _reject_interpretive_keys(inventory)
    if inventory.get("schema_version") != SCHEMA_VERSION:
        raise TranscriptionReviewError("unsupported sign inventory schema_version")
    if inventory.get("scientific_scope") != INVENTORY_SCOPE:
        raise TranscriptionReviewError("sign inventory scientific_scope is not fail-closed")

    rights = _require_mapping(inventory.get("rights"), "sign inventory rights")
    if rights.get("analysis_use") not in {"permitted", "denied", "unknown"}:
        raise TranscriptionReviewError("unknown sign inventory analysis_use")

    primary_identifier_scheme = _require_string(
        inventory.get("primary_identifier_scheme"),
        "primary_identifier_scheme",
    )
    source_documents = _require_list(
        inventory.get("source_documents"),
        "sign inventory source_documents",
    )
    document_ids: set[str] = set()
    document_page_counts: dict[str, int | None] = {}
    for index, value in enumerate(source_documents):
        document = _require_mapping(value, f"source document {index}")
        document_id = _require_string(
            document.get("document_id"),
            f"source document {index} document_id",
        )
        if document_id in document_ids:
            raise TranscriptionReviewError("sign inventory contains duplicate source document IDs")
        document_ids.add(document_id)
        page_count = document.get("page_count")
        document_page_counts[document_id] = (
            page_count if isinstance(page_count, int) and not isinstance(page_count, bool) else None
        )
        if (
            rights.get("redistribution")
            and rights.get("derivatives")
            and (not document.get("license_id") or not document.get("rights_evidence_uri"))
        ):
            raise TranscriptionReviewError(
                "redistributable sign inventory needs source-document rights evidence"
            )

    signs = _require_list(inventory.get("signs"), "sign inventory signs")
    if not signs:
        raise TranscriptionReviewError("sign inventory must contain at least one sign")

    sign_ids: set[str] = set()
    project_sign_ids: set[str] = set()
    primary_source_identifiers: set[str] = set()
    evidence_ids: set[str] = set()
    rows: dict[str, Mapping[str, Any]] = {}
    for index, value in enumerate(signs):
        sign = _require_mapping(value, f"sign inventory sign {index}")
        sign_id = _require_string(sign.get("sign_id"), f"sign inventory sign {index} sign_id")
        project_sign_id = _require_string(
            sign.get("project_sign_id"),
            f"sign inventory sign {index} project_sign_id",
        )
        if sign_id in sign_ids:
            raise TranscriptionReviewError("sign inventory contains duplicate sign_id values")
        if project_sign_id in project_sign_ids:
            raise TranscriptionReviewError(
                "sign inventory contains duplicate project_sign_id values"
            )
        sign_ids.add(sign_id)
        project_sign_ids.add(project_sign_id)
        rows[sign_id] = sign

        graphic_sources = _require_list(
            sign.get("graphic_sources"),
            f"sign inventory sign {index} graphic_sources",
        )
        local_evidence_ids: set[str] = set()
        local_evidence_documents: dict[str, str] = {}
        for source_index, source_value in enumerate(graphic_sources):
            source = _require_mapping(
                source_value,
                f"sign inventory sign {index} graphic source {source_index}",
            )
            evidence_id = _require_string(
                source.get("evidence_id"),
                f"sign inventory sign {index} graphic evidence_id",
            )
            if evidence_id in evidence_ids:
                raise TranscriptionReviewError("graphic evidence_id values must be globally unique")
            evidence_ids.add(evidence_id)
            local_evidence_ids.add(evidence_id)
            document_id = _require_string(
                source.get("document_id"),
                f"sign inventory sign {index} graphic document_id",
            )
            if document_id not in document_ids:
                raise TranscriptionReviewError("graphic source cites an unknown source document")
            local_evidence_documents[evidence_id] = document_id
            page_index = source.get("page_index")
            page_count = document_page_counts[document_id]
            if (
                not isinstance(page_index, int)
                or isinstance(page_index, bool)
                or page_index < 0
                or (page_count is not None and page_index >= page_count)
            ):
                raise TranscriptionReviewError(
                    "graphic source page_index is outside the source document"
                )
            _polygon(
                source.get("polygon"),
                f"sign inventory sign {index} graphic polygon",
            )
            if (
                "other"
                in _require_list(
                    source.get("doubt_markers"),
                    f"sign inventory sign {index} doubt_markers",
                )
                and source.get("doubt_notes") is None
            ):
                raise TranscriptionReviewError("other doubt marker requires explanatory notes")

        published_identifiers = _require_list(
            sign.get("published_identifiers"),
            f"sign inventory sign {index} published_identifiers",
        )
        primary_identifiers: list[str] = []
        identifier_keys: set[tuple[str, str, str]] = set()
        for identifier_index, identifier_value in enumerate(published_identifiers):
            identifier = _require_mapping(
                identifier_value,
                f"sign inventory sign {index} published identifier {identifier_index}",
            )
            scheme_id = _require_string(
                identifier.get("scheme_id"),
                f"sign inventory sign {index} identifier scheme_id",
            )
            identifier_value_string = _require_string(
                identifier.get("value"),
                f"sign inventory sign {index} identifier value",
            )
            role = _require_string(
                identifier.get("role"),
                f"sign inventory sign {index} identifier role",
            )
            identifier_key = (scheme_id, identifier_value_string, role)
            if identifier_key in identifier_keys:
                raise TranscriptionReviewError("sign inventory repeats a published identifier")
            identifier_keys.add(identifier_key)
            document_id = _require_string(
                identifier.get("document_id"),
                f"sign inventory sign {index} identifier document_id",
            )
            if document_id not in document_ids:
                raise TranscriptionReviewError(
                    "published identifier cites an unknown source document"
                )
            if identifier.get("evidence_id") not in local_evidence_ids:
                raise TranscriptionReviewError(
                    "published identifier does not resolve to local graphic evidence"
                )
            if (
                local_evidence_documents[
                    _require_string(
                        identifier.get("evidence_id"),
                        f"sign inventory sign {index} identifier evidence_id",
                    )
                ]
                != document_id
            ):
                raise TranscriptionReviewError(
                    "published identifier and graphic evidence cite different documents"
                )
            if role == "primary_source_identifier" and scheme_id == primary_identifier_scheme:
                primary_identifiers.append(identifier_value_string)
        if len(primary_identifiers) != 1:
            raise TranscriptionReviewError("each sign needs exactly one primary source identifier")
        if primary_identifiers[0] in primary_source_identifiers:
            raise TranscriptionReviewError("primary source identifier values must be unique")
        primary_source_identifiers.add(primary_identifiers[0])

    for sign_id, sign in rows.items():
        superseded_by = sign.get("superseded_by")
        deprecated = sign.get("deprecated")
        if deprecated is True and superseded_by is None:
            raise TranscriptionReviewError(
                "a deprecated sign must identify its non-deprecated replacement"
            )
        if deprecated is False and superseded_by is not None:
            raise TranscriptionReviewError("a non-deprecated sign cannot declare superseded_by")
        if superseded_by is not None:
            if superseded_by == sign_id:
                raise TranscriptionReviewError("a sign cannot supersede itself")
            if superseded_by not in sign_ids:
                raise TranscriptionReviewError("superseded_by is outside the sign inventory")
            if rows[superseded_by].get("deprecated") is True:
                raise TranscriptionReviewError(
                    "a deprecated sign must resolve directly to a current sign"
                )


def validate_transcription_review(
    review_value: Mapping[str, Any],
    inventory_value: Mapping[str, Any],
    *,
    inventory_sha256: str | None = None,
) -> None:
    """Validate one independent transcription or adjudication record."""

    review = _require_mapping(review_value, "transcription review")
    inventory = _require_mapping(inventory_value, "sign inventory")
    validate_sign_inventory(inventory)
    _reject_interpretive_keys(review)

    if review.get("schema_version") != SCHEMA_VERSION:
        raise TranscriptionReviewError("unsupported transcription review schema_version")
    if review.get("scientific_scope") != SCIENTIFIC_SCOPE:
        raise TranscriptionReviewError("transcription scientific_scope is not fail-closed")
    if review.get("visual_order_basis") != "left_to_right_in_image":
        raise TranscriptionReviewError("transcription v0.1 requires left-to-right visual indexing")

    subject_id = _require_string(review.get("subject_id"), "subject_id")
    inventory_commitment = _require_mapping(review.get("sign_inventory"), "sign_inventory")
    if inventory_commitment.get("inventory_id") != inventory.get("inventory_id"):
        raise TranscriptionReviewError("review inventory_id does not match the inventory")
    if inventory_commitment.get("edition") != inventory.get("edition"):
        raise TranscriptionReviewError("review inventory edition does not match the inventory")
    if inventory_sha256 is not None and inventory_commitment.get("sha256") != inventory_sha256:
        raise TranscriptionReviewError("review inventory digest does not match the exact bytes")

    source = _require_mapping(review.get("source_commitment"), "source_commitment")
    if source.get("subject_id") != subject_id:
        raise TranscriptionReviewError("source_commitment subject_id does not match review")
    region_polygon = _polygon(source.get("region_polygon"), "source region_polygon")
    source_image_id = _require_string(source.get("image_id"), "source image_id")
    source_image_sha256 = _require_string(source.get("image_sha256"), "source image_sha256")
    view_transform = _require_mapping(
        source.get("view_transform"),
        "source view_transform",
    )
    if view_transform.get("mirrored") is not False or view_transform.get("rotation_degrees") != 0:
        raise TranscriptionReviewError(
            "transcription v0.1 requires an unmirrored, unrotated source view"
        )

    actor = _require_mapping(review.get("actor"), "actor")
    actor_id = _require_string(actor.get("actor_id"), "actor_id")
    assignment_id = _require_string(review.get("assignment_id"), "assignment_id")
    stage = review.get("review_stage")
    input_reviews = _require_list(review.get("input_reviews"), "input_reviews")
    promotion_target = review.get("promotion_target")
    if stage == "independent":
        if input_reviews:
            raise TranscriptionReviewError("independent transcription cannot cite input reviews")
        if promotion_target is not None:
            raise TranscriptionReviewError(
                "independent transcription cannot contain a promotion target"
            )
        if actor.get("role") != "transcriber" or actor.get("independent_pass") is not True:
            raise TranscriptionReviewError(
                "independent transcription requires an independent transcriber"
            )
    elif stage == "adjudication":
        if len(input_reviews) < 2:
            raise TranscriptionReviewError("adjudication requires at least two input reviews")
        _require_mapping(promotion_target, "adjudication promotion_target")
        if actor.get("role") != "adjudicator" or actor.get("independent_pass") is not False:
            raise TranscriptionReviewError("adjudication requires a non-independent adjudicator")
        input_actor_ids = {
            _require_string(
                _require_mapping(value, "input review").get("actor_id"),
                "input review actor_id",
            )
            for value in input_reviews
        }
        input_assignment_ids = {
            _require_string(
                _require_mapping(value, "input review").get("assignment_id"),
                "input review assignment_id",
            )
            for value in input_reviews
        }
        if len(input_actor_ids) != len(input_reviews):
            raise TranscriptionReviewError("adjudication input actors are not distinct")
        if len(input_assignment_ids) != len(input_reviews):
            raise TranscriptionReviewError("adjudication input assignments are not distinct")
        if actor_id in input_actor_ids or assignment_id in input_assignment_ids:
            raise TranscriptionReviewError("adjudicator is not independent of the input reviews")
    else:
        raise TranscriptionReviewError("unknown transcription review_stage")

    token_values = _require_list(review.get("tokens"), "tokens")
    if review.get("outcome") == "complete" and not token_values:
        raise TranscriptionReviewError("complete transcription must contain at least one token")

    sign_index = _inventory_index(inventory)
    token_ids: set[str] = set()
    tokens: list[Mapping[str, Any]] = []
    previous_visual_center_x: float | None = None
    for index, value in enumerate(token_values):
        token = _require_mapping(value, f"token {index}")
        token_id = _require_string(token.get("token_id"), f"token {index} token_id")
        if token_id in token_ids:
            raise TranscriptionReviewError("transcription contains duplicate token_id values")
        token_ids.add(token_id)
        tokens.append(token)
        if token.get("visual_index") != index:
            raise TranscriptionReviewError("visual_index values must be contiguous from zero")

        geometry = _require_mapping(token.get("geometry"), f"token {index} geometry")
        if geometry.get("image_id") != source_image_id:
            raise TranscriptionReviewError("token geometry cites a different image_id")
        if geometry.get("image_sha256") != source_image_sha256:
            raise TranscriptionReviewError("token geometry cites different image bytes")
        if geometry.get("coordinate_space") != "normalized_original_image":
            raise TranscriptionReviewError("token geometry uses an unknown coordinate space")
        token_polygon = _polygon(geometry.get("polygon"), f"token {index} polygon")
        if not _polygon_within(token_polygon, region_polygon):
            raise TranscriptionReviewError("token geometry falls outside the committed region")
        token_center_x = (
            min(point[0] for point in token_polygon) + max(point[0] for point in token_polygon)
        ) / 2
        if (
            previous_visual_center_x is not None
            and token_center_x <= previous_visual_center_x + _EPSILON
        ):
            raise TranscriptionReviewError(
                "visual_index must follow strictly increasing horizontal centers"
            )
        previous_visual_center_x = token_center_x

        selected = token.get("selected_sign")
        selected_key = None if selected is None else _validated_sign_ref(selected, sign_index)
        alternatives = _require_list(token.get("alternatives"), f"token {index} alternatives")
        alternative_keys: set[SignKey] = set()
        alternative_probability = 0.0
        for alternative_value in alternatives:
            alternative = _require_mapping(
                alternative_value,
                f"token {index} alternative",
            )
            key = _validated_sign_ref(alternative.get("sign"), sign_index)
            if key == selected_key or key in alternative_keys:
                raise TranscriptionReviewError("selected and alternative signs must be distinct")
            alternative_keys.add(key)
            probability = alternative.get("probability")
            if not isinstance(probability, int | float) or isinstance(probability, bool):
                raise TranscriptionReviewError("alternative probability must be numeric")
            probability_value = float(probability)
            if not math.isfinite(probability_value):
                raise TranscriptionReviewError("alternative probability must be finite")
            alternative_probability += probability_value

        confidence = token.get("confidence")
        if not isinstance(confidence, int | float) or isinstance(confidence, bool):
            raise TranscriptionReviewError("token confidence must be numeric")
        confidence_value = float(confidence)
        if not math.isfinite(confidence_value):
            raise TranscriptionReviewError("token confidence must be finite")
        if selected_key is None and confidence_value != 0:
            raise TranscriptionReviewError("an unclassified token must have zero confidence")
        if selected_key is not None and confidence_value <= 0:
            raise TranscriptionReviewError("a selected sign must have positive confidence")
        if confidence_value + alternative_probability > 1 + _EPSILON:
            raise TranscriptionReviewError("selected and alternative probabilities exceed one")
        if 0 < confidence_value < 0.6 and not alternatives:
            raise TranscriptionReviewError("weak sign identification requires an alternative")
        if token.get("condition") in {
            "lost",
            "unreadable",
        } and (selected_key is not None or confidence_value != 0 or alternatives):
            raise TranscriptionReviewError(
                "lost or unreadable tokens cannot receive sign identities"
            )

        uncertainty = _require_mapping(token.get("uncertainty"), f"token {index} uncertainty")
        uncertainty_status = uncertainty.get("status")
        if uncertainty_status == "certain" and confidence_value != 1:
            raise TranscriptionReviewError("certain tokens require confidence 1")
        if uncertainty_status == "clear" and not 0.9 <= confidence_value <= 1:
            raise TranscriptionReviewError("clear tokens require confidence of at least 0.9")
        if uncertainty_status == "ambiguous" and not alternatives:
            raise TranscriptionReviewError("ambiguous tokens require alternative signs")
        if uncertainty_status == "unresolved" and selected_key is not None:
            raise TranscriptionReviewError("unresolved tokens cannot select a sign")

        input_token_refs = _require_list(
            token.get("input_token_refs"),
            f"token {index} input_token_refs",
        )
        adjudication_reason = token.get("adjudication_reason")
        if stage == "independent":
            if input_token_refs or adjudication_reason is not None:
                raise TranscriptionReviewError(
                    "independent tokens cannot contain adjudication evidence"
                )
        else:
            if not input_token_refs or not isinstance(adjudication_reason, str):
                raise TranscriptionReviewError("adjudicated tokens require input refs and a reason")

    direction = _require_mapping(review.get("reading_direction"), "reading_direction")
    direction_value = direction.get("value")
    direction_confidence = direction.get("confidence")
    direction_evidence = set(_require_list(direction.get("evidence"), "reading_direction evidence"))
    if not isinstance(direction_confidence, int | float) or isinstance(direction_confidence, bool):
        raise TranscriptionReviewError("direction confidence must be numeric")
    if not math.isfinite(float(direction_confidence)):
        raise TranscriptionReviewError("direction confidence must be finite")
    reading_indices = [token.get("reading_index") for token in tokens]
    if direction_value == "unknown":
        if float(direction_confidence) != 0:
            raise TranscriptionReviewError("unknown direction must have zero confidence")
        if direction_evidence != {"unknown"}:
            raise TranscriptionReviewError("unknown direction must cite only unknown evidence")
        if any(index is not None for index in reading_indices):
            raise TranscriptionReviewError("unknown direction cannot assign reading_index values")
    elif direction_value in _KNOWN_DIRECTIONS:
        if float(direction_confidence) <= 0:
            raise TranscriptionReviewError("known direction needs positive confidence")
        if not direction_evidence or "unknown" in direction_evidence:
            raise TranscriptionReviewError("known direction needs specific non-unknown evidence")
        if review.get("outcome") == "complete":
            if any(
                not isinstance(index, int) or isinstance(index, bool) for index in reading_indices
            ):
                raise TranscriptionReviewError(
                    "complete known-direction transcription needs every reading_index"
                )
            integer_reading_indices = [
                index
                for index in reading_indices
                if isinstance(index, int) and not isinstance(index, bool)
            ]
            if sorted(integer_reading_indices) != list(range(len(tokens))):
                raise TranscriptionReviewError("reading_index values must form one permutation")
    else:
        raise TranscriptionReviewError("unknown reading direction value")

    if actor.get("sign_inventory_access") is False and any(
        token.get("selected_sign") is not None or token.get("alternatives") for token in tokens
    ):
        raise TranscriptionReviewError("a catalog-blind actor cannot assign inventory signs")

    if stage == "independent" and direction.get("adjudication_reason") is not None:
        raise TranscriptionReviewError(
            "independent direction cannot contain an adjudication reason"
        )
    if stage == "adjudication" and not isinstance(direction.get("adjudication_reason"), str):
        raise TranscriptionReviewError("adjudicated direction requires a reason")


def compare_independent_transcriptions(
    left_value: Mapping[str, Any],
    right_value: Mapping[str, Any],
    *,
    minimum_bbox_iou: float = 0.5,
) -> JsonObject:
    """Compare two already validated independent reviews without exposing sign IDs."""

    left = _require_mapping(left_value, "left transcription")
    right = _require_mapping(right_value, "right transcription")
    if left.get("review_stage") != "independent" or right.get("review_stage") != "independent":
        raise TranscriptionReviewError("agreement requires two independent reviews")
    if left.get("source_commitment") != right.get("source_commitment"):
        raise TranscriptionReviewError("independent reviews cite different source commitments")
    if left.get("sign_inventory") != right.get("sign_inventory"):
        raise TranscriptionReviewError("independent reviews cite different sign inventories")
    if (
        left.get("visual_order_basis") != "left_to_right_in_image"
        or right.get("visual_order_basis") != "left_to_right_in_image"
    ):
        raise TranscriptionReviewError("agreement requires left-to-right visual indexing")
    if _actor_id(left) == _actor_id(right):
        raise TranscriptionReviewError("independent reviews reuse the same actor_id")
    if left.get("assignment_id") == right.get("assignment_id"):
        raise TranscriptionReviewError("independent reviews reuse the same assignment_id")
    if (
        not isinstance(minimum_bbox_iou, int | float)
        or isinstance(minimum_bbox_iou, bool)
        or not math.isfinite(minimum_bbox_iou)
        or not 0 < minimum_bbox_iou <= 1
    ):
        raise TranscriptionReviewError("minimum_bbox_iou must be in (0, 1]")

    left_tokens = [
        _require_mapping(value, "left token")
        for value in _require_list(left.get("tokens"), "left tokens")
    ]
    right_tokens = [
        _require_mapping(value, "right token")
        for value in _require_list(right.get("tokens"), "right tokens")
    ]
    alignment = _optimal_monotonic_alignment(
        left_tokens,
        right_tokens,
        minimum_bbox_iou=minimum_bbox_iou,
    )
    aligned_count = len(alignment)
    left_count = len(left_tokens)
    right_count = len(right_tokens)
    segmentation_precision = aligned_count / right_count if right_count else 0.0
    segmentation_recall = aligned_count / left_count if left_count else 0.0
    segmentation_f1 = (
        2 * aligned_count / (left_count + right_count) if left_count + right_count else 1.0
    )

    sign_comparable = 0
    sign_agreements = 0
    condition_agreements = 0
    reading_agreements = 0
    segmentation_agreements = 0
    uncertainty_agreements = 0
    alternative_agreements = 0
    confidence_agreements = 0
    iou_total = 0.0
    for left_index, right_index, iou in alignment:
        left_token = left_tokens[left_index]
        right_token = right_tokens[right_index]
        iou_total += iou
        left_sign = _optional_sign_key(left_token.get("selected_sign"))
        right_sign = _optional_sign_key(right_token.get("selected_sign"))
        if left_sign is not None and right_sign is not None:
            sign_comparable += 1
            sign_agreements += left_sign == right_sign
        condition_agreements += left_token.get("condition") == right_token.get("condition")
        segmentation_agreements += left_token.get("segmentation") == right_token.get("segmentation")
        left_reading_index = left_token.get("reading_index")
        right_reading_index = right_token.get("reading_index")
        reading_agreements += left_reading_index == right_reading_index
        left_uncertainty = _require_mapping(
            left_token.get("uncertainty"),
            "left uncertainty",
        )
        right_uncertainty = _require_mapping(
            right_token.get("uncertainty"),
            "right uncertainty",
        )
        uncertainty_agreements += left_uncertainty == right_uncertainty
        alternative_agreements += left_token.get("alternatives") == right_token.get("alternatives")
        confidence_agreements += left_token.get("confidence") == right_token.get("confidence")

    direction_agreement = left.get("reading_direction") == right.get("reading_direction")
    complete_outcomes = left.get("outcome") == right.get("outcome") == "complete"
    fully_aligned = aligned_count == left_count == right_count
    every_sign_agrees = sign_comparable == aligned_count and sign_agreements == aligned_count
    every_condition_agrees = condition_agreements == aligned_count
    every_segmentation_agrees = segmentation_agreements == aligned_count
    every_reading_index_agrees = reading_agreements == aligned_count
    every_uncertainty_agrees = uncertainty_agreements == aligned_count
    every_alternative_agrees = alternative_agreements == aligned_count
    every_confidence_agrees = confidence_agreements == aligned_count
    adjudication_required = not (
        complete_outcomes
        and fully_aligned
        and every_sign_agrees
        and every_condition_agrees
        and every_segmentation_agrees
        and every_reading_index_agrees
        and every_uncertainty_agrees
        and every_alternative_agrees
        and every_confidence_agrees
        and direction_agreement
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "scientific_scope": SCIENTIFIC_SCOPE,
        "left_token_count": left_count,
        "right_token_count": right_count,
        "aligned_token_count": aligned_count,
        "mean_bbox_iou": (iou_total / aligned_count if aligned_count else None),
        "segmentation_precision": segmentation_precision,
        "segmentation_recall": segmentation_recall,
        "segmentation_f1": segmentation_f1,
        "sign_identity_comparable_count": sign_comparable,
        "sign_identity_agreement_count": sign_agreements,
        "sign_identity_agreement": (sign_agreements / sign_comparable if sign_comparable else None),
        "condition_agreement_count": condition_agreements,
        "condition_agreement": (condition_agreements / aligned_count if aligned_count else None),
        "segmentation_agreement_count": segmentation_agreements,
        "segmentation_agreement": (
            segmentation_agreements / aligned_count if aligned_count else None
        ),
        "reading_index_comparable_count": aligned_count,
        "reading_index_agreement_count": reading_agreements,
        "reading_index_agreement": (reading_agreements / aligned_count if aligned_count else None),
        "uncertainty_agreement_count": uncertainty_agreements,
        "uncertainty_agreement": (
            uncertainty_agreements / aligned_count if aligned_count else None
        ),
        "alternative_agreement_count": alternative_agreements,
        "alternative_agreement": (
            alternative_agreements / aligned_count if aligned_count else None
        ),
        "confidence_agreement_count": confidence_agreements,
        "confidence_agreement": (confidence_agreements / aligned_count if aligned_count else None),
        "direction_agreement": direction_agreement,
        "both_outcomes_complete": complete_outcomes,
        "adjudication_required": adjudication_required,
        "independence_assurance": (
            "distinct pseudonymous actor_id and assignment_id only; "
            "real-world independence is not established"
        ),
    }


def _verify_transcription_adjudication(
    independent_reviews: Sequence[tuple[Mapping[str, Any], str]],
    adjudication_value: Mapping[str, Any],
    inventory_value: Mapping[str, Any],
    *,
    inventory_sha256: str,
) -> JsonObject:
    """Verify one already decoded adjudication graph.

    This is deliberately private: only the exact-byte public API may claim that
    review commitments were recomputed from the supplied evidence.
    """

    if len(independent_reviews) < 2:
        raise TranscriptionReviewError("at least two independent reviews are required")
    inventory = _require_mapping(inventory_value, "sign inventory")
    adjudication = _require_mapping(adjudication_value, "adjudication")
    validate_transcription_review(
        adjudication,
        inventory,
        inventory_sha256=inventory_sha256,
    )
    if adjudication.get("review_stage") != "adjudication":
        raise TranscriptionReviewError("the final record is not an adjudication")
    reviews: list[Mapping[str, Any]] = []
    expected_inputs: set[tuple[str, str, str, str]] = set()
    review_tokens: dict[str, dict[str, Mapping[str, Any]]] = {}
    review_ids: set[str] = set()
    review_digests: set[str] = set()
    actor_ids: set[str] = set()
    assignment_ids: set[str] = set()
    source_commitment: object | None = None
    inventory_commitment: object | None = None
    for review_value, digest in independent_reviews:
        review = _require_mapping(review_value, "independent review")
        validate_transcription_review(
            review,
            inventory,
            inventory_sha256=inventory_sha256,
        )
        if review.get("review_stage") != "independent":
            raise TranscriptionReviewError("an input record is not an independent review")
        if review.get("outcome") != "complete":
            raise TranscriptionReviewError(
                "every independent input must be complete before adjudication"
            )
        actor_id = _actor_id(review)
        assignment_id = _require_string(review.get("assignment_id"), "assignment_id")
        if actor_id in actor_ids or assignment_id in assignment_ids:
            raise TranscriptionReviewError("independent input actors and assignments must differ")
        actor_ids.add(actor_id)
        assignment_ids.add(assignment_id)
        if source_commitment is None:
            source_commitment = review.get("source_commitment")
            inventory_commitment = review.get("sign_inventory")
        elif review.get("source_commitment") != source_commitment:
            raise TranscriptionReviewError("independent reviews cite different source commitments")
        elif review.get("sign_inventory") != inventory_commitment:
            raise TranscriptionReviewError("independent reviews cite different sign inventories")
        review_id = _require_string(review.get("review_id"), "review_id")
        if review_id in review_ids:
            raise TranscriptionReviewError("independent input review_id values must differ")
        if digest in review_digests:
            raise TranscriptionReviewError("independent input review digests must differ")
        review_ids.add(review_id)
        review_digests.add(digest)
        expected_inputs.add((review_id, digest, assignment_id, actor_id))
        review_tokens[review_id] = {
            _require_string(token.get("token_id"), "token_id"): token
            for token in (
                _require_mapping(value, "input token")
                for value in _require_list(review.get("tokens"), "tokens")
            )
        }
        reviews.append(review)

    if adjudication.get("source_commitment") != source_commitment:
        raise TranscriptionReviewError("adjudication cites a different source commitment")
    if adjudication.get("sign_inventory") != inventory_commitment:
        raise TranscriptionReviewError("adjudication cites a different sign inventory")
    adjudication_review_id = _require_string(
        adjudication.get("review_id"),
        "adjudication review_id",
    )
    if adjudication_review_id in review_ids:
        raise TranscriptionReviewError(
            "adjudication review_id must differ from every independent review_id"
        )

    actual_inputs = {
        (
            _require_string(row.get("review_id"), "input review_id"),
            _require_string(row.get("review_sha256"), "input review_sha256"),
            _require_string(row.get("assignment_id"), "input assignment_id"),
            _require_string(row.get("actor_id"), "input actor_id"),
        )
        for row in (
            _require_mapping(value, "adjudication input review")
            for value in _require_list(adjudication.get("input_reviews"), "input_reviews")
        )
    }
    if actual_inputs != expected_inputs:
        raise TranscriptionReviewError(
            "adjudication input commitments do not match the exact independent reviews"
        )

    covered: set[tuple[str, str]] = set()
    reference_usage: dict[tuple[str, str], list[int]] = {}
    output_reference_sets: list[set[tuple[str, str]]] = []
    output_bboxes: list[tuple[float, float, float, float]] = []
    for output_index, token_value in enumerate(
        _require_list(adjudication.get("tokens"), "adjudication tokens")
    ):
        token = _require_mapping(token_value, "adjudication token")
        referenced_signs: set[SignKey] = set()
        referenced_tokens: set[tuple[str, str]] = set()
        output_bbox = _token_bbox(token)
        output_bboxes.append(output_bbox)
        for ref_value in _require_list(token.get("input_token_refs"), "input_token_refs"):
            ref = _require_mapping(ref_value, "input_token_ref")
            review_id = _require_string(ref.get("review_id"), "input token review_id")
            token_id = _require_string(ref.get("token_id"), "input token token_id")
            token_ref = (review_id, token_id)
            if token_ref in referenced_tokens:
                raise TranscriptionReviewError(
                    "adjudication token repeats an input token reference"
                )
            referenced_tokens.add(token_ref)
            source_tokens = review_tokens.get(review_id)
            if source_tokens is None or token_id not in source_tokens:
                raise TranscriptionReviewError("adjudication cites an unknown input token")
            covered.add(token_ref)
            reference_usage.setdefault(token_ref, []).append(output_index)
            source_token = source_tokens[token_id]
            if (
                _polygon_output_coverage(
                    _token_polygon(token),
                    _token_polygon(source_token),
                )
                < 0.5
            ):
                raise TranscriptionReviewError(
                    "adjudication token does not sufficiently overlap its cited input geometry"
                )
            selected = _optional_sign_key(source_token.get("selected_sign"))
            if selected is not None:
                referenced_signs.add(selected)
            for alternative_value in _require_list(
                source_token.get("alternatives"),
                "input token alternatives",
            ):
                alternative = _require_mapping(alternative_value, "input token alternative")
                sign = _optional_sign_key(alternative.get("sign"))
                if sign is not None:
                    referenced_signs.add(sign)

        output_signs: set[SignKey] = set()
        selected_output = _optional_sign_key(token.get("selected_sign"))
        if selected_output is not None:
            output_signs.add(selected_output)
        for alternative_value in _require_list(
            token.get("alternatives"),
            "adjudication token alternatives",
        ):
            alternative = _require_mapping(alternative_value, "adjudication alternative")
            sign = _optional_sign_key(alternative.get("sign"))
            if sign is not None:
                output_signs.add(sign)
        if not output_signs.issubset(referenced_signs):
            raise TranscriptionReviewError(
                "adjudication introduced a sign absent from its cited input tokens"
            )
        if {review_id for review_id, _token_id in referenced_tokens} != review_ids:
            raise TranscriptionReviewError(
                "every adjudication token must cite every independent review"
            )
        output_reference_sets.append(referenced_tokens)

    expected_coverage = {
        (review_id, token_id) for review_id, tokens in review_tokens.items() for token_id in tokens
    }
    if covered != expected_coverage:
        raise TranscriptionReviewError("adjudication does not cover every independent-review token")

    reused_references = {
        token_ref
        for token_ref, output_indices in reference_usage.items()
        if len(output_indices) > 1
    }
    for token_ref in reused_references:
        output_indices = reference_usage[token_ref]
        for left_offset, left_index in enumerate(output_indices):
            for right_index in output_indices[left_offset + 1 :]:
                if (
                    _bbox_intersection_area(
                        output_bboxes[left_index],
                        output_bboxes[right_index],
                    )
                    > 0
                ):
                    raise TranscriptionReviewError(
                        "outputs that split one input token must not overlap"
                    )
    for token_refs in output_reference_sets:
        if token_refs.intersection(reused_references) and not any(
            len(reference_usage[token_ref]) == 1 for token_ref in token_refs
        ):
            raise TranscriptionReviewError(
                "a split output needs a uniquely used input-token anchor"
            )
    for (review_id, token_id), output_indices in reference_usage.items():
        source_bbox = _token_bbox(review_tokens[review_id][token_id])
        source_area = _bbox_area(source_bbox)
        covered_source_area = sum(
            _bbox_intersection_area(source_bbox, output_bboxes[output_index])
            for output_index in output_indices
        )
        if source_area <= 0 or covered_source_area / source_area < 0.5:
            raise TranscriptionReviewError(
                "adjudication outputs do not sufficiently cover cited input geometry"
            )

    input_directions = {
        _require_mapping(review.get("reading_direction"), "reading_direction").get("value")
        for review in reviews
    }
    adjudicated_direction = _require_mapping(
        adjudication.get("reading_direction"),
        "adjudicated reading_direction",
    ).get("value")
    if adjudicated_direction != "unknown" and adjudicated_direction not in input_directions:
        raise TranscriptionReviewError(
            "adjudication introduced a direction absent from the independent reviews"
        )

    pairwise = [
        (
            _sorted_pair(
                _require_string(reviews[left].get("review_id"), "left review_id"),
                _require_string(reviews[right].get("review_id"), "right review_id"),
            ),
            compare_independent_transcriptions(reviews[left], reviews[right]),
        )
        for left in range(len(reviews))
        for right in range(left + 1, len(reviews))
    ]
    expected_disagreements = {
        (
            review_pair,
            sha256_bytes(encode_json(comparison)),
        )
        for review_pair, comparison in pairwise
        if comparison["adjudication_required"]
    }
    actual_disagreements: set[tuple[tuple[str, str], str]] = set()
    for value in _require_list(adjudication.get("disagreements"), "disagreements"):
        disagreement = _require_mapping(value, "disagreement")
        review_pair_values = _require_list(
            disagreement.get("review_ids"),
            "disagreement review_ids",
        )
        if len(review_pair_values) != 2:
            raise TranscriptionReviewError("disagreement must bind exactly two independent reviews")
        review_pair = _sorted_pair(
            _require_string(review_pair_values[0], "disagreement review_id"),
            _require_string(review_pair_values[1], "disagreement review_id"),
        )
        if len(set(review_pair)) != 2:
            raise TranscriptionReviewError("disagreement must bind distinct independent reviews")
        commitment = (
            review_pair,
            _require_string(
                disagreement.get("comparison_sha256"),
                "disagreement comparison_sha256",
            ),
        )
        if commitment in actual_disagreements:
            raise TranscriptionReviewError("adjudication repeats a disagreement commitment")
        actual_disagreements.add(commitment)
    if actual_disagreements != expected_disagreements:
        raise TranscriptionReviewError(
            "adjudication disagreement commitments do not match reviewer conflicts"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "valid": True,
        "independent_review_count": len(reviews),
        "pairwise_comparison_count": len(pairwise),
        "pairwise_adjudication_required_count": sum(
            bool(summary["adjudication_required"]) for _review_pair, summary in pairwise
        ),
        "input_token_coverage_complete": True,
        "input_digest_references_match_supplied_digest_arguments": True,
        "source_commitment_cross_record_consistent": True,
        "inventory_commitment_cross_record_consistent": True,
        "inventory_source_document_bytes_rehashed": False,
        "inventory_graphic_crop_bytes_rehashed": False,
        "source_image_bytes_present_or_rehashed": False,
        "rights_evidence_externally_verified": False,
        "real_world_independence_verified": False,
    }


def _default_schema_path(filename: str) -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / filename
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(f"schemas/{filename}")
    return Path(str(package_candidate))


def _decode_evidence_object(
    raw_bytes: bytes,
    *,
    label: str,
    schema_filename: str,
) -> JsonObject:
    if not isinstance(raw_bytes, bytes):
        raise TranscriptionReviewError(f"{label} must be supplied as exact bytes")
    if not raw_bytes or len(raw_bytes) > _MAX_EVIDENCE_JSON_BYTES:
        raise TranscriptionReviewError(f"{label} has an invalid byte length")
    try:
        value = decode_json(raw_bytes, source=label)
    except ValueError as error:
        raise TranscriptionReviewError(str(error)) from error
    if not isinstance(value, dict):
        raise TranscriptionReviewError(f"{label} must decode to an object")
    issues = validate_schema_instance(
        value,
        _default_schema_path(schema_filename),
    )
    if issues:
        first = issues[0]
        raise TranscriptionReviewError(f"{label} schema invalid at {first.path}: {first.message}")
    return value


def _verify_transcription_evidence_bytes(
    inventory_bytes: bytes,
    independent_review_bytes: Sequence[bytes],
    adjudication_bytes: bytes,
) -> _VerifiedTranscriptionEvidence:
    if not 2 <= len(independent_review_bytes) <= 16:
        raise TranscriptionReviewError(
            "promotion requires two to sixteen independent review byte strings"
        )
    inventory = _decode_evidence_object(
        inventory_bytes,
        label="sign inventory",
        schema_filename="sign-inventory.schema.json",
    )
    reviews = tuple(
        _decode_evidence_object(
            raw_bytes,
            label=f"independent review {index}",
            schema_filename="transcription-review.schema.json",
        )
        for index, raw_bytes in enumerate(independent_review_bytes)
    )
    adjudication = _decode_evidence_object(
        adjudication_bytes,
        label="adjudication",
        schema_filename="transcription-review.schema.json",
    )
    inventory_sha256 = sha256_bytes(inventory_bytes)
    review_sha256 = tuple(sha256_bytes(raw_bytes) for raw_bytes in independent_review_bytes)
    adjudication_sha256 = sha256_bytes(adjudication_bytes)
    summary = _verify_transcription_adjudication(
        list(zip(reviews, review_sha256, strict=True)),
        adjudication,
        inventory,
        inventory_sha256=inventory_sha256,
    )
    summary.pop(
        "input_digest_references_match_supplied_digest_arguments",
        None,
    )
    summary["input_digest_references_match_supplied_bytes"] = True
    summary["inventory_digest_matches_supplied_bytes"] = True
    summary["adjudication_digest_computed_from_supplied_bytes"] = True
    return _VerifiedTranscriptionEvidence(
        inventory=inventory,
        reviews=reviews,
        adjudication=adjudication,
        inventory_sha256=inventory_sha256,
        review_sha256=review_sha256,
        adjudication_sha256=adjudication_sha256,
        summary=summary,
    )


def verify_transcription_evidence_bytes(
    inventory_bytes: bytes,
    independent_review_bytes: Sequence[bytes],
    adjudication_bytes: bytes,
) -> JsonObject:
    """Verify schemas, semantics, and hashes from the exact supplied JSON bytes."""

    evidence = _verify_transcription_evidence_bytes(
        inventory_bytes,
        independent_review_bytes,
        adjudication_bytes,
    )
    return copy.deepcopy(evidence.summary)


def promote_adjudicated_transcription(
    artifact_template_value: Mapping[str, Any],
    *,
    inventory_bytes: bytes,
    independent_review_bytes: Sequence[bytes],
    adjudication_bytes: bytes,
    side_id: str,
    line_id: str,
    release_scope: str,
) -> TranscriptionPromotion:
    """Verify exact evidence bytes and privately promote one adjudicated line."""

    artifact_template = _require_mapping(artifact_template_value, "artifact template")
    artifact_schema_issues = validate_schema_instance(
        artifact_template,
        _default_schema_path("artifact.schema.json"),
    )
    if artifact_schema_issues:
        first = artifact_schema_issues[0]
        raise TranscriptionReviewError(
            f"artifact template schema invalid at {first.path}: {first.message}"
        )
    evidence = _verify_transcription_evidence_bytes(
        inventory_bytes,
        independent_review_bytes,
        adjudication_bytes,
    )
    adjudication = evidence.adjudication
    inventory = evidence.inventory
    adjudication_sha256 = evidence.adjudication_sha256
    if release_scope != "private_research":
        raise TranscriptionReviewError(
            "public transcription export is disabled pending an allowlist-only exporter"
        )
    if adjudication.get("review_stage") != "adjudication":
        raise TranscriptionReviewError("only an adjudication can be promoted")
    if adjudication.get("outcome") != "complete":
        raise TranscriptionReviewError("only a complete adjudication can be promoted")

    direction = _require_mapping(adjudication.get("reading_direction"), "reading_direction")
    if direction.get("value") not in _KNOWN_DIRECTIONS | {"unknown"}:
        raise TranscriptionReviewError("invalid reading direction cannot be promoted")
    tokens = [
        _require_mapping(value, "adjudication token")
        for value in _require_list(adjudication.get("tokens"), "adjudication tokens")
    ]
    inventory_rights = _require_mapping(inventory.get("rights"), "inventory rights")
    source = _require_mapping(adjudication.get("source_commitment"), "source_commitment")
    source_rights = _require_mapping(source.get("rights"), "source rights")
    if inventory_rights.get("analysis_use") != "permitted":
        raise TranscriptionReviewError("sign inventory analysis use is not permitted")
    if source_rights.get("transcription_use") != "permitted":
        raise TranscriptionReviewError("source transcription use is not permitted")

    artifact = copy.deepcopy(dict(artifact_template))
    if has_errors(validate_artifact(artifact)):
        raise TranscriptionReviewError("artifact template fails semantic validation")
    artifact_rights = _require_mapping(artifact.get("rights"), "artifact rights")
    if (
        artifact_rights.get("status")
        not in {
            "public_domain",
            "open_licensed",
            "permission_granted",
        }
        or artifact_rights.get("derivatives") is not True
    ):
        raise TranscriptionReviewError(
            "artifact rights do not permit a derived transcription observation"
        )
    source_record_ids = set(_require_list(source.get("source_record_ids"), "source_record_ids"))
    artifact_source_ids = {
        row.get("source_record_id")
        for row in (
            _require_mapping(value, "artifact source record")
            for value in _require_list(artifact.get("source_records"), "source_records")
        )
    }
    if not source_record_ids.issubset(artifact_source_ids):
        raise TranscriptionReviewError(
            "source commitment does not resolve in the artifact template"
        )

    image_id = _require_string(source.get("image_id"), "source image_id")
    image_sha256 = _require_string(source.get("image_sha256"), "source image_sha256")
    images = [
        _require_mapping(value, "artifact image")
        for value in _require_list(artifact.get("images"), "artifact images")
    ]
    matching_images = [image for image in images if image.get("image_id") == image_id]
    if len(matching_images) != 1 or matching_images[0].get("image_hash") != image_sha256:
        raise TranscriptionReviewError("artifact template does not bind the exact source image")
    image_rights = _require_mapping(matching_images[0].get("rights"), "source image rights")
    if (
        image_rights.get("status")
        not in {
            "public_domain",
            "open_licensed",
            "permission_granted",
        }
        or image_rights.get("derivatives") is not True
    ):
        raise TranscriptionReviewError(
            "source image rights do not permit a derived transcription observation"
        )
    sides = [
        _require_mapping(value, "artifact side")
        for value in _require_list(artifact.get("sides"), "artifact sides")
    ]
    matching_sides = [side for side in sides if side.get("side_id") == side_id]
    if len(matching_sides) != 1:
        raise TranscriptionReviewError("target side_id is missing or ambiguous")
    side = matching_sides[0]
    artifact_target = _require_mapping(
        adjudication.get("promotion_target"),
        "promotion_target",
    )
    if (
        artifact_target.get("artifact_id") != artifact.get("artifact_id")
        or artifact_target.get("side_id") != side_id
        or artifact_target.get("line_id") != line_id
    ):
        raise TranscriptionReviewError(
            "promotion target differs from the committed artifact target"
        )
    if side.get("physical_form") != source.get("carrier_view"):
        raise TranscriptionReviewError(
            "target side physical form differs from the committed carrier view"
        )
    if image_id not in _require_list(side.get("image_ids"), "side image_ids"):
        raise TranscriptionReviewError("target side is not linked to the source image")
    lines = [
        _require_mapping(value, "artifact line")
        for value in _require_list(side.get("lines"), "side lines")
    ]
    matching_lines = [line for line in lines if line.get("line_id") == line_id]
    if len(matching_lines) != 1:
        raise TranscriptionReviewError("target line_id is missing or ambiguous")
    line = matching_lines[0]
    if not isinstance(line, dict):
        raise TranscriptionReviewError("target line must be a mutable JSON object")
    scaffold_tokens = _require_list(line.get("tokens"), "target scaffold tokens")
    if (
        line.get("reading_direction") != "unknown"
        or line.get("direction_confidence") != 0
        or len(scaffold_tokens) != 1
    ):
        raise TranscriptionReviewError(
            "target line must be an unresolved one-token promotion scaffold"
        )
    scaffold_token = _require_mapping(
        scaffold_tokens[0],
        "target scaffold token",
    )
    scaffold_uncertainty = _require_mapping(
        scaffold_token.get("uncertainty"),
        "target scaffold uncertainty",
    )
    if (
        scaffold_token.get("sign_id") is not None
        or scaffold_token.get("visual_index") != 0
        or scaffold_token.get("reading_index") is not None
        or scaffold_token.get("confidence") != 0
        or scaffold_token.get("condition") != "unreadable"
        or scaffold_token.get("geometry") is not None
        or scaffold_uncertainty.get("status") != "unresolved"
        or scaffold_uncertainty.get("alternatives") != []
        or scaffold_uncertainty.get("notes") is not None
        or set(
            _require_list(
                scaffold_token.get("source_record_ids"),
                "target scaffold source_record_ids",
            )
        )
        != source_record_ids
    ):
        raise TranscriptionReviewError("target line contains observations and cannot be replaced")

    sign_index = _inventory_index(inventory)
    promoted_tokens: list[JsonObject] = []
    for token in tokens:
        selected_key = _optional_sign_key(token.get("selected_sign"))
        selected_project_id = None if selected_key is None else sign_index[selected_key]
        alternatives = []
        for alternative_value in _require_list(token.get("alternatives"), "alternatives"):
            alternative = _require_mapping(alternative_value, "alternative")
            alternative_key = _optional_sign_key(alternative.get("sign"))
            if alternative_key is None:
                raise TranscriptionReviewError("alternative sign cannot be null")
            alternatives.append(
                {
                    "sign_id": sign_index[alternative_key],
                    "probability": alternative.get("probability"),
                }
            )
        geometry = _require_mapping(token.get("geometry"), "token geometry")
        promoted_tokens.append(
            {
                "token_id": token.get("token_id"),
                "sign_id": selected_project_id,
                "visual_index": token.get("visual_index"),
                "reading_index": token.get("reading_index"),
                "confidence": token.get("confidence"),
                "condition": token.get("condition"),
                "uncertainty": {
                    "status": _require_mapping(
                        token.get("uncertainty"),
                        "token uncertainty",
                    ).get("status"),
                    "alternatives": alternatives,
                    "notes": _require_mapping(
                        token.get("uncertainty"),
                        "token uncertainty",
                    ).get("notes"),
                },
                "geometry": {
                    "image_id": geometry.get("image_id"),
                    "coordinate_space": "normalized",
                    "polygon": [
                        {"x": point[0], "y": point[1]}
                        for point in _require_list(
                            geometry.get("polygon"),
                            "token polygon",
                        )
                    ],
                },
                "source_record_ids": sorted(source_record_ids),
            }
        )

    line["visual_order_basis"] = adjudication.get("visual_order_basis")
    line["reading_direction"] = direction.get("value")
    line["direction_confidence"] = direction.get("confidence")
    line["tokens"] = promoted_tokens
    extensions = artifact.setdefault("extensions", {})
    if not isinstance(extensions, dict):
        raise TranscriptionReviewError("artifact extensions must be an object")
    if "indusbench:transcription_bridge" in extensions:
        raise TranscriptionReviewError(
            "transcription bridge v0.1 refuses to replace an existing promotion receipt"
        )
    bridge_extension: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "claim_class": "development_observation",
        "release_scope": release_scope,
        "promotion_state": "private_staging_only",
        "evaluation_admissible": False,
        "assurances": {
            "source_image_digest_cross_record_consistent": True,
            "input_digest_references_matched_supplied_bytes": True,
            "inventory_source_document_bytes_rehashed": False,
            "inventory_graphic_crop_bytes_rehashed": False,
            "source_image_bytes_present_or_rehashed": False,
            "rights_evidence_externally_verified": False,
            "blind_evaluation": False,
            "decipherment": False,
            "real_world_reviewer_independence": False,
        },
    }
    bridge_extension["private_commitments"] = {
        "inventory_commitment": adjudication.get("sign_inventory"),
        "adjudication_review_id": adjudication.get("review_id"),
        "adjudication_sha256": adjudication_sha256,
        "input_review_sha256": sorted(
            _require_string(row.get("review_sha256"), "input review_sha256")
            for row in (
                _require_mapping(value, "input review")
                for value in _require_list(
                    adjudication.get("input_reviews"),
                    "input_reviews",
                )
            )
        ),
        "source_image_sha256": image_sha256,
        "source_view_transform": source.get("view_transform"),
        "visual_order_basis": adjudication.get("visual_order_basis"),
        "token_segmentation": [
            {
                "token_id": token.get("token_id"),
                "segmentation": token.get("segmentation"),
            }
            for token in tokens
        ],
    }
    extensions["indusbench:transcription_bridge"] = bridge_extension
    if has_errors(validate_artifact(artifact)):
        raise TranscriptionReviewError("promoted artifact fails semantic validation")
    return TranscriptionPromotion(
        artifact=artifact,
        verification=copy.deepcopy(evidence.summary),
    )


def _inventory_index(inventory: Mapping[str, Any]) -> dict[SignKey, str]:
    inventory_id = _require_string(inventory.get("inventory_id"), "inventory_id")
    edition = _require_string(inventory.get("edition"), "inventory edition")
    return {
        (inventory_id, edition, _require_string(sign.get("sign_id"), "sign_id")): _require_string(
            sign.get("project_sign_id"),
            "project_sign_id",
        )
        for sign in (
            _require_mapping(value, "inventory sign")
            for value in _require_list(inventory.get("signs"), "inventory signs")
        )
        if sign.get("deprecated") is False
    }


def _validated_sign_ref(value: object, sign_index: Mapping[SignKey, str]) -> SignKey:
    sign = _require_mapping(value, "sign reference")
    key = (
        _require_string(sign.get("inventory_id"), "sign inventory_id"),
        _require_string(sign.get("edition"), "sign edition"),
        _require_string(sign.get("sign_id"), "sign_id"),
    )
    if key not in sign_index:
        raise TranscriptionReviewError("sign reference is outside the fixed inventory")
    return key


def _optional_sign_key(value: object) -> SignKey | None:
    if value is None:
        return None
    sign = _require_mapping(value, "sign reference")
    return (
        _require_string(sign.get("inventory_id"), "sign inventory_id"),
        _require_string(sign.get("edition"), "sign edition"),
        _require_string(sign.get("sign_id"), "sign_id"),
    )


def _actor_id(review: Mapping[str, Any]) -> str:
    return _require_string(
        _require_mapping(review.get("actor"), "actor").get("actor_id"),
        "actor_id",
    )


def _reject_interpretive_keys(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in FORBIDDEN_INTERPRETIVE_KEYS:
                raise TranscriptionReviewError(
                    f"{path}: interpretive field {normalized!r} is forbidden"
                )
            _reject_interpretive_keys(child, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for index, child in enumerate(value):
            _reject_interpretive_keys(child, path=f"{path}[{index}]")


def _polygon(value: object, label: str) -> tuple[tuple[float, float], ...]:
    rows = _require_list(value, label)
    if len(rows) != 4:
        raise TranscriptionReviewError(f"{label} must be one four-corner axis-aligned rectangle")
    points: list[tuple[float, float]] = []
    for point_value in rows:
        point = _require_list(point_value, f"{label} point")
        if len(point) != 2:
            raise TranscriptionReviewError(f"{label} point must contain two coordinates")
        x, y = point
        if (
            not isinstance(x, int | float)
            or isinstance(x, bool)
            or not isinstance(y, int | float)
            or isinstance(y, bool)
        ):
            raise TranscriptionReviewError(f"{label} coordinates must be numeric")
        x_value = float(x)
        y_value = float(y)
        if not math.isfinite(x_value) or not math.isfinite(y_value):
            raise TranscriptionReviewError(f"{label} coordinates must be finite")
        if not 0 <= x_value <= 1 or not 0 <= y_value <= 1:
            raise TranscriptionReviewError(f"{label} coordinates must be normalized")
        points.append((x_value, y_value))
    _require_axis_aligned_rectangle(points, label)
    return tuple(points)


def _require_axis_aligned_rectangle(
    polygon: Sequence[tuple[float, float]],
    label: str,
) -> None:
    xs = {point[0] for point in polygon}
    ys = {point[1] for point in polygon}
    if len(xs) != 2 or len(ys) != 2:
        raise TranscriptionReviewError(f"{label} must have two distinct x and y coordinates")
    expected_corners = {(x, y) for x in xs for y in ys}
    if set(polygon) != expected_corners:
        raise TranscriptionReviewError(f"{label} must contain each rectangle corner exactly once")
    for start, end in _polygon_edges(polygon):
        if (start[0] == end[0]) == (start[1] == end[1]):
            raise TranscriptionReviewError(f"{label} corners must follow the rectangle perimeter")


def _cross(
    origin: tuple[float, float],
    left: tuple[float, float],
    right: tuple[float, float],
) -> float:
    return (left[0] - origin[0]) * (right[1] - origin[1]) - (left[1] - origin[1]) * (
        right[0] - origin[0]
    )


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    return (
        abs(_cross(start, end, point)) <= _EPSILON
        and min(start[0], end[0]) - _EPSILON <= point[0] <= max(start[0], end[0]) + _EPSILON
        and min(start[1], end[1]) - _EPSILON <= point[1] <= max(start[1], end[1]) + _EPSILON
    )


def _segments_intersect(
    left_start: tuple[float, float],
    left_end: tuple[float, float],
    right_start: tuple[float, float],
    right_end: tuple[float, float],
) -> bool:
    orientations = (
        _cross(left_start, left_end, right_start),
        _cross(left_start, left_end, right_end),
        _cross(right_start, right_end, left_start),
        _cross(right_start, right_end, left_end),
    )
    if (
        orientations[0] * orientations[1] < -_EPSILON
        and orientations[2] * orientations[3] < -_EPSILON
    ):
        return True
    return (
        (
            abs(orientations[0]) <= _EPSILON
            and _point_on_segment(
                right_start,
                left_start,
                left_end,
            )
        )
        or (
            abs(orientations[1]) <= _EPSILON
            and _point_on_segment(
                right_end,
                left_start,
                left_end,
            )
        )
        or (
            abs(orientations[2]) <= _EPSILON
            and _point_on_segment(
                left_start,
                right_start,
                right_end,
            )
        )
        or (
            abs(orientations[3]) <= _EPSILON
            and _point_on_segment(
                left_end,
                right_start,
                right_end,
            )
        )
    )


def _segments_properly_cross(
    left_start: tuple[float, float],
    left_end: tuple[float, float],
    right_start: tuple[float, float],
    right_end: tuple[float, float],
) -> bool:
    return (
        _cross(left_start, left_end, right_start) * _cross(left_start, left_end, right_end)
        < -_EPSILON
        and _cross(right_start, right_end, left_start) * _cross(right_start, right_end, left_end)
        < -_EPSILON
    )


def _polygon_edges(
    polygon: Sequence[tuple[float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(polygon, (*polygon[1:], polygon[0]), strict=True))


def _require_simple_polygon(
    polygon: Sequence[tuple[float, float]],
    label: str,
) -> None:
    if len(set(polygon)) != len(polygon):
        raise TranscriptionReviewError(f"{label} contains a repeated vertex")
    edges = _polygon_edges(polygon)
    for index, (start, end) in enumerate(edges):
        if start == end:
            raise TranscriptionReviewError(f"{label} contains a zero-length edge")
        for other_index in range(index + 1, len(edges)):
            if other_index == index + 1 or (index == 0 and other_index == len(edges) - 1):
                continue
            if _segments_intersect(start, end, *edges[other_index]):
                raise TranscriptionReviewError(f"{label} is self-intersecting")


def _point_location(
    point: tuple[float, float],
    polygon: Sequence[tuple[float, float]],
) -> str:
    for start, end in _polygon_edges(polygon):
        if _point_on_segment(point, start, end):
            return "boundary"
    inside = False
    x, y = point
    for start, end in _polygon_edges(polygon):
        if (start[1] > y) == (end[1] > y):
            continue
        crossing_x = start[0] + (y - start[1]) * (end[0] - start[0]) / (end[1] - start[1])
        if crossing_x > x:
            inside = not inside
    return "inside" if inside else "outside"


def _polygon_within(
    inner: Sequence[tuple[float, float]],
    outer: Sequence[tuple[float, float]],
) -> bool:
    return _bbox_within(_bbox(inner), _bbox(outer))


def _polygon_output_coverage(
    output: Sequence[tuple[float, float]],
    source: Sequence[tuple[float, float]],
) -> float:
    output_bbox = _bbox(output)
    source_bbox = _bbox(source)
    intersection = _bbox_intersection_area(output_bbox, source_bbox)
    output_area = (output_bbox[2] - output_bbox[0]) * (output_bbox[3] - output_bbox[1])
    return intersection / output_area if output_area > 0 else 0.0


def _bbox(polygon: Sequence[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_within(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> bool:
    return (
        inner[0] + _EPSILON >= outer[0]
        and inner[1] + _EPSILON >= outer[1]
        and inner[2] <= outer[2] + _EPSILON
        and inner[3] <= outer[3] + _EPSILON
    )


def _bbox_iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    intersection_width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    intersection_height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    intersection = intersection_width * intersection_height
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _bbox_intersection_area(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    return width * height


def _bbox_area(bounds: tuple[float, float, float, float]) -> float:
    return max(0.0, bounds[2] - bounds[0]) * max(0.0, bounds[3] - bounds[1])


def _token_bbox(token: Mapping[str, Any]) -> tuple[float, float, float, float]:
    return _bbox(_token_polygon(token))


def _token_polygon(
    token: Mapping[str, Any],
) -> tuple[tuple[float, float], ...]:
    geometry = _require_mapping(token.get("geometry"), "token geometry")
    return _polygon(geometry.get("polygon"), "token polygon")


def _optimal_monotonic_alignment(
    left_tokens: Sequence[Mapping[str, Any]],
    right_tokens: Sequence[Mapping[str, Any]],
    *,
    minimum_bbox_iou: float,
) -> list[tuple[int, int, float]]:
    left_count = len(left_tokens)
    right_count = len(right_tokens)
    scores: list[list[tuple[int, float]]] = [
        [(0, 0.0) for _ in range(right_count + 1)] for _ in range(left_count + 1)
    ]
    choices: list[list[str]] = [["" for _ in range(right_count + 1)] for _ in range(left_count + 1)]
    ious = [
        [_bbox_iou(_token_bbox(left), _token_bbox(right)) for right in right_tokens]
        for left in left_tokens
    ]
    for left_index in range(left_count - 1, -1, -1):
        choices[left_index][right_count] = "left"
    for right_index in range(right_count - 1, -1, -1):
        choices[left_count][right_index] = "right"
    for left_index in range(left_count - 1, -1, -1):
        for right_index in range(right_count - 1, -1, -1):
            candidates: list[tuple[tuple[int, float], int, str]] = [
                (scores[left_index + 1][right_index], 1, "left"),
                (scores[left_index][right_index + 1], 0, "right"),
            ]
            iou = ious[left_index][right_index]
            if iou >= minimum_bbox_iou:
                tail = scores[left_index + 1][right_index + 1]
                candidates.append(((tail[0] + 1, tail[1] + iou), 2, "match"))
            score, _, choice = max(candidates, key=lambda item: (item[0], item[1]))
            scores[left_index][right_index] = score
            choices[left_index][right_index] = choice

    alignment: list[tuple[int, int, float]] = []
    left_index = 0
    right_index = 0
    while left_index < left_count or right_index < right_count:
        choice = choices[left_index][right_index]
        if choice == "match":
            alignment.append(
                (
                    left_index,
                    right_index,
                    ious[left_index][right_index],
                )
            )
            left_index += 1
            right_index += 1
        elif choice == "left":
            left_index += 1
        elif choice == "right":
            right_index += 1
        else:
            break
    return alignment


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TranscriptionReviewError(f"{label} must be an object")
    return value


def _sorted_pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def _require_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TranscriptionReviewError(f"{label} must be a list")
    return value


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TranscriptionReviewError(f"{label} must be a non-empty string")
    return value
