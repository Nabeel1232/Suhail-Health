# Suhail Health submission

**Category** Population Health · Challenge 05 · Closing the Screening-to-Care Loop  
**Maturity** Prototype

## Files for the portal

| Field | File |
|---|---|
| Prototype demo, up to three minutes | [Suhail Health final three-minute demo](reports/video-final/Suhail_Health_Final_Demo.mp4), 2:55.18 |
| Optional extended showcase | [Suhail Health five-minute showcase](reports/video-final/Suhail_Health_5_Minute_Showcase.mp4), 4:58 |
| Solution deck | [Suhail Health deck (PDF)](docs/Suhail_Health_Deck.pdf) |
| Source and technical documentation | This repository. Start with [SUBMISSION.md](SUBMISSION.md). |

The demo uses fictional patients and simulated providers. The five-minute edit shows earlier verified application footage. The portal will need this repository's URL, the team members and a contact address. If the demo field asks for a URL, use a video share link reviewers can open without signing in.

## Short description, up to 100 words

Suhail Health closes the follow-up gap after actionable colorectal screening results. It gives navigators, clinicians and receiving providers a shared record of the owner, deadline and next action. Patients read a secure update in Arabic or English, acknowledge it and answer two teach-back questions. Rejected referrals and missed appointments create owned recovery work. Trusted urgent flags go directly to qualified staff. An authorized clinician closes completed care with verified evidence. In a simulated cohort, follow-up completion rises from 56% to 69% under declared assumptions. We seek one provider network for a 12-week pilot.

## Full description, up to 300 words

A screening result only helps if someone acts on it. In a US study of people with a positive stool-based screening test, 56% completed follow-up colonoscopy within one year. The gap can open at any handoff, from result notification to an appointment that never gets rebooked.

Suhail Health gives each result an owner, a deadline and a visible path to care. A navigator can see overdue work, rejected referrals and unresolved cases in one queue. Patients read the original secure update in Arabic or English, confirm receipt and answer two short questions that check understanding. If an answer shows uncertainty, a navigator gets an assigned follow-up task. Receiving teams see a scoped referral packet and accept or reject it with a reason. Clinicians review source evidence before documenting closure. Trusted urgent flags go directly to staff with a backup route.

The working prototype uses a PostgreSQL ledger, versioned pathway rules, a durable worker and role-scoped workspaces. Six bounded AI functions can prepare drafts for staff review. The final software evaluation passed 1,500 deterministic checks, including 500 refused premature closures. The demonstration uses fictional patients, simulated notifications and a FHIR R4 test server.

In a simulated cohort using published US follow-up rates and a navigation trial, completion by day 360 rises from 56% to 69% under declared assumptions. That represents about 1,300 additional completions per 10,000 actionable results in the model. We seek a provider network for a 12-week pilot on one screening pathway. We would measure notification and care timings, referral and attendance completion, unresolved work, documented closure, and patient understanding.
