# ML Pipeline Diagram

```mermaid
flowchart TD
  Seed[Synthetic seed data with deterministic dispute labels] --> Features[Feature extraction from transactions, customers, merchants, devices, disputes]
  Features --> Split[Stratified train / validation / held-out test split]
  Split --> Candidates[Compare Logistic Regression, Random Forest, XGBoost]
  Candidates --> Select[Select on validation recall with F1 and ROC-AUC tie-breakers]
  Select --> Test[Single held-out test evaluation]
  Test --> Artifacts[Persist model, metadata, registry, evaluation JSON/Markdown]
  Artifacts --> API[Prediction and metrics APIs]
```

Metrics shown in the UI and README must come from `backend/artifacts/models/chargeback-risk-v1.evaluation.json` after running `python -m app.ml.train_model`. If that artifact is absent, no performance numbers should be claimed.
