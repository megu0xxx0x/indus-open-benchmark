from __future__ import annotations

import ast
import re
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from indusbench.kp1979_v3_protocol import (
    C3_PASS_AUTHORIZATION,
    CASE_INVOCATIONS,
    CASE_ROSTER,
    CONTROL_ID,
    EXPECTED_CASE_IDS,
    EXPECTED_METAMORPHIC_RELATIONS,
    INTENDED_PREDICTION_HEIGHT,
    MAXIMUM_PREDICTION_HEIGHT,
    MAXIMUM_PREDICTIONS_PER_INVOCATION,
    METAMORPHIC_ENDPOINT_INVOCATIONS,
    METAMORPHIC_RELATIONS,
    NEGATIVE_CASE_IDS,
    OUT_OF_CONTRACT_CASE_ERRORS,
    POSITIVE_CASE_IDS,
    PUBLIC_CLAIM_BOUNDARY,
    PUBLIC_CLAIM_PERMISSIONS,
    RAW_P4_CONTRACT,
    SYNTHETIC_PAGE_HEIGHT,
    SYNTHETIC_PAGE_WIDTH,
    SYNTHETIC_PBM_BYTE_SIZE,
    SYNTHETIC_PBM_HEADER,
    SYNTHETIC_PBM_PAYLOAD_BYTE_SIZE,
    SYNTHETIC_ROW_BYTES,
    SYNTHETIC_SCAN_BANDS,
    TARGET_ALGORITHM_ID,
    TOTAL_WORKER_INVOCATIONS,
    TRUE_REFERENCE_HALF_HEIGHT,
    V3_PROTOCOL,
    WORKER_ID,
    AuthorizationCondition,
    AuthorizedUse,
    CaseCategory,
    CaseSpec,
    ClaimName,
    ClaimPermission,
    InputErrorCode,
    KP1979V3Protocol,
    KP1979V3ProtocolError,
    MetamorphicKind,
    MetamorphicRelationSpec,
    validate_protocol,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "indusbench" / "kp1979_v3_protocol.py"
LOWER_KEBAB_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)


class KP1979V3ProtocolRosterTests(unittest.TestCase):
    def test_protocol_identifiers_are_exact(self) -> None:
        self.assertEqual("kp1979-label-lattice-synthetic-control-v3", CONTROL_ID)
        self.assertEqual("two-column-glyph-lattice-v3", TARGET_ALGORITHM_ID)
        self.assertEqual("kp1979-label-detector-v3-worker-v1", WORKER_ID)
        self.assertEqual(CONTROL_ID, V3_PROTOCOL.control_id)
        self.assertEqual(TARGET_ALGORITHM_ID, V3_PROTOCOL.target_algorithm_id)
        self.assertEqual(WORKER_ID, V3_PROTOCOL.worker_id)

    def test_positive_roster_is_exact_and_ordered(self) -> None:
        self.assertEqual(
            (
                "positive-renderer-a-clean",
                "positive-renderer-b-clean",
                "positive-renderer-a-pitch-158",
                "positive-renderer-b-pitch-172",
                "positive-mixed-asymmetric",
                "positive-gaps-jitter",
                "positive-double-gaps",
                "positive-unequal-partial-lanes",
                "positive-bounded-damage",
                "positive-stroke-qualifier",
                "positive-horizontal-offsets",
                "positive-sparse-distractors",
            ),
            POSITIVE_CASE_IDS,
        )
        self.assertEqual(
            POSITIVE_CASE_IDS,
            tuple(case.case_id for case in CASE_ROSTER if case.category is CaseCategory.POSITIVE),
        )

    def test_negative_roster_is_exact_and_ordered(self) -> None:
        self.assertEqual(
            (
                "negative-blank",
                "negative-single-lane",
                "negative-cross-lane-pitch-conflict",
                "negative-periodic-single-tier",
                "negative-periodic-two-tier-paired-segments",
                "negative-periodic-paired-dashes",
                "negative-ruled-form",
                "negative-table-grid",
                "negative-repeated-boxes",
                "negative-decorative-border",
                "negative-repeated-stamp",
                "negative-dense-multicolumn",
                "negative-mixed-label-confound",
                "negative-staggered-single-tiers",
            ),
            NEGATIVE_CASE_IDS,
        )
        self.assertEqual(
            NEGATIVE_CASE_IDS,
            tuple(case.case_id for case in CASE_ROSTER if case.category is CaseCategory.NEGATIVE),
        )

    def test_out_of_contract_roster_and_codes_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            (
                (
                    "out-of-contract-truncated-payload",
                    InputErrorCode.INVALID_PBM_PAYLOAD_SIZE,
                ),
                (
                    "out-of-contract-extended-payload",
                    InputErrorCode.INVALID_PBM_PAYLOAD_SIZE,
                ),
                (
                    "out-of-contract-noncanonical-header",
                    InputErrorCode.INVALID_PBM_HEADER,
                ),
                (
                    "out-of-contract-dimension-mismatch",
                    InputErrorCode.INVALID_DIMENSIONS,
                ),
                (
                    "out-of-contract-wrong-scan-extent",
                    InputErrorCode.INVALID_SCAN_BANDS,
                ),
                (
                    "out-of-contract-overlapping-scan-bands",
                    InputErrorCode.INVALID_SCAN_BANDS,
                ),
            ),
            OUT_OF_CONTRACT_CASE_ERRORS,
        )
        actual = tuple(
            (case.case_id, case.expected_error_code)
            for case in CASE_ROSTER
            if case.category is CaseCategory.OUT_OF_CONTRACT
        )
        self.assertEqual(OUT_OF_CONTRACT_CASE_ERRORS, actual)

    def test_case_counts_order_and_identifiers_are_closed(self) -> None:
        self.assertEqual(12, len(POSITIVE_CASE_IDS))
        self.assertEqual(14, len(NEGATIVE_CASE_IDS))
        self.assertEqual(6, len(OUT_OF_CONTRACT_CASE_ERRORS))
        self.assertEqual(32, len(CASE_ROSTER))
        self.assertEqual(EXPECTED_CASE_IDS, tuple(case.case_id for case in CASE_ROSTER))
        ids = tuple(case.case_id for case in CASE_ROSTER)
        self.assertEqual(len(ids), len(set(ids)))
        for case_id in ids:
            self.assertTrue(case_id.isascii())
            self.assertIsNotNone(LOWER_KEBAB_RE.fullmatch(case_id))

    def test_metamorphic_roster_is_exact_and_ordered(self) -> None:
        self.assertEqual(
            (
                ("identical", MetamorphicKind.IDENTICAL, None),
                ("unread-margin", MetamorphicKind.UNREAD_MARGIN, None),
                ("vertical-plus-11", MetamorphicKind.VERTICAL_PLUS_11, 11),
                (
                    "horizontal-translation",
                    MetamorphicKind.HORIZONTAL_TRANSLATION,
                    None,
                ),
                ("stroke-width", MetamorphicKind.STROKE_WIDTH, None),
                (
                    "renderer-substitution",
                    MetamorphicKind.RENDERER_SUBSTITUTION,
                    None,
                ),
                ("lane-swap", MetamorphicKind.LANE_SWAP, None),
                ("gap-deletion", MetamorphicKind.GAP_DELETION, None),
            ),
            EXPECTED_METAMORPHIC_RELATIONS,
        )
        self.assertEqual(8, len(METAMORPHIC_RELATIONS))
        self.assertEqual(
            EXPECTED_METAMORPHIC_RELATIONS,
            tuple(
                (relation.relation_id, relation.kind, relation.vertical_delta)
                for relation in METAMORPHIC_RELATIONS
            ),
        )
        all_ids = tuple(case.case_id for case in CASE_ROSTER) + tuple(
            relation.relation_id for relation in METAMORPHIC_RELATIONS
        )
        self.assertEqual(len(all_ids), len(set(all_ids)))
        for relation in METAMORPHIC_RELATIONS:
            self.assertEqual(2, relation.endpoint_invocations)
            self.assertTrue(relation.relation_id.isascii())
            self.assertIsNotNone(LOWER_KEBAB_RE.fullmatch(relation.relation_id))

    def test_closed_enums_have_no_extra_values(self) -> None:
        expected: tuple[tuple[type[StrEnum], tuple[str, ...]], ...] = (
            (CaseCategory, ("positive", "negative", "out_of_contract")),
            (
                InputErrorCode,
                (
                    "invalid_pbm_payload_size",
                    "invalid_pbm_header",
                    "invalid_dimensions",
                    "invalid_scan_bands",
                ),
            ),
            (
                MetamorphicKind,
                (
                    "identical",
                    "unread-margin",
                    "vertical-plus-11",
                    "horizontal-translation",
                    "stroke-width",
                    "renderer-substitution",
                    "lane-swap",
                    "gap-deletion",
                ),
            ),
            (AuthorizationCondition, ("c3-pass",)),
            (AuthorizedUse, ("owner-only-provisional-candidates",)),
            (
                ClaimName,
                (
                    "page_78",
                    "accuracy",
                    "identifier",
                    "sequence",
                    "language",
                    "meaning",
                    "translation",
                    "decipherment",
                    "prize",
                    "corpus_claim",
                ),
            ),
        )
        for enum_type, values in expected:
            with self.subTest(enum_type=enum_type.__name__):
                self.assertEqual(values, tuple(value.value for value in enum_type))


class KP1979V3ProtocolGeometryAndBoundaryTests(unittest.TestCase):
    def test_raw_p4_contract_is_exact(self) -> None:
        self.assertEqual(4880, SYNTHETIC_PAGE_WIDTH)
        self.assertEqual(7010, SYNTHETIC_PAGE_HEIGHT)
        self.assertEqual(610, SYNTHETIC_ROW_BYTES)
        self.assertEqual(b"P4\n4880 7010\n", SYNTHETIC_PBM_HEADER)
        self.assertEqual(4_276_100, SYNTHETIC_PBM_PAYLOAD_BYTE_SIZE)
        self.assertEqual(4_276_113, SYNTHETIC_PBM_BYTE_SIZE)
        self.assertEqual(
            (
                (2056, 550, 2316, 6600),
                (4232, 550, 4492, 6600),
            ),
            SYNTHETIC_SCAN_BANDS,
        )
        self.assertEqual(SYNTHETIC_PAGE_WIDTH // 8, SYNTHETIC_ROW_BYTES)
        self.assertEqual(
            SYNTHETIC_ROW_BYTES * SYNTHETIC_PAGE_HEIGHT,
            SYNTHETIC_PBM_PAYLOAD_BYTE_SIZE,
        )
        self.assertEqual(
            len(SYNTHETIC_PBM_HEADER) + SYNTHETIC_PBM_PAYLOAD_BYTE_SIZE,
            SYNTHETIC_PBM_BYTE_SIZE,
        )
        self.assertEqual(SYNTHETIC_PAGE_WIDTH, RAW_P4_CONTRACT.width)
        self.assertEqual(SYNTHETIC_PAGE_HEIGHT, RAW_P4_CONTRACT.height)
        self.assertEqual(SYNTHETIC_SCAN_BANDS, RAW_P4_CONTRACT.scan_bands)

    def test_prediction_reference_and_invocation_bounds_are_exact(self) -> None:
        self.assertEqual(96, INTENDED_PREDICTION_HEIGHT)
        self.assertEqual(128, MAXIMUM_PREDICTION_HEIGHT)
        self.assertEqual(128, MAXIMUM_PREDICTIONS_PER_INVOCATION)
        self.assertEqual(28, TRUE_REFERENCE_HALF_HEIGHT)
        self.assertEqual(32, CASE_INVOCATIONS)
        self.assertEqual(16, METAMORPHIC_ENDPOINT_INVOCATIONS)
        self.assertEqual(48, TOTAL_WORKER_INVOCATIONS)
        self.assertEqual(
            len(CASE_ROSTER)
            + sum(relation.endpoint_invocations for relation in METAMORPHIC_RELATIONS),
            TOTAL_WORKER_INVOCATIONS,
        )
        self.assertEqual(TOTAL_WORKER_INVOCATIONS, V3_PROTOCOL.total_worker_invocations)

    def test_c3_pass_authorizes_only_owner_provisional_pages_22_through_77(self) -> None:
        boundary = C3_PASS_AUTHORIZATION
        self.assertIs(AuthorizationCondition.C3_PASS, boundary.condition)
        self.assertIs(
            AuthorizedUse.OWNER_ONLY_PROVISIONAL_CANDIDATES,
            boundary.authorized_use,
        )
        self.assertEqual(22, boundary.first_page)
        self.assertEqual(77, boundary.last_page)
        self.assertIs(True, boundary.owner_only)
        self.assertIs(True, boundary.provisional_candidates_only)
        self.assertIs(False, boundary.page_78_allowed)
        self.assertLess(boundary.last_page, 78)
        self.assertEqual(boundary, V3_PROTOCOL.c3_pass_authorization)

    def test_public_claim_boundary_is_fixed_false_and_machine_readable(self) -> None:
        self.assertIsInstance(PUBLIC_CLAIM_BOUNDARY, MappingProxyType)
        self.assertEqual(
            {
                "page_78": False,
                "accuracy": False,
                "identifier": False,
                "sequence": False,
                "language": False,
                "meaning": False,
                "translation": False,
                "decipherment": False,
                "prize": False,
                "corpus_claim": False,
            },
            dict(PUBLIC_CLAIM_BOUNDARY),
        )
        self.assertEqual(tuple(ClaimName), tuple(item.claim for item in PUBLIC_CLAIM_PERMISSIONS))
        self.assertTrue(all(item.allowed is False for item in PUBLIC_CLAIM_PERMISSIONS))
        self.assertEqual(PUBLIC_CLAIM_PERMISSIONS, V3_PROTOCOL.public_claim_permissions)
        with self.assertRaises(TypeError):
            cast(Any, PUBLIC_CLAIM_BOUNDARY)["accuracy"] = True

    def test_protocol_records_no_page_assignment_or_private_inventory(self) -> None:
        protocol_fields = {field.name for field in fields(KP1979V3Protocol)}
        authorization_fields = {field.name for field in fields(type(C3_PASS_AUTHORIZATION))}
        self.assertTrue(
            {
                "page_numbers",
                "page_assignment",
                "page_count",
                "corpus_count",
                "corpus_digest",
                "private_path",
            }.isdisjoint(protocol_fields | authorization_fields)
        )
        self.assertEqual(77, V3_PROTOCOL.c3_pass_authorization.last_page)
        self.assertIs(False, PUBLIC_CLAIM_BOUNDARY["page_78"])
        self.assertIs(False, PUBLIC_CLAIM_BOUNDARY["corpus_claim"])


class KP1979V3ProtocolMutationTests(unittest.TestCase):
    def test_validate_accepts_only_the_exact_protocol(self) -> None:
        self.assertIsNone(validate_protocol(V3_PROTOCOL))
        with self.assertRaisesRegex(KP1979V3ProtocolError, "closed KP1979V3Protocol"):
            validate_protocol(cast(KP1979V3Protocol, object()))

    def test_duplicate_and_reordered_cases_fail_closed(self) -> None:
        duplicate = replace(
            V3_PROTOCOL,
            cases=(*CASE_ROSTER[:-1], CASE_ROSTER[0]),
        )
        with self.assertRaisesRegex(KP1979V3ProtocolError, "case roster"):
            validate_protocol(duplicate)

        reordered = replace(
            V3_PROTOCOL,
            cases=(CASE_ROSTER[1], CASE_ROSTER[0], *CASE_ROSTER[2:]),
        )
        with self.assertRaisesRegex(KP1979V3ProtocolError, "case roster"):
            validate_protocol(reordered)

    def test_case_category_and_ooc_code_mutations_fail_closed(self) -> None:
        wrong_category = replace(CASE_ROSTER[0], category=CaseCategory.NEGATIVE)
        mutated_cases = (wrong_category, *CASE_ROSTER[1:])
        with self.assertRaisesRegex(KP1979V3ProtocolError, "taxonomy"):
            validate_protocol(replace(V3_PROTOCOL, cases=mutated_cases))

        wrong_error = replace(
            CASE_ROSTER[-1],
            expected_error_code=InputErrorCode.INVALID_DIMENSIONS,
        )
        with self.assertRaisesRegex(KP1979V3ProtocolError, "error-code"):
            validate_protocol(replace(V3_PROTOCOL, cases=(*CASE_ROSTER[:-1], wrong_error)))

    def test_duplicate_and_reordered_relations_fail_closed(self) -> None:
        duplicate = replace(
            V3_PROTOCOL,
            metamorphic_relations=(
                *METAMORPHIC_RELATIONS[:-1],
                METAMORPHIC_RELATIONS[0],
            ),
        )
        with self.assertRaisesRegex(KP1979V3ProtocolError, "metamorphic roster"):
            validate_protocol(duplicate)

        reordered = replace(
            V3_PROTOCOL,
            metamorphic_relations=(
                METAMORPHIC_RELATIONS[1],
                METAMORPHIC_RELATIONS[0],
                *METAMORPHIC_RELATIONS[2:],
            ),
        )
        with self.assertRaisesRegex(KP1979V3ProtocolError, "metamorphic roster"):
            validate_protocol(reordered)

    def test_invocation_accounting_mutations_fail_closed(self) -> None:
        for field_name, value in (
            ("case_invocations", 31),
            ("metamorphic_endpoint_invocations", 15),
            ("total_worker_invocations", 47),
        ):
            with self.subTest(field_name=field_name):
                mutated = replace(V3_PROTOCOL, **{field_name: value})
                with self.assertRaisesRegex(KP1979V3ProtocolError, "invocation"):
                    validate_protocol(mutated)

    def test_non_ascii_non_kebab_and_non_string_ids_are_rejected(self) -> None:
        for case_id in (
            "Upper-case",
            "under_score",
            "double--dash",
            "-leading",
            "trailing-",
            "非ascii",
            "",
        ):
            with (
                self.subTest(case_id=case_id),
                self.assertRaisesRegex(KP1979V3ProtocolError, "ASCII lower-kebab"),
            ):
                CaseSpec(case_id, CaseCategory.POSITIVE, None)
        with self.assertRaisesRegex(KP1979V3ProtocolError, "must be a string"):
            CaseSpec(cast(str, 1), CaseCategory.POSITIVE, None)

    def test_raw_enum_values_are_rejected_even_when_text_matches(self) -> None:
        with self.assertRaisesRegex(KP1979V3ProtocolError, "closed CaseCategory"):
            CaseSpec(
                "positive-raw-enum",
                cast(CaseCategory, "positive"),
                None,
            )
        with self.assertRaisesRegex(KP1979V3ProtocolError, "closed InputErrorCode"):
            CaseSpec(
                "out-of-contract-raw-error",
                CaseCategory.OUT_OF_CONTRACT,
                cast(InputErrorCode, "invalid_dimensions"),
            )
        with self.assertRaisesRegex(KP1979V3ProtocolError, "closed MetamorphicKind"):
            MetamorphicRelationSpec(
                relation_id="raw-relation",
                kind=cast(MetamorphicKind, "identical"),
                endpoint_invocations=2,
                vertical_delta=None,
            )

    def test_booleans_are_rejected_from_every_integer_boundary(self) -> None:
        with self.assertRaisesRegex(KP1979V3ProtocolError, "not a boolean"):
            replace(RAW_P4_CONTRACT, width=True)
        with self.assertRaisesRegex(KP1979V3ProtocolError, "not a boolean"):
            replace(METAMORPHIC_RELATIONS[0], endpoint_invocations=True)
        with self.assertRaisesRegex(KP1979V3ProtocolError, "not a boolean"):
            replace(V3_PROTOCOL, total_worker_invocations=True)

    def test_lists_subclasses_and_wrong_closed_types_are_rejected(self) -> None:
        with self.assertRaisesRegex(KP1979V3ProtocolError, "exact tuple of CaseSpec"):
            replace(V3_PROTOCOL, cases=cast(tuple[CaseSpec, ...], list(CASE_ROSTER)))
        with self.assertRaisesRegex(KP1979V3ProtocolError, r"exact .*tuple"):
            replace(
                RAW_P4_CONTRACT,
                scan_bands=cast(
                    tuple[tuple[int, int, int, int], ...],
                    list(SYNTHETIC_SCAN_BANDS),
                ),
            )

        class CaseSpecSubclass(CaseSpec):
            pass

        subclass_value = CaseSpecSubclass(
            "positive-subclass",
            CaseCategory.POSITIVE,
            None,
        )
        with self.assertRaisesRegex(KP1979V3ProtocolError, "exact tuple of CaseSpec"):
            replace(
                V3_PROTOCOL,
                cases=(*CASE_ROSTER[:-1], subclass_value),
            )

    def test_claim_mutations_and_bool_aliases_fail_closed(self) -> None:
        with self.assertRaisesRegex(KP1979V3ProtocolError, "exact boolean"):
            ClaimPermission(ClaimName.ACCURACY, cast(bool, 0))
        with self.assertRaisesRegex(KP1979V3ProtocolError, "cannot authorize"):
            ClaimPermission(ClaimName.ACCURACY, True)
        with self.assertRaisesRegex(KP1979V3ProtocolError, "closed ClaimName"):
            ClaimPermission(cast(ClaimName, "accuracy"), False)
        with self.assertRaisesRegex(KP1979V3ProtocolError, "public claim boundary"):
            validate_protocol(
                replace(
                    V3_PROTOCOL,
                    public_claim_permissions=PUBLIC_CLAIM_PERMISSIONS[:-1],
                )
            )

    def test_page_78_and_non_owner_authorization_mutations_fail_at_construction(self) -> None:
        for field_name, value in (
            ("last_page", 78),
            ("owner_only", False),
            ("provisional_candidates_only", False),
            ("page_78_allowed", True),
        ):
            with (
                self.subTest(field_name=field_name),
                self.assertRaises(KP1979V3ProtocolError),
            ):
                replace(C3_PASS_AUTHORIZATION, **{field_name: value})

    def test_all_contract_dataclasses_are_frozen_and_slotted(self) -> None:
        instances = (
            RAW_P4_CONTRACT,
            CASE_ROSTER[0],
            METAMORPHIC_RELATIONS[0],
            PUBLIC_CLAIM_PERMISSIONS[0],
            C3_PASS_AUTHORIZATION,
            V3_PROTOCOL,
        )
        for instance in instances:
            with self.subTest(instance_type=type(instance).__name__):
                self.assertFalse(hasattr(instance, "__dict__"))
                with self.assertRaises(FrozenInstanceError):
                    setattr(instance, fields(instance)[0].name, object())


class KP1979V3ProtocolStaticBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = MODULE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_module_imports_only_standard_library_contract_helpers(self) -> None:
        imported_modules = {
            node.module
            for node in ast.walk(self.tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertEqual(
            {
                "__future__",
                "re",
                "dataclasses",
                "enum",
                "types",
                "typing",
            },
            imported_modules,
        )
        self.assertTrue(all(not module.startswith("indusbench.") for module in imported_modules))

    def test_module_has_no_v2_import_or_dependency(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn("v2", node.module or "")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn("v2", alias.name)
        self.assertNotIn("kp1979_v2_runner", self.source)
        self.assertNotIn("kp1979_synthetic_control_v2", self.source)
        self.assertNotIn("kp1979_detector_v2_worker", self.source)

    def test_protocol_contains_no_generator_truth_seed_round_or_detector_logic(self) -> None:
        forbidden_fields = {
            "truth",
            "references",
            "reference_intervals",
            "seed",
            "round",
            "randomness",
            "signature",
            "generator",
            "pbm_bytes",
            "predictions",
        }
        declared_fields = {
            target.id
            for node in ast.walk(self.tree)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            for target in (node.target,)
        }
        self.assertTrue(forbidden_fields.isdisjoint(declared_fields))
        forbidden_function_prefixes = (
            "build_",
            "generate_",
            "render_",
            "detect_",
            "evaluate_",
            "score_",
            "verify_beacon",
        )
        function_names = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertFalse(
            any(name.startswith(forbidden_function_prefixes) for name in function_names)
        )

    def test_protocol_performs_no_io_process_network_or_dynamic_code_execution(self) -> None:
        called_names = {
            node.func.id
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(
            {
                "open",
                "exec",
                "eval",
                "compile",
                "__import__",
                "system",
                "run",
                "Popen",
            }.isdisjoint(called_names)
        )

    def test_public_contract_contains_no_private_values_or_digests(self) -> None:
        forbidden_fragments = (
            "/home/",
            "/Users/",
            "private_corpus",
            "corpus_sha256",
            "audit_result",
        )
        for fragment in forbidden_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, self.source)


if __name__ == "__main__":
    unittest.main()
