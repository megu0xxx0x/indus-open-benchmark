# Context source-link preselection gate

**Status date:** 2026-07-31

**Source checkpoint:** `fd5148431b0fa9136336650208e2d570d0f176d8`

**Claim status:** static repository-only preselection contract; not a source
join, admitted row, transcription, Helsinki correspondence, decipherment
result, or authorization to access a source

## Purpose

The highest-information next question is whether archaeological context can
be connected to a separately controlled inscription record without using the
inscription signs to choose the match. Before designing that attempt, this
gate freezes its six candidate source-table rows and preserves every known
conflict.

The gate is intentionally smaller than a reviewed-evidence or runtime
contract. It records source locators only. It does not access either source,
join records, admit evidence, carry sign content, or run an experiment.

## Exact source table

The table order is source-table order only, not a ranking. Each displayed
field number, official record ID, and accession number is stored with its
exact identifier namespace and source ID.

| Row | Mackay field number | Penn official record ID | Penn accession | Role |
|---:|---|---:|---|---|
| 1 | SF 2000 | 83830 | L-141-160 | `lead_no_listed_material_conflict` |
| 2 | SF 3495 | 83829 | L-141-159 | `excavation_location_axis_conflict` |
| 3 | SF 3493 | 149372 | L-141-92 | `lead_no_listed_material_conflict` |
| 4 | SF 2428 | 238862 | L-141-176 | `lead_no_listed_material_conflict` |
| 5 | SF 3051 | 329820 | L-141-177 | `shared_penn_target_identity_collision` |
| 6 | SF 2558 | 329820 | L-141-177 | `shared_penn_target_identity_collision` |

The exact role counts are:

- three `lead_no_listed_material_conflict` rows;
- one `excavation_location_axis_conflict` row; and
- two `shared_penn_target_identity_collision` rows.

Every row has both of these closed statuses:

- `preselection_status`: `source_locator_only`;
- `future_join_status`: `not_joined_requires_separate_contract`.

The identifier order inside every row is also exact:

1. a `field_number` under source `mackay-chanhu-daro-1943`;
2. an `official_record_id` under source
   `penn-museum-collections-data`; and
3. an `accession_number` under the same Penn bulk source.

Bare or namespace-swapped identifiers are rejected. These triples preserve
where a value came from; they do not prove that values refer to the same
physical object.

## Conflicts stay open

SF 3495 retains role `excavation_location_axis_conflict` and unresolved axis
`excavation_location`. The gate does not promote it to an unconflicted lead.

SF 3051 and SF 2558 are separate Mackay field rows. Both point to Penn
official record 329820 and accession L-141-177, and both remain in collision
group `chanhu-daro-penn-329820-collision`. The gate neither merges them nor
chooses one as the Penn object's identity.

The registry counts six locator rows but only five distinct Penn catalog
records, with zero admitted joins. A catalog-record count is not an artifact
count or a physical-identity decision. `physical_identity_verified` remains
false.

## Rights are layer-specific

The rights record has exactly three layers:

1. `penn_bulk_metadata` is CC BY 4.0, metadata-only, redistributable, and
   contains no media.
2. `penn_item_page_association` is an extra-bulk item-page layer. It is not
   registered in the source registry, its source binding is null, its license
   is null, its rights are unknown, its scope is link-only, and it records
   `redistribution_permitted=false` without making a legal-rights conclusion.
3. `mackay_report_locator` has a null license, unknown rights, link-only scope,
   no media, and the same frozen false field without an inferred legal
   prohibition.

The CC BY 4.0 status of Penn bulk metadata does not flow into the Penn item
page. No image, crop, PDF page, plate, scan, or other media byte is part of
this gate.

## Closed claim surface

The registry has no positive, probable, exact, joined, or admitted status.
It contains no sign, glyph, token, sequence, transcription, Helsinki row,
reading direction, OCR value, meaning, language, translation, phonetic value,
image, quote, source text, page byte, or plate byte.

The following assertions are all fixed false:

- context correctness verified;
- decipherment evidence;
- evaluation admitted;
- evaluation nonexposure verified;
- field-number truth verified;
- future-join rights verified;
- object authenticity verified;
- physical identity verified;
- selection representativeness verified;
- source independence verified; and
- transcription approved.

The absence of these values is not missing documentation to be filled by
guessing. It is the scientific boundary of this checkpoint.

## Schema and packaging boundary

The Draft 2020-12 schema fixes the entire object. The `links` array has
minimum and maximum length six, six exact `prefixItems`, and `items: false`.
The three rights layers use the same exact-array construction. All top-level
properties are required and additional properties are forbidden. Canonical
exact-byte tests bind both registry and schema.

A scoped recursive exercise applied 355 mutations across the frozen object;
all 355 tested mutations were rejected. That evidence demonstrates exact
static validation of the tested object. It does not prove that a source join
is true or that a runtime loaded these bytes.

This checkpoint has no production builder, command-line operation, API,
strict runtime loader, or source-access implementation. The registry and its
test are present in the source repository and source distribution but absent
from the wheel. The schema is included in the wheel. Therefore this is not a
package-level or runtime gate.

Any future operationalization must, at minimum:

1. read a bounded exact byte container;
2. pass those bytes through the project's strict `decode_json` path, rejecting
   invalid UTF-8, duplicate keys, non-finite values, and trailing data;
3. compare exact canonical `encode_json` bytes and validate against the exact
   schema rather than an advisory shape;
4. add installed-source and wheel resource-inclusion tests that state exactly
   which resources are available; and
5. preserve a no-source-access mode until a separately reviewed execution
   contract grants that authority.

None of those future steps is implemented or authorized here.

## Validation record

The source checkpoint adds exactly these three mode-`100644` files:

- `registry/chanhu-daro-helsinki-gate-v1.json`;
- `schemas/context-source-link-gate.schema.json`; and
- `tests/test_context_source_link_gate.py`.

The diff has 979 additions and binary diff SHA-256
`56d8124f05223df5c9e010cfc97de328b5f7b6c3c2bc52f2aa8e8a7d10bd8de9`.
That digest identifies diff bytes; it is not a signature, trusted timestamp,
custody record, or source-access receipt.

Local evidence recorded:

- 9 focused tests passed in about 0.03s;
- 19 related tests passed with one environment-specific skip in 0.667s;
- all four publication-boundary tests passed;
- Ruff lint passed, Ruff format accepted all 182 checked files, and Pyright
  reported zero errors, warnings, or information messages;
- the successful offline isolated build produced a 341-member sdist with the
  exact three new files and a 164-member wheel with only the schema from that
  three-file set; and
- Gitleaks scanned 67 commits and approximately 7.22 MB with no leaks.

A non-isolated build command first stopped before build because its backend
was absent; it did not produce an artifact. The locked offline isolated build
then succeeded. This is a tooling event, not source or scientific evidence.

The first full suite ran 1,087 tests with 19 environment-specific skips and
recorded exactly two failures and two errors. All four outcomes were Quicknet
fail-closed checks rejecting vendored Noble regular files at `0664` and
directories at `0775`, inherited in the isolated worktree. Only the
worktree's vendored modes were normalized to `0644` and `0755`; no tracked
byte, content hash, or source diff changed. All 23 Quicknet tests then passed
in 4.634s. The clean second run completed the 1,087-test full suite with
`OK (skipped=19)` in 976.546s. The failed first attempt remains part of the
validation history.

The first independent audit found one major issue: the draft incorrectly
extended the Penn bulk-source binding to the extra-bulk item-page layer. It
also found one minor naming issue that described catalog records as objects.
Both were corrected. The final independent audit of the exact candidate
reported zero blockers, zero major findings, and zero minor findings.

Public CI run `30635957691` succeeded for event `push` at exact head SHA
`fd5148431b0fa9136336650208e2d570d0f176d8`. Every job asserted Node
`v24.18.1` on Linux/x64. Python 3.11, 3.13, and 3.14 passed Quicknet 6/6 in
527.702196ms, 655.421586ms, and 503.092653ms, respectively, and completed the
1,087-test full suite with `OK (skipped=22)` in 810.027s, 946.248s, and
759.619s, respectively. Each job also passed Ruff (`All checks passed`), Ruff
format with all 182 files accepted, Pyright with zero errors, warnings, or
information messages, and both sdist and wheel builds.

## Non-execution statement

This checkpoint made no network request to a research or source endpoint, no
external or protected source-byte download, no image/page/plate retrieval, no
Helsinki-row access, no institution or source-holder contact, and no
operational gate or real source-link attempt. Repository publication and CI
are outside that statement. No external research-source or media bytes were
added. This document does not authorize any of those actions.

There is no selected match, probable or exact correspondence, joined record,
admitted observation, approved transcription, sign sequence, reading,
translation, decipherment evidence, public claim authorization, prize
submission, or prize result.

## Next research gate

Infrastructure expansion is hard-frozen for this step. Host Node 24
activation, dynamic-closure expansion, and an official one-shot runner are
deferred unless a real experiment exposes a reproducible need.

At source checkpoint `fd5148431b0fa9136336650208e2d570d0f176d8`, the next
work was to design and separately freeze one non-sign source-link attempt. It
had to choose source rows without using sign, glyph, transcription, or
sequence similarity; preserve SF 3495's conflict; keep SF 3051 and SF 2558
separate; treat `no_link` as a fully valid stop; and forbid substitution after
inspection.

This document does not authorize source access or execution of that attempt.

## Follow-up policy freeze — 2026-08-01

Commit `c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9` freezes that decision
surface as the separate
[static source-reported-link policy](SOURCE_REPORTED_LINK_POLICY_V1.md). The
preselection gate remains the immutable parent input table; it was not turned
into a runtime gate and was not executed.

The follow-up policy requires one mutually exclusive terminal state for each
of the six parent rows under precedence `contract_blocked`, `unresolved`,
`source_reported_link`, then `no_link`. It forbids aggregation, omitted rows,
and post-hoc substitution. Hard rejection precedes state evaluation and is not
a result. `source_reported_link` is a source-report label only, not a
positive/truth state or admitted join.

The current real state is `contract_blocked` because the Penn item page is
unregistered and unknown-rights and because no external exact source revision,
rights-handling, inspection, and complete-roster contract exists. The two
future passes are coded machine passes with distinct identifiers and seals
only; their human, model, and organizational independence, blinding, and
nonexposure are unverified.

No runtime evaluator, source access, source byte, observation, pass,
source-reported-link/no-link outcome, join, transcription, translation,
decipherment evidence, or prize result exists. The next gate is a separate
source registration and rights contract, not execution under this document.
