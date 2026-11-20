"""Render four speech-aligned authored v4 illustrations; never invokes TTS/models.

Each completed clip retains its own final chapter clock. The parent must honor
preserve_source_timing and merge the returned capture/sync rows only after UI
recording completes. Ready PNGs are actual decoded frames from these clips.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

from motion_scenes import render
from sync_plan import aligned_phrase, build_chapter

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'runtime/video-v4'
FPS=25
LEAD=.6
TAIL=.8
SPEED=1.
ANTICIPATION=.24
SPECS={
 '01':{'scene':'solution','maximum':34,'cues':[
  {'id':'purpose','phrase':'Meet Suhail Health','until_phrase':'screening follow-up','phase':0,'initial_state':True,'hold_phase':1.5,'box':{'x':130,'y':205,'width':1170,'height':530}},
  {'id':'result-journey','phrase':'An actionable result','until_phrase':'start of a journey','phase':8.5,'box':{'x':115,'y':520,'width':1710,'height':245}},
  {'id':'connected-journey','phrase':'Suhail connects','until_phrase':'documented care','phase':18.5,'box':{'x':205,'y':565,'width':1520,'height':205}},
  {'id':'patient-team','phrase':'Patients see','until_phrase':'owns the work','phase':23.6,'box':{'x':95,'y':445,'width':1718,'height':345}},
  {'id':'ask-suhail','phrase':'And with Ask Suhail','until_phrase':'relevant detail','phase':25.,'box':{'x':1323,'y':180,'width':498,'height':145}},
 ]},
 '02':{'scene':'agents','maximum':35,'cues':[
  {'id':'six-functions','phrase':'Six focused agents','until_phrase':'that journey','phase':4.5,'box':{'x':95,'y':463,'width':1720,'height':370}},
  {'id':'intake','phrase':'Intake','until_phrase':'source facts','phase':4.5,'box':{'x':98,'y':466,'width':550,'height':170}},
  {'id':'pathway_router','phrase':'Routing','until_phrase':'configured pathway','phase':4.5,'box':{'x':680,'y':466,'width':550,'height':170}},
  {'id':'safety_escalation','phrase':'Safety','until_phrase':'urgent signals','phase':4.5,'box':{'x':1262,'y':466,'width':550,'height':170}},
  {'id':'patient_navigator','phrase':'Patient navigation','until_phrase':'next step','phase':4.5,'box':{'x':98,'y':657,'width':550,'height':170}},
  {'id':'coordination','phrase':'Coordination','until_phrase':'appointment recovery','phase':4.5,'box':{'x':680,'y':657,'width':550,'height':170}},
  {'id':'closure_evidence','phrase':'Closure evidence','until_phrase':'verification','phase':4.5,'box':{'x':1262,'y':657,'width':550,'height':170}},
  {'id':'human-governance','phrase':'Each function','until_phrase':'govern the decisions','phase':4.5,'box':{'x':95,'y':870,'width':1720,'height':67}},
 ]},
 '03':{'scene':'models','maximum':28,'cues':[
  {'id':'current-model','phrase':'The six functions','until_phrase':'through Groq','phase':.5,'box':{'x':1338,'y':476,'width':485,'height':282}},
  {'id':'permission-grounding','phrase':'Ask Suhail','until_phrase':'workflow records','phase':3.8,'box':{'x':95,'y':817,'width':1118,'height':84}},
  {'id':'separate-rules','phrase':'Model configuration','until_phrase':'evidence rules','phase':7.8,'box':{'x':92,'y':903,'width':1640,'height':38}},
  {'id':'future-compatible','phrase':'This creates a path','until_phrase':'care team’s authority','phase':15.4,'box':{'x':1338,'y':804,'width':485,'height':103}},
 ]},
 '14':{'scene':'closing','maximum':31,'cues':[
  {'id':'software-checks','phrase':'Software verification','until_phrase':'deterministic checks','phase':.8,'box':{'x':95,'y':520,'width':1725,'height':270}},
  {'id':'execution-records','phrase':'Execution records','until_phrase':'each measurement','phase':11.5,'box':{'x':95,'y':475,'width':1725,'height':318}},
  {'id':'connected-care','phrase':'Suhail Health','until_phrase':'screening-to-care journey','phase':20.,'box':{'x':95,'y':302,'width':1615,'height':400}},
  {'id':'focused-agents','phrase':'Six focused agents','until_phrase':'the workflow','phase':20.5,'box':{'x':613,'y':732,'width':310,'height':50}},
  {'id':'ask-context','phrase':'Ask Suhail','until_phrase':'within reach','phase':21.,'box':{'x':1337,'y':198,'width':488,'height':142}},
  {'id':'clinical-authority','phrase':'The care team','until_phrase':'in control','phase':21.5,'box':{'x':940,'y':732,'width':392,'height':50}},
 ]},
}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def frame_floor(t):return math.floor(t*FPS+1e-8)/FPS
def frame_ceil(t):return math.ceil(t*FPS-1e-8)/FPS

def prepare(ident,chapter,audio):
 spec=SPECS[ident]
 assert audio['status']=='generated' and audio['model']=='eleven_v4' and audio['voice']=='Sarah'
 assert hashlib.sha256(chapter['text'].encode()).hexdigest()==audio['text_sha256'], 'Narration changed: '+ident
 alignment_path=WORK/(ident+'-alignment.json')
 alignment=json.loads(alignment_path.read_text())['alignment']
 duration=frame_ceil(audio['duration_seconds']+LEAD+TAIL)
 cues=[];anchors=[];focus=[]
 for raw in spec['cues']:
  row=dict(raw);start=aligned_phrase(alignment,row['phrase']);end=aligned_phrase(alignment,row['until_phrase'])
  ready=0. if row.get('initial_state') else frame_floor(start['start_seconds']+LEAD-ANTICIPATION)
  hold_end=frame_ceil(end['end_seconds']+LEAD+1/FPS)
  if anchors and ready<=anchors[-1]['time_seconds']:
   raise ValueError(f'Insufficient sentence pause to hold prior stage and anticipate next: {ident}/{row["id"]}')
  anchors.append({'time_seconds':ready,'phase':row['phase']})
  if row.get('hold_phase') is not None:
   anchors.append({'time_seconds':min(ready+.4,hold_end-.04),'phase':row['hold_phase']})
  anchors.append({'time_seconds':hold_end,'phase':row.get('hold_phase',row['phase'])})
  row.update(source_seconds=ready,source_visible_until_seconds=hold_end,
             source_description='Authored Canvas stage, fully visible before the spoken cue and retained through its sentence; verify decoded ready reference.',highlight=False)
  cues.append(row)
  if ident=='02' and row['id'] in {'intake','pathway_router','safety_escalation','patient_navigator','coordination','closure_evidence'}:
   focus.append({'id':row['id'],'start_seconds':ready,'end_seconds':hold_end})
 # Never append an implicit sweep into unrelated later stages during tail padding.
 anchors.append({'time_seconds':duration,'phase':anchors[-1]['phase']})
 config={'phase_anchors':anchors,'focus_cues':focus,'show_workspace_assistant':True}
 folder=WORK/'motion';folder.mkdir(exist_ok=True)
 timing=folder/(ident+'-timing.json');timing.write_text(json.dumps(config,indent=2)+'\n')
 return {'id':ident,'scene':spec['scene'],'duration_seconds':duration,'audio_duration_seconds':audio['duration_seconds'],
         'alignment':alignment,'cues':cues,'timing_path':timing,'output':folder/(ident+'-'+spec['scene']+'.mp4'),
         'audio_sha256':audio['audio_sha256'],'text_sha256':audio['text_sha256'],'alignment_sha256':sha(alignment_path)}

def render_one(plan,reuse_rendered=False):
 metadata_path=plan['output'].with_suffix('.json')
 metadata=None
 if reuse_rendered and metadata_path.is_file():
  candidate=json.loads(metadata_path.read_text())
  if candidate.get('status')!='completed' or candidate.get('scene')!=plan['scene']:
   raise ValueError('Existing motion metadata is not a completed matching scene: '+plan['id'])
  if abs(candidate['duration_seconds']-plan['duration_seconds'])>.002 or candidate.get('fps')!=FPS:
   raise ValueError('Existing motion timing differs: '+plan['id'])
  if sha(plan['output'])!=candidate['video_sha256']:
   raise ValueError('Existing motion video hash differs: '+plan['id'])
  for name,digest in candidate['assets'].items():
   if sha(ROOT/name)!=digest:
    raise ValueError('Existing motion asset/config changed: '+name)
  timing_key=str(plan['timing_path'].relative_to(ROOT))
  if candidate['assets'].get(timing_key)!=sha(plan['timing_path']):
   raise ValueError('Regenerated narration timing does not match original rendered config: '+plan['id'])
  metadata=candidate
  print(json.dumps({'reused_rendered_clip':plan['id'],'video_sha256':candidate['video_sha256']}),flush=True)
 if metadata is None:
  metadata=render(plan['scene'],plan['duration_seconds'],plan['output'],ROOT/'reports/ui-redesign/benchmark-evidence.json',
                 metrics_mode='capabilities',asset=ROOT/'scripts/video/motion_assets/scene_v4.js',timing_config=plan['timing_path'])
 audio_path=WORK/(plan['id']+'.mp3')
 if sha(audio_path)!=plan['audio_sha256']:
  raise ValueError('Saved audio hash differs from narration manifest: '+plan['id'])
 metadata['narration_binding']={'audio_sha256':plan['audio_sha256'],'alignment_sha256':plan['alignment_sha256'],'text_sha256':plan['text_sha256'],'audio_speed':SPEED,'lead_seconds':LEAD,'tail_seconds':TAIL,'binding_method':'Saved-audio hash verified; phrase config regenerated from saved alignment and checked against original rendered config hash before reuse.'}
 metadata_path.write_text(json.dumps(metadata,indent=2)+'\n')
 ident=plan['id'];folder=WORK/'motion'/('ready-'+ident);folder.mkdir(exist_ok=True)
 actions=[];cue_rows=[]
 for row in plan['cues']:
  ready=folder/(row['id']+'-ready.png')
  subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',f'{row["source_seconds"]:.6f}',
                  '-i',str(plan['output']),'-frames:v','1','-threads','1',str(ready)],check=True)
  actions.append({'action':'visual_ready','cue_id':row['id'],'source_seconds':row['source_seconds'],
                  'bbox':row['box'],'screenshot_path':str(ready.relative_to(ROOT)),
                  'screenshot_sha256':sha(ready),'source_visible_until_seconds':row['source_visible_until_seconds'],
                  'method':'decoded_frame_from_authored_clip'})
  actions.append({'action':'visual_end','cue_id':row['id'],'source_seconds':row['source_visible_until_seconds']})
  cue_rows.append({**row,'visual_event':{'action':'visual_ready','cue_id':row['id']},
                   'visual_end_event':{'action':'visual_end','cue_id':row['id']}})
 capture={**metadata,'id':ident,'title':plan['scene'],'viewport':{'width':1920,'height':1080},'trim_start_seconds':0,'actions':actions}
 sync=build_chapter(ident,capture,plan['alignment'],cue_rows,plan['audio_duration_seconds'],speed=SPEED,lead=LEAD,tail=TAIL,
                    anticipation=ANTICIPATION,fps=FPS,require_visible_holds=True)
 # The illustrations have already been generated on the final narrated clock.
 # Applying a second whole-clip slowdown would destroy exact phrase alignment.
 sync['preserve_source_timing']=True
 for cue in sync['cues']:cue['highlight']=False
 assert all(abs(point['source_seconds']-point['output_seconds'])<1e-6 for point in sync['control_points'])
 return capture,sync

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--go',action='store_true');parser.add_argument('--jobs',type=int,choices=[1,2],default=2);parser.add_argument('--reuse-rendered',action='store_true')
 args=parser.parse_args();os.environ.setdefault('TMPDIR',str(ROOT/'.runtime/showcase-tmp'))
 storyboard_path=WORK/'storyboard.json';story=json.loads(storyboard_path.read_text())
 narration=json.loads((WORK/'narration-manifest.json').read_text());audio={x['chapter']:x for x in narration['chapters']}
 assert len(audio)==14 and all(v['status']=='generated' for v in audio.values()),'All narration must finish first'
 planned_total=sum(frame_ceil(audio[c['id']]['duration_seconds']+LEAD+TAIL) for c in story)
 assert 360<=planned_total<=420,(planned_total,'outside 6–7 minutes')
 plans=[prepare(c['id'],c,audio[c['id']]) for c in story if c['id'] in SPECS]
 summary={'storyboard_sha256':sha(storyboard_path),'audio_speed':SPEED,'lead_seconds':LEAD,'tail_seconds':TAIL,
          'fps':FPS,'planned_video_duration_seconds':planned_total,'chapters':[{'id':p['id'],'scene':p['scene'],
          'duration_seconds':p['duration_seconds'],'timing_config':str(p['timing_path'].relative_to(ROOT))} for p in plans]}
 (WORK/'authored-motion-plan.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
 if not args.go:return
 results=[]
 with ThreadPoolExecutor(max_workers=args.jobs) as pool:
  futures={pool.submit(render_one,p,args.reuse_rendered):p['id'] for p in plans}
  for future in as_completed(futures):
   results.append(future.result());print(json.dumps({'completed':futures[future]}),flush=True)
 result={**summary,'status':'completed','created_at':datetime.now(timezone.utc).isoformat(),
         'captures':sorted((r[0] for r in results),key=lambda r:r['id']),
         'chapters':sorted((r[1] for r in results),key=lambda r:r['id']),
         'preserve_source_timing':True,'all_semantic_anchors_pass':all(r[1]['all_semantic_anchors_pass'] for r in results),
         'scope':'Authored illustrations only; actual decoded ready PNGs retained. Final encoded-frame and semantic review still required.'}
 (WORK/'authored-sync-chapters.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':'completed','path':str((WORK/'authored-sync-chapters.json').relative_to(ROOT))}),flush=True)

if __name__=='__main__':main()
