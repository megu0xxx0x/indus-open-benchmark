from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from urllib.request import Request

from indusbench.museum_intake import (
    JsonDocument,
    MuseumIntakeError,
    _NoRedirectHandler,
    build_cleveland_intake,
    build_met_intake,
    download_intake_media,
    fetch_json_document,
    validate_intake_semantics,
    verify_intake_bundle,
    write_intake_raw_response,
)

ROOT = Path(__file__).resolve().parents[1]
RETRIEVED_AT = "2026-07-26T08:00:00Z"


class FakeResponse:
    def __init__(
        self,
        value: bytes,
        *,
        content_type: str,
        status: int = 200,
        content_length: int | None = None,
    ) -> None:
        self.status = status
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(value) if content_length is None else content_length),
        }
        self._stream = io.BytesIO(value)

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self._stream.close()

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


class FakeOpener:
    def __init__(self, responses: dict[str, tuple[bytes, str, int | None]]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def __call__(self, request: Request, *, timeout: float) -> FakeResponse:
        del timeout
        self.requested.append(request.full_url)
        value, content_type, content_length = self.responses[request.full_url]
        return FakeResponse(
            value,
            content_type=content_type,
            content_length=content_length,
        )


def document(url: str, value: dict[str, Any]) -> JsonDocument:
    raw_bytes = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return JsonDocument(
        url=url,
        status=200,
        content_type="application/json",
        headers={"content-type": "application/json"},
        raw_bytes=raw_bytes,
        value=value,
    )


def met_payload(*, public_domain: bool = True) -> dict[str, Any]:
    return {
        "objectID": 324062,
        "isPublicDomain": public_domain,
        "accessionNumber": "49.40.1",
        "title": "Stamp seal and modern impression",
        "objectURL": "https://www.metmuseum.org/art/collection/search/324062",
        "primaryImage": "https://images.metmuseum.org/example/primary.jpg",
        "additionalImages": ["https://images.metmuseum.org/example/alternate.jpg"],
    }


def cleveland_derivative(
    url: str,
    *,
    width: str = "2000",
    height: str = "1500",
    filesize: str = "9000",
) -> dict[str, str]:
    return {
        "url": url,
        "width": width,
        "height": height,
        "filesize": filesize,
    }


def cleveland_payload(*, license_status: str = "CC0") -> dict[str, Any]:
    return {
        "data": [
            {
                "id": 140095,
                "accession_number": "1964.104",
                "title": "Seal with Unicorn and Inscription",
                "share_license_status": license_status,
                "url": "https://clevelandart.org/art/1964.104",
                "images": {
                    "print": cleveland_derivative(
                        "https://openaccess-cdn.clevelandart.org/1964.104/1964.104_print.jpg"
                    ),
                    "full": cleveland_derivative(
                        "https://openaccess-cdn.clevelandart.org/1964.104/1964.104_full.tif"
                    ),
                },
                "alternate_images": [
                    {
                        "print": cleveland_derivative(
                            "https://openaccess-cdn.clevelandart.org/1964.104/"
                            "1964.104_alt0_print.jpg"
                        ),
                        "full": cleveland_derivative(
                            "https://openaccess-cdn.clevelandart.org/1964.104/"
                            "1964.104_alt0_full.tif"
                        ),
                    }
                ],
            }
        ]
    }


class MuseumIntakeParsingTests(unittest.TestCase):
    def test_met_record_is_untranscribed_and_does_not_infer_physical_sides(self) -> None:
        source = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(),
        )

        record = build_met_intake(
            source,
            expected_object_id=324062,
            retrieved_at=RETRIEVED_AT,
        )

        self.assertEqual("untranscribed", record["record_state"])
        self.assertEqual(
            ["provider_primary", "provider_alternate_unknown"],
            [item["view_role"] for item in record["media"]],
        )
        self.assertEqual({"unknown"}, {item["physical_side"] for item in record["media"]})
        self.assertEqual(
            source.sha256,
            record["item_rights"]["evidence"]["api_response_sha256"],
        )
        self.assertIs(
            True,
            record["item_rights"]["evidence"]["observed_value"],
        )
        self.assertNotIn("tokens", record)
        validate_intake_semantics(record, document=source)

    def test_met_rejects_non_public_domain_and_mismatched_ids(self) -> None:
        denied = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(public_domain=False),
        )
        with self.assertRaisesRegex(MuseumIntakeError, "not currently marked"):
            build_met_intake(
                denied,
                expected_object_id=324062,
                retrieved_at=RETRIEVED_AT,
            )

        mismatched = met_payload()
        mismatched["objectID"] = 1
        with self.assertRaisesRegex(MuseumIntakeError, "did not match"):
            build_met_intake(
                document(
                    "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
                    mismatched,
                ),
                expected_object_id=324062,
                retrieved_at=RETRIEVED_AT,
            )

    def test_cleveland_retains_print_and_full_as_distinct_media(self) -> None:
        source = document(
            "https://openaccess-api.clevelandart.org/api/artworks/?accession_number=1964.104",
            cleveland_payload(),
        )

        record = build_cleveland_intake(
            source,
            expected_accession_number="1964.104",
            retrieved_at=RETRIEVED_AT,
        )

        self.assertEqual(4, len(record["media"]))
        self.assertEqual(
            {
                "cleveland:1964.104:primary:print",
                "cleveland:1964.104:primary:full",
                "cleveland:1964.104:alt0:print",
                "cleveland:1964.104:alt0:full",
            },
            {item["media_id"] for item in record["media"]},
        )
        self.assertEqual(
            {"cleveland_print", "cleveland_full"},
            {item["provider_derivative"] for item in record["media"]},
        )
        self.assertEqual({9000}, {item["api_declared_bytes"] for item in record["media"]})
        self.assertEqual(
            {"unknown"},
            {item["physical_side"] for item in record["media"]},
        )

    def test_cleveland_rejects_any_status_other_than_exact_cc0(self) -> None:
        source = document(
            "https://openaccess-api.clevelandart.org/api/artworks/?accession_number=1964.104",
            cleveland_payload(license_status="Copyrighted"),
        )
        with self.assertRaisesRegex(MuseumIntakeError, "not currently marked CC0"):
            build_cleveland_intake(
                source,
                expected_accession_number="1964.104",
                retrieved_at=RETRIEVED_AT,
            )

    def test_cleveland_rejects_lossy_numeric_metadata(self) -> None:
        payload = cleveland_payload()
        payload["data"][0]["images"]["print"]["filesize"] = 1.5
        source = document(
            "https://openaccess-api.clevelandart.org/api/artworks/?accession_number=1964.104",
            payload,
        )

        with self.assertRaisesRegex(MuseumIntakeError, "canonical positive decimal"):
            build_cleveland_intake(
                source,
                expected_accession_number="1964.104",
                retrieved_at=RETRIEVED_AT,
            )

    def test_cross_field_rights_hash_mismatch_is_rejected(self) -> None:
        source = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(),
        )
        record = build_met_intake(
            source,
            expected_object_id=324062,
            retrieved_at=RETRIEVED_AT,
        )
        record["item_rights"]["evidence"]["api_response_sha256"] = "sha256:" + ("0" * 64)

        with self.assertRaisesRegex(MuseumIntakeError, "evidence hash"):
            validate_intake_semantics(record)

    def test_known_provider_media_host_is_allowlisted(self) -> None:
        source = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(),
        )
        record = build_met_intake(
            source,
            expected_object_id=324062,
            retrieved_at=RETRIEVED_AT,
        )
        record["media"][0]["source_uri"] = "https://untrusted.example/primary.jpg"

        with self.assertRaisesRegex(MuseumIntakeError, "provider allowlist"):
            validate_intake_semantics(record)

    def test_unknown_provider_cannot_disable_network_allowlists(self) -> None:
        source = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(),
        )
        record = build_met_intake(
            source,
            expected_object_id=324062,
            retrieved_at=RETRIEVED_AT,
        )
        record["source_id"] = "unknown-provider"

        with self.assertRaisesRegex(MuseumIntakeError, "unsupported museum intake source_id"):
            validate_intake_semantics(record)


class MuseumIntakeHttpTests(unittest.TestCase):
    def test_fetch_json_retains_exact_bytes_and_enforces_bounds(self) -> None:
        raw = b'{"answer":42}'
        opener = FakeOpener(
            {
                "https://api.example/item": (
                    raw,
                    "application/json; charset=utf-8",
                    None,
                )
            }
        )

        fetched = fetch_json_document(
            "https://api.example/item",
            max_bytes=len(raw),
            opener=opener,
        )

        self.assertEqual({"answer": 42}, fetched.value)
        self.assertEqual(
            f"sha256:{hashlib.sha256(raw).hexdigest()}",
            fetched.sha256,
        )
        self.assertEqual("application/json", fetched.content_type)
        with self.assertRaisesRegex(MuseumIntakeError, "exceeds max_bytes"):
            fetch_json_document(
                "https://api.example/item",
                max_bytes=len(raw) - 1,
                opener=opener,
            )
        with self.assertRaisesRegex(MuseumIntakeError, "HTTPS"):
            fetch_json_document("http://api.example/item", opener=opener)

    def test_fetch_json_rejects_cross_host_redirects(self) -> None:
        class RedirectResponse(FakeResponse):
            def geturl(self) -> str:
                return "https://redirected.example/item"

        def opener(request: Request, *, timeout: float) -> FakeResponse:
            del request, timeout
            return RedirectResponse(
                b'{"answer":42}',
                content_type="application/json",
            )

        with self.assertRaisesRegex(MuseumIntakeError, "redirects are not allowed"):
            fetch_json_document("https://api.example/item", opener=opener)

    def test_fetch_json_rejects_duplicate_keys_at_any_depth(self) -> None:
        raw = b'{"rights":{"status":"CC0","status":"Copyrighted"}}'
        opener = FakeOpener(
            {
                "https://api.example/item": (
                    raw,
                    "application/json",
                    None,
                )
            }
        )

        with self.assertRaisesRegex(MuseumIntakeError, "duplicate key"):
            fetch_json_document("https://api.example/item", opener=opener)

    def test_redirect_handler_rejects_each_cross_host_hop(self) -> None:
        handler = _NoRedirectHandler()
        request = Request("https://api.example/item")

        with self.assertRaisesRegex(MuseumIntakeError, "redirects are not allowed"):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://redirected.example/item",
            )
        with self.assertRaisesRegex(MuseumIntakeError, "redirects are not allowed"):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://api.example/other-item",
            )

    def test_download_records_actual_bytes_and_bundle_rehashes_them(self) -> None:
        source = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(),
        )
        record = build_met_intake(
            source,
            expected_object_id=324062,
            retrieved_at=RETRIEVED_AT,
        )
        primary = b"\xff\xd8primary-jpeg\xff\xd9"
        alternate = b"\xff\xd8alternate-jpeg\xff\xd9"
        opener = FakeOpener(
            {
                "https://images.metmuseum.org/example/primary.jpg": (
                    primary,
                    "image/jpeg",
                    None,
                ),
                "https://images.metmuseum.org/example/alternate.jpg": (
                    alternate,
                    "image/jpeg",
                    None,
                ),
            }
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            bundle = Path(temporary_directory)
            write_intake_raw_response(record, source, root=bundle)
            downloaded = download_intake_media(
                record,
                root=bundle,
                downloaded_at="2026-07-26T08:01:00Z",
                opener=opener,
            )
            report = verify_intake_bundle(downloaded, root=bundle)

            self.assertTrue(report["verified"])
            self.assertEqual(2, report["downloaded_media_count"])
            self.assertEqual(len(primary) + len(alternate), report["downloaded_media_bytes"])
            self.assertEqual(
                [len(primary), len(alternate)],
                [item["download"]["bytes"] for item in downloaded["media"]],
            )
            invalid_bytes = copy.deepcopy(downloaded)
            invalid_bytes["media"][0]["download"]["bytes"] = float(len(primary))
            with self.assertRaisesRegex(MuseumIntakeError, "positive integer"):
                validate_intake_semantics(invalid_bytes)

            unknown_download_field = copy.deepcopy(downloaded)
            unknown_download_field["media"][0]["download"]["unexpected"] = True
            with self.assertRaisesRegex(MuseumIntakeError, "not a closed object"):
                validate_intake_semantics(unknown_download_field)

            invalid_download_time = copy.deepcopy(downloaded)
            invalid_download_time["media"][0]["download"]["downloaded_at"] = 12345
            with self.assertRaisesRegex(MuseumIntakeError, "RFC 3339"):
                validate_intake_semantics(invalid_download_time)

            with self.assertRaises(FileExistsError):
                write_intake_raw_response(record, source, root=bundle)

            first_path = bundle / downloaded["media"][0]["download"]["local_relative_path"]
            first_path.write_bytes(b"tampered")
            with self.assertRaisesRegex(MuseumIntakeError, "hash mismatch"):
                verify_intake_bundle(downloaded, root=bundle)

    def test_api_declared_size_never_overrides_downloaded_size(self) -> None:
        source = document(
            "https://openaccess-api.clevelandart.org/api/artworks/?accession_number=1964.104",
            cleveland_payload(),
        )
        record = build_cleveland_intake(
            source,
            expected_accession_number="1964.104",
            retrieved_at=RETRIEVED_AT,
            derivatives=("print",),
        )
        values: dict[str, tuple[bytes, str, int | None]] = {}
        for item in record["media"]:
            source_uri = item["source_uri"]
            self.assertIsInstance(source_uri, str)
            values[str(source_uri)] = (b"\xff\xd8received-bytes", "image/jpeg", None)

        with tempfile.TemporaryDirectory() as temporary_directory:
            downloaded = download_intake_media(
                record,
                root=temporary_directory,
                downloaded_at="2026-07-26T08:02:00Z",
                opener=FakeOpener(values),
            )

        self.assertEqual({9000}, {item["api_declared_bytes"] for item in downloaded["media"]})
        self.assertEqual(
            {len(b"\xff\xd8received-bytes")},
            {item["download"]["bytes"] for item in downloaded["media"]},
        )

    def test_download_rejects_mislabeled_non_image_bytes(self) -> None:
        source = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(),
        )
        record = build_met_intake(
            source,
            expected_object_id=324062,
            retrieved_at=RETRIEVED_AT,
        )
        values: dict[str, tuple[bytes, str, int | None]] = {}
        for item in record["media"]:
            values[str(item["source_uri"])] = (b"not-a-jpeg", "image/jpeg", None)

        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(MuseumIntakeError, "signature"):
                download_intake_media(
                    record,
                    root=temporary_directory,
                    downloaded_at="2026-07-26T08:03:00Z",
                    opener=FakeOpener(values),
                )
            self.assertEqual(
                [],
                list(Path(temporary_directory).rglob("*.part")),
            )

    def test_verifier_rebuilds_rights_from_stored_raw_response(self) -> None:
        source = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(),
        )
        record = build_met_intake(
            source,
            expected_object_id=324062,
            retrieved_at=RETRIEVED_AT,
        )
        forged_raw = json.dumps(
            met_payload(public_domain=False),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        forged_hash = f"sha256:{hashlib.sha256(forged_raw).hexdigest()}"
        record["retrieval"]["response_sha256"] = forged_hash
        record["item_rights"]["evidence"]["api_response_sha256"] = forged_hash

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_path = root / record["retrieval"]["raw_response_local_relative_path"]
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(forged_raw)

            with self.assertRaisesRegex(MuseumIntakeError, "not currently marked"):
                verify_intake_bundle(record, root=root)

    def test_verifier_rejects_fields_not_derived_from_stored_raw(self) -> None:
        source = document(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
            met_payload(),
        )
        record = build_met_intake(
            source,
            expected_object_id=324062,
            retrieved_at=RETRIEVED_AT,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_intake_raw_response(record, source, root=root)
            record["translation"] = "forged"

            with self.assertRaisesRegex(MuseumIntakeError, "does not exactly match"):
                verify_intake_bundle(record, root=root)


class MuseumIntakeSchemaIntegrationTests(unittest.TestCase):
    def test_parser_outputs_match_normative_schema(self) -> None:
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ImportError:
            self.skipTest("jsonschema optional extra is not installed")

        schema = json.loads(
            (ROOT / "schemas/museum-intake.schema.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        records = [
            build_met_intake(
                document(
                    "https://collectionapi.metmuseum.org/public/collection/v1/objects/324062",
                    met_payload(),
                ),
                expected_object_id=324062,
                retrieved_at=RETRIEVED_AT,
            ),
            build_cleveland_intake(
                document(
                    "https://openaccess-api.clevelandart.org/api/artworks/"
                    "?accession_number=1964.104",
                    cleveland_payload(),
                ),
                expected_accession_number="1964.104",
                retrieved_at=RETRIEVED_AT,
            ),
        ]

        for record in records:
            self.assertEqual([], list(validator.iter_errors(record)))


if __name__ == "__main__":
    unittest.main()
