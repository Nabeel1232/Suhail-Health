'use client';

import {useEffect, useRef, useState, type KeyboardEvent} from 'react';
import {AnimatePresence, motion} from 'motion/react';
import {Icon} from '@/components/icon';

const frames = [
  {
    label: 'A result to explain', short: 'The result', icon: 'file-text', status: 'Follow-up needed',
    title: 'The next step has an owner.', action: 'Explain the follow-up assessment',
    caption: 'A screening result enters an owned care journey.',
    heading: 'A clear update for the patient',
    message: 'Your care team will explain the next assessment and help you arrange follow-up.',
    detail: 'Acknowledgement and understanding are recorded separately.',
  },
  {
    label: 'People to connect', short: 'The people', icon: 'message-circle', status: 'Human reply recorded',
    title: 'Questions reach the right person.', action: 'Coordinate the agreed next action',
    caption: 'A real conversation becomes an accountable next action.',
    heading: 'A question. A human response.',
    message: 'We can talk through your questions before the assessment. Your navigation team will coordinate the next step.',
    detail: 'The reply, agreed action, and responsible team stay together.',
  },
  {
    label: 'Care to follow through', short: 'The follow-through', icon: 'file-check', status: 'Evidence ready for review',
    title: 'Follow-through stays visible.', action: 'Review the documented care plan',
    caption: 'Care milestones are supported by their own source records.',
    heading: 'Evidence for the next decision',
    message: 'Attendance, the completed investigation, and the reviewed outcome each have a separate record.',
    detail: 'An authorized clinician makes the separate closure decision.',
  },
];

export function LandingVisual() {
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [reduced, setReduced] = useState(false);
  const controls = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    update(); query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!playing || reduced) return;
    const timer = window.setInterval(() => setActive(value => (value + 1) % frames.length), 6200);
    return () => window.clearInterval(timer);
  }, [playing, reduced]);

  const frame = frames[active];
  function selectFrame(index: number) {setActive(index); setPlaying(false);}
  function controlKey(event: KeyboardEvent<HTMLDivElement>) {
    if (!(event.target instanceof HTMLElement) || !event.target.closest('[data-preview-step]')) return;
    let next = active;
    if (event.key === 'ArrowRight') next = (active + 1) % frames.length;
    else if (event.key === 'ArrowLeft') next = (active + frames.length - 1) % frames.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = frames.length - 1;
    else return;
    event.preventDefault(); selectFrame(next);
    controls.current?.querySelectorAll<HTMLButtonElement>('[data-preview-step]')[next]?.focus();
  }
  return <div className="lp-visual-wrap">
    <div className="lp-orbit lp-orbit-one" aria-hidden="true"/><div className="lp-orbit lp-orbit-two" aria-hidden="true"/>
    <span className="lp-orbit-star" aria-hidden="true"><Icon name="sparkles" size={27} strokeWidth={1.1}/></span>
    <div className="lp-browser" aria-label="Illustrative synthetic care coordination preview">
      <div className="lp-browser-bar"><div className="lp-window-dots" aria-hidden="true"><i/><i/><i/></div><span><Icon name="lock" size={11}/>Suhail / care workspace</span><span className="lp-preview-tag">Synthetic preview</span></div>
      <div className="lp-mini-app">
        <aside className="lp-mini-nav" aria-hidden="true"><span className="lp-mini-symbol"><Icon name="sparkles" size={22}/></span><span><Icon name="grid" size={17}/></span><span className="lp-mini-nav-active"><Icon name="git-branch" size={18}/></span><span><Icon name="message-circle" size={18}/></span><span><Icon name="activity" size={18}/></span><span className="lp-mini-user">N</span></aside>
        <div className="lp-mini-main">
          <div className="lp-mini-breadcrumb"><span>Care worklist</span><Icon name="chevron-right" size={10}/><strong>Illustrative episode</strong></div>
          <div className="lp-mini-heading"><div><span className="lp-mini-eyebrow">SCREENING FOLLOW-UP</span><h3>A connected care journey</h3></div><span className="lp-mini-avatar"><Icon name="heart-pulse" size={20}/></span></div>
          <div className="lp-mini-owner"><span className="lp-mini-owner-icon"><Icon name="users" size={17}/></span><div><small>ACCOUNTABLE EPISODE OWNER</small><strong>Navigation team</strong></div><span className="lp-mini-owned"><i/>Assigned</span></div>
          <AnimatePresence mode="wait" initial={false}><motion.div className="lp-mini-stage" key={active}
            initial={reduced ? false : {opacity: 0, x: 10}} animate={{opacity: 1, x: 0}} exit={{opacity: 0, x: reduced ? 0 : -8}}
            transition={{duration: reduced ? 0 : .24, ease: [.22, 1, .36, 1]}}>
            <div className="lp-mini-stage-top"><span className="lp-mini-stage-icon"><Icon name={frame.icon} size={17}/></span><span>{frame.status}</span><Icon name="more-horizontal" size={18}/></div>
            <h4>{frame.title}</h4>
            <div className="lp-mini-track" aria-hidden="true">{[0,1,2].map(i => <span className={i <= active ? 'lp-track-done' : ''} key={i}><i>{i <= active ? <Icon name="check" size={10} strokeWidth={2.8}/> : null}</i><b/></span>)}</div>
            <div className="lp-mini-message"><div><Icon name={active === 1 ? 'stethoscope' : active === 2 ? 'clipboard-check' : 'message-circle'} size={14}/><strong>{frame.heading}</strong></div><p>{frame.message}</p></div>
            <div className="lp-mini-next"><small>NEXT ACTION</small><span>{frame.action}<Icon name="arrow-up-right" size={13}/></span></div>
          </motion.div></AnimatePresence>
          <p className="lp-mini-note"><Icon name="shield" size={12}/>{frame.detail}</p>
        </div>
      </div>
      <div ref={controls} className="lp-preview-controls" aria-label="Illustrative workflow stages" onKeyDown={controlKey}>{frames.map((item, i) => <button key={item.short} data-preview-step={i} type="button" onClick={() => selectFrame(i)} aria-pressed={active === i} aria-label={`Show ${item.short.toLowerCase()} preview`}>
        <span>0{i + 1}</span>{item.short}
        {active === i && <motion.i key={String(playing)} className="lp-step-timer" aria-hidden="true" initial={{scaleX: reduced || !playing ? 1 : 0}} animate={{scaleX: 1}} transition={{duration: playing && !reduced ? 6.2 : 0, ease: 'linear'}}/>}
      </button>)}{!reduced && <button type="button" className="lp-preview-play" onClick={() => setPlaying(value => !value)} aria-label={playing ? 'Pause illustrative preview' : 'Play illustrative preview'}>{playing ? <span className="lp-pause-glyph" aria-hidden="true"><i/><i/></span> : <Icon name="play" size={13}/>}</button>}</div>
    </div>
    <div className="lp-preview-caption"><span className="lp-caption-mark" aria-hidden="true"/><p>{frame.caption}<small>Illustrative synthetic example. No patient record is changed.</small></p></div>
    <div className="lp-float-note"><span><Icon name="shield" size={19}/></span><div><strong>Care has a human owner.</strong><small>Clinical decisions stay with the team.</small></div><Icon name="check" size={15}/></div>
  </div>;
}
