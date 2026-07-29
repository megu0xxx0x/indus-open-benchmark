# Global evidence update — 2026-07-29

## Scope and claim boundary

This is a primary-source discovery audit for the next evidence-acquisition
steps. It does not admit a corpus record, authorize image reuse, establish an
Indus reading, or create a Tamil Nadu prize submission route.

## Findings

### iCEL three-dimensional database

The [2025 iCEL/IMSc paper][icel-paper] describes a contextual
three-dimensional database as work in progress and presents public online
access as a future objective. The [2025 workshop page][icel-workshop] and
[IMSc publication list][imsc-publications] disclose no stable viewer,
download, API, manifest, coverage list, version, geometry hash, or reusable
geometry/texture licence.

The paper establishes the 2025 status. The wider primary-source search did not
find a released dataset as of 2026-07-29; absence from that search is not proof
that no unindexed release exists. Project state:

```text
status_in_2025_primary_paper = under_construction
public_dataset_release_verified_at_2026_07_29 = false
licence_verified = false
independent_corpus_verified = false
```

No third-party three-dimensional model may substitute for an institution-bound
scan with a stable object identifier, scale, provenance, and explicit reuse
terms.

### ASI/NMMA external catalogue candidates

The [National Mission on Monuments and Antiquities][nmma-about] is operated by
the Archaeological Survey of India. Its [Central Antiquity Collection
“Seals & Sealings” listing][nmma-seals] reported 1,352 catalogue rows when
audited.

All seven listing offsets (`0`, `200`, `400`, `600`, `800`, `1000`, and
`1200`) were inspected. Unique row references whose provenance text matched
`Harappa|Mohenjo|Desalpur|Surkotada` produced:

| provenance string | candidate rows |
| --- | ---: |
| Harappa | 165 |
| Mohenjo-daro | 242 |
| Desalpur | 4 |
| Surkotada | 2 |
| total | 413 |

These are **site-origin candidates within a seals-and-sealings category**, not
413 confirmed inscribed Indus objects. Individual review must still reject
uninscribed objects, modern replicas, ambiguous provenance, and duplicate
catalogue records.

The [Lothal record ASM-KML-GJ-1425186][nmma-lothal] demonstrates the potential
information gain: an official object identifier, visible inscription,
material, dimensions, custody, and excavation context coexist in one record.
NMMA also warns that its data are being corrected and remain subject to
validation.

No public bulk API or reusable catalogue-metadata or image licence was found.
The admissible public artifact is therefore limited to the official record ID
and official landing URL. Titles and displayed provenance may guide manual
browser review but must not be copied into the public index without a separate
rights basis. Automated image download, redistribution, or training use is
not authorized.

NMMA is institutionally independent of the Helsinki editions, but a listed
object may be the same physical object published there. Archaeological
independence must be assigned only after object-level crosswalk and duplicate
review.

### Tamil Nadu graffiti and potsherd resources

The [Tamil Nadu Graffiti project][tn-graffiti] reports 9,486 recognized
graffiti observations or occurrences, 42 base signs, 544 variants, and 1,521
composites. This does not establish a fixed 9,486-row export. The Tamil Digital
Library also exposes the 2026
[Inscribed Potsherds of Tamil Nadu, volume 1][potsherds-v1] and
[volume 2][potsherds-v2].

These are relevant archaeological context sources, but no reusable structured
export licence was found. Their published “similar to Indus” classifications
must not become truth labels for an Indus-similarity test because that would
reuse the conclusion being tested. They are not bilingual texts. Until rights
and extraction contracts are established, retain only links, bibliography,
and non-circular site/context facts.

### Tamil Nadu one-million-dollar announcement

The [Tamil Nadu Department of Information and Public Relations release dated
2025-01-05][tn-dipr-release] establishes that the Chief Minister announced a
one-million-US-dollar award for an individual or organization presenting a
route to understanding the script that archaeologists accept as a valid
solution.

As of this audit, searches of the official release system, Gazette and
Government Order routes, the [Tamil Nadu Awards portal][tn-awards],
[notifications][tn-awards-notifications], and [department Government
Orders][tn-awards-orders] did not establish an operational scheme. No official
application form, submission address, deadline, eligibility rules, evidence
standard, judging procedure, intellectual-property terms, tax/payment terms,
or appeal process was verified.

Project state:

```text
announcement_authentic = true
operational_submission_scheme_verified = false
submission_attempt_allowed = false
```

Do not send a claim to a generic awards portal or guessed email address.

## Priority decision

The critical path remains:

1. build the source-bound KP1979 identifier-order record spine;
2. reconcile it with the two source-local sorted renderings;
3. preserve KP1980 corrections, cross-references, documentation, and duplicate
   relations as a versioned delta;
4. use KP1982 later as occurrence-level consistency evidence; and
5. develop the NMMA 413-row result only as a rights-conservative
   ID-and-official-URL-only external-catalogue candidate lane.

The Helsinki three-way agreement and KP1980 corrections improve extraction
reliability but are not independent archaeological confirmation. The NMMA
crosswalk can supply that external comparison only after physical-object
identity and reuse boundaries are resolved.

[icel-paper]: https://www.imsc.res.in/~sitabhra/papers/sinha_ashraf_Indus100_confproc_2025.pdf
[icel-workshop]: https://www.imsc.res.in/~sitabhra/meetings/bitsscripts25/
[imsc-publications]: https://www.imsc.res.in/~sitabhra/publication.html
[nmma-about]: https://nmma.nic.in/nmma/aboutNmma.do
[nmma-seals]: https://nmma.nic.in/nmma/exploreMusObject.do?musname=CAC-CCA&object=32
[nmma-lothal]: https://nmma.nic.in/nmma/antiqDetail.do?object=32&refId=1425186
[tn-graffiti]: https://tngraffiti.in/
[potsherds-v1]: https://tamildigitallibrary.in/Articles/062969_Inscribed_Potsherds_of_Tamil_Nadu_Vol_1
[potsherds-v2]: https://tamildigitallibrary.in/Marc-Articles/062968_Inscribed_Potsherds_of_Tamil_Nadu_Vol_2
[tn-dipr-release]: https://dipr.tn.gov.in/ords/r/dipr/info-prdept103/press-release1?cs=17R0H-bKZMbOX4AlR_1awqes0TjNMjZfSiguFGs-EZAuLpJ7oTo7mfnIeUQKJYwuwGZWO8x9ra6Rt5S1dG70WFw&p33_file_id=11209&request=APPLICATION_PROCESS%3DGET_FILE
[tn-awards]: https://awards.tn.gov.in/
[tn-awards-notifications]: https://awards.tn.gov.in/com_notify.php
[tn-awards-orders]: https://awards.tn.gov.in/gos_dept.php
