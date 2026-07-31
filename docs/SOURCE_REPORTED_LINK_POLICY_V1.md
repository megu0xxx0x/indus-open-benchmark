# Static source-reported-link decision policy

**Status date:** 2026-08-01

**Source checkpoint:** `c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9`

**Parent checkpoint:** `54fccb7a86a0d45de4e626b57a6332d091c11db2`

**Claim status:** static repository-only decision contract; not a runtime
evaluator, source-access authorization, observation, link result, admitted
join, translation, decipherment result, or prize result

## Purpose and execution boundary

This policy freezes how a future, separately authorized non-sign source
inspection would classify each row of the existing Chanhu-Daro preselection
table. It prevents an aggregate answer from hiding rows, prevents post-hoc
row replacement, and makes an unresolved or no-link result reportable without
turning either into a source join.

The current prerequisite state is `contract_blocked`. Authorization is
`not_authorized`, execution is `not_executed`, and
`runtime_evaluator_implemented` is false. The policy contains no observations
and does not inspect, retrieve, parse, or compare any research-source bytes.
It is a static decision surface only.

The success-side name is deliberately `source_reported_link`. It means that
two coded machine passes reported the same bounded source-local locator under
the external prerequisites below. It does not mean “positive,” true match,
correct context, physical identity, or admitted join. There is no state named
`positive` in this policy.

## Parent binding and six ordered result slots

The policy binds the exact parent preselection artifacts:

| Parent artifact | Size | SHA-256 |
|---|---:|---|
| `registry/chanhu-daro-helsinki-gate-v1.json` | 6,955 bytes | `43c0fae1a8558fbffeb062725e401e0c3c1de570e5f8f7eef610ca2616cbfb3d` |
| `schemas/context-source-link-gate.schema.json` | 9,216 bytes | `72109818eb55aca008b0f34b1d6c627efd0e38bdbaff8c500cb3c60dc74e3002` |

All six parent rows are required in source-table order, not rank order:

| Index | Parent link ID | Preserved role | Preserved unresolved state |
|---:|---|---|---|
| 0 | `chanhu-daro-preselection-v1:000` | `lead_no_listed_material_conflict` | none |
| 1 | `chanhu-daro-preselection-v1:001` | `excavation_location_axis_conflict` | `excavation_location` |
| 2 | `chanhu-daro-preselection-v1:002` | `lead_no_listed_material_conflict` | none |
| 3 | `chanhu-daro-preselection-v1:003` | `lead_no_listed_material_conflict` | none |
| 4 | `chanhu-daro-preselection-v1:004` | `shared_penn_target_identity_collision` | collision retained |
| 5 | `chanhu-daro-preselection-v1:005` | `shared_penn_target_identity_collision` | collision retained |

The result vector length is exactly six. Each parent row must receive exactly
one mutually exclusive terminal state. Result aggregation, row omission, and
post-hoc row substitution are forbidden. The last two slots remain distinct
even though their parent rows share the same Penn catalog target.

## Terminal-state policy

State evaluation uses this exact precedence:

1. `contract_blocked`;
2. `unresolved`;
3. `source_reported_link`; and
4. `no_link`.

| State | Exact policy meaning |
|---|---|
| `contract_blocked` | One or more externally committed prerequisites are absent and observations are empty. The prerequisites are source registration, exact source revision, rights handling, inspection procedure, and the complete ordered source roster. This is the current state. |
| `unresolved` | The source is unreadable, inspection errors, ambiguity, multiple candidates, pass disagreement, source-revision disagreement, roster-commitment disagreement, or incomplete roster coverage prevents a stronger state. A bare “not found” without complete-roster evidence is also `unresolved`. |
| `source_reported_link` | External prerequisites match exactly and both passes use the same source revision, parent target, exactly one candidate, and the same bounded ASCII source-local locator without a forbidden channel. This is a source report only, not truth authentication or admission. |
| `no_link` | For one parent row, both passes either explicitly reject the same exact target at the same source revision, or both attest complete one-to-one processing of the exact ordered roster with matching count, roster hash, revision, processed count, completeness digest, and zero missing, extra, duplicate, unreadable, error, and ambiguous counts. |

`no_link` applies per parent row. It is not permission to inspect another row
or substitute a new target. For the row-absent alternative, both passes must
bind the exact ordered source-roster count and SHA-256, exact source revision,
processed-count equality, and an exact completeness-attestation digest. A
mere search miss does not meet this standard.

`hard_reject` is not a terminal result state. Hard rejection is applied before
state evaluation and produces no scientific result.

## Two-pass separation boundary

The frozen mode is: **two separately sealed coded machine passes; only
`pass_id` and `seal_sha256` are required to differ**.

That is the complete implemented separation claim. The policy does not verify
human independence, model independence, organizational independence,
blinding, or nonexposure. It does not authenticate who or what produced a
pass. Distinct identifiers and seals alone must not be described as two
independent reviews or as independent replication.

## Source registration and rights blocker

The Mackay report locator is registered, but its rights are unknown and its
scope is link-only. The frozen policy records
`redistribution_permitted=false`; it makes no legal-rights conclusion. The
Penn item page is unregistered, has a null source-registry binding and null
license, unknown rights, and link-only scope. It also records
`redistribution_permitted=false` without converting that field into a legal
prohibition. Penn bulk metadata's CC BY 4.0 license is explicitly not
inherited by the Penn item page.

Consequently, the current real state is `contract_blocked`. A separate source
registration and rights contract must bind the exact external source revision,
rights handling, inspection procedure, and complete ordered source roster
before observations could exist. This policy neither supplies that contract
nor authorizes the source access needed to create it.

## Forbidden channels and hard rejection

The attempt may not carry or use confidence, excerpts, free text, glyphs,
images, linguistic values, media, notes, OCR, pages, raw values, sequences,
signs, similarity, source bytes, tokens, transcriptions, or visual values.
These fields are forbidden because the experiment is meant to ask whether a
source-reported association can be found without choosing by inscription
content or visual resemblance.

The following inputs hard-reject before state evaluation:

- malformed input;
- noncanonical input;
- observations before prerequisites;
- parent-commitment mismatch;
- verification-commitment mismatch; and
- any forbidden channel.

Hard rejection is fail-closed control behavior. It must not be counted as
`contract_blocked`, `unresolved`, `source_reported_link`, or `no_link`.

## Schema, canonical bytes, and packaging

Commit `c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9`, whose parent is
`54fccb7a86a0d45de4e626b57a6332d091c11db2`, adds exactly three
mode-`100644` files and 898 lines. Its exact binary diff SHA-256 is
`a635c012adefc52e05677aa1b337afe45ba53a25d4589bcb71446c7c2c0e8982`.

| File | Bytes | SHA-256 |
|---|---:|---|
| `registry/source-reported-link-policy-v1.json` | 7,967 | `c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90` |
| `schemas/source-reported-link-policy.schema.json` | 8,589 | `d951541892bb6a5ef092d44e9a5564da2261f960e52e3e84a95ecd5ef8e61aff` |
| `tests/test_source_reported_link_policy.py` | 16,778 | `8870593c1195aad4138626343d9e051da0815fb6695c8f6515f9e9270b5af045` |

Draft 2020-12 `const` fixes the policy semantically, but JSON Schema treats
JSON numbers such as `6` and `6.0` as equivalent. Schema validation alone is
therefore not exact-byte validation. Canonical byte identity is separately
required, and any noncanonical input is a hard reject.

The exact build produced a 345-member sdist with all three policy files and a
165-member wheel with only the schema from that three-file set. The sdist
SHA-256 is
`378f38b04f9e396e96881d4d0a195003080a790256bd34958bb8992114c15033`;
the wheel SHA-256 is
`3f7cb59e4eb7ace577f7dadf2e8e056d644791bf138889e8dbfdaf2e04aba9a5`.
The policy registry and its test are not wheel resources. No installed loader
or runtime evaluator exists, so this is not a package-level or runtime gate.

## Validation and audit record

Focused policy validation passed all 7 tests. The combined policy,
preselection-parent, and publication-boundary set passed all 20 tests. Ruff
lint passed, Ruff format accepted all 183 checked files, and Pyright reported
zero errors, warnings, or information messages. The final independent audit
of the exact candidate reported zero blockers, zero major findings, and zero
minor findings.

The first full-suite run reached 1,094 tests in 1034.566s with 19
environment-specific skips and recorded exactly two failures and two errors.
All four outcomes were Quicknet fail-closed mode checks: the isolated
worktree's vendored Noble closure inherited `0664` regular files and `0775`
directories. Only those isolated-worktree modes were normalized to
`0644`/`0755`. Tracked bytes, candidate hashes, and the exact staged diff did
not change. Focused Quicknet then passed all 23 tests in 4.197s. The clean
full rerun completed all 1,094 tests in 1084.894s with `OK (skipped=19)`.
The failed first run remains part of the validation history and is not
relabeled as success.

Gitleaks scanned 69 reachable commits and 7,292,640 bytes with no leaks.

Public CI run `30654728606` succeeded at exact head
`c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9`:

- Python 3.11 passed Quicknet 6/6 in 398.928145ms and all 1,094 tests in
  636.266s with 22 skips;
- Python 3.13 passed Quicknet 6/6 in 522.070668ms and all 1,094 tests in
  910.867s with 22 skips; and
- Python 3.14 passed Quicknet 6/6 in 542.131729ms and all 1,094 tests in
  930.525s with 22 skips.

Each matrix job also passed the exact Node 24.18.1 Linux/x64 assertions, Ruff,
formatting of all 183 files, zero-finding Pyright, and sdist/wheel builds. CI
is reproducibility evidence for the public source tree, not source-access,
custody, runtime-attestation, or scientific-result evidence.

## Abandoned local runtime prototype

Before this static policy was frozen, a local untracked runtime-evaluator
prototype was reviewed and discarded. Pre-publication design/security review
found that it could misrepresent an incomplete roster as complete, return an
aggregate that hid five of the six rows, trust duck-typed verification values,
allow raw parser exceptions to escape the closed error boundary, and fail its
installed-schema lookup.

The prototype was never staged, committed, pushed, packaged, or used on
source data. It produced no observation or result and was deleted. The project
then narrowed the checkpoint to the static policy, schema, and tests above.
These findings are retained to prevent a later implementation from silently
reintroducing the rejected design.

## Non-execution and nonclaims

During this static-policy checkpoint, no request to a research or protected
source endpoint, external source-byte download, image/page/plate/media
retrieval, Helsinki-row access, institution or source-holder contact,
evaluator execution, source inspection, coded pass, observation, locator
comparison, roster attestation, source-reported-link result, or no-link result
occurred. Repository publication and public CI are outside that statement and
authorize none of those actions.

The policy verifies no caller honesty, truth, source independence, context
correctness, field-number truth, object authenticity, physical identity,
selection representativeness, future-join rights, transcription, evaluation
admission, join, translation, decipherment, claim authorization, prize
submission, or prize result. Every such nonclaim remains closed.

## Next gate

The next safe work is a separate source registration and rights contract. It
must bind the Penn item-page source, exact source revisions, rights handling,
inspection procedure, and complete ordered source roster without opening or
inspecting the sources under this policy.

Only new explicit authority after that contract could permit implementation
of a strict runtime evaluator or execution of the two coded machine passes.
Any future implementation must preserve all six per-row results, state
precedence, hard-rejection boundary, conflicts, no-aggregation rule,
no-substitution rule, forbidden channels, and canonical-byte checks. This
policy itself authorizes none of that work and establishes no decipherment
result.
