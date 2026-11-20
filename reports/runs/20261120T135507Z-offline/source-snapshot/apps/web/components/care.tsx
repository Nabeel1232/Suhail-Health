'use client';

import Link from 'next/link';
import {useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode} from 'react';
import {AnimatePresence, motion, useReducedMotion} from 'motion/react';
import {api, duration, envelope, human, relative, rows, when, needsUrgentReview, type CareCase, type Row} from '@/lib/api';
import {label, teamCodes} from '@/lib/labels';
import {Icon} from './icon';
import {useSession} from './shell';
import {FileIntake} from './intake';
import {AssistantDraft} from './assistant';
import {SourceReview} from './source-review';
import {ActionButton, ActionForm, Badge, Disclosure, Empty, ErrorBox, Field, Panel, StateBadge} from './ui';

type Command = (path: string, body?: Row) => Promise<unknown>;

export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const requestSequence = useRef(0);
  const mounted = useRef(false);
  const activePath = useRef(path);

  const load = useCallback(async () => {
    if (!path || !mounted.current || activePath.current !== path) return;
    const sequence = ++requestSequence.current;
    const isCurrent = () => mounted.current && sequence === requestSequence.current;
    setError('');
    try {
      const next = await api<T>(path);
      if (isCurrent()) setData(next);
    } catch (error) {
      if (isCurrent()) setError(error instanceof Error ? error.message : 'Unable to load workspace');
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    mounted.current = true;
    activePath.current = path;
    setData(null);
    setLoading(!!path);
    if (path) load();
    return () => {
      mounted.current = false;
      requestSequence.current += 1;
    };
  }, [load, path]);
  return {data, error, loading, load};
}

export function LoadState({loading, error, retry}: {loading: boolean; error: string; retry: () => unknown}) {
  if (loading) {
    return (
      <div className="loading-panel care-loading" role="status">
        <span className="spinner" />
        <div><strong>Opening your care workspace</strong><span>Loading your care workspace…</span></div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="panel care-error-panel">
        <ErrorBox message={error} />
        <button className="button secondary" onClick={retry}><Icon name="refresh" size={16} />Try again</button>
      </div>
    );
  }
  return null;
}

export function PageHeading({eyebrow, title, description, children}: {
  eyebrow: string; title: string; description?: string; children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{description && <p>{description}</p>}</div>
      {children}
    </div>
  );
}

function PatientAvatar({name, large = false}: {name: unknown; large?: boolean}) {
  const initials = String(name || 'Patient').replace(/\s*\(synthetic\)/gi, '').trim()
    .split(/\s+/).slice(0, 2).map(part => part[0]).join('');
  return <span className={'patient-avatar care-avatar' + (large ? ' care-avatar-large' : '')} aria-hidden="true">{initials}</span>;
}

const active = (c: Row) => c.disposition !== 'completed_required_care' &&
  (c.disposition !== 'clinically_resolved' || !!c.residual_need);
const overdue = (c: Row) => c.tasks?.some((task: Row) => task.status === 'overdue') ||
  !!(c.due_at && new Date(c.due_at).getTime() < new Date(c.now || Date.now()).getTime() && active(c));

const FILTERS = [
  ['all', 'All cases'], ['active', 'Active follow-up'], ['urgent', 'Urgent review'], ['overdue', 'Overdue'],
  ['quarantine', 'Quarantined'], ['rejected', 'Rejected transfer'],
  ['barriers', 'Barriers'], ['unassigned', 'Unassigned work'],
] as const;

function matchesFilter(c: Row, filter: string) {
  return filter === 'all' ||
    filter === 'active' && active(c) ||
    filter === 'urgent' && needsUrgentReview(c) ||
    filter === 'overdue' && overdue(c) ||
    filter === 'quarantine' && c.quarantine_reason ||
    filter === 'rejected' && c.handoffs?.some((handoff: Row) => handoff.status === 'rejected') ||
    filter === 'barriers' && c.delay_reasons?.length ||
    filter === 'unassigned' && c.tasks?.some((task: Row) => !task.assignee || String(task.assignee).includes('exception'));
}

function MilestoneProgress({c, compact = false}: {c: Row; compact?: boolean}) {
  const required = rows(c.milestones).filter(item => item.required);
  const completed = required.filter(item => item.status === 'completed').length;
  if (!required.length) return null;
  return (
    <div className={'care-progress' + (compact ? ' care-progress-compact' : '')}>
      <div className="care-progress-label">
        <span>{compact ? 'Required milestones' : 'Required milestones documented'}</span>
        <strong>{completed}<span> / {required.length}</span></strong>
      </div>
      <div className="care-progress-track" role="progressbar" aria-label="Required milestones documented"
        aria-valuemin={0} aria-valuemax={required.length} aria-valuenow={completed}
        aria-valuetext={completed + ' of ' + required.length + ' required milestones documented'}>
        <span style={{width: (completed / required.length * 100) + '%'}} />
      </div>
    </div>
  );
}

export function Stat({label, value, note, tone = '', icon = 'activity', onClick, selected = false, actionLabel}: {
  label: string; value: ReactNode; note: string; tone?: string; icon?: string; onClick?: () => void; selected?: boolean; actionLabel?: string;
}) {
  const content = <>
    <div className="care-stat-top"><p>{label}</p><span className="care-stat-icon"><Icon name={icon} size={18} /></span></div>
    <strong>{value}</strong><small>{note}</small>
    {onClick && <span className="care-stat-link">View cases<Icon name="arrow-up-right" size={13}/></span>}
  </>;
  if (onClick) return <button type="button" className={'stat-card care-stat care-stat-select ' + tone}
    aria-label={actionLabel || 'Show ' + label.toLowerCase() + ' cases'} aria-pressed={selected} onClick={onClick}>{content}</button>;
  return (
    <div className={'stat-card care-stat ' + tone}>{content}</div>
  );
}

function SlaChip({due, now}: {due: unknown; now: unknown}) {
  const deadline = Date.parse(String(due));
  const hours = (deadline - Date.parse(String(now))) / 3_600_000;
  if (!Number.isFinite(hours)) return <span className="muted care-due"><Icon name="clock" size={13}/>{Number.isFinite(deadline) ? when(due) : 'Not set'}</span>;
  const tone = hours < 0 ? 'overdue' : hours < 24 ? 'soon' : 'on-track';
  const text = hours < 0 ? 'Overdue ' + duration(-hours) : 'Due ' + relative(due, now);
  return <span className={'care-due sla-chip sla-chip-' + tone} title={when(due)}><Icon name="clock" size={13}/>{text}</span>;
}

function QueuePriority({c}: {c: Row}) {
  const urgent = needsUrgentReview(c);
  const urgentDue = rows(c.escalations).find(item => !item.disposition && !item.acknowledged_at)?.due_at;
  return (
    <div className="care-priority">
      {c.urgent && (
        <Badge tone={urgent ? 'danger' : 'neutral'}>
          <Icon name={urgent ? 'alert-circle' : 'shield'} size={12} />
          {urgent ? 'Trusted urgent flag' : 'Trusted flag · disposition recorded'}
        </Badge>
      )}
      {(!c.urgent || urgentDue || c.due_at) && <SlaChip due={urgentDue || c.due_at} now={c.now}/>}
      {overdue(c) && <small className="cell-note danger-text">Overdue follow-up</small>}
    </div>
  );
}

function WorklistTable({cases}: {cases: Row[]}) {
  return (
    <>
      <div className="table-scroll care-table-wrap">
        <table className="case-table care-case-table">
          <thead><tr>
            <th>Patient / episode</th><th>Current stage</th><th>Next action</th>
            <th>Accountable owner</th><th>Due / priority</th><th><span className="sr-only">Open case</span></th>
          </tr></thead>
          <tbody>{cases.map(c => (
            <tr key={c.id} className={needsUrgentReview(c) ? 'care-row-urgent' : ''}>
              <td>
                <Link href={'/cases/' + c.id} className="patient-link">
                  <PatientAvatar name={c.patient_name} />
                  <span><strong>{c.patient_name || c.patient_id}</strong><small>{c.id} · Result v{c.result_version}</small></span>
                </Link>
              </td>
              <td className="care-stage-cell">
                <StateBadge state={c.quarantine_reason ? 'blocked' : c.disposition} />
                <span className="care-stage-description">{label(c.phase)}</span>
                {c.quarantine_reason && <small className="cell-note">{label(c.quarantine_reason)}</small>}
              </td>
              <td className="next-action">
                {c.next_action || 'Review outstanding follow-up'}
                {c.delay_reasons?.length > 0 && <small className="cell-note care-barrier-note">
                  <Icon name="info" size={12} />{c.delay_reasons.map((reason: string) => label(reason)).join(' · ')}
                </small>}
              </td>
              <td><span className="care-owner"><span className="owner-dot" />{label(c.owner)}</span><small className="cell-note">Backup: {label(c.backup_queue)}</small></td>
              <td><QueuePriority c={c} /></td>
              <td><Link className="icon-link care-open-case" aria-label={'Open ' + c.patient_name} href={'/cases/' + c.id}><Icon name="arrow-up-right" size={18} /></Link></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="care-mobile-queue">
        {cases.map(c => (
          <article className="care-mobile-case" key={c.id}>
            <div className="care-mobile-case-heading">
              <Link href={'/cases/' + c.id} className="patient-link">
                <PatientAvatar name={c.patient_name} />
                <span><strong>{c.patient_name || c.patient_id}</strong><small>{c.id}</small></span>
              </Link>
              <StateBadge state={c.quarantine_reason ? 'blocked' : c.disposition} />
            </div>
            <p className="care-mobile-next">{c.next_action || 'Review outstanding follow-up'}</p>
            <div className="care-mobile-case-footer"><span><Icon name="users" size={14} />{label(c.owner)}</span><QueuePriority c={c} /></div>
            <MilestoneProgress c={c} compact />
            <Link className="care-mobile-case-link" href={'/cases/' + c.id}>View care journey<Icon name="arrow-right" size={15} /></Link>
          </article>
        ))}
      </div>
    </>
  );
}

const BOARD_GROUPS = [
  {id: 'review', label: 'Review & reconciliation', icon: 'shield', description: 'Trusted flags and source blocks'},
  {id: 'team', label: 'Patient & team follow-up', icon: 'message-circle', description: 'Communication and owned next steps'},
  {id: 'service', label: 'Services & source evidence', icon: 'network', description: 'Current referral, visit or evidence work'},
  {id: 'decision', label: 'Recorded decisions', icon: 'file-check', description: 'Review the outcome and remaining need'},
] as const;

function currentFocusTask(c: Row) {
  // Mirrors the API's next-action ordering; the board never advances a milestone.
  return [...rows(c.tasks)].filter(task => !['completed', 'cancelled'].includes(task.status))
    .sort((a, b) => String(a.due_at || '').localeCompare(String(b.due_at || '')))[0];
}

function boardGroup(c: Row): string {
  if (c.quarantine_reason || needsUrgentReview(c)) return 'review';
  if (c.disposition && c.disposition !== 'open') return 'decision';
  const type = String(currentFocusTask(c)?.type || '');
  const service = ['referral', 'appointment', 'attendance', 'investigation', 'reviewed_outcome',
    'patient_updated', 'treatment_initiated', 'surveillance_plan', 'evidence_review'];
  return service.some(kind => type === kind || type.startsWith(kind + ':') || type.startsWith(kind + '_')) ? 'service' : 'team';
}

function JourneyBoard({cases}: {cases: Row[]}) {
  const reduced = useReducedMotion();
  return <div className="care-board" aria-label="Cases grouped by current focus">
    {BOARD_GROUPS.map(group => {
      const items = cases.filter(c => boardGroup(c) === group.id);
      return <section className={'care-board-lane care-board-' + group.id} key={group.id} aria-labelledby={'board-lane-' + group.id}>
        <header className="care-board-lane-heading"><span className="care-board-lane-icon"><Icon name={group.icon} size={17}/></span>
          <div><h3 id={'board-lane-' + group.id}>{group.label}</h3><p>{group.description}</p></div><span className="care-board-count">{items.length}</span>
        </header>
        <div className="care-board-cases" tabIndex={items.length ? 0 : undefined} aria-label={group.label + ' cases'}>
          <AnimatePresence initial={false}>
            {items.map(c => {
              const focus = currentFocusTask(c);
              return <motion.article layout={reduced ? false : 'position'} className="care-board-card" key={c.id}
                initial={reduced ? false : {opacity: 0, y: 8}} animate={{opacity: 1, y: 0}} exit={{opacity: 0}}
                transition={{duration: reduced ? 0 : .2}}>
                <div className="care-board-patient"><PatientAvatar name={c.patient_name}/><div><strong>{c.patient_name || c.patient_id}</strong><small>{c.id} · Result v{c.result_version}</small></div></div>
                <StateBadge state={c.quarantine_reason ? 'blocked' : c.disposition}/>
                <p className="care-board-next">{c.next_action || 'Review outstanding follow-up'}</p>
                {c.quarantine_reason && <p className="care-board-reason"><Icon name="lock" size={12}/>{label(c.quarantine_reason)}</p>}
                {c.residual_need && c.disposition !== 'open' && <p className="care-board-reason"><Icon name="info" size={12}/>Remaining care need stays open</p>}
                <dl className="care-board-accountability"><div><dt>Episode owner</dt><dd>{label(c.owner)}</dd></div>
                  {focus?.assignee && focus.assignee !== c.owner && <div><dt>Next action team</dt><dd>{label(focus.assignee)}</dd></div>}
                </dl>
                <MilestoneProgress c={c} compact/>
                <div className="care-board-card-footer"><QueuePriority c={c}/><Link href={'/cases/' + c.id} aria-label={'Open ' + c.patient_name} className="care-board-open">View journey<Icon name="arrow-up-right" size={14}/></Link></div>
              </motion.article>;
            })}
          </AnimatePresence>
          {!items.length && <div className="care-board-empty"><Icon name={group.icon} size={23}/><strong>No cases in this view</strong><span>Cases appear here when their recorded focus matches.</span></div>}
        </div>
      </section>;
    })}
  </div>;
}

export function Worklist() {
  const {user} = useSession();
  const {data, error, loading, load} = useResource<Row[]>('/cases');
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [view, setView] = useState<'list' | 'board'>('list');
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get('filter');
    if (requested && FILTERS.some(([value]) => value === requested)) setFilter(requested);
  }, []);
  const reduced = useReducedMotion();
  const soonestDue = (c: Row) => c.due_at ? Date.parse(c.due_at) : Infinity;
  const cases = [...rows(data)].sort((a, b) =>
    Number(needsUrgentReview(b)) - Number(needsUrgentReview(a)) ||
    Number(!!overdue(b)) - Number(!!overdue(a)) ||
    soonestDue(a) - soonestDue(b) || 0);
  const filtered = cases.filter(c =>
    (c.patient_name + ' ' + c.id + ' ' + c.owner).toLowerCase().includes(search.toLowerCase()) &&
    matchesFilter(c, filter),
  );
  function selectSummary(value: string) {
    setFilter(value); setSearch('');
    document.querySelector('.care-queue-panel')?.scrollIntoView({behavior: reduced ? 'instant' : 'smooth', block: 'start'});
  }
  return (
    <div className="care-worklist">
      <PageHeading eyebrow="CARE NAVIGATION" title="Every case, a clear next step."
        description={'Welcome, ' + user.name.split(' ')[0] + '. Keep screening follow-up moving with shared accountability.'}>
        <button className="button secondary" onClick={load}><Icon name="refresh" size={16} />Refresh</button>
      </PageHeading>
      <LoadState loading={loading} error={error} retry={load} />
      {!loading && !error && <>
        <div className="stat-grid care-worklist-stats">
          <Stat icon="users" label="Actionable episodes" value={cases.length} note="All authorized cases, including exceptions" onClick={() => selectSummary('all')} selected={filter === 'all'} actionLabel="Show all actionable cases"/>
          <Stat icon="git-branch" label="Active follow-up" value={cases.filter(active).length} note="Care still needs coordination" onClick={() => selectSummary('active')} selected={filter === 'active'}/>
          <Stat icon="alert-circle" label="Urgent review" value={cases.filter(needsUrgentReview).length} note="Trusted source flag · human disposition" tone="danger" onClick={() => selectSummary('urgent')} selected={filter === 'urgent'}/>
          <Stat icon="shield" label="Needs reconciliation" value={cases.filter(c => c.quarantine_reason).length} note="Owned identity or pathway review" onClick={() => selectSummary('quarantine')} selected={filter === 'quarantine'} actionLabel="Show cases needing reconciliation"/>
        </div>
        <Panel title="Care worklist" eyebrow="FOCUS ON WHAT NEEDS YOU" className="care-queue-panel" action={<Badge>{filtered.length} cases</Badge>}>
          <div className="queue-toolbar care-queue-toolbar">
            <label className="search-field care-search">
              <span className="sr-only">Search by patient, case or owner</span><Icon name="search" size={18} />
              <input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search patient, case, owner…" />
            </label>
            <div className="care-queue-tools"><div className="care-queue-context"><Icon name="layers" size={15} />{filtered.length} of {cases.length} episodes</div>
              <div className="care-view-switch" role="group" aria-label="Worklist view">
                {([{id: 'list', label: 'List view', icon: 'list'}, {id: 'board', label: 'Journey board', icon: 'layout-dashboard'}] as const).map(item => <button type="button" key={item.id}
                  aria-pressed={view === item.id} onClick={() => setView(item.id)}>
                  {view === item.id && <motion.span className="care-view-active" layoutId="care-worklist-view" transition={{duration: reduced ? 0 : .22}}/>}
                  <Icon name={item.icon} size={15}/><span>{item.label}</span>
                </button>)}
              </div>
            </div>
          </div>
          <div className="filter-tabs care-filter-tabs" aria-label="Filter cases">
            {FILTERS.map(([value, label]) => (
              <button key={value} className={filter === value ? 'selected' : ''} onClick={() => setFilter(value)} aria-pressed={filter === value} aria-label={label}>
                {value === 'urgent' && <Icon name="alert-circle" size={13} />}{label}
                <span aria-hidden="true">{cases.filter(c => matchesFilter(c, value)).length}</span>
              </button>
            ))}
          </div>
          <p className="sr-only" role="status" aria-live="polite">{filtered.length} cases shown in {view === 'board' ? 'journey board' : 'list view'}.</p>
          {view === 'board' && <div className="care-board-explainer"><Icon name="git-branch" size={16}/><p>Grouped by the recorded decision or current next work item. Milestones remain independent.</p></div>}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={view} initial={reduced ? false : {opacity: 0, y: 8}} animate={{opacity: 1, y: 0}} exit={{opacity: 0, y: reduced ? 0 : -5}} transition={{duration: reduced ? 0 : .18}}>
              {filtered.length ? view === 'board' ? <JourneyBoard cases={filtered}/> : <WorklistTable cases={filtered}/> : (
                <Empty title="No matching cases">Try another filter or search. Every unresolved case remains in the full episode denominator.</Empty>
              )}
            </motion.div>
          </AnimatePresence>
          {['navigator', 'clinician'].includes(user.role) && <FileIntake refresh={load} />}
        </Panel>
        <div className="quiet-note care-policy-note"><Icon name="shield" size={15} />Deadlines come from the versioned demonstration policy. An alert, a booked visit, and completed care are recorded separately.</div>
      </>}
    </div>
  );
}

const CASE_TABS = [
  {value: 'journey', label: 'Journey & evidence', icon: 'git-branch'},
  {value: 'consultations', label: 'Consultations', icon: 'message-circle'},
  {value: 'coordination', label: 'Coordination', icon: 'network'},
  {value: 'activity', label: 'Activity & provenance', icon: 'activity'},
];

function CaseStatusNotices({c}: {c: CareCase}) {
  return <>
    {needsUrgentReview(c) && <div className="notice error care-case-notice">
      <Icon name="alert-circle" size={21} />
      <div><strong>Trusted urgent signal · clinician review required</strong><span>Staff acknowledgement and clinical disposition are separate. Routine progression pauses until the required disposition.</span></div>
    </div>}
    {c.urgent && !needsUrgentReview(c) && <div className="notice subtle care-case-notice">
      <Icon name="shield" size={21} />
      <div><strong>Trusted urgent source flag · clinician disposition recorded</strong><span>The source flag is preserved. Review the recorded human decision and current next action below.</span></div>
    </div>}
    {c.quarantine_reason && <div className="notice warning care-case-notice">
      <Icon name="lock" size={21} />
      <div><strong>Progression blocked: {human(c.quarantine_reason)}</strong><span>The {human(c.owner)} team remains accountable. Use authorized reconciliation with source evidence.</span></div>
    </div>}
  </>;
}

function CaseOverview({c, closure}: {c: CareCase; closure: Row | null}) {
  return (
    <div className="case-summary care-case-summary" id="case-overview" tabIndex={-1}>
      <div><span className="care-summary-icon"><Icon name="users" size={20} /></span><div><small>ACCOUNTABLE EPISODE OWNER</small><strong>{label(c.owner)}</strong><span>Backup: {label(c.backup_queue)}</span></div></div>
      <div><span className="care-summary-icon"><Icon name="arrow-right" size={20} /></span><div><small>NEXT ACTION</small><strong>{c.next_action || 'Review required follow-up'}</strong><span><Icon name="clock" size={12} />Due {when(c.due_at)}</span></div></div>
      <div><span className="care-summary-icon"><Icon name="target" size={20} /></span><div><small>CARE ENDPOINT</small><strong>{label(closure?.endpoint || 'Required diagnostic follow-up')}</strong><span>{c.residual_need ? 'Residual care need remains' : 'See current evidence checklist'}</span></div></div>
    </div>
  );
}

function MilestoneWhen({milestone, now}: {milestone: Row; now: unknown}) {
  const target = typeof milestone.target_hours === 'number' ? duration(milestone.target_hours) + ' service level from intake' : undefined;
  if (milestone.status === 'completed') {
    if (!milestone.completed_at) return null;
    const sinceIssue = typeof milestone.hours_from_issue === 'number' ? ' · ' + duration(milestone.hours_from_issue) + ' after the result' : '';
    return <p className="care-milestone-when" title={target}>Completed {when(milestone.completed_at)}{sinceIssue}</p>;
  }
  if (!milestone.due_at) return null;
  const owner = milestone.assignee ? ' · ' + label(milestone.assignee) : '';
  const due = relative(milestone.due_at, now);
  if (milestone.late || due.endsWith(' ago')) {
    return <p className="care-milestone-when danger-text" title={target}>{due.endsWith(' ago') ? 'Overdue by ' + due.slice(0, -4) : 'Overdue since ' + when(milestone.due_at)}{owner}</p>;
  }
  return <p className="care-milestone-when" title={target}>Due {when(milestone.due_at)}{due ? ' · ' + due : ''}{owner}</p>;
}

function JourneyMilestones({c}: {c: CareCase}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const reduced = useReducedMotion();
  // Display order does not constrain the independent backend milestone states.
  const order = ['result_ingested','identity','notification','acknowledgement','understanding','referral','appointment','attendance','investigation','reviewed_outcome','patient_updated'];
  const rank = (type: string) => order.includes(type) ? order.indexOf(type) : order.length;
  const recorded = rows(c.milestones);
  const timeline = rows(c.timeline);
  const recordedByType = new Map(recorded.map(milestone => [milestone.type, milestone]));
  const scheduledTypes = new Set(timeline.map(milestone => milestone.type));
  const milestones = timeline.length
    ? [...timeline.map(milestone => ({...milestone, ...recordedByType.get(milestone.type)})), ...recorded.filter(milestone => !scheduledTypes.has(milestone.type))]
    : [...recorded].sort((a, b) => rank(a.type) - rank(b.type));
  const visible = milestones.filter(m => filter === 'all' || filter === 'required' && m.required || filter === 'documented' && m.status === 'completed');
  const records = [...rows(c.evidence), ...rows(c.communications), ...rows(c.consultations), ...rows(c.handoffs), ...rows(c.appointments)];
  const journey = c.journey;
  const issued = journey?.issued_at ? new Intl.DateTimeFormat('en-GB', {day: 'numeric', month: 'short', timeZone: 'Asia/Dubai'}).format(new Date(journey.issued_at)) : '';
  const documented = milestones.filter(milestone => milestone.status === 'completed').length;
  return (
    <Panel id="case-milestones" title="Result-to-care timeline" eyebrow="INDEPENDENT MILESTONES" className="care-journey-panel" action={<span className="care-live-label"><span />Shared record</span>}>
      <p className="panel-intro">Communication, consultation, and referral can move in parallel. Each completed step needs its own evidence.</p>
      {issued && typeof journey.age_hours === 'number' && <div className="care-timeline-summary">
        <span><Icon name="calendar" size={15}/>Result issued {issued}</span>
        <span>Day {Math.max(1, Math.floor(journey.age_hours / 24))}</span>
        <span>{documented} of {milestones.length} steps documented</span>
        {journey.closed_at && typeof journey.total_hours === 'number'
          ? <strong>Result to documented closure in {duration(journey.total_hours)}</strong>
          : <strong>Open for {duration(journey.age_hours)}</strong>}
      </div>}
      <MilestoneProgress c={c} />
      <div className="care-journey-tools"><div className="care-milestone-filters" role="group" aria-label="Filter milestones">
        {[['all', 'All milestones'], ['required', 'Required milestones'], ['documented', 'Documented milestones']].map(([value, label]) => <button type="button" key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}
      </div><span>{visible.length} of {milestones.length}</span></div>
      <p className="care-inspect-hint"><Icon name="mouse-pointer-2" size={13}/>Select a milestone to inspect its recorded state and linked references.</p>
      <div className="milestone-list care-milestone-list">
        {visible.map(milestone => {
          const index = milestones.indexOf(milestone);
          const expanded = selected === milestone.type;
          const milestoneName = label(milestone.type);
          const related = rows(c.tasks).filter(task => task.type === milestone.type);
          return <div className={'milestone care-milestone ' + (milestone.status === 'completed' ? 'complete' : '') + (expanded ? ' care-milestone-selected' : '')} key={milestone.id || milestone.type}>
            <div className="milestone-marker" aria-hidden="true">{milestone.status === 'completed' ? <Icon name="check" size={16} /> : String(index + 1).padStart(2, '0')}</div>
            <div className="milestone-main">
              <div><h3><button type="button" className="care-milestone-select care-milestone-selector" aria-label={'Inspect ' + milestoneName + ' milestone'} aria-expanded={expanded}
                aria-controls={'milestone-detail-' + c.id + '-' + milestone.type} onClick={() => setSelected(expanded ? null : milestone.type)}>
                {milestoneName}<Icon name="chevron-down" size={14}/></button></h3><StateBadge state={milestone.status} /></div>
              <p>{milestone.required ? 'Required for this pathway' : 'Conditional milestone'}{milestone.evidence_ids?.length ? ' · ' + milestone.evidence_ids.length + ' linked records' : ''}</p>
              <MilestoneWhen milestone={milestone} now={journey?.now || c.now}/>
              <AnimatePresence initial={false}>
                {expanded && <motion.div id={'milestone-detail-' + c.id + '-' + milestone.type} className="care-milestone-inspector" role="region" aria-label={milestoneName + ' milestone details'}
                  initial={reduced ? false : {height: 0, opacity: 0}} animate={{height: 'auto', opacity: 1}} exit={{height: 0, opacity: 0}} transition={{duration: reduced ? 0 : .2}}>
                  <div className="care-inspector-inner"><div className="care-inspector-heading"><Icon name={milestone.status === 'completed' ? 'file-check' : 'clipboard-check'} size={18}/><strong>Recorded milestone</strong><span>Result v{c.result_version}</span></div>
                    <dl className="care-inspector-facts"><div><dt>Recorded state</dt><dd>{human(milestone.status)}</dd></div><div><dt>Pathway requirement</dt><dd>{milestone.required ? 'Required' : 'Conditional'}</dd></div></dl>
                    <p>{milestone.status === 'completed' ? 'This milestone is documented in the shared record. Other required milestones retain their own states.' : 'This milestone still needs its own supporting action or evidence. Selecting it does not change the care record.'}</p>
                    {milestone.evidence_ids?.length ? <div className="care-inspector-records"><small>LINKED REFERENCES</small>{milestone.evidence_ids.map((id: string) => {
                      const record = records.find(item => item.id === id);
                      const sourceEvidence = rows(c.evidence).some(item => item.id === id);
                      return <div key={id}><Icon name={sourceEvidence ? 'file-text' : 'link'} size={15}/><div><strong>{record ? human(record.type || record.channel || record.scope || 'Recorded event') : 'Recorded reference'}</strong>
                        <code>{record?.reference || id}</code>{record?.verification && <span>{human(record.verification)} · {human(record.status)}</span>}</div>
                        {sourceEvidence && <a href={'#evidence-' + id} aria-label={'Find source evidence ' + id}><Icon name="arrow-down-right" size={16}/><span>View evidence</span></a>}
                      </div>;
                    })}</div> : <p className="care-inspector-empty">This state comes from the recorded episode. No separate linked reference is returned for this milestone.</p>}
                    {related.length > 0 && <div className="care-inspector-tasks"><small>ASSIGNED WORK</small>{related.map(task => <div key={task.id}><span>{task.next_action}<small>{label(task.assignee)} · {when(task.due_at)}</small></span><StateBadge state={task.status}/></div>)}</div>}
                  </div>
                </motion.div>}
              </AnimatePresence>
            </div>
          </div>;
        })}
        {!visible.length && <Empty title="No milestones match this view">Choose another milestone filter to see the independent recorded states.</Empty>}
      </div>
    </Panel>
  );
}

function ReferralHistory({c, command, canManage}: {c: CareCase; command: Command; canManage: boolean}) {
  return (
    <Panel id="case-referrals" title="Referral & ownership" className="care-referral-panel">
      <p className="panel-intro">The sending team keeps accountability until an authorized destination explicitly accepts the proposed scope.</p>
      {rows(c.handoffs).length ? rows(c.handoffs).map(handoff => (
        <div className="record-row care-handoff" key={handoff.id}>
          <span className="care-record-icon"><Icon name="building" size={19} /></span>
          <div className="care-handoff-content"><strong>{human(handoff.receiver)}</strong><p>{human(handoff.scope)} transfer · {handoff.id}</p>{handoff.reason && <small>{handoff.reason}</small>}</div>
          <StateBadge state={handoff.status} />
        </div>
      )) : <Empty title="No referral proposed" />}
      {canManage && <Disclosure title="Propose a referral">
        <ActionForm label="Propose referral" onSubmit={data => command('/handoffs', {...data, case_id: c.id})}>
          <Field label="Receiving provider" name="receiver" defaultValue="provider-a" options={['provider-a', 'provider-b']} />
          <Field label="Handoff scope" name="scope" defaultValue="task" options={[{value: 'task', label: 'Task only'}, {value: 'episode', label: 'Episode accountability'}]} />
          <Field label="Referral reason" name="reason" type="textarea" />
        </ActionForm>
      </Disclosure>}
    </Panel>
  );
}

function CommunicationHistory({c}: {c: CareCase}) {
  return (
    <Panel title="Communication ledger">
      {rows(c.communications).length ? rows(c.communications).map(message => (
        <div className="message-record care-message-record" key={message.id}>
          <div className="record-row"><span className="care-record-icon"><Icon name="mail" size={18} /></span><strong>{human(message.channel)} · {message.language?.toUpperCase()}</strong><StateBadge state={message.delivery_status} /></div>
          <p>{message.body || 'Minimal care-team notification'}</p>
          <div className="inline-meta"><span>Acknowledged: {message.acknowledged_at ? when(message.acknowledged_at) : 'Waiting'}</span><span>Understanding: {human(message.understanding || 'unknown')}</span></div>
        </div>
      )) : <Empty title="No notification recorded" />}
    </Panel>
  );
}

function AuditHistory({c}: {c: CareCase}) {
  return (
    <Panel id="case-activity" title="Audit & ownership history" className="care-audit-panel">
      <div className="audit-list care-audit-list">
        {rows(c.audit).length ? rows(c.audit).map((event, index) => (
          <div key={event.id || index}><span className="audit-dot" /><div>
            <strong>{human(event.event_type || event.action || event.type)}</strong>
            <p>{human(event.actor || event.actor_id)} · {when(event.created_at || event.timestamp || event.occurred_at)}</p>
            <small>{event.summary || event.reason || 'Case version ' + (event.after_version || event.case_version || event.version || 'recorded')}</small>
          </div></div>
        )) : <Empty title="No audit entries returned" />}
      </div>
      <div className="provenance care-case-provenance">
        <span><Icon name="building" size={14} />Source organization: {human(c.source_organization)}</span>
        <span>Order: {c.order_id}</span><span>Current result: v{c.result_version} · Case: v{c.version}</span>
      </div>
    </Panel>
  );
}

function ClosureReview({c, closure, clinical, command}: {c: CareCase; closure: Row | null; clinical: boolean; command: Command}) {
  return (
    <Panel id="case-closure" title="Closure evidence check" eyebrow="DETERMINISTIC SAFETY CHECK" className="care-closure-panel">
      <div className={'closure-status ' + (closure?.allowed ? 'ready' : '')}>
        <span><Icon name={closure?.allowed ? 'check-circle' : 'clipboard-check'} size={21} /></span>
        <div><strong>{closure?.allowed ? 'Evidence requirements satisfied' : 'More evidence is needed'}</strong><small>{closure?.allowed ? 'Ready for an authorized review' : 'Required work remains visible'}</small></div>
      </div>
      {rows(closure?.missing).length > 0 ? (
        <ul className="checklist closure-checklist care-closure-checklist">{closure?.missing.map((missing: string) => <li key={missing}><Icon name="clock" size={14} /><span>{label(missing)}</span></li>)}</ul>
      ) : closure?.missing?.map((missing: string) => <p key={missing}>{label(missing)}</p>)}
      <p className="microcopy care-closure-policy"><Icon name="shield" size={14} />Colorectal FIT pathway, policy v1 (demonstration). Only an authorized clinician can close, and only with this evidence.</p>
      {clinical && <Disclosure title="Record authorized disposition">
        <ActionForm label="Record disposition" onSubmit={data => command('/cases/' + c.id + '/dispositions', {...data, residual_need: data.residual_need || ''})}>
          <Field label="Disposition category" name="category" defaultValue="completed_required_care" options={['completed_required_care', 'clinically_resolved', 'accepted_transfer_open', 'informed_decline', 'unable_to_contact', 'other_exception']} />
          <Field label="Clinical rationale" name="reason" type="textarea" />
          <Field label="Remaining care need (required for exceptions)" name="residual_need" type="textarea" required={false} />
        </ActionForm>
      </Disclosure>}
    </Panel>
  );
}

export function CaseDetail({id}: {id: string}) {
  const {user} = useSession();
  const {data: c, error, loading, load} = useResource<CareCase>('/cases/' + id);
  const {data: closure, load: loadClosure} = useResource<Row>(user.role === 'specialist' ? null : '/cases/' + id + '/closure-check');
  const [tab, setTab] = useState('journey');
  const reduced = useReducedMotion();
  const targetHash = useRef('');
  const [linkVersion, setLinkVersion] = useState(0);

  useEffect(() => {
    function readLink(href = window.location.href) {
      const url = new URL(href, window.location.origin);
      if (url.pathname !== '/cases/' + encodeURIComponent(id)) return;
      let hash = '';
      try {hash = decodeURIComponent(url.hash.slice(1));} catch {}
      const requested = url.searchParams.get('tab');
      const inferred = ['case-referrals', 'case-appointments', 'case-tasks'].includes(hash) ? 'coordination' : hash === 'case-consultations' ? 'consultations' : hash === 'case-activity' ? 'activity' : 'journey';
      setTab(CASE_TABS.some(item => item.value === requested) ? requested! : inferred);
      targetHash.current = hash;
      setLinkVersion(value => value + 1);
    }
    const locationChanged = () => readLink();
    const recordOpened = (event: Event) => {
      const href = (event as CustomEvent<{href?: string}>).detail?.href;
      if (href) readLink(href);
    };
    readLink();
    window.addEventListener('popstate', locationChanged);
    window.addEventListener('hashchange', locationChanged);
    window.addEventListener('suhail:open-record', recordOpened);
    return () => {window.removeEventListener('popstate', locationChanged); window.removeEventListener('hashchange', locationChanged); window.removeEventListener('suhail:open-record', recordOpened);};
  }, [id]);

  useEffect(() => {
    if (!c || !targetHash.current) return;
    const timeout = window.setTimeout(() => {
      const element = document.getElementById(targetHash.current);
      if (element) {if (!element.hasAttribute('tabindex')) element.setAttribute('tabindex', '-1'); element.scrollIntoView({block: 'start', behavior: 'instant'}); element.focus({preventScroll: true}); targetHash.current = '';}
    }, reduced ? 0 : 230);
    return () => window.clearTimeout(timeout);
  }, [c, tab, linkVersion, reduced]);

  function selectTab(value: string) {
    targetHash.current = '';
    setTab(value);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', value); url.hash = '';
    window.history.replaceState(window.history.state, '', url.pathname + url.search);
  }

  async function command(path: string, body: Row = {}) {
    if (!c) return;
    await api(path, {...envelope(c.version), ...body});
    await Promise.all([load(), loadClosure()]);
  }

  function tabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % CASE_TABS.length;
    else if (event.key === 'ArrowLeft') next = (index + CASE_TABS.length - 1) % CASE_TABS.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = CASE_TABS.length - 1;
    else return;
    event.preventDefault();
    selectTab(CASE_TABS[next].value);
    document.getElementById('care-tab-' + id + '-' + CASE_TABS[next].value)?.focus();
  }

  if (loading || error || !c) return <LoadState loading={loading} error={error} retry={load} />;
  const clinical = user.role === 'clinician';
  const coord = ['navigator', 'clinician'].includes(user.role);

  return (
    <div className="care-case">
      <Link className="back-link care-back-link" href="/worklist"><Icon name="arrow-left" size={15} />Care worklist</Link>
      <div className="care-patient-header">
        <PatientAvatar name={c.patient_name} large />
        <PageHeading eyebrow={'CASE JOURNEY / ' + c.id} title={c.patient_name}
          description={'Colorectal screening follow-up · ' + c.patient_id + ' · Source result v' + c.result_version}>
          <StateBadge state={c.disposition} />
          <button className="button secondary" onClick={async () => {await load(); await loadClosure();}}><Icon name="refresh" size={16} />Refresh</button>
        </PageHeading>
      </div>
      <div className="care-source-strip">
        <span><Icon name="building" size={14} />{human(c.source_organization)}</span>
        <span><Icon name="file-text" size={14} />Order {c.order_id}</span>
        <span><Icon name="clock" size={14} />Issued {when(c.issued_at)}</span>
        <span className="care-source-version"><Icon name="shield" size={13} />Case version {c.version}</span>
      </div>
      <CaseStatusNotices c={c} />
      <CaseOverview c={c} closure={closure} />
      <div className="section-tabs care-section-tabs" role="tablist" aria-label="Case sections">
        {CASE_TABS.map((item, index) => (
          <button key={item.value} id={'care-tab-' + id + '-' + item.value} role="tab"
            aria-selected={tab === item.value} aria-controls={'care-panel-' + id}
            tabIndex={tab === item.value ? 0 : -1} onClick={() => selectTab(item.value)}
            onKeyDown={event => tabKey(event, index)}>
            <Icon name={item.icon} size={17} />{item.label}
            {item.value === 'consultations' && c.consultations?.length > 0 && <span>{c.consultations.length}</span>}
          </button>
        ))}
      </div>
      <div className="case-columns care-case-columns">
        <motion.div key={tab} className="case-primary" id={'care-panel-' + id} role="tabpanel"
          aria-labelledby={'care-tab-' + id + '-' + tab} tabIndex={0}
          initial={reduced ? false : {opacity: 0, y: 8}} animate={{opacity: 1, y: 0}} transition={{duration: reduced ? 0 : .2}}>
          {tab === 'journey' && <>
            <JourneyMilestones c={c} />
            <Panel id="case-evidence" title="Source evidence" eyebrow="LINKED, REVIEWABLE RECORDS" className="care-evidence-panel" action={<Badge>{rows(c.evidence).length} records</Badge>}>
              <EvidenceList c={c} command={command} canVerify={clinical} canReadSource={['clinician', 'specialist'].includes(user.role)} />
              {coord && <Disclosure title="Link supporting evidence"><EvidenceForm c={c} onSubmit={data => command('/cases/' + c.id + '/evidence', data)} /></Disclosure>}
            </Panel>
          </>}
          {tab === 'consultations' && <>
            <Panel id="case-consultations" title="Consultation threads" eyebrow="HUMAN QUESTIONS. HUMAN REPLIES.">
              <ConsultationList c={c} command={command} role={user.role} />
            </Panel>
            {coord && <Panel title="Request a specialist consultation">
              <ActionForm label="Assign consultation" onSubmit={data => command('/consultations', {...data, case_id: c.id, type: 'clinician_to_specialist'})}>
                <Field label="Question for the specialist" name="question" type="textarea" />
                <Field label="Receiving specialist" name="recipient" defaultValue="specialist" options={[{value: 'specialist', label: 'Colorectal specialist'}]} />
              </ActionForm>
              <p className="microcopy">This creates assigned work with a service window. A reply must come from an authenticated specialist.</p>
            </Panel>}
          </>}
          {tab === 'coordination' && <>
            <ReferralHistory c={c} command={command} canManage={coord} />
            <Panel id="case-appointments" title="Appointments & attendance">
              <AppointmentList appointments={rows(c.appointments)} />
              <p className="microcopy">Booking, attendance, completed investigation, and reviewed outcomes are separate records.</p>
            </Panel>
            <Panel id="case-tasks" title="Assigned follow-up">
              <TaskList c={c} command={command} canManage={coord} />
              {coord && <Disclosure title="Create owned follow-up work">
                <ActionForm label="Create task" onSubmit={data => command('/cases/' + c.id + '/tasks', {...data, required: false})}>
                  <Field label="Task type" name="type" defaultValue="navigation_followup" />
                  <Field label="Assigned team" name="assignee" defaultValue={c.owner} />
                  <Field label="Next action" name="next_action" />
                  <Field label="Reason / delay" name="reason" type="textarea" />
                </ActionForm>
              </Disclosure>}
            </Panel>
          </>}
          {tab === 'activity' && <><CommunicationHistory c={c} /><AuditHistory c={c} /></>}
        </motion.div>
        <aside className="case-aside care-case-aside">
          <Panel id="case-next-action" title="Next best action" eyebrow="COORDINATION DESK" className="care-next-action-panel">
            <div className="care-next-action-copy"><span><Icon name="arrow-up-right" size={20} /></span><p>{c.next_action || 'Review open evidence and required follow-up.'}</p></div>
            {coord && <NotificationForm key={c.id + ':' + c.language} c={c} command={command}/>}
            <p className="microcopy">Delivery uses the visible local outbox. No real patient is contacted.</p>
            <AssistantDraft c={c} role={user.role} />
          </Panel>
          {c.quarantine_reason && coord && <Panel title="Authorized reconciliation" className="care-reconciliation-panel">
            <ActionForm label="Reconcile with evidence" onSubmit={data => command('/cases/' + c.id + '/reconciliation', {...data, identity_verified: true, pathway: 'colorectal-fit'})}>
              <Field label="Verified source reference" name="source_reference" />
              <Field label="Reconciliation reason" name="reason" type="textarea" />
            </ActionForm>
          </Panel>}
          {rows(c.escalations).length > 0 && <Panel title="Urgent review" className="care-urgent-panel"><EscalationList c={c} command={command} clinical={clinical} /></Panel>}
          {user.role !== 'specialist' && <ClosureReview c={c} closure={closure} clinical={clinical} command={command} />}
        </aside>
      </div>
    </div>
  );
}

function NotificationForm({c, command}: {c: CareCase; command: Command}) {
  const [language, setLanguage] = useState(c.language === 'ar' ? 'ar' : 'en');
  const body = c.notification_templates?.[language];
  return <ActionForm label="Send approved notification" onSubmit={data => command('/communications', {...data, case_id: c.id})}>
    <div className="care-form-columns">
      <label className="field"><span>Language</span>
        <select aria-label="Language" name="language" value={language} onChange={event => setLanguage(event.target.value === 'ar' ? 'ar' : 'en')}>
          <option value="en">English</option><option value="ar">العربية</option>
        </select>
      </label>
      <Field label="Channel" name="channel" defaultValue="portal" options={[{value: 'portal', label: 'Local notification simulator'}]} />
    </div>
    {body && <div className="care-notification-preview" aria-live="polite"><small>Message preview</small>
      <blockquote lang={language} dir={language === 'ar' ? 'rtl' : 'ltr'}>{body}</blockquote>
    </div>}
  </ActionForm>;
}

export function EvidenceForm({c, onSubmit}: {c: CareCase | Row; onSubmit: (data: Row) => Promise<unknown>}) {
  return (
    <ActionForm label="Link evidence for verification" className="care-evidence-form" onSubmit={data => {
      if (!data.document_text) delete data.document_text;
      return onSubmit({...data, patient_id: c.patient_id, order_id: c.order_id,
        result_version: c.result_version, requires_onward: data.requires_onward === 'true'});
    }}>
      <div className="care-form-columns">
        <Field name="type" label="Evidence type" defaultValue="investigation" options={['investigation', 'reviewed_outcome', 'patient_updated', 'treatment_initiated', 'surveillance_plan', 'outreach', 'exception_review']} />
        <Field name="reference" label="Document / resource reference" placeholder="Synthetic Procedure or signed record reference" />
      </div>
      <Field name="document_text" label="Synthetic source document" type="textarea" required={false} help="Required for manual uploads (at least 10 characters). The document is retained for clinician verification; a reference alone cannot establish evidence." />
      <Field name="requires_onward" label="Does this outcome require onward care?" defaultValue="false" options={[{value: 'false', label: 'No / not applicable'}, {value: 'true', label: 'Yes — treatment endpoint required'}]} />
      <div className="care-form-columns">
        <Field name="plan_owner" label="Surveillance plan owner" required={false} />
        <Field name="recall_date" label="Surveillance recall date" type="date" required={false} />
      </div>
      <p className="microcopy">An upload is pending evidence. An authorized clinician must verify its source and patient/order match.</p>
    </ActionForm>
  );
}

export function EvidenceList({c, command, canVerify, canReadSource = false}: {
  c: CareCase; command: Command; canVerify: boolean; canReadSource?: boolean;
}) {
  if (!rows(c.evidence).length) {
    return <Empty title="Evidence is still outstanding">Required source records will appear here. A booked appointment alone cannot satisfy completed care.</Empty>;
  }
  return (
    <div className="care-evidence-list">
      {rows(c.evidence).map(evidence => (
        <div className="evidence-card care-evidence-card" id={'evidence-' + evidence.id} key={evidence.id}>
          <div className="record-row">
            <span className="care-evidence-icon"><Icon name={evidence.verification === 'verified' ? 'file-check' : 'file-text'} size={21} /></span>
            <div className="care-evidence-heading"><strong>{human(evidence.type)}</strong><small>{evidence.id} · Result v{evidence.result_version}</small></div>
            <div className="inline-meta"><StateBadge state={evidence.verification} /><StateBadge state={evidence.status} /></div>
          </div>
          <p className="care-evidence-reference">{evidence.reference}</p>
          <small className="care-evidence-source"><Icon name="building" size={13} />Source: {human(evidence.source)} · {evidence.patient_id} / {evidence.order_id}</small>
          {canReadSource && <SourceReview key={evidence.id + ':' + evidence.status + ':' + evidence.result_version} evidenceId={evidence.id} />}
          {canVerify && ['pending', 'pending_verification', 'unverified'].includes(evidence.verification || evidence.status) && <Disclosure title="Verify or reject evidence">
            <ActionForm label="Record verification" onSubmit={data => command('/evidence/' + evidence.id + '/verification', {...data, verified: data.verified === 'true'})}>
              <Field name="verified" label="Source / matching checks" defaultValue="true" options={[{value: 'true', label: 'Verified correct patient, order and version'}, {value: 'false', label: 'Rejected — matching or source problem'}]} />
              <Field name="reason" label="Verification findings" type="textarea" />
            </ActionForm>
          </Disclosure>}
        </div>
      ))}
    </div>
  );
}

const PROTECTED_TASKS = [
  'result_ingested', 'identity', 'notification', 'acknowledgement', 'understanding',
  'referral', 'appointment', 'attendance', 'investigation', 'reviewed_outcome',
  'patient_updated', 'treatment_initiated', 'surveillance_plan', 'urgent_review',
  'consultation', 'quarantine',
];
const assignmentOptions = [{value: '', label: 'Choose a team'},
  ...teamCodes.map(value => ({value, label: label(value)}))];

function TaskRecord({task, c, command, canManage}: {task: Row; c: CareCase; command: Command; canManage: boolean}) {
  const canAssign = canManage && !['completed', 'cancelled'].includes(task.status);
  const canComplete = canAssign &&
    !PROTECTED_TASKS.includes(task.type) && !task.type.startsWith('consultation:') && !task.type.startsWith('evidence_review:');
  return (
    <div className="task-row care-task-row">
      <div className="record-row">
        <span className={'care-task-check ' + (task.status === 'completed' ? 'is-complete' : '')}><Icon name={task.status === 'completed' ? 'check' : 'clipboard-check'} size={16} /></span>
        <strong>{human(task.type)}</strong><StateBadge state={task.status} />
      </div>
      <p>{task.next_action}</p>
      <div className="care-task-meta"><span><Icon name="users" size={13} />{label(task.assignee)}</span><span><Icon name="clock" size={13} />Due {when(task.due_at)}</span></div>
      {task.type === 'appointment_recovery' && !['completed', 'cancelled'].includes(task.status) && <SlaChip due={task.due_at} now={c.now}/>}
      {task.reason && <small className="care-task-reason">{task.reason}</small>}
      {canAssign && <Disclosure title="Assign">
        <ActionForm label="Save assignment" onSubmit={({assignee}) => command('/cases/' + c.id + '/tasks', {task_id: task.id, assignee})}>
          <Field key={task.assignee} name="assignee" label="Accountable team"
            defaultValue={teamCodes.some(team => team === task.assignee) ? task.assignee : ''} options={assignmentOptions}/>
        </ActionForm>
      </Disclosure>}
      {canComplete && <Disclosure title="Record coordination work">
        <ActionForm label="Update task" onSubmit={data => command('/cases/' + c.id + '/tasks', {...data, task_id: task.id})}>
          <Field name="status" label="Task state" defaultValue="completed" options={['completed', 'in_progress']} />
          <Field name="reason" label="Action taken / outcome" />
        </ActionForm>
      </Disclosure>}
    </div>
  );
}

export function TaskList({c, command, canManage}: {c: CareCase; command: Command; canManage: boolean}) {
  const tasks = rows(c.tasks);
  if (!tasks.length) return <Empty title="No assigned tasks" />;
  const pending = tasks.filter(task => !['completed', 'cancelled'].includes(task.status));
  const recorded = tasks.filter(task => ['completed', 'cancelled'].includes(task.status));
  return (
    <div className="care-task-groups">
      {[{title: 'Needs attention', items: pending}, {title: 'Recorded work', items: recorded}].filter(group => group.items.length).map(group => (
        <div className="care-task-group" key={group.title}>
          <div className="care-group-heading"><h3>{group.title}</h3><span>{group.items.length}</span></div>
          {group.items.map(task => <TaskRecord key={task.id} task={task} c={c} command={command} canManage={canManage} />)}
        </div>
      ))}
    </div>
  );
}

export function ConsultationList({c, command, role}: {c: CareCase; command: Command; role: string}) {
  if (!rows(c.consultations).length) {
    return <Empty title="No open questions yet">Patient questions and specialist requests become assigned consultation work here.</Empty>;
  }
  return (
    <div className="consultation-list care-consultation-list">
      {rows(c.consultations).map(question => (
        <article key={question.id} className="consultation care-consultation">
          <div className="record-row">
            <Badge><Icon name={question.type === 'patient_to_clinician' ? 'message-circle' : 'stethoscope'} size={13} />{question.type === 'patient_to_clinician' ? 'Patient question' : 'Specialist consultation'}</Badge>
            <StateBadge state={question.status} />
          </div>
          <h3>{question.question}</h3>
          <p className="inline-meta"><span><Icon name="user" size={13} />Assigned to {human(question.recipient)}</span><span><Icon name="clock" size={13} />Due {when(question.due_at)}</span></p>
          {question.reply ? (
            <div className="human-reply care-human-reply">
              <div className="care-reply-author"><span><Icon name="stethoscope" size={16} /></span><small>HUMAN REPLY · {human(question.human_author)}</small></div>
              <p>{question.reply}</p>
              <div className="care-agreed-action"><strong>Agreed next action</strong><p>{question.agreed_action} · Owner: {human(question.action_owner)}</p></div>
            </div>
          ) : <div className="notice subtle care-awaiting-reply"><Icon name="clock" size={15} />Waiting for an authorized human reply.</div>}
          {!question.reply && ((role === 'clinician' && question.type === 'patient_to_clinician') || (role === 'specialist' && question.type === 'clinician_to_specialist')) && (
            <ActionForm label="Send human reply & next action" onSubmit={data => command('/consultations/' + question.id + '/reply', data)}>
              <Field label="Your clinical reply" name="reply" type="textarea" />
              <Field label="Agreed next action" name="agreed_action" />
              <Field label="Accountable action owner" name="action_owner" defaultValue="navigation-team" />
            </ActionForm>
          )}
        </article>
      ))}
    </div>
  );
}

export function AppointmentList({appointments, language = 'en'}: {appointments: Row[]; language?: 'en' | 'ar'}) {
  const ar = language === 'ar';
  const locale = ar ? 'ar-AE' : 'en-GB';
  const statusLabel = (value: string) => ar ? ({
    booked: 'موعد مؤكد', attended: 'تم الحضور', cancelled: 'تم الإلغاء', no_show: 'لم يتم الحضور', no_slots: 'لا تتوفر مواعيد',
  } as Record<string, string>)[value] || human(value) : human(value);
  if (!appointments.length) {
    return <Empty title={ar ? 'لم يتم تأكيد الموعد بعد' : 'Appointment not yet confirmed'}>{ar ? 'سيؤكد الفريق المستقبِل الموعد التالي المتاح.' : 'The receiving team will confirm the next available appointment.'}</Empty>;
  }
  return (
    <div className="care-appointments">
      {appointments.map(appointment => (
        <div className="appointment-card care-appointment-card" key={appointment.id}>
          <div className="record-row">
            <span className="care-record-icon"><Icon name="calendar" size={20} /></span>
            <div><strong>{ar ? label(appointment.provider, 'ar') : human(appointment.provider)}</strong><p>{when(appointment.scheduled_at, locale)}</p></div>
            {ar ? <Badge tone={['cancelled', 'no_show', 'no_slots'].includes(appointment.status) ? 'danger' : appointment.status === 'attended' ? 'success' : 'neutral'}>{statusLabel(appointment.status)}</Badge> : <StateBadge state={appointment.status} />}
          </div>
          <small>{ar ? 'الموعد' : 'Appointment'} {appointment.id}</small>
          {appointment.events?.length > 0 && <div className="inline-meta care-appointment-events">
            {appointment.events.map((event: Row, index: number) => <span key={index}><span className="care-event-dot" />{statusLabel(event.status)} · {when(event.occurred_at, locale)}</span>)}
          </div>}
          {['cancelled', 'no_show', 'no_slots'].includes(appointment.status) && <p className="danger-text">{ar ? 'فريق الرعاية مسؤول عن المتابعة. يحتاج الموعد الجديد إلى تأكيد.' : 'Recovery work remains with the care team. A new appointment needs confirmation.'}</p>}
        </div>
      ))}
    </div>
  );
}

export function EscalationList({c, command, clinical}: {c: CareCase; command: Command; clinical: boolean}) {
  return <>
    {rows(c.escalations).map(escalation => (
      <div className="escalation care-escalation" key={escalation.id}>
        <div className="care-escalation-priority">
          <Badge tone="danger"><Icon name="alert-circle" size={13} />{human(escalation.trigger)}</Badge>
          {!escalation.acknowledged_at && escalation.due_at && <SlaChip due={escalation.due_at} now={c.now}/>}
        </div>
        <div className="care-escalation-route">
          <div><small>Recipient</small><strong>{human(escalation.recipient)}</strong></div>
          <Icon name="arrow-right" size={15} />
          <div><small>Backup</small><strong>{human(escalation.backup || escalation.backup_queue)}</strong></div>
        </div>
        <div className="care-escalation-steps">
          <div><span className={escalation.acknowledged_at ? 'is-recorded' : ''}><Icon name={escalation.acknowledged_at ? 'check' : 'bell'} size={14} /></span><p>Acknowledgement: <strong>{escalation.acknowledged_at ? when(escalation.acknowledged_at) : 'Awaiting staff'}</strong></p></div>
          <div><span className={escalation.disposition ? 'is-recorded' : ''}><Icon name={escalation.disposition ? 'check' : 'stethoscope'} size={14} /></span><p>Disposition: <strong>{human(escalation.disposition || 'Awaiting clinician')}</strong></p></div>
        </div>
        {!escalation.acknowledged_at && <ActionButton onClick={() => command('/escalations/' + escalation.id + '/acknowledge')}>Acknowledge staff alert</ActionButton>}
        {clinical && !escalation.disposition && <ActionForm label="Record clinical disposition" onSubmit={data => command('/escalations/' + escalation.id + '/disposition', data)}>
          <Field label="Clinical decision" name="decision" defaultValue="continue_pathway" options={['continue_pathway', 'urgent_clinical_followup']} />
          <Field label="Disposition rationale" name="reason" type="textarea" />
        </ActionForm>}
      </div>
    ))}
  </>;
}
