"""Scientific and rights-aware validation beyond generic JSON Schema."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from indusbench.issues import Issue

SCHEMA_VERSION = "0.1.0"
READING_DIRECTIONS = {
    "left_to_right",
    "right_to_left",
    "top_to_bottom",
    "bottom_to_top",
    "boustrophedon",
    "mixed",
    "unknown",
}
RIGHTS_STATUSES = {
    "public_domain",
    "open_licensed",
    "permission_granted",
    "metadata_only",
    "restricted",
    "unknown",
}
TOKEN_CONDITIONS = {"clear", "worn", "damaged", "broken", "lost", "unreadable"}
UNCERTAINTY_STATUSES = {"certain", "clear", "uncertain", "ambiguous", "unresolved"}
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _required_mapping(
    value: Mapping[str, Any], key: str, path: str, issues: list[Issue]
) -> Mapping[str, Any] | None:
    child = value.get(key)
    if not isinstance(child, Mapping):
        issues.append(Issue("required_mapping", f"{path}.{key}", "must be an object"))
        return None
    return child


def _required_list(
    value: Mapping[str, Any], key: str, path: str, issues: list[Issue]
) -> list[Any] | None:
    child = value.get(key)
    if not isinstance(child, list):
        issues.append(Issue("required_list", f"{path}.{key}", "must be an array"))
        return None
    return child


def _required_string(
    value: Mapping[str, Any], key: str, path: str, issues: list[Issue]
) -> str | None:
    child = value.get(key)
    if not isinstance(child, str) or not child.strip():
        issues.append(Issue("required_string", f"{path}.{key}", "must be a non-empty string"))
        return None
    return child


def _check_unique(pairs: Iterable[tuple[str | None, str]], code: str, issues: list[Issue]) -> None:
    seen: dict[str, str] = {}
    for value, path in pairs:
        if value is None:
            continue
        if value in seen:
            issues.append(Issue(code, path, f"{value!r} duplicates identifier at {seen[value]}"))
        else:
            seen[value] = path


def _validate_rights(rights: Mapping[str, Any], path: str, issues: list[Issue]) -> None:
    status = _required_string(rights, "status", path, issues)
    statement = _required_string(rights, "statement", path, issues)
    if status is not None and status not in RIGHTS_STATUSES:
        issues.append(
            Issue(
                "invalid_rights_status",
                f"{path}.status",
                f"must be one of {sorted(RIGHTS_STATUSES)}",
            )
        )

    for key in ("redistribution", "derivatives"):
        if not isinstance(rights.get(key), bool):
            issues.append(Issue("invalid_type", f"{path}.{key}", "must be a boolean"))
    commercial_use = rights.get("commercial_use")
    if commercial_use is not None and not isinstance(commercial_use, bool):
        issues.append(Issue("invalid_type", f"{path}.commercial_use", "must be a boolean or null"))

    license_id = rights.get("license_id")
    if license_id is not None and (not isinstance(license_id, str) or not license_id):
        issues.append(Issue("invalid_type", f"{path}.license_id", "must be a string or null"))

    if rights.get("redistribution") is True and status in {
        "restricted",
        "unknown",
        "metadata_only",
    }:
        issues.append(
            Issue(
                "rights_contradiction",
                f"{path}.redistribution",
                f"redistribution cannot be true when rights status is {status!r}",
            )
        )
    if rights.get("redistribution") is True and status == "open_licensed" and license_id is None:
        issues.append(
            Issue(
                "missing_license",
                f"{path}.license_id",
                "open redistribution requires an explicit license identifier",
            )
        )
    if statement is None:
        return


def _validate_token(
    token: Mapping[str, Any],
    path: str,
    issues: list[Issue],
) -> tuple[str | None, int | None, int | None]:
    token_id = _required_string(token, "token_id", path, issues)
    sign_id = token.get("sign_id")
    if sign_id is not None and (not isinstance(sign_id, str) or not sign_id):
        issues.append(
            Issue("invalid_sign_id", f"{path}.sign_id", "must be a non-empty string or null")
        )

    visual_index = token.get("visual_index")
    if not isinstance(visual_index, int) or isinstance(visual_index, bool) or visual_index < 0:
        issues.append(
            Issue("invalid_visual_index", f"{path}.visual_index", "must be an integer >= 0")
        )
        visual_index = None

    reading_index = token.get("reading_index")
    if reading_index is not None and (
        not isinstance(reading_index, int) or isinstance(reading_index, bool) or reading_index < 0
    ):
        issues.append(
            Issue(
                "invalid_reading_index",
                f"{path}.reading_index",
                "must be null or an integer >= 0",
            )
        )
        reading_index = None

    confidence = token.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        issues.append(
            Issue("invalid_confidence", f"{path}.confidence", "must be a number from 0 to 1")
        )

    condition = token.get("condition")
    if condition not in TOKEN_CONDITIONS:
        issues.append(
            Issue(
                "invalid_token_condition",
                f"{path}.condition",
                f"must be one of {sorted(TOKEN_CONDITIONS)}",
            )
        )

    uncertainty = token.get("uncertainty")
    if not isinstance(uncertainty, Mapping):
        issues.append(Issue("required_mapping", f"{path}.uncertainty", "must be an object"))
    else:
        uncertainty_status = uncertainty.get("status")
        if uncertainty_status not in UNCERTAINTY_STATUSES:
            issues.append(
                Issue(
                    "invalid_uncertainty_status",
                    f"{path}.uncertainty.status",
                    f"must be one of {sorted(UNCERTAINTY_STATUSES)}",
                )
            )
        alternatives = uncertainty.get("alternatives")
        if not isinstance(alternatives, list):
            issues.append(
                Issue(
                    "required_list",
                    f"{path}.uncertainty.alternatives",
                    "must be an array",
                )
            )

    source_record_ids = token.get("source_record_ids")
    if (
        not isinstance(source_record_ids, list)
        or not source_record_ids
        or not all(isinstance(ref, str) and ref for ref in source_record_ids)
    ):
        issues.append(
            Issue(
                "invalid_source_record_ids",
                f"{path}.source_record_ids",
                "must be a non-empty array of source-record identifiers",
            )
        )

    return token_id, visual_index, reading_index


def _validate_line(
    line: Mapping[str, Any],
    path: str,
    issues: list[Issue],
) -> tuple[str | None, list[tuple[str | None, str]]]:
    line_id = _required_string(line, "line_id", path, issues)
    direction = _required_string(line, "reading_direction", path, issues)
    if direction is not None and direction not in READING_DIRECTIONS:
        issues.append(
            Issue(
                "invalid_reading_direction",
                f"{path}.reading_direction",
                f"must be one of {sorted(READING_DIRECTIONS)}",
            )
        )

    visual_order_basis = _required_string(line, "visual_order_basis", path, issues)
    if visual_order_basis is not None and visual_order_basis != "left_to_right_in_image":
        issues.append(
            Issue(
                "invalid_visual_order_basis",
                f"{path}.visual_order_basis",
                "must be 'left_to_right_in_image'",
            )
        )
    direction_confidence = line.get("direction_confidence")
    if (
        not isinstance(direction_confidence, (int, float))
        or isinstance(direction_confidence, bool)
        or not 0 <= direction_confidence <= 1
    ):
        issues.append(
            Issue(
                "invalid_direction_confidence",
                f"{path}.direction_confidence",
                "must be a number from 0 to 1",
            )
        )

    tokens = _required_list(line, "tokens", path, issues)
    if tokens is None:
        return line_id, []
    if not tokens:
        issues.append(Issue("empty_line", f"{path}.tokens", "must contain at least one token"))

    token_ids: list[tuple[str | None, str]] = []
    visual_indices: list[tuple[int | None, str]] = []
    reading_indices: list[tuple[int | None, str]] = []
    for index, token in enumerate(tokens):
        token_path = f"{path}.tokens[{index}]"
        if not isinstance(token, Mapping):
            issues.append(Issue("invalid_token", token_path, "must be an object"))
            continue
        token_id, visual_index, reading_index = _validate_token(token, token_path, issues)
        token_ids.append((token_id, f"{token_path}.token_id"))
        visual_indices.append((visual_index, f"{token_path}.visual_index"))
        reading_indices.append((reading_index, f"{token_path}.reading_index"))

    _check_unique(token_ids, "duplicate_token_id", issues)
    _check_unique(
        (
            (str(value) if value is not None else None, item_path)
            for value, item_path in visual_indices
        ),
        "duplicate_visual_index",
        issues,
    )
    _check_unique(
        (
            (str(value) if value is not None else None, item_path)
            for value, item_path in reading_indices
        ),
        "duplicate_reading_index",
        issues,
    )

    known_visual_indices = [value for value, _ in visual_indices if value is not None]
    if len(known_visual_indices) == len(tokens) and set(known_visual_indices) != set(
        range(len(tokens))
    ):
        issues.append(
            Issue(
                "noncontiguous_visual_order",
                f"{path}.tokens",
                "visual_index values must be the permutation 0..token_count-1",
            )
        )

    known_reading_indices = [value for value, _ in reading_indices if value is not None]
    if direction == "unknown" and known_reading_indices:
        issues.append(
            Issue(
                "direction_order_conflict",
                f"{path}.reading_direction",
                "direction is unknown but reading_index values assert a normalized order",
                "warning",
            )
        )
    elif len(known_reading_indices) == len(tokens) and set(known_reading_indices) != set(
        range(len(tokens))
    ):
        issues.append(
            Issue(
                "noncontiguous_reading_order",
                f"{path}.tokens",
                "complete reading_index values must be the permutation 0..token_count-1",
            )
        )

    return line_id, token_ids


def validate_artifact(record: Mapping[str, Any], index: int | None = None) -> list[Issue]:
    """Validate one nested artifact record and return all detected issues."""

    root = f"$[{index}]" if index is not None else "$"
    issues: list[Issue] = []

    version = _required_string(record, "schema_version", root, issues)
    if version is not None and version != SCHEMA_VERSION:
        issues.append(
            Issue(
                "unsupported_schema_version",
                f"{root}.schema_version",
                f"expected {SCHEMA_VERSION!r}, found {version!r}",
            )
        )

    _required_string(record, "artifact_id", root, issues)
    source_records = _required_list(record, "source_records", root, issues)
    source_record_ids: list[tuple[str | None, str]] = []
    if source_records is not None:
        if not source_records:
            issues.append(
                Issue("missing_provenance", f"{root}.source_records", "must not be empty")
            )
        for source_index, source in enumerate(source_records):
            source_path = f"{root}.source_records[{source_index}]"
            if not isinstance(source, Mapping):
                issues.append(Issue("invalid_source_record", source_path, "must be an object"))
                continue
            source_record_id = _required_string(source, "source_record_id", source_path, issues)
            source_record_ids.append((source_record_id, f"{source_path}.source_record_id"))
            _required_string(source, "source_id", source_path, issues)
            _required_string(source, "upstream_record_id", source_path, issues)
            _required_string(source, "role", source_path, issues)
    _check_unique(source_record_ids, "duplicate_source_record_id", issues)
    known_source_record_ids = {
        source_record_id
        for source_record_id, _ in source_record_ids
        if source_record_id is not None
    }

    rights = _required_mapping(record, "rights", root, issues)
    if rights is not None:
        _validate_rights(rights, f"{root}.rights", issues)

    crosswalk = _required_list(record, "catalog_crosswalk", root, issues)
    if crosswalk is not None:
        for crosswalk_index, entry in enumerate(crosswalk):
            entry_path = f"{root}.catalog_crosswalk[{crosswalk_index}]"
            if not isinstance(entry, Mapping):
                issues.append(Issue("invalid_catalog_identifier", entry_path, "must be an object"))
                continue
            _required_string(entry, "catalog", entry_path, issues)
            _required_string(entry, "identifier", entry_path, issues)

    site = _required_mapping(record, "site", root, issues)
    if site is not None:
        site_id = site.get("site_id")
        name = site.get("name")
        if site_id is not None and (not isinstance(site_id, str) or not site_id):
            issues.append(
                Issue("invalid_site_id", f"{root}.site.site_id", "must be a string or null")
            )
        if name is not None and (not isinstance(name, str) or not name):
            issues.append(
                Issue("invalid_site_name", f"{root}.site.name", "must be a string or null")
            )
        if site_id is None and name is None:
            issues.append(
                Issue(
                    "unknown_site",
                    f"{root}.site",
                    "site_id and name are both unknown",
                    "warning",
                )
            )

    object_record = _required_mapping(record, "object", root, issues)
    if object_record is not None:
        _required_string(object_record, "object_type", f"{root}.object", issues)
        material = object_record.get("material")
        if material is not None and not isinstance(material, str):
            issues.append(
                Issue("invalid_type", f"{root}.object.material", "must be a string or null")
            )

    period = _required_mapping(record, "period", root, issues)
    if period is not None:
        certainty = period.get("certainty")
        if (
            not isinstance(certainty, (int, float))
            or isinstance(certainty, bool)
            or not 0 <= certainty <= 1
        ):
            issues.append(
                Issue(
                    "invalid_period_certainty",
                    f"{root}.period.certainty",
                    "must be a number from 0 to 1",
                )
            )

    family_id = record.get("duplicate_family_id")
    if family_id is not None and (not isinstance(family_id, str) or not family_id):
        issues.append(
            Issue(
                "invalid_duplicate_family",
                f"{root}.duplicate_family_id",
                "must be a non-empty string or null",
            )
        )

    images = _required_list(record, "images", root, issues)
    image_ids: list[tuple[str | None, str]] = []
    if images is not None:
        for image_index, image in enumerate(images):
            image_path = f"{root}.images[{image_index}]"
            if not isinstance(image, Mapping):
                issues.append(Issue("invalid_image", image_path, "must be an object"))
                continue
            image_id = _required_string(image, "image_id", image_path, issues)
            image_ids.append((image_id, f"{image_path}.image_id"))
            _required_string(image, "source_id", image_path, issues)
            image_hash = image.get("image_hash")
            if not isinstance(image_hash, str) or not SHA256_PATTERN.fullmatch(image_hash):
                issues.append(
                    Issue(
                        "invalid_sha256",
                        f"{image_path}.image_hash",
                        "must be 'sha256:' followed by 64 lowercase hexadecimal characters",
                    )
                )
            image_rights = _required_mapping(image, "rights", image_path, issues)
            if image_rights is not None:
                _validate_rights(image_rights, f"{image_path}.rights", issues)
        _check_unique(image_ids, "duplicate_image_id", issues)
    known_image_ids = {image_id for image_id, _ in image_ids if image_id is not None}

    sides = _required_list(record, "sides", root, issues)
    if sides is None:
        return issues
    if not sides:
        issues.append(Issue("empty_artifact", f"{root}.sides", "must contain at least one side"))

    side_ids: list[tuple[str | None, str]] = []
    line_ids: list[tuple[str | None, str]] = []
    global_token_ids: list[tuple[str | None, str]] = []
    for side_index, side in enumerate(sides):
        side_path = f"{root}.sides[{side_index}]"
        if not isinstance(side, Mapping):
            issues.append(Issue("invalid_side", side_path, "must be an object"))
            continue
        side_id = _required_string(side, "side_id", side_path, issues)
        side_ids.append((side_id, f"{side_path}.side_id"))
        _required_string(side, "physical_form", side_path, issues)
        side_image_ids = _required_list(side, "image_ids", side_path, issues)
        if side_image_ids is not None and not all(
            isinstance(image_id, str) and image_id for image_id in side_image_ids
        ):
            issues.append(
                Issue(
                    "invalid_image_ids",
                    f"{side_path}.image_ids",
                    "must contain only non-empty image identifiers",
                )
            )
        elif side_image_ids is not None:
            for image_index, image_id in enumerate(side_image_ids):
                if image_id not in known_image_ids:
                    issues.append(
                        Issue(
                            "unknown_image_reference",
                            f"{side_path}.image_ids[{image_index}]",
                            f"{image_id!r} is not declared in artifact images",
                        )
                    )
        lines = _required_list(side, "lines", side_path, issues)
        if lines is None:
            continue
        for line_index, line in enumerate(lines):
            line_path = f"{side_path}.lines[{line_index}]"
            if not isinstance(line, Mapping):
                issues.append(Issue("invalid_line", line_path, "must be an object"))
                continue
            line_id, token_ids = _validate_line(line, line_path, issues)
            line_ids.append((line_id, f"{line_path}.line_id"))
            global_token_ids.extend(token_ids)
            for token_index, token in enumerate(line.get("tokens", [])):
                if not isinstance(token, Mapping):
                    continue
                for source_index, source_record_id in enumerate(token.get("source_record_ids", [])):
                    if (
                        isinstance(source_record_id, str)
                        and source_record_id not in known_source_record_ids
                    ):
                        issues.append(
                            Issue(
                                "unknown_source_record_reference",
                                (
                                    f"{line_path}.tokens[{token_index}]"
                                    f".source_record_ids[{source_index}]"
                                ),
                                (
                                    f"{source_record_id!r} is not declared in "
                                    "artifact source_records"
                                ),
                            )
                        )

    _check_unique(side_ids, "duplicate_side_id", issues)
    _check_unique(line_ids, "duplicate_line_id", issues)
    _check_unique(global_token_ids, "duplicate_token_id", issues)
    return issues


def validate_corpus(records: Iterable[Mapping[str, Any]]) -> list[Issue]:
    """Validate a collection and enforce cross-artifact identifiers."""

    records_list = list(records)
    issues: list[Issue] = []
    artifact_ids: list[tuple[str | None, str]] = []
    for index, record in enumerate(records_list):
        if not isinstance(record, Mapping):
            issues.append(Issue("invalid_artifact", f"$[{index}]", "must be an object"))
            continue
        issues.extend(validate_artifact(record, index))
        value = record.get("artifact_id")
        artifact_ids.append((value if isinstance(value, str) else None, f"$[{index}].artifact_id"))
    _check_unique(artifact_ids, "duplicate_artifact_id", issues)
    return issues


def has_errors(issues: Iterable[Issue]) -> bool:
    """Return whether any issue has error severity."""

    return any(issue.severity == "error" for issue in issues)
