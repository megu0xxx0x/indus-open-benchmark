# Museum human-observation review contract

## Status

The catalog-blind subject schema, review-record schema, semantic validators,
synthetic fixture, packet generator, and sealed review/adjudication checks are
implemented.

This document specifies software and governance behavior. It does not publish
or attest to a real private packet, reviewer roster, review result, custody
event, or source-manifest anchor.

Normative words such as **MUST**, **MUST NOT**, **SHOULD**, and **MAY** describe
the contract.

## Purpose

Museum intake is staging evidence, not an artifact registry and not a
transcription source. The review layer supports bounded human observations:

- carrier type, such as a seal matrix, impression, cast, or uncertain object;
- visible physical surfaces and inscription regions;
- possible relationships among views or records;
- exact catalog crosswalk proposals under
  [CROSSWALK_PROTOCOL.md](CROSSWALK_PROTOCOL.md); and
- disagreements and adjudication history.

The layer stops before sign transcription, reading direction, language
assignment, phonetic value, meaning, translation, or decipherment.

## Separation of layers

A conforming workflow keeps these layers distinct:

1. immutable source intake and evidence;
2. a catalog-blind reviewer packet;
3. a private custody map held by the controller;
4. independent review submissions;
5. adjudications over sealed submissions; and
6. separately governed promotion inputs.

The packet uses opaque identifiers. Institution, accession, title, source URL,
and original filename remain in the custody map and MUST NOT enter reviewer
text.

Visual resemblance MAY create a review question. It MUST NOT establish object
identity, inscription equivalence, a reading, or a decipherment claim.

## Inputs

Packet preparation accepts a fully verified museum-intake bundle whose media
are present and whose item-level rights evidence is still valid. It MUST reject:

- incomplete or unverified intake;
- missing media;
- symbolic links, hard links, special files, or unexpected entries;
- byte or digest drift;
- overlapping source and output roots;
- an existing or dangling destination; and
- platforms that cannot provide the required no-replace publication behavior.

Provider image roles are retained only as source assertions. A provider
`primary` or `alternate` field never becomes a physical front, reverse, seal,
or impression automatically.

## Packet layout

The implementation produces a closed packet under a caller-selected private
root. Documentation and tests use placeholders rather than an executed path:

```text
<packet-root>/
  packet-manifest.json
  reviewer/
    manifest.json
    subjects/
    evidence/
  custody/
    manifest.json
    mappings/
```

The reviewer subtree contains opaque subject and image identifiers, bounded
observation prompts, and exact evidence copies. The custody subtree contains
the source-identity mapping required for later controlled reconciliation.

Packet manifests bind the closed inventory and exact bytes. These digests are
private, linkable metadata and MUST NOT be copied into public documentation,
issue text, CI logs, or release artifacts.

## Review record

A review record:

- identifies one opaque subject;
- binds the exact packet and subject bytes;
- records only schema-defined observations and bounded assertions;
- distinguishes `observed`, `inferred`, `unknown`, and `not_applicable`;
- carries uncertainty and reviewer rationale without catalog identity; and
- contains no sign ID, reading direction, sound, language, meaning, or
  translation.

Unknown is a valid and often preferred result. The schema MUST NOT force a
reviewer to turn ambiguity into an assertion.

## Independent review and adjudication

The controller defines the required independent-review policy before review
starts. A reviewer MUST NOT see another reviewer's submission before sealing
their own.

Submissions are immutable and content-addressed. A correction creates a new
record that identifies its predecessor; it never edits sealed bytes in place.
An adjudication cites the exact submissions it considers and records agreement,
disagreement, abstention, and unresolved fields explicitly.

The software verifies structure and byte relationships. It does not prove that
reviewers were independent people, that they worked at the stated time, or that
the controller prevented communication. Those assurances require an external
roster, chronology, and checkpoint procedure.

## Private custody

The controller MUST:

- restrict packet, custody, submission, and adjudication files to authorized
  reviewers;
- keep reviewer and custody views separated;
- avoid public paths and Web roots;
- prohibit issue, chat, or CI attachment of private records;
- preserve originals and use append-only review records;
- document retention and deletion authority outside the public repository; and
- treat filenames, opaque IDs, paths, inventories, byte totals, and digests as
  private operational metadata.

Publication requires a separate export review that removes custody mappings and
checks every released field against source rights and participant consent.

## Commands

Examples use caller-selected placeholders:

```bash
uv run indusbench prepare-museum-review \
  <verified-intake-root> \
  <new-private-packet-root>

uv run indusbench verify-museum-review \
  <private-packet-root>

uv run indusbench seal-museum-review \
  <private-packet-root> \
  <private-ledger-root> \
  <review-draft.json> \
  --expected-packet-manifest-sha256 sha256:<trusted-digest>

uv run indusbench verify-museum-review-ledger \
  <private-packet-root> \
  <private-ledger-root>
```

The expected digest must arrive through a channel independent of the packet.
Copying a digest reported by the same local bundle establishes no external
anchor.

## Promotion gate

No review output enters a public artifact record until:

- source and media rights allow the intended publication;
- custody mappings have been reconciled under controlled access;
- the required independent reviews and adjudication are complete;
- unresolved identities and physical sides remain unresolved;
- the exported record contains no private reviewer/custody identifiers; and
- a separate publication review approves the exact output bytes.

Even after promotion, human observation is not a sign reading or translation.

## Public verification surface

The repository may publish schemas, validators, synthetic fixtures, generic
commands, and tests. It must not publish:

- a real packet or ledger;
- an executed private directory name;
- a private source selection or inventory;
- exact private counts or byte totals;
- a private manifest or evidence digest;
- a reviewer/custody identifier; or
- a real review or adjudication result.
