"""Join preserved benchmark evidence for the UI tour; performs no inference."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'reports/runs/groq-smoke-holdout-v1'
COMPONENTS=['intake','pathway_router','safety_escalation','patient_navigator','coordination','closure_evidence']
records=[json.loads(line) for line in (RUN/'cases.jsonl').read_text().splitlines()]
primary=[record for record in records if record['component'] in COMPONENTS and record['evaluated']]
audit=json.loads((RUN/'secondary-scoring-audit/summary.json').read_text())
secondary=audit['cases']
assert len(primary)==30 and len(secondary)==6
assert not ({x['case_id'] for x in primary}&{x['case_id'] for x in secondary})
selected={r['case_id'] for r in records if r['component'] in COMPONENTS}
assert {x['case_id'] for x in primary+secondary}==selected
assert all(x['candidate_call_id'] for x in primary+secondary)
passed=sum(bool(x['score']['passed']) for x in primary)+sum(bool(x['passed']) for x in secondary)
assert passed==35
software_path=ROOT/'reports/runs/software-delivery-final/summary.json'
software=json.loads(software_path.read_text())
assert software['counts']['selected']==1500 and software['counts']['task_passed']==1500 and software['usage']['api_calls']==0
sources=[RUN/'cases.jsonl',RUN/'summary.json',RUN/'secondary-scoring-audit/summary.json',software_path]
result={'generated_at':datetime.now(timezone.utc).isoformat(),'new_inference_calls':0,'bounded_agent_functions':COMPONENTS,'standalone_function_conformance':{'passed':passed,'evaluated':len(selected),'percentage':round(100*passed/len(selected),1),'primary_scored':len(primary),'secondary_saved_responses':len(secondary),'definition':'Primary standalone scores joined with the explicitly separate post-hoc scoring audit of six saved responses. Case IDs are disjoint and cover all36 selected standalone cases.','limits':'Small, known-family synthetic conformance set; not overall medical accuracy, unseen-family generalization, full-journey AI success rate, or independent clinical validation. Original primary failures/denominators remain unchanged.','cases':[{'case_id':x['case_id'],'candidate_call_id':x['candidate_call_id'],'passed':x['score']['passed'],'layer':'primary'} for x in primary]+[{**x,'layer':'secondary_saved_response_audit'} for x in secondary]},'deterministic_software_checks':{'passed':1500,'selected':1500,'percentage':100.0,'model_calls':0},'primary_live_run':json.loads((RUN/'summary.json').read_text())['counts'],'sources':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]}
out=ROOT/'reports/ui-redesign';out.mkdir(exist_ok=True);(out/'benchmark-evidence.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'functions':6,'standalone_passed':passed,'standalone_selected':len(selected),'standalone_conformance_percent':result['standalone_function_conformance']['percentage'],'software_passed':1500,'new_inference_calls':0}))
