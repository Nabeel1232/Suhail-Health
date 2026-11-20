# Final three-minute submission demo

The final edit runs 2:55.18 and uses Sarah's ElevenLabs v4 narration with captions. It opens with the follow-up problem, follows fictional patient Mariam through the worklist and patient view, and closes with software evidence and the pilot ask. The two consultation and handoff chapters reuse earlier verified footage. The other four UI chapters show the frozen release.

[Final demo](../reports/video-final/Suhail_Health_Final_Demo.mp4) · [Transcript](../reports/video-final/Suhail_Health_Final_Demo_Transcript.txt) · [Verification](../reports/video-final/verification.json)

## Narration and chapter timings

00:00:00  01  Why results get lost
A screening test only helps if someone acts on the result. In a study of more than thirty-two thousand adults with a positive stool test, only fifty-six percent completed a follow-up colonoscopy within a year. Every transfer creates a chance for responsibility to become unclear. Suhail Health gives each result a visible route to care.

00:00:23  02  Every result has an owner
Meet Mariam, a fictional patient in this demo. Her result arrives in a worklist with an owner, a next action, and a deadline. Navigators can find overdue work, rejected transfers, and cases that need assignment. Open a completed case to see dates, service targets, and the evidence behind each step, from the result through closure.

00:00:47  03  Clear for the patient
On her phone, Mariam can see where she is in the journey. Her result message arrives in Arabic. It explains what happens next and who will help. She can confirm receipt and answer two questions to check understanding. If she needs help, her navigator gets a task to call her. Her care team is easy to reach.

00:01:08  04  Connect human expertise
Clinicians bring assigned episodes and patient questions into one workspace. Human replies record an agreed action and owner. Specialists see their assigned consultations. Optional AI assistance prepares source-linked drafts for review. The care team makes the clinical decisions.

00:01:28  05  Make the handoff accountable
Receiving services see a minimum referral packet. They explicitly accept a referral or record a rejection reason. Appointment controls keep booking, attendance, and no-shows distinct. A proposed transfer keeps the sending owner accountable until the receiver accepts the intended responsibility.

00:01:49  06  Safe escalation, evidenced closure
An urgent result goes straight to a clinician on a sixty-minute clock, with an on-call backup and no model in that path. To close required care, an authorized clinician needs verified evidence of the investigation, the reviewed outcome, and the patient update. The checklist shows exactly what is missing.

00:02:10  07  Measure what happens next
Operations can see time to notification, understanding, and completed care, and where work is stalled. In a simulated cohort calibrated to published studies, estimated follow-up completion rises from fifty-six to sixty-nine percent within a year. A pilot would measure the effect in practice.

00:02:31  08  Human control, ready to pilot
Six bounded agents prepare drafts and check records. The care team remains responsible for decisions. Fifteen hundred automated safety checks passed, including five hundred correctly refused premature closures. We are seeking a partner for a twelve-week pilot on one screening pathway. Suhail Health. Guiding every result to care.

## Earlier walkthrough and recording instructions

The [five-minute showcase](../reports/video-final/Suhail_Health_5_Minute_Showcase.mp4) is an edit of earlier verified application footage. The instructions below describe the earlier walkthrough's recording setup.

**Audience:** a screening-program or provider-network team. **Target length:** 4 minutes 50 seconds. **Scope:** one already-actionable FIT screening result, coordinated through evidenced follow-up and a documented care plan.

All patients, staff accounts, organizations, service windows and provider events in this demonstration are synthetic. Provider A, Provider B and the FHIR R4 server are separate running simulators. No real patient is contacted. Clinical and Arabic-language expert review is **NOT_RUN**.

## Prepare before recording

1. From the project root, run `make status` and open <http://127.0.0.1:3000>. The API is <http://127.0.0.1:18000/docs>.
2. If a clean demonstration is needed, run `.venv/bin/python scripts/reset_demo.py`. It requests **only `demo-v1`** through the protected reset command. It preserves unrelated integration, browser, replay and other datasets. Do not delete database volumes or clear the whole database to reset the demo. Existing unrelated datasets also mean their clock configuration is preserved.
3. Use separate browser profiles/contexts for the patient, navigator, clinician, specialist and two receiving teams. At `/`, select the clearly labelled **synthetic demo** role. Normal deployment disables this chooser. Password-based demo credentials are held privately in `.runtime/demo-credentials.json`; do not display that file while recording.
4. Keep `/cases/SC-001`, `/patient`, `/clinical`, `/receiving`, `/operations` and `/evaluation` ready in the corresponding authenticated profiles. Prepare the short source documents below in a local editor. Do not pre-complete the actions presented as live.
5. For a compact recording, use cuts between roles or show an identified clip from the actual browser run. Label a recorded clip as recorded. The application still performs each displayed action against its backend; do not describe a screenshot as a new execution.

## Presentation and actions

| Time | Screen and action | Suggested narration |
|---|---|---|
| 0:00–0:25 | Public entry, then navigator `/worklist` → `SC-001`. Show result source/version, accountable owner, next action and due condition. | “Suhail Health guides an actionable screening result through the follow-up process. This is a synthetic demonstration. The care team retains clinical authority, and every open case has an accountable team and a next action.” |
| 0:25–1:00 | Patient `/patient`: acknowledge the delivered update, submit **Needs help** separately, and ask “Can my clinician explain the next assessment?” Briefly switch Arabic/English and show RTL. | “Receiving a message does not establish understanding. A request for help creates assigned work. Patients can ask a clinical question, see who will respond, and use their preferred language.” |
| 1:00–1:35 | Clinician opens `SC-001` → **Consultations**. Send a human reply with agreed next action and owner. Assign a clinician-to-specialist consultation; switch to the specialist and reply with an agreed action and owner. Reload the requesting clinician and patient pages. Patient submits a passed understanding check after the explanation. | “These are authenticated human replies. Both consultations record an agreed action, an accountable owner and a service window. An AI draft cannot impersonate either clinician.” |
| 1:35–2:15 | Navigator → **Coordination** → propose an **episode** referral to Provider A. Receiver A `/receiving` rejects with a capacity reason. Show that the sender remains accountable. Propose Provider B; receiver B explicitly accepts the episode. | “Sending a referral does not transfer responsibility. Rejection leaves the original owner in place. Acceptance changes only the intended handoff scope. The receiving team sees a minimum referral packet, rather than unrestricted source records.” |
| 2:15–2:45 | Receiver B records a confirmed appointment, then a no-show. Show the patient's recovery message and owned recovery work. Record rebooking and attendance as separate events. If time permits, show **unavailable capacity** before booking on a separate accepted demo referral. | “A requested appointment, a confirmed booking and attendance are separate facts. A missed visit or unavailable slot creates a recorded delay and recovery action. The system does not invent specialist capacity.” |
| 2:45–3:40 | Clinician shows the blocked closure checklist. Receiver B returns an investigation source document; clinician verifies source and matching. Clinician links and separately verifies `reviewed_outcome` and `patient_updated` source documents. | “Booking and attendance are not proof that the required assessment or care endpoint happened. Uploaded evidence remains pending until an authorized reviewer checks its source, patient, order and current result version.” |
| 3:40–4:10 | Navigator records completion of the actual agreed human coordination and referral-recovery work. Clinician reloads the evidence checklist and records **Completed required care** with a rationale. Patient reloads to see completed care and the retained approved plan text. | “Closure is a separate clinical command. It recomputes the evidence and every required task. The patient now sees the documented plan, rather than a message saying an appointment is still being arranged.” |
| 4:10–4:30 | Open seeded `SC-003`: show trusted urgent review, staff acknowledgement and separate clinician disposition. Open `SC-007`: show accepted onward referral and the unfinished treatment-initiation endpoint. | “Trusted urgent signals reach staff without waiting for a model. Acknowledging an alert does not dispose of it. An accepted onward referral also does not count as completed treatment.” |
| 4:30–4:50 | Operations `/operations`, then administrator `/evaluation`. Show current denominators, residual need and the actual run status/downloads. | “These measurements come from executed records. The 1,000 trajectories and 500 invalid-closure attempts are deterministic software tests. Live Groq responses and adapted HealthBench rubric estimates are reported separately, including failures, missing measurements and budget limits.” |

The live model demonstration is optional. Existing fixed templates and staffed work remain operational when Groq is unavailable. A template or mocked response must never be described as successful live AI inference. Do not launch another benchmark while recording merely to fill an empty metric.

## Short synthetic source documents

Use the **actual case's** patient ID, order ID and result version in each evidence form. References must identify distinct retained documents, for example `synthetic://presentation/<run-label>/investigation`. A URI alone cannot be verified as evidence.

- **Investigation:** “Synthetic source record: the planned follow-up assessment was completed for this fictional patient and order. The assessment report is returned for clinician review. This is demonstration evidence.”
- **Reviewed outcome:** “Your clinician has reviewed your completed assessment. Follow the documented plan with your responsible care team, and contact the team if you need help arranging the next visit. This is an approved synthetic demonstration plan.”
- **Patient updated:** Record the actual approved wording communicated to the synthetic patient. Keep the patient's next action explicit. Do not substitute an internal source-check attestation for plan text.
- **Verification reason:** “Reviewed retained source, exact patient/order match and current result version.” This is a staff attestation, not the patient-facing care plan.

Only complete human coordination tasks after demonstrating the stated work. Evidence, urgency, identity, policy and clinical endpoint tasks use their dedicated commands. If onward care applies, leave treatment initiation unresolved until verified endpoint evidence or an accepted surveillance plan with owner and valid recall date is recorded.

## Proof and recording references

| Evidence | Actual artifact |
|---|---|
| Full role-based browser care journey | `runtime/browser-fullcare-journey.json`; `runtime/screenshots/fullcare-receiving-b.png`; `runtime/screenshots/fullcare-closed-clinical.png`; `runtime/screenshots/fullcare-closed-patient-mobile.png` |
| Patient Arabic/mobile and queue screenshots | `runtime/screenshots/patient-arabic-mobile.png`; `runtime/screenshots/worklist-desktop.png` |
| Independent provider HTTP callbacks and returned evidence | `runtime/provider-journey-proof.json`; `runtime/integration-results.xml` |
| Actual acceptance/security results | `runtime/test-results.xml` — the final release run passed 98 checks; `runtime/browser-results.xml` passed 10 browser journeys. Earlier focused runs remain preserved separately. |
| Persistent graph pause/restart | `runtime/graph-restart-proof.json` |
| Reproducible reports | `reports/runs/software-delivery-final/summary.html`; `reports/runs/groq-smoke-holdout-v1/summary.html`; exact manifests and ledgers remain alongside each report. |

The final full browser sequence passed 10/10 after the patient-plan wording and retained-source review changes. Its11 persisted care snapshots and three actual pre-verification source reads are recorded in `runtime/browser-fullcare-journey.json`. Final captures are indexed in `reports/screenshots/INDEX.md`. The later full UI video is linked above. No external usability study was performed.

## Pilot discussion, if asked

“A suitable first pilot would involve one screening program, a limited synthetic-to-supervised integration scope and one pathway. We would first agree clinical ownership, source verification, sharing permissions and endpoint rules. We would then measure consultation time, accepted referrals, staff effort, patient understanding and unresolved care against agreed denominators.”

This is a proposed pilot, with no named partner, endorsement or committed deployment. Buyer willingness to pay, integration effort and recurring facility/episode pricing are business hypotheses to test. External expert review remains **NOT_RUN**; simulated workflow results do not establish clinical outcome improvement.
