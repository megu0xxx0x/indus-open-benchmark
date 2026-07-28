# Helsinki 1982 sign-list Batch 0 protocol

## Purpose

Batch 0 is the smallest fixed exercise for testing the private transcription
evidence bridge against a published sign list. It is a protocol and source
pin, not a completed transcription, authoritative sign inventory, corpus
release, reading, translation, or decipherment.

It qualifies evidence handling and can support archival transcription; by
itself it adds no artifact find context and is not a semantic-information
experiment.

The source, layout proposal, and proposal-value-stripped reviewer-assignment
preparation layers are implemented. No Batch 0 independent human review,
adjudication, inventory promotion, decipherment, or prize result is claimed to
have occurred.

## Fixed public source

The source is Kimmo Koskenniemi and Asko Parpola's 1982
*A Concordande to the Texts in the Indus Script* (the title spelling used by
the official catalog), made available through the University of Helsinki:

- [official University of Helsinki publication record](https://researchportal.helsinki.fi/en/publications/a-concordande-to-the-texts-in-the-indus-script/)
- [official PDF snapshot](https://tuhat.helsinki.fi/ws/portalfiles/portal/209717802/indus_concordance_1982.pdf)

The official record labels the work CC BY. The selected PDF has 201 pages and
16,767,043 bytes; its exact digest and rights-evidence links are pinned in the
source registry rather than repeated in this operational document.

That source record does not establish rights for a different edition,
third-party artifact photograph, or unrelated sign artwork. The bridge also
does not independently verify the license statement or rehash source-document
and crop bytes during promotion.

`registry/kp1982_batch0.json` is the closed machine contract. The
`verify-kp1982-source` command checks caller-supplied PDF bytes and, when
provided, the two canonical PBM page images without network access. This
separate source check does not make later transcription promotion rehash those
same bytes.

## Fixed first target

The first double-transcription target is the sign list on one-based PDF pages
20–21. Their zero-based indices are 19–20 and the printed labels are `[20]`
and `[21]`.

Each page contains one 4888×6705 one-bit embedded image and no embedded text
layer. The normative observation space is the decoded bitmap with a top-left
origin and integer half-open rectangles `[x0,y0,x1,y1)`. A canonical PBM uses
row-major pixels, black=1, MSB-first, and no metadata. Poppler and MuPDF
produced pixel-identical pages in the recorded software check; their exact PBM
and packed-pixel commitments are in the machine contract. This decoder
agreement is not independent research replication.

Do not segment from a rescaled 595×841 PDF canvas. Normalized coordinates are
derived values only; the native integer rectangles remain normative.

Each sign-list entry visually contains two identifiers with different roles:

- the upper catalog rank may repeat; and
- the lower source-local printed identifier distinguishes the sign-list entry.

They must never be collapsed into one field. The lower identifier is recorded
under the inventory's primary identifier scheme with role
`primary_source_identifier`. The upper value is separately preserved with role
`catalog_rank`; duplicate catalog ranks are allowed. The graphic crop, page,
rectangle, extraction method, and printed doubt marks remain attached to the
same source evidence. “Primary” is a field role within this source; it does not
assert an invariant identity across editions, allograph policies, sound
values, or meanings.

## Relationship to the concordance fast lane

Batch 0 remains the complete, high-assurance 700-slot sign-list protocol. It is
not the only way research may begin, and it is no longer a serial prerequisite
for extracting proposals from the rest of the same source.

The separate
[decipherment-efficiency audit](DECIPHERMENT_EFFICIENCY_AUDIT_2026-07-28.md)
defines a fast lane:

- deterministically select approximately 80–120 sign-list slots across
  expected frequency, numeral/modifier forms, visual confusability, rarity,
  compound structure, scan difficulty, and random audit coverage;
- collect independent calibration evidence for that selected tranche;
- separately prepare a stratified reference of approximately 8–12
  concordance pages and 300–500 rows, with a sealed portion;
- treat page 22 as a section-title negative control and generate abstaining,
  exact-source-bound machine proposals only for the 179 data pages 23–201;
  and
- review proposals by uncertainty, disagreement, token coverage, and expected
  effect on a preregistered hypothesis.

That selected tranche must not be called “Batch 0 complete,” and its unreviewed
remainder must not be called a gold inventory. Machine proposals cannot enter
an admitted corpus or evaluation merely because the source is openly licensed.
Cell calibration cannot establish row splitting, key alignment, side
boundaries, logical order, identifier recovery, sequence accuracy, or
deduplication; the separate row reference and frozen sealed evaluation are
mandatory for an end-to-end claim.
The full procedure below remains available when its additional assurance has
enough downstream value to justify the human work.

## Batch 0 procedure

1. **Verify the source snapshot and page pixels.** Obtain the PDF only from the
   fixed official URL, extract pages in contract order, and run:

   ```bash
   uv run indusbench verify-kp1982-source indus_concordance_1982.pdf \
     --page-pbm page-20.pbm page-21.pbm
   ```

2. **Freeze deterministic cells and context.** The pages have ten vertical
   lanes and 35 row slots per lane, with the last page's final lane visibly
   ending early. Because the scan is slightly slanted, use a separately
   audited row-boundary array for each lane, not one global horizontal grid.
   Preserve a non-overlapping cell plus a padded context rectangle so printed
   marks crossing an internal guide are not clipped. Current measured
   lane/row anchors are preserved in
   `registry/kp1982_batch0_layout_seed.json` as proposals, not accepted
   evidence.

   Generate the byte-bound private proposal in a pre-existing owner-only
   directory:

   ```bash
   install -d -m 700 /private/kp1982-layout
   uv run indusbench propose-kp1982-layout \
     page-20.pbm page-21.pbm /private/kp1982-layout/proposal.json
   uv run indusbench verify-kp1982-layout \
     page-20.pbm page-21.pbm /private/kp1982-layout/proposal.json
   ```

   The commands commit and independently recompute all 700 cell and fixed
   32-pixel padded-context crops and require the canonical proposal bytes. The
   cell crop is a locator and may split foreground; the context is a review
   view, not accepted glyph evidence. Schema validation alone is insufficient.
   The verifier also rechecks that the proposal remains a single-link
   owner-owned `0600` file below a physical owner-only `0700` parent. These
   commands do not accept geometry, occupancy, or identifiers.

   A fixed-page eight-connected-component audit found that 32 pixels contains
   every component within its proposal owner cell's context when ownership is
   maximum black-pixel overlap with manifest-order tie-breaking. This rule is
   only a deterministic padding basis, not a machine-recomputed coverage
   assurance. It cannot assign disconnected printed marks semantically, so
   human review remains mandatory.
3. **Prepare a proposal-value-stripped reviewer assignment.** Rebuild and
   verify the canonical layout proposal, then derive its complete 700-cell
   locator roster:

   ```bash
   uv run indusbench prepare-kp1982-bootstrap-assignment \
     page-20.pbm page-21.pbm \
     /private/kp1982-layout/proposal.json \
     /private/kp1982-layout/bootstrap-assignment.json
   uv run indusbench verify-kp1982-bootstrap-assignment \
     page-20.pbm page-21.pbm \
     /private/kp1982-layout/proposal.json \
     /private/kp1982-layout/bootstrap-assignment.json
   ```

   Each assignment cell contains only its stable roster coordinates, proposed
   cell/context rectangles, and exact crop commitments. The closed schema and
   semantic builder structurally exclude machine occupancy values, accepted
   occupancy, OCR output, machine identifier proposals, and accepted
   observation fields. The cell crop remains a locator that may split
   foreground, and the context crop remains an unaccepted reviewer aid.
   Successful preparation verifies the fixed input bytes and stripping rule;
   it does not accept geometry or prove actual reviewer separation, blindness,
   or private custody.
4. **Run two independent bootstrap passes.** First verify the reviewer-safe
   input without giving the layout proposal to the reviewer environment:

   ```bash
   install -d -m 700 /private/kp1982-reviews /private/kp1982-reports
   uv run indusbench verify-kp1982-bootstrap-review-input \
     page-20.pbm page-21.pbm \
     /private/kp1982-layout/bootstrap-assignment.json
   uv run indusbench verify-kp1982-bootstrap-review \
     page-20.pbm page-21.pbm \
     /private/kp1982-layout/bootstrap-assignment.json \
     /private/kp1982-reviews/pass-a.json
   uv run indusbench verify-kp1982-bootstrap-review \
     page-20.pbm page-21.pbm \
     /private/kp1982-layout/bootstrap-assignment.json \
     /private/kp1982-reviews/pass-b.json
   uv run indusbench audit-kp1982-bootstrap-reviews \
     page-20.pbm page-21.pbm \
     /private/kp1982-layout/bootstrap-assignment.json \
     /private/kp1982-reviews/pass-a.json \
     /private/kp1982-reviews/pass-b.json \
     --private-report /private/kp1982-reports/new-bootstrap-audit.json
   ```

   These passes provide the evidence from which an inventory may be created
   only after adjudication. They must not use the artifact-transcription review
   schema or a pre-existing version of the inventory being derived. Each
   reviewer independently records occupancy, separate raw upper catalog rank
   and lower primary identifier observations with their own crops,
   glyph-with-marks evidence, an optional glyph-core rectangle, every
   surrounding printed mark, condition, uncertainty, and exact crop
   commitments. Every reviewed cell and observation crop must lie inside that
   cell's reviewed context; a corrected context may extend beyond the proposal.
   Review records and the assignment are private `0600` files below physical
   owner-only `0700` parents. The terminal audit is count-free;
   comparison detail is written only to a new private no-replace report. That
   report may contain record commitments, pseudonymous IDs, aggregate counts,
   and cell-level mismatch locations and field codes, but no raw identifier
   observations. These human passes have not yet been executed.
5. **Keep OCR proposals hidden and non-authoritative.** The pages have no text
   layer, and generic OCR misread clear numerals during the source audit.
   Machine proposals may be retained with separate provenance but cannot
   populate accepted identifiers or be shown between independent passes.
6. **Adjudicate the bootstrap.** A distinct adjudicator resolves every
   identifier, crop, occupancy, and printed-mark conflict while retaining
   unresolved observations:

   ```bash
   uv run indusbench verify-kp1982-bootstrap-adjudication \
     page-20.pbm page-21.pbm \
     /private/kp1982-layout/bootstrap-assignment.json \
     /private/kp1982-reviews/pass-a.json \
     /private/kp1982-reviews/pass-b.json \
     /private/kp1982-reviews/adjudication.json
   ```

   The adjudication must bind the canonical bytes of exactly two complete
   verified independent records and cite both observations for every
   assignment cell. A final value, rectangle, crop, or printed-mark set must
   equal one of those inputs or remain unresolved; the adjudicator cannot
   introduce a third observation. If neither input is admissible, collect new
   independent evidence instead of filling the field from OCR or adjudicator
   re-observation. Duplicate lower identifiers are a hard conflict, not an
   automatic merge. Only a verified adjudication may feed a later
   deterministic draft `sign-inventory.schema.json` builder, which is a
   separate software layer.
7. **Validate the generated inventory.** Keep the upper rank and lower primary
   identifier as separate published-identifier roles and bind every value to
   its source page, component rectangle, and crop. Do not assign sound,
   language, meaning, or translation.
8. **Use the transcription bridge only afterward.** Once the inventory has
   independent bootstrap evidence, inscription images can receive two
   independent sign-identification reviews and a distinct adjudication. That
   later artifact receipt remains private and
   `evaluation_admissible=false`.

Distinct pseudonymous actor and assignment IDs do not prove real-world
independence. The operating procedure must establish and audit actual reviewer
separation outside this software contract.

## Batch 0 completion evidence

Batch 0 may be described as software-contract complete only when the following
private evidence exists and verifies:

- one exact source snapshot accepted by the current byte verifier;
- both canonical page images accepted by the current byte verifier;
- one canonical, proposal-value-stripped 700-cell bootstrap assignment
  accepted by its exact-byte verifier;
- visually audited page and crop coordinates for all selected entries;
- two independent sign-list bootstrap records and one complete bootstrap
  adjudication accepted by the exact-byte, crop-rehashing, and no-invention
  verifiers;
- one schema- and semantics-valid inventory;

Even then, the accurate statement is “Batch 0 visual transcription evidence
passed the private contract.” It would not establish source rights,
independence, a public corpus, evaluation validity, sign sounds, language,
translation, or decipherment.

Later artifact-transcription review, adjudication, and a non-overwriting
private promotion receipt are a separate transcription-bridge milestone, not
Batch 0 completion evidence.

## Immediate engineering next step

Run two engineering lanes without conflating their assurance:

1. freeze the implemented PDF/PBM, layout-proposal,
   proposal-value-stripped assignment, bootstrap-review, two-review audit, and
   no-invention adjudication verifier as the full-700 high-assurance V1; and
2. specify the deterministic calibration tranche plus an abstaining,
   source-bound concordance-proposal contract.

Full Batch 0 still requires two genuinely independent visual passes over every
slot and distinct no-invention adjudication. The fast lane does not satisfy
that requirement. The software does not prove human authorship, real
independence or non-exposure, custody, rights, evaluation admission,
decipherment, or prize eligibility. No proposal is accepted evidence, no human
review has been executed, and Batch 0 remains unexecuted.
