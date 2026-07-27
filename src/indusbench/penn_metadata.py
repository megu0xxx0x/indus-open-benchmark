"""Fail-closed parsing of the Penn Museum metadata-only CSV snapshot."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any

SCHEMA_VERSION = "0.1.0"
PENN_INSTITUTION_ID = "penn-museum"
PENN_INSTITUTION_NAME = "Penn Museum"
PENN_CSV_URL = (
    "https://collections.penn.museum/collections/assets/data/Penn_Museum_Collections_Data.csv"
)
PENN_LANDING_URL = "https://collections.penn.museum/collections/objects/data.php"
PENN_TERMS_URL = "https://www.penn.museum/about/statements-and-policies/terms-and-conditions"
PENN_LICENSE_ID = "CC-BY-4.0"
PENN_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
PENN_ATTRIBUTION = "Penn Museum"

PENN_CSV_HEADER = (
    "Record URL",
    "identifier",
    "curatorialSection",
    "onDisplay",
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

PRIMARY_SCRIPT_CANDIDATE = "primary_script_candidate"
BROAD_ARCHAEOLOGICAL_CANDIDATE = "broad_archaeological_candidate"
REPLICA_OR_MODERN = "replica_or_modern"
PHYSICAL_STATUS_UNKNOWN = "physical_status_unknown_pending_review"

LIMITATIONS = (
    "metadata_only_no_images",
    "candidate_classification_requires_human_review",
    "physical_status_never_auto_labels_original",
)

_TOP_LEVEL_KEYS = (
    "schema_version",
    "snapshot_id",
    "record_state",
    "source",
    "source_acquisition",
    "csv_header",
    "record_count",
    "candidate_count",
    "candidates",
    "limitations",
)
_SOURCE_KEYS = (
    "institution_id",
    "institution_name",
    "dataset_url",
    "landing_url",
    "terms_url",
    "license_id",
    "license_url",
    "attribution",
    "images_included",
)
_ACQUISITION_KEYS = (
    "url",
    "retrieved_at",
    "bytes",
    "sha256",
    "etag",
    "last_modified",
    "source_last_updated",
)
_CANDIDATE_KEYS = (
    "candidate_id",
    "csv_row_number",
    "classification",
    "matches",
    "record_url",
    "identifier",
    "physical_status",
    "raw_fields",
)
_MATCH_KEYS = ("field", "normalized_token")
_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_TOKEN_SEPARATOR_PATTERN = re.compile(r"[,;|/\r\n]+")
_MODERN_WORD_PATTERN = re.compile(r"\b(?:modern|contemporary)\b")
_MODERN_CENTURY_PATTERN = re.compile(r"\b(?:19th|20th|21st)\s+centur(?:y|ies)\b")
_FOUR_DIGIT_YEAR_PATTERN = re.compile(r"(?<!\d)\d{4}(?!\d)")
_ANCIENT_ERA_PATTERN = re.compile(r"\b(?:b\.?\s*c\.?\s*e?\.?|before\s+(?:the\s+)?common\s+era)\b")
_FORBIDDEN_FIELD_FRAGMENT = re.compile(r"(?:image|media)")

JsonObject = dict[str, Any]


class PennMetadataError(ValueError):
    """Raised when a Penn metadata snapshot violates the closed intake contract."""


def parse_penn_csv_snapshot(
    raw_bytes: bytes,
    *,
    source_url: str,
    retrieved_at: str,
    expected_bytes: int,
    expected_sha256: str,
    etag: str | None,
    last_modified: str | None,
    source_last_updated: str | None,
) -> JsonObject:
    """Parse exact CSV bytes without fetching or following any record URL.

    The caller supplies every acquisition commitment, including an explicit
    ``None`` when an HTTP validator was absent. The byte length and digest are
    checked before any candidate output is returned.
    """

    _validate_acquisition_inputs(
        raw_bytes,
        source_url=source_url,
        retrieved_at=retrieved_at,
        expected_bytes=expected_bytes,
        expected_sha256=expected_sha256,
        etag=etag,
        last_modified=last_modified,
        source_last_updated=source_last_updated,
    )
    record_count, candidates = _parse_candidate_snapshot(raw_bytes)
    snapshot: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": f"penn-museum-csv:{expected_sha256}",
        "record_state": "metadata_only_untranscribed",
        "source": {
            "institution_id": PENN_INSTITUTION_ID,
            "institution_name": PENN_INSTITUTION_NAME,
            "dataset_url": PENN_CSV_URL,
            "landing_url": PENN_LANDING_URL,
            "terms_url": PENN_TERMS_URL,
            "license_id": PENN_LICENSE_ID,
            "license_url": PENN_LICENSE_URL,
            "attribution": PENN_ATTRIBUTION,
            "images_included": False,
        },
        "source_acquisition": {
            "url": source_url,
            "retrieved_at": retrieved_at,
            "bytes": expected_bytes,
            "sha256": expected_sha256,
            "etag": etag,
            "last_modified": last_modified,
            "source_last_updated": source_last_updated,
        },
        "csv_header": list(PENN_CSV_HEADER),
        "record_count": record_count,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "limitations": list(LIMITATIONS),
    }
    validate_penn_metadata_semantics(snapshot)
    return snapshot


def validate_penn_metadata_semantics(
    snapshot: Mapping[str, Any],
    *,
    raw_bytes: bytes | None = None,
) -> None:
    """Enforce closed metadata-only and candidate derivation invariants."""

    _reject_media_fields(snapshot, path="$")
    _require_exact_keys(snapshot, _TOP_LEVEL_KEYS, "$")
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise PennMetadataError("schema_version is not supported")
    if snapshot.get("record_state") != "metadata_only_untranscribed":
        raise PennMetadataError("record_state must remain metadata_only_untranscribed")

    source = _require_mapping(snapshot.get("source"), "$.source")
    _require_exact_keys(source, _SOURCE_KEYS, "$.source")
    expected_source: dict[str, object] = {
        "institution_id": PENN_INSTITUTION_ID,
        "institution_name": PENN_INSTITUTION_NAME,
        "dataset_url": PENN_CSV_URL,
        "landing_url": PENN_LANDING_URL,
        "terms_url": PENN_TERMS_URL,
        "license_id": PENN_LICENSE_ID,
        "license_url": PENN_LICENSE_URL,
        "attribution": PENN_ATTRIBUTION,
        "images_included": False,
    }
    for field, expected in expected_source.items():
        if source.get(field) != expected:
            raise PennMetadataError(f"$.source.{field} must equal the approved Penn constant")

    acquisition = _require_mapping(
        snapshot.get("source_acquisition"),
        "$.source_acquisition",
    )
    _require_exact_keys(acquisition, _ACQUISITION_KEYS, "$.source_acquisition")
    _validate_acquisition_object(acquisition, raw_bytes=raw_bytes)

    expected_snapshot_id = f"penn-museum-csv:{acquisition['sha256']}"
    if snapshot.get("snapshot_id") != expected_snapshot_id:
        raise PennMetadataError("snapshot_id must be derived from source_acquisition.sha256")
    if snapshot.get("csv_header") != list(PENN_CSV_HEADER):
        raise PennMetadataError("csv_header must preserve the exact approved 32-column order")
    if snapshot.get("limitations") != list(LIMITATIONS):
        raise PennMetadataError("limitations must preserve the closed metadata-only warnings")

    record_count = _require_nonnegative_integer(snapshot.get("record_count"), "$.record_count")
    candidate_count = _require_nonnegative_integer(
        snapshot.get("candidate_count"),
        "$.candidate_count",
    )
    candidates = _require_sequence(snapshot.get("candidates"), "$.candidates")
    if candidate_count != len(candidates):
        raise PennMetadataError("$.candidate_count does not equal the candidate array length")
    if candidate_count > record_count:
        raise PennMetadataError("$.candidate_count cannot exceed $.record_count")

    seen_record_urls: set[str] = set()
    seen_identifiers: set[str] = set()
    previous_row_number = 1
    for index, value in enumerate(candidates):
        path = f"$.candidates[{index}]"
        candidate = _require_mapping(value, path)
        _require_exact_keys(candidate, _CANDIDATE_KEYS, path)
        row_number = _require_positive_integer(
            candidate.get("csv_row_number"),
            f"{path}.csv_row_number",
        )
        if row_number <= previous_row_number:
            raise PennMetadataError(f"{path}.csv_row_number must be strictly increasing")
        if row_number > record_count + 1:
            raise PennMetadataError(f"{path}.csv_row_number exceeds the snapshot record count")
        previous_row_number = row_number

        raw_fields = _require_mapping(candidate.get("raw_fields"), f"{path}.raw_fields")
        _require_exact_keys(raw_fields, PENN_CSV_HEADER, f"{path}.raw_fields")
        for field in PENN_CSV_HEADER:
            if not isinstance(raw_fields.get(field), str):
                raise PennMetadataError(f"{path}.raw_fields[{field!r}] must be a raw string")

        record_url = _require_identity(
            candidate.get("record_url"),
            f"{path}.record_url",
        )
        identifier = _require_identity(
            candidate.get("identifier"),
            f"{path}.identifier",
        )
        if record_url != raw_fields["Record URL"]:
            raise PennMetadataError(f"{path}.record_url must equal its raw field")
        if identifier != raw_fields["identifier"]:
            raise PennMetadataError(f"{path}.identifier must equal its raw field")
        if record_url in seen_record_urls:
            raise PennMetadataError(f"duplicate candidate Record URL: {record_url!r}")
        if identifier in seen_identifiers:
            raise PennMetadataError(f"duplicate candidate identifier: {identifier!r}")
        seen_record_urls.add(record_url)
        seen_identifiers.add(identifier)

        expected_matches = _candidate_matches(raw_fields)
        if not expected_matches:
            raise PennMetadataError(f"{path} is not a Penn script or archaeological candidate")
        matches = _require_sequence(candidate.get("matches"), f"{path}.matches")
        for match_index, match in enumerate(matches):
            _require_exact_keys(
                _require_mapping(match, f"{path}.matches[{match_index}]"),
                _MATCH_KEYS,
                f"{path}.matches[{match_index}]",
            )
        if matches != expected_matches:
            raise PennMetadataError(f"{path}.matches are not exactly derived from raw fields")

        expected_classification = _candidate_classification(raw_fields)
        if candidate.get("classification") != expected_classification:
            raise PennMetadataError(f"{path}.classification is not derived from raw fields")
        expected_physical_status = _physical_status(raw_fields)
        if candidate.get("physical_status") != expected_physical_status:
            raise PennMetadataError(f"{path}.physical_status is not derived from raw fields")
        expected_candidate_id = _candidate_id(record_url, identifier)
        if candidate.get("candidate_id") != expected_candidate_id:
            raise PennMetadataError(f"{path}.candidate_id is not derived from record identity")

    if raw_bytes is not None:
        expected_record_count, expected_candidates = _parse_candidate_snapshot(raw_bytes)
        if record_count != expected_record_count:
            raise PennMetadataError("$.record_count does not match the committed CSV bytes")
        if candidates != expected_candidates:
            raise PennMetadataError("$.candidates do not exactly match the committed CSV bytes")


def _validate_acquisition_inputs(
    raw_bytes: bytes,
    *,
    source_url: str,
    retrieved_at: str,
    expected_bytes: int,
    expected_sha256: str,
    etag: str | None,
    last_modified: str | None,
    source_last_updated: str | None,
) -> None:
    if not isinstance(raw_bytes, bytes):
        raise PennMetadataError("raw_bytes must be exact bytes")
    if source_url != PENN_CSV_URL:
        raise PennMetadataError("source_url must equal the approved direct Penn CSV URL")
    _require_canonical_rfc3339(retrieved_at, "retrieved_at")
    actual_bytes = len(raw_bytes)
    if (
        isinstance(expected_bytes, bool)
        or not isinstance(expected_bytes, int)
        or expected_bytes < 1
    ):
        raise PennMetadataError("expected_bytes must be a positive integer")
    if expected_bytes != actual_bytes:
        raise PennMetadataError(
            f"source byte commitment mismatch: expected {expected_bytes}, received {actual_bytes}"
        )
    actual_sha256 = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
    if not isinstance(expected_sha256, str) or not _CHECKSUM_PATTERN.fullmatch(expected_sha256):
        raise PennMetadataError("expected_sha256 must be a lowercase SHA-256 commitment")
    if expected_sha256 != actual_sha256:
        raise PennMetadataError("source SHA-256 commitment does not match raw_bytes")
    _validate_optional_http_validator(etag, "etag")
    _validate_optional_http_validator(last_modified, "last_modified")
    _validate_optional_source_date(source_last_updated)


def _validate_acquisition_object(
    acquisition: Mapping[str, Any],
    *,
    raw_bytes: bytes | None,
) -> None:
    if acquisition.get("url") != PENN_CSV_URL:
        raise PennMetadataError("$.source_acquisition.url is not the approved direct CSV URL")
    retrieved_at = acquisition.get("retrieved_at")
    if not isinstance(retrieved_at, str):
        raise PennMetadataError("$.source_acquisition.retrieved_at must be a string")
    _require_canonical_rfc3339(retrieved_at, "$.source_acquisition.retrieved_at")
    byte_count = _require_positive_integer(
        acquisition.get("bytes"),
        "$.source_acquisition.bytes",
    )
    checksum = acquisition.get("sha256")
    if not isinstance(checksum, str) or not _CHECKSUM_PATTERN.fullmatch(checksum):
        raise PennMetadataError("$.source_acquisition.sha256 must be lowercase SHA-256")
    etag = acquisition.get("etag")
    last_modified = acquisition.get("last_modified")
    source_last_updated = acquisition.get("source_last_updated")
    if etag is not None and not isinstance(etag, str):
        raise PennMetadataError("$.source_acquisition.etag must be a string or null")
    if last_modified is not None and not isinstance(last_modified, str):
        raise PennMetadataError("$.source_acquisition.last_modified must be a string or null")
    if source_last_updated is not None and not isinstance(source_last_updated, str):
        raise PennMetadataError("$.source_acquisition.source_last_updated must be a string or null")
    _validate_optional_http_validator(etag, "$.source_acquisition.etag")
    _validate_optional_http_validator(
        last_modified,
        "$.source_acquisition.last_modified",
    )
    _validate_optional_source_date(source_last_updated)
    if raw_bytes is not None:
        if not isinstance(raw_bytes, bytes):
            raise PennMetadataError("raw_bytes must be exact bytes")
        if len(raw_bytes) != byte_count:
            raise PennMetadataError("$.source_acquisition.bytes does not match raw_bytes")
        actual_sha256 = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
        if checksum != actual_sha256:
            raise PennMetadataError("$.source_acquisition.sha256 does not match raw_bytes")


def _parse_candidate_snapshot(
    raw_bytes: bytes,
) -> tuple[int, list[JsonObject]]:
    if not isinstance(raw_bytes, bytes):
        raise PennMetadataError("raw_bytes must be exact bytes")
    if b"\x00" in raw_bytes:
        raise PennMetadataError("Penn CSV contains a forbidden NUL byte")
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PennMetadataError(f"Penn CSV is not strict UTF-8 at byte {error.start}") from error
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration as error:
        raise PennMetadataError("Penn CSV is empty") from error
    except csv.Error as error:
        raise PennMetadataError(f"malformed Penn CSV header: {error}") from error
    if len(set(header)) != len(header):
        raise PennMetadataError("Penn CSV header contains duplicate columns")
    if tuple(header) != PENN_CSV_HEADER:
        raise PennMetadataError("Penn CSV header must match the exact approved 32-column order")

    record_count = 0
    candidates: list[JsonObject] = []
    seen_record_urls: set[str] = set()
    seen_identifiers: set[str] = set()
    try:
        for csv_row_number, values in enumerate(reader, start=2):
            record_count += 1
            if len(values) != len(PENN_CSV_HEADER):
                raise PennMetadataError(
                    f"Penn CSV row {csv_row_number} has {len(values)} columns; "
                    f"expected {len(PENN_CSV_HEADER)}"
                )
            raw_fields: dict[str, str] = dict(zip(PENN_CSV_HEADER, values, strict=True))
            _require_identity(raw_fields["Record URL"], f"Penn CSV row {csv_row_number} Record URL")
            _require_identity(raw_fields["identifier"], f"Penn CSV row {csv_row_number} identifier")
            classification = _candidate_classification(raw_fields)
            if classification is None:
                continue
            record_url = raw_fields["Record URL"]
            identifier = raw_fields["identifier"]
            if record_url in seen_record_urls:
                raise PennMetadataError(f"duplicate candidate Record URL: {record_url!r}")
            if identifier in seen_identifiers:
                raise PennMetadataError(f"duplicate candidate identifier: {identifier!r}")
            seen_record_urls.add(record_url)
            seen_identifiers.add(identifier)
            candidates.append(
                {
                    "candidate_id": _candidate_id(record_url, identifier),
                    "csv_row_number": csv_row_number,
                    "classification": classification,
                    "matches": _candidate_matches(raw_fields),
                    "record_url": record_url,
                    "identifier": identifier,
                    "physical_status": _physical_status(raw_fields),
                    "raw_fields": raw_fields,
                }
            )
    except csv.Error as error:
        raise PennMetadataError(
            f"malformed Penn CSV near record {record_count + 2}: {error}"
        ) from error
    return record_count, candidates


def _candidate_classification(row: Mapping[str, str]) -> str | None:
    if "indus script" in _normalized_tokens(row["inscriptionMarkLanguage"]):
        return PRIMARY_SCRIPT_CANDIDATE
    if "harappan" in _normalized_tokens(row["culture"]):
        return BROAD_ARCHAEOLOGICAL_CANDIDATE
    return None


def _candidate_matches(row: Mapping[str, str]) -> list[JsonObject]:
    matches: list[JsonObject] = []
    if "indus script" in _normalized_tokens(row["inscriptionMarkLanguage"]):
        matches.append(
            {
                "field": "inscriptionMarkLanguage",
                "normalized_token": "indus script",
            }
        )
    if "harappan" in _normalized_tokens(row["culture"]):
        matches.append({"field": "culture", "normalized_token": "harappan"})
    return matches


def _physical_status(row: Mapping[str, str]) -> str:
    if {"plaster", "plaster of paris"} & _normalized_tokens(row["material"]):
        return REPLICA_OR_MODERN
    if re.search(
        r"\b(?:cast|reproduction)\b",
        _normalize_token(row["objectName"]),
    ):
        return REPLICA_OR_MODERN
    if re.search(r"\bcast\b", _normalize_token(row["technique"])):
        return REPLICA_OR_MODERN
    if _is_clearly_modern_date(row["dateMade"]):
        return REPLICA_OR_MODERN
    return PHYSICAL_STATUS_UNKNOWN


def _is_clearly_modern_date(value: str) -> bool:
    normalized = _normalize_token(value)
    if not normalized:
        return False
    if _MODERN_WORD_PATTERN.search(normalized):
        return True
    if _ANCIENT_ERA_PATTERN.search(normalized):
        return False
    if _MODERN_CENTURY_PATTERN.search(normalized):
        return True
    years = [int(match.group()) for match in _FOUR_DIGIT_YEAR_PATTERN.finditer(normalized)]
    return bool(years) and all(1800 <= year <= 2100 for year in years)


def _normalized_tokens(value: str) -> set[str]:
    return {
        normalized
        for part in _TOKEN_SEPARATOR_PATTERN.split(value)
        if (normalized := _normalize_token(part))
    }


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _candidate_id(record_url: str, identifier: str) -> str:
    digest = hashlib.sha256(f"{record_url}\0{identifier}".encode()).hexdigest()
    return f"penn-museum-candidate:sha256:{digest}"


def _require_mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PennMetadataError(f"{path} must be an object")
    return value


def _require_sequence(value: object, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PennMetadataError(f"{path} must be an array")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: Sequence[str],
    path: str,
) -> None:
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        unexpected = sorted(actual_set - expected_set)
        raise PennMetadataError(f"{path} is not closed; missing={missing}, unexpected={unexpected}")


def _require_identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PennMetadataError(f"{label} must be a non-empty raw string")
    if value != value.strip():
        raise PennMetadataError(f"{label} must not contain surrounding whitespace")
    return value


def _require_nonnegative_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PennMetadataError(f"{path} must be a non-negative integer")
    return value


def _require_positive_integer(value: object, path: str) -> int:
    result = _require_nonnegative_integer(value, path)
    if result < 1:
        raise PennMetadataError(f"{path} must be a positive integer")
    return result


def _require_canonical_rfc3339(value: object, label: str) -> None:
    if not isinstance(value, str) or not _RFC3339_PATTERN.fullmatch(value):
        raise PennMetadataError(f"{label} must be a canonical RFC 3339 date-time")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise PennMetadataError(f"{label} must be an RFC 3339 date-time") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PennMetadataError(f"{label} must include a UTC offset")
    canonical = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise PennMetadataError(f"{label} must use canonical UTC RFC 3339 form")


def _validate_optional_http_validator(value: str | None, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value or value != value.strip():
        raise PennMetadataError(f"{label} must be a non-empty unpadded string or null")
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise PennMetadataError(f"{label} contains forbidden control characters")


def _validate_optional_source_date(value: str | None) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise PennMetadataError("source_last_updated must be an ISO date or null")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise PennMetadataError("source_last_updated must be an ISO date or null") from error
    if parsed.isoformat() != value:
        raise PennMetadataError("source_last_updated must use canonical YYYY-MM-DD form")


def _reject_media_fields(value: object, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise PennMetadataError(f"{path} contains a non-string field name")
            normalized_key = re.sub(r"[^a-z]", "", key.casefold())
            if key != "images_included" and _FORBIDDEN_FIELD_FRAGMENT.search(normalized_key):
                raise PennMetadataError(f"{path}.{key} is a forbidden media/image field")
            _reject_media_fields(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_media_fields(item, path=f"{path}[{index}]")
