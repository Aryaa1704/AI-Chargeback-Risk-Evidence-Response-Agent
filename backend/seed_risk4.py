import sys
sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models.transaction import Transaction
from app.ml.prediction import predict_risk
import inspect
print(inspect.signature(predict_risk))
