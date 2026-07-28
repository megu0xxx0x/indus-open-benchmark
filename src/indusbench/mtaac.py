"""Strict, network-free adapter for the pinned MTAAC morphology gold corpus.

The adapter targets one public upstream revision but never fetches it.  Callers
must provide either archive bytes or a mapping of relative paths to bytes.  The
raw seven-column annotations and the model-facing observations are represented
by different frozen data classes: the latter contain only opaque, exact-FORM
word-token hashes and row order.  In particular, source identifiers and gold
annotation columns are not model features.

``sign_id`` is retained as the cross-benchmark field name.  For MTAAC it denotes
an opaque hash of one complete FORM word token; it is not a claim that the FORM
has been segmented into individual cuneiform signs.
"""

from __future__ import annotations

import hashlib
import io
import re
import stat
import tarfile
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

MTAAC_REPOSITORY_URL = "https://github.com/cdli-gh/mtaac_gold_corpus"
MTAAC_PINNED_COMMIT = "66e0643efd230401210e27db353ebb6d7228b1bb"
MTAAC_PINNED_TREE_URL = f"{MTAAC_REPOSITORY_URL}/tree/{MTAAC_PINNED_COMMIT}/morph/to_dict"
MTAAC_PINNED_ARCHIVE_URL = f"{MTAAC_REPOSITORY_URL}/archive/{MTAAC_PINNED_COMMIT}.tar.gz"
MTAAC_PINNED_ARCHIVE_SHA256 = (
    "sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091"
)
MTAAC_PINNED_SELECTED_MANIFEST_SHA256 = (
    "sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e"
)
MTAAC_LICENSE_ID = "CC0-1.0"
MTAAC_LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
MTAAC_ATTRIBUTION = "MTAAC Contributors"
MTAAC_CORPUS_GLOB = "morph/to_dict/*.conll"
MTAAC_COLUMNS = ("ID", "FORM", "SEGM", "XPOSTAG", "HEAD", "DEPREL", "MISC")

# Public diagnostics for the pinned revision.  The 7-column figures are not
# admissions: four otherwise 7-column documents contain duplicate token
# positions and are consequently quarantined by the strict adapter.
MTAAC_PINNED_SELECTED_DOCUMENT_COUNT = 371
MTAAC_PINNED_ROW_SHAPE_DOCUMENT_COUNT = 365
MTAAC_PINNED_ROW_SHAPE_TOKEN_COUNT = 15_196
MTAAC_PINNED_STRICT_DOCUMENT_COUNT = 361
MTAAC_PINNED_STRICT_TOKEN_COUNT = 15_038
MTAAC_PINNED_ROW_SHAPE_CLASS_COUNTS = (
    ("quantity", 3_179),
    ("unit", 1_815),
    ("person_name", 1_492),
    ("settlement_name", 330),
)
MTAAC_PINNED_STRICT_CLASS_COUNTS = (
    ("quantity", 3_145),
    ("unit", 1_794),
    ("person_name", 1_479),
    ("settlement_name", 325),
)

MTAAC_GOLD_CLASSES = ("quantity", "unit", "person_name", "settlement_name")
MTAAC_OPAQUE_FORM_SCHEME = "mtaac-word-form-sha256-v1"
MTAAC_OPAQUE_DOCUMENT_SCHEME = "mtaac-document-source-id-sha256-v1"
MTAAC_OPAQUE_TOKEN_SCHEME = "mtaac-token-source-order-sha256-v1"

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10_000
MAX_SELECTED_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_SELECTED_TOTAL_BYTES = 128 * 1024 * 1024

GoldClass = Literal["quantity", "unit", "person_name", "settlement_name"]
InputKind = Literal["archive_zip", "archive_tar", "directory_mapping"]

_P_IDENTIFIER = re.compile(r"^P[0-9]{6}$")
_PINNED_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_TAGGED_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_NEW_TEXT = re.compile(r"^#new_text=(P[0-9]{6})$")
_QUANTITY_TAG = re.compile(r"^NU(?:[.]|$)")
_PERSON_NAME_TAG = re.compile(r"^PN(?:[.]|$)")
_SETTLEMENT_NAME_TAG = re.compile(r"^SN(?:[.]|$)")
_HEADER = "# " + "\t".join(MTAAC_COLUMNS)
_FORM_HASH_DOMAIN = b"indusbench:mtaac:word-form:v1\x00"
_DOCUMENT_HASH_DOMAIN = b"indusbench:mtaac:document-source-id:v1\x00"
_TOKEN_HASH_DOMAIN = b"indusbench:mtaac:token-source-order:v1\x00"
_MAPPING_HASH_DOMAIN = b"indusbench:mtaac:directory-mapping:v1\x00"
_MANIFEST_HASH_DOMAIN = b"indusbench:mtaac:selected-manifest:v1\x00"


class MTAACError(ValueError):
    """Raised when the caller-supplied corpus container is unsafe or ambiguous."""


@dataclass(frozen=True, slots=True)
class MTAACModelToken:
    """One model-facing word token with no raw or gold annotation field."""

    token_key: str
    sign_id: str
    visual_index: int


@dataclass(frozen=True, slots=True)
class MTAACModelDocument:
    """Model-facing document grouped by an opaque key, never by a P identifier."""

    document_key: str
    tokens: tuple[MTAACModelToken, ...]


@dataclass(frozen=True, slots=True)
class MTAACGoldToken:
    """Raw source columns and derived labels kept outside the model view."""

    token_key: str
    source_line_number: int
    position: str
    form: str
    segm: str
    xpostag: str
    head: str
    deprel: str
    misc: str
    classes: tuple[GoldClass, ...]


@dataclass(frozen=True, slots=True)
class MTAACGoldDocument:
    """Auditable source/gold sidecar for one strictly admitted document."""

    document_key: str
    p_identifier: str
    input_path: str
    corpus_path: str
    source_bytes: int
    source_sha256: str
    tokens: tuple[MTAACGoldToken, ...]


@dataclass(frozen=True, slots=True)
class MTAACQuarantinedDocument:
    """Whole-document quarantine without copying the malformed source line."""

    input_path: str
    corpus_path: str
    source_bytes: int
    source_sha256: str
    reason_code: str
    source_line_number: int | None


@dataclass(frozen=True, slots=True)
class MTAACProvenance:
    """Container and selection commitments plus staged admission counts."""

    repository_url: str
    adapter_target_commit: str
    license_id: str
    license_url: str
    attribution: str
    corpus_glob: str
    input_kind: InputKind
    input_sha256: str
    caller_digest_verified: bool
    selected_manifest_sha256: str
    selected_document_count: int
    row_shape_document_count: int
    row_shape_token_count: int
    admitted_document_count: int
    admitted_token_count: int
    quarantined_document_count: int
    revision_attestation: Literal["target_only_caller_bytes_not_git_attested"]


@dataclass(frozen=True, slots=True)
class MTAACCorpus:
    """Strict adapter result with structurally separate observation and gold views."""

    provenance: MTAACProvenance
    model_documents: tuple[MTAACModelDocument, ...]
    gold_documents: tuple[MTAACGoldDocument, ...]
    quarantined_documents: tuple[MTAACQuarantinedDocument, ...]
    row_shape_class_counts: tuple[tuple[GoldClass, int], ...]
    admitted_class_counts: tuple[tuple[GoldClass, int], ...]


@dataclass(frozen=True, slots=True)
class _InputEntry:
    input_path: str
    corpus_path: str
    root_prefix: tuple[str, ...]
    raw: bytes


@dataclass(frozen=True, slots=True)
class _RowShape:
    valid: bool
    token_count: int
    class_counts: tuple[tuple[GoldClass, int], ...]
    first_bad_line: int | None


class _DocumentProblem(Exception):
    def __init__(self, reason_code: str, line_number: int | None = None) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.line_number = line_number


def opaque_form_sign_id(form: str) -> str:
    """Return an opaque deterministic ID for the exact UTF-8 FORM value.

    No Unicode normalization, case folding, transliteration parsing, lemma
    extraction, or sign segmentation is performed.
    """

    if not isinstance(form, str) or not form:
        raise MTAACError("FORM must be a non-empty string")
    if _contains_forbidden_control(form):
        raise MTAACError("FORM contains a forbidden control character")
    digest = hashlib.sha256(_FORM_HASH_DOMAIN + form.encode("utf-8")).hexdigest()
    return f"{MTAAC_OPAQUE_FORM_SCHEME}:{digest}"


def opaque_document_key(p_identifier: str) -> str:
    """Return a gold-independent family key for one validated source ID."""

    if not isinstance(p_identifier, str) or _P_IDENTIFIER.fullmatch(p_identifier) is None:
        raise MTAACError("source document identifier must match P followed by six digits")
    digest = hashlib.sha256(_DOCUMENT_HASH_DOMAIN + p_identifier.encode("ascii")).hexdigest()
    return f"{MTAAC_OPAQUE_DOCUMENT_SCHEME}:{digest}"


def opaque_token_key(document_key: str, visual_index: int) -> str:
    """Return a gold-independent token key from family identity and source order."""

    prefix = f"{MTAAC_OPAQUE_DOCUMENT_SCHEME}:"
    suffix = (
        document_key.removeprefix(prefix)
        if isinstance(document_key, str) and document_key.startswith(prefix)
        else ""
    )
    if re.fullmatch(r"[0-9a-f]{64}", suffix) is None:
        raise MTAACError("document key does not match the opaque source-ID scheme")
    if (
        isinstance(visual_index, bool)
        or not isinstance(visual_index, int)
        or not 0 <= visual_index < 1 << 64
    ):
        raise MTAACError("visual index must be an unsigned 64-bit integer")
    document_bytes = document_key.encode("ascii")
    material = (
        _TOKEN_HASH_DOMAIN
        + len(document_bytes).to_bytes(8, "big")
        + document_bytes
        + visual_index.to_bytes(8, "big")
    )
    return f"{MTAAC_OPAQUE_TOKEN_SCHEME}:{hashlib.sha256(material).hexdigest()}"


def derive_mtaac_gold_classes(segm: str, xpostag: str) -> tuple[GoldClass, ...]:
    """Derive the four mechanical gold markers without interpreting SEGM roots."""

    if not isinstance(segm, str) or not isinstance(xpostag, str):
        raise MTAACError("SEGM and XPOSTAG must be strings")
    classes: list[GoldClass] = []
    if _QUANTITY_TAG.match(xpostag):
        classes.append("quantity")
    if "[unit]" in segm:
        classes.append("unit")
    if _PERSON_NAME_TAG.match(xpostag):
        classes.append("person_name")
    if _SETTLEMENT_NAME_TAG.match(xpostag):
        classes.append("settlement_name")
    return tuple(classes)


def parse_mtaac_directory(
    files: Mapping[str, bytes],
    *,
    expected_input_sha256: str | None = None,
) -> MTAACCorpus:
    """Parse caller-supplied relative-path bytes without filesystem access."""

    if not isinstance(files, Mapping):
        raise MTAACError("directory input must be a mapping of relative paths to bytes")
    raw_entries: list[tuple[str, bytes]] = []
    for path, raw in files.items():
        if not isinstance(path, str):
            raise MTAACError("directory input paths must be strings")
        _validate_input_path(path, directory=False)
        if not isinstance(raw, bytes):
            raise MTAACError("directory input values must be bytes")
        raw_entries.append((path, raw))
    raw_entries.sort(key=lambda item: item[0])
    input_sha256 = _mapping_digest(raw_entries)
    _verify_expected_digest(expected_input_sha256, input_sha256)
    selected = _select_entries(raw_entries)
    return _parse_selected_entries(
        selected,
        input_kind="directory_mapping",
        input_sha256=input_sha256,
        caller_digest_verified=expected_input_sha256 is not None,
    )


def parse_mtaac_archive(
    archive_bytes: bytes,
    *,
    expected_input_sha256: str | None = None,
) -> MTAACCorpus:
    """Parse a caller-supplied ZIP or TAR-family archive entirely in memory."""

    if not isinstance(archive_bytes, bytes):
        raise MTAACError("archive input must be bytes")
    if not archive_bytes:
        raise MTAACError("archive input is empty")
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise MTAACError("archive input exceeds the byte limit")
    input_sha256 = _tagged_sha256(archive_bytes)
    _verify_expected_digest(expected_input_sha256, input_sha256)

    buffer = io.BytesIO(archive_bytes)
    if zipfile.is_zipfile(buffer):
        raw_entries = _read_zip_entries(archive_bytes)
        input_kind: InputKind = "archive_zip"
    else:
        raw_entries = _read_tar_entries(archive_bytes)
        input_kind = "archive_tar"
    selected = _select_entries(raw_entries)
    return _parse_selected_entries(
        selected,
        input_kind=input_kind,
        input_sha256=input_sha256,
        caller_digest_verified=expected_input_sha256 is not None,
    )


def _parse_selected_entries(
    selected: Sequence[_InputEntry],
    *,
    input_kind: InputKind,
    input_sha256: str,
    caller_digest_verified: bool,
) -> MTAACCorpus:
    if not _PINNED_COMMIT.fullmatch(MTAAC_PINNED_COMMIT):
        raise AssertionError("invalid pinned MTAAC commit constant")
    selected_manifest_sha256 = _selected_manifest_digest(selected)
    model_documents: list[MTAACModelDocument] = []
    gold_documents: list[MTAACGoldDocument] = []
    quarantined: list[MTAACQuarantinedDocument] = []
    row_shape_document_count = 0
    row_shape_token_count = 0
    row_shape_counts = _empty_class_counts()
    admitted_counts = _empty_class_counts()
    form_by_sign_id: dict[str, str] = {}

    for entry in selected:
        source_digest = _tagged_sha256(entry.raw)
        try:
            lines = _decode_document(entry.raw)
        except _DocumentProblem as problem:
            quarantined.append(_quarantine(entry, source_digest, problem))
            continue

        shape = _inspect_row_shape(lines)
        if not shape.valid:
            reason_code = (
                "non_7_column_row" if shape.first_bad_line is not None else "no_token_rows"
            )
            quarantined.append(
                _quarantine(
                    entry,
                    source_digest,
                    _DocumentProblem(reason_code, shape.first_bad_line),
                )
            )
            continue
        row_shape_document_count += 1
        row_shape_token_count += shape.token_count
        _merge_counts(row_shape_counts, shape.class_counts)

        try:
            model, gold = _parse_well_shaped_document(entry, lines, source_digest)
        except _DocumentProblem as problem:
            quarantined.append(_quarantine(entry, source_digest, problem))
            continue
        for model_token, gold_token in zip(model.tokens, gold.tokens, strict=True):
            previous_form = form_by_sign_id.setdefault(model_token.sign_id, gold_token.form)
            if previous_form != gold_token.form:
                raise MTAACError("opaque FORM identifier collision")
        model_documents.append(model)
        gold_documents.append(gold)
        for token in gold.tokens:
            for gold_class in token.classes:
                admitted_counts[gold_class] += 1

    model_documents.sort(key=lambda item: item.document_key)
    gold_documents.sort(key=lambda item: item.document_key)
    quarantined.sort(key=lambda item: item.corpus_path)
    admitted_token_count = sum(len(document.tokens) for document in model_documents)
    provenance = MTAACProvenance(
        repository_url=MTAAC_REPOSITORY_URL,
        adapter_target_commit=MTAAC_PINNED_COMMIT,
        license_id=MTAAC_LICENSE_ID,
        license_url=MTAAC_LICENSE_URL,
        attribution=MTAAC_ATTRIBUTION,
        corpus_glob=MTAAC_CORPUS_GLOB,
        input_kind=input_kind,
        input_sha256=input_sha256,
        caller_digest_verified=caller_digest_verified,
        selected_manifest_sha256=selected_manifest_sha256,
        selected_document_count=len(selected),
        row_shape_document_count=row_shape_document_count,
        row_shape_token_count=row_shape_token_count,
        admitted_document_count=len(model_documents),
        admitted_token_count=admitted_token_count,
        quarantined_document_count=len(quarantined),
        revision_attestation="target_only_caller_bytes_not_git_attested",
    )
    return MTAACCorpus(
        provenance=provenance,
        model_documents=tuple(model_documents),
        gold_documents=tuple(gold_documents),
        quarantined_documents=tuple(quarantined),
        row_shape_class_counts=_ordered_counts(row_shape_counts),
        admitted_class_counts=_ordered_counts(admitted_counts),
    )


def _parse_well_shaped_document(
    entry: _InputEntry,
    lines: Sequence[str],
    source_sha256: str,
) -> tuple[MTAACModelDocument, MTAACGoldDocument]:
    filename = entry.corpus_path.rsplit("/", 1)[-1]
    filename_stem = filename.removesuffix(".conll")
    if not _P_IDENTIFIER.fullmatch(filename_stem):
        raise _DocumentProblem("invalid_p_identifier")
    if len(lines) < 2:
        raise _DocumentProblem("missing_new_text", 1)

    directive_fields = lines[0].split("\t")
    directive_match = _NEW_TEXT.fullmatch(directive_fields[0])
    if directive_match is None or any(field != "" for field in directive_fields[1:]):
        raise _DocumentProblem("invalid_new_text", 1)
    p_identifier = directive_match.group(1)
    if p_identifier != filename_stem:
        raise _DocumentProblem("p_identifier_mismatch", 1)
    if lines[1] != _HEADER:
        raise _DocumentProblem("invalid_column_header", 2)

    document_key = opaque_document_key(p_identifier)
    model_tokens: list[MTAACModelToken] = []
    gold_tokens: list[MTAACGoldToken] = []
    positions: set[str] = set()
    for line_number, line in enumerate(lines[2:], start=3):
        if line == "":
            continue
        if line.startswith("#"):
            raise _DocumentProblem("unsupported_comment", line_number)
        fields = line.split("\t")
        if len(fields) != len(MTAAC_COLUMNS):
            raise _DocumentProblem("non_7_column_row", line_number)
        position, form, segm, xpostag, head, deprel, misc = fields
        if not position or position.strip() != position:
            raise _DocumentProblem("invalid_token_position", line_number)
        if position in positions:
            raise _DocumentProblem("duplicate_token_position", line_number)
        positions.add(position)
        if not form or form.strip() != form:
            raise _DocumentProblem("invalid_form", line_number)
        if any(_contains_forbidden_control(field) for field in fields):
            raise _DocumentProblem("forbidden_control_character", line_number)

        visual_index = len(model_tokens)
        token_key = opaque_token_key(document_key, visual_index)
        classes = derive_mtaac_gold_classes(segm, xpostag)
        if len(classes) > 1:
            raise _DocumentProblem("overlapping_gold_classes", line_number)
        model_tokens.append(
            MTAACModelToken(
                token_key=token_key,
                sign_id=opaque_form_sign_id(form),
                visual_index=visual_index,
            )
        )
        gold_tokens.append(
            MTAACGoldToken(
                token_key=token_key,
                source_line_number=line_number,
                position=position,
                form=form,
                segm=segm,
                xpostag=xpostag,
                head=head,
                deprel=deprel,
                misc=misc,
                classes=classes,
            )
        )
    if not model_tokens:
        raise _DocumentProblem("no_token_rows")
    return (
        MTAACModelDocument(document_key=document_key, tokens=tuple(model_tokens)),
        MTAACGoldDocument(
            document_key=document_key,
            p_identifier=p_identifier,
            input_path=entry.input_path,
            corpus_path=entry.corpus_path,
            source_bytes=len(entry.raw),
            source_sha256=source_sha256,
            tokens=tuple(gold_tokens),
        ),
    )


def _decode_document(raw: bytes) -> list[str]:
    if len(raw) > MAX_SELECTED_DOCUMENT_BYTES:
        raise _DocumentProblem("document_byte_limit_exceeded")
    if b"\x00" in raw:
        raise _DocumentProblem("forbidden_nul_byte")
    normalized = raw.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise _DocumentProblem("invalid_line_ending")
    try:
        text = normalized.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise _DocumentProblem("invalid_utf8") from error
    if _contains_forbidden_control(text, allow_tab_and_newline=True):
        raise _DocumentProblem("forbidden_control_character")
    return text.split("\n")


def _inspect_row_shape(lines: Sequence[str]) -> _RowShape:
    rows: list[list[str]] = []
    first_bad_line: int | None = None
    for line_number, line in enumerate(lines, start=1):
        if line == "" or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != len(MTAAC_COLUMNS):
            first_bad_line = line_number
            break
        rows.append(fields)
    if first_bad_line is not None or not rows:
        return _RowShape(
            valid=False,
            token_count=0,
            class_counts=_ordered_counts(_empty_class_counts()),
            first_bad_line=first_bad_line,
        )
    counts = _empty_class_counts()
    for fields in rows:
        for gold_class in derive_mtaac_gold_classes(fields[2], fields[3]):
            counts[gold_class] += 1
    return _RowShape(
        valid=True,
        token_count=len(rows),
        class_counts=_ordered_counts(counts),
        first_bad_line=None,
    )


def _select_entries(raw_entries: Sequence[tuple[str, bytes]]) -> tuple[_InputEntry, ...]:
    selected: list[_InputEntry] = []
    canonical_paths: set[str] = set()
    total_bytes = 0
    for input_path, raw in raw_entries:
        parts = tuple(input_path.split("/"))
        if (
            len(parts) < 3
            or parts[-3:-1] != ("morph", "to_dict")
            or not parts[-1].endswith(".conll")
        ):
            continue
        corpus_path = "/".join(parts[-3:])
        if corpus_path in canonical_paths:
            raise MTAACError("duplicate selected corpus path")
        canonical_paths.add(corpus_path)
        total_bytes += len(raw)
        if len(raw) > MAX_SELECTED_DOCUMENT_BYTES:
            raise MTAACError("selected document exceeds the byte limit")
        if total_bytes > MAX_SELECTED_TOTAL_BYTES:
            raise MTAACError("selected corpus exceeds the byte limit")
        selected.append(
            _InputEntry(
                input_path=input_path,
                corpus_path=corpus_path,
                root_prefix=parts[:-3],
                raw=raw,
            )
        )
    if not selected:
        raise MTAACError(f"input contains no files matching {MTAAC_CORPUS_GLOB}")
    root_prefixes = {entry.root_prefix for entry in selected}
    if len(root_prefixes) != 1:
        raise MTAACError("selected documents come from multiple corpus roots")
    selected.sort(key=lambda entry: entry.corpus_path)
    return tuple(selected)


def _read_zip_entries(archive_bytes: bytes) -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []
    seen_paths: set[str] = set()
    selected_total_bytes = 0
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r") as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise MTAACError("archive contains too many members")
            for member in members:
                path = member.filename
                _validate_input_path(path, directory=member.is_dir())
                if path in seen_paths:
                    raise MTAACError("archive contains a duplicate member path")
                seen_paths.add(path)
                if member.is_dir():
                    continue
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    if _path_is_selected(path):
                        raise MTAACError("selected archive member is a symbolic link")
                    continue
                if member.flag_bits & 0x1:
                    raise MTAACError("encrypted archive members are not supported")
                if not _path_is_selected(path):
                    continue
                if member.file_size > MAX_SELECTED_DOCUMENT_BYTES:
                    raise MTAACError("selected document exceeds the byte limit")
                selected_total_bytes += member.file_size
                if selected_total_bytes > MAX_SELECTED_TOTAL_BYTES:
                    raise MTAACError("selected corpus exceeds the byte limit")
                raw = archive.read(member)
                if len(raw) != member.file_size:
                    raise MTAACError("archive member byte size changed while reading")
                entries.append((path, raw))
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise MTAACError("invalid ZIP archive") from error
    return entries


def _read_tar_entries(archive_bytes: bytes) -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []
    seen_paths: set[str] = set()
    selected_total_bytes = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as archive:
            members = archive.getmembers()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise MTAACError("archive contains too many members")
            for member in members:
                path = member.name
                _validate_input_path(path, directory=member.isdir())
                if path in seen_paths:
                    raise MTAACError("archive contains a duplicate member path")
                seen_paths.add(path)
                if member.isdir():
                    continue
                if not _path_is_selected(path):
                    continue
                if not member.isfile():
                    raise MTAACError("selected archive member is not a regular file")
                if member.size > MAX_SELECTED_DOCUMENT_BYTES:
                    raise MTAACError("selected document exceeds the byte limit")
                selected_total_bytes += member.size
                if selected_total_bytes > MAX_SELECTED_TOTAL_BYTES:
                    raise MTAACError("selected corpus exceeds the byte limit")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise MTAACError("selected archive member could not be read")
                raw = extracted.read(MAX_SELECTED_DOCUMENT_BYTES + 1)
                if len(raw) != member.size:
                    raise MTAACError("archive member byte size changed while reading")
                entries.append((path, raw))
    except (OSError, tarfile.TarError) as error:
        raise MTAACError("input is neither a valid ZIP nor TAR archive") from error
    return entries


def _validate_input_path(path: str, *, directory: bool) -> None:
    if not path:
        raise MTAACError("input contains an empty path")
    candidate = path[:-1] if directory and path.endswith("/") else path
    if not candidate or candidate.startswith("/") or "\\" in candidate:
        raise MTAACError("input path is not a safe relative POSIX path")
    components = candidate.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise MTAACError("input path is not a safe relative POSIX path")
    if _contains_forbidden_control(candidate):
        raise MTAACError("input path contains a forbidden control character")


def _path_is_selected(path: str) -> bool:
    candidate = path[:-1] if path.endswith("/") else path
    parts = candidate.split("/")
    return (
        len(parts) >= 3
        and tuple(parts[-3:-1]) == ("morph", "to_dict")
        and parts[-1].endswith(".conll")
    )


def _mapping_digest(entries: Sequence[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    digest.update(_MAPPING_HASH_DOMAIN)
    for path, raw in entries:
        _update_length_prefixed(digest, path.encode("utf-8"))
        _update_length_prefixed(digest, raw)
    return "sha256:" + digest.hexdigest()


def _selected_manifest_digest(entries: Sequence[_InputEntry]) -> str:
    digest = hashlib.sha256()
    digest.update(_MANIFEST_HASH_DOMAIN)
    for entry in entries:
        _update_length_prefixed(digest, entry.corpus_path.encode("utf-8"))
        digest.update(len(entry.raw).to_bytes(8, "big"))
        digest.update(hashlib.sha256(entry.raw).digest())
    return "sha256:" + digest.hexdigest()


def _update_length_prefixed(digest: object, value: bytes) -> None:
    if not hasattr(digest, "update"):
        raise AssertionError("digest object does not provide update")
    digest.update(len(value).to_bytes(8, "big"))  # type: ignore[attr-defined]
    digest.update(value)  # type: ignore[attr-defined]


def _tagged_sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _verify_expected_digest(expected: str | None, actual: str) -> None:
    if expected is None:
        return
    if not isinstance(expected, str) or not _TAGGED_SHA256.fullmatch(expected):
        raise MTAACError("expected input digest must be tagged lowercase SHA-256")
    if expected != actual:
        raise MTAACError("caller-supplied input digest does not match the bytes")


def _contains_forbidden_control(value: str, *, allow_tab_and_newline: bool = False) -> bool:
    allowed = {"\t", "\n"} if allow_tab_and_newline else set()
    return any(
        (ord(character) < 32 or ord(character) == 127) and character not in allowed
        for character in value
    )


def _empty_class_counts() -> dict[GoldClass, int]:
    return {gold_class: 0 for gold_class in MTAAC_GOLD_CLASSES}


def _ordered_counts(counts: Mapping[GoldClass, int]) -> tuple[tuple[GoldClass, int], ...]:
    return tuple((gold_class, counts[gold_class]) for gold_class in MTAAC_GOLD_CLASSES)


def _merge_counts(
    destination: dict[GoldClass, int],
    source: Sequence[tuple[GoldClass, int]],
) -> None:
    for gold_class, count in source:
        destination[gold_class] += count


def _quarantine(
    entry: _InputEntry,
    source_sha256: str,
    problem: _DocumentProblem,
) -> MTAACQuarantinedDocument:
    return MTAACQuarantinedDocument(
        input_path=entry.input_path,
        corpus_path=entry.corpus_path,
        source_bytes=len(entry.raw),
        source_sha256=source_sha256,
        reason_code=problem.reason_code,
        source_line_number=problem.line_number,
    )


__all__ = [
    "MTAAC_ATTRIBUTION",
    "MTAAC_COLUMNS",
    "MTAAC_CORPUS_GLOB",
    "MTAAC_GOLD_CLASSES",
    "MTAAC_LICENSE_ID",
    "MTAAC_LICENSE_URL",
    "MTAAC_OPAQUE_FORM_SCHEME",
    "MTAAC_PINNED_ARCHIVE_SHA256",
    "MTAAC_PINNED_ARCHIVE_URL",
    "MTAAC_PINNED_COMMIT",
    "MTAAC_PINNED_ROW_SHAPE_CLASS_COUNTS",
    "MTAAC_PINNED_ROW_SHAPE_DOCUMENT_COUNT",
    "MTAAC_PINNED_ROW_SHAPE_TOKEN_COUNT",
    "MTAAC_PINNED_SELECTED_DOCUMENT_COUNT",
    "MTAAC_PINNED_SELECTED_MANIFEST_SHA256",
    "MTAAC_PINNED_STRICT_CLASS_COUNTS",
    "MTAAC_PINNED_STRICT_DOCUMENT_COUNT",
    "MTAAC_PINNED_STRICT_TOKEN_COUNT",
    "MTAAC_PINNED_TREE_URL",
    "MTAAC_REPOSITORY_URL",
    "MTAACCorpus",
    "MTAACError",
    "MTAACGoldDocument",
    "MTAACGoldToken",
    "MTAACModelDocument",
    "MTAACModelToken",
    "MTAACProvenance",
    "MTAACQuarantinedDocument",
    "derive_mtaac_gold_classes",
    "opaque_document_key",
    "opaque_form_sign_id",
    "opaque_token_key",
    "parse_mtaac_archive",
    "parse_mtaac_directory",
]
