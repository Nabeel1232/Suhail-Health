"""Build an audio-led visual edit from exact speech and recorded-state cues.

The old editor stretched a whole chapter with one ratio. This planner instead
maps each captured state-ready marker to a phrase's real TTS timestamp, placing
the state slightly before its spoken mention. It never generates application
screens, changes a clinical record, or makes a provider request.

Cue JSON example::

  {"chapters": [{"id": "05", "cues": [{
    "id": "board", "phrase": "journey board", "occurrence": 1,
    "visual_event": {"action": "qc_screenshot", "name": "dynamic-journey-board"},
    "box": {"x": 280, "y": 105, "width": 1260, "height": 600}
  }]}]}

Use ``source_seconds`` for an authored animation's recorded stage marker.
Otherwise ``visual_event`` must uniquely identify a real capture action. Boxes
are optional, measured source-viewport coordinates, not invented UI elements.
Run ``python scripts/video/sync_plan.py --help`` for the local-only CLI.
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


ROOT = Path(__file__).resolve().parents[2]


def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite number')
    return float(value)


def normalize(value):
    return unicodedata.normalize('NFKC', value).replace('’', "'").casefold()


def word_spans(value):
    return [(normalize(m.group()), m.start(), m.end())
            for m in re.finditer(r"\w+(?:['’]\w+)?", value, re.UNICODE)]


def aligned_phrase(alignment, phrase, occurrence=None):
    """Find actual phrase timing, rejecting absent and ambiguous matches."""
    chars = alignment['characters']
    starts = alignment['character_start_times_seconds']
    ends = alignment['character_end_times_seconds']
    if not chars or len(chars) != len(starts) or len(chars) != len(ends):
        raise ValueError('Alignment arrays must have the same nonzero length')
    for i, (a, b) in enumerate(zip(starts, ends)):
        a, b = finite(a, 'alignment start'), finite(b, 'alignment end')
        if not 0 <= a <= b or i and (a < starts[i-1] or b < ends[i-1]):
            raise ValueError('Alignment times must be nonnegative and monotonic')
    text = ''.join(chars)
    words, query = word_spans(text), [w[0] for w in word_spans(phrase)]
    if not query:
        raise ValueError('Cue phrase must contain words')
    matches = [(words[i][1], words[i+len(query)-1][2]) for i in range(len(words)-len(query)+1)
               if [w[0] for w in words[i:i+len(query)]] == query]
    if not matches:
        raise ValueError('Cue phrase is absent from actual narration: ' + phrase)
    if occurrence is None and len(matches) != 1:
        raise ValueError('Repeated phrase needs an explicit occurrence: ' + phrase)
    occurrence = 1 if occurrence is None else occurrence
    if type(occurrence) is not int or not 1 <= occurrence <= len(matches):
        raise ValueError('Cue occurrence is outside the matched phrase range')
    first, end = matches[occurrence-1]
    return {'text': text[first:end], 'start_seconds': starts[first],
            'end_seconds': ends[end-1], 'character_start': first,
            'character_end': end, 'occurrence': occurrence,
            'total_occurrences': len(matches)}


def source_marker(capture, cue):
    """Resolve a cue to recorded evidence; never infer an unrecorded action."""
    selector = cue.get('visual_event')
    if selector is not None:
        if not isinstance(selector, dict) or not selector or 'action' not in selector:
            raise ValueError('visual_event needs an action and identifying fields')
        found = [event for event in capture.get('actions', [])
                 if all(event.get(key) == value for key, value in selector.items())]
        if len(found) != 1:
            raise ValueError('Visual event must identify exactly one recorded action: ' + str(selector))
        event = found[0]
        seconds = finite(event.get('source_seconds', event.get('seconds')), 'visual source time')
        evidence = {'event': event, 'method': 'recorded_capture_event'}
    elif 'source_seconds' in cue:
        seconds = finite(cue['source_seconds'], 'visual source time')
        evidence = {'method': 'explicit_recorded_stage_marker',
                    'description': cue.get('source_description', 'Author-supplied source stage marker')}
    else:
        raise ValueError('Each cue needs visual_event or source_seconds')
    seconds += finite(capture.get('event_clock_offset_seconds', 0), 'event clock offset')
    return seconds, evidence


def project_box(box, viewport, authored=False):
    values = {k: finite(box[k], 'box ' + k) for k in ['x', 'y', 'width', 'height']}
    width, height = finite(viewport['width'], 'viewport width'), finite(viewport['height'], 'viewport height')
    if not (width > 0 and height > 0 and values['x'] >= 0 and values['y'] >= 0 and
            values['width'] > 0 and values['height'] > 0 and
            values['x']+values['width'] <= width+.5 and values['y']+values['height'] <= height+.5):
        raise ValueError('Highlight box must be visible inside the recorded viewport')
    if authored:
        sx, sy, ox, oy = 1920/width, 1080/height, 0, 0
    elif height > width:
        sx = sy = 880/height
        ox, oy = 1210, 78
    else:
        sx, sy, ox, oy = 1920/width, 912/height, 0, 60
    result = {'x': round(values['x']*sx+ox, 3), 'y': round(values['y']*sy+oy, 3),
              'width': round(values['width']*sx, 3), 'height': round(values['height']*sy, 3)}
    if result['x']+result['width'] > 1920.5 or result['y']+result['height'] > 1080.5:
        raise ValueError('Projected highlight falls outside the final canvas')
    return result


def map_source(points, seconds):
    seconds = finite(seconds, 'source time')
    if not points[0]['source_seconds']-1e-8 <= seconds <= points[-1]['source_seconds']+1e-8:
        raise ValueError('Source time is outside edit bounds')
    for left, right in zip(points, points[1:]):
        if seconds <= right['source_seconds']+1e-8:
            ratio = (seconds-left['source_seconds'])/(right['source_seconds']-left['source_seconds'])
            return left['output_seconds']+ratio*(right['output_seconds']-left['output_seconds'])
    return points[-1]['output_seconds']


def setpts_expression(points):
    """Expression for a source trimmed then reset with PTS-STARTPTS."""
    trim = points[0]['source_seconds']
    expressions = []
    for left, right in zip(points, points[1:]):
        source_left = left['source_seconds']-trim
        source_right = right['source_seconds']-trim
        slope = (right['output_seconds']-left['output_seconds'])/(source_right-source_left)
        expr = f'((PTS*TB-{source_left:.9f})*{slope:.12f}+{left["output_seconds"]:.9f})'
        expressions.append((source_right, expr))
    expression = expressions[-1][1]
    for limit, expr in reversed(expressions[:-1]):
        expression = f'if(lt(PTS*TB,{limit:.9f}),{expr},{expression})'
    return expression+'/TB'


def visibility_hold_points(points, cues, fps):
    """Pin recorded state ends after their complete spoken explanations.

    Ready anchors stay fixed. Equal source ends share the latest required output
    end. A hold already covered by a later fixed ready anchor needs no extra
    point; impossible/crossed hold order is rejected rather than hidden.
    """
    groups = {}
    for cue in cues:
        if 'source_visible_until_seconds' not in cue:
            continue
        end = finite(cue['source_visible_until_seconds'], 'source visibility end')
        if not cue['source_seconds'] < end <= points[-1]['source_seconds']:
            raise ValueError('Visibility-end marker must follow the ready state inside the source')
        key = round(end, 9)
        row = groups.setdefault(key, {'source_seconds': end, 'output_seconds': 0.,
            'minimum_seconds': 0., 'cue_ids': []})
        row['output_seconds'] = max(row['output_seconds'], cue['mention_end_seconds']+.05)
        row['minimum_seconds'] = max(row['minimum_seconds'], cue['mention_end_seconds']+1/fps)
        row['cue_ids'].append(cue['id'])
    additions = []
    for row in groups.values():
        source, target = row['source_seconds'], row['output_seconds']
        existing = next((p for p in points if abs(p['source_seconds']-source)<1e-8), None)
        if existing:
            if existing['output_seconds']+1e-7 < row['minimum_seconds']:
                raise ValueError('Recorded state leaves before its spoken explanation ends; hold or recapture: '+','.join(row['cue_ids']))
            continue
        # The source may already hold through the final spoken frame. Keep
        # those valid mappings unchanged, particularly authored identity edits;
        # an unnecessary +.05 anchor would introduce a small timing warp.
        if map_source(points, source)+1e-7 >= row['minimum_seconds']:
            continue
        left, right = next((a,b) for a,b in zip(points,points[1:]) if a['source_seconds']<source<b['source_seconds'])
        if target <= left['output_seconds']+1e-8:
            # Overlapping, still-visible regions may end after another ready
            # state. That later fixed anchor already covers this explanation.
            continue
        if target >= right['output_seconds']-1e-8:
            if map_source(points, source)+1e-7 >= row['minimum_seconds']:
                continue
            raise ValueError('Recorded state leaves before its spoken explanation ends; hold or recapture: '+','.join(row['cue_ids']))
        additions.append({'source_seconds': source, 'output_seconds': target,
            'id': '+'.join(row['cue_ids'])+':visible_end', 'kind':'visibility_end',
            'cue_ids':row['cue_ids']})
    combined = sorted(points+additions, key=lambda p:p['source_seconds'])
    if any(b['source_seconds']<=a['source_seconds'] or b['output_seconds']<=a['output_seconds']
           for a,b in zip(combined,combined[1:])):
        raise ValueError('Visibility holds require strictly increasing source/output order; recapture or revise overlapping explanation ends')
    return combined


def build_chapter(chapter_id, capture, alignment, cue_rows, audio_duration,
                  speed=1., lead=.6, tail=.8, anticipation=.24, fps=25,
                  require_visible_holds=False):
    if capture.get('status') != 'completed' or capture.get('errors'):
        raise ValueError('Capture must be completed and clean before sync planning')
    if not cue_rows:
        raise ValueError('Each chapter needs semantic visual cues; uniform fallback is not a sync proof')
    raw = finite(capture['duration_seconds'], 'capture duration')
    trim = finite(capture.get('trim_start_seconds', 0), 'capture trim')
    speed, lead, tail = finite(speed, 'speed'), finite(lead, 'lead'), finite(tail, 'tail')
    if not 0 < speed <= 2 or not 0 <= trim < raw or fps <= 0:
        raise ValueError('Invalid audio speed, source trim or frame rate')
    total = math.ceil((finite(audio_duration, 'audio duration')/speed+lead+tail)*fps-1e-7)/fps
    cues, points = [], [{'source_seconds': trim, 'output_seconds': 0., 'id': 'start'}]
    identities = set()
    for row in cue_rows:
        ident = row['id']
        if ident in identities:
            raise ValueError('Cue IDs must be unique within a chapter')
        identities.add(ident)
        phrase = aligned_phrase(alignment, row['phrase'], row.get('occurrence'))
        mention_start, mention_end = phrase['start_seconds']/speed+lead, phrase['end_seconds']/speed+lead
        until = aligned_phrase(alignment, row['until_phrase'], row.get('until_occurrence')) if row.get('until_phrase') else None
        if until:
            mention_end = until['end_seconds']/speed+lead
            if mention_end < mention_start:
                raise ValueError('until_phrase must follow the cue mention')
        desired_lead = finite(row.get('anticipation_seconds', anticipation), 'visual anticipation')
        if not 0 <= desired_lead <= 1:
            raise ValueError('Visual anticipation must be between zero and one second')
        # Round toward the earlier frame: the encoded frame must already be
        # present at least the requested lead before the spoken feature.
        target = math.floor(max(0., mention_start-desired_lead)*fps+1e-8)/fps
        source, evidence = source_marker(capture, row)
        initial_state = row.get('initial_state', False)
        if initial_state:
            if len(points) != 1 or abs(source-trim) > 1/fps:
                raise ValueError('An initial-state cue must identify the first retained source frame')
            source, target = trim, 0.
        elif not trim < source < raw:
            raise ValueError('Visual state marker must be inside the trimmed source: ' + ident)
        if not initial_state and (source <= points[-1]['source_seconds'] or target <= points[-1]['output_seconds']):
            raise ValueError('Cues require increasing source and narration order; recapture or revise the script: ' + ident)
        if target >= total:
            raise ValueError('Visual target is outside final chapter: ' + ident)
        if not initial_state:
            points.append({'source_seconds': source, 'output_seconds': target, 'id': ident})
        highlight_end = min(total, max(mention_end+.35, target+finite(row.get('highlight_hold_seconds', 2.), 'highlight hold')))
        cue = {'id': ident, 'phrase': phrase, 'source_seconds': source, 'initial_state': initial_state,
               'mention_start_seconds': mention_start, 'mention_end_seconds': mention_end,
               'visual_ready_output_seconds': target,
               'visual_lead_seconds': round(mention_start-target, 6),
               'verification_frame_seconds': mention_start,
               'highlight_start_seconds': target, 'highlight_end_seconds': highlight_end,
               'source_evidence': evidence}
        if until:
            cue['spoken_until_phrase'] = until
        if row.get('visual_end_event'):
            end_source, end_evidence = source_marker(capture, {'visual_event': row['visual_end_event']})
            cue['source_visible_until_seconds'], cue['visibility_end_evidence'] = end_source, end_evidence
        elif row.get('source_visible_until_seconds') is not None:
            cue['source_visible_until_seconds'] = finite(row['source_visible_until_seconds'], 'source visibility end')
        elif evidence.get('event', {}).get('source_visible_until_seconds') is not None:
            cue['source_visible_until_seconds'] = finite(evidence['event']['source_visible_until_seconds'], 'source visibility end')
        if require_visible_holds and 'source_visible_until_seconds' not in cue:
            raise ValueError('Production cue requires a recorded visibility-end marker: ' + ident)
        box = row.get('box') or evidence.get('event', {}).get('box') or evidence.get('event', {}).get('bbox')
        if box is not None:
            cue['source_box'] = box
            cue['projected_box'] = project_box(box, capture['viewport'], capture.get('media_type') == 'authored_motion_graphics')
        cues.append(cue)
    points.append({'source_seconds': raw, 'output_seconds': total, 'id': 'end'})
    points = visibility_hold_points(points, cues, fps)
    segments, warnings = [], []
    for left, right in zip(points, points[1:]):
        scale = (right['output_seconds']-left['output_seconds'])/(right['source_seconds']-left['source_seconds'])
        if scale <= 0:
            raise ValueError('Every edit segment needs positive duration')
        if scale < .35 or scale > 3:
            warnings.append({'segment': left['id']+' -> '+right['id'], 'pts_scale': scale,
                             'reason': 'Review fast transitions or long holds; recapture beats when needed.'})
        segments.append({'from': left['id'], 'to': right['id'],
                         'source_start_seconds': left['source_seconds'], 'source_end_seconds': right['source_seconds'],
                         'output_start_seconds': left['output_seconds'], 'output_end_seconds': right['output_seconds'],
                         'pts_scale': scale, 'playback_rate': 1/scale})
    for cue in cues:
        actual = map_source(points, cue['source_seconds'])
        cue['mapped_visual_ready_seconds'] = actual
        cue['anchor_error_seconds'] = actual-cue['visual_ready_output_seconds']
        expected_lead = next(row.get('anticipation_seconds', anticipation) for row in cue_rows if row['id'] == cue['id'])
        cue['encoded_ready_frame_seconds'] = math.ceil((actual-1e-8)*fps)/fps
        cue['encoded_visual_lead_seconds'] = cue['mention_start_seconds']-cue['encoded_ready_frame_seconds']
        if 'source_visible_until_seconds' in cue:
            end_source = cue['source_visible_until_seconds']
            if not cue['source_seconds'] < end_source <= raw:
                raise ValueError('Visibility-end marker must follow the ready state inside the source')
            cue['mapped_visibility_end_seconds'] = map_source(points, end_source)
            cue['visible_during_spoken_phrase'] = cue['mapped_visibility_end_seconds'] >= cue['mention_end_seconds']+1/fps-1e-7
            cue['highlight_end_seconds'] = min(cue['highlight_end_seconds'], cue['mapped_visibility_end_seconds']-1/fps)
            if not cue['visible_during_spoken_phrase']:
                raise ValueError('Recorded state leaves before its spoken explanation ends; hold or recapture: ' + cue['id'])
        cue['mathematical_sync_passed'] = (abs(cue['anchor_error_seconds']) <= 1/fps and
            cue['encoded_visual_lead_seconds'] >= min(expected_lead, cue['mention_start_seconds'])-1e-7)
    expression = setpts_expression(points)
    return {'id': chapter_id, 'status': 'planned', 'duration_seconds': total, 'fps': fps,
            'source_trim_seconds': trim, 'source_duration_seconds': raw,
            'audio_speed': speed, 'lead_seconds': lead, 'tail_seconds': tail,
            'control_points': points, 'segments': segments, 'cues': cues,
            'all_semantic_anchors_pass': all(c['mathematical_sync_passed'] for c in cues),
            'setpts_expression': expression,
            'video_filter_prefix': f"trim=start={trim:.9f}:end={raw:.9f},setpts=PTS-STARTPTS,setpts='{expression}',fps={fps}",
            'warnings': warnings,
            'limits': ['Cue timing proves the declared recorded marker mapping, not semantic image recognition.',
                       'Source event timestamps use the capture clock; inspect encoded cue frames against the retained ready-state screenshot.',
                       'Highlights must use measured source-viewport boxes; no invented UI or clinical state is created.']}


def probe_duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)], text=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--cue-file', type=Path, required=True)
    parser.add_argument('--capture-manifest', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--audio-speed', type=float, default=1.)
    parser.add_argument('--lead', type=float, default=.6)
    parser.add_argument('--tail', type=float, default=.8)
    parser.add_argument('--require-visible-holds', action='store_true', help='Require recorded state-end markers that cover every spoken explanation')
    args = parser.parse_args()
    work = args.work_dir.resolve()
    capture_path = args.capture_manifest or work/'captures/manifest.json'
    raw = json.loads(capture_path.read_text())
    captures = {r['id']: r for r in raw['scenes']}
    specification = json.loads(args.cue_file.read_text())
    defaults = specification.get('defaults', {})
    chapters = []
    for row in specification['chapters']:
        ident = row['id']
        alignment_path = work/(ident+'-alignment.json')
        raw = json.loads(alignment_path.read_text())
        alignment = raw.get('normalized_alignment') or raw['alignment']
        chapter = build_chapter(ident, captures[ident], alignment, row['cues'], probe_duration(work/(ident+'.mp3')),
            args.audio_speed, args.lead, args.tail, defaults.get('anticipation_seconds', .24), defaults.get('fps', 25), args.require_visible_holds)
        chapter['sources'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [alignment_path, capture_path, args.cue_file]}
        chapters.append(chapter)
    result = {'schema_version': 'suhail-audio-led-visual-sync-v1',
              'generated_at': datetime.now(timezone.utc).isoformat(),
              'status': 'planned', 'method': 'Exact phrase-alignment to recorded-state piecewise visual retiming',
              'generation_requests': 0, 'application_state_changes': 0,
              'chapters': chapters, 'total_cues': sum(len(c['cues']) for c in chapters),
              'all_semantic_anchors_pass': all(c['all_semantic_anchors_pass'] for c in chapters),
              'final_encoded_visual_review_required': True}
    output = args.output or work/'sync-plan.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': result['status'], 'chapters': len(chapters),
                     'cues': result['total_cues'], 'all_semantic_anchors_pass': result['all_semantic_anchors_pass'],
                     'output': str(output)}))


if __name__ == '__main__':
    main()
