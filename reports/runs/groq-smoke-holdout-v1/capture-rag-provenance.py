"""Transparent late RAG capture verified against actual immutable provider inputs.

This repairs provenance, without changing model, prompts, source documents,
scoring, candidate outputs, original manifest hashes or executed call records.
"""
from pathlib import Path
import sys,json,shutil
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from evals.common import now,file_hash,digest,read_json,rows,Ledger,atomic_json
RUN=Path(__file__).resolve().parent
PACK=ROOT/'services/agents/knowledge.json'
DEST=RUN/'rag-provenance/knowledge-captured-late.json'
DEST.parent.mkdir(parents=True,exist_ok=True)
if not DEST.exists():shutil.copy2(PACK,DEST)
assert file_hash(DEST)==file_hash(PACK),'Knowledge pack changed after late capture; record a new version rather than overwriting.'
pack=read_json(DEST);docs={d['id']:d for d in pack['documents']}
ledger=Ledger(RUN/'rag-provenance/retrieval-lineage.jsonl');observed=set()
for r in rows(ledger.path):observed.update(r['document_ids'])
for call in rows(RUN/'provider-calls.jsonl'):
    if call['call_id'] in ledger.ids:continue
    contexts=[]
    for i,msg in enumerate(call.get('messages',[])):
        try:value=json.loads(msg.get('content') or '')
        except (ValueError,TypeError):continue
        if not isinstance(value,dict):continue
        if isinstance(value.get('retrieved_policy'),list):contexts.append({'location':f'messages[{i}].retrieved_policy','sections':value['retrieved_policy']})
        if msg.get('role')=='tool' and value.get('name')=='retrieve_policy' and isinstance(value.get('result'),list):contexts.append({'location':f'messages[{i}].tool.result','sections':value['result']})
    if not contexts:continue
    ids=[]
    for context in contexts:
        for section in context['sections']:
            original=dict(section);citation=original.pop('citation',None)
            assert original==docs.get(original.get('id')),'Actual earlier retrieved section differs from late-captured pack.'
            assert citation==original['id']+'#'+original['section'],'Citation metadata mismatch.'
            ids.append(original['id']);observed.add(original['id'])
    ledger.append({'case_id':call['call_id'],'provider_call_id':call['call_id'],'provider_case_id':call.get('metadata',{}).get('case_id'),'provider_record_hash':call['record_hash'],'actual_retrieved_context_hash':digest(contexts),'document_ids':sorted(set(ids)),'knowledge_pack_sha256':file_hash(DEST),'captured_at':now(),'verified_against_late_capture':True})
manifest=read_json(RUN/'manifest.json')
existing=read_json(RUN/'rag-provenance/erratum.json',{})
erratum={'id':'rag-provenance-erratum-v1','first_captured_at':existing.get('first_captured_at',now()),'last_validated_at':now(),'reason':'Original source allowlist omitted services/agents/knowledge.json; original retrieval_hash covered pathway files rather than the actual SQLiteFTS knowledge pack.','original_manifest_retrieval_hash':manifest.get('retrieval_hash'),'original_hash_scope':'pathway source files only; not an initial byte capture of the actual RAG pack','late_capture_path':str(DEST.relative_to(RUN)),'late_capture_sha256':file_hash(DEST),'actual_rag_snapshot_hash':digest(sorted(pack['documents'],key=lambda x:x['id'])),'pack_version':pack['version'],'observed_document_ids':sorted(observed),'all_pack_documents_observed_in_actual_provider_inputs':observed==set(docs),'verified_provider_context_records':len(rows(ledger.path)),'source_unchanged_claim':'Owner implementation agent reports knowledge pack unchanged since development validation. Independently every observed full section/metadata/citation is byte-content equivalent to this capture; actual provider inputs retain those sections and their original call hashes.','no_retroactive_initial_capture_claim':True,'no_model_prompt_scoring_output_or_original_ledger_change':True}
atomic_json(RUN/'rag-provenance/erratum.json',erratum)
print(json.dumps({'verified_provider_context_records':erratum['verified_provider_context_records'],'observed_documents':erratum['observed_document_ids'],'all_pack_documents_observed':erratum['all_pack_documents_observed_in_actual_provider_inputs'],'actual_rag_snapshot_hash':erratum['actual_rag_snapshot_hash']}))
