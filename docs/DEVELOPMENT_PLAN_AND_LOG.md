# Public development plan and status

**Status date:** 2026-07-29

**Last source-level update:** 2026-07-29 04:36 JST (Asia/Tokyo)

**Project:** Open Indus Benchmark

**Public source:** <https://github.com/megu0xxx0x/indus-open-benchmark>

This document is the public continuation guide. It intentionally excludes
machine topology, authentication details, private storage layout, private data
inventories, item-level private results, and operational incident logs.

## Mission

Build a rights-aware and falsifiable research foundation for Indus
inscriptions without presenting an unverified reading as a decipherment.
Observations, source assertions, hypotheses, and evaluation claims remain
separate and traceable.

## Public state

- The repository is an engineering and governance seed, not an authoritative
  corpus release.
- Normative schemas, validators, importers, audit tools, synthetic examples,
  tests, and scientific/governance documentation are public.
- The current split and evaluator are development-only. They are not blind or
  final.
- No private corpus, provider download, museum image bundle, private review
  packet, hidden-test companion, submission, institutional message, or
  translation claim is part of the public source tree.
- Release tags, package publication, DOI registration, and prize submission
  require separate decisions.

## Implemented public capabilities

1. **Evidence and rights governance**
   - Source, research-evidence, museum-candidate, and quarantine registries.
   - Separate rights states for metadata, transcription, glyph art, images,
     derivatives, training, and redistribution.
   - Dated global research, open-source, museum-rights, and prize-status audits.
   - Exact-byte Penn metadata context staging and a dated primary-source
     Chanhu-Daro field-number crosswalk with unresolved conflicts preserved.

2. **Observation contracts and validation**
   - Nested artifact/side/line/token schema.
   - Observation/hypothesis separation and namespaced extensions.
   - Fail-closed source, rights, identifier, direction, order, and uncertainty
     validation.

3. **Public development evaluation**
   - Duplicate-family and exact-sequence leakage checks.
   - Family-grouped development holdouts.
   - Simple probabilistic baselines, matched-shuffle nulls, and a deterministic
     treewidth audit.
   - A project-authored synthetic known-truth identifiability gate with
     family-safe degradation, equal family weighting, conservative
     family-permutation nulls, and anchor-free abstention.
   - A pre-result-frozen MTAAC V2 known-script control with exact source,
     selected-member, and evaluation-equivalence commitments; gold-independent
     event/null identities; source-family weighting; fixed baselines and
     permutation nulls; and aggregate-only reporting. The aborted V1
     invocation and path-free error are preserved as an explicit erratum. The
     single frozen V2 run returned `NO_GO`, so the unchanged method is blocked
     from Indus transfer.

4. **Integrity protocols**
   - Exact-byte benchmark-definition lock for declared public inputs.
   - Deterministic complete-tree submission commitment `S`.
   - Explicit non-claims for trusted time, confidentiality, custody, blindness,
     execution, result validity, and decipherment.

5. **Private-workflow software boundary**
   - Network-free readiness scanning and deny-all review-bundle generation.
   - Fail-closed museum intake and catalog-blind review tooling.
   - Exact-byte sign-inventory, double-review, adjudication, and private
     transcription-promotion tooling.
   - Exact-byte KP1982 layout and proposal-value-stripped 700-cell bootstrap
     assignment preparation/verification tooling.
   - Non-circular KP1982 structurally distinct bootstrap-review records,
     private two-review audit, and no-invention adjudication verification
     tooling. The software does not establish real-world independence.
   - Exact official KP1979 source and 179-page native-pixel contracts plus a
     streaming, pixel-only label-lattice audit that abstains on prose,
     sign-list, and auxiliary-grid controls. It does not segment full rows;
     label slots remain unaccepted.
   - Public schemas and synthetic fixtures only; real private execution details
     are not public records.

## Verification contract

Contributors should run:

```bash
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python -m unittest discover -s tests -v
uv run indusbench --help
uv build
```

Before any public push, also:

- inspect `git status` and the exact tracked-file inventory;
- confirm no path under `data`, build output, environment, local tool state, or
  credential file is tracked;
- inspect source and wheel/sdist archives;
- scan the current tree and reachable Git history for secrets;
- verify local Markdown links; and
- confirm the public remote head and CI result.

Do not paste private command output into this document. A public verification
record should state only the source-level result needed by contributors.

## Current development plan

### R0 — Decipherment-efficiency reset

The [2026-07-28 efficiency audit](DECIPHERMENT_EFFICIENCY_AUDIT_2026-07-28.md)
finds that the completed verification work is necessary but a serial
“finish all 700 sign-list cells, then start analysis” pipeline is not the
highest-information route.

The public source verifier becomes a stable V1 instrument after this release.
Further generic assurance work does not stay on the critical path unless an
implemented downstream experiment exposes a concrete defect.

Research now proceeds in parallel:

- extract the 57-page KP1979 identifier-order base corpus before the
  occurrence-expanded KP1982 concordance;
- reconcile it against the KP1979 sorted-from-end and
  sorted-from-beginning reprints using identifiers/codes first and sequences
  only as checked values;
- apply the official 1980 additions, corrections, bidirectional Mahadevan
  cross-reference, documentation, and strict/loose duplicate assertions as a
  versioned delta;
- deterministically select an approximately 80–120-slot KP1982 calibration
  tranche without describing it as full Batch 0;
- freeze the KP1979 12-page label-lattice reference before accepting label
  geometry; full-row segmentation is a later, separate gate;
- later freeze the KP1982 occurrence page map, using page 22 as a negative
  control and pages 23–201 as 179 concordance data pages;
- generate abstaining, source-bound proposals and freeze the recognizer before
  opening sealed evaluations;
- preserve edition disagreements and uncertainty through corpus adapters and
  crosswalks;
- preregister functional tests around numeral-like signs, metrology,
  repeated-tablet families, seals/sealings, and archaeological context; and
- compare linguistic, non-linguistic, hybrid, and multilingual hypotheses
  under equal budgets and sealed domain holdouts.

No calibration review, concordance extraction, functional anchor,
language/sound assignment, translation, or decipherment is claimed in this
source update.

The exact reason for the ordering change, official source hashes, section
boundaries, 1980 OCR failure examples, worldwide open-source triage, detector
gates, and next milestone are recorded in the
[Helsinki corpus fast-path audit](HELSINKI_CORPUS_FAST_PATH_2026-07-28.md).

Current assurance layers:

| Layer | Status |
|---|---|
| Public verifier code and synthetic tests | implemented; current release candidate |
| Real calibration or Batch 0 human execution | not executed or claimed |
| Synthetic functional-class identifiability | default gate passed; method sanity only |
| MTAAC real known-script control | V1 error preserved; single frozen V2 run returned `NO_GO` |
| Penn metadata context registry | 34 entries; five pending originality review and 29 negative controls |
| Extra-bulk field-number/context admission | not admitted; two conflicts remain open |
| Scientific functional-anchor validation | not executed or claimed |
| Independent external replication | not executed or claimed |

### P1 — Submission commitment

Implemented. `S` binds a complete candidate tree, declared roles, entrypoint,
static arguments, and a caller-declared benchmark-definition digest. It remains
linkable local integrity evidence and supplies none of the assurances reserved
for an independent custodian.

### P2 — Independent hidden-test companion

Blocked. Work may begin only after all of the following exist:

- a real independent custodian;
- explicit authority and responsibility boundaries;
- a private storage/access/retention procedure;
- an authenticated receipt protocol binding the public benchmark definition
  and `S`; and
- a disclosure plan that reveals no hidden identifiers, values, paths, or
  content digests.

### P3 — Isolated execution and result receipt

Blocked on P2, a fixed runtime contract, and independent execution authority.

### T1 — Private transcription evidence bridge

Implemented as an unsealed v0.1 draft workflow. It verifies exact inventory,
independent-review, and adjudication bytes; separates left-to-right visual
indexing from reading direction; restricts geometry to normalized
axis-aligned rectangles; and creates at most one non-overwriting receipt in an
unresolved artifact template.

Detailed reports and promoted artifacts are private-only `0600` outputs under
a pre-existing physical, descriptor-pinned, owner-only `0700` parent. Public
export and evaluation admission are disabled. The software does not verify
source-document, crop, or source-image bytes; external rights; actual reviewer
independence; blindness; translation; or decipherment.

### T2 — Helsinki 1982 Batch 0

Source identity and target-page pixels are now mechanically fixed, but Batch 0
is not transcribed. The first target is the sign list on one-based PDF pages
20–21 (zero-based indices 19–20) of the official University of Helsinki 1982
CC BY concordance snapshot. A network-free command verifies the exact PDF and
optional canonical PBM bytes. Poppler and MuPDF produced pixel-identical
4888×6705 one-bit pages in the recorded software check; this is decoder
agreement within the project, not an independent research replication.

A fixed-seed generator recomputes all 700 cell and padded-context crop hashes
from the verified PBMs and writes only a private, no-replace proposal. The next
software layer rebuilds that canonical proposal and prepares or verifies a
closed 700-cell reviewer assignment. It retains proposed locator/context
rectangles and crop commitments while structurally withholding machine
occupancy, OCR, identifier, and accepted-observation values.

The non-circular review layer verifies that value-stripped assignment directly
against the two canonical PBMs without supplying the source layout proposal.
It validates and rehashes every submitted observation crop, compares exactly
two structurally distinct sealed passes into a private no-replace report, and
requires a distinct
adjudication to choose an input observation or remain unresolved rather than
invent a third one. A pre-existing sign inventory is not an input.

This is preparation, not execution. Every geometry, occupancy, identifier,
human-review, real-world reviewer-independence/blinding, public-release,
evaluation-admission, and decipherment assurance remains false. The upper
catalog rank, lower primary source identifier, glyph, and printed marks must
still be observed in two genuinely independent human passes and resolved by a
distinct adjudicator. Actor and access declarations do not prove human
authorship, real independence, non-exposure, custody, or rights. No actual
Batch 0 review, adjudication, inventory generation, promotion, evaluation
admission, decipherment, prize eligibility, or prize result is part of this
public update.

### T3 — Helsinki 1979/1980 corpus fast path

The official 1979 PDF, its section map, and all 179 native one-bit page images
are now exact-byte committed. Poppler and MuPDF produced pixel-identical
mapped pages. A common pixel-only detector is run unchanged on normal pages
and hard controls: it proposes label-lattice slots for the normal two-column
corpus and abstains on dense prose, both ten-column sign-list pages, and the
eight- and six-column auxiliary grids. The terminal English-prose region is a
predeclared mask, not detector evidence.

The real exact-source audit passed all current source and page-class gates.
This establishes neither label-position precision/recall, full-row
segmentation, nor an accepted identifier or sign sequence. Page 128's
page-level candidate flag does not admit all of its mixed rows. The future
evaluation page identities and pixels are public; their manual label values are
absent. This is label-withheld preparation, not a blind page or pixel holdout.

The official 1980 continuation is byte-pinned in the source registry. Its OCR
layer contains verified digit errors and is locator-only. The next parser must
preserve a `1979 raw → 1980 revision → 1982 reconciliation` history, validate
both directions of the Finnish–Mahadevan mapping, carry duplicate-group state
across columns/pages, and never collapse strict/loose information redundancy
into physical-object identity.

### T4 — Context anchors and method identifiability

The current official Penn bulk CSV now parses under a strict 32-column
contract that recognizes its exact generic-object-URL terminal sentinel but
continues to reject every other malformed row. Revalidation against the
complete source bytes derives 34 image-free primary-script context entries:
five originality-pending Chanhu-Daro records and 29 replica/modern negative
controls. Field-number, transcription, meaning, language, and originality
approvals remain false.

Mackay's primary excavation report provides field-context leads for the five
Penn records. It also reveals a two-field-number identity collision for
L-141-177 and a narrative/catalog location disagreement for SF 3495. Neither
conflict is resolved by inference. The original register and object-card
ranges are identified in the official Penn finding aid, but no card was
accessed and no institution was contacted.

The synthetic identifiability gate passed its fixed default configuration
after family weighting and a whole-family-vector permutation-p95 null
reference were enforced: macro-F1 0.7762, coverage 0.8869, null-reference
delta 0.3892, and add-one
empirical p=0.01. With anchors removed it reports `not_identifiable` and emits
no F1. This validates only a project-authored synthetic pipeline. The
rights-cleared MTAAC V2 instrument returned `NO_GO`; an admitted Indus
transcription-to-context join remains undone.

### T5 — MTAAC real known-script method control

The first real known-script source is the CC0 MTAAC Gold Corpus at a fixed
upstream commit. The exact archive, 371-member selected manifest, and
evaluation-equivalence corpus fingerprint are fixed. The strict adapter
reproduces 361 admitted documents, 15,038 rows, ten whole-document
quarantines, and 6,743 mechanically projected targets across quantity, unit,
person-name, and settlement-name classes.

The pre-result implementation fixes source-document/complete-sequence-safe
splitting, novel exact-line primary support, clean/mild/harsh cumulative
degradation, family weights, categorical Naive Bayes, majority/position/null
references, 999 label-vector permutation runs, coverage/support gates, and
clean/mild decision thresholds. Harsh, cue-mask, and seen/unseen membership
diagnostics cannot change the outcome. Anchor-free and insufficient-support
states emit no decision metrics.

Two V1 freeze-integrity defects found during independent review were corrected
before its publication. Event and permutation identities now derive from the
validated source identifier and source order rather than a hash containing
gold annotations. The synthetic entry parses raw fixture bytes itself and
rejects not only the fixed archive/manifest but also any container-equivalent
copy of the fixed evaluator-consumed corpus. Tests require annotation-only
changes to leave split, degradation, metrics, and permutation values
unchanged. CLI failures emit path-free error codes, and reports contain no raw
row, source identifier, member path, local path, host, or account value.

V1 was then frozen publicly at commit
`57db0949f6542429d2f05b1bf935ee586bdf3699`. Its first fixed-source invocation
entered the scoring routine but aborted during the first permutation-integrity
check. The CLI emitted only a path-free error and no aggregate result, null
distribution, decision reference, p-value, `GO`, or `NO_GO`. The implementation
had calculated observed and baseline metrics in memory before the abort; no
metric value was emitted, inspected, or used to choose the correction.

The failure was a false binary-float mass mismatch. V2 is a separately
versioned freeze: it checks exact `1/(R*D)` mass with rational arithmetic,
requires complete R-stratum vector and replica preservation, materializes and
validates all clean/mild assignments before any metric, reuses the same
assignments, and uses `math.fsum` for model, majority, and confusion buckets.
The numerical accumulator can be decision-bearing at a floating-point tie and
is therefore disclosed rather than called a V1 patch. Source, split,
degradation, seeds, model features/smoothing, support gates, thresholds, and
nonclaims are unchanged.

V2 was frozen publicly at commit
`37157f1411a55ffd91b7327afaca8fc1080fa708` and then executed once with the
fixed archive and no override. The exact aggregate-report commitment is
recorded in the
[immutable V2 result record](MTAAC_KNOWN_SCRIPT_CONTROL_V2_RESULT_2026-07-28.md).
The result is **`NO_GO`**. Clean passed every decision-bearing gate. Mild passed support,
coverage, integrity, macro-F1, reference-delta, permutation-p, and movable
family gates, but `settlement_name` recall was 0.193553 against the frozen
minimum 0.35. No alternate seed, threshold, split, or protocol was tried.

The unchanged V2 method is therefore blocked from Indus transfer. Any V3 is
explicitly post-result and cannot treat the exposed V2 holdout as fresh
confirmation. A genuinely untouched source is required for binding
confirmation; the later ED3b safety audit does not satisfy that requirement.
Neither the V1 error nor V2 `NO_GO` is an Indus reading, translation,
decipherment, or prize claim.

### T6 — V3 ORACC prospective-validation source seal

**Recorded at:** 2026-07-28T23:10:00+09:00

**Safety-audit correction completed at:** 2026-07-28T23:54:05+09:00

The V2 failure was audited before any V3 implementation. The primary defect
for transfer is not only low settlement-name recall: V2 predicts only rows
whose target eligibility is selected from evaluator truth. That four-class
oracle is unavailable for an unknown script. V3 is therefore a separate joint
five-state task over every retained token:
`context_only`, `quantity`, `unit`, `person_name`, and `settlement_name`.
V2 source code, protocols, and results remain immutable.

The official CC0 ORACC ePSD2 Early Dynastic IIIb administrative JSON source is
now fixed before V3 model fitting. Eligibility requires the exact
Early Dynastic IIIb period, Administrative genre, and `lem` metadata
membership. Sixteen records whose contents were displayed while qualifying
the source schema are excluded through a fixed domain-separated
identifier-hash set. Their identifiers are not directly listed, but the
commitment is not claimed to conceal them from enumeration over the finite
public source. The resulting reserved source has 3,338 documents and 226,618
retained lemma tokens.
Its exact source identifiers have zero intersection with all 371 selected
members of the pinned MTAAC archive. Sequence-level lexical novelty remains a
separate pre-score validation diagnostic.

The four target projections are fixed from ORACC's official annotation
contracts: lowercase `n` for the operational conventional numeric/count-unit
state, noun guide word `unit` for metrological units, `PN` for person names,
and `SN` for settlement names. Spelled number words tagged `NU` and quarter
names tagged `QN` remain `context_only`; the quantity state does not claim to
cover every semantically numeric word. Per-class support is committed but not
published. Every class passes the predeclared minimum of 200 tokens and 100
supporting documents.

The first raw-GDL design was rejected before publication. Gold-conditioned
GDL-key rates showed that numeric-parser and determinative keys were
near-direct target proxies. The final observation projection consumes only
`f.gdl`, hashes approved `q/c/s/v` or audited numeric/modified `form` payloads
under one source-specific namespace, flattens approved wrappers, and emits
only neutral gap and damage markers. It drops numeric-parser, determinative,
delimiter, ID, modifier, span-ID, and related key identities. This remains
annotation-stripped scholarly transliteration, not a native-glyph observation
or secrecy mechanism.

Eight retained tokens across seven documents lack POS truth. They remain in
the observation sequence and require five-state predictions, but the evaluator
assigns fixed `annotation_unknown` truth and excludes them from metrics instead
of silently treating them as `context_only`. The exact source now has 226,610
scorable tokens.

The source-only verifier accepts only the exact official archive, validates
all archive paths, embedded CC0 declarations, catalogue/corpus identity,
strict JSON, line and lemma structure, the fixed exclusion, projection,
annotation-stripping observation contract, selected-member manifest,
effective-corpus digest, and support commitment. It emits an aggregate
allowlisted receipt and performs no model fit, prediction, metric, threshold
selection, or validation execution.

ORACC is a feature-safety-exposed prospective validation source, not binding
confirmation. Archive-wide and SumTablets-joined class counts, limited
examples, and gold-conditioned GDL-key rates were inspected before the seal
and informed the sanitizer. Those exposures cannot be undone. Candidate model
fitting, selection, tuning, debugging, and further feature design on ORACC are
prohibited. A public hash proves content identity rather than trusted time,
custody, or absence of access.

Binding confirmation must use a different, previously uninspected corpus.
Its selection cannot be project-side cherry-picking: either an independent
custodian reserves it before development, or a public random beacon chooses
from a predeclared ordered eligible pool after the complete model/evaluator
freeze, with terminal support failure or a predeclared fallback order.

**Source-qualification receipt recorded at:** 2026-07-29T00:07:52+09:00

The public source-freeze commit is
`2537dd099e708039c49d96598ad6b379eddeafd8`. After that commit was published,
the exact pinned archive was processed once through the no-replace
source-qualification entry point. The resulting aggregate receipt is
`benchmark/results/oracc-ed3b-validation-source-v1.json`: 4,695 bytes,
SHA-256
`bdcf01a1a04dee7f14b64b396de4240f40c8ab0826e19096f113e091b94c3bd3`.
It passed the closed receipt schema and public-boundary scan and returned
`source_qualified` for 3,338 documents, 226,618 retained tokens, 226,610
scorable tokens, eight `annotation_unknown` tokens, and all four support
gates. `model_executed` and `scientific_metrics_emitted` are both false. The
receipt contains no source-document identifiers, raw values, archive-member
paths, local paths, host/account data, private or operational network
addresses, or credentials.

### Data and source work

Safe next work:

- define a reviewed extra-bulk evidence contract for Penn field numbers and
  Mackay page references without copying plates;
- resolve or explicitly quarantine the SF 3051/2558 and SF 3495 conflicts;
- design V3 as explicit post-result work using train-side or separately
  declared development analyses, without rewriting V2;
- preserve the frozen ORACC source boundary while V3 is developed only on
  declared development data;
- add a separate context-bearing known-script stress test; MTAAC is a
  word-level transliteration control rather than a context or glyph control;
- curate public source/provenance/rights evidence;
- create the external 12-page KP1979 row reference and freeze the detector
  before using its withheld manual values;
- implement image-verified KP1979 identifier/code proposals and 1980
  revision/cross-reference/duplicate parsers with explicit abstention;
- build three-way KP1979 record reconciliation before sign classification;
- inventory KP1982 concordance page classes and implement source-bound,
  abstaining occurrence proposals after the KP1979/1980 record spine;
- specify the deterministic stratified calibration tranche separately from
  full Batch 0;
- specify a separate concordance-row reference, model-freeze point, and
  end-to-end release gates;
- implement edition-preserving corpus adapters using public or synthetic
  fixtures;
- preregister functional-anchor tests and kill criteria before examining
  results;
- prepare synthetic reviewer-record templates and a deterministic
  post-adjudication inventory-build receipt without executing or fabricating
  human review;
- improve parsers and validation using public or synthetic fixtures;
- strengthen leakage and null-model tests;
- document unresolved rights or provenance as unknown;
- prepare non-operational custodian and review specifications.

Not authorized by inference:

- publishing ignored or externally governed data;
- converting private material into a public corpus;
- filling unknown rights from filenames or public availability;
- creating a real hidden companion;
- contacting an institution or prize administrator;
- asserting a language, reading, translation, or decipherment.

## Public logging policy

Public documents may contain reproducible source facts, public upstream
revisions, public scientific results, software changes, and explicit
limitations. Keep the following outside Git:

- host or account identifiers and absolute personal paths;
- authentication mechanisms, key metadata, and connection details;
- local/private storage topology;
- private file and directory names;
- exact private counts, sizes, timestamps, or digests;
- private scan results and remediation logs; and
- internal browser, CI administration, or migration history.

If a detail is useful only to the operator of a particular machine, it is not a
public development-log entry.

## Source-level verification record — 2026-07-28

- Ruff lint and format check: passed.
- Pyright: passed with no errors or warnings.
- Primary filesystem profile: 436 tests run, 423 passed, and 13 optional or
  environment-specific tests skipped.
- Post-publication canonical profile at result commit
  `9c360c44033212402985e44a3b2d3fb3e7e3cf6d`: 436 tests run, 424 passed,
  and 12 environment-specific tests skipped. Ruff lint, format check, and
  Pyright also passed.
- Prior second filesystem profile, before the MTAAC addition: 378 tests run,
  366 passed, and 12 optional tests skipped. It exercised the additional
  Unicode-casefold-collision test.
- The 58 focused MTAAC parser, evaluator, statistics, CLI, and published-result
  tests passed.
  The frozen protocol bytes match the implementation's SHA-256 constant.
- The single V2 aggregate report is 313,140 bytes; its exact SHA-256 is recorded
  in the
  [immutable V2 result record](MTAAC_KNOWN_SCRIPT_CONTROL_V2_RESULT_2026-07-28.md).
  Independent aggregate-only checks reproduced all confusion-derived metrics,
  both 999-run null summaries, threshold criteria, and `NO_GO`. The report
  contains no raw row, P identifier, token/document key, member/local path,
  host, or account value.
- A separate exact-source KP1979 run exercised the fixed PDF and all 179
  canonical page images through its seven-test module: passed. This validates
  source and label-lattice gates, not manual label accuracy or row extraction.
- A separate owner-controlled exact-source run exercised the canonical page
  pixels and assignment through the relevant 35-test module: passed. No
  private path, inventory, or content value is recorded here.
- Source distribution and wheel build: passed.
- Markdown-link existence check: passed.
- Gitleaks current-tree and reachable-history scans: no finding.
- Semgrep: no finding in the complete tracked tree or the explicit new Python
  release candidates. The Python-before-3.7 compatibility rule is suppressed
  only at the seven affected `importlib.resources` lines because the package
  requires Python 3.11 or newer.
- Trivy filesystem scan: no high/critical dependency vulnerability, secret, or
  detected misconfiguration finding.

These checks and the project-run known-script control are not execution of a
human review, independent external replication, an Indus result, or a
decipherment result.

## MTAAC V3 development implementation — 2026-07-29T01:10:06+09:00

V3 is now implemented as a separate development-only package and command,
without changing the immutable V2 parser, evaluator, protocol, or result.
The exact machine-readable plan is
`benchmark/mtaac-v3-development-v1.json`. Its one-way gateway accepts only the
fixed MTAAC archive, rederives the fixed V2 split, and exposes clean and mild
views of the 271 training families. The 90-family V2 holdout is not exposed to
the model and is not scored.

The first V3 model jointly predicts `context_only`, `quantity`, `unit`,
`person_name`, and `settlement_name` for every retained token. Its fixed
source-neutral feature surface records sequence position, line shape, damage,
direction, and within-line equality patterns without exporting lexical
identity. Weighted categorical naive-Bayes emissions, unadjusted first-order
transition counts, and Viterbi decoding use `alpha = 1` and the exact
`gamma × lambda` grid `{0, 0.5, 1} × {0, 0.5, 1}`.

Candidate selection is family-disjoint nested five-outer/four-inner
cross-validation. Mild family-weighted macro-F1 is the only selection metric;
clean is an integrity diagnostic and cannot choose a candidate. A separate
domain-separated four-fold procedure selects the final development
configuration over all 271 development families. The report boundary permits
only aggregate support, fold metrics, confusion matrices, configuration
summaries, public parent commitments, and a final model-state commitment.

The isolated command verifies the plan before reading the archive, imports no
main command module, reserved-source module, or network client, writes a new
output only, and rechecks the complete public parent/data boundary before
serialization. The reserved prospective validation source remains unloaded.
This development run cannot use the V2 holdout, cannot produce a reserved
validation result, and cannot support an Indus reading or prize claim.

Verification at this checkpoint:

- Ruff lint and format check: passed;
- Pyright: zero errors and warnings;
- full suite: 511 tests passed, 13 environment-specific tests skipped;
- focused V3 suite: plan, gateway, folds, sequence model, metrics, runner,
  schema, command, and import-closure checks passed;
- a synthetic 271-family execution passed both the recursive public boundary
  and the closed report schema;
- wheel and source distribution contain the exact plan, report schema, V3
  modules, and independent command entry point;
- Gitleaks, Semgrep, and Trivy reported no finding; and
- all four frozen V2 file digests remain unchanged.

No real V3 development report existed at this checkpoint. The controlled next
step is to publish this code-and-plan freeze, execute the exact MTAAC archive
once at that published implementation commit, validate the aggregate report,
and publish the result in a separate commit. ORACC execution remains
prohibited until a later model/evaluator freeze.

## MTAAC V3 development result — 2026-07-29T01:19:40+09:00

The code-and-plan freeze was published at
`5b39c8ba358ea66e46183cbf02eb07fbc91861e2`. The exact MTAAC archive was then
processed once through the independent no-replace V3 command. The output is
`benchmark/results/mtaac-v3-development-v1.json`: 77,086 bytes, SHA-256
`e40d4802906dbe05b19a8625949f8c9154711a28a687c930d3e31cec2bf124d2`.
It passed the closed schema, recursive public-output boundary, aggregate
confusion recomputation, and one-standard-error selection recomputation.

All five outer folds and the separate final four-fold procedure selected
`gamma = 0.5, lambda = 0`. Mild out-of-fold macro-F1 is 0.3243, weighted
accuracy is 0.4895, balanced accuracy is 0.3619, and worst-state recall is
0.0369. The zero transition strength means the first-order sequence component
was not selected. Settlement-name and quantity recall remain too weak for this
feature surface to be considered an adequate transferable structural model.

The V2 holdout was neither model-visible nor scored. The reserved prospective
validation source was not loaded. This is an aggregate known-script
development result only; it supplies no Indus reading, translation,
decipherment, binding-confirmation, or prize evidence.

V3 is now immutable. The highest-value next experiment is a separately frozen
V4 that derives gold-free corpus-level frequency, dispersion, position, and
context-diversity features from opaque type equality, then tests a
discriminative sequence model under the same family-grouped boundary. Further
MTAAC reuse is method development rather than fresh held-out evidence.

## MTAAC V4 development implementation — 2026-07-29T02:34:17+09:00

V4 is implemented as a separate development-only package and command without
changing any V2 or V3 implementation, protocol, schema, or result byte. Its
exact machine-readable plan is `benchmark/mtaac-v4-development-v1.json`:
10,354 bytes, SHA-256
`604725a5929b63f578ade07b65ca784eefefefce9b827e1686d4836f668c123b`.
The one-way gateway accepts only the fixed 271-family MTAAC development
partition, reverifies exclusion of the 90-family V2 holdout, and does not load
the prospective validation source.

For every outer-fold side and clean/mild regime independently, the primary
profile treats the complete unlabeled side as a fixed target batch and removes
the current family's complete contribution before deriving type statistics.
The ten low-cardinality V3 local features are joined to 24 fixed frequency,
dispersion, position, context, neighbor, evidence, and interaction features.
Opaque form fingerprints are transient equality keys only. They, profile
maps, feature rows, family/fold membership, individual predictions, raw
annotations, and local paths cannot cross the aggregate report boundary.

There is one primary candidate and no inner selection: an L2-regularized
linear-chain CRF with a fixed family-weighted objective, Jeffreys-smoothed
class prior, post-training class adjustment, and dependency-free deterministic
full-batch L-BFGS. The optimizer fails closed on non-finite arithmetic,
unrecoverable non-descent, failed line search, or non-convergence. Finite
difference gradients, exact family weights, brute-force partition and Viterbi
comparisons, input-order invariance, real-profile compatibility, minimum-step
handling, and public-boundary rejection are covered by tests.

Independent pre-freeze review aligned the Armijo contract to 31 evaluated
steps, making the declared `2^-30` minimum step reachable without exceeding
the published trial count. The runtime command now applies the same closed
Draft 2020-12 report schema used by release checks, recomputes every metric
from its confusion matrix, reconstructs out-of-fold aggregates, and rechecks
paired deltas and every gate before any output can be written.

V4 reuses the exact five V3 outer family assignments for paired development
estimates. Local-only CRF, transition-zero decoding, independent logistic
emissions, self-inclusive target profiling, and strict single-family profiling
are predeclared nonselecting diagnostics. The fixed decision requires every
macro-F1, rare-state recall, paired-fold, profile-increment, clean-integrity,
and self-information gate to pass. Any other valid outcome is
`development_killed`; diagnostics cannot rescue it.

Verification at this checkpoint:

- Ruff lint and format check: passed;
- Pyright: zero errors and warnings;
- full suite: 569 tests passed and 13 environment-specific tests skipped;
- focused V4 suite: 54 plan, contract, profile, sequence, runner, schema,
  command, and architecture tests passed;
- the exact V2/V3 file digests and V3 parent commitments remain unchanged;
- source and wheel distributions contain the exact V4 plan, report schema,
  modules, and independent command entry point; and
- the local Markdown-link check passed; Gitleaks, Semgrep, and Trivy reported
  no finding.

No real V4 report exists at this checkpoint. The controlled next step is to
publish this code-and-plan freeze, execute the exact MTAAC command once at that
published implementation commit, validate the aggregate report, and publish
the result separately. A valid negative result ends this protocol. A valid
advance result permits only the specified all-development-family model fit and
still does not authorize prospective validation, binding confirmation, an
Indus reading, a prize submission, or institutional contact.

## MTAAC V4 development result — 2026-07-29T03:11:52+09:00

The code-and-plan freeze was published at
`304f8b36a32083330b8af02d21a58382c29d8915`. The exact fixed command then
completed once. Its 164,563-byte aggregate output is
`benchmark/results/mtaac-v4-development-v1.json`, SHA-256
`4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897`.
Every outer-fold CRF, local-only CRF, and independent logistic diagnostic
converged under the frozen optimizer contract.

Primary mild out-of-fold macro-F1 is 0.3878, compared with immutable V3's
0.3243. Every paired outer fold improved, and the full-profile primary exceeded
the local-only diagnostic by 0.0608 macro-F1. Transition-zero decoding scored
0.3443 and independent logistic emissions scored 0.3569, so both the profile
and fitted sequence component contributed within this reused known-script
development task. Self-inclusive profiling added only 0.0067 over LOFO, while
the strict single-family diagnostic fell to 0.2562; the method is explicitly
target-batch dependent.

The fixed decision nevertheless returned `development_killed`. Mild `unit`
recall was 0.3052 against its 0.3768 floor, and mild `settlement_name` recall
was 0.0429 against its 0.15 floor. All other gates passed, including mild
macro-F1, five-of-five positive paired deltas, profile increment, clean
integrity, the other recall floors, and self-information sensitivity. Because
every gate was mandatory, diagnostics cannot rescue the result. The all-271
final development model was not fitted and has no model-state commitment.

The closed runtime and release schema, recursive public boundary, every
confusion-derived metric, summed out-of-fold confusion, paired V3 comparison,
and gate decision recomputed exactly. The report contains no item identifier,
feature row, family/fold membership, raw annotation, local path, account,
network address, or prospective-source result.

The V2 holdout and prospective validation source remained unloaded and
unscored. V4 cannot execute that source. Its improvement is useful
known-script method evidence but does not establish transfer, an Indus
reading, translation, decipherment, binding confirmation, or prize evidence.

If MTAAC is used once more, the highest-information final attempt is a
separately frozen V5 with no new parameter capacity. V4 features, LOFO
target-batch profiling, sequence structure, optimizer, class adjustment,
parameter count, and five outer folds should remain fixed. Change only the
emission regularizer for the `quantity`/`unit` and `person`/`settlement`
pairs, including their biases. For each pair define
`mu = (beta_a + beta_b) / 2` and `kappa = (beta_a - beta_b) / 2`, preserve
V4's common-direction penalty, and use the single fixed pair penalty
`rho * (||mu||^2 + 2 * ||kappa||^2)` at `rho = 0.01`. Context emissions,
start weights, and transition weights retain V4's ordinary
`rho / 2 * ||beta||^2` penalty. This orthogonal group-contrast contract has
the same five-state parameter count, is identifiable, and contains no
pooling-weight search; a naive shared-plus-residual decomposition is
prohibited.

Rare-state precision must not regress from V4 while unit and settlement
recall meet the existing floors. V5 must also require material mild macro-F1
improvement and consistent fold-level rare-state gains, rather than accepting
a pure class-tradeoff. It must declare in advance that MTAAC is retired after
that one result regardless of outcome. A V5 failure ends this feature/model
family; a V5 pass still requires a separate prospective evaluator freeze and
is not fresh evidence.

Post-result publication validation passed Ruff, formatting, Pyright, all 573
tests with 13 environment-specific skips, source and wheel builds, local
Markdown links, the runtime/schema result verifier, Gitleaks, Semgrep, Trivy,
and a dedicated scan for deployment identifiers.

## Final MTAAC V5 code-and-plan freeze — 2026-07-29T04:00:00+09:00

The V4 result showed real overall and paired improvement but failed the mild
`unit` and `settlement_name` recall gates. Its aggregate confusion indicates
that missed units flow mainly to `context_only`, while missed settlements flow
almost entirely to `context_only` or `person_name`. V5 therefore tests one
narrow, result-adaptive hypothesis and then retires MTAAC.

The exact 15,268-byte plan is
`benchmark/mtaac-v5-development-v1.json`, SHA-256
`3c4a7c733218fcd0c4e6e25fbd59e5b86c1fd589512e9a88bb243b1d036c10f1`.
It binds the V4 code freeze, result commit, result SHA, aggregate precision and
recall baselines, and all five fold-by-fold comparison vectors.

V5 retains V4's data boundary, observations, 10 local and 24 LOFO profile
features, five-state parameter layout, family-weighted conditional
likelihood, class adjustment, exact outer folds, zero initialization, and
deterministic L-BFGS. For every emission coefficient and bias in the
`quantity`/`unit` and `person_name`/`settlement_name` pairs, it writes
`mu = (beta_a + beta_b) / 2` and
`kappa = (beta_a - beta_b) / 2`, then applies
`rho * (mu^2 + 2 * kappa^2)` at `rho = 0.01`. Context, start, and transition
parameters retain V4's ordinary L2 penalty. The parameter count and
representable score family are unchanged; the inductive bias changes. The
contrast multiplier is fixed at 2 and has no runtime API. No grouping, weight,
class-offset, diagnostic, V4-refit, or fallback choice exists.

The 15 mandatory checks cover mild macro-F1, all five recall floors, rare-state
precision non-regression, clean macro-F1 and settlement integrity, positive
V5-minus-V4 fold deltas for macro-F1/unit/settlement in at least four of five
folds, positive settlement recall in all folds, and the V4 worst-fold unit
recall floor. Minimum comparisons and strict positive comparisons use the
predeclared `1e-12` rule.

The closed Draft 2020-12 report schema and runtime validator reject unknown
fields and all item, membership, path, host, account, annotation, and
prospective-source detail. The validator recalculates each fold metric from
its 5-by-5 confusion, sums fold confusions before deriving OOF metrics,
rebuilds all three V4-paired vectors and counts, verifies fold support and
family-mass partitions, and recalculates every gate and terminal state.
Optimizer summaries and profile commitments are closed attestations because
an aggregate-only report intentionally cannot reconstruct their private
inputs.

A complete runtime- and schema-valid report is the single valid result. A
pre-report environmental or I/O failure may retry only byte-identical code,
plan, archive, and arguments before any metric is emitted. Any changed
condition or exposed partial metric retires V5/MTAAC without another attempt.
A valid failed report is `mtaac_retired` with no final model. A valid pass is
`advance_to_prospective_freeze`, fits only the final development model, and
also retires MTAAC. A pass still authorizes no prospective execution until a
separate evaluator freeze.

Independent mathematical, contract, runner, CLI, and adversarial reviews found
no execution blocker. At this checkpoint no real V5 result exists, and V5 has
not executed MTAAC, the V2 holdout, or the prospective source.

The final pre-publication audit passed all 39 focused V5 tests and all 612
repository tests (599 passed and 13 environment-specific tests skipped),
Ruff, formatting, Pyright, Draft 2020-12 meta-schema and runtime plan
validation, 131 local Markdown links, fresh source and wheel builds, isolated
wheel installation and CLI/resource checks, Gitleaks, Semgrep, Trivy, and a
dedicated deployment-identifier and private-path scan.

## Final MTAAC V5 execution completed — 2026-07-29T04:23:53+09:00

The public code-and-plan freeze is implementation commit
`b0be18d7c317d276dfefd1237c17ec0be6886cd0`. The exact V5 command completed
once against the pinned archive. The output and captured standard output were
byte-identical. The 59,053-byte aggregate result is
`benchmark/results/mtaac-v5-development-v1.json`, SHA-256
`9b60b9eb6006efc35cdca90e91fdb07c356a09becc2a1d300ef22ec16393e88f`.

V5 mild out-of-fold macro-F1 is 0.3845528260, below both V4's 0.3877588814
and the fixed 0.3977588814 gate. Only one of five fold deltas is positive.
Mild `unit` recall is 0.2936901059, below V4's 0.3052156741 and the fixed
0.3767836311 floor; none of five fold deltas is positive, and the worst fold
is 0.1684979017. Mild `settlement_name` recall improves from 0.0429419136 to
0.0574655518, with three positive fold deltas, but remains below the 0.15
floor. Unit precision also regresses from 0.3512887015 to 0.3462416049.

Seven of the 15 mandatory gates pass and eight fail. The clean macro-F1 and
clean settlement checks pass, as do context, quantity, and person recall,
settlement precision, and positive settlement recall in all five folds. The
aggregate, unit, settlement-floor, paired-consistency, and worst-fold unit
requirements do not all pass.

The report is closed-schema and runtime valid. Its terminal status is
`mtaac_retired`; the final all-development-family model is not fitted. The V2
holdout and prospective source remain unscored. The stronger fixed pair
contrast shrinkage produced a small settlement gain but did not solve the rare
state problem and harmed unit and aggregate performance. The frozen test does
not support the narrow V5 development hypothesis; it is not evidence against
every possible linguistic or structural account of the Indus script.

MTAAC development is now permanently retired by the predeclared stopping
rule. Do not rerun, retune, repair, or replace V5 and do not create V6. Any
future model claim requires a separately preregistered task and genuinely
independent evidence rather than another adaptive use of MTAAC.

Post-result publication validation passed all 44 focused V5 tests and all 617
repository tests (604 passed and 13 environment-specific tests skipped),
Ruff, formatting, Pyright, closed-schema/runtime validation, independent
confusion/metric/gate recomputation, 135 local Markdown links, fresh source
and wheel builds, isolated wheel installation and resource checks, Gitleaks,
Semgrep, Trivy, and dedicated public-boundary and deployment-identifier scans.

## KP1979 base-row review spine and global evidence refresh — 2026-07-29T11:40:26+09:00

MTAAC remains permanently retired. The next information-gain audit selected
the official Helsinki 1979/1980 record spine instead of another model run.
The fixed KP1979 PDF and all 179 canonical native PBMs were installed in the
canonical owner-only source store and passed the existing exact-source,
per-page pixel, negative-control, and layout gates. The fixed KP1980 PDF was
also installed there. Its 98 Poppler PBMs are retained only as an owner-only
extraction candidate; they are not yet a public canonical page-map contract.
Transfer staging was removed after hash and permission checks.

The original KP1979 exact container remains 16,935,356 bytes with SHA-256
`e6f9dec7cf98d2ee6130f068e60ab37021808dd63953de41f92ce457b35a4bfa`.
The current HeldA endpoint was observed returning container variants with
different object numbers, xref data, trailer IDs, sizes, and raw hashes across
requests. Independent Poppler and MuPDF checks found all 179 embedded images,
all decoded canonical PBMs, all 180 rendered pages, and extracted text
identical to the fixed snapshot. The exact V1 container and page map were
therefore not replaced. One observed current variant is retained in
owner-only quarantine. A future delivery-variant verifier must require all
fixed per-page PBM commitments and must never auto-allowlist an unfamiliar
raw PDF hash.

This checkpoint implements:

- `schemas/kp1979-row-assignment.schema.json`, a closed private proposal-only
  assignment whose 57 selected page commitments are fixed exactly;
- `src/indusbench/kp1979_row_assignment.py`, which repeats the complete
  179-page audit, re-reads PDF pages 22–78, rejects oversized input before
  hashing, creates stable visual slot locators, and commits canonical label
  and wider row-context crops;
- `prepare-kp1979-row-assignment`, with physical input-directory checks and
  private owner-only, atomic, no-replace output;
- `verify-kp1979-row-assignment`, which independently rebuilds the manifest
  from the exact PDF and PBMs and requires canonical byte equality; and
- synthetic, malformed/deep-JSON, forbidden-answer-field, schema-boundary,
  private-I/O, symlink, overwrite, durability, tamper, and fixed-real-source
  tests.

The assignment contains no OCR, printed identifier, lower code, sign value,
occupancy decision, reading direction, language, meaning, translation, or
external manual label. Candidate counts and private values are not printed.
The row rectangles are review aids only: no label or row geometry is accepted,
no human or independent review is complete, no record is admitted, and no
decipherment or prize evidence exists. JSON Schema validation alone is not an
attestation; the pixel-recomputing canonical verifier is mandatory.

The dated global evidence refresh adds three operational conclusions:

- the 2025 iCEL paper describes its contextual three-dimensional database as
  under construction, and no released dataset, manifest, API, coverage list,
  or reusable geometry licence was verified as of 2026-07-29;
- the official ASI/NMMA seals-and-sealings catalogue contains 413
  site-origin candidates across Harappa, Mohenjo-daro, Desalpur, and Surkotada,
  but they are not 413 confirmed inscribed objects and the public candidate
  lane is limited to official IDs plus official landing URLs; and
- the Tamil Nadu one-million-US-dollar announcement is authentic, but an
  operational submission scheme, rules, deadline, judging process, and
  submission address remain unverified. No submission is authorized.

Pre-publication validation at this checkpoint passed:

- the fixed-real-source build and canonical verifier;
- all 632 repository tests, with 14 environment-specific tests skipped;
- Ruff lint and formatting plus Pyright with zero errors or warnings;
- Draft 2020-12 schema validation and exact 57-page commitment
  reconciliation;
- 151 local Markdown links;
- fresh source and wheel builds plus isolated wheel installation, CLI, and
  packaged-schema checks;
- Gitleaks, Semgrep, and Trivy with no finding; and
- independent CLI/security, core/schema, scientific-claim, rights, secret,
  deployment-identifier, and public-boundary reviews.

The next controlled work is:

1. create the external manual reference and independent review contracts for
   the fixed 12-page KP1979 protocol without exposing values to the detector;
2. use the private 57-page assignment for image-verified identifier and lower
   code review, preserving abstentions and disagreements;
3. reconcile accepted source-local records against the two KP1979 sorted
   renderings without using sign sequences as join keys;
4. implement the KP1980 exact source/page contract and versioned
   correction/cross-reference/duplicate parsers; and
5. build only an ID-and-official-URL NMMA candidate index unless a separate
   metadata or image reuse basis is established.

Do not rerun MTAAC, V2 holdout, V5, or the reserved prospective source. Do not
contact an institution or attempt a prize submission without new explicit
authority and a verified operational route.

### Post-implementation fixed-source CLI verification

Implementation commit `fcd5749c43896bfff1431e301d3df1b8e846570e` was verified
without changing canonical `main`. The real
`prepare-kp1979-row-assignment` command completed against the fixed PDF and all
179 canonical PBMs. The output passed the owner-only directory, mode,
link-count, no-value, no-count, canonical-byte, and scientific-nonclaim
assertions. The real
`verify-kp1979-row-assignment` command then independently repeated the
179-page audit, re-read pages 22–78, rebuilt the manifest from pixels, and
passed exact canonical equality.

No private assignment, fixed source, source path, or storage inventory is a
public corpus artifact or part of the tracked tree.

## KP1979 proposal-free label-reference checkpoint — 2026-07-29T15:37:05+09:00

The first controlled item from the preceding checkpoint is now implemented.
The 57-page row assignment remains only a detector proposal and is not valid
input for establishing its own reference labels. To break that circularity,
the new reference workflow starts from fixed source pixels and opaque slots,
with detector output, proposal geometry, OCR, prior manual values, page roles,
and scoring expectations absent from the assignment.

This checkpoint adds:

- separate answer-free assignments for the fixed `development` and
  `future_evaluation` partitions;
- closed assignment and review schemas plus canonical builders and verifiers;
- exact source-PDF, page-map, PBM-byte, pixel, assignment, crop, roster, lane,
  authorship-declaration, and access-declaration checks;
- owner-only, no-replace private I/O with descriptor-relative reads,
  symlink/hard-link/FIFO rejection, bounded input, ancestry pinning, and
  mutation detection; and
- fixed count-, value-, identity-, digest-, and path-free command summaries.

The review contract admits `complete_no_targets`, `complete_with_targets`, or
`unresolved` for every page and lane. A target is the complete visible
two-tier row-label block, including attached punctuation or qualifiers, but
not sign drawings, damage hatching, baselines, headings, prose, sign-list
cells, or auxiliary-grid identifiers. The downstream matching rule is frozen
as same-page and same-lane, anchor-in-interval, maximum-cardinality,
order-preserving one-to-one matching; ties among maximum solutions are
ambiguous and receive no score. Unresolved records also receive no score, and
negative pages remain a separate empty-prediction gate.

Both partitions were generated from the fixed source snapshot in isolated
owner-only storage and independently rebuilt from the same canonical pixels.
Preparation and verification passed for each partition. No review record,
manual target value, identifier, lower code, sign sequence, reading
direction, detector comparison, or adjudication was created by that run.

Schema validity and recorded declarations do not prove human authorship,
independence, blinding, nonexposure, custody, or evaluation admissibility.
No human review has started; no reference geometry or source-local value has
been accepted; no detector or scorer has been frozen; and no decipherment or
prize result exists.

Validation passed all 29 focused label-reference tests on both supported
POSIX environments, including an explicit group-writable-source rejection,
and all 661 repository tests with 14 environment-specific skips. Ruff,
formatting, and Pyright passed; 152 local Markdown links resolved; fresh
source and wheel builds plus isolated wheel installation, CLI, and packaged
schema checks passed; and Gitleaks, Semgrep, Trivy, publication-boundary, and
independent scientific/security reviews reported no finding.

The next controlled work is:

1. prepare reviewer-only packets that omit detector proposals and scoring
   details, then obtain two genuinely separate human passes under an
   independent custodian;
2. compare the passes without inventing agreement, preserve abstentions and
   unresolved cases, adjudicate disagreements, and freeze the accepted
   development reference before any detector scoring;
3. freeze the detector and scorer, then perform the future-evaluation
   partition exactly once under the declared rules;
4. proceed separately with image-verified identifier and lower-code review
   for the 57-page assignment; and
5. implement the KP1980 exact source/page contract and its versioned
   correction, cross-reference, and duplicate parsers.

Do not use the 57-page proposals to create reference answers. Do not rerun
MTAAC, the V2 holdout, V5, or the reserved prospective source. Do not contact
an institution or attempt a prize submission without new explicit authority
and a verified operational route.

## KP1979 AI-only provisional extraction checkpoint — 2026-07-29

Human reviewers are not a prerequisite for continuing the provisional
machine-assisted extraction work. The development workflow now has a distinct
`machine_development_pass` whose declared evidence use is limited to exposed,
provisional extraction. Two genuinely separate human passes remain useful for
later external-reference promotion, publication confidence, or a prize-facing
claim, but their absence does not stop AI-based engineering, falsification, or
source-pixel verification.

The deterministic projection now follows continuous target-facing ink across
the fixed scan-band edge until a bounded terminus inside the physical lane is
found. A detached exterior run joined only across a short gap remains visible
evidence but marks the observation `boundary_ambiguous`. The 320-by-128 target
limit remains fail-closed. Nearby sign-facing continuation is excluded from the
crop, and vertically clipped associations are also unresolved. An observed
target requires a substantial blank vertical split with active row-projection
support on both sides; insufficient two-tier evidence records
`missing_label_tier`. A large internal horizontal gap by itself does not
invalidate otherwise eligible two-tier evidence.

Synthetic regressions cover target-side crossing, sign-side continuation,
detached exterior ink, unrelated exterior ink, vertical clipping, false
multi-run tier evidence, a missing projection run, and eligible two-tier
evidence with a large internal gap. The public label-reference, CLI, scorer,
synthetic-control, schema, and publication-boundary tests pass, as do
formatting, lint, and static type checks. Private-data execution results remain
outside the tracked public log.

The machine result remains ineligible as a human reference and cannot enter
the label-position scorer. The synthetic control remains `not_qualified`;
these changes improve extraction correctness but do not establish a reading,
language, meaning, translation, decipherment, evaluation admissibility, or
prize eligibility.

The current next work is:

1. assign a new KP1979 detector algorithm identifier rather than retuning V1
   under its old identity;
2. freeze a separately generated synthetic control before inspecting the new
   detector's result, treating the exposed V1 cases only as regressions; and
3. only after those gates, create the 57-page machine-authored provisional
   extraction while preserving uncertainty and all scientific nonclaims.

Human passes remain optional for this AI development sequence. They become a
gate only if the project later seeks to promote geometry as externally grounded
reference evidence or to report performance against such evidence.
