"""Repeated matched-null evaluation for transparent structural baselines."""

from __future__ import annotations

import random
import statistics
from collections.abc import Iterable, Mapping
from typing import Any

from indusbench.baseline import (
    AddOneNGramBaseline,
    SignSequence,
    extract_sequences,
    score_missing_signs,
)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot summarize an empty null distribution")
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "standard_deviation": statistics.stdev(values) if len(values) > 1 else 0.0,
        "minimum": min(values),
        "p025": _percentile(values, 0.025),
        "median": statistics.median(values),
        "p975": _percentile(values, 0.975),
        "maximum": max(values),
    }


def _shuffle_sequences(sequences: list[SignSequence], seed: int) -> list[SignSequence]:
    signs = [sign for sequence in sequences for sign in sequence]
    random.Random(seed).shuffle(signs)
    offset = 0
    shuffled: list[SignSequence] = []
    for sequence in sequences:
        length = len(sequence)
        shuffled.append(tuple(signs[offset : offset + length]))
        offset += length
    return shuffled


def evaluate_shuffle_null(
    train: Iterable[Mapping[str, Any]],
    test: Iterable[Mapping[str, Any]],
    *,
    order: int = 2,
    runs: int = 100,
    seed: int = 0,
) -> dict[str, Any]:
    """Compare an observed n-gram with repeated sign-order shuffles.

    Each null run preserves the train and test partitions, their sequence
    lengths, and each partition's unigram counts. Independent seeds shuffle
    train and test assignments, destroying within-sequence order.
    """

    if runs < 1:
        raise ValueError("runs must be at least 1")
    train_rows = list(train)
    test_rows = list(test)
    train_sequences = extract_sequences(train_rows)
    test_sequences = extract_sequences(test_rows)

    observed_model = AddOneNGramBaseline(order=order).fit(train_sequences)
    observed_heldout = observed_model.score_heldout(test_sequences)
    observed_missing = score_missing_signs(observed_model, test_sequences)

    null_perplexities: list[float] = []
    null_accuracies: list[float] = []
    null_reciprocal_ranks: list[float] = []
    run_values: list[dict[str, float | int]] = []
    for offset in range(runs):
        run_seed = seed + offset
        shuffled_train = _shuffle_sequences(train_sequences, run_seed)
        shuffled_test = _shuffle_sequences(test_sequences, run_seed + 10_000_019)
        model = AddOneNGramBaseline(order=order).fit(shuffled_train)
        heldout = model.score_heldout(shuffled_test)
        missing = score_missing_signs(model, shuffled_test)
        null_perplexities.append(heldout.perplexity)
        null_accuracies.append(missing.accuracy)
        null_reciprocal_ranks.append(missing.mean_reciprocal_rank)
        run_values.append(
            {
                "seed": run_seed,
                "perplexity": heldout.perplexity,
                "masked_accuracy": missing.accuracy,
                "mean_reciprocal_rank": missing.mean_reciprocal_rank,
            }
        )

    accuracy_p = (1 + sum(value >= observed_missing.accuracy for value in null_accuracies)) / (
        runs + 1
    )
    perplexity_p = (
        1 + sum(value <= observed_heldout.perplexity for value in null_perplexities)
    ) / (runs + 1)
    reciprocal_rank_p = (
        1 + sum(value >= observed_missing.mean_reciprocal_rank for value in null_reciprocal_ranks)
    ) / (runs + 1)

    return {
        "model": "add_one_ngram",
        "order": order,
        "runs": runs,
        "seed_start": seed,
        "null_control": {
            "kind": "independent_partition_global_sign_shuffle",
            "preserves": ["partition_membership", "sequence_lengths", "unigram_counts"],
            "destroys": ["within_sequence_order"],
        },
        "observed": {
            "perplexity": observed_heldout.perplexity,
            "masked_accuracy": observed_missing.accuracy,
            "mean_reciprocal_rank": observed_missing.mean_reciprocal_rank,
            "evaluated_tokens": observed_missing.evaluated_tokens,
            "skipped_oov_tokens": observed_missing.skipped_oov_tokens,
        },
        "null_summary": {
            "perplexity": _summary(null_perplexities),
            "masked_accuracy": _summary(null_accuracies),
            "mean_reciprocal_rank": _summary(null_reciprocal_ranks),
        },
        "empirical_p_values": {
            "perplexity_lower_or_equal": perplexity_p,
            "masked_accuracy_greater_or_equal": accuracy_p,
            "mean_reciprocal_rank_greater_or_equal": reciprocal_rank_p,
        },
        "run_values": run_values,
        "scientific_scope": (
            "tests local sequential regularity against one matched null family; "
            "does not identify language, phonetic values, semantics, or translation"
        ),
    }
