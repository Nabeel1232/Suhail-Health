"""Render the versioned score-only audit from its immutable existing-response records."""
import csv
import html
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
folder=root/'reports/runs/groq-smoke-holdout-v1/secondary-scoring-audit'
summary=json.loads((folder/'summary.json').read_text())
cases=[json.loads(line) for line in (folder/'cases.jsonl').read_text().splitlines() if line]
assert len(cases)==summary['existing_live_responses_audited']
assert sum(c['score']['passed'] is True for c in cases)==summary['task_passed']
assert all(c['new_api_calls']==0 for c in cases)
fields=['case_id','component','passed','candidate_call_id','scorer_version','scored_at']
rows=[{**{k:c[k] for k in fields if k!='passed'},'passed':c['score']['passed']} for c in cases]
with (folder/'metrics.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
intro=f"{len(cases)} existing live responses audited; {summary['task_passed']} correct; {summary['task_incorrect']} incorrect; 0 new API calls. Original primary scoring failures and denominators remain unchanged."
lines=['# Suhail Health secondary scoring audit','',intro,'',summary['reason'],'','| Function | Original case | Correct | Original response ID | Scorer |','|---|---|---|---|---|']
for c in rows:lines.append(f"| {c['component']} | {c['case_id']} | {c['passed']} | {c['candidate_call_id']} | {c['scorer_version']} |")
(folder/'summary.md').write_text('\n'.join(lines)+'\n')
table=''.join('<tr>'+''.join('<td>'+html.escape(str(c[k]))+'</td>' for k in fields)+'</tr>' for c in rows)
(folder/'summary.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suhail Health secondary scoring audit</title><style>body{font:16px system-ui;background:#f4f8f7;color:#143d3c;max-width:1200px;margin:32px auto;padding:20px}h1,a{color:#006568}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #d4e2de;overflow-wrap:anywhere}th{background:#e8f3f0}.table{overflow:auto}</style><h1>Suhail Health · Secondary scoring audit</h1><p>'+html.escape(intro)+'</p><p>'+html.escape(summary['reason'])+'</p><div class="table"><table><tr>'+''.join('<th>'+html.escape(k.replace('_',' '))+'</th>' for k in fields)+'</tr>'+table+'</table></div><p><a href="summary.json">JSON</a> · <a href="summary.md">Markdown</a> · <a href="metrics.csv">CSV</a> · <a href="cases.jsonl">Hash-linked audit records</a></p></html>')
print('Secondary audit rendered in HTML/Markdown/CSV from six existing response records; zero new inference.')
