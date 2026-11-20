# Complete customer experience

The customer is a screening program or provider network. The users are patients, navigators, clinicians, specialists, receiving-service staff and operational administrators. Every actionable screening case needs an accountable episode owner even when tasks span organizations.

## Entry and trust

Provide a concise Suhail Health introduction, meaningful product benefits and sign-in. Use the logo and the phrase Guiding every result to care. Explain patient privacy and clinician oversight using the actual implemented behavior. Do not invent hospital customers, partner logos, certifications, testimonials or clinical validation.

The demonstration contains fictional patients and organizations. Make this clear at entry and in the demo shell. Generate scoped demo accounts and place credentials in an ignored local handoff file. A demo-only role chooser must not operate as a production authentication bypass. Keep patient access authenticated or use short-lived scoped demo links; never put private clinical details in an unauthenticated URL.

## Patient journey

1. Sign in or open the scoped demonstration link. See result context in plain language, the assigned care team, the next step and when to expect contact under the demonstration configuration.
2. Choose English or Arabic and an available contact preference. Explain what each channel actually supports. Keep confidential details inside the authenticated page; the default message outbox contains only a minimal notification.
3. Acknowledge receipt. Separately complete a simple understanding check. Record passed, needs help or unknown. A message delivery/read event cannot set understood.
4. Ask a question or request a callback. See the assigned team, request status and human reply. Ask a follow-up without losing the thread. Clinical questions reach a clinician task; the AI does not impersonate the clinician.
5. Report a barrier such as timing, transport, language or uncertainty. See the resulting assistance task and a practical next action. Do not imply that the system can create unavailable specialist capacity.
6. See accepted referral and appointment status. Where an actual scheduling adapter is unavailable, submit preferred times for staff confirmation; clearly label requested versus confirmed bookings.
7. Receive cancellation/no-show recovery guidance, updated responsibility and consultation outcomes. Urgent concerns use the configured staff escalation and approved guidance; no unrestricted emergency diagnosis chat.
8. See a documented assessment outcome and care plan approved by the appropriate role. If onward care remains open, show its team and next action. When completed, update the view from arranging your next step to the appropriate documented follow-up state.

The patient must always be able to find who is responsible and how to request help. Do not expose model names, raw prompts, tool traces or technical benchmark scores in this view.

## Navigator journey

The queue prioritizes unresolved work: new results, uncertain identity, missing staffing, failed notification, poor understanding, unanswered questions, rejected transfers, appointment problems and overdue actions. Filters and counts query the database and reconcile to case totals.

Open the case journey, validate source matching, assign tasks, use approved message templates, request clinician consultation and propose a receiving service. See consent/access scope and the minimum referral packet. A proposed owner transfer leaves the current owner accountable. Rejection and timeout return visible work without clearing the original responsibility.

Resolve access barriers and no-show tasks through recorded actions. Route clinical decisions to clinicians. Explain a deadline or exception with its configured source and reason. Ordinary task completion cannot clear quarantine, verify a clinical document or close required care without its authorized command.

## Clinician and specialist journey

Review the result, source evidence, relevant policy and uncertainties. Respond to a patient question as an authenticated clinician. Initiate an e-consult with a named question, recipient, service window and supporting packet. The specialist sees only permitted information, replies as a human author, and records the agreed action and owner. The requesting clinician can request clarification or implement the next task.

For urgent review, see the source flag and escalation history. Record acknowledgement separately from a clinical disposition. Acknowledgement alone does not resume affected work if the disposition is still required.

Review the closure evidence checklist. Approve the applicable milestone or a supported episode disposition. If treatment initiation or another declared endpoint is unfinished, completed-care closure stays blocked. An authorized exception retains residual care need and remains separate in outcome reports.

## Receiving service journey

Receive a limited referral packet; request more information, accept or reject with a reason. Acceptance is scope-specific: task assignment and episode accountability are different. Record available slots/booking, cancellation, attendance and completed assessment through authenticated service events. Return source evidence and the clinical response. Acceptance must not open unrelated patient charts or all source-provider records.

## Operations and evaluation

Operators see failed callbacks, dead letters, retries, staffing gaps, unresolved urgent acknowledgements and unavailable models/connectors. Each error has an accountable queue and recovery action. Show health checks and whether a connector is live, simulated or manual.

Impact views define denominators and distinguish notification, understanding, consultation, acceptance, attendance, required care and disposition. Decline, unreachable and transfer cases remain visible. Charts are derived from the selected time period and source records, with empty states for unmeasured outcomes.

Evaluation users see run provenance, model, data split, attempted/failed counts, budget status, measured metrics and downloadable reports. Unrun metrics display Not measured rather than zero or a fabricated success percentage. Optional expert review has its own status and report.

## Browser verification

Automate at least: uncomplicated completion; patient question and clinician reply; clinician-specialist consultation; rejection then acceptance; no-show recovery; urgent review with model unavailable; quarantine and authorized recovery; invalid-evidence closure rejection; ongoing-care endpoint block; amended-result reopening; informed decline; and permission denial. Verify shared state across two browser sessions, reloads and application restart. Check Arabic RTL and narrow/mobile widths, not only a desktop screenshot.
