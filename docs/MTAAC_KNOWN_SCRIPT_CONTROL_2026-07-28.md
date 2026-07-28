# MTAAC known-script control source audit

**Audit date:** 2026-07-28

**Decision status:** source admitted for the first real known-script method
control; V1 is preserved as an aborted first invocation, and the corrected V2
was frozen, executed once, and returned `NO_GO`

**Corpus language and script:** Ur III Sumerian in ATF transliteration with
MTAAC morphological annotation

**Indus status:** no reading, language, translation, or decipherment claim

**Result status:** V1 emitted only a fail-closed error and no aggregate result;
V2 returned `NO_GO` because mild `settlement_name` recall missed its frozen
threshold; no independent preregistration claim

**Frozen V2 protocol SHA-256:**
`sha256:25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892`

## Executive decision

The MTAAC Gold Corpus is suitable for the project's first rights-cleared,
real-data stress test of its **method**, under the fail-closed adapter and
[corrected V2 pre-result protocol](../benchmark/mtaac-known-script-control-v2.json).
The corpus is not an Indus parallel text, a linguistic bridge, an
archaeological-context dataset, or evidence that any MTAAC label applies to an
Indus inscription.

V1 was frozen publicly at commit
`57db0949f6542429d2f05b1bf935ee586bdf3699` with protocol SHA-256
`sha256:25fbea943a662144700dfca418927758ad3319817bc42191c4c8e6e45fc518b3`.
Its first fixed-source invocation reached the scoring routine and then
fail-closed during the first permutation-integrity check. The exact
[path-free error output](../benchmark/results/mtaac-known-script-control-v1-attempt-1-error.json)
states that scientific metrics were not emitted. The V1 execution order had
already calculated observed and baseline metrics in memory, so this audit does
not claim that no metric was calculated. No metric value was emitted,
inspected, or used to choose the correction.

The failure was a numerical implementation defect, not evidence of a changed
label vector: repeated binary-float addition differed by more than the fixed
tolerance even though the declared family mass was algebraically identical.
V2 conservatively supersedes V1. It validates the exact `1/(R*D)` invariant
with rational arithmetic, requires complete vector/replica preservation,
materializes and validates both decision-bearing permutation schedules before
any metric calculation, and uses `math.fsum` bucket reductions so an exact
duplicate layout cannot change a model, majority baseline, or confusion
matrix through addition order. These numerical changes can affect a
decision-bearing floating-point tie and are therefore disclosed as a V2
implementation change. Source, split, degradation, model features and
smoothing, permutation assignment and seeds, support gates, thresholds, and
scientific nonclaims are unchanged.

After the V2 code freeze and protocol bytes were publicly visible, V2 was run
once with no override. The [aggregate result](MTAAC_KNOWN_SCRIPT_CONTROL_V2_RESULT_2026-07-28.md)
is `NO_GO`: every clean gate and all but one mild gate passed, but mild
`settlement_name` recall was 0.193553 against the frozen minimum 0.35. The V2
method therefore cannot be transferred unchanged to Indus data.

The source is fixed at:

```text
repository: https://github.com/cdli-gh/mtaac_gold_corpus
commit:     66e0643efd230401210e27db353ebb6d7228b1bb
archive:    https://github.com/cdli-gh/mtaac_gold_corpus/archive/66e0643efd230401210e27db353ebb6d7228b1bb.tar.gz
archive sha256:
  sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091
scope:      morph/to_dict/*.conll
selected-member manifest sha256:
  sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e
evaluation-equivalence corpus sha256:
  sha256:e7d6f8c9a8c090bb33ef4ba3703c1b36fe0519086efa75ff70d1ba53a8bf9312
```

The [pinned corpus tree](https://github.com/cdli-gh/mtaac_gold_corpus/tree/66e0643efd230401210e27db353ebb6d7228b1bb)
and its [README](https://github.com/cdli-gh/mtaac_gold_corpus/blob/66e0643efd230401210e27db353ebb6d7228b1bb/README.md)
identify the resource as the MTAAC annotation gold corpus and describe the
Ur III portion as manually annotated. Its
[CC0-1.0 legal code](https://github.com/cdli-gh/mtaac_gold_corpus/blob/66e0643efd230401210e27db353ebb6d7228b1bb/LICENSE)
and README place the repository content in the public domain to the extent
possible under law. The README nevertheless requests academic citation of the
[contributors](https://github.com/cdli-gh/mtaac_gold_corpus/blob/66e0643efd230401210e27db353ebb6d7228b1bb/CONTRIBUTORS.txt)
and associated paper; the project should honor that request.

No corpus file is added by this audit. A CC0 source may be legally reusable,
but this project's raw-data boundary still keeps any future source checkout
outside the tracked tree.

The official archive bytes were re-fetched from the URL above. Their SHA-256,
the adapter-derived selected-member manifest, and the evaluator-consumed
corpus fingerprint matched all three fixed values.
Running the source-admission adapter over those bytes reproduced the
stage counts below. This was parser/source verification only: it did not train
a model, calculate an evaluation metric, or issue a decision.

## Why this source and no broader directory

Only `morph/to_dict/*.conll` is in the proposed first control:

- `morph/to_annotate` is not treated as gold annotation;
- `morph/external` contains annotations automatically derived from ETCSRI,
  rather than the manually annotated Ur III pool, and the pinned README itself
  records unresolved tagset-consistency work for that directory; and
- no tablet image or native cuneiform-glyph layer exists in the pinned
  repository tree.

The official MTAAC annotation documentation says that the project converts
ATF transcriptions into a seven-column CDLI-CoNLL-like table and manually fills
`SEGM` and `XPOSTAG`. It defines the columns as
`ID, FORM, SEGM, XPOSTAG, HEAD, DEPREL, MISC`. The source versions used for
this audit are pinned at official documentation commit
[`3e1fab1270c25737aa5ddf5dbc8cb31be23a1c7f`](https://github.com/cdli-gh/cdli-gh.github.io/tree/3e1fab1270c25737aa5ddf5dbc8cb31be23a1c7f):

- [annotation workflow, fields, and worked example](https://github.com/cdli-gh/cdli-gh.github.io/blob/3e1fab1270c25737aa5ddf5dbc8cb31be23a1c7f/_pages/guide_overview.md);
- [MTAAC tagsets and named-entity definitions](https://github.com/cdli-gh/cdli-gh.github.io/blob/3e1fab1270c25737aa5ddf5dbc8cb31be23a1c7f/_pages/guide_tagsets.md);
- [gold-corpus morphology workflow](https://github.com/cdli-gh/cdli-gh.github.io/blob/3e1fab1270c25737aa5ddf5dbc8cb31be23a1c7f/_pages/research_morph_ann.md); and
- [official corpus-selection description](https://github.com/cdli-gh/cdli-gh.github.io/blob/3e1fab1270c25737aa5ddf5dbc8cb31be23a1c7f/_pages/research_select_corpus.md).

The rendered documentation remains useful for reading, but the commit-specific
source links above are the reproducibility references.

The official guide calls this a CoNLL-like format, not a claim of complete
CoNLL-U compliance. It also contains unfinished sections and placeholder tool
references. The adapter must therefore validate the observed seven-column
contract directly and must not infer absent syntax or silently apply a generic
CoNLL-U repair.

## Reproduced structural audit

The pinned `morph/to_dict` tree contains 371 `.conll` files. This differs from
the README's dated statement of 372 manually annotated texts and is why the
README count must not be used as an executable contract.

The first-pass parser used the following deliberately narrow rules:

1. decode each file as UTF-8;
2. ignore an empty line or a line whose first character is `#`;
3. require every other line to contain exactly seven tab-separated fields;
4. require at least one token row; and
5. reject the **whole document** when any row fails.

Six documents fail that seven-column contract:

| Public document | Reproduced defect |
|---|---|
| `P101470.conll` | one six-column token row |
| `P101694.conll` | 317 four-column token rows |
| `P101904.conll` | one six-column token row |
| `P102295.conll` | a whitespace-prefixed would-be comment becomes a one-column row |
| `P106082.conll` | five nine-column token rows |
| `P131202.conll` | three nine-column token rows |

Rejecting those six documents yields a **seven-column diagnostic subset of 365
documents and 15,196 token rows**. Whole-document rejection is required:
padding, truncating, or keeping only the conforming rows would silently invent
the intended schema and alter within-document context.

The 365-document result is not yet the strict adapter result. A second
invariant finds four documents in which one token `ID` names two different
rows:

| Public document | Duplicated token ID |
|---|---|
| `P101173.conll` | `r.11.1` |
| `P102310.conll` | `r.1.1` |
| `P458899.conll` | `o.3.1` and `o.3.2` |
| `P480067.conll` | `r.1.1` |

The adapter must not guess a renumbering. Quarantining those four complete
documents leaves the proposed **strict v0 subset of 361 documents and 15,038
token rows**. Thus:

- 371 documents enter the selected-member stage;
- 365/15,196 is the reproducible seven-column diagnostic set;
- 361/15,038 is the current strict unique-ID admission candidate; and
- ten documents are quarantined in total—six for a non-seven-column row and
  four for a duplicated token position;
- neither count establishes philological correctness.

All 365 seven-column documents have one logical `#new_text` first tab field
matching the filename stem; some headers contain trailing empty tab fields.
Complete-document ordered `FORM` sequences are unique across the 361-document
candidate at this pin. Individual word forms and line sequences are frequently
repeated, so complete-document, line, and word-level overlap must be reported
separately.

### Field completeness

Across the 365-document diagnostic subset:

- all 15,196 `HEAD` values are `_`;
- all 15,196 `DEPREL` values are `_`;
- all 15,196 `MISC` values are `_`;
- 460 `XPOSTAG` values are `_`; and
- seven `SEGM` values are exactly `_`.

The four duplicate-ID documents do not contain those missing `XPOSTAG` or
exactly-missing `SEGM` rows, so the last two counts remain unchanged in the
361-document candidate.

This is a morphological/lexical control, not a syntactic-role or discourse-role
gold standard.

## Mechanical four-class gold projection

The initial control has exactly four classes. The mapping is fixed from
official annotation semantics, not inferred from English translations:

| Control class | Mechanical gold rule | 365-doc tokens | 361-doc tokens |
|---|---|---:|---:|
| `quantity` | first dot-delimited `XPOSTAG` component is `NU` | 3,179 | 3,145 |
| `unit` | `SEGM` contains the literal gloss `[unit]` | 1,815 | 1,794 |
| `person_name` | first `XPOSTAG` component is `PN` | 1,492 | 1,479 |
| `settlement_name` | first `XPOSTAG` component is `SN` | 330 | 325 |

The official tagset defines `NU` as number, `PN` as personal name, and `SN` as
settlement name. Its worked example represents a metrological unit as a noun
whose `SEGM` contains `[unit]`; there is no separate unit POS tag. The four
rules have zero token overlap at the pinned commit. A future overlap must fail
validation rather than be resolved by undocumented precedence. Every other
token is `abstain` for this v0 control, even if another useful upstream tag
exists.

`SEGM` and `XPOSTAG` are gold-only fields. A model that receives either field
as input would be given the answer, especially the literal `[unit]` marker.
Raw `FORM` is also not a model-facing field. The adapter uses its exact UTF-8
bytes only to derive a domain-separated opaque identifier for one complete
word token.

### Raw family keys are not settled lemma identities

For audit only, a raw family key was reproduced as
`casefold(SEGM before the first "[")`. The result is descriptive:

| Class | 365-doc raw keys | 361-doc raw keys | Placeholder observations |
|---|---:|---:|---|
| `quantity` | 58 | 58 | `_(_)`: 36 tokens |
| `unit` | 50 | 49 | `_`: one token |
| `person_name` | 703 | 701 | empty root: four tokens; `_`: 57 tokens |
| `settlement_name` | 72 | 72 | `_`: four tokens |

These are raw string buckets, not independently verified people, places,
metrological systems, or philological lemma families. For example, excluding
the damaged quantity key produces 57 remaining quantity strings, while
excluding only the four empty personal-name roots produces 702 remaining
personal-name buckets; neither number is a count of verified lemma identities.

The frozen protocol fixes the placeholder policy. After casefold, a
diagnostic stem exactly equal to the empty string, `_`, `_(_)`, `x`, `n`,
`...`, or `…` is omitted **only** from evaluator-side seen/unseen raw-stem
diagnostics. It is not a source-readability filter.

Every strictly admitted token matched by exactly one of the four mechanical
rules remains an eligible target, including a token with one of those
placeholder stems. At this pin all **6,743** strict projected targets are
eligible: 3,145 quantity, 1,794 unit, 1,479 person-name, and 325
settlement-name targets. Placeholder status does not remove a target from
the eligible pool, split-side training or scoring when otherwise readable,
support, or the applicable pre-degradation coverage denominator. No
philological repair is performed.

This source has no separate lemma column. Connecting documents through either
shared raw `SEGM` stems or shared exact word `FORM` values joins nearly the
entire target-bearing pool into one component. A simultaneous document-safe
and word/stem-disjoint four-class holdout is therefore unavailable at this
pin. The first control must use source document as its split family, make
novel complete-line sequences its primary test stratum, and report seen/unseen
word-form and raw-stem strata separately. It must set
`lemma_field_available=false` and must not call that split lemma-safe.

## Labels that are unavailable

### `person_name` is not `issuer`

The official guide says `MISC` may contain a semantic role such as `seller`.
It also reserves `HEAD` and `DEPREL` for syntactic relations. All three fields
are empty in the admitted pool. Therefore:

- `PN` supports only `person_name`;
- no gold `issuer`, owner, seller, recipient, or seal-holder role is available;
  and
- a positional rule around `kiszib` or another lexical item would be a
  hypothesis, not an upstream label.

The adapter must never rename `person_name` to `issuer`.

### Commodity is heuristic-only

The official tagset has no gold `commodity` class. The worked example places a
noun such as barley after a quantity and unit, but ordinary nouns also encode
people's roles, animals, materials, actions, and many other concepts.

A future `quantity → unit → noun` or lemma-gloss rule may generate a
`measured_item_candidate` for an explicitly separate exploratory analysis. It
must:

- remain outside the four-class gold score;
- carry the exact heuristic and abstention reason;
- never be called a verified commodity, translation, or Indus meaning; and
- be evaluated manually or against a separately sourced gold ontology before
  promotion.

## What this control can and cannot test

It can test whether the project's evaluation machinery behaves sensibly on a
real, already understood written language with genuine annotation
irregularity, class imbalance, damaged forms, repeated lexemes, and document
structure.

It cannot by itself test:

- image ingestion, sign segmentation, glyph classification, or allography;
- archaeological find context, material, object type, site, or stratum;
- recovery from genuinely undeciphered signs;
- upstream philological correctness or inter-annotator agreement;
- identification of an issuer or commodity;
- transfer of Sumerian grammar, vocabulary, numerals, determinatives, or
  writing conventions to Indus inscriptions; or
- an Indus reading, language assignment, translation, decipherment, prize
  eligibility, or prize result.

`FORM` is an expert ATF transliteration, not a native-glyph observation. The
adapter treats one complete source row as one word token and computes
`mtaac-word-form-sha256-v1:<digest>` from a domain separator plus the exact
UTF-8 `FORM` bytes. The model receives only that opaque whole-word category,
anonymous relative line structure, position/line-length buckets, neighboring
opaque categories, and reported direction. It receives no raw `FORM`, sign
segmentation, P identifier, or raw token ID.

The only model-visible word identity is the opaque whole-word identifier.
Evaluator-side family and alignment identities are separate and are never
prediction features or report values. The document key is a domain-separated
hash of the validated P identifier; the token key is a domain-separated hash
of that document key and zero-based source-row order. They do not depend on
`FORM`, `SEGM`, `XPOSTAG`, `HEAD`, `DEPREL`, or `MISC`. Regression tests change
gold and unused annotation values while holding source identity/order fixed
and require identical model keys, split, degradation events, metrics, and
permutation-null values.

This deterministic identifier is categorical coding, not secrecy, blindness,
or protection against enumeration from the public corpus. Exact source word
forms also contain strong script-specific cues, including numerical notation
and determinatives. The frozen protocol therefore defines evaluator-side
digit and determinative masks **before** opaque hashing as diagnostics. A high
score could still reflect those transliteration conventions rather than
general semantic inference.

The corpus provides within-document sequence and position, but no audited
archaeological-context join in this source contract. Any later CDLI metadata
join needs its own source pin, rights review, identifier contract, and missing
data audit.

The evaluation-equivalence fingerprint is an additional anti-laundering gate.
It commits the admitted source families, anonymous line/order structure, exact
`FORM`, projected class, and only the diagnostic-stem information actually
consumed by V1 and the unchanged V2 scoring semantics. It intentionally
ignores line-ending choice, trailing blank
lines, raw token-ID spelling that preserves the same anonymous grouping/order,
unused annotation columns, and unused gloss detail. Therefore those
score-preserving edits cannot disguise the fixed real evaluation corpus as a
synthetic fixture. The synthetic evaluator accepts only raw in-memory file
mappings and parses them itself; it does not accept a caller-built corpus
object whose provenance fields could have been replaced.

## Frozen fail-closed gates

The [V2 machine-readable protocol](../benchmark/mtaac-known-script-control-v2.json)
and its implementation were frozen before the corrected real invocation.
They enforce
the following gates:

1. **Source lock:** require the exact 40-character corpus commit, archive
   SHA-256, selected-member manifest SHA-256, and evaluation-equivalence
   fingerprint recorded above; reject a moving branch, unlisted directory,
   equivalent real corpus routed through the synthetic entry, or any mismatch
   before splitting or scoring.
2. **Parser gate:** require UTF-8, exactly seven tab-separated fields, a
   matching document identifier, non-empty documents, and unique token IDs.
   At the current pin this admits 361 documents; a different count is a hard
   failure requiring a new dated audit.
3. **Projection gate:** implement only the four mechanical rules above,
   require zero overlap, and make every other row abstain.
4. **Gold and raw-field isolation:** derive anonymous structure and an opaque
   whole-word ID evaluator-side. Expose no raw `FORM`, `SEGM`, `XPOSTAG`,
   source document ID, raw token ID, or raw-stem value as a model feature,
   prompt, retrieval key, tuning value, or prediction-time field.
5. **Placeholder gate:** keep every strictly admitted mechanically projected
   target eligible. Omit the fixed placeholder set only from optional
   seen/unseen raw-stem diagnostics; never remove it from the primary target
   set, support, scoring, or coverage.
6. **Leakage gate:** split by source document and cluster any duplicate
   complete-document `FORM` sequence before assignment. Use novel
   complete-line sequences as the primary test stratum. Report, but do not
   misrepresent as disjoint, repeated word `FORM` and raw `SEGM`-stem overlap.
   If a stricter connected-family split collapses the evaluation pool, report
   that insufficiency instead of weakening the rule after scoring.
7. **Baseline and null gate:** freeze majority, position-only, train-lexicon,
   and complete-document-vector permutation references before the first real
   score. Compare document-family-weighted macro-F1, per-class metrics,
   coverage, and an add-one empirical p-value under fixed seeds.
8. **Degradation gate:** deterministically test clean, mild, and harsh
   cumulative regimes using opaque-word pseudo-surface variants, synthetic
   damage, nested contiguous windows, direction uncertainty, and
   duplicate-weighting stress. Separate digit/determinative masks are
   diagnostic only. These artificial variants are not natural cuneiform
   allographs. Never create train and test variants of the same source
   document.
9. **Acceptance gate:** freeze protocol bytes, implementation constants,
   thresholds, seeds, and a caller-declared public code commit before the first
   real score. Require all four classes in the evaluation support and
   improvement over the strongest declared reference while maintaining frozen
   coverage. A later failure blocks reuse of that method on Indus data; a
   later success would pass only this instrument check.
10. **Publication gate:** publish code, schema, synthetic fixtures, aggregate
    results, source citations, and exact protocol decisions. Do not vendor the
    raw corpus, tablet images, or an unreviewed derived label set in this
    repository.

## Required order: freeze, then real score

The order is normative:

1. finish and review the adapter, evaluator, deterministic degradation,
   references, reporting allowlist, and synthetic tests;
2. reproduce the exact archive, selected-manifest, parser, quarantine, strict
   target, and implementation/protocol-digest gates without calculating a
   model score or changing the frozen split design;
3. freeze the exact protocol bytes, thresholds, seeds, implementation
   constants, and a public pre-result code commit;
4. only after that freeze, calculate split support and run the first
   real-source scoring execution; and
5. report the frozen commitments and aggregate result without choosing another
   seed, lowering a threshold, changing a hash domain, or silently replacing
   the protocol after seeing the score.

V1 completed steps 1–3, then its first step-4 invocation aborted before a
report was created. Its error output is preserved rather than overwritten.
Because the implementation calculated observed and baseline metrics before
the failing invariant, the correction is a new V2 protocol rather than a
silent V1 patch. No metric value, null distribution, decision reference,
p-value, `GO`, or `NO_GO` was emitted or inspected from V1.

For V2, steps 1–3 were completed in public freeze commit
`37157f1411a55ffd91b7327afaca8fc1080fa708`. All clean and mild permutation
assignments were validated before any metric calculation. Step 4 was then
executed exactly once against the fixed archive and exact V2 protocol bytes;
the aggregate JSON SHA-256 is
`sha256:6bc4ed610862d109b596bdd934f36fd19b99e3cbfcced42882546d0c852a7afe`.
The frozen result is `NO_GO`. No second seed, lower threshold, alternative
split, or replacement protocol was tried. Any later protocol or
implementation change requires another version, explicit freeze, and
separate reporting.

The report records non-identifying Python, operating-system,
architecture, libc, and binary-float metadata. Exact JSON byte identity is
claimed only under the same reported numeric runtime; cross-runtime
last-bit identity is not claimed. The public freeze gives project-local
ordering evidence only. It does not establish independent preregistration,
trusted time, custody, blindness, or independent replication.

## Minimal source reproduction

The source identity and inventory can be checked without a moving branch:

```bash
curl --fail --location --proto '=https' \
  'https://github.com/cdli-gh/mtaac_gold_corpus/archive/66e0643efd230401210e27db353ebb6d7228b1bb.tar.gz' \
  --output mtaac_gold_corpus-66e0643.tar.gz
printf '%s  %s\n' \
  '2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091' \
  'mtaac_gold_corpus-66e0643.tar.gz' |
  shasum -a 256 --check -

git clone --filter=blob:none \
  https://github.com/cdli-gh/mtaac_gold_corpus.git mtaac_gold_corpus
git -C mtaac_gold_corpus checkout --detach \
  66e0643efd230401210e27db353ebb6d7228b1bb
test "$(git -C mtaac_gold_corpus rev-parse HEAD)" = \
  "66e0643efd230401210e27db353ebb6d7228b1bb"
git -C mtaac_gold_corpus ls-tree -r --name-only HEAD morph/to_dict |
  awk '/[.]conll$/'
```

The final command must enumerate 371 files. Before splitting or scoring, the
adapter must recompute the selected-member manifest as
`sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e`.
Applying the seven-column whole-document rule must produce 365
documents/15,196 rows. Applying unique within-document token IDs must then
produce 361 documents/15,038 rows and ten quarantined documents. The strict
four-class counts must be 3,145/1,794/1,479/325 in the fixed class order.
The evaluator-consumed corpus fingerprint must be
`sha256:e7d6f8c9a8c090bb33ef4ba3703c1b36fe0519086efa75ff70d1ba53a8bf9312`.

These counts are source-integrity checks. They are not accuracy measurements,
independent philological replication, or evidence about the Indus script.
