"""Execution-time source evidence; no scoring or clinical-state mutation."""
from __future__ import annotations
import sys,shutil
from pathlib import Path
from .common import ROOT,read_json,atomic_json,file_hash,digest,now

def capture_backend_before_import(database_path:Path)->dict|None:
    """Archive actual backend bytes at first full-journey test-store import.

    The model benchmark starts before API tests run. Application security repairs
    may finish while model requests execute. This records the real first-import
    version instead of pretending an earlier candidate-source capture applied.
    """
    prefix='suhail-';suffix='-journey-execution.sqlite3';name=database_path.name
    if not name.startswith(prefix) or not name.endswith(suffix):return None
    run_id=name[len(prefix):-len(suffix)]
    if not run_id or not all(c.isalnum() or c in '-_' for c in run_id):raise ValueError('invalid_provenance_run')
    run=ROOT/'reports/runs'/run_id
    if not (run/'manifest.json').exists():return None
    evidence=run/'actual-backend-first-import.json'
    files={str(p.relative_to(ROOT)):file_hash(p) for p in (ROOT/'services/api').glob('*.py')}
    previous=read_json(evidence)
    if previous:
        if previous['file_hashes']!=files:raise ValueError('backend_changed_after_first_journey_freeze')
        return previous
    for rel,expected in files.items():
        target=run/'actual-backend-source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
        if file_hash(target)!=expected:raise ValueError('backend_changed_during_preimport_capture')
    instrumentation={}
    for source in (Path(__file__),ROOT/'evals/domain_harness.py'):
        rel=str(source.relative_to(ROOT));target=run/'journey-provenance-instrumentation'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);instrumentation[rel]=file_hash(target)
    record={'id':'actual-backend-at-first-journey-import','captured_at':now(),'file_hashes':files,'backend_hash':digest(files),'already_loaded_api_modules':[name for name in sys.modules if name.startswith('services.api')],'captured_before_services_api_db_and_domain_import':not any(name in sys.modules for name in ('services.api.db','services.api.domain')),'instrumentation_revision':instrumentation,'reason':'Instrumentation-only source capture added before DomainHarness first import to distinguish final backend security repairs from earlier model-source freeze; no model/prompt/RAG/scorer/truth/command changes.','prior_backend_captures':'Earlier scheduler-resume/prejourney captures are intermediate; this execution-time capture governs actual fulljourneys. Raw case backend_source_hash from the scheduler is a resume-point label, not a replacement for this phase evidence.','applies_to_components':['journeys'],'artifact_path':'actual-backend-source'}
    atomic_json(evidence,record);return record


def retrieval_contexts(call:dict)->list[dict]:
    import json
    result=[]
    for index,message in enumerate(call.get('messages',[])):
        try:value=json.loads(message.get('content') or '')
        except (TypeError,ValueError):continue
        if not isinstance(value,dict):continue
        if isinstance(value.get('retrieved_policy'),list):result.append({'location':f'messages[{index}].retrieved_policy','sections':value['retrieved_policy']})
        if message.get('role')=='tool' and value.get('name')=='retrieve_policy' and isinstance(value.get('result'),list):result.append({'location':f'messages[{index}].tool.result','sections':value['result']})
    return result


def policy_references(call:dict)->set[str]:
    return {str(section[key]) for context in retrieval_contexts(call) for section in context['sections'] for key in ('source','citation') if key in section}


def validate_rag_lineage(run:Path,calls:list[dict])->list[str]:
    from .common import rows,verify_chain
    errors=[];archive=run/'rag-provenance/knowledge-captured-late.json'
    if not archive.exists():archive=run/'source-snapshot/services/agents/knowledge.json'
    if not archive.exists():return errors
    pack=read_json(archive);docs={d['id']:d for d in pack['documents']}
    lineage=rows(run/'rag-provenance/retrieval-lineage.jsonl')
    try:verify_chain(lineage)
    except (AssertionError,KeyError) as exc:errors.append('RAG lineage chain: '+str(exc))
    by_call={r['provider_call_id']:r for r in lineage}
    for call in calls:
        contexts=retrieval_contexts(call)
        if not contexts:continue
        link=by_call.get(call['call_id'])
        if not link:errors.append('missing actual RAG call lineage '+call['call_id']);continue
        if link['provider_record_hash']!=call['record_hash'] or link['actual_retrieved_context_hash']!=digest(contexts):errors.append('RAG call/input hash mismatch '+call['call_id'])
        if link['knowledge_pack_sha256']!=file_hash(archive):errors.append('RAG archive byte hash mismatch')
        for context in contexts:
            for section in context['sections']:
                item=dict(section);citation=item.pop('citation',None)
                if item!=docs.get(item.get('id')) or citation!=item['id']+'#'+item['section']:errors.append('actual retrieved section differs from archived pack '+call['call_id'])
    return errors


def dispatch_accounting(run:Path,calls:list[dict])->dict:
    import datetime as dt
    from .common import rows
    dispatches=rows(run/'scheduler-dispatches.jsonl')
    adjustments=read_json(run/'manifest.json',{}).get('operational_adjustments',[])
    earliest=min((a['timestamp'] for a in adjustments),default=None)
    proved=[];queued=[];unknown=[]
    def stamp(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    for call in calls:
        if call.get('status')=='completed' or call.get('http_status') is not None:
            proved.append(call['call_id']);continue
        start=stamp(call['timestamp']);end=start+dt.timedelta(milliseconds=float(call.get('latency_ms') or 0))
        sent=any(d['input_hash']==call.get('input_hash') and start-dt.timedelta(seconds=.1)<=stamp(d['dispatched_at'])<=end+dt.timedelta(seconds=.1) for d in dispatches)
        if sent:proved.append(call['call_id'])
        elif call.get('status')=='cancelled' and earliest and start>=stamp(earliest):queued.append(call['call_id'])
        else:unknown.append(call['call_id'])
    return {'reservation_attempts':len(calls),'actual_dispatched_requests':len(proved) if not unknown else None,'confirmed_dispatched_requests':len(proved),'queued_pre_dispatch_cancellations':len(queued),'unknown_dispatch_attempts':len(unknown),'completed_provider_responses':sum(c.get('status')=='completed' for c in calls),'successful_generation_responses':sum(c.get('status')=='completed' and c.get('mode')!='model_list' for c in calls),'paid_inference_calls':None,'confirmed_dispatch_call_ids':proved,'pre_dispatch_cancelled_call_ids':queued,'unknown_dispatch_call_ids':unknown,'definition':'usage.api_calls and spending cap count reserved request attempts, including queued cancellations. Actual SDK/network dispatch is shown separately; paid-call status and missing usage stay unknown. No conservative reservation is refunded.'}


def ensure_rag_lineage(run:Path)->None:
    from .common import rows,Ledger
    archive=run/'rag-provenance/knowledge-captured-late.json'
    scope='explicit_late_capture_erratum'
    if not archive.exists():archive=run/'source-snapshot/services/agents/knowledge.json';scope='initial_frozen_source_snapshot'
    if not archive.exists():return
    docs={d['id']:d for d in read_json(archive)['documents']};ledger=Ledger(run/'rag-provenance/retrieval-lineage.jsonl')
    for call in rows(run/'provider-calls.jsonl'):
        if call['call_id'] in ledger.ids:continue
        contexts=retrieval_contexts(call)
        if not contexts:continue
        for context in contexts:
            for section in context['sections']:
                doc=dict(section);citation=doc.pop('citation',None)
                if doc!=docs.get(doc.get('id')) or citation!=doc['id']+'#'+doc['section']:raise ValueError('actual_retrieval_does_not_match_archived_snapshot')
        ledger.append({'case_id':call['call_id'],'provider_call_id':call['call_id'],'provider_case_id':call.get('metadata',{}).get('case_id'),'provider_record_hash':call['record_hash'],'actual_retrieved_context_hash':digest(contexts),'document_ids':sorted({d['id'] for c in contexts for d in c['sections']}),'knowledge_pack_sha256':file_hash(archive),'captured_at':now(),'archive_scope':scope})


def secondary_arabic_score_audit(run:Path)->dict:
    """Score-only audit of existing failed-case responses; preserve primary failures."""
    import importlib.util
    from .common import rows,Ledger
    from .synthetic import score_proposal
    calls=rows(run/'provider-calls.jsonl');records=rows(run/'cases.jsonl');path=run/'secondary-scoring-audit/cases.jsonl';ledger=Ledger(path)
    original_path=run/'source-snapshot/evals/synthetic.py'
    original=None
    if original_path.exists():
        spec=importlib.util.spec_from_file_location('evals.original_synthetic_scorer_frozen_v1',original_path)
        original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
    for record in records:
        case_id=record['case_id']
        if case_id in ledger.ids or record.get('evaluated') or record.get('component') not in ('intake','pathway_router','safety_escalation','patient_navigator','coordination','closure_evidence'):continue
        example=record.get('input',{})
        if example.get('case',{}).get('language')!='ar':continue
        candidates=[c for c in calls if c.get('metadata',{}).get('case_id')==case_id and c.get('metadata',{}).get('purpose')=='candidate' and c.get('status')=='completed' and c.get('parsed') is not None]
        if len(candidates)!=1:continue
        call=candidates[0];original_error=None
        try:
            if original:original.score_proposal(example,call['parsed'])
        except Exception as exc:original_error=type(exc).__name__
        if original_error!='PolicyReviewRequired':continue
        score=score_proposal(example,call['parsed'],policy_references(call))
        ledger.append({'case_id':case_id,'component':record['component'],'original_case_record_hash':record['record_hash'],'original_terminal_state_preserved':'failed_scoring_execution','original_scoring_error_reproduced':original_error,'scored_at':now(),'scorer_version':'secondary-source-language-audit-v2','scorer_sha256':file_hash(ROOT/'evals/synthetic.py'),'candidate_call_id':call['call_id'],'candidate_record_hash':call['record_hash'],'candidate_output_hash':digest(call['parsed']),'candidate_model':call['model'],'new_api_calls':0,'evidence_mode':'score_only_replay_of_existing_live_response','score':score})
    for source in (ROOT/'evals/synthetic.py',Path(__file__)):
        dest=run/'secondary-scoring-audit/source'/str(source.relative_to(ROOT));dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copy2(source,dest)
    audit=rows(path)
    summary={'status':'COMPLETE' if audit else 'NOT_RUN','new_api_calls':0,'existing_live_responses_audited':len(audit),'task_passed':sum(r['score']['passed'] for r in audit),'task_incorrect':sum(not r['score']['passed'] for r in audit),'original_failure_counts_unchanged':True,'reason':'Original v1 scorer queried English FTS terms for Arabic source context, raised PolicyReviewRequired and lost the candidate ID in its exception path. Existing real responses are audited with their exact permitted policy references. This is secondary post-hoc scoring, not new inference or silent replacement of the primary failed-case denominator.','cases':[{'case_id':r['case_id'],'component':r['component'],'passed':r['score']['passed'],'candidate_call_id':r['candidate_call_id']} for r in audit]}
    atomic_json(run/'secondary-scoring-audit/summary.json',summary)
    (run/'secondary-scoring-audit/README.md').write_text('# Secondary Arabic scoring audit\n\n'+summary['reason']+'\n\n'+f'{len(audit)} existing responses audited; {summary["task_passed"]} passed and {summary["task_incorrect"]} incorrect. New API calls: 0. Original primary failure counts remain unchanged.\n')
    return summary


def validate_backend_artifacts(run:Path,records:list[dict])->list[str]:
    import sqlite3
    from .common import read_json
    errors=[];phase=read_json(run/'actual-backend-first-import.json',{})
    for rel,expected in phase.get('file_hashes',{}).items():
        archived=run/phase['artifact_path']/rel
        if not archived.exists() or file_hash(archived)!=expected:errors.append('actual backend source archive hash mismatch '+rel)
    databases={r['arm']:r for r in read_json(run/'journey-database-manifest.json',[])}
    for meta in databases.values():
        path=run/meta['artifact']
        if not path.exists() or file_hash(path)!=meta['sha256']:errors.append('independent arm DB hash mismatch '+meta['arm'])
    for record in records:
        if record.get('component')!='journeys' or not record.get('independent_arm_store') or not record.get('evaluated'):continue
        meta=databases.get(record['arm'])
        if not meta:errors.append('missing actual independent arm database '+record['case_id']);continue
        path=run/meta['artifact']
        with sqlite3.connect(path) as db:
            db.row_factory=sqlite3.Row
            case=db.execute('SELECT * FROM cases WHERE id=?',(record['output']['case_id'],)).fetchone()
            if case is None:errors.append('journey output case absent from saved DB '+record['case_id']);continue
            if case['disposition']!=record['output']['disposition'] or case['version']!=record['output']['version']:errors.append('saved case/output state mismatch '+record['case_id'])
            truth=record['input']['case']
            if case['patient_id']!=truth['patient_id'] or case['order_id']!=truth['order_id']:errors.append('saved patient/order truth mismatch '+record['case_id'])
            if case['disposition']=='completed_required_care':
                open_required=db.execute("SELECT COUNT(*) FROM tasks WHERE case_id=? AND required=1 AND status!='completed'",(case['id'],)).fetchone()[0]
                if open_required:errors.append('saved completed episode has unfinished required tasks '+record['case_id'])
                valid=db.execute("SELECT type FROM evidence WHERE case_id=? AND verification='verified' AND status='current' AND patient_id=? AND order_id=? AND result_version=?",(case['id'],case['patient_id'],case['order_id'],case['result_version'])).fetchall()
                types={r[0] for r in valid}
                if not {'investigation','reviewed_outcome','patient_updated'}<=types:errors.append('saved completed episode lacks endpoint evidence '+record['case_id'])
                if case['requires_onward'] and not ({'treatment_initiated','surveillance_plan'}&types):errors.append('saved completed episode lacks onward endpoint '+record['case_id'])
    return errors
