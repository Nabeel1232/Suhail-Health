'use client';

import {useEffect, useRef, useState} from 'react';
import {AnimatePresence, motion, useReducedMotion, useScroll, useSpring} from 'motion/react';
import {useRouter} from 'next/navigation';
import {api, type User} from '@/lib/api';
import {roles, roleHome} from './shell';
import {ActionForm, Field} from './ui';
import {Icon} from './icon';
import {LandingVisual} from './landing-visual';
import '@/app/landing.css';

const viewpoints = [
  {id:'care', label:'Care teams', icon:'stethoscope', eyebrow:'NAVIGATORS · CLINICIANS · SPECIALISTS', title:'Know who owns the next step.', text:'A shared coordination record connects the source result, human conversations, and unfinished care. Every open action has a responsible team.', items:['Prioritize work that needs attention','Connect patient and specialist consultations','Review source evidence before closure'], panelTitle:'A shared plan. Clear responsibility.', records:[['Episode owner','Navigation team'],['Consultation','Human reply recorded'],['Next action','Coordinate the agreed follow-up']]},
  {id:'patient', label:'Patients', icon:'heart', eyebrow:'ENGLISH · العربية · MOBILE', title:'A plan you can understand.', text:'See what happens next, find your responsible team, and ask for help. Acknowledging a message and understanding the plan are separate steps.', items:['Read your next step in plain language','Ask a clinician a question','Share practical barriers and preferences'], panelTitle:'Your care team is here to help.', records:[['Responsible team','Care navigation'],['A question','Assigned to a clinician'],['Your preference','English or Arabic']]},
  {id:'receiving', label:'Receiving services', icon:'building', eyebrow:'FOCUSED REFERRAL COORDINATION', title:'A handoff that is explicit.', text:'Review the authorized referral packet, record an acceptance or rejection, and return appointment and care evidence to the coordination record.', items:['See the minimum authorized packet','Keep capacity, booking, and attendance distinct','Return evidence of completed care'], panelTitle:'The right information for the handoff.', records:[['Access','Authorized referral packet'],['Acceptance','Recorded by the destination'],['Source evidence','Returned for clinical review']]},
  {id:'operations', label:'Operations', icon:'activity', eyebrow:'VISIBILITY · RECOVERY · EVIDENCE', title:'Keep unresolved need in view.', text:'See delivery failures, waiting work, urgent acknowledgements, and defined outcome measures. Inspect the actual execution records behind evaluation reports.', items:['Find owned recovery work','Keep exceptions in the full denominator','Inspect run provenance and limitations'], panelTitle:'An operational view of follow-through.', records:[['Delivery','Retry and failure states visible'],['Accountability','Primary and backup queues'],['Reports','Actual measured run records']]},
];

export function Home() {
  const [demo, setDemo] = useState(false);
  const [viewpoint, setViewpoint] = useState(0);
  const pageRef = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const {scrollYProgress} = useScroll();
  const readingProgress = useSpring(scrollYProgress, {stiffness: 180, damping: 32});
  const router = useRouter();
  useEffect(() => {api('/auth/config').then(result => setDemo(!!result.demo_mode)).catch(() => {})}, []);
  useEffect(() => {
    const page = pageRef.current;
    if (!page || window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
    page.classList.add('lp-motion-ready');
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {if (entry.isIntersecting) {entry.target.classList.add('lp-visible');observer.unobserve(entry.target)}}), {threshold:0.12});
    page.querySelectorAll('.lp-reveal').forEach(element => observer.observe(element));
    return () => observer.disconnect();
  }, []);
  async function enter(body:Record<string, unknown>, path:string) {await api(path, body);const user = await api<User>('/auth/me');router.push(roleHome(user.role))}
  const perspective = viewpoints[viewpoint];

  return <div className="lp-page" ref={pageRef}>
    <motion.div className="lp-reading-progress" style={{scaleX: reduced ? scrollYProgress : readingProgress}} aria-hidden="true"/>
    <a className="lp-skip" href="#lp-main">Skip to content</a>
    <header className="lp-header"><div className="lp-header-inner">
      <a className="lp-brand" href="/" aria-label="Suhail Health home"><img src="/brand/logo-original.png" alt="Suhail Health"/><span>Screening to care<small>COORDINATION, CONNECTED.</small></span></a>
      <nav className="lp-header-nav" aria-label="Public navigation"><a href="#platform">The approach</a><a href="#people">Connected care</a><a href="#signin" className="lp-header-signin">Sign in<Icon name="arrow-up-right" size={16}/></a></nav>
    </div></header>

    <main id="lp-main">
      <section className="lp-hero">
        <div className="lp-hero-copy"><p className="lp-kicker"><span/>FOR HOSPITALS, CLINICS & SCREENING PROGRAMS</p><h1 aria-label="Guiding every result to care.">Guiding every<br/>result <em>to care.</em></h1><p className="lp-hero-description">A result is a beginning.<br className="lp-desktop-break"/> Keep the next step connected.</p><p className="lp-hero-body">Built for hospitals, clinics and organizations running screening programs. Suhail connects patient guidance, accountable teams and source evidence across follow-up.</p><ul className="lp-audience-strip" aria-label="Organizations Suhail supports"><li><Icon name="building" size={14}/>Hospitals</li><li><Icon name="stethoscope" size={14}/>Clinics</li><li><Icon name="users" size={14}/>Organizational screening</li></ul><div className="lp-hero-actions"><a className="lp-button" href="#signin">Open your workspace<Icon name="arrow-up-right" size={18}/></a><a className="lp-inline-link" href="#platform">Explore the approach<Icon name="arrow-down" size={15}/></a></div><div className="lp-hero-principles"><span><Icon name="shield" size={15}/>Human clinical decisions</span><span><Icon name="globe" size={15}/>English & Arabic</span></div></div>
        <LandingVisual/>
        <div className="lp-hero-foot"><span><Icon name="git-branch" size={14}/>Starting with colorectal screening follow-up</span><span>CLARITY FOR PEOPLE. CONTINUITY FOR CARE.<Icon name="arrow-down" size={13}/></span></div>
      </section>

      <section className="lp-approach" id="platform"><div className="lp-section-top lp-reveal"><p className="lp-kicker"><span/>THE SPACE BETWEEN A RESULT AND A PLAN</p><div><h2>Care moves forward<br/>when the next step is clear.</h2><p>Screening follow-up involves more than a reminder. Suhail keeps communication, people, and required evidence connected across the journey.</p></div></div><div className="lp-feature-grid">
        <article className="lp-feature lp-reveal"><div className="lp-feature-top"><span>01 / CLARITY</span><Icon name="message-circle" size={24}/></div><h3>A person.<br/>A clear next step.</h3><p>Plain-language updates, a separate understanding check, and a direct route to human help.</p><div className="lp-feature-detail"><span className="lp-feature-avatar">P</span><div><small>THE PATIENT CAN ASK</small><strong>“What happens next?”</strong></div><Icon name="arrow-up-right" size={17}/></div></article>
        <article className="lp-feature lp-reveal"><div className="lp-feature-top"><span>02 / ACCOUNTABILITY</span><Icon name="users" size={24}/></div><h3>A team.<br/>Clear responsibility.</h3><p>An accountable episode owner, owned tasks, and explicit acceptance when responsibility changes hands.</p><div className="lp-feature-detail"><span className="lp-feature-avatar lp-avatar-team"><Icon name="users" size={15}/></span><div><small>THE TEAM CAN SEE</small><strong>Who is responsible.</strong></div><Icon name="arrow-up-right" size={17}/></div></article>
        <article className="lp-feature lp-reveal"><div className="lp-feature-top"><span>03 / FOLLOW-THROUGH</span><Icon name="file-check" size={24}/></div><h3>A source.<br/>A supported decision.</h3><p>Keep referral, booking, attendance, investigation, and the declared care endpoint distinct.</p><div className="lp-feature-detail"><span className="lp-feature-avatar lp-avatar-evidence"><Icon name="check" size={16}/></span><div><small>THE RECORD CAN SHOW</small><strong>The evidence behind care.</strong></div><Icon name="arrow-up-right" size={17}/></div></article>
      </div></section>

      <section className="lp-people" id="people"><div className="lp-people-inner"><div className="lp-people-copy lp-reveal"><p className="lp-kicker"><span/>DIFFERENT ROLES. A CONNECTED JOURNEY.</p><h2>One shared purpose.<br/><em>Every point of view.</em></h2><p>Patients, care navigators, clinicians, specialists, receiving providers and operations teams each have a focused workspace. Shared records connect their work, with access following the signed-in role.</p><div className="lp-perspective-tabs" aria-label="Explore role perspectives">{viewpoints.map((item,i) => <button type="button" key={item.id} aria-pressed={viewpoint===i} onClick={() => setViewpoint(i)}><Icon name={item.icon} size={18}/>{item.label}<Icon name="arrow-up-right" size={15}/></button>)}</div></div>
      <div className="lp-role-story lp-reveal"><AnimatePresence mode="wait" initial={false}><motion.div className="lp-role-content" key={perspective.id}
        initial={reduced ? false : {opacity: 0, y: 9}} animate={{opacity: 1, y: 0}} exit={{opacity: 0, y: reduced ? 0 : -6}} transition={{duration: reduced ? 0 : .2}}>
        <div className="lp-role-story-heading"><span className="lp-role-symbol"><Icon name={perspective.icon} size={25}/></span><span>{perspective.eyebrow}</span></div><h3>{perspective.title}</h3><p>{perspective.text}</p><ul>{perspective.items.map(item => <li key={item}><Icon name="check" size={15}/>{item}</li>)}</ul><div className="lp-role-record"><div><span className="lp-role-record-dot"/><strong>{perspective.panelTitle}</strong><Icon name="more-horizontal" size={18}/></div>{perspective.records.map(([label,value]) => <dl key={label}><dt>{label}</dt><dd>{value}</dd></dl>)}<small>Illustrative synthetic example · Access follows the authenticated role.</small></div>
      </motion.div></AnimatePresence></div></div></section>

      <section className="lp-continuity lp-reveal" id="how-it-works"><div className="lp-continuity-title"><span className="lp-small-star"><Icon name="sparkles" size={27}/></span><p>Responsibility stays visible.<br/><strong>Even when care changes hands.</strong></p></div><div className="lp-continuity-copy"><p>The sending team remains accountable until the intended receiving service explicitly accepts the handoff. An accepted referral is a milestone. The required care endpoint still needs its own evidence.</p><a className="lp-inline-link" href="#signin">See the connected workspaces<Icon name="arrow-right" size={16}/></a></div></section>

      <section className="lp-access-section" id="signin"><div className="lp-access-inner"><div className="lp-access-copy lp-reveal"><p className="lp-kicker"><span/>YOUR SECURE WORKSPACE</p><h2>Care is a<br/>shared journey.</h2><p>Sign in to see your next step, respond to a question, or coordinate follow-up with your care team.</p><div className="lp-access-principles"><div><span><Icon name="lock" size={19}/></span><p><strong>Your role. Your view.</strong><small>Access is limited by your role and authorized care relationships.</small></p></div><div><span><Icon name="heart-pulse" size={20}/></span><p><strong>A human team behind the plan.</strong><small>Clinical decisions remain with authorized professionals.</small></p></div><div><span><Icon name="message-circle" size={19}/></span><p><strong>Care details stay inside.</strong><small>The default notification simulator sends no real patient messages.</small></p></div></div><span className="lp-access-line" aria-hidden="true"/></div>
      <div className="lp-auth-card lp-reveal"><div className="lp-auth-heading"><span className="lp-auth-icon"><Icon name="lock" size={22}/></span><span>AUTHORIZED ACCESS</span></div><h2>Welcome back</h2><p>Open your Suhail workspace.</p><ActionForm className="lp-auth-form" label="Sign in" onSubmit={data => enter(data,'/auth/login')}><Field name="email" label="Email address" type="email" placeholder="you@your-organization.org"/><Field name="password" label="Password" type="password"/></ActionForm><p className="lp-account-note">Account access is managed by your program administrator.</p>{demo&&<div className="lp-demo-entry"><div className="lp-demo-heading"><span><Icon name="play" size={13}/></span><h3>Explore the synthetic demonstration</h3></div><p>Fictional patients and simulated providers. No real patient messages are sent.</p><ActionForm className="lp-demo-form" label="Enter synthetic demo" onSubmit={data => enter(data,'/auth/demo')}><Field name="role" label="Demonstration role" defaultValue="navigator" options={roles}/></ActionForm></div>}</div></div></section>
    </main>
    <footer className="lp-footer"><div className="lp-footer-main"><a href="/" className="lp-footer-brand" aria-label="Suhail Health home"><img src="/brand/logo-original.png" alt="Suhail Health"/></a><div><p>Guiding every result <em>to care.</em></p><span>Screening to care coordination.</span></div><nav aria-label="Footer navigation"><a href="#platform">The approach</a><a href="#people">Connected care</a><a href="#signin">Sign in<Icon name="arrow-up-right" size={14}/></a></nav></div><div className="lp-footer-bottom"><span>SUHAIL HEALTH</span><span>Demonstration clinical content · Not clinically validated</span><a href="#lp-main">Back to top<Icon name="arrow-up" size={13}/></a></div></footer>
  </div>;
}
