'use client';

import {useState, type ReactNode} from 'react';
import {api, human, when, type Row} from '@/lib/api';
import {Icon} from './icon';
import {Badge, ErrorBox} from './ui';

function Facts({value, depth = 0}: {value: unknown; depth?: number}): ReactNode {
  if (value === null || value === undefined) return <span className="muted">Not recorded</span>;
  if (typeof value === 'boolean') return <span>{value ? 'Yes' : 'No'}</span>;
  if (typeof value !== 'object') return <span>{String(value)}</span>;
  if (depth >= 3) {
    return <pre tabIndex={0} aria-label="Retained structured source facts">{JSON.stringify(value, null, 2)}</pre>;
  }
  if (Array.isArray(value)) {
    return value.length
      ? <ul className="source-values">{value.map((item, index) => <li key={index}><Facts value={item} depth={depth + 1} /></li>)}</ul>
      : <span className="muted">Empty list</span>;
  }
  const entries = Object.entries(value);
  return entries.length ? (
    <dl className="source-facts">
      {entries.map(([key, item]) => (
        <div key={key}>
          <dt>{human(key.replace(/([a-z])([A-Z])/g, '$1 $2'))}</dt>
          <dd><Facts value={item} depth={depth + 1} /></dd>
        </div>
      ))}
    </dl>
  ) : <span className="muted">No retained source facts</span>;
}

function MatchingChecks({matching}: {matching: Row}) {
  return (
    <section className="care-source-checks">
      <h4><Icon name="clipboard-check" size={16} />Matching checks</h4>
      <ul className="source-matching">
        {Object.entries(matching).map(([key, value]) => (
          <li key={key}>
            <span className="care-matching-icon"><Icon name={value === true ? 'check-circle' : value === false ? 'alert-circle' : 'info'} size={16} /></span>
            <span>{human(key)}</span>
            <Badge tone={value === true ? 'success' : value === false ? 'danger' : 'neutral'}>
              {value === true ? 'Matched' : value === false ? 'Does not match' : 'Not recorded'}
            </Badge>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Provenance({source}: {source: Row}) {
  const facts = [
    ['Reference', source.reference],
    ['Source', human(source.source)],
    ['Authority', human(source.authority)],
    ['Patient / order', source.patient_id + ' / ' + source.order_id],
    ['Result version', source.result_version],
    ['Effective time', when(source.effective_at)],
    ['Retained at', when(source.artifact_received_at)],
    ['Content hash', source.content_hash],
    ['Case snapshot', source.case_id + ' · version ' + source.case_version],
  ];
  return (
    <section className="care-source-provenance-section">
      <h4><Icon name="shield" size={16} />Source provenance</h4>
      <dl className="source-facts source-provenance">
        {facts.map(([label, value]) => (
          <div key={String(label)} className={label === 'Content hash' || label === 'Reference' ? 'care-provenance-wide' : ''}>
            <dt>{label}</dt><dd>{String(value ?? 'Not recorded')}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function SourceReview({evidenceId}: {evidenceId: string}) {
  const [source, setSource] = useState<Row | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function read() {
    setLoading(true);
    setError('');
    try {
      setSource(await api('/evidence/' + encodeURIComponent(evidenceId) + '/source'));
    } catch (error) {
      setError(error instanceof Error ? error.message : 'The retained source could not be loaded.');
    } finally {
      setLoading(false);
    }
  }

  const content = source?.content;
  const document = content && typeof content === 'object' && !Array.isArray(content) &&
    typeof content.document_text === 'string' ? content.document_text : null;
  const extra = content && typeof content === 'object' && !Array.isArray(content)
    ? Object.fromEntries(Object.entries(content).filter(([key]) => key !== 'document_text')) : null;

  return (
    <details className="disclosure source-review care-source-review" onToggle={event => {
      if (event.currentTarget.open && !source && !loading && !error) void read();
    }}>
      <summary><span className="care-source-trigger"><Icon name="eye" size={16} />Read retained source</span><Icon name="chevron-down" size={16} /></summary>
      <div className="retained-source">
        {loading && <div className="care-source-loading" role="status"><span className="spinner" /><p>Loading retained source…</p></div>}
        {error && <>
          <ErrorBox message={error} />
          <button type="button" className="button secondary" disabled={loading} onClick={() => void read()}>
            <Icon name="refresh" size={15} />Try reading source again
          </button>
        </>}
        {source && <>
          <div className="care-source-review-intro">
            <span className="care-record-icon"><Icon name="file-text" size={20} /></span>
            <div><strong>Retained source record</strong><p className="microcopy">Review the retained document and matching information before recording your verification decision.</p></div>
          </div>
          {(source.status === 'superseded' || source.matching?.result_version_match === false) && (
            <div className="notice warning care-source-history"><Icon name="clock" size={16} /><span>Historical source · review its result version against the current case.</span></div>
          )}
          <div className="source-document care-source-document">
            <div className="care-document-label"><Icon name="file-text" size={15} />SOURCE CONTENT<Badge tone="neutral">Result v{source.result_version}</Badge></div>
            {document ? <p>{document}</p> : <Facts value={content} />}
          </div>
          {document && extra && Object.keys(extra).length > 0 && (
            <div className="source-extra"><h4>Additional retained facts</h4><Facts value={extra} /></div>
          )}
          <MatchingChecks matching={source.matching || {}} />
          <Provenance source={source} />
          <p className="care-source-audit-note"><Icon name="lock" size={13} />Source access is scoped to this case and recorded in the audit trail.</p>
        </>}
      </div>
    </details>
  );
}
