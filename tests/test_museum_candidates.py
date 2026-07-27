from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry/museum_candidates.json"


class MuseumCandidateRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_registry_scope_is_read_only_and_unique(self) -> None:
        self.assertEqual("0.1.0", self.registry["schema_version"])
        self.assertTrue(self.registry["scope"]["primary_sources_only"])
        self.assertFalse(self.registry["scope"]["media_downloaded"])
        self.assertFalse(self.registry["scope"]["external_contact_performed"])
        institutions = self.registry["institutions"]
        self.assertEqual(11, len(institutions))
        self.assertEqual(
            len(institutions),
            len({item["institution_id"] for item in institutions}),
        )
        self.assertEqual(
            list(range(1, len(institutions) + 1)),
            sorted(item["priority"]["rank"] for item in institutions),
        )

    def test_every_evidence_link_is_official_https(self) -> None:
        for institution in self.registry["institutions"]:
            with self.subTest(institution=institution["institution_id"]):
                urls = institution["official_urls"]
                self.assertGreater(len(urls), 0)
                self.assertTrue(all(item["url"].startswith("https://") for item in urls))
                self.assertTrue(
                    institution["metadata_rights"]["evidence_url"].startswith("https://")
                )
                self.assertTrue(institution["media_rights"]["evidence_url"].startswith("https://"))

    def test_verified_candidates_never_enable_unreviewed_media(self) -> None:
        for institution in self.registry["institutions"]:
            candidates = institution["verified_artifact_candidates"]
            if not candidates:
                continue
            with self.subTest(institution=institution["institution_id"]):
                self.assertFalse(institution["media_rights"]["automated_retrieval"])
                self.assertFalse(institution["media_rights"]["redistribution"])
                self.assertTrue(
                    all(
                        candidate["media_action"]
                        in {
                            "permission_required",
                            "exclude_metadata_only",
                            "exclude_until_cc0_media_verified",
                        }
                        for candidate in candidates
                    )
                )

    def test_retention_limited_apis_remain_discovery_only(self) -> None:
        durations = {
            institution["institution_id"]: institution["retention_limit"]["metadata"][
                "duration_days"
            ]
            for institution in self.registry["institutions"]
            if institution["automation_class"] == "discovery_only_no_retention"
        }
        self.assertEqual(
            {
                "harvard-art-museums": 14,
                "victoria-and-albert-museum": 28,
            },
            durations,
        )


if __name__ == "__main__":
    unittest.main()
