"""Permission-filtered read tools and deterministic, source-linked answer rendering.

No user/model text becomes SQL, a file path, a URL, or an application command.
Counts and facts are always rendered from current authorized database records.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote

from sqlalchemy import select

from services.api.config import settings
from services.api.db import Case, Consultation, Handoff, Outbox, now_iso
from services.api.domain import (authorize_case, serialize_case, referral_packet,
    permitted_grant, clock)
from services.api.domain import asdict
from services.agents.retrieval import retrieve, PolicyReviewRequired

ROLES = {'patient', 'navigator', 'clinician', 'specialist', 'receiver_a', 'receiver_b', 'admin'}
STAFF = {'navigator', 'clinician', 'admin'}
DONE = {'completed', 'cancelled', 'not_applicable'}
INTENTS = {'overview', 'episodes', 'requests', 'tasks', 'overdue', 'urgent', 'appointments',
           'evidence', 'consultations', 'ownership', 'patient', 'operations', 'knowledge'}
EPISODE_COUNT = (r'\b(?:how many|number of|count(?: of)?)\s+'
    r'(?:(?:authorized|visible|my|care)\s+)*(?:episodes|cases|patients)\b|'
    r'\b(?:episode|case|patient)\s+count\b|(?:كم|عدد)\s+(?:حالة|حالات|مرضى|المرضى)')
UNSAFE = re.compile(r'(system\s+prompt|api[ _-]?key|\.env\b|password|secret\s+key|'
    r'ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions|'
    r'\b(?:drop\s+table|delete\s+from|execute\s+sql)\b)', re.I)
CLINICAL = re.compile(r'\b(?:diagnos\w*|prescrib\w*|medication|dosage|cure|'
    r'do\s+i\s+have\s+cancer|does\s+\w+\s+have\s+cancer|is\s+this\s+cancer|'
    r'what\s+treatment|should\s+i\s+take|symptom\w*|pain|bleed\w*|bloody|fever|dose|'
    r'dizz\w*|chemotherapy|side\s+effects?)\b|تشخيص|جرعة|هل.*سرطان|دواء|نزيف|ألم', re.I)
WRITE = re.compile(r'^\s*(?:please\s+)?(?:accept|reject|book|cancel|complete|close|'
    r'approve|verify|send|notify|assign|merge|delete|reset|record)\b|^\s*(?:اغلق|احجز|وافق|أرسل)', re.I)


def human(value):
    return str(value if value is not None else 'Not recorded').replace('_', ' ').replace('-', ' ')


def active_task(task):
    return task.get('status') not in DONE


def urgent_review(record):
    escalations = record.get('escalations', [])
    return bool(record.get('urgent') and (not escalations or any(
        item.get('status') == 'care_team_review' or (not item.get('status') and not item.get('disposition'))
        for item in escalations)))


@dataclass
class Scope:
    actor: dict
    records: list[dict]
    packets: list[dict]
    instant: str
    outbox: list[dict] = field(default_factory=list)

    @property
    def ids(self):
        return {record.get('case_id', record.get('id')) for record in self.records}

    @property
    def provider(self):
        return self.actor['role'].startswith('receiver')

    @property
    def dependencies(self):
        return {'packets': [p['id'] for p in self.packets],
                'consultations': [c['id'] for r in self.records for c in r.get('consultations', [])]
                    if self.actor['role'] == 'specialist' else []}

    @property
    def label(self):
        if self.provider:
            return human(self.actor['organization']) + ' · authorized referral packets'
        if self.actor['role'] == 'patient':
            return 'Your linked care episodes'
        if self.actor['role'] == 'specialist':
            return 'Your assigned specialist consultations'
        return human(self.actor['organization']) + ' · authorized care workspace'


def load_scope(db, actor):
    """Use the same case and packet boundaries as the ordinary application API."""
    if actor['role'] not in ROLES:
        from fastapi import HTTPException
        raise HTTPException(403, 'This assistant requires a signed-in care workspace account.')
    packets, records = [], []
    role = actor['role']
    if role.startswith('receiver'):
        for handoff in db.scalars(select(Handoff).where(Handoff.receiver == actor['organization']).order_by(Handoff.requested_at)):
            if permitted_grant(db, actor, handoff.case_id, handoff.id):
                authorize_case(db, actor, handoff.case_id, packet=True)
                packets.append(referral_packet(db, handoff))
        # A provider may have more than one scoped packet for one episode.
        by_case = {}
        for packet in packets:
            by_case[packet['case_id']] = packet
        records = list(by_case.values())
    else:
        query = select(Case).order_by(Case.created_at, Case.id)
        if role == 'patient':
            query = query.where(Case.patient_id == actor.get('patient_id'), Case.identity_verified == True)
        elif role == 'specialist':
            if actor['organization'] != settings()['specialist_organization']:
                return Scope(actor, [], [], clock(db).isoformat())
            case_ids = select(Consultation.case_id).where(Consultation.recipient.in_([actor['id'], 'specialist']))
            query = query.where(Case.id.in_(case_ids))
        else:
            query = query.where(Case.source_organization == actor['organization'])
        for case in db.scalars(query):
            records.append(serialize_case(db, authorize_case(db, actor, case.id), actor))
    ids = {case_id(record) for record in records}
    deliveries = [asdict(row) for row in db.scalars(select(Outbox).where(Outbox.case_id.in_(ids)))] if role in STAFF and ids else []
    return Scope(actor, records, packets, clock(db).isoformat(), deliveries)


def case_id(record):
    return record.get('case_id', record.get('id'))


def case_href(scope, record, section='journey'):
    cid = case_id(record)
    if scope.provider:
        return '/receiving#referral-' + quote(record['id'], safe='')
    if scope.actor['role'] == 'patient':
        anchors = {'appointments': 'patient-appointments', 'consultations': 'patient-questions',
                   'evidence': 'patient-plan', 'ownership': 'next-step'}
        return '/patient#' + anchors.get(section, 'next-step')
    if scope.actor['role'] == 'specialist' and section == 'clinical':
        # Specialist case access does not include the closure-review panel.
        return '/cases/' + quote(cid, safe='') + '?tab=journey#case-milestones'
    tabs = {'appointments': 'coordination', 'ownership': 'coordination', 'tasks': 'coordination',
            'consultations': 'consultations', 'evidence': 'journey', 'clinical': 'clinical'}
    anchors = {'appointments': 'case-appointments', 'ownership': 'case-referrals', 'tasks': 'case-tasks',
               'consultations': 'case-consultations', 'evidence': 'case-evidence', 'clinical': 'case-closure'}
    return '/cases/' + quote(cid, safe='') + '?tab=' + ('journey' if section == 'clinical' else tabs.get(section, 'journey')) + '#' + anchors.get(section, 'case-milestones')


def source(scope, record, field='episode', section='journey'):
    cid = case_id(record)
    return {'id': cid + ':' + field, 'label': cid + ' · ' + human(field),
            'href': case_href(scope, record, section), 'case_id': cid,
            'field': field, 'version': record.get('version')}


def record_card(scope, record, section='journey'):
    cid = case_id(record)
    card = {'id': cid, 'title': record.get('patient_name', cid),
        'subtitle': cid + ' · ' + (human(record.get('status')) if scope.provider else human(record.get('phase'))),
        'status': record.get('status') if scope.provider else record.get('disposition'),
        'href': case_href(scope, record, section),
        'fields': [{'label': 'Episode owner', 'value': human(record.get('owner'))}]}
    if scope.provider:
        card['fields'] += [{'label': 'Referral scope', 'value': human(record.get('scope'))},
                           {'label': 'Source result', 'value': 'Version ' + str(record.get('result_version'))},
                           {'label': 'Referral reason', 'value': record.get('reason') or record.get('reason_for_referral') or 'Not recorded'}]
    else:
        card['fields'].append({'label': 'Next step', 'value': record.get('next_action') or 'Review the care record'})
        if scope.actor['role'] != 'patient':
            card['fields'] += [{'label':'Source result','value':'Version '+str(record.get('result_version'))},
                               {'label':'Issued','value':record.get('issued_at') or 'Not recorded'}]
    return card


def assigned_requests(scope, records=None):
    records = scope.records if records is None else records
    role = scope.actor['role']
    if scope.provider:
        ids = {case_id(r) for r in records}
        return [(p, 'referral') for p in scope.packets if p['case_id'] in ids and p['status'] == 'requested']
    if role == 'navigator':
        aliases = {scope.actor['id'], 'navigator', 'navigation-team'}
        return [(r, task) for r in records for task in r.get('tasks', [])
                if active_task(task) and task.get('assignee') in aliases]
    if role == 'admin':
        by_id = {case_id(r): r for r in records}
        return [(by_id[item['case_id']], item) for item in scope.outbox
                if item['case_id'] in by_id and item['status'] not in {'delivered', 'completed'}]
    requests = []
    for record in records:
        for item in record.get('consultations', []):
            if item.get('reply'):
                continue
            if role == 'specialist' and item['recipient'] not in {scope.actor['id'], 'specialist'}:
                continue
            if role == 'clinician' and item['recipient'] not in {scope.actor['id'], 'clinician'}:
                continue
            requests.append((record, item))
        if role == 'patient':
            requests.extend((record, item) for item in record.get('tasks', []) if active_task(item))
    return requests


def scope_counts(scope):
    tasks = [task for record in scope.records for task in record.get('tasks', []) if active_task(task)]
    # Providers' source task lists are intentionally absent from packet scope.
    return {'episodes': len(scope.records), 'open_tasks': len(tasks) if not scope.provider else None,
        'pending_requests': len(assigned_requests(scope)),
        'urgent_reviews': sum(urgent_review(r) for r in scope.records) if not scope.provider else None}


def suggestions(scope, selected=None):
    if scope.actor['role'] == 'patient':
        return ['What is my next step?', 'Who is my care team?', 'What appointments are recorded?', 'How can I ask my clinician?']
    if scope.provider:
        return ['How many referral requests do I have?', 'Show my pending referrals', 'Which appointments are booked?', 'What information can I see?']
    if selected:
        cid = case_id(selected)
        return [f'What is the next step for {cid}?', f'Show appointments for {cid}', f'Who owns {cid}?', f'What evidence is recorded for {cid}?']
    return ['How many requests do I have?', 'Which cases need urgent review?', 'Show overdue work', 'Find a patient']


def context_payload(scope):
    provider = scope.provider
    request_definition = ('Referral packets awaiting your service decision' if provider else
        'Unanswered consultations addressed to your role' if scope.actor['role'] in {'clinician', 'specialist'} else
        'Unfinished follow-up tasks assigned to your navigation role' if scope.actor['role']=='navigator' else
        'Unfinished integration delivery records in your authorized operations scope' if scope.actor['role']=='admin' else
        'Your unanswered clinical questions and unfinished practical-help requests')
    return {'actor': scope.actor, 'scope_label': scope.label, 'counts': scope_counts(scope),
        'count_definitions': {'episodes': 'Distinct episodes visible to this account',
            'open_tasks': 'Unfinished tasks returned within your permitted case view; source tasks are not exposed to receiving services',
            'pending_requests': request_definition, 'urgent_reviews': 'Trusted urgent signals with unresolved review in your permitted view'},
        'suggestions': suggestions(scope), 'mode': 'authorized_records',
        'capabilities': ['Find permitted patients', 'Read current workload', 'Explain recorded next steps',
                         'Link to the relevant workspace', 'Read versioned workflow guidance'],
        'refreshed_at': now_iso(), 'read_only': True}


def detect_intent(question):
    q = question.casefold()
    tests = [('operations', r'integration|delivery|deliveries|outbox|callback|connector|تكامل'),
        ('urgent', r'urgent|escalat|عاجل|تصعيد'), ('overdue', r'overdue|late\b|delay|متأخر'),
        ('appointments', r'appoint|booking|booked|attend|no.show|موعد|مواعيد|حضور'),
        ('evidence', r'evidence|document|source|result|verify|verification|close|closure|outcome|milestone|دليل|مستند|نتيجة|اغلاق'),
        ('ownership', r'\bowner\b|\bowns\b|responsib|care team|who.*team|فريق|مسؤول'),
        ('consultations', r'consult|question|reply|replies|استشار|سؤال|أسئلة|ردود'),
        ('tasks', r'\btask|next action|work item|مهام'),
        ('episodes', EPISODE_COUNT),
        ('requests', r'request|how many|\bcount\b|\bnumber\b|workload|\bqueue\b|'
            r'pending\s+referrals?\b|referrals?\s+(?:need|await|waiting)\b|كم|طلبات'),
        ('knowledge', r'how does|how do i|what can|what information|workflow|guidance|difference|كيف|مساعدة'),
        ('patient', r'patient|find|show|next step|مريض|ابحث|التالي')]
    return next((intent for intent, pattern in tests if re.search(pattern, q)), 'overview')


def select_records(scope, question, context_case_id=None):
    """Search only already-authorized names/IDs; never probe the global case table."""
    q = question.casefold()
    explicit = re.findall(r'\b(?:SC-\d+|BRW-[A-Za-z0-9_-]+)\b', question, re.I)
    if explicit:
        selected = [r for r in scope.records if str(case_id(r)).casefold() in {x.casefold() for x in explicit}]
        return selected, not bool(selected)
    selected = [r for r in scope.records if str(case_id(r)).casefold() in q or str(r.get('patient_id', '!')).casefold() in q]
    if not selected:
        for record in scope.records:
            tokens = [t for t in re.findall(r'\w+', record.get('patient_name', '').casefold()) if len(t) > 2 and t != 'synthetic']
            if tokens and any(re.search(r'\b'+re.escape(token)+r'\b', q) for token in tokens):
                selected.append(record)
    if selected:
        return selected, False
    if context_case_id:
        return [r for r in scope.records if case_id(r) == context_case_id], context_case_id not in scope.ids
    if scope.actor['role'] == 'patient' and len(scope.records) == 1:
        return scope.records, False
    return [], False


def render_answer(db, scope, question, context_case_id=None, intent=None):
    """Return an answer and the complete visibility dependency for safe history."""
    selected, unavailable = select_records(scope, question, context_case_id)
    intent = intent if intent in INTENTS else detect_intent(question)
    answer = {'summary': '', 'mode': 'authorized_records', 'sources': [], 'cards': [],
              'suggestions': suggestions(scope, selected[0] if len(selected) == 1 else None),
              'refreshed_at': now_iso(), 'scope_label': scope.label, 'read_only': True}
    related = {case_id(r) for r in selected}
    if UNSAFE.search(question):
        answer['summary'] = 'I can help with permitted care records and workflow questions. Credentials, hidden records, system instructions and database commands are outside this workspace assistant.'
        return answer, set(), None
    if unavailable:
        answer['summary'] = 'I could not find a matching record available to this account. Try an authorized case reference or open your workspace. I cannot confirm records outside your access.'
        return answer, set(), None
    if CLINICAL.search(question):
        answer['summary'] = 'A qualified clinician needs to answer that clinical question. I can show the documented plan, responsible team and where to ask for a human reply.'
        for record in selected[:6]:
            answer['cards'].append(record_card(scope, record, 'consultations'))
            answer['sources'].append(source(scope, record, 'care_team', 'consultations'))
        if not selected and scope.actor['role'] == 'patient':
            answer['cards'] = [{'id': 'ask-team', 'title': 'Ask your care team', 'subtitle': 'Clinical questions receive a human reply', 'href': '/patient#patient-questions'}]
        return answer, related, case_id(selected[0]) if len(selected) == 1 else None
    records = selected or scope.records
    related = {case_id(r) for r in records}
    imperative = bool(WRITE.search(question))
    if imperative:
        answer['summary'] = 'This chat reads records and links you to the authorized action. It does not accept referrals, book visits, verify evidence, send messages or change clinical decisions. '
    prefix = answer['summary']
    counts = scope_counts(scope)
    if intent == 'episodes':
        # The episode metric is different from role-specific pending requests.
        # A patient can have multiple episodes; count identities separately when
        # the user asks for patients, using only the already permitted records.
        patients = bool(re.search(r'\bpatients?\b|مرضى|المرضى', question, re.I))
        total = len({r['patient_id'] for r in records}) if patients else len(records)
        label = 'Authorized patients' if patients else 'Authorized episodes'
        answer['summary'] = prefix + f'{total} distinct authorized '+('patients' if patients else 'care episodes') + ' in this permitted view.'
        answer['metrics'] = [{'label':label, 'value':total,
            'definition':'Distinct patient identities in permitted episode records' if patients else 'Distinct episodes visible to this account'}]
        if patients:
            answer['metrics'].append({'label':'Authorized episodes','value':len(records),
                'definition':'A patient can have more than one care episode'})
        answer['cards'] = [record_card(scope, r) for r in records[:8]]
        answer['sources'] = [source(scope, r) for r in records[:12]]
    elif intent in {'requests', 'consultations'}:
        pending = assigned_requests(scope, records)
        count_label = ('referral requests awaiting your service decision' if scope.provider else
            'unfinished follow-up tasks assigned to your navigation role' if scope.actor['role']=='navigator' else
            'unfinished delivery records in your operations scope' if scope.actor['role']=='admin' else
            'unanswered consultation requests addressed to your role' if scope.actor['role'] in {'clinician','specialist'} else
            'unanswered questions or unfinished practical-help requests')
        answer['summary'] = prefix + f'{len(pending)} {count_label}' + (' for the selected episode.' if selected else ' in your authorized workspace.')
        answer['metrics'] = [{'label': 'Pending requests', 'value': len(pending), 'definition': context_payload(scope)['count_definitions']['pending_requests']}]
        seen = set()
        for record, _ in pending:
            if case_id(record) not in seen:
                answer['cards'].append(record_card(scope, record, 'consultations'))
                seen.add(case_id(record))
        answer['sources'] = [source(scope, r, 'pending_requests', 'consultations') for r in records[:12]]
    elif intent in {'tasks', 'overdue', 'urgent'}:
        if scope.provider:
            answer['summary'] = prefix + 'Your receiving-service access includes referral packets and your appointments. Source-clinic task lists and clinical escalation details are not granted by that scope.'
            answer['cards'] = [record_card(scope, r) for r in records[:8]]
        else:
            tasks = [(r, t) for r in records for t in r.get('tasks', []) if active_task(t)
                     and (intent != 'overdue' or (t.get('due_at') and t['due_at'] < scope.instant))]
            if intent == 'urgent':
                matches = [r for r in records if urgent_review(r)]
                answer['summary'] = prefix + f'{len(matches)} episodes need trusted urgent clinical review in this permitted view. Staff acknowledgement and clinical disposition remain separate.'
                answer['cards'] = [record_card(scope, r, 'clinical') for r in matches]
                answer['metrics'] = [{'label': 'Urgent reviews', 'value': len(matches)}]
            else:
                answer['summary'] = prefix + f'{len(tasks)} ' + ('overdue' if intent == 'overdue' else 'unfinished') + ' tasks in this permitted view. Deadlines use the configured demonstration service windows.'
                answer['metrics'] = [{'label': 'Overdue tasks' if intent == 'overdue' else 'Open tasks', 'value': len(tasks)}]
                answer['cards'] = [{'id': t['id'], 'title': r.get('patient_name', case_id(r)), 'subtitle': t['next_action'],
                    'status': t['status'], 'href': case_href(scope, r, 'tasks'), 'fields': [
                        {'label': 'Assignee', 'value': human(t.get('assignee'))}, {'label': 'Due', 'value': t.get('due_at') or 'Not set'}]} for r,t in tasks[:12]]
            answer['sources'] = [source(scope, r, intent, 'clinical' if intent == 'urgent' else 'tasks') for r in records[:12]]
    elif intent == 'appointments':
        appointments = [(r, item) for r in records for item in r.get('appointments', [])]
        filters = [('no_show',r'no.show'),('cancelled',r'cancelled|canceled'),('attended',r'attended|حضر'),('booked',r'booked|confirmed|upcoming|مؤكد')]
        status_filter = next((value for value, pattern in filters if re.search(pattern, question, re.I)), None)
        if status_filter:
            appointments = [(record, item) for record, item in appointments if item['status']==status_filter]
        answer['summary'] = prefix + f'{len(appointments)} appointment records in this permitted view. Booking, attendance, investigation and clinical outcome remain separate facts.'
        answer['metrics'] = [{'label': 'Recorded appointments', 'value': len(appointments)}]
        answer['cards'] = [{'id': item['id'], 'title': r.get('patient_name', case_id(r)),
            'subtitle': human(item.get('provider')), 'status': item['status'], 'href': case_href(scope, r, 'appointments'),
            'fields': [{'label': 'Scheduled', 'value': item.get('scheduled_at') or 'Not recorded'}]} for r,item in appointments[:12]]
        answer['sources'] = [source(scope, r, 'appointments', 'appointments') for r in records[:12]]
    elif intent == 'ownership':
        answer['summary'] = prefix + ('The accountable team and recorded next step are shown below.' if records else 'No care episode is currently linked within this account scope.')
        answer['cards'] = [record_card(scope, r, 'ownership') for r in records[:8]]
        answer['sources'] = [source(scope, r, 'owner', 'ownership') for r in records[:8]]
    elif intent == 'evidence':
        if scope.provider:
            answer['summary'] = prefix + 'You can inspect the granted referral packet and your service appointment facts. It does not grant source-chart documents or clinical verification access.'
            answer['cards'] = [record_card(scope, r) for r in records[:8]]
        elif scope.actor['role'] == 'patient':
            plans = [(r, r.get('care_plan')) for r in records if r.get('care_plan')]
            answer['summary'] = prefix + ('The clinician-approved plan recorded for your episode is shown below.' if plans else 'A clinician-approved care plan is not yet recorded in your permitted patient view. Your team can explain the next step.')
            answer['cards'] = [{'id': case_id(r)+':plan', 'title': 'Your documented care plan', 'subtitle': plan['summary'],
                'href': '/patient#patient-plan', 'fields': [{'label': 'Approved by', 'value': human(plan.get('approved_by'))}]} for r,plan in plans]
        else:
            evidence = [(r, item) for r in records for item in r.get('evidence', [])]
            answer['summary'] = prefix + f'{len(evidence)} source-evidence records are linked to this permitted view. Pending or superseded evidence does not establish completed care. Open the case to read authorized sources and the clinical checklist.'
            answer['cards'] = [{'id': item['id'], 'title': r.get('patient_name', case_id(r))+' · '+human(item['type']),
                'subtitle': item['reference'], 'status': human(item['verification'])+' · '+human(item['status']),
                'href': case_href(scope, r, 'evidence').split('#')[0]+'#evidence-'+quote(item['id'],safe=''),
                'fields': [{'label': 'Source result', 'value': 'Version '+str(item['result_version'])}]} for r,item in evidence[:12]]
        answer['sources'] = [source(scope, r, 'evidence', 'evidence') for r in records[:12]]
    elif intent == 'operations':
        if scope.actor['role'] not in STAFF:
            answer['summary'] = prefix + 'Integration and operational queues are outside this account scope. I can show your permitted care records and requests.'
        else:
            rows = [o for o in db.scalars(select(Outbox)) if o.case_id in scope.ids]
            failed = [o for o in rows if o.status in {'retry','dead_letter'}]
            answer['summary'] = prefix + f'{len(failed)} delivery records currently need recovery out of {len(rows)} visible integration records. No retry was submitted by this chat.'
            answer['cards'] = [{'id':'operations', 'title':'Integration delivery and recovery', 'subtitle':'Actual persisted outbox records', 'count':len(failed), 'href':'/operations'}]
            answer['sources'] = [{'id':'operations:outbox','label':'Operations · current outbox','href':'/operations','field':'outbox'}]
    elif intent == 'knowledge':
        try:
            docs = retrieve(question+' followup ownership communication', scope='public' if scope.actor['role']=='patient' or scope.provider else 'staff', limit=2)
        except PolicyReviewRequired:
            docs = []
        if docs:
            answer['summary'] = prefix + 'The current versioned knowledge pack provides the following workflow guidance. Local service windows are demonstration settings; source review status is shown with each entry.'
            for doc in docs:
                href = doc['source'] if doc['source'].startswith('https://') else '/api/assistant/knowledge/'+quote(doc['id'],safe='')
                answer['cards'].append({'id':doc['id'],'title':doc['section'],'subtitle':doc['text'],'href':href,
                    'fields':[{'label':'Authority','value':doc['authority']},{'label':'Version','value':doc['version']},{'label':'Review status','value':doc.get('review_status','Not independently reviewed')}]})
                answer['sources'].append({'id':doc['citation'],'label':doc['authority']+' · '+doc['section'],'href':href,'field':'versioned_workflow_guidance'})
        else:
            answer['summary'] = prefix + 'I could not find current versioned guidance for that question. Ask the responsible care team; I can still help locate permitted records and next steps.'
    else:
        if selected:
            answer['summary'] = prefix + ('The current authorized episode is shown below.' if len(selected)==1 else f'{len(selected)} matching authorized episodes are shown below.')
        elif intent == 'patient':
            answer['summary'] = prefix + f'{len(scope.records)} episodes are available in this account scope. Search by a patient name or case reference to focus the answer.'
        else:
            answer['summary'] = prefix + (f"Your authorized workspace contains {counts['episodes']} episodes and {counts['pending_requests']} pending referral requests. Only your granted referral packets and service appointment facts are included." if scope.provider else f"Your authorized workspace contains {counts['episodes']} episodes, {counts['pending_requests']} pending requests and {counts['open_tasks']} unfinished tasks. These counts were read from current records.")
            answer['metrics'] = [{'label':human(k),'value':v} for k,v in counts.items() if v is not None]
        answer['cards'] = [record_card(scope, r) for r in records[:8]]
        answer['sources'] = [source(scope, r) for r in records[:12]]
    # Bounded response size, with all selected-record and count dependencies retained
    # server-side for history invalidation after an access change.
    answer['cards'] = answer['cards'][:12]
    answer['recorded_total'] = len(records)
    if len(records)>12:
        answer['scope_note'] = 'Counts cover the full authorized view; at most twelve source links are shown.'
    return answer, related, case_id(selected[0]) if len(selected)==1 else None
