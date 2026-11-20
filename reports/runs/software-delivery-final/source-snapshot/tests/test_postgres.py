"""Real PostgreSQL concurrency checks in an isolated, disposable test schema."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from services.api.config import settings
from services.api.db import Base, Case, Task, SourceEvent
from services.api.domain import intake, command
from services.api.seed import actor

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Opt-in actual PostgreSQL test; isolated schema required')


@pytest.fixture
def pgstore():
    schema = 'suhail_test_' + uuid.uuid4().hex
    admin_engine = create_engine(settings()['database_url'])
    if admin_engine.dialect.name != 'postgresql':
        pytest.skip('Actual PostgreSQL URL is required')
    with admin_engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA ' + schema))
    engine = admin_engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        with admin_engine.begin() as conn:
            conn.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        admin_engine.dispose()


def source():
    return {'case_id': 'PG-CASE', 'dataset': 'isolated-test', 'event_id': 'PG-EVENT',
        'source_organization': 'source-clinic', 'patient_id': 'pg-patient', 'patient_name': 'Synthetic PG patient',
        'order_id': 'pg-order', 'result_version': 1, 'test_code': 'FIT_POSITIVE',
        'issued_at': datetime.now(timezone.utc).isoformat(), 'identity_verified': True, 'trusted_urgent': False}


def test_postgres_duplicate_simultaneous_intake_is_one_source_case(pgstore):
    data = source()
    def submit(_):
        with pgstore() as db:
            return intake(db, actor('navigator'), data)['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(submit, range(2)))
    assert ids == ['PG-CASE', 'PG-CASE']
    with pgstore() as db:
        assert len(list(db.scalars(select(Case)))) == 1
        assert len(list(db.scalars(select(SourceEvent)))) == 1
        assert len(list(db.scalars(select(Task)))) == 9


def test_postgres_concurrent_same_version_cannot_lose_an_update(pgstore):
    with pgstore() as db:
        intake(db, actor('navigator'), source())
    def submit(i):
        with pgstore() as db:
            try:
                result = command(db, actor('navigator'), 'PG-CASE', 'task',
                    {'expected_version': 1, 'idempotency_key': 'concurrent-command-' + str(i),
                    'type': 'transport-' + str(i), 'next_action': 'Arrange synthetic transport', 'assignee': 'navigation-team'})
                return ('ok', result['version'])
            except HTTPException as exc:
                db.rollback()
                return ('error', exc.status_code)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(results) == [('error', 409), ('ok', 2)]
    with pgstore() as db:
        assert db.get(Case, 'PG-CASE').version == 2
        assert len([t for t in db.scalars(select(Task)) if t.type.startswith('transport-')]) == 1
