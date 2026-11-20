"""Execution-time source evidence; no scoring or clinical-state mutation."""
from __future__ import annotations
import sys,shutil
from pathlib import Path
from .common import ROOT,read_json,atomic_json,file_hash,digest,now

def capture_backend_before_import(database_path:Path)->dict|None:
    """Archive actual backend bytes at first full-journey test-store import.

    The model benchmark starts before API tests run. Application security repairs
    may finish while model requests execute. This records the real first-import
    version instead of pretending an earlier candidate-source capture applied.
    """
    prefix='suhail-';suffix='-journey-execution.sqlite3';name=database_path.name
    if not name.startswith(prefix) or not name.endswith(suffix):return None
    run_id=name[len(prefix):-len(suffix)]
    if not run_id or not all(c.isalnum() or c in '-_' for c in run_id):raise ValueError('invalid_provenance_run')
    run=ROOT/'reports/runs'/run_id
    if not (run/'manifest.json').exists():return None
    evidence=run/'actual-backend-first-import.json'
    files={str(p.relative_to(ROOT)):file_hash(p) for p in (ROOT/'services/api').glob('*.py')}
    previous=read_json(evidence)
    if previous:
        if previous['file_hashes']!=files:raise ValueError('backend_changed_after_first_journey_freeze')
        return previous
    for rel,expected in files.items():
        target=run/'actual-backend-source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
        if file_hash(target)!=expected:raise ValueError('backend_changed_during_preimport_capture')
    instrumentation={}
    for source in (Path(__file__),ROOT/'evals/domain_harness.py'):
        rel=str(source.relative_to(ROOT));target=run/'journey-provenance-instrumentation'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);instrumentation[rel]=file_hash(target)
    record={'id':'actual-backend-at-first-journey-import','captured_at':now(),'file_hashes':files,'backend_hash':digest(files),'already_loaded_api_modules':[name for name in sys.modules if name.startswith('services.api')],'captured_before_services_api_db_and_domain_import':not any(name in sys.modules for name in ('services.api.db','services.api.domain')),'instrumentation_revision':instrumentation,'reason':'Instrumentation-only source capture added before DomainHarness first import to distinguish final backend security repairs from earlier model-source freeze; no model/prompt/RAG/scorer/truth/command changes.','prior_backend_captures':'Earlier scheduler-resume/prejourney captures are intermediate; this execution-time capture governs actual fulljourneys. Raw case backend_source_hash from the scheduler is a resume-point label, not a replacement for this phase evidence.','applies_to_components':['journeys'],'artifact_path':'actual-backend-source'}
    atomic_json(evidence,record);return record
