# Corpus Crosswalk Protocol

## Purpose

Indus corpora do not share one stable artifact inventory or one sign inventory. A catalog number,
a physical object, a seal impression, a line of transcription, and an abstract sign are different
entities. This protocol prevents a visual resemblance or repeated identifier from silently turning
into an asserted identity.

The initial targets are Mahadevan 1977, CISI, Wells/ICIT, museum accessions, excavation reports,
and licensed derived datasets. This document defines how to record mappings; it does not assert
that any particular unresolved mapping is correct.

## Entity model

Crosswalk work MUST keep the following levels separate.

| Level | Definition | Typical identifier |
|---|---|---|
| Source edition | A dated corpus, catalog, export, or publication | source ID plus edition/revision |
| Catalog record | One entry in a source edition | exact upstream record ID |
| Physical artifact | One archaeological object | project `artifact_id` |
| Impression/cast | A physical or modern impression made from an object | its own artifact ID plus relationship |
| Side/surface | One inscribed surface of an artifact | `side_id` |
| Line/zone | A documented visual line or inscription zone | `line_id` |
| Token occurrence | One observed mark at one location | `token_id` |
| Abstract sign | A member of a named sign inventory | inventory ID plus sign ID |
| Allograph class | A hypothesis that forms are variants of one sign | hypothesis ID, never an observation ID |

A photograph, drawing, plaster cast, seal matrix, and impression may show the same carving in
different orientations, but they are not interchangeable source records. A transcription is an
interpretation of an observation and MUST retain the image or publication record from which it was
made.

## Identifier rules

1. Project IDs are stable and opaque. They do not encode a preferred catalog.
2. Every upstream identifier is stored with its `source_id`, edition/revision, and exact spelling.
3. A bare number such as `342` is invalid because the inventory or catalog is unknown.
4. Museum accession numbers, excavation field numbers, publication plate numbers, and corpus
   numbers occupy separate namespaces.
5. Correcting a mapping does not reuse or silently change a project ID.
6. A sign ID is always a pair: `{inventory_id, sign_id}`.
7. Private test-custodian identifiers are salted or replaced before they enter development data.

## Artifact mapping record

An artifact crosswalk assertion should contain at least:

```json
{
  "mapping_id": "map:example-only",
  "left": {
    "source_id": "source-a",
    "edition": "edition-or-revision",
    "upstream_record_id": "exact-id-a"
  },
  "right": {
    "source_id": "source-b",
    "edition": "edition-or-revision",
    "upstream_record_id": "exact-id-b"
  },
  "relationship": "possible_same_artifact",
  "status": "under_review",
  "evidence_record_ids": [],
  "counterevidence_record_ids": [],
  "asserted_by": "reviewer-or-importer-id",
  "asserted_at": "YYYY-MM-DD",
  "reviewed_by": [],
  "notes": "Illustrative shape only; this is not a real mapping."
}
```

The example is a contract illustration, not evidence of a real catalog correspondence.

Allowed artifact relationships are:

- `same_physical_artifact`
- `seal_to_impression`
- `modern_cast_of`
- `fragment_of`
- `joins_with`
- `same_mold_or_template_family`
- `same_inscription_sequence_only`
- `possible_same_artifact`
- `rejected_same_artifact`
- `unresolved`

`same_inscription_sequence_only` MUST NOT merge artifacts. Identical texts may occur on distinct
objects.

## Mapping strength

Each assertion uses one of four evidence strengths.

| Strength | Meaning | Permitted use |
|---|---|---|
| `exact` | Unique accession/field chain or decisive object-level evidence | May unify identity after independent review |
| `probable` | Multiple independent object features agree; no material conflict | Duplicate-family isolation, not silent merge |
| `possible` | Plausible but underdetermined | Research queue only |
| `rejected` | A proposed match conflicts with decisive evidence | Preserve as negative knowledge |

Numeric confidence MAY accompany the enum for ranking, but it MUST NOT replace the evidence
record or imply false measurement precision.

### Minimum evidence for an exact artifact match

An `exact` assertion requires at least one of:

- a documented accession or excavation-number chain across the two sources;
- an explicit cross-reference in a primary catalog or museum record; or
- independently reviewed agreement on object dimensions, material, damage, reverse features,
  provenance, and inscription geometry that excludes alternatives.

Matching catalog text, animal motif, or sign sequence alone is insufficient.

## Sign-inventory mapping

Sign equivalence is distinct from artifact identity. A sign-mapping assertion contains:

- left and right inventory editions;
- exact sign IDs;
- relation type;
- the token occurrences and images inspected;
- graphic features used;
- positional and combinatorial evidence;
- damage and orientation alternatives;
- reviewers and disagreements;
- version and supersession information.

Allowed sign relationships are:

- `exact_equivalent`
- `allograph_candidate`
- `graphic_variant_only`
- `mirror_or_orientation_candidate`
- `compound_contains`
- `split_candidate`
- `merge_candidate`
- `graphic_similarity_without_equivalence`
- `not_equivalent`
- `unresolved`

An allograph or compound analysis is a hypothesis. Raw token observations retain the upstream
inventory assignment and do not get overwritten when a hypothesis changes.

## Seal and impression handling

The matrix and intended impression normally reverse visual order. Therefore:

- record the physical carrier type;
- record whether an image shows the matrix, ancient impression, modern impression, drawing, or
  digitally mirrored view;
- preserve upstream visual order;
- store any reconstructed reading order separately;
- never mirror pixels without recording the transformation;
- link a seal to an impression through a relationship, not by reusing one artifact ID.

## Duplicate and family graph

Crosswalk assertions form a graph. Evaluation partitions MUST close transitively over:

- exact or probable physical-artifact matches;
- fragments and joins;
- seal/impression and cast relationships;
- same mold/template families;
- exact image hashes and reviewed near-duplicate images;
- exact normalized inscription sequences when the task could memorize them.

Closing transitively means that if A is related to B and B to C, A, B, and C stay in one partition
even when no direct A–C assertion exists.

Possible matches do not automatically merge records, but evaluation tooling SHOULD run a
sensitivity audit that treats them as one family and reports whether results change.

## Conflict handling

Sources may disagree about site, layer, material, orientation, sign segmentation, or catalog
identity. The crosswalk MUST:

1. preserve each source assertion verbatim;
2. attach provenance to every assertion;
3. record the conflict explicitly;
4. avoid selecting a winner merely because one source is newer;
5. document the adjudication rule and reviewers;
6. retain rejected mappings so the same error is not reintroduced.

Corrections append a new assertion that supersedes the earlier one. Released manifests are
immutable.

## Versioning

Every crosswalk release records:

- schema version;
- crosswalk release ID;
- generation time;
- source editions and immutable revisions;
- included and excluded mappings;
- mapping-strength counts;
- reviewer set;
- content hash;
- superseded release, if any.

A changed source edition triggers re-evaluation; it does not silently inherit mappings from an
older edition.

## Rights and access

An identifier match is factual metadata, but its evidence may contain restricted photographs,
catalog pages, or transcriptions. Each evidence record therefore states whether it can be:

- inspected privately;
- quoted;
- redistributed;
- transformed;
- used for model training;
- included in an external replication package.

Restricted evidence may support an internal assertion without entering a public release. Public
crosswalk rows should expose only fields permitted by all applicable terms.

## Blind-test boundary

The evaluation custodian may hold artifact identities and crosswalk edges that development teams
must not see. Before a blind evaluation:

- derive a public family token that reveals no museum or catalog identity;
- close all hidden duplicate and template relationships inside the custodian environment;
- provide only task inputs authorized for the submission;
- publish the split and leakage audit after the evaluation when rights permit;
- never use challenge feedback to retroactively tune a preregistered submission.

## Admission workflow

1. Register the exact source edition and rights.
2. Import upstream identifiers without normalization.
3. Generate candidate matches using identifiers, metadata, image hashes, or geometry.
4. Separate candidate generation from human adjudication.
5. Require two reviewers for `exact`; require an archaeologist or collection specialist when
   object identity depends on physical context.
6. Record counterevidence and unresolved alternatives.
7. Freeze and hash the accepted release.
8. Run duplicate-graph and split-leakage audits.

No automated similarity score can promote a mapping to `exact` without the required evidence and
review.
