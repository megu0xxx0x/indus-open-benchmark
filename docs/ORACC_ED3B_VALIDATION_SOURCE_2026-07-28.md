# ORACC Early Dynastic IIIb prospective-validation source audit

**Audit date:** 2026-07-28

**Decision status:** reserve the eligible ORACC ePSD2 `admin/ed3b` source,
after a fixed audit-example exclusion, as a rights-cleared,
feature-safety-exposed prospective validation source before V3 model fitting

**Evaluation status:** source, rights, ontology, and observation-safety audit
only; no model was trained, selected, tuned, or evaluated, and no prediction
or performance result was calculated

**Indus status:** no sign value, function, language, meaning, translation,
decipherment, prize-eligibility, or transfer-readiness claim

## Executive decision

The official ORACC ePSD2 Early Dynastic IIIb administrative corpus is admitted
as the project's next known-script prospective validation source. All eligible
documents other than the fixed audit-example exclusion described below are
reserved together. They must not be used for V3 candidate fitting, development
metrics, hyperparameter or threshold selection, post-freeze feature design,
error analysis, prompt construction, or model choice.

This is a source reservation, not a result or binding confirmation. The source
is public and its annotations are publicly obtainable. Archive-wide and
joined-source class counts were inspected, and gold-conditioned GDL-key
frequencies were computed to remove direct annotation leakage from the
observation projection. The project therefore does not claim that ED3b is
feature-unseen, distribution-blind, secret, or independently blind. A binding
confirmation requires a different, previously uninspected corpus selected
through an independently controlled or predeclared-random mechanism after the
complete model and evaluator freeze. A later ED3b split cannot regain
untouched status.

V2 remains immutable. Its parser, evaluator, protocols, preserved error, and
published aggregate result must not be rewritten, relabelled, or retrospectively
reinterpreted as V3. The ORACC adapter, projection, five-state model, statistics,
protocol, and future report belong to a separate V3 implementation.

## Exact official source

- [ORACC ePSD2 Early Dynastic IIIb corpus](https://oracc.museum.upenn.edu/epsd2/admin/ed3b/corpus)
- [Official ORACC JSON ZIP](https://oracc.museum.upenn.edu/json/epsd2-admin-ed3b.zip)
- [Official ORACC JSON/open-data specification](https://oracc.museum.upenn.edu/doc/opendata/json/)
- [Official ORACC open-data documentation](https://oracc.museum.upenn.edu/doc/opendata/)
- [CC0 1.0 Universal legal instrument](https://creativecommons.org/publicdomain/zero/1.0/)

The admitted archive bytes are fixed as follows:

```text
source:       ORACC ePSD2 admin/ed3b JSON ZIP
archive URL:  https://oracc.museum.upenn.edu/json/epsd2-admin-ed3b.zip
bytes:        34,534,747
members:      3,491
catalogue:    3,477 documents
sha256:       a108205140d101ca8d4d38c106fad7b61abac427eb51da12f912c8eada70c557
```

The ZIP embeds an ORACC license declaration stating that the data are released
under CC0 and embeds the CC0 URI above. The same declaration is present in the
corpus and glossary JSON metadata. This supports legal reuse of the admitted
JSON bytes, but it does not prove annotation correctness, completeness,
philological consensus, or fitness for an Indus claim.

The download endpoint is not a content-addressed historical release. Every
future use must therefore require the exact byte length and SHA-256 above
before parsing. A later response from the same URL is a different source
unless it is byte-identical.

No archive member or extracted raw record is added to Git. Raw and derived
corpus material remains outside the tracked tree under the project's data
boundary. Only public source citations, protocols, validators, commitments,
aggregate allowlisted reports, and synthetic fixtures may be tracked.

## Eligibility contract

A catalogue document is eligible only when all three conditions hold exactly:

1. catalogue `period` is `Early Dynastic IIIb`;
2. catalogue `genre` is `Administrative`; and
3. the document is present in `metadata.formats.lem`.

The intersection is closed: a document failing any condition is excluded, and
missing, malformed, duplicated, or contradictory metadata fails closed. No
case folding, substring matching, spelling repair, fallback to transliteration
alone, or manual inclusion is permitted.

Sixteen documents whose individual contents were displayed as examples during
the source audit are excluded before validation. This exclusion is fixed
before V3 model development and cannot be revised after a development or
validation result. No raw source identifier from that set is placed in tracked
code or this public audit. The verifier contains the 16 domain-separated
identifier hashes and binds their ordered set through a second commitment.
This is data minimization, not secrecy: because the source identifier space
and archive are public and finite, the hashed identifiers can be enumerated
by a motivated party.

All documents passing the intersection after that fixed exclusion are reserved
together as the validation source. There is no train/development split within
ED3b, no search over split seeds, and no post-support replacement.

### Eligibility receipt

The source-only verifier reproduced the following commitments without fitting
or executing a model and without calculating a prediction metric:

```text
eligible documents after fixed audit exclusion:
  3,338
retained lemma tokens:
  226,618
scorable five-state truth tokens:
  226,610
annotation-unknown tokens / documents:
  8 / 7
audit-exclusion set sha256:
  sha256:5c28be3dbfb6111d83a297ac31b2ba640ce4fa521adf89edec3abf195b9ae0cf
selected-member manifest sha256:
  sha256:6eda68ba7e96d7d56b2edb49b72f7727ecd3cef0519abbe8269d04b6bce034b6
effective-corpus sha256:
  sha256:c6a745a6a397dc5492bfcdad60d91787bece7267653f3c897944459880af5342
observation-contract sha256:
  sha256:a801e1980c2c973fb4a2ca806e2f6ec56a96fb45477d2fb63d295f6ce69eb123
four-class support commitment sha256:
  sha256:ad6a3615420b3d37cb3d3a622393beddb02cfd6828f069879cea382644793eb8
```

The support gate was fixed to require at least 200 retained tokens and 100
supporting documents for each target class. Every class passed.
Selected-source per-class counts are not listed in the receipt; the commitment
binds them in
`quantity`, `unit`, `person_name`, `settlement_name` order. A support failure
would have returned `insufficient_source_support` without authorizing source,
seed, scope, or exclusion changes.

The [frozen source protocol](../benchmark/oracc-ed3b-validation-source-v1.json)
defines the length framing, hash domains, canonical JSON encoding, ordering,
projection, and fail-closed rules. The checked-in aggregate receipt is generated
only after that implementation and protocol have a public source-freeze commit.

This does not make ED3b distribution-blind. The
[global source audit](V3_GLOBAL_KNOWN_SCRIPT_SOURCE_AUDIT_2026-07-28.md)
published archive-wide projected counts and SumTablets-joined counts. The
observation-safety audit also used class-conditioned GDL-key rates to identify
numeric-parser and determinative leakage. Those are now fixed provenance
facts, not erasable exposure. No prediction or performance metric was run.

An exact source-identifier comparison against all 371 selected members of the
pinned MTAAC archive found zero overlap. This is stronger than comparing only
the future MTAAC development partition, but it proves neither lexical novelty
nor absence of formulaic sequence overlap. The later validation protocol
must bind complete-document and line-level observation-overlap diagnostics
before scoring and cannot change the reserved ORACC source in response.

## Mechanical five-state projection

V3's primary task is a joint five-state sequence problem over all readable
retained tokens:

1. `context_only`
2. `quantity`
3. `unit`
4. `person_name`
5. `settlement_name`

The evaluator-side gold projection is mechanical:

| State | Exact rule |
|---|---|
| `quantity` | lemma feature `f.pos` is exactly lowercase `n`; `NU` and `QN` are not admitted by this rule |
| `unit` | lemma feature `f.gw` is exactly `unit` and lemma feature `f.pos` is exactly `N` |
| `person_name` | lemma feature `f.pos` is exactly `PN` |
| `settlement_name` | lemma feature `f.pos` is exactly `SN` |
| `context_only` | none of the four target rules matches |
| `annotation_unknown` | `f.pos` is missing, or an `N` token lacks the required `f.gw`; prediction is still required but truth is unscored |

The official ORACC documentation used to interpret these fields is:

- [ORACC metrology and numerical-annotation guidance](https://oracc.museum.upenn.edu/doc/help/editinginatf/metrology/index.html)
- [ORACC proper-noun annotation guidance](https://oracc.museum.upenn.edu/doc/help/languages/propernouns/index.html)

A token matching more than one target rule is an integrity failure. Malformed
fields fail closed. The exact eight missing-POS tokens do not silently become
negative examples: they receive fixed `annotation_unknown` evaluator truth.

Gold fields determine evaluator-side truth only. They are not model features.
The primary five-state task predicts every readable retained token, including
`context_only`; it does not use test truth to preselect which tokens receive a
prediction. This removes the four-class target-eligibility oracle from the
primary V3 task. A four-target-only score may be retained solely as a labelled
comparability diagnostic and cannot replace the five-state primary result.

### Cross-source estimands

The shared names are operational estimands, not proof that two tag strings are
identical:

| State | MTAAC development rule | ED3b validation rule | Comparability |
|---|---|---|---|
| `quantity` | `XPOSTAG` begins `NU`; the official example labels written `3(u)` as `NU` | lowercase lemma `f.pos == "n"` | aligned conventional written numeric marker/count-unit construct under different annotation conventions; ORACC number-word `NU` remains outside this narrow estimand |
| `unit` | `SEGM` contains `[unit]` | `f.pos == "N"` and `f.gw == "unit"` | aligned metrological-unit normalization/guide-word construct |
| `person_name` | first tag component `PN` | `f.pos == "PN"` | same ORACC-derived named-entity semantics |
| `settlement_name` | first tag component `SN` | `f.pos == "SN"` | same ORACC-derived named-entity semantics |
| `context_only` | all other scorable tokens in the future V3 pool | all other scorable tokens | broad complement whose composition and prevalence remain source-specific |

The MTAAC evidence is the fixed
[annotation workflow and example](https://github.com/cdli-gh/cdli-gh.github.io/blob/3e1fab1270c25737aa5ddf5dbc8cb31be23a1c7f/_pages/guide_overview.md)
and [tagset](https://github.com/cdli-gh/cdli-gh.github.io/blob/3e1fab1270c25737aa5ddf5dbc8cb31be23a1c7f/_pages/guide_tagsets.md).
This crosswalk does not claim every semantic quantity expression is covered.

## Annotation-stripping observation projection

Passing raw `f.gdl` to a model is invalid. In the pinned source, numeric
wrapper keys and determinative annotations are highly class-conditioned, and
ORACC's formal GDL specification permits linguistic-service attributes not
present in raw ATF. The frozen projection therefore accepts only `f.gdl`,
collapses ordinary `q/c/s/v` or audited numeric/modified `form` payloads into
one source-specific SHA-256 atom namespace, flattens approved wrappers in
source order, maps ellipsis/newline to one `GAP`, and maps missing/damaged to
one damage mask. Numeric-parser, determinative, delimiter, ID, modifier,
span-ID, and related key identities are not emitted. Unknown keys, ambiguous
shapes, multiple atom keys, or zero observations fail closed.

This output is an annotation-key-stripped transliteration-layer
representation. Hashing preserves equality and order but does not erase the
scholarly reading behind a public transliteration or provide confidentiality.
It is not a native glyph, photograph, palaeographic observation, or visual
recognition control. Source-specific atom domains also forbid direct
MTAAC-to-ED3b lexical identity in the primary transfer; only frozen
source-neutral structure, position, repetition, damage, and template features
may transfer. The official [GDL specification](https://oracc.museum.upenn.edu/ns/gdl/1.0/)
defines the annotation layer and documents processor-added grapheme roles.

## Pre-validation development boundary

Before the ORACC source can be evaluated, the project must:

1. publish the exact source and eligibility receipt commitments;
2. develop candidates only on separately declared development sources and
   synthetic fixtures;
3. freeze the V3 observation contract, degradation, complete candidate
   selection, model parameters, class balancing, sequence decoding,
   uncertainty diagnostics, null model, metrics, support gates, thresholds,
   output allowlist, implementation bytes, and code commit;
4. publish that complete protocol before the first ORACC score; and
5. run the fixed validation entry point without source, seed, candidate,
   threshold, or run-count overrides and without replacing an existing output.

The validation protocol must separate capabilities. An observation-only,
network-free prediction process receives one canonical document at a time
with frozen model, vocabulary, priors, transitions, normalizers, and
dependencies. It may not fit ED3b IDF, clusters, calibration, embeddings, or
other batch statistics. It commits no-replace predictions before a separate
evaluator loads `f.pos` or `f.gw`. The primary candidate may use only declared
MTAAC-development observations and project-authored synthetic fixtures; no
pretrained language model, external embedding/tokenizer, ORACC lexicon,
sign-role table, web/API lookup, or validation record in a prompt is allowed.

Before scoring, gold-independent ED3b document and line fingerprints must
freeze internal exact/near-duplicate families and MTAAC–ED3b overlaps.
Decision metrics use family-balanced weights and cluster uncertainty, with a
novel-template stratum. A permutation null must move whole
family/document-label tensors only within fixed compatible layout strata.
Distinct source identifiers are not treated as proof of independent evidence.

The intended primary candidate is a class-balanced five-state linear-chain
model that decodes complete retained lines. Forced prediction is
decision-bearing. Predictive uncertainty and abstention are diagnostic only
unless a future pre-validation protocol expressly freezes a non-gameable
coverage and error contract.

The sequence permutation null must move a complete document's label tensor
only within an identical line-layout signature and must preserve replicas,
partition membership, line boundaries, readable-row layout, and global label
mass. Insufficient movable family mass fails closed rather than authorizing a
weaker post-result null.

## Reporting and nonclaims

A future public report may contain source/protocol/code commitments,
non-identifying runtime metadata, aggregate parser and exclusion counts,
aggregate support, confusion matrices, metrics, null summaries, uncertainty
summaries, integrity booleans, and a terminal status.

It must not contain raw token values, source-document identifiers, per-document
predictions, archive-member paths, local paths, host or account information,
network addresses, storage topology, credentials, or private operational
timestamps.

Even a successful known-script validation would validate only the frozen
method under the declared, feature-safety-exposed ORACC scope. It would not be
binding confirmation and would not by itself identify an Indus language,
reading, sign value, translation, or decipherment, or establish prize
eligibility.
