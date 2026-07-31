from __future__ import annotations

import contextlib
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import indusbench.kp1979_v3_sandbox as sandbox


def _request(payload: str = "UDQKMSAxCg==") -> bytes:
    return (
        json.dumps(
            {
                "height": 1,
                "interface_version": "kp1979-label-detector-v3-worker-v1",
                "pbm_base64": payload,
                "scan_bands": [[0, 0, 1, 1]],
                "width": 1,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _dummy_zipapp(path: Path) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "__main__.py",
            "import sys\n"
            "request = sys.stdin.buffer.read()\n"
            "sys.stdout.buffer.write(request)\n"
            "sys.stdout.buffer.flush()\n",
        )
    os.chmod(path, 0o600)
    return sha256(path.read_bytes()).hexdigest()


def _ordinary_failures() -> list[tuple[str, Exception]]:
    return [
        ("timeout", subprocess.TimeoutExpired(("synthetic",), 0.01)),
        ("oserror", OSError("synthetic ordinary failure")),
        ("subprocess", subprocess.SubprocessError("synthetic subprocess failure")),
        ("runtime", RuntimeError("synthetic runtime failure")),
    ]


def _interrupt_failures() -> list[tuple[str, BaseException]]:
    return [
        ("keyboard", KeyboardInterrupt("synthetic keyboard interrupt")),
        ("system_exit", SystemExit("synthetic system exit")),
        ("generator_exit", GeneratorExit("synthetic generator exit")),
    ]


class _ControlledProcess:
    def __init__(
        self,
        *,
        communicate: Sequence[BaseException | int | None] = (),
        wait: Sequence[BaseException | int | None] = (),
        returncode: int | None = None,
        returncode_events: Sequence[BaseException | int | None] = (),
        pid: int = 424242,
    ) -> None:
        self.pid = pid
        self._returncode = returncode
        self._returncode_events = list(returncode_events)
        self.communicate_outcomes = list(communicate)
        self.wait_outcomes = list(wait)
        self.communicate_timeouts: list[float | None] = []
        self.wait_timeouts: list[float | None] = []

    @property
    def returncode(self) -> int | None:
        if self._returncode_events:
            outcome = self._returncode_events.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            self._returncode = outcome
        return self._returncode

    def _apply(self, outcome: BaseException | int | None) -> None:
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome is not None:
            self._returncode = outcome

    def communicate(
        self,
        input: bytes | None = None,
        timeout: float | None = None,
    ) -> tuple[None, None]:
        if input is not None:
            raise AssertionError("the sandbox client must not receive input")
        self.communicate_timeouts.append(timeout)
        if self.communicate_outcomes:
            self._apply(self.communicate_outcomes.pop(0))
        return None, None

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(timeout)
        if self.wait_outcomes:
            self._apply(self.wait_outcomes.pop(0))
        return 0 if self._returncode is None else self._returncode


def _new_invoker(base: Path) -> sandbox.SandboxedWorkerInvoker:
    artifact = base / "worker.pyz"
    digest = _dummy_zipapp(artifact)
    return sandbox.SandboxedWorkerInvoker(
        worker_artifact=artifact,
        expected_sha256=digest,
        python_executable=Path("/usr/bin/python3"),
    )


def _flood_zipapp(path: Path) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "__main__.py",
            "import os\nblock = b'x' * 65536\nwhile True:\n    os.write(1, block)\n",
        )
    os.chmod(path, 0o600)
    return sha256(path.read_bytes()).hexdigest()


def _hostile_stdout_zipapp(path: Path) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "__main__.py",
            """import ctypes
import errno
import os
import sys


class IOVec(ctypes.Structure):
    _fields_ = [("base", ctypes.c_void_p), ("length", ctypes.c_size_t)]


def expect_os_eperm(name, operation):
    try:
        result = operation()
    except OSError as error:
        if error.errno != errno.EPERM:
            raise RuntimeError(name + " returned the wrong errno") from error
    else:
        if isinstance(result, int) and result >= 0:
            os.close(result)
        raise RuntimeError(name + " was not filtered")


def expect_libc_eperm(name, operation):
    ctypes.set_errno(0)
    result = operation()
    error_number = ctypes.get_errno()
    if result != -1 or error_number != errno.EPERM:
        raise RuntimeError(name + " was not filtered")


libc = ctypes.CDLL(None, use_errno=True)
libc.process_vm_readv.restype = ctypes.c_ssize_t
libc.ptrace.restype = ctypes.c_long
libc.pidfd_getfd.restype = ctypes.c_int

for descriptor in range(3, 256):
    try:
        os.fstat(descriptor)
    except OSError as error:
        if error.errno != errno.EBADF:
            raise RuntimeError("descriptor probe returned the wrong errno") from error
    else:
        raise RuntimeError("nonstandard descriptor reached the worker")

source = ctypes.create_string_buffer(b"x")
destination = ctypes.create_string_buffer(1)
local_iovec = IOVec(ctypes.cast(destination, ctypes.c_void_p), 1)
remote_iovec = IOVec(ctypes.cast(source, ctypes.c_void_p), 1)
expect_libc_eperm(
    "process_vm_readv",
    lambda: libc.process_vm_readv(
        os.getpid(),
        ctypes.byref(local_iovec),
        1,
        ctypes.byref(remote_iovec),
        1,
        0,
    ),
)
expect_os_eperm("pidfd_open", lambda: os.pidfd_open(os.getpid(), 0))
expect_os_eperm("kill", lambda: os.kill(os.getpid(), 0))
expect_os_eperm("memfd_create", lambda: os.memfd_create("kp1979-probe", 0))
expect_libc_eperm("ptrace", lambda: libc.ptrace(16, -1, None, None))
expect_libc_eperm("pidfd_getfd", lambda: libc.pidfd_getfd(-1, -1, 0))

try:
    open(sys.argv[-1], "wb")
except PermissionError:
    pass
else:
    raise RuntimeError("handshake path unexpectedly reopened")
os.lseek(1, 0, os.SEEK_SET)
os.ftruncate(1, 0)
os.write(1, b'{"fake_handshake":true}\\n')
""",
        )
    os.chmod(path, 0o600)
    return sha256(path.read_bytes()).hexdigest()


def _fd_probe_zipapp(path: Path) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "__main__.py",
            """import errno
import os
import sys

try:
    os.fstat(3)
except OSError as error:
    if error.errno != errno.EBADF:
        raise
else:
    raise RuntimeError("descriptor three reached the worker")
request = sys.stdin.buffer.read()
sys.stdout.buffer.write(request)
sys.stdout.buffer.flush()
""",
        )
    os.chmod(path, 0o600)
    return sha256(path.read_bytes()).hexdigest()


def _worker_reached_zipapp(path: Path) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "__main__.py",
            "import os\nos.write(1, b'worker-reached\\n')\n",
        )
    os.chmod(path, 0o600)
    return sha256(path.read_bytes()).hexdigest()


def _execve_boundary_zipapp(path: Path) -> str:
    second_stage = """import errno
import os
import socket

for descriptor in range(3, 256):
    try:
        os.fstat(descriptor)
    except OSError as error:
        if error.errno != errno.EBADF:
            raise
    else:
        raise RuntimeError("nonstandard descriptor survived execve")
try:
    open("/etc/passwd", "rb")
except PermissionError:
    pass
else:
    raise RuntimeError("Landlock did not survive execve")
try:
    os.kill(os.getpid(), 0)
except OSError as error:
    if error.errno != errno.EPERM:
        raise
else:
    raise RuntimeError("seccomp signal filter did not survive execve")
try:
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
except OSError as error:
    if error.errno != errno.EPERM:
        raise
else:
    probe.close()
    raise RuntimeError("seccomp network filter did not survive execve")
os.write(1, b'{"execve_boundary":true}\\n')
"""
    first_stage = (
        "import os\n"
        "import sys\n"
        f"second_stage = {second_stage!r}\n"
        "os.execve(\n"
        "    sys.executable,\n"
        '    [sys.executable, "-I", "-S", "-B", "-c", second_stage],\n'
        '    {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin"},\n'
        ")\n"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("__main__.py", first_stage)
    os.chmod(path, 0o600)
    return sha256(path.read_bytes()).hexdigest()


def _write_fd3_wrapper(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/python3
import os
import sys

arguments = sys.argv[1:]
if not arguments or arguments[0] != "-i":
    raise RuntimeError("closed environment invocation required")
environment = {}
index = 1
while index < len(arguments) and "=" in arguments[index]:
    key, value = arguments[index].split("=", 1)
    environment[key] = value
    index += 1
if index >= len(arguments):
    raise RuntimeError("missing Python executable")
descriptor = os.open("/dev/null", os.O_RDONLY)
if descriptor == 3:
    os.set_inheritable(descriptor, True)
else:
    os.dup2(descriptor, 3, inheritable=True)
    os.close(descriptor)
os.execve(arguments[index], arguments[index:], environment)
""",
        encoding="ascii",
    )
    os.chmod(path, 0o700)


def _write_close_range_denial_wrapper(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/python3
import ctypes
import errno
import os
import sys


class SockFilter(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("jump_true", ctypes.c_ubyte),
        ("jump_false", ctypes.c_ubyte),
        ("constant", ctypes.c_uint32),
    ]


class SockFprog(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ushort),
        ("filters", ctypes.POINTER(SockFilter)),
    ]


filters = (SockFilter * 4)(
    SockFilter(0x20, 0, 0, 0),
    SockFilter(0x15, 0, 1, 436),
    SockFilter(0x06, 0, 0, 0x00050000 | errno.EPERM),
    SockFilter(0x06, 0, 0, 0x7FFF0000),
)
program = SockFprog(len(filters), filters)
libc = ctypes.CDLL(None, use_errno=True)
libc.prctl.restype = ctypes.c_int
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")
if libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "PR_SET_SECCOMP failed")
os.execve(sys.executable, [sys.executable, *sys.argv[1:]], dict(os.environ))
""",
        encoding="ascii",
    )
    os.chmod(path, 0o700)


class KP1979V3SandboxContractTests(unittest.TestCase):
    def test_command_is_closed_argv_with_all_systemd_limits_and_minimal_worker_env(self) -> None:
        expected_system_call_filter = (
            "SystemCallFilter=~@cpu-emulation @debug @ipc @keyring @mount @network-io "
            "@obsolete @privileged @resources clone clone3 execveat fork io_uring_enter "
            "io_uring_register io_uring_setup kcmp kill pidfd_open pidfd_send_signal "
            "prlimit64 process_mrelease rt_sigqueueinfo rt_tgsigqueueinfo setns tgkill "
            "tkill unshare vfork"
        )
        self.assertEqual(expected_system_call_filter, sandbox.SYSTEM_CALL_FILTER)
        self.assertNotIn("@signal", sandbox.SYSTEM_CALL_FILTER)
        self.assertNotIn("@process", sandbox.SYSTEM_CALL_FILTER)
        nonce = "a" * 32
        command = sandbox.build_systemd_command(
            systemd_run=Path("/usr/bin/systemd-run"),
            env_executable=Path("/usr/bin/env"),
            python_executable=Path("/usr/bin/python3"),
            unit_name=f"indus-kp1979-v3-{nonce}",
            nonce=nonce,
            artifact_sha256="b" * 64,
            artifact_path=Path("/tmp/sandbox/worker.pyz"),
            working_directory=Path("/tmp/sandbox/cwd"),
            canary_path=Path("/tmp/sandbox/canary.bin"),
            request_path=Path("/tmp/sandbox/request.bin"),
            stdout_path=Path("/tmp/sandbox/stdout.bin"),
            stderr_path=Path("/tmp/sandbox/stderr.bin"),
            handshake_path=Path("/tmp/sandbox/handshake.bin"),
        )

        self.assertIsInstance(command, tuple)
        self.assertEqual("/usr/bin/systemd-run", command[0])
        for required in (
            "--user",
            "--wait",
            "--collect",
            "--quiet",
            "--service-type=exec",
            "--property=NoNewPrivileges=yes",
            "--property=SystemCallArchitectures=native",
            f"--property={expected_system_call_filter}",
            "--property=SystemCallErrorNumber=EPERM",
            "--property=RestrictAddressFamilies=AF_UNIX",
            "--property=TasksMax=1",
            "--property=RuntimeMaxSec=35s",
            "--property=MemoryMax=1073741824",
            "--property=LimitCPU=24",
            "--property=LimitNOFILE=32",
            "--property=LimitCORE=0",
            "--property=LimitFSIZE=131072",
            "--property=UMask=0077",
            "--property=KeyringMode=private",
            "--property=LockPersonality=yes",
            "--property=MemoryDenyWriteExecute=yes",
            "--property=StandardInput=file:/tmp/sandbox/request.bin",
            "--property=StandardOutput=file:/tmp/sandbox/stdout.bin",
            "--property=StandardError=file:/tmp/sandbox/stderr.bin",
        ):
            self.assertIn(required, command)
        self.assertNotIn("--pipe", command)
        env_position = command.index("/usr/bin/env")
        self.assertEqual(
            (
                "/usr/bin/env",
                "-i",
                "LANG=C.UTF-8",
                "LC_ALL=C.UTF-8",
                "PATH=/usr/bin:/bin",
                "/usr/bin/python3",
                "-I",
                "-S",
                "-B",
                "-c",
            ),
            command[env_position : env_position + 10],
        )
        joined = "\0".join(command)
        for forbidden in (
            "case_id",
            "case_class",
            "truth",
            "reference",
            "roster",
            "HOME=",
        ):
            self.assertNotIn(forbidden, joined)

    def test_bootstrap_applies_landlock_and_probes_before_runpy(self) -> None:
        source = sandbox._BOOTSTRAP_SCRIPT
        compile(source, "<kp1979-v3-bootstrap>", "exec")
        for required in (
            "SYS_CLOSE_RANGE = 436",
            "SYS_LANDLOCK_CREATE_RULESET = 444",
            "SYS_LANDLOCK_ADD_RULE = 445",
            "SYS_LANDLOCK_RESTRICT_SELF = 446",
            "PR_SET_NO_NEW_PRIVS = 38",
            "ACCESS_FS_TRUNCATE = 1 << 14",
            "ACCESS_NET_BIND_TCP = 1 << 0",
            "ACCESS_NET_CONNECT_TCP = 1 << 1",
            'denied_open("/etc/passwd")',
            "open_handshake_file(handshake_path)",
            "write_handshake(handshake_fd, encoded)",
            "socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)",
            "denied_socket_creation()",
            'runpy.run_path(artifact_path, run_name="__main__")',
        ):
            self.assertIn(required, source)
        open_handshake = source.rindex("handshake_fd = open_handshake_file(handshake_path)")
        first_close_range = source.index(
            "close_nonstandard_fds(handshake_fd)",
            open_handshake,
        )
        apply_landlock = source.rindex(
            "landlock_abi = apply_landlock(artifact_path, working_directory)"
        )
        second_close_range = source.index(
            "close_nonstandard_fds(handshake_fd)",
            apply_landlock,
        )
        probes = source.rindex("probes = {")
        write_handshake = source.rindex("write_handshake(handshake_fd, encoded)")
        run_worker = source.rindex('runpy.run_path(artifact_path, run_name="__main__")')
        ordered_boundary = (
            open_handshake,
            first_close_range,
            apply_landlock,
            second_close_range,
            probes,
            write_handshake,
            run_worker,
        )
        self.assertEqual(tuple(sorted(ordered_boundary)), ordered_boundary)
        self.assertEqual(2, source.count("close_nonstandard_fds(handshake_fd)"))
        close_definition = source[
            source.index("def close_nonstandard_fds(") : source.index("def open_handshake_file(")
        ]
        self.assertIn("SYS_CLOSE_RANGE", close_definition)
        handshake_writer = source[
            source.index("def write_handshake(") : source.index("def add_path_rule(")
        ]
        self.assertIn("finally:\n        os.close(descriptor)", handshake_writer)
        self.assertNotIn("sys.stdout.write(encoded", source)

    def test_answer_free_request_rejects_extra_or_malformed_fields(self) -> None:
        with self.assertRaises(ValueError):
            sandbox._validate_answer_free_request(
                _request().replace(b'"width":1', b'"truth":[],"width":1')
            )
        with self.assertRaises(ValueError):
            sandbox._validate_answer_free_request(b'{"width":1,"width":1}\n')
        with self.assertRaises(ValueError):
            sandbox._validate_answer_free_request(_request("not-base64"))
        with self.assertRaises(ValueError):
            sandbox._validate_answer_free_request(_request().replace(b'":', b'": ', 1))
        with self.assertRaises(ValueError):
            sandbox._validate_answer_free_request(b"")
        sandbox._validate_answer_free_request(_request())

    def test_deep_request_is_redacted_by_invoker_without_starting_a_process(self) -> None:
        depth = 2_000
        request = b'{"x":' + (b"[" * depth) + b"0" + (b"]" * depth) + b"}\n"
        self.assertLess(len(request), sandbox.MAX_REQUEST_BYTES)
        invoker = object.__new__(sandbox.SandboxedWorkerInvoker)
        result = invoker(request)
        self.assertEqual("request_rejected", result.disposition)
        self.assertEqual("request_contract", result.failure_code)
        self.assertFalse(result.process_started)
        self.assertEqual(b"", result.worker_stdout)

    def test_numeric_parser_failures_are_redacted_without_starting_a_process(self) -> None:
        replacements = (
            b"9" * 5_000,
            b"1e999",
        )
        for replacement in replacements:
            request = _request().replace(b'"width":1', b'"width":' + replacement)
            self.assertLess(len(request), sandbox.MAX_REQUEST_BYTES)
            invoker = object.__new__(sandbox.SandboxedWorkerInvoker)
            with self.subTest(replacement_prefix=replacement[:16]):
                result = invoker(request)
                self.assertEqual("request_rejected", result.disposition)
                self.assertEqual("request_contract", result.failure_code)
                self.assertFalse(result.process_started)
                self.assertEqual(b"", result.worker_stdout)

    def test_deep_handshake_is_normalized_to_value_error(self) -> None:
        depth = 2_000
        line = b'{"x":' + (b"[" * depth) + b"0" + (b"]" * depth) + b"}\n"
        self.assertLess(len(line), sandbox.MAX_HANDSHAKE_BYTES)
        with self.assertRaisesRegex(ValueError, "handshake"):
            sandbox._parse_verified_handshake(
                line,
                nonce="1" * 32,
                artifact_sha256="2" * 64,
            )

    def test_handshake_requires_canonical_closed_all_true_proof(self) -> None:
        nonce = "1" * 32
        digest = "2" * 64
        value = {
            "artifact_sha256": digest,
            "landlock_abi": 4,
            "nonce": nonce,
            "probes": {key: True for key in sandbox.PROBE_KEYS},
            "schema": sandbox.SANDBOX_SCHEMA,
        }
        line = sandbox._canonical_json_line(value)
        self.assertEqual(
            4,
            sandbox._parse_verified_handshake(
                line,
                nonce=nonce,
                artifact_sha256=digest,
            ),
        )
        noncanonical = json.dumps(value, sort_keys=True).encode("ascii") + b"\n"
        with self.assertRaises(ValueError):
            sandbox._parse_verified_handshake(
                noncanonical,
                nonce=nonce,
                artifact_sha256=digest,
            )
        value["probes"]["canary_open_denied"] = False
        with self.assertRaises(ValueError):
            sandbox._parse_verified_handshake(
                sandbox._canonical_json_line(value),
                nonce=nonce,
                artifact_sha256=digest,
            )

    def test_artifact_requires_regular_owner_single_link_safe_mode_and_digest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-artifact-test-") as raw:
            base = Path(raw)
            artifact = base / "worker.pyz"
            digest = _dummy_zipapp(artifact)
            snapshot = sandbox._read_frozen_artifact(artifact, digest)
            self.assertEqual(digest, snapshot.digest)

            os.chmod(artifact, 0o622)
            with self.assertRaises(sandbox.SandboxPreflightError):
                sandbox._read_frozen_artifact(artifact, digest)
            os.chmod(artifact, 0o600)

            second_link = base / "second.pyz"
            os.link(artifact, second_link)
            with self.assertRaises(sandbox.SandboxPreflightError):
                sandbox._read_frozen_artifact(artifact, digest)
            second_link.unlink()

            symbolic_link = base / "symbolic.pyz"
            symbolic_link.symlink_to(artifact)
            with self.assertRaises(sandbox.SandboxPreflightError):
                sandbox._read_frozen_artifact(symbolic_link, digest)
            with self.assertRaises(sandbox.SandboxPreflightError):
                sandbox._read_frozen_artifact(artifact, "0" * 64)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux-only invoker")
    def test_artifact_fstat_read_close_failure_matrix_is_closed_and_never_counts_start(
        self,
    ) -> None:
        for stage in ("fstat", "read", "close"):
            failures: list[tuple[str, BaseException]] = [
                *_ordinary_failures(),
                *_interrupt_failures(),
            ]
            for label, failure in failures:
                with self.subTest(stage=stage, failure=label):
                    with tempfile.TemporaryDirectory(
                        prefix="indus-kp1979-v3-artifact-io-matrix-"
                    ) as raw:
                        invoker = _new_invoker(Path(raw))
                        real_close = os.close
                        leaked_descriptors: list[int] = []

                        def failing_close(
                            descriptor: int,
                            _leaked: list[int] = leaked_descriptors,
                            _failure: BaseException = failure,
                        ) -> None:
                            _leaked.append(descriptor)
                            raise _failure

                        replacements: dict[str, Any] = {
                            "fstat": patch.object(sandbox.os, "fstat", side_effect=failure),
                            "read": patch.object(sandbox.os, "read", side_effect=failure),
                            "close": patch.object(sandbox.os, "close", new=failing_close),
                        }
                        with replacements[stage]:
                            if isinstance(failure, Exception):
                                result = invoker(_request())
                                self.assertEqual("artifact_changed", result.failure_code)
                                self.assertFalse(result.process_started)
                            else:
                                with self.assertRaises(type(failure)) as raised:
                                    invoker(_request())
                                self.assertIs(failure, raised.exception)
                        for descriptor in leaked_descriptors:
                            real_close(descriptor)
                    self.assertEqual(0, invoker.started_process_count)
                    self.assertEqual(0, invoker.verified_invocation_count)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux-only invoker")
    def test_artifact_primary_and_close_interrupt_precedence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-artifact-precedence-") as raw:
            invoker = _new_invoker(Path(raw))
            real_close = os.close
            leaked_descriptors: list[int] = []
            ordinary_primary = RuntimeError("ordinary artifact read")
            cleanup_interrupt = SystemExit("artifact close interrupt")

            def precedence_close(descriptor: int) -> None:
                leaked_descriptors.append(descriptor)
                raise cleanup_interrupt

            with (
                patch.object(sandbox.os, "read", side_effect=ordinary_primary),
                patch.object(sandbox.os, "close", new=precedence_close),
                self.assertRaises(SystemExit) as raised,
            ):
                invoker(_request())
            self.assertIs(cleanup_interrupt, raised.exception)
            for descriptor in leaked_descriptors:
                real_close(descriptor)

            primary_interrupt = KeyboardInterrupt("artifact primary interrupt")
            cleanup_interrupt = SystemExit("later artifact close interrupt")
            leaked_descriptors = []

            def later_failing_close(descriptor: int) -> None:
                leaked_descriptors.append(descriptor)
                raise cleanup_interrupt

            with (
                patch.object(sandbox.os, "read", side_effect=primary_interrupt),
                patch.object(sandbox.os, "close", new=later_failing_close),
                self.assertRaises(KeyboardInterrupt) as raised,
            ):
                invoker(_request())
            self.assertIs(primary_interrupt, raised.exception)
            for descriptor in leaked_descriptors:
                real_close(descriptor)
        self.assertEqual(0, invoker.started_process_count)

    def test_handshake_fstat_read_close_matrix_normalizes_ordinary_exceptions(
        self,
    ) -> None:
        for stage in ("fstat", "read", "close"):
            failures: list[tuple[str, BaseException]] = [
                *_ordinary_failures(),
                *_interrupt_failures(),
            ]
            for label, failure in failures:
                with (
                    self.subTest(stage=stage, failure=label),
                    tempfile.TemporaryDirectory(
                        prefix="indus-kp1979-v3-handshake-io-matrix-"
                    ) as raw,
                ):
                    path = Path(raw) / "handshake.bin"
                    path.write_bytes(b"synthetic\n")
                    os.chmod(path, 0o600)
                    real_close = os.close
                    leaked_descriptors: list[int] = []

                    def failing_close(
                        descriptor: int,
                        _leaked: list[int] = leaked_descriptors,
                        _failure: BaseException = failure,
                    ) -> None:
                        _leaked.append(descriptor)
                        raise _failure

                    replacements: dict[str, Any] = {
                        "fstat": patch.object(sandbox.os, "fstat", side_effect=failure),
                        "read": patch.object(sandbox.os, "read", side_effect=failure),
                        "close": patch.object(sandbox.os, "close", new=failing_close),
                    }
                    with replacements[stage]:
                        if isinstance(failure, Exception):
                            with self.assertRaises(ValueError) as raised:
                                sandbox._read_handshake_file(path)
                            self.assertIs(failure, raised.exception.__cause__)
                        else:
                            with self.assertRaises(type(failure)) as raised:
                                sandbox._read_handshake_file(path)
                            self.assertIs(failure, raised.exception)
                    for descriptor in leaked_descriptors:
                        real_close(descriptor)

    def test_bounded_output_fstat_read_and_close_preserve_exact_failure(self) -> None:
        for stage in ("fstat", "read", "close"):
            failures: list[tuple[str, BaseException]] = [
                *_ordinary_failures(),
                *_interrupt_failures(),
            ]
            for label, failure in failures:
                with (
                    self.subTest(stage=stage, failure=label),
                    tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-output-io-matrix-") as raw,
                ):
                    path = Path(raw) / "stdout.bin"
                    path.write_bytes(b"synthetic")
                    os.chmod(path, 0o600)
                    real_close = os.close
                    leaked_descriptors: list[int] = []

                    def failing_close(
                        descriptor: int,
                        _leaked: list[int] = leaked_descriptors,
                        _failure: BaseException = failure,
                    ) -> None:
                        _leaked.append(descriptor)
                        raise _failure

                    replacements: dict[str, Any] = {
                        "fstat": patch.object(sandbox.os, "fstat", side_effect=failure),
                        "read": patch.object(sandbox.os, "read", side_effect=failure),
                        "close": patch.object(sandbox.os, "close", new=failing_close),
                    }
                    replacement = replacements[stage]
                    with replacement, self.assertRaises(type(failure)) as raised:
                        sandbox._read_bounded_file(path, 32)
                    self.assertIs(failure, raised.exception)
                    for descriptor in leaked_descriptors:
                        real_close(descriptor)

    @unittest.skipUnless(hasattr(os, "O_NONBLOCK"), "requires O_NONBLOCK")
    def test_all_parent_readers_use_nonblocking_open_and_reject_fifo(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-fifo-reader-") as raw:
            fifo = Path(raw) / "synthetic.fifo"
            os.mkfifo(fifo, 0o600)
            real_open = os.open
            observed_flags: list[int] = []

            def checked_open(path: os.PathLike[str] | str, flags: int, mode: int = 0o777) -> int:
                observed_flags.append(flags)
                if not flags & os.O_NONBLOCK:
                    raise AssertionError("reader omitted O_NONBLOCK")
                return real_open(path, flags, mode)

            with patch.object(sandbox.os, "open", new=checked_open):
                with self.assertRaises(sandbox.SandboxPreflightError):
                    sandbox._read_frozen_artifact(fifo, "0" * 64)
                with self.assertRaises(ValueError):
                    sandbox._read_handshake_file(fifo)
                with self.assertRaises(ValueError):
                    sandbox._read_bounded_file(fifo, 32)
        self.assertEqual(3, len(observed_flags))
        self.assertTrue(all(flags & os.O_NONBLOCK for flags in observed_flags))

    def test_bounded_reader_rejects_unsafe_regular_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-bounded-metadata-") as raw:
            path = Path(raw) / "stdout.bin"
            path.write_bytes(b"synthetic")
            os.chmod(path, 0o644)
            with self.assertRaises(ValueError):
                sandbox._read_bounded_file(path, 32)
            os.chmod(path, 0o600)
            second_link = Path(raw) / "stdout-second-link.bin"
            os.link(path, second_link)
            with self.assertRaises(ValueError):
                sandbox._read_bounded_file(path, 32)

    def test_bounded_reader_rejects_mutation_and_short_read_but_returns_limit_plus_one(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-bounded-stability-") as raw:
            path = Path(raw) / "stdout.bin"
            path.write_bytes(b"original")
            os.chmod(path, 0o600)
            real_fstat = os.fstat
            fstat_calls = 0

            def mutate_before_second_fstat(descriptor: int) -> os.stat_result:
                nonlocal fstat_calls
                fstat_calls += 1
                if fstat_calls == 2:
                    path.write_bytes(b"changed-size")
                return real_fstat(descriptor)

            with (
                patch.object(sandbox.os, "fstat", new=mutate_before_second_fstat),
                self.assertRaises(ValueError),
            ):
                sandbox._read_bounded_file(path, 32)
            self.assertEqual(2, fstat_calls)

            path.write_bytes(b"short-read")
            os.chmod(path, 0o600)
            real_read = os.read
            first_read = True

            def truncate_first_read(descriptor: int, size: int) -> bytes:
                nonlocal first_read
                block = real_read(descriptor, size)
                if first_read:
                    first_read = False
                    return block[:-1]
                return block

            with (
                patch.object(sandbox.os, "read", new=truncate_first_read),
                self.assertRaises(ValueError),
            ):
                sandbox._read_bounded_file(path, 32)

            content = bytes(range(64))
            path.write_bytes(content)
            os.chmod(path, 0o600)
            bounded = sandbox._read_bounded_file(path, 32)
            self.assertEqual(content[:33], bounded)
            self.assertEqual(33, len(bounded))

    def test_exclusive_write_and_close_preserve_primary_precedence(self) -> None:
        failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for stage in ("write", "fsync", "close"):
            for label, failure in failures:
                with (
                    self.subTest(stage=stage, failure=label),
                    tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-write-io-matrix-") as raw,
                ):
                    path = Path(raw) / "request.bin"
                    real_close = os.close
                    leaked_descriptors: list[int] = []
                    close_calls = 0

                    def observed_close(
                        descriptor: int,
                        _leaked: list[int] = leaked_descriptors,
                        _failure: BaseException = failure,
                        _stage: str = stage,
                        _real_close: Any = real_close,
                    ) -> None:
                        nonlocal close_calls
                        close_calls += 1
                        if _stage == "close":
                            _leaked.append(descriptor)
                            raise _failure
                        _real_close(descriptor)

                    replacement = patch.object(
                        sandbox.os,
                        "write" if stage == "write" else "fsync",
                        side_effect=failure,
                    )
                    if stage == "close":
                        replacement = contextlib.nullcontext()
                    with (
                        replacement,
                        patch.object(sandbox.os, "close", new=observed_close),
                        self.assertRaises(type(failure)) as raised,
                    ):
                        sandbox._write_exclusive(path, b"synthetic", 0o600)
                    self.assertIs(failure, raised.exception)
                    self.assertEqual(1, close_calls)
                    for descriptor in leaked_descriptors:
                        real_close(descriptor)

        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-write-precedence-") as raw:
            path = Path(raw) / "ordinary-primary.bin"
            real_close = os.close
            leaked_descriptors: list[int] = []
            ordinary_primary = RuntimeError("ordinary write primary")
            cleanup_interrupt = GeneratorExit("write close interrupt")

            def write_precedence_close(descriptor: int) -> None:
                leaked_descriptors.append(descriptor)
                raise cleanup_interrupt

            with (
                patch.object(sandbox.os, "write", side_effect=ordinary_primary),
                patch.object(sandbox.os, "close", new=write_precedence_close),
                self.assertRaises(GeneratorExit) as raised,
            ):
                sandbox._write_exclusive(path, b"synthetic", 0o600)
            self.assertIs(cleanup_interrupt, raised.exception)
            for descriptor in leaked_descriptors:
                real_close(descriptor)

    def test_temporary_directory_cleanup_primary_precedence(self) -> None:
        class ControlledDirectory:
            name = "/synthetic/owner-only"

            def __init__(self, cleanup_error: BaseException) -> None:
                self.cleanup_error = cleanup_error
                self.cleanup_calls = 0

            def cleanup(self) -> None:
                self.cleanup_calls += 1
                raise self.cleanup_error

        cases: list[tuple[str, BaseException, BaseException]] = [
            (
                "primary_interrupt",
                KeyboardInterrupt("temp primary"),
                SystemExit("temp cleanup"),
            ),
            (
                "cleanup_interrupt",
                RuntimeError("temp ordinary primary"),
                GeneratorExit("temp cleanup"),
            ),
            (
                "ordinary_primary",
                RuntimeError("temp ordinary primary"),
                OSError("temp ordinary cleanup"),
            ),
        ]
        for label, primary, cleanup in cases:
            expected = primary
            if isinstance(primary, Exception) and not isinstance(cleanup, Exception):
                expected = cleanup
            directory = ControlledDirectory(cleanup)
            with (
                self.subTest(case=label),
                patch.object(sandbox.tempfile, "TemporaryDirectory", return_value=directory),
                self.assertRaises(type(expected)) as raised,
                sandbox._temporary_directory(),
            ):
                raise primary
            self.assertIs(expected, raised.exception)
            self.assertEqual(1, directory.cleanup_calls)

        cleanup_failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for label, cleanup in cleanup_failures:
            directory = ControlledDirectory(cleanup)
            with (
                self.subTest(successful_body_cleanup=label),
                patch.object(sandbox.tempfile, "TemporaryDirectory", return_value=directory),
                self.assertRaises(type(cleanup)) as raised,
                sandbox._temporary_directory() as raw_directory,
            ):
                self.assertEqual(directory.name, raw_directory)
            self.assertIs(cleanup, raised.exception)
            self.assertEqual(1, directory.cleanup_calls)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux-only process mock")
class KP1979V3SandboxFailureTests(unittest.TestCase):
    def test_spawn_failure_is_redacted_and_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-spawn-test-") as raw:
            artifact = Path(raw) / "worker.pyz"
            digest = _dummy_zipapp(artifact)
            invoker = sandbox.SandboxedWorkerInvoker(
                worker_artifact=artifact,
                expected_sha256=digest,
                python_executable=Path("/usr/bin/python3"),
            )
            with patch.object(
                sandbox.subprocess,
                "Popen",
                side_effect=OSError("private synthetic detail"),
            ):
                result = invoker(_request())

        self.assertEqual("transport_failure", result.disposition)
        self.assertEqual("setup_failed", result.failure_code)
        self.assertEqual(b"", result.worker_stdout)
        self.assertFalse(result.handshake_verified)
        self.assertEqual(0, invoker.started_process_count)
        self.assertNotIn("private", repr(result))

    def test_request_validation_ordinary_failure_is_redacted_and_interrupt_is_preserved(
        self,
    ) -> None:
        invoker = object.__new__(sandbox.SandboxedWorkerInvoker)
        ordinary = RuntimeError("synthetic request validator failure")
        with patch.object(sandbox, "_validate_answer_free_request", side_effect=ordinary):
            result = invoker(_request())
        self.assertEqual("setup_failed", result.failure_code)
        self.assertFalse(result.process_started)

        primary_interrupt = KeyboardInterrupt("synthetic request validator interrupt")
        with (
            patch.object(
                sandbox,
                "_validate_answer_free_request",
                side_effect=primary_interrupt,
            ),
            self.assertRaises(KeyboardInterrupt) as raised,
        ):
            invoker(_request())
        self.assertIs(primary_interrupt, raised.exception)

    def test_popen_failure_matrix_preserves_interrupts_and_never_counts_start(self) -> None:
        failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for label, failure in failures:
            with self.subTest(failure=label):
                with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-popen-matrix-") as raw:
                    invoker = _new_invoker(Path(raw))
                    with patch.object(sandbox.subprocess, "Popen", side_effect=failure):
                        if isinstance(failure, Exception):
                            result = invoker(_request())
                            self.assertEqual("transport_failure", result.disposition)
                            self.assertEqual("setup_failed", result.failure_code)
                            self.assertFalse(result.process_started)
                        else:
                            with self.assertRaises(type(failure)) as raised:
                                invoker(_request())
                            self.assertIs(failure, raised.exception)
                self.assertEqual(0, invoker.started_process_count)
                self.assertEqual(0, invoker.verified_invocation_count)

    def test_initial_communicate_failure_matrix_kills_reaps_and_preserves_identity(
        self,
    ) -> None:
        failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for label, failure in failures:
            with self.subTest(failure=label):
                process = _ControlledProcess(communicate=[failure, -9], wait=[-9])
                with tempfile.TemporaryDirectory(
                    prefix="indus-kp1979-v3-communicate-matrix-"
                ) as raw:
                    invoker = _new_invoker(Path(raw))
                    with (
                        patch.object(sandbox.subprocess, "Popen", return_value=process),
                        patch.object(invoker, "_kill_unit", return_value=True) as kill_unit,
                        patch.object(sandbox.os, "killpg") as killpg,
                        patch.object(
                            sandbox,
                            "_read_bounded_file",
                            wraps=sandbox._read_bounded_file,
                        ) as read_bounded,
                    ):
                        if isinstance(failure, Exception):
                            result = invoker(_request())
                            self.assertTrue(result.process_started)
                            if isinstance(failure, subprocess.TimeoutExpired):
                                self.assertEqual("timeout", result.failure_code)
                                self.assertTrue(result.timed_out)
                                self.assertEqual(3, read_bounded.call_count)
                            else:
                                self.assertEqual("setup_failed", result.failure_code)
                                self.assertFalse(result.timed_out)
                                self.assertEqual(1, read_bounded.call_count)
                        else:
                            with self.assertRaises(type(failure)) as raised:
                                invoker(_request())
                            self.assertIs(failure, raised.exception)
                            self.assertEqual(1, read_bounded.call_count)
                    self.assertEqual(1, kill_unit.call_count)
                    killpg.assert_called_once_with(process.pid, signal.SIGKILL)
                self.assertEqual(
                    [
                        sandbox.PARENT_WALL_TIMEOUT_SECONDS,
                        sandbox.UNIT_KILL_TIMEOUT_SECONDS,
                    ],
                    process.communicate_timeouts,
                )
                self.assertEqual([sandbox.UNIT_KILL_TIMEOUT_SECONDS], process.wait_timeouts)
                self.assertEqual(-9, process.returncode)
                self.assertEqual(1, invoker.started_process_count)
                self.assertEqual(0, invoker.verified_invocation_count)

    def test_cleanup_stage_failure_matrix_continues_all_stages(self) -> None:
        stages = ("unit", "killpg", "communicate", "wait")
        for stage in stages:
            failures: list[tuple[str, BaseException]] = [
                *_ordinary_failures(),
                *_interrupt_failures(),
            ]
            for label, failure in failures:
                with self.subTest(stage=stage, failure=label):
                    communicate = [failure] if stage == "communicate" else [None]
                    wait = [failure, -9] if stage == "wait" else [-9]
                    process = _ControlledProcess(
                        communicate=communicate,
                        wait=wait,
                        returncode=-9,
                    )
                    with tempfile.TemporaryDirectory(
                        prefix="indus-kp1979-v3-cleanup-matrix-"
                    ) as raw:
                        invoker = _new_invoker(Path(raw))
                        unit_effect: list[BaseException | bool] = (
                            [failure, True] if stage == "unit" else [True]
                        )
                        killpg_effect = failure if stage == "killpg" else None
                        with (
                            patch.object(
                                invoker,
                                "_kill_unit",
                                side_effect=unit_effect,
                            ) as kill_unit,
                            patch.object(
                                sandbox.os,
                                "killpg",
                                side_effect=killpg_effect,
                            ) as killpg,
                        ):
                            reaped, unit_killed, cleanup_interrupt = (
                                invoker._cleanup_started_process(
                                    cast(subprocess.Popen[bytes], process),
                                    "indus-kp1979-v3-" + ("0" * 32),
                                )
                            )
                    self.assertTrue(reaped)
                    self.assertTrue(unit_killed)
                    expected_unit_calls = 2 if stage == "unit" else 1
                    self.assertEqual(expected_unit_calls, kill_unit.call_count)
                    self.assertEqual(1, killpg.call_count)
                    self.assertEqual(
                        [sandbox.UNIT_KILL_TIMEOUT_SECONDS],
                        process.communicate_timeouts,
                    )
                    expected_wait_calls = 2 if stage == "wait" else 1
                    self.assertEqual(expected_wait_calls, len(process.wait_timeouts))
                    if isinstance(failure, Exception):
                        self.assertIsNone(cleanup_interrupt)
                    else:
                        self.assertIs(failure, cleanup_interrupt)

    def test_cleanup_stage_order_is_unit_killpg_retry_communicate_wait(self) -> None:
        events: list[str] = []

        class OrderedProcess(_ControlledProcess):
            def communicate(
                self,
                input: bytes | None = None,
                timeout: float | None = None,
            ) -> tuple[None, None]:
                events.append("communicate")
                self._returncode = -9
                return super().communicate(input=input, timeout=timeout)

            def wait(self, timeout: float | None = None) -> int:
                events.append("wait")
                return super().wait(timeout=timeout)

        process = OrderedProcess(wait=[-9])
        unit_results = iter((False, True))

        def ordered_unit_kill(unit_name: str) -> bool:
            del unit_name
            result = next(unit_results)
            events.append("unit-false" if not result else "unit-true")
            return result

        def ordered_killpg(pid: int, selected_signal: int) -> None:
            if pid != process.pid or selected_signal != signal.SIGKILL:
                raise AssertionError("unexpected client process group")
            events.append("killpg")

        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-cleanup-order-") as raw:
            invoker = _new_invoker(Path(raw))
            with (
                patch.object(invoker, "_kill_unit", new=ordered_unit_kill),
                patch.object(sandbox.os, "killpg", new=ordered_killpg),
            ):
                reaped, unit_killed, cleanup_interrupt = invoker._cleanup_started_process(
                    cast(subprocess.Popen[bytes], process),
                    "indus-kp1979-v3-" + ("0" * 32),
                )
        self.assertTrue(reaped)
        self.assertTrue(unit_killed)
        self.assertIsNone(cleanup_interrupt)
        self.assertEqual(
            ["unit-false", "killpg", "unit-true", "communicate", "wait"],
            events,
        )

    def test_cleanup_retains_first_interrupt_and_bounds_hostile_wait_retries(self) -> None:
        first = KeyboardInterrupt("first cleanup interrupt")
        later_killpg = SystemExit("later killpg interrupt")
        later_communicate = GeneratorExit("later communicate interrupt")
        later_wait = SystemExit("later wait interrupt")
        process = _ControlledProcess(
            communicate=[later_communicate],
            wait=[later_wait, RuntimeError("second wait failure")],
            returncode=None,
        )
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-first-interrupt-") as raw:
            invoker = _new_invoker(Path(raw))
            with (
                patch.object(invoker, "_kill_unit", side_effect=[first, True]) as kill_unit,
                patch.object(sandbox.os, "killpg", side_effect=later_killpg) as killpg,
            ):
                reaped, unit_killed, cleanup_interrupt = invoker._cleanup_started_process(
                    cast(subprocess.Popen[bytes], process),
                    "indus-kp1979-v3-" + ("0" * 32),
                )
        self.assertFalse(reaped)
        self.assertTrue(unit_killed)
        self.assertIs(first, cleanup_interrupt)
        self.assertEqual(2, kill_unit.call_count)
        self.assertEqual(1, killpg.call_count)
        self.assertEqual(1, len(process.communicate_timeouts))
        self.assertEqual(2, len(process.wait_timeouts))

    def test_ordinary_primary_reraises_each_cleanup_interrupt_exactly(self) -> None:
        for stage in ("unit", "killpg", "communicate", "wait"):
            for label, cleanup_interrupt in _interrupt_failures():
                with self.subTest(stage=stage, cleanup_interrupt=label):
                    primary = RuntimeError("ordinary main communicate primary")
                    communicate: list[BaseException | int | None] = [primary]
                    wait: list[BaseException | int | None] = [-9]
                    if stage == "communicate":
                        communicate.append(cleanup_interrupt)
                    else:
                        communicate.append(None if stage == "wait" else -9)
                    if stage == "wait":
                        wait = [cleanup_interrupt, -9]
                    process = _ControlledProcess(communicate=communicate, wait=wait)
                    unit_effect: list[BaseException | bool] = (
                        [cleanup_interrupt, True] if stage == "unit" else [True]
                    )
                    killpg_effect = cleanup_interrupt if stage == "killpg" else None
                    with tempfile.TemporaryDirectory(
                        prefix="indus-kp1979-v3-primary-cleanup-cross-"
                    ) as raw:
                        invoker = _new_invoker(Path(raw))
                        with (
                            patch.object(sandbox.subprocess, "Popen", return_value=process),
                            patch.object(
                                invoker,
                                "_kill_unit",
                                side_effect=unit_effect,
                            ) as kill_unit,
                            patch.object(
                                sandbox.os,
                                "killpg",
                                side_effect=killpg_effect,
                            ) as killpg,
                            patch.object(
                                sandbox,
                                "_read_bounded_file",
                                wraps=sandbox._read_bounded_file,
                            ) as read_bounded,
                            self.assertRaises(type(cleanup_interrupt)) as raised,
                        ):
                            invoker(_request())
                    self.assertIs(cleanup_interrupt, raised.exception)
                    self.assertEqual(2 if stage == "unit" else 1, kill_unit.call_count)
                    self.assertEqual(1, killpg.call_count)
                    self.assertEqual(1, read_bounded.call_count)
                    self.assertEqual(1, invoker.started_process_count)
                    self.assertEqual(0, invoker.verified_invocation_count)

    def test_main_primary_interrupt_wins_over_different_cleanup_interrupt(self) -> None:
        primaries = _interrupt_failures()
        cleanups = _interrupt_failures()
        cleanups = cleanups[1:] + cleanups[:1]
        for (primary_label, primary), (cleanup_label, cleanup) in zip(
            primaries,
            cleanups,
            strict=True,
        ):
            with self.subTest(primary=primary_label, cleanup=cleanup_label):
                process = _ControlledProcess(
                    communicate=[primary, cleanup],
                    wait=[-9],
                    returncode=-9,
                )
                with tempfile.TemporaryDirectory(
                    prefix="indus-kp1979-v3-main-primary-precedence-"
                ) as raw:
                    invoker = _new_invoker(Path(raw))
                    with (
                        patch.object(sandbox.subprocess, "Popen", return_value=process),
                        patch.object(invoker, "_kill_unit", return_value=True) as kill_unit,
                        patch.object(sandbox.os, "killpg") as killpg,
                        patch.object(
                            sandbox,
                            "_read_bounded_file",
                            wraps=sandbox._read_bounded_file,
                        ) as read_bounded,
                        self.assertRaises(type(primary)) as raised,
                    ):
                        invoker(_request())
                self.assertIs(primary, raised.exception)
                self.assertEqual(1, kill_unit.call_count)
                self.assertEqual(1, killpg.call_count)
                self.assertEqual(1, read_bounded.call_count)
                self.assertEqual(1, invoker.started_process_count)

    def test_normal_communicate_without_status_and_status_failure_matrix_cleanup(
        self,
    ) -> None:
        cases: list[tuple[str, BaseException | None]] = [
            ("none", None),
            *[
                (f"property_{label}", failure)
                for label, failure in [*_ordinary_failures(), *_interrupt_failures()]
            ],
        ]
        for label, failure in cases:
            with self.subTest(case=label):
                process = _ControlledProcess(
                    communicate=[None, -9],
                    wait=[-9],
                    returncode_events=[] if failure is None else [failure],
                )
                with tempfile.TemporaryDirectory(
                    prefix="indus-kp1979-v3-main-status-failure-"
                ) as raw:
                    invoker = _new_invoker(Path(raw))
                    with (
                        patch.object(sandbox.subprocess, "Popen", return_value=process),
                        patch.object(invoker, "_kill_unit", return_value=True) as kill_unit,
                        patch.object(sandbox.os, "killpg") as killpg,
                        patch.object(
                            sandbox,
                            "_read_bounded_file",
                            wraps=sandbox._read_bounded_file,
                        ) as read_bounded,
                    ):
                        if failure is None or isinstance(failure, Exception):
                            result = invoker(_request())
                            self.assertEqual("setup_failed", result.failure_code)
                            self.assertTrue(result.process_started)
                        else:
                            with self.assertRaises(type(failure)) as raised:
                                invoker(_request())
                            self.assertIs(failure, raised.exception)
                self.assertEqual(1, kill_unit.call_count)
                self.assertEqual(1, killpg.call_count)
                self.assertEqual(1, read_bounded.call_count)
                self.assertEqual(1, invoker.started_process_count)
                self.assertEqual(0, invoker.verified_invocation_count)

    def test_negative_client_status_runs_cleanup_and_never_reads_early_outputs(self) -> None:
        process = _ControlledProcess(communicate=[-9, -9], wait=[-9])
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-negative-client-") as raw:
            invoker = _new_invoker(Path(raw))
            with (
                patch.object(sandbox.subprocess, "Popen", return_value=process),
                patch.object(invoker, "_kill_unit", return_value=True) as kill_unit,
                patch.object(sandbox.os, "killpg") as killpg,
                patch.object(
                    sandbox,
                    "_read_bounded_file",
                    wraps=sandbox._read_bounded_file,
                ) as read_bounded,
                patch.object(
                    sandbox,
                    "_read_handshake_file",
                    return_value=b'{"valid":"early"}\n',
                ) as read_handshake,
                patch.object(sandbox, "_parse_verified_handshake", return_value=4) as parse,
            ):
                result = invoker(_request())
        self.assertEqual("setup_failed", result.failure_code)
        self.assertTrue(result.process_started)
        self.assertEqual(1, kill_unit.call_count)
        self.assertEqual(1, killpg.call_count)
        self.assertEqual(1, read_bounded.call_count)
        read_handshake.assert_not_called()
        parse.assert_not_called()
        self.assertEqual(1, invoker.started_process_count)
        self.assertEqual(0, invoker.verified_invocation_count)

    def test_positive_nonzero_client_status_keeps_worker_failure_path(self) -> None:
        process = _ControlledProcess(communicate=[7])
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-positive-client-") as raw:
            invoker = _new_invoker(Path(raw))

            def bounded_content(path: Path, maximum_bytes: int) -> bytes:
                del maximum_bytes
                if path.name == "worker.pyz":
                    return invoker._artifact.content
                return b""

            with (
                patch.object(sandbox.subprocess, "Popen", return_value=process),
                patch.object(sandbox, "_read_bounded_file", side_effect=bounded_content),
                patch.object(sandbox, "_read_handshake_file", return_value=b"synthetic\n"),
                patch.object(sandbox, "_parse_verified_handshake", return_value=4),
                patch.object(invoker, "_kill_unit") as kill_unit,
            ):
                result = invoker(_request())
        self.assertEqual("nonzero_exit", result.failure_code)
        self.assertTrue(result.process_started)
        self.assertTrue(result.handshake_verified)
        self.assertEqual(4, result.landlock_abi)
        kill_unit.assert_not_called()
        self.assertEqual(1, invoker.started_process_count)
        self.assertEqual(1, invoker.verified_invocation_count)

    def test_cleanup_returncode_failure_matrix_never_claims_reaped(self) -> None:
        failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for label, failure in failures:
            with self.subTest(failure=label):
                process = _ControlledProcess(
                    communicate=[-9],
                    wait=[-9],
                    returncode=-9,
                    returncode_events=[failure],
                )
                with tempfile.TemporaryDirectory(
                    prefix="indus-kp1979-v3-cleanup-returncode-"
                ) as raw:
                    invoker = _new_invoker(Path(raw))
                    with (
                        patch.object(invoker, "_kill_unit", return_value=True) as kill_unit,
                        patch.object(sandbox.os, "killpg") as killpg,
                    ):
                        reaped, unit_killed, cleanup_interrupt = invoker._cleanup_started_process(
                            cast(subprocess.Popen[bytes], process),
                            "indus-kp1979-v3-" + ("0" * 32),
                        )
                self.assertFalse(reaped)
                self.assertTrue(unit_killed)
                if isinstance(failure, Exception):
                    self.assertIsNone(cleanup_interrupt)
                else:
                    self.assertIs(failure, cleanup_interrupt)
                self.assertEqual(1, kill_unit.call_count)
                self.assertEqual(1, killpg.call_count)
                self.assertEqual(1, len(process.communicate_timeouts))
                self.assertEqual(1, len(process.wait_timeouts))

    def test_timeout_without_reap_never_reads_output_or_handshake(self) -> None:
        process = _ControlledProcess(
            communicate=[
                subprocess.TimeoutExpired(("sandbox",), 0.01),
                subprocess.TimeoutExpired(("sandbox-cleanup",), 0.01),
            ],
            wait=[
                subprocess.TimeoutExpired(("sandbox-wait-1",), 0.01),
                subprocess.TimeoutExpired(("sandbox-wait-2",), 0.01),
            ],
            returncode=None,
        )
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-unreaped-") as raw:
            invoker = _new_invoker(Path(raw))
            with (
                patch.object(sandbox.subprocess, "Popen", return_value=process),
                patch.object(invoker, "_kill_unit", return_value=False) as kill_unit,
                patch.object(sandbox.os, "killpg", side_effect=OSError("synthetic kill")),
                patch.object(
                    sandbox,
                    "_read_bounded_file",
                    wraps=sandbox._read_bounded_file,
                ) as read_bounded,
                patch.object(
                    sandbox,
                    "_read_handshake_file",
                    side_effect=AssertionError("unreaped handshake read"),
                ) as read_handshake,
            ):
                result = invoker(_request())
        self.assertEqual("setup_failed", result.failure_code)
        self.assertTrue(result.process_started)
        self.assertFalse(result.handshake_verified)
        self.assertEqual(2, kill_unit.call_count)
        self.assertEqual(1, read_bounded.call_count)
        read_handshake.assert_not_called()
        self.assertEqual(2, len(process.communicate_timeouts))
        self.assertEqual(2, len(process.wait_timeouts))
        self.assertIsNone(process.returncode)

    def test_timeout_with_reaped_client_but_no_confirmed_unit_kill_never_reads_output(
        self,
    ) -> None:
        process = _ControlledProcess(
            communicate=[
                subprocess.TimeoutExpired(("sandbox",), 0.01),
                -9,
            ],
            wait=[-9],
        )
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-unit-not-killed-") as raw:
            invoker = _new_invoker(Path(raw))
            with (
                patch.object(sandbox.subprocess, "Popen", return_value=process),
                patch.object(invoker, "_kill_unit", return_value=False) as kill_unit,
                patch.object(sandbox.os, "killpg") as killpg,
                patch.object(
                    sandbox,
                    "_read_bounded_file",
                    wraps=sandbox._read_bounded_file,
                ) as read_bounded,
                patch.object(
                    sandbox,
                    "_read_handshake_file",
                    side_effect=AssertionError("unconfirmed unit handshake read"),
                ) as read_handshake,
            ):
                result = invoker(_request())
        self.assertEqual("setup_failed", result.failure_code)
        self.assertTrue(result.process_started)
        self.assertEqual(2, kill_unit.call_count)
        self.assertEqual(1, killpg.call_count)
        self.assertEqual(1, read_bounded.call_count)
        read_handshake.assert_not_called()
        self.assertEqual(-9, process.returncode)

    def test_unit_kill_helper_failure_matrix_self_cleans_and_preserves_identity(self) -> None:
        failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for label, failure in failures:
            with self.subTest(failure=label):
                helper = _ControlledProcess(communicate=[failure, -9], wait=[-9])
                captured: dict[str, Any] = {}

                def fake_popen(
                    arguments: Sequence[str],
                    _captured: dict[str, Any] = captured,
                    _helper: _ControlledProcess = helper,
                    **kwargs: Any,
                ) -> _ControlledProcess:
                    _captured["arguments"] = tuple(arguments)
                    _captured.update(kwargs)
                    return _helper

                with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-helper-matrix-") as raw:
                    invoker = _new_invoker(Path(raw))
                    with (
                        patch.object(sandbox.subprocess, "Popen", new=fake_popen),
                        patch.object(sandbox.os, "killpg") as killpg,
                    ):
                        if isinstance(failure, Exception):
                            self.assertFalse(invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32)))
                        else:
                            with self.assertRaises(type(failure)) as raised:
                                invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32))
                            self.assertIs(failure, raised.exception)
                killpg.assert_called_once_with(helper.pid, signal.SIGKILL)
                self.assertEqual(
                    [
                        sandbox.UNIT_KILL_TIMEOUT_SECONDS,
                        sandbox.UNIT_KILL_TIMEOUT_SECONDS,
                    ],
                    helper.communicate_timeouts,
                )
                self.assertEqual([sandbox.UNIT_KILL_TIMEOUT_SECONDS], helper.wait_timeouts)
                self.assertIs(True, captured["start_new_session"])
                self.assertIs(True, captured["close_fds"])
                self.assertIs(False, captured["shell"])
                self.assertEqual(subprocess.DEVNULL, captured["stdin"])
                self.assertEqual(0, invoker.started_process_count)

    def test_unit_kill_helper_popen_matrix_does_not_touch_counters(self) -> None:
        failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for label, failure in failures:
            with self.subTest(failure=label):
                with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-helper-popen-") as raw:
                    invoker = _new_invoker(Path(raw))
                    with patch.object(sandbox.subprocess, "Popen", side_effect=failure):
                        if isinstance(failure, Exception):
                            self.assertFalse(invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32)))
                        else:
                            with self.assertRaises(type(failure)) as raised:
                                invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32))
                            self.assertIs(failure, raised.exception)
                self.assertEqual(0, invoker.started_process_count)
                self.assertEqual(0, invoker.verified_invocation_count)

    def test_unit_kill_helper_primary_and_cleanup_interrupt_precedence(self) -> None:
        ordinary_primary = RuntimeError("ordinary helper primary")
        first_cleanup = KeyboardInterrupt("first helper cleanup interrupt")
        later_communicate = SystemExit("later helper communicate interrupt")
        later_wait = GeneratorExit("later helper wait interrupt")
        helper = _ControlledProcess(
            communicate=[ordinary_primary, later_communicate],
            wait=[later_wait, -9],
        )
        killpg_calls = 0

        def interrupted_then_success(pid: int, selected_signal: int) -> None:
            nonlocal killpg_calls
            killpg_calls += 1
            if killpg_calls == 1:
                raise first_cleanup
            if pid != helper.pid or selected_signal != signal.SIGKILL:
                raise AssertionError("unexpected helper process group")

        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-helper-precedence-") as raw:
            invoker = _new_invoker(Path(raw))
            with (
                patch.object(sandbox.subprocess, "Popen", return_value=helper),
                patch.object(sandbox.os, "killpg", new=interrupted_then_success),
                self.assertRaises(KeyboardInterrupt) as raised,
            ):
                invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32))
        self.assertIs(first_cleanup, raised.exception)
        self.assertEqual(2, killpg_calls)
        self.assertEqual(2, len(helper.communicate_timeouts))
        self.assertEqual(2, len(helper.wait_timeouts))

        primary_interrupt = KeyboardInterrupt("helper primary interrupt")
        cleanup_interrupt = SystemExit("helper cleanup interrupt")
        helper = _ControlledProcess(
            communicate=[primary_interrupt, cleanup_interrupt],
            wait=[-9],
            returncode=-9,
        )
        with tempfile.TemporaryDirectory(
            prefix="indus-kp1979-v3-helper-primary-precedence-"
        ) as raw:
            invoker = _new_invoker(Path(raw))
            with (
                patch.object(sandbox.subprocess, "Popen", return_value=helper),
                patch.object(sandbox.os, "killpg", side_effect=cleanup_interrupt),
                self.assertRaises(KeyboardInterrupt) as raised,
            ):
                invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32))
        self.assertIs(primary_interrupt, raised.exception)
        self.assertEqual(2, len(helper.communicate_timeouts))
        self.assertEqual(1, len(helper.wait_timeouts))

    def test_unit_kill_helper_returncode_none_and_property_failure_matrix(self) -> None:
        for returncode, expected in ((0, True), (7, False)):
            with self.subTest(normal_returncode=returncode):
                helper = _ControlledProcess(communicate=[returncode])
                with tempfile.TemporaryDirectory(
                    prefix="indus-kp1979-v3-helper-normal-status-"
                ) as raw:
                    invoker = _new_invoker(Path(raw))
                    with (
                        patch.object(sandbox.subprocess, "Popen", return_value=helper),
                        patch.object(sandbox.os, "killpg") as killpg,
                    ):
                        self.assertIs(
                            expected,
                            invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32)),
                        )
                killpg.assert_not_called()
                self.assertEqual(1, len(helper.communicate_timeouts))
                self.assertEqual(0, len(helper.wait_timeouts))

        helper = _ControlledProcess(communicate=[None, -9], wait=[-9])
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-helper-no-status-") as raw:
            invoker = _new_invoker(Path(raw))
            with (
                patch.object(sandbox.subprocess, "Popen", return_value=helper),
                patch.object(sandbox.os, "killpg") as killpg,
            ):
                self.assertFalse(invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32)))
        self.assertEqual(1, killpg.call_count)
        self.assertEqual(2, len(helper.communicate_timeouts))
        self.assertEqual(1, len(helper.wait_timeouts))

        failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for label, failure in failures:
            with self.subTest(property_failure=label):
                helper = _ControlledProcess(
                    communicate=[None, -9],
                    wait=[-9],
                    returncode_events=[failure],
                )
                with tempfile.TemporaryDirectory(
                    prefix="indus-kp1979-v3-helper-status-matrix-"
                ) as raw:
                    invoker = _new_invoker(Path(raw))
                    with (
                        patch.object(sandbox.subprocess, "Popen", return_value=helper),
                        patch.object(sandbox.os, "killpg") as killpg,
                    ):
                        if isinstance(failure, Exception):
                            self.assertFalse(invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32)))
                        else:
                            with self.assertRaises(type(failure)) as raised:
                                invoker._kill_unit("indus-kp1979-v3-" + ("0" * 32))
                            self.assertIs(failure, raised.exception)
                self.assertEqual(1, killpg.call_count)
                self.assertEqual(2, len(helper.communicate_timeouts))
                self.assertEqual(1, len(helper.wait_timeouts))

    def test_post_start_output_failure_matrix_is_normalized_or_preserved(self) -> None:
        failures: list[tuple[str, BaseException]] = [
            *_ordinary_failures(),
            *_interrupt_failures(),
        ]
        for label, failure in failures:
            with self.subTest(failure=label):
                process = _ControlledProcess(communicate=[0])
                with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-output-failure-") as raw:
                    invoker = _new_invoker(Path(raw))

                    def bounded_content(
                        path: Path,
                        maximum_bytes: int,
                        _content: bytes = invoker._artifact.content,
                        _failure: BaseException = failure,
                    ) -> bytes:
                        del maximum_bytes
                        if path.name == "worker.pyz":
                            return _content
                        raise _failure

                    with (
                        patch.object(sandbox.subprocess, "Popen", return_value=process),
                        patch.object(sandbox, "_read_bounded_file", side_effect=bounded_content),
                        patch.object(invoker, "_kill_unit") as kill_unit,
                    ):
                        if isinstance(failure, Exception):
                            result = invoker(_request())
                            self.assertEqual("setup_failed", result.failure_code)
                            self.assertTrue(result.process_started)
                        else:
                            with self.assertRaises(type(failure)) as raised:
                                invoker(_request())
                            self.assertIs(failure, raised.exception)
                    kill_unit.assert_not_called()
                self.assertEqual(1, invoker.started_process_count)
                self.assertEqual(0, invoker.verified_invocation_count)

    def test_stable_oversize_output_returns_limit_plus_one_and_output_limit_result(
        self,
    ) -> None:
        process = _ControlledProcess(communicate=[0])
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-output-limit-") as raw:
            invoker = _new_invoker(Path(raw))
            oversized = b"x" * (sandbox.MAX_STDOUT_BYTES + 1)

            def bounded_content(path: Path, maximum_bytes: int) -> bytes:
                if path.name == "worker.pyz":
                    return invoker._artifact.content
                if path.name == "stdout.bin":
                    self.assertEqual(sandbox.MAX_STDOUT_BYTES, maximum_bytes)
                    return oversized
                self.assertEqual(sandbox.MAX_STDERR_BYTES, maximum_bytes)
                return b""

            with (
                patch.object(sandbox.subprocess, "Popen", return_value=process),
                patch.object(sandbox, "_read_bounded_file", side_effect=bounded_content),
                patch.object(
                    sandbox,
                    "_read_handshake_file",
                    side_effect=AssertionError("output-limit handshake read"),
                ) as read_handshake,
            ):
                result = invoker(_request())
        self.assertEqual("output_limit", result.failure_code)
        self.assertTrue(result.process_started)
        self.assertEqual(sandbox.MAX_STDOUT_BYTES + 1, result.captured_stdout_bytes)
        self.assertEqual(0, result.captured_stderr_bytes)
        self.assertFalse(result.handshake_verified)
        read_handshake.assert_not_called()

    def test_verified_counter_is_exact_when_post_handshake_status_access_fails(self) -> None:
        status_error = RuntimeError("synthetic post-handshake status failure")
        process = _ControlledProcess(
            communicate=[None],
            returncode=0,
            returncode_events=[0, status_error],
        )
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-verified-counter-") as raw:
            invoker = _new_invoker(Path(raw))

            def bounded_content(path: Path, maximum_bytes: int) -> bytes:
                del maximum_bytes
                if path.name == "worker.pyz":
                    return invoker._artifact.content
                return b""

            with (
                patch.object(sandbox.subprocess, "Popen", return_value=process),
                patch.object(sandbox, "_read_bounded_file", side_effect=bounded_content),
                patch.object(sandbox, "_read_handshake_file", return_value=b"synthetic\n"),
                patch.object(sandbox, "_parse_verified_handshake", return_value=4),
            ):
                result = invoker(_request())
        self.assertEqual("setup_failed", result.failure_code)
        self.assertTrue(result.process_started)
        self.assertEqual(1, invoker.started_process_count)
        self.assertEqual(1, invoker.verified_invocation_count)

    def test_safe_real_sleep_group_is_killed_and_reaped_after_one_interrupt(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        real_killpg = os.killpg
        first_interrupt = KeyboardInterrupt("synthetic first killpg interrupt")
        killpg_calls = 0

        def interrupted_then_real_kill(pid: int, selected_signal: int) -> None:
            nonlocal killpg_calls
            killpg_calls += 1
            if killpg_calls == 1:
                raise first_interrupt
            real_killpg(pid, selected_signal)

        try:
            with patch.object(sandbox.os, "killpg", new=interrupted_then_real_kill):
                reaped, cleanup_interrupt = sandbox.SandboxedWorkerInvoker._cleanup_process_group(
                    process
                )
            self.assertTrue(reaped)
            self.assertIs(first_interrupt, cleanup_interrupt)
            self.assertEqual(2, killpg_calls)
            self.assertIsNotNone(process.returncode)
        finally:
            if process.poll() is None:
                real_killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)

    def test_mock_process_receives_only_request_and_closed_subprocess_options(self) -> None:
        captured: dict[str, Any] = {}

        class FakeProcess:
            returncode = 0
            pid = 12345

            def __init__(
                self,
                arguments: Sequence[str],
                keyword_arguments: Mapping[str, Any],
            ) -> None:
                captured["arguments"] = tuple(arguments)
                captured.update(keyword_arguments)

            def communicate(
                self,
                input: bytes | None = None,
                timeout: float | None = None,
            ) -> tuple[None, None]:
                captured["input"] = input
                captured["timeout"] = timeout
                arguments = cast(tuple[str, ...], captured["arguments"])
                standard_input = next(
                    item.removeprefix("--property=StandardInput=file:")
                    for item in arguments
                    if item.startswith("--property=StandardInput=file:")
                )
                standard_output = next(
                    item.removeprefix("--property=StandardOutput=file:")
                    for item in arguments
                    if item.startswith("--property=StandardOutput=file:")
                )
                captured["request_file"] = Path(standard_input).read_bytes()
                nonce = arguments[-5]
                digest = arguments[-6]
                handshake_path = Path(arguments[-1])
                captured["handshake_mode"] = stat.S_IMODE(handshake_path.stat().st_mode)
                captured["handshake_links"] = handshake_path.stat().st_nlink
                handshake = {
                    "artifact_sha256": digest,
                    "landlock_abi": 4,
                    "nonce": nonce,
                    "probes": {key: True for key in sandbox.PROBE_KEYS},
                    "schema": sandbox.SANDBOX_SCHEMA,
                }
                handshake_path.write_bytes(sandbox._canonical_json_line(handshake))
                Path(standard_output).write_bytes(b'{"ok":true}\n')
                return None, None

        def fake_popen(arguments: Sequence[str], **keyword_arguments: Any) -> FakeProcess:
            return FakeProcess(arguments, keyword_arguments)

        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-process-test-") as raw:
            artifact = Path(raw) / "worker.pyz"
            digest = _dummy_zipapp(artifact)
            invoker = sandbox.SandboxedWorkerInvoker(
                worker_artifact=artifact,
                expected_sha256=digest,
                python_executable=Path("/usr/bin/python3"),
            )
            with patch.object(sandbox.subprocess, "Popen", new=fake_popen):
                result = invoker(_request())

        self.assertEqual("completed", result.disposition)
        self.assertEqual(b'{"ok":true}\n', result.worker_stdout)
        self.assertIsNone(captured["input"])
        self.assertEqual(_request(), captured["request_file"])
        self.assertEqual(0o600, captured["handshake_mode"])
        self.assertEqual(1, captured["handshake_links"])
        self.assertEqual(sandbox.PARENT_WALL_TIMEOUT_SECONDS, captured["timeout"])
        self.assertEqual(subprocess.DEVNULL, captured["stdin"])
        self.assertEqual(subprocess.DEVNULL, captured["stdout"])
        self.assertEqual(subprocess.DEVNULL, captured["stderr"])
        self.assertIs(True, captured["close_fds"])
        self.assertIs(False, captured["shell"])
        self.assertIs(True, captured["start_new_session"])
        environment = cast(dict[str, str], captured["env"])
        self.assertNotIn("HOME", environment)
        self.assertEqual(
            {
                "DBUS_SESSION_BUS_ADDRESS",
                "LANG",
                "LC_ALL",
                "PATH",
                "XDG_RUNTIME_DIR",
            },
            set(environment),
        )
        self.assertEqual(1, invoker.started_process_count)
        self.assertEqual(1, invoker.verified_invocation_count)


@unittest.skipUnless(
    os.environ.get("INDUSBENCH_RUN_V3_SANDBOX_INTEGRATION") == "1",
    "set INDUSBENCH_RUN_V3_SANDBOX_INTEGRATION=1 for the VPS isolation proof",
)
class KP1979V3SandboxVPSIntegrationTests(unittest.TestCase):
    def test_preoccupied_fd3_is_normalized_then_closed_before_worker(self) -> None:
        if not sys.platform.startswith("linux"):
            self.fail("official integration proof requires Linux")
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-fd3-test-") as raw:
            base = Path(raw)
            artifact = base / "worker.pyz"
            wrapper = base / "fd3-env"
            digest = _fd_probe_zipapp(artifact)
            _write_fd3_wrapper(wrapper)
            invoker = sandbox.SandboxedWorkerInvoker(
                worker_artifact=artifact,
                expected_sha256=digest,
                env_executable=wrapper,
            )
            request = _request()
            result = invoker(request)

        self.assertEqual("completed", result.disposition, result.failure_code)
        self.assertTrue(result.handshake_verified)
        self.assertEqual(request, result.worker_stdout)
        self.assertEqual(1, invoker.verified_invocation_count)

    def test_close_range_failure_prevents_worker_and_invalidates_handshake(self) -> None:
        if not sys.platform.startswith("linux"):
            self.fail("official integration proof requires Linux")
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-close-range-test-") as raw:
            base = Path(raw)
            artifact = base / "worker.pyz"
            wrapper = base / "deny-close-range"
            digest = _worker_reached_zipapp(artifact)
            _write_close_range_denial_wrapper(wrapper)
            invoker = sandbox.SandboxedWorkerInvoker(
                worker_artifact=artifact,
                expected_sha256=digest,
                python_executable=wrapper,
            )
            result = invoker(_request())

        self.assertEqual("isolation_failure", result.disposition)
        self.assertEqual("invalid_handshake", result.failure_code)
        self.assertFalse(result.handshake_verified)
        self.assertEqual(0, result.captured_stdout_bytes)
        self.assertGreater(result.captured_stderr_bytes, 0)
        self.assertEqual(b"", result.worker_stdout)
        self.assertEqual(0, invoker.verified_invocation_count)

    def test_execve_preserves_seccomp_landlock_and_descriptor_boundary(self) -> None:
        if not sys.platform.startswith("linux"):
            self.fail("official integration proof requires Linux")
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-execve-test-") as raw:
            artifact = Path(raw) / "worker.pyz"
            digest = _execve_boundary_zipapp(artifact)
            invoker = sandbox.SandboxedWorkerInvoker(
                worker_artifact=artifact,
                expected_sha256=digest,
            )
            result = invoker(_request())

        self.assertEqual("completed", result.disposition, result.failure_code)
        self.assertTrue(result.handshake_verified)
        self.assertEqual(b'{"execve_boundary":true}\n', result.worker_stdout)
        self.assertEqual(1, invoker.verified_invocation_count)

    def test_real_systemd_and_landlock_handshake_then_runs_dummy_zipapp(self) -> None:
        if not sys.platform.startswith("linux"):
            self.fail("official integration proof requires Linux")
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-integration-test-") as raw:
            artifact = Path(raw) / "worker.pyz"
            digest = _dummy_zipapp(artifact)
            invoker = sandbox.SandboxedWorkerInvoker(
                worker_artifact=artifact,
                expected_sha256=digest,
            )
            request = _request()
            result = invoker(request)

        self.assertEqual("completed", result.disposition, result.failure_code)
        self.assertTrue(result.handshake_verified)
        self.assertIsNotNone(result.landlock_abi)
        self.assertGreaterEqual(cast(int, result.landlock_abi), sandbox.MINIMUM_LANDLOCK_ABI)
        self.assertEqual(request, result.worker_stdout)
        self.assertEqual(1, invoker.started_process_count)
        self.assertEqual(1, invoker.verified_invocation_count)
        self.assertEqual(0, result.captured_stderr_bytes)

    def test_real_unit_file_size_limit_stops_worker_output_growth(self) -> None:
        if not sys.platform.startswith("linux"):
            self.fail("official integration proof requires Linux")
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-output-limit-test-") as raw:
            artifact = Path(raw) / "worker.pyz"
            digest = _flood_zipapp(artifact)
            invoker = sandbox.SandboxedWorkerInvoker(
                worker_artifact=artifact,
                expected_sha256=digest,
            )
            result = invoker(_request())

        self.assertEqual("worker_failure", result.disposition)
        self.assertEqual("nonzero_exit", result.failure_code)
        self.assertTrue(result.handshake_verified)
        self.assertLessEqual(result.captured_stdout_bytes, sandbox.MAX_STDOUT_BYTES)
        self.assertLessEqual(result.captured_stderr_bytes, sandbox.MAX_STDERR_BYTES)
        self.assertEqual(b"", result.worker_stdout)

    def test_hostile_worker_cannot_replace_handshake_through_stdout_or_path(self) -> None:
        if not sys.platform.startswith("linux"):
            self.fail("official integration proof requires Linux")
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v3-handshake-owner-test-") as raw:
            artifact = Path(raw) / "worker.pyz"
            digest = _hostile_stdout_zipapp(artifact)
            invoker = sandbox.SandboxedWorkerInvoker(
                worker_artifact=artifact,
                expected_sha256=digest,
            )
            result = invoker(_request())

        self.assertEqual("completed", result.disposition, result.failure_code)
        self.assertTrue(result.handshake_verified)
        self.assertIsNotNone(result.landlock_abi)
        self.assertEqual(b'{"fake_handshake":true}\n', result.worker_stdout)
        self.assertEqual(len(result.worker_stdout), result.captured_stdout_bytes)
        self.assertEqual(1, invoker.verified_invocation_count)


if __name__ == "__main__":
    unittest.main()
