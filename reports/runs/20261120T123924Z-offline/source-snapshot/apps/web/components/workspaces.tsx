'use client';

import Link from 'next/link';
import {useEffect, useMemo, useState} from 'react';
import {api, envelope, human, needsUrgentReview, rows, when, type CareCase, type Row} from '@/lib/api';
import {useSession} from './shell';
import {useResource, LoadState, PageHeading, ConsultationList, EvidenceForm, Stat} from './care';
import {ActionButton, ActionForm, Badge, Disclosure, Empty, Field, Panel, StateBadge} from './ui';
import {Icon} from './icon';

const initials = (name: string) => name.split(' ').filter(Boolean).map(part => part[0]).slice(0, 2).join('');
const count = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const formatNumber = (value: unknown) => count(value) === null ? 'Not measured' : Number(value).toLocaleString('en-GB');
const percent = (value: number, total: number) => total > 0 ? Math.max(0, Math.min(100, value / total * 100)) : 0;

function RefreshButton({onClick}: {onClick: () => unknown}) {
  return <button className="button secondary" onClick={onClick}><Icon name="refresh" size={16}/> Refresh</button>;
}

export function Clinical() {
  const {data, error, loading, load} = useResource<Row[]>('/cases');
  const {user} = useSession();
  const [chosen, setChosen] = useState('');
  const [query, setQuery] = useState('');
  const list = rows(data);
  const filtered = list.filter(item => `${item.patient_name} ${item.id} ${item.patient_id}`.toLowerCase().includes(query.toLowerCase()));
  const selected = list.some(item => item.id === chosen) ? chosen : list[0]?.id;
  const pending = list.reduce((total, item) => total + rows(item.consultations).filter(question => !question.reply).length, 0);

  return <div className="ws-view ws-clinical">
    <PageHeading eyebrow={user.role === 'specialist' ? 'SPECIALIST CONSULTATION' : 'CLINICAL WORKSPACE'} title="Human expertise. Connected care." description="The right question. A human response. A clear, owned next step.">
      <RefreshButton onClick={load}/>
    </PageHeading>
    <LoadState loading={loading} error={error} retry={load}/>
    {!loading && !error && <>
      <div className="ws-overview-strip">
        <span><span className="ws-mini-icon"><Icon name="clipboard-check"/></span><strong>{list.length}</strong> assigned episodes</span>
        <span><span className="ws-mini-icon"><Icon name="message-circle"/></span><strong>{pending}</strong> awaiting a human reply</span>
        <span className={list.some(needsUrgentReview) ? 'ws-attention' : ''}><span className="ws-mini-icon"><Icon name="shield"/></span><strong>{list.filter(needsUrgentReview).length}</strong> urgent reviews</span>
        <small><Icon name="lock" size={13}/> Your authorized episodes only</small>
      </div>
      {list.length ? <div className="ws-clinical-grid">
        <Panel title="Assigned episodes" eyebrow="YOUR CLINICAL DESK" className="ws-inbox">
          <label className="ws-search"><Icon name="search" size={17}/><input aria-label="Search assigned episodes" placeholder="Find a patient or episode" value={query} onChange={event => setQuery(event.target.value)}/></label>
          <div className="clinical-case-list ws-case-list">
            {filtered.map(item => <button key={item.id} className={selected === item.id ? 'selected' : ''} onClick={() => setChosen(item.id)} aria-pressed={selected === item.id}>
              <span className="ws-inbox-patient"><span className="ws-avatar">{initials(item.patient_name || 'Patient')}</span><span><strong>{item.patient_name}</strong><small>{item.id}</small></span>{needsUrgentReview(item) && <Icon name="alert-circle" className="ws-attention" size={17}/>}</span>
              <span className="ws-inbox-action">{item.next_action || human(item.phase)}</span>
              <span className="ws-inbox-foot"><span>{human(item.owner)}</span><Icon name="arrow-right" size={15}/></span>
            </button>)}
            {!filtered.length && <Empty title="No matching episodes">Try the patient name or case reference.</Empty>}
          </div>
        </Panel>
        {selected && <ClinicalCase key={selected} id={selected}/>}
      </div> : <Panel><Empty title="No clinical episodes assigned">Your assigned patient questions and specialist requests will appear here.</Empty></Panel>}
    </>}
  </div>;
}

function ClinicalCase({id}: {id: string}) {
  const {data: c, error, loading, load} = useResource<CareCase>(`/cases/${id}`);
  const {user} = useSession();
  async function command(path: string, body: Row = {}) {
    if (!c) return;
    await api(path, {...envelope(c.version), ...body});
    await load();
  }
  if (loading || error || !c) return <LoadState loading={loading} error={error} retry={load}/>;
  const questions = rows(c.consultations);

  return <div className="clinical-main ws-clinical-main">
    <Panel title={c.patient_name} eyebrow="PATIENT CONTEXT" className="ws-patient-context" action={<Link className="button secondary" href={`/cases/${c.id}`}>Full case journey <Icon name="arrow-up-right" size={16}/></Link>}>
      <div className="ws-context-facts"><span><small>PATIENT REFERENCE</small>{c.patient_id}</span><span><small>SOURCE RESULT</small>Version {c.result_version}</span><span><small>EPISODE OWNER</small>{human(c.owner)}</span></div>
      <div className="ws-next-line"><Icon name="arrow-right" size={19}/><div><small>NEXT COORDINATION ACTION</small><p>{c.next_action}</p></div></div>
      {needsUrgentReview(c) && <div className="notice error"><Icon name="alert-circle" size={20}/><span>Trusted urgent source signal. Record acknowledgement and clinical disposition in the full case journey.</span></div>}
    </Panel>
    <Panel title="Questions & specialist replies" eyebrow="HUMAN CONSULTATION" action={<Badge>{questions.length} {questions.length === 1 ? 'thread' : 'threads'}</Badge>} className="ws-consultations">
      <ConsultationList c={c} command={command} role={user.role}/>
    </Panel>
    {user.role === 'clinician' && <Panel title="Request a specialist opinion" eyebrow="CONNECT THE NEXT EXPERT" className="ws-consult-request">
      <div className="ws-form-intro"><span className="ws-feature-icon"><Icon name="stethoscope" size={22}/></span><p>Share the clinical question and the relevant uncertainty. The specialist’s reply becomes part of the same care record.</p></div>
      <ActionForm label="Assign specialist consultation" onSubmit={body => command('/consultations', {...body, case_id: c.id, type: 'clinician_to_specialist'})}>
        <Field name="question" label="Clinical question and relevant uncertainty" type="textarea"/>
        <Field name="recipient" label="Named receiving service" defaultValue="specialist" options={[{value: 'specialist', label: 'Colorectal specialist'}]}/>
      </ActionForm>
      <p className="microcopy"><Icon name="user" size={14}/> The receiving specialist must author the reply. Drafts and summaries do not count as a human consultation.</p>
    </Panel>}
  </div>;
}

export function Receiving() {
  const {data, error, loading, load} = useResource<Row[]>('/referrals');
  const {user} = useSession();
  const packets = rows(data);
  const state = (packet: Row) => (packet.handoff || packet).status;
  const pending = packets.filter(packet => ['proposed', 'pending', 'requested', 'awaiting_acceptance'].includes(state(packet))).length;

  return <div className="ws-view ws-receiving">
    <PageHeading eyebrow="RECEIVING SERVICE" title="A clear handoff. Shared responsibility." description={`${human(user.organization)} · The information you need, within the scope you were granted.`}>
      <RefreshButton onClick={load}/>
    </PageHeading>
    <LoadState loading={loading} error={error} retry={load}/>
    {!loading && !error && <>
      <div className="ws-overview-strip"><span><span className="ws-mini-icon"><Icon name="file-text"/></span><strong>{packets.length}</strong> authorized packets</span><span><span className="ws-mini-icon"><Icon name="clock"/></span><strong>{pending}</strong> awaiting your decision</span><span><span className="ws-mini-icon"><Icon name="check-circle"/></span><strong>{packets.filter(packet => state(packet) === 'accepted').length}</strong> accepted</span><small><Icon name="shield" size={14}/> Minimum necessary access</small></div>
      {packets.length ? <div className="referral-grid ws-referral-grid">{packets.map(packet => <ReferralCard key={packet.id || packet.handoff_id} packet={packet} refresh={load}/>)}</div> : <Panel><Empty title="No authorized referrals yet">A referring team must propose a scoped handoff before this service can view a packet.</Empty></Panel>}
    </>}
  </div>;
}

function ReferralCard({packet: p, refresh}: {packet: Row; refresh: () => Promise<unknown>}) {
  const info = p.packet || p;
  const handoff = p.handoff || p;
  const version = p.case_version || p.version || info.version || handoff.case_version;
  const id = p.handoff_id || handoff.id;
  const caseId = p.case_id || info.case_id || info.id;
  const provider = p.receiver || handoff.receiver;
  const requested = ['proposed', 'pending', 'requested', 'awaiting_acceptance'].includes(handoff.status);
  async function command(path: string, body: Row = {}) {
    await api(path, {...envelope(version), ...body});
    await refresh();
  }

  return <Panel id={'referral-' + id} title={info.patient_name || info.patient_id || 'Authorized referral'} eyebrow="MINIMUM REFERRAL PACKET" className="ws-referral-card" action={<StateBadge state={handoff.status}/>}>
    <div className="ws-referral-identity"><span className="ws-avatar ws-avatar-large"><Icon name="user" size={24}/></span><div><small>REFERRAL FOR ASSESSMENT</small><strong>Colorectal screening follow-up</strong><span>{caseId}</span></div></div>
    <div className="referral-details ws-packet-facts">
      <span>Patient reference <strong>{info.patient_id}</strong></span><span>Order <strong>{info.order_id || 'In packet'}</strong></span>
      <span>Scope <strong>{human(handoff.scope || p.scope)}</strong></span><span>Sending owner <strong>{human(handoff.sending_owner || handoff.sender || p.sending_owner || info.owner)}</strong></span>
      <span>Result version <strong>{info.result_version || p.result_version || 'In packet'}</strong></span><span>Receiving service <strong>{human(provider)}</strong></span>
    </div>
    <div className="ws-referral-reason"><small>REASON FOR REFERRAL</small><p>{handoff.reason || info.reason || 'Colorectal screening follow-up assessment.'}</p></div>
    <div className="ws-access-note"><Icon name="lock" size={16}/><p>This access is limited to the granted referral. Acceptance changes only the intended ownership scope.</p></div>
    {requested && <div className="referral-actions ws-referral-decisions">
      <ActionButton onClick={() => command(`/handoffs/${id}/accept`, {reason: 'Accepted by receiving service'})}><Icon name="check" size={17}/> Accept referral</ActionButton>
      <Disclosure title="Reject or request more information"><ActionForm label="Reject with recorded reason" onSubmit={body => command(`/handoffs/${id}/reject`, body)}><Field name="reason" label="Rejection reason / information needed" type="textarea"/></ActionForm></Disclosure>
    </div>}
    {handoff.status === 'accepted' && <div className="ws-provider-actions">
      <div className="ws-section-kicker"><Icon name="calendar" size={17}/><span>APPOINTMENT COORDINATION</span></div>
      <Disclosure title="Report no available slots"><p className="microcopy">Record a capacity problem before booking. The accountable care team receives owned recovery work; no appointment is created.</p><ActionForm label="Record unavailable capacity" onSubmit={body => command(`/cases/${caseId}/capacity`, {...body, status: 'no_slots'})}><Field name="reason" label="Capacity reason and practical next action" type="textarea"/></ActionForm></Disclosure>
      <Disclosure title="Confirm an appointment" open><ActionForm label="Record confirmed appointment" onSubmit={body => command(`/cases/${caseId}/appointments`, {...body, provider, scheduled_at: new Date(body.scheduled_at).toISOString()})}><Field name="scheduled_at" label="Confirmed appointment date and time" type="datetime-local"/></ActionForm></Disclosure>
      {rows(p.appointments || info.appointments).map(appointment => <div className="appointment-card ws-provider-appointment" key={appointment.id}>
        <div className="record-row"><div><small>CONFIRMED DATE & TIME</small><strong>{when(appointment.scheduled_at)}</strong></div><StateBadge state={appointment.status}/></div>
        <ActionForm label="Record appointment event" onSubmit={body => command(`/appointments/${appointment.id}/events`, {...body, source_event_id: crypto.randomUUID()})}><Field name="status" label="Attendance / booking event" defaultValue="attended" options={['booked', 'attended', 'cancelled', 'no_show', 'no_slots']}/></ActionForm>
      </div>)}
      <div className="ws-section-kicker"><Icon name="file-check" size={17}/><span>RETURNING SOURCE EVIDENCE</span></div>
      <Disclosure title="Return source evidence"><EvidenceForm c={{...info, source_organization: provider}} onSubmit={body => command(`/cases/${caseId}/evidence`, body)}/></Disclosure>
      <p className="microcopy">Booking, attendance, investigation and completed care remain separate records.</p>
    </div>}
  </Panel>;
}

const stageLabels: Record<string, string> = {notified: 'Notification delivered', acknowledged: 'Patient acknowledged', understood: 'Understanding confirmed', consultation_replied: 'Human consultation reply', referral_accepted: 'Referral accepted', attended: 'Appointment attended', care_completed: 'Required care completed'};
const chartColors = ['#086c68', '#71aaa2', '#c4a46b', '#a2bba9', '#c2826e', '#9aa8b6', '#d1d9d3'];

function StageChart({metrics}: {metrics: Row}) {
  const denominator = count(metrics.denominator);
  const entries = Object.entries(metrics.stages || {}).filter(([, value]) => count(value) !== null);
  return <Panel title="From result to evidenced care" eyebrow="INDEPENDENT MILESTONES" className="ws-stage-panel" action={<Badge>{denominator === null ? 'Not measured' : `${denominator} episodes`}</Badge>}>
    <p className="panel-intro">Every bar uses the full actionable-episode denominator. Milestones may overlap; this is not a linear funnel.</p>
    {entries.length && denominator !== null ? <div className="ws-stage-chart" role="img" aria-label="Recorded milestone counts out of the full actionable episode denominator">
      {entries.map(([key, value], index) => <div className="ws-stage-row" key={key}><div><span>{stageLabels[key] || human(key)}</span><strong>{formatNumber(value)}<small> / {denominator}</small></strong></div><div className="ws-bar-track"><span style={{width: `${percent(Number(value), denominator)}%`, background: index === entries.length - 1 ? '#086c68' : '#84b8af'}}/></div></div>)}
    </div> : <Empty title="No milestone measurements yet">Measurements appear when episode events are recorded.</Empty>}
    <div className="ws-chart-caption"><Icon name="info" size={15}/> Decline, unreachable and accepted transfers with care still open remain in the denominator.</div>
  </Panel>;
}

function DispositionChart({metrics}: {metrics: Row}) {
  const entries = Object.entries(metrics.dispositions || {}).filter(([, value]) => typeof value === 'number' && value > 0);
  const total = entries.reduce((sum, [, value]) => sum + Number(value), 0);
  let running = 0;
  const stops = entries.map(([, value], index) => {const start = running; running += total ? Number(value) / total * 100 : 0; return `${chartColors[index % chartColors.length]} ${start}% ${running}%`;});
  return <Panel title="Every outcome stays visible" eyebrow="EPISODE DISPOSITIONS" className="ws-disposition-panel">
    {total > 0 ? <>
      <div className="ws-donut" style={{background: `conic-gradient(${stops.join(',')})`}} role="img" aria-label={entries.map(([name, value]) => `${human(name)} ${value}`).join(', ')}><div><strong>{total.toLocaleString('en-GB')}</strong><span>recorded episodes</span></div></div>
      <div className="ws-chart-legend">{entries.map(([name, value], index) => <div key={name}><span style={{background: chartColors[index % chartColors.length]}}/><label>{human(name)}</label><strong>{String(value)}</strong></div>)}</div>
    </> : <Empty title="No dispositions recorded"/>}
    <p className="microcopy">An administrative or exception disposition is separate from completed required care.</p>
  </Panel>;
}

export function Operations() {
  const {data: ops, error, loading, load} = useResource<Row>('/operations');
  const {data: metrics, error: metricError, loading: metricLoading, load: loadMetrics} = useResource<Row>('/metrics');
  const {user, demo} = useSession();
  const [outboxFilter, setOutboxFilter] = useState('all');
  const [visibleOutbox, setVisibleOutbox] = useState(6);
  async function refresh() {await Promise.all([load(), loadMetrics()]);}
  const counts = metrics?.counts || metrics || {};
  const outbox = rows(ops?.outbox);
  const filteredOutbox = outbox.filter(item => outboxFilter === 'all' || (outboxFilter === 'attention' ? ['retry', 'failed', 'dead_letter', 'pending_retry'].includes(item.status) : item.status === 'delivered'));
  const attention = outbox.filter(item => ['retry', 'failed', 'dead_letter', 'pending_retry'].includes(item.status)).length;
  const connectors = Array.isArray(ops?.connectors) ? ops.connectors : Object.entries(ops?.connectors || {}).map(([name, status]) => ({name, status}));

  return <div className="ws-view ws-operations">
    <PageHeading eyebrow="OPERATIONS & IMPACT" title="Keep the loop moving." description="A clear view of outstanding work, responsible teams and evidenced outcomes."><RefreshButton onClick={refresh}/></PageHeading>
    <LoadState loading={loading || metricLoading} error={error || metricError} retry={refresh}/>
    {!loading && !metricLoading && !error && !metricError && <>
      <div className="stat-grid ws-stat-grid">
        <Stat label="Actionable-case denominator" value={metrics?.denominator ?? metrics?.actionable_cases ?? 'Not measured'} note="Includes declined, unreachable, and open transfers"/>
        <Stat label="Required care completed" value={counts.completed_required_care ?? counts.care_completed ?? 'Not measured'} note="Evidence-backed endpoint, separate from exceptions"/>
        <Stat label="Residual care need" value={counts.residual_need ?? counts.residual_need_count ?? 'Not measured'} note="Ongoing need remains visible after disposition"/>
        <Stat label="Understanding passed" value={counts.understanding_passed ?? counts.understood ?? 'Not measured'} note="Separate from delivery and acknowledgement"/>
      </div>
      <div className="ws-impact-grid"><StageChart metrics={metrics || {}}/><DispositionChart metrics={metrics || {}}/></div>
      <div className="ws-section-heading"><div><p className="eyebrow">KEEP WORK MOVING</p><h2>Attention has an owner.</h2></div><Badge tone={attention ? 'warning' : 'neutral'}>{attention} delivery items need attention</Badge></div>
      <div className="ws-recovery-grid">
        <Panel title="Delivery & integration outbox" eyebrow="PERSISTED RECOVERY" className="ws-outbox-panel" action={<span className="ws-panel-icon"><Icon name="send"/></span>}>
          <div className="ws-filter-pills" aria-label="Filter delivery outbox">{[['all', 'All delivery'], ['attention', 'Needs attention'], ['delivered', 'Delivered']].map(([value, label]) => <button key={value} aria-pressed={outboxFilter === value} className={outboxFilter === value ? 'selected' : ''} onClick={() => {setOutboxFilter(value); setVisibleOutbox(6);}}>{label}</button>)}</div>
          {filteredOutbox.length ? <div className="ws-outbox-list">{filteredOutbox.slice(0, visibleOutbox).map(item => <div className="outbox-row" key={item.id}>
            <div className="record-row"><strong>{human(item.kind || item.type || item.event_type || item.topic)}</strong><StateBadge state={item.status}/></div>
            <p>Owner: {human(item.owner || 'operations-exception-queue')} · Attempts: {item.attempts ?? 0}</p>
            <small>{item.error_code ? `Error: ${human(item.error_code)}` : item.last_error || item.error || item.destination || 'Local simulated delivery'}</small>
            {item.case_id && <p><Link href={`/cases/${item.case_id}`}>Open case {item.case_id} <Icon name="arrow-up-right" size={14}/></Link></p>}
            {['failed', 'dead_letter', 'pending_retry', 'retry'].includes(item.status) && <ActionButton variant="secondary" onClick={async () => {await api(`/operations/outbox/${item.id}/retry`, {idempotency_key: crypto.randomUUID()}); await refresh();}}>Retry delivery</ActionButton>}
          </div>)}</div> : <Empty title="No outbox records">No delivery items match this view.</Empty>}
          {filteredOutbox.length > visibleOutbox && <button className="button secondary full" onClick={() => setVisibleOutbox(value => value + 10)}>Show more delivery records <Icon name="chevron-down" size={16}/></button>}
        </Panel>
        <div className="ws-recovery-side">
          <Panel title="Urgent staff acknowledgements" eyebrow="HUMAN REVIEW" action={<span className="ws-panel-icon ws-red"><Icon name="bell"/></span>}>
            {rows(ops?.pending_escalations).length ? rows(ops?.pending_escalations).map(item => <div className="record-row ws-action-record" key={item.id}><div><strong>{human(item.trigger)}</strong><p>{human(item.recipient)} · Backup {human(item.backup || item.backup_queue)}</p><Link href={`/cases/${item.case_id}`}>Open urgent review <Icon name="arrow-up-right" size={14}/></Link></div><StateBadge state={item.acknowledged_at ? 'acknowledged' : 'pending'}/></div>) : <div className="ws-clear-state"><Icon name="check-circle"/><strong>No pending urgent acknowledgements</strong><p>Clinical disposition remains separate from staff acknowledgement.</p></div>}
          </Panel>
          <Panel title="Overdue & unassigned work" action={<span className="ws-panel-icon"><Icon name="clock"/></span>}>
            {rows(ops?.overdue).length ? <div className="ws-overdue-list">{rows(ops?.overdue).map(item => <div className="record-row ws-action-record" key={item.id}><div><strong>{human(item.type)}</strong><p>{item.next_action}</p><small>{human(item.assignee)} · {when(item.due_at)}</small>{item.case_id && <p><Link href={`/cases/${item.case_id}`}>Open case <Icon name="arrow-up-right" size={14}/></Link></p>}</div><StateBadge state={item.status}/></div>)}</div> : <Empty title="No overdue work returned"/>}
          </Panel>
        </div>
      </div>
      <Panel title="Connector capabilities" eyebrow="TRANSPARENT CONNECTION STATUS" className="ws-connectors"><div className="ws-connector-grid">{connectors.map((item: Row, index: number) => <div key={item.id || item.name || index}><span className="ws-feature-icon"><Icon name={String(item.name || item.id).toLowerCase().includes('provider') ? 'building' : 'network'} size={21}/></span><strong>{human(item.name || item.id)}</strong><StateBadge state={item.status || item.mode}/><p>{item.description || item.detail || 'See implemented capability matrix'}</p></div>)}</div><p className="microcopy">Provider services and FHIR are test integrations. No live EHR, Malaffi, NABIDH, or Riayati connection is claimed.</p></Panel>
      <Panel title="Measured coordination outcomes" eyebrow="FULL DENOMINATOR"><p className="panel-intro">These values come from persisted episodes. Administrative disposition and completed required care stay separate.</p><Disclosure title="Inspect the full metric definitions and observed values"><MetricTable data={metrics || {}}/></Disclosure><div className="ws-experience-note"><Icon name="heart" size={20}/><div><strong>Patient experience is recorded feedback.</strong><p>{metrics?.experience?.responses ? `${metrics.experience.responses} synthetic responses · Clarity ${metrics.experience.confidence_mean ?? 'not measured'}/5 · Reassurance ${metrics.experience.reassurance_mean ?? 'not measured'}/5.` : 'No patient experience responses measured.'} Self-reports do not establish clinical improvement or a volunteer study.</p></div></div></Panel>
      {demo && user.role === 'admin' && <Panel title="Synthetic demonstration controls" className="ws-demo-controls" action={<Badge>Demo only</Badge>}><p>Clock advances affect only the synthetic demonstration dataset. Service windows are operational examples, not clinical deadlines.</p><div className="two-column"><ActionForm label="Advance demo clock" onSubmit={async body => {await api('/demo/clock', {hours: Number(body.hours)}); await refresh();}}><Field name="hours" label="Hours to advance" type="number" defaultValue={25}/></ActionForm><Disclosure title="Reset identified synthetic dataset"><p>Reset replaces only the named Suhail synthetic demonstration records. Evaluation reports are preserved.</p><ActionButton variant="danger" onClick={async () => {await api('/demo/reset', {dataset: 'suhail-demo-v1'}); await refresh();}}>Reset synthetic demonstration</ActionButton></Disclosure></div></Panel>}
    </>}
  </div>;
}

function MetricTable({data}: {data: Row}) {
  const flat = Object.entries(data).flatMap(([key, value]) => value !== null && typeof value === 'object' && !Array.isArray(value) ? Object.entries(value).map(([sub, item]) => [`${key}: ${sub}`, item]) : [[key, value]]);
  return <div className="table-scroll"><table className="metrics-table"><thead><tr><th>Measure</th><th>Observed value</th></tr></thead><tbody>{flat.map(([key, value]) => <tr key={String(key)}><td>{human(key)}</td><td>{value === null ? 'Not measured' : typeof value === 'object' ? JSON.stringify(value) : String(value)}</td></tr>)}</tbody></table></div>;
}

const agentNames: Record<string, string> = {intake: 'Source intake', pathway_router: 'Pathway routing', safety_escalation: 'Safety & escalation', patient_navigator: 'Patient navigation', coordination: 'Care coordination', closure_evidence: 'Closure evidence'};
const agentIcons: Record<string, string> = {intake: 'file-text', pathway_router: 'git-branch', safety_escalation: 'shield', patient_navigator: 'message-circle', coordination: 'network', closure_evidence: 'file-check'};
const reportFiles = ['summary.html', 'summary.md', 'summary.json', 'metrics.csv', 'manifest.json', 'dataset-manifest.json', 'journeys.csv'];

function ReportLinks({runId, compact = false, files = reportFiles}: {runId: string; compact?: boolean; files?: string[]}) {
  return <div className={`report-downloads ws-report-downloads ${compact ? 'ws-compact-downloads' : ''}`}>{files.map(file => <a className="button secondary" key={file} href={`/api/reports/${runId}/${file}`} target="_blank" rel="noreferrer"><Icon name="download" size={14}/>{file}</a>)}</div>;
}

function useReportSummaries(reports: Row[]) {
  const [summaries, setSummaries] = useState<Record<string, Row>>({});
  const [failures, setFailures] = useState<Record<string, string>>({});
  const key = reports.map(report => report.run_id || report.id).join('|');
  useEffect(() => {
    let active = true;
    const ids = key.split('|').filter(Boolean);
    Promise.allSettled(ids.map(async id => {
      try {
        const summary = await api<Row>(`/reports/${id}/summary.json`);
        if (active) setSummaries(previous => ({...previous, [id]: summary}));
      } catch {
        if (active) setFailures(previous => ({...previous, [id]: 'Summary not available. Inspect the provenance manifest for this run.'}));
      }
    }));
    return () => {active = false;};
  }, [key]);
  return {summaries, failures};
}

export function Evaluation() {
  const {data, error, loading, load} = useResource<Row[]>('/reports');
  const reports = useMemo(() => rows(data), [data]);
  const {summaries, failures} = useReportSummaries(reports);
  const ordered = [...reports].sort((a, b) => String(b.started_at || '').localeCompare(String(a.started_at || '')));
  const liveManifest = ordered.find(report => report.kind === 'live' && report.status === 'PARTIAL' && !report.prepare_only) || ordered.find(report => report.kind === 'live' && !report.prepare_only);
  const softwareManifest = ordered.find(report => report.kind === 'offline' && report.status === 'COMPLETE');
  const live = liveManifest ? summaries[liveManifest.run_id] : null;
  const software = softwareManifest ? summaries[softwareManifest.run_id] : null;
  const primary = live?.counts;
  const softwareCounts = software?.counts;
  const agents = Object.entries(agentNames).map(([id, label]) => ({id, label, report: live?.components?.[id]}));
  const external = live?.components?.external_suite;
  const publicManifest = ordered.find(report => report.evidence_mode === 'public_input_operational_conformance');
  const publicReport = publicManifest ? summaries[publicManifest.run_id] : null;
  const publicInput = publicReport?.public_input;
  const publicModelMetric = rows(external?.metrics).find(metric => metric.name === 'adapted_healthbench_rubric_score');
  const audit = live?.secondary_scoring_audit;
  const dispatch = live?.dispatch_accounting;
  const budget = live?.budget || {};
  const agentEvaluated = agents.reduce((sum, agent) => sum + (agent.report?.counts?.completed || 0), 0);
  const agentSelected = agents.reduce((sum, agent) => sum + (agent.report?.counts?.selected || 0), 0);
  const primaryAgentPassed = agents.reduce((sum, agent) => sum + (agent.report?.counts?.task_passed || 0), 0);
  const primaryAgentFailures = agents.reduce((sum, agent) => sum + (agent.report?.counts?.failed || 0), 0);
  const joinedReady = !!audit && agents.every(agent => count(agent.report?.counts?.completed) !== null);
  const joinedPassed = primaryAgentPassed + (audit?.task_passed || 0);
  const joinedTotal = agentEvaluated + (audit?.existing_live_responses_audited || 0);


  return <div className="ws-view ws-evaluation">
    <PageHeading eyebrow="RESTRICTED EVALUATION WORKSPACE" title="Measured evidence. Clear limits." description="Traceable execution. Separate evidence layers. Every failure stays in view."><RefreshButton onClick={load}/></PageHeading>
    <LoadState loading={loading} error={error} retry={load}/>
    {!loading && !error && <>
      <div className="ws-evaluation-note"><span className="ws-feature-icon"><Icon name="shield" size={23}/></span><div><strong>Expert clinical assessment: not performed</strong><p>Software verification and benchmark estimates do not establish medical validation or patient outcome improvement.</p></div><Badge>Administrator access</Badge></div>
      {reports.length ? <>
        <section className="ws-conformance-hero" aria-label="Standalone function conformance, including a separate post-hoc scoring audit">
          <div className="ws-conformance-story"><p className="eyebrow"><Icon name="sparkles" size={15}/> SIX FUNCTIONS · TRACEABLE RESPONSES</p><h2>Standalone function conformance</h2><p>{joinedReady ? `${joinedPassed} of ${joinedTotal} saved standalone responses passed the known synthetic checks.` : 'Reading the saved primary scoring and separate response audit.'}</p><small>{joinedReady ? `${agentEvaluated} primary scored responses + ${audit.existing_live_responses_audited} responses in a separate post-hoc saved-response audit. ${primaryAgentFailures} original primary scoring failures retained.` : 'Original primary records and denominators remain unchanged.'}</small></div>
          <div className="ws-conformance-score"><strong>{joinedReady && joinedTotal ? (joinedPassed / joinedTotal * 100).toFixed(1) : '—'}<small>{joinedReady ? '%' : ''}</small></strong><span>primary + post-hoc audit</span><p>Known synthetic cases<br/>Not clinical accuracy</p></div>
        </section>
        {publicManifest && <Panel title="Public questions. Actual navigation agent." eyebrow="PUBLIC DATASET · SEPARATE OPERATIONAL TEST" className="ws-public-input" action={<StateBadge state={publicReport?.status || publicManifest.status}/>}>
          <div className="ws-public-story"><div><span className="ws-evidence-label"><Icon name="globe" size={19}/> HealthBench · pinned public source</span><p>Preselected public questions submitted through Suhail’s actual patient-navigation agent, inside an explicitly synthetic workflow context.</p><small>Tests source-linked routing, a supported next step and human-review boundaries. It does not measure medical answer accuracy or complete the original HealthBench benchmark.</small></div><div className={'ws-public-score' + (publicInput?.evaluated === 0 ? ' ws-public-unscored' : '')}><strong>{publicInput ? publicInput.evaluated > 0 ? `${publicInput.passed} / ${publicInput.evaluated}` : 'Not scored' : '—'}</strong><span>{publicInput && publicInput.evaluated === 0 ? 'No evaluated model response' : 'operational cases passed'}</span><small>{publicInput ? `${publicInput.selected} selected · ${publicInput.evaluated} evaluated · ${publicInput.failed} failed` : 'Reading executed records'}</small></div></div>
          <div className="ws-public-footer"><p><Icon name="info" size={15}/>{publicInput?.limitations || 'A small exploratory public-input pilot, separate from known-family synthetic conformance. No clinical validation or broad generalization claim.'}</p><a className="button secondary" href={`/api/reports/${publicManifest.run_id}/summary.html`} target="_blank" rel="noreferrer">Inspect the public-input report <Icon name="arrow-up-right" size={15}/></a></div>
        </Panel>}
        <div className="ws-evidence-grid">
          <article className="ws-evidence-card"><span className="ws-evidence-label"><Icon name="clipboard-check" size={19}/> SOFTWARE & RELIABILITY</span><strong>{softwareCounts ? formatNumber(softwareCounts.completed) : '—'}<small> evaluated cases</small></strong><p>Persisted workflow trajectories and invalid-closure attempts.</p><div><StateBadge state={software?.status || softwareManifest?.status || 'NOT_RUN'}/><span>{software ? `${software.usage?.api_calls ?? 0} model calls` : 'Loading saved measurements'}</span></div></article>
          <article className="ws-evidence-card ws-evidence-live"><span className="ws-evidence-label"><Icon name="sparkles" size={19}/> BUDGETED GROQ RUN</span><strong>{primary ? formatNumber(primary.completed) : '—'}<small>{primary ? ` / ${primary.selected} evaluated` : ' primary records'}</small></strong><p>{primary ? `${primary.failed} failed · ${primary.skipped} skipped. Across selected run records; original outcomes retained.` : 'Reads actual saved response and execution records.'}</p><div><StateBadge state={live?.status || liveManifest?.status || 'NOT_RUN'}/><span>{liveManifest?.model || 'Model not measured'}</span></div></article>
          <article className="ws-evidence-card"><span className="ws-evidence-label"><Icon name="layers" size={19}/> ADAPTED EXTERNAL RUBRICS</span><strong>{external?.counts ? formatNumber(external.counts.completed) : '—'}<small>{external?.counts ? ` / ${external.counts.selected} conversations` : ' conversations'}</small></strong><p>Earlier base-model HealthBench conversations with a Groq grader. {count(publicModelMetric?.value) !== null ? `${(Number(publicModelMetric?.value) * 100).toFixed(1)}% adapted rubric estimate; ` : ''}not application-agent accuracy.</p><div><StateBadge state={external?.status || 'Awaiting report'}/><span>Not the official overall score</span></div></article>
        </div>
        <div className="ws-evaluation-grid">
          <Panel title="Six bounded functions. Actual execution." eyebrow="MODEL-ASSISTED COORDINATION" className="ws-agent-panel" action={<Badge>{live ? `${agentEvaluated}/${agentSelected} primary agent cases evaluated` : 'Saved records only'}</Badge>}>
            <p className="panel-intro">Coverage measures completed scoring, not clinical correctness. Failed and unscored cases remain in each selected denominator.</p>
            <div className="ws-agent-grid">{agents.map(agent => {const counts = agent.report?.counts; return <article className="ws-agent-card" key={agent.id}><div className="ws-agent-title"><span className="ws-mini-icon"><Icon name={agentIcons[agent.id]} size={20}/></span><h3>{agent.label}</h3><StateBadge state={agent.report?.status || (liveManifest ? 'Loading records' : 'Not measured')}/></div><div className="ws-agent-value"><strong>{counts ? counts.completed : '—'}</strong><span>{counts ? `/ ${counts.selected} evaluated` : 'Not measured'}</span></div><div className="ws-bar-track"><span style={{width: `${counts ? percent(counts.completed, counts.selected) : 0}%`}}/></div><p>{counts ? `${counts.failed} failed · ${counts.skipped} skipped` : 'Awaiting saved report data'}</p>{liveManifest && <a href={`/api/reports/${liveManifest.run_id}/agents/${agent.id}.html`} target="_blank" rel="noreferrer">Inspect function report <Icon name="arrow-up-right" size={14}/></a>}</article>;})}</div>
          </Panel>
          <div className="ws-evaluation-side">
            <Panel title="A separate scoring audit" eyebrow="EXISTING RESPONSES · NO NEW INFERENCE" className="ws-audit-card"><span className="ws-panel-icon"><Icon name="file-check" size={24}/></span>{audit ? <><div className="ws-audit-values"><div><strong>{audit.task_passed}</strong><span>correct</span></div><div><strong>{audit.task_incorrect}</strong><span>incorrect</span></div><div><strong>{audit.new_api_calls}</strong><span>new API calls</span></div></div><p>The source-language scoring repair re-examines {audit.existing_live_responses_audited} saved responses. Primary scoring failures and denominators remain unchanged.</p>{liveManifest && <a className="ws-text-link" href={`/api/reports/${liveManifest.run_id}/secondary-scoring-audit/summary.html`} target="_blank" rel="noreferrer">Open the labelled secondary audit <Icon name="arrow-up-right" size={15}/></a>}</> : <p>No separate audit measurement is available.</p>}</Panel>
            <Panel title="Spending has explicit limits" eyebrow="REQUEST & TOKEN ACCOUNTING" className="ws-budget-card"><div className="ws-accounting-row"><span>Reserved request attempts</span><strong>{dispatch ? formatNumber(dispatch.reservation_attempts) : 'Not measured'}</strong></div><div className="ws-accounting-row"><span>Confirmed actual dispatches</span><strong>{dispatch?.actual_dispatched_requests == null ? 'Not measured' : formatNumber(dispatch.actual_dispatched_requests)}</strong></div><div className="ws-accounting-row"><span>Conservative tokens charged</span><strong>{budget.charged_tokens == null ? 'Not measured' : formatNumber(budget.charged_tokens)}</strong></div>{budget.max_tokens > 0 && <><div className="ws-bar-track"><span style={{width: `${percent(budget.charged_tokens || 0, budget.max_tokens)}%`}}/></div><p className="microcopy">Allowance {formatNumber(budget.max_tokens)} tokens. Unknown usage keeps its conservative reservation.</p></>}<div className="ws-accounting-row"><span>Complete measured cost</span><strong>{live?.usage?.cost_usd == null ? 'Unknown' : `$${Number(live.usage.cost_usd).toFixed(4)}`}</strong></div><p className="microcopy">Queued cancellations are request reservations, not a claim of paid inference.</p></Panel>
          </div>
        </div>
        {liveManifest && <Panel title={liveManifest.run_id} eyebrow="CURRENT LIVE EXECUTION RECORD" action={<StateBadge state={live?.status || liveManifest.status}/>} className="ws-current-run"><div className="ws-run-snapshot"><span><small>MODEL</small><strong>{liveManifest.model || 'Not measured'}</strong></span><span><small>PRIMARY CASE COUNTS</small><strong>{primary ? `${primary.attempted} attempted · ${primary.completed} evaluated · ${primary.failed} failed` : 'Loading saved summary'}</strong></span><span><small>EXECUTION STARTED</small><strong>{when(liveManifest.started_at)}</strong></span></div><ReportLinks runId={liveManifest.run_id}/><p className="microcopy">Known-family synthetic conformance and adapted conversation estimates. Optional expert review and real patient outcome studies were not performed.</p></Panel>}
        <div className="ws-section-heading"><div><p className="eyebrow">REPRODUCIBLE BY DESIGN</p><h2>Explore the execution archive.</h2></div><Badge>{reports.length} recorded runs</Badge></div>
        <div className="ws-run-archive">{ordered.map(report => {const summary = summaries[report.run_id || report.id]; const counts = summary?.counts || report.counts; return <Panel key={report.run_id || report.id} title={report.run_id || report.id} eyebrow={human(report.evidence_mode || report.kind || 'Executed evaluation')} action={<StateBadge state={summary?.status || report.status}/>} className="ws-archive-card"><div className="report-meta"><div><small>MODEL</small><strong>{report.model || report.provenance?.model || 'Not applicable / not measured'}</strong></div><div><small>STARTED</small><strong>{when(report.started_at)}</strong></div><div><small>CASE COUNTS</small><strong>{counts ? `${counts.attempted} attempted · ${counts.completed} evaluated · ${counts.failed} failed` : failures[report.run_id] || 'Loading recorded summary…'}</strong></div><div><small>DATA / SPLIT</small><strong>{summary?.components?.intake?.provenance?.dataset || report.dataset || report.provenance?.dataset || report.split || 'See provenance manifest'}</strong></div></div>{report.reason_code && <p className="notice warning">{human(report.reason_code)}</p>}<ReportLinks runId={report.run_id || report.id} compact files={report.evidence_mode === 'public_input_operational_conformance' ? reportFiles.filter(file => file !== 'journeys.csv') : reportFiles}/><p className="microcopy">Immutable records retain case IDs, source versions, usage uncertainty and original failures.</p></Panel>;})}</div>
      </> : <Panel><Empty title="No executed reports yet">Run a permitted evaluation preset. Results appear only after actual execution records are written.</Empty></Panel>}
    </>}
  </div>;
}
