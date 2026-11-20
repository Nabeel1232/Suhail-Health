"""Observe actual split separation and gold consistency without live inference."""
import csv
import io
import json
import re
import pytest

from evals.common import FUNCTIONS, digest
from evals.synthetic import function_cases as v1_cases, score_proposal
from evals.synthetic_v2 import function_cases, observable_family, manifest, GENERATOR_VERSION, SEEDS

SPLITS = ('development', 'validation', 'holdout')


def extract_actual_source(case):
    document = case['source_document']
    if isinstance(document, dict):
        resources = {entry['resource']['resourceType']: entry['resource'] for entry in document['entry']}
        observation = resources['Observation']
        return {'patient_id': resources['Patient']['id'],
            'order_id': observation.get('basedOn', [{}])[0].get('reference', '').removeprefix('ServiceRequest/'),
            'test_code': observation['code']['coding'][0]['code'],
            'result_version': observation['meta']['versionId']}
    if case['source_media_type'] == 'text/csv':
        row = next(csv.DictReader(io.StringIO(document)))
        return {'patient_id': row['patient_ref'], 'order_id': row['order_ref'],
            'test_code': row['screening_code'], 'result_version': row['result_revision']}
    fields = dict(line.split(': ', 1) for line in document.splitlines()[1:])
    keys = ('معرف المريض', 'معرف الطلب', 'رمز الفحص', 'إصدار النتيجة') if case['language'] == 'ar' else (
        'Participant reference', 'Order reference', 'Screening code', 'Result revision')
    result = dict(zip(('patient_id', 'order_id', 'test_code', 'result_version'), [fields[key] for key in keys]))
    if result['order_id'] in ('[not supplied]', '[غير متوفر]'):
        result['order_id'] = ''
    return result


def stripped_observation(example):
    # Exclude IDs, split/generator/template labels, and any source checksums.
    # Inspect actual source content/shape and actual operational observations.
    case = example['case']
    body = json.dumps({'source': case['source_document'], 'context': case['operational_context'],
        'request': case['requested_task'], 'question': case.get('patient_question')}, sort_keys=True, ensure_ascii=False)
    body = re.sub(r'SYN2-\d+-F\d+-\d+(?:-[A-Za-z_]+)*', '<identifier>', body)
    return digest(body)


@pytest.mark.parametrize('function', FUNCTIONS)
def test_real_source_structures_and_feature_combinations_are_disjoint_after_labels_removed(function):
    batches = {split: function_cases(function, 18, split) for split in SPLITS}
    structural, observed = {}, {}
    for index, split in enumerate(SPLITS, 1):
        structural[split] = {digest(observable_family(e)) for e in batches[split]}
        observed[split] = {stripped_observation(e) for e in batches[split]}
        assert all(len(e['case']['operational_context']) == index for e in batches[split])
        assert all(not any(split in key for key in e['case']['operational_context']) for e in batches[split])
    for left, right in [('development', 'validation'), ('development', 'holdout'), ('validation', 'holdout')]:
        assert structural[left].isdisjoint(structural[right])
        assert observed[left].isdisjoint(observed[right])
        # Combination separation holds even when document structures/prose are ignored.
        assert {tuple(sorted(e['case']['operational_context'])) for e in batches[left]}.isdisjoint(
            {tuple(sorted(e['case']['operational_context'])) for e in batches[right]})
    assert all(isinstance(e['case']['source_document'], dict) for e in batches['development'])
    assert all(len(list(csv.DictReader(io.StringIO(e['case']['source_document'])))) == 1 for e in batches['validation'])
    assert any(e['case']['language'] == 'ar' and 'معرف المريض' in e['case']['source_document'] for e in batches['holdout'])


@pytest.mark.parametrize('split', SPLITS)
def test_intake_truth_matches_actual_parsed_source_not_only_case_labels(split):
    for example in function_cases('intake', 12, split):
        facts = {key: value for key, value in extract_actual_source(example['case']).items() if value != ''}
        assert facts == example['truth']['fact_fields']
        assert set(example['truth']) == {'recommended_action', 'fact_fields', 'evidence_ids', 'review_required'}
        assert 'source_spans' not in example['truth']  # No invented offsets or spans.


def test_ids_seeds_and_all_linked_evidence_are_consistent_and_disjoint_from_v1():
    assert set(SEEDS.values()).isdisjoint({101, 202, 90317})
    patients, ids = set(), set()
    for function in FUNCTIONS:
        for split in SPLITS:
            batch = function_cases(function, 12, split)
            assert batch == function_cases(function, 12, split)
            assert all(e['generator_version'] == GENERATOR_VERSION for e in batch)
            old = {e['case']['patient_id'] for e in v1_cases(function, 12, split)}
            new = {e['case']['patient_id'] for e in batch}
            assert new.isdisjoint(old) and new.isdisjoint(patients)
            patients.update(new)
            for example in batch:
                case = example['case']
                assert case['id'] == case['case_id'] and case['id'] not in ids
                ids.add(case['id'])
                assert 'SYN-DEVELOPMENT-' not in json.dumps(example)
                assert all(case['id'] in ref for ref in case['source_references'])
                gold_ids = set(example['truth']['evidence_ids'])
                actual_valid = {e['id'] for e in case['evidence'] if e['verification'] == 'verified' and
                    e['status'] == 'current' and e['patient_id'] == case['patient_id'] and
                    e['order_id'] == case['order_id'] and e['result_version'] == case['result_version']}
                assert gold_ids == actual_valid
                assert all(case['id'] in e['id'] and case['id'] in e['reference'] for e in case['evidence'])


@pytest.mark.parametrize('function', FUNCTIONS)
def test_same_independent_scorer_accepts_gold_and_rejects_wrong_actions(function):
    for split in SPLITS:
        for example in function_cases(function, 6, split):
            case, truth = example['case'], example['truth']
            proposal = {'case_id': case['id'], 'case_version': case['version'], 'function': function,
                'recommended_action': truth['recommended_action'], 'policy_version': 'demo-fit-v1',
                'source_references': case['source_references'], 'evidence_ids': truth['evidence_ids'],
                'missing_fields': ['order_id'] if not case['order_id'] else [],
                'extracted_facts': [{'field': key, 'value': value, 'source_reference': case['source_references'][0]}
                    for key, value in truth['fact_fields'].items()],
                'patient_message': 'راجع الخطوة التالية مع فريق الرعاية المسؤول.' if case['language'] == 'ar' else 'Discuss the documented next step with your responsible care team.'}
            assert score_proposal(example, proposal)['passed']
            proposal['recommended_action'] = 'review_identity' if truth['recommended_action'] != 'review_identity' else 'closure_review'
            assert not score_proposal(example, proposal)['passed']


def test_questions_and_metadata_are_honest_and_generation_does_not_mutate_v1():
    original = v1_cases('patient_navigator', 6, 'development')
    batches = [function_cases('patient_navigator', 6, split) for split in SPLITS]
    assert len({batch[1]['case']['patient_question'] for batch in batches}) == 3
    assert len({batch[0]['case']['requested_task'] for batch in batches}) == 3
    assert v1_cases('patient_navigator', 6, 'development') == original
    meta = manifest([e for batch in batches for e in batch])
    assert meta['not_clinical_ground_truth'] and meta['generator_version'] == GENERATOR_VERSION
    assert any('shared' in limitation for limitation in meta['limitations'])
    assert function_cases('intake', 0) == []
    for count in [-1, True, 1.5]:
        with pytest.raises(ValueError): function_cases('intake', count)
