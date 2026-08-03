"""Verify the source-free NMFA measurement core from one built wheel."""

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
BUNDLE_PATH = "benchmark/nmfa-measurement-core-evaluator-bundle-v1.json"
EXPECTED_BUNDLE_BYTES = 5876
EXPECTED_BUNDLE_SHA256 = "c1b8d41cf6acc7edca9b9e0f0381fe309a2b862020d185d44b0df4f294e8ff12"
EXPECTED_PLAN_SHA256 = "sha256:d7907ec8e9edbdd04e2904c8fc28007facf27c177e33994df20472025567e267"

WHEEL_PATH_BY_BUNDLE_PATH = {
    "benchmark/nmfa-measurement-core-plan-v1.json": (
        "indusbench/benchmark/nmfa-measurement-core-plan-v1.json"
    ),
    "benchmark/nmfa-selector-core-evaluator-bundle-v1.json": (
        "indusbench/benchmark/nmfa-selector-core-evaluator-bundle-v1.json"
    ),
    "benchmark/nmfa-selector-core-plan-v1.json": (
        "indusbench/benchmark/nmfa-selector-core-plan-v1.json"
    ),
    "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json": (
        "indusbench/benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
    ),
    "benchmark/numeral-metrology-functional-anchor-protocol-v1.json": (
        "indusbench/benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
    ),
    "schemas/nmfa-gf-roster.schema.json": "indusbench/schemas/nmfa-gf-roster.schema.json",
    "schemas/nmfa-measurement-core-plan.schema.json": (
        "indusbench/schemas/nmfa-measurement-core-plan.schema.json"
    ),
    "schemas/nmfa-metric-receipt.schema.json": (
        "indusbench/schemas/nmfa-metric-receipt.schema.json"
    ),
    "schemas/nmfa-metric-roster.schema.json": ("indusbench/schemas/nmfa-metric-roster.schema.json"),
    "schemas/nmfa-score-receipt.schema.json": ("indusbench/schemas/nmfa-score-receipt.schema.json"),
    "schemas/nmfa-target-receipt.schema.json": (
        "indusbench/schemas/nmfa-target-receipt.schema.json"
    ),
    "schemas/nmfa-x-batch.schema.json": "indusbench/schemas/nmfa-x-batch.schema.json",
    "schemas/nmfa-y-batch.schema.json": "indusbench/schemas/nmfa-y-batch.schema.json",
    "src/indusbench/io.py": "indusbench/io.py",
    "src/indusbench/nmfa_measurement_common.py": "indusbench/nmfa_measurement_common.py",
    "src/indusbench/nmfa_rank_statistics_core.py": ("indusbench/nmfa_rank_statistics_core.py"),
    "src/indusbench/nmfa_x_model_core.py": "indusbench/nmfa_x_model_core.py",
    "src/indusbench/nmfa_y_rational_core.py": "indusbench/nmfa_y_rational_core.py",
}

_ISOLATED_PROGRAM = r"""
import hashlib
import json
import os
import pathlib
import sys

wheel_root = pathlib.Path(sys.argv[1]).resolve()
expected_plan_sha256 = sys.argv[2]
sys.path.insert(0, str(wheel_root))

write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
write_events = {
    "os.mkdir", "os.remove", "os.rename", "os.renames", "os.replace",
    "os.rmdir", "os.symlink", "os.truncate", "os.unlink",
}

def deny_external_effects(event, args):
    if event.startswith("socket.") or event in write_events or event == "os.urandom":
        raise RuntimeError("external effect forbidden")
    if event == "open":
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        if (isinstance(mode, str) and any(character in mode for character in "wax+")) or (
            isinstance(flags, int) and flags & write_flags
        ):
            raise RuntimeError("file write forbidden")

sys.addaudithook(deny_external_effects)

import indusbench
from indusbench.io import encode_json
from indusbench.nmfa_measurement_common import load_installed_nmfa_measurement_plan
from indusbench.nmfa_rank_statistics_core import (
    evaluate_nmfa_rank_metrics,
    exact_nmfa_spearman_at_least,
    verify_nmfa_metric_receipt,
)
from indusbench.nmfa_x_model_core import score_nmfa_x_batch, verify_nmfa_score_receipt
from indusbench.nmfa_y_rational_core import normalize_nmfa_y_batch, verify_nmfa_target_receipt

package_file = pathlib.Path(indusbench.__file__).resolve()
if not package_file.is_relative_to(wheel_root):
    raise SystemExit("source checkout shadowed extracted wheel")

plan = load_installed_nmfa_measurement_plan()
raw_plan = (
    wheel_root / "indusbench" / "benchmark" / "nmfa-measurement-core-plan-v1.json"
).read_bytes()
if "sha256:" + hashlib.sha256(raw_plan).hexdigest() != expected_plan_sha256:
    raise SystemExit("installed measurement plan digest mismatch")

def sha256(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def domain_digest(domain, value):
    return sha256(domain + encode_json(value))

def opaque(label):
    return "hmac-sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()

def registry_id(label):
    return "registry-id:" + hashlib.sha256(label.encode("ascii")).hexdigest()

def checksum(label):
    return "sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()

bindings = plan["bindings"]
claim_binding = {
    "claim_family_id": registry_id("wheel-family"),
    "claim_slot_id": registry_id("wheel-slot"),
    "experiment_instance_id": registry_id("wheel-instance"),
    "predecessor_chain_head_sha256": checksum("wheel-chain"),
}
rows = [
    {
        "g_id": "sha256:" + f"{index + 1:064x}",
        "primary_f_id": "hmac-sha256:" + f"{index + 1:064x}",
    }
    for index in range(160)
]
roster = {
    "claim_binding": claim_binding,
    "format_version": "1.0.0",
    "gate_plan_sha256": bindings["gate_plan_sha256"],
    "measurement_plan_sha256": expected_plan_sha256,
    "parent_protocol_sha256": bindings["parent_protocol_sha256"],
    "record_kind": "nmfa_gf_roster",
    "rows": rows,
    "selector_assignment_raw_sha256": checksum("wheel-selector-assignment"),
    "selector_plan_sha256": bindings["selector_plan_sha256"],
}
roster_raw = encode_json(roster)
roster_raw_sha256 = sha256(roster_raw)
roster_sha256 = domain_digest(
    b"indusbench:nmfa:assignment-roster:v1\x00", {"rows": rows}
)
metric_roster = {
    "assignment_roster_raw_sha256": roster_raw_sha256,
    "assignment_roster_sha256": roster_sha256,
    "claim_binding": claim_binding,
    "format_version": "1.0.0",
    "measurement_plan_sha256": expected_plan_sha256,
    "record_kind": "nmfa_metric_roster",
    "rows": rows[:4],
    "selector_assignment_raw_sha256": roster["selector_assignment_raw_sha256"],
}
metric_roster_raw = encode_json(metric_roster)
metric_roster_raw_sha256 = sha256(metric_roster_raw)

tokens = {name: opaque(name) for name in ("a1", "a2", "b", "c")}
classes = [
    {
        "class_id": domain_digest(
            b"indusbench:nmfa:model-class:v1\x00",
            {"member_token_ids": sorted([tokens["a1"], tokens["a2"]])},
        ),
        "member_token_ids": sorted([tokens["a1"], tokens["a2"]]),
        "weight": 2,
    },
    {
        "class_id": domain_digest(
            b"indusbench:nmfa:model-class:v1\x00", {"member_token_ids": [tokens["b"]]}
        ),
        "member_token_ids": [tokens["b"]],
        "weight": 1,
    },
]
classes.sort(key=lambda row: row["class_id"])
model = {
    "classes": classes,
    "policy_commitments": {
        "allograph_policy_sha256": checksum("wheel-allograph-policy"),
        "damage_policy_sha256": checksum("wheel-damage-policy"),
        "direction_policy_sha256": checksum("wheel-direction-policy"),
        "length_identity_policy_sha256": checksum("wheel-length-policy"),
        "segmentation_policy_sha256": checksum("wheel-segmentation-policy"),
        "surface_order_policy_sha256": checksum("wheel-surface-policy"),
    },
}
token_vectors = [
    [tokens["c"]],
    [tokens["c"], tokens["c"]],
    [tokens["b"]],
    [tokens["a1"]],
] + [[tokens["c"]] for _ in rows[4:]]
x_units = []
for index, (row, identities) in enumerate(zip(rows, token_vectors, strict=True)):
    x_units.append({
        "all_sides_complete_declared": True,
        "g_id": row["g_id"],
        "primary_f_id": row["primary_f_id"],
        "sides": [{
            "lines": [{
                "line_id": opaque(f"wheel-line-{index}"),
                "line_index": 0,
                "tokens": [
                    {
                        "disposition": "included",
                        "length_identity_id": identity,
                        "scoring_identity_id": identity,
                        "token_index": token_index,
                    }
                    for token_index, identity in enumerate(identities)
                ],
            }],
            "side_id": opaque(f"wheel-side-{index}"),
            "side_index": 0,
        }],
        "source_binding_sha256": checksum(f"wheel-x-source-{index}"),
    })
x_batch = {
    "assignment_roster_sha256": roster_sha256,
    "claim_binding": claim_binding,
    "format_version": "1.0.0",
    "gate_plan_sha256": bindings["gate_plan_sha256"],
    "measurement_plan_sha256": expected_plan_sha256,
    "model": model,
    "parent_protocol_sha256": bindings["parent_protocol_sha256"],
    "record_kind": "nmfa_x_model_batch",
    "selector_assignment_raw_sha256": roster["selector_assignment_raw_sha256"],
    "selector_plan_sha256": bindings["selector_plan_sha256"],
    "units": x_units,
}
x_batch_raw = encode_json(x_batch)
model_sha256 = domain_digest(b"indusbench:nmfa:x-model:v1\x00", model)

canonical_unit_id = opaque("wheel-canonical-unit")
target_contract = {
    "canonical_unit_id": canonical_unit_id,
    "conversions": [{
        "multiplier": {"denominator": 1, "numerator": 1},
        "source_unit_id": canonical_unit_id,
    }],
    "policy_commitments": {
        "canonical_unit_conversion_policy_sha256": checksum("wheel-conversion-policy"),
        "measurement_policy_sha256": checksum("wheel-measurement-policy"),
        "repeated_measurement_resolution_policy_sha256": checksum("wheel-repeat-policy"),
    },
    "target_family": "direct_count",
}
y_targets = (0, 1, 1, 2) + (0,) * (len(rows) - 4)
y_units = [
    {
        "g_id": row["g_id"],
        "primary_f_id": row["primary_f_id"],
        "source_binding_sha256": checksum(f"wheel-y-source-{index}"),
        "source_unit_id": canonical_unit_id,
        "source_value": {"denominator": 1, "numerator": target},
    }
    for index, (row, target) in enumerate(zip(rows, y_targets, strict=True))
]
y_batch = {
    "assignment_roster_sha256": roster_sha256,
    "claim_binding": claim_binding,
    "format_version": "1.0.0",
    "gate_plan_sha256": bindings["gate_plan_sha256"],
    "measurement_plan_sha256": expected_plan_sha256,
    "parent_protocol_sha256": bindings["parent_protocol_sha256"],
    "record_kind": "nmfa_y_target_batch",
    "selector_assignment_raw_sha256": roster["selector_assignment_raw_sha256"],
    "selector_plan_sha256": bindings["selector_plan_sha256"],
    "target_contract": target_contract,
    "units": y_units,
}
y_batch_raw = encode_json(y_batch)
target_contract_sha256 = domain_digest(
    b"indusbench:nmfa:target-contract:v1\x00", target_contract
)

score = score_nmfa_x_batch(
    roster_raw, roster_raw_sha256, x_batch_raw, sha256(x_batch_raw), model_sha256
)
target = normalize_nmfa_y_batch(
    roster_raw,
    roster_raw_sha256,
    y_batch_raw,
    sha256(y_batch_raw),
    target_contract_sha256,
)
metric = evaluate_nmfa_rank_metrics(
    roster_raw,
    roster_raw_sha256,
    metric_roster_raw,
    metric_roster_raw_sha256,
    score.receipt_bytes,
    score.receipt_raw_sha256,
    target.receipt_bytes,
    target.receipt_raw_sha256,
)
verify_nmfa_score_receipt(
    roster_raw,
    roster_raw_sha256,
    x_batch_raw,
    sha256(x_batch_raw),
    model_sha256,
    score.receipt_bytes,
)
verify_nmfa_target_receipt(
    roster_raw,
    roster_raw_sha256,
    y_batch_raw,
    sha256(y_batch_raw),
    target_contract_sha256,
    target.receipt_bytes,
)
verify_nmfa_metric_receipt(
    roster_raw,
    roster_raw_sha256,
    metric_roster_raw,
    metric_roster_raw_sha256,
    score.receipt_bytes,
    score.receipt_raw_sha256,
    target.receipt_bytes,
    target.receipt_raw_sha256,
    metric.receipt_bytes,
)

score_value = score.receipt()
target_value = target.receipt()
metric_value = metric.receipt()
primary = metric_value["metrics"]["score_vs_target"]
observed = {
    "complete_E": plan["assurance_boundary"]["complete_typed_execution_bundle"],
    "metric_has_rows": "rows" in metric_value,
    "primary_c": primary["covariance_c"],
    "primary_q12": primary["rho_scaled_1e12"],
    "score": [row["score"] for row in score_value["rows"][:4]],
    "target": [row["canonical_value"]["numerator"] for row in target_value["rows"][:4]],
    "threshold_collapse_rejected": not exact_nmfa_spearman_at_least(
        799_999_999_999, 1, 4 * 10**24, 2, 5
    ),
}
expected = {
    "complete_E": False,
    "metric_has_rows": False,
    "primary_c": "60",
    "primary_q12": 833333333333,
    "score": [0, 0, 1, 2],
    "target": ["0", "1", "1", "2"],
    "threshold_collapse_rejected": True,
}
if observed != expected:
    raise SystemExit("installed measurement core snapshot mismatch")
if any(token.encode("ascii") in score.receipt_bytes for token in tokens.values()):
    raise SystemExit("score receipt leaked token identity")
if canonical_unit_id.encode("ascii") in metric.receipt_bytes:
    raise SystemExit("metric receipt leaked canonical unit identity")
print(json.dumps(
    {"isolated_wheel_nmfa_measurement": "source_free_exact_core_validated"},
    sort_keys=True,
))
"""


def fail(message: str) -> Never:
    raise SystemExit(f"NMFA measurement installed-distribution verification failed: {message}")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode_json(raw: bytes, label: str):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"NMFA measurement installed-distribution verification failed: invalid {label}"
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
        bundle["bundle_id"] != "nmfa-measurement-core-evaluator-bundle-v1"
        or bundle["created_at"] != "2026-08-03T01:10:01Z"
        or bundle["format_version"] != "1.0.0"
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
        rows = bundle["files"]
        if (
            type(rows) is not list
            or [row.get("path") for row in rows] != sorted(WHEEL_PATH_BY_BUNDLE_PATH)
            or len(rows) != len(WHEEL_PATH_BY_BUNDLE_PATH)
        ):
            fail("evaluator bundle file roster mismatch")
        for row in rows:
            if set(row) != {"bytes", "path", "sha256", "verification"}:
                fail("evaluator bundle file row surface is not closed")
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
            decoded["schemas/nmfa-measurement-core-plan.schema.json"],
            format_checker=FormatChecker(),
        )
        plan = decoded["benchmark/nmfa-measurement-core-plan-v1.json"]
        if next(validator.iter_errors(plan), None) is not None:
            fail("packaged measurement plan/schema mismatch")

        metadata_members = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_members) != 1:
            fail("wheel metadata absent or duplicated")
        metadata = archive.read(metadata_members[0]).decode("utf-8")
        exact_requirements = (bundle["runtime_profile"]["dependency_requirement"],)
        if not metadata_preserves_exact_requirements(metadata, exact_requirements):
            fail("wheel metadata lacks exact evaluator dependency commitment")

        previous_umask = os.umask(0o022)
        try:
            with tempfile.TemporaryDirectory(prefix="indus-nmfa-measurement-wheel-") as raw_dir:
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
        fail("isolated wheel loader rejected measurement resources")
    expected_stdout = json.dumps(
        {"isolated_wheel_nmfa_measurement": "source_free_exact_core_validated"},
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
