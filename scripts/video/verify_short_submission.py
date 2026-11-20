"""Read-only delivery checks for the separate three-minute submission.

No provider/application requests or credential reads are made. Defaults are the
new runtime/video-3min and reports/video-3min directories. Historical video
directories cannot be used as writable output. Audio, pixel, browser, editorial
and state proofs must already exist and come from their actual execution.

Preservation input: preservation-before.json and preservation-after.json each
contain an `at` timestamp and sanitized `main_case` object. Before additionally
contains `protected_files: [{path, sha256, bytes?}]`, including both original
benchmark ledgers/logs, the application chat ledger/log, and the v4 movie/QC.
The after object may repeat protected_files; current bytes are always rehashed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
ROLES={'navigator':'/worklist','clinician':'/clinical','specialist':'/clinical',
       'receiver_a':'/receiving','receiver_b':'/receiving','patient':'/patient','admin':'/operations'}
BUDGET_FILES={f'{base}/{name}' for base in [
    'reports/runs/groq-smoke-holdout-v1','reports/runs/public-navigation-healthbench-v3',
    'runtime/context-chat/model-ledger'] for name in ['budget.sqlite3','provider-calls.jsonl']}
HISTORICAL=[ROOT/f'{kind}/{version}' for kind in ['runtime','reports']
            for version in ['video','video-v2','video-v3','video-v4']]


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def label(path):
    try:return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:return str(Path(path).resolve())


def local(value,base=ROOT):
    path=Path(value)
    if not path.is_absolute():
        path=next((p for p in [base/path,ROOT/path] if p.is_file()),base/path)
    path=path.resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError('Required project artifact is missing: '+label(path))
    return path


def read(path):return json.loads(Path(path).read_text())
def passed(value):return isinstance(value,str) and value.startswith('passed')
def normalized(value):return ' '.join(unicodedata.normalize('NFKC',value).replace('’',"'").casefold().split())


def safe_output(work,output):
    work,output=Path(work).resolve(),Path(output).resolve()
    if not work.is_relative_to(ROOT) or not output.is_relative_to(ROOT):
        raise ValueError('The submission work/output directories must be inside the project')
    if any(work.is_relative_to(old) or output.is_relative_to(old) for old in HISTORICAL):
        raise ValueError('Historical video directories are immutable; use the new submission directories')
    if output.is_relative_to(ROOT/'reports/ui-chat-v4'):
        raise ValueError('The historical UI/chat verification is immutable')
    return work,output


def probe(path):
    value=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],
        capture_output=True,text=True,timeout=30)
    if value.returncode:raise ValueError('FFprobe could not read '+label(path))
    return json.loads(value.stdout)


def duration_allowed(seconds):
    return math.isfinite(seconds) and 0<seconds<=180


def changed_protected_files(entries):
    changed=[]
    for item in entries:
        current=local(item['path'])
        if sha(current)!=item['sha256'] or 'bytes' in item and current.stat().st_size!=item['bytes']:
            changed.append(item['path'])
    return changed


def junit(path):
    tree=ET.parse(path).getroot();suites=[tree] if tree.tag=='testsuite' else tree.findall('.//testsuite')
    result={key:sum(int(s.get(key,0)) for s in suites) for key in ['tests','failures','errors','skipped']}
    result['seconds']=sum(float(s.get('time',0)) for s in suites)
    result['all_passed']=bool(result['tests'] and not any(result[k] for k in ['failures','errors','skipped']))
    result['test_names']=[c.get('name','') for c in tree.iter('testcase')]
    return result


def verify(work,output,ui_proof,preservation_after,editorial=None,claims=None):
    work,output=safe_output(work,output)
    checks={};details={};inputs={}
    def load(name,path):
        path=local(path);inputs[name]={'path':label(path),'sha256':sha(path)}
        return read(path)
    def check(name,condition,detail=None):
        checks[name]=bool(condition)
        if detail is not None:details[name]=detail
    manifest=load('delivery_manifest',output/'manifest.json')
    storyboard=load('storyboard',work/'storyboard.json')
    narration=load('narration',work/'narration-manifest.json')
    plan=load('sync_plan',work/'sync-plan.json')
    captures=load('captures',work/'captures/manifest.json')
    technical=load('technical',output/'verification.json')
    ui_pixels=load('ui_pixels',output/'visual-sync-verification.json')
    authored_pixels=load('authored_pixels',output/'authored-sync-verification.json')
    editorial=load('editorial',editorial or output/'final-encoded-editorial-review.json')
    claims=load('claims',claims or work/'final-claims-review.json')
    audio_qc=load('audio_qc',work/'audio-qc.json')
    ui=load('new_ui_source_proof',ui_proof)
    before=load('preservation_before',work/'preservation-before.json')
    after=load('preservation_after',preservation_after)
    movie=local(manifest['video'],output)
    if not movie.is_relative_to(output):raise ValueError('The submission movie must be inside the new output directory')
    movie_hash=sha(movie);media=probe(movie);duration=float(media['format']['duration'])
    ids=[s['id'] for s in storyboard]
    check('new_storyboard_has_nine_unique_chapters',len(ids)==len(set(ids))==9 and
        all(re.fullmatch(r'[A-Za-z0-9_-]+',ident) for ident in ids))
    check('actual_mux_duration_at_most_180_seconds',duration_allowed(duration),
        {'actual_seconds':duration,'hard_maximum_seconds':180})
    check('movie_matches_delivery_hash',movie_hash==manifest['video_sha256'] and
        abs(duration-manifest['duration_seconds'])<=.05)
    check('chapters_match_new_storyboard',ids==[c['id'] for c in manifest['chapters']]==
        [c['chapter'] for c in narration['chapters']]==[c['id'] for c in plan['chapters']])
    word_count=sum(len(re.findall(r"\b\w+(?:['’-]\w+)*\b",s['text'])) for s in storyboard)
    characters=sum(len(s['text']) for s in storyboard)
    check('narration_character_budget_matches',characters==narration['selected_text_characters'] and
        characters<=narration['maximum_text_characters']<=3000,
        {'characters':characters,'maximum_characters':3000,'reported_words':word_count,
         'word_count_is_informational':True})
    prior_voice=read(ROOT/'runtime/video-v4/narration-manifest.json')
    check('same_sarah_elevenlabs_v4_voice',manifest['narration']['provider']=='ElevenLabs' and
        manifest['narration']['voice']==narration['voice']==prior_voice['voice']=='Sarah' and
        manifest['narration']['model']==narration['model']==prior_voice['model']=='eleven_v4' and
        manifest['narration']['voice_id']==narration['voice_id']==prior_voice['voice_id'])
    by_audio={c['chapter']:c for c in narration['chapters']};audio=[]
    for scene in storyboard:
        ident=scene['id'];record=by_audio[ident]
        mp3=local(work/(ident+'.mp3'));text=local(work/(ident+'-text.txt'))
        alignment=local(work/(ident+'-alignment.json'));receipt_path=local(work/(ident+'-request.json'))
        receipt=read(receipt_path);audio_info=probe(mp3);actual_audio=float(audio_info['format']['duration'])
        expected_text=hashlib.sha256(scene['text'].encode()).hexdigest()
        good=(text.read_text()==scene['text'] and sha(text)==expected_text==record['text_sha256']==receipt['text_sha256']
            and sha(mp3)==record['audio_sha256']==receipt['audio_sha256']
            and record['status']==receipt['status']=='generated' and receipt.get('http_status')==200
            and record['model']==receipt['model']=='eleven_v4' and record['voice']==receipt['voice']=='Sarah'
            and record['voice_id']==receipt['voice_id']==narration['voice_id']
            and abs(actual_audio-record['duration_seconds'])<=.04)
        audio.append({'chapter':ident,'passed':good,'actual_audio_seconds':actual_audio,
            'audio':label(mp3),'audio_sha256':sha(mp3),'text_sha256':sha(text),
            'alignment_sha256':sha(alignment),'request_receipt_sha256':sha(receipt_path)})
    check('all_nine_audio_text_alignment_receipts_bound',len(audio)==9 and all(a['passed'] for a in audio),audio)
    transcript=local(output/(movie.stem+'_Transcript.txt'));transcript_text=normalized(transcript.read_text());cursor=0
    transcript_order=True
    for scene in storyboard:
        position=transcript_text.find(normalized(scene['text']),cursor)
        if position<0:transcript_order=False;break
        cursor=position+len(normalized(scene['text']))
    check('new_transcript_covers_spoken_chapters_in_order',bool(transcript_text) and transcript_order,
        {'path':label(transcript),'sha256':sha(transcript)})
    check('technical_checks_pass_for_current_movie',technical['status']=='passed' and
        technical['video_sha256']==movie_hash and bool(technical['checks']) and all(technical['checks'].values()))
    target=audio_qc.get('projected_duration',{}).get('target_seconds',[])
    check('audio_qc_declares_short_duration_target',audio_qc['status']=='passed' and len(target)==2 and
        0<target[0]<=duration<=target[1]<=180)
    cap={c['id']:c for c in captures['scenes']};timeline={c['id']:c for c in manifest['chapters']}
    expected={'ui':set(),'authored':set()};cue_map={}
    for chapter in plan['chapters']:
        ident=chapter['id'];kind='authored' if cap[ident].get('media_type')=='authored_motion_graphics' else 'ui'
        for cue in chapter['cues']:
            key=(ident,cue['id']);expected[kind].add(key);cue_map[key]=cue
    pixel_details={}
    for kind,proof,minimum in [('ui',ui_pixels,.95),('authored',authored_pixels,.92)]:
        actual={(c['chapter'],c['cue_id']) for c in proof['cues']}
        good=(proof['status']=='passed' and proof['video_sha256']==movie_hash and proof['all_cues_passed'] and
            proof['checked_cues']==proof['expected_cues']==len(expected[kind])>0 and actual==expected[kind] and
            proof['threshold']>=minimum and proof['sync_plan_sha256']==inputs['sync_plan']['sha256'] and
            proof['source_manifest_sha256']==inputs['captures']['sha256'])
        bad=[];sample_count=0
        for row in proof['cues']:
            key=(row['chapter'],row['cue_id']);cue=cue_map.get(key);start=timeline[row['chapter']]['start_seconds']
            valid=bool(cue and row.get('passed') and len(row['samples'])==2 and
                {s['name'] for s in row['samples']}=={'before_mention','spoken_phrase_end'})
            for sample in row['samples']:
                sample_count+=1
                frame=local(sample.get('frame') or sample['encoded_frame'])
                frame_hash=sample.get('frame_sha256') or sample['encoded_frame_sha256']
                valid=(valid and frame.is_relative_to(output) and sha(frame)==frame_hash and sample['passed'] and
                    sample['timing_within_spoken_boundary'] and math.isfinite(sample['ssim']) and sample['ssim']>=minimum)
                stats=local(sample['stats_file']);valid=valid and stats.is_relative_to(output) and stats.stat().st_size>0
                if cue:
                    boundary=start+(cue['mention_start_seconds'] if sample['name']=='before_mention' else cue['mention_end_seconds'])
                    pts=sample['decoded_global_pts_seconds']
                    valid=valid and (pts<boundary if sample['name']=='before_mention' else pts<=boundary+.001)
            if not valid:bad.append({'chapter':key[0],'cue_id':key[1]})
            good=good and valid
        check(kind+'_pixels_pass_for_all_actual_new_cues',good,
            {'expected_cues':len(expected[kind]),'checked_cues':proof['checked_cues'],'samples':sample_count,'invalid_cues':bad})
        pixel_details[kind]={'cues':len(expected[kind]),'samples':sample_count}
    review_cues=editorial['cues'];review_keys={(r['chapter'],r.get('cue',r.get('cue_id'))) for r in review_cues}
    review_good=(passed(editorial['status']) and editorial['movie']['sha256']==movie_hash and
        editorial['storyboard_sha256']==inputs['storyboard']['sha256'] and editorial['blocked_cues']==0 and
        editorial['reviewed_cues']==len(review_cues)>0 and editorial['passed_cues']==len(review_cues) and
        review_keys.issubset(set(cue_map)))
    reviewed_frames=0
    for row in review_cues:
        review_good=review_good and bool(row['samples'])
        for sample in row['samples']:
            frame=local(sample['frame']);reviewed_frames+=1
            review_good=review_good and sample['independently_viewed'] is True and sha(frame)==sample['frame_sha256']
    review_good=review_good and editorial['reviewed_frames']==reviewed_frames
    check('independent_editorial_review_passes_current_movie',review_good,
        {'reviewed_cues':len(review_cues),'reviewed_frames':reviewed_frames,'blocked_cues':editorial['blocked_cues']})
    claim_rows=claims['claims'];text_hashes={s['id']:hashlib.sha256(s['text'].encode()).hexdigest() for s in storyboard}
    claim_source_drift=[s['path'] for s in claims['source_evidence']+claims['homepage_role_gate']['sources']
        if sha(local(s['path']))!=s['sha256']]
    check('factual_claims_bound_to_new_narration',passed(claims['status']) and
        claims['storyboard_sha256']==inputs['storyboard']['sha256'] and claims['chapter_count']==claims['claim_count']==len(claim_rows)==9 and
        {c['chapter'] for c in claim_rows}==set(ids) and
        all(c['status']=='supported' and c['text_sha256']==text_hashes[c['chapter']] for c in claim_rows) and
        not claim_source_drift and claims['maturity']=='Prototype' and
        claims['new_benchmark_measurements_claimed'] is False and claims['blanket_accuracy_claimed'] is False and
        claims['real_clinical_deployment_claimed'] is False and claims['frontier_model_accuracy_gain_claimed'] is False,
        {'changed_source_evidence':claim_source_drift})
    ui_browser=ui['browser'];junit_path=local(ui_browser['junit']);result=junit(junit_path)
    browser=load('new_ui_browser_evidence',ui_browser['evidence'])
    inputs['new_ui_junit']={'path':label(junit_path),'sha256':sha(junit_path)}
    source_drift=[p for p,h in ui['source_hashes'].items() if sha(local(p))!=h]
    audience=browser['audience'];demo=browser['demo_roles'];screenshots=audience['screenshots']+demo['screenshots']
    images_good=all(sha(local(s['path']))==s['sha256'] for s in screenshots)
    role_rows=demo['roles'];role_good=(len(role_rows)==7 and {r['role'] for r in role_rows}==set(ROLES) and
        all(r['actual_actor_verified'] is True and r['home']==ROLES[r['role']] for r in role_rows))
    check('fresh_audience_and_seven_demo_roles_browser_checks',result['all_passed'] and passed(ui_browser['status']) and
        ui['typecheck']['status']=='passed' and ui['status']=='passed' and ui['source_unchanged_since_freeze'] is True and
        ui['source_hashes']==ui['source_hashes_after'] and not source_drift and images_good and len(screenshots)>=4 and
        audience['first_screen_visible_desktop_and_mobile'] is True and len(audience['organizations'])>=3 and
        len(audience['workflow_people'])>=6 and role_good and demo['all_seven_visible_in_desktop_frame'] is True and
        demo['native_select_retained_and_actual_switch_passed'] is True and demo['current_role_causes_no_auth_request'] is True and
        demo['mobile_horizontal_overflow'] is False and demo['case_version_before']==demo['case_version_after'] and
        {'Enter','Home','End','ArrowDown','Escape','Focus return'}.issubset(demo['keyboard']),
        {'junit':result,'source_drift':source_drift,'actual_roles_checked':len(role_rows),'screenshots_checked':len(screenshots),
         'scope':'New audience/demo-menu checks only; the prior full21 suite is historical and is not combined.'})
    before_time=datetime.fromisoformat(before['at'].replace('Z','+00:00'));after_time=datetime.fromisoformat(after['at'].replace('Z','+00:00'))
    check('fresh_main_case_unchanged_at_version_30',after_time>=before_time and before['main_case']==after['main_case']==
        {'id':'SC-001','owner':'provider-b','version':30,'disposition':'completed_required_care'})
    protected={p['path']:p for p in before['protected_files']}
    file_drift=changed_protected_files(before['protected_files'])
    check('original_benchmark_and_chat_budgets_unchanged',BUDGET_FILES.issubset(protected) and not file_drift,
        {'required_budget_files':sorted(BUDGET_FILES),'protected_files':len(protected),'changed_files':file_drift})
    v4_qc_path=local(ROOT/'reports/video-v4/delivery-qc.json');v4_qc=read(v4_qc_path)
    v4_drift=[e['path'] for e in v4_qc['evidence'] if sha(local(e['path']))!=e['sha256']]
    check('v4_movie_and_all_pinned_evidence_preserved',v4_qc['status']=='passed' and
        sha(local(v4_qc['video']))==v4_qc['video_sha256'] and not v4_drift and
        {'reports/video-v4/delivery-qc.json','reports/video-v4/manifest.json',v4_qc['video']}.issubset(protected),
        {'movie_sha256':v4_qc['video_sha256'],'pinned_files':len(v4_qc['evidence']),'changed_files':v4_drift})
    prior_app=read(ROOT/'reports/ui-chat-v4/verification.json')
    core={p:h for p,h in prior_app['latest_source_hashes'].items() if
        (p.startswith('services/api/') or p.startswith('services/assistant/')) and p.endswith('.py') or
        p in {'services/agents/gateway.py','services/agents/retrieval.py'}}
    core_drift=[p for p,h in core.items() if sha(local(p))!=h]
    check('clinical_and_chat_backend_matches_verified_v4',bool(core) and not core_drift,{'changed_files':core_drift})
    inputs['v4_delivery_qc']={'path':label(v4_qc_path),'sha256':sha(v4_qc_path)}
    check('movie_did_not_change_during_gate',sha(movie)==movie_hash)
    return {'status':'passed' if all(checks.values()) else 'review_required',
        'checked_at':datetime.now(timezone.utc).isoformat(),'video':label(movie),'video_sha256':movie_hash,
        'duration_seconds':duration,'hard_maximum_seconds':180,'bytes':movie.stat().st_size,
        'chapters':len(ids),'narration_words':word_count,'actual_pixel_coverage':pixel_details,
        'checks':checks,'details':details,'evidence':inputs,'provider_calls':0,'application_requests':0,
        'credential_reads':0,'application_state_changes':0,
        'limits':['The new targeted UI checks and prior21-check workflow baseline retain separate denominators.',
            'Software/pixel/editorial checks do not establish clinical validation, patient-outcome improvement or new model accuracy.',
            'Main-case preservation is verified against actual operator-generated before/after read records; this gate makes no API request.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,default=ROOT/'runtime/video-3min')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'reports/video-3min')
    parser.add_argument('--ui-proof',type=Path,default=ROOT/'runtime/submission-ui/source-proof.json')
    parser.add_argument('--preservation-after',type=Path)
    parser.add_argument('--editorial-proof',type=Path);parser.add_argument('--claims-proof',type=Path)
    args=parser.parse_args()
    try:work,output=safe_output(args.work_dir,args.output_dir)
    except ValueError as exc:parser.error(str(exc))
    try:
        result=verify(work,output,args.ui_proof,args.preservation_after or work/'preservation-after.json',args.editorial_proof,args.claims_proof)
    except (KeyError,ValueError,TypeError,OSError,ET.ParseError,subprocess.SubprocessError) as exc:
        result={'status':'review_required','checked_at':datetime.now(timezone.utc).isoformat(),
            'checks':{'all_required_actual_records_available_and_consistent':False},'error':str(exc),
            'provider_calls':0,'application_requests':0,'credential_reads':0,'application_state_changes':0}
    output.mkdir(parents=True,exist_ok=True);report=output/'delivery-qc.json'
    report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'failed_checks':[k for k,v in result['checks'].items() if not v],
        'error':result.get('error'),'report':label(report)}),flush=True)
    if result['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
