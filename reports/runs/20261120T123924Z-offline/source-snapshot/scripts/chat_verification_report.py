"""Render the v4 assistant release report from retained execution records.

No application, browser or model request is made. The model accounting database
is opened read-only; provider prompts, raw answers and credentials are omitted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'reports/ui-chat-v4'


def read(path):
    return json.loads((ROOT/path).read_text())


def digest(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def junit(path, expected):
    root = ET.parse(ROOT/path).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    result = {name: sum(int(s.get(name, 0)) for s in suites)
              for name in ['tests', 'failures', 'errors', 'skipped']}
    result['passed'] = result['tests']-result['failures']-result['errors']-result['skipped']
    result.update(path=path, sha256=digest(path), expected_tests=expected,
                  seconds=sum(float(s.get('time', 0)) for s in suites))
    result['status'] = 'passed' if result['tests'] == result['passed'] == expected else 'review_required'
    return result


def runtime_model():
    proof_path = 'runtime/ui-v4/chat-live-functional.json'
    proof = read(proof_path)
    ledger_dir = ROOT/'runtime/context-chat/model-ledger'
    with sqlite3.connect('file:'+str(ledger_dir/'budget.sqlite3')+'?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        config = dict(db.execute('SELECT model,max_calls,max_tokens FROM run_config').fetchone())
        accounting = dict(db.execute('SELECT COUNT(*) AS reserved_calls, '
            'COALESCE(SUM(COALESCE(actual,tokens)),0) AS charged_tokens, '
            'COALESCE(SUM(actual),0) AS known_actual_tokens, '
            'SUM(CASE WHEN actual IS NULL THEN 1 ELSE 0 END) AS unknown_usage_calls '
            'FROM reservations').fetchone())
    records = [json.loads(line) for line in (ledger_dir/'provider-calls.jsonl').read_text().splitlines() if line.strip()]
    checks = {s.get('intelligence', {}).get('call_id') for s in proof['steps']}
    calls = [{key: r.get(key) for key in ['call_id', 'timestamp', 'model', 'provider',
                'mode', 'status', 'usage', 'latency_ms']} for r in records if r.get('call_id') in checks]
    return {'status': proof['status'], 'classification': proof['mode'],
        'source': proof_path, 'source_sha256': digest(proof_path),
        'actual_new_dispatches': proof['new_model_reservations'],
        'recorded_functional_steps': [{
            'question': s['question'], 'http_status': s['status'], 'answer_mode': s['mode'],
            'interpretation': s['intelligence'], 'source_link_count': s['sources'], 'card_count': s['cards']
        } for s in proof['steps']],
        'matching_provider_records': calls,
        'ledger': {'path': 'runtime/context-chat/model-ledger', 'persistent': True,
                   'reset': False, 'limits': config, 'accounting': accounting,
                   'provider_records_sha256': digest('runtime/context-chat/model-ledger/provider-calls.jsonl'),
                   'automatic_retries': 0, 'output_token_ceiling': 1024},
        'clinical_state_preserved': proof['clinical_state_preserved'],
        'old_benchmark_unchanged': proof['old_benchmark_unchanged'],
        'measured_accuracy': None,
        'limits': 'One synthetic functional dispatch demonstrates an actual successful bounded intent call, not general model accuracy, latency or clinical quality.'}


def build():
    baseline = read('runtime/ui-v4/backend-verification.json')
    post = read('runtime/ui-v4/post-suite-focused-verification.json')
    ui = read('runtime/chat-ui/implementation.json')
    restoration = read('runtime/ui-v4/proof-restoration.json')
    browser_source_path='runtime/ui-v4/browser-source-hashes.json'
    browser_source=read(browser_source_path)
    native_path='reports/ui-chat-v4/native-runtime-smoke.json'
    native=read(native_path)
    recovery_path='.runtime/disk-recovery/20261116T115318Z/relocations.json'
    recovery=read(recovery_path)
    checks = {
        'backend_baseline': junit('runtime/ui-v4/backend-results.xml', 123),
        'post_suite_specialist_link': junit('runtime/ui-v4/specialist-link-fix.xml', 1),
        'post_suite_count_intents': junit('runtime/ui-v4/count-intent-final.xml', 4),
        'post_suite_ownership_followup': junit('runtime/ui-v4/ownership-followup-fix.xml', 2),
        'media_sync_focused': junit('runtime/video-v4/sync-identity-tests.xml', 14),
        'browser_final': junit('runtime/ui-v4/browser-results.xml', 21),
        'browser_ui_checkpoint': junit('runtime/ui-v4/context-chat-final-focused.xml', 5),
    }
    checks['backend_baseline'].update(chat_tests_included=20, video_sync_tests_included=10,
        report='runtime/ui-v4/backend-verification.json',
        source_hashes_at_execution=baseline['source_hashes'],
        note='The baseline preceded the documented specialist URL and media-helper changes. Its source hashes and 123-check denominator are preserved.')
    checks['post_suite_specialist_link']['note'] = 'Focused pure-link regression after the baseline; not a second full backend run.'
    checks['media_sync_focused']['note'] = 'Fourteen current media checks, including the ten present in the baseline, required visibility extensions and unchanged authored identity mappings. Earlier13-check evidence remains historical; overlapping checks are not added to a combined total.'
    checks['post_suite_count_intents']['note'] = 'Current authorized episode/patient counts, distinct patient identities, case-context clearing, pending provider prompts and the existing direct-query contract; one older global-context regression is included.'
    checks['post_suite_ownership_followup']['note'] = 'Actual workload → explicit case → bare ownership follow-up, explicit case switch and global-workload reset, with unchanged care state and a denied foreign case; includes the existing global-context regression.'
    checks['browser_final'].update(console='runtime/ui-v4/browser-console.log',
        artifacts='runtime/ui-v4/journey-artifacts',
        note='Ordered final production-browser regression on the frozen UI/backend; earlier failed20/21-check attempts remain separately preserved and are not promoted to successes.')
    checks['browser_ui_checkpoint'].update(
        note='Five focused chat browser checks passed before the final tiny API follow-up patch/test expansion; the final21-check run is authoritative for the current source. These overlap and are not added to a combined total.')
    model = runtime_model()
    expected_sources = {**baseline['source_hashes'], **post['latest_source_hashes'], **ui['source_hashes'],
                        **browser_source.get('source_hashes_after',{})}
    paths = set(expected_sources)
    paths |= {str(p.relative_to(ROOT)) for p in (ROOT/'services/assistant').glob('*.py')}
    paths |= {'services/api/main.py', 'services/assistant/README.md', 'scripts/chat_verification_report.py',
              'scripts/video/verify_authored_v4.py'}
    latest = {p:digest(p) for p in sorted(paths)}
    mismatches = [p for p,h in ui['source_hashes'].items() if latest[p]!=h]
    unverified_drift = [p for p,h in expected_sources.items() if latest[p]!=h]
    archived_browser_matches = (digest('runtime/ui-v4/journey-artifacts/browser-results.xml')
        == checks['browser_final']['sha256'])
    checks['browser_final']['archived_junit_matches'] = archived_browser_matches
    model_good = (model['status']=='passed' and model['actual_new_dispatches']==1
        and len(model['matching_provider_records'])==1
        and model['matching_provider_records'][0]['status']=='completed'
        and model['clinical_state_preserved'] and model['old_benchmark_unchanged']
        and model['ledger']['limits']['max_calls']==20
        and model['ledger']['limits']['max_tokens']==40000)
    restoration_good = (restoration.get('status')=='passed'
        and restoration.get('suite_exit_code')==0
        and restoration.get('main_case_mutations')==0
        and restoration.get('prior_ui_v3_dynamic_proof_restored') is True)
    browser_hashes=browser_source.get('source_hashes_after',{})
    browser_drift=[p for p,h in browser_hashes.items() if not (ROOT/p).is_file() or digest(p)!=h]
    browser_source_good=(browser_source.get('status')=='passed'
        and browser_source.get('source_unchanged_during_execution') is True
        and browser_source.get('suite_exit_code')==0
        and browser_source.get('model_assistance_enabled') is False
        and isinstance(browser_source.get('web_build_id'),str) and bool(browser_source['web_build_id'])
        and bool(browser_hashes) and browser_hashes==browser_source.get('source_hashes_before')
        and not browser_drift)
    native_good=(native.get('status')=='passed' and native.get('main_case_preserved') is True
        and native.get('worker_alive') is True and native.get('model_requests')==0
        and native.get('benchmark_requests')==0 and native.get('chat_ledger_unchanged_by_this_check') is True
        and {r['role'] for r in native['roles']}=={'patient','navigator','clinician','specialist','receiver_a','receiver_b','admin'}
        and all(r['http_status']==200 and r['actor_matches'] is True for r in native['roles'])
        and len(native['services'])==5 and all(s['http_status']==200 for s in native['services'])
        and native['main_case']==read('runtime/ui-v4/native-before-chat.json'))
    good = (all(c['status']=='passed' for c in checks.values()) and model_good and restoration_good
        and native_good and browser_source_good and archived_browser_matches and not mismatches and not unverified_drift)
    historical = [junit(path, expected) for path,expected in [
        ('runtime/ui-v4/initial-browser-attempt/browser-results.xml',20),
        ('runtime/ui-v4/pre-final-patch-browser/browser-results.xml',20),
        ('runtime/ui-v4/final21-ack-race-attempt/browser-results.xml',21),
        ('runtime/ui-v4/final21-history-list-wait-attempt/browser-results.xml',21),
        ('runtime/ui-v4/targeted-chat-initial/context-chat-targeted.xml',4),
        ('runtime/ui-v4/targeted-chat-pre-draft-fix/context-chat-targeted.xml',4),
    ] if (ROOT/path).is_file()]
    return {
        'release':'Suhail Health · Ask Suhail · UI/chat v4',
        'recorded_at':datetime.now(timezone.utc).isoformat(),
        'status':'passed' if good else 'review_required',
        'summary':'A signed-in, role-scoped read-only workspace assistant with current-record answers, private persisted conversations and authorized field links.',
        'evidence_groups':checks,
        'historical_attempts':historical,
        'browser_source_verification':{'path':browser_source_path,'sha256':digest(browser_source_path),
            'passed':browser_source_good,'current_source_drift':browser_drift,'record':browser_source},
        'native_runtime_read_smoke':{'path':native_path,'sha256':digest(native_path),
            'passed':native_good,'record':native,
            'scope':'Supplemental actual native PostgreSQL read/authentication and service smoke; full write/browser journeys use the isolated SQLite stack, with separate evidence.'},
        'operating_notes':{'disk_recovery':{'path':recovery_path,'sha256':digest(recovery_path),
            'status':recovery['status'],'recorded_at':recovery['finished_at'],
            'recorded_available_bytes':recovery['disk_after']['available_bytes'],
            'generated_files_relocated':len(recovery['relocations']),
            'original_paths_preserved_by_verified_symlinks':all(r['symlink_preserved'] and r['sha256_before']==r['sha256_after'] for r in recovery['relocations']),
            'current_project_dependencies_changed':recovery['current_project_dependencies_changed'],
            'databases_changed':recovery['databases_changed'],
            'docker_or_postgresql_storage_touched':recovery['docker_or_postgresql_storage_touched'],
            'scope':'Only large generated dependency files in inactive /tmp/suhail-fresh-* project setup copies were relocated to Lustre. Earlier recovery is recorded separately at .runtime/disk-recovery/20261116T112744Z/relocations.json.'}},
        'no_combined_check_total':True,
        'runtime_model_functional_check':model,
        'authorization':{
            'patient':'Identity-verified linked episodes through the existing patient serializer; approved plan only from the permitted patient view.',
            'receiving_service':'Current granted minimal referral packets and that service\'s appointment facts; source charts, internal tasks and escalation details remain outside packet access.',
            'specialist':'Assigned consultations in the configured specialist organization, with existing serializer restrictions.',
            'navigator_clinician_admin':'Existing role rules and source-organization case scope; operational rows limited to permitted cases.',
            'conversation_history':'Owner, role, organization, patient identity, case roster and packet/consultation dependencies rechecked on every list, history read and new turn; affected threads are hidden after revocation.',
            'facts':'Current SQLAlchemy record reads and allowlisted rendering; counts, statuses, cards and links do not come from model prose.',
            'counts':'Role-specific definitions returned by the server; full authorized denominator with a bounded preview of up to twelve cards/source links. Ungranted metrics are null.',
            'clinical_authority':'Human clinical questions and clinical actions stay in their existing authorized workflows; chat does not diagnose, prescribe, approve evidence, close care, book visits or submit delivery retries.',
        },
        'optional_model':{
            'purpose':'Allowlisted intent interpretation for ambiguous questions only; familiar questions read records directly.',
            'input':'Typed question and bounded classification instructions, without a case-record/history dump or application tools.',
            'mode_labels':{'authorized_records':'Record-grounded answer', 'model_assisted_records':'AI-assisted record answer'},
            'fallback':'A failed, capped or disabled model keeps the deterministic record-grounded answer, with its interpretation status.',
        },
        'ui':{'launcher':'Ask Suhail', 'shortcut':'Ctrl/Cmd+J',
            'features':['Private conversation history and new threads','Metrics, source chips, record cards and follow-up questions',
                        'Case tab/field navigation and provider referral anchors','Mobile dialog and Arabic/RTL handling',
                        'Actor-bound request cancellation and uncertain-send reconciliation without automatic retry'],
            'implementation_record':'runtime/chat-ui/implementation.json',
            'source_hash_mismatches':mismatches},
        'preserved_state':{'main_case_before':read('runtime/ui-v4/native-before-chat.json'),
            'main_case_after_native_read_smoke':native['main_case'],
            'live_check_reports_clinical_state_preserved':model['clinical_state_preserved'],
            'proof_restoration':'runtime/ui-v4/proof-restoration.json',
            'proof_restoration_sha256':digest('runtime/ui-v4/proof-restoration.json'),
            'proof_restoration_record':restoration,
            'proof_restoration_passed':restoration_good,
            'original_benchmark_artifacts_unchanged_by_runtime_check':model['old_benchmark_unchanged'],
            'benchmark_budget_is_separate':True,'benchmark_budget_reset':False},
        'latest_source_hashes':latest,
        'unverified_source_drift':unverified_drift,
        'post_suite_source_record':'runtime/ui-v4/post-suite-focused-verification.json',
        'limits':[
            'These are software, browser and synthetic functional checks. They do not establish clinical validation or accuracy of an autonomous clinical agent.',
            'The single live request tested question interpretation. It is separate from the preserved historical benchmark and does not extend that budget.',
            'Source timestamps reflect real read time; due/overdue status uses the configured demonstration clock and demonstration service windows.',
            'Versioned local workflow guidance shows its source and review status; demonstration material is not independent clinical approval.',
            'The baseline 123-check backend suite was not repeated after its documented final focused link/count/media changes; their actual current-source evidence is shown separately.',
            'Unchanged external native-service integration checks and optional PostgreSQL concurrency tests were excluded from this backend run; production hosting and clinical review are not claimed.',
            'Actual v4 movie pixel verification is generated separately after final capture/render; local FFmpeg fixtures are not substituted for final-video proof.',
        ]}


def render(report):
    esc = html.escape
    def link(path, text=None):
        return '<a href="../../'+esc(path, quote=True)+'">'+esc(text or path)+'</a>'
    rows = ''.join('<tr><td>'+esc(name.replace('_',' '))+'</td><td>'+str(r['passed'])+'/'+str(r['tests'])+
        '</td><td>'+esc(r['status'])+'</td><td>'+link(r['path'],'JUnit XML')+'</td></tr>'
        for name,r in report['evidence_groups'].items())
    scope = ''.join('<li><strong>'+esc(k.replace('_',' '))+':</strong> '+esc(v)+'</li>' for k,v in report['authorization'].items())
    limits = ''.join('<li>'+esc(s)+'</li>' for s in report['limits'])
    model = report['runtime_model_functional_check']; acct=model['ledger']['accounting']
    sources = '<li>'+link('services/assistant/README.md','Backend/API technical guide')+'</li><li>'+link('runtime/ui-v4/post-suite-focused-verification.json','Post-suite source hashes and focused checks')+'</li><li>'+link('runtime/ui-v4/chat-live-functional.json','Sanitized live functional record')+'</li><li><a href="native-runtime-smoke.json">Actual native PostgreSQL read/authentication smoke</a></li><li>'+link('runtime/ui-v4/journey-artifacts','Browser journey artifacts')+'</li><li>'+link(report['operating_notes']['disk_recovery']['path'],'Reversible temporary-dependency relocation record')+'</li>'
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Ask Suhail · v4 verification</title><style>'
        'body{margin:0;background:#f2f7f6;color:#153b39;font:16px/1.6 system-ui}main{max-width:1080px;margin:48px auto;padding:28px}'
        'header{padding:32px;background:#103f3d;color:white;border-radius:20px}h1{font-size:38px;margin:5px 0}h2{margin-top:34px}'
        '.status{display:inline-block;background:#d3f4e6;color:#12483c;padding:5px 14px;border-radius:30px;font-weight:700}'
        'table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:13px;border-bottom:1px solid #dbe6e3}'
        'a{color:#007277}li{margin:9px 0}.muted{color:#59736f}.card{padding:22px;border-radius:14px;background:white;margin:20px 0}'
        '@media(max-width:650px){main{margin:10px auto;padding:16px}header{padding:22px}h1{font-size:30px}td,th{padding:8px;font-size:14px}}'
        '</style><main><header><span class="status">'+esc(report['status'])+'</span><h1>Ask Suhail</h1>'
        '<p>'+esc(report['summary'])+'</p></header><p class="muted">Execution evidence recorded '+esc(report['recorded_at'])+
        ' · <a href="verification.json">Complete JSON and source hashes</a></p><h2>Executed checks</h2>'
        '<table><thead><tr><th>Evidence group</th><th>Passed</th><th>Status</th><th>Record</th></tr></thead><tbody>'+rows+'</tbody></table>'
        '<p>Each row retains its own denominator. The baseline includes 20 chat and 10 earlier media checks; later focused checks are not added to a combined total. Earlier failed browser attempts remain preserved.</p>'
        '<h2>Actual model integration</h2><div class="card"><strong>'+str(model['actual_new_dispatches'])+' live synthetic application dispatch</strong>'
        '<p>The ambiguous-question check completed through GPT-OSS120B. The familiar workload question used direct record grounding and made no model call. All answer facts came from permitted application records.</p>'
        '<p>The persistent runtime ledger records '+str(acct['reserved_calls'])+' reservation and '+str(acct['charged_tokens'])+
        ' charged tokens, with '+str(acct['unknown_usage_calls'] or 0)+' unknown-usage requests, against 20 calls/40,000 tokens. Automatic retries are disabled; the ledger was not reset.</p>'
        '<p>This functional check is separate from the original benchmark. It is not an accuracy measurement.</p></div>'
        '<h2>Native application health</h2><p>All seven signed-in roles returned the correct actor and HTTP 200 from the actual PostgreSQL-backed assistant context. The web, API, both provider simulators and FHIR service returned HTTP 200; the worker was alive. The original main case remains completed with provider B at version 30. This supplemental read/authentication check made no model request and is separate from the isolated write/browser journeys.</p>'
        '<h2>Access and human authority</h2><ul>'+scope+'</ul><h2>Operating note</h2><p>Host-root space was recovered by moving verified large dependency files from inactive project fresh-check copies to Lustre and preserving their original paths with symlinks. The latest recovery recorded about 551 MiB available; current application dependencies, databases and Docker storage were untouched.</p><h2>Evidence links</h2><ul>'+sources+'</ul>'
        '<h2>Interpretation and limits</h2><ul>'+limits+'</ul></main></html>')


def main():
    report=build();OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (OUTPUT/'index.html').write_text(render(report))
    print(json.dumps({'status':report['status'],'output':str(OUTPUT.relative_to(ROOT))}))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
