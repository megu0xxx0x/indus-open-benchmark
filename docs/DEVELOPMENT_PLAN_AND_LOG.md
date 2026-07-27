# Public development plan and status

**Status date:** 2026-07-28

**Last source-level update:** 2026-07-28 04:52 JST (Asia/Tokyo)

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
optional canonical PBM bytes. Independent Poppler and MuPDF decoding produced
pixel-identical 4888×6705 one-bit pages.

A fixed-seed generator recomputes all 700 cell and padded-context crop hashes
from the verified PBMs and writes only a private, no-replace proposal. The next
software layer now rebuilds that canonical proposal and prepares or verifies a
closed 700-cell reviewer assignment. It retains proposed locator/context
rectangles and crop commitments while structurally withholding machine
occupancy, OCR, identifier, and accepted-observation values.

This is preparation, not execution. Every geometry, occupancy, identifier,
human-review, real-world reviewer-independence/blinding, public-release,
evaluation-admission, and decipherment assurance remains false. The upper
catalog rank, lower primary source identifier, glyph, and printed marks must
still be observed in two genuinely independent human passes and resolved by a
distinct adjudicator under human-review contracts that are not yet
implemented. No actual Batch 0 review, promotion, rights verification,
decipherment, or prize result is part of this public update.

### Data and source work

Safe next work:

- curate public source/provenance/rights evidence;
- implement the Helsinki 1982 human bootstrap-review and adjudication
  contracts over the fixed, proposal-value-stripped assignment;
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
