"""Verify the source-free NMFA preregistration evaluator from one built wheel."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Never

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"
EXPECTED_BUNDLE_BYTES = 3181
EXPECTED_BUNDLE_SHA256 = "ec9ba6fbaa5df13dce438f819114206da2d6ca6e68afb521476635d5abd91a79"
EXPECTED_GATE_PLAN_SHA256 = (
    "sha256:dfea30b6cc0635e98d6fc1c0125e428df454bfbb4f22ba464923801db01273af"
)

WHEEL_PATH_BY_BUNDLE_PATH = {
    "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json": (
        "indusbench/benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
    ),
    "benchmark/numeral-metrology-functional-anchor-protocol-v1.json": (
        "indusbench/benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
    ),
    "schemas/nmfa-value-blind-preregistration-gate-plan.schema.json": (
        "indusbench/schemas/nmfa-value-blind-preregistration-gate-plan.schema.json"
    ),
    "schemas/nmfa-value-blind-preregistration-manifest.schema.json": (
        "indusbench/schemas/nmfa-value-blind-preregistration-manifest.schema.json"
    ),
    "schemas/nmfa-value-blind-preregistration-report.schema.json": (
        "indusbench/schemas/nmfa-value-blind-preregistration-report.schema.json"
    ),
    "src/indusbench/io.py": "indusbench/io.py",
    "src/indusbench/nmfa_preregistration.py": "indusbench/nmfa_preregistration.py",
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
from indusbench.nmfa_preregistration import load_installed_nmfa_preregistration_gate_plan

package_file = pathlib.Path(indusbench.__file__).resolve()
if not package_file.is_relative_to(wheel_root):
    raise SystemExit("source checkout shadowed extracted wheel")

snapshot = load_installed_nmfa_preregistration_gate_plan()
observed = {
    "cell_minimum_g": snapshot.cell_minimum_g,
    "complement_minimum_g": snapshot.complement_minimum_g,
    "eligible_g_minimum": snapshot.eligible_g_minimum,
    "execution_authorized": snapshot.execution_authorized,
    "gate_id": snapshot.gate_id,
    "gate_plan_sha256": snapshot.gate_plan_sha256,
    "holdout_minimum_g": snapshot.holdout_minimum_g,
    "max_n2_primary_assignments": snapshot.max_n2_primary_assignments,
    "n2_minimum_movable_g": snapshot.n2_minimum_movable_g,
    "n2_minimum_movable_percent": snapshot.n2_minimum_movable_percent,
    "parent_protocol_sha256": snapshot.parent_protocol_sha256,
    "registration_ready": snapshot.registration_ready,
    "source_access_authorized": snapshot.source_access_authorized,
}
expected = {
    "cell_minimum_g": 20,
    "complement_minimum_g": 80,
    "eligible_g_minimum": 160,
    "execution_authorized": False,
    "gate_id": "nmfa-value-blind-preregistration-gate-v1",
    "gate_plan_sha256": expected_plan_sha256,
    "holdout_minimum_g": 80,
    "max_n2_primary_assignments": 2000000,
    "n2_minimum_movable_g": 64,
    "n2_minimum_movable_percent": 80,
    "parent_protocol_sha256": (
        "sha256:b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"
    ),
    "registration_ready": False,
    "source_access_authorized": False,
}
if observed != expected:
    raise SystemExit("installed NMFA preregistration snapshot mismatch")
print(json.dumps({"isolated_wheel_nmfa_preregistration": "source_free_validated"}, sort_keys=True))
"""


def fail(message: str) -> Never:
    raise SystemExit(f"NMFA installed-distribution verification failed: {message}")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode_json(raw: bytes, label: str):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"NMFA installed-distribution verification failed: invalid {label}"
        ) from error


def regular_member(archive: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
    matching = [member for member in archive.infolist() if member.filename == name]
    if len(matching) != 1 or not stat.S_ISREG(matching[0].external_attr >> 16):
        fail("required regular wheel member absent or duplicated")
    return matching[0]


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

        wheel_bundle_name = "indusbench/" + BUNDLE_PATH
        wheel_bundle = regular_member(archive, wheel_bundle_name)
        if archive.read(wheel_bundle) != bundle_raw:
            fail("wheel/repository evaluator bundle mismatch")

        rows = bundle["files"]
        for row in rows:
            repo_raw = (ROOT / row["path"]).read_bytes()
            if len(repo_raw) != row["bytes"] or "sha256:" + sha256(repo_raw) != row["sha256"]:
                fail("bundle/repository file commitment mismatch")
            if row["verification"] == "runtime_and_ci":
                wheel_name = WHEEL_PATH_BY_BUNDLE_PATH.get(row["path"])
                if wheel_name is None:
                    fail("runtime file has no wheel mapping")
                member = regular_member(archive, wheel_name)
                if archive.read(member) != repo_raw:
                    fail("wheel/repository runtime file mismatch")

        decoded = {
            path: decode_json((ROOT / path).read_bytes(), path)
            for path in WHEEL_PATH_BY_BUNDLE_PATH
            if path.endswith(".json")
        }
        schema_paths = [path for path in decoded if path.startswith("schemas/")]
        for path in schema_paths:
            Draft202012Validator.check_schema(decoded[path])
        plan_validator = Draft202012Validator(
            decoded["schemas/nmfa-value-blind-preregistration-gate-plan.schema.json"],
            format_checker=FormatChecker(),
        )
        plan = decoded["benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"]
        if next(plan_validator.iter_errors(plan), None) is not None:
            fail("packaged NMFA plan/schema mismatch")

        metadata_members = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_members) != 1:
            fail("wheel metadata absent or duplicated")
        metadata = archive.read(metadata_members[0]).decode("utf-8")
        exact_requirements = (
            "Requires-Dist: attrs==26.1.0",
            "Requires-Dist: jsonschema[format]==4.26.0",
            "Requires-Dist: jsonschema-specifications==2025.9.1",
            "Requires-Dist: referencing==0.37.0",
            "Requires-Dist: rfc3339-validator==0.1.4",
            "Requires-Dist: rpds-py==2026.6.3",
            "Requires-Dist: six==1.17.0",
            "Requires-Dist: typing-extensions==4.16.0; python_version < '3.13'",
        )
        if any(requirement not in metadata for requirement in exact_requirements):
            fail("wheel metadata lacks exact evaluator dependency commitment")

        previous_umask = os.umask(0o022)
        try:
            with tempfile.TemporaryDirectory(prefix="indus-nmfa-wheel-") as raw_directory:
                root = Path(raw_directory)
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
                        EXPECTED_GATE_PLAN_SHA256,
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
        fail("isolated wheel loader rejected NMFA resources")
    expected_stdout = json.dumps(
        {"isolated_wheel_nmfa_preregistration": "source_free_validated"}, sort_keys=True
    )
    if completed.stdout.strip() != expected_stdout or completed.stderr:
        fail("isolated wheel loader emitted unexpected output")


def main() -> None:
    if len(sys.argv) != 2:
        fail("exactly one wheel path is required")
    verify(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    main()
