"""Measure actual pixels for source calibration and encoded UI cue verification.

Uses FFmpeg's decoded presentation timestamps and native SSIM. It performs no
OCR, image synthesis, browser access, application request or provider request.
SSIM verifies the retained reference region, not the semantic truth of its text;
references and boxes still require an independent human visual review.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
FFMPEG = shutil.which('ffmpeg') or 'ffmpeg'
FFPROBE = shutil.which('ffprobe') or 'ffprobe'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def label(path):
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def media_path(value, work, suffixes=None):
    path = Path(value)
    if not path.is_absolute():
        path = next((p for p in [ROOT/path, work/path] if p.is_file()), work/path)
    path = path.resolve()
    if not path.is_file() or suffixes and path.suffix.lower() not in suffixes:
        raise ValueError('Expected local media file is missing or has an unsupported type: '+label(path))
    return path


def probe(path):
    result = subprocess.run([FFPROBE, '-v', 'error', '-show_format', '-show_streams',
        '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('FFprobe could not decode local media: '+label(path))
    value = json.loads(result.stdout)
    stream = next((s for s in value['streams'] if s['codec_type']=='video'), None)
    if not stream:
        raise ValueError('A video/image stream is required: '+label(path))
    return value, stream


def number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name+' must be a finite number')
    return float(value)


def pixel_box(box, width, height, inset=0):
    values = {key:number(box[key], 'box '+key) for key in ['x','y','width','height']}
    if values['width']<=0 or values['height']<=0 or values['x']<0 or values['y']<0 or \
            values['x']+values['width']>width+.5 or values['y']+values['height']>height+.5:
        raise ValueError('Measured region must be inside its actual viewport')
    left, top = math.ceil(values['x']+inset), math.ceil(values['y']+inset)
    right = math.floor(min(width, values['x']+values['width'])-inset)
    bottom = math.floor(min(height, values['y']+values['height'])-inset)
    if right-left<8 or bottom-top<8:
        raise ValueError('Region is too small after the required overlay inset; choose a larger measured UI region')
    return {'x':left,'y':top,'width':right-left,'height':bottom-top}


def crop(box):
    return 'crop={width}:{height}:{x}:{y}'.format(**box)


def filter_file(path):
    return "'"+str(path).replace('\\','\\\\').replace(':','\\:').replace("'", "'\\''")+"'"


def execute(args, log):
    result = subprocess.run(args, capture_output=True, text=True, timeout=150)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stderr)
    if result.returncode:
        raise ValueError('FFmpeg comparison failed; inspect '+label(log))
    return result.stderr


def pts_rows(stderr):
    return [float(match[1]) for match in re.finditer(r'\bn:\s*\d+\s+pts:.*?\bpts_time:([-+\deE.]+)', stderr)]


def ssim_rows(path):
    return [{'index':int(match[1]),'ssim':float(match[2])}
        for match in re.finditer(r'\bn:(\d+)\s+.*?\bAll:([-+\deE.]+)', path.read_text())]


def slug(value):
    return re.sub(r'[^A-Za-z0-9_-]', '_', str(value))[:65]+'-'+hashlib.sha256(str(value).encode()).hexdigest()[:7]


def extract_frame(source, seconds, output):
    """Extract the first decoded frame at/after a requested source timestamp."""
    seconds = max(0, number(seconds, 'frame time'))
    output.parent.mkdir(parents=True, exist_ok=True)
    stderr = execute([FFMPEG,'-hide_banner','-nostdin','-nostats','-y','-copyts',
        '-ss',f'{max(0,seconds-.08):.9f}','-i',str(source),'-vf',
        f"select='gte(t,{seconds:.9f})',showinfo",'-frames:v','1','-fps_mode','passthrough',
        '-threads','2',str(output)], output.with_suffix('.extract.log'))
    times = pts_rows(stderr)
    if not times or not output.is_file():
        raise ValueError('No decoded frame exists at the requested timestamp')
    return times[0]


def scan_source(source, reference, box, start, end, folder):
    """Compare every actual decoded source frame in a bounded PTS interval."""
    stats, log = folder/'source.ssim', folder/'source-ffmpeg.log'
    folder.mkdir(parents=True, exist_ok=True)
    graph = (f"[0:v]select='between(t,{start:.9f},{end:.9f})',format=yuv444p,{crop(box)},showinfo[src];"
             f"[1:v]format=yuv444p,{crop(box)}[ref];"
             f"[src][ref]ssim=stats_file={filter_file(stats)}:shortest=0:repeatlast=1[out]")
    stderr = execute([FFMPEG,'-hide_banner','-nostdin','-nostats','-copyts',
        '-ss',f'{max(0,start-.08):.9f}','-i',str(source),'-i',str(reference),
        '-filter_complex_threads','1','-filter_complex',graph,'-map','[out]',
        '-an','-fps_mode','passthrough','-threads','2','-f','null','-'], log)
    times, scores = pts_rows(stderr), ssim_rows(stats)
    if not times or len(times)!=len(scores) or any(row['index']!=i+1 for i,row in enumerate(scores)):
        raise ValueError('Decoded source timestamps do not reconcile to native per-frame SSIM measurements')
    return [{'source_seconds':time, 'ssim':row['ssim']} for time,row in zip(times,scores)]


def reference_variation(reference, box, folder):
    """Reject an empty/flat crop that could trivially match unrelated screens."""
    stderr=execute([FFMPEG,'-hide_banner','-nostdin','-nostats','-i',str(reference),
        '-vf','format=gray,'+crop(box)+',showinfo','-frames:v','1','-an',
        '-threads','2','-f','null','-'],folder/'reference-variation.log')
    found=re.search(r'\bstdev:\[([-+\deE.]+)\]',stderr)
    if not found:raise ValueError('Could not measure reference ROI luma variation')
    deviation=float(found[1])
    if not math.isfinite(deviation) or deviation<2:
        raise ValueError('Reference ROI is nearly flat; choose a meaningful visible UI landmark instead of background pixels')
    return deviation


def geometry(viewport):
    return ('scale=-2:880,pad=1920:1080:1210:78:color=0x133334'
            if viewport['height']>viewport['width'] else
            'scale=1920:912,pad=1920:1080:0:60:color=0x133334')


def compare_encoded_frame(frame, reference, viewport, box, folder):
    """Resize the reference with the renderer's actual geometry before ROI SSIM."""
    stats, log = folder/'encoded.ssim', folder/'encoded-ffmpeg.log'
    graph = (f"[0:v]format=yuv444p,{crop(box)}[actual];"
             f"[1:v]{geometry(viewport)},format=yuv444p,{crop(box)}[reference];"
             f"[actual][reference]ssim=stats_file={filter_file(stats)}[out]")
    execute([FFMPEG,'-hide_banner','-nostdin','-nostats','-i',str(frame),'-i',str(reference),
        '-filter_complex_threads','1','-filter_complex',graph,'-map','[out]',
        '-frames:v','1','-an','-threads','2','-f','null','-'], log)
    rows = ssim_rows(stats)
    if len(rows)!=1:
        raise ValueError('Encoded frame comparison did not produce exactly one SSIM measurement')
    return rows[0]['ssim']


def event_clock(event, offset=0):
    value = event.get('capture_clock_seconds', event.get('approx_source_seconds', event.get('seconds', event.get('source_seconds'))))
    return number(value, 'capture clock')+offset


def calibrate(work, window=.8, threshold=.90, near_best=.003, chapters=None):
    work = work.resolve();manifest_path=work/'captures/manifest.json'
    if manifest_path.resolve().is_relative_to(ROOT/'runtime/video-v3'):
        raise ValueError('Historical v3 captures are immutable; copy a fixture into the new work directory')
    raw = json.loads(manifest_path.read_text())
    if any(c.get('status')=='recording' for c in raw['scenes']):
        raise ValueError('The UI recorder is still writing; finish capture before calibration')
    original_bytes = manifest_path.read_bytes()
    folder = work/'visual-calibration';folder.mkdir(parents=True,exist_ok=True)
    original_path=folder/('manifest-before-'+hashlib.sha256(original_bytes).hexdigest()[:16]+'.json')
    if not original_path.exists():original_path.write_bytes(original_bytes)
    # Work on a copy and publish atomically only when every selected cue passes.
    updated=json.loads(original_bytes);proofs=[];failures=[];skipped=[]
    for capture in updated['scenes']:
        ident=capture['id']
        if capture.get('media_type')=='authored_motion_graphics' or chapters and ident not in chapters:
            skipped.append(ident);continue
        if capture.get('status')!='completed' or capture.get('errors'):
            failures.append({'chapter':ident,'error':'Capture is not complete and clean'});continue
        try:
            source=media_path(capture['video_path'],work,{'.webm','.mp4','.mkv'})
            info,stream=probe(source);duration=float(info['format']['duration']);video_hash=sha(source)
            ready=[e for e in capture.get('actions',[]) if e.get('action')=='visual_ready']
            if not ready:raise ValueError('Actual UI chapter has no visual_ready evidence')
            if len({e.get('cue_id') for e in ready})!=len(ready):raise ValueError('Ready cue IDs must be unique')
            offset=number(capture.get('event_clock_offset_before_visual_calibration_seconds',capture.get('event_clock_offset_seconds',0)),'event clock offset')
            calibrated=[]
            for event in ready:
                cue=event['cue_id'];cue_folder=folder/(slug(ident)+'-'+slug(cue))
                cue_folder.mkdir(exist_ok=True)
                reference=media_path(event['screenshot_path'],work,{'.png','.jpg','.jpeg'})
                _,image=probe(reference)
                if (stream['width'],stream['height'])!=(image['width'],image['height']):
                    raise ValueError('Ready reference dimensions must match the raw recording viewport')
                box=pixel_box(event.get('bbox') or event.get('box'),stream['width'],stream['height'])
                variation=reference_variation(reference,box,cue_folder)
                original_ready_clock=event_clock(event)
                clock_prediction=original_ready_clock+offset
                # A manually reviewed landmark/full-clip scan may narrow the
                # next bounded search. It is a search hint, never a measured
                # timestamp or a replacement for the original capture clock.
                approx=number(event.get('source_search_hint_seconds',clock_prediction),'source search hint')
                event.setdefault('capture_clock_seconds',original_ready_clock)
                if not 0<=approx<=duration+window:raise ValueError('Ready capture clock lies outside the bounded source search')
                samples=scan_source(source,reference,box,max(0,approx-window),min(duration-1e-6,approx+window),cue_folder)
                peak=max(s['ssim'] for s in samples)
                candidates=[s for s in samples if s['ssim']>=max(threshold,peak-near_best)]
                if not candidates:raise ValueError(f'Ready reference does not match raw video (bestSSIM={peak:.6f})')
                chosen=min(candidates,key=lambda row:row['source_seconds']);actual=chosen['source_seconds']
                ends=[e for e in capture['actions'] if e.get('action')=='visual_end' and e.get('cue_id')==cue]
                if len(ends)!=1:raise ValueError('Each ready cue requires exactly one paired visual_end')
                end=ends[0];original_end_clock=event_clock(end)
                end_source=actual+(original_end_clock-original_ready_clock)
                end.setdefault('capture_clock_seconds',original_end_clock)
                if not actual<end_source<=duration+1e-6:raise ValueError('Calibrated visibility end is outside the source or precedes readiness')
                frame=cue_folder/'chosen-source-frame.png';decoded=extract_frame(source,actual,frame)
                if abs(decoded-actual)>.001:raise ValueError('Chosen decoded PTS was not reproducible')
                item={'chapter':ident,'cue_id':cue,'passed':True,'source_video':label(source),'source_video_sha256':video_hash,
                    'screenshot_path':label(reference),'screenshot_sha256':sha(reference),'bbox':box,
                    'approx_source_seconds':approx,'source_seconds':actual,'clock_adjustment_seconds':actual-clock_prediction,
                    'original_ready_capture_clock_seconds':original_ready_clock,
                    'original_end_capture_clock_seconds':original_end_clock,
                    'recorded_visibility_duration_seconds':original_end_clock-original_ready_clock,
                    'capture_clock_prediction_seconds':clock_prediction,
                    'per_event_search_hint_used':'source_search_hint_seconds' in event,
                    'search_hint_adjustment_seconds':actual-approx,
                    'source_visible_until_seconds':end_source,'threshold':threshold,'best_ssim':peak,
                    'reference_luma_stddev':variation,
                    'chosen_ssim':chosen['ssim'],'near_best_tolerance':near_best,'decoded_source_frame':label(frame),
                    'frame_sha256':sha(frame),'samples':samples,'stats_file':label(cue_folder/'source.ssim')}
                event['source_seconds']=actual;event['source_calibration']={k:item[k] for k in [
                    'source_video_sha256','screenshot_sha256','source_seconds','chosen_ssim','threshold']}
                end['source_seconds']=end_source
                end['source_calibration']={'paired_ready_cue_id':cue,
                    'clock_adjustment_seconds':actual-clock_prediction,
                    'recorded_visibility_duration_seconds':original_end_clock-original_ready_clock}
                calibrated.append(actual);proofs.append(item)
            if any(a>=b for a,b in zip(calibrated,calibrated[1:])):
                raise ValueError('Calibrated ready timestamps must increase strictly; recapture ambiguous or repeated states')
            capture.setdefault('trim_before_visual_calibration_seconds',capture.get('trim_start_seconds',0))
            capture['trim_start_seconds']=calibrated[0]
            capture['event_clock_offset_before_visual_calibration_seconds']=offset
            capture['event_clock_offset_seconds']=0
        except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as exc:
            failures.append({'chapter':ident,'error':str(exc)})
    report={'status':'passed' if proofs and not failures else 'review_required','checked_at':datetime.now(timezone.utc).isoformat(),
        'method':'Native FFmpeg per-frame SSIM matched to retained ready PNGs, using actual decoded showinfo PTS',
        'source_manifest_before':label(original_path),'source_manifest_before_sha256':hashlib.sha256(original_bytes).hexdigest(),
        'checked_cues':len(proofs),'cues':proofs,'failures':failures,'skipped_chapters':skipped,
        'manifest_updated':False,'threshold':threshold,'window_seconds':window,
        'provider_requests':0,'application_state_changes':0,
        'limits':['SSIM matches retained pixels; independent review must establish that the screenshot and measured ROI represent the claimed UI state.',
                  'Visibility-end clock receives the same per-cue offset as its matched ready state; final encoded hold pixels are independently checked.']}
    if report['status']=='passed':
        updated['visual_calibration']={'status':'passed','report':label(folder/'calibration.json'),
            'original_manifest':label(original_path),'method':'decoded_source_pts_native_ssim'}
        temporary=manifest_path.with_suffix('.calibrated.tmp');temporary.write_text(json.dumps(updated,indent=2,allow_nan=False)+'\n')
        temporary.replace(manifest_path);report['manifest_updated']=True;report['source_manifest_after_sha256']=sha(manifest_path)
    (folder/'calibration.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def verify(work, output, threshold=.92, inset=8):
    work,output=work.resolve(),output.resolve()
    manifest=json.loads((output/'manifest.json').read_text());plan=json.loads((work/'sync-plan.json').read_text())
    captures={c['id']:c for c in json.loads((work/'captures/manifest.json').read_text())['scenes']}
    timeline={c['id']:c for c in manifest['chapters']};video=media_path(manifest['video'],output,{'.mp4'})
    video_hash=sha(video);_,stream=probe(video)
    if (stream['width'],stream['height'])!=(1920,1080):raise ValueError('Expected final1920x1080 video geometry')
    frame_folder=output/'visual-sync-frames';frame_folder.mkdir(parents=True,exist_ok=True)
    expected=0;checked=[];authored=[];failures=[]
    for chapter in plan['chapters']:
        ident=chapter['id'];capture=captures[ident]
        if capture.get('media_type')=='authored_motion_graphics':
            authored.extend({'chapter':ident,'cue_id':c['id'],'status':'separate_authored_visual_review'} for c in chapter['cues']);continue
        for cue in chapter['cues']:
            expected+=1;row={'chapter':ident,'cue_id':cue['id'],'passed':False,'samples':[]}
            try:
                event=cue['source_evidence']['event']
                reference=media_path(event['screenshot_path'],work,{'.png','.jpg','.jpeg'})
                calibration=event.get('source_calibration',{})
                reference_hash=sha(reference)
                if calibration.get('screenshot_sha256')!=reference_hash:
                    raise ValueError('Cue reference is not linked to the calibrated source screenshot hash')
                source=media_path(capture['video_path'],work,{'.webm','.mp4','.mkv'})
                if calibration.get('source_video_sha256')!=sha(source):
                    raise ValueError('Cue calibration does not match the current source video')
                box=pixel_box(cue['projected_box'],1920,1080,inset)
                start=number(timeline[ident]['start_seconds'],'chapter start')
                mention_start=number(cue['mention_start_seconds'],'mention start')
                mention_end=number(cue['mention_end_seconds'],'mention end')
                before=max(0,mention_start-.08)
                probes=[('before_mention',before),('spoken_phrase_end',max(0,mention_end-.05))]
                row.update(reference=label(reference),reference_sha256=reference_hash,projected_roi=box,
                    border_inset_pixels=inset,threshold=threshold,source_seconds=cue['source_seconds'])
                for name,local_time in probes:
                    folder=frame_folder/(slug(ident)+'-'+slug(cue['id'])+'-'+name);folder.mkdir(exist_ok=True)
                    frame=folder/'encoded-frame.png';requested=start+local_time
                    pts=extract_frame(video,requested,frame)
                    if abs(pts-requested)>.061:
                        raise ValueError('Encoded sample timestamp is not close to the requested cue frame')
                    score=compare_encoded_frame(frame,reference,capture['viewport'],box,folder)
                    time_ok=(pts<start+mention_start if name=='before_mention' else pts<=start+mention_end+.001)
                    row['samples'].append({'name':name,'requested_global_seconds':requested,
                        'decoded_global_pts_seconds':pts,'ssim':score,'threshold':threshold,
                        'timing_within_spoken_boundary':time_ok,'passed':bool(score>=threshold and time_ok),
                        'frame':label(frame),'frame_sha256':sha(frame),'stats_file':label(folder/'encoded.ssim')})
                row['passed']=all(s['passed'] for s in row['samples'])
                if not row['passed']:failures.append({'chapter':ident,'cue_id':cue['id'],'error':'Encoded pixels or spoken-boundary timing do not match the retained state'})
            except (KeyError,ValueError,TypeError,OSError,subprocess.SubprocessError) as exc:
                row['error']=str(exc);failures.append({'chapter':ident,'cue_id':cue['id'],'error':str(exc)})
            checked.append(row)
    passed=bool(expected and len(checked)==expected and all(c['passed'] for c in checked) and not failures)
    report={'status':'passed' if passed else 'review_required','checked_at':datetime.now(timezone.utc).isoformat(),
        'method':'Native FFmpeg SSIM of actual final encoded UI pixels against calibrated retained state references',
        'video':label(video),'video_sha256':video_hash,'checked_cues':len(checked),'expected_cues':expected,
        'expected_ui_cues':expected,'total_sync_cues':sum(len(c['cues']) for c in plan['chapters']),
        'all_cues_passed':passed,'cues':checked,'failures':failures,
        'authored_cues_excluded':authored,'authored_cue_count':len(authored),
        'authored_review':'Requires separate authored-stage/visual review; no UI pixel result is invented for illustrations.',
        'threshold':threshold,'border_inset_pixels':inset,'provider_requests':0,'application_state_changes':0,
        'source_manifest_sha256':sha(work/'captures/manifest.json'),'sync_plan_sha256':sha(work/'sync-plan.json'),
        'limits':['Two actual encoded frames are checked per UI cue: before its spoken mention and near the end of its explanation.',
                  'SSIM does not recognize text meaning or prove clinical correctness. Retained references/ROIs need independent visual review.',
                  'Highlight borders are excluded by an8px inset; captions and labels must remain outside these measured regions.']}
    (output/'visual-sync-verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--calibrate',action='store_true');mode.add_argument('--verify',action='store_true')
    parser.add_argument('--work-dir',type=Path,required=True);parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--window',type=float,default=.8);parser.add_argument('--threshold',type=float)
    parser.add_argument('--near-best',type=float,default=.003);parser.add_argument('--inset',type=int,default=8)
    parser.add_argument('--chapters',nargs='+',help='Calibrate selected chapters only; final verification always checks all UI cues')
    args=parser.parse_args()
    if not 0<args.window<=2 or not 0<=args.near_best<=.02 or not 0<=args.inset<=24:
        parser.error('Window, near-best tolerance or inset is outside its bounded range')
    threshold=args.threshold if args.threshold is not None else .90 if args.calibrate else .92
    if not .85<=threshold<=1:parser.error('SSIM threshold must be between.85and1')
    if args.verify and (not args.output_dir or args.chapters):parser.error('Verification requires --output-dir and checks every UI cue')
    result=calibrate(args.work_dir,args.window,threshold,args.near_best,set(args.chapters) if args.chapters else None) if args.calibrate else verify(args.work_dir,args.output_dir,threshold,args.inset)
    print(json.dumps({'status':result['status'],'checked_cues':result['checked_cues'],
        'failures':result['failures'],'report':label(args.work_dir/'visual-calibration/calibration.json') if args.calibrate else label(args.output_dir/'visual-sync-verification.json')}),flush=True)
    if result['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
