from __future__ import annotations

import errno
import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import indusbench.kp1979_v3_state as state_module
from indusbench.kp1979_v3_state import (
    MAX_RECORD_BYTES,
    STARTED_RECORD_NAME,
    TERMINAL_RECORD_NAME,
    C3OneShotState,
    KP1979V3StateError,
    ObservedStatus,
    StateErrorCode,
    TerminalStatus,
    execute_one_shot,
)

STARTED_BYTES = b'{"state":"started","version":1}\n'


class KP1979V3StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="kp1979-v3-state-test-")
        self.root = Path(self.temporary.name)
        self.state_directory = self.root / "state"
        self.state_directory.mkdir(mode=0o700)
        self.state_directory.chmod(0o700)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_raw(self, name: str, raw: bytes, *, mode: int = 0o600) -> Path:
        target = self.state_directory / name
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            mode,
        )
        try:
            os.fchmod(descriptor, mode)
            state_module._write_all(descriptor, raw)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return target

    def _assert_error(
        self,
        context: Any,
        code: StateErrorCode,
    ) -> KP1979V3StateError:
        error = cast(KP1979V3StateError, context.exception)
        self.assertEqual(code, error.code)
        self.assertEqual(code.value, str(error))
        self.assertNotIn(str(self.state_directory), str(error))
        self.assertTrue(error.__suppress_context__)
        return error

    def test_absent_state_is_minimal(self) -> None:
        with C3OneShotState(self.state_directory) as state:
            snapshot = state.inspect()
        self.assertEqual(ObservedStatus.ABSENT, snapshot.status)
        self.assertFalse(snapshot.terminal_record_present)
        self.assertEqual([], list(self.state_directory.iterdir()))

    def test_preflight_failure_is_unconsumed_and_detail_free(self) -> None:
        worker_called = False

        def preflight() -> object:
            raise RuntimeError("detail-that-must-not-escape")

        def worker(_: object) -> TerminalStatus:
            nonlocal worker_called
            worker_called = True
            return TerminalStatus.QUALIFIED

        with self.assertRaises(KP1979V3StateError) as raised:
            execute_one_shot(
                self.state_directory,
                preflight=preflight,
                worker=worker,
            )
        self._assert_error(raised, StateErrorCode.PREFLIGHT_FAILED)
        self.assertFalse(worker_called)
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.ABSENT, state.inspect().status)

    def test_preflight_base_exception_is_unconsumed_and_detail_free(self) -> None:
        def preflight() -> object:
            raise SystemExit("base-detail-that-must-not-escape")

        with self.assertRaises(KP1979V3StateError) as raised:
            execute_one_shot(
                self.state_directory,
                preflight=preflight,
                worker=lambda _: TerminalStatus.QUALIFIED,
            )
        self._assert_error(raised, StateErrorCode.PREFLIGHT_FAILED)
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.ABSENT, state.inspect().status)

    def test_started_is_file_and_directory_synced_before_worker(self) -> None:
        events: list[str] = []
        real_file_fsync = state_module._fsync_file
        real_directory_fsync = state_module._fsync_directory

        def file_fsync(descriptor: int) -> None:
            events.append("file")
            real_file_fsync(descriptor)

        def directory_fsync(descriptor: int) -> None:
            events.append("directory")
            real_directory_fsync(descriptor)

        def worker(prepared: object) -> TerminalStatus:
            self.assertIs(token, prepared)
            self.assertEqual(["file", "directory"], events[-2:])
            self.assertEqual(
                STARTED_BYTES,
                (self.state_directory / STARTED_RECORD_NAME).read_bytes(),
            )
            self.assertFalse((self.state_directory / TERMINAL_RECORD_NAME).exists())
            return TerminalStatus.QUALIFIED

        token = object()
        with (
            patch.object(state_module, "_fsync_file", side_effect=file_fsync),
            patch.object(state_module, "_fsync_directory", side_effect=directory_fsync),
        ):
            metadata = execute_one_shot(
                self.state_directory,
                preflight=lambda: token,
                worker=worker,
            )
        self.assertEqual(TerminalStatus.QUALIFIED, metadata.status)
        self.assertEqual(
            ["file", "directory", "file", "directory"],
            events[-4:],
        )

    def test_every_typed_terminal_status_round_trips(self) -> None:
        for status in TerminalStatus:
            with self.subTest(status=status):
                directory = self.root / status.value
                directory.mkdir(mode=0o700)
                directory.chmod(0o700)
                metadata = execute_one_shot(
                    directory,
                    preflight=lambda: None,
                    worker=lambda _, status=status: status,
                )
                self.assertEqual(status, metadata.status)
                with C3OneShotState(directory) as state:
                    snapshot = state.inspect()
                self.assertEqual(ObservedStatus(status.value), snapshot.status)
                self.assertTrue(snapshot.terminal_record_present)

    def test_records_are_canonical_ascii_and_content_free(self) -> None:
        opaque = object()
        execute_one_shot(
            self.state_directory,
            preflight=lambda: opaque,
            worker=lambda value: (
                TerminalStatus.NOT_QUALIFIED if value is opaque else TerminalStatus.EXECUTION_FAILED
            ),
        )
        started = (self.state_directory / STARTED_RECORD_NAME).read_bytes()
        terminal = (self.state_directory / TERMINAL_RECORD_NAME).read_bytes()
        self.assertEqual(STARTED_BYTES, started)
        self.assertEqual(
            b'{"state":"not_qualified","version":1}\n',
            terminal,
        )
        combined = started + terminal
        combined.decode("ascii")
        for forbidden in (
            b"experiment",
            b"commit",
            b"digest",
            b"result",
            b"detail",
            repr(opaque).encode("ascii"),
        ):
            self.assertNotIn(forbidden, combined)

    def test_worker_exception_is_terminal_execution_failed_and_hidden(self) -> None:
        def worker(_: None) -> TerminalStatus:
            raise RuntimeError("worker-detail-that-must-not-escape")

        with self.assertRaises(KP1979V3StateError) as raised:
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=worker,
            )
        self._assert_error(raised, StateErrorCode.WORKER_FAILED)
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.EXECUTION_FAILED, state.inspect().status)

    def test_invalid_worker_outcome_is_terminal_execution_failed(self) -> None:
        with self.assertRaises(KP1979V3StateError) as raised:
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=lambda _: cast(Any, "qualified"),
            )
        self._assert_error(raised, StateErrorCode.INVALID_WORKER_OUTCOME)
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.EXECUTION_FAILED, state.inspect().status)

    def test_base_exception_is_terminal_consumed_incomplete(self) -> None:
        def worker(_: None) -> TerminalStatus:
            raise KeyboardInterrupt

        with self.assertRaises(KP1979V3StateError) as raised:
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=worker,
            )
        self._assert_error(raised, StateErrorCode.WORKER_FAILED)
        with C3OneShotState(self.state_directory) as state:
            snapshot = state.inspect()
        self.assertEqual(ObservedStatus.CONSUMED_INCOMPLETE, snapshot.status)
        self.assertTrue(snapshot.terminal_record_present)

    def test_marker_only_crash_is_consumed_incomplete_and_never_retried(self) -> None:
        with C3OneShotState(self.state_directory) as state:
            state.mark_started()
        with C3OneShotState(self.state_directory) as state:
            snapshot = state.inspect()
        self.assertEqual(ObservedStatus.CONSUMED_INCOMPLETE, snapshot.status)
        self.assertFalse(snapshot.terminal_record_present)
        worker_called = False

        def worker(_: None) -> TerminalStatus:
            nonlocal worker_called
            worker_called = True
            return TerminalStatus.QUALIFIED

        with self.assertRaises(KP1979V3StateError) as raised:
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=worker,
            )
        self._assert_error(raised, StateErrorCode.ATTEMPT_CONSUMED)
        self.assertFalse(worker_called)

    def test_invalid_transitions_are_rejected(self) -> None:
        with C3OneShotState(self.state_directory) as state:
            with self.assertRaises(KP1979V3StateError) as before_start:
                state.finish(TerminalStatus.QUALIFIED)
            self._assert_error(before_start, StateErrorCode.INVALID_TRANSITION)
            state.mark_started()
            with self.assertRaises(KP1979V3StateError) as raw_string:
                state.finish(cast(Any, "qualified"))
            self._assert_error(raw_string, StateErrorCode.INVALID_TRANSITION)

    def test_finish_is_single_call_even_after_success(self) -> None:
        with C3OneShotState(self.state_directory) as state:
            state.mark_started()
            state.finish(TerminalStatus.QUALIFIED)
            with self.assertRaises(KP1979V3StateError) as second:
                state.finish(TerminalStatus.NOT_QUALIFIED)
        self._assert_error(second, StateErrorCode.INVALID_TRANSITION)

    def test_closed_handle_is_rejected(self) -> None:
        state = C3OneShotState(self.state_directory)
        state.close()
        with self.assertRaises(KP1979V3StateError) as raised:
            state.inspect()
        self._assert_error(raised, StateErrorCode.CLOSED)

    def test_no_retry_reset_delete_or_force_api_and_limit_is_documented(self) -> None:
        for name in ("retry", "reset", "delete", "force"):
            self.assertFalse(hasattr(C3OneShotState, name))
            self.assertNotIn(name, state_module.__all__)
        documentation = " ".join((state_module.__doc__ or "").split())
        for phrase in (
            "not independent custody",
            "owner",
            "can delete",
            "do not prove single execution",
        ):
            self.assertIn(phrase, documentation)

    def test_owner_can_delete_state_so_technical_single_use_is_not_claimed(self) -> None:
        execute_one_shot(
            self.state_directory,
            preflight=lambda: None,
            worker=lambda _: TerminalStatus.QUALIFIED,
        )
        (self.state_directory / TERMINAL_RECORD_NAME).unlink()
        (self.state_directory / STARTED_RECORD_NAME).unlink()
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.ABSENT, state.inspect().status)

    def test_directory_must_be_absolute_owner_only_and_same_uid(self) -> None:
        self.state_directory.chmod(0o750)
        with self.assertRaises(KP1979V3StateError) as unsafe:
            C3OneShotState(self.state_directory)
        self._assert_error(unsafe, StateErrorCode.UNSAFE_STATE_DIRECTORY)
        self.state_directory.chmod(0o700)
        with self.assertRaises(KP1979V3StateError) as relative:
            C3OneShotState(Path("state"))
        self._assert_error(relative, StateErrorCode.INVALID_STATE_DIRECTORY)
        with self.assertRaises(KP1979V3StateError) as traversal:
            C3OneShotState(self.root / "state" / ".." / "state")
        self._assert_error(traversal, StateErrorCode.INVALID_STATE_DIRECTORY)
        with (
            patch.object(state_module.os, "geteuid", return_value=os.geteuid() + 1),
            self.assertRaises(KP1979V3StateError) as wrong_uid,
        ):
            C3OneShotState(self.state_directory)
        self._assert_error(wrong_uid, StateErrorCode.UNSAFE_STATE_DIRECTORY)

    def test_nonsticky_world_writable_ancestor_is_rejected(self) -> None:
        self.root.chmod(0o777)
        try:
            with self.assertRaises(KP1979V3StateError) as raised:
                C3OneShotState(self.state_directory)
        finally:
            self.root.chmod(0o700)
        self._assert_error(raised, StateErrorCode.UNSAFE_STATE_DIRECTORY)

    def test_root_owned_sticky_boundary_is_accepted(self) -> None:
        temporary_root = Path(tempfile.gettempdir())
        metadata = temporary_root.stat()
        if metadata.st_uid != 0 or not metadata.st_mode & stat.S_ISVTX:
            self.skipTest("temporary root is not a root-owned sticky boundary")
        self.assertTrue(
            state_module._directory_component_is_safe(
                metadata,
                effective_uid=os.geteuid(),
                root=False,
                final=False,
            )
        )
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.ABSENT, state.inspect().status)

    def test_foreign_owner_ancestor_is_rejected(self) -> None:
        target_metadata = self.root.stat()
        target_identity = (target_metadata.st_dev, target_metadata.st_ino)
        real_fstat = state_module.os.fstat

        def foreign_fstat(descriptor: int) -> os.stat_result:
            metadata = real_fstat(descriptor)
            if (metadata.st_dev, metadata.st_ino) != target_identity:
                return metadata
            values = list(metadata)
            values[4] = os.geteuid() + 10_000
            return os.stat_result(values)

        with (
            patch.object(state_module.os, "fstat", side_effect=foreign_fstat),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            C3OneShotState(self.state_directory)
        self._assert_error(raised, StateErrorCode.UNSAFE_STATE_DIRECTORY)

    def test_acl_ancestor_and_final_directory_are_rejected(self) -> None:
        if state_module.sys.platform != "linux":
            self.skipTest("Linux listxattr ACL test")
        real_listxattr = vars(state_module.os)["listxattr"]
        for target in (self.root, self.state_directory):
            with self.subTest(target=target.name):
                target_metadata = target.stat()
                target_identity = (target_metadata.st_dev, target_metadata.st_ino)

                def listxattr(
                    descriptor: int,
                    target_identity: tuple[int, int] = target_identity,
                ) -> list[str]:
                    metadata = os.fstat(descriptor)
                    if (metadata.st_dev, metadata.st_ino) == target_identity:
                        return ["system.posix_acl_access"]
                    return cast(list[str], real_listxattr(descriptor))

                with (
                    patch.object(state_module.os, "listxattr", side_effect=listxattr),
                    self.assertRaises(KP1979V3StateError) as raised,
                ):
                    C3OneShotState(self.state_directory)
                self._assert_error(raised, StateErrorCode.UNSAFE_STATE_DIRECTORY)

    def test_non_posix_acl_xattr_names_are_rejected_case_insensitively(self) -> None:
        if state_module.sys.platform != "linux":
            self.skipTest("Linux listxattr ACL test")
        target_metadata = self.state_directory.stat()
        target_identity = (target_metadata.st_dev, target_metadata.st_ino)
        real_listxattr = vars(state_module.os)["listxattr"]
        for acl_name in (
            "system.nfs4_acl",
            b"security.NTACL",
            "system.richacl",
            b"trusted.SGI_ACL_FILE",
        ):
            with self.subTest(acl_name=acl_name):

                def listxattr(
                    descriptor: int,
                    acl_name: str | bytes = acl_name,
                ) -> list[str | bytes]:
                    metadata = os.fstat(descriptor)
                    if (metadata.st_dev, metadata.st_ino) == target_identity:
                        return [acl_name]
                    return cast(list[str | bytes], real_listxattr(descriptor))

                with (
                    patch.object(state_module.os, "listxattr", side_effect=listxattr),
                    self.assertRaises(KP1979V3StateError) as raised,
                ):
                    C3OneShotState(self.state_directory)
                self._assert_error(raised, StateErrorCode.UNSAFE_STATE_DIRECTORY)

    def test_unrelated_xattr_is_not_treated_as_an_acl(self) -> None:
        if state_module.sys.platform != "linux":
            self.skipTest("Linux listxattr ACL test")
        target_metadata = self.state_directory.stat()
        target_identity = (target_metadata.st_dev, target_metadata.st_ino)
        real_listxattr = vars(state_module.os)["listxattr"]

        def listxattr(descriptor: int) -> list[str]:
            metadata = os.fstat(descriptor)
            if (metadata.st_dev, metadata.st_ino) == target_identity:
                return ["user.comment"]
            return cast(list[str], real_listxattr(descriptor))

        with (
            patch.object(state_module.os, "listxattr", side_effect=listxattr),
            C3OneShotState(self.state_directory) as state,
        ):
            self.assertEqual(ObservedStatus.ABSENT, state.inspect().status)

    def test_unverifiable_acl_state_is_rejected(self) -> None:
        if state_module.sys.platform != "linux":
            self.skipTest("Linux listxattr ACL test")
        with (
            patch.object(
                state_module.os,
                "listxattr",
                side_effect=OSError(errno.ENOTSUP, "acl-detail-that-must-not-escape"),
            ),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            C3OneShotState(self.state_directory)
        self._assert_error(raised, StateErrorCode.UNSAFE_STATE_DIRECTORY)

    def test_all_ancestry_descriptors_remain_pinned_until_close(self) -> None:
        state = C3OneShotState(self.state_directory)
        descriptors = state._ancestry.descriptors
        self.assertEqual(len(self.state_directory.parts), len(descriptors))
        for descriptor in descriptors:
            self.assertTrue(stat.S_ISDIR(os.fstat(descriptor).st_mode))
        state.close()
        for descriptor in descriptors:
            with self.assertRaises(OSError) as raised:
                os.fstat(descriptor)
            self.assertEqual(errno.EBADF, raised.exception.errno)

    def test_hostile_pathlike_failure_is_detail_free(self) -> None:
        class HostilePath:
            def __fspath__(self) -> str:
                raise RuntimeError("path-detail-that-must-not-escape")

        with self.assertRaises(KP1979V3StateError) as raised:
            C3OneShotState(HostilePath())
        self._assert_error(raised, StateErrorCode.INVALID_STATE_DIRECTORY)

    def test_unencodable_surrogate_path_is_detail_free(self) -> None:
        invalid = f"{self.state_directory}\udcff"
        with self.assertRaises(KP1979V3StateError) as raised:
            C3OneShotState(invalid)
        self._assert_error(raised, StateErrorCode.INVALID_STATE_DIRECTORY)

    def test_freebsd_is_rejected_before_preflight_or_worker(self) -> None:
        preflight_called = False
        worker_called = False

        def preflight() -> None:
            nonlocal preflight_called
            preflight_called = True

        def worker(_: None) -> TerminalStatus:
            nonlocal worker_called
            worker_called = True
            return TerminalStatus.QUALIFIED

        with (
            patch.object(state_module.sys, "platform", "freebsd14"),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            execute_one_shot(
                self.state_directory,
                preflight=preflight,
                worker=worker,
            )
        self._assert_error(raised, StateErrorCode.UNSUPPORTED_PLATFORM)
        self.assertFalse(preflight_called)
        self.assertFalse(worker_called)
        self.assertEqual([], list(self.state_directory.iterdir()))

    def test_symlink_state_directory_and_ancestor_are_rejected(self) -> None:
        target = self.root / "target"
        target.mkdir(mode=0o700)
        target.chmod(0o700)
        symlink = self.root / "state-link"
        symlink.symlink_to(target, target_is_directory=True)
        with self.assertRaises(KP1979V3StateError) as direct:
            C3OneShotState(symlink)
        self._assert_error(direct, StateErrorCode.UNSAFE_STATE_DIRECTORY)
        ancestor_target = self.root / "ancestor-target"
        ancestor_target.mkdir(mode=0o700)
        ancestor_target.chmod(0o700)
        nested = ancestor_target / "nested"
        nested.mkdir(mode=0o700)
        nested.chmod(0o700)
        ancestor_link = self.root / "ancestor-link"
        ancestor_link.symlink_to(ancestor_target, target_is_directory=True)
        with self.assertRaises(KP1979V3StateError) as ancestor:
            C3OneShotState(ancestor_link / "nested")
        self._assert_error(ancestor, StateErrorCode.UNSAFE_STATE_DIRECTORY)

    def test_symlink_record_is_corrupt_and_never_followed(self) -> None:
        (self.state_directory / STARTED_RECORD_NAME).symlink_to("/dev/null")
        with (
            C3OneShotState(self.state_directory) as state,
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            state.inspect()
        self._assert_error(raised, StateErrorCode.STATE_CORRUPT)

    def test_hardlinked_started_or_terminal_record_is_corrupt(self) -> None:
        with C3OneShotState(self.state_directory) as state:
            state.mark_started()
        os.link(
            self.state_directory / STARTED_RECORD_NAME,
            self.root / "started-link",
        )
        with (
            C3OneShotState(self.state_directory) as state,
            self.assertRaises(KP1979V3StateError) as started,
        ):
            state.inspect()
        self._assert_error(started, StateErrorCode.STATE_CORRUPT)

        other = self.root / "other-state"
        other.mkdir(mode=0o700)
        other.chmod(0o700)
        execute_one_shot(
            other,
            preflight=lambda: None,
            worker=lambda _: TerminalStatus.QUALIFIED,
        )
        os.link(other / TERMINAL_RECORD_NAME, self.root / "terminal-link")
        with (
            C3OneShotState(other) as state,
            self.assertRaises(KP1979V3StateError) as terminal,
        ):
            state.inspect()
        self.assertEqual(StateErrorCode.STATE_CORRUPT, terminal.exception.code)

    def test_wrong_record_mode_is_corrupt(self) -> None:
        marker = self._write_raw(STARTED_RECORD_NAME, STARTED_BYTES)
        marker.chmod(0o640)
        with (
            C3OneShotState(self.state_directory) as state,
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            state.inspect()
        self._assert_error(raised, StateErrorCode.STATE_CORRUPT)

    def test_record_acl_is_corrupt(self) -> None:
        if state_module.sys.platform != "linux":
            self.skipTest("Linux listxattr ACL test")
        execute_one_shot(
            self.state_directory,
            preflight=lambda: None,
            worker=lambda _: TerminalStatus.QUALIFIED,
        )
        terminal_metadata = (self.state_directory / TERMINAL_RECORD_NAME).stat()
        terminal_identity = (terminal_metadata.st_dev, terminal_metadata.st_ino)
        real_listxattr = vars(state_module.os)["listxattr"]

        def listxattr(descriptor: int) -> list[str]:
            metadata = os.fstat(descriptor)
            if (metadata.st_dev, metadata.st_ino) == terminal_identity:
                return ["system.posix_acl_access"]
            return cast(list[str], real_listxattr(descriptor))

        with (
            patch.object(state_module.os, "listxattr", side_effect=listxattr),
            C3OneShotState(self.state_directory) as state,
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            state.inspect()
        self._assert_error(raised, StateErrorCode.STATE_CORRUPT)

    def test_duplicate_noncanonical_and_malformed_json_are_rejected(self) -> None:
        malformed_values = (
            b'{"state":"started","state":"started","version":1}\n',
            b'{ "state":"started","version":1 }\n',
            b'{"extra":false,"state":"started","version":1}\n',
            b'{"state":"started","version":true}\n',
            b'{"state":"st\\xc3\\xa4rted","version":1}\n',
            b"",
            b"x" * (MAX_RECORD_BYTES + 1),
        )
        for index, raw in enumerate(malformed_values):
            with self.subTest(index=index):
                directory = self.root / f"malformed-{index}"
                directory.mkdir(mode=0o700)
                directory.chmod(0o700)
                descriptor = os.open(
                    directory / STARTED_RECORD_NAME,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                    0o600,
                )
                try:
                    os.fchmod(descriptor, 0o600)
                    if raw:
                        state_module._write_all(descriptor, raw)
                finally:
                    os.close(descriptor)
                with (
                    C3OneShotState(directory) as state,
                    self.assertRaises(KP1979V3StateError) as raised,
                ):
                    state.inspect()
                self.assertEqual(StateErrorCode.STATE_CORRUPT, raised.exception.code)

    def test_terminal_without_started_or_duplicate_terminal_is_corrupt(self) -> None:
        self._write_raw(
            TERMINAL_RECORD_NAME,
            b'{"state":"qualified","version":1}\n',
        )
        with (
            C3OneShotState(self.state_directory) as state,
            self.assertRaises(KP1979V3StateError) as missing,
        ):
            state.inspect()
        self._assert_error(missing, StateErrorCode.STATE_CORRUPT)

        other = self.root / "duplicate-terminal"
        other.mkdir(mode=0o700)
        other.chmod(0o700)
        for name, raw in (
            (STARTED_RECORD_NAME, STARTED_BYTES),
            (
                TERMINAL_RECORD_NAME,
                b'{"state":"qualified","state":"qualified","version":1}\n',
            ),
        ):
            descriptor = os.open(
                other / name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o600,
            )
            try:
                os.fchmod(descriptor, 0o600)
                state_module._write_all(descriptor, raw)
            finally:
                os.close(descriptor)
        with (
            C3OneShotState(other) as state,
            self.assertRaises(KP1979V3StateError) as duplicate,
        ):
            state.inspect()
        self.assertEqual(StateErrorCode.STATE_CORRUPT, duplicate.exception.code)

    def test_real_rename_probe_checks_no_overwrite_then_success_and_cleans(self) -> None:
        calls: list[str] = []
        real_rename = state_module._rename_no_replace

        def observed_rename(parent: int, source: str, target: str) -> None:
            try:
                real_rename(parent, source, target)
            except FileExistsError:
                calls.append("no-overwrite")
                self.assertEqual(
                    state_module._PROBE_SOURCE_BYTES,
                    (self.state_directory / source).read_bytes(),
                )
                self.assertEqual(
                    state_module._PROBE_TARGET_BYTES,
                    (self.state_directory / target).read_bytes(),
                )
                raise
            calls.append("success")

        with (
            patch.object(state_module, "_rename_no_replace", side_effect=observed_rename),
            C3OneShotState(self.state_directory) as state,
        ):
            state.mark_started()
        self.assertEqual(["no-overwrite", "success"], calls)
        self.assertFalse((self.state_directory / state_module._PROBE_SOURCE_NAME).exists())
        self.assertFalse((self.state_directory / state_module._PROBE_TARGET_NAME).exists())

    def test_unsupported_rename_probe_blocks_worker_without_marker(self) -> None:
        worker_called = False

        def worker(_: None) -> TerminalStatus:
            nonlocal worker_called
            worker_called = True
            return TerminalStatus.QUALIFIED

        with (
            patch.object(
                state_module,
                "_rename_no_replace",
                side_effect=OSError(errno.ENOTSUP, "detail-that-must-not-escape"),
            ),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=worker,
            )
        self._assert_error(raised, StateErrorCode.RENAME_PROBE_FAILED)
        self.assertFalse(worker_called)
        self.assertFalse((self.state_directory / STARTED_RECORD_NAME).exists())
        self.assertEqual([], list(self.state_directory.iterdir()))

    def test_overwriting_rename_semantics_fail_probe_and_are_cleaned(self) -> None:
        def overwriting_rename(parent: int, source: str, target: str) -> None:
            os.rename(
                source,
                target,
                src_dir_fd=parent,
                dst_dir_fd=parent,
            )

        with (
            patch.object(
                state_module,
                "_rename_no_replace",
                side_effect=overwriting_rename,
            ),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=lambda _: TerminalStatus.QUALIFIED,
            )
        self._assert_error(raised, StateErrorCode.RENAME_PROBE_FAILED)
        self.assertFalse((self.state_directory / STARTED_RECORD_NAME).exists())
        self.assertEqual([], list(self.state_directory.iterdir()))

    def test_probe_fsync_failure_is_stable_and_cleans_known_inodes(self) -> None:
        with (
            patch.object(
                state_module,
                "_fsync_directory",
                side_effect=OSError("detail-that-must-not-escape"),
            ),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=lambda _: TerminalStatus.QUALIFIED,
            )
        self._assert_error(raised, StateErrorCode.RENAME_PROBE_FAILED)
        self.assertFalse((self.state_directory / STARTED_RECORD_NAME).exists())
        self.assertEqual([], list(self.state_directory.iterdir()))

    def test_probe_never_removes_unknown_reserved_name(self) -> None:
        reserved = self._write_raw(
            state_module._PROBE_SOURCE_NAME,
            b"not-this-probe\n",
        )
        with self.assertRaises(KP1979V3StateError) as raised:
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=lambda _: TerminalStatus.QUALIFIED,
            )
        self._assert_error(raised, StateErrorCode.RENAME_PROBE_FAILED)
        self.assertEqual(b"not-this-probe\n", reserved.read_bytes())
        self.assertFalse((self.state_directory / STARTED_RECORD_NAME).exists())

    def test_partial_started_write_is_left_as_consumed_corrupt_state(self) -> None:
        def partial(descriptor: int, payload: bytes) -> None:
            os.write(descriptor, payload[:5])
            raise OSError("partial-detail")

        with (
            C3OneShotState(self.state_directory) as state,
            patch.object(state, "_probe_rename_no_replace"),
            patch.object(state_module, "_write_all", side_effect=partial),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            state.mark_started()
        self._assert_error(raised, StateErrorCode.START_DURABILITY_UNKNOWN)
        self.assertTrue((self.state_directory / STARTED_RECORD_NAME).exists())
        with (
            C3OneShotState(self.state_directory) as state,
            self.assertRaises(KP1979V3StateError) as corrupt,
        ):
            state.inspect()
        self._assert_error(corrupt, StateErrorCode.STATE_CORRUPT)

    def test_started_file_fsync_failure_blocks_worker(self) -> None:
        worker_called = False

        def worker(_: None) -> TerminalStatus:
            nonlocal worker_called
            worker_called = True
            return TerminalStatus.QUALIFIED

        with (
            patch.object(C3OneShotState, "_probe_rename_no_replace"),
            patch.object(state_module, "_fsync_file", side_effect=OSError("hidden")),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=worker,
            )
        self._assert_error(raised, StateErrorCode.START_DURABILITY_UNKNOWN)
        self.assertFalse(worker_called)
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.CONSUMED_INCOMPLETE, state.inspect().status)

    def test_started_directory_fsync_failure_blocks_worker(self) -> None:
        worker_called = False

        def worker(_: None) -> TerminalStatus:
            nonlocal worker_called
            worker_called = True
            return TerminalStatus.QUALIFIED

        with (
            patch.object(C3OneShotState, "_probe_rename_no_replace"),
            patch.object(state_module, "_fsync_directory", side_effect=OSError("hidden")),
            self.assertRaises(KP1979V3StateError) as raised,
        ):
            execute_one_shot(
                self.state_directory,
                preflight=lambda: None,
                worker=worker,
            )
        self._assert_error(raised, StateErrorCode.START_DURABILITY_UNKNOWN)
        self.assertFalse(worker_called)
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.CONSUMED_INCOMPLETE, state.inspect().status)

    def test_partial_terminal_write_cleans_staging_and_stays_consumed(self) -> None:
        with C3OneShotState(self.state_directory) as state:
            state.mark_started()

            def partial(descriptor: int, payload: bytes) -> None:
                os.write(descriptor, payload[:7])
                raise OSError("partial-detail")

            with (
                patch.object(state_module, "_write_all", side_effect=partial),
                self.assertRaises(KP1979V3StateError) as raised,
            ):
                state.finish(TerminalStatus.QUALIFIED)
        self._assert_error(raised, StateErrorCode.TERMINAL_WRITE_FAILED)
        self.assertFalse((self.state_directory / TERMINAL_RECORD_NAME).exists())
        self.assertEqual(
            [STARTED_RECORD_NAME],
            [entry.name for entry in self.state_directory.iterdir()],
        )
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.CONSUMED_INCOMPLETE, state.inspect().status)

    def test_terminal_entropy_errors_are_stable_and_leave_marker_only(self) -> None:
        failures: tuple[object, ...] = (
            RuntimeError("entropy-detail-that-must-not-escape"),
            SystemExit("entropy-base-detail-that-must-not-escape"),
            "not-a-canonical-token",
        )
        for index, failure in enumerate(failures):
            with self.subTest(index=index):
                directory = self.root / f"entropy-{index}"
                directory.mkdir(mode=0o700)
                directory.chmod(0o700)
                with C3OneShotState(directory) as state:
                    state.mark_started()
                    if isinstance(failure, BaseException):
                        token_patch = patch.object(
                            state_module.secrets,
                            "token_hex",
                            side_effect=failure,
                        )
                    else:
                        token_patch = patch.object(
                            state_module.secrets,
                            "token_hex",
                            return_value=failure,
                        )
                    with (
                        token_patch,
                        self.assertRaises(KP1979V3StateError) as raised,
                    ):
                        state.finish(TerminalStatus.QUALIFIED)
                self.assertEqual(
                    StateErrorCode.TERMINAL_WRITE_FAILED,
                    raised.exception.code,
                )
                self.assertEqual(
                    StateErrorCode.TERMINAL_WRITE_FAILED.value,
                    str(raised.exception),
                )
                self.assertFalse((directory / TERMINAL_RECORD_NAME).exists())
                self.assertEqual(
                    [STARTED_RECORD_NAME],
                    [entry.name for entry in directory.iterdir()],
                )
                with C3OneShotState(directory) as state:
                    self.assertEqual(
                        ObservedStatus.CONSUMED_INCOMPLETE,
                        state.inspect().status,
                    )

    def test_post_rename_directory_fsync_failure_is_committed_but_unknown(self) -> None:
        with C3OneShotState(self.state_directory) as state:
            state.mark_started()
            with (
                patch.object(
                    state_module,
                    "_fsync_directory",
                    side_effect=OSError("post-rename-detail"),
                ),
                self.assertRaises(KP1979V3StateError) as raised,
            ):
                state.finish(TerminalStatus.QUALIFIED)
            with self.assertRaises(KP1979V3StateError) as second:
                state.finish(TerminalStatus.NOT_QUALIFIED)
        self._assert_error(raised, StateErrorCode.TERMINAL_DURABILITY_UNKNOWN)
        self._assert_error(second, StateErrorCode.INVALID_TRANSITION)
        self.assertEqual(
            b'{"state":"qualified","version":1}\n',
            (self.state_directory / TERMINAL_RECORD_NAME).read_bytes(),
        )
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.QUALIFIED, state.inspect().status)

    def test_marker_deletion_during_terminal_publication_fails_closed(self) -> None:
        with C3OneShotState(self.state_directory) as state:
            state.mark_started()

            def sync_then_remove_marker(descriptor: int) -> None:
                os.fsync(descriptor)
                os.unlink(STARTED_RECORD_NAME, dir_fd=descriptor)

            with (
                patch.object(
                    state_module,
                    "_fsync_directory",
                    side_effect=sync_then_remove_marker,
                ),
                self.assertRaises(KP1979V3StateError) as raised,
            ):
                state.finish(TerminalStatus.QUALIFIED)
        self._assert_error(raised, StateErrorCode.STATE_CORRUPT)
        self.assertTrue((self.state_directory / TERMINAL_RECORD_NAME).exists())
        with (
            C3OneShotState(self.state_directory) as state,
            self.assertRaises(KP1979V3StateError) as reopened,
        ):
            state.inspect()
        self._assert_error(reopened, StateErrorCode.STATE_CORRUPT)

    def test_post_rename_directory_identity_change_is_durability_unknown(self) -> None:
        moved = self.root / "moved-after-terminal"
        with C3OneShotState(self.state_directory) as state:
            state.mark_started()

            def sync_then_replace(descriptor: int) -> None:
                os.fsync(descriptor)
                self.state_directory.rename(moved)
                self.state_directory.mkdir(mode=0o700)
                self.state_directory.chmod(0o700)

            with (
                patch.object(
                    state_module,
                    "_fsync_directory",
                    side_effect=sync_then_replace,
                ),
                self.assertRaises(KP1979V3StateError) as raised,
            ):
                state.finish(TerminalStatus.QUALIFIED)
        self._assert_error(raised, StateErrorCode.TERMINAL_DURABILITY_UNKNOWN)
        self.assertEqual(
            b'{"state":"qualified","version":1}\n',
            (moved / TERMINAL_RECORD_NAME).read_bytes(),
        )
        with C3OneShotState(self.state_directory) as replacement:
            self.assertEqual(ObservedStatus.ABSENT, replacement.inspect().status)

    def test_terminal_destination_race_never_overwrites(self) -> None:
        racer_bytes = b'{"state":"not_qualified","version":1}\n'
        real_rename = state_module._rename_no_replace

        def insert_then_rename(parent: int, source: str, target: str) -> None:
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            try:
                os.fchmod(descriptor, 0o600)
                state_module._write_all(descriptor, racer_bytes)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            real_rename(parent, source, target)

        with C3OneShotState(self.state_directory) as state:
            state.mark_started()
            with (
                patch.object(state_module, "_rename_no_replace", side_effect=insert_then_rename),
                self.assertRaises(KP1979V3StateError) as raised,
            ):
                state.finish(TerminalStatus.QUALIFIED)
        self._assert_error(raised, StateErrorCode.ATTEMPT_CONSUMED)
        self.assertEqual(
            racer_bytes,
            (self.state_directory / TERMINAL_RECORD_NAME).read_bytes(),
        )
        with C3OneShotState(self.state_directory) as state:
            self.assertEqual(ObservedStatus.NOT_QUALIFIED, state.inspect().status)

    def test_state_directory_replacement_race_is_detected_before_start(self) -> None:
        state = C3OneShotState(self.state_directory)
        moved = self.root / "moved-state"
        self.state_directory.rename(moved)
        self.state_directory.mkdir(mode=0o700)
        self.state_directory.chmod(0o700)
        try:
            with self.assertRaises(KP1979V3StateError) as raised:
                state.mark_started()
        finally:
            state.close()
        self._assert_error(raised, StateErrorCode.STATE_DIRECTORY_CHANGED)
        self.assertFalse((moved / STARTED_RECORD_NAME).exists())
        self.assertFalse((self.state_directory / STARTED_RECORD_NAME).exists())

    def test_ancestor_namespace_swap_is_detected_with_all_fds_pinned(self) -> None:
        ancestor = self.root / "ancestor"
        nested = ancestor / "nested"
        nested_state = nested / "state"
        ancestor.mkdir(mode=0o700)
        nested.mkdir(mode=0o700)
        nested_state.mkdir(mode=0o700)
        for directory in (ancestor, nested, nested_state):
            directory.chmod(0o700)
        state = C3OneShotState(nested_state)
        moved = self.root / "moved-ancestor"
        ancestor.rename(moved)
        nested = ancestor / "nested"
        nested_state = nested / "state"
        ancestor.mkdir(mode=0o700)
        nested.mkdir(mode=0o700)
        nested_state.mkdir(mode=0o700)
        for directory in (ancestor, nested, nested_state):
            directory.chmod(0o700)
        try:
            with self.assertRaises(KP1979V3StateError) as raised:
                state.inspect()
        finally:
            state.close()
        self._assert_error(raised, StateErrorCode.STATE_DIRECTORY_CHANGED)

    def test_pre_create_identity_change_remains_state_directory_changed(self) -> None:
        moved = self.root / "moved-before-create"
        state = C3OneShotState(self.state_directory)
        real_verify = state._verify_pinned_directory
        verify_calls = 0

        def replace_on_pre_create_verify() -> None:
            nonlocal verify_calls
            verify_calls += 1
            if verify_calls == 3:
                self.state_directory.rename(moved)
                self.state_directory.mkdir(mode=0o700)
                self.state_directory.chmod(0o700)
            real_verify()

        try:
            with (
                patch.object(
                    state,
                    "_verify_pinned_directory",
                    side_effect=replace_on_pre_create_verify,
                ),
                patch.object(state, "_probe_rename_no_replace"),
                self.assertRaises(KP1979V3StateError) as raised,
            ):
                state.mark_started()
        finally:
            state.close()
        self._assert_error(raised, StateErrorCode.STATE_DIRECTORY_CHANGED)
        self.assertFalse((moved / STARTED_RECORD_NAME).exists())
        self.assertFalse((self.state_directory / STARTED_RECORD_NAME).exists())

    def test_post_sync_started_identity_change_is_durability_unknown(self) -> None:
        moved = self.root / "moved-after-start-sync"
        state = C3OneShotState(self.state_directory)
        real_verify = state._verify_pinned_directory
        verify_calls = 0

        def replace_on_post_sync_verify() -> None:
            nonlocal verify_calls
            verify_calls += 1
            if verify_calls == 4:
                self.state_directory.rename(moved)
                self.state_directory.mkdir(mode=0o700)
                self.state_directory.chmod(0o700)
            real_verify()

        try:
            with (
                patch.object(
                    state,
                    "_verify_pinned_directory",
                    side_effect=replace_on_post_sync_verify,
                ),
                patch.object(state, "_probe_rename_no_replace"),
                self.assertRaises(KP1979V3StateError) as raised,
            ):
                state.mark_started()
        finally:
            state.close()
        self._assert_error(raised, StateErrorCode.START_DURABILITY_UNKNOWN)
        self.assertEqual(
            STARTED_BYTES,
            (moved / STARTED_RECORD_NAME).read_bytes(),
        )
        self.assertFalse((self.state_directory / STARTED_RECORD_NAME).exists())

    def test_concurrent_started_creation_has_one_winner_and_no_overwrite(self) -> None:
        first = C3OneShotState(self.state_directory)
        second = C3OneShotState(self.state_directory)
        barrier = threading.Barrier(2)
        outcomes: list[StateErrorCode | None] = []
        lock = threading.Lock()

        def start(state: C3OneShotState) -> None:
            barrier.wait()
            try:
                state.mark_started()
            except KP1979V3StateError as error:
                outcome: StateErrorCode | None = error.code
            else:
                outcome = None
            with lock:
                outcomes.append(outcome)

        threads = [
            threading.Thread(target=start, args=(first,)),
            threading.Thread(target=start, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        first.close()
        second.close()
        self.assertEqual(1, outcomes.count(None))
        loser = next(outcome for outcome in outcomes if outcome is not None)
        self.assertIn(
            loser,
            {
                StateErrorCode.ATTEMPT_CONSUMED,
                StateErrorCode.RENAME_PROBE_FAILED,
                StateErrorCode.STATE_CORRUPT,
            },
        )
        self.assertEqual(
            STARTED_BYTES,
            (self.state_directory / STARTED_RECORD_NAME).read_bytes(),
        )

    def test_directory_and_record_opens_use_required_flags_and_dirfds(self) -> None:
        real_open = state_module.os.open
        calls: list[tuple[Any, int, int | None]] = []

        def recording_open(
            path: Any,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            calls.append((path, flags, dir_fd))
            return real_open(path, flags, mode, dir_fd=dir_fd)

        with (
            patch.object(state_module, "_require_supported_platform"),
            patch.object(state_module.os, "open", side_effect=recording_open),
            C3OneShotState(self.state_directory) as state,
        ):
            state.mark_started()
        directory_calls = [call for call in calls if call[1] & os.O_DIRECTORY]
        create_calls = [call for call in calls if call[1] & os.O_CREAT]
        self.assertTrue(directory_calls)
        self.assertTrue(create_calls)
        for _, flags, _ in directory_calls:
            self.assertTrue(flags & os.O_DIRECTORY)
            self.assertTrue(flags & os.O_NOFOLLOW)
            self.assertTrue(flags & os.O_CLOEXEC)
        for _, flags, dir_fd in create_calls:
            self.assertTrue(flags & os.O_CREAT)
            self.assertTrue(flags & os.O_EXCL)
            self.assertTrue(flags & os.O_NOFOLLOW)
            self.assertTrue(flags & os.O_CLOEXEC)
            self.assertIsNotNone(dir_fd)

    def test_published_records_are_owner_only_regular_single_links(self) -> None:
        execute_one_shot(
            self.state_directory,
            preflight=lambda: None,
            worker=lambda _: TerminalStatus.QUALIFIED,
        )
        for name in (STARTED_RECORD_NAME, TERMINAL_RECORD_NAME):
            metadata = (self.state_directory / name).lstat()
            self.assertTrue(stat.S_ISREG(metadata.st_mode))
            self.assertEqual(os.geteuid(), metadata.st_uid)
            self.assertEqual(1, metadata.st_nlink)
            self.assertEqual(0o600, stat.S_IMODE(metadata.st_mode))


if __name__ == "__main__":
    unittest.main()
