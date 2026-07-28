# MTAAC V4 world research synthesis

**Research cutoff:** 2026-07-29

**Status:** public method note; primary publications and official project repositories only

**Scope:** source-neutral structural-role induction across scripts

**Non-claim:** this document does not identify a language, sound, word, translation, or decipherment

## Decision

The most defensible V4 step is one fixed, low-capacity linear-chain CRF over
truth-free distributional and local structural features. It tests whether five
mechanically projected MTAAC roles can be recovered under the exact five
outer-fold assignments already used by V3. Those folds are reused development
data, not new held-out evidence.

The feature set below is a synthesis of several studies. No cited paper has
validated the complete set as a universal cross-script decoder. Here,
*source-neutral* means that the model does not receive a sign catalogue ID,
transliteration, gloss, proposed language, or archaeological interpretation.
It does not mean that the representation is already proven domain-invariant.

## Frozen V4 profile

The primary profile is named
`target_batch_partition_regime_local_document_leave_one_family_out`, shortened
below to target-batch LOFO.

Within each cross-validation side and each clean or mild regime independently,
V4 aggregates truth-free opaque-form equality. Before transforming a token,
it subtracts the token's current family's entire contribution. Consequently:

- training and validation profiles never share statistics;
- clean and mild profiles never share statistics;
- the held-out side may use its complete unlabeled target batch, making the
  protocol explicitly transductive;
- every family is leave-one-family-out within its own side and regime; and
- opaque IDs exist only transiently for equality aggregation and are absent
  from feature rows, the model, caches, and reports.

The profile uses fixed log-normalized continuous features plus one fixed
support bucket. Continuous values remain numeric floats in `[0, 1]`; they must
not be decimal-stringified and one-hot encoded. The profile learns no
quantiles, secondary bins, thresholds, vocabulary, scaler, or embedding.

### Corpus-level type features

- support bucket:
  `UNSEEN`, `1`, `2`, `3-4`, `5-8`, `9-16`, or `17+`;
- occurrence, family-dispersion, and line-dispersion values:
  `log1p(count) / log1p(N)`, `log1p(families) / log1p(D)`, and
  `log1p(lines) / log1p(L)` for the applicable partition totals;
- support-aware family entropy;
- initial rate, final rate, normalized-position mean, and
  normalized-position variance, shrunk toward the applicable global prior
  with evidence weight `r = m / (m + 4)`;
- left and right context excess diversity and normalized context entropy with
  `r_div = (m - 1) / (m + 3)`, using zero when `m <= 1`;
- repetition and same-neighbor rates;
- leave-one-family-out left and right neighbor commonness; and
- explicit `r` and `r_div` evidence features.

Here `m` is the applicable leave-one-family-out evidence mass for the
corresponding estimate.

### Retained local features

V4 retains the low-cardinality V3 features:

- token-position and line-length buckets;
- reported direction, damage, and observation-presence state;
- equality with the previous and next token;
- within-line frequency; and
- whether an equal observation appeared before or will appear later.

The high-cardinality V3 `line_template` feature is removed.

### Fixed conjunctions

- local-initial flag × type-initial tendency;
- local-final flag × type-final tendency;
- `r × (1 - abs(local_normalized_position - type_mean_position))`; and
- local-neighbor-equality × type-repeat-rate.

These are the complete primary feature families. PageRank, betweenness, raw
graph identities, visual embeddings, proposed allographs, site, object type,
motif, commodity, owner, reading, gloss, and language-specific POS are not
primary model inputs.

Alternative direction and sign-equivalence hypotheses are outside this frozen
V4. A separate protocol would be required to test them; they must not be
silently promoted to observations or gold labels.

## Frozen model

V4 has exactly one candidate: a project-local, pure-Python first-order
linear-chain CRF. There is no model grid, inner candidate selection,
one-standard-error choice, structured perceptron, neural encoder, pretrained
model, or dependency fallback.

- L2 regularization coefficient: `rho = 0.01`.
- Post-hoc class logit adjustment: `gamma = 0.5`.
- Class prior:
  `pi = (family_weighted_class_mass + 0.5) / (total_mass + 2.5)`.
- Weighted CRF negative log-likelihood gives each line weight
  `1 / (that family's total clean-plus-mild token count)`.
- Initialization: all-zero parameter vector.
- Optimizer: deterministic L-BFGS with history `10` and at most `100`
  iterations.
- Line search: Armijo `c1 = 1e-4`, initial step `1`, multiplication by `0.5`,
  at most `31` trials, and minimum step `2^-30`.
- Curvature pair admission:
  `s·y > 1e-12 * ||s|| * ||y||`.
- Convergence:
  gradient infinity norm at most `1e-5`, **or** relative objective change at
  most `1e-9` for five iterations while gradient infinity norm is at most
  `1e-3`.

[Lafferty, McCallum, and Pereira (2001)](https://dl.acm.org/doi/10.5555/645530.655813)
support the use of a conditional sequence model with interacting observation
features and output transitions.
[Liu and Nocedal (1989)](https://doi.org/10.1007/BF01589116) is the primary
L-BFGS reference.
[Menon et al. (2021)](https://openreview.net/forum?id=37nvvqkCo5) and their
[official code](https://github.com/google-research/google-research/tree/master/logit_adjustment)
support prior-based adjustment for long-tailed multiclass prediction. The
fixed V4 use is an empirical extension to CRF emissions, not a claim that the
i.i.d. multiclass theory supplies a new structured-prediction guarantee.

[Collins (2002)](https://aclanthology.org/W02-1001/) and the official
[CRFsuite](https://github.com/chokkan/crfsuite),
[python-crfsuite](https://github.com/scrapinghub/python-crfsuite), and
[seqlearn](https://github.com/larsmans/seqlearn) repositories remain useful
method references. They are not V4 implementations or runtime dependencies.

[Cui et al. (2019)](https://openaccess.thecvf.com/content_CVPR_2019/html/Cui_Class-Balanced_Loss_Based_on_Effective_Number_of_Samples_CVPR_2019_paper.html)
is not adopted. Correlated tokens from one inscription family are not
independent image-classification examples, so raw token counts would
overstate evidence.

## Fold and information boundary

- Reuse exactly the deterministic five outer V3 family assignments.
- A complete sequence family never crosses an outer boundary.
- The V2 holdout remains unavailable and unscored.
- The ORACC prospective source remains unavailable to fitting, feature
  design, debugging, evaluation, and reporting.
- Every outer training and validation side must contain positive support for
  all five states.
- Gold labels never enter profile construction, scaling, class-independent
  feature computation, or opaque-form equality.
- There is no seed search, replacement split, support fallback, or
  post-result threshold change.

The target-batch profile is transductive but label-free. It tests adaptation
to the distribution of an already supplied unlabeled batch; it is not an
inductive promise for a single isolated future inscription.

Grouped evaluation and a fixed pre-result method are required because
ordinary row-level resampling and tuning can overfit dependent data and the
selection criterion itself:
[Varma and Simon (2006)](https://doi.org/10.1186/1471-2105-7-91),
[Cawley and Talbot (2010)](https://jmlr.org/papers/v11/cawley10a.html), and
[Roberts et al. (2017)](https://doi.org/10.1111/ecog.02881).

## Nonselecting diagnostics

The following are diagnostic refits or decodes only. They cannot select a
candidate, alter the primary result, rescue a failed gate, or authorize a
reserved-source run:

1. CRF refit without the corpus-level profile;
2. primary CRF decoded with transition weights set to zero;
3. an independent logistic emission model;
4. a self-inclusive profile as an explicit optimistic upper bound; and
5. a strict single-family profile whose leave-one-family-out support is empty.

Feature-family ablations are likewise diagnostics only. V4 does not choose a
feature subset from their results.

## Frozen decision gates

Macro-F1, recall, and paired fold comparisons use the same family weighting
and state definitions as V3.

### Hard-invalid

The run is invalid and emits no scientific metrics after any:

- train/validation, clean/mild, gold, family, opaque-ID, cache, or report
  boundary leak;
- V2 holdout or ORACC access;
- missing five-state support in a required partition;
- non-finite value;
- optimizer failure; or
- test or integrity-check failure.

### `ADVANCE`

Every condition below must pass:

- mild out-of-fold macro-F1 at least `0.36432759235715436`;
- mild `settlement_name` recall at least `0.15`;
- positive paired mild macro-F1 delta over V3 in at least four of five outer
  folds;
- full-profile CRF mild macro-F1 exceeds the no-profile CRF diagnostic by at
  least `0.02`;
- other mild recall floors:
  - `context_only >= 0.520654531441017`;
  - `quantity >= 0.1765055025096581`;
  - `unit >= 0.3767836311289388`; and
  - `person_name >= 0.4988092152820551`;
- clean macro-F1 at least `0.36`; and
- clean `settlement_name` recall at least `0.10`.

If the self-inclusive-profile macro-F1 exceeds the primary leave-one-family-out
macro-F1 by more than `0.05`, set `self_information_sensitive` and block
advancement even when all other thresholds pass.

Any valid run that does not meet every advancement condition is
`development_killed`. No V4 outcome in this protocol executes or authorizes an
ORACC evaluator. Passing would support only a better known-script structural
model, not an Indus reading.

## Primary research adopted with limits

| Primary source | Observation that can inform V4 | Binding limit |
|---|---|---|
| [Rao et al. (2009), *Science*](https://doi.org/10.1126/science.1170391) | Conditional entropy can compare sequence flexibility under controlled tokenization. | Entropy similarity is not a reading or proof of natural language. |
| [Yadav et al. (2010), *PLOS ONE*](https://doi.org/10.1371/journal.pone.0009506) | Frequency rank, boundary tendencies, local transitions, smoothing, and held-out restoration are content-neutral measurements. | Short texts make high-order n-grams sparse; “formal structure” does not identify language or meaning. |
| [Sinha et al. (2011), *Computer Speech & Language*](https://doi.org/10.1016/j.csl.2010.05.007) | Directed degree, strength, and core/periphery measurements motivate context-profile diagnostics. | Raw network values are frequency- and corpus-size-sensitive and are not V4 syntax evidence. |
| [Ashraf and Sinha (2012), CICLing](https://doi.org/10.1007/978-3-642-28604-9_12) | Frequency, positional entropy, and coreness can be compared across English, Chinese, Sumerian, and Indus inventories. | These measurements are correlated; a “core” is not a semantic class. |
| [Born et al. (2019), Proto-Elamite](https://aclanthology.org/W19-2516/) | Left/right contexts and agreement across several unsupervised views are useful diagnostics. | Hapax-heavy data and uncertain sign units prevent clusters or topics from becoming ground truth. |
| [Born et al. (2022), Proto-Elamite](https://aclanthology.org/2022.emnlp-main.620/) | Sequence-local models can expose positionally concentrated document structure and annotation errors. | The paper explicitly lacks ground truth and allows analytic overfitting; latent states require expert interpretation. |
| [Cassani et al. (2018), *PLOS ONE*](https://doi.org/10.1371/journal.pone.0209449) | Frequency, contextual diversity, and predictability are plausible category-induction signals. | The study is not an ancient-script or universal cross-script validation. |
| [Ferrara et al. (2022), Cypro-Minoan](https://doi.org/10.1371/journal.pone.0269544) | Context, material, style, and damage matter when investigating allographs. | Visual or allograph similarity is not semantic-role evidence. |
| [Daggumati and Revesz (2021)](https://doi.org/10.1057/s41599-021-00713-0) | Direction and sign-equivalence uncertainty deserve explicit alternative analyses. | Proposed allograph pairs and directions are hypotheses, not frozen V4 truth. |
| [Mukhopadhyay (2023)](https://doi.org/10.1057/s41599-023-02320-7) | Object, numerical adjacency, and archaeological context may later test structural predictions externally. | Proposed taxation, trade, licensing, and commodity functions are not gold labels. |

The [Proto-Elamite toolkit](https://github.com/sfu-natlang/pe-decipher-toolkit),
[document-structure data/code](https://github.com/sfu-natlang/pe-headers), and
[Sign2Vec_d repository](https://github.com/ashmikuz/sign2vec_d) are useful
open references. Their licenses, revisions, input rights, and assumptions
still require a separate adoption review.

## Why structure is not decipherment

[Sproat (2014)](https://doi.org/10.1353/lan.2014.0031) showed that previously
used entropy comparisons did not reliably separate writing from a broader set
of structured non-linguistic systems. Therefore:

- no entropy, Zipf, graph, HMM, CRF, perplexity, or rigidity statistic is a
  decipherment criterion;
- forward/reverse asymmetry shows irreversibility, not intended reading
  direction by itself;
- an HMM state, cluster, CRF role, network core, or attention peak is not a
  phoneme, morpheme, word, office, commodity, or name;
- known linguistic, heraldic, administrative, and randomized baselines must
  use the same unit definition and normalization; and
- an eventual reading requires independent linguistic and archaeological
  predictions that can fail on material not used to construct it.

Structural role induction is valuable because it can reduce and falsify later
hypotheses. It is not a substitute for that later validation.

## Current-claim triage at the research cutoff

### Track only

- [Nair (2026), arXiv:2604.17828](https://arxiv.org/abs/2604.17828) proposes a
  multi-metric synthetic-baseline scorecard. The arXiv record says code is
  available from the author on request while the abstract says code and data
  are publicly available. V4 must wait for a citable, fixed source package and
  independent reproduction before using its results.
- [Tiwari (2026), ACL NLP4DH](https://aclanthology.org/2026.nlp4dh-1.28/)
  asks useful questions about position, direction, visual grouping, HMMs, and
  sequence prediction, but the reported results are not V4 evidence:
  positional rigidity is defined as `1 - H_i/H_1` while Table 2 reports values
  above 1; Table 4 gives lower perplexity to every modified set than to the
  real test set while the discussion interprets modifications as less
  probable; and the paper states that processed data and scripts will be made
  available. Reproduce from a fixed release before reconsideration.
- [Dixit et al. (2025), ASDA](https://doi.org/10.5334/jcaa.175) and
  [Ganeriwala et al. (2025), few-shot recognition](https://doi.org/10.1145/3773290)
  concern recognition or archiving. Their results may inform corpus-quality
  work, not reading, meaning, or decipherment.

### Do not use as labels, priors, or success evidence

- [Neukart (2025), SSRN](https://doi.org/10.2139/ssrn.5141753) reports direct
  readings from nine copper plates without an independently accepted key.
- [Pierson (2026), Zenodo preprint](https://doi.org/10.5281/zenodo.20414696)
  proposes 185 Proto-Dravidian readings but explicitly records anchor
  circularity, underdetermination, and the absence of specialist review.
- [Ross (2026), Zenodo preprint](https://doi.org/10.5281/zenodo.19362548)
  promotes treewidth and proposed readings as decipherment evidence. The
  project's [independent treewidth audit](ROSS_2026_TREEWIDTH_AUDIT.md)
  reproduced the reported upper bound but found it non-anomalous under the
  declared nulls.
- [The Indus Script: Preliminary Lexical and Functional Decipherment
  (2025)](https://doi.org/10.5281/zenodo.17330061) is a proposed lexicon and
  function catalogue, not accepted ground truth.

These records belong in a claim registry so that later tests can address them.
Excluding them from training is not a declaration that every proposal is
false; it prevents the model from validating assumptions supplied as its own
answers.

## Interpretation boundary

An `ADVANCE` result would mean only that the frozen distributional profile and
single CRF improved a reused known-script development task under its fixed
gates. `development_killed` would mean that this observable feature surface
did not justify further reserved-source evaluation. Neither outcome assigns
an Indus language, function, sound, reading, translation, decipherment, or
prize eligibility.
