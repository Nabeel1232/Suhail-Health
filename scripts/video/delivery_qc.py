"""Final local delivery gate: executed app evidence plus movie/editorial proof."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/video-v4'
WORK=ROOT/'runtime/video-v4'


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=read(OUT/'manifest.json');movie=OUT/manifest['video'];movie_hash=sha(movie)
    technical=read(OUT/'verification.json');ui=read(OUT/'visual-sync-verification.json')
    authored=read(OUT/'authored-sync-verification.json');editorial=read(OUT/'final-encoded-editorial-review.json')
    ready=read(WORK/'reviews/final-ready-frame-review.json');claims=read(WORK/'final-claims-review.json')
    app=read(ROOT/'reports/ui-chat-v4/verification.json')
    suites=ET.parse(ROOT/'runtime/ui-v4/browser-results.xml').getroot().findall('.//testsuite')
    selected=sum(int(s.get('tests','0')) for s in suites)
    failed=sum(int(s.get(k,'0')) for s in suites for k in ['failures','errors','skipped'])
    checks={
        'movie_and_manifest_hash_match':movie_hash==manifest['video_sha256'],
        'duration_six_to_seven_minutes':360<=manifest['duration_seconds']<=420,
        'fourteen_chapters':len(manifest['chapters'])==14,
        'actual_sarah_elevenlabs_v4_narration':manifest['narration']['voice']=='Sarah' and manifest['narration']['model']=='eleven_v4',
        'technical_checks_passed_current_movie':technical['status']=='passed' and technical['video_sha256']==movie_hash and all(technical['checks'].values()),
        'forty_seven_ui_cues_verified_current_movie':ui['status']=='passed' and ui['video_sha256']==movie_hash and ui['checked_cues']==ui['expected_cues']==47 and ui['all_cues_passed'] and ui['threshold']>=.95,
        'twenty_three_authored_cues_verified_current_movie':authored['status']=='passed' and authored['video_sha256']==movie_hash and authored['checked_cues']==authored['expected_cues']==23 and authored['all_cues_passed'],
        'independent_editorial_review_passed_current_movie':editorial['status'].startswith('passed') and editorial['movie']['sha256']==movie_hash and editorial['blocked_cues']==0 and editorial['reviewed_cues']>=26,
        'all_seventy_source_reference_hashes_unchanged':len(ready['frames'])==70 and not ready['blocking_source_frame_issues'] and all(sha(ROOT/f['reference_png'])==f['reference_sha256'] for f in ready['frames']),
        'factual_claims_passed_frozen_narration':claims['status'].startswith('passed') and claims['storyboard_sha256']==sha(WORK/'storyboard.json') and all(claims['checks'].values()),
        'current_application_verification_passed':app['status']=='passed',
        'single_clean_twenty_one_browser_check_execution':selected==21 and failed==0,
    }
    paths=[OUT/'manifest.json',OUT/'verification.json',OUT/'visual-sync-verification.json',OUT/'authored-sync-verification.json',OUT/'final-encoded-editorial-review.json',WORK/'reviews/final-ready-frame-review.json',WORK/'final-claims-review.json',ROOT/'reports/ui-chat-v4/verification.json',ROOT/'runtime/ui-v4/browser-results.xml']
    report={'status':'passed' if all(checks.values()) else 'review_required','checked_at':datetime.now(timezone.utc).isoformat(),'video':str(movie.relative_to(ROOT)),'video_sha256':movie_hash,'duration_seconds':manifest['duration_seconds'],'bytes':movie.stat().st_size,'chapters':14,'captions':sum(c['caption_count'] for c in manifest['chapters']),'checks':checks,'technical_check_count':len(technical['checks']),'ui_cues':47,'authored_cues':23,'encoded_pixel_samples':140,'independently_reviewed_encoded_cues':editorial['reviewed_cues'],'source_reference_frames_reviewed':70,'single_final_browser_suite':{'selected':selected,'failures_errors_or_skips':failed},'evidence':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in paths],'limits':['Software and pixel checks are not clinical accuracy or patient-outcome validation.','The rejected initial count-loading encode and its false-positive broad ROI results are preserved separately; this gate accepts only the corrected movie hash.']}
    (OUT/'delivery-qc.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'failed_checks':[k for k,v in checks.items() if not v],'video_sha256':movie_hash}))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
