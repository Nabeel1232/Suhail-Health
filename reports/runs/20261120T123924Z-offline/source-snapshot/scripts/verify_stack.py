"""Native, project-local verification stack with no Docker or main-store writes.

Commands: ``plan``, ``up``, ``status``, ``down``. The hidden ``service`` command
boots each child with a private configuration root before application imports.
SQLite is suitable for these serial HTTP/browser journeys; it does not replace
the separately preserved PostgreSQL concurrency or LangGraph checkpoint proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = PROJECT/'.runtime/ui-v4-stack-root'
DATABASE = PROJECT/'.runtime/ui-v4-verification.db'
ARTIFACTS = PROJECT/'runtime/ui-v4'
REGISTRY = ARTIFACTS/'stack-pids.json'
PYTHON = PROJECT/'.venv/bin/python'
SCRIPT = Path(__file__).resolve()
PORTS = {'api': 18001, 'provider-a': 18101, 'provider-b': 18102, 'fhir': 18103}
MODEL_OFF = {'CHAT_LLM_ENABLED': 'false', 'CHAT_MAX_CALLS': '0',
             'CHAT_MAX_TOKENS': '0', 'GROQ_API_KEY': '',
             'GROQ_MAX_CALLS': '0', 'GROQ_MAX_TOKENS': '0'}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.new')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def plan():
    return {'mode': 'native_isolated_serial_verification',
            'database_url': 'sqlite:///'+str(DATABASE),
            'private_configuration_root': str(PRIVATE_ROOT),
            'private_credentials': str(PRIVATE_ROOT/'.runtime/demo-credentials.json'),
            'owner_environment': 'not loaded; isolated secret-free dotenv file',
            'ports': PORTS, 'main_services': 'unchanged; native3000/API18000/providers8101,8102/FHIR8103/Postgres55432',
            'provider_callback_api': 'http://127.0.0.1:18001',
            'provider_and_fhir_data': str(PRIVATE_ROOT/'runtime'),
            'policy_path': str(PROJECT/'pathways/colorectal-demo/policy.json'),
            'published_report_root': str(PROJECT/'reports/runs'),
            'model_inference': 'disabled; no inherited API keys; chat/Groq caps zero',
            'docker_commands': 0, 'main_dataset_reset': False,
            'limits': ['Serial browser/HTTP verification on SQLite. It is not PostgreSQL locking/concurrency or LangGraph PostgresSaver verification.',
                       'All process-generated credentials, settings, provider data and PIDs are isolated from the main runtime.']}


def environment(name):
    # Deliberately do not inherit model credentials, owner configuration or
    # database URLs from the parent shell.
    result = {key: value for key, value in os.environ.items()
              if key in {'HOME', 'USER', 'LANG', 'LC_ALL', 'PATH', 'TZ'}}
    result.update(MODEL_OFF)
    result.update(DATABASE_URL='sqlite:///'+str(DATABASE),
                  ENV_FILE_PATH=str(PRIVATE_ROOT/'isolated.env'),
                  DEMO_MODE='true', SESSION_SECURE='false',
                  PROVIDER_A_URL='http://127.0.0.1:18101',
                  PROVIDER_B_URL='http://127.0.0.1:18102',
                  FHIR_URL='http://127.0.0.1:18103',
                  API_INTERNAL_URL='http://127.0.0.1:18001',
                  PATHWAY_POLICY_PATH=str(PROJECT/'pathways/colorectal-demo/policy.json'),
                  PYTHONPATH=str(PROJECT), PYTHONUNBUFFERED='1',
                  PYTHONDONTWRITEBYTECODE='1',
                  TMPDIR=str(PRIVATE_ROOT/'tmp'),
                  SQLITE_TMPDIR=str(PRIVATE_ROOT/'tmp'),
                  XDG_CACHE_HOME=str(PRIVATE_ROOT/'cache'))
    if name.startswith('provider-'):
        result['PROVIDER_ID'] = name
        result['PROVIDER_DATA_PATH'] = str(PRIVATE_ROOT/'runtime'/(name+'.sqlite3'))
    result['FHIR_DATA_PATH'] = str(PRIVATE_ROOT/'runtime/fhir.sqlite3')
    return result


def configure_child():
    if os.environ.get('DATABASE_URL') != 'sqlite:///'+str(DATABASE):
        raise RuntimeError('Refusing a child without the exact isolated SQLite URL')
    if Path(os.environ.get('ENV_FILE_PATH', '')).resolve() != PRIVATE_ROOT/'isolated.env':
        raise RuntimeError('Refusing a child that could load the owner dotenv')
    if any(os.environ.get(name) != value for name, value in MODEL_OFF.items()):
        raise RuntimeError('Verification inference guards are not set')
    sys.path.insert(0, str(PROJECT))
    from services.api import config
    config.ROOT = PRIVATE_ROOT
    config.settings.cache_clear()


def database_timeout():
    from sqlalchemy import event
    from services.api.db import engine
    if engine.dialect.name != 'sqlite' or Path(engine.url.database).resolve() != DATABASE:
        raise RuntimeError('Verification engine is not the isolated SQLite file')
    @event.listens_for(engine, 'connect')
    def configure_sqlite(connection, _):
        connection.execute('PRAGMA busy_timeout=30000')
        connection.execute('PRAGMA temp_store=MEMORY')


def child(name):
    configure_child()
    if name in {'api', 'seed'}:
        from services.api import main
        # Only sanitized report downloads need the true repository root. The
        # settings and seed modules retain the private configuration root.
        main.ROOT = PROJECT
        database_timeout()
        if name == 'seed':
            from services.api.db import init_db
            from services.api.seed import seed
            init_db()
            result = seed()
            print(json.dumps({'status': 'seeded_isolated', 'case_ids': result['seeded_case_ids'],
                              'accounts': result['accounts'], 'credentials_printed': False}))
            return
        app = main.app
    elif name == 'worker':
        from services.api import worker
        database_timeout()
        worker.main()
        return
    elif name.startswith('provider-'):
        app = importlib.import_module('integrations.provider').app
    elif name == 'fhir':
        app = importlib.import_module('integrations.fhir').app
    else:
        raise ValueError('Unsupported verification child')
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=PORTS[name],
                access_log=False, log_level='warning')


def is_owned_process(pid, name):
    try:
        proc = Path('/proc')/str(pid)
        command = (proc/'cmdline').read_bytes().replace(b'\0', b' ').decode()
        return ((proc/'cwd').resolve() == PRIVATE_ROOT and str(SCRIPT) in command and
                'service '+name in command and os.getpgid(pid) == pid)
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return False


def registry():
    return json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}


def health(name, timeout=2):
    import httpx
    try:
        r = httpx.get(f'http://127.0.0.1:{PORTS[name]}/health', timeout=timeout)
        body = r.json()
        valid = r.status_code == 200 and body.get('status') == 'ok'
        if name == 'api':
            valid = valid and body.get('database') == 'sqlite'
        if name.startswith('provider-'):
            valid = valid and body.get('organization') == name
        return {'ready': bool(valid), 'http_status': r.status_code, 'health': body}
    except (httpx.HTTPError, ValueError):
        return {'ready': False}


def main_case():
    import httpx
    deadline = time.monotonic()+30
    while True:
        try:
            with httpx.Client(base_url='http://127.0.0.1:18000', timeout=3) as client:
                client.post('/auth/demo', json={'role': 'admin'}).raise_for_status()
                r = client.get('/cases/SC-001')
                r.raise_for_status()
                case = r.json()
                return {key: case[key] for key in ['id', 'owner', 'version', 'disposition']}
        except httpx.HTTPError:
            if time.monotonic() >= deadline:
                raise
            # The release coordinator may briefly restart the main API while
            # this independent stack starts. Never stop or modify that process.
            time.sleep(.25)


def protected_files():
    result = {}
    for relative in ['.env', '.runtime/app.env', '.runtime/settings.json', '.runtime/demo-credentials.json']:
        path = PROJECT/relative
        if path.exists():
            info = path.stat()
            # No owner dotenv contents are read. Private generated settings and
            # credentials are compared in memory; their hashes are never saved.
            digest = hashlib.sha256(path.read_bytes()).digest() if relative.endswith(('.json',)) else None
            result[relative] = (info.st_mtime_ns, info.st_size, info.st_mode, digest)
        else:
            result[relative] = None
    return result


def ensure_ports_free(rows):
    for name, port in PORTS.items():
        if name in rows and is_owned_process(rows[name]['pid'], name):
            continue
        with socket.socket() as probe:
            # Match Uvicorn's bind behavior after an owned service stops;
            # accepted sockets may still be in TIME_WAIT without a listener.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                raise RuntimeError(f'Port{port} is occupied by an untracked service; it will not be stopped') from None


def up():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    write_json(ARTIFACTS/'stack-plan.json', plan())
    records = registry()
    ensure_ports_free(records)
    before, files_before = main_case(), protected_files()
    if before != {'id': 'SC-001', 'owner': 'provider-b', 'version': 30, 'disposition': 'completed_required_care'}:
        raise RuntimeError('Main baseline differs from the expected preserved completed case; no verification service started')
    for directory in [PRIVATE_ROOT, PRIVATE_ROOT/'tmp', PRIVATE_ROOT/'cache', PRIVATE_ROOT/'runtime', PRIVATE_ROOT/'.runtime']:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    secret_free = PRIVATE_ROOT/'isolated.env'
    if not secret_free.exists():
        secret_free.write_text('# Verification configuration is supplied by explicit process overrides. No owner keys.\n')
    with (ARTIFACTS/'stack-seed.log').open('a') as log:
        subprocess.run([str(PYTHON), str(SCRIPT), 'service', 'seed'],
                       cwd=PRIVATE_ROOT, env=environment('seed'), stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    for name in ['provider-a', 'provider-b', 'fhir', 'api', 'worker']:
        if name in records and is_owned_process(records[name]['pid'], name):
            continue
        with (ARTIFACTS/('stack-'+name+'.log')).open('a') as log:
            process = subprocess.Popen([str(PYTHON), str(SCRIPT), 'service', name],
                cwd=PRIVATE_ROOT, env=environment(name), stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
        records[name] = {'pid': process.pid, 'cwd': str(PRIVATE_ROOT),
                         'port': PORTS.get(name), 'started_at': now()}
        write_json(REGISTRY, records)
        if name != 'worker':
            deadline = time.monotonic()+45
            while time.monotonic() < deadline:
                if health(name)['ready']:
                    break
                if process.poll() is not None:
                    raise RuntimeError(name+' exited; inspect its isolated stack log')
                time.sleep(.25)
            else:
                raise RuntimeError(name+' did not become ready; inspect its isolated stack log')
    # Verify every role from actual API authentication, without care commands.
    import httpx
    role_checks = []
    for role in ['patient', 'navigator', 'clinician', 'specialist', 'receiver_a', 'receiver_b', 'admin']:
        with httpx.Client(base_url='http://127.0.0.1:18001', timeout=15) as client:
            r = client.post('/auth/demo', json={'role': role})
            valid = r.status_code == 200 and r.json().get('role') == role
            role_checks.append({'role': role, 'authenticated': valid})
    after, files_after = main_case(), protected_files()
    same_files = {path: files_before[path] == files_after[path] for path in files_before}
    status = {'mode': 'actual_native_sqlite_verification_stack', 'at': now(),
              'services': {name: health(name) for name in PORTS},
              'role_authentication': role_checks, 'database_path': str(DATABASE),
              'main_before': before, 'main_after': after,
              'main_clinical_state_preserved': before == after,
              'main_protected_files_unchanged': same_files,
              'credential_values_or_fingerprints_recorded': False,
              'owner_dotenv_contents_read': False,
              'model_requests': 0, 'docker_commands': 0,
              'worker_pid_tracked': is_owned_process(records['worker']['pid'], 'worker'),
              'limits': plan()['limits']}
    passed = before == after and all(same_files.values()) and all(x['authenticated'] for x in role_checks) and all(x['ready'] for x in status['services'].values())
    status['status'] = 'passed' if passed else 'review_required'
    write_json(ARTIFACTS/'stack-isolation-proof.json', status)
    if not passed:
        raise RuntimeError('Native verification isolation check requires review')
    print(json.dumps({'status': 'ready', 'api': 'http://127.0.0.1:18001',
                      'database': 'isolated SQLite', 'roles_authenticated': len(role_checks),
                      'main_case_unchanged': True, 'main_files_unchanged': True,
                      'docker_commands': 0, 'model_requests': 0}))


def down():
    stopped = []
    for name, row in reversed(list(registry().items())):
        pid = row['pid']
        if is_owned_process(pid, name):
            os.killpg(pid, signal.SIGTERM)
            deadline = time.monotonic()+6
            while is_owned_process(pid, name) and time.monotonic() < deadline:
                time.sleep(.05)
            stopped.append({'service': name, 'pid': pid,
                            'status': 'stopped' if not is_owned_process(pid, name) else 'graceful_stop_pending'})
        else:
            stopped.append({'service': name, 'status': 'not_running_or_not_owned; no signal sent'})
    write_json(ARTIFACTS/'stack-stop.json', {'at': now(), 'processes': stopped,
               'database_and_private_files_retained': True, 'docker_commands': 0,
               'main_services_changed': False})
    print(json.dumps({'status': 'verification_stop_requested', 'services': len(stopped),
                      'main_services_changed': False, 'data_retained': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'up', 'status', 'down', 'service'])
    parser.add_argument('name', nargs='?', choices=[*PORTS, 'worker', 'seed'])
    args = parser.parse_args()
    if args.command == 'service':
        if not args.name:
            parser.error('service needs a child name')
        child(args.name)
    elif args.command == 'plan':
        write_json(ARTIFACTS/'stack-plan.json', plan())
        print(json.dumps(plan(), indent=2))
    elif args.command == 'up':
        up()
    elif args.command == 'down':
        down()
    else:
        result = {name: health(name) for name in PORTS}
        result['worker'] = {'owned_process': bool('worker' in registry() and is_owned_process(registry()['worker']['pid'], 'worker'))}
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
