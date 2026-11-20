"""Render release verification only from actual command/test artifacts."""
import csv
import hashlib
import html
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/verification'
OUT.mkdir(parents=True,exist_ok=True)


def read(path):
    p=ROOT/path
    return json.loads(p.read_text()) if p.is_file() else None


def junit(path):
    p=ROOT/path
    if not p.is_file():return {'status':'NOT_RUN','path':path,'tests':None,'passed':None,'failed':None,'skipped':None,'cases':[]}
    tree=ET.parse(p)
    cases=[]
    for c in tree.iter('testcase'):
        status='failed' if c.find('failure') is not None or c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed'
        cases.append({'name':c.attrib['classname']+'.'+c.attrib['name'],'status':status,'seconds':float(c.attrib.get('time','0'))})
    failed=sum(x['status']=='failed' for x in cases);skipped=sum(x['status']=='skipped' for x in cases)
    return {'status':'PARTIAL' if failed or skipped else 'COMPLETE','path':path,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'tests':len(cases),'passed':len(cases)-failed-skipped,'failed':failed,'skipped':skipped,'cases':cases}


sources={}
for folder in ['services','integrations','apps/web','pathways','tests','scripts']:
    for p in (ROOT/folder).rglob('*'):
        if p.is_file() and p.suffix in ('.py','.ts','.tsx','.css','.json') and not any(x in p.parts for x in ('node_modules','.next','__pycache__')):
            sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
for rel in ['requirements.lock','compose.yaml','Makefile','.env.example','infra/api.Dockerfile','infra/web.Dockerfile','infra/compose.verify.yaml']:
    p=ROOT/rel
    sources[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
checks={'acceptance_security_provider_postgres':junit('runtime/test-results.xml'),'browser_patient_staff':junit('runtime/browser-results.xml'),'fresh_install_acceptance':junit('runtime/fresh-install/fresh-tests.xml')}
proofs={'full_browser_care_journey':read('runtime/browser-fullcare-journey.json'),'independent_provider_journey':read('runtime/provider-journey-proof.json'),'graph_persistence':read('runtime/graph-restart-proof.json'),'fresh_install':read('runtime/fresh-install/manifest.json'),'demo_replay':read('runtime/demo-replay.json'),'application_restart':read('runtime/application-restart-proof.json'),'container_stack':read('runtime/container-verification.json'),'container_source_parity':read('runtime/container-source-check.json'),'canonical_contract':read('runtime/contract-validation.json'),'backup_restore':read('runtime/backup-restore-proof.json')}
runs=[]
for p in sorted((ROOT/'reports/runs').glob('*/summary.json')):
    summary=json.loads(p.read_text()); integrity=p.with_name('integrity.json')
    runs.append({'run_id':p.parent.name,'status':summary.get('status'),'counts':summary.get('counts'),'usage':summary.get('usage'),'integrity':json.loads(integrity.read_text()) if integrity.exists() else None,'report':'../runs/'+p.parent.name+'/summary.html'})
required=[checks['acceptance_security_provider_postgres']['status']=='COMPLETE',checks['browser_patient_staff']['status']=='COMPLETE',proofs['fresh_install'] and proofs['fresh_install'].get('status')=='passed',proofs['full_browser_care_journey'] and proofs['full_browser_care_journey'].get('status')=='passed',bool(proofs['independent_provider_journey']),bool(proofs['graph_persistence']),proofs['container_stack'] and proofs['container_stack'].get('status')=='passed',proofs['application_restart'] and proofs['application_restart'].get('status')=='passed']
result={'title':'Suhail Health actual release verification','generated_at':datetime.now(timezone.utc).isoformat(),'status':'COMPLETE' if all(required) else 'PARTIAL','evidence_mode':'software_and_synthetic_customer_journeys','checks':checks,'proofs':proofs,'evaluation_runs':runs,'source_hashes':sources,'code_revision':None,'dirty_state_hash':hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest(),'limitations':['Fictional participants and simulated provider/FHIR services; no real patient contact or live EHR/exchange connection.','The 1,000-trajectory/500-invalid-closure evaluation is deterministic software execution, not 1,500 live AI trajectories.','Live Groq model quality and adapted public conversation rubric estimates are separate run records, with actual partial/failed counts and unknown usage retained.','No clinical outcome improvement, human usability study, independent translation/clinical review, or medical production approval is claimed.','MedAgentBench cloud-processing rights/container/original scorer remain unverified; credentialed MIMIC is disabled; Synthea was not run.']}
(OUT/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
with (OUT/'checks.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=['layer','status','tests','passed','failed','skipped','artifact']);writer.writeheader()
    for layer,c in checks.items():writer.writerow({'layer':layer,**{k:c[k] for k in ['status','tests','passed','failed','skipped']},'artifact':c['path']})
lines=['# Suhail Health executed verification','',f'Generated: {result["generated_at"]}',f'Status: {result["status"]}','','| Evidence layer | Status | Passed / selected | Failed | Skipped |','|---|---|---:|---:|---:|']
for name,c in checks.items():lines.append(f'| {name} | {c["status"]} | {c["passed"]} / {c["tests"]} | {c["failed"]} | {c["skipped"]} |')
lines+=['','## Actual journey proof','']
for name,p in proofs.items():lines.append('- '+name+': '+('Not run' if p is None else 'Captured; see summary.json for exact source IDs, state and commands.'))
lines+=['','## Evaluation records','']
for r in runs:lines.append(f'- [{r["run_id"]}]({r["report"]}): {r["status"]}; {r["counts"]}')
lines+=['','## Limits','']+['- '+x for x in result['limitations']]
(OUT/'summary.md').write_text('\n'.join(lines)+'\n')
body='<h1>Suhail Health</h1><p>Actual release verification · '+html.escape(result['generated_at'])+'</p><h2>'+result['status']+'</h2><table><tr><th>Evidence layer</th><th>Status</th><th>Passed / selected</th><th>Failed</th><th>Skipped</th></tr>'
for name,c in checks.items():body+='<tr><td>'+html.escape(name.replace('_',' '))+'</td><td>'+c['status']+'</td><td>'+str(c['passed'])+' / '+str(c['tests'])+'</td><td>'+str(c['failed'])+'</td><td>'+str(c['skipped'])+'</td></tr>'
body+='</table><h2>Separate evaluation records</h2><ul>'
for r in runs:body+='<li><a href="'+html.escape(r['report'])+'">'+html.escape(r['run_id'])+'</a> · '+str(r['status'])+'</li>'
body+='</ul><h2>Clinical and evidence limits</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in result['limitations'])+'</ul><p><a href="summary.json">Exact provenance and journey records (JSON)</a> · <a href="checks.csv">Measurements CSV</a> · <a href="summary.md">Markdown</a></p>'
(OUT/'summary.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Suhail Health verification</title><style>body{font:16px system-ui;max-width:1080px;margin:40px auto;padding:20px;color:#143D3C;background:#F4F8F7}h1,h2,a{color:#006568}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:14px;border-bottom:1px solid #D4E2DE}th{background:#E8F3F0}li{margin:12px 0}@media print{body{background:white}}</style>'+body+'</html>')
print(json.dumps({'status':result['status'],'report':str(OUT/'summary.html')},indent=2))
