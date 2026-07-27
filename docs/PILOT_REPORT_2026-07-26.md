# Mayig Structural Pilot — 2026-07-26

## Scope

This is an engineering and structural-prediction smoke test, **not a decipherment result**.

- Upstream: `mayig/indus-valley-script-corpus`
- Revision: `ad2f1e218a34b8c33c57de0d6cb8d99272765bbb`
- Imported artifacts: 179
- Lines: 186
- Sign tokens: 1,003
- Site: Mohenjo-daro only
- Object class: seal records only
- Images, reliable periods, stratigraphy, and duplicate-family metadata: absent
- Corpus SHA-256:
  `c9a73664ad15ee60c122f1152fc06b04f76fb27dfb7561c9f80fbb6cb06f526d`

The live upstream checkout was imported from a temporary directory. No upstream corpus files or
images were added to this repository. All 179 converted records passed the domain validator and
Draft 2020-12 artifact schema. Two upstream damage-feature anomalies remain preserved in
namespaced extensions; neither was silently clipped or converted into a sign label.

## Split

- Method: deterministic connected components
- Grouping evidence: duplicate family, catalog alias, image hash, exact normalized line sequence
- Seed: `20260726`
- Train: 142 artifacts
- Public development holdout: 37 artifacts
- Public development sequences: 38
- Split ID: `split:330e344b36c5b21dbfb0b0ba`
- Cross-partition leakage findings: 0

The historical implementation and split ID used the label `test`. Its complete
membership was disclosed, so it was a development holdout—not a blind,
custodian-held, or final evaluation set.

## Transparent baseline

An add-one bigram model was fit on reading-order sign IDs. Unreadable positions break context.
Twenty held-out tokens whose signs did not occur in training were excluded from masked-sign
ranking, but remained represented in held-out sequence scoring through the model's unknown-sign
handling.

One hundred independently shuffled controls used seeds `20260726..20260825` for train and a
disjoint deterministic seed offset for test.

| Metric | Observed | Null mean | Null 2.5–97.5 percentile |
|---|---:|---:|---:|
| Perplexity | 96.250 | 138.344 | 129.140–145.803 |
| Top-1 masked-sign accuracy | 34.804% | 5.936% | 2.941–8.824% |
| Mean reciprocal rank | 0.422 | 0.122 | 0.093–0.154 |

The one-sided add-one empirical p-value is `1/101 = 0.0099` for lower perplexity, higher masked
accuracy, and higher reciprocal rank. This p-value applies only to this preselected bigram and this
single null family; it is not corrected for model selection and is not evidence of language.

Each control preserves partition membership, baseline sequence lengths, and partition-level unigram
counts while destroying within-sequence order.

## What this supports

Within this small transcription, local sign order contains predictive regularity beyond this
particular shuffled control. The result also confirms that the importer, schema, connected split,
audit, scoring, and JSON output work end to end.

## What this does not support

It does not identify:

- whether every sequence is linguistic;
- the writing-system type;
- word boundaries;
- phonetic values;
- a Dravidian, Indo-Aryan, Munda, or other language;
- any translation.

The corpus is narrow, lacks images and archaeological covariates, and does not supply independently
verified physical duplicate families. A bigram can exploit formulaic administrative or emblematic
order without language. The 100 controls test randomized sign order only; they do not represent the
full range of accounting, emblematic, ownership, registry, or mixed systems. Results must be
repeated with richer matched non-linguistic controls, alternative sign inventories and directions,
rights-cleared image-linked data, and leave-one-site/period/object-type holdouts before making
broader claims.
