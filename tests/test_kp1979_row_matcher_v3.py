from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import indusbench.kp1979_match_calibration_v3 as calibration_v3
import indusbench.kp1979_row_matcher_v3 as row_matcher_v3
from indusbench.io import encode_json
from indusbench.kp1979_glyph_match import build_template_index
from indusbench.kp1979_match_calibration import calibrate_matcher_plan
from indusbench.kp1979_match_calibration_v3 import (
    calibrate_matcher_plan_v3,
    matcher_config_from_recomputed_plan_v3,
)
from indusbench.kp1979_row_matcher import (
    KP1979RowMatcherError,
    build_row_match_proposal,
)
from indusbench.kp1979_row_matcher_v3 import (
    build_row_match_proposal_v3,
    verify_row_match_proposal_v3_bytes,
)
from indusbench.kp1979_row_separator import match_row_with_separator
from indusbench.schema_validation import validate_schema_instance
from tests.test_kp1979_match_calibration import (
    BOUND_TEMPLATES,
    CROSS,
    SMALL_GRID,
    config,
    pbm,
    roster_bytes_for,
)
from tests.test_kp1979_row_matcher import (
    DEVELOPMENT_ROW_ID,
    RESERVED_ROW_ID,
    ROW_PBM,
    assignment_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
V3_PROPOSAL_SCHEMA = ROOT / "schemas" / "kp1979-row-match-proposal-v2.schema.json"

TemplatePBM = tuple[str, int, bytes]


def stable_v3_templates() -> tuple[TemplatePBM, ...]:
    size = 31
    center = size // 2
    predicates = (
        lambda x, y: abs(x - center) <= 3 or abs(y - center) <= 3,
        lambda x, y: min(x, y, size - 1 - x, size - 1 - y) < 5,
        lambda x, y: y < 7 or abs(x - center) <= 3,
    )
    return tuple(
        (
            f"KP1979:P20:L97:R0{position}",
            10 + position,
            pbm(
                *(
                    "".join("#" if predicate(x, y) else "." for x in range(size))
                    for y in range(size)
                )
            ),
        )
        for position, predicate in enumerate(predicates)
    )


class KP1979RowMatcherV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.templates = stable_v3_templates()
        cls.glyphs = {variant_id: raw_bytes for variant_id, _rank, raw_bytes in cls.templates}
        cls.roster_bytes = roster_bytes_for(cls.templates)
        cls.plan = calibrate_matcher_plan_v3(cls.templates)
        if cls.plan["status"] != "frozen_closed_template_candidate_ranking_only":
            raise AssertionError("public synthetic V3 matcher plan did not freeze")
        cls.plan_bytes = encode_json(cls.plan)
        cls.assignment_bytes = assignment_bytes()

    @staticmethod
    def _development_row_loader(calls: list[str]):
        def load(row_id: str) -> bytes:
            calls.append(row_id)
            if row_id == RESERVED_ROW_ID:
                raise AssertionError("reserved future row was opened")
            if row_id != DEVELOPMENT_ROW_ID:
                raise AssertionError(f"unexpected synthetic row {row_id}")
            return ROW_PBM

        return load

    def test_exact_v3_plan_build_verify_and_structural_api_is_not_authority(self) -> None:
        row_calls: list[str] = []
        row_loader = self._development_row_loader(row_calls)
        with patch.object(
            calibration_v3,
            "validate_matcher_plan_v3",
            side_effect=AssertionError("structural state API was used as authority"),
        ):
            proposal = build_row_match_proposal_v3(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                row_loader,
            )
            proposal_bytes = encode_json(proposal)
            summary = verify_row_match_proposal_v3_bytes(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                row_loader,
                proposal_bytes,
            )

        self.assertEqual([DEVELOPMENT_ROW_ID, DEVELOPMENT_ROW_ID], row_calls)
        self.assertEqual([], validate_schema_instance(proposal, V3_PROPOSAL_SCHEMA))
        self.assertEqual(
            "KP1979:BASE:DEVELOPMENT:ROW-MATCH-PROPOSAL:V2",
            proposal["manifest_id"],
        )
        self.assertEqual(
            calibration_v3.MATCHER_PLAN_ID,
            proposal["input_bindings"]["matcher_plan"]["id"],
        )
        self.assertEqual(
            "frozen_closed_template_candidate_ranking_only",
            proposal["calibration_scope"]["matcher_plan_status"],
        )
        self.assertIs(proposal["calibration_scope"]["tier_b_accepted"], False)
        self.assertIs(proposal["calibration_scope"]["speck_robustness_claimed"], False)
        self.assertIs(proposal["assurances"]["real_row_tier_assigned"], False)
        self.assertIs(summary["valid"], True)
        self.assertIs(summary["frozen_matcher_plan_v3_verified"], True)
        self.assertIs(summary["tier_b_accepted"], False)
        self.assertIs(summary["reserved_future_rows_loaded"], False)

        tampered = copy.deepcopy(proposal)
        tampered["assurances"]["tier_b_accepted"] = True
        with self.assertRaises(KP1979RowMatcherError):
            verify_row_match_proposal_v3_bytes(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                self._development_row_loader([]),
                encode_json(tampered),
            )

        noncanonical = json.dumps(proposal, separators=(",", ":")).encode()
        with self.assertRaisesRegex(KP1979RowMatcherError, "not canonical"):
            verify_row_match_proposal_v3_bytes(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                self._development_row_loader([]),
                noncanonical,
            )

    def test_no_go_tamper_v2_and_custom_grid_fail_before_row_loading(self) -> None:
        no_go_roster = roster_bytes_for(BOUND_TEMPLATES)
        no_go_glyphs = {variant_id: raw_bytes for variant_id, _rank, raw_bytes in BOUND_TEMPLATES}
        no_go_plan = calibrate_matcher_plan_v3(BOUND_TEMPLATES)
        self.assertEqual("no_go", no_go_plan["status"])

        tampered = copy.deepcopy(self.plan)
        tampered["configuration"]["max_token_cost"] = 5_000_000

        v2_plan = calibrate_matcher_plan(self.templates)
        self.assertEqual(
            "KP1979:GLYPH-MATCHER-PLAN:V2",
            v2_plan["matcher_plan_id"],
        )

        custom_grid_plan = calibrate_matcher_plan_v3(self.templates, grid=SMALL_GRID)
        self.assertEqual(
            "frozen_closed_template_candidate_ranking_only",
            custom_grid_plan["status"],
        )

        failures = (
            (
                "no-go",
                no_go_roster,
                no_go_glyphs,
                encode_json(no_go_plan),
            ),
            (
                "tampered",
                self.roster_bytes,
                self.glyphs,
                encode_json(tampered),
            ),
            (
                "v2-plan",
                self.roster_bytes,
                self.glyphs,
                encode_json(v2_plan),
            ),
            (
                "custom-grid",
                self.roster_bytes,
                self.glyphs,
                encode_json(custom_grid_plan),
            ),
        )
        for label, roster_bytes, glyphs, plan_bytes in failures:
            row_calls: list[str] = []
            with (
                self.subTest(label=label),
                self.assertRaisesRegex(
                    KP1979RowMatcherError,
                    "exact template-only recomputation",
                ),
            ):
                build_row_match_proposal_v3(
                    self.assignment_bytes,
                    roster_bytes,
                    plan_bytes,
                    glyphs.__getitem__,
                    self._development_row_loader(row_calls),
                )
            self.assertEqual([], row_calls)

        reverse_row_calls: list[str] = []
        with self.assertRaisesRegex(
            KP1979RowMatcherError,
            "exact template-only recomputation",
        ):
            build_row_match_proposal(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                self.glyphs.__getitem__,
                self._development_row_loader(reverse_row_calls),
            )
        self.assertEqual([], reverse_row_calls)

    def test_glyph_commitment_failure_precedes_development_row_loading(self) -> None:
        row_calls: list[str] = []

        def tampered_glyph_loader(variant_id: str) -> bytes:
            return self.glyphs[variant_id] + b"tamper"

        with self.assertRaisesRegex(KP1979RowMatcherError, "roster commitment"):
            build_row_match_proposal_v3(
                self.assignment_bytes,
                self.roster_bytes,
                self.plan_bytes,
                tampered_glyph_loader,
                self._development_row_loader(row_calls),
            )
        self.assertEqual([], row_calls)

    def test_compiled_default_grid_and_stability_gates_are_runtime_bound(self) -> None:
        matcher_config = matcher_config_from_recomputed_plan_v3(
            self.plan_bytes,
            self.roster_bytes,
            self.templates,
            grid=calibration_v3.CalibrationGrid(),
        )
        self.assertTrue(matcher_config.require_speck_stability)
        self.assertTrue(matcher_config.require_shift_stability)
        self.assertEqual(
            calibration_v3.CalibrationGrid(),
            row_matcher_v3._TRUSTED_CALIBRATION_GRID,
        )

    def test_real_speck_failed_matcher_result_remains_ambiguous(self) -> None:
        row = pbm(
            ".......#.",
            ".#.....#.",
            ".......#.",
        )
        index = build_template_index(
            (
                ("dot", 1, pbm("#")),
                ("cross", 2, CROSS),
            )
        )
        result = match_row_with_separator(
            row_id="synthetic-speck-row",
            row_pbm=row,
            proposed_label_bbox=(7, 0, 8, 3),
            index=index,
            config=config(),
        )
        self.assertEqual("ambiguous", result["proposal_status"])
        self.assertIs(result["gates"]["best_matcher_proposed"], False)
        self.assertIs(
            result["candidate_paths"][0]["matcher_gates"]["speck_ablation_stability_passed"],
            False,
        )
        row_matcher_v3._validate_speck_nonpromotion(result)

        promoted: dict[str, Any] = copy.deepcopy(result)
        promoted["proposal_status"] = "proposed"
        promoted["gates"]["best_matcher_proposed"] = True
        promoted["candidate_paths"][0]["matcher_proposal_status"] = "proposed"
        with self.assertRaisesRegex(KP1979RowMatcherError, "promoted"):
            row_matcher_v3._validate_speck_nonpromotion(promoted)

    def test_v2_schema_is_closed_nonattesting_and_contains_no_interpretation(self) -> None:
        schema = json.loads(V3_PROPOSAL_SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("schema validity alone does not attest", schema["description"].lower())
        self.assertEqual("0.2.0", schema["properties"]["schema_version"]["const"])
        calibration = schema["properties"]["calibration_scope"]["const"]
        self.assertIs(calibration["tier_b_accepted"], False)
        self.assertIs(calibration["speck_robustness_claimed"], False)
        self.assertIs(calibration["real_row_performance_claimed"], False)

        property_names: set[str] = set()
        pending: list[object] = [schema]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                properties = value.get("properties")
                if isinstance(properties, dict):
                    property_names.update(properties)
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        self.assertTrue(
            {
                "identifier",
                "code",
                "reading",
                "reading_direction",
                "language",
                "meaning",
                "translation",
                "sign_sequence",
                "accepted_sign",
                "inventory",
                "summary",
                "row_count",
                "template_count",
            }.isdisjoint(property_names)
        )


if __name__ == "__main__":
    unittest.main()
