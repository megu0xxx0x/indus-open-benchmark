# Source and Rights Ledger

This project distinguishes public access from permission to copy, transform, or redistribute a
corpus. A website that can be searched is not automatically an open dataset. No source enters a
release until its record-level provenance and redistribution scope are documented in
`registry/sources.json`.

## Rights-cleared museum image pilot sources

### The Metropolitan Museum of Art Open Access

- Policy: <https://www.metmuseum.org/hubs/open-access>
- API documentation: <https://metmuseum.github.io/>
- Benchmark policy: admit an item only while its official API response has
  `isPublicDomain=true`; record that response, retrieval time, image checksum, and accession
  number

The official API was reviewed on 2026-07-26 for object IDs `324062`, `324063`, `324064`,
`324065`, and `38287`. All five responses marked the object public domain and supplied a primary
image. Object `324062` also supplied a second view. The records describe Indus seals or seal
material, but they do not supply secure excavation findspots or stratigraphic context.

CC0 permits image-pipeline and annotation work, but it does not turn the museum's dating,
cultural description, or a future sign transcription into ground truth. Item status MUST be
rechecked before every release.

### Cleveland Museum of Art Open Access

- Policy: <https://www.clevelandart.org/open-access>
- API: <https://openaccess-api.clevelandart.org/>
- Benchmark policy: admit an item only while its official API response has
  `share_license_status=CC0`; store each full TIFF and alternate view as a separate image
  observation with its own checksum

The official API was reviewed on 2026-07-26 for accession numbers `1964.104`, `1973.160`, and
`1973.161`. All three responses explicitly returned `CC0` and supplied full-resolution TIFFs;
the API also supplies provider-labeled alternate views, none of which it identifies as a physical
reverse. These records are suitable for a rights-cleared image-ingestion pilot. They remain
insufficient for decipherment training: there are only three objects, and their public records do
not provide archaeological findspots or stratigraphy.

### Publication boundary

The public ledger records source policy, API behavior, and item-level rights
requirements. It does not publish an executed private intake, selected private
inventory, provider download, local path, byte total, or manifest digest.
Operational intake evidence remains outside Git until a separate
rights-and-publication review approves exact release bytes.

## Current metadata-only context source

### Penn Museum collections dataset

- Official dataset page:
  <https://collections.penn.museum/collections/objects/data.php>
- Official CSV:
  <https://collections.penn.museum/collections/assets/data/Penn_Museum_Collections_Data.csv>
- Terms:
  <https://www.penn.museum/about/statements-and-policies/terms-and-conditions>
- Rights status: CC BY 4.0 applies to downloaded collections datasets;
  images are explicitly excluded
- Dataset page state reviewed: 2026-07-28; it reported `Last Updated:
  2026-07-01`
- Current use: exact-byte, metadata-only candidate discovery and conservative
  context-axis staging

The current official CSV has an exact one-field terminal sentinel containing
the generic Penn object URL after its complete 32-column records. The parser
recognizes only that exact final sentinel, only after at least one data row.
It continues to reject any other malformed-width row, padding, or later row.

The reviewed snapshot contains 430,813 complete records and yields 521 broad
review candidates. Thirty-four have the bulk catalog label `Indus Script`;
five are not automatically identified as replicas or modern objects, while
29 plaster/cast records are retained as negative controls. None of the five is
automatically approved as an ancient original.

The image-free context registry revalidates its snapshot against the complete
CSV bytes before deriving any entry. It preserves raw site, chronology,
object, material, motif, and measurement fields, but approves no field number,
transcription, meaning, language, or originality. Penn object-page field
numbers are outside the bulk schema and require a separate reviewed-evidence
layer.

The first primary-source follow-up is the
[Chanhu-Daro context crosswalk audit](CHANHU_DARO_CONTEXT_CROSSWALK_2026-07-28.md).
It links six published excavation field records to the five Penn candidates
and keeps two material conflicts unresolved rather than silently choosing a
mapping.

## Feature-safety-exposed known-script validation source

### ORACC ePSD2 Early Dynastic IIIb administrative corpus

- Official corpus:
  <https://oracc.museum.upenn.edu/epsd2/admin/ed3b/corpus>
- Official JSON ZIP:
  <https://oracc.museum.upenn.edu/json/epsd2-admin-ed3b.zip>
- ORACC JSON/open-data documentation:
  <https://oracc.museum.upenn.edu/doc/opendata/json/>
- Rights status: the exact archive embeds the CC0 declaration and CC0 URI
- Exact archive identity: 34,534,747 bytes; SHA-256
  `a108205140d101ca8d4d38c106fad7b61abac427eb51da12f912c8eada70c557`
- Current use: source qualification, ontology alignment, observation-safety
  audit, and prospective validation reservation; no candidate model fitting or
  performance evaluation

Eligibility requires exact Early Dynastic IIIb period, Administrative genre,
and `lem` metadata membership. A fixed 16-document hashed exclusion covers
the records whose individual contents were displayed during source-schema
qualification. After that exclusion, the source-only verifier commits 3,338
documents and 226,618 retained lemma tokens without directly listing
identifiers or raw values. The hash set is a data-minimizing commitment, not a
confidentiality mechanism; the finite public identifier space can be
enumerated.

The future evaluator-side states are `context_only`, operational conventional
numeric/count-unit token, metrological unit, person name, and settlement name.
They are projected mechanically from lowercase `n`, noun guide word `unit`,
`PN`, and `SN`. `NU` number words and `QN` quarter names are not quantity
targets. Gold fields are never model features and cannot select which rows
receive predictions.

The [source audit](ORACC_ED3B_VALIDATION_SOURCE_2026-07-28.md),
[global candidate audit](V3_GLOBAL_KNOWN_SCRIPT_SOURCE_AUDIT_2026-07-28.md),
and
[pre-model-fitting source protocol](../benchmark/oracc-ed3b-validation-source-v1.json)
define the fail-closed boundary. The source is public. Rights, schema,
archive-wide and joined-source class counts, limited now-excluded examples,
and gold-conditioned GDL-key safety aggregates were inspected. Those
aggregates informed the frozen annotation-stripping sanitizer, so ED3b is a
feature-safety-exposed prospective validation source—not feature-unseen,
distribution-blind, independently held, independently preregistered, or
binding confirmation.

Eight tokens across seven reserved documents lack sufficient POS truth. They
remain observation-bearing and require predictions but use the fixed
`annotation_unknown` evaluator state and are excluded from metrics rather than
silently becoming `context_only`. A different, previously uninspected corpus
must be selected through an independently controlled or predeclared-random
mechanism for binding confirmation.

## Current importable source

### University of Helsinki 1979 corpus

- Official record:
  <https://researchportal.helsinki.fi/en/publications/corpus-of-texts-in-the-indus-script/>
- Official PDF:
  <https://tuhat.helsinki.fi/ws/portalfiles/portal/176353520/indus_corpus_1979.pdf>
- Rights status: official record marked CC BY
- Exact PDF identity: 180 pages, 16,935,356 bytes,
  SHA-256 `e6f9dec7cf98d2ee6130f068e60ab37021808dd63953de41f92ce457b35a4bfa`
- Current use: fixed source, section/page map, and proposal-only layout audit;
  no accepted transcription or decipherment

The identifier-order base corpus is on PDF pages 22–78. Normal
sorted-from-end pages are 79–128; pages 129 and 130 are eight- and six-column
auxiliary catalog grids and are not linguistic sign sequences. The
sorted-from-beginning rendering is on pages 131–180.

`registry/kp1979_page_map.json` commits every native page image from PDF pages
2–180. Poppler and MuPDF produced pixel-identical 4880×7010 one-bit results.
The network-free audit applies one pixel-only detector to normal pages and
hard controls. It accepts no identifier or sign value and withholds candidate
counts.

The three renderings are valuable internal extraction checks, but they share
authors and source lineage. Agreement is not independent archaeological
confirmation.

### University of Helsinki 1980 documentation and duplicates

- Official record:
  <https://researchportal.helsinki.fi/en/publications/documentation-and-duplicates-of-the-texts-in-the-indus-script/>
- Official PDF:
  <https://tuhat.helsinki.fi/ws/portalfiles/portal/207886811/indus_duplicates_1980.pdf>
- Rights status: official record marked CC BY
- Exact PDF identity: 98 pages, 8,143,483 bytes,
  SHA-256 `0ced4102dc6197246df6c84e4b730ed380f41085a4a1ea8dd8a6459332da37d1`
- Current use: pinned revision/cross-reference/documentation/duplicate
  specification; canonical extraction pending

Data-bearing ranges are PDF pages 20–23, 27–32, 40–51, and 59–98. The
embedded OCR layer demonstrably confuses digits and section numbers and may
locate rows only. Every canonical value requires page-image verification.

The duplicate list carries group state across columns and pages. Its `strict`
and `loose` relations describe information redundancy under the authors'
rules, not necessarily one physical object, one ancient matrix, or exact text
identity. Preserve all these relations separately and never delete the raw
1979 observation.

### University of Helsinki 1982 concordance

- Official record:
  <https://researchportal.helsinki.fi/en/publications/a-concordande-to-the-texts-in-the-indus-script/>
- Official PDF:
  <https://tuhat.helsinki.fi/ws/portalfiles/portal/209717802/indus_concordance_1982.pdf>
- Rights status: official record marked CC BY
- Current use: fixed-source sign-list bootstrap only; no accepted
  transcription or decipherment

The checked-in KP1982 Batch 0 contract fixes the exact PDF, one-based pages
20–21, zero-based indices 19–20, and canonical 4888×6705 one-bit page images.
Poppler and MuPDF independently decoded identical pixels. The pages contain no
embedded text layer. Generic OCR produced incorrect numerals even on clear
labels, so OCR may propose candidates but cannot populate accepted
identifiers.

The upper catalog rank and lower primary source identifier are distinct source
fields; the upper value may repeat. Glyphs and surrounding printed
punctuation/doubt marks need separate evidence rectangles and crop
commitments. A fixed PDF or page hash does not establish the correctness of
those future crops or human readings.

### mayig/indus-valley-script-corpus

- Landing page: <https://github.com/mayig/indus-valley-script-corpus>
- Revision reviewed: `ad2f1e218a34b8c33c57de0d6cb8d99272765bbb`
- Review date: 2026-07-26
- Repository licence: MIT
- Benchmark policy: metadata/transcription import only; do not import images

The repository describes itself as a work-in-progress digitization of the *Corpus of Indus Seals
and Inscriptions* (CISI). Its repository-level `LICENSE` is MIT. This benchmark nevertheless uses
`metadata_only` rights status because the records are derived from CISI, no per-record CISI page or
rights evidence is supplied, and the repository does not include artifact images with separately
verified licences.

The reviewed revision contains 179 JSON artifact files (`M-1` through `M-184`, with gaps), 1,003
grapheme observations, and 182 distinct upstream `P###` base identifiers. It is not a representative
Indus corpus: every current description is a unicorn seal, every current artifact has one side,
only seven records contain a second line, and there is no image, material, period, stratigraphic,
findspot, or duplicate-family metadata.

The upstream README defines two independent orders:

1. graphemes are stored in physical left-to-right order on the intended sealing; and
2. the inscription is inferred by the upstream maintainer to read right-to-left.

The importer therefore keeps tokens in upstream visual order, assigns `visual_index` in that order,
and assigns the reverse `reading_index` within each line. It labels the side
`seal_impression`, not the seal matrix. Neither direction nor impression reconstruction is silently
promoted beyond the upstream assertion: both remain traceable to the pinned source record.

The first three values of each upstream feature vector are documented as damage percentage, line
number, and subjective uncertainty percentage. The reviewed data include damage values `1410` and
`110`, outside the documented 0–100 range. The importer does not clamp them. It preserves every raw
feature vector and records structured import warnings in the namespaced `extensions` field.

No upstream files are vendored. Tests use small synthetic records that reproduce only the documented
JSON shape.

## Reference-only or blocked sources

### CISI print corpus

The CISI volumes are the bibliographic source behind the mayig identifiers and transcriptions.
No machine-readable redistribution licence or artifact-image licence was verified for those
volumes. Treat CISI as a reference source and request permission before copying tables, drawings, or
photographs. The MIT licence in a downstream repository does not by itself establish rights in
third-party catalog pages or images.

### RMRL IndusScript / Mahadevan concordance

- Official description: <https://www.rmrl.in/en/irc>
- Application: <https://indusscript.in/>
- Status: blocked pending written data and redistribution terms

The Roja Muthiah Research Library describes IndusScript as an online conversion of Iravatham
Mahadevan's 1977 concordance and makes it available as a web research tool. The reviewed official
page does not publish a machine-readable corpus licence, bulk-download licence, or image
redistribution grant, and its site footer states that rights are reserved. Do not scrape, download,
or repackage its corpus. A future importer requires written permission, a pinned export, field-level
provenance, and explicit terms for metadata, transcriptions, glyph drawings, and photographs.

### Interactive Corpus of Indus Texts (ICIT)

- Official project page: <https://www.epigraphica.de/indus/menueindus.htm>
- Status: blocked pending access agreement and redistribution terms

The official page describes ICIT as the database developed by Bryan K. Wells and Andreas Fuls and
directs researchers to ask the administrator for access. No public corpus licence or redistribution
grant was verified. Do not automate access, copy an export obtained for individual research, or
repackage ICIT-derived tables. Before use, obtain permission that covers benchmark redistribution
and document the export version, record identifiers, sign-list version, image rights, and any CISI
dependencies.

### yajnadevam/lipi

- Repository: <https://github.com/yajnadevam/lipi>
- Status: blocked

The public repository presents conjectural transliterations and translations together with corpus
data. During review, no licence establishing redistribution rights for the corpus tables was
verified, and the record-level upstream lineage was insufficient to separate observations from
interpretive labels. Importing it would risk both rights contamination and circular evaluation.
Do not download or repackage its data. Any future reconsideration must independently establish the
origin and rights of every observation and place all proposed readings in a hypothesis layer, never
in benchmark ground truth.

## Admission checklist

A source can move from blocked to importable only when all of the following are recorded:

- a stable landing page and immutable revision or export identifier;
- creator, maintainer, and upstream-source lineage;
- explicit licences or written permissions for each of metadata, transcription, glyph artwork, and
  images;
- whether redistribution, derivatives, and commercial reuse are allowed;
- artifact-level identifiers and enough provenance to detect copies and seal/impression pairs;
- a documented sign inventory, visual order, reading-direction status, damage, and uncertainty;
- checksums for the reviewed input and deterministic importer output;
- a transformation log that keeps observations separate from decipherment hypotheses.
