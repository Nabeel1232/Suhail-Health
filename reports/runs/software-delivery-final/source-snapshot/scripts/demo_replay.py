"""Actual local HTTP replay with persisted synthetic records and no model cost."""
import json
import sys
import uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path

import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.api.config import settings

API='http://127.0.0.1:18000'
trace=[]
clients={}
cid='REPLAY-'+uuid.uuid4().hex[:10]


def check(r,action):
    data=r.json()
    trace.append({'timestamp':datetime.now(timezone.utc).isoformat(),'action':action,'http_status':r.status_code,'case_id':cid,'version':data.get('version'),'record_id':data.get('record_id')})
    if not r.is_success:raise RuntimeError(action+' failed with HTTP '+str(r.status_code))
    return data


def client(role):
    if role not in clients:
        c=httpx.Client(base_url=API,timeout=20);check(c.post('/auth/demo',json={'role':role}),'signin:'+role);clients[role]=c
    return clients[role]


def cmd(role,path,**data):
    key='replay:'+uuid.uuid4().hex
    for attempt in range(4):
        case=check(client('navigator').get('/cases/'+cid),'read_current_version')
        response=client(role).post(path,json={'expected_version':case['version'],'idempotency_key':key,**data})
        if response.status_code==409 and 'version conflict' in response.text.lower():
            trace.append({'action':path,'http_status':409,'reason':'version_conflict_retry','attempt':attempt+1})
            continue
        return check(response,path)
    return check(response,path)


try:
    case=check(client('navigator').post('/events/results',json={'event_id':cid,'case_id':cid,'dataset':'replay-v1','source_organization':'source-clinic','patient_id':cid+'-P','patient_name':'Replay participant (synthetic)','order_id':cid+'-O','result_version':1,'test_code':'FIT_POS','issued_at':(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),'identity_verified':True}),'intake')
    failed=client('clinician').post('/cases/'+cid+'/dispositions',json={'expected_version':case['version'],'idempotency_key':uuid.uuid4().hex,'category':'completed_required_care','reason':'Premature closure challenge'})
    assert failed.status_code==409
    trace.append({'action':'premature_closure_correctly_blocked','http_status':409})
    cmd('navigator','/communications',case_id=cid,language='en',channel='portal')
    question=cmd('clinician','/consultations',case_id=cid,type='clinician_to_specialist',question='Synthetic replay: confirm the next coordination action',recipient='specialist')
    cmd('specialist','/consultations/'+question['record_id']+'/reply',reply='Human specialist reviewed the synthetic request. Arrange source-linked assessment.',agreed_action='Coordinate assessment',action_owner='navigation-team')
    h=cmd('navigator','/handoffs',case_id=cid,receiver='provider-a',scope='episode',reason='Synthetic replay capacity check')
    cmd('receiver_a','/handoffs/'+h['record_id']+'/reject',reason='No available demonstration slots')
    assert check(client('navigator').get('/cases/'+cid),'owner_after_rejection')['owner']=='navigation-team'
    h=cmd('navigator','/handoffs',case_id=cid,receiver='provider-b',scope='task',reason='Alternative provider assessment')
    cmd('receiver_b','/handoffs/'+h['record_id']+'/accept',reason='Assessment task explicitly accepted')
    appt=cmd('receiver_b','/cases/'+cid+'/appointments',provider='provider-b',scheduled_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())
    cmd('receiver_b','/appointments/'+appt['record_id']+'/events',status='no_show')
    cmd('receiver_b','/appointments/'+appt['record_id']+'/events',status='attended')
    for kind in ['investigation','reviewed_outcome','patient_updated']:
        e=cmd('clinician','/cases/'+cid+'/evidence',type=kind,reference='synthetic://replay/'+cid+'/'+kind,patient_id=case['patient_id'],order_id=case['order_id'],result_version=1,document_text='Retained synthetic source document for replay '+cid+' '+kind+'; exact patient and order reviewed by the demo clinician.')
        cmd('clinician','/evidence/'+e['record_id']+'/verification',verified=True,reason='Human verified retained synthetic source and patient/order/result version')
    final=check(client('clinician').get('/cases/'+cid+'/closure-check'),'closure_check')
    # This replay has no account for the new synthetic patient: acknowledgement and
    # understanding remain visibly pending. Do not impersonate a patient or fake closure.
    assert not final['allowed'] and any('acknowledgement' in x or 'understanding' in x for x in final['missing'])
    result={'status':'passed','case_id':cid,'evidence_mode':'real_http_synthetic_replay','clinical_care_completed':False,'remaining':final['missing'],'commands':trace,'limitations':['New replay participant has no provisioned patient account; acknowledgement/understanding remain open. The full authenticated patient-to-care browser journey is tested separately.']}
except Exception as exc:
    result={'status':'failed','case_id':cid,'error':str(exc),'commands':trace}
finally:
    for c in clients.values():c.close()
out=ROOT/'runtime/demo-replay.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(result,indent=2))
print(json.dumps({'status':result['status'],'case_id':cid,'record':str(out)},indent=2))
if result['status']!='passed':sys.exit(1)
