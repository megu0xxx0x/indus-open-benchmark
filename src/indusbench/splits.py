"""Leakage-resistant dataset splits.

The split helpers operate on JSON-like artifact mappings and return the original
record objects. Duplicate families, rather than individual rows, are the unit
of the deterministic public train/development split.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from typing import TypeAlias

from indusbench.audit import (
    extract_catalog_crosswalks,
    extract_image_hashes,
    extract_normalized_sequences,
)

ArtifactRecord: TypeAlias = Mapping[str, object]
DatasetSplit: TypeAlias = tuple[list[ArtifactRecord], list[ArtifactRecord]]

MISSING_GROUP = "<missing>"


def _stable_text(value: object) -> str:
    """Return a deterministic, human-readable representation of a group value."""
    if value is None:
        return MISSING_GROUP
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else MISSING_GROUP
    if isinstance(value, Mapping):
        identity_keys = (
            "id",
            "site_id",
            "object_type",
            "label",
            "phase",
            "type",
            "name",
            "value",
        )
        for key in identity_keys:
            candidate = value.get(key)
            if candidate not in (None, ""):
                return _stable_text(candidate)
        if any(key in value for key in identity_keys):
            return MISSING_GROUP
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def _artifact_id(record: ArtifactRecord) -> str:
    artifact_id = _stable_text(record.get("artifact_id"))
    if artifact_id == MISSING_GROUP:
        raise ValueError("record is missing a non-empty artifact_id")
    return artifact_id


def duplicate_family_key(record: ArtifactRecord) -> str:
    """Return a collision-resistant grouping key for an artifact.

    Records without a ``duplicate_family_id`` form a singleton family keyed by
    ``artifact_id``. Prefixes prevent a real family identifier from colliding
    with that fallback.
    """
    family_id = _stable_text(record.get("duplicate_family_id"))
    if family_id != MISSING_GROUP:
        return f"family:{family_id}"
    return f"artifact:{_artifact_id(record)}"


def _ranked_family_keys(family_keys: Iterable[str], seed: int | str) -> list[str]:
    seed_text = str(seed)

    def rank(family_key: str) -> tuple[bytes, str]:
        payload = f"{seed_text}\0{family_key}".encode()
        return hashlib.sha256(payload).digest(), family_key

    return sorted(set(family_keys), key=rank)


def _test_group_count(group_count: int, test_fraction: float) -> int:
    if test_fraction == 0.0:
        return 0
    if test_fraction == 1.0:
        return group_count
    if group_count < 2:
        raise ValueError("an interior test_fraction requires at least two leakage groups")
    rounded_count = math.floor((group_count * test_fraction) + 0.5)
    return min(group_count - 1, max(1, rounded_count))


def _validate_test_fraction(test_fraction: float) -> None:
    if not math.isfinite(test_fraction) or not 0.0 <= test_fraction <= 1.0:
        raise ValueError("test_fraction must be a finite number between 0 and 1")


def deterministic_family_split(
    records: Iterable[ArtifactRecord],
    *,
    test_fraction: float = 0.2,
    seed: int | str = 0,
) -> DatasetSplit:
    """Split artifacts deterministically while keeping duplicate families intact.

    The requested fraction is applied to the number of families, not rows. For
    an interior fraction, both partitions receive at least one family. At least
    two distinct families are therefore required.
    """
    _validate_test_fraction(test_fraction)

    materialized = list(records)
    if not materialized:
        return [], []

    family_by_record = [duplicate_family_key(record) for record in materialized]
    ranked_families = _ranked_family_keys(family_by_record, seed)
    family_count = len(ranked_families)

    test_family_count = _test_group_count(family_count, test_fraction)

    test_families = set(ranked_families[:test_family_count])
    train: list[ArtifactRecord] = []
    test: list[ArtifactRecord] = []
    for record, family_key in zip(materialized, family_by_record, strict=True):
        (test if family_key in test_families else train).append(record)
    return train, test


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))
        self._rank = [0] * size

    def find(self, index: int) -> int:
        parent = self._parent[index]
        if parent != index:
            self._parent[index] = self.find(parent)
        return self._parent[index]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self._rank[left_root] < self._rank[right_root]:
            left_root, right_root = right_root, left_root
        self._parent[right_root] = left_root
        if self._rank[left_root] == self._rank[right_root]:
            self._rank[left_root] += 1


def deterministic_leakage_safe_split(
    records: Iterable[ArtifactRecord],
    *,
    test_fraction: float = 0.2,
    seed: int | str = 0,
) -> DatasetSplit:
    """Split connected leakage components deterministically.

    Two records share a component when they have the same duplicate family,
    normalized image hash, exact normalized line sequence, or catalog crosswalk
    alias. Connectivity is transitive, so indirect evidence chains remain
    entirely in one partition.
    """
    _validate_test_fraction(test_fraction)
    materialized = list(records)
    if not materialized:
        return [], []

    union_find = _UnionFind(len(materialized))
    evidence_owner: dict[tuple[str, Hashable], int] = {}
    for index, record in enumerate(materialized):
        evidence: list[tuple[str, Hashable]] = [("family", duplicate_family_key(record))]
        evidence.extend(("image_hash", value) for value in extract_image_hashes(record))
        evidence.extend(("sequence", value) for value in extract_normalized_sequences(record))
        evidence.extend(
            ("catalog_crosswalk", value) for value in extract_catalog_crosswalks(record)
        )
        for evidence_key in evidence:
            owner = evidence_owner.setdefault(evidence_key, index)
            union_find.union(index, owner)

    members_by_root: dict[int, list[int]] = defaultdict(list)
    for index in range(len(materialized)):
        members_by_root[union_find.find(index)].append(index)

    component_by_record: list[str] = [""] * len(materialized)
    for member_indexes in members_by_root.values():
        member_artifact_ids = sorted(_artifact_id(materialized[index]) for index in member_indexes)
        component_key = json.dumps(
            member_artifact_ids,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for index in member_indexes:
            component_by_record[index] = component_key

    ranked_components = _ranked_family_keys(component_by_record, seed)
    test_component_count = _test_group_count(len(ranked_components), test_fraction)
    test_components = set(ranked_components[:test_component_count])

    train: list[ArtifactRecord] = []
    test: list[ArtifactRecord] = []
    for record, component_key in zip(
        materialized,
        component_by_record,
        strict=True,
    ):
        (test if component_key in test_components else train).append(record)
    return train, test


def _nested_group_value(record: ArtifactRecord, candidates: tuple[str, ...]) -> str:
    for field in candidates:
        if field in record:
            return _stable_text(record[field])

    for container_name in ("context", "provenance", "archaeology"):
        container = record.get(container_name)
        if not isinstance(container, Mapping):
            continue
        for field in candidates:
            if field in container:
                return _stable_text(container[field])
    return MISSING_GROUP


def _leave_one_group_out(
    records: Iterable[ArtifactRecord],
    candidates: tuple[str, ...],
) -> dict[str, DatasetSplit]:
    materialized = list(records)
    group_by_record = [_nested_group_value(record, candidates) for record in materialized]
    family_by_record = [duplicate_family_key(record) for record in materialized]
    result: dict[str, DatasetSplit] = {}
    for held_out_group in sorted(set(group_by_record)):
        held_out_families = {
            family
            for family, group in zip(family_by_record, group_by_record, strict=True)
            if group == held_out_group
        }
        train: list[ArtifactRecord] = []
        test: list[ArtifactRecord] = []
        for record, family in zip(materialized, family_by_record, strict=True):
            (test if family in held_out_families else train).append(record)
        result[held_out_group] = (train, test)
    return result


def leave_one_site_out(records: Iterable[ArtifactRecord]) -> dict[str, DatasetSplit]:
    """Return one split per site, closing the holdout over duplicate families."""
    return _leave_one_group_out(records, ("site", "site_id"))


def leave_one_period_out(records: Iterable[ArtifactRecord]) -> dict[str, DatasetSplit]:
    """Return one split per period or phase, closing over duplicate families."""
    return _leave_one_group_out(records, ("period", "phase"))


def leave_one_object_type_out(records: Iterable[ArtifactRecord]) -> dict[str, DatasetSplit]:
    """Return one split per object type, closing over duplicate families."""
    return _leave_one_group_out(
        records,
        ("object_type", "object", "artifact_type", "object_class"),
    )
