# Roadmap

## Continuing track — Global evidence audit

- Maintain a dated, multilingual map of corpora, catalogues, museums, institutions, current
  projects, theories, critiques, code, and prize rules.
- Grade every source as primary evidence, peer-reviewed structure, interpretive hypothesis,
  preprint/tool, or unverified claim.
- Reproduce major computational results and test them against matched null models before adopting
  their metrics.
- Build Mahadevan/CISI/Wells/ICIT artifact and sign crosswalk specifications.
- Record separate rights for metadata, transcription, glyph art, artifact images, crops, and
  learned derivatives.
- Keep rights-restricted data, custody material, and operational hidden-test
  material private while permissions and independent custody remain unresolved.

Current assets:

- [timestamped development plan and continuation log](DEVELOPMENT_PLAN_AND_LOG.md)
- [2026-07-27 public-source publication precheck](PUBLICATION_PRECHECK_2026-07-27.md)
- [2026-07-26 global research report](GLOBAL_RESEARCH_LANDSCAPE_2026-07-26.md)
- [2026-07-27 global open-source and reproducibility audit](GLOBAL_OPEN_SOURCE_AUDIT_2026-07-27.md)
- [machine-readable research evidence ledger](../registry/research_landscape.json)
- [machine-enforced quarantine registry](../registry/quarantine.json)
- [public-development benchmark definition boundary](BENCHMARK_LOCK.md)
- [local submission content commitment boundary](SUBMISSION_COMMITMENT.md)
- [private corpus readiness boundary](PRIVATE_CORPUS_READINESS.md)
- [cross-edition crosswalk protocol](CROSSWALK_PROTOCOL.md)
- [recurring research-intelligence workflow](INTELLIGENCE_WORKFLOW.md)
- [Ross 2026 treewidth reproduction audit](ROSS_2026_TREEWIDTH_AUDIT.md)
- [museum intake contract](MUSEUM_INTAKE.md)
- [global museum rights/API audit](GLOBAL_MUSEUM_RIGHTS_AUDIT_2026-07-26.md)
- [machine-readable museum candidate ledger](../registry/museum_candidates.json)
- [private catalog-blind museum review contract](MUSEUM_REVIEW.md)
- [private transcription evidence bridge](TRANSCRIPTION_BRIDGE.md)
- [Helsinki 1982 sign-list Batch 0 protocol](KP1982_BATCH0_PROTOCOL.md)
- [2026-07-28 decipherment-efficiency audit](DECIPHERMENT_EFFICIENCY_AUDIT_2026-07-28.md)
- [context source-link preselection gate](CONTEXT_SOURCE_LINK_PRESELECTION_GATE.md)
- [static source-reported-link decision policy](SOURCE_REPORTED_LINK_POLICY_V1.md)
- [static source registration and rights contract](SOURCE_REPORTED_LINK_SOURCE_CONTRACT_V1.md)
- [Chanhu-Daro context crosswalk audit](CHANHU_DARO_CONTEXT_CROSSWALK_2026-07-28.md)
- [2026-07-28 Helsinki corpus fast-path audit](HELSINKI_CORPUS_FAST_PATH_2026-07-28.md)
- [2026-07-28 global known-script source audit](V3_GLOBAL_KNOWN_SCRIPT_SOURCE_AUDIT_2026-07-28.md)
- [2026-07-28 ORACC ED3b prospective-validation source audit](ORACC_ED3B_VALIDATION_SOURCE_2026-07-28.md)

## v0.1 — Public, non-blind engineering seed

- Normative contracts and synthetic examples.
- Rights/source registry.
- Versioned global research evidence ledger.
- Mayig adapter without vendoring source data.
- Validation, fail-closed quarantine, grouped public-development split,
  leakage audit, simple baselines, structural null audits, and an exact-byte
  local definition lock.
- Reproducible CLI and tests.

## Current research track — Information gain before corpus volume

- [x] Freeze the repository-only Chanhu-Daro source-link preselection table at
  commit `fd5148431b0fa9136336650208e2d570d0f176d8`: exactly six ordered
  source-namespaced identifier triples for SF 2000, SF 3495, SF 3493, SF 2428,
  SF 3051, and SF 2558. Keep all rows `source_locator_only` and
  `not_joined_requires_separate_contract`; preserve the SF 3495
  excavation-location conflict and the distinct SF 3051/SF 2558 rows that
  share one Penn catalog target. Six links and five Penn catalog records are
  not six verified physical objects. Rights remain layer-specific: CC BY 4.0
  covers Penn bulk metadata only, while Penn item-page associations and
  Mackay locators remain unknown-rights, link-only layers. No sign, glyph,
  sequence, transcription, Helsinki row, join, or admission is frozen.
  Static validation rejected all 355 tested mutations. The final audit was
  zero/zero/zero after correction of the first audit's bulk-versus-item and
  catalog-naming findings. Local validation completed the 1,087-test full suite
  with `OK (skipped=19)` in 976.546s after preserving an earlier Quicknet
  fail-closed worktree-mode incident. Public CI run `30635957691` succeeded
  for event `push` at exact head SHA
  `fd5148431b0fa9136336650208e2d570d0f176d8`. Every job asserted Node
  `v24.18.1` on Linux/x64. Python 3.11, 3.13, and 3.14 passed Quicknet 6/6 in
  527.702196ms, 655.421586ms, and 503.092653ms, respectively, and completed the
  1,087-test full suite with `OK (skipped=22)` in 810.027s, 946.248s, and
  759.619s, respectively. Every job also passed Ruff, Ruff format for all 182
  files, zero-finding Pyright, and sdist plus wheel builds.
- [x] Design and freeze the static non-sign source-link decision policy at
  commit `c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9`. Bind exactly one result
  slot to each of the six parent rows, forbid aggregation/omission/post-hoc
  substitution, and fix precedence `contract_blocked`, `unresolved`,
  `source_reported_link`, then `no_link`. Hard rejection occurs before state
  evaluation. `source_reported_link` is a source report rather than a
  positive/truth state or join admission. The two passes differ only in
  identifier and seal; independence, blinding, and nonexposure are not
  verified. Current state: `contract_blocked`, with no evaluator, execution,
  observation, source byte, result, or join.
- [x] Freeze the static, explicitly nonretroactive source registration and
  rights contract at `90f3fd3bea1177034451283795ad13ccb4b31bcf`.
  Register the five exact Penn item-page URIs without claiming revision
  capture, rights clearance, source access, or execution. Preserve five
  future Penn receipt members, six ordered source-revision resources, and six
  parent-row result slots; preserve the SF 3495 conflict and distinct SF
  3051/SF 2558 slots. Penn bulk metadata's CC BY 4.0 license is not inherited.
  State remains `contract_blocked`, authorization `not_authorized`, and
  execution `not_executed`.
- [ ] Freeze a closed receipt schema, separate receipt-commitment envelope,
  protected ephemeral custody/deletion contract, strict canonical loader,
  operational parser, and runtime evaluator. Only after a new explicit
  authority decision may one complete bounded acquisition retrieve the five
  Penn members and construct the exact six-resource revision set and
  completeness commitments. Invalid or partial prerequisites must remain
  blocked and cannot become `unresolved` or `no_link`.
- [ ] Only after new explicit authority, implement and review a strict runtime
  evaluator and execute two coded machine passes. Preserve all six row-level
  states and forbidden channels; do not infer human/model/organizational
  independence from distinct IDs and seals.
- [ ] Add a strict `decode_json`-backed installed contract loader, registry
  resource-inclusion checks, and installed-distribution tests before making
  any operational or packaged runtime claim for the source-link gate. Static
  publication does not implement this step. The modified source registry and
  new contract schema are wheel resources; the contract registry and tests
  are not. No installed contract loader, parser, or evaluator exists.
- [x] Hard-freeze infrastructure expansion for this research step. Defer host
  Node 24 activation, dynamic-closure expansion, and an official runner until
  a real experiment exposes a reproducible need. This does not authorize
  source access, worker execution, or a join.

- [x] Audit whether the serial transcription-first path is the
  highest-efficiency route and record explicit resource allocations, claim
  gates, and kill criteria.
- [x] Complete the KP1982 source/layout/assignment/review/adjudication verifier
  V1. After publication, freeze it unless a downstream experiment exposes a
  reproducible defect or evidence-loss problem.
- [x] Pin the official KP1979 PDF and all 179 native page images, freeze its
  section/page map, and implement the pixel-only abstaining two-column audit.
- [x] Implement a private, exact-source row-review assignment for all 57
  identifier-order pages. It rechecks the 179-page audit, stores only
  proposal geometry and crop commitments, and withholds every OCR,
  identifier, code, sign, occupancy, direction, and manual-reference value.
- [ ] Add a separate KP1979 delivery-variant verifier for the current official
  HeldA route. Keep the existing exact container fixed; accept no new raw PDF
  hash unless all 179 per-page PBM commitments independently reproduce.
- [x] Confirm the official 1980 continuation's exact bytes and data-bearing
  ranges for revisions, bidirectional Mahadevan cross-reference,
  documentation, and strict/loose duplicate assertions.
- [ ] Freeze independently prepared label y-positions for the 12-page KP1979
  development/future-evaluation protocol. Page identities and pixels are
  public; require exact label-position precision/recall before accepting any
  label-slot geometry, then validate full-row segmentation separately.
  - [x] Define separate proposal-free six-page assignments, a geometry-only
    review contract, exact source/PBM/crop verification, and the pre-result
    matching rule.
  - [x] Add an exposed, development-only machine geometry pass for provisional
    extraction when human reviewers are unavailable. It preserves unresolved
    observations, cannot be promoted to human reference evidence, cannot be
    used for detector scoring, and leaves future-evaluation values unopened.
  - [x] Implement the frozen position-scoring arithmetic and a
    source-independent known-truth synthetic control. Preserve V1 as
    `not_qualified` after its thin-stroke and periodic non-label failures.
  - [ ] Develop any successor under a new KP1979 detector identifier. Keep the
    exposed V1 cases as regression tests and freeze a separate generator or
    seed before treating a new synthetic result as qualification evidence.
  - [x] Complete the synthetic-only V3 generator checkpoint: 12 positive,
    14 negative, and six out-of-contract cases plus eight fixed two-endpoint
    metamorphic relations, for 48 worker invocations. Bind every
    controller-side case and relation to exact canonical regeneration under
    the supplied suite seed. Instantiated suite seeds, generated objects, full
    construction and truth metadata, generation commitments, and schedule
    metadata must not be persisted or published before execution and must not
    be passed to a worker. Only `request_bytes` satisfying the exact five-field
    answer-free wire contract may cross that boundary. Independent
    source-level QA reported zero blockers, zero major findings, and zero minor
    findings. KP1979 V2 remains immutable.
  - [x] Implement and independently audit the streaming V3 evaluator. It
    is published at commit `ee847035867fe92dbca8b3e0aa9422dcfd43f138`,
    same-seed-validates one canonical object at a time, passes only
    `request_bytes` to the supplied invoker, and evaluates all 48 calls without
    materializing or publishing a schedule. Positive cases require exact
    height 96 and zero false positives or false negatives;
    negative and out-of-contract behavior plus all eight fixed relations are
    exact gates. Scientific failures complete all 48 calls as
    `not_qualified`; technical failures expose no detail, counts, or
    authorization, and `BaseException` propagates for future one-shot state
    handling. A complete pass permits only owner-only provisional candidates
    for pages 22–77; page 78 authorization and every public claim remain
    false. The public API permits caller injection of the invoker, so the
    ten-field component result is not an execution attestation. No official
    runner exists yet. Public CI run `30604750422` succeeded in 16m32s across
    Python 3.11, 3.13, and 3.14, passing Quicknet 6/6 and all 975 tests with
    22 environment-specific skips in every matrix job, plus Ruff, Ruff format
    on 179 files, Pyright with no findings, and both distribution builds.
  - [x] Harden bounded best-effort Quicknet interruption cleanup at commit
    `eda8af5791ed3ad6073d80308fa0696434ab89b6`. Initial-`communicate`
    `BaseException` now triggers bounded process-group kill/reap attempts and
    is bare-re-raised as the original object. For ordinary primary failures,
    the first cleanup `BaseException` is retained while every bounded stage
    continues; interrupted first kill and wait stages receive their declared
    bounded retries. Ordinary public failures stay path-free and detail-free.
    This does not guarantee cleanup under repeated hostile interrupts.
    Local evidence passed 9/9 focused interruption tests, the 27-case
    ordinary-primary × cleanup-location × `BaseException`-wrapper matrix, all
    23 Quicknet tests, all 984 repository tests with 19 environment-specific
    skips, static and publication checks, and an independent zero-finding
    audit. Public CI run `30608426512` succeeded on Python 3.11, 3.13, and
    3.14 with Quicknet 6/6, all 984 tests and 22 environment-specific skips
    per job, Ruff, formatting of all 179 files, Pyright with no findings, and
    both builds.
  - [x] Implement and independently audit the non-operational, source-only C3
    control-bundle builder at commit
    `2e81afef7e188f9dd70059c60b9f1123019b3753`. Its canonical source roster is
    exactly 36 payloads and 37 members including the manifest. It records 32
    case and 16 relation-endpoint invocations while fixing
    `source_only=true`, `non_operational=true`, no target selection, and
    absent detector and integration components. Local evidence passed all 63
    focused tests under exact CPython 3.12.11 in 2.017s, all 1,047 repository
    tests with 19 environment-specific skips in 1002.306s, Ruff, formatting
    of 181 files, zero-finding Pyright, sdist and wheel builds, Gitleaks, and
    public-boundary checks. Two independent read-only source audits each
    reported zero blockers, zero major findings, and zero minor findings.
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
    The `source_commit` label does not prove Git authenticity or custody, and
    same-UID/root race limitations remain. Exact CPython 3.12.11 is installed
    locally, but no real control bundle, freeze artifact, or subject digest was
    generated or retained.
    This checkpoint dispatched no freeze or worker and selected no target.
  - [ ] Establish a supported host-runtime policy and harden sandbox
    `BaseException` cleanup before implementing any official runner. Current
    portable semantic CI pins exact Node 24.18.1 on Linux/x64 through
    full-SHA-pinned `actions/setup-node` v7.0.0
    (`820762786026740c76f36085b0efc47a31fe5020`), disables package-manager
    caching, and asserts version, platform, and architecture before the
    semantic suite. Earlier Node 24.18.0/setup-node v6.5.0 run evidence remains
    historical and unchanged. This is semantic CI, not host/deployment
    attestation or a closed dynamic runtime. The fixed Node 18.19.1 host
    wrapper remains end-of-life and qualification-only. Quicknet cleanup
    remains bounded best effort under a second or repeated hostile interrupt.
    Public CI run `30617537380` succeeded in 16m24s at exact source commit
    `0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec`. Every matrix job used the
    full-SHA-pinned setup action, provisioned exact Node 24.18.1 on Linux/x64,
    and passed the exact version/platform/architecture assertions. Python
    3.11 passed Quicknet 6/6 in 535.647147ms and all 1,047 tests with 22
    environment-specific skips in 856.889s, with a 14m50s job duration.
    Python 3.13 passed Quicknet 6/6 in 525.265295ms and the same 1,047-test,
    22-skip suite in 944.686s, with a 16m20s job duration. Python 3.14 passed
    Quicknet 6/6 in 527.783322ms and that suite in 895.407s, with a 15m28s
    job duration. Every matrix job passed Ruff, accepted all 181 checked files
    as formatted, reported zero Pyright errors, warnings, or information
    messages, and built both the sdist and wheel.
    Source commit `cd583fb12b12a80d132c80e8a3465e53f5c3151a` implements
    the planned post-start sequence:
    unit-kill dispatch, client `killpg`, conditional unit-kill retry, bounded
    `communicate`, and bounded `wait` with one retry. Timeout output is gated
    on both client reaping and at least one zero-status unit-kill dispatch;
    zero means dispatch acknowledgement, not proof that the cgroup is empty.
    Negative client status enters cleanup before output or handshake reads.
    Primary `BaseException` identity, first cleanup-interrupt identity after an
    ordinary primary, nonblocking descriptor reads, FD/temp cleanup, and exact
    main-client/verified-handshake counters are covered while the public API
    stays unchanged. Repeated hostile interruption remains an explicit bounded
    best-effort residual.
    Source-commit-bound focused validation passed twice: 47 tests with six skips
    under both the normal interpreter and exact CPython 3.12.11; the combined
    evaluator/worker-wire suites passed 51 tests without skips. Two independent
    code audits of diff SHA-256
    `7069fbae6e9749c401f00ef35b5e5cc8c74d0e262f00626c95d4a7192d71115d`
    each reported zero blockers, zero major findings, and zero minor findings.
    The first full run reached 1,078 tests with 19 skips and recorded
    four Quicknet failure/error outcomes (two failures and two errors). All four
    outcomes were fail-closed mode checks rejecting `0664`/`0775` Noble modes inherited
    from umask. Bytes, hashes, and the source diff were unchanged; worktree-only
    `chmod go-w` restored `0644`/`0755`, and focused Quicknet passed. This first
    attempt remains a failed historical validation event.
    After normalization, all 23 Quicknet tests passed. The clean full rerun
    passed all 1,078 repository tests with 19 environment-specific skips in
    1213.871s, with a 1214.88s external wall duration. Ruff lint passed, Ruff
    format accepted all 181 checked files, and Pyright reported zero errors,
    warnings, or information messages. Distribution checks passed for a
    337-member sdist and 163-member wheel, including path, private-material,
    and source-hash assertions. Gitleaks scanned 65 commits and approximately
    7.15 MB with no leaks, and the public-boundary check passed.
    Public-CI
    [run 30623782622](/megu0xxx0x/indus-open-benchmark/actions/runs/30623782622)
    used event `push` at exact head SHA
    `cd583fb12b12a80d132c80e8a3465e53f5c3151a`, completed with conclusion
    `success`, and left all three matrix jobs green. The overall run window was
    `2026-07-31`, `10:30:29Z`–`10:46:17Z` (15m48s). Every Quicknet
    job asserted Node `v24.18.1` on Linux/x64 and recorded failed, cancelled,
    skipped, and todo counts of zero. Python 3.11 ran
    `10:30:33Z`–`10:44:34Z` (14m01s), Quicknet 6/6 at
    `duration_ms=615.588048`, and unittest 1078 tests with 22 skipped in
    808.435s. Python 3.13 ran `10:30:32Z`–`10:39:02Z` (8m30s), Quicknet 6/6
    at `duration_ms=292.030965`, and unittest 1078 tests with 22 skipped in
    483.182s. Python 3.14 ran `10:30:32Z`–`10:46:16Z` (15m44s), Quicknet 6/6
    at `duration_ms=565.70517`, and unittest 1078 tests with 22 skipped in
    906.229s. Each job also passed Ruff lint, Ruff format with 181 files already
    formatted, Pyright with zero errors, warnings, or information messages,
    and sdist plus wheel builds. The CI count is 22 skipped tests per job; the
    clean local result's 19 skips remain a distinct measurement.
    Tests use controlled process doubles and one inert local sleep group, with
    no real systemd service or project worker. The separate supported
    host-runtime/dynamic-closure sub-gate remains open.
    No freeze, target, data, worker, detector, decipherment, or prize action is
    authorized or performed by this work.
  - [ ] Implement an official one-shot runner only after those gates. It must
    internally construct and own an exact `SandboxedWorkerInvoker`, permit no
    caller-supplied invoker or factory, verify its process and invocation
    counters, and bind the result to the one-shot state transition. The
    current evaluator's injected-invoker result remains a non-attestation.
    Git authenticity, commit-to-checkout equality, trusted time, artifact
    custody, and privileged-actor controls remain external. This step does
    not authorize a freeze, target selection or fetch, C3 execution,
    detector, real-source access, decipherment claim, or prize action.
  - [ ] Obtain two genuinely separate human passes, compare them only after
    sealing, complete no-invention adjudication, and retain future-evaluation
    values outside detector custody. This is the promotion gate for externally
    grounded reference evidence and detector scoring, not a prerequisite for
    provisional machine-assisted research.
- [ ] Extract the 57-page KP1979 identifier-order base lane first, then
  reconcile records against the sorted-from-end and sorted-from-beginning
  reprints without using sign sequences as join keys. Exposed machine geometry
  may support provisional extraction, but it cannot admit rows to an accepted
  corpus or supply a detector score.
- [ ] Implement the 1980 versioned-delta, bidirectional cross-reference, and
  state-carrying duplicate-list parsers. Preserve strict, loose,
  exact-sequence, ancient repetition, and physical-object relations
  separately.
- [ ] Freeze the exact KP1982 concordance page map after the KP1979/1980
  record spine exists; use page 22 as the negative control and pages 23–201
  as occurrence-level consistency evidence.
- [ ] Define a deterministic 80–120-slot stratified calibration tranche.
  This fast lane does not complete or weaken the separate full-700 Batch 0
  contract.
- [ ] Generate source-bound, abstaining machine proposals over pages 23–201,
  require empty output on page 22, and freeze the recognizer before sealed
  evaluation. This is a later occurrence-audit lane; do not auto-admit
  unreviewed output.
- [ ] Implement edition-preserving corpus adapters and uncertainty-bearing
  crosswalks before importing any rights-compatible export.
- [ ] Build an ASI/NMMA candidate index containing only official record IDs
  and official landing URLs. Do not copy catalogue metadata or images without
  a separate reuse basis; do not call all 413 site-origin candidates
  inscribed objects.
- [ ] Preregister numeral/metrology and repeated-tablet functional-anchor
  tests with site, period, medium, and object holdouts.
- [ ] Run equal-budget linguistic, non-linguistic, hybrid, and multilingual
  hypotheses against the same sealed tests and matched controls.

## Current source track — Submission integrity (Unreleased)

- [x] P1: deterministic complete inventory below a caller-selected candidate
  root, with closed roles and entrypoint binding; explicitly no trusted-time,
  confidentiality, custody, blind, runtime, or result claim.
- [ ] P2: independently held private companion and authenticated B/S receipt.
  Blocked until a real external custodian, storage/access procedure, and
  explicit authority exist.
- [ ] P3: isolated run lock and result receipt. Blocked on P2, a fixed runtime
  contract, and independent execution authority.

## Current data track — Private readiness (Unreleased)

- [x] Privacy-minimized physical-tree scan with fixed public summary,
  private aggregate report, two complete keyed inventories, and fail-closed
  storage/content checks.
- [x] Closed per-file private policy and derived local-use compatibility gate.
- [x] Exact-byte-bound deny-all review bundle and value-free structural
  quarantine ledger with atomic no-replace private publication.
- [ ] Curate an exact private policy for an authorized non-public corpus. Automatic
  inference from filenames, public availability, or embedded metadata is not
  accepted as rights evidence.
- [ ] Normalize only policy-compatible layers, retain duplicate aliases, and
  quarantine malformed records without deletion.

## Current transcription track — Evidence before interpretation (Unreleased)

- [x] Closed sign-inventory and unsealed review/adjudication draft contracts,
  exact-byte and semantic verification, double-review comparison, and one
  non-overwriting private promotion receipt.
- [x] Keep left-to-right visual indexing separate from reading direction,
  restrict v0.1 geometry to normalized axis-aligned rectangles, and preserve
  unknown direction and unresolved signs.
- [x] Disable public export and evaluation admission; write detailed reports
  and promoted artifacts only as new `0600` files under a pre-existing
  physical owner-only `0700` parent.
- [x] Implement a closed fixed-source contract and network-free exact-byte
  verifier for the official Helsinki 1982 PDF and canonical target-page PBMs.
- [x] Generate a deterministic private proposal for all 700 fixed row slots,
  including exact cell/context rectangles and crop hashes, from a byte-pinned
  provisional seed and the verified page pixels.
- [x] Prepare and exact-byte-verify a closed 700-cell bootstrap assignment
  that retains proposed locator/context rectangles and crop commitments while
  structurally withholding machine occupancy, OCR, identifier, and accepted
  observation values.
- [ ] Freeze visually audited per-lane row boundaries, context crops, and crop
  commitments; generated values remain proposals until independent review.
- [x] Implement the non-circular human bootstrap-review and adjudication
  contract, reviewer-safe assignment/PBM verification, exact crop rehashing,
  private count-bearing two-review audit, and no-invention adjudication gate.
  These software checks do not prove human authorship or independence.
- [ ] Execute the pages 20–21 Batch 0 sign-list protocol with two genuinely
  independent reviewers and a distinct adjudicator. No such execution or
  reviewer-independence claim is part of the public source tree. Full
  completion remains a high-assurance inventory path, not a prerequisite for
  the separate stratified concordance fast lane.
- [ ] Design an allowlist-only exporter and separate corpus-admission review.
  Neither becomes authorized merely because a private receipt validates.

## v0.2 — Rights-cleared image workflow

- [x] Implement fail-closed museum intake, item-rights evidence, bundle
  verification, catalog-blind packet preparation, isolated custody mapping,
  and synthetic integration coverage.
- [ ] Complete an authorized review under a separately approved private
  operating procedure. Executed private paths, inventories, byte totals,
  digests, and results are not public roadmap records.
- [ ] Complete two independent human-observation passes per subject and
  adjudication before any carrier, physical-surface, relationship, ROI, or
  exact-crosswalk promotion.
- [ ] Negotiate source agreements under separately authorized outreach.
- [x] Derive the first exact-byte Penn metadata context registry: five
  originality-pending Chanhu-Daro candidates plus 29 replica/modern negative
  controls, with no image, transcription, field-number, or meaning approval.
- [ ] Resolve the SF 3051/2558 identity collision and SF 3495 room/locus
  conflict through separately reviewed primary evidence before context
  admission.
- [ ] Prioritize a context-rich 150–250-artifact target set. Expand toward
  500–1,000 only while new batches improve coverage, add contexts or anchors,
  or change hypothesis discrimination.
- [ ] Double annotation and adjudication.
- [ ] IIIF manifests, token geometry, image hashes, and duplicate-family graph.
- [ ] Frozen internal development set and institution-held test set.

## Active analysis track / v0.3 packaging — Matched stress tests

These experiments begin on the smallest admissible data now; they do not wait
for the v0.2 volume target.

- [x] Project-authored synthetic known-truth degradation gate with
  duplicate-family splits, family weighting, family-vector permutation nulls,
  and anchor-free abstention.
- [x] Preserve the aborted V1 invocation of the first rights-cleared
  known-script instrument, including its public freeze and path-free
  integrity error. V1 emitted no aggregate result, null distribution,
  decision reference, p-value, `GO`, or `NO_GO`.
- [x] Freeze the corrected V2 MTAAC instrument with exact family-mass/vector
  validation, pre-metric clean/mild permutation plans, and replica-stable
  accumulation. Source, split, degradation, seeds, model design, support
  gates, and thresholds are unchanged.
- [x] Execute the corrected frozen MTAAC V2 run once, without post-result
  retuning. It returned `NO_GO`: every binding gate passed except mild
  `settlement_name` recall, 0.193553 against the frozen minimum 0.35.
- [x] Reserve the exact CC0 ORACC ED3b administrative source, after a fixed
  audit-example exclusion, before V3 model fitting. The source is public;
  gold-conditioned GDL-key safety aggregates informed its sanitizer, so it is
  prospective validation rather than feature-unseen or binding confirmation.
- [x] Implement V3 explicitly as post-result work without rewriting V2:
  joint five-state prediction over every retained token, class balancing,
  line-sequence decoding, grouped nested development validation, and no use
  of the V2 holdout or ORACC records for candidate fitting or selection.
- [x] Publish the exact V3 code/plan freeze, execute the MTAAC training-side
  development protocol once, and preserve its aggregate negative result.
  `gamma = 0.5, lambda = 0` was selected; mild macro-F1 is 0.3243 and
  worst-state recall is 0.0369.
- [x] Define and implement V4 under a separate exact-byte development freeze:
  target-batch, partition/regime-local leave-one-family-out distributional
  features; one fixed L2 linear-chain CRF; deterministic dependency-free
  L-BFGS; nonselecting ablations; the exact V3 outer assignments; and
  predeclared advance/kill gates. Reusing MTAAC remains adaptive method
  development, not new held-out evidence.
- [x] Execute the exact V4 MTAAC command once at its public code-and-plan
  freeze and preserve the aggregate result. Mild macro-F1 improved to 0.3878
  with positive V3 deltas in all five folds, but mild `unit` recall 0.3052 and
  `settlement_name` recall 0.0429 failed their frozen floors. The terminal
  decision is `development_killed`; no final model was fitted.
- [x] Keep the prospective source unexecuted and unscored after the V4 kill.
  This protocol cannot define or execute a prospective evaluator, and its
  source qualification remains neither performance evidence nor binding
  confirmation.
- [x] Freeze one final V5 code-and-plan attempt rather than open-ended tuning.
  It retains the V4 observations, profile, folds, sequence structure,
  parameter count, and optimizer; changes only the fixed emission contrast
  regularizer; searches no weight or grouping; and requires rare-state
  precision, recall, paired-fold, and clean gates. MTAAC retires after the
  single valid result regardless of outcome.
- [x] Execute the exact V5 network-free command once at its public
  code-and-plan freeze and preserve the aggregate result. V5 passed 7 of 15
  gates and returned `mtaac_retired`: mild macro-F1 was 0.3846, `unit` recall
  was 0.2937, and `settlement_name` recall was 0.0575. No final model was
  fitted; the V2 holdout and prospective source remained unscored.
- [x] Retire MTAAC after the valid V5 result. Do not rerun, retune, repair, or
  replace V5, and do not create V6. Any next model claim must use a separately
  preregistered task and genuinely independent evidence.
- [ ] Freeze a non-cherry-pickable binding-confirmation source-selection
  mechanism: independent custody before development or a public random beacon
  over a predeclared eligible pool after model freeze. It must select a
  different, previously uninspected corpus; an ED3b post-hoc split is invalid.
- [ ] Alternative sign inventories and direction lattices.
- [ ] Linguistic, accounting, emblematic, hybrid, and shuffled null models.
- [ ] Site, period, material, and object-type generalization reports.

## Separate publication gates

**Corpus release:** source, layer-specific redistribution rights, provenance,
and duplicate lineage are documented for every released item.

**Structural or functional partial result:** applicable leakage audits,
matched nulls, domain holdouts, uncertainty analysis, and independent
reproduction pass. Unresolved expert objections are published rather than
hidden behind a requirement for unanimous agreement.

**Phonetic, language, or translation claim:** the fixed mapping predicts
prospective or sealed material, survives edition/direction/allograph/domain
sensitivity, has multiple compatible independent anchors, and is reproduced
by a separate team.

**Prize submission:** an official operational scheme, required evidence,
responsible submitting authority, external-communication approval, and
submission package are separately verified. A source release never authorizes
submission by itself.

## v1.0 — Multi-institution benchmark, only after the gate

- Versioned, image-linked master register with documented permissions.
- Independent evaluation custodian and submission protocol.
- Prospective tests on newly catalogued or excavated material.
- Public replication packages, negative results, corrections, and retractions.
