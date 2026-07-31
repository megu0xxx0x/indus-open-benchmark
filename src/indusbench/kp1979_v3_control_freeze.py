"""Deterministic, non-operational KP1979 V3 control source bundle.

This module packages only the closed controller-side source and its vendored
offline verification dependency. It does not choose a target round, derive a
suite seed, instantiate generated cases, invoke a worker, evaluate a response,
open one-shot state, or implement a detector, integration binding, or runner.

The gzip stream uses a project-owned stored-DEFLATE encoder so its bytes do not
depend on a zlib implementation. The enclosed tar is a strict canonical USTAR
profile. Verification is bounded and reconstructs both encodings byte for byte.
Git commit authenticity and workflow attestation remain external authorities;
a returned Python object is not an execution or custody attestation.
"""

from __future__ import annotations

import binascii
import contextlib
import hashlib
import json
import os
import secrets
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Never

SUBJECT_NAME = "kp1979-v3-control-bundle.tar.gz"
MANIFEST_NAME = "MANIFEST.json"
MANIFEST_FORMAT = "kp1979-v3-control-bundle-manifest"
MANIFEST_VERSION = 1
PROTOCOL_IDENTITY = "kp1979-v3-closed-answer-free-protocol-v1"
CONTROL_IDENTITY = "kp1979-label-lattice-synthetic-control-v3"
TARGET_ALGORITHM_IDENTITY = "two-column-glyph-lattice-v3"
WORKER_IDENTITY = "kp1979-label-detector-v3-worker-v1"

CASE_INVOCATIONS = 32
METAMORPHIC_ENDPOINT_INVOCATIONS = 16
TOTAL_WORKER_INVOCATIONS = 48

MAX_SOURCE_MEMBER_BYTES = 512 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024
MAX_SUBJECT_BYTES = 16 * 1024 * 1024
_MODULE_NAME = "indusbench.kp1979_v3_control_freeze"
_TAR_BLOCK_BYTES = 512
_DEFLATE_STORED_BLOCK_BYTES = 65_535
_GZIP_HEADER = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff"
_ZERO_TAR_BLOCK = bytes(_TAR_BLOCK_BYTES)
_MODULE_RELATIVE_PATH = "src/indusbench/kp1979_v3_control_freeze.py"
_MODULE_PATH = Path(os.path.abspath(__file__))
_SOURCE_ROOT = _MODULE_PATH.parents[2]
_CONCRETE_PATH_TYPE = type(_MODULE_PATH)

PAYLOAD_PATHS = (
    "LICENSE",
    "schemas/kp1979-v3-control-bundle-manifest.schema.json",
    "src/indusbench/__init__.py",
    "src/indusbench/_vendor/noble/VENDOR_MANIFEST.json",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/LICENSE",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/abstract/bls.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/abstract/curve.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/abstract/hash-to-curve.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/abstract/modular.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/abstract/tower.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/abstract/weierstrass.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/bls12-381.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/package.json",
    "src/indusbench/_vendor/noble/node_modules/@noble/curves/utils.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/hashes/LICENSE",
    "src/indusbench/_vendor/noble/node_modules/@noble/hashes/_md.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/hashes/_u64.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/hashes/cryptoNode.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/hashes/hmac.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/hashes/package.json",
    "src/indusbench/_vendor/noble/node_modules/@noble/hashes/sha2.js",
    "src/indusbench/_vendor/noble/node_modules/@noble/hashes/utils.js",
    "src/indusbench/_vendor/noble/quicknet_verify.cjs",
    "src/indusbench/kp1979_v3_canvas.py",
    "src/indusbench/kp1979_v3_control_freeze.py",
    "src/indusbench/kp1979_v3_evaluator.py",
    "src/indusbench/kp1979_v3_generator.py",
    "src/indusbench/kp1979_v3_grammar.py",
    "src/indusbench/kp1979_v3_prf.py",
    "src/indusbench/kp1979_v3_protocol.py",
    "src/indusbench/kp1979_v3_quicknet.py",
    "src/indusbench/kp1979_v3_renderer_a.py",
    "src/indusbench/kp1979_v3_renderer_b.py",
    "src/indusbench/kp1979_v3_sandbox.py",
    "src/indusbench/kp1979_v3_state.py",
    "src/indusbench/kp1979_v3_wire.py",
)
_ARCHIVE_PATHS = tuple(sorted((MANIFEST_NAME, *PAYLOAD_PATHS)))
_FORBIDDEN_SOURCE_COMPONENTS = (
    "src/indusbench/kp1979_v3_controller.py",
    "src/indusbench/kp1979_v3_detector.py",
    "src/indusbench/kp1979_v3_detector_freeze.py",
    "src/indusbench/kp1979_v3_integration.py",
    "src/indusbench/kp1979_v3_integration_freeze.py",
    "src/indusbench/kp1979_v3_runner.py",
)
_LOWER_HEX = frozenset("0123456789abcdef")
_MANIFEST_KEYS = frozenset(
    {
        "format",
        "version",
        "source_commit",
        "protocol_identity",
        "control_identity",
        "target_algorithm_identity",
        "worker_identity",
        "case_invocations",
        "metamorphic_endpoint_invocations",
        "total_worker_invocations",
        "source_only",
        "non_operational",
        "target_round_selected",
        "detector_component",
        "integration_binding",
        "payload",
    }
)

__all__ = (
    "PAYLOAD_PATHS",
    "SUBJECT_NAME",
    "ControlFreezeErrorCode",
    "KP1979V3ControlFreezeError",
    "VerifiedControlBundle",
    "build_control_bundle",
    "main",
    "verify_control_bundle",
)


class ControlFreezeErrorCode(StrEnum):
    """Stable path- and detail-free source-freeze failure codes."""

    INVALID_ARGUMENT = "invalid_argument"
    INVALID_ENVIRONMENT = "invalid_environment"
    UNSAFE_SOURCE = "unsafe_source"
    SOURCE_CHANGED = "source_changed"
    INVALID_BUNDLE = "invalid_bundle"
    UNSAFE_OUTPUT = "unsafe_output"
    OUTPUT_EXISTS = "output_exists"
    OUTPUT_WRITE_FAILED = "output_write_failed"


class KP1979V3ControlFreezeError(RuntimeError):
    """A stable failure that never includes a local path or parser detail."""

    def __init__(self, code: ControlFreezeErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class VerifiedControlBundle:
    """Minimal verification summary; not an execution attestation."""

    source_commit: str
    member_count: int
    payload_count: int
    uncompressed_size: int
    subject_sha256: str


@dataclass(frozen=True, slots=True)
class _PinnedOutputParent:
    descriptors: tuple[int, ...]
    fingerprints: tuple[tuple[int, ...], ...]
    names: tuple[str, ...]

    @property
    def descriptor(self) -> int:
        return self.descriptors[-1]


@dataclass(frozen=True, slots=True)
class _PinnedSourceRoot:
    descriptors: tuple[int, ...]
    fingerprints: tuple[tuple[int, ...], ...]
    names: tuple[str, ...]
    root_fingerprint: tuple[int, ...]

    @property
    def descriptor(self) -> int:
        return self.descriptors[-1]


def _raise(code: ControlFreezeErrorCode) -> Never:
    raise KP1979V3ControlFreezeError(code) from None


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and value.isascii()
        and all(character in _LOWER_HEX for character in value)
    )


def _require_source_commit(value: object) -> str:
    if not _is_lower_hex(value, 40):
        _raise(ControlFreezeErrorCode.INVALID_ARGUMENT)
    assert isinstance(value, str)
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeError):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)


def _duplicate_rejecting_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        value[key] = item
    return value


def _reject_json_constant(_value: str) -> Never:
    _raise(ControlFreezeErrorCode.INVALID_BUNDLE)


def _load_canonical_manifest(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_MANIFEST_BYTES:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    try:
        value: Any = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_json_constant,
        )
    except KP1979V3ControlFreezeError:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    if type(value) is not dict or _canonical_json_bytes(value) != raw:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return value


def _stat_fingerprint(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _directory_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
    )


def _directory_flags() -> int:
    required = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    if os.name != "posix" or any(not hasattr(os, name) for name in required):
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    return os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW


def _file_read_flags() -> int:
    required = ("O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK")
    if os.name != "posix" or any(not hasattr(os, name) for name in required):
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    return os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK


def _require_safe_source_directory(value: os.stat_result) -> None:
    mode = stat.S_IMODE(value.st_mode)
    if (
        not stat.S_ISDIR(value.st_mode)
        or value.st_uid != os.geteuid()
        or value.st_nlink < 1
        or mode & 0o022
        or mode & (stat.S_ISUID | stat.S_ISGID)
    ):
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)


def _require_safe_source_file(value: os.stat_result) -> None:
    mode = stat.S_IMODE(value.st_mode)
    if (
        not stat.S_ISREG(value.st_mode)
        or value.st_uid != os.geteuid()
        or value.st_nlink != 1
        or value.st_size < 1
        or value.st_size > MAX_SOURCE_MEMBER_BYTES
        or mode & 0o022
        or mode & 0o111
        or mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)
    ):
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)


def _require_safe_source_ancestor(value: os.stat_result, *, final: bool) -> None:
    mode = stat.S_IMODE(value.st_mode)
    effective_uid = os.geteuid()
    root_sticky_boundary = value.st_uid == 0 and bool(mode & stat.S_ISVTX) and bool(mode & 0o002)
    if (
        not stat.S_ISDIR(value.st_mode)
        or value.st_nlink < 1
        or value.st_uid not in {0, effective_uid}
        or mode & (stat.S_ISUID | stat.S_ISGID)
        or (mode & 0o022 and not root_sticky_boundary)
        or (final and (value.st_uid != effective_uid or mode & 0o022))
    ):
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)


def _open_source_root() -> _PinnedSourceRoot:
    path = _SOURCE_ROOT
    if (
        type(path) is not _CONCRETE_PATH_TYPE
        or type(_MODULE_PATH) is not _CONCRETE_PATH_TYPE
        or not path.is_absolute()
        or path.anchor != "/"
        or str(path) != os.path.abspath(path)
        or path == Path("/")
        or any(part in {"", ".", ".."} for part in str(path).split("/")[1:])
        or path / _MODULE_RELATIVE_PATH != _MODULE_PATH
        or _MODULE_PATH.parts[-3:] != ("src", "indusbench", "kp1979_v3_control_freeze.py")
    ):
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    descriptors: list[int] = []
    fingerprints: list[tuple[int, ...]] = []
    names: list[str] = []
    try:
        current = os.open("/", _directory_flags())
        descriptors.append(current)
        value = os.fstat(current)
        _require_safe_source_ancestor(value, final=False)
        fingerprints.append(_directory_identity(value))
        components = path.parts[1:]
        for index, component in enumerate(components):
            current = os.open(component, _directory_flags(), dir_fd=current)
            descriptors.append(current)
            names.append(component)
            value = os.fstat(current)
            _require_safe_source_ancestor(value, final=index == len(components) - 1)
            fingerprints.append(_directory_identity(value))
        _require_safe_source_directory(value)
        return _PinnedSourceRoot(
            tuple(descriptors),
            tuple(fingerprints),
            tuple(names),
            _stat_fingerprint(value),
        )
    except KP1979V3ControlFreezeError:
        for descriptor in reversed(descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        raise
    except (OSError, TypeError, ValueError):
        for descriptor in reversed(descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    except BaseException:
        for descriptor in reversed(descriptors):
            with contextlib.suppress(BaseException):
                os.close(descriptor)
        raise


def _revalidate_source_root(root: _PinnedSourceRoot) -> None:
    if len(root.descriptors) != len(root.fingerprints) or len(root.names) + 1 != len(
        root.descriptors
    ):
        _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
    for index, (descriptor, fingerprint) in enumerate(
        zip(root.descriptors, root.fingerprints, strict=True)
    ):
        try:
            current = os.fstat(descriptor)
        except OSError:
            _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
        if _directory_identity(current) != fingerprint:
            _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
        if index:
            try:
                namespace_value = os.stat(
                    root.names[index - 1],
                    dir_fd=root.descriptors[index - 1],
                    follow_symlinks=False,
                )
            except OSError:
                _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
            if _directory_identity(namespace_value) != fingerprint:
                _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
    try:
        current_root = os.fstat(root.descriptor)
    except OSError:
        _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
    if _stat_fingerprint(current_root) != root.root_fingerprint:
        _raise(ControlFreezeErrorCode.SOURCE_CHANGED)


def _validated_member_parts(path: str) -> tuple[str, ...]:
    if type(path) is not str or not path or not path.isascii() or "\\" in path:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    pure = PurePosixPath(path)
    parts = pure.parts
    if (
        pure.is_absolute()
        or str(pure) != path
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
    ):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return parts


def _open_source_child_directory(parent: int, name: str) -> tuple[int, tuple[int, ...]]:
    descriptor: int | None = None
    completed = False
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent)
        current = os.fstat(descriptor)
        _require_safe_source_directory(current)
        fingerprint = _stat_fingerprint(current)
        completed = True
        return descriptor, fingerprint
    except OSError:
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    finally:
        if descriptor is not None and not completed:
            with contextlib.suppress(OSError):
                os.close(descriptor)


def _read_source_member(root: int, path: str) -> bytes:
    parts = _validated_member_parts(path)
    opened_directories: list[tuple[int, str, int, tuple[int, ...]]] = []
    current = root
    descriptor: int | None = None
    try:
        for component in parts[:-1]:
            parent = current
            child, fingerprint = _open_source_child_directory(parent, component)
            opened_directories.append((parent, component, child, fingerprint))
            current = child
        try:
            descriptor = os.open(parts[-1], _file_read_flags(), dir_fd=current)
            before = os.fstat(descriptor)
        except OSError:
            _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
        _require_safe_source_file(before)
        chunks: list[bytes] = []
        size = 0
        while True:
            block = os.read(descriptor, min(65_536, MAX_SOURCE_MEMBER_BYTES + 1 - size))
            if not block:
                break
            chunks.append(block)
            size += len(block)
            if size > MAX_SOURCE_MEMBER_BYTES:
                _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
        try:
            after = os.fstat(descriptor)
            leaf_namespace = os.stat(
                parts[-1],
                dir_fd=current,
                follow_symlinks=False,
            )
            directory_values = tuple(
                (
                    os.fstat(directory),
                    os.stat(name, dir_fd=parent, follow_symlinks=False),
                )
                for parent, name, directory, _fingerprint in opened_directories
            )
        except OSError:
            _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
        if _stat_fingerprint(before) != _stat_fingerprint(after) or size != before.st_size:
            _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
        if _stat_fingerprint(leaf_namespace) != _stat_fingerprint(before):
            _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
        for (
            (_parent, _name, _directory, fingerprint),
            (directory_value, namespace_value),
        ) in zip(opened_directories, directory_values, strict=True):
            if (
                _stat_fingerprint(directory_value) != fingerprint
                or _stat_fingerprint(namespace_value) != fingerprint
            ):
                _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
        return b"".join(chunks)
    except KP1979V3ControlFreezeError:
        raise
    except OSError:
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    finally:
        if descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        for _parent, _name, directory, _fingerprint in reversed(opened_directories):
            with contextlib.suppress(OSError):
                os.close(directory)


def _relative_source_component_exists(root: int, path: str) -> bool:
    parts = _validated_member_parts(path)
    opened: list[int] = []
    current = root
    try:
        for component in parts[:-1]:
            child: int | None = None
            try:
                child = os.open(component, _directory_flags(), dir_fd=current)
            except FileNotFoundError:
                return False
            try:
                _require_safe_source_directory(os.fstat(child))
            except BaseException:
                with contextlib.suppress(OSError):
                    os.close(child)
                raise
            opened.append(child)
            current = child
        try:
            os.stat(parts[-1], dir_fd=current, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True
    except KP1979V3ControlFreezeError:
        raise
    except OSError:
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    finally:
        for descriptor in reversed(opened):
            with contextlib.suppress(OSError):
                os.close(descriptor)


def _load_source_payloads() -> dict[str, bytes]:
    if (
        len(PAYLOAD_PATHS) != 36
        or tuple(sorted(PAYLOAD_PATHS)) != PAYLOAD_PATHS
        or len(set(PAYLOAD_PATHS)) != len(PAYLOAD_PATHS)
        or len(_ARCHIVE_PATHS) != 37
    ):
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    root = _open_source_root()
    try:
        if any(
            _relative_source_component_exists(root.descriptor, path)
            for path in _FORBIDDEN_SOURCE_COMPONENTS
        ):
            _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
        payloads: dict[str, bytes] = {}
        total = 0
        for path in PAYLOAD_PATHS:
            _revalidate_source_root(root)
            raw = _read_source_member(root.descriptor, path)
            total += len(raw)
            if total > MAX_UNCOMPRESSED_BYTES:
                _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
            payloads[path] = raw
        _revalidate_source_root(root)
        if any(
            _relative_source_component_exists(root.descriptor, path)
            for path in _FORBIDDEN_SOURCE_COMPONENTS
        ):
            _raise(ControlFreezeErrorCode.SOURCE_CHANGED)
        _revalidate_source_root(root)
        return payloads
    finally:
        for descriptor in reversed(root.descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)


def _manifest_for(source_commit: str, payloads: Mapping[str, bytes]) -> dict[str, object]:
    if tuple(payloads) != PAYLOAD_PATHS:
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    payload = [
        {
            "path": path,
            "sha256": hashlib.sha256(payloads[path]).hexdigest(),
            "size": len(payloads[path]),
        }
        for path in PAYLOAD_PATHS
    ]
    return {
        "case_invocations": CASE_INVOCATIONS,
        "control_identity": CONTROL_IDENTITY,
        "detector_component": "absent",
        "format": MANIFEST_FORMAT,
        "integration_binding": "absent",
        "metamorphic_endpoint_invocations": METAMORPHIC_ENDPOINT_INVOCATIONS,
        "non_operational": True,
        "payload": payload,
        "protocol_identity": PROTOCOL_IDENTITY,
        "source_commit": source_commit,
        "source_only": True,
        "target_algorithm_identity": TARGET_ALGORITHM_IDENTITY,
        "target_round_selected": False,
        "total_worker_invocations": TOTAL_WORKER_INVOCATIONS,
        "version": MANIFEST_VERSION,
        "worker_identity": WORKER_IDENTITY,
    }


def _tar_name_field(path: str) -> bytes:
    _validated_member_parts(path)
    encoded = path.encode("ascii")
    if len(encoded) > 99:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return encoded + bytes(100 - len(encoded))


def _tar_octal(value: int, width: int) -> bytes:
    if type(value) is not int or value < 0:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    encoded = f"{value:0{width - 1}o}".encode("ascii") + b"\0"
    if len(encoded) != width:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return encoded


def _tar_header(path: str, size: int) -> bytes:
    if type(size) is not int or size < 0 or size > MAX_SOURCE_MEMBER_BYTES:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    header = bytearray(_TAR_BLOCK_BYTES)
    header[0:100] = _tar_name_field(path)
    header[100:108] = b"0000644\0"
    header[108:116] = b"0000000\0"
    header[116:124] = b"0000000\0"
    header[124:136] = _tar_octal(size, 12)
    header[136:148] = b"00000000000\0"
    header[148:156] = b"        "
    header[156:157] = b"0"
    header[257:263] = b"ustar\0"
    header[263:265] = b"00"
    checksum = sum(header)
    checksum_field = f"{checksum:06o}\0 ".encode("ascii")
    if len(checksum_field) != 8:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    header[148:156] = checksum_field
    return bytes(header)


def _encode_tar(members: Mapping[str, bytes]) -> bytes:
    names = tuple(sorted(members))
    if len(names) != len(members) or any(type(members[name]) is not bytes for name in names):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    output = bytearray()
    for name in names:
        raw = members[name]
        if not raw or len(raw) > MAX_SOURCE_MEMBER_BYTES:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        output.extend(_tar_header(name, len(raw)))
        output.extend(raw)
        padding = (-len(raw)) % _TAR_BLOCK_BYTES
        output.extend(bytes(padding))
        if len(output) + (2 * _TAR_BLOCK_BYTES) > MAX_UNCOMPRESSED_BYTES:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    output.extend(_ZERO_TAR_BLOCK)
    output.extend(_ZERO_TAR_BLOCK)
    return bytes(output)


def _encode_stored_gzip(raw: bytes) -> bytes:
    if type(raw) is not bytes or not raw or len(raw) > MAX_UNCOMPRESSED_BYTES:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    output = bytearray(_GZIP_HEADER)
    position = 0
    while position < len(raw):
        end = min(position + _DEFLATE_STORED_BLOCK_BYTES, len(raw))
        block = raw[position:end]
        final = end == len(raw)
        output.append(1 if final else 0)
        length = len(block)
        output.extend(length.to_bytes(2, "little"))
        output.extend((length ^ 0xFFFF).to_bytes(2, "little"))
        output.extend(block)
        position = end
    output.extend((binascii.crc32(raw) & 0xFFFFFFFF).to_bytes(4, "little"))
    output.extend((len(raw) & 0xFFFFFFFF).to_bytes(4, "little"))
    if len(output) > MAX_SUBJECT_BYTES:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return bytes(output)


def _decode_stored_gzip(subject: bytes) -> bytes:
    if (
        type(subject) is not bytes
        or len(subject) < len(_GZIP_HEADER) + 5 + 8
        or len(subject) > MAX_SUBJECT_BYTES
        or subject[: len(_GZIP_HEADER)] != _GZIP_HEADER
    ):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    position = len(_GZIP_HEADER)
    output = bytearray()
    block_count = 0
    while True:
        if position + 5 > len(subject):
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        marker = subject[position]
        position += 1
        if marker not in {0, 1}:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        final = marker == 1
        length = int.from_bytes(subject[position : position + 2], "little")
        inverse = int.from_bytes(subject[position + 2 : position + 4], "little")
        position += 4
        if inverse != (length ^ 0xFFFF):
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        if (not final and length != _DEFLATE_STORED_BLOCK_BYTES) or (
            final and not 1 <= length <= _DEFLATE_STORED_BLOCK_BYTES
        ):
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        if position + length > len(subject):
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        output.extend(subject[position : position + length])
        position += length
        block_count += 1
        if (
            len(output) > MAX_UNCOMPRESSED_BYTES
            or block_count > (MAX_UNCOMPRESSED_BYTES // _DEFLATE_STORED_BLOCK_BYTES) + 2
        ):
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        if final:
            break
    if position + 8 != len(subject):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    raw = bytes(output)
    expected_crc = int.from_bytes(subject[position : position + 4], "little")
    expected_size = int.from_bytes(subject[position + 4 : position + 8], "little")
    if (
        expected_crc != (binascii.crc32(raw) & 0xFFFFFFFF)
        or expected_size != len(raw)
        or _encode_stored_gzip(raw) != subject
    ):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return raw


def _decode_tar_name(field: bytes) -> str:
    if len(field) != 100:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    try:
        end = field.index(0)
    except ValueError:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    if end == 0 or any(field[end + 1 :]):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    try:
        value = field[:end].decode("ascii")
    except UnicodeError:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    _validated_member_parts(value)
    if _tar_name_field(value) != field:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return value


def _decode_tar_size(field: bytes) -> int:
    if (
        len(field) != 12
        or field[-1:] != b"\0"
        or any(value not in b"01234567" for value in field[:-1])
    ):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    try:
        size = int(field[:-1], 8)
    except ValueError:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    if size > MAX_SOURCE_MEMBER_BYTES or _tar_octal(size, 12) != field:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return size


def _decode_tar(tar_bytes: bytes) -> dict[str, bytes]:
    if (
        type(tar_bytes) is not bytes
        or not tar_bytes
        or len(tar_bytes) > MAX_UNCOMPRESSED_BYTES
        or len(tar_bytes) % _TAR_BLOCK_BYTES
        or len(tar_bytes) < 3 * _TAR_BLOCK_BYTES
        or tar_bytes[-2 * _TAR_BLOCK_BYTES :] != _ZERO_TAR_BLOCK * 2
    ):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    terminal_offset = len(tar_bytes) - (2 * _TAR_BLOCK_BYTES)
    position = 0
    members: dict[str, bytes] = {}
    previous_name: str | None = None
    while position < terminal_offset:
        if position + _TAR_BLOCK_BYTES > terminal_offset:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        header = tar_bytes[position : position + _TAR_BLOCK_BYTES]
        position += _TAR_BLOCK_BYTES
        if header == _ZERO_TAR_BLOCK:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        name = _decode_tar_name(header[0:100])
        size = _decode_tar_size(header[124:136])
        comparison_header = bytearray(header)
        comparison_header[148:156] = b"        "
        checksum_field = f"{sum(comparison_header):06o}\0 ".encode("ascii")
        if (
            header[100:108] != b"0000644\0"
            or header[108:116] != b"0000000\0"
            or header[116:124] != b"0000000\0"
            or header[136:148] != b"00000000000\0"
            or header[148:156] != checksum_field
            or header[156:157] != b"0"
            or any(header[157:257])
            or header[257:263] != b"ustar\0"
            or header[263:265] != b"00"
            or any(header[265:512])
            or _tar_header(name, size) != header
        ):
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        if previous_name is not None and name <= previous_name:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        if name in members:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        previous_name = name
        padded_size = size + ((-size) % _TAR_BLOCK_BYTES)
        if position + padded_size > terminal_offset:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        raw = tar_bytes[position : position + size]
        padding = tar_bytes[position + size : position + padded_size]
        if not raw or any(padding):
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        members[name] = raw
        position += padded_size
    if position != terminal_offset or _encode_tar(members) != tar_bytes:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    return members


def _validate_manifest(
    manifest: dict[str, object],
    members: Mapping[str, bytes],
    expected_source_commit: str,
) -> None:
    if frozenset(manifest) != _MANIFEST_KEYS:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    fixed_values: tuple[tuple[str, object, object], ...] = (
        ("format", manifest["format"], MANIFEST_FORMAT),
        ("version", manifest["version"], MANIFEST_VERSION),
        ("protocol_identity", manifest["protocol_identity"], PROTOCOL_IDENTITY),
        ("control_identity", manifest["control_identity"], CONTROL_IDENTITY),
        (
            "target_algorithm_identity",
            manifest["target_algorithm_identity"],
            TARGET_ALGORITHM_IDENTITY,
        ),
        ("worker_identity", manifest["worker_identity"], WORKER_IDENTITY),
        ("case_invocations", manifest["case_invocations"], CASE_INVOCATIONS),
        (
            "metamorphic_endpoint_invocations",
            manifest["metamorphic_endpoint_invocations"],
            METAMORPHIC_ENDPOINT_INVOCATIONS,
        ),
        (
            "total_worker_invocations",
            manifest["total_worker_invocations"],
            TOTAL_WORKER_INVOCATIONS,
        ),
        ("source_only", manifest["source_only"], True),
        ("non_operational", manifest["non_operational"], True),
        ("target_round_selected", manifest["target_round_selected"], False),
        ("detector_component", manifest["detector_component"], "absent"),
        ("integration_binding", manifest["integration_binding"], "absent"),
    )
    for _name, actual, expected in fixed_values:
        if type(actual) is not type(expected) or actual != expected:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    if (
        not _is_lower_hex(manifest["source_commit"], 40)
        or manifest["source_commit"] != expected_source_commit
    ):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    payload = manifest["payload"]
    if type(payload) is not list or len(payload) != len(PAYLOAD_PATHS):
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    for index, expected_path in enumerate(PAYLOAD_PATHS):
        entry = payload[index]
        if type(entry) is not dict or frozenset(entry) != {"path", "sha256", "size"}:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        path = entry["path"]
        digest = entry["sha256"]
        size = entry["size"]
        if (
            type(path) is not str
            or path != expected_path
            or type(size) is not int
            or not 1 <= size <= MAX_SOURCE_MEMBER_BYTES
            or not _is_lower_hex(digest, 64)
            or path not in members
            or len(members[path]) != size
            or hashlib.sha256(members[path]).hexdigest() != digest
        ):
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
    if MANIFEST_NAME in {entry["path"] for entry in payload if type(entry) is dict}:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)


def _build_control_bundle(source_commit: str) -> bytes:
    payloads = _load_source_payloads()
    manifest = _manifest_for(source_commit, payloads)
    members = {**payloads, MANIFEST_NAME: _canonical_json_bytes(manifest)}
    if tuple(sorted(members)) != _ARCHIVE_PATHS:
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)
    tar_bytes = _encode_tar(members)
    return _encode_stored_gzip(tar_bytes)


def build_control_bundle(*, source_commit: str) -> bytes:
    """Build the source-only subject from the internally fixed checkout root."""

    commit = _require_source_commit(source_commit)
    try:
        subject = _build_control_bundle(commit)
        verify_control_bundle(subject, expected_source_commit=commit)
        return subject
    except KP1979V3ControlFreezeError:
        raise
    except Exception:
        _raise(ControlFreezeErrorCode.UNSAFE_SOURCE)


def verify_control_bundle(
    subject: bytes,
    *,
    expected_source_commit: str,
) -> VerifiedControlBundle:
    """Verify bounds, canonical gzip/USTAR, roster, manifest, and payload hashes."""

    commit = _require_source_commit(expected_source_commit)
    try:
        tar_bytes = _decode_stored_gzip(subject)
        members = _decode_tar(tar_bytes)
        if tuple(members) != _ARCHIVE_PATHS or len(members) != 37:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        manifest = _load_canonical_manifest(members[MANIFEST_NAME])
        _validate_manifest(manifest, members, commit)
        if _encode_stored_gzip(_encode_tar(members)) != subject:
            _raise(ControlFreezeErrorCode.INVALID_BUNDLE)
        return VerifiedControlBundle(
            source_commit=commit,
            member_count=len(members),
            payload_count=len(PAYLOAD_PATHS),
            uncompressed_size=len(tar_bytes),
            subject_sha256=hashlib.sha256(subject).hexdigest(),
        )
    except KP1979V3ControlFreezeError:
        raise
    except Exception:
        _raise(ControlFreezeErrorCode.INVALID_BUNDLE)


def _validated_output_path(raw: object) -> Path:
    if (
        type(raw) is not str
        or not raw
        or "\x00" in raw
        or any("\ud800" <= character <= "\udfff" for character in raw)
    ):
        _raise(ControlFreezeErrorCode.INVALID_ARGUMENT)
    try:
        path = Path(raw)
        encoded = os.fsencode(raw)
    except (TypeError, UnicodeError, ValueError):
        _raise(ControlFreezeErrorCode.INVALID_ARGUMENT)
    if (
        not encoded
        or not path.is_absolute()
        or path.anchor != "/"
        or str(path) != raw
        or path.name != SUBJECT_NAME
        or path.parent == Path("/")
        or any(part in {"", ".", ".."} for part in raw.split("/")[1:])
    ):
        _raise(ControlFreezeErrorCode.INVALID_ARGUMENT)
    return path


def _require_safe_output_ancestor(value: os.stat_result, *, final: bool) -> None:
    mode = stat.S_IMODE(value.st_mode)
    effective_uid = os.geteuid()
    root_sticky_boundary = value.st_uid == 0 and bool(mode & stat.S_ISVTX) and bool(mode & 0o002)
    if (
        not stat.S_ISDIR(value.st_mode)
        or value.st_nlink < 1
        or value.st_uid not in {0, effective_uid}
        or mode & (stat.S_ISUID | stat.S_ISGID)
        or (mode & 0o022 and not root_sticky_boundary)
        or (final and (value.st_uid != effective_uid or mode != 0o700))
    ):
        _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)


def _open_output_parent(path: Path) -> _PinnedOutputParent:
    if os.name != "posix" or not hasattr(os, "geteuid"):
        _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
    flags = _directory_flags()
    descriptors: list[int] = []
    fingerprints: list[tuple[int, ...]] = []
    names: list[str] = []
    try:
        current = os.open("/", flags)
        descriptors.append(current)
        root_value = os.fstat(current)
        _require_safe_output_ancestor(root_value, final=False)
        fingerprints.append(_directory_identity(root_value))
        components = path.parent.parts[1:]
        if not components:
            _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
        for index, component in enumerate(components):
            current = os.open(component, flags, dir_fd=current)
            descriptors.append(current)
            names.append(component)
            value = os.fstat(current)
            _require_safe_output_ancestor(value, final=index == len(components) - 1)
            fingerprints.append(_directory_identity(value))
        return _PinnedOutputParent(tuple(descriptors), tuple(fingerprints), tuple(names))
    except KP1979V3ControlFreezeError:
        for descriptor in reversed(descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        raise
    except OSError:
        for descriptor in reversed(descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
    except BaseException:
        for descriptor in reversed(descriptors):
            with contextlib.suppress(BaseException):
                os.close(descriptor)
        raise


def _revalidate_output_parent(parent: _PinnedOutputParent) -> None:
    if len(parent.descriptors) != len(parent.fingerprints) or len(parent.names) + 1 != len(
        parent.descriptors
    ):
        _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
    for index, (descriptor, fingerprint) in enumerate(
        zip(parent.descriptors, parent.fingerprints, strict=True)
    ):
        try:
            current = os.fstat(descriptor)
        except OSError:
            _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
        if _directory_identity(current) != fingerprint:
            _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
        if index:
            try:
                namespace_value = os.stat(
                    parent.names[index - 1],
                    dir_fd=parent.descriptors[index - 1],
                    follow_symlinks=False,
                )
            except OSError:
                _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
            if _directory_identity(namespace_value) != fingerprint:
                _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)


def _output_exists(parent: int) -> bool:
    try:
        os.stat(SUBJECT_NAME, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError:
        _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
    return True


def _create_staging_file(parent: int) -> tuple[int, str]:
    required = ("O_CLOEXEC", "O_NOFOLLOW")
    if any(not hasattr(os, name) for name in required):
        _raise(ControlFreezeErrorCode.UNSAFE_OUTPUT)
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    for _attempt in range(8):
        name = f".kp1979-v3-control-freeze.{secrets.token_hex(16)}.tmp"
        try:
            descriptor = os.open(name, flags, 0o600, dir_fd=parent)
        except FileExistsError:
            continue
        except OSError:
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        try:
            os.fchmod(descriptor, 0o600)
            value = os.fstat(descriptor)
            if (
                not stat.S_ISREG(value.st_mode)
                or stat.S_IMODE(value.st_mode) != 0o600
                or value.st_uid != os.geteuid()
                or value.st_nlink != 1
                or value.st_size != 0
            ):
                _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        except BaseException:
            with contextlib.suppress(OSError):
                os.close(descriptor)
            with contextlib.suppress(OSError):
                os.unlink(name, dir_fd=parent)
            raise
        return descriptor, name
    _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)


def _write_all(descriptor: int, raw: bytes) -> None:
    position = 0
    while position < len(raw):
        try:
            written = os.write(descriptor, raw[position:])
        except OSError:
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        if written <= 0:
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        position += written


def _verify_written_output(
    parent: int,
    expected: bytes,
    expected_identity: tuple[int, int],
) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(SUBJECT_NAME, _file_read_flags(), dir_fd=parent)
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        size = 0
        while True:
            block = os.read(descriptor, min(65_536, MAX_SUBJECT_BYTES + 1 - size))
            if not block:
                break
            chunks.append(block)
            size += len(block)
            if size > MAX_SUBJECT_BYTES:
                _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        after = os.fstat(descriptor)
        namespace_value = os.stat(
            SUBJECT_NAME,
            dir_fd=parent,
            follow_symlinks=False,
        )
    except KP1979V3ControlFreezeError:
        raise
    except OSError:
        _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
    finally:
        if descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(descriptor)
    if (
        _stat_fingerprint(before) != _stat_fingerprint(after)
        or _stat_fingerprint(namespace_value) != _stat_fingerprint(after)
        or (before.st_dev, before.st_ino) != expected_identity
        or (after.st_dev, after.st_ino) != expected_identity
        or (namespace_value.st_dev, namespace_value.st_ino) != expected_identity
        or not stat.S_ISREG(after.st_mode)
        or stat.S_IMODE(after.st_mode) != 0o600
        or after.st_uid != os.geteuid()
        or after.st_nlink != 1
        or after.st_size != len(expected)
        or b"".join(chunks) != expected
    ):
        _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)


def _unlink_owned_output_if_present(
    parent: int,
    staging_descriptor: int,
    staging_identity: tuple[int, int],
) -> None:
    try:
        descriptor_value = os.fstat(staging_descriptor)
        namespace_value = os.stat(
            SUBJECT_NAME,
            dir_fd=parent,
            follow_symlinks=False,
        )
        if (descriptor_value.st_dev, descriptor_value.st_ino) != staging_identity or (
            namespace_value.st_dev,
            namespace_value.st_ino,
        ) != staging_identity:
            return
        os.unlink(SUBJECT_NAME, dir_fd=parent)
        os.fsync(parent)
    except OSError:
        return


def _write_subject_no_replace(path: Path, subject: bytes) -> None:
    if type(subject) is not bytes or not subject or len(subject) > MAX_SUBJECT_BYTES:
        _raise(ControlFreezeErrorCode.INVALID_ARGUMENT)
    parent = _open_output_parent(path)
    staging_descriptor: int | None = None
    staging_name: str | None = None
    linked = False
    link_attempted = False
    completed = False
    staging_identity: tuple[int, int] | None = None
    try:
        _revalidate_output_parent(parent)
        if _output_exists(parent.descriptor):
            _raise(ControlFreezeErrorCode.OUTPUT_EXISTS)
        staging_descriptor, staging_name = _create_staging_file(parent.descriptor)
        _write_all(staging_descriptor, subject)
        os.fsync(staging_descriptor)
        staging_value = os.fstat(staging_descriptor)
        if (
            not stat.S_ISREG(staging_value.st_mode)
            or stat.S_IMODE(staging_value.st_mode) != 0o600
            or staging_value.st_uid != os.geteuid()
            or staging_value.st_nlink != 1
            or staging_value.st_size != len(subject)
        ):
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        staging_identity = (staging_value.st_dev, staging_value.st_ino)
        try:
            staging_namespace = os.stat(
                staging_name,
                dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
        except OSError:
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        if _stat_fingerprint(staging_namespace) != _stat_fingerprint(staging_value):
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        _revalidate_output_parent(parent)
        link_attempted = True
        try:
            os.link(
                staging_name,
                SUBJECT_NAME,
                src_dir_fd=parent.descriptor,
                dst_dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
        except FileExistsError:
            _raise(ControlFreezeErrorCode.OUTPUT_EXISTS)
        except OSError:
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        linked = True
        try:
            linked_staging = os.stat(
                staging_name,
                dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
            linked_output = os.stat(
                SUBJECT_NAME,
                dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
            linked_descriptor = os.fstat(staging_descriptor)
        except OSError:
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        if (
            staging_identity is None
            or (linked_staging.st_dev, linked_staging.st_ino) != staging_identity
            or (linked_output.st_dev, linked_output.st_ino) != staging_identity
            or (linked_descriptor.st_dev, linked_descriptor.st_ino) != staging_identity
            or linked_staging.st_nlink != 2
            or linked_output.st_nlink != 2
            or linked_descriptor.st_nlink != 2
            or not stat.S_ISREG(linked_output.st_mode)
            or stat.S_IMODE(linked_output.st_mode) != 0o600
            or linked_output.st_uid != os.geteuid()
            or linked_output.st_size != len(subject)
        ):
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        os.unlink(staging_name, dir_fd=parent.descriptor)
        staging_name = None
        if os.fstat(staging_descriptor).st_nlink != 1:
            _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
        os.fsync(parent.descriptor)
        _revalidate_output_parent(parent)
        _verify_written_output(
            parent.descriptor,
            subject,
            staging_identity,
        )
        completed = True
    except KP1979V3ControlFreezeError:
        raise
    except OSError:
        _raise(ControlFreezeErrorCode.OUTPUT_WRITE_FAILED)
    finally:
        if (
            link_attempted
            and not completed
            and staging_descriptor is not None
            and staging_identity is not None
        ):
            _unlink_owned_output_if_present(
                parent.descriptor,
                staging_descriptor,
                staging_identity,
            )
        if staging_descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(staging_descriptor)
        if staging_name is not None:
            with contextlib.suppress(OSError):
                os.unlink(staging_name, dir_fd=parent.descriptor)
        if linked:
            with contextlib.suppress(OSError):
                os.fsync(parent.descriptor)
        for descriptor in reversed(parent.descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)


def _freeze_environment_source_commit() -> str:
    executable = getattr(sys, "executable", None)
    if type(executable) is not str or not executable or not Path(executable).is_absolute():
        _raise(ControlFreezeErrorCode.INVALID_ENVIRONMENT)
    source_commit = os.environ.get("SOURCE_COMMIT")
    if not _is_lower_hex(source_commit, 40):
        _raise(ControlFreezeErrorCode.INVALID_ENVIRONMENT)
    expected_environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": f"{Path(executable).parent}:/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "SOURCE_COMMIT": source_commit,
        "SOURCE_DATE_EPOCH": "0",
        "TZ": "UTC",
    }
    if (
        sys.implementation.name != "cpython"
        or sys.version_info[:3] != (3, 12, 11)
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or not sys.dont_write_bytecode
        or os.environ != expected_environment
    ):
        _raise(ControlFreezeErrorCode.INVALID_ENVIRONMENT)
    assert isinstance(source_commit, str)
    return source_commit


def _require_cli_invocation(values: list[str]) -> None:
    expected = [sys.executable, "-s", "-B", "-m", _MODULE_NAME, *values]
    if type(sys.orig_argv) is not list or sys.orig_argv != expected:
        _raise(ControlFreezeErrorCode.INVALID_ENVIRONMENT)


def _parse_cli_output(argv: Sequence[str]) -> Path:
    try:
        values = list(argv)
    except Exception:
        _raise(ControlFreezeErrorCode.INVALID_ARGUMENT)
    if len(values) != 2 or values[0] != "--output":
        _raise(ControlFreezeErrorCode.INVALID_ARGUMENT)
    _require_cli_invocation(values)
    return _validated_output_path(values[1])


def main(argv: Sequence[str] | None = None) -> int:
    """Build one source-only subject; success and failure are both silent."""

    try:
        values = sys.argv[1:] if argv is None else argv
        output = _parse_cli_output(values)
        source_commit = _freeze_environment_source_commit()
        subject = build_control_bundle(source_commit=source_commit)
        _write_subject_no_replace(output, subject)
    except KP1979V3ControlFreezeError:
        return 2
    except Exception:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
