# Decipherment-efficiency audit

**Audit date:** 2026-07-28

**Decision status:** adopted research strategy; no decipherment claim

**Question:** Is the present transcription-and-verification path the
highest-efficiency route to an independently defensible decipherment?

## Executive verdict

**No—not if the present path is continued as a single, serial pipeline.**

The verification work completed so far is necessary scientific insurance: it
prevents a machine proposal, OCR error, duplicated object, leaked split, or
post-hoc reading from silently becoming “evidence.” Its marginal value now
drops sharply, however, if every one of the 700 KP1982 sign-list slots must be
double-reviewed before any corpus extraction or semantic experiment begins.

The higher-efficiency route is parallel and information-gain driven:

1. freeze the completed verifier as V1 unless a downstream experiment exposes
   a concrete defect;
2. use a stratified subset of the KP1982 sign list as calibration evidence
   while generating abstaining machine proposals over all 179 concordance data
   pages;
3. federate independent corpus editions without erasing disagreements;
4. test high-information functional anchors—especially numeral-like strokes,
   weights, capacities, tablet families, sealings, object types, sites, and
   periods;
5. make linguistic, non-linguistic, hybrid, and multilingual hypotheses
   compete under the same preregistered held-out tests; and
6. spend further annotation effort only where it can distinguish surviving
   hypotheses.

日本語要旨: これまでの検証基盤は無駄ではないが、700枠の全量人手判定を解読開始の
前提にすると遅い。V1を凍結し、80–120枠程度の層化較正、concordance
179データページの棄権可能な機械抽出、外部文脈アンカー、競合仮説の封印評価を
並走させる。目的は
「もっと多く転写する」ことではなく、「誤った仮説を最少時間で落とす」ことである。

## What changed the decision

### KP1982 is a corpus-extraction lever, not only a 700-cell list

The official University of Helsinki record describes a 201-page final
published version and labels it CC BY 4.0. Pages 20–21 contain the 700-slot
sign list already fixed by the Batch 0 source contract. A reproducible visual
audit of the same exact PDF classifies page 22 as the section title page and
pages 23–201 as 179 concordance data pages. Page 22 is useful as a negative
control; it must not produce invented rows.

That changes the return on the sign-list work. The 700 layout slots, their
printed content, and eventual reviewed identifier observations can calibrate
template matching, segmentation, OCR ranking, and abstention over the
concordance pages. The sign list should therefore be treated as a calibration
dictionary and uncertainty reference, not as an isolated transcription
destination.

This does **not** mean that unreviewed machine output becomes a corpus. A
machine proposal remains a proposal. It must carry page geometry, source-byte
commitments, confidence or abstention, and disagreement links; admission to a
research corpus remains a separate decision.

Sources:

- [University of Helsinki publication record and CC BY access statement](https://researchportal.helsinki.fi/en/publications/a-concordande-to-the-texts-in-the-indus-script/)
- [Official KP1982 PDF](https://tuhat.helsinki.fi/ws/portalfiles/portal/209717802/indus_concordance_1982.pdf)
- [CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/)

Any released derivative must credit the authors, title, year, publisher,
source, and licence; indicate modifications; and avoid implying University or
author endorsement. The licence applies to the identified PDF, not
automatically to portal metadata, another edition, a crosswalk source, or a
third-party artifact image.

### A larger corpus already exists, but access and lineage are not equivalent

The 2023 ICIT project abstract reports 4,665 inscribed objects, 5,650 texts,
17,966 legible sign occurrences, and 16,015 photographs or drawings. It also
warns that artifact distributions are heterogeneous and must not be treated as
one homogeneous dataset. The public ICIT page supports interactive sign,
sequence, statistical, and geographic search, but directs researchers to an
administrator for database access.

Consequently, reproducing another undifferentiated sequence list is not the
highest-value contribution. The missing public value is a rights-aware,
edition-aware federation with explicit uncertainty, object context, and sealed
tests. A formal export would be valuable, but public web access alone is not a
bulk-data or image-reuse licence.

Sources:

- [ICIT public project page](https://www.epigraphica.de/indus/menueindus.htm)
- [Andreas Fuls, 2023 ICIT abstract, pp. 44–45](https://asc.iitgn.ac.in/assets/events/training_workshop/Book_of_Abstracts_com.pdf)

### The hard bottleneck is an anchor, not another fluent model

Current evidence supports directionality, positional restrictions, recurring
clusters, and heterogeneous use. It does not fix sound values, language,
meaning, or even a single uniform generative system.

Recent computational-decipherment successes on other scripts rely on
information that Indus research lacks: a known related language, cognates,
phonetic priors, longer texts, or a bilingual. The successful model class
cannot be transferred as an end-to-end “AI decoder” merely by increasing
compute.

The 2025 field review by Sinha and Ashraf explicitly warns against brute-force
AI claims and argues for coupling sequences to findspot, material, artifact,
and other physical context. Kenoyer and Meadow likewise show why stratigraphy,
medium, chronology, repeated molds, sealings, and tablet families can carry
information that a flat sign string loses.

Sources:

- [Sinha and Ashraf 2025, “Data and Decipherment”](https://www.imsc.res.in/~sitabhra/papers/sinha_ashraf_Indus100_confproc_2025.pdf)
- [Kenoyer and Meadow 2010, *Inscribed Objects from Harappa Excavations 1986–2007*](https://www.harappa.com/sites/default/files/pdf/KenoyerMeadow%202010%20Inscribed%20Objects%20from%20Harappa.pdf)
- [Luo, Cao, and Barzilay 2019, neural decipherment with cognate structure](https://aclanthology.org/P19-1303/)
- [Luo et al. 2021, decipherment using phonetic priors](https://aclanthology.org/2021.tacl-1.5/)
- [Braović et al. 2024, systematic computational-decipherment review](https://aclanthology.org/2024.cl-2.7/)

## Expected value by workstream

“Efficiency” here means expected reduction in uncertainty between competing
explanations per unit of research time, not raw records processed.

| Workstream | Expected information gain now | Main risk | Decision |
|---|---:|---|---|
| More generic governance or verifier layers | low | engineering becomes the research target | freeze V1 after release |
| Serial full-700 double review before analysis | medium | delays every downstream test | retain as a high-assurance path, not the critical path |
| Stratified sign-list calibration plus full-concordance machine proposals | high | OCR propagates errors | start in parallel; abstain and review disagreements |
| Formal ICIT/RMRL/CISI/Wells export and crosswalk | very high | access, licence, and lineage uncertainty | prepare adapters; request access only with separate authority |
| Context-rich internal anchors | very high | confounding by site, period, or medium | highest immediate analytic priority |
| Mesopotamia/Dilmun/Oman contact-material search | high impact, low hit probability | “Indus-style” is mistaken for a bilingual | bounded search with strict same-object/same-event rule |
| LLM or dictionary-led direct translation | negative | unconstrained post-hoc fit and hallucination | do not use as evidence |

## Revised operating model

### 1. Freeze the current verifier V1

The current KP1982 source, layout, assignment, two-review comparison, crop
rehashing, and no-invention adjudication software becomes a stable
high-assurance instrument.

After release, change it only if:

- an implemented downstream extraction exposes a reproducible correctness or
  security defect;
- the fixed public contract contradicts the pinned source bytes; or
- a schema omission prevents preservation of a real observation without
  interpretation.

New convenience features, additional assurance wording, or speculative
future-custody machinery do not justify delaying research experiments.

### 2. Add a separate KP1982 concordance fast lane

The fast lane does not redefine or complete Batch 0.

1. Select approximately 80–120 sign-list slots by a deterministic,
   preregistered mixture of:
   - high expected frequency;
   - numeral-like and modifier-bearing shapes;
   - visually similar/allograph candidates;
   - rare or compound shapes;
   - scan-quality and segmentation difficulty; and
   - random audit coverage.
2. Obtain independent visual evidence for the selected calibration tranche.
3. Separately create a stratified end-to-end concordance reference of roughly
   8–12 pages and 300–500 printed rows, including long, dense, multiline,
   noisy, and boundary cases; keep part sealed.
4. Generate source-bound machine segmentation and sign proposals over pages
   23–201 immediately; allow explicit abstention and require empty output on
   the page-22 negative control.
5. Use ordinary OCR only for printed numeric or alphabetic fields. Recognize
   Indus glyphs through source-specific template/classifier proposals, not a
   presumed Unicode text recognizer.
6. Freeze the production recognizer before opening the sealed cell and row
   evaluations.
7. Prioritize human review by uncertainty, source disagreement, expected token
   coverage, and effect on an active hypothesis.
8. Keep every unreviewed proposal outside admitted corpora and evaluation.
9. Continue toward the full 700-slot review only when its marginal error
   reduction or downstream coverage justifies the effort.

This changes the likely initial workload from roughly 1,400 independent cell
judgments to roughly 160–240 judgments, plus disagreement adjudication, while
preserving the full contract for later high-assurance completion. Those counts
are planning estimates, not completed-review counts or measured accuracy.

The cell sample tests sign-list segmentation and label observation; it cannot
by itself validate row splitting, key alignment, side boundaries, reading
order, identifier reconstruction, sequence accuracy, or deduplication. The
separate concordance-row reference is therefore mandatory before any
end-to-end accuracy or public-corpus claim. The sample seed, strata, inclusion
probabilities, development/sealed split, and stopping rule must be fixed before
model tuning. A risk-enriched sample cannot be reported as population accuracy
without the corresponding sampling weights.

The concordance repeats an inscription around different keyed sign
occurrences. Printed rows must not be counted as unique inscriptions.
Repetition is instead a powerful internal consistency check after recovery of
the source-local identifiers.

### 3. Federate corpora without declaring one edition correct

Build adapters and crosswalks that preserve:

- physical artifact and side identity;
- edition-specific sequence and sign identifier;
- seal face versus impression orientation;
- damage, uncertain strokes, restoration, and reading order;
- site, stratum, period, material, object type, motif, and find context;
- duplicate mold/template and publication-image lineage;
- one-to-many and many-to-one sign correspondences; and
- rights separately for metadata, transcriptions, glyphs, photographs, and
  derivatives.

Conflicts become review targets. They are not silently normalized.

### 4. Run an anchor registry before language mapping

The first experiments should attempt functional partial decipherment:

1. numeral-like strokes × standardized weights or vessel capacities;
2. duplicate miniature-tablet families × rationing, labor, movement, or
   administrative-slot predictions;
3. seals × sealings and reverse impressions;
4. same sequence with different motifs and same motif with different
   sequences;
5. site × period × medium × object-type conditional distributions;
6. repeated formulae and the longest inscriptions; and
7. Indus-related objects from Mesopotamia, Dilmun, and Oman.

An “Indus-style object with a known-language inscription” is contextual
evidence, not automatically a bilingual. A candidate external anchor must
place the two systems on the same object, impression, or securely identical
administrative event, and the correspondence must recur.

### 5. Make hypotheses compete under one budget

At minimum, preregister equal-complexity representatives of:

- Proto-/Para-Dravidian;
- early Indo-Aryan;
- Munda or another substrate;
- an unknown or isolate language;
- a non-linguistic administrative/emblematic system;
- a mixed linguistic and non-linguistic system; and
- one script used for more than one language.

Each receives the same access to data, lexicon budget, allograph budget,
parameters, and tuning folds. All are evaluated on sealed site-, period-, and
medium-level holdouts and matched unrelated-language or symbol-system
controls.

AI may rank OCR candidates, extract claims, write reproducible code, propose
counterexamples, and attack a hypothesis. It may not manufacture missing
strokes, choose a preferred language, or grade its own translation as truth.

## Dynamic resource allocation

The percentages are a project decision, not a fact reported by the cited
literature.

| Period | Stable infrastructure | Corpus federation and QA | Internal functional anchors | External anchors | Hypothesis tournament |
|---|---:|---:|---:|---:|---:|
| Days 0–30 | 10% | 25% | 35% | 20% | 10% |
| Days 31–90 | 10% | 20% | 30% | 15% | 25% |
| Days 91–180 | 5% | 15% | 25% | 10% | 45% |

Language mapping receives the largest share only after at least one functional
anchor survives prospective or held-out testing.

## 30-, 90-, and 180-day deliverables

### Days 0–30

- release and freeze the existing verifier V1;
- inventory the exact page classes and geometry of the KP1982 concordance;
- define and commit the deterministic 80–120-slot calibration sample;
- create the separate 8–12-page, 300–500-row development/sealed concordance
  reference;
- implement abstaining concordance segmentation and template-proposal output;
- reproduce direction, n-gram, entropy, and sequence-null baselines under
  alternative direction, duplicate, and allograph choices;
- define artifact/site/period/medium holdouts before looking at results;
- define a context-rich 150–250-artifact target roster separately from the
  80–120 sign-list calibration slots;
- create the anchor registry and preregister the first numeral and tablet
  tests; and
- build corpus-adapter interfaces without importing unlicensed material.

The output is a calibrated extraction proposal and falsifiable tests—not a
translation.

### Days 31–90

- expand reviewed material by expected information gain until it covers
  approximately 90–95% of observed tokens or stops changing conclusions;
- compare n-gram, HMM, latent-slot, administrative-template, emblematic, and
  mixed models on the same holdouts;
- run leave-one-site, leave-one-medium, and leave-one-period-out tests;
- link numeral-like patterns to independently measured quantity, weight,
  capacity, or object variables where evidence exists;
- review repeated-mold tablets, seal/sealing pairs, and context-rich Harappa
  groups;
- audit contact-zone objects under the strict external-anchor rule; and
- put published “decipherment” claims into a registry that includes their
  failure cases and parameter freedoms.

### Days 91–180

- evaluate all surviving models on a sealed tranche that includes newly
  transcribed or newly catalogued material;
- compare them with permutation controls, synthetic non-linguistic controls,
  minimum-description-length penalties, and calibrated uncertainty;
- seek blind review from archaeology, epigraphy, historical linguistics, and
  statistics specialists only under a separately authorized procedure;
- advance to sound values only if multiple independent functional anchors
  survive; and
- publish a partial functional result if that is all the evidence supports.

## Kill criteria

Stopping weak work is part of the efficiency plan.

### General corpus expansion

Stop undirected expansion when a new batch:

- changes every decision-relevant statistic by less than one standard error;
- adds no new context class, sign pair, or external anchor; and
- does not change the ranking of surviving hypotheses.

After that point, add only records selected to distinguish specific hypotheses.

### OCR and template matching

- Auto-admission remains forbidden until an independently reviewed,
  preregistered high-confidence stratum reaches at least 99% precision.
- Below that threshold, the system remains suggestion-only with abstention.
- Stop optimizing average classification accuracy if it does not reduce
  sequence-level error, review time, or hypothesis uncertainty.
- Redesign layout immediately if a source page is missing, the page-22
  negative control produces a row, pilot row recall is below 99%, or row
  split/merge error exceeds 1%.
- Hold public sequence release if a frozen sealed evaluation has identifier
  exact match below 99.9%, token accuracy below 99%, exact-sequence accuracy
  below 98%, unresolved/conflict rate above 1%, or repeated-identifier
  consistency below 99.5%. These are conservative project gates, not
  literature-established proof thresholds.

An 80–120-cell audit is suitable for feasibility and discovering error modes,
not for proving that all 700 slots have error below 1%. If such a population
claim is needed, expand the probability sample substantially—approximately
300 randomly selected slots when no errors are observed—or review all slots,
and publish confidence intervals rather than only point accuracy.

### Numeral and metrology model

Kill or revise it if:

- monotonicity or compositionality vanishes under leave-one-site or
  leave-one-object testing;
- it fails to outperform frequency-matched permutations; or
- it cannot prospectively predict an independent quantity, weight, capacity,
  or object slot.

### Administrative or tablet-slot model

Kill or revise it if:

- the context association disappears after stratifying by site, period, and
  medium;
- a general sequence model achieves equal or better held-out likelihood or
  description length; or
- the same sequence repeatedly occurs in contexts the model declared
  incompatible.

### Language or sound-value model

Kill it if:

- coverage requires inscription-specific synonyms, dictionary additions,
  direction changes, or allograph merges after seeing the test;
- matched unrelated languages or symbol permutations perform similarly;
- the advantage disappears in any major domain holdout;
- historical sound changes, morphology, and ordering are inconsistent; or
- it makes no successful prospective prediction.

A corrected permutation result or Bayes factor around 10 may justify further
testing, but cannot by itself prove a language or decipherment.

### External-anchor search

Reduce this workstream from 10–20% to approximately 3% after 90 days if no
same-object, same-impression, or securely same-event candidate is found.
Trade contact, visual resemblance, or the title “Meluhha interpreter” alone
does not create paired text.

## Current 2026 computational claims: use as reproduction targets

The latest large-corpus papers reinforce the strategy shift but do not supply a
reading.

- Tiwari 2026 reports 6,579 inscriptions and structured sequence behavior.
  The paper is a structural study, not a decipherment. Its published PDF also
  needs reproduction before adoption: the stated positional-rigidity formula
  has an upper bound of 1 while reported values include approximately 1.78,
  and its “lower is more natural” perplexity definition conflicts with a table
  in which every modified sequence scores below the real test data.
- Nair 2026 uses 1,916 deduplicated inscriptions, 584 signs, 11,110 tokens, and
  stronger synthetic non-linguistic controls. Its result is intermediate:
  neither tested baseline family reproduces the whole profile. The abstract
  says code and data are public while the same record says code is available
  on request, so the analysis remains a reproduction target rather than an
  adopted benchmark.

Sources:

- [Tiwari 2026, *Statistical Structure in Indus Sign Sequences*](https://aclanthology.org/2026.nlp4dh-1.28/)
- [Nair 2026, *How Non-Linguistic Is the Indus Sign System?*](https://arxiv.org/abs/2604.17828)

## Claim and prize gate

A candidate may be described as a partial or complete decipherment only when
all of the following are true:

1. the sign mapping and allowed variants were fixed before final evaluation;
2. it predicts unseen sequences or archaeological contexts better than strong
   linguistic and non-linguistic baselines;
3. the result survives alternate corpus editions, direction choices,
   allograph policies, duplicate treatment, sites, periods, and media;
4. multiple independent anchors support compatible functions or readings;
5. a separate team reproduces the result from the published procedure; and
6. prospective material confirms predictions that were recorded in advance.

The Tamil Nadu announcement is an incentive, not a scientific scoring rule.
Until an official operational submission protocol, panel, evidence standard,
and deadline are verified, the project optimizes for independent scholarly
acceptance rather than a presumed application form. Contacting an institution
or submitting a claim remains a separately authorized external action.

See the separate
[dated prize-status audit](TAMIL_NADU_PRIZE_STATUS_2026-07-27.md) for the
announcement evidence and unresolved operational rules.

## Bottom line

The project was not going in the wrong direction; it was staying in the
foundation phase too long. The efficient correction is not to discard the
foundation. It is to freeze it and convert it into leverage:

**small audited calibration set → full source-bound extraction proposals →
context-rich anchors → equal-budget hypothesis tournament → prospective
replication.**

That route still cannot guarantee a decipherment. No responsible method can,
because a decisive bilingual or equivalent anchor may not exist in the
currently known record. It does maximize the rate at which this project can
produce either a defensible breakthrough or a decisive negative result.
