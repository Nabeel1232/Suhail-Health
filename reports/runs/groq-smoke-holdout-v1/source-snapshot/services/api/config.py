"""Server-only configuration. Owner dotenv is parsed as data and never rewritten."""
import json
import os
import secrets
from functools import lru_cache
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def settings():
    external = dotenv_values(os.getenv('ENV_FILE_PATH', str(ROOT / '.env')))
    runtime_dir = ROOT / '.runtime'
    runtime_dir.mkdir(mode=0o700, exist_ok=True)
    runtime_file = runtime_dir / 'settings.json'
    if runtime_file.exists():
        local = json.loads(runtime_file.read_text())
    else:
        local = {'session_secret': secrets.token_urlsafe(48), 'connector_token': secrets.token_urlsafe(40)}
        runtime_file.write_text(json.dumps(local))
        runtime_file.chmod(0o600)
    runtime_env = dotenv_values(runtime_dir / 'app.env')
    def get(name, default=None):
        for source in (os.environ, external, runtime_env):
            value = source.get(name)
            if value is not None and value != '':
                return value
        return default
    return {
        'database_url': get('DATABASE_URL', 'postgresql+psycopg://suhail@127.0.0.1:55432/suhail'),
        'demo_mode': str(get('DEMO_MODE', 'true')).lower() == 'true',
        'session_secure': str(get('SESSION_SECURE', 'false')).lower() == 'true',
        'session_secret': get('SESSION_SECRET', local['session_secret']),
        'connector_token': get('CONNECTOR_TOKEN', local['connector_token']),
        'provider_a_url': get('PROVIDER_A_URL', 'http://127.0.0.1:8101'),
        'provider_b_url': get('PROVIDER_B_URL', 'http://127.0.0.1:8102'),
        'fhir_url': get('FHIR_URL', 'http://127.0.0.1:8103'),
    }
