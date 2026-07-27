# Release Checklist

## Evidence and rights

- [ ] Source registry reviewed against current official terms.
- [ ] No restricted corpus, scan, image, or speculative translation entered release artifacts.
- [ ] Every redistributed image has item-level rights and provenance.
- [ ] Data corrections and known anomalies are documented.

## Reproducibility

- [ ] Exact corpus, schema, source, quarantine, split, evaluator, project, and
  dependency-lock bytes are bound in a verified benchmark definition.
- [ ] Public train/development membership is frozen and explicitly marked
  `blind=false`, `final=false`, and `benchmark_locked=false`.
- [ ] Family, catalog, image, and exact-sequence leakage audit is clean.
- [ ] Seeds, environment, code revision, exclusions, and negative controls are archived.
- [ ] The digest supplied to `S` equals `definition_sha256` from a separately
  verified benchmark definition `B`.
- [ ] Any candidate submission has a complete-tree `S` build→verify result;
  its digest is retained separately and rechecked with
  `--expected-commitment-sha256`.
- [ ] The entrypoint, source, configuration, model-weight, dependency,
  static-argument, and every fallback `runtime_input` classification were
  reviewed and explained.
- [ ] Before publishing an `S` manifest, its paths, roles, sizes, hashes,
  arguments, and target passed secret, hidden-metadata, linkability, and
  rights-disclosure review.
- [ ] Local assurance remains non-blind, non-final, unanchored,
  non-confidential, and without custody/time/access/runtime/result attestation.
- [ ] A final/blind claim additionally has external evidence that a specific
  `B` and `S` pair was authenticated, independently retained, and
  time-evidenced before the candidate ran on hidden inputs and before the
  hypothesis/submission team received hidden material or hidden-derived
  feedback, plus externally controlled private-test custody, an isolated run
  definition, and access/run/result receipts. A local `S`, signature alone,
  timestamp alone, or public development output cannot satisfy this item.

## Engineering

- [ ] `just check`
- [ ] `uv run python -m unittest discover -s tests -v`
- [ ] `uv build`
- [ ] Wheel installed and exercised outside the source tree.
- [ ] Wheel and sdist contents inspected for unexpected data.
- [ ] Gitleaks, Semgrep, and Trivy scans clean or findings documented.
- [ ] Changelog, version, citation metadata, and release date agree.

## Claim review

- [ ] Structural results are not described as translation.
- [ ] Every phonetic or semantic claim has a frozen hypothesis record.
- [ ] Results include unrelated-language and non-linguistic controls.
- [ ] Failures, exceptions, uncertainty, and out-of-domain performance are reported.
- [ ] Independent evaluator or replication status is stated.
