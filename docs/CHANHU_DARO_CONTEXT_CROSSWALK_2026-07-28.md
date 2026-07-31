# Chanhu-Daro context crosswalk audit

**Status date:** 2026-07-28

**Claim status:** primary-source research crosswalk; not an admitted
transcription, semantic anchor, originality decision, or decipherment result

## Scope

This audit follows the five Penn Museum catalog records that the current bulk
dataset labels both `Indus Script` and `Harappan` into Ernest J. H. Mackay's
original Chanhu-Daro excavation report. It asks only whether a published field
number can recover excavation context.

It does not infer a sign sequence, reading direction, language, meaning, or
phonetic value. Penn's object pages and Mackay's report are separate source
layers. A match is not admitted into the machine-generated Penn context
registry until the extra-bulk field-number evidence receives its own reviewed
record.

## Primary sources and fixed bytes

- Ernest J. H. Mackay, *Chanhu-Daro Excavations 1935–36*, American
  Oriental Series 20 (New Haven: American Oriental Society, 1943):
  [Internet Archive record](https://archive.org/details/in.ernet.dli.2015.105167)
  and
  [source PDF](https://archive.org/download/in.ernet.dli.2015.105167/2015.105167.Chanhu-Daro-Excavations-1935-36.pdf).
- The reviewed PDF is 27,802,606 bytes, SHA-256
  `93a76551ab048c6a455b4239730dce718b96cd5b3747852b025858d86b253ef0`.
  Internet Archive describes its source library as the Central
  Archaeological Library, Archaeological Survey of India, and records the
  item as `Out_of_copyright`. The repository does not vendor the PDF or its
  plates.
- Penn Museum object records are linked in the table below. Field numbers
  visible on those pages are not columns in the CC BY 4.0 bulk CSV and are
  therefore not silently copied into the deterministic bulk-derived registry.
- The archival resolution route is the
  [Penn Museum Chanhu-Daro finding aid, call number 1064](https://findingaids.library.upenn.edu/records/UPENN_MUSEUM_PU-MU.1064).

Mackay's `Harappa Occupation I` and `Harappa II` are his local stratigraphic
labels. This audit does not automatically equate them with a later generalized
chronology for the whole Indus civilization.

## Field-number results

| Field number | Penn record | Mackay context | Published catalog or plate | Crosswalk status |
|---|---|---|---|---|
| SF 2000 | [83830 / L-141-160](https://collections.penn.museum/collections/object/83830) | [p. 28](https://archive.org/details/in.ernet.dli.2015.105167/page/n48/mode/1up): Harappa Occupation I; square 8/D, locus 223, level +12.2 ft; unfinished seal | [p. 292](https://archive.org/details/in.ernet.dli.2015.105167/page/n312/mode/1up), Plate LI:9 | High agreement among field number, narrative, and catalog |
| SF 3495 | [83829 / L-141-159](https://collections.penn.museum/collections/object/83829) | [p. 39](https://archive.org/details/in.ernet.dli.2015.105167/page/n59/mode/1up): Harappa II; square 7/C; narrative places it in room 238/460 | [p. 292](https://archive.org/details/in.ernet.dli.2015.105167/page/n312/mode/1up): locus 98, level +7.5 ft, Plate LI:17 | Field number and occupation high; exact room/locus unresolved |
| SF 3493 | [149372 / L-141-92](https://collections.penn.museum/collections/object/149372) | [p. 39](https://archive.org/details/in.ernet.dli.2015.105167/page/n59/mode/1up): Harappa II; square 7/C, room/locus 240 | [p. 292](https://archive.org/details/in.ernet.dli.2015.105167/page/n312/mode/1up): level +7.0 ft, Plate LI:12 | High agreement |
| SF 2428 | [238862 / L-141-176](https://collections.penn.museum/collections/object/238862) | [p. 43](https://archive.org/details/in.ernet.dli.2015.105167/page/n63/mode/1up): Harappa II; square 9/D, passage/locus 286 floor; apparently unfinished | [p. 293](https://archive.org/details/in.ernet.dli.2015.105167/page/n313/mode/1up): level +9.7 ft, Plate LII:19 | High agreement |
| SF 3051 | [329820 / L-141-177](https://collections.penn.museum/collections/object/329820) | [p. 45](https://archive.org/details/in.ernet.dli.2015.105167/page/n65/mode/1up): Harappa II; square 9/D, main-street locus 211, level +8.1 ft; poorly preserved | [p. 292](https://archive.org/details/in.ernet.dli.2015.105167/page/n312/mode/1up), Plate LI:24 | Mackay record high; one-to-one Penn association unresolved |
| SF 2558 | The same [329820 / L-141-177](https://collections.penn.museum/collections/object/329820) page lists this second field number | [p. 57](https://archive.org/details/in.ernet.dli.2015.105167/page/n77/mode/1up): Harappa II; square 9/D, locus 106, level +8.8 ft | [p. 293](https://archive.org/details/in.ernet.dli.2015.105167/page/n313/mode/1up), Plate LII:12 | Mackay record high; one-to-one Penn association unresolved |

## Conflicts that must remain open

### L-141-177 joins two distinct field records

Penn record `329820 / L-141-177` lists both SF 3051 and SF 2558. Mackay's
catalog treats them as different finds:

- different loci: 211 versus 106;
- different levels: +8.1 ft versus +8.8 ft;
- different dimensions and proportions; and
- different published plates: LI:24 versus LII:12.

The project must not merge these field records, choose one automatically, or
train on either association as settled ground truth. The Penn description
appears visually more compatible with one plate, but that observation is not
a sufficient identity decision.

### SF 3495 has a narrative/catalog location mismatch

Mackay's narrative associates SF 3495 with room 238/460, whereas the catalog
row gives locus 98. The occupation, square, field number, level, and plate
association remain useful, but the exact room/locus is unresolved.

## Archival resolution route

The Penn finding aid states that the collection contains the original
register, room-number records, and object-card catalogs. The relevant
holdings are:

- original register and room numbers: Box 2;
- SF 2000, card range 1731–2288: Box 8;
- SF 2428 and SF 2558, range 2289–2726: Box 9;
- SF 3051, range 2727–3280: Box 10;
- SF 3493 and SF 3495, range 3281–3810: Box 11; and
- seals, seal impressions, amulets, and published plate files: Boxes 3–4.

The finding aid says these materials are generally physical rather than
digitally available. No object card was accessed and no institution was
contacted during this audit. Any future request is a separately authorized
external action.

## Admission decision

The six Mackay field records are useful context leads. They are not yet
machine-admitted anchors because:

1. the field-number evidence is outside the exact Penn bulk snapshot;
2. one Penn accession has a two-record identity collision;
3. one published location is internally inconsistent; and
4. no source here supplies an accepted sign transcription.

The next safe implementation is a separate reviewed-evidence contract binding
the Penn page, retrieval evidence, field number, Mackay page, reviewer
decision, and unresolved-conflict state. Only conflict-free records can then
be joined to an independently admitted transcription for prospective
functional testing.

## Static preselection follow-up — 2026-07-31

The repository now includes a deliberately narrower
[context source-link preselection gate](CONTEXT_SOURCE_LINK_PRESELECTION_GATE.md).
It does not implement the reviewed-evidence contract described above and does
not reopen any source. It freezes only the six table rows, in source-table
order, as source-namespaced locator triples:

| Row | Mackay field number | Penn official record / accession | Frozen role |
|---:|---|---|---|
| 1 | SF 2000 | 83830 / L-141-160 | `lead_no_listed_material_conflict` |
| 2 | SF 3495 | 83829 / L-141-159 | `excavation_location_axis_conflict` |
| 3 | SF 3493 | 149372 / L-141-92 | `lead_no_listed_material_conflict` |
| 4 | SF 2428 | 238862 / L-141-176 | `lead_no_listed_material_conflict` |
| 5 | SF 3051 | 329820 / L-141-177 | `shared_penn_target_identity_collision` |
| 6 | SF 2558 | 329820 / L-141-177 | `shared_penn_target_identity_collision` |

Each triple records its source ID and identifier namespace. Every row has
status `source_locator_only` and
`not_joined_requires_separate_contract`. SF 3495 remains unresolved on the
excavation-location axis. SF 3051 and SF 2558 remain two distinct field rows
that point to one Penn catalog target. The gate therefore records six links,
five distinct Penn catalog records, and zero admitted joins. Those are catalog
counts, not verified physical-object identities.

The rights record does not extend Penn's bulk CC BY 4.0 metadata license to
the extra-bulk item-page association. That layer has no registered source
binding, null license, unknown rights, and link-only scope. The Mackay
locator is likewise unknown-rights and link-only. No image, page, plate, or
media byte is included.

The exact schema fixes all six rows with `prefixItems` and rejects additional
rows with `items: false`; all 355 tested mutations were rejected. This is
static repository validation only. There is no production builder, API,
strict runtime loader, or packaged registry gate. The registry and test are
not in the wheel; the schema is. Future operationalization needs strict
`decode_json` parsing and resource-inclusion tests.

The gate adds no positive, probable, exact, joined, or admitted status and no
sign, glyph, sequence, transcription, Helsinki row, reading, direction,
language, translation, or decipherment. Public CI run `30635957691` succeeded
for event `push` at exact head SHA
`fd5148431b0fa9136336650208e2d570d0f176d8`. Every job asserted Node
`v24.18.1` on Linux/x64. Python 3.11, 3.13, and 3.14 passed Quicknet 6/6 in
527.702196ms, 655.421586ms, and 503.092653ms, respectively, and completed the
1,087-test full suite with `OK (skipped=22)` in 810.027s, 946.248s, and
759.619s, respectively. Every job also passed Ruff, Ruff format for all 182
files, zero-finding Pyright, and sdist plus wheel builds.

This implementation made no network request to a research or source endpoint,
no external source-byte download, no image/page/plate retrieval, no
Helsinki-row access, no institution or source-holder contact, and no
operational gate or real source-link attempt. Repository publication and CI
are outside that statement. It authorizes none. The next research design is
a separately frozen non-sign source-link attempt. Source rows must never be
chosen through sign, glyph, transcription, or sequence similarity, and a
valid no-link outcome must stop without post-hoc substitution.

## Static source-reported-link policy follow-up — 2026-08-01

The separately frozen
[static source-reported-link decision policy](SOURCE_REPORTED_LINK_POLICY_V1.md)
binds one result slot to each of the six parent rows without changing this
crosswalk or resolving any source conflict. The slots remain in source-table
order, not rank order, and aggregation, row omission, and post-inspection row
substitution are forbidden.

SF 3495 keeps its unresolved excavation-location axis. SF 3051 and SF 2558
remain two distinct parent rows in the same Penn-target collision group. A
future `source_reported_link` would mean only that two separately sealed coded
machine passes reported the same bounded source-local locator for one parent
row. It would not approve a crosswalk join, establish physical identity, or
resolve either conflict.

The current state is `contract_blocked`: the Penn item page is unregistered,
its source-registry binding is null, its rights are unknown, and Penn bulk
metadata's CC BY 4.0 license is not inherited. No runtime evaluator,
inspection, observation, source byte, source-reported-link/no-link result,
join, translation, or decipherment result exists. A separate source
registration and rights contract is required before any source-access or
execution decision.

## Nonretroactive source-registration follow-up — 2026-08-01T07:07:54+09:00

The unregistered/null statement above remains the exact historical state of
the frozen policy checkpoint. The later
[static source registration and rights contract](SOURCE_REPORTED_LINK_SOURCE_CONTRACT_V1.md)
records an explicitly nonretroactive transition to
`registered_static_no_revision_receipt` for the five Penn item-page URIs. It
does not revise this crosswalk and is not an exact source revision, rights
clearance, source access, inspection, or execution.

The follow-up deliberately preserves three different cardinalities: five
future Penn receipt members, six ordered source-revision resources (the
existing Mackay revision plus those five Penn revisions), and six ordered
link/result slots. SF 3495 remains conflicted, while SF 3051 and SF 2558
remain distinct slots that declare reuse of Penn resource 329820.

The state is still `contract_blocked`, authorization is `not_authorized`, and
execution is `not_executed`. No closed receipt schema, commitment-envelope
schema, protected ephemeral custody/deletion contract, receipt, revision-set
or completeness digest, parser, evaluator, observation, or result exists.
No research or protected source was accessed for the static follow-up.
