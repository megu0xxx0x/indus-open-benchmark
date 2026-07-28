# V3 global known-script source audit

**Audit date:** 2026-07-28

**Scope:** non-exhaustive audit, as of 2026-07-28, of public ancient-script
candidate sources for rights explicitness, immutable bytes, task fit, and
leakage risk

**Primary decision:** reserve ORACC ePSD2 `admin/ed3b` as a
feature-safety-exposed prospective validation source, not binding
confirmation; treat all other sources below as separately governed companions,
secondary controls, stress tests, deferred candidates, or negative controls

**Evaluation status:** source, rights, structure, fixity, ontology, and leakage
audit only; no model was trained, selected, tuned, scored, or compared.
Archive-wide, joined-source, and gold-conditioned key aggregates are disclosed
side information, so ED3b is neither distribution-blind nor feature-unseen.

## Executive decision

Among the candidates audited here, ORACC ePSD2 Early Dynastic IIIb ranks
highest under the stated rights, fixity, task-fit, and leakage criteria. It
supplies document, line, and lemma
order; a mechanically defensible operational projection for written numeric
markers, metrological units, personal names, and settlement names; embedded
CC0 declarations; and exact bytes. Gold-conditioned GDL-key inspection was
needed to remove direct annotation proxies, so it is prospective validation,
not untouched confirmation.

SumTablets is the highest-ranked future glyph companion audited here. It adds
normalized Unicode
cuneiform sequences and preserves surface, column, line, blank-space, and
ruling structure. It is not part of the current ORACC source seal. If V3 will
consume any SumTablets field, its exact Git and Hugging Face bytes, join rule,
alignment rejection rule, and leakage boundary must be sealed separately
before model development.

ORAEC/AES is the highest-ranked fixed, rights-clear secondary family audited
here from a different known writing system. DHARMA Satavahana is the
highest-ranked geographically relevant South Asian short-inscription stress
source found in this audit, but it does
not supply the same token-level gold task or native glyph stream.

The audited Linear B sources are either non-commercial, dynamically served,
insufficiently licensed for bulk reuse, or dominated by augmented and
duplicate sequences. The ClassicMayan project is rich and generally open, but
its item-level metadata rights vary, image-reuse rights were not established
by those statements, and the machine-readable corpus remains under
construction. Proto-Elamite is undeciphered and therefore cannot be a
known-script positive semantic control; its rights-clear sign drawings may
serve only a separately declared negative or abstention diagnostic.

## Decision matrix

| Source | Context and labels | Native-script representation | Rights and fixity | V3 role |
|---|---|---|---|---|
| ORACC ePSD2 `admin/ed3b` | Document/line/lemma order; numeric, unit, personal-name, and settlement-name projection | Annotation-stripped structured transliteration, not native glyphs | Embedded CC0; exact ZIP byte seal; feature-safety exposed | **Prospective validation; not binding confirmation** |
| SumTablets | Parallel transliteration, glyph names, period, genre, and layout markers; no target gold | Normalized Unicode cuneiform, not object photography | CC BY 4.0; fixed Git and HF revisions | Future glyph companion; separate pre-model seal required |
| ORAEC/AES | Sentence/token order, translations, lemma, POS, named entities, metadata | Partial normalized Unicode Egyptian hieroglyphs | CC BY-SA 4.0; fixed commits | Independent secondary known-script control |
| DHARMA Satavahana | EpiDoc edition, translation, date, provenance, and object metadata | Latin-script diplomatic transcription; no bundled native-glyph stream | Per-file rights conservatively treated as CC BY-SA 4.0; fixed commit | South Asian short-inscription stress test |
| Linear B | Source-dependent sequence or epigraphic context | Mostly transliteration in the auditable bulk source | Non-commercial, unfixed, unclear, or duplicate-heavy | Do not admit as primary |
| ClassicMayan | Images, epigraphic analysis, transcription, translation, and object context | Photographs and drawings | General CC BY statement; varying item-metadata terms do not establish image reuse; no fixed complete bulk release | Defer pending layer-specific rights manifest and immutable release |
| Proto-Elamite/CDLI | Sign drawings and transliterations; no deciphered semantic gold | EPS sign drawings; CDLI object images are separately restricted | Glyph repository CC BY 4.0; broader data and images require separate rights treatment | Negative/abstention diagnostic only |

## 1. Prospective validation source: ORACC Early Dynastic IIIb

### Official source and sealed bytes

- [ORACC ED3b human corpus view](https://oracc.museum.upenn.edu/epsd2/admin/ed3b/corpus)
- [Official ORACC ED3b JSON ZIP](https://oracc.museum.upenn.edu/json/epsd2-admin-ed3b.zip)
- [ORACC JSON open-data specification](https://oracc.museum.upenn.edu/doc/opendata/json/)
- [ORACC open-data documentation](https://oracc.museum.upenn.edu/doc/opendata/)
- [CC0 1.0 legal instrument](https://creativecommons.org/publicdomain/zero/1.0/)

The admitted upstream archive is:

```text
project: epsd2/admin/ed3b
archive bytes: 34,534,747
archive members: 3,491
catalogue documents: 3,477
sha256: a108205140d101ca8d4d38c106fad7b61abac427eb51da12f912c8eada70c557
```

The ZIP embeds `This data is released under the CC0 license` and the CC0 URI
in both corpus and glossary metadata. Its internal corpus and glossary
timestamps are 2022-12-07. The download URL is not content-addressed; later
bytes from the same URL are a different source unless their length and digest
match exactly.

The project-local source seal and selection contract are documented
separately in
[ORACC Early Dynastic IIIb prospective-validation source audit](ORACC_ED3B_VALIDATION_SOURCE_2026-07-28.md).
This global audit does not replace or broaden that closed contract.

### Mechanical projection and its limit

The relevant official annotation definitions are:

- [ORACC numbers and metrology guidance](https://oracc.museum.upenn.edu/doc/help/editinginatf/metrology/index.html)
- [ORACC proper-noun annotation guidance](https://oracc.museum.upenn.edu/doc/help/languages/propernouns/index.html)

The fixed operational projection is:

| State | Exact source rule | Archive-wide count observed during source audit |
|---|---|---:|
| `quantity` | lemma `f.pos` is lowercase `n` | 80,438 |
| `unit` | lemma `f.pos` is `N` and `f.gw` is `unit` | 6,173 |
| `person_name` | lemma `f.pos` is `PN` | 31,265 |
| `settlement_name` | lemma `f.pos` is `SN` | 2,043 |
| `context_only` | none of the four rules matches | mechanically derived by the source verifier and future evaluator; count not listed |

ORACC explicitly instructs that administrative numerals and count-unit
graphemes are lemmatized as lowercase `n`. The `quantity` label is therefore
an operational class for conventional written numeric/count-unit tokens; it
must not be described as every semantic expression of quantity. ED3b also
contains 1,098 `NU` number-word lemmas, which the frozen narrow rule does not
admit. `QN` means Quarter Name in the ORACC proper-noun vocabulary and must
never be reinterpreted as quantity.

The unit rule has unusually strong internal support. The Sumerian glossary has
18 entries with guide word `unit`, part of speech `N`, and a summed instance
count of 6,173, equal to the corpus token scan. ORACC's metrology guidance
independently specifies guide word or sense `unit` for weights and measures.

ED3b and the earlier MTAAC control differ chronologically, but both participate
in the broader CDLI/ORACC identifier ecosystem. Exact source-identifier and
normalized-sequence overlap checks remain mandatory before validation.

## 2. Future glyph companion: SumTablets

### Fixed public source

- [Author repository at fixed commit](https://github.com/colesimmons/SumTablets/tree/933b38872779363197ddf4ecb89db02dba1b32a8)
- [Exact Git tar.gz bytes](https://codeload.github.com/colesimmons/SumTablets/tar.gz/933b38872779363197ddf4ecb89db02dba1b32a8)
- [Hugging Face dataset at fixed revision](https://huggingface.co/datasets/colesimmons/SumTablets/tree/11638cd142afbed716df43c55d8810d47fb9b52c)
- [SumTablets publication record](https://aclanthology.org/2024.ml4al-1.20/)
- License: CC BY 4.0

The fixed Git `tar.gz` from the codeload URL has SHA-256
`5973d072261e1471754d8b603b55680768c5c2ad76ba8621c208bcd5b2f40ffb`.
The dataset contains 91,606 tablets and 6,970,407 glyphs with fields for
identifier, glyphs, glyph names, transliteration, period, and genre. Its public
split sizes are 82,452 train, 4,577 validation, and 4,577 test rows.

The fixed HF CSV digests observed in this audit are:

```text
train.csv:      57c78a77ead81790b4a7efcd94090e2957ef11645998bc7edfdff5db1a3db6ce
validation.csv: 061a275a9c0e63135a7175c4fb153ac767361c493847ab6a9ce8c5fec9a3f9ee
test.csv:       65dfe606c2d6f40f8cc6900d5abad43e2bf31e009d425c4ac1539e1baa06ab85
```

### Confirmed ED3b overlap and short-line structure

An identifier-only join found SumTablets glyph rows for 3,440 of the 3,477
ED3b catalogue documents. Within that joined scope, the ORACC-side target
counts remain 80,363 lowercase-`n` numeric tokens, 6,170 units, 31,226
personal names, and 2,033 settlement names.

The joined glyph view contains 86,155 non-empty cuneiform lines:

- median line length: 4 Unicode cuneiform code points;
- 40,633 lines, or 47.16%, contain at most 3 code points;
- 70,636 lines, or 81.99%, contain at most 5 code points; and
- 85,004 lines, or 98.66%, contain at most 10 code points.

This is a useful short-sequence analogue, but the representation is normalized
Unicode cuneiform generated from scholarly readings and sign lists. It is not
a photograph, palaeographic facsimile, or independent visual observation of
the tablet.

SumTablets cleans transliterations and maps readings to glyph names. It does
not publish the V3 gold labels, and its cleaned tokenization is not guaranteed
to align one-to-one with ORACC lemma tokens. Any future use must freeze:

1. the exact Git and HF revisions and file digests;
2. the exact eligible identifier join;
3. a development-only alignment validator;
4. fail-closed exclusion of ambiguous lines instead of coerced alignment;
5. document/family-level duplicate and near-duplicate grouping; and
6. a rule forbidding the public HF split from silently becoming the V3 split.

**SumTablets is not included in the current ORACC ED3b source seal.** Adding it
after model development would change the observation source and invalidate a
claim that the combined control was prospectively sealed. It requires its own
pre-model source seal before any field is used.

## 3. Different-script secondary: ORAEC and AES Egyptian

- [ORAEC corpus site](https://oraec.github.io/corpus/)
- [ORAEC raw-data repository at fixed commit](https://github.com/oraec/corpus_raw_data/tree/b83a0ee5fae27a40d4c0a2a9a8c9c2973d45e9cd)
- [Exact ORAEC tar.gz bytes](https://codeload.github.com/oraec/corpus_raw_data/tar.gz/b83a0ee5fae27a40d4c0a2a9a8c9c2973d45e9cd)
- [AES repository at fixed commit](https://github.com/simondschweitzer/aes/tree/35276d2527cca1a055e31ed5f6683e777717170f)
- License: CC BY-SA 4.0

The ORAEC fixed `tar.gz` has SHA-256
`f86edd3afb16e95c03269c6ff958108b7823d3a0e04081140093dfc5259ac524`.
The audited snapshot contains:

- 13,026 documents;
- 101,796 sentence objects;
- 815,026 tokens;
- 783,318 POS fields and 779,011 lemma identifiers;
- 15,713 `person_name`, 6,937 `place_name`, and 20,709 `numeral` tokens; and
- 267,042 normalized hieroglyph fields across 2,900 documents.

There are 6,545 hieroglyph fields containing a Unicode replacement character,
so a glyph-quality gate is mandatory. These fields are normalized hieroglyph
strings, not source-object images.

ORAEC/AES offers document and sentence context, translations, lemmas, POS,
entity subtypes, date, provenience, object type, line references, and partial
native-script representation. It is a strong independent-script replication
candidate. It does not expose a unit property equivalent to ORACC `gw=unit`;
deriving units from translations or a hand-picked lexicon would change the
gold ontology and risk leakage. It should therefore be sealed as a secondary
context/sequence/entity control, not presented as a drop-in joint-five-state
replication without a separately justified projection.

The current
[Thesaurus Linguae Aegyptiae license terms](https://tla.digital/info/licenses)
impose restrictions on bulk copying, so this audit recommends the fixed,
licensed ORAEC/AES release rather than scraping TLA.

## 4. South Asian stress source: DHARMA Satavahana

- [DHARMA repository catalogue](https://dharmalekha.info/repositories)
- [Satavahana epigraphy repository at fixed commit](https://github.com/erc-dharma/tfb-satavahana-epigraphy/tree/a883987befeb5679ac88f23341f3d6a2987b607e)
- [Exact Satavahana tar.gz bytes](https://codeload.github.com/erc-dharma/tfb-satavahana-epigraphy/tar.gz/a883987befeb5679ac88f23341f3d6a2987b607e)
- [EpiDoc specification](https://epidoc.stoa.org/)

The fixed `tar.gz` has SHA-256
`a44b28a67704d370e1b1f20d3df87204c6d76e1bc6914ccffe3e5d9903964724`.
The audited repository contains 511 text XML files: 508 Middle Indo-Aryan and
3 Sanskrit records. Each audited record has an edition and translation, with
EpiDoc structures for document metadata, lineation, damage, and diplomatic
text.

The repository-level statement and individual XML availability declarations
are not uniformly worded. The safe redistribution posture is to retain every
file's attribution and apply the stricter observed CC BY-SA 4.0 condition to
combined derivatives.

The source is valuable because it is an ancient South Asian inscription
collection with short, context-bearing records. It does not provide token POS,
the four ORACC target labels, a native Brahmi glyph sequence, or bundled
facsimile images. It is therefore a regional sequence/context stress test, not
a replacement for the ORACC prospective validation task.

## 5. Linear B: researched but not admitted as primary

### DĀMOS and LiBER

- [DĀMOS database description](https://damos.hf.uio.no/about/database/)
- [LiBER official CNR record](https://explore.cnr.it/resource/item/113622?language=en-US)

DĀMOS provides broad Mycenaean text coverage and detailed epigraphic metadata,
but its content license is CC BY-NC-SA 4.0 and no immutable official bulk
snapshot was found. LiBER integrates transcription, apparatus, photographs,
findspots, scribes, chronology, and inventory data, but this audit did not find
an explicit machine-readable bulk redistribution license and fixed release.
Neither is admitted for a public, potentially prize-related V3 control.

### Mycenaean Series D

- [Fixed Zenodo record and DOI](https://zenodo.org/records/7404653)
- License metadata: CC BY 4.0
- File checksum: `md5:0c9b9190b86840c82cafdbf4f4b8c827`

The publisher's own description divides the 2,565 sequences into 513 sequences
processed from Series D tablets, 725 augmented sequences, and 1,327 duplicates
added to reduce bias. It supplies neither the V3 semantic labels nor native
images and has severe duplicate leakage by construction. The first 513
sequences may support a small, explicitly exploratory sequence diagnostic, but
the release must not be used as binding confirmation or represented as 2,565
independent ancient observations.

## 6. Classic Maya: rich structure, deferred rights and release gate

- [ClassicMayan project architecture](https://classicmayan.org/portal/doc/62)
- [ClassicMayan general open-access statement](https://classicmayan.org/portal/doc/6)
- [Bonn Maya Hieroglyphic Text and Image Archive](https://classicmayan.ulb.uni-bonn.de/)
- [Official archive description](https://classicmayan.org/portal/doc/96)
- [Example CC BY item-metadata statement](https://classicmayan.ulb.uni-bonn.de/content/titleinfo/10390612)
- [Example CC BY-NC-SA item-metadata statement](https://classicmayan.ulb.uni-bonn.de/content/titleinfo/9625063)

The project is designed to combine original hieroglyphic spelling,
transcription, epigraphic and linguistic analysis, translation, temporal and
regional metadata, photographs, and drawings. The portal states CC BY 4.0 for
materials made available on the site.

The ULB archive exposes varying item-metadata statements, including CC BY 4.0
and CC BY-NC-SA 4.0, but the English item pages expressly limit those
statements to metadata and exclude images. Image-reuse permission therefore
remains unverified. The corpus is continually growing, many
transcriptions and translations remain work in progress, and no immutable
complete machine-readable release with a corpus-wide per-item rights manifest
was identified.

Maya should be reconsidered only after a fixed TEI/JSON release exists and a
machine-verifiable manifest restricts each input layer to rights that permit
the intended use. General open access or a metadata license must not be
extended to images.

## 7. Proto-Elamite and CDLI: negative control only

- [CDLI Proto-Elamite glyph repository at fixed commit](https://github.com/cdli-gh/proto-elamite_data/tree/d2de8fc54ffff6700d8435d51c8f0ad99628f6fc)
- [Unicode Proto-Elamite proposal](https://www.unicode.org/L2/L2023/23196-proto-elamite.pdf)
- [CDLI Proto-Elamite tools](https://www.cdli.ox.ac.uk/wiki/doku.php?id=proto-elamite_tools)
- [CDLI image and reuse policy discussion](https://cdli.earth/articles/cdln/2012-3)
- [Current CDLI Terms of Use](https://cdli.earth/terms-of-use)
- [CDLI fixed data tag](https://github.com/cdli-gh/data/tree/2022.08)
- [Exact Proto-Elamite glyph tar.gz bytes](https://codeload.github.com/cdli-gh/proto-elamite_data/tar.gz/d2de8fc54ffff6700d8435d51c8f0ad99628f6fc)

The fixed glyph-repository `tar.gz` has SHA-256
`b0577e70f86c747b5c0d6217e81c44c4fadf9297d16495db168582b8a800ea67`
and contains 1,329 EPS sign-glyph files under CC BY 4.0.

The broader fixed CDLI data snapshot identifies 1,729 Proto-Elamite catalogue
records, including 1,597 categorized as administrative. In that snapshot, 801
records advertise photo availability and 1,440 line-art availability. Those
availability flags do not grant redistribution rights. The broader data
repository lacks an explicit repository license. The current CDLI terms and
published image policy restrict image reuse and may defer to item-level or
holding-institution restrictions.

Most importantly, Proto-Elamite is itself undeciphered. It has no accepted
semantic gold capable of showing that a method recovers known meanings.
Treating it as a known-script positive control would be circular. The
rights-clear EPS sign drawings may instead test whether a frozen method
abstains or avoids unsupported semantic confidence on an undeciphered system.
No CDLI object image should be copied into a public benchmark under the glyph
repository's separate CC BY license.

## Recommended sealing order

1. Keep the exact ORACC ED3b ZIP and closed eligibility/projection contract as
   feature-safety-exposed prospective validation, not binding confirmation.
2. If normalized glyphs will be consumed, create a separate prospective
   SumTablets seal covering the fixed Git commit, fixed HF revision, exact CSV
   digests, join, alignment rejection, and family grouping before development.
3. Reserve the fixed ORAEC snapshot for a later independent-script replication
   with a separately frozen task that does not invent an Egyptian unit label.
4. Reserve the fixed DHARMA Satavahana snapshot for a South Asian
   context/short-sequence stress test under the stricter per-file rights
   posture.
5. Freeze a non-cherry-pickable selection mechanism for binding confirmation:
   either independent private custody before development or a post-freeze
   public random beacon over a predeclared ordered eligible pool.
6. Do not admit Linear B, Maya, or Proto-Elamite as binding confirmation
   without resolving the specific rights, fixity, duplication, and
   semantic-gold failures documented above.

## Leakage, governance, and nonclaims

- Public availability is not blindness. This audit inspected source schemas,
  aggregate counts, licenses, limited examples, and gold-conditioned GDL-key
  rates. Those rates informed the ORACC observation sanitizer.
- A Git commit or SHA-256 establishes byte identity, not trusted time,
  independent custody, non-exposure, or independent preregistration.
- No source in this report authorizes use of a pretrained model that may
  already contain its public material. Validation should use the frozen
  project implementation and prohibit further raw source use in prompts,
  feature design, debugging, or post-result error analysis.
- Artifact identifiers, duplicate families, and normalized sequence
  fingerprints must remain grouped across every split. Public train/test names
  are not evidence that those splits satisfy the project's leakage contract.
- Rights for text, normalized glyphs, line art, photographs, metadata, and
  derivatives are distinct. A license for one layer must not be silently
  extended to another.
- This audit reports no model performance and makes no claim of blindness,
  custody, trusted timestamping, independent execution, Indus sign value,
  language identification, translation, decipherment, binding confirmation,
  prize eligibility, or prize result.

The repository and dataset counts above were observed in a local deterministic
audit but are not yet independently reproduced by a checked-in aggregate
receipt. The exact codeload/Hugging Face revisions and file digests make the
inputs identifiable; future admission still requires publishing the
corresponding deterministic aggregation procedure.
