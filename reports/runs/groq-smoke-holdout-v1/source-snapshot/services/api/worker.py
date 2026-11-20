"""Durable leases, bounded local/provider delivery, and persisted deadline recovery."""
import random
import time
from datetime import timedelta
import httpx
from sqlalchemy import select, or_, and_
from .config import settings
from .db import SessionLocal, Outbox, Case, Communication, Escalation, Handoff, Task
from .domain import clock, due, rows, outbox, task, complete, milestone, audit, add_delay

ACTOR = {'id': 'worker', 'organization': 'source-clinic', 'role': 'system', 'name': 'Durable worker'}


def process_timers(db, case_id=None):
    current = clock(db).isoformat()
    count = 0
    for item in db.scalars(select(Escalation).where(Escalation.acknowledged_at == None,
            Escalation.escalated_at == None, Escalation.due_at <= current).with_for_update(skip_locked=True)):
        if case_id and item.case_id != case_id:
            continue
        case = db.get(Case, item.case_id)
        item.escalated_at = current
        task(db, case, 'urgent_backup:' + item.id, 'Acknowledge overdue urgent review', assignee=item.backup, hours=1)
        outbox(db, case, 'urgent_backup', 'staff-simulator', {'escalation_id': item.id, 'recipient': item.backup})
        audit(db, ACTOR, case, 'urgent_backup_escalated', {'escalation_id': item.id})
        count += 1
    for item in db.scalars(select(Handoff).where(Handoff.status == 'requested', Handoff.due_at <= current).with_for_update(skip_locked=True)):
        if case_id and item.case_id != case_id:
            continue
        case = db.get(Case, item.case_id)
        item.status = 'expired'
        item.reason = 'Acceptance service window elapsed; sending owner retained'
        item.decided_at = current
        add_delay(case, 'handoff_timeout')
        task(db, case, 'referral_recovery', 'Contact the provider or find another receiving service', reason='handoff_timeout')
        audit(db, ACTOR, case, 'handoff_timeout', {'handoff_id': item.id})
        count += 1
    for item in db.scalars(select(Task).where(Task.status.notin_(['completed', 'cancelled', 'overdue']), Task.due_at <= current)):
        if case_id and item.case_id != case_id:
            continue
        item.status = 'overdue'
        case = db.get(Case, item.case_id)
        add_delay(case, 'overdue:' + item.type)
        audit(db, ACTOR, case, 'task_overdue', {'task_id': item.id, 'backup': case.backup_queue})
        count += 1
    db.commit()
    return count


def run_once(db=None, deliver_external=True, case_id=None):
    own_session = db is None
    if own_session:
        db = SessionLocal()
    delivered = failed = 0
    try:
        timers = process_timers(db, case_id=case_id)
        current = clock(db).isoformat()
        query = select(Outbox).where(or_(
            and_(Outbox.status.in_(['pending', 'retry']), Outbox.next_attempt_at <= current),
            and_(Outbox.status == 'processing', Outbox.lease_until <= current)))
        if not deliver_external:
            query = query.where(Outbox.kind != 'referral')
        if case_id:
            query = query.where(Outbox.case_id == case_id)
        jobs = list(db.scalars(query.order_by(Outbox.created_at).limit(50).with_for_update(skip_locked=True)))
        ids = [j.id for j in jobs]
        for item in jobs:
            item.status = 'processing'
            item.lease_until = (clock(db) + timedelta(minutes=2)).isoformat()
            item.attempts += 1
        db.commit()
        for job_id in ids:
            item = db.get(Outbox, job_id)
            case = db.get(Case, item.case_id)
            try:
                if item.payload.get('simulate_failure'):
                    raise RuntimeError('simulated_delivery_failure')
                if item.kind == 'referral':
                    url = settings()['provider_a_url'] if item.destination == 'provider-a' else settings()['provider_b_url']
                    payload = {**item.payload, 'outbox_id': item.id, 'version': case.version}
                    response = httpx.post(url.rstrip('/') + '/referrals', json=payload,
                        headers={'X-Connector-Token': settings()['connector_token']}, timeout=8)
                    response.raise_for_status()
                elif item.kind == 'notification':
                    msg = db.get(Communication, item.payload['communication_id'])
                    if msg:
                        if item.payload.get('result_version', 1) == case.result_version:
                            msg.delivery_status = 'delivered'
                            msg.delivered_at = clock(db).isoformat()
                            complete(db, case, 'notification')
                            milestone(db, case, 'notification', evidence_id=msg.id)
                        else:
                            msg.delivery_status = 'superseded'
                        case.version += 1
                elif item.kind not in {'urgent_alert', 'urgent_backup'}:
                    raise RuntimeError('unsupported_outbox_kind')
                item.status = 'delivered'
                item.error_code = None
                item.lease_until = None
                complete(db, case, 'integration_recovery:' + item.id)
                audit(db, ACTOR, case, 'outbox_delivered', {'outbox_id': item.id, 'kind': item.kind, 'attempt': item.attempts})
                delivered += 1
            except Exception as exc:
                # Error classes only; never persist HTTP headers, tokens, or provider response bodies.
                item.error_code = 'provider_unavailable' if isinstance(exc, httpx.HTTPError) else 'delivery_failed'
                item.status = 'dead_letter' if item.attempts >= 3 else 'retry'
                item.next_attempt_at = (clock(db) + timedelta(seconds=min(300, 2 ** item.attempts) + random.random())).isoformat()
                item.lease_until = None
                if item.kind == 'notification':
                    msg = db.get(Communication, item.payload.get('communication_id'))
                    if msg:
                        msg.delivery_status = 'failed'
                task(db, case, 'integration_recovery:' + item.id, 'Repair and retry integration delivery',
                    assignee=item.owner, reason=item.error_code)
                add_delay(case, item.error_code)
                audit(db, ACTOR, case, 'outbox_failed', {'outbox_id': item.id, 'code': item.error_code, 'attempt': item.attempts})
                failed += 1
            db.commit()
        return {'delivered': delivered, 'failed': failed, 'timers': timers}
    finally:
        if own_session:
            db.close()


def main():
    from .db import init_db
    init_db()
    while True:
        run_once()
        time.sleep(2)


if __name__ == '__main__':
    main()
