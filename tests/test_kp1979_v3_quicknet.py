from __future__ import annotations

import base64
import contextlib
import hashlib
import inspect
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest import mock

from indusbench import kp1979_v3_quicknet as quicknet

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
NODE_TEST = ROOT / "tests" / "node" / "kp1979_v3_quicknet.test.cjs"
HOST_NODE_TEST = ROOT / "tests" / "node" / "kp1979_v3_quicknet_host.test.cjs"
AVAILABLE_NODE_EXECUTABLE = shutil.which("node")
VENDOR_ROOT = ROOT / "src" / "indusbench" / "_vendor" / "noble"
NODE_MODULES = VENDOR_ROOT / "node_modules"
REQUIRE_PATTERN = re.compile(r"""require\(["']([^"']+)["']\)""")

EXPECTED_CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
EXPECTED_PUBLIC_KEY = (
    "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183"
    "c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4"
    "bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a"
)
EXPECTED_GROUP_HASH = "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e"
EXPECTED_SIGNATURE = (
    "b44679b9a59af2ec876b1a6b1ad52ea9b1615fc3982b19576350f93447cb112"
    "5e342b73a8dd2bacbe47e4b6b63ed5e39"
)
EXPECTED_RANDOMNESS = "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd"
EXPECTED_SRI_SHA512 = {
    "@noble/curves": (
        "81b286711518223037ff308235a5837224cc148d1d0a4be8bb74cbf199b2e4d7"
        "3bb09e3b6b48ed39e6684da33192ea91a3d71186339d6495de831604e4537fc7"
    ),
    "@noble/hashes": (
        "8c2b3d95d77b370ce98170c87fa3f7f8dac787dfec0fa0907711f28d023e87fe"
        "ab0cda3cf32a41c71cf8e540ee647cfdaf7b4dcfb37f5489d256855db57108e0"
    ),
}


def _trusted_node_host_available() -> bool:
    launchers = [
        (quicknet.NODE_EXECUTABLE, quicknet.NODE_LAUNCHER_SHA256),
        (quicknet.PRLIMIT_EXECUTABLE, quicknet.PRLIMIT_LAUNCHER_SHA256),
    ]
    for path, expected_digest in launchers:
        try:
            metadata = path.stat(follow_symlinks=False)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return False
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != 0
            or metadata.st_nlink != 1
            or digest != expected_digest
        ):
            return False
    return True


def _known_request() -> bytes:
    return quicknet.canonical_quicknet_request(
        1000,
        EXPECTED_SIGNATURE,
        EXPECTED_RANDOMNESS,
    )


class KP1979V3QuicknetContractTests(unittest.TestCase):
    def test_official_chain_identity_and_round_1000_vector_are_exact(self) -> None:
        self.assertEqual(EXPECTED_CHAIN_HASH, quicknet.CHAIN_HASH)
        self.assertEqual(EXPECTED_PUBLIC_KEY, quicknet.PUBLIC_KEY)
        self.assertEqual(EXPECTED_GROUP_HASH, quicknet.GROUP_HASH)
        self.assertEqual("bls-unchained-g1-rfc9380", quicknet.SCHEME_ID)
        self.assertEqual("quicknet", quicknet.BEACON_ID)
        self.assertEqual(
            "BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_",
            quicknet.DST,
        )
        self.assertEqual(1_692_803_367, quicknet.GENESIS_TIME)
        self.assertEqual(3, quicknet.PERIOD_SECONDS)
        self.assertEqual(EXPECTED_SIGNATURE, quicknet.ROUND_1000_SIGNATURE)
        self.assertEqual(EXPECTED_RANDOMNESS, quicknet.ROUND_1000_RANDOMNESS)
        self.assertEqual(
            EXPECTED_RANDOMNESS,
            hashlib.sha256(bytes.fromhex(EXPECTED_SIGNATURE)).hexdigest(),
        )
        self.assertEqual(
            "f652498d092acd949bad74e40683bf3824fb817980504a0c7e6722cfc5a9c0a3",
            hashlib.sha256((1000).to_bytes(8, "big")).hexdigest(),
        )

    def test_request_is_closed_canonical_ascii_and_lossless(self) -> None:
        raw = _known_request()
        self.assertEqual(1, raw.count(b"\n"))
        self.assertTrue(raw.endswith(b"\n"))
        self.assertTrue(raw.isascii())
        value = json.loads(raw)
        self.assertEqual(
            {
                "beacon_id",
                "chain_hash",
                "dst",
                "genesis_time",
                "group_hash",
                "period",
                "public_key",
                "randomness",
                "round",
                "scheme_id",
                "signature",
                "version",
            },
            set(value),
        )
        self.assertEqual("1000", value["round"])
        self.assertEqual(
            raw,
            (
                json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
            ).encode("ascii"),
        )

    def test_invalid_round_hex_and_randomness_fail_before_process_start(self) -> None:
        invalid_rounds: list[object] = [True, 0, -1, quicknet.MAX_ROUND + 1, 1.0, "1000"]
        for round_number in invalid_rounds:
            with (
                self.subTest(round_number=round_number),
                self.assertRaisesRegex(
                    quicknet.QuicknetVerificationError,
                    "^quicknet_verification_failed$",
                ),
            ):
                quicknet.canonical_quicknet_request(
                    cast(int, round_number),
                    EXPECTED_SIGNATURE,
                    EXPECTED_RANDOMNESS,
                )
        invalid_pairs = [
            (EXPECTED_SIGNATURE.upper(), EXPECTED_RANDOMNESS),
            (EXPECTED_SIGNATURE[:-1], EXPECTED_RANDOMNESS),
            (f"g{EXPECTED_SIGNATURE[1:]}", EXPECTED_RANDOMNESS),
            (EXPECTED_SIGNATURE, EXPECTED_RANDOMNESS.upper()),
            (EXPECTED_SIGNATURE, f"0{EXPECTED_RANDOMNESS[1:]}"),
        ]
        for signature, randomness in invalid_pairs:
            with (
                self.subTest(signature=signature[:4], randomness=randomness[:4]),
                self.assertRaises(quicknet.QuicknetVerificationError),
            ):
                quicknet.canonical_quicknet_request(1000, signature, randomness)

    def test_hex_inputs_reject_str_subclasses_before_special_method_dispatch(self) -> None:
        class HostileHex(str):
            def __len__(self) -> int:
                raise AssertionError("subclass __len__ must not run")

            def __iter__(self) -> Any:
                raise AssertionError("subclass __iter__ must not run")

        invalid_pairs = [
            (HostileHex(EXPECTED_SIGNATURE), EXPECTED_RANDOMNESS),
            (EXPECTED_SIGNATURE, HostileHex(EXPECTED_RANDOMNESS)),
        ]
        for signature, randomness in invalid_pairs:
            with (
                self.subTest(
                    signature_type=type(signature).__name__,
                    randomness_type=type(randomness).__name__,
                ),
                self.assertRaisesRegex(
                    quicknet.QuicknetVerificationError,
                    "^quicknet_verification_failed$",
                ),
            ):
                quicknet.canonical_quicknet_request(1000, signature, randomness)

    def test_prlimit_launcher_replaces_unsafe_preexec_hook(self) -> None:
        self.assertEqual("eol-host-qualified-only", quicknet.NODE_RUNTIME_SUPPORT_STATUS)
        self.assertEqual((22, 24), quicknet.CRYPTO_SEMANTIC_TEST_NODE_MAJORS)
        self.assertEqual(
            (
                "--as=1073741824:1073741824",
                "--core=0:0",
                "--cpu=5:5",
                "--fsize=4096:4096",
                "--nofile=32:32",
            ),
            quicknet._PRLIMIT_ARGUMENTS,
        )
        source = inspect.getsource(quicknet.verify_quicknet_beacon)
        self.assertIn("PRLIMIT_EXECUTABLE", source)
        self.assertNotIn("preexec_fn", source)
        self.assertNotIn("resource", quicknet.__dict__)

    def test_ci_pins_supported_node_and_requires_portable_bls_suite(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        setup_node = "uses: actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38 # v6.5.0"
        self.assertEqual(1, workflow.count(setup_node))
        self.assertEqual(1, workflow.count('node-version: "24.18.0"'))
        self.assertEqual(1, workflow.count("package-manager-cache: false"))
        version_assertion = 'test "$(node --version)" = "v24.18.0"'
        portable_command = "node --test tests/node/kp1979_v3_quicknet.test.cjs"
        self.assertEqual(1, workflow.count(version_assertion))
        self.assertEqual(1, workflow.count(portable_command))
        self.assertLess(workflow.index(setup_node), workflow.index(version_assertion))
        self.assertLess(workflow.index(version_assertion), workflow.index(portable_command))
        portable_suite = NODE_TEST.read_text(encoding="utf-8")
        self.assertNotIn("skip:", portable_suite)
        self.assertNotIn("kp1979_v3_quicknet_host.test.cjs", workflow)


class KP1979V3QuicknetInterruptionTests(unittest.TestCase):
    def _verify_with_process(self, process: Any) -> quicknet.VerifiedQuicknetBeacon:
        with (
            mock.patch.object(
                quicknet,
                "verify_vendored_noble",
                return_value=quicknet.VENDOR_MANIFEST_SHA256,
            ),
            mock.patch.object(quicknet, "_require_safe_file"),
            mock.patch.object(quicknet, "_verify_host_prerequisites"),
            mock.patch.object(quicknet.subprocess, "Popen", return_value=process),
        ):
            return quicknet.verify_quicknet_beacon(
                1000,
                EXPECTED_SIGNATURE,
                EXPECTED_RANDOMNESS,
            )

    def _assert_same_exception(self, expected: BaseException, process: Any) -> None:
        try:
            self._verify_with_process(process)
        except BaseException as caught:
            self.assertIs(expected, caught)
        else:
            self.fail("expected BaseException")

    def test_communicate_baseexceptions_kill_and_reap_before_exact_reraise(self) -> None:
        for interruption in (
            KeyboardInterrupt("keyboard-detail"),
            SystemExit("system-exit-detail"),
            GeneratorExit("generator-exit-detail"),
        ):
            process = mock.Mock()
            process.pid = 424_242
            process.communicate.side_effect = [interruption, (b"", b"")]
            process.wait.return_value = -signal.SIGKILL
            with (
                self.subTest(interruption=type(interruption).__name__),
                mock.patch.object(quicknet.os, "killpg") as killpg,
            ):
                self._assert_same_exception(interruption, process)
            self.assertEqual(
                [
                    mock.call(input=_known_request(), timeout=quicknet.WALL_TIMEOUT_SECONDS),
                    mock.call(timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS),
                ],
                process.communicate.call_args_list,
            )
            killpg.assert_called_once_with(process.pid, signal.SIGKILL)
            process.wait.assert_called_once_with(
                timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS
            )

    def test_cleanup_processlookup_and_cleanup_failures_cannot_replace_interrupt(self) -> None:
        scenarios = [
            (ProcessLookupError("already-gone"), None),
            (None, KeyboardInterrupt("cleanup-communicate")),
        ]
        for kill_failure, communicate_failure in scenarios:
            interruption = SystemExit("original")
            process = mock.Mock()
            process.pid = 434_343
            process.communicate.side_effect = [interruption, communicate_failure]
            process.wait.side_effect = GeneratorExit("cleanup-wait")
            kill_side_effect = kill_failure if kill_failure is not None else None
            with (
                self.subTest(
                    kill_failure=type(kill_failure).__name__ if kill_failure else None,
                    communicate_failure=(
                        type(communicate_failure).__name__ if communicate_failure else None
                    ),
                ),
                mock.patch.object(
                    quicknet.os,
                    "killpg",
                    side_effect=kill_side_effect,
                ) as killpg,
            ):
                self._assert_same_exception(interruption, process)
            killpg.assert_called_once_with(process.pid, signal.SIGKILL)
            self.assertEqual(2, process.wait.call_count)
            process.wait.assert_called_with(timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS)

    def test_already_exited_process_still_gets_bounded_best_effort_cleanup(self) -> None:
        interruption = KeyboardInterrupt("after-exit")
        process = mock.Mock()
        process.pid = 444_444
        process.returncode = 0
        process.communicate.side_effect = [interruption, (b"", b"")]
        process.wait.return_value = 0
        with mock.patch.object(
            quicknet.os,
            "killpg",
            side_effect=ProcessLookupError,
        ) as killpg:
            self._assert_same_exception(interruption, process)
        killpg.assert_called_once_with(process.pid, signal.SIGKILL)
        process.communicate.assert_called_with(timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS)
        process.wait.assert_called_once_with(timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS)

    def test_invalid_request_and_popen_interrupt_without_handle_trigger_no_cleanup(self) -> None:
        with mock.patch.object(quicknet.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(
                quicknet.QuicknetVerificationError,
                "^quicknet_verification_failed$",
            ):
                quicknet.verify_quicknet_beacon(
                    0,
                    EXPECTED_SIGNATURE,
                    EXPECTED_RANDOMNESS,
                )
            popen.assert_not_called()

        interruption = KeyboardInterrupt("popen-detail")
        with (
            mock.patch.object(
                quicknet,
                "verify_vendored_noble",
                return_value=quicknet.VENDOR_MANIFEST_SHA256,
            ),
            mock.patch.object(quicknet, "_require_safe_file"),
            mock.patch.object(quicknet, "_verify_host_prerequisites"),
            mock.patch.object(
                quicknet.subprocess,
                "Popen",
                side_effect=interruption,
            ) as popen,
            mock.patch.object(quicknet.os, "killpg") as killpg,
        ):
            try:
                quicknet.verify_quicknet_beacon(
                    1000,
                    EXPECTED_SIGNATURE,
                    EXPECTED_RANDOMNESS,
                )
            except BaseException as caught:
                self.assertIs(interruption, caught)
            else:
                self.fail("expected KeyboardInterrupt")
        killpg.assert_not_called()
        launch_kwargs = popen.call_args.kwargs
        self.assertTrue(launch_kwargs["start_new_session"])
        self.assertFalse(launch_kwargs["shell"])
        self.assertEqual(subprocess.PIPE, launch_kwargs["stdin"])

    def test_ordinary_communication_failures_remain_detail_free(self) -> None:
        for failure in (
            OSError("private-operating-detail"),
            subprocess.SubprocessError("private-subprocess-detail"),
            subprocess.TimeoutExpired("private-command", 10),
        ):
            process = mock.Mock()
            process.pid = 454_545
            process.returncode = -signal.SIGKILL
            process.communicate.side_effect = [failure, (b"", b"")]
            with (
                self.subTest(failure=type(failure).__name__),
                mock.patch.object(quicknet.os, "killpg") as killpg,
                self.assertRaisesRegex(
                    quicknet.QuicknetVerificationError,
                    "^quicknet_verification_failed$",
                ),
            ):
                self._verify_with_process(process)
            killpg.assert_called_once_with(process.pid, signal.SIGKILL)
            process.communicate.assert_called_with(
                timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS
            )
            process.wait.assert_called_once_with(
                timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS
            )

    def test_each_cleanup_interrupt_after_ordinary_failure_is_reaped_and_reraised(
        self,
    ) -> None:
        for failure in (
            OSError("initial-operating-detail"),
            subprocess.SubprocessError("initial-subprocess-detail"),
            subprocess.TimeoutExpired("initial-command", 10),
        ):
            for location in ("killpg", "communicate", "wait"):
                for interruption in (
                    KeyboardInterrupt(f"cleanup-{location}"),
                    SystemExit(f"cleanup-{location}"),
                    GeneratorExit(f"cleanup-{location}"),
                ):
                    with self.subTest(
                        failure=type(failure).__name__,
                        interruption=type(interruption).__name__,
                        location=location,
                    ):
                        process = mock.Mock()
                        process.pid = 464_646
                        process.communicate.side_effect = [
                            failure,
                            interruption if location == "communicate" else (b"", b""),
                        ]
                        process.wait.side_effect = (
                            [interruption, KeyboardInterrupt("later-wait")]
                            if location == "wait"
                            else None
                        )
                        process.wait.return_value = -signal.SIGKILL
                        kill_side_effect = (
                            [interruption, SystemExit("later-kill")]
                            if location == "killpg"
                            else None
                        )
                        with mock.patch.object(
                            quicknet.os,
                            "killpg",
                            side_effect=kill_side_effect,
                        ) as killpg:
                            self._assert_same_exception(interruption, process)
                        self.assertEqual(2 if location == "killpg" else 1, killpg.call_count)
                        self.assertEqual(
                            [
                                mock.call(
                                    input=_known_request(),
                                    timeout=quicknet.WALL_TIMEOUT_SECONDS,
                                ),
                                mock.call(timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS),
                            ],
                            process.communicate.call_args_list,
                        )
                        self.assertEqual(2 if location == "wait" else 1, process.wait.call_count)
                        process.wait.assert_called_with(
                            timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS
                        )

    def test_first_cleanup_interrupt_wins_while_every_cleanup_stage_is_attempted(
        self,
    ) -> None:
        first = KeyboardInterrupt("first-kill")
        process = mock.Mock()
        process.pid = 474_747
        process.communicate.side_effect = [
            OSError("initial"),
            GeneratorExit("later-communicate"),
        ]
        process.wait.side_effect = SystemExit("later-wait")
        with mock.patch.object(
            quicknet.os,
            "killpg",
            side_effect=[first, KeyboardInterrupt("later-kill")],
        ) as killpg:
            self._assert_same_exception(first, process)
        self.assertEqual(2, killpg.call_count)
        self.assertEqual(2, process.communicate.call_count)
        self.assertEqual(2, process.wait.call_count)
        process.wait.assert_called_with(timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS)

    def test_original_primary_interrupt_wins_over_every_cleanup_interrupt(self) -> None:
        original = GeneratorExit("original")
        process = mock.Mock()
        process.pid = 484_848
        process.communicate.side_effect = [
            original,
            SystemExit("cleanup-communicate"),
        ]
        process.wait.side_effect = KeyboardInterrupt("cleanup-wait")
        with mock.patch.object(
            quicknet.os,
            "killpg",
            side_effect=[
                KeyboardInterrupt("cleanup-first-kill"),
                GeneratorExit("cleanup-second-kill"),
            ],
        ) as killpg:
            self._assert_same_exception(original, process)
        self.assertEqual(2, killpg.call_count)
        self.assertEqual(2, process.communicate.call_count)
        self.assertEqual(2, process.wait.call_count)
        process.wait.assert_called_with(timeout=quicknet._INTERRUPT_CLEANUP_TIMEOUT_SECONDS)

    @unittest.skipUnless(hasattr(os, "killpg"), "process groups unavailable")
    def test_interrupted_first_kill_is_retried_and_real_process_is_reaped(self) -> None:
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", "-c", "import time; time.sleep(60)"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                shell=False,
                start_new_session=True,
            )
        except OSError as error:
            self.skipTest(f"local process launch unavailable: {type(error).__name__}")
        interruption = KeyboardInterrupt("first-real-kill")
        real_killpg = os.killpg
        kill_attempts = 0

        def interrupt_once_then_kill(process_group: int, sig: int) -> None:
            nonlocal kill_attempts
            kill_attempts += 1
            if kill_attempts == 1:
                raise interruption
            real_killpg(process_group, sig)

        try:
            with mock.patch.object(
                quicknet.os,
                "killpg",
                side_effect=interrupt_once_then_kill,
            ):
                try:
                    quicknet._kill_and_reap_process(
                        process,
                        reraise_cleanup_interrupt=True,
                    )
                except BaseException as caught:
                    self.assertIs(interruption, caught)
                else:
                    self.fail("expected KeyboardInterrupt")
            self.assertEqual(2, kill_attempts)
            self.assertIsNotNone(process.returncode)
        finally:
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


class KP1979V3QuicknetVendorTests(unittest.TestCase):
    def test_minimal_vendor_manifest_hashes_every_file(self) -> None:
        self.assertEqual(
            quicknet.VENDOR_MANIFEST_SHA256,
            quicknet.verify_vendored_noble(),
        )
        manifest_raw = (VENDOR_ROOT / "VENDOR_MANIFEST.json").read_bytes()
        self.assertEqual(
            quicknet.VENDOR_MANIFEST_SHA256,
            hashlib.sha256(manifest_raw).hexdigest(),
        )
        manifest = json.loads(manifest_raw)
        self.assertEqual(
            manifest_raw,
            (
                json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
                + "\n"
            ).encode("ascii"),
        )
        for package in manifest["packages"]:
            integrity_algorithm, encoded_digest = package["npm_integrity"].split("-", 1)
            self.assertEqual("sha512", integrity_algorithm)
            self.assertEqual(
                EXPECTED_SRI_SHA512[package["name"]],
                base64.b64decode(encoded_digest, validate=True).hex(),
            )
            package_root = NODE_MODULES / "@noble" / package["name"].removeprefix("@noble/")
            package_json = json.loads((package_root / "package.json").read_bytes())
            self.assertEqual(package["name"], package_json["name"])
            self.assertEqual(package["version"], package_json["version"])
            self.assertEqual("MIT", package_json["license"])
            license_text = (package_root / "LICENSE").read_text(encoding="utf-8")
            self.assertIn("MIT License", license_text)
            self.assertIn("Permission is hereby granted", license_text)
        curves_json = json.loads((NODE_MODULES / "@noble" / "curves" / "package.json").read_bytes())
        self.assertEqual({"@noble/hashes": "1.8.0"}, curves_json["dependencies"])

    def test_upstream_trailing_whitespace_exception_is_exact_and_unique(self) -> None:
        observed: list[tuple[str, int, str]] = []
        for source in sorted(path for path in NODE_MODULES.rglob("*") if path.is_file()):
            for line_number, raw_line in enumerate(source.read_bytes().splitlines(), start=1):
                if raw_line.rstrip(b" \t") != raw_line:
                    observed.append(
                        (
                            source.relative_to(NODE_MODULES).as_posix(),
                            line_number,
                            raw_line.decode("utf-8"),
                        )
                    )
        expected_content = "const hasHexBuiltin = /* @__PURE__ */ (() => "
        self.assertEqual(
            [("@noble/hashes/utils.js", 133, expected_content)],
            observed,
        )
        manifest = json.loads((VENDOR_ROOT / "VENDOR_MANIFEST.json").read_bytes())
        hashes_record = next(
            package for package in manifest["packages"] if package["name"] == "@noble/hashes"
        )
        self.assertEqual(
            [
                {
                    "content": expected_content,
                    "line": 133,
                    "path": "utils.js",
                    "reason": "exact npm 1.8.0 source byte",
                }
            ],
            hashes_record["upstream_whitespace_exceptions"],
        )

    def test_selected_commonjs_graph_is_complete_and_has_no_network_import(self) -> None:
        curves_root = NODE_MODULES / "@noble" / "curves"
        hashes_root = NODE_MODULES / "@noble" / "hashes"
        entry = curves_root / "bls12-381.js"
        visited: set[Path] = set()
        allowed_builtin = {"node:crypto"}

        def resolve(source: Path, specifier: str) -> Path | None:
            if specifier.startswith("."):
                candidate = (source.parent / specifier).resolve()
                if candidate.suffix != ".js":
                    candidate = candidate.with_suffix(".js")
                return candidate
            if specifier.startswith("@noble/hashes/"):
                subpath = specifier.removeprefix("@noble/hashes/")
                if subpath == "crypto":
                    return hashes_root / "cryptoNode.js"
                candidate = hashes_root / subpath
                if candidate.suffix != ".js":
                    candidate = candidate.with_suffix(".js")
                return candidate
            self.assertIn(specifier, allowed_builtin)
            return None

        def visit(source: Path) -> None:
            source = source.resolve()
            if source in visited:
                return
            self.assertTrue(source.is_file(), source)
            visited.add(source)
            text = source.read_text(encoding="utf-8")
            for specifier in REQUIRE_PATTERN.findall(text):
                self.assertNotIn(
                    specifier.removeprefix("node:"),
                    {"dgram", "dns", "http", "http2", "https", "net", "tls"},
                )
                target = resolve(source, specifier)
                if target is not None:
                    visit(target)

        visit(entry)
        selected_js = {
            path.resolve()
            for package_root in (curves_root, hashes_root)
            for path in package_root.rglob("*.js")
        }
        self.assertEqual(selected_js, visited)

    def test_manifest_source_tamper_and_extra_file_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-quicknet-vendor-test-") as raw:
            copied_root = Path(raw) / "noble"
            shutil.copytree(VENDOR_ROOT, copied_root)
            copied_manifest = copied_root / "VENDOR_MANIFEST.json"
            copied_modules = copied_root / "node_modules"
            target = copied_modules / "@noble" / "hashes" / "sha2.js"
            target.write_bytes(target.read_bytes() + b"\n")
            with (
                mock.patch.object(quicknet, "_VENDOR_ROOT", copied_root),
                mock.patch.object(quicknet, "_VENDOR_MANIFEST", copied_manifest),
                mock.patch.object(quicknet, "_NODE_MODULES", copied_modules),
                self.assertRaises(quicknet.QuicknetVerificationError),
            ):
                quicknet.verify_vendored_noble()

            shutil.copy2(
                VENDOR_ROOT / "node_modules" / "@noble" / "hashes" / "sha2.js",
                target,
            )
            extra = copied_modules / "@noble" / "hashes" / "unexpected.js"
            extra.write_text('"use strict";\n', encoding="ascii")
            with (
                mock.patch.object(quicknet, "_VENDOR_ROOT", copied_root),
                mock.patch.object(quicknet, "_VENDOR_MANIFEST", copied_manifest),
                mock.patch.object(quicknet, "_NODE_MODULES", copied_modules),
                self.assertRaises(quicknet.QuicknetVerificationError),
            ):
                quicknet.verify_vendored_noble()


@unittest.skipUnless(AVAILABLE_NODE_EXECUTABLE, "Node unavailable for BLS semantic test")
class KP1979V3QuicknetPortableNodeTests(unittest.TestCase):
    def test_node_adversarial_suite_passes(self) -> None:
        node_executable = cast(str, AVAILABLE_NODE_EXECUTABLE)
        version_result = subprocess.run(
            [node_executable, "--version"],
            cwd=ROOT,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
            capture_output=True,
            check=False,
            shell=False,
            timeout=5,
        )
        self.assertEqual(b"", version_result.stderr)
        self.assertEqual(0, version_result.returncode)
        match = re.fullmatch(rb"v([0-9]+)\.[0-9]+\.[0-9]+\n", version_result.stdout)
        self.assertIsNotNone(match)
        major = int(cast(re.Match[bytes], match).group(1))
        exact_qualification_host = (
            Path(node_executable).resolve() == quicknet.NODE_EXECUTABLE
            and version_result.stdout == f"{quicknet.NODE_VERSION}\n".encode("ascii")
            and _trusted_node_host_available()
        )
        if not exact_qualification_host:
            self.assertIn(major, quicknet.CRYPTO_SEMANTIC_TEST_NODE_MAJORS)

        completed = subprocess.run(
            [node_executable, "--test", "--test-reporter=tap", str(NODE_TEST)],
            cwd=ROOT,
            env={
                "LANG": "C",
                "LC_ALL": "C",
                "NODE_NO_WARNINGS": "1",
                "NODE_OPTIONS": "",
                "NODE_PATH": "",
                "PATH": "/usr/bin",
                "TZ": "UTC",
            },
            capture_output=True,
            check=False,
            shell=False,
            timeout=30,
        )
        self.assertEqual(b"", completed.stderr)
        self.assertEqual(0, completed.returncode, completed.stdout.decode("ascii", "replace"))
        summary_lines = completed.stdout.splitlines()
        self.assertIn(b"# tests 6", summary_lines)
        self.assertIn(b"# pass 6", summary_lines)
        self.assertIn(b"# fail 0", summary_lines)
        self.assertIn(b"# skipped 0", summary_lines)


@unittest.skipUnless(
    _trusted_node_host_available(), "trusted Node 18 host prerequisites unavailable"
)
class KP1979V3QuicknetNode18Tests(unittest.TestCase):
    def test_qualified_standalone_cli_is_promptly_bounded(self) -> None:
        completed = subprocess.run(
            [str(quicknet.NODE_EXECUTABLE), "--test", str(HOST_NODE_TEST)],
            cwd=ROOT,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
            capture_output=True,
            check=False,
            shell=False,
            timeout=10,
        )
        self.assertEqual(b"", completed.stderr)
        self.assertEqual(0, completed.returncode, completed.stdout.decode("ascii", "replace"))
        self.assertIn(b"# pass 1", completed.stdout)
        self.assertIn(b"# fail 0", completed.stdout)
        self.assertIn(b"# skipped 0", completed.stdout)

    def test_python_wrapper_verifies_only_the_known_vector(self) -> None:
        verified = quicknet.verify_quicknet_beacon(
            1000,
            EXPECTED_SIGNATURE,
            EXPECTED_RANDOMNESS,
        )
        self.assertEqual(1000, verified.round)
        self.assertEqual(EXPECTED_SIGNATURE, verified.signature)
        self.assertEqual(EXPECTED_RANDOMNESS, verified.randomness)
        self.assertEqual(EXPECTED_CHAIN_HASH, verified.chain_hash)
        constructor = cast(Any, quicknet.VerifiedQuicknetBeacon)
        with self.assertRaises(TypeError):
            constructor(
                round=1000,
                signature=EXPECTED_SIGNATURE,
                randomness=EXPECTED_RANDOMNESS,
            )
        with self.assertRaises(quicknet.QuicknetVerificationError):
            quicknet.VerifiedQuicknetBeacon(
                _token=object(),
                round=1000,
                signature=EXPECTED_SIGNATURE,
                randomness=EXPECTED_RANDOMNESS,
            )
        with self.assertRaises(quicknet.QuicknetVerificationError):
            quicknet.verify_quicknet_beacon(
                1001,
                EXPECTED_SIGNATURE,
                EXPECTED_RANDOMNESS,
            )

    def test_cli_succeeds_in_a_private_network_namespace(self) -> None:
        systemd_run = Path("/usr/bin/systemd-run")
        if not systemd_run.is_file():
            self.skipTest("systemd-run unavailable")
        environment_arguments = [
            f"{key}={value}" for key, value in sorted(quicknet._NODE_ENVIRONMENT.items())
        ]
        completed = subprocess.run(
            [
                str(systemd_run),
                "--user",
                "--pipe",
                "--wait",
                "--quiet",
                "--collect",
                "--property=PrivateNetwork=yes",
                "--property=RestrictAddressFamilies=AF_UNIX",
                "/usr/bin/env",
                "-i",
                *environment_arguments,
                str(quicknet.NODE_EXECUTABLE),
                str(VENDOR_ROOT / "quicknet_verify.cjs"),
            ],
            cwd=ROOT,
            input=_known_request(),
            capture_output=True,
            check=False,
            shell=False,
            timeout=30,
        )
        self.assertEqual(b"", completed.stderr)
        self.assertEqual(0, completed.returncode, completed.stdout.decode("ascii", "replace"))
        response = json.loads(completed.stdout)
        self.assertEqual("verified", response["status"])
        self.assertEqual("1000", response["round"])


if __name__ == "__main__":
    unittest.main()
