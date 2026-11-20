"""Future synthetic sets with observable source/combination family separation.

The care decision rules and six core v1 scenario variants are intentionally
shared. V2 separates source-document structures, request wording, and actual
operational-context combinations; it does not claim new clinical-rule families
or external generalization. No model call occurs during generation or scoring.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import random
from typing import Any

from .common import FUNCTIONS, digest
from .synthetic import function_cases as v1_function_cases, score_proposal

GENERATOR_VERSION = 'suhail-synthetic-v2.0'
SEEDS = {'development': 710921, 'validation': 820933, 'holdout': 930947}
SOURCE_FAMILIES = {
    'development': 'fhir-r4-result-bundle',
    'validation': 'controlled-transfer-csv',
    'holdout': 'screening-followup-narrative',
}

REQUESTS = {
    'development': {
        'intake': 'Extract the recorded identifiers and source result revision from this FHIR bundle.',
        'pathway_router': 'Check the result code and identity state against the configured pathway mapping.',
        'safety_escalation': 'Identify whether the recorded source flag requires staffed review.',
        'patient_navigator': 'Prepare a short explanation of the recorded next action and responsible team.',
        'coordination': 'Review the current referral and appointment records before proposing the next coordination action.',
        'closure_evidence': 'Compare current evidence identifiers and open required work with the care endpoint.',
    },
    'validation': {
        'intake': 'A transfer arrived as a controlled table. Which supplied facts can be extracted, and which are missing?',
        'pathway_router': 'Does this tabular transfer fit a permitted follow-up pathway, or should staff reconcile it?',
        'safety_escalation': 'Use the explicit alert fields in this transfer to prepare the appropriate staff route.',
        'patient_navigator': 'Help the participant understand the immediate step described by this transfer and how to reach the team.',
        'coordination': 'Given the service response in this transfer, what owned coordination work should happen next?',
        'closure_evidence': 'Which referenced records support the endpoint, and what unfinished requirement prevents review?',
    },
    'holdout': {
        'intake': 'Read this follow-up note and report only the exact patient, order, code and revision facts it contains.',
        'pathway_router': 'Assess the documented screening context for a configured coordination route without inferring a diagnosis.',
        'safety_escalation': 'Prepare a human handoff from this note while preserving any trusted urgent signal.',
        'patient_navigator': 'Explain the documented next step and human support route for this participant in their selected language.',
        'coordination': 'Review this narrative together with the unresolved service events and propose a bounded next action.',
        'closure_evidence': 'Locate source-linked current evidence in this note and distinguish the documented endpoint from pending work.',
    },
}
AR_REQUESTS = {
    'intake': 'اقرأ ملاحظة المتابعة واستخرج فقط معرف المريض والطلب ورمز النتيجة وإصدارها كما وردت.',
    'pathway_router': 'راجع بيانات الفحص الموثقة لتحديد مسار التنسيق المسموح أو الحاجة إلى مراجعة بشرية.',
    'safety_escalation': 'جهز إحالة إلى الفريق البشري مع الحفاظ على أي علامة عاجلة موثوقة في المصدر.',
    'patient_navigator': 'اشرح الخطوة التالية الموثقة وكيفية التواصل مع الفريق المسؤول باللغة المفضلة للمشارك.',
    'coordination': 'راجع هذه الملاحظة وأحداث الخدمة غير المحسومة واقترح الخطوة التالية ضمن صلاحيات التنسيق.',
    'closure_evidence': 'حدد الأدلة الحالية المرتبطة بالمصدر وميز بينها وبين متطلبات الرعاية التي لم تكتمل.',
}

PATIENT_QUESTIONS = {
    'development': 'Could the clinician explain the assessment mentioned in my result update?',
    'validation': 'I received the transfer notice. Who can discuss what I should expect at the follow-up visit?',
    'holdout': 'Before I arrange transport, could my clinician clarify the documented assessment and next step?',
}
AR_PATIENT_QUESTION = 'قبل ترتيب المواصلات، هل يمكن لطبيبي توضيح التقييم المسجل والخطوة التالية؟'

# These are real observable preferences/support conditions, not split labels.
# Their cardinalities (one/two/three) make combination families disjoint even
# after all IDs, prose, provenance metadata and split names are removed.
CONTEXT_COMBINATIONS = {
    'development': (
        ('transport_support',), ('contact_window',), ('administrative_correction',),
    ),
    'validation': (
        ('transport_support', 'contact_window'),
        ('language_support', 'slot_availability'),
        ('caregiver_coordination', 'administrative_correction'),
    ),
    'holdout': (
        ('transport_support', 'language_support', 'slot_availability'),
        ('contact_window', 'caregiver_coordination', 'administrative_correction'),
        ('transport_support', 'contact_window', 'slot_availability'),
    ),
}


def _replace(value: Any, substitutions: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace(item, substitutions) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace(item, substitutions) for item in value]
    if isinstance(value, str):
        for old, new in substitutions.items():
            value = value.replace(old, new)
    return value


def _context(case: dict, keys: tuple[str, ...], rng: random.Random) -> dict:
    availability = 'not_yet_confirmed'
    if any(a.get('status') == 'no_slots' for a in case['appointments']):
        availability = 'none_available_reported_by_service'
    values = {
        'transport_support': {'reported': True, 'request': rng.choice(['accessible_vehicle', 'public_transport_planning'])},
        'contact_window': {'preferred': rng.choice(['morning', 'afternoon']), 'channel': 'secure_portal'},
        'administrative_correction': {'field': 'contact_spelling', 'clinical_content_changed': False, 'state': 'source_confirmation_pending'},
        'language_support': {'preferred_language': case['language'], 'staff_interpreter_requested': True},
        'slot_availability': {'state': availability, 'confirmation_authority': 'receiving_service'},
        'caregiver_coordination': {'assistance_requested': True, 'sharing_authorization': 'not_yet_recorded'},
    }
    return {key: values[key] for key in keys}


def _source_fields(case: dict) -> dict:
    """Source facts are generated from scenario state, never from a proposal."""
    return {
        'patient_ref': case['patient_id'], 'order_ref': case['order_id'],
        'screening_code': case['test_code'], 'result_revision': str(case['result_version']),
        'identity_verified': str(case['identity_verified']).lower(),
        'trusted_urgent': str(case['trusted_urgent']).lower(),
        'preferred_language': case['language'],
    }


def _fhir_document(case: dict) -> dict:
    observation = {
        'resourceType': 'Observation', 'id': case['id'] + '-result',
        'status': 'amended' if case.get('correction') else 'final',
        'meta': {'versionId': str(case['result_version'])},
        'subject': {'reference': 'Patient/' + case['patient_id']},
        'code': {'coding': [{'system': 'urn:suhail:synthetic-screening-code', 'code': case['test_code']}]},
        'extension': [{'url': 'urn:suhail:synthetic-identity-verified', 'valueBoolean': case['identity_verified']}],
    }
    if case['order_id']:
        observation['basedOn'] = [{'reference': 'ServiceRequest/' + case['order_id']}]
    if case['trusted_urgent']:
        observation['interpretation'] = [{'coding': [{'code': 'HH'}]}]
    entries = [{'resource': {'resourceType': 'Patient', 'id': case['patient_id'],
        'name': [{'text': case['patient_name']}], 'communication': [{'language': {'text': case['language']}}]}},
        {'resource': observation}]
    if case['order_id']:
        entries.append({'resource': {'resourceType': 'ServiceRequest', 'id': case['order_id'],
            'status': 'active', 'intent': 'order', 'subject': {'reference': 'Patient/' + case['patient_id']}}})
    return {'resourceType': 'Bundle', 'type': 'collection', 'entry': entries}


def _csv_document(case: dict) -> str:
    output = io.StringIO(newline='')
    fields = _source_fields(case)
    writer = csv.DictWriter(output, fieldnames=list(fields), lineterminator='\n')
    writer.writeheader()
    writer.writerow(fields)
    return output.getvalue()


def _narrative_document(case: dict) -> str:
    fields = _source_fields(case)
    if case['language'] == 'ar':
        labels = {'patient_ref': 'معرف المريض', 'order_ref': 'معرف الطلب', 'screening_code': 'رمز الفحص',
            'result_revision': 'إصدار النتيجة', 'identity_verified': 'مطابقة الهوية موثقة',
            'trusted_urgent': 'علامة عاجلة موثوقة', 'preferred_language': 'اللغة المفضلة'}
        heading, absent = 'ملاحظة تنسيق متابعة الفحص — مشارك افتراضي', '[غير متوفر]'
    else:
        labels = {'patient_ref': 'Participant reference', 'order_ref': 'Order reference', 'screening_code': 'Screening code',
            'result_revision': 'Result revision', 'identity_verified': 'Identity match documented',
            'trusted_urgent': 'Trusted urgent signal', 'preferred_language': 'Preferred language'}
        heading, absent = 'Screening follow-up coordination note — fictional participant', '[not supplied]'
    return heading + '\n' + '\n'.join(labels[key] + ': ' + (value or absent) for key, value in fields.items())


def function_cases(function: str, count=6, split='holdout') -> list[dict]:
    if function not in FUNCTIONS:
        raise ValueError('unknown_function')
    if split not in SEEDS:
        raise ValueError('invalid_split')
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError('count_must_be_nonnegative_integer')
    examples = []
    # Reuse only the independent, known-rule base truth. V1 IDs and template
    # metadata are replaced, and v1 artifacts remain unchanged.
    for index, original in enumerate(v1_function_cases(function, count, 'development')):
        old_prefix = original['case']['id']
        prefix = f'SYN2-{SEEDS[split]}-F{FUNCTIONS.index(function)}-{index:06d}'
        substitutions = {old_prefix: prefix, 'WRONG-PATIENT': prefix + '-OTHER-PATIENT',
            'synthetic://wrong-evidence': 'synthetic://' + prefix + '/wrong-evidence',
            'synthetic://old-evidence': 'synthetic://' + prefix + '/old-evidence'}
        example = _replace(copy.deepcopy(original), substitutions)
        case = example['case']
        case['patient_name'] = 'Project fictional participant ' + str(index)
        case['language'] = 'ar' if split == 'holdout' and index % 2 else 'en'
        case['requested_task'] = AR_REQUESTS[function] if case['language'] == 'ar' else REQUESTS[split][function]
        if case.get('patient_question'):
            question = AR_PATIENT_QUESTION if case['language'] == 'ar' else PATIENT_QUESTIONS[split]
            case['patient_question'] = question
            for consultation in case['consultations']:
                if consultation.get('type') == 'patient_to_clinician':
                    consultation['question'] = question
        keys = CONTEXT_COMBINATIONS[split][index % len(CONTEXT_COMBINATIONS[split])]
        case['operational_context'] = _context(case, keys, random.Random(SEEDS[split] + 10007 * FUNCTIONS.index(function) + index))
        case['barriers'] = [{'type': key, **value} for key, value in case['operational_context'].items()
            if key in {'transport_support', 'language_support', 'caregiver_coordination'}]
        if split == 'development':
            case['source_document'], case['source_media_type'] = _fhir_document(case), 'application/fhir+json'
        elif split == 'validation':
            case['source_document'], case['source_media_type'] = _csv_document(case), 'text/csv'
        else:
            case['source_document'], case['source_media_type'] = _narrative_document(case), 'text/plain'
        example.update(id=f'{function}-v2-{split}-{index:03d}', split=split,
            template_family=SOURCE_FAMILIES[split] + ':' + '+'.join(keys), generator_version=GENERATOR_VERSION)
        examples.append(example)
    return examples


def observable_family(example: dict) -> dict:
    """ID-free structural proof, independent of split names and template labels."""
    case = example['case']
    document = case['source_document']
    if isinstance(document, dict):
        structure = {'object_keys': sorted(document),
            'resource_types': [entry['resource']['resourceType'] for entry in document['entry']]}
    elif case['source_media_type'] == 'text/csv':
        structure = {'table_columns': next(csv.reader(io.StringIO(document))), 'rows': len(list(csv.DictReader(io.StringIO(document))))}
    else:
        structure = {'narrative_labels': [line.split(':', 1)[0] for line in document.splitlines()[1:]]}
    return {'source_structure': structure, 'operational_features': sorted(case['operational_context'])}


def manifest(examples: list[dict]) -> dict:
    return {'id': 'suhail_project_synthetic_v2', 'generator_version': GENERATOR_VERSION,
        'revision': digest(examples), 'sha256': digest(examples), 'split_seeds': SEEDS,
        'selected_case_ids': [example['id'] for example in examples],
        'source_template_families': SOURCE_FAMILIES,
        'observable_family_fingerprints': sorted({digest(observable_family(example)) for example in examples}),
        'license': 'project_generated_no_upstream_license_claim', 'not_clinical_ground_truth': True,
        'limitations': ['Core care rules and base decision variants are shared across splits.',
            'Source-template and support-condition combination separation is a narrow synthetic construction, not clinical or external generalization.',
            'Generation and deterministic scorer checks do not constitute live Groq evaluation.',
            'V1 executed records remain unchanged and are known-family regression evidence.']}
