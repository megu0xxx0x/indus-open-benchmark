"""Network-free, no-replace CLI for the development-only MTAAC V3 run."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from indusbench.v3dev.plan import (
    MAX_V3_DEVELOPMENT_PLAN_BYTES,
    V3_DEVELOPMENT_PLAN_SHA256,
    V3DevelopmentPlanError,
    validate_v3_development_plan,
)

MAX_MTAAC_V3_ARCHIVE_BYTES: Final = 256 * 1024 * 1024
MAX_MTAAC_V3_REPORT_BYTES: Final = 4 * 1024 * 1024
MTAAC_V3_REPORT_VERSION: Final = "mtaac-v3-development-report-v1"

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_UNTAGGED_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_P_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])P[0-9]{6}(?![0-9])")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_RAW_IDENTIFIER_PREFIX = re.compile(
    r"mtaac-(?:document-source-id|token-source-order|word-form|artificial-word-form)-sha256-v1:"
)
_RAW_ANNOTATION_WORD = re.compile(r"\b(?:FORM|SEGM|XPOSTAG)\b", re.IGNORECASE)

_PUBLIC_REPORT_KEYS: Final = frozenset(
    {
        "analysis",
        "report_version",
        "terminal_status",
        "development_only",
        "model_executed",
        "scientific_metrics_emitted",
        "plan_sha256",
        "implementation_commit",
        "parent_commitments",
        "data_boundary",
        "model_contract",
        "nested_development",
        "final_development_model",
        "claim_scope",
    }
)
_EXPECTED_PARENT_COMMITMENTS: Final = {
    "gateway_version": "mtaac-v2-training-gateway-v1",
    "mtaac_source_commit": "66e0643efd230401210e27db353ebb6d7228b1bb",
    "v2_freeze_commit": "37157f1411a55ffd91b7327afaca8fc1080fa708",
    "source_archive_sha256": (
        "sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091"
    ),
    "selected_manifest_sha256": (
        "sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e"
    ),
    "evaluation_corpus_sha256": (
        "sha256:e7d6f8c9a8c090bb33ef4ba3703c1b36fe0519086efa75ff70d1ba53a8bf9312"
    ),
    "v2_protocol_sha256": (
        "sha256:25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892"
    ),
    "v2_split_manifest_sha256": (
        "sha256:7249c8fe1d3efc95b42cc9e0a9378550addb64f5b992f89af99dd852b83c5c30"
    ),
}
_EXPECTED_DATA_BOUNDARY: Final = {
    "model_training_family_count": 271,
    "v2_holdout_family_count_excluded": 90,
    "v2_holdout_exposed_to_model": False,
    "v2_holdout_scored": False,
    "reserved_validation_source_loaded": False,
    "regimes_used": ["clean", "mild"],
    "replica_index_used": 0,
}
_FORBIDDEN_REPORT_KEYS: Final = frozenset(
    {
        "archive_member",
        "archive_members",
        "archive_member_path",
        "document",
        "documents",
        "document_id",
        "document_ids",
        "document_identifier",
        "document_identifiers",
        "document_key",
        "document_keys",
        "families",
        "family_id",
        "family_ids",
        "family_membership",
        "file_path",
        "fold_family_ids",
        "fold_members",
        "fold_membership",
        "form",
        "input_path",
        "local_path",
        "member",
        "members",
        "member_name",
        "member_names",
        "member_path",
        "member_paths",
        "observed_form_id",
        "observation_id",
        "output_path",
        "p_id",
        "per_document",
        "per_document_metrics",
        "per_family",
        "per_family_metrics",
        "per_member",
        "per_token",
        "pid",
        "raw_form",
        "raw_value",
        "segm",
        "source_document_identifier",
        "source_identifier",
        "source_path",
        "token",
        "tokens",
        "token_id",
        "token_ids",
        "token_key",
        "token_keys",
        "xpostag",
    }
)


class V3DevelopmentCLIError(ValueError):
    """Raised when local CLI data cannot cross the public output boundary."""


def _canonical_json(value: object) -> bytes:
    try:
        raw = (
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
        raise V3DevelopmentCLIError("development report is not canonical JSON data") from error
    if len(raw) > MAX_MTAAC_V3_REPORT_BYTES:
        raise V3DevelopmentCLIError("development report exceeds the public byte limit")
    return raw


def _validate_public_scalar(value: object, *, key: str | None) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise V3DevelopmentCLIError("public report contains a non-finite number")
    if not isinstance(value, str):
        raise V3DevelopmentCLIError("public report contains a non-JSON value")
    if len(value) > 10_000:
        raise V3DevelopmentCLIError("public report contains an oversized string")
    folded = value.casefold()
    if "oracc" in folded:
        raise V3DevelopmentCLIError("public report names the reserved validation source")
    if (
        _P_IDENTIFIER.search(value) is not None
        or _RAW_IDENTIFIER_PREFIX.search(folded) is not None
        or _RAW_ANNOTATION_WORD.search(value) is not None
        or value.startswith(("/", "~"))
        or _WINDOWS_ABSOLUTE_PATH.match(value) is not None
        or "file://" in folded
    ):
        raise V3DevelopmentCLIError("public report contains item-level or local source data")
    if _UNTAGGED_SHA256.fullmatch(value) is not None:
        raise V3DevelopmentCLIError("public report contains an unlabelled item fingerprint")
    if key is not None and key.endswith("_sha256") and not value.startswith("sha256:"):
        raise V3DevelopmentCLIError("public report contains an untagged SHA-256 commitment")


def _validate_public_value(
    value: object,
    *,
    key: str | None = None,
    depth: int = 0,
    budget: list[int],
) -> None:
    if depth > 32:
        raise V3DevelopmentCLIError("public report nesting exceeds the fixed limit")
    budget[0] += 1
    if budget[0] > 100_000:
        raise V3DevelopmentCLIError("public report structure exceeds the fixed limit")
    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str) or not nested_key:
                raise V3DevelopmentCLIError("public report keys must be non-empty strings")
            normalized_key = nested_key.casefold().replace("-", "_")
            if (
                normalized_key in _FORBIDDEN_REPORT_KEYS
                or normalized_key.startswith("raw_")
                or normalized_key.endswith("_path")
                or "oracc" in normalized_key
            ):
                raise V3DevelopmentCLIError("public report contains a forbidden field")
            _validate_public_value(
                nested_value,
                key=normalized_key,
                depth=depth + 1,
                budget=budget,
            )
        return
    if isinstance(value, (list, tuple)):
        for nested_value in value:
            _validate_public_value(
                nested_value,
                key=key,
                depth=depth + 1,
                budget=budget,
            )
        return
    _validate_public_scalar(value, key=key)


def validate_public_development_report(
    report: object,
    *,
    expected_implementation_commit: str | None = None,
) -> dict[str, Any]:
    """Enforce the aggregate-only success-report boundary before publication."""

    if not isinstance(report, dict) or set(report) != _PUBLIC_REPORT_KEYS:
        raise V3DevelopmentCLIError("development report root does not match the closed contract")
    if (
        report["analysis"] != "mtaac_v3_structural_development"
        or report["report_version"] != MTAAC_V3_REPORT_VERSION
        or report["terminal_status"] != "development_complete"
        or report["development_only"] is not True
        or report["model_executed"] is not True
        or report["scientific_metrics_emitted"] is not True
        or report["plan_sha256"] != V3_DEVELOPMENT_PLAN_SHA256
        or not isinstance(report["implementation_commit"], str)
        or _COMMIT.fullmatch(report["implementation_commit"]) is None
        or (
            expected_implementation_commit is not None
            and report["implementation_commit"] != expected_implementation_commit
        )
    ):
        raise V3DevelopmentCLIError("development report assertions do not match the plan")
    for field_name in (
        "parent_commitments",
        "data_boundary",
        "model_contract",
        "nested_development",
        "final_development_model",
        "claim_scope",
    ):
        if not isinstance(report[field_name], dict):
            raise V3DevelopmentCLIError("development report aggregate sections must be objects")
    if report["parent_commitments"] != _EXPECTED_PARENT_COMMITMENTS:
        raise V3DevelopmentCLIError("development report parent commitments disagree")
    if report["data_boundary"] != _EXPECTED_DATA_BOUNDARY:
        raise V3DevelopmentCLIError("development report data boundary assertions disagree")
    _validate_public_value(report, budget=[0])
    _canonical_json(report)
    return report


def _read_regular_bytes(path: Path, *, max_bytes: int) -> bytes:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise V3DevelopmentCLIError("input is not a single-link regular file")
        if before.st_size > max_bytes:
            raise V3DevelopmentCLIError("input exceeds the byte limit")
        chunks: list[bytes] = []
        byte_count = 0
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            while True:
                chunk = handle.read(min(1024 * 1024, max_bytes + 1 - byte_count))
                if not chunk:
                    after = os.fstat(handle.fileno())
                    break
                chunks.append(chunk)
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise V3DevelopmentCLIError("input exceeds the byte limit")
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise V3DevelopmentCLIError("input changed while it was read")
        return b"".join(chunks)
    except OSError as error:
        raise V3DevelopmentCLIError("input could not be read safely") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _output_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _write_no_replace(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _build_training_bundle(archive_bytes: bytes) -> Any:
    from indusbench.v3dev.mtaac_training import build_mtaac_v2_training_bundle

    return build_mtaac_v2_training_bundle(archive_bytes)


def _run_v3_development(
    bundle: Any,
    *,
    plan_bytes: bytes,
    implementation_commit: str,
) -> dict[str, Any]:
    from indusbench.v3dev.runner import run_v3_development

    return run_v3_development(
        bundle,
        plan_bytes=plan_bytes,
        implementation_commit=implementation_commit,
    )


def _print_json(value: object) -> None:
    sys.stdout.write(_canonical_json(value).decode("utf-8"))


def _fail(error_code: str, message: str, *, status: int = 2) -> int:
    _print_json(
        {
            "analysis": "mtaac_v3_structural_development",
            "development_only": True,
            "error": message,
            "error_code": error_code,
            "model_executed": False,
            "scientific_metrics_emitted": False,
            "terminal_status": "error",
        }
    )
    return status


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="indusbench-v3dev-mtaac",
        description="Run the exact development-only MTAAC V3 plan without network access.",
    )
    parser.add_argument("archive", type=Path, help="local exact pinned MTAAC archive")
    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
        help="local exact frozen MTAAC V3 development plan",
    )
    parser.add_argument(
        "--implementation-commit",
        required=True,
        help="published lowercase 40-hex implementation commit",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new aggregate JSON report path; existing paths are never replaced",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the one-purpose development CLI with path-redacted failures."""

    args = _parser().parse_args(list(argv) if argv is not None else None)
    if _COMMIT.fullmatch(args.implementation_commit) is None:
        return _fail(
            "implementation_commit_invalid",
            "the implementation commit must be lowercase 40-hex",
        )
    try:
        if _output_exists(args.output):
            return _fail(
                "output_exists",
                "the aggregate output target already exists",
                status=1,
            )
    except (OSError, ValueError):
        return _fail(
            "output_uninspectable",
            "the aggregate output target could not be inspected safely",
        )

    try:
        plan_bytes = _read_regular_bytes(
            args.plan,
            max_bytes=MAX_V3_DEVELOPMENT_PLAN_BYTES,
        )
    except (OSError, ValueError):
        return _fail("plan_unreadable", "the development plan could not be read safely")
    try:
        validate_v3_development_plan(plan_bytes)
    except V3DevelopmentPlanError:
        return _fail("plan_rejected", "the development plan does not match the exact freeze")

    try:
        archive_bytes = _read_regular_bytes(
            args.archive,
            max_bytes=MAX_MTAAC_V3_ARCHIVE_BYTES,
        )
    except (OSError, ValueError):
        return _fail("archive_unreadable", "the MTAAC archive could not be read safely")

    try:
        if _output_exists(args.output):
            return _fail(
                "output_exists",
                "the aggregate output target already exists",
                status=1,
            )
    except (OSError, ValueError):
        return _fail(
            "output_uninspectable",
            "the aggregate output target could not be inspected safely",
        )

    try:
        bundle = _build_training_bundle(archive_bytes)
    except Exception:
        return _fail(
            "archive_rejected",
            "the MTAAC archive failed the exact V3 training boundary",
        )
    try:
        report = _run_v3_development(
            bundle,
            plan_bytes=plan_bytes,
            implementation_commit=args.implementation_commit,
        )
    except Exception:
        return _fail(
            "development_rejected",
            "the fixed V3 development run failed closed",
        )
    try:
        validate_public_development_report(
            report,
            expected_implementation_commit=args.implementation_commit,
        )
        raw_report = _canonical_json(report)
    except (TypeError, ValueError):
        return _fail(
            "report_rejected",
            "the development report failed the aggregate public boundary",
        )

    try:
        _write_no_replace(args.output, raw_report)
    except FileExistsError:
        return _fail(
            "output_exists",
            "the aggregate output target already exists",
            status=1,
        )
    except (OSError, ValueError):
        return _fail(
            "output_write_failed",
            "the aggregate output could not be written safely",
        )
    sys.stdout.write(raw_report.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
