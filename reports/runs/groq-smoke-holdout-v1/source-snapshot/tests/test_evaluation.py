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
