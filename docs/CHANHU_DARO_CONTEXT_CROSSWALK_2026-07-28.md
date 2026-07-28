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
