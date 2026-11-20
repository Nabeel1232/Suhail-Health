'use client';

import {useEffect, useRef, useState} from 'react';
import {motion, useReducedMotion} from 'motion/react';
import {api, envelope, human, rows, when, needsUrgentReview, type CareCase, type Row} from '@/lib/api';
import {label} from '@/lib/labels';
import {useResource, LoadState, AppointmentList} from './care';
import {ActionButton, ActionForm, Badge, Empty, Field, FormLanguage, Panel} from './ui';
import {ExperienceSurvey} from './experience-survey';
import {Icon} from './icon';

type Language = 'en' | 'ar';
type PatientCommand = (path: string, body?: Row) => Promise<unknown>;

const words = {
  "en": {
    "eyebrow": "YOUR CARE, CONNECTED",
    "hello": "Hello",
    "intro": "Your next step, in one place.",
    "sub": "Your care team is here to guide you and answer your questions.",
    "lang": "العربية",
    "team": "Your responsible care team",
    "backup": "Backup team",
    "next": "What happens next",
    "context": "Your stool screening result needs follow-up. This result alone does not diagnose cancer. Your care team will explain the next assessment.",
    "contact": "Your care team will contact you within the demonstration service window shown below.",
    "ack": "Have you received your care-team update?",
    "ackText": "Let us know you have seen this message. We will check your understanding separately.",
    "ackButton": "I have received this update",
    "ackDone": "Thank you. Your acknowledgement is recorded.",
    "understand": "Is your next step clear?",
    "understandText": "Please answer both questions.",
    "understandButton": "Send my understanding",
    "nextQuestion": "What will you do next?",
    "nextWait": "Wait; nothing is needed from me",
    "nextArrange": "Arrange the follow-up assessment with my care team",
    "meaningQuestion": "What does this result mean?",
    "meaningDiagnosis": "It means I have cancer",
    "meaningFollowup": "It needs a follow-up test to find the cause; it is not a diagnosis",
    "unknown": "I am not sure",
    "passed": "Thank you — that is right. Your team will arrange the assessment.",
    "help": "That is okay. A member of your care team will call you to explain.",
    "messageChannel": "Secure message · simulated channel",
    "messageDelivered": "Delivered",
    "messageOriginal": "This message is shown in the language it was sent in.",
    "questions": "Questions for your clinician",
    "questionDesc": "Ask about your result or request a callback. An assigned clinician will reply here.",
    "questionLabel": "Your question or callback request",
    "ask": "Send to my clinician",
    "human": "Reply from your clinician",
    "waiting": "Waiting for your clinician to reply",
    "agreed": "Agreed next action",
    "owner": "Responsible team",
    "helpTitle": "What would make the next step easier?",
    "helpDesc": "Tell us about a barrier. Your team will arrange support or contact you about the available options.",
    "barrier": "What help do you need?",
    "detail": "Tell us more",
    "barrierButton": "Request support",
    "preferences": "Your communication preferences",
    "channel": "Available channel",
    "channelLabel": "Secure local notification simulator",
    "preferenceHelp": "In this demonstration, notifications are stored in a local simulator. Your care details remain inside this page.",
    "save": "Save preferences",
    "language": "Preferred language",
    "appointments": "Your appointments",
    "appointmentHelp": "Only appointments confirmed by the receiving service are shown as booked. A preferred time is a request, not a confirmed booking.",
    "preferred": "Preferred appointment times",
    "requestTimes": "Send preferred times",
    "times": "Days or times that work for you",
    "support": "Your support requests",
    "careComplete": "Your follow-up plan is documented.",
    "careCompleteDesc": "Your care team has recorded the required care endpoint. See your approved follow-up plan below and contact the team with questions.",
    "ongoing": "Further care is still being coordinated.",
    "ongoingDesc": "Your assessment needs onward follow-up. Your episode stays open until the required care endpoint is recorded.",
    "outcome": "Your documented care plan",
    "noOutcome": "Your team has not yet recorded a reviewed outcome. We will update this page when the next plan is approved.",
    "review": "Demonstration content. English and Arabic clinical wording has not had external clinical review.",
    "urgent": "Your result has been flagged for urgent staff review.",
    "urgentDesc": "Your clinical team is reviewing the trusted source flag. Use your care team’s established urgent contact route if you need urgent help.",
    "recovery": "Your appointment needs another step. Your care team has follow-up work assigned.",
    "disposition": "Recorded outcome",
    "due": "Next action due",
    "thread": "Your conversation",
    "you": "You",
    "notifyMissing": "Your team is preparing your first secure update. You can still ask for help below."
  },
  "ar": {
    "eyebrow": "رعايتك متصلة",
    "hello": "مرحباً",
    "intro": "خطوتك التالية في مكان واحد.",
    "sub": "فريق رعايتك هنا لإرشادك والإجابة عن أسئلتك.",
    "lang": "الإنجليزية",
    "team": "فريق الرعاية المسؤول عنك",
    "backup": "الفريق البديل",
    "next": "ماذا سيحدث بعد ذلك",
    "context": "تحتاج نتيجة فحص البراز إلى متابعة. هذه النتيجة وحدها لا تشخّص السرطان. سيشرح لك فريق رعايتك التقييم التالي.",
    "contact": "سيتواصل فريق رعايتك معك ضمن الفترة التجريبية الموضحة أدناه.",
    "ack": "هل استلمت تحديث فريق الرعاية؟",
    "ackText": "أخبرنا أنك اطلعت على الرسالة. سنتحقق من فهم الخطوة التالية بشكل منفصل.",
    "ackButton": "لقد استلمت هذا التحديث",
    "ackDone": "شكراً لك. تم تسجيل استلامك للرسالة.",
    "understand": "هل خطوتك التالية واضحة؟",
    "understandText": "يرجى الإجابة عن السؤالين.",
    "understandButton": "إرسال إجابتي",
    "nextQuestion": "ما الخطوة التالية المطلوبة منك؟",
    "nextWait": "الانتظار، لا يلزمني أي إجراء",
    "nextArrange": "ترتيب تقييم المتابعة مع فريق رعايتي",
    "meaningQuestion": "ماذا تعني هذه النتيجة؟",
    "meaningDiagnosis": "تعني أنني مصاب بالسرطان",
    "meaningFollowup": "تحتاج إلى فحص متابعة لمعرفة السبب، وليست تشخيصاً",
    "unknown": "لست متأكداً",
    "passed": "شكراً لك، هذا صحيح. سيرتب فريقك التقييم.",
    "help": "لا بأس. سيتصل بك أحد أعضاء فريق رعايتك للشرح.",
    "messageChannel": "رسالة آمنة · قناة تجريبية",
    "messageDelivered": "تم التسليم",
    "messageOriginal": "تظهر هذه الرسالة باللغة التي أُرسلت بها.",
    "questions": "أسئلة لطبيبك",
    "questionDesc": "اسأل عن نتيجتك أو اطلب مكالمة. سيرد طبيب مكلّف هنا.",
    "questionLabel": "سؤالك أو طلب الاتصال",
    "ask": "إرسال إلى طبيبي",
    "human": "رد من طبيبك",
    "waiting": "بانتظار رد طبيبك",
    "agreed": "الخطوة التالية المتفق عليها",
    "owner": "الفريق المسؤول",
    "helpTitle": "ما الذي يسهّل عليك الخطوة التالية؟",
    "helpDesc": "أخبرنا عن أي عائق. سيرتب فريقك الدعم أو يتواصل معك بشأن الخيارات المتاحة.",
    "barrier": "ما الدعم الذي تحتاجه؟",
    "detail": "أخبرنا بالمزيد",
    "barrierButton": "طلب الدعم",
    "preferences": "تفضيلات التواصل",
    "channel": "قناة التواصل المتاحة",
    "channelLabel": "محاكي إشعارات محلي آمن",
    "preferenceHelp": "في هذا العرض التجريبي، تُحفظ الإشعارات في محاكي محلي. تبقى تفاصيل رعايتك داخل هذه الصفحة.",
    "save": "حفظ التفضيلات",
    "language": "اللغة المفضلة",
    "appointments": "مواعيدك",
    "appointmentHelp": "تظهر المواعيد المؤكدة من الجهة المستقبلة فقط كحجز. الوقت المفضل طلب وليس حجزاً مؤكداً.",
    "preferred": "الأوقات المفضلة للموعد",
    "requestTimes": "إرسال الأوقات المفضلة",
    "times": "الأيام أو الأوقات المناسبة لك",
    "support": "طلبات الدعم الخاصة بك",
    "careComplete": "تم توثيق خطة متابعتك.",
    "careCompleteDesc": "سجّل فريق رعايتك الرعاية المطلوبة. راجع خطة المتابعة المعتمدة أدناه وتواصل مع الفريق إذا كانت لديك أسئلة.",
    "ongoing": "لا تزال متابعة الرعاية قيد التنسيق.",
    "ongoingDesc": "يحتاج تقييمك إلى متابعة إضافية. يبقى ملفك مفتوحاً حتى توثيق الرعاية المطلوبة.",
    "outcome": "خطة رعايتك الموثقة",
    "noOutcome": "لم يسجّل فريقك نتيجة تمت مراجعتها بعد. سنحدّث هذه الصفحة عند اعتماد الخطة التالية.",
    "review": "محتوى تجريبي. لم تخضع الصياغة الطبية باللغتين العربية والإنجليزية لمراجعة سريرية خارجية.",
    "urgent": "تم وضع علامة لمراجعة عاجلة من الفريق.",
    "urgentDesc": "يراجع فريقك الطبي العلامة الواردة من المصدر الموثوق. استخدم قناة التواصل العاجل المعتمدة لدى فريقك إذا احتجت مساعدة عاجلة.",
    "recovery": "يحتاج موعدك إلى خطوة إضافية. تم إسناد المتابعة لفريق رعايتك.",
    "disposition": "النتيجة المسجلة",
    "due": "موعد الإجراء التالي",
    "thread": "محادثتك",
    "you": "أنت",
    "notifyMissing": "يعدّ فريقك أول تحديث آمن لك. يمكنك طلب المساعدة أدناه."
  }
};

const dispositionCopy: Record<Language, Record<string, {title: string; description: string}>> = {
  "en": {
    "informed_decline": {
      "title": "Your decision is documented.",
      "description": "Your team has recorded your informed decline. Your remaining follow-up need stays visible. Contact your care team if you would like to discuss support or review your decision."
    },
    "unable_to_contact": {
      "title": "Your team is trying to reach you.",
      "description": "Your team recorded unsuccessful contact and an authorized handling decision. Follow-up care may still be needed. You can send a question or update your contact preference here."
    },
    "accepted_transfer_open": {
      "title": "Your care has a receiving team.",
      "description": "A transfer has been documented. Required downstream care remains open; your responsible team and next action are shown below."
    },
    "clinically_resolved": {
      "title": "Your clinician has documented a decision.",
      "description": "An authorized clinician recorded a clinical resolution. Review the documented plan and remaining care need below."
    },
    "other_exception": {
      "title": "Your team has documented a handling decision.",
      "description": "This category does not mean required care was completed. Review the remaining care need and contact your team for support."
    }
  },
  "ar": {
    "informed_decline": {
      "title": "تم توثيق قرارك.",
      "description": "سجّل فريقك قرار الرفض بعد التوضيح. تبقى احتياجات المتابعة ظاهرة. تواصل مع فريقك لمناقشة الدعم أو مراجعة قرارك."
    },
    "unable_to_contact": {
      "title": "يحاول فريقك التواصل معك.",
      "description": "سجّل فريقك تعذّر التواصل وقراراً معتمداً بشأن المتابعة. قد تظل هناك حاجة إلى الرعاية. يمكنك إرسال سؤال أو تحديث تفضيلات التواصل هنا."
    },
    "accepted_transfer_open": {
      "title": "أصبح لرعايتك فريق مستقبِل.",
      "description": "تم توثيق الإحالة. لا تزال الرعاية اللاحقة المطلوبة مفتوحة. يظهر الفريق المسؤول والخطوة التالية أدناه."
    },
    "clinically_resolved": {
      "title": "وثّق طبيبك قراراً بشأن رعايتك.",
      "description": "سجّل طبيب مخوّل قراراً طبياً. راجع الخطة الموثّقة واحتياجات الرعاية المتبقية أدناه."
    },
    "other_exception": {
      "title": "وثّق فريقك قراراً بشأن المتابعة.",
      "description": "لا تعني هذه الفئة اكتمال الرعاية المطلوبة. راجع احتياجات الرعاية المتبقية وتواصل مع فريقك لطلب الدعم."
    }
  }
};

type Words = typeof words.en;

const trackerSteps = [
  {en: 'Result ready', ar: 'النتيجة جاهزة', milestones: ['result_ingested']},
  {en: 'You are informed', ar: 'تم إبلاغك', milestones: ['notification', 'acknowledgement', 'understanding']},
  {en: 'Appointment arranged', ar: 'تم ترتيب الموعد', milestones: ['referral', 'appointment']},
  {en: 'Test done', ar: 'تم إجراء الفحص', milestones: ['attendance', 'investigation']},
  {en: 'Plan explained', ar: 'تم شرح الخطة', milestones: ['reviewed_outcome', 'patient_updated']},
];

function PatientTracker({c, language}: {c: CareCase; language: Language}) {
  const timeline = rows(c.timeline);
  const statuses = timeline.length ? timeline : rows(c.milestones);
  const documented = new Set(statuses.filter(item => item.status === 'completed').map(item => item.type));
  const firstOpen = trackerSteps.findIndex(step => !step.milestones.every(type => documented.has(type)));
  const current = firstOpen === -1 ? trackerSteps.length - 1 : Math.max(0, firstOpen - 1);
  return <section className="pt-tracker" aria-label={language === 'ar' ? 'تقدم رعايتك' : 'Your care journey'}>
    <ol>{trackerSteps.map((step, index) => <li key={step.en} aria-current={index === current ? 'step' : undefined} className={index < current ? 'is-documented' : undefined}>
      <span className="pt-tracker-dot" aria-hidden="true">{index < current && <Icon name="check" size={13}/>}</span>
      <span>{step[language]}</span>
    </li>)}</ol>
  </section>;
}

const delayArabic: Record<string, string> = {
  'barrier:transport': 'المواصلات',
  'barrier:timing': 'توقيت الموعد',
  'barrier:preferred_times': 'الأوقات المفضلة للموعد',
  'barrier:language': 'اللغة',
  'barrier:access': 'الوصول إلى الرعاية',
  'barrier:uncertainty': 'توضيح المعلومات',
  handoff_rejected: 'تعذّر قبول الإحالة',
  handoff_timeout: 'انتهت مهلة الرد على الإحالة',
  no_show: 'لم يتم حضور الموعد',
  cancelled: 'أُلغي الموعد',
  no_slots: 'لا تتوفر مواعيد',
  corrected_result: 'تم تصحيح النتيجة',
};

const residualArabic: Record<string, string> = {
  'Diagnostic follow-up pending': 'المتابعة التشخيصية قيد الانتظار',
  'New trusted urgent signal requires qualified clinical review': 'تحتاج العلامة العاجلة الجديدة إلى مراجعة الفريق الطبي',
  'Corrected result requires fresh clinical review and patient update': 'تحتاج النتيجة المصححة إلى مراجعة طبية جديدة وإبلاغك بالتحديث',
  'Treatment initiation or accepted surveillance endpoint remains open': 'لا يزال بدء العلاج أو اعتماد خطة المتابعة قيد التنسيق',
};

function PatientContact({language}: {language: Language}) {
  const ar = language === 'ar';
  return <Panel className="pt-contact">
    <span className="pt-care-icon"><Icon name="message-circle" size={20}/></span>
    <div>
      <p><strong>{ar ? 'تحدث مع فريق رعايتك:' : 'Talk to your care team:'}</strong> <bdi dir="ltr">800 000 000</bdi> {ar ? '(رقم تجريبي)' : '(demonstration number)'}</p>
      <p>{ar ? 'في الحالات الطارئة اتصل بالرقم' : 'In an emergency call'} <a href="tel:998">998</a>.</p>
    </div>
  </Panel>;
}

export function Patient() {
  const {data, error, loading, load} = useResource<Row[]>('/cases');
  const cases = rows(data);
  if (loading || error) return <LoadState loading={loading} error={error} retry={load}/>;
  if (!cases.length) return <Empty title="No care plan is available">Your care team will link your screening episode to this account.</Empty>;
  return <PatientCase id={cases[0].id}/>;
}

function PatientSections({language, complete, appointmentsLabel}: {language: Language; complete: boolean; appointmentsLabel: string}) {
  const [active, setActive] = useState('next-step');
  const nav = useRef<HTMLElement>(null);
  const reduced = useReducedMotion();
  const ar = language === 'ar';
  const sections = [
    {id: 'next-step', label: ar ? 'خطوتك التالية' : 'Your next step', icon: complete ? 'check' : 'arrow-right'},
    {id: 'patient-questions', label: ar ? 'اسأل فريقك' : 'Ask your team', icon: 'message-circle'},
    {id: 'patient-appointments', label: appointmentsLabel, icon: 'calendar'},
    {id: 'patient-plan', label: ar ? 'خطة رعايتك' : 'Your care plan', icon: 'file-check'},
  ];

  useEffect(() => {
    let frame = 0;
    const ids = ['next-step', 'patient-questions', 'patient-appointments', 'patient-plan'];
    function update() {
      frame = 0;
      const line = Math.min(window.innerHeight * .35, 240);
      let current = ids[0];
      for (const id of ids) {
        const element = document.getElementById(id);
        if (element && element.getBoundingClientRect().top <= line) current = id;
      }
      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 3) {
        const lastVisible = [...ids].reverse().find(id => {
          const element = document.getElementById(id);
          return element && element.getBoundingClientRect().top < window.innerHeight;
        });
        if (lastVisible) current = lastVisible;
      }
      setActive(current);
    }
    function schedule() { if (!frame) frame = window.requestAnimationFrame(update); }
    update();
    window.addEventListener('scroll', schedule, {passive: true});
    window.addEventListener('resize', schedule);
    return () => {window.cancelAnimationFrame(frame); window.removeEventListener('scroll', schedule); window.removeEventListener('resize', schedule);};
  }, [language, complete]);

  useEffect(() => {
    const element = nav.current;
    if (element && element.scrollWidth > element.clientWidth) {
      const selected = element.querySelector('[aria-current="location"]');
      if (!selected) return;
      const viewport = element.getBoundingClientRect();
      const item = selected.getBoundingClientRect();
      const inset = 8;
      const delta = item.left < viewport.left + inset ? item.left - viewport.left - inset
        : item.right > viewport.right - inset ? item.right - viewport.right + inset : 0;
      // Move only the horizontal navigation viewport. scrollIntoView can also
      // pull the entire page back to this navigation while a patient reads.
      if (delta) element.scrollBy({left: delta, behavior: reduced ? 'instant' : 'smooth'});
    }
  }, [active, reduced]);

  return <nav ref={nav} className="pt-section-nav pt-following-nav" aria-label={ar ? 'أقسام خطة الرعاية' : 'Your care plan sections'}>
    {sections.map(section => <a key={section.id} href={'#' + section.id} aria-current={active === section.id ? 'location' : undefined} onClick={() => setActive(section.id)}>
      <span><Icon name={section.icon} size={15}/></span>{section.label}
      {active === section.id && <motion.i className="pt-nav-current" layoutId="patient-current-section" transition={{duration: reduced ? 0 : .22}} aria-hidden="true"/>}
    </a>)}
  </nav>;
}

function PatientCase({id}: {id: string}) {
  const {data: c, error, loading, load} = useResource<CareCase>(`/cases/${id}`);
  const [language, setLanguage] = useState<Language>('en');

  useEffect(() => {
    if (c?.language === 'ar' || c?.language === 'en') setLanguage(c.language);
  }, [c?.language]);

  if (loading || error || !c) return <LoadState loading={loading} error={error} retry={load}/>;

  const ar = language === 'ar';
  const locale = ar ? 'ar-AE' : 'en-GB';
  const w = words[language];
  const documented = dispositionCopy[language][c.disposition];
  const complete = c.disposition === 'completed_required_care';
  const onward = !!c.requires_onward && !complete;
  const latest = rows(c.communications).at(-1);
  const patientQuestions = rows(c.consultations).filter(q => q.type === 'patient_to_clinician');
  const title = complete ? w.careComplete : documented ? documented.title : onward ? w.ongoing : w.intro;
  const description = complete ? w.careCompleteDesc : documented ? documented.description : onward ? w.ongoingDesc : w.sub;

  async function command(path: string, body: Row = {}) {
    await api(path, {...envelope(c!.version), ...body});
    await load();
  }

  return <FormLanguage.Provider value={language}><div className="patient-view pt-view" dir={ar ? 'rtl' : 'ltr'} lang={language}>
    <header className="pt-welcome">
      <div>
        <p className="eyebrow pt-eyebrow"><span className="pt-live-dot"/>{w.eyebrow}</p>
        <p className="pt-hello">{w.hello}{ar ? '، ' : ', '}<strong><bdi>{ar ? c.patient_name.replace(/\(synthetic\)$/i, '(تجريبي)') : c.patient_name}</bdi></strong></p>
        <h1>{title}</h1>
        <p className="pt-intro">{description}</p>
      </div>
      <ActionButton variant="secondary pt-language" onClick={async () => {
        const next = ar ? 'en' : 'ar';
        await command(`/cases/${id}/preferences`, {language: next, channel: c.channel || 'portal'});
        setLanguage(next);
      }}><Icon name="globe" size={17}/>{w.lang}</ActionButton>
    </header>

    <PatientTracker c={c} language={language}/>

    {needsUrgentReview(c) && <div className="notice error pt-alert">
      <Icon name="alert-circle" size={22}/><div><strong>{w.urgent}</strong><p>{w.urgentDesc}</p></div>
    </div>}
    {c.urgent && !needsUrgentReview(c) && <div className="notice subtle pt-alert">
      <Icon name="shield" size={21}/><div>
        <strong>{ar ? 'سجّل طبيبك قراراً بشأن العلامة الواردة من المصدر.' : 'Your clinician has recorded a decision on the source flag.'}</strong>
        <p>{ar ? 'تظل العلامة الأصلية محفوظة. راجع خطتك والخطوة التالية أدناه.' : 'The original flag stays on record. Review your documented plan and current next step below.'}</p>
      </div>
    </div>}

    <PatientSections language={language} complete={complete} appointmentsLabel={w.appointments}/>

    <div className="patient-grid pt-layout">
      <div className="patient-primary pt-primary">
        <section id="next-step" className="patient-next pt-next">
          <div className="pt-next-art" aria-hidden="true"><Icon name={complete ? 'check-check' : 'heart-pulse'} size={35}/></div>
          <p className="eyebrow">{w.next}</p>
          <h2>{complete ? w.careComplete : documented ? documented.title : onward ? w.ongoing : ar ? 'تواصل مع فريق الرعاية لترتيب تقييم المتابعة' : c.next_action || 'Speak with your care team'}</h2>
          <p className="pt-next-description">{complete ? w.careCompleteDesc : documented ? documented.description : w.context}</p>
          {!complete && !documented && <p className="pt-contact-window">{w.contact}</p>}
          <div className="pt-next-footer">
            <div className="pt-next-owner"><span className="pt-care-icon"><Icon name="users" size={20}/></span><div><small>{w.team}</small><strong>{label(c.owner, language)}</strong></div></div>
            {!complete && <div className="pt-next-due"><Icon name="clock" size={15}/><span><small>{w.due}</small><strong>{when(c.due_at, locale)}</strong></span></div>}
            {complete && <span className="pt-complete-label"><Icon name="check-circle" size={16}/>{ar ? 'سجّل فريقك الرعاية المطلوبة' : 'Required care recorded by your team'}</span>}
          </div>
        </section>

        {latest ? <PatientUpdate latest={latest} owner={c.owner} complete={complete} language={language} w={w} command={command}/> :
          <Panel className="pt-update"><div className="pt-inline-note"><Icon name="bell" size={21}/><p>{w.notifyMissing}</p></div></Panel>}

        <div id="patient-questions" className="pt-anchor">
          <Panel title={w.questions} eyebrow={ar ? 'نحن هنا للمساعدة' : 'A CONVERSATION WITH YOUR TEAM'} className="pt-questions" action={<span className="pt-panel-symbol"><Icon name="message-circle" size={20}/></span>}>
            <p className="panel-intro">{w.questionDesc}</p>
            {patientQuestions.length > 0 ? <div className="patient-thread pt-thread">
              {patientQuestions.map(q => <article key={q.id}>
                <div className="question-bubble pt-question"><small><Icon name="user" size={13}/>{w.you} · {when(q.created_at, locale)}</small><p dir="auto">{q.question}</p></div>
                {q.reply ? <div className="reply-bubble pt-reply">
                  <small><Icon name="stethoscope" size={14}/>{w.human}{!ar && <> · {human(q.human_author)}</>}</small><p dir="auto">{q.reply}</p>
                  <div className="pt-agreed-action"><strong><Icon name="check-circle" size={14}/>{w.agreed}</strong><p dir="auto">{q.agreed_action}</p><small>{w.owner}: {label(q.action_owner, language)}</small></div>
                </div> : <p className="waiting-reply pt-waiting"><Icon name="clock" size={14}/>{w.waiting} · {when(q.due_at, locale)}</p>}
              </article>)}
            </div> : <div className="pt-question-hint"><Icon name="heart" size={17}/><p>{ar ? 'يمكنك السؤال بكلماتك. سيجيب أحد أعضاء فريق رعايتك هنا.' : 'Use your own words. A member of your care team will reply here.'}</p></div>}
            <ActionForm label={w.ask} onSubmit={d => command('/consultations', {...d, case_id: id, type: 'patient_to_clinician', recipient: 'clinician'})}>
              <Field name="question" label={w.questionLabel} type="textarea"/>
            </ActionForm>
          </Panel>
        </div>

        <div id="patient-appointments" className="pt-anchor">
          <Panel title={w.appointments} eyebrow={ar ? 'خطط لخطوتك التالية' : 'MAKING THE NEXT STEP EASIER'} className="pt-appointments" action={<span className="pt-panel-symbol"><Icon name="calendar" size={20}/></span>}>
            <AppointmentList appointments={rows(c.appointments)} language={language}/>
            <p className="microcopy pt-appointment-note"><Icon name="info" size={15}/>{w.appointmentHelp}</p>
            {!complete && <details className="disclosure"><summary>{w.preferred}<Icon name="plus" size={17}/></summary><div className="pt-details-content">
              <ActionForm label={w.requestTimes} onSubmit={d => command(`/cases/${id}/barriers`, {barrier: 'preferred_times', detail: d.detail})}>
                <Field name="detail" label={w.times}/>
              </ActionForm>
            </div></details>}
          </Panel>
        </div>

        <div id="patient-plan" className="pt-anchor"><PatientCarePlan c={c} language={language} w={w}/></div>
      </div>

      <aside className="patient-aside pt-aside">
        <PatientContact language={language}/>
        <Panel title={w.team} className="pt-team" eyebrow={ar ? 'أنت لست وحدك' : 'HERE TO HELP YOU'}>
          <div className="pt-team-profile"><span className="pt-team-avatar"><Icon name="heart-pulse" size={27}/></span><div><strong>{label(c.owner, language)}</strong><span>{ar ? 'فريق رعايتك المسؤول' : 'Your accountable care team'}</span></div></div>
          <div className="pt-backup"><span>{w.backup}</span><strong>{label(c.backup_queue, language)}</strong></div>
          <a className="button secondary full" href="#care-help">{ar ? 'اطلب مساعدة فريقك' : 'Ask your care team for help'}<Icon name="arrow-up-right" size={16}/></a>
        </Panel>

        <div id="care-help" className="pt-anchor"><Panel title={w.helpTitle} className="pt-support" action={<span className="pt-panel-symbol"><Icon name="heart" size={19}/></span>}>
          <p className="panel-intro">{w.helpDesc}</p>
          <ActionForm label={w.barrierButton} onSubmit={d => command(`/cases/${id}/barriers`, d)}>
            <Field name="barrier" label={w.barrier} defaultValue="uncertainty" options={ar ? [
              {value: 'uncertainty', label: 'توضيح المعلومات'}, {value: 'transport', label: 'المواصلات'},
              {value: 'timing', label: 'توقيت الموعد'}, {value: 'language', label: 'اللغة'}, {value: 'access', label: 'الوصول إلى الرعاية'},
            ] : ['uncertainty', 'transport', 'timing', 'language', 'access']}/>
            <Field name="detail" label={w.detail} type="textarea"/>
          </ActionForm>
          {c.delay_reasons?.length > 0 && <div className="support-summary pt-support-history"><h3>{w.support}</h3>
            {c.delay_reasons.map((reason: string, i: number) => <p key={i}><Icon name="clock" size={13}/>{ar ? delayArabic[reason] || (reason.startsWith('overdue:') ? 'تأخر إجراء المتابعة' : 'تحتاج المتابعة إلى اهتمام فريق الرعاية') : label(reason)}</p>)}
          </div>}
        </Panel></div>

        <Panel title={w.preferences} className="pt-preferences" action={<span className="pt-panel-symbol"><Icon name="settings" size={18}/></span>}>
          <ActionForm label={w.save} onSubmit={d => command(`/cases/${id}/preferences`, d)}>
            <Field name="language" label={w.language} defaultValue={c.language || language} key={c.language || language} options={[{value: 'en', label: ar ? 'الإنجليزية' : 'English'}, {value: 'ar', label: 'العربية'}]}/>
            <Field name="channel" label={w.channel} defaultValue="portal" options={[{value: 'portal', label: w.channelLabel}]}/>
            <p className="microcopy">{w.preferenceHelp}</p>
          </ActionForm>
        </Panel>
        <ExperienceSurvey c={c} language={language} command={command}/>
        <p className="clinical-review-note pt-review-note"><Icon name="info" size={14}/>{w.review}</p>
      </aside>
    </div>
  </div></FormLanguage.Provider>;
}

function PatientMessage({latest, owner, language, w}: {latest: Row; owner: unknown; language: Language; w: Words}) {
  const sentAt = latest.delivered_at || latest.created_at;
  const messageLanguage = latest.language || language;
  return <article className="pt-team-message pt-message-bubble">
    <div className="pt-message-meta"><strong>{label(owner, language)}</strong><time dateTime={sentAt || undefined}>{when(sentAt, language === 'ar' ? 'ar-AE' : 'en-GB')}</time></div>
    <p lang={messageLanguage} dir={messageLanguage === 'ar' ? 'rtl' : 'ltr'}>{latest.body}</p>
    <div className="pt-message-channel"><span>{w.messageChannel}</span>{latest.delivery_status === 'delivered' && <span className="pt-message-delivered"><Icon name="check-check" size={15}/>{w.messageDelivered}</span>}</div>
  </article>;
}

function PatientUpdate({latest, owner, complete, language, w, command}: {latest: Row; owner: unknown; complete: boolean; language: Language; w: Words; command: PatientCommand}) {
  const ar = language === 'ar';
  return <Panel title={complete ? ar ? 'سجل التواصل مع فريق رعايتك' : 'Your care-team communication record' : w.ack} className="pt-update" eyebrow={ar ? 'تحديث فريق الرعاية' : 'A NOTE FROM YOUR CARE TEAM'} action={<span className="pt-panel-symbol"><Icon name={complete ? 'file-check' : 'mail'} size={20}/></span>}>
    {complete ? <>
      <p>{ar ? 'هذا سجل تحديث النتيجة السابق. اتبع خطة الرعاية المعتمدة الموضّحة أعلاه.' : 'This is the record of your earlier result update. Follow the approved care plan shown above.'}</p>
      <details className="disclosure"><summary>{ar ? 'عرض الرسالة السابقة' : 'View earlier result message'}<Icon name="plus" size={17}/></summary><div className="pt-details-content"><PatientMessage latest={latest} owner={owner} language={language} w={w}/></div></details>
    </> : <>
      <PatientMessage latest={latest} owner={owner} language={language} w={w}/>
      {latest.language && latest.language !== language && <small className="pt-language-note">{w.messageOriginal}</small>}
      <p className="muted">{w.ackText}</p>
    </>}
    {latest.acknowledged_at ? <div className="notice success pt-acknowledged" role="status"><Icon name="check-circle" size={18}/>{w.ackDone}</div> : !complete && <ActionButton onClick={() => command(`/communications/${latest.id}/acknowledgement`)}><Icon name="check" size={17}/>{w.ackButton}</ActionButton>}
    <div className={'patient-understanding pt-understanding' + (complete ? '' : ' pt-teachback')}>
      {complete ? <>
        <h3>{ar ? 'سجل فهم الخطوة التالية' : 'Recorded understanding'}</h3>
        <p className="notice subtle">{latest.understanding === 'passed' ? ar ? 'تم تأكيد فهمك. احتُفظ بنتيجة التحقق من الفهم في سجل رعايتك.' : 'Your understanding was confirmed. The check is retained in your care record.' : latest.understanding === 'needs_help' ? ar ? 'تم طلب التوضيح وسجّل فريقك المتابعة المطلوبة.' : 'Help was requested and your team documented the required follow-up.' : ar ? 'راجع فريق رعايتك للاطلاع على سجل التحقق من الفهم.' : 'See your care team for the recorded understanding check.'}</p>
      </> : <>
        <div className="pt-understanding-heading"><span className="pt-small-symbol"><Icon name="message-circle" size={18}/></span><div><h3>{w.understand}</h3>{latest.understanding !== 'passed' && <p>{w.understandText}</p>}</div></div>
        {latest.understanding === 'passed' ? <p className="notice success" role="status">{w.passed}</p> : <>
          {latest.understanding === 'needs_help' && <p className="notice subtle" role="status">{w.help}</p>}
          <ActionForm key={latest.id} label={w.understandButton} onSubmit={({next_step, meaning}) => command(`/communications/${latest.id}/understanding`, {
            outcome: next_step === 'arrange_followup' && meaning === 'needs_followup' ? 'passed' : 'needs_help',
            answers: {next_step, meaning},
          })}>
            <fieldset className="pt-teachback-question"><legend>{w.nextQuestion}</legend>
              {[['wait', w.nextWait], ['arrange_followup', w.nextArrange], ['unsure', w.unknown]].map(([value, text]) => <label key={value}><input type="radio" name="next_step" value={value} required/><span>{text}</span></label>)}
            </fieldset>
            <fieldset className="pt-teachback-question"><legend>{w.meaningQuestion}</legend>
              {[['diagnosis', w.meaningDiagnosis], ['needs_followup', w.meaningFollowup], ['unsure', w.unknown]].map(([value, text]) => <label key={value}><input type="radio" name="meaning" value={value} required/><span>{text}</span></label>)}
            </fieldset>
          </ActionForm>
        </>}
      </>}
    </div>
  </Panel>;
}

function PatientCarePlan({c, language, w}: {c: CareCase; language: Language; w: Words}) {
  const ar = language === 'ar';
  const reviewed = rows(c.evidence).filter(e => e.type === 'reviewed_outcome' && ['verified', 'accepted'].includes(e.verification || e.status));
  const dispositionLabels: Record<string, string> = {
    open: 'المتابعة مستمرة', completed_required_care: 'اكتملت الرعاية المطلوبة', clinically_resolved: 'تم توثيق القرار الطبي',
    accepted_transfer_open: 'تم قبول الإحالة والمتابعة مستمرة', informed_decline: 'تم تسجيل قرار الرفض بعد التوضيح',
    unable_to_contact: 'تعذّر التواصل', other_exception: 'تم توثيق إجراء استثنائي',
  };
  return <Panel title={w.outcome} className="pt-care-plan" eyebrow={ar ? 'موثّقة من فريقك' : 'DOCUMENTED BY YOUR TEAM'} action={<span className="pt-panel-symbol"><Icon name="file-check" size={20}/></span>}>
    {c.residual_need && <div className="notice warning"><strong>{ar ? 'احتياجات الرعاية المتبقية' : 'Remaining care need'}</strong><p dir="auto">{ar ? residualArabic[c.residual_need] || c.residual_need : c.residual_need}</p></div>}
    {c.care_plan ? <div className="pt-approved-plan"><p dir="auto">{c.care_plan.summary || c.care_plan.reference}</p><small><Icon name="shield" size={14}/>{ar ? 'السجل المعتمد من فريقك' : human(c.care_plan.source) + ' · ' + human(c.care_plan.approved_by)}</small></div> : reviewed.length ? reviewed.map(e => <div key={e.id} className="pt-approved-plan"><p dir="auto">{e.summary || e.reference}</p><small><Icon name="shield" size={14}/>{ar ? 'السجل المعتمد من فريقك' : 'Verified record from your team · ' + human(e.source)}</small></div>) : <div className="pt-plan-pending"><span><Icon name="file-text" size={25}/></span><p>{w.noOutcome}</p></div>}
    <div className="pt-disposition"><span>{w.disposition}</span><Badge tone={c.disposition === 'completed_required_care' ? 'success' : 'neutral'}>{ar ? dispositionLabels[c.disposition] || human(c.disposition) : human(c.disposition)}</Badge></div>
  </Panel>;
}
