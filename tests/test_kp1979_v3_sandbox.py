from __future__ import annotations

import json
import os
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
