"""Hash-linked immutable execution records and reproducibility metadata."""
from __future__ import annotations
import hashlib,json,os,subprocess,tempfile,datetime as dt,shutil,importlib.metadata,platform
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
FUNCTIONS=('intake','pathway_router','safety_escalation','patient_navigator','coordination','closure_evidence')
SCORER_VERSION='suhail-independent-state-v1;healthbench-signed-positive-denominator-aggregate-clip-v1'

def now()->str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def canonical(data:Any)->str:
    return json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)

def digest(data:Any)->str:
    return hashlib.sha256(canonical(data).encode()).hexdigest()

def file_hash(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def source_snapshot()->dict:
    # Explicit allowlist excludes dotenv, runtime credentials, databases and downloaded data.
    patterns=('services/**/*.py','apps/web/app/**/*.tsx','apps/web/app/**/*.css','apps/web/components/**/*.tsx','evals/*.py','pathways/**/*.json','pathways/**/*.md','contracts/*.md','requirements*.txt','apps/web/package*.json','tests/*.py')
    files={}
    for pattern in patterns:
        for p in ROOT.glob(pattern):
            if p.is_file():files[str(p.relative_to(ROOT))]=file_hash(p)
    try:
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,stderr=subprocess.DEVNULL,text=True).strip()
    except (subprocess.CalledProcessError,FileNotFoundError):revision=None
    return {'code_revision':revision,'dirty_state_hash':digest(files),'files':dict(sorted(files.items()))}

def atomic_json(path:Path,data:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',dir=path.parent,encoding='utf-8',delete=False) as f:
        json.dump(data,f,indent=2,ensure_ascii=False,default=str);f.write('\n');tmp=f.name
    os.replace(tmp,path)

def read_json(path:Path,default=None):
    return json.loads(path.read_text()) if path.exists() else default

def rows(path:Path)->list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []

class Ledger:
    """Append-only JSONL, hash chained. A completed case is never rewritten on resume."""
    def __init__(self,path:Path):
        self.path=path;path.parent.mkdir(parents=True,exist_ok=True)
        old=rows(path);self.previous=old[-1]['record_hash'] if old else None
        self.ids={r.get('case_id') for r in old}
    def append(self,record:dict)->dict:
        if record.get('case_id') in self.ids:raise ValueError('immutable_case_already_recorded')
        record=dict(record);record['previous_hash']=self.previous;record['record_hash']=digest(record)
        with self.path.open('a',encoding='utf-8') as f:
            f.write(canonical(record)+'\n');f.flush();os.fsync(f.fileno())
        self.previous=record['record_hash'];self.ids.add(record.get('case_id'));return record

def verify_chain(records:list[dict])->None:
    prev=None;seen=set()
    for row in records:
        d=dict(row);h=d.pop('record_hash',None)
        assert d.get('previous_hash')==prev,'case chain broken'
        assert h==digest(d),'case record hash mismatch'
        assert row['case_id'] not in seen,'duplicate case id'
        seen.add(row['case_id']);prev=h

def new_run(kind:str,run_id:str|None=None)->tuple[Path,dict]:
    run_id=run_id or dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+kind
    if not all(c.isalnum() or c in '-_' for c in run_id):raise ValueError('invalid_run_id')
    p=ROOT/'reports'/'runs'/run_id;p.mkdir(parents=True,exist_ok=True)
    manifest_path=p/'manifest.json'
    if manifest_path.exists():
        m=read_json(manifest_path)
        if m.get('finished_at'):raise ValueError('finished_run_is_immutable_create_new_run')
        for rel,expected in m.get('source_snapshot',{}).get('files',{}).items():
            if rel.startswith(('services/','evals/','pathways/','contracts/')) and (not (ROOT/rel).exists() or file_hash(ROOT/rel)!=expected):
                raise ValueError('candidate_changed_resume_requires_original_source_or_new_run')
        return p,m
    snapshot=source_snapshot()
    m={'schema_version':'1.0','run_id':run_id,'kind':kind,'status':'NOT_RUN','started_at':now(),'finished_at':None,'source_snapshot':snapshot,'provider':None,'model':None,'grader_model':None,'selected_case_ids':[],'dataset_revision':None,'prompt_hash':None,'retrieval_hash':None,'policy_hash':None,'scorer_version':SCORER_VERSION,'commands':[],'budgets':{},'freeze':{'frozen_at':now(),'split':'holdout-v1','optimization_rounds':0,'selection':'No model optimization on final holdout; single configured candidate'},'limitations':[],'runtime_versions':{'python':platform.python_version(),'packages':{name:importlib.metadata.version(name) for name in ('fastapi','SQLAlchemy','groq','langgraph','pydantic','httpx','jsonschema')}}}
    
    for rel,expected_hash in snapshot['files'].items():
        source=ROOT/rel;target=p/'source-snapshot'/rel
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if file_hash(target)!=expected_hash:raise ValueError('source_changed_during_freeze_retry_new_run')
    atomic_json(manifest_path,m);return p,m

def record_command(run_dir:Path,command:str)->None:
    with (run_dir/'commands.txt').open('a') as f:f.write(command+'\n')
