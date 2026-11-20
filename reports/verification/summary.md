# Suhail Health submission verification

The 20 November 2026 Product freeze passed its production build, service restart, and browser test sequence. The reseeded demo contained 16 fictional cases, and all seven role switches opened their workspaces.

| Evidence | Passed / selected | Failed | Skipped |
|---|---:|---:|---:|
| Native backend, agents and evaluation tests | 139 / 141 | 0 | 2 |
| Native Chromium browser tests | 16 / 16 | 0 | 0 |
| Deterministic replay and safety checks | 1500 / 1500 | 0 | 0 |
| Premature closure attempts refused (included above) | 500 / 500 | 0 | 0 |
| Isolated fresh-install acceptance tests | 69 / 69 | 0 | 0 |

The offline record passed its integrity check. [Frozen run](../runs/20261120T135507Z-offline/summary.html) · [Record integrity](../runs/20261120T135507Z-offline/integrity.json)

The isolated setup installed the locked Python and web dependencies, seeded SQLite, passed the backend and agent acceptance tests, and built the production web app. [Fresh-install proof](final-fresh-install.json)

## Evidence boundaries

- The offline checks executed synthetic software workflows. The held-out live-model evaluation has its own sample, status and usage records. [Live-model holdout](../runs/groq-smoke-holdout-v1/summary.html)
- The prototype uses fictional records and simulated delivery, provider and FHIR endpoints. Independent clinical and Arabic-language review remains a pilot requirement.
- Projected follow-up completion estimates come from the paired simulation. The proposed pilot would measure follow-up, patient understanding and care delivery in practice. [Impact model](../../docs/IMPACT_MODEL.md)
- The existing summary.html and summary.json record earlier release checks.
