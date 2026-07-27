"""Privacy-minimized readiness checks for a local, non-public corpus.

The scanner deliberately keeps logical paths, filenames, source identifiers,
locators, values, and keyed content tokens in memory only.  Its public summary
contains a fixed vocabulary and no corpus counts.  The optional aggregate
report is still private-by-default and never contains item-level material.

A successful result means only that a point-in-time declaration is internally
compatible with the requested local, non-public use.  It does not attest legal
ownership, provenance authenticity, confidentiality, custody, blindness,
future immutability, decipherment, or prize eligibility.
"""

from __future__ import annotations

import csv
import ctypes
import decimal
import errno
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import stat
import sys
import threading
import unicodedata
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from indusbench.quarantine import inspect_corpus_quarantine

SCHEMA_VERSION = "0.2.0"
POLICY_SCHEMA_VERSION = "0.2.0"
CLAIM_CLASS = "private_working_corpus_readiness"
REPORT_KIND = "private_corpus_readiness_aggregate"

INTENDED_USES = frozenset(
    {
        "local_nonpublic_research",
        "local_nonpublic_normalization",
    }
)
REASON_CODES = frozenset(
    {
        "PLATFORM_UNSUPPORTED",
        "ROOT_BOUNDARY_INVALID",
        "PERMISSION_BOUNDARY_INVALID",
        "ACL_UNVERIFIABLE_OR_PRESENT",
        "SYMLINK_PRESENT",
        "HARDLINK_OR_DUPLICATE_INODE",
        "SPECIAL_OR_UNSUPPORTED_ENTRY",
        "CROSS_DEVICE_ENTRY",
        "PATH_PROFILE_INVALID_OR_COLLISION",
        "RESOURCE_LIMIT_EXCEEDED",
        "CONCURRENT_MUTATION_DETECTED",
        "INPUT_UNREADABLE_OR_UNVERIFIABLE",
        "POLICY_DOCUMENT_INVALID",
        "POLICY_CONTENT_BINDING_MISMATCH",
        "POLICY_REVIEW_INCOMPLETE",
        "RIGHTS_COVERAGE_INCOMPLETE",
        "RIGHTS_AMBIGUOUS_OR_CONFLICTING",
        "INTENDED_USE_NOT_PERMITTED",
        "QUARANTINED_OR_UNKNOWN_SOURCE",
        "CONTENT_CONTRACT_INVALID",
        "INTERNAL_ERROR",
    }
)

ASSURANCE = {
    "blind_claim_allowed": False,
    "final_evaluation_eligible": False,
    "independent_custody_attested": False,
    "external_custodian_attested": False,
    "trusted_timestamp_attested": False,
    "access_history_attested": False,
    "confidentiality_attested": False,
    "rights_ownership_attested": False,
    "provenance_authenticity_attested": False,
    "future_immutability_attested": False,
    "decipherment_claim_allowed": False,
    "prize_submission_eligible": False,
}

PRIVACY = {
    "aggregate_only": True,
    "paths_disclosed": False,
    "filenames_disclosed": False,
    "content_digests_disclosed": False,
    "identifiers_disclosed": False,
    "private_values_disclosed": False,
    "publication_review_required": True,
}

FORMAT_NAMES = (
    "jpeg",
    "tiff",
    "json",
    "jsonl",
    "csv",
    "html",
    "plain_text",
    "unknown_binary",
)
SIGNAL_NAMES = (
    "documented_provenance",
    "partial_provenance",
    "unknown_provenance",
    "disputed_provenance",
    "public_domain_rights",
    "open_licensed_rights",
    "permission_granted_rights",
    "metadata_only_rights",
    "restricted_rights",
    "unknown_rights",
    "documented_rights_evidence",
    "missing_rights_evidence",
    "ambiguous_rights_evidence",
    "conflicting_rights_evidence",
)

_POLICY_KEYS = frozenset({"schema_version", "policy_kind", "entries"})
_ENTRY_KEYS = frozenset(
    {
        "relative_path",
        "content_sha256",
        "curation_status",
        "content_layer",
        "source_id",
        "source_locator",
        "source_revision",
        "provenance_status",
        "rights_status",
        "rights_evidence_status",
        "permitted_uses",
    }
)
_CONTENT_LAYERS = frozenset(
    {
        "metadata",
        "transcription",
        "image",
        "catalog_scan",
        "documentation",
        "derived_statistics",
        "configuration",
        "model_artifact",
        "unknown",
    }
)
_METADATA_ONLY_LAYERS = frozenset(
    {
        "metadata",
        "documentation",
        "derived_statistics",
        "configuration",
    }
)
_PROVENANCE_STATUSES = frozenset({"documented", "partial", "unknown", "disputed"})
_RIGHTS_STATUSES = frozenset(
    {
        "public_domain",
        "open_licensed",
        "permission_granted",
        "metadata_only",
        "restricted",
        "unknown",
    }
)
_EVIDENCE_STATUSES = frozenset({"documented", "missing", "ambiguous", "conflicting"})
_CURATION_STATUSES = frozenset({"pending", "reviewed"})
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")

STRUCTURE_ANOMALY_CODES = frozenset(
    {
        "ANOMALY_LIMIT_EXCEEDED",
        "CSV_COLUMN_LIMIT_EXCEEDED",
        "CSV_EMPTY_DOCUMENT",
        "CSV_PARSE_ERROR",
        "CSV_RECORD_LIMIT_EXCEEDED",
        "CSV_ROW_LIMIT_EXCEEDED",
        "CSV_ROW_WIDTH_MISMATCH",
        "INVALID_UTF8",
        "JSON_COMPLEXITY_LIMIT_EXCEEDED",
        "JSON_DOCUMENT_INVALID",
        "JSONL_EMPTY_DOCUMENT",
        "JSONL_RECORD_INVALID",
        "JSONL_RECORD_LIMIT_EXCEEDED",
        "JSONL_RECORD_NOT_OBJECT",
        "NUL_BYTE_PRESENT",
        "STRUCTURED_DOCUMENT_TOO_LARGE",
        "UTF8_BOM_PRESENT",
    }
)
_CSV_FIELD_LIMIT_LOCK = threading.Lock()
_MAX_CONFIGURED_JSON_DEPTH = 256
_MAX_JSON_NUMBER_BYTES = 512
_JSON_LINE_SEPARATOR = re.compile(rb"\r\n?|\n")


@dataclass(frozen=True)
class AuditLimits:
    """Closed resource limits for one readiness audit."""

    max_files: int = 4096
    max_directories: int = 4096
    max_depth: int = 32
    max_component_bytes: int = 255
    max_path_bytes: int = 4096
    max_file_bytes: int = 8 * 1024 * 1024 * 1024
    max_total_bytes: int = 16 * 1024 * 1024 * 1024
    max_structured_bytes: int = 64 * 1024 * 1024
    max_csv_bytes: int = 512 * 1024 * 1024
    max_json_nodes: int = 100_000
    max_json_depth: int = 64
    max_csv_rows: int = 2_000_000
    max_csv_columns: int = 4096
    max_csv_record_bytes: int = 1024 * 1024
    max_anomalies: int = 1000
    read_chunk_bytes: int = 1024 * 1024


@dataclass(frozen=True)
class AuditResult:
    """Safe public summary plus an aggregate report intended for private storage."""

    summary: dict[str, Any]
    report: dict[str, Any] | None


class PrivateReadinessError(ValueError):
    """A fixed-code failure that cannot contain private input."""

    def __init__(self, code: str) -> None:
        safe_code = code if code in REASON_CODES else "INTERNAL_ERROR"
        self.code = safe_code
        super().__init__(safe_code)


@dataclass(frozen=True)
class _StructureAnomaly:
    code: str
    record_number: int | None = None
    expected_columns: int | None = None
    observed_columns: int | None = None


@dataclass(frozen=True)
class _FileAnalysis:
    format_name: str
    parseable: bool
    structured_records: int = 0
    csv_rows: int = 0
    ragged: int = 0
    anomalies: tuple[_StructureAnomaly, ...] = ()
    anomaly_enumeration_complete: bool = True


@dataclass(frozen=True)
class _FileObservation:
    relative_path: str
    path_token: bytes
    content_token: bytes
    content_sha256: bytes
    byte_count: int
    fingerprint: tuple[int, ...]
    analysis: _FileAnalysis


@dataclass(frozen=True)
class _Snapshot:
    files: tuple[_FileObservation, ...]
    namespaces: tuple[tuple[bytes, tuple[int, ...]], ...]
    root_identity: tuple[int, ...]
    directory_count: int
    total_bytes: int


@dataclass
class _ScanState:
    key: bytes
    limits: AuditLimits
    root_device: int
    effective_uid: int
    files: list[_FileObservation]
    namespaces: list[tuple[bytes, tuple[int, ...]]]
    collision_paths: set[str]
    inodes: set[tuple[int, int]]
    recorded_anomalies: int = 0
    directory_count: int = 1
    total_bytes: int = 0


@dataclass(frozen=True)
class _PolicyEntry:
    path_token: bytes
    content_sha256: bytes
    curation_status: str
    content_layer: str
    source_id: str
    source_locator: str | None
    source_revision: str | None
    provenance_status: str
    rights_status: str
    rights_evidence_status: str
    permitted_uses: frozenset[str]


@dataclass(frozen=True)
class _PinnedDirectory:
    descriptors: tuple[int, ...]
    names: tuple[str, ...]
    fingerprints: tuple[tuple[int, ...], ...]

    @property
    def descriptor(self) -> int:
        return self.descriptors[-1]


class _FormatInvalid(ValueError):
    pass


class _StructuredResourceLimit(_FormatInvalid):
    pass


def safe_failure_summary(intended_use: str, code: str) -> dict[str, Any]:
    """Return a fixed-vocabulary failure summary with no private values."""

    safe_use = intended_use if intended_use in INTENDED_USES else "local_nonpublic_normalization"
    safe_code = code if code in REASON_CODES else "INTERNAL_ERROR"
    return _safe_summary(
        intended_use=safe_use,
        ready=False,
        scan_completed=False,
        reason_codes=(safe_code,),
    )


def audit_private_corpus(
    root: Path,
    *,
    intended_use: str,
    created_at: str,
    policy: Mapping[str, Any] | None,
    source_registry: Mapping[str, Any] | None,
    quarantine_manifest: Mapping[str, Any] | None,
    key: bytes | None = None,
    limits: AuditLimits | None = None,
) -> AuditResult:
    """Audit a physical private root and return only aggregate observations.

    Unsafe filesystem input raises :class:`PrivateReadinessError`, whose string
    representation is a fixed reason code.  Policy incompleteness is a normal,
    successfully scanned result with ``ready=false``.
    """

    if intended_use not in INTENDED_USES:
        raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
    _validate_created_at(created_at)
    active_limits = limits or AuditLimits()
    _validate_limits(active_limits)
    active_key = key if key is not None else secrets.token_bytes(32)
    if not isinstance(active_key, bytes) or len(active_key) < 16:
        raise PrivateReadinessError("INTERNAL_ERROR")

    first = _stable_snapshot(root, key=active_key, limits=active_limits)

    formats = _format_summary(first.files)
    reasons: set[str] = set()
    if formats["invalid"] or formats["ragged"]:
        reasons.add("CONTENT_CONTRACT_INVALID")

    (
        policy_summary,
        signals,
        policy_reasons,
    ) = _evaluate_policy(
        first,
        policy=policy,
        intended_use=intended_use,
        source_registry=source_registry,
        quarantine_manifest=quarantine_manifest,
        key=active_key,
        limits=active_limits,
    )
    reasons.update(policy_reasons)
    ordered_reasons = tuple(sorted(reasons))
    ready = not ordered_reasons
    duplicates = _duplicate_summary(first.files)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "created_at": created_at,
        "intended_use": intended_use,
        "ready": ready,
        "scan_completed": True,
        "reason_codes": list(ordered_reasons),
        "privacy": dict(PRIVACY),
        "assurance": dict(ASSURANCE),
        "inventory": {
            "file_count": len(first.files),
            "directory_count": first.directory_count,
            "total_bytes": first.total_bytes,
        },
        "storage": {
            "owner_only": True,
            "acl_free": True,
            "single_device": True,
        },
        "formats": formats,
        "duplicates": duplicates,
        "signals": signals,
        "policy": policy_summary,
    }
    return AuditResult(
        summary=_safe_summary(
            intended_use=intended_use,
            ready=ready,
            scan_completed=True,
            reason_codes=ordered_reasons,
        ),
        report=report,
    )


def read_private_policy(
    path: Path,
    *,
    max_bytes: int = 16 * 1024 * 1024,
) -> dict[str, Any]:
    """Read one private policy without following any path symlink."""

    if max_bytes < 1:
        raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
    parent, name = _split_absolute_file(path)
    pinned = _open_pinned_directory(parent, private_target=True)
    descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        expected = os.stat(name, dir_fd=pinned.descriptor, follow_symlinks=False)
        if stat.S_ISLNK(expected.st_mode):
            raise PrivateReadinessError("SYMLINK_PRESENT")
        descriptor = os.open(name, flags, dir_fd=pinned.descriptor)
        opened = os.fstat(descriptor)
        if _fingerprint(opened) != _fingerprint(expected):
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
        _validate_private_file(
            opened,
            descriptor,
            root_device=os.fstat(pinned.descriptor).st_dev,
        )
        if opened.st_size < 1 or opened.st_size > max_bytes:
            raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
        raw = _read_exact_descriptor(descriptor, opened.st_size, 1024 * 1024)
        after = os.fstat(descriptor)
        namespace_after = os.stat(
            name,
            dir_fd=pinned.descriptor,
            follow_symlinks=False,
        )
        if _fingerprint(after) != _fingerprint(opened) or _fingerprint(
            namespace_after
        ) != _fingerprint(opened):
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
        _verify_pinned_directory(pinned)
        value = _strict_json(raw, AuditLimits())
        if not isinstance(value, dict):
            raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
        return value
    except PrivateReadinessError:
        raise
    except _StructuredResourceLimit:
        raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED") from None
    except (OSError, ValueError, UnicodeError):
        raise PrivateReadinessError("INPUT_UNREADABLE_OR_UNVERIFIABLE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        _close_pinned_directory(pinned)


def _safe_summary(
    *,
    intended_use: str,
    ready: bool,
    scan_completed: bool,
    reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "claim_class": CLAIM_CLASS,
        "intended_use": intended_use,
        "ready": ready,
        "scan_completed": scan_completed,
        "reason_codes": list(reason_codes),
        "assurance": dict(ASSURANCE),
    }


def _validate_created_at(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise PrivateReadinessError("POLICY_DOCUMENT_INVALID") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")


def _validate_limits(limits: AuditLimits) -> None:
    values = (
        limits.max_files,
        limits.max_directories,
        limits.max_depth,
        limits.max_component_bytes,
        limits.max_path_bytes,
        limits.max_file_bytes,
        limits.max_total_bytes,
        limits.max_structured_bytes,
        limits.max_csv_bytes,
        limits.max_json_nodes,
        limits.max_json_depth,
        limits.max_csv_rows,
        limits.max_csv_columns,
        limits.max_csv_record_bytes,
        limits.max_anomalies,
        limits.read_chunk_bytes,
    )
    if any(type(value) is not int or value < 1 for value in values):
        raise PrivateReadinessError("INTERNAL_ERROR")
    if (
        limits.max_structured_bytes > limits.max_file_bytes
        or limits.max_csv_bytes > limits.max_file_bytes
        or limits.max_csv_record_bytes > limits.max_csv_bytes
        or limits.max_json_depth > _MAX_CONFIGURED_JSON_DEPTH
    ):
        raise PrivateReadinessError("INTERNAL_ERROR")


def _stable_snapshot(
    root: Path,
    *,
    key: bytes,
    limits: AuditLimits,
) -> _Snapshot:
    """Return one complete, stable, descriptor-relative private inventory."""

    first = _scan_once(root, key=key, limits=limits)
    second = _scan_once(root, key=key, limits=limits)
    if first != second:
        raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
    return first


def _require_platform() -> None:
    missing = []
    for constant in ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"):
        if not getattr(os, constant, 0):
            missing.append(constant)
    if os.open not in os.supports_dir_fd:
        missing.append("openat")
    if os.stat not in os.supports_dir_fd or os.stat not in os.supports_follow_symlinks:
        missing.append("fstatat")
    if os.scandir not in os.supports_fd:
        missing.append("fd-scandir")
    if missing or os.name != "posix":
        raise PrivateReadinessError("PLATFORM_UNSUPPORTED")


def _fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _directory_identity(metadata: os.stat_result) -> tuple[int, ...]:
    """Pin ancestry without treating unrelated sibling changes as a root swap."""

    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
    )


def _split_absolute_file(path: Path) -> tuple[Path, str]:
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")
    return path.parent, path.name


def _open_pinned_directory(path: Path, *, private_target: bool) -> _PinnedDirectory:
    _require_platform()
    if not path.is_absolute() or path == Path(path.anchor):
        raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")
    components = path.parts[1:]
    if not components or any(component in {"", ".", ".."} for component in components):
        raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")

    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptors: list[int] = []
    names: list[str] = []
    fingerprints: list[tuple[int, ...]] = []
    try:
        descriptor = os.open(path.anchor, flags)
        descriptors.append(descriptor)
        root_metadata = os.fstat(descriptor)
        fingerprints.append(_directory_identity(root_metadata))
        effective_uid = os.geteuid()
        for index, component in enumerate(components):
            _validate_component(component, 255)
            child = os.open(component, flags, dir_fd=descriptors[-1])
            metadata = os.fstat(child)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child)
                raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")
            mode = stat.S_IMODE(metadata.st_mode)
            root_owned_sticky_boundary = metadata.st_uid == 0 and bool(
                metadata.st_mode & stat.S_ISVTX
            )
            if metadata.st_uid not in {0, effective_uid} or (
                mode & 0o022 and not root_owned_sticky_boundary
            ):
                os.close(child)
                raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")
            descriptors.append(child)
            names.append(component)
            fingerprints.append(_directory_identity(metadata))
            if index == len(components) - 1 and private_target:
                if metadata.st_uid != effective_uid or stat.S_IMODE(metadata.st_mode) != 0o700:
                    raise PrivateReadinessError("PERMISSION_BOUNDARY_INVALID")
                _require_acl_free(child)
        return _PinnedDirectory(
            descriptors=tuple(descriptors),
            names=tuple(names),
            fingerprints=tuple(fingerprints),
        )
    except PrivateReadinessError:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise
    except OSError:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise PrivateReadinessError("ROOT_BOUNDARY_INVALID") from None


def _verify_pinned_directory(pinned: _PinnedDirectory) -> None:
    if len(pinned.descriptors) != len(pinned.fingerprints):
        raise PrivateReadinessError("INTERNAL_ERROR")
    for index, descriptor in enumerate(pinned.descriptors):
        if _directory_identity(os.fstat(descriptor)) != pinned.fingerprints[index]:
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
        if index == 0:
            continue
        namespace = os.stat(
            pinned.names[index - 1],
            dir_fd=pinned.descriptors[index - 1],
            follow_symlinks=False,
        )
        if _directory_identity(namespace) != pinned.fingerprints[index]:
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")


def _close_pinned_directory(pinned: _PinnedDirectory) -> None:
    for descriptor in reversed(pinned.descriptors):
        with suppress(OSError):
            os.close(descriptor)


def _scan_once(root: Path, *, key: bytes, limits: AuditLimits) -> _Snapshot:
    pinned = _open_pinned_directory(root, private_target=True)
    try:
        root_metadata = os.fstat(pinned.descriptor)
        state = _ScanState(
            key=key,
            limits=limits,
            root_device=root_metadata.st_dev,
            effective_uid=os.geteuid(),
            files=[],
            namespaces=[
                (
                    _opaque_token(key, b"path", b"."),
                    _fingerprint(root_metadata),
                )
            ],
            collision_paths=set(),
            inodes={(root_metadata.st_dev, root_metadata.st_ino)},
        )
        _walk_directory(
            pinned.descriptor,
            prefix="",
            depth=0,
            state=state,
        )
        _require_acl_free(pinned.descriptor)
        _verify_pinned_directory(pinned)
        return _Snapshot(
            files=tuple(sorted(state.files, key=lambda item: item.path_token)),
            namespaces=tuple(sorted(state.namespaces, key=lambda item: item[0])),
            root_identity=_directory_identity(root_metadata),
            directory_count=state.directory_count,
            total_bytes=state.total_bytes,
        )
    except PrivateReadinessError:
        raise
    except OSError:
        raise PrivateReadinessError("INPUT_UNREADABLE_OR_UNVERIFIABLE") from None
    finally:
        _close_pinned_directory(pinned)


def _walk_directory(
    descriptor: int,
    *,
    prefix: str,
    depth: int,
    state: _ScanState,
) -> None:
    before = os.fstat(descriptor)
    if not stat.S_ISDIR(before.st_mode):
        raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
    _validate_private_directory(before, descriptor, root_device=state.root_device)
    try:
        children: list[tuple[str, os.stat_result]] = []
        with os.scandir(descriptor) as iterator:
            for entry in iterator:
                if len(children) + len(state.files) + state.directory_count > (
                    state.limits.max_files + state.limits.max_directories
                ):
                    raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
                children.append((entry.name, entry.stat(follow_symlinks=False)))
    except PrivateReadinessError:
        raise
    except OSError:
        raise PrivateReadinessError("INPUT_UNREADABLE_OR_UNVERIFIABLE") from None
    if _fingerprint(os.fstat(descriptor)) != _fingerprint(before):
        raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")

    prepared: list[tuple[str, str, os.stat_result]] = []
    for name, metadata in children:
        if depth + 1 > state.limits.max_depth:
            raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
        _validate_component(name, state.limits.max_component_bytes)
        logical_path = f"{prefix}/{name}" if prefix else name
        encoded_path = _validate_relative_path(
            logical_path,
            max_component_bytes=state.limits.max_component_bytes,
            max_path_bytes=state.limits.max_path_bytes,
        )
        collision = _collision_key(logical_path)
        if collision in state.collision_paths:
            raise PrivateReadinessError("PATH_PROFILE_INVALID_OR_COLLISION")
        state.collision_paths.add(collision)
        path_token = _opaque_token(state.key, b"path", encoded_path)
        prepared.append((name, logical_path, metadata))
        if stat.S_ISLNK(metadata.st_mode):
            raise PrivateReadinessError("SYMLINK_PRESENT")
        if metadata.st_dev != state.root_device:
            raise PrivateReadinessError("CROSS_DEVICE_ENTRY")
        inode = (metadata.st_dev, metadata.st_ino)
        if inode in state.inodes:
            raise PrivateReadinessError("HARDLINK_OR_DUPLICATE_INODE")
        state.inodes.add(inode)
        if stat.S_ISDIR(metadata.st_mode):
            if state.directory_count >= state.limits.max_directories:
                raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
            state.directory_count += 1
            state.namespaces.append((path_token, _fingerprint(metadata)))
        elif not stat.S_ISREG(metadata.st_mode):
            raise PrivateReadinessError("SPECIAL_OR_UNSUPPORTED_ENTRY")

    prepared.sort(key=lambda item: os.fsencode(item[0]))
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    for name, logical_path, expected in prepared:
        if stat.S_ISDIR(expected.st_mode):
            child_descriptor: int | None = None
            try:
                child_descriptor = os.open(name, directory_flags, dir_fd=descriptor)
                opened = os.fstat(child_descriptor)
                if _fingerprint(opened) != _fingerprint(expected):
                    raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
                _validate_private_directory(
                    opened,
                    child_descriptor,
                    root_device=state.root_device,
                )
                _walk_directory(
                    child_descriptor,
                    prefix=logical_path,
                    depth=depth + 1,
                    state=state,
                )
                if _fingerprint(os.fstat(child_descriptor)) != _fingerprint(opened):
                    raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
                _require_acl_free(child_descriptor)
            except PrivateReadinessError:
                raise
            except OSError:
                raise PrivateReadinessError("INPUT_UNREADABLE_OR_UNVERIFIABLE") from None
            finally:
                if child_descriptor is not None:
                    os.close(child_descriptor)
        else:
            _observe_file(
                descriptor,
                name=name,
                logical_path=logical_path,
                expected=expected,
                state=state,
            )

    for name, _logical_path, expected in prepared:
        try:
            current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except OSError:
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED") from None
        if _fingerprint(current) != _fingerprint(expected):
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
    if _fingerprint(os.fstat(descriptor)) != _fingerprint(before):
        raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
    _require_acl_free(descriptor)


def _observe_file(
    parent_descriptor: int,
    *,
    name: str,
    logical_path: str,
    expected: os.stat_result,
    state: _ScanState,
) -> None:
    if len(state.files) >= state.limits.max_files:
        raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
    if expected.st_nlink != 1:
        raise PrivateReadinessError("HARDLINK_OR_DUPLICATE_INODE")
    if expected.st_size < 0 or expected.st_size > state.limits.max_file_bytes:
        raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
    if state.total_bytes + expected.st_size > state.limits.max_total_bytes:
        raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")

    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor: int | None = None
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
        if _fingerprint(opened) != _fingerprint(expected):
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
        _validate_private_file(opened, descriptor, root_device=state.root_device)
        digest = hmac.new(state.key, b"content\x00", hashlib.sha256)
        content_sha256 = hashlib.sha256()
        prefix = bytearray()
        tail = b""
        byte_count = 0
        while True:
            chunk = os.read(descriptor, state.limits.read_chunk_bytes)
            if not chunk:
                break
            digest.update(chunk)
            content_sha256.update(chunk)
            if len(prefix) < 65_536:
                prefix.extend(chunk[: 65_536 - len(prefix)])
            tail = (tail + chunk)[-4:]
            byte_count += len(chunk)
            if (
                byte_count > state.limits.max_file_bytes
                or state.total_bytes + byte_count > state.limits.max_total_bytes
            ):
                raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
        after_hash = os.fstat(descriptor)
        if _fingerprint(after_hash) != _fingerprint(opened) or byte_count != opened.st_size:
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
        analysis = _analyze_file(
            descriptor,
            name=name,
            byte_count=byte_count,
            prefix=bytes(prefix),
            tail=tail,
            limits=state.limits,
            anomaly_budget=max(
                state.limits.max_anomalies - state.recorded_anomalies,
                0,
            ),
        )
        state.recorded_anomalies += len(analysis.anomalies)
        after_analysis = os.fstat(descriptor)
        namespace_after = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if _fingerprint(after_analysis) != _fingerprint(opened) or _fingerprint(
            namespace_after
        ) != _fingerprint(opened):
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
        _require_acl_free(descriptor)
        state.files.append(
            _FileObservation(
                relative_path=logical_path,
                path_token=_opaque_token(
                    state.key,
                    b"path",
                    logical_path.encode("utf-8"),
                ),
                content_token=digest.digest(),
                content_sha256=content_sha256.digest(),
                byte_count=byte_count,
                fingerprint=_fingerprint(opened),
                analysis=analysis,
            )
        )
        state.total_bytes += byte_count
    except PrivateReadinessError:
        raise
    except OSError:
        raise PrivateReadinessError("INPUT_UNREADABLE_OR_UNVERIFIABLE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _validate_private_directory(
    metadata: os.stat_result,
    descriptor: int,
    *,
    root_device: int,
) -> None:
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_dev != root_device
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise PrivateReadinessError("PERMISSION_BOUNDARY_INVALID")
    _require_acl_free(descriptor)


def _validate_private_file(
    metadata: os.stat_result,
    descriptor: int,
    *,
    root_device: int,
) -> None:
    if metadata.st_nlink != 1:
        raise PrivateReadinessError("HARDLINK_OR_DUPLICATE_INODE")
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_dev != root_device
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise PrivateReadinessError("PERMISSION_BOUNDARY_INVALID")
    _require_acl_free(descriptor)


def _require_acl_free(descriptor: int) -> None:
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            acl_get_fd = libc.acl_get_fd_np
            acl_free = libc.acl_free
        except AttributeError:
            raise PrivateReadinessError("ACL_UNVERIFIABLE_OR_PRESENT") from None
        acl_get_fd.argtypes = [ctypes.c_int, ctypes.c_int]
        acl_get_fd.restype = ctypes.c_void_p
        acl_free.argtypes = [ctypes.c_void_p]
        acl_free.restype = ctypes.c_int
        ctypes.set_errno(0)
        acl = acl_get_fd(descriptor, 0x00000100)
        if not acl:
            if ctypes.get_errno() == errno.ENOENT:
                return
            raise PrivateReadinessError("ACL_UNVERIFIABLE_OR_PRESENT")
        try:
            raise PrivateReadinessError("ACL_UNVERIFIABLE_OR_PRESENT")
        finally:
            acl_free(acl)
    if os.name != "posix" or not hasattr(os, "listxattr"):
        raise PrivateReadinessError("ACL_UNVERIFIABLE_OR_PRESENT")
    try:
        names = os.listxattr(descriptor)
    except OSError:
        raise PrivateReadinessError("ACL_UNVERIFIABLE_OR_PRESENT") from None
    if any(
        name
        in {
            "system.posix_acl_access",
            "system.posix_acl_default",
            b"system.posix_acl_access",
            b"system.posix_acl_default",
        }
        for name in names
    ):
        raise PrivateReadinessError("ACL_UNVERIFIABLE_OR_PRESENT")


def _validate_component(component: str, max_bytes: int) -> None:
    if component in {"", ".", ".."} or "/" in component or "\x00" in component:
        raise PrivateReadinessError("PATH_PROFILE_INVALID_OR_COLLISION")
    try:
        encoded = component.encode("utf-8")
    except UnicodeError:
        raise PrivateReadinessError("PATH_PROFILE_INVALID_OR_COLLISION") from None
    if len(encoded) > max_bytes or any(
        ord(character) < 32 or ord(character) == 127 or unicodedata.category(character) == "Cf"
        for character in component
    ):
        raise PrivateReadinessError("PATH_PROFILE_INVALID_OR_COLLISION")


def _validate_relative_path(
    value: str,
    *,
    max_component_bytes: int,
    max_path_bytes: int,
) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
    ):
        raise PrivateReadinessError("PATH_PROFILE_INVALID_OR_COLLISION")
    parts = value.split("/")
    for component in parts:
        _validate_component(component, max_component_bytes)
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise PrivateReadinessError("PATH_PROFILE_INVALID_OR_COLLISION") from None
    if len(encoded) > max_path_bytes:
        raise PrivateReadinessError("RESOURCE_LIMIT_EXCEEDED")
    return encoded


def _collision_key(value: str) -> str:
    return unicodedata.normalize(
        "NFKC",
        unicodedata.normalize("NFKC", value).casefold(),
    )


def _opaque_token(key: bytes, domain: bytes, value: bytes) -> bytes:
    return hmac.new(key, domain + b"\x00" + value, hashlib.sha256).digest()


def _read_exact_descriptor(descriptor: int, byte_count: int, chunk_size: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = byte_count
    while remaining:
        chunk = os.read(descriptor, min(chunk_size, remaining))
        if not chunk:
            raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(descriptor, 1):
        raise PrivateReadinessError("CONCURRENT_MUTATION_DETECTED")
    return b"".join(chunks)


def _analyze_file(
    descriptor: int,
    *,
    name: str,
    byte_count: int,
    prefix: bytes,
    tail: bytes,
    limits: AuditLimits,
    anomaly_budget: int,
) -> _FileAnalysis:
    suffix = Path(name).suffix.casefold()
    if prefix.startswith(b"\xff\xd8\xff"):
        return _FileAnalysis("jpeg", tail.endswith(b"\xff\xd9"))
    if prefix.startswith((b"II*\x00", b"MM\x00*")):
        valid = len(prefix) >= 8
        if valid:
            byte_order = "little" if prefix.startswith(b"II") else "big"
            first_ifd = int.from_bytes(prefix[4:8], byte_order)
            valid = first_ifd == 0 or 8 <= first_ifd < byte_count
        return _FileAnalysis("tiff", valid)

    if suffix == ".csv":
        return _analyze_csv(
            descriptor,
            byte_count=byte_count,
            prefix=prefix,
            limits=limits,
            anomaly_budget=anomaly_budget,
        )
    if suffix == ".json":
        return _analyze_json_document(
            descriptor,
            byte_count,
            limits,
            anomaly_budget=anomaly_budget,
        )
    if suffix in {".jsonl", ".ndjson"}:
        return _analyze_json_lines(
            descriptor,
            byte_count,
            limits,
            anomaly_budget=anomaly_budget,
        )

    if byte_count > limits.max_structured_bytes:
        return _FileAnalysis("unknown_binary", False)
    raw = _read_exact_descriptor(descriptor, byte_count, limits.read_chunk_bytes)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _FileAnalysis("unknown_binary", False)
    stripped = text.lstrip()
    if suffix in {".html", ".htm"} or stripped[:32].casefold().startswith(
        ("<!doctype html", "<html")
    ):
        return _FileAnalysis("html", True)
    if stripped.startswith(("{", "[")):
        try:
            value = _strict_json(raw, limits)
        except _StructuredResourceLimit:
            return _invalid_structured_analysis(
                "json",
                "JSON_COMPLEXITY_LIMIT_EXCEEDED",
                anomaly_budget=anomaly_budget,
                anomaly_enumeration_complete=False,
            )
        except _FormatInvalid:
            try:
                return _json_lines_from_raw(raw, limits)
            except _StructuredResourceLimit:
                return _invalid_structured_analysis(
                    "jsonl",
                    "JSON_COMPLEXITY_LIMIT_EXCEEDED",
                    anomaly_budget=anomaly_budget,
                    anomaly_enumeration_complete=False,
                )
            except _FormatInvalid:
                return _FileAnalysis("plain_text", True)
        return _FileAnalysis("json", True, structured_records=_json_record_count(value))
    return _FileAnalysis("plain_text", True)


def _analyze_json_document(
    descriptor: int,
    byte_count: int,
    limits: AuditLimits,
    *,
    anomaly_budget: int,
) -> _FileAnalysis:
    if byte_count > limits.max_structured_bytes:
        return _invalid_structured_analysis(
            "json",
            "STRUCTURED_DOCUMENT_TOO_LARGE",
            anomaly_budget=anomaly_budget,
            anomaly_enumeration_complete=False,
        )
    raw = _read_exact_descriptor(descriptor, byte_count, limits.read_chunk_bytes)
    if raw.startswith(b"\xef\xbb\xbf"):
        return _invalid_structured_analysis(
            "json",
            "UTF8_BOM_PRESENT",
            anomaly_budget=anomaly_budget,
        )
    if b"\x00" in raw:
        return _invalid_structured_analysis(
            "json",
            "NUL_BYTE_PRESENT",
            anomaly_budget=anomaly_budget,
        )
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return _invalid_structured_analysis(
            "json",
            "INVALID_UTF8",
            anomaly_budget=anomaly_budget,
        )
    try:
        value = _strict_json(raw, limits)
    except _StructuredResourceLimit:
        return _invalid_structured_analysis(
            "json",
            "JSON_COMPLEXITY_LIMIT_EXCEEDED",
            anomaly_budget=anomaly_budget,
            anomaly_enumeration_complete=False,
        )
    except _FormatInvalid:
        return _invalid_structured_analysis(
            "json",
            "JSON_DOCUMENT_INVALID",
            anomaly_budget=anomaly_budget,
        )
    return _FileAnalysis("json", True, structured_records=_json_record_count(value))


def _analyze_json_lines(
    descriptor: int,
    byte_count: int,
    limits: AuditLimits,
    *,
    anomaly_budget: int,
) -> _FileAnalysis:
    if byte_count > limits.max_structured_bytes:
        return _invalid_structured_analysis(
            "jsonl",
            "STRUCTURED_DOCUMENT_TOO_LARGE",
            anomaly_budget=anomaly_budget,
            anomaly_enumeration_complete=False,
        )
    raw = _read_exact_descriptor(descriptor, byte_count, limits.read_chunk_bytes)
    if raw.startswith(b"\xef\xbb\xbf"):
        return _invalid_structured_analysis(
            "jsonl",
            "UTF8_BOM_PRESENT",
            anomaly_budget=anomaly_budget,
        )
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return _invalid_structured_analysis(
            "jsonl",
            "INVALID_UTF8",
            anomaly_budget=anomaly_budget,
        )

    anomalies: list[_StructureAnomaly] = []
    complete = True
    records = 0
    for record_number, line in _iter_json_lines(raw):
        if record_number > limits.max_json_nodes:
            _append_anomaly(
                anomalies,
                _StructureAnomaly(
                    "JSONL_RECORD_LIMIT_EXCEEDED",
                    record_number=record_number,
                ),
                budget=anomaly_budget,
            )
            complete = False
            break
        if not line.strip():
            continue
        if b"\x00" in line:
            complete = (
                _append_anomaly(
                    anomalies,
                    _StructureAnomaly("NUL_BYTE_PRESENT", record_number=record_number),
                    budget=anomaly_budget,
                )
                and complete
            )
            continue
        try:
            value = _strict_json(line, limits)
        except _StructuredResourceLimit:
            _append_anomaly(
                anomalies,
                _StructureAnomaly(
                    "JSON_COMPLEXITY_LIMIT_EXCEEDED",
                    record_number=record_number,
                ),
                budget=anomaly_budget,
            )
            complete = False
            break
        except _FormatInvalid:
            complete = (
                _append_anomaly(
                    anomalies,
                    _StructureAnomaly("JSONL_RECORD_INVALID", record_number=record_number),
                    budget=anomaly_budget,
                )
                and complete
            )
            continue
        if not isinstance(value, Mapping):
            complete = (
                _append_anomaly(
                    anomalies,
                    _StructureAnomaly("JSONL_RECORD_NOT_OBJECT", record_number=record_number),
                    budget=anomaly_budget,
                )
                and complete
            )
            continue
        records += 1
        if records > limits.max_json_nodes:
            _append_anomaly(
                anomalies,
                _StructureAnomaly(
                    "JSONL_RECORD_LIMIT_EXCEEDED",
                    record_number=record_number,
                ),
                budget=anomaly_budget,
            )
            complete = False
            break
    if records == 0 and not anomalies:
        complete = (
            _append_anomaly(
                anomalies,
                _StructureAnomaly("JSONL_EMPTY_DOCUMENT"),
                budget=anomaly_budget,
            )
            and complete
        )
    return _FileAnalysis(
        "jsonl",
        not anomalies and complete,
        structured_records=records,
        anomalies=tuple(anomalies),
        anomaly_enumeration_complete=complete,
    )


def _invalid_structured_analysis(
    format_name: str,
    code: str,
    *,
    anomaly_budget: int,
    anomaly_enumeration_complete: bool = True,
) -> _FileAnalysis:
    anomalies: list[_StructureAnomaly] = []
    recorded = _append_anomaly(
        anomalies,
        _StructureAnomaly(code),
        budget=anomaly_budget,
    )
    return _FileAnalysis(
        format_name,
        False,
        anomalies=tuple(anomalies),
        anomaly_enumeration_complete=(recorded and anomaly_enumeration_complete),
    )


def _append_anomaly(
    anomalies: list[_StructureAnomaly],
    anomaly: _StructureAnomaly,
    *,
    budget: int,
) -> bool:
    if anomaly.code not in STRUCTURE_ANOMALY_CODES:
        raise PrivateReadinessError("INTERNAL_ERROR")
    if budget < 1:
        return False
    if len(anomalies) < budget:
        anomalies.append(anomaly)
        return True
    anomalies[-1] = _StructureAnomaly("ANOMALY_LIMIT_EXCEEDED")
    return False


def _json_lines_from_raw(raw: bytes, limits: AuditLimits) -> _FileAnalysis:
    records = 0
    for record_number, line in _iter_json_lines(raw):
        if record_number > limits.max_json_nodes:
            raise _StructuredResourceLimit
        if not line.strip():
            continue
        value = _strict_json(line, limits)
        if not isinstance(value, Mapping):
            raise _FormatInvalid
        records += 1
        if records > limits.max_json_nodes:
            raise _StructuredResourceLimit
    if records < 1:
        raise _FormatInvalid
    return _FileAnalysis("jsonl", True, structured_records=records)


def _iter_json_lines(raw: bytes) -> Iterator[tuple[int, bytes]]:
    """Yield CR, LF, or CRLF-delimited records without materializing a list."""

    start = 0
    record_number = 1
    for separator in _JSON_LINE_SEPARATOR.finditer(raw):
        yield record_number, raw[start : separator.start()]
        start = separator.end()
        record_number += 1
    if start < len(raw):
        yield record_number, raw if start == 0 else raw[start:]


class _JsonStructurePreflight:
    """Validate JSON structure and bounds before object materialization."""

    _WHITESPACE = frozenset({0x09, 0x0A, 0x0D, 0x20})
    _HEX = frozenset(b"0123456789abcdefABCDEF")

    def __init__(self, raw: bytes, limits: AuditLimits) -> None:
        self.raw = raw
        self.limits = limits
        self.position = 0
        self.nodes = 0

    def run(self) -> None:
        self._skip_whitespace()
        self._parse_value(depth=0)
        self._skip_whitespace()
        if self.position != len(self.raw):
            raise _FormatInvalid

    def _parse_value(self, *, depth: int) -> None:
        self.nodes += 1
        if self.nodes > self.limits.max_json_nodes or depth > self.limits.max_json_depth:
            raise _StructuredResourceLimit
        if self.position >= len(self.raw):
            raise _FormatInvalid
        marker = self.raw[self.position]
        if marker == 0x7B:
            self._parse_object(depth=depth)
        elif marker == 0x5B:
            self._parse_array(depth=depth)
        elif marker == 0x22:
            self._parse_string()
        elif marker == 0x74:
            self._parse_literal(b"true")
        elif marker == 0x66:
            self._parse_literal(b"false")
        elif marker == 0x6E:
            self._parse_literal(b"null")
        elif marker == 0x2D or 0x30 <= marker <= 0x39:
            self._parse_number()
        else:
            raise _FormatInvalid

    def _parse_object(self, *, depth: int) -> None:
        self.position += 1
        self._skip_whitespace()
        if self._consume_if(0x7D):
            return
        while True:
            if self.position >= len(self.raw) or self.raw[self.position] != 0x22:
                raise _FormatInvalid
            self._parse_string()
            self._skip_whitespace()
            self._require(0x3A)
            self._skip_whitespace()
            self._parse_value(depth=depth + 1)
            self._skip_whitespace()
            if self._consume_if(0x7D):
                return
            self._require(0x2C)
            self._skip_whitespace()

    def _parse_array(self, *, depth: int) -> None:
        self.position += 1
        self._skip_whitespace()
        if self._consume_if(0x5D):
            return
        while True:
            self._parse_value(depth=depth + 1)
            self._skip_whitespace()
            if self._consume_if(0x5D):
                return
            self._require(0x2C)
            self._skip_whitespace()

    def _parse_string(self) -> None:
        self._require(0x22)
        while self.position < len(self.raw):
            marker = self.raw[self.position]
            self.position += 1
            if marker == 0x22:
                return
            if marker < 0x20:
                raise _FormatInvalid
            if marker != 0x5C:
                continue
            if self.position >= len(self.raw):
                raise _FormatInvalid
            escaped = self.raw[self.position]
            self.position += 1
            if escaped in b'"\\/bfnrt':
                continue
            if escaped != 0x75 or self.position + 4 > len(self.raw):
                raise _FormatInvalid
            if any(digit not in self._HEX for digit in self.raw[self.position : self.position + 4]):
                raise _FormatInvalid
            self.position += 4
        raise _FormatInvalid

    def _parse_literal(self, expected: bytes) -> None:
        if self.raw[self.position : self.position + len(expected)] != expected:
            raise _FormatInvalid
        self.position += len(expected)

    def _parse_number(self) -> None:
        start = self.position
        if self._consume_if(0x2D) and self.position >= len(self.raw):
            raise _FormatInvalid
        if self._consume_if(0x30):
            if self.position < len(self.raw) and 0x30 <= self.raw[self.position] <= 0x39:
                raise _FormatInvalid
        elif self.position < len(self.raw) and 0x31 <= self.raw[self.position] <= 0x39:
            self.position += 1
            self._consume_digits()
        else:
            raise _FormatInvalid
        if self._consume_if(0x2E) and not self._consume_digits(require_one=True):
            raise _FormatInvalid
        if self.position < len(self.raw) and self.raw[self.position] in {0x45, 0x65}:
            self.position += 1
            if self.position < len(self.raw) and self.raw[self.position] in {
                0x2B,
                0x2D,
            }:
                self.position += 1
            if not self._consume_digits(require_one=True):
                raise _FormatInvalid
        if self.position - start > _MAX_JSON_NUMBER_BYTES:
            raise _StructuredResourceLimit

    def _consume_digits(self, *, require_one: bool = False) -> bool:
        start = self.position
        while self.position < len(self.raw) and 0x30 <= self.raw[self.position] <= 0x39:
            self.position += 1
        consumed = self.position > start
        return consumed or not require_one

    def _skip_whitespace(self) -> None:
        while self.position < len(self.raw) and self.raw[self.position] in self._WHITESPACE:
            self.position += 1

    def _consume_if(self, marker: int) -> bool:
        if self.position < len(self.raw) and self.raw[self.position] == marker:
            self.position += 1
            return True
        return False

    def _require(self, marker: int) -> None:
        if not self._consume_if(marker):
            raise _FormatInvalid


def _strict_json(raw: bytes, limits: AuditLimits) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise _FormatInvalid
    _JsonStructurePreflight(raw, limits).run()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _FormatInvalid from None

    def duplicate_checked(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _FormatInvalid
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise _FormatInvalid

    try:
        value = json.loads(
            text,
            object_pairs_hook=duplicate_checked,
            parse_float=decimal.Decimal,
            parse_constant=reject_constant,
        )
    except _FormatInvalid:
        raise
    except (json.JSONDecodeError, decimal.InvalidOperation):
        raise _FormatInvalid from None
    except (RecursionError, ValueError):
        raise _StructuredResourceLimit from None
    _check_json_complexity(value, limits)
    return value


def _check_json_complexity(value: object, limits: AuditLimits) -> None:
    pending: list[tuple[object, int]] = [(value, 0)]
    seen: set[int] = set()
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        if nodes > limits.max_json_nodes or depth > limits.max_json_depth:
            raise _StructuredResourceLimit
        if isinstance(current, Mapping):
            identity = id(current)
            if identity in seen:
                raise _FormatInvalid
            seen.add(identity)
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            identity = id(current)
            if identity in seen:
                raise _FormatInvalid
            seen.add(identity)
            pending.extend((child, depth + 1) for child in current)


def _json_record_count(value: object) -> int:
    return len(value) if isinstance(value, list) else 1


def _preflight_csv_structure(
    descriptor: int,
    limits: AuditLimits,
) -> _StructureAnomaly | None:
    """Bound logical CSV records before ``csv.reader`` materializes fields."""

    os.lseek(descriptor, 0, os.SEEK_SET)
    logical_record = 1
    record_bytes = 0
    delimiters = 0
    at_field_start = True
    in_quotes = False
    after_quote = False
    skip_lf_after_cr = False
    while True:
        chunk = os.read(descriptor, limits.read_chunk_bytes)
        if not chunk:
            return None
        for byte in chunk:
            if (
                skip_lf_after_cr
                and byte == 0x0A
                and not in_quotes
                and not after_quote
                and at_field_start
            ):
                skip_lf_after_cr = False
                continue
            skip_lf_after_cr = False
            record_bytes += 1
            if record_bytes > limits.max_csv_record_bytes:
                return _StructureAnomaly(
                    "CSV_RECORD_LIMIT_EXCEEDED",
                    record_number=logical_record,
                )

            if in_quotes:
                if byte == 0x22:
                    in_quotes = False
                    after_quote = True
                continue

            if after_quote:
                if byte == 0x22:
                    in_quotes = True
                    after_quote = False
                    continue
                after_quote = False

            if byte == 0x2C:
                delimiters += 1
                if delimiters >= limits.max_csv_columns:
                    return _StructureAnomaly(
                        "CSV_COLUMN_LIMIT_EXCEEDED",
                        record_number=logical_record,
                        observed_columns=delimiters + 1,
                    )
                at_field_start = True
                continue
            if byte in {0x0A, 0x0D}:
                logical_record += 1
                record_bytes = 0
                delimiters = 0
                at_field_start = True
                skip_lf_after_cr = byte == 0x0D
                continue
            if byte == 0x22 and at_field_start:
                in_quotes = True
            at_field_start = False


@contextmanager
def _bounded_csv_field_limit(limit: int) -> Iterator[None]:
    """Pin and restore Python's process-global CSV field limit."""

    with _CSV_FIELD_LIMIT_LOCK:
        previous = csv.field_size_limit()
        try:
            csv.field_size_limit(limit)
            yield
        finally:
            csv.field_size_limit(previous)


def _analyze_csv(
    descriptor: int,
    *,
    byte_count: int,
    prefix: bytes,
    limits: AuditLimits,
    anomaly_budget: int,
) -> _FileAnalysis:
    if byte_count > limits.max_csv_bytes:
        return _invalid_structured_analysis(
            "csv",
            "STRUCTURED_DOCUMENT_TOO_LARGE",
            anomaly_budget=anomaly_budget,
            anomaly_enumeration_complete=False,
        )
    duplicate = os.dup(descriptor)
    rows = 0
    ragged = 0
    width: int | None = None
    anomalies: list[_StructureAnomaly] = []
    complete = True
    invalid = False
    try:
        if prefix.startswith(b"\xef\xbb\xbf"):
            invalid = True
            complete = (
                _append_anomaly(
                    anomalies,
                    _StructureAnomaly("UTF8_BOM_PRESENT", record_number=1),
                    budget=anomaly_budget,
                )
                and complete
            )
        preflight = _preflight_csv_structure(duplicate, limits)
        if preflight is not None:
            _append_anomaly(
                anomalies,
                preflight,
                budget=anomaly_budget,
            )
            return _FileAnalysis(
                "csv",
                False,
                anomalies=tuple(anomalies),
                anomaly_enumeration_complete=False,
            )
        os.lseek(duplicate, 0, os.SEEK_SET)
        with os.fdopen(duplicate, "rb") as binary:
            duplicate = -1
            with (
                _bounded_csv_field_limit(limits.max_csv_record_bytes),
                io.TextIOWrapper(
                    binary,
                    encoding="utf-8",
                    errors="strict",
                    newline="",
                ) as text,
            ):
                reader = csv.reader(text, strict=True)
                for row in reader:
                    rows += 1
                    if rows > limits.max_csv_rows:
                        invalid = True
                        complete = False
                        _append_anomaly(
                            anomalies,
                            _StructureAnomaly(
                                "CSV_ROW_LIMIT_EXCEEDED",
                                record_number=rows,
                            ),
                            budget=anomaly_budget,
                        )
                        break
                    if len(row) > limits.max_csv_columns:
                        invalid = True
                        complete = False
                        _append_anomaly(
                            anomalies,
                            _StructureAnomaly(
                                "CSV_COLUMN_LIMIT_EXCEEDED",
                                record_number=rows,
                                observed_columns=len(row),
                            ),
                            budget=anomaly_budget,
                        )
                        break
                    if any("\x00" in field for field in row):
                        invalid = True
                        complete = (
                            _append_anomaly(
                                anomalies,
                                _StructureAnomaly(
                                    "NUL_BYTE_PRESENT",
                                    record_number=rows,
                                ),
                                budget=anomaly_budget,
                            )
                            and complete
                        )
                    if width is None:
                        width = len(row)
                    elif len(row) != width:
                        ragged += 1
                        complete = (
                            _append_anomaly(
                                anomalies,
                                _StructureAnomaly(
                                    "CSV_ROW_WIDTH_MISMATCH",
                                    record_number=rows,
                                    expected_columns=width,
                                    observed_columns=len(row),
                                ),
                                budget=anomaly_budget,
                            )
                            and complete
                        )
        if rows == 0:
            invalid = True
            complete = (
                _append_anomaly(
                    anomalies,
                    _StructureAnomaly("CSV_EMPTY_DOCUMENT"),
                    budget=anomaly_budget,
                )
                and complete
            )
        return _FileAnalysis(
            "csv",
            not invalid,
            structured_records=max(rows - 1, 0),
            csv_rows=rows,
            ragged=ragged,
            anomalies=tuple(anomalies),
            anomaly_enumeration_complete=complete,
        )
    except UnicodeError:
        complete = (
            _append_anomaly(
                anomalies,
                _StructureAnomaly("INVALID_UTF8", record_number=rows + 1),
                budget=anomaly_budget,
            )
            and complete
        )
        return _FileAnalysis(
            "csv",
            False,
            csv_rows=rows,
            ragged=ragged,
            anomalies=tuple(anomalies),
            anomaly_enumeration_complete=False,
        )
    except (csv.Error, OSError):
        complete = (
            _append_anomaly(
                anomalies,
                _StructureAnomaly("CSV_PARSE_ERROR", record_number=rows + 1),
                budget=anomaly_budget,
            )
            and complete
        )
        return _FileAnalysis(
            "csv",
            False,
            csv_rows=rows,
            ragged=ragged,
            anomalies=tuple(anomalies),
            anomaly_enumeration_complete=False,
        )
    finally:
        if duplicate >= 0:
            os.close(duplicate)


def _format_summary(files: tuple[_FileObservation, ...]) -> dict[str, int]:
    counts = Counter(observation.analysis.format_name for observation in files)
    result = {name: counts.get(name, 0) for name in FORMAT_NAMES}
    result.update(
        {
            "parseable": sum(observation.analysis.parseable for observation in files),
            "invalid": sum(not observation.analysis.parseable for observation in files),
            "structured_records": sum(
                observation.analysis.structured_records for observation in files
            ),
            "csv_rows": sum(observation.analysis.csv_rows for observation in files),
            "ragged": sum(observation.analysis.ragged for observation in files),
        }
    )
    return result


def _duplicate_summary(files: tuple[_FileObservation, ...]) -> dict[str, int]:
    groups = Counter(observation.content_token for observation in files)
    duplicate_sizes = [count for count in groups.values() if count > 1]
    return {
        "duplicate_groups": len(duplicate_sizes),
        "duplicate_files": sum(duplicate_sizes),
    }


def _evaluate_policy(
    snapshot: _Snapshot,
    *,
    policy: Mapping[str, Any] | None,
    intended_use: str,
    source_registry: Mapping[str, Any] | None,
    quarantine_manifest: Mapping[str, Any] | None,
    key: bytes,
    limits: AuditLimits,
) -> tuple[dict[str, Any], dict[str, int], set[str]]:
    signals = {name: 0 for name in SIGNAL_NAMES}
    if policy is None:
        return (
            {
                "provided": False,
                "valid": False,
                "covered_files": 0,
                "uncovered_files": len(snapshot.files),
                "extra_entries": 0,
                "compatible_entries": 0,
                "blocking_entries": len(snapshot.files),
            },
            signals,
            {"RIGHTS_COVERAGE_INCOMPLETE"},
        )

    try:
        entries = _parse_policy(policy, key=key, limits=limits)
    except PrivateReadinessError:
        return (
            {
                "provided": True,
                "valid": False,
                "covered_files": 0,
                "uncovered_files": len(snapshot.files),
                "extra_entries": 0,
                "compatible_entries": 0,
                "blocking_entries": len(snapshot.files),
            },
            signals,
            {"POLICY_DOCUMENT_INVALID", "RIGHTS_COVERAGE_INCOMPLETE"},
        )

    for entry in entries:
        signals[f"{entry.provenance_status}_provenance"] += 1
        signals[f"{entry.rights_status}_rights"] += 1
        signals[f"{entry.rights_evidence_status}_rights_evidence"] += 1

    observation_by_token = {observation.path_token: observation for observation in snapshot.files}
    actual_tokens = set(observation_by_token)
    entry_by_token = {entry.path_token: entry for entry in entries}
    policy_tokens = set(entry_by_token)
    covered_tokens = actual_tokens & policy_tokens
    uncovered = actual_tokens - policy_tokens
    extra = policy_tokens - actual_tokens
    reasons: set[str] = set()
    if uncovered or extra:
        reasons.add("RIGHTS_COVERAGE_INCOMPLETE")

    quarantined_tokens: set[bytes] = set()
    source_rights: dict[str, tuple[str, bool]] = {}
    if source_registry is None or quarantine_manifest is None:
        quarantined_tokens = set(covered_tokens)
    else:
        try:
            source_rights = _source_rights_index(source_registry)
            adapters = []
            token_by_artifact: dict[str, bytes] = {}
            for index, token in enumerate(sorted(covered_tokens)):
                entry = entry_by_token[token]
                artifact_id = f"private:{index}"
                token_by_artifact[artifact_id] = token
                source_record: dict[str, Any] = {"source_id": entry.source_id}
                if entry.source_locator is not None:
                    source_record["locator"] = entry.source_locator
                if entry.source_revision is not None:
                    source_record["revision"] = entry.source_revision
                adapters.append(
                    {
                        "artifact_id": artifact_id,
                        "source_records": [source_record],
                        "images": [],
                    }
                )
            quarantine = inspect_corpus_quarantine(
                adapters,
                source_registry=source_registry,
                quarantine_manifest=quarantine_manifest,
                purpose="audit_only",
            )
            quarantined_tokens = {
                token_by_artifact[finding.artifact_id]
                for finding in quarantine.findings
                if finding.artifact_id in token_by_artifact
            }
        except (TypeError, ValueError):
            reasons.add("POLICY_DOCUMENT_INVALID")
            quarantined_tokens = set(covered_tokens)

    compatible = 0
    for token in covered_tokens:
        entry = entry_by_token[token]
        observation = observation_by_token[token]
        entry_compatible = True
        if not hmac.compare_digest(
            entry.content_sha256,
            observation.content_sha256,
        ):
            reasons.add("POLICY_CONTENT_BINDING_MISMATCH")
            entry_compatible = False
        if entry.curation_status != "reviewed":
            reasons.add("POLICY_REVIEW_INCOMPLETE")
            entry_compatible = False
        if token in quarantined_tokens:
            reasons.add("QUARANTINED_OR_UNKNOWN_SOURCE")
            entry_compatible = False
        registry_rights = source_rights.get(entry.source_id)
        if registry_rights is None or not _source_rights_compatible(
            entry,
            registry_status=registry_rights[0],
            derivatives_permitted=registry_rights[1],
            intended_use=intended_use,
        ):
            reasons.add("RIGHTS_AMBIGUOUS_OR_CONFLICTING")
            entry_compatible = False
        if entry.provenance_status != "documented":
            reasons.add("CONTENT_CONTRACT_INVALID")
            entry_compatible = False
        if entry.rights_evidence_status != "documented":
            reasons.add("RIGHTS_AMBIGUOUS_OR_CONFLICTING")
            entry_compatible = False
        if intended_use not in entry.permitted_uses:
            reasons.add("INTENDED_USE_NOT_PERMITTED")
            entry_compatible = False
        rights_compatible = entry.rights_status in {
            "public_domain",
            "open_licensed",
            "permission_granted",
        } or (
            entry.rights_status == "metadata_only" and entry.content_layer in _METADATA_ONLY_LAYERS
        )
        if not rights_compatible:
            reasons.add("RIGHTS_AMBIGUOUS_OR_CONFLICTING")
            entry_compatible = False
        if entry_compatible:
            compatible += 1

    blocking = len(snapshot.files) - compatible + len(extra)
    return (
        {
            "provided": True,
            "valid": "POLICY_DOCUMENT_INVALID" not in reasons,
            "covered_files": len(covered_tokens),
            "uncovered_files": len(uncovered),
            "extra_entries": len(extra),
            "compatible_entries": compatible,
            "blocking_entries": blocking,
        },
        signals,
        reasons,
    )


def _source_rights_index(
    source_registry: Mapping[str, Any],
) -> dict[str, tuple[str, bool]]:
    raw_sources = source_registry.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError
    result: dict[str, tuple[str, bool]] = {}
    for raw_source in raw_sources:
        if not isinstance(raw_source, Mapping):
            raise ValueError
        source_id = raw_source.get("source_id")
        rights = raw_source.get("rights")
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id in result
            or not isinstance(rights, Mapping)
            or not isinstance(rights.get("status"), str)
        ):
            raise ValueError
        result[source_id] = (
            str(rights["status"]),
            rights.get("derivatives") is True,
        )
    return result


def _source_rights_compatible(
    entry: _PolicyEntry,
    *,
    registry_status: str,
    derivatives_permitted: bool,
    intended_use: str,
) -> bool:
    allowed_policy_statuses = {
        "public_domain": {"public_domain", "metadata_only"},
        "open_licensed": {"open_licensed", "metadata_only"},
        "permission_granted": {"permission_granted", "metadata_only"},
        "metadata_only": {"metadata_only"},
    }.get(registry_status, set())
    if entry.rights_status not in allowed_policy_statuses:
        return False
    if registry_status == "metadata_only" and entry.content_layer not in _METADATA_ONLY_LAYERS:
        return False
    return intended_use != "local_nonpublic_normalization" or derivatives_permitted


def _parse_policy(
    policy: Mapping[str, Any],
    *,
    key: bytes,
    limits: AuditLimits,
) -> tuple[_PolicyEntry, ...]:
    if set(policy) != _POLICY_KEYS:
        raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
    if (
        policy.get("schema_version") != POLICY_SCHEMA_VERSION
        or policy.get("policy_kind") != "private_corpus_use_policy"
    ):
        raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
    raw_entries = policy.get("entries")
    if not isinstance(raw_entries, list) or not 1 <= len(raw_entries) <= limits.max_files:
        raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")

    result: list[_PolicyEntry] = []
    tokens: set[bytes] = set()
    collisions: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping) or set(raw_entry) != _ENTRY_KEYS:
            raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
        relative_path = raw_entry.get("relative_path")
        if not isinstance(relative_path, str):
            raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
        encoded_path = _validate_relative_path(
            relative_path,
            max_component_bytes=limits.max_component_bytes,
            max_path_bytes=limits.max_path_bytes,
        )
        collision = _collision_key(relative_path)
        token = _opaque_token(key, b"path", encoded_path)
        if collision in collisions or token in tokens:
            raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
        collisions.add(collision)
        tokens.add(token)

        content_layer = raw_entry.get("content_layer")
        content_sha256 = raw_entry.get("content_sha256")
        curation_status = raw_entry.get("curation_status")
        source_id = raw_entry.get("source_id")
        source_locator = raw_entry.get("source_locator")
        source_revision = raw_entry.get("source_revision")
        provenance_status = raw_entry.get("provenance_status")
        rights_status = raw_entry.get("rights_status")
        evidence_status = raw_entry.get("rights_evidence_status")
        permitted_uses = raw_entry.get("permitted_uses")
        if (
            not isinstance(content_sha256, str)
            or _SHA256.fullmatch(content_sha256) is None
            or curation_status not in _CURATION_STATUSES
            or not isinstance(content_layer, str)
            or content_layer not in _CONTENT_LAYERS
            or not isinstance(source_id, str)
            or _STABLE_ID.fullmatch(source_id) is None
            or (source_locator is not None and not isinstance(source_locator, str))
            or (
                isinstance(source_locator, str)
                and (not source_locator or len(source_locator) > 2000)
            )
            or (source_revision is not None and not isinstance(source_revision, str))
            or (
                isinstance(source_revision, str)
                and (not source_revision or len(source_revision) > 256)
            )
            or provenance_status not in _PROVENANCE_STATUSES
            or rights_status not in _RIGHTS_STATUSES
            or evidence_status not in _EVIDENCE_STATUSES
            or not isinstance(permitted_uses, list)
            or len(permitted_uses) > len(INTENDED_USES)
            or any(not isinstance(use, str) or use not in INTENDED_USES for use in permitted_uses)
            or len(set(permitted_uses)) != len(permitted_uses)
        ):
            raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
        result.append(
            _PolicyEntry(
                path_token=token,
                content_sha256=bytes.fromhex(content_sha256.removeprefix("sha256:")),
                curation_status=str(curation_status),
                content_layer=content_layer,
                source_id=source_id,
                source_locator=source_locator,
                source_revision=source_revision,
                provenance_status=str(provenance_status),
                rights_status=str(rights_status),
                rights_evidence_status=str(evidence_status),
                permitted_uses=frozenset(permitted_uses),
            )
        )
    return tuple(result)
