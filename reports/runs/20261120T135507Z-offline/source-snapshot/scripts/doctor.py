"""Secret-free configuration and dependency checks."""
import json,os,sys,importlib.metadata,shutil,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.agents.gateway import env_value
ROOT=Path(__file__).resolve().parents[1]
checks={'owner_env_exists':Path(os.environ.get('ENV_FILE_PATH',ROOT/'.env')).is_file(),'groq_credential_configured':bool(env_value('GROQ_API_KEY')),'logo_exists':(ROOT/'apps/web/public/brand/logo-original.png').is_file(),'python':sys.version.split()[0],'docker_available':bool(shutil.which('docker'))}
checks['dependencies']={}
for name in ['fastapi','uvicorn','sqlalchemy','psycopg','groq','langgraph','langgraph-checkpoint-postgres']:
 try:checks['dependencies'][name]=importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError:checks['dependencies'][name]=None
node=ROOT/'.runtime/node/bin/node'
if not node.is_file():node=Path(shutil.which('node') or '/nonexistent')
try:checks['node']=subprocess.check_output([str(node),'--version'],text=True).strip()
except Exception:checks['node']=None
try:
 from sqlalchemy import create_engine,text
 from services.api.config import settings
 engine=create_engine(settings()['database_url'])
 with engine.connect() as c:c.execute(text('SELECT 1'))
 checks['database']='reachable';checks['database_backend']=engine.dialect.name
except Exception:checks['database']='unavailable'
print(json.dumps(checks,indent=2))
if checks['database']=='unavailable' or any(v is None for v in checks['dependencies'].values()):sys.exit(1)
