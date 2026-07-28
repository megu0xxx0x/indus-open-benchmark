# Public development plan and status

**Status date:** 2026-07-28

**Last source-level update:** 2026-07-28 21:56 JST (Asia/Tokyo)

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
