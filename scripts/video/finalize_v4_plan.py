"""Merge actual UI and authored provenance, then build the strict v4 edit.

Run --register-motion after UI recording, source calibration next, and this
script without flags last. This makes no network or application requests.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

from sync_plan import build_chapter

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'runtime/video-v4'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--register-motion',action='store_true');args=parser.parse_args()
    scenes=read(WORK/'storyboard.json');ids=[s['id'] for s in scenes]
    authored=read(WORK/'authored-sync-chapters.json')
    assert authored['storyboard_sha256']==sha(WORK/'storyboard.json')
    path=WORK/'captures/manifest.json';manifest=read(path)
    if args.register_motion:
        assert not any(c['status']=='recording' for c in manifest['scenes'])
        current={c['id']:c for c in manifest['scenes']}
        titles={s['id']:s['title'] for s in scenes}
        for capture in authored['captures']:
            assert capture['status']=='completed' and not capture['errors']
            assert sha(ROOT/capture['video_path'])==capture['video_sha256']
            current[capture['id']]={**capture,'title':titles[capture['id']]}
        assert set(current)==set(ids)
        manifest['scenes']=[current[ident] for ident in ids];write(path,manifest)
        print(json.dumps({'registered_authored':4,'completed_chapters':len(ids)}));return
    assert manifest.get('visual_calibration',{}).get('status')=='passed'
    captures={c['id']:c for c in manifest['scenes']};cue_path=WORK/'ui-cues.json';cues=read(cue_path)
    audio={c['chapter']:c for c in read(WORK/'narration-manifest.json')['chapters']}
    authored_plans={c['id']:c for c in authored['chapters']};plans=[]
    for ident in ids:
        if ident in authored_plans:
            plan=authored_plans[ident]
            assert plan['preserve_source_timing'] and plan['all_semantic_anchors_pass']
        else:
            alignment_path=WORK/(ident+'-alignment.json');alignment=read(alignment_path)
            alignment=alignment.get('normalized_alignment') or alignment['alignment']
            assert all('source_calibration' in a for a in captures[ident]['actions'] if a['action']=='visual_ready')
            plan=build_chapter(ident,captures[ident],alignment,cues[ident],audio[ident]['duration_seconds'],speed=1.,lead=.6,tail=.8,require_visible_holds=True)
            labels={cue['id']:cue.get('label') for cue in cues[ident]}
            for cue in plan['cues']:
                if labels[cue['id']]:cue['label']=labels[cue['id']]
            plan['sources']={str(p.relative_to(ROOT)):sha(p) for p in [alignment_path,path,cue_path]}
        assert sha(WORK/(ident+'.mp3'))==audio[ident]['audio_sha256']
        plans.append(plan)
    result={'schema_version':'suhail-audio-led-visual-sync-v1','generated_at':datetime.now(timezone.utc).isoformat(),'status':'planned','method':'Exact speech phrases to calibrated recorded UI states and authored final-clock stages, with visible explanation holds','generation_requests':0,'application_state_changes':0,'chapters':plans,'total_cues':sum(len(p['cues']) for p in plans),'all_semantic_anchors_pass':all(p['all_semantic_anchors_pass'] for p in plans),'final_encoded_visual_review_required':True,'storyboard_sha256':sha(WORK/'storyboard.json'),'capture_manifest_sha256':sha(path)}
    write(WORK/'sync-plan.json',result)
    print(json.dumps({'status':'planned','chapters':len(plans),'cues':result['total_cues'],'all_anchors_pass':result['all_semantic_anchors_pass']}))


if __name__=='__main__':main()
