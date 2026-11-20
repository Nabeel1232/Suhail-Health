"""Render every artifact from executed ledgers; validate counts and live lineage."""
from __future__ import annotations
import csv,html,json,statistics,hashlib,math,sqlite3
from pathlib import Path
from collections import Counter
import jsonschema
from .common import ROOT,FUNCTIONS,canonical,digest,rows,read_json,atomic_json,verify_chain
from .healthbench import aggregate_score,calculate_score,validate_grades
COMPONENTS=FUNCTIONS+('journeys','software_suite','external_suite')

def percentile(values,p):
    if not values:return None
    v=sorted(values);return v[max(0,math.ceil(len(v)*p)-1)]

def count_records(records:list[dict])->dict:
    a=[r for r in records if r.get('attempted')]
    c=[r for r in a if r.get('evaluated')]
    f=[r for r in a if not r.get('evaluated')]
    return {'selected':len(records),'attempted':len(a),'completed':len(c),'failed':len(f),'skipped':len(records)-len(a),'task_passed':sum(r.get('score',{}).get('passed') is True for r in c) if any(type(r.get('score',{}).get('passed')) is bool for r in c) else None,'task_incorrect':sum(r.get('score',{}).get('passed') is False for r in c) if any(type(r.get('score',{}).get('passed')) is bool for r in c) else None}

def status_for(counts):
    if not counts['selected']:return 'NOT_RUN'
    if not counts['attempted']:return 'BLOCKED'
    if not counts['completed']:return 'BLOCKED'
    if counts['failed'] or counts['skipped']:return 'PARTIAL'
    return 'COMPLETE'

def usage_for(calls:list[dict])->dict:
    unknown=any(not c.get('usage') for c in calls)
    inp=None if unknown else sum(c['usage']['input_tokens'] for c in calls)
    out=None if unknown else sum(c['usage']['output_tokens'] for c in calls)
    costs=[c.get('cost_usd') for c in calls]
    latency=[float(c['latency_ms']) for c in calls if c.get('latency_ms') is not None]
    return {'api_calls':len(calls),'input_tokens':inp,'output_tokens':out,'cost_usd':sum(costs) if all(x is not None for x in costs) else None,'latency_ms_p50':percentile(latency,.5),'latency_ms_p95':percentile(latency,.95),'price_map_version':next((c.get('price_map_version') for c in calls if c.get('price_map_version')),None),'budget_reason':None}

def provenance(manifest,records,component):
    dataset=manifest.get('dataset_manifest',{})
    hb=manifest.get('external_dataset_manifest',{}) if component=='external_suite' else {}
    return {'code_revision':manifest['source_snapshot']['code_revision'],'dirty_state_hash':manifest['source_snapshot']['dirty_state_hash'],'provider':manifest.get('provider') if manifest['kind']=='live' else None,'model':manifest.get('model') if manifest['kind']=='live' else None,'grader_model':manifest.get('grader_model') if component=='external_suite' else None,'dataset':hb.get('id',dataset.get('id','suhail_project_synthetic')),'dataset_revision':hb.get('revision',dataset.get('revision')),'dataset_checksum':hb.get('sha256',dataset.get('sha256')),'license':hb.get('license',dataset.get('license')),'selected_case_ids':[r['case_id'] for r in records],'prompt_hash':manifest.get('prompt_hash'),'retrieval_hash':manifest.get('retrieval_hash'),'policy_hash':manifest.get('policy_hash'),'scorer_version':manifest['scorer_version'],'sampling_parameters':manifest.get('parameters',{})}

def component_report(manifest,records,calls,component):
    cr=[r for r in records if r['component']==component]
    ids={r['case_id'] for r in cr}
    pc=[c for c in calls if c.get('metadata',{}).get('case_id') in ids]
    counts=count_records(cr);status=status_for(counts)
    mode='adapted_external' if component=='external_suite' else 'live_groq_synthetic' if manifest['kind']=='live' and component!='software_suite' else 'deterministic_software'
    reason=next((r.get('error',{}).get('code') for r in cr if r.get('error')),None)
    evaluated=[r for r in cr if r.get('evaluated')]
    metrics=[{'name':'task_accuracy','value':counts['task_passed']/counts['completed'] if counts['completed'] and counts['task_passed'] is not None else None,'unit':'fraction','denominator':counts['completed'] or None,'method':'Independent scenario truth; incorrect evaluated answers remain in denominator.'}]
    for metric in ('action_correct','field_precision','field_recall','evidence_precision','review_or_abstention'):
        values=[float(r['score'][metric]) for r in evaluated if r.get('score',{}).get(metric) is not None]
        if values:metrics.append({'name':metric,'value':statistics.mean(values),'unit':'fraction','denominator':len(values),'method':'Independent known synthetic truth; no grader model.'})
    if component=='external_suite':
        values=[r['score']['rubric_score'] for r in evaluated if r.get('score',{}).get('rubric_score') is not None]
        metrics=[{'name':'adapted_healthbench_rubric_score','value':aggregate_score(values),'unit':'fraction','denominator':len(values) or None,'method':'Signed weights / total positive weights per example; clip aggregate mean to [0,1]. Groq batched rubric-grader estimate; not official HealthBench.'}]
    if component=='journeys':
        for arm in ('A','B','C'):
            records_arm=[r for r in evaluated if r.get('arm')==arm]
            if records_arm:
                metrics.append({'name':f'arm_{arm}_required_care_completed','value':sum(bool(r.get('journey',{}).get('care_completed')) for r in records_arm)/len(records_arm),'unit':'fraction','denominator':len(records_arm),'method':'Automated synthetic behavior/capacity scenario; not patient outcome evidence.'})
    errors=[{'case_id':r['case_id'],'code':r['error']['code'],'message':r['error']['message']} for r in cr if r.get('error')][:12]
    limits=list(manifest.get('limitations',[]))
    if mode=='adapted_external':limits+=['Public deterministic thematic subset, not representative overall HealthBench.','Candidate and grader may share model/family; no independent human review performed.','Batched rubric grading differs from the reference one-criterion-per-request protocol.']
    if component in FUNCTIONS and manifest['kind']!='live':limits+=['Live function inference was not run in this deterministic software run.']
    if component=='journeys':limits+=['Scripted authenticated role actions and known evidence use synthetic behavior and service capacity; no clinical effectiveness or reassurance claim.','A reminders; B full workflow templates; C same workflow plus bounded live proposals. Unexecuted arms have zero selected cases and no outcome estimate.']
    return {'schema_version':'1.0','run_id':manifest['run_id'],'status':status,'reason_code':reason,'evidence_mode':mode,'component':component,'started_at':min((r['started_at'] for r in cr),default=None),'finished_at':max((r['finished_at'] for r in cr),default=None),'provenance':provenance(manifest,cr,component),'counts':counts,'metrics':metrics,'usage':usage_for(pc),'errors':errors,'limitations':list(dict.fromkeys(limits)),'reproduce_command':f'python -m evals.runner {manifest["kind"]} --run-id NEW_RUN_ID' if manifest['kind'] in ('live','offline') else None}

def render_md(report):
    c=report['counts'];u=report['usage']
    lines=[f'# Suhail Health · {report["component"].replace("_"," ")}',f'Run `{report["run_id"]}` · **{report["status"]}** · {report["evidence_mode"]}',f'Selected {c["selected"]}; attempted {c["attempted"]}; evaluated {c["completed"]}; failed {c["failed"]}; skipped {c["skipped"]}.',f'Task passed {c["task_passed"] if c["task_passed"] is not None else "Not measured"}; incorrect {c["task_incorrect"] if c["task_incorrect"] is not None else "Not measured"}.','', '| Measurement | Value | Denominator | Method |','|---|---:|---:|---|']
    for m in report['metrics']:lines.append(f'| {m["name"]} | {m["value"] if m["value"] is not None else "Not measured"} | {m["denominator"] if m["denominator"] is not None else "Not measured"} | {m["method"]} |')
    lines+=['',f'API calls: {u["api_calls"]}; input tokens: {u["input_tokens"] if u["input_tokens"] is not None else "Unknown"}; output tokens: {u["output_tokens"] if u["output_tokens"] is not None else "Unknown"}; cost USD: {u["cost_usd"] if u["cost_usd"] is not None else "Unknown"}.',f'Model: {report["provenance"]["model"] or "Not run"}; dataset revision: {report["provenance"]["dataset_revision"] or "Unknown"}.','','## Limits','']+['- '+x for x in report['limitations']]
    if report['errors']:lines+=['','## Sanitized errors','']+['- '+e['case_id']+': '+e['code']+' — '+e['message'] for e in report['errors']]
    return '\n\n'.join(lines)+'\n'

def build_reports(run_dir:Path)->dict:
    m=read_json(run_dir/'manifest.json');records=rows(run_dir/'cases.jsonl');calls=rows(run_dir/'provider-calls.jsonl')
    reports={component:component_report(m,records,calls,component) for component in COMPONENTS}
    schema=read_json(ROOT/'evals/report.schema.json')
    for comp,r in reports.items():
        jsonschema.validate(r,schema)
        path=run_dir/'agents'/comp if comp in FUNCTIONS else run_dir/comp
        atomic_json(path.with_suffix('.json'),r);path.with_suffix('.md').write_text(render_md(r))
        with path.with_suffix('.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=('name','value','unit','denominator','method'));writer.writeheader()
            for metric in r['metrics']:writer.writerow({k:v for k,v in metric.items() if k!='note'})
        metric_rows=''.join('<tr><td>'+html.escape(metric['name'])+'</td><td>'+html.escape(str(metric['value']) if metric['value'] is not None else 'Not measured')+'</td><td>'+str(metric['denominator'] if metric['denominator'] is not None else 'Not measured')+'</td><td>'+html.escape(metric['method'])+'</td></tr>' for metric in r['metrics'])
        path.with_suffix('.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suhail Health · '+html.escape(comp)+'</title><style>body{font:16px system-ui;margin:32px;color:#143d3c;background:#f4f8f7}main{max-width:1000px;margin:auto;background:white;padding:28px;border:1px solid #d4e2de;border-radius:12px;overflow:auto}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #d4e2de}th{background:#e8f3f0}pre{white-space:pre-wrap}</style><main><p>Suhail Health · Guiding every result to care</p><h1>'+html.escape(comp.replace('_',' '))+'</h1><p>'+html.escape(r['run_id'])+' · '+r['status']+' · '+r['evidence_mode']+'</p><table><tr><th>Measurement</th><th>Value</th><th>Denominator</th><th>Method</th></tr>'+metric_rows+'</table><h2>Execution counts and usage</h2><pre>'+html.escape(json.dumps({'counts':r['counts'],'usage':r['usage']},indent=2))+'</pre><h2>Limits</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in r['limitations'])+'</ul></main></html>')
    journeys=[r for r in records if r['component']=='journeys']
    fields=('case_id','arm','scenario','attempted','evaluated','passed','notification','understanding','consultation','accepted_handoffs','attendance','care_completed','residual_need','delay_reasons')
    with (run_dir/'journeys.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in journeys:
            j=r.get('journey',{});w.writerow({'case_id':r['case_id'],'arm':r.get('arm','B'),'scenario':r.get('scenario'),'attempted':r.get('attempted'),'evaluated':r.get('evaluated'),'passed':r.get('score',{}).get('passed'),**{k:j.get(k) for k in fields[6:]}})
    atomic_json(run_dir/'journey-records.json',journeys)
    counts=count_records(records);status=status_for(counts)
    summary={'schema_version':'1.0','run_id':m['run_id'],'status':status,'kind':m['kind'],'started_at':m['started_at'],'finished_at':m.get('finished_at'),'counts':counts,'usage':usage_for(calls),'budget':m.get('budget_status',m.get('budgets',{})),'components':reports,'limitations':m.get('limitations',[]),'optional_workstreams':{'expert_review':{'status':'NOT_RUN','reason':'No qualified independent review performed'},'medagentbench':{'status':'BLOCKED','reason':'rights_unverified; original container/scorer not established; no records uploaded'},'mimic_iv_ed':{'status':'BLOCKED','reason':'credentialed restricted data excluded from default remote path'},'synthea':{'status':'NOT_RUN','alternative':'Project-generated synthetic FHIR fixtures'}}}
    atomic_json(run_dir/'summary.json',summary)
    md=['# Suhail Health execution report',f'Run `{m["run_id"]}` · **{status}**',f'{counts["selected"]} selected; {counts["attempted"]} attempted; {counts["completed"]} evaluated; {counts["failed"]} failed; {counts["skipped"]} skipped.','Software execution, live inference and adapted conversation rubric estimates are separate evidence layers.','| Component | Evidence | Status | Attempted / selected | Evaluated | Incorrect |','|---|---|---|---:|---:|---:|']
    for comp,r in reports.items():md.append(f'| {comp} | {r["evidence_mode"]} | {r["status"]} | {r["counts"]["attempted"]} / {r["counts"]["selected"]} | {r["counts"]["completed"]} | {r["counts"]["task_incorrect"] if r["counts"]["task_incorrect"] is not None else "Not measured"} |')
    md+=['','Actual request usage: `'+canonical(summary['usage'])+'`.','Optional expert review was not performed. MedAgentBench/MIMIC are blocked or excluded; no restricted records were sent.','Public data and model benchmarks do not establish medical validation. Synthetic workflow outcomes do not establish patient impact.','','## Reproduce','',f'`python -m evals.runner reports --run-id {m["run_id"]}`',f'`python -m evals.runner validate --run-id {m["run_id"]}`']
    (run_dir/'summary.md').write_text('\n\n'.join(md)+'\n')
    with (run_dir/'metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=('component','evidence_mode','name','value','unit','denominator','method'));w.writeheader()
        for comp,r in reports.items():
            for metric in r['metrics']:w.writerow({'component':comp,'evidence_mode':r['evidence_mode'],**{k:v for k,v in metric.items() if k!='note'}})
    esc=html.escape
    table=''.join(f'<tr><td>{esc(comp)}</td><td>{esc(r["evidence_mode"])}</td><td>{r["status"]}</td><td>{r["counts"]["attempted"]}/{r["counts"]["selected"]}</td><td>{r["counts"]["completed"]}</td><td>{r["counts"]["task_incorrect"] if r["counts"]["task_incorrect"] is not None else "Not measured"}</td></tr>' for comp,r in reports.items())
    chart=''.join(f'<div class="barrow"><span>{esc(comp)}</span><meter min="0" max="{max(1,r["counts"]["selected"])}" value="{r["counts"]["completed"]}" aria-label="{esc(comp)} evaluated cases"></meter><b>{r["counts"]["completed"]}/{r["counts"]["selected"]}</b></div>' for comp,r in reports.items() if r['counts']['selected'])
    (run_dir/'summary.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suhail Health · {esc(m['run_id'])}</title><style>body{{font:16px system-ui,sans-serif;margin:0;background:#f4f8f7;color:#143d3c}}header{{background:#143d3c;color:white;padding:32px}}main{{max-width:1100px;margin:auto;padding:28px}}.tile{{background:white;border:1px solid #d4e2de;border-radius:12px;padding:24px;margin:20px 0;overflow:auto}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #d4e2de}}th{{background:#e8f3f0}}.barrow{{display:flex;gap:14px;align-items:center;margin:14px 0}}.barrow span{{width:180px}}meter{{flex:1;accent-color:#006568}}a{{color:#006568}}small{{line-height:1.6}}@media print{{body{{background:white}}header{{background:white;color:#143d3c}}}}</style><header><strong>Suhail Health</strong><h1>Executed evaluation report</h1><p>{esc(m['run_id'])} · {status}</p></header><main><p>{counts['attempted']} attempted of {counts['selected']} selected; {counts['completed']} evaluated; {counts['failed']} failed; {counts['skipped']} skipped.</p><section class="tile"><h2>Evidence layers</h2><table><thead><tr><th>Component</th><th>Evidence</th><th>Status</th><th>Attempted / selected</th><th>Evaluated</th><th>Incorrect</th></tr></thead><tbody>{table}</tbody></table></section><section class="tile"><h2>Measured execution coverage</h2>{chart}<small>Counts represent executed records. Evaluated incorrect responses remain in the denominator. Coverage is separate from correctness.</small></section><section class="tile"><h2>Request usage</h2><pre>{esc(json.dumps(summary['usage'],indent=2))}</pre></section><section class="tile"><h2>Limits and provenance</h2><p>Public data and model benchmarks do not establish clinical validation. Synthetic trajectories do not establish patient outcome improvement. Adapted HealthBench uses a Groq grader and thematic subset, with possible same-model bias.</p><p>Independent expert review: Not run. MedAgentBench: blocked pending rights, original container and scorer. MIMIC: excluded from remote path.</p><p>Frozen source hash: <code>{esc(m['source_snapshot']['dirty_state_hash'])}</code></p><p><a href="summary.json">JSON report</a> · <a href="metrics.csv">Metrics CSV</a> · <a href="summary.md">Markdown</a> · <a href="manifest.json">Run manifest</a></p></section></main></html>''')
    (run_dir/'README.md').write_text(f'# Reproduce {m["run_id"]}\n\nAll metrics render from immutable cases.jsonl and provider-calls.jsonl.\n\n```sh\npython -m evals.runner reports --run-id {m["run_id"]}\npython -m evals.runner validate --run-id {m["run_id"]}\n```\n\nUse a new run ID for new inference. Rebuilding reports never calls a model or alters execution timestamps. Source hashes, selected cases, exact commands, model, prompts, RAG and dataset revisions are in manifest.json.\n')
    integrity=validate_run(run_dir,raise_errors=False)
    atomic_json(run_dir/'integrity.json',integrity)
    return summary

def validate_run(run_dir:Path,raise_errors=True)->dict:
    errors=[]
    def check(ok,msg):
        if not ok:errors.append(msg)
    m=read_json(run_dir/'manifest.json',{});rs=rows(run_dir/'cases.jsonl');cs=rows(run_dir/'provider-calls.jsonl')
    try:verify_chain(rs)
    except (AssertionError,KeyError) as exc:errors.append(str(exc))
    previous=None;calls={}
    for c in cs:
        d=dict(c);h=d.pop('record_hash',None)
        expected=hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        check(c.get('previous_hash')==previous,'provider chain mismatch');check(h==expected,'provider hash mismatch');check(c.get('call_id') not in calls,'duplicate provider call id');calls[c.get('call_id')]=c;previous=h
    selected=m.get('selected_case_ids',[])
    check(len(selected)==len(set(selected)),'duplicate manifest selection IDs')
    check(set(selected)=={r['case_id'] for r in rs},'manifest/case selected IDs differ')
    schema=read_json(ROOT/'evals/report.schema.json')
    for component in COMPONENTS:
        path=run_dir/'agents'/f'{component}.json' if component in FUNCTIONS else run_dir/f'{component}.json'
        report=read_json(path)
        if report is None:errors.append('missing report '+component);continue
        try:jsonschema.validate(report,schema)
        except jsonschema.ValidationError as exc:errors.append(component+' schema: '+exc.message)
        expected_records=[r for r in rs if r['component']==component]
        count=count_records(expected_records)
        check(report['counts']==count,component+' count reconciliation failed')
        check(count['selected']==count['attempted']+count['skipped'],component+' selected count equation')
        check(count['attempted']==count['completed']+count['failed'],component+' attempted count equation')
        check(report['provenance']['selected_case_ids']==[r['case_id'] for r in expected_records],component+' report lineage selection mismatch')
        report_ids={r['case_id'] for r in expected_records}
        expected_usage=usage_for([c for c in cs if c.get('metadata',{}).get('case_id') in report_ids])
        check(report['usage']==expected_usage,component+' usage reconciliation failed')
        for metric in report.get('metrics',[]):
            if metric['name']=='task_accuracy':check(metric['denominator']==(count['completed'] or None),'task denominator mismatch')
    for r in rs:
        if r.get('evidence_mode') not in ('live_groq_synthetic','adapted_external') or not r.get('evaluated'):continue
        for link in r.get('candidate_call_lineage',[]):
            linked=calls.get(link['call_id'])
            check(bool(linked) and linked.get('status')=='completed',r['case_id']+' missing linked journey candidate')
            if linked:
                check(linked.get('metadata',{}).get('case_id')==r['case_id'],r['case_id']+' journey call scope mismatch')
                check(link.get('output_hash')==digest(linked.get('parsed') if linked.get('parsed') is not None else linked.get('text')),r['case_id']+' journey output hash mismatch')
        if r.get('arm')=='C':
            check(len(r.get('candidate_call_lineage',[]))==6,r['case_id']+' full journey requires all six function response records')
        cid=r.get('candidate_call_id');c=calls.get(cid)
        check(bool(c) and c.get('status')=='completed',r['case_id']+' no actual completed candidate response')
        if not c:continue
        check(c.get('metadata',{}).get('case_id')==r['case_id'],r['case_id']+' candidate call belongs to another case')
        check(c.get('metadata',{}).get('purpose')!='capability_probe',r['case_id']+' probe used as candidate')
        check(bool(c.get('model')),r['case_id']+' missing model provenance')
        if r['component'] in FUNCTIONS:
            check(r.get('proposal')==c.get('parsed'),r['case_id']+' scored proposal differs from actual candidate')
            from .synthetic import score_proposal
            expected_score=score_proposal(r['input'],c['parsed'])
            if r.get('error'):
                expected_score['passed']=False;expected_score['assertions'].append({'name':'application_accepted_proposal_scope_and_sources','passed':False})
            check(r.get('score')==expected_score,r['case_id']+' semantic score does not reproduce from independent truth')
        output=c.get('parsed') if c.get('parsed') is not None else c.get('text')
        check(r.get('candidate_output_hash')==digest(output),r['case_id']+' candidate output hash mismatch')
        if r['evidence_mode']=='adapted_external':
            gc=calls.get(r.get('grader_call_id'));check(bool(gc) and gc.get('status')=='completed',r['case_id']+' missing actual grader response')
            if gc:
                check(gc.get('metadata',{}).get('case_id')==r['case_id'],r['case_id']+' grader belongs to another case')
                check(r.get('grader_output_hash')==digest(gc.get('parsed')),r['case_id']+' grader output hash mismatch')
                check(bool(r.get('candidate_model')) and bool(r.get('grader_model')),r['case_id']+' missing candidate/grader model IDs')
                check(c.get('messages')==r.get('input_messages'),r['case_id']+' candidate input not original conversation')
                try:
                    example={'rubrics':r['rubrics']}
                    actual_grades=validate_grades(example,gc['parsed'])
                    actual_score=calculate_score(r['rubrics'],actual_grades)
                    check(r['score'].get('rubric_score')==actual_score,r['case_id']+' rubric score differs from actual signed-weight grader result')
                    check(r['score'].get('grades')==actual_grades,r['case_id']+' stored rubric grades differ from actual grader response')
                    grader_input=json.loads(gc['messages'][1]['content'])
                    check(grader_input['conversation']==r['input_messages']+[{'role':'assistant','content':c['text']}],r['case_id']+' grader did not evaluate actual candidate response')
                    check(grader_input['criteria']==[{'index':i,'criterion':rubric['criterion'],'points':rubric['points']} for i,rubric in enumerate(r['rubrics'])],r['case_id']+' grader criteria or signed weights differ')
                except (ValueError,KeyError,TypeError) as exc:errors.append(r['case_id']+' invalid rubric/grader lineage')
    if (run_dir/'budget.sqlite3').exists():
        with sqlite3.connect(run_dir/'budget.sqlite3') as db:
            reservations=db.execute('SELECT id,tokens,actual,state FROM reservations').fetchall()
        check({x[0] for x in reservations}==set(calls),'budget reservation/call ledger IDs differ')
        check(len(reservations)<=m.get('budgets',{}).get('max_calls',300),'request budget exceeded')
        charged=sum(actual if actual is not None else reserved for _,reserved,actual,_ in reservations)
        check(charged<=m.get('budgets',{}).get('max_tokens',300000),'charged token budget exceeded')
        for rid,reserved,actual,state in reservations:
            call=calls.get(rid,{})
            if call.get('usage'):
                check(actual==call['usage']['total_tokens'],'actual token usage/reservation mismatch')
                check(call['usage']['total_tokens']==call['usage']['input_tokens']+call['usage']['output_tokens'],'input/output/total usage mismatch')
            else:check(actual is None,'unknown usage was refunded')
    external_report=read_json(run_dir/'external_suite.json',{})
    actual_scores=[r['score']['rubric_score'] for r in rs if r.get('component')=='external_suite' and r.get('evaluated') and r.get('score',{}).get('rubric_score') is not None]
    if external_report.get('metrics'):check(external_report['metrics'][0]['value']==aggregate_score(actual_scores),'adapted external aggregate metric mismatch')
    check(not any('gsk_' in canonical(r) or 'xai-' in canonical(r) for r in rs+cs),'credential-like string in ledger')
    result={'valid':not errors,'run_id':m.get('run_id'),'case_records':len(rs),'provider_records':len(cs),'checks':['hash chains','selected IDs','count equations','schema','usage reconciliation','candidate/grader response lineage','model provenance','no capability probe substitution'],'errors':errors}
    if errors and raise_errors:raise ValueError('; '.join(errors))
    return result
