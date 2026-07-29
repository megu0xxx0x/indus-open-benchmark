"""One-shot process runner for the frozen KP1979 V2 synthetic control.

The parent imports only the frozen control contract. The detector runs from
the separately built D wheel in a fresh child process for every input. No
case identity, truth, scorer state, or roster position crosses that boundary.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import pwd
import resource
import signal
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal, TypeAlias

from jsonschema import Draft202012Validator

import indusbench.kp1979_label_scoring as scoring_module
import indusbench.kp1979_synthetic_control_v2 as control_module
from indusbench.kp1979_synthetic_control_v2 import (
    CONTROL_ID,
    MAX_PREDICTIONS_PER_PROPOSAL,
    SyntheticControlReport,
    SyntheticDetectorInput,
    SyntheticDetectorProposal,
    SyntheticInputRejection,
    SyntheticPrediction,
    evaluate_frozen_synthetic_control,
    frozen_synthetic_control,
)

RUNNER_ID: Final = "kp1979-label-lattice-v2-one-shot-runner-v1"
PLAN_ID: Final = "kp1979-label-lattice-v2-execution-plan-v1"
RESULT_SCHEMA_ID: Final = "kp1979-label-lattice-v2-result-v1"
TARGET_ALGORITHM_ID: Final = "two-column-label-lattice-v2"
WORKER_INTERFACE_VERSION: Final = "kp1979-label-detector-v2-worker-v1"

BASE_COMMIT: Final = "662b01c23d4d4e2336e248d79bc508c3b7ed5f66"
CONTROL_COMMIT: Final = "e143a5ed5a8128d7b7e3626a3bf01607289ee7cc"
DETECTOR_COMMIT: Final = "5f059032ed9ee1e790c4c668047510f8e1cd60d5"
DETECTOR_WHEEL_SHA256: Final = "7861a7e435d8221ac9c95a12e232c988533bba9c803b30f470384d2e9476a5cb"
CONTROL_MODULE_SHA256: Final = "7674968043476cc366cf7f0a73daf588d4cea8695a3c6fd368bf1c3d730ebab9"
CONTROL_MANIFEST_SHA256: Final = "ee368613138f2ccb89686872ff127504f0627b2df662edef3b5a0486583f870f"
WORKER_MODULE_SHA256: Final = "4405774a8c544da5d09eb313025b40757ddfe6acc12dfa5013406e3c3f5326c4"
DETECTOR_MODULE_SHA256: Final = "2540310dad612080034ab89f37cff96ce3341d1fc93d2fa44c0c86a78ccd66a4"
SCORER_MODULE_SHA256: Final = "56bdcfe869f96e043acadabe44d839bce97891b5c1eb81604e72874fce4b48ba"
UV_LOCK_SHA256: Final = "d916009109bb939157fe248d613398ddc21735871704117dfa1ea1e00b7c2443"
EXPECTED_ORIGIN_URL: Final = "ssh://git@ssh.github.com:443/megu0xxx0x/indus-open-benchmark.git"
GIT_EXECUTABLE: Final = Path("/usr/bin/git")

EXECUTION_PLAN_PATH: Final = Path(
    "benchmark/kp1979-label-lattice-synthetic-control-v2-execution-v1.json"
)
EXECUTION_SCHEMA_PATH: Final = Path(
    "schemas/kp1979-label-lattice-synthetic-control-v2-execution.schema.json"
)
RESULT_SCHEMA_PATH: Final = Path(
    "schemas/kp1979-label-lattice-synthetic-control-v2-result.schema.json"
)

FRESH_PROCESS_COUNT: Final = 25
CONTROL_BEFORE_DETECTOR_FREEZE: Final = False
POSTFREEZE_PERIODIC_CONFOUND_DEPLOYMENT_BLOCK: Final = True
ALGORITHM_MISMATCH_SENTINEL: Final = "integration-transport-failure-v1"

MAX_REQUEST_BYTES: Final = 6_000_000
MAX_STDOUT_BYTES: Final = 131_072
MAX_STDERR_BYTES: Final = 131_072
WALL_TIMEOUT_SECONDS: Final = 30.0
CPU_LIMIT_SECONDS: Final = 24
ADDRESS_SPACE_LIMIT_BYTES: Final = 1_073_741_824
OPEN_FILE_LIMIT: Final = 32
FILE_SIZE_LIMIT_BYTES: Final = 131_072
MAX_JSON_DEPTH: Final = 6

KNOWN_ABSTENTION_CODES: Final = frozenset(
    {
        "excessive_tier_fragmentation",
        "insufficient_two_tier_evidence",
        "insufficient_contiguous_label_run",
        "lane_pitch_disagreement",
        "multi_column_confound",
        "invalid_request",
    }
)
FORBIDDEN_WHEEL_MEMBER_PARTS: Final = (
    "kp1979_synthetic_control_v2",
    "benchmark/results/",
    "data/raw/",
    "data/derived/",
)

WorkerDisposition = Literal["accepted", "out_of_contract", "algorithm_mismatch"]
ProcessInvoker: TypeAlias = Callable[[bytes], "WorkerProcessResult"]

_REQUEST_KEYS: Final = frozenset(
    {"interface_version", "pbm_base64", "width", "height", "scan_bands"}
)
_RESPONSE_KEYS: Final = frozenset(
    {"algorithm_id", "interface_version", "status", "abstention_codes", "predictions"}
)
_PREDICTION_KEYS: Final = frozenset({"lane", "y0", "y1"})
_WORKER_BOOTSTRAP: Final = (
    "import sys;"
    "sys.path.insert(0,sys.argv[1]);"
    "from indusbench.kp1979_detector_v2_worker import main;"
    "raise SystemExit(main())"
)


class KP1979V2RunnerError(ValueError):
    """Raised when the one-shot runner contract cannot be completed safely."""


class WorkerBoundaryError(KP1979V2RunnerError):
    """A normalized, non-secret failure at the child-process boundary."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class WorkerPrediction:
    """One validated worker prediction."""

    lane: int
    y0: int
    y1: int


@dataclass(frozen=True, slots=True)
class WorkerOutcome:
    """One normalized child-process outcome before synthetic scoring."""

    disposition: WorkerDisposition
    status: str
    abstention_codes: tuple[str, ...]
    predictions: tuple[WorkerPrediction, ...]


@dataclass(frozen=True, slots=True)
class WorkerProcessResult:
    """Bounded bytes and status returned by one fresh child process."""

    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class TransportRecord:
    """Public aggregate-safe disposition for one worker invocation."""

    disposition: WorkerDisposition
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class RunConfiguration:
    """Owner-supplied paths and the already-published integration commit."""

    repository_root: Path
    detector_wheel: Path
    python_executable: Path
    integration_commit: str


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if not isinstance(key, str) or key in result:
            raise WorkerBoundaryError("malformed_json")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> object:
    raise WorkerBoundaryError("malformed_json")


def _require_bounded_depth(value: object, *, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise WorkerBoundaryError("overdeep_json")
    if isinstance(value, dict):
        for nested in value.values():
            _require_bounded_depth(nested, depth=depth + 1)
    elif isinstance(value, list):
        for nested in value:
            _require_bounded_depth(nested, depth=depth + 1)


def _strict_integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise WorkerBoundaryError("invalid_prediction")
    return value


def _request_bytes(detector_input: SyntheticDetectorInput) -> bytes:
    request = {
        "interface_version": WORKER_INTERFACE_VERSION,
        "pbm_base64": base64.b64encode(detector_input.pbm_bytes).decode("ascii"),
        "width": detector_input.width,
        "height": detector_input.height,
        "scan_bands": [list(band) for band in detector_input.scan_bands],
    }
    if frozenset(request) != _REQUEST_KEYS:
        raise KP1979V2RunnerError("internal request contract is not closed")
    encoded = _canonical_json_bytes(request)
    if not encoded or len(encoded) > MAX_REQUEST_BYTES:
        raise KP1979V2RunnerError("worker request exceeds its fixed bound")
    return encoded


def _input_is_structurally_valid(detector_input: SyntheticDetectorInput) -> bool:
    return (
        type(detector_input.width) is int
        and detector_input.width == 4880
        and type(detector_input.height) is int
        and detector_input.height == 7010
        and detector_input.scan_bands
        == (
            (2056, 550, 2316, 6600),
            (4232, 550, 4492, 6600),
        )
        and type(detector_input.pbm_bytes) is bytes
        and len(detector_input.pbm_bytes) == 4_276_113
        and detector_input.pbm_bytes.startswith(b"P4\n4880 7010\n")
    )


def parse_worker_process_result(process: WorkerProcessResult) -> WorkerOutcome:
    """Validate one raw worker response without coercion or sorting."""

    if not isinstance(process, WorkerProcessResult):
        raise WorkerBoundaryError("invalid_process_result")
    if process.timed_out:
        raise WorkerBoundaryError("timeout")
    if process.returncode != 0:
        raise WorkerBoundaryError("nonzero_exit")
    if process.stderr:
        raise WorkerBoundaryError("stderr_output")
    if not process.stdout or len(process.stdout) > MAX_STDOUT_BYTES:
        raise WorkerBoundaryError("stdout_size")
    if not process.stdout.endswith(b"\n") or process.stdout.count(b"\n") != 1:
        raise WorkerBoundaryError("noncanonical_stdout")
    try:
        parsed = json.loads(
            process.stdout.decode("utf-8"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except WorkerBoundaryError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerBoundaryError("malformed_json") from exc
    _require_bounded_depth(parsed)
    if not isinstance(parsed, dict) or frozenset(parsed) != _RESPONSE_KEYS:
        raise WorkerBoundaryError("response_not_closed")
    if parsed["algorithm_id"] != TARGET_ALGORITHM_ID:
        raise WorkerBoundaryError("algorithm_id")
    if parsed["interface_version"] != WORKER_INTERFACE_VERSION:
        raise WorkerBoundaryError("interface_version")

    status = parsed["status"]
    codes = parsed["abstention_codes"]
    raw_predictions = parsed["predictions"]
    if status not in {"proposed", "abstained"}:
        raise WorkerBoundaryError("status")
    if (
        not isinstance(codes, list)
        or any(not isinstance(code, str) or code not in KNOWN_ABSTENTION_CODES for code in codes)
        or codes != sorted(set(codes))
    ):
        raise WorkerBoundaryError("abstention_codes")
    if not isinstance(raw_predictions, list) or len(raw_predictions) > MAX_PREDICTIONS_PER_PROPOSAL:
        raise WorkerBoundaryError("prediction_count")

    predictions: list[WorkerPrediction] = []
    ordering: list[tuple[int, int, int]] = []
    for raw_prediction in raw_predictions:
        if not isinstance(raw_prediction, dict) or frozenset(raw_prediction) != _PREDICTION_KEYS:
            raise WorkerBoundaryError("invalid_prediction")
        lane = _strict_integer(raw_prediction["lane"])
        y0 = _strict_integer(raw_prediction["y0"])
        y1 = _strict_integer(raw_prediction["y1"])
        if lane not in {0, 1} or not 0 <= y0 < y1 <= 7010 or y1 - y0 != 96:
            raise WorkerBoundaryError("invalid_prediction")
        ordering.append((lane, y0, y1))
        predictions.append(WorkerPrediction(lane=lane, y0=y0, y1=y1))
    if ordering != sorted(set(ordering)):
        raise WorkerBoundaryError("prediction_order")

    code_tuple = tuple(codes)
    prediction_tuple = tuple(predictions)
    if status == "proposed":
        if codes or not predictions:
            raise WorkerBoundaryError("proposed_contract")
        return WorkerOutcome("accepted", status, code_tuple, prediction_tuple)
    if not codes or predictions:
        raise WorkerBoundaryError("abstained_contract")
    if codes == ["invalid_request"]:
        return WorkerOutcome("out_of_contract", status, code_tuple, ())
    if "invalid_request" in codes:
        raise WorkerBoundaryError("invalid_request_mixed")
    return WorkerOutcome("accepted", status, code_tuple, ())


def _failure_sentinel() -> SyntheticDetectorProposal:
    return SyntheticDetectorProposal(
        algorithm_id=ALGORITHM_MISMATCH_SENTINEL,
        detection_status="abstained",
        predictions=(),
    )


class FreshProcessAdapter:
    """Convert one fresh worker response per input into the frozen control type."""

    def __init__(self, invoker: ProcessInvoker, *, process_isolation_verified: bool) -> None:
        self._invoker = invoker
        self.process_isolation_verified = process_isolation_verified
        self.records: list[TransportRecord] = []

    @property
    def invocation_count(self) -> int:
        return len(self.records)

    def __call__(
        self,
        detector_input: SyntheticDetectorInput,
        /,
    ) -> SyntheticDetectorProposal | SyntheticInputRejection:
        structurally_valid = _input_is_structurally_valid(detector_input)
        try:
            raw_result = self._invoker(_request_bytes(detector_input))
            outcome = parse_worker_process_result(raw_result)
        except WorkerBoundaryError as exc:
            self.records.append(TransportRecord("algorithm_mismatch", exc.code))
            return _failure_sentinel()
        except Exception:
            self.records.append(TransportRecord("algorithm_mismatch", "transport_exception"))
            return _failure_sentinel()

        if outcome.disposition == "out_of_contract":
            if structurally_valid:
                self.records.append(
                    TransportRecord(
                        "algorithm_mismatch",
                        "invalid_request_on_valid_input",
                    )
                )
                return _failure_sentinel()
            self.records.append(TransportRecord("out_of_contract", None))
            return SyntheticInputRejection(algorithm_id=TARGET_ALGORITHM_ID)
        if not structurally_valid:
            self.records.append(
                TransportRecord(
                    "algorithm_mismatch",
                    "nonrejection_on_invalid_input",
                )
            )
            return _failure_sentinel()
        if outcome.disposition != "accepted":
            self.records.append(TransportRecord("algorithm_mismatch", "invalid_disposition"))
            return _failure_sentinel()
        self.records.append(TransportRecord("accepted", None))
        return SyntheticDetectorProposal(
            algorithm_id=TARGET_ALGORITHM_ID,
            detection_status=outcome.status,  # type: ignore[arg-type]
            predictions=tuple(
                SyntheticPrediction(
                    lane_index=prediction.lane,
                    y0=prediction.y0,
                    y1=prediction.y1,
                )
                for prediction in outcome.predictions
            ),
        )


def _apply_child_limits() -> None:
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    if hasattr(resource, "RLIMIT_AS"):
        resource.setrlimit(
            resource.RLIMIT_AS,
            (ADDRESS_SPACE_LIMIT_BYTES, ADDRESS_SPACE_LIMIT_BYTES),
        )
    resource.setrlimit(resource.RLIMIT_NOFILE, (OPEN_FILE_LIMIT, OPEN_FILE_LIMIT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (FILE_SIZE_LIMIT_BYTES, FILE_SIZE_LIMIT_BYTES),
    )


class SubprocessWorkerInvoker:
    """Invoke the frozen D wheel once in a bounded empty working directory."""

    def __init__(self, *, python_executable: Path, detector_wheel: Path) -> None:
        self._python_executable = python_executable
        self.started_process_count = 0
        wheel_bytes = detector_wheel.read_bytes()
        if sha256(wheel_bytes).hexdigest() != DETECTOR_WHEEL_SHA256:
            raise KP1979V2RunnerError("detector wheel changed after preflight")
        self._detector_wheel_bytes = wheel_bytes

    def __call__(self, request: bytes) -> WorkerProcessResult:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-worker-") as raw_directory:
            base_directory = Path(raw_directory)
            if stat.S_IMODE(base_directory.stat().st_mode) & 0o077:
                raise WorkerBoundaryError("temporary_directory_permissions")
            working_directory = base_directory / "cwd"
            working_directory.mkdir(mode=0o700)
            detector_wheel = base_directory / "detector.whl"
            wheel_descriptor = os.open(
                detector_wheel,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o600,
            )
            try:
                _write_all(wheel_descriptor, self._detector_wheel_bytes)
                os.fsync(wheel_descriptor)
            finally:
                os.close(wheel_descriptor)
            detector_wheel.chmod(0o400)
            stdout_path = base_directory / "stdout.bin"
            stderr_path = base_directory / "stderr.bin"
            with stdout_path.open("w+b") as stdout_handle, stderr_path.open("w+b") as stderr_handle:
                if any(working_directory.iterdir()):
                    raise WorkerBoundaryError("working_directory_not_empty")
                process = subprocess.Popen(
                    [
                        str(self._python_executable),
                        "-I",
                        "-S",
                        "-c",
                        _WORKER_BOOTSTRAP,
                        str(detector_wheel),
                    ],
                    cwd=working_directory,
                    env={
                        "PATH": "/usr/bin:/bin",
                        "LANG": "C.UTF-8",
                        "LC_ALL": "C.UTF-8",
                    },
                    stdin=subprocess.PIPE,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    close_fds=True,
                    shell=False,
                    start_new_session=True,
                    preexec_fn=_apply_child_limits,
                )
                self.started_process_count += 1
                timed_out = False
                try:
                    process.communicate(input=request, timeout=WALL_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                stdout_handle.flush()
                stderr_handle.flush()
                stdout_handle.seek(0)
                stderr_handle.seek(0)
                standard_output = stdout_handle.read(MAX_STDOUT_BYTES + 1)
                standard_error = stderr_handle.read(MAX_STDERR_BYTES + 1)
            return WorkerProcessResult(
                returncode=process.returncode,
                stdout=standard_output,
                stderr=standard_error,
                timed_out=timed_out,
            )


def _require_regular_owner_file(path: Path, *, executable: bool = False) -> Path:
    if not path.is_absolute():
        raise KP1979V2RunnerError("input path must be absolute")
    resolved = path.resolve(strict=True)
    metadata = resolved.stat()
    owner_is_safe = metadata.st_uid == os.getuid() or (executable and metadata.st_uid == 0)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or not owner_is_safe
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        raise KP1979V2RunnerError("input file is not a safe owner file")
    if executable and not os.access(resolved, os.X_OK):
        raise KP1979V2RunnerError("python executable is not executable")
    if executable and resolved != Path(sys.executable).resolve(strict=True):
        raise KP1979V2RunnerError("worker interpreter differs from the runner interpreter")
    return resolved


def _validate_detector_wheel(path: Path) -> tuple[Path, int]:
    wheel = _require_regular_owner_file(path)
    if _sha256_path(wheel) != DETECTOR_WHEEL_SHA256:
        raise KP1979V2RunnerError("detector wheel digest differs from the freeze")
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
        if (
            not members
            or len(members) != len(set(members))
            or any(
                forbidden in member
                for member in members
                for forbidden in FORBIDDEN_WHEEL_MEMBER_PARTS
            )
            or "indusbench/kp1979_detector_v2_worker.py" not in members
            or "indusbench/printed_concordance_layout_v2.py" not in members
        ):
            raise KP1979V2RunnerError("detector wheel members differ from the boundary")
    return wheel, wheel.stat().st_size


def _git(repository_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        [str(GIT_EXECUTABLE), "-C", str(repository_root), *arguments],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
        env={
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/bin:/bin",
        },
    )
    if completed.returncode != 0 or completed.stderr:
        raise KP1979V2RunnerError("Git preflight failed")
    return completed.stdout.strip()


def _require_hex_commit(value: str) -> None:
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise KP1979V2RunnerError("integration commit is not a full lowercase object id")


def _validate_repository(configuration: RunConfiguration) -> Path:
    root = configuration.repository_root.resolve(strict=True)
    if not root.is_dir():
        raise KP1979V2RunnerError("repository root is invalid")
    expected_hashes = {
        "src/indusbench/kp1979_synthetic_control_v2.py": CONTROL_MODULE_SHA256,
        "benchmark/kp1979-label-lattice-synthetic-control-v2.json": (CONTROL_MANIFEST_SHA256),
        "src/indusbench/kp1979_detector_v2_worker.py": WORKER_MODULE_SHA256,
        "src/indusbench/printed_concordance_layout_v2.py": DETECTOR_MODULE_SHA256,
        "src/indusbench/kp1979_label_scoring.py": SCORER_MODULE_SHA256,
        "uv.lock": UV_LOCK_SHA256,
    }
    for relative_path, expected_digest in expected_hashes.items():
        path = root / relative_path
        if not path.is_file() or _sha256_path(path) != expected_digest:
            raise KP1979V2RunnerError("frozen repository bytes differ")
    loaded_paths = {
        Path(control_module.__file__ or "").resolve(strict=True): (
            root / "src/indusbench/kp1979_synthetic_control_v2.py"
        ).resolve(strict=True),
        Path(scoring_module.__file__ or "").resolve(strict=True): (
            root / "src/indusbench/kp1979_label_scoring.py"
        ).resolve(strict=True),
    }
    if any(actual != expected for actual, expected in loaded_paths.items()):
        raise KP1979V2RunnerError("loaded frozen module path differs")
    _require_hex_commit(configuration.integration_commit)
    if _git(root, "status", "--porcelain"):
        raise KP1979V2RunnerError("integration worktree is not clean")
    if _git(root, "rev-parse", "HEAD") != configuration.integration_commit:
        raise KP1979V2RunnerError("integration HEAD differs from the requested commit")
    parents = _git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()
    if parents != [configuration.integration_commit, CONTROL_COMMIT, DETECTOR_COMMIT]:
        raise KP1979V2RunnerError("integration commit does not have the frozen parents")
    if _git(root, "merge-base", CONTROL_COMMIT, DETECTOR_COMMIT) != BASE_COMMIT:
        raise KP1979V2RunnerError("control and detector merge base differs")
    if _git(root, "remote", "get-url", "origin") != EXPECTED_ORIGIN_URL:
        raise KP1979V2RunnerError("public remote identity differs")
    if _git(root, "rev-parse", "refs/remotes/origin/main") != configuration.integration_commit:
        raise KP1979V2RunnerError("public main ref does not contain the integration freeze")
    return root


def _load_closed_json(path: Path) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except WorkerBoundaryError as exc:
        raise KP1979V2RunnerError("tracked JSON is not closed") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KP1979V2RunnerError("tracked JSON is malformed") from exc
    if not isinstance(parsed, dict):
        raise KP1979V2RunnerError("tracked JSON root is not an object")
    return parsed, raw


def _validate_plan_and_schemas(
    root: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, str]]:
    plan, plan_bytes = _load_closed_json(root / EXECUTION_PLAN_PATH)
    execution_schema, execution_schema_bytes = _load_closed_json(root / EXECUTION_SCHEMA_PATH)
    result_schema, result_schema_bytes = _load_closed_json(root / RESULT_SCHEMA_PATH)
    Draft202012Validator.check_schema(execution_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(execution_schema).validate(plan)
    if (
        plan.get("plan_id") != PLAN_ID
        or plan.get("target_algorithm_id") != TARGET_ALGORITHM_ID
        or plan.get("control_id") != CONTROL_ID
        or plan.get("result_state") != "not_run"
    ):
        raise KP1979V2RunnerError("execution plan identity differs from the freeze")
    digests = {
        "execution_plan_sha256": sha256(plan_bytes).hexdigest(),
        "execution_schema_sha256": sha256(execution_schema_bytes).hexdigest(),
        "result_schema_sha256": sha256(result_schema_bytes).hexdigest(),
    }
    return plan, result_schema, digests


def _validate_owner_output_paths(marker: Path, result: Path) -> tuple[Path, str, str]:
    if not marker.is_absolute() or not result.is_absolute():
        raise KP1979V2RunnerError("output paths must be absolute")
    marker_parent = marker.parent.resolve(strict=True)
    result_parent = result.parent.resolve(strict=True)
    if marker.parent != marker_parent or result.parent != result_parent:
        raise KP1979V2RunnerError("output parent must not traverse a symlink")
    if marker_parent != result_parent or marker.name == result.name:
        raise KP1979V2RunnerError("marker and result must be distinct in one directory")
    metadata = marker_parent.stat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise KP1979V2RunnerError("output directory is not owner-only")
    for target in (marker, result):
        try:
            target.lstat()
        except FileNotFoundError:
            continue
        raise KP1979V2RunnerError("attempt marker or result already exists")
    return marker_parent, marker.name, result.name


def _canonical_state_directory() -> Path:
    account_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
    return account_home / ".local" / "state" / "indus-open-benchmark" / "kp1979-v2-qualification-v1"


def _canonical_state_paths() -> tuple[Path, Path]:
    directory = _canonical_state_directory()
    return (
        directory / "attempt-1.started.json",
        directory / "attempt-1.result.json",
    )


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("short write")
        view = view[written:]


def _create_marker(parent: Path, name: str, payload: bytes) -> None:
    parent_descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(name, flags, 0o600, dir_fd=parent_descriptor)
        try:
            _write_all(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)


def _publish_result(parent: Path, name: str, payload: bytes) -> None:
    parent_descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    temporary_name = f".{name}.tmp-{os.getpid()}-{os.urandom(8).hex()}"
    committed = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary_name, flags, 0o600, dir_fd=parent_descriptor)
        try:
            _write_all(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.link(
            temporary_name,
            name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        os.fsync(parent_descriptor)
        committed = True
        with contextlib.suppress(OSError):
            os.unlink(temporary_name, dir_fd=parent_descriptor)
        with contextlib.suppress(OSError):
            os.fsync(parent_descriptor)
    except Exception:
        if not committed:
            with contextlib.suppress(OSError):
                os.unlink(temporary_name, dir_fd=parent_descriptor)
        raise
    finally:
        os.close(parent_descriptor)


def _transport_summary(adapter: FreshProcessAdapter) -> dict[str, object]:
    failure_counts: dict[str, int] = {}
    for record in adapter.records:
        if record.failure_code is not None:
            failure_counts[record.failure_code] = failure_counts.get(record.failure_code, 0) + 1
    return {
        "invocation_count": adapter.invocation_count,
        "expected_invocation_count": FRESH_PROCESS_COUNT,
        "accepted_count": sum(record.disposition == "accepted" for record in adapter.records),
        "out_of_contract_rejection_count": sum(
            record.disposition == "out_of_contract" for record in adapter.records
        ),
        "transport_failure_count": sum(
            record.disposition == "algorithm_mismatch" for record in adapter.records
        ),
        "failure_codes": [
            {"code": code, "count": count} for code, count in sorted(failure_counts.items())
        ],
        "stderr_observed": "stderr_output" in failure_counts,
        "timeout_observed": "timeout" in failure_counts,
    }


def _build_result(
    *,
    configuration: RunConfiguration,
    wheel_size: int,
    schema_digests: Mapping[str, str],
    report: SyntheticControlReport,
    adapter: FreshProcessAdapter,
    started_process_count: int,
) -> dict[str, object]:
    transport = _transport_summary(adapter)
    control_passed = report.status == "qualified"
    transport_passed = transport["transport_failure_count"] == 0
    fresh_process_count_verified = (
        started_process_count == adapter.invocation_count == FRESH_PROCESS_COUNT
    )
    control_report = json.loads(_canonical_json_bytes(asdict(report)))
    if not isinstance(control_report, dict):
        raise KP1979V2RunnerError("control report is not a JSON object")
    result = {
        "result_version": 1,
        "terminal_status": "not_qualified",
        "advance_to_provisional_extraction": False,
        "commitments": {
            "base_commit": BASE_COMMIT,
            "control_commit": CONTROL_COMMIT,
            "detector_commit": DETECTOR_COMMIT,
            "integration_commit": configuration.integration_commit,
            "detector_wheel_sha256": DETECTOR_WHEEL_SHA256,
            "detector_wheel_byte_size": wheel_size,
            "control_module_sha256": CONTROL_MODULE_SHA256,
            "control_manifest_sha256": CONTROL_MANIFEST_SHA256,
            "worker_module_sha256": WORKER_MODULE_SHA256,
            "detector_module_sha256": DETECTOR_MODULE_SHA256,
            "scorer_module_sha256": SCORER_MODULE_SHA256,
            "uv_lock_sha256": UV_LOCK_SHA256,
            **schema_digests,
        },
        "freeze_integrity": {
            "git_ancestry_verified": True,
            "blob_identity_verified": True,
            "control_manifest_verified": True,
            "detector_wheel_verified": True,
            "wheel_excludes_v2_control": True,
            "public_main_ref_matches_integration_commit": True,
            "public_remote_independently_attested": False,
        },
        "development_separation": {
            "process_separated": True,
            "mutual_nonexposure_declared": True,
            "control_before_detector_freeze": CONTROL_BEFORE_DETECTOR_FREEZE,
            "confidentiality_verified": False,
            "blinding_verified": False,
            "organizational_independence_verified": False,
            "cross_access_absence_verified": False,
            "git_proves_bytes_and_ancestry_only": True,
        },
        "execution_boundary": {
            "fresh_process_per_invocation": fresh_process_count_verified,
            "started_process_count": started_process_count,
            "canonical_attempt_state_enforced": True,
            "single_execution_technically_enforced": False,
            "loaded_module_paths_verified": True,
            "child_input_fields": [
                "height",
                "interface_version",
                "pbm_base64",
                "scan_bands",
                "width",
            ],
            "case_identity_supplied": False,
            "truth_supplied": False,
            "scorer_supplied": False,
            "order_supplied": False,
            "empty_working_directory": True,
            "environment_allowlist": ["LANG", "LC_ALL", "PATH"],
            "close_fds": True,
            "shell_used": False,
            "wall_timeout_seconds": WALL_TIMEOUT_SECONDS,
            "cpu_limit_seconds": CPU_LIMIT_SECONDS,
            "address_space_limit_bytes": ADDRESS_SPACE_LIMIT_BYTES,
            "open_file_limit": OPEN_FILE_LIMIT,
            "file_size_limit_bytes": FILE_SIZE_LIMIT_BYTES,
            "network_isolation_verified": False,
            "network_nonaccess_verified": False,
            "filesystem_namespace_isolation_verified": False,
            "worker_internal_failure_cause_distinguishable": False,
            "valid_input_invalid_request_fails_closed": True,
            "preimport_code_execution_excluded": False,
        },
        "transport_summary": transport,
        "mandatory_gates": {
            "control_case_gates_passed": control_passed,
            "control_before_detector_freeze": CONTROL_BEFORE_DETECTOR_FREEZE,
            "transport_boundary_passed": transport_passed,
            "fresh_process_count_verified": fresh_process_count_verified,
            "control_contract_hardening_applied": True,
            "postfreeze_adversarial_deployment_clear": False,
            "all_mandatory_gates_passed": False,
        },
        "control_report": control_report,
        "deployment_decision": {
            "status": "blocked",
            "reason_codes": [
                "control_before_detector_freeze_order_not_satisfied",
                "postfreeze_periodic_confound",
            ],
            "machine_development_candidate_generation_allowed": False,
            "automatic_corpus_admission_allowed": False,
            "reference_promotion_allowed": False,
            "future_execution_allowed": False,
        },
        "claim_scope": {
            "real_accuracy": False,
            "accepted_reference": False,
            "code_transcription_validated": False,
            "evaluation_admissible": False,
            "future_evaluation_opened": False,
            "future_pixels_loaded": False,
            "future_pixels_opened": False,
            "reserved_sources_read": False,
            "full_row_segmentation_validated": False,
            "identifier_transcription_validated": False,
            "lower_code_validated": False,
            "row_identity_validated": False,
            "sign_sequence_validated": False,
            "reading_direction_validated": False,
            "language_identified": False,
            "meaning_established": False,
            "translation_produced": False,
            "decipherment": False,
            "prize_submission_eligible": False,
            "prize_claim": False,
            "prize_submission_made": False,
        },
    }
    return result


def _validate_result_semantics(result: Mapping[str, object]) -> None:
    report = result.get("control_report")
    transport = result.get("transport_summary")
    gates = result.get("mandatory_gates")
    claims = result.get("claim_scope")
    deployment = result.get("deployment_decision")
    boundary = result.get("execution_boundary")
    if not all(
        isinstance(value, dict)
        for value in (report, transport, gates, claims, deployment, boundary)
    ):
        raise KP1979V2RunnerError("result semantic object is malformed")
    assert isinstance(report, dict)
    assert isinstance(transport, dict)
    assert isinstance(gates, dict)
    assert isinstance(claims, dict)
    assert isinstance(deployment, dict)
    assert isinstance(boundary, dict)

    cases = report.get("cases")
    metamorphic = report.get("metamorphic_checks")
    if not isinstance(cases, list) or not isinstance(metamorphic, list):
        raise KP1979V2RunnerError("control result rosters are malformed")
    freeze = frozen_synthetic_control()
    expected_cases = tuple(
        (commitment.case_id, commitment.case_class) for commitment in freeze.case_commitments
    )
    actual_cases = tuple(
        (case.get("case_id"), case.get("case_class")) for case in cases if isinstance(case, dict)
    )
    if actual_cases != expected_cases or len(actual_cases) != len(cases):
        raise KP1979V2RunnerError("control case roster differs from the freeze")
    expected_relations = (
        "identical_input_reproducibility",
        "unread_margin_invariance",
        "vertical_translation_equivariance",
    )
    actual_relations = tuple(
        relation.get("relation_id") for relation in metamorphic if isinstance(relation, dict)
    )
    if actual_relations != expected_relations or len(actual_relations) != len(metamorphic):
        raise KP1979V2RunnerError("metamorphic roster differs from the freeze")

    raw_case_passes = [case.get("passed") for case in cases if isinstance(case, dict)]
    raw_relation_passes = [
        relation.get("passed") for relation in metamorphic if isinstance(relation, dict)
    ]
    if any(type(value) is not bool for value in (*raw_case_passes, *raw_relation_passes)):
        raise KP1979V2RunnerError("control pass state is malformed")
    case_passes = [value for value in raw_case_passes if isinstance(value, bool)]
    relation_passes = [value for value in raw_relation_passes if isinstance(value, bool)]
    qualified = all(case_passes) and all(relation_passes)
    expected_status = "qualified" if qualified else "not_qualified"
    if (
        report.get("status") != expected_status
        or report.get("passed_case_count") != sum(case_passes)
        or gates.get("control_case_gates_passed") is not qualified
    ):
        raise KP1979V2RunnerError("control aggregate state is inconsistent")

    count_fields = (
        transport.get("accepted_count"),
        transport.get("out_of_contract_rejection_count"),
        transport.get("transport_failure_count"),
    )
    if any(type(value) is not int or value < 0 for value in count_fields):
        raise KP1979V2RunnerError("transport counts are malformed")
    accepted, rejected, failed = count_fields
    assert isinstance(accepted, int)
    assert isinstance(rejected, int)
    assert isinstance(failed, int)
    if (
        transport.get("invocation_count") != FRESH_PROCESS_COUNT
        or transport.get("expected_invocation_count") != FRESH_PROCESS_COUNT
        or accepted + rejected + failed != FRESH_PROCESS_COUNT
    ):
        raise KP1979V2RunnerError("transport totals are inconsistent")
    failure_codes = transport.get("failure_codes")
    if not isinstance(failure_codes, list):
        raise KP1979V2RunnerError("transport failure roster is malformed")
    failure_total = sum(
        item.get("count", -1)
        for item in failure_codes
        if isinstance(item, dict) and type(item.get("count")) is int
    )
    if len(failure_codes) != sum(isinstance(item, dict) for item in failure_codes):
        raise KP1979V2RunnerError("transport failure item is malformed")
    if failure_total != failed:
        raise KP1979V2RunnerError("transport failure counts are inconsistent")

    if (
        result.get("terminal_status") != "not_qualified"
        or result.get("advance_to_provisional_extraction") is not False
        or gates.get("control_before_detector_freeze") is not False
        or gates.get("postfreeze_adversarial_deployment_clear") is not False
        or gates.get("all_mandatory_gates_passed") is not False
        or deployment.get("status") != "blocked"
        or gates.get("fresh_process_count_verified")
        is not (
            boundary.get("started_process_count") == FRESH_PROCESS_COUNT
            and transport.get("invocation_count") == FRESH_PROCESS_COUNT
        )
        or any(value is not False for value in claims.values())
    ):
        raise KP1979V2RunnerError("result safety gates are inconsistent")


def run_one_shot(
    configuration: RunConfiguration,
) -> dict[str, object]:
    """Execute the frozen control once after all non-consuming preflights."""

    root = _validate_repository(configuration)
    wheel, wheel_size = _validate_detector_wheel(configuration.detector_wheel)
    python_executable = _require_regular_owner_file(
        configuration.python_executable,
        executable=True,
    )
    _, result_schema, schema_digests = _validate_plan_and_schemas(root)
    attempt_marker, result_output = _canonical_state_paths()
    parent, marker_name, result_name = _validate_owner_output_paths(
        attempt_marker,
        result_output,
    )

    marker = {
        "attempt_id": RUNNER_ID,
        "state": "started",
        "control_id": CONTROL_ID,
        "target_algorithm_id": TARGET_ALGORITHM_ID,
        "integration_commit": configuration.integration_commit,
    }
    worker_invoker = SubprocessWorkerInvoker(
        python_executable=python_executable,
        detector_wheel=wheel,
    )
    _create_marker(parent, marker_name, _canonical_json_bytes(marker))
    adapter = FreshProcessAdapter(
        worker_invoker,
        process_isolation_verified=True,
    )
    report = evaluate_frozen_synthetic_control(adapter)
    if adapter.invocation_count != FRESH_PROCESS_COUNT:
        raise KP1979V2RunnerError("control invocation roster did not complete exactly once")

    result = _build_result(
        configuration=configuration,
        wheel_size=wheel_size,
        schema_digests=schema_digests,
        report=report,
        adapter=adapter,
        started_process_count=worker_invoker.started_process_count,
    )
    _validate_result_semantics(result)
    Draft202012Validator(result_schema).validate(result)
    encoded_result = _canonical_json_bytes(result)
    reparsed = json.loads(encoded_result)
    Draft202012Validator(result_schema).validate(reparsed)
    _publish_result(parent, result_name, encoded_result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="indusbench-kp1979-v2-qualification",
        description="Run the frozen KP1979 V2 synthetic control exactly once.",
    )
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--detector-wheel", required=True, type=Path)
    parser.add_argument("--python-executable", required=True, type=Path)
    parser.add_argument("--integration-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configuration = RunConfiguration(
        repository_root=arguments.repository_root,
        detector_wheel=arguments.detector_wheel,
        python_executable=arguments.python_executable,
        integration_commit=arguments.integration_commit,
    )
    try:
        result = run_one_shot(configuration)
    except Exception:
        sys.stderr.write("indusbench-kp1979-v2-qualification: execution failed closed\n")
        return 1
    sys.stdout.buffer.write(
        _canonical_json_bytes(
            {
                "advance_to_provisional_extraction": result["advance_to_provisional_extraction"],
                "terminal_status": result["terminal_status"],
            }
        )
    )
    return 0


__all__ = [
    "ADDRESS_SPACE_LIMIT_BYTES",
    "ALGORITHM_MISMATCH_SENTINEL",
    "BASE_COMMIT",
    "CONTROL_BEFORE_DETECTOR_FREEZE",
    "CONTROL_COMMIT",
    "DETECTOR_COMMIT",
    "DETECTOR_WHEEL_SHA256",
    "FILE_SIZE_LIMIT_BYTES",
    "FRESH_PROCESS_COUNT",
    "KNOWN_ABSTENTION_CODES",
    "PLAN_ID",
    "POSTFREEZE_PERIODIC_CONFOUND_DEPLOYMENT_BLOCK",
    "RESULT_SCHEMA_ID",
    "RUNNER_ID",
    "TARGET_ALGORITHM_ID",
    "WALL_TIMEOUT_SECONDS",
    "WORKER_INTERFACE_VERSION",
    "FreshProcessAdapter",
    "KP1979V2RunnerError",
    "RunConfiguration",
    "SubprocessWorkerInvoker",
    "WorkerBoundaryError",
    "WorkerOutcome",
    "WorkerPrediction",
    "WorkerProcessResult",
    "build_parser",
    "main",
    "parse_worker_process_result",
    "run_one_shot",
]


if __name__ == "__main__":
    raise SystemExit(main())
