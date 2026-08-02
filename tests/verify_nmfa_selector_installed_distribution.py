"""Verify the source-free NMFA selector core from one built wheel."""

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
BUNDLE_PATH = "benchmark/nmfa-selector-core-evaluator-bundle-v1.json"
EXPECTED_BUNDLE_BYTES = 3493
EXPECTED_BUNDLE_SHA256 = "c8aa0101a5e0396dbd7a577154302e1823235d31075bd2407247a8fbe0209eb6"
EXPECTED_PLAN_SHA256 = "sha256:f4c80a15804c4dffcef4f850d597f54836b44c3444af811f1c686814f39c5190"

WHEEL_PATH_BY_BUNDLE_PATH = {
    "benchmark/nmfa-selector-core-plan-v1.json": (
        "indusbench/benchmark/nmfa-selector-core-plan-v1.json"
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
    "schemas/nmfa-selector-core-plan.schema.json": (
        "indusbench/schemas/nmfa-selector-core-plan.schema.json"
    ),
    "schemas/nmfa-selector-inventory.schema.json": (
        "indusbench/schemas/nmfa-selector-inventory.schema.json"
    ),
    "schemas/nmfa-selector-receipt.schema.json": (
        "indusbench/schemas/nmfa-selector-receipt.schema.json"
    ),
    "src/indusbench/io.py": "indusbench/io.py",
    "src/indusbench/nmfa_selector_core.py": "indusbench/nmfa_selector_core.py",
}

_ISOLATED_PROGRAM = r"""
import hashlib
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
from indusbench.io import encode_json
from indusbench.nmfa_selector_core import (
    NMFASelectorOutcome,
    evaluate_nmfa_selector_inventory,
    load_installed_nmfa_selector_plan,
    normalize_nmfa_split_nonce,
    validate_nmfa_selector_inventory,
)

package_file = pathlib.Path(indusbench.__file__).resolve()
if not package_file.is_relative_to(wheel_root):
    raise SystemExit("source checkout shadowed extracted wheel")

plan = load_installed_nmfa_selector_plan()
raw_plan = (
    wheel_root / "indusbench" / "benchmark" / "nmfa-selector-core-plan-v1.json"
).read_bytes()
if "sha256:" + hashlib.sha256(raw_plan).hexdigest() != expected_plan_sha256:
    raise SystemExit("installed selector plan digest mismatch")

f_id = "hmac-sha256:" + "0" * 64
contexts = {
    "site": "hmac-sha256:" + "1" * 64,
    "period": "hmac-sha256:" + "2" * 64,
    "medium": "hmac-sha256:" + "3" * 64,
    "object_type": "hmac-sha256:" + "4" * 64,
}
eligible_payload = {
    "axis_order": ["site", "period", "medium", "object_type"],
    "closure_tables": {
        axis: [{"group_id": value, "member_value_ids": [value]}]
        for axis, value in contexts.items()
    },
    "components": [{
        "complete_c": True,
        "m_g_member_ids": [f_id],
        "members": [{
            "context": {
                "medium": contexts["medium"],
                "nuisance": [],
                "object_type": contexts["object_type"],
                "period": contexts["period"],
                "site": contexts["site"],
            },
            "e_eligible": True,
            "f_id": f_id,
            "split_eligible": True,
        }],
        "split_eligible_g": True,
    }],
    "nuisance_semantics": {
        "nuisance_field_ids": [],
        "nuisance_vocabularies": [],
        "provenance_policy": "single_prespecified_regime",
    },
}
inventory = {
    "claim_binding": {
        "claim_family_id": "registry-id:" + "1" * 64,
        "claim_slot_id": "registry-id:" + "2" * 64,
        "experiment_instance_id": "registry-id:" + "3" * 64,
        "predecessor_chain_head_sha256": "sha256:" + "9" * 64,
    },
    "eligible_split_inventory": eligible_payload,
    "format_version": "1.0.0",
    "gate_plan_sha256": plan["bindings"]["gate_plan_sha256"],
    "parent_protocol_sha256": plan["bindings"]["parent_protocol_sha256"],
    "record_kind": "nmfa_selector_inventory",
    "selector_plan_sha256": expected_plan_sha256,
}
eligible_digest = "sha256:" + hashlib.sha256(
    b"indusbench:nmfa:eligible-split-inventory:v1\x00" + encode_json(eligible_payload)
).hexdigest()
raw_inventory = encode_json(inventory)
validated = validate_nmfa_selector_inventory(raw_inventory, eligible_digest)
analysis = evaluate_nmfa_selector_inventory(raw_inventory, eligible_digest)
if analysis.outcome is not NMFASelectorOutcome.INSUFFICIENT_ELIGIBLE_G:
    raise SystemExit("installed selector synthetic outcome mismatch")
if normalize_nmfa_split_nonce("00" * 32) != bytes(32):
    raise SystemExit("installed selector nonce normalization mismatch")
observed = {
    "complete_E": plan["assurance_boundary"]["complete_typed_execution_bundle"],
    "eligible_digest_bound": validated.eligible_split_inventory_sha256 == eligible_digest,
    "outcome": analysis.outcome.value,
    "plan_id": plan["plan_id"],
}
expected = {
    "complete_E": False,
    "eligible_digest_bound": True,
    "outcome": "INSUFFICIENT_ELIGIBLE_G",
    "plan_id": "nmfa-selector-core-plan-v1",
}
if observed != expected:
    raise SystemExit("installed selector snapshot mismatch")
print(json.dumps(
    {"isolated_wheel_nmfa_selector": "source_free_component_validated"},
    sort_keys=True,
))
"""


def fail(message: str) -> Never:
    raise SystemExit(f"NMFA selector installed-distribution verification failed: {message}")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode_json(raw: bytes, label: str):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"NMFA selector installed-distribution verification failed: invalid {label}"
        ) from error


def regular_member(archive: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
    matching = [member for member in archive.infolist() if member.filename == name]
    if len(matching) != 1 or not stat.S_ISREG(matching[0].external_attr >> 16):
        fail("required regular wheel member absent or duplicated")
    return matching[0]


def metadata_preserves_exact_requirements(metadata: str, expected: tuple[str, ...]) -> bool:
    """Require exact bound dependencies while allowing unrelated extras."""

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
    if set(bundle) != {
        "bundle_id",
        "created_at",
        "files",
        "format_version",
        "runtime_profile",
        "security_boundary",
    }:
        fail("evaluator bundle surface is not closed")
    if (
        bundle["created_at"] != "2026-08-02T15:50:25Z"
        or bundle["runtime_profile"].get("dependency_scope")
        != "direct_declared_requirement_only_runtime_environment_not_attested"
        or bundle["runtime_profile"].get("dependency_requirement") != "jsonschema[format]==4.26.0"
        or any(bundle["security_boundary"].values())
    ):
        fail("evaluator bundle runtime or assurance profile mismatch")

    with zipfile.ZipFile(wheel) as archive:
        names = [member.filename for member in archive.infolist()]
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
            decoded["schemas/nmfa-selector-core-plan.schema.json"],
            format_checker=FormatChecker(),
        )
        if (
            next(
                validator.iter_errors(decoded["benchmark/nmfa-selector-core-plan-v1.json"]),
                None,
            )
            is not None
        ):
            fail("packaged selector plan/schema mismatch")

        metadata_members = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_members) != 1:
            fail("wheel metadata absent or duplicated")
        metadata = archive.read(metadata_members[0]).decode("utf-8")
        exact_requirements = (bundle["runtime_profile"]["dependency_requirement"],)
        if not metadata_preserves_exact_requirements(metadata, exact_requirements):
            fail("wheel metadata lacks exact evaluator dependency commitment")

        previous_umask = os.umask(0o022)
        try:
            with tempfile.TemporaryDirectory(prefix="indus-nmfa-selector-wheel-") as raw_dir:
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
        fail("isolated wheel loader rejected selector resources")
    expected_stdout = json.dumps(
        {"isolated_wheel_nmfa_selector": "source_free_component_validated"},
        sort_keys=True,
    )
    if completed.stdout.strip() != expected_stdout or completed.stderr:
        fail("isolated wheel loader emitted unexpected output")


def main() -> None:
    if len(sys.argv) != 2:
        fail("exactly one wheel path is required")
    verify(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    main()
