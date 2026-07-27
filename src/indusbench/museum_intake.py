"""Rights-gated intake of untranscribed museum records and image files."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA_VERSION = "0.1.0"
MET_SOURCE_ID = "met-open-access-indus"
CLEVELAND_SOURCE_ID = "cleveland-open-access-indus"
MET_API_ROOT = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
CLEVELAND_API_ROOT = "https://openaccess-api.clevelandart.org/api/artworks/"
MET_POLICY_URI = "https://www.metmuseum.org/hubs/open-access"
CLEVELAND_POLICY_URI = "https://www.clevelandart.org/open-access"
CC0_URI = "https://creativecommons.org/publicdomain/zero/1.0/"
DEFAULT_MAX_JSON_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_MEDIA_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_MEDIA_COUNT = 1_000
DEFAULT_MAX_TOTAL_MEDIA_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_TOTAL_JSON_BYTES = 128 * 1024 * 1024
USER_AGENT = "indus-open-benchmark/0.1 museum-intake"

_ACCESSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SAFE_COMPONENT_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
_PROVIDER_HOSTS = {
    MET_SOURCE_ID: {
        "api": {"collectionapi.metmuseum.org"},
        "record": {"www.metmuseum.org"},
        "media": {"images.metmuseum.org"},
    },
    CLEVELAND_SOURCE_ID: {
        "api": {"openaccess-api.clevelandart.org"},
        "record": {"clevelandart.org", "www.clevelandart.org"},
        "media": {"openaccess-cdn.clevelandart.org"},
    },
}

JsonObject = dict[str, Any]
UrlOpener = Callable[..., Any]


class MuseumIntakeError(ValueError):
    """Raised when a remote record or file fails the private-intake contract."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> Request | None:
        _require_https_url(new_url)
        raise MuseumIntakeError(
            f"HTTP redirects are not allowed: {request.full_url!r} -> {new_url!r}"
        )


_SECURE_OPENER = build_opener(_NoRedirectHandler())


def _secure_urlopen(request: Request, *, timeout: float) -> Any:
    return _SECURE_OPENER.open(request, timeout=timeout)


@dataclass(frozen=True)
class JsonDocument:
    """An exact HTTP JSON response plus the parsed object used for intake."""

    url: str
    status: int
    content_type: str
    headers: dict[str, str]
    raw_bytes: bytes
    value: JsonObject

    @property
    def sha256(self) -> str:
        return f"sha256:{hashlib.sha256(self.raw_bytes).hexdigest()}"


@dataclass(frozen=True)
class PolicyEvidenceSpec:
    """One exact official policy or API document required by a provider gate."""

    evidence_id: str
    source_id: str
    uri: str
    raw_relative_path: str
    allowed_content_types: frozenset[str]
    required_markers: tuple[bytes, ...]


@dataclass(frozen=True)
class PolicyDocument:
    """Exact bounded bytes fetched from an official rights-evidence locator."""

    evidence_id: str
    source_id: str
    url: str
    status: int
    content_type: str
    raw_relative_path: str
    raw_bytes: bytes

    @property
    def sha256(self) -> str:
        return f"sha256:{hashlib.sha256(self.raw_bytes).hexdigest()}"


POLICY_EVIDENCE_SPECS = (
    PolicyEvidenceSpec(
        evidence_id="met-openaccess-readme-e901de1",
        source_id=MET_SOURCE_ID,
        uri=(
            "https://raw.githubusercontent.com/metmuseum/openaccess/"
            "e901de145e60258542243571098245826a01fe47/README.md"
        ),
        raw_relative_path="raw/policies/met-openaccess-readme-e901de1.md",
        allowed_content_types=frozenset({"text/plain"}),
        required_markers=(
            b"creative commons zero",
            b"companion artworks",
            b"images are not included",
        ),
    ),
    PolicyEvidenceSpec(
        evidence_id="met-collection-api-docs",
        source_id=MET_SOURCE_ID,
        uri="https://metmuseum.github.io/",
        raw_relative_path="raw/policies/met-collection-api-docs.html",
        allowed_content_types=frozenset({"text/html"}),
        required_markers=(
            b"high resolution images",
            b"public domain",
            b"ispublicdomain",
        ),
    ),
    PolicyEvidenceSpec(
        evidence_id="cleveland-open-access-policy",
        source_id=CLEVELAND_SOURCE_ID,
        uri="https://www.clevelandart.org/open-access",
        raw_relative_path="raw/policies/cleveland-open-access-policy.html",
        allowed_content_types=frozenset({"text/html"}),
        required_markers=(
            b"creative commons",
            b"cc0",
            b"open access",
        ),
    ),
    PolicyEvidenceSpec(
        evidence_id="cleveland-open-access-api-docs",
        source_id=CLEVELAND_SOURCE_ID,
        uri="https://openaccess-api.clevelandart.org/",
        raw_relative_path="raw/policies/cleveland-open-access-api-docs.html",
        allowed_content_types=frozenset({"text/html"}),
        required_markers=(
            b"share_license_status",
            b"only artworks with the cc0",
            b"corresponding",
        ),
    ),
)
_POLICY_SPEC_BY_ID = {
    specification.evidence_id: specification for specification in POLICY_EVIDENCE_SPECS
}


def fetch_policy_documents(
    source_ids: Sequence[str],
    *,
    timeout: float = 30.0,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_JSON_BYTES,
    opener: UrlOpener = _secure_urlopen,
) -> list[PolicyDocument]:
    """Fetch the exact official policy documents required by selected providers."""

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_bytes < 1 or max_total_bytes < 1:
        raise ValueError("policy byte limits must be positive")
    requested_sources = tuple(dict.fromkeys(source_ids))
    unsupported = set(requested_sources) - set(_PROVIDER_HOSTS)
    if unsupported:
        raise MuseumIntakeError(f"unsupported policy evidence sources: {sorted(unsupported)}")
    specifications = [
        specification
        for specification in POLICY_EVIDENCE_SPECS
        if specification.source_id in requested_sources
    ]
    documents: list[PolicyDocument] = []
    total_bytes = 0
    for specification in specifications:
        request = Request(
            specification.uri,
            headers={"Accept": "text/html,text/plain", "User-Agent": USER_AGENT},
        )
        with opener(request, timeout=timeout) as response:
            status = _response_status(response)
            if status != 200:
                raise MuseumIntakeError(
                    f"expected HTTP 200 from {specification.uri}, received {status}"
                )
            _require_no_redirect(
                specification.uri,
                _response_url(response, specification.uri),
            )
            headers = _response_headers(response)
            content_type = _normalized_content_type(headers.get("content-type"))
            if content_type not in specification.allowed_content_types:
                raise MuseumIntakeError(
                    f"unexpected policy content type from {specification.uri}: "
                    f"{content_type or 'unknown'}"
                )
            header_length = _optional_content_length(
                headers.get("content-length"),
                specification.uri,
            )
            remaining_total = max_total_bytes - total_bytes
            if remaining_total < 1:
                raise MuseumIntakeError("policy evidence exceeds aggregate byte limit")
            effective_limit = min(max_bytes, remaining_total)
            if header_length is not None and header_length > effective_limit:
                raise MuseumIntakeError(f"policy content-length exceeds limit: {specification.uri}")
            raw_bytes = _read_bounded(
                response,
                max_bytes=effective_limit,
                label=specification.uri,
            )
        if header_length is not None and header_length != len(raw_bytes):
            raise MuseumIntakeError(
                f"HTTP content-length mismatch for {specification.uri}: "
                f"{header_length} != {len(raw_bytes)}"
            )
        _validate_policy_markers(specification, raw_bytes)
        total_bytes += len(raw_bytes)
        documents.append(
            PolicyDocument(
                evidence_id=specification.evidence_id,
                source_id=specification.source_id,
                url=specification.uri,
                status=status,
                content_type=content_type,
                raw_relative_path=specification.raw_relative_path,
                raw_bytes=raw_bytes,
            )
        )
    return documents


def policy_manifest_entry(
    document: PolicyDocument,
    *,
    retrieved_at: str,
) -> JsonObject:
    """Create the closed manifest row for one exact policy response."""

    return {
        "evidence_id": document.evidence_id,
        "source_id": document.source_id,
        "uri": document.url,
        "retrieved_at": retrieved_at,
        "http_status": document.status,
        "response_content_type": document.content_type,
        "response_sha256": document.sha256,
        "response_bytes": len(document.raw_bytes),
        "raw_response_local_relative_path": document.raw_relative_path,
    }


def write_policy_document(
    document: PolicyDocument,
    *,
    root: str | Path,
) -> Path:
    """Write one exact policy response without replacing an existing file."""

    specification = _POLICY_SPEC_BY_ID.get(document.evidence_id)
    if specification is None:
        raise MuseumIntakeError(f"unknown policy evidence_id: {document.evidence_id!r}")
    _validate_policy_document_identity(document, specification)
    _validate_policy_markers(specification, document.raw_bytes)
    destination = _resolved_bundle_path(root, document.raw_relative_path)
    _atomic_write_bytes(destination, document.raw_bytes, force=False)
    return destination


def verify_policy_evidence(
    entries: object,
    *,
    source_ids: Sequence[str],
    root: str | Path,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_JSON_BYTES,
) -> list[JsonObject]:
    """Verify the closed policy manifest and every stored policy response."""

    if max_bytes < 1 or max_total_bytes < 1:
        raise ValueError("policy verification byte limits must be positive")
    if not isinstance(entries, list):
        raise MuseumIntakeError("manifest.policy_evidence must be a list")
    requested_sources = tuple(dict.fromkeys(source_ids))
    unsupported = set(requested_sources) - set(_PROVIDER_HOSTS)
    if unsupported:
        raise MuseumIntakeError(f"unsupported policy evidence sources: {sorted(unsupported)}")
    expected_specifications = [
        specification
        for specification in POLICY_EVIDENCE_SPECS
        if specification.source_id in requested_sources
    ]
    if len(entries) != len(expected_specifications):
        raise MuseumIntakeError("manifest policy evidence count does not match selected providers")
    entry_by_id: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise MuseumIntakeError("manifest policy evidence row must be an object")
        evidence_id = entry.get("evidence_id")
        if not isinstance(evidence_id, str) or evidence_id in entry_by_id:
            raise MuseumIntakeError("manifest policy evidence IDs must be unique strings")
        entry_by_id[evidence_id] = entry

    reports: list[JsonObject] = []
    total_bytes = 0
    for specification in expected_specifications:
        entry = entry_by_id.get(specification.evidence_id)
        if entry is None:
            raise MuseumIntakeError(f"manifest lacks policy evidence: {specification.evidence_id}")
        _validate_policy_manifest_entry(entry, specification)
        remaining_total = max_total_bytes - total_bytes
        if remaining_total < 1:
            raise MuseumIntakeError("stored policy evidence exceeds aggregate limit")
        path = _resolved_bundle_path(
            root,
            specification.raw_relative_path,
        )
        try:
            with _open_regular_binary(path) as handle:
                raw_bytes = _read_bounded(
                    handle,
                    max_bytes=min(max_bytes, remaining_total),
                    label=str(path),
                )
        except FileNotFoundError as error:
            raise MuseumIntakeError(f"stored policy evidence is missing: {path}") from error
        _validate_policy_markers(specification, raw_bytes)
        actual_hash = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
        if actual_hash != entry.get("response_sha256"):
            raise MuseumIntakeError(
                f"stored policy evidence hash mismatch: {specification.evidence_id}"
            )
        if len(raw_bytes) != entry.get("response_bytes"):
            raise MuseumIntakeError(
                f"stored policy evidence byte mismatch: {specification.evidence_id}"
            )
        total_bytes += len(raw_bytes)
        reports.append(
            {
                "evidence_id": specification.evidence_id,
                "source_id": specification.source_id,
                "response_sha256": actual_hash,
                "response_bytes": len(raw_bytes),
                "verified": True,
            }
        )
    return reports


def fetch_json_document(
    url: str,
    *,
    timeout: float = 30.0,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
    opener: UrlOpener = _secure_urlopen,
) -> JsonDocument:
    """Fetch one bounded HTTPS JSON object while retaining its exact response bytes."""

    _require_https_url(url)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")

    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with opener(request, timeout=timeout) as response:
        status = _response_status(response)
        if status != 200:
            raise MuseumIntakeError(f"expected HTTP 200 from {url}, received {status}")
        _require_no_redirect(url, _response_url(response, url))
        headers = _response_headers(response)
        content_type = _normalized_content_type(headers.get("content-type"))
        if content_type not in {"application/json", "application/ld+json"}:
            raise MuseumIntakeError(
                f"expected a JSON content type from {url}, received {content_type or 'unknown'}"
            )
        raw_bytes = _read_bounded(response, max_bytes=max_bytes, label=url)

    try:
        value = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MuseumIntakeError(f"invalid UTF-8 JSON from {url}: {error}") from error
    if not isinstance(value, dict):
        raise MuseumIntakeError(f"expected a JSON object from {url}")
    return JsonDocument(
        url=url,
        status=status,
        content_type=content_type,
        headers=headers,
        raw_bytes=raw_bytes,
        value=value,
    )


def fetch_met_intake(
    object_id: int,
    *,
    retrieved_at: str,
    timeout: float = 30.0,
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES,
    opener: UrlOpener = _secure_urlopen,
) -> tuple[JsonObject, JsonDocument]:
    """Fetch and validate one Met Open Access object record."""

    if isinstance(object_id, bool) or object_id < 1:
        raise ValueError("Met object_id must be a positive integer")
    document = fetch_json_document(
        f"{MET_API_ROOT}/{object_id}",
        timeout=timeout,
        max_bytes=max_json_bytes,
        opener=opener,
    )
    return (
        build_met_intake(
            document,
            expected_object_id=object_id,
            retrieved_at=retrieved_at,
        ),
        document,
    )


def fetch_cleveland_intake(
    accession_number: str,
    *,
    retrieved_at: str,
    derivatives: Sequence[str] = ("print", "full"),
    timeout: float = 30.0,
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES,
    opener: UrlOpener = _secure_urlopen,
) -> tuple[JsonObject, JsonDocument]:
    """Fetch and validate one Cleveland Open Access accession record."""

    accession = _validated_accession(accession_number)
    api_url = f"{CLEVELAND_API_ROOT}?{urlencode({'accession_number': accession})}"
    document = fetch_json_document(
        api_url,
        timeout=timeout,
        max_bytes=max_json_bytes,
        opener=opener,
    )
    return (
        build_cleveland_intake(
            document,
            expected_accession_number=accession,
            retrieved_at=retrieved_at,
            derivatives=derivatives,
        ),
        document,
    )


def build_met_intake(
    document: JsonDocument,
    *,
    expected_object_id: int,
    retrieved_at: str,
) -> JsonObject:
    """Build an untranscribed intake row from an exact Met API response."""

    record = document.value
    object_id = record.get("objectID")
    if object_id != expected_object_id:
        raise MuseumIntakeError(
            f"Met response objectID {object_id!r} did not match requested {expected_object_id}"
        )
    if record.get("isPublicDomain") is not True:
        raise MuseumIntakeError(
            f"Met object {expected_object_id} is not currently marked isPublicDomain=true"
        )

    accession = _require_string(record, "accessionNumber", "Met record")
    title = _require_string(record, "title", "Met record")
    record_uri = _require_https_string(record, "objectURL", "Met record")
    primary_uri = _require_https_string(record, "primaryImage", "Met record")
    additional = record.get("additionalImages", [])
    if not isinstance(additional, list):
        raise MuseumIntakeError("Met additionalImages must be a list")

    media = [
        _media_row(
            media_id=f"met:{object_id}:primary:original",
            provider_media_id="primaryImage",
            view_role="provider_primary",
            provider_view_index=0,
            provider_derivative="met_original",
            source_uri=primary_uri,
        )
    ]
    for index, value in enumerate(additional):
        if not isinstance(value, str):
            raise MuseumIntakeError(f"Met additionalImages[{index}] must be a URL string")
        _require_https_url(value)
        media.append(
            _media_row(
                media_id=f"met:{object_id}:alt{index}:original",
                provider_media_id=f"additionalImages[{index}]",
                view_role="provider_alternate_unknown",
                provider_view_index=index + 1,
                provider_derivative="met_original",
                source_uri=value,
            )
        )

    raw_path = f"raw/met/{object_id}/api-response.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "intake_id": f"museum:met:{object_id}",
        "record_state": "untranscribed",
        "institution": {
            "institution_id": "met",
            "name": "The Metropolitan Museum of Art",
        },
        "source_id": MET_SOURCE_ID,
        "official_record": {
            "object_id": str(object_id),
            "accession_number": accession,
            "title_as_catalogued": title,
            "record_uri": record_uri,
        },
        "retrieval": {
            "api_endpoint": document.url,
            "retrieved_at": retrieved_at,
            "http_status": document.status,
            "response_content_type": document.content_type,
            "response_sha256": document.sha256,
            "raw_response_local_relative_path": raw_path,
        },
        "item_rights": _item_rights(
            rights_holder="The Metropolitan Museum of Art",
            api_field="isPublicDomain",
            observed_value=True,
            item_record_uri=record_uri,
            policy_uri=MET_POLICY_URI,
            verified_at=retrieved_at,
            response_sha256=document.sha256,
            statement=(
                "The official item response currently marks isPublicDomain=true; "
                "the Met Open Access policy applies CC0 to eligible public-domain images."
            ),
        ),
        "media": media,
        "catalog_crosswalk": {
            "status": "unresolved",
            "notes": (
                "No identity with a CISI, Mahadevan, Wells/ICIT, or excavation record is asserted."
            ),
        },
        "limitations": [
            "Catalog title, culture, date, material, and dimensions remain museum assertions.",
            "The official record supplies no secure excavation findspot or stratigraphic context.",
            (
                "Provider primary/additional ordering does not identify a physical "
                "front, reverse, seal, or impression."
            ),
            (
                "No sign segmentation, transcription, reading direction, language, "
                "or translation is present."
            ),
        ],
    }


def build_cleveland_intake(
    document: JsonDocument,
    *,
    expected_accession_number: str,
    retrieved_at: str,
    derivatives: Sequence[str] = ("print", "full"),
) -> JsonObject:
    """Build an untranscribed intake row from a Cleveland API search response."""

    selected_derivatives = tuple(dict.fromkeys(derivatives))
    if not selected_derivatives:
        raise ValueError("at least one Cleveland derivative must be selected")
    unsupported = set(selected_derivatives) - {"print", "full"}
    if unsupported:
        raise ValueError(f"unsupported Cleveland derivatives: {sorted(unsupported)}")

    data = document.value.get("data")
    if not isinstance(data, list):
        raise MuseumIntakeError("Cleveland response data must be a list")
    matches = [
        item
        for item in data
        if isinstance(item, Mapping) and item.get("accession_number") == expected_accession_number
    ]
    if len(matches) != 1:
        raise MuseumIntakeError(
            f"expected one exact Cleveland accession {expected_accession_number}, "
            f"received {len(matches)}"
        )
    record = matches[0]
    if record.get("share_license_status") != "CC0":
        raise MuseumIntakeError(
            f"Cleveland accession {expected_accession_number} is not currently marked CC0"
        )

    provider_id = record.get("id")
    if isinstance(provider_id, bool) or not isinstance(provider_id, int) or provider_id < 1:
        raise MuseumIntakeError("Cleveland record id must be a positive integer")
    title = _require_string(record, "title", "Cleveland record")
    record_uri = _require_https_string(record, "url", "Cleveland record")
    media: list[JsonObject] = []

    primary = record.get("images")
    if not isinstance(primary, Mapping):
        raise MuseumIntakeError("Cleveland images must be an object")
    media.extend(
        _cleveland_media_rows(
            primary,
            accession_number=expected_accession_number,
            provider_view_index=0,
            view_slug="primary",
            view_role="provider_primary",
            derivatives=selected_derivatives,
        )
    )

    alternate_images = record.get("alternate_images", [])
    if not isinstance(alternate_images, list):
        raise MuseumIntakeError("Cleveland alternate_images must be a list")
    for index, alternate in enumerate(alternate_images):
        if not isinstance(alternate, Mapping):
            raise MuseumIntakeError(f"Cleveland alternate_images[{index}] must be an object")
        media.extend(
            _cleveland_media_rows(
                alternate,
                accession_number=expected_accession_number,
                provider_view_index=index + 1,
                view_slug=f"alt{index}",
                view_role="provider_alternate_unknown",
                derivatives=selected_derivatives,
            )
        )

    raw_path = f"raw/cleveland/{expected_accession_number}/api-response.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "intake_id": f"museum:cleveland:{expected_accession_number}",
        "record_state": "untranscribed",
        "institution": {
            "institution_id": "cleveland",
            "name": "Cleveland Museum of Art",
        },
        "source_id": CLEVELAND_SOURCE_ID,
        "official_record": {
            "object_id": str(provider_id),
            "accession_number": expected_accession_number,
            "title_as_catalogued": title,
            "record_uri": record_uri,
        },
        "retrieval": {
            "api_endpoint": document.url,
            "retrieved_at": retrieved_at,
            "http_status": document.status,
            "response_content_type": document.content_type,
            "response_sha256": document.sha256,
            "raw_response_local_relative_path": raw_path,
        },
        "item_rights": _item_rights(
            rights_holder="Cleveland Museum of Art",
            api_field="share_license_status",
            observed_value="CC0",
            item_record_uri=record_uri,
            policy_uri=CLEVELAND_POLICY_URI,
            verified_at=retrieved_at,
            response_sha256=document.sha256,
            statement=(
                "The official item response currently reports share_license_status=CC0; "
                "only media enumerated by that response enter this intake."
            ),
        ),
        "media": media,
        "catalog_crosswalk": {
            "status": "unresolved",
            "notes": (
                "No identity with a CISI, Mahadevan, Wells/ICIT, or excavation record is asserted."
            ),
        },
        "limitations": [
            "Catalog title, culture, date, material, and dimensions remain museum assertions.",
            "The official record supplies no secure excavation findspot or stratigraphic context.",
            (
                "Provider primary/alternate ordering does not identify a physical "
                "front, reverse, seal, or impression."
            ),
            (
                "API-declared byte sizes are provenance metadata; downloaded bytes "
                "and SHA-256 are authoritative for file integrity."
            ),
            (
                "No sign segmentation, transcription, reading direction, language, "
                "or translation is present."
            ),
        ],
    }


def write_raw_response(
    document: JsonDocument,
    *,
    root: str | Path,
    relative_path: str,
    force: bool = False,
) -> Path:
    """Write the exact API response bytes beneath a validated private bundle root."""

    destination = _resolved_bundle_path(root, relative_path)
    _atomic_write_bytes(destination, document.raw_bytes, force=force)
    return destination


def write_intake_raw_response(
    record: Mapping[str, Any],
    document: JsonDocument,
    *,
    root: str | Path,
    force: bool = False,
) -> Path:
    """Verify and store the exact API response named by an intake record."""

    validate_intake_semantics(record, document=document)
    retrieval = record.get("retrieval")
    if not isinstance(retrieval, Mapping):
        raise MuseumIntakeError("intake retrieval must be an object")
    relative_path = retrieval.get("raw_response_local_relative_path")
    if not isinstance(relative_path, str):
        raise MuseumIntakeError("intake retrieval lacks a raw response path")
    return write_raw_response(
        document,
        root=root,
        relative_path=relative_path,
        force=force,
    )


def download_intake_media(
    record: Mapping[str, Any],
    *,
    root: str | Path,
    downloaded_at: str,
    timeout: float = 60.0,
    max_bytes: int = DEFAULT_MAX_MEDIA_BYTES,
    max_media_count: int = DEFAULT_MAX_MEDIA_COUNT,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_MEDIA_BYTES,
    force: bool = False,
    opener: UrlOpener = _secure_urlopen,
) -> JsonObject:
    """Download every enumerated medium and return a copy with integrity metadata."""

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if max_media_count < 1:
        raise ValueError("max_media_count must be positive")
    if max_total_bytes < 1:
        raise ValueError("max_total_bytes must be positive")
    validate_intake_semantics(record)
    updated = copy.deepcopy(dict(record))
    media = updated.get("media")
    if not isinstance(media, list) or not media:
        raise MuseumIntakeError("intake record must contain at least one media row")
    if len(media) > max_media_count:
        raise MuseumIntakeError(
            f"intake media count exceeds limit: {len(media)} > {max_media_count}"
        )

    downloaded_bytes = 0
    for index, item in enumerate(media):
        if not isinstance(item, dict):
            raise MuseumIntakeError(f"media[{index}] must be an object")
        source_uri = item.get("source_uri")
        media_id = item.get("media_id")
        if not isinstance(source_uri, str) or not isinstance(media_id, str):
            raise MuseumIntakeError(f"media[{index}] lacks source_uri or media_id")
        _require_https_url(source_uri)
        relative_path = _media_relative_path(updated, item)
        destination = _resolved_bundle_path(root, relative_path)
        remaining_bytes = max_total_bytes - downloaded_bytes
        if remaining_bytes < 1:
            raise MuseumIntakeError(
                f"intake media bytes exceed aggregate limit ({max_total_bytes})"
            )
        download = _download_file(
            source_uri,
            destination=destination,
            downloaded_at=downloaded_at,
            timeout=timeout,
            max_bytes=min(max_bytes, remaining_bytes),
            force=force,
            opener=opener,
        )
        downloaded_bytes += int(download["bytes"])
        download["local_relative_path"] = relative_path
        item["download"] = download
    validate_intake_semantics(updated)
    return updated


def validate_intake_semantics(
    record: Mapping[str, Any],
    *,
    document: JsonDocument | None = None,
) -> None:
    """Enforce cross-field invariants that JSON Schema cannot express."""

    retrieval = record.get("retrieval")
    rights = record.get("item_rights")
    if not isinstance(retrieval, Mapping) or not isinstance(rights, Mapping):
        raise MuseumIntakeError("intake retrieval and item_rights must be objects")
    evidence = rights.get("evidence")
    if not isinstance(evidence, Mapping):
        raise MuseumIntakeError("item_rights.evidence must be an object")
    response_sha256 = retrieval.get("response_sha256")
    evidence_sha256 = evidence.get("api_response_sha256")
    if response_sha256 != evidence_sha256:
        raise MuseumIntakeError("item rights evidence hash must equal retrieval response hash")
    if document is not None:
        if response_sha256 != document.sha256:
            raise MuseumIntakeError("intake response hash does not match fetched bytes")
        if retrieval.get("api_endpoint") != document.url:
            raise MuseumIntakeError("intake API endpoint does not match fetched URL")
        if retrieval.get("http_status") != document.status:
            raise MuseumIntakeError("intake HTTP status does not match fetched response")
        recorded_content_type = _normalized_content_type(
            retrieval.get("response_content_type")
            if isinstance(retrieval.get("response_content_type"), str)
            else None
        )
        if recorded_content_type != document.content_type:
            raise MuseumIntakeError("intake response content type does not match fetched response")
    retrieved_at = retrieval.get("retrieved_at")
    if not isinstance(retrieved_at, str):
        raise MuseumIntakeError("intake retrieval lacks an RFC 3339 retrieved_at")
    _require_canonical_rfc3339(retrieved_at, "retrieval.retrieved_at")

    if rights.get("item_level_verified") is not True:
        raise MuseumIntakeError("item-level rights must be verified")
    for field in ("redistribution", "derivatives", "commercial_use"):
        if rights.get(field) is not True:
            raise MuseumIntakeError(f"item rights must explicitly allow {field}")

    source_id = record.get("source_id")
    provider_hosts = _PROVIDER_HOSTS.get(source_id) if isinstance(source_id, str) else None
    if provider_hosts is None:
        raise MuseumIntakeError(f"unsupported museum intake source_id: {source_id!r}")
    api_endpoint = retrieval.get("api_endpoint")
    official_record = record.get("official_record")
    if not isinstance(api_endpoint, str) or not isinstance(official_record, Mapping):
        raise MuseumIntakeError("provider intake lacks API or official record metadata")
    record_uri = official_record.get("record_uri")
    if not isinstance(record_uri, str):
        raise MuseumIntakeError("provider intake lacks an official record URI")
    _require_allowed_host(api_endpoint, provider_hosts["api"], "API endpoint")
    _require_allowed_host(record_uri, provider_hosts["record"], "record URI")

    media = record.get("media")
    if not isinstance(media, Sequence) or isinstance(media, (str, bytes)) or not media:
        raise MuseumIntakeError("intake must contain at least one media row")
    media_ids: set[str] = set()
    for index, item in enumerate(media):
        if not isinstance(item, Mapping):
            raise MuseumIntakeError(f"media[{index}] must be an object")
        media_id = item.get("media_id")
        if not isinstance(media_id, str) or not media_id:
            raise MuseumIntakeError(f"media[{index}] lacks a stable media_id")
        if media_id in media_ids:
            raise MuseumIntakeError(f"duplicate media_id: {media_id}")
        media_ids.add(media_id)
        if item.get("physical_side") != "unknown":
            raise MuseumIntakeError(f"media[{index}] must not infer a physical side during intake")
        if item.get("rights_basis") != "item_rights":
            raise MuseumIntakeError(f"media[{index}] lacks item-level rights inheritance")
        source_uri = item.get("source_uri")
        if not isinstance(source_uri, str):
            raise MuseumIntakeError(f"media[{index}] lacks source_uri")
        _require_https_url(source_uri)
        _require_allowed_host(
            source_uri,
            provider_hosts["media"],
            f"media[{index}] source",
        )
        download = item.get("download")
        if not isinstance(download, Mapping):
            raise MuseumIntakeError(f"media[{index}].download must be an object")
        required_download_keys = {
            "status",
            "sha256",
            "bytes",
            "content_type",
            "local_relative_path",
            "downloaded_at",
        }
        if set(download) != required_download_keys:
            raise MuseumIntakeError(f"media[{index}].download is not a closed object")
        status = download.get("status")
        evidence_fields = (
            download.get("sha256"),
            download.get("bytes"),
            download.get("content_type"),
            download.get("local_relative_path"),
            download.get("downloaded_at"),
        )
        if status == "not_downloaded" and any(value is not None for value in evidence_fields):
            raise MuseumIntakeError(
                f"media[{index}] has download evidence without downloaded bytes"
            )
        if status == "downloaded" and any(value is None for value in evidence_fields):
            raise MuseumIntakeError(f"media[{index}] lacks complete download evidence")
        if status not in {"downloaded", "not_downloaded"}:
            raise MuseumIntakeError(f"media[{index}] has invalid download status")
        if status == "downloaded":
            checksum = download.get("sha256")
            if not isinstance(checksum, str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                checksum,
            ):
                raise MuseumIntakeError(f"media[{index}] lacks a valid SHA-256 checksum")
            byte_count = download.get("bytes")
            if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 1:
                raise MuseumIntakeError(
                    f"media[{index}] downloaded bytes must be a positive integer"
                )
            content_type = download.get("content_type")
            if content_type not in {
                "image/jpeg",
                "image/png",
                "image/tiff",
                "image/x-tiff",
            }:
                raise MuseumIntakeError(
                    f"media[{index}] has an unsupported downloaded content type"
                )
            local_relative_path = download.get("local_relative_path")
            if not isinstance(local_relative_path, str):
                raise MuseumIntakeError(f"media[{index}] lacks a downloaded relative path")
            _require_safe_relative_path(
                local_relative_path,
                f"media[{index}] download path",
            )
            downloaded_at = download.get("downloaded_at")
            if not isinstance(downloaded_at, str):
                raise MuseumIntakeError(f"media[{index}] lacks an RFC 3339 download time")
            _require_canonical_rfc3339(
                downloaded_at,
                f"media[{index}].downloaded_at",
            )

    if document is not None:
        _verify_record_matches_document(record, document)


def verify_intake_bundle(
    record: Mapping[str, Any],
    *,
    root: str | Path,
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES,
    max_media_bytes: int = DEFAULT_MAX_MEDIA_BYTES,
    max_media_count: int = DEFAULT_MAX_MEDIA_COUNT,
    max_total_media_bytes: int = DEFAULT_MAX_TOTAL_MEDIA_BYTES,
) -> JsonObject:
    """Rehash a private intake bundle and return a concise integrity report."""

    if max_json_bytes < 1:
        raise ValueError("max_json_bytes must be positive")
    if max_media_bytes < 1:
        raise ValueError("max_media_bytes must be positive")
    if max_media_count < 1:
        raise ValueError("max_media_count must be positive")
    if max_total_media_bytes < 1:
        raise ValueError("max_total_media_bytes must be positive")
    validate_intake_semantics(record)
    retrieval = record["retrieval"]
    if not isinstance(retrieval, Mapping):
        raise MuseumIntakeError("intake retrieval must be an object")
    raw_relative = retrieval.get("raw_response_local_relative_path")
    if not isinstance(raw_relative, str):
        raise MuseumIntakeError("intake retrieval lacks a raw response path")
    raw_path = _resolved_bundle_path(root, raw_relative)
    stored_document = _stored_json_document(
        record,
        raw_path,
        max_bytes=max_json_bytes,
    )
    raw_hash = stored_document.sha256
    raw_bytes = len(stored_document.raw_bytes)
    if raw_hash != retrieval.get("response_sha256"):
        raise MuseumIntakeError(f"raw API response hash mismatch: {raw_path}")
    _verify_record_matches_document(record, stored_document)

    downloaded_count = 0
    downloaded_bytes = 0
    if len(record["media"]) > max_media_count:
        raise MuseumIntakeError(
            f"intake media count exceeds verification limit: "
            f"{len(record['media'])} > {max_media_count}"
        )
    for item in record["media"]:
        if not isinstance(item, Mapping):
            raise MuseumIntakeError("media row must be an object")
        download = item.get("download")
        if not isinstance(download, Mapping) or download.get("status") != "downloaded":
            continue
        relative_path = download.get("local_relative_path")
        if not isinstance(relative_path, str):
            raise MuseumIntakeError("downloaded media lacks a local path")
        expected_relative_path = _media_relative_path(record, item)
        if relative_path != expected_relative_path:
            raise MuseumIntakeError(
                f"downloaded media path does not match its deterministic path: "
                f"{relative_path!r} != {expected_relative_path!r}"
            )
        media_path = _resolved_bundle_path(root, relative_path)
        remaining_total_bytes = max_total_media_bytes - downloaded_bytes
        if remaining_total_bytes < 1:
            raise MuseumIntakeError("downloaded media exceed the aggregate verification limit")
        media_hash, media_bytes, prefix = _hash_file(
            media_path,
            max_bytes=min(max_media_bytes, remaining_total_bytes),
        )
        if media_hash != download.get("sha256"):
            raise MuseumIntakeError(f"downloaded media hash mismatch: {media_path}")
        if media_bytes != download.get("bytes"):
            raise MuseumIntakeError(f"downloaded media byte count mismatch: {media_path}")
        content_type = download.get("content_type")
        source_uri = item.get("source_uri")
        if not isinstance(content_type, str) or not isinstance(source_uri, str):
            raise MuseumIntakeError("downloaded media lacks content type or source URI")
        _validate_image_signature(source_uri, content_type, prefix)
        downloaded_count += 1
        downloaded_bytes += media_bytes
    return {
        "intake_id": record.get("intake_id"),
        "raw_response_sha256": raw_hash,
        "raw_response_bytes": raw_bytes,
        "downloaded_media_count": downloaded_count,
        "downloaded_media_bytes": downloaded_bytes,
        "verified": True,
    }


def _stored_json_document(
    record: Mapping[str, Any],
    path: Path,
    *,
    max_bytes: int,
) -> JsonDocument:
    retrieval = record.get("retrieval")
    if not isinstance(retrieval, Mapping):
        raise MuseumIntakeError("intake retrieval must be an object")
    endpoint = retrieval.get("api_endpoint")
    status = retrieval.get("http_status")
    content_type_value = retrieval.get("response_content_type")
    if not isinstance(endpoint, str):
        raise MuseumIntakeError("intake retrieval lacks an API endpoint")
    _require_https_url(endpoint)
    if status != 200:
        raise MuseumIntakeError("stored API evidence must have HTTP status 200")
    if not isinstance(content_type_value, str):
        raise MuseumIntakeError("intake retrieval lacks a response content type")
    content_type = _normalized_content_type(content_type_value)
    if content_type not in {"application/json", "application/ld+json"}:
        raise MuseumIntakeError("stored API evidence must have a JSON content type")
    try:
        with _open_regular_binary(path) as handle:
            raw_bytes = _read_bounded(
                handle,
                max_bytes=max_bytes,
                label=str(path),
            )
    except FileNotFoundError as error:
        raise MuseumIntakeError(f"intake bundle file is missing: {path}") from error
    try:
        value = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MuseumIntakeError(f"stored API response is not valid UTF-8 JSON: {path}") from error
    if not isinstance(value, dict):
        raise MuseumIntakeError(f"stored API response must be a JSON object: {path}")
    return JsonDocument(
        url=endpoint,
        status=status,
        content_type=content_type,
        headers={"content-type": content_type},
        raw_bytes=raw_bytes,
        value=value,
    )


def _verify_record_matches_document(
    record: Mapping[str, Any],
    document: JsonDocument,
) -> None:
    source_id = record.get("source_id")
    retrieval = record.get("retrieval")
    official_record = record.get("official_record")
    if not isinstance(retrieval, Mapping) or not isinstance(official_record, Mapping):
        raise MuseumIntakeError("intake lacks retrieval or official record metadata")
    retrieved_at = retrieval.get("retrieved_at")
    if not isinstance(retrieved_at, str) or not retrieved_at:
        raise MuseumIntakeError("intake retrieval lacks retrieved_at")

    if source_id == MET_SOURCE_ID:
        object_id_value = official_record.get("object_id")
        if not isinstance(object_id_value, str) or not object_id_value.isdigit():
            raise MuseumIntakeError("Met intake object_id must be a positive decimal string")
        object_id = int(object_id_value)
        if object_id < 1:
            raise MuseumIntakeError("Met intake object_id must be positive")
        rebuilt = build_met_intake(
            document,
            expected_object_id=object_id,
            retrieved_at=retrieved_at,
        )
    elif source_id == CLEVELAND_SOURCE_ID:
        accession_value = official_record.get("accession_number")
        if not isinstance(accession_value, str):
            raise MuseumIntakeError("Cleveland intake lacks an accession number")
        accession_number = _validated_accession(accession_value)
        derivative_names: list[str] = []
        media = record.get("media")
        if not isinstance(media, Sequence) or isinstance(media, (str, bytes)):
            raise MuseumIntakeError("Cleveland intake media must be a sequence")
        derivative_map = {
            "cleveland_print": "print",
            "cleveland_full": "full",
        }
        for item in media:
            if not isinstance(item, Mapping):
                raise MuseumIntakeError("Cleveland intake media row must be an object")
            provider_derivative = item.get("provider_derivative")
            if not isinstance(provider_derivative, str):
                raise MuseumIntakeError("Cleveland provider derivative must be a string")
            derivative = derivative_map.get(provider_derivative)
            if derivative is None:
                raise MuseumIntakeError(
                    f"unsupported Cleveland provider derivative: {provider_derivative!r}"
                )
            if derivative not in derivative_names:
                derivative_names.append(derivative)
        rebuilt = build_cleveland_intake(
            document,
            expected_accession_number=accession_number,
            retrieved_at=retrieved_at,
            derivatives=derivative_names,
        )
    else:
        raise MuseumIntakeError(f"unsupported museum intake source_id: {source_id!r}")

    normalized = copy.deepcopy(dict(record))
    normalized_media = normalized.get("media")
    if not isinstance(normalized_media, list):
        raise MuseumIntakeError("intake media must be a list")
    for item in normalized_media:
        if not isinstance(item, dict):
            raise MuseumIntakeError("intake media row must be an object")
        item["download"] = {
            "status": "not_downloaded",
            "sha256": None,
            "bytes": None,
            "content_type": None,
            "local_relative_path": None,
            "downloaded_at": None,
        }
    if normalized != rebuilt:
        raise MuseumIntakeError(
            "intake metadata does not exactly match the stored official API response"
        )


def _download_file(
    url: str,
    *,
    destination: Path,
    downloaded_at: str,
    timeout: float,
    max_bytes: int,
    force: bool,
    opener: UrlOpener,
) -> JsonObject:
    if destination.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing media without force: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"Accept": "image/*", "User-Agent": USER_AGENT})
    temporary_path: Path | None = None
    try:
        with opener(request, timeout=timeout) as response:
            status = _response_status(response)
            if status != 200:
                raise MuseumIntakeError(f"expected HTTP 200 from {url}, received {status}")
            _require_no_redirect(url, _response_url(response, url))
            headers = _response_headers(response)
            content_type = _normalized_content_type(headers.get("content-type"))
            if not content_type.startswith("image/"):
                raise MuseumIntakeError(
                    f"expected an image content type from {url}, "
                    f"received {content_type or 'unknown'}"
                )
            header_length = _optional_content_length(headers.get("content-length"), url)
            if header_length is not None and header_length > max_bytes:
                raise MuseumIntakeError(
                    f"content-length for {url} exceeds max_bytes ({header_length} > {max_bytes})"
                )

            digest = hashlib.sha256()
            byte_count = 0
            prefix = bytearray()
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                suffix=".part",
                dir=destination.parent,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    byte_count += len(chunk)
                    if byte_count > max_bytes:
                        raise MuseumIntakeError(
                            f"download from {url} exceeds max_bytes ({max_bytes})"
                        )
                    digest.update(chunk)
                    if len(prefix) < 16:
                        prefix.extend(chunk[: 16 - len(prefix)])
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())

        if header_length is not None and header_length != byte_count:
            raise MuseumIntakeError(
                f"HTTP content-length mismatch for {url}: {header_length} != {byte_count}"
            )
        if byte_count == 0:
            raise MuseumIntakeError(f"empty image response from {url}")
        _validate_image_signature(url, content_type, bytes(prefix))
        if destination.exists() and not force:
            raise FileExistsError(
                f"refusing to overwrite existing media without force: {destination}"
            )
        _install_temporary_file(
            temporary_path,
            destination,
            force=force,
        )
        temporary_path = None
        return {
            "status": "downloaded",
            "sha256": f"sha256:{digest.hexdigest()}",
            "bytes": byte_count,
            "content_type": content_type,
            "local_relative_path": None,
            "downloaded_at": downloaded_at,
        }
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _item_rights(
    *,
    rights_holder: str,
    api_field: str,
    observed_value: str | bool,
    item_record_uri: str,
    policy_uri: str,
    verified_at: str,
    response_sha256: str,
    statement: str,
) -> JsonObject:
    return {
        "status": "public_domain",
        "item_level_verified": True,
        "license_id": "CC0-1.0",
        "license_uri": CC0_URI,
        "rights_holder": rights_holder,
        "redistribution": True,
        "derivatives": True,
        "commercial_use": True,
        "statement": statement,
        "evidence": {
            "scope": "item",
            "api_field": api_field,
            "observed_value": observed_value,
            "item_record_uri": item_record_uri,
            "policy_uri": policy_uri,
            "verified_at": verified_at,
            "api_response_sha256": response_sha256,
        },
    }


def _media_row(
    *,
    media_id: str,
    provider_media_id: str | None,
    view_role: str,
    provider_view_index: int,
    provider_derivative: str,
    source_uri: str,
    provider_width: int | None = None,
    provider_height: int | None = None,
    api_declared_bytes: int | None = None,
) -> JsonObject:
    _require_https_url(source_uri)
    return {
        "media_id": media_id,
        "provider_media_id": provider_media_id,
        "view_role": view_role,
        "physical_side": "unknown",
        "provider_view_index": provider_view_index,
        "provider_derivative": provider_derivative,
        "provider_width": provider_width,
        "provider_height": provider_height,
        "api_declared_bytes": api_declared_bytes,
        "source_uri": source_uri,
        "rights_basis": "item_rights",
        "download": {
            "status": "not_downloaded",
            "sha256": None,
            "bytes": None,
            "content_type": None,
            "local_relative_path": None,
            "downloaded_at": None,
        },
    }


def _cleveland_media_rows(
    image_record: Mapping[str, Any],
    *,
    accession_number: str,
    provider_view_index: int,
    view_slug: str,
    view_role: str,
    derivatives: Sequence[str],
) -> list[JsonObject]:
    rows = []
    for derivative in derivatives:
        value = image_record.get(derivative)
        if not isinstance(value, Mapping):
            raise MuseumIntakeError(
                f"Cleveland {accession_number} {view_slug} lacks {derivative} image metadata"
            )
        source_uri = _require_https_string(value, "url", "Cleveland image")
        rows.append(
            _media_row(
                media_id=(f"cleveland:{accession_number}:{view_slug}:{derivative}"),
                provider_media_id=(
                    f"images.{derivative}"
                    if view_slug == "primary"
                    else f"alternate_images[{provider_view_index - 1}].{derivative}"
                ),
                view_role=view_role,
                provider_view_index=provider_view_index,
                provider_derivative=f"cleveland_{derivative}",
                source_uri=source_uri,
                provider_width=_positive_integer(value.get("width"), "image width"),
                provider_height=_positive_integer(value.get("height"), "image height"),
                api_declared_bytes=_positive_integer(value.get("filesize"), "image filesize"),
            )
        )
    return rows


def _media_relative_path(record: Mapping[str, Any], media: Mapping[str, Any]) -> str:
    intake_id = record.get("intake_id")
    media_id = media.get("media_id")
    source_uri = media.get("source_uri")
    if not all(isinstance(value, str) for value in (intake_id, media_id, source_uri)):
        raise MuseumIntakeError("cannot derive a media path from incomplete intake metadata")
    parsed = urlparse(str(source_uri))
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in _SUPPORTED_IMAGE_SUFFIXES:
        raise MuseumIntakeError(f"unsupported image suffix {suffix!r} in {source_uri}")
    intake_component = _safe_component(str(intake_id))
    media_component = _safe_component(str(media_id))
    return f"images/{intake_component}/{media_component}{suffix}"


def _atomic_write_bytes(destination: Path, value: bytes, *, force: bool) -> None:
    if destination.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file without force: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        if destination.exists() and not force:
            raise FileExistsError(
                f"refusing to overwrite existing file without force: {destination}"
            )
        _install_temporary_file(
            temporary_path,
            destination,
            force=force,
        )
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _hash_file(path: Path, *, max_bytes: int) -> tuple[str, int, bytes]:
    digest = hashlib.sha256()
    byte_count = 0
    prefix = bytearray()
    try:
        with _open_regular_binary(path) as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise MuseumIntakeError(
                        f"bundle file exceeds verification limit: {path} "
                        f"({byte_count} > {max_bytes})"
                    )
                if len(prefix) < 16:
                    prefix.extend(chunk[: 16 - len(prefix)])
    except FileNotFoundError as error:
        raise MuseumIntakeError(f"intake bundle file is missing: {path}") from error
    return f"sha256:{digest.hexdigest()}", byte_count, bytes(prefix)


def _install_temporary_file(
    temporary_path: Path,
    destination: Path,
    *,
    force: bool,
) -> None:
    if force:
        os.replace(temporary_path, destination)
        return
    try:
        os.link(temporary_path, destination)
    except FileExistsError as error:
        raise FileExistsError(
            f"refusing to overwrite concurrently created file: {destination}"
        ) from error
    temporary_path.unlink()


@contextmanager
def _open_regular_binary(path: Path) -> Iterator[BinaryIO]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise MuseumIntakeError(f"bundle path is not a regular file: {path}")
        if metadata.st_nlink != 1:
            raise MuseumIntakeError(f"bundle file must have exactly one hard link: {path}")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            yield handle
    except FileNotFoundError as error:
        raise MuseumIntakeError(f"intake bundle file is missing: {path}") from error
    except OSError as error:
        raise MuseumIntakeError(f"cannot safely open bundle file {path}: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_bounded(response: Any, *, max_bytes: int, label: str) -> bytes:
    chunks: list[bytes] = []
    byte_count = 0
    while True:
        chunk = response.read(min(1024 * 1024, max_bytes + 1 - byte_count))
        if not chunk:
            break
        byte_count += len(chunk)
        if byte_count > max_bytes:
            raise MuseumIntakeError(f"response from {label} exceeds max_bytes ({max_bytes})")
        chunks.append(chunk)
    return b"".join(chunks)


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    if isinstance(status, bool) or not isinstance(status, int):
        raise MuseumIntakeError("HTTP response did not supply an integer status")
    return status


def _response_headers(response: Any) -> dict[str, str]:
    headers = getattr(response, "headers", None)
    if headers is None:
        raise MuseumIntakeError("HTTP response did not supply headers")
    return {str(key).lower(): str(value).strip() for key, value in headers.items()}


def _response_url(response: Any, requested_url: str) -> str:
    geturl = getattr(response, "geturl", None)
    if not callable(geturl):
        return requested_url
    value = geturl()
    if not isinstance(value, str):
        raise MuseumIntakeError("HTTP response returned an invalid final URL")
    _require_https_url(value)
    return value


def _require_no_redirect(requested_url: str, final_url: str) -> None:
    if final_url != requested_url:
        raise MuseumIntakeError(
            f"HTTP redirects are not allowed: {requested_url!r} -> {final_url!r}"
        )


def _validate_policy_document_identity(
    document: PolicyDocument,
    specification: PolicyEvidenceSpec,
) -> None:
    if (
        document.evidence_id != specification.evidence_id
        or document.source_id != specification.source_id
        or document.url != specification.uri
        or document.status != 200
        or document.content_type not in specification.allowed_content_types
        or document.raw_relative_path != specification.raw_relative_path
    ):
        raise MuseumIntakeError(f"policy document identity mismatch: {specification.evidence_id}")


def _validate_policy_manifest_entry(
    entry: Mapping[str, Any],
    specification: PolicyEvidenceSpec,
) -> None:
    required_keys = {
        "evidence_id",
        "source_id",
        "uri",
        "retrieved_at",
        "http_status",
        "response_content_type",
        "response_sha256",
        "response_bytes",
        "raw_response_local_relative_path",
    }
    if set(entry) != required_keys:
        raise MuseumIntakeError(f"policy manifest row is not closed: {specification.evidence_id}")
    expected_values = {
        "evidence_id": specification.evidence_id,
        "source_id": specification.source_id,
        "uri": specification.uri,
        "http_status": 200,
        "raw_response_local_relative_path": specification.raw_relative_path,
    }
    for field, expected in expected_values.items():
        if entry.get(field) != expected:
            raise MuseumIntakeError(
                f"policy manifest {field} mismatch: {specification.evidence_id}"
            )
    retrieved_at = entry.get("retrieved_at")
    if not isinstance(retrieved_at, str) or not retrieved_at:
        raise MuseumIntakeError("policy manifest retrieved_at must be a string")
    _require_canonical_rfc3339(
        retrieved_at,
        f"policy {specification.evidence_id} retrieved_at",
    )
    content_type = entry.get("response_content_type")
    if content_type not in specification.allowed_content_types:
        raise MuseumIntakeError(
            f"policy manifest content type mismatch: {specification.evidence_id}"
        )
    checksum = entry.get("response_sha256")
    if not isinstance(checksum, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}",
        checksum,
    ):
        raise MuseumIntakeError("policy manifest checksum must be SHA-256")
    response_bytes = entry.get("response_bytes")
    if (
        isinstance(response_bytes, bool)
        or not isinstance(response_bytes, int)
        or response_bytes < 1
    ):
        raise MuseumIntakeError("policy manifest byte count must be positive")


def _validate_policy_markers(
    specification: PolicyEvidenceSpec,
    raw_bytes: bytes,
) -> None:
    if not raw_bytes:
        raise MuseumIntakeError(f"policy evidence is empty: {specification.evidence_id}")
    lowered = raw_bytes.lower()
    missing = [
        marker.decode("ascii", errors="replace")
        for marker in specification.required_markers
        if marker.lower() not in lowered
    ]
    if missing:
        raise MuseumIntakeError(
            f"policy evidence lacks required markers {missing}: {specification.evidence_id}"
        )


def _normalized_content_type(value: str | None) -> str:
    return (value or "").split(";", 1)[0].strip().lower()


def _optional_content_length(value: str | None, label: str) -> int | None:
    if value is None:
        return None
    try:
        result = int(value)
    except ValueError as error:
        raise MuseumIntakeError(f"invalid HTTP content-length from {label}: {value!r}") from error
    if result < 0:
        raise MuseumIntakeError(f"negative HTTP content-length from {label}")
    return result


def _validate_image_signature(url: str, content_type: str, prefix: bytes) -> None:
    suffix = Path(urlparse(url).path).suffix.lower()
    valid = False
    if suffix in {".jpg", ".jpeg"} and content_type == "image/jpeg":
        valid = prefix.startswith(b"\xff\xd8")
    elif suffix == ".png" and content_type == "image/png":
        valid = prefix.startswith(b"\x89PNG\r\n\x1a\n")
    elif suffix in {".tif", ".tiff"} and content_type in {"image/tiff", "image/x-tiff"}:
        valid = prefix.startswith((b"II*\x00", b"MM\x00*"))
    if not valid:
        raise MuseumIntakeError(f"image signature, suffix, and content type disagree for {url}")


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise MuseumIntakeError(f"{label} must be a positive integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
        result = int(value)
    else:
        raise MuseumIntakeError(f"{label} must be an integer or canonical positive decimal string")
    if result < 1:
        raise MuseumIntakeError(f"{label} must be a positive integer")
    return result


def _unique_json_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    value: JsonObject = {}
    for key, item in pairs:
        if key in value:
            raise MuseumIntakeError(f"JSON object contains duplicate key: {key!r}")
        value[key] = item
    return value


def _require_string(record: Mapping[str, Any], key: str, label: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MuseumIntakeError(f"{label} {key} must be a non-empty string")
    return value.strip()


def _require_https_string(record: Mapping[str, Any], key: str, label: str) -> str:
    value = _require_string(record, key, label)
    _require_https_url(value)
    return value


def _require_https_url(value: str) -> None:
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError as error:
        raise MuseumIntakeError(f"invalid HTTPS port in URL {value!r}") from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or port not in {None, 443}
    ):
        raise MuseumIntakeError(f"expected a credential-free HTTPS URL, received {value!r}")


def _require_canonical_rfc3339(value: str, label: str) -> None:
    if not _RFC3339_PATTERN.fullmatch(value):
        raise MuseumIntakeError(f"{label} must be a strict RFC 3339 date-time")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise MuseumIntakeError(f"{label} must be an RFC 3339 date-time") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MuseumIntakeError(f"{label} must include a UTC offset")
    canonical = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise MuseumIntakeError(f"{label} must use canonical RFC 3339 form")


def _require_safe_relative_path(value: str, label: str) -> None:
    if not re.fullmatch(
        r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*",
        value,
    ):
        raise MuseumIntakeError(f"{label} is not a safe bundle-relative path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise MuseumIntakeError(f"{label} is not a safe bundle-relative path")


def _require_allowed_host(value: str, allowed_hosts: set[str], label: str) -> None:
    _require_https_url(value)
    hostname = (urlparse(value).hostname or "").lower()
    if hostname not in allowed_hosts:
        raise MuseumIntakeError(f"{label} host {hostname!r} is not in the provider allowlist")


def _validated_accession(value: str) -> str:
    accession = value.strip()
    if not _ACCESSION_PATTERN.fullmatch(accession):
        raise ValueError(f"invalid accession number: {value!r}")
    return accession


def _safe_component(value: str) -> str:
    component = _SAFE_COMPONENT_PATTERN.sub("_", value).strip("._")
    if not component or component in {".", ".."}:
        raise MuseumIntakeError(f"cannot derive a safe path component from {value!r}")
    return component


def _resolved_bundle_path(root: str | Path, relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise MuseumIntakeError(f"unsafe bundle-relative path: {relative_path!r}")
    root_path = Path(root).resolve()
    unresolved_candidate = root_path.joinpath(*relative.parts)
    current = root_path
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise MuseumIntakeError(f"bundle path contains a symbolic link: {relative_path!r}")
    candidate = unresolved_candidate.resolve()
    if candidate != root_path and root_path not in candidate.parents:
        raise MuseumIntakeError(f"path escapes bundle root: {relative_path!r}")
    return candidate
