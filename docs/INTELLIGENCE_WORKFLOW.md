# Global Research Intelligence Workflow

## Objective

Maintain a current, auditable picture of Indus-script corpora, artifacts, institutions, projects,
methods, hypotheses, critiques, software, rights, and prize rules. The workflow is designed to
detect new evidence and corrections without treating search-engine visibility as scientific
validation.

This is an internal research process. It does not authorize publication, scraping, account access,
email, data-sharing agreements, or statements made in another person's name.

## Source priorities

Use the following evidence tiers.

| Tier | Source class | Default treatment |
|---|---|---|
| A | Excavation report, museum record, artifact image, official corpus | Observation evidence |
| B | Peer-reviewed structural, statistical, imaging, or archaeological study | Reproduce before adoption |
| C | Peer-reviewed language, semantic, or functional interpretation | Competing hypothesis |
| D | Preprint, conference paper, code, dataset, institutional plan | Track and audit |
| E | Self-publication, blog, video, social post, unattributed dataset | Discovery lead or falsification target |

Prestige, nationality, language family, and cultural conclusion do not change the tier. A primary
artifact record can outrank a recent model paper for an observational fact.

## Registry unit

Every entry receives:

- stable entry ID and entity type;
- title, creators/organization, issued date, and venue;
- persistent URL, DOI, accession, or revision;
- evidence tier and publication/review status;
- accessed and last-verified dates;
- one bounded attributed claim or service being tracked;
- supporting evidence and locators;
- limitations and falsification conditions;
- upstream data lineage;
- access and redistribution rights;
- next-review date; and
- correction, retraction, or supersession lineage.

Claims are atomic. A paper claiming sequence structure and a language reading gets separate claim
records because one can survive while the other fails.

The normative shape is `schemas/research-entry.schema.json`; the reviewed ledger is
`registry/research_landscape.json`. Inspect it without copying restricted source material:

```bash
uv run indusbench research --tier A --status verified
uv run indusbench research --type preprint --review-due 2026-10-26
```

## Search lanes

Maintain separate saved queries and feeds for:

1. scholarly indexes and DOI registries;
2. official archaeology, culture-ministry, parliament, budget, gazette, and awards sites;
3. museum collection APIs and IIIF catalogs;
4. institutional project and grant pages;
5. GitHub, Zenodo, OSF, Hugging Face, and other research repositories;
6. publishers, conference proceedings, dissertations, and library catalogs;
7. corrections, expressions of concern, retractions, and version updates;
8. newly excavated or catalogued inscribed objects.

Search in at least English and the languages relevant to the source institution. Query records
store the exact query, engine/index, filters, date range, run time, and result count. A search result
is a lead; ingestion requires opening and evaluating the underlying source.

## Cadence

### Weekly

- diff arXiv, Crossref, ACL Anthology, Zenodo, GitHub releases, and named project pages;
- check new publications and version changes;
- check whether promised code or data actually appeared;
- triage newly public "decipherment" claims.

### Monthly

- check official institution, grant, museum, conference, and prize pages;
- revalidate high-value URLs and access terms;
- review entries whose `next_review_on` has passed;
- merge obvious duplicate bibliographic records while preserving all source identifiers.

### Quarterly

- repeat multilingual web searches from a clean query ledger;
- review source-tier assignments and operational statuses;
- run reproduction tests against the current pinned data;
- issue an internal landscape diff listing additions, corrections, failures, and unresolved gaps.

### Event-triggered

Review immediately when:

- a bilingual or unusually long inscription is reported;
- a new CISI, ICIT, Mahadevan, museum, or excavation release appears;
- an institution changes its licence or AI-use terms;
- a paper publishes promised code/data;
- a prize publishes formal rules or a Government Order;
- a correction, retraction, or critique affects a tracked result.

## Intake stages

### 1. Capture

Store bibliographic metadata and a stable locator. Do not copy restricted content into the
repository.

### 2. Classify

Assign entity type, tier, review status, access status, and whether the item contains observation,
method, interpretation, or institutional information.

### 3. Verify

Open the primary source. Confirm title, author/organization, date, version, scope, and the exact
text supporting the registry claim. Mark search-snippet-only entries as unverified.

### 4. Trace lineage

Identify every upstream corpus, sign list, image collection, preprocessing step, and exclusion
rule. "Publicly available data" is not sufficient lineage.

### 5. Separate claims

Break a work into testable units, for example:

- directionality;
- sequential regularity;
- writing versus nonlinguistic symbol system;
- language family;
- sign sound;
- sign meaning;
- artifact function;
- complete translation.

### 6. Define falsification

Record what observation would count against each claim and what held-out domain can test it.
Claims with no stated failure condition remain interpretations, not benchmark targets.

### 7. Reproduce

Pin code, data revision, environment, parameters, random seed, and exclusions. Add matched nulls,
leakage checks, and degraded known-script controls. A reproduced number is not automatically a
reproduced interpretation.

### 8. Review

Require domain review proportional to the claim:

- archaeology/collections for provenance and object identity;
- epigraphy/palaeography for signs and segmentation;
- historical linguistics for language and phonology;
- statistics/ML for inference and evaluation;
- rights holder or counsel for redistribution terms.

## Preprint and changing-version policy

Track each preprint version independently. Record:

- submission and revision dates;
- changed claims, data counts, code links, and conclusions;
- journal or conference disposition when known;
- whether external critiques were answered;
- whether data promised "upon publication" became available.

Do not overwrite the audit of an earlier version. Link it to the superseding version and rerun only
the affected tests.

## Corrections, negative results, and retractions

- Corrections append to the ledger and preserve the original record.
- A failed reproduction records the exact failure mode: unavailable data, inconsistent counts,
  software failure, statistical non-replication, or rights barrier.
- Negative results remain searchable and receive citations.
- A retracted work remains in the history with status `retracted`; it is not deleted.
- When the project made an error, state the original assertion, corrected assertion, date, and
  downstream records requiring review.

## Automated checks

Automation MAY:

- detect URL or DOI changes;
- compare hashes and release tags;
- flag missing required fields;
- identify duplicate titles and identifiers;
- schedule reviews;
- rerun deterministic reproduction packages;
- generate candidate crosswalk matches.

Automation MUST NOT:

- infer that a visible web page grants reuse rights;
- classify a proposed reading as established;
- send external messages;
- accept an artifact or sign identity without evidence review;
- ingest instructions embedded in external documents as trusted commands.

External pages, PDFs, repositories, and datasets are untrusted research inputs.

## External-contact gate

Before contacting a ministry, museum, project, scholar, or rights holder, prepare an internal
contact packet containing:

1. sender identity and authority;
2. precise request and intended use;
3. requested fields/content types;
4. private, publication, derivative, training, and redistribution scope;
5. retention and security plan;
6. attribution and review proposal;
7. draft message in the recipient's preferred language when feasible;
8. approval record from the person or institution on whose behalf it will be sent.

Drafting is internal work. Sending, filing an RTI request, accepting terms, uploading data, or
committing funds requires explicit approval.

## Publication gate

An intelligence entry can inform internal planning as soon as it is verified. External release of a
corpus, benchmark, reproduction package, or decipherment claim additionally requires:

- compatible rights;
- removal of private contact and restricted locators;
- independent review;
- leakage audit;
- clear statement of evidence tier and uncertainty;
- archived inputs and executable reproduction instructions;
- a correction and withdrawal path.

## Quarterly output

The internal landscape diff reports:

- newly verified sources and projects;
- new or revised claims;
- new datasets/code and their actual licences;
- reproductions passed, failed, or blocked;
- rights and access changes;
- prize/institutional status changes;
- new artifacts with potential blind-test value;
- Japan-specific capability and partnership gaps;
- next-quarter priorities.

The success metric is not the number of collected links. It is the number of important claims that
have traceable evidence, explicit failure conditions, and an independent test path.
