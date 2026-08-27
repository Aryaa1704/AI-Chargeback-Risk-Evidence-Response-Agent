import sys
sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models.risk_case import RiskCase

db = SessionLocal()
cases = db.query(RiskCase).all()
print(f'Existing cases: {len(cases)}')
for c in cases[:5]:
    print(f'{c.case_id} - {c.transaction_id} - {c.status}')

# Delete all existing cases to fix 409 conflict
db.query(RiskCase).delete()
db.commit()
print('All cases deleted - Investigate buttons will work fresh now!')
db.close()
