"""Prepare only the private, model-disabled v4 recording dataset.

This is an explicit synthetic setup, separate from read-only UI recording.
The native completed case and the old benchmark ledgers are never reset.
"""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import uuid

import httpx

ROOT=Path(__file__).resolve().parents[2]
API='http://127.0.0.1:18001'
EXPECTED={'id':'SC-001','owner':'provider-b','version':30,'disposition':'completed_required_care'}


def checked(response):
    if not response.is_success:
        raise RuntimeError(f'Isolated setup HTTP{response.status_code} at {response.request.url.path}')
    return response.json()


def main_case():
    with httpx.Client(base_url='http://127.0.0.1:18000',timeout=15) as c:
        checked(c.post('/auth/demo',json={'role':'admin'}))
        data=checked(c.get('/cases/SC-001'))
        return {key:data[key] for key in EXPECTED}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--go',action='store_true');args=parser.parse_args()
    if not args.go:print('Explicit --go prepares only private API18001.');return
    output=ROOT/'runtime/video-v4/demo-preparation.json'
    if output.exists():raise RuntimeError('Preparation record exists; refusing an unreviewed repeat reset')
    before=main_case();assert before==EXPECTED
    writes=[]
    with httpx.Client(base_url=API,timeout=30) as c:
        health=checked(c.get('/health'));assert health['database']=='sqlite'
        checked(c.post('/auth/demo',json={'role':'admin'}))
        assert checked(c.get('/assistant/context'))['model_assistance']['enabled'] is False
        checked(c.post('/demo/reset'));writes.append({'path':'/demo/reset','dataset':'demo-v1','scope':'private verification database'})
        checked(c.post('/auth/demo',json={'role':'navigator'}))

        def command(path, data):
            for _ in range(3):
                current=checked(c.get('/cases/SC-001'))
                response=c.post(path,json={'expected_version':current['version'],'idempotency_key':'video-v4:'+uuid.uuid4().hex,**data})
                if response.status_code==409:continue
                result=checked(response);writes.append({'path':path,'expected_version':current['version'],'actor_role':'navigator' if path=='/handoffs' else 'clinician' if path.endswith('/evidence') else 'patient'})
                return result
            raise RuntimeError('Isolated setup encountered repeated version changes')

        current=checked(c.get('/cases/SC-001'))
        command('/handoffs',{'case_id':'SC-001','receiver':'provider-a','scope':'episode','reason':'Synthetic demonstration: assessment referral awaiting the receiving service’s explicit decision.'})
        checked(c.post('/auth/demo',json={'role':'clinician'}))
        current=checked(c.get('/cases/SC-001'))
        command('/cases/SC-001/evidence',{'type':'investigation','reference':'synthetic://suhail-video-v4/investigation-pending','patient_id':current['patient_id'],'order_id':current['order_id'],'result_version':current['result_version'],'requires_onward':False,'document_text':f'SYNTHETIC INVESTIGATION REPORT\nPatient: {current["patient_id"]}\nOrder: {current["order_id"]}\nSource result version: {current["result_version"]}\nThe fictional diagnostic assessment was completed. Findings require a qualified clinician’s source review and documented interpretation. This retained demonstration document is pending verification. It does not record a clinical disposition.'})
        checked(c.post('/auth/demo',json={'role':'patient'}))
        command('/cases/SC-001/preferences',{'language':'en','channel':'portal'})
        checked(c.post('/auth/demo',json={'role':'navigator'}))
        final=checked(c.get('/cases/SC-001'))
        assert final['disposition']=='open' and final['owner']=='navigation-team'
        assert any(h['receiver']=='provider-a' and h['status']=='requested' for h in final['handoffs'])
    after=main_case();assert after==before
    output.write_text(json.dumps({'status':'passed','at':datetime.now(timezone.utc).isoformat(),'api':API,'model_assistance':False,'model_requests':0,'writes':writes,'main_before':before,'main_after':after,'main_clinical_state_preserved':True,'private_case_after':{key:final[key] for key in ['id','version','owner','disposition']},'purpose':'Actual active synthetic recording state, prepared independently of read-only UI capture'},indent=2)+'\n')
    print(json.dumps({'status':'passed','private_setup_commands':len(writes),'main_case_unchanged':True,'model_requests':0}))


if __name__=='__main__':main()
