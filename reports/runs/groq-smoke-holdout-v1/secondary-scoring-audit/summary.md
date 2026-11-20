# Suhail Health secondary scoring audit

6 existing live responses audited; 5 correct; 1 incorrect; 0 new API calls. Original primary scoring failures and denominators remain unchanged.

Original v1 scorer queried English FTS terms for Arabic source context, raised PolicyReviewRequired and lost the candidate ID in its exception path. Existing real responses are audited with their exact permitted policy references. This is secondary post-hoc scoring, not new inference or silent replacement of the primary failed-case denominator.

| Function | Original case | Correct | Original response ID | Scorer |
|---|---|---|---|---|
| intake | intake-holdout-002 | False | c71086d0-4011-4470-8f2d-b59be6c4a4d2 | secondary-source-language-audit-v2 |
| pathway_router | pathway_router-holdout-002 | True | ca887e36-bd7c-4676-aa22-ad4b95f99401 | secondary-source-language-audit-v2 |
| safety_escalation | safety_escalation-holdout-002 | True | 48ecb560-29d1-4ac2-8294-c836949936e8 | secondary-source-language-audit-v2 |
| patient_navigator | patient_navigator-holdout-002 | True | af773186-9d9a-4ea2-98f4-f0fee2663589 | secondary-source-language-audit-v2 |
| coordination | coordination-holdout-002 | True | fc5819f0-df8e-41d4-9cbf-d5b7a5ccc803 | secondary-source-language-audit-v2 |
| closure_evidence | closure_evidence-holdout-002 | True | 6523d0c4-ec7a-496d-8391-ac26fd634079 | secondary-source-language-audit-v2 |
