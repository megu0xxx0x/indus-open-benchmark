# Helsinki corpus fast-path audit

**Audit timestamp:** 2026-07-28 11:54 JST (Asia/Tokyo)

**Implementation validation update:** 2026-07-28 12:34 JST (Asia/Tokyo)

**Decision status:** adopted critical-path correction; no transcription,
translation, language assignment, decipherment, or prize claim

## Decision

The previous plan—finish the KP1982 700-cell sign list and then extract all
179 concordance pages—is not the maximum-efficiency route.

The new critical path is:

1. extract the 57-page identifier-order corpus in the official 1979 volume;
2. reconcile it against the same volume's sorted-from-end and
   sorted-from-beginning renderings;
3. apply the official 1980 additions, corrections, cross-references,
   documentation, and duplicate assertions as a versioned delta;
4. use the 1982 concordance as a sign-occurrence and revision consistency
   layer rather than the first full transcription target;
5. begin a 150–250-object, high-information gold corpus and hypothesis
   tournament before attempting full coverage.

The KP1982 V1 verifier and sign-list workflow remain useful calibration
instruments. They are not discarded, but full 700-cell completion no longer
blocks corpus work or falsifiable experiments.

## Why this is faster

The 1979 volume contains the same source-local records in three useful
orders:

| Rendering | PDF pages | Immediate use |
|---|---:|---|
| Identifier-order base corpus | 22–78 | First transcription lane; 57 pages |
| Sorted from the end | 79–128 | Detect suffix/final-position and extraction disagreements |
| Auxiliary catalog grids | 129–130 | Catalog state only; exclude from linguistic sequences |
| Sorted from the beginning | 131–180 | Detect prefix/initial-position and extraction disagreements |

The base lane is less than one third of the 179-page KP1982 concordance lane.
The two reprints then provide internal checks without first solving sign
recognition. Matching must begin with the printed identifier and lower code;
the sign sequence is the value being checked, not the key used to force a
match.

One direct audit example is `(identifier=692, code=73 98)`:

- identifier-order rendering: PDF page 29;
- sorted-from-end rendering: PDF page 106;
- sorted-from-beginning rendering: PDF page 131.

All three preserve the same left-to-right printed sequence. The reprints move
the label from the right to the left and back, but do not require a sequence
reversal. This is internal consistency evidence, not an independent
archaeological witness.

## Exact public sources

### 1979 base and sorted corpus

- [Official University of Helsinki record](https://researchportal.helsinki.fi/en/publications/corpus-of-texts-in-the-indus-script/)
- [Official PDF](https://tuhat.helsinki.fi/ws/portalfiles/portal/176353520/indus_corpus_1979.pdf)
- Licence shown by the official record: CC BY 4.0
- Exact size: `16,935,356` bytes
- SHA-256:
  `e6f9dec7cf98d2ee6130f068e60ab37021808dd63953de41f92ce457b35a4bfa`
- PDF pages: 180; the cover is additional to the 179 printed pages
- PDF page = printed page + 1 after the cover
- PDF pages 2–180: one 4880×7010, one-bit native image per page

Poppler `pdfimages 26.04.0` and MuPDF `mutool 1.27.2` independently decoded
pixel-identical results for all 179 mapped pages. The MuPDF PNG comparison was
performed through Pillow 11.3.0. This is reproducible decoder agreement inside
the project, not external replication.

### 1980 corrections, documentation, and duplicates

- [Official University of Helsinki record](https://researchportal.helsinki.fi/en/publications/documentation-and-duplicates-of-the-texts-in-the-indus-script/)
- [Official PDF](https://tuhat.helsinki.fi/ws/portalfiles/portal/207886811/indus_duplicates_1980.pdf)
- Licence shown by the official record: CC BY 4.0
- Exact size: `8,143,483` bytes
- SHA-256:
  `0ced4102dc6197246df6c84e4b730ed380f41085a4a1ea8dd8a6459332da37d1`
- PDF pages: 98
- Every page: one 4904×6761, one-bit scan plus a non-Unicode OCR layer

High-value machine-data ranges:

| PDF pages | Content |
|---|---|
| 20–23 | Additions, deletions, and revisions to the 1979 corpus |
| 27–29 | Finnish identifier to Mahadevan identifier |
| 30–32 | Mahadevan identifier to Finnish identifier |
| 40–51 | Documentation list |
| 59–98 | Strict and loose duplicate lists |

The OCR layer is a locator only. Image checks found digit and section-number
errors, including `0334` read as `0330`, `3401` read as `3001`, and section
`3.2` read as `5.2`. No identifier, range, suffix, punctuation, uncertainty
mark, or group boundary may become canonical from OCR alone.

Duplicate-list state can continue across a column or page. A parser must carry
the current loose group and strict subgroup forward. It must prove that every
declared subgroup count and group total reconciles or abstain from the entire
group.

The 1980 `strict` and `loose` relations describe information redundancy under
the authors' rules. They do not automatically mean the same physical object,
the same ancient matrix, or an exact text duplicate. The canonical data model
must keep these relations separate.

### 1982 occurrence concordance

- [Official University of Helsinki record](https://researchportal.helsinki.fi/en/publications/a-concordande-to-the-texts-in-the-indus-script/)
- [Official PDF](https://tuhat.helsinki.fi/ws/portalfiles/portal/209717802/indus_concordance_1982.pdf)
- Exact size: `16,767,043` bytes
- SHA-256:
  `07d24564cd3abf23620a3cd9d417c9931c9d3e1aafb204d7c4fd49b4022d043c`

Page 22 is a negative control and pages 23–201 are 179 occurrence-concordance
pages. Concordance rows repeat inscriptions around different keyed signs and
must never be counted as unique inscriptions.

## Implemented source and layout gate

This update adds:

- `registry/kp1979_corpus.json`: exact source and section contract;
- `registry/kp1979_page_map.json`: exact native PBM commitments, page classes,
  proposal-only scan bands, and the 12-page layout protocol;
- `verify-kp1979-source`: network-free exact PDF and contract verification;
- `audit-kp1979-layout`: streaming verification of all 179 PBMs followed by a
  pixel-only, abstaining two-column detector;
- `prepare-kp1979-row-assignment` and
  `verify-kp1979-row-assignment`: private no-overwrite generation and
  independent canonical reconstruction of proposal-only label/row review
  crops for the 57 identifier-order pages;
- synthetic tests for valid lattices, blank pages, incompatible lane pitches,
  a one-sided discontinuous-lane false positive, ten-column confounds, and
  malformed PBMs.

The detector uses no OCR, identifier, sign inventory, corpus value, direction,
language, meaning, or translation. It fits a 158–172-pixel vertical lattice
inside two audited scan bands and rejects pages that resemble a repeated
multi-column table. Both lanes must independently satisfy the contiguous-run
gate; a regular lane cannot authorize a discontinuous peer lane.

The exact-source run passed these gates:

- all 179 native page images matched the fixed page map;
- all normal two-column corpus pages produced two label-lattice proposals;
- dense prose page 8 produced no admitted label-slot proposal;
- ten-column sign-list pages 20–21 produced no admitted label-slot proposal;
- eight-column page 129 and six-column page 130 produced no admitted
  label-slot proposal;
- label-slot candidates intersecting the predeclared English-prose mask on
  page 180 were removed by that mask.

The page-180 result is mask enforcement, not evidence that the detector
recognized prose: the raw detector has candidates in that region, and its
false-positive rate there is unmeasured. These are label-lattice gates, not
full-row segmentation or row-accuracy results. Candidate label slots remain
unaccepted until the selected pages have independently prepared manual labels
and a frozen detector is evaluated against them.

The row-assignment command does not advance that acceptance state. It repeats
the full source/layout audit, re-reads the fixed base pages, and stores only
visual slot locators plus exact label- and row-crop commitments. It contains
no OCR, printed identifier, lower code, sign value, occupancy decision,
reading direction, interpretation, or external manual reference. The private
manifest is therefore a reproducible review roster, not an extracted corpus.

## Twelve-page layout protocol

Development pages:

- 20: ten-column sign-list hard negative;
- 22: identifier-order start;
- 79: sorted-from-end start;
- 129: eight-column auxiliary grid;
- 131: sorted-from-beginning start;
- 180: partial lane plus explanatory prose.

Future evaluation pages (identities and pixels public; manual values absent):

- 8: dense prose hard negative;
- 78: identifier-order terminal page and partial right lane;
- 99: dense normal sorted-from-end page;
- 128: normal two-column page mixing real and auxiliary/damaged entries;
- 130: six-column auxiliary grid;
- 175: dense sorted-from-beginning page with damage marks.

Before a label-lattice accuracy claim:

1. freeze manual label intervals outside the recognizer using the separate
   proposal-free assignments and exact-crop review contract in
   [`KP1979_LABEL_REFERENCE_PROTOCOL.md`](KP1979_LABEL_REFERENCE_PROTOCOL.md);
2. freeze the interval-membership, same-lane, order-preserving one-to-one
   matching rule before opening future-evaluation values, then require 100%
   label-position precision and recall on the future-evaluation positive
   pages;
3. require zero label slots on pages 8, 20, 129, and 130;
4. reject any geometry observation assigned twice or left unexplained; defer
   duplicate identifier-value checks to the later identifier/code
   transcription contract because a y-only reference contains no identifier
   value;
5. do not fill a partial lane to an assumed 36 rows;
6. queue any label spacing outside 40–58 pixels or row pitch outside
   158–172 pixels;
7. keep auxiliary signs, damaged text, inaccessible text, fully broken text,
   and uninscribed objects outside linguistic sign sequences.

## Worldwide open-source triage

Public availability is not equivalent to a reusable licence, reliable
lineage, or a valid decipherment.

### Latest cross-script signal

[AlphaOracle (20 July 2026)](https://arxiv.org/abs/2607.17849) reports a
four-stage oracle-bone workflow—image parsing, form evolution, contextual
retrieval, and philological validation—with explicit evidence chains and a
study of 86 specialists. Its reported time saving supports stage-separated
human/AI work rather than an end-to-end translation model. It does not supply
an Indus shortcut: oracle-bone work has diachronic descendants, classical
textual grounding, and a much larger specialist corpus that the Indus case
lacks. No exact code revision was linked from the arXiv record during this
audit, so it is design evidence only and not an admitted dependency or
benchmark.

### Eligible next admissions

- [Sproat non-linguistic symbol corpora](https://richardsproat.com/data/non-linguistic-symbols/):
  candidate matched non-linguistic controls, not an authoritative Indus corpus.
- [Proto-Elamite decipherment toolkit](https://github.com/sfu-natlang/pe-decipher-toolkit):
  candidate known/partially understood script benchmark after modernizing its
  old dependencies.
- [Mayig limited corpus](https://github.com/mayig/indus-valley-script-corpus):
  use only for schema and pilot tests; it is a small, single-site,
  single-motif, image-free derived sample.
- [Daggumati and Revesz allograph candidates](https://www.nature.com/articles/s41599-021-00713-0):
  import as falsifiable assertions with artifact references, never as automatic
  sign merges.
- Rights-cleared museum records and images already admitted item by item under
  provider terms.

Except for the already pinned Mayig sample and item-level museum admissions,
these are not canonical inputs in this release. Before ingestion, each exact
revision or byte snapshot, licence, provenance, and permitted use must be added
to the source or quarantine registry.

### Hold behind access, lineage, or licence gates

- [ICIT](https://www.epigraphica.de/indus/menueindus.htm): valuable scale and
  context, but access-gated with no verified bulk redistribution licence.
- [RMRL IndusScript](https://indusscript.in/): official Mahadevan-derived web
  tool, but no verified machine-readable reuse grant.
- [Nair 2026](https://arxiv.org/abs/2604.17828): useful claims to reproduce,
  but code/data availability statements and corpus counts require resolution.
- [Dixit et al. image code](https://github.com/DM-BiCLab/Deep-Learning-in-Archiving-Indus-Script-and-Motif-Information):
  code is available, but the complete image set, labels, weights, and
  third-party image rights are not.
- `ivc2tyc`, `mdp-ancient-scripts`, and `yajnadevam/lipi`: inspect in
  quarantine only; code or web visibility does not cure upstream ICIT/CISI
  rights and lineage gaps.

### Do not adopt as evidence of decipherment

- [Tiwari 2026](https://aclanthology.org/2026.nlp4dh-1.28/): no released
  source corpus or implementation was found, and reported formula/result and
  synthetic-perplexity inconsistencies prevent canonical adoption.
- dictionary-led or Sanskrit/Proto-Dravidian translation repositories whose
  anchor selection, crosswalk, evaluation language, and score are fitted on
  the same data;
- any image similarity result presented as proof of linguistic ancestry,
  phonetic value, or meaning.

These projects may enter a claim registry and be tested on the same held-out
data. Their translations, mappings, and scores must not enter observations or
gold labels.

## Provisional high-information work allocation

Until the first frozen hypothesis tournament:

| Work | Allocation |
|---|---:|
| Gold observations and provenance | 35% |
| 1980 corrections, duplicate relations, and crosswalk | 25% |
| Hypothesis and matched-control harness | 25% |
| Archaeological and metrological anchors | 15% |

This is an operating prior, not a measured global optimum. Record actual hours,
new token coverage, disagreements, and hypothesis-ranking changes weekly, then
revise the allocation by observed information gain.

The initial review-day triggers—less than 1% additional covered tokens or more
than 20% disagreement—are provisional triage thresholds, not validated
constants. Run sensitivity checks around them and redirect work only when the
same conclusion holds across reasonable nearby thresholds.

Every statistic must be reported under at least these views:

1. catalog rows;
2. one row per physical artifact;
3. exact-sequence deduplication;
4. 1980 strict-information deduplication;
5. 1980 loose-information deduplication.

If a result changes sign under reasonable direction, allograph, or duplicate
choices, it is not stable enough to support a reading.

## Immediate next milestone

1. Freeze manual row labels for the 12-page protocol before using those labels
   for detector development. This is a future label-withheld check, not a blind
   page or pixel holdout.
2. Extract and double-check only the 1979 identifier-order lane first.
3. Parse the 1980 revision and bidirectional cross-reference tables, preserving
   uncertainty marks and unapplied conflicts.
4. Build three-way record reconciliation before sign classification.
5. Select 150–250 high-information physical objects by site, medium, period,
   length, repeated family, and numeral/metrology relevance.
6. Freeze equal-budget linguistic, non-linguistic, hybrid, and administrative
   models with artifact-, site-, medium-, and period-held-out tests.

The next milestone is not a translation. It is a source-bound, independently
checkable corpus slice capable of killing bad hypotheses quickly.
