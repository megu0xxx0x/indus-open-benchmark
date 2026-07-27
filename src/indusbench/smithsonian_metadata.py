"""Closed, raw-byte-bound normalization of Smithsonian Open Access JSONL.

The exact Smithsonian JSONL container is the trust boundary.  This module does
not fetch anything: callers provide the complete container bytes and select one
one-based line.  Container and line commitments, the byte offset, and every
derived decision are computed here rather than accepted from the caller.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

SCHEMA_VERSION = "0.2.0"

ORIGINAL_CANDIDATE = "original_candidate"
REPLICA_OR_MODERN = "replica_or_modern"
BIBLIOGRAPHIC_CANDIDATE = "bibliographic_candidate"
NOISE_OR_UNRESOLVED = "noise_or_unresolved"

APPROVED_CC0 = "approved_cc0"
QUARANTINED = "quarantined"

MAX_CONTAINER_BYTES = 64 * 1024 * 1024
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 100_000
MAX_NORMALIZED_STRING_CHARACTERS = 8 * 1024 * 1024
MAX_JSONL_LINES = 100_000
MAX_MEDIA_ITEMS = 128
MAX_TEXT_NODES = 4_096
MAX_TEXT_CHARACTERS = 1_000_000
MAX_CLASSIFICATION_EVIDENCE = 256

LIMITATIONS = (
    "raw_source_required_for_semantic_verification",
    "metadata_and_media_have_separate_mandatory_rights_checks",
    "candidate_classification_requires_human_review",
    "media_absence_never_authorizes_web_scraping",
    "approved_media_url_is_the_only_approved_media_resource",
    "no_transcription_or_decipherment_claim",
)

_TOP_LEVEL_KEYS = (
    "schema_version",
    "intake_id",
    "record_state",
    "candidate_classification",
    "classification_reasons",
    "classification_evidence",
    "source_acquisition",
    "raw_record_text",
    "upstream_commitments",
    "record_context",
    "rights",
    "media",
    "limitations",
)
_SOURCE_KEYS = (
    "provider",
    "distribution",
    "url",
    "retrieved_at",
    "etag",
    "last_modified",
    "container",
    "locator",
)
_CONTAINER_KEYS = ("bytes", "sha256")
_LOCATOR_KEYS = (
    "line_number",
    "byte_offset",
    "line_bytes",
    "line_sha256",
    "record_text_bytes",
    "line_ending",
)
_COMMITMENT_KEYS = (
    "id",
    "record_ID",
    "hash",
    "docSignature",
    "lastTimeUpdated",
    "record_sha256",
)
_CONTEXT_KEYS = ("unit_code", "record_url", "record_link", "title")
_RIGHTS_KEYS = ("metadata", "record_restrictions")
_METADATA_RIGHTS_KEYS = (
    "status",
    "normalized_access",
    "reason_codes",
    "original_metadata_usage",
)
_RESTRICTION_KEYS = (
    "contradictory",
    "reason_codes",
    "original_objectRights",
    "original_userestrict",
    "original_accessrestrict",
)
_MEDIA_KEYS = (
    "state",
    "count",
    "approved_count",
    "quarantined_count",
    "items",
)
_MEDIA_ITEM_KEYS = (
    "index",
    "media_id",
    "media_guid",
    "media_type",
    "url",
    "status",
    "normalized_access",
    "reason_codes",
    "original_usage",
)
_EVIDENCE_KEYS = ("kind", "path", "matched_term")

_CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_UPSTREAM_HASH_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_DOC_SIGNATURE_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$"
)
_SOURCE_URL_PATTERN = re.compile(
    r"^https://smithsonian-open-access\.s3-us-west-2\.amazonaws\.com/"
    r"metadata/edan/(?P<unit>[a-z0-9_]{1,128})/(?P<shard>[0-9a-f]{2})\.txt$"
)
_PERCENT_ESCAPE_ERROR_PATTERN = re.compile(r"%(?![0-9A-Fa-f]{2})")
_MEDIA_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_AWS_ACCESS_KEY_VALUE_PATTERN = re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])")
_SECRET_TEXT_PATTERN = re.compile(
    r"(?i)\b(?:"
    r"api[\s_-]?key|x[\s_-]?api[\s_-]?key|"
    r"aws[\s_-]?access[\s_-]?key[\s_-]?id|"
    r"aws[\s_-]?secret[\s_-]?access[\s_-]?key|"
    r"secret[\s_-]?access[\s_-]?key|"
    r"x[\s_-]?amz[\s_-]?(?:credential|signature|security[\s_-]?token)|"
    r"authorization|access[\s_-]?token|bearer[\s_-]?token|client[\s_-]?secret|"
    r"password|passwd|pwd"
    r")\b\s*(?:=|:)\s*[^\s\"'<>]+"
)
_RIGHTS_KEY_MARKERS = (
    "right",
    "restrict",
    "license",
    "licence",
    "usage",
    "permission",
    "termsofuse",
    "condition",
    "embargo",
)
MAX_ACQUISITION_HEADER_LENGTH = 1024
MAX_UNIT_CODE_LENGTH = 128

_CIVILIZATION_OR_SITE_PATTERN = re.compile(
    r"\b(?:"
    r"harappan|indus\s+script|indus\s+(?:valley\s+)?civilization|"
    r"mohenjo[\s-]?daro|harappa|dholavira|lothal|kalibangan|"
    r"rakhigarhi|chanhu[\s-]?daro|banawali|kot[\s-]?diji"
    r")\b",
    re.IGNORECASE,
)
_ARTIFACT_OBJECT_PATTERN = re.compile(
    r"\b(?:"
    r"seal(?:ing|s)?|seal\s+impression(?:s)?|stamp\s+seal(?:s)?|"
    r"tablet(?:s)?|inscription(?:s)?|inscribed|indus\s+script|script|"
    r"amulet(?:s)?|"
    r"inscribed\s+(?:sherd(?:s)?|potsherd(?:s)?|vessel(?:s)?|"
    r"ivory\s+rod(?:s)?|bone\s+rod(?:s)?|token(?:s)?|figurine(?:s)?)"
    r")\b",
    re.IGNORECASE,
)
_REPLICA_OR_MODERN_PATTERN = re.compile(
    r"\b(?:"
    r"plaster(?:\s+of\s+paris)?\s+cast(?:s)?|"
    r"(?:seal|tablet|inscription|artifact)\s*,?\s+cast(?:s)?|"
    r"cast(?:s)?\s+of|replica(?:s)?|reproduction(?:s)?|facsimile(?:s)?|"
    r"modern\s+cop(?:y|ies)|souvenir\s+cop(?:y|ies)"
    r")\b",
    re.IGNORECASE,
)

_BIBLIOGRAPHIC_UNIT_CODES = frozenset({"SIL", "SLA_SRO"})
_NATURAL_HISTORY_UNIT_CODES = frozenset(
    {
        "NMNH",
        "NMNHBIRDS",
        "NMNHBOTANY",
        "NMNHEDUCATION",
        "NMNHENTO",
        "NMNHFISHES",
        "NMNHHERPS",
        "NMNHINV",
        "NMNHMAMMALS",
        "NMNHMINSCI",
        "NMNHPALEO",
        "NZP",
    }
)
_RIGHTS_SKIP_KEYS = frozenset(
    {
        "metadata_usage",
        "objectrights",
        "userestrict",
        "accessrestrict",
        "online_media",
    }
)
_USAGE_KEYS = frozenset({"access", "codes", "text"})
_SENSITIVE_KEY_NAMES = frozenset(
    {
        "apikey",
        "xapikey",
        "authorization",
        "accesstoken",
        "bearertoken",
        "clientsecret",
        "awsaccesskeyid",
        "awssecretaccesskey",
        "secretaccesskey",
        "password",
        "passwd",
        "pwd",
        "xamzcredential",
        "xamzsignature",
        "xamzsecuritytoken",
    }
)

JsonObject = dict[str, Any]
JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


class SmithsonianMetadataError(ValueError):
    """Raised when a Smithsonian record violates the closed intake contract."""


@dataclass(frozen=True)
class _LocatedJsonLine:
    record: JsonObject
    raw_text: str
    line_number: int
    byte_offset: int
    line_bytes: int
    line_sha256: str
    record_text_bytes: int
    line_ending: str


def normalize_smithsonian_record(
    raw_jsonl_bytes: bytes,
    *,
    source_url: str,
    retrieved_at: str,
    line_number: int,
    etag: str | None,
    last_modified: str | None,
) -> JsonObject:
    """Normalize one line selected from an exact Smithsonian JSONL container.

    The complete container bytes are hashed internally.  ``line_number`` is the
    only caller-supplied locator; its byte offset and exact line commitment are
    derived while parsing the container.
    """

    normalized = _normalize_from_raw(
        raw_jsonl_bytes,
        source_url=source_url,
        retrieved_at=retrieved_at,
        line_number=line_number,
        etag=etag,
        last_modified=last_modified,
    )
    validate_smithsonian_metadata_semantics(
        normalized,
        raw_jsonl_bytes=raw_jsonl_bytes,
    )
    return normalized


def validate_smithsonian_metadata_semantics(
    value: Mapping[str, Any],
    *,
    raw_jsonl_bytes: bytes,
) -> None:
    """Rebuild every normalized field from the exact raw JSONL bytes."""

    _validate_json_depth(value, "$")
    cloned = _clone_json(value, "$")
    if not isinstance(cloned, dict):
        raise SmithsonianMetadataError("$ must be a JSON object")
    _reject_secrets(cloned, "$")
    _require_exact_keys(cloned, _TOP_LEVEL_KEYS, "$")
    if cloned.get("schema_version") != SCHEMA_VERSION:
        raise SmithsonianMetadataError("$.schema_version is not supported")

    source = _require_mapping(cloned.get("source_acquisition"), "$.source_acquisition")
    _require_exact_keys(source, _SOURCE_KEYS, "$.source_acquisition")
    container = _require_mapping(source.get("container"), "$.source_acquisition.container")
    _require_exact_keys(container, _CONTAINER_KEYS, "$.source_acquisition.container")
    locator = _require_mapping(source.get("locator"), "$.source_acquisition.locator")
    _require_exact_keys(locator, _LOCATOR_KEYS, "$.source_acquisition.locator")

    expected = _normalize_from_raw(
        raw_jsonl_bytes,
        source_url=_require_nonempty_string(
            source.get("url"),
            "$.source_acquisition.url",
        ),
        retrieved_at=_require_nonempty_string(
            source.get("retrieved_at"),
            "$.source_acquisition.retrieved_at",
        ),
        line_number=_require_positive_integer(
            locator.get("line_number"),
            "$.source_acquisition.locator.line_number",
        ),
        etag=_optional_nonempty_string(
            source.get("etag"),
            "$.source_acquisition.etag",
        ),
        last_modified=_optional_nonempty_string(
            source.get("last_modified"),
            "$.source_acquisition.last_modified",
        ),
    )
    if cloned != expected:
        path = _first_difference(cloned, expected, "$")
        raise SmithsonianMetadataError(
            f"{path} does not exactly match the committed raw Smithsonian record"
        )


def _normalize_from_raw(
    raw_jsonl_bytes: bytes,
    *,
    source_url: str,
    retrieved_at: str,
    line_number: int,
    etag: str | None,
    last_modified: str | None,
) -> JsonObject:
    source_match = _validate_acquisition_inputs(
        raw_jsonl_bytes,
        source_url=source_url,
        retrieved_at=retrieved_at,
        line_number=line_number,
        etag=etag,
        last_modified=last_modified,
    )
    located = _locate_jsonl_record(raw_jsonl_bytes, line_number)
    record = located.record
    _reject_secrets(record, "$")
    if record.get("type") != "edanmdm":
        raise SmithsonianMetadataError("$.type must equal 'edanmdm'")

    content = _require_mapping(record.get("content"), "$.content")
    descriptive = _require_mapping(
        content.get("descriptiveNonRepeating"),
        "$.content.descriptiveNonRepeating",
    )
    freetext = _optional_mapping(content.get("freetext"), "$.content.freetext")
    _optional_mapping(content.get("indexedStructured"), "$.content.indexedStructured")

    upstream = _build_upstream_commitments(
        record,
        descriptive,
        source_shard=source_match.group("shard"),
    )
    context = _build_record_context(record, descriptive)
    classification, reasons, evidence = _classify_record(record, context["unit_code"])

    metadata_rights = _normalize_metadata_rights(descriptive.get("metadata_usage"))
    restrictions = _normalize_record_restrictions(freetext, record)
    metadata_approved = metadata_rights["status"] == APPROVED_CC0
    media = _normalize_media(
        descriptive.get("online_media"),
        restrictions,
        metadata_approved=metadata_approved,
    )
    record_state = "metadata_approved" if metadata_approved else "quarantined_metadata_rights"

    container_sha256 = f"sha256:{hashlib.sha256(raw_jsonl_bytes).hexdigest()}"
    source_acquisition: JsonObject = {
        "provider": "Smithsonian Open Access",
        "distribution": "Smithsonian Open Access AWS JSONL",
        "url": source_url,
        "retrieved_at": retrieved_at,
        "etag": etag,
        "last_modified": last_modified,
        "container": {
            "bytes": len(raw_jsonl_bytes),
            "sha256": container_sha256,
        },
        "locator": {
            "line_number": located.line_number,
            "byte_offset": located.byte_offset,
            "line_bytes": located.line_bytes,
            "line_sha256": located.line_sha256,
            "record_text_bytes": located.record_text_bytes,
            "line_ending": located.line_ending,
        },
    }
    intake_id = _derive_intake_id(source_acquisition, upstream["record_sha256"])
    return {
        "schema_version": SCHEMA_VERSION,
        "intake_id": intake_id,
        "record_state": record_state,
        "candidate_classification": classification,
        "classification_reasons": reasons,
        "classification_evidence": evidence,
        "source_acquisition": source_acquisition,
        "raw_record_text": located.raw_text,
        "upstream_commitments": upstream,
        "record_context": context,
        "rights": {
            "metadata": metadata_rights,
            "record_restrictions": restrictions,
        },
        "media": media,
        "limitations": list(LIMITATIONS),
    }


def _validate_acquisition_inputs(
    raw_jsonl_bytes: object,
    *,
    source_url: object,
    retrieved_at: object,
    line_number: object,
    etag: object,
    last_modified: object,
) -> re.Match[str]:
    if not isinstance(raw_jsonl_bytes, bytes):
        raise SmithsonianMetadataError("raw_jsonl_bytes must be exact bytes")
    if not raw_jsonl_bytes:
        raise SmithsonianMetadataError("raw_jsonl_bytes must not be empty")
    if len(raw_jsonl_bytes) > MAX_CONTAINER_BYTES:
        raise SmithsonianMetadataError(
            f"raw_jsonl_bytes exceeds the {MAX_CONTAINER_BYTES}-byte container limit"
        )
    if b"\x00" in raw_jsonl_bytes:
        raise SmithsonianMetadataError("raw_jsonl_bytes contains a forbidden NUL byte")
    try:
        raw_jsonl_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SmithsonianMetadataError(
            f"raw_jsonl_bytes is not strict UTF-8 at byte {error.start}"
        ) from error

    source_url_string = _require_nonempty_string(source_url, "source_url")
    if len(source_url_string) > 512:
        raise SmithsonianMetadataError("source_url exceeds the 512-character limit")
    if _has_control_or_space(source_url_string):
        raise SmithsonianMetadataError("source_url contains whitespace or a control character")
    source_match = _SOURCE_URL_PATTERN.fullmatch(source_url_string)
    if source_match is None:
        raise SmithsonianMetadataError(
            "source_url must be a canonical Smithsonian AWS EDAN JSONL shard URL "
            "without a query, fragment, credentials, or port"
        )
    _reject_secret_text(source_url_string, "source_url")

    retrieved_at_string = _require_nonempty_string(retrieved_at, "retrieved_at")
    _require_rfc3339(retrieved_at_string, "retrieved_at")
    _require_positive_integer(line_number, "line_number")
    etag_string = _optional_nonempty_string(etag, "etag")
    modified_string = _optional_nonempty_string(last_modified, "last_modified")
    if etag_string is not None:
        if len(etag_string) > MAX_ACQUISITION_HEADER_LENGTH or _has_control(etag_string):
            raise SmithsonianMetadataError(
                f"etag exceeds the {MAX_ACQUISITION_HEADER_LENGTH}-character limit "
                "or contains a control character"
            )
        _reject_secret_text(etag_string, "etag")
    if modified_string is not None:
        if len(modified_string) > MAX_ACQUISITION_HEADER_LENGTH or _has_control(modified_string):
            raise SmithsonianMetadataError(
                f"last_modified exceeds the {MAX_ACQUISITION_HEADER_LENGTH}-character "
                "limit or contains a control character"
            )
        _reject_secret_text(modified_string, "last_modified")
    return source_match


def _locate_jsonl_record(raw_jsonl_bytes: bytes, selected_line: int) -> _LocatedJsonLine:
    offset = 0
    current_line = 0
    selected: _LocatedJsonLine | None = None
    total_bytes = len(raw_jsonl_bytes)

    while offset < total_bytes:
        current_line += 1
        if current_line > MAX_JSONL_LINES:
            raise SmithsonianMetadataError(
                f"JSONL container exceeds the {MAX_JSONL_LINES}-line limit"
            )
        newline = raw_jsonl_bytes.find(b"\n", offset)
        if newline < 0:
            span_end = total_bytes
            content_end = total_bytes
            line_ending = "none"
        else:
            span_end = newline + 1
            if newline > offset and raw_jsonl_bytes[newline - 1 : newline] == b"\r":
                content_end = newline - 1
                line_ending = "crlf"
            else:
                content_end = newline
                line_ending = "lf"

        record_bytes = raw_jsonl_bytes[offset:content_end]
        line_span = raw_jsonl_bytes[offset:span_end]
        if not record_bytes.strip():
            raise SmithsonianMetadataError(f"JSONL line {current_line} is blank")
        if b"\r" in record_bytes:
            raise SmithsonianMetadataError(
                f"JSONL line {current_line} contains a bare carriage return"
            )
        if len(record_bytes) > MAX_RECORD_BYTES:
            raise SmithsonianMetadataError(
                f"JSONL line {current_line} exceeds the {MAX_RECORD_BYTES}-byte record limit"
            )

        record, raw_text = _parse_json_record(record_bytes, current_line)
        if current_line == selected_line:
            selected = _LocatedJsonLine(
                record=record,
                raw_text=raw_text,
                line_number=current_line,
                byte_offset=offset,
                line_bytes=len(line_span),
                line_sha256=f"sha256:{hashlib.sha256(line_span).hexdigest()}",
                record_text_bytes=len(record_bytes),
                line_ending=line_ending,
            )
        offset = span_end

    if selected is None:
        raise SmithsonianMetadataError(
            f"line_number {selected_line} exceeds the {current_line}-line JSONL container"
        )
    return selected


def _parse_json_record(record_bytes: bytes, line_number: int) -> tuple[JsonObject, str]:
    try:
        raw_text = record_bytes.decode("utf-8", errors="strict")
        value = json.loads(
            raw_text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError as error:
        raise SmithsonianMetadataError(
            f"JSONL line {line_number} is not strict UTF-8 at record byte {error.start}"
        ) from error
    except json.JSONDecodeError as error:
        raise SmithsonianMetadataError(
            f"JSONL line {line_number} is not one strict JSON value: {error.msg}"
        ) from error
    except RecursionError as error:
        raise SmithsonianMetadataError(
            f"JSONL line {line_number} exceeds the JSON parser depth limit"
        ) from error
    except SmithsonianMetadataError as error:
        raise SmithsonianMetadataError(f"JSONL line {line_number}: {error}") from error
    except (ValueError, OverflowError) as error:
        raise SmithsonianMetadataError(
            f"JSONL line {line_number} contains a value the JSON parser cannot represent"
        ) from error
    if not isinstance(value, dict):
        raise SmithsonianMetadataError(f"JSONL line {line_number} must contain a JSON object")
    _validate_json_depth(value, f"$line[{line_number}]")
    cloned = _clone_json(value, f"$line[{line_number}]")
    if not isinstance(cloned, dict):
        raise SmithsonianMetadataError(f"JSONL line {line_number} must contain a JSON object")
    return cloned, raw_text


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise SmithsonianMetadataError(f"JSON object contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise SmithsonianMetadataError(f"JSON contains forbidden non-finite constant {value!r}")


def _derive_intake_id(
    source_acquisition: Mapping[str, Any],
    record_sha256: object,
) -> str:
    container = _require_mapping(
        source_acquisition.get("container"),
        "$.source_acquisition.container",
    )
    locator = _require_mapping(
        source_acquisition.get("locator"),
        "$.source_acquisition.locator",
    )
    identity = {
        "source_url": source_acquisition.get("url"),
        "retrieved_at": source_acquisition.get("retrieved_at"),
        "etag": source_acquisition.get("etag"),
        "last_modified": source_acquisition.get("last_modified"),
        "container_bytes": container.get("bytes"),
        "container_sha256": container.get("sha256"),
        "line_number": locator.get("line_number"),
        "byte_offset": locator.get("byte_offset"),
        "line_bytes": locator.get("line_bytes"),
        "line_sha256": locator.get("line_sha256"),
        "record_text_bytes": locator.get("record_text_bytes"),
        "line_ending": locator.get("line_ending"),
        "record_sha256": record_sha256,
    }
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"smithsonian-jsonl-record:sha256:{hashlib.sha256(canonical).hexdigest()}"


def _build_upstream_commitments(
    record: JsonObject,
    descriptive: Mapping[str, Any],
    *,
    source_shard: str,
) -> JsonObject:
    record_id = _require_nonempty_string(
        descriptive.get("record_ID"),
        "$.content.descriptiveNonRepeating.record_ID",
    )
    record_url = _require_nonempty_string(record.get("url"), "$.url")
    if record_url != f"edanmdm:{record_id}":
        raise SmithsonianMetadataError("$.url must equal 'edanmdm:' plus record_ID")
    upstream_hash = _require_nonempty_string(record.get("hash"), "$.hash")
    if _UPSTREAM_HASH_PATTERN.fullmatch(upstream_hash) is None:
        raise SmithsonianMetadataError("$.hash must be 40 lowercase hexadecimal characters")
    if not upstream_hash.startswith(source_shard):
        raise SmithsonianMetadataError("$.hash does not belong to the source JSONL shard")
    doc_signature = _require_nonempty_string(record.get("docSignature"), "$.docSignature")
    if _DOC_SIGNATURE_PATTERN.fullmatch(doc_signature) is None:
        raise SmithsonianMetadataError("$.docSignature must be 32 lowercase hexadecimal characters")
    updated = record.get("lastTimeUpdated")
    if (
        isinstance(updated, bool)
        or not isinstance(updated, int | str)
        or (isinstance(updated, int) and updated < 0)
        or (isinstance(updated, str) and not updated.strip())
    ):
        raise SmithsonianMetadataError(
            "$.lastTimeUpdated must be a nonnegative integer or nonempty string"
        )

    canonical = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "id": _require_nonempty_string(record.get("id"), "$.id"),
        "record_ID": record_id,
        "hash": upstream_hash,
        "docSignature": doc_signature,
        "lastTimeUpdated": updated,
        "record_sha256": f"sha256:{hashlib.sha256(canonical).hexdigest()}",
    }


def _build_record_context(
    record: Mapping[str, Any],
    descriptive: Mapping[str, Any],
) -> JsonObject:
    unit_code = _require_nonempty_string(record.get("unitCode"), "$.unitCode")
    if len(unit_code) > MAX_UNIT_CODE_LENGTH:
        raise SmithsonianMetadataError(
            f"$.unitCode exceeds the {MAX_UNIT_CODE_LENGTH}-character limit"
        )
    nested_unit_code = descriptive.get("unit_code")
    if nested_unit_code is not None and nested_unit_code != unit_code:
        raise SmithsonianMetadataError(
            "$.unitCode and $.content.descriptiveNonRepeating.unit_code disagree"
        )

    top_title = record.get("title")
    _require_optional_string(top_title, "$.title")
    title_object = descriptive.get("title")
    nested_title = title_object.get("content") if isinstance(title_object, Mapping) else None
    _require_optional_string(
        nested_title,
        "$.content.descriptiveNonRepeating.title.content",
    )
    if (
        isinstance(top_title, str)
        and top_title
        and isinstance(nested_title, str)
        and nested_title
        and top_title != nested_title
    ):
        raise SmithsonianMetadataError("$.title and descriptive title disagree")
    title = top_title if isinstance(top_title, str) else nested_title

    record_link = descriptive.get("record_link")
    _require_optional_string(
        record_link,
        "$.content.descriptiveNonRepeating.record_link",
    )
    return {
        "unit_code": unit_code,
        "record_url": _require_nonempty_string(record.get("url"), "$.url"),
        "record_link": record_link,
        "title": title,
    }


def _classify_record(
    record: Mapping[str, Any],
    unit_code: object,
) -> tuple[str, list[str], list[JsonObject]]:
    if not isinstance(unit_code, str):
        raise SmithsonianMetadataError("$.unitCode must be a string")
    normalized_unit = unicodedata.normalize("NFKC", unit_code).strip().upper()

    if normalized_unit in _BIBLIOGRAPHIC_UNIT_CODES:
        return (
            BIBLIOGRAPHIC_CANDIDATE,
            ["bibliographic_unit"],
            [
                {
                    "kind": "bibliographic_unit",
                    "path": "$.unitCode",
                    "matched_term": normalized_unit,
                }
            ],
        )
    if normalized_unit in _NATURAL_HISTORY_UNIT_CODES:
        return (
            NOISE_OR_UNRESOLVED,
            ["natural_history_unit", "artifact_origin_not_established"],
            [
                {
                    "kind": "natural_history_unit",
                    "path": "$.unitCode",
                    "matched_term": normalized_unit,
                }
            ],
        )

    nodes: list[tuple[str, str]] = []
    text_characters = 0
    for path, text in _classification_text_nodes(record):
        nodes.append((path, text))
        text_characters += len(text)
        if len(nodes) > MAX_TEXT_NODES:
            raise SmithsonianMetadataError(
                f"classification text exceeds the {MAX_TEXT_NODES}-node limit"
            )
        if text_characters > MAX_TEXT_CHARACTERS:
            raise SmithsonianMetadataError(
                f"classification text exceeds the {MAX_TEXT_CHARACTERS}-character limit"
            )
    nodes.sort(key=lambda item: item[0])
    civilization = _pattern_evidence(
        nodes,
        _CIVILIZATION_OR_SITE_PATTERN,
        "civilization_or_site",
    )
    artifact = _pattern_evidence(nodes, _ARTIFACT_OBJECT_PATTERN, "artifact_object")
    replica = _pattern_evidence(nodes, _REPLICA_OR_MODERN_PATTERN, "replica_or_modern")

    if civilization and artifact and replica:
        return (
            REPLICA_OR_MODERN,
            [
                "civilization_or_site_marker",
                "artifact_object_marker",
                "replica_or_modern_marker",
            ],
            _sorted_unique_evidence([*civilization, *artifact, *replica]),
        )
    if civilization and artifact:
        return (
            ORIGINAL_CANDIDATE,
            [
                "civilization_or_site_marker",
                "artifact_object_marker",
                "requires_human_originality_review",
            ],
            _sorted_unique_evidence([*civilization, *artifact]),
        )
    missing_reason = (
        "missing_artifact_object_marker" if civilization else "missing_civilization_or_site_marker"
    )
    return (
        NOISE_OR_UNRESOLVED,
        [missing_reason, "artifact_origin_not_established"],
        _sorted_unique_evidence([*civilization, *artifact, *replica]),
    )


def _classification_text_nodes(record: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    title = record.get("title")
    if isinstance(title, str):
        yield "$.title", title
    content = record.get("content")
    if not isinstance(content, Mapping):
        return
    for key in ("freetext", "indexedStructured"):
        value = content.get(key)
        if value is not None:
            yield from _iter_text(value, f"$.content.{key}", skip_rights=True)
    descriptive = content.get("descriptiveNonRepeating")
    if isinstance(descriptive, Mapping) and descriptive.get("title") is not None:
        yield from _iter_text(
            descriptive["title"],
            "$.content.descriptiveNonRepeating.title",
            skip_rights=True,
        )


def _iter_text(
    value: object,
    path: str,
    *,
    skip_rights: bool,
) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_text(item, f"{path}[{index}]", skip_rights=skip_rights)
    elif isinstance(value, Mapping):
        for key in sorted(value):
            if not isinstance(key, str):
                continue
            if skip_rights and key.casefold() in _RIGHTS_SKIP_KEYS:
                continue
            yield from _iter_text(
                value[key],
                f"{path}.{key}",
                skip_rights=skip_rights,
            )


def _pattern_evidence(
    nodes: list[tuple[str, str]],
    pattern: re.Pattern[str],
    kind: str,
) -> list[JsonObject]:
    evidence: list[JsonObject] = []
    for path, value in nodes:
        normalized = unicodedata.normalize("NFKC", value)
        for match in pattern.finditer(normalized):
            evidence.append(
                {
                    "kind": kind,
                    "path": path,
                    "matched_term": " ".join(match.group(0).casefold().split()),
                }
            )
            if len(evidence) > MAX_CLASSIFICATION_EVIDENCE:
                raise SmithsonianMetadataError(
                    f"classification evidence exceeds the {MAX_CLASSIFICATION_EVIDENCE}-item limit"
                )
    return _sorted_unique_evidence(evidence)


def _sorted_unique_evidence(evidence: list[JsonObject]) -> list[JsonObject]:
    seen: set[tuple[object, object, object]] = set()
    result: list[JsonObject] = []
    for item in sorted(
        evidence,
        key=lambda value: (
            str(value["kind"]),
            str(value["path"]),
            str(value["matched_term"]),
        ),
    ):
        key = (item["kind"], item["path"], item["matched_term"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    if len(result) > MAX_CLASSIFICATION_EVIDENCE:
        raise SmithsonianMetadataError(
            f"classification evidence exceeds the {MAX_CLASSIFICATION_EVIDENCE}-item limit"
        )
    return result


def _normalize_metadata_rights(value: object) -> JsonObject:
    original = _clone_json(value, "$.content.descriptiveNonRepeating.metadata_usage")
    reasons = _usage_reason_codes(original, "metadata")
    status = APPROVED_CC0 if not reasons else QUARANTINED
    return {
        "status": status,
        "normalized_access": "CC0" if status == APPROVED_CC0 else None,
        "reason_codes": reasons,
        "original_metadata_usage": original,
    }


def _usage_reason_codes(value: JsonValue, prefix: str) -> list[str]:
    reasons: list[str] = []
    if value is None:
        return [f"{prefix}_usage_missing"]
    if not isinstance(value, dict):
        return [f"{prefix}_usage_malformed"]

    unknown_substantive = sorted(
        key
        for key, item in value.items()
        if key not in _USAGE_KEYS and _has_substantive_value(item)
    )
    if unknown_substantive:
        reasons.append(f"{prefix}_usage_unknown_substantive_field")

    access = value.get("access")
    normalized_access = _normalize_access(access)
    if access is None or (isinstance(access, str) and not access.strip()):
        reasons.append(f"{prefix}_access_missing")
    elif normalized_access != "CC0":
        reasons.append(
            f"{prefix}_usage_conditions_apply"
            if _is_usage_conditions(access)
            else f"{prefix}_access_not_cc0"
        )

    if "codes" in value:
        codes = value["codes"]
        if codes is None or codes == []:
            pass
        elif not isinstance(codes, list):
            reasons.append(f"{prefix}_codes_malformed")
        elif any(
            not isinstance(code, str) or not code.strip() or _normalize_access(code) != "CC0"
            for code in codes
        ):
            reasons.append(f"{prefix}_codes_conflict")

    if "text" in value:
        text = value["text"]
        if text is None or (isinstance(text, str) and not text.strip()):
            pass
        elif not isinstance(text, str):
            reasons.append(f"{prefix}_text_malformed")
        elif _normalize_access(text) != "CC0":
            reasons.append(f"{prefix}_text_conflict")
    return list(dict.fromkeys(reasons))


def _normalize_record_restrictions(
    freetext: Mapping[str, Any],
    record: Mapping[str, Any],
) -> JsonObject:
    object_rights = _clone_json(freetext.get("objectRights"), "$.content.freetext.objectRights")
    use_restriction = _clone_json(
        freetext.get("userestrict"),
        "$.content.freetext.userestrict",
    )
    access_restriction = _clone_json(
        freetext.get("accessrestrict"),
        "$.content.freetext.accessrestrict",
    )
    reasons: list[str] = []
    if _object_rights_contradict_cc0(object_rights):
        reasons.append("object_rights_contradiction")
    if _has_substantive_value(use_restriction):
        reasons.append("use_restriction_present")
    if _has_substantive_value(access_restriction):
        reasons.append("access_restriction_present")
    known_restriction_keys = {
        "objectrights",
        "userestrict",
        "accessrestrict",
    }
    for key, item in freetext.items():
        normalized_key = _normalized_key(key)
        if (
            normalized_key not in known_restriction_keys
            and any(marker in normalized_key for marker in _RIGHTS_KEY_MARKERS)
            and _has_substantive_value(item)
        ):
            reasons.append("unknown_record_restriction_field")
            break
    if _has_unknown_rights_field(record):
        reasons.append("unknown_record_restriction_field")
    reasons = list(dict.fromkeys(reasons))
    return {
        "contradictory": bool(reasons),
        "reason_codes": reasons,
        "original_objectRights": object_rights,
        "original_userestrict": use_restriction,
        "original_accessrestrict": access_restriction,
    }


def _normalize_media(
    online_media_value: object,
    restrictions: Mapping[str, Any],
    *,
    metadata_approved: bool,
) -> JsonObject:
    if online_media_value is None:
        media_values: list[object] = []
    else:
        online_media = _require_mapping(
            online_media_value,
            "$.content.descriptiveNonRepeating.online_media",
        )
        media_values = _require_list(
            online_media.get("media", []),
            "$.content.descriptiveNonRepeating.online_media.media",
        )
        if len(media_values) > MAX_MEDIA_ITEMS:
            raise SmithsonianMetadataError(f"online_media exceeds the {MAX_MEDIA_ITEMS}-item limit")
        media_count = online_media.get("mediaCount")
        if media_count is not None and (
            isinstance(media_count, bool)
            or not isinstance(media_count, int)
            or media_count != len(media_values)
        ):
            raise SmithsonianMetadataError(
                "$.content.descriptiveNonRepeating.online_media.mediaCount "
                "must equal the media array length"
            )

    restriction_reasons = restrictions.get("reason_codes")
    if not isinstance(restriction_reasons, list) or any(
        not isinstance(reason, str) for reason in restriction_reasons
    ):
        raise SmithsonianMetadataError("$.rights.record_restrictions.reason_codes is invalid")

    items: list[JsonObject] = []
    for index, value in enumerate(media_values):
        path = f"$.content.descriptiveNonRepeating.online_media.media[{index}]"
        media = _require_mapping(value, path)
        usage = _clone_json(media.get("usage"), f"{path}.usage")
        media_type = _optional_scalar_string(media.get("type"), f"{path}.type")
        url = media.get("content")
        reasons = _usage_reason_codes(usage, "media")
        if not metadata_approved:
            reasons.append("record_metadata_not_cc0")
        if media_type != "Images":
            reasons.append("media_type_not_image")
        if url is None or (isinstance(url, str) and not url.strip()):
            reasons.append("media_url_missing")
        elif not isinstance(url, str) or not _is_safe_smithsonian_image_url(url):
            reasons.append("media_url_not_approved_smithsonian_image")
        reasons.extend(restriction_reasons)
        reasons = list(dict.fromkeys(reasons))
        status = APPROVED_CC0 if not reasons else QUARANTINED
        items.append(
            {
                "index": index,
                "media_id": _optional_scalar_string(media.get("id"), f"{path}.id"),
                "media_guid": _optional_scalar_string(media.get("guid"), f"{path}.guid"),
                "media_type": media_type,
                "url": url if isinstance(url, str) else None,
                "status": status,
                "normalized_access": "CC0" if status == APPROVED_CC0 else None,
                "reason_codes": reasons,
                "original_usage": usage,
            }
        )

    approved_count = sum(item["status"] == APPROVED_CC0 for item in items)
    return {
        "state": "present" if items else "absent_metadata_only",
        "count": len(items),
        "approved_count": approved_count,
        "quarantined_count": len(items) - approved_count,
        "items": items,
    }


def _is_safe_smithsonian_image_url(value: str) -> bool:
    if _has_control_or_space(value) or _PERCENT_ESCAPE_ERROR_PATTERN.search(value):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or parsed.hostname != "ids.si.edu"
        or parsed.netloc != "ids.si.edu"
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/ids/deliveryService"
        or parsed.fragment
    ):
        return False
    try:
        query = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=4,
        )
    except ValueError:
        return False
    if len(query) != 1 or query[0][0] != "id":
        return False
    media_id = query[0][1]
    if "://" in media_id or media_id.casefold().startswith(("file:", "data:", "javascript:")):
        return False
    return _MEDIA_ID_PATTERN.fullmatch(media_id) is not None


def _normalize_access(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).split()).upper()
    return normalized or None


def _is_usage_conditions(value: object) -> bool:
    return _normalize_access(value) == "USAGE CONDITIONS APPLY"


def _object_rights_contradict_cc0(value: JsonValue) -> bool:
    if not _has_substantive_value(value):
        return False
    semantic_values = list(_rights_semantic_values(value))
    if not semantic_values:
        return True
    return any(_normalize_access(item) != "CC0" for item in semantic_values)


def _rights_semantic_values(
    value: JsonValue,
    *,
    semantic_parent: bool = False,
) -> Iterator[object]:
    if isinstance(value, str):
        if semantic_parent and value.strip():
            yield value
    elif isinstance(value, list):
        for item in value:
            yield from _rights_semantic_values(item, semantic_parent=semantic_parent)
    elif isinstance(value, dict):
        for key, item in value.items():
            normalized_key = _normalized_key(key)
            # EDAN commonly supplies a human-readable ``label`` sibling.
            # Only its observed structural value is non-semantic. Every other
            # label or substantive sibling is rights-bearing; otherwise a
            # restriction could hide in a future field.
            harmless_structural_label = (
                not semantic_parent
                and normalized_key == "label"
                and isinstance(item, str)
                and " ".join(unicodedata.normalize("NFKC", item).casefold().split())
                == "restrictions & rights"
            )
            if harmless_structural_label:
                continue
            semantic = semantic_parent or normalized_key != "label" or _has_substantive_value(item)
            yield from _rights_semantic_values(item, semantic_parent=semantic)
    elif semantic_parent:
        yield value


def _has_unknown_rights_field(
    value: object,
    path: tuple[str | int, ...] = (),
) -> bool:
    if isinstance(value, list):
        return any(
            _has_unknown_rights_field(item, (*path, index)) for index, item in enumerate(value)
        )
    if not isinstance(value, Mapping):
        return False
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        item_path = (*path, key)
        if _is_explicitly_parsed_rights_path(item_path):
            continue
        normalized_key = _normalized_key(key)
        if any(
            marker in normalized_key for marker in _RIGHTS_KEY_MARKERS
        ) and _has_substantive_value(item):
            return True
        if _has_unknown_rights_field(item, item_path):
            return True
    return False


def _is_explicitly_parsed_rights_path(path: tuple[str | int, ...]) -> bool:
    if path in {
        ("content", "descriptiveNonRepeating", "metadata_usage"),
        ("content", "freetext", "objectRights"),
        ("content", "freetext", "userestrict"),
        ("content", "freetext", "accessrestrict"),
    }:
        return True
    return (
        len(path) == 6
        and path[:4]
        == (
            "content",
            "descriptiveNonRepeating",
            "online_media",
            "media",
        )
        and isinstance(path[4], int)
        and path[5] == "usage"
    )


def _has_substantive_value(value: JsonValue | object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_substantive_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_substantive_value(item) for item in value.values())
    return True


def _reject_secrets(value: JsonValue, path: str) -> None:
    if isinstance(value, str):
        _reject_secret_text(value, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secrets(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            if _normalized_key(key) in _SENSITIVE_KEY_NAMES:
                raise SmithsonianMetadataError(f"{path}.{key} is a credential-bearing field")
            _reject_secrets(item, f"{path}.{key}")


def _reject_secret_text(value: str, path: str) -> None:
    decoded = value
    for _ in range(3):
        if _SECRET_TEXT_PATTERN.search(decoded) or _AWS_ACCESS_KEY_VALUE_PATTERN.search(decoded):
            raise SmithsonianMetadataError(f"{path} contains a credential")
        next_value = unquote(decoded)
        if next_value == decoded:
            return
        decoded = next_value
    if _SECRET_TEXT_PATTERN.search(decoded) or _AWS_ACCESS_KEY_VALUE_PATTERN.search(decoded):
        raise SmithsonianMetadataError(f"{path} contains a credential")


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", value).casefold())


def _has_control_or_space(value: str) -> bool:
    return any(
        character.isspace() or unicodedata.category(character) == "Cc" for character in value
    )


def _has_control(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _require_rfc3339(value: str, path: str) -> None:
    if _RFC3339_PATTERN.fullmatch(value) is None:
        raise SmithsonianMetadataError(f"{path} must be strict RFC 3339")
    parse_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError as error:
        raise SmithsonianMetadataError(f"{path} must be strict RFC 3339") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SmithsonianMetadataError(f"{path} must include an RFC 3339 timezone")


def _validate_json_depth(value: object, path: str) -> None:
    stack: list[tuple[object, int]] = [(value, 1)]
    nodes = 0
    string_characters = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise SmithsonianMetadataError(
                f"{path} exceeds the maximum JSON node count of {MAX_JSON_NODES}"
            )
        if depth > MAX_JSON_DEPTH:
            raise SmithsonianMetadataError(
                f"{path} exceeds the maximum JSON depth of {MAX_JSON_DEPTH}"
            )
        if isinstance(current, str):
            string_characters += len(current)
        elif isinstance(current, Mapping):
            string_characters += sum(len(key) for key in current if isinstance(key, str))
        if string_characters > MAX_NORMALIZED_STRING_CHARACTERS:
            raise SmithsonianMetadataError(
                f"{path} exceeds the maximum JSON string-character count of "
                f"{MAX_NORMALIZED_STRING_CHARACTERS}"
            )
        if isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)
        elif isinstance(current, Mapping):
            stack.extend((item, depth + 1) for item in current.values())


def _clone_json(value: object, path: str) -> JsonValue:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise SmithsonianMetadataError(f"{path} contains an unpaired Unicode surrogate")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SmithsonianMetadataError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, list):
        return [_clone_json(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SmithsonianMetadataError(f"{path} contains a non-string key")
            result[key] = _clone_json(item, f"{path}.{key}")
        return result
    raise SmithsonianMetadataError(f"{path} contains a non-JSON value")


def _first_difference(actual: object, expected: object, path: str) -> str:
    if type(actual) is not type(expected):
        return path
    if isinstance(actual, dict) and isinstance(expected, dict):
        if set(actual) != set(expected):
            return path
        for key in sorted(actual):
            difference = _first_difference(actual[key], expected[key], f"{path}.{key}")
            if difference:
                return difference
        return ""
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            return path
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected, strict=True)):
            difference = _first_difference(
                actual_item,
                expected_item,
                f"{path}[{index}]",
            )
            if difference:
                return difference
        return ""
    return "" if actual == expected else path


def _optional_mapping(value: object, path: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    return _require_mapping(value, path)


def _require_mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SmithsonianMetadataError(f"{path} must be an object")
    return value


def _require_list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise SmithsonianMetadataError(f"{path} must be an array")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: tuple[str, ...],
    path: str,
) -> None:
    actual = set(value)
    expected_set = set(expected)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        unexpected = sorted(actual - expected_set)
        raise SmithsonianMetadataError(
            f"{path} has invalid keys; missing={missing!r}, unexpected={unexpected!r}"
        )


def _require_nonempty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SmithsonianMetadataError(f"{path} must be a nonempty string")
    return value


def _require_optional_string(value: object, path: str) -> None:
    if value is not None and not isinstance(value, str):
        raise SmithsonianMetadataError(f"{path} must be a string or null")


def _optional_nonempty_string(value: object, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SmithsonianMetadataError(f"{path} must be a nonempty string or null")
    return value


def _optional_scalar_string(value: object, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SmithsonianMetadataError(f"{path} must be a string or null")
    return value


def _require_positive_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SmithsonianMetadataError(f"{path} must be a positive integer")
    return value
