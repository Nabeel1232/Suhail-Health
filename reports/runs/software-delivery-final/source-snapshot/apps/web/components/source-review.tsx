'use client';
import {useState} from 'react';
import {api,human,when,type Row} from '@/lib/api';
import {Badge,ErrorBox} from './ui';

function Facts({value,depth=0}:{value:unknown;depth?:number}):React.ReactNode {
  if(value===null||value===undefined)return <span className="muted">Not recorded</span>;
  if(typeof value==='boolean')return <span>{value?'Yes':'No'}</span>;
  if(typeof value!=='object')return <span>{String(value)}</span>;
  if(depth>=3)return <pre tabIndex={0} aria-label="Retained structured source facts">{JSON.stringify(value,null,2)}</pre>;
  if(Array.isArray(value))return value.length?<ul className="source-values">{value.map((item,i)=><li key={i}><Facts value={item} depth={depth+1}/></li>)}</ul>:<span className="muted">Empty list</span>;
  const entries=Object.entries(value);
  return entries.length?<dl className="source-facts">{entries.map(([key,item])=><div key={key}><dt>{human(key.replace(/([a-z])([A-Z])/g,'$1 $2'))}</dt><dd><Facts value={item} depth={depth+1}/></dd></div>)}</dl>:<span className="muted">No retained source facts</span>;
}

export function SourceReview({evidenceId}:{evidenceId:string}) {
  const [source,setSource]=useState<Row|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState('');
  async function read(){setLoading(true);setError('');try{setSource(await api(`/evidence/${encodeURIComponent(evidenceId)}/source`))}catch(e){setError(e instanceof Error?e.message:'The retained source could not be loaded.')}finally{setLoading(false)}}
  const content=source?.content;
  const document=content&&typeof content==='object'&&!Array.isArray(content)&&typeof content.document_text==='string'?content.document_text:null;
  const extra=content&&typeof content==='object'&&!Array.isArray(content)?Object.fromEntries(Object.entries(content).filter(([key])=>key!=='document_text')):null;
  return <details className="disclosure source-review" onToggle={e=>{if(e.currentTarget.open&&!source&&!loading&&!error)void read()}}><summary>Read retained source<span aria-hidden="true">＋</span></summary><div className="retained-source">{loading&&<p className="notice subtle" role="status">Loading retained source…</p>}{error&&<><ErrorBox message={error}/><button type="button" className="button secondary" disabled={loading} onClick={()=>void read()}>Try reading source again</button></>}{source&&<><p className="microcopy">Review the retained document and matching information before recording your verification decision.</p><div className="source-document">{document?<p>{document}</p>:<Facts value={content}/>}</div>{document&&extra&&Object.keys(extra).length>0&&<div className="source-extra"><h4>Additional retained facts</h4><Facts value={extra}/></div>}<h4>Source provenance</h4><dl className="source-facts source-provenance">{[['Reference',source.reference],['Source',human(source.source)],['Authority',human(source.authority)],['Patient / order',`${source.patient_id} / ${source.order_id}`],['Result version',source.result_version],['Effective time',when(source.effective_at)],['Retained at',when(source.artifact_received_at)],['Content hash',source.content_hash],['Case snapshot',`${source.case_id} · version ${source.case_version}`]].map(([label,value])=><div key={String(label)}><dt>{label}</dt><dd>{String(value??'Not recorded')}</dd></div>)}</dl><h4>Matching checks</h4><ul className="source-matching">{Object.entries(source.matching||{}).map(([key,value])=><li key={key}><span>{human(key)}</span><Badge tone={value===true?'success':value===false?'danger':'neutral'}>{value===true?'Matched':value===false?'Does not match':'Not recorded'}</Badge></li>)}</ul></>}</div></details>
}
