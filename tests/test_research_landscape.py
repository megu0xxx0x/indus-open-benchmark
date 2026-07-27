from __future__ import annotations

import importlib.util
import json
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
LANDSCAPE_PATH = ROOT / "registry" / "research_landscape.json"
LANDSCAPE_SCHEMA_PATH = ROOT / "schemas" / "research-entry.schema.json"
SOURCE_REGISTRY_PATH = ROOT / "registry" / "sources.json"
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class ResearchLandscapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_json(LANDSCAPE_PATH)
        cls.entries = cls.registry["entries"]
        cls.entries_by_id = {entry["entry_id"]: entry for entry in cls.entries}

    def test_registry_has_reviewable_high_value_scope(self) -> None:
        self.assertEqual(len(self.entries), 30)
        self.assertEqual(len(self.entries_by_id), len(self.entries))
        self.assertEqual(set(self.registry["evidence_policy"]), {"A", "B", "C", "D", "E"})
        self.assertEqual(
            Counter(entry["evidence_tier"] for entry in self.entries),
            Counter({"A": 12, "B": 5, "C": 3, "D": 10}),
        )

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema optional extra is not installed")
    def test_registry_matches_normative_schema(self) -> None:
        issues = validate_schema_instance(self.registry, LANDSCAPE_SCHEMA_PATH)
        self.assertEqual([], issues)

    def test_research_and_source_lineage_resolve(self) -> None:
        source_registry = load_json(SOURCE_REGISTRY_PATH)
        source_ids = {source["source_id"] for source in source_registry["sources"]}

        for entry in self.entries:
            with self.subTest(entry_id=entry["entry_id"]):
                lineage = entry["lineage"]
                self.assertLessEqual(set(lineage["source_registry_ids"]), source_ids)
                self.assertLessEqual(
                    set(lineage["upstream_entry_ids"]),
                    set(self.entries_by_id),
                )
                self.assertNotIn(entry["entry_id"], lineage["upstream_entry_ids"])

    def test_research_lineage_is_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(entry_id: str) -> None:
            if entry_id in visited:
                return
            self.assertNotIn(entry_id, visiting, f"research lineage cycle at {entry_id}")
            visiting.add(entry_id)
            for upstream_id in self.entries_by_id[entry_id]["lineage"]["upstream_entry_ids"]:
                visit(upstream_id)
            visiting.remove(entry_id)
            visited.add(entry_id)

        for entry_id in self.entries_by_id:
            visit(entry_id)

    def test_interpretations_are_not_recorded_as_established_observations(self) -> None:
        interpretations = [
            entry for entry in self.entries if entry["claim"]["kind"] == "interpretive_hypothesis"
        ]
        self.assertGreaterEqual(len(interpretations), 3)
        for entry in interpretations:
            with self.subTest(entry_id=entry["entry_id"]):
                self.assertIn(entry["evidence_tier"], {"C", "D", "E"})
                self.assertNotEqual(entry["claim"]["acceptance"], "established")
                self.assertEqual(entry["claim"]["attribution"], "source_reported")

    def test_unknown_or_restricted_rights_never_grant_redistribution(self) -> None:
        for entry in self.entries:
            rights = entry["access_rights"]
            if rights["rights_status"] not in {"restricted", "unknown"}:
                continue
            with self.subTest(entry_id=entry["entry_id"]):
                self.assertIn(rights["redistribution"], {False, None})

    def test_unverified_matters_are_explicit_and_reviewed_later(self) -> None:
        for entry in self.entries:
            with self.subTest(entry_id=entry["entry_id"]):
                self.assertTrue(entry["limitations"])
                for limitation in entry["limitations"]:
                    self.assertIn(
                        limitation["verification"],
                        {"verified", "unverified", "not_applicable"},
                    )

                verified_on = date.fromisoformat(entry["dates"]["verified_on"])
                next_review = entry["dates"]["next_review_on"]
                if next_review is not None:
                    self.assertGreater(date.fromisoformat(next_review), verified_on)

    def test_priority_current_entries_are_present(self) -> None:
        expected = {
            "dataset-mayig-audit-2026",
            "paper-tiwari-2026-statistical-structure",
            "preprint-nair-2026-scorecard",
            "preprint-ross-2026-treewidth",
            "policy-tamil-nadu-prize-2025",
            "project-cambridge-mahsa-phase2",
            "project-florida-tech-isi-asda",
            "project-imsc-icel",
            "project-kaken-uesugi-22h00711",
            "project-rihn-indus-2007-2012",
            "software-prabhatchanchal-indusbench-2026",
            "dataset-hf-hellosindh-indus-script-synthetic-2026",
            "software-ai-epigraphy-indiahci2025",
            "software-ivc2tyc-1.0.0",
            "preprint-kriger-hunt-2026-functional",
            "official-unicode-indus-roadmap-2026",
        }
        self.assertLessEqual(expected, set(self.entries_by_id))

    def test_current_projects_remain_institutional_not_decipherment_claims(self) -> None:
        project_ids = {
            "project-cambridge-mahsa-phase2",
            "project-florida-tech-isi-asda",
            "project-imsc-icel",
            "project-kaken-uesugi-22h00711",
        }
        for entry_id in project_ids:
            with self.subTest(entry_id=entry_id):
                entry = self.entries_by_id[entry_id]
                self.assertEqual(entry["entity_type"], "institution_or_project")
                self.assertEqual(entry["evidence_tier"], "A")
                self.assertEqual(entry["claim"]["kind"], "institutional_statement")
                self.assertNotEqual(entry["claim"]["acceptance"], "unresolved")

    def test_ross_record_preserves_the_failed_language_discriminator(self) -> None:
        entry = self.entries_by_id["preprint-ross-2026-treewidth"]
        self.assertEqual(entry["status"], "disputed")
        self.assertEqual(entry["falsification"]["current_result"], "failed")
        self.assertIn(
            "contradictory",
            {item["support"] for item in entry["evidence"]},
        )

    def test_prize_announcement_is_not_misreported_as_operational(self) -> None:
        entry = self.entries_by_id["policy-tamil-nadu-prize-2025"]
        self.assertEqual(entry["claim"]["kind"], "policy_announcement")
        self.assertIn("announcement only", entry["claim"]["scope"])
        self.assertIn(
            "unverified",
            {limitation["verification"] for limitation in entry["limitations"]},
        )


if __name__ == "__main__":
    unittest.main()
