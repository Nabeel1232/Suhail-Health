"""Resume only pending selected IDs with the SAME immutable model and spending ledger.

Operational correction after observed 8,000 TPM account limit. This wrapper does
not change model, model parameters, prompts, retrieval, scorers, case inputs or
selected ID denominators. It changes dispatch timing and execution order only.
"""
from pathlib import Path
import sys,asyncio,time,json,hashlib,shutil,argparse
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from evals import runner
from evals.common import read_json,atomic_json,file_hash,digest,now,rows,Ledger
from evals.healthbench import load,select_subset
from services.agents.gateway import GroqGateway
RUN_DIR=Path(__file__).resolve().parent
INITIAL=read_json(RUN_DIR/'manifest.json')
assert INITIAL['run_id']=='groq-smoke-holdout-v1' and not INITIAL.get('finished_at')
# Frozen inference/scoring data remain exact. Current backend corrections are
# recorded separately before the first full-journey command executes.
for rel,expected in INITIAL['source_snapshot']['files'].items():
    if rel.startswith(('services/agents/','evals/','pathways/','contracts/')) and rel not in {'evals/domain_harness.py','evals/runner.py','contracts/README.md'}:
        assert file_hash(ROOT/rel)==expected, 'Frozen candidate changed: '+rel
backend={str(p.relative_to(ROOT)):file_hash(p) for p in (ROOT/'services/api').glob('*.py')}
for rel in backend:
    target=RUN_DIR/'backend-source-at-isolation-resume'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
ADJUSTMENT={'id':'independent-arm-store-resume-v3','timestamp':now(),'reason':'Observed account 8000 tokens/minute; avoid repeated429s and preserve allsix-function coverage under existing conservativebudget','dispatch_interval_seconds':30,'selected_id_set_unchanged':True,'model_prompt_rag_scorer_data_unchanged':True,'execution_order':'firstremainingpreselectedpair1rejected-handoffA/BvalidatedinseparateSQLitearmstoresbeforeC; invalidfirstpairpreservedandexcludedfrommatchedcomparison; thenremaininglayersunderoriginalbudget','initial_selected_case_ids':INITIAL['selected_case_ids'],'backend_hash_before_journey_execution':digest(backend),'backend_files':backend,'wrapper_sha256':file_hash(Path(__file__)),'provenance_only_harness_revision_sha256':file_hash(ROOT/'evals/domain_harness.py'),'updated_application_contract_sha256':file_hash(ROOT/'contracts/README.md'),'isolated_journey_runner_sha256':file_hash(ROOT/'evals/runner.py'),'prior_provider_records':len(rows(RUN_DIR/'provider-calls.jsonl')),'latency_note':'Afterresume measured gateway latency includes local pacing queue wait; scheduler-dispatches.jsonl records dispatch timing.'}
atomic_json(RUN_DIR/'operational-adjustments.json',ADJUSTMENT)
# Preserve original manifest selection ordering and dataset checksum. Dispatch
# ordering is separate provenance and never changes denominators or original IDs.
original_atomic=runner.atomic_json

def preserve_manifest(path,data):
    if Path(path)==RUN_DIR/'manifest.json':
        data['selected_case_ids']=INITIAL['selected_case_ids']
        data['dataset_manifest']=INITIAL['dataset_manifest']
        data['operational_adjustments']=INITIAL.get('operational_adjustments',[])+[ADJUSTMENT]
        data['limitations']=list(dict.fromkeys(data.get('limitations',[])+['Observed429s consume conservative unknown-usage reservations; all failed calls retained.','Operational30-second dispatch pacing and round-robin pending-case order added after observing8000TPM; model/prompt/RAG/scoring/inputIDs unchanged.','Backend security corrections before fulljourneys recorded in backend-source-at-resume; model-only responses use the original frozen agentcode.','Postresume latency includes explicit local pacing; no pure network-latency claim.']))
    return original_atomic(path,data)
runner.atomic_json=preserve_manifest

def existing_run(kind,run_id=None):
    assert kind=='live' and run_id==INITIAL['run_id']
    return RUN_DIR,read_json(RUN_DIR/'manifest.json')
runner.new_run=existing_run
runner.synthetic_manifest=lambda examples: INITIAL['dataset_manifest']
original_cases=runner.function_cases

def round_robin(function,count=6,split='holdout'):
    assert count==6
    position=runner.FUNCTIONS.index(function)
    return [original_cases(f,count,split)[position] for f in runner.FUNCTIONS]
runner.function_cases=round_robin
state={'ledger':None,'priority_external_done':any(r['component']=='external_suite' for r in rows(RUN_DIR/'cases.jsonl')),'last_dispatch':0.0}

class TrackedLedger(Ledger):
    def __init__(self,path):super().__init__(path);state['ledger']=self
runner.Ledger=TrackedLedger
original_init=GroqGateway.__init__

def init_with_pacing(self,*args,**kwargs):
    original_init(self,*args,**kwargs)
    if self.client is None:return
    original_create=self.client.chat.completions.create
    async def create(*a,**kw):
        delay=max(0.0,30-(time.monotonic()-state['last_dispatch']))
        while delay>0:
            wait=min(25.0,delay);await asyncio.sleep(wait);delay-=wait
        state['last_dispatch']=time.monotonic()
        with (RUN_DIR/'scheduler-dispatches.jsonl').open('a') as f:
            f.write(json.dumps({'dispatched_at':now(),'model':kw.get('model'),'input_hash':hashlib.sha256(json.dumps(kw.get('messages'),ensure_ascii=False).encode()).hexdigest(),'minimum_dispatch_interval_seconds':30})+'\n')
        return await original_create(*a,**kw)
    self.client.chat.completions.create=create
GroqGateway.__init__=init_with_pacing
original_function=runner.live_function
original_external=runner.live_external
original_journey=runner.live_journey
state['priority_journey_done']=any(r.get('case_id')=='paired-trajectory-holdout-500001-C' for r in rows(RUN_DIR/'cases.jsonl'))

async def ensure_priority_journey(run_dir,m,g):
    if state['priority_journey_done']:return
    from evals.synthetic import trajectory_truth
    for arm in ('A','B','C'):
        truth=trajectory_truth(500001);case_id=f'paired-{truth["id"]}-{arm}'
        if case_id in state['ledger'].ids:continue
        if arm=='C':
            earlier=rows(RUN_DIR/'cases.jsonl')
            baselines=[next((r for r in earlier if r.get('case_id')==f'paired-{truth["id"]}-{a}'),None) for a in ('A','B')]
            assert all(r and r.get('evaluated') and r.get('independent_arm_store') for r in baselines),'Baseline isolationvalidation failed; noCproviderdispatch permitted.'
            assert baselines[0]['execution_database']!=baselines[1]['execution_database']
            assert baselines[0]['input']['case']['patient_id']==baselines[1]['input']['case']['patient_id']
            assert baselines[0]['input']['case']['order_id']==baselines[1]['input']['case']['order_id']
            atomic_json(RUN_DIR/'priority-baseline-independence.json',{'validated_at':now(),'paired_id':truth['id'],'same_patient_order_truth':True,'independent_actual_databases':True,'baseline_case_ids':[r['case_id'] for r in baselines],'baseline_output_case_ids':[r['output']['case_id'] for r in baselines],'before_any_C_request_for_this_pair':True})
        record=await original_journey(run_dir,m,g,truth,arm,'rejected_handoff')
        record['execution_phase']='independent-arm-store-resume-v3'
        actual=read_json(RUN_DIR/'actual-backend-first-import.json')
        record['actual_backend_source_hash']=actual['backend_hash'] if actual else None
        state['ledger'].append(record)
        print(json.dumps({'priority_matched_journey':case_id,'evaluated':record['evaluated'],'error':record.get('error'),'budget':g.budget_status()}),flush=True)
    state['priority_journey_done']=True

async def function(run_dir,m,g,example):
    await ensure_priority_journey(run_dir,m,g)
    existing=rows(RUN_DIR/'cases.jsonl')
    covered={r['component'] for r in existing if r.get('evaluated') and r['component'] in runner.FUNCTIONS}
    if len(covered)==6 and not state['priority_external_done']:
        _,data=load();selected,_=select_subset(data,12)
        first=selected[0]
        if 'healthbench-'+first['id'] not in state['ledger'].ids:
            record=await original_external(run_dir,m,g,first);record['execution_phase']='paced-resume-v1';state['ledger'].append(record)
            print(json.dumps({'priority_external_case':first['id'],'budget':g.budget_status()}),flush=True)
        state['priority_external_done']=True
    record=await original_function(run_dir,m,g,example);record['execution_phase']='paced-resume-v1';return record

async def external(*args,**kwargs):
    await ensure_priority_journey(args[0],args[1],args[2])
    record=await original_external(*args,**kwargs);record['execution_phase']='paced-resume-v1';return record

async def journey(*args,**kwargs):
    run_dir,m,g,truth,arm,scenario=args
    allowance=g.budget_status()
    if arm=='C' and allowance['max_tokens']-allowance['charged_tokens']<35000:
        return {'case_id':f'paired-{truth["id"]}-{arm}','component':'journeys','paired_id':truth['id'],'scenario':scenario,'arm':arm,'evidence_mode':'live_groq_synthetic','started_at':now(),'finished_at':now(),'attempted':False,'evaluated':False,'score':{},'error':{'code':'budget_insufficient_for_full_journey','message':'Remainingconservativeallowancecannotreserve35000tokensforanothercomplete6-functionjourney; noproviderrequestdispatched.'},'execution_phase':'independent-arm-store-resume-v3'}
    record=await original_journey(*args,**kwargs);record['execution_phase']='independent-arm-store-resume-v3';record['backend_source_hash']=digest(backend);return record
runner.live_function=function;runner.live_external=external;runner.live_journey=journey
args=argparse.Namespace(run_id=INITIAL['run_id'],preset='smoke',max_calls=300,max_tokens=300000,usd_cap=None,model=None,cases=None,journeys=None,external=None)
try:asyncio.run(runner.live(args))
except KeyboardInterrupt:print('Evaluation paused; immutable records and conservative reservations preserved.',file=sys.stderr)
