import sys
sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction

db = SessionLocal()
txn = db.query(Transaction).first()
print(f'Transaction id (int): {txn.id}')
print(f'Transaction transaction_id (str): {txn.transaction_id}')

pred = db.query(RiskPrediction).first()
print(f'Prediction transaction_id: {pred.transaction_id}')
print(f'Match: {pred.transaction_id == txn.id}')
db.close()
