"""Closed checks for the source-free numeral/metrology draft protocol."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from indusbench.io import read_json
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
SCHEMA_PATH = ROOT / "schemas/hypothesis.schema.json"
PROTOCOL_DOC_PATH = ROOT / "docs/NUMERAL_METROLOGY_FUNCTIONAL_ANCHOR_PROTOCOL_V1.md"
DEVELOPMENT_LOG_PATH = ROOT / "docs/DEVELOPMENT_LOG.md"
DEVELOPMENT_PLAN_PATH = ROOT / "docs/DEVELOPMENT_PLAN_AND_LOG.md"

PROTOCOL_SHA256 = "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"
UPDATED_AT = "2026-08-02T03:48:48Z"

ASSUMPTION_IDS = {
    "NMFA-STATE-001",
    "NMFA-DATA-001",
    "NMFA-TARGET-001",
    "NMFA-POLICY-001",
    "NMFA-NONCLAIM-001",
}
RULE_IDS = {
    "NMFA-ELIG-001",
    "NMFA-MODEL-001",
    "NMFA-FAMILY-001",
    "NMFA-SPLIT-001",
    "NMFA-METRIC-001",
    "NMFA-NULL-001",
    "NMFA-MULT-001",
    "NMFA-PROSP-001",
    "NMFA-ERR-001",
    "NMFA-CHANGE-001",
}
CLAIM_IDS = {"NMFA-HYP-001"}
KILL_IDS = ("NMFA-KILL-001", "NMFA-KILL-002", "NMFA-KILL-003")


class NumeralMetrologyFunctionalAnchorProtocolTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.raw = PROTOCOL_PATH.read_bytes()
        self.protocol = read_json(PROTOCOL_PATH)
        self.rules = {rule["rule_id"]: rule["formalism"] for rule in self.protocol["rules"]}

    def test_matches_existing_hypothesis_schema(self) -> None:
        self.assertEqual([], validate_schema_instance(self.protocol, SCHEMA_PATH))

    def test_exact_payload_and_revision_time_are_locked(self) -> None:
        self.assertEqual(PROTOCOL_SHA256, hashlib.sha256(self.raw).hexdigest())
        self.assertEqual("2026-08-02T02:45:00Z", self.protocol["created_at"])
        self.assertEqual(UPDATED_AT, self.protocol["updated_at"])
        created = datetime.fromisoformat(self.protocol["created_at"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(self.protocol["updated_at"].replace("Z", "+00:00"))
        self.assertLessEqual(created, updated)
        jst = updated.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S JST")
        marker = f"**Final draft revision/checkpoint:** {jst}"
        for path in (PROTOCOL_DOC_PATH, DEVELOPMENT_LOG_PATH, DEVELOPMENT_PLAN_PATH):
            with self.subTest(path=path.name):
                self.assertIn(marker, path.read_text(encoding="utf-8"))

    def test_is_exactly_a_source_free_unregistered_draft(self) -> None:
        self.assertEqual("draft", self.protocol["status"])
        self.assertEqual(
            {
                "frozen": False,
                "registered_at": None,
                "registry_uri": None,
                "content_hash": None,
            },
            self.protocol["preregistration"],
        )
        for field in ("artifact_ids", "site_ids", "period_labels", "object_types"):
            self.assertEqual([], self.protocol["scope"][field])
        for field in ("sign_mappings", "predictions", "evidence", "exceptions"):
            self.assertEqual([], self.protocol[field])
        for rule in self.protocol["rules"]:
            self.assertEqual([], rule["applies_to"])
        for claim in self.protocol["claims"]:
            self.assertEqual([], claim["observation_refs"])
            self.assertEqual(0.0, claim["confidence"])
            self.assertEqual(
                {
                    "text": None,
                    "sign_ids": [],
                    "boundaries": [],
                    "direction": "unknown",
                    "language": None,
                    "value_type": "functional",
                    "numeric_value": None,
                },
                claim["proposed_value"],
            )

    def test_ids_are_unique_and_all_rule_claims_close(self) -> None:
        assumptions = self.protocol["assumptions"]
        rules = self.protocol["rules"]
        claims = self.protocol["claims"]
        self.assertEqual(ASSUMPTION_IDS, {item["assumption_id"] for item in assumptions})
        self.assertEqual(len(assumptions), len(ASSUMPTION_IDS))
        self.assertEqual(RULE_IDS, {item["rule_id"] for item in rules})
        self.assertEqual(len(rules), len(RULE_IDS))
        self.assertEqual(CLAIM_IDS, {item["claim_id"] for item in claims})
        self.assertEqual(len(claims), len(CLAIM_IDS))
        self.assertEqual(CLAIM_IDS, {rule["claim_id"] for rule in rules})

    def test_data_physical_units_and_superfamily_closure_are_locked(self) -> None:
        data = next(
            item["statement"]
            for item in self.protocol["assumptions"]
            if item["assumption_id"] == "NMFA-DATA-001"
        )
        for fragment in (
            "bind eight roles",
            "E is the complete value-free",
            "documentation/measurement-provenance nuisance fields",
            "F is one physical-original all-side analysis unit",
            "G is the target-blind transitive leakage/dependence superfamily",
        ):
            self.assertIn(fragment, data)

        eligibility = self.rules["NMFA-ELIG-001"]
        for fragment in (
            "freeze one documentation/measurement-provenance policy",
            "restricted to one prespecified transcription/annotation",
            "complete canonical nuisance tuple",
            "unknown nuisance provenance is ineligible",
        ):
            self.assertIn(fragment, eligibility)

        family = self.rules["NMFA-FAMILY-001"]
        for fragment in (
            "A distinct cast, replica, impression, or mold product is never merged into F",
            "G is closed across every F, eligible or not",
            "possible/unresolved relation",
            "unknown relation status is never treated as evidence of independence",
            "M_G={F in G:E(F)=true}",
            "every F in G has complete canonical C",
            "minimum hash among M_G members whose canonical C triggers that assigned cell",
            "incoming F that bridges >=2 historical G",
            "incoming F connected to exactly one historical G is absorbed",
            "prospective-only relations close prospectively",
        ):
            self.assertIn(fragment, family)

    def test_strict_split_and_unpredictable_nonce_are_locked(self) -> None:
        split = self.rules["NMFA-SPLIT-001"]
        for fragment in (
            "at least 160 eligible G",
            "complete value-free E",
            "E/F/G/M_G/C eligible-inventory digest",
            "including E-ineligible F",
            "C_axis(G)",
            "closure_C(s) intersects C_site(G)",
            "every disjoint cell has >=20 G",
            "union H has >=80 G",
            "complement D has >=80 G",
            "every H member has at least one F in M_G",
            "externally verifiable unpredictable split_nonce",
            "Retry and resalting are forbidden",
            "[development, development, validation]",
        ):
            self.assertIn(fragment, split)

    def test_model_effect_length_and_bootstrap_gates_are_locked(self) -> None:
        model = self.rules["NMFA-MODEL-001"]
        for fragment in (
            "canonical concatenation of every eligible side/inscription",
            "L_total=all eligible token count",
            "L_distinct=distinct frozen token/allograph-class count",
            "1<=J<=8",
            "1<=w_j<=16",
            "select exactly one ordinal score on validation",
        ):
            self.assertIn(fragment, model)

        metric = self.rules["NMFA-METRIC-001"]
        for fragment in (
            "exactly one per G",
            "rho_H>=0.40",
            "delta_length>=0.10",
            "10,000 H-cell-stratified G bootstrap replicates",
            "in each identical resample",
            "250th one-based value",
            "lower(CI95_rho)>0.20",
            "lower(CI95_delta_length)>0.00",
            "rho_cell>=0.20",
            ">=4 distinct observed levels for both S and Y",
            "undefined/nonfinite bootstrap rho_H is assigned -1",
            "paired interval must independently exclude zero",
        ):
            self.assertIn(fragment, metric)

    def test_specificity_and_full_context_null_controls_are_locked(self) -> None:
        controls = self.rules["NMFA-NULL-001"]
        for fragment in (
            "R=99,999",
            "development G-prevalence power-of-two bin",
            "N1 is a token-specificity negative control",
            "not an inferential p value",
            "exact full-C tuple",
            "documentation/measurement-provenance nuisance field",
            "at least 80% and at least 64 H G",
            "preserves every observed C and nuisance association",
            "q0.99 is the 99,000th one-based value",
            "specificity_tail_fraction",
            "N2 p=",
            "If N1 or N2 support cannot be constructed before H opens",
        ):
            self.assertIn(fragment, controls)
        self.assertIn("K=1 is mandatory", self.rules["NMFA-MULT-001"])
        self.assertIn(
            "requires a separately registered protocol with fresh H",
            self.rules["NMFA-MULT-001"],
        )

    def test_prospective_sequence_context_and_terminal_precedence_are_locked(self) -> None:
        prospective = self.rules["NMFA-PROSP-001"]
        for fragment in (
            "commit the prospective source frame",
            "design-stage sensitivity/power rationale",
            "only an evaluability floor, not a claim of adequate power",
            "first eligibility-qualifying source-bound availability",
            "strictly later than the immutable model, policy, and prediction-algorithm freeze",
            "available earlier is historical and ineligible",
            "include every qualifying unit",
            "re-close relations against all historical and prospective F",
            "joined to exactly one historical G is absorbed",
            "bridging >=2 historical G or historical partitions",
            "relations only among incoming F close into one prospective G",
            "Require nonempty M_G and complete C",
            "complete G-to-S prediction manifest",
            "while Y remains sealed",
            "Before Y reveal, require >=20 new G",
            "at least 80% and at least 16 prospective G",
            "Do not reveal Y in any of those states",
            "INSUFFICIENT_PROSPECTIVE_CONTEXT_SUPPORT",
            "delta_length=rho-rho_length>=0.10",
            "lower(CI95_rho)>0.20",
            "lower(CI95_delta_length)>0.00",
            "prospective-bootstrap-v1 and prospective-null-n2-v1",
            "freeze exact seed encoding and generator semantics",
            "99,999-run one-sided whole-G Y-permutation within the frozen full-C strata",
            "INSUFFICIENT_PROSPECTIVE_DATA",
            "INSUFFICIENT_PROSPECTIVE_VARIATION",
        ):
            self.assertIn(fragment, prospective)

        errors = self.rules["NMFA-ERR-001"]
        for fragment in (
            "BENCHMARK_INVALID > EVALUATION_VOID > CANDIDATE_INVALID/NO_GO",
            "CONFIRMATORY_NO_GO",
            "any INSUFFICIENT_PROSPECTIVE_* state",
            "PROSPECTIVE_NO_GO > FUNCTIONAL_ANCHOR_CANDIDATE",
            "cannot be masked by later prospective insufficiency",
            "fresh H",
        ):
            self.assertIn(fragment, errors)

    def test_one_zero_confidence_hypothesis_has_exactly_three_closed_kills(self) -> None:
        claim = self.protocol["claims"][0]
        self.assertEqual("NMFA-HYP-001", claim["claim_id"])
        self.assertEqual("functional_interpretation", claim["claim_type"])
        self.assertEqual(0.0, claim["confidence"])
        criteria = claim["falsification_criteria"]
        self.assertEqual(KILL_IDS, tuple(item.split(" — ", 1)[0] for item in criteria))
        self.assertIn("delta_length=rho_H-rho_length<0.10", criteria[0])
        self.assertIn("paired lower(CI95_delta_length)<=0.00", criteria[0])
        self.assertIn("specificity_tail_fraction>0.01", criteria[1])
        self.assertIn("lower(CI95_delta_length)<=0.00", criteria[2])
        self.assertIn("full-C-stratified", criteria[2])
        self.assertIn("any INSUFFICIENT_PROSPECTIVE_* state", criteria[2])

        change = self.rules["NMFA-CHANGE-001"]
        self.assertIn("prospective-only edges", change)
        self.assertIn("incoming F to exactly one historical G", change)

    def test_protocol_is_shipped_in_the_wheel(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        force_include = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
        self.assertEqual(
            "indusbench/benchmark/numeral-metrology-functional-anchor-protocol-v1.json",
            force_include["benchmark/numeral-metrology-functional-anchor-protocol-v1.json"],
        )


if __name__ == "__main__":
    unittest.main()
