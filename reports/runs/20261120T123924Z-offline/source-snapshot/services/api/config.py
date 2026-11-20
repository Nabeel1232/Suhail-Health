"""Server-only configuration. Owner dotenv is parsed as data and never rewritten."""
import json
import os
import secrets
import fcntl
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
    with (runtime_dir / 'settings.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        local = json.loads(runtime_file.read_text()) if runtime_file.exists() else {
            'session_secret': secrets.token_urlsafe(48), 'connector_token': secrets.token_urlsafe(40)}
        if 'connector_tokens' not in local:
            local['connector_tokens'] = {'source-clinic': local['connector_token'],
                'provider-a': secrets.token_urlsafe(40), 'provider-b': secrets.token_urlsafe(40)}
        temporary = runtime_dir / ('settings.' + str(os.getpid()) + '.tmp')
        temporary.write_text(json.dumps(local))
        temporary.chmod(0o600)
        temporary.replace(runtime_file)
        fcntl.flock(lock, fcntl.LOCK_UN)
    runtime_env = dotenv_values(runtime_dir / 'app.env')
    def get(name, default=None):
        for source in (os.environ, external, runtime_env):
            value = source.get(name)
            if value is not None and value != '':
                return value
        return default
    source_token = get('CONNECTOR_TOKEN', local['connector_tokens']['source-clinic'])
    demo_mode = str(get('DEMO_MODE', 'false')).lower() == 'true'
    return {
        'database_url': get('DATABASE_URL', 'postgresql+psycopg://suhail@127.0.0.1:55432/suhail'),
        'demo_mode': demo_mode,
        'session_secure': str(get('SESSION_SECURE', 'false' if demo_mode else 'true')).lower() == 'true',
        'session_secret': get('SESSION_SECRET', local['session_secret']),
        'connector_token': source_token,
        'connector_tokens': {'source-clinic': source_token,
            'provider-a': get('PROVIDER_A_CONNECTOR_TOKEN', local['connector_tokens']['provider-a']),
            'provider-b': get('PROVIDER_B_CONNECTOR_TOKEN', local['connector_tokens']['provider-b'])},
        'provider_a_url': get('PROVIDER_A_URL', 'http://127.0.0.1:8101'),
        'provider_b_url': get('PROVIDER_B_URL', 'http://127.0.0.1:8102'),
        'fhir_url': get('FHIR_URL', 'http://127.0.0.1:8103'),
        'specialist_organization': get('SPECIALIST_ORGANIZATION', 'specialist-clinic'),
    }
