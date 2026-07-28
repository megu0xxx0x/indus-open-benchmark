# Project handoff instructions

This file applies to the entire `indus-open-benchmark` repository.

## Read first

Before changing anything, read
[`docs/DEVELOPMENT_PLAN_AND_LOG.md`](docs/DEVELOPMENT_PLAN_AND_LOG.md). It is
the public project status, safety boundary, development plan, and continuation
guide.

The authoritative shared source history is the public GitHub `main` branch:

```text
https://github.com/megu0xxx0x/indus-open-benchmark
```

Machine-specific operating notes are deliberately kept outside Git. Do not add
hostnames, addresses, account names, home-directory paths, authentication
details, private key metadata, local storage topology, or private corpus
inventories to tracked files or public issue/CI output.

## Safety and authority boundary

- This project does **not** claim that the Indus script has been deciphered.
- Public development data are neither blind nor final evaluation data.
- Source publication does not authorize publication of ignored data,
  externally governed data, institutional contact, a prize entry, or a
  decipherment claim.
- `data/raw/` and `data/derived/` may contain private or externally governed
  material. The entire `data` path is ignored and must not be vendored,
  published, attached to issues, copied into CI, or treated as redistributable.
- Do not publish a private corpus path, filename, identifier, item-level value,
  exact inventory, byte total, content or manifest digest, private audit
  result, or operational timestamp.
- A public hash or development lock is not proof of blindness, custody,
  authorship time, runtime isolation, or scientific correctness.
- Do not contact an institution, create a real hidden-test companion, submit
  for a prize, or make a translation/decipherment claim without separate
  explicit authority.
- Preserve existing work. Inspect dirty or untracked state before editing, and
  never use broad destructive cleanup to make a worktree look clean.

## Resume checklist

Use the project-local commands and locked environment:

```bash
git status --short --branch
git fetch --prune
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python -m unittest discover -s tests -v
uv run indusbench --help
```

Before publication, also inspect the exact tracked tree and archives for
ignored/private material, run secret scanning, verify local Markdown links, and
confirm the public remote head.

## Public logging rule

Tracked status documents may record public source changes, reproducible
commands, public test expectations, scientific limitations, and public release
decisions. Detailed machine operations, credentials, private-data execution
results, and incident evidence belong in an owner-only handoff outside Git.

When a public status update is necessary, record only the minimum information
needed for another contributor to understand the source tree. Use synthetic or
placeholder paths in examples.

## Current safe next work

MTAAC V4 completed once and returned `development_killed`. Overall and paired
development metrics improved, but the fixed mild `unit` and
`settlement_name` recall gates failed. No final V4 model was fitted. Do not
rerun or retune V4, and do not execute the prospective validation source under
that protocol.

The final MTAAC V5 code-and-plan contract changes only the emission regularizer
for the `quantity`/`unit` and `person`/`settlement` pairs. It keeps the V4
feature/profile, sequence, optimizer, class adjustment, parameter count, and
fold contracts fixed; exposes no weight or grouping search; requires every
rare-state precision, recall, macro-F1, paired-fold, and clean-integrity gate;
and retires MTAAC after its single valid result regardless of outcome.

After independent review and public code-and-plan freeze, the only authorized
MTAAC work is one exact V5 command followed by aggregate validation and a
separate result publication. Do not alter V5 after observing any scientific
metric. Before any metric is emitted or exposed, only an environmental or I/O
failure may retry the byte-identical implementation, plan, archive, and CLI
arguments; every other change or partial metric retires V5 without a retry. Do
not execute the prospective source under V5; even a pass only advances to a
separately frozen prospective evaluator.

The local submission commitment `S` remains implemented. An independently
custodial hidden-test companion remains blocked until a real external
custodian, storage/access procedure, and explicit authority exist.

Safe public work may improve source/provenance/rights evidence, harden the
non-blind development protocols, extend synthetic interoperability tests, or
prepare non-operational specifications. Do not infer rights, promote private
material, fabricate a custodian, generate real hidden data, or claim a blind
evaluation.
