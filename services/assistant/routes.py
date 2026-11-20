"""User-owned chat with fresh authorization on every context, turn and history read."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, func

from services.api.auth import require_actor, COOKIE
from services.api.db import get_db, now_iso
from services.api.domain import audit
from services.agents.retrieval import PACK_PATH, retrieve, PolicyReviewRequired
from .models import AssistantConversation, AssistantMessage
from .context import (load_scope, context_payload, render_answer, detect_intent, INTENTS,
                      UNSAFE, CLINICAL)
from .intent import classify, model_enabled
from services.agents.gateway import env_value
import re

router = APIRouter(prefix='/assistant', tags=['Workspace assistant'])


class ConversationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None, max_length=80)


class MessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=2000)
    context_case_id: str | None = Field(default=None, max_length=160)

    @field_validator('message')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Write a question to continue.')
        return value.strip()


def identity_matches(thread, actor):
    return thread.owner_id == actor['id'] and thread.owner_role == actor['role'] and \
        thread.organization == actor['organization'] and thread.patient_id == actor.get('patient_id')


def still_permitted(thread, scope):
    if not identity_matches(thread, scope.actor) or not set(thread.related_case_ids).issubset(scope.ids):
        return False
    dependencies = thread.access_dependencies or {}
    current = scope.dependencies
    return all(set(dependencies.get(key, [])).issubset(current.get(key, [])) for key in ['packets', 'consultations'])


def thread_for(db, ident, scope, lock=False):
    query = select(AssistantConversation).where(AssistantConversation.id == ident)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    thread = db.scalar(query)
    if not thread or not still_permitted(thread, scope):
        # No title, user question, source or stored answer is returned after a
        # scope change, even when another grant still exposes the same case.
        raise HTTPException(404, 'Conversation is not available in your current account scope.')
    return thread


def conversation_dict(thread):
    return {name: getattr(thread, name) for name in ['id', 'title', 'created_at', 'updated_at']}


def message_dict(message):
    payload = {name: getattr(message, name) for name in ['id', 'role', 'content', 'created_at']}
    if message.answer:
        payload['answer'] = message.answer
    return payload


@router.get('/context')
def context(actor=Depends(require_actor), db=Depends(get_db)):
    payload = context_payload(load_scope(db, actor))
    enabled = model_enabled()
    payload['model_assistance'] = {'enabled':enabled, 'status':'configured' if enabled else 'disabled',
        'model':env_value('GROQ_MODEL','openai/gpt-oss-120b') if enabled else None,
        'purpose':'Question interpretation only; current facts and counts are read from permitted records.'}
    return payload


@router.get('/conversations')
def conversations(actor=Depends(require_actor), db=Depends(get_db)):
    scope = load_scope(db, actor)
    records = db.scalars(select(AssistantConversation).where(AssistantConversation.owner_id == actor['id'])
        .order_by(AssistantConversation.updated_at.desc()).limit(100))
    return {'conversations': [conversation_dict(thread) for thread in records if still_permitted(thread, scope)]}


@router.post('/conversations')
def create_conversation(payload: ConversationInput | None = None, actor=Depends(require_actor), db=Depends(get_db)):
    scope = load_scope(db, actor)
    count = db.scalar(select(func.count()).select_from(AssistantConversation).where(AssistantConversation.owner_id == actor['id']))
    if count >= 200:
        raise HTTPException(429, 'Conversation storage limit reached. Use an existing conversation.')
    # Titles are generated from a bounded intent label, never copied from raw
    # patient text or a model. Initial dependencies protect even empty threads.
    thread = AssistantConversation(owner_id=actor['id'], owner_role=actor['role'],
        organization=actor['organization'], patient_id=actor.get('patient_id'),
        title='Care workspace conversation', related_case_ids=sorted(scope.ids),
        access_dependencies=scope.dependencies)
    db.add(thread); db.commit()
    return {'conversation': conversation_dict(thread), 'messages': []}


@router.get('/conversations/{conversation_id}')
def history(conversation_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    scope = load_scope(db, actor)
    thread = thread_for(db, conversation_id, scope)
    messages = db.scalars(select(AssistantMessage).where(AssistantMessage.conversation_id == thread.id)
        .order_by(AssistantMessage.sequence))
    return {'conversation': conversation_dict(thread), 'messages': [message_dict(m) for m in messages],
            'scope_label': scope.label, 'read_only': True}


@router.post('/conversations/{conversation_id}/messages')
async def post_message(conversation_id: str, payload: MessageInput, request: Request, actor=Depends(require_actor), db=Depends(get_db)):
    scope = load_scope(db, actor)
    thread = thread_for(db, conversation_id, scope)
    # No model sees a denied record reference. Clinical requests and prompt/key
    # injection attempts are handled by the deterministic boundary first.
    global_query = detect_intent(payload.message) == 'episodes' or bool(re.search(r'\b(?:workspace|overall|across|all\s+(?:cases|patients|requests|referrals)|my\s+(?:requests|workload|queue))\b|how many.*(?:i have|my)|كم.*لدي', payload.message, re.I))
    followup = detect_intent(payload.message) == 'ownership' or bool(re.search(r'\b(?:this\s+(?:case|patient|episode)|that\s+(?:case|patient)|its|their|her|his|same\s+(?:patient|case))\b|هذا|هذه|لهذا|لها|له', payload.message, re.I))
    supplied_context = None if global_query else payload.context_case_id
    initial, _, _ = render_answer(db, scope, payload.message, supplied_context)
    denied = initial['summary'].startswith('I could not find a matching record')
    if not denied and not UNSAFE.search(payload.message) and not CLINICAL.search(payload.message):
        db.rollback()  # never hold a transaction/clinical lock over a network wait
        plan = await classify(payload.message)
        db.expire_all()
        if request.cookies.get(COOKIE):
            # Session revocation or account role/organization changes during
            # inference take effect before any reply or history is persisted.
            actor = require_actor(request, db)
        scope = load_scope(db, actor)
        thread = thread_for(db, conversation_id, scope)
    else:
        plan = {'intent': detect_intent(payload.message), 'intelligence': {'status': 'not_requested', 'mode': 'record_grounding'}}
    thread = thread_for(db, conversation_id, scope, lock=True)
    previous = db.scalar(select(AssistantMessage).where(AssistantMessage.conversation_id == thread.id,
        AssistantMessage.role == 'assistant').order_by(AssistantMessage.sequence.desc()).limit(1))
    case_context = supplied_context or (previous.context_case_id if previous and followup and not global_query else None)
    answer, dependencies, focused = render_answer(db, scope, payload.message, case_context, plan['intent'])
    answer['intelligence'] = plan['intelligence']
    if plan['intelligence']['status'] == 'completed':
        answer['mode'] = 'model_assisted_records'
    # Persist only in assistant tables. Case/task/evidence/disposition versions
    # and clinical authority never change through a chat turn.
    count = db.scalar(select(func.count()).select_from(AssistantMessage).where(AssistantMessage.conversation_id == thread.id))
    if count >= 120:
        raise HTTPException(429, 'This conversation has reached its message limit. Start a new conversation.')
    user = AssistantMessage(conversation_id=thread.id, role='user', content=payload.message,
        sequence=count, context_case_id=focused)
    reply = AssistantMessage(conversation_id=thread.id, role='assistant', content=answer['summary'],
        answer=answer, sequence=count+1, context_case_id=focused)
    db.add_all([user, reply])
    thread.related_case_ids = sorted(set(thread.related_case_ids) | dependencies)
    current = scope.dependencies
    thread.access_dependencies = {key: sorted(set((thread.access_dependencies or {}).get(key, [])) | set(current[key])) for key in current}
    if count == 0:
        labels = {'episodes':'Your authorized episodes','requests':'Your current requests','appointments':'Recorded appointments','evidence':'Evidence and next decisions',
            'ownership':'Responsible care teams','urgent':'Urgent review work','overdue':'Overdue follow-up',
            'consultations':'Human consultation requests','knowledge':'Care workflow guidance','patient':'Find a permitted patient',
            'operations':'Operational recovery','tasks':'Owned follow-up tasks','overview':'Your care workspace'}
        thread.title = labels.get(plan['intent'], labels['overview'])
    thread.updated_at = now_iso()
    audit(db, actor, None, 'assistant_answer_read', {'conversation_id':thread.id,
        'answer_mode':answer['mode'], 'permitted_record_count':len(scope.records), 'clinical_state_changed':False})
    db.commit()
    return {'conversation_id':thread.id, 'message':message_dict(reply), 'user_message':message_dict(user), 'answer':answer}


@router.get('/knowledge/{document_id}')
def knowledge(document_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    scope = load_scope(db, actor)
    import json
    documents = json.loads(PACK_PATH.read_text())['documents']
    document = next((d for d in documents if d['id'] == document_id), None)
    if not document or (document['access_scope']=='staff' and (actor['role']=='patient' or scope.provider)):
        raise HTTPException(404, 'Guidance is not available in this account scope.')
    try:
        validated = retrieve('followup ownership help', language=document['language'],
            scope='public' if actor['role']=='patient' or scope.provider else 'staff', documents=[document])
    except PolicyReviewRequired:
        raise HTTPException(404, 'No current versioned guidance is available for this request.') from None
    return {key:validated[0][key] for key in ['id','authority','section','version','text','source','language','review_status']}
