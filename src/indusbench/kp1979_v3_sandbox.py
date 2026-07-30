"""Fail-closed Linux process isolation for one KP1979 V3 detector request.

The trusted parent sends only the closed, answer-free detector request.  A
fresh transient user service applies systemd limits and seccomp from process
start.  Its trusted bootstrap then applies Landlock before loading the frozen
worker zipapp.  The bootstrap writes a canonical one-line handshake to a
separate owner-only file and closes it before loading the worker.  The parent
can therefore distinguish a verified sandbox from a worker or transport
failure without publishing child diagnostics.

This boundary is deliberately Linux-specific.  Official qualification must
fail rather than silently downgrade when systemd or Landlock is unavailable.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hmac
import json
import os
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal

SANDBOX_SCHEMA: Final = "kp1979-v3-sandbox-handshake-v1"
WORKER_INTERFACE_VERSION: Final = "kp1979-label-detector-v3-worker-v1"
MINIMUM_LANDLOCK_ABI: Final = 4

MAX_REQUEST_BYTES: Final = 6_000_000
MAX_ARTIFACT_BYTES: Final = 16_777_216
MAX_STDOUT_BYTES: Final = 131_072
MAX_STDERR_BYTES: Final = 131_072
MAX_HANDSHAKE_BYTES: Final = 4_096
PARENT_WALL_TIMEOUT_SECONDS: Final = 40.0
UNIT_KILL_TIMEOUT_SECONDS: Final = 5.0

SYSTEMD_RUN: Final = Path("/usr/bin/systemd-run")
SYSTEMCTL: Final = Path("/usr/bin/systemctl")
ENV_EXECUTABLE: Final = Path("/usr/bin/env")

SYSTEM_CALL_FILTER: Final = (
    "SystemCallFilter=~@cpu-emulation @debug @ipc @keyring @mount @network-io "
    "@obsolete @privileged @resources clone clone3 execveat fork io_uring_enter "
    "io_uring_register io_uring_setup kcmp kill pidfd_open pidfd_send_signal "
    "prlimit64 process_mrelease rt_sigqueueinfo rt_tgsigqueueinfo setns tgkill "
    "tkill unshare vfork"
)
SYSTEMD_PROPERTIES: Final = (
    "NoNewPrivileges=yes",
    "SystemCallArchitectures=native",
    SYSTEM_CALL_FILTER,
    "SystemCallErrorNumber=EPERM",
    "RestrictAddressFamilies=AF_UNIX",
    "TasksMax=1",
    "RuntimeMaxSec=35s",
    "MemoryMax=1073741824",
    "LimitCPU=24",
    "LimitNOFILE=32",
    "LimitCORE=0",
    "LimitFSIZE=131072",
    "UMask=0077",
    "KeyringMode=private",
    "LockPersonality=yes",
    "MemoryDenyWriteExecute=yes",
)

ANSWER_FREE_REQUEST_KEYS: Final = frozenset(
    {"interface_version", "pbm_base64", "width", "height", "scan_bands"}
)
HANDSHAKE_KEYS: Final = frozenset({"artifact_sha256", "landlock_abi", "nonce", "probes", "schema"})
PROBE_KEYS: Final = frozenset(
    {
        "canary_open_denied",
        "cwd_write_denied",
        "etc_passwd_open_denied",
        "handshake_reopen_denied",
        "parent_list_denied",
        "systemd_socket_creation_denied",
    }
)

SandboxDisposition = Literal[
    "completed",
    "request_rejected",
    "isolation_failure",
    "worker_failure",
    "transport_failure",
]


class SandboxPreflightError(ValueError):
    """Raised before a roster when the official sandbox cannot be frozen safely."""


class _RequestContractError(ValueError):
    """Internal marker for an answer-free request contract violation."""


@dataclass(frozen=True, slots=True)
class SandboxInvocationResult:
    """Redacted result of one fresh sandbox invocation."""

    disposition: SandboxDisposition
    worker_stdout: bytes
    failure_code: str | None
    handshake_verified: bool
    landlock_abi: int | None
    process_started: bool
    timed_out: bool
    captured_stdout_bytes: int
    captured_stderr_bytes: int


@dataclass(frozen=True, slots=True)
class _ArtifactSnapshot:
    path: Path
    digest: str
    content: bytes
    fingerprint: tuple[int, int, int, int, int, int, int, int]


def _canonical_json_line(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise _RequestContractError("JSON encoding") from exc


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _RequestContractError("duplicate key")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> object:
    raise _RequestContractError("non-finite JSON constant")


def _is_strict_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_answer_free_request(request: bytes) -> None:
    if type(request) is not bytes or not request or len(request) > MAX_REQUEST_BYTES:
        raise _RequestContractError("request size")
    try:
        parsed = json.loads(
            request.decode("ascii"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except _RequestContractError:
        raise
    except (RecursionError, ValueError) as exc:
        raise _RequestContractError("request JSON") from exc
    if not isinstance(parsed, dict) or frozenset(parsed) != ANSWER_FREE_REQUEST_KEYS:
        raise _RequestContractError("request keys")
    if _canonical_json_line(parsed) != request:
        raise _RequestContractError("request encoding")
    interface_version = parsed["interface_version"]
    pbm_base64 = parsed["pbm_base64"]
    width = parsed["width"]
    height = parsed["height"]
    scan_bands = parsed["scan_bands"]
    if (
        not isinstance(interface_version, str)
        or interface_version != WORKER_INTERFACE_VERSION
        or not isinstance(pbm_base64, str)
        or not pbm_base64
        or not pbm_base64.isascii()
        or type(width) is not int
        or not 0 < width <= 10_000
        or type(height) is not int
        or not 0 < height <= 10_000
        or not isinstance(scan_bands, list)
        or not 1 <= len(scan_bands) <= 8
    ):
        raise _RequestContractError("request values")
    for band in scan_bands:
        if (
            not isinstance(band, list)
            or len(band) != 4
            or any(
                type(coordinate) is not int or not 0 <= coordinate <= 10_000 for coordinate in band
            )
        ):
            raise _RequestContractError("scan bands")
    try:
        decoded_pbm = base64.b64decode(pbm_base64.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise _RequestContractError("PBM encoding") from exc
    if not decoded_pbm or base64.b64encode(decoded_pbm).decode("ascii") != pbm_base64:
        raise _RequestContractError("PBM encoding")


def _file_fingerprint(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_nlink,
    )


def _read_frozen_artifact(path: Path, expected_sha256: str) -> _ArtifactSnapshot:
    if (
        not path.is_absolute()
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
    ):
        raise SandboxPreflightError("invalid frozen artifact declaration")
    try:
        unresolved_metadata = path.lstat()
    except OSError as exc:
        raise SandboxPreflightError("frozen artifact is unavailable") from exc
    if stat.S_ISLNK(unresolved_metadata.st_mode):
        raise SandboxPreflightError("frozen artifact must not be a symbolic link")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SandboxPreflightError("frozen artifact cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) & 0o022
            or not 0 < before.st_size <= MAX_ARTIFACT_BYTES
        ):
            raise SandboxPreflightError("frozen artifact is not an owner-safe regular file")
        content_parts: list[bytes] = []
        remaining = MAX_ARTIFACT_BYTES + 1
        while remaining:
            block = os.read(descriptor, min(1_048_576, remaining))
            if not block:
                break
            content_parts.append(block)
            remaining -= len(block)
        content = b"".join(content_parts)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        len(content) != before.st_size
        or len(content) > MAX_ARTIFACT_BYTES
        or _file_fingerprint(before) != _file_fingerprint(after)
    ):
        raise SandboxPreflightError("frozen artifact changed while it was read")
    digest = sha256(content).hexdigest()
    if not hmac.compare_digest(digest, expected_sha256):
        raise SandboxPreflightError("frozen artifact digest mismatch")
    return _ArtifactSnapshot(
        path=path,
        digest=digest,
        content=content,
        fingerprint=_file_fingerprint(after),
    )


def _require_safe_executable(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise SandboxPreflightError("sandbox executable is unavailable") from exc
    if (
        not resolved.is_absolute()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid not in {0, os.getuid()}
        or stat.S_IMODE(metadata.st_mode) & 0o022
        or not os.access(resolved, os.X_OK)
    ):
        raise SandboxPreflightError("sandbox executable is not safe")
    return resolved


def _systemd_client_environment() -> dict[str, str]:
    runtime_directory = f"/run/user/{os.getuid()}"
    return {
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime_directory}/bus",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
        "XDG_RUNTIME_DIR": runtime_directory,
    }


def build_systemd_command(
    *,
    systemd_run: Path,
    env_executable: Path,
    python_executable: Path,
    unit_name: str,
    nonce: str,
    artifact_sha256: str,
    artifact_path: Path,
    working_directory: Path,
    canary_path: Path,
    request_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    handshake_path: Path,
) -> tuple[str, ...]:
    """Build the closed argv used for one transient user service."""

    if (
        len(nonce) != 32
        or any(character not in "0123456789abcdef" for character in nonce)
        or unit_name != f"indus-kp1979-v3-{nonce}"
        or len(artifact_sha256) != 64
        or any(character not in "0123456789abcdef" for character in artifact_sha256)
        or any(
            not path.is_absolute()
            for path in (
                artifact_path,
                working_directory,
                canary_path,
                request_path,
                stdout_path,
                stderr_path,
                handshake_path,
            )
        )
    ):
        raise SandboxPreflightError("invalid sandbox command declaration")
    arguments = [
        str(systemd_run),
        "--user",
        "--wait",
        "--collect",
        "--quiet",
        "--service-type=exec",
        f"--unit={unit_name}",
        f"--working-directory={working_directory}",
    ]
    arguments.extend(f"--property={item}" for item in SYSTEMD_PROPERTIES)
    arguments.extend(
        (
            f"--property=StandardInput=file:{request_path}",
            f"--property=StandardOutput=file:{stdout_path}",
            f"--property=StandardError=file:{stderr_path}",
        )
    )
    arguments.extend(
        (
            str(env_executable),
            "-i",
            "LANG=C.UTF-8",
            "LC_ALL=C.UTF-8",
            "PATH=/usr/bin:/bin",
            str(python_executable),
            "-I",
            "-S",
            "-B",
            "-c",
            _BOOTSTRAP_SCRIPT,
            artifact_sha256,
            nonce,
            str(artifact_path),
            str(working_directory),
            str(canary_path),
            str(handshake_path),
        )
    )
    return tuple(arguments)


def _parse_verified_handshake(
    line: bytes,
    *,
    nonce: str,
    artifact_sha256: str,
) -> int:
    if not line.endswith(b"\n") or not 1 < len(line) <= MAX_HANDSHAKE_BYTES:
        raise ValueError("handshake framing")
    try:
        parsed = json.loads(
            line.decode("ascii"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
        canonical = _canonical_json_line(parsed)
    except (RecursionError, ValueError) as exc:
        raise ValueError("handshake JSON") from exc
    if (
        not isinstance(parsed, dict)
        or frozenset(parsed) != HANDSHAKE_KEYS
        or parsed["schema"] != SANDBOX_SCHEMA
        or parsed["nonce"] != nonce
        or parsed["artifact_sha256"] != artifact_sha256
        or canonical != line
    ):
        raise ValueError("handshake contract")
    abi = parsed["landlock_abi"]
    probes = parsed["probes"]
    if (
        not _is_strict_integer(abi)
        or abi < MINIMUM_LANDLOCK_ABI
        or not isinstance(probes, dict)
        or frozenset(probes) != PROBE_KEYS
        or any(value is not True for value in probes.values())
    ):
        raise ValueError("handshake isolation proof")
    return abi


def _write_exclusive(path: Path, content: bytes, mode: int) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        mode,
    )
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short sandbox file write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _handshake_metadata_is_safe(metadata: os.stat_result, *, require_empty: bool) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_uid == os.getuid()
        and metadata.st_nlink == 1
        and stat.S_IMODE(metadata.st_mode) == 0o600
        and (not require_empty or metadata.st_size == 0)
    )


def _require_empty_handshake_file(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SandboxPreflightError("handshake file is unavailable") from exc
    if not _handshake_metadata_is_safe(metadata, require_empty=True):
        raise SandboxPreflightError("handshake file is not a safe empty regular file")


def _read_handshake_file(path: Path) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError("handshake file cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        parts: list[bytes] = []
        remaining = MAX_HANDSHAKE_BYTES + 1
        while remaining:
            block = os.read(descriptor, remaining)
            if not block:
                break
            parts.append(block)
            remaining -= len(block)
        content = b"".join(parts)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        not _handshake_metadata_is_safe(before, require_empty=False)
        or _file_fingerprint(before) != _file_fingerprint(after)
        or not content
        or len(content) > MAX_HANDSHAKE_BYTES
        or before.st_size != len(content)
    ):
        raise ValueError("handshake file contract")
    return content


def _redacted_result(
    disposition: SandboxDisposition,
    failure_code: str,
    *,
    process_started: bool = False,
    timed_out: bool = False,
    stdout_size: int = 0,
    stderr_size: int = 0,
    handshake_verified: bool = False,
    landlock_abi: int | None = None,
) -> SandboxInvocationResult:
    return SandboxInvocationResult(
        disposition=disposition,
        worker_stdout=b"",
        failure_code=failure_code,
        handshake_verified=handshake_verified,
        landlock_abi=landlock_abi,
        process_started=process_started,
        timed_out=timed_out,
        captured_stdout_bytes=stdout_size,
        captured_stderr_bytes=stderr_size,
    )


class SandboxedWorkerInvoker:
    """Run one request per fresh, verified systemd and Landlock boundary."""

    def __init__(
        self,
        *,
        worker_artifact: Path,
        expected_sha256: str,
        python_executable: Path | None = None,
        systemd_run: Path = SYSTEMD_RUN,
        systemctl: Path = SYSTEMCTL,
        env_executable: Path = ENV_EXECUTABLE,
    ) -> None:
        if not sys.platform.startswith("linux"):
            raise SandboxPreflightError("official sandbox requires Linux")
        self._artifact = _read_frozen_artifact(worker_artifact, expected_sha256)
        self._python_executable = _require_safe_executable(
            Path(sys.executable) if python_executable is None else python_executable
        )
        self._systemd_run = _require_safe_executable(systemd_run)
        self._systemctl = _require_safe_executable(systemctl)
        self._env_executable = _require_safe_executable(env_executable)
        self.started_process_count = 0
        self.verified_invocation_count = 0

    def _source_artifact_is_unchanged(self) -> bool:
        try:
            refreshed = _read_frozen_artifact(self._artifact.path, self._artifact.digest)
        except SandboxPreflightError:
            return False
        return refreshed.fingerprint == self._artifact.fingerprint and hmac.compare_digest(
            refreshed.content, self._artifact.content
        )

    def _kill_unit(self, unit_name: str) -> None:
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                [
                    str(self._systemctl),
                    "--user",
                    "kill",
                    "--kill-whom=all",
                    "--signal=SIGKILL",
                    f"{unit_name}.service",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                close_fds=True,
                shell=False,
                timeout=UNIT_KILL_TIMEOUT_SECONDS,
                env=_systemd_client_environment(),
            )

    def __call__(self, request: bytes) -> SandboxInvocationResult:
        try:
            _validate_answer_free_request(request)
        except _RequestContractError:
            return _redacted_result("request_rejected", "request_contract")
        if not self._source_artifact_is_unchanged():
            return _redacted_result("isolation_failure", "artifact_changed")

        try:
            return self._invoke(request)
        except (OSError, SandboxPreflightError, subprocess.SubprocessError):
            return _redacted_result("transport_failure", "setup_failed")

    def _invoke(self, request: bytes) -> SandboxInvocationResult:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-sandbox-") as raw_directory:
            base_directory = Path(raw_directory)
            if stat.S_IMODE(base_directory.stat().st_mode) & 0o077:
                raise SandboxPreflightError("temporary directory permissions")
            working_directory = base_directory / "cwd"
            working_directory.mkdir(mode=0o700)
            artifact_path = base_directory / "worker.pyz"
            canary_path = base_directory / "canary.bin"
            request_path = base_directory / "request.bin"
            stdout_path = base_directory / "stdout.bin"
            stderr_path = base_directory / "stderr.bin"
            handshake_path = base_directory / "handshake.bin"
            _write_exclusive(artifact_path, self._artifact.content, 0o400)
            _write_exclusive(canary_path, b"sandbox-canary\n", 0o400)
            _write_exclusive(request_path, request, 0o400)
            _write_exclusive(stdout_path, b"", 0o600)
            _write_exclusive(stderr_path, b"", 0o600)
            _write_exclusive(handshake_path, b"", 0o600)
            _require_empty_handshake_file(handshake_path)
            if sha256(artifact_path.read_bytes()).hexdigest() != self._artifact.digest:
                return _redacted_result("isolation_failure", "artifact_copy")
            if any(working_directory.iterdir()):
                return _redacted_result("isolation_failure", "working_directory")

            nonce = secrets.token_hex(16)
            unit_name = f"indus-kp1979-v3-{nonce}"
            command = build_systemd_command(
                systemd_run=self._systemd_run,
                env_executable=self._env_executable,
                python_executable=self._python_executable,
                unit_name=unit_name,
                nonce=nonce,
                artifact_sha256=self._artifact.digest,
                artifact_path=artifact_path,
                working_directory=working_directory,
                canary_path=canary_path,
                request_path=request_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                handshake_path=handshake_path,
            )

            process: subprocess.Popen[bytes] | None = None
            timed_out = False
            try:
                process = subprocess.Popen(
                    command,
                    cwd=working_directory,
                    env=_systemd_client_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    shell=False,
                    start_new_session=True,
                )
                self.started_process_count += 1
                try:
                    process.communicate(timeout=PARENT_WALL_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    self._kill_unit(unit_name)
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        process.communicate(timeout=UNIT_KILL_TIMEOUT_SECONDS)
                with stdout_path.open("rb") as stdout_handle:
                    standard_output = stdout_handle.read(MAX_STDOUT_BYTES + 1)
                with stderr_path.open("rb") as stderr_handle:
                    standard_error = stderr_handle.read(MAX_STDERR_BYTES + 1)
            except BaseException:
                if process is not None:
                    self._kill_unit(unit_name)
                raise

            if timed_out:
                return _redacted_result(
                    "transport_failure",
                    "timeout",
                    process_started=True,
                    timed_out=True,
                    stdout_size=len(standard_output),
                    stderr_size=len(standard_error),
                )
            if len(standard_output) > MAX_STDOUT_BYTES or len(standard_error) > MAX_STDERR_BYTES:
                return _redacted_result(
                    "transport_failure",
                    "output_limit",
                    process_started=True,
                    stdout_size=len(standard_output),
                    stderr_size=len(standard_error),
                )
            try:
                handshake_line = _read_handshake_file(handshake_path)
            except ValueError:
                return _redacted_result(
                    "isolation_failure",
                    "invalid_handshake",
                    process_started=True,
                    stdout_size=len(standard_output),
                    stderr_size=len(standard_error),
                )
            try:
                landlock_abi = _parse_verified_handshake(
                    handshake_line,
                    nonce=nonce,
                    artifact_sha256=self._artifact.digest,
                )
            except ValueError:
                return _redacted_result(
                    "isolation_failure",
                    "invalid_handshake",
                    process_started=True,
                    stdout_size=len(standard_output),
                    stderr_size=len(standard_error),
                )
            self.verified_invocation_count += 1
            if process.returncode != 0:
                return _redacted_result(
                    "worker_failure",
                    "nonzero_exit",
                    process_started=True,
                    stdout_size=len(standard_output),
                    stderr_size=len(standard_error),
                    handshake_verified=True,
                    landlock_abi=landlock_abi,
                )
            if standard_error:
                return _redacted_result(
                    "worker_failure",
                    "stderr_output",
                    process_started=True,
                    stdout_size=len(standard_output),
                    stderr_size=len(standard_error),
                    handshake_verified=True,
                    landlock_abi=landlock_abi,
                )
            return SandboxInvocationResult(
                disposition="completed",
                worker_stdout=standard_output,
                failure_code=None,
                handshake_verified=True,
                landlock_abi=landlock_abi,
                process_started=True,
                timed_out=False,
                captured_stdout_bytes=len(standard_output),
                captured_stderr_bytes=0,
            )


_BOOTSTRAP_SCRIPT: Final = r"""
import ctypes
import errno
import hashlib
import json
import os
import runpy
import socket
import stat
import sys

SYS_CLOSE_RANGE = 436
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1
PR_SET_NO_NEW_PRIVS = 38
MINIMUM_LANDLOCK_ABI = 4

ACCESS_FS_EXECUTE = 1 << 0
ACCESS_FS_WRITE_FILE = 1 << 1
ACCESS_FS_READ_FILE = 1 << 2
ACCESS_FS_READ_DIR = 1 << 3
ACCESS_FS_REMOVE_DIR = 1 << 4
ACCESS_FS_REMOVE_FILE = 1 << 5
ACCESS_FS_MAKE_CHAR = 1 << 6
ACCESS_FS_MAKE_DIR = 1 << 7
ACCESS_FS_MAKE_REG = 1 << 8
ACCESS_FS_MAKE_SOCK = 1 << 9
ACCESS_FS_MAKE_FIFO = 1 << 10
ACCESS_FS_MAKE_BLOCK = 1 << 11
ACCESS_FS_MAKE_SYM = 1 << 12
ACCESS_FS_REFER = 1 << 13
ACCESS_FS_TRUNCATE = 1 << 14
ACCESS_NET_BIND_TCP = 1 << 0
ACCESS_NET_CONNECT_TCP = 1 << 1

HANDLED_FS = (
    ACCESS_FS_EXECUTE
    | ACCESS_FS_WRITE_FILE
    | ACCESS_FS_READ_FILE
    | ACCESS_FS_READ_DIR
    | ACCESS_FS_REMOVE_DIR
    | ACCESS_FS_REMOVE_FILE
    | ACCESS_FS_MAKE_CHAR
    | ACCESS_FS_MAKE_DIR
    | ACCESS_FS_MAKE_REG
    | ACCESS_FS_MAKE_SOCK
    | ACCESS_FS_MAKE_FIFO
    | ACCESS_FS_MAKE_BLOCK
    | ACCESS_FS_MAKE_SYM
    | ACCESS_FS_REFER
    | ACCESS_FS_TRUNCATE
)
HANDLED_NET = ACCESS_NET_BIND_TCP | ACCESS_NET_CONNECT_TCP


class RulesetAttr(ctypes.Structure):
    _fields_ = [
        ("handled_access_fs", ctypes.c_uint64),
        ("handled_access_net", ctypes.c_uint64),
    ]


class PathBeneathAttr(ctypes.Structure):
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
        ("reserved", ctypes.c_uint32),
    ]


def fail(message):
    raise RuntimeError(message)


def syscall(libc, number, *arguments):
    ctypes.set_errno(0)
    result = libc.syscall(ctypes.c_long(number), *arguments)
    if result < 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, "sandbox syscall failed")
    return int(result)


def close_nonstandard_fds(preserved_fd):
    if preserved_fd != 3:
        fail("handshake descriptor was not normalized")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    syscall(
        libc,
        SYS_CLOSE_RANGE,
        ctypes.c_uint(4),
        ctypes.c_uint(0xFFFFFFFF),
        ctypes.c_uint(0),
    )


def open_handshake_file(path):
    flags = os.O_WRONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    metadata = os.fstat(descriptor)
    if (
        descriptor < 3
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_size != 0
    ):
        os.close(descriptor)
        fail("unsafe handshake file")
    if descriptor != 3:
        os.dup2(descriptor, 3, inheritable=False)
        os.close(descriptor)
        descriptor = 3
    return descriptor


def write_handshake(descriptor, encoded):
    content = (encoded + "\n").encode("ascii")
    if len(content) > 4096:
        fail("oversized handshake")
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                fail("short handshake write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def add_path_rule(libc, ruleset_fd, path, allowed_access):
    flags = os.O_PATH | os.O_CLOEXEC
    descriptor = os.open(path, flags)
    try:
        attribute = PathBeneathAttr(
            allowed_access=allowed_access,
            parent_fd=descriptor,
            reserved=0,
        )
        syscall(
            libc,
            SYS_LANDLOCK_ADD_RULE,
            ctypes.c_int(ruleset_fd),
            ctypes.c_int(LANDLOCK_RULE_PATH_BENEATH),
            ctypes.byref(attribute),
            ctypes.c_uint(0),
        )
    finally:
        os.close(descriptor)


def apply_landlock(artifact_path, working_directory):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    libc.prctl.restype = ctypes.c_int
    abi = syscall(
        libc,
        SYS_LANDLOCK_CREATE_RULESET,
        ctypes.c_void_p(),
        ctypes.c_size_t(0),
        ctypes.c_uint(LANDLOCK_CREATE_RULESET_VERSION),
    )
    if abi < MINIMUM_LANDLOCK_ABI:
        fail("unsupported Landlock ABI")
    attribute = RulesetAttr(
        handled_access_fs=HANDLED_FS,
        handled_access_net=HANDLED_NET,
    )
    ruleset_fd = syscall(
        libc,
        SYS_LANDLOCK_CREATE_RULESET,
        ctypes.byref(attribute),
        ctypes.c_size_t(ctypes.sizeof(attribute)),
        ctypes.c_uint(0),
    )
    try:
        seen = set()
        for candidate in ("/usr", "/lib", "/lib64"):
            real_path = os.path.realpath(candidate)
            if os.path.isdir(real_path) and real_path not in seen:
                seen.add(real_path)
                add_path_rule(
                    libc,
                    ruleset_fd,
                    real_path,
                    ACCESS_FS_EXECUTE | ACCESS_FS_READ_FILE | ACCESS_FS_READ_DIR,
                )
        add_path_rule(libc, ruleset_fd, artifact_path, ACCESS_FS_READ_FILE)
        add_path_rule(libc, ruleset_fd, working_directory, ACCESS_FS_READ_DIR)
        linker_cache = "/etc/ld.so.cache"
        if os.path.isfile(linker_cache):
            add_path_rule(libc, ruleset_fd, linker_cache, ACCESS_FS_READ_FILE)
        ctypes.set_errno(0)
        if libc.prctl(
            ctypes.c_int(PR_SET_NO_NEW_PRIVS),
            ctypes.c_ulong(1),
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
        ) != 0:
            error_number = ctypes.get_errno()
            raise OSError(error_number, "no-new-privileges failed")
        syscall(
            libc,
            SYS_LANDLOCK_RESTRICT_SELF,
            ctypes.c_int(ruleset_fd),
            ctypes.c_uint(0),
        )
    finally:
        os.close(ruleset_fd)
    return abi


def denied_open(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as error:
        return error.errno in (errno.EACCES, errno.EPERM)
    else:
        os.close(descriptor)
        return False


def denied_parent_list(parent_directory):
    try:
        os.listdir(parent_directory)
    except OSError as error:
        return error.errno in (errno.EACCES, errno.EPERM)
    return False


def denied_cwd_write(working_directory):
    probe_path = os.path.join(working_directory, "write-probe")
    try:
        descriptor = os.open(
            probe_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
        )
    except OSError as error:
        return error.errno in (errno.EACCES, errno.EPERM)
    else:
        os.close(descriptor)
        return False


def denied_socket_creation():
    try:
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    except OSError as error:
        return error.errno in (errno.EACCES, errno.EPERM)
    else:
        probe.close()
        return False


def sha256_path(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1048576)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def bootstrap():
    if len(sys.argv) != 7:
        fail("invalid bootstrap arguments")
    (
        expected_digest,
        nonce,
        artifact_path,
        working_directory,
        canary_path,
        handshake_path,
    ) = sys.argv[1:]
    if (
        len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
        or len(nonce) != 32
        or any(character not in "0123456789abcdef" for character in nonce)
        or not all(
            os.path.isabs(path)
            for path in (artifact_path, working_directory, canary_path, handshake_path)
        )
        or os.getcwd() != working_directory
        or os.listdir(working_directory)
    ):
        fail("invalid bootstrap state")
    handshake_fd = open_handshake_file(handshake_path)
    close_nonstandard_fds(handshake_fd)
    landlock_abi = apply_landlock(artifact_path, working_directory)
    close_nonstandard_fds(handshake_fd)
    if sha256_path(artifact_path) != expected_digest:
        fail("artifact digest mismatch")
    parent_directory = os.path.dirname(working_directory)
    probes = {
        "canary_open_denied": denied_open(canary_path),
        "cwd_write_denied": denied_cwd_write(working_directory),
        "etc_passwd_open_denied": denied_open("/etc/passwd"),
        "handshake_reopen_denied": denied_open(handshake_path),
        "parent_list_denied": denied_parent_list(parent_directory),
        "systemd_socket_creation_denied": denied_socket_creation(),
    }
    if set(probes.values()) != {True}:
        fail("sandbox self-probe failed")
    handshake = {
        "artifact_sha256": expected_digest,
        "landlock_abi": landlock_abi,
        "nonce": nonce,
        "probes": probes,
        "schema": "kp1979-v3-sandbox-handshake-v1",
    }
    encoded = json.dumps(
        handshake,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    write_handshake(handshake_fd, encoded)
    global HANDSHAKE_SENT
    HANDSHAKE_SENT = True
    try:
        runpy.run_path(artifact_path, run_name="__main__")
    except SystemExit as error:
        if error.code not in (None, 0):
            raise


HANDSHAKE_SENT = False
try:
    bootstrap()
except BaseException:
    message = "sandbox_worker_failure\n" if HANDSHAKE_SENT else "sandbox_bootstrap_failure\n"
    try:
        sys.stderr.write(message)
        sys.stderr.flush()
    finally:
        os._exit(113 if HANDSHAKE_SENT else 112)
"""


__all__ = [
    "ANSWER_FREE_REQUEST_KEYS",
    "MAX_REQUEST_BYTES",
    "MAX_STDERR_BYTES",
    "MAX_STDOUT_BYTES",
    "MINIMUM_LANDLOCK_ABI",
    "SANDBOX_SCHEMA",
    "SYSTEMD_PROPERTIES",
    "WORKER_INTERFACE_VERSION",
    "SandboxInvocationResult",
    "SandboxPreflightError",
    "SandboxedWorkerInvoker",
    "build_systemd_command",
]
