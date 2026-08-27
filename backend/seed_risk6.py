import sys, uuid
from datetime import datetime, timezone
sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models.transaction import Transaction
from app.models.risk_prediction import RiskPrediction

db = SessionLocal()
txns = db.query(Transaction).all()
print(f'Transactions: {len(txns)}')

success = 0
for txn in txns:
    existing = db.query(RiskPrediction).filter(RiskPrediction.transaction_id == txn.transaction_id).first()
    if not existing:
        rp = RiskPrediction(
            transaction_id=txn.transaction_id,
            model_version="chargeback-risk-v1",
            risk_score=0.63,
            risk_band="MEDIUM",
            explanation={"top_factors": []},
            created_at=datetime.now(timezone.utc)
        )
        db.add(rp)
        success += 1

db.commit()
db.close()
print(f'Done: {success} predictions inserted')
