"""Prepare the short submission edit from real, source-hashed UI recordings.

Existing v4 source clips are read only. The changed public/role-menu view is
captured separately. All final timing is rebuilt from the new narration.
"""
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from sync_plan import build_chapter

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'runtime/video-3min'
V4=ROOT/'runtime/video-v4'
SOURCES={'03':'05','04':'07','05':'08','06':'09','07':'10','08':'12'}
# Cue IDs identify actual retained v4 screenshots and decoded source PTS.
CUES={
 '03':[
  ('conversation','Navigators can open','one conversation'),
  ('workload','Check the current workload','current workload'),
  ('patient-answer',"Ask for a patient's next step",'next step'),
  ('episode-followup','Follow up about responsibility','that episode'),
  ('record-link','Open a result','relevant case section'),
  ('history','Conversation history','stays private'),
 ],
 '04':[
  ('patient-next','Patients see','their phone'),
  ('understanding','Understanding is recorded','an update'),
  ('patient-question','They can ask','a question'),
  ('patient-chat','Ask Suhail helps','their own records'),
  ('arabic','English and Arabic','the journey'),
 ],
 '05':[
  ('clinical-work','Clinicians bring','one workspace'),
  ('human-reply','Human replies','and owner'),
  ('assigned-specialist','Specialists see','assigned consultations'),
  ('draft-controls','Optional AI assistance','clinical decisions'),
 ],
 '06':[
  ('packet','Receiving services see','minimum referral packet'),
  ('receiver-decision','They explicitly accept','rejection reason'),
  ('appointments','Appointment controls','no-shows distinct'),
  ('sending-owner','A proposed transfer','intended responsibility'),
 ],
 '07':[
  ('pending-source','Returned evidence stays pending','stays pending'),
  ('retained-document','an authorized clinician reviews','result version'),
  ('closure-check','The closure checklist','complete required care'),
  ('authorized-disposition','Documented evidence','the endpoint'),
 ],
 '08':[
  ('approved-plan','The completed patient view','responsible team'),
  ('historical-message','Previous communication','stays recorded'),
  ('available-help','Questions and support','stay available'),
  ('documented-next','The next step','documented outcome'),
 ],
}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def clock():
    audio=read(WORK/'narration-manifest.json')['chapters']
    assert len(audio)==9 and all(a['status']=='generated' for a in audio)
    # Keep a comfortable margin under the180s cap, including AAC mux padding.
    seconds=sum(a['duration_seconds'] for a in audio)
    speed=seconds/(174.6-9*.8)
    if not .85<=speed<=1.2:raise ValueError('Narration would need an unnatural speed; revise ungenerated copy instead')
    speed=round(speed,8)
    rounded=sum(math.ceil((a['duration_seconds']/speed+.8)*25-1e-7)/25 for a in audio)
    assert rounded<179
    config={'audio_speed':speed,'lead_seconds':.4,'tail_seconds':.4,'fps':25,'audio_seconds':seconds,'planned_video_seconds':rounded,'max_video_seconds':180,'narration_chapters':9,'narration_characters':read(WORK/'narration-manifest.json')['selected_text_characters']}
    write(WORK/'clock.json',config);print(json.dumps(config));return config


def compose_ui(fresh_capture,fresh_cues):
    scenes={s['id']:s for s in read(WORK/'storyboard.json')}
    original=read(V4/'captures/manifest.json');caps={c['id']:c for c in original['scenes']}
    selected=[];specs={}
    for ident,old_id in SOURCES.items():
        capture=copy.deepcopy(caps[old_id]);assert capture['status']=='completed' and not capture['errors']
        source=ROOT/capture['video_path'];assert source.is_file()
        capture.update(id=ident,title=scenes[ident]['title'],scene=scenes[ident]['scene'])
        capture['reused_actual_recording']={'manifest':str((V4/'captures/manifest.json').relative_to(ROOT)),'manifest_sha256':sha(V4/'captures/manifest.json'),'original_chapter':old_id,'source_video_sha256':sha(source),'new_narration_and_edit':True}
        rows=[]
        for index,(cue_id,phrase,until) in enumerate(CUES[ident]):
            event=next(e for e in capture['actions'] if e.get('action')=='visual_ready' and e.get('cue_id')==cue_id)
            assert event['source_calibration']['source_video_sha256']==sha(source)
            assert event['source_calibration']['screenshot_sha256']==sha(ROOT/event['screenshot_path'])
            rows.append({'id':cue_id,'phrase':phrase,'until_phrase':until,'initial_state':index==0,'visual_event':{'action':'visual_ready','cue_id':cue_id},'visual_end_event':{'action':'visual_end','cue_id':cue_id}})
            if index==0:capture['trim_start_seconds']=event['source_seconds']
        selected.append(capture);specs[ident]=rows
    fresh=read(fresh_capture);assert fresh['id']=='02' and fresh['status']=='completed' and not fresh['errors']
    selected.append(fresh);specs['02']=read(fresh_cues)
    write(WORK/'captures/manifest.json',{'version':'submission-3min','capture_policy':'Read-only reuse of actual verified fictional records; fresh current UI audience/role-menu capture; no clinical/model commands. New speech-anchored edit.','scenes':sorted(selected,key=lambda c:c['id'])})
    write(WORK/'ui-cues.json',specs)
    print(json.dumps({'ui_chapters':len(selected),'ui_cues':sum(len(r) for r in specs.values())}))


def merge_motion():
    path=WORK/'captures/manifest.json';manifest=read(path);motion=read(WORK/'authored-sync-chapters.json')
    assert motion['storyboard_sha256']==sha(WORK/'storyboard.json')
    current={c['id']:c for c in manifest['scenes']}
    for c in motion['captures']:
        assert c['status']=='completed' and not c['errors'] and sha(ROOT/c['video_path'])==c['video_sha256']
        current[c['id']]=c
    assert set(current)=={s['id'] for s in read(WORK/'storyboard.json')}
    manifest['scenes']=[current[k] for k in sorted(current)];write(path,manifest)


def plan():
    config=read(WORK/'clock.json');captures_path=WORK/'captures/manifest.json';caps={c['id']:c for c in read(captures_path)['scenes']}
    authored={c['id']:c for c in read(WORK/'authored-sync-chapters.json')['chapters']};rows=read(WORK/'ui-cues.json');audio={a['chapter']:a for a in read(WORK/'narration-manifest.json')['chapters']};chapters=[]
    for scene in read(WORK/'storyboard.json'):
        ident=scene['id'];assert sha(WORK/(ident+'.mp3'))==audio[ident]['audio_sha256']
        if ident in authored:chapter=authored[ident]
        else:
            a=read(WORK/(ident+'-alignment.json'));a=a.get('normalized_alignment') or a['alignment']
            chapter=build_chapter(ident,caps[ident],a,rows[ident],audio[ident]['duration_seconds'],speed=config['audio_speed'],lead=.4,tail=.4,anticipation=.2,require_visible_holds=True)
        assert chapter['all_semantic_anchors_pass'];chapters.append(chapter)
    result={'schema_version':'suhail-audio-led-visual-sync-v1','generated_at':datetime.now(timezone.utc).isoformat(),'status':'planned','method':'Exact new speech alignment to verified actual UI state PTS and new authored final-clock animations','chapters':chapters,'total_cues':sum(len(c['cues']) for c in chapters),'all_semantic_anchors_pass':True,'final_encoded_visual_review_required':True,'storyboard_sha256':sha(WORK/'storyboard.json'),'capture_manifest_sha256':sha(captures_path),'generation_requests':0,'application_state_changes':0}
    write(WORK/'sync-plan.json',result);print(json.dumps({'chapters':len(chapters),'cues':result['total_cues'],'duration_seconds':sum(c['duration_seconds'] for c in chapters)}))


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['clock','compose-ui','merge-motion','plan']);p.add_argument('--fresh-capture',type=Path,default=WORK/'captures02.json');p.add_argument('--fresh-cues',type=Path,default=WORK/'new-rolemenu-cues.json');args=p.parse_args()
    if args.stage=='clock':clock()
    elif args.stage=='compose-ui':compose_ui(args.fresh_capture,args.fresh_cues)
    elif args.stage=='merge-motion':merge_motion()
    else:plan()


if __name__=='__main__':main()
