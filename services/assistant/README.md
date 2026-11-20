# Workspace assistant

This is a read-only query interface alongside the six existing care functions.
It does not add clinical authority or an application command tool.

## API and client contract

- `GET /assistant/context`: current role, authorized counts, count definitions,
  suggested questions, and optional model configuration status.
- `GET /assistant/conversations`: the current account's available conversations.
- `POST /assistant/conversations`: create a conversation. Titles are generated
  from bounded intent labels rather than copied patient text.
- `GET /assistant/conversations/{id}`: persisted user and assistant turns.
- `POST /assistant/conversations/{id}/messages`: ask a question with optional
  `context_case_id`; returns a summary, metrics, cards, source links and follow-ups.
- `GET /assistant/knowledge/{id}`: permitted, current, versioned guidance.

The message body is `{ "message": "How many requests do I have?",
"context_case_id": "SC-001" }`; `context_case_id` is optional and must already
be visible to the actor. Messages are trimmed and limited to 2,000 characters;
unknown body fields are rejected. The reply contains `conversation_id`, the
persisted `user_message`, the assistant `message`, and its structured `answer`.
An answer includes `summary`, `mode`, `sources`, `cards`, `suggestions`,
`refreshed_at`, `scope_label`, `read_only`, and interpretation status under
`intelligence`. Applicable answers also include exact `metrics`,
`recorded_total`, and a note when the visible card/source preview is truncated.
Counts cover all permitted matching records; cards and sources are bounded to
twelve. Null means the role is not granted that measurement, rather than zero.

Conversation creation returns `{ "conversation": {...}, "messages": [] }`.
History returns the same conversation object and ordered messages. Lists return
`{ "conversations": [...] }`; at most 100 recent entries are examined. An
account can store 200 conversations, each with 120 persisted messages. A denied
or revoked conversation returns the same 404 shape as an unavailable one.

Every endpoint requires the existing signed-in actor. Receiving services get
only granted referral packets and their service appointments. Patients get
their identity-verified linked cases through the existing patient serializer.
Specialists get assigned consultations. Staff remain scoped to their source
organization. Connector credentials cannot use this assistant.

## Grounding and history

The server reads current authorized records for every question. Counts, statuses,
ownership, next steps, source links and cards are constructed by allowlisted
query/rendering functions. User or model text never becomes SQL, a file path,
an arbitrary URL, a tool call, or a clinical state change.

Request counts have role-specific definitions returned by `/assistant/context`:
receiving-service pending referral decisions; clinician/specialist unanswered
assigned consultations; navigator assigned follow-up tasks; patient unanswered
questions and practical-help work; administrator unfinished delivery records.
Unavailable provider task/escalation measurements remain null, rather than zero.
Episode-count questions use distinct permitted episode IDs, independently of
pending requests. Explicit patient-count questions deduplicate permitted patient
identities and also show the episode denominator; several episodes may belong
to one patient. Existing pending-referral prompts count current service decisions
and do not require model interpretation. A workspace count clears a stale case
page context, while an explicitly named case still focuses that permitted case.

Conversation ownership includes user, role, organization and patient identity.
History also depends on the referenced case roster, individual referral grants,
and assigned specialist consultations. Losing any dependency hides the entire
affected conversation, including its title, user turns, answers and citations.
After a model wait, real cookie authentication and current record permissions
are checked again before a reply is stored. A global workload question clears
old patient context. Case pronouns and ownership follow-ups can reuse the last
focused case: after an explicit SC-001 question, "Who is responsible?" refers
to SC-001. An explicit different name/case still takes precedence over that focus.

Persistence uses the existing SQLAlchemy engine and additive startup schema
initialization. `assistant_conversations` holds the owner identity, bounded
title, case/grant dependencies and timestamps; `assistant_messages` holds the
ordered user/reply turns, structured answer and optional focused case ID.
These tables are separate from cases, evidence and care dispositions. The
existing database backup/access controls must also cover conversation history.
No client-provided title is copied into a patient-bearing conversation label.

This history rule is intentionally conservative: the initial case roster and
packet/consultation grants are dependencies too. Losing access to any dependency
hides that entire conversation even if another grant still exposes some of the
same episodes. New conversations use the current permitted roster. Stored turns
are historical snapshots; a new question reads records again. Chat writes its
own conversation/message rows and a read audit, never care-case state.

Source timestamps use actual read time. Due/overdue calculations use the same
configured demonstration clock as the rest of the application. Guidance cards
show source authority, version and review status; local demonstration material
is not represented as independently clinically reviewed. Patient care-plan text
is read only from the existing authorized, human-approved patient view.

## Optional model interpretation

`CHAT_LLM_ENABLED=false` is the default. The record-grounded assistant remains
functional without a model. When enabled, familiar exact queries still use the
direct read path. Ambiguous wording can use one schema-constrained intent
classification request; the model returns only an allowlisted intent enum.
It sees the typed question and bounded interpretation instructions, not a dump
of case records, history, private source bodies, or credentials. Deployment must
permit processing the typed input before enabling remote interpretation.

The persistent application ledger is `runtime/context-chat/model-ledger`.
Its limits default to `CHAT_MAX_CALLS=20`, `CHAT_MAX_TOKENS=40000`, and
`CHAT_MAX_OUTPUT_TOKENS=1024`, with no automatic retries. Lower owner settings
and shared gateway limits are respected; zero call/token caps prevent dispatch.
Do not delete or reset the ledger to bypass its cap. This application runtime
ledger is separate from immutable benchmark execution records.

`model_assisted_records` means an actual model interpretation completed; all
answer facts still come from the database. `authorized_records` means direct
grounding, including a clearly indicated model-unavailable fallback. Configuration
status is not a claim of provider availability or measured accuracy.

## Deep links and clinical boundaries

The server constructs links after authorization. Staff links select a real case
tab and field anchor; providers open their permitted referral card and patients
open their existing patient-page fields. Specialist urgent-review links target
the visible journey milestones, because their case view does not include the
clinician closure panel. Knowledge links resolve only versioned permitted
documents or their actual source. The client does not infer access from a URL.

The assistant can explain recorded facts, accountable teams and workflow. It
does not diagnose, choose treatment, prescribe, approve evidence, close cases,
accept referrals, book visits, send messages, or retry deliveries. Clinical
questions link to human consultation; action requests link to the existing
authorized workflow. Urgent clinical review, staff acknowledgement, clinical
disposition and completed care remain distinct application facts.

## Verification

`tests/test_context_chat.py` uses isolated persisted SQLite stores and explicitly
mocked model boundaries. It checks role scopes, current counts, restricted links,
cross-account conversation probing, scope revocation, post-inference account
changes, injection handling, human clinical routing, persistence, and unchanged
clinical versions. Functional live provider checks require a separately bounded
runtime instruction; these tests make no external inference requests.

The current release evidence is in `reports/ui-chat-v4/verification.json` and
`index.html`. It reports the 123-check baseline, later focused specialist-link
and count/ownership-intent checks, media sync checks, the authoritative browser
regression, the earlier focused chat-browser checkpoint and the separately authorized runtime model
check with their own denominators. Overlapping tests are not added together.
None is presented as clinical validation or as a new agent-accuracy benchmark.
Original evaluation/provider artifacts and the nearly exhausted benchmark
allowance are not reset by this feature.

`reports/ui-chat-v4/native-runtime-smoke.json` separately records authenticated
context reads for all seven roles on the actual PostgreSQL-backed application,
service health and preservation of the original completed SC-001 state. It made
zero model requests. The complete browser/write journeys run against the private
SQLite verification stack; this native read smoke does not claim a repeated
PostgreSQL write journey or optional PostgreSQL concurrency test run.
