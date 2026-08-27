import sys, uuid
from datetime import datetime
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
            prediction_id=str(uuid.uuid4()),
            transaction_id=txn.transaction_id,
            risk_score=0.63,
            risk_label="MEDIUM",
            prediction="CHARGEBACK_RISK",
            created_at=datetime.utcnow()
        )
        db.add(rp)
        success += 1

db.commit()
db.close()
print(f'Done: {success} predictions inserted')
