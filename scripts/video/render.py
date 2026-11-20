"""Assemble actual UI captures with timed narration, captions and MP4 chapters."""
import argparse
import hashlib
import html
import json
import math
import re
import subprocess
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'runtime/video'
OUT = ROOT / 'reports/video'
STEM = 'Suhail_Health_UI_Walkthrough'
LEAD = .85
TAIL = 1.15
CHAPTER_COUNT = 19


def run(args, log):
    with log.open('w') as file:
        subprocess.run(args, stdout=file, stderr=subprocess.STDOUT, check=True)


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))


def clock(seconds, kind='ass'):
    if kind == 'ass':
        c = round(seconds * 100)
        return f'{c//360000}:{c//6000%60:02d}:{c//100%60:02d}.{c%100:02d}'
    m = round(seconds * 1000)
    value = f'{m//3600000:02d}:{m//60000%60:02d}:{m//1000%60:02d}.{m%1000:03d}'
    return value.replace('.', ',') if kind == 'srt' else value


def caption_chunks(path, speed=1.):
    result = json.loads(path.read_text())
    a = result.get('normalized_alignment') or result['alignment']
    chars, starts, ends = a['characters'], a['character_start_times_seconds'], a['character_end_times_seconds']
    text = ''.join(chars)
    words = [{'text': m.group(), 'start': starts[m.start()], 'end': ends[m.end()-1]} for m in re.finditer(r'\S+', text)]
    output, group = [], []
    for word in words:
        if group and (len(' '.join(x['text'] for x in group + [word])) > 83 or word['end'] - group[0]['start'] > 5.5):
            output.append({'text': ' '.join(x['text'] for x in group), 'start': group[0]['start'] / speed + LEAD, 'end': group[-1]['end'] / speed + LEAD})
            group = []
        group.append(word)
        if word['text'].endswith(('.', '!', '?', ';')) and len(' '.join(x['text'] for x in group)) > 30:
            output.append({'text': ' '.join(x['text'] for x in group), 'start': group[0]['start'] / speed + LEAD, 'end': group[-1]['end'] / speed + LEAD})
            group = []
    if group:
        output.append({'text': ' '.join(x['text'] for x in group), 'start': group[0]['start'] / speed + LEAD, 'end': group[-1]['end'] / speed + LEAD})
    return output


def ass_escape(text):
    return text.replace('\\', '\\u005c').replace('{', '(').replace('}', ')')


def caption_lines(text):
    if len(text) <= 70:
        return [text]
    words = text.split()
    cut = min(range(1, len(words)), key=lambda i: abs(len(' '.join(words[:i])) - len(' '.join(words[i:]))))
    return [' '.join(words[:cut]), ' '.join(words[cut:])]


def write_ass(scene, captions, duration, mobile, visual_cues=None):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Header,DejaVu Sans,25,&H00FFFFFF,&H000000FF,&H00133334,&H00133334,-1,0,0,0,100,100,0,0,1,0,0,7,36,36,17,1
Style: Tag,DejaVu Sans,18,&H00BCE0E1,&H000000FF,&H00133334,&H00133334,0,0,0,0,100,100,0,0,1,0,0,9,36,36,21,1
Style: Caption,DejaVu Sans,30,&H00FFFFFF,&H000000FF,&H00133334,&H00133334,0,0,0,0,100,100,0,0,1,0,0,2,150,150,17,1
Style: MobileTitle,DejaVu Sans,58,&H00FFFFFF,&H000000FF,&H00133334,&H00133334,-1,0,0,0,100,100,0,0,1,0,0,7,120,700,210,1
Style: MobileNotes,DejaVu Sans,31,&H00C7E4E4,&H000000FF,&H00133334,&H00133334,0,0,0,0,100,100,0,0,1,0,0,7,120,750,415,1
Style: FocusLabel,DejaVu Sans,20,&H00FFFFFF,&H000000FF,&H00143334,&H00143334,-1,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    end = clock(duration)
    title = f'SUHAIL HEALTH   /   {scene["id"]}  {scene["title"]}'
    label = scene.get('media_label', 'SYNTHETIC UI TOUR')
    rows = [f'Dialogue: 0,0:00:00.00,{end},Header,,0,0,0,,{ass_escape(title)}', f'Dialogue: 0,0:00:00.00,{end},Tag,,0,0,0,,{ass_escape(label)}  |  {scene["id"]} / {CHAPTER_COUNT}']
    if mobile:
        mobile_title=ass_escape(scene.get('visual_heading','Care on any screen'))
        mobile_notes=scene.get('visual_notes',['English + Arabic RTL','','Your next step and care team','Questions and human replies','Practical support and preferences','Optional recorded feedback'])
        notes='\\N'.join(ass_escape(value) for value in mobile_notes)
        rows += [f'Dialogue: 0,0:00:00.00,{end},MobileTitle,,0,0,0,,{mobile_title}', f'Dialogue: 0,0:00:00.00,{end},MobileNotes,,0,0,0,,{notes}']
    for c in captions:
        lines = '\\N'.join(caption_lines(c['text']))
        rows.append(f'Dialogue: 1,{clock(c["start"])},{clock(c["end"])},Caption,,0,0,0,,{ass_escape(lines).replace(chr(92)+"u005cN", chr(92)+"N")}')
    for cue in visual_cues or []:
        box = cue.get('projected_box')
        if not box or cue.get('highlight', True) is False:
            continue
        x = max(5., box['x']-6); y = max(65., box['y']-6)
        right = min(1915., box['x']+box['width']+6); bottom = min(965., box['y']+box['height']+6)
        if right <= x or bottom <= y:
            continue
        start, stop = clock(cue['highlight_start_seconds']), clock(cue['highlight_end_seconds'])
        # An authored outline emphasizes actual recorded pixels; it adds no UI state.
        outline = f'{{\\an7\\pos(0,0)\\p1\\bord3\\shad0\\1a&HFF&\\3a&H00&\\3c&H5BA2C9&\\fad(120,160)}}m {x:.1f} {y:.1f} l {right:.1f} {y:.1f} {right:.1f} {bottom:.1f} {x:.1f} {bottom:.1f} {x:.1f} {y:.1f}'
        rows.append(f'Dialogue: 2,{start},{stop},FocusLabel,,0,0,0,,{outline}')
        label = cue.get('label')
        if label:
            label_x = min(x+8, 1600); label_y = max(68, y-31)
            rows.append(f'Dialogue: 3,{start},{stop},FocusLabel,,0,0,0,,{{\\pos({label_x:.1f},{label_y:.1f})\\fad(120,160)}}{ass_escape(label)}')
    path = WORK / (scene['id'] + '.ass')
    path.write_text(header + '\n'.join(rows) + '\n')
    return path


def main():
    global WORK, OUT, STEM, LEAD, TAIL, CHAPTER_COUNT
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-dir', type=Path, default=WORK)
    parser.add_argument('--output-dir', type=Path, default=OUT)
    parser.add_argument('--stem', default=STEM)
    parser.add_argument('--title', default='Suhail Health complete UI walkthrough')
    parser.add_argument('--crf', type=int, default=20)
    parser.add_argument('--preset', default='veryfast', choices=['veryfast','faster','fast','medium'])
    parser.add_argument('--audio-speed', type=float, default=1.)
    parser.add_argument('--lead', type=float, default=LEAD)
    parser.add_argument('--tail', type=float, default=TAIL)
    parser.add_argument('--only', help='Render just one preview chapter')
    parser.add_argument('--wait-for-captures', action='store_true')
    args = parser.parse_args()
    WORK=args.work_dir.resolve();OUT=args.output_dir.resolve();STEM=args.stem;LEAD=args.lead;TAIL=args.tail
    if not 16<=args.crf<=28 or not .85<=args.audio_speed<=1.2 or not 0<=LEAD<=2 or not 0<=TAIL<=3:
        raise SystemExit('Media settings outside bounded quality/timing limits.')
    scenes = json.loads((WORK / 'storyboard.json').read_text())
    production_path = WORK / 'production-notes.json'
    production = json.loads(production_path.read_text()) if production_path.is_file() else {}
    sync_path = WORK / 'sync-plan.json'
    sync = json.loads(sync_path.read_text()) if sync_path.is_file() else None
    sync_chapters = {chapter['id']: chapter for chapter in sync['chapters']} if sync else {}
    if production.get('require_semantic_sync') and (not sync or not sync.get('all_semantic_anchors_pass') or set(sync_chapters) != {s['id'] for s in scenes}):
        raise SystemExit('This production requires a complete, validated phrase-to-state sync plan; uniform chapter stretching is disabled.')
    CHAPTER_COUNT=len(scenes)
    assembled, all_caps, timeline = [], [], []
    cursor = 0.
    for scene in scenes:
        ident = scene['id']
        if args.only and ident != args.only:
            continue
        deadline = time.monotonic() + 1200
        while True:
            try:
                raw = json.loads((WORK / 'captures/manifest.json').read_text())
                captures = {x['id']: x for x in (raw['scenes'] if isinstance(raw, dict) else raw)}
                cap = captures[ident]
                if cap.get('status') != 'completed' or cap.get('errors') or not cap.get('video_path'):
                    raise KeyError('Capture is not complete and clean yet: ' + ident)
                break
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                if not args.wait_for_captures or time.monotonic() > deadline:
                    raise
                time.sleep(3)
        source = Path(cap['video_path'])
        if not source.is_absolute():
            source = ROOT / source
        audio = WORK / (ident + '.mp3')
        video_info, audio_info = probe(source), probe(audio)
        raw_duration = float(video_info['format']['duration'])
        audio_duration = float(audio_info['format']['duration']) / args.audio_speed
        total = math.ceil((audio_duration + LEAD + TAIL) * 25 - 1e-7) / 25
        trim = min(float(cap.get('trim_start_seconds', 0)), max(0., raw_duration - 2))
        slowdown = max(.25, (total - .15) / (raw_duration - trim))
        stream = next(s for s in video_info['streams'] if s['codec_type'] == 'video')
        mobile = stream['height'] > stream['width']
        captions = caption_chunks(WORK / (ident + '-alignment.json'), args.audio_speed)
        chapter_sync = sync_chapters.get(ident)
        if chapter_sync and (not chapter_sync['all_semantic_anchors_pass'] or abs(chapter_sync['duration_seconds']-total)>.002):
            raise ValueError('Visual cue plan does not match the final narration timing: '+ident)
        ass = write_ass(scene, captions, total, mobile, chapter_sync.get('cues') if chapter_sync else None)
        if cap.get('media_type') == 'authored_motion_graphics':
            geometry = 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x133334,drawbox=x=0:y=0:w=1920:h=60:color=0x133334:t=fill,drawbox=x=0:y=972:w=1920:h=108:color=0x133334:t=fill'
        elif mobile:
            geometry = 'scale=-2:880,pad=1920:1080:1210:78:color=0x133334'
        else:
            geometry = 'scale=1920:912,pad=1920:1080:0:60:color=0x133334'
        if chapter_sync:
            prefix = f'trim=start=0:end={total},setpts=PTS-STARTPTS,fps=25' if chapter_sync.get('preserve_source_timing') else chapter_sync['video_filter_prefix']
        else:
            prefix = f'trim=start={trim},setpts={slowdown:.9f}*(PTS-STARTPTS),fps=25'
        vf = f'{prefix},{geometry},tpad=stop_mode=clone:stop_duration=2,ass={ass}'
        target = WORK / (ident + '-final.mp4')
        fingerprint = hashlib.sha256((hashlib.sha256(source.read_bytes()).hexdigest() + hashlib.sha256(audio.read_bytes()).hexdigest() + hashlib.sha256(ass.read_bytes()).hexdigest() + vf + str(args.crf) + args.preset + str(args.audio_speed)).encode()).hexdigest()
        fingerprint_path = target.with_suffix('.sha256')
        if not target.exists() or not fingerprint_path.exists() or fingerprint_path.read_text() != fingerprint:
            run(['ffmpeg', '-hide_banner', '-y', '-i', str(source), '-i', str(audio), '-filter_complex', f'[0:v]{vf}[v];[1:a]atempo={args.audio_speed},adelay={round(LEAD*1000)}:all=1,apad[a]', '-map', '[v]', '-map', '[a]', '-t', str(total), '-c:v', 'libx264', '-preset', args.preset, '-crf', str(args.crf), '-pix_fmt', 'yuv420p', '-threads', '6', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(target)], WORK / (ident + '-render.log'))
            fingerprint_path.write_text(fingerprint)
        timeline.append({'id': ident, 'title': scene['title'], 'start_seconds': cursor, 'end_seconds': cursor + total, 'duration_seconds': total, 'capture': str(source.relative_to(ROOT)), 'audio': str(audio.relative_to(ROOT)), 'role': cap.get('role'), 'source_url': cap.get('base_url'), 'media_type': cap.get('media_type', 'actual_application_capture'), 'caption_count': len(captions)})
        all_caps.extend({**c, 'start': c['start'] + cursor, 'end': c['end'] + cursor} for c in captions)
        cursor += total
        assembled.append(target)
        print(json.dumps({'chapter': ident, 'rendered_seconds': total}), flush=True)
    if args.only:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    srt = '\n\n'.join(f'{i+1}\n{clock(c["start"], "srt")} --> {clock(c["end"], "srt")}\n'+ '\n'.join(caption_lines(c['text'])) for i, c in enumerate(all_caps)) + '\n'
    (OUT / (STEM + '.srt')).write_text(srt)
    (OUT / (STEM + '.vtt')).write_text('WEBVTT\n\n' + '\n\n'.join(f'{clock(c["start"], "vtt")} --> {clock(c["end"], "vtt")}\n{c["text"]}' for c in all_caps) + '\n')
    by_id = {scene['id']: scene for scene in scenes}
    transcript = '\n\n'.join(f'{clock(chapter["start_seconds"], "vtt")[:8]}  {chapter["id"]}  {chapter["title"]}\n{by_id[chapter["id"]]["text"]}' for chapter in timeline)
    (OUT / (STEM + '_Transcript.txt')).write_text(args.title+'\n\n'+transcript+'\n')
    concat = WORK / 'concat.txt'
    concat.write_text('\n'.join("file '" + str(p).replace("'", "'\\''") + "'" for p in assembled))
    meta = WORK / 'chapters.ffmeta'
    mixed_media = any(s['media_type'] == 'authored_motion_graphics' for s in timeline)
    comment = 'Authored solution illustrations and actual synthetic application recordings. AI narration by ElevenLabs.' if mixed_media else 'Actual synthetic application recordings. AI narration by ElevenLabs.'
    meta_title = args.title.replace('\n', ' ').replace('=', '-')
    meta.write_text(';FFMETADATA1\ntitle='+meta_title+'\ncomment='+comment+'\n' + '\n'.join(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(s["start_seconds"]*1000)}\nEND={round(s["end_seconds"]*1000)}\ntitle={s["id"]} {s["title"]}' for s in timeline))
    final = OUT / (STEM + '.mp4')
    run(['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat), '-i', str(meta), '-i', str(OUT / (STEM + '.srt')), '-map', '0:v', '-map', '0:a', '-map', '2:0', '-map_metadata', '1', '-map_chapters', '1', '-c', 'copy', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng', '-disposition:s:0', '0', '-movflags', '+faststart', str(final)], WORK / 'assembly.log')
    poster = OUT / (STEM + '_Poster.jpg')
    poster_seconds = float(production.get('poster_seconds', 6))
    run(['ffmpeg', '-hide_banner', '-y', '-ss', str(poster_seconds), '-i', str(final), '-frames:v', '1', '-q:v', '2', str(poster)], WORK / 'poster.log')
    info = probe(final)
    delivery = {'title': args.title, 'generated_at': datetime.now(timezone.utc).isoformat(), 'video': final.name, 'video_sha256': hashlib.sha256(final.read_bytes()).hexdigest(), 'bytes': final.stat().st_size, 'duration_seconds': float(info['format']['duration']), 'width': 1920, 'height': 1080, 'frames_per_second': 25, 'narration': {'provider': 'ElevenLabs', 'model': 'eleven_multilingual_v2', 'voice': 'Rachel', 'language': 'en', 'synthetic_voice': True, 'post_tempo_factor':args.audio_speed}, 'chapters': timeline, 'notes': ['Actual application screen captures, paced for narration.', 'Active isolated synthetic episodes and the existing native completed episode are shown.', 'Recording setup prepared a pending referral in the isolated synthetic database and changed demonstration language preferences; the main case and its clinical disposition were preserved.', 'No new Groq inference or clinical disposition commands were performed for the recording.', 'No public publication or real patient data.']}
    if production:
        delivery['notes'] = production['notes']
        delivery['evidence'] = production.get('evidence', {})
    narration_manifest = json.loads((WORK / 'narration-manifest.json').read_text())
    delivery['narration'].update(model=narration_manifest['model'], voice=narration_manifest['voice'], voice_id=narration_manifest.get('voice_id') or narration_manifest['chapters'][0].get('voice_id'), voice_speed=narration_manifest['chapters'][0].get('voice_speed'))
    if sync:
        delivery['visual_sync'] = {'method': sync['method'], 'cue_count': sync['total_cues'], 'planned_semantic_anchors_pass': sync['all_semantic_anchors_pass'], 'encoded_frame_verification_required': True, 'authored_verification_required': bool(production.get('require_authored_sync')), 'source': str(sync_path.relative_to(ROOT))}
    delivery['timing'] = {'lead_seconds_per_chapter': LEAD, 'tail_seconds_per_chapter': TAIL, 'post_tempo_factor': args.audio_speed, 'pitch_preserved': True}
    (OUT / 'manifest.json').write_text(json.dumps(delivery, indent=2))
    chapter_list = ''.join(f'<li><button onclick="jump({s["start_seconds"]})">{clock(s["start_seconds"], "vtt")[:8]} · {html.escape(s["title"])}</button></li>' for s in timeline)
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suhail Health UI walkthrough</title><style>body{margin:0;background:#f4f8f7;color:#143d3c;font:16px system-ui}main{max-width:1200px;margin:40px auto;padding:24px}h1{font-size:36px}video{width:100%;background:#133334;border-radius:12px}a{color:#006568}ol{columns:2;padding-left:20px}li{padding:7px}button{background:none;border:0;color:#006568;text-align:left;font:inherit;cursor:pointer}p{line-height:1.6}@media(max-width:700px){ol{columns:1}}</style><main><h1>Suhail Health</h1><p>Complete UI walkthrough · English AI narration by ElevenLabs · Actual synthetic application screens</p><video id="tour" controls preload="metadata" poster="'+poster.name+'"><source src="'+final.name+'" type="video/mp4"><track kind="subtitles" srclang="en" label="English" src="'+STEM+'.vtt"></video><p><a download href="'+final.name+'">Download MP4</a> · <a href="'+STEM+'_Transcript.txt">Transcript</a> · <a href="'+STEM+'.srt">Captions</a> · <a href="manifest.json">Recording details</a></p><h2>Chapters</h2><ol>'+chapter_list+'</ol><p>Fictional participants and simulated providers. This tour shows active and completed episode states. No real patient contact, new Groq benchmark run, public deployment or clinical validation is represented.</p></main><script>function jump(t){const v=document.getElementById("tour");v.currentTime=t;v.play()}</script></html>'
    if production:
        page = page.replace('Suhail Health UI walkthrough', html.escape(args.title))
        page = page.replace('Complete UI walkthrough · English AI narration by ElevenLabs · Actual synthetic application screens', html.escape(production.get('player_description', 'Product showcase · English AI narration by ElevenLabs · Illustrations and actual synthetic application screens')))
        page = page.replace('Fictional participants and simulated providers. This tour shows active and completed episode states. No real patient contact, new Groq benchmark run, public deployment or clinical validation is represented.', html.escape(production.get('player_limits', 'Fictional application participants and simulated providers. Illustrations explain the solution; application recordings show actual persisted state. Public-dataset measurements are separately identified. No clinical validation or patient-outcome improvement is established.')))
    (OUT / 'index.html').write_text(page)
    print(json.dumps({'video': str(final), 'seconds': delivery['duration_seconds'], 'bytes': delivery['bytes'], 'chapters': len(timeline)}), flush=True)


if __name__ == '__main__':
    main()
