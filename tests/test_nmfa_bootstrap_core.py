from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from indusbench import nmfa_bootstrap_core as bootstrap_core
from indusbench.io import read_json
from indusbench.nmfa_bootstrap_core import (
    ProtectedNMFABootstrapState,
    _BootstrapRow,
)
from indusbench.nmfa_counter_stream import NMFACounterStream
from indusbench.nmfa_measurement_common import (
    ValidatedNMFAGFRoster,
    ValidatedNMFAMetricRoster,
)
from indusbench.nmfa_resampling_common import (
    _AXES,
    _CELL_ROSTER_DOMAIN,
    _SCHEDULE_DOMAIN,
    NMFAResamplingError,
    NMFAResamplingErrorCode,
    _domain_digest,
)
from indusbench.nmfa_y_rational_core import CanonicalRational

_ZERO_CHECKSUM = "sha256:" + "0" * 64
ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark/nmfa-resampling-core-plan-v1.json"


def _cells() -> dict[str, tuple[_BootstrapRow, ...]]:
    cells: dict[str, tuple[_BootstrapRow, ...]] = {}
    for cell_index, axis in enumerate(_AXES):
        rows = []
        for local_index in range(20):
            value = cell_index * 100 + local_index
            rows.append(
                _BootstrapRow(
                    g_id=f"sha256:{value:064x}",
                    primary_f_id=f"hmac-sha256:{value:064x}",
                    score=value,
                    l_total=value + 10_000,
                    l_distinct=value + 20_000,
                    target=CanonicalRational(value + 1, 1),
                )
            )
        cells[axis] = tuple(rows)
    return cells


def _defined_zero_metric(_: list[int], __: list[CanonicalRational]) -> dict[str, Any]:
    return {
        "covariance_c": "0",
        "denominator_radicand": "1",
        "status": "defined",
    }


class NMFABootstrapCoreTests(unittest.TestCase):
    def test_protected_state_is_factory_issued_and_rejects_forgery(self) -> None:
        raw = b"{}\n"
        arguments = {
            "receipt_bytes": raw,
            "receipt_raw_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "receipt_sha256": "sha256:" + "1" * 64,
            "bundle_sha256": "sha256:" + "2" * 64,
        }
        for token in (None, object()):
            with self.subTest(token=token), self.assertRaises(NMFAResamplingError) as caught:
                ProtectedNMFABootstrapState(**arguments, _token=token)
            self.assertIs(caught.exception.code, NMFAResamplingErrorCode.INVALID_ARGUMENT)

        forged = object.__new__(ProtectedNMFABootstrapState)
        for name, value in arguments.items():
            object.__setattr__(forged, name, value)
        with (
            patch.object(bootstrap_core, "_decode_bootstrap_receipt") as decode,
            self.assertRaises(NMFAResamplingError) as caught,
        ):
            forged.receipt()
        self.assertIs(
            caught.exception.code,
            NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
        )
        decode.assert_not_called()

        object.__setattr__(forged, "_construction_marker", object())
        with self.assertRaises(NMFAResamplingError) as caught:
            forged.receipt()
        self.assertIs(
            caught.exception.code,
            NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
        )

    def test_exact_rho_substitutes_only_closed_undefined_statuses(self) -> None:
        for status in bootstrap_core._UNDEFINED_METRIC_STATUSES:
            candidate, substituted = bootstrap_core._exact_rho({"status": status}, -1)
            self.assertTrue(substituted)
            self.assertEqual((-1, 1), (candidate.covariance_c, candidate.denominator_radicand))
        with self.assertRaises(NMFAResamplingError) as caught:
            bootstrap_core._exact_rho({"status": "unexpected_internal_state"}, -1)
        self.assertIs(caught.exception.code, NMFAResamplingErrorCode.EXACT_ORDER_INVALID)

    def test_schedule_commitment_matches_frozen_small_vector(self) -> None:
        vector = read_json(PLAN_PATH)["fixed_vectors"]["bootstrap_schedule"]
        roster_sha256 = _domain_digest(
            _CELL_ROSTER_DOMAIN,
            {"rows": vector["cell_roster_rows"]},
        )
        self.assertEqual(
            roster_sha256,
            "sha256:" + vector["expected_cell_roster_sha256_hex"],
        )
        key = bytes.fromhex(vector["frozen_protocol_chain_head_sha256_hex"])
        cell_sizes = tuple(vector["cell_sizes"])
        accepted: list[int] = []
        for run_index in range(vector["run_count"]):
            stream = NMFACounterStream(key, "bootstrap-v1", run_index)
            for cell_size in cell_sizes:
                accepted.extend(stream.draw_index(cell_size) for _ in range(cell_size))
        self.assertEqual(accepted, vector["accepted_local_indices"])

        hasher = bootstrap_core._schedule_hasher(
            roster_sha256,
            key,
            vector["run_count"],
            cell_sizes,
        )
        for local_index in accepted:
            hasher.update(local_index.to_bytes(8, "big"))
        self.assertEqual(
            hasher.hexdigest(),
            vector["expected_schedule_sha256_hex"],
        )

        swapped = bootstrap_core._schedule_hasher(
            "sha256:" + key.hex(),
            bytes.fromhex(roster_sha256[7:]),
            vector["run_count"],
            cell_sizes,
        )
        for local_index in accepted:
            swapped.update(local_index.to_bytes(8, "big"))
        self.assertNotEqual(swapped.hexdigest(), vector["expected_schedule_sha256_hex"])

        omitted_roster = hashlib.sha256()
        omitted_roster.update(_SCHEDULE_DOMAIN)
        omitted_roster.update(key)
        for value in (
            vector["run_count"],
            vector["total_holdout_rows"],
            len(cell_sizes),
            *cell_sizes,
        ):
            omitted_roster.update(value.to_bytes(8, "big"))
        for local_index in accepted:
            omitted_roster.update(local_index.to_bytes(8, "big"))
        self.assertNotEqual(
            omitted_roster.hexdigest(),
            vector["expected_schedule_sha256_hex"],
        )

    def test_cell_roster_commitment_keeps_global_metric_order(self) -> None:
        assignments: list[dict[str, Any]] = [
            {
                "cell": cell,
                "g_id": f"sha256:{index:064x}",
                "partition": "holdout",
                "primary_f_id": f"hmac-sha256:{index:064x}",
            }
            for index, cell in enumerate(("period", "site", "medium", "site"))
        ]
        assignments.insert(
            2,
            {
                "cell": "object_type",
                "g_id": "sha256:" + "f" * 64,
                "partition": "development",
                "primary_f_id": "hmac-sha256:" + "f" * 64,
            },
        )
        expected_rows = [
            {
                "cell": row["cell"],
                "g_id": row["g_id"],
                "primary_f_id": row["primary_f_id"],
            }
            for row in assignments
            if row["partition"] == "holdout"
        ]
        self.assertEqual(
            bootstrap_core._cell_roster_sha256({"assignments": assignments}),
            _domain_digest(_CELL_ROSTER_DOMAIN, {"rows": expected_rows}),
        )

    def test_one_occurrence_drives_all_four_sampled_value_streams(self) -> None:
        observed: list[tuple[list[int], list[CanonicalRational]]] = []

        def metric(
            left: list[int],
            target: list[CanonicalRational],
        ) -> dict[str, Any]:
            observed.append((list(left), list(target)))
            return _defined_zero_metric(left, target)

        with patch.object(bootstrap_core, "_metric_state", side_effect=metric):
            bootstrap_core._evaluate_runs(
                _cells(),
                b"\x01" * 32,
                "sha256:" + "2" * 64,
                1,
                0,
            )
        self.assertEqual(len(observed), 3)
        scores, score_targets = observed[0]
        totals, total_targets = observed[1]
        distinct, distinct_targets = observed[2]
        self.assertEqual(totals, [value + 10_000 for value in scores])
        self.assertEqual(distinct, [value + 20_000 for value in scores])
        self.assertEqual(score_targets, total_targets)
        self.assertEqual(score_targets, distinct_targets)

    def test_sampled_position_limit_is_precharged_before_stream_creation(self) -> None:
        class SizedRows:
            def __init__(self, size: int) -> None:
                self.size = size

            def __len__(self) -> int:
                return self.size

        cells = {
            "site": SizedRows(20),
            "period": SizedRows(20),
            "medium": SizedRows(20),
            "object_type": SizedRows(19_941),
        }
        with (
            patch.object(bootstrap_core, "NMFACounterStream") as stream,
            self.assertRaises(NMFAResamplingError) as caught,
        ):
            bootstrap_core._evaluate_runs(
                cast(Any, cells),
                b"\x01" * 32,
                "sha256:" + "2" * 64,
                10_000,
                249,
            )
        self.assertIs(caught.exception.code, NMFAResamplingErrorCode.COMPUTATION_LIMIT_BLOCKED)
        stream.assert_not_called()

    def test_exact_ten_thousand_run_stream_accounting_and_tie_indices(self) -> None:
        calls = 0

        def metric(
            left: list[int],
            target: list[CanonicalRational],
        ) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return _defined_zero_metric(left, target)

        with patch.object(bootstrap_core, "_metric_state", side_effect=metric):
            bootstrap, endpoints = bootstrap_core._evaluate_runs(
                _cells(),
                b"\x03" * 32,
                "sha256:" + "4" * 64,
                10_000,
                249,
            )
        self.assertEqual(calls, 30_000)
        self.assertEqual(bootstrap["run_count"], 10_000)
        self.assertEqual(bootstrap["draws_per_run"], 80)
        self.assertEqual(bootstrap["counter"]["total_draws"], 800_000)
        self.assertEqual(
            bootstrap["counter"]["total_blocks_generated"],
            bootstrap["counter"]["total_draws"] + bootstrap["counter"]["total_rejected_blocks"],
        )
        self.assertEqual(bootstrap["discarded_runs"], 0)
        self.assertEqual(bootstrap["redrawn_runs"], 0)
        self.assertEqual(
            bootstrap["length_maximum_selections"],
            {"zero": 10_000, "l_total": 0, "l_distinct": 0},
        )
        self.assertEqual(
            bootstrap["substitutions"],
            {
                "candidate_to_negative_one": 0,
                "l_distinct_to_zero": 0,
                "l_total_to_zero": 0,
            },
        )
        self.assertEqual(endpoints["candidate_rho_lower"]["run_index"], 249)
        self.assertEqual(endpoints["paired_delta_lower"]["run_index"], 249)
        forbidden = {"rows", "assignments", "g_id", "primary_f_id"}
        self.assertFalse(forbidden & set(bootstrap))
        self.assertFalse(forbidden & set(endpoints))

    def test_cell_minimum_and_holdout_minimum_are_enforced(self) -> None:
        cells = _cells()
        assignments: list[dict[str, Any]] = []
        score_rows: list[dict[str, Any]] = []
        target_rows: list[dict[str, Any]] = []
        for axis in _AXES:
            for row in cells[axis]:
                assignments.append(
                    {
                        "cell": axis,
                        "g_id": row.g_id,
                        "partition": "holdout",
                        "primary_f_id": row.primary_f_id,
                    }
                )
                score_rows.append(
                    {
                        "g_id": row.g_id,
                        "l_distinct": row.l_distinct,
                        "l_total": row.l_total,
                        "primary_f_id": row.primary_f_id,
                        "score": row.score,
                    }
                )
                target_rows.append(
                    {
                        "canonical_value": {
                            "denominator": str(row.target.denominator),
                            "numerator": str(row.target.numerator),
                        },
                        "g_id": row.g_id,
                        "primary_f_id": row.primary_f_id,
                    }
                )
        selector: dict[str, Any] = {"assignments": assignments}
        score: dict[str, Any] = {"rows": score_rows}
        target: dict[str, Any] = {"rows": target_rows}
        by_cell = bootstrap_core._bootstrap_rows_by_cell(selector, score, target)
        self.assertEqual(
            {axis: len(rows) for axis, rows in by_cell.items()},
            {axis: 20 for axis in _AXES},
        )

        assignments[0]["partition"] = "development"
        with self.assertRaises(NMFAResamplingError) as caught:
            bootstrap_core._bootstrap_rows_by_cell(selector, score, target)
        self.assertIs(
            caught.exception.code,
            NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID,
        )

    def test_roster_inputs_require_every_and_only_holdout_row(self) -> None:
        claim = {
            "claim_family_id": "registry-id:" + "1" * 64,
            "claim_slot_id": "registry-id:" + "2" * 64,
            "experiment_instance_id": "registry-id:" + "3" * 64,
            "predecessor_chain_head_sha256": "sha256:" + "4" * 64,
        }
        selector_raw_sha256 = "sha256:" + "5" * 64
        rows = (
            ("sha256:" + "6" * 64, "hmac-sha256:" + "6" * 64),
            ("sha256:" + "7" * 64, "hmac-sha256:" + "7" * 64),
        )
        full = ValidatedNMFAGFRoster(
            canonical_bytes=b"{}\n",
            raw_sha256="sha256:" + "8" * 64,
            roster_sha256="sha256:" + "9" * 64,
            selector_assignment_raw_sha256=selector_raw_sha256,
            claim_binding=claim,
            rows=rows,
            bundle_sha256="sha256:" + "a" * 64,
        )
        metric = ValidatedNMFAMetricRoster(
            canonical_bytes=b"{}\n",
            raw_sha256="sha256:" + "b" * 64,
            metric_roster_sha256="sha256:" + "c" * 64,
            rows=(rows[0],),
            full_roster=full,
        )
        selector: dict[str, Any] = {
            "assignments": [
                {
                    "cell": "site",
                    "g_id": rows[0][0],
                    "partition": "holdout",
                    "primary_f_id": rows[0][1],
                },
                {
                    "cell": "period",
                    "g_id": rows[1][0],
                    "partition": "development",
                    "primary_f_id": rows[1][1],
                },
            ],
            "claim_binding": claim,
        }
        bindings = {
            "assignment_roster_sha256": full.roster_sha256,
            "selector_assignment_raw_sha256": selector_raw_sha256,
        }
        score: dict[str, Any] = {
            "bindings": bindings,
            "claim_binding": claim,
            "rows": [{"g_id": key[0], "primary_f_id": key[1]} for key in rows],
        }
        target: dict[str, Any] = {
            "bindings": bindings,
            "claim_binding": claim,
            "rows": [{"g_id": key[0], "primary_f_id": key[1]} for key in rows],
        }
        with (
            patch.object(
                bootstrap_core,
                "validate_nmfa_metric_roster",
                return_value=metric,
            ),
            patch.object(
                bootstrap_core,
                "_decode_selector_assignment",
                return_value=selector,
            ),
            patch.object(bootstrap_core, "_decode_score_receipt", return_value=score),
            patch.object(bootstrap_core, "_decode_target_receipt", return_value=target),
        ):
            result = bootstrap_core._selector_and_measurement_inputs(
                b"full",
                "sha256:" + "d" * 64,
                b"metric",
                "sha256:" + "e" * 64,
                b"selector",
                selector_raw_sha256,
                b"score",
                "sha256:" + "f" * 64,
                b"target",
                _ZERO_CHECKSUM,
            )
        self.assertEqual(result[-1], (rows[0],))

        cross_claim_target = {
            **target,
            "claim_binding": {
                **claim,
                "claim_slot_id": "registry-id:" + "a" * 64,
            },
        }
        with (
            patch.object(
                bootstrap_core,
                "validate_nmfa_metric_roster",
                return_value=metric,
            ),
            patch.object(
                bootstrap_core,
                "_decode_selector_assignment",
                return_value=selector,
            ),
            patch.object(bootstrap_core, "_decode_score_receipt", return_value=score),
            patch.object(
                bootstrap_core,
                "_decode_target_receipt",
                return_value=cross_claim_target,
            ),
            self.assertRaises(NMFAResamplingError) as caught,
        ):
            bootstrap_core._selector_and_measurement_inputs(
                b"full",
                "sha256:" + "d" * 64,
                b"metric",
                "sha256:" + "e" * 64,
                b"selector",
                selector_raw_sha256,
                b"score",
                "sha256:" + "f" * 64,
                b"target",
                _ZERO_CHECKSUM,
            )
        self.assertIs(caught.exception.code, NMFAResamplingErrorCode.ROSTER_MISMATCH)

        bad_metric = ValidatedNMFAMetricRoster(
            canonical_bytes=metric.canonical_bytes,
            raw_sha256=metric.raw_sha256,
            metric_roster_sha256=metric.metric_roster_sha256,
            rows=rows,
            full_roster=full,
        )
        with (
            patch.object(
                bootstrap_core,
                "validate_nmfa_metric_roster",
                return_value=bad_metric,
            ),
            patch.object(
                bootstrap_core,
                "_decode_selector_assignment",
                return_value=selector,
            ),
            patch.object(bootstrap_core, "_decode_score_receipt", return_value=score),
            patch.object(bootstrap_core, "_decode_target_receipt", return_value=target),
            self.assertRaises(NMFAResamplingError) as caught,
        ):
            bootstrap_core._selector_and_measurement_inputs(
                b"full",
                "sha256:" + "d" * 64,
                b"metric",
                "sha256:" + "e" * 64,
                b"selector",
                selector_raw_sha256,
                b"score",
                "sha256:" + "f" * 64,
                b"target",
                _ZERO_CHECKSUM,
            )
        self.assertIs(caught.exception.code, NMFAResamplingErrorCode.ROSTER_MISMATCH)

    def test_verifier_requires_byte_exact_reexecution(self) -> None:
        expected = SimpleNamespace(
            receipt_bytes=b"{}\n",
            receipt_raw_sha256="sha256:" + hashlib.sha256(b"{}\n").hexdigest(),
            receipt_sha256="sha256:" + "1" * 64,
            bundle_sha256="sha256:" + "2" * 64,
        )
        arguments = {
            "full_roster_raw": b"full",
            "expected_full_roster_raw_sha256": _ZERO_CHECKSUM,
            "metric_roster_raw": b"metric",
            "expected_metric_roster_raw_sha256": _ZERO_CHECKSUM,
            "selector_assignment_raw": b"selector",
            "expected_selector_assignment_raw_sha256": _ZERO_CHECKSUM,
            "score_receipt_raw": b"score",
            "expected_score_receipt_raw_sha256": _ZERO_CHECKSUM,
            "target_receipt_raw": b"target",
            "expected_target_receipt_raw_sha256": _ZERO_CHECKSUM,
            "frozen_protocol_chain_head_sha256": _ZERO_CHECKSUM,
        }
        with (
            patch.object(
                bootstrap_core,
                "evaluate_nmfa_paired_bootstrap",
                return_value=expected,
            ),
            patch.object(
                bootstrap_core,
                "_decode_bootstrap_receipt",
                return_value={},
            ) as decode,
            patch.object(bootstrap_core, "_require_unchanged_bundle"),
        ):
            bootstrap_core.verify_nmfa_bootstrap_receipt(
                **arguments,
                bootstrap_receipt_raw=b"{}\n",
            )
            decode.assert_called_once_with(
                b"{}\n",
                expected.receipt_raw_sha256,
                expected.bundle_sha256,
            )
            with self.assertRaises(NMFAResamplingError) as caught:
                bootstrap_core.verify_nmfa_bootstrap_receipt(
                    **arguments,
                    bootstrap_receipt_raw=b"{ }\n",
                )
        self.assertIs(
            caught.exception.code,
            NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
        )

    def test_sha256_module_is_not_replaced_by_mutable_schedule_material(self) -> None:
        hasher = bootstrap_core._schedule_hasher(
            _ZERO_CHECKSUM,
            b"\x00" * 32,
            1,
            (20, 20, 20, 20),
        )
        self.assertIsInstance(hasher, type(hashlib.sha256()))


if __name__ == "__main__":
    unittest.main()
