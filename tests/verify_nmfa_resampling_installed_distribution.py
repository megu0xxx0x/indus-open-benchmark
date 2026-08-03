"""Verify the source-free NMFA resampling core from one built wheel."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Any, Never

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = "benchmark/nmfa-resampling-core-evaluator-bundle-v1.json"

EXPECTED_BUNDLE_BYTES = 6082
EXPECTED_BUNDLE_SHA256 = "cb428e75a6c82d5d052bd8070eedd5f75ac9c26de2ba6dd532c3f73182b2adee"

WHEEL_PATH_BY_BUNDLE_PATH = {
    "benchmark/nmfa-measurement-core-evaluator-bundle-v1.json": (
        "indusbench/benchmark/nmfa-measurement-core-evaluator-bundle-v1.json"
    ),
    "benchmark/nmfa-measurement-core-plan-v1.json": (
        "indusbench/benchmark/nmfa-measurement-core-plan-v1.json"
    ),
    "benchmark/nmfa-resampling-core-plan-v1.json": (
        "indusbench/benchmark/nmfa-resampling-core-plan-v1.json"
    ),
    "benchmark/nmfa-selector-core-evaluator-bundle-v1.json": (
        "indusbench/benchmark/nmfa-selector-core-evaluator-bundle-v1.json"
    ),
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
    "schemas/nmfa-bootstrap-receipt.schema.json": (
        "indusbench/schemas/nmfa-bootstrap-receipt.schema.json"
    ),
    "schemas/nmfa-resampling-core-plan.schema.json": (
        "indusbench/schemas/nmfa-resampling-core-plan.schema.json"
    ),
    "schemas/nmfa-selector-receipt.schema.json": (
        "indusbench/schemas/nmfa-selector-receipt.schema.json"
    ),
    "src/indusbench/io.py": "indusbench/io.py",
    "src/indusbench/nmfa_bootstrap_core.py": "indusbench/nmfa_bootstrap_core.py",
    "src/indusbench/nmfa_counter_stream.py": "indusbench/nmfa_counter_stream.py",
    "src/indusbench/nmfa_exact_order.py": "indusbench/nmfa_exact_order.py",
    "src/indusbench/nmfa_measurement_common.py": ("indusbench/nmfa_measurement_common.py"),
    "src/indusbench/nmfa_rank_statistics_core.py": ("indusbench/nmfa_rank_statistics_core.py"),
    "src/indusbench/nmfa_resampling_common.py": ("indusbench/nmfa_resampling_common.py"),
    "src/indusbench/nmfa_x_model_core.py": "indusbench/nmfa_x_model_core.py",
    "src/indusbench/nmfa_y_rational_core.py": "indusbench/nmfa_y_rational_core.py",
}

EXPECTED_RUNTIME_PROFILE = {
    "canonical_encoder": "indusbench.io:encode_json",
    "dependencies": {"jsonschema": "4.26.0"},
    "dependency_requirement": "jsonschema[format]==4.26.0",
    "dependency_scope": ("direct_declared_requirement_only_runtime_environment_not_attested"),
    "entrypoints": [
        "indusbench.nmfa_resampling_common:load_installed_nmfa_resampling_plan",
        "indusbench.nmfa_counter_stream:nmfa_hmac_counter_block",
        "indusbench.nmfa_counter_stream:NMFACounterStream",
        "indusbench.nmfa_exact_order:compare_exact_rho",
        "indusbench.nmfa_exact_order:compare_exact_paired_delta",
        "indusbench.nmfa_bootstrap_core:evaluate_nmfa_paired_bootstrap",
        "indusbench.nmfa_bootstrap_core:verify_nmfa_bootstrap_receipt",
    ],
    "implementation": "CPython",
    "integer_arithmetic": "exact_bounded_integer_and_fraction_intermediates",
    "supported_python_minors": ["3.11", "3.12", "3.13", "3.14"],
}

EXPECTED_SECURITY_BOUNDARY = {
    "activation_or_source_authority_included": False,
    "complete_execution_bundle": False,
    "external_chain_head_or_receipt_origin_verified": False,
    "network_clock_random_or_file_write_used": False,
    "protected_input_or_receipt_included": False,
    "real_source_or_target_values_included": False,
    "runtime_environment_attested": False,
    "scientific_result": False,
}

_ISOLATED_PROGRAM = r"""
import hashlib
import json
import os
import pathlib
import sys

wheel_root = pathlib.Path(sys.argv[1]).resolve()
expected_plan_sha256 = sys.argv[2]
expected_bundle_sha256 = sys.argv[3]
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
import indusbench.nmfa_bootstrap_core as bootstrap_core
import indusbench.nmfa_counter_stream as counter_core
import indusbench.nmfa_exact_order as exact_core
import indusbench.nmfa_resampling_common as resampling_common
from indusbench.nmfa_bootstrap_core import (
    _BootstrapRow,
    _evaluate_runs,
    _schedule_hasher,
    evaluate_nmfa_paired_bootstrap,
    verify_nmfa_bootstrap_receipt,
)
from indusbench.nmfa_counter_stream import NMFACounterStream, nmfa_hmac_counter_block
from indusbench.nmfa_exact_order import (
    ExactRho,
    compare_exact_paired_delta,
    compare_exact_rho,
    make_exact_paired_delta,
)
from indusbench.nmfa_resampling_common import load_installed_nmfa_resampling_plan
from indusbench.nmfa_y_rational_core import CanonicalRational

plan = load_installed_nmfa_resampling_plan()
plan_path = (
    wheel_root / "indusbench" / "benchmark" / "nmfa-resampling-core-plan-v1.json"
)
bundle_path = (
    wheel_root
    / "indusbench"
    / "benchmark"
    / "nmfa-resampling-core-evaluator-bundle-v1.json"
)
if "sha256:" + hashlib.sha256(plan_path.read_bytes()).hexdigest() != expected_plan_sha256:
    raise SystemExit("installed resampling plan digest mismatch")
if "sha256:" + hashlib.sha256(bundle_path.read_bytes()).hexdigest() != expected_bundle_sha256:
    raise SystemExit("installed resampling bundle digest mismatch")
if plan["plan_id"] != "nmfa-resampling-core-plan-v1":
    raise SystemExit("installed resampling plan identity mismatch")
if plan["assurance_boundary"]["scientific_result"] is not False:
    raise SystemExit("installed resampling assurance boundary mismatch")
if not callable(evaluate_nmfa_paired_bootstrap) or not callable(
    verify_nmfa_bootstrap_receipt
):
    raise SystemExit("installed public bootstrap entrypoint absent")

expected_blocks = {
    "bootstrap-v1": "796035efff9fa84895ee049e6aaaca77666e2972cce850da3fdd951f8b22bdc9",
    "control-n1-v1": "bdf831d83dd0388424ddf3caebff8f92826c5c3e725a2fe1a46e587863669335",
    "null-n2-v1": "a616fc573b1c3a9b436db069b82b90b5cbfad6a75b1f18a9c3cb228e1216c9ff",
}
plan_blocks = {
    row["label"]: row["block_hex"]
    for row in plan["fixed_vectors"]["counter_blocks_zero_key"]
}
if plan_blocks != expected_blocks:
    raise SystemExit("installed counter plan vector mismatch")
for label, expected in expected_blocks.items():
    if nmfa_hmac_counter_block(bytes(32), label, 0, 0).hex() != expected:
        raise SystemExit("installed counter block mismatch")
stream = NMFACounterStream(bytes(32), "bootstrap-v1", 0)
if stream.draw_index(1) != 0 or stream.stats().blocks_generated != 0:
    raise SystemExit("unit bound consumed an installed counter block")
if stream.draw_index(10) != 7:
    raise SystemExit("installed rejection sampler vector mismatch")
stats = stream.stats()
if (stats.draws, stats.blocks_generated, stats.rejected_blocks, stats.next_counter) != (
    2, 1, 0, 1
):
    raise SystemExit("installed counter accounting mismatch")

one_over_sqrt_two = ExactRho.defined(1, 2)
two_over_sqrt_eight = ExactRho.defined(2, 8)
if compare_exact_rho(one_over_sqrt_two, two_over_sqrt_eight) != 0:
    raise SystemExit("installed exact scaled-radicand equality mismatch")
zero = ExactRho.sentinel(0)
left_delta = make_exact_paired_delta(
    one_over_sqrt_two,
    ExactRho.defined(1, 3),
    zero,
)
right_delta = make_exact_paired_delta(
    ExactRho.defined(1, 3),
    ExactRho.defined(1, 5),
    zero,
)
if compare_exact_paired_delta(left_delta, right_delta) >= 0:
    raise SystemExit("installed exact paired-delta ordering mismatch")

schedule_vector = plan["fixed_vectors"]["bootstrap_schedule"]
cell_roster_sha256 = resampling_common._domain_digest(
    resampling_common._CELL_ROSTER_DOMAIN,
    {"rows": schedule_vector["cell_roster_rows"]},
)
if cell_roster_sha256 != (
    "sha256:" + schedule_vector["expected_cell_roster_sha256_hex"]
):
    raise SystemExit("installed bootstrap cell-roster vector mismatch")
schedule_key = bytes.fromhex(
    schedule_vector["frozen_protocol_chain_head_sha256_hex"]
)
accepted_indices = []
for run_index in range(schedule_vector["run_count"]):
    schedule_stream = NMFACounterStream(schedule_key, "bootstrap-v1", run_index)
    for cell_size in schedule_vector["cell_sizes"]:
        accepted_indices.extend(
            schedule_stream.draw_index(cell_size) for _ in range(cell_size)
        )
if accepted_indices != schedule_vector["accepted_local_indices"]:
    raise SystemExit("installed bootstrap accepted-index vector mismatch")
hasher = _schedule_hasher(
    cell_roster_sha256,
    schedule_key,
    schedule_vector["run_count"],
    tuple(schedule_vector["cell_sizes"]),
)
for local_index in accepted_indices:
    hasher.update(local_index.to_bytes(8, "big"))
if hasher.hexdigest() != schedule_vector["expected_schedule_sha256_hex"]:
    raise SystemExit("installed bootstrap schedule vector mismatch")

axes = ("site", "period", "medium", "object_type")
cells = {}
for cell_index, axis in enumerate(axes):
    rows = []
    for local_index in range(20):
        value = cell_index * 100 + local_index
        rows.append(
            _BootstrapRow(
                g_id=f"sha256:{value:064x}",
                primary_f_id=f"hmac-sha256:{value:064x}",
                score=value,
                l_total=value + 10_000,
                l_distinct=value + 20_000,
                target=CanonicalRational(value + 1, 1),
            )
        )
    cells[axis] = tuple(rows)
bootstrap, endpoints = _evaluate_runs(
    cells,
    b"\x03" * 32,
    "sha256:" + "4" * 64,
    10_000,
    249,
)
expected_bootstrap = {
    "cell_order": list(axes),
    "cell_roster_sha256": "sha256:" + "4" * 64,
    "cell_sizes": {axis: 20 for axis in axes},
    "counter": {
        "maximum_blocks_generated_per_run": 80,
        "total_blocks_generated": 800_000,
        "total_draws": 800_000,
        "total_rejected_blocks": 0,
    },
    "discarded_runs": 0,
    "draws_per_run": 80,
    "holdout_units": 80,
    "length_maximum_selections": {
        "zero": 0,
        "l_total": 10_000,
        "l_distinct": 0,
    },
    "redrawn_runs": 0,
    "run_count": 10_000,
    "schedule_sha256": (
        "sha256:c96caee6d779215ec7fee349e66ea8f92bcd3834e80a52d845ad0cf1e2312006"
    ),
    "substitutions": {
        "candidate_to_negative_one": 0,
        "l_distinct_to_zero": 0,
        "l_total_to_zero": 0,
    },
}
endpoint_rho = {
    "covariance_c": "13642560",
    "denominator_radicand": "186119443353600",
    "kind": "defined",
}
expected_endpoints = {
    "candidate_rho_lower": {"rho": endpoint_rho, "run_index": 249},
    "lower_index_zero_based": 249,
    "lower_order_one_based": 250,
    "paired_delta_lower": {
        "length_maximum": {"rho": endpoint_rho, "source": "l_total"},
        "primary_rho": endpoint_rho,
        "run_index": 249,
    },
}
if bootstrap != expected_bootstrap or endpoints != expected_endpoints:
    raise SystemExit("installed ten-thousand-run bootstrap snapshot mismatch")

for name, module in tuple(sys.modules.items()):
    if name != "indusbench" and not name.startswith("indusbench."):
        continue
    module_file = getattr(module, "__file__", None)
    if module_file is not None and not pathlib.Path(module_file).resolve().is_relative_to(
        wheel_root
    ):
        raise SystemExit("source checkout shadowed extracted wheel")
for module in (
    indusbench,
    bootstrap_core,
    counter_core,
    exact_core,
    resampling_common,
):
    if not pathlib.Path(module.__file__).resolve().is_relative_to(wheel_root):
        raise SystemExit("source checkout shadowed extracted wheel")

print(json.dumps(
    {"isolated_wheel_nmfa_resampling": "source_free_exact_bootstrap_validated"},
    sort_keys=True,
))
"""


def fail(message: str) -> Never:
    raise SystemExit(f"NMFA resampling installed-distribution verification failed: {message}")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = child
    return value


def decode_json(raw: bytes, label: str) -> Any:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non-finite JSON number")
            ),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"NMFA resampling installed-distribution verification failed: invalid {label}"
        ) from error
    return value


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise SystemExit(
            "NMFA resampling installed-distribution verification failed: non-canonical JSON value"
        ) from error


def safe_member_name(name: str) -> bool:
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or unicodedata.normalize("NFC", name) != name
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        return False
    segments = name.split("/")
    parsed = PurePosixPath(name)
    return (
        not parsed.is_absolute()
        and all(segment not in {"", ".", ".."} for segment in segments)
        and ":" not in segments[0]
    )


def regular_file_mode(member: zipfile.ZipInfo) -> bool:
    """Accept an explicit regular type or Hatch's permission-only metadata mode."""

    mode = member.external_attr >> 16
    return stat.S_ISREG(mode) or (stat.S_IFMT(mode) == 0 and not member.is_dir())


def regular_member(archive: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
    matching = [member for member in archive.infolist() if member.filename == name]
    if len(matching) != 1 or not regular_file_mode(matching[0]) or matching[0].flag_bits & 0x1:
        fail("required regular wheel member absent, duplicated, encrypted, or special")
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


def verify_record(archive: zipfile.ZipFile, names: list[str]) -> str:
    record_names = [name for name in names if name.endswith(".dist-info/RECORD")]
    if len(record_names) != 1:
        fail("wheel RECORD absent or duplicated")
    record_name = record_names[0]
    raw = archive.read(regular_member(archive, record_name))
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))
    except (csv.Error, UnicodeError) as error:
        raise SystemExit(
            "NMFA resampling installed-distribution verification failed: invalid RECORD"
        ) from error
    if any(len(row) != 3 for row in rows):
        fail("wheel RECORD row surface mismatch")
    paths = [row[0] for row in rows]
    if (
        len(paths) != len(set(paths))
        or set(paths) != set(names)
        or any(not safe_member_name(path) for path in paths)
    ):
        fail("wheel RECORD inventory mismatch")
    by_path = {row[0]: row[1:] for row in rows}
    if by_path[record_name] != ["", ""]:
        fail("wheel RECORD self-row must omit hash and size")
    for name in names:
        if name == record_name:
            continue
        member_raw = archive.read(regular_member(archive, name))
        encoded = base64.urlsafe_b64encode(hashlib.sha256(member_raw).digest()).rstrip(b"=")
        if by_path[name] != [f"sha256={encoded.decode('ascii')}", str(len(member_raw))]:
            fail("wheel RECORD hash or size mismatch")
    return record_name.rsplit("/", 1)[0]


def verify(wheel: Path) -> None:
    if not wheel.is_file() or wheel.suffix != ".whl":
        fail("exactly one wheel path is required")
    try:
        bundle_raw = (ROOT / BUNDLE_PATH).read_bytes()
    except OSError as error:
        raise SystemExit(
            "NMFA resampling installed-distribution verification failed: "
            "repository evaluator bundle absent"
        ) from error
    if len(bundle_raw) != EXPECTED_BUNDLE_BYTES:
        fail("repository evaluator bundle byte count is not frozen")
    if sha256(bundle_raw) != EXPECTED_BUNDLE_SHA256:
        fail("repository evaluator bundle digest is not frozen")
    bundle = decode_json(bundle_raw, BUNDLE_PATH)
    if canonical_json_bytes(bundle) != bundle_raw:
        fail("repository evaluator bundle is not canonical JSON")
    if type(bundle) is not dict or set(bundle) != {
        "bundle_id",
        "created_at",
        "files",
        "format_version",
        "runtime_profile",
        "security_boundary",
    }:
        fail("evaluator bundle surface is not closed")
    if (
        bundle["bundle_id"] != "nmfa-resampling-core-evaluator-bundle-v1"
        or bundle["created_at"] != "2026-08-03T12:18:41Z"
        or bundle["format_version"] != "1.0.0"
        or bundle["runtime_profile"] != EXPECTED_RUNTIME_PROFILE
        or bundle["security_boundary"] != EXPECTED_SECURITY_BOUNDARY
    ):
        fail("evaluator bundle runtime or assurance profile mismatch")

    try:
        archive = zipfile.ZipFile(wheel)
    except (OSError, zipfile.BadZipFile) as error:
        raise SystemExit(
            "NMFA resampling installed-distribution verification failed: invalid wheel ZIP"
        ) from error
    with archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)) or len(names) != len({name.casefold() for name in names}):
            fail("duplicate or case-colliding wheel member")
        if any(not safe_member_name(name) for name in names):
            fail("unsafe wheel member path")
        if any(not regular_file_mode(member) or member.flag_bits & 0x1 for member in members):
            fail("wheel contains a directory, encrypted member, or special member")
        dist_info_dir = verify_record(archive, names)

        wheel_bundle = regular_member(archive, "indusbench/" + BUNDLE_PATH)
        if archive.read(wheel_bundle) != bundle_raw:
            fail("wheel/repository evaluator bundle mismatch")
        rows = bundle["files"]
        if (
            type(rows) is not list
            or len(rows) != len(WHEEL_PATH_BY_BUNDLE_PATH)
            or [row.get("path") if type(row) is dict else None for row in rows]
            != sorted(WHEEL_PATH_BY_BUNDLE_PATH)
        ):
            fail("evaluator bundle file roster mismatch")
        for row in rows:
            if type(row) is not dict or set(row) != {
                "bytes",
                "path",
                "sha256",
                "verification",
            }:
                fail("evaluator bundle file row surface is not closed")
            if row["verification"] != "runtime_and_ci":
                fail("unknown evaluator bundle verification policy")
            path = row["path"]
            if type(path) is not str or path not in WHEEL_PATH_BY_BUNDLE_PATH:
                fail("runtime file has no wheel mapping")
            try:
                repo_raw = (ROOT / path).read_bytes()
            except OSError as error:
                raise SystemExit(
                    "NMFA resampling installed-distribution verification failed: "
                    "bundle repository member absent"
                ) from error
            if (
                type(row["bytes"]) is not int
                or row["bytes"] < 1
                or len(repo_raw) != row["bytes"]
                or "sha256:" + sha256(repo_raw) != row["sha256"]
            ):
                fail("bundle/repository file commitment mismatch")
            wheel_name = WHEEL_PATH_BY_BUNDLE_PATH[path]
            if archive.read(regular_member(archive, wheel_name)) != repo_raw:
                fail("wheel/repository runtime file mismatch")

        decoded = {
            path: decode_json((ROOT / path).read_bytes(), path)
            for path in WHEEL_PATH_BY_BUNDLE_PATH
            if path.endswith(".json")
        }
        for path in (path for path in decoded if path.startswith("schemas/")):
            Draft202012Validator.check_schema(decoded[path])
        plan_path = "benchmark/nmfa-resampling-core-plan-v1.json"
        plan = decoded[plan_path]
        if canonical_json_bytes(plan) != (ROOT / plan_path).read_bytes():
            fail("resampling plan is not canonical JSON")
        validator = Draft202012Validator(
            decoded["schemas/nmfa-resampling-core-plan.schema.json"],
            format_checker=FormatChecker(),
        )
        if next(validator.iter_errors(plan), None) is not None:
            fail("packaged resampling plan/schema mismatch")
        if (
            plan.get("plan_id") != "nmfa-resampling-core-plan-v1"
            or plan.get("assurance_boundary", {}).get("scientific_result") is not False
            or plan.get("assurance_boundary", {}).get("prize_submission_eligible") is not False
        ):
            fail("resampling plan identity or assurance boundary mismatch")

        metadata_name = f"{dist_info_dir}/METADATA"
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if metadata_names != [metadata_name]:
            fail("wheel metadata absent, duplicated, or in a second dist-info directory")
        try:
            metadata = archive.read(regular_member(archive, metadata_name)).decode("utf-8")
        except UnicodeError as error:
            raise SystemExit(
                "NMFA resampling installed-distribution verification failed: invalid METADATA"
            ) from error
        exact_requirements = (bundle["runtime_profile"]["dependency_requirement"],)
        if not metadata_preserves_exact_requirements(metadata, exact_requirements):
            fail("wheel metadata lacks exact evaluator dependency commitment")
        wheel_name = f"{dist_info_dir}/WHEEL"
        wheel_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
        if wheel_names != [wheel_name]:
            fail("wheel descriptor absent, duplicated, or in a second dist-info directory")
        regular_member(archive, wheel_name)

        plan_row = next(row for row in rows if row["path"] == plan_path)
        bundle_sha256 = "sha256:" + sha256(bundle_raw)
        previous_umask = os.umask(0o022)
        try:
            with tempfile.TemporaryDirectory(prefix="indus-nmfa-resampling-wheel-") as raw_dir:
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
                        plan_row["sha256"],
                        bundle_sha256,
                    ],
                    cwd=empty_cwd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
        finally:
            os.umask(previous_umask)
    if completed.returncode != 0:
        fail("isolated wheel loader rejected resampling resources")
    expected_stdout = json.dumps(
        {"isolated_wheel_nmfa_resampling": "source_free_exact_bootstrap_validated"},
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
