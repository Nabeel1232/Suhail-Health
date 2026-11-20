"""Generate bounded, resumable ElevenLabs narration without exposing credentials."""
import argparse
import base64
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'runtime/video'
VOICE = '21m00Tcm4TlvDq8ikWAM'
MODEL = 'eleven_multilingual_v2'


def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(path)], text=True))


def main():
    global WORK
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env_elevenlabs')
    parser.add_argument('--max-characters', type=int, default=12500)
    parser.add_argument('--work-dir', type=Path, default=WORK)
    parser.add_argument('--voice-speed', type=float, default=.98)
    parser.add_argument('--model-id', default=MODEL)
    parser.add_argument('--voice-id', default=VOICE)
    parser.add_argument('--voice-name', default='Rachel')
    parser.add_argument('--only', nargs='+', help='Generate selected chapter IDs; other paid audio is preserved. Run without this option to reconcile the complete manifest.')
    args = parser.parse_args()
    WORK=args.work_dir.resolve()
    WORK.mkdir(parents=True,exist_ok=True)
    if not .7 <= args.voice_speed <= 1.2:
        raise SystemExit('Voice speed must be between0.7 and1.2.')
    scenes = json.loads((WORK / 'storyboard.json').read_text())
    native_v4 = args.model_id == 'eleven_v4'
    effective_speed = None if native_v4 else args.voice_speed
    selected_characters = sum(len(s['text']) for s in scenes)
    if selected_characters > args.max_characters:
        raise SystemExit('Narration exceeds the fixed character ceiling; no request sent.')
    selected = set(args.only or [scene['id'] for scene in scenes])
    if selected - {scene['id'] for scene in scenes}:
        raise SystemExit('Unknown narration chapter ID; no request sent.')
    values = dotenv_values(args.env_file)
    key = next((v for k, v in values.items() if v and k.lower() in {'elevenlabs_api', 'elevenlabs_api_key', 'xi_api_key'}), None)
    if not key:
        raise SystemExit('The private ElevenLabs credential entry is unavailable; contents withheld.')
    records = []
    for scene in scenes:
        ident, text = scene['id'], scene['text']
        if ident not in selected:
            continue
        audio, alignment, source = (WORK / (ident + suffix) for suffix in ['.mp3', '-alignment.json', '-text.txt'])
        request_record = WORK / (ident + '-request.json')
        record = {'chapter': ident, 'model': args.model_id, 'voice': args.voice_name, 'voice_id': args.voice_id, 'voice_speed':effective_speed, 'characters': len(text), 'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
        if audio.exists() and alignment.exists() and source.exists():
            if source.read_text() != text:
                raise SystemExit(f'Chapter {ident} has different cached text; preserving previous paid audio.')
            if request_record.exists():
                cached=json.loads(request_record.read_text())
                if cached.get('voice_speed', .98)!=effective_speed or cached.get('model', MODEL)!=args.model_id or cached.get('voice_id', VOICE)!=args.voice_id:
                    raise SystemExit(f'Chapter {ident} has different cached model or voice settings; previous paid audio preserved.')
                record.update(cached)
            elif ident == '01' and (WORK / 'tts-first-call.json').is_file():
                record.update(json.loads((WORK / 'tts-first-call.json').read_text()))
            record['reused_saved_audio'] = True
        else:
            if request_record.exists():
                previous = json.loads(request_record.read_text())
                if previous.get('status') == 'unknown_dispatch_result' or (previous.get('http_status') or 0) >= 400:
                    raise SystemExit(f'Chapter {ident}: an earlier unsuccessful request is preserved; no automatic paid retry.')
            record['requested_at'] = datetime.now(timezone.utc).isoformat()
            voice_settings = {'stability': .5, 'similarity_boost': .75} if native_v4 else {'stability': .55, 'similarity_boost': .75, 'style': .1, 'use_speaker_boost': True, 'speed': args.voice_speed}
            body = {'text': text, 'model_id': args.model_id, 'voice_settings': voice_settings}
            if not native_v4:
                body['seed'] = 215 + int(ident)
            record['voice_settings'] = voice_settings
            record['native_model_settings_only'] = native_v4
            # Persist an uncertain-dispatch fence before a billable network
            # operation; an interrupted process must not silently charge twice.
            record['status'] = 'unknown_dispatch_result'
            request_record.write_text(json.dumps(record, indent=2))
            try:
                with httpx.Client(timeout=httpx.Timeout(180, connect=25)) as client:
                    response = client.post(f'https://api.elevenlabs.io/v1/text-to-speech/{args.voice_id}/with-timestamps', params={'output_format': 'mp3_44100_128'}, headers={'xi-api-key': key}, json=body)
            except httpx.HTTPError as error:
                record.update(status='unknown_dispatch_result', error_type=type(error).__name__)
                request_record.write_text(json.dumps(record, indent=2))
                raise SystemExit(f'Chapter {ident}: network outcome unknown; preserved record, no automatic paid retry.') from None
            record.update(http_status=response.status_code, request_id=response.headers.get('request-id') or response.headers.get('x-request-id'), provider_character_cost_header=response.headers.get('character-cost'))
            if not response.is_success:
                try:
                    detail = response.json().get('detail', {})
                    record['error_code'] = detail.get('status') if isinstance(detail, dict) else 'response_withheld'
                except ValueError:
                    record['error_code'] = 'response_withheld'
                request_record.write_text(json.dumps(record, indent=2))
                raise SystemExit(f'Chapter {ident}: ElevenLabs HTTP {response.status_code}; details sanitized.')
            result = response.json()
            audio.write_bytes(base64.b64decode(result.pop('audio_base64')))
            alignment.write_text(json.dumps(result, ensure_ascii=False))
            source.write_text(text)
            record['reused_saved_audio'] = False
            time.sleep(.3)
        record.update(status='generated', duration_seconds=duration(audio), audio_sha256=hashlib.sha256(audio.read_bytes()).hexdigest())
        request_record.write_text(json.dumps(record, indent=2))
        records.append(record)
        (WORK / 'narration-manifest.json').write_text(json.dumps({'provider': 'ElevenLabs', 'voice': args.voice_name, 'voice_id':args.voice_id, 'model': args.model_id, 'maximum_text_characters': args.max_characters, 'selected_text_characters': selected_characters, 'currency_cost': None, 'chapters': records}, indent=2))
        print(json.dumps({'chapter': ident, 'status': record['status'], 'seconds': round(record['duration_seconds'], 2), 'cached': record['reused_saved_audio']}), flush=True)


if __name__ == '__main__':
    main()
