# Museum API intake

Museum intake records preserve official API evidence and rights-cleared media
before any transcription or catalogue reconciliation. They are staging records,
not artifact observations and not decipherment evidence.

The normative schema is
[`schemas/museum-intake.schema.json`](../schemas/museum-intake.schema.json).
Entirely synthetic examples are in
[`examples/synthetic_museum_intake.jsonl`](../examples/synthetic_museum_intake.jsonl).
Executed private intake inventories and results are deliberately not part of
the public documentation.

## Admission boundary

An intake record is admissible only when all of the following are retained:

- the official institution, source-registry ID, object ID, accession number, and
  item-record URI;
- retrieval time, HTTP status, response content type, raw API response path,
  and SHA-256 digest;
- an item-level rights field and observed value, rights-policy URI, verification
  time, and the digest of the exact API response used as evidence;
- exact, hashed snapshots of the official policy and API documentation needed
  to interpret each provider's item-level flag;
- an affirmative redistribution, derivatives, and commercial-use grant under a
  named license;
- for each downloaded media object, its source URI, byte length, content type,
  local relative path, retrieval time, and SHA-256 digest.

Known providers use exact API, record, and media-host allowlists. HTTP
redirects are rejected rather than allowing the requested evidence locator to
drift. Image suffix, HTTP content type, and JPEG/PNG/TIFF signature must agree
before a staged file is finalized.

The verifier parses the stored API bytes again with duplicate JSON keys
forbidden, rebuilds the provider record, and compares all non-download fields
with that reconstruction. It also verifies the closed bundle manifest and
policy snapshots, rejects symbolic links, hard links, non-regular files,
duplicate path ownership, untracked files or directories, excessive directory
depth or entry counts, and configured per-file and aggregate resource limits.
Preflight and postflight inventories bind device, inode, mode, size, mtime,
ctime, and link count. Index files are opened nonblocking without following a
final symbolic link.

Provider-declared dimensions and byte counts are retained separately as
`provider_width`, `provider_height`, and `api_declared_bytes`. They are catalog
metadata, not file-integrity evidence. `download.bytes` and `download.sha256`
describe the bytes actually received over HTTP and remain authoritative even
when an API-declared file size disagrees.

Unknown, restricted, and metadata-only rights do not validate against this
schema. A media entry marked `not_downloaded` must keep all download-evidence
fields null. This is deliberate fail-closed behavior.

The rights-evidence digest must equal `retrieval.response_sha256`. JSON Schema
cannot express equality between two instance values portably, so intake code
must enforce that semantic invariant in addition to schema validation.

## Provider roles are not physical sides

`provider_primary` means only that the provider placed a URL in its primary
image field. `provider_alternate_unknown` means only that it came from the
provider's alternate-image list. Neither role establishes an artifact front,
reverse, impression, cast, or duplicate relationship.

`provider_derivative` preserves which upstream rendition was requested, such
as `met_original`, `cleveland_print`, or `cleveland_full`.

Every staged media record therefore has `physical_side: "unknown"`. The only
valid crosswalk state is `unresolved`. The closed schema has no fields for
tokens, sign IDs, reading direction, phonetic values, language assignments, or
translations.

## Promotion

Promotion into an artifact observation requires a separate, reviewable step:

1. verify the current item-level rights evidence again;
2. verify all recorded hashes and byte lengths;
3. resolve institutional records against the crosswalk protocol without
   treating similarity as identity;
4. annotate physical sides and inscriptions from direct observations while
   retaining uncertainty;
5. validate the resulting artifact record independently.

The original intake record and raw API response are append-only operational
provenance. Their hashes detect accidental or unilateral file changes, but a
bundle and its internal manifest can still be replaced together. Authenticity
therefore requires a trusted manifest digest held outside the bundle.
Manifest parsing and external-anchor comparison use the same single, bounded,
no-follow read; they do not reopen the file between those operations.

## Commands

`intake-museum` accepts explicit official object/accession identifiers. It
uses the system UTC clock, snapshots the required official policy documents,
then fetches and validates all JSON records before creating a temporary
bundle. It optionally downloads each enumerated medium. An existing
destination, including a dangling symbolic link, is never replaced. Final
publication uses the operating system's atomic no-replace rename primitive
with source and parent directory descriptors pinned; a platform or filesystem
without that guarantee fails closed.

```bash
uv run indusbench intake-museum data/raw/museum_open_access/snapshot \
  --met-object <public-object-id> \
  --cleveland-accession <public-accession> \
  --download-media \
  --full-schema
```

Rehash the saved API responses and every downloaded image, recompute record
digests and counts, compare them with the bundle manifest, and reject duplicate
record identifiers, symbolic or hard links, FIFOs and other non-regular files,
or untracked files and directories:

```bash
uv run indusbench verify-museum-intake \
  data/raw/museum_open_access/snapshot \
  --full-schema
```

After a bundle has every evidence image downloaded and passes full
verification, prepare a separate catalog-blind private review packet:

```bash
uv run indusbench prepare-museum-review \
  data/raw/museum_open_access/snapshot \
  data/derived/private_reviews/snapshot
uv run indusbench verify-museum-review \
  data/derived/private_reviews/snapshot
```

This does not mutate the intake. It makes exact normal copies under opaque
image IDs, groups provider derivatives without asserting physical sides,
places institution/accession/title/URL mappings in a separate custody
subtree, and scans reviewer text for source-identity leakage. The review layer
is governed by [MUSEUM_REVIEW.md](MUSEUM_REVIEW.md) and still contains no sign
reading, language, meaning, or translation.

The output includes `manifest_file_sha256`, `self_consistent`, and
`externally_anchored`. The last value is false unless a trusted digest from
outside the bundle is supplied:

```bash
uv run indusbench verify-museum-intake \
  data/raw/museum_open_access/snapshot \
  --expected-manifest-sha256 "$TRUSTED_MANIFEST_SHA256"
```

Without that external value, a successful verification establishes internal
self-consistency, not historical authenticity or a trusted timestamp.

Both commands operate on the Git-ignored private data tree. A successful
intake is not automatic authorization to publish the bundle or train a release
model.
