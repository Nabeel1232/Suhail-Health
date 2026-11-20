"""Generate secret-free canonical record JSON Schema and TypeScript contracts."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.api import db

CLASSES=['Case','Task','Milestone','Communication','Consultation','Handoff','AccessGrant','Appointment','Evidence','SourceArtifact','Escalation','Disposition','AuditEvent','Outbox','SourceEvent','PatientExperience']
LIST_FIELDS={'delay_reasons','evidence_ids','events'}
OBJECT_FIELDS={'payload','provenance','detail','content'}
defs={}
ts=['// Generated from the authoritative persisted Python record types. Do not put credentials here.','export type CommandEnvelope = { expected_version: number; idempotency_key: string; correlation_id?: string };',"export type Role = 'patient'|'navigator'|'clinician'|'specialist'|'receiver_a'|'receiver_b'|'connector'|'admin';"]
for name in CLASSES:
    cls=getattr(db,name)
    props={};required=[];fields=[]
    for col in cls.__table__.columns:
        try:pytype=col.type.python_type
        except NotImplementedError:pytype=str
        kind='array' if col.name in LIST_FIELDS else 'object' if col.name in OBJECT_FIELDS else {str:'string',int:'integer',bool:'boolean',float:'number',dict:'object',list:'array'}.get(pytype,'string')
        schema={'type':[kind,'null'] if col.nullable else kind}
        if kind=='array':schema['items']={'type':'object'} if col.name=='events' else {'type':'string'}
        props[col.name]=schema
        if not col.nullable:required.append(col.name)
        t={'string':'string','integer':'number','number':'number','boolean':'boolean','object':'Record<string, unknown>','array':'Array<Record<string, unknown>>' if col.name=='events' else 'string[]'}[kind]
        fields.append('  '+col.name+': '+t+(' | null' if col.nullable else '')+';')
    defs[name]={'type':'object','properties':props,'required':required,'additionalProperties':False}
    ts.append('export interface '+name+'Record {\n'+'\n'.join(fields)+'\n}')
children={'tasks':'Task','milestones':'Milestone','communications':'Communication','consultations':'Consultation','handoffs':'Handoff','appointments':'Appointment','evidence':'Evidence','escalations':'Escalation','dispositions':'Disposition','audit':'AuditEvent','experience':'PatientExperience','access_grants':'AccessGrant'}
case_props={**defs['Case']['properties'],'phase':{'type':'string'},'next_action':{'type':'string'},'due_at':{'type':['string','null']},**{key:{'type':'array','items':{'$ref':'#/$defs/'+value}} for key,value in children.items()}}
defs['StaffCaseDetail']={'type':'object','properties':case_props,'required':list(case_props),'additionalProperties':True}
ts.append('export interface StaffCaseDetail extends CaseRecord {\n  phase: string;\n  next_action: string;\n  due_at: string | null;\n'+'\n'.join('  '+key+': '+value+'Record[];' for key,value in children.items())+'\n}')
ts.append('export interface ClosureCheck { allowed: boolean; missing: string[]; endpoint: string; policy_version: string; evidence_ids: string[]; case_id: string; version: number }')
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://suhail.invalid/contracts/canonical-records-v1','title':'Suhail canonical persisted coordination records','$defs':defs,'$ref':'#/$defs/StaffCaseDetail'}
out=ROOT/'contracts';out.mkdir(exist_ok=True)
(out/'canonical-records.schema.json').write_text(json.dumps(schema,indent=2))
(out/'canonical-records.ts').write_text('\n\n'.join(ts)+'\n')
print('Canonical JSON Schema and TypeScript contracts exported; credential/session records excluded.')
