# Private transcription evidence bridge

## Status and scope

The transcription bridge v0.1 is an **unsealed draft workflow** for visual sign
segmentation and sign-inventory identification. It does not seal a review,
establish a trusted time, verify a reviewer roster, or make a phonetic,
language, semantic, translation, or decipherment claim.

Its public components are the closed JSON Schemas, semantic validators,
comparison logic, promotion logic, CLI surface, and synthetic tests. Review
records, adjudications, detailed agreement reports, source-image commitments,
and promoted artifacts remain private.

Public export is disabled. Every promoted artifact is marked
`private_staging_only` and `evaluation_admissible=false`; baseline extraction
must not treat it as evaluation data. A central fail-closed gate also rejects
any bridge-marked record from evaluation, leakage audit, splitting, control
shuffle, and release-manifest flows regardless of the marker's value.

## Evidence graph

One promotion requires:

1. one versioned sign inventory supplied as exact JSON bytes;
2. at least two complete independent-review drafts, each supplied as exact JSON
   bytes;
3. one complete adjudication draft supplied as exact JSON bytes; and
4. one artifact template whose target is an unresolved one-token scaffold.

Every adjudication input must bind the exact review digest, review ID,
assignment ID, and pseudonymous actor ID. Every adjudicated token must cite
tokens from every independent review, and the adjudication must cover every
input token. It cannot introduce a sign identity or reading direction absent
from the cited independent evidence. Reviewer conflicts require exact,
pairwise comparison commitments and a recorded resolution; an empty
`disagreements` list cannot erase a detected conflict.

The software requires distinct actor and assignment identifiers. That is a
consistency check, not proof that the reviewers were independent people, worked
without coordination, or lacked access to one another's drafts. The records
remain unsealed.

## Visual order is not reading order

`visual_index` is always assigned from left to right in the unmirrored,
unrotated source image. This is only a stable image-coordinate convention.
It does not assert that the inscription was read left to right.

The reading direction may remain `unknown`, with zero confidence and no
`reading_index` values. A known reading direction needs explicit evidence and a
complete reading-index permutation. Adjudication cannot invent a direction
that neither independent draft proposed.

In v0.1, source regions, inventory glyph regions, and token regions are
normalized, four-corner, axis-aligned rectangles. Arbitrary polygons, mirrored
views, and rotated views are outside this version's transform contract.
Adjudicated output rectangles must be substantially covered by each cited
input rectangle, so a full-image or remotely overlapping box cannot stand in
for local token evidence.

## Verification and promotion

The bridge strictly decodes the supplied JSON bytes, rejecting duplicate keys,
non-finite numbers, schema violations, and semantic inconsistencies. It hashes
those exact bytes internally and verifies the adjudication's review and
inventory commitments before promotion.

Promotion creates one private artifact observation and one
`indusbench:transcription_bridge` receipt. v0.1 refuses to replace either a
populated target line or an existing bridge receipt. A new or corrected
evidence graph therefore needs a new unresolved artifact template; it is not an
in-place rewrite of an earlier receipt.

The private receipt preserves evidence commitments and explicit negative
assurances. In particular:

- source-document bytes declared by the sign inventory are not rehashed;
- inventory crop bytes are not rehashed;
- source-image bytes are not required to be present or rehashed;
- rights evidence is not externally verified;
- real-world reviewer independence is not verified;
- the result is not blind or evaluation-admissible; and
- no decipherment is claimed.

Thus a successful command means only that the supplied evidence bytes satisfy
the v0.1 software contract. It is not proof of source authenticity, image
custody, rights ownership, independent work, scientific correctness, or a
reading.

## Private output boundary

Detailed agreement reports and promoted artifacts are written as new files
with mode `0600`. Their requested parent must already exist as a physical,
descriptor-pinned, owner-only directory with mode `0700`; symbolic-link
parents, extended ACLs, existing destinations, and unsafe path changes are
rejected. Terminal output is fixed and count-free and does not disclose the
agreement result.

Example with placeholder private paths:

```bash
install -d -m 700 /private/transcription-reports /private/transcription-artifacts

uv run indusbench audit-transcription-agreement \
  sign-inventory.json review-a.json review-b.json \
  --private-report /private/transcription-reports/new-agreement.json

uv run indusbench promote-transcription \
  sign-inventory.json unresolved-artifact.json adjudication.json \
  /private/transcription-artifacts/new-artifact.json \
  --review review-a.json \
  --review review-b.json \
  --side-id <side-id> \
  --line-id <line-id>
```

The output directories must be outside Git, CI artifacts, web roots, and other
publication paths. Promotion currently accepts only
`--release-scope private_research`.

## Admission gates not implemented

The bridge intentionally stops before corpus or evaluation admission. A future
release path needs, at minimum:

- direct verification of fixed source-document and crop bytes;
- a separately authorized, auditable reviewer-independence procedure;
- item- and layer-specific rights review;
- an allowlist-only public exporter that cannot copy private commitments or
  free text;
- duplicate-family and leakage review; and
- a separate scientific decision on corpus and evaluation eligibility.

None of those gates may be inferred from a valid v0.1 private receipt.
