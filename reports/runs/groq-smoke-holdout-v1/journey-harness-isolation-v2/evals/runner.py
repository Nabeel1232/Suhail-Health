"""Bounded actual execution entry point: python -m evals.runner --help."""
from __future__ import annotations
import argparse,asyncio,copy,json,os,sys,time,traceback,sqlite3
from pathlib import Path
from .common import ROOT,FUNCTIONS,SCORER_VERSION,Ledger,now,digest,file_hash,atomic_json,read_json,rows,new_run,record_command
from .synthetic import function_cases,trajectory_truth,manifest as synthetic_manifest,base_case
from .reporting import build_reports,validate_run,count_records,status_for


def sanitized_error(exc):
    # Provider exceptions never include URLs/headers/raw private exception repr.
    return {'code':getattr(exc,'code','assertion_failed' if isinstance(exc,AssertionError) else 'execution_error'),'message':getattr(exc,'message','Scenario assertion failed: '+str(exc)[:180] if isinstance(exc,AssertionError) else 'Execution did not produce a valid evaluated result; see sanitized command events.')}

def configuration_hashes(m):
    from services.agents.engine import SYSTEM_PROMPT,PROPOSAL_SCHEMA
    m['prompt_hash']=digest({'prompt':SYSTEM_PROMPT,'schema':PROPOSAL_SCHEMA})
    paths=list((ROOT/'pathways').rglob('*')) if (ROOT/'pathways').exists() else []
    pack={str(p.relative_to(ROOT)):file_hash(p) for p in paths if p.is_file()}
    m['retrieval_hash']=digest(pack);m['policy_hash']=digest({k:v for k,v in pack.items() if 'policy' in k or 'json' in k})
    m['retrieval_snapshot']=pack

def finish(run_dir,m,ledger):
    for db_name in ('execution','journey-execution'):
        source=Path('/tmp')/f'suhail-{m["run_id"]}-{db_name}.sqlite3'
        if source.exists():
            with sqlite3.connect(source) as src,sqlite3.connect(run_dir/(db_name+'.sqlite3')) as dst:src.backup(dst)
    database_artifacts=[]
    for arm in ('A','B','C'):
        source=Path('/tmp')/f'suhail-{m["run_id"]}-journey-arm-{arm}'/f'suhail-{m["run_id"]}-journey-execution.sqlite3'
        if source.exists():
            target=run_dir/'journey-databases'/f'{arm}.sqlite3';target.parent.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(source) as src,sqlite3.connect(target) as dst:src.backup(dst)
            database_artifacts.append({'arm':arm,'source':str(source),'artifact':str(target.relative_to(run_dir)),'sha256':file_hash(target),'independent_arm_store':True})
    if database_artifacts:atomic_json(run_dir/'journey-database-manifest.json',database_artifacts)
    records=rows(run_dir/'cases.jsonl');m['run_state']='finished';m['finished_at']=now();m['status']=status_for(count_records(records));atomic_json(run_dir/'manifest.json',m)
    result=build_reports(run_dir)
    integrity=validate_run(run_dir)
    atomic_json(run_dir/'integrity.json',integrity)
    print(json.dumps({'run_id':m['run_id'],'status':result['status'],'counts':result['counts'],'usage':result['usage'],'integrity_valid':integrity['valid'],'report':str(run_dir/'summary.html')},indent=2))
    return result

def offline(args):
    from .domain_harness import DomainHarness
    run_dir,m=new_run('offline',args.run_id);record_command(run_dir,' '.join(sys.argv));ledger=Ledger(run_dir/'cases.jsonl')
    examples=[trajectory_truth(i,args.split) for i in range(args.trajectories)]
    invalids=[]
    for i in range(args.invalid_closures):
        truth=trajectory_truth(300000+i,args.split);truth['id']=f'invalid-closure-{args.split}-{i:05d}';truth['case']['id']=truth['case']['case_id']=m['run_id']+'-INVALID-'+str(i);truth['truth']['scenario']='invalid_closure';invalids.append(truth)
    for truth in examples:truth['case']['id']=truth['case']['case_id']=m['run_id']+'-'+truth['id']
    selected=examples+invalids;m['selected_case_ids']=[e['id'] for e in selected];m['dataset_manifest']=synthetic_manifest(selected)
    m['commands']=[' '.join(sys.argv)];m['limitations']=['Deterministic persisted domain commands, no live model inference in this layer.','SQLite isolated test store; production PostgreSQL API/browser integration verified separately.','Provider requests/events here execute domain authorization with synthetic actors; independent provider HTTP-contract checks are a separate test layer.','Operational deadlines and behavior are demonstration settings, not clinical validation.']
    try:configuration_hashes(m)
    except ImportError:pass
    atomic_json(run_dir/'manifest.json',m);atomic_json(run_dir/'dataset-manifest.json',m['dataset_manifest'])
    for i,truth in enumerate(selected):
        if truth['id'] in ledger.ids:continue
        started=now();h=DomainHarness(Path('/tmp')/f'suhail-{m["run_id"]}-execution.sqlite3');t0=time.monotonic();evaluated=False;error=None;output={};journey={}
        try:
            if truth in invalids:
                # Every attempt starts a distinct actual persisted case and calls the protected disposition command.
                h.intake(truth)
                i_invalid=int(truth['id'].rsplit('-',1)[1]);variant=i_invalid%5
                if variant==1:h.handoff();h.appointment(status='booked')
                elif variant==2:h.cmd('evidence_add','clinician',type='investigation',reference='synthetic://unverified',patient_id=h.case.patient_id,order_id=h.case.order_id,result_version=1)
                elif variant==3:
                    r=h.cmd('evidence_add','clinician',type='investigation',reference='synthetic://wrong-patient',patient_id='WRONG-PATIENT',order_id=h.case.order_id,result_version=1)
                    h.denied('wrong_evidence_verification_rejected','evidence_verify',evidence_id=r['record_id'],verified=True,reason='Mismatching source')
                elif variant==4:
                    h.evidence('reviewed_outcome',requires_onward=True);h.handoff('provider-b')
                h.denied('invalid_completed_care_disposition_rejected','disposition',category='completed_required_care',reason='Adversarial premature completion attempt')
                h.check('case_remains_unresolved',h.case.disposition=='open');journey=h.journey()
            else:journey=h.run_scenario(truth)
            output={'case_id':h.case.id,'version':h.case.version,'disposition':h.case.disposition,'owner':h.case.owner,'result_version':h.case.result_version};evaluated=True
        except Exception as exc:
            error=sanitized_error(exc);h.db.rollback()
            if h.case:
                try:output={'case_id':h.case.id,'version':h.case.version,'disposition':h.case.disposition}
                except Exception:pass
        record={'case_id':truth['id'],'component':'software_suite' if truth in invalids else 'journeys','scenario':truth['truth']['scenario'],'arm':'B','evidence_mode':'deterministic_software','started_at':started,'finished_at':now(),'attempted':True,'evaluated':evaluated,'input':truth,'output':output,'tool_events':h.events,'score':{'passed':evaluated and all(a['passed'] for a in h.assertions),'assertions':h.assertions},'journey':journey,'error':error,'latency_ms':(time.monotonic()-t0)*1000}
        ledger.append(record);h.close()
        if (i+1)%100==0:print(json.dumps({'progress':i+1,'selected':len(selected),'failed_execution':sum(not r['evaluated'] for r in rows(run_dir/'cases.jsonl'))}),flush=True)
    return finish(run_dir,m,ledger)

async def invoke_agent(gateway,example,run_id,case_id=None,tool_mode=False):
    from services.agents.engine import propose
    return await propose(example['component'],example['case'],gateway,metadata={'run_id':run_id,'case_id':case_id or example['id']},tool_mode=tool_mode)

def candidate_call(run_dir,cid):
    return next((x for x in reversed(rows(run_dir/'provider-calls.jsonl')) if x.get('call_id')==cid),None)

def successful_candidate_record(run_dir,cid):
    c=candidate_call(run_dir,cid)
    if c and c.get('status')=='completed' and c.get('parsed') is not None:return c
    return None

async def live_function(run_dir,m,gateway,example):
    from .synthetic import score_proposal
    started=now();cid=None;error=None;result={};score={};evaluated=False;t0=time.monotonic()
    try:
        result=await invoke_agent(gateway,example,m['run_id'],tool_mode=example['component'] in ('coordination','closure_evidence') and example['id'].endswith('005'))
        cid=result['candidate_call_id'];score=score_proposal(example,result['proposal']);evaluated=True
    except Exception as exc:
        error=sanitized_error(exc);cid=getattr(exc,'call_id',None);c=successful_candidate_record(run_dir,cid)
        if c:
            # Semantically invalid/rejected completed model outputs count as evaluated incorrect, not infrastructure failures.
            result={'proposal':c['parsed'],'tool_events':[]};score=score_proposal(example,c['parsed']);score['passed']=False;score['assertions'].append({'name':'application_accepted_proposal_scope_and_sources','passed':False});evaluated=True
    c=candidate_call(run_dir,cid)
    return {'case_id':example['id'],'component':example['component'],'evidence_mode':'live_groq_synthetic','started_at':started,'finished_at':now(),'attempted':True,'evaluated':evaluated,'input':example,'proposal':result.get('proposal'),'tool_events':result.get('tool_events',[]),'tool_call_ids':result.get('tool_call_ids',[]),'candidate_call_id':cid,'candidate_output_hash':digest(c.get('parsed') if c.get('parsed') is not None else c.get('text')) if c else None,'candidate_model':c.get('model') if c else gateway.model,'score':score,'error':error,'latency_ms':(time.monotonic()-t0)*1000}

async def live_external(run_dir,m,gateway,example):
    from .healthbench import grader_messages,GRADER_SCHEMA,validate_grades,calculate_score
    started=now();cid=gid=None;error=None;score={};evaluated=False;grades=None;t0=time.monotonic()
    case_id='healthbench-'+example['id'];candidate_model=grader_model=gateway.model
    try:
        # Leave room for the required grader before producing a candidate.
        if m['grader_model']!=gateway.model:
            from services.agents.gateway import GatewayError
            raise GatewayError('grader_configuration_blocked','Configured grader differs from the frozen shared gateway model; no silent model substitution.')
        status=gateway.budget_status()
        reserve_need=len(json.dumps(grader_messages(example,'x'*6000),ensure_ascii=False).encode())+4096+512
        if status['max_calls']-status['api_calls']<2 or status['max_tokens']-status['charged_tokens']<reserve_need+8192:
            from services.agents.gateway import GatewayError
            raise GatewayError('budget_exhausted','Insufficient conservative allowance for candidate plus mandatory rubric grading.')
        candidate=await gateway.complete(example['messages'],mode='text',max_tokens=1536,metadata={'run_id':m['run_id'],'case_id':case_id,'purpose':'external_candidate'})
        cid=candidate['call_id'];candidate_model=candidate['model']
        grade=await gateway.complete(grader_messages(example,candidate['text']),response_schema=GRADER_SCHEMA,mode='structured',max_tokens=4096,metadata={'run_id':m['run_id'],'case_id':case_id,'purpose':'external_grader'})
        gid=grade['call_id'];grader_model=grade['model'];grades=validate_grades(example,grade['parsed']);value=calculate_score(example['rubrics'],grades)
        score={'rubric_score':value,'passed':None,'grades':grades,'aggregation':'signed_met_weights/positive_weights; aggregate mean clipping only'};evaluated=True
    except Exception as exc:error=sanitized_error(exc)
    c=candidate_call(run_dir,cid);g=candidate_call(run_dir,gid)
    return {'case_id':case_id,'component':'external_suite','evidence_mode':'adapted_external','started_at':started,'finished_at':now(),'attempted':bool(cid or (error and error['code']!='budget_exhausted')),'evaluated':evaluated,'original_example_id':example['id'],'input_messages':example['messages'],'rubrics':example['rubrics'],'category_metadata':example['category_metadata'],'candidate_call_id':cid,'grader_call_id':gid,'candidate_model':candidate_model,'grader_model':grader_model,'candidate_output_hash':digest(c.get('text')) if c else None,'grader_output_hash':digest(g.get('parsed')) if g else None,'score':score,'error':error,'latency_ms':(time.monotonic()-t0)*1000}

def journey_agent_snapshot(h,source_references):
    s=h.snapshot()
    fields=('id','version','patient_id','order_id','result_version','test_code','pathway','policy_version','owner','backup_queue','language','identity_verified','quarantine_reason','urgent','requires_onward','disposition','residual_need','next_action','delay_reasons')
    out={k:s[k] for k in fields if k in s};out['source_references']=source_references
    selections={'tasks':('id','type','status','required','assignee'),'evidence':('id','type','reference','verification','status','patient_id','order_id','result_version','plan_owner','recall_date'),'handoffs':('id','status','scope','receiver'),'appointments':('id','provider','status'),'consultations':('id','type','question','status','human_author','agreed_action','action_owner'),'escalations':('id','trigger','disposition','acknowledged_at')}
    for group,keys in selections.items():out[group]=[{k:r.get(k) for k in keys} for r in s.get(group,[])]
    return out

async def live_journey(run_dir,m,gateway,truth,arm,scenario):
    from .domain_harness import DomainHarness
    from .synthetic import score_proposal
    from services.agents.engine import check_detached_closure
    # Paired arms share scenario truth, with independent application stores.
    # A common patient/order namespace in one store would correctly deduplicate
    # A/B/C into the same clinical episode and invalidate a paired comparison.
    db_directory=Path('/tmp')/f'suhail-{m["run_id"]}-journey-arm-{arm}'
    db_directory.mkdir(parents=True,exist_ok=True)
    db_path=db_directory/f'suhail-{m["run_id"]}-journey-execution.sqlite3'
    h=DomainHarness(db_path);started=now();t0=time.monotonic();error=None;evaluated=False;proposals=[];cids=[];output={};journey={}
    cid=None;case_id=f'paired-{truth["id"]}-{arm}';truth=copy.deepcopy(truth);truth['case']['id']=truth['case']['case_id']=m['run_id']+'-'+case_id
    try:
        opts={'identity_verified':False} if scenario=='identity_conflict' else {'trusted_urgent':True} if scenario=='urgent_timeout' else {}
        h.intake(truth,**opts)
        h.check('arm_starts_in_its_own_case_identity',h.case.id==truth['case']['id'])
        h.check('arm_starts_at_fresh_case_version',h.case.version==1)
        if arm=='C':
            for function in FUNCTIONS[:-1]:
                s=journey_agent_snapshot(h,truth['case']['source_references'])
                result=await invoke_agent(gateway,{'component':function,'case':s},m['run_id'],case_id=case_id)
                cids.append(result['candidate_call_id']);proposals.append({'function':function,**result})
        h.complete(scenario,arm,finalize=arm!='C')
        if arm=='C':
            s=journey_agent_snapshot(h,truth['case']['source_references']);s['closure_check']=check_detached_closure(s)
            result=await invoke_agent(gateway,{'component':'closure_evidence','case':s},m['run_id'],case_id=case_id)
            cid=result['candidate_call_id'];cids.append(cid);proposals.append({'function':'closure_evidence',**result})
            h.cmd('disposition','clinician',category='completed_required_care',reason='Human scenario actor independently checks deterministic endpoint evidence',residual_need='')
        h.check('paired_arm_expected_state',h.case.disposition==('open' if arm=='A' else 'completed_required_care'))
        journey=h.journey();output={'case_id':h.case.id,'version':h.case.version,'disposition':h.case.disposition};evaluated=True
    except Exception as exc:
        h.db.rollback();error=sanitized_error(exc)
        if getattr(exc,'call_id',None):cids.append(exc.call_id)
    finally:
        events=h.events;assertions=h.assertions;h.close()
    c=candidate_call(run_dir,cid)
    lineage=[]
    for linked in cids:
        call=candidate_call(run_dir,linked)
        if call:lineage.append({'call_id':linked,'output_hash':digest(call.get('parsed') if call.get('parsed') is not None else call.get('text')),'model':call.get('model')})
    return {'case_id':case_id,'component':'journeys','scenario':scenario,'arm':arm,'paired_id':truth['id'],'execution_database':str(db_path),'independent_arm_store':True,'execution_harness_revision':'independent-arm-stores-v2','scenario_contract':{'preselected_scenario':scenario,'base_fixture_tag':truth['truth']['scenario'],'base_fixture_tag_is_not_the_driver_scenario':True},'evidence_mode':'live_groq_synthetic' if arm=='C' else 'deterministic_software','started_at':started,'finished_at':now(),'attempted':True,'evaluated':evaluated,'input':truth,'output':output,'tool_events':events,'agent_proposals':proposals,'candidate_call_id':cid,'candidate_call_lineage':lineage,'candidate_output_hash':digest(c.get('parsed')) if c else None,'candidate_model':c.get('model') if c else None,'score':{'passed':evaluated and all(a['passed'] for a in assertions),'assertions':assertions},'journey':journey,'error':error,'latency_ms':(time.monotonic()-t0)*1000}

async def live(args):
    from services.agents.gateway import GroqGateway,GatewayError,env_value
    from .healthbench import load,select_subset
    run_dir,m=new_run('live',args.run_id);record_command(run_dir,' '.join(sys.argv));ledger=Ledger(run_dir/'cases.jsonl')
    if args.preset=='standard' and not (args.max_calls is not None and args.max_tokens is not None):raise ValueError('standard_requires_explicit_max_calls_and_max_tokens')
    count=min(6,int(env_value('SYNTHETIC_CASES_PER_AGENT',6))) if args.preset=='smoke' else min(args.cases or 50,50)
    journey_count=min(6,int(env_value('LIVE_JOURNEY_CASES',6))) if args.preset=='smoke' else min(args.journeys or 50,50)
    external_count=min(12,int(env_value('HEALTHBENCH_CASES',12))) if args.preset=='smoke' else min(args.external or 50,50)
    examples=[e for function in FUNCTIONS for e in function_cases(function,count)]
    scenarios=['normal_completion','rejected_handoff','no_show','onward_care','identity_conflict','urgent_timeout']
    journeys=[(trajectory_truth(500000+i),arm,scenarios[i%len(scenarios)]) for i in range(journey_count) for arm in ('A','B','C')]
    external=[];external_manifest=None;dataset_error=None
    try:external_manifest,all_external=load();external,selection=select_subset(all_external,external_count);atomic_json(run_dir/'external-selection.json',selection)
    except Exception as exc:dataset_error='dataset_access'
    m['provider']='groq';m['model']=args.model or env_value('GROQ_MODEL','openai/gpt-oss-120b');m['grader_model']=env_value('GROQ_GRADER_MODEL',m['model']);m['parameters']={'temperature':0,'structured_max_tokens':min(2048,int(env_value('AGENT_MAX_OUTPUT_TOKENS',2048))),'external_max_tokens':min(1536,int(env_value('AGENT_MAX_OUTPUT_TOKENS',1536))),'grader_max_tokens':min(4096,int(env_value('AGENT_MAX_OUTPUT_TOKENS',4096))),'stream':False,'concurrency':1,'configured_max_concurrency':min(2,int(env_value('MAX_CONCURRENCY',2))),'tool_parallel_calls':False,'quantization':'provider managed; not disclosed'}
    configured_calls=int(env_value('MAX_API_CALLS',300));configured_tokens=int(env_value('MAX_TOTAL_TOKENS',300000))
    configured_cost=env_value('MAX_COST_USD') or env_value('GROQ_USD_CAP')
    usd_cap=args.usd_cap if args.usd_cap is not None else float(configured_cost) if configured_cost else None
    m['budgets']={'max_calls':min(args.max_calls or configured_calls,configured_calls,300) if args.preset=='smoke' else min(args.max_calls,configured_calls),'max_tokens':min(args.max_tokens or configured_tokens,configured_tokens,300000) if args.preset=='smoke' else min(args.max_tokens,configured_tokens),'usd_cap':usd_cap,'preset':args.preset}
    m['commands']=[' '.join(sys.argv)];m['dataset_manifest']=synthetic_manifest(examples)
    m['external_dataset_manifest']=external_manifest;m['selected_case_ids']=[e['id'] for e in examples]+[f'paired-{t["id"]}-{a}' for t,a,s in journeys]+['healthbench-'+e['id'] for e in external]
    if dataset_error:m['selected_case_ids']+=['healthbench-unavailable-'+str(i) for i in range(external_count)]
    m['limitations']=['Single frozen configured candidate; no model sweep, optimization or clinical effectiveness claim.','Synthetic holdout patients/templates disjoint from development/validation IDs; known scripted scenario families remain software regression evidence.','Live journey proposals are observed drafts with explicit human-simulated approval; backend truth and endpoint checks govern every transition.','A/B/C comparisons share synthetic behavior, capacity and evidence; no human usability study or reassurance measurement performed.','Standard/full presets not executed unless explicit budgets are supplied.']
    configuration_hashes(m);m['run_state']='running';m['status']='PARTIAL';atomic_json(run_dir/'manifest.json',m);atomic_json(run_dir/'dataset-manifest.json',{'synthetic':m['dataset_manifest'],'healthbench_adapted':external_manifest,'optional':{'medagentbench':'BLOCKED rights_unverified','mimic':'BLOCKED credentialed_data_excluded','synthea':'NOT_RUN project_generated_fhir_alternative'}})
    gateway=GroqGateway(run_dir=run_dir,model=m['model'],max_calls=m['budgets']['max_calls'],max_tokens=m['budgets']['max_tokens'],usd_cap=usd_cap)
    block=None
    if not read_json(run_dir/'capability.json'):
        try:atomic_json(run_dir/'capability.json',await gateway.probe())
        except Exception as exc:block=sanitized_error(exc);atomic_json(run_dir/'capability.json',{'status':'BLOCKED','error':block})
    print(json.dumps({'run_id':m['run_id'],'selected':len(m['selected_case_ids']),'model':gateway.model,'capability_block':block}),flush=True)
    if block:
        for cid in m['selected_case_ids']:
            if cid in ledger.ids:continue
            component=next((f for f in FUNCTIONS if cid.startswith(f+'-')),'external_suite' if cid.startswith('healthbench-') else 'journeys')
            ledger.append({'case_id':cid,'component':component,'evidence_mode':'adapted_external' if component=='external_suite' else 'live_groq_synthetic','started_at':now(),'finished_at':now(),'attempted':False,'evaluated':False,'score':{},'error':block})
    else:
        for i,example in enumerate(examples):
            if example['id'] in ledger.ids:continue
            ledger.append(await live_function(run_dir,m,gateway,example));print(json.dumps({'completed_function_case':example['id'],'budget':gateway.budget_status()}),flush=True)
        for example in external:
            if 'healthbench-'+example['id'] in ledger.ids:continue
            ledger.append(await live_external(run_dir,m,gateway,example));print(json.dumps({'completed_external':example['id'],'budget':gateway.budget_status()}),flush=True)
        for truth,arm,scenario in journeys:
            cid=f'paired-{truth["id"]}-{arm}'
            if cid in ledger.ids:continue
            ledger.append(await live_journey(run_dir,m,gateway,truth,arm,scenario));print(json.dumps({'completed_journey':cid,'budget':gateway.budget_status()}),flush=True)
        if dataset_error:
            for i in range(external_count):
                cid='healthbench-unavailable-'+str(i)
                if cid in ledger.ids:continue
                ledger.append({'case_id':cid,'component':'external_suite','evidence_mode':'adapted_external','started_at':now(),'finished_at':now(),'attempted':False,'evaluated':False,'score':{},'error':{'code':'dataset_access','message':'Run dataset fetch before the adapted external evaluation; no score invented.'}})
    m['budget_status']=gateway.budget_status();return finish(run_dir,m,ledger)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for command in ('offline','live','reports','validate'):
        q=sub.add_parser(command);q.add_argument('--run-id')
        if command=='offline':q.add_argument('--trajectories',type=int,default=1000);q.add_argument('--invalid-closures',type=int,default=500);q.add_argument('--split',choices=('development','validation','holdout'),default='holdout')
        if command=='live':
            q.add_argument('--preset',choices=('smoke','standard'),default='smoke');q.add_argument('--max-calls',type=int);q.add_argument('--max-tokens',type=int);q.add_argument('--usd-cap',type=float);q.add_argument('--model');q.add_argument('--cases',type=int);q.add_argument('--journeys',type=int);q.add_argument('--external',type=int)
    q=sub.add_parser('fetch');q.add_argument('--dataset',default='healthbench_adapted',choices=('healthbench_adapted',))
    args=p.parse_args()
    if args.command=='offline':offline(args)
    elif args.command=='live':asyncio.run(live(args))
    elif args.command=='fetch':
        from .healthbench import fetch
        print(json.dumps(fetch(),indent=2))
    else:
        if not args.run_id:p.error('--run-id is required')
        if not all(c.isalnum() or c in '-_' for c in args.run_id):p.error('invalid run ID')
        run_dir=ROOT/'reports/runs'/args.run_id
        print(json.dumps(build_reports(run_dir) if args.command=='reports' else validate_run(run_dir),indent=2))

if __name__=='__main__':main()
