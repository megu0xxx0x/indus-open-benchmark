# Blind Benchmark Protocol

## Objective

The benchmark measures whether a representation or decipherment hypothesis predicts material it
could not have memorized. Fluency, visual resemblance, and post-hoc coverage are not metrics.

**Current implementation status:** split manifest v0.2 produces only fully
public `train` and `development` partitions. The local definition lock binds
their exact inputs but remains unanchored and dependency-lock-only. A separate
local submission commitment can now bind a complete candidate tree and its
target definition, but “complete” is relative to the caller-selected root and
does not prove runtime closure. It has no trusted time, external custody, or
access-history evidence. No hidden test, submission custody receipt, isolated
run lock, blind result, or final evaluation currently exists. The requirements
below describe the future protocol boundary, not a completed claim.

## Unit of isolation

The primary split unit is a physical/template family, not a transcription row. All of the following
must remain in one partition:

- the same physical artifact and each side;
- seal and impression pairs;
- casts, replicas, re-photography, and publication duplicates;
- objects attributed to one mold, template, or near-copy family;
- identical image hashes;
- exact normalized sign sequences.

Unknown relationships are reported as uncertainty. They are not assumed independent.

## Required evaluations

1. Family-grouped public train/development split plus a separately custodial
   hidden test definition.
2. Leave-one-site-out evaluation.
3. Leave-one-period-out evaluation.
4. Leave-one-object-type-out evaluation.
5. Future or institution-held material evaluated only after exact benchmark
   definition `B` and submission commitment `S` are externally receipted.

The candidate must not be run on hidden inputs, and the
hypothesis/submission team must not receive hidden material or hidden-derived
feedback, before that receipt. Raw hidden material normally remains
inaccessible to hypothesis authors throughout a real prize or decipherment
evaluation.

## Matched controls

Compare each claim against:

- length- and frequency-preserving shuffled sequences;
- inventory-matched accounting, registry, or ownership-mark systems;
- short natural-language seal legends;
- unrelated candidate-language lexica;
- permuted semantic assignments;
- simple unigram and n-gram models.

Evidence of non-random structure is not, by itself, evidence of language.
Randomized controls use multiple preregistered seeds and report their full distribution plus an
add-one empirical p-value; one favorable shuffle is not a benchmark.

## Known-script stress test

Before applying a method to Indus material:

1. hide the known values of Linear B, Ugaritic, or Cypriot signs;
2. truncate the corpus to the Indus sequence-length and sample-size distribution;
3. remove word boundaries and external anchors in controlled stages;
4. introduce damage, allographs, duplicate families, and transcription uncertainty;
5. measure how much of the known answer the method recovers.

A system that cannot recover known writing under matched information constraints has not earned a
semantic interpretation of the Indus data.

## Metrics

Structural models report:

- held-out negative log likelihood and perplexity;
- masked-sign top-k accuracy and proper scoring rules;
- calibration by token uncertainty;
- minimum-description-length or explicit complexity penalty;
- performance by site, period, object type, material, and inscription length;
- sensitivity to alternative sign inventories and reading directions.

Hypotheses additionally report:

- coverage before exceptions;
- count and cost of null, one-to-many, and ad-hoc mappings;
- phonological and morphological consistency;
- pre-registered archaeological predictions;
- negative-control and unrelated-language results.

## Recognition threshold

A serious decipherment claim must:

- place its sign inventory, direction, mapping, grammar, exceptions, weights,
  and executable submission in the frozen payload/tree;
- have an independent custodian authenticate and retain a receipt for exact
  `B` and `S` values before the candidate is run on hidden inputs and before
  the hypothesis/submission team receives hidden material or hidden-derived
  feedback;
- generalize across sites, periods, and media;
- outperform linguistic and non-linguistic controls;
- predict unseen signs, distributions, quantities, names, or archaeological context;
- publish data lineage, code, environment, seeds, exclusions, and failures;
- be independently reproduced;
- ultimately connect to an external anchor such as a bilingual, confirmed name, known quantity, or
  sufficiently long and constrained text.

A local Git timestamp, author-supplied hypothesis timestamp, or self-consistent
`S` is not external freeze evidence.
