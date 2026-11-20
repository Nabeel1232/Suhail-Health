"""Reproduce installation in an isolated directory without touching demo records."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/fresh-install'
OUT.mkdir(parents=True,exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='suhail-fresh-'))
manifest={'started_at':datetime.now(timezone.utc).isoformat(),'workspace':str(work),'steps':[],'status':'running','secrets_copied':False}


def run(name,args,env=None,cwd=work):
    start=time.monotonic()
    print(name,flush=True)
    with (OUT/(name+'.log')).open('w') as log:
        result=subprocess.run(args,cwd=cwd,env=env,stdout=log,stderr=log)
    manifest['steps'].append({'name':name,'command':args,'exit_code':result.returncode,'duration_seconds':time.monotonic()-start})
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    if result.returncode:
        raise RuntimeError(name+' failed; see runtime/fresh-install/'+name+'.log')


try:
    for folder in ['services','integrations','pathways','evals','tests','docs','contracts']:
        shutil.copytree(ROOT/folder,work/folder,ignore=shutil.ignore_patterns('__pycache__','cache'))
    shutil.copy2(ROOT/'requirements.lock',work/'requirements.lock')
    shutil.copytree(ROOT/'apps/web',work/'apps/web',ignore=shutil.ignore_patterns('node_modules','.next','tsconfig.tsbuildinfo'))
    manifest['source_hashes']={str(p.relative_to(work)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['services','integrations','apps/web','pathways'] for p in (work/folder).rglob('*') if p.is_file() and p.suffix in ['.py','.ts','.tsx','.css','.json']}
    # No owner dotenv, runtime credentials, patient store or benchmark cache is copied.
    run('python-venv',[sys.executable,'-m','venv',str(work/'.venv')])
    py=str(work/'.venv/bin/python')
    run('python-install',[py,'-m','pip','install','-r','requirements.lock'])
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(work/'fresh.sqlite3'),'DEMO_MODE':'true','ENV_FILE_PATH':str(work/'no-owner-env'),'NEXT_TELEMETRY_DISABLED':'1'}
    run('fresh-schema-seed',[py,'-m','services.api.seed'],env)
    run('fresh-acceptance',[py,'-m','pytest','tests/test_backend.py','tests/test_agents.py','-q','--junitxml='+str(OUT/'fresh-tests.xml')],env)
    node=ROOT/'.runtime/node/bin'
    env['PATH']=str(node)+':'+env.get('PATH','')
    env['API_INTERNAL_URL']='http://127.0.0.1:18000'
    npm=str(node/'npm') if (node/'npm').exists() else 'npm'
    run('web-install',[npm,'ci','--no-audit','--no-fund'],env,work/'apps/web')
    run('web-production-build',[npm,'run','build'],env,work/'apps/web')
    manifest['status']='passed'
except Exception as exc:
    manifest['status']='failed';manifest['error']=str(exc);print(str(exc),flush=True)
finally:
    manifest['finished_at']=datetime.now(timezone.utc).isoformat()
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'status':manifest['status'],'report':str(OUT/'manifest.json')},indent=2))
if manifest['status']!='passed':sys.exit(1)
