# Secondary Arabic scoring audit

Original v1 scorer queried English FTS terms for Arabic source context, raised PolicyReviewRequired and lost the candidate ID in its exception path. Existing real responses are audited with their exact permitted policy references. This is secondary post-hoc scoring, not new inference or silent replacement of the primary failed-case denominator.

6 existing responses audited; 5 passed and 1 incorrect. New API calls: 0. Original primary failure counts remain unchanged.
