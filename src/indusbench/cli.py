"""Command-line interface for rights-aware corpus and evaluation infrastructure."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
import json
import math
import os
import re
import secrets
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from indusbench import __version__
from indusbench.audit import audit_leakage
from indusbench.baseline import (
    AddOneNGramBaseline,
    UnigramBaseline,
    score_missing_signs,
)
from indusbench.benchmark_lock import (
    BenchmarkLockError,
    build_benchmark_definition,
    verify_benchmark_definition,
)
from indusbench.context_anchor import (
    derive_context_anchor_registry,
    validate_context_anchor_registry,
)
from indusbench.controls import global_sign_shuffle
from indusbench.identifiability import DegradationConfig, run_identifiability_gate
from indusbench.importers.mayig import import_mayig_corpus
from indusbench.io import (
    CorpusFormatError,
    encode_json,
    read_json,
    read_jsonl,
    write_json,
    write_jsonl,
)
from indusbench.kp1979 import (
    MAX_CONTRACT_BYTES as KP1979_MAX_CONTRACT_BYTES,
)
from indusbench.kp1979 import (
    MAX_PAGE_MAP_BYTES as KP1979_MAX_PAGE_MAP_BYTES,
)
from indusbench.kp1979 import (
    MAX_PAGE_PBM_BYTES as KP1979_MAX_PAGE_PBM_BYTES,
)
from indusbench.kp1979 import (
    MAX_SOURCE_BYTES as KP1979_MAX_SOURCE_BYTES,
)
from indusbench.kp1979 import (
    KP1979SourceError,
    audit_kp1979_layout,
    verify_kp1979_source,
)
from indusbench.kp1979_label_reference import (
    MAX_ASSIGNMENT_BYTES as KP1979_MAX_LABEL_REFERENCE_ASSIGNMENT_BYTES,
)
from indusbench.kp1979_label_reference import (
    MAX_REVIEW_BYTES as KP1979_MAX_LABEL_REFERENCE_REVIEW_BYTES,
)
from indusbench.kp1979_label_reference import (
    PARTITION_PAGES as KP1979_LABEL_REFERENCE_PARTITION_PAGES,
)
from indusbench.kp1979_label_reference import (
    KP1979LabelReferenceError,
    build_label_reference_assignment,
    build_machine_development_label_reference_review,
    verify_independent_label_reference_review_bytes,
    verify_label_reference_assignment_bytes,
    verify_machine_development_label_reference_review_bytes,
)
from indusbench.kp1979_row_assignment import (
    MAX_ASSIGNMENT_BYTES as KP1979_MAX_ROW_ASSIGNMENT_BYTES,
)
from indusbench.kp1979_row_assignment import (
    KP1979RowAssignmentError,
    build_row_assignment,
    verify_row_assignment_bytes,
)
from indusbench.kp1979_sign_template_roster import (
    MAX_CATALOG_BYTES as KP1979_MAX_SIGN_TEMPLATE_CATALOG_BYTES,
)
from indusbench.kp1979_sign_template_roster import (
    MAX_GEOMETRY_MANIFEST_BYTES as KP1979_MAX_SIGN_TEMPLATE_GEOMETRY_BYTES,
)
from indusbench.kp1979_sign_template_roster import (
    MAX_INPUT_ITEMS as KP1979_MAX_SIGN_TEMPLATE_INPUT_ITEMS,
)
from indusbench.kp1979_sign_template_roster import (
    MAX_TEMPLATE_PBM_BYTES as KP1979_MAX_SIGN_TEMPLATE_PBM_BYTES,
)
from indusbench.kp1979_sign_template_roster import (
    MAX_TEMPLATE_ROSTER_BYTES as KP1979_MAX_SIGN_TEMPLATE_ROSTER_BYTES,
)
from indusbench.kp1979_sign_template_roster import (
    KP1979SignTemplateRosterError,
    build_sign_template_roster,
    verify_sign_template_roster_bytes,
)
from indusbench.kp1979_synthetic_control import (
    TARGET_ALGORITHM_ID as KP1979_SYNTHETIC_TARGET_ALGORITHM_ID,
)
from indusbench.kp1979_synthetic_control import (
    SyntheticControlReport,
    run_synthetic_control,
)
from indusbench.kp1982 import (
    MAX_CONTRACT_BYTES as KP1982_MAX_CONTRACT_BYTES,
)
from indusbench.kp1982 import (
    MAX_PAGE_PBM_BYTES as KP1982_MAX_PAGE_PBM_BYTES,
)
from indusbench.kp1982 import (
    MAX_SOURCE_BYTES as KP1982_MAX_SOURCE_BYTES,
)
from indusbench.kp1982 import KP1982SourceError, verify_kp1982_source
from indusbench.kp1982_bootstrap import (
    MAX_ASSIGNMENT_BYTES as KP1982_MAX_BOOTSTRAP_ASSIGNMENT_BYTES,
)
from indusbench.kp1982_bootstrap import (
    KP1982BootstrapError,
    build_bootstrap_assignment,
    verify_bootstrap_assignment_bytes,
)
from indusbench.kp1982_bootstrap_review import (
    MAX_REVIEW_BYTES as KP1982_MAX_BOOTSTRAP_REVIEW_BYTES,
)
from indusbench.kp1982_bootstrap_review import (
    KP1982BootstrapReviewError,
    compare_independent_review_bytes,
    verify_adjudication_bytes,
    verify_independent_review_bytes,
    verify_stripped_bootstrap_assignment_bytes,
)
from indusbench.kp1982_layout import (
    MAX_PROPOSAL_BYTES as KP1982_MAX_LAYOUT_PROPOSAL_BYTES,
)
from indusbench.kp1982_layout import (
    MAX_SEED_BYTES as KP1982_MAX_LAYOUT_SEED_BYTES,
)
from indusbench.kp1982_layout import (
    KP1982LayoutError,
    build_layout_proposal,
    verify_layout_proposal_bytes,
)
from indusbench.manifest import build_manifest, corpus_digest, sha256_json
from indusbench.mtaac import MAX_ARCHIVE_BYTES as MTAAC_MAX_ARCHIVE_BYTES
from indusbench.mtaac_control import (
    MTAAC_CONTROL_PROTOCOL_SHA256,
    MTAACControlAttestation,
    MTAACControlError,
    evaluate_mtaac_control_archive,
)
from indusbench.museum_intake import (
    DEFAULT_MAX_JSON_BYTES,
    DEFAULT_MAX_MEDIA_BYTES,
    DEFAULT_MAX_MEDIA_COUNT,
    DEFAULT_MAX_TOTAL_JSON_BYTES,
    DEFAULT_MAX_TOTAL_MEDIA_BYTES,
    download_intake_media,
    fetch_cleveland_intake,
    fetch_met_intake,
    fetch_policy_documents,
    policy_manifest_entry,
    validate_intake_semantics,
    verify_intake_bundle,
    verify_policy_evidence,
    write_intake_raw_response,
    write_policy_document,
)
from indusbench.museum_review import (
    build_blind_review_materials,
    build_packet_manifest,
    build_reviewer_manifest,
    render_review_instructions,
    validate_custody_semantics,
    validate_packet_manifest_semantics,
    validate_review_submission,
    validate_reviewer_manifest_semantics,
    validate_subject_semantics,
)
from indusbench.museum_review_ledger import (
    audit_review_chain,
    build_ledger_manifest,
    canonical_review_bytes,
    review_digest,
    review_relative_path,
    validate_ledger_manifest,
)
from indusbench.null_evaluation import evaluate_shuffle_null
from indusbench.oracc_ed3b import (
    MAX_ARCHIVE_BYTES as ORACC_ED3B_MAX_ARCHIVE_BYTES,
)
from indusbench.oracc_ed3b import (
    MAX_PROTOCOL_BYTES as ORACC_ED3B_MAX_PROTOCOL_BYTES,
)
from indusbench.oracc_ed3b import (
    ORACCEd3bError,
    verify_oracc_ed3b_archive,
    verify_oracc_ed3b_protocol_bytes,
)
from indusbench.penn_metadata import (
    PENN_CSV_URL,
    parse_penn_csv_snapshot,
    validate_penn_metadata_semantics,
)
from indusbench.private_readiness import (
    INTENDED_USES as PRIVATE_READINESS_INTENDED_USES,
)
from indusbench.private_readiness import (
    PrivateReadinessError,
    _close_pinned_directory,
    _open_pinned_directory,
    _verify_pinned_directory,
    audit_private_corpus,
    read_private_policy,
    safe_failure_summary,
)
from indusbench.private_review_bundle import (
    PrivateReviewError,
    build_private_review_bundle,
    publish_private_review_bundle,
    read_private_review_bundle,
    safe_private_review_summary,
)
from indusbench.quarantine import (
    CorpusQuarantineError,
    QuarantineReport,
    inspect_corpus_quarantine,
    require_corpus_permitted,
)
from indusbench.schema_validation import (
    SchemaDependencyMissing,
    compile_schema_validator,
    validate_artifact_rows,
    validate_schema_instance,
)
from indusbench.smithsonian_metadata import (
    MAX_CONTAINER_BYTES as SMITHSONIAN_MAX_JSONL_BYTES,
)
from indusbench.smithsonian_metadata import (
    SmithsonianMetadataError,
    normalize_smithsonian_record,
)
from indusbench.split_manifest import build_split_manifest
from indusbench.splits import deterministic_leakage_safe_split
from indusbench.submission_commitment import (
    SubmissionCommitmentError,
    build_submission_commitment,
    read_submission_commitment,
    verify_submission_commitment,
)
from indusbench.transcription_admission import require_admitted_transcription_corpus
from indusbench.transcription_review import (
    TranscriptionReviewError,
    compare_independent_transcriptions,
    promote_adjudicated_transcription,
    sha256_bytes,
    validate_sign_inventory,
    validate_transcription_review,
)
from indusbench.treewidth_audit import evaluate_treewidth_nulls
from indusbench.validation import SCHEMA_VERSION, has_errors, validate_corpus

MUSEUM_BUNDLE_VERSION = "0.2.0"
MUSEUM_SCIENTIFIC_SCOPE = (
    "untranscribed rights and media staging; no physical-side, sign, "
    "language, or translation inference"
)
MUSEUM_MAX_INDEX_BYTES = 64 * 1024 * 1024
MUSEUM_MAX_BUNDLE_DEPTH = 8
MUSEUM_MAX_SEALED_REVIEW_COUNT = 100_000
PENN_MAX_CSV_BYTES = 256 * 1024 * 1024
PENN_MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
MTAAC_MAX_PROTOCOL_BYTES = 1024 * 1024
CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
STABLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SEALED_REVIEW_PATH_PATTERN = re.compile(
    r"^(submissions|adjudications)/sha256-([0-9a-f]{64})\.json$"
)


class _CommittedDurabilityUnknown(OSError):
    """Raised after publication when directory-entry durability is unknown."""

    def __init__(
        self,
        error_number: int,
        message: str,
        filename: str,
        *,
        content_verified: bool,
    ) -> None:
        super().__init__(error_number, message, filename)
        self.content_verified = content_verified


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "+Infinity" if value > 0 else "-Infinity"
    return value


def _print_json(value: Any) -> None:
    json.dump(_jsonable(value), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _default_artifact_schema() -> Path | None:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / "artifact.schema.json"
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "schemas/artifact.schema.json"
    )
    return Path(str(package_candidate)) if package_candidate.is_file() else None


def _default_schema(filename: str) -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / filename
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(f"schemas/{filename}")
    return Path(str(package_candidate))


def _default_source_registry() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "registry" / "sources.json"
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath("registry/sources.json")
    return Path(str(package_candidate))


def _default_kp1982_contract() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "registry" / "kp1982_batch0.json"
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "registry/kp1982_batch0.json"
    )
    return Path(str(package_candidate))


def _default_kp1979_contract() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "registry" / "kp1979_corpus.json"
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "registry/kp1979_corpus.json"
    )
    return Path(str(package_candidate))


def _default_kp1979_page_map() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "registry" / "kp1979_page_map.json"
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "registry/kp1979_page_map.json"
    )
    return Path(str(package_candidate))


def _default_kp1982_layout_seed() -> Path:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "registry" / "kp1982_batch0_layout_seed.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "registry/kp1982_batch0_layout_seed.json"
    )
    return Path(str(package_candidate))


def _default_quarantine_registry() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "registry" / "quarantine.json"
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath("registry/quarantine.json")
    return Path(str(package_candidate))


def _default_research_registry() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "registry" / "research_landscape.json"
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "registry/research_landscape.json"
    )
    return Path(str(package_candidate))


def _quarantine_policy(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_registry = read_json(args.source_registry)
    quarantine_registry = read_json(args.quarantine_registry)
    if not isinstance(source_registry, dict):
        raise CorpusFormatError("source registry must be a JSON object")
    if not isinstance(quarantine_registry, dict):
        raise CorpusFormatError("quarantine registry must be a JSON object")
    return source_registry, quarantine_registry


def _inspect_quarantine(
    records: list[dict[str, Any]],
    args: argparse.Namespace,
    *,
    purpose: str,
) -> QuarantineReport:
    if purpose != "schema_validation":
        require_admitted_transcription_corpus(records)
    source_registry, quarantine_registry = _quarantine_policy(args)
    return inspect_corpus_quarantine(
        records,
        source_registry=source_registry,
        quarantine_manifest=quarantine_registry,
        purpose=purpose,
    )


def _require_quarantine(
    records: list[dict[str, Any]],
    args: argparse.Namespace,
    *,
    purpose: str,
) -> QuarantineReport:
    require_admitted_transcription_corpus(records)
    source_registry, quarantine_registry = _quarantine_policy(args)
    return require_corpus_permitted(
        records,
        source_registry=source_registry,
        quarantine_manifest=quarantine_registry,
        purpose=purpose,
    )


def _default_museum_candidate_registry() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "registry" / "museum_candidates.json"
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "registry/museum_candidates.json"
    )
    return Path(str(package_candidate))


def _default_museum_intake_schema() -> Path | None:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "schemas" / ("museum-intake.schema.json")
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "schemas/museum-intake.schema.json"
    )
    return Path(str(package_candidate)) if package_candidate.is_file() else None


def _default_museum_review_subject_schema() -> Path | None:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "schemas" / "museum-review-subject.schema.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "schemas/museum-review-subject.schema.json"
    )
    return Path(str(package_candidate)) if package_candidate.is_file() else None


def _default_museum_review_schema() -> Path | None:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "schemas" / "museum-review.schema.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "schemas/museum-review.schema.json"
    )
    return Path(str(package_candidate)) if package_candidate.is_file() else None


def _default_museum_review_ledger_schema() -> Path | None:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "schemas" / "museum-review-ledger.schema.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "schemas/museum-review-ledger.schema.json"
    )
    return Path(str(package_candidate)) if package_candidate.is_file() else None


def _default_penn_metadata_schema() -> Path | None:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "schemas" / "penn-metadata-snapshot.schema.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "schemas/penn-metadata-snapshot.schema.json"
    )
    return Path(str(package_candidate)) if package_candidate.is_file() else None


def _default_context_anchor_schema() -> Path | None:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "schemas" / "context-anchor-registry.schema.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "schemas/context-anchor-registry.schema.json"
    )
    return Path(str(package_candidate)) if package_candidate.is_file() else None


def _default_mtaac_control_protocol() -> Path:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "benchmark" / "mtaac-known-script-control-v2.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "benchmark/mtaac-known-script-control-v2.json"
    )
    return Path(str(package_candidate))


def _default_oracc_ed3b_source_protocol() -> Path:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "benchmark" / "oracc-ed3b-validation-source-v1.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "benchmark/oracc-ed3b-validation-source-v1.json"
    )
    return Path(str(package_candidate))


def _default_smithsonian_metadata_schema() -> Path | None:
    project_candidate = (
        Path(__file__).resolve().parents[2] / "schemas" / "smithsonian-metadata-record.schema.json"
    )
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        "schemas/smithsonian-metadata-record.schema.json"
    )
    return Path(str(package_candidate)) if package_candidate.is_file() else None


def _stat_fingerprint(
    metadata: os.stat_result,
) -> tuple[int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_nlink,
    )


def _museum_bundle_inventory(
    bundle_dir: Path,
    *,
    max_json_bytes: int,
    max_media_bytes: int,
    max_media_count: int,
    max_total_json_bytes: int,
    max_total_media_bytes: int,
) -> tuple[
    dict[str, tuple[int, int, int, int, int, int, int]],
    dict[str, tuple[int, int, int, int, int, int, int]],
]:
    limits = {
        "max_json_bytes": max_json_bytes,
        "max_media_bytes": max_media_bytes,
        "max_media_count": max_media_count,
        "max_total_json_bytes": max_total_json_bytes,
        "max_total_media_bytes": max_total_media_bytes,
    }
    for name, value in limits.items():
        if isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be positive")
    try:
        root_metadata = bundle_dir.lstat()
    except FileNotFoundError as error:
        raise ValueError(f"museum bundle does not exist: {bundle_dir}") from error
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("museum bundle root must be a real directory, not a symbolic link")

    file_inventory: dict[str, tuple[int, int, int, int, int, int, int]] = {}
    directory_inventory: dict[str, tuple[int, int, int, int, int, int, int]] = {
        ".": _stat_fingerprint(root_metadata)
    }
    media_count = 0
    raw_json_count = 0
    total_media_bytes = 0
    total_json_bytes = 0
    entry_count = 0
    max_entry_count = (4 * max_media_count) + 32
    try:
        pending_directories = [(bundle_dir, 0)]
        while pending_directories:
            current_directory, current_depth = pending_directories.pop()
            with os.scandir(current_directory) as entries:
                for entry in entries:
                    entry_count += 1
                    if entry_count > max_entry_count:
                        raise ValueError(
                            "museum bundle entry count exceeds limit: "
                            f"{entry_count} > {max_entry_count}"
                        )
                    path = Path(entry.path)
                    metadata = entry.stat(follow_symlinks=False)
                    relative_path = path.relative_to(bundle_dir).as_posix()
                    if stat.S_ISLNK(metadata.st_mode):
                        raise ValueError(f"museum bundle contains a symbolic link: {relative_path}")
                    if stat.S_ISDIR(metadata.st_mode):
                        depth = current_depth + 1
                        if depth > MUSEUM_MAX_BUNDLE_DEPTH:
                            raise ValueError(
                                f"museum bundle directory depth exceeds limit: {relative_path}"
                            )
                        if relative_path in directory_inventory:
                            raise ValueError(
                                f"museum bundle directory is repeated: {relative_path}"
                            )
                        directory_inventory[relative_path] = _stat_fingerprint(metadata)
                        pending_directories.append((path, depth))
                        continue
                    if not stat.S_ISREG(metadata.st_mode):
                        raise ValueError(
                            f"museum bundle contains a non-regular file: {relative_path}"
                        )
                    if metadata.st_nlink != 1:
                        raise ValueError(
                            f"museum bundle file must have exactly one hard link: {relative_path}"
                        )
                    if relative_path in file_inventory:
                        raise ValueError(f"museum bundle path is repeated: {relative_path}")
                    file_inventory[relative_path] = _stat_fingerprint(metadata)

                    if relative_path in {"intake.jsonl", "bundle-manifest.json"}:
                        if metadata.st_size > MUSEUM_MAX_INDEX_BYTES:
                            raise ValueError(f"museum bundle index exceeds limit: {relative_path}")
                    elif relative_path.startswith("raw/"):
                        raw_json_count += 1
                        total_json_bytes += metadata.st_size
                        if metadata.st_size > max_json_bytes:
                            raise ValueError(
                                f"stored API response exceeds per-file limit: {relative_path}"
                            )
                        if raw_json_count > max_media_count + 8:
                            raise ValueError("stored API response count exceeds limit")
                        if total_json_bytes > max_total_json_bytes:
                            raise ValueError("stored API responses exceed aggregate byte limit")
                    elif relative_path.startswith("images/"):
                        media_count += 1
                        total_media_bytes += metadata.st_size
                        if metadata.st_size > max_media_bytes:
                            raise ValueError(
                                f"stored media exceeds per-file limit: {relative_path}"
                            )
                        if media_count > max_media_count:
                            raise ValueError("stored media count exceeds limit")
                        if total_media_bytes > max_total_media_bytes:
                            raise ValueError("stored media exceed aggregate byte limit")
                    elif metadata.st_size > max_media_bytes:
                        raise ValueError(f"unclassified bundle file exceeds limit: {relative_path}")
    except (FileNotFoundError, NotADirectoryError) as error:
        raise ValueError("museum bundle changed during file inventory") from error
    return file_inventory, directory_inventory


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
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError(f"museum bundle index is not a single-link regular file: {path}")
        if metadata.st_size > max_bytes:
            raise ValueError(f"museum bundle index exceeds limit: {path}")
        chunks: list[bytes] = []
        byte_count = 0
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            while True:
                chunk = handle.read(min(1024 * 1024, max_bytes + 1 - byte_count))
                if not chunk:
                    break
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise ValueError(f"museum bundle index exceeds limit: {path}")
                chunks.append(chunk)
        return b"".join(chunks)
    except OSError as error:
        raise ValueError(f"cannot safely open museum bundle index {path}: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_private_regular_bytes_at(
    parent_descriptor: int,
    name: str,
    *,
    max_bytes: int,
) -> bytes:
    """Read one stable owner-only file relative to a pinned private directory."""

    if not name or name in {".", ".."} or "/" in name or "\x00" in name:
        raise ValueError("private input filename is invalid")
    descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_size > max_bytes
            or _descriptor_has_extended_acl(descriptor)
        ):
            raise ValueError("private input is not a bounded owner-only regular file")
        chunks: list[bytes] = []
        byte_count = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - byte_count))
            if not chunk:
                break
            byte_count += len(chunk)
            if byte_count > max_bytes:
                raise ValueError("private input exceeds its byte limit")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        namespace = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        fingerprint_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        before_fingerprint = tuple(getattr(before, field) for field in fingerprint_fields)
        if (
            tuple(getattr(after, field) for field in fingerprint_fields) != before_fingerprint
            or tuple(getattr(namespace, field) for field in fingerprint_fields)
            != before_fingerprint
            or _descriptor_has_extended_acl(descriptor)
        ):
            raise ValueError("private input changed during its bounded read")
        return b"".join(chunks)
    except OSError as error:
        raise ValueError("private input could not be read safely") from error
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


def _read_private_regular_bytes(path: Path, *, max_bytes: int) -> bytes:
    """Read one stable owner-only file through a pinned physical parent."""

    absolute = Path(os.path.abspath(path))
    if (
        not absolute.name
        or absolute.name in {".", ".."}
        or "/" in absolute.name
        or "\x00" in absolute.name
    ):
        raise ValueError("private input filename is invalid")
    pinned = _open_pinned_directory(absolute.parent, private_target=True)
    try:
        raw_bytes = _read_private_regular_bytes_at(
            pinned.descriptor,
            absolute.name,
            max_bytes=max_bytes,
        )
        _verify_pinned_directory(pinned)
        return raw_bytes
    except PrivateReadinessError as error:
        raise ValueError("private input could not be read safely") from error
    finally:
        _close_pinned_directory(pinned)


def _museum_json_value(raw_bytes: bytes, *, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"{label} contains duplicate JSON key: {key!r}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise ValueError(f"{label} contains non-finite JSON number {value!r}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{label} contains non-finite JSON number {value!r}")
        return parsed

    try:
        return json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{label} is not valid UTF-8 JSON: {error}") from error


def _read_museum_records(path: Path) -> list[dict[str, Any]]:
    raw_bytes = _read_regular_bytes(path, max_bytes=MUSEUM_MAX_INDEX_BYTES)
    return _museum_records_from_bytes(raw_bytes, label=str(path))


def _museum_records_from_bytes(
    raw_bytes: bytes,
    *,
    label: str,
) -> list[dict[str, Any]]:
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CorpusFormatError(f"{label}: invalid UTF-8") from error
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = _museum_json_value(
            line.encode("utf-8"),
            label=f"{label}:{line_number}",
        )
        if not isinstance(value, dict):
            raise CorpusFormatError(f"{label}:{line_number}: each JSONL row must be an object")
        records.append(value)
    return records


def _read_museum_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
    raw_bytes = _read_regular_bytes(path, max_bytes=MUSEUM_MAX_INDEX_BYTES)
    value = _museum_json_value(raw_bytes, label=str(path))
    if not isinstance(value, dict):
        raise ValueError("museum bundle manifest must be a JSON object")
    return value, raw_bytes


def _path_lexists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _target_is_clear(path: Path, force: bool) -> bool:
    if force or not _path_lexists(path):
        return True
    print(f"refusing to overwrite existing path without --force: {path}", file=sys.stderr)
    return False


def _fsync_directory(path: Path) -> None:
    """Persist directory-entry updates or fail when durability is unavailable."""

    if os.name == "nt":
        return
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _path_has_extended_acl(path: Path) -> bool:
    """Fail closed on ACLs that POSIX owner/group/other mode bits cannot show."""

    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        acl_get_link = libc.acl_get_link_np
        acl_get_link.argtypes = [ctypes.c_char_p, ctypes.c_int]
        acl_get_link.restype = ctypes.c_void_p
        acl_free = libc.acl_free
        acl_free.argtypes = [ctypes.c_void_p]
        acl_free.restype = ctypes.c_int
        ctypes.set_errno(0)
        acl = acl_get_link(os.fsencode(path), 0x00000100)
        if not acl:
            error_number = ctypes.get_errno()
            if error_number == errno.ENOENT:
                return False
            raise ValueError(
                f"cannot inspect extended ACL for private path {path}: {os.strerror(error_number)}"
            )
        try:
            return True
        finally:
            if acl_free(acl) != 0:
                raise ValueError(f"cannot release extended ACL for private path {path}")

    if os.name == "posix":
        try:
            attribute_names = os.listxattr(path, follow_symlinks=False)
        except OSError as error:
            if error.errno in {errno.ENOTSUP, errno.EOPNOTSUPP}:
                return False
            raise ValueError(f"cannot inspect ACL attributes for private path {path}") from error
        return any(
            name in {"system.posix_acl_access", "system.posix_acl_default"}
            for name in attribute_names
        )
    return False


def _descriptor_has_extended_acl(descriptor: int) -> bool:
    """Inspect one pinned descriptor and fail closed if ACL inspection is unavailable."""

    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            acl_get_fd = libc.acl_get_fd_np
        except AttributeError as error:
            raise ValueError(
                "descriptor-relative extended ACL inspection is unavailable"
            ) from error
        acl_get_fd.argtypes = [ctypes.c_int, ctypes.c_int]
        acl_get_fd.restype = ctypes.c_void_p
        acl_free = libc.acl_free
        acl_free.argtypes = [ctypes.c_void_p]
        acl_free.restype = ctypes.c_int
        ctypes.set_errno(0)
        acl = acl_get_fd(descriptor, 0x00000100)
        if not acl:
            error_number = ctypes.get_errno()
            if error_number == errno.ENOENT:
                return False
            raise ValueError(
                "cannot inspect the extended ACL on a pinned output descriptor: "
                + os.strerror(error_number)
            )
        try:
            return True
        finally:
            if acl_free(acl) != 0:
                raise ValueError("cannot release the extended ACL on a pinned output descriptor")

    if os.name == "posix":
        list_attributes = getattr(os, "listxattr", None)
        if list_attributes is None:
            raise ValueError("descriptor-relative ACL inspection is unavailable")
        try:
            attribute_names = list_attributes(descriptor)
        except OSError as error:
            raise ValueError(
                "cannot inspect ACL attributes on a pinned output descriptor"
            ) from error
        return any(
            name
            in {
                "system.posix_acl_access",
                "system.posix_acl_default",
                b"system.posix_acl_access",
                b"system.posix_acl_default",
            }
            for name in attribute_names
        )
    raise ValueError("descriptor-relative ACL inspection is unsupported")


def _assert_private_creation_root(path: Path) -> None:
    metadata = path.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or _path_has_extended_acl(path)
    ):
        raise ValueError("private staging directory is not owner-only or inherited an extended ACL")


def _assert_private_tree(path: Path) -> None:
    pending = [path]
    while pending:
        current = pending.pop()
        metadata = current.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or (not stat.S_ISDIR(metadata.st_mode) and not stat.S_ISREG(metadata.st_mode))
            or stat.S_IMODE(metadata.st_mode) & 0o077
            or _path_has_extended_acl(current)
        ):
            raise ValueError(f"private staging path is not owner-only and ACL-free: {current}")
        if stat.S_ISDIR(metadata.st_mode):
            with os.scandir(current) as entries:
                pending.extend(Path(entry.path) for entry in entries)


def _rename_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish a directory without replacing any destination entry."""

    if source.parent != destination.parent:
        raise ValueError("museum staging and output directories must share one parent")
    source_name = source.name
    destination_name = destination.name
    for label, name in (("source", source_name), ("destination", destination_name)):
        if not name or name in {".", ".."} or "/" in name or "\x00" in name:
            raise ValueError(f"invalid museum {label} directory name")

    source_metadata = source.lstat()
    if stat.S_ISLNK(source_metadata.st_mode) or not stat.S_ISDIR(source_metadata.st_mode):
        raise ValueError("museum staging path must be a real directory")

    if os.name == "nt":
        # os.rename() is no-replace on Windows and raises FileExistsError for dst.
        os.rename(source, destination)
        return

    parent_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    parent_descriptor = os.open(source.parent, parent_flags)
    parent_metadata = os.fstat(parent_descriptor)
    if not stat.S_ISDIR(parent_metadata.st_mode):
        os.close(parent_descriptor)
        raise ValueError("museum output parent must be a real directory")
    source_descriptor: int | None = None

    encoded_source = os.fsencode(source_name)
    encoded_destination = os.fsencode(destination_name)
    try:
        source_descriptor = os.open(source_name, parent_flags, dir_fd=parent_descriptor)
        pinned_source_metadata = os.fstat(source_descriptor)
        if (
            not stat.S_ISDIR(pinned_source_metadata.st_mode)
            or pinned_source_metadata.st_dev != source_metadata.st_dev
            or pinned_source_metadata.st_ino != source_metadata.st_ino
        ):
            raise ValueError("museum staging directory changed before publication")

        ctypes.set_errno(0)
        if sys.platform == "darwin":
            renameatx = ctypes.CDLL(None, use_errno=True).renameatx_np
            renameatx.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameatx.restype = ctypes.c_int
            # Darwin RENAME_EXCL | RENAME_NOFOLLOW_ANY.
            result = int(
                renameatx(
                    parent_descriptor,
                    encoded_source,
                    parent_descriptor,
                    encoded_destination,
                    0x00000004 | 0x00000010,
                )
            )
        elif sys.platform.startswith("linux"):
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is None:
                raise OSError(
                    errno.ENOTSUP,
                    "this platform lacks an atomic no-replace directory rename",
                    str(destination),
                )
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            # Linux RENAME_NOREPLACE with both basenames resolved under one pinned dirfd.
            result = int(
                renameat2(
                    parent_descriptor,
                    encoded_source,
                    parent_descriptor,
                    encoded_destination,
                    1,
                )
            )
        else:
            raise OSError(
                errno.ENOTSUP,
                "this platform lacks an atomic no-replace directory rename",
                str(destination),
            )
        error_number = ctypes.get_errno()
        if result == 0:
            published_metadata = os.stat(
                destination_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(published_metadata.st_mode)
                or published_metadata.st_dev != pinned_source_metadata.st_dev
                or published_metadata.st_ino != pinned_source_metadata.st_ino
            ):
                raise OSError(
                    errno.EIO,
                    "published museum directory does not match the pinned staging directory",
                    str(destination),
                )
            os.fsync(parent_descriptor)
    finally:
        if source_descriptor is not None:
            os.close(source_descriptor)
        os.close(parent_descriptor)
    if result != 0:
        raise OSError(
            error_number,
            os.strerror(error_number),
            str(destination),
        )


def _rename_regular_file_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish one regular file without replacing an existing entry."""

    for label, name in (("source", source.name), ("destination", destination.name)):
        if not name or name in {".", ".."} or "/" in name or "\x00" in name:
            raise ValueError(f"invalid review {label} filename")

    source_metadata = source.lstat()
    if (
        stat.S_ISLNK(source_metadata.st_mode)
        or not stat.S_ISREG(source_metadata.st_mode)
        or source_metadata.st_nlink != 1
    ):
        raise ValueError("review staging path must be a single-link regular file")

    if os.name == "nt":
        os.rename(source, destination)
        try:
            published_metadata = destination.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(published_metadata.st_mode)
                or published_metadata.st_dev != source_metadata.st_dev
                or published_metadata.st_ino != source_metadata.st_ino
            ):
                raise OSError(
                    errno.EIO,
                    "published review does not match the staging file",
                    str(destination),
                )
        except OSError as error:
            raise _CommittedDurabilityUnknown(
                error.errno or errno.EIO,
                "published file exists but post-publication verification failed",
                str(destination),
                content_verified=False,
            ) from error
        return

    parent_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    source_parent_descriptor = os.open(source.parent, parent_flags)
    destination_parent_descriptor: int | None = None
    source_descriptor: int | None = None
    published = False
    content_verified = False
    try:
        destination_parent_descriptor = os.open(destination.parent, parent_flags)
        source_parent_metadata = os.fstat(source_parent_descriptor)
        destination_parent_metadata = os.fstat(destination_parent_descriptor)
        if not stat.S_ISDIR(source_parent_metadata.st_mode) or not stat.S_ISDIR(
            destination_parent_metadata.st_mode
        ):
            raise ValueError("review staging and output parents must be real directories")
        source_descriptor = os.open(
            source.name,
            file_flags,
            dir_fd=source_parent_descriptor,
        )
        pinned_source_metadata = os.fstat(source_descriptor)
        if (
            not stat.S_ISREG(pinned_source_metadata.st_mode)
            or pinned_source_metadata.st_nlink != 1
            or pinned_source_metadata.st_dev != source_metadata.st_dev
            or pinned_source_metadata.st_ino != source_metadata.st_ino
        ):
            raise ValueError("review staging file changed before publication")

        encoded_source = os.fsencode(source.name)
        encoded_destination = os.fsencode(destination.name)
        ctypes.set_errno(0)
        if sys.platform == "darwin":
            renameatx = ctypes.CDLL(None, use_errno=True).renameatx_np
            renameatx.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameatx.restype = ctypes.c_int
            result = int(
                renameatx(
                    source_parent_descriptor,
                    encoded_source,
                    destination_parent_descriptor,
                    encoded_destination,
                    0x00000004 | 0x00000010,
                )
            )
        elif sys.platform.startswith("linux"):
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is None:
                raise OSError(
                    errno.ENOTSUP,
                    "this platform lacks atomic no-replace review publication",
                    str(destination),
                )
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            result = int(
                renameat2(
                    source_parent_descriptor,
                    encoded_source,
                    destination_parent_descriptor,
                    encoded_destination,
                    1,
                )
            )
        else:
            raise OSError(
                errno.ENOTSUP,
                "this platform lacks atomic no-replace review publication",
                str(destination),
            )
        error_number = ctypes.get_errno()
        if result != 0:
            raise OSError(
                error_number,
                os.strerror(error_number),
                str(destination),
            )
        published = True
        try:
            published_metadata = os.stat(
                destination.name,
                dir_fd=destination_parent_descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(published_metadata.st_mode)
                or published_metadata.st_dev != pinned_source_metadata.st_dev
                or published_metadata.st_ino != pinned_source_metadata.st_ino
            ):
                raise OSError(
                    errno.EIO,
                    "published review does not match the pinned staging file",
                    str(destination),
                )
        except OSError as error:
            raise _CommittedDurabilityUnknown(
                error.errno or errno.EIO,
                "published file exists but post-publication verification failed",
                str(destination),
                content_verified=False,
            ) from error
        content_verified = True
        try:
            os.fsync(destination_parent_descriptor)
            os.fsync(source_parent_descriptor)
        except OSError as error:
            raise _CommittedDurabilityUnknown(
                error.errno or errno.EIO,
                "published file exists but directory durability is unknown",
                str(destination),
                content_verified=True,
            ) from error
    finally:
        close_error: OSError | None = None
        if source_descriptor is not None:
            try:
                os.close(source_descriptor)
            except OSError as error:
                close_error = error
        if destination_parent_descriptor is not None:
            try:
                os.close(destination_parent_descriptor)
            except OSError as error:
                close_error = close_error or error
        try:
            os.close(source_parent_descriptor)
        except OSError as error:
            close_error = close_error or error
        if close_error is not None:
            if published:
                raise _CommittedDurabilityUnknown(
                    close_error.errno or errno.EIO,
                    "published file exists but descriptor cleanup failed",
                    str(destination),
                    content_verified=content_verified,
                ) from close_error
            raise close_error


def _write_json_no_replace(
    destination: Path,
    value: dict[str, Any],
    *,
    mode: int = 0o600,
) -> tuple[bool, bool]:
    """Durably publish deterministic JSON without an overwrite window."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve(strict=False)
    raw_bytes = (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".json-write-",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        os.chmod(temporary_path, mode)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(raw_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        if (
            _read_regular_bytes(
                temporary_path,
                max_bytes=max(len(raw_bytes), 1),
            )
            != raw_bytes
        ):
            raise OSError(
                errno.EIO,
                "JSON staging verification failed",
                str(temporary_path),
            )
        try:
            _rename_regular_file_no_replace(temporary_path, destination)
        except _CommittedDurabilityUnknown as error:
            return False, error.content_verified
        return True, True
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path.exists():
            temporary_path.unlink()


def _write_private_json_no_replace(
    destination: Path,
    value: dict[str, Any],
) -> tuple[bool, bool]:
    """Publish private JSON relative to one pinned, owner-only directory."""

    absolute = Path(os.path.abspath(destination))
    if not absolute.name or absolute.name in {".", ".."} or "\x00" in absolute.name:
        raise ValueError("private output filename is invalid")
    raw_bytes = encode_json(value)
    pinned = _open_pinned_directory(absolute.parent, private_target=True)
    staging_name = f".indusbench-private-{secrets.token_hex(16)}.tmp"
    descriptor: int | None = None
    published = False
    content_verified = False
    try:
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(
            staging_name,
            flags,
            0o600,
            dir_fd=pinned.descriptor,
        )
        os.fchmod(descriptor, 0o600)
        pending = memoryview(raw_bytes)
        while pending:
            written = os.write(descriptor, pending)
            if written <= 0:
                raise OSError(errno.EIO, "private JSON staging write failed")
            pending = pending[written:]
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        observed = bytearray()
        while len(observed) < len(raw_bytes):
            chunk = os.read(descriptor, len(raw_bytes) - len(observed))
            if not chunk:
                break
            observed.extend(chunk)
        content_verified = bytes(observed) == raw_bytes
        metadata = os.fstat(descriptor)
        if (
            not content_verified
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or _descriptor_has_extended_acl(descriptor)
        ):
            raise OSError(errno.EIO, "private JSON staging verification failed")

        _verify_pinned_directory(pinned)
        _rename_private_name_no_replace(
            pinned.descriptor,
            staging_name,
            absolute.name,
        )
        published = True
        published_metadata = os.stat(
            absolute.name,
            dir_fd=pinned.descriptor,
            follow_symlinks=False,
        )
        descriptor_metadata = os.fstat(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        published_bytes = bytearray()
        while len(published_bytes) <= len(raw_bytes):
            chunk = os.read(descriptor, len(raw_bytes) + 1 - len(published_bytes))
            if not chunk:
                break
            published_bytes.extend(chunk)
        content_verified = bytes(published_bytes) == raw_bytes
        if (
            not content_verified
            or not stat.S_ISREG(published_metadata.st_mode)
            or published_metadata.st_dev != metadata.st_dev
            or published_metadata.st_ino != metadata.st_ino
            or not stat.S_ISREG(descriptor_metadata.st_mode)
            or descriptor_metadata.st_dev != metadata.st_dev
            or descriptor_metadata.st_ino != metadata.st_ino
            or descriptor_metadata.st_nlink != 1
            or descriptor_metadata.st_uid != os.geteuid()
            or stat.S_IMODE(descriptor_metadata.st_mode) != 0o600
            or _descriptor_has_extended_acl(descriptor)
        ):
            raise OSError(errno.EIO, "private JSON publication verification failed")
        os.fsync(pinned.descriptor)
        _verify_pinned_directory(pinned)
        return True, True
    except _CommittedDurabilityUnknown as error:
        return False, error.content_verified
    except (OSError, PrivateReadinessError):
        if published:
            return False, content_verified
        raise
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        if not published:
            with suppress(OSError):
                os.unlink(staging_name, dir_fd=pinned.descriptor)
        _close_pinned_directory(pinned)


def _rename_private_name_no_replace(
    parent_descriptor: int,
    source_name: str,
    destination_name: str,
) -> None:
    """Atomically rename two basenames under one pinned directory descriptor."""

    for name in (source_name, destination_name):
        if not name or name in {".", ".."} or "/" in name or "\x00" in name:
            raise ValueError("private output filename is invalid")
    encoded_source = os.fsencode(source_name)
    encoded_destination = os.fsencode(destination_name)
    ctypes.set_errno(0)
    if sys.platform == "darwin":
        renameatx = ctypes.CDLL(None, use_errno=True).renameatx_np
        renameatx.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameatx.restype = ctypes.c_int
        result = int(
            renameatx(
                parent_descriptor,
                encoded_source,
                parent_descriptor,
                encoded_destination,
                0x00000004 | 0x00000010,
            )
        )
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise OSError(errno.ENOTSUP, "atomic private publication is unavailable")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = int(
            renameat2(
                parent_descriptor,
                encoded_source,
                parent_descriptor,
                encoded_destination,
                1,
            )
        )
    else:
        raise OSError(errno.ENOTSUP, "atomic private publication is unavailable")
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _validate_review_destination(bundle_dir: Path, output_dir: Path) -> None:
    bundle_resolved = bundle_dir.resolve(strict=True)
    output_resolved = output_dir.resolve(strict=False)
    if (
        output_resolved == bundle_resolved
        or output_resolved.is_relative_to(bundle_resolved)
        or bundle_resolved.is_relative_to(output_resolved)
    ):
        raise ValueError("review output and source museum bundle must be disjoint")


def _sha256_regular_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError(f"review packet file is not a single-link regular file: {path}")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return "sha256:" + digest.hexdigest()


def _copy_verified_review_evidence(
    source: Path,
    destination: Path,
    *,
    expected_fingerprint: tuple[int, int, int, int, int, int, int],
    expected_sha256: str,
    expected_bytes: int,
) -> None:
    source_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    destination_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    source_descriptor: int | None = None
    destination_descriptor: int | None = None
    digest = hashlib.sha256()
    byte_count = 0
    try:
        source_descriptor = os.open(source, source_flags)
        source_metadata = os.fstat(source_descriptor)
        if _stat_fingerprint(source_metadata) != expected_fingerprint:
            raise ValueError(f"museum source changed before review copy: {source}")
        if (
            not stat.S_ISREG(source_metadata.st_mode)
            or source_metadata.st_nlink != 1
            or source_metadata.st_size != expected_bytes
        ):
            raise ValueError(f"museum review source is not the expected regular file: {source}")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination_descriptor = os.open(destination, destination_flags, 0o600)
        with (
            os.fdopen(source_descriptor, "rb") as source_handle,
            os.fdopen(destination_descriptor, "wb") as destination_handle,
        ):
            source_descriptor = None
            destination_descriptor = None
            while chunk := source_handle.read(1024 * 1024):
                destination_handle.write(chunk)
                digest.update(chunk)
                byte_count += len(chunk)
                if byte_count > expected_bytes:
                    raise ValueError(f"museum review source grew during copy: {source}")
            destination_handle.flush()
            os.fsync(destination_handle.fileno())
            if _stat_fingerprint(os.fstat(source_handle.fileno())) != expected_fingerprint:
                raise ValueError(f"museum source changed during review copy: {source}")
    finally:
        if source_descriptor is not None:
            os.close(source_descriptor)
        if destination_descriptor is not None:
            os.close(destination_descriptor)
    actual_sha256 = "sha256:" + digest.hexdigest()
    if byte_count != expected_bytes or actual_sha256 != expected_sha256:
        raise ValueError(f"museum review evidence copy failed integrity check: {source}")
    os.chmod(destination, 0o600)


def _reviewer_sensitive_strings(
    records: list[dict[str, Any]],
    *,
    bundle_dir: Path,
) -> set[str]:
    sensitive = {str(bundle_dir), str(bundle_dir.resolve(strict=True))}
    for record in records:
        for field in ("intake_id", "source_id"):
            value = record.get(field)
            if isinstance(value, str):
                sensitive.add(value)
        institution = record.get("institution")
        if isinstance(institution, dict):
            sensitive.update(value for value in institution.values() if isinstance(value, str))
        official_record = record.get("official_record")
        if isinstance(official_record, dict):
            sensitive.update(value for value in official_record.values() if isinstance(value, str))
        for media in record.get("media", []):
            if not isinstance(media, dict):
                continue
            for field in (
                "media_id",
                "source_uri",
                "provider_derivative",
                "view_role",
            ):
                value = media.get(field)
                if isinstance(value, str):
                    sensitive.add(value)
            download = media.get("download")
            if isinstance(download, dict):
                path = download.get("local_relative_path")
                if isinstance(path, str):
                    sensitive.add(path)
    return {value for value in sensitive if len(value) >= 6}


def _prepare_museum_review_packet(
    *,
    bundle_dir: Path,
    output_dir: Path,
    records: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    source_manifest: dict[str, Any],
    source_manifest_sha256: str,
    source_externally_anchored: bool,
    preflight_file_inventory: dict[
        str,
        tuple[int, int, int, int, int, int, int],
    ],
    preflight_directory_inventory: dict[
        str,
        tuple[int, int, int, int, int, int, int],
    ],
    subject_schema: Path,
    max_json_bytes: int,
    max_media_bytes: int,
    max_media_count: int,
    max_total_json_bytes: int,
    max_total_media_bytes: int,
) -> dict[str, Any]:
    output_label = str(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve(strict=False)
    packet_id = f"packet:{secrets.token_hex(12)}"
    created_at = _utc_timestamp()
    subjects, custody_map, copy_specs = build_blind_review_materials(
        records,
        reports,
        packet_id=packet_id,
        pseudonym_key=secrets.token_bytes(32),
        source_bundle_manifest_sha256=source_manifest_sha256,
        source_bundle_version=source_manifest["bundle_version"],
        source_bundle_created_at=source_manifest["created_at"],
        source_bundle_externally_anchored=source_externally_anchored,
    )
    schema_issues = []
    validate_subject_schema = compile_schema_validator(subject_schema)
    for index, subject in enumerate(subjects):
        validate_subject_semantics(subject)
        schema_issues.extend(
            validate_subject_schema(
                subject,
                f"$[{index}]",
            )
        )
    if schema_issues:
        messages = "; ".join(f"{issue.path}: {issue.message}" for issue in schema_issues[:10])
        raise ValueError(f"generated museum review subjects failed schema validation: {messages}")

    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=".museum-review-",
            dir=output_dir.parent,
        )
    )
    # The packet contains private museum evidence; group/other access is forbidden.
    os.chmod(staging_dir, 0o700)  # nosemgrep
    try:
        _assert_private_creation_root(staging_dir)
        reviewer_dir = staging_dir / "reviewer"
        evidence_dir = reviewer_dir / "evidence"
        custody_dir = staging_dir / "custody"
        reviewer_dir.mkdir(mode=0o700)
        evidence_dir.mkdir(mode=0o700)
        custody_dir.mkdir(mode=0o700)

        evidence_inventory = []
        for specification in copy_specs:
            source_relative_path = specification["source_relative_path"]
            expected_fingerprint = preflight_file_inventory.get(source_relative_path)
            if expected_fingerprint is None:
                raise ValueError(
                    f"review evidence is absent from verified source inventory: "
                    f"{source_relative_path}"
                )
            destination = reviewer_dir / PurePosixPath(specification["review_relative_path"])
            _copy_verified_review_evidence(
                bundle_dir / PurePosixPath(source_relative_path),
                destination,
                expected_fingerprint=expected_fingerprint,
                expected_sha256=specification["sha256"],
                expected_bytes=specification["bytes"],
            )
            evidence_inventory.append(
                {
                    "image_id": specification["image_id"],
                    "relative_path": specification["review_relative_path"],
                    "sha256": specification["sha256"],
                    "bytes": specification["bytes"],
                    "content_type": specification["content_type"],
                }
            )

        subjects_path = reviewer_dir / "subjects.jsonl"
        write_jsonl(subjects_path, subjects)
        os.chmod(subjects_path, 0o600)
        instructions_path = reviewer_dir / "REVIEW_INSTRUCTIONS.md"
        instructions_path.write_text(
            render_review_instructions(),
            encoding="utf-8",
            newline="\n",
        )
        os.chmod(instructions_path, 0o600)
        reviewer_manifest = build_reviewer_manifest(
            subjects,
            packet_id=packet_id,
            created_at=created_at,
            subjects_file_sha256=_sha256_regular_file(subjects_path),
            instructions_file_sha256=_sha256_regular_file(instructions_path),
            evidence_inventory=evidence_inventory,
        )
        reviewer_manifest_path = reviewer_dir / "manifest.json"
        write_json(reviewer_manifest_path, reviewer_manifest)
        os.chmod(reviewer_manifest_path, 0o600)

        custody_path = custody_dir / "identity-map.json"
        write_json(custody_path, custody_map)
        os.chmod(custody_path, 0o600)
        packet_manifest = build_packet_manifest(
            packet_id=packet_id,
            created_at=created_at,
            source_bundle_manifest_sha256=source_manifest_sha256,
            source_bundle_version=source_manifest["bundle_version"],
            source_bundle_created_at=source_manifest["created_at"],
            source_bundle_externally_anchored=source_externally_anchored,
            reviewer_manifest_sha256=_sha256_regular_file(reviewer_manifest_path),
            custody_map_sha256=_sha256_regular_file(custody_path),
            subject_count=reviewer_manifest["subject_count"],
            view_group_count=reviewer_manifest["view_group_count"],
            evidence_image_count=reviewer_manifest["evidence_image_count"],
            evidence_bytes=reviewer_manifest["evidence_bytes"],
        )
        packet_manifest_path = staging_dir / "packet-manifest.json"
        write_json(packet_manifest_path, packet_manifest)
        os.chmod(packet_manifest_path, 0o600)

        reviewer_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                subjects_path,
                instructions_path,
                reviewer_manifest_path,
            )
        )
        leaked_values = sorted(
            value
            for value in _reviewer_sensitive_strings(records, bundle_dir=bundle_dir)
            if value in reviewer_text
        )
        if leaked_values:
            raise ValueError(
                "catalog-blind reviewer packet leaked source identity values: "
                + ", ".join(repr(value) for value in leaked_values[:5])
            )

        post_copy_files, post_copy_directories = _museum_bundle_inventory(
            bundle_dir,
            max_json_bytes=max_json_bytes,
            max_media_bytes=max_media_bytes,
            max_media_count=max_media_count,
            max_total_json_bytes=max_total_json_bytes,
            max_total_media_bytes=max_total_media_bytes,
        )
        if (
            post_copy_files != preflight_file_inventory
            or post_copy_directories != preflight_directory_inventory
        ):
            raise ValueError("museum bundle changed while preparing review evidence")

        packet_manifest_sha256 = _sha256_regular_file(packet_manifest_path)
        _assert_private_tree(staging_dir)
        _rename_directory_no_replace(staging_dir, output_dir)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)

    return {
        "written": True,
        "output": output_label,
        "packet_id": packet_id,
        "packet_version": packet_manifest["packet_version"],
        "packet_manifest_sha256": packet_manifest_sha256,
        "subject_count": packet_manifest["subject_count"],
        "view_group_count": packet_manifest["view_group_count"],
        "evidence_image_count": packet_manifest["evidence_image_count"],
        "evidence_bytes": packet_manifest["evidence_bytes"],
        "required_independent_reviews_per_subject": (
            packet_manifest["required_independent_reviews_per_subject"]
        ),
        "source_self_consistent": True,
        "source_externally_anchored": source_externally_anchored,
        "privacy_classification": packet_manifest["privacy_classification"],
        "publication_gate": packet_manifest["publication_gate"],
        "catalog_blind_text_leak_check": "passed",
    }


def _review_packet_inventory(
    packet_dir: Path,
    *,
    max_json_bytes: int,
    max_media_bytes: int,
    max_media_count: int,
    max_total_json_bytes: int,
    max_total_media_bytes: int,
) -> tuple[
    dict[str, tuple[int, int, int, int, int, int, int]],
    dict[str, tuple[int, int, int, int, int, int, int]],
]:
    for name, value in {
        "max_json_bytes": max_json_bytes,
        "max_media_bytes": max_media_bytes,
        "max_media_count": max_media_count,
        "max_total_json_bytes": max_total_json_bytes,
        "max_total_media_bytes": max_total_media_bytes,
    }.items():
        if isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be positive")
    try:
        root_metadata = packet_dir.lstat()
    except FileNotFoundError as error:
        raise ValueError(f"museum review packet does not exist: {packet_dir}") from error
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("museum review packet root must be a real directory")

    file_inventory: dict[str, tuple[int, int, int, int, int, int, int]] = {}
    directory_inventory = {".": _stat_fingerprint(root_metadata)}
    media_count = 0
    media_bytes = 0
    index_bytes = 0
    entry_count = 0
    pending_directories = [(packet_dir, 0)]
    try:
        while pending_directories:
            current_directory, current_depth = pending_directories.pop()
            with os.scandir(current_directory) as entries:
                for entry in entries:
                    entry_count += 1
                    if entry_count > max_media_count + 32:
                        raise ValueError("museum review packet entry count exceeds limit")
                    path = Path(entry.path)
                    metadata = entry.stat(follow_symlinks=False)
                    relative_path = path.relative_to(packet_dir).as_posix()
                    if stat.S_ISLNK(metadata.st_mode):
                        raise ValueError(
                            f"museum review packet contains a symbolic link: {relative_path}"
                        )
                    if stat.S_ISDIR(metadata.st_mode):
                        depth = current_depth + 1
                        if depth > 4:
                            raise ValueError(
                                f"museum review packet directory depth exceeds limit: "
                                f"{relative_path}"
                            )
                        directory_inventory[relative_path] = _stat_fingerprint(metadata)
                        pending_directories.append((path, depth))
                        continue
                    if not stat.S_ISREG(metadata.st_mode):
                        raise ValueError(
                            f"museum review packet contains a non-regular file: {relative_path}"
                        )
                    if metadata.st_nlink != 1:
                        raise ValueError(
                            f"museum review packet file must have one hard link: {relative_path}"
                        )
                    file_inventory[relative_path] = _stat_fingerprint(metadata)
                    if relative_path.startswith("reviewer/evidence/"):
                        media_count += 1
                        media_bytes += metadata.st_size
                        if metadata.st_size > max_media_bytes:
                            raise ValueError(
                                f"review evidence exceeds per-file limit: {relative_path}"
                            )
                        if media_count > max_media_count:
                            raise ValueError("review evidence count exceeds limit")
                        if media_bytes > max_total_media_bytes:
                            raise ValueError("review evidence bytes exceed aggregate limit")
                    else:
                        index_bytes += metadata.st_size
                        if metadata.st_size > max_json_bytes:
                            raise ValueError(
                                f"review packet index exceeds per-file limit: {relative_path}"
                            )
                        if index_bytes > max_total_json_bytes:
                            raise ValueError("review packet indexes exceed aggregate limit")
    except (FileNotFoundError, NotADirectoryError) as error:
        raise ValueError("museum review packet changed during inventory") from error
    return file_inventory, directory_inventory


def _read_review_json(path: Path, *, max_bytes: int) -> dict[str, Any]:
    value, _ = _read_review_json_with_bytes(path, max_bytes=max_bytes)
    return value


def _read_review_json_with_bytes(
    path: Path,
    *,
    max_bytes: int,
) -> tuple[dict[str, Any], bytes]:
    raw_bytes = _read_regular_bytes(path, max_bytes=max_bytes)
    value = _museum_json_value(raw_bytes, label=str(path))
    if not isinstance(value, dict):
        raise ValueError(f"museum review JSON must be an object: {path}")
    return value, raw_bytes


def _review_ledger_inventory(
    ledger_dir: Path,
    *,
    max_json_bytes: int,
    max_total_json_bytes: int,
    max_review_count: int,
) -> tuple[
    dict[str, tuple[int, int, int, int, int, int, int]],
    dict[str, tuple[int, int, int, int, int, int, int]],
]:
    for name, value in {
        "max_json_bytes": max_json_bytes,
        "max_total_json_bytes": max_total_json_bytes,
        "max_review_count": max_review_count,
    }.items():
        if isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be positive")
    try:
        root_metadata = ledger_dir.lstat()
    except FileNotFoundError as error:
        raise ValueError(f"museum review ledger does not exist: {ledger_dir}") from error
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("museum review ledger root must be a real directory")

    file_inventory: dict[str, tuple[int, int, int, int, int, int, int]] = {}
    directory_inventory = {".": _stat_fingerprint(root_metadata)}
    total_json_bytes = 0
    entry_count = 0
    pending_directories = [(ledger_dir, 0)]
    try:
        while pending_directories:
            current_directory, current_depth = pending_directories.pop()
            with os.scandir(current_directory) as entries:
                for entry in entries:
                    entry_count += 1
                    # One manifest and two fixed stage directories are the only
                    # non-review entries in a closed ledger.
                    if entry_count > max_review_count + 3:
                        raise ValueError("museum review ledger entry count exceeds limit")
                    path = Path(entry.path)
                    metadata = entry.stat(follow_symlinks=False)
                    relative_path = path.relative_to(ledger_dir).as_posix()
                    if stat.S_ISLNK(metadata.st_mode):
                        raise ValueError(
                            f"museum review ledger contains a symbolic link: {relative_path}"
                        )
                    if stat.S_ISDIR(metadata.st_mode):
                        depth = current_depth + 1
                        if depth > 1:
                            raise ValueError(
                                "museum review ledger directory depth exceeds limit: "
                                f"{relative_path}"
                            )
                        directory_inventory[relative_path] = _stat_fingerprint(metadata)
                        pending_directories.append((path, depth))
                        continue
                    if not stat.S_ISREG(metadata.st_mode):
                        raise ValueError(
                            f"museum review ledger contains a non-regular file: {relative_path}"
                        )
                    if metadata.st_nlink != 1:
                        raise ValueError(
                            f"museum review ledger file must have one hard link: {relative_path}"
                        )
                    if metadata.st_size > max_json_bytes:
                        raise ValueError(
                            f"museum review ledger JSON exceeds per-file limit: {relative_path}"
                        )
                    total_json_bytes += metadata.st_size
                    if total_json_bytes > max_total_json_bytes:
                        raise ValueError("museum review ledger exceeds aggregate JSON byte limit")
                    file_inventory[relative_path] = _stat_fingerprint(metadata)
    except (FileNotFoundError, NotADirectoryError) as error:
        raise ValueError("museum review ledger changed during file inventory") from error
    return file_inventory, directory_inventory


@contextmanager
def _review_ledger_lock(
    ledger_dir: Path,
    *,
    exclusive: bool,
) -> Iterator[tuple[int, int, int, int, int, int, int]]:
    """Hold one advisory lock while pinning the ledger root or manifest."""

    root_metadata = ledger_dir.lstat()
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("museum review ledger root must be a real directory")
    root_fingerprint = _stat_fingerprint(root_metadata)

    if os.name == "nt":
        lock_path = ledger_dir / "ledger-manifest.json"
        descriptor = os.open(
            lock_path,
            os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        lock_module = __import__("msvcrt")
        lock_fn = lock_module.locking
        lock_mode = int(lock_module.LK_LOCK if exclusive else lock_module.LK_RLCK)
        unlock_mode = int(lock_module.LK_UNLCK)
        os.lseek(descriptor, 0, os.SEEK_SET)
        lock_fn(descriptor, lock_mode, 1)
        try:
            yield root_fingerprint
        finally:
            os.lseek(descriptor, 0, os.SEEK_SET)
            lock_fn(descriptor, unlock_mode, 1)
            os.close(descriptor)
        return

    descriptor = os.open(
        ledger_dir,
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode) or _stat_fingerprint(metadata) != root_fingerprint:
        os.close(descriptor)
        raise ValueError("museum review ledger root changed before locking")
    lock_module = __import__("fcntl")
    flock = lock_module.flock
    lock_mode = int(getattr(lock_module, "LOCK_EX" if exclusive else "LOCK_SH"))
    unlock_mode = int(lock_module.LOCK_UN)
    flock(descriptor, lock_mode)
    try:
        yield root_fingerprint
    finally:
        flock(descriptor, unlock_mode)
        os.close(descriptor)


def _initialize_review_ledger(
    ledger_dir: Path,
    *,
    packet_dir: Path,
    packet_id: str,
    packet_manifest_sha256: str,
    reviewer_manifest_sha256: str,
    ledger_schema: Path,
    initial_review_relative_path: str,
    initial_review_bytes: bytes,
    max_json_bytes: int,
    max_total_json_bytes: int,
    max_review_count: int,
) -> bool:
    _validate_review_destination(packet_dir, ledger_dir)
    if _path_lexists(ledger_dir):
        return False
    ledger_dir.parent.mkdir(parents=True, exist_ok=True)
    ledger_dir = ledger_dir.resolve(strict=False)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=".museum-review-ledger-",
            dir=ledger_dir.parent,
        )
    )
    # 0o700 is intentionally owner-only for the private review staging root.
    # nosemgrep
    os.chmod(staging_dir, 0o700)
    try:
        _assert_private_creation_root(staging_dir)
        (staging_dir / "submissions").mkdir(mode=0o700)
        (staging_dir / "adjudications").mkdir(mode=0o700)
        manifest = build_ledger_manifest(
            packet_id=packet_id,
            created_at=_utc_timestamp(),
            packet_manifest_sha256=packet_manifest_sha256,
            reviewer_manifest_sha256=reviewer_manifest_sha256,
        )
        schema_issues = validate_schema_instance(manifest, ledger_schema)
        if schema_issues:
            messages = "; ".join(f"{issue.path}: {issue.message}" for issue in schema_issues[:10])
            raise ValueError(f"generated review ledger manifest is invalid: {messages}")
        manifest_bytes = (
            json.dumps(
                manifest,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        if max_review_count < 1:
            raise ValueError("max_review_count cannot admit the initial sealed review")
        if len(manifest_bytes) > max_json_bytes:
            raise ValueError("review ledger manifest exceeds the per-file JSON byte limit")
        if len(initial_review_bytes) > max_json_bytes:
            raise ValueError("canonical draft exceeds the per-file JSON byte limit")
        if len(manifest_bytes) + len(initial_review_bytes) > max_total_json_bytes:
            raise ValueError("initial ledger and review exceed the aggregate JSON byte limit")
        review_relative_path = PurePosixPath(initial_review_relative_path)
        if (
            review_relative_path.is_absolute()
            or ".." in review_relative_path.parts
            or len(review_relative_path.parts) != 2
            or review_relative_path.parts[0] not in {"submissions", "adjudications"}
        ):
            raise ValueError("initial sealed review path is unsafe")
        manifest_path = staging_dir / "ledger-manifest.json"
        review_path = staging_dir / review_relative_path
        for path, raw_bytes in (
            (manifest_path, manifest_bytes),
            (review_path, initial_review_bytes),
        ):
            descriptor = os.open(
                path,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(path, 0o600)
        _assert_private_tree(staging_dir)
        _fsync_directory(staging_dir / "submissions")
        _fsync_directory(staging_dir / "adjudications")
        _fsync_directory(staging_dir)
        try:
            _rename_directory_no_replace(staging_dir, ledger_dir)
        except FileExistsError:
            if not _path_lexists(ledger_dir):
                raise
            return False
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
            _fsync_directory(ledger_dir.parent)
    return True


def _empty_review_chain_summary(subject_count: int) -> dict[str, Any]:
    return {
        "valid": False,
        "errors": [],
        "sealed_review_count": 0,
        "validated_review_count": 0,
        "independent_review_count": 0,
        "active_independent_review_count": 0,
        "adjudication_count": 0,
        "active_adjudication_count": 0,
        "superseded_review_count": 0,
        "subjects_with_two_reviews": 0,
        "adjudication_ready_subjects": 0,
        "adjudicated_subjects": 0,
        "stale_adjudication_subjects": 0,
        "exact_crosswalk_count": 0,
        "chain_supported_exact_crosswalk_count": 0,
        "accepted_active_exact_crosswalk_count": 0,
        "identity_roster_bound": False,
        "append_only_proven": False,
        "seal_chronology_bound": False,
        "promotion_ready_subjects": 0,
        "independence_assurance": (
            "distinct pseudonymous actor_id and assignment_id only; "
            "identity-custodian roster not yet bound"
        ),
        "chronology_assurance": (
            "actor-declared reviewed_at chronology only; no controller-sealed "
            "timestamp or monotonic sequence is bound"
        ),
        "unresolved_subjects": subject_count,
    }


def _load_review_ledger(
    *,
    packet_dir: Path,
    ledger_dir: Path,
    packet_payload: dict[str, Any],
    subjects: list[dict[str, Any]],
    review_schema: Path,
    ledger_schema: Path,
    max_json_bytes: int,
    max_total_json_bytes: int,
    max_review_count: int,
    locked_root_fingerprint: tuple[int, int, int, int, int, int, int],
) -> tuple[int, dict[str, Any], dict[str, dict[str, Any]]]:
    preflight_files, preflight_directories = _review_ledger_inventory(
        ledger_dir,
        max_json_bytes=max_json_bytes,
        max_total_json_bytes=max_total_json_bytes,
        max_review_count=max_review_count,
    )
    mismatches: list[str] = []
    if preflight_directories.get(".") != locked_root_fingerprint:
        mismatches.append("review ledger root differs from the locked directory")

    expected_directories = {".", "submissions", "adjudications"}
    actual_directories = set(preflight_directories)
    mismatches.extend(
        f"unexpected review ledger directory: {path}"
        for path in sorted(actual_directories - expected_directories)
    )
    mismatches.extend(
        f"missing review ledger directory: {path}"
        for path in sorted(expected_directories - actual_directories)
    )

    if os.name == "nt":
        mismatches.append(
            "private review-ledger verification is unsupported without Windows ACL checks"
        )
    else:
        for path, fingerprint in {
            **preflight_directories,
            **preflight_files,
        }.items():
            if stat.S_IMODE(fingerprint[2]) & 0o077:
                mismatches.append(f"review ledger path is accessible to group/other: {path}")
            absolute_path = ledger_dir if path == "." else ledger_dir / PurePosixPath(path)
            if _path_has_extended_acl(absolute_path):
                mismatches.append(f"review ledger path has an unsupported extended ACL: {path}")

    manifest_path = ledger_dir / "ledger-manifest.json"
    manifest = _read_review_json(manifest_path, max_bytes=max_json_bytes)
    try:
        validate_ledger_manifest(manifest)
    except ValueError as error:
        mismatches.append(f"ledger manifest: {error}")
    manifest_schema_issues = validate_schema_instance(manifest, ledger_schema)
    mismatches.extend(f"{issue.path}: {issue.message}" for issue in manifest_schema_issues)

    reviewer_manifest_sha256 = packet_payload["reviewer_manifest_sha256"]
    source_commitment = manifest.get("source_commitment")
    if not isinstance(source_commitment, dict):
        mismatches.append("ledger manifest source_commitment is not an object")
    else:
        if (
            source_commitment.get("packet_manifest_sha256")
            != packet_payload["packet_manifest_sha256"]
        ):
            mismatches.append("ledger packet-manifest commitment mismatch")
        if source_commitment.get("reviewer_manifest_sha256") != reviewer_manifest_sha256:
            mismatches.append("ledger reviewer-manifest commitment mismatch")
    if manifest.get("packet_id") != packet_payload["packet_id"]:
        mismatches.append("ledger packet_id mismatch")

    expected_files = {"ledger-manifest.json"}
    sealed_reviews: dict[str, dict[str, Any]] = {}
    validate_review_schema = compile_schema_validator(review_schema)
    for relative_path in sorted(path for path in preflight_files if path != "ledger-manifest.json"):
        match = SEALED_REVIEW_PATH_PATTERN.fullmatch(relative_path)
        if match is None:
            mismatches.append(f"unexpected review ledger file: {relative_path}")
            continue
        expected_files.add(relative_path)
        raw_bytes = _read_regular_bytes(
            ledger_dir / PurePosixPath(relative_path),
            max_bytes=max_json_bytes,
        )
        digest = "sha256:" + match.group(2)
        if "sha256:" + hashlib.sha256(raw_bytes).hexdigest() != digest:
            mismatches.append(f"{relative_path}: filename digest mismatch")
            continue
        value = _museum_json_value(raw_bytes, label=relative_path)
        if not isinstance(value, dict):
            mismatches.append(f"{relative_path}: sealed review must be an object")
            continue
        try:
            canonical_bytes = canonical_review_bytes(value)
        except ValueError as error:
            mismatches.append(f"{relative_path}: non-canonical JSON value: {error}")
            continue
        if raw_bytes != canonical_bytes:
            mismatches.append(f"{relative_path}: raw bytes are not the canonical serialization")
            continue
        try:
            expected_path = review_relative_path(value, digest)
        except ValueError as error:
            mismatches.append(f"{relative_path}: {error}")
            continue
        if relative_path != expected_path:
            mismatches.append(f"{relative_path}: review_stage directory mismatch")
            continue
        schema_issues = validate_review_schema(value, "$")
        if schema_issues:
            mismatches.extend(
                f"{relative_path}{issue.path.removeprefix('$')}: {issue.message}"
                for issue in schema_issues
            )
            continue
        sealed_reviews[digest] = value

    actual_files = set(preflight_files)
    mismatches.extend(
        f"missing review ledger file: {path}" for path in sorted(expected_files - actual_files)
    )

    if isinstance(source_commitment, dict):
        chain = audit_review_chain(
            sealed_reviews,
            subjects,
            packet_id=packet_payload["packet_id"],
            reviewer_manifest_sha256=reviewer_manifest_sha256,
            required_independent_reviews=(
                packet_payload["required_independent_reviews_per_subject"]
            ),
        )
    else:
        chain = _empty_review_chain_summary(len(subjects))
    mismatches.extend(chain["errors"])

    postflight_files, postflight_directories = _review_ledger_inventory(
        ledger_dir,
        max_json_bytes=max_json_bytes,
        max_total_json_bytes=max_total_json_bytes,
        max_review_count=max_review_count,
    )
    if postflight_files != preflight_files or postflight_directories != preflight_directories:
        mismatches.append("museum review ledger changed during verification")

    valid = not mismatches and chain["valid"]
    if not valid:
        for field in (
            "subjects_with_two_reviews",
            "adjudication_ready_subjects",
            "adjudicated_subjects",
            "chain_supported_exact_crosswalk_count",
            "accepted_active_exact_crosswalk_count",
            "promotion_ready_subjects",
        ):
            chain[field] = 0
        chain["unresolved_subjects"] = len(subjects)
    payload = {
        "self_consistent": valid,
        "packet": str(packet_dir),
        "ledger": str(ledger_dir),
        "packet_id": packet_payload["packet_id"],
        "ledger_id": manifest.get("ledger_id"),
        "packet_manifest_sha256": packet_payload["packet_manifest_sha256"],
        "reviewer_manifest_sha256": reviewer_manifest_sha256,
        "source_externally_anchored": packet_payload["source_externally_anchored"],
        "ledger_externally_checkpointed": False,
        "publication_or_training_release_allowed": False,
        "publication_blocks": [
            "identity_custodian_roster_not_bound",
            "ledger_not_externally_checkpointed",
            "rights_review_not_approved",
            "cultural_heritage_review_not_approved",
            *(
                []
                if packet_payload["source_externally_anchored"]
                else ["source_packet_not_externally_anchored"]
            ),
        ],
        **chain,
        "valid": valid,
        "mismatches": mismatches,
    }
    return (0 if valid else 2), payload, sealed_reviews


def _custody_sensitive_strings(custody_map: dict[str, Any]) -> set[str]:
    sensitive: set[str] = set()
    for subject in custody_map.get("subjects", []):
        if not isinstance(subject, dict):
            continue
        for field in ("intake_id", "source_id"):
            value = subject.get(field)
            if isinstance(value, str):
                sensitive.add(value)
        for field in ("institution", "official_record"):
            value = subject.get(field)
            if isinstance(value, dict):
                sensitive.update(item for item in value.values() if isinstance(item, str))
        for group in subject.get("view_groups", []):
            if not isinstance(group, dict):
                continue
            for image in group.get("images", []):
                if not isinstance(image, dict):
                    continue
                for field in (
                    "media_id",
                    "provider_derivative",
                    "provider_view_role",
                    "source_uri",
                    "source_bundle_relative_path",
                ):
                    value = image.get(field)
                    if isinstance(value, str):
                        sensitive.add(value)
    return {value for value in sensitive if len(value) >= 6}


def _invalid_review_packet_payload(
    packet_dir: Path,
    mismatches: list[str],
    *,
    packet_id: object = None,
) -> dict[str, Any]:
    return {
        "valid": False,
        "self_consistent": False,
        "packet": str(packet_dir),
        "packet_id": packet_id,
        "mismatches": mismatches,
    }


def _verify_museum_review_payload(
    args: argparse.Namespace,
) -> tuple[int, dict[str, Any]]:
    packet_dir: Path = args.packet_dir
    preflight_files, preflight_directories = _review_packet_inventory(
        packet_dir,
        max_json_bytes=args.max_json_bytes,
        max_media_bytes=args.max_media_bytes,
        max_media_count=args.max_media_count,
        max_total_json_bytes=args.max_total_json_bytes,
        max_total_media_bytes=args.max_total_media_bytes,
    )
    packet_manifest_path = packet_dir / "packet-manifest.json"
    packet_manifest, packet_manifest_bytes = _read_review_json_with_bytes(
        packet_manifest_path,
        max_bytes=args.max_json_bytes,
    )
    try:
        validate_packet_manifest_semantics(packet_manifest)
    except ValueError as error:
        return (
            2,
            _invalid_review_packet_payload(
                packet_dir,
                [f"packet manifest: {error}"],
                packet_id=packet_manifest.get("packet_id"),
            ),
        )

    reviewer_manifest_path = packet_dir / "reviewer/manifest.json"
    custody_path = packet_dir / "custody/identity-map.json"
    reviewer_manifest, reviewer_manifest_bytes = _read_review_json_with_bytes(
        reviewer_manifest_path,
        max_bytes=args.max_json_bytes,
    )
    custody_map, custody_bytes = _read_review_json_with_bytes(
        custody_path,
        max_bytes=args.max_json_bytes,
    )
    semantic_mismatches: list[str] = []
    try:
        validate_reviewer_manifest_semantics(reviewer_manifest)
    except ValueError as error:
        semantic_mismatches.append(f"reviewer manifest: {error}")
    try:
        validate_custody_semantics(custody_map)
    except ValueError as error:
        semantic_mismatches.append(f"custody map: {error}")
    if semantic_mismatches:
        return (
            2,
            _invalid_review_packet_payload(
                packet_dir,
                semantic_mismatches,
                packet_id=packet_manifest["packet_id"],
            ),
        )

    subjects_path = packet_dir / "reviewer/subjects.jsonl"
    subjects_bytes = _read_regular_bytes(
        subjects_path,
        max_bytes=args.max_json_bytes,
    )
    subjects = _museum_records_from_bytes(
        subjects_bytes,
        label=str(subjects_path),
    )
    subjects_file_sha256 = "sha256:" + hashlib.sha256(subjects_bytes).hexdigest()
    subject_schema: Path | None = args.review_subject_schema
    if subject_schema is None:
        subject_schema = _default_museum_review_subject_schema()
    if subject_schema is None:
        raise ValueError("museum review subject schema not found; pass --review-subject-schema")

    mismatches: list[str] = []
    schema_issues = []
    validate_subject_schema = compile_schema_validator(subject_schema)
    for index, subject in enumerate(subjects):
        try:
            validate_subject_semantics(subject)
        except ValueError as error:
            mismatches.append(f"subjects[{index}]: {error}")
            continue
        schema_issues.extend(
            validate_subject_schema(
                subject,
                f"$[{index}]",
            )
        )
    mismatches.extend(f"{issue.path}: {issue.message}" for issue in schema_issues)

    expected_files = {
        "packet-manifest.json",
        "reviewer/manifest.json",
        "reviewer/subjects.jsonl",
        "reviewer/REVIEW_INSTRUCTIONS.md",
        "custody/identity-map.json",
    }
    manifest_evidence: dict[str, dict[str, Any]] = {}
    for item in reviewer_manifest["evidence"]:
        image_id = item["image_id"]
        if image_id in manifest_evidence:
            mismatches.append(f"duplicate reviewer manifest image_id: {image_id}")
        manifest_evidence[image_id] = item
        expected_files.add("reviewer/" + item["relative_path"])
    actual_files = set(preflight_files)
    mismatches.extend(
        f"unexpected review packet file: {path}" for path in sorted(actual_files - expected_files)
    )
    mismatches.extend(
        f"missing review packet file: {path}" for path in sorted(expected_files - actual_files)
    )
    expected_directories = {".", "reviewer", "reviewer/evidence", "custody"}
    actual_directories = set(preflight_directories)
    mismatches.extend(
        f"unexpected review packet directory: {path}"
        for path in sorted(actual_directories - expected_directories)
    )
    mismatches.extend(
        f"missing review packet directory: {path}"
        for path in sorted(expected_directories - actual_directories)
    )

    if os.name == "nt":
        mismatches.append(
            "private review-packet verification is unsupported without Windows ACL checks"
        )
    else:
        for path, fingerprint in {
            **preflight_directories,
            **preflight_files,
        }.items():
            if stat.S_IMODE(fingerprint[2]) & 0o077:
                mismatches.append(f"review packet path is accessible to group/other: {path}")
            absolute_path = packet_dir if path == "." else packet_dir / PurePosixPath(path)
            if _path_has_extended_acl(absolute_path):
                mismatches.append(f"review packet path has an unsupported extended ACL: {path}")

    reviewer_manifest_sha256 = "sha256:" + hashlib.sha256(reviewer_manifest_bytes).hexdigest()
    if reviewer_manifest_sha256 != packet_manifest["reviewer_packet"]["manifest_sha256"]:
        mismatches.append("reviewer manifest hash does not match packet manifest")
    if (
        "sha256:" + hashlib.sha256(custody_bytes).hexdigest()
        != packet_manifest["custody"]["identity_map_sha256"]
    ):
        mismatches.append("custody map hash does not match packet manifest")
    if subjects_file_sha256 != reviewer_manifest["subjects_file_sha256"]:
        mismatches.append("subjects file hash does not match reviewer manifest")
    instructions_path = packet_dir / "reviewer/REVIEW_INSTRUCTIONS.md"
    instructions_bytes = _read_regular_bytes(
        instructions_path,
        max_bytes=args.max_json_bytes,
    )
    if (
        "sha256:" + hashlib.sha256(instructions_bytes).hexdigest()
        != reviewer_manifest["instructions_file_sha256"]
    ):
        mismatches.append("instructions hash does not match reviewer manifest")

    for image_id, item in manifest_evidence.items():
        path = packet_dir / "reviewer" / PurePosixPath(item["relative_path"])
        if (
            item["bytes"]
            != preflight_files.get(
                "reviewer/" + item["relative_path"],
                (0, 0, 0, -1, 0, 0, 0),
            )[3]
        ):
            mismatches.append(f"{image_id}: evidence byte count mismatch")
            continue
        if _sha256_regular_file(path) != item["sha256"]:
            mismatches.append(f"{image_id}: evidence hash mismatch")

    subject_ids: list[str] = []
    subject_evidence: dict[str, dict[str, Any]] = {}
    for subject in subjects:
        subject_ids.append(subject.get("subject_id", ""))
        if subject.get("packet_id") != packet_manifest["packet_id"]:
            mismatches.append(f"{subject.get('subject_id')}: packet_id does not match controller")
        for group in subject.get("view_groups", []):
            for image in group.get("evidence_images", []):
                image_id = image.get("image_id")
                if image_id in subject_evidence:
                    mismatches.append(f"duplicate subject image_id: {image_id}")
                elif isinstance(image_id, str):
                    subject_evidence[image_id] = image
    if subject_evidence != manifest_evidence:
        mismatches.append("subject evidence inventory does not match reviewer manifest")
    if len(set(subject_ids)) != len(subject_ids):
        mismatches.append("review subjects contain duplicate subject_id values")

    view_group_count = sum(len(subject.get("view_groups", [])) for subject in subjects)
    counts = {
        "subject_count": len(subjects),
        "view_group_count": view_group_count,
        "evidence_image_count": len(subject_evidence),
        "evidence_bytes": sum(item["bytes"] for item in subject_evidence.values()),
    }
    for field, actual in counts.items():
        if reviewer_manifest.get(field) != actual:
            mismatches.append(
                f"reviewer manifest {field}: "
                f"declared={reviewer_manifest.get(field)!r}, actual={actual!r}"
            )
        if packet_manifest.get(field) != actual:
            mismatches.append(
                f"packet manifest {field}: "
                f"declared={packet_manifest.get(field)!r}, actual={actual!r}"
            )

    if reviewer_manifest["packet_id"] != packet_manifest["packet_id"]:
        mismatches.append("reviewer manifest packet_id does not match controller")
    if custody_map["packet_id"] != packet_manifest["packet_id"]:
        mismatches.append("custody packet_id does not match controller")
    custody_subject_ids = {item["subject_id"] for item in custody_map["subjects"]}
    if custody_subject_ids != set(subject_ids):
        mismatches.append("custody subject mapping does not match blind subjects")
    custody_evidence = {
        image["image_id"]: {
            "image_id": image["image_id"],
            "sha256": image["sha256"],
            "bytes": image["bytes"],
            "content_type": image["content_type"],
            "relative_path": image["review_relative_path"],
        }
        for subject in custody_map["subjects"]
        for group in subject["view_groups"]
        for image in group["images"]
    }
    if custody_evidence != subject_evidence:
        mismatches.append("custody image mapping does not match blind evidence")

    reviewer_text = "\n".join(
        raw.decode("utf-8")
        for raw in (
            subjects_bytes,
            instructions_bytes,
            reviewer_manifest_bytes,
        )
    )
    leaked_values = sorted(
        value for value in _custody_sensitive_strings(custody_map) if value in reviewer_text
    )
    if leaked_values:
        mismatches.append(
            "reviewer text contains custody identity values: "
            + ", ".join(repr(value) for value in leaked_values[:5])
        )

    postflight_files, postflight_directories = _review_packet_inventory(
        packet_dir,
        max_json_bytes=args.max_json_bytes,
        max_media_bytes=args.max_media_bytes,
        max_media_count=args.max_media_count,
        max_total_json_bytes=args.max_total_json_bytes,
        max_total_media_bytes=args.max_total_media_bytes,
    )
    if postflight_files != preflight_files or postflight_directories != preflight_directories:
        mismatches.append("museum review packet changed during verification")

    packet_manifest_sha256 = "sha256:" + hashlib.sha256(packet_manifest_bytes).hexdigest()
    expected_packet_manifest_sha256 = getattr(
        args,
        "expected_packet_manifest_sha256",
        None,
    )
    if (
        expected_packet_manifest_sha256 is not None
        and packet_manifest_sha256 != expected_packet_manifest_sha256
    ):
        mismatches.append("packet manifest does not match caller-supplied external digest")

    payload = {
        "valid": not mismatches,
        "self_consistent": not mismatches,
        "packet": str(packet_dir),
        "packet_id": packet_manifest["packet_id"],
        "packet_manifest_sha256": packet_manifest_sha256,
        "reviewer_manifest_sha256": reviewer_manifest_sha256,
        "subjects_file_sha256": subjects_file_sha256,
        **counts,
        "required_independent_reviews_per_subject": (
            packet_manifest["required_independent_reviews_per_subject"]
        ),
        "source_externally_anchored": packet_manifest["source_bundle"]["externally_anchored"],
        "publication_gate": packet_manifest["publication_gate"],
        "catalog_blind_text_leak_check": "passed" if not leaked_values else "failed",
        "mismatches": mismatches,
    }
    return (0 if not mismatches else 2), payload


def _command_verify_museum_review(args: argparse.Namespace) -> int:
    try:
        exit_code, payload = _verify_museum_review_payload(args)
    except ValueError as error:
        payload = _invalid_review_packet_payload(
            args.packet_dir,
            [str(error)],
        )
        exit_code = 2
    _print_json(payload)
    return exit_code


def _review_ledger_schemas(
    args: argparse.Namespace,
) -> tuple[Path, Path]:
    review_schema: Path | None = args.review_schema
    if review_schema is None:
        review_schema = _default_museum_review_schema()
    if review_schema is None:
        raise ValueError("museum review schema not found; pass --review-schema")
    ledger_schema: Path | None = args.review_ledger_schema
    if ledger_schema is None:
        ledger_schema = _default_museum_review_ledger_schema()
    if ledger_schema is None:
        raise ValueError("museum review ledger schema not found; pass --review-ledger-schema")
    return review_schema, ledger_schema


def _packet_subjects(
    packet_dir: Path,
    *,
    expected_sha256: str,
    max_bytes: int,
) -> list[dict[str, Any]]:
    subjects_path = packet_dir / "reviewer/subjects.jsonl"
    raw_bytes = _read_regular_bytes(subjects_path, max_bytes=max_bytes)
    actual_sha256 = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "review subjects changed after packet verification; "
            f"expected {expected_sha256}, got {actual_sha256}"
        )
    return _museum_records_from_bytes(raw_bytes, label=str(subjects_path))


def _validate_review_draft_for_packet(
    *,
    draft_path: Path,
    review_schema: Path,
    packet_payload: dict[str, Any],
    subjects: list[dict[str, Any]],
    max_json_bytes: int,
) -> tuple[
    dict[str, Any] | None,
    bytes,
    str,
    str,
    list[str],
]:
    try:
        draft = _read_review_json(draft_path, max_bytes=max_json_bytes)
    except ValueError as error:
        return None, b"", "", "", [f"draft parse failed: {error}"]

    draft_schema_issues = validate_schema_instance(draft, review_schema)
    errors = [f"{issue.path}: {issue.message}" for issue in draft_schema_issues]
    subject_by_id = {
        subject["subject_id"]: subject
        for subject in subjects
        if isinstance(subject.get("subject_id"), str)
    }
    subject = subject_by_id.get(draft.get("subject_id"))
    if subject is None:
        errors.append("draft cites an unknown review subject")
    else:
        try:
            validate_review_submission(draft, subject=subject)
        except ValueError as error:
            errors.append(str(error))
    if draft.get("packet_id") != packet_payload["packet_id"]:
        errors.append("draft packet_id does not match the verified packet")
    source_commitment = draft.get("source_commitment")
    if (
        not isinstance(source_commitment, dict)
        or source_commitment.get("reviewer_manifest_sha256")
        != packet_payload["reviewer_manifest_sha256"]
    ):
        errors.append("draft reviewer-manifest commitment does not match the packet")
    try:
        canonical_bytes = canonical_review_bytes(draft)
        digest = review_digest(draft)
        relative_path = review_relative_path(draft, digest)
    except ValueError as error:
        errors.append(f"draft canonicalization failed: {error}")
        canonical_bytes = b""
        digest = ""
        relative_path = ""
    if canonical_bytes and len(canonical_bytes) > max_json_bytes:
        errors.append("canonical draft exceeds the per-file JSON byte limit")
    return draft, canonical_bytes, digest, relative_path, errors


def _command_verify_museum_review_ledger(args: argparse.Namespace) -> int:
    try:
        return _verify_museum_review_ledger(args)
    except ValueError as error:
        _print_json(
            {
                "valid": False,
                "self_consistent": False,
                "packet": str(args.packet_dir),
                "ledger": str(args.ledger_dir),
                "publication_or_training_release_allowed": False,
                "mismatches": [str(error)],
            }
        )
        return 2


def _verify_museum_review_ledger(args: argparse.Namespace) -> int:
    review_schema, ledger_schema = _review_ledger_schemas(args)
    with _review_ledger_lock(args.ledger_dir, exclusive=False) as root_fingerprint:
        packet_exit_code, packet_payload = _verify_museum_review_payload(args)
        if packet_exit_code != 0:
            _print_json(
                {
                    "valid": False,
                    "packet": str(args.packet_dir),
                    "ledger": str(args.ledger_dir),
                    "packet_verification": packet_payload,
                }
            )
            return 2
        subjects = _packet_subjects(
            args.packet_dir,
            expected_sha256=packet_payload["subjects_file_sha256"],
            max_bytes=args.max_json_bytes,
        )
        ledger_exit_code, payload, _ = _load_review_ledger(
            packet_dir=args.packet_dir,
            ledger_dir=args.ledger_dir,
            packet_payload=packet_payload,
            subjects=subjects,
            review_schema=review_schema,
            ledger_schema=ledger_schema,
            max_json_bytes=args.max_json_bytes,
            max_total_json_bytes=args.max_total_json_bytes,
            max_review_count=args.max_review_count,
            locked_root_fingerprint=root_fingerprint,
        )
        post_packet_exit_code, post_packet_payload = _verify_museum_review_payload(args)
        if post_packet_exit_code != 0 or post_packet_payload != packet_payload:
            payload["valid"] = False
            payload["self_consistent"] = False
            payload["mismatches"].append("museum review packet changed during ledger verification")
            for field in (
                "subjects_with_two_reviews",
                "adjudication_ready_subjects",
                "adjudicated_subjects",
                "chain_supported_exact_crosswalk_count",
                "accepted_active_exact_crosswalk_count",
                "promotion_ready_subjects",
            ):
                payload[field] = 0
            payload["unresolved_subjects"] = len(subjects)
            ledger_exit_code = 2
    _print_json(payload)
    return ledger_exit_code


def _command_seal_museum_review(args: argparse.Namespace) -> int:
    commit_state: dict[str, Any] = {
        "committed": False,
        "review_sha256": None,
        "relative_path": None,
    }
    try:
        return _seal_museum_review(args, commit_state=commit_state)
    except (OSError, ValueError) as error:
        relative_path = commit_state.get("relative_path")
        expected_digest = commit_state.get("review_sha256")
        if (
            commit_state["committed"] is False
            and isinstance(relative_path, str)
            and isinstance(expected_digest, str)
        ):
            try:
                committed_bytes = _read_regular_bytes(
                    args.ledger_dir / PurePosixPath(relative_path),
                    max_bytes=args.max_json_bytes,
                )
            except ValueError:
                committed_bytes = b""
            if (
                committed_bytes
                and "sha256:" + hashlib.sha256(committed_bytes).hexdigest() == expected_digest
            ):
                commit_state["committed"] = True
        _print_json(
            {
                "sealed": commit_state["committed"],
                "valid": False,
                "packet": str(args.packet_dir),
                "ledger": str(args.ledger_dir),
                "draft": str(args.draft),
                "review_sha256": commit_state["review_sha256"],
                "relative_path": commit_state["relative_path"],
                "postcondition": (
                    (
                        "committed_durability_unknown"
                        if isinstance(error, OSError)
                        else "committed_but_post_verification_failed"
                    )
                    if commit_state["committed"]
                    else (
                        "not_committed_operational_failure"
                        if isinstance(error, OSError)
                        else "not_committed"
                    )
                ),
                "errors": [str(error)],
            }
        )
        return 1 if isinstance(error, OSError) else 2


def _seal_museum_review(
    args: argparse.Namespace,
    *,
    commit_state: dict[str, Any],
) -> int:
    review_schema, ledger_schema = _review_ledger_schemas(args)
    packet_exit_code, packet_payload = _verify_museum_review_payload(args)
    if packet_exit_code != 0:
        _print_json(
            {
                "sealed": False,
                "packet": str(args.packet_dir),
                "ledger": str(args.ledger_dir),
                "draft": str(args.draft),
                "packet_verification": packet_payload,
            }
        )
        return 2

    subjects = _packet_subjects(
        args.packet_dir,
        expected_sha256=packet_payload["subjects_file_sha256"],
        max_bytes=args.max_json_bytes,
    )
    draft, canonical_bytes, digest, relative_path, draft_errors = _validate_review_draft_for_packet(
        draft_path=args.draft,
        review_schema=review_schema,
        packet_payload=packet_payload,
        subjects=subjects,
        max_json_bytes=args.max_json_bytes,
    )
    if draft_errors or draft is None:
        _print_json(
            {
                "sealed": False,
                "valid": False,
                "ledger_created": False,
                "packet_id": packet_payload["packet_id"],
                "draft": str(args.draft),
                "errors": draft_errors,
            }
        )
        return 2
    commit_state["review_sha256"] = digest
    commit_state["relative_path"] = relative_path

    ledger_created = False
    already_sealed = False
    if not _path_lexists(args.ledger_dir):
        initial_chain = audit_review_chain(
            {digest: draft},
            subjects,
            packet_id=packet_payload["packet_id"],
            reviewer_manifest_sha256=packet_payload["reviewer_manifest_sha256"],
            required_independent_reviews=(
                packet_payload["required_independent_reviews_per_subject"]
            ),
        )
        if not initial_chain["valid"]:
            _print_json(
                {
                    "sealed": False,
                    "valid": False,
                    "ledger_created": False,
                    "packet_id": packet_payload["packet_id"],
                    "draft": str(args.draft),
                    "review_sha256": digest,
                    "errors": initial_chain["errors"],
                }
            )
            return 2
        precreate_exit_code, precreate_payload = _verify_museum_review_payload(args)
        if precreate_exit_code != 0 or precreate_payload != packet_payload:
            _print_json(
                {
                    "sealed": False,
                    "valid": False,
                    "ledger_created": False,
                    "packet_id": packet_payload["packet_id"],
                    "draft": str(args.draft),
                    "errors": ["museum review packet changed before ledger creation"],
                }
            )
            return 2
        _packet_subjects(
            args.packet_dir,
            expected_sha256=packet_payload["subjects_file_sha256"],
            max_bytes=args.max_json_bytes,
        )
        ledger_created = _initialize_review_ledger(
            args.ledger_dir,
            packet_dir=args.packet_dir,
            packet_id=packet_payload["packet_id"],
            packet_manifest_sha256=packet_payload["packet_manifest_sha256"],
            reviewer_manifest_sha256=packet_payload["reviewer_manifest_sha256"],
            ledger_schema=ledger_schema,
            initial_review_relative_path=relative_path,
            initial_review_bytes=canonical_bytes,
            max_json_bytes=args.max_json_bytes,
            max_total_json_bytes=args.max_total_json_bytes,
            max_review_count=args.max_review_count,
        )
        if ledger_created:
            commit_state.update(
                {
                    "committed": True,
                    "review_sha256": digest,
                    "relative_path": relative_path,
                }
            )

    with _review_ledger_lock(args.ledger_dir, exclusive=True) as root_fingerprint:
        locked_packet_exit_code, locked_packet_payload = _verify_museum_review_payload(args)
        if locked_packet_exit_code != 0 or locked_packet_payload != packet_payload:
            _print_json(
                {
                    "sealed": commit_state["committed"],
                    "ledger_created": ledger_created,
                    "packet_verification": locked_packet_payload,
                    "review_sha256": commit_state["review_sha256"],
                    "relative_path": commit_state["relative_path"],
                    "postcondition": (
                        "committed_but_post_verification_failed"
                        if commit_state["committed"]
                        else "not_committed"
                    ),
                    "errors": ["museum review packet changed before sealing"],
                }
            )
            return 2
        subjects = _packet_subjects(
            args.packet_dir,
            expected_sha256=locked_packet_payload["subjects_file_sha256"],
            max_bytes=args.max_json_bytes,
        )
        ledger_exit_code, ledger_payload, sealed_reviews = _load_review_ledger(
            packet_dir=args.packet_dir,
            ledger_dir=args.ledger_dir,
            packet_payload=locked_packet_payload,
            subjects=subjects,
            review_schema=review_schema,
            ledger_schema=ledger_schema,
            max_json_bytes=args.max_json_bytes,
            max_total_json_bytes=args.max_total_json_bytes,
            max_review_count=args.max_review_count,
            locked_root_fingerprint=root_fingerprint,
        )
        if ledger_exit_code != 0:
            _print_json(
                {
                    "sealed": commit_state["committed"],
                    "ledger_created": ledger_created,
                    "ledger_verification": ledger_payload,
                    "review_sha256": commit_state["review_sha256"],
                    "relative_path": commit_state["relative_path"],
                    "postcondition": (
                        "committed_but_post_verification_failed"
                        if commit_state["committed"]
                        else "not_committed"
                    ),
                }
            )
            return 2

        if digest in sealed_reviews:
            if not ledger_created:
                already_sealed = True
            post_ledger_exit_code = ledger_exit_code
            post_ledger_payload = ledger_payload
            post_reviews = sealed_reviews
        else:
            append_errors: list[str] = []
            if len(sealed_reviews) + 1 > args.max_review_count:
                append_errors.append("sealing the draft would exceed max_review_count")
            current_files, _ = _review_ledger_inventory(
                args.ledger_dir,
                max_json_bytes=args.max_json_bytes,
                max_total_json_bytes=args.max_total_json_bytes,
                max_review_count=args.max_review_count,
            )
            current_json_bytes = sum(fingerprint[3] for fingerprint in current_files.values())
            if current_json_bytes + len(canonical_bytes) > args.max_total_json_bytes:
                append_errors.append("sealing the draft would exceed the aggregate JSON byte limit")
            if append_errors:
                _print_json(
                    {
                        "sealed": False,
                        "valid": False,
                        "ledger_created": ledger_created,
                        "packet_id": locked_packet_payload["packet_id"],
                        "draft": str(args.draft),
                        "errors": append_errors,
                    }
                )
                return 2

            candidate_reviews = {**sealed_reviews, digest: draft}
            candidate_chain = audit_review_chain(
                candidate_reviews,
                subjects,
                packet_id=locked_packet_payload["packet_id"],
                reviewer_manifest_sha256=(locked_packet_payload["reviewer_manifest_sha256"]),
                required_independent_reviews=(
                    locked_packet_payload["required_independent_reviews_per_subject"]
                ),
            )
            if not candidate_chain["valid"]:
                _print_json(
                    {
                        "sealed": False,
                        "valid": False,
                        "ledger_created": ledger_created,
                        "packet_id": locked_packet_payload["packet_id"],
                        "draft": str(args.draft),
                        "review_sha256": digest,
                        "errors": candidate_chain["errors"],
                    }
                )
                return 2

            destination = args.ledger_dir / PurePosixPath(relative_path)
            staging_dir = Path(
                tempfile.mkdtemp(
                    prefix=".museum-review-seal-",
                    dir=args.ledger_dir.parent,
                )
            )
            # 0o700 is intentionally owner-only for private review staging.
            # nosemgrep
            os.chmod(staging_dir, 0o700)
            temporary_path = staging_dir / destination.name
            temporary_descriptor = -1
            try:
                _assert_private_creation_root(staging_dir)
                temporary_descriptor = os.open(
                    temporary_path,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                with os.fdopen(temporary_descriptor, "wb") as handle:
                    temporary_descriptor = -1
                    handle.write(canonical_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary_path, 0o600)
                if (
                    _read_regular_bytes(
                        temporary_path,
                        max_bytes=args.max_json_bytes,
                    )
                    != canonical_bytes
                    or _sha256_regular_file(temporary_path) != digest
                ):
                    raise OSError(
                        errno.EIO,
                        "sealed review staging verification failed",
                        str(temporary_path),
                    )
                _rename_regular_file_no_replace(temporary_path, destination)
                commit_state.update(
                    {
                        "committed": True,
                        "review_sha256": digest,
                        "relative_path": relative_path,
                    }
                )
            finally:
                if temporary_descriptor >= 0:
                    os.close(temporary_descriptor)
                if staging_dir.exists():
                    shutil.rmtree(staging_dir)
                    _fsync_directory(args.ledger_dir.parent)

            post_ledger_exit_code, post_ledger_payload, post_reviews = _load_review_ledger(
                packet_dir=args.packet_dir,
                ledger_dir=args.ledger_dir,
                packet_payload=locked_packet_payload,
                subjects=subjects,
                review_schema=review_schema,
                ledger_schema=ledger_schema,
                max_json_bytes=args.max_json_bytes,
                max_total_json_bytes=args.max_total_json_bytes,
                max_review_count=args.max_review_count,
                locked_root_fingerprint=root_fingerprint,
            )
        post_packet_exit_code, post_packet_payload = _verify_museum_review_payload(args)
        if (
            post_ledger_exit_code != 0
            or digest not in post_reviews
            or post_packet_exit_code != 0
            or post_packet_payload != locked_packet_payload
        ):
            post_ledger_payload["valid"] = False
            post_ledger_payload["self_consistent"] = False
            post_ledger_payload["mismatches"].append(
                "packet or ledger changed during sealed review publication"
            )
            _print_json(
                {
                    "sealed": True,
                    "valid": False,
                    "review_sha256": digest,
                    "relative_path": relative_path,
                    "ledger_verification": post_ledger_payload,
                }
            )
            return 2

    _print_json(
        {
            "sealed": True,
            "valid": True,
            "ledger_created": ledger_created,
            "packet": str(args.packet_dir),
            "ledger": str(args.ledger_dir),
            "packet_id": locked_packet_payload["packet_id"],
            "review_id": draft["review_id"],
            "review_stage": draft["review_stage"],
            "review_sha256": digest,
            "relative_path": relative_path,
            "already_sealed": already_sealed,
            "postcondition": (
                "already_sealed_and_verified" if already_sealed else "sealed_and_verified"
            ),
            "publication_or_training_release_allowed": False,
            "chain": post_ledger_payload,
        }
    )
    return 0


def _command_parse_penn_metadata(args: argparse.Namespace) -> int:
    if not _target_is_clear(args.output, False):
        return 1
    if (
        isinstance(args.max_csv_bytes, bool)
        or args.max_csv_bytes < 1
        or args.max_csv_bytes > PENN_MAX_CSV_BYTES
    ):
        raise ValueError(
            "max_csv_bytes must be positive and cannot exceed the "
            f"{PENN_MAX_CSV_BYTES}-byte parser ceiling"
        )
    raw_bytes = _read_regular_bytes(
        args.csv,
        max_bytes=args.max_csv_bytes,
    )
    actual_sha256 = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    if args.expected_sha256 is not None and actual_sha256 != args.expected_sha256:
        _print_json(
            {
                "valid": False,
                "written": False,
                "input": str(args.csv),
                "output": str(args.output),
                "expected_sha256": args.expected_sha256,
                "actual_sha256": actual_sha256,
                "errors": ["Penn CSV does not match the externally supplied digest"],
            }
        )
        return 2

    source_last_updated = (
        args.source_last_updated.isoformat() if args.source_last_updated is not None else None
    )
    snapshot = parse_penn_csv_snapshot(
        raw_bytes,
        source_url=PENN_CSV_URL,
        retrieved_at=args.retrieved_at,
        expected_bytes=len(raw_bytes),
        expected_sha256=actual_sha256,
        etag=args.etag,
        last_modified=args.last_modified,
        source_last_updated=source_last_updated,
    )
    schema: Path | None = args.schema
    if schema is None:
        schema = _default_penn_metadata_schema()
    if schema is None:
        raise ValueError("Penn metadata snapshot schema not found; pass --schema")
    schema_issues = validate_schema_instance(snapshot, schema)
    if schema_issues:
        _print_json(
            {
                "valid": False,
                "written": False,
                "input": str(args.csv),
                "output": str(args.output),
                "errors": [f"{issue.path}: {issue.message}" for issue in schema_issues],
            }
        )
        return 2
    durability_confirmed, output_content_verified = _write_json_no_replace(
        args.output,
        snapshot,
    )
    postcondition = (
        "committed_and_durable"
        if durability_confirmed
        else (
            "committed_durability_unknown"
            if output_content_verified
            else "committed_verification_and_durability_unknown"
        )
    )
    _print_json(
        {
            "valid": True,
            "written": True,
            "output_content_verified": output_content_verified,
            "postcondition": postcondition,
            "input": str(args.csv),
            "output": str(args.output),
            "source_url": PENN_CSV_URL,
            "source_sha256": actual_sha256,
            "source_bytes": len(raw_bytes),
            "record_count": snapshot["record_count"],
            "candidate_count": snapshot["candidate_count"],
            "primary_script_candidate_count": sum(
                candidate["classification"] == "primary_script_candidate"
                for candidate in snapshot["candidates"]
            ),
            "broad_archaeological_candidate_count": sum(
                candidate["classification"] == "broad_archaeological_candidate"
                for candidate in snapshot["candidates"]
            ),
            "replica_or_modern_count": sum(
                candidate["physical_status"] == "replica_or_modern"
                for candidate in snapshot["candidates"]
            ),
            "license_id": snapshot["source"]["license_id"],
            "images_included": snapshot["source"]["images_included"],
        }
    )
    return 0 if durability_confirmed else 1


def _command_derive_penn_context_anchors(args: argparse.Namespace) -> int:
    if not _target_is_clear(args.output, False):
        return 1
    for name, value, ceiling in (
        ("max_snapshot_bytes", args.max_snapshot_bytes, PENN_MAX_SNAPSHOT_BYTES),
        ("max_csv_bytes", args.max_csv_bytes, PENN_MAX_CSV_BYTES),
    ):
        if isinstance(value, bool) or value < 1 or value > ceiling:
            raise ValueError(
                f"{name} must be positive and cannot exceed the {ceiling}-byte parser ceiling"
            )

    snapshot_bytes = _read_regular_bytes(
        args.snapshot,
        max_bytes=args.max_snapshot_bytes,
    )
    snapshot_value = _museum_json_value(snapshot_bytes, label=str(args.snapshot))
    if not isinstance(snapshot_value, dict):
        raise ValueError("Penn metadata snapshot must be a JSON object")

    csv_bytes = _read_regular_bytes(
        args.csv,
        max_bytes=args.max_csv_bytes,
    )
    source_sha256 = "sha256:" + hashlib.sha256(csv_bytes).hexdigest()
    if args.expected_source_sha256 is not None and source_sha256 != args.expected_source_sha256:
        _print_json(
            {
                "valid": False,
                "written": False,
                "snapshot": str(args.snapshot),
                "source_csv": str(args.csv),
                "output": str(args.output),
                "expected_source_sha256": args.expected_source_sha256,
                "actual_source_sha256": source_sha256,
                "errors": ["Penn CSV does not match the externally supplied digest"],
            }
        )
        return 2

    validate_penn_metadata_semantics(snapshot_value, raw_bytes=csv_bytes)
    snapshot_schema: Path | None = args.snapshot_schema
    if snapshot_schema is None:
        snapshot_schema = _default_penn_metadata_schema()
    if snapshot_schema is None:
        raise ValueError("Penn metadata snapshot schema not found; pass --snapshot-schema")
    snapshot_issues = validate_schema_instance(snapshot_value, snapshot_schema)
    if snapshot_issues:
        _print_json(
            {
                "valid": False,
                "written": False,
                "snapshot": str(args.snapshot),
                "source_csv": str(args.csv),
                "output": str(args.output),
                "errors": [f"{issue.path}: {issue.message}" for issue in snapshot_issues],
            }
        )
        return 2

    registry = derive_context_anchor_registry(snapshot_value)
    validate_context_anchor_registry(registry, source_snapshot=snapshot_value)
    schema: Path | None = args.schema
    if schema is None:
        schema = _default_context_anchor_schema()
    if schema is None:
        raise ValueError("context-anchor registry schema not found; pass --schema")
    schema_issues = validate_schema_instance(registry, schema)
    if schema_issues:
        _print_json(
            {
                "valid": False,
                "written": False,
                "snapshot": str(args.snapshot),
                "source_csv": str(args.csv),
                "output": str(args.output),
                "errors": [f"{issue.path}: {issue.message}" for issue in schema_issues],
            }
        )
        return 2

    durability_confirmed, output_content_verified = _write_json_no_replace(
        args.output,
        registry,
    )
    postcondition = (
        "committed_and_durable"
        if durability_confirmed
        else (
            "committed_durability_unknown"
            if output_content_verified
            else "committed_verification_and_durability_unknown"
        )
    )
    _print_json(
        {
            "valid": True,
            "written": True,
            "output_content_verified": output_content_verified,
            "postcondition": postcondition,
            "snapshot": str(args.snapshot),
            "source_csv": str(args.csv),
            "output": str(args.output),
            "registry_id": registry["registry_id"],
            "source_sha256": source_sha256,
            "source_candidate_count": registry["source_candidate_count"],
            "entry_count": registry["entry_count"],
            "role_counts": registry["role_counts"],
            "license_id": registry["rights"]["license_id"],
            "images_included": registry["rights"]["images_included"],
            "transcription_approved": False,
            "meaning_approved": False,
            "originality_approved": False,
        }
    )
    return 0 if durability_confirmed else 1


def _command_synthetic_identifiability_gate(args: argparse.Namespace) -> int:
    report = run_identifiability_gate(
        seed=args.seed,
        family_count=args.family_count,
        config=DegradationConfig(seed=args.seed),
        anchors_available=not args.anchor_free,
        runs=args.runs,
        null_seed=args.null_seed,
    )
    _print_json(report)
    return 2 if args.require_go and report["gate_status"] != "go" else 0


def _command_verify_oracc_ed3b_source(args: argparse.Namespace) -> int:
    def fail(error_code: str, message: str, *, status: int = 2) -> int:
        _print_json(
            {
                "analysis": "oracc_ed3b_source_qualification",
                "terminal_status": "error",
                "scientific_metrics_emitted": False,
                "model_executed": False,
                "error_code": error_code,
                "error": message,
            }
        )
        return status

    def output_exists() -> bool | None:
        if args.output is None:
            return False
        try:
            return _path_lexists(args.output)
        except (OSError, ValueError):
            return None

    initial_output_state = output_exists()
    if initial_output_state is None:
        return fail(
            "output_uninspectable",
            "the aggregate output target could not be inspected safely",
        )
    if initial_output_state:
        return fail(
            "output_exists",
            "the aggregate output target already exists",
            status=1,
        )

    try:
        protocol_bytes = _read_regular_bytes(
            args.protocol,
            max_bytes=ORACC_ED3B_MAX_PROTOCOL_BYTES,
        )
        protocol_sha256 = verify_oracc_ed3b_protocol_bytes(protocol_bytes)
    except (OSError, ORACCEd3bError, ValueError):
        return fail(
            "protocol_rejected",
            "the exact source-freeze protocol could not be verified",
        )
    try:
        archive_bytes = _read_regular_bytes(
            args.archive,
            max_bytes=ORACC_ED3B_MAX_ARCHIVE_BYTES,
        )
    except (OSError, ValueError):
        return fail(
            "archive_unreadable",
            "the archive input could not be read safely",
        )
    try:
        report = verify_oracc_ed3b_archive(archive_bytes)
    except ORACCEd3bError as error:
        return fail("source_rejected", str(error))

    final_output_state = output_exists()
    if final_output_state is None:
        return fail(
            "output_uninspectable",
            "the aggregate output target could not be inspected safely",
        )
    if final_output_state:
        return fail(
            "output_exists",
            "the aggregate output target already exists",
            status=1,
        )

    report["analysis"] = "oracc_ed3b_source_qualification"
    report["protocol_sha256"] = protocol_sha256
    report["source_freeze_commit"] = args.source_freeze_commit
    report["scientific_metrics_emitted"] = False
    report["model_executed"] = False
    report["attestation_limit"] = (
        "the commit is caller-declared; the verifier does not independently attest "
        "Git state, publication time, custody, or blindness"
    )

    durability_confirmed = True
    if args.output is not None:
        try:
            durability_confirmed, _ = _write_json_no_replace(args.output, report)
        except (OSError, ValueError):
            return fail(
                "output_write_failed",
                "the aggregate output could not be written safely",
            )
    _print_json(report)
    return 0 if durability_confirmed else 1


def _command_evaluate_mtaac_control(args: argparse.Namespace) -> int:
    def fail(error_code: str, message: str, *, status: int = 2) -> int:
        _print_json(
            {
                "analysis": "mtaac_known_script_control",
                "terminal_status": "error",
                "scientific_metrics_emitted": False,
                "error_code": error_code,
                "error": message,
            }
        )
        return status

    def output_exists() -> bool | None:
        if args.output is None:
            return False
        try:
            return _path_lexists(args.output)
        except (OSError, ValueError):
            return None

    initial_output_state = output_exists()
    if initial_output_state is None:
        return fail(
            "output_uninspectable",
            "the aggregate output target could not be inspected safely",
        )
    if initial_output_state:
        return fail(
            "output_exists",
            "the aggregate output target already exists",
            status=1,
        )
    try:
        archive_bytes = _read_regular_bytes(
            args.archive,
            max_bytes=MTAAC_MAX_ARCHIVE_BYTES,
        )
    except (OSError, ValueError):
        return fail(
            "archive_unreadable",
            "the archive input could not be read safely",
        )
    try:
        protocol_bytes = _read_regular_bytes(
            args.protocol,
            max_bytes=MTAAC_MAX_PROTOCOL_BYTES,
        )
    except (OSError, ValueError):
        return fail(
            "protocol_unreadable",
            "the protocol input could not be read safely",
        )
    final_output_state = output_exists()
    if final_output_state is None:
        return fail(
            "output_uninspectable",
            "the aggregate output target could not be inspected safely",
        )
    if final_output_state:
        return fail(
            "output_exists",
            "the aggregate output target already exists",
            status=1,
        )
    attestation = MTAACControlAttestation(
        protocol_sha256=MTAAC_CONTROL_PROTOCOL_SHA256,
        pre_result_code_commit=args.pre_result_code_commit,
        data_origin="fixed_real_source",
        external_data_used=True,
    )
    try:
        report = evaluate_mtaac_control_archive(
            archive_bytes,
            protocol_bytes,
            attestation=attestation,
            anchors_available=not args.anchor_free,
        )
    except MTAACControlError as error:
        return fail(
            "evaluation_rejected",
            str(error),
        )

    durability_confirmed = True
    if args.output is not None:
        try:
            durability_confirmed, _ = _write_json_no_replace(args.output, report)
        except (OSError, ValueError):
            return fail(
                "output_write_failed",
                "the aggregate output could not be written safely",
            )
    _print_json(report)
    if not durability_confirmed:
        return 1
    return 2 if args.require_go and report["terminal_status"] != "go" else 0


def _command_parse_smithsonian_metadata(args: argparse.Namespace) -> int:
    if not _target_is_clear(args.output, False):
        return 1
    if (
        isinstance(args.max_jsonl_bytes, bool)
        or args.max_jsonl_bytes < 1
        or args.max_jsonl_bytes > SMITHSONIAN_MAX_JSONL_BYTES
    ):
        raise ValueError(
            "max_jsonl_bytes must be positive and cannot exceed the "
            f"{SMITHSONIAN_MAX_JSONL_BYTES}-byte parser ceiling"
        )
    raw_bytes = _read_regular_bytes(
        args.jsonl,
        max_bytes=args.max_jsonl_bytes,
    )
    actual_sha256 = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    if args.expected_sha256 is not None and actual_sha256 != args.expected_sha256:
        _print_json(
            {
                "valid": False,
                "written": False,
                "input": str(args.jsonl),
                "output": str(args.output),
                "expected_sha256": args.expected_sha256,
                "actual_sha256": actual_sha256,
                "errors": ["Smithsonian JSONL does not match the externally supplied digest"],
            }
        )
        return 2

    try:
        record = normalize_smithsonian_record(
            raw_bytes,
            source_url=args.source_url,
            retrieved_at=args.retrieved_at,
            line_number=args.line_number,
            etag=args.etag,
            last_modified=args.last_modified,
        )
    except SmithsonianMetadataError as error:
        _print_json(
            {
                "valid": False,
                "written": False,
                "input": str(args.jsonl),
                "output": str(args.output),
                "source_url": args.source_url,
                "line_number": args.line_number,
                "source_sha256": actual_sha256,
                "errors": [str(error)],
            }
        )
        return 2

    schema: Path | None = args.schema
    if schema is None:
        schema = _default_smithsonian_metadata_schema()
    if schema is None:
        raise ValueError("Smithsonian metadata record schema not found; pass --schema")
    schema_issues = validate_schema_instance(record, schema)
    if schema_issues:
        _print_json(
            {
                "valid": False,
                "written": False,
                "input": str(args.jsonl),
                "output": str(args.output),
                "errors": [f"{issue.path}: {issue.message}" for issue in schema_issues],
            }
        )
        return 2

    durability_confirmed, output_content_verified = _write_json_no_replace(
        args.output,
        record,
    )
    postcondition = (
        "committed_and_durable"
        if durability_confirmed
        else (
            "committed_durability_unknown"
            if output_content_verified
            else "committed_verification_and_durability_unknown"
        )
    )
    _print_json(
        {
            "valid": True,
            "written": True,
            "output_content_verified": output_content_verified,
            "postcondition": postcondition,
            "input": str(args.jsonl),
            "output": str(args.output),
            "source_url": args.source_url,
            "source_sha256": actual_sha256,
            "source_bytes": len(raw_bytes),
            "external_digest_checked": args.expected_sha256 is not None,
            "line_number": record["source_acquisition"]["locator"]["line_number"],
            "line_sha256": record["source_acquisition"]["locator"]["line_sha256"],
            "intake_id": record["intake_id"],
            "record_ID": record["upstream_commitments"]["record_ID"],
            "record_state": record["record_state"],
            "candidate_classification": record["candidate_classification"],
            "media_count": record["media"]["count"],
            "approved_media_count": record["media"]["approved_count"],
            "publication_or_training_release_allowed": False,
        }
    )
    return 0 if durability_confirmed else 1


def _command_validate(args: argparse.Namespace) -> int:
    records = read_jsonl(args.corpus)
    quarantine = _inspect_quarantine(records, args, purpose="schema_validation")
    issues = validate_corpus(records)
    schema_path: Path | None = args.schema
    if args.full_schema and schema_path is None:
        schema_path = _default_artifact_schema()
        if schema_path is None:
            print("artifact schema not found; pass --schema explicitly", file=sys.stderr)
            return 1
    if schema_path is not None:
        issues.extend(validate_artifact_rows(records, schema_path))

    payload = {
        "corpus": str(args.corpus),
        "artifacts": len(records),
        "errors": sum(issue.severity == "error" for issue in issues),
        "warnings": sum(issue.severity == "warning" for issue in issues),
        "issues": [issue.as_dict() for issue in issues],
        "quarantine": quarantine.as_dict(),
        "valid": not has_errors(issues) and quarantine.allowed,
    }
    _print_json(payload)
    return 2 if has_errors(issues) or not quarantine.allowed else 0


def _require_schema_valid(
    value: Any,
    schema: Path,
    *,
    label: str,
) -> None:
    issues = validate_schema_instance(value, schema)
    if issues:
        first = issues[0]
        raise TranscriptionReviewError(f"{label} schema invalid at {first.path}")


def _command_verify_kp1982_source(args: argparse.Namespace) -> int:
    try:
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1982_MAX_CONTRACT_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1982_MAX_SOURCE_BYTES,
        )
        page_pbm_bytes = (
            [
                _read_regular_bytes(
                    path,
                    max_bytes=KP1982_MAX_PAGE_PBM_BYTES,
                )
                for path in args.page_pbm
            ]
            if args.page_pbm is not None
            else None
        )
        summary = verify_kp1982_source(
            contract_bytes,
            source_bytes,
            page_pbm_bytes=page_pbm_bytes,
        )
    except (OSError, ValueError) as error:
        raise KP1982SourceError("KP1982 fixed source verification failed") from error
    _print_json(summary)
    return 0


def _command_verify_kp1979_source(args: argparse.Namespace) -> int:
    try:
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )
        summary = verify_kp1979_source(
            contract_bytes,
            page_map_bytes,
            source_bytes,
        )
    except (OSError, ValueError) as error:
        raise KP1979SourceError("KP1979 fixed source verification failed") from error
    _print_json(summary)
    return 0


def _command_audit_kp1979_layout(args: argparse.Namespace) -> int:
    try:
        directory_metadata = args.page_pbm_dir.lstat()
        if stat.S_ISLNK(directory_metadata.st_mode) or not stat.S_ISDIR(directory_metadata.st_mode):
            raise KP1979SourceError("page bitmap input must be a physical directory")
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )

        def page_bytes():
            for page_number in range(2, 181):
                yield (
                    page_number,
                    _read_regular_bytes(
                        args.page_pbm_dir / f"page-{page_number:03d}.pbm",
                        max_bytes=KP1979_MAX_PAGE_PBM_BYTES,
                    ),
                )

        summary = audit_kp1979_layout(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            page_bytes(),
        )
    except (OSError, ValueError) as error:
        raise KP1979SourceError("KP1979 source-bound layout audit failed") from error
    _print_json(summary)
    return 0


def _require_kp1979_page_directory(path: Path) -> None:
    """Require a physical directory before any fixed-page iterator is created."""

    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("KP1979 page bitmap input is not a physical directory")


def _iter_kp1979_page_bytes(
    directory: Path,
    *,
    first_page: int,
    last_page: int,
) -> Iterator[tuple[int, bytes]]:
    """Read one closed inclusive range of canonical KP1979 page bitmaps."""

    for page_number in range(first_page, last_page + 1):
        yield (
            page_number,
            _read_regular_bytes(
                directory / f"page-{page_number:03d}.pbm",
                max_bytes=KP1979_MAX_PAGE_PBM_BYTES,
            ),
        )


def _kp1979_row_assignment_summary(
    *,
    valid: bool,
    private_storage_verified: bool,
    assignment_canonical_bytes_verified: bool,
    written: bool | None = None,
    **state: bool | str,
) -> dict[str, bool | str]:
    """Return a fixed, count-free summary for a private row assignment."""

    summary: dict[str, bool | str] = {
        "valid": valid,
        "claim_class": "private_kp1979_row_assignment_only",
        "counts_disclosed": False,
        "private_values_disclosed": False,
        "private_storage_verified": private_storage_verified,
        "source_page_pixels_verified": True,
        "audit_page_layout_gates_passed": True,
        "base_page_pixels_verified": True,
        "assignment_canonical_bytes_verified": assignment_canonical_bytes_verified,
        "proposal_geometry_only": assignment_canonical_bytes_verified,
        "machine_answer_values_withheld": assignment_canonical_bytes_verified,
        "label_geometry_accepted": False,
        "row_geometry_accepted": False,
        "human_review_complete": False,
        "reviewer_independence_verified": False,
        "identifiers_transcribed": False,
        "codes_transcribed": False,
        "sign_sequences_transcribed": False,
        "reading_direction_assigned": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
    }
    if written is not None:
        summary["written"] = written
    if set(state).intersection(summary):
        raise KP1979RowAssignmentError(
            "KP1979 row assignment summary state cannot replace a fixed assurance"
        )
    summary.update(state)
    return summary


def _command_prepare_kp1979_row_assignment(args: argparse.Namespace) -> int:
    try:
        _require_kp1979_page_directory(args.page_pbm_dir)
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )
        assignment = build_row_assignment(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            _iter_kp1979_page_bytes(
                args.page_pbm_dir,
                first_page=2,
                last_page=180,
            ),
            _iter_kp1979_page_bytes(
                args.page_pbm_dir,
                first_page=22,
                last_page=78,
            ),
        )
    except (OSError, ValueError) as error:
        raise KP1979RowAssignmentError("KP1979 row assignment preparation failed") from error

    try:
        durability_confirmed, content_verified = _write_private_json_no_replace(
            args.output,
            assignment,
        )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1979RowAssignmentError(
            "private KP1979 row assignment could not be created safely"
        ) from error
    if not durability_confirmed or not content_verified:
        _print_json(
            _kp1979_row_assignment_summary(
                valid=False,
                written=False,
                private_storage_verified=False,
                assignment_canonical_bytes_verified=content_verified,
                output_content_verified=content_verified,
                durability_confirmed=durability_confirmed,
                destination_may_exist=True,
                postcondition=(
                    "committed_content_verified_durability_unknown"
                    if content_verified
                    else "committed_content_unknown"
                ),
            )
        )
        return 1
    _print_json(
        _kp1979_row_assignment_summary(
            valid=True,
            written=True,
            private_storage_verified=True,
            assignment_canonical_bytes_verified=True,
        )
    )
    return 0


def _command_verify_kp1979_row_assignment(args: argparse.Namespace) -> int:
    try:
        _require_kp1979_page_directory(args.page_pbm_dir)
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )
        assignment_bytes = _read_private_regular_bytes(
            args.assignment,
            max_bytes=KP1979_MAX_ROW_ASSIGNMENT_BYTES,
        )
        core_summary = verify_row_assignment_bytes(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            _iter_kp1979_page_bytes(
                args.page_pbm_dir,
                first_page=2,
                last_page=180,
            ),
            _iter_kp1979_page_bytes(
                args.page_pbm_dir,
                first_page=22,
                last_page=78,
            ),
            assignment_bytes,
        )
        if (
            core_summary.get("valid") is not True
            or core_summary.get("assignment_canonical_bytes_verified") is not True
            or core_summary.get("proposal_geometry_only") is not True
            or core_summary.get("machine_answer_values_withheld") is not True
            or core_summary.get("decipherment") is not False
        ):
            raise KP1979RowAssignmentError(
                "KP1979 row assignment verifier returned an incomplete assurance state"
            )
    except (OSError, ValueError) as error:
        raise KP1979RowAssignmentError("KP1979 row assignment verification failed") from error
    _print_json(
        _kp1979_row_assignment_summary(
            valid=True,
            private_storage_verified=True,
            assignment_canonical_bytes_verified=True,
        )
    )
    return 0


_KP1979_SIGN_TEMPLATE_CELL_ID = re.compile(r"\AKP1979:P(?:20|21):L[0-9]{2}:R[0-9]{2}\Z")
_KP1979_MAX_SIGN_TEMPLATE_TOTAL_GLYPH_BYTES = 256 * 1024 * 1024


@contextmanager
def _kp1979_sign_template_glyph_loader(
    directory: Path,
) -> Iterator[Callable[[str], bytes]]:
    """Yield one bounded loader over a pinned owner-only glyph directory."""

    absolute = Path(os.path.abspath(directory))
    pinned = _open_pinned_directory(absolute, private_target=True)
    requested: set[str] = set()
    total_bytes = 0

    def load(cell_id: str) -> bytes:
        nonlocal total_bytes
        if not isinstance(cell_id, str) or _KP1979_SIGN_TEMPLATE_CELL_ID.fullmatch(cell_id) is None:
            raise ValueError("KP1979 sign-template glyph ID is invalid")
        if cell_id in requested:
            raise ValueError("KP1979 sign-template glyph was requested more than once")
        if len(requested) >= KP1979_MAX_SIGN_TEMPLATE_INPUT_ITEMS:
            raise ValueError("KP1979 sign-template glyph request limit was exceeded")
        requested.add(cell_id)
        glyph_bytes = _read_private_regular_bytes_at(
            pinned.descriptor,
            f"{cell_id}.pbm",
            max_bytes=KP1979_MAX_SIGN_TEMPLATE_PBM_BYTES,
        )
        total_bytes += len(glyph_bytes)
        if total_bytes > _KP1979_MAX_SIGN_TEMPLATE_TOTAL_GLYPH_BYTES:
            raise ValueError("KP1979 sign-template glyph aggregate limit was exceeded")
        return glyph_bytes

    try:
        yield load
        _verify_pinned_directory(pinned)
    finally:
        _close_pinned_directory(pinned)


def _kp1979_sign_template_roster_summary(
    *,
    valid: bool,
    private_storage_verified: bool,
    roster_canonical_bytes_verified: bool,
    written: bool | None = None,
    **state: bool | str,
) -> dict[str, bool | str]:
    """Return a fixed count-, value-, identity-, digest-, and path-free summary."""

    summary: dict[str, bool | str] = {
        "valid": valid,
        "claim_class": "private_kp1979_sign_template_roster_only",
        "counts_disclosed": False,
        "private_values_disclosed": False,
        "record_ids_disclosed": False,
        "digests_disclosed": False,
        "paths_disclosed": False,
        "private_storage_verified": private_storage_verified,
        "catalog_geometry_raw_bytes_bound": roster_canonical_bytes_verified,
        "catalog_geometry_item_join_verified": roster_canonical_bytes_verified,
        "glyph_crop_commitments_verified": roster_canonical_bytes_verified,
        "roster_canonical_bytes_verified": roster_canonical_bytes_verified,
        "machine_provisional_graphic_identity_only": roster_canonical_bytes_verified,
        "catalog_values_accepted": False,
        "sign_identity_accepted": False,
        "human_review_complete": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
    }
    if written is not None:
        summary["written"] = written
    if set(state).intersection(summary):
        raise KP1979SignTemplateRosterError(
            "KP1979 sign-template roster summary state cannot replace a fixed assurance"
        )
    summary.update(state)
    return summary


def _require_kp1979_sign_template_roster_summary(
    summary: dict[str, bool | str],
) -> None:
    required_true = (
        "valid",
        "catalog_geometry_raw_bytes_bound",
        "catalog_geometry_item_join_verified",
        "glyph_crop_commitments_verified",
        "roster_canonical_bytes_verified",
    )
    required_false = (
        "catalog_values_accepted",
        "sign_identity_accepted",
        "human_review_complete",
        "public_release_authorized",
        "evaluation_admissible",
        "decipherment",
        "prize_submission_eligible",
    )
    if any(summary.get(field) is not True for field in required_true) or any(
        summary.get(field) is not False for field in required_false
    ):
        raise KP1979SignTemplateRosterError(
            "KP1979 sign-template roster verifier returned an incomplete assurance state"
        )


def _command_prepare_kp1979_sign_template_roster(args: argparse.Namespace) -> int:
    try:
        catalog_bytes = _read_private_regular_bytes(
            args.catalog,
            max_bytes=KP1979_MAX_SIGN_TEMPLATE_CATALOG_BYTES,
        )
        geometry_manifest_bytes = _read_private_regular_bytes(
            args.geometry_manifest,
            max_bytes=KP1979_MAX_SIGN_TEMPLATE_GEOMETRY_BYTES,
        )
        with _kp1979_sign_template_glyph_loader(args.glyph_pbm_dir) as glyph_loader:
            roster = build_sign_template_roster(
                catalog_bytes,
                geometry_manifest_bytes,
                glyph_loader,
            )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1979SignTemplateRosterError(
            "KP1979 sign-template roster preparation failed"
        ) from error

    try:
        durability_confirmed, content_verified = _write_private_json_no_replace(
            args.output,
            roster,
        )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1979SignTemplateRosterError(
            "private KP1979 sign-template roster could not be created safely"
        ) from error
    if not durability_confirmed or not content_verified:
        _print_json(
            _kp1979_sign_template_roster_summary(
                valid=False,
                written=False,
                private_storage_verified=False,
                roster_canonical_bytes_verified=content_verified,
                output_content_verified=content_verified,
                durability_confirmed=durability_confirmed,
                destination_may_exist=True,
                postcondition=(
                    "committed_content_verified_durability_unknown"
                    if content_verified
                    else "committed_content_unknown"
                ),
            )
        )
        return 1
    _print_json(
        _kp1979_sign_template_roster_summary(
            valid=True,
            written=True,
            private_storage_verified=True,
            roster_canonical_bytes_verified=True,
        )
    )
    return 0


def _command_verify_kp1979_sign_template_roster(args: argparse.Namespace) -> int:
    try:
        catalog_bytes = _read_private_regular_bytes(
            args.catalog,
            max_bytes=KP1979_MAX_SIGN_TEMPLATE_CATALOG_BYTES,
        )
        geometry_manifest_bytes = _read_private_regular_bytes(
            args.geometry_manifest,
            max_bytes=KP1979_MAX_SIGN_TEMPLATE_GEOMETRY_BYTES,
        )
        roster_bytes = _read_private_regular_bytes(
            args.roster,
            max_bytes=KP1979_MAX_SIGN_TEMPLATE_ROSTER_BYTES,
        )
        with _kp1979_sign_template_glyph_loader(args.glyph_pbm_dir) as glyph_loader:
            core_summary = verify_sign_template_roster_bytes(
                catalog_bytes,
                geometry_manifest_bytes,
                glyph_loader,
                roster_bytes,
            )
        _require_kp1979_sign_template_roster_summary(core_summary)
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1979SignTemplateRosterError(
            "KP1979 sign-template roster verification failed"
        ) from error
    _print_json(
        _kp1979_sign_template_roster_summary(
            valid=True,
            private_storage_verified=True,
            roster_canonical_bytes_verified=True,
        )
    )
    return 0


def _read_regular_bytes_at(
    parent_descriptor: int,
    name: str,
    *,
    max_bytes: int,
) -> bytes:
    """Read one stable single-link regular file relative to a pinned directory."""

    if not name or name in {".", ".."} or "/" in name or "\x00" in name:
        raise ValueError("pinned input filename is invalid")
    descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > max_bytes:
            raise ValueError("pinned input is not a bounded single-link regular file")
        chunks: list[bytes] = []
        byte_count = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - byte_count))
            if not chunk:
                break
            byte_count += len(chunk)
            if byte_count > max_bytes:
                raise ValueError("pinned input exceeds its byte limit")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        namespace = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        fingerprint_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        before_fingerprint = tuple(getattr(before, field) for field in fingerprint_fields)
        if (
            tuple(getattr(after, field) for field in fingerprint_fields) != before_fingerprint
            or tuple(getattr(namespace, field) for field in fingerprint_fields)
            != before_fingerprint
        ):
            raise ValueError("pinned input changed during its bounded read")
        return b"".join(chunks)
    except OSError as error:
        raise ValueError("pinned input could not be read safely") from error
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


def _read_kp1979_label_reference_page_bytes(
    directory: Path,
    *,
    partition: str,
) -> tuple[tuple[int, bytes], ...]:
    """Read one exact six-page roster through a single pinned physical directory."""

    page_numbers = KP1979_LABEL_REFERENCE_PARTITION_PAGES.get(partition)
    if page_numbers is None:
        raise KP1979LabelReferenceError("KP1979 label-reference partition is invalid")
    absolute = Path(os.path.abspath(directory))
    pinned = _open_pinned_directory(absolute, private_target=False)
    try:
        pages = tuple(
            (
                page_number,
                _read_regular_bytes_at(
                    pinned.descriptor,
                    f"page-{page_number:03d}.pbm",
                    max_bytes=KP1979_MAX_PAGE_PBM_BYTES,
                ),
            )
            for page_number in page_numbers
        )
        _verify_pinned_directory(pinned)
        return pages
    finally:
        _close_pinned_directory(pinned)


def _kp1979_label_reference_summary(
    *,
    valid: bool,
    claim_class: str,
    private_storage_verified: bool,
    assignment_canonical_bytes_verified: bool,
    review_canonical_bytes_verified: bool = False,
    review_record_verified: bool = False,
    submitted_crop_bytes_recomputed: bool = False,
    authorship_declaration_recorded: bool = False,
    access_declaration_recorded: bool = False,
    written: bool | None = None,
    **state: bool | str,
) -> dict[str, bool | str]:
    """Return a fixed count-, value-, identity-, digest-, and path-free summary."""

    summary: dict[str, bool | str] = {
        "valid": valid,
        "claim_class": claim_class,
        "counts_disclosed": False,
        "private_values_disclosed": False,
        "record_ids_disclosed": False,
        "digests_disclosed": False,
        "paths_disclosed": False,
        "private_storage_verified": private_storage_verified,
        "source_snapshot_match": True,
        "page_map_snapshot_match": True,
        "selected_page_pixels_verified": True,
        "partition_isolated": True,
        "assignment_canonical_bytes_verified": assignment_canonical_bytes_verified,
        "answer_values_withheld": assignment_canonical_bytes_verified,
        "detector_output_absent": assignment_canonical_bytes_verified,
        "proposal_geometry_absent": assignment_canonical_bytes_verified,
        "review_canonical_bytes_verified": review_canonical_bytes_verified,
        "review_record_verified": review_record_verified,
        "submitted_crop_bytes_recomputed": submitted_crop_bytes_recomputed,
        "authorship_declaration_recorded": authorship_declaration_recorded,
        "access_declaration_recorded": access_declaration_recorded,
        "authorship_declaration_verified": False,
        "access_declaration_verified": False,
        "label_reference_values_accepted": False,
        "actor_identity_verified": False,
        "human_review_started_verified": False,
        "human_review_complete_verified": False,
        "human_authorship_verified": False,
        "real_world_independence_verified": False,
        "reviewer_blinding_verified": False,
        "reviewer_nonexposure_verified": False,
        "label_geometry_accepted": False,
        "row_geometry_accepted": False,
        "identifiers_transcribed": False,
        "codes_transcribed": False,
        "sign_sequences_transcribed": False,
        "reading_direction_assigned": False,
        "source_custody_verified": False,
        "source_rights_verified": False,
        "reference_custody_verified": False,
        "detector_freeze_verified": False,
        "scorer_freeze_verified": False,
        "runtime_isolation_verified": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
    }
    if written is not None:
        summary["written"] = written
    if set(state).intersection(summary):
        raise KP1979LabelReferenceError(
            "KP1979 label-reference summary state cannot replace a fixed assurance"
        )
    summary.update(state)
    return summary


def _require_kp1979_label_reference_assignment_summary(
    summary: dict[str, bool | str],
) -> None:
    required_true = (
        "valid",
        "source_snapshot_match",
        "page_map_snapshot_match",
        "selected_page_pixels_verified",
        "assignment_canonical_bytes_verified",
        "answer_values_withheld",
        "detector_output_absent",
        "proposal_geometry_absent",
    )
    required_false = (
        "human_review_started_verified",
        "human_review_complete_verified",
        "human_authorship_verified",
        "real_world_independence_verified",
        "reviewer_blinding_verified",
        "label_geometry_accepted",
        "row_geometry_accepted",
        "public_release_authorized",
        "evaluation_admissible",
        "decipherment",
        "prize_submission_eligible",
        "reference_custody_verified",
        "detector_freeze_verified",
        "scorer_freeze_verified",
        "runtime_isolation_verified",
    )
    if any(summary.get(field) is not True for field in required_true) or any(
        summary.get(field) is not False for field in required_false
    ):
        raise KP1979LabelReferenceError(
            "KP1979 label-reference assignment verifier returned an incomplete assurance state"
        )


def _require_kp1979_label_reference_review_summary(
    summary: dict[str, bool | str],
) -> None:
    required_true = (
        "valid",
        "assignment_canonical_bytes_verified",
        "assignment_commitment_verified",
        "selected_page_pixels_verified",
        "review_canonical_bytes_verified",
        "review_roster_verified",
        "submitted_crop_bytes_recomputed",
        "opaque_record_ids_structurally_distinct",
        "authorship_declaration_recorded",
        "access_declaration_recorded",
    )
    required_false = (
        "actor_identity_verified",
        "authorship_declaration_verified",
        "access_declaration_verified",
        "human_review_started_verified",
        "human_review_complete_verified",
        "human_authorship_verified",
        "real_world_independence_verified",
        "reviewer_blinding_verified",
        "reviewer_nonexposure_verified",
        "label_geometry_accepted",
        "row_geometry_accepted",
        "identifiers_transcribed",
        "codes_transcribed",
        "sign_sequences_transcribed",
        "reading_direction_assigned",
        "source_custody_verified",
        "source_rights_verified",
        "public_release_authorized",
        "evaluation_admissible",
        "decipherment",
        "prize_submission_eligible",
        "reference_custody_verified",
        "detector_freeze_verified",
        "scorer_freeze_verified",
        "runtime_isolation_verified",
    )
    if any(summary.get(field) is not True for field in required_true) or any(
        summary.get(field) is not False for field in required_false
    ):
        raise KP1979LabelReferenceError(
            "KP1979 label-reference review verifier returned an incomplete assurance state"
        )


def _require_kp1979_machine_development_review_summary(
    summary: dict[str, bool | str],
) -> None:
    _require_kp1979_label_reference_review_summary(summary)
    required_true = (
        "machine_development_pass_verified",
        "machine_authorship_declared",
        "deterministic_source_pixel_recomputation_verified",
        "machine_development_exposed",
        "detector_output_exposure_declared",
        "ocr_output_exposure_declared",
        "page_role_expectations_exposure_declared",
        "scoring_expectations_exposure_declared",
    )
    required_false = (
        "eligible_as_human_reference",
        "eligible_for_detector_scoring",
        "procedural_independence_verified",
    )
    if any(summary.get(field) is not True for field in required_true) or any(
        summary.get(field) is not False for field in required_false
    ):
        raise KP1979LabelReferenceError(
            "KP1979 machine-development verifier returned an incomplete use boundary"
        )


def _command_prepare_kp1979_label_reference_assignment(
    args: argparse.Namespace,
) -> int:
    try:
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )
        page_pbm_bytes = _read_kp1979_label_reference_page_bytes(
            args.page_pbm_dir,
            partition=args.partition,
        )
        assignment = build_label_reference_assignment(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            page_pbm_bytes,
            partition=args.partition,
        )
    except (OSError, ValueError) as error:
        raise KP1979LabelReferenceError(
            "KP1979 label-reference assignment preparation failed"
        ) from error

    try:
        durability_confirmed, content_verified = _write_private_json_no_replace(
            args.output,
            assignment,
        )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1979LabelReferenceError(
            "private KP1979 label-reference assignment could not be created safely"
        ) from error
    if not durability_confirmed or not content_verified:
        _print_json(
            _kp1979_label_reference_summary(
                valid=False,
                claim_class="private_kp1979_label_reference_assignment_preparation",
                private_storage_verified=False,
                assignment_canonical_bytes_verified=content_verified,
                written=False,
                output_content_verified=content_verified,
                durability_confirmed=durability_confirmed,
                destination_may_exist=True,
                postcondition=(
                    "committed_content_verified_durability_unknown"
                    if content_verified
                    else "committed_content_unknown"
                ),
            )
        )
        return 1
    _print_json(
        _kp1979_label_reference_summary(
            valid=True,
            claim_class="private_kp1979_label_reference_assignment_preparation",
            private_storage_verified=True,
            assignment_canonical_bytes_verified=True,
            written=True,
        )
    )
    return 0


def _command_verify_kp1979_label_reference_assignment(
    args: argparse.Namespace,
) -> int:
    try:
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )
        assignment_bytes = _read_private_regular_bytes(
            args.assignment,
            max_bytes=KP1979_MAX_LABEL_REFERENCE_ASSIGNMENT_BYTES,
        )
        page_pbm_bytes = _read_kp1979_label_reference_page_bytes(
            args.page_pbm_dir,
            partition=args.partition,
        )
        core_summary = verify_label_reference_assignment_bytes(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            page_pbm_bytes,
            assignment_bytes,
        )
        _require_kp1979_label_reference_assignment_summary(core_summary)
    except (OSError, ValueError) as error:
        raise KP1979LabelReferenceError(
            "KP1979 label-reference assignment verification failed"
        ) from error
    _print_json(
        _kp1979_label_reference_summary(
            valid=True,
            claim_class="private_kp1979_label_reference_assignment_verification",
            private_storage_verified=True,
            assignment_canonical_bytes_verified=True,
        )
    )
    return 0


def _command_verify_kp1979_label_reference_review(
    args: argparse.Namespace,
) -> int:
    try:
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )
        assignment_bytes = _read_private_regular_bytes(
            args.assignment,
            max_bytes=KP1979_MAX_LABEL_REFERENCE_ASSIGNMENT_BYTES,
        )
        review_bytes = _read_private_regular_bytes(
            args.review,
            max_bytes=KP1979_MAX_LABEL_REFERENCE_REVIEW_BYTES,
        )
        page_pbm_bytes = _read_kp1979_label_reference_page_bytes(
            args.page_pbm_dir,
            partition=args.partition,
        )
        assignment_summary = verify_label_reference_assignment_bytes(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            page_pbm_bytes,
            assignment_bytes,
        )
        _require_kp1979_label_reference_assignment_summary(assignment_summary)
        review_summary = verify_independent_label_reference_review_bytes(
            assignment_bytes,
            page_pbm_bytes,
            review_bytes,
        )
        _require_kp1979_label_reference_review_summary(review_summary)
    except (OSError, ValueError) as error:
        raise KP1979LabelReferenceError(
            "KP1979 label-reference review verification failed"
        ) from error
    _print_json(
        _kp1979_label_reference_summary(
            valid=True,
            claim_class="private_kp1979_label_reference_review_verification",
            private_storage_verified=True,
            assignment_canonical_bytes_verified=True,
            review_canonical_bytes_verified=True,
            review_record_verified=True,
            submitted_crop_bytes_recomputed=True,
            authorship_declaration_recorded=True,
            access_declaration_recorded=True,
            review_actor_assignment_ids_structurally_pairwise_distinct=True,
        )
    )
    return 0


def _command_prepare_kp1979_machine_development_review(
    args: argparse.Namespace,
) -> int:
    try:
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )
        assignment_bytes = _read_private_regular_bytes(
            args.assignment,
            max_bytes=KP1979_MAX_LABEL_REFERENCE_ASSIGNMENT_BYTES,
        )
        page_pbm_bytes = _read_kp1979_label_reference_page_bytes(
            args.page_pbm_dir,
            partition="development",
        )
        assignment_summary = verify_label_reference_assignment_bytes(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            page_pbm_bytes,
            assignment_bytes,
        )
        _require_kp1979_label_reference_assignment_summary(assignment_summary)
        review = build_machine_development_label_reference_review(
            assignment_bytes,
            page_pbm_bytes,
        )
        review_summary = verify_machine_development_label_reference_review_bytes(
            assignment_bytes,
            page_pbm_bytes,
            encode_json(review),
        )
        _require_kp1979_machine_development_review_summary(review_summary)
    except (OSError, ValueError) as error:
        raise KP1979LabelReferenceError(
            "KP1979 machine-development review preparation failed"
        ) from error

    try:
        durability_confirmed, content_verified = _write_private_json_no_replace(
            args.output,
            review,
        )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1979LabelReferenceError(
            "private KP1979 machine-development review could not be created safely"
        ) from error
    if not durability_confirmed or not content_verified:
        _print_json(
            _kp1979_label_reference_summary(
                valid=False,
                claim_class="private_kp1979_machine_development_review_preparation",
                private_storage_verified=False,
                assignment_canonical_bytes_verified=True,
                review_canonical_bytes_verified=content_verified,
                review_record_verified=content_verified,
                submitted_crop_bytes_recomputed=True,
                authorship_declaration_recorded=True,
                access_declaration_recorded=True,
                machine_development_pass_verified=True,
                machine_authorship_declared=True,
                deterministic_source_pixel_recomputation_verified=True,
                machine_development_exposed=True,
                detector_output_exposure_declared=True,
                ocr_output_exposure_declared=True,
                page_role_expectations_exposure_declared=True,
                scoring_expectations_exposure_declared=True,
                eligible_as_human_reference=False,
                eligible_for_detector_scoring=False,
                procedural_independence_verified=False,
                written=False,
                output_content_verified=content_verified,
                durability_confirmed=durability_confirmed,
                destination_may_exist=True,
                postcondition=(
                    "committed_content_verified_durability_unknown"
                    if content_verified
                    else "committed_content_unknown"
                ),
            )
        )
        return 1
    _print_json(
        _kp1979_label_reference_summary(
            valid=True,
            claim_class="private_kp1979_machine_development_review_preparation",
            private_storage_verified=True,
            assignment_canonical_bytes_verified=True,
            review_canonical_bytes_verified=True,
            review_record_verified=True,
            submitted_crop_bytes_recomputed=True,
            authorship_declaration_recorded=True,
            access_declaration_recorded=True,
            machine_development_pass_verified=True,
            machine_authorship_declared=True,
            deterministic_source_pixel_recomputation_verified=True,
            machine_development_exposed=True,
            detector_output_exposure_declared=True,
            ocr_output_exposure_declared=True,
            page_role_expectations_exposure_declared=True,
            scoring_expectations_exposure_declared=True,
            eligible_as_human_reference=False,
            eligible_for_detector_scoring=False,
            procedural_independence_verified=False,
            written=True,
        )
    )
    return 0


def _command_verify_kp1979_machine_development_review(
    args: argparse.Namespace,
) -> int:
    try:
        contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1979_MAX_CONTRACT_BYTES,
        )
        page_map_bytes = _read_regular_bytes(
            args.page_map,
            max_bytes=KP1979_MAX_PAGE_MAP_BYTES,
        )
        source_bytes = _read_regular_bytes(
            args.pdf,
            max_bytes=KP1979_MAX_SOURCE_BYTES,
        )
        assignment_bytes = _read_private_regular_bytes(
            args.assignment,
            max_bytes=KP1979_MAX_LABEL_REFERENCE_ASSIGNMENT_BYTES,
        )
        review_bytes = _read_private_regular_bytes(
            args.review,
            max_bytes=KP1979_MAX_LABEL_REFERENCE_REVIEW_BYTES,
        )
        page_pbm_bytes = _read_kp1979_label_reference_page_bytes(
            args.page_pbm_dir,
            partition="development",
        )
        assignment_summary = verify_label_reference_assignment_bytes(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            page_pbm_bytes,
            assignment_bytes,
        )
        _require_kp1979_label_reference_assignment_summary(assignment_summary)
        review_summary = verify_machine_development_label_reference_review_bytes(
            assignment_bytes,
            page_pbm_bytes,
            review_bytes,
        )
        _require_kp1979_machine_development_review_summary(review_summary)
    except (OSError, ValueError) as error:
        raise KP1979LabelReferenceError(
            "KP1979 machine-development review verification failed"
        ) from error
    _print_json(
        _kp1979_label_reference_summary(
            valid=True,
            claim_class="private_kp1979_machine_development_review_verification",
            private_storage_verified=True,
            assignment_canonical_bytes_verified=True,
            review_canonical_bytes_verified=True,
            review_record_verified=True,
            submitted_crop_bytes_recomputed=True,
            authorship_declaration_recorded=True,
            access_declaration_recorded=True,
            machine_development_pass_verified=True,
            machine_authorship_declared=True,
            deterministic_source_pixel_recomputation_verified=True,
            machine_development_exposed=True,
            detector_output_exposure_declared=True,
            ocr_output_exposure_declared=True,
            page_role_expectations_exposure_declared=True,
            scoring_expectations_exposure_declared=True,
            eligible_as_human_reference=False,
            eligible_for_detector_scoring=False,
            procedural_independence_verified=False,
        )
    )
    return 0


def _command_run_kp1979_label_lattice_synthetic_control(
    _args: argparse.Namespace,
) -> int:
    report = run_synthetic_control()
    if not isinstance(report, SyntheticControlReport):
        raise ValueError("KP1979 synthetic control returned an unsafe claim state")
    required_false = (
        report.real_accuracy,
        report.reference_accepted,
        report.future_evaluation_opened,
        report.reserved_sources_read,
        report.decipherment,
        report.prize_submission_eligible,
    )
    if (
        report.target_algorithm_id != KP1979_SYNTHETIC_TARGET_ALGORITHM_ID
        or report.status not in {"qualified", "not_qualified"}
        or report.reference_use != "synthetic_control"
        or report.synthetic_only is not True
        or any(value is not False for value in required_false)
    ):
        raise ValueError("KP1979 synthetic control returned an unsafe claim state")
    _print_json(_jsonable(report))
    return 0


def _command_propose_kp1982_layout(args: argparse.Namespace) -> int:
    try:
        source_contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1982_MAX_CONTRACT_BYTES,
        )
        layout_seed_bytes = _read_regular_bytes(
            args.layout_seed,
            max_bytes=KP1982_MAX_LAYOUT_SEED_BYTES,
        )
        page_pbm_bytes = [
            _read_regular_bytes(
                path,
                max_bytes=KP1982_MAX_PAGE_PBM_BYTES,
            )
            for path in (args.page20_pbm, args.page21_pbm)
        ]
        proposal = build_layout_proposal(
            source_contract_bytes,
            layout_seed_bytes,
            page_pbm_bytes,
        )
    except (OSError, ValueError) as error:
        raise KP1982LayoutError("KP1982 layout proposal generation failed") from error

    try:
        durability_confirmed, content_verified = _write_private_json_no_replace(
            args.output,
            proposal,
        )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1982LayoutError(
            "private KP1982 layout proposal could not be created safely"
        ) from error
    if not durability_confirmed or not content_verified:
        _print_json(
            {
                "valid": False,
                "written": False,
                "claim_class": "private_layout_proposal_only",
                "output_content_verified": content_verified,
                "durability_confirmed": durability_confirmed,
                "postcondition": "committed_durability_unknown",
                "counts_disclosed": False,
                "private_storage_verified": False,
                "canonical_manifest_bytes_verified": True,
                "context_component_coverage_recomputed": False,
                "layout_accepted": False,
                "human_double_review_complete": False,
                "identifiers_transcribed": False,
                "decipherment": False,
            }
        )
        return 1
    _print_json(
        {
            "valid": True,
            "written": True,
            "claim_class": "private_layout_proposal_only",
            "counts_disclosed": False,
            "private_storage_verified": True,
            "canonical_manifest_bytes_verified": True,
            "context_component_coverage_recomputed": False,
            "layout_accepted": False,
            "human_double_review_complete": False,
            "identifiers_transcribed": False,
            "decipherment": False,
        }
    )
    return 0


def _command_verify_kp1982_layout(args: argparse.Namespace) -> int:
    try:
        source_contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1982_MAX_CONTRACT_BYTES,
        )
        layout_seed_bytes = _read_regular_bytes(
            args.layout_seed,
            max_bytes=KP1982_MAX_LAYOUT_SEED_BYTES,
        )
        page_pbm_bytes = [
            _read_regular_bytes(
                path,
                max_bytes=KP1982_MAX_PAGE_PBM_BYTES,
            )
            for path in (args.page20_pbm, args.page21_pbm)
        ]
        proposal_bytes = _read_private_regular_bytes(
            args.proposal,
            max_bytes=KP1982_MAX_LAYOUT_PROPOSAL_BYTES,
        )
        summary = verify_layout_proposal_bytes(
            source_contract_bytes,
            layout_seed_bytes,
            page_pbm_bytes,
            proposal_bytes,
        )
        summary["private_storage_verified"] = True
    except (OSError, ValueError) as error:
        raise KP1982LayoutError("KP1982 layout proposal verification failed") from error
    _print_json(summary)
    return 0


def _command_prepare_kp1982_bootstrap_assignment(args: argparse.Namespace) -> int:
    try:
        source_contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1982_MAX_CONTRACT_BYTES,
        )
        layout_seed_bytes = _read_regular_bytes(
            args.layout_seed,
            max_bytes=KP1982_MAX_LAYOUT_SEED_BYTES,
        )
        page_pbm_bytes = [
            _read_regular_bytes(
                path,
                max_bytes=KP1982_MAX_PAGE_PBM_BYTES,
            )
            for path in (args.page20_pbm, args.page21_pbm)
        ]
        proposal_bytes = _read_private_regular_bytes(
            args.proposal,
            max_bytes=KP1982_MAX_LAYOUT_PROPOSAL_BYTES,
        )
        assignment = build_bootstrap_assignment(
            source_contract_bytes,
            layout_seed_bytes,
            page_pbm_bytes,
            proposal_bytes,
        )
    except (OSError, ValueError) as error:
        raise KP1982BootstrapError("KP1982 bootstrap assignment preparation failed") from error

    try:
        durability_confirmed, content_verified = _write_private_json_no_replace(
            args.output,
            assignment,
        )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1982BootstrapError(
            "private KP1982 bootstrap assignment could not be created safely"
        ) from error
    if not durability_confirmed or not content_verified:
        _print_json(
            {
                "valid": False,
                "written": False,
                "claim_class": "private_bootstrap_assignment_only",
                "output_content_verified": content_verified,
                "durability_confirmed": durability_confirmed,
                "postcondition": (
                    "committed_content_verified_durability_unknown"
                    if content_verified
                    else "committed_content_unknown"
                ),
                "destination_may_exist": True,
                "counts_disclosed": False,
                "private_storage_verified": False,
                "source_page_pixels_verified": True,
                "layout_proposal_canonical_bytes_verified": True,
                "assignment_canonical_bytes_verified": content_verified,
                "machine_answer_values_withheld": content_verified,
                "cell_geometry_accepted": False,
                "occupancy_accepted": False,
                "human_review_complete": False,
                "reviewer_independence_verified": False,
                "reviewer_blinding_verified": False,
                "identifiers_transcribed": False,
                "public_release_authorized": False,
                "evaluation_admissible": False,
                "decipherment": False,
            }
        )
        return 1
    _print_json(
        {
            "valid": True,
            "written": True,
            "claim_class": "private_bootstrap_assignment_only",
            "counts_disclosed": False,
            "private_storage_verified": True,
            "source_page_pixels_verified": True,
            "layout_proposal_canonical_bytes_verified": True,
            "assignment_canonical_bytes_verified": True,
            "machine_answer_values_withheld": True,
            "cell_geometry_accepted": False,
            "occupancy_accepted": False,
            "human_review_complete": False,
            "reviewer_independence_verified": False,
            "reviewer_blinding_verified": False,
            "identifiers_transcribed": False,
            "public_release_authorized": False,
            "evaluation_admissible": False,
            "decipherment": False,
        }
    )
    return 0


def _command_verify_kp1982_bootstrap_assignment(args: argparse.Namespace) -> int:
    try:
        source_contract_bytes = _read_regular_bytes(
            args.contract,
            max_bytes=KP1982_MAX_CONTRACT_BYTES,
        )
        layout_seed_bytes = _read_regular_bytes(
            args.layout_seed,
            max_bytes=KP1982_MAX_LAYOUT_SEED_BYTES,
        )
        page_pbm_bytes = [
            _read_regular_bytes(
                path,
                max_bytes=KP1982_MAX_PAGE_PBM_BYTES,
            )
            for path in (args.page20_pbm, args.page21_pbm)
        ]
        proposal_bytes = _read_private_regular_bytes(
            args.proposal,
            max_bytes=KP1982_MAX_LAYOUT_PROPOSAL_BYTES,
        )
        assignment_bytes = _read_private_regular_bytes(
            args.assignment,
            max_bytes=KP1982_MAX_BOOTSTRAP_ASSIGNMENT_BYTES,
        )
        summary = verify_bootstrap_assignment_bytes(
            source_contract_bytes,
            layout_seed_bytes,
            page_pbm_bytes,
            proposal_bytes,
            assignment_bytes,
        )
        summary["private_storage_verified"] = True
    except (OSError, ValueError) as error:
        raise KP1982BootstrapError("KP1982 bootstrap assignment verification failed") from error
    _print_json(summary)
    return 0


def _kp1982_bootstrap_review_safe_summary(
    claim_class: str,
    **verified_operations: bool,
) -> dict[str, bool | str]:
    """Return a fixed, count-free public summary for private review operations."""

    return {
        "valid": True,
        "claim_class": claim_class,
        "counts_disclosed": False,
        "private_values_disclosed": False,
        "raw_identifier_values_disclosed": False,
        "cell_ids_disclosed": False,
        "record_ids_disclosed": False,
        "private_storage_verified": True,
        "canonical_page_bitmaps_verified": True,
        "assignment_exact_bytes_verified": True,
        "assignment_roster_verified": True,
        "layout_proposal_not_supplied": True,
        "preexisting_sign_inventory_not_supplied": True,
        "independent_review_record_verified": False,
        "independent_review_records_verified": False,
        "distinct_record_actor_assignment_ids_verified": False,
        "submitted_crop_bytes_recomputed": False,
        "two_review_audit_verified": False,
        "private_report_written": False,
        "adjudication_record_verified": False,
        "no_invention_rule_verified": False,
        "human_review_started_verified": False,
        "human_review_complete_verified": False,
        "human_adjudication_complete_verified": False,
        "human_authorship_verified": False,
        "real_world_independence_verified": False,
        "reviewer_blinding_verified": False,
        "reviewer_nonexposure_verified": False,
        "source_custody_verified": False,
        "source_rights_verified": False,
        "sign_inventory_generated": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
        **verified_operations,
    }


def _read_kp1982_bootstrap_review_context(
    args: argparse.Namespace,
) -> tuple[bytes, list[bytes]]:
    """Read one private assignment and the two public page images safely."""

    assignment_bytes = _read_private_regular_bytes(
        args.assignment,
        max_bytes=KP1982_MAX_BOOTSTRAP_ASSIGNMENT_BYTES,
    )
    page_pbm_bytes = [
        _read_regular_bytes(path, max_bytes=KP1982_MAX_PAGE_PBM_BYTES)
        for path in (args.page20_pbm, args.page21_pbm)
    ]
    return assignment_bytes, page_pbm_bytes


def _command_verify_kp1982_bootstrap_review_input(args: argparse.Namespace) -> int:
    try:
        assignment_bytes, page_pbm_bytes = _read_kp1982_bootstrap_review_context(args)
        verify_stripped_bootstrap_assignment_bytes(assignment_bytes, page_pbm_bytes)
    except (OSError, ValueError) as error:
        raise KP1982BootstrapReviewError(
            "KP1982 bootstrap reviewer input verification failed"
        ) from error
    _print_json(
        _kp1982_bootstrap_review_safe_summary(
            "private_bootstrap_reviewer_input_verification",
            independent_review_record_verified=False,
            two_review_audit_verified=False,
            adjudication_record_verified=False,
        )
    )
    return 0


def _command_verify_kp1982_bootstrap_review(args: argparse.Namespace) -> int:
    try:
        assignment_bytes, page_pbm_bytes = _read_kp1982_bootstrap_review_context(args)
        review_bytes = _read_private_regular_bytes(
            args.review,
            max_bytes=KP1982_MAX_BOOTSTRAP_REVIEW_BYTES,
        )
        verify_independent_review_bytes(
            assignment_bytes,
            page_pbm_bytes,
            review_bytes,
        )
    except (OSError, ValueError) as error:
        raise KP1982BootstrapReviewError(
            "KP1982 independent bootstrap review verification failed"
        ) from error
    _print_json(
        _kp1982_bootstrap_review_safe_summary(
            "private_bootstrap_independent_review_verification",
            independent_review_record_verified=True,
            submitted_crop_bytes_recomputed=True,
            two_review_audit_verified=False,
            adjudication_record_verified=False,
        )
    )
    return 0


def _command_audit_kp1982_bootstrap_reviews(args: argparse.Namespace) -> int:
    try:
        assignment_bytes, page_pbm_bytes = _read_kp1982_bootstrap_review_context(args)
        review_bytes = [
            _read_private_regular_bytes(
                path,
                max_bytes=KP1982_MAX_BOOTSTRAP_REVIEW_BYTES,
            )
            for path in (args.left, args.right)
        ]
        private_report = compare_independent_review_bytes(
            assignment_bytes,
            page_pbm_bytes,
            review_bytes,
        )
    except (OSError, ValueError) as error:
        raise KP1982BootstrapReviewError("KP1982 bootstrap two-review audit failed") from error

    try:
        durability_confirmed, content_verified = _write_private_json_no_replace(
            args.private_report,
            private_report,
        )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise KP1982BootstrapReviewError(
            "private KP1982 bootstrap review audit could not be created safely"
        ) from error
    if not durability_confirmed or not content_verified:
        summary = _kp1982_bootstrap_review_safe_summary(
            "private_bootstrap_two_review_audit",
            independent_review_records_verified=True,
            distinct_record_actor_assignment_ids_verified=True,
            two_review_audit_verified=True,
            submitted_crop_bytes_recomputed=True,
            private_report_written=False,
            output_content_verified=content_verified,
            durability_confirmed=durability_confirmed,
            destination_may_exist=True,
            adjudication_record_verified=False,
        )
        summary["valid"] = False
        summary["private_storage_verified"] = False
        _print_json(summary)
        return 1

    _print_json(
        _kp1982_bootstrap_review_safe_summary(
            "private_bootstrap_two_review_audit",
            independent_review_records_verified=True,
            distinct_record_actor_assignment_ids_verified=True,
            two_review_audit_verified=True,
            submitted_crop_bytes_recomputed=True,
            private_report_written=True,
            output_content_verified=True,
            durability_confirmed=True,
            agreement_result_disclosed=False,
            adjudication_record_verified=False,
        )
    )
    return 0


def _command_verify_kp1982_bootstrap_adjudication(args: argparse.Namespace) -> int:
    try:
        assignment_bytes, page_pbm_bytes = _read_kp1982_bootstrap_review_context(args)
        review_bytes = [
            _read_private_regular_bytes(
                path,
                max_bytes=KP1982_MAX_BOOTSTRAP_REVIEW_BYTES,
            )
            for path in (args.left, args.right)
        ]
        adjudication_bytes = _read_private_regular_bytes(
            args.adjudication,
            max_bytes=KP1982_MAX_BOOTSTRAP_REVIEW_BYTES,
        )
        verify_adjudication_bytes(
            assignment_bytes,
            page_pbm_bytes,
            review_bytes,
            adjudication_bytes,
        )
    except (OSError, ValueError) as error:
        raise KP1982BootstrapReviewError(
            "KP1982 bootstrap adjudication verification failed"
        ) from error
    _print_json(
        _kp1982_bootstrap_review_safe_summary(
            "private_bootstrap_adjudication_verification",
            independent_review_records_verified=True,
            distinct_record_actor_assignment_ids_verified=True,
            adjudication_record_verified=True,
            submitted_crop_bytes_recomputed=True,
            no_invention_rule_verified=True,
        )
    )
    return 0


def _read_transcription_json(path: Path) -> tuple[dict[str, Any], bytes, str]:
    """Read and hash one bounded, immutable transcription input snapshot."""

    try:
        raw_bytes = _read_regular_bytes(path, max_bytes=MUSEUM_MAX_INDEX_BYTES)
        value = _museum_json_value(raw_bytes, label="transcription input")
    except ValueError as error:
        raise TranscriptionReviewError(
            "transcription input could not be read as a safe finite JSON object"
        ) from error
    if not isinstance(value, dict):
        raise TranscriptionReviewError("transcription input must be an object")
    return value, raw_bytes, sha256_bytes(raw_bytes)


def _command_audit_transcription_agreement(args: argparse.Namespace) -> int:
    inventory, _inventory_bytes, inventory_sha256 = _read_transcription_json(args.inventory)
    left, _left_bytes, _left_sha256 = _read_transcription_json(args.left)
    right, _right_bytes, _right_sha256 = _read_transcription_json(args.right)
    inventory_schema = args.inventory_schema or _default_schema("sign-inventory.schema.json")
    review_schema = args.review_schema or _default_schema("transcription-review.schema.json")
    _require_schema_valid(inventory, inventory_schema, label="sign inventory")
    _require_schema_valid(left, review_schema, label="left transcription")
    _require_schema_valid(right, review_schema, label="right transcription")
    validate_sign_inventory(inventory)
    validate_transcription_review(
        left,
        inventory,
        inventory_sha256=inventory_sha256,
    )
    validate_transcription_review(
        right,
        inventory,
        inventory_sha256=inventory_sha256,
    )
    summary = compare_independent_transcriptions(
        left,
        right,
        minimum_bbox_iou=args.minimum_bbox_iou,
    )
    summary["inventory_bytes_verified"] = True
    summary["source_commitment_cross_record_consistent"] = True
    summary["source_image_bytes_present_or_rehashed"] = False
    private_report_written = False
    if args.private_report is not None:
        try:
            durability_confirmed, content_verified = _write_private_json_no_replace(
                args.private_report,
                summary,
            )
        except (OSError, PrivateReadinessError, ValueError) as error:
            raise TranscriptionReviewError(
                "private transcription report could not be created safely"
            ) from error
        if not durability_confirmed or not content_verified:
            _print_json(
                {
                    "valid": False,
                    "claim_class": "private_draft_validation",
                    "private_report_written": False,
                    "output_content_verified": content_verified,
                    "durability_confirmed": durability_confirmed,
                    "postcondition": "committed_durability_unknown",
                    "counts_disclosed": False,
                    "agreement_result_disclosed": False,
                    "real_world_independence_verified": False,
                    "decipherment": False,
                }
            )
            return 1
        private_report_written = True
    _print_json(
        {
            "valid": True,
            "claim_class": "private_draft_validation",
            "private_report_written": private_report_written,
            "counts_disclosed": False,
            "agreement_result_disclosed": False,
            "real_world_independence_verified": False,
            "decipherment": False,
        }
    )
    return 0


def _command_promote_transcription(args: argparse.Namespace) -> int:
    inventory, inventory_bytes, _inventory_sha256 = _read_transcription_json(args.inventory)
    artifact_template, _template_bytes, _template_sha256 = _read_transcription_json(
        args.artifact_template
    )
    adjudication, adjudication_bytes, _adjudication_sha256 = _read_transcription_json(
        args.adjudication
    )
    independent_evidence = [_read_transcription_json(path) for path in args.review]
    independent_reviews = [review for review, _raw_bytes, _digest in independent_evidence]
    independent_review_bytes = [raw_bytes for _review, raw_bytes, _digest in independent_evidence]

    inventory_schema = args.inventory_schema or _default_schema("sign-inventory.schema.json")
    review_schema = args.review_schema or _default_schema("transcription-review.schema.json")
    artifact_schema = args.artifact_schema or _default_artifact_schema()
    if artifact_schema is None:
        raise TranscriptionReviewError("artifact schema not found")

    _require_schema_valid(inventory, inventory_schema, label="sign inventory")
    _require_schema_valid(
        artifact_template,
        artifact_schema,
        label="artifact template",
    )
    _require_schema_valid(
        adjudication,
        review_schema,
        label="transcription adjudication",
    )
    for index, review in enumerate(independent_reviews):
        _require_schema_valid(
            review,
            review_schema,
            label=f"independent transcription {index}",
        )

    promotion = promote_adjudicated_transcription(
        artifact_template,
        inventory_bytes=inventory_bytes,
        independent_review_bytes=independent_review_bytes,
        adjudication_bytes=adjudication_bytes,
        side_id=args.side_id,
        line_id=args.line_id,
        release_scope=args.release_scope,
    )
    artifact = promotion.artifact
    _require_schema_valid(artifact, artifact_schema, label="promoted artifact")
    semantic_issues = validate_corpus([artifact])
    if has_errors(semantic_issues):
        first = next(issue for issue in semantic_issues if issue.severity == "error")
        raise TranscriptionReviewError(f"promoted artifact invalid at {first.path}")

    try:
        durability_confirmed, content_verified = _write_private_json_no_replace(
            args.output,
            artifact,
        )
    except (OSError, PrivateReadinessError, ValueError) as error:
        raise TranscriptionReviewError(
            "private transcription artifact could not be created safely"
        ) from error
    if not durability_confirmed or not content_verified:
        _print_json(
            {
                "valid": False,
                "written": False,
                "claim_class": "private_staging_only",
                "output_content_verified": content_verified,
                "durability_confirmed": durability_confirmed,
                "postcondition": "committed_durability_unknown",
                "counts_disclosed": False,
                "private_evidence_disclosed": False,
                "evaluation_admissible": False,
                "real_world_reviewer_independence_verified": False,
                "blind_evaluation": False,
                "decipherment": False,
            }
        )
        return 1
    _print_json(
        {
            "valid": True,
            "written": True,
            "claim_class": "private_staging_only",
            "counts_disclosed": False,
            "private_evidence_disclosed": False,
            "evaluation_admissible": False,
            "real_world_reviewer_independence_verified": False,
            "blind_evaluation": False,
            "decipherment": False,
        }
    )
    return 0


def _command_audit_private_readiness(args: argparse.Namespace) -> int:
    """Run a redacted private-corpus readiness audit."""

    try:
        policy: dict[str, Any] | None = None
        source_registry: dict[str, Any] | None = None
        quarantine_registry: dict[str, Any] | None = None
        policy_path = args.policy or args.policy_bundle
        if policy_path is not None:
            _assert_private_input_outside_root(args.root, policy_path)
            for registry_path in (
                args.source_registry,
                args.quarantine_registry,
            ):
                _assert_private_input_outside_root(
                    args.root,
                    registry_path.absolute(),
                )
            if args.policy_bundle is not None:
                bundle = read_private_review_bundle(args.policy_bundle)
                for document, schema_name in (
                    (bundle.as_dict(), "private-review-bundle.schema.json"),
                    (bundle.policy, "private-corpus-policy.schema.json"),
                    (
                        bundle.structural_quarantine,
                        "private-structural-quarantine.schema.json",
                    ),
                ):
                    if validate_schema_instance(
                        document,
                        _default_schema(schema_name),
                    ):
                        raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
                policy = bundle.policy
            else:
                assert args.policy is not None
                policy = read_private_policy(args.policy)
            raw_source_registry = read_json(args.source_registry)
            raw_quarantine_registry = read_json(args.quarantine_registry)
            if not isinstance(raw_source_registry, dict) or not isinstance(
                raw_quarantine_registry,
                dict,
            ):
                raise PrivateReadinessError("POLICY_DOCUMENT_INVALID")
            source_registry = raw_source_registry
            quarantine_registry = raw_quarantine_registry

        result = audit_private_corpus(
            args.root,
            intended_use=args.intended_use,
            created_at=args.created_at,
            policy=policy,
            source_registry=source_registry,
            quarantine_manifest=quarantine_registry,
        )
        if args.private_report is not None:
            if not args.private_report.is_absolute():
                raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")
            report_parent = args.private_report.parent
            _assert_private_creation_root(report_parent)
            root = args.root
            report_path = args.private_report.resolve(strict=False)
            if report_path == root or report_path.is_relative_to(root):
                raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")
            if result.report is None:
                raise PrivateReadinessError("INTERNAL_ERROR")
            schema_issues = validate_schema_instance(
                result.report,
                _default_schema("private-corpus-readiness.schema.json"),
            )
            if schema_issues:
                raise PrivateReadinessError("INTERNAL_ERROR")
            durability_confirmed, content_verified = _write_json_no_replace(
                args.private_report,
                result.report,
                mode=0o600,
            )
            if not durability_confirmed or not content_verified:
                raise PrivateReadinessError("INTERNAL_ERROR")
        _print_json(result.summary)
        return 0 if result.summary["ready"] is True else 2
    except PrivateReviewError:
        _print_json(safe_failure_summary(args.intended_use, "POLICY_DOCUMENT_INVALID"))
        return 2
    except PrivateReadinessError as error:
        _print_json(safe_failure_summary(args.intended_use, error.code))
        return 2
    except Exception:
        _print_json(safe_failure_summary(args.intended_use, "INTERNAL_ERROR"))
        return 2


def _assert_private_input_outside_root(root: Path, candidate: Path) -> None:
    if not root.is_absolute() or not candidate.is_absolute():
        raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")
    try:
        root_resolved = root.resolve(strict=True)
        candidate_resolved = candidate.resolve(strict=True)
    except OSError:
        raise PrivateReadinessError("INPUT_UNREADABLE_OR_UNVERIFIABLE") from None
    if candidate_resolved == root_resolved or candidate_resolved.is_relative_to(root_resolved):
        raise PrivateReadinessError("ROOT_BOUNDARY_INVALID")


def _command_prepare_private_review(args: argparse.Namespace) -> int:
    """Create one atomic, deny-all private review bundle."""

    scan_completed = False
    try:
        bundle = build_private_review_bundle(
            args.root,
            args.created_at,
        )
        scan_completed = True
        for document, schema_name in (
            (bundle.as_dict(), "private-review-bundle.schema.json"),
            (bundle.policy, "private-corpus-policy.schema.json"),
            (
                bundle.structural_quarantine,
                "private-structural-quarantine.schema.json",
            ),
        ):
            if validate_schema_instance(document, _default_schema(schema_name)):
                raise PrivateReviewError("ARTIFACT_VALIDATION_FAILED")
        publication = publish_private_review_bundle(
            args.root,
            args.output,
            bundle,
        )
        _print_json(
            safe_private_review_summary(
                scan_completed=True,
                write_state=publication.write_state,
                reason_code=publication.reason_code,
            )
        )
        return 0 if publication.write_state == "committed_and_verified" else 2
    except PrivateReviewError as error:
        _print_json(
            safe_private_review_summary(
                scan_completed=scan_completed,
                write_state="not_written",
                reason_code=error.code,
            )
        )
        return 2
    except PrivateReadinessError as error:
        _print_json(
            safe_private_review_summary(
                scan_completed=False,
                write_state="not_written",
                reason_code=error.code,
            )
        )
        return 2
    except Exception:
        _print_json(
            safe_private_review_summary(
                scan_completed=scan_completed,
                write_state="not_written",
                reason_code="INTERNAL_ERROR",
            )
        )
        return 2


def _command_import_mayig(args: argparse.Namespace) -> int:
    if not _target_is_clear(args.output, args.force):
        return 1
    records = import_mayig_corpus(
        args.source,
        source_revision=args.revision,
        retrieved_at=args.retrieved_at,
    )
    quarantine = _require_quarantine(records, args, purpose="corpus_ingestion")
    issues = validate_corpus(records)
    if args.full_schema:
        schema_path = args.schema or _default_artifact_schema()
        if schema_path is None:
            print("artifact schema not found; pass --schema explicitly", file=sys.stderr)
            return 1
        issues.extend(validate_artifact_rows(records, schema_path))
    if has_errors(issues):
        _print_json(
            {
                "written": False,
                "errors": [issue.as_dict() for issue in issues],
            }
        )
        return 2
    write_jsonl(args.output, records)
    _print_json(
        {
            "written": True,
            "output": str(args.output),
            "artifacts": len(records),
            "quarantine": quarantine.as_dict(),
            "warnings": [issue.as_dict() for issue in issues if issue.severity == "warning"],
        }
    )
    return 0


def _command_intake_museum(args: argparse.Namespace) -> int:
    output_dir: Path = args.output_dir
    if not _target_is_clear(output_dir, False):
        return 1
    met_object_ids = list(dict.fromkeys(args.met_object or []))
    cleveland_accessions = list(dict.fromkeys(args.cleveland_accession or []))
    if not met_object_ids and not cleveland_accessions:
        raise ValueError("provide at least one --met-object or --cleveland-accession")
    requested_record_count = len(met_object_ids) + len(cleveland_accessions)
    if requested_record_count > args.max_media_count:
        raise ValueError(
            f"museum record request count exceeds limit: "
            f"{requested_record_count} > {args.max_media_count}"
        )

    retrieved_at = _utc_timestamp()
    derivatives = tuple(args.cleveland_derivative or ("print", "full"))
    schema_path: Path | None = args.schema
    if args.full_schema and schema_path is None:
        schema_path = _default_museum_intake_schema()
        if schema_path is None:
            print("museum intake schema not found; pass --schema explicitly", file=sys.stderr)
            return 1

    selected_source_ids = []
    if met_object_ids:
        selected_source_ids.append("met-open-access-indus")
    if cleveland_accessions:
        selected_source_ids.append("cleveland-open-access-indus")
    policy_documents = fetch_policy_documents(
        selected_source_ids,
        timeout=args.timeout,
        max_bytes=args.max_json_bytes,
        max_total_bytes=args.max_total_json_bytes,
    )
    fetched: list[tuple[dict[str, Any], Any]] = []
    total_json_bytes = sum(len(document.raw_bytes) for document in policy_documents)
    planned_media_count = 0
    for object_id in met_object_ids:
        fetched_record = fetch_met_intake(
            object_id,
            retrieved_at=retrieved_at,
            timeout=args.timeout,
            max_json_bytes=args.max_json_bytes,
        )
        total_json_bytes += len(fetched_record[1].raw_bytes)
        planned_media_count += len(fetched_record[0]["media"])
        if total_json_bytes > args.max_total_json_bytes:
            raise ValueError("museum API responses exceed aggregate byte limit")
        if planned_media_count > args.max_media_count:
            raise ValueError("museum media count exceeds limit")
        fetched.append(fetched_record)
    for accession_number in cleveland_accessions:
        fetched_record = fetch_cleveland_intake(
            accession_number,
            retrieved_at=retrieved_at,
            derivatives=derivatives,
            timeout=args.timeout,
            max_json_bytes=args.max_json_bytes,
        )
        total_json_bytes += len(fetched_record[1].raw_bytes)
        planned_media_count += len(fetched_record[0]["media"])
        if total_json_bytes > args.max_total_json_bytes:
            raise ValueError("museum API responses exceed aggregate byte limit")
        if planned_media_count > args.max_media_count:
            raise ValueError("museum media count exceeds limit")
        fetched.append(fetched_record)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=".museum-intake-",
            dir=output_dir.parent,
        )
    )
    # 0o700 is intentionally owner-only while intake bytes are unreviewed.
    # nosemgrep
    os.chmod(staging_dir, 0o700)
    try:
        _assert_private_creation_root(staging_dir)
        records: list[dict[str, Any]] = []
        verification_reports: list[dict[str, Any]] = []
        total_downloaded_bytes = 0
        policy_entries = [
            policy_manifest_entry(document, retrieved_at=retrieved_at)
            for document in policy_documents
        ]
        for document in policy_documents:
            write_policy_document(document, root=staging_dir)
        for index, (record, document) in enumerate(fetched):
            validate_intake_semantics(record, document=document)
            if schema_path is not None:
                issues = validate_schema_instance(
                    record,
                    schema_path,
                    path_prefix=f"$[{index}]",
                )
                if issues:
                    _print_json(
                        {
                            "written": False,
                            "errors": [issue.as_dict() for issue in issues],
                        }
                    )
                    return 2
            write_intake_raw_response(
                record,
                document,
                root=staging_dir,
            )
            if args.download_media:
                remaining_total_bytes = args.max_total_media_bytes - total_downloaded_bytes
                if remaining_total_bytes < 1:
                    raise ValueError("museum media bytes exceed the aggregate download limit")
                record = download_intake_media(
                    record,
                    root=staging_dir,
                    downloaded_at=retrieved_at,
                    timeout=args.timeout,
                    max_bytes=args.max_media_bytes,
                    max_media_count=args.max_media_count,
                    max_total_bytes=remaining_total_bytes,
                )
                total_downloaded_bytes += sum(
                    media["download"]["bytes"] for media in record["media"]
                )
            validate_intake_semantics(record, document=document)
            if schema_path is not None:
                issues = validate_schema_instance(
                    record,
                    schema_path,
                    path_prefix=f"$[{index}]",
                )
                if issues:
                    _print_json(
                        {
                            "written": False,
                            "errors": [issue.as_dict() for issue in issues],
                        }
                    )
                    return 2
            verification = verify_intake_bundle(
                record,
                root=staging_dir,
                max_json_bytes=args.max_json_bytes,
                max_media_bytes=args.max_media_bytes,
                max_media_count=args.max_media_count,
                max_total_media_bytes=args.max_total_media_bytes,
            )
            verification["record_sha256"] = f"sha256:{sha256_json(record)}"
            records.append(record)
            verification_reports.append(verification)

        media_count = sum(len(record["media"]) for record in records)
        downloaded_media_count = sum(
            report["downloaded_media_count"] for report in verification_reports
        )
        downloaded_media_bytes = sum(
            report["downloaded_media_bytes"] for report in verification_reports
        )
        manifest = {
            "bundle_version": MUSEUM_BUNDLE_VERSION,
            "created_at": retrieved_at,
            "record_count": len(records),
            "media_count": media_count,
            "downloaded_media_count": downloaded_media_count,
            "downloaded_media_bytes": downloaded_media_bytes,
            "source_ids": sorted({record["source_id"] for record in records}),
            "policy_evidence": policy_entries,
            "records": verification_reports,
            "scientific_scope": MUSEUM_SCIENTIFIC_SCOPE,
        }
        verify_policy_evidence(
            policy_entries,
            source_ids=manifest["source_ids"],
            root=staging_dir,
            max_bytes=args.max_json_bytes,
            max_total_bytes=args.max_total_json_bytes,
        )
        write_jsonl(staging_dir / "intake.jsonl", records)
        write_json(staging_dir / "bundle-manifest.json", manifest)
        for private_path in staging_dir.rglob("*"):
            os.chmod(private_path, 0o700 if private_path.is_dir() else 0o600)
        _assert_private_tree(staging_dir)
        _rename_directory_no_replace(staging_dir, output_dir)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)

    _print_json(
        {
            "written": True,
            "output": str(output_dir),
            **manifest,
        }
    )
    return 0


def _command_verify_museum_intake(args: argparse.Namespace) -> int:
    bundle_dir: Path = args.bundle_dir
    review_output: Path | None = getattr(args, "prepare_review", None)
    if review_output is not None:
        if not _target_is_clear(review_output, False):
            return 1
        _validate_review_destination(bundle_dir, review_output)
        review_subject_schema: Path | None = getattr(
            args,
            "review_subject_schema",
            None,
        )
        if review_subject_schema is None:
            review_subject_schema = _default_museum_review_subject_schema()
        if review_subject_schema is None:
            print(
                "museum review subject schema not found; pass --review-subject-schema",
                file=sys.stderr,
            )
            return 1
    else:
        review_subject_schema = None
    preflight_file_inventory, preflight_directory_inventory = _museum_bundle_inventory(
        bundle_dir,
        max_json_bytes=args.max_json_bytes,
        max_media_bytes=args.max_media_bytes,
        max_media_count=args.max_media_count,
        max_total_json_bytes=args.max_total_json_bytes,
        max_total_media_bytes=args.max_total_media_bytes,
    )
    records = _read_museum_records(bundle_dir / "intake.jsonl")
    manifest, manifest_bytes = _read_museum_manifest(bundle_dir / "bundle-manifest.json")
    manifest_file_sha256 = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
    if len(records) > args.max_media_count:
        raise ValueError(
            f"museum intake record count exceeds limit: {len(records)} > {args.max_media_count}"
        )
    declared_media_count = sum(
        len(record.get("media", [])) for record in records if isinstance(record.get("media"), list)
    )
    if declared_media_count > args.max_media_count:
        raise ValueError(
            f"museum declared media count exceeds limit: "
            f"{declared_media_count} > {args.max_media_count}"
        )
    schema_path: Path | None = args.schema
    if args.full_schema and schema_path is None:
        schema_path = _default_museum_intake_schema()
        if schema_path is None:
            print("museum intake schema not found; pass --schema explicitly", file=sys.stderr)
            return 1

    schema_issues = []
    reports = []
    verified_media_bytes = 0
    for index, record in enumerate(records):
        validate_intake_semantics(record)
        if schema_path is not None:
            schema_issues.extend(
                validate_schema_instance(
                    record,
                    schema_path,
                    path_prefix=f"$[{index}]",
                )
            )
        report = verify_intake_bundle(
            record,
            root=bundle_dir,
            max_json_bytes=args.max_json_bytes,
            max_media_bytes=args.max_media_bytes,
            max_media_count=args.max_media_count,
            max_total_media_bytes=max(
                1,
                args.max_total_media_bytes - verified_media_bytes,
            ),
        )
        report["record_sha256"] = f"sha256:{sha256_json(record)}"
        reports.append(report)
        verified_media_bytes += report["downloaded_media_bytes"]
    if schema_issues:
        _print_json(
            {
                "valid": False,
                "errors": [issue.as_dict() for issue in schema_issues],
            }
        )
        return 2

    media_count = sum(len(record["media"]) for record in records)
    downloaded_media_count = sum(report["downloaded_media_count"] for report in reports)
    downloaded_media_bytes = sum(report["downloaded_media_bytes"] for report in reports)
    source_ids = sorted({record["source_id"] for record in records})
    policy_reports = verify_policy_evidence(
        manifest.get("policy_evidence"),
        source_ids=source_ids,
        root=bundle_dir,
        max_bytes=args.max_json_bytes,
        max_total_bytes=args.max_total_json_bytes,
    )
    actual = {
        "record_count": len(records),
        "media_count": media_count,
        "downloaded_media_count": downloaded_media_count,
        "downloaded_media_bytes": downloaded_media_bytes,
        "source_ids": source_ids,
    }
    mismatches = [
        f"{field}: manifest={manifest.get(field)!r}, actual={value!r}"
        for field, value in actual.items()
        if manifest.get(field) != value
    ]
    required_manifest_keys = {
        "bundle_version",
        "created_at",
        "record_count",
        "media_count",
        "downloaded_media_count",
        "downloaded_media_bytes",
        "source_ids",
        "policy_evidence",
        "records",
        "scientific_scope",
    }
    manifest_keys = set(manifest)
    for key in sorted(required_manifest_keys - manifest_keys):
        mismatches.append(f"manifest is missing required field: {key}")
    for key in sorted(manifest_keys - required_manifest_keys):
        mismatches.append(f"manifest contains unknown field: {key}")
    count_fields = (
        "record_count",
        "media_count",
        "downloaded_media_count",
        "downloaded_media_bytes",
    )
    for field in count_fields:
        value = manifest.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            mismatches.append(f"manifest.{field} must be a nonnegative integer")
    if manifest.get("bundle_version") != MUSEUM_BUNDLE_VERSION:
        mismatches.append(
            f"bundle_version: expected={MUSEUM_BUNDLE_VERSION!r}, "
            f"actual={manifest.get('bundle_version')!r}"
        )
    if manifest.get("scientific_scope") != MUSEUM_SCIENTIFIC_SCOPE:
        mismatches.append("manifest scientific_scope does not match the intake-only boundary")
    created_at = manifest.get("created_at")
    if not isinstance(created_at, str):
        mismatches.append("manifest.created_at must be an RFC 3339 string")
    else:
        try:
            normalized_created_at = _rfc3339(created_at)
        except argparse.ArgumentTypeError:
            mismatches.append("manifest.created_at must be a valid RFC 3339 date-time")
        else:
            if normalized_created_at != created_at:
                mismatches.append("manifest.created_at must use canonical RFC 3339 form")
        record_retrieval_times = {record["retrieval"]["retrieved_at"] for record in records}
        if record_retrieval_times != {created_at}:
            mismatches.append("manifest.created_at must equal every intake retrieval timestamp")
        policy_retrieval_times = {
            entry.get("retrieved_at")
            for entry in manifest.get("policy_evidence", [])
            if isinstance(entry, dict)
        }
        if policy_retrieval_times != {created_at}:
            mismatches.append("manifest.created_at must equal every policy retrieval timestamp")
    if not records:
        mismatches.append("museum intake bundle must contain at least one record")
    externally_anchored = args.expected_manifest_sha256 is not None
    anchor_mismatch: str | None = None
    if (
        args.expected_manifest_sha256 is not None
        and args.expected_manifest_sha256 != manifest_file_sha256
    ):
        anchor_mismatch = (
            f"external manifest anchor mismatch: "
            f"expected={args.expected_manifest_sha256}, actual={manifest_file_sha256}"
        )
        externally_anchored = False

    record_intake_ids = [report.get("intake_id") for report in reports]
    if any(not isinstance(intake_id, str) or not intake_id for intake_id in record_intake_ids):
        mismatches.append("intake records must have non-empty string intake_id values")
    if len(set(record_intake_ids)) != len(record_intake_ids):
        mismatches.append("intake.jsonl contains duplicate intake_id values")

    manifest_records_value = manifest.get("records")
    if not isinstance(manifest_records_value, list):
        mismatches.append("manifest.records must be a list")
        manifest_records: list[dict[str, Any]] = []
    else:
        manifest_records = [item for item in manifest_records_value if isinstance(item, dict)]
        if len(manifest_records) != len(manifest_records_value):
            mismatches.append("manifest.records contains a non-object entry")
    required_report_keys = {
        "intake_id",
        "raw_response_sha256",
        "raw_response_bytes",
        "downloaded_media_count",
        "downloaded_media_bytes",
        "record_sha256",
        "verified",
    }
    for index, item in enumerate(manifest_records):
        item_keys = set(item)
        for key in sorted(required_report_keys - item_keys):
            mismatches.append(f"manifest.records[{index}] is missing required field: {key}")
        for key in sorted(item_keys - required_report_keys):
            mismatches.append(f"manifest.records[{index}] contains unknown field: {key}")
        if item.get("verified") is not True:
            mismatches.append(f"manifest.records[{index}].verified must be true")
        intake_id = item.get("intake_id")
        if not isinstance(intake_id, str) or not STABLE_ID_PATTERN.fullmatch(intake_id):
            mismatches.append(f"manifest.records[{index}].intake_id must be a stable identifier")
        for field in ("raw_response_sha256", "record_sha256"):
            value = item.get(field)
            if not isinstance(value, str) or not CHECKSUM_PATTERN.fullmatch(value):
                mismatches.append(f"manifest.records[{index}].{field} must be a SHA-256 checksum")
        for field in (
            "raw_response_bytes",
            "downloaded_media_count",
            "downloaded_media_bytes",
        ):
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                mismatches.append(
                    f"manifest.records[{index}].{field} must be a nonnegative integer"
                )
    manifest_intake_ids = [item.get("intake_id") for item in manifest_records]
    if any(not isinstance(intake_id, str) or not intake_id for intake_id in manifest_intake_ids):
        mismatches.append("manifest records must have non-empty string intake_id values")
    string_manifest_intake_ids = [
        intake_id for intake_id in manifest_intake_ids if isinstance(intake_id, str)
    ]
    if len(set(string_manifest_intake_ids)) != len(string_manifest_intake_ids):
        mismatches.append("manifest.records contains duplicate intake_id values")
    expected_reports = {
        item.get("intake_id"): item
        for item in manifest_records
        if isinstance(item.get("intake_id"), str)
    }
    report_fields = (
        "raw_response_sha256",
        "raw_response_bytes",
        "downloaded_media_count",
        "downloaded_media_bytes",
        "record_sha256",
        "verified",
    )
    for report in reports:
        intake_id = report["intake_id"]
        expected = expected_reports.get(intake_id)
        if expected is None:
            mismatches.append(f"{intake_id}: missing manifest record")
            continue
        for field in report_fields:
            if expected.get(field) != report.get(field):
                mismatches.append(
                    f"{intake_id}.{field}: "
                    f"manifest={expected.get(field)!r}, actual={report.get(field)!r}"
                )
    if len(manifest_records) != len(reports):
        mismatches.append(
            f"manifest record entries: manifest={len(manifest_records)}, actual={len(reports)}"
        )

    expected_file_owners: dict[str, list[str]] = {
        "bundle-manifest.json": ["bundle manifest"],
        "intake.jsonl": ["intake index"],
    }

    def register_expected_path(relative_path: Any, owner: str) -> None:
        if not isinstance(relative_path, str) or not relative_path:
            mismatches.append(f"{owner} lacks a valid bundle-relative path")
            return
        expected_file_owners.setdefault(relative_path, []).append(owner)

    for record in records:
        retrieval = record["retrieval"]
        register_expected_path(
            retrieval["raw_response_local_relative_path"],
            f"{record['intake_id']} raw response",
        )
        for media in record["media"]:
            download = media["download"]
            if download["status"] == "downloaded":
                register_expected_path(
                    download["local_relative_path"],
                    f"{record['intake_id']} {media['media_id']}",
                )
    for policy_entry in manifest["policy_evidence"]:
        register_expected_path(
            policy_entry["raw_response_local_relative_path"],
            f"policy evidence {policy_entry['evidence_id']}",
        )
    for relative_path, owners in sorted(expected_file_owners.items()):
        if len(owners) > 1:
            mismatches.append(
                f"bundle path has multiple owners: {relative_path} ({', '.join(owners)})"
            )
    expected_bundle_files = set(expected_file_owners)
    actual_bundle_files = set(preflight_file_inventory)
    for relative_path in sorted(actual_bundle_files - expected_bundle_files):
        mismatches.append(f"unexpected bundle file: {relative_path}")
    for relative_path in sorted(expected_bundle_files - actual_bundle_files):
        mismatches.append(f"missing bundle file: {relative_path}")

    expected_bundle_directories = {"."}
    for relative_path in expected_bundle_files:
        parts = PurePosixPath(relative_path).parts[:-1]
        for depth in range(1, len(parts) + 1):
            expected_bundle_directories.add(PurePosixPath(*parts[:depth]).as_posix())
    actual_bundle_directories = set(preflight_directory_inventory)
    for relative_path in sorted(actual_bundle_directories - expected_bundle_directories):
        mismatches.append(f"unexpected bundle directory: {relative_path}")
    for relative_path in sorted(expected_bundle_directories - actual_bundle_directories):
        mismatches.append(f"missing bundle directory: {relative_path}")

    postflight_file_inventory, postflight_directory_inventory = _museum_bundle_inventory(
        bundle_dir,
        max_json_bytes=args.max_json_bytes,
        max_media_bytes=args.max_media_bytes,
        max_media_count=args.max_media_count,
        max_total_json_bytes=args.max_total_json_bytes,
        max_total_media_bytes=args.max_total_media_bytes,
    )
    if (
        postflight_file_inventory != preflight_file_inventory
        or postflight_directory_inventory != preflight_directory_inventory
    ):
        mismatches.append("museum bundle changed during verification")

    self_consistent = not mismatches
    if anchor_mismatch is not None:
        mismatches.append(anchor_mismatch)
    review_packet = None
    if not mismatches and review_output is not None and review_subject_schema is not None:
        review_packet = _prepare_museum_review_packet(
            bundle_dir=bundle_dir,
            output_dir=review_output,
            records=records,
            reports=reports,
            source_manifest=manifest,
            source_manifest_sha256=manifest_file_sha256,
            source_externally_anchored=externally_anchored,
            preflight_file_inventory=preflight_file_inventory,
            preflight_directory_inventory=preflight_directory_inventory,
            subject_schema=review_subject_schema,
            max_json_bytes=args.max_json_bytes,
            max_media_bytes=args.max_media_bytes,
            max_media_count=args.max_media_count,
            max_total_json_bytes=args.max_total_json_bytes,
            max_total_media_bytes=args.max_total_media_bytes,
        )
    payload = {
        "valid": not mismatches,
        "self_consistent": self_consistent,
        "externally_anchored": externally_anchored,
        "manifest_file_sha256": manifest_file_sha256,
        "bundle": str(bundle_dir),
        **actual,
        "records": reports,
        "policy_evidence": policy_reports,
        "manifest_mismatches": mismatches,
    }
    if review_packet is not None:
        payload["review_packet"] = review_packet
    _print_json(payload)
    return 0 if not mismatches else 2


def _command_split(args: argparse.Namespace) -> int:
    before = os.stat(args.corpus, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError("split corpus must be a single-link regular file")
    records = read_jsonl(args.corpus)
    after_read = os.stat(args.corpus, follow_symlinks=False)
    if _stat_fingerprint(before) != _stat_fingerprint(after_read):
        raise ValueError("split corpus changed while it was being read")
    quarantine = _require_quarantine(records, args, purpose="corpus_ingestion")
    issues = validate_corpus(records)
    if has_errors(issues):
        _print_json({"written": False, "issues": [issue.as_dict() for issue in issues]})
        return 2

    train, development = deterministic_leakage_safe_split(
        records,
        test_fraction=args.test_fraction,
        seed=args.seed,
    )
    report = audit_leakage(train, development)
    if report.has_leakage:
        _print_json({"written": False, "leakage": report.as_dict()})
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        "train": args.output_dir / "train.jsonl",
        "development": args.output_dir / "development.jsonl",
        "manifest": args.output_dir / "split-manifest.json",
        "audit": args.output_dir / "leakage-audit.json",
    }
    if not all(_target_is_clear(path, args.force) for path in targets.values()):
        return 1

    manifest = build_split_manifest(
        train,
        development,
        seed=args.seed,
        corpus_file_sha256=_sha256_regular_file(args.corpus),
        corpus_file_bytes=after_read.st_size,
        source_registry_sha256=quarantine.source_registry_sha256,
        quarantine_manifest_sha256=quarantine.manifest_sha256,
        test_fraction=args.test_fraction,
        created_by=args.created_by,
    )
    after_hash = os.stat(args.corpus, follow_symlinks=False)
    if _stat_fingerprint(after_read) != _stat_fingerprint(after_hash):
        raise ValueError("split corpus changed while it was being hashed")
    write_jsonl(targets["train"], train)
    write_jsonl(targets["development"], development)
    write_json(targets["manifest"], manifest)
    write_json(targets["audit"], report.as_dict())
    _print_json(
        {
            "written": True,
            "train_artifacts": len(train),
            "development_artifacts": len(development),
            "split_id": manifest["split_id"],
            "corpus_fingerprint": manifest["corpus_fingerprint"],
            "evaluation_assurance": manifest["evaluation_assurance"],
            "quarantine": quarantine.as_dict(),
            "files": {key: str(path) for key, path in targets.items()},
        }
    )
    return 0


def _command_audit(args: argparse.Namespace) -> int:
    train = read_jsonl(args.train)
    test = read_jsonl(args.test)
    if args.allow_quarantined_for_audit:
        quarantine = _inspect_quarantine(train + test, args, purpose="audit_only")
    else:
        quarantine = _require_quarantine(
            train + test,
            args,
            purpose="development_evaluation",
        )
    report = audit_leakage(train, test)
    value = report.as_dict()
    value["quarantine"] = quarantine.as_dict()
    if args.output is not None:
        if not _target_is_clear(args.output, args.force):
            return 1
        write_json(args.output, value)
    _print_json(value)
    return 2 if report.has_leakage else 0


def _command_baseline(args: argparse.Namespace) -> int:
    train = read_jsonl(args.train)
    test = read_jsonl(args.test)
    train_quarantine = _require_quarantine(train, args, purpose="training")
    test_quarantine = _require_quarantine(
        test,
        args,
        purpose="development_evaluation",
    )
    model = UnigramBaseline() if args.model == "unigram" else AddOneNGramBaseline(order=args.order)
    model.fit(train)
    result = {
        "model": args.model,
        "order": args.order if args.model == "ngram" else 1,
        "vocabulary_size": len(model.vocabulary),
        "heldout": model.score_heldout(test),
        "missing_sign": score_missing_signs(model, test),
        "scientific_scope": "structural baseline only; no phonetic or semantic inference",
        "quarantine": {
            "train": train_quarantine.as_dict(),
            "test": test_quarantine.as_dict(),
        },
    }
    value = _jsonable(result)
    if args.output is not None:
        if not _target_is_clear(args.output, args.force):
            return 1
        write_json(args.output, value)
    _print_json(value)
    return 0


def _command_control_shuffle(args: argparse.Namespace) -> int:
    if not _target_is_clear(args.output, args.force):
        return 1
    records = read_jsonl(args.corpus)
    quarantine = _require_quarantine(records, args, purpose="corpus_ingestion")
    controls = global_sign_shuffle(records, seed=args.seed)
    write_jsonl(args.output, controls)
    _print_json(
        {
            "written": True,
            "output": str(args.output),
            "artifacts": len(controls),
            "seed": args.seed,
            "control": "global_sign_shuffle",
            "quarantine": quarantine.as_dict(),
        }
    )
    return 0


def _command_null_evaluate(args: argparse.Namespace) -> int:
    train = read_jsonl(args.train)
    test = read_jsonl(args.test)
    train_quarantine = _require_quarantine(train, args, purpose="training")
    test_quarantine = _require_quarantine(
        test,
        args,
        purpose="development_evaluation",
    )
    value = evaluate_shuffle_null(
        train,
        test,
        order=args.order,
        runs=args.runs,
        seed=args.seed,
    )
    value["quarantine"] = {
        "train": train_quarantine.as_dict(),
        "test": test_quarantine.as_dict(),
    }
    if args.output is not None:
        if not _target_is_clear(args.output, args.force):
            return 1
        write_json(args.output, value)
    _print_json(value)
    return 0


def _command_treewidth_audit(args: argparse.Namespace) -> int:
    records = read_jsonl(args.corpus)
    quarantine = _require_quarantine(
        records,
        args,
        purpose="development_evaluation",
    )
    value = evaluate_treewidth_nulls(
        records,
        runs=args.runs,
        seed=args.seed,
        sequence_unit=args.sequence_unit,
        min_length=args.min_length,
    )
    value["input"] = {
        "corpus_sha256": corpus_digest(records),
        "artifact_count": len(records),
        "quarantine": quarantine.as_dict(),
    }
    if args.output is not None:
        if not _target_is_clear(args.output, args.force):
            return 1
        write_json(args.output, value)
    _print_json(value)
    return 0


def _command_manifest(args: argparse.Namespace) -> int:
    records = read_jsonl(args.corpus)
    quarantine = _require_quarantine(records, args, purpose="corpus_ingestion")
    sources = read_json(args.sources) if args.sources is not None else None
    value = build_manifest(
        records,
        schema_version=SCHEMA_VERSION,
        source_registry=sources,
    )
    value["quarantine"] = quarantine.as_dict()
    if args.output is not None:
        if not _target_is_clear(args.output, args.force):
            return 1
        write_json(args.output, value)
    _print_json(value)
    return 0


def _benchmark_definition_arguments(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "corpus_path": args.corpus,
        "split_dir": args.split_dir,
        "evaluator_config_path": args.evaluator_config,
        "evaluator_files": args.evaluator_file,
        "environment_lock_path": args.environment_lock,
        "project_manifest_path": args.project_manifest,
        "artifact_schema_path": args.artifact_schema,
        "source_registry_path": args.source_registry,
        "source_schema_path": args.source_schema,
        "quarantine_registry_path": args.quarantine_registry,
        "quarantine_schema_path": args.quarantine_schema,
        "split_schema_path": args.split_schema,
        "evaluator_schema_path": args.evaluator_schema,
        "benchmark_lock_schema_path": args.benchmark_lock_schema,
    }


def _command_lock_benchmark(args: argparse.Namespace) -> int:
    if not _target_is_clear(args.output, args.force):
        return 1
    definition = build_benchmark_definition(
        **_benchmark_definition_arguments(args),
        created_by=args.created_by,
        created_at=args.created_at,
    )
    schema_issues = validate_schema_instance(
        definition,
        args.benchmark_lock_schema,
    )
    if schema_issues:
        _print_json(
            {
                "valid": False,
                "written": False,
                "issues": [issue.as_dict() for issue in schema_issues],
            }
        )
        return 2
    write_json(args.output, definition)
    _print_json(
        {
            "valid": True,
            "written": True,
            "output": str(args.output),
            "definition_id": definition["definition_id"],
            "definition_sha256": definition["definition_sha256"],
            "claim_class": definition["assurance"]["claim_class"],
            "blind_claim_allowed": False,
            "final_evaluation_eligible": False,
            "externally_anchored": False,
        }
    )
    return 0


def _command_verify_benchmark_lock(args: argparse.Namespace) -> int:
    try:
        definition = read_json(args.lock)
        if not isinstance(definition, dict):
            raise BenchmarkLockError("benchmark lock must be a JSON object")
        schema_issues = validate_schema_instance(
            definition,
            args.benchmark_lock_schema,
        )
        if schema_issues:
            _print_json(
                {
                    "valid": False,
                    "self_consistent": False,
                    "externally_anchored": False,
                    "issues": [issue.as_dict() for issue in schema_issues],
                }
            )
            return 2
        report = verify_benchmark_definition(
            definition,
            **_benchmark_definition_arguments(args),
            expected_definition_sha256=args.expected_definition_sha256,
        )
    except (OSError, SchemaDependencyMissing, ValueError) as error:
        _print_json(
            {
                "valid": False,
                "self_consistent": False,
                "externally_anchored": False,
                "error": str(error),
            }
        )
        return 2
    _print_json(report.as_dict())
    return 0 if report.valid else 2


def _submission_assurance_output() -> dict[str, bool | str]:
    return {
        "claim_class": "submission_content_commitment",
        "blind_claim_allowed": False,
        "final_evaluation_eligible": False,
        "externally_anchored": False,
        "custody_attested": False,
        "trusted_timestamp_attested": False,
        "authorship_attested": False,
        "access_history_attested": False,
        "confidentiality_attested": False,
        "runtime_isolation_attested": False,
        "execution_result_attested": False,
        "verification_scope": "point_in_time_non_atomic_filesystem_checks",
        "postconditions_atomic": False,
        "future_immutability_attested": False,
    }


@dataclass(frozen=True)
class _PinnedSubmissionOutput:
    root_path: Path
    requested_path: Path
    destination_name: str
    root_descriptor: int
    parent_descriptor: int
    root_identity: tuple[int, int]


@dataclass(frozen=True)
class _SubmissionPublicationResult:
    published: bool
    published_identity: tuple[int, int] | None
    content_verified: bool
    durability_confirmed: bool
    boundary_preserved: bool
    requested_path_verified: bool
    error: str | None


_SUBMISSION_LINK_DIR_FD_SUPPORTED = (
    os.link in os.supports_dir_fd
    and os.link in os.supports_follow_symlinks
    and os.unlink in os.supports_dir_fd
)


def _submission_directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )


def _directory_fd_is_within(
    directory_descriptor: int,
    ancestor_identity: tuple[int, int],
) -> bool:
    current_descriptor = os.dup(directory_descriptor)
    os.set_inheritable(current_descriptor, False)
    try:
        for _ in range(1024):
            current = os.fstat(current_descriptor)
            current_identity = (current.st_dev, current.st_ino)
            if current_identity == ancestor_identity:
                return True
            parent_descriptor = os.open(
                "..",
                _submission_directory_flags(),
                dir_fd=current_descriptor,
            )
            parent = os.fstat(parent_descriptor)
            parent_identity = (parent.st_dev, parent.st_ino)
            os.close(current_descriptor)
            current_descriptor = parent_descriptor
            if parent_identity == current_identity:
                return False
    finally:
        os.close(current_descriptor)
    raise SubmissionCommitmentError("output directory ancestry exceeds the safety limit")


def _submission_destination_exists(target: _PinnedSubmissionOutput) -> bool:
    try:
        os.stat(
            target.destination_name,
            dir_fd=target.parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return False
    return True


def _assert_pinned_submission_boundary(target: _PinnedSubmissionOutput) -> None:
    root_metadata = os.fstat(target.root_descriptor)
    if (
        not stat.S_ISDIR(root_metadata.st_mode)
        or (root_metadata.st_dev, root_metadata.st_ino) != target.root_identity
    ):
        raise SubmissionCommitmentError("pinned submission root changed identity")
    try:
        root_namespace = target.root_path.lstat()
    except OSError as error:
        raise SubmissionCommitmentError(
            "submission root namespace changed before output publication"
        ) from error
    if (
        not stat.S_ISDIR(root_namespace.st_mode)
        or (root_namespace.st_dev, root_namespace.st_ino) != target.root_identity
    ):
        raise SubmissionCommitmentError(
            "submission root namespace changed before output publication"
        )
    parent_metadata = os.fstat(target.parent_descriptor)
    if not stat.S_ISDIR(parent_metadata.st_mode):
        raise SubmissionCommitmentError("pinned output parent changed type")
    if _directory_fd_is_within(target.parent_descriptor, target.root_identity):
        raise SubmissionCommitmentError(
            "submission commitment output must be outside the committed tree"
        )


def _requested_submission_metadata(
    target: _PinnedSubmissionOutput,
    expected_identity: tuple[int, int],
) -> os.stat_result:
    requested_parent_descriptor: int | None = None
    try:
        requested_parent_path = target.requested_path.parent.resolve(strict=True)
        requested_parent_descriptor = os.open(
            requested_parent_path,
            _submission_directory_flags(),
        )
        requested_parent = os.fstat(requested_parent_descriptor)
        pinned_parent = os.fstat(target.parent_descriptor)
        if _directory_fd_is_within(
            requested_parent_descriptor,
            target.root_identity,
        ):
            raise SubmissionCommitmentError(
                "requested output parent moved inside the committed tree"
            )
        if (
            requested_parent.st_dev,
            requested_parent.st_ino,
        ) != (
            pinned_parent.st_dev,
            pinned_parent.st_ino,
        ):
            raise SubmissionCommitmentError(
                "requested output parent no longer names the pinned directory"
            )
        requested_metadata = os.stat(
            target.destination_name,
            dir_fd=requested_parent_descriptor,
            follow_symlinks=False,
        )
        path_metadata = target.requested_path.lstat()
        if (
            requested_metadata.st_dev,
            requested_metadata.st_ino,
        ) != expected_identity or (
            path_metadata.st_dev,
            path_metadata.st_ino,
        ) != expected_identity:
            raise SubmissionCommitmentError(
                "requested output path no longer names the published commitment"
            )
        return requested_metadata
    except (OSError, RuntimeError) as error:
        raise SubmissionCommitmentError(
            "cannot verify the requested output path against its pinned directory"
        ) from error
    finally:
        if requested_parent_descriptor is not None:
            os.close(requested_parent_descriptor)


@contextmanager
def _pinned_submission_output(
    root: Path,
    output: Path,
) -> Iterator[_PinnedSubmissionOutput]:
    destination_name = output.name
    if (
        not destination_name
        or destination_name in {".", ".."}
        or "/" in destination_name
        or "\x00" in destination_name
    ):
        raise SubmissionCommitmentError("invalid submission commitment output filename")
    try:
        root_before = root.lstat()
    except OSError as error:
        raise SubmissionCommitmentError(f"cannot stat submission root: {error}") from error
    if stat.S_ISLNK(root_before.st_mode) or not stat.S_ISDIR(root_before.st_mode):
        raise SubmissionCommitmentError("submission root must be a real directory")

    root_descriptor: int | None = None
    parent_descriptor: int | None = None
    try:
        root_descriptor = os.open(root, _submission_directory_flags())
        root_opened = os.fstat(root_descriptor)
        if _stat_fingerprint(root_opened) != _stat_fingerprint(root_before):
            raise SubmissionCommitmentError(
                "submission root changed while pinning output boundaries"
            )
        parent_path = output.parent.resolve(strict=True)
        parent_descriptor = os.open(parent_path, _submission_directory_flags())
        target = _PinnedSubmissionOutput(
            root_path=root,
            requested_path=output,
            destination_name=destination_name,
            root_descriptor=root_descriptor,
            parent_descriptor=parent_descriptor,
            root_identity=(root_opened.st_dev, root_opened.st_ino),
        )
        _assert_pinned_submission_boundary(target)
        if _submission_destination_exists(target):
            raise FileExistsError(
                errno.EEXIST,
                os.strerror(errno.EEXIST),
                str(output),
            )
        yield target
    finally:
        if parent_descriptor is not None:
            os.close(parent_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)


def _read_exact_descriptor_bytes(descriptor: int, expected: bytes) -> bool:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    byte_count = 0
    while True:
        chunk = os.read(descriptor, min(1024 * 1024, len(expected) + 1 - byte_count))
        if not chunk:
            break
        chunks.append(chunk)
        byte_count += len(chunk)
        if byte_count > len(expected):
            return False
    return b"".join(chunks) == expected


def _verify_final_published_submission(
    target: _PinnedSubmissionOutput,
    *,
    expected_identity: tuple[int, int],
    expected_bytes: bytes,
) -> None:
    descriptor: int | None = None
    try:
        _assert_pinned_submission_boundary(target)
        descriptor = os.open(
            target.destination_name,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=target.parent_descriptor,
        )
        before = os.fstat(descriptor)
        if (
            (before.st_dev, before.st_ino) != expected_identity
            or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size != len(expected_bytes)
            or stat.S_IMODE(before.st_mode) != 0o600
            or _descriptor_has_extended_acl(descriptor)
            or not _read_exact_descriptor_bytes(descriptor, expected_bytes)
        ):
            raise SubmissionCommitmentError(
                "published commitment failed the final exact-byte or metadata check"
            )
        _requested_submission_metadata(target, expected_identity)
        pinned_namespace = os.stat(
            target.destination_name,
            dir_fd=target.parent_descriptor,
            follow_symlinks=False,
        )
        after = os.fstat(descriptor)
        if (
            _stat_fingerprint(after) != _stat_fingerprint(before)
            or _stat_fingerprint(pinned_namespace) != _stat_fingerprint(before)
            or _descriptor_has_extended_acl(descriptor)
            or not _read_exact_descriptor_bytes(descriptor, expected_bytes)
        ):
            raise SubmissionCommitmentError(
                "published commitment changed during the final postcondition check"
            )
        _requested_submission_metadata(target, expected_identity)
        _assert_pinned_submission_boundary(target)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _unlink_submission_staging_if_same(
    parent_descriptor: int,
    name: str,
    identity: tuple[int, int],
) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return
    if (metadata.st_dev, metadata.st_ino) == identity:
        os.unlink(name, dir_fd=parent_descriptor)


def _publish_submission_json_no_replace(
    target: _PinnedSubmissionOutput,
    value: dict[str, Any],
) -> _SubmissionPublicationResult:
    if not _SUBMISSION_LINK_DIR_FD_SUPPORTED:
        raise SubmissionCommitmentError(
            "atomic descriptor-relative submission publication is unsupported"
        )
    raw_bytes = encode_json(value)
    staging_name = f".submission-commitment-{secrets.token_hex(16)}.tmp"
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    staging_identity: tuple[int, int] | None = None
    published = False
    content_verified = False
    boundary_preserved = False
    requested_path_verified = False
    result: _SubmissionPublicationResult | None = None
    cleanup_errors: list[str] = []
    try:
        _assert_pinned_submission_boundary(target)
        if _submission_destination_exists(target):
            raise FileExistsError(
                errno.EEXIST,
                os.strerror(errno.EEXIST),
                str(target.requested_path),
            )
        descriptor = os.open(
            staging_name,
            flags,
            0o600,
            dir_fd=target.parent_descriptor,
        )
        os.fchmod(descriptor, 0o600)
        offset = 0
        while offset < len(raw_bytes):
            written = os.write(descriptor, raw_bytes[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "short submission commitment write")
            offset += written
        os.fsync(descriptor)
        staged = os.fstat(descriptor)
        staging_identity = (staged.st_dev, staged.st_ino)
        if (
            not stat.S_ISREG(staged.st_mode)
            or staged.st_nlink != 1
            or staged.st_size != len(raw_bytes)
            or stat.S_IMODE(staged.st_mode) != 0o600
            or _descriptor_has_extended_acl(descriptor)
            or not _read_exact_descriptor_bytes(descriptor, raw_bytes)
        ):
            raise OSError(errno.EIO, "submission commitment staging verification failed")
        stable_staged = os.fstat(descriptor)
        if _stat_fingerprint(stable_staged) != _stat_fingerprint(staged):
            raise OSError(errno.EIO, "submission commitment staging file changed")

        _assert_pinned_submission_boundary(target)
        if _submission_destination_exists(target):
            raise FileExistsError(
                errno.EEXIST,
                os.strerror(errno.EEXIST),
                str(target.requested_path),
            )
        os.link(
            staging_name,
            target.destination_name,
            src_dir_fd=target.parent_descriptor,
            dst_dir_fd=target.parent_descriptor,
            follow_symlinks=False,
        )
        published = True
        linked = os.stat(
            target.destination_name,
            dir_fd=target.parent_descriptor,
            follow_symlinks=False,
        )
        if (
            (linked.st_dev, linked.st_ino) != staging_identity
            or not stat.S_ISREG(linked.st_mode)
            or linked.st_nlink != 2
            or _descriptor_has_extended_acl(descriptor)
            or not _read_exact_descriptor_bytes(descriptor, raw_bytes)
        ):
            raise OSError(
                errno.EIO,
                "published commitment does not match the pinned staging bytes",
            )
        _unlink_submission_staging_if_same(
            target.parent_descriptor,
            staging_name,
            staging_identity,
        )
        final_metadata = os.stat(
            target.destination_name,
            dir_fd=target.parent_descriptor,
            follow_symlinks=False,
        )
        if (
            (final_metadata.st_dev, final_metadata.st_ino) != staging_identity
            or final_metadata.st_nlink != 1
            or _descriptor_has_extended_acl(descriptor)
            or not _read_exact_descriptor_bytes(descriptor, raw_bytes)
        ):
            raise OSError(
                errno.EIO,
                "published commitment failed final exact-byte verification",
            )
        content_verified = True
        _assert_pinned_submission_boundary(target)
        boundary_preserved = True
        _requested_submission_metadata(target, staging_identity)
        requested_path_verified = True
        os.fsync(target.parent_descriptor)
        final_metadata = os.stat(
            target.destination_name,
            dir_fd=target.parent_descriptor,
            follow_symlinks=False,
        )
        final_requested_metadata = _requested_submission_metadata(
            target,
            staging_identity,
        )
        if (
            (final_metadata.st_dev, final_metadata.st_ino) != staging_identity
            or final_metadata.st_nlink != 1
            or stat.S_IMODE(final_metadata.st_mode) != 0o600
            or _descriptor_has_extended_acl(descriptor)
            or (
                final_requested_metadata.st_dev,
                final_requested_metadata.st_ino,
            )
            != staging_identity
            or not _read_exact_descriptor_bytes(descriptor, raw_bytes)
        ):
            content_verified = False
            requested_path_verified = False
            raise OSError(
                errno.EIO,
                "published commitment changed during durability confirmation",
            )
        boundary_preserved = False
        _assert_pinned_submission_boundary(target)
        boundary_preserved = True
        result = _SubmissionPublicationResult(
            published=True,
            published_identity=staging_identity,
            content_verified=True,
            durability_confirmed=True,
            boundary_preserved=True,
            requested_path_verified=True,
            error=None,
        )
    except (OSError, ValueError) as error:
        if not published:
            raise
        result = _SubmissionPublicationResult(
            published=True,
            published_identity=staging_identity,
            content_verified=content_verified,
            durability_confirmed=False,
            boundary_preserved=boundary_preserved,
            requested_path_verified=requested_path_verified,
            error=str(error),
        )
    finally:
        if staging_identity is not None:
            try:
                _unlink_submission_staging_if_same(
                    target.parent_descriptor,
                    staging_name,
                    staging_identity,
                )
            except OSError as error:
                cleanup_errors.append(f"staging cleanup failed: {error}")
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                cleanup_errors.append(f"staging descriptor close failed: {error}")
    if cleanup_errors:
        if result is None:
            raise OSError(errno.EIO, "; ".join(cleanup_errors))
        result = _SubmissionPublicationResult(
            published=result.published,
            published_identity=result.published_identity,
            content_verified=result.content_verified,
            durability_confirmed=False,
            boundary_preserved=result.boundary_preserved,
            requested_path_verified=result.requested_path_verified,
            error="; ".join(
                part
                for part in (
                    result.error,
                    *cleanup_errors,
                )
                if part
            ),
        )
    assert result is not None
    return result


def _command_build_submission_commitment(args: argparse.Namespace) -> int:
    if not _target_is_clear(args.output, False):
        return 1
    publication: _SubmissionPublicationResult | None = None
    commitment: dict[str, Any] | None = None
    post_write_report = None
    final_output_matches = False
    try:
        with _pinned_submission_output(args.root, args.output) as output_target:
            commitment = build_submission_commitment(
                root=args.root,
                benchmark_definition_sha256=args.benchmark_definition_sha256,
                entrypoint=args.entrypoint,
                source_files=args.source_file,
                config_files=args.config_file,
                model_weight_files=args.model_weight_file,
                dependency_files=args.dependency_file,
                static_arguments=args.static_argument,
            )
            publication = _publish_submission_json_no_replace(
                output_target,
                commitment,
            )
            if (
                publication.content_verified
                and publication.boundary_preserved
                and publication.requested_path_verified
            ):
                post_write_report = verify_submission_commitment(
                    commitment,
                    root=args.root,
                    expected_commitment_sha256=commitment["commitment_sha256"],
                )
                if publication.published_identity is None:
                    raise SubmissionCommitmentError("published commitment identity is unavailable")
                _verify_final_published_submission(
                    output_target,
                    expected_identity=publication.published_identity,
                    expected_bytes=encode_json(commitment),
                )
                final_output_matches = True
            else:
                post_write_report = None
    except FileExistsError:
        print(
            f"refusing to overwrite existing path: {args.output}",
            file=sys.stderr,
        )
        return 1
    except (OSError, SchemaDependencyMissing, ValueError) as error:
        _print_json(
            {
                "valid": False,
                "written": bool(publication and publication.published),
                "durability_confirmed": bool(publication and publication.durability_confirmed),
                "output_content_verified": bool(publication and publication.content_verified),
                "output_boundary_preserved": bool(publication and publication.boundary_preserved),
                "final_output_matches": final_output_matches,
                "error": str(error),
                **_submission_assurance_output(),
            }
        )
        return 2
    assert publication is not None
    assert commitment is not None
    operation_valid = (
        publication.published
        and publication.content_verified
        and publication.durability_confirmed
        and publication.boundary_preserved
        and publication.requested_path_verified
        and post_write_report is not None
        and post_write_report.valid
        and final_output_matches
    )
    if not operation_valid:
        _print_json(
            {
                "valid": False,
                "commitment_valid": True,
                "written": publication.published,
                "output": str(args.output),
                "durability_confirmed": publication.durability_confirmed,
                "output_content_verified": publication.content_verified,
                "output_boundary_preserved": publication.boundary_preserved,
                "requested_path_verified": publication.requested_path_verified,
                "post_write_tree_verified": bool(post_write_report and post_write_report.valid),
                "final_output_matches": final_output_matches,
                "postcondition": "published_but_not_fully_verified",
                "error": publication.error
                or (
                    "; ".join(post_write_report.mismatches)
                    if post_write_report is not None
                    else "publication postcondition failed"
                ),
                "commitment_id": commitment["commitment_id"],
                "commitment_sha256": commitment["commitment_sha256"],
                **_submission_assurance_output(),
            }
        )
        return 2
    _print_json(
        {
            "valid": True,
            "written": True,
            "output": str(args.output),
            "durability_confirmed": publication.durability_confirmed,
            "output_content_verified": publication.content_verified,
            "output_boundary_preserved": publication.boundary_preserved,
            "requested_path_verified": publication.requested_path_verified,
            "post_write_tree_verified": True,
            "final_output_matches": True,
            "postcondition": "committed_and_verified_at_check",
            "commitment_id": commitment["commitment_id"],
            "commitment_sha256": commitment["commitment_sha256"],
            "tree_sha256": commitment["tree"]["tree_sha256"],
            "target_benchmark_definition_sha256": commitment["target"][
                "benchmark_definition_sha256"
            ],
            "entry_count": commitment["tree"]["entry_count"],
            "file_count": commitment["tree"]["file_count"],
            "directory_count": commitment["tree"]["directory_count"],
            "total_bytes": commitment["tree"]["total_bytes"],
            **_submission_assurance_output(),
        }
    )
    return 0


def _command_verify_submission_commitment(args: argparse.Namespace) -> int:
    try:
        commitment = read_submission_commitment(args.commitment)
        report = verify_submission_commitment(
            commitment,
            root=args.root,
            expected_commitment_sha256=args.expected_commitment_sha256,
        )
    except (OSError, SchemaDependencyMissing, ValueError) as error:
        _print_json(
            {
                "valid": False,
                "self_consistent": False,
                "tree_matches": False,
                "entrypoint_bound": False,
                "expected_digest_match": None,
                "error": str(error),
                **_submission_assurance_output(),
            }
        )
        return 2
    _print_json(report.as_dict())
    return 0 if report.valid else 2


def _command_sources(args: argparse.Namespace) -> int:
    registry = read_json(args.registry)
    sources = registry.get("sources", [])
    if args.status:
        sources = [
            source
            for source in sources
            if source.get("rights", {}).get("status") in set(args.status)
        ]
    _print_json(
        {
            "registry_id": registry.get("registry_id"),
            "source_count": len(sources),
            "sources": sources,
        }
    )
    return 0


def _command_research(args: argparse.Namespace) -> int:
    registry = read_json(args.registry)
    entries = registry.get("entries", [])
    if args.tier:
        entries = [entry for entry in entries if entry.get("evidence_tier") in set(args.tier)]
    if args.entity_type:
        entries = [entry for entry in entries if entry.get("entity_type") in set(args.entity_type)]
    if args.status:
        entries = [entry for entry in entries if entry.get("status") in set(args.status)]
    if args.tag:
        requested_tags = set(args.tag)
        entries = [
            entry for entry in entries if requested_tags.issubset(set(entry.get("tags", [])))
        ]
    if args.review_due is not None:
        review_cutoff = args.review_due.isoformat()
        entries = [
            entry
            for entry in entries
            if (next_review := entry.get("dates", {}).get("next_review_on")) is not None
            and next_review <= review_cutoff
        ]
    _print_json(
        {
            "registry_id": registry.get("registry_id"),
            "generated_at": registry.get("generated_at"),
            "filters": {
                "evidence_tiers": args.tier or [],
                "entity_types": args.entity_type or [],
                "statuses": args.status or [],
                "tags_all": args.tag or [],
                "review_due": args.review_due.isoformat() if args.review_due is not None else None,
            },
            "entry_count": len(entries),
            "entries": entries,
        }
    )
    return 0


def _command_museum_candidates(args: argparse.Namespace) -> int:
    if args.priority_at_most is not None and args.priority_at_most < 1:
        raise ValueError("--priority-at-most must be positive")
    registry = read_json(args.registry)
    if not isinstance(registry, dict):
        raise ValueError("museum candidate registry root must be an object")
    institutions_value = registry.get("institutions")
    if not isinstance(institutions_value, list) or any(
        not isinstance(item, dict) for item in institutions_value
    ):
        raise ValueError("museum candidate registry institutions must be objects")
    institutions: list[dict[str, Any]] = [
        dict(item) for item in institutions_value if isinstance(item, dict)
    ]
    if args.automation_class:
        selected_classes = set(args.automation_class)
        institutions = [
            item for item in institutions if item.get("automation_class") in selected_classes
        ]
    if args.country:
        selected_countries = set(args.country)
        institutions = [item for item in institutions if item.get("country") in selected_countries]
    if args.priority_at_most is not None:
        institutions = [
            item
            for item in institutions
            if isinstance(item.get("priority"), dict)
            and isinstance(item["priority"].get("rank"), int)
            and item["priority"]["rank"] <= args.priority_at_most
        ]
    if args.with_verified_candidates:
        institutions = [
            item
            for item in institutions
            if isinstance(item.get("verified_artifact_candidates"), list)
            and bool(item["verified_artifact_candidates"])
        ]
    institutions.sort(
        key=lambda item: (
            item.get("priority", {}).get("rank", sys.maxsize),
            item.get("institution_id", ""),
        )
    )
    _print_json(
        {
            "registry_id": registry.get("registry_id"),
            "generated_at": registry.get("generated_at"),
            "assessed_on": registry.get("assessed_on"),
            "global_media_gate": registry.get("global_media_gate"),
            "filters": {
                "automation_classes": args.automation_class or [],
                "countries": args.country or [],
                "priority_at_most": args.priority_at_most,
                "with_verified_candidates": args.with_verified_candidates,
            },
            "institution_count": len(institutions),
            "institutions": institutions,
        }
    )
    return 0


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected an ISO date in YYYY-MM-DD form") from error


def _rfc3339(value: str) -> str:
    if not RFC3339_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("expected a strict RFC 3339 date-time")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected an RFC 3339 date-time") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("RFC 3339 date-time must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _sha256_checksum(value: str) -> str:
    if not CHECKSUM_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("expected sha256 followed by 64 lowercase hex digits")
    return value


def _git_commit(value: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise argparse.ArgumentTypeError("expected a 40-character lowercase Git commit")
    return value


def _add_quarantine_arguments(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument(
        "--source-registry",
        type=_path,
        default=_default_source_registry(),
        help="closed source-rights registry used by the fail-closed corpus gate",
    )
    command_parser.add_argument(
        "--quarantine-registry",
        type=_path,
        default=_default_quarantine_registry(),
        help="content-addressed deny registry used by the fail-closed corpus gate",
    )


def _add_benchmark_definition_inputs(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("corpus", type=_path)
    command_parser.add_argument("split_dir", type=_path)
    command_parser.add_argument("evaluator_config", type=_path)
    command_parser.add_argument(
        "--evaluator-file",
        action="append",
        type=_path,
        required=True,
        help=(
            "exact evaluator source file to bind; repeat for every dependency "
            "(v0.1 does not attest dependency-closure completeness)"
        ),
    )
    command_parser.add_argument(
        "--environment-lock",
        type=_path,
        default=Path(__file__).resolve().parents[2] / "uv.lock",
    )
    command_parser.add_argument(
        "--project-manifest",
        type=_path,
        default=Path(__file__).resolve().parents[2] / "pyproject.toml",
    )
    command_parser.add_argument(
        "--artifact-schema",
        type=_path,
        default=_default_schema("artifact.schema.json"),
    )
    command_parser.add_argument(
        "--source-registry",
        type=_path,
        default=_default_source_registry(),
    )
    command_parser.add_argument(
        "--source-schema",
        type=_path,
        default=_default_schema("source-registry.schema.json"),
    )
    command_parser.add_argument(
        "--quarantine-registry",
        type=_path,
        default=_default_quarantine_registry(),
    )
    command_parser.add_argument(
        "--quarantine-schema",
        type=_path,
        default=_default_schema("quarantine-manifest.schema.json"),
    )
    command_parser.add_argument(
        "--split-schema",
        type=_path,
        default=_default_schema("split-manifest.schema.json"),
    )
    command_parser.add_argument(
        "--evaluator-schema",
        type=_path,
        default=_default_schema("evaluator-config.schema.json"),
    )
    command_parser.add_argument(
        "--benchmark-lock-schema",
        type=_path,
        default=_default_schema("benchmark-lock.schema.json"),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser."""

    parser = argparse.ArgumentParser(
        prog="indusbench",
        description=(
            "Rights-aware corpus validation and infrastructure for future "
            "independently custodial evaluation."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate artifact JSONL")
    validate_parser.add_argument("corpus", type=_path)
    validate_parser.add_argument("--full-schema", action="store_true")
    validate_parser.add_argument("--schema", type=_path)
    _add_quarantine_arguments(validate_parser)
    validate_parser.set_defaults(handler=_command_validate)

    kp1979_source_parser = subparsers.add_parser(
        "verify-kp1979-source",
        help="verify exact local bytes of the fixed official KP1979 corpus PDF",
    )
    kp1979_source_parser.add_argument("pdf", type=_path)
    kp1979_source_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_source_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_source_parser.set_defaults(handler=_command_verify_kp1979_source)

    kp1979_layout_parser = subparsers.add_parser(
        "audit-kp1979-layout",
        help="verify all KP1979 page pixels and run abstaining label-lattice gates",
    )
    kp1979_layout_parser.add_argument("pdf", type=_path)
    kp1979_layout_parser.add_argument(
        "page_pbm_dir",
        type=_path,
        help="physical directory containing canonical page-002.pbm through page-180.pbm",
    )
    kp1979_layout_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_layout_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_layout_parser.set_defaults(handler=_command_audit_kp1979_layout)

    kp1979_row_prepare_parser = subparsers.add_parser(
        "prepare-kp1979-row-assignment",
        help="create a private source-bound KP1979 base-row reviewer assignment",
    )
    kp1979_row_prepare_parser.add_argument("pdf", type=_path)
    kp1979_row_prepare_parser.add_argument(
        "page_pbm_dir",
        type=_path,
        help="physical directory containing canonical page-002.pbm through page-180.pbm",
    )
    kp1979_row_prepare_parser.add_argument(
        "output",
        type=_path,
        help="new 0600 assignment under a pre-existing physical 0700 directory",
    )
    kp1979_row_prepare_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_row_prepare_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_row_prepare_parser.set_defaults(handler=_command_prepare_kp1979_row_assignment)

    kp1979_row_verify_parser = subparsers.add_parser(
        "verify-kp1979-row-assignment",
        help="recompute a private KP1979 base-row reviewer assignment",
    )
    kp1979_row_verify_parser.add_argument("pdf", type=_path)
    kp1979_row_verify_parser.add_argument(
        "page_pbm_dir",
        type=_path,
        help="physical directory containing canonical page-002.pbm through page-180.pbm",
    )
    kp1979_row_verify_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical 0600 assignment under a physical owner-only directory",
    )
    kp1979_row_verify_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_row_verify_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_row_verify_parser.set_defaults(handler=_command_verify_kp1979_row_assignment)

    kp1979_sign_template_prepare_parser = subparsers.add_parser(
        "prepare-kp1979-sign-template-roster",
        help="create a private machine-provisional KP1979 sign-template roster",
    )
    kp1979_sign_template_prepare_parser.add_argument(
        "catalog",
        type=_path,
        help="canonical 0600 resolved catalog under a physical owner-only directory",
    )
    kp1979_sign_template_prepare_parser.add_argument(
        "geometry_manifest",
        type=_path,
        help="bound 0600 sign-list geometry manifest under a physical owner-only directory",
    )
    kp1979_sign_template_prepare_parser.add_argument(
        "glyph_pbm_dir",
        type=_path,
        help=(
            "physical owner-only directory containing catalog/geometry-bound provisional glyph PBMs"
        ),
    )
    kp1979_sign_template_prepare_parser.add_argument(
        "output",
        type=_path,
        help="new 0600 roster under a pre-existing physical 0700 directory",
    )
    kp1979_sign_template_prepare_parser.set_defaults(
        handler=_command_prepare_kp1979_sign_template_roster
    )

    kp1979_sign_template_verify_parser = subparsers.add_parser(
        "verify-kp1979-sign-template-roster",
        help="recompute a private machine-provisional KP1979 sign-template roster",
    )
    kp1979_sign_template_verify_parser.add_argument(
        "catalog",
        type=_path,
        help="canonical 0600 resolved catalog under a physical owner-only directory",
    )
    kp1979_sign_template_verify_parser.add_argument(
        "geometry_manifest",
        type=_path,
        help="bound 0600 sign-list geometry manifest under a physical owner-only directory",
    )
    kp1979_sign_template_verify_parser.add_argument(
        "glyph_pbm_dir",
        type=_path,
        help=(
            "physical owner-only directory containing catalog/geometry-bound provisional glyph PBMs"
        ),
    )
    kp1979_sign_template_verify_parser.add_argument(
        "roster",
        type=_path,
        help="canonical 0600 roster under a physical owner-only directory",
    )
    kp1979_sign_template_verify_parser.set_defaults(
        handler=_command_verify_kp1979_sign_template_roster
    )

    kp1979_label_reference_prepare_parser = subparsers.add_parser(
        "prepare-kp1979-label-reference-assignment",
        help="create one private, detector-free KP1979 label-reference assignment",
    )
    kp1979_label_reference_prepare_parser.add_argument("pdf", type=_path)
    kp1979_label_reference_prepare_parser.add_argument(
        "page_pbm_dir",
        type=_path,
        help="physical directory containing the canonical KP1979 page PBMs",
    )
    kp1979_label_reference_prepare_parser.add_argument(
        "output",
        type=_path,
        help="new 0600 assignment under a pre-existing physical 0700 directory",
    )
    kp1979_label_reference_prepare_parser.add_argument(
        "--partition",
        choices=("development", "future_evaluation"),
        required=True,
        help="isolated fixed six-page protocol partition",
    )
    kp1979_label_reference_prepare_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_label_reference_prepare_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_label_reference_prepare_parser.set_defaults(
        handler=_command_prepare_kp1979_label_reference_assignment
    )

    kp1979_label_reference_verify_parser = subparsers.add_parser(
        "verify-kp1979-label-reference-assignment",
        help="recompute one private, detector-free KP1979 label-reference assignment",
    )
    kp1979_label_reference_verify_parser.add_argument("pdf", type=_path)
    kp1979_label_reference_verify_parser.add_argument(
        "page_pbm_dir",
        type=_path,
        help="physical directory containing the canonical KP1979 page PBMs",
    )
    kp1979_label_reference_verify_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical 0600 assignment under a physical owner-only directory",
    )
    kp1979_label_reference_verify_parser.add_argument(
        "--partition",
        choices=("development", "future_evaluation"),
        required=True,
        help="isolated fixed six-page protocol partition",
    )
    kp1979_label_reference_verify_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_label_reference_verify_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_label_reference_verify_parser.set_defaults(
        handler=_command_verify_kp1979_label_reference_assignment
    )

    kp1979_label_reference_review_parser = subparsers.add_parser(
        "verify-kp1979-label-reference-review",
        help="verify one private KP1979 manual label-reference review",
    )
    kp1979_label_reference_review_parser.add_argument("pdf", type=_path)
    kp1979_label_reference_review_parser.add_argument(
        "page_pbm_dir",
        type=_path,
        help="physical directory containing the canonical KP1979 page PBMs",
    )
    kp1979_label_reference_review_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical 0600 assignment under a physical owner-only directory",
    )
    kp1979_label_reference_review_parser.add_argument(
        "review",
        type=_path,
        help="canonical 0600 review under a physical owner-only directory",
    )
    kp1979_label_reference_review_parser.add_argument(
        "--partition",
        choices=("development", "future_evaluation"),
        required=True,
        help="isolated fixed six-page protocol partition",
    )
    kp1979_label_reference_review_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_label_reference_review_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_label_reference_review_parser.set_defaults(
        handler=_command_verify_kp1979_label_reference_review
    )

    kp1979_machine_development_prepare_parser = subparsers.add_parser(
        "prepare-kp1979-machine-development-review",
        help=("create one private, exposed, machine-only KP1979 development geometry pass"),
    )
    kp1979_machine_development_prepare_parser.add_argument("pdf", type=_path)
    kp1979_machine_development_prepare_parser.add_argument(
        "page_pbm_dir",
        type=_path,
        help="physical directory containing the canonical KP1979 page PBMs",
    )
    kp1979_machine_development_prepare_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical development assignment under a physical owner-only directory",
    )
    kp1979_machine_development_prepare_parser.add_argument(
        "output",
        type=_path,
        help="new 0600 machine pass under a pre-existing physical 0700 directory",
    )
    kp1979_machine_development_prepare_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_machine_development_prepare_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_machine_development_prepare_parser.set_defaults(
        handler=_command_prepare_kp1979_machine_development_review
    )

    kp1979_machine_development_verify_parser = subparsers.add_parser(
        "verify-kp1979-machine-development-review",
        help=(
            "recompute one private KP1979 machine-development geometry "
            "pass without admitting it as external reference evidence"
        ),
    )
    kp1979_machine_development_verify_parser.add_argument("pdf", type=_path)
    kp1979_machine_development_verify_parser.add_argument(
        "page_pbm_dir",
        type=_path,
        help="physical directory containing the canonical KP1979 page PBMs",
    )
    kp1979_machine_development_verify_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical development assignment under a physical owner-only directory",
    )
    kp1979_machine_development_verify_parser.add_argument(
        "review",
        type=_path,
        help="canonical 0600 machine pass under a physical owner-only directory",
    )
    kp1979_machine_development_verify_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1979_contract(),
        help="closed checked-in KP1979 source contract",
    )
    kp1979_machine_development_verify_parser.add_argument(
        "--page-map",
        type=_path,
        default=_default_kp1979_page_map(),
        help="closed checked-in KP1979 native-page map",
    )
    kp1979_machine_development_verify_parser.set_defaults(
        handler=_command_verify_kp1979_machine_development_review
    )

    kp1979_synthetic_control_parser = subparsers.add_parser(
        "run-kp1979-label-lattice-synthetic-control",
        help=(
            "run the source-independent known-truth synthetic control for "
            "the frozen KP1979 V1 label-lattice detector"
        ),
    )
    kp1979_synthetic_control_parser.set_defaults(
        handler=_command_run_kp1979_label_lattice_synthetic_control
    )

    kp1982_source_parser = subparsers.add_parser(
        "verify-kp1982-source",
        help="verify exact local bytes of the fixed official KP1982 Batch 0 PDF",
    )
    kp1982_source_parser.add_argument("pdf", type=_path)
    kp1982_source_parser.add_argument(
        "--page-pbm",
        type=_path,
        nargs=2,
        metavar=("PAGE20_PBM", "PAGE21_PBM"),
        help="optional canonical PBM pages in contract order for pixel verification",
    )
    kp1982_source_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1982_contract(),
        help="closed checked-in KP1982 Batch 0 source contract",
    )
    kp1982_source_parser.set_defaults(handler=_command_verify_kp1982_source)

    kp1982_layout_parser = subparsers.add_parser(
        "propose-kp1982-layout",
        help="create a private deterministic crop proposal for KP1982 Batch 0 review",
    )
    kp1982_layout_parser.add_argument("page20_pbm", type=_path)
    kp1982_layout_parser.add_argument("page21_pbm", type=_path)
    kp1982_layout_parser.add_argument(
        "output",
        type=_path,
        help="new 0600 proposal under a pre-existing physical 0700 directory",
    )
    kp1982_layout_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1982_contract(),
        help="closed checked-in KP1982 Batch 0 source contract",
    )
    kp1982_layout_parser.add_argument(
        "--layout-seed",
        type=_path,
        default=_default_kp1982_layout_seed(),
        help="closed checked-in provisional KP1982 Batch 0 layout seed",
    )
    kp1982_layout_parser.set_defaults(handler=_command_propose_kp1982_layout)

    kp1982_layout_verify_parser = subparsers.add_parser(
        "verify-kp1982-layout",
        help="recompute a private KP1982 layout proposal from the fixed page pixels",
    )
    kp1982_layout_verify_parser.add_argument("page20_pbm", type=_path)
    kp1982_layout_verify_parser.add_argument("page21_pbm", type=_path)
    kp1982_layout_verify_parser.add_argument("proposal", type=_path)
    kp1982_layout_verify_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1982_contract(),
        help="closed checked-in KP1982 Batch 0 source contract",
    )
    kp1982_layout_verify_parser.add_argument(
        "--layout-seed",
        type=_path,
        default=_default_kp1982_layout_seed(),
        help="closed checked-in provisional KP1982 Batch 0 layout seed",
    )
    kp1982_layout_verify_parser.set_defaults(handler=_command_verify_kp1982_layout)

    kp1982_bootstrap_prepare_parser = subparsers.add_parser(
        "prepare-kp1982-bootstrap-assignment",
        help="create a private value-stripped KP1982 Batch 0 reviewer assignment",
    )
    kp1982_bootstrap_prepare_parser.add_argument("page20_pbm", type=_path)
    kp1982_bootstrap_prepare_parser.add_argument("page21_pbm", type=_path)
    kp1982_bootstrap_prepare_parser.add_argument(
        "proposal",
        type=_path,
        help="canonical 0600 layout proposal under a physical owner-only directory",
    )
    kp1982_bootstrap_prepare_parser.add_argument(
        "output",
        type=_path,
        help="new 0600 assignment under a pre-existing physical 0700 directory",
    )
    kp1982_bootstrap_prepare_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1982_contract(),
        help="closed checked-in KP1982 Batch 0 source contract",
    )
    kp1982_bootstrap_prepare_parser.add_argument(
        "--layout-seed",
        type=_path,
        default=_default_kp1982_layout_seed(),
        help="closed checked-in provisional KP1982 Batch 0 layout seed",
    )
    kp1982_bootstrap_prepare_parser.set_defaults(
        handler=_command_prepare_kp1982_bootstrap_assignment
    )

    kp1982_bootstrap_verify_parser = subparsers.add_parser(
        "verify-kp1982-bootstrap-assignment",
        help="recompute a private value-stripped KP1982 Batch 0 reviewer assignment",
    )
    kp1982_bootstrap_verify_parser.add_argument("page20_pbm", type=_path)
    kp1982_bootstrap_verify_parser.add_argument("page21_pbm", type=_path)
    kp1982_bootstrap_verify_parser.add_argument(
        "proposal",
        type=_path,
        help="canonical 0600 layout proposal under a physical owner-only directory",
    )
    kp1982_bootstrap_verify_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical 0600 assignment under a physical owner-only directory",
    )
    kp1982_bootstrap_verify_parser.add_argument(
        "--contract",
        type=_path,
        default=_default_kp1982_contract(),
        help="closed checked-in KP1982 Batch 0 source contract",
    )
    kp1982_bootstrap_verify_parser.add_argument(
        "--layout-seed",
        type=_path,
        default=_default_kp1982_layout_seed(),
        help="closed checked-in provisional KP1982 Batch 0 layout seed",
    )
    kp1982_bootstrap_verify_parser.set_defaults(handler=_command_verify_kp1982_bootstrap_assignment)

    kp1982_bootstrap_review_input_parser = subparsers.add_parser(
        "verify-kp1982-bootstrap-review-input",
        help=(
            "verify a private value-stripped assignment against the fixed page pixels "
            "without supplying the layout proposal"
        ),
    )
    kp1982_bootstrap_review_input_parser.add_argument("page20_pbm", type=_path)
    kp1982_bootstrap_review_input_parser.add_argument("page21_pbm", type=_path)
    kp1982_bootstrap_review_input_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical 0600 assignment under a physical owner-only directory",
    )
    kp1982_bootstrap_review_input_parser.set_defaults(
        handler=_command_verify_kp1982_bootstrap_review_input
    )

    kp1982_bootstrap_review_parser = subparsers.add_parser(
        "verify-kp1982-bootstrap-review",
        help="verify one private independent KP1982 inventory-bootstrap review",
    )
    kp1982_bootstrap_review_parser.add_argument("page20_pbm", type=_path)
    kp1982_bootstrap_review_parser.add_argument("page21_pbm", type=_path)
    kp1982_bootstrap_review_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical 0600 assignment under a physical owner-only directory",
    )
    kp1982_bootstrap_review_parser.add_argument(
        "review",
        type=_path,
        help="independent-pass 0600 record under a physical owner-only directory",
    )
    kp1982_bootstrap_review_parser.set_defaults(handler=_command_verify_kp1982_bootstrap_review)

    kp1982_bootstrap_review_audit_parser = subparsers.add_parser(
        "audit-kp1982-bootstrap-reviews",
        help="verify two private bootstrap reviews and write a private count-bearing audit",
    )
    kp1982_bootstrap_review_audit_parser.add_argument("page20_pbm", type=_path)
    kp1982_bootstrap_review_audit_parser.add_argument("page21_pbm", type=_path)
    kp1982_bootstrap_review_audit_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical 0600 assignment under a physical owner-only directory",
    )
    kp1982_bootstrap_review_audit_parser.add_argument("left", type=_path)
    kp1982_bootstrap_review_audit_parser.add_argument("right", type=_path)
    kp1982_bootstrap_review_audit_parser.add_argument(
        "--private-report",
        type=_path,
        required=True,
        help="new 0600 no-replace report under a pre-existing physical 0700 directory",
    )
    kp1982_bootstrap_review_audit_parser.set_defaults(
        handler=_command_audit_kp1982_bootstrap_reviews
    )

    kp1982_bootstrap_adjudication_parser = subparsers.add_parser(
        "verify-kp1982-bootstrap-adjudication",
        help="verify one no-invention adjudication over exactly two private reviews",
    )
    kp1982_bootstrap_adjudication_parser.add_argument("page20_pbm", type=_path)
    kp1982_bootstrap_adjudication_parser.add_argument("page21_pbm", type=_path)
    kp1982_bootstrap_adjudication_parser.add_argument(
        "assignment",
        type=_path,
        help="canonical 0600 assignment under a physical owner-only directory",
    )
    kp1982_bootstrap_adjudication_parser.add_argument("left", type=_path)
    kp1982_bootstrap_adjudication_parser.add_argument("right", type=_path)
    kp1982_bootstrap_adjudication_parser.add_argument("adjudication", type=_path)
    kp1982_bootstrap_adjudication_parser.set_defaults(
        handler=_command_verify_kp1982_bootstrap_adjudication
    )

    transcription_audit_parser = subparsers.add_parser(
        "audit-transcription-agreement",
        help="compare two image-bound independent sign transcriptions",
    )
    transcription_audit_parser.add_argument("inventory", type=_path)
    transcription_audit_parser.add_argument("left", type=_path)
    transcription_audit_parser.add_argument("right", type=_path)
    transcription_audit_parser.add_argument(
        "--minimum-bbox-iou",
        type=float,
        default=0.5,
        help="minimum token bounding-box IoU for monotonic alignment",
    )
    transcription_audit_parser.add_argument("--inventory-schema", type=_path)
    transcription_audit_parser.add_argument("--review-schema", type=_path)
    transcription_audit_parser.add_argument(
        "--private-report",
        type=_path,
        help="optional new 0600 detailed report under a pre-existing physical 0700 directory",
    )
    transcription_audit_parser.set_defaults(handler=_command_audit_transcription_agreement)

    transcription_promote_parser = subparsers.add_parser(
        "promote-transcription",
        help="verify adjudication evidence and create one artifact observation",
    )
    transcription_promote_parser.add_argument("inventory", type=_path)
    transcription_promote_parser.add_argument("artifact_template", type=_path)
    transcription_promote_parser.add_argument("adjudication", type=_path)
    transcription_promote_parser.add_argument("output", type=_path)
    transcription_promote_parser.add_argument(
        "--review",
        action="append",
        required=True,
        type=_path,
        help="independent review file; repeat at least twice",
    )
    transcription_promote_parser.add_argument("--side-id", required=True)
    transcription_promote_parser.add_argument("--line-id", required=True)
    transcription_promote_parser.add_argument(
        "--release-scope",
        choices=("private_research",),
        default="private_research",
        help="public export is disabled until an allowlist-only exporter exists",
    )
    transcription_promote_parser.add_argument("--inventory-schema", type=_path)
    transcription_promote_parser.add_argument("--review-schema", type=_path)
    transcription_promote_parser.add_argument("--artifact-schema", type=_path)
    transcription_promote_parser.set_defaults(handler=_command_promote_transcription)

    private_readiness_parser = subparsers.add_parser(
        "audit-private-readiness",
        help=("scan a physical private corpus and emit only a fixed, count-free public summary"),
    )
    private_readiness_parser.add_argument(
        "root",
        type=_path,
        help="absolute physical owner-only corpus root; symbolic-link roots are rejected",
    )
    private_readiness_parser.add_argument(
        "--intended-use",
        required=True,
        choices=sorted(PRIVATE_READINESS_INTENDED_USES),
    )
    private_readiness_parser.add_argument(
        "--created-at",
        required=True,
        type=_rfc3339,
        help="explicit RFC 3339 time stored only in the private aggregate report",
    )
    private_policy_group = private_readiness_parser.add_mutually_exclusive_group()
    private_policy_group.add_argument(
        "--policy",
        type=_path,
        help=(
            "optional private 0600 content-bound per-file rights policy; "
            "omission always leaves readiness blocked"
        ),
    )
    private_policy_group.add_argument(
        "--policy-bundle",
        type=_path,
        help=(
            "optional private 0600 review bundle; its quarantine ledger never overrides readiness"
        ),
    )
    private_readiness_parser.add_argument(
        "--private-report",
        type=_path,
        help=("optional new aggregate-only JSON report under a pre-existing 0700 directory"),
    )
    _add_quarantine_arguments(private_readiness_parser)
    private_readiness_parser.set_defaults(handler=_command_audit_private_readiness)

    private_review_parser = subparsers.add_parser(
        "prepare-private-review",
        help=("build an atomic deny-all private policy and structural-quarantine bundle"),
    )
    private_review_parser.add_argument(
        "root",
        type=_path,
        help="absolute physical owner-only corpus root",
    )
    private_review_parser.add_argument(
        "output",
        type=_path,
        help="new 0600 bundle under a pre-existing physical 0700 directory",
    )
    private_review_parser.add_argument(
        "--created-at",
        required=True,
        type=_rfc3339,
        help="explicit RFC 3339 time stored only inside the private bundle",
    )
    private_review_parser.set_defaults(handler=_command_prepare_private_review)

    import_parser = subparsers.add_parser(
        "import-mayig",
        help="import a local mayig corpus checkout without vendoring it",
    )
    import_parser.add_argument("source", type=_path)
    import_parser.add_argument("output", type=_path)
    import_parser.add_argument("--revision")
    import_parser.add_argument("--retrieved-at")
    import_parser.add_argument("--full-schema", action="store_true")
    import_parser.add_argument("--schema", type=_path)
    import_parser.add_argument("--force", action="store_true")
    _add_quarantine_arguments(import_parser)
    import_parser.set_defaults(handler=_command_import_mayig)

    museum_parser = subparsers.add_parser(
        "intake-museum",
        help="stage item-rights evidence and untranscribed museum media",
    )
    museum_parser.add_argument(
        "output_dir",
        type=_path,
        help="new private bundle directory; existing paths are never replaced",
    )
    museum_parser.add_argument(
        "--met-object",
        action="append",
        type=int,
        metavar="OBJECT_ID",
    )
    museum_parser.add_argument(
        "--cleveland-accession",
        action="append",
        metavar="ACCESSION",
    )
    museum_parser.add_argument(
        "--cleveland-derivative",
        action="append",
        choices=("print", "full"),
        help="repeat to select derivatives; defaults to both print and full",
    )
    museum_parser.add_argument(
        "--download-media",
        action="store_true",
        help="download every enumerated image into the private bundle",
    )
    museum_parser.add_argument("--timeout", type=float, default=60.0)
    museum_parser.add_argument(
        "--max-json-bytes",
        type=int,
        default=DEFAULT_MAX_JSON_BYTES,
    )
    museum_parser.add_argument(
        "--max-total-json-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_JSON_BYTES,
    )
    museum_parser.add_argument(
        "--max-media-bytes",
        type=int,
        default=DEFAULT_MAX_MEDIA_BYTES,
    )
    museum_parser.add_argument(
        "--max-media-count",
        type=int,
        default=DEFAULT_MAX_MEDIA_COUNT,
    )
    museum_parser.add_argument(
        "--max-total-media-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_MEDIA_BYTES,
    )
    museum_parser.add_argument("--full-schema", action="store_true")
    museum_parser.add_argument("--schema", type=_path)
    museum_parser.set_defaults(handler=_command_intake_museum)

    verify_museum_parser = subparsers.add_parser(
        "verify-museum-intake",
        help="rehash and validate a private museum-intake bundle",
    )
    verify_museum_parser.add_argument("bundle_dir", type=_path)
    verify_museum_parser.add_argument(
        "--max-json-bytes",
        type=int,
        default=DEFAULT_MAX_JSON_BYTES,
    )
    verify_museum_parser.add_argument(
        "--max-total-json-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_JSON_BYTES,
    )
    verify_museum_parser.add_argument(
        "--max-media-bytes",
        type=int,
        default=DEFAULT_MAX_MEDIA_BYTES,
    )
    verify_museum_parser.add_argument(
        "--max-media-count",
        type=int,
        default=DEFAULT_MAX_MEDIA_COUNT,
    )
    verify_museum_parser.add_argument(
        "--max-total-media-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_MEDIA_BYTES,
    )
    verify_museum_parser.add_argument(
        "--expected-manifest-sha256",
        type=_sha256_checksum,
        help="optional trusted digest supplied from outside the bundle",
    )
    verify_museum_parser.add_argument(
        "--prepare-review",
        type=_path,
        help="atomically create a private catalog-blind review packet after verification",
    )
    verify_museum_parser.add_argument(
        "--review-subject-schema",
        type=_path,
        help="override the catalog-blind review-subject schema",
    )
    verify_museum_parser.add_argument("--full-schema", action="store_true")
    verify_museum_parser.add_argument("--schema", type=_path)
    verify_museum_parser.set_defaults(handler=_command_verify_museum_intake)

    prepare_review_parser = subparsers.add_parser(
        "prepare-museum-review",
        help="verify museum intake and create a private catalog-blind review packet",
    )
    prepare_review_parser.add_argument("bundle_dir", type=_path)
    prepare_review_parser.add_argument("prepare_review", type=_path, metavar="output_dir")
    prepare_review_parser.add_argument(
        "--max-json-bytes",
        type=int,
        default=DEFAULT_MAX_JSON_BYTES,
    )
    prepare_review_parser.add_argument(
        "--max-total-json-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_JSON_BYTES,
    )
    prepare_review_parser.add_argument(
        "--max-media-bytes",
        type=int,
        default=DEFAULT_MAX_MEDIA_BYTES,
    )
    prepare_review_parser.add_argument(
        "--max-media-count",
        type=int,
        default=DEFAULT_MAX_MEDIA_COUNT,
    )
    prepare_review_parser.add_argument(
        "--max-total-media-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_MEDIA_BYTES,
    )
    prepare_review_parser.add_argument(
        "--expected-manifest-sha256",
        type=_sha256_checksum,
        help="optional trusted digest supplied from outside the bundle",
    )
    prepare_review_parser.add_argument(
        "--schema",
        type=_path,
        help="override the museum-intake schema",
    )
    prepare_review_parser.add_argument(
        "--review-subject-schema",
        type=_path,
        help="override the catalog-blind review-subject schema",
    )
    prepare_review_parser.set_defaults(
        handler=_command_verify_museum_intake,
        full_schema=True,
    )

    verify_review_parser = subparsers.add_parser(
        "verify-museum-review",
        help="rehash and validate a private catalog-blind museum review packet",
    )
    verify_review_parser.add_argument("packet_dir", type=_path)
    verify_review_parser.add_argument(
        "--max-json-bytes",
        type=int,
        default=DEFAULT_MAX_JSON_BYTES,
    )
    verify_review_parser.add_argument(
        "--max-total-json-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_JSON_BYTES,
    )
    verify_review_parser.add_argument(
        "--max-media-bytes",
        type=int,
        default=DEFAULT_MAX_MEDIA_BYTES,
    )
    verify_review_parser.add_argument(
        "--max-media-count",
        type=int,
        default=DEFAULT_MAX_MEDIA_COUNT,
    )
    verify_review_parser.add_argument(
        "--max-total-media-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_MEDIA_BYTES,
    )
    verify_review_parser.add_argument(
        "--review-subject-schema",
        type=_path,
        help="override the catalog-blind review-subject schema",
    )
    verify_review_parser.add_argument(
        "--expected-packet-manifest-sha256",
        type=_sha256_checksum,
        help="optional trusted digest supplied from outside the packet",
    )
    verify_review_parser.set_defaults(handler=_command_verify_museum_review)

    seal_review_parser = subparsers.add_parser(
        "seal-museum-review",
        help="validate and atomically append one human review to a private ledger",
    )
    seal_review_parser.add_argument("packet_dir", type=_path)
    seal_review_parser.add_argument("ledger_dir", type=_path)
    seal_review_parser.add_argument("draft", type=_path)
    seal_review_parser.add_argument(
        "--max-json-bytes",
        type=int,
        default=DEFAULT_MAX_JSON_BYTES,
    )
    seal_review_parser.add_argument(
        "--max-total-json-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_JSON_BYTES,
    )
    seal_review_parser.add_argument(
        "--max-media-bytes",
        type=int,
        default=DEFAULT_MAX_MEDIA_BYTES,
    )
    seal_review_parser.add_argument(
        "--max-media-count",
        type=int,
        default=DEFAULT_MAX_MEDIA_COUNT,
    )
    seal_review_parser.add_argument(
        "--max-total-media-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_MEDIA_BYTES,
    )
    seal_review_parser.add_argument(
        "--max-review-count",
        type=int,
        default=MUSEUM_MAX_SEALED_REVIEW_COUNT,
    )
    seal_review_parser.add_argument(
        "--expected-packet-manifest-sha256",
        type=_sha256_checksum,
        help="optional trusted digest supplied from outside the packet",
    )
    seal_review_parser.add_argument(
        "--review-subject-schema",
        type=_path,
        help="override the catalog-blind review-subject schema",
    )
    seal_review_parser.add_argument(
        "--review-schema",
        type=_path,
        help="override the sealed human-review schema",
    )
    seal_review_parser.add_argument(
        "--review-ledger-schema",
        type=_path,
        help="override the private review-ledger manifest schema",
    )
    seal_review_parser.set_defaults(handler=_command_seal_museum_review)

    verify_review_ledger_parser = subparsers.add_parser(
        "verify-museum-review-ledger",
        help="rehash and validate a packet-bound append-only human-review ledger",
    )
    verify_review_ledger_parser.add_argument("packet_dir", type=_path)
    verify_review_ledger_parser.add_argument("ledger_dir", type=_path)
    verify_review_ledger_parser.add_argument(
        "--max-json-bytes",
        type=int,
        default=DEFAULT_MAX_JSON_BYTES,
    )
    verify_review_ledger_parser.add_argument(
        "--max-total-json-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_JSON_BYTES,
    )
    verify_review_ledger_parser.add_argument(
        "--max-media-bytes",
        type=int,
        default=DEFAULT_MAX_MEDIA_BYTES,
    )
    verify_review_ledger_parser.add_argument(
        "--max-media-count",
        type=int,
        default=DEFAULT_MAX_MEDIA_COUNT,
    )
    verify_review_ledger_parser.add_argument(
        "--max-total-media-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_MEDIA_BYTES,
    )
    verify_review_ledger_parser.add_argument(
        "--max-review-count",
        type=int,
        default=MUSEUM_MAX_SEALED_REVIEW_COUNT,
    )
    verify_review_ledger_parser.add_argument(
        "--expected-packet-manifest-sha256",
        type=_sha256_checksum,
        help="optional trusted digest supplied from outside the packet",
    )
    verify_review_ledger_parser.add_argument(
        "--review-subject-schema",
        type=_path,
        help="override the catalog-blind review-subject schema",
    )
    verify_review_ledger_parser.add_argument(
        "--review-schema",
        type=_path,
        help="override the sealed human-review schema",
    )
    verify_review_ledger_parser.add_argument(
        "--review-ledger-schema",
        type=_path,
        help="override the private review-ledger manifest schema",
    )
    verify_review_ledger_parser.set_defaults(handler=_command_verify_museum_review_ledger)

    penn_metadata_parser = subparsers.add_parser(
        "parse-penn-metadata",
        help="validate a local official Penn CSV and write an image-free candidate snapshot",
    )
    penn_metadata_parser.add_argument("csv", type=_path)
    penn_metadata_parser.add_argument("output", type=_path)
    penn_metadata_parser.add_argument(
        "--retrieved-at",
        type=_rfc3339,
        required=True,
        help="UTC retrieval time for the exact local CSV bytes",
    )
    penn_metadata_parser.add_argument("--etag")
    penn_metadata_parser.add_argument("--last-modified")
    penn_metadata_parser.add_argument(
        "--source-last-updated",
        type=_iso_date,
        metavar="YYYY-MM-DD",
    )
    penn_metadata_parser.add_argument(
        "--expected-sha256",
        type=_sha256_checksum,
        help="optional trusted digest supplied from outside the local CSV",
    )
    penn_metadata_parser.add_argument(
        "--max-csv-bytes",
        type=int,
        default=PENN_MAX_CSV_BYTES,
    )
    penn_metadata_parser.add_argument(
        "--schema",
        type=_path,
        help="override the closed Penn metadata snapshot schema",
    )
    penn_metadata_parser.set_defaults(handler=_command_parse_penn_metadata)

    penn_context_parser = subparsers.add_parser(
        "derive-penn-context-anchors",
        help=(
            "revalidate a Penn metadata snapshot against its exact CSV and write "
            "an image-free context-anchor registry"
        ),
    )
    penn_context_parser.add_argument("snapshot", type=_path)
    penn_context_parser.add_argument("csv", type=_path)
    penn_context_parser.add_argument("output", type=_path)
    penn_context_parser.add_argument(
        "--expected-source-sha256",
        type=_sha256_checksum,
        help="optional trusted digest supplied from outside the snapshot and local CSV",
    )
    penn_context_parser.add_argument(
        "--max-snapshot-bytes",
        type=int,
        default=PENN_MAX_SNAPSHOT_BYTES,
    )
    penn_context_parser.add_argument(
        "--max-csv-bytes",
        type=int,
        default=PENN_MAX_CSV_BYTES,
    )
    penn_context_parser.add_argument(
        "--snapshot-schema",
        type=_path,
        help="override the closed Penn metadata snapshot schema",
    )
    penn_context_parser.add_argument(
        "--schema",
        type=_path,
        help="override the closed context-anchor registry schema",
    )
    penn_context_parser.set_defaults(handler=_command_derive_penn_context_anchors)

    identifiability_parser = subparsers.add_parser(
        "synthetic-identifiability-gate",
        help=(
            "run the project-authored known-truth stress test; this is not "
            "an Indus decipherment result"
        ),
    )
    identifiability_parser.add_argument("--seed", type=int, default=0)
    identifiability_parser.add_argument("--family-count", type=int, default=96)
    identifiability_parser.add_argument("--runs", type=int, default=99)
    identifiability_parser.add_argument(
        "--null-seed",
        type=int,
        help="optional first family-permutation seed; defaults to --seed",
    )
    identifiability_parser.add_argument(
        "--anchor-free",
        action="store_true",
        help="demonstrate that named classes are not identifiable without train-side anchors",
    )
    identifiability_parser.add_argument(
        "--require-go",
        action="store_true",
        help="return status 2 unless the report's gate_status is go; useful for CI",
    )
    identifiability_parser.set_defaults(handler=_command_synthetic_identifiability_gate)

    oracc_ed3b_source_parser = subparsers.add_parser(
        "verify-oracc-ed3b-source",
        help=(
            "qualify the exact pinned ORACC ED3b archive as a reserved external "
            "feature-safety-exposed prospective validation source; this does not run a model"
        ),
    )
    oracc_ed3b_source_parser.add_argument(
        "archive",
        type=_path,
        help="local exact archive bytes; the command never downloads source data",
    )
    oracc_ed3b_source_parser.add_argument(
        "--protocol",
        type=_path,
        default=_default_oracc_ed3b_source_protocol(),
        help="exact pre-model-fitting-frozen ORACC ED3b validation-source protocol JSON",
    )
    oracc_ed3b_source_parser.add_argument(
        "--source-freeze-commit",
        required=True,
        type=_git_commit,
        help=(
            "caller-declared 40-character lowercase Git commit containing the "
            "source verifier and protocol; the command does not independently attest it"
        ),
    )
    oracc_ed3b_source_parser.add_argument(
        "--output",
        type=_path,
        help=(
            "optional new no-replace aggregate source receipt; no raw corpus record "
            "or scientific performance metric is written"
        ),
    )
    oracc_ed3b_source_parser.set_defaults(handler=_command_verify_oracc_ed3b_source)

    mtaac_control_parser = subparsers.add_parser(
        "evaluate-mtaac-control",
        help=(
            "evaluate the exact pinned MTAAC archive under the frozen "
            "known-script protocol; this is not an Indus result"
        ),
    )
    mtaac_control_parser.add_argument(
        "archive",
        type=_path,
        help="local exact archive bytes; the command never downloads source data",
    )
    mtaac_control_parser.add_argument(
        "--protocol",
        type=_path,
        default=_default_mtaac_control_protocol(),
        help="exact pre-result-frozen MTAAC protocol JSON",
    )
    mtaac_control_parser.add_argument(
        "--pre-result-code-commit",
        required=True,
        type=_git_commit,
        help=(
            "caller-declared 40-character lowercase Git commit containing the "
            "implementation and protocol; the command does not independently attest it"
        ),
    )
    mtaac_control_parser.add_argument(
        "--anchor-free",
        action="store_true",
        help="emit the named-class non-identifiability result without F1 or null metrics",
    )
    mtaac_control_parser.add_argument(
        "--require-go",
        action="store_true",
        help="return status 2 unless the terminal_status is go",
    )
    mtaac_control_parser.add_argument(
        "--output",
        type=_path,
        help="optional new no-replace aggregate JSON report; raw corpus rows are never written",
    )
    mtaac_control_parser.set_defaults(handler=_command_evaluate_mtaac_control)

    smithsonian_metadata_parser = subparsers.add_parser(
        "parse-smithsonian-metadata",
        help=(
            "validate one line from a local official Smithsonian AWS JSONL "
            "container without fetching media"
        ),
    )
    smithsonian_metadata_parser.add_argument("jsonl", type=_path)
    smithsonian_metadata_parser.add_argument("output", type=_path)
    smithsonian_metadata_parser.add_argument(
        "--source-url",
        required=True,
        help="exact official Smithsonian AWS EDAN shard URL for the local bytes",
    )
    smithsonian_metadata_parser.add_argument(
        "--retrieved-at",
        type=_rfc3339,
        required=True,
        help="UTC retrieval time for the exact local JSONL bytes",
    )
    smithsonian_metadata_parser.add_argument(
        "--line-number",
        type=int,
        required=True,
        help="one-based physical JSONL line to normalize",
    )
    smithsonian_metadata_parser.add_argument("--etag")
    smithsonian_metadata_parser.add_argument("--last-modified")
    smithsonian_metadata_parser.add_argument(
        "--expected-sha256",
        type=_sha256_checksum,
        help="optional trusted digest supplied from outside the local JSONL",
    )
    smithsonian_metadata_parser.add_argument(
        "--max-jsonl-bytes",
        type=int,
        default=SMITHSONIAN_MAX_JSONL_BYTES,
    )
    smithsonian_metadata_parser.add_argument(
        "--schema",
        type=_path,
        help="override the closed Smithsonian metadata-record schema",
    )
    smithsonian_metadata_parser.set_defaults(handler=_command_parse_smithsonian_metadata)

    split_parser = subparsers.add_parser(
        "split",
        help="create a connected-component, leakage-safe public development split",
    )
    split_parser.add_argument("corpus", type=_path)
    split_parser.add_argument("output_dir", type=_path)
    split_parser.add_argument(
        "--development-fraction",
        "--test-fraction",
        dest="test_fraction",
        type=float,
        default=0.2,
        help="public development fraction; --test-fraction is a deprecated alias",
    )
    split_parser.add_argument("--seed", type=int, default=0)
    split_parser.add_argument("--created-by", default="indusbench")
    split_parser.add_argument("--force", action="store_true")
    _add_quarantine_arguments(split_parser)
    split_parser.set_defaults(handler=_command_split)

    audit_parser = subparsers.add_parser(
        "audit",
        help="audit two partitions for leakage without implying blind evaluation",
    )
    audit_parser.add_argument("train", type=_path)
    audit_parser.add_argument("test", type=_path)
    audit_parser.add_argument("--output", type=_path)
    audit_parser.add_argument("--force", action="store_true")
    audit_parser.add_argument(
        "--allow-quarantined-for-audit",
        action="store_true",
        help=(
            "inspect denied material without promoting it to corpus, training, or evaluation use"
        ),
    )
    _add_quarantine_arguments(audit_parser)
    audit_parser.set_defaults(handler=_command_audit)

    baseline_parser = subparsers.add_parser(
        "baseline",
        help="score transparent structural baselines",
    )
    baseline_parser.add_argument("train", type=_path)
    baseline_parser.add_argument("test", type=_path)
    baseline_parser.add_argument("--model", choices=("unigram", "ngram"), default="ngram")
    baseline_parser.add_argument("--order", type=int, default=2)
    baseline_parser.add_argument("--output", type=_path)
    baseline_parser.add_argument("--force", action="store_true")
    _add_quarantine_arguments(baseline_parser)
    baseline_parser.set_defaults(handler=_command_baseline)

    control_parser = subparsers.add_parser(
        "control-shuffle",
        help="create a global frequency- and length-preserving null control",
    )
    control_parser.add_argument("corpus", type=_path)
    control_parser.add_argument("output", type=_path)
    control_parser.add_argument("--seed", type=int, required=True)
    control_parser.add_argument("--force", action="store_true")
    _add_quarantine_arguments(control_parser)
    control_parser.set_defaults(handler=_command_control_shuffle)

    null_parser = subparsers.add_parser(
        "null-evaluate",
        help="compare an n-gram baseline with repeated matched sign-order shuffles",
    )
    null_parser.add_argument("train", type=_path)
    null_parser.add_argument("test", type=_path)
    null_parser.add_argument("--order", type=int, default=2)
    null_parser.add_argument("--runs", type=int, default=100)
    null_parser.add_argument("--seed", type=int, default=0)
    null_parser.add_argument("--output", type=_path)
    null_parser.add_argument("--force", action="store_true")
    _add_quarantine_arguments(null_parser)
    null_parser.set_defaults(handler=_command_null_evaluate)

    treewidth_parser = subparsers.add_parser(
        "treewidth-audit",
        help="audit sign-adjacency treewidth against explicit null models",
    )
    treewidth_parser.add_argument("corpus", type=_path)
    treewidth_parser.add_argument("--runs", type=int, default=100)
    treewidth_parser.add_argument("--seed", type=int, default=0)
    treewidth_parser.add_argument(
        "--sequence-unit",
        choices=("canonical_line", "artifact_flat"),
        default="canonical_line",
        help="preserve line boundaries or reproduce artifact-flat analyses",
    )
    treewidth_parser.add_argument(
        "--min-length",
        type=int,
        default=1,
        help="exclude sequences with fewer observed signs",
    )
    treewidth_parser.add_argument("--output", type=_path)
    treewidth_parser.add_argument("--force", action="store_true")
    _add_quarantine_arguments(treewidth_parser)
    treewidth_parser.set_defaults(handler=_command_treewidth_audit)

    manifest_parser = subparsers.add_parser(
        "manifest",
        help="fingerprint a corpus and summarize its composition",
    )
    manifest_parser.add_argument("corpus", type=_path)
    manifest_parser.add_argument("--sources", type=_path)
    manifest_parser.add_argument("--output", type=_path)
    manifest_parser.add_argument("--force", action="store_true")
    _add_quarantine_arguments(manifest_parser)
    manifest_parser.set_defaults(handler=_command_manifest)

    lock_parser = subparsers.add_parser(
        "lock-benchmark",
        help=(
            "bind exact public-development inputs in a local, explicitly unanchored definition lock"
        ),
    )
    _add_benchmark_definition_inputs(lock_parser)
    lock_parser.add_argument("output", type=_path)
    lock_parser.add_argument("--created-by", required=True)
    lock_parser.add_argument("--created-at", type=_rfc3339)
    lock_parser.add_argument("--force", action="store_true")
    lock_parser.set_defaults(handler=_command_lock_benchmark)

    verify_lock_parser = subparsers.add_parser(
        "verify-benchmark-lock",
        help="rehash and rederive every input in a public-development definition lock",
    )
    verify_lock_parser.add_argument("lock", type=_path)
    _add_benchmark_definition_inputs(verify_lock_parser)
    verify_lock_parser.add_argument(
        "--expected-definition-sha256",
        type=_sha256_checksum,
        help=(
            "digest supplied from outside the local lock; equality does not prove "
            "timestamp, custody, or blindness"
        ),
    )
    verify_lock_parser.set_defaults(handler=_command_verify_benchmark_lock)

    submission_parser = subparsers.add_parser(
        "build-submission-commitment",
        help=(
            "bind a complete submission tree without claiming trusted time, custody, "
            "blindness, execution, or results"
        ),
    )
    submission_parser.add_argument("root", type=_path)
    submission_parser.add_argument("output", type=_path)
    submission_parser.add_argument(
        "--benchmark-definition-sha256",
        type=_sha256_checksum,
        required=True,
        help=(
            "target public benchmark-definition digest, verified separately with "
            "verify-benchmark-lock, to bind into the commitment"
        ),
    )
    submission_parser.add_argument(
        "--entrypoint",
        required=True,
        help="portable relative path of the one declared entrypoint file",
    )
    submission_parser.add_argument(
        "--source-file",
        action="append",
        default=[],
        help="portable relative source path; repeat as needed (entrypoint is included)",
    )
    submission_parser.add_argument(
        "--config-file",
        action="append",
        default=[],
        help="portable relative configuration path; repeat as needed",
    )
    submission_parser.add_argument(
        "--model-weight-file",
        action="append",
        default=[],
        help="portable relative model-weight path; repeat as needed",
    )
    submission_parser.add_argument(
        "--dependency-file",
        action="append",
        default=[],
        help="portable relative dependency input or lock path; repeat as needed",
    )
    submission_parser.add_argument(
        "--static-argument",
        action="append",
        default=[],
        help=(
            "exact static argv item after the entrypoint; use "
            "--static-argument=--flag for values beginning with '-'"
        ),
    )
    submission_parser.set_defaults(handler=_command_build_submission_commitment)

    verify_submission_parser = subparsers.add_parser(
        "verify-submission-commitment",
        help="re-enumerate a complete tree and verify a local submission commitment",
    )
    verify_submission_parser.add_argument("commitment", type=_path)
    verify_submission_parser.add_argument("root", type=_path)
    verify_submission_parser.add_argument(
        "--expected-commitment-sha256",
        type=_sha256_checksum,
        help=(
            "digest supplied separately; equality does not prove trusted time, "
            "custody, or blindness"
        ),
    )
    verify_submission_parser.set_defaults(handler=_command_verify_submission_commitment)

    sources_parser = subparsers.add_parser("sources", help="inspect the source-rights registry")
    sources_parser.add_argument(
        "registry",
        nargs="?",
        type=_path,
        default=_default_source_registry(),
    )
    sources_parser.add_argument(
        "--status",
        action="append",
        choices=(
            "public_domain",
            "open_licensed",
            "permission_granted",
            "metadata_only",
            "restricted",
            "unknown",
        ),
    )
    sources_parser.set_defaults(handler=_command_sources)

    research_parser = subparsers.add_parser(
        "research",
        help="inspect the machine-readable global research evidence ledger",
    )
    research_parser.add_argument(
        "registry",
        nargs="?",
        type=_path,
        default=_default_research_registry(),
    )
    research_parser.add_argument(
        "--tier",
        action="append",
        choices=("A", "B", "C", "D", "E"),
    )
    research_parser.add_argument(
        "--type",
        dest="entity_type",
        action="append",
        choices=(
            "corpus",
            "dataset",
            "database",
            "publication",
            "preprint",
            "conference_paper",
            "software",
            "institution_or_project",
            "official_record",
            "policy_or_prize",
            "other",
        ),
    )
    research_parser.add_argument(
        "--status",
        action="append",
        choices=(
            "verified",
            "partially_verified",
            "unverified",
            "disputed",
            "superseded",
            "retracted",
        ),
    )
    research_parser.add_argument(
        "--tag",
        action="append",
        help="require a tag; repeat to require all listed tags",
    )
    research_parser.add_argument(
        "--review-due",
        type=_iso_date,
        metavar="YYYY-MM-DD",
        help="show entries whose next review is due by this date",
    )
    research_parser.set_defaults(handler=_command_research)

    museum_candidates_parser = subparsers.add_parser(
        "museum-candidates",
        help="inspect the global museum API, rights, and candidate ledger",
    )
    museum_candidates_parser.add_argument(
        "registry",
        nargs="?",
        type=_path,
        default=_default_museum_candidate_registry(),
    )
    museum_candidates_parser.add_argument(
        "--automation-class",
        action="append",
        choices=(
            "metadata_only",
            "permission_required",
            "discovery_only_no_retention",
            "watchlist_no_verified_artifact",
        ),
    )
    museum_candidates_parser.add_argument("--country", action="append")
    museum_candidates_parser.add_argument(
        "--priority-at-most",
        type=int,
        metavar="RANK",
    )
    museum_candidates_parser.add_argument(
        "--with-verified-candidates",
        action="store_true",
    )
    museum_candidates_parser.set_defaults(handler=_command_museum_candidates)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except CorpusQuarantineError as error:
        _print_json(
            {
                "blocked": True,
                "valid": False,
                "written": False,
                "quarantine": error.report.as_dict(),
            }
        )
        return 2
    except (
        OSError,
        SchemaDependencyMissing,
        ValueError,
    ) as error:
        print(f"indusbench: {error}", file=sys.stderr)
        return 1
