"""Record v4 UI beats with measured, retained visual-state evidence.

Only synthetic authentication, isolated chat writes and isolated language
preferences are allowed. All care-command forms remain unsubmitted.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from capture_showcase import ShowcaseTour
from capture_ui import atomic_json, media_duration

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'runtime/video-v4'
STACKS = {'isolated': {'web': 'http://127.0.0.1:3002', 'api': 'http://127.0.0.1:18001'},
          'native': {'web': 'http://127.0.0.1:3000', 'api': 'http://127.0.0.1:18000'}}
PLANS = {
 '04': ('isolated', 'public', '/', False),
 '05': ('isolated', 'navigator', '/worklist', False),
 '06': ('isolated', 'navigator', '/worklist', False),
 '07': ('isolated', 'patient', '/patient', True),
 '08': ('native', 'clinician', '/clinical', False),
 '09': ('isolated', 'receiver_a', '/receiving', False),
 '10': ('isolated', 'clinician', '/cases/SC-001', False),
 '11': ('native', 'clinician', '/cases/SC-003', False),
 '12': ('native', 'patient', '/patient', True),
 '13': ('native', 'admin', '/operations', False),
}


class FocusTour(ShowcaseTour):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active = None
        self.cues = []

    def end(self):
        if self.active:
            self.pause(.2)
            self.log('visual_end', cue_id=self.active)
            self.active = None

    def goto(self, path):
        self.end()
        super().goto(path)

    def scroll_to(self, locator, seconds=.6):
        self.end()
        locator.first.wait_for(state='visible')
        offset = 90 if self.record['viewport']['width'] < 700 else 105
        target = locator.first.evaluate('(e,o)=>e.getBoundingClientRect().top+scrollY-o', offset)
        self.scroll_y(target, seconds)
        self.pause(.35)

    def ready(self, ident, phrase, locator, until=None, initial=False, scroll=True, hold=1.4, label=None, text_region=False):
        self.end()
        if scroll:
            self.scroll_to(locator)
        locator.first.wait_for(state='visible')
        self.pause(.35)
        box = locator.first.evaluate('''el=>{const r=document.createRange();r.selectNodeContents(el);const b=r.getBoundingClientRect();const w=Math.max(70,b.width+20);return {x:b.x-(w-b.width)/2,y:b.y-7,width:w,height:Math.max(54,b.height+14)}}''') if text_region else locator.first.bounding_box()
        assert box
        w,h = self.record['viewport'].values()
        x,y=max(0,box['x']),max(0,box['y'])
        right,bottom=min(w,box['x']+box['width']),min(h,box['y']+box['height'])
        box={'x':x,'y':y,'width':right-x,'height':bottom-y}
        assert box['width'] > 40 and box['height'] > 40, (ident,box)
        screenshot=self.folder/(ident+'-ready.png')
        seconds=round(time.monotonic()-self.started,3)
        self.page.screenshot(path=str(screenshot),full_page=False)
        self.log('visual_ready',cue_id=ident,source_seconds=seconds,
                 screenshot_path=str(screenshot.relative_to(ROOT)),bbox=box,url=self.page.url)
        cue={'id':ident,'phrase':phrase,'until_phrase':until or phrase,
             'visual_event':{'action':'visual_ready','cue_id':ident},
             'visual_end_event':{'action':'visual_end','cue_id':ident},
             'initial_state':initial}
        if label: cue['label']=label
        self.cues.append(cue); self.active=ident
        self.pause(hold)

    def chat(self, question=None):
        self.end()
        launcher=self.page.get_by_role('button',name=re.compile(r'^(Ask Suhail|اسأل سهيل)$'))
        if not self.page.get_by_role('dialog').count(): launcher.click()
        dialog=self.page.get_by_role('dialog',name=re.compile(r'^(Ask Suhail|اسأل سهيل)$'))
        dialog.wait_for(state='visible')
        dialog.locator('.cc-connected').wait_for(state='visible',timeout=30000)
        dialog.locator('.cc-thread-loading').wait_for(state='hidden',timeout=30000)
        if question:
            dialog.locator('#context-chat-question').fill(question)
            with self.page.expect_response(lambda r:r.request.method=='POST' and '/api/assistant/conversations/' in r.url and r.url.endswith('/messages')) as result:
                dialog.get_by_role('button',name=re.compile(r'^(Send message|إرسال الرسالة)$')).click()
            assert result.value.ok
            payload=result.value.json()
            assert payload['answer']['mode']=='authorized_records'
            self.log('authorized_chat_answer',question=question,mode=payload['answer']['mode'],conversation_id=payload['conversation_id'])
            self.page.wait_for_function("!document.querySelector('.cc-thinking')")
            dialog.locator('.cc-assistant-message').last.wait_for(state='visible')
            self.pause(.5)
        return dialog


def perform(t: FocusTour, scene):
    p=t.page
    if scene=='04':
        t.ready('public','The public page',p.locator('.lp-hero-copy'),until='connected care journey.',initial=True,scroll=False)
        t.ready('signin','Secure sign-in',p.locator('#signin'),until='by role.')
        t.authenticate('navigator');t.goto('/worklist')
        t.ready('workspace','Inside, each person',p.locator('.care-worklist'),until='their account.',scroll=False)
    elif scene=='05':
        dialog=t.chat()
        t.ready('conversation','Ask Suhail brings',dialog,until='one conversation.',initial=True,scroll=False)
        dialog=t.chat('How many requests do I have?')
        t.ready('workload','A navigator can ask',dialog.locator('.cc-assistant-message').last.locator('.cc-answer-metrics strong').first,until='current records.',scroll=False,text_region=True)
        dialog=t.chat('What is the next step for SC-001?')
        answer=dialog.locator('.cc-assistant-message').last
        t.ready('patient-answer','Ask about a specific patient',answer,until='source-linked details.',scroll=False,label='Authorized patient context')
        dialog=t.chat('Who is responsible?')
        answer=dialog.locator('.cc-assistant-message').last
        assert answer.locator('a[href*="/cases/SC-001"]').count()
        t.ready('episode-followup','Follow-up questions',answer,until='that episode.',scroll=False,label='Follow-up stays with the episode')
        t.end()
        link=answer.locator('a[href*="/cases/SC-001"]').first
        link.scroll_into_view_if_needed();link.click();p.wait_for_url('**/cases/SC-001**');t.pause(.8)
        t.ready('record-link','Open a result card',p.locator('.care-case'),until='relevant case section.',scroll=False,label='Direct link to the record')
        dialog=t.chat();dialog.get_by_role('button',name='Conversation history',exact=True).click()
        dialog.locator('.cc-history-list>button').first.wait_for(state='visible',timeout=30000)
        t.pause(.4)
        t.ready('history','Conversation history',dialog,until='answers are opened.',scroll=False)
    elif scene=='06':
        t.ready('list','Switch between the focused list',p.locator('.care-queue-panel'),until='focused list',initial=True)
        t.end();t.button('Journey board').click();t.pause(.6)
        t.ready('board','journey board',p.locator('.care-board'),until='authorized cases.')
        t.end();t.button('List view').click();t.button('Show cases needing reconciliation').click();t.pause(.5)
        t.ready('filter','Summary cards filter',p.locator('.care-worklist-stats'),until='reconciliation.')
        t.goto('/cases/SC-001')
        t.ready('episode','Open an episode',p.locator('#case-milestones'),until='the next action.')
        t.end();p.locator('.care-milestone-selector').last.click();t.pause(.5)
        t.ready('milestone','Select a milestone',p.locator('.care-milestone-inspector'),until='assigned work.')
        t.end();t.tab('Activity & provenance')
        t.ready('activity','The activity record',p.locator('#case-activity'),until='case changed.')
    elif scene=='07':
        t.english();t.top()
        t.ready('patient-next','On a phone',p.locator('.pt-next'),until='team first.',initial=True)
        t.ready('understanding','Receiving an update',p.locator('.pt-understanding'),until='separate actions.')
        t.ready('patient-question','Patients can ask',p.locator('.pt-questions'),until='staff confirmation.')
        dialog=t.chat('What is my next step?')
        t.ready('patient-chat','Ask Suhail helps',dialog.locator('.cc-assistant-message').last,until='care team.',scroll=False)
        t.end();p.keyboard.press('Escape');t.top();p.locator('.pt-language').click()
        p.wait_for_function("document.querySelector('.patient-view')?.dir==='rtl'")
        t.ready('arabic','English and right-to-left Arabic',p.locator('.pt-next'),until='visible content.')
    elif scene=='08':
        p.get_by_label('Search assigned episodes',exact=True).fill('Mariam')
        p.locator('.clinical-case-list button').filter(has_text='SC-001').first.click();t.pause(.5)
        t.log('local_case_filter',query='Mariam',clinical_state_changed=False)
        t.ready('clinical-work','The clinical workspace',p.locator('.ws-overview-strip'),until='questions together.',initial=True)
        t.ready('human-reply','A human reply',p.locator('.care-human-reply').first,until='and owner.')
        t.ready('request-opinion','Clinicians can request',p.locator('.ws-consult-request'),until='a specialist opinion;')
        t.authenticate('specialist');t.goto('/clinical')
        cases=t.read('/cases');chosen=None
        for item in cases:
            detail=t.read('/cases/'+item['id'])
            if any(q.get('type')=='clinician_to_specialist' and q.get('reply') for q in detail.get('consultations',[])):
                chosen=item['id'];break
        assert chosen, 'No actual answered specialist consultation'
        p.get_by_label('Search assigned episodes',exact=True).fill(chosen)
        p.locator('.clinical-case-list button').filter(has_text=chosen).first.click();t.pause(.5)
        t.ready('assigned-specialist','specialists see',p.locator('.care-human-reply').first,until='assigned consultations.')
        t.authenticate('clinician');t.goto('/cases/SC-001');t.open('Prepare an AI-assisted draft')
        t.ready('draft-controls','Optional AI assistance',p.locator('.ws-assistant'),until='clinical disposition.')
    elif scene=='09':
        packet=p.locator('.ws-referral-card').filter(has_text='SC-001').first
        t.ready('packet','Receiving services see',packet,until='granted scope.',initial=True)
        dialog=t.chat('How many requests do I have?')
        t.ready('provider-chat','Ask Suhail answers',dialog.locator('.cc-assistant-message').last,until='right referral.',scroll=False)
        t.end();p.keyboard.press('Escape');t.open('Reject or request more information',packet)
        t.ready('receiver-decision','Explicit acceptance',packet.locator('.ws-referral-decisions'),until='recovery work.')
        t.authenticate('receiver_b');t.goto('/receiving')
        packets=t.read('/referrals')
        accepted=[r for r in packets if r.get('status',r.get('handoff',{}).get('status'))=='accepted' and r.get('appointments')]
        assert accepted,'No accepted appointment packet'
        card=p.locator('.ws-referral-card').filter(has_text=accepted[0]['case_id']).first
        t.open('Report no available slots',card);t.open('Confirm an appointment',card)
        t.ready('appointments','Accepted services can report',card.get_by_label('Attendance / booking event',exact=True).first.locator('..'),until='a no-show.')
        t.end();t.authenticate('receiver_a');t.goto('/receiving')
        requested=p.locator('.ws-referral-card').filter(has_text='SC-001').first
        t.ready('sending-owner','A proposed transfer',requested,until='accountable.')
    elif scene=='10':
        case=t.read('/cases/SC-001')
        items=[e for e in case.get('evidence',[]) if e.get('status','current')=='current' and e.get('verification') in {'pending','pending_verification','unverified'} and e.get('patient_id')==case['patient_id'] and e.get('order_id')==case['order_id']]
        items.sort(key=lambda e:e.get('type')!='investigation');assert items
        card=p.locator('.evidence-card').filter(has_text=items[0]['reference']).first
        t.ready('pending-source','Returned evidence starts',card,until='pending verification.',initial=True)
        t.open('Read retained source',card)
        t.ready('retained-document','An authorized clinician reads',card.locator('.source-document'),until='result version.')
        t.goto('/cases/SC-007')
        t.ready('closure-check','The closure checklist',p.locator('.care-closure-panel'),until='support the endpoint.')
        t.open('Record authorized disposition',p.locator('.care-closure-panel'))
        t.ready('authorized-disposition','Only an authorized clinical disposition',p.locator('.care-closure-panel').locator('details[open]').last,until='required care.')
    elif scene=='11':
        t.ready('urgent','Trusted urgent signals',p.locator('.care-urgent-panel'),until='recorded separately.',initial=True)
        t.goto('/cases/SC-004')
        t.ready('quarantine','Identity conflicts',p.locator('.care-case'),until='authorized reconciliation.',scroll=False)
        t.goto('/cases/SC-008')
        t.ready('correction','Corrected results',p.locator('.care-patient-header').locator('..'),until='affected work.',scroll=False)
        t.ready('superseded','Earlier evidence',p.locator('.care-evidence-panel'),until='marked superseded.')
        t.goto('/cases/SC-006')
        t.ready('exceptions','Decline, inability to contact',p.locator('.care-case'),until='residual need.',scroll=False)
    elif scene=='12':
        assert p.locator('.patient-view').get_attribute('lang')=='en'
        t.ready('approved-plan','The completed patient view',p.locator('.pt-care-plan'),until='responsible team.',initial=True)
        t.open('View earlier result message')
        t.ready('historical-message','Earlier communication',p.locator('.pt-update'),until='historical records.')
        t.ready('available-help','Questions and requests',p.locator('.pt-questions form').last,until='stay available.')
        t.ready('documented-next','The wording follows',p.locator('.pt-next'),until='its source.')
    elif scene=='13':
        t.ready('operations','Operations measures',p.locator('.ws-stage-panel'),until='stay distinct.',initial=True)
        t.ready('delivery','Delivery records show',p.locator('.ws-outbox-panel'),until='underlying case.')
        t.ready('urgent-work','Urgent acknowledgements',p.locator('.ws-recovery-side'),until='own queue.')
        t.ready('definitions','The dashboard makes',p.locator('.ws-stage-panel'),until='traceable records.')
    else: raise ValueError(scene)
    t.end();t.pause(.5)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--go',action='store_true');parser.add_argument('--scenes',nargs='+');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--take',default='',help='Separate folder for a framing retake; previous footage stays preserved')
    args=parser.parse_args();scenes=json.loads((WORK/'storyboard.json').read_text());selected=set(args.scenes or PLANS)
    assert selected <= PLANS.keys()
    assert re.fullmatch(r'[A-Za-z0-9_-]*',args.take)
    if not args.go: print(json.dumps({s:PLANS[s] for s in sorted(selected)},indent=2));return
    folder=WORK/'captures';folder.mkdir(parents=True,exist_ok=True);path=folder/'manifest.json'
    manifest=json.loads(path.read_text()) if path.exists() else {'version':'4','scenes':[],'capture_policy':'Actual scoped synthetic UI. Clinical/model commands blocked. Isolated chat records and patient language only.'}
    cues_path=WORK/'ui-cues.json';all_cues=json.loads(cues_path.read_text()) if cues_path.exists() else {}
    def save(record):
        manifest['scenes']=sorted([r for r in manifest['scenes'] if r['id']!=record['id']]+[record],key=lambda r:r['id'])
        atomic_json(path,manifest)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=2'])
        for chapter in scenes:
            ident=chapter['id']
            if ident not in selected:continue
            old=next((r for r in manifest['scenes'] if r['id']==ident),None)
            if args.resume and old and old['status']=='completed':continue
            stack,role,route,mobile=PLANS[ident];base,api=STACKS[stack].values()
            viewport={'width':390,'height':844} if mobile else {'width':1600,'height':760}
            target=folder/(ident+('-'+args.take if args.take else ''));target.mkdir(exist_ok=True)
            record={'id':ident,'title':chapter['title'],'scene':chapter['scene'],'stack':stack,'role':role,'base_url':base,'api_url':api,'viewport':viewport,'status':'recording','media_type':'actual_application_capture','actions':[],'errors':[],'non_get_requests':[],'started_at':datetime.now(timezone.utc).isoformat()}
            context=browser.new_context(viewport=viewport,record_video_dir=str(target),record_video_size=viewport,is_mobile=mobile,has_touch=mobile)
            def guard(r):
                req=r.request;u=urlsplit(req.url)
                if req.method not in {'GET','HEAD','OPTIONS'}:
                    allowed=False
                    if u.scheme+'://'+u.netloc in {base,api} and req.method=='POST':
                        allowed=u.path in {'/api/auth/demo','/auth/demo'}
                        if stack=='isolated' and re.fullmatch(r'/api/assistant/conversations(?:/[A-Za-z0-9_-]+/messages)?',u.path):allowed=True
                        if stack=='isolated' and ident=='07' and u.path=='/api/cases/SC-001/preferences':
                            body=req.post_data_json;allowed=isinstance(body,dict) and body.get('language') in {'ar','en'} and set(body)<={'expected_version','idempotency_key','correlation_id','language','channel'}
                    record['non_get_requests'].append({'method':req.method,'path':u.path,'allowed':allowed})
                    if not allowed:record['errors'].append({'blocked_request':u.path});r.abort();return
                r.continue_()
            context.route('**/*',guard)
            began=time.monotonic();page=context.new_page();page.set_default_timeout(15000)
            page.on('pageerror',lambda e:record['errors'].append({'pageerror':str(e)}))
            page.on('response',lambda r:record['errors'].append({'http_status':r.status,'path':urlsplit(r.url).path}) if '/api/' in r.url and r.status>=400 else None)
            t=FocusTour(page,context,record,base,api,target);t.started=began;save(record)
            try:
                if role!='public':t.authenticate(role)
                if stack=='isolated' and role!='public':assert t.read('/assistant/context')['model_assistance']['enabled'] is False
                t.goto(route);perform(t,ident)
                record['status']='completed' if not record['errors'] else 'completed_with_errors'
                all_cues[ident]=t.cues;atomic_json(cues_path,all_cues)
            except Exception as exc:
                record['status']='failed';record['errors'].append({'type':type(exc).__name__,'message':str(exc)[:1800]})
                page.screenshot(path=str(target/'error.png'))
            finally:
                video=page.video;context.close();source=Path(video.path())
                record.update(video_path=str(source.relative_to(ROOT)),duration_seconds=media_duration(source),finished_at=datetime.now(timezone.utc).isoformat())
                save(record);print(json.dumps({'id':ident,'status':record['status'],'cues':len(t.cues),'errors':record['errors']}),flush=True)
            if record['status']!='completed':browser.close();raise SystemExit(1)
        browser.close()


if __name__=='__main__':main()
