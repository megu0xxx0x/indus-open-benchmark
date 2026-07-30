from __future__ import annotations

import base64
import copy
import json
import os
import stat
import sys
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

import indusbench.kp1979_v2_runner as runner
from indusbench.kp1979_synthetic_control_v2 import (
    SYNTHETIC_PAGE_HEIGHT,
    SYNTHETIC_PAGE_WIDTH,
    SYNTHETIC_PBM_BYTE_SIZE,
    SYNTHETIC_PBM_HEADER,
    SYNTHETIC_SCAN_BANDS,
    SyntheticDetectorInput,
    SyntheticDetectorProposal,
    SyntheticInputRejection,
    build_synthetic_fixture,
    detector_input_for_fixture,
    evaluate_synthetic_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
REQUEST_KEYS = {
    "interface_version",
    "pbm_base64",
    "width",
    "height",
    "scan_bands",
}


def _response_bytes(
    *,
    status: str,
    abstention_codes: list[str] | None = None,
    predictions: Sequence[Mapping[str, object]] | None = None,
) -> bytes:
    return (
        json.dumps(
            {
                "algorithm_id": runner.TARGET_ALGORITHM_ID,
                "interface_version": runner.WORKER_INTERFACE_VERSION,
                "status": status,
                "abstention_codes": abstention_codes or [],
                "predictions": predictions or [],
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _process(
    *,
    status: str = "abstained",
    abstention_codes: list[str] | None = None,
    predictions: Sequence[Mapping[str, object]] | None = None,
    returncode: int = 0,
    stderr: bytes = b"",
    timed_out: bool = False,
) -> runner.WorkerProcessResult:
    return runner.WorkerProcessResult(
        returncode=returncode,
        stdout=_response_bytes(
            status=status,
            abstention_codes=abstention_codes,
            predictions=predictions,
        ),
        stderr=stderr,
        timed_out=timed_out,
    )


def _small_input() -> SyntheticDetectorInput:
    return SyntheticDetectorInput(
        pbm_bytes=b"P4\n8 1\n\x00",
        width=8,
        height=1,
        scan_bands=((0, 0, 8, 1),),
    )


def _valid_structural_input() -> SyntheticDetectorInput:
    return SyntheticDetectorInput(
        pbm_bytes=SYNTHETIC_PBM_HEADER + bytes(SYNTHETIC_PBM_BYTE_SIZE - len(SYNTHETIC_PBM_HEADER)),
        width=SYNTHETIC_PAGE_WIDTH,
        height=SYNTHETIC_PAGE_HEIGHT,
        scan_bands=SYNTHETIC_SCAN_BANDS,
    )


def _assert_failure_sentinel(
    testcase: unittest.TestCase,
    proposal: SyntheticDetectorProposal | SyntheticInputRejection,
) -> None:
    testcase.assertIsInstance(proposal, SyntheticDetectorProposal)
    assert isinstance(proposal, SyntheticDetectorProposal)
    testcase.assertEqual(runner.ALGORITHM_MISMATCH_SENTINEL, proposal.algorithm_id)
    testcase.assertEqual("abstained", proposal.detection_status)
    testcase.assertEqual((), proposal.predictions)


class _StructuralFakeInvoker:
    """Answer only from the five-field structural request, never control truth."""

    def __init__(self, marker_path: Path | None = None, result_path: Path | None = None) -> None:
        self.marker_path = marker_path
        self.result_path = result_path
        self.call_count = 0
        self.request_keysets: list[frozenset[str]] = []

    def __call__(self, request: bytes) -> runner.WorkerProcessResult:
        if self.call_count == 0 and self.marker_path is not None:
            if not self.marker_path.is_file():
                raise AssertionError("attempt marker must precede the first invocation")
            if self.result_path is not None and self.result_path.exists():
                raise AssertionError("result must not exist before the first invocation")
        self.call_count += 1

        parsed: dict[str, Any] = json.loads(request.decode("ascii"))
        keyset = frozenset(parsed)
        self.request_keysets.append(keyset)
        if keyset != REQUEST_KEYS:
            raise AssertionError("child request exposed fields outside the fixed boundary")

        pbm_text = parsed["pbm_base64"]
        if not isinstance(pbm_text, str):
            raise AssertionError("runner emitted a non-string PBM")
        try:
            pbm_bytes = base64.b64decode(pbm_text, validate=True)
        except (ValueError, UnicodeError) as exc:
            raise AssertionError("runner emitted invalid base64") from exc

        structurally_valid = (
            type(parsed["width"]) is int
            and parsed["width"] == SYNTHETIC_PAGE_WIDTH
            and type(parsed["height"]) is int
            and parsed["height"] == SYNTHETIC_PAGE_HEIGHT
            and parsed["scan_bands"] == [list(band) for band in SYNTHETIC_SCAN_BANDS]
            and len(pbm_bytes) == SYNTHETIC_PBM_BYTE_SIZE
            and pbm_bytes.startswith(SYNTHETIC_PBM_HEADER)
        )
        codes = ["insufficient_two_tier_evidence"] if structurally_valid else ["invalid_request"]
        return _process(status="abstained", abstention_codes=codes)


class KP1979V2WorkerBoundaryTests(unittest.TestCase):
    def test_canonical_json_is_pretty_sorted_finite_ascii_with_final_lf(self) -> None:
        self.assertEqual(
            b'{\n  "a": 1,\n  "z": 2\n}\n',
            runner._canonical_json_bytes({"z": 2, "a": 1}),
        )
        with self.assertRaisesRegex(ValueError, "Out of range float values"):
            runner._canonical_json_bytes({"invalid": float("nan")})

    def test_accepts_valid_proposed_semantic_abstention_and_exact_invalid_request(
        self,
    ) -> None:
        proposed = runner.parse_worker_process_result(
            _process(
                status="proposed",
                predictions=[{"lane": 0, "y0": 100, "y1": 196}],
            )
        )
        self.assertEqual("accepted", proposed.disposition)
        self.assertEqual("proposed", proposed.status)
        self.assertEqual(
            (runner.WorkerPrediction(lane=0, y0=100, y1=196),),
            proposed.predictions,
        )

        abstained = runner.parse_worker_process_result(
            _process(
                status="abstained",
                abstention_codes=["insufficient_two_tier_evidence"],
            )
        )
        self.assertEqual("accepted", abstained.disposition)
        self.assertEqual("abstained", abstained.status)
        self.assertEqual((), abstained.predictions)

        rejected = runner.parse_worker_process_result(
            _process(status="abstained", abstention_codes=["invalid_request"])
        )
        self.assertEqual("out_of_contract", rejected.disposition)
        self.assertEqual(("invalid_request",), rejected.abstention_codes)
        self.assertEqual((), rejected.predictions)

        valid_input_adapter = runner.FreshProcessAdapter(
            lambda _: _process(
                status="abstained",
                abstention_codes=["invalid_request"],
            ),
            process_isolation_verified=False,
        )
        valid_input_outcome = valid_input_adapter(_valid_structural_input())
        _assert_failure_sentinel(self, valid_input_outcome)
        self.assertEqual(
            "invalid_request_on_valid_input",
            valid_input_adapter.records[0].failure_code,
        )

        invalid_input_adapter = runner.FreshProcessAdapter(
            lambda _: _process(
                status="abstained",
                abstention_codes=["invalid_request"],
            ),
            process_isolation_verified=False,
        )
        invalid_input_outcome = invalid_input_adapter(_small_input())
        self.assertIsInstance(invalid_input_outcome, SyntheticInputRejection)
        assert isinstance(invalid_input_outcome, SyntheticInputRejection)
        self.assertEqual(runner.TARGET_ALGORITHM_ID, invalid_input_outcome.algorithm_id)
        self.assertEqual(
            "out_of_contract",
            invalid_input_adapter.records[0].disposition,
        )

    def test_every_malformed_or_failed_worker_result_maps_to_the_sentinel(self) -> None:
        prediction = {"lane": 0, "y0": 100, "y1": 196}
        malformed_results = {
            "proposed_empty": _process(status="proposed"),
            "unsorted": _process(
                status="proposed",
                predictions=[
                    {"lane": 1, "y0": 100, "y1": 196},
                    {"lane": 0, "y0": 100, "y1": 196},
                ],
            ),
            "duplicate": _process(
                status="proposed",
                predictions=[prediction, prediction],
            ),
            "unknown_code": _process(
                status="abstained",
                abstention_codes=["unknown_code"],
            ),
            "bool": _process(
                status="proposed",
                predictions=[{"lane": True, "y0": 100, "y1": 196}],
            ),
            "out_of_range": _process(
                status="proposed",
                predictions=[{"lane": 0, "y0": 7000, "y1": 7096}],
            ),
            "non96": _process(
                status="proposed",
                predictions=[{"lane": 0, "y0": 100, "y1": 195}],
            ),
            "stderr": _process(
                status="proposed",
                predictions=[prediction],
                stderr=b"unexpected",
            ),
            "nonzero": _process(
                status="proposed",
                predictions=[prediction],
                returncode=7,
            ),
            "timeout": _process(
                status="proposed",
                predictions=[prediction],
                timed_out=True,
            ),
            "malformed": runner.WorkerProcessResult(0, b"{]\n", b""),
            "second_json": runner.WorkerProcessResult(
                0,
                _response_bytes(
                    status="abstained",
                    abstention_codes=["insufficient_two_tier_evidence"],
                )
                + _response_bytes(
                    status="abstained",
                    abstention_codes=["insufficient_two_tier_evidence"],
                ),
                b"",
            ),
            "oversize": runner.WorkerProcessResult(
                0,
                b"x" * (runner.MAX_STDOUT_BYTES + 1),
                b"",
            ),
        }
        expected_failure_codes = {
            "proposed_empty": "proposed_contract",
            "unsorted": "prediction_order",
            "duplicate": "prediction_order",
            "unknown_code": "abstention_codes",
            "bool": "invalid_prediction",
            "out_of_range": "invalid_prediction",
            "non96": "invalid_prediction",
            "stderr": "stderr_output",
            "nonzero": "nonzero_exit",
            "timeout": "timeout",
            "malformed": "malformed_json",
            "second_json": "noncanonical_stdout",
            "oversize": "stdout_size",
        }
        for name, process in malformed_results.items():
            with self.subTest(name=name):
                adapter = runner.FreshProcessAdapter(
                    lambda _, value=process: value,
                    process_isolation_verified=False,
                )
                proposal = adapter(_small_input())
                _assert_failure_sentinel(self, proposal)
                self.assertEqual(1, adapter.invocation_count)
                self.assertEqual("algorithm_mismatch", adapter.records[0].disposition)
                self.assertEqual(
                    expected_failure_codes[name],
                    adapter.records[0].failure_code,
                )

    def test_transport_exception_maps_to_sentinel(self) -> None:
        def explode(_: bytes) -> runner.WorkerProcessResult:
            raise RuntimeError("fake transport failure")

        adapter = runner.FreshProcessAdapter(
            explode,
            process_isolation_verified=False,
        )
        proposal = adapter(_small_input())
        _assert_failure_sentinel(self, proposal)
        self.assertEqual("transport_exception", adapter.records[0].failure_code)

    def test_out_of_contract_crash_is_never_mapped_to_a_rejection(self) -> None:
        fixture = build_synthetic_fixture("out_of_contract_truncated_payload")
        adapter = runner.FreshProcessAdapter(
            lambda _: runner.WorkerProcessResult(9, b"", b""),
            process_isolation_verified=False,
        )
        outcome = adapter(detector_input_for_fixture(fixture))
        _assert_failure_sentinel(self, outcome)
        self.assertNotIsInstance(outcome, SyntheticInputRejection)
        evaluated = evaluate_synthetic_fixture(fixture, outcome)
        self.assertFalse(evaluated.passed)
        self.assertEqual("abstained", evaluated.outcome_status)

    def test_child_request_contains_exactly_five_answer_free_fields(self) -> None:
        captured: list[dict[str, Any]] = []

        def invoker(request: bytes) -> runner.WorkerProcessResult:
            captured.append(json.loads(request))
            return _process(
                status="abstained",
                abstention_codes=["insufficient_two_tier_evidence"],
            )

        adapter = runner.FreshProcessAdapter(
            invoker,
            process_isolation_verified=False,
        )
        adapter(_small_input())
        self.assertEqual(1, len(captured))
        self.assertEqual(REQUEST_KEYS, set(captured[0]))
        self.assertEqual(5, len(captured[0]))
        for forbidden in (
            "case_id",
            "case_class",
            "truth",
            "references",
            "order",
            "roster_position",
            "scorer",
        ):
            self.assertNotIn(forbidden, captured[0])


class KP1979V2ProcessIsolationTests(unittest.TestCase):
    def test_worker_artifact_and_captures_are_siblings_of_an_empty_cwd(self) -> None:
        wheel_bytes = b"synthetic-test-wheel-not-a-detector"
        captured: dict[str, Any] = {}

        class FakeProcess:
            returncode = 0
            pid = 12345

            def __init__(
                self,
                arguments: Sequence[str],
                keyword_arguments: Mapping[str, Any],
            ) -> None:
                working_directory = Path(keyword_arguments["cwd"])
                detector_wheel = Path(arguments[-1])
                stdout_handle = keyword_arguments["stdout"]
                stderr_handle = keyword_arguments["stderr"]
                captured.update(
                    {
                        "arguments": tuple(arguments),
                        "cwd": working_directory,
                        "cwd_entries": tuple(working_directory.iterdir()),
                        "cwd_mode": stat.S_IMODE(working_directory.stat().st_mode),
                        "detector_wheel": detector_wheel,
                        "detector_wheel_bytes": detector_wheel.read_bytes(),
                        "detector_wheel_mode": stat.S_IMODE(detector_wheel.stat().st_mode),
                        "stdout_path": Path(stdout_handle.name),
                        "stderr_path": Path(stderr_handle.name),
                        "env": dict(keyword_arguments["env"]),
                        "close_fds": keyword_arguments["close_fds"],
                        "shell": keyword_arguments["shell"],
                        "start_new_session": keyword_arguments["start_new_session"],
                    }
                )
                self.stdout_handle = stdout_handle

            def communicate(
                self,
                input: bytes | None = None,
                timeout: float | None = None,
            ) -> tuple[None, None]:
                captured["input"] = input
                captured["timeout"] = timeout
                self.stdout_handle.write(
                    _response_bytes(
                        status="abstained",
                        abstention_codes=["insufficient_two_tier_evidence"],
                    )
                )
                return None, None

        def fake_popen(
            arguments: Sequence[str],
            **keyword_arguments: Any,
        ) -> FakeProcess:
            return FakeProcess(arguments, keyword_arguments)

        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-subprocess-test-") as raw_dir:
            detector_wheel = Path(raw_dir) / "input.whl"
            detector_wheel.write_bytes(wheel_bytes)
            os.chmod(detector_wheel, 0o600)
            with (
                patch.object(
                    runner,
                    "DETECTOR_WHEEL_SHA256",
                    sha256(wheel_bytes).hexdigest(),
                ),
                patch.object(runner.subprocess, "Popen", new=fake_popen),
            ):
                invoker = runner.SubprocessWorkerInvoker(
                    python_executable=Path(sys.executable).resolve(),
                    detector_wheel=detector_wheel,
                )
                process_result = invoker(b"request\n")

        self.assertEqual((), captured["cwd_entries"])
        self.assertEqual(0o700, captured["cwd_mode"])
        working_directory = cast(Path, captured["cwd"])
        copied_wheel = cast(Path, captured["detector_wheel"])
        stdout_path = cast(Path, captured["stdout_path"])
        stderr_path = cast(Path, captured["stderr_path"])
        self.assertEqual(working_directory.parent, copied_wheel.parent)
        self.assertEqual(working_directory.parent, stdout_path.parent)
        self.assertEqual(working_directory.parent, stderr_path.parent)
        self.assertNotEqual(working_directory, copied_wheel.parent)
        self.assertEqual(wheel_bytes, captured["detector_wheel_bytes"])
        self.assertEqual(0o400, captured["detector_wheel_mode"])
        arguments = cast(tuple[str, ...], captured["arguments"])
        self.assertEqual(str(Path(sys.executable).resolve()), arguments[0])
        self.assertEqual(("-I", "-S", "-c"), arguments[1:4])
        self.assertEqual(str(copied_wheel), arguments[-1])
        self.assertEqual(
            {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            captured["env"],
        )
        self.assertNotIn("HOME", cast(dict[str, str], captured["env"]))
        self.assertIs(True, captured["close_fds"])
        self.assertIs(False, captured["shell"])
        self.assertIs(True, captured["start_new_session"])
        self.assertEqual(b"request\n", captured["input"])
        self.assertEqual(runner.WALL_TIMEOUT_SECONDS, captured["timeout"])
        self.assertEqual(
            "accepted",
            runner.parse_worker_process_result(process_result).disposition,
        )

    def test_failed_popen_is_not_counted_as_a_started_process(self) -> None:
        wheel_bytes = b"synthetic-test-wheel-not-a-detector"
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-popen-failure-test-") as raw_dir:
            detector_wheel = Path(raw_dir) / "input.whl"
            detector_wheel.write_bytes(wheel_bytes)
            os.chmod(detector_wheel, 0o600)
            with (
                patch.object(
                    runner,
                    "DETECTOR_WHEEL_SHA256",
                    sha256(wheel_bytes).hexdigest(),
                ),
                patch.object(
                    runner.subprocess,
                    "Popen",
                    side_effect=OSError("synthetic spawn failure"),
                ),
            ):
                invoker = runner.SubprocessWorkerInvoker(
                    python_executable=Path(sys.executable).resolve(),
                    detector_wheel=detector_wheel,
                )
                with self.assertRaisesRegex(OSError, "synthetic spawn failure"):
                    invoker(b"request\n")
        self.assertEqual(0, invoker.started_process_count)

    def test_interpreter_identity_and_state_path_ignore_environment_home(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-interpreter-test-") as raw_dir:
            matching_interpreter = Path(raw_dir) / "matching-python"
            matching_interpreter.write_bytes(b"#!/bin/sh\nexit 0\n")
            os.chmod(matching_interpreter, 0o700)
            different_interpreter = Path(raw_dir) / "python"
            different_interpreter.write_bytes(b"#!/bin/sh\nexit 0\n")
            os.chmod(different_interpreter, 0o700)
            with patch.object(runner.sys, "executable", str(matching_interpreter)):
                accepted = runner._require_regular_owner_file(
                    matching_interpreter,
                    executable=True,
                )
                self.assertEqual(matching_interpreter.resolve(), accepted)
                with self.assertRaisesRegex(
                    runner.KP1979V2RunnerError,
                    "interpreter differs",
                ):
                    runner._require_regular_owner_file(
                        different_interpreter,
                        executable=True,
                    )

        with patch.dict(os.environ, {"HOME": "/tmp/untrusted-home-one"}):
            first_state = runner._canonical_state_directory()
        with patch.dict(os.environ, {"HOME": "/tmp/untrusted-home-two"}):
            second_state = runner._canonical_state_directory()
        self.assertEqual(first_state, second_state)
        self.assertNotIn("untrusted-home", str(first_state))
        self.assertEqual(
            Path(".local/state/indus-open-benchmark/kp1979-v2-qualification-v1"),
            first_state.relative_to(first_state.parents[3]),
        )

    def test_hardlinked_runner_interpreter_remains_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-hardlink-test-") as raw_dir:
            directory = Path(raw_dir)
            interpreter = directory / "python"
            alias = directory / "python-alias"
            interpreter.write_bytes(b"#!/bin/sh\nexit 0\n")
            os.chmod(interpreter, 0o700)
            os.link(interpreter, alias)

            with (
                patch.object(runner.sys, "executable", str(interpreter)),
                self.assertRaisesRegex(
                    runner.KP1979V2RunnerError,
                    "safe owner file",
                ),
            ):
                runner._require_regular_owner_file(
                    interpreter,
                    executable=True,
                )


class KP1979V2OneShotTests(unittest.TestCase):
    def _configuration(
        self,
        output_directory: Path,
    ) -> runner.RunConfiguration:
        return runner.RunConfiguration(
            repository_root=ROOT,
            detector_wheel=output_directory / "unused-detector.whl",
            python_executable=Path(sys.executable),
            integration_commit="a" * 40,
        )

    def test_fake_boundary_runs_full_control_once_and_publishes_safe_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-runner-test-") as raw_dir:
            output_directory = Path(raw_dir)
            configuration = self._configuration(output_directory)
            wheel_bytes = b"synthetic-test-wheel-not-a-detector"
            configuration.detector_wheel.write_bytes(wheel_bytes)
            os.chmod(configuration.detector_wheel, 0o600)
            attempt_marker = output_directory / "attempt-1.started.json"
            result_output = output_directory / "attempt-1.result.json"
            fake = _StructuralFakeInvoker(attempt_marker, result_output)

            def fake_worker_init(
                worker: runner.SubprocessWorkerInvoker,
                *,
                python_executable: Path,
                detector_wheel: Path,
            ) -> None:
                worker._python_executable = python_executable
                worker.started_process_count = 0
                worker._detector_wheel_bytes = detector_wheel.read_bytes()

            def fake_worker_call(
                worker: runner.SubprocessWorkerInvoker,
                request: bytes,
            ) -> runner.WorkerProcessResult:
                worker.started_process_count += 1
                return fake(request)

            with (
                patch.object(runner, "_validate_repository", return_value=ROOT),
                patch.object(
                    runner,
                    "_validate_detector_wheel",
                    return_value=(configuration.detector_wheel, 12345),
                ),
                patch.object(
                    runner,
                    "_require_regular_owner_file",
                    return_value=configuration.python_executable,
                ),
                patch.object(
                    runner,
                    "_canonical_state_directory",
                    return_value=output_directory,
                ),
                patch.object(
                    runner.SubprocessWorkerInvoker,
                    "__init__",
                    new=fake_worker_init,
                ),
                patch.object(
                    runner.SubprocessWorkerInvoker,
                    "__call__",
                    new=fake_worker_call,
                ),
            ):
                result = cast(
                    dict[str, Any],
                    runner.run_one_shot(configuration),
                )

            self.assertEqual(runner.FRESH_PROCESS_COUNT, fake.call_count)
            self.assertEqual(
                [REQUEST_KEYS] * runner.FRESH_PROCESS_COUNT,
                [set(keys) for keys in fake.request_keysets],
            )
            self.assertEqual("not_qualified", result["terminal_status"])
            self.assertIs(False, result["advance_to_provisional_extraction"])
            self.assertEqual(
                runner.FRESH_PROCESS_COUNT,
                result["transport_summary"]["invocation_count"],
            )
            self.assertEqual(21, result["transport_summary"]["accepted_count"])
            self.assertEqual(
                4,
                result["transport_summary"]["out_of_contract_rejection_count"],
            )
            self.assertEqual(0, result["transport_summary"]["transport_failure_count"])
            self.assertEqual("not_qualified", result["control_report"]["status"])
            self.assertIs(
                True,
                result["execution_boundary"]["fresh_process_per_invocation"],
            )
            self.assertEqual(
                runner.FRESH_PROCESS_COUNT,
                result["execution_boundary"]["started_process_count"],
            )
            self.assertTrue(all(value is False for value in result["claim_scope"].values()))
            self.assertIs(
                False,
                result["mandatory_gates"]["all_mandatory_gates_passed"],
            )
            self.assertEqual("blocked", result["deployment_decision"]["status"])
            self.assertIs(
                False,
                result["deployment_decision"]["machine_development_candidate_generation_allowed"],
            )

            marker = json.loads(attempt_marker.read_bytes())
            recorded_result = json.loads(result_output.read_bytes())
            self.assertEqual("started", marker["state"])
            self.assertEqual(result, recorded_result)
            self.assertEqual(
                0o600,
                stat.S_IMODE(attempt_marker.stat().st_mode),
            )
            self.assertEqual(
                0o600,
                stat.S_IMODE(result_output.stat().st_mode),
            )

            _, result_schema, _ = runner._validate_plan_and_schemas(ROOT)
            Draft202012Validator(result_schema).validate(recorded_result)
            unsafe_variants = []
            for path, unsafe_value in (
                (("claim_scope", "decipherment"), True),
                (("claim_scope", "prize_claim"), True),
                (("terminal_status",), "qualified"),
                (("advance_to_provisional_extraction",), True),
            ):
                unsafe = copy.deepcopy(recorded_result)
                target: dict[str, object] = unsafe
                for key in path[:-1]:
                    nested = target[key]
                    assert isinstance(nested, dict)
                    target = nested
                target[path[-1]] = unsafe_value
                unsafe_variants.append((path, unsafe))
            for path, unsafe in unsafe_variants:
                with (
                    self.subTest(unsafe_path=path),
                    self.assertRaises(ValidationError),
                ):
                    Draft202012Validator(result_schema).validate(unsafe)

    def test_one_spawn_failure_records_short_count_and_valid_not_qualified_result(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-short-spawn-test-") as raw_dir:
            output_directory = Path(raw_dir)
            configuration = self._configuration(output_directory)
            wheel_bytes = b"synthetic-test-wheel-not-a-detector"
            configuration.detector_wheel.write_bytes(wheel_bytes)
            os.chmod(configuration.detector_wheel, 0o600)
            attempt_marker = output_directory / "attempt-1.started.json"
            result_output = output_directory / "attempt-1.result.json"
            fake = _StructuralFakeInvoker(attempt_marker, result_output)

            def fake_worker_init(
                worker: runner.SubprocessWorkerInvoker,
                *,
                python_executable: Path,
                detector_wheel: Path,
            ) -> None:
                worker._python_executable = python_executable
                worker.started_process_count = 0
                worker._detector_wheel_bytes = detector_wheel.read_bytes()

            def one_spawn_failure(
                worker: runner.SubprocessWorkerInvoker,
                request: bytes,
            ) -> runner.WorkerProcessResult:
                response = fake(request)
                if fake.call_count == 7:
                    raise OSError("synthetic spawn failure")
                worker.started_process_count += 1
                return response

            with (
                patch.object(runner, "_validate_repository", return_value=ROOT),
                patch.object(
                    runner,
                    "_validate_detector_wheel",
                    return_value=(configuration.detector_wheel, 12345),
                ),
                patch.object(
                    runner,
                    "_require_regular_owner_file",
                    return_value=configuration.python_executable,
                ),
                patch.object(
                    runner,
                    "_canonical_state_directory",
                    return_value=output_directory,
                ),
                patch.object(
                    runner.SubprocessWorkerInvoker,
                    "__init__",
                    new=fake_worker_init,
                ),
                patch.object(
                    runner.SubprocessWorkerInvoker,
                    "__call__",
                    new=one_spawn_failure,
                ),
            ):
                result = cast(
                    dict[str, Any],
                    runner.run_one_shot(configuration),
                )

            self.assertEqual(runner.FRESH_PROCESS_COUNT, fake.call_count)
            self.assertEqual("not_qualified", result["terminal_status"])
            self.assertIs(False, result["advance_to_provisional_extraction"])
            self.assertEqual(
                runner.FRESH_PROCESS_COUNT - 1,
                result["execution_boundary"]["started_process_count"],
            )
            self.assertIs(
                False,
                result["execution_boundary"]["fresh_process_per_invocation"],
            )
            self.assertIs(
                False,
                result["mandatory_gates"]["fresh_process_count_verified"],
            )
            self.assertEqual(
                1,
                result["transport_summary"]["transport_failure_count"],
            )
            self.assertEqual(
                [{"code": "transport_exception", "count": 1}],
                result["transport_summary"]["failure_codes"],
            )
            recorded_result = json.loads(result_output.read_bytes())
            self.assertEqual(result, recorded_result)
            _, result_schema, _ = runner._validate_plan_and_schemas(ROOT)
            Draft202012Validator(result_schema).validate(recorded_result)

    def test_existing_marker_or_result_prevents_any_invocation(self) -> None:
        for existing_name in ("attempt-1.started.json", "attempt-1.result.json"):
            with (
                self.subTest(existing_name=existing_name),
                tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-existing-test-") as raw_dir,
            ):
                output_directory = Path(raw_dir)
                configuration = self._configuration(output_directory)
                existing = output_directory / existing_name
                existing.write_bytes(b"preserve")
                os.chmod(existing, 0o600)
                fake = _StructuralFakeInvoker()

                def fake_worker_call(
                    _: runner.SubprocessWorkerInvoker,
                    request: bytes,
                    bound_fake: _StructuralFakeInvoker = fake,
                ) -> runner.WorkerProcessResult:
                    return bound_fake(request)

                with (
                    patch.object(
                        runner,
                        "_validate_repository",
                        return_value=ROOT,
                    ),
                    patch.object(
                        runner,
                        "_validate_detector_wheel",
                        return_value=(configuration.detector_wheel, 12345),
                    ),
                    patch.object(
                        runner,
                        "_require_regular_owner_file",
                        return_value=configuration.python_executable,
                    ),
                    patch.object(
                        runner,
                        "_validate_plan_and_schemas",
                        return_value=({}, {}, {}),
                    ),
                    patch.object(
                        runner,
                        "_canonical_state_directory",
                        return_value=output_directory,
                    ),
                    patch.object(
                        runner.SubprocessWorkerInvoker,
                        "__call__",
                        new=fake_worker_call,
                    ),
                    self.assertRaisesRegex(
                        runner.KP1979V2RunnerError,
                        "already exists",
                    ),
                ):
                    runner.run_one_shot(configuration)
                self.assertEqual(0, fake.call_count)
                self.assertEqual(b"preserve", existing.read_bytes())

    def test_atomic_result_publication_never_replaces_an_existing_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-publish-test-") as raw_dir:
            output_directory = Path(raw_dir)
            existing = output_directory / "result.json"
            existing.write_bytes(b"original")
            os.chmod(existing, 0o600)
            with self.assertRaises(FileExistsError):
                runner._publish_result(output_directory, existing.name, b"replacement")
            self.assertEqual(b"original", existing.read_bytes())
            self.assertEqual(
                {existing.name},
                {path.name for path in output_directory.iterdir()},
            )

    def test_non_owner_only_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="indus-kp1979-v2-mode-test-") as raw_dir:
            output_directory = Path(raw_dir)
            os.chmod(output_directory, 0o750)
            with self.assertRaisesRegex(
                runner.KP1979V2RunnerError,
                "owner-only",
            ):
                runner._validate_owner_output_paths(
                    output_directory / "attempt.json",
                    output_directory / "result.json",
                )


if __name__ == "__main__":
    unittest.main()
