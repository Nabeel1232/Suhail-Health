"""Compare authored source pixels to actual encoded showcase frames.

The authored chapters must preserve their source clock and 1920x1080 canvas.
Two actual decoded frames per cue are compared with native FFmpeg SSIM. This
checks encoding/timing correspondence, not the semantic truth of an illustration.
No browser, application, model, provider or external network request is made.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

try:
    from .visual_sync_check import (ROOT, FFMPEG, crop, execute, extract_frame,
        filter_file, label, media_path, number, pixel_box, probe, sha, slug, ssim_rows)
except ImportError:
    from visual_sync_check import (ROOT, FFMPEG, crop, execute, extract_frame,
        filter_file, label, media_path, number, pixel_box, probe, sha, slug, ssim_rows)


def compare_pair(encoded, source, box, folder):
    stats, log = folder/'authored.ssim', folder/'authored-ffmpeg.log'
    graph = (f'[0:v]format=yuv444p,{crop(box)}[encoded];'
             f'[1:v]format=yuv444p,{crop(box)}[source];'
             f'[encoded][source]ssim=stats_file={filter_file(stats)}[out]')
    execute([FFMPEG,'-hide_banner','-nostdin','-nostats','-i',str(encoded),
        '-i',str(source),'-filter_complex_threads','1','-filter_complex',graph,
        '-map','[out]','-frames:v','1','-an','-threads','2','-f','null','-'],log)
    rows=ssim_rows(stats)
    if len(rows)!=1:
        raise ValueError('An authored frame pair must produce exactly one native SSIM measurement')
    return rows[0]['ssim'],stats


def identity_chapter(chapter):
    if chapter.get('preserve_source_timing') is not True or abs(number(
            chapter['source_trim_seconds'],'source trim'))>1e-8:
        raise ValueError('Authored verification requires an explicit untrimmed identity source clock')
    points=chapter['control_points']
    if len(points)<2 or any(abs(number(p['source_seconds'],'source anchor')-
            number(p['output_seconds'],'output anchor'))>1e-7 for p in points):
        raise ValueError('Authored source/output control points must preserve identity timing')
    if any(b['source_seconds']<=a['source_seconds'] for a,b in zip(points,points[1:])):
        raise ValueError('Authored identity control points must increase strictly')


def verify(work, output, threshold=.92, inset=8, expected_cues=23):
    work,output=Path(work).resolve(),Path(output).resolve()
    manifest_path=output/'manifest.json';plan_path=work/'sync-plan.json'
    captures_path=work/'captures/manifest.json'
    input_hashes={path:sha(path) for path in [manifest_path,plan_path,captures_path]}
    manifest=json.loads(manifest_path.read_text());plan=json.loads(plan_path.read_text())
    captures={c['id']:c for c in json.loads(captures_path.read_text())['scenes']}
    timeline={c['id']:c for c in manifest['chapters']}
    video=media_path(manifest['video'],output,{'.mp4'});video_hash=sha(video)
    _,encoded_stream=probe(video)
    if (encoded_stream['width'],encoded_stream['height'])!=(1920,1080):
        raise ValueError('Expected the actual final 1920x1080 encoded canvas')
    failures=[];checked=[];source_proofs=[];skipped=[]
    if video_hash!=manifest.get('video_sha256'):
        failures.append({'error':'Final movie SHA256 does not match its delivery manifest'})
    frame_root=output/'authored-sync-frames';frame_root.mkdir(parents=True,exist_ok=True)
    actual_cues=0
    for chapter in plan['chapters']:
        ident=chapter['id'];capture=captures.get(ident,{})
        if capture.get('media_type')!='authored_motion_graphics':
            skipped.append(ident);continue
        actual_cues+=len(chapter['cues'])
        try:
            identity_chapter(chapter)
            if capture.get('status')!='completed' or capture.get('errors'):
                raise ValueError('Authored capture is not complete and clean')
            source=media_path(capture['video_path'],work,{'.mp4','.webm','.mkv'})
            source_hash=sha(source);_,source_stream=probe(source)
            if (source_stream['width'],source_stream['height'])!=(1920,1080):
                raise ValueError('Authored source must use the same measured 1920x1080 canvas')
            if capture.get('video_sha256')!=source_hash:
                raise ValueError('Authored source SHA256 does not match the capture manifest')
            entry=timeline[ident]
            if media_path(entry['capture'],work).resolve()!=source.resolve():
                raise ValueError('Delivery timeline points to a different authored source clip')
            start=number(entry['start_seconds'],'chapter start')
            if abs(number(entry['duration_seconds'],'timeline duration')-
                    number(chapter['duration_seconds'],'planned duration'))>.001:
                raise ValueError('Authored chapter duration changed between plan and delivery')
            source_proofs.append({'chapter':ident,'source':label(source),'sha256':source_hash,
                'identity_source_timing':True,'chapter_start_seconds':start})
            chapter_error=None
        except (KeyError,ValueError,TypeError,OSError,subprocess.SubprocessError) as exc:
            chapter_error=str(exc)
        for cue in chapter['cues']:
            row={'chapter':ident,'cue_id':cue['id'],'passed':False,'samples':[]}
            try:
                if chapter_error:raise ValueError(chapter_error)
                box=pixel_box(cue['source_box'],1920,1080,inset)
                projected=pixel_box(cue['projected_box'],1920,1080,inset)
                if box!=projected:
                    raise ValueError('Authored projected region differs from the measured identity source region')
                if box['y']<60 or box['y']+box['height']>972:
                    raise ValueError('Authored ROI intersects the renderer header/caption bands')
                event=cue['source_evidence']['event']
                ready=media_path(event['screenshot_path'],work,{'.png','.jpg','.jpeg'})
                if sha(ready)!=event.get('screenshot_sha256'):
                    raise ValueError('Retained authored ready screenshot changed after cue planning')
                mention_start=number(cue['mention_start_seconds'],'mention start')
                mention_end=number(cue['mention_end_seconds'],'mention end')
                if not 0<mention_start<mention_end<=chapter['duration_seconds']:
                    raise ValueError('Authored spoken interval is outside its actual chapter')
                row.update(source_video=label(source),source_video_sha256=source_hash,
                    ready_screenshot=label(ready),ready_screenshot_sha256=sha(ready),
                    measured_source_roi=box,projected_roi=projected,border_inset_pixels=inset,
                    threshold=threshold,mention_start_seconds=mention_start,mention_end_seconds=mention_end)
                for name,local in [('before_mention',max(0,mention_start-.08)),
                                   ('spoken_phrase_end',max(0,mention_end-.05))]:
                    folder=frame_root/(slug(ident)+'-'+slug(cue['id'])+'-'+name)
                    folder.mkdir(exist_ok=True)
                    encoded=folder/'encoded-frame.png';reference=folder/'actual-source-frame.png'
                    requested=start+local;decoded=extract_frame(video,requested,encoded)
                    source_requested=decoded-start
                    source_decoded=extract_frame(source,source_requested,reference)
                    score,stats=compare_pair(encoded,reference,box,folder)
                    timing_ok=(abs(decoded-requested)<=.061 and
                        0<=source_requested and 0<=source_decoded-source_requested+.000001<=.061 and
                        (decoded<start+mention_start if name=='before_mention' else decoded<=start+mention_end+.001))
                    row['samples'].append({'name':name,'requested_global_seconds':requested,
                        'decoded_global_pts_seconds':decoded,'source_requested_seconds':source_requested,
                        'decoded_source_pts_seconds':source_decoded,'ssim':score,'threshold':threshold,
                        'timing_within_spoken_boundary':timing_ok,'passed':bool(score>=threshold and timing_ok),
                        'encoded_frame':label(encoded),'encoded_frame_sha256':sha(encoded),
                        'source_frame':label(reference),'source_frame_sha256':sha(reference),
                        'stats_file':label(stats)})
                row['passed']=all(s['passed'] for s in row['samples'])
                if not row['passed']:
                    raise ValueError('Actual authored source/encoded pixels or spoken-boundary timing do not match')
            except (KeyError,ValueError,TypeError,OSError,subprocess.SubprocessError) as exc:
                row['error']=str(exc);failures.append({'chapter':ident,'cue_id':cue['id'],'error':str(exc)})
            checked.append(row)
    if actual_cues!=expected_cues:
        failures.append({'error':'Authored cue count differs from the required release count',
            'expected':expected_cues,'actual':actual_cues})
    if sha(video)!=video_hash:
        failures.append({'error':'Final video changed during authored frame verification'})
    for path,expected_hash in input_hashes.items():
        if sha(path)!=expected_hash:
            failures.append({'error':'A source/timeline manifest changed during authored verification','path':label(path)})
    for proof in source_proofs:
        if sha(media_path(proof['source'],work))!=proof['sha256']:
            failures.append({'error':'An authored source video changed during frame verification','chapter':proof['chapter']})
    passed=bool(len(checked)==actual_cues==expected_cues and not failures and all(c['passed'] for c in checked))
    report={'status':'passed' if passed else 'review_required',
        'checked_at':datetime.now(timezone.utc).isoformat(),
        'method':'Actual decoded identity-clock authored source and final encoded frames compared with native FFmpeg SSIM',
        'video':label(video),'video_sha256':video_hash,'checked_cues':len(checked),
        'expected_cues':expected_cues,'actual_authored_cues':actual_cues,'all_cues_passed':passed,
        'cues':checked,'sources':source_proofs,'failures':failures,'ui_chapters_excluded':skipped,
        'threshold':threshold,'border_inset_pixels':inset,
        'source_manifest_sha256':input_hashes[captures_path],'sync_plan_sha256':input_hashes[plan_path],
        'delivery_manifest_sha256':input_hashes[manifest_path],'provider_requests':0,'application_state_changes':0,
        'limits':['Two actual encoded samples per authored cue are compared with raw source frames at decoded final PTS minus chapter start.',
            'This comparison requires an untrimmed identity source clock and the actual same-canvas authored geometry; no synthetic timestamp or visual match is invented.',
            'SSIM establishes pixel correspondence, not semantic recognition, clinical correctness or verification of a narrated outcome claim.']}
    (output/'authored-sync-verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--threshold',type=float,default=.92)
    parser.add_argument('--inset',type=int,default=8)
    args=parser.parse_args()
    if not .85<=args.threshold<=1 or not 0<=args.inset<=24:
        parser.error('SSIM threshold/inset is outside its bounded supported range')
    report=verify(args.work_dir,args.output_dir,args.threshold,args.inset)
    print(json.dumps({'status':report['status'],'checked_cues':report['checked_cues'],
        'expected_cues':report['expected_cues'],'failures':report['failures'],
        'report':label(args.output_dir/'authored-sync-verification.json')}),flush=True)
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
