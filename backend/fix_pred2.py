import sys, json
from datetime import datetime, timezone
sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction

db = SessionLocal()

# Delete wrong predictions
db.query(RiskPrediction).delete()
db.commit()

# Re-insert with correct transaction.id (UUID)
txns = db.query(Transaction).all()
print(f'Transactions: {len(txns)}')

for txn in txns:
    rp = RiskPrediction(
        transaction_id=txn.id,
        model_version="chargeback-risk-v1",
        risk_score=0.63,
        risk_band="MEDIUM",
        explanation=json.dumps({"top_factors": []}),
        created_at=datetime.now(timezone.utc)
    )
    db.add(rp)

db.commit()
count = db.query(RiskPrediction).count()
print(f'Done: {count} predictions inserted correctly')
db.close()
