from __future__ import annotations

import math
import unittest

from indusbench.v3dev.contracts import V3ObservationLine, V3ObservationToken
from indusbench.v4dev.contracts import (
    V4FeatureCorpus,
    V4ObservationCorpus,
    V4ObservationDocument,
)
from indusbench.v4dev.corpus_statistics import (
    FEATURE_NAMES_BY_ABLATION,
    LOCAL_FEATURE_NAMES,
    PROFILE_FEATURE_NAMES,
    V4CorpusProfile,
    V4CorpusStatisticsError,
)


def _line(*identifiers: str | None, ordinal: int = 0) -> V3ObservationLine:
    return V3ObservationLine(
        line_ordinal=ordinal,
        reported_direction="known_source_order",
        tokens=tuple(
            V3ObservationToken(
                observation_id=identifier,
                damaged=identifier is None,
            )
            for identifier in identifiers
        ),
    )


def _document(*lines: V3ObservationLine) -> V4ObservationDocument:
    return V4ObservationDocument(lines=lines)


def _corpus(
    documents: tuple[tuple[tuple[str | None, ...], ...], ...],
) -> V4ObservationCorpus:
    return V4ObservationCorpus(
        documents=tuple(
            _document(
                *(
                    _line(*identifiers, ordinal=line_index)
                    for line_index, identifiers in enumerate(lines)
                )
            )
            for lines in documents
        )
    )


def _row(
    feature_corpus: V4FeatureCorpus,
    document_index: int,
    line_index: int,
    token_index: int,
) -> dict[str, str | float]:
    documents = feature_corpus.documents
    return dict(documents[document_index].lines[line_index].rows[token_index])


def _rename(
    corpus: V4ObservationCorpus,
    mapping: dict[str, str],
) -> V4ObservationCorpus:
    return V4ObservationCorpus(
        documents=tuple(
            V4ObservationDocument(
                lines=tuple(
                    V3ObservationLine(
                        line_ordinal=line.line_ordinal,
                        reported_direction=line.reported_direction,
                        tokens=tuple(
                            V3ObservationToken(
                                observation_id=(
                                    None
                                    if token.observation_id is None
                                    else mapping[token.observation_id]
                                ),
                                damaged=token.damaged,
                            )
                            for token in line.tokens
                        ),
                    )
                    for line in document.lines
                )
            )
            for document in corpus.documents
        )
    )


class V4CorpusStatisticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.corpus = _corpus(
            (
                (("x", "y"),),
                (("x", "x", "y"),),
                (("y", "x"),),
            )
        )

    def test_feature_surface_is_local_or_full_and_drops_template_hash(self) -> None:
        profile = V4CorpusProfile.fit(self.corpus)
        local = profile.transform_corpus(self.corpus, ablation="local")
        full = profile.transform_corpus(self.corpus, ablation="full")
        local_row = _row(local, 0, 0, 0)
        full_row = _row(full, 0, 0, 0)

        self.assertEqual(tuple(local_row), LOCAL_FEATURE_NAMES)
        self.assertEqual(tuple(full_row), FEATURE_NAMES_BY_ABLATION["full"])
        self.assertEqual(len(full_row), len(LOCAL_FEATURE_NAMES) + len(PROFILE_FEATURE_NAMES))
        self.assertNotIn("line_template", local_row)
        self.assertNotIn("template-sha256", repr(full))

    def test_lofo_exact_frequency_dispersion_context_and_shrinkage(self) -> None:
        features = V4CorpusProfile.fit(self.corpus).transform_corpus(self.corpus)
        row = _row(features, 0, 0, 0)

        count = 3
        reliability = count / (count + 4)
        diversity_reliability = (count - 1) / (count + 3)
        expected_family_entropy = (
            diversity_reliability
            * (-(2 / 3) * math.log(2 / 3) - (1 / 3) * math.log(1 / 3))
            / math.log(2)
        )

        self.assertEqual(row["type_support"], "3-4")
        self.assertAlmostEqual(
            float(row["type_frequency"]),
            math.log1p(3) / math.log1p(5),
        )
        self.assertEqual(row["family_dispersion"], 1.0)
        self.assertEqual(row["line_dispersion"], 1.0)
        self.assertAlmostEqual(float(row["family_entropy"]), expected_family_entropy)
        self.assertAlmostEqual(
            float(row["type_initial_tendency"]),
            0.4 + reliability * (1 / 3 - 0.4),
        )
        self.assertAlmostEqual(float(row["type_mean_position"]), 0.5)
        self.assertAlmostEqual(
            float(row["type_position_variance"]),
            0.8 + reliability * (2 / 3 - 0.8),
        )
        self.assertAlmostEqual(
            float(row["left_context_excess_diversity"]),
            diversity_reliability,
        )
        self.assertAlmostEqual(
            float(row["left_context_entropy"]),
            diversity_reliability,
        )
        self.assertAlmostEqual(
            float(row["type_repeat_in_line_rate"]),
            0.4 + reliability * (2 / 3 - 0.4),
        )
        self.assertEqual(row["left_neighbor_commonness"], "BOS")
        self.assertAlmostEqual(
            float(row["right_neighbor_commonness"]),
            math.log1p(2) / math.log1p(5),
        )
        self.assertAlmostEqual(float(row["type_evidence"]), reliability)
        self.assertAlmostEqual(
            float(row["type_diversity_evidence"]),
            diversity_reliability,
        )

    def test_current_document_is_wholly_removed(self) -> None:
        corpus = _corpus(
            (
                (("only-here", "only-here"),),
                (("other",),),
            )
        )
        features = V4CorpusProfile.fit(corpus).transform_corpus(corpus)
        first = _row(features, 0, 0, 0)
        second = _row(features, 0, 0, 1)

        for row in (first, second):
            self.assertEqual(row["type_support"], "UNSEEN")
            self.assertEqual(row["type_frequency"], "UNSEEN")
            self.assertEqual(row["type_evidence"], "UNSEEN")

    def test_damaged_token_profile_is_neutral(self) -> None:
        corpus = _corpus(
            (
                ((None,),),
                (("x",),),
            )
        )
        row = _row(V4CorpusProfile.fit(corpus).transform_corpus(corpus), 0, 0, 0)

        for feature_name in PROFILE_FEATURE_NAMES:
            if feature_name in {"left_neighbor_commonness", "right_neighbor_commonness"}:
                continue
            self.assertEqual(row[feature_name], "DAMAGED_NEUTRAL")
        self.assertEqual(row["left_neighbor_commonness"], "BOS")
        self.assertEqual(row["right_neighbor_commonness"], "EOS")

    def test_damaged_token_keeps_truth_free_neighbor_commonness(self) -> None:
        corpus = _corpus(
            (
                (("x", None, "y"),),
                (("x", "y"),),
                (("x", "y"),),
            )
        )
        row = _row(V4CorpusProfile.fit(corpus).transform_corpus(corpus), 0, 0, 1)
        expected = math.log1p(2) / math.log1p(4)

        self.assertAlmostEqual(float(row["left_neighbor_commonness"]), expected)
        self.assertAlmostEqual(float(row["right_neighbor_commonness"]), expected)
        self.assertEqual(row["type_frequency"], "DAMAGED_NEUTRAL")

    def test_identifier_bijection_preserves_commitment_and_every_feature(self) -> None:
        renamed = _rename(self.corpus, {"x": "renamed-7", "y": "renamed-2"})
        first_profile = V4CorpusProfile.fit(self.corpus)
        second_profile = V4CorpusProfile.fit(renamed)
        first_features = first_profile.transform_corpus(self.corpus)
        second_features = second_profile.transform_corpus(renamed)

        self.assertEqual(first_profile.corpus_commitment, second_profile.corpus_commitment)
        self.assertEqual(first_features, second_features)
        self.assertNotIn("_identity_commitment", V4CorpusProfile.__slots__)
        rendered = repr(first_profile) + repr(first_features)
        self.assertNotIn('"x"', rendered)
        self.assertNotIn('"y"', rendered)

    def test_profile_refuses_a_different_identity_assignment(self) -> None:
        renamed = _rename(self.corpus, {"x": "renamed-7", "y": "renamed-2"})
        profile = V4CorpusProfile.fit(self.corpus)

        with self.assertRaisesRegex(V4CorpusStatisticsError, "exact fitted corpus"):
            profile.transform_corpus(renamed)

    def test_single_document_lofo_is_all_unseen(self) -> None:
        corpus = _corpus(((("x",),),))
        row = _row(V4CorpusProfile.fit(corpus).transform_corpus(corpus), 0, 0, 0)

        self.assertEqual(row["type_support"], "UNSEEN")
        self.assertEqual(row["type_frequency"], "UNSEEN")

    def test_self_inclusive_mode_is_explicit_diagnostic(self) -> None:
        corpus = _corpus(((("x",),),))
        profile = V4CorpusProfile.fit(corpus)
        row = _row(
            profile.transform_corpus(corpus, profile_mode="self_inclusive"),
            0,
            0,
            0,
        )

        self.assertEqual(row["type_support"], "1")
        self.assertIsInstance(row["type_frequency"], float)
        with self.assertRaisesRegex(V4CorpusStatisticsError, "profile mode"):
            profile.transform_corpus(
                corpus,
                profile_mode="invalid",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
