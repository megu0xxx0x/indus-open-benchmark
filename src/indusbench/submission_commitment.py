"""Deterministic, local-only commitments for complete submission trees.

This module binds exact file bytes, portable logical paths, declared roles, an
entrypoint, and a target benchmark-definition digest.  It does not attest when
or by whom the commitment was created, whether hidden data had been accessed,
whether a custodian received it, or whether the committed bytes were executed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from indusbench.schema_validation import validate_schema_instance

SCHEMA_VERSION = "0.1.0"
CANONICALIZATION = "indus-json-c14n-v1"
DIGEST_SUITE = "indusbench-submission-sha256-v0.1"
TREE_DOMAIN = b"indusbench:submission-tree:v0.1\0"
COMMITMENT_DOMAIN = b"indusbench:submission-commitment:v0.1\0"
SCIENTIFIC_SCOPE = (
    "submission tree bytes, declared roles, a declared entrypoint, and a caller-declared "
    "target benchmark-definition digest only; no blind, custody, trusted-time, "
    "authorship, confidentiality, runtime, result, decipherment, or translation inference"
)
ROLE_ORDER = (
    "entrypoint",
    "source",
    "configuration",
    "model_weight",
    "dependency",
    "runtime_input",
)
ASSURANCE_REASON_CODES = (
    "content_identity_only",
    "manifest_not_confidential_or_unlinkable",
    "no_external_anchor_in_commitment",
    "no_custody_receipt_in_commitment",
    "no_trusted_timestamp_in_commitment",
    "author_identity_not_attested",
    "hidden_data_access_not_observed",
    "runtime_not_executed_or_attested",
)

MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_DIRECTORIES = 4096
MAX_DEPTH = 32
MAX_PATH_BYTES = 240
MAX_COMPONENT_BYTES = 100
MAX_FILE_BYTES = 8 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024 * 1024
MAX_STATIC_ARGUMENTS = 32
MAX_STATIC_ARGUMENT_BYTES = 256
MAX_STATIC_ARGUMENT_TOTAL_BYTES = 4096
MAX_MISMATCHES = 100
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 100_000
READ_CHUNK_BYTES = 1024 * 1024

CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9._+@-]+$")
WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)


class SubmissionCommitmentError(ValueError):
    """Raised when a submission cannot be committed or safely interpreted."""


@dataclass(frozen=True)
class SubmissionVerificationReport:
    """Verification result with assurance fields generated only by trusted code."""

    valid: bool
    self_consistent: bool
    tree_matches: bool
    entrypoint_bound: bool
    expected_digest_match: bool | None
    commitment_sha256: str
    expected_commitment_sha256: str | None
    checked_file_count: int
    checked_total_bytes: int
    mismatches: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "self_consistent": self.self_consistent,
            "tree_matches": self.tree_matches,
            "entrypoint_bound": self.entrypoint_bound,
            "expected_digest_match": self.expected_digest_match,
            "commitment_sha256": self.commitment_sha256,
            "expected_commitment_sha256": self.expected_commitment_sha256,
            "checked_file_count": self.checked_file_count,
            "checked_total_bytes": self.checked_total_bytes,
            "mismatches": list(self.mismatches),
            "claim_class": "submission_content_commitment",
            "blind_claim_allowed": False,
            "final_evaluation_eligible": False,
            "externally_anchored": False,
            "custody_attested": False,
            "trusted_timestamp_attested": False,
            "authorship_attested": False,
            "access_history_attested": False,
            "confidentiality_attested": False,
            "runtime_isolation_attested": False,
            "execution_result_attested": False,
            "verification_scope": "point_in_time_non_atomic_filesystem_checks",
            "postconditions_atomic": False,
            "future_immutability_attested": False,
        }


@dataclass(frozen=True)
class _TreeSnapshot:
    entries: tuple[dict[str, Any], ...]
    file_count: int
    directory_count: int
    total_bytes: int
    fingerprints: tuple[tuple[str, tuple[int, ...]], ...]
    root_fingerprint: tuple[int, ...]


@dataclass
class _ScanState:
    root_device: int
    entries: list[dict[str, Any]]
    fingerprints: list[tuple[str, tuple[int, ...]]]
    collision_paths: dict[str, str]
    inode_paths: dict[tuple[int, int], str]
    observed_entry_count: int = 0
    file_count: int = 0
    directory_count: int = 0
    total_bytes: int = 0


def _assurance() -> dict[str, Any]:
    return {
        "claim_class": "submission_content_commitment",
        "blind_claim_allowed": False,
        "final_evaluation_eligible": False,
        "externally_anchored": False,
        "custody_attested": False,
        "trusted_timestamp_attested": False,
        "authorship_attested": False,
        "access_history_attested": False,
        "confidentiality_attested": False,
        "runtime_isolation_attested": False,
        "execution_result_attested": False,
        "reason_codes": list(ASSURANCE_REASON_CODES),
    }


def _reject_floats(value: object, path: str = "$") -> None:
    if isinstance(value, float):
        raise SubmissionCommitmentError(
            f"{path}: submission commitment values cannot contain floats"
        )
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_floats(child, f"{path}[{index}]")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise SubmissionCommitmentError(
                    f"{path}: submission commitment keys must be strings"
                )
            _reject_floats(child, f"{path}.{key}")


def _check_json_complexity(value: object) -> None:
    stack: list[tuple[object, int]] = [(value, 0)]
    seen_containers: set[int] = set()
    node_count = 0
    while stack:
        current, depth = stack.pop()
        node_count += 1
        if node_count > MAX_JSON_NODES:
            raise SubmissionCommitmentError(
                f"submission commitment exceeds {MAX_JSON_NODES} JSON nodes"
            )
        if depth > MAX_JSON_DEPTH:
            raise SubmissionCommitmentError(
                f"submission commitment exceeds JSON depth {MAX_JSON_DEPTH}"
            )
        if isinstance(current, Mapping):
            identity = id(current)
            if identity in seen_containers:
                raise SubmissionCommitmentError(
                    "submission commitment contains cyclic or aliased containers"
                )
            seen_containers.add(identity)
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            identity = id(current)
            if identity in seen_containers:
                raise SubmissionCommitmentError(
                    "submission commitment contains cyclic or aliased containers"
                )
            seen_containers.add(identity)
            stack.extend((child, depth + 1) for child in current)


def canonical_submission_json(value: Mapping[str, Any]) -> bytes:
    """Apply the strict no-float canonical JSON profile used by commitments."""

    _check_json_complexity(value)
    _reject_floats(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def submission_tree_digest(tree: Mapping[str, Any]) -> str:
    """Return the domain-separated tree digest without its self field."""

    body = dict(tree)
    body.pop("tree_sha256", None)
    return "sha256:" + hashlib.sha256(TREE_DOMAIN + canonical_submission_json(body)).hexdigest()


def submission_commitment_digest(value: Mapping[str, Any]) -> str:
    """Return the domain-separated commitment digest without its self fields."""

    body = dict(value)
    body.pop("commitment_id", None)
    body.pop("commitment_sha256", None)
    return (
        "sha256:" + hashlib.sha256(COMMITMENT_DOMAIN + canonical_submission_json(body)).hexdigest()
    )


def _strict_json_bytes(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SubmissionCommitmentError(f"{label}: invalid UTF-8") from error

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, child in pairs:
            if key in result:
                raise SubmissionCommitmentError(f"{label}: duplicate JSON key {key!r}")
            result[key] = child
        return result

    def reject_constant(value: str) -> None:
        raise SubmissionCommitmentError(f"{label}: non-finite JSON number {value!r}")

    def reject_float(value: str) -> None:
        raise SubmissionCommitmentError(f"{label}: JSON floats are not permitted ({value!r})")

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
            parse_float=reject_float,
        )
    except (json.JSONDecodeError, RecursionError) as error:
        raise SubmissionCommitmentError(f"{label}: invalid JSON: {error}") from error
    _check_json_complexity(value)
    return value


def _fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_bounded_regular_path(path: Path, *, max_bytes: int, label: str) -> bytes:
    try:
        before = path.lstat()
    except OSError as error:
        raise SubmissionCommitmentError(f"{label}: cannot stat input: {error}") from error
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size <= 0
        or before.st_size > max_bytes
    ):
        raise SubmissionCommitmentError(
            f"{label}: input must be a non-empty, single-link regular file "
            f"of at most {max_bytes} bytes"
        )

    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if _fingerprint(opened) != _fingerprint(before):
            raise SubmissionCommitmentError(f"{label}: input changed before it was opened")
        chunks: list[bytes] = []
        byte_count = 0
        while True:
            chunk = os.read(descriptor, min(READ_CHUNK_BYTES, max_bytes + 1 - byte_count))
            if not chunk:
                break
            chunks.append(chunk)
            byte_count += len(chunk)
            if byte_count > max_bytes:
                raise SubmissionCommitmentError(f"{label}: input exceeds size limit")
        after = os.fstat(descriptor)
        if _fingerprint(after) != _fingerprint(opened):
            raise SubmissionCommitmentError(f"{label}: input changed while it was read")
        try:
            path_after = path.lstat()
        except OSError as error:
            raise SubmissionCommitmentError(
                f"{label}: input namespace changed after it was read"
            ) from error
        if _fingerprint(path_after) != _fingerprint(opened):
            raise SubmissionCommitmentError(f"{label}: input namespace changed after it was read")
        return b"".join(chunks)
    except OSError as error:
        raise SubmissionCommitmentError(f"{label}: cannot safely read input: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_submission_commitment(path: str | Path) -> dict[str, Any]:
    """Read one bounded, strict commitment without following its final symlink."""

    source = Path(path)
    raw = _read_bounded_regular_path(
        source,
        max_bytes=MAX_MANIFEST_BYTES,
        label=str(source),
    )
    value = _strict_json_bytes(raw, str(source))
    if not isinstance(value, dict):
        raise SubmissionCommitmentError("submission commitment must be a JSON object")
    return value


def _reject_remote_schema_refs(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        reference = value.get("$ref")
        if isinstance(reference, str) and not reference.startswith("#/"):
            raise SubmissionCommitmentError(
                f"submission commitment schema {path} contains a non-local $ref"
            )
        for key, child in value.items():
            _reject_remote_schema_refs(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_remote_schema_refs(child, f"{path}[{index}]")


def _default_submission_schema() -> dict[str, Any]:
    candidates = (
        Path(__file__).resolve().parents[2] / "schemas" / "submission-commitment.schema.json",
        Path(__file__).resolve().parent / "schemas" / "submission-commitment.schema.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            raw = _read_bounded_regular_path(
                candidate,
                max_bytes=MAX_MANIFEST_BYTES,
                label="schemas/submission-commitment.schema.json",
            )
            value = _strict_json_bytes(raw, "schemas/submission-commitment.schema.json")
            if not isinstance(value, dict):
                raise SubmissionCommitmentError(
                    "submission commitment schema must be a JSON object"
                )
            _reject_remote_schema_refs(value)
            return value
    raise SubmissionCommitmentError("submission-commitment.schema.json is unavailable")


def _schema_issues(instance: Any, schema: Mapping[str, Any]) -> None:
    issues = validate_schema_instance(instance, schema)
    if issues:
        preview = "; ".join(f"{issue.path}: {issue.message}" for issue in issues[:5])
        raise SubmissionCommitmentError(
            f"submission commitment failed schema validation: {preview}"
        )


def _require_secure_tree_platform() -> None:
    missing: list[str] = []
    for constant in ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"):
        if not getattr(os, constant, 0):
            missing.append(constant)
    if os.open not in os.supports_dir_fd:
        missing.append("openat")
    if os.stat not in os.supports_dir_fd or os.stat not in os.supports_follow_symlinks:
        missing.append("fstatat-no-follow")
    if os.scandir not in os.supports_fd:
        missing.append("fd-scandir")
    if missing:
        raise SubmissionCommitmentError(
            "secure submission-tree traversal is unsupported on this platform: "
            + ", ".join(missing)
        )


def _validate_component(component: str) -> None:
    try:
        encoded = component.encode("ascii")
    except UnicodeEncodeError as error:
        raise SubmissionCommitmentError(
            "submission logical paths must use the v0.1 portable ASCII profile"
        ) from error
    if not component or component in {".", ".."}:
        raise SubmissionCommitmentError(f"unsafe logical path component {component!r}")
    if len(encoded) > MAX_COMPONENT_BYTES:
        raise SubmissionCommitmentError(
            f"logical path component exceeds {MAX_COMPONENT_BYTES} bytes"
        )
    if not SAFE_COMPONENT_PATTERN.fullmatch(component):
        raise SubmissionCommitmentError(f"unsafe logical path component {component!r}")
    if component.endswith((".", " ")):
        raise SubmissionCommitmentError(
            f"logical path component has a non-portable suffix: {component!r}"
        )
    device_stem = component.split(".", maxsplit=1)[0].upper()
    if device_stem in WINDOWS_RESERVED_NAMES:
        raise SubmissionCommitmentError(
            f"logical path component is a reserved device name: {component!r}"
        )


def normalize_logical_path(value: str) -> str:
    """Validate and return one canonical v0.1 portable relative path."""

    if not isinstance(value, str) or not value:
        raise SubmissionCommitmentError("logical path must be a non-empty string")
    if value.startswith("/") or "\\" in value or "\x00" in value:
        raise SubmissionCommitmentError(f"unsafe logical path {value!r}")
    parts = value.split("/")
    if not parts or len(parts) > MAX_DEPTH or any(not part for part in parts):
        raise SubmissionCommitmentError(f"unsafe logical path {value!r}")
    for component in parts:
        _validate_component(component)
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise SubmissionCommitmentError(
            "submission logical paths must use the v0.1 portable ASCII profile"
        ) from error
    if len(encoded) > MAX_PATH_BYTES:
        raise SubmissionCommitmentError(f"logical path exceeds {MAX_PATH_BYTES} bytes")
    return value


def _collision_key(path: str) -> str:
    return unicodedata.normalize(
        "NFKC",
        unicodedata.normalize("NFKC", path).casefold(),
    )


def _path_sort_key(path: str) -> bytes:
    return path.encode("utf-8")


def _reject_special_bits(metadata: os.stat_result, logical_path: str) -> None:
    if metadata.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
        raise SubmissionCommitmentError(
            f"{logical_path}: setuid, setgid, and sticky mode bits are forbidden"
        )


def _register_namespace_entry(
    state: _ScanState,
    *,
    logical_path: str,
    metadata: os.stat_result,
) -> None:
    if len(state.entries) >= MAX_ENTRIES:
        raise SubmissionCommitmentError(f"submission tree exceeds {MAX_ENTRIES} entries")
    collision_key = _collision_key(logical_path)
    previous = state.collision_paths.get(collision_key)
    if previous is not None:
        raise SubmissionCommitmentError(
            f"logical path collision between {previous!r} and {logical_path!r}"
        )
    state.collision_paths[collision_key] = logical_path
    inode_key = (metadata.st_dev, metadata.st_ino)
    previous_inode = state.inode_paths.get(inode_key)
    if previous_inode is not None:
        raise SubmissionCommitmentError(
            f"filesystem inode is reachable as both {previous_inode!r} and {logical_path!r}"
        )
    state.inode_paths[inode_key] = logical_path
    if metadata.st_dev != state.root_device:
        raise SubmissionCommitmentError(f"{logical_path}: cross-device boundaries are forbidden")
    _reject_special_bits(metadata, logical_path)
    state.fingerprints.append((logical_path, _fingerprint(metadata)))


def _hash_regular_file_at(
    parent_descriptor: int,
    name: str,
    *,
    logical_path: str,
    expected: os.stat_result,
    state: _ScanState,
) -> dict[str, Any]:
    if not stat.S_ISREG(expected.st_mode) or expected.st_nlink != 1:
        raise SubmissionCommitmentError(
            f"{logical_path}: submission leaves must be single-link regular files"
        )
    if expected.st_size < 0 or expected.st_size > MAX_FILE_BYTES:
        raise SubmissionCommitmentError(
            f"{logical_path}: file exceeds the {MAX_FILE_BYTES}-byte limit"
        )
    if state.file_count >= MAX_ENTRIES:
        raise SubmissionCommitmentError(f"submission tree exceeds {MAX_ENTRIES} files")
    if state.total_bytes + expected.st_size > MAX_TOTAL_BYTES:
        raise SubmissionCommitmentError(
            f"submission tree exceeds the {MAX_TOTAL_BYTES}-byte aggregate limit"
        )

    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor: int | None = None
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
        if _fingerprint(opened) != _fingerprint(expected):
            raise SubmissionCommitmentError(f"{logical_path}: file changed before it was opened")
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_dev != state.root_device
        ):
            raise SubmissionCommitmentError(
                f"{logical_path}: opened leaf is not a same-device, single-link regular file"
            )
        _reject_special_bits(opened, logical_path)
        digest = hashlib.sha256()
        byte_count = 0
        while True:
            chunk = os.read(descriptor, READ_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            byte_count += len(chunk)
            if byte_count > MAX_FILE_BYTES or state.total_bytes + byte_count > MAX_TOTAL_BYTES:
                raise SubmissionCommitmentError(
                    f"{logical_path}: file changed beyond a byte limit while being read"
                )
        after = os.fstat(descriptor)
        if _fingerprint(after) != _fingerprint(opened) or byte_count != opened.st_size:
            raise SubmissionCommitmentError(f"{logical_path}: file changed while it was read")
        try:
            namespace_after = os.stat(
                name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError as error:
            raise SubmissionCommitmentError(
                f"{logical_path}: file namespace changed after it was read"
            ) from error
        if _fingerprint(namespace_after) != _fingerprint(opened):
            raise SubmissionCommitmentError(
                f"{logical_path}: file namespace changed after it was read"
            )
    except OSError as error:
        raise SubmissionCommitmentError(
            f"{logical_path}: cannot safely read regular file: {error}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)

    _register_namespace_entry(
        state,
        logical_path=logical_path,
        metadata=opened,
    )
    state.file_count += 1
    state.total_bytes += byte_count
    return {
        "path": logical_path,
        "type": "file",
        "bytes": byte_count,
        "content_sha256": "sha256:" + digest.hexdigest(),
        "executable": bool(opened.st_mode & 0o111),
    }


def _walk_directory(
    descriptor: int,
    *,
    prefix: str,
    depth: int,
    state: _ScanState,
) -> None:
    directory_before = os.fstat(descriptor)
    if not stat.S_ISDIR(directory_before.st_mode):
        raise SubmissionCommitmentError(f"{prefix or '.'}: directory descriptor changed type")
    try:
        children: list[tuple[str, os.stat_result]] = []
        with os.scandir(descriptor) as iterator:
            for entry in iterator:
                if state.observed_entry_count >= MAX_ENTRIES:
                    raise SubmissionCommitmentError(
                        f"submission tree exceeds {MAX_ENTRIES} entries"
                    )
                state.observed_entry_count += 1
                children.append((entry.name, entry.stat(follow_symlinks=False)))
    except OSError as error:
        raise SubmissionCommitmentError(
            f"{prefix or '.'}: cannot enumerate directory: {error}"
        ) from error
    if _fingerprint(os.fstat(descriptor)) != _fingerprint(directory_before):
        raise SubmissionCommitmentError(
            f"{prefix or '.'}: directory changed while it was enumerated"
        )

    prepared: list[tuple[str, str, os.stat_result]] = []
    for name, metadata in children:
        logical_path = f"{prefix}/{name}" if prefix else name
        if depth + 1 > MAX_DEPTH:
            raise SubmissionCommitmentError(
                f"{logical_path}: submission tree exceeds depth {MAX_DEPTH}"
            )
        normalize_logical_path(logical_path)
        prepared.append((name, logical_path, metadata))
    prepared.sort(key=lambda item: _path_sort_key(item[1]))

    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    for name, logical_path, metadata in prepared:
        if stat.S_ISLNK(metadata.st_mode):
            raise SubmissionCommitmentError(f"{logical_path}: symbolic links are forbidden")
        if stat.S_ISDIR(metadata.st_mode):
            if state.directory_count >= MAX_DIRECTORIES:
                raise SubmissionCommitmentError(
                    f"submission tree exceeds {MAX_DIRECTORIES} directories"
                )
            _register_namespace_entry(
                state,
                logical_path=logical_path,
                metadata=metadata,
            )
            state.directory_count += 1
            state.entries.append({"path": logical_path, "type": "directory"})
            child_descriptor: int | None = None
            try:
                child_descriptor = os.open(
                    name,
                    directory_flags,
                    dir_fd=descriptor,
                )
                opened = os.fstat(child_descriptor)
                if (
                    _fingerprint(opened) != _fingerprint(metadata)
                    or not stat.S_ISDIR(opened.st_mode)
                    or opened.st_dev != state.root_device
                ):
                    raise SubmissionCommitmentError(
                        f"{logical_path}: directory changed before it was opened"
                    )
                _walk_directory(
                    child_descriptor,
                    prefix=logical_path,
                    depth=depth + 1,
                    state=state,
                )
            except OSError as error:
                raise SubmissionCommitmentError(
                    f"{logical_path}: cannot safely open directory: {error}"
                ) from error
            finally:
                if child_descriptor is not None:
                    os.close(child_descriptor)
        elif stat.S_ISREG(metadata.st_mode):
            state.entries.append(
                _hash_regular_file_at(
                    descriptor,
                    name,
                    logical_path=logical_path,
                    expected=metadata,
                    state=state,
                )
            )
        else:
            raise SubmissionCommitmentError(
                f"{logical_path}: only real directories and regular files are permitted"
            )

    for name, logical_path, expected in prepared:
        try:
            current = os.stat(
                name,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
        except OSError as error:
            raise SubmissionCommitmentError(
                f"{logical_path}: namespace changed during tree traversal"
            ) from error
        if _fingerprint(current) != _fingerprint(expected):
            raise SubmissionCommitmentError(
                f"{logical_path}: namespace changed during tree traversal"
            )
    if _fingerprint(os.fstat(descriptor)) != _fingerprint(directory_before):
        raise SubmissionCommitmentError(f"{prefix or '.'}: directory changed during tree traversal")


def _scan_tree_once(root: Path) -> _TreeSnapshot:
    _require_secure_tree_platform()
    try:
        root_before = root.lstat()
    except OSError as error:
        raise SubmissionCommitmentError(f"cannot stat submission root: {error}") from error
    if stat.S_ISLNK(root_before.st_mode) or not stat.S_ISDIR(root_before.st_mode):
        raise SubmissionCommitmentError("submission root must be a real directory")
    _reject_special_bits(root_before, ".")

    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor: int | None = None
    try:
        descriptor = os.open(root, directory_flags)
        root_opened = os.fstat(descriptor)
        if _fingerprint(root_opened) != _fingerprint(root_before):
            raise SubmissionCommitmentError("submission root changed before it was opened")
        state = _ScanState(
            root_device=root_opened.st_dev,
            entries=[],
            fingerprints=[],
            collision_paths={},
            inode_paths={(root_opened.st_dev, root_opened.st_ino): "."},
        )
        _walk_directory(
            descriptor,
            prefix="",
            depth=0,
            state=state,
        )
        root_after = os.fstat(descriptor)
        if _fingerprint(root_after) != _fingerprint(root_opened):
            raise SubmissionCommitmentError("submission root changed during tree traversal")
        try:
            root_namespace_after = root.lstat()
        except OSError as error:
            raise SubmissionCommitmentError(
                "submission root namespace changed during tree traversal"
            ) from error
        if _fingerprint(root_namespace_after) != _fingerprint(root_opened):
            raise SubmissionCommitmentError(
                "submission root namespace changed during tree traversal"
            )
    except OSError as error:
        raise SubmissionCommitmentError(
            f"cannot safely traverse submission root: {error}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)

    if state.file_count < 1:
        raise SubmissionCommitmentError("submission tree must contain at least one file")
    entries = tuple(
        sorted(
            state.entries,
            key=lambda entry: _path_sort_key(str(entry["path"])),
        )
    )
    fingerprints = tuple(
        sorted(
            state.fingerprints,
            key=lambda item: _path_sort_key(item[0]),
        )
    )
    return _TreeSnapshot(
        entries=entries,
        file_count=state.file_count,
        directory_count=state.directory_count,
        total_bytes=state.total_bytes,
        fingerprints=fingerprints,
        root_fingerprint=_fingerprint(root_opened),
    )


def _stable_tree_snapshot(root: Path) -> _TreeSnapshot:
    first = _scan_tree_once(root)
    second = _scan_tree_once(root)
    if (
        first.entries != second.entries
        or first.fingerprints != second.fingerprints
        or first.root_fingerprint != second.root_fingerprint
        or first.file_count != second.file_count
        or first.directory_count != second.directory_count
        or first.total_bytes != second.total_bytes
    ):
        raise SubmissionCommitmentError(
            "submission tree changed between the pre- and post-read inventories"
        )
    return first


def _normalize_role_paths(values: Iterable[str], *, label: str) -> set[str]:
    paths: set[str] = set()
    collision_paths: dict[str, str] = {}
    for value in values:
        path = normalize_logical_path(value)
        collision_key = _collision_key(path)
        previous = collision_paths.get(collision_key)
        if previous is not None:
            raise SubmissionCommitmentError(
                f"{label} contains duplicate or colliding paths {previous!r} and {path!r}"
            )
        collision_paths[collision_key] = path
        paths.add(path)
    return paths


def _validate_static_arguments(values: Iterable[str]) -> list[str]:
    arguments = list(values)
    if len(arguments) > MAX_STATIC_ARGUMENTS:
        raise SubmissionCommitmentError(
            f"entrypoint has more than {MAX_STATIC_ARGUMENTS} static arguments"
        )
    total_bytes = 0
    for argument in arguments:
        if not isinstance(argument, str) or not argument:
            raise SubmissionCommitmentError("entrypoint static arguments must be non-empty strings")
        encoded = argument.encode("utf-8")
        if len(encoded) > MAX_STATIC_ARGUMENT_BYTES or any(
            unicodedata.category(character).startswith("C") for character in argument
        ):
            raise SubmissionCommitmentError(
                "entrypoint static argument is too long or contains a control character"
            )
        total_bytes += len(encoded)
    if total_bytes > MAX_STATIC_ARGUMENT_TOTAL_BYTES:
        raise SubmissionCommitmentError(
            "entrypoint static arguments exceed the aggregate byte limit"
        )
    return arguments


def _tree_with_roles(
    snapshot: _TreeSnapshot,
    *,
    entrypoint: str,
    source_files: Iterable[str],
    config_files: Iterable[str],
    model_weight_files: Iterable[str],
    dependency_files: Iterable[str],
) -> dict[str, Any]:
    role_paths = {
        "source": _normalize_role_paths(source_files, label="source_files"),
        "configuration": _normalize_role_paths(config_files, label="config_files"),
        "model_weight": _normalize_role_paths(
            model_weight_files,
            label="model_weight_files",
        ),
        "dependency": _normalize_role_paths(
            dependency_files,
            label="dependency_files",
        ),
    }
    role_paths["source"].add(entrypoint)
    file_paths = {str(entry["path"]) for entry in snapshot.entries if entry["type"] == "file"}
    for role, paths in role_paths.items():
        missing = paths - file_paths
        if missing:
            raise SubmissionCommitmentError(
                f"{role} role references files outside the committed tree: "
                + ", ".join(sorted(missing, key=_path_sort_key))
            )
    if entrypoint not in file_paths:
        raise SubmissionCommitmentError(
            "declared entrypoint does not resolve to a committed regular file"
        )

    entries: list[dict[str, Any]] = []
    role_counts = {role: 0 for role in ROLE_ORDER}
    for base_entry in snapshot.entries:
        entry = dict(base_entry)
        if entry["type"] == "file":
            path = str(entry["path"])
            roles: set[str] = set()
            if path == entrypoint:
                roles.add("entrypoint")
            for role, paths in role_paths.items():
                if path in paths:
                    roles.add(role)
            if not roles:
                roles.add("runtime_input")
            ordered_roles = [role for role in ROLE_ORDER if role in roles]
            entry["roles"] = ordered_roles
            for role in ordered_roles:
                role_counts[role] += 1
        entries.append(entry)

    tree: dict[str, Any] = {
        "tree_sha256": "",
        "entry_count": len(entries),
        "file_count": snapshot.file_count,
        "directory_count": snapshot.directory_count,
        "total_bytes": snapshot.total_bytes,
        "role_counts": role_counts,
        "entries": entries,
    }
    tree["tree_sha256"] = submission_tree_digest(tree)
    return tree


def build_submission_commitment(
    *,
    root: Path,
    benchmark_definition_sha256: str,
    entrypoint: str,
    source_files: Iterable[str] = (),
    config_files: Iterable[str] = (),
    model_weight_files: Iterable[str] = (),
    dependency_files: Iterable[str] = (),
    static_arguments: Iterable[str] = (),
    schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic local content commitment for a complete tree."""

    if not CHECKSUM_PATTERN.fullmatch(benchmark_definition_sha256):
        raise SubmissionCommitmentError(
            "benchmark_definition_sha256 must be a lowercase sha256 checksum"
        )
    normalized_entrypoint = normalize_logical_path(entrypoint)
    arguments = _validate_static_arguments(static_arguments)
    snapshot = _stable_tree_snapshot(Path(root))
    tree = _tree_with_roles(
        snapshot,
        entrypoint=normalized_entrypoint,
        source_files=source_files,
        config_files=config_files,
        model_weight_files=model_weight_files,
        dependency_files=dependency_files,
    )
    commitment: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "canonicalization": CANONICALIZATION,
        "digest_suite": DIGEST_SUITE,
        "commitment_id": "",
        "commitment_sha256": "",
        "scientific_scope": SCIENTIFIC_SCOPE,
        "target": {
            "benchmark_definition_sha256": benchmark_definition_sha256,
        },
        "tree": tree,
        "entrypoint": {
            "kind": "declared_tree_file",
            "path": normalized_entrypoint,
            "working_directory": ".",
            "static_arguments": arguments,
        },
        "assurance": _assurance(),
    }
    digest = submission_commitment_digest(commitment)
    commitment["commitment_sha256"] = digest
    commitment["commitment_id"] = f"submission-commitment:{digest}"
    validate_submission_commitment(commitment, schema=schema)
    return commitment


def _validate_entry_structure(tree: Mapping[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    entries = tree.get("entries")
    if not isinstance(entries, list) or not entries:
        raise SubmissionCommitmentError("tree.entries must be a non-empty array")
    if len(entries) > MAX_ENTRIES:
        raise SubmissionCommitmentError(f"tree exceeds {MAX_ENTRIES} entries")

    paths: set[str] = set()
    collision_paths: dict[str, str] = {}
    directory_paths: set[str] = set()
    file_paths: set[str] = set()
    normalized_entries: list[dict[str, Any]] = []
    previous_sort_key: bytes | None = None
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, Mapping):
            raise SubmissionCommitmentError(f"tree.entries[{index}] must be an object")
        entry = dict(raw_entry)
        path = entry.get("path")
        if not isinstance(path, str) or normalize_logical_path(path) != path:
            raise SubmissionCommitmentError(f"tree.entries[{index}].path is unsafe")
        sort_key = _path_sort_key(path)
        if previous_sort_key is not None and sort_key <= previous_sort_key:
            raise SubmissionCommitmentError(
                "tree entries must be in unique ascending UTF-8 path order"
            )
        previous_sort_key = sort_key
        collision_key = _collision_key(path)
        previous = collision_paths.get(collision_key)
        if previous is not None:
            raise SubmissionCommitmentError(
                f"logical path collision between {previous!r} and {path!r}"
            )
        collision_paths[collision_key] = path
        paths.add(path)

        entry_type = entry.get("type")
        if entry_type == "directory":
            if set(entry) != {"path", "type"}:
                raise SubmissionCommitmentError(
                    f"{path}: directory entry has missing or unknown fields"
                )
            directory_paths.add(path)
        elif entry_type == "file":
            if set(entry) != {
                "path",
                "type",
                "bytes",
                "content_sha256",
                "executable",
                "roles",
            }:
                raise SubmissionCommitmentError(f"{path}: file entry has missing or unknown fields")
            byte_count = entry.get("bytes")
            if type(byte_count) is not int or byte_count < 0 or byte_count > MAX_FILE_BYTES:
                raise SubmissionCommitmentError(f"{path}: invalid file byte count")
            if not isinstance(entry.get("content_sha256"), str) or not CHECKSUM_PATTERN.fullmatch(
                str(entry["content_sha256"])
            ):
                raise SubmissionCommitmentError(f"{path}: invalid content checksum")
            if type(entry.get("executable")) is not bool:
                raise SubmissionCommitmentError(f"{path}: executable must be boolean")
            roles = entry.get("roles")
            if (
                not isinstance(roles, list)
                or not roles
                or any(not isinstance(role, str) or role not in ROLE_ORDER for role in roles)
            ):
                raise SubmissionCommitmentError(f"{path}: invalid declared roles")
            expected_roles = [role for role in ROLE_ORDER if role in set(roles)]
            if roles != expected_roles or len(roles) != len(set(roles)):
                raise SubmissionCommitmentError(
                    f"{path}: roles must be unique and in canonical order"
                )
            if "runtime_input" in roles and len(roles) != 1:
                raise SubmissionCommitmentError(
                    f"{path}: runtime_input cannot be combined with explicit roles"
                )
            file_paths.add(path)
        else:
            raise SubmissionCommitmentError(f"{path}: unknown tree entry type")
        normalized_entries.append(entry)

    for path in paths:
        parts = path.split("/")
        for depth in range(1, len(parts)):
            parent = "/".join(parts[:depth])
            if parent not in directory_paths:
                raise SubmissionCommitmentError(
                    f"{path}: parent {parent!r} is not a committed directory"
                )
    if directory_paths & file_paths:
        raise SubmissionCommitmentError("a logical path cannot be both file and directory")
    return normalized_entries, file_paths


def _validate_tree(tree: Mapping[str, Any], entrypoint_path: str) -> None:
    required_keys = {
        "tree_sha256",
        "entry_count",
        "file_count",
        "directory_count",
        "total_bytes",
        "role_counts",
        "entries",
    }
    if set(tree) != required_keys:
        raise SubmissionCommitmentError("tree has missing or unknown fields")
    entries, file_paths = _validate_entry_structure(tree)
    file_entries = [entry for entry in entries if entry["type"] == "file"]
    directory_entries = [entry for entry in entries if entry["type"] == "directory"]
    total_bytes = sum(int(entry["bytes"]) for entry in file_entries)
    if tree.get("entry_count") != len(entries):
        raise SubmissionCommitmentError("tree.entry_count is inconsistent")
    if tree.get("file_count") != len(file_entries):
        raise SubmissionCommitmentError("tree.file_count is inconsistent")
    if tree.get("directory_count") != len(directory_entries):
        raise SubmissionCommitmentError("tree.directory_count is inconsistent")
    if len(directory_entries) > MAX_DIRECTORIES:
        raise SubmissionCommitmentError(f"tree exceeds {MAX_DIRECTORIES} directories")
    if total_bytes > MAX_TOTAL_BYTES or tree.get("total_bytes") != total_bytes:
        raise SubmissionCommitmentError("tree.total_bytes is inconsistent or exceeds its limit")

    role_counts = tree.get("role_counts")
    if not isinstance(role_counts, Mapping) or set(role_counts) != set(ROLE_ORDER):
        raise SubmissionCommitmentError("tree.role_counts is not closed")
    actual_role_counts = {
        role: sum(role in entry["roles"] for entry in file_entries) for role in ROLE_ORDER
    }
    if dict(role_counts) != actual_role_counts:
        raise SubmissionCommitmentError("tree.role_counts is inconsistent")
    if actual_role_counts["entrypoint"] != 1 or actual_role_counts["source"] < 1:
        raise SubmissionCommitmentError(
            "tree must have exactly one entrypoint and at least one source file"
        )
    entrypoint_entries = [entry for entry in file_entries if "entrypoint" in entry["roles"]]
    if (
        entrypoint_path not in file_paths
        or entrypoint_entries[0]["path"] != entrypoint_path
        or "source" not in entrypoint_entries[0]["roles"]
    ):
        raise SubmissionCommitmentError(
            "declared entrypoint must resolve to the unique entrypoint/source file"
        )
    if tree.get("tree_sha256") != submission_tree_digest(tree):
        raise SubmissionCommitmentError("tree_sha256 does not match the tree body")


def validate_submission_commitment(
    value: Mapping[str, Any],
    *,
    schema: Mapping[str, Any] | None = None,
) -> None:
    """Validate the closed schema, semantic invariants, and both self-digests."""

    _check_json_complexity(value)
    required_keys = {
        "schema_version",
        "canonicalization",
        "digest_suite",
        "commitment_id",
        "commitment_sha256",
        "scientific_scope",
        "target",
        "tree",
        "entrypoint",
        "assurance",
    }
    if set(value) != required_keys:
        raise SubmissionCommitmentError(
            "submission commitment has missing or unknown top-level fields"
        )
    _reject_floats(value)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise SubmissionCommitmentError(f"schema_version must equal {SCHEMA_VERSION!r}")
    if value.get("canonicalization") != CANONICALIZATION:
        raise SubmissionCommitmentError(f"canonicalization must equal {CANONICALIZATION!r}")
    if value.get("digest_suite") != DIGEST_SUITE:
        raise SubmissionCommitmentError(f"digest_suite must equal {DIGEST_SUITE!r}")
    if value.get("scientific_scope") != SCIENTIFIC_SCOPE:
        raise SubmissionCommitmentError("scientific_scope is not the closed content-only statement")
    if value.get("assurance") != _assurance():
        raise SubmissionCommitmentError(
            "assurance block cannot claim blind, final, custody, time, "
            "authorship, confidentiality, or runtime status"
        )

    target = value.get("target")
    if (
        not isinstance(target, Mapping)
        or set(target) != {"benchmark_definition_sha256"}
        or not isinstance(target.get("benchmark_definition_sha256"), str)
        or not CHECKSUM_PATTERN.fullmatch(str(target["benchmark_definition_sha256"]))
    ):
        raise SubmissionCommitmentError(
            "target must contain one benchmark-definition sha256 checksum"
        )
    entrypoint = value.get("entrypoint")
    if not isinstance(entrypoint, Mapping) or set(entrypoint) != {
        "kind",
        "path",
        "working_directory",
        "static_arguments",
    }:
        raise SubmissionCommitmentError("entrypoint has missing or unknown fields")
    if (
        entrypoint.get("kind") != "declared_tree_file"
        or entrypoint.get("working_directory") != "."
        or not isinstance(entrypoint.get("path"), str)
    ):
        raise SubmissionCommitmentError("entrypoint declaration is not closed")
    entrypoint_path = normalize_logical_path(str(entrypoint["path"]))
    static_arguments = entrypoint.get("static_arguments")
    if not isinstance(static_arguments, list):
        raise SubmissionCommitmentError("entrypoint.static_arguments must be an array")
    if _validate_static_arguments(static_arguments) != static_arguments:
        raise SubmissionCommitmentError("entrypoint.static_arguments are not canonical")

    tree = value.get("tree")
    if not isinstance(tree, Mapping):
        raise SubmissionCommitmentError("tree must be an object")
    _validate_tree(tree, entrypoint_path)

    effective_schema = schema if schema is not None else _default_submission_schema()
    _check_json_complexity(effective_schema)
    _reject_remote_schema_refs(effective_schema)
    _schema_issues(value, effective_schema)
    expected_digest = submission_commitment_digest(value)
    if value.get("commitment_sha256") != expected_digest:
        raise SubmissionCommitmentError("commitment_sha256 does not match the commitment body")
    if value.get("commitment_id") != f"submission-commitment:{expected_digest}":
        raise SubmissionCommitmentError("commitment_id does not match commitment_sha256")


def _base_entries_from_commitment(value: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    tree = value.get("tree")
    if not isinstance(tree, Mapping):
        return None
    entries = tree.get("entries")
    if not isinstance(entries, list):
        return None
    result: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            return None
        if entry.get("type") == "directory":
            result.append({"path": entry.get("path"), "type": "directory"})
        elif entry.get("type") == "file":
            result.append(
                {
                    "path": entry.get("path"),
                    "type": "file",
                    "bytes": entry.get("bytes"),
                    "content_sha256": entry.get("content_sha256"),
                    "executable": entry.get("executable"),
                }
            )
        else:
            return None
    return result


def verify_submission_commitment(
    value: Mapping[str, Any],
    *,
    root: Path,
    expected_commitment_sha256: str | None = None,
    schema: Mapping[str, Any] | None = None,
) -> SubmissionVerificationReport:
    """Re-enumerate the complete tree and verify one local commitment."""

    actual_digest = submission_commitment_digest(value)
    mismatches: list[str] = []
    try:
        validate_submission_commitment(value, schema=schema)
        self_consistent = True
        entrypoint_bound = True
    except SubmissionCommitmentError as error:
        self_consistent = False
        entrypoint_bound = False
        mismatches.append(str(error))

    snapshot = _stable_tree_snapshot(Path(root))
    expected_base_entries = _base_entries_from_commitment(value)
    tree = value.get("tree")
    tree_counts_match = (
        isinstance(tree, Mapping)
        and tree.get("entry_count") == len(snapshot.entries)
        and tree.get("file_count") == snapshot.file_count
        and tree.get("directory_count") == snapshot.directory_count
        and tree.get("total_bytes") == snapshot.total_bytes
    )
    tree_matches = expected_base_entries == list(snapshot.entries) and tree_counts_match
    if not tree_matches:
        mismatches.append("current submission tree differs from the commitment")

    expected_digest_match: bool | None = None
    if expected_commitment_sha256 is not None:
        if not CHECKSUM_PATTERN.fullmatch(expected_commitment_sha256):
            mismatches.append("externally supplied commitment digest is malformed")
            expected_digest_match = False
        else:
            expected_digest_match = expected_commitment_sha256 == actual_digest
            if not expected_digest_match:
                mismatches.append("externally supplied commitment digest does not match")

    mismatches = mismatches[:MAX_MISMATCHES]
    return SubmissionVerificationReport(
        valid=(
            self_consistent
            and tree_matches
            and expected_digest_match is not False
            and not mismatches
        ),
        self_consistent=self_consistent,
        tree_matches=tree_matches,
        entrypoint_bound=entrypoint_bound,
        expected_digest_match=expected_digest_match,
        commitment_sha256=actual_digest,
        expected_commitment_sha256=expected_commitment_sha256,
        checked_file_count=snapshot.file_count,
        checked_total_bytes=snapshot.total_bytes,
        mismatches=tuple(mismatches),
    )
