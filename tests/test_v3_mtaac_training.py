from __future__ import annotations

import json
import unittest
from dataclasses import asdict, replace
from typing import Any
from unittest.mock import call, patch

import indusbench.v3dev.mtaac_training as gateway
from indusbench.mtaac import MTAAC_PINNED_ARCHIVE_SHA256, MTAACCorpus
from indusbench.mtaac_control import (
    CLEAN_REGIME,
    MILD_REGIME,
    MTAAC_CONTROL_PROTOCOL_SHA256,
    MTAAC_REAL_EVALUATION_CORPUS_SHA256,
    MTAACDegradedCorpus,
    MTAACSplitManifest,
    build_mtaac_split,
    degrade_mtaac_corpus,
)
from indusbench.v3dev.contracts import (
    MTAAC_TRAINING_GATEWAY_VERSION,
    V3_STRUCTURAL_STATES,
    MTAACTrainingBundle,
    MTAACTrainingView,
    V3ObservationLine,
    V3ObservationToken,
)
from indusbench.v3dev.mtaac_training import (
    MTAAC_V2_HOLDOUT_FAMILY_COUNT,
    MTAAC_V2_SPLIT_MANIFEST_SHA256,
    MTAAC_V2_SPLIT_SEED,
    MTAAC_V2_TEST_FRACTION,
    MTAAC_V2_TRAINING_FAMILY_COUNT,
    MTAACTrainingGatewayError,
    build_mtaac_v2_training_bundle,
)
from tests.test_mtaac_control import synthetic_corpus


class _ExplodingTokens:
    def __iter__(self) -> Any:
        raise AssertionError("holdout gold tokens must not be traversed")


def _synthetic_bundle(
    clean: MTAACTrainingView,
    mild: MTAACTrainingView,
    split: MTAACSplitManifest,
) -> MTAACTrainingBundle:
    return MTAACTrainingBundle(
        gateway_version=MTAAC_TRAINING_GATEWAY_VERSION,
        source_commit="a" * 40,
        v2_freeze_commit="b" * 40,
        source_archive_sha256="sha256:" + "1" * 64,
        selected_manifest_sha256="sha256:" + "2" * 64,
        evaluation_corpus_sha256="sha256:" + "3" * 64,
        v2_protocol_sha256="sha256:" + "4" * 64,
        split_manifest_sha256=split.manifest_sha256,
        split_seed=split.seed,
        split_test_fraction=split.test_fraction,
        training_family_count=len(clean.documents),
        excluded_holdout_family_count=sum(entry.partition == "test" for entry in split.entries),
        states=V3_STRUCTURAL_STATES,
        clean=clean,
        mild=mild,
    )


def _mapping_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested_key for nested in value.values() for nested_key in _mapping_keys(nested)
        }
    if isinstance(value, list):
        return {nested_key for nested in value for nested_key in _mapping_keys(nested)}
    return set()


class ExactGatewayTests(unittest.TestCase):
    def test_frozen_v2_split_commitment_and_counts_are_literal(self) -> None:
        self.assertEqual(MTAAC_V2_SPLIT_SEED, 0)
        self.assertEqual(MTAAC_V2_TEST_FRACTION, 0.25)
        self.assertEqual(
            MTAAC_V2_SPLIT_MANIFEST_SHA256,
            "sha256:7249c8fe1d3efc95b42cc9e0a9378550addb64f5b992f89af99dd852b83c5c30",
        )
        self.assertEqual(MTAAC_V2_TRAINING_FAMILY_COUNT, 271)
        self.assertEqual(MTAAC_V2_HOLDOUT_FAMILY_COUNT, 90)

    def test_wrong_archive_digest_stops_before_archive_parser(self) -> None:
        with (
            patch.object(gateway, "parse_mtaac_archive") as parser,
            self.assertRaisesRegex(MTAACTrainingGatewayError, "pinned SHA-256"),
        ):
            build_mtaac_v2_training_bundle(b"not-the-pinned-archive")
        parser.assert_not_called()

    def test_nonfixed_parser_result_stops_before_split(self) -> None:
        corpus = synthetic_corpus(40, context_count=6)
        with (
            patch.object(
                gateway,
                "_tagged_sha256",
                return_value=MTAAC_PINNED_ARCHIVE_SHA256,
            ),
            patch.object(gateway, "parse_mtaac_archive", return_value=corpus),
            patch.object(gateway, "build_mtaac_split") as splitter,
            self.assertRaisesRegex(MTAACTrainingGatewayError, "fixed source"),
        ):
            build_mtaac_v2_training_bundle(b"project-authored-test-container")
        splitter.assert_not_called()

    def test_public_gateway_passes_only_fixed_derivation_arguments(self) -> None:
        corpus = synthetic_corpus(40, context_count=6)
        split = build_mtaac_split(corpus)
        clean = degrade_mtaac_corpus(corpus, split, CLEAN_REGIME)
        mild = degrade_mtaac_corpus(corpus, split, MILD_REGIME)
        supplied = b"project-authored-test-container"

        with (
            patch.object(
                gateway,
                "_tagged_sha256",
                return_value=MTAAC_PINNED_ARCHIVE_SHA256,
            ) as digest,
            patch.object(gateway, "parse_mtaac_archive", return_value=corpus) as parser,
            patch.object(gateway, "_validate_exact_source") as source_validator,
            patch.object(gateway, "build_mtaac_split", return_value=split) as splitter,
            patch.object(
                gateway,
                "degrade_mtaac_corpus",
                side_effect=(clean, mild),
            ) as degrader,
            patch.object(
                gateway,
                "MTAAC_V2_SPLIT_MANIFEST_SHA256",
                split.manifest_sha256,
            ),
            patch.object(gateway, "MTAAC_V2_TRAINING_FAMILY_COUNT", 30),
            patch.object(gateway, "MTAAC_V2_HOLDOUT_FAMILY_COUNT", 10),
        ):
            bundle = build_mtaac_v2_training_bundle(supplied)

        digest.assert_called_once_with(supplied)
        parser.assert_called_once_with(
            supplied,
            expected_input_sha256=MTAAC_PINNED_ARCHIVE_SHA256,
        )
        source_validator.assert_called_once_with(corpus)
        splitter.assert_called_once_with(corpus, seed=0, test_fraction=0.25)
        degrader.assert_has_calls(
            (
                call(corpus, split, CLEAN_REGIME, seed=0),
                call(corpus, split, MILD_REGIME, seed=0),
            )
        )
        self.assertEqual(bundle.training_family_count, 30)
        self.assertEqual(bundle.excluded_holdout_family_count, 10)
        self.assertEqual(bundle.evaluation_corpus_sha256, MTAAC_REAL_EVALUATION_CORPUS_SHA256)
        self.assertEqual(bundle.v2_protocol_sha256, MTAAC_CONTROL_PROTOCOL_SHA256)
        self.assertNotIn("corpus", MTAACTrainingBundle.__dataclass_fields__)
        self.assertNotIn("split", MTAACTrainingBundle.__dataclass_fields__)
        self.assertNotIn("gold", MTAACTrainingBundle.__dataclass_fields__)

    def test_exact_split_gate_rejects_manifest_and_count_substitution(self) -> None:
        split = build_mtaac_split(synthetic_corpus(40, context_count=6))
        with self.assertRaisesRegex(
            MTAACTrainingGatewayError,
            "exact frozen V2 split",
        ):
            gateway._validate_exact_split(split)

        forged_digest = replace(
            split,
            manifest_sha256=MTAAC_V2_SPLIT_MANIFEST_SHA256,
        )
        with self.assertRaisesRegex(
            MTAACTrainingGatewayError,
            "271 train and 90 holdout",
        ):
            gateway._validate_exact_split(forged_digest)


class TrainingProjectionTests(unittest.TestCase):
    corpus: MTAACCorpus
    split: MTAACSplitManifest
    clean_degraded: MTAACDegradedCorpus
    mild_degraded: MTAACDegradedCorpus
    clean: MTAACTrainingView
    mild: MTAACTrainingView

    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = synthetic_corpus(40, context_count=6)
        cls.split = build_mtaac_split(cls.corpus)
        cls.clean_degraded = degrade_mtaac_corpus(cls.corpus, cls.split, CLEAN_REGIME)
        cls.mild_degraded = degrade_mtaac_corpus(cls.corpus, cls.split, MILD_REGIME)
        cls.clean, cls.mild = gateway._project_training_views(
            cls.corpus,
            cls.split,
            cls.clean_degraded,
            cls.mild_degraded,
            expected_training_family_count=30,
            expected_holdout_family_count=10,
        )

    def test_only_training_families_and_representative_replicas_cross_boundary(
        self,
    ) -> None:
        train_keys = {
            entry.document_key for entry in self.split.entries if entry.partition == "train"
        }
        holdout_keys = {
            entry.document_key for entry in self.split.entries if entry.partition == "test"
        }
        for view in (self.clean, self.mild):
            output_keys = {document.document_key for document in view.documents}
            self.assertEqual(output_keys, train_keys)
            self.assertTrue(output_keys.isdisjoint(holdout_keys))
            self.assertEqual(len(view.documents), 30)
            self.assertTrue(all(document.replica_index == 0 for document in view.documents))
            self.assertEqual(
                len({document.cluster_identifier for document in view.documents}),
                30,
            )

        source_train_counts: dict[str, int] = {}
        for observation in self.mild_degraded.observations:
            if observation.partition == "train":
                source_train_counts[observation.document_key] = (
                    source_train_counts.get(observation.document_key, 0) + 1
                )
        self.assertTrue(any(count == 2 for count in source_train_counts.values()))
        self.assertEqual(
            {document.document_key for document in self.clean.documents},
            {document.document_key for document in self.mild.documents},
        )

    def test_empty_gold_is_context_and_all_five_states_are_jointly_present(self) -> None:
        gold_by_token = {
            token.token_key: token.classes
            for document in self.corpus.gold_documents
            if any(
                entry.document_key == document.document_key and entry.partition == "train"
                for entry in self.split.entries
            )
            for token in document.tokens
        }
        projected = {
            token.token_key: token.state
            for document in self.clean.documents
            for line in document.lines
            for token in line.tokens
        }
        self.assertEqual(
            set(projected.values()),
            set(V3_STRUCTURAL_STATES),
        )
        self.assertTrue(any(not classes for classes in gold_by_token.values()))
        self.assertEqual(
            {
                token_key: ("context_only" if not classes else classes[0])
                for token_key, classes in gold_by_token.items()
            },
            projected,
        )

    def test_damaged_retained_tokens_are_included_with_null_observation(self) -> None:
        source_damaged = {
            token.token_key
            for observation in self.mild_degraded.observations
            if observation.partition == "train" and observation.replica_index == 0
            for line in observation.lines
            for token in line.tokens
            if token.damaged
        }
        projected_damaged = {
            token.token_key
            for document in self.mild.documents
            for line in document.lines
            for token in line.tokens
            if token.damaged
        }
        self.assertTrue(source_damaged)
        self.assertEqual(projected_damaged, source_damaged)
        self.assertTrue(
            all(
                token.observed_form_id is None
                for document in self.mild.documents
                for line in document.lines
                for token in line.tokens
                if token.damaged
            )
        )

    def test_tokens_are_canonicalized_to_the_reported_model_order(self) -> None:
        projected_lines = {
            (document.document_key, line.line_ordinal): line
            for document in self.mild.documents
            for line in document.lines
        }
        seen_directions: set[str] = set()
        for observation in self.mild_degraded.observations:
            if observation.partition != "train" or observation.replica_index != 0:
                continue
            for source_line in observation.lines:
                output_line = projected_lines[(observation.document_key, source_line.line_ordinal)]
                seen_directions.add(source_line.reported_direction)
                if source_line.reported_direction == "known_source_order":
                    ordered = sorted(
                        source_line.tokens,
                        key=lambda token: (token.source_order, token.token_key),
                    )
                else:
                    ordered = sorted(
                        source_line.tokens,
                        key=lambda token: (token.visual_index, token.token_key),
                    )
                self.assertEqual(
                    tuple(token.token_key for token in output_line.tokens),
                    tuple(token.token_key for token in ordered),
                )
                self.assertEqual(
                    output_line.reported_direction,
                    source_line.reported_direction,
                )
        self.assertEqual(
            seen_directions,
            {"known_source_order", "unknown_visual_order"},
        )

    def test_truth_free_observation_contract_removes_keys_and_states(self) -> None:
        training_line = self.mild.documents[0].lines[0]
        observation = training_line.to_observation()
        self.assertIsInstance(observation, V3ObservationLine)
        self.assertEqual(
            set(V3ObservationLine.__dataclass_fields__),
            {"line_ordinal", "reported_direction", "tokens"},
        )
        self.assertEqual(
            set(V3ObservationToken.__dataclass_fields__),
            {"observation_id", "damaged"},
        )
        self.assertEqual(
            tuple(token.observation_id for token in observation.tokens),
            tuple(token.observed_form_id for token in training_line.tokens),
        )
        self.assertEqual(
            tuple(token.damaged for token in observation.tokens),
            tuple(token.damaged for token in training_line.tokens),
        )
        self.assertTrue(all(not hasattr(token, "state") for token in observation.tokens))
        self.assertTrue(all(not hasattr(token, "token_key") for token in observation.tokens))

    def test_holdout_gold_tokens_are_not_traversed_after_membership(self) -> None:
        holdout_keys = {
            entry.document_key for entry in self.split.entries if entry.partition == "test"
        }
        guarded = replace(
            self.corpus,
            gold_documents=tuple(
                replace(
                    document,
                    tokens=_ExplodingTokens(),  # type: ignore[arg-type]
                )
                if document.document_key in holdout_keys
                else document
                for document in self.corpus.gold_documents
            ),
        )
        clean, mild = gateway._project_training_views(
            guarded,
            self.split,
            self.clean_degraded,
            self.mild_degraded,
            expected_training_family_count=30,
            expected_holdout_family_count=10,
        )
        self.assertEqual(clean, self.clean)
        self.assertEqual(mild, self.mild)

    def test_overlapping_training_truth_fails_closed(self) -> None:
        train_keys = {
            entry.document_key for entry in self.split.entries if entry.partition == "train"
        }
        changed = False
        gold_documents = []
        for document in self.corpus.gold_documents:
            if not changed and document.document_key in train_keys:
                first = replace(
                    document.tokens[0],
                    classes=("quantity", "unit"),
                )
                document = replace(document, tokens=(first, *document.tokens[1:]))
                changed = True
            gold_documents.append(document)
        self.assertTrue(changed)
        forged = replace(self.corpus, gold_documents=tuple(gold_documents))
        with self.assertRaisesRegex(
            MTAACTrainingGatewayError,
            "overlapping classes",
        ):
            gateway._project_training_views(
                forged,
                self.split,
                self.clean_degraded,
                self.mild_degraded,
                expected_training_family_count=30,
                expected_holdout_family_count=10,
            )

    def test_degradation_must_be_bound_to_the_same_split_seed_and_regime(self) -> None:
        tampered = replace(self.mild_degraded, seed=self.mild_degraded.seed + 1)
        with self.assertRaisesRegex(
            MTAACTrainingGatewayError,
            "bound to the split and regime",
        ):
            gateway._project_training_views(
                self.corpus,
                self.split,
                self.clean_degraded,
                tampered,
                expected_training_family_count=30,
                expected_holdout_family_count=10,
            )

    def test_bundle_contains_no_raw_source_or_degradation_mechanics(self) -> None:
        bundle = _synthetic_bundle(self.clean, self.mild, self.split)
        encoded = asdict(bundle)
        serialized = json.dumps(encoded, sort_keys=True)
        for forbidden_value in (
            "P800",
            "SYNTHETIC_",
            "synthetic_",
            "fixture/morph",
            ".conll",
        ):
            self.assertNotIn(forbidden_value, serialized)
        forbidden_fields = {
            "corpus",
            "corpus_path",
            "form",
            "gold_documents",
            "input_path",
            "p_identifier",
            "partition",
            "pseudo_variant_applied",
            "segm",
            "source_order",
            "visual_index",
            "visual_reversed",
            "xpostag",
        }
        self.assertTrue(forbidden_fields.isdisjoint(_mapping_keys(encoded)))


if __name__ == "__main__":
    unittest.main()
