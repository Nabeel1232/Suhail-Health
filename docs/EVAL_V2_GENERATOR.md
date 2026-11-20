# Synthetic generator v2

`evals/synthetic_v2.py` defines `suhail-synthetic-v2.0` for future evaluations. It does not alter any v1 executed record, candidate response, model setting, report denominator or live-call budget. No live model request was made to create or verify this generator.

## What is separated

The development set contains actual FHIR result bundles; validation contains controlled CSV transfers; holdout contains independently worded English/Arabic narrative notes. The candidate-visible `source_document` holds the real generated document, rather than a renamed template label. Intake gold facts can be extracted from each document's actual fields.

Operational combinations also differ structurally: development has one observed support/preference condition, validation has two, and holdout has three. Conditions concern transport support, contact windows, nonclinical contact-spelling corrections, language support, receiving-service capacity confirmation and caregiver sharing authorization. Each is represented as actual candidate-visible structured context. Combination sets remain disjoint after removing IDs, split labels, prose and provenance metadata. No capacity, clinical correction or sharing permission is invented by these context records.

Patient IDs, case/order/evidence references and deterministic seeds differ from v1 and across all v2 splits/functions. Question wording changes in the actual request and patient consultation, not just the family label. Evidence references and gold IDs are remapped consistently. The generator does not supply invented source spans or character offsets.

## Limits

- Core care decision rules and the six base v1 variants are shared across splits. This is source-template and operational-combination separation, not a holdout of new clinical rules or wholly unseen care scenarios.
- Document formats and feature cardinalities are deliberately confounded with split. Results could reflect format or context-complexity shifts; they do not establish external or clinical generalization.
- Arabic text and clinical content have not received independent expert review. All records and operational observations are project-generated synthetic data.
- Reusing the independent v1 scenario truth preserves known care rules. Parsing tests independently check source facts; semantic scorer checks distinguish correct and incorrect proposals. Neither is live model quality evidence.
- Existing v1 executed runs remain known-family regression evidence. They must not be relabelled as v2 or as unseen-family validation. A future v2 run needs its own frozen candidate, manifest, selected IDs and measured response ledger.

## Interface and verification

Use `function_cases(function, count=6, split='holdout')`; supported functions are the same six bounded functions as v1. Case/truth shapes remain compatible with `evals.synthetic.score_proposal`, which is also re-exported by v2. `manifest(examples)` records generation seeds, actual family fingerprints and limitations.

```bash
.venv/bin/python -m pytest tests/test_synthetic_v2.py -q \
  --junitxml=runtime/synthetic-v2-tests.xml
```

Tests inspect actual source structure and operational feature combinations with identifying/split labels removed; independently parse intake source facts; check deterministic IDs/evidence links; verify v1 remains unchanged; and require wrong task actions to fail the same independent scorer. This command makes zero model calls. Its execution result is recorded separately from all live Groq reports.
