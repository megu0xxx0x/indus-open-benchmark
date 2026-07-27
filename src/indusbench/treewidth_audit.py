"""Deterministic graph and null-model utilities for sign-sequence audits."""

from __future__ import annotations

import random
import statistics
from bisect import bisect_right
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from heapq import heapify, heappop, heappush
from itertools import count, pairwise
from typing import Any, Literal, TypeAlias

from indusbench.baseline import CorpusInput, SignSequence, extract_sequences

AdjacencyGraph: TypeAlias = dict[str, set[str]]
NullGenerator: TypeAlias = Callable[[CorpusInput, int], list[SignSequence]]
SequenceUnit: TypeAlias = Literal["canonical_line", "artifact_flat"]


def build_undirected_adjacency_graph(data: CorpusInput) -> AdjacencyGraph:
    """Build a simple undirected graph from consecutive signs.

    Every observed sign is retained as a vertex, including isolated signs.
    Consecutive equal signs do not create self-loops.
    """

    sequences = extract_sequences(data)
    graph: AdjacencyGraph = {}
    for sequence in sequences:
        for sign in sequence:
            graph.setdefault(sign, set())
        for left, right in pairwise(sequence):
            if left == right:
                continue
            graph[left].add(right)
            graph[right].add(left)
    return graph


def min_degree_treewidth_upper_bound(adjacency: Mapping[str, Iterable[str]]) -> int:
    """Return the induced width of deterministic minimum-degree elimination.

    The supplied graph is normalized to a simple undirected graph. At each
    step, the minimum-degree vertex is eliminated and its remaining neighbors
    are completed to a clique. A stable heap initialized in lexical vertex
    order makes degree ties deterministic.
    """

    supplied_neighbors = {node: set(neighbors) for node, neighbors in adjacency.items()}
    nodes = set(supplied_neighbors)
    for neighbors in supplied_neighbors.values():
        nodes.update(neighbors)

    graph: AdjacencyGraph = {node: set() for node in sorted(nodes)}
    for node, neighbors in supplied_neighbors.items():
        for neighbor in neighbors:
            if neighbor == node:
                continue
            graph[node].add(neighbor)
            graph[neighbor].add(node)

    insertion_counter = count()
    degree_queue = [(len(graph[node]), next(insertion_counter), node) for node in graph]
    heapify(degree_queue)
    update_nodes: set[str] = set()
    upper_bound = 0
    while graph:
        for node in sorted(update_nodes):
            heappush(
                degree_queue,
                (len(graph[node]), next(insertion_counter), node),
            )

        eliminated: str | None = None
        while degree_queue:
            minimum_degree, _, candidate = heappop(degree_queue)
            if candidate not in graph or len(graph[candidate]) != minimum_degree:
                continue
            if minimum_degree == len(graph) - 1:
                return max(upper_bound, minimum_degree)
            eliminated = candidate
            break
        if eliminated is None:
            raise RuntimeError("minimum-degree queue was exhausted before the graph")

        neighbors = set(graph[eliminated])
        upper_bound = max(upper_bound, len(neighbors))

        for left in neighbors:
            graph[left].update(neighbors - {left})
        for neighbor in neighbors:
            graph[neighbor].discard(eliminated)
        del graph[eliminated]
        update_nodes = neighbors

    return upper_bound


def _artifact_flat_sequence(
    record: Mapping[str, object],
    record_index: int,
) -> tuple[SignSequence | None, str]:
    artifact_id = record.get("artifact_id")
    record_label = artifact_id if isinstance(artifact_id, str) else f"record[{record_index}]"
    sides = record.get("sides")
    if not isinstance(sides, Sequence) or isinstance(sides, (str, bytes)):
        raise ValueError(f"{record_label}: artifact_flat requires a sides sequence")

    extensions = record.get("extensions")
    upstream_indices: Mapping[object, object] | None = None
    if isinstance(extensions, Mapping):
        candidate = extensions.get("mayig:upstream_grapheme_indices")
        if isinstance(candidate, Mapping):
            upstream_indices = candidate

    flat_signs: list[str] = []
    order_basis = (
        "mayig_upstream_grapheme_index"
        if upstream_indices is not None
        else "stored_side_line_token_order"
    )
    for side_index, side in enumerate(sides):
        if not isinstance(side, Mapping):
            raise TypeError(f"{record_label}.sides[{side_index}]: must be an object")
        lines = side.get("lines")
        if not isinstance(lines, Sequence) or isinstance(lines, (str, bytes)):
            raise TypeError(f"{record_label}.sides[{side_index}].lines: must be a sequence")

        stored_tokens: list[tuple[int, Mapping[object, object]]] = []
        storage_index = 0
        for line_index, line in enumerate(lines):
            if not isinstance(line, Mapping):
                raise TypeError(
                    f"{record_label}.sides[{side_index}].lines[{line_index}]: must be an object"
                )
            tokens = line.get("tokens")
            if not isinstance(tokens, Sequence) or isinstance(tokens, (str, bytes)):
                raise TypeError(
                    f"{record_label}.sides[{side_index}].lines[{line_index}].tokens: "
                    "must be a sequence"
                )
            for token in tokens:
                if not isinstance(token, Mapping):
                    raise TypeError(
                        f"{record_label}.sides[{side_index}].lines[{line_index}]"
                        f".tokens[{storage_index}]: must be an object"
                    )
                stored_tokens.append((storage_index, token))
                storage_index += 1

        if upstream_indices is not None:

            def upstream_order(item: tuple[int, Mapping[object, object]]) -> tuple[int, int]:
                stored_index, token = item
                token_id = token.get("token_id")
                upstream_index = upstream_indices.get(token_id)
                if not isinstance(upstream_index, int):
                    raise ValueError(
                        f"{record_label}: artifact_flat requires an integer upstream index "
                        f"for token {token_id!r}"
                    )
                return upstream_index, stored_index

            stored_tokens.sort(key=upstream_order)

        for _, token in stored_tokens:
            token_id = token.get("token_id")
            sign_id = token.get("sign_id")
            if not isinstance(sign_id, str) or not sign_id:
                raise ValueError(
                    f"{record_label}: artifact_flat cannot bridge unresolved token {token_id!r}"
                )
            flat_signs.append(sign_id)

    return (tuple(flat_signs) if flat_signs else None), order_basis


def extract_treewidth_sequences(
    data: CorpusInput,
    *,
    sequence_unit: SequenceUnit = "canonical_line",
    min_length: int = 1,
) -> tuple[list[SignSequence], dict[str, Any]]:
    """Extract sequences and return an explicit, JSON-compatible boundary policy."""

    if sequence_unit not in {"canonical_line", "artifact_flat"}:
        raise ValueError("sequence_unit must be 'canonical_line' or 'artifact_flat'")
    if min_length < 1:
        raise ValueError("min_length must be at least 1")

    materialized: list[object] = [data] if isinstance(data, Mapping) else list(data)

    order_basis_counts: Counter[str] = Counter()
    if materialized and all(isinstance(item, Mapping) for item in materialized):
        if sequence_unit == "canonical_line":
            sequences = extract_sequences(materialized)
            order_basis_counts["canonical_reading_order_per_line"] = len(sequences)
        else:
            sequences = []
            for record_index, item in enumerate(materialized):
                if not isinstance(item, Mapping):
                    continue
                sequence, order_basis = _artifact_flat_sequence(item, record_index)
                if sequence is not None:
                    sequences.append(sequence)
                    order_basis_counts[order_basis] += 1
    else:
        sequences = extract_sequences(materialized)
        order_basis_counts["explicit_input_sequences"] = len(sequences)

    before_sequence_count = len(sequences)
    before_token_count = sum(len(sequence) for sequence in sequences)
    filtered_sequences = [sequence for sequence in sequences if len(sequence) >= min_length]
    after_token_count = sum(len(sequence) for sequence in filtered_sequences)
    policy = {
        "sequence_unit": sequence_unit,
        "order_basis_counts": dict(sorted(order_basis_counts.items())),
        "min_length": min_length,
        "short_sequence_rule": "exclude_if_observed_sign_count_is_less_than_min_length",
        "before_filter": {
            "sequence_count": before_sequence_count,
            "token_count": before_token_count,
        },
        "excluded": {
            "sequence_count": before_sequence_count - len(filtered_sequences),
            "token_count": before_token_count - after_token_count,
        },
        "after_filter": {
            "sequence_count": len(filtered_sequences),
            "token_count": after_token_count,
        },
    }
    return filtered_sequences, policy


def global_frequency_preserving_shuffle(data: CorpusInput, seed: int) -> list[SignSequence]:
    """Shuffle all signs globally while preserving sequence lengths and total counts."""

    sequences = extract_sequences(data)
    signs = [sign for sequence in sequences for sign in sequence]
    random.Random(seed).shuffle(signs)

    shuffled: list[SignSequence] = []
    offset = 0
    for sequence in sequences:
        end = offset + len(sequence)
        shuffled.append(tuple(signs[offset:end]))
        offset = end
    return shuffled


def within_sequence_order_shuffle(data: CorpusInput, seed: int) -> list[SignSequence]:
    """Shuffle order independently inside each extracted inscription sequence."""

    sequences = extract_sequences(data)
    generator = random.Random(seed)
    shuffled: list[SignSequence] = []
    for sequence in sequences:
        signs = list(sequence)
        generator.shuffle(signs)
        shuffled.append(tuple(signs))
    return shuffled


def empirical_frequency_iid(data: CorpusInput, seed: int) -> list[SignSequence]:
    """Draw IID signs from observed integer frequencies at the observed lengths."""

    sequences = extract_sequences(data)
    counts = Counter(sign for sequence in sequences for sign in sequence)
    if not counts:
        return []

    signs = sorted(counts)
    cumulative_counts: list[int] = []
    token_count = 0
    for sign in signs:
        token_count += counts[sign]
        cumulative_counts.append(token_count)

    generator = random.Random(seed)

    def draw_sign() -> str:
        index = bisect_right(cumulative_counts, generator.randrange(token_count))
        return signs[index]

    return [tuple(draw_sign() for _ in sequence) for sequence in sequences]


def _edge_count(graph: Mapping[str, set[str]]) -> int:
    return sum(len(neighbors) for neighbors in graph.values()) // 2


def _null_summary(values: list[int], observed: int) -> dict[str, Any]:
    run_count = len(values)
    return {
        "observed": observed,
        "min": min(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "max": max(values),
        "empirical_rate": {
            "null_less_than_or_equal_observed": (
                sum(value <= observed for value in values) / run_count
            ),
            "null_equal_observed": sum(value == observed for value in values) / run_count,
            "null_greater_than_or_equal_observed": (
                sum(value >= observed for value in values) / run_count
            ),
        },
    }


def evaluate_treewidth_nulls(
    data: CorpusInput,
    *,
    runs: int = 100,
    seed: int = 0,
    sequence_unit: SequenceUnit = "canonical_line",
    min_length: int = 1,
) -> dict[str, Any]:
    """Evaluate the observed graph against three deterministic null families."""

    if runs < 1:
        raise ValueError("runs must be at least 1")

    sequences, sequence_policy = extract_treewidth_sequences(
        data,
        sequence_unit=sequence_unit,
        min_length=min_length,
    )
    if not sequences:
        raise ValueError("data must contain at least one sign sequence after min_length filtering")

    observed_graph = build_undirected_adjacency_graph(sequences)
    observed_width = min_degree_treewidth_upper_bound(observed_graph)
    null_specs: tuple[
        tuple[str, NullGenerator, list[str], list[str]],
        ...,
    ] = (
        (
            "global_frequency_preserving_shuffle",
            global_frequency_preserving_shuffle,
            ["sequence_lengths", "global_sign_counts"],
            ["within_sequence_order", "sign_sequence_membership"],
        ),
        (
            "within_sequence_order_shuffle",
            within_sequence_order_shuffle,
            ["sequence_lengths", "per_sequence_sign_counts"],
            ["within_sequence_order"],
        ),
        (
            "empirical_frequency_iid",
            empirical_frequency_iid,
            ["sequence_lengths", "expected_global_sign_frequencies"],
            ["exact_global_sign_counts", "within_sequence_order", "sign_sequence_membership"],
        ),
    )

    null_models: dict[str, Any] = {}
    for name, generator, preserves, destroys in null_specs:
        widths: list[int] = []
        run_values: list[dict[str, int]] = []
        for offset in range(runs):
            run_seed = seed + offset
            null_sequences = generator(sequences, run_seed)
            null_graph = build_undirected_adjacency_graph(null_sequences)
            null_width = min_degree_treewidth_upper_bound(null_graph)
            widths.append(null_width)
            run_values.append(
                {
                    "seed": run_seed,
                    "treewidth_upper_bound": null_width,
                    "node_count": len(null_graph),
                    "edge_count": _edge_count(null_graph),
                }
            )
        null_models[name] = {
            "preserves": preserves,
            "destroys": destroys,
            **_null_summary(widths, observed_width),
            "run_values": run_values,
        }

    return {
        "analysis": "treewidth_null_audit",
        "metric": {
            "name": "minimum_degree_elimination_treewidth_upper_bound",
            "graph_kind": "simple_undirected_consecutive_sign_adjacency",
            "self_loops": "excluded",
            "tie_break": "stable_heap_with_lexical_sign_initialization_and_updates",
        },
        "runs": runs,
        "seed_start": seed,
        "seed_schedule": "seed_start + zero_based_run_index",
        "sequence_policy": sequence_policy,
        "sequence_count": len(sequences),
        "token_count": sum(len(sequence) for sequence in sequences),
        "observed": {
            "treewidth_upper_bound": observed_width,
            "node_count": len(observed_graph),
            "edge_count": _edge_count(observed_graph),
        },
        "null_models": null_models,
    }
