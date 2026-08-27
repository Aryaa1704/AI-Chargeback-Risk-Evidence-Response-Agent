import sys
sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models.transaction import Transaction
from app.ml.prediction import predict_risk

db = SessionLocal()
txns = db.query(Transaction).all()
print(f'DB transactions: {len(txns)}')

success = 0
for i, txn in enumerate(txns):
    try:
        predict_risk(txn.transaction_id, db)
        success += 1
    except Exception as e:
        pass
    if i % 20 == 0:
        print(f'Progress: {i+1}/{len(txns)}')

db.close()
print(f'Done: {success}/{len(txns)}')
