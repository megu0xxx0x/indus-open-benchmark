# Data contracts

The repository defines the following JSON Schema Draft 2020-12 contracts:

- `schemas/source-registry.schema.json` — upstream sources, access, rights, and
  transformation provenance.
- `schemas/artifact.schema.json` — observation-only
  artifact → side → line → token records.
- `schemas/hypothesis.schema.json` — versioned interpretations, mappings,
  assumptions, exceptions, and prospective predictions.
- `schemas/research-entry.schema.json` — a global evidence ledger with claim
  attribution, evidence tier, limitations, falsification, rights, lineage, and
  scheduled review.
- `schemas/museum-intake.schema.json` — rights-gated, untranscribed museum API
  records and downloaded-media integrity evidence before artifact promotion.
- `schemas/museum-review-subject.schema.json` — opaque, catalog-blind groupings
  of exact private evidence images for human observation.
- `schemas/museum-review.schema.json` (v0.2) — append-only independent reviews,
  digest-bound corrections, and adjudications that stop before sign
  segmentation or interpretation.
- `schemas/museum-review-ledger.schema.json` — a private packet-bound controller
  for canonical digest-named review files.
- `schemas/penn-metadata-snapshot.schema.json` — a closed, image-free Penn
  Museum CSV candidate snapshot with CC BY 4.0 provenance.
- `schemas/context-anchor-registry.schema.json` — a deterministic Penn
  primary-script context registry with raw metadata axes, replica negative
  controls, exact snapshot provenance, and all interpretive/field-number
  approval gates fixed closed.
- `schemas/smithsonian-metadata-record.schema.json` (v0.2) — one exact
  Smithsonian AWS JSONL record, bound to its raw container and independently
  gated metadata/media rights.
- `schemas/quarantine-manifest.schema.json` — content-addressed, fail-closed
  source, locator, revision, rights, and purpose rules.
- `schemas/evaluator-config.schema.json` — closed public-development evaluator
  entrypoint, commands, metrics, and seeds.
- `schemas/split-manifest.schema.json` (v0.2) — exactly two public
  train/development partitions with exact-byte and leakage commitments.
- `schemas/benchmark-lock.schema.json` — an exact-byte, explicitly unanchored
  public-development definition lock.
- `schemas/submission-commitment.schema.json` (v0.1.0) — a deterministic
  complete-tree submission-layer commitment to a caller-declared benchmark
  definition digest.
- `schemas/private-corpus-policy.schema.json` (v0.2.0) — a closed private
  curator declaration with one exact path, private content commitment,
  review state, and intended-use decision per file; it contains no
  self-asserted readiness or assurance fields.
- `schemas/private-corpus-readiness.schema.json` (v0.2.0) — a path-, name-,
  identifier-, value-, and digest-free aggregate report for one local
  point-in-time readiness audit.
- `schemas/private-structural-quarantine.schema.json` (v0.1.0) — a private,
  policy-indexed and content-bound ledger of fixed structural findings that
  contains no source row, header, source/catalog identifier, path, or
  exception text.
- `schemas/private-review-bundle.schema.json` (v0.1.0) — the closed atomic
  envelope for one policy draft and its structural quarantine ledger.
- `schemas/kp1979-corpus-source.schema.json` (v0.1.0) — the exact official
  KP1979 PDF identity, section ranges, page-number relation, and native image
  geometry; it contains no transcription.
- `schemas/kp1979-page-map.schema.json` (v0.1.0) — the complete exact native
  PBM commitments for PDF pages 2–180, audited page classes, proposal-only
  detector bands, exclusions, and value-free layout protocol.
- `schemas/kp1979-row-assignment.schema.json` (v0.1.0) — a closed private
  assignment for proposal-only label and row-context crops on the 57
  identifier-order pages; OCR, identifiers, codes, signs, occupancy,
  direction, interpretation, and external manual values are withheld.
- `schemas/kp1979-sign-template-roster.schema.json` (v0.1.0) — a closed
  private, catalog/geometry-bound machine-provisional roster of committed
  canonical glyph PBMs and shape-class ranks. It contains no accepted sign
  identity, row transcription, reading, language, meaning, or translation.
- `schemas/kp1979-row-match-proposal.schema.json` (v0.1.0) — a closed
  development-only envelope for language-blind row-shape proposals, their
  raw input commitments, observed separator provenance, and at most three
  deterministic candidate paths. It does not accept row geometry, sign
  sequences, reading direction, interpretation, evaluation admission, or a
  decipherment.
- `schemas/kp1979-row-match-proposal-v2.schema.json` (v0.2.0) — a separate
  closed development-only envelope bound to an exactly recomputed V3
  candidate-ranking plan. Tier B remains provisional and nonaccepted, speck
  robustness and real-row tiers are not claimed, and no sign sequence or
  interpretation is accepted.
- `schemas/kp1979-label-reference-assignment.schema.json` (v0.1.0) — a
  proposal-free, six-page reviewer assignment for exactly one fixed KP1979
  development or future-evaluation partition. It binds source pixels and
  coordinate rules while omitting page classes, detector geometry, candidate
  counts, OCR, and manual values.
- `schemas/kp1979-label-reference-review.schema.json` (v0.2.0) — one private
  geometry-only label review bound to the proposal-free assignment. It
  distinguishes an independent pass from an exposed, development-only machine
  pass that is ineligible as external reference evidence or detector-scoring
  input. Both record physical-lane label rectangles and exact crop commitments
  without recording identifier, code, sign, direction, language, meaning, or
  translation values.
- `schemas/kp1982-batch0-source.schema.json` (v0.1.0) — the exact official
  KP1982 PDF identity, target-page indices, embedded-image geometry, and
  canonical PBM commitments; it contains no transcription.
- `schemas/kp1982-layout-seed.schema.json` (v0.1.0) — provisional lane and
  per-lane row-fit measurements for visual double review; every acceptance
  assurance is fixed false.
- `schemas/kp1982-layout-proposal.schema.json` (v0.1.0) — a private,
  deterministic 700-cell proposal with fixed source/seed/page commitments,
  integer cell/context rectangles, and exact crop hashes; every human-review,
  identifier, and decipherment assurance is fixed false.
- `schemas/kp1982-bootstrap-assignment.schema.json` (v0.1.0) — a closed,
  proposal-value-stripped 700-cell reviewer assignment bound to the exact
  source, seed, canonical layout proposal, and page pixels. It retains only
  proposed locator/context rectangles and crop commitments while structurally
  excluding machine answer and accepted-observation values.
- `schemas/kp1982-bootstrap-review.schema.json` (v0.1.0) — a closed private
  record for either one inventory-bootstrap pass or a later adjudication,
  without a pre-existing sign inventory. It separates upper and lower raw
  identifiers and their crops, glyph evidence, printed marks, condition, and
  uncertainty. Adjudication binds two exact review inputs and forbids a third
  invented observation.
- `schemas/sign-inventory.schema.json` (v0.1.0) — a versioned visual sign
  inventory that keeps primary published identifiers, repeated catalog ranks,
  graphic evidence, and doubt marks separate from interpretation.
- `schemas/transcription-review.schema.json` (v0.1.0) — unsealed,
  image-bound independent transcription and adjudication drafts for private
  staging only.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.
JSON objects use UTF-8. Times use RFC 3339 UTC where possible. Corpus files use
JSON Lines: one complete artifact object per non-blank line.

## KP1979 fixed corpus source and page map

`registry/kp1979_corpus.json` binds the official 180-page PDF and its section
roles. `registry/kp1979_page_map.json` binds the canonical 4880×7010 one-bit
PBM for every PDF page from 2 through 180, including both the complete PBM
digest and packed pixel-payload digest.

The page map separates:

- non-corpus and sign-list negative controls;
- the identifier-order base corpus;
- normal sorted-from-end pages;
- the eight- and six-column auxiliary grids;
- normal sorted-from-beginning pages; and
- an explicit, predeclared prose mask on the terminal page.

Detector scan bands and their returned rectangles cover only printed label
slots, not full inscription rows. The terminal mask is a rule, not evidence
that the detector recognized prose. The page-level
`contains_linguistic_sequence_candidates` flag never admits every row on a
mixed page such as page 128.

Detector scan bands are proposal geometry, not accepted labels. The
`audit-kp1979-layout` command verifies the exact PDF and all mapped PBMs, then
runs a pixel-only lattice detector. It emits no candidate count or identifier.
A passing audit means only that the source pixels and current page-class gates
match. It does not establish label-position accuracy, row segmentation,
reading order, accepted geometry, identifier transcription, sign
transcription, three-way reconciliation, or decipherment.

`prepare-kp1979-row-assignment` repeats that complete audit and separately
re-reads PDF pages 22–78. The resulting private manifest binds each proposed
label rectangle and its wider row-review rectangle to canonical PBM crop
hashes and byte sizes. `verify-kp1979-row-assignment` independently rebuilds
the manifest and requires canonical byte equality. Stable slot IDs encode only
PDF page, visual lane, and top-to-bottom visual position; they do not encode
an inscription identifier, occupancy decision, reading order, or accepted
row. The schema fixes all acceptance, review, publication, evaluation, and
decipherment assurances false.

Schema validation alone is not an evidence attestation. Relationships among a
slot ID, page, lane, rectangles, pixels, and crop commitments require the
canonical verifier; only exact reconstruction from the fixed PDF and PBMs may
return a valid assignment summary.

## KP1979 provisional templates and development-only row matching

The sign-template roster binds one canonical machine-provisional catalog, its
catalog/geometry manifest, and each manifest-addressed canonical raw PBM glyph.
The builder checks the catalog/geometry join, the committed PBM byte size and
digest, exact P4 encoding, dimensions, and nonempty ink before recording a
variant and provisional shape-class rank. Multiple variants may share a rank;
the matcher scores only the best variant per rank so a rank gains no bonus from
having more variants. Neither a roster field nor schema validity makes the
catalog rank final, proves the source pages, accepts geometry, or establishes a
sign identity. The canonical roster builder/verifier must recompute these
relationships from the supplied raw bytes.

The template-only matcher plan is a canonical structure containing its
protocol and matcher identities, roster commitment, integer configuration,
claim scope, fold protocol, selection rule, closed-set control summaries,
open-set leave-one-variant-out negative control, normalized-equality report,
and fixed-false assurances. Before any development row loader is called, the
row-proposal builder reloads every roster-addressed raw glyph PBM, verifies its
commitment, rebuilds the template index, recomputes the complete matcher plan
from those exact PBM bytes, and requires canonical byte equality with the
supplied plan. It then rechecks the frozen identity and scope gates. Merely
matching the plan's JSON shape or repeating its recorded metrics is
insufficient. The frozen claim is limited to closed-template near-exact
retrieval; the open-set control is not used for threshold selection and does
not demonstrate allograph generalization or real-row performance.

The row-proposal builder consumes an already-created canonical row assignment;
it binds those raw assignment bytes but deliberately does not call the
assignment's source-pixel recomputing verifier. For each allowed development
slot, the caller-supplied row loader must return bytes matching the assignment's
row-crop commitment and dimensions. Separation never treats a proposed label
rectangle edge as observed truth. It compares maximal full-height white gaps
that overlap or contact the locator plus its nearest observed neighbours,
retains deterministic global top-three shape paths with separator provenance,
and abstains when different separator candidates support different best path
signatures. These remain machine proposals, not transcriptions.

The development allowlist covers only public PDF pages 22–77. The canonical
row assignment may also contain the reserved page 78, but this matcher run
filters its slot IDs before creating or invoking the row loader; therefore this
specific run does not load page-78 row pixels. That narrow property does not
claim that page 78, its source file, or its pixels were inaccessible to other
tools or earlier assignment construction, and it does not by itself establish
blind evaluation.

Roster and row-proposal artifacts contain private commitments and provisional
values. Generated files should be kept in owner-only storage and must not be
published without a separate disclosure review. The pure Python builders
return objects and cannot enforce storage permissions; the roster CLI adds
physical-directory, owner-permission, no-replace, and exact-byte checks. No
public row-proposal CLI is documented unless such an entrypoint exists.

## KP1982 fixed source and transcription bootstrap

`registry/kp1982_batch0.json` binds the official PDF and one-based pages 20–21
(zero-based indices 19–20). Each target is a 4888×6705 one-bit embedded image
with a canonical raw PBM commitment. The PBM coordinate origin is top-left;
rectangles use integer half-open bounds. Normalized coordinates are derived,
not normative.

The source verifier checks caller-supplied PDF and optional PBM bytes without
network access. Exact byte identity does not reparse PDF page structure,
validate crop coordinates, prove external rights, or create a sign inventory.
The sign-list pages have no text layer, and OCR output is proposal-only.

`propose-kp1982-layout` accepts only the byte-pinned provisional layout seed
and verified target PBMs. It deterministically derives 35 half-pitch row slots
for each of ten lanes on both pages and hashes both the non-overlapping cell
crop and fixed 32-pixel padded context crop. It writes a new private file
without replacing an existing destination. A cell crop is only a locator and
may split foreground. The context is a reviewer aid, not accepted glyph
evidence. `verify-kp1982-layout` MUST rebuild the complete proposal from the
fixed PBMs and require its canonical exact bytes before any downstream use;
schema validation alone does not prove cell coverage, rectangle semantics, or
crop hashes. The V1 canonical manifest byte size and digest are pinned in the
implementation so an algorithm change must use a new manifest version.
The CLI verifier additionally requires a stable single-link owner-owned `0600`
proposal below a physical, pinned, owner-only `0700` parent. Generated
rectangles and provisional occupancy labels remain review prompts, not
accepted observations.

The 32-pixel context was selected by an eight-connected-component audit of the
two fixed pages. Under the proposal-only rule assigning a component to the cell
with maximum black-pixel overlap (ties by manifest order), it contains each
owner component on these pages. The proposal records this as the padding basis,
while its machine-recomputed component-coverage assurance remains false. It
does not determine the semantic ownership of disconnected quotation-like or
doubt-like marks, and it must not replace visual double review.

The bootstrap-assignment preparation layer rebuilds the canonical layout
proposal and derives exactly 700 assignment cells. Each cell may carry only
its stable page/lane/row identity, proposed cell/context rectangles, and the
two crop commitments. Machine occupancy and accepted-occupancy values, OCR
output, machine identifier proposals, and accepted observation fields are
forbidden recursively. Exact-byte verification rebuilds the assignment rather
than trusting its assurance fields. Schema validity alone does not accept
geometry, establish reviewer independence or blinding, authorize public
release, admit evaluation data, establish a decipherment, or support a prize
claim.

The sign-inventory bootstrap must precede `transcription-review.schema.json`.
Using an already-created inventory to “review” the pages from which that same
inventory was derived would be circular. The dedicated bootstrap-review
contract instead binds each independent pass directly to the exact
proposal-value-stripped assignment and canonical PBMs. Its verifier requires
the complete ordered roster, rehashes every submitted crop, rejects
interpretive fields and control characters, and keeps the upper catalog rank,
lower primary identifier, glyph-with-marks crop, surrounding printed marks,
condition, uncertainty, and unresolved readings separate. Every reviewed cell
and observation crop must remain within that cell's reviewed context, although
a corrected context may extend beyond the original proposal.

The two-review audit accepts exactly two semantically valid independent-pass
byte records for the same assignment and requires different review, actor,
and review-assignment IDs; `review_id` is the pass/session identifier. Its
detailed result may contain record commitments, pseudonymous IDs, and aggregate
counts plus cell-level mismatch locations and field codes, but never raw
identifier observations; it remains private. The CLI emits only a fixed
count-free summary. Distinct declarations do not prove distinct humans or real
independence. Adjudication binds the exact bytes of both inputs, covers every
assignment cell, and may select one input observation or leave it unresolved.
It cannot invent an identifier, geometry, crop, or printed-mark set. Schema
validity alone cannot enforce those cross-record rules; the exact-byte semantic
verifier is required.

Every human-authorship, real-world independence/non-exposure, custody, rights,
public-release, evaluation-admission, decipherment, and prize assurance remains
false. No actual bootstrap review or adjudication is claimed complete.

## Private corpus readiness

The private policy and derived readiness report are deliberately separate.
The policy records curator evidence and binds each decision to exact source
bytes. Trusted code derives coverage, content-binding, review,
compatibility, and fixed-false assurance fields; callers cannot inject a
`ready`, blind, decipherment, or prize claim into the policy.

`prepare-private-review` publishes the policy and structural ledger together
as one `0600` no-replace private JSON bundle. Every generated entry starts
with `curation_status: pending`, unknown source/content/rights/provenance,
missing rights evidence, and no permitted uses. The ledger refers to policy
entries by index and private digest, so it need not repeat filenames or paths.
It stores only fixed anomaly codes and numeric structural positions; it never
copies cells, headers, source values, source/catalog identifiers, or parser
exception text.
The bundle schema, embedded policy schema, and embedded ledger schema are all
normative and MUST be validated.

Every policy path must correspond to exactly one physical single-link file.
The current bytes must match `content_sha256`, and `curation_status` must be
`reviewed`; a matching path alone is insufficient. A content digest is only a
replacement detector. It is not evidence of rights, provenance,
confidentiality, custody, or trusted time.
Unknown or quarantined sources, partial/disputed provenance, missing or
ambiguous rights evidence, restricted/unknown rights, content-layer mismatch,
and intended-use mismatch all block readiness. `metadata_only` never
authorizes images, transcriptions, catalog scans, model artifacts, training,
or redistribution.

The report contains aggregate counts only and is still private by default.
The terminal summary is narrower and contains no timestamp or count. See the
[private corpus readiness audit](PRIVATE_CORPUS_READINESS.md) for the
filesystem and claim boundary.

## Observation and interpretation boundary

`artifact.schema.json` contains observations and faithfully transcribed source
assertions. It MUST NOT contain translations, phonetic values, language labels,
semantic glosses, or a claimed decipherment. Those belong in a separately
versioned `hypothesis.schema.json` record.

An uncertain observation is not silently repaired. A damaged or unidentified
sign uses `sign_id: null`, an explicit `condition`, a numeric `confidence`, and
an `uncertainty` object. Plausible catalog labels MAY be preserved in
`uncertainty.alternatives`; they are alternatives, not ground truth.

Likewise, a catalog's proposed reading direction may be recorded with
`direction_confidence`, but the image-coordinate order is never rewritten to
make that reading direction look natural. A competing direction or
interpretation can be preregistered as a hypothesis.

## Artifact identity and provenance

Every artifact has a project-stable `artifact_id`. It is distinct from any
museum accession number or scholarly catalog number.

`catalog_crosswalk` preserves those upstream identifiers. It MAY be empty when
no responsible match has been established. Each match carries its own
certainty. Implementations MUST treat repeated high-confidence catalog
identifiers across artifacts as a possible duplicate, not as independent
evidence.

Each `source_records` entry has:

- a local, stable `source_record_id`;
- a `source_id` that resolves to the source registry;
- the exact `upstream_record_id`;
- its role in the artifact record;
- locator and retrieval time when known;
- upstream `revision` and `source_path` when known;
- an optional hash of the retrieved record.

`token.source_record_ids` MUST refer to local `source_record_id` values in the
same artifact. Source-record IDs MUST be unique within an artifact. This
explicit reference prevents a token copied from one transcription from being
mistaken for an independent reading.

No restricted image or source text is committed merely because its metadata
can be redistributed. `rights.status: "metadata_only"` means that only the
described metadata/transcription is in scope. In this case, `images` and
`side.image_ids` MAY be empty; an image URI, hash, or license MUST NOT be
fabricated.

## Rights

Rights are recorded at both artifact-metadata and image level because those
layers often have different licenses. The following fields are mandatory:

- `status`: `public_domain`, `open_licensed`, `permission_granted`,
  `metadata_only`, `restricted`, or `unknown`;
- `license_id` and `license_uri`, nullable when no verified license exists;
- `rights_holder`, nullable when unknown;
- separate `redistribution`, `derivatives`, and nullable `commercial_use`
  decisions;
- a human-readable `statement`;
- the evidence URL and verification time when available.

`unknown` never implies permission. A pipeline MUST fail closed before
redistributing material unless `redistribution` is true and the rights evidence
has been reviewed under project policy. At artifact/image level,
`metadata_only`, `restricted`, and `unknown` require
`redistribution: false`. The source registry may separately document an
explicitly licensed metadata layer without granting rights to an artifact
record or image.

## Physical, visual, and reading order

The three concepts are deliberately separate:

1. `physical_form` states what is represented: a carved `matrix`, an
   `impression`/`seal_impression`, a `direct_inscription`, a drawing only, or an
   unknown form.
2. `visual_index` is zero-based left-to-right order in the supplied image or
   drawing. `visual_order_basis` is fixed to
   `left_to_right_in_image`.
3. `reading_index` is zero-based proposed reading order. It is `null` when no
   reading position is responsibly asserted.

A seal matrix and its impression are mirror images. Importers MUST preserve the
source representation and MUST NOT silently flip token order. For a
right-to-left three-sign impression, a valid pair of index sequences is:

```text
visual_index   0 1 2
reading_index  2 1 0
```

Within a line, `visual_index` values MUST be the exact permutation
`0..token_count-1`. When `reading_direction` is `unknown`, every
`reading_index` SHOULD be `null`. When a complete reading order is asserted,
non-null reading indexes MUST be the exact permutation
`0..token_count-1`. These cross-item constraints require semantic validation in
addition to JSON Schema.

## Token uncertainty and geometry

`confidence` is the confidence in the selected `sign_id`, not confidence in a
translation. It is always a number from 0 through 1. For unknown signs it
records the annotator's strongest identification probability, or `0` when
there is no supported identification.

Alternative probabilities MUST each lie in `[0, 1]`. When the alternatives
form an exhaustive distribution, they SHOULD sum to 1 within floating-point
tolerance. If unlisted possibilities remain, their sum MAY be below 1.

Token geometry is optional. When present, its `image_id` MUST resolve to an
image in the same artifact. A polygon has at least three points. Normalized
coordinates SHOULD lie in `[0, 1]`; pixel coordinates MUST lie within image
bounds. Images use content hashes of the form `sha256:<64 lowercase hex>`.

## Unknowns and extensions

Unknown values are represented by documented `null` values or explicit
`unknown` enum members. Empty strings are not substitutes for unknowns.

`extensions` is the sole lossless escape hatch for upstream fields not yet in
the normative contract. Keys MUST be namespace-qualified, for example:

```json
{
  "mayig:features": [0, 1, 0],
  "mayig:raw_damage": "?",
  "mayig:import_warnings": ["Unexpected glyph count preserved."]
}
```

Extension values are non-normative payload. Consumers MUST NOT promote them to
observations, labels, or ground truth without a reviewed schema migration.
Generic, unqualified keys are rejected.

## Research evidence ledger

`research-entry.schema.json` governs the registry of corpora, datasets,
databases, publications, preprints, software, institutions/projects, official
records, and policy/prize records. Its A–E evidence tier is a source-audit
priority, not a score for whether a decipherment is correct.

Each entry MUST:

- attribute its single bounded claim and distinguish a reported result,
  institutional statement, observed property, and interpretation;
- state direct or indirect supporting evidence and stable locators;
- preserve limitations and verification state instead of filling gaps;
- record a falsification or audit criterion and its current result;
- record access and redistribution rights independently of public
  availability;
- resolve upstream research/source lineage without cycles; and
- include access, verification, and next-review dates.

Preprint publication, peer review, code availability, and result replication
are separate facts. A verified record can faithfully document a disputed
claim; `verified` does not mean that the claim has been accepted as true.

## Museum intake staging

`museum-intake.schema.json` is deliberately narrower than the artifact
contract. It requires item-level reuse evidence, the exact API-response hash,
provider media roles, downloaded-file hashes and byte counts, unresolved
physical sides, and an unresolved catalog crosswalk. It contains no token,
sign, reading, language, or translation fields.

The raw response hash used by `item_rights.evidence` MUST equal the retrieval
hash. Download evidence is all-or-nothing: a `downloaded` medium has a hash,
byte count, content type, relative path, and timestamp; a `not_downloaded`
medium has all five fields set to null. Semantic tooling checks the
cross-field hash equality and rehashes private bundle files.

Provider `primary` and `alternate` roles are catalog placement, not physical
front/reverse assertions. Promotion to an artifact requires separate
crosswalk and annotation review.

## Smithsonian metadata intake

`smithsonian-metadata-record.schema.json` normalizes one selected line from a
caller-supplied official AWS JSONL shard. The semantic validator re-parses the
complete strict-UTF-8 container, recomputes its digest, byte count, selected
line offset/digest, canonical record digest, intake ID, classification, and
all rights decisions. A normalized JSON record is not self-verifying without
the committed raw JSONL bytes.

Metadata is approved only when the closed EDAN `metadata_usage` object has
uncontradicted `CC0` access. Each image is evaluated separately and remains
quarantined unless the record metadata, media usage, image type, exact
Smithsonian delivery URL, and record-level restriction checks all pass.
Missing media authorizes neither page scraping nor image retrieval. Candidate
classification never creates a transcription, physical-originality finding,
or publication permission.

## Museum human-observation review

The museum-review subject contract deliberately calls each intake row a review
subject, not an artifact. Opaque subject, view-group, and image IDs appear in
the reviewer layer. Institution, accession, title, provider URLs, media IDs,
and original paths remain in a separate private custody map.

Review records may describe carriers, observable surfaces, whole inscription
regions, damage, entity relationships, and authorized catalog-crosswalk
candidates. They cannot contain sign IDs, token segmentation, reading
direction, transcription, phonetic values, language assignments, meanings,
glosses, translations, or decipherment claims. Semantic validation checks this
boundary recursively.

Each review commits to the exact blind manifest, subject record, and complete
set of evidence-image hashes. Independent reviews have no prior-review inputs.
Adjudication requires at least two distinct sealed input hashes. An `exact`
crosswalk can be adopted only during adjudication, with collections or
archaeology expertise and an explicit counterevidence check.

The current packet generator copies exact bytes into a catalog-blind reviewer
subtree, keeps the identity mapping in a custody subtree, and refuses
publication while the source bundle lacks an independently controlled
manifest anchor. It does not allocate artifact or sign IDs.

## Hypotheses

A hypothesis is independently identifiable and versioned. It records:

- authors, license, status, and preregistration commitment;
- explicit scope and exclusions;
- assumptions with alternatives considered;
- sign mappings and formal or prose rules;
- falsifiable claims;
- prospective predictions with author-supplied registration fields;
- supporting and contradicting evidence;
- every registered exception.

`observation_ref` points into the artifact corpus without modifying it.
Hypothesis confidence is a claim author's estimate and MUST NOT be copied into
token confidence.

The current `created_at`, `registered_at`, `made_at`, `content_hash`, and
`commitment_hash` values are author-supplied. Schema validity does not prove
their time, authorship, or external receipt, and `status=preregistered` is not
currently cross-field-enforced against `frozen`, a registry URI, time, and
hash. Predictions intended for a blind test SHOULD be frozen before the
candidate is run on hidden inputs and before the hypothesis/submission team
receives hidden material or hidden-derived feedback. A real pre-access claim
requires an independently retained receipt binding exact `B` and `S` values;
a local Git timestamp, hypothesis timestamp, hash, or `S` alone is
insufficient. Updating a frozen mapping, rule, exception, or prediction
requires a new hypothesis version and a new `S`.
Use the [frozen payload template](PREREGISTRATION_TEMPLATE.md) inside the
candidate root and the separate
[external receipt envelope](PREREGISTRATION_RECEIPT_ENVELOPE_TEMPLATE.md)
outside `S` to avoid a digest self-reference.

The checked-in
[numeral/metrology functional-anchor protocol V1](NUMERAL_METROLOGY_FUNCTIONAL_ANCHOR_PROTOCOL_V1.md)
is a source-free `draft` instance of this schema. Because version 0.1.0 has no
typed metric, split, null, or terminal-state fields, that draft records them
in closed rule/formalism strings. Focused semantic tests lock decision-critical
fragments and the exact raw payload digest. Schema validity does not make
those prose rules executable or registered; a real run still
requires a new externally receipted version and typed evaluator/result
contracts.

The follow-on
[NMFA value-blind preregistration gate](NMFA_VALUE_BLIND_PREREGISTRATION_GATE_V1.md)
adds closed schemas for a protected structural manifest and private report,
plus a closed schema for its source-free gate plan. The manifest contains no
plaintext X or numeric Y. Before either protected layer is accessed, its
preinventory digest is designed to bind the exact source-record-to-F roster,
actual per-F C, physical-identity/context evidence, and prior-exposure map.
Later X/Y seals cover that same F roster. The report schema is structural only:
authenticity requires deterministic reexecution with the exact manifest and
evaluator bundle and byte equality. A schema-valid or synthetic candidate
state is not access authority, external registration, a scientific result, or
prize eligibility.

The additive
[NMFA activation preflight companion](NMFA_ACTIVATION_PREFLIGHT_V1.md) uses
four further Draft 2020-12 schemas: an immutable source-free plan, a
separately supplied trust profile, a `oneOf` PREMETADATA/PREVALUE protected
request, and a private deterministic report. Every object is closed. Opaque
identifiers use the fixed `hmac-sha256:` shape; signatures use canonical
unpadded base64url Ed25519 envelopes and never carry a public key. PREVALUE has
no schema fields for transcription or target values, value-bearing statuses,
eligibility, final G exclusion, predictions, scores, ciphertext, Merkle roots,
nonces, or actual seals. Schema validity alone is insufficient: the evaluator
recomputes resource, request, receipt, ledger, supplied-inventory, roster,
archive and report digests; verifies signatures against that profile; reexecutes
the exact PREMETADATA predecessor; and checks cross-field chronology and
declared-roster consistency. It does not prove external source-universe or
R0/Rpre completeness, provider-byte separation, or opaque-identifier origin.
The installed plan's five null activation identities force a private blocked
report even when the synthetic semantic core and signatures validate.

## Quarantine manifest

The quarantine manifest's canonical self-digest excludes only its
`manifest_sha256` field. Normal CLI paths resolve every source/image
`source_id`, apply purpose-specific rights, and match explicit source IDs,
HTTPS locator prefixes, and pinned revisions. Unknown and malformed provenance
fails closed.

An `audit_only` result MAY inspect denied material but MUST retain
`audit_only_override=true` and all findings. It MUST NOT be reused as corpus,
training, evaluation, or redistribution approval. Quarantine is an admission
gate, not proof that every allowed record is archaeologically authentic.

## Public-development split manifests and leakage

Splits are artifact-level. Randomly separating transcription rows is forbidden
because copies, impressions, catalog aliases, or identical short sequences can
otherwise occur in both training and development data.

Every manifest MUST group on all three primary leakage keys:

- `duplicate_family_id`;
- image content hash;
- normalized reading-order sequence hash.

Catalog crosswalk matches are also required to share a partition. Version 0.2
models exactly two public partitions, `train` and `development`, and lists all
self-auditing members. `membership_frozen=true` commits membership only;
`benchmark_locked=false`, `blind_claim_allowed=false`, and
`final_evaluation_eligible=false` are mandatory. A custodian-held hidden test
is outside this schema version. `image_hashes` MAY be empty for a metadata-only
artifact; missing images are never replaced with fabricated hashes.

Implementations MUST additionally verify:

- every public member artifact exists in the fingerprinted corpus;
- an artifact occurs in at most one partition;
- duplicate-family, image-hash, normalized-sequence, and catalog components do
  not cross partitions;
- `artifact_count` equals the disclosed member count for public partitions;
- a membership-frozen manifest has no listed leakage violations;
- the seed, normalization rule, corpus fingerprint, and software revision are
  recorded before evaluation.

JSON Schema cannot express all graph-wide uniqueness and referential rules.
Conforming tooling therefore performs both schema-shape and semantic
validation.

## Benchmark definition lock

The split manifest does not freeze the evaluator or runtime. Version 0.1 of the
benchmark definition additionally binds the exact corpus bytes; artifact,
source, quarantine, split, evaluator-config, and lock schemas; source and
quarantine registries; split manifest and files; evaluator config and supplied
source files; `pyproject.toml`; and `uv.lock`.

Its domain-separated canonical digest establishes local self-consistency only.
The schema forces `development_reproducibility`, forbids blind/final claims,
and declares the definition unanchored. Even an independently supplied
matching digest is reported as `expected_digest_match`; it is not a timestamp,
signature, custody receipt, runtime-isolation proof, or scientific external
anchor. See [BENCHMARK_LOCK.md](BENCHMARK_LOCK.md).

## Submission commitment

`submission-commitment.schema.json` schema version 0.1.0 and digest protocol
v0.1 form a separate deterministic contract for the submission layer `S`. It
binds one caller-declared digest of a separately verified benchmark
definition, a complete directory/regular-file inventory below a selected
root, exact file bytes, executable-bit state, closed roles, one entrypoint,
and static argument strings.

All objects are closed. Semantic validation additionally enforces canonical
entry and role ordering, a portable ASCII relative-path profile, path and
case-fold uniqueness, parent-directory closure, role counts, exact
entrypoint/source binding, derived counts, fixed byte/depth limits, and both
domain-separated self-digests. Files omitted from explicit role flags are
recorded as `runtime_input`; nothing below the submission root is ignored.

The assurance block is constant and cannot be supplied from committed file
content. It forbids blind, final, external-anchor, custody, trusted-time,
authorship, access-history, confidentiality, runtime, and result claims. The
format deliberately has no `created_at` or `created_by`: those assertions
require a later external receipt. The manifest is deterministic and
linkable—not hiding or encryption. See
[SUBMISSION_COMMITMENT.md](SUBMISSION_COMMITMENT.md).

## Synthetic fixture

`examples/synthetic_corpus.jsonl` contains no real inscription, image, or
archaeological assertion. Its first record demonstrates a right-to-left
impression with visual coordinates. Its second demonstrates metadata-only
provenance, empty image arrays, unknown reading order, and namespaced raw
extensions.

The standard library can verify that the contract and fixture files are valid
JSON:

```bash
python3 -m json.tool schemas/artifact.schema.json >/dev/null
python3 -m unittest tests.test_schema_examples
```

The package declares `jsonschema` as a runtime dependency so every normative
command can perform full Draft 2020-12 keyword evaluation.
