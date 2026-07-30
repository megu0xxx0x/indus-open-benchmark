"""Fail-closed durable state for one KP1979 V3 C3 execution.

The state machine deliberately knows nothing about experiment identifiers,
commitments, detector output, scores, or result payloads. A caller completes
all non-consuming preflight work first. Immediately before the worker is
called, this module creates and durably syncs one ``started`` record with
no-replace semantics. After that point every observed outcome is terminal:
``qualified``, ``not_qualified``, ``execution_failed``, or
``consumed_incomplete``. A valid started record without a terminal record is
interpreted as ``consumed_incomplete`` on recovery, so a crash never authorizes
a retry.

This is local owner-controlled state, not independent custody. The operating
system owner (or a more privileged actor) can delete, replace, or roll back the
directory and can interfere between checks. Consequently these records do not
prove single execution, trusted time, non-deletion, external custody, or
tamper resistance. They fail closed while the checked state remains present;
they do not make the owner unable to remove it.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import json
import os
import secrets
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import NoReturn, TypeVar

STATE_FORMAT_VERSION = 1
STARTED_RECORD_NAME = "attempt.started.json"
TERMINAL_RECORD_NAME = "attempt.terminal.json"
MAX_RECORD_BYTES = 256

_STARTED_STATE = "started"
_RENAME_NOREPLACE = 1
_DARWIN_RENAME_EXCL = 0x00000004
_PROBE_SOURCE_NAME = ".kp1979-v3-state.rename-probe.source"
_PROBE_TARGET_NAME = ".kp1979-v3-state.rename-probe.target"
_PROBE_SOURCE_BYTES = b"kp1979-v3-state-rename-probe-source-v1\n"
_PROBE_TARGET_BYTES = b"kp1979-v3-state-rename-probe-target-v1\n"
_PreflightValue = TypeVar("_PreflightValue")


class TerminalStatus(StrEnum):
    """The only terminal meanings stored by this state layer."""

    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    EXECUTION_FAILED = "execution_failed"
    CONSUMED_INCOMPLETE = "consumed_incomplete"


class ObservedStatus(StrEnum):
    """A closed observation of the durable state directory."""

    ABSENT = "absent"
    QUALIFIED = TerminalStatus.QUALIFIED
    NOT_QUALIFIED = TerminalStatus.NOT_QUALIFIED
    EXECUTION_FAILED = TerminalStatus.EXECUTION_FAILED
    CONSUMED_INCOMPLETE = TerminalStatus.CONSUMED_INCOMPLETE


class StateErrorCode(StrEnum):
    """Stable path- and detail-free public failure codes."""

    UNSUPPORTED_PLATFORM = "unsupported_platform"
    INVALID_STATE_DIRECTORY = "invalid_state_directory"
    UNSAFE_STATE_DIRECTORY = "unsafe_state_directory"
    STATE_DIRECTORY_CHANGED = "state_directory_changed"
    STATE_CORRUPT = "state_corrupt"
    ATTEMPT_CONSUMED = "attempt_consumed"
    INVALID_TRANSITION = "invalid_transition"
    PREFLIGHT_FAILED = "preflight_failed"
    WORKER_FAILED = "worker_failed"
    INVALID_WORKER_OUTCOME = "invalid_worker_outcome"
    START_DURABILITY_UNKNOWN = "start_durability_unknown"
    RENAME_PROBE_FAILED = "rename_probe_failed"
    TERMINAL_WRITE_FAILED = "terminal_write_failed"
    TERMINAL_DURABILITY_UNKNOWN = "terminal_durability_unknown"
    CLOSED = "state_handle_closed"


class KP1979V3StateError(RuntimeError):
    """A state failure whose string contains only a stable error code."""

    def __init__(self, code: StateErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class TerminalMetadata:
    """Minimal typed terminal metadata; result content belongs elsewhere."""

    status: TerminalStatus


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """One fail-closed observation of the state directory."""

    status: ObservedStatus
    terminal_record_present: bool


class _InvalidRecord(Exception):
    pass


class _UnsafeACL(Exception):
    pass


class _UnsafeAncestry(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _PinnedAncestry:
    descriptors: tuple[int, ...]
    names: tuple[str, ...]
    fingerprints: tuple[tuple[int, ...], ...]
    effective_uid: int

    @property
    def descriptor(self) -> int:
        return self.descriptors[-1]


def _raise(code: StateErrorCode) -> NoReturn:
    raise KP1979V3StateError(code) from None


def _require_supported_platform() -> None:
    required_constants = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    if (
        sys.platform not in {"linux", "darwin"}
        or os.name != "posix"
        or not hasattr(os, "geteuid")
        or any(not hasattr(os, name) for name in required_constants)
        or os.open not in os.supports_dir_fd
        or os.stat not in os.supports_dir_fd
        or os.unlink not in os.supports_dir_fd
        or (sys.platform == "linux" and not hasattr(os, "listxattr"))
    ):
        _raise(StateErrorCode.UNSUPPORTED_PLATFORM)


def _validated_absolute_path(directory: os.PathLike[str] | str) -> Path:
    try:
        raw = os.fspath(directory)
    except BaseException:
        _raise(StateErrorCode.INVALID_STATE_DIRECTORY)
    if (
        type(raw) is not str
        or not raw
        or "\x00" in raw
        or any("\ud800" <= character <= "\udfff" for character in raw)
    ):
        _raise(StateErrorCode.INVALID_STATE_DIRECTORY)
    try:
        encoded_path = os.fsencode(raw)
        path = Path(raw)
    except (UnicodeError, ValueError):
        _raise(StateErrorCode.INVALID_STATE_DIRECTORY)
    if (
        not encoded_path
        or b"\x00" in encoded_path
        or not path.is_absolute()
        or path.anchor != "/"
        or str(path) != raw
        or path == Path("/")
        or any(part in {"", ".", ".."} for part in raw.split("/")[1:])
    ):
        _raise(StateErrorCode.INVALID_STATE_DIRECTORY)
    for component in path.parts[1:]:
        try:
            encoded_component = os.fsencode(component)
        except (UnicodeError, ValueError):
            _raise(StateErrorCode.INVALID_STATE_DIRECTORY)
        if (
            not encoded_component
            or len(encoded_component) > 255
            or b"/" in encoded_component
            or b"\x00" in encoded_component
        ):
            _raise(StateErrorCode.INVALID_STATE_DIRECTORY)
    return path


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _record_read_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


def _record_create_flags() -> int:
    return os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC


def _require_acl_free(descriptor: int) -> None:
    if sys.platform == "darwin":
        library = ctypes.CDLL(None, use_errno=True)
        try:
            acl_get_fd = library.acl_get_fd_np
            acl_free = library.acl_free
        except AttributeError:
            raise _UnsafeACL from None
        acl_get_fd.argtypes = [ctypes.c_int, ctypes.c_int]
        acl_get_fd.restype = ctypes.c_void_p
        acl_free.argtypes = [ctypes.c_void_p]
        acl_free.restype = ctypes.c_int
        ctypes.set_errno(0)
        acl = acl_get_fd(descriptor, 0x00000100)
        if not acl:
            if ctypes.get_errno() == errno.ENOENT:
                return
            raise _UnsafeACL
        try:
            raise _UnsafeACL
        finally:
            acl_free(acl)
    if sys.platform != "linux":
        raise _UnsafeACL
    try:
        names = os.listxattr(descriptor)
    except (OSError, TypeError):
        raise _UnsafeACL from None
    for name in names:
        if type(name) is str:
            acl_name = "acl" in name.casefold()
        elif type(name) is bytes:
            acl_name = b"acl" in name.lower()
        else:
            raise _UnsafeACL
        if acl_name:
            raise _UnsafeACL


def _directory_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
    )


def _directory_component_is_safe(
    metadata: os.stat_result,
    *,
    effective_uid: int,
    root: bool,
    final: bool,
) -> bool:
    if not stat.S_ISDIR(metadata.st_mode):
        return False
    mode = stat.S_IMODE(metadata.st_mode)
    if root:
        return metadata.st_uid == 0 and not bool(mode & 0o022)
    if final:
        return metadata.st_uid == effective_uid and mode == 0o700
    root_owned_sticky_boundary = metadata.st_uid == 0 and bool(metadata.st_mode & stat.S_ISVTX)
    return metadata.st_uid in {0, effective_uid} and (
        not bool(mode & 0o022) or root_owned_sticky_boundary
    )


def _close_pinned_ancestry(pinned: _PinnedAncestry) -> None:
    for descriptor in reversed(pinned.descriptors):
        with contextlib.suppress(OSError):
            os.close(descriptor)


def _verify_pinned_ancestry(pinned: _PinnedAncestry) -> None:
    if (
        len(pinned.descriptors) != len(pinned.fingerprints)
        or len(pinned.names) + 1 != len(pinned.descriptors)
        or os.geteuid() != pinned.effective_uid
    ):
        raise _UnsafeAncestry
    for index, descriptor in enumerate(pinned.descriptors):
        metadata = os.fstat(descriptor)
        if _directory_fingerprint(metadata) != pinned.fingerprints[
            index
        ] or not _directory_component_is_safe(
            metadata,
            effective_uid=pinned.effective_uid,
            root=index == 0,
            final=index == len(pinned.descriptors) - 1,
        ):
            raise _UnsafeAncestry
        _require_acl_free(descriptor)
        if index == 0:
            continue
        namespace = os.stat(
            pinned.names[index - 1],
            dir_fd=pinned.descriptors[index - 1],
            follow_symlinks=False,
        )
        if _directory_fingerprint(namespace) != pinned.fingerprints[index]:
            raise _UnsafeAncestry


def _open_pinned_ancestry(path: Path) -> _PinnedAncestry:
    descriptors: list[int] = []
    names: list[str] = []
    fingerprints: list[tuple[int, ...]] = []
    effective_uid = os.geteuid()
    try:
        root_descriptor = os.open("/", _directory_flags())
        descriptors.append(root_descriptor)
        root_metadata = os.fstat(root_descriptor)
        if not _directory_component_is_safe(
            root_metadata,
            effective_uid=effective_uid,
            root=True,
            final=False,
        ):
            raise _UnsafeAncestry
        _require_acl_free(root_descriptor)
        fingerprints.append(_directory_fingerprint(root_metadata))
        components = path.parts[1:]
        for index, component in enumerate(components):
            child = os.open(component, _directory_flags(), dir_fd=descriptors[-1])
            descriptors.append(child)
            names.append(component)
            metadata = os.fstat(child)
            if not _directory_component_is_safe(
                metadata,
                effective_uid=effective_uid,
                root=False,
                final=index == len(components) - 1,
            ):
                raise _UnsafeAncestry
            _require_acl_free(child)
            fingerprint = _directory_fingerprint(metadata)
            namespace = os.stat(
                component,
                dir_fd=descriptors[-2],
                follow_symlinks=False,
            )
            if _directory_fingerprint(namespace) != fingerprint:
                raise _UnsafeAncestry
            fingerprints.append(fingerprint)
        pinned = _PinnedAncestry(
            descriptors=tuple(descriptors),
            names=tuple(names),
            fingerprints=tuple(fingerprints),
            effective_uid=effective_uid,
        )
        _verify_pinned_ancestry(pinned)
        return pinned
    except BaseException:
        for descriptor in reversed(descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        raise


def _safe_record(metadata: os.stat_result) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_uid == os.geteuid()
        and metadata.st_nlink == 1
        and stat.S_IMODE(metadata.st_mode) == 0o600
        and 0 < metadata.st_size <= MAX_RECORD_BYTES
    )


def _record_identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _stable_record_metadata(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _write_all(descriptor: int, payload: bytes) -> None:
    pending = memoryview(payload)
    while pending:
        written = os.write(descriptor, pending)
        if written <= 0:
            raise OSError(errno.EIO, "state write failed")
        pending = pending[written:]


def _read_bounded(descriptor: int) -> bytes:
    observed = bytearray()
    while len(observed) <= MAX_RECORD_BYTES:
        chunk = os.read(descriptor, MAX_RECORD_BYTES + 1 - len(observed))
        if not chunk:
            break
        observed.extend(chunk)
    if not observed or len(observed) > MAX_RECORD_BYTES:
        raise _InvalidRecord
    return bytes(observed)


def _fsync_file(descriptor: int) -> None:
    os.fsync(descriptor)


def _fsync_directory(descriptor: int) -> None:
    os.fsync(descriptor)


def _reject_constant(_: str) -> object:
    raise _InvalidRecord


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if type(key) is not str or key in result:
            raise _InvalidRecord
        result[key] = value
    return result


def _canonical_record(state_value: str) -> bytes:
    value = {"state": state_value, "version": STATE_FORMAT_VERSION}
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )


def _decode_record(raw: bytes, *, terminal: bool) -> str:
    try:
        parsed = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _InvalidRecord):
        raise _InvalidRecord from None
    if (
        type(parsed) is not dict
        or set(parsed) != {"state", "version"}
        or type(parsed["state"]) is not str
        or type(parsed["version"]) is not int
        or parsed["version"] != STATE_FORMAT_VERSION
    ):
        raise _InvalidRecord
    state_value = parsed["state"]
    if terminal:
        try:
            TerminalStatus(state_value)
        except ValueError:
            raise _InvalidRecord from None
    elif state_value != _STARTED_STATE:
        raise _InvalidRecord
    if raw != _canonical_record(state_value):
        raise _InvalidRecord
    return state_value


def _rename_no_replace(parent_descriptor: int, source_name: str, target_name: str) -> None:
    source = source_name.encode("ascii")
    target = target_name.encode("ascii")
    library = ctypes.CDLL(None, use_errno=True)
    ctypes.set_errno(0)
    if sys.platform.startswith("linux"):
        try:
            renameat2 = library.renameat2
        except AttributeError:
            raise OSError(errno.ENOTSUP, "rename no-replace unavailable") from None
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = int(
            renameat2(
                parent_descriptor,
                source,
                parent_descriptor,
                target,
                _RENAME_NOREPLACE,
            )
        )
    elif sys.platform == "darwin":
        try:
            renameatx = library.renameatx_np
        except AttributeError:
            raise OSError(errno.ENOTSUP, "rename no-replace unavailable") from None
        renameatx.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameatx.restype = ctypes.c_int
        result = int(
            renameatx(
                parent_descriptor,
                source,
                parent_descriptor,
                target,
                _DARWIN_RENAME_EXCL,
            )
        )
    else:
        raise OSError(errno.ENOTSUP, "rename no-replace unavailable")
    if result != 0:
        error_number = ctypes.get_errno() or errno.EIO
        if error_number == errno.EEXIST:
            raise FileExistsError(error_number, "state record exists")
        raise OSError(error_number, "rename no-replace failed")


def _terminal_staging_name() -> str:
    try:
        token = secrets.token_hex(16)
    except BaseException:
        _raise(StateErrorCode.TERMINAL_WRITE_FAILED)
    if (
        type(token) is not str
        or len(token) != 32
        or any(character not in "0123456789abcdef" for character in token)
    ):
        _raise(StateErrorCode.TERMINAL_WRITE_FAILED)
    return f".terminal-{token}.tmp"


class C3OneShotState:
    """A descriptor-pinned, owner-only, one-shot C3 state directory."""

    def __init__(self, directory: os.PathLike[str] | str) -> None:
        _require_supported_platform()
        self._path = _validated_absolute_path(directory)
        try:
            self._ancestry = _open_pinned_ancestry(self._path)
        except (OSError, _UnsafeACL, _UnsafeAncestry):
            _raise(StateErrorCode.UNSAFE_STATE_DIRECTORY)
        self._descriptor = self._ancestry.descriptor
        self._closed = False
        self._start_attempted = False
        self._started_here = False
        self._finish_attempted = False

    def __enter__(self) -> C3OneShotState:
        self._require_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            _close_pinned_ancestry(self._ancestry)

    def _require_open(self) -> None:
        if self._closed:
            _raise(StateErrorCode.CLOSED)

    def _verify_pinned_directory(self) -> None:
        self._require_open()
        try:
            _verify_pinned_ancestry(self._ancestry)
        except KP1979V3StateError:
            raise
        except (OSError, _UnsafeACL, _UnsafeAncestry):
            _raise(StateErrorCode.STATE_DIRECTORY_CHANGED)

    def _read_record(self, name: str) -> bytes | None:
        try:
            before = os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError:
            raise _InvalidRecord from None
        if not _safe_record(before):
            raise _InvalidRecord
        descriptor = -1
        try:
            descriptor = os.open(name, _record_read_flags(), dir_fd=self._descriptor)
            opened = os.fstat(descriptor)
            _require_acl_free(descriptor)
            if (
                not _safe_record(opened)
                or _record_identity(opened) != _record_identity(before)
                or _stable_record_metadata(opened) != _stable_record_metadata(before)
            ):
                raise _InvalidRecord
            raw = _read_bounded(descriptor)
            after_descriptor = os.fstat(descriptor)
            after_name = os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)
            _require_acl_free(descriptor)
            if (
                not _safe_record(after_descriptor)
                or not _safe_record(after_name)
                or _stable_record_metadata(after_descriptor) != _stable_record_metadata(opened)
                or _stable_record_metadata(after_name) != _stable_record_metadata(opened)
            ):
                raise _InvalidRecord
            return raw
        except (FileNotFoundError, OSError, _UnsafeACL):
            raise _InvalidRecord from None
        finally:
            if descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(descriptor)

    def inspect(self) -> StateSnapshot:
        """Observe state; a marker-only crash is terminal and consumed."""

        self._require_open()
        try:
            self._verify_pinned_directory()
            started_raw = self._read_record(STARTED_RECORD_NAME)
            terminal_raw = self._read_record(TERMINAL_RECORD_NAME)
            self._verify_pinned_directory()
            if started_raw is None and terminal_raw is None:
                return StateSnapshot(ObservedStatus.ABSENT, False)
            if started_raw is None:
                raise _InvalidRecord
            _decode_record(started_raw, terminal=False)
            if terminal_raw is None:
                return StateSnapshot(ObservedStatus.CONSUMED_INCOMPLETE, False)
            terminal_value = _decode_record(terminal_raw, terminal=True)
            return StateSnapshot(ObservedStatus(terminal_value), True)
        except KP1979V3StateError:
            raise
        except (_InvalidRecord, OSError, ValueError):
            _raise(StateErrorCode.STATE_CORRUPT)

    def _validate_open_record(self, descriptor: int, expected: bytes) -> None:
        metadata = os.fstat(descriptor)
        try:
            _require_acl_free(descriptor)
        except _UnsafeACL:
            raise _InvalidRecord from None
        if not _safe_record(metadata) or metadata.st_size != len(expected):
            raise OSError(errno.EIO, "unsafe state record")
        os.lseek(descriptor, 0, os.SEEK_SET)
        if _read_bounded(descriptor) != expected:
            raise OSError(errno.EIO, "state record verification failed")

    def _require_record_name_matches(
        self,
        name: str,
        descriptor: int,
        expected: bytes,
    ) -> None:
        namespace = os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)
        descriptor_metadata = os.fstat(descriptor)
        self._validate_open_record(descriptor, expected)
        if not _safe_record(namespace) or _stable_record_metadata(
            namespace
        ) != _stable_record_metadata(descriptor_metadata):
            raise OSError(errno.EIO, "probe namespace changed")

    def _require_name_absent(self, name: str) -> None:
        try:
            os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise OSError(errno.EEXIST, "probe name remains")

    def _remove_known_probe_name(
        self,
        name: str,
        known: tuple[tuple[int, bytes], ...],
    ) -> None:
        try:
            namespace = os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return
        for descriptor, expected in known:
            descriptor_metadata = os.fstat(descriptor)
            if _record_identity(namespace) != _record_identity(descriptor_metadata):
                continue
            self._require_record_name_matches(name, descriptor, expected)
            os.unlink(name, dir_fd=self._descriptor)
            if os.fstat(descriptor).st_nlink != 0:
                raise OSError(errno.EIO, "probe unlink did not detach inode")
            return
        raise OSError(errno.EPERM, "probe name is not an owned probe inode")

    def _cleanup_probe_names(
        self,
        known: tuple[tuple[int, bytes], ...],
    ) -> None:
        cleanup_failed = False
        for name in (_PROBE_SOURCE_NAME, _PROBE_TARGET_NAME):
            try:
                self._remove_known_probe_name(name, known)
            except BaseException:
                cleanup_failed = True
        try:
            _fsync_directory(self._descriptor)
            self._verify_pinned_directory()
            self._require_name_absent(_PROBE_SOURCE_NAME)
            self._require_name_absent(_PROBE_TARGET_NAME)
        except BaseException:
            cleanup_failed = True
        if cleanup_failed:
            raise OSError(errno.EIO, "probe cleanup failed")

    def _probe_rename_no_replace(self) -> None:
        descriptors: list[tuple[int, bytes]] = []
        probe_failed = False
        try:
            self._verify_pinned_directory()
            for name, payload in (
                (_PROBE_SOURCE_NAME, _PROBE_SOURCE_BYTES),
                (_PROBE_TARGET_NAME, _PROBE_TARGET_BYTES),
            ):
                descriptor = os.open(
                    name,
                    _record_create_flags(),
                    0o600,
                    dir_fd=self._descriptor,
                )
                descriptors.append((descriptor, payload))
                os.fchmod(descriptor, 0o600)
                _write_all(descriptor, payload)
                _fsync_file(descriptor)
                self._validate_open_record(descriptor, payload)
            _fsync_directory(self._descriptor)
            self._verify_pinned_directory()
            source_descriptor = descriptors[0][0]
            target_descriptor = descriptors[1][0]

            try:
                _rename_no_replace(
                    self._descriptor,
                    _PROBE_SOURCE_NAME,
                    _PROBE_TARGET_NAME,
                )
            except FileExistsError:
                pass
            else:
                raise OSError(errno.EIO, "rename probe overwrote its target")
            self._require_record_name_matches(
                _PROBE_SOURCE_NAME,
                source_descriptor,
                _PROBE_SOURCE_BYTES,
            )
            self._require_record_name_matches(
                _PROBE_TARGET_NAME,
                target_descriptor,
                _PROBE_TARGET_BYTES,
            )

            self._remove_known_probe_name(
                _PROBE_TARGET_NAME,
                tuple(descriptors),
            )
            _fsync_directory(self._descriptor)
            self._verify_pinned_directory()
            self._require_name_absent(_PROBE_TARGET_NAME)

            _rename_no_replace(
                self._descriptor,
                _PROBE_SOURCE_NAME,
                _PROBE_TARGET_NAME,
            )
            _fsync_directory(self._descriptor)
            self._verify_pinned_directory()
            self._require_name_absent(_PROBE_SOURCE_NAME)
            self._require_record_name_matches(
                _PROBE_TARGET_NAME,
                source_descriptor,
                _PROBE_SOURCE_BYTES,
            )
        except BaseException:
            probe_failed = True
        try:
            self._cleanup_probe_names(tuple(descriptors))
        except BaseException:
            probe_failed = True
        for descriptor, _ in reversed(descriptors):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        if probe_failed:
            _raise(StateErrorCode.RENAME_PROBE_FAILED)

    def mark_started(self) -> None:
        """Durably consume the attempt immediately before a worker starts."""

        self._require_open()
        if self._start_attempted:
            _raise(StateErrorCode.INVALID_TRANSITION)
        self._start_attempted = True
        if self.inspect().status is not ObservedStatus.ABSENT:
            _raise(StateErrorCode.ATTEMPT_CONSUMED)
        self._probe_rename_no_replace()
        payload = _canonical_record(_STARTED_STATE)
        descriptor = -1
        created = False
        try:
            self._verify_pinned_directory()
            descriptor = os.open(
                STARTED_RECORD_NAME,
                _record_create_flags(),
                0o600,
                dir_fd=self._descriptor,
            )
            created = True
            os.fchmod(descriptor, 0o600)
            _write_all(descriptor, payload)
            _fsync_file(descriptor)
            self._validate_open_record(descriptor, payload)
            _fsync_directory(self._descriptor)
            self._verify_pinned_directory()
            observed = self._read_record(STARTED_RECORD_NAME)
            if observed is None:
                raise OSError(errno.EIO, "started record disappeared")
            if observed != payload or _decode_record(observed, terminal=False) != _STARTED_STATE:
                raise OSError(errno.EIO, "started record changed")
        except FileExistsError:
            _raise(StateErrorCode.ATTEMPT_CONSUMED)
        except KP1979V3StateError as error:
            if created and error.code is StateErrorCode.STATE_DIRECTORY_CHANGED:
                _raise(StateErrorCode.START_DURABILITY_UNKNOWN)
            raise
        except (OSError, _InvalidRecord, ValueError):
            _raise(StateErrorCode.START_DURABILITY_UNKNOWN)
        finally:
            if descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(descriptor)
        self._started_here = True

    def _safe_remove_staging(self, descriptor: int, name: str) -> None:
        with contextlib.suppress(OSError, _UnsafeACL):
            descriptor_metadata = os.fstat(descriptor)
            name_metadata = os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)
            _require_acl_free(descriptor)
            if (
                _safe_record(descriptor_metadata)
                and _safe_record(name_metadata)
                and _stable_record_metadata(descriptor_metadata)
                == _stable_record_metadata(name_metadata)
            ):
                os.unlink(name, dir_fd=self._descriptor)
                if os.fstat(descriptor).st_nlink != 0:
                    raise OSError(errno.EIO, "staging unlink did not detach inode")

    def _publish_terminal(self, payload: bytes) -> None:
        staging_name = _terminal_staging_name()
        descriptor = -1
        renamed = False
        try:
            descriptor = os.open(
                staging_name,
                _record_create_flags(),
                0o600,
                dir_fd=self._descriptor,
            )
            os.fchmod(descriptor, 0o600)
            _write_all(descriptor, payload)
            _fsync_file(descriptor)
            self._validate_open_record(descriptor, payload)
            self._verify_pinned_directory()
            started_before = self._read_record(STARTED_RECORD_NAME)
            if (
                started_before is None
                or _decode_record(started_before, terminal=False) != _STARTED_STATE
            ):
                raise _InvalidRecord
            if self._read_record(TERMINAL_RECORD_NAME) is not None:
                _raise(StateErrorCode.ATTEMPT_CONSUMED)
            _rename_no_replace(self._descriptor, staging_name, TERMINAL_RECORD_NAME)
            renamed = True
            try:
                _fsync_directory(self._descriptor)
            except OSError:
                _raise(StateErrorCode.TERMINAL_DURABILITY_UNKNOWN)
            self._verify_pinned_directory()
            try:
                started_after = self._read_record(STARTED_RECORD_NAME)
                if (
                    started_after is None
                    or _decode_record(started_after, terminal=False) != _STARTED_STATE
                ):
                    raise _InvalidRecord
            except _InvalidRecord:
                _raise(StateErrorCode.STATE_CORRUPT)
            observed = self._read_record(TERMINAL_RECORD_NAME)
            if observed != payload:
                _raise(StateErrorCode.STATE_CORRUPT)
        except FileExistsError:
            _raise(StateErrorCode.ATTEMPT_CONSUMED)
        except KP1979V3StateError as error:
            if renamed and error.code is StateErrorCode.STATE_DIRECTORY_CHANGED:
                _raise(StateErrorCode.TERMINAL_DURABILITY_UNKNOWN)
            raise
        except (OSError, _InvalidRecord, ValueError):
            if renamed:
                _raise(StateErrorCode.TERMINAL_DURABILITY_UNKNOWN)
            _raise(StateErrorCode.TERMINAL_WRITE_FAILED)
        finally:
            if descriptor >= 0:
                if not renamed:
                    self._safe_remove_staging(descriptor, staging_name)
                with contextlib.suppress(OSError):
                    os.close(descriptor)

    def finish(self, status: TerminalStatus) -> TerminalMetadata:
        """Publish exactly one typed terminal status without replacement."""

        self._require_open()
        if type(status) is not TerminalStatus or not self._started_here or self._finish_attempted:
            _raise(StateErrorCode.INVALID_TRANSITION)
        self._finish_attempted = True
        try:
            self._verify_pinned_directory()
            started_raw = self._read_record(STARTED_RECORD_NAME)
            if started_raw is None or _decode_record(started_raw, terminal=False) != _STARTED_STATE:
                raise _InvalidRecord
            if self._read_record(TERMINAL_RECORD_NAME) is not None:
                _raise(StateErrorCode.ATTEMPT_CONSUMED)
            payload = _canonical_record(status.value)
            self._publish_terminal(payload)
            return TerminalMetadata(status)
        except KP1979V3StateError:
            raise
        except (_InvalidRecord, OSError, ValueError):
            _raise(StateErrorCode.STATE_CORRUPT)


def execute_one_shot(
    directory: os.PathLike[str] | str,
    *,
    preflight: Callable[[], _PreflightValue],
    worker: Callable[[_PreflightValue], TerminalStatus],
) -> TerminalMetadata:
    """Run preflight unconsumed, then durably consume immediately before worker.

    Caller exceptions are collapsed to stable codes. This function never
    serializes or interprets the preflight value or any worker result content;
    the worker returns only a typed terminal status.
    """

    with C3OneShotState(directory) as state:
        if state.inspect().status is not ObservedStatus.ABSENT:
            _raise(StateErrorCode.ATTEMPT_CONSUMED)
        try:
            prepared = preflight()
        except BaseException:
            _raise(StateErrorCode.PREFLIGHT_FAILED)
        state.mark_started()
        try:
            outcome = worker(prepared)
        except Exception:
            state.finish(TerminalStatus.EXECUTION_FAILED)
            _raise(StateErrorCode.WORKER_FAILED)
        except BaseException:
            state.finish(TerminalStatus.CONSUMED_INCOMPLETE)
            _raise(StateErrorCode.WORKER_FAILED)
        if type(outcome) is not TerminalStatus:
            state.finish(TerminalStatus.EXECUTION_FAILED)
            _raise(StateErrorCode.INVALID_WORKER_OUTCOME)
        return state.finish(outcome)


__all__ = [
    "MAX_RECORD_BYTES",
    "STARTED_RECORD_NAME",
    "STATE_FORMAT_VERSION",
    "TERMINAL_RECORD_NAME",
    "C3OneShotState",
    "KP1979V3StateError",
    "ObservedStatus",
    "StateErrorCode",
    "StateSnapshot",
    "TerminalMetadata",
    "TerminalStatus",
    "execute_one_shot",
]
