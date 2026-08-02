"""Verify the source-free NMFA activation preflight from one built wheel."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Never

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = "benchmark/nmfa-activation-preflight-evaluator-bundle-v1.json"
EXPECTED_BUNDLE_BYTES = 3948
EXPECTED_BUNDLE_SHA256 = "95eeab667878f97450b0a39d92a5dffe46ac2196d49ef2328b134f4570fef2d3"
EXPECTED_PLAN_SHA256 = "sha256:2d75e6f4ceec9f599b4b96720e4373327758b7f863bb0bd884c2361690d11d96"

WHEEL_PATH_BY_BUNDLE_PATH = {
    "benchmark/nmfa-activation-preflight-plan-v1.json": (
        "indusbench/benchmark/nmfa-activation-preflight-plan-v1.json"
    ),
    "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json": (
        "indusbench/benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"
    ),
    "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json": (
        "indusbench/benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
    ),
    "benchmark/numeral-metrology-functional-anchor-protocol-v1.json": (
        "indusbench/benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
    ),
    "schemas/nmfa-activation-preflight-plan.schema.json": (
        "indusbench/schemas/nmfa-activation-preflight-plan.schema.json"
    ),
    "schemas/nmfa-activation-preflight-report.schema.json": (
        "indusbench/schemas/nmfa-activation-preflight-report.schema.json"
    ),
    "schemas/nmfa-activation-preflight-request.schema.json": (
        "indusbench/schemas/nmfa-activation-preflight-request.schema.json"
    ),
    "schemas/nmfa-external-trust-profile.schema.json": (
        "indusbench/schemas/nmfa-external-trust-profile.schema.json"
    ),
    "src/indusbench/io.py": "indusbench/io.py",
    "src/indusbench/nmfa_preflight.py": "indusbench/nmfa_preflight.py",
}

_ISOLATED_PROGRAM = r"""
import json
import pathlib
import sys

wheel_root = pathlib.Path(sys.argv[1]).resolve()
expected_plan_sha256 = sys.argv[2]
sys.path.insert(0, str(wheel_root))

def deny_network(event, args):
    del args
    if event.startswith("socket."):
        raise RuntimeError("network forbidden")

sys.addaudithook(deny_network)

import indusbench
from indusbench.nmfa_preflight import load_installed_nmfa_activation_preflight_plan

package_file = pathlib.Path(indusbench.__file__).resolve()
if not package_file.is_relative_to(wheel_root):
    raise SystemExit("source checkout shadowed extracted wheel")

snapshot = load_installed_nmfa_activation_preflight_plan()
observed = {
    "compiled_blockers": list(snapshot.compiled_blockers),
    "execution_authorized": snapshot.execution_authorized,
    "plan_id": snapshot.plan_id,
    "plan_sha256": snapshot.plan_sha256,
    "premetadata_ready_enabled": snapshot.premetadata_ready_enabled,
    "prevalue_ready_enabled": snapshot.prevalue_ready_enabled,
    "source_access_authorized": snapshot.source_access_authorized,
}
expected = {
    "compiled_blockers": [
        "TYPED_EXECUTION_BUNDLE_UNBOUND",
        "EXTERNAL_TRUST_PROFILE_UNBOUND",
        "EXTERNAL_TIME_ANCHOR_UNBOUND",
        "CONSUMPTION_REGISTRY_UNBOUND",
        "ACTIVATION_WRAPPER_UNBOUND",
    ],
    "execution_authorized": False,
    "plan_id": "nmfa-activation-preflight-plan-v1",
    "plan_sha256": expected_plan_sha256,
    "premetadata_ready_enabled": False,
    "prevalue_ready_enabled": False,
    "source_access_authorized": False,
}
if observed != expected:
    raise SystemExit("installed NMFA activation preflight snapshot mismatch")
print(json.dumps(
    {"isolated_wheel_nmfa_preflight": "source_free_blocked_validated"},
    sort_keys=True,
))
"""


def fail(message: str) -> Never:
    raise SystemExit(f"NMFA preflight installed-distribution verification failed: {message}")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode_json(raw: bytes, label: str):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"NMFA preflight installed-distribution verification failed: invalid {label}"
        ) from error


def regular_member(archive: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
    matching = [member for member in archive.infolist() if member.filename == name]
    if len(matching) != 1 or not stat.S_ISREG(matching[0].external_attr >> 16):
        fail("required regular wheel member absent or duplicated")
    return matching[0]


def metadata_preserves_exact_requirements(metadata: str, expected: tuple[str, ...]) -> bool:
    """Require one exact requirement per bound dependency while allowing dev extras."""

    try:
        observed = Parser().parsestr(metadata).get_all("Requires-Dist", [])
    except (TypeError, ValueError):
        return False
    name_pattern = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*")

    def normalized_name(requirement: str) -> str | None:
        match = name_pattern.match(requirement)
        if match is None:
            return None
        return re.sub(r"[-_.]+", "-", match.group().lower())

    expected_by_name: dict[str, str] = {}
    for requirement in expected:
        name = normalized_name(requirement)
        if name is None or name in expected_by_name:
            return False
        expected_by_name[name] = requirement
    observed_by_name: dict[str, list[str]] = {}
    for requirement in observed:
        name = normalized_name(requirement)
        if name is None:
            return False
        observed_by_name.setdefault(name, []).append(requirement)
    return all(
        observed_by_name.get(name) == [requirement]
        for name, requirement in expected_by_name.items()
    )


def verify(wheel: Path) -> None:
    if not wheel.is_file() or wheel.suffix != ".whl":
        fail("exactly one wheel path is required")
    bundle_raw = (ROOT / BUNDLE_PATH).read_bytes()
    if len(bundle_raw) != EXPECTED_BUNDLE_BYTES or sha256(bundle_raw) != EXPECTED_BUNDLE_SHA256:
        fail("repository evaluator bundle is not the frozen bundle")
    bundle = decode_json(bundle_raw, BUNDLE_PATH)

    with zipfile.ZipFile(wheel) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            fail("duplicate wheel member")
        for name in names:
            parsed = PurePosixPath(name)
            if parsed.is_absolute() or ".." in parsed.parts or "\\" in name:
                fail("unsafe wheel member path")

        wheel_bundle = regular_member(archive, "indusbench/" + BUNDLE_PATH)
        if archive.read(wheel_bundle) != bundle_raw:
            fail("wheel/repository evaluator bundle mismatch")

        for row in bundle["files"]:
            if row["verification"] != "runtime_and_ci":
                fail("unknown evaluator bundle verification policy")
            repo_raw = (ROOT / row["path"]).read_bytes()
            if len(repo_raw) != row["bytes"] or "sha256:" + sha256(repo_raw) != row["sha256"]:
                fail("bundle/repository file commitment mismatch")
            if row["verification"] == "runtime_and_ci":
                wheel_name = WHEEL_PATH_BY_BUNDLE_PATH.get(row["path"])
                if wheel_name is None:
                    fail("runtime file has no wheel mapping")
                if archive.read(regular_member(archive, wheel_name)) != repo_raw:
                    fail("wheel/repository runtime file mismatch")

        decoded = {
            path: decode_json((ROOT / path).read_bytes(), path)
            for path in WHEEL_PATH_BY_BUNDLE_PATH
            if path.endswith(".json")
        }
        for path in (path for path in decoded if path.startswith("schemas/")):
            Draft202012Validator.check_schema(decoded[path])
        validator = Draft202012Validator(
            decoded["schemas/nmfa-activation-preflight-plan.schema.json"],
            format_checker=FormatChecker(),
        )
        plan = decoded["benchmark/nmfa-activation-preflight-plan-v1.json"]
        if next(validator.iter_errors(plan), None) is not None:
            fail("packaged NMFA activation preflight plan/schema mismatch")

        metadata_members = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_members) != 1:
            fail("wheel metadata absent or duplicated")
        metadata = archive.read(metadata_members[0]).decode("utf-8")
        exact_requirements = (
            "attrs==26.1.0",
            "cffi==2.1.0",
            "cryptography==50.0.0",
            "jsonschema[format]==4.26.0",
            "jsonschema-specifications==2025.9.1",
            "pycparser==3.0",
            "referencing==0.37.0",
            "rfc3339-validator==0.1.4",
            "rpds-py==2026.6.3",
            "six==1.17.0",
            "typing-extensions==4.16.0; python_version < '3.13'",
        )
        if not metadata_preserves_exact_requirements(metadata, exact_requirements):
            fail("wheel metadata lacks exact evaluator dependency commitment")

        previous_umask = os.umask(0o022)
        try:
            with tempfile.TemporaryDirectory(prefix="indus-nmfa-preflight-wheel-") as raw_dir:
                root = Path(raw_dir)
                extracted = root / "installed"
                empty_cwd = root / "empty-cwd"
                extracted.mkdir()
                empty_cwd.mkdir()
                archive.extractall(extracted)
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-s",
                        "-B",
                        "-c",
                        _ISOLATED_PROGRAM,
                        str(extracted),
                        EXPECTED_PLAN_SHA256,
                    ],
                    cwd=empty_cwd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
        finally:
            os.umask(previous_umask)
    if completed.returncode != 0:
        fail("isolated wheel loader rejected NMFA activation preflight resources")
    expected_stdout = json.dumps(
        {"isolated_wheel_nmfa_preflight": "source_free_blocked_validated"}, sort_keys=True
    )
    if completed.stdout.strip() != expected_stdout or completed.stderr:
        fail("isolated wheel loader emitted unexpected output")


def main() -> None:
    if len(sys.argv) != 2:
        fail("exactly one wheel path is required")
    verify(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    main()
