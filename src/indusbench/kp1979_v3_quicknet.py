"""Network-independent, fail-closed verification for the fixed Quicknet chain.

The verifier fetches and installs nothing. Its source graph is exact-byte
checked and works in a private network namespace, but the Python wrapper does
not claim to create a kernel-enforced network sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Never

VERIFIER_VERSION = "kp1979-v3-quicknet-offline-verifier-v1"
CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
PUBLIC_KEY = (
    "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183"
    "c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4"
    "bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a"
)
GROUP_HASH = "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e"
SCHEME_ID = "bls-unchained-g1-rfc9380"
BEACON_ID = "quicknet"
DST = "BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"
GENESIS_TIME = 1_692_803_367
PERIOD_SECONDS = 3
MAX_ROUND = (1 << 64) - 1

ROUND_1000_SIGNATURE = (
    "b44679b9a59af2ec876b1a6b1ad52ea9b1615fc3982b19576350f93447cb112"
    "5e342b73a8dd2bacbe47e4b6b63ed5e39"
)
ROUND_1000_RANDOMNESS = "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd"

NODE_EXECUTABLE = Path("/usr/bin/node")
NODE_VERSION = "v18.19.1"
NODE_RUNTIME_SUPPORT_STATUS = "eol-host-qualified-only"
# Module-level BLS semantic tests may run on these supported Node LTS majors.
# This is not an authorization list for the legacy host-qualified wrapper.
CRYPTO_SEMANTIC_TEST_NODE_MAJORS = (22, 24)
NODE_LAUNCHER_SHA256 = "f3f93db342d5ac5bb61656d0599a603a73779e98befd9342171e550002725f4d"
PRLIMIT_EXECUTABLE = Path("/usr/bin/prlimit")
PRLIMIT_VERSION = "prlimit from util-linux 2.39.3"
PRLIMIT_LAUNCHER_SHA256 = "f27cfd8c1512a4cc6541b59b80cb4cdfd6ef28c34aa21db4299b48264cd0d128"
NODE_VERIFIER_SHA256 = "7d0423e288e6bb73a6195a0ec7fa11d458936590bdd7b683fd275d2cb0f732b8"
VENDOR_MANIFEST_SHA256 = "84e999ba41218a6a80b0a880fe714bf158667f670ce394e0f39774a9e7586b4b"

MAX_MANIFEST_BYTES = 16_384
MAX_REQUEST_BYTES = 4_096
MAX_OUTPUT_BYTES = 4_096
WALL_TIMEOUT_SECONDS = 10
_INTERRUPT_CLEANUP_TIMEOUT_SECONDS = 1

_VENDOR_ROOT = Path(__file__).resolve().parent / "_vendor" / "noble"
_NODE_VERIFIER = _VENDOR_ROOT / "quicknet_verify.cjs"
_VENDOR_MANIFEST = _VENDOR_ROOT / "VENDOR_MANIFEST.json"
_NODE_MODULES = _VENDOR_ROOT / "node_modules"
_PRLIMIT_ARGUMENTS = (
    "--as=1073741824:1073741824",
    "--core=0:0",
    "--cpu=5:5",
    f"--fsize={MAX_OUTPUT_BYTES}:{MAX_OUTPUT_BYTES}",
    "--nofile=32:32",
)
_NODE_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "NODE_NO_WARNINGS": "1",
    "NODE_OPTIONS": "",
    "NODE_PATH": "",
    "PATH": "/usr/bin",
    "TZ": "UTC",
}
_EXPECTED_PACKAGE_METADATA = {
    "@noble/curves": {
        "git_commit": "a0ac59846ee76c52f7c18886f4963e1211345d48",
        "github_tag_object": "be48f3ce4087a428701487675fc745b6d362bc01",
        "github_tag_signature_verified": True,
        "license": "MIT",
        "npm_integrity": (
            "sha512-gbKGcRUYIjA3/zCCNaWDciTMFI0dCkvou3TL8Zmy5Nc7sJ47a0jtOeZoTaMxkuq"
            "Ro9cRhjOdZJXegxYE5FN/xw=="
        ),
        "npm_shasum_sha1": "79d04b4758a43e4bca2cbdc62e7771352fa6b951",
        "registry_signature_keyid": "SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U",
        "tarball_sha256": "c4c5545645b8d58a080d2faf84982f6fe5dc3a0516e11de8dc571b38cab565e9",
        "tarball_url": "https://registry.npmjs.org/@noble/curves/-/curves-1.9.7.tgz",
        "version": "1.9.7",
    },
    "@noble/hashes": {
        "git_commit": "32f700f38ec49d7e6b2ab687904d6b2d7d60d80a",
        "github_tag_object": "990a523783b254a328b8448a7b9563957121de27",
        "github_tag_signature_verified": True,
        "license": "MIT",
        "npm_integrity": (
            "sha512-jCs9ldd7NwzpgXDIf6P3+NrHh9/sD6CQdxHyjQI+h/6rDNo88ypBxxz45UDuZHz9"
            "r3tNz7N/VInSVoVdtXEI4A=="
        ),
        "npm_shasum_sha1": "cee43d801fcef9644b11b8194857695acd5f815a",
        "registry_signature_keyid": "SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U",
        "tarball_sha256": "e8a765d92c04faaccba8776411c5038cb195f812ee629fce07e1d2e6aec80ea0",
        "tarball_url": "https://registry.npmjs.org/@noble/hashes/-/hashes-1.8.0.tgz",
        "upstream_whitespace_exceptions": [
            {
                "content": "const hasHexBuiltin = /* @__PURE__ */ (() => ",
                "line": 133,
                "path": "utils.js",
                "reason": "exact npm 1.8.0 source byte",
            }
        ],
        "version": "1.8.0",
    },
}


class QuicknetVerificationError(ValueError):
    """A path-free, detail-free Quicknet verification failure."""

    def __init__(self) -> None:
        super().__init__("quicknet_verification_failed")


@dataclass(frozen=True, slots=True)
class VerifiedQuicknetBeacon:
    """Trusted local return value, not a transferable proof or attestation.

    Normal construction is restricted to :func:`verify_quicknet_beacon`.
    Like every in-process Python object, this is not an unforgeable receipt and
    supplies no trusted time, custody, execution, or external-attestation claim.
    """

    round: int
    signature: str
    randomness: str
    chain_hash: str
    scheme_id: str

    def __init__(
        self,
        *,
        _token: object,
        round: int,
        signature: str,
        randomness: str,
    ) -> None:
        if _token is not _VERIFIED_BEACON_CONSTRUCTION_TOKEN:
            _fail()
        object.__setattr__(self, "round", round)
        object.__setattr__(self, "signature", signature)
        object.__setattr__(self, "randomness", randomness)
        object.__setattr__(self, "chain_hash", CHAIN_HASH)
        object.__setattr__(self, "scheme_id", SCHEME_ID)


_VERIFIED_BEACON_CONSTRUCTION_TOKEN = object()


def _fail() -> Never:
    raise QuicknetVerificationError


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
    except OSError:
        _fail()
    return digest.hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    try:
        rendered = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return (rendered + "\n").encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError):
        _fail()


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if not isinstance(key, str) or key in result:
            _fail()
        result[key] = value
    return result


def _reject_json_constant(_: str) -> object:
    _fail()


def _load_canonical_json(raw: bytes) -> object:
    if not raw or len(raw) > MAX_MANIFEST_BYTES or not raw.endswith(b"\n"):
        _fail()
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail()
    if _canonical_json_bytes(value) != raw:
        _fail()
    return value


def _require_safe_file(
    path: Path,
    *,
    expected_sha256: str,
    root_owned: bool = False,
    executable: bool = False,
) -> Path:
    if not path.is_absolute():
        _fail()
    try:
        metadata = path.stat(follow_symlinks=False)
        resolved = path.resolve(strict=True)
    except OSError:
        _fail()
    trusted_owners = {0} if root_owned else {0, os.getuid()}
    if (
        path.is_symlink()
        or resolved != path
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) & 0o022
        or metadata.st_uid not in trusted_owners
        or (executable and not os.access(path, os.X_OK))
        or _sha256_path(path) != expected_sha256
    ):
        _fail()
    return path


def _require_safe_vendor_directory(path: Path) -> None:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError:
        _fail()
    if (
        path.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid not in {0, os.getuid()}
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        _fail()


def verify_vendored_noble() -> str:
    """Verify the exact minimal noble source set without network or installation."""

    manifest_path = _require_safe_file(
        _VENDOR_MANIFEST,
        expected_sha256=VENDOR_MANIFEST_SHA256,
    )
    try:
        raw_manifest = manifest_path.read_bytes()
    except OSError:
        _fail()
    value = _load_canonical_json(raw_manifest)
    if not isinstance(value, dict) or set(value) != {"format", "packages"}:
        _fail()
    if value["format"] != "kp1979-v3-noble-vendor-manifest-v1":
        _fail()
    packages = value["packages"]
    if not isinstance(packages, list) or len(packages) != 2:
        _fail()

    declared_paths: set[Path] = set()
    observed_names: list[str] = []
    for package in packages:
        if not isinstance(package, dict):
            _fail()
        name = package.get("name")
        if not isinstance(name, str) or name not in _EXPECTED_PACKAGE_METADATA:
            _fail()
        observed_names.append(name)
        expected_metadata = _EXPECTED_PACKAGE_METADATA[name]
        if set(package) != {"files", "name", *expected_metadata}:
            _fail()
        if any(package[key] != expected for key, expected in expected_metadata.items()):
            _fail()
        package_leaf = name.removeprefix("@noble/")
        package_root = _NODE_MODULES / "@noble" / package_leaf
        files = package["files"]
        if not isinstance(files, list) or not files:
            _fail()
        previous_path = ""
        for file_record in files:
            if not isinstance(file_record, dict) or set(file_record) != {"path", "sha256"}:
                _fail()
            relative_text = file_record["path"]
            expected_digest = file_record["sha256"]
            if (
                not isinstance(relative_text, str)
                or not isinstance(expected_digest, str)
                or len(expected_digest) != 64
                or any(character not in "0123456789abcdef" for character in expected_digest)
                or relative_text <= previous_path
            ):
                _fail()
            relative = PurePosixPath(relative_text)
            if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
                _fail()
            path = package_root.joinpath(*relative.parts)
            _require_safe_file(path, expected_sha256=expected_digest)
            if path in declared_paths:
                _fail()
            declared_paths.add(path)
            previous_path = relative_text

    if observed_names != ["@noble/curves", "@noble/hashes"]:
        _fail()
    for directory in [_VENDOR_ROOT, _NODE_MODULES, _NODE_MODULES / "@noble"]:
        _require_safe_vendor_directory(directory)
    for directory in sorted(
        {path.parent for path in declared_paths},
        key=lambda entry: (len(entry.parts), entry.as_posix()),
    ):
        _require_safe_vendor_directory(directory)
    actual_paths = {
        path for path in _NODE_MODULES.rglob("*") if path.is_file() or path.is_symlink()
    }
    if actual_paths != declared_paths:
        _fail()
    return VENDOR_MANIFEST_SHA256


def _validate_hex(value: object, *, byte_length: int) -> str:
    if (
        type(value) is not str
        or len(value) != byte_length * 2
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail()
    return value


def canonical_quicknet_request(round_number: int, signature: str, randomness: str) -> bytes:
    """Build the only accepted, lossless request shape."""

    if type(round_number) is not int or not 1 <= round_number <= MAX_ROUND:
        _fail()
    checked_signature = _validate_hex(signature, byte_length=48)
    checked_randomness = _validate_hex(randomness, byte_length=32)
    if hashlib.sha256(bytes.fromhex(checked_signature)).hexdigest() != checked_randomness:
        _fail()
    request = {
        "beacon_id": BEACON_ID,
        "chain_hash": CHAIN_HASH,
        "dst": DST,
        "genesis_time": GENESIS_TIME,
        "group_hash": GROUP_HASH,
        "period": PERIOD_SECONDS,
        "public_key": PUBLIC_KEY,
        "randomness": checked_randomness,
        "round": str(round_number),
        "scheme_id": SCHEME_ID,
        "signature": checked_signature,
        "version": VERIFIER_VERSION,
    }
    encoded = _canonical_json_bytes(request)
    if len(encoded) > MAX_REQUEST_BYTES:
        _fail()
    return encoded


def _verify_host_launcher(
    executable: Path,
    *,
    expected_sha256: str,
    expected_version: str,
) -> None:
    _require_safe_file(
        executable,
        expected_sha256=expected_sha256,
        root_owned=True,
        executable=True,
    )
    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            cwd=Path("/"),
            env=_NODE_ENVIRONMENT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            shell=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        _fail()
    if (
        completed.returncode != 0
        or completed.stdout != f"{expected_version}\n".encode("ascii")
        or completed.stderr
    ):
        _fail()


def _verify_host_prerequisites() -> None:
    """Check the trusted OS launchers and their reported versions.

    Launcher digests do not attest their dynamic shared-library closure. Those
    root-owned OS runtimes remain part of the trusted host base. Qualification
    tests run the known vector as semantic evidence for this pinned stack; this
    function does not replace caller input with a hidden runtime self-test.
    Node 18 is end-of-life, so this existing host is qualification-only; any
    long-lived or public deployment requires a separately audited supported
    runtime rather than treating this pin as portable or currently supported.
    """

    _verify_host_launcher(
        NODE_EXECUTABLE,
        expected_sha256=NODE_LAUNCHER_SHA256,
        expected_version=NODE_VERSION,
    )
    _verify_host_launcher(
        PRLIMIT_EXECUTABLE,
        expected_sha256=PRLIMIT_LAUNCHER_SHA256,
        expected_version=PRLIMIT_VERSION,
    )


def _parse_verified_output(
    raw: bytes,
    *,
    round_number: int,
    randomness: str,
) -> None:
    value = _load_canonical_json(raw)
    expected = {
        "chain_hash": CHAIN_HASH,
        "randomness": randomness,
        "round": str(round_number),
        "status": "verified",
        "version": VERIFIER_VERSION,
    }
    if value != expected:
        _fail()


def _kill_and_reap_process(
    process: subprocess.Popen[bytes],
    *,
    reraise_cleanup_interrupt: bool,
) -> None:
    """Run bounded termination and optionally re-raise its first interruption."""

    first_cleanup_interrupt: BaseException | None = None
    kill_was_interrupted = False
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except Exception:
        pass
    except BaseException as error:
        first_cleanup_interrupt = error
        kill_was_interrupted = True

    if kill_was_interrupted:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            pass
        except BaseException:
            pass

    try:
        process.communicate(timeout=_INTERRUPT_CLEANUP_TIMEOUT_SECONDS)
    except Exception:
        pass
    except BaseException as error:
        if first_cleanup_interrupt is None:
            first_cleanup_interrupt = error

    wait_was_interrupted = False
    try:
        process.wait(timeout=_INTERRUPT_CLEANUP_TIMEOUT_SECONDS)
    except Exception:
        pass
    except BaseException as error:
        wait_was_interrupted = True
        if first_cleanup_interrupt is None:
            first_cleanup_interrupt = error

    if wait_was_interrupted:
        try:
            process.wait(timeout=_INTERRUPT_CLEANUP_TIMEOUT_SECONDS)
        except Exception:
            pass
        except BaseException:
            pass

    if reraise_cleanup_interrupt and first_cleanup_interrupt is not None:
        raise first_cleanup_interrupt


def verify_quicknet_beacon(
    round_number: int,
    signature: str,
    randomness: str,
) -> VerifiedQuicknetBeacon:
    """Verify one externally obtained beacon without fetching or installing.

    The exact source graph imports no network client, and ordinary Node network
    modules are blocked. This wrapper does not itself establish an OS network
    namespace; callers needing that assurance must provide one externally.
    """

    request = canonical_quicknet_request(round_number, signature, randomness)
    verify_vendored_noble()
    _require_safe_file(_NODE_VERIFIER, expected_sha256=NODE_VERIFIER_SHA256)
    _verify_host_prerequisites()

    with tempfile.TemporaryDirectory(prefix="indus-quicknet-v3-") as raw_directory:
        base_directory = Path(raw_directory)
        if stat.S_IMODE(base_directory.stat().st_mode) & 0o077:
            _fail()
        working_directory = base_directory / "cwd"
        working_directory.mkdir(mode=0o700)
        stdout_path = base_directory / "stdout.bin"
        stderr_path = base_directory / "stderr.bin"
        with stdout_path.open("w+b") as stdout_handle, stderr_path.open("w+b") as stderr_handle:
            try:
                process = subprocess.Popen(
                    [
                        str(PRLIMIT_EXECUTABLE),
                        *_PRLIMIT_ARGUMENTS,
                        "--",
                        str(NODE_EXECUTABLE),
                        str(_NODE_VERIFIER),
                    ],
                    cwd=working_directory,
                    env=_NODE_ENVIRONMENT,
                    stdin=subprocess.PIPE,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    close_fds=True,
                    shell=False,
                    start_new_session=True,
                )
            except (OSError, subprocess.SubprocessError):
                _fail()
            timed_out = False
            try:
                process.communicate(input=request, timeout=WALL_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_and_reap_process(
                    process,
                    reraise_cleanup_interrupt=True,
                )
            except (OSError, subprocess.SubprocessError):
                _kill_and_reap_process(
                    process,
                    reraise_cleanup_interrupt=True,
                )
                _fail()
            except BaseException:
                _kill_and_reap_process(
                    process,
                    reraise_cleanup_interrupt=False,
                )
                raise
            stdout_handle.flush()
            stderr_handle.flush()
            stdout_handle.seek(0)
            stderr_handle.seek(0)
            standard_output = stdout_handle.read(MAX_OUTPUT_BYTES + 1)
            standard_error = stderr_handle.read(MAX_OUTPUT_BYTES + 1)
    if timed_out or process.returncode != 0 or standard_error:
        _fail()
    if (
        not standard_output
        or len(standard_output) > MAX_OUTPUT_BYTES
        or standard_output.count(b"\n") != 1
        or not standard_output.endswith(b"\n")
    ):
        _fail()
    _parse_verified_output(
        standard_output,
        round_number=round_number,
        randomness=randomness,
    )
    return VerifiedQuicknetBeacon(
        _token=_VERIFIED_BEACON_CONSTRUCTION_TOKEN,
        round=round_number,
        signature=signature,
        randomness=randomness,
    )
