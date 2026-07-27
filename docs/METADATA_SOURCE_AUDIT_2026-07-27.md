# Penn and Smithsonian metadata-source audit

Assessed: 2026-07-27 JST
Scope: official metadata acquisition routes, rights fields, Indus/Harappan
candidate extraction, and fail-closed implementation rules
Publication state: public audit record; no museum image was acquired or
released by this audit

## Outcome

Penn Museum is suitable for an automated **metadata-only** snapshot. Its
download page and terms apply CC BY 4.0 to the downloadable collections data
and state that images are not included. The current CSV is directly
downloadable without authentication.

Smithsonian is suitable for metadata discovery and per-record/per-media rights
inspection. Reviewed Harappan seal-cast candidates did not provide reusable
online media, so this audit does not establish Smithsonian as an image source.

Neither source is evidence that the Indus script has been deciphered. A catalog
match creates a review candidate only.

## Penn Museum

### Official endpoints and observed distribution

- Distribution page:
  `https://collections.penn.museum/collections/objects/data.php`
- Direct CSV:
  `https://collections.penn.museum/collections/assets/data/Penn_Museum_Collections_Data.csv`
- Terms:
  `https://www.penn.museum/about/statements-and-policies/terms-and-conditions`
- License:
  `https://creativecommons.org/licenses/by/4.0/`
- Distribution-page update shown during audit: `2026-07-01`

The URL is mutable and ETag is not a cryptographic source commitment. Every
retained acquisition therefore needs its own UTC retrieval time, byte count,
SHA-256, HTTP validators, and visible source-update date.

### Full-file validation result

The strict parser rejected the reviewed official distribution because its
terminal logical row did not satisfy the exact 32-column contract. The
malformed value was an incomplete object locator rather than a complete
record.

No normative Penn snapshot was written and no candidate was admitted. Exact
acquisition headers, local byte commitments, row totals, and diagnostic
aggregates are operational evidence kept outside the public repository. The
malformed terminal row must be corrected upstream or handled by a new,
explicitly versioned quarantine contract; it will not be silently dropped.

### Exact CSV contract

The observed header contains 32 fields, in this exact order:

```text
Record URL
identifier
curatorialSection
onDisplay
objectName
nativeName
title
creditLine
description
placeName
siteName
culture
cultureArea
locus
period
material
technique
creator
iconography
iconographySubject
inscriptionMarkLanguage
dateMade
earlyDate
lateDate
depth
length
width
height
thickness
weight
outsideDiameter
measurementUnit
```

There is no image URL, image ID, or image-license column. A parser must stop on
header additions, removals, duplicates, or reordering instead of silently
accepting a changed contract.

### Candidate extraction

The official collections search showed:

- `inscriptionMarkLanguage = Indus Script`: 34 records;
- `culture = Harappan`: 521 records.

The primary rule is an exact normalized `indus script` token in
`inscriptionMarkLanguage`. An exact normalized `harappan` token in `culture`
creates only a broad archaeological candidate. It cannot promote a row to an
inscribed object.

The 34 Indus Script records include many modern casts or impressions.
High-priority official records include:

- `L-141-159`, Chanhu-Daro, stone seal fragment;
- `L-141-176`, Chanhu-Daro, steatite seal;
- `L-141-92`, Chanhu-Daro, unfinished steatite seal;
- `89-13-408.2`, modern plaster seal impression.

Plaster, Plaster of Paris, `cast`, `reproduction`, or a clearly modern date is
classified as `replica_or_modern`. Every other row remains
`physical_status_unknown_pending_review`; it is never auto-labelled original.

### Implemented parser

[`penn_metadata.py`](../src/indusbench/penn_metadata.py) implements a
network-free parser over caller-supplied exact bytes. It enforces:

- approved direct URL and CC BY 4.0 constants;
- `images_included=false`;
- byte length and SHA-256 commitments before parsing;
- strict UTF-8, no NUL, strict CSV, and the exact header;
- non-empty record URL and identifier on every row;
- duplicate candidate URL/identifier rejection;
- raw preservation of all 32 strings;
- conservative candidate and physical-status derivation; and
- recursive rejection of unexpected media/image fields.

Its closed output contract is
[`penn-metadata-snapshot.schema.json`](../schemas/penn-metadata-snapshot.schema.json).
It does not fetch the CSV, follow record URLs, or acquire media.

The local CLI wrapper writes the validated snapshot atomically without
overwriting an existing path:

```bash
uv run indusbench parse-penn-metadata \
  <official-penn-csv> \
  <new-private-output.json> \
  --retrieved-at <rfc3339-acquisition-time> \
  --source-last-updated <source-update-date> \
  --expected-sha256 sha256:<trusted-download-digest>
```

## Smithsonian Open Access

### Current acquisition routes

The current API base is `https://api.si.edu/openaccess`. The API requires a key
and documents search pagination up to 1,000 rows.

The former GitHub bulk repository was archived on 2026-05-21 and points to the
current Smithsonian-managed AWS Open Data distribution. The current bulk
layout has a master unit index and per-unit hexadecimal shards named
`00.txt` through `ff.txt`; despite the extension, shards are JSON Lines.
Bulk data are updated weekly.

Primary entry points:

- `https://registry.opendata.aws/smithsonian-open-access/`
- `https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/index.txt`
- `https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/nmnhanthro/index.txt`

Bulk is the preferred discovery path. The API is a complement, because live
API results can include units not present under the same name in the bulk
master index.

### Separate metadata and media rights

The EDAN record model separates:

```text
content.descriptiveNonRepeating.metadata_usage.access
content.descriptiveNonRepeating.online_media.media[i].usage.access
```

Metadata is accepted only when the record type is `edanmdm` and normalized
metadata access is exactly `CC0`. Each media item must independently carry
exact `CC0` access, an HTTPS resource URL, and no contradictory usage or
restriction fields. Missing media usage, unknown values, `Usage conditions
apply`, or restriction conflicts stop media use.

`objectRights` is retained for audit but is not treated as the digital image
license. A record page is never scraped to fill a missing media field.

API keys belong in the `X-Api-Key` request header, never in retained URLs,
logs, fixtures, or source control. Runtime rate-limit response headers override
documented defaults; the audit observed a lower `X-RateLimit-Limit` for
`DEMO_KEY` than the generic documentation value.

### Candidate audit

The reviewed search results mixed physical-object metadata, library records,
and research outputs. The strongest NMNH candidates were described as casts
and did not provide online media.

A broad `Indus Valley` query is noisy because natural-history records use the
term geographically. Unit type, object terms, culture/site terms, and
cast/replica language must therefore be evaluated together. SIL and research
output records remain bibliographic candidates, not physical artifacts.

### Implemented raw-byte parser

[`smithsonian_metadata.py`](../src/indusbench/smithsonian_metadata.py)
implements a network-free parser over one caller-selected line in a complete
official AWS JSONL shard. It does not trust caller-supplied byte counts,
digests, offsets, raw-record text, rights decisions, or classifications. It
enforces:

- a canonical Smithsonian AWS EDAN shard URL and strict RFC 3339 retrieval
  time;
- a bounded, nonempty, strict-UTF-8 JSONL container with no NULs, blank lines,
  duplicate JSON keys, non-finite numbers, or excessive depth;
- internally computed container/line byte counts, offsets, line endings, and
  SHA-256 commitments;
- exact raw record text plus a derived intake ID bound to the acquisition
  timestamp and headers, container, locator, and canonical record;
- cross-checks among shard, upstream hash, `record_ID`, `url`,
  `docSignature`, and unit/title fields;
- bibliographic and natural-history unit gates before physical-object
  classification;
- closed metadata and media usage checks over `access`, `codes`, `text`, and
  unknown substantive fields;
- quarantine of every medium when record metadata is not CC0 or record-level
  restrictions conflict; and
- approval only for `Images` at the exact HTTPS Smithsonian image-delivery
  endpoint.

The closed output contract is
[`smithsonian-metadata-record.schema.json`](../schemas/smithsonian-metadata-record.schema.json).
Semantic verification additionally requires the exact raw JSONL container.

The local CLI validates one one-based physical line and writes without
overwriting:

```bash
uv run indusbench parse-smithsonian-metadata \
  <official-shard.jsonl> \
  <new-private-output.json> \
  --source-url <canonical-official-shard-url> \
  --retrieved-at <rfc3339-acquisition-time> \
  --line-number <one-based-line-number> \
  --etag <observed-etag> \
  --last-modified <observed-last-modified> \
  --expected-sha256 sha256:<trusted-download-digest>
```

Because the command is deliberately network-free, a matching URL field does
not prove where the local bytes came from. An independently retained
acquisition log or `--expected-sha256` value is the external source anchor;
without one, the output proves internal byte consistency only. The upstream
`docSignature` is retained as an identifier and is not treated as a verified
cryptographic signature.

Exact live-acquisition headers, timestamps, byte totals, line selections,
record identifiers, and derived digests are not public audit fields. Synthetic
regression fixtures exercise the parser and positive media gate. A validated
metadata-only record is still not automatically admitted into the inscription
corpus.

## Gates still closed

- No Penn or Smithsonian metadata row creates a sign sequence, side, reading
  direction, language, meaning, or translation.
- No Smithsonian Harappan seal-cast image was available through the audited
  Open Access record.
- Penn CSV image acquisition is out of scope because the licensed bulk export
  explicitly excludes images and Penn image terms are separate.
- Metadata candidate status and physical originality require human review.
- Public release additionally requires source anchoring, rights and heritage
  review, and—where human review records are used—a custody-bound reviewer
  roster and an externally checkpointed ledger.
