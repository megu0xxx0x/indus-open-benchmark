# Public development plan and status

**Status date:** 2026-08-01

**Last source-level update:** 2026-08-01

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
- The static source-reported-link policy, nonretroactive source
  registration/rights contract, four evidence-artifact schemas, and protected
  ephemeral custody/deletion contract are frozen. No dynamic revision receipt,
  authority proof, protected source byte, custody workspace, runtime
  bootstrap/parser/evaluator, observation, result, or admitted join exists.
  State remains `contract_blocked`, authorization is `not_authorized`, and
  execution is `not_executed`.
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
| Source-reported-link decision policy | static and frozen; six parent-row slots; not a runtime result |
| Source evidence, custody, rights, and execution | static policy, registration/rights contract, four evidence schemas, and protected-ephemeral custody/deletion contract frozen; dynamic receipts, authority proof, bootstrap/trust roots, strict runtime verifier/parser/evaluator, source access, and execution absent and blocked |
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

## KP1979 V2 qualification executed and published — 2026-07-30

The public
[V2 qualification protocol](KP1979_LABEL_LATTICE_V2_QUALIFICATION_PROTOCOL_2026-07-30.md)
and machine-readable execution plan fixed the result interpretation before the
combined control-detector run. The exact frozen command has now completed once,
and its
[machine-readable result](../benchmark/results/kp1979-label-lattice-v2-result-v1.json)
is published.

The raw synthetic control is `not_qualified`: 18 of 19 cases passed. The sole
failure, `positive_bounded_jitter_with_gaps`, was an abstention with zero
precision and zero recall against 68 synthetic references. All three
metamorphic checks passed. The process and transport boundary recorded 25
successfully started child processes for 25 adapter invocations, 21 accepted
responses, four proper out-of-contract rejections, and zero transport failures.

The detector branch was frozen before the separately developed control branch,
contrary to the required control-before-detector order. Independently of the
raw control failure, the overall terminal status is therefore `not_qualified`
and advance is false.

A post-freeze adversarial periodic two-tier non-label confound is also a
deployment block. It does not modify either frozen parent or the raw-control
gates, but it prevents V2 from being promoted for reference, real-source,
provisional-extraction, future-evaluation, accuracy, decipherment, or prize
use.

The execution used no detector-control preflight and started the required 25
fresh child processes for 19 fixed cases and three two-call metamorphic
relations. It checked the actual started-process count, used answer-free worker
requests, failed closed on transport or response errors, wrote the attempt
marker before the first call, and published the result atomically without
replacement. No retry is allowed after a control invocation. Local attempt
state does not technically prevent its owner from deleting that state, so
technical single-execution enforcement is not claimed.

Git verifies exact bytes and ancestry only. Mutual nonexposure and process
separation are declarations; confidentiality, blindness, custody,
independence, organizational independence, cross-access absence, filesystem
or network isolation, trusted time, and independent public-remote attestation
remain unverified.

The V2 execution reads synthetic PBMs only. It does not open the real source,
future-evaluation values or pixels, PDF page 78, the 57-page proposal
assignment, the MTAAC holdout, ORACC prospective material, or another reserved
source. It validates no identifier, code, row identity, sign sequence, reading
direction, language, meaning, translation, decipherment, or prize claim.

V2 is now retired and immutable. It must not be rerun, retuned, repaired, or
used for extraction. The controlled next step is to create and publish an
independent synthetic control for a new V3 algorithm identity before
implementing the V3 detector. The successor must treat V2 only as exposed
development evidence and must include the known periodic confound and broader
non-label families. No V3 implementation exists at this checkpoint.

## KP1979 V3 pre-detector control infrastructure — 2026-07-30

The reusable
[freeze core](../.github/workflows/kp1979-v3-freeze-core.yml) was published as
P0 at commit `6eebc904a1bee3eaa05be619796cc6336bb2d10e`; its exact workflow
SHA-256 is
`9bd93bed5359bd8cb396a0f6be063b5bc6f76ad1b84e1d6338e1edc14ae0300a`.
The pinned
[manual caller](../.github/workflows/kp1979-v3-freeze.yml) was published as P1
at commit `b530d1a2068135807f96dfe63ddbaf484b1acbb2`; its exact workflow
SHA-256 is
`aca066fc5df3565af831669b28ab661482dc0a21f319f6759fd912365c3f3442`.
For Python 3.11, 3.13, and 3.14, every P0 CI job passed 753 tests and every P1
CI job passed 758 tests. Neither workflow has been dispatched for a freeze,
and no V3 attestation exists.

The answer-free
[V3 protocol](../src/indusbench/kp1979_v3_protocol.py) fixes control identity
`kp1979-label-lattice-synthetic-control-v3`, algorithm identity
`two-column-glyph-lattice-v3`, and worker identity
`kp1979-label-detector-v3-worker-v1`. Its ordered roster contains 12 positive,
14 negative, and six out-of-contract cases. Eight two-endpoint metamorphic
relations make the closed execution total 48 fresh worker invocations.

The current pre-detector source candidate adds an audited bounded canvas,
domain-separated deterministic PRF, mutually independent orthogonal-graph and
bitmap-mask renderers, and a fail-closed
[systemd/Landlock sandbox](../src/indusbench/kp1979_v3_sandbox.py). The sandbox
uses a bootstrap-owned separate handshake, seccomp restrictions, descriptor
closure, and bounded resources. This is defense-in-depth process isolation,
not a virtual machine. The root operating system, user manager, and trusted
parent process remain in the trust base.

No V3 detector, case generator, evaluator, target Quicknet round, C3 artifact
or result, real-source access, decipherment, or prize claim exists at this
checkpoint. A future C3 pass may authorize only owner-only provisional
candidates for pages 22 through 77. It cannot authorize page 78, public
release, accuracy, identifier, sequence, language, meaning, translation,
decipherment, prize, or corpus claims.

The controlled next sequence is:

1. wire the closed protocol, case generators, evaluator, and audited
   primitives while preserving the answer-free worker boundary;
2. integrate an offline Quicknet verifier and deterministic C3 freeze builder;
3. publish the complete C3 source, then select an exact Quicknet target round
   at least eight days ahead and attest C3 at least seven days before that
   round; and
4. begin detector implementation only after the control is publicly frozen
   and attested.

## KP1979 V3 Quicknet verification dependency — 2026-07-30

An offline verifier is specified as a pre-C3 qualification dependency. This
checkpoint makes no claim that C3 is frozen or executed. Normal public Git
history records the integrated bytes without a separate release assertion in
this section.

The component fixes the public Quicknet chain identity and the already-public
past round 1000 qualification vector. It accepts externally supplied round,
signature, and randomness values, requires canonical lossless input, checks
`randomness = SHA256(signature)`, computes
`SHA256(uint64be(round))`, and verifies the RFC 9380 BLS signature with the
fixed G1-signature/G2-public-key scheme and DST. Infinity, non-subgroup,
malformed, non-canonical, wrong-chain, wrong-key, wrong-schedule,
wrong-randomness, and wrong-signature inputs fail closed.

The exact minimal CommonJS closure contains 18 MIT-licensed upstream files from
`@noble/curves@1.9.7` and `@noble/hashes@1.8.0`, plus a canonical provenance
manifest and the verifier. Per-file hashes, npm tarball hashes and SRI, source
commits, signed-tag observations, licenses, and the only exact upstream
trailing-whitespace exception are fixed. Runtime checks the exact 20-file
inventory and fetches or installs nothing.

Portable BLS semantics are now mandatory in each main CI Python matrix job
under exact Node 24.18.0, provisioned by full-SHA-pinned
`actions/setup-node@v6.5.0` with package-manager caching disabled. The CI job
asserts the version and runs the six-test known/adversarial Node suite with no
skip path. The Python wrapper remains a separate legacy host qualification:
it checks root-owned Node 18.19.1 and util-linux `prlimit` 2.39.3 launcher
bytes and versions, uses a minimal environment and no shell, and applies
address-space, core, CPU, output-size, file-descriptor, and wall-time bounds
without Python `preexec_fn`.

Focused evidence at this checkpoint includes 13 Python tests, six portable
Node tests, one current-host CLI bound test, the round-1000 verification under
official Node 24.18.0 with zero skips, and compatibility under a private
network namespace. Fresh wheel and sdist trials contained the exact 20-file
vendor inventory and an isolated wheel installation verified the manifest and
round-1000 vector. The integrated state must repeat repository-wide and
package checks and pass public CI; focused evidence does not pre-attest that
future CI state.

The launcher digests do not attest dynamic `libnode`, OpenSSL, glibc, the
kernel, or the complete operating-system closure. Those root-owned components
remain an explicit trusted host base. Node 18 is end-of-life and is
qualification-only. The wrapper does not itself create a kernel network
namespace, and same-UID concurrent replacement between checking and use remains
outside the threat model. Provenance signatures and attestations are audit-time
observations, not live offline revalidation.

No future target or round is selected, reserved, fetched, or disclosed. The
component supplies no trusted time, custody, freshness, external attestation,
identifier, sequence, language, meaning, translation, decipherment, accuracy,
or prize claim. A returned Python object is not an unforgeable receipt.

## KP1979 V3 Quicknet CI and worker-wire checkpoint — 2026-07-30

The Quicknet dependency was published at commit
`af9e757087505137a4b9d17d1e7ae4811b63432d`. Public CI run `30519982857`
passed Python 3.11, 3.13, and 3.14 with 845 tests and 22
environment-specific skips in every matrix job and built both source and wheel
distributions. An earlier run's only failure was a test-reporter prefix that
varied between Node 18 and Node 24; the portable BLS semantic step already
passed in every job. The corrective commit fixed the reporter explicitly and
did not change production-verifier or vendored-cryptography bytes.

The answer-free
[worker wire](../src/indusbench/kp1979_v3_wire.py) was published at commit
`f79e437`, with permanent boundary additions at `cef6299`. A request contains
only the exact worker interface version, raw-P4 bytes, public width and height,
and scan bands. It cannot carry a case identity, expected answer, truth, seed,
relation identity, or generator metadata.

The outer boundary admits the six predeclared semantically invalid fixtures so
that each reaches exactly one sandbox invocation. Worker rejection applies the
fixed precedence header, dimensions, payload size, then scan bands. Responses
use only `proposed`, `abstained`, or `rejected`; predictions are sorted,
unique, lane-bounded, page-bounded, and at most 128 pixels high. The future
scientific evaluator must still require the intended exact height of 96
pixels. Deep JSON and pathological numeric values fail with one generic error
that discloses neither path nor parser detail.

Independent adversarial review, including permanent compound-precedence and
request/response huge-number tests, reported zero blocker and zero major
findings. Public CI run `30522383744` then passed Python 3.11, 3.13, and 3.14.
Each matrix job passed all 871 tests with 22 environment-specific skips,
passed the six mandatory Quicknet BLS tests with zero failures, and built both
source and wheel distributions.

This checkpoint still creates no accepted trial-state component, generator,
evaluator, freeze artifact, target Quicknet round, detector, C3 result,
real-source result, decipherment evidence, or prize evidence.

## KP1979 V3 one-shot trial state — 2026-07-30

The hardened
[one-shot state layer](../src/indusbench/kp1979_v3_state.py) was integrated at
commit `bb01fe6`. Its two canonical record forms contain only a format version
and closed state value. Experiment identities, request commitments, seeds,
oracles, worker outputs, scores, exception details, and result payloads are
outside this layer.

Non-consuming preflight occurs before the attempt is consumed. Immediately
before a worker can start, the state layer verifies real no-replace rename
semantics on the selected filesystem in both existing-target and absent-target
cases, safely removes and syncs its probes, creates and syncs the `started`
record without replacement, and revalidates its pinned directory ancestry.
After `started`, a crash is `consumed_incomplete`, technical failure is
`execution_failed`, and a completed evaluator may publish only `qualified` or
`not_qualified`. No retry, reset, delete, or force API exists.

Every ancestor descriptor remains pinned through close. Namespace links,
device/inode and ownership/mode fingerprints, effective identity, and
detectable ACL attributes are rechecked. Intermediate components must be safe
root/effective-user directories, except that a root-owned sticky writable
boundary is permitted; the final directory must be effective-user-owned mode
0700. Linux and Darwin are the only accepted platform families. Unsupported
or unverifiable behavior fails before worker execution.

Independent adversarial review reported zero blocker and zero major findings.
The single minor finding is the absence of a permanent Darwin CI job, although
the Darwin ACL and exclusive-rename paths received an independent live check.
The focused state suite passed 55 tests; its implementation branch passed all
886 tests with 19 environment-specific skips. The integrated source passed
Ruff, formatting, Pyright, source and wheel builds, Gitleaks, and the dedicated
public-boundary scan before publication.

These records provide owner-controlled local fail-closed durability only.
They do not prevent the owner, root, or the filesystem from deleting,
replacing, or rolling back the directory and therefore do not prove trusted
time, non-deletion, independent custody, tamper resistance, organizational
independence, or technical single execution against those actors.

No C3 attempt marker or terminal record has been created. This checkpoint
executes no worker and establishes no generator, evaluator, freeze artifact,
target round, detector, C3 result, real-source result, decipherment evidence,
or prize evidence.

## KP1979 V3 deterministic generator checkpoint — 2026-07-31

The preceding one-shot state integration was confirmed by public CI run
`30524604595`. Python 3.11, 3.13, and 3.14 each completed 926 tests with 22
environment-specific skips and built both source and wheel distributions.

The synthetic-only deterministic
[generator](../src/indusbench/kp1979_v3_generator.py) was published at commit
`88794f9748e909eef66f54c4c56d82fee5e9e521`. It implements all 12 positive,
14 negative, and six out-of-contract cases and all eight two-endpoint
metamorphic relations fixed by the protocol. The closed controller schedule
therefore contains exactly 48 worker invocations.

Every generated case and relation is authoritatively checked against exact
canonical regeneration under the supplied suite seed. This seed-bound
boundary rejects wrong-seed objects, cross-recipe substitutions, retagged
construction metadata, relation substitutions, and commitment changes.
Low-level structural certificate validation is not an authoritative
acceptance boundary.

The suite seed, generated objects, full construction and truth metadata,
generation commitments, and schedule metadata are controller-only. Once
instantiated, they must not be persisted or published before execution and
must never be passed to a worker. A worker may receive only `request_bytes`
satisfying the exact five-field answer-free wire contract.

Independent read-only QA reported zero blockers, zero major findings, and zero
minor findings. The local integrated-source profile passed 99 focused
generator/state/wire tests and all 947 repository tests with 19
environment-specific skips, plus Ruff, formatting, Pyright, both distribution
builds, Gitleaks, and public-boundary checks. Public CI run `30599459365`
passed all 947 tests with 22 environment-specific skips on Python 3.11, 3.13,
and 3.14 and built both distributions in every matrix job.

This generator checkpoint did not implement an evaluator and was not a C3
freeze or run. No target Quicknet round had been selected. No detector,
real-source access or result, decipherment evidence, or prize evidence existed
at that checkpoint. KP1979 V2 remains immutable.

## KP1979 V3 streaming evaluator checkpoint — 2026-07-31

The streaming, aggregate-only
[evaluator](../src/indusbench/kp1979_v3_evaluator.py) is implemented at commit
`ee847035867fe92dbca8b3e0aa9422dcfd43f138`. It constructs and authoritatively
validates one generator object at a time
against exact same-seed canonical regeneration. It does not import or
materialize the controller schedule. For all 32 cases and 16 relation
endpoints, it passes only `request_bytes` to the supplied invoker. Generated
objects, truth, responses, request digests, and schedule meaning remain
ephemeral and absent from the result.

Positive cases require exact `proposed` responses, 96-pixel height for every
prediction, and sorted same-lane one-to-one matching whose prediction anchor
lies in the corresponding half-open truth interval. Complete coverage is
mandatory, so both false positives and false negatives are zero. Negative
cases require exact `abstained`. Each out-of-contract case requires
`rejected` with its predeclared error code. Both endpoints of every relation
must first pass the positive gate; the evaluator then checks the five exact
invariant relations, vertical translation by 11 pixels, lane swap, and
deletion of exactly the matched omitted witness.

A valid scientific failure does not short-circuit. All 48 worker calls are
consumed before `not_qualified` is returned. A technical failure at any point
collapses to `execution_failed` with no exception detail, no partial index,
all five counts absent, and no authorization. `BaseException` deliberately
propagates so the future one-shot integration can distinguish an interrupted
or fatal attempt as `consumed_incomplete`.

The closed aggregate result has ten fields and contains no case or relation
identity, prediction, truth, stdout, request or PBM, suite seed, digest, error
detail or code, or generation commitment. Only a complete scientific pass
returns `qualified` and the protocol authorization. That authorization is
limited to owner-only provisional candidates for pages 22 through 77;
page 78 remains disallowed and every public claim permission remains false.

The evaluator API accepts an injected invoker. Its component return value
therefore is not an attestation of execution, isolation, custody, freshness,
single use, or use of the official sandbox path. An official C3 runner
has not been implemented. Any authoritative future use must internally
construct and own an exact `SandboxedWorkerInvoker`, expose no
caller-injection path, verify both process and invocation counters around
every call, integrate the one-shot state boundary, and preserve the
component's aggregate-only result.

Local source evidence at this checkpoint:

- all 28 focused evaluator tests passed;
- all 975 repository tests completed with 19 environment-specific skips;
- Ruff lint and format checks, Pyright, source and wheel builds, Gitleaks, and
  public-boundary checks passed; and
- two independent read-only source audits reported zero blockers, zero major
  findings, and zero minor findings.

Public CI run `30604750422` succeeded in 16m32s. Python 3.11 passed Quicknet
6/6 in 528.547056ms and all 975 tests with 22 environment-specific skips in
843.345s; Python 3.13 passed Quicknet 6/6 in 728.88314ms and the same 975-test,
22-skip suite in 957.050s; and Python 3.14 passed Quicknet 6/6 in 608.578832ms
and that suite in 906.624s. Every matrix job passed Ruff, checked all 179
files with Ruff format, reported zero Pyright errors, warnings, or information
messages, and built both the sdist and wheel.

No C3 controller or freeze builder has been implemented; no freeze has been
dispatched; and no C3 run, target selection, detector, real-source access or
result, decipherment evidence, or prize result exists. KP1979 V2 remains
retired and immutable.

At that checkpoint, the next controlled source task was a non-operational C3
controller and deterministic freeze builder plus the then-unresolved
Quicknet interruption-cleanup and runtime-policy work. The target round
remained unselected.

## KP1979 V3 Quicknet interruption-hardening checkpoint — 2026-07-31

Bounded best-effort Quicknet interruption cleanup is implemented at commit
`eda8af5791ed3ad6073d80308fa0696434ab89b6`. If `BaseException` interrupts the
initial verifier `communicate`, cleanup attempts process-group termination,
bounded `communicate`, and bounded `wait`; cleanup exceptions are suppressed
on that path and a bare raise preserves the exact original exception object.

After an ordinary timeout, `OSError`, or `SubprocessError`, the first cleanup
`BaseException` from process-group kill, `communicate`, or `wait` is retained
while every bounded cleanup stage continues. An interrupted first kill is
retried. An interrupted wait is retried once with the same bound. The exact
first cleanup exception object is then re-raised. In the absence of a cleanup
interrupt, ordinary public Quicknet failures retain their stable path-free,
detail-free boundary.

These are bounded best-effort termination and reaping attempts, not a
guarantee under repeated hostile interrupts. The focused tests include a
27-case ordinary-primary × cleanup-location × `BaseException`-wrapper matrix
using controlled process doubles. A distinct real-process regression
interrupts the first process-group kill and verifies the second kill/reap
path; it does not represent every matrix combination as a real process.

Local source evidence at this checkpoint:

- all 9 focused interruption tests passed, including the 27-case matrix;
- all 23 Quicknet tests passed;
- all 984 repository tests completed with 19 environment-specific skips in
  976.360s;
- Ruff lint and format checks, Pyright, Gitleaks, and an exact two-file
  production-source/test scope check passed; and
- independent audit reported zero blockers, zero major findings, and zero
  minor findings.

Public CI run `30608426512` succeeded in 16m27s. Python 3.11 passed Quicknet
6/6 in 448.623633ms and all 984 tests with 22 environment-specific skips in
640.818s, with an 11m11s job duration. Python 3.13 passed Quicknet 6/6 in
527.92177ms and the same 984-test, 22-skip suite in 950.240s, with a 16m17s
job duration. Python 3.14 passed Quicknet 6/6 in 546.222152ms and that suite
in 925.641s, with a 16m05s job duration. Every matrix job passed Ruff, checked
all 179 files as formatted, reported zero Pyright errors, warnings, or
information messages, and built both the sdist and wheel.

Portable semantic CI remains fixed to exact Node 24.18.0. The host wrapper
remains fixed to end-of-life Node 18.19.1 and is qualification-only. A
supported runtime policy remains unresolved before any official runner.

No official C3 runner, controller, or freeze builder has been implemented. No
freeze was dispatched, and no target round was selected, reserved, or
fetched. No detector execution, real-source access or result, decipherment
evidence, or prize result exists. The evaluator still accepts a caller-
injected invoker, so its component result remains a non-attestation of the
official sandbox path or execution. KP1979 V2 remains retired and immutable.

The next controlled source task is a non-operational, source-only
control-bundle builder plus the supported runtime policy. It must not select a
target or expose an operational runner. A future official runner must
internally construct and own an exact `SandboxedWorkerInvoker`, permit no
caller-supplied invoker, and preserve the one-shot and aggregate-only
boundaries. This step authorizes no freeze dispatch, worker or detector
execution, real-source access, public claim, or prize action.

## KP1979 V3 non-operational control source bundle — 2026-07-31

The deterministic
[control source-bundle builder](KP1979_V3_CONTROL_BUNDLE.md) is implemented at
commit `2e81afef7e188f9dd70059c60b9f1123019b3753`. It packages public source
only. The implementation does not select a target, derive a suite seed,
instantiate a generator object, invoke a worker, evaluate a response, open
one-shot state, or implement a detector, integration binding, controller, or
runner.

The closed payload roster has exactly 36 files: the project license, one
manifest schema, the package initializer, the builder, 12 controller-side
modules, and the exact 20-file vendored Noble/Quicknet closure. The canonical
archive has 37 regular-file members after adding `MANIFEST.json`. The builder
rejects any source tree containing the forbidden controller, detector,
detector-freeze, integration, integration-freeze, or runner components.

The compact canonical manifest fixes the protocol, control, target-algorithm,
and worker identities; 32 case invocations; 16 metamorphic endpoints; 48 total
invocations; `source_only=true`; `non_operational=true`;
`target_round_selected=false`; and absent detector and integration components.
It binds the exact ordered path, byte size, and SHA-256 of every payload.

The subject representation is closed:

- sorted regular-file-only USTAR uses mode `0644`, UID/GID and mtime zero,
  empty owner names, canonical fields and padding, and exactly two terminal
  zero blocks;
- a project-owned stored-DEFLATE encoder emits one fixed gzip stream with
  mtime zero, no filename, and OS byte 255; and
- bounded verification checks the exact roster and manifest, payload sizes and
  hashes, gzip CRC and size, and byte-for-byte reconstruction of both layers.

Descriptor-relative source reads reject unsafe ownership, group- or
other-writable or executable files, links, special files, and namespace or
fingerprint changes.
The output contract requires an absolute exact basename under an owner-only
parent, writes and synchronizes an owner-only staging inode, publishes without
replacement, and verifies the final namespace/inode/link/mode/size/bytes. On
failure, cleanup rechecks that the output name identifies the builder-owned
inode and otherwise preserves an unknown entry. This is best effort and not
atomic against same-UID or root namespace replacement.

The command-line environment is closed to exact CPython 3.12.11, exact
`-s -B -m` invocation, and eight exact environment keys. Exact CPython 3.12.11
is installed locally. No real source bundle was generated or retained, so
there is no release artifact or subject digest.

Local source evidence:

- all 63 focused control-bundle tests passed under exact CPython 3.12.11 in
  2.017s;
- all 1,047 repository tests completed with 19 environment-specific skips in
  1002.306s;
- Ruff lint passed and Ruff format accepted all 181 files;
- Pyright reported zero errors, warnings, or information messages;
- sdist and wheel builds passed;
- Gitleaks and public-boundary checks passed; and
- two independent read-only audits each reported zero blockers, zero major
  findings, and zero minor findings.

Public CI run `30615528575` succeeded in 16m23s at exact source commit
`2e81afef7e188f9dd70059c60b9f1123019b3753`:

- Python 3.11 passed Quicknet 6/6 in 520.428152ms and all 1,047 tests with 22
  environment-specific skips in 848.443s; its job completed in 14m35s.
- Python 3.13 passed Quicknet 6/6 in 537.327487ms and all 1,047 tests with 22
  environment-specific skips in 943.488s; its job completed in 16m13s.
- Python 3.14 passed Quicknet 6/6 in 410.523122ms and all 1,047 tests with 22
  environment-specific skips in 675.542s; its job completed in 11m48s.

Every matrix job passed Ruff, accepted all 181 checked files as formatted,
reported zero Pyright errors, warnings, or information messages, and built
both the sdist and wheel.

This evidence does not convert the builder into an attestation. The
`source_commit` input is validated only as lowercase hexadecimal and manifest
equality; authenticity, commit-to-checkout equality, signatures, trusted time,
non-deletion, and independent custody remain external. Descriptor, inode, and
namespace revalidation plus no-replace output do not defend against all
same-UID or root actions and cannot eliminate every race.

The evaluator still accepts a supplied invoker, so its aggregate result cannot
prove use of the official sandbox. A future official runner must internally
construct and own the exact `SandboxedWorkerInvoker`, permit no caller-supplied
invoker or factory, verify process and invocation counters, and bind the
aggregate result to the one-shot transition. Before that runner, the project
must harden the sandbox `BaseException` process-cleanup path and resolve the
supported host-runtime policy. Quicknet cleanup remains bounded best effort
against a second or repeated hostile interrupt. Portable semantic CI uses
exact Node 24.18.0, while the current fixed Node 18.19.1 host wrapper remains
end-of-life and qualification-only.

No real control bundle, freeze artifact, or subject digest was generated or retained.
No freeze was dispatched. No target round was selected, reserved, fetched, or
accessed. No real suite seed, schedule, generated object, truth, request,
worker response, or oracle was instantiated or persisted. No detector,
integration binding, official runner, worker execution, detector execution,
real-source access or result, C3 result, decipherment evidence, translation,
claim authorization, or prize evidence exists. KP1979 V2 remains retired and
immutable.

The next controlled source work is the supported host-runtime decision,
sandbox interruption-cleanup hardening, and an injection-free official
one-shot runner. External authenticity and custody controls must also be
defined before any authoritative use. None of those tasks authorizes building
or dispatching a freeze, selecting or fetching a target, running a worker or
detector, opening real source material, or making a public or prize claim.

## Portable Quicknet semantic-CI security pin — 2026-07-31

The portable CI policy is updated at commit
`0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec`. The exact source scope is
`.github/workflows/ci.yml` and `tests/test_kp1979_v3_quicknet.py`; production
Quicknet, vendored Noble code, the Node 18 host wrapper, sandbox, generator,
evaluator, control-bundle builder, and runtime source are unchanged.

Each Python matrix job now provisions exact Node 24.18.1 through
`actions/setup-node` v7.0.0 at full commit SHA
`820762786026740c76f36085b0efc47a31fe5020`. The workflow requests x64,
disables package-manager caching, and requires the following order before the
portable Quicknet suite:

1. exact `node --version == v24.18.1`;
2. exact `process.platform == "linux"`;
3. exact `process.arch == "x64"`; and
4. the six-test no-skip semantic command.

The source contract binds each setup field and assertion exactly once and
excludes the qualification-host test. This is a semantic-CI configuration for
deterministic public-input BLS checks in an ephemeral Linux/x64 job. It is not
provenance, custody, isolation, or attestation for a project/deployment runtime,
launcher, dynamic `libnode`, OpenSSL, glibc, kernel, sandbox, or worker.

The fixed Node 18.19.1 host wrapper remains end-of-life and
qualification-only. A supported host-runtime policy, complete dynamic
dependency closure, and official injection-free runner remain unresolved.
Earlier public evidence under exact Node 24.18.0 and full-SHA-pinned
`actions/setup-node` v6.5.0 remains historical and unchanged; those results
must not be relabeled as evidence for this configuration.

Focused Quicknet contract tests, Ruff lint and formatting, Pyright, YAML
parsing, diff checks, and an independent read-only zero-finding source review
passed locally.

Public CI run `30617537380` succeeded in 16m24s at exact source commit
`0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec`. Every matrix job used the
full-SHA-pinned setup action, provisioned exact Node 24.18.1 on Linux/x64, and
passed the exact version/platform/architecture assertions. Python 3.11 passed
Quicknet 6/6 in 535.647147ms and all 1,047 tests with 22
environment-specific skips in 856.889s, with a 14m50s job duration. Python
3.13 passed Quicknet 6/6 in 525.265295ms and the same 1,047-test, 22-skip
suite in 944.686s, with a 16m20s job duration. Python 3.14 passed Quicknet 6/6
in 527.783322ms and that suite in 895.407s, with a 15m28s job duration. Every
matrix job passed Ruff, accepted all 181 checked files as formatted, reported
zero Pyright errors, warnings, or information messages, and built both the
sdist and wheel.

No project or deployment runtime was installed or changed. No freeze was
built or dispatched, no target was selected or fetched, no protected or real
data was opened, and no worker or detector ran. This checkpoint establishes no
C3 result, real-source result, decipherment evidence, claim authorization, or
prize result.

## KP1979 V3 sandbox cleanup hardening checkpoint — 2026-07-31

Source commit `cd583fb12b12a80d132c80e8a3465e53f5c3151a`, whose parent is
public main `0f120e813dd449dfdfd499e39fa154a804a6b77a`, changes exactly the
sandbox implementation and its test module. Its exact binary diff SHA-256 is
`7069fbae6e9749c401f00ef35b5e5cc8c74d0e262f00626c95d4a7192d71115d`.
That digest identifies the source-commit diff bytes. It is not a signature,
trusted timestamp, custody record, runtime receipt, or attestation.

The implementation makes post-start cleanup an explicit bounded state machine:

1. **A — unit kill dispatch:** start an isolated, bounded `systemctl --user
   kill --kill-whom=all --signal=SIGKILL` helper.
2. **B — client kill:** send `SIGKILL` to the main sandbox client process
   group, independently of the helper outcome.
3. **C — conditional retry:** when A did not return status zero, dispatch one
   more bounded unit kill after the client kill.
4. **D — drain:** call bounded `communicate` on the main client.
5. **E — reap:** call bounded `wait`, with one bounded retry after failure or
   interruption, then determine reaping only from a non-`None` return code.

Every later stage is attempted after an earlier ordinary failure or interrupt.
The unit-kill helper uses its own new process group and explicit bounded
kill/communicate/wait cleanup if it fails or is interrupted. A helper return
status of zero means only that the dispatch command completed successfully. It
does not prove that the service cgroup is empty, that all descendants stopped,
or that the sandbox path, custody, or execution was attested.

Timeout output sizes may be read and returned only after both the main client
is reaped and at least one unit-kill dispatch returned zero. If either fact is
missing, the caller receives the existing redacted setup-failure surface and
no output or handshake is read. A negative main-client return code also enters
the full cleanup sequence before any output or handshake read. Normal
nonnegative completion retains the existing output/handshake validation path.

Exception precedence is explicit. A primary non-`Exception` `BaseException`
is re-raised as the exact same object after bounded cleanup, even when cleanup
is also interrupted. If the primary is ordinary, the first cleanup
non-`Exception` `BaseException` is retained by identity while all remaining
bounded stages are attempted. Ordinary failures remain path-free and
detail-free through the existing public result vocabulary. Repeated hostile
interruption can still defeat finite attempts or prevent later cleanup; this
is best effort, not a termination guarantee.

Bounded here means a finite attempt count and explicit timeouts on
`communicate` and `wait`. It is not a hard real-time bound on `Popen` process
creation, kernel scheduling, signal delivery, or filesystem/operating-system
calls. Process creation occurs before the subprocess timeout can govern the
child, so a stalled creation or kernel/filesystem operation can exceed the
nominal timeout sum.

Parent-side artifact, handshake, and output readers use no-follow and
nonblocking opens where available, owner-safe regular-file validation, bounded
reads, fingerprint revalidation, and explicit descriptor closing. Exclusive
writes and temporary-directory cleanup apply the same primary-versus-cleanup
exception rules. The public `SandboxedWorkerInvoker` construction/call
signature and `SandboxInvocationResult` schema, dispositions, and failure
codes remain unchanged. The started counter advances only when the main client
handle is returned and never for unit-kill helpers; the verified counter
advances only after a canonical handshake.

The test design covers controlled ordinary and `BaseException` failures at
process start, every cleanup stage, status access, bounded reads, descriptor
close, exclusive writes, and temporary cleanup; primary/cleanup identity;
stage order and bounded retries; timeout and negative-status gates; counters;
and one inert local sleep process group killed and reaped after a synthetic
first interrupt. It does not invoke a real systemd service or project worker.

Source-commit-bound local validation passed the normal focused sandbox suite
(47 tests in 1.644s, six environment-specific skips), the same suite under
exact CPython 3.12.11 (47 tests in 1.645s, the same six skips), and the
combined evaluator/worker-wire suites (51 tests in 27.230s, no skips). Two
independent read-only code audits each reported zero blockers, zero major
findings, and zero minor findings.

The first complete-suite attempt ran 1,078 tests with 19
environment-specific skips and recorded
four Quicknet failure/error outcomes (two failures and two errors). All four
outcomes were fail-closed mode
prechecks caused by inherited umask in the isolated worktree:
vendored Noble regular files were `0664` and directories were `0775`. Source
bytes, hashes, and the source diff did not change. Worktree-only `chmod go-w`
restored `0644`/`0755`, and focused Quicknet then passed. The attempt remains
a failed historical validation event and is not relabeled as success.

Final local validation after normalization passed all 23 Quicknet tests and
all 1,078 repository tests with 19 environment-specific skips in 1213.871s,
with a 1214.88s external wall duration. Ruff lint passed over the complete
configured scope, Ruff format accepted all 181 checked files, and Pyright
reported zero errors, warnings, or information messages. Distribution member
checks passed for a 337-member sdist and 163-member wheel, including path,
private-material, and source-hash assertions. Gitleaks scanned 65 commits and
approximately 7.15 MB with no leaks, and the public-boundary check passed.

The public-CI gate is now closed by
[run 30623782622](/megu0xxx0x/indus-open-benchmark/actions/runs/30623782622),
for event `push` at exact head SHA
`cd583fb12b12a80d132c80e8a3465e53f5c3151a`: status `completed`, conclusion
`success`, and all three matrix jobs green. The overall run window was
`2026-07-31`, `10:30:29Z`–`10:46:17Z` (15m48s). Every Quicknet job
asserted Node `v24.18.1` on Linux/x64 and recorded failed, cancelled, skipped,
and todo counts of zero. Python 3.11 ran
`10:30:33Z`–`10:44:34Z` (14m01s), with Quicknet 6/6
(`duration_ms=615.588048`) and unittest 1078 tests, 22 skipped, in 808.435s.
Python 3.13 ran `10:30:32Z`–`10:39:02Z` (8m30s), with Quicknet 6/6
(`duration_ms=292.030965`) and unittest 1078 tests, 22 skipped, in 483.182s.
Python 3.14 ran `10:30:32Z`–`10:46:16Z` (15m44s), with Quicknet 6/6
(`duration_ms=565.70517`) and unittest 1078 tests, 22 skipped, in 906.229s.
Each matrix job also passed Ruff lint, Ruff format with 181 files already
formatted, Pyright with zero errors, warnings, or information messages, and
sdist plus wheel builds. These are CI runs with 22 skipped tests per job; the
clean local full-suite result above has 19 skips, and the counts must not be
interchanged.

No project or deployment runtime was installed or changed. No real systemd
unit, worker, detector, control bundle, freeze, or target was created or run; no freeze was
dispatched; no target was selected, reserved, or fetched; no protected or real
data was opened; and no seed, schedule, truth, request, response, or oracle was
instantiated for execution. There is no C3 result, real-source result,
decipherment evidence, public-claim authorization, or prize result. KP1979 V2
remains retired and immutable. After audited publication, the separate next
gates remain a supported host-runtime/dynamic-closure decision and an
injection-free official one-shot runner. This source checkpoint authorizes neither.

## Chanhu-Daro source-link preselection hard-freeze — 2026-07-31

The project has shifted from infrastructure expansion back to the
highest-information research bottleneck: whether an independently chosen
context source can be linked without using the signs themselves. Source
commit `fd5148431b0fa9136336650208e2d570d0f176d8` freezes the input table for
that future question without executing it. Parent commit is
`361b1532d08b642423dd202f2f03c40cd41cdbb2`; the exact three-file,
mode-`100644`, 979-addition binary diff SHA-256 is
`56d8124f05223df5c9e010cfc97de328b5f7b6c3c2bc52f2aa8e8a7d10bd8de9`.

### Frozen table and nonclaims

The exact source-table order is:

1. SF 2000 / Penn 83830 / L-141-160 —
   `lead_no_listed_material_conflict`;
2. SF 3495 / Penn 83829 / L-141-159 —
   `excavation_location_axis_conflict`, with the excavation-location axis
   unresolved;
3. SF 3493 / Penn 149372 / L-141-92 —
   `lead_no_listed_material_conflict`;
4. SF 2428 / Penn 238862 / L-141-176 —
   `lead_no_listed_material_conflict`;
5. SF 3051 / Penn 329820 / L-141-177 —
   `shared_penn_target_identity_collision`; and
6. SF 2558 / Penn 329820 / L-141-177 —
   `shared_penn_target_identity_collision`.

Each value is carried in an exact source-namespaced identifier triple, not as
a bare identifier. Every row is `source_locator_only` and
`not_joined_requires_separate_contract`; table order is source order, not
rank. SF 3495 is not promoted past its conflict. SF 3051 and SF 2558 are not
merged even though they address the same Penn catalog target. The count is
six links, five distinct Penn catalog records, and zero admitted joins. It
does not count or verify physical objects.

The registry contains no positive, probable, exact, joined, or admitted
status and no sign, glyph, sequence, transcription, Helsinki row, reading,
direction, meaning, language, translation, or decipherment. All recorded
verification and admission nonclaims are false.

### Rights and implementation boundary

Only Penn bulk metadata is recorded as CC BY 4.0, redistributable metadata.
The extra-bulk Penn item-page association has an unregistered/null source
binding, null license, unknown rights, link-only scope, and records
`redistribution_permitted=false` without making a legal-rights conclusion.
The Mackay locator is also unknown-rights and link-only, with the same frozen
false field and no inferred legal prohibition. No layer includes media, and no
image, page, or plate bytes are part of the gate.

The Draft 2020-12 schema fixes six canonical `prefixItems`, rejects every
additional item with `items: false`, and binds the complete rights and
nonclaim records. All 355 tested mutations were rejected. This is a
repository-only contract. There is no production builder, API, strict runtime
loader, or packaged registry gate. The source distribution contains the
registry, schema, and test; the wheel contains the schema but not the registry
or test. Before any operational use, add strict `decode_json` parsing and
explicit distribution/resource-inclusion tests.

### Evidence and incidents

Focused validation passed 9 tests in about 0.03s, the related set passed 19
tests with one environment-specific skip in 0.667s, and all four publication
tests passed. Ruff lint, formatting of 182 files, and Pyright with no findings
passed. A locked offline isolated build produced a 341-member sdist and a
164-member wheel with the inclusion boundary above. The earlier non-isolated
build did not begin because its backend was absent; it produced no artifact.
Gitleaks scanned 67 commits and approximately 7.22 MB with no leaks.

The first full run reached 1,087 tests with 19 skips and recorded exactly two
failures and two errors. Quicknet correctly rejected `0664` files and `0775`
directories inherited by the isolated worktree's vendored Noble closure.
Only those worktree modes were normalized to `0644` and `0755`; tracked
content, hashes, and the code diff stayed unchanged. Quicknet then passed all
23 tests in 4.634s. The clean second run completed the 1,087-test full suite
with `OK (skipped=19)` in 976.546s.

The final independent audit reported zero blockers, zero major findings, and
zero minor findings. This followed correction of the first audit's major
bulk-versus-item source-binding finding and minor object-versus-catalog naming
finding. Public CI run `30635957691` succeeded for event `push` at exact head
SHA `fd5148431b0fa9136336650208e2d570d0f176d8`. Every job asserted Node
`v24.18.1` on Linux/x64. Python 3.11, 3.13, and 3.14 passed Quicknet 6/6 in
527.702196ms, 655.421586ms, and 503.092653ms, respectively, and completed the
1,087-test full suite with `OK (skipped=22)` in 810.027s, 946.248s, and
759.619s, respectively. Each job also passed Ruff (`All checks passed`), Ruff
format with all 182 files accepted, Pyright with zero errors, warnings, or
information messages, and both sdist and wheel builds.

### Authority boundary and next step

No network request to a research or source endpoint, external or protected
source-byte download, image/page/plate retrieval, Helsinki-row access,
institution or source-holder contact, operational gate, or real source-link
attempt occurred. Repository publication and CI are outside that statement.
This hard-freeze neither authorizes research-source access nor admits a row.

The infrastructure lane is hard-frozen for this research step. Host Node 24
activation, dynamic-closure expansion, and an official runner are deferred
until a real experiment demonstrates a reproducible need. The next step is to
design and separately freeze one non-sign source-link attempt. It must not use
sign, glyph, transcription, or sequence similarity to select among these
rows. The attempt must preserve conflicts, and a fully valid no-link outcome
must stop rather than trigger post-hoc row substitution. Only a later,
separately reviewed contract could authorize source access or any join.

## Static source-reported-link decision policy — 2026-08-01

Source commit `c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9`, whose parent is
`54fccb7a86a0d45de4e626b57a6332d091c11db2`, freezes the policy described in
[the detailed decision contract](SOURCE_REPORTED_LINK_POLICY_V1.md). It adds
exactly three mode-`100644` files and 898 lines. The binary diff SHA-256 is
`a635c012adefc52e05677aa1b337afe45ba53a25d4589bcb71446c7c2c0e8982`.
The registry, schema, and test hashes are recorded in the detailed contract.

### Frozen decision surface

All six preselection rows remain in source-table order, not rank order, with
one required result slot per row. The mutually exclusive terminal states use
precedence `contract_blocked`, `unresolved`, `source_reported_link`, then
`no_link`. Hard rejection precedes state evaluation and is not a terminal
state. Results may not be aggregated, omitted, or replaced after inspection.

There is no state named `positive`. `source_reported_link` means only that two
coded machine passes report the same bounded ASCII source-local locator for
the same parent row and exact source revision after all external prerequisites
match. It is not truth authentication, context verification, physical
identity, or join admission. A row-absent `no_link` requires exact complete
ordered-roster evidence from both passes; a bare not-found report is
`unresolved`.

### Pass and independence boundary

The frozen mode is two separately sealed coded machine passes. Only
`pass_id` and `seal_sha256` are required to differ. Human, model, and
organizational independence, blinding, nonexposure, and authorship
authenticity are not verified. Distinct IDs and seals must not be relabeled as
independent human review or external replication.

Sign, glyph, sequence, token, transcription, visual, linguistic, similarity,
confidence, OCR, raw/source bytes, excerpts, pages, images, media, notes, and
free text are forbidden channels. Malformed, noncanonical, premature-
observation, parent-mismatched, verification-mismatched, and forbidden-channel
inputs hard-reject before result classification.

### Rights and execution blocker

The Mackay locator is registered but unknown-rights and link-only; the frozen
policy records `redistribution_permitted=false` without making a legal-rights
conclusion. The Penn item page is unregistered, has a null source-registry
binding and license, unknown rights, link-only scope, and the same false field
without an inferred legal prohibition. Penn bulk metadata's CC BY 4.0 license
is explicitly not inherited by that item page.

The current state is therefore `contract_blocked`, with empty observations,
`not_authorized` execution, and no runtime evaluator. Unblocking requires a
separate contract binding source registration, exact revisions, rights
handling, inspection procedure, and the complete ordered source roster. This
policy does not authorize source access to prepare or execute that contract.

### Validation and abandoned prototype

The Schema `const` is semantically exact but treats JSON numeric `6` and `6.0`
as equivalent. Canonical byte identity is separately mandatory and
noncanonical input hard-rejects. The exact build produced a 345-member sdist
containing the policy, schema, and test and a 165-member wheel containing only
the schema from that set. Artifact hashes and exact inclusion boundaries are
recorded in the detailed policy document. No installed loader or package-
runtime claim exists.

A local untracked runtime prototype was abandoned after pre-publication
design/security review found incomplete-roster misrepresentation, an aggregate
result that hid five rows, trust in duck-typed verification, raw parser
exceptions outside the closed boundary, and a broken installed-schema lookup.
It was never staged, committed, pushed, packaged, or used on source data and
was deleted. It produced no observation or result.

Focused policy tests passed 7/7 and the combined policy, parent, and
publication-boundary set passed 20/20. Ruff lint, formatting of 183 files,
zero-finding Pyright, exact builds, and an independent zero-blocker/
zero-major/zero-minor audit passed. Gitleaks scanned 69 commits and 7,292,640
bytes with no leaks.

The first full run reached 1,094 tests in 1034.566s with 19 skips and recorded
two failures and two errors solely because Quicknet rejected `0664`/`0775`
vendored Noble modes inherited by the isolated worktree. Only those worktree
modes were normalized to `0644`/`0755`; tracked bytes, hashes, and diff were
unchanged. Quicknet then passed 23/23 in 4.197s, and the clean full rerun passed
1,094 tests in 1084.894s with `OK (skipped=19)`. The failed first run remains
part of the record.

Public CI run `30654728606` succeeded at exact head
`c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9`. Python 3.11, 3.13, and 3.14
passed Quicknet 6/6 in 398.928145ms, 522.070668ms, and 542.131729ms,
respectively, and passed all 1,094 tests with 22 skips in 636.266s, 910.867s,
and 930.525s. Every job also asserted Node 24.18.1 on Linux/x64, passed Ruff,
accepted all 183 files as formatted, reported zero Pyright errors, warnings,
or information messages, and built both the sdist and wheel.

### Authority boundary and next step

During this static-policy checkpoint, no research/protected source endpoint
was requested, no external source byte or media was opened, no Helsinki row or
protected corpus was accessed, and no institution or source holder was
contacted. No evaluator, source inspection, pass, observation, locator
comparison, roster attestation, source-reported-link/no-link outcome, join,
transcription, translation, decipherment evidence, public-claim authorization,
submission, or prize result exists. Repository publication and CI are outside
that statement and authorize none of those actions.

The next gate is a separate source registration and rights contract. Only a
new explicit authority decision after that contract could permit runtime
implementation or two-pass execution. Infrastructure remains hard-frozen
unless this research gate exposes a concrete reproducible need. KP1979 V2 and
all other retired controls remain immutable.

## Static source registration and rights contract — 2026-08-01

Source checkpoint `90f3fd3bea1177034451283795ad13ccb4b31bcf`, based on parent
`45d946a462dd85aa3025ed9ad9c0465541bd85be`, freezes the
[detailed static source contract](SOURCE_REPORTED_LINK_SOURCE_CONTRACT_V1.md).
The linked documentation records the exact candidate identities, hashes,
builds, request/receipt/custody rules, and validation evidence.

The policy's `unregistered`/null Penn item-page state remains exact historical
fact. The later, nonretroactive state is
`registered_static_no_revision_receipt`: five exact Penn object-page URIs are
statically bound without exact revisions or rights clearance. Five receipt
members, six revision resources, and six result slots remain distinct;
conflict and collision semantics are unchanged. Static registration does not
authorize access, retention, inspection, or execution.

The exact candidate passed 30 focused tests, Ruff lint and format,
static/build/secret checks, and a final zero/zero/zero audit. Two earlier
full-suite attempts were interrupted for specification hardening, then
`Content-Encoding` nullability correction, not test failures. Final suite
result is `Ran 1106 tests in 1023.743s; OK (skipped=19)`. Public
[CI run 30667904927](/megu0xxx0x/indus-open-benchmark/actions/runs/30667904927)
succeeded at exact head `90f3fd3bea1177034451283795ad13ccb4b31bcf`.
Python 3.11, 3.13, and 3.14 respectively recorded Quicknet/full-suite
durations of 425.727693 ms/642.201s, 522.243511 ms/978.761s, and
512.327502 ms/887.018s. Each matrix passed Quicknet 6/6 and 1106 full tests
with 22 skips, plus Ruff, the 184-file format check, zero-error Pyright,
sdist, and wheel builds.

Contract status is `preregistered_contract_blocked_pending_revision_receipt`;
the policy prerequisite remains `contract_blocked`, authorization
`not_authorized`, and execution `not_executed`. Required schemas, custody,
digests, runtime surfaces, observations, and results are absent; no source was
accessed. Next is to freeze those missing surfaces and obtain new explicit
authority before acquisition or two-pass execution. Retired controls remain
immutable.

## Static evidence prerequisites and custody blueprint — 2026-08-01

Static prerequisite commit `698c029b038b08d8f7e5538e048fdc42eb659160`,
based on parent `68ae5cff9065477be3a34ccc07b152636f44eb2f`, freezes the
[detailed evidence-prerequisite contract](SOURCE_REPORTED_LINK_EVIDENCE_PREREQUISITES_V1.md).
The validated head is the test-only Pyright narrowing commit
`93609e39263fde2617a6ea13b2f4de64947cd17e`; it changes no contract, schema,
or scientific semantics.

### What is now frozen

The static package closes four dynamic payload shapes: the five-member
source-revision receipt, its separate self-cycle-free commitment envelope,
the six-resource revision set, and the conditional six-slot completeness
attestation. Their exact schema-set digest is frozen in the linked detailed
evidence-prerequisite contract.
It also freezes the protected ephemeral custody/deletion/recovery blueprint,
one-time attempt and durable registry/ledger relations, source-access status
lattice, internal retention-review boundary, and nonclaims.

The contract preserves the distinct 5/6/6 cardinalities and all six parent
rows. Content-bearing response/parser/inspection bytes are memory-only;
the workspace is an exact-zero content-leaf isolation boundary. Cleanup is
descriptor-pinned and records logical absence without claiming secure
erasure. Unknown state, partial state, guessed deletion, untracked
descriptors, or cleanup uncertainty blocks scientific retention and
publication.

The executable models in the test are non-security reference semantics only.
They do not implement or establish a bootstrap trust root, signature/MAC
authenticity, strict runtime validation, durable custody, source access,
execution, or a result. The strict verifier, root classifier, terminalizer,
restart implementation, acquisition client, deterministic parser, evaluator,
future dynamic schemas, transitive runtime manifest, distribution binding,
and exact authority proof are still missing hard blockers.

### Validation and public evidence

Focused validation passed 22 prerequisite tests, 12 parent source-contract
tests, and seven policy tests. The closed reference-model evidence includes
five no-ledger branches, 20 other branches, all 990 Cartesian branch
combinations with zero mismatches, 34 storage-state cases, and 25 additional
storage assertions. Ruff, formatting of 185 files, locked Pyright 1.1.409,
canonical/schema validation, exact builds, and diff-scoped secret/public
boundary checks passed. Three independent read-only AI audits of the frozen
candidate reported zero P0, P1, and P2 findings; this is not human or external
scientific review.

A local validation run under unsupported Node 18.19.1 completed 1,128 tests in
912.511 seconds with 19 skips and four Quicknet-only fail-closed
failures/errors. All V8 tests passed. The first public CI run, `30691454425`,
passed Node 24 Quicknet and lint in all three matrix jobs, then stopped at
seven Pyright narrowing diagnostics confined to the new reference-model test.
The test-only follow-up fixed those diagnostics without changing contract or
schema bytes. Public GitHub Actions run `30692592441` then succeeded at exact
head
`93609e39263fde2617a6ea13b2f4de64947cd17e` under required Node 24.18.1.
Python 3.11, 3.13, and 3.14 passed Quicknet 6/6, Ruff, the 185-file format
check, zero-error Pyright, all 1,128 tests with 22 skips in 832.968s,
942.715s, and 865.301s respectively, and both distribution builds.

Documentation-only run `30693842726` subsequently rejected exact head
`c8d7231` after all three Python jobs found the same two classes of
publication-boundary regression: a literal digest in this operational
document and repository-specific Actions links in three public documents.
The corrective follow-up removes those literals and changes no contract,
schema, or scientific semantics.

### Exact current boundary and next step

Current contract status is
`preregistered_static_prerequisite_blocked_not_authorized`; authorization is
`not_authorized`, execution is `not_executed`, and source-access status is
`NONE_no_source_access_executed`. No research/protected source request,
external source byte, receipt, revision-set instance, completeness
attestation, pass, observation, source-link/no-link result, join,
transcription, translation, decipherment evidence, submission, or prize
result exists.

The next checkpoint is source-free runtime implementation. Build and freeze
the missing schemas, independent bootstrap verifier and external trust-root
interface, strict cross-artifact verifier, root classifier, terminalizer,
one-time registry/ledger recovery, custody supervisor, exact acquisition
client, bounded deterministic parser, two-pass evaluator, and review/retention
state machines. Bind their complete transitive manifest and reproducible
distribution to a distinct runtime commit and independently audit it.

Only after that checkpoint may a new exact authenticated authority proof bind
both commits and permit one complete acquisition. Earlier generic approvals
or instructions to continue cannot be reused as that one-attempt authority.
Even a valid source-reported-link result would be bounded contextual evidence,
not a decipherment; it must feed the separate hypothesis-tournament and
prospective-validation track without weakening the claim gate.

## Installed static loader and canonical-resource preflight — 2026-08-01

The first source-free implementation slice is now described in the
[detailed loader report](SOURCE_REPORTED_LINK_STATIC_LOADER_V1.md). It adds a
closed canonical-JSON preflight for all 21 raw artifact roles and an
argument-free installed-package loader for exactly 14 frozen static
resources.

The raw preflight implements only the first five verification stages:
per-role byte limits, BOM-free strict UTF-8, duplicate-key rejection,
integer-only bounded JSON, and exact `encode_json` byte equality. It does not
claim schema validity, a domain digest, parent/attempt binding, authority, or
evidence admissibility.

The installed loader uses descriptor-relative no-follow reads and fixed
size/hash identities, validates nine Draft 2020-12 schemas and five
registry/contract instances, and recomputes the ordered six-task roster and
four-schema set. Its immutable output contains six package-local identities.
The runtime-distribution and transitive runtime-input-manifest bindings remain
explicitly absent, so the future eight-way binding set is still incomplete.

Two frozen legacy resources predate the current canonical key order. Their
re-encoding exception is closed to those exact two compiled keys and applies
only after fixed raw size/hash agreement, which the decoder independently
rechecks. Their decoded form is never written back or adopted; the other 12
resources require canonical equality.

Frozen strict V1 separately hard-rejects every noncanonical raw input.
Consequently the snapshot fixes `strict_v1_resolver_eligible=False` and names
the two parent-byte conflicts as blockers. Adding the runtime-distribution
and transitive-manifest identities alone cannot make it eligible. A successor
normative profile defining the exact-two rule, or a re-frozen parent chain,
must precede any strict resolver or authority path.

The wheel packages the five required registries individually. A post-build
check independently verifies the 14 exact wheel members and then loads only
the extracted wheel from an empty working directory under isolated Python,
with no repository fallback and socket audit events trapped. Its extraction
uses a temporary deterministic `0022` umask and restores the caller's umask in
`finally`, avoiding ambient build-host group-write modes.

Focused pre-publication validation passed 76/76, including 22 raw-preflight
and 13 static-loader tests. Targeted Ruff, formatting, locked Pyright, both
distribution builds, wheel parity, and isolated-wheel loading passed. The
four publication-boundary tests also passed. Three independent read-only AI
audits each reported P0/P1/P2 as 0/0/0.

The local macOS full suite discovered all 1,163 tests and completed in
587.892s with 55 skips, but was not green. Its five failures and six errors
were confined to unchanged KP1979 V3 control-freeze host tests involving
Darwin directory revalidation and an AF_UNIX path-length limit; none involved
the new modules or changed packaging boundary. Required public Linux CI
remains a separate pending gate.

This changes the next-step boundary but not the authorization state. Remaining
work is the independent bootstrap/trust interface, transitive runtime
manifest, reproducible runtime distribution, missing dynamic schemas, strict
cross-artifact verifier, root classifier, terminalizer, recovery/state
machines, acquisition client, deterministic parser, and two-pass evaluator,
plus resolution of the frozen-V1 canonical conflict. Only a later exact
authenticated authority proof may bind an eligible static profile and the
completed runtime commit.

Current state remains
`preregistered_static_prerequisite_blocked_not_authorized`,
`not_authorized`, `not_executed`, and
`NONE_no_source_access_executed`. No source was accessed and no receipt,
observation, result, decipherment evidence, submission, or prize result
exists.
