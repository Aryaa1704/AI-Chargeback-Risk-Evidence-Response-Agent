import sys
sys.path.insert(0, '.')
from app.models.risk_prediction import RiskPrediction
print([c.name for c in RiskPrediction.__table__.columns])
