"""Import the public mayig JSON transcription without vendoring upstream data.

The upstream repository stores graphemes in physical left-to-right order while
documenting an inferred right-to-left reading direction. This importer keeps
those orders separate and retains the lossless upstream feature vectors in a
namespaced, non-normative extension payload.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import quote

SCHEMA_VERSION = "0.1.0"
SOURCE_ID = "mayig-indus-valley-script-corpus"
SOURCE_URL = "https://github.com/mayig/indus-valley-script-corpus"
MIT_LICENSE_URL = f"{SOURCE_URL}/blob/main/LICENSE"
UPSTREAM_DIRECTION_CONFIDENCE = 0.5

_FILE_ID_PATTERN = re.compile(r"^(?P<prefix>[A-Za-z]+)0*(?P<number>[0-9]+)$")
_FULL_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_OBJECT_TYPES = {
    "seal": "seal",
    "sealing": "sealing",
    "tablet": "tablet",
    "pottery": "pottery",
    "token": "token",
    "amulet": "amulet",
    "signboard": "signboard",
}
_SITE_BY_PREFIX: dict[str, dict[str, Any]] = {
    "M": {
        "site_id": "Mohenjo-daro",
        "name": "Mohenjo-daro",
        "modern_country": "Pakistan",
        "administrative_area": "Sindh",
        "findspot": None,
        "certainty": 1.0,
    }
}

JsonObject = dict[str, Any]


class MayigImportError(ValueError):
    """Raised when an upstream record cannot be mapped without silent repair."""


def import_mayig_corpus(
    source_root: str | Path,
    *,
    source_revision: str | None = None,
    retrieved_at: str | None = None,
) -> list[JsonObject]:
    """Import every mayig artifact in deterministic upstream path order.

    ``source_root`` may be a repository checkout or its ``corpus`` directory.
    No files are copied into this project. A revision is detected from a normal
    Git checkout when one is not supplied explicitly.
    """

    repository_root, corpus_root = _resolve_corpus_root(Path(source_root))
    revision = _validated_revision(source_revision) or _read_git_revision(repository_root)
    paths = sorted(
        corpus_root.rglob("*.json"),
        key=lambda path: path.relative_to(corpus_root).as_posix(),
    )
    if not paths:
        raise MayigImportError(f"{corpus_root}: no JSON artifact records found")

    records: list[JsonObject] = []
    artifact_sources: dict[str, str] = {}
    for path in paths:
        record = import_mayig_artifact(
            path,
            repository_root=repository_root,
            source_revision=revision,
            retrieved_at=retrieved_at,
        )
        artifact_id = record["artifact_id"]
        source_path = record["source_records"][0]["source_path"]
        if artifact_id in artifact_sources:
            first_path = artifact_sources[artifact_id]
            raise MayigImportError(
                f"{source_path}: artifact_id {artifact_id!r} duplicates {first_path}"
            )
        artifact_sources[artifact_id] = source_path
        records.append(record)
    return records


def import_mayig_artifact(
    artifact_path: str | Path,
    *,
    repository_root: str | Path | None = None,
    source_revision: str | None = None,
    retrieved_at: str | None = None,
) -> JsonObject:
    """Import one upstream JSON file into the nested artifact contract."""

    path = Path(artifact_path)
    if not path.is_file():
        raise MayigImportError(f"{path}: artifact JSON file does not exist")

    root = Path(repository_root) if repository_root is not None else _infer_repository_root(path)
    revision = _validated_revision(source_revision)
    if revision is None:
        revision = _read_git_revision(root)

    try:
        raw_bytes = path.read_bytes()
        payload = json.loads(raw_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MayigImportError(f"{path}: invalid artifact JSON: {exc}") from exc

    source_path = _relative_source_path(path, root)
    sides_payload = _require_list(payload, source_path)
    if not sides_payload:
        raise MayigImportError(f"{source_path}: artifact must contain at least one side")

    artifact_id = _catalog_id_from_filename(path.stem)
    source_record_id = f"mayig:{artifact_id}"
    record_hash = f"sha256:{sha256(raw_bytes).hexdigest()}"
    source_record = {
        "source_record_id": source_record_id,
        "source_id": SOURCE_ID,
        "upstream_record_id": artifact_id,
        "role": "transcription",
        "locator": _source_locator(source_path, revision),
        "retrieved_at": retrieved_at,
        "revision": revision,
        "source_path": source_path,
        "record_hash": record_hash,
    }

    extensions: JsonObject = {
        "mayig:raw_feature_vectors": {},
        "mayig:upstream_grapheme_indices": {},
        "mayig:side_descriptions": {},
        "mayig:import_warnings": [],
        "mayig:sequence_policy": (
            "Tokens preserve the upstream physical left-to-right order; reading_index reverses "
            "that order within each line under the upstream right-to-left inference."
        ),
    }
    sides: list[JsonObject] = []
    descriptions: list[str] = []
    any_reported_damage = False
    seen_side_ids: set[str] = set()

    for side_index, side_value in enumerate(sides_payload):
        side_path = f"{source_path}#sides[{side_index}]"
        side = _require_mapping(side_value, side_path)
        side_id = _require_nonempty_string(side.get("id"), f"{side_path}.id")
        if side_id in seen_side_ids:
            raise MayigImportError(f"{side_path}.id: duplicate side id {side_id!r}")
        seen_side_ids.add(side_id)

        description = _optional_string(side.get("description"), f"{side_path}.description")
        descriptions.append(description)
        extensions["mayig:side_descriptions"][side_id] = description
        graphemes = _require_list(side.get("graphemes"), f"{side_path}.graphemes")
        if not graphemes:
            raise MayigImportError(f"{side_path}.graphemes: side must contain at least one token")

        grouped: dict[int, list[tuple[int, Mapping[str, Any], list[int]]]] = defaultdict(list)
        for upstream_index, grapheme_value in enumerate(graphemes):
            grapheme_path = f"{side_path}.graphemes[{upstream_index}]"
            grapheme = _require_mapping(grapheme_value, grapheme_path)
            features = _feature_vector(grapheme.get("features"), f"{grapheme_path}.features")
            grouped[features[1]].append((upstream_index, grapheme, features))

        lines: list[JsonObject] = []
        for line_number in sorted(grouped):
            observations = grouped[line_number]
            tokens: list[JsonObject] = []
            token_count = len(observations)
            for visual_index, (upstream_index, grapheme, features) in enumerate(observations):
                grapheme_path = f"{side_path}.graphemes[{upstream_index}]"
                sign_id = _require_nonempty_string(grapheme.get("id"), f"{grapheme_path}.id")
                damage = features[0]
                uncertainty_value = features[2]
                if uncertainty_value > 100:
                    raise MayigImportError(
                        f"{grapheme_path}.features[2]: uncertainty {uncertainty_value} "
                        "is outside documented range 0-100"
                    )

                token_id = f"{side_id}:L{line_number}:T{upstream_index + 1}"
                confidence = (100 - uncertainty_value) / 100
                condition = "clear" if damage == 0 else "damaged"
                any_reported_damage = any_reported_damage or damage > 0
                uncertainty_status = "clear" if uncertainty_value == 0 else "uncertain"
                uncertainty_notes = (
                    f"Upstream annotator's subjective uncertainty value: {uncertainty_value}/100."
                )
                tokens.append(
                    {
                        "token_id": token_id,
                        "sign_id": sign_id,
                        "visual_index": visual_index,
                        "reading_index": token_count - visual_index - 1,
                        "confidence": confidence,
                        "condition": condition,
                        "uncertainty": {
                            "status": uncertainty_status,
                            "alternatives": [],
                            "notes": uncertainty_notes,
                        },
                        "geometry": None,
                        "source_record_ids": [source_record_id],
                    }
                )
                extensions["mayig:raw_feature_vectors"][token_id] = features
                extensions["mayig:upstream_grapheme_indices"][token_id] = upstream_index

                if damage > 100:
                    extensions["mayig:import_warnings"].append(
                        {
                            "code": "damage_out_of_documented_range",
                            "path": f"{grapheme_path}.features[0]",
                            "raw_value": damage,
                            "message": (
                                "Damage is documented as a percentage but exceeds 100; "
                                "the raw value is retained without clamping."
                            ),
                        }
                    )

            lines.append(
                {
                    "line_id": f"{side_id}:L{line_number}",
                    "visual_order_basis": "left_to_right_in_image",
                    "reading_direction": "right_to_left",
                    "direction_confidence": UPSTREAM_DIRECTION_CONFIDENCE,
                    "tokens": tokens,
                }
            )

        sides.append(
            {
                "side_id": side_id,
                "physical_form": _physical_form(description),
                "image_ids": [],
                "lines": lines,
            }
        )

    if any(not side_id.startswith(artifact_id) for side_id in seen_side_ids):
        extensions["mayig:import_warnings"].append(
            {
                "code": "side_id_artifact_id_mismatch",
                "path": source_path,
                "raw_value": sorted(seen_side_ids),
                "message": (
                    f"One or more side ids do not begin with the filename-derived "
                    f"artifact id {artifact_id!r}."
                ),
            }
        )

    rights_license_uri = (
        f"{SOURCE_URL}/blob/{revision}/LICENSE" if revision is not None else MIT_LICENSE_URL
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "source_records": [source_record],
        "rights": {
            "status": "metadata_only",
            "license_id": "MIT",
            "license_uri": rights_license_uri,
            "rights_holder": "Michael Carlson",
            "redistribution": False,
            "derivatives": True,
            "commercial_use": True,
            "statement": (
                "The upstream repository declares MIT. This record redistributes structured "
                "transcription metadata only; it includes no artifact or catalog image."
            ),
            "evidence_uri": rights_license_uri,
            "verified_at": retrieved_at,
        },
        "catalog_crosswalk": [
            {
                "catalog": "CISI",
                "identifier": artifact_id,
                "record_uri": None,
                "certainty": 1.0,
            }
        ],
        "site": _site_for_artifact(artifact_id),
        "period": {
            "label": None,
            "phase": None,
            "earliest_year_bce": None,
            "latest_year_bce": None,
            "basis": "unknown",
            "certainty": 0.0,
        },
        "object": {
            "object_type": _object_type(descriptions),
            "material": "unknown",
            "dimensions_mm": None,
            "condition": "damaged" if any_reported_damage else "unknown",
            "collection": {
                "institution": None,
                "accession_number": None,
            },
            "observed_motifs": _observed_motifs(descriptions),
        },
        "duplicate_family_id": None,
        "images": [],
        "sides": sides,
        "observation_notes": (
            "Imported from a work-in-progress CISI-derived transcription. The source supplies no "
            "images, material, period, findspot, collection, or duplicate-family evidence. "
            "Right-to-left reading is an upstream corpus-wide inference."
        ),
        "extensions": extensions,
    }


def _resolve_corpus_root(source_root: Path) -> tuple[Path, Path]:
    root = source_root.resolve()
    if not root.is_dir():
        raise MayigImportError(f"{source_root}: source directory does not exist")
    nested = root / "corpus"
    if nested.is_dir():
        return root, nested
    if root.name == "corpus":
        return root.parent, root
    if any(root.rglob("*.json")):
        return root, root
    raise MayigImportError(f"{root}: expected a repository root or corpus directory")


def _infer_repository_root(path: Path) -> Path:
    for parent in path.resolve().parents:
        if parent.name == "corpus":
            return parent.parent
    return path.resolve().parent


def _relative_source_path(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _validated_revision(revision: str | None) -> str | None:
    if revision is None:
        return None
    if not isinstance(revision, str) or not revision.strip():
        raise MayigImportError("source_revision must be a non-empty string or null")
    return revision.strip()


def _read_git_revision(repository_root: Path) -> str | None:
    marker = repository_root / ".git"
    git_directory = marker
    if marker.is_file():
        try:
            marker_text = marker.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not marker_text.startswith("gitdir:"):
            return None
        git_directory = Path(marker_text.removeprefix("gitdir:").strip())
        if not git_directory.is_absolute():
            git_directory = marker.parent / git_directory
    if not git_directory.is_dir():
        return None

    try:
        head = (git_directory / "HEAD").read_text(encoding="ascii").strip()
    except OSError:
        return None
    if _FULL_COMMIT_PATTERN.fullmatch(head):
        return head
    if not head.startswith("ref: "):
        return None

    reference = head.removeprefix("ref: ").strip()
    try:
        commit = (git_directory / reference).read_text(encoding="ascii").strip()
    except OSError:
        commit = _read_packed_reference(git_directory / "packed-refs", reference)
    return commit if commit is not None and _FULL_COMMIT_PATTERN.fullmatch(commit) else None


def _read_packed_reference(packed_refs: Path, reference: str) -> str | None:
    try:
        lines = packed_refs.read_text(encoding="ascii").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line or line.startswith(("#", "^")):
            continue
        commit, separator, candidate = line.partition(" ")
        if separator and candidate == reference:
            return commit
    return None


def _catalog_id_from_filename(stem: str) -> str:
    match = _FILE_ID_PATTERN.fullmatch(stem)
    if match is None:
        raise MayigImportError(
            f"{stem}: artifact filename must contain an alphabetic prefix and numeric id"
        )
    number = int(match.group("number"))
    return f"{match.group('prefix').upper()}-{number}"


def _source_locator(source_path: str, revision: str | None) -> str:
    ref = revision if revision is not None else "main"
    return f"{SOURCE_URL}/blob/{quote(ref, safe='')}/{quote(source_path, safe='/')}"


def _site_for_artifact(artifact_id: str) -> JsonObject:
    prefix = artifact_id.partition("-")[0]
    known = _SITE_BY_PREFIX.get(prefix)
    if known is not None:
        return dict(known)
    return {
        "site_id": None,
        "name": None,
        "modern_country": None,
        "administrative_area": None,
        "findspot": None,
        "certainty": 0.0,
    }


def _physical_form(description: str) -> str:
    return "seal_impression" if "seal" in description.casefold().split() else "unknown"


def _object_type(descriptions: list[str]) -> str:
    candidates = {
        normalized
        for description in descriptions
        for word, normalized in _OBJECT_TYPES.items()
        if word in description.casefold().split()
    }
    return candidates.pop() if len(candidates) == 1 else "unknown"


def _observed_motifs(descriptions: list[str]) -> list[str]:
    motifs: list[str] = []
    if any("unicorn" in description.casefold().split() for description in descriptions):
        motifs.append("unicorn")
    return motifs


def _feature_vector(value: Any, path: str) -> list[int]:
    features = _require_list(value, path)
    if len(features) < 3:
        raise MayigImportError(
            f"{path}: expected damage, line, and uncertainty as the first three values"
        )
    for index, feature in enumerate(features):
        if not isinstance(feature, int) or isinstance(feature, bool) or feature < 0:
            raise MayigImportError(f"{path}[{index}]: feature values must be integers >= 0")
    if features[1] < 1:
        raise MayigImportError(f"{path}[1]: line number must be an integer >= 1")
    return list(features)


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MayigImportError(f"{path}: expected an object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise MayigImportError(f"{path}: expected an array")
    return value


def _require_nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MayigImportError(f"{path}: expected a non-empty string")
    return value


def _optional_string(value: Any, path: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise MayigImportError(f"{path}: expected a string or null")
    return value
