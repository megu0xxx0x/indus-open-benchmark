"""Append-only sealing and chain validation for private museum reviews."""

from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from indusbench.museum_review import (
    REVIEW_SCOPE,
    validate_review_submission,
    validate_subject_semantics,
)

LEDGER_SCHEMA_VERSION = "0.1.0"
LEDGER_PRIVACY_CLASSIFICATION = "private_append_only_review_ledger"
CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
STABLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


class MuseumReviewLedgerError(ValueError):
    """Raised when an append-only review ledger violates its contract."""


def build_ledger_manifest(
    *,
    packet_id: str,
    created_at: str,
    packet_manifest_sha256: str,
    reviewer_manifest_sha256: str,
) -> dict[str, Any]:
    """Build an immutable manifest for a packet-bound review ledger."""

    ledger_id = f"ledger:{packet_id.split(':', 1)[-1]}"
    manifest = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "ledger_id": ledger_id,
        "packet_id": packet_id,
        "created_at": created_at,
        "privacy_classification": LEDGER_PRIVACY_CLASSIFICATION,
        "scientific_scope": REVIEW_SCOPE,
        "source_commitment": {
            "packet_manifest_sha256": packet_manifest_sha256,
            "reviewer_manifest_sha256": reviewer_manifest_sha256,
        },
        "storage": {
            "submissions_directory": "submissions",
            "adjudications_directory": "adjudications",
            "filename_rule": "sha256-<64 lowercase hex>.json",
        },
        "append_only": True,
    }
    validate_ledger_manifest(manifest)
    return manifest


def validate_ledger_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the closed, immutable ledger manifest."""

    _require_closed_keys(
        manifest,
        {
            "schema_version",
            "ledger_id",
            "packet_id",
            "created_at",
            "privacy_classification",
            "scientific_scope",
            "source_commitment",
            "storage",
            "append_only",
        },
        "review ledger manifest",
    )
    if manifest["schema_version"] != LEDGER_SCHEMA_VERSION:
        raise MuseumReviewLedgerError("unsupported review ledger schema version")
    _require_stable_id(manifest["ledger_id"], "ledger_id")
    _require_stable_id(manifest["packet_id"], "packet_id")
    _require_canonical_utc(manifest["created_at"], "created_at")
    if manifest["privacy_classification"] != LEDGER_PRIVACY_CLASSIFICATION:
        raise MuseumReviewLedgerError("review ledger privacy classification mismatch")
    if manifest["scientific_scope"] != REVIEW_SCOPE:
        raise MuseumReviewLedgerError("review ledger scientific scope mismatch")
    if manifest["append_only"] is not True:
        raise MuseumReviewLedgerError("review ledger must be append-only")
    source = _require_mapping(manifest["source_commitment"], "source_commitment")
    _require_closed_keys(
        source,
        {"packet_manifest_sha256", "reviewer_manifest_sha256"},
        "source_commitment",
    )
    _require_checksum(
        source["packet_manifest_sha256"],
        "packet_manifest_sha256",
    )
    _require_checksum(
        source["reviewer_manifest_sha256"],
        "reviewer_manifest_sha256",
    )
    storage = _require_mapping(manifest["storage"], "storage")
    _require_closed_keys(
        storage,
        {
            "submissions_directory",
            "adjudications_directory",
            "filename_rule",
        },
        "storage",
    )
    if storage != {
        "submissions_directory": "submissions",
        "adjudications_directory": "adjudications",
        "filename_rule": "sha256-<64 lowercase hex>.json",
    }:
        raise MuseumReviewLedgerError("review ledger storage contract mismatch")


def canonical_review_bytes(review: Mapping[str, Any]) -> bytes:
    """Return the sole accepted on-disk serialization for a sealed review."""

    return (
        json.dumps(
            dict(review),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def review_digest(review: Mapping[str, Any]) -> str:
    """Return the content digest of a canonical sealed review."""

    return "sha256:" + hashlib.sha256(canonical_review_bytes(review)).hexdigest()


def review_relative_path(review: Mapping[str, Any], digest: str) -> str:
    """Return the immutable relative path for a sealed review digest."""

    _require_checksum(digest, "review digest")
    stage = review.get("review_stage")
    if stage == "independent":
        directory = "submissions"
    elif stage == "adjudication":
        directory = "adjudications"
    else:
        raise MuseumReviewLedgerError("unknown review_stage")
    return f"{directory}/sha256-{digest.removeprefix('sha256:')}.json"


def audit_review_chain(
    sealed_reviews: Mapping[str, Mapping[str, Any]],
    subjects: Sequence[Mapping[str, Any]],
    *,
    packet_id: str,
    reviewer_manifest_sha256: str,
    required_independent_reviews: int = 2,
) -> dict[str, Any]:
    """Audit immutable reviews, supersession, independence, and adjudication."""

    if required_independent_reviews < 2:
        raise MuseumReviewLedgerError("at least two independent reviews are required")
    _require_stable_id(packet_id, "packet_id")
    _require_checksum(reviewer_manifest_sha256, "reviewer_manifest_sha256")
    errors: list[str] = []
    subjects_by_id: dict[str, Mapping[str, Any]] = {}
    for index, subject in enumerate(subjects):
        try:
            validate_subject_semantics(subject)
        except ValueError as error:
            errors.append(f"subjects[{index}]: {error}")
            continue
        subject_id = subject["subject_id"]
        if subject.get("packet_id") != packet_id:
            errors.append(f"{subject_id}: subject packet_id mismatch")
        if subject_id in subjects_by_id:
            errors.append(f"duplicate subject_id: {subject_id}")
        else:
            subjects_by_id[subject_id] = subject

    valid_records: dict[str, Mapping[str, Any]] = {}
    review_id_to_digest: dict[str, str] = {}
    for digest, review in sealed_reviews.items():
        try:
            _require_checksum(digest, "sealed review digest")
        except ValueError as error:
            errors.append(str(error))
            continue
        if review_digest(review) != digest:
            errors.append(f"{digest}: canonical content digest mismatch")
            continue
        subject_id = review.get("subject_id")
        subject = subjects_by_id.get(subject_id) if isinstance(subject_id, str) else None
        if subject is None:
            errors.append(f"{digest}: review cites an unknown subject")
            continue
        try:
            validate_review_submission(review, subject=subject)
        except ValueError as error:
            errors.append(f"{digest}: {error}")
            continue
        if review.get("packet_id") != packet_id:
            errors.append(f"{digest}: review packet_id mismatch")
            continue
        if review["source_commitment"]["reviewer_manifest_sha256"] != reviewer_manifest_sha256:
            errors.append(f"{digest}: reviewer manifest commitment mismatch")
            continue
        review_id = review["review_id"]
        if review_id in review_id_to_digest:
            errors.append(f"duplicate review_id: {review_id}")
            continue
        review_id_to_digest[review_id] = digest
        valid_records[digest] = review

    review_times = {digest: _review_time(review) for digest, review in valid_records.items()}
    superseded_by: dict[str, str] = {}
    for successor_digest, successor in valid_records.items():
        target_review_id = successor["supersedes_review_id"]
        if target_review_id is None:
            continue
        edge_error_count = len(errors)
        target_digest = review_id_to_digest.get(target_review_id)
        if target_digest is None:
            errors.append(f"{successor_digest}: supersedes unknown review_id {target_review_id}")
            continue
        if successor["supersedes_review_sha256"] != target_digest:
            errors.append(f"{successor_digest}: predecessor digest commitment mismatch")
        target = valid_records[target_digest]
        if target_digest in superseded_by:
            errors.append(f"{target_digest}: review has multiple direct successors")
        for field in ("packet_id", "subject_id", "assignment_id", "review_stage"):
            if successor[field] != target[field]:
                errors.append(f"{successor_digest}: supersession changes protected field {field}")
        if successor["actor"]["actor_id"] != target["actor"]["actor_id"]:
            errors.append(f"{successor_digest}: supersession changes actor_id")
        if review_times[successor_digest] <= review_times[target_digest]:
            errors.append(f"{successor_digest}: supersession timestamp is not later")
        if len(errors) == edge_error_count:
            superseded_by[target_digest] = successor_digest

    # A functional graph needs only one color pass. Walking every chain from
    # every node would make a long, otherwise-valid supersession chain O(n²).
    visit_state: dict[str, int] = {}
    for start_digest in valid_records:
        if visit_state.get(start_digest) == 2:
            continue
        trail: list[str] = []
        current = start_digest
        while True:
            state = visit_state.get(current, 0)
            if state == 1:
                errors.append(f"{current}: supersession cycle detected")
                break
            if state == 2:
                break
            visit_state[current] = 1
            trail.append(current)
            successor = superseded_by.get(current)
            if successor is None:
                break
            current = successor
        for digest in trail:
            visit_state[digest] = 2

    active_digests = set(valid_records) - set(superseded_by)
    active_independent: dict[str, list[str]] = defaultdict(list)
    active_adjudications: dict[str, list[str]] = defaultdict(list)
    independent_digests = {
        digest
        for digest, review in valid_records.items()
        if review["review_stage"] == "independent"
    }
    adjudication_digests = set(valid_records) - independent_digests
    eligibility_events: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    for digest in independent_digests:
        review = valid_records[digest]
        if review["outcome"] != "complete":
            continue
        subject_id = review["subject_id"]
        eligibility_events[subject_id].append((review_times[digest], 1))
        successor_digest = superseded_by.get(digest)
        if successor_digest is not None:
            eligibility_events[subject_id].append((review_times[successor_digest], -1))
    eligibility_prefix: dict[str, tuple[list[datetime], list[int]]] = {}
    for subject_id, events in eligibility_events.items():
        times: list[datetime] = []
        counts: list[int] = []
        running = 0
        for event_time, delta in sorted(events):
            if times and times[-1] == event_time:
                running += delta
                counts[-1] = running
            else:
                running += delta
                times.append(event_time)
                counts.append(running)
        eligibility_prefix[subject_id] = (times, counts)

    for digest in active_digests:
        review = valid_records[digest]
        if review["review_stage"] == "independent":
            if review["outcome"] == "complete":
                active_independent[review["subject_id"]].append(digest)
        else:
            active_adjudications[review["subject_id"]].append(digest)

    stale_adjudication_subjects: set[str] = set()
    completed_adjudication_subjects: set[str] = set()
    exact_crosswalk_count = 0
    chain_supported_exact_crosswalk_count = 0
    accepted_active_exact_crosswalk_count = 0
    for digest in adjudication_digests:
        adjudication = valid_records[digest]
        inputs = adjudication["input_reviews"]
        input_records: list[Mapping[str, Any]] = []
        adjudication_error_count = len(errors)
        supported_exact_in_adjudication = 0
        adjudication_time = review_times[digest]
        event_times, event_counts = eligibility_prefix.get(
            adjudication["subject_id"],
            ([], []),
        )
        event_index = bisect_right(event_times, adjudication_time) - 1
        eligible_input_count = event_counts[event_index] if event_index >= 0 else 0
        if len(inputs) != eligible_input_count:
            errors.append(
                f"{digest}: adjudication inputs must cover every current complete "
                "independent review available at decision time"
            )
        for input_digest in inputs:
            input_record = valid_records.get(input_digest)
            if input_record is None:
                errors.append(f"{digest}: missing input review {input_digest}")
                continue
            if input_record["review_stage"] != "independent":
                errors.append(f"{digest}: input is not an independent review")
                continue
            if input_record["outcome"] != "complete":
                errors.append(f"{digest}: input review is not complete")
            if (
                input_record["packet_id"] != adjudication["packet_id"]
                or input_record["subject_id"] != adjudication["subject_id"]
            ):
                errors.append(f"{digest}: input review belongs to another subject")
                continue
            if review_times[input_digest] > adjudication_time:
                errors.append(f"{digest}: input review postdates adjudication")
            successor_digest = superseded_by.get(input_digest)
            if successor_digest is not None and review_times[successor_digest] <= adjudication_time:
                errors.append(f"{digest}: input review was already superseded")
            input_records.append(input_record)
        actor_ids = {record["actor"]["actor_id"] for record in input_records}
        assignment_ids = {record["assignment_id"] for record in input_records}
        if len(actor_ids) < required_independent_reviews:
            errors.append(f"{digest}: adjudication lacks independent reviewer actors")
        if len(assignment_ids) < required_independent_reviews:
            errors.append(f"{digest}: adjudication lacks distinct independent assignments")
        if adjudication["actor"]["actor_id"] in actor_ids:
            errors.append(f"{digest}: adjudicator also authored an input review")
        if adjudication["assignment_id"] in assignment_ids:
            errors.append(f"{digest}: adjudication reuses an independent assignment_id")

        for crosswalk in adjudication["catalog_crosswalk_assertions"]:
            if crosswalk["strength"] != "exact":
                continue
            exact_crosswalk_count += 1
            matching_support = [
                record
                for record in input_records
                if _input_supports_exact_crosswalk(record, crosswalk)
            ]
            contradictory = any(
                _input_contradicts_exact_crosswalk(record, crosswalk) for record in input_records
            )
            if contradictory:
                errors.append(f"{digest}: exact crosswalk has contradictory input assertions")
            supporting_actor_ids = {record["actor"]["actor_id"] for record in matching_support}
            supporting_assignment_ids = {record["assignment_id"] for record in matching_support}
            if (
                len(supporting_actor_ids) < required_independent_reviews
                or len(supporting_assignment_ids) < required_independent_reviews
            ):
                errors.append(
                    f"{digest}: exact crosswalk lacks two independently supported "
                    "probable input assertions"
                )
            elif not contradictory:
                supported_exact_in_adjudication += 1

        adjudication_is_clean = len(errors) == adjudication_error_count
        current_complete_inputs = set(active_independent.get(adjudication["subject_id"], []))
        inputs_are_current = set(inputs) == current_complete_inputs and all(
            input_digest in active_digests for input_digest in inputs
        )
        if adjudication_is_clean and adjudication["outcome"] == "complete":
            chain_supported_exact_crosswalk_count += supported_exact_in_adjudication
        if digest in active_digests:
            if not inputs_are_current:
                stale_adjudication_subjects.add(adjudication["subject_id"])
            elif (
                adjudication_is_clean
                and adjudication["outcome"] == "complete"
                and len(actor_ids) >= required_independent_reviews
                and len(assignment_ids) >= required_independent_reviews
            ):
                completed_adjudication_subjects.add(adjudication["subject_id"])
                accepted_active_exact_crosswalk_count += supported_exact_in_adjudication

    for subject_id, digests in active_adjudications.items():
        if len(digests) > 1:
            errors.append(f"{subject_id}: multiple active adjudications")
            completed_adjudication_subjects.discard(subject_id)

    active_assignment_heads: dict[tuple[str, str], list[str]] = defaultdict(list)
    for digest in active_digests:
        review = valid_records[digest]
        if review["review_stage"] == "independent":
            active_assignment_heads[(review["subject_id"], review["assignment_id"])].append(digest)
    for (subject_id, assignment_id), digests in active_assignment_heads.items():
        if len(digests) > 1:
            errors.append(f"{subject_id}: assignment {assignment_id} has multiple active reviews")

    subjects_with_two_reviews = {
        subject_id
        for subject_id, digests in active_independent.items()
        if len({valid_records[digest]["actor"]["actor_id"] for digest in digests})
        >= required_independent_reviews
        and len({valid_records[digest]["assignment_id"] for digest in digests})
        >= required_independent_reviews
    }
    adjudication_ready = subjects_with_two_reviews - set(active_adjudications)
    all_subject_ids = set(subjects_by_id)
    if errors:
        # Any malformed graph can taint the apparent active heads. Promotion-like
        # counts therefore fail closed instead of reporting partial readiness.
        subjects_with_two_reviews = set()
        adjudication_ready = set()
        completed_adjudication_subjects = set()
        chain_supported_exact_crosswalk_count = 0
        accepted_active_exact_crosswalk_count = 0
    return {
        "valid": not errors,
        "errors": errors,
        "sealed_review_count": len(sealed_reviews),
        "validated_review_count": len(valid_records),
        "independent_review_count": len(independent_digests),
        "active_independent_review_count": sum(
            len(digests) for digests in active_independent.values()
        ),
        "adjudication_count": len(adjudication_digests),
        "active_adjudication_count": sum(len(digests) for digests in active_adjudications.values()),
        "superseded_review_count": len(superseded_by),
        "subjects_with_two_reviews": len(subjects_with_two_reviews),
        "adjudication_ready_subjects": len(adjudication_ready),
        "adjudicated_subjects": len(completed_adjudication_subjects),
        "stale_adjudication_subjects": len(stale_adjudication_subjects),
        "exact_crosswalk_count": exact_crosswalk_count,
        "chain_supported_exact_crosswalk_count": (chain_supported_exact_crosswalk_count),
        "accepted_active_exact_crosswalk_count": (accepted_active_exact_crosswalk_count),
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
        "unresolved_subjects": len(all_subject_ids - completed_adjudication_subjects),
    }


def _input_supports_exact_crosswalk(
    review: Mapping[str, Any],
    adopted: Mapping[str, Any],
) -> bool:
    if review["outcome"] != "complete":
        return False
    if review["actor"]["conflict_status"] != "none_declared":
        return False
    if not {"collections", "archaeology"}.intersection(review["actor"]["expertise"]):
        return False
    expected = (
        adopted["target_source_id"],
        adopted["target_edition"],
        adopted["target_record_id"],
        adopted["relationship"],
    )
    return any(
        (
            assertion["target_source_id"],
            assertion["target_edition"],
            assertion["target_record_id"],
            assertion["relationship"],
        )
        == expected
        and assertion["strength"] == "probable"
        and bool(assertion["evidence"])
        and assertion["counterevidence_checked"] is True
        for assertion in review["catalog_crosswalk_assertions"]
    )


def _input_contradicts_exact_crosswalk(
    review: Mapping[str, Any],
    adopted: Mapping[str, Any],
) -> bool:
    target = (
        adopted["target_source_id"],
        adopted["target_edition"],
        adopted["target_record_id"],
    )
    return any(
        (
            assertion["target_source_id"],
            assertion["target_edition"],
            assertion["target_record_id"],
        )
        == target
        and (
            assertion["relationship"] != adopted["relationship"]
            or assertion["strength"] == "rejected"
        )
        for assertion in review["catalog_crosswalk_assertions"]
    )


def _review_time(review: Mapping[str, Any]) -> datetime:
    value = review["actor"]["reviewed_at"]
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _require_closed_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise MuseumReviewLedgerError(
            f"{label} keys mismatch; "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MuseumReviewLedgerError(f"{label} must be an object")
    return value


def _require_checksum(value: object, label: str) -> None:
    if not isinstance(value, str) or not CHECKSUM_PATTERN.fullmatch(value):
        raise MuseumReviewLedgerError(f"{label} must be a SHA-256 checksum")


def _require_stable_id(value: object, label: str) -> None:
    if not isinstance(value, str) or not STABLE_ID_PATTERN.fullmatch(value):
        raise MuseumReviewLedgerError(f"{label} must be a stable identifier")


def _require_canonical_utc(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MuseumReviewLedgerError(f"{label} must be a canonical UTC date-time")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise MuseumReviewLedgerError(f"{label} must be a valid date-time") from error
    canonical = parsed.isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise MuseumReviewLedgerError(f"{label} must use canonical UTC form")
