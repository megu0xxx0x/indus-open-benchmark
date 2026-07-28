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

The global evidence audit has established a baseline and now continues as
recurring monitoring; it no longer blocks calibrated extraction and
falsifiable functional tests. It is not model-led translation, an external
corpus release, a decipherment claim, a blind result, or a prize submission.
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
```

The final command checks every canonical PBM byte and pixel digest, so a
different image count, mapping, encoding, or decoder result fails closed.
Pixel-equivalent but differently encoded PBMs also fail because the V1
canonical byte representation is fixed. The audit emits no candidate count or
identifier. A passing result establishes exact input pixels and page-class
detector gates only.

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
