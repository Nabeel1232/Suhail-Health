export type Row = Record<string, any>;
export interface User {id:string; name:string; role:string; organization:string; patient_id?:string}
export interface CareCase extends Row {id:string;patient_id:string;patient_name:string;owner:string;version:number;milestones:Row[];tasks:Row[];communications:Row[];consultations:Row[];handoffs:Row[];appointments:Row[];evidence:Row[];escalations:Row[];audit:Row[]}
export async function api<T=Row>(path:string, body?:Row, method?:string):Promise<T> {
  const res = await fetch(`/api${path}`, {method:method || (body?'POST':'GET'), credentials:'include', headers: body?{'Content-Type':'application/json'}:{}, body:body?JSON.stringify(body):undefined,cache:'no-store'});
  let data:Row={}; try {data=await res.json();} catch {}
  if(!res.ok) { const detail=data.detail; const message=typeof detail==='string'?detail:detail?.message || (Array.isArray(detail)?detail.map((d:Row)=>`${d.loc?.at(-1)||'Field'}: ${d.msg}`).join('; '):detail?JSON.stringify(detail):`Request failed (${res.status})`); throw new Error(message); }
  return data as T;
}
export const envelope=(version:number)=>({expected_version:version,idempotency_key:crypto.randomUUID(),correlation_id:crypto.randomUUID()});
export const human=(s:unknown)=>String(s??'Not recorded').replaceAll('_',' ').replaceAll('-',' ');
export const when=(s:unknown,lang:'en-GB'|'ar-AE'='en-GB')=>s?new Intl.DateTimeFormat(lang,{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Dubai'}).format(new Date(String(s))):lang==='ar-AE'?'لم يُحدد':'Not set';
export function duration(hours: number): string {
  const totalMinutes = Math.max(0, Math.round(hours * 60));
  const totalHours = Math.floor(totalMinutes / 60);
  const days = Math.floor(totalHours / 24);
  const remainingHours = totalHours % 24;
  const minutes = totalMinutes % 60;
  if (days) return days + ' d' + (remainingHours ? ' ' + remainingHours + ' h' : '');
  if (totalHours) return totalHours + ' h' + (minutes ? ' ' + minutes + ' min' : '');
  return totalMinutes + ' min';
}
export function relative(due: unknown, now: unknown): string {
  const hours = (Date.parse(String(due)) - Date.parse(String(now))) / 3_600_000;
  if (!Number.isFinite(hours)) return '';
  if (!hours) return 'now';
  const elapsed = duration(Math.abs(hours));
  return hours < 0 ? elapsed + ' ago' : 'in ' + elapsed;
}
export const rows=(v:unknown):Row[]=>Array.isArray(v)?v:[];

export const needsUrgentReview=(c:Row):boolean=>!!c.urgent&&(rows(c.escalations).length===0||rows(c.escalations).some(e=>e.status?e.status==='care_team_review':!e.disposition));
