'use client';

import {createContext, useContext, useState, type FormEvent, type ReactNode} from 'react';
import {human, type Row} from '@/lib/api';
import {Icon} from './icon';

export const FormLanguage = createContext<'en' | 'ar'>('en');

export function Badge({children,tone='neutral'}:{children:ReactNode;tone?:string}) {
  return <span className={'badge '+tone}><span className="badge-dot" aria-hidden="true"/>{children}</span>;
}

export function StateBadge({state}:{state:unknown}) {
  const value=String(state||'pending');
  const tone=['completed','accepted','passed','attended','verified','delivered','completed_required_care','COMPLETE'].includes(value)?'success':
    ['blocked','rejected','overdue','no_show','failed','dead_letter','needs_help','urgent'].includes(value)?'danger':
    ['awaiting_external','pending','open','in_progress','PARTIAL'].includes(value)?'warning':'neutral';
  return <Badge tone={tone}>{human(value)}</Badge>;
}

export function Empty({title='No work here',children}:{title?:string;children?:ReactNode}) {
  return <div className="empty"><span className="empty-mark" aria-hidden="true"><Icon name="layers" size={24}/></span>
    <h3>{title}</h3><p>{children||'New activity will appear here when it is recorded.'}</p></div>;
}

export function ErrorBox({message}:{message:string}) {
  const ar = useContext(FormLanguage) === 'ar';
  const text = ar && !/\p{Script=Arabic}/u.test(message) ? 'تعذّر تسجيل هذا الإجراء. حاول مرة أخرى.' : message;
  return <div className="notice error" role="alert"><Icon name="alert-circle" size={19}/><div><strong>{ar ? 'يحتاج هذا الإجراء إلى مراجعة' : 'Action needs attention'}</strong><span>{text}</span></div></div>;
}

export function Panel({title,eyebrow,children,action,className='',id}:{title?:string;eyebrow?:string;children:ReactNode;action?:ReactNode;className?:string;id?:string}) {
  return <section id={id} tabIndex={id?-1:undefined} className={'panel '+className}>{(title||eyebrow)&&<div className="panel-heading"><div>
    {eyebrow&&<p className="eyebrow">{eyebrow}</p>}{title&&<h2>{title}</h2>}</div>{action}</div>}{children}</section>;
}

export function Field({label,name,type='text',required=true,defaultValue='',placeholder,options,help}:{label:string;name:string;type?:string;required?:boolean;defaultValue?:string|number;placeholder?:string;options?:Array<string|{value:string;label:string}>;help?:string}) {
  const ar = useContext(FormLanguage) === 'ar';
  return <label className="field"><span>{label}{!required&&<small>{ar ? ' اختياري' : ' Optional'}</small>}</span>
    {options?<select aria-label={label} name={name} defaultValue={defaultValue} required={required}>
      {options.map(option=>typeof option==='string'?<option key={option} value={option}>{human(option)}</option>:<option key={option.value} value={option.value}>{option.label}</option>)}
    </select>:type==='textarea'?<textarea aria-label={label} name={name} required={required} defaultValue={defaultValue} placeholder={placeholder} rows={3}/>:
      <input aria-label={label} type={type} name={name} required={required} defaultValue={defaultValue} placeholder={placeholder}/>}
    {help&&<small>{help}</small>}</label>;
}

export function ActionForm({children,onSubmit,label='Save',className='',disabled=false}:{children?:ReactNode;onSubmit:(data:Row)=>Promise<unknown>;label?:string;className?:string;disabled?:boolean}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[done,setDone]=useState(false);
  const ar = useContext(FormLanguage) === 'ar';
  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    if(busy)return;
    const values=Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true);setError('');setDone(false);
    try{await onSubmit(values);setDone(true)}
    catch(error){setError(error instanceof Error?error.message:'Action could not be recorded. Please try again.')}
    finally{setBusy(false)}
  }
  return <form className={'action-form '+className} onSubmit={submit} aria-busy={busy}>
    {children}{error&&<ErrorBox message={error}/>}
    <div className="form-footer"><button type="submit" disabled={busy||disabled} className="button">
      {busy&&<Icon name="loader" className="is-spinning" size={16}/>}<span>{busy ? ar ? 'جارٍ الحفظ…' : 'Saving…' : label}</span>
      {!busy&&<Icon name="arrow-up-right" className="button-arrow" size={16}/>}
    </button>{done&&<span role="status" className="success-text"><Icon name="check-circle" size={16}/>{ar ? 'تم التسجيل بنجاح' : 'Recorded successfully'}</span>}</div>
  </form>;
}

export function ActionButton({children,onClick,variant='',disabled=false}:{children:ReactNode;onClick:()=>Promise<unknown>;variant?:string;disabled?:boolean}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const ar = useContext(FormLanguage) === 'ar';
  return <><button className={'button '+variant} disabled={busy||disabled} onClick={async()=>{
    if(busy)return;setBusy(true);setError('');
    try{await onClick()}catch(error){setError(error instanceof Error?error.message:'Unable to record action')}finally{setBusy(false)}
  }}>{busy?<><Icon name="loader" className="is-spinning" size={16}/>{ar ? 'جارٍ الحفظ…' : 'Saving…'}</>:children}</button>{error&&<ErrorBox message={error}/>}</>;
}

export function Disclosure({title,children,open=false}:{title:string;children:ReactNode;open?:boolean}) {
  return <details className="disclosure" open={open||undefined}><summary>{title}<span aria-hidden="true"><Icon name="plus" size={17}/></span></summary><div className="disclosure-content">{children}</div></details>;
}
