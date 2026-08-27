import sys
sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models.risk_case import RiskCase

db = SessionLocal()
count = db.query(RiskCase).count()
print(f'Cases before: {count}')
db.query(RiskCase).delete()
db.commit()
count = db.query(RiskCase).count()
print(f'Cases after: {count}')
db.close()
