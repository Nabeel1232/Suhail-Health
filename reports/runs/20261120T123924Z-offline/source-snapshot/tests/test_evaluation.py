"""Independent checks for signed HealthBench aggregation and report integrity."""
import json
from pathlib import Path
import pytest
from evals.common import Ledger,digest,verify_chain,read_json,atomic_json
from evals.healthbench import calculate_score,aggregate_score,normalize,select_subset,validate_grades
from evals.reporting import count_records,status_for,usage_for
from evals.synthetic import function_cases,score_proposal


def test_healthbench_negative_weights_and_only_aggregate_clipping():
    rubric=[{'points':5},{'points':-9},{'points':3}]
    grades=[{'criteria_met':False},{'criteria_met':True},{'criteria_met':False}]
    assert calculate_score(rubric,grades)==-9/8
    # Clipping each example first would give .5; correct reference behavior is 0.
    assert aggregate_score([-9/8,1])==0
    assert aggregate_score([-.2,1])==pytest.approx(.4)
    assert calculate_score([{'points':-2}],[{'criteria_met':True}]) is None
    assert aggregate_score([]) is None
    with pytest.raises(ValueError):calculate_score(rubric,[])
    with pytest.raises(ValueError):calculate_score([{'points':1}],[{'criteria_met':'true'}])


def test_actual_healthbench_schema_preserved_and_rubric_not_candidate_input():
    row={'example_id':'original-id','prompt':[{'role':'user','content':'A public conversation'}],'rubrics':[{'criterion':'Give clear next steps','points':2,'tags':['axis:communication_quality']},{'criterion':'Invents reassurance','points':-4,'tags':['axis:accuracy']}],'example_tags':['theme:communication']}
    n=normalize(row)
    assert n['id']=='original-id' and n['rubrics'][1]['points']==-4
    assert n['messages']==row['prompt'] and 'rubrics' not in json.dumps(n['messages'])
    s,m=select_subset([n],1)
    assert s==[n] and m['selected'][0]['matched_actual_tags']
    with pytest.raises(ValueError):validate_grades(n,{'grades':[{'index':1,'criteria_met':True},{'index':0,'criteria_met':False}]})


def test_count_equations_keep_incorrect_outputs_in_completed_denominator():
    rs=[{'attempted':True,'evaluated':True,'score':{'passed':False}},{'attempted':True,'evaluated':False},{'attempted':False,'evaluated':False}]
    counts=count_records(rs)
    assert counts=={'selected':3,'attempted':2,'completed':1,'failed':1,'skipped':1,'task_passed':0,'task_incorrect':1}
    assert status_for(counts)=='PARTIAL'
    rubric=count_records([{'attempted':True,'evaluated':True,'score':{'rubric_score':.2,'passed':None}}])
    assert rubric['task_passed'] is None and rubric['task_incorrect'] is None


def test_unknown_provider_usage_stays_unknown():
    calls=[{'usage':{'input_tokens':2,'output_tokens':3},'latency_ms':100,'cost_usd':.01},{'usage':None,'latency_ms':200,'cost_usd':None}]
    u=usage_for(calls)
    assert u['api_calls']==2 and u['input_tokens'] is None and u['cost_usd'] is None
    assert usage_for([])['input_tokens']==0


def test_immutable_ledger_hashes_and_duplicate_guard(tmp_path):
    path=tmp_path/'cases.jsonl';ledger=Ledger(path)
    ledger.append({'case_id':'a','score':{'passed':True}})
    ledger.append({'case_id':'b','score':{'passed':False}})
    records=[json.loads(x) for x in path.read_text().splitlines()];verify_chain(records)
    with pytest.raises(ValueError):Ledger(path).append({'case_id':'a'})
    records[0]['score']['passed']=False
    with pytest.raises(AssertionError):verify_chain(records)


def test_disjoint_synthetic_splits_and_semantic_not_schema_score():
    dev=function_cases('pathway_router',6,'development');holdout=function_cases('pathway_router',6,'holdout')
    assert {e['case']['patient_id'] for e in dev}.isdisjoint({e['case']['patient_id'] for e in holdout})
    e=holdout[1];c=e['case']
    proposal={'case_id':c['id'],'case_version':1,'function':'pathway_router','recommended_action':'route_colorectal','source_references':c['source_references'],'extracted_facts':[],'evidence_ids':[]}
    score=score_proposal(e,proposal)
    assert not score['passed'] and not score['action_correct']


def test_arabic_policy_context_scores_without_english_fts_failure():
    from evals.common import FUNCTIONS
    for function in FUNCTIONS:
        example=next(e for e in function_cases(function) if e['case']['language']=='ar')
        c=example['case'];truth=example['truth']
        proposal={'case_id':c['id'],'case_version':1,'function':function,'policy_version':'demo-fit-v1','recommended_action':truth['recommended_action'],'source_references':c['source_references'],'extracted_facts':[{'field':k,'value':v,'source_reference':c['source_references'][0]} for k,v in truth['fact_fields'].items()],'missing_fields':['order_id'] if not c['order_id'] else [],'evidence_ids':truth['evidence_ids'],'patient_message':'فريق الرعاية سيشرح الخطوة التالية'}
        assert score_proposal(example,proposal)['passed']


def test_benchmark_aliases_preserve_process_precedence(monkeypatch):
    from evals.runner import benchmark_setting,requested_count
    monkeypatch.setenv('MAX_API_CALLS','17')
    monkeypatch.delenv('BENCHMARK_MAX_API_CALLS',raising=False)
    assert benchmark_setting('BENCHMARK_MAX_API_CALLS','MAX_API_CALLS',300)=='17'
    monkeypatch.setenv('BENCHMARK_MAX_API_CALLS','11')
    assert benchmark_setting('BENCHMARK_MAX_API_CALLS','MAX_API_CALLS',300)=='11'
    assert requested_count(0,6,6)==0
    assert requested_count(50,6,50)==6
    with pytest.raises(ValueError):requested_count(-1,6,6)


def test_matched_comparison_requires_same_valid_independent_pairs():
    from evals.reporting import matched_comparisons
    def record(pair,arm,complete,valid=True):
        return {'case_id':f'paired-{pair}-{arm}','paired_id':pair,'arm':arm,'evaluated':True,'independent_arm_store':valid,'execution_database':arm+'.sqlite3','input':{'case':{'patient_id':pair+'-p','order_id':pair+'-o'}},'journey':{'care_completed':complete}}
    records=[record('one','A',False),record('one','B',True),record('one','C',True),record('two','A',False),record('two','B',True),record('bad','B',True,False),record('bad','C',True,False)]
    result=matched_comparisons(records)
    assert result['A_B']['matched_pairs']==2 and result['A_B']['difference']==1
    assert result['B_C']['matched_pairs']==1 and result['B_C']['difference']==0
