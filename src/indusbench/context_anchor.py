"""Deterministic, metadata-only context anchors derived from Penn snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from indusbench.penn_metadata import (
    PENN_ATTRIBUTION,
    PENN_CSV_URL,
    PENN_INSTITUTION_ID,
    PENN_INSTITUTION_NAME,
    PENN_LANDING_URL,
    PENN_LICENSE_ID,
    PENN_LICENSE_URL,
    PHYSICAL_STATUS_UNKNOWN,
    PRIMARY_SCRIPT_CANDIDATE,
    REPLICA_OR_MODERN,
    validate_penn_metadata_semantics,
)

SCHEMA_VERSION = "0.1.0"
RECORD_STATE = "metadata_context_anchors_untranscribed"
SELECTION_POLICY = "penn_primary_script_candidates_only"
DERIVATION_METHOD_ID = "penn-context-anchor-v1"

PENDING_ORIGINALITY_ROLE = "context_candidate_pending_originality_review"
REPLICA_NEGATIVE_CONTROL_ROLE = "replica_or_modern_negative_control"

CONTEXT_FIELDS = (
    "objectName",
    "nativeName",
    "title",
    "creditLine",
    "description",
    "placeName",
    "siteName",
    "culture",
    "cultureArea",
    "locus",
    "period",
    "material",
    "technique",
    "creator",
    "iconography",
    "iconographySubject",
    "inscriptionMarkLanguage",
    "dateMade",
    "earlyDate",
    "lateDate",
    "depth",
    "length",
    "width",
    "height",
    "thickness",
    "weight",
    "outsideDiameter",
    "measurementUnit",
)

LIMITATIONS = (
    "metadata_only_no_images",
    "no_transcription_or_sign_values",
    "no_meaning_or_language_decipherment_claim",
    "originality_requires_human_review",
    "field_numbers_absent_from_bulk_schema_and_not_inferred",
    "catalog_metadata_may_be_incomplete_or_outdated",
)

_AXIS_FIELDS = (
    ("catalog_identity", ("Record URL", "identifier")),
    ("script_catalog_label", ("inscriptionMarkLanguage",)),
    ("site_context", ("placeName", "siteName")),
    ("culture_context", ("culture", "cultureArea")),
    ("excavation_context", ("locus",)),
    ("chronology_context", ("period", "dateMade", "earlyDate", "lateDate")),
    ("object_form", ("objectName", "nativeName", "title")),
    ("material_technology", ("material", "technique")),
    ("motif_context", ("iconography", "iconographySubject")),
    (
        "measurement_context",
        (
            "depth",
            "length",
            "width",
            "height",
            "thickness",
            "weight",
            "outsideDiameter",
            "measurementUnit",
        ),
    ),
    ("provenance_credit", ("creditLine",)),
    ("catalog_description", ("description",)),
)

_TOP_LEVEL_KEYS = (
    "schema_version",
    "registry_id",
    "record_state",
    "selection_policy",
    "derivation_method_id",
    "source",
    "source_acquisition",
    "rights",
    "source_candidate_count",
    "entry_count",
    "role_counts",
    "entries",
    "limitations",
)
_SOURCE_KEYS = (
    "snapshot_id",
    "institution_id",
    "institution_name",
    "dataset_url",
    "landing_url",
)
_ACQUISITION_KEYS = (
    "retrieved_at",
    "bytes",
    "sha256",
    "etag",
    "last_modified",
    "source_last_updated",
)
_RIGHTS_KEYS = (
    "scope",
    "status",
    "license_id",
    "license_url",
    "attribution",
    "redistribution",
    "derivatives",
    "commercial_use",
    "images_included",
    "media_rights_status",
    "evidence_url",
)
_ROLE_COUNT_KEYS = (
    PENDING_ORIGINALITY_ROLE,
    REPLICA_NEGATIVE_CONTROL_ROLE,
)
_ENTRY_KEYS = (
    "anchor_id",
    "candidate_id",
    "csv_row_number",
    "record_url",
    "accession_number",
    "candidate_classification",
    "physical_status",
    "anchor_role",
    "source_fields",
    "anchor_axes",
    "field_numbers",
    "admission",
    "provenance",
)
_AXIS_KEYS = ("axis", "source_fields")
_FIELD_NUMBER_KEYS = ("status", "values")
_ADMISSION_KEYS = (
    "human_review_required",
    "transcription_approved",
    "meaning_approved",
    "originality_approved",
    "field_number_approved",
)
_PROVENANCE_KEYS = (
    "source_snapshot_id",
    "source_sha256",
    "csv_row_number",
    "raw_fields_sha256",
)
_CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

JsonObject = dict[str, Any]


class ContextAnchorError(ValueError):
    """Raised when a context-anchor registry violates its closed contract."""


def derive_context_anchor_registry(snapshot: Mapping[str, Any]) -> JsonObject:
    """Derive context-only anchors from one valid Penn metadata snapshot."""

    validate_penn_metadata_semantics(snapshot)
    registry = _derive_registry(snapshot)
    validate_context_anchor_registry(registry, source_snapshot=snapshot)
    return registry


def validate_context_anchor_registry(
    registry: Mapping[str, Any],
    *,
    source_snapshot: Mapping[str, Any] | None = None,
) -> None:
    """Validate closed semantics and optionally rederive every entry."""

    _require_exact_keys(registry, _TOP_LEVEL_KEYS, "$")
    if registry.get("schema_version") != SCHEMA_VERSION:
        raise ContextAnchorError("$.schema_version is not supported")
    if registry.get("record_state") != RECORD_STATE:
        raise ContextAnchorError("$.record_state is not the closed metadata-only state")
    if registry.get("selection_policy") != SELECTION_POLICY:
        raise ContextAnchorError("$.selection_policy is not supported")
    if registry.get("derivation_method_id") != DERIVATION_METHOD_ID:
        raise ContextAnchorError("$.derivation_method_id is not supported")
    if registry.get("limitations") != list(LIMITATIONS):
        raise ContextAnchorError("$.limitations must preserve all fixed warnings")

    source = _require_mapping(registry.get("source"), "$.source")
    _require_exact_keys(source, _SOURCE_KEYS, "$.source")
    expected_source_constants = {
        "institution_id": PENN_INSTITUTION_ID,
        "institution_name": PENN_INSTITUTION_NAME,
        "dataset_url": PENN_CSV_URL,
        "landing_url": PENN_LANDING_URL,
    }
    for field, expected in expected_source_constants.items():
        if source.get(field) != expected:
            raise ContextAnchorError(f"$.source.{field} must equal the approved Penn constant")
    snapshot_id = _require_nonempty_string(source.get("snapshot_id"), "$.source.snapshot_id")

    acquisition = _require_mapping(registry.get("source_acquisition"), "$.source_acquisition")
    _require_exact_keys(acquisition, _ACQUISITION_KEYS, "$.source_acquisition")
    source_sha256 = _require_checksum(acquisition.get("sha256"), "$.source_acquisition.sha256")
    if snapshot_id != f"penn-museum-csv:{source_sha256}":
        raise ContextAnchorError("$.source.snapshot_id is not derived from the source digest")
    expected_registry_id = f"penn-context-anchor-registry:{source_sha256}"
    if registry.get("registry_id") != expected_registry_id:
        raise ContextAnchorError("$.registry_id is not derived from the source digest")
    _require_nonempty_string(acquisition.get("retrieved_at"), "$.source_acquisition.retrieved_at")
    _require_positive_integer(acquisition.get("bytes"), "$.source_acquisition.bytes")
    for field in ("etag", "last_modified", "source_last_updated"):
        value = acquisition.get(field)
        if value is not None and (not isinstance(value, str) or not value):
            raise ContextAnchorError(f"$.source_acquisition.{field} must be a string or null")

    rights = _require_mapping(registry.get("rights"), "$.rights")
    _require_exact_keys(rights, _RIGHTS_KEYS, "$.rights")
    expected_rights: dict[str, object] = {
        "scope": "metadata_only",
        "status": "open_licensed",
        "license_id": PENN_LICENSE_ID,
        "license_url": PENN_LICENSE_URL,
        "attribution": PENN_ATTRIBUTION,
        "redistribution": True,
        "derivatives": True,
        "commercial_use": True,
        "images_included": False,
        "media_rights_status": "not_evaluated_not_included",
        "evidence_url": PENN_LANDING_URL,
    }
    if rights != expected_rights:
        raise ContextAnchorError("$.rights must equal the approved metadata-only rights record")

    source_candidate_count = _require_nonnegative_integer(
        registry.get("source_candidate_count"),
        "$.source_candidate_count",
    )
    entry_count = _require_nonnegative_integer(registry.get("entry_count"), "$.entry_count")
    if entry_count > source_candidate_count:
        raise ContextAnchorError("$.entry_count cannot exceed $.source_candidate_count")
    entries = _require_sequence(registry.get("entries"), "$.entries")
    if entry_count != len(entries):
        raise ContextAnchorError("$.entry_count does not equal the entry array length")

    role_counts = _require_mapping(registry.get("role_counts"), "$.role_counts")
    _require_exact_keys(role_counts, _ROLE_COUNT_KEYS, "$.role_counts")
    observed_role_counts: dict[str, int] = dict.fromkeys(_ROLE_COUNT_KEYS, 0)
    seen_anchor_ids: set[str] = set()
    seen_candidate_ids: set[str] = set()
    seen_record_urls: set[str] = set()
    seen_accessions: set[str] = set()
    previous_row_number = 1

    for index, value in enumerate(entries):
        path = f"$.entries[{index}]"
        entry = _require_mapping(value, path)
        _require_exact_keys(entry, _ENTRY_KEYS, path)

        candidate_id = _require_nonempty_string(entry.get("candidate_id"), f"{path}.candidate_id")
        anchor_id = _require_nonempty_string(entry.get("anchor_id"), f"{path}.anchor_id")
        expected_anchor_id = _anchor_id(candidate_id)
        if anchor_id != expected_anchor_id:
            raise ContextAnchorError(f"{path}.anchor_id is not derived from candidate_id")
        record_url = _require_nonempty_string(entry.get("record_url"), f"{path}.record_url")
        accession = _require_nonempty_string(
            entry.get("accession_number"),
            f"{path}.accession_number",
        )
        row_number = _require_positive_integer(
            entry.get("csv_row_number"),
            f"{path}.csv_row_number",
        )
        if row_number <= previous_row_number:
            raise ContextAnchorError(f"{path}.csv_row_number must be strictly increasing")
        previous_row_number = row_number
        for seen, item, label in (
            (seen_anchor_ids, anchor_id, "anchor_id"),
            (seen_candidate_ids, candidate_id, "candidate_id"),
            (seen_record_urls, record_url, "record_url"),
            (seen_accessions, accession, "accession_number"),
        ):
            if item in seen:
                raise ContextAnchorError(f"duplicate {label}: {item!r}")
            seen.add(item)

        if entry.get("candidate_classification") != PRIMARY_SCRIPT_CANDIDATE:
            raise ContextAnchorError(f"{path}.candidate_classification is outside selection policy")
        physical_status = entry.get("physical_status")
        expected_role = _anchor_role(physical_status)
        if entry.get("anchor_role") != expected_role:
            raise ContextAnchorError(f"{path}.anchor_role is not derived from physical_status")
        observed_role_counts[expected_role] += 1

        source_fields = _require_mapping(entry.get("source_fields"), f"{path}.source_fields")
        _require_exact_keys(source_fields, CONTEXT_FIELDS, f"{path}.source_fields")
        for field in CONTEXT_FIELDS:
            if not isinstance(source_fields.get(field), str):
                raise ContextAnchorError(f"{path}.source_fields[{field!r}] must be a raw string")
        expected_axes = _anchor_axes(
            record_url=record_url,
            accession_number=accession,
            source_fields=source_fields,
        )
        axes = _require_sequence(entry.get("anchor_axes"), f"{path}.anchor_axes")
        for axis_index, axis_value in enumerate(axes):
            _require_exact_keys(
                _require_mapping(axis_value, f"{path}.anchor_axes[{axis_index}]"),
                _AXIS_KEYS,
                f"{path}.anchor_axes[{axis_index}]",
            )
        if axes != expected_axes:
            raise ContextAnchorError(
                f"{path}.anchor_axes are not exactly derived from source fields"
            )

        field_numbers = _require_mapping(entry.get("field_numbers"), f"{path}.field_numbers")
        _require_exact_keys(field_numbers, _FIELD_NUMBER_KEYS, f"{path}.field_numbers")
        if field_numbers != {
            "status": "not_available_in_bulk_snapshot",
            "values": [],
        }:
            raise ContextAnchorError(f"{path}.field_numbers must remain unavailable and empty")

        admission = _require_mapping(entry.get("admission"), f"{path}.admission")
        _require_exact_keys(admission, _ADMISSION_KEYS, f"{path}.admission")
        expected_admission = {
            "human_review_required": True,
            "transcription_approved": False,
            "meaning_approved": False,
            "originality_approved": False,
            "field_number_approved": False,
        }
        if admission != expected_admission:
            raise ContextAnchorError(f"{path}.admission must preserve all approval gates")

        provenance = _require_mapping(entry.get("provenance"), f"{path}.provenance")
        _require_exact_keys(provenance, _PROVENANCE_KEYS, f"{path}.provenance")
        if provenance.get("source_snapshot_id") != snapshot_id:
            raise ContextAnchorError(f"{path}.provenance.source_snapshot_id does not match source")
        if provenance.get("source_sha256") != source_sha256:
            raise ContextAnchorError(f"{path}.provenance.source_sha256 does not match source")
        if provenance.get("csv_row_number") != row_number:
            raise ContextAnchorError(f"{path}.provenance.csv_row_number does not match entry")
        _require_checksum(
            provenance.get("raw_fields_sha256"),
            f"{path}.provenance.raw_fields_sha256",
        )

    if role_counts != observed_role_counts:
        raise ContextAnchorError("$.role_counts do not equal the derived entry counts")

    if source_snapshot is not None:
        validate_penn_metadata_semantics(source_snapshot)
        expected = _derive_registry(source_snapshot)
        if registry != expected:
            raise ContextAnchorError("registry does not exactly match the supplied Penn snapshot")


def _derive_registry(snapshot: Mapping[str, Any]) -> JsonObject:
    acquisition = _require_mapping(snapshot.get("source_acquisition"), "$.source_acquisition")
    candidates = _require_sequence(snapshot.get("candidates"), "$.candidates")
    snapshot_id = _require_nonempty_string(snapshot.get("snapshot_id"), "$.snapshot_id")
    source_sha256 = _require_checksum(acquisition.get("sha256"), "$.source_acquisition.sha256")

    entries: list[JsonObject] = []
    for index, value in enumerate(candidates):
        candidate = _require_mapping(value, f"$.candidates[{index}]")
        if candidate.get("classification") != PRIMARY_SCRIPT_CANDIDATE:
            continue
        raw_fields = _require_mapping(
            candidate.get("raw_fields"),
            f"$.candidates[{index}].raw_fields",
        )
        context_fields = {field: raw_fields[field] for field in CONTEXT_FIELDS}
        record_url = _require_nonempty_string(
            candidate.get("record_url"),
            f"$.candidates[{index}].record_url",
        )
        accession = _require_nonempty_string(
            candidate.get("identifier"),
            f"$.candidates[{index}].identifier",
        )
        row_number = _require_positive_integer(
            candidate.get("csv_row_number"),
            f"$.candidates[{index}].csv_row_number",
        )
        candidate_id = _require_nonempty_string(
            candidate.get("candidate_id"),
            f"$.candidates[{index}].candidate_id",
        )
        physical_status = candidate.get("physical_status")
        entries.append(
            {
                "anchor_id": _anchor_id(candidate_id),
                "candidate_id": candidate_id,
                "csv_row_number": row_number,
                "record_url": record_url,
                "accession_number": accession,
                "candidate_classification": PRIMARY_SCRIPT_CANDIDATE,
                "physical_status": physical_status,
                "anchor_role": _anchor_role(physical_status),
                "source_fields": context_fields,
                "anchor_axes": _anchor_axes(
                    record_url=record_url,
                    accession_number=accession,
                    source_fields=context_fields,
                ),
                "field_numbers": {
                    "status": "not_available_in_bulk_snapshot",
                    "values": [],
                },
                "admission": {
                    "human_review_required": True,
                    "transcription_approved": False,
                    "meaning_approved": False,
                    "originality_approved": False,
                    "field_number_approved": False,
                },
                "provenance": {
                    "source_snapshot_id": snapshot_id,
                    "source_sha256": source_sha256,
                    "csv_row_number": row_number,
                    "raw_fields_sha256": _raw_fields_sha256(raw_fields),
                },
            }
        )

    role_counts: dict[str, int] = dict.fromkeys(_ROLE_COUNT_KEYS, 0)
    for entry in entries:
        role_counts[entry["anchor_role"]] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "registry_id": f"penn-context-anchor-registry:{source_sha256}",
        "record_state": RECORD_STATE,
        "selection_policy": SELECTION_POLICY,
        "derivation_method_id": DERIVATION_METHOD_ID,
        "source": {
            "snapshot_id": snapshot_id,
            "institution_id": PENN_INSTITUTION_ID,
            "institution_name": PENN_INSTITUTION_NAME,
            "dataset_url": PENN_CSV_URL,
            "landing_url": PENN_LANDING_URL,
        },
        "source_acquisition": {
            "retrieved_at": acquisition["retrieved_at"],
            "bytes": acquisition["bytes"],
            "sha256": source_sha256,
            "etag": acquisition["etag"],
            "last_modified": acquisition["last_modified"],
            "source_last_updated": acquisition["source_last_updated"],
        },
        "rights": {
            "scope": "metadata_only",
            "status": "open_licensed",
            "license_id": PENN_LICENSE_ID,
            "license_url": PENN_LICENSE_URL,
            "attribution": PENN_ATTRIBUTION,
            "redistribution": True,
            "derivatives": True,
            "commercial_use": True,
            "images_included": False,
            "media_rights_status": "not_evaluated_not_included",
            "evidence_url": PENN_LANDING_URL,
        },
        "source_candidate_count": snapshot["candidate_count"],
        "entry_count": len(entries),
        "role_counts": role_counts,
        "entries": entries,
        "limitations": list(LIMITATIONS),
    }


def _anchor_role(physical_status: object) -> str:
    if physical_status == REPLICA_OR_MODERN:
        return REPLICA_NEGATIVE_CONTROL_ROLE
    if physical_status == PHYSICAL_STATUS_UNKNOWN:
        return PENDING_ORIGINALITY_ROLE
    raise ContextAnchorError(f"unsupported Penn physical status: {physical_status!r}")


def _anchor_axes(
    *,
    record_url: str,
    accession_number: str,
    source_fields: Mapping[str, Any],
) -> list[JsonObject]:
    available: dict[str, str] = {
        "Record URL": record_url,
        "identifier": accession_number,
    }
    for field in CONTEXT_FIELDS:
        value = source_fields.get(field)
        if not isinstance(value, str):
            raise ContextAnchorError(f"source field {field!r} must be a raw string")
        available[field] = value

    axes: list[JsonObject] = []
    for axis, fields in _AXIS_FIELDS:
        evidence_fields = [field for field in fields if available[field].strip()]
        if evidence_fields:
            axes.append({"axis": axis, "source_fields": evidence_fields})
    return axes


def _anchor_id(candidate_id: str) -> str:
    payload = f"{DERIVATION_METHOD_ID}\x00{candidate_id}".encode()
    return f"penn-context-anchor:sha256:{hashlib.sha256(payload).hexdigest()}"


def _raw_fields_sha256(raw_fields: Mapping[str, Any]) -> str:
    payload = json.dumps(
        raw_fields,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _require_mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContextAnchorError(f"{path} must be an object")
    return value


def _require_sequence(value: object, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ContextAnchorError(f"{path} must be an array")
    return value


def _require_exact_keys(value: Mapping[str, Any], keys: Sequence[str], path: str) -> None:
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ContextAnchorError(
            f"{path} is not closed; missing={missing}, unexpected={unexpected}"
        )


def _require_nonempty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContextAnchorError(f"{path} must be a non-empty string")
    return value


def _require_positive_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContextAnchorError(f"{path} must be a positive integer")
    return value


def _require_nonnegative_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContextAnchorError(f"{path} must be a non-negative integer")
    return value


def _require_checksum(value: object, path: str) -> str:
    if not isinstance(value, str) or _CHECKSUM_PATTERN.fullmatch(value) is None:
        raise ContextAnchorError(f"{path} must be a lowercase SHA-256 commitment")
    return value
