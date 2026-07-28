from __future__ import annotations

import hashlib
import io
import json
import math
import re
import stat
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

ORACC_ED3B_PROJECT: Final = "epsd2/admin/ed3b"
ORACC_ED3B_ARCHIVE_URL: Final = "https://oracc.museum.upenn.edu/json/epsd2-admin-ed3b.zip"
ORACC_ED3B_ARCHIVE_SHA256: Final = (
    "sha256:a108205140d101ca8d4d38c106fad7b61abac427eb51da12f912c8eada70c557"
)
ORACC_ED3B_ARCHIVE_BYTES: Final = 34_534_747
ORACC_ED3B_ARCHIVE_MEMBER_COUNT: Final = 3_491
ORACC_ED3B_CATALOGUE_DOCUMENT_COUNT: Final = 3_477
ORACC_ED3B_UNIT_GLOSSARY_ENTRY_COUNT: Final = 18
ORACC_ED3B_UNIT_GLOSSARY_INSTANCE_COUNT: Final = 6_173
ORACC_ED3B_LICENSE_ID: Final = "CC0-1.0"
ORACC_ED3B_LICENSE_TEXT: Final = "This data is released under the CC0 license"
ORACC_ED3B_LICENSE_URL: Final = "https://creativecommons.org/publicdomain/zero/1.0/"
ORACC_ED3B_PERIOD: Final = "Early Dynastic IIIb"
ORACC_ED3B_GENRE: Final = "Administrative"
ORACC_ED3B_PROTOCOL_SHA256: Final = (
    "sha256:ff495b0f9da96153c428614b7677c4099c35ea3035f414999473e2c807d07ba3"
)

ORACC_ED3B_GOLD_CLASSES: Final = (
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
)
ORACC_ED3B_STATES: Final = ("context_only", *ORACC_ED3B_GOLD_CLASSES)
ORACC_ED3B_TRUTH_STATES: Final = (*ORACC_ED3B_STATES, "annotation_unknown")

MAX_ARCHIVE_BYTES: Final = 48 * 1024 * 1024
MAX_ARCHIVE_MEMBERS: Final = 5_000
MAX_DECLARED_UNCOMPRESSED_BYTES: Final = 650 * 1024 * 1024
MAX_INDEX_MEMBER_BYTES: Final = 48 * 1024 * 1024
MAX_CORPUS_MEMBER_BYTES: Final = 2 * 1024 * 1024
MAX_JSON_DEPTH: Final = 128
MAX_PROTOCOL_BYTES: Final = 64 * 1024

_PUBLIC_IDENTIFIER = re.compile(r"^P[0-9]{6}$")
_TAGGED_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_CORPUS_MEMBER = re.compile(rf"^{re.escape(ORACC_ED3B_PROJECT)}/corpusjson/(P[0-9]{{6}})\.json$")
_MANIFEST_DOMAIN: Final = b"indusbench:oracc-ed3b:selected-member-manifest:v1\x00"
_EFFECTIVE_CORPUS_DOMAIN: Final = b"indusbench:oracc-ed3b:effective-corpus:v1\x00"
_SUPPORT_COMMITMENT_DOMAIN: Final = b"indusbench:oracc-ed3b:support-commitment:v1\x00"
_PROJECTION_DOMAIN: Final = b"indusbench:oracc-ed3b:gold-projection:v1\x00"
_OBSERVATION_CONTRACT_DOMAIN: Final = b"indusbench:oracc-ed3b:observation-contract:v1\x00"
_OBSERVATION_ATOM_DOMAIN: Final = b"indusbench:oracc-ed3b:observation-atom:v1\x00"
_AUDIT_EXCLUSION_ID_DOMAIN: Final = b"indusbench:oracc-ed3b:audit-exclusion-id:v1\x00"
_AUDIT_EXCLUSION_SET_SHA256: Final = (
    "sha256:5c28be3dbfb6111d83a297ac31b2ba640ce4fa521adf89edec3abf195b9ae0cf"
)
_AUDIT_EXCLUSION_KEYS: Final = frozenset(
    {
        "3ee204951c459e102f063f62fc9fa191060ab372eaf55d30dfd1abbdbf8ba004",
        "4c8f0af0e1f02824ba7a9364c71861046d2dd00409731e5901010309753d8cd5",
        "505ea3be377c49d251f0b0f75eee09d83028c7fc018b28c8385a22e30ccfe955",
        "580e89125fe52b6ba7ba4237d9e9eef84b469bb4928f35dc8cd2fddf154c0209",
        "595d16bb1f519e4e359a8f7a8c10026ac1f1653c18888ac1c47b2de07c06cde5",
        "6106bfd46f6d42d3712f4fe6ffd54c47318b1a3fd02f4d7bd1426c1563c8fac7",
        "8f7ebb10d31b0cbcff489dc8dd24bc465e58ebaeb24d335374412a65a25adeb6",
        "9513f10ed2d44e8a933ddde6c8d1f57b2ad0dfe3ad77e0e8bd18bcb4e2ab8f46",
        "9e964935fd374906f502623a598373a7442ed3c6171bc05ab184ce83efe34a9a",
        "aefe6f8257362a9c904518f5f93b27542b1ec787ada3e4cbd10a71004b504886",
        "b83cb98a44ed47f105ecd0cb6729b7bd43f0ceb196b35304979039fde0af4ed3",
        "cea889e62543b804e93a2f83b61b70b81f55fd9faecc31fb1c61c7001de47430",
        "dd416fb7cda3bab28a42f1849b86950b1a3dd8427d3ab04c9f6476bc0d9f52c6",
        "eeac6ff3965220796f6f7c6759cd985a9cf2c52750ed7f6b067ebc47ef3dce5c",
        "f3ace6ba9e09444326daec0197549a74f7eb0509b4ec034e4dd30ecab99d931a",
        "fa12d802d72440558ec6a57baf6f7fae1705b34817f907ce0125056a2cf2fd1c",
    }
)

GoldClass = Literal["quantity", "unit", "person_name", "settlement_name"]
State = Literal[
    "context_only",
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
]
TruthState = Literal[
    "context_only",
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
    "annotation_unknown",
]

_GDL_ATOM_KEYS: Final = ("q", "c", "s", "v")
_GDL_CHILD_KEYS: Final = ("seq", "qualified", "group")
_GDL_DROPPED_KEYS: Final = frozenset(
    {
        "b",
        "breakEnd",
        "breakStart",
        "delim",
        "det",
        "gdl_collated",
        "gdl_remarked",
        "gdl_type",
        "gg",
        "hc",
        "ho",
        "id",
        "m",
        "mods",
        "n",
        "o",
        "pos",
        "queried",
        "r",
        "statusStart",
    }
)
_GDL_ALLOWED_KEYS: Final = (
    frozenset(_GDL_ATOM_KEYS)
    | frozenset(_GDL_CHILD_KEYS)
    | _GDL_DROPPED_KEYS
    | {"break", "form", "x"}
)

__all__ = [
    "ORACC_ED3B_ARCHIVE_BYTES",
    "ORACC_ED3B_ARCHIVE_MEMBER_COUNT",
    "ORACC_ED3B_ARCHIVE_SHA256",
    "ORACC_ED3B_ARCHIVE_URL",
    "ORACC_ED3B_CATALOGUE_DOCUMENT_COUNT",
    "ORACC_ED3B_EXPECTATIONS",
    "ORACC_ED3B_GENRE",
    "ORACC_ED3B_GOLD_CLASSES",
    "ORACC_ED3B_LICENSE_ID",
    "ORACC_ED3B_LICENSE_URL",
    "ORACC_ED3B_PERIOD",
    "ORACC_ED3B_PROJECT",
    "ORACC_ED3B_PROTOCOL_SHA256",
    "ORACC_ED3B_STATES",
    "ORACC_ED3B_TRUTH_STATES",
    "ORACCEd3bError",
    "canonicalize_oracc_ed3b_observation",
    "derive_oracc_ed3b_gold_class",
    "derive_oracc_ed3b_truth_state",
    "verify_oracc_ed3b_archive",
    "verify_oracc_ed3b_protocol_bytes",
]


class ORACCEd3bError(ValueError):
    """Raised when an ORACC ED3b source archive violates the closed contract."""


@dataclass(frozen=True)
class ORACCEd3bExpectations:
    qualified_document_count: int
    qualified_lemma_token_count: int
    scorable_lemma_token_count: int
    annotation_unknown_token_count: int
    annotation_unknown_document_count: int
    selected_member_manifest_sha256: str
    effective_corpus_sha256: str
    support_commitment_sha256: str
    observation_contract_sha256: str
    minimum_tokens_per_class: int
    minimum_documents_per_class: int

    def __post_init__(self) -> None:
        if self.qualified_document_count < 1:
            raise ValueError("qualified_document_count must be positive")
        if self.qualified_lemma_token_count < 1:
            raise ValueError("qualified_lemma_token_count must be positive")
        if self.scorable_lemma_token_count < 1:
            raise ValueError("scorable_lemma_token_count must be positive")
        if self.annotation_unknown_token_count < 0:
            raise ValueError("annotation_unknown_token_count must be non-negative")
        if self.annotation_unknown_document_count < 0:
            raise ValueError("annotation_unknown_document_count must be non-negative")
        if (
            self.scorable_lemma_token_count + self.annotation_unknown_token_count
            != self.qualified_lemma_token_count
        ):
            raise ValueError("scorable and annotation-unknown token counts must be exhaustive")
        for field_name in (
            "selected_member_manifest_sha256",
            "effective_corpus_sha256",
            "support_commitment_sha256",
            "observation_contract_sha256",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or _TAGGED_SHA256.fullmatch(value) is None:
                raise ValueError(f"{field_name} must be a tagged lowercase SHA-256")
        if self.minimum_tokens_per_class < 1:
            raise ValueError("minimum_tokens_per_class must be positive")
        if self.minimum_documents_per_class < 1:
            raise ValueError("minimum_documents_per_class must be positive")


ORACC_ED3B_EXPECTATIONS: Final = ORACCEd3bExpectations(
    qualified_document_count=3_338,
    qualified_lemma_token_count=226_618,
    scorable_lemma_token_count=226_610,
    annotation_unknown_token_count=8,
    annotation_unknown_document_count=7,
    selected_member_manifest_sha256=(
        "sha256:6eda68ba7e96d7d56b2edb49b72f7727ecd3cef0519abbe8269d04b6bce034b6"
    ),
    effective_corpus_sha256=(
        "sha256:c6a745a6a397dc5492bfcdad60d91787bece7267653f3c897944459880af5342"
    ),
    support_commitment_sha256=(
        "sha256:ad6a3615420b3d37cb3d3a622393beddb02cfd6828f069879cea382644793eb8"
    ),
    observation_contract_sha256=(
        "sha256:a801e1980c2c973fb4a2ca806e2f6ec56a96fb45477d2fb63d295f6ce69eb123"
    ),
    minimum_tokens_per_class=200,
    minimum_documents_per_class=100,
)


def derive_oracc_ed3b_gold_class(fields: Mapping[str, Any]) -> GoldClass | None:
    """Apply the fixed evaluator-side four-class projection to one ORACC lemma."""

    pos = fields.get("pos")
    guide_word = fields.get("gw")
    matches: list[GoldClass] = []
    if pos == "n":
        matches.append("quantity")
    if pos == "N" and guide_word == "unit":
        matches.append("unit")
    if pos == "PN":
        matches.append("person_name")
    if pos == "SN":
        matches.append("settlement_name")
    if len(matches) > 1:
        raise ORACCEd3bError("one lemma matches multiple gold classes")
    return matches[0] if matches else None


def derive_oracc_ed3b_truth_state(fields: Mapping[str, Any]) -> TruthState:
    """Derive evaluator truth without silently treating missing annotation as negative."""

    pos = fields.get("pos")
    if pos is None:
        return "annotation_unknown"
    if not isinstance(pos, str) or not pos:
        raise ORACCEd3bError("lemma part of speech must be a non-empty string when present")
    guide_word = fields.get("gw")
    if pos == "N" and guide_word is None:
        return "annotation_unknown"
    if guide_word is not None and not isinstance(guide_word, str):
        raise ORACCEd3bError("lemma guide word must be a string when present")
    label = derive_oracc_ed3b_gold_class(fields)
    return label if label is not None else "context_only"


def canonicalize_oracc_ed3b_observation(fields: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return an annotation-key-stripped, source-separated transliteration view.

    This is not a native-glyph observation or a secrecy mechanism. The
    projection drops lemma fields and direct GDL annotation-key identities.
    Admitted transliteration payloads share one source-specific hash namespace,
    preserving equality and order without listing raw strings in model rows.
    """

    gdl = fields.get("gdl")
    if not isinstance(gdl, list) or not gdl:
        raise ORACCEd3bError("lemma gdl must be a non-empty array")
    output: list[dict[str, Any]] = []
    for item in gdl:
        output.extend(_canonicalize_gdl_node(item, inherited_damage=False))
    if not output:
        raise ORACCEd3bError("lemma GDL produces no approved observation")
    return output


def _audit_oracc_ed3b_archive(
    archive_bytes: bytes,
    *,
    expected_archive_sha256: str = ORACC_ED3B_ARCHIVE_SHA256,
    minimum_tokens_per_class: int = 1,
    minimum_documents_per_class: int = 1,
) -> dict[str, Any]:
    """Derive an internal path-free, identifier-free source audit.

    This routine performs source and parser qualification only. It does not
    construct a train/test split, fit a model, calculate a prediction metric,
    or expose document identifiers, member names, forms, signs, or labels.
    """

    if not isinstance(archive_bytes, bytes):
        raise ORACCEd3bError("archive input must be bytes")
    if not archive_bytes:
        raise ORACCEd3bError("archive input is empty")
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise ORACCEd3bError("archive input exceeds the byte limit")
    if minimum_tokens_per_class < 1 or minimum_documents_per_class < 1:
        raise ORACCEd3bError("support minima must be positive")
    if _TAGGED_SHA256.fullmatch(expected_archive_sha256) is None:
        raise ORACCEd3bError("expected archive digest is invalid")
    if _audit_exclusion_set_digest() != _AUDIT_EXCLUSION_SET_SHA256:
        raise ORACCEd3bError("audit exclusion commitment is internally inconsistent")

    archive_sha256 = _tagged_sha256(archive_bytes)
    if archive_sha256 != expected_archive_sha256:
        raise ORACCEd3bError("archive SHA-256 does not match the pinned source")

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r") as archive:
            members = archive.infolist()
            member_by_path = _validate_archive_members(members)
            catalogue = _read_json_member(
                archive,
                member_by_path,
                f"{ORACC_ED3B_PROJECT}/catalogue.json",
                max_bytes=MAX_INDEX_MEMBER_BYTES,
            )
            metadata = _read_json_member(
                archive,
                member_by_path,
                f"{ORACC_ED3B_PROJECT}/metadata.json",
                max_bytes=MAX_INDEX_MEMBER_BYTES,
            )
            glossary = _read_json_member(
                archive,
                member_by_path,
                f"{ORACC_ED3B_PROJECT}/gloss-sux.json",
                max_bytes=MAX_INDEX_MEMBER_BYTES,
            )
            _validate_embedded_header(catalogue, expected_type="catalogue")
            _validate_embedded_header(metadata, expected_type="metadata")
            _validate_embedded_header(glossary, expected_type="glossary")
            _validate_unit_glossary(glossary)

            catalogue_members = _catalogue_members(catalogue)
            lemmatized_ids = _lemmatized_ids(metadata, catalogue_members)
            corpus_member_paths = _corpus_member_paths(member_by_path)
            if set(catalogue_members) != set(corpus_member_paths):
                raise ORACCEd3bError(
                    "catalogue identifiers and corpus JSON member identifiers differ"
                )

            eligible_ids = tuple(
                sorted(
                    public_id
                    for public_id, record in catalogue_members.items()
                    if public_id in lemmatized_ids
                    and record.get("period") == ORACC_ED3B_PERIOD
                    and record.get("genre") == ORACC_ED3B_GENRE
                )
            )
            observed_exclusion_keys = {
                _audit_exclusion_key(public_id)
                for public_id in eligible_ids
                if _audit_exclusion_key(public_id) in _AUDIT_EXCLUSION_KEYS
            }
            if observed_exclusion_keys != _AUDIT_EXCLUSION_KEYS:
                raise ORACCEd3bError("audit exclusion identifiers do not match the eligible source")
            selected_ids = tuple(
                public_id
                for public_id in eligible_ids
                if _audit_exclusion_key(public_id) not in _AUDIT_EXCLUSION_KEYS
            )
            if not selected_ids:
                raise ORACCEd3bError("source selection is empty")

            result = _audit_selected_documents(
                archive,
                member_by_path,
                selected_ids,
                minimum_tokens_per_class=minimum_tokens_per_class,
                minimum_documents_per_class=minimum_documents_per_class,
            )
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise ORACCEd3bError("invalid ZIP archive") from error

    projection_sha256 = _projection_digest()
    observation_contract_sha256 = _observation_contract_digest()
    return {
        "receipt_version": "oracc-ed3b-internal-source-audit-v1",
        "terminal_status": (
            "source_qualified" if result["support_gate_passed"] else "insufficient_source_support"
        ),
        "source": {
            "project": ORACC_ED3B_PROJECT,
            "archive_url": ORACC_ED3B_ARCHIVE_URL,
            "archive_sha256": archive_sha256,
            "archive_bytes": len(archive_bytes),
            "archive_member_count": len(members),
            "catalogue_document_count": len(catalogue_members),
            "license_id": ORACC_ED3B_LICENSE_ID,
            "license_url": ORACC_ED3B_LICENSE_URL,
            "embedded_license_verified": True,
        },
        "selection": {
            "period": ORACC_ED3B_PERIOD,
            "genre": ORACC_ED3B_GENRE,
            "requires_metadata_format": "lem",
            "audit_exclusion_count": len(_AUDIT_EXCLUSION_KEYS),
            "audit_exclusion_set_sha256": _AUDIT_EXCLUSION_SET_SHA256,
            "audit_exclusion_identifiers_listed": False,
            "audit_exclusion_hash_confidentiality_claimed": False,
            "qualified_document_count": len(selected_ids),
            "selected_member_manifest_sha256": result["selected_member_manifest_sha256"],
        },
        "projection": {
            "states": list(ORACC_ED3B_STATES),
            "truth_states": list(ORACC_ED3B_TRUTH_STATES),
            "rules": {
                "quantity": 'f.pos == "n"',
                "unit": 'f.pos == "N" and f.gw == "unit"',
                "person_name": 'f.pos == "PN"',
                "settlement_name": 'f.pos == "SN"',
                "zero_matches": "context_only",
                "multiple_matches": "hard_fail",
                "missing_pos_or_required_unit_gw": "annotation_unknown",
            },
            "projection_sha256": projection_sha256,
            "qualified_lemma_token_count": result["qualified_lemma_token_count"],
            "scorable_lemma_token_count": result["scorable_lemma_token_count"],
            "annotation_unknown_token_count": result["annotation_unknown_token_count"],
            "annotation_unknown_document_count": result["annotation_unknown_document_count"],
            "effective_corpus_sha256": result["effective_corpus_sha256"],
        },
        "observation": {
            "contract_sha256": observation_contract_sha256,
            "source_atom_domain": "indusbench:oracc-ed3b:observation-atom:v1\\x00",
            "source_domain_separated_atoms": True,
            "model_row_raw_values_listed": False,
            "model_row_gdl_atom_key_identity_listed": False,
            "hash_confidentiality_claimed": False,
            "dropped_gdl_keys": sorted(_GDL_DROPPED_KEYS),
            "unknown_gdl_key": "hard_fail",
            "linguistic_role_key": "hard_fail",
        },
        "support_gate": {
            "minimum_tokens_per_class": minimum_tokens_per_class,
            "minimum_documents_per_class": minimum_documents_per_class,
            "all_classes_pass": result["support_gate_passed"],
            "support_commitment_sha256": result["support_commitment_sha256"],
            "selected_per_class_counts_listed_in_receipt": False,
            "upstream_aggregate_class_counts_previously_disclosed": True,
            "source_distribution_blindness_claimed": False,
        },
        "reservation": {
            "role": "feature_safety_exposed_prospective_validation_source",
            "candidate_model_fitting_use": "prohibited",
            "model_selection_use": "prohibited",
            "hyperparameter_tuning_use": "prohibited",
            "debugging_use": "prohibited",
            "aggregate_side_information": (
                "archive-wide and joined-source class counts were disclosed before "
                "the source freeze"
            ),
            "gold_conditioned_feature_safety_audit": (
                "class-conditioned GDL-key aggregates informed the frozen sanitizer"
            ),
            "distribution_blindness_claimed": False,
            "validation_execution": "disabled_until_separate_post_development_protocol_freeze",
            "binding_confirmation_role": "prohibited",
        },
        "scientific_nonclaims": [
            "independent_custody",
            "blindness",
            "trusted_time",
            "model_performance",
            "binding_confirmation",
            "Indus_sign_value",
            "Indus_language",
            "Indus_translation",
            "Indus_decipherment",
            "prize_eligibility",
        ],
    }


def verify_oracc_ed3b_archive(
    archive_bytes: bytes,
) -> dict[str, Any]:
    """Verify the exact archive and every frozen aggregate commitment."""

    expectations = ORACC_ED3B_EXPECTATIONS
    report = _audit_oracc_ed3b_archive(
        archive_bytes,
        expected_archive_sha256=ORACC_ED3B_ARCHIVE_SHA256,
        minimum_tokens_per_class=expectations.minimum_tokens_per_class,
        minimum_documents_per_class=expectations.minimum_documents_per_class,
    )
    if report["selection"]["qualified_document_count"] != expectations.qualified_document_count:
        raise ORACCEd3bError("qualified document count does not match the source seal")
    if (
        report["projection"]["qualified_lemma_token_count"]
        != expectations.qualified_lemma_token_count
    ):
        raise ORACCEd3bError("qualified lemma count does not match the source seal")
    for field_name in (
        "scorable_lemma_token_count",
        "annotation_unknown_token_count",
        "annotation_unknown_document_count",
    ):
        if report["projection"][field_name] != getattr(expectations, field_name):
            raise ORACCEd3bError(f"{field_name} does not match the source seal")
    commitments = {
        "selected_member_manifest_sha256": report["selection"]["selected_member_manifest_sha256"],
        "effective_corpus_sha256": report["projection"]["effective_corpus_sha256"],
        "support_commitment_sha256": report["support_gate"]["support_commitment_sha256"],
        "observation_contract_sha256": report["observation"]["contract_sha256"],
    }
    for field_name, actual in commitments.items():
        if actual != getattr(expectations, field_name):
            raise ORACCEd3bError(f"{field_name} does not match the source seal")
    if report["terminal_status"] != "source_qualified":
        raise ORACCEd3bError("source support gate failed")
    report["receipt_version"] = "oracc-ed3b-source-qualification-v1"
    return report


def verify_oracc_ed3b_protocol_bytes(protocol_bytes: bytes) -> str:
    """Verify the exact source-freeze protocol and return its tagged digest."""

    if not isinstance(protocol_bytes, bytes):
        raise ORACCEd3bError("protocol input must be bytes")
    if not protocol_bytes:
        raise ORACCEd3bError("protocol input is empty")
    if len(protocol_bytes) > MAX_PROTOCOL_BYTES:
        raise ORACCEd3bError("protocol input exceeds the byte limit")
    actual_sha256 = _tagged_sha256(protocol_bytes)
    if actual_sha256 != ORACC_ED3B_PROTOCOL_SHA256:
        raise ORACCEd3bError("protocol SHA-256 does not match the source freeze")
    value = _strict_json(protocol_bytes)
    if not isinstance(value, dict):
        raise ORACCEd3bError("protocol JSON root must be an object")
    if value.get("protocol_id") != "oracc-ed3b-validation-source-v1":
        raise ORACCEd3bError("protocol identifier does not match the source freeze")
    if (
        value.get("protocol_status")
        != "source_frozen_after_feature_safety_audit_before_v3_model_fitting"
    ):
        raise ORACCEd3bError("protocol status does not match the source freeze")
    return actual_sha256


def _validate_archive_members(
    members: Sequence[zipfile.ZipInfo],
) -> dict[str, zipfile.ZipInfo]:
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ORACCEd3bError("archive contains too many members")
    if len(members) != ORACC_ED3B_ARCHIVE_MEMBER_COUNT:
        raise ORACCEd3bError("archive member count does not match the pinned source")

    member_by_path: dict[str, zipfile.ZipInfo] = {}
    declared_uncompressed_bytes = 0
    for member in members:
        path = member.filename
        _validate_member_path(path, directory=member.is_dir())
        if path in member_by_path:
            raise ORACCEd3bError("archive contains a duplicate member path")
        member_by_path[path] = member
        if member.flag_bits & 0x1:
            raise ORACCEd3bError("encrypted archive members are not supported")
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ORACCEd3bError("symbolic links are not supported in the source archive")
        file_type = stat.S_IFMT(mode)
        if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise ORACCEd3bError("special files are not supported in the source archive")
        if not member.is_dir():
            declared_uncompressed_bytes += member.file_size
            if declared_uncompressed_bytes > MAX_DECLARED_UNCOMPRESSED_BYTES:
                raise ORACCEd3bError("archive declared uncompressed size exceeds the limit")
    return member_by_path


def _validate_member_path(path: str, *, directory: bool) -> None:
    if not isinstance(path, str) or not path:
        raise ORACCEd3bError("archive member path is empty")
    if "\x00" in path or "\\" in path or path.startswith("/"):
        raise ORACCEd3bError("archive member path is unsafe")
    components = path.split("/")
    if directory and components[-1] == "":
        components = components[:-1]
    if not components or any(component in {"", ".", ".."} for component in components):
        raise ORACCEd3bError("archive member path is unsafe")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in path):
        raise ORACCEd3bError("archive member path contains a control character")


def _read_json_member(
    archive: zipfile.ZipFile,
    member_by_path: Mapping[str, zipfile.ZipInfo],
    path: str,
    *,
    max_bytes: int,
) -> dict[str, Any]:
    member = member_by_path.get(path)
    if member is None or member.is_dir():
        raise ORACCEd3bError("required source index member is missing")
    if member.file_size > max_bytes:
        raise ORACCEd3bError("source index member exceeds the byte limit")
    raw = archive.read(member)
    if len(raw) != member.file_size:
        raise ORACCEd3bError("archive member byte size changed while reading")
    value = _strict_json(raw)
    if not isinstance(value, dict):
        raise ORACCEd3bError("source JSON root must be an object")
    return value


def _strict_json(raw: bytes) -> Any:
    if b"\x00" in raw:
        raise ORACCEd3bError("source JSON contains a NUL byte")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ORACCEd3bError("source JSON is not strict UTF-8") from error

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise ORACCEd3bError("source JSON contains a duplicate object key")
            output[key] = value
        return output

    def reject_constant(value: str) -> float:
        raise ORACCEd3bError(f"source JSON contains a non-finite number: {value}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ORACCEd3bError("source JSON contains an out-of-range number")
        return parsed

    try:
        result = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ORACCEd3bError("source JSON is invalid") from error
    _validate_json_depth(result)
    return result


def _validate_json_depth(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise ORACCEd3bError("source JSON nesting exceeds the limit")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def _validate_embedded_header(value: Mapping[str, Any], *, expected_type: str) -> None:
    expected = {
        "project": ORACC_ED3B_PROJECT,
        "license": ORACC_ED3B_LICENSE_TEXT,
        "license-url": ORACC_ED3B_LICENSE_URL,
        "type": expected_type,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise ORACCEd3bError(f"source JSON embedded {key} does not match")


def _catalogue_members(catalogue: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    members = catalogue.get("members")
    if not isinstance(members, dict):
        raise ORACCEd3bError("catalogue members must be an object")
    if len(members) != ORACC_ED3B_CATALOGUE_DOCUMENT_COUNT:
        raise ORACCEd3bError("catalogue document count does not match the pinned source")
    output: dict[str, dict[str, Any]] = {}
    for public_id, record in members.items():
        if not isinstance(public_id, str) or _PUBLIC_IDENTIFIER.fullmatch(public_id) is None:
            raise ORACCEd3bError("catalogue contains an invalid document identifier")
        if not isinstance(record, dict) or record.get("id_text") != public_id:
            raise ORACCEd3bError("catalogue member identifier is inconsistent")
        output[public_id] = record
    return output


def _validate_unit_glossary(glossary: Mapping[str, Any]) -> None:
    entries = glossary.get("entries")
    if not isinstance(entries, list):
        raise ORACCEd3bError("Sumerian glossary entries must be an array")
    unit_entries = [
        entry for entry in entries if isinstance(entry, dict) and entry.get("gw") == "unit"
    ]
    if len(unit_entries) != ORACC_ED3B_UNIT_GLOSSARY_ENTRY_COUNT:
        raise ORACCEd3bError("unit glossary entry count does not match the source seal")
    instance_count = 0
    for entry in unit_entries:
        if entry.get("pos") != "N":
            raise ORACCEd3bError("unit glossary entry has an unexpected part of speech")
        raw_count = entry.get("icount")
        if not isinstance(raw_count, str) or not raw_count.isascii() or not raw_count.isdigit():
            raise ORACCEd3bError("unit glossary entry has an invalid instance count")
        instance_count += int(raw_count)
    if instance_count != ORACC_ED3B_UNIT_GLOSSARY_INSTANCE_COUNT:
        raise ORACCEd3bError("unit glossary instance count does not match the source seal")


def _lemmatized_ids(
    metadata: Mapping[str, Any],
    catalogue_members: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    formats = metadata.get("formats")
    if not isinstance(formats, dict):
        raise ORACCEd3bError("metadata formats must be an object")
    raw_ids = formats.get("lem")
    if not isinstance(raw_ids, list):
        raise ORACCEd3bError("metadata lem format must be an array")
    output: set[str] = set()
    for public_id in raw_ids:
        if (
            not isinstance(public_id, str)
            or _PUBLIC_IDENTIFIER.fullmatch(public_id) is None
            or public_id not in catalogue_members
        ):
            raise ORACCEd3bError("metadata lem format contains an invalid identifier")
        if public_id in output:
            raise ORACCEd3bError("metadata lem format contains a duplicate identifier")
        output.add(public_id)
    return output


def _corpus_member_paths(
    member_by_path: Mapping[str, zipfile.ZipInfo],
) -> dict[str, str]:
    output: dict[str, str] = {}
    for path, member in member_by_path.items():
        match = _CORPUS_MEMBER.fullmatch(path)
        if match is None:
            continue
        if member.is_dir():
            raise ORACCEd3bError("corpus JSON member cannot be a directory")
        public_id = match.group(1)
        if public_id in output:
            raise ORACCEd3bError("duplicate corpus document identifier")
        output[public_id] = path
    return output


def _audit_selected_documents(
    archive: zipfile.ZipFile,
    member_by_path: Mapping[str, zipfile.ZipInfo],
    selected_ids: Sequence[str],
    *,
    minimum_tokens_per_class: int,
    minimum_documents_per_class: int,
) -> dict[str, Any]:
    manifest = hashlib.sha256()
    manifest.update(_MANIFEST_DOMAIN)
    _update_u64(manifest, len(selected_ids))

    effective = hashlib.sha256()
    effective.update(_EFFECTIVE_CORPUS_DOMAIN)
    _update_u64(effective, len(selected_ids))

    class_token_counts = {label: 0 for label in ORACC_ED3B_GOLD_CLASSES}
    class_document_counts = {label: 0 for label in ORACC_ED3B_GOLD_CLASSES}
    qualified_lemma_token_count = 0
    annotation_unknown_token_count = 0
    annotation_unknown_document_count = 0

    for public_id in selected_ids:
        path = f"{ORACC_ED3B_PROJECT}/corpusjson/{public_id}.json"
        member = member_by_path.get(path)
        if member is None or member.is_dir():
            raise ORACCEd3bError("qualified corpus JSON member is missing")
        if member.file_size > MAX_CORPUS_MEMBER_BYTES:
            raise ORACCEd3bError("qualified corpus JSON member exceeds the byte limit")
        raw = archive.read(member)
        if len(raw) != member.file_size:
            raise ORACCEd3bError("archive member byte size changed while reading")

        _update_framed(manifest, path.encode("ascii"))
        _update_u64(manifest, len(raw))
        manifest.update(hashlib.sha256(raw).digest())

        document = _strict_json(raw)
        if not isinstance(document, dict):
            raise ORACCEd3bError("corpus JSON root must be an object")
        _validate_embedded_header(document, expected_type="cdl")
        if document.get("textid") != public_id:
            raise ORACCEd3bError("corpus JSON text identifier is inconsistent")
        cdl = document.get("cdl")
        if not isinstance(cdl, list):
            raise ORACCEd3bError("corpus JSON cdl must be an array")

        tokens, line_count = _document_tokens(cdl)
        if not tokens or line_count < 1:
            raise ORACCEd3bError("qualified corpus document has no lemmatized line")

        _update_framed(effective, public_id.encode("ascii"))
        _update_u64(effective, line_count)
        _update_u64(effective, len(tokens))

        document_classes: set[GoldClass] = set()
        document_has_annotation_unknown = False
        for token_ordinal, (line_ordinal, fields) in enumerate(tokens):
            truth_state = derive_oracc_ed3b_truth_state(fields)
            if truth_state == "annotation_unknown":
                annotation_unknown_token_count += 1
                document_has_annotation_unknown = True
            elif truth_state != "context_only":
                class_token_counts[truth_state] += 1
                document_classes.add(truth_state)

            _update_u64(effective, token_ordinal)
            _update_u64(effective, line_ordinal)
            _update_framed(effective, truth_state.encode("ascii"))
            canonical_observation = json.dumps(
                canonicalize_oracc_ed3b_observation(fields),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            _update_framed(effective, canonical_observation)

        for label in document_classes:
            class_document_counts[label] += 1
        if document_has_annotation_unknown:
            annotation_unknown_document_count += 1
        qualified_lemma_token_count += len(tokens)

    support = hashlib.sha256()
    support.update(_SUPPORT_COMMITMENT_DOMAIN)
    for label in ORACC_ED3B_GOLD_CLASSES:
        _update_framed(support, label.encode("ascii"))
        _update_u64(support, class_token_counts[label])
        _update_u64(support, class_document_counts[label])

    support_gate_passed = all(
        class_token_counts[label] >= minimum_tokens_per_class
        and class_document_counts[label] >= minimum_documents_per_class
        for label in ORACC_ED3B_GOLD_CLASSES
    )
    return {
        "qualified_lemma_token_count": qualified_lemma_token_count,
        "scorable_lemma_token_count": (
            qualified_lemma_token_count - annotation_unknown_token_count
        ),
        "annotation_unknown_token_count": annotation_unknown_token_count,
        "annotation_unknown_document_count": annotation_unknown_document_count,
        "selected_member_manifest_sha256": f"sha256:{manifest.hexdigest()}",
        "effective_corpus_sha256": f"sha256:{effective.hexdigest()}",
        "support_commitment_sha256": f"sha256:{support.hexdigest()}",
        "support_gate_passed": support_gate_passed,
    }


def _document_tokens(
    cdl: Sequence[Any],
) -> tuple[list[tuple[int, Mapping[str, Any]]], int]:
    tokens: list[tuple[int, Mapping[str, Any]]] = []
    next_line_ordinal = 0
    current_line_ordinal: int | None = None

    def visit(items: Sequence[Any]) -> None:
        nonlocal current_line_ordinal, next_line_ordinal
        for item in items:
            if not isinstance(item, dict):
                raise ORACCEd3bError("corpus cdl node must be an object")
            node = item.get("node")
            node_type = item.get("type")
            if node == "d" and node_type == "line-start":
                current_line_ordinal = next_line_ordinal
                next_line_ordinal += 1
            if node == "l":
                if current_line_ordinal is None:
                    raise ORACCEd3bError("lemma occurs before the first line boundary")
                fields = item.get("f")
                if not isinstance(fields, dict):
                    raise ORACCEd3bError("lemma fields must be an object")
                derive_oracc_ed3b_truth_state(fields)
                canonicalize_oracc_ed3b_observation(fields)
                tokens.append((current_line_ordinal, fields))
            children = item.get("cdl")
            if children is not None:
                if not isinstance(children, list):
                    raise ORACCEd3bError("nested cdl must be an array")
                visit(children)

    visit(cdl)
    return tokens, next_line_ordinal


def _projection_digest() -> str:
    digest = hashlib.sha256()
    digest.update(_PROJECTION_DOMAIN)
    rules = (
        ("quantity", 'f.pos == "n"'),
        ("unit", 'f.pos == "N" and f.gw == "unit"'),
        ("person_name", 'f.pos == "PN"'),
        ("settlement_name", 'f.pos == "SN"'),
        ("zero_matches", "context_only"),
        ("multiple_matches", "hard_fail"),
        ("missing_pos_or_required_unit_gw", "annotation_unknown"),
    )
    for label, rule in rules:
        _update_framed(digest, label.encode("ascii"))
        _update_framed(digest, rule.encode("ascii"))
    return f"sha256:{digest.hexdigest()}"


def _canonicalize_gdl_node(
    value: Any,
    *,
    inherited_damage: bool,
) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise ORACCEd3bError("GDL node must be a non-empty object")
    keys = set(value)
    if not all(isinstance(key, str) for key in keys):
        raise ORACCEd3bError("GDL node keys must be strings")
    unknown_keys = keys - _GDL_ALLOWED_KEYS
    if unknown_keys:
        raise ORACCEd3bError("GDL node contains an unapproved key")

    for key in _GDL_DROPPED_KEYS - {"mods"}:
        if key not in value:
            continue
        dropped_value = value[key]
        if not isinstance(dropped_value, str) or not dropped_value:
            raise ORACCEd3bError("dropped GDL metadata must be a non-empty string")
    if "mods" in value:
        modifiers = value["mods"]
        if not isinstance(modifiers, list) or not modifiers:
            raise ORACCEd3bError("dropped GDL modifiers must be a non-empty array")
        if not all(isinstance(item, dict) and item for item in modifiers):
            raise ORACCEd3bError("dropped GDL modifier entries must be objects")
    if "form" in value and (not isinstance(value["form"], str) or not value["form"]):
        raise ORACCEd3bError("GDL form must be a non-empty string")

    node_damage = inherited_damage
    if "break" in value:
        raw_break = value["break"]
        if raw_break not in {"damaged", "missing"}:
            raise ORACCEd3bError("GDL break value is outside the closed contract")
        node_damage = True

    atom_keys = [key for key in _GDL_ATOM_KEYS if key in value]
    if len(atom_keys) > 1:
        raise ORACCEd3bError("GDL node contains multiple atomic payloads")
    for key in _GDL_CHILD_KEYS:
        if key in value and (not isinstance(value[key], list) or not value[key]):
            raise ORACCEd3bError("GDL child container must be a non-empty array")

    atom_key: str | None = atom_keys[0] if atom_keys else None
    if atom_key is None and "form" in value:
        numeric_form = "n" in value and "seq" in value
        modified_form = "mods" in value
        if not numeric_form and not modified_form:
            raise ORACCEd3bError("GDL form is outside the closed numeric or modified shape")
        atom_key = "form"

    if atom_key is not None:
        raw_atom = value[atom_key]
        if not isinstance(raw_atom, str) or not raw_atom:
            raise ORACCEd3bError("GDL atom must be a non-empty string")
        observation: dict[str, Any] = {
            "atom": hashlib.sha256(_OBSERVATION_ATOM_DOMAIN + raw_atom.encode("utf-8")).hexdigest()
        }
        if node_damage:
            observation["damaged"] = True
        return [observation]

    if "x" in value:
        raw_gap = value["x"]
        if raw_gap not in {"ellipsis", "newline"}:
            raise ORACCEd3bError("GDL gap value is outside the closed contract")
        observation = {"gap": True}
        if node_damage:
            observation["damaged"] = True
        return [observation]

    child_keys = [key for key in _GDL_CHILD_KEYS if key in value]
    if len(child_keys) != 1:
        raise ORACCEd3bError("GDL wrapper must contain exactly one approved child container")
    output: list[dict[str, Any]] = []
    for child in value[child_keys[0]]:
        output.extend(_canonicalize_gdl_node(child, inherited_damage=node_damage))
    if not output:
        raise ORACCEd3bError("GDL wrapper produces no approved observation")
    return output


def _observation_contract_digest() -> str:
    digest = hashlib.sha256()
    digest.update(_OBSERVATION_CONTRACT_DOMAIN)
    rules = (
        ("atom_domain", "indusbench:oracc-ed3b:observation-atom:v1\\x00"),
        ("ordinary_atom_precedence", ",".join(_GDL_ATOM_KEYS)),
        ("form_atom_scope", "n+form+seq_or_form+mods_only"),
        ("child_precedence", ",".join(_GDL_CHILD_KEYS)),
        ("dropped_keys", ",".join(sorted(_GDL_DROPPED_KEYS))),
        ("gap_values", "ellipsis,newline"),
        ("damage_values_collapsed", "damaged,missing"),
        ("unknown_key", "hard_fail"),
        ("multiple_atom_or_child_keys", "hard_fail"),
        ("atom_output", "one_sha256_hex_without_source_key_identity"),
        ("unicode_normalization", "none"),
    )
    for label, rule in rules:
        _update_framed(digest, label.encode("ascii"))
        _update_framed(digest, rule.encode("ascii"))
    return f"sha256:{digest.hexdigest()}"


def _audit_exclusion_key(public_id: str) -> str:
    return hashlib.sha256(_AUDIT_EXCLUSION_ID_DOMAIN + public_id.encode("ascii")).hexdigest()


def _audit_exclusion_set_digest() -> str:
    digest = hashlib.sha256()
    digest.update(b"indusbench:oracc-ed3b:audit-exclusion-set:v1\x00")
    _update_u64(digest, len(_AUDIT_EXCLUSION_KEYS))
    for key in sorted(_AUDIT_EXCLUSION_KEYS):
        _update_framed(digest, key.encode("ascii"))
    return f"sha256:{digest.hexdigest()}"


def _tagged_sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _update_u64(digest: Any, value: int) -> None:
    if value < 0 or value >= 2**64:
        raise ORACCEd3bError("digest integer is out of range")
    digest.update(value.to_bytes(8, byteorder="big", signed=False))


def _update_framed(digest: Any, raw: bytes) -> None:
    _update_u64(digest, len(raw))
    digest.update(raw)
