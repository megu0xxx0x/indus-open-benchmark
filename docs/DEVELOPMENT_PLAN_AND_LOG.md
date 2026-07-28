# Public development plan and status

**Status date:** 2026-07-28

**Last source-level update:** 2026-07-28 10:42 JST (Asia/Tokyo)

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

- deterministically select an approximately 80–120-slot KP1982 calibration
  tranche without describing it as full Batch 0;
- freeze the exact page map, using page 22 as a negative control and pages
  23–201 as 179 concordance data pages;
- build a separate 8–12-page, 300–500-row development/sealed concordance
  reference because cell calibration cannot establish end-to-end accuracy;
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

Current assurance layers:

| Layer | Status |
|---|---|
| Public verifier code and synthetic tests | implemented; current release candidate |
| Real calibration or Batch 0 human execution | not executed or claimed |
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

### Data and source work

Safe next work:

- curate public source/provenance/rights evidence;
- inventory KP1982 concordance page classes and implement source-bound,
  abstaining extraction proposals;
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
- Unit/integration suite: 339 tests passed; 11 optional
  external-fixture tests were skipped by their declared environment gates.
- A separate owner-controlled exact-source run exercised the canonical page
  pixels and assignment through the relevant 35-test module: passed. No
  private path, inventory, or content value is recorded here.
- Source distribution and wheel build: passed.
- Local Markdown-link existence check: passed.
- Gitleaks current-tree and reachable-history scans: no finding.
- Semgrep: no finding across 328 applicable rules. One Python-before-3.7
  compatibility rule was excluded as inapplicable because the package requires
  Python 3.11 or newer.
- Trivy filesystem scan: no high/critical dependency vulnerability, secret, or
  detected misconfiguration finding.

These are source and packaging checks, not execution of a human review,
scientific validation, independent replication, or a decipherment result.
