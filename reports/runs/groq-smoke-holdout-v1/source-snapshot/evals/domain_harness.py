"""Actual transactional domain command trajectories on an isolated evaluation DB.

The harness controls fictional behavior/capacity, never clinical ground truth.
It uses the same intake, command, authorization, worker and closure code as the API.
"""
from __future__ import annotations
import datetime as dt,json,uuid,os
from pathlib import Path
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from .common import now

ACTORS={
 'navigator':{'id':'eval-navigator','name':'Synthetic Navigator','role':'navigator','organization':'source-clinic','patient_id':None},
 'clinician':{'id':'eval-clinician','name':'Synthetic Clinician','role':'clinician','organization':'source-clinic','patient_id':None},
 'specialist':{'id':'eval-specialist','name':'Synthetic Specialist','role':'specialist','organization':'specialist-clinic','patient_id':None},
 'receiver_a':{'id':'eval-receiver-a','name':'Synthetic Receiver A','role':'receiver_a','organization':'provider-a','patient_id':None},
 'receiver_b':{'id':'eval-receiver-b','name':'Synthetic Receiver B','role':'receiver_b','organization':'provider-b','patient_id':None},
 'connector':{'id':'eval-connector','name':'Synthetic Source','role':'connector','organization':'source-clinic','patient_id':None},
 'admin':{'id':'eval-admin','name':'Synthetic Operator','role':'admin','organization':'source-clinic','patient_id':None},
}

_ENGINE_CACHE={}

class DomainHarness:
    def __init__(self,path:Path):
        # Explicit test-store selection prevents evaluation from touching demo/owner data.
        os.environ.setdefault('DATABASE_URL','sqlite:///'+str(path.resolve()))
        from services.api.db import Base
        key=str(path.resolve())
        if key not in _ENGINE_CACHE:
            engine=create_engine('sqlite:///'+key,connect_args={'check_same_thread':False})
            Base.metadata.create_all(engine);_ENGINE_CACHE[key]=(engine,sessionmaker(bind=engine,expire_on_commit=False))
        self.engine,self.Session=_ENGINE_CACHE[key]
        self.db=self.Session();self.events=[];self.assertions=[];self.case=None;self.sequence=0
    def close(self):self.db.close()
    def actor(self,role):
        if role=='patient':return {'id':'eval-patient-'+self.case.patient_id,'name':'Synthetic Patient','role':'patient','organization':'patient','patient_id':self.case.patient_id}
        return dict(ACTORS[role])
    def check(self,name,predicate):
        self.assertions.append({'name':name,'passed':bool(predicate)})
        if not predicate:raise AssertionError(name)
    def intake(self,truth,**overrides):
        from services.api import domain as d
        from services.api.db import Case
        c=truth['case'];data={'case_id':c['id'],'dataset':'eval-'+truth['id'],'event_id':c['id']+'-RESULT-v1','source_organization':'source-clinic','patient_id':c['patient_id'],'patient_name':c['patient_name'],'order_id':c['order_id'],'result_version':1,'test_code':'FIT_POSITIVE','issued_at':'2026-11-14T09:00:00+00:00','identity_verified':True,'trusted_urgent':False,'language':c['language'],'source_reference':c['source_references'][0],**overrides}
        r=d.intake(self.db,self.actor('connector'),data);self.case=self.db.get(Case,r['id']);self.events.append({'command':'intake','input':data,'version':self.case.version});return r
    def snapshot(self):
        from services.api import domain as d
        self.db.refresh(self.case)
        return d.serialize_case(self.db,self.case,self.actor('clinician'),internal=True)
    def cmd(self,kind,role='navigator',**fields):
        from services.api import domain as d
        self.db.refresh(self.case);self.sequence+=1
        data={'expected_version':self.case.version,'idempotency_key':self.case.id+'-'+str(self.sequence)+'-'+kind,**fields}
        r=d.command(self.db,self.actor(role),self.case.id,kind,data);self.db.refresh(self.case)
        self.events.append({'command':kind,'actor_role':role,'input':data,'version':self.case.version,'record_id':r.get('record_id')});return r
    def denied(self,name,kind,role='clinician',expected=(403,409,422),**fields):
        try:self.cmd(kind,role,**fields)
        except HTTPException as e:
            self.db.rollback();self.events.append({'command':kind,'actor_role':role,'expected_denial':e.status_code,'detail':e.detail});self.check(name,e.status_code in expected);return
        raise AssertionError(name+': unexpectedly authorized')
    def deliver(self):
        from services.api.worker import run_once
        result=run_once(self.db,deliver_external=False,case_id=self.case.id)
        self.events.append({'command':'worker.run_once','result':result})
        self.db.expire_all();self.db.refresh(self.case)
    def clock_advance(self,hours):
        from services.api.db import Setting
        setting=self.db.get(Setting,'demo_clock')
        if not setting:setting=Setting(key='demo_clock',value={'hours':0});self.db.add(setting)
        setting.value={'hours':setting.value.get('hours',0)+hours};self.db.commit();self.events.append({'command':'demo_clock_configuration','hours_advanced':hours,'demonstration_only':True})
    def reset_clock(self):
        from services.api.db import Setting
        setting=self.db.get(Setting,'demo_clock')
        if setting:setting.value={'hours':0};self.db.commit()
    def communicate(self,outcome='passed'):
        r=self.cmd('communication',language=self.case.language,channel='portal');msg=r['record_id'];self.deliver()
        s=self.snapshot();m=next(x for x in s['communications'] if x['id']==msg)
        self.check('delivery_does_not_acknowledge',m['acknowledged_at'] is None)
        self.check('delivery_does_not_establish_understanding',m['understanding']=='unknown')
        self.cmd('acknowledgement','patient',communication_id=msg)
        self.check('acknowledgement_does_not_establish_understanding',next(x for x in self.snapshot()['communications'] if x['id']==msg)['understanding']=='unknown')
        self.cmd('understanding','patient',communication_id=msg,outcome=outcome);return msg
    def evidence(self,type_,**extra):
        fields={'document_text':'Project-generated synthetic source document. Known truth: '+type_+' for case '+self.case.id+'. This fixture is not clinical guidance.','type':type_,'reference':f'synthetic://{self.case.id}/{type_}/{self.sequence}','patient_id':self.case.patient_id,'order_id':self.case.order_id,'result_version':self.case.result_version,**extra}
        r=self.cmd('evidence_add','clinician',**fields);eid=r['record_id']
        self.cmd('evidence_verify','clinician',evidence_id=eid,verified=True,reason='Synthetic scenario source identity/order/version independently checked');return eid
    def clear_generic(self):
        from services.api.domain import GATES
        for t in self.snapshot()['tasks']:
            if t['status'] not in ('completed','cancelled') and t['type'] not in GATES:
                self.cmd('task',task_id=t['id'],status='completed',reason='Scenario actor completed the recorded agreed coordination action')
    def consultations(self):
        r=self.cmd('consultation','patient',type='patient_to_clinician',question='What is my next step?',recipient='clinician')
        self.cmd('consultation_reply','clinician',consultation_id=r['record_id'],reply='Your screening result needs diagnostic follow-up. We will discuss the assessment with you.',agreed_action='Confirm the patient next step and arrange assessment',action_owner='navigation-team')
        r=self.cmd('consultation','clinician',type='clinician_to_specialist',question='Please advise the coordination steps for the documented actionable screening result.',recipient='specialist')
        self.cmd('consultation_reply','specialist',consultation_id=r['record_id'],reply='Arrange the documented diagnostic assessment and return the report for clinician review.',agreed_action='Obtain assessment report and clinician review',action_owner='navigation-team')
        self.clear_generic();s=self.snapshot();self.check('both_consultations_have_human_reply',len(s['consultations'])==2 and all(x['human_author'] for x in s['consultations']))
    def handoff(self,provider='provider-a',scope='task',reject=False):
        r=self.cmd('handoff',receiver=provider,scope=scope,reason='Synthetic permitted minimal diagnostic referral');hid=r['record_id'];role='receiver_a' if provider=='provider-a' else 'receiver_b';owner=self.case.owner
        self.check('proposal_preserves_owner',self.case.owner==owner)
        self.cmd('handoff_reject' if reject else 'handoff_accept',role,handoff_id=hid,reason='Synthetic service capacity unavailable' if reject else 'Synthetic destination explicitly accepts intended scope')
        if reject or scope=='task':self.check('task_scope_or_rejection_preserves_episode_owner',self.case.owner==owner)
        return hid
    def appointment(self,provider='provider-a',status='attended'):
        role='receiver_a' if provider=='provider-a' else 'receiver_b'
        r=self.cmd('appointment_create',role,provider=provider,scheduled_at='2026-11-18T09:00:00+00:00');aid=r['record_id'];self.cmd('appointment_event',role,appointment_id=aid,status=status,source_event_id=self.case.id+'-'+status+'-'+str(self.sequence));return aid
    def urgent_dispose(self):
        e=self.snapshot()['escalations'][0];self.cmd('escalation_ack','clinician',escalation_id=e['id'])
        self.denied('urgent_acknowledgement_is_not_disposition','communication',role='navigator',language='en',channel='portal')
        self.cmd('escalation_disposition','clinician',escalation_id=e['id'],decision='Human review recorded; resume configured follow-up',reason='Qualified synthetic clinician reviewed source flag and documented next action')
    def complete(self,scenario='normal_completion',arm='B',finalize=True):
        from services.api import domain as d
        if self.case.quarantine_reason:self.cmd('reconciliation',identity_verified=True,pathway='colorectal-fit',source_reference='synthetic://verified-identity',reason='Authorized matching review from synthetic source evidence')
        if self.case.urgent:self.urgent_dispose()
        self.communicate()
        if arm=='A':return
        self.consultations()
        if scenario in ('rejected_handoff','no_show'):
            self.handoff('provider-a',reject=True);self.clear_generic()
        self.handoff('provider-a')
        if scenario=='no_show':
            aid=self.appointment(status='no_show');self.cmd('appointment_event','receiver_a',appointment_id=aid,status='attended',source_event_id=self.case.id+'-attended-recovery')
        else:self.appointment()
        self.evidence('investigation')
        onward=scenario=='onward_care'
        self.evidence('reviewed_outcome',requires_onward=onward)
        self.evidence('patient_updated')
        if onward:
            self.handoff('provider-b',scope='task')
            self.denied('accepted_onward_referral_cannot_close_required_care','disposition',category='completed_required_care',reason='Attempt before treatment evidence')
            self.evidence('treatment_initiated')
        self.clear_generic()
        check=d.closure_check(self.db,self.case);self.check('closure_allowed_only_after_required_care',check['allowed'])
        if finalize:
            self.cmd('disposition','clinician',category='completed_required_care',reason='All configured synthetic diagnostic/care endpoint evidence checked',residual_need='')
            self.check('authorized_completion_persisted',self.case.disposition=='completed_required_care')
    def journey(self):
        s=self.snapshot();return {'notification':any(x['delivery_status']=='delivered' for x in s['communications']),'understanding':any(x['understanding']=='passed' for x in s['communications']),'consultation':sum(x['status']=='replied' for x in s['consultations']),'accepted_handoffs':sum(x['status']=='accepted' for x in s['handoffs']),'attendance':any(x['status']=='attended' for x in s['appointments']),'care_completed':s['disposition']=='completed_required_care','residual_need':s['residual_need'],'delay_reasons':s['delay_reasons'],'disposition':s['disposition'],'owner':s['owner']}
    def run_scenario(self,truth):
        from services.api import domain as d
        from services.api.db import Case,Evidence,Task,Handoff,Communication,Outbox
        scenario=truth['truth']['scenario'];opts={}
        if scenario=='unsupported_pathway':opts['test_code']='UNSUPPORTED'
        if scenario=='identity_conflict':opts['identity_verified']=False
        if scenario=='urgent_timeout':opts['trusted_urgent']=True
        if scenario=='onward_care':opts['requires_onward']=True
        self.intake(truth,**opts)
        self.check('intake_owned_and_tasks_persisted',bool(self.case.owner) and bool(self.snapshot()['tasks']))
        self.check('issuance_and_ingestion_separate',self.case.issued_at!=self.case.created_at)
        if scenario=='normal_completion':self.complete()
        elif scenario in ('unsupported_pathway','identity_conflict'):
            self.check('owned_quarantine',bool(self.case.quarantine_reason) and any(t['type']=='quarantine' and t['assignee'] for t in self.snapshot()['tasks']))
            self.denied('ordinary_task_cannot_release_quarantine','task',task_id=self.snapshot()['tasks'][0]['id'],status='completed',reason='Cannot bypass dedicated reconciliation')
            self.cmd('reconciliation',identity_verified=True,pathway='colorectal-fit',source_reference='synthetic://verified-identity',reason='Authorized source reconciliation')
            self.check('authorized_recovery_recreates_work',not self.case.quarantine_reason and len(self.snapshot()['tasks'])>2)
        elif scenario=='corrected_result':
            eid=self.evidence('investigation');old_version=self.case.result_version
            self.intake(truth,event_id=self.case.id+'-CORRECTION',result_version=2)
            self.check('correction_supersedes_evidence',self.db.get(Evidence,eid).status=='superseded' and self.case.result_version>old_version)
            self.check('correction_reopens_review',not d.closure_check(self.db,self.case)['allowed'])
        elif scenario=='wrong_evidence':
            r=self.cmd('evidence_add','clinician',type='investigation',reference='synthetic://wrong-patient',patient_id='WRONG',order_id=self.case.order_id,result_version=1)
            self.denied('wrong_patient_evidence_cannot_verify','evidence_verify',evidence_id=r['record_id'],verified=True,reason='Attempt matching check')
        elif scenario=='unanswered_consultation':
            self.cmd('consultation','patient',type='patient_to_clinician',question='Please explain the next step',recipient='clinician')
            self.check('unanswered_question_assigned',any(t['type'].startswith('consultation:') and t['assignee']=='clinician' for t in self.snapshot()['tasks']))
        elif scenario=='failed_understanding':
            self.communicate('needs_help');self.check('teachback_failure_creates_owned_help',any(t['type']=='understanding_help' and t['assignee'] for t in self.snapshot()['tasks']))
        elif scenario=='access_barrier':
            self.cmd('barrier','patient',barrier='transport',detail='Synthetic transport access barrier');self.check('barrier_assigned_and_reason_retained',any(t['type']=='barrier' and t['assignee'] for t in self.snapshot()['tasks']) and 'barrier:transport' in self.case.delay_reasons)
        elif scenario=='rejected_handoff':self.handoff(reject=True);self.check('rejected_work_recoverable',any(t['type']=='referral_recovery' for t in self.snapshot()['tasks']))
        elif scenario=='expired_handoff':
            self.cmd('handoff',receiver='provider-a',scope='episode',reason='Synthetic pending handoff');self.clock_advance(25);self.deliver();self.check('deadline_preserved',any(h['due_at'] for h in self.snapshot()['handoffs']));self.reset_clock()
        elif scenario in ('no_slots','cancelled_visit','no_show'):
            self.handoff();status='cancelled' if scenario=='cancelled_visit' else scenario;self.appointment(status=status);self.check('appointment_failure_owned_and_not_attendance',any(t['type']=='appointment_recovery' and t['assignee'] for t in self.snapshot()['tasks']) and not any(a['status']=='attended' for a in self.snapshot()['appointments']))
        elif scenario=='urgent_timeout':
            self.check('urgent_routes_without_model',bool(self.snapshot()['escalations']));self.denied('urgent_blocks_routine_progress','communication',role='navigator',language='en',channel='portal');self.clock_advance(2);self.deliver();self.reset_clock();self.urgent_dispose()
        elif scenario=='provider_outage':
            self.cmd('handoff',receiver='provider-a',scope='task',reason='Synthetic outage recovery');self.check('durable_owned_outbox',any(x.owner and x.status=='pending' for x in self.db.scalars(select(Outbox).where(Outbox.case_id==self.case.id))))
        elif scenario=='duplicate_reordered':
            before=len(self.snapshot()['tasks']);self.intake(truth);self.check('duplicate_intake_no_tasks_duplicated',len(self.snapshot()['tasks'])==before)
            self.intake(truth,event_id=self.case.id+'-V2',result_version=2);self.intake(truth,event_id=self.case.id+'-DELAYED',result_version=1);self.check('reordered_old_result_cannot_downgrade_version',self.case.result_version==2)
        elif scenario=='unauthorized_access':
            try:d.authorize_case(self.db,ACTORS['receiver_b'],self.case.id)
            except HTTPException as e:self.db.rollback();self.check('ungranted_receiver_source_record_denied',e.status_code==403)
            else:raise AssertionError('ungranted receiver accessed source record')
            self.denied('navigator_cannot_clinically_dispose','disposition',role='navigator',category='completed_required_care',reason='Unauthorized attempt')
        elif scenario=='onward_care':
            self.evidence('reviewed_outcome',requires_onward=True);self.handoff('provider-b');self.denied('onward_acceptance_not_care_endpoint','disposition',category='completed_required_care',reason='Attempt at referral acceptance');self.check('onward_need_visible',bool(self.case.residual_need) and any(t['type']=='treatment_initiated' and t['status']!='completed' for t in self.snapshot()['tasks']))
        elif scenario in ('informed_decline','unable_to_contact'):
            self.evidence('outreach');self.evidence('exception_review');self.cmd('disposition','clinician',category=scenario,reason='Synthetic clinician authorized exception after documented outreach',residual_need='Diagnostic care remains indicated and unresolved');self.check('exception_not_counted_completed',self.case.disposition!='completed_required_care' and bool(self.case.residual_need))
        self.check('all_active_tasks_have_owner_and_deadline',all(t['assignee'] and t['next_action'] and t['due_at'] for t in self.snapshot()['tasks'] if t['status'] not in ('completed','cancelled')))
        return self.journey()
