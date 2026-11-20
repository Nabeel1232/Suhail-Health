'use client';

import {useState} from 'react';
import {api, type Row} from '@/lib/api';
import {Icon} from './icon';
import {ActionForm, Disclosure, Field} from './ui';

export function FileIntake({refresh}: {refresh: () => Promise<unknown>}) {
  const [content, setContent] = useState('');
  const [filename, setFilename] = useState('');
  const [format, setFormat] = useState('json');

  return (
    <div className="care-file-intake">
      <Disclosure title="Import a synthetic source file">
        <div className="care-intake-intro">
          <span className="care-record-icon"><Icon name="upload" size={21} /></span>
          <div><strong>Bring the source into the care ledger</strong><p className="microcopy">Accepts a validated JSON array or CSV of synthetic result events. All uploaded results enter owned source reconciliation before patient contact. File intake does not verify clinical authenticity.</p></div>
        </div>
        <label className={'field care-file-picker' + (filename ? ' has-file' : '')}>
          <span className="care-upload-icon"><Icon name={filename ? 'file-check' : 'upload'} size={25} /></span>
          <span>Synthetic JSON or CSV file</span>
          <small>{filename || 'Choose a file to validate before importing'}</small>
          <span className="care-file-formats" aria-hidden="true">JSON <span>·</span> CSV</span>
          <input type="file" aria-label="Synthetic JSON or CSV file" accept=".json,.csv,application/json,text/csv" onChange={async event => {
            const file = event.target.files?.[0];
            if (!file) return;
            setContent(await file.text());
            setFilename(file.name);
            setFormat(file.name.endsWith('.csv') ? 'csv' : 'json');
          }} />
        </label>
        {filename && <p className="care-selected-file"><Icon name="file-check" size={15} />Ready to validate: <strong>{filename}</strong></p>}
        <ActionForm label="Validate and import for reconciliation" disabled={!content} onSubmit={async (data: Row) => {
          await api('/integrations/files/intake', {format: data.format, content});
          await refresh();
        }}>
          <Field name="format" label="File format" defaultValue={format} options={['json', 'csv']} key={format} />
          <details className="care-import-schema">
            <summary><Icon name="info" size={14} />Required source fields<Icon name="chevron-down" size={13} /></summary>
            <p className="microcopy">Required fields: event_id, source_organization, patient_id, patient_name, order_id, result_version, test_code, issued_at, identity_verified. Only fictional records may be imported.</p>
          </details>
        </ActionForm>
        <p className="care-intake-safeguard"><Icon name="shield" size={15} />Import creates owned reconciliation work. Identity and clinical evidence still need their authorized checks.</p>
      </Disclosure>
    </div>
  );
}
