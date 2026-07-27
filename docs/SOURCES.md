# Source and Rights Ledger

This project distinguishes public access from permission to copy, transform, or redistribute a
corpus. A website that can be searched is not automatically an open dataset. No source enters a
release until its record-level provenance and redistribution scope are documented in
`registry/sources.json`.

## Rights-cleared museum image pilot sources

### The Metropolitan Museum of Art Open Access

- Policy: <https://www.metmuseum.org/hubs/open-access>
- API: <https://collectionapi.metmuseum.org/public/collection/v1/>
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

## Current importable source

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
