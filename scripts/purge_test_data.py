"""Remove non-demo-v1 cases and their dependent rows from the synthetic demo database."""
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.api.config import settings
from services.api.db import AccessGrant, Case, Outbox, Receipt, SessionLocal, SourceArtifact, SourceEvent
from services.api.domain import CHILDREN


def main():
    if not settings()['demo_mode']:
        raise SystemExit('Synthetic demonstration mode is disabled. No records changed.')
    with SessionLocal.begin() as db:
        non_demo = Case.dataset != 'demo-v1'
        counts = list(db.execute(select(Case.dataset, func.count()).where(non_demo)
            .group_by(Case.dataset).order_by(Case.dataset)))
        ids = select(Case.id).where(non_demo)
        for model in [AccessGrant, Outbox, Receipt, SourceEvent, SourceArtifact, *CHILDREN.values()]:
            db.execute(delete(model).where(model.case_id.in_(ids)))
        db.execute(delete(Case).where(non_demo))
    for dataset, count in counts:
        print(f'{dataset}: removed {count} case(s)')
    print(f'Total: removed {sum(count for _, count in counts)} case(s)')


if __name__ == '__main__':
    main()
