from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

from indusbench.schema_validation import validate_schema_instance
from indusbench.smithsonian_metadata import (
    APPROVED_CC0,
    BIBLIOGRAPHIC_CANDIDATE,
    MAX_JSON_DEPTH,
    MAX_JSON_NODES,
    MAX_MEDIA_ITEMS,
    MAX_RECORD_BYTES,
    NOISE_OR_UNRESOLVED,
    ORIGINAL_CANDIDATE,
    QUARANTINED,
    REPLICA_OR_MODERN,
    SmithsonianMetadataError,
    normalize_smithsonian_record,
    validate_smithsonian_metadata_semantics,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "smithsonian-metadata-record.schema.json"
SOURCE_URL = (
    "https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/nmnhanthro/01.txt"
)
MISSING = object()


def synthetic_record(
    *,
    title: str = "Harappan Steatite Seal",
    unit_code: str = "NMNHANTHRO",
    metadata_access: object = "CC0",
    notes: str | None = None,
    culture: str = "Harappan (ca. 2500 B.C.)",
    place: str = "Harappa, Punjab, Pakistan",
    object_type: str = "Seal",
    media: list[dict[str, Any]] | None = None,
    object_rights: object = MISSING,
    userestrict: object = MISSING,
    accessrestrict: object = MISSING,
    identifier: str = "synthetic-1",
    upstream_hash: str = "01" + "a" * 38,
) -> dict[str, Any]:
    record_id = f"nmnhanthropology_{identifier}"
    freetext: dict[str, Any] = {
        "culture": [{"label": "Culture", "content": culture}],
        "place": [{"label": "Place", "content": place}],
        "objectType": [{"label": "Object Type", "content": object_type}],
    }
    if notes is not None:
        freetext["notes"] = [{"label": "Notes", "content": notes}]
    if object_rights is not MISSING:
        freetext["objectRights"] = object_rights
    if userestrict is not MISSING:
        freetext["userestrict"] = userestrict
    if accessrestrict is not MISSING:
        freetext["accessrestrict"] = accessrestrict

    descriptive: dict[str, Any] = {
        "record_ID": record_id,
        "unit_code": unit_code,
        "title": {"label": "title", "content": title},
        "record_link": f"http://n2t.net/ark:/65665/{identifier}",
    }
    if metadata_access is not MISSING:
        descriptive["metadata_usage"] = (
            metadata_access if isinstance(metadata_access, dict) else {"access": metadata_access}
        )
    if media is not None:
        descriptive["online_media"] = {
            "media": media,
            "mediaCount": len(media),
        }
    return {
        "id": f"ld1-{identifier}",
        "version": "",
        "unitCode": unit_code,
        "linkedId": "",
        "type": "edanmdm",
        "content": {
            "freetext": freetext,
            "indexedStructured": {
                "culture": ["Indus civilization"] if culture else [],
                "place": [place] if place else [],
                "object_type": [object_type] if object_type else [],
            },
            "descriptiveNonRepeating": descriptive,
        },
        "url": f"edanmdm:{record_id}",
        "hash": upstream_hash,
        "docSignature": "b" * 32,
        "timestamp": 1663781672,
        "lastTimeUpdated": 1769619450,
        "title": title,
    }


def approved_media(**changes: Any) -> dict[str, Any]:
    media: dict[str, Any] = {
        "id": "media:SYNTHETIC-1",
        "guid": "http://n2t.net/ark:/65665/media-synthetic-1",
        "type": "Images",
        "usage": {"access": "CC0"},
        "content": "https://ids.si.edu/ids/deliveryService?id=SYNTHETIC-1",
    }
    media.update(changes)
    return media


def json_record_bytes(record: dict[str, Any], *, padding: bool = False) -> bytes:
    text = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if padding:
        text = f"  {text}  "
    return text.encode("utf-8")


def jsonl_container(record: dict[str, Any], *, ending: bytes = b"\n") -> bytes:
    return json_record_bytes(record) + ending


def normalize(
    record: dict[str, Any],
    *,
    raw_jsonl_bytes: bytes | None = None,
    **changes: Any,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "source_url": SOURCE_URL,
        "retrieved_at": "2026-07-27T04:05:06Z",
        "line_number": 1,
        "etag": '"synthetic-etag"',
        "last_modified": "Mon, 27 Jul 2026 03:00:00 GMT",
    }
    arguments.update(changes)
    raw = jsonl_container(record) if raw_jsonl_bytes is None else raw_jsonl_bytes
    return normalize_smithsonian_record(raw, **arguments)


class SmithsonianMetadataTests(unittest.TestCase):
    def test_five_nmnh_seal_casts_remain_metadata_only_replica_candidates(self) -> None:
        fixtures = (
            ("Mohenjo-Daro Square Seal Cast", "Cast/replica."),
            ("Harappa Unicorn Seal Replica", "Replica made for study."),
            ("Dholavira Seal Reproduction", "Reproduction."),
            ("Lothal Inscribed Tablet Cast", "Plaster cast."),
            ("Kalibangan Seal Facsimile", "Facsimile copy."),
        )
        for index, (title, notes) in enumerate(fixtures):
            with self.subTest(index=index, title=title):
                output = normalize(
                    synthetic_record(
                        title=title,
                        notes=notes,
                        identifier=f"cast-{index}",
                    )
                )
                self.assertEqual(REPLICA_OR_MODERN, output["candidate_classification"])
                self.assertEqual("metadata_approved", output["record_state"])
                self.assertEqual("absent_metadata_only", output["media"]["state"])
                self.assertEqual([], output["media"]["items"])
                self.assertIn(
                    "media_absence_never_authorizes_web_scraping",
                    output["limitations"],
                )

    def test_high_precision_original_candidate_and_generic_artifact_exclusion(self) -> None:
        output = normalize(
            synthetic_record(
                title="Steatite Seal",
                culture="Indus Valley Civilization",
                place="Mohenjo-daro, Sindh, Pakistan",
                object_type="Seal",
            )
        )
        self.assertEqual(ORIGINAL_CANDIDATE, output["candidate_classification"])
        self.assertIn(
            "requires_human_originality_review",
            output["classification_reasons"],
        )

        figurine = normalize(
            synthetic_record(
                title="Harappan Figurine",
                culture="Harappan",
                object_type="Figurine",
            )
        )
        self.assertEqual(NOISE_OR_UNRESOLVED, figurine["candidate_classification"])
        self.assertIn(
            "missing_artifact_object_marker",
            figurine["classification_reasons"],
        )

    def test_unit_gates_precede_replica_markers(self) -> None:
        bibliographic = normalize(
            synthetic_record(
                title="Modern catalogue of Harappan seal casts",
                unit_code="SIL",
                notes="Facsimile reproductions.",
                object_type="Book",
            )
        )
        self.assertEqual(
            BIBLIOGRAPHIC_CANDIDATE,
            bibliographic["candidate_classification"],
        )

        for unit_code in ("NMNHFISHES", "NMNHEDUCATION"):
            with self.subTest(unit_code=unit_code):
                natural = normalize(
                    synthetic_record(
                        title="Harappan seal cast teaching specimen",
                        unit_code=unit_code,
                    )
                )
                self.assertEqual(
                    NOISE_OR_UNRESOLVED,
                    natural["candidate_classification"],
                )
                self.assertIn("natural_history_unit", natural["classification_reasons"])

    def test_cast_iron_and_modern_catalogue_do_not_imply_replica(self) -> None:
        for notes in (
            "Made using a cast iron support.",
            "A modern catalogue describes this original seal.",
        ):
            with self.subTest(notes=notes):
                output = normalize(synthetic_record(notes=notes))
                self.assertEqual(
                    ORIGINAL_CANDIDATE,
                    output["candidate_classification"],
                )

    def test_metadata_usage_checks_access_codes_text_and_unknown_fields(self) -> None:
        approved = normalize(
            synthetic_record(
                metadata_access={
                    "access": "\u3000cc0 \n",
                    "codes": ["CC0"],
                    "text": "",
                    "future": {},
                }
            )
        )
        self.assertEqual(APPROVED_CC0, approved["rights"]["metadata"]["status"])

        cases = {
            "missing": (MISSING, "metadata_usage_missing"),
            "access": ("Usage conditions apply", "metadata_usage_conditions_apply"),
            "codes": (
                {"access": "CC0", "codes": ["Usage conditions apply"]},
                "metadata_codes_conflict",
            ),
            "text": (
                {"access": "CC0", "text": "Usage conditions apply"},
                "metadata_text_conflict",
            ),
            "unknown": (
                {"access": "CC0", "source": {"note": "not an approved rights field"}},
                "metadata_usage_unknown_substantive_field",
            ),
        }
        for label, (usage, reason) in cases.items():
            with self.subTest(label=label):
                output = normalize(
                    synthetic_record(
                        metadata_access=usage,
                        media=[approved_media()],
                    )
                )
                self.assertEqual(
                    "quarantined_metadata_rights",
                    output["record_state"],
                )
                self.assertIn(
                    reason,
                    output["rights"]["metadata"]["reason_codes"],
                )
                self.assertEqual(QUARANTINED, output["media"]["items"][0]["status"])
                self.assertIn(
                    "record_metadata_not_cc0",
                    output["media"]["items"][0]["reason_codes"],
                )

    def test_media_usage_and_record_restrictions_fail_closed(self) -> None:
        approved = normalize(
            synthetic_record(
                media=[
                    approved_media(
                        usage={"access": "CC0", "codes": ["CC0"], "text": ""},
                    )
                ],
                object_rights=[
                    {
                        "label": "Restrictions & Rights",
                        "content": "CC0",
                    }
                ],
            )
        )
        self.assertEqual(APPROVED_CC0, approved["media"]["items"][0]["status"])

        cases = {
            "usage_text": (
                approved_media(usage={"access": "CC0", "text": "restricted"}),
                {},
                "media_text_conflict",
            ),
            "usage_codes": (
                approved_media(
                    usage={
                        "access": "CC0",
                        "codes": ["Usage conditions apply"],
                    }
                ),
                {},
                "media_codes_conflict",
            ),
            "unknown_usage": (
                approved_media(usage={"access": "CC0", "rights": "restricted"}),
                {},
                "media_usage_unknown_substantive_field",
            ),
            "object_rights": (
                approved_media(),
                {
                    "object_rights": [
                        {
                            "label": "Restrictions & Rights",
                            "content": "Usage conditions apply",
                        }
                    ]
                },
                "object_rights_contradiction",
            ),
            "object_rights_unknown_sibling": (
                approved_media(),
                {
                    "object_rights": [
                        {
                            "label": "Restrictions & Rights",
                            "content": "CC0",
                            "note": "Copyright; all rights reserved.",
                        }
                    ]
                },
                "object_rights_contradiction",
            ),
            "use_restriction": (
                approved_media(),
                {
                    "userestrict": [
                        {
                            "label": "Collection Rights",
                            "content": "Contact repository.",
                        }
                    ]
                },
                "use_restriction_present",
            ),
        }
        for label, (media, record_changes, reason) in cases.items():
            with self.subTest(label=label):
                output = normalize(synthetic_record(media=[media], **record_changes))
                item = output["media"]["items"][0]
                self.assertEqual(QUARANTINED, item["status"])
                self.assertIn(reason, item["reason_codes"])

        unknown_rights = synthetic_record(media=[approved_media()])
        unknown_rights["content"]["freetext"]["futureRightsNote"] = [
            {"content": "Contact the repository before use."}
        ]
        output = normalize(unknown_rights)
        self.assertTrue(output["rights"]["record_restrictions"]["contradictory"])
        self.assertIn(
            "unknown_record_restriction_field",
            output["media"]["items"][0]["reason_codes"],
        )

        for label, object_rights in {
            "boolean_sibling": [{"content": "CC0", "restriction": True}],
            "numeric_sibling": [{"content": "CC0", "restriction": 1}],
            "object_sibling": [{"content": "CC0", "restriction": {"flag": True}}],
            "array_sibling": [{"content": "CC0", "restriction": ["CC0", True]}],
            "nested_label": [
                {
                    "content": "CC0",
                    "restriction": {"label": "All rights reserved"},
                }
            ],
            "restrictive_top_label": [
                {
                    "label": "All rights reserved",
                    "content": "CC0",
                }
            ],
            "nonstring_top_label": [
                {
                    "label": True,
                    "content": "CC0",
                }
            ],
        }.items():
            with self.subTest(label=label):
                output = normalize(
                    synthetic_record(
                        media=[approved_media()],
                        object_rights=object_rights,
                    )
                )
                self.assertTrue(output["rights"]["record_restrictions"]["contradictory"])
                self.assertEqual(QUARANTINED, output["media"]["items"][0]["status"])

        for field in (
            "permissions",
            "termsOfUse",
            "conditions",
            "embargo",
            "licence",
        ):
            with self.subTest(field=field):
                record = synthetic_record(media=[approved_media()])
                record["content"]["freetext"][field] = [
                    {"content": "Contact repository; all rights reserved."}
                ]
                output = normalize(record)
                self.assertIn(
                    "unknown_record_restriction_field",
                    output["media"]["items"][0]["reason_codes"],
                )

        scoped_rights = synthetic_record(media=[approved_media()])
        scoped_rights["content"]["descriptiveNonRepeating"]["rightsStatement"] = (
            "All rights reserved"
        )
        scoped_rights["content"]["indexedStructured"]["usage_flag"] = ["Unknown"]
        output = normalize(scoped_rights)
        self.assertIn(
            "unknown_record_restriction_field",
            output["media"]["items"][0]["reason_codes"],
        )

    def test_only_exact_smithsonian_image_delivery_urls_are_approved(self) -> None:
        cases = {
            "private_ip": "https://127.0.0.1/admin",
            "foreign_host": "https://example.org/image.jpg",
            "http": "http://ids.si.edu/ids/deliveryService?id=X",
            "uppercase_host": "https://IDS.SI.EDU/ids/deliveryService?id=X",
            "download_path": "https://ids.si.edu/ids/download?id=X",
            "extra_query": "https://ids.si.edu/ids/deliveryService?id=X&token=SECRET",
            "fragment": "https://ids.si.edu/ids/deliveryService?id=X#fragment",
            "space": "https://ids.si.edu/ids/deliveryService?id=X Y",
            "encoded_assignment": ("https://ids.si.edu/ids/deliveryService?id=secret%3DSECRET"),
            "nested_https": (
                "https://ids.si.edu/ids/deliveryService?id=https%3A%2F%2F127.0.0.1%2Fadmin"
            ),
            "file_uri": ("https://ids.si.edu/ids/deliveryService?id=file%3A%2F%2F%2Fetc%2Fpasswd"),
        }
        for label, url in cases.items():
            with self.subTest(label=label):
                output = normalize(synthetic_record(media=[approved_media(content=url)]))
                item = output["media"]["items"][0]
                self.assertEqual(QUARANTINED, item["status"])
                self.assertIn(
                    "media_url_not_approved_smithsonian_image",
                    item["reason_codes"],
                )
                self.assertEqual([], validate_schema_instance(output, SCHEMA))

        video = normalize(synthetic_record(media=[approved_media(type="Video")]))
        self.assertEqual(QUARANTINED, video["media"]["items"][0]["status"])
        self.assertIn(
            "media_type_not_image",
            video["media"]["items"][0]["reason_codes"],
        )
        self.assertEqual([], validate_schema_instance(video, SCHEMA))

    def test_raw_container_and_exact_line_commitments_are_computed(self) -> None:
        first = synthetic_record(identifier="first")
        target = synthetic_record(identifier="target")
        third = synthetic_record(identifier="third")
        first_line = json_record_bytes(first) + b"\r\n"
        target_record_bytes = json_record_bytes(target, padding=True)
        target_line = target_record_bytes + b"\n"
        raw = first_line + target_line + json_record_bytes(third)

        output = normalize(
            target,
            raw_jsonl_bytes=raw,
            line_number=2,
        )
        acquisition = output["source_acquisition"]
        locator = acquisition["locator"]
        self.assertEqual(len(raw), acquisition["container"]["bytes"])
        self.assertEqual(
            "sha256:" + hashlib.sha256(raw).hexdigest(),
            acquisition["container"]["sha256"],
        )
        self.assertEqual(len(first_line), locator["byte_offset"])
        self.assertEqual(len(target_line), locator["line_bytes"])
        self.assertEqual(
            "sha256:" + hashlib.sha256(target_line).hexdigest(),
            locator["line_sha256"],
        )
        self.assertEqual(len(target_record_bytes), locator["record_text_bytes"])
        self.assertEqual("lf", locator["line_ending"])
        self.assertEqual(target_record_bytes.decode("utf-8"), output["raw_record_text"])

        different_container = target_record_bytes
        second_output = normalize(
            target,
            raw_jsonl_bytes=different_container,
            line_number=1,
        )
        self.assertNotEqual(output["intake_id"], second_output["intake_id"])

    def test_strict_jsonl_rejects_duplicate_keys_nul_invalid_utf8_and_blank_lines(self) -> None:
        record = synthetic_record()
        text = json_record_bytes(record).decode("utf-8")
        duplicate = text.replace(
            '"type":"edanmdm"',
            '"type":"edanmdm","type":"edanmdm"',
            1,
        ).encode()
        malformed = {
            "duplicate": duplicate + b"\n",
            "nul": json_record_bytes(record) + b"\x00\n",
            "utf8": json_record_bytes(record) + b"\xff\n",
            "blank": b"\n" + json_record_bytes(record) + b"\n",
        }
        for label, raw in malformed.items():
            with self.subTest(label=label), self.assertRaises(SmithsonianMetadataError):
                normalize(record, raw_jsonl_bytes=raw)

        nan_text = text.replace(
            '"timestamp":1663781672',
            '"timestamp":NaN',
            1,
        ).encode()
        with self.assertRaisesRegex(SmithsonianMetadataError, "non-finite"):
            normalize(record, raw_jsonl_bytes=nan_text)

        huge_integer = text.replace(
            '"timestamp":1663781672',
            '"timestamp":' + "9" * 5000,
            1,
        ).encode()
        with self.assertRaisesRegex(SmithsonianMetadataError, "cannot represent"):
            normalize(record, raw_jsonl_bytes=huge_integer)

        unpaired_surrogate = text.replace(
            '"title":"Harappan Steatite Seal"',
            '"title":"\\ud800"',
            1,
        ).encode()
        with self.assertRaisesRegex(SmithsonianMetadataError, "Unicode surrogate"):
            normalize(record, raw_jsonl_bytes=unpaired_surrogate)

    def test_source_url_timestamp_and_encoded_credentials_are_strict(self) -> None:
        bad_source_urls = (
            SOURCE_URL + "?X-Amz-Signature=SECRET",
            SOURCE_URL + "#api%5Fkey=SECRET",
            SOURCE_URL.replace("/01.txt", ":443/01.txt"),
            SOURCE_URL.replace("/metadata/edan/", "/other/"),
        )
        for source_url in bad_source_urls:
            with (
                self.subTest(source_url=source_url),
                self.assertRaisesRegex(SmithsonianMetadataError, "source_url"),
            ):
                normalize(synthetic_record(), source_url=source_url)

        with self.assertRaisesRegex(SmithsonianMetadataError, "RFC 3339"):
            normalize(
                synthetic_record(),
                retrieved_at="20260727T040506+00:00",
            )

        record = synthetic_record()
        record["debug"] = "https://api.si.edu/path?api%255Fkey%3DSECRET"
        with self.assertRaisesRegex(SmithsonianMetadataError, "credential"):
            normalize(record)

        record = synthetic_record()
        record["debug"] = {"X-Amz-Security-Token": "SECRET"}
        with self.assertRaisesRegex(SmithsonianMetadataError, "credential-bearing"):
            normalize(record)

        for field in (
            "AWSAccessKeyId",
            "aws_secret_access_key",
            "password",
            "pwd",
        ):
            with self.subTest(field=field):
                record = synthetic_record()
                record[field] = "SECRET"
                with self.assertRaisesRegex(
                    SmithsonianMetadataError,
                    "credential-bearing",
                ):
                    normalize(record)

        encoded_key = synthetic_record(
            media=[
                approved_media(
                    content=("https://ids.si.edu/ids/deliveryService?id=AWSAccessKeyId%3DSECRET")
                )
            ]
        )
        with self.assertRaisesRegex(SmithsonianMetadataError, "credential"):
            normalize(encoded_key)

        encoded_pwd = synthetic_record(
            media=[
                approved_media(content=("https://ids.si.edu/ids/deliveryService?id=pwd%3DSECRET"))
            ]
        )
        with self.assertRaisesRegex(SmithsonianMetadataError, "credential"):
            normalize(encoded_pwd)

        aws_value = synthetic_record()
        aws_value["debug"] = "copied value AKIAIOSFODNN7EXAMPLE"
        with self.assertRaisesRegex(SmithsonianMetadataError, "credential"):
            normalize(aws_value)

        with self.assertRaisesRegex(SmithsonianMetadataError, "character limit"):
            normalize(synthetic_record(), etag="x" * 1025)
        with self.assertRaisesRegex(SmithsonianMetadataError, "character limit"):
            normalize(synthetic_record(), last_modified="x" * 1025)
        with self.assertRaisesRegex(SmithsonianMetadataError, "unitCode"):
            normalize(synthetic_record(unit_code="X" * 129))

    def test_upstream_identity_and_source_shard_are_cross_checked(self) -> None:
        wrong_url = synthetic_record()
        wrong_url["url"] = "edanmdm:other_record"
        with self.assertRaisesRegex(SmithsonianMetadataError, "record_ID"):
            normalize(wrong_url)

        wrong_shard = synthetic_record(upstream_hash="ff" + "a" * 38)
        with self.assertRaisesRegex(SmithsonianMetadataError, "source JSONL shard"):
            normalize(wrong_shard)

        bad_signature = synthetic_record()
        bad_signature["docSignature"] = "not-a-signature"
        with self.assertRaisesRegex(SmithsonianMetadataError, "docSignature"):
            normalize(bad_signature)

    def test_record_depth_size_and_media_count_limits(self) -> None:
        too_many_media = synthetic_record(
            media=[approved_media(id=f"media:{index}") for index in range(MAX_MEDIA_ITEMS + 1)]
        )
        with self.assertRaisesRegex(SmithsonianMetadataError, "media"):
            normalize(too_many_media)

        deep_record = synthetic_record()
        nested: dict[str, Any] = {}
        deep_record["debug"] = nested
        for _ in range(MAX_JSON_DEPTH + 1):
            child: dict[str, Any] = {}
            nested["child"] = child
            nested = child
        with self.assertRaisesRegex(SmithsonianMetadataError, "depth"):
            normalize(deep_record)

        large_record = synthetic_record(title="x" * (MAX_RECORD_BYTES + 1))
        with self.assertRaisesRegex(SmithsonianMetadataError, "record limit"):
            normalize(large_record)

    def test_schema_semantics_and_coordinated_tamper_resistance(self) -> None:
        record = synthetic_record(
            metadata_access="Usage conditions apply",
            media=[approved_media()],
        )
        raw = jsonl_container(record)
        output = normalize(record, raw_jsonl_bytes=raw)
        self.assertEqual([], validate_schema_instance(output, SCHEMA))
        validate_smithsonian_metadata_semantics(output, raw_jsonl_bytes=raw)

        escalated = copy.deepcopy(output)
        escalated["record_state"] = "metadata_approved"
        escalated["rights"]["metadata"] = {
            "status": "approved_cc0",
            "normalized_access": "CC0",
            "reason_codes": [],
            "original_metadata_usage": {"access": "CC0"},
        }
        item = escalated["media"]["items"][0]
        item["status"] = "approved_cc0"
        item["normalized_access"] = "CC0"
        item["reason_codes"] = []
        escalated["media"]["approved_count"] = 1
        escalated["media"]["quarantined_count"] = 0
        self.assertEqual([], validate_schema_instance(escalated, SCHEMA))
        with self.assertRaisesRegex(SmithsonianMetadataError, "committed raw"):
            validate_smithsonian_metadata_semantics(
                escalated,
                raw_jsonl_bytes=raw,
            )

        evidence_tamper = copy.deepcopy(output)
        evidence_tamper["record_context"]["title"] = "forged"
        evidence_tamper["classification_evidence"] = []
        with self.assertRaisesRegex(SmithsonianMetadataError, "committed raw"):
            validate_smithsonian_metadata_semantics(
                evidence_tamper,
                raw_jsonl_bytes=raw,
            )

        source_tamper = copy.deepcopy(output)
        source_tamper["source_acquisition"]["container"]["sha256"] = "sha256:" + "0" * 64
        source_tamper["intake_id"] = "smithsonian-jsonl-record:sha256:" + "0" * 64
        with self.assertRaisesRegex(SmithsonianMetadataError, "committed raw"):
            validate_smithsonian_metadata_semantics(
                source_tamper,
                raw_jsonl_bytes=raw,
            )

        retrieval_tamper = copy.deepcopy(output)
        retrieval_tamper["source_acquisition"]["retrieved_at"] = "2026-07-27T04:05:07Z"
        with self.assertRaisesRegex(SmithsonianMetadataError, "committed raw"):
            validate_smithsonian_metadata_semantics(
                retrieval_tamper,
                raw_jsonl_bytes=raw,
            )

        oversized_normalized = copy.deepcopy(output)
        oversized_normalized["unexpected"] = [None] * MAX_JSON_NODES
        with self.assertRaisesRegex(SmithsonianMetadataError, "node count"):
            validate_smithsonian_metadata_semantics(
                oversized_normalized,
                raw_jsonl_bytes=raw,
            )

    def test_non_edan_and_media_count_mismatch_fail_closed(self) -> None:
        wrong_type = synthetic_record()
        wrong_type["type"] = "ead_component"
        with self.assertRaisesRegex(SmithsonianMetadataError, r"\$\.type"):
            normalize(wrong_type)

        malformed = synthetic_record(media=[])
        malformed["content"]["descriptiveNonRepeating"]["online_media"]["mediaCount"] = 1
        with self.assertRaisesRegex(SmithsonianMetadataError, "mediaCount"):
            normalize(malformed)


if __name__ == "__main__":
    unittest.main()
