'use client';

import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {AnimatePresence, motion, useReducedMotion} from 'motion/react';
import {useEffect, useRef, useState, type FormEvent} from 'react';
import {type User} from '@/lib/api';
import {Icon} from './icon';
import {StateBadge} from './ui';

type Source = {id: string; label: string; href: string; case_id?: string; field?: string; version?: number};
type Card = {id: string; title: string; subtitle?: string; count?: number; status?: string; href?: string; fields?: {label: string; value: string | number | boolean | null}[]};
type Answer = {summary: string; mode: string; sources: Source[]; cards: Card[]; suggestions: string[]; metrics?: {label: string; value: number; definition?: string}[]; refreshed_at?: string; scope_label?: string};
type Message = {id: string; role: string; content: string; created_at: string; answer?: Answer};
type Conversation = {id: string; title: string; created_at: string; updated_at: string};
type WorkspaceContext = {actor: User; scope_label: string; suggestions: string[]; counts: {episodes?: number; open_tasks?: number; pending_requests?: number; urgent_reviews?: number}; mode: string; capabilities: string[]};
type Thread = {conversation: Conversation; messages: Message[]};
type Reply = {conversation_id: string; message: Message; user_message: Message; answer: Answer};

const allowedHref = (href?: string) => !!href && /^\/(?:worklist|cases\/[^/?#]+|clinical|receiving|patient|operations|evaluation)(?:[?#].*)?$/.test(href) && !href.startsWith('//');
const approvedPublicGuidance = new Set(['https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/colorectal-cancer-screening']);
const guidanceHref = (href?: string) => !!href && (/^\/api\/assistant\/knowledge\/[A-Za-z0-9._-]+$/.test(href) || approvedPublicGuidance.has(href));
const safeDecode = (value: string) => {try {return decodeURIComponent(value);} catch {return value;}};
const recordText = (value: unknown) => value === null || value === undefined || value === '' ? 'Not recorded' : typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : 'See the source record';

class AssistantRequestError extends Error {
  constructor(message: string, readonly status: number) {super(message);}
}
const scopeError = (error: unknown) => error instanceof AssistantRequestError && [401, 403, 404].includes(error.status);

function localTime(value: string | undefined, arabic: boolean, detailed = false) {
  if (!value || Number.isNaN(new Date(value).getTime())) return '';
  return new Intl.DateTimeFormat(arabic ? 'ar' : 'en-GB', detailed ? {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Dubai'} : {hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai'}).format(new Date(value));
}

export function ContextChat({user}: {user: User}) {
  const pathname = usePathname();
  const reduced = useReducedMotion();
  const dialog = useRef<HTMLDialogElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const feed = useRef<HTMLDivElement>(null);
  const priorFocus = useRef<HTMLElement | null>(null);
  const restoreFocus = useRef(true);
  const alive = useRef(true);
  const requests = useRef(new Set<AbortController>());
  const navigationTimers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const navigationGeneration = useRef(0);
  const generation = useRef(0);
  const contextGeneration = useRef(0);
  const openingGeneration = useRef(0);
  const sending = useRef(false);
  const draftRevision = useRef(0);
  const [open, setOpen] = useState(false);
  const [arabic, setArabic] = useState(false);
  const [context, setContext] = useState<WorkspaceContext | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState('');
  const [history, setHistory] = useState<Conversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingThread, setLoadingThread] = useState(false);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const patient = user.role === 'patient';
  const currentCase = pathname.startsWith('/cases/') ? safeDecode(pathname.split('/')[2] || '') : undefined;
  const copy = {
    title: arabic ? 'اسأل سهيل' : 'Ask Suhail',
    subtitle: arabic ? 'مساعد مساحة الرعاية' : 'Your care workspace assistant',
    placeholder: arabic ? 'اسأل عن خطوتك التالية أو فريق رعايتك…' : patient ? 'Ask about your next step or care team…' : 'Ask about your work, a patient, or a next step…',
    send: arabic ? 'إرسال الرسالة' : 'Send message',
    history: arabic ? 'المحادثات السابقة' : 'Conversation history',
    newChat: arabic ? 'محادثة جديدة' : 'New conversation',
    close: arabic ? 'إغلاق المساعد' : 'Close assistant',
  };

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      generation.current += 1;
      contextGeneration.current += 1;
      openingGeneration.current += 1;
      for (const controller of requests.current) controller.abort();
      requests.current.clear();
      for (const timer of navigationTimers.current) clearTimeout(timer);
      navigationTimers.current.clear();
    };
  }, []);

  useEffect(() => {
    if (!patient) return;
    const update = () => setArabic(document.querySelector('.patient-view')?.getAttribute('lang') === 'ar');
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['lang']});
    return () => observer.disconnect();
  }, [patient, pathname]);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'j') {
        event.preventDefault();
        setOpen(value => {
          if (!value) priorFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
          return !value;
        });
      }
    }
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, []);

  async function request<T>(path: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    requests.current.add(controller);
    try {
      const response = await fetch('/api' + path, {method: body === undefined ? 'GET' : 'POST', credentials: 'include', cache: 'no-store', signal: controller.signal, headers: body === undefined ? undefined : {'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body)});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 401) throw new AssistantRequestError('Your session has expired. Sign in again to continue.', 401);
        const message = typeof data.detail === 'string' ? data.detail : typeof data.detail?.message === 'string' ? data.detail.message : 'The assistant could not load this request. Please try again.';
        throw new AssistantRequestError(message, response.status);
      }
      return data as T;
    } finally {
      requests.current.delete(controller);
    }
  }

  function clearPrivateState() {
    generation.current += 1;
    contextGeneration.current += 1;
    openingGeneration.current += 1;
    for (const controller of requests.current) controller.abort();
    setContext(null); setMessages([]); setHistory([]); setConversationId(null); setInput('');
    setPending(false); setLoadingThread(false); setContextLoading(false);
    sending.current = false;
  }

  async function refreshHistory() {
    try {
      const result = await request<{conversations: Conversation[]}>('/assistant/conversations');
      if (alive.current) {setHistory(result.conversations); setHistoryError('');}
    } catch (error) {
      if (alive.current && scopeError(error)) clearPrivateState();
      if (alive.current && !(error instanceof DOMException && error.name === 'AbortError')) setHistoryError('Conversation history could not be loaded. Your current conversation is still available.');
    }
  }

  async function refreshContext() {
    const number = ++contextGeneration.current;
    setContextLoading(true);
    setContextError('');
    try {
      const result = await request<WorkspaceContext>('/assistant/context');
      if (alive.current && number === contextGeneration.current) {
        const actor = result.actor;
        if (actor.id !== user.id || actor.role !== user.role || actor.organization !== user.organization || (actor.patient_id || '') !== (user.patient_id || '')) {
          clearPrivateState();
          window.location.reload();
          return false;
        }
        setContext(result);
        return true;
      }
    } catch (error) {
      if (alive.current && number === contextGeneration.current && !(error instanceof DOMException && error.name === 'AbortError')) {
        if (scopeError(error)) clearPrivateState();
        setContext(null); setContextError(error instanceof Error ? error.message : 'Your workspace could not be loaded.');
      }
    } finally {
      if (alive.current && number === contextGeneration.current) setContextLoading(false);
    }
    return false;
  }

  useEffect(() => {
    if (!open) {
      if (dialog.current?.open) dialog.current.close();
      return;
    }
    restoreFocus.current = true;
    const opening = ++openingGeneration.current;
    const isCurrentOpening = () => alive.current && opening === openingGeneration.current;
    const restoreThread = conversationId;
    const restoreDraft = input;
    const openingDraftRevision = draftRevision.current;
    // Hide cached records until the current cookie identity and thread access
    // have been checked. A different tab may have changed the signed-in user.
    generation.current += 1;
    for (const controller of requests.current) controller.abort();
    sending.current = false;
    setMessages([]); setHistory([]); setInput(''); setConversationId(null); setPending(false);
    setLoadingThread(!!restoreThread);
    setArabic(document.querySelector('.patient-view')?.getAttribute('lang') === 'ar');
    if (!dialog.current?.open) dialog.current?.showModal();
    requestAnimationFrame(() => composer.current?.focus());
    void (async () => {
      try {
        if (!await refreshContext() || !isCurrentOpening()) return;
        await refreshHistory();
        if (!isCurrentOpening()) return;
        if (restoreThread) await loadConversation(restoreThread, true);
        if (isCurrentOpening() && draftRevision.current === openingDraftRevision) setInput(restoreDraft);
      } finally {
        if (isCurrentOpening()) {setLoadingThread(false); requestAnimationFrame(() => composer.current?.focus());}
      }
    })();
    return () => {
      openingGeneration.current += 1;
      if (dialog.current?.open) dialog.current.close();
      if (restoreFocus.current) requestAnimationFrame(() => {
        if (priorFocus.current?.isConnected && priorFocus.current !== document.body) priorFocus.current.focus();
        else launcher.current?.focus();
      });
    };
  // The actor is a component key in Shell; opening refreshes facts without discarding the user's thread.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    const element = composer.current;
    if (element) {element.style.height = 'auto'; element.style.height = Math.min(element.scrollHeight, 148) + 'px';}
  }, [input]);

  useEffect(() => {
    const element = feed.current;
    if (!open || !element) return;
    let top = messages.length || pending ? element.scrollHeight : 0;
    if (!pending && messages[messages.length - 1]?.role === 'assistant') {
      const users = element.querySelectorAll<HTMLElement>('.cc-user-message');
      const answers = element.querySelectorAll<HTMLElement>('.cc-assistant-message');
      const lastUser = users[users.length - 1];
      const anchor = lastUser && lastUser.offsetHeight < 120 ? lastUser : answers[answers.length - 1];
      if (anchor) top = anchor.getBoundingClientRect().top - element.getBoundingClientRect().top + element.scrollTop - 20;
    }
    element.scrollTo({top, behavior: reduced || !messages.length ? 'instant' : 'smooth'});
  }, [messages, pending, open, reduced]);

  function dismiss(navigating = false) {
    openingGeneration.current += 1;
    restoreFocus.current = !navigating;
    setOpen(false);
    setHistoryOpen(false);
  }

  function navigateRecord(href: string) {
    const destination = new URL(href, window.location.origin);
    const number = ++navigationGeneration.current;
    window.dispatchEvent(new CustomEvent('suhail:open-record', {detail: {href}}));
    dismiss(true);
    if (!destination.hash) return;
    let attempts = 0;
    function focusTarget() {
      if (!alive.current || number !== navigationGeneration.current || attempts++ > 80) return;
      const target = window.location.pathname === destination.pathname ? document.getElementById(safeDecode(destination.hash.slice(1))) : null;
      if (target) {
        if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
        target.scrollIntoView({block: 'start', behavior: 'instant'});
        target.focus({preventScroll: true});
      } else {
        const timer = setTimeout(() => {navigationTimers.current.delete(timer); focusTarget();}, 100);
        navigationTimers.current.add(timer);
      }
    }
    const timer = setTimeout(() => {navigationTimers.current.delete(timer); focusTarget();}, 100);
    navigationTimers.current.add(timer);
  }

  function newConversation() {
    if (sending.current) return;
    openingGeneration.current += 1;
    generation.current += 1;
    setConversationId(null); setMessages([]); setInput(''); setError(''); setHistoryOpen(false); setLoadingThread(false);
    requestAnimationFrame(() => composer.current?.focus());
  }

  async function loadConversation(id: string, opening = false) {
    if (sending.current) return;
    if (!opening) openingGeneration.current += 1;
    const number = ++generation.current;
    setLoadingThread(true); setHistoryOpen(false); setError('');
    try {
      if (!opening && (!await refreshContext() || !alive.current || number !== generation.current)) return;
      const result = await request<Thread>('/assistant/conversations/' + encodeURIComponent(id));
      if (alive.current && number === generation.current) {setConversationId(id); setMessages(result.messages); setInput('');}
    } catch (error) {
      if (alive.current && number === generation.current) {
        if (scopeError(error)) clearPrivateState();
        setError(error instanceof Error ? error.message : 'This conversation could not be loaded.');
      }
    } finally {
      if (alive.current && number === generation.current) setLoadingThread(false);
    }
  }

  async function send(question: string) {
    const text = question.trim();
    if (!text || sending.current || loadingThread) return;
    openingGeneration.current += 1;
    sending.current = true;
    const number = ++generation.current;
    const temporaryId = 'local-' + crypto.randomUUID();
    const sendingDraftRevision = draftRevision.current;
    setMessages(previous => [...previous, {id: temporaryId, role: 'user', content: text, created_at: new Date().toISOString()}]);
    setInput(''); setError(''); setPending(true); setHistoryOpen(false);
    let id = conversationId;
    try {
      if (!await refreshContext() || !alive.current || number !== generation.current) return;
      if (!id) {
        const created = await request<Thread>('/assistant/conversations', {title: text.slice(0, 80)});
        id = created.conversation.id;
        if (!alive.current || number !== generation.current) return;
        setConversationId(id);
      }
      const result = await request<Reply>('/assistant/conversations/' + encodeURIComponent(id) + '/messages', {message: text, ...(currentCase ? {context_case_id: currentCase} : {})});
      if (!alive.current || number !== generation.current) return;
      setMessages(previous => [...previous.filter(message => message.id !== temporaryId), result.user_message, {...result.message, answer: result.answer}]);
      void refreshContext().then(valid => {if (valid) void refreshHistory();});
    } catch (error) {
      if (alive.current && number === generation.current && !(error instanceof DOMException && error.name === 'AbortError')) {
        if (scopeError(error)) {
          clearPrivateState();
          setError(error instanceof Error ? error.message : 'This conversation is no longer available in your account scope.');
          return;
        }
        setMessages(previous => previous.filter(message => message.id !== temporaryId));
        if (draftRevision.current === sendingDraftRevision) setInput(text);
        setError(error instanceof Error ? error.message : 'The answer could not be completed. Try again.');
        // Re-read a persisted thread after an uncertain network outcome; do not repeat the request automatically.
        if (id) {
          try {const thread = await request<Thread>('/assistant/conversations/' + encodeURIComponent(id)); if (alive.current && number === generation.current) setMessages(thread.messages);} catch {}
        }
      }
    } finally {
      sending.current = false;
      if (alive.current && number === generation.current) {setPending(false); requestAnimationFrame(() => composer.current?.focus());}
    }
  }

  function submit(event: FormEvent) {event.preventDefault(); void send(input);}
  const fallbackPrompts = patient ? ['What is my next step?', 'Who is my care team?', 'What appointments do I have?'] : user.role.startsWith('receiver') ? ['How many requests do I have?', 'Which referrals need my response?', 'Show my appointments'] : ['How many requests need my attention?', 'Show cases needing urgent review', 'Which cases have missing evidence?'];
  const prompts = context?.suggestions?.length ? context.suggestions : fallbackPrompts;
  const latestAnswer = [...messages].reverse().find(message => message.role === 'assistant' && message.answer)?.answer;
  const followups = latestAnswer?.suggestions || [];

  return <>
    <button ref={launcher} type="button" className="cc-launcher" aria-label={copy.title} aria-haspopup="dialog" aria-expanded={open} onClick={() => {priorFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; setOpen(true);}} hidden={open}>
      <span className="cc-launcher-symbol"><Icon name="sparkles" size={21}/></span><span>{copy.title}<small>{arabic ? 'مساحة عملك، بوضوح' : 'Your workspace, connected'}</small></span><kbd>⌘ J</kbd>
    </button>
    <dialog ref={dialog} className="cc-dialog" aria-labelledby="context-chat-title" dir={arabic ? 'rtl' : 'ltr'} lang={arabic ? 'ar' : 'en'} onCancel={event => {event.preventDefault(); dismiss();}} onClick={event => {if (event.target === event.currentTarget) dismiss();}}>
      <motion.div className="cc-shell" initial={reduced ? false : {opacity: 0, x: 14}} animate={{opacity: 1, x: 0}} transition={{duration: .24}}>
        <header className="cc-header"><span className="cc-brand"><Icon name="sparkles" size={22}/></span><div><p>SUHAIL HEALTH</p><h2 id="context-chat-title">{copy.title}</h2><span>{copy.subtitle}</span></div><div className="cc-header-actions"><button type="button" className="cc-icon-button" title={copy.history} aria-label={copy.history} aria-expanded={historyOpen} aria-controls="context-chat-history" onClick={() => setHistoryOpen(value => !value)} disabled={pending}><Icon name="clock" size={18}/></button><button type="button" className="cc-icon-button" title={copy.newChat} aria-label={copy.newChat} onClick={newConversation} disabled={pending}><Icon name="plus" size={19}/></button><button type="button" className="cc-icon-button cc-close" aria-label={copy.close} onClick={() => dismiss()}><Icon name="x" size={21}/></button></div></header>
        <div className="cc-scope"><Icon name="shield" size={14}/><span>{context?.scope_label || (arabic ? 'السجلات المصرح لك بالوصول إليها فقط' : 'Your authorized workspace records only')}</span>{contextLoading ? <Icon name="loader" size={13} className="is-spinning"/> : context && <span className="cc-connected"><i/>{arabic ? 'متصل' : 'Connected'}</span>}</div>
        <AnimatePresence>{historyOpen && <motion.section id="context-chat-history" className="cc-history" aria-label={copy.history} initial={reduced ? false : {opacity: 0, height: 0}} animate={{opacity: 1, height: 'auto'}} exit={{opacity: 0, height: 0}}><div className="cc-history-heading"><h3>{copy.history}</h3><button type="button" onClick={newConversation}><Icon name="plus" size={14}/>{copy.newChat}</button></div>{historyError && <p className="cc-small-error">{historyError}</p>}{history.length ? <div className="cc-history-list">{history.map(thread => <button type="button" key={thread.id} className={thread.id === conversationId ? 'selected' : ''} onClick={() => void loadConversation(thread.id)}><Icon name="message-circle" size={17}/><span><strong>{thread.title}</strong><small>{localTime(thread.updated_at, arabic, true)}</small></span><Icon name="arrow-up-right" size={15}/></button>)}</div> : <p className="cc-history-empty">{arabic ? 'ستظهر محادثاتك المحفوظة هنا.' : 'Your saved conversations will appear here.'}</p>}</motion.section>}</AnimatePresence>
        <div className="cc-feed" ref={feed} role="log" aria-label={arabic ? 'رسائل المساعد' : 'Assistant messages'} aria-live="polite" aria-busy={pending || loadingThread}>
          {loadingThread ? <div className="cc-thread-loading" role="status"><Icon name="loader" className="is-spinning" size={22}/><p>{arabic ? 'جارٍ تحميل المحادثة…' : 'Opening your conversation…'}</p></div> : !messages.length ? <div className="cc-welcome"><div className="cc-welcome-art" aria-hidden="true"><span/><span/><span/><i><Icon name="sparkles" size={32}/></i></div><p className="cc-eyebrow">{arabic ? 'مساحة رعايتك، في محادثة واحدة' : 'ONE CONVERSATION. A CLEARER NEXT STEP.'}</p><h3>{arabic ? `مرحباً ${user.name.split(' ')[0]}` : `Hi ${user.name.split(' ')[0]},`}<br/>{arabic ? 'كيف يمكنني مساعدتك؟' : patient ? 'How can I help with your care?' : 'Where should we focus?'}</h3><p className="cc-welcome-intro">{arabic ? 'اسأل عن خطوتك التالية أو مواعيدك أو فريق الرعاية. تستند الإجابات إلى سجلاتك المصرح بها.' : patient ? 'Ask about your next step, appointments or care team. Answers link back to your care record.' : 'Find the work that needs you. Explore a patient’s journey. Open the right record, right from the answer.'}</p>
            {!patient && context?.counts && <div className="cc-workspace-counts">{[{key: 'episodes', label: 'Authorized episodes', question: 'How many episodes can I access?', icon: 'users'}, {key: 'open_tasks', label: 'Open tasks', question: 'Show my open tasks', icon: 'clipboard-check'}, {key: 'pending_requests', label: 'Pending requests', question: 'How many requests do I have?', icon: 'message-circle'}].filter(metric => typeof context.counts[metric.key as keyof WorkspaceContext['counts']] === 'number').map(metric => <button type="button" key={metric.key} onClick={() => void send(metric.question)}><Icon name={metric.icon} size={17}/><strong>{context.counts[metric.key as keyof WorkspaceContext['counts']]}</strong><span>{metric.label}</span></button>)}</div>}
            <div className="cc-suggestion-heading"><Icon name="message-square" size={15}/>{arabic ? 'يمكنك أن تسأل' : 'A few places to start'}</div><div className="cc-starter-prompts">{prompts.slice(0, 4).map((prompt, index) => <button type="button" key={prompt} onClick={() => void send(prompt)}><span className="cc-prompt-icon"><Icon name={['clipboard-check', 'users', 'calendar', 'file-text'][index]} size={17}/></span><span>{prompt}</span><Icon name="arrow-up-right" size={16}/></button>)}</div>
          </div> : <div className="cc-message-list">{messages.map(message => <MessageView key={message.id} message={message} arabic={arabic} navigate={navigateRecord}/>)}</div>}
          {contextError && <div className="cc-error" role="alert"><Icon name="alert-circle" size={17}/><span>{contextError}</span><button type="button" onClick={() => void refreshContext()}>{arabic ? 'حاول مجدداً' : 'Retry'}</button></div>}
          {pending && <div className="cc-thinking" role="status"><span className="cc-answer-symbol"><Icon name="sparkles" size={17}/></span><span><strong>{arabic ? 'جارٍ مراجعة سجلاتك المصرح بها…' : 'Checking your authorized records…'}</strong><small>{arabic ? 'البحث عن الحقائق والمصادر المرتبطة' : 'Finding the facts and their source records'}</small></span><Icon name="loader" size={16} className="is-spinning"/></div>}
          {error && <div className="cc-error" role="alert"><Icon name="alert-circle" size={18}/><span>{error}</span></div>}
          {!!messages.length && !pending && !!followups.length && <div className="cc-followups"><span>{arabic ? 'استكشف المزيد' : 'Keep exploring'}</span>{followups.slice(0, 3).map(prompt => <button type="button" key={prompt} onClick={() => void send(prompt)}>{prompt}<Icon name="arrow-right" size={14}/></button>)}</div>}
        </div>
        <div className="cc-composer-wrap">{currentCase && <div className="cc-current-context"><Icon name="link" size={12}/>{arabic ? 'السجل المعروض' : 'Viewing'}<strong>{currentCase}</strong><span>{arabic ? 'يمكنك السؤال عن سجل آخر مصرح به' : 'Ask about another authorized record at any time'}</span></div>}<form className="cc-composer" onSubmit={submit}><label className="sr-only" htmlFor="context-chat-question">{arabic ? 'سؤالك' : 'Your question'}</label><textarea id="context-chat-question" ref={composer} value={input} onChange={event => {draftRevision.current += 1; setInput(event.target.value);}} placeholder={copy.placeholder} rows={1} maxLength={2000} readOnly={loadingThread} aria-busy={loadingThread} onKeyDown={event => {if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {event.preventDefault(); void send(input);}}}/><button type="submit" aria-label={copy.send} disabled={!input.trim() || pending || loadingThread}>{pending ? <Icon name="loader" className="is-spinning" size={18}/> : <Icon name="arrow-up" size={20}/>}</button></form><p className="cc-composer-note"><Icon name="lock" size={12}/>{arabic ? 'للمساعدة فقط. لا تغيّر هذه المحادثة خطة رعايتك.' : patient ? 'Here to help. This conversation does not change your care plan.' : 'Read-only assistance. Your care team stays in control.'}<span>{input.length > 1800 ? `${input.length}/2000` : '↵'}</span></p></div>
      </motion.div>
    </dialog>
  </>;
}

function MessageView({message, arabic, navigate}: {message: Message; arabic: boolean; navigate: (href: string) => void}) {
  if (message.role === 'user') return <article className="cc-user-message"><p dir="auto">{message.content}</p><time dateTime={message.created_at}>{localTime(message.created_at, arabic)}</time></article>;
  const answer = message.answer;
  const modelAssisted = !!answer && ['live_groq', 'live_model', 'model_grounded', 'llm_grounded', 'model_assisted_records'].includes(answer.mode);
  const isGuidanceSource = (source: Source) => ['versioned_workflow_guidance', 'approved_workflow_guidance'].includes(source.field || '');
  const approvedGuidance = (href?: string) => guidanceHref(href) && !!answer?.sources?.some(source => isGuidanceSource(source) && source.href === href);
  return <article className="cc-assistant-message"><div className="cc-answer-heading"><span className="cc-answer-symbol"><Icon name="sparkles" size={17}/></span><strong>{arabic ? 'سهيل' : 'Suhail'}</strong><span>{arabic ? 'إجابة تستند إلى السجل' : modelAssisted ? 'AI-assisted record answer' : 'Record-grounded answer'}</span></div><p className="cc-answer-text" dir="auto">{answer?.summary || message.content}</p>
    {!!answer?.metrics?.length && <div className="cc-answer-metrics">{answer.metrics.filter(metric => typeof metric.value === 'number' && Number.isFinite(metric.value)).map((metric, index) => <div key={metric.label + index}><span><Icon name="bar-chart-3" size={15}/>{metric.label}</span><strong>{metric.value.toLocaleString(arabic ? 'ar' : 'en-GB')}</strong>{metric.definition && <p>{metric.definition}</p>}</div>)}</div>}
    {!!answer?.cards?.length && <div className="cc-answer-cards">{answer.cards.map((card, index) => {
      const content = <><div className="cc-card-top"><span className="cc-card-icon"><Icon name={typeof card.count === 'number' ? 'bar-chart-3' : 'file-text'} size={17}/></span>{card.status && <StateBadge state={card.status}/>} {(allowedHref(card.href) || approvedGuidance(card.href)) && <Icon name="arrow-up-right" size={16}/>}</div>{typeof card.count === 'number' && <strong className="cc-card-count">{card.count}</strong>}<h4 dir="auto">{card.title}</h4>{card.subtitle && <p dir="auto">{card.subtitle}</p>}{!!card.fields?.length && <dl>{card.fields.map((field, number) => <div key={field.label + number}><dt>{field.label}</dt><dd dir="auto">{recordText(field.value)}</dd></div>)}</dl>}{(allowedHref(card.href) || approvedGuidance(card.href)) && <span className="cc-card-open">{arabic ? approvedGuidance(card.href) ? 'اقرأ الإرشادات' : 'افتح السجل' : approvedGuidance(card.href) ? 'Read guidance' : 'Open record'}<Icon name="arrow-right" size={13}/></span>}</>;
      return allowedHref(card.href) ? <Link key={card.id || index} href={card.href!} onClick={event => {if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) navigate(card.href!);}} className="cc-answer-card">{content}</Link> : approvedGuidance(card.href) ? <a key={card.id || index} href={card.href} target="_blank" rel="noopener noreferrer" className="cc-answer-card">{content}</a> : <div key={card.id || index} className="cc-answer-card">{content}</div>;
    })}</div>}
    {!!answer?.sources?.length && <div className="cc-sources"><span><Icon name="link" size={12}/>{arabic ? 'المصادر' : 'Source records'}</span><div>{answer.sources.map((source, index) => allowedHref(source.href) ? <Link key={source.id + ':' + index} href={source.href} onClick={event => {if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) navigate(source.href);}} title={source.version ? `Record version ${source.version}` : undefined}><Icon name="file-check" size={12}/>{source.label}<Icon name="arrow-up-right" size={11}/></Link> : (isGuidanceSource(source) && approvedGuidance(source.href)) ? <a key={source.id + ':' + index} href={source.href} target="_blank" rel="noopener noreferrer"><Icon name="file-check" size={12}/>{source.label}<Icon name="arrow-up-right" size={11}/></a> : <span key={source.id + ':' + index}>{source.label}</span>)}</div></div>}
    <div className="cc-answer-freshness"><Icon name="shield" size={11}/><span>{answer?.scope_label || (arabic ? 'حسب صلاحيات وصولك' : 'Within your authorized access')}</span>{(answer?.refreshed_at || message.created_at) && <time dateTime={answer?.refreshed_at || message.created_at}>{arabic ? 'تم التحقق' : 'Checked'} {localTime(answer?.refreshed_at || message.created_at, arabic)}</time>}</div>
  </article>;
}
