"""Build and publish a deny-all private corpus review bundle.

The bundle is deliberately private and contains exact relative paths and
content SHA-256 commitments.  Its terminal summary contains neither.  A
generated bundle grants no use, establishes no rights or provenance, and does
not modify the source corpus.
"""

from __future__ import annotations

import errno
import json
import os
import secrets
import stat
from contextlib import suppress
from dataclasses import dataclass, field
from importlib import resources  # nosemgrep
from pathlib import Path
from typing import Any

from indusbench.private_readiness import (
    ASSURANCE,
    POLICY_SCHEMA_VERSION,
    AuditLimits,
    PrivateReadinessError,
    _close_pinned_directory,
    _directory_identity,
    _fingerprint,
    _open_pinned_directory,
    _read_exact_descriptor,
    _require_acl_free,
    _stable_snapshot,
    _validate_component,
    _validate_created_at,
    _validate_limits,
    read_private_policy,
)
from indusbench.schema_validation import validate_schema_instance

STRUCTURAL_QUARANTINE_SCHEMA_VERSION = "0.1.0"
BUNDLE_SCHEMA_VERSION = "0.1.0"
PREPARATION_SCHEMA_VERSION = "0.1.0"
PARSER_CONTRACT = "indusbench.private-structured-records.v1"
MAX_POLICY_BYTES = 16 * 1024 * 1024
MAX_STRUCTURAL_QUARANTINE_BYTES = 32 * 1024 * 1024
MAX_BUNDLE_BYTES = 48 * 1024 * 1024

PREPARATION_REASON_CODES = frozenset(
    {
        "ACL_UNVERIFIABLE_OR_PRESENT",
        "ARTIFACT_VALIDATION_FAILED",
        "CONCURRENT_MUTATION_DETECTED",
        "CROSS_DEVICE_ENTRY",
        "CURATOR_REVIEW_REQUIRED",
        "EMPTY_CORPUS",
        "HARDLINK_OR_DUPLICATE_INODE",
        "INPUT_UNREADABLE_OR_UNVERIFIABLE",
        "INTERNAL_ERROR",
        "OUTPUT_ALREADY_EXISTS",
        "OUTPUT_BOUNDARY_INVALID",
        "OUTPUT_COMMIT_STATE_UNKNOWN",
        "OUTPUT_CONTENT_UNVERIFIED",
        "OUTPUT_WRITE_FAILED",
        "PATH_PROFILE_INVALID_OR_COLLISION",
        "PERMISSION_BOUNDARY_INVALID",
        "PLATFORM_UNSUPPORTED",
        "POLICY_DOCUMENT_INVALID",
        "RESOURCE_LIMIT_EXCEEDED",
        "ROOT_BOUNDARY_INVALID",
        "SPECIAL_OR_UNSUPPORTED_ENTRY",
        "SYMLINK_PRESENT",
    }
)
WRITE_STATES = frozenset(
    {
        "not_written",
        "committed_and_verified",
        "committed_durability_unknown",
        "outcome_unknown",
    }
)

_BUNDLE_PRIVACY = {
    "private_storage_required": True,
    "exact_paths_included": True,
    "content_digests_included": True,
    "source_values_included": False,
    "publication_review_required": True,
}

_QUARANTINE_PRIVACY = {
    "exact_paths_included": False,
    "content_digests_included": True,
    "headers_included": False,
    "source_identifiers_included": False,
    "private_values_included": False,
    "exception_text_included": False,
    "publication_review_required": True,
}


class PrivateReviewError(ValueError):
    """A fixed-code private-review failure that cannot quote private input."""

    def __init__(self, code: str) -> None:
        safe_code = code if code in PREPARATION_REASON_CODES else "INTERNAL_ERROR"
        self.code = safe_code
        super().__init__(safe_code)


@dataclass(frozen=True)
class PrivateReviewBundle:
    """Two closed private documents published as one atomic JSON artifact."""

    policy: dict[str, Any]
    structural_quarantine: dict[str, Any]
    source_root_identity: tuple[int, ...] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "bundle_kind": "private_corpus_review_bundle",
            "policy": self.policy,
            "structural_quarantine": self.structural_quarantine,
            "privacy": dict(_BUNDLE_PRIVACY),
            "assurance": dict(ASSURANCE),
        }


@dataclass(frozen=True)
class PrivateReviewPublication:
    """Sanitized publication postcondition."""

    write_state: str
    reason_code: str | None = None


def build_private_review_bundle(
    root: Path,
    created_at: str,
    *,
    key: bytes | None = None,
    limits: AuditLimits | None = None,
) -> PrivateReviewBundle:
    """Create a stable, deny-all review draft without modifying the corpus."""

    _validate_created_at(created_at)
    active_limits = limits or AuditLimits()
    _validate_limits(active_limits)
    active_key = key if key is not None else secrets.token_bytes(32)
    if not isinstance(active_key, bytes) or len(active_key) < 16:
        raise PrivateReviewError("INTERNAL_ERROR")

    snapshot = _stable_snapshot(root, key=active_key, limits=active_limits)
    if not snapshot.files:
        raise PrivateReviewError("EMPTY_CORPUS")
    if any(not observation.analysis.anomaly_enumeration_complete for observation in snapshot.files):
        raise PrivateReviewError("RESOURCE_LIMIT_EXCEEDED")

    ordered = tuple(
        sorted(
            snapshot.files,
            key=lambda observation: observation.relative_path.encode("utf-8"),
        )
    )
    policy_entries: list[dict[str, Any]] = []
    quarantine_entries: list[dict[str, Any]] = []
    for policy_entry_index, observation in enumerate(ordered):
        content_sha256 = f"sha256:{observation.content_sha256.hex()}"
        policy_entries.append(
            {
                "relative_path": observation.relative_path,
                "content_sha256": content_sha256,
                "curation_status": "pending",
                "content_layer": "unknown",
                "source_id": "unresolved-private-source",
                "source_locator": None,
                "source_revision": None,
                "provenance_status": "unknown",
                "rights_status": "unknown",
                "rights_evidence_status": "missing",
                "permitted_uses": [],
            }
        )
        if not observation.analysis.anomalies:
            continue
        quarantine_entries.append(
            {
                "policy_entry_index": policy_entry_index,
                "content_sha256": content_sha256,
                "format": observation.analysis.format_name,
                "analysis_complete": observation.analysis.anomaly_enumeration_complete,
                "anomalies": [
                    {
                        "code": anomaly.code,
                        "record_number": anomaly.record_number,
                        "expected_columns": anomaly.expected_columns,
                        "observed_columns": anomaly.observed_columns,
                    }
                    for anomaly in observation.analysis.anomalies
                ],
            }
        )

    policy = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_kind": "private_corpus_use_policy",
        "entries": policy_entries,
    }
    structural_quarantine = {
        "schema_version": STRUCTURAL_QUARANTINE_SCHEMA_VERSION,
        "ledger_kind": "private_corpus_structural_quarantine",
        "created_at": created_at,
        "scope": "csv_json_jsonl_structure",
        "parser_contract": PARSER_CONTRACT,
        "scan_completed": True,
        "inventory_complete": True,
        "file_quarantine_coverage_complete": True,
        "anomaly_enumeration_complete": True,
        "source_data_modified": False,
        "readiness_override": False,
        "clean_files_omitted": True,
        "privacy": dict(_QUARANTINE_PRIVACY),
        "assurance": dict(ASSURANCE),
        "entries": quarantine_entries,
    }
    bundle = PrivateReviewBundle(
        policy=policy,
        structural_quarantine=structural_quarantine,
        source_root_identity=snapshot.root_identity,
    )
    _validate_bundle_documents(bundle)
    _enforce_bundle_sizes(bundle)
    return bundle


def safe_private_review_summary(
    *,
    scan_completed: bool,
    write_state: str,
    reason_code: str | None = None,
) -> dict[str, Any]:
    """Return a fixed, count-free summary suitable for a public log."""

    safe_state = write_state if write_state in WRITE_STATES else "outcome_unknown"
    if reason_code is None and safe_state == "committed_and_verified":
        reasons = ["CURATOR_REVIEW_REQUIRED"]
    else:
        safe_reason = reason_code if reason_code in PREPARATION_REASON_CODES else "INTERNAL_ERROR"
        reasons = [safe_reason]
    return {
        "schema_version": PREPARATION_SCHEMA_VERSION,
        "operation": "prepare_private_review",
        "scan_completed": scan_completed,
        "write_state": safe_state,
        "template_state": "deny_all_pending_review",
        "curator_review_required": True,
        "corpus_use_permitted": False,
        "source_data_modified": False,
        "publication_review_required": True,
        "reason_codes": reasons,
        "assurance": dict(ASSURANCE),
    }


def read_private_review_bundle(
    path: Path,
    *,
    max_bytes: int = MAX_BUNDLE_BYTES,
) -> PrivateReviewBundle:
    """Read one closed private bundle without following path symlinks."""

    value = read_private_policy(path, max_bytes=max_bytes)
    if set(value) != {
        "schema_version",
        "bundle_kind",
        "policy",
        "structural_quarantine",
        "privacy",
        "assurance",
    }:
        raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED")
    if (
        value.get("schema_version") != BUNDLE_SCHEMA_VERSION
        or value.get("bundle_kind") != "private_corpus_review_bundle"
        or value.get("privacy") != _BUNDLE_PRIVACY
        or value.get("assurance") != ASSURANCE
        or not isinstance(value.get("policy"), dict)
        or not isinstance(value.get("structural_quarantine"), dict)
    ):
        raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED")
    policy = value["policy"]
    structural_quarantine = value["structural_quarantine"]
    assert isinstance(policy, dict)
    assert isinstance(structural_quarantine, dict)
    bundle = PrivateReviewBundle(
        policy=policy,
        structural_quarantine=structural_quarantine,
    )
    _enforce_bundle_sizes(bundle)
    _validate_bundle_documents(bundle)
    return bundle


def publish_private_review_bundle(
    root: Path,
    destination: Path,
    bundle: PrivateReviewBundle,
) -> PrivateReviewPublication:
    """Publish one freshly scanned 0600 bundle without replacing any path."""

    if bundle.source_root_identity is None:
        raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED")
    _validate_bundle_documents(bundle)
    raw = _enforce_bundle_sizes(bundle)
    if (
        not root.is_absolute()
        or not destination.is_absolute()
        or destination.name in {"", ".", ".."}
        or "/" in destination.name
        or "\x00" in destination.name
    ):
        raise PrivateReviewError("OUTPUT_BOUNDARY_INVALID")
    try:
        _validate_component(destination.name, 255)
    except PrivateReadinessError:
        raise PrivateReviewError("OUTPUT_BOUNDARY_INVALID") from None
    if (
        os.link not in os.supports_dir_fd
        or os.link not in os.supports_follow_symlinks
        or os.unlink not in os.supports_dir_fd
    ):
        raise PrivateReviewError("PLATFORM_UNSUPPORTED")

    root_pinned = None
    parent_pinned = None
    descriptor: int | None = None
    staging_name = f".private-review-{secrets.token_hex(16)}.tmp"
    staging_identity: tuple[int, int] | None = None
    published = False
    content_verified = False
    try:
        try:
            root_pinned = _open_pinned_directory(root, private_target=True)
        except PrivateReadinessError as error:
            raise PrivateReviewError(error.code) from None
        try:
            parent_pinned = _open_pinned_directory(
                destination.parent,
                private_target=True,
            )
        except PrivateReadinessError:
            raise PrivateReviewError("OUTPUT_BOUNDARY_INVALID") from None
        root_identity = _inode_identity(os.fstat(root_pinned.descriptor))
        if _directory_identity(os.fstat(root_pinned.descriptor)) != (bundle.source_root_identity):
            raise PrivateReviewError("CONCURRENT_MUTATION_DETECTED")
        if _directory_fd_is_within(parent_pinned.descriptor, root_identity):
            raise PrivateReviewError("OUTPUT_BOUNDARY_INVALID")
        _verify_boundaries(root_pinned, parent_pinned)
        if _entry_exists(parent_pinned.descriptor, destination.name):
            raise PrivateReviewError("OUTPUT_ALREADY_EXISTS")

        descriptor = os.open(
            staging_name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=parent_pinned.descriptor,
        )
        opened = os.fstat(descriptor)
        staging_identity = _inode_identity(opened)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_uid != os.geteuid()
        ):
            raise OSError(errno.EIO, "private review staging identity invalid")
        os.fchmod(descriptor, 0o600)
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        staged = os.fstat(descriptor)
        if _inode_identity(staged) != staging_identity:
            raise OSError(errno.EIO, "private review staging identity changed")
        _verify_private_output_descriptor(descriptor, raw, expected_nlink=1)
        if _fingerprint(os.fstat(descriptor)) != _fingerprint(staged):
            raise OSError(errno.EIO, "private review staging file changed")

        _verify_boundaries(root_pinned, parent_pinned)
        if _entry_exists(parent_pinned.descriptor, destination.name):
            raise PrivateReviewError("OUTPUT_ALREADY_EXISTS")
        _link_no_replace(
            staging_name,
            destination.name,
            parent_descriptor=parent_pinned.descriptor,
        )
        published = True
        _verify_private_output_descriptor(descriptor, raw, expected_nlink=2)
        _unlink_staging_if_same(
            parent_pinned.descriptor,
            staging_name,
            staging_identity,
        )
        _verify_private_output_descriptor(descriptor, raw, expected_nlink=1)
        content_verified = True
        _verify_requested_destination(
            destination,
            pinned_parent=parent_pinned,
            expected_identity=staging_identity,
            expected_bytes=raw,
        )
        _verify_boundaries(root_pinned, parent_pinned)
        try:
            os.fsync(parent_pinned.descriptor)
        except OSError:
            return PrivateReviewPublication(
                "committed_durability_unknown",
                "OUTPUT_COMMIT_STATE_UNKNOWN",
            )
        _verify_private_output_descriptor(descriptor, raw, expected_nlink=1)
        _verify_requested_destination(
            destination,
            pinned_parent=parent_pinned,
            expected_identity=staging_identity,
            expected_bytes=raw,
        )
        _verify_boundaries(root_pinned, parent_pinned)
        return PrivateReviewPublication("committed_and_verified")
    except PrivateReviewError:
        if published:
            return PrivateReviewPublication(
                "outcome_unknown",
                (
                    "OUTPUT_CONTENT_UNVERIFIED"
                    if not content_verified
                    else "OUTPUT_COMMIT_STATE_UNKNOWN"
                ),
            )
        raise
    except (OSError, ValueError) as error:
        if published:
            return PrivateReviewPublication(
                "outcome_unknown",
                (
                    "OUTPUT_CONTENT_UNVERIFIED"
                    if not content_verified
                    else "OUTPUT_COMMIT_STATE_UNKNOWN"
                ),
            )
        if isinstance(error, OSError) and error.errno == errno.EEXIST:
            raise PrivateReviewError("OUTPUT_ALREADY_EXISTS") from None
        raise PrivateReviewError("OUTPUT_WRITE_FAILED") from None
    finally:
        if parent_pinned is not None and staging_identity is not None:
            with suppress(OSError):
                _unlink_staging_if_same(
                    parent_pinned.descriptor,
                    staging_name,
                    staging_identity,
                )
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        if parent_pinned is not None:
            _close_pinned_directory(parent_pinned)
        if root_pinned is not None:
            _close_pinned_directory(root_pinned)


def _encode_private_json(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _validate_bundle_links(bundle: PrivateReviewBundle) -> None:
    policy_entries = bundle.policy.get("entries")
    quarantine_entries = bundle.structural_quarantine.get("entries")
    if not isinstance(policy_entries, list) or not isinstance(
        quarantine_entries,
        list,
    ):
        raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED")
    seen: set[int] = set()
    for raw_entry in quarantine_entries:
        if not isinstance(raw_entry, dict):
            raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED")
        index = raw_entry.get("policy_entry_index")
        digest = raw_entry.get("content_sha256")
        if (
            type(index) is not int
            or index < 0
            or index >= len(policy_entries)
            or index in seen
            or not isinstance(policy_entries[index], dict)
            or policy_entries[index].get("content_sha256") != digest
        ):
            raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED")
        seen.add(index)


def _validate_bundle_documents(bundle: PrivateReviewBundle) -> None:
    _validate_bundle_links(bundle)
    for document, schema_name in (
        (bundle.as_dict(), "private-review-bundle.schema.json"),
        (bundle.policy, "private-corpus-policy.schema.json"),
        (
            bundle.structural_quarantine,
            "private-structural-quarantine.schema.json",
        ),
    ):
        try:
            issues = validate_schema_instance(
                document,
                _private_schema_path(schema_name),
            )
        except Exception:
            raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED") from None
        if issues:
            raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED")


def _enforce_bundle_sizes(bundle: PrivateReviewBundle) -> bytes:
    policy_bytes = _encode_private_json(bundle.policy)
    structural_bytes = _encode_private_json(bundle.structural_quarantine)
    bundle_bytes = _encode_private_json(bundle.as_dict())
    if (
        len(policy_bytes) > MAX_POLICY_BYTES
        or len(structural_bytes) > MAX_STRUCTURAL_QUARANTINE_BYTES
        or len(bundle_bytes) > MAX_BUNDLE_BYTES
    ):
        raise PrivateReviewError("RESOURCE_LIMIT_EXCEEDED")
    return bundle_bytes


def _private_schema_path(filename: str) -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / filename
    if project_candidate.is_file():
        return project_candidate
    package_candidate = resources.files("indusbench").joinpath(f"schemas/{filename}")
    return Path(str(package_candidate))


def _inode_identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK


def _directory_fd_is_within(
    descriptor: int,
    ancestor_identity: tuple[int, int],
) -> bool:
    current = os.dup(descriptor)
    os.set_inheritable(current, False)
    try:
        for _ in range(1024):
            metadata = os.fstat(current)
            identity = _inode_identity(metadata)
            if identity == ancestor_identity:
                return True
            parent = os.open("..", _directory_flags(), dir_fd=current)
            parent_identity = _inode_identity(os.fstat(parent))
            os.close(current)
            current = parent
            if parent_identity == identity:
                return False
    finally:
        os.close(current)
    raise PrivateReviewError("OUTPUT_BOUNDARY_INVALID")


def _verify_boundaries(root_pinned: Any, parent_pinned: Any) -> None:
    try:
        from indusbench.private_readiness import _verify_pinned_directory

        _verify_pinned_directory(root_pinned)
        _verify_pinned_directory(parent_pinned)
    except PrivateReadinessError as error:
        raise PrivateReviewError(error.code) from None


def _entry_exists(parent_descriptor: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise PrivateReviewError("OUTPUT_WRITE_FAILED") from error
    return True


def _write_all(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            raise OSError(errno.EIO, "short private review write")
        offset += written


def _link_no_replace(
    source_name: str,
    destination_name: str,
    *,
    parent_descriptor: int,
) -> None:
    os.link(
        source_name,
        destination_name,
        src_dir_fd=parent_descriptor,
        dst_dir_fd=parent_descriptor,
        follow_symlinks=False,
    )


def _verify_private_output_descriptor(
    descriptor: int,
    expected: bytes,
    *,
    expected_nlink: int,
) -> None:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != expected_nlink
        or metadata.st_size != len(expected)
    ):
        raise OSError(errno.EIO, "private review output metadata mismatch")
    _require_acl_free(descriptor)
    if _read_exact_descriptor(descriptor, len(expected), 1024 * 1024) != expected:
        raise OSError(errno.EIO, "private review output content mismatch")


def _unlink_staging_if_same(
    parent_descriptor: int,
    name: str,
    expected_identity: tuple[int, int],
) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return
    if _inode_identity(metadata) == expected_identity:
        os.unlink(name, dir_fd=parent_descriptor)


def _verify_requested_destination(
    destination: Path,
    *,
    pinned_parent: Any,
    expected_identity: tuple[int, int],
    expected_bytes: bytes,
) -> None:
    requested_parent = None
    descriptor: int | None = None
    try:
        requested_parent = _open_pinned_directory(
            destination.parent,
            private_target=True,
        )
        if _directory_identity(os.fstat(requested_parent.descriptor)) != _directory_identity(
            os.fstat(pinned_parent.descriptor)
        ):
            raise PrivateReviewError("OUTPUT_COMMIT_STATE_UNKNOWN")
        descriptor = os.open(
            destination.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=requested_parent.descriptor,
        )
        if _inode_identity(os.fstat(descriptor)) != expected_identity:
            raise PrivateReviewError("OUTPUT_COMMIT_STATE_UNKNOWN")
        _verify_private_output_descriptor(
            descriptor,
            expected_bytes,
            expected_nlink=1,
        )
    except PrivateReadinessError as error:
        raise PrivateReviewError(error.code) from None
    except OSError:
        raise PrivateReviewError("OUTPUT_COMMIT_STATE_UNKNOWN") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if requested_parent is not None:
            _close_pinned_directory(requested_parent)
