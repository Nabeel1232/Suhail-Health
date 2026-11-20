'use client';
import Link from 'next/link';
import {Icon} from '@/components/icon';
export default function WorkspaceError({reset}:{error:Error;reset:()=>void}){return <section className="panel restricted-panel"><Icon name="refresh" size={28}/><h1>Let’s try that again.</h1><p>This workspace could not be loaded. Your saved care records are retained.</p><div className="error-actions"><button className="button" onClick={reset}>Try loading again</button><Link className="button secondary" href="/worklist">Care worklist</Link></div></section>}
