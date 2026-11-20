"""Project-generated synthetic cases from independent scenario truth.

No real patient information and no clinical deadlines. Seeds, patient IDs and
scenario families are disjoint across development, validation and holdout.
"""
from __future__ import annotations
import random,copy
from .common import FUNCTIONS,digest
GENERATOR_VERSION='suhail-synthetic-v1'
SEEDS={'development':101,'validation':202,'holdout':90317}
SCENARIOS=('normal_completion','unsupported_pathway','identity_conflict','corrected_result','wrong_evidence','unanswered_consultation','failed_understanding','access_barrier','rejected_handoff','expired_handoff','no_slots','cancelled_visit','no_show','urgent_timeout','provider_outage','duplicate_reordered','unauthorized_access','onward_care','informed_decline','unable_to_contact')

def base_case(index:int,split='holdout')->dict:
    if split not in SEEDS:raise ValueError('invalid_split')
    prefix=f'SYN-{split.upper()}-{index:05d}'
    return {'id':prefix,'case_id':prefix,'version':1,'patient_id':prefix+'-P','patient_name':'Synthetic Participant '+str(index),'source_organization':'screening-center','order_id':prefix+'-O','result_version':1,'test_code':'FIT_POS','pathway':'colorectal-fit','policy_version':'demo-fit-v1','owner':'navigation-team','backup_queue':'clinical-backup','identity_verified':True,'quarantine_reason':None,'urgent':False,'trusted_urgent':False,'language':'ar' if index%4==3 else 'en','disposition':'open','residual_need':True,'next_action':'Arrange clinician-reviewed diagnostic follow-up','source_references':['synthetic://'+prefix+'/result'],'evidence':[],'tasks':[{'id':prefix+'-T','type':'investigation','required':True,'status':'required','assignee':'navigation-team','next_action':'Arrange diagnostic assessment','due_at':'2026-11-16T09:00:00+00:00'}],'handoffs':[],'appointments':[],'consultations':[],'communications':[],'milestones':[],'delay_reasons':[]}

def function_cases(function:str,count=6,split='holdout')->list[dict]:
    if function not in FUNCTIONS:raise ValueError('unknown_function')
    out=[]
    for i in range(count):
        c=base_case(SEEDS[split]+1000*FUNCTIONS.index(function)+i,split);variant=i%6
        truth={'recommended_action':None,'fact_fields':{},'evidence_ids':[],'review_required':False}
        if function=='intake':
            truth['recommended_action']='review_pathway'
            if variant==1:c['identity_verified']=False;c['quarantine_reason']='identity_conflict';truth.update(recommended_action='review_identity',review_required=True)
            if variant==2:c['order_id']='';truth['review_required']=True
            if variant==3:c['result_version']=2;c['correction']=True
            if variant==4:c['test_code']='UNSUPPORTED'
            truth['fact_fields']={k:str(c[k]) for k in ('patient_id','order_id','test_code','result_version') if c.get(k) not in (None,'')}
        elif function=='pathway_router':
            if variant in (1,3,5):c['test_code']=['OTHER_TEST','UNKNOWN','FIT_NEG'][variant//2];truth.update(recommended_action='review_pathway',review_required=True)
            else:truth['recommended_action']='route_colorectal'
        elif function=='safety_escalation':
            if variant in (0,2,4):c['trusted_urgent']=True;c['urgent']=True;truth['recommended_action']='staff_urgent_review'
            else:c['context_uncertain']=True;truth.update(recommended_action='request_clinician',review_required=True)
            if variant==4:c['model_unavailable_context']='The deterministic urgent flag already created staff escalation.'
        elif function=='patient_navigator':
            if variant in (1,3,5):c['patient_question']='Can a clinician explain this result and next step?';c['consultations']=[{'type':'patient_to_clinician','question':c['patient_question'],'status':'open'}];truth['recommended_action']='request_clinician'
            else:truth['recommended_action']='explain_next_step'
            if variant==4:c['understanding']='needs_help'
        elif function=='coordination':
            if variant in (1,2,4):
                status={1:'no_show',2:'cancelled',4:'no_slots'}[variant];c['appointments']=[{'id':c['id']+'-APT','status':status,'provider':'provider-a'}];c['delay_reasons']=[status];truth['recommended_action']='recover_appointment'
            elif variant==3:c['handoffs']=[{'id':c['id']+'-H','status':'rejected','receiver':'provider-a'}];truth['recommended_action']='recover_appointment'
            else:truth['recommended_action']='prepare_handoff'
        elif function=='closure_evidence':
            refs=[]
            if variant in (0,2,4):
                c['tasks']=[]
                for t in ('investigation','reviewed_outcome','patient_updated'):
                    eid=c['id']+'-'+t
                    c['evidence'].append({'id':eid,'type':t,'patient_id':c['patient_id'],'order_id':c['order_id'],'result_version':c['result_version'],'verification':'verified','status':'current','source':'synthetic-provider','reference':'synthetic://'+eid});refs.append(eid)
                c['closure_check']={'allowed':True,'missing':[],'endpoint':'diagnostic_follow_up','policy_version':'demo-fit-v1'};truth['recommended_action']='closure_review';truth['evidence_ids']=refs
            else:
                c['closure_check']={'allowed':False,'missing':['investigation','reviewed_outcome','patient_updated'],'endpoint':'diagnostic_follow_up','policy_version':'demo-fit-v1'};truth['recommended_action']='collect_evidence'
                if variant==3:c['evidence']=[{'id':c['id']+'-WRONG','type':'investigation','patient_id':'WRONG-PATIENT','order_id':c['order_id'],'result_version':1,'verification':'pending','status':'current','reference':'synthetic://wrong-evidence'}]
                if variant==5:c['evidence']=[{'id':c['id']+'-OLD','type':'investigation','patient_id':c['patient_id'],'order_id':c['order_id'],'result_version':0,'verification':'verified','status':'superseded','reference':'synthetic://old-evidence'}]
        out.append({'id':f'{function}-{split}-{i:03d}','component':function,'case':c,'truth':truth,'split':split,'template_family':f'{split}-{function}-{variant}','generator_version':GENERATOR_VERSION})
    return out

def score_proposal(example:dict,proposal:dict)->dict:
    """Score independent gold facts/action/evidence, never schema validity alone."""
    t=example['truth'];c=example['case'];assertions=[]
    def check(name,value):assertions.append({'name':name,'passed':bool(value)})
    check('action_matches_scenario_truth',proposal.get('recommended_action')==t['recommended_action'])
    check('case_and_version_match',proposal.get('case_id')==c['id'] and proposal.get('case_version')==c['version'])
    check('function_matches',proposal.get('function')==example['component'])
    check('policy_version_matches',proposal.get('policy_version')=='demo-fit-v1')
    known_refs=set(c['source_references'])|{str(e.get('reference')) for e in c['evidence']}|{str(e.get('id')) for e in c['evidence']}
    
    try:
        from services.agents.retrieval import retrieve
        policy=retrieve('FIT follow-up ownership consultation evidence',language=c.get('language','en'))
        known_refs|={x['citation'] for x in policy}|{x['source'] for x in policy}
    except ImportError:pass
    citations=set(proposal.get('source_references',[]));check('citations_nonempty_and_supported',bool(citations) and citations<=known_refs and bool(citations&set(c['source_references'])))
    facts={x.get('field'):x.get('value') for x in proposal.get('extracted_facts',[])}
    expected=t['fact_fields'];matches=sum(str(facts.get(k))==v for k,v in expected.items())
    precision=matches/len(facts) if facts else (1.0 if not expected else 0.0);recall=matches/len(expected) if expected else None
    if expected:
        check('all_known_facts_extracted',matches==len(expected))
        check('fact_source_spans_supported',all(x.get('source_reference') in known_refs for x in proposal.get('extracted_facts',[])))
        if not c.get('order_id'):check('missing_order_identified','order_id' in proposal.get('missing_fields',[]))
    if example['component']=='closure_evidence':
        check('evidence_ids_match_current_verified_case_evidence',set(proposal.get('evidence_ids',[]))==set(t['evidence_ids']))
    if example['component']=='patient_navigator':
        check('plain_language_message_present',bool(str(proposal.get('patient_message','')).strip()))
        if c.get('language')=='ar':
            import re
            check('arabic_message_present',bool(re.search('[\u0600-\u06ff]',proposal.get('patient_message',''))))
    return {'passed':all(a['passed'] for a in assertions),'assertions':assertions,'field_precision':precision if expected else None,'field_recall':recall,'action_correct':proposal.get('recommended_action')==t['recommended_action'],'evidence_precision':(len(set(proposal.get('evidence_ids',[]))&set(t['evidence_ids']))/len(proposal.get('evidence_ids',[])) if proposal.get('evidence_ids') else (1.0 if not t['evidence_ids'] else 0.0)) if example['component']=='closure_evidence' else None,'review_or_abstention':proposal.get('recommended_action') in ('review_identity','review_pathway','request_clinician','collect_evidence')}

def trajectory_truth(index:int,split='holdout')->dict:
    scenario=SCENARIOS[index%len(SCENARIOS)];c=base_case(index+SEEDS[split],split)
    expected={'scenario':scenario,'quarantined':scenario in ('unsupported_pathway','identity_conflict'),'completed_required_care':scenario=='normal_completion','owner_continuity':True,'residual_need':scenario!='normal_completion'}
    return {'id':f'trajectory-{split}-{index:05d}','component':'software_suite','case':c,'truth':expected,'split':split,'generator_version':GENERATOR_VERSION}

def manifest(examples:list[dict])->dict:
    return {'id':'suhail_project_synthetic','generator_version':GENERATOR_VERSION,'revision':digest(examples),'sha256':digest(examples),'license':'project_generated_no_upstream_license_claim','provenance':'project-generated fictional participants and known scenario truth','split_seeds':SEEDS,'selected_case_ids':[e['id'] for e in examples],'scenario_families':list(SCENARIOS),'not_clinical_ground_truth':True}
