# Shared implementation contract v1

API base `/api` in the browser proxies to FastAPI on local port 18000 (container port 8000) (API routes themselves have no prefix). All data is synthetic. Python API models are authoritative and OpenAPI generates the detailed schema. Changes to this contract are coordinated by the root implementation owner.

Authentication: `GET /auth/config` returns `{demo_mode:boolean}`. `POST /auth/login {email,password}` sets HTTP-only cookie. `POST /auth/demo {role}` sets scoped demo cookie, allowed only DEMO_MODE. Roles: `navigator`, `clinician`, `specialist`, `receiver_a`, `receiver_b`, `patient`, `admin`. `GET /auth/me` returns `{id,name,role,organization,patient_id}`. POST `/auth/logout` clears session. No frontend secrets. Every mutation carries `expected_version` (case row version), `idempotency_key` and optionally `correlation_id`. A response returns the updated case/detail or command object containing `case_id` and `version`; UI reloads detail after mutations. Errors: `{detail:string|object}` with 401/403/409/422.

`GET /cases` returns array of authorized case summaries. `GET /cases/{id}` returns detail. Common fields: `id`, `patient_id`, `patient_name`, `language` (`en`/`ar`), `source_organization`, `order_id`, `result_version`, `pathway`, `owner`, `backup_queue`, `phase`, `disposition`, `residual_need`, `version`, `quarantine_reason`, `urgent`, `next_action`, `due_at`, `delay_reasons`, `created_at`; detail arrays: `milestones`, `tasks`, `communications`, `consultations`, `handoffs`, `appointments`, `evidence`, `escalations`, `audit`. Patient detail is filtered; receivers receive ONLY explicit minimal packets, not source case detail. Summary filters can be applied on client over authorized cases. Task `{id,type,status,assignee,next_action,due_at,required,reason}`. Milestone `{type,status,required,evidence_ids}`. Evidence `{id,type,source,reference,verification,status,result_version,patient_id,order_id}`. Handoff `{id,scope,receiver,status,reason}`. Communication `{id,language,channel,body,delivery_status,acknowledged_at,understanding}`. Consultation `{id,type,question,recipient,status,reply,agreed_action,action_owner,due_at,human_author}`. Escalation `{id,trigger,recipient,backup,acknowledged_at,disposition}`. Appointment `{id,provider,status,events}`.

Commands (body always envelope plus fields):

- `POST /events/results`: source event `{event_id,source_organization,patient_id,patient_name,order_id,result_version,test_code,issued_at,identity_verified,trusted_urgent}`. Connector auth server-side; demo staff intake supported separately.
- `POST /cases/{id}/reconciliation`: `{identity_verified:true,pathway:'colorectal-fit',source_reference,reason}` clinician/navigator authorized.
- `POST /cases/{id}/tasks`: `{type,assignee,next_action,required?,reason?}`; updates use `task_id,status,reason`, cannot complete clinical gates.
- `POST /communications`: `{case_id,language,channel}` approved fixed template.
- `POST /communications/{id}/acknowledgement`: no extra data, patient only.
- `POST /communications/{id}/understanding`: `{outcome:'passed'|'needs_help'|'unknown'}` patient only.
- `POST /cases/{id}/preferences`: `{language,channel}` patient only.
- `POST /cases/{id}/barriers`: `{barrier,detail}` patient or navigator.
- `POST /consultations`: `{case_id,type:'patient_to_clinician'|'clinician_to_specialist',question,recipient}`.
- `POST /consultations/{id}/reply`: `{reply,agreed_action,action_owner}` clinician or assigned specialist; human authorship inferred from auth.
- `POST /handoffs`: `{case_id,receiver:'provider-a'|'provider-b',scope:'episode'|'task',reason}`.
- `GET /referrals`: array of authorized minimal referral packets for receiver; `/handoffs/{id}/accept|reject` with `{reason?}`.
- `POST /cases/{id}/appointments`: `{provider,scheduled_at}`; `POST /appointments/{id}/events`: `{status:'booked'|'cancelled'|'no_show'|'attended'|'no_slots',occurred_at?,source_event_id?}` receiving staff.
- `POST /cases/{id}/evidence`: `{type,reference,source?,patient_id,order_id,result_version}` pending upload; `/evidence/{id}/verification` `{verified:boolean,reason}` clinician only. Evidence types: `investigation`, `reviewed_outcome`, `patient_updated`, `treatment_initiated`, `surveillance_plan`; reviewed_outcome may specify `requires_onward:true`.
- `POST /escalations/{id}/acknowledge`: staff; `/disposition` `{decision,reason}` clinician.
- `GET /cases/{id}/closure-check`: `{allowed:boolean,missing:string[],endpoint,policy_version}` deterministic; `POST /cases/{id}/dispositions` `{category:'completed_required_care'|'clinically_resolved'|'informed_decline'|'unable_to_contact'|'accepted_transfer_open'|'other_exception',reason,residual_need}` clinician only.
- `GET /operations`: `{outbox,overdue,pending_escalations,connectors}`; `POST /operations/outbox/{id}/retry`; `GET /metrics`: actual denominator/counts. `POST /demo/clock {hours}` and `/demo/reset` admin/demo only. `GET /reports`: run manifest summaries. `GET /reports/{run_id}/{filename}` restricted admin safe report download.
- Agent routes integrated by root: `POST /agents/{function}/propose` requires staff role + envelope, case_id. Never disposition authority.

Frontend routes: `/` intro/signin, `/worklist`, `/cases/[id]`, `/clinical`, `/receiving`, `/patient`, `/operations`, `/evaluation`. Receiver UI never calls source case detail.
