"""Pure local checks for audio-led visual editing; no app/provider requests."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/video'))
from sync_plan import aligned_phrase, build_chapter, map_source, project_box, visibility_hold_points


def alignment(text, step=.1):
    return {'characters': list(text),
            'character_start_times_seconds': [i*step for i in range(len(text))],
            'character_end_times_seconds': [(i+1)*step for i in range(len(text))]}


def capture():
    return {'status': 'completed', 'errors': [], 'duration_seconds': 20.,
            'trim_start_seconds': 1., 'viewport': {'width': 1600, 'height': 760},
            'actions': [{'action': 'ready', 'name': 'board', 'seconds': 4.},
                        {'action': 'ready', 'name': 'patient', 'seconds': 12.}]}


def cues():
    return [{'id': 'board', 'phrase': 'journey board',
             'visual_event': {'action': 'ready', 'name': 'board'}},
            {'id': 'patient', 'phrase': 'patient details',
             'visual_event': {'action': 'ready', 'name': 'patient'}}]


def test_phrase_finds_real_timestamps_despite_case_and_punctuation():
    text = 'Open the Journey Board, then read patient details.'
    found = aligned_phrase(alignment(text), 'journey board')
    assert found['start_seconds'] == pytest.approx(text.index('Journey')*.1)
    assert found['end_seconds'] == pytest.approx((text.index('Board')+len('Board'))*.1)


def test_repeated_phrase_requires_occurrence_to_prevent_wrong_visual():
    a = alignment('Open the board. Later return to the board.')
    with pytest.raises(ValueError, match='explicit occurrence'):
        aligned_phrase(a, 'the board')
    assert aligned_phrase(a, 'the board', 2)['start_seconds'] > aligned_phrase(a, 'the board', 1)['start_seconds']


def test_each_recorded_state_arrives_before_its_exact_spoken_mention():
    plan = build_chapter('05', capture(), alignment('Open the journey board, then read the patient details.'), cues(), 8.)
    for cue in plan['cues']:
        actual = map_source(plan['control_points'], cue['source_seconds'])
        assert .24-1e-8 <= cue['mention_start_seconds']-actual < .24+1/25+1e-8
        assert cue['mathematical_sync_passed']
    assert plan['control_points'][0]['output_seconds'] == 0
    assert plan['control_points'][-1]['output_seconds'] == plan['duration_seconds']


def test_narration_and_action_order_conflict_requires_recapture():
    rows = cues()
    rows[0]['visual_event']['name'], rows[1]['visual_event']['name'] = 'patient', 'board'
    with pytest.raises(ValueError, match='recapture or revise'):
        build_chapter('05', capture(), alignment('Open the journey board, then read the patient details.'), rows, 8.)


def test_missing_or_ambiguous_capture_marker_cannot_create_fake_sync_proof():
    c = capture()
    c['actions'].append(dict(c['actions'][0]))
    with pytest.raises(ValueError, match='exactly one recorded action'):
        build_chapter('05', c, alignment('Open the journey board, then read the patient details.'), cues(), 8.)


def test_highlight_projects_real_mobile_box_and_rejects_offscreen_box():
    viewport = {'width': 390, 'height': 844}
    box = project_box({'x': 20, 'y': 100, 'width': 350, 'height': 200}, viewport)
    assert box['x'] == pytest.approx(1210+20*880/844, abs=.001)
    assert box['y'] == pytest.approx(78+100*880/844, abs=.001)
    with pytest.raises(ValueError, match='inside the recorded viewport'):
        project_box({'x': 20, 'y': 700, 'width': 350, 'height': 200}, viewport)


def test_uncued_chapter_cannot_be_labelled_semantically_synchronized():
    with pytest.raises(ValueError, match='semantic visual cues'):
        build_chapter('05', capture(), alignment('Open the journey board.'), [], 8.)


def test_initial_frame_is_already_visible_before_first_words():
    c = capture()
    c['actions'].insert(0, {'action': 'ready', 'name': 'brand', 'source_seconds': 1.})
    rows = [{'id': 'brand', 'phrase': 'Suhail Health', 'initial_state': True,
             'visual_event': {'action': 'ready', 'name': 'brand'}}]
    plan = build_chapter('01', c, alignment('We are Suhail Health.'), rows, 4.)
    assert plan['cues'][0]['visual_ready_output_seconds'] == 0
    assert plan['cues'][0]['mathematical_sync_passed']


def test_production_cue_needs_a_real_visibility_end_marker():
    with pytest.raises(ValueError, match='recorded visibility-end marker'):
        build_chapter('05', capture(), alignment('Open the journey board, then read the patient details.'), cues(), 8., require_visible_holds=True)


def test_state_cannot_leave_while_its_explanation_is_still_spoken():
    rows = cues()
    rows[0].update(until_phrase='patient details', source_visible_until_seconds=5.)
    rows[1]['source_visible_until_seconds'] = 20.
    with pytest.raises(ValueError, match='spoken explanation ends'):
        build_chapter('05', capture(), alignment('Open the journey board, then read the patient details.'), rows, 8., require_visible_holds=True)


def test_recorded_visibility_end_is_pinned_after_the_complete_explanation():
    rows = cues()
    rows[0].update(phrase='board', until_phrase='panel visible', source_visible_until_seconds=5.)
    rows[1]['source_visible_until_seconds']=19.
    text='Open the board. Keep this panel visible. Then read patient details.'
    plan=build_chapter('05',capture(),alignment(text),rows,8.,require_visible_holds=True)
    first=plan['cues'][0]
    assert map_source(plan['control_points'],5.)==pytest.approx(first['mention_end_seconds']+.05)
    assert first['visible_during_spoken_phrase']
    assert any(p.get('kind')=='visibility_end' for p in plan['control_points'])


def test_equal_visibility_source_ends_merge_using_the_latest_spoken_end():
    points=[{'source_seconds':0.,'output_seconds':0.,'id':'start'},
            {'source_seconds':2.,'output_seconds':2.,'id':'second'},
            {'source_seconds':10.,'output_seconds':9.,'id':'end'}]
    cues=[{'id':'first','source_seconds':0.,'source_visible_until_seconds':8.,'mention_end_seconds':5.},
          {'id':'second','source_seconds':2.,'source_visible_until_seconds':8.,'mention_end_seconds':7.5}]
    result=visibility_hold_points(points,cues,25)
    matching=[p for p in result if p['source_seconds']==8.]
    assert len(matching)==1 and matching[0]['output_seconds']==pytest.approx(7.55)
    assert matching[0]['cue_ids']==['first','second']


def test_crossed_visibility_end_output_order_is_rejected():
    points=[{'source_seconds':0.,'output_seconds':0.,'id':'start'},
            {'source_seconds':10.,'output_seconds':10.,'id':'end'}]
    cues=[{'id':'first','source_seconds':0.,'source_visible_until_seconds':4.,'mention_end_seconds':6.},
          {'id':'second','source_seconds':1.,'source_visible_until_seconds':5.,'mention_end_seconds':5.5}]
    with pytest.raises(ValueError,match='strictly increasing'):
        visibility_hold_points(points,cues,25)


def test_already_covered_visibility_holds_preserve_authored_identity_mapping():
    points=[{'source_seconds':0.,'output_seconds':0.,'id':'start'},
            {'source_seconds':2.,'output_seconds':2.,'id':'second'},
            {'source_seconds':10.,'output_seconds':10.,'id':'end'}]
    for end,spoken_end in [(4.,3.96),(8.,6.)]:
        cue={'id':'authored-stage','source_seconds':2.,
             'source_visible_until_seconds':end,'mention_end_seconds':spoken_end}
        result=visibility_hold_points(points,[cue],25)
        assert result==points
        assert all(point['source_seconds']==point['output_seconds'] for point in result)
        assert map_source(result,end)>=spoken_end+1/25-1e-8
