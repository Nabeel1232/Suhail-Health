'use client';

import {useState} from 'react';
import {api, envelope, human, rows, type CareCase, type Row} from '@/lib/api';
import {ActionForm, Badge, Disclosure, Field} from './ui';
import {Icon} from './icon';

const purposes = [
  {value: 'intake', label: 'Review extracted source facts'},
  {value: 'pathway_router', label: 'Check supported pathway mapping'},
  {value: 'safety_escalation', label: 'Prepare a staff review handoff'},
  {value: 'patient_navigator', label: 'Draft a plain-language next step'},
  {value: 'coordination', label: 'Prepare coordination follow-up'},
  {value: 'closure_evidence', label: 'Find evidence for closure review'},
];

export function AssistantDraft({c, role}: {c: CareCase; role: string}) {
  const [result, setResult] = useState<Row | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const proposal = result?.proposal;
  const stale = !!proposal && proposal.case_version !== c.version;
  const canReview = ['clinician', 'specialist'].includes(role) && result?.review?.thread_id && !reviewed;

  return <div className="ws-assistant">
    <Disclosure title="Prepare an AI-assisted draft">
      <div className="ws-assistant-intro">
        <span className="ws-assistant-symbol"><Icon name="sparkles" size={23}/></span>
        <div><p className="ws-assistant-kicker">A SECOND PAIR OF EYES</p><h3>Thoughtful assistance. Your clinical judgement.</h3>
          <p>Optional assistance uses the authorized synthetic case and versioned sources. A draft is held for human review; required application commands govern every clinical action.</p>
        </div>
      </div>
      <div className="ws-assistant-boundaries"><span><Icon name="file-check" size={14}/>Source-linked</span><span><Icon name="lock" size={14}/>Case-scoped</span><span><Icon name="user" size={14}/>Human-reviewed</span></div>
      <ActionForm label="Prepare source-linked draft" className="ws-assistant-request" onSubmit={async data => {
        setReviewed(false);
        setResult(await api(`/agents/${data.function}/propose`, {...envelope(c.version), case_id: c.id}));
      }}>
        <Field name="function" label="What would help?" defaultValue="patient_navigator" options={purposes}/>
      </ActionForm>

      {result && <div className="assistant-result ws-assistant-result" aria-live="polite">
        {result.mode === 'live_groq' && proposal ? <>
          <div className="ws-assistant-result-heading"><span className="ws-assistant-symbol"><Icon name="bot" size={23}/></span><div><small>PREPARED FOR YOUR REVIEW</small><h3>AI-prepared proposal</h3></div><Badge tone="warning">Human review required</Badge></div>
          <div className="ws-proposed-action"><small>PROPOSED NEXT ACTION</small><strong>{human(proposal.recommended_action)}</strong></div>
          {proposal.patient_message && <div className="ws-draft-message"><small><Icon name="message-square" size={14}/>PROPOSED PATIENT WORDING</small><blockquote>{proposal.patient_message}</blockquote></div>}
          {proposal.review_reason && <div className="ws-draft-reason"><Icon name="info" size={16}/><p>{proposal.review_reason}</p></div>}
          {rows(proposal.missing_fields).length > 0 && <div className="notice warning"><strong>Missing information</strong><p>{rows(proposal.missing_fields).map(human).join(', ')}</p></div>}
          <div className="ws-draft-sources"><h4><Icon name="layers" size={15}/>Source references</h4>
            {rows(proposal.source_references).length ? <ul>{rows(proposal.source_references).map((source, i) => <li key={String(source) + i}><Icon name="file-text" size={13}/><code>{String(source)}</code></li>)}</ul> : <p>No source references were returned.</p>}
          </div>
          <p className="ws-draft-version"><Icon name="git-branch" size={14}/>Case version {proposal.case_version} · {human(result.review?.status || 'awaiting_human')}. No care milestone or disposition has changed.</p>
          {stale && <p className="notice warning">The case has changed since this draft was prepared. Prepare a new draft against the current case version before recording review.</p>}
          {canReview && <div className="ws-human-review"><h4><Icon name="stethoscope" size={17}/>Your review, on the record</h4>
            <ActionForm label="Record human review" disabled={stale} onSubmit={async data => {
              await api(`/agent-reviews/${result.review.thread_id}/resume`, {...envelope(c.version), case_id: c.id, ...data});
              setReviewed(true);
            }}>
              <Field name="decision" label="Your review decision" defaultValue="reviewed" options={[
                {value: 'reviewed', label: 'Reviewed for use in a separate application action'},
                {value: 'rejected', label: 'Rejected — do not use this draft'},
              ]}/>
              <Field name="reason" label="Review findings" type="textarea"/>
            </ActionForm>
          </div>}
          {reviewed && <p className="notice success"><Icon name="check-circle" size={18}/>Human review recorded. Any clinical action still requires its separate authorized command.</p>}
        </> : <div className="notice warning ws-assistant-unavailable"><Icon name="info" size={21}/><div>
          <strong>AI draft unavailable · fixed-template workflow available</strong>
          <p>{result.message || result.reason || 'Your assigned care team can continue with the approved workflow.'}</p>
          <small>State: {human(result.status)} · This is not a successful live model response.</small>
        </div></div>}
      </div>}
    </Disclosure>
  </div>;
}
