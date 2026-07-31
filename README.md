# Open Indus Benchmark

An open, rights-aware, falsifiable research foundation for Indus inscriptions.

**This project does not claim to decipher or translate the Indus script.** It
builds the data contracts, provenance checks, leakage-resistant development
splits, and prerequisites for future independently custodial blind evaluations
needed to distinguish a predictive hypothesis from an attractive post-hoc story.

日本語要約: このプロジェクトは「インダス文字翻訳AI」ではありません。画像・出典・
権利・不確実性を追跡できるコーパスと、将来、外部機関が未知資料を管理する盲検試験を
作るための基盤です。現行の公開 development 分割自体は盲検試験ではありません。

## Current priority

Public repository:
[github.com/megu0xxx0x/indus-open-benchmark](https://github.com/megu0xxx0x/indus-open-benchmark).

For AI/maintainer continuation, read the public
[development plan and status](docs/DEVELOPMENT_PLAN_AND_LOG.md) first. It
records the source-level handoff state, authority boundaries, and next
milestones. Machine operations and private-data execution details are kept
outside Git.

The initial source-publication scope and its explicit exclusions are recorded
in the [2026-07-27 publication precheck](docs/PUBLICATION_PRECHECK_2026-07-27.md).

The [2026-07-28 decipherment-efficiency audit](docs/DECIPHERMENT_EFFICIENCY_AUDIT_2026-07-28.md)
changes the critical path. The completed verification software is scientific
insurance, but a serial full-700 review before analysis is not the
highest-information route. The subsequent
[Helsinki corpus fast-path audit](docs/HELSINKI_CORPUS_FAST_PATH_2026-07-28.md)
now starts with the official 1979 identifier-order corpus, checks it against
the same volume's two sorted reprints, applies the official 1980
revision/cross-reference/duplicate delta, and only then uses the 1982
occurrence concordance. A stratified calibration tranche, context-rich gold
objects, and an equal-budget hypothesis tournament proceed in parallel.
Unreviewed proposals remain outside admitted corpora and evaluation.

The first context-track implementation now revalidates a Penn Museum
metadata snapshot against its complete official CSV and derives 34
image-free context candidates: five pending originality review and 29
replica/modern negative controls. A primary-source
[Chanhu-Daro crosswalk audit](docs/CHANHU_DARO_CONTEXT_CROSSWALK_2026-07-28.md)
recovers published excavation contexts but keeps a two-field-number identity
collision and a room/locus disagreement unresolved. Separately, a
project-authored synthetic known-truth gate checks whether the proposed
functional-class machinery remains identifiable under short sequences,
allographs, damage, uncertain direction, and duplicate families. Passing that
method gate is not evidence that any Indus sign has been read.

The first real MTAAC control subsequently returned `NO_GO`, principally
because its fixed mild settlement-name recall gate failed. Its evaluator also
relies on gold-derived target eligibility, which cannot transfer to unknown
writing. V3 therefore leaves V2 immutable and changes the primary task to
joint prediction of `context_only` plus four target states over every retained
token. The fixed
[V3 development protocol](docs/MTAAC_V3_DEVELOPMENT.md) uses only the 271
MTAAC V2 training families; the 90-family V2 holdout is neither exposed to the
model nor scored. Its source-neutral structural baseline uses categorical
naive-Bayes emissions, first-order transitions, and Viterbi decoding under a
fixed family-grouped nested-selection design. This is development-only
known-script evidence, not an Indus or confirmation result.

The published V3 run obtained mild out-of-fold macro-F1 0.3243 and
`settlement_name` recall 0.0369. The one-standard-error rule selected
`gamma = 0.5, lambda = 0` in every outer fold. This means that the transition
component was not selected under that rule; it does not prove that sequence
transitions are absent.

The separately frozen
[V4 development protocol](docs/MTAAC_V4_DEVELOPMENT.md) now tests one fixed
distributional linear-chain CRF, not another parameter search. Its truth-free
target-batch profile is partition- and regime-local and removes the current
family before calculating type frequency, dispersion, position, context, and
neighbor statistics. Exact form identity never becomes a model feature. V4
reuses the exact V3 outer folds for paired development estimates and fixes all
advance/kill gates before execution. The
[world-research synthesis](docs/MTAAC_V4_WORLD_RESEARCH_2026-07-29.md)
records the primary-source rationale and rejects entropy, hidden states, or
network structure as decipherment evidence. The separately published
[V4 development result](docs/MTAAC_V4_DEVELOPMENT_RESULT_2026-07-29.md)
improved mild macro-F1 from V3's 0.3243 to 0.3878 in a positive direction on
all five paired outer folds. It nevertheless returned `development_killed`:
mild `unit` recall was 0.3052 against a 0.3768 floor, and
`settlement_name` recall was 0.0429 against a 0.15 floor. The final model was
not fitted. The prospective source was not loaded or scored by V4 and remains
prohibited from performance execution.

The [final MTAAC V5 protocol](docs/MTAAC_V5_DEVELOPMENT.md) predeclares one
last adaptive known-script test before retiring MTAAC. It keeps V4's data,
features, five-state capacity, folds, likelihood, class adjustment, and
optimizer fixed, and doubles only the regularization on the
`quantity`/`unit` and `person_name`/`settlement_name` emission contrast
directions. There is one candidate, no diagnostics or tuning grid, rare-state
precision cannot regress, and fold-level gains are mandatory. The separately
published [V5 result](docs/MTAAC_V5_DEVELOPMENT_RESULT_2026-07-29.md) passed
7 of 15 gates and returned `mtaac_retired`. Mild macro-F1 decreased from
0.3878 to 0.3846 and `unit` recall decreased from 0.3052 to 0.2937.
`settlement_name` recall increased from 0.0429 to 0.0575 but remained far
below its 0.15 floor. No final model was fitted, and MTAAC is retired.

Before any V3 model fitting, all eligibility-qualified, non-excluded
records from the exact CC0
[ORACC ED3b administrative source](docs/ORACC_ED3B_VALIDATION_SOURCE_2026-07-28.md)
were reserved. The source-only verifier and protocol calculate no
model-performance result; the records are prohibited from candidate fitting,
tuning, debugging, and model selection.

ORACC is no longer described as an untouched confirmation source. Rights and
schema inspection, archive-wide and joined-source class counts, and
gold-conditioned GDL-key safety aggregates informed its annotation-stripping
observation projection. It is therefore a feature-safety-exposed prospective
validation source. A binding confirmation requires a different, previously
uninspected corpus selected through an independently controlled or
predeclared-random mechanism after the complete model and evaluator freeze.
The
[global known-script source audit](docs/V3_GLOBAL_KNOWN_SCRIPT_SOURCE_AUDIT_2026-07-28.md)
records the other candidates and their narrower or deferred roles.

The global evidence audit has established a baseline and now continues as
recurring monitoring; it no longer blocks calibrated extraction and
falsifiable functional tests. It is not model-led translation, an external
corpus release, a decipherment claim, a blind result, or a prize submission.
The [2026-07-29 evidence update](docs/GLOBAL_EVIDENCE_UPDATE_2026-07-29.md)
found no verifiable public iCEL three-dimensional dataset as of that date,
identifies an ASI/NMMA ID-and-official-URL-only external-catalogue lane, and
rechecks that the authentic Tamil Nadu award announcement still lacks a
verified operational submission scheme.
The dated [global research landscape](docs/GLOBAL_RESEARCH_LANDSCAPE_2026-07-26.md)
maps the principal corpora, institutions, theories, recent computational claims, open-source and
rights constraints, the Tamil Nadu prize status, and Japan's actual research gap. Its claims are
tracked in a [machine-readable evidence ledger](registry/research_landscape.json), with explicit
verification, rights, falsification, lineage, and review dates. The [roadmap](docs/ROADMAP.md) now
places continuing evidence review beside corpus extraction and decipherment
tests rather than before them.

The 2026-07-27
[global open-source audit](docs/GLOBAL_OPEN_SOURCE_AUDIT_2026-07-27.md)
pins current repositories, models, datasets, and Unicode status. It quarantines
public benchmarks with unresolved lineage, licensing, split leakage, or
circular evaluation instead of treating “open on the web” as ground truth.
The [machine-enforced quarantine registry](registry/quarantine.json) blocks
those sources, unknown source IDs, and incompatible rights from normal corpus,
training, and evaluation paths. Explicit audit-only inspection never promotes
material into an admissible corpus.

The prize has a separate current audit:
[announcement authentic, operational submission scheme not verified](docs/TAMIL_NADU_PRIZE_STATUS_2026-07-27.md).

The separate [global museum-rights audit](docs/GLOBAL_MUSEUM_RIGHTS_AUDIT_2026-07-26.md)
and [museum candidate ledger](registry/museum_candidates.json) distinguish open
metadata, reusable images, exploration-only APIs, and sources that require
written permission. An API or IIIF manifest is never treated as image reuse
permission by itself.

## What the current source tree provides

- A nested `artifact → side → line → token` observation contract.
- Separate contracts for source rights, hypotheses, quarantine, public-development
  membership, evaluator configuration, and benchmark definitions.
- Domain validation for provenance, rights, identifiers, direction, order, and uncertainty.
- A reviewed importer for the small MIT-licensed `mayig` transcription corpus.
- Duplicate-family, image-hash, and exact-sequence leakage audits.
- Family-grouped public development holdouts; these are neither blind nor final
  evaluation sets.
- A domain-separated exact-byte definition lock for corpus, schemas, source and
  quarantine registries, split, evaluator inputs, `pyproject.toml`, and `uv.lock`;
  it remains explicitly local, unanchored, and development-only.
- A deterministic complete-tree submission commitment for a caller-declared
  digest of a separately verified benchmark definition, declared entrypoint,
  source, configuration, weights,
  dependencies, and otherwise unclassified runtime inputs. It remains local
  content-integrity evidence, not a trusted timestamp or blind-test receipt.
- Simple probabilistic baselines that test the pipeline without pretending to translate.
- Repeated matched-shuffle null evaluation with explicit empirical uncertainty.
- A global research evidence ledger that separates reported results from interpretations.
- A deterministic treewidth audit with explicit sequence boundaries and three null families.
- Protocols for future cross-edition artifact/sign mapping, with no
  authoritative mapping release yet, and ongoing research-intelligence
  workflows.
- A fail-closed museum API intake that preserves item rights, raw-response and image hashes,
  exact policy evidence, provider renditions, and unresolved physical-side status.
- Raw-byte-bound, network-free Penn and Smithsonian metadata parsers that
  separate catalog discovery from media permission.
- A deterministic Penn context-anchor registry that revalidates the complete
  official CSV, retains replicas as negative controls, and fixes every
  field-number, transcription, meaning, and originality approval false.
- A project-authored CC0 synthetic identifiability gate with family-safe
  splits, family weighting, damage/allograph/direction degradation,
  family-vector permutation nulls, and an explicit anchor-free abstention.
- A pinned, network-free adapter and pre-result-frozen V2 protocol for the CC0
  MTAAC known-script control. It isolates four mechanical word-level labels
  from opaque whole-FORM categories, fixes source-document splits and
  degradation, preserves the aborted V1 invocation as an explicit erratum,
  and records the single V2 run as `NO_GO`. The unchanged method cannot be
  transferred to Indus and cannot issue a reading or decipherment claim.
- A strict source-only verifier and pre-development protocol for the exact
  CC0 ORACC ED3b administrative archive. It reserves the mechanically
  qualified source for later project-run five-state prospective validation,
  emits only aggregate commitments, and does not expose a validation scoring
  entry point. Feature-safety inspection informed its frozen observation
  sanitizer, so it is not binding confirmation evidence. The
  [published source-qualification receipt](benchmark/results/oracc-ed3b-validation-source-v1.json)
  binds the exact public source-freeze commit and reports no model execution
  or performance metric.
- A separate MTAAC V3 development plan and implementation boundary that keeps
  V2 immutable, exposes only its fixed 271-family training partition, and
  excludes and does not score its 90-family holdout. The five-state
  source-neutral structural baseline fixes its complete feature surface,
  nine-candidate parameter grid, family-grouped nested `5 × 4` selection,
  mild-only candidate selection, clean diagnostics, fixed four-fold final
  development selection, and aggregate-only report contract. The
  [published V3 development result](docs/MTAAC_V3_DEVELOPMENT_RESULT_2026-07-29.md)
  selected `gamma = 0.5, lambda = 0` under its one-standard-error rule and
  obtained mild out-of-fold macro-F1 0.3243 with worst-state recall 0.0369.
  The transition component was not selected; this is not proof that
  transitions are absent. The result is a modest known-script baseline, not a
  decipherment claim.
- A separate exact-byte V4 development plan, truth-free
  `target_batch_partition_regime_local_document_leave_one_family_out` profile,
  fixed distributional linear-chain CRF, independent
  logistic-emission diagnostic, deterministic pure-Python L-BFGS optimizer,
  paired V3 outer-fold comparison, predeclared advance/kill gates, closed
  aggregate schema, and network-free no-replace command. V4 uses only the 271
  development families, excludes the V2 holdout, does not load the reserved
  prospective source, and cannot issue an Indus reading or decipherment
  claim. Its separately published result improved overall and on every paired
  fold but failed the fixed mild `unit` and `settlement_name` recall gates,
  returned `development_killed`, and fitted no final model.
- A final MTAAC V5 code-and-plan contract that preserves V4's parameter count
  and full observation/model pipeline while changing only the fixed emission
  contrast regularizer. Its exact rare-state recall, precision, paired-fold,
  clean-integrity, one-shot, and MTAAC-retirement gates are fixed before any
  real V5 execution. Its separately published result passed 7 of 15 gates,
  returned `mtaac_retired`, fitted no final model, and ended adaptive MTAAC
  development.
- A privacy-minimized, descriptor-relative private-corpus readiness audit that
  emits a fixed count-free terminal summary, keeps aggregate details private,
  and cannot promote material without exact per-file rights coverage.
- A private transcription evidence bridge that verifies exact sign-inventory,
  independent-review, and adjudication bytes, then creates a non-overwriting
  private staging receipt. Its drafts are unsealed, public export is disabled,
  and promoted observations are excluded from evaluation.
- A proposal-value-stripped KP1982 bootstrap-assignment builder and verifier.
  It derives an exact 700-cell reviewer roster from the fixed page pixels and
  canonical layout proposal while structurally excluding machine occupancy,
  OCR, identifier, and accepted-observation values. Proposed rectangles and
  crop commitments remain reviewer aids, not accepted observations.
- A non-circular KP1982 bootstrap-review and adjudication verifier. It checks
  the value-stripped assignment directly against the two fixed PBMs, rehashes
  every submitted observation crop, binds exactly two structurally distinct
  sealed review inputs, and prevents an adjudicator from inventing a third
  observation.
  Its actor declarations do not prove human authorship or real independence.
- A fixed official KP1979 source and 179-page native-pixel map, plus a
  streaming, pixel-only layout audit. It proposes label-lattice slots on normal
  two-column corpus pages while abstaining on dense prose, ten-column sign
  lists, and the eight-/six-column auxiliary grids. It does not segment full
  rows. No label slot, row, identifier, sign, or decipherment value is accepted.
- Separate proposal-free KP1979 label-reference assignments for the fixed
  six-page development and six-page future-evaluation partitions, plus a
  geometry-only review verifier that recomputes every submitted crop from the
  exact source pixels. The assignments expose no page class, scan band,
  detector geometry, candidate count, OCR result, or manual value.
- A separate development-only, exposed machine projection for KP1979 label
  geometry. It preserves unresolved observations and can support provisional
  extraction, but it is neither human reference evidence nor admissible input
  to detector scoring; it never opens the future-evaluation reference.
- Source-independent frozen position-matching arithmetic behind a
  canonical-fixture-only synthetic control for the KP1979 V1 label-lattice
  detector. V1 is retained as `not_qualified` after failing thin-stroke and
  periodic non-label counterexamples; the result is synthetic-only and makes
  no real-accuracy claim.
- A synthetic-only deterministic KP1979 V3 generator covering 12 positive,
  14 negative, and six out-of-contract cases plus eight fixed two-endpoint
  relations, for exactly 48 worker invocations. Authoritative controller-side
  validation binds every case and relation to exact canonical regeneration
  under the supplied suite seed. Only `request_bytes` satisfying the exact
  five-field answer-free wire contract may reach a worker. Instantiated suite
  seeds, generated objects, full construction and truth metadata, generation
  commitments, and schedule metadata must not be persisted or published
  before execution or passed across that boundary. This is generator
  infrastructure only and does not itself freeze or execute C3. KP1979 V2
  remains immutable.
- A streaming, aggregate-only
  [KP1979 V3 evaluator](src/indusbench/kp1979_v3_evaluator.py), published at
  commit `ee847035867fe92dbca8b3e0aa9422dcfd43f138`. It builds and
  same-seed-validates one canonical generator object at a time, then passes
  only its `request_bytes` to the supplied invoker for all 48 sequential calls.
  Positive cases require `proposed`, exact 96-pixel predictions, and complete
  same-lane one-to-one anchor matching with no false positives or false
  negatives; negative cases require exact
  abstention, out-of-contract cases require the expected rejection code, and
  all eight fixed relations are checked exactly.
  A scientifically wrong but valid response still completes all 48 calls and
  returns `not_qualified`. A technical fault returns `execution_failed`
  without error detail, counts, or authorization. `BaseException` is
  deliberately propagated so a future one-shot runner can record
  `consumed_incomplete`. The closed ten-field aggregate result can authorize
  only owner-only provisional candidates for pages 22 through 77 after a
  complete pass; page 78 authorization and every public claim permission
  remain false.
  The component result alone is not an execution attestation. Its public API
  accepts an injected invoker, so this component does not establish that the
  official sandbox path was used. An official runner is not yet implemented.
  Any authoritative future use must internally construct and own an exact
  `SandboxedWorkerInvoker` and must not allow caller injection of another
  invoker.
  Public CI run `30604750422` succeeded in 16m32s on Python 3.11, 3.13, and
  3.14. Every job passed Quicknet 6/6, all 975 tests with 22
  environment-specific skips, Ruff lint and formatting of all 179 files,
  Pyright with no findings, and both distribution builds.
  No C3 controller or freeze builder has been implemented; no freeze has been
  dispatched; and no C3 run, target selection, detector, real-source access or
  result, decipherment evidence, or prize result exists. KP1979 V2 remains
  immutable.
- Bounded best-effort Quicknet interruption cleanup, published at commit
  `eda8af5791ed3ad6073d80308fa0696434ab89b6`. A `BaseException` raised by the
  initial verifier `communicate` now triggers bounded process-group
  termination attempts, bounded `communicate` and `wait`, and a bare re-raise
  that preserves the original exception object. For an ordinary timeout,
  `OSError`, or `SubprocessError`, the first cleanup `BaseException` from
  process-group kill, `communicate`, or `wait` is retained while every bounded
  cleanup stage continues, then re-raised as the same object. An interrupted
  first kill is retried, and an interrupted wait receives one bounded retry.
  Ordinary public Quicknet failures remain path-free and detail-free.
  This is bounded best-effort cleanup, not a guarantee against repeated
  hostile interrupts. Local validation passed 9/9 focused interruption tests,
  including a 27-case ordinary-primary × cleanup-location ×
  `BaseException`-wrapper matrix. A separate real-process regression covers
  an interrupted first kill followed by the second kill/reap path; the matrix
  does not claim that every combination starts a real process. All 23
  Quicknet tests passed, and all 984 repository tests completed locally with
  19 environment-specific skips in 976.360s, together with Ruff, formatting,
  Pyright, Gitleaks, an exact two-file scope check, and an independent audit
  reporting zero blockers, zero major findings, and zero minor findings.
  Public CI run `30608426512` succeeded in 16m27s on Python 3.11, 3.13, and
  3.14. Every job passed Quicknet 6/6, all 984 tests with 22
  environment-specific skips, Ruff, formatting of all 179 files, Pyright with
  no findings, and both distribution builds. At that checkpoint portable
  semantic CI was fixed to exact Node 24.18.0 through full-SHA-pinned
  `actions/setup-node` v6.5.0. The legacy host wrapper remained fixed to
  end-of-life Node 18.19.1 for qualification only; a supported runtime policy
  was unresolved before any official runner. No official C3 runner,
  controller, or freeze builder existed. The next source task was a
  non-operational, source-only control-bundle builder plus that supported
  runtime policy, without target selection.
- A portable Quicknet semantic-CI security update at commit
  `0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec`. The workflow now pins exact
  Node 24.18.1 and `actions/setup-node` v7.0.0 by full commit SHA
  `820762786026740c76f36085b0efc47a31fe5020`, fixes architecture `x64`, and
  disables package-manager caching. Before the six mandatory Quicknet tests,
  it asserts the exact Node version, Linux platform, and x64 architecture.
  The contract test binds each setup field and assertion exactly once, fixes
  the runtime assertion/command order, and excludes the host test from
  portable CI.
  This is public-input BLS semantic CI on an ephemeral Linux/x64 runner, not
  an attestation of a deployment launcher, installed runtime, dynamic
  libraries, kernel, custody, or official worker execution. The unchanged
  Node 18.19.1 host wrapper remains end-of-life and qualification-only. A
  supported host runtime and its dynamic closure remain unresolved.
  Public CI run `30617537380` succeeded in 16m24s at that exact source
  commit. Every matrix job used the full-SHA-pinned setup action, provisioned
  exact Node 24.18.1 on Linux/x64, and passed the exact
  version/platform/architecture assertions. Python 3.11 passed Quicknet 6/6
  in 535.647147ms and all 1,047 tests with 22 environment-specific skips in
  856.889s; its job completed in 14m50s. Python 3.13 passed Quicknet 6/6 in
  525.265295ms and the same 1,047-test, 22-skip suite in 944.686s; its job
  completed in 16m20s. Python 3.14 passed Quicknet 6/6 in 527.783322ms and
  that suite in 895.407s; its job completed in 15m28s. Every matrix job
  passed Ruff, accepted all 181 checked files as formatted, reported zero
  Pyright errors, warnings, or information messages, and built both the sdist
  and wheel.
  No project or deployment runtime was installed or changed by this
  source-only update. It selected or fetched no target, built or dispatched no
  freeze, opened no protected or real data, ran no worker or detector, and
  produced no decipherment or prize result.
- A deterministic, non-operational
  [KP1979 V3 control source-bundle builder](docs/KP1979_V3_CONTROL_BUNDLE.md),
  published at commit `2e81afef7e188f9dd70059c60b9f1123019b3753`.
  Its closed canonical representation contains exactly 36 source payloads and
  37 regular-file members after adding the manifest. The manifest fixes the
  protocol, control, target-algorithm, and worker identities; records 32 case
  plus 16 relation-endpoint invocations; marks the subject source-only and
  non-operational; records no target selection; and requires detector and
  integration components to be absent.
  Verification bounds and exactly reconstructs compact ASCII JSON, canonical
  USTAR, and project-owned stored-DEFLATE gzip bytes.
  The exact 63 focused tests passed under CPython 3.12.11 in 2.017s. All
  1,047 repository tests completed locally in 1002.306s with 19
  environment-specific skips; Ruff, formatting of 181 files, zero-finding
  Pyright, sdist and wheel builds, Gitleaks, and public-boundary checks
  passed. Two independent audits each reported zero blockers, zero major
  findings, and zero minor findings.
  Public CI run `30615528575` succeeded in 16m23s at exact source commit
  `2e81afef7e188f9dd70059c60b9f1123019b3753`:
  - Python 3.11 passed Quicknet 6/6 in 520.428152ms and all 1,047 tests with
    22 environment-specific skips in 848.443s; its job completed in 14m35s;
  - Python 3.13 passed Quicknet 6/6 in 537.327487ms and all 1,047 tests with
    22 environment-specific skips in 943.488s; its job completed in 16m13s;
    and
  - Python 3.14 passed Quicknet 6/6 in 410.523122ms and all 1,047 tests with
    22 environment-specific skips in 675.542s; its job completed in 11m48s.
  Every matrix job passed Ruff, accepted all 181 checked files as formatted,
  reported zero Pyright errors, warnings, or information messages, and built
  both the sdist and wheel.
  The supplied `source_commit` remains an unauthenticated label; Git
  authenticity, custody, trusted time, and commit-to-checkout equality are
  external. Descriptor and no-replace hardening do not form a security
  boundary against same-UID or root actors or eliminate every race. The
  evaluator's injected-invoker result remains a non-attestation. Quicknet
  repeated-interrupt and sandbox `BaseException` cleanup residuals plus a
  supported host-runtime policy remain unresolved before any official runner.
  The code exists, but no real control bundle, freeze artifact, or subject
  digest was generated or retained. No freeze or dispatch exists; no target
  or real-run seed,
  schedule, truth, worker execution, detector, integration, runner,
  real-source access or result, decipherment evidence, or prize claim exists.
- An atomic private review bundle that binds every policy entry to exact bytes,
  starts every source/right/use decision at deny-all pending review, and records
  structured anomalies without copying source values.
- A catalog-blind private review packet that separates opaque reviewer evidence
  from the institution/accession custody map and forbids sign or language inference.
- Synthetic fixtures that are safe to publish and cannot contaminate historical claims.

## Scientific boundary

The project distinguishes five outcomes:

1. **Transcription:** identify signs, variants, damage, and possible direction.
2. **Structure:** test positional classes, repeated formulae, and object/site associations.
3. **Functional partial decipherment:** predict quantity, metrology, object,
   commodity, role, or administrative slots from independent context.
4. **Phonetic or language assignment:** requires predictive evidence across held-out material.
5. **Translation:** requires independent replication and preferably an external anchor.

The first three are the current research targets. The latter two are not
inferred from visual similarity, modern-language resemblance, or fluent LLM
output.

## Quick start

The runtime uses Python 3.11+ and `jsonschema` for the normative Draft 2020-12
contracts. The `just` development recipes run through `uv` and resolve the
dependency-locked (`uv.lock`) optional lint and type-check dependencies.

```bash
cd /path/to/indus-open-benchmark
just test
PYTHONPATH=src python3 -m indusbench --help
PYTHONPATH=src python3 -m indusbench validate examples/synthetic_corpus.jsonl
```

For the dependency-locked development environment:

```bash
uv sync --extra dev
uv run indusbench validate examples/synthetic_corpus.jsonl --full-schema
just check
```

To import a local checkout of the upstream mayig corpus without vendoring it:

```bash
PYTHONPATH=src python3 -m indusbench import-mayig \
  /path/to/indus-valley-script-corpus \
  data/derived/mayig.jsonl
```

Raw and derived external data directories are ignored by Git. Importing data does not grant
permission to publish it; see [DATA_POLICY.md](DATA_POLICY.md).

Prepare a private review draft, then audit an ignored physical corpus without
exposing its names, paths, identifiers, values, counts, or content hashes in
the terminal output:

```bash
install -d -m 700 /private/reviews /private/reports
uv run indusbench prepare-private-review \
  /private/physical-corpus-root \
  /private/reviews/review-bundle.json \
  --created-at 2026-07-27T08:00:00Z

uv run indusbench audit-private-readiness \
  /private/physical-corpus-root \
  --intended-use local_nonpublic_normalization \
  --created-at 2026-07-27T08:00:00Z \
  --policy-bundle /private/reviews/review-bundle.json \
  --private-report /private/reports/readiness.json
```

The repository `data` symlink is intentionally rejected; pass its physical
target. Generation succeeds as an operation but deliberately produces
`curation_status=pending`, unknown rights/provenance, and no permitted use, so
the resulting audit remains `ready=false`. The private bundle contains exact
paths and SHA-256 bindings; it must remain outside Git and any web root. Those
digests detect replacement but prove no rights, provenance, time, or custody.
Even a later successful local audit keeps every custody, blind, decipherment,
and prize assurance false. See the
[private corpus readiness boundary](docs/PRIVATE_CORPUS_READINESS.md).

After creating a split, compare a bigram with repeated matched nulls:

```bash
uv run indusbench null-evaluate \
  data/derived/split/train.jsonl data/derived/split/development.jsonl \
  --runs 100 --seed 20260726
```

Inspect verified official/project records in the global evidence ledger:

```bash
uv run indusbench research --tier A --status verified
uv run indusbench museum-candidates \
  --automation-class metadata_only --with-verified-candidates
```

Run the line-preserving treewidth audit on an imported corpus:

```bash
uv run indusbench treewidth-audit data/derived/mayig.jsonl \
  --sequence-unit canonical_line --runs 100 --seed 20260726
```

Commit a prepared submission tree without claiming custody or blindness:

```bash
uv run indusbench build-submission-commitment \
  data/derived/candidate \
  data/derived/candidate-submission.json \
  --benchmark-definition-sha256 sha256:<64-lowercase-hex> \
  --entrypoint src/run.py \
  --source-file src/model.py \
  --config-file config/model.json \
  --model-weight-file weights/model.bin \
  --dependency-file uv.lock
uv run indusbench verify-submission-commitment \
  data/derived/candidate-submission.json \
  data/derived/candidate
```

The commitment includes every file and empty directory under its root, has no
ignore rules, and must be written outside that root. It never records a
self-asserted creation time or upgrades
`blind_claim_allowed=false`; see the
[submission commitment boundary](docs/SUBMISSION_COMMITMENT.md).
The manifest is not confidential: it exposes paths, roles, sizes, static
arguments, and deterministic hashes. Do not publish one containing secrets,
hidden identifiers/hashes, custodian nonces, or rights-restricted metadata.

Verify the fixed KP1979 source. The crosschecked extraction used Poppler
`pdfimages 26.04.0`; reproduce its exact filename mapping as follows:

```bash
uv run indusbench verify-kp1979-source indus_corpus_1979.pdf

test "$(pdfimages -v 2>&1 | sed -n '1p')" = "pdfimages version 26.04.0"
mkdir kp1979-poppler-raw canonical-kp1979-pbm
pdfimages -f 2 -l 180 -p -print-filenames \
  indus_corpus_1979.pdf kp1979-poppler-raw/page
test "$(find kp1979-poppler-raw -type f -name '*.pbm' | wc -l | tr -d ' ')" = 179
page=2
image=0
while test "$page" -le 180; do
  source_file="$(printf 'kp1979-poppler-raw/page-%03d-%03d.pbm' "$page" "$image")"
  target_file="$(printf 'canonical-kp1979-pbm/page-%03d.pbm' "$page")"
  test -f "$source_file"
  test ! -e "$target_file"
  cp "$source_file" "$target_file"
  page=$((page + 1))
  image=$((image + 1))
done

uv run indusbench audit-kp1979-layout \
  indus_corpus_1979.pdf canonical-kp1979-pbm

install -d -m 700 /private/kp1979-row-review
uv run indusbench prepare-kp1979-row-assignment \
  indus_corpus_1979.pdf canonical-kp1979-pbm \
  /private/kp1979-row-review/base-row-assignment.json
uv run indusbench verify-kp1979-row-assignment \
  indus_corpus_1979.pdf canonical-kp1979-pbm \
  /private/kp1979-row-review/base-row-assignment.json
```

The final command checks every canonical PBM byte and pixel digest, so a
different image count, mapping, encoding, or decoder result fails closed.
Pixel-equivalent but differently encoded PBMs also fail because the V1
canonical byte representation is fixed. The audit emits no candidate count or
identifier. A passing result establishes exact input pixels and page-class
detector gates only.

The private row assignment repeats the complete 179-page audit, then binds
proposal-only label and row-context crops for the 57 identifier-order pages.
It contains no OCR, identifier, lower code, sign, occupancy, reading direction,
language, meaning, or accepted manual value. Its rectangles remain unaccepted
review aids. Provisional machine extraction may continue without human
reviewers, but only eligible independent human-reference evidence can promote
geometry or support detector scoring. The command will not overwrite an
existing output and requires a physical owner-only parent directory.

Create and verify the separate proposal-free assignments. Keep development
and future evaluation in different owner-only directories, and do not show the
57-page proposal-bearing assignment to a reference reviewer:

```bash
install -d -m 700 /private/kp1979-label-reference-development
uv run indusbench prepare-kp1979-label-reference-assignment \
  indus_corpus_1979.pdf canonical-kp1979-pbm \
  /private/kp1979-label-reference-development/assignment.json \
  --partition development
uv run indusbench verify-kp1979-label-reference-assignment \
  indus_corpus_1979.pdf canonical-kp1979-pbm \
  /private/kp1979-label-reference-development/assignment.json \
  --partition development
uv run indusbench verify-kp1979-label-reference-review \
  indus_corpus_1979.pdf canonical-kp1979-pbm \
  /private/kp1979-label-reference-development/assignment.json \
  /private/kp1979-label-reference-development/review.json \
  --partition development
```

The assignment command creates no review and no reference value. To create
eligible independent human-reference evidence, a review must be prepared
outside the recognizer by an actual reviewer. Valid schema, opaque IDs,
declarations, and exact crop hashes do not by themselves prove human
authorship or real independence.

If human reviewers are unavailable, create and recompute the separate
development-only machine pass:

```bash
uv run indusbench prepare-kp1979-machine-development-review \
  "$KP1979_PDF" "$KP1979_PBM_DIR" \
  "$KP1979_DEVELOPMENT_ASSIGNMENT" "$KP1979_MACHINE_REVIEW"
uv run indusbench verify-kp1979-machine-development-review \
  "$KP1979_PDF" "$KP1979_PBM_DIR" \
  "$KP1979_DEVELOPMENT_ASSIGNMENT" "$KP1979_MACHINE_REVIEW"
```

That pass is intentionally exposed to detector output, OCR, page-role
expectations, and scoring expectations. It is machine-authored, provisional,
preserves unresolved geometry, is ineligible as human reference evidence, and
must not be used for detector scoring. It does not open or populate the
future-evaluation reference. Human passes remain a later promotion gate for
externally grounded reference evidence, not a prerequisite for provisional
research progress. The target, partitioning, custody, matching, and scientific
nonclaim rules are fixed in
[`docs/KP1979_LABEL_REFERENCE_PROTOCOL.md`](docs/KP1979_LABEL_REFERENCE_PROTOCOL.md).

Run the public, source-independent V1 synthetic diagnostic with:

```bash
uv run indusbench run-kp1979-label-lattice-synthetic-control
```

The command currently succeeds as an execution while reporting the scientific
status `not_qualified`; its JSON fixes all real-accuracy, reference-acceptance,
decipherment, and prize claims false.

The current synthetic-only V1 result and its retrospective limits are recorded
in
[`docs/KP1979_LABEL_LATTICE_SYNTHETIC_CONTROL_V1_RESULT_2026-07-29.md`](docs/KP1979_LABEL_LATTICE_SYNTHETIC_CONTROL_V1_RESULT_2026-07-29.md).

Verify the KP1982 inventory-bootstrap evidence; only after a future separate
post-adjudication inventory build, compare later inscription-transcription
drafts and promote a complete adjudication to private staging:

```bash
uv run indusbench verify-kp1982-source indus_concordance_1982.pdf \
  --page-pbm page-20.pbm page-21.pbm

install -d -m 700 /private/kp1982-layout
uv run indusbench propose-kp1982-layout \
  page-20.pbm page-21.pbm /private/kp1982-layout/proposal.json
uv run indusbench verify-kp1982-layout \
  page-20.pbm page-21.pbm /private/kp1982-layout/proposal.json
uv run indusbench prepare-kp1982-bootstrap-assignment \
  page-20.pbm page-21.pbm \
  /private/kp1982-layout/proposal.json \
  /private/kp1982-layout/bootstrap-assignment.json
uv run indusbench verify-kp1982-bootstrap-assignment \
  page-20.pbm page-21.pbm \
  /private/kp1982-layout/proposal.json \
  /private/kp1982-layout/bootstrap-assignment.json

install -d -m 700 /private/kp1982-reviews /private/kp1982-reports
uv run indusbench verify-kp1982-bootstrap-review-input \
  page-20.pbm page-21.pbm \
  /private/kp1982-layout/bootstrap-assignment.json
uv run indusbench verify-kp1982-bootstrap-review \
  page-20.pbm page-21.pbm \
  /private/kp1982-layout/bootstrap-assignment.json \
  /private/kp1982-reviews/pass-a.json
uv run indusbench audit-kp1982-bootstrap-reviews \
  page-20.pbm page-21.pbm \
  /private/kp1982-layout/bootstrap-assignment.json \
  /private/kp1982-reviews/pass-a.json \
  /private/kp1982-reviews/pass-b.json \
  --private-report /private/kp1982-reports/new-bootstrap-audit.json
uv run indusbench verify-kp1982-bootstrap-adjudication \
  page-20.pbm page-21.pbm \
  /private/kp1982-layout/bootstrap-assignment.json \
  /private/kp1982-reviews/pass-a.json \
  /private/kp1982-reviews/pass-b.json \
  /private/kp1982-reviews/adjudication.json

install -d -m 700 /private/transcription-reports /private/transcription-artifacts
uv run indusbench audit-transcription-agreement \
  sign-inventory.json review-a.json review-b.json \
  --private-report /private/transcription-reports/new-agreement.json
uv run indusbench promote-transcription \
  sign-inventory.json unresolved-artifact.json adjudication.json \
  /private/transcription-artifacts/new-artifact.json \
  --review review-a.json --review review-b.json \
  --side-id <side-id> --line-id <line-id>
```

The layout commands deterministically bind all cell and fixed 32-pixel
padded-context rectangles to the page pixels, write only a new private `0600`
proposal, and independently recompute it before later use. A cell crop is only
a locator and may split foreground; its context crop is a review view, not
accepted glyph evidence. Every layout-acceptance, identifier, and decipherment
claim remains false. Verification also requires the proposal to remain a
single-link owner-owned `0600` file under a physical owner-only `0700` parent.

The bootstrap-assignment commands rebuild the fixed proposal before preparing
or verifying an exact 700-cell locator roster. The assignment exposes proposed
cell/context rectangles and their crop commitments, but its closed structure
contains no machine occupancy answer, accepted occupancy, OCR output, machine
identifier proposal, or accepted observation field. This prepares independent
human work; it does not prove that reviewers were independent or blinded, and
no human pass or adjudication has yet been completed.

The bootstrap-review commands do not receive the layout proposal. They accept
only the exact proposal-value-stripped assignment and the two canonical PBMs,
then recompute the assignment crop commitments and every submitted observation
crop. Every reviewed cell and observation crop must remain inside that cell's
reviewed context, though a corrected context may leave the original proposal.
Independent records cannot depend on a pre-existing sign inventory.
Adjudication must bind exactly two verified structurally distinct review
records and may select one of their observations or remain unresolved; it
cannot add a third value,
rectangle, crop, or printed-mark set. Assignment, review, and adjudication
inputs must be single-link owner-owned `0600` files below physical owner-only
`0700` parents. The audit writes its count-bearing detail only to a new private
no-replace report; that report may contain record commitments, pseudonymous
IDs, aggregate counts, and cell-level mismatch locations and field codes but
never raw identifier observations, while terminal output is count-free. These
checks do not verify human authorship, actual reviewer separation or
non-exposure, source rights, public-release authority, evaluation admission,
decipherment, or prize eligibility. No real review or adjudication execution
is claimed.

Left-to-right numbering is a visual-coordinate convention, not an inferred
reading direction; direction and signs may remain unresolved. Outputs are new
`0600` files below pre-existing physical owner-only `0700` parents. The v0.1
records are unsealed, private-only, and evaluation-inadmissible. See the
[transcription bridge boundary](docs/TRANSCRIPTION_BRIDGE.md) and the
[Helsinki 1982 Batch 0 protocol](docs/KP1982_BATCH0_PROTOCOL.md). None of these
preparation steps is a decipherment result or a prize claim.

Stage explicitly selected Open Access museum objects in the ignored private
data tree:

```bash
uv run indusbench intake-museum data/raw/museum_open_access/snapshot \
  --met-object <public-object-id> \
  --cleveland-accession <public-accession> \
  --download-media --full-schema
uv run indusbench verify-museum-intake \
  data/raw/museum_open_access/snapshot --full-schema
uv run indusbench prepare-museum-review \
  data/raw/museum_open_access/snapshot \
  data/derived/private_reviews/snapshot
uv run indusbench verify-museum-review \
  data/derived/private_reviews/snapshot
uv run indusbench seal-museum-review \
  data/derived/private_reviews/snapshot \
  data/derived/private_review_ledgers/snapshot \
  /private/path/human-review-draft.json
uv run indusbench verify-museum-review-ledger \
  data/derived/private_reviews/snapshot \
  data/derived/private_review_ledgers/snapshot
uv run indusbench parse-penn-metadata \
  <official-penn-csv> \
  <new-private-penn-output.json> \
  --retrieved-at <rfc3339-acquisition-time> \
  --source-last-updated <source-update-date>
uv run indusbench derive-penn-context-anchors \
  <private-penn-snapshot.json> \
  <same-official-penn-csv> \
  <new-private-context-registry.json> \
  --expected-source-sha256 sha256:<trusted-download-digest>
uv run indusbench synthetic-identifiability-gate
uv run indusbench parse-smithsonian-metadata \
  <official-smithsonian-shard.jsonl> \
  <new-private-smithsonian-output.json> \
  --source-url <canonical-official-shard-url> \
  --retrieved-at <rfc3339-acquisition-time> \
  --line-number <one-based-line-number> \
  --expected-sha256 sha256:<trusted-download-digest>
```

Review preparation re-verifies the source, makes exact single-link evidence
copies under opaque IDs, isolates the identity map, and scans reviewer text for
catalog leakage. Human records can then be validated and atomically sealed into
a separate digest-named ledger; Codex does not fabricate those records. Neither
step publishes images, assigns artifact/sign IDs, or authorizes model training.
The Penn and Smithsonian commands parse caller-supplied official bulk bytes
only; neither downloads the file nor follows record or image URLs. Smithsonian
output commits to the complete JSONL container and exact selected line, and
keeps record-level metadata rights separate from every media item's rights.
Penn context derivation additionally requires the complete CSV again and
exactly re-derives the supplied snapshot before writing a no-replace registry.
The synthetic identifiability command uses no historical or third-party data.
It reports every valid scientific outcome with status zero by default. Add
`--require-go` in CI when a non-`go` report must return status 2.

The historical normative invocation of the corrected frozen MTAAC V2
known-script control used the public pre-result code commit recorded in the
report:

```bash
uv run indusbench evaluate-mtaac-control \
  <exact-pinned-mtaac-archive.tar.gz> \
  --pre-result-code-commit <40-character-public-freeze-commit> \
  --output <new-aggregate-result.json>
```

The command is network-free, refuses a different archive or protocol byte,
never writes raw corpus rows, and does not overwrite an existing report.
`--require-go` returns status 2 for any outcome other than `go`; without it,
scientifically valid `no_go`, `insufficient_evidence`, and
`not_identifiable` reports remain publishable outcomes. A passing control is
only a method-instrument result, not an Indus reading or prize claim.

The normative V2 invocation has now occurred once. Its
[aggregate result](docs/MTAAC_KNOWN_SCRIPT_CONTROL_V2_RESULT_2026-07-28.md)
is `NO_GO`: mild `settlement_name` recall was 0.193553 against the frozen
minimum 0.35. Do not rerun V2 with another seed, threshold, split, or protocol
to replace that result. A later exact-condition execution is an independent
replication only; it must not overwrite or reinterpret the fixed normative
result.

## Repository map

```text
schemas/                 Normative JSON Schema contracts
registry/sources.json    Machine-readable source and rights ledger
registry/research_landscape.json
                         Machine-readable global research evidence ledger
registry/museum_candidates.json
                         Global museum automation/rights candidate ledger
registry/quarantine.json Machine-enforced deny/audit-only evidence registry
benchmark/               Closed public-development evaluator configuration
src/indusbench/          Validation, import, split, audit, and baseline code
examples/                Synthetic, redistributable examples
tests/                   Unit and integration tests
docs/                    Scientific protocol and schema documentation
AGENTS.md                Public handoff and safety instructions
```

## Core rule

No score is valid until all records from the same physical artifact, mold/template family,
image hash, and exact normalized sequence are isolated in one partition. Reported results must
also include leave-one-site, leave-one-period, and leave-one-object-type tests where metadata
permits.

Read the [scientific standard](docs/BENCHMARK.md), [schema contract](docs/SCHEMA.md),
[benchmark-definition lock boundary](docs/BENCHMARK_LOCK.md),
[submission commitment boundary](docs/SUBMISSION_COMMITMENT.md),
[private corpus readiness boundary](docs/PRIVATE_CORPUS_READINESS.md),
[private transcription bridge](docs/TRANSCRIPTION_BRIDGE.md),
[MTAAC known-script control audit](docs/MTAAC_KNOWN_SCRIPT_CONTROL_2026-07-28.md),
[MTAAC V2 result](docs/MTAAC_KNOWN_SCRIPT_CONTROL_V2_RESULT_2026-07-28.md),
[MTAAC V3 development protocol](docs/MTAAC_V3_DEVELOPMENT.md),
[MTAAC V4 development protocol](docs/MTAAC_V4_DEVELOPMENT.md),
[MTAAC V4 world-research synthesis](docs/MTAAC_V4_WORLD_RESEARCH_2026-07-29.md),
[MTAAC V4 development result](docs/MTAAC_V4_DEVELOPMENT_RESULT_2026-07-29.md),
[MTAAC V5 final development protocol](docs/MTAAC_V5_DEVELOPMENT.md),
[MTAAC V5 development result](docs/MTAAC_V5_DEVELOPMENT_RESULT_2026-07-29.md),
[annotation guide](docs/ANNOTATION_GUIDE.md), [data policy](DATA_POLICY.md), and
[contribution guide](CONTRIBUTING.md) before adding data or models. Institutional access work can
start from the bilingual [permission templates](docs/PERMISSION_REQUESTS.md); hypothesis teams use
the [frozen payload template](docs/PREREGISTRATION_TEMPLATE.md), while a future
independent custodian uses the separate
[receipt-envelope template](docs/PREREGISTRATION_RECEIPT_ENVELOPE_TEMPLATE.md).
Edition alignment follows the
[crosswalk protocol](docs/CROSSWALK_PROTOCOL.md), and recurring global monitoring follows the
[research-intelligence workflow](docs/INTELLIGENCE_WORKFLOW.md). Rights-cleared,
untranscribed image staging follows the
[museum-intake contract](docs/MUSEUM_INTAKE.md). Catalog-blind carrier,
surface, relationship, ROI, and crosswalk observation follows the private
[museum-review contract](docs/MUSEUM_REVIEW.md).

The first rights-limited end-to-end run is documented in the
[Mayig structural pilot](docs/PILOT_REPORT_2026-07-26.md). Its predictive result is explicitly
structural and is not presented as evidence for a language or translation.
The separate [Ross 2026 treewidth audit](docs/ROSS_2026_TREEWIDTH_AUDIT.md) reproduces the
reported upper bound while showing why it does not distinguish linguistic from non-linguistic
generation on its own.
Museum intake and catalog-blind review are documented as public software
contracts with synthetic fixtures. No executed private intake, review packet,
inventory, content digest, or review result is published. A successful private
intake is never an automatic corpus-publication action.

## Status

Version `0.1.0` is an engineering and governance seed, not an authoritative corpus release.
RMRL/IM77, ICIT/Wells, CISI images, museum photography, and publication scans require separate
permissions or item-level rights review. Their absence is not filled with synthetic translations.

Code is MIT licensed. External data and images retain their own rights.
