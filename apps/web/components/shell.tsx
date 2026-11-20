'use client';

import Link from 'next/link';
import {usePathname,useRouter} from 'next/navigation';
import {createContext,useContext,useEffect,useMemo,useRef,useState} from 'react';
import {motion,useReducedMotion} from 'motion/react';
import {api,human,type User,type CareCase} from '@/lib/api';
import {ErrorBox} from './ui';
import {Icon} from './icon';
import {ContextChat} from './context-chat';

const Context=createContext<{user:User;demo:boolean}>({user:{id:'',name:'',role:'',organization:''},demo:false});
export const useSession=()=>useContext(Context);
export const roles=[
  {value:'navigator',label:'Care navigator',icon:'git-branch',description:'Coordinate follow-up, referrals and unfinished care.'},
  {value:'clinician',label:'Clinician',icon:'stethoscope',description:'Review patient questions, source evidence and care decisions.'},
  {value:'specialist',label:'Specialist',icon:'briefcase',description:'Respond to consultations with a documented human reply.'},
  {value:'receiver_a',label:'Provider A',icon:'building',description:'Review authorized referral packets and service requests.'},
  {value:'receiver_b',label:'Provider B',icon:'network',description:'Manage your service’s referrals, appointments and returned evidence.'},
  {value:'patient',label:'Patient',icon:'heart-pulse',description:'Understand the plan, ask questions and find practical help.'},
  {value:'admin',label:'Operations administrator',icon:'bar-chart-3',description:'Monitor delivery, recovery and measured workflow results.'},
];
export const roleHome=(role:string)=>role==='patient'?'/patient':role.startsWith('receiver')?'/receiving':['clinician','specialist'].includes(role)?'/clinical':role==='admin'?'/operations':'/worklist';
const navigation=[
  {href:'/worklist',title:'Care worklist',icon:'layout-dashboard',description:'Every case and its next step',roles:['navigator','clinician','specialist','admin']},
  {href:'/clinical',title:'Clinical workspace',icon:'stethoscope',description:'Questions, reviews and decisions',roles:['clinician','specialist']},
  {href:'/receiving',title:'Receiving service',icon:'network',description:'Referrals and appointments',roles:['receiver_a','receiver_b']},
  {href:'/patient',title:'My care plan',icon:'heart-pulse',description:'Your next step and care team',roles:['patient']},
  {href:'/operations',title:'Operations & impact',icon:'bar-chart-3',description:'Delivery, recovery and outcomes',roles:['admin','navigator']},
  {href:'/evaluation',title:'Evaluation reports',icon:'layers',description:'Measured software and agent results',roles:['admin']},
];

export function Shell({children}:{children:React.ReactNode}) {
  const [user,setUser]=useState<User|null>(null),[demo,setDemo]=useState(false),[error,setError]=useState('');
  const [switching,setSwitching]=useState(false),[searchOpen,setSearchOpen]=useState(false),[mobileOpen,setMobileOpen]=useState(false),[roleMenuOpen,setRoleMenuOpen]=useState(false);
  const pathname=usePathname(),router=useRouter(),reduce=useReducedMotion();
  const routerRef=useRef(router),roleExplorerTrigger=useRef<HTMLButtonElement>(null);
  useEffect(()=>{routerRef.current=router},[router]);
  useEffect(()=>{
    let current=true;
    api<User>('/auth/me').then(value=>{if(current)setUser(value)}).catch(()=>{if(current)routerRef.current.replace('/')});
    api('/auth/config').then(value=>{if(current)setDemo(!!value.demo_mode)}).catch(()=>{});
    return()=>{current=false};
  },[]);
  useEffect(()=>{setMobileOpen(false);setSearchOpen(false);setRoleMenuOpen(false)},[pathname]);
  useEffect(()=>{
    const key=(event:KeyboardEvent)=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setSearchOpen(value=>!value)}};
    window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);
  },[]);
  async function changeRole(role:string,fromExplorer=false) {
    if(switching)return;
    setRoleMenuOpen(false);
    if(role===user?.role)return;
    setSwitching(true);setError('');
    try{await api('/auth/demo',{role});const me=await api<User>('/auth/me');setUser(me);router.push(roleHome(me.role));router.refresh()}
    catch(error){setError(error instanceof Error?error.message:'Role change failed')}
    finally{setSwitching(false);if(fromExplorer)requestAnimationFrame(()=>roleExplorerTrigger.current?.focus())}
  }
  if(!user)return <div className="loading-screen"><img src="/brand/logo-original.png" alt="Suhail Health"/><span className="loading-orbit"><Icon name="heart-pulse" size={25}/></span><p role="status">Opening your secure workspace…</p><a href="/">Return to sign in</a></div>;
  const links=navigation.filter(item=>item.roles.includes(user.role));
  const current=navigation.find(item=>item.href===pathname);
  const allowed=pathname.startsWith('/cases/')?['navigator','clinician','specialist','admin'].includes(user.role):current?.roles.includes(user.role);
  const initials=user.name.split(' ').filter(Boolean).slice(0,2).map(name=>name[0]).join('');
  return <Context.Provider value={{user,demo}}>
    <a className="skip-link" href="#main">Skip to content</a>
    <div className="app-shell">
      <aside className="sidebar" data-mobile-open={mobileOpen}>
        <div className="sidebar-brand"><Link href={roleHome(user.role)} className="logo-tile" aria-label="Suhail Health home"><img src="/brand/logo-original.png" alt="Suhail Health"/><span className="sidebar-wordmark">Suhail<span>HEALTH</span></span></Link>
          <button className="mobile-nav-toggle icon-button" aria-label={mobileOpen?'Close navigation':'Open navigation'} aria-expanded={mobileOpen} aria-controls="workspace-navigation" onClick={()=>setMobileOpen(!mobileOpen)}><Icon name={mobileOpen?'x':'menu'} size={22}/></button>
        </div>
        <div className="sidebar-navigation" id="workspace-navigation"><p className="sidebar-label">YOUR WORKSPACE</p>
          <nav aria-label="Main navigation">{links.map(item=><Link key={item.href} href={item.href} className={'nav-item '+(pathname===item.href||(item.href==='/worklist'&&pathname.startsWith('/cases/'))?'active':'')} aria-current={pathname===item.href?'page':undefined}>
            <span className="nav-icon"><Icon name={item.icon} size={19}/></span><span>{item.title}</span><span className="nav-arrow"><Icon name="chevron-right" size={15}/></span>
          </Link>)}</nav>
          <button className="sidebar-search" onClick={()=>setSearchOpen(true)}><Icon name="search" size={17}/><span>Quick navigation</span><kbd>⌘ K</kbd></button>
        </div>
        <div className="sidebar-bottom"><div className="pathway-note"><span className="pathway-stars" aria-hidden="true">✦</span><span className="pathway-kicker">CONNECTED CARE</span><strong>Every result.<br/>A clearer next step.</strong><p>Colorectal screening<br/>follow-up pathway</p><div className="pathway-line"><i/><i/><i/><i/></div></div>
          <div className="user-card"><span className="avatar">{initials||'S'}</span><div><strong>{user.name}</strong><small>{roles.find(role=>role.value===user.role)?.label||human(user.role)}</small></div><button className="icon-button" title="Sign out" aria-label="Sign out" onClick={async()=>{await api('/auth/logout',{});router.push('/')}}><Icon name="log-out" size={18}/></button></div>
        </div>
      </aside>
      <div className="app-main"><header className="topbar"><div className="breadcrumb"><span className="breadcrumb-home"><Icon name="layers" size={16}/> Workspace</span><Icon name="chevron-right" size={13}/><strong>{current?.title||'Case journey'}</strong></div>
        <div className="topbar-right"><button className="topbar-search" aria-label="Search workspaces and cases" onClick={()=>setSearchOpen(true)}><Icon name="search" size={17}/><span>Search anything</span><kbd>⌘ K</kbd></button><span className="privacy-mark"><Icon name="shield" size={15}/> Private workspace</span>
          {demo&&<><label className="role-switch"><span>Synthetic demo role</span><select aria-label="Synthetic demo role" value={user.role} disabled={switching} onChange={event=>void changeRole(event.target.value)}>{roles.map(role=><option key={role.value} value={role.value}>{role.label}</option>)}</select></label><button ref={roleExplorerTrigger} type="button" className="demo-roles-trigger" aria-label="Explore demo roles" aria-haspopup="dialog" aria-expanded={roleMenuOpen} disabled={switching} onClick={()=>setRoleMenuOpen(true)}><Icon name={switching?'loader':'users'} size={16} className={switching?'is-spinning':undefined}/><span>Explore roles</span><Icon name="chevron-down" size={13}/></button>{switching&&<span className="sr-only" role="status">Switching your demonstration workspace…</span>}</>}
        </div>
      </header>
      {demo&&<div className="demo-banner"><span className="demo-banner-label"><span/> SYNTHETIC DEMO</span><p>Fictional patients. Connected workspaces. <span>Service windows are demonstration settings.</span></p><Icon name="info" size={15}/></div>}
      <motion.main key={pathname+':'+user.id+':'+user.role+':'+user.organization} id="main" className="workspace" initial={reduce?false:{opacity:0,y:9}} animate={{opacity:1,y:0}} transition={{duration:.28,ease:[.22,1,.36,1]}}>
        {error&&<ErrorBox message={error}/>}{allowed?children:<div className="panel restricted-panel"><Icon name="lock" size={28}/><h1>This workspace is restricted</h1><p>Your role does not have access to this workspace.</p><Link className="button" href={roleHome(user.role)}>Open my workspace <Icon name="arrow-right" size={16}/></Link></div>}
      </motion.main>
      <footer className="app-footer"><span><i/> SUHAIL HEALTH</span><span>Guiding every result to care.</span><span>Human oversight. Shared accountability.</span></footer>
      </div>
    </div>
    {searchOpen&&<QuickNavigation user={user} links={links} close={()=>setSearchOpen(false)}/>}
    {demo&&roleMenuOpen&&<DemoRoleExplorer currentRole={user.role} close={()=>setRoleMenuOpen(false)} choose={role=>void changeRole(role,true)}/>}
    <ContextChat key={user.id+':'+user.role+':'+user.organization+':'+(user.patient_id||'')} user={user}/>
  </Context.Provider>;
}

function DemoRoleExplorer({currentRole,close,choose}:{currentRole:string;close:()=>void;choose:(role:string)=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    const previous=document.activeElement instanceof HTMLElement?document.activeElement:null;
    dialog.current?.showModal();
    dialog.current?.querySelector<HTMLButtonElement>('[data-demo-role="'+currentRole+'"]')?.focus();
    return()=>{if(dialog.current?.open)dialog.current.close();requestAnimationFrame(()=>{if(previous?.isConnected)previous.focus()})};
  },[currentRole]);
  return <dialog ref={dialog} className="demo-roles-dialog" aria-labelledby="demo-roles-title" aria-describedby="demo-roles-description" onCancel={event=>{event.preventDefault();close()}} onClick={event=>{if(event.target===event.currentTarget)close()}}>
    <div className="demo-roles-surface"><header className="demo-roles-heading"><span className="demo-roles-symbol"><Icon name="users" size={23}/></span><div><p>ONE CONNECTED CARE JOURNEY</p><h2 id="demo-roles-title">Explore all {roles.length} demo roles</h2></div><button type="button" className="icon-button" aria-label="Close demo roles" onClick={close}><Icon name="x" size={19}/></button></header>
      <p id="demo-roles-description" className="demo-roles-description">For hospitals, clinics and organizations coordinating screening follow-up. Choose a role to open its workspace.</p>
      <ul className="demo-role-options" aria-label="Available demo roles" onKeyDown={event=>{
        const keys=['ArrowDown','ArrowRight','ArrowUp','ArrowLeft','Home','End'];if(!keys.includes(event.key))return;
        const buttons=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button[data-demo-role]'));
        const index=buttons.indexOf(document.activeElement as HTMLButtonElement);
        const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowUp'||event.key==='ArrowLeft'?-1:1)+buttons.length)%buttons.length;
        event.preventDefault();buttons[next]?.focus();
      }}>{roles.map(role=><li key={role.value}><button type="button" data-demo-role={role.value} aria-label={'Use '+role.label+' demo role'} aria-describedby={'demo-role-description-'+role.value} aria-current={role.value===currentRole?'true':undefined} onClick={()=>choose(role.value)}><span className="demo-role-icon"><Icon name={role.icon} size={21}/></span><span className="demo-role-copy"><strong>{role.label}</strong><small id={'demo-role-description-'+role.value}>{role.description}</small></span>{role.value===currentRole?<span className="demo-role-current"><Icon name="check" size={13}/>Current</span>:<Icon name="arrow-up-right" size={16}/>}</button></li>)}</ul>
      <footer className="demo-roles-footer"><span><Icon name="shield" size={14}/>Each role sees its authorized records.</span><span>Fictional patients · Synthetic demonstration</span></footer>
    </div>
  </dialog>;
}

type NavItem=typeof navigation[number];
function QuickNavigation({user,links,close}:{user:User;links:NavItem[];close:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null),input=useRef<HTMLInputElement>(null),router=useRouter();
  const [query,setQuery]=useState(''),[cases,setCases]=useState<CareCase[]>([]),[loading,setLoading]=useState(false),[error,setError]=useState(''),[active,setActive]=useState(0);
  useEffect(()=>{const previous=document.activeElement instanceof HTMLElement?document.activeElement:null;dialog.current?.showModal();input.current?.focus();if(['navigator','clinician','specialist','admin'].includes(user.role)){setLoading(true);api<CareCase[]>('/cases').then(setCases).catch(()=>setError('Cases could not be loaded. Your workspace links are still available.')).finally(()=>setLoading(false))}return()=>{requestAnimationFrame(()=>{if(previous?.isConnected)previous.focus()})}},[user.role]);
  const results=useMemo(()=>{
    const q=query.trim().toLowerCase();
    return [...links.filter(item=>(item.title+' '+item.description).toLowerCase().includes(q)).map(item=>({href:item.href,title:item.title,subtitle:item.description,icon:item.icon})),
      ...cases.filter(item=>q&&(item.id+' '+item.patient_name).toLowerCase().includes(q)).slice(0,7).map(item=>({href:'/cases/'+encodeURIComponent(item.id),title:item.patient_name,subtitle:item.id+' · '+human(item.disposition),icon:'user'}))];
  },[query,links,cases]);
  useEffect(()=>setActive(0),[query]);
  function dismiss(){dialog.current?.close();close()}
  function go(href:string){dismiss();router.push(href)}
  return <dialog ref={dialog} className="command-dialog" onCancel={event=>{event.preventDefault();dismiss()}} onClick={event=>{if(event.target===event.currentTarget)dismiss()}} aria-label="Quick navigation">
    <div className="command-surface"><div className="command-input"><Icon name="search" size={21}/><input ref={input} id="command-title" type="search" role="combobox" aria-label="Search workspaces and cases" aria-expanded="true" aria-controls="command-results" aria-activedescendant={results[active]?'command-result-'+active:undefined} placeholder="Find a workspace, patient or case…" value={query} onChange={event=>setQuery(event.target.value)} onKeyDown={event=>{
      if(event.key==='ArrowDown'){event.preventDefault();setActive(value=>(value+1)%Math.max(results.length,1))}
      if(event.key==='ArrowUp'){event.preventDefault();setActive(value=>(value-1+results.length)%Math.max(results.length,1))}
      if(event.key==='Enter'&&results[active]){event.preventDefault();go(results[active].href)}
    }}/><button className="icon-button" aria-label="Close quick navigation" onClick={dismiss}><Icon name="x" size={18}/></button></div>
    <p className="command-label">{query?'MATCHING RESULTS':'YOUR WORKSPACES'}</p><div className="command-results" id="command-results" role="listbox" aria-label="Navigation results">
      {results.map((result,index)=><button key={result.href} id={'command-result-'+index} role="option" aria-selected={active===index} className={active===index?'selected':''} onPointerMove={()=>setActive(index)} onClick={()=>go(result.href)}><span className="command-result-icon"><Icon name={result.icon} size={20}/></span><span><strong>{result.title}</strong><small>{result.subtitle}</small></span><Icon name="arrow-up-right" size={17}/></button>)}
      {!results.length&&<div className="command-empty">{loading?'Loading your authorized cases…':'No matching results. Try a patient name, case ID or workspace.'}</div>}
    </div>{error&&<p className="command-error">{error}</p>}<div className="command-footer"><span><kbd>↑</kbd><kbd>↓</kbd> to navigate <kbd>↵</kbd> to open</span><span><Icon name="shield" size={13}/> Your authorized records only</span></div></div>
  </dialog>;
}
