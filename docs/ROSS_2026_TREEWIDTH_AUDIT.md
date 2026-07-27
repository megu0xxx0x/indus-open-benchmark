# Ross 2026 treewidth reproduction audit

Status: independent computational audit
Audit date: 2026-07-26
Scientific scope: structural graph statistic only; no language, reading, or translation is inferred

## Result

The reported minimum-degree treewidth upper bound of 26 is reproducible from the fixed
`mayig` revision below. It is not, however, unusually high under any of the three explicit null
models in this audit. In the artifact-flat analysis, 93% to 100% of null runs produced an upper
bound at least as large as 26.

This result rejects neither a linguistic nor a non-linguistic interpretation of the Indus sign
system. It shows that this statistic and these data do not support the stronger claim that a
value of 26 is by itself a discriminator of language.

## Fixed input

- Upstream repository:
  [mayig/indus-valley-script-corpus](https://github.com/mayig/indus-valley-script-corpus)
- Revision: `ad2f1e218a34b8c33c57de0d6cb8d99272765bbb`
- Local import: `indusbench import-mayig`; no upstream corpus files are vendored here
- Imported corpus SHA-256:
  `50ac90a3771f7ddabfb38344b49cf952e5371cd766792bc29b20ee0350275815`
- Audit seed schedule: integer seed `20260726 + zero-based run index`
- Runs per null model: 100

The audited preprint is
[Reading the Indus Valley Script](https://zenodo.org/records/19362548), updated
2026-07-21 in the record reviewed for this audit.

## Boundary audit

The upstream data contain seven artifacts with more than one stored line. Treating each line as
an independent sequence and flattening all graphemes on an artifact are therefore different
analyses.

| Sequence policy | Sequences | Tokens | Vertices | Edges | Upper bound |
|---|---:|---:|---:|---:|---:|
| Canonical line, minimum length 1 | 186 | 1,003 | 182 | 515 | 26 |
| Artifact-flat, minimum length 1 | 179 | 1,003 | 182 | 521 | 26 |
| Artifact-flat, minimum length 2 | 178 | 1,002 | 181 | 521 | 26 |

The artifact-flat mode reconstructs order from the upstream grapheme index stored by the
reviewed importer. The safe CLI default remains canonical-line mode because a line boundary must
not be erased silently.

The preprint reports 178 inscriptions, 1,003 tokens, 182 vertices, and one connected component.
Those four counts cannot be produced together by one transparent exclusion policy on the fixed
public revision:

- retaining the one-sign artifact `M-137A/P379` gives 179 sequences, 1,003 tokens, 182 vertices,
  and two components because `P379` is isolated;
- removing it gives 178 sequences, 1,002 tokens, 181 vertices, and one component.

This accounting discrepancy does not change the reproduced upper bound of 26. It does require
the original exclusion and vertex-retention rules to be disclosed before other reported graph
statistics can be treated as exactly reproduced.

## Graph and estimator

For each selected sequence, the audit creates an undirected edge between consecutive unequal
signs. It retains every observed sign as a vertex, excludes self-loops, and collapses repeated
edges. It then applies deterministic minimum-degree elimination and reports the maximum induced
degree encountered.

This is a heuristic **upper bound**, not an exact treewidth computation. Equal-degree choices can
change a heuristic result, so this implementation fixes lexical initialization and stable update
order and records that policy in every JSON report. It is an independent standard-library
implementation of the stated minimum-degree procedure, not a claim of bit-for-bit identity with
every NetworkX version or graph insertion order.

## Null-model result

The main comparison retains all 179 artifact-flat sequences and all 1,003 tokens.

| Null model | Minimum | Mean | Median | Maximum | Runs with null ≥ 26 |
|---|---:|---:|---:|---:|---:|
| Global shuffle preserving exact sign counts and sequence lengths | 25 | 28.73 | 29 | 32 | 99% |
| Within-sequence shuffle preserving each artifact's sign multiset | 23 | 27.23 | 27 | 30 | 93% |
| Independent draws from the empirical sign-frequency distribution | 26 | 30.32 | 30 | 34 | 100% |

The relevant tail for a claim that 26 is anomalously **high** is the proportion of null runs at
or above 26. The report also retains both opposite-tail rates and every run-level seed and value,
so alternative preregistered tests can be checked without rerunning the audit.

These nulls are deliberately simple. They do not simulate the full space of administrative,
religious, emblematic, or linguistic production processes. Consequently:

- a high null rate defeats the proposed high-treewidth threshold on this corpus;
- it does not establish that the signs are non-linguistic;
- it does not validate or invalidate any proposed sign meaning;
- broader claims still require matched comparative systems, leakage controls, and held-out
  predictions.

## Reproduction

After checking out the fixed upstream revision locally:

```bash
uv run indusbench import-mayig \
  /path/to/indus-valley-script-corpus \
  /tmp/mayig-fixed.jsonl \
  --revision ad2f1e218a34b8c33c57de0d6cb8d99272765bbb \
  --retrieved-at 2026-07-26T00:00:00Z

uv run indusbench treewidth-audit \
  /tmp/mayig-fixed.jsonl \
  --sequence-unit artifact_flat \
  --min-length 1 \
  --runs 100 \
  --seed 20260726 \
  --output /tmp/ross-treewidth-audit.json
```

For the repository's line-preserving default, replace `artifact_flat` with `canonical_line`.
The output binds the result to the imported corpus digest and records sequence filtering,
estimator policy, preservation/destruction rules for every null, summary statistics, and all
run-level values.
